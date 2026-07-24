#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
stock_deriv.py — 종목별 파생 포지셔닝 (v2: KR 파생상장 전 종목 + US 옵션 종목)

v1(파일럿 삼성전자·SK하이닉스, likeItmsNm 종목별 조회) → v2 확장:
  · KR: FSC 벌크(일자당 선물 1콜 + 옵션 3콜 페이징)로 전 상장 기초자산 수집.
        itmsNm 에서 기초자산명을 파싱해 screener_pool 의 종목명과 매칭(지수·국채·FX 자동 배제).
        지표: 베이시스·선물OI·PCR(OI)·IV스큐·GEX + 60일 z (백필 가능 — 2020년까지 조회됨)
  · US: yfinance 옵션체인(deriv_signals.ingest.option_metrics 재사용 — SPX/NDX와 동일 산식).
        선물이 없어 베이시스·선물OI는 없음. PCR(OI)·IV스큐(25Δ)·GEX 만.
        옵션체인은 포인트인타임(백필 불가) → z 는 수집 개시일부터 누적(20일 후 산출).

실행: venv python 권장(US 파트가 yfinance·pandas 필요 — 없으면 US 자동 스킵)
  /home/ubuntu/namoobi/venv/bin/python scripts/stock_deriv.py            # 증분
  /home/ubuntu/namoobi/venv/bin/python scripts/stock_deriv.py --backfill # KR 130일 백필
cron: 40 13 * * 1-6 (KR T+1 반영 후) + 50 6 * * 2-6 (US 마감 후)

산출: data/db/stock_deriv.json
  {"asof","src","stocks":{code:{"name","mkt":"kr|us","days":[...],"z":{...},"latest":{...}}}}
