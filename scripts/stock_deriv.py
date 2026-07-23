#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
stock_deriv.py — 종목별 파생 포지셔닝 수집 (파일럿: 삼성전자·SK하이닉스)

목적: 인덱스 3.1.13(코스피200 파생)을 종목 단위로 내린다.
  개별주식 선물·옵션에서 5개 선행지표를 산출해 일별 시계열 + 60거래일 z 를 만든다.
  ① 선물 베이시스(최근월 선물 − 현물)   ② 선물 미결제약정(OI) 합계·변화
  ③ 풋콜비율 PCR(OI)                    ④ IV 스큐(OTM 풋 IV − OTM 콜 IV)
  ⑤ 딜러 감마 GEX(콜 롱감마 + / 풋 숏감마 −)

소스: 금융위원회_파생상품시세정보 (data.go.kr, 무료·T+1 확정치)
  End Point 에 /service/ 가 반드시 들어간다 (Swagger 기본 URL 에는 빠져 있어 500 남 — 실측).
  옵션: getOptionsPriceInfo  → iptVlty(내재변동성 %)·opnint(미결제) 직접 제공
  선물: getStockFuturesPriceInfo → sptPrc(현물가) 포함 → 베이시스 원콜 계산
  과거 2020년까지 조회됨(실측) → z 는 백필로 즉시 활성 (인덱스처럼 3개월 대기 불필요)

주의(실측 근거):
  - T+1: 기준일 다음 영업일 13시 이후 반영(금요일치=월요일). 백필·저녁 점검용.
  - 개별주식옵션은 유동성이 얇다 → IV 스큐는 표본조건 미달 시 None(빈칸)으로 두고
    사유를 남긴다. PCR 도 양쪽 OI 합이 얇으면 None.
  - 장중(T+0)은 선물 2종(베이시스·OI)만 KIS 로 따로 갱신 예정 — 옵션 3종은 장중
    호가 공백으로 퇴화(인덱스 실측: 장전 PCR 4,199)라 확정치만 쓴다.

산출물: data/db/stock_deriv.json
  {"asof":..., "stocks":{code:{"name":..,"days":[{d,spot,fut,basis,basis_pct,fut_oi,
    pcr_oi,iv_skew,gex}...], "z":{basis_pct:..,fut_oi_chg:..,pcr_oi:..,iv_skew:..,gex:..}}}}

사용: python3 scripts/stock_deriv.py                # 증분(마지막 저장일 다음날~어제)
      python3 scripts/stock_deriv.py --backfill 130 # 최근 130일 백필
