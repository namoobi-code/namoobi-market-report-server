#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""stlead.py — 주가지수 선행지표 허브 + 시차 회귀 예측 (2026-08-22 신설 · 포트폴리오 탭).

목적
  relead.py(부동산 중위가 예측)의 검증된 엔진(시차 탐색 → 릿지 회귀 → 워크포워드
  백테스트 → 보정·밴드)을 **주가지수 5종**에 그대로 적용한다. 엔진 함수는 relead 에서
  import 해 재사용한다 — 복사하지 않는다(수정이 한 곳에만 반영되는 사고 방지).

예측 대상 (야후 월봉, range=max — 각 지수의 존재하는 최대 과거까지)
  spx   ^GSPC  S&P500        1927~
  ndx   ^NDX   나스닥100     1985~
  sox   ^SOX   필라델피아반도체 1993~
  ks200 ^KS200 코스피200     1996~ (야후 제공 시작 — 지수 자체는 1990 기준이나 소급 데이터 없음)
  dvy   DVY    배당 ETF      2003~

선행지표 (미국 FRED + 한국 ECOS/OECD — 전부 월축)
  물가: CPI·PPI·PCE / 금리: 연준금리·10Y·2Y·장단기금리차 / 고용: NFP·실업률·신규청구
  실물: GDP·산업생산·소매판매·주택착공·반도체생산(IPG3344S) / 유동성: M2(미)·M2(한)
  심리: VIX·미시간소비심리·달러지수·BAA신용스프레드·CLI(한, ks200만)
  ks200 은 위 미국 핵심지표 + 한국 지표 + S&P500 자체를 지표로 쓴다(미국→한국 전이).

그룹 통합 r
  같은 계열 지표(물가 3종 등)는 개별 r 과 별도로, 구성원의 z-점수 평균(합성지표)을
  만들어 타깃과의 시차·상관을 다시 잰다 — 유사지표가 여럿일 때 계열 전체의 영향력.

예측·백테스트
  타깃 = 마지막 관측 대비 h개월 누적 로그변화율(step_log) · h=1~24.
  백테스트 24시점 워크포워드(그 시점 자료만) → MAPE·방향적중률·보정계수(calib).
  화면 예측선은 calib 를 곱해 그린다(백테스트에서 실현된 만큼만).

비중 제안(참고용 — 투자권유 아님)
  기본 비중(SPYM35·QQQM20·SCHD10·KODEX200 10·SOXX10·현금15)에서 12개월 보정예측
  수익률의 상대 우열만큼 ±5%p 한도로 기울인다. 잔여는 현금.

