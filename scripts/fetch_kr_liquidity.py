#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fetch_kr_liquidity.py — 3.1.14 국내 유동성·레버리지 시계열 수집 (cron 1일 3회).

수집 항목 → data/kr_liquidity.db
  [일별 kr_liq_daily]
    · 투자자예탁금·위탁매매미수금·미수금대비 반대매매금액/비중  (금융위 증시자금 API, 금투협 원천, T+2)
    · 신용융자잔고 전체/코스피/코스닥                          (금융위 신용공여 API, T+2)
    · 코스피/코스닥 지수·거래대금                              (다음금융, T+0)
  [월별 kr_liq_monthly]
    · M2(평잔, 161Y006/BBHA00) · 코스피 종가(901Y014/1070000) · 코스닥 종가(901Y014/2090000)  (ECOS, ~2개월 지연)
    · 정기예금 말잔(104Y015/BDAA31, 십억원 — 예탁금과의 자금이동 대비용, ~1개월 지연)

cron 슬롯 (deploy/crontab.txt):
  06:35 안전망(전일 재시도+ECOS 월별 체크) · 14:10 금융위 T+2 신규분(13시 갱신) · 16:10 다음 T+0 당일 종가
같은 스크립트를 모든 슬롯에서 실행 — 최근 lookback 일을 기간조회해 upsert 하므로 멱등.