cron: 40 13 * * 1-6 (FSC 13시 반영 후)
"""
import json, os, re, sys, time, math, glob
from datetime import date, datetime, timedelta
from urllib.parse import urlencode
import urllib.request

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB   = os.path.join(BASE, "data", "db")
OUT  = os.path.join(DB, "stock_deriv.json")

API  = "https://apis.data.go.kr/1160100/service/GetDerivativeProductInfoService"

# 파일럿 대상 — 파생(주식선물·주식옵션) 상장 종목만 의미가 있다
STOCKS = {"005930": "삼성전자", "000660": "SK하이닉스"}

Z_WIN = 60          # z-score 롤링 창(거래일) — 인덱스 3.1.13 과 동일
RISK_FREE = 0.03    # GEX 감마 산출용 무위험금리(근사)


# ── 인증키 ────────────────────────────────────────────────────────────────
def _key():
    k = os.environ.get("DATAGOKR_KEY")
    if k: return k.strip()
    cands = [os.path.expanduser("~/namoobi/secrets/datagokr.key"),
             "D:/claudeCowork/SECURITY/data.go.kr.txt"]
    cands += glob.glob("/sessions/*/mnt/*/SECURITY/data.go.kr.txt")
    for p in cands:
        try:
            t = open(p, encoding="utf-8").read().strip()
            if t: return t.splitlines()[0].strip()
        except Exception: pass
    raise SystemExit("data.go.kr 인증키 없음 (~/namoobi/secrets/datagokr.key)")

KEY = _key()


def _get(op, tries=4, **params):
    p = {"serviceKey": KEY, "resultType": "json", "numOfRows": params.pop("n", 500),
         "pageNo": 1, **params}
    url = f"{API}/{op}?{urlencode(p)}"
    last = None
    for _ in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                j = json.loads(r.read().decode("utf-8"))
            b = j["response"]["body"]
            its = b.get("items") or {}
            rows = its.get("item") or []
            if isinstance(rows, dict): rows = [rows]
            return rows
        except Exception as e:
            last = e; time.sleep(2)
    print(f"  [warn] {op} {params.get('basDt')} 실패: {last}")
    return []


def _f(v):
    try:
        v = str(v).replace(",", "").strip()
        return float(v) if v not in ("", "-") else None
    except Exception: return None


# ── 만기(잔존일) — KRX 주식옵션 최종거래일 = 결제월 두 번째 목요일 ─────────
def _expiry(yyyymm):
    y, m = int(yyyymm[:4]), int(yyyymm[4:6])
    d = date(y, m, 1)
    thursdays = [d + timedelta(days=i) for i in range(31)
                 if (d + timedelta(days=i)).month == m and (d + timedelta(days=i)).weekday() == 3]
    return thursdays[1]


# ── BS 감마 (GEX용) ──────────────────────────────────────────────────────
def _gamma(S, K, T, sigma):
    if not all([S, K, sigma]) or T <= 0 or sigma <= 0: return 0.0
    try:
        d1 = (math.log(S / K) + (RISK_FREE + sigma * sigma / 2) * T) / (sigma * math.sqrt(T))
        phi = math.exp(-d1 * d1 / 2) / math.sqrt(2 * math.pi)
        return phi / (S * sigma * math.sqrt(T))
    except Exception: return 0.0


# ── 하루치 산출 ──────────────────────────────────────────────────────────
_OPT_RE = re.compile(r"([CP])\s+(\d{6})\s+([\d,]+)")

def one_day(name, basdt):
    """basdt(YYYYMMDD) 하루의 5지표. 데이터 없으면 None(휴장)."""
    fut = _get("getStockFuturesPriceInfo", basDt=basdt, likeItmsNm=name, n=50)
    fut = [r for r in fut if name in (r.get("itmsNm") or "")]
    if not fut: return None
    # 최근월 = 만기 yyyymm 최소 (스프레드 상품 제외: 'F 202608' 단일월물만)
    rows = []
    for r in fut:
        m = re.search(r"F\s+(\d{6})", r.get("itmsNm") or "")
        if m: rows.append((m.group(1), r))
    if not rows: return None
    rows.sort(key=lambda x: x[0])
    ym, near = rows[0]
    spot = _f(near.get("sptPrc")); futp = _f(near.get("clpr"))
    if not spot or not futp: return None
    basis = futp - spot
    fut_oi = sum(int(_f(r.get("opnint")) or 0) for _, r in rows)

    opts = _get("getOptionsPriceInfo", basDt=basdt, likeItmsNm=name, n=2000)
    opts = [r for r in opts if name in (r.get("itmsNm") or "")]
    coi = poi = 0
    chain = []          # (side, strike, iv, oi, ym)
    for r in opts:
        m = _OPT_RE.search(r.get("itmsNm") or "")
        if not m: continue
        side, oym, k = m.group(1), m.group(2), _f(m.group(3))
        oi = int(_f(r.get("opnint")) or 0)
        iv = _f(r.get("iptVlty"))
        if side == "C": coi += oi
        else:           poi += oi
        chain.append((side, k, iv, oi, oym))
    pcr = round(poi / coi, 3) if (coi >= 100 and poi >= 100) else None  # 얇은 날 퇴화 방지

    # IV 스큐 — 최근월 · OTM 5% 지점의 풋 IV − 콜 IV. 표본조건: 목표 행사가 ±3% 내 존재
    near_ch = [c for c in chain if c[4] == ym and c[2]]
    iv_skew = None
    if near_ch and spot:
        tgt_p, tgt_c = spot * 0.95, spot * 1.05
        puts  = [c for c in near_ch if c[0] == "P" and c[1] and abs(c[1] - tgt_p) / spot <= 0.03]
        calls = [c for c in near_ch if c[0] == "C" and c[1] and abs(c[1] - tgt_c) / spot <= 0.03]
        if puts and calls:
            pv = min(puts,  key=lambda c: abs(c[1] - tgt_p))[2]
            cv = min(calls, key=lambda c: abs(c[1] - tgt_c))[2]
            if pv and cv and abs(pv - cv) <= 30:   # 퇴화 IV(호가 공백) 폐기 — 인덱스와 동일 기준
                iv_skew = round(pv - cv, 2)

    # GEX — 최근월 전 행사가. 주식옵션 계약승수 10주. 단위: 억원
    gex = None
    if near_ch and spot:
        T = max(( _expiry(ym) - datetime.strptime(basdt, "%Y%m%d").date()).days, 1) / 365.0
        tot = 0.0; used = 0
        for side, k, iv, oi, _ in near_ch:
            if not oi: continue
            g = _gamma(spot, k, T, (iv or 0) / 100.0)
            if g <= 0: continue
            tot += (1 if side == "C" else -1) * g * oi * 10 * (spot ** 2) / 100.0
            used += 1
        if used >= 4: gex = round(tot / 1e8, 2)

    return {"d": basdt, "spot": spot, "fut": futp,
            "basis": round(basis, 1), "basis_pct": round(basis / spot * 100, 3),
            "fut_oi": fut_oi, "pcr_oi": pcr, "iv_skew": iv_skew, "gex": gex}


# ── z-score ──────────────────────────────────────────────────────────────
def _z(series, win=Z_WIN):
    """마지막 값의 롤링 z. 표본 20개 미만이면 None."""
    xs = [x for x in series if x is not None]
    if len(xs) < 20: return None
    xs = xs[-win:]
    mu = sum(xs) / len(xs)
    sd = (sum((x - mu) ** 2 for x in xs) / len(xs)) ** 0.5
    return round((xs[-1] - mu) / sd, 2) if sd > 1e-9 else None


def finalize(days):
    """days(오름차순)에서 최신 z 묶음 + 파생 시리즈 계산."""
    get = lambda k: [d.get(k) for d in days]
    oi = get("fut_oi")
    oi_chg = [None] + [ (oi[i] - oi[i-1]) if (oi[i] is not None and oi[i-1] is not None) else None
                        for i in range(1, len(oi)) ]
    z = {"basis_pct": _z(get("basis_pct")), "fut_oi_chg": _z(oi_chg),
         "pcr_oi": _z(get("pcr_oi")), "iv_skew": _z(get("iv_skew")), "gex": _z(get("gex"))}
    return z, oi_chg


# ── 메인 ─────────────────────────────────────────────────────────────────
def main():
    back = 0
    for a in sys.argv[1:]:
        if a == "--backfill": back = 130
        elif a.isdigit(): back = int(a)

    prev = {}
    if os.path.exists(OUT):
        try: prev = json.load(open(OUT, encoding="utf-8")).get("stocks", {})
        except Exception: pass

    today = date.today()
    out = {}
    for code, name in STOCKS.items():
        days = {d["d"]: d for d in (prev.get(code, {}) or {}).get("days", [])}
        if back:
            start = today - timedelta(days=back)
        else:
            last = max(days) if days else None
            start = (datetime.strptime(last, "%Y%m%d").date() + timedelta(days=1)) if last \
                    else today - timedelta(days=130)
        d = start; got = 0
        while d < today:                      # 오늘은 아직 미확정(T+1)
            if d.weekday() < 5:
                bd = d.strftime("%Y%m%d")
                if bd not in days:
                    rec = one_day(name, bd)
                    if rec: days[bd] = rec; got += 1
                    time.sleep(0.15)
            d += timedelta(days=1)
        arr = [days[k] for k in sorted(days)][-280:]   # 보관 상한(약 1년)
        z, oi_chg = finalize(arr)
        # 자동해석용 부가값: 최근일 선물등락·OI변화
        latest = dict(arr[-1]) if arr else {}
        if len(arr) >= 2 and arr[-1].get("fut") and arr[-2].get("fut"):
            latest["fut_chg_pct"] = round((arr[-1]["fut"] / arr[-2]["fut"] - 1) * 100, 2)
        if oi_chg: latest["fut_oi_chg"] = oi_chg[-1]
        out[code] = {"name": name, "days": arr, "z": z, "latest": latest}
        print(f"[stock_deriv] {name}: +{got}일 (총 {len(arr)}일) z={z}")

    os.makedirs(DB, exist_ok=True)
    json.dump({"asof": datetime.now().strftime("%Y-%m-%d %H:%M"), "src": "금융위 FSC 파생상품시세정보(T+1 확정치)",
               "stocks": out}, open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"[stock_deriv] ✅ 저장 → {OUT}")


if __name__ == "__main__":
    main()