산출: data/db/stlead.json   cron: 20 5 * * * (미 장 마감 후)
"""
import json, math, sys, time, urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
import relead                                    # 엔진 재사용 (함수 단위)
from relead import (yoy_log, step_log, best_lag, ridge_fit,  # noqa: F401
                    forecast, lags_for, backtest, add_months, num, build_xy)
import nmr_fred

DB = BASE / "data" / "db"
OUT = DB / "stlead.json"
NOW = datetime.now()

# 엔진 파라미터 — 지수 히스토리가 길어(SPX 1,180개월) 부동산 기본값이면 너무 느리다.
relead.HZ = 24
relead.MAXLAG = 24
relead.BT_ORIGINS = 24
relead.TOPK = 6
HZ = 24

TARGETS = {
    # key: (야후심볼, 라벨, ETF 매핑, 기본비중%)  — 기본 0 은 위성자산(예측 우위 시 현금에서 편입)
    "spx":    ("^GSPC",     "S&P500",        "SPYM",       35),
    "ndx":    ("^NDX",      "나스닥100",      "QQQM",       20),
    "sox":    ("^SOX",      "필라델피아반도체", "SOXX",       10),
    # (2026-08-23) ^KS200 은 야후에서 전 구간 빈 응답(실측) → KODEX 200 ETF 로 대체(2002~)
    "ks200":  ("069500.KS", "코스피200(KODEX)", "KODEX 200", 10),
    "dvy":    ("DVY",       "배당(DVY)",      "SCHD/DVY",   10),
    "gold":   ("GC=F",      "금(선물)",       "GLD/KRX금",   0),
    "btc":    ("BTC-USD",   "비트코인",       "현물(거래소)", 0),
    "xle":    ("XLE",       "에너지 섹터",    "XLE",         0),
    "tlt":    ("TLT",       "미 장기국채",    "TLT",         0),
    "shy":    ("SHY",       "미 단기국채",    "SHY",         0),
    "krb_s":  ("153130.KS", "국내 단기채권",  "KODEX 단기채권", 0),
    "krb_m":  ("157450.KS", "국내 단기통안채", "TIGER 단기통안채", 0),
    # (2026-08-23) 분산 확장 — MAGS 는 2023 상장(40개월)이라 엔진 요건 미달 → MGK 로 대체
    "mgk":    ("MGK", "메가캡 성장",    "MGK (Mag7 ~60%)", 0),
    "efa":    ("EFA", "선진국(ex-US)", "EFA",  0),
    "tip":    ("TIP", "물가연동채",     "TIP",  0),
    "eem":    ("EEM", "신흥국",        "EEM",  0),
    "vnq":    ("VNQ", "미국 리츠",     "VNQ",  0),
    "dbc":    ("DBC", "원자재(14종)",   "DBC",  0),
}
CASH_BASE = 15
TILT_ELIG = {"spx", "ndx", "sox", "ks200", "dvy", "gold", "btc", "xle", "tlt",
             "mgk", "efa", "tip", "eem", "vnq", "dbc"}
CASH_LIKE = {"shy", "krb_s", "krb_m"}            # 현금성 — 비중 제안에서 현금군으로 취급

META = {   # key: (label, group, unit, src)
    "cpi":     ("소비자물가 CPI", "물가", "전년비", "FRED CPIAUCSL"),
    "ppi":     ("생산자물가 PPI", "물가", "전년비", "FRED PPIACO"),
    "pce":     ("PCE 물가", "물가", "전년비", "FRED PCEPI"),
    "ffr":     ("연준 기준금리", "금리", "%", "FRED FEDFUNDS"),
    "us10y":   ("미 10년물 금리", "금리", "%", "FRED DGS10"),
    "us2y":    ("미 2년물 금리", "금리", "%", "FRED DGS2"),
    "t10y2y":  ("장단기 금리차(10Y-2Y)", "금리", "%p", "FRED"),
    "payems":  ("비농업고용 NFP", "고용", "전년비", "FRED PAYEMS"),
    "unrate":  ("실업률", "고용", "%", "FRED UNRATE"),
    "claims":  ("신규 실업수당청구", "고용", "전년비", "FRED ICSA 월평균"),
    "gdp":     ("미 명목 GDP", "실물", "전년비", "FRED GDP(분기 계단)"),
    "indpro":  ("산업생산", "실물", "전년비", "FRED INDPRO"),
    "retail":  ("소매판매", "실물", "전년비", "FRED RSAFS"),
    "houst":   ("주택착공", "실물", "전년비", "FRED HOUST"),
    "semi_ip": ("반도체 산업생산", "실물", "전년비", "FRED IPG3344S"),
    "m2":      ("미 통화량 M2", "유동성", "전년비", "FRED M2SL"),
    "m2_kr":   ("한 통화량 M2", "유동성", "전년비", "ECOS"),
    "vix":     ("VIX 변동성", "심리", "지수", "FRED VIXCLS 월평균"),
    "umcsent": ("미시간 소비심리", "심리", "지수", "FRED UMCSENT"),
    "dxy":     ("달러지수(광의)", "심리", "지수", "FRED DTWEXBGS"),
    "baa10y":  ("BAA 신용스프레드", "심리", "%p", "FRED BAA10YM"),
    "cli_kr":  ("경기선행지수 CLI(한)", "심리", "지수", "OECD"),
    "rate_kr": ("한은 기준금리", "금리", "%", "ECOS"),
    "fx":      ("원/달러 환율", "심리", "전년비", "ECOS"),
    "spx_ind": ("S&P500(전이)", "시장", "전년비", "야후"),
    "wti":     ("WTI 유가", "실물", "전년비", "FRED DCOILWTICO 월평균"),
}
# 수준(lvl) 그대로 쓰는 지표 — 나머지는 전년비 로그성장률로 변환
LVL = {"ffr", "us10y", "us2y", "t10y2y", "unrate", "vix", "umcsent", "dxy",
       "baa10y", "cli_kr", "rate_kr"}
GROUPS = ["물가", "금리", "고용", "실물", "유동성", "심리", "시장"]

US_KEYS = ["cpi", "ppi", "pce", "ffr", "us10y", "us2y", "t10y2y", "payems",
           "unrate", "claims", "gdp", "indpro", "retail", "houst", "m2",
           "vix", "umcsent", "dxy", "baa10y"]
KR_KEYS = ["ffr", "us10y", "t10y2y", "vix", "dxy", "m2", "indpro",
           "rate_kr", "m2_kr", "fx", "cli_kr", "spx_ind",
           "baa10y", "claims", "umcsent", "cpi", "unrate"]   # 급락모델·위기전이 지표
KEYS_FOR = {
    "spx":   US_KEYS,
    "ndx":   US_KEYS + ["semi_ip"],
    "sox":   US_KEYS + ["semi_ip"],
    "dvy":   US_KEYS,
    "ks200": KR_KEYS,
    "gold":  US_KEYS + ["wti"],
    "btc":   US_KEYS,
    "xle":   US_KEYS + ["wti"],
    "tlt":   US_KEYS,
    "shy":   US_KEYS,
    "krb_s": KR_KEYS,
    "krb_m": KR_KEYS,
    "mgk":   US_KEYS + ["semi_ip"],
    "efa":   US_KEYS,
    "tip":   US_KEYS,
    "eem":   US_KEYS + ["wti"],
    "vnq":   US_KEYS,
    "dbc":   US_KEYS + ["wti"],
}


def _yahoo_chart(sym, p1, p2, iv):
    u = (f"https://query1.finance.yahoo.com/v8/finance/chart/"
         f"{urllib.request.quote(sym)}?period1={p1}&period2={p2}&interval={iv}")
    for k in range(3):
        try:
            req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
            d = json.loads(urllib.request.urlopen(req, timeout=60).read())
            r = d["chart"]["result"][0]
            return list(zip(r.get("timestamp") or [],
                            r["indicators"]["quote"][0].get("close") or []))
        except Exception as e:
            if k == 2:
                print(f"    ⚠ yahoo {sym} {iv}: {str(e)[:70]}")
                return []
            time.sleep(3)


def yahoo_monthly(sym):
    """야후 → {YYYYMM: 월말 종가}. (2026-08-22 실측) range=max&interval=1mo 는
    장기 구간에서 분기봉으로 강등되고(^GSPC 168캔들), 1985년 이전 구간은 1mo 요청 시
    아예 빈 응답이다. 일봉은 1927년까지 온전히 나온다 → **1985년 이전은 일봉을 받아
    월말 종가로 집계**, 이후는 월봉. 시각은 UTC 로 통일(월말 경계 밀림 방지)."""
    P85 = 473385600                               # 1985-01-01 UTC
    out = {}
    for p1, p2, iv in ((-1357016400, -252460800, "1d"),   # 1927~1962 일봉
                       (-252460800, P85, "1d"),           # 1962~1985 일봉
                       (P85, int(time.time()) + 86400, "1mo")):
        for t, c in _yahoo_chart(sym, p1, p2, iv):
            if c is None:
                continue
            ym = datetime.fromtimestamp(t, tz=timezone.utc).strftime("%Y%m")
            out[ym] = float(c)                    # 뒤 값이 덮음 → 일봉은 월말 종가가 남는다
        time.sleep(0.5)
    return out


def fred_monthly(sid, agg="mean"):
    """FRED 계열 → {YYYYMM: 값}. 일/주별이면 월평균."""
    rows = nmr_fred.fred_series(sid, timeout=25) or []
    acc = {}
    for d, v in rows:
        acc.setdefault(str(d)[:7].replace("-", ""), []).append(v)
    return {k: (sum(v) / len(v) if agg == "mean" else v[-1]) for k, v in acc.items() if v}


def collect_indicators():
    print("[st] 지표 수집")
    f = {}
    FRED = {"cpi": "CPIAUCSL", "ppi": "PPIACO", "pce": "PCEPI", "ffr": "FEDFUNDS",
            "us10y": "DGS10", "us2y": "DGS2", "payems": "PAYEMS", "unrate": "UNRATE",
            "claims": "ICSA", "gdp": "GDP", "indpro": "INDPRO", "retail": "RSAFS",
            "houst": "HOUST", "semi_ip": "IPG3344S", "m2": "M2SL", "vix": "VIXCLS",
            "umcsent": "UMCSENT", "dxy": "DTWEXBGS", "baa10y": "BAA10YM",
            "wti": "DCOILWTICO"}
    for k, sid in FRED.items():
        f[k] = fred_monthly(sid)
        print(f"    {k:8s} {len(f[k])}개월")
        time.sleep(0.3)
    # GDP 분기 → 3개월 계단
    if f.get("gdp"):
        g2 = {}
        for ym, v in sorted(f["gdp"].items()):
            y, m = int(ym[:4]), int(ym[4:])
            for mm in (m, m + 1, m + 2):
                g2[f"{y + (mm - 1) // 12}{(mm - 1) % 12 + 1:02d}"] = v
        f["gdp"] = g2
    # 장단기 금리차
    f["t10y2y"] = {ym: f["us10y"][ym] - f["us2y"][ym]
                   for ym in f.get("us10y", {}) if ym in f.get("us2y", {})}
    # 한국 (relead 수집기 재사용)
    try:
        f["rate_kr"] = relead.ecos("722Y001", "0101000")
        f["m2_kr"] = relead.ecos("161Y006", "BBHA00", s="200310", scale=1e-3)
        f["fx"] = relead.ecos_daily_monthly("731Y001", "0000001")
        f["cli_kr"] = relead.oecd_cli()
    except Exception as e:
        print("    ⚠ KR 지표:", str(e)[:80])
    return f


def to_axis(t, mp):
    return [mp.get(ym) for ym in t]


def transform(key, seq):
    return list(seq) if key in LVL else yoy_log(seq)


def zscore(seq):
    v = [x for x in seq if x is not None]
    if len(v) < 24:
        return [None] * len(seq)
    mu = sum(v) / len(v)
    sd = math.sqrt(sum((x - mu) ** 2 for x in v) / len(v)) or 1.0
    return [None if x is None else (x - mu) / sd for x in seq]


# (2026-08-23) 급락 확률 모델 — 평균 경로 회귀는 원리적으로 꼬리 사건을 못 맞추므로,
# "향후 12개월 내 현재가 대비 -20% 드로다운 발생 여부"를 타깃으로 한 로지스틱을 별도로 둔다.
# 지표는 급락과 연관 큰 것만(VIX·신용스프레드·장단기금리차·실업청구·소비심리·금리·물가·M2·실업률).
CRASH_KEYS = ["vix", "baa10y", "t10y2y", "claims", "umcsent", "ffr", "cpi", "m2", "unrate"]
CRASH_DD = 0.80                                   # -20% 드로다운
CRASH_HZ = 12                                     # 12개월 창


def crash_prob(feat, prices, keys, months=None):
    """순수 파이썬 로지스틱(표준화+GD+L2). 반환: 현재확률·역사기저율·상위20% 신호 적중률
    + 최근 10년 월별 소급 확률(hist — 표본 내 재현이라 참고용, 추세 그래프용)."""
    use = [k for k in CRASH_KEYS if k in keys
           and sum(1 for v in feat[k] if v is not None) >= 120]
    if len(use) < 5:
        return None
    N = len(prices)
    X, y, idxs = [], [], []
    for i in range(N - CRASH_HZ):
        if not prices[i]:
            continue
        fut = [p for p in prices[i + 1:i + 1 + CRASH_HZ] if p]
        if len(fut) < CRASH_HZ:
            continue
        row = []
        ok = True
        for k in use:
            v = feat[k][i]
            if v is None:
                ok = False
                break
            row.append(v)
        if ok:
            X.append(row)
            y.append(1 if min(fut) / prices[i] <= CRASH_DD else 0)
            idxs.append(i)
    if len(X) >= 120 and sum(y) < 5:
        # (2026-08-24) 표본은 충분한데 급락 사례가 5건 미만 = 이 자산은 -20% 급락을
        # 사실상 안 하는 자산(SHY 최대낙폭 -5%·TIP -13%) — '데이터 부족'과 구분해 표시
        return {"na": 1, "ev": sum(y), "n": len(X)}
    if len(X) < 120 or sum(y) < 5:
        return None
    n, p = len(X), len(use)
    mu = [sum(r[j] for r in X) / n for j in range(p)]
    sd = [math.sqrt(sum((r[j] - mu[j]) ** 2 for r in X) / n) or 1.0 for j in range(p)]
    Z = [[(r[j] - mu[j]) / sd[j] for j in range(p)] for r in X]
    w = [0.0] * p
    b = 0.0
    lr, l2 = 0.5, 1e-2
    for _ in range(400):                          # 경사하강 (표본 수백 × 9변수라 즉시 수렴)
        gw = [l2 * w[j] for j in range(p)]
        gb = 0.0
        for i in range(n):
            z = b + sum(w[j] * Z[i][j] for j in range(p))
            e = 1 / (1 + math.exp(-max(-30, min(30, z)))) - y[i]
            for j in range(p):
                gw[j] += e * Z[i][j] / n
            gb += e / n
        w = [w[j] - lr * gw[j] for j in range(p)]
        b -= lr * gb
    def prob(row):
        z = b + sum(w[j] * (row[j] - mu[j]) / sd[j] for j in range(p))
        return 1 / (1 + math.exp(-max(-30, min(30, z))))
    # 상위 20% 신호 구간의 실제 급락 비율(리프트) — 표본 내 검증(참고용)
    ps = sorted(((prob(X[i]), y[i]) for i in range(n)), reverse=True)
    top = ps[:max(1, n // 5)]
    base = sum(y) / n
    top_rate = sum(t[1] for t in top) / len(top)
    # 현재 입력 — 지표별 마지막 관측(발표 지연 3개월 내 이월)
    row_now = []
    for k in use:
        v = None
        for j in range(len(feat[k]) - 1, max(-1, len(feat[k]) - 4), -1):
            if feat[k][j] is not None:
                v = feat[k][j]
                break
        if v is None:
            return None
        row_now.append(v)
    # (2026-08-24) 월별 소급 이력(최근 120개월) — 추세 스파크라인용. 표본 내 재현이라 참고치.
    hist = []
    if months:
        for j in range(max(0, n - 120), n):
            hist.append([str(months[idxs[j]]), round(prob(X[j]) * 100, 1)])
    return {"p": round(prob(row_now) * 100, 1), "base": round(base * 100, 1),
            "top": round(top_rate * 100, 1), "n": n, "ev": sum(y), "hist": hist,
            "beta": {k: round(w[j], 3) for j, k in enumerate(use)}}


def pack_series(mp):
    """{YYYYMM: v} → {"t0": 시작월, "v": [연속 월 배열(빈 달 null)]} — 차트 오버레이용."""
    if not mp:
        return None
    ks = sorted(mp)
    t0, t1 = ks[0], ks[-1]
    out, ym = [], t0
    while ym <= t1:
        v = mp.get(ym)
        out.append(None if v is None else round(v, 4))
        ym = add_months(ym, 1)
    return {"t0": t0, "v": out}


FAST = "--fast" in sys.argv                      # 백테스트 생략, 기존 JSON 의 bt 재사용
OLD_BT = {}


def main():
    if FAST and OUT.exists():
        try:
            for k, v in json.loads(OUT.read_text(encoding="utf-8"))["targets"].items():
                if v.get("bt"):
                    OLD_BT[k] = v["bt"]
            print(f"[st] --fast: 기존 백테스트 {len(OLD_BT)}개 재사용")
        except Exception:
            pass
    ind = collect_indicators()
    targets_out, alloc_in = {}, {}
    for tk, (sym, label, etf, base_w) in TARGETS.items():
        print(f"[st] ── {label} ({sym})")
        try:
            _one(tk, sym, label, etf, base_w, ind, targets_out, alloc_in)
        except Exception as e:                     # 한 자산의 사고가 전체를 죽이지 않게
            print(f"    ⚠ {label} 실패: {type(e).__name__} {str(e)[:80]}")
    _finish(targets_out, alloc_in, ind)


def _san_bt(bt):
    """(2026-08-23) BTC 처럼 고변동 자산은 엔진 내부(비클램프) 예측이 폭주해 백테스트
    오차가 천문학적 수치(4.5e+40%)로 저장됐다 — 표시 통계를 999% 로 캡(신뢰불가 표식)."""
    for b in (bt.get("by_h") or {}).values():
        for f in ("mape", "sd", "naive"):
            if b.get(f) is not None:
                b[f] = round(min(b[f], 999.0), 2)
    if bt.get("mape") is not None:
        bt["mape"] = round(min(bt["mape"], 999.0), 2)
    return bt


def _one(tk, sym, label, etf, base_w, ind, targets_out, alloc_in):
    if True:
        px = yahoo_monthly(sym)
        if len(px) < 120:
            print("    ⚠ 시세 부족 — 건너뜀")
            return
        t = sorted(px)
        prices = [px[ym] for ym in t]
        ytr = yoy_log(prices)
        keys = list(KEYS_FOR[tk])
        feat = {}
        for k in keys:
            src = ind.get(k) or {}
            if k == "spx_ind":
                src = yahoo_monthly("^GSPC")
            feat[k] = transform(k, to_axis(t, src))
        keys = [k for k in keys if sum(1 for v in feat[k] if v is not None) >= 60]
        # ── 개별 r·시차 (전 구간)
        lead = lags_for(feat, ytr, keys)
        # (2026-08-23) 표시용 가중치를 '12개월 예측 기준'으로 — 전구간 최적 r(시차 0 포함)로
        # 가중치를 매기면 동행지표(소매판매 등)가 크게 보여 "예측 기여"로 오해된다(사용자 지적).
        # 지평별(1·3·6·12M) 출전 시차(≥h)에서의 r 을 각각 산출해 표에 보여준다.
        for k in keys:
            for hh in (1, 3, 6, 12, 18, 24):
                Lh, ch = relead.best_lag_ge(feat[k], ytr, hh)
                lead[k][f"lag{hh}"], lead[k][f"r{hh}"] = Lh, round(ch, 3)
        wsum = sum(abs(lead[k]["corr"]) for k in keys) or 1.0
        w12s = sum(abs(lead[k]["r12"]) for k in keys) or 1.0
        for k in keys:
            lead[k]["w"] = round(abs(lead[k]["corr"]) / wsum, 3)
            lead[k]["w12"] = round(abs(lead[k]["r12"]) / w12s, 3)
        # ── 그룹 합성 r — 구성원 z점수 평균 → 시차 재탐색
        groups = []
        for g in GROUPS:
            mem = [k for k in keys if META[k][1] == g]
            if len(mem) < 2:
                continue
            zs = [zscore(feat[k]) for k in mem]
            comp = [None] * len(t)
            for i in range(len(t)):
                vv = [z[i] for z in zs if z[i] is not None]
                if len(vv) >= max(2, len(mem) // 2):
                    comp[i] = sum(vv) / len(vv)
            L, c, n = best_lag(comp, ytr)
            if n:
                groups.append({"name": g, "members": mem,
                               "lag": L, "corr": round(c, 3), "n": n})
        # ── 예측 + 백테스트
        t_last = len(t) - 1
        fc = forecast(feat, ytr, prices, keys, t_last, horizons=HZ)
        # (2026-08-23) 지표별 기여도 분해 — 화면의 '가중치 조절' 기능용.
        #   표준화 릿지에서 g = ym + Σ β_j·z_j 이므로, fc 가 돌려준 β·시차로 X 를
        #   다시 만들어 mu/sd/ym 만 산출하면 재적합 없이 기여도 c_j = β_j·z_j 를 얻는다.
        #   클라이언트는 g' = calib×(ym + Σ m_j·c_j) 로 배수 m_j 를 곱해 정확히 재계산.
        for h, r in fc.items():
            try:
                use = list(r["betas"].keys())
                lagsd = {k: {"lag": r["lags"][k], "corr": r["corrs"][k]} for k in use}
                X, Y, _ = build_xy(feat, step_log(prices, h), h, lagsd, use, force=use)
                if not X:
                    continue
                n, p = len(X), len(use)
                mu = [sum(row[j] for row in X) / n for j in range(p)]
                sd = [math.sqrt(sum((row[j] - mu[j]) ** 2 for row in X) / n) or 1.0
                      for j in range(p)]
                ym = sum(Y) / n
                rowv = [feat[k][t_last - (lagsd[k]["lag"] - h)] for k in use]
                r["_ym"] = ym
                r["_cont"] = {k: round(r["betas"][k] * (rowv[j] - mu[j]) / sd[j], 5)
                              for j, k in enumerate(use)}
            except Exception:
                pass
        bt = OLD_BT.get(tk) if FAST and OLD_BT.get(tk) else _san_bt(backtest(feat, ytr, prices, keys))
        # 보정 적용 경로 (relead 방식: calib 곱)
        ext = [add_months(t[-1], i + 1) for i in range(HZ)]
        N2 = len(t) + HZ
        fut = {"price": [None] * N2, "lo": [None] * N2, "hi": [None] * N2}
        fut["price"][t_last] = prices[t_last]     # 실측 끝점과 이어 그리기
        pred = {}
        for h, r in fc.items():
            b = bt["by_h"].get(h) or {}
            calib = b.get("calib", 1.0) or 0.0
            # 기여도 분해가 있으면 raw = ym + Σcont 로 일관 계산(가중치 조절과 기준 일치)
            raw = (r["_ym"] + sum(r["_cont"].values())) if "_cont" in r else r["growth"]
            # (2026-08-23) BTC 같은 고변동 자산은 보정 전 성장률·백테스트 sd 가 폭주해
            # exp 오버플로가 났다(실측) → 로그성장 ±1.2(≈-70%~+230%)·sd 100% 로 클램프
            g = max(-1.2, min(1.2, raw * calib))
            p = prices[t_last] * math.exp(g)
            sd = min(1.0, (b.get("sd") or 5.0) / 100)
            j = t_last + h
            fut["price"][j] = round(p, 2)
            fut["lo"][j] = round(p * math.exp(-1.28 * sd), 2)
            fut["hi"][j] = round(p * math.exp(1.28 * sd), 2)
            pred[h] = {"g": round(g, 4), "price": round(p, 2)}
            if "_cont" in r:                       # 가중치 조절·시나리오용
                # g' = clamp(calib × (base + Σ m_k·(cont_k + s_k·β_k)))
                #   m_k=가중치 배수, s_k=시나리오(지표 ±1σ 가정: +1 오름/-1 내림/0 기본)
                pred[h]["base"] = round(r["_ym"], 5)
                pred[h]["cont"] = r["_cont"]
                pred[h]["beta"] = {k: r["betas"][k] for k in r["_cont"]}
                pred[h]["calib"] = round(calib, 3)
                pred[h]["bsd"] = round(sd, 4)
        crash = None
        try:
            crash = crash_prob(feat, prices, keys, months=t)
        except Exception as e:
            print(f"    ⚠ 급락모델: {str(e)[:60]}")
        targets_out[tk] = {
            "label": label, "sym": sym, "etf": etf, "base": base_w,
            "t": t + ext, "past": t_last,
            "hist": [round(v, 2) for v in prices] + [None] * HZ,
            "fut": fut, "lead": lead, "groups": groups, "bt": bt, "pred": pred,
            "crash": crash,
        }
        alloc_in[tk] = pred.get(12, {}).get("g", 0.0)
        print(f"    {t[0]}~{t[-1]} {len(t)}개월 · 지표 {len(keys)} · "
              f"12M {math.exp(alloc_in[tk] or 0) * 100 - 100:+.1f}% · "
              f"MAPE {bt.get('mape')}% · 방향 {bt.get('hit')}%")


CRASH_HIST = DB / "stlead_crash_hist.json"


def _crash_hist(targets_out):
    """(2026-08-24) 급락확률 일별 적재 — 매일 크론이 돌 때 {날짜: {지수: p}} 로 쌓고
    (같은 날 재실행은 덮어씀·최근 400일 보관), 화면용으로 지수별 시계열로 변환해 준다."""
    try:
        h = json.loads(CRASH_HIST.read_text(encoding="utf-8")) if CRASH_HIST.exists() else {}
    except Exception:
        h = {}
    today = NOW.strftime("%Y-%m-%d")
    h[today] = {tk: t["crash"]["p"] for tk, t in targets_out.items()
                if t.get("crash") and "p" in t["crash"]}
    for k in sorted(h)[:-400]:
        del h[k]
    CRASH_HIST.write_text(json.dumps(h), encoding="utf-8")
    out = {}
    for d2 in sorted(h):
        for tk, p in h[d2].items():
            out.setdefault(tk, []).append([d2, p])
    return out


def _finish(targets_out, alloc_in, ind):
    # ── 비중 제안 — 12개월 보정예측의 상대 우열로 코어 ±5%p · 위성 0~+3%p (현금에서)
    alloc = []
    core = {k: g for k, g in alloc_in.items() if k in TILT_ELIG and k in targets_out}
    if core:
        avg = sum(core.values()) / len(core)
        tot = 0
        for tk, (sym, label, etf, base_w) in TARGETS.items():
            if tk not in targets_out:
                continue
            g12 = alloc_in.get(tk, 0.0)
            g24p = targets_out[tk]["pred"].get(24, {}).get("g")
            row = {"key": tk, "asset": label, "etf": etf, "base": base_w,
                   "g12": round(math.exp(g12) * 100 - 100, 1),
                   "g24": round(math.exp(g24p) * 100 - 100, 1) if g24p is not None else None}
            if tk in CASH_LIKE:                    # 현금성 — 예측만 표시, 비중은 현금군
                row["sug"] = None
            else:
                cap = 5 if base_w > 0 else 3       # 위성(기본0)은 +3%p 까지만
                tilt = max(-5 if base_w > 0 else 0,
                           min(cap, round((g12 - avg) * 40)))
                row["sug"] = max(0, base_w + tilt)
                tot += row["sug"]
            alloc.append(row)
        alloc.append({"key": "cash", "asset": "현금·단기채 (SHY·KODEX단기채 등)",
                      "etf": "파킹/머니마켓", "base": CASH_BASE, "g12": None,
                      "g24": None, "sug": max(0, 100 - tot)})
    OUT.write_text(json.dumps({
        "asof": NOW.strftime("%Y-%m-%d %H:%M"),
        "src": "야후 월봉 · FRED · 한국은행 ECOS · OECD — 매일 05:20 자동 갱신",
        "meta": {k: {"label": v[0], "group": v[1], "unit": v[2], "src": v[3]}
                 for k, v in META.items()},
        "series": {k: pack_series(v) for k, v in ind.items() if v},
        "crash_hist": _crash_hist(targets_out),
        "targets": targets_out, "alloc": alloc,
        "note": ("예측은 선행지표 시차 릿지회귀(백테스트 보정) 산출물로 참고용이며 "
                 "투자권유가 아님. 비중 제안 = 기본비중 ± 12개월 상대예측 5%p 한도.")},
        ensure_ascii=False), encoding="utf-8")
    print(f"[st] ✅ {len(targets_out)}개 지수 → {OUT} ({OUT.stat().st_size // 1024}KB)")


if __name__ == "__main__":
    main()