키: keys/data.go.kr.txt · keys/ecos.txt (git 미포함 — scp 로 배포, PC 에선 SECURITY 폴백).
Usage: fetch_kr_liquidity.py [--backfill 400]   (기본 lookback 30일)
"""
import json, sys, sqlite3, ssl, urllib.request, urllib.parse, datetime as dt
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DB   = BASE / "data" / "kr_liquidity.db"
LOOK = int(sys.argv[sys.argv.index("--backfill")+1]) if "--backfill" in sys.argv else 30
CTX  = ssl.create_default_context()

def _key(fname, sec_name):
    for p in [BASE/"keys"/fname,
              Path("D:/claudeCowork/SECURITY")/sec_name] + \
             sorted(Path("/sessions").glob(f"*/mnt/claudeCowork/SECURITY/{sec_name}")):
        try: return Path(p).read_text(encoding="utf-8").strip()
        except Exception: pass
    return None

def get(url, headers=None):
    req = urllib.request.Request(url, headers=headers or {"User-Agent": "Mozilla/5.0 (namoobi)"})
    for t in range(3):                        # 서버→data.go.kr SSL 핸드셰이크가 간헐 지연 → 재시도
        try:
            with urllib.request.urlopen(req, timeout=40, context=CTX) as r:
                return json.loads(r.read().decode())
        except Exception:
            if t == 2: raise
            import time; time.sleep(3)

def init():
    DB.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB, timeout=20)
    c.execute("PRAGMA journal_mode=WAL")     # app.py 읽기와 cron 쓰기 동시성
    c.execute("PRAGMA busy_timeout=15000")
    c.execute("""CREATE TABLE IF NOT EXISTS kr_liq_daily(
        date TEXT PRIMARY KEY, deposit REAL, ucol REAL, opp_amt REAL, opp_ratio REAL,
        crd_whl REAL, crd_kospi REAL, crd_kosdaq REAL,
        kospi REAL, kospi_trdval REAL, kosdaq REAL, kosdaq_trdval REAL)""")
    c.execute("""CREATE TABLE IF NOT EXISTS kr_liq_monthly(
        month TEXT PRIMARY KEY, m2 REAL, kospi REAL, kosdaq REAL)""")
    try: c.execute("ALTER TABLE kr_liq_monthly ADD COLUMN tdep REAL")   # (2026-08-02) 정기예금 말잔(십억원)
    except Exception: pass
    return c

def up(c, date, **cols):
    keys = list(cols)
    c.execute(f"""INSERT INTO kr_liq_daily(date,{','.join(keys)})
        VALUES(?,{','.join('?'*len(keys))})
        ON CONFLICT(date) DO UPDATE SET
        {','.join(f'{k}=COALESCE(excluded.{k},kr_liq_daily.{k})' for k in keys)}""",
        (date, *cols.values()))

def upm(c, month, **cols):
    keys = list(cols)
    c.execute(f"""INSERT INTO kr_liq_monthly(month,{','.join(keys)})
        VALUES(?,{','.join('?'*len(keys))})
        ON CONFLICT(month) DO UPDATE SET
        {','.join(f'{k}=COALESCE(excluded.{k},kr_liq_monthly.{k})' for k in keys)}""",
        (month, *cols.values()))

def f(x):
    try: return float(str(x).replace(",", ""))
    except Exception: return None

def fetch_fsc(c, key, beg, end):
    """금융위 증시자금 + 신용공여 (기간조회, T+2)"""
    B = "https://apis.data.go.kr/1160100/service/GetKofiaStatisticsInfoService"
    n = 0
    for op, fn in (("getSecuritiesMarketTotalCapitalInfo",
                    lambda r: dict(deposit=f(r.get("invrDpsgAmt")), ucol=f(r.get("brkTrdUcolMny")),
                                   opp_amt=f(r.get("brkTrdUcolMnyVsOppsTrdAmt")),
                                   opp_ratio=f(r.get("ucolMnyVsOppsTrdRlImpt")))),
                   ("getGrantingOfCreditBalanceInfo",
                    lambda r: dict(crd_whl=f(r.get("crdTrFingWhl")), crd_kospi=f(r.get("crdTrFingScrs")),
                                   crd_kosdaq=f(r.get("crdTrFingKosdaq"))))):
        p = 1
        while True:
            d = get(f"{B}/{op}?serviceKey={key}&resultType=json&numOfRows=600&pageNo={p}"
                    f"&beginBasDt={beg}&endBasDt={end}")
            body = d["response"]["body"]
            items = (body.get("items") or {}).get("item") or []
            for r in items:
                up(c, r["basDt"], **fn(r)); n += 1
            if p * 600 >= int(body["totalCount"]) or not items: break
            p += 1
    return n

def fetch_daum(c, days):
    """다음금융 — 코스피/코스닥 지수·거래대금 (T+0)"""
    H = {"User-Agent": "Mozilla/5.0", "Referer": "https://finance.daum.net"}
    n = 0
    for mkt, ci, cv in (("KOSPI", "kospi", "kospi_trdval"), ("KOSDAQ", "kosdaq", "kosdaq_trdval")):
        page, got = 1, 0
        while got < days:
            d = get(f"https://finance.daum.net/api/market_index/days?page={page}&perPage=100"
                    f"&market={mkt}&pagination=true", H)
            rows = d.get("data") or []
            if not rows: break
            for r in rows:
                tv = f(r.get("accTradePrice"))          # 다음 accTradePrice 단위 = 백만원
                up(c, r["date"][:10].replace("-", ""),
                   **{ci: f(r.get("tradePrice")), cv: tv * 1e6 if tv else None})
                n += 1; got += 1
                if got >= days: break
            if page >= int(d.get("totalPages") or 1): break
            page += 1
    return n

def fetch_ecos(c, key):
    """ECOS 월별 — M2·코스피/코스닥 월말 종가 (신규월만 실질 갱신, 멱등 upsert)"""
    end = dt.date.today().strftime("%Y%m")
    n = 0
    for stat, item, col in (("161Y006", "BBHA00", "m2"),
                            ("901Y014", "1070000", "kospi"),
                            ("901Y014", "2090000", "kosdaq"),
                            ("104Y015", "BDAA31", "tdep")):   # 예금은행 정기예금 말잔(십억원, 2026-08-02)
        try:
            d = get(f"https://ecos.bok.or.kr/api/StatisticSearch/{key}/json/kr/1/400/"
                    f"{stat}/M/201501/{end}/{item}/")
            for r in (d.get("StatisticSearch") or {}).get("row") or []:
                upm(c, r["TIME"], **{col: f(r["DATA_VALUE"])}); n += 1
        except Exception as e:
            print(f"ECOS {stat}/{item} 실패: {e}")
    return n

def main():
    c = init()
    today = dt.date.today()
    beg = (today - dt.timedelta(days=LOOK)).strftime("%Y%m%d")
    end = today.strftime("%Y%m%d")
    kd, ke = _key("data.go.kr.txt", "data.go.kr.txt"), _key("ecos.txt", "한국은행OPENAPI인증키.txt")
    r = {}
    if kd:
        try: r["fsc"] = fetch_fsc(c, kd, beg, end)
        except Exception as e: print("금융위 실패:", e)
    else: print("data.go.kr 키 없음 — 금융위 스킵")
    try: r["daum"] = fetch_daum(c, LOOK)
    except Exception as e: print("다음 실패:", e)
    if ke:
        try: r["ecos"] = fetch_ecos(c, ke)
        except Exception as e: print("ECOS 실패:", e)
    else: print("ECOS 키 없음 — 월별 스킵")
    c.commit()
    last = c.execute("SELECT date, deposit, opp_amt, crd_kosdaq, kospi FROM kr_liq_daily "
                     "WHERE deposit IS NOT NULL ORDER BY date DESC LIMIT 1").fetchone()
    nd = c.execute("SELECT COUNT(*) FROM kr_liq_daily").fetchone()[0]
    nm = c.execute("SELECT COUNT(*) FROM kr_liq_monthly").fetchone()[0]
    # DB 데이터 인벤토리 등록용 스냅샷 (원본은 kr_liquidity.db — 이 json 은 목록·기준일 표시용)
    try:
        t0 = c.execute("SELECT date FROM kr_liq_daily WHERE kospi IS NOT NULL ORDER BY date DESC LIMIT 1").fetchone()
        snap = {"as_of": f"{last[0][:4]}-{last[0][4:6]}-{last[0][6:]}" if last else "",
                "marker": f"T+2:{last[0] if last else ''}|T0:{t0[0] if t0 else ''}|d{nd}m{nm}",
                "data": {"daily_rows": nd, "monthly_rows": nm,
                         "deposit_t": round(last[1]/1e12, 1) if last and last[1] else None,
                         "opp_amt_e": round(last[2]/1e8) if last and last[2] else None,
                         "crd_kosdaq_t": round(last[3]/1e12, 2) if last and last[3] else None}}
        dbdir = BASE / "data" / "db"; dbdir.mkdir(parents=True, exist_ok=True)
        (dbdir / "kr_liquidity.json").write_text(json.dumps(snap, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        print("db 스냅샷 실패:", e)
    print(f"{dt.datetime.now():%m-%d %H:%M} rows={r} daily={nd} monthly={nm} 최신T+2={last}")
    c.close()

if __name__ == "__main__":
    main()
