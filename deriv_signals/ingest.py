# -*- coding: utf-8 -*-
"""
데이터 수집 (전부 무료 소스, API 키 불필요)
  - 현물/선물/VIX : yfinance
  - 옵션 PCR/스큐/델타 : yfinance 옵션체인 스냅샷(당일 기준, 매일 누적)
  - 선물 포지셔닝(COT) : CFTC TFF 리포트 직접 다운로드(cot_reports)
"""
import math
import warnings
from datetime import datetime
from statistics import NormalDist

import numpy as np
import pandas as pd
import yfinance as yf

from config import INSTRUMENTS, RISK_FREE, OPT_TARGET_DTE
from db import log

warnings.filterwarnings("ignore")
_N = NormalDist().cdf


def _f(x):
    try:
        return None if pd.isna(x) else float(x)
    except Exception:
        return None


# ── 가격(현물/선물/VIX) ─────────────────────────────
def _daum_close(ticker, start, end):
    # (req 2026-07-05) Yahoo 가 한국상장 ETF(.KS/.KQ) 이력을 최신 1점만 주는 문제 → finance.daum.net 일봉 폴백.
    import urllib.request as _u, json as _j
    code = str(ticker).split(".")[0]
    if not (str(ticker).endswith(".KS") or str(ticker).endswith(".KQ")):
        return pd.Series(dtype=float)
    try:
        u = "https://finance.daum.net/api/charts/A%s/days?limit=520&adjusted=true" % code
        rq = _u.Request(u, headers={"Referer": "https://finance.daum.net/quotes/A%s" % code,
                                    "User-Agent": "Mozilla/5.0", "X-Requested-With": "XMLHttpRequest"})
        d = _j.loads(_u.urlopen(rq, timeout=15).read().decode("utf-8", "replace")).get("data", [])
        idx, val = [], []
        for p in d:
            tp = p.get("tradePrice"); dt = str(p.get("date"))[:10]
            if not tp or not dt: continue
            if (start and dt < start) or (end and dt > end): continue
            idx.append(dt); val.append(float(tp))
        return pd.Series(val, index=idx).dropna()
    except Exception:
        return pd.Series(dtype=float)


def _close(ticker, start, end):
    df = yf.download(ticker, start=start, end=end, progress=False, auto_adjust=False)
    c = None
    if df is not None and len(df):
        c = df["Close"]
        if isinstance(c, pd.DataFrame):
            c = c.iloc[:, 0]
        c.index = pd.to_datetime(c.index).strftime("%Y-%m-%d")
        c = c.dropna()
    if (c is None or len(c) < 5) and (str(ticker).endswith(".KS") or str(ticker).endswith(".KQ")):
        d = _daum_close(ticker, start, end)   # (fix) 한국상장 ETF 이력은 Daum 폴백
        if len(d) >= 5: return d
    return c if c is not None else pd.Series(dtype=float)


def ingest_prices(con, start, end):
    vix = _close("^VIX", start, end)
    n = 0
    for inst in INSTRUMENTS:
        spot = _close(inst["spot"], start, end)
        fut = _close(inst["future"], start, end) if inst["future"] else pd.Series(dtype=float)
        for d in spot.index:
            con.execute(
                "INSERT OR REPLACE INTO prices_daily(id,date,spot_close,future_close,vix_close) VALUES(?,?,?,?,?)",
                (inst["id"], d,
                 _f(spot.get(d)),
                 _f(fut.get(d)) if d in fut.index else None,
                 _f(vix.get(d)) if (inst["region"] == "US" and d in vix.index) else None),
            )
            n += 1
    con.commit()
    log(con, "ingest_prices", n)
    return n


# ── COT (CFTC TFF) ─────────────────────────────
def _num(s):
    return pd.to_numeric(s.astype(str).str.replace(",", "", regex=False), errors="coerce")


def ingest_cot(con, years):
    try:
        import cot_reports as cot
    except Exception as e:
        print("  cot_reports 미설치 → 미국 COT 포지셔닝 skip:", repr(e)[:60])
        log(con, "ingest_cot", 0, "cot_reports missing")
        return 0
    import os, tempfile
    _cwd = os.getcwd(); _tmp = tempfile.mkdtemp(prefix="cot_")
    os.chdir(_tmp)                      # COT 임시파일이 사용자 폴더를 어지럽히지 않도록
    frames = []
    for y in years:
        try:
            frames.append(cot.cot_year(y, cot_report_type="traders_in_financial_futures_fut"))
        except Exception as e:
            print(f"  COT {y} skip: {repr(e)[:80]}")
    os.chdir(_cwd)
    if not frames:
        log(con, "ingest_cot", 0, "no data")
        return 0
    df = pd.concat(frames, ignore_index=True)
    namecol = "Market_and_Exchange_Names"
    df["_date"] = pd.to_datetime(df["Report_Date_as_YYYY-MM-DD"], errors="coerce")
    n = 0
    for inst in INSTRUMENTS:
        if not inst["cot"]:
            continue
        sub = df[df[namecol] == inst["cot"]].copy().sort_values("_date")
        if sub.empty:
            continue
        oi = _num(sub["Open_Interest_All"])
        oichg = _num(sub["Change_in_Open_Interest_All"])
        lev = _num(sub["Lev_Money_Positions_Long_All"]) - _num(sub["Lev_Money_Positions_Short_All"])
        amgr = _num(sub["Asset_Mgr_Positions_Long_All"]) - _num(sub["Asset_Mgr_Positions_Short_All"])
        deal = _num(sub["Dealer_Positions_Long_All"]) - _num(sub["Dealer_Positions_Short_All"])
        for i, d in enumerate(sub["_date"]):
            if pd.isna(d):
                continue
            con.execute(
                "INSERT OR REPLACE INTO positioning_weekly(id,report_date,open_interest,oi_change,lev_net,asset_mgr_net,dealer_net) VALUES(?,?,?,?,?,?,?)",
                (inst["id"], d.strftime("%Y-%m-%d"),
                 _f(oi.iloc[i]), _f(oichg.iloc[i]), _f(lev.iloc[i]), _f(amgr.iloc[i]), _f(deal.iloc[i])),
            )
            n += 1
    con.commit()
    log(con, "ingest_cot", n)
    return n