"""
import json, os, re, sys, time, math
from datetime import date, datetime, timedelta
from urllib.parse import urlencode
import urllib.request

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB   = os.path.join(BASE, "data", "db")
OUT  = os.path.join(DB, "stock_deriv.json")
API  = "https://apis.data.go.kr/1160100/service/GetDerivativeProductInfoService"

US_STOCKS = {"AAPL": "애플", "NVDA": "엔비디아"}   # 폴백 — main()에서 시총 상위 100으로 대체

def _us_universe(n=100):
    """(2026-07-24) US 옵션 수집 대상 — 스크리너 풀 시총 상위 n종목 (옵션 유동성 대부분 커버)."""
    try:
        pool = json.load(open(os.path.join(DB, "screener_pool.json"), encoding="utf-8"))
        us = sorted((r for r in (pool.get("us") or []) if r.get("cap")),
                    key=lambda r: -r["cap"])[:n]
        out = {r["c"]: (r.get("kn") or r.get("n") or r["c"]) for r in us}
        return out or dict(US_STOCKS)
    except Exception:
        return dict(US_STOCKS)

Z_WIN = 60
RISK_FREE = 0.03
KEEP_DAYS = 280


def _key():
    k = os.environ.get("DATAGOKR_KEY")
    if k: return k.strip()
    for p in [os.path.expanduser("~/namoobi/secrets/datagokr.key"),
              "D:/claudeCowork/SECURITY/data.go.kr.txt"]:
        try:
            t = open(p, encoding="utf-8").read().strip()
            if t: return t.splitlines()[0].strip()
        except Exception: pass
    raise SystemExit("data.go.kr 인증키 없음")

KEY = _key()


def _get(op, tries=4, **params):
    p = {"serviceKey": KEY, "resultType": "json", **params}
    url = f"{API}/{op}?{urlencode(p)}"
    last = None
    for _ in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                j = json.loads(r.read().decode("utf-8"))
            b = j["response"]["body"]
            its = b.get("items") or {}
            rows = its.get("item") or []
            if isinstance(rows, dict): rows = [rows]
            return b.get("totalCount", 0), rows
        except Exception as e:
            last = e; time.sleep(2)
    print(f"  [warn] {op} {params.get('basDt')} 실패: {last}")
    return 0, None


def _f(v):
    try:
        v = str(v).replace(",", "").strip()
        return float(v) if v not in ("", "-") else None
    except Exception: return None


def _expiry(yyyymm):
    """KRX 주식선물·옵션 최종거래일 = 결제월 두 번째 목요일"""
    y, m = int(yyyymm[:4]), int(yyyymm[4:6])
    d = date(y, m, 1)
    th = [d + timedelta(days=i) for i in range(31)
          if (d + timedelta(days=i)).month == m and (d + timedelta(days=i)).weekday() == 3]
    return th[1]


def _gamma(S, K, T, sigma):
    if not all([S, K, sigma]) or T <= 0 or sigma <= 0: return 0.0
    try:
        d1 = (math.log(S / K) + (RISK_FREE + sigma * sigma / 2) * T) / (sigma * math.sqrt(T))
        return math.exp(-d1 * d1 / 2) / math.sqrt(2 * math.pi) / (S * sigma * math.sqrt(T))
    except Exception: return 0.0


# ── KR: 풀 이름 → 코드 매핑 ─────────────────────────────────────────────
def _pool_map():
    p = os.path.join(DB, "screener_pool.json")
    try:
        kr = json.load(open(p, encoding="utf-8")).get("kr") or []
        return {r["n"].strip(): r["c"] for r in kr if r.get("n") and r.get("c")}
    except Exception as e:
        raise SystemExit(f"screener_pool.json 로드 실패: {e}")


_FUT_RE = re.compile(r"^(.+?)\s+F\s+(\d{6})")
_OPT_RE = re.compile(r"^(.+?)\s+([CP])\s+(\d{6})\s+([\d,]+)")


def kr_bulk_day(basdt, name2code):
    """하루치 전체 선물+옵션 벌크 → {code: rec}. 데이터 없으면 None(휴장)."""
    tc, fut = _get("getStockFuturesPriceInfo", basDt=basdt, numOfRows=10000, pageNo=1)
    if fut is None or not fut: return None
    opts = []
    page = 1
    while True:
        tc, rows = _get("getOptionsPriceInfo", basDt=basdt, numOfRows=10000, pageNo=page)
        if rows: opts += rows
        if not rows or len(opts) >= tc or page >= 5: break
        page += 1

    F = {}   # name -> [(ym, row)]
    for r in fut:
        m = _FUT_RE.match((r.get("itmsNm") or "").strip())
        if not m: continue
        nm = m.group(1).strip()
        if nm in name2code: F.setdefault(nm, []).append((m.group(2), r))
    O = {}   # name -> [(side, strike, iv, oi, ym)]
    for r in opts:
        m = _OPT_RE.match((r.get("itmsNm") or "").strip())
        if not m: continue
        nm = m.group(1).strip()
        if nm not in name2code: continue
        O.setdefault(nm, []).append((m.group(2), _f(m.group(4)),
                                     _f(r.get("iptVlty")), int(_f(r.get("opnint")) or 0),
                                     m.group(3)))

    out = {}
    for nm, rows in F.items():
        rows.sort(key=lambda x: x[0])
        ym, near = rows[0]
        spot = _f(near.get("sptPrc")); futp = _f(near.get("clpr"))
        if not spot or not futp: continue
        rec = {"d": basdt, "spot": spot, "fut": futp,
               "basis": round(futp - spot, 1),
               "basis_pct": round((futp - spot) / spot * 100, 3),
               "fut_oi": sum(int(_f(r.get("opnint")) or 0) for _, r in rows),
               "pcr_oi": None, "iv_skew": None, "gex": None}
        ch = O.get(nm) or []
        if ch:
            coi = sum(o[3] for o in ch if o[0] == "C")
            poi = sum(o[3] for o in ch if o[0] == "P")
            if coi >= 100 and poi >= 100: rec["pcr_oi"] = round(poi / coi, 3)
            near_ch = [o for o in ch if o[4] == ym and o[2]]
            if near_ch:
                tp, tcs = spot * 0.95, spot * 1.05
                puts  = [o for o in near_ch if o[0] == "P" and o[1] and abs(o[1] - tp) / spot <= 0.03]
                calls = [o for o in near_ch if o[0] == "C" and o[1] and abs(o[1] - tcs) / spot <= 0.03]
                if puts and calls:
                    pv = min(puts,  key=lambda o: abs(o[1] - tp))[2]
                    cv = min(calls, key=lambda o: abs(o[1] - tcs))[2]
                    if pv and cv and abs(pv - cv) <= 30: rec["iv_skew"] = round(pv - cv, 2)
                T = max((_expiry(ym) - datetime.strptime(basdt, "%Y%m%d").date()).days, 1) / 365.0
                tot = 0.0; used = 0
                for side, k, iv, oi, _ym in near_ch:
                    if not oi: continue
                    g = _gamma(spot, k, T, (iv or 0) / 100.0)
                    if g <= 0: continue
                    tot += (1 if side == "C" else -1) * g * oi * 10 * (spot ** 2) / 100.0
                    used += 1
                if used >= 4: rec["gex"] = round(tot / 1e8, 2)   # 억원
        out[name2code[nm]] = rec
    return out


# ── US: yfinance 옵션체인 (deriv_signals 산식 재사용) ────────────────────
def us_day():
    """AAPL·NVDA 등 스냅샷 → {ticker: rec}. yfinance 없으면 {} (KR만 진행)."""
    try:
        sys.path.insert(0, os.path.expanduser("~/namoobi/deriv_signals"))
        from ingest import option_metrics
        import yfinance as yf
    except Exception as e:
        print(f"  [us] 스킵(yfinance 환경 아님): {e}")
        return {}
    out = {}
    for tk in US_STOCKS:
        try:
            m = option_metrics(tk)
            if not m: continue
            h = yf.Ticker(tk).history(period="1d")
            d = h.index[-1].strftime("%Y%m%d") if len(h) else datetime.utcnow().strftime("%Y%m%d")
            spot = float(h["Close"].iloc[-1]) if len(h) else None
            out[tk] = {"d": d, "spot": spot, "fut": None, "basis": None, "basis_pct": None,
                       "fut_oi": None,
                       "pcr_oi": round(m["pcr_oi"], 3) if m.get("pcr_oi") is not None else None,
                       # yfinance IV는 소수(0.30) — KR(%)과 표기 통일 위해 %p 로
                       "iv_skew": round(m["iv_skew_25d"] * 100, 2) if m.get("iv_skew_25d") is not None else None,
                       # GEX $/1%p → 백만달러(M$)
                       "gex": round(m["gex"] / 1e6, 1) if m.get("gex") is not None else None,
                       "expiry": m.get("expiry"), "dte": m.get("dte")}
            print(f"  [us] {tk}: PCR {out[tk]['pcr_oi']} 스큐 {out[tk]['iv_skew']}%p GEX {out[tk]['gex']}M$ ({m.get('expiry')})")
        except Exception as e:
            print(f"  [us] {tk} 실패: {str(e)[:60]}")
        time.sleep(0.7)
    return out


# ── z ───────────────────────────────────────────────────────────────────
def _z(series, win=Z_WIN):
    xs = [x for x in series if x is not None]
    if len(xs) < 20: return None
    xs = xs[-win:]
    mu = sum(xs) / len(xs)
    sd = (sum((x - mu) ** 2 for x in xs) / len(xs)) ** 0.5
    return round((xs[-1] - mu) / sd, 2) if sd > 1e-9 else None


def finalize(days):
    get = lambda k: [d.get(k) for d in days]
    oi = get("fut_oi")
    oi_chg = [None] + [(oi[i] - oi[i-1]) if (oi[i] is not None and oi[i-1] is not None) else None
                       for i in range(1, len(oi))]
    z = {"basis_pct": _z(get("basis_pct")), "fut_oi_chg": _z(oi_chg),
         "pcr_oi": _z(get("pcr_oi")), "iv_skew": _z(get("iv_skew")), "gex": _z(get("gex"))}
    latest = dict(days[-1]) if days else {}
    if len(days) >= 2 and days[-1].get("fut") and days[-2].get("fut"):
        latest["fut_chg_pct"] = round((days[-1]["fut"] / days[-2]["fut"] - 1) * 100, 2)
    if oi_chg: latest["fut_oi_chg"] = oi_chg[-1]
    return z, latest


def main():
    global US_STOCKS
    US_STOCKS = _us_universe(100)
    back = 0
    for a in sys.argv[1:]:
        if a == "--backfill": back = 130
        elif a.isdigit(): back = int(a)

    prev = {}
    if os.path.exists(OUT):
        try: prev = json.load(open(OUT, encoding="utf-8")).get("stocks", {})
        except Exception: pass

    name2code = _pool_map()
    today = date.today()

    # 수집 대상 날짜: 백필이면 range, 증분이면 KR 최종일 다음날~어제
    kr_days = {c: {d["d"]: d for d in (v.get("days") or [])}
               for c, v in prev.items() if v.get("mkt", "kr") == "kr"}
    last = max((max(ds) for ds in kr_days.values() if ds), default=None)
    start = today - timedelta(days=back) if back else \
            (datetime.strptime(last, "%Y%m%d").date() + timedelta(days=1) if last
             else today - timedelta(days=130))

    # (2026-07-24) 벌크 콜이 회당 15~30초라 순차로는 백필이 수 시간 — 날짜 병렬(4워커)
    from concurrent.futures import ThreadPoolExecutor
    dates = []
    d = start
    while d < today:
        if d.weekday() < 5: dates.append(d.strftime("%Y%m%d"))
        d += timedelta(days=1)
    ndays = 0
    with ThreadPoolExecutor(max_workers=4) as ex:
        for bd, got in zip(dates, ex.map(lambda x: kr_bulk_day(x, name2code), dates)):
            if got:
                ndays += 1
                for code, rec in got.items():
                    kr_days.setdefault(code, {})[bd] = rec
                print(f"  [kr] {bd}: {len(got)}종목", flush=True)
    print(f"[stock_deriv] KR 벌크 {ndays}일 수집 · 종목 {len(kr_days)}개", flush=True)

    us = us_day()

    out = {}
    for code, ds in kr_days.items():
        arr = [ds[k] for k in sorted(ds)][-KEEP_DAYS:]
        if not arr: continue
        z, latest = finalize(arr)
        nm = next((n for n, c in name2code.items() if c == code), code)
        out[code] = {"name": nm, "mkt": "kr", "days": arr, "z": z, "latest": latest}
    for tk, rec in us.items():
        pv = prev.get(tk, {})
        ds = {x["d"]: x for x in (pv.get("days") or [])}
        ds[rec["d"]] = rec
        arr = [ds[k] for k in sorted(ds)][-KEEP_DAYS:]
        z, latest = finalize(arr)
        out[tk] = {"name": US_STOCKS.get(tk, tk), "mkt": "us", "days": arr, "z": z, "latest": latest}
    # US 티커가 이번 실행에서 실패해도 기존 이력은 보존
    for tk in US_STOCKS:
        if tk not in out and tk in prev: out[tk] = prev[tk]

    os.makedirs(DB, exist_ok=True)
    json.dump({"asof": datetime.now().strftime("%Y-%m-%d %H:%M"),
               "src": "KR=금융위 FSC 파생상품시세정보(T+1 확정치) · US=Yahoo 옵션체인(마감 스냅샷·백필 불가→z 누적 중)",
               "stocks": out}, open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
    # (2026-07-24) 스크리너 '파생·수급판정' 컬럼용 slim 점수 소스 — z 3종만 코드별로 (2.6MB → 수 KB)
    slim = {c: {"b": v["z"].get("basis_pct"), "p": v["z"].get("pcr_oi"), "s": v["z"].get("iv_skew"),
                # o=옵션 상장 여부(CASE1/2 구분) — 이력에 옵션값이 하루라도 있으면 1
                "o": 1 if any((x.get("pcr_oi") is not None) or (x.get("gex") is not None)
                              for x in v["days"]) else 0}
            for c, v in out.items() if v.get("z")}
    json.dump({"asof": datetime.now().strftime("%Y-%m-%d %H:%M"), "s": slim},
              open(os.path.join(DB, "stock_deriv_score.json"), "w", encoding="utf-8"), ensure_ascii=False)
    nkr = sum(1 for v in out.values() if v["mkt"] == "kr")
    print(f"[stock_deriv] ✅ 저장 — KR {nkr}종목 · US {len(out)-nkr}종목 → {OUT}")


if __name__ == "__main__":
    main()