# ── 옵션 스냅샷(PCR/스큐/델타) ─────────────────────────────
def _bs_delta(S, K, T, r, sigma, typ):
    if not (sigma > 0 and T > 0 and S > 0 and K > 0):
        return float("nan")
    d1 = (math.log(S / K) + (r + 0.5 * sigma * sigma) * T) / (sigma * math.sqrt(T))
    return _N(d1) if typ == "c" else _N(d1) - 1.0


def _bs_gamma(S, K, T, r, sigma):
    if not (sigma > 0 and T > 0 and S > 0 and K > 0):
        return float("nan")
    d1 = (math.log(S / K) + (r + 0.5 * sigma * sigma) * T) / (sigma * math.sqrt(T))
    return math.exp(-0.5 * d1 * d1) / (S * sigma * math.sqrt(T) * math.sqrt(2 * math.pi))


def _spot_last(tk):
    try:
        p = tk.fast_info["last_price"]
        if p:
            return float(p)
    except Exception:
        pass
    h = tk.history(period="1d")
    return float(h["Close"].iloc[-1]) if len(h) else float("nan")


def option_metrics(option_ticker):
    tk = yf.Ticker(option_ticker)
    exps = list(tk.options)
    if not exps:
        return None
    today = datetime.utcnow().date()
    best = min(exps, key=lambda e: abs((datetime.strptime(e, "%Y-%m-%d").date() - today).days - OPT_TARGET_DTE))
    dte = (datetime.strptime(best, "%Y-%m-%d").date() - today).days
    T = max(dte, 1) / 365.0
    oc = tk.option_chain(best)
    calls, puts = oc.calls.copy(), oc.puts.copy()
    S = _spot_last(tk)
    for df, typ in [(calls, "c"), (puts, "p")]:
        df["iv"] = pd.to_numeric(df["impliedVolatility"], errors="coerce")
        df["oi"] = pd.to_numeric(df["openInterest"], errors="coerce").fillna(0)
        df["vol"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0)
        df["delta"] = df.apply(lambda r: _bs_delta(S, r["strike"], T, RISK_FREE, r["iv"], typ), axis=1)
        df["gamma"] = df.apply(lambda r: _bs_gamma(S, r["strike"], T, RISK_FREE, r["iv"]), axis=1)

    pcr_oi = puts["oi"].sum() / max(calls["oi"].sum(), 1)
    pcr_vol = puts["vol"].sum() / max(calls["vol"].sum(), 1)
    ci = calls.iloc[(calls["strike"] - S).abs().argmin()]["iv"] if len(calls) else np.nan
    pi = puts.iloc[(puts["strike"] - S).abs().argmin()]["iv"] if len(puts) else np.nan
    iv_atm = np.nanmean([ci, pi])

    pv = puts.dropna(subset=["delta", "iv"])
    cv = calls.dropna(subset=["delta", "iv"])
    skew = np.nan
    if len(pv) and len(cv):
        p25 = pv.iloc[(pv["delta"] + 0.25).abs().argmin()]["iv"]
        c25 = cv.iloc[(cv["delta"] - 0.25).abs().argmin()]["iv"]
        skew = float(p25 - c25)

    num = (puts["oi"] * puts["delta"].abs()).sum()
    den = (calls["oi"] * calls["delta"].clip(lower=0)).sum()
    delta_imb = num / den if den else np.nan

    cg = (calls["gamma"] * calls["oi"]).sum()
    pg = (puts["gamma"] * puts["oi"]).sum()
    gex = (cg - pg) * S * S * 0.01 * 100          # 딜러 롱콜·숏풋 가정, $/1%p

    return dict(expiry=best, dte=int(dte), pcr_oi=float(pcr_oi), pcr_vol=float(pcr_vol),
                iv_atm=_f(iv_atm), iv_skew_25d=_f(skew), delta_imbalance=_f(delta_imb), gex=_f(gex))


def ingest_options(con, asof=None):
    asof = asof or datetime.utcnow().strftime("%Y-%m-%d")
    n = 0
    for inst in INSTRUMENTS:
        if not inst["option"]:
            continue
        try:
            m = option_metrics(inst["option"])
        except Exception as e:
            print(f"  option {inst['id']} skip: {repr(e)[:80]}")
            m = None
        if not m:
            continue
        con.execute(
            "INSERT OR REPLACE INTO options_daily(id,date,expiry_used,dte,pcr_oi,pcr_vol,iv_atm,iv_skew_25d,delta_imbalance,gex) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (inst["id"], asof, m["expiry"], m["dte"], m["pcr_oi"], m["pcr_vol"],
             m["iv_atm"], m["iv_skew_25d"], m["delta_imbalance"], m["gex"]),
        )
        n += 1
    con.commit()
    log(con, "ingest_options", n)
    return n


def ingest_all(con, start, end, years, do_options=True):
    p = ingest_prices(con, start, end)
    c = ingest_cot(con, years)
    o = ingest_options(con) if do_options else 0
    return dict(prices=p, cot=c, options=o)
