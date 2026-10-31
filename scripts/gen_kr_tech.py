#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gen_kr_tech.py — KOSPI·KOSDAQ 1년 일봉 기술 차트(캔들+MA+볼린저/거래량/RSI/누적순매수/프로그램) 서버 일간 생성 (2026-10-31 신설)

왜: 홈피 3.2.1(AI Daily)·🌐 Market 탭의 KOSPI/KOSDAQ 상세가 쓰는 charts/kospi_tech.png 는 리포트 회차가 만들어 sync_server 가 올리던 그림인데,
    v3.73(7/21) WORK 폴더 타임스탬프화 뒤 sync 경로가 어긋나 8/14 에 멈췄다(두 달 반 전 캔들이 '최신'으로 표시). 리포트에 묶지 않고
    서버가 매일 장 마감 뒤 직접 그린다 — 리포트 gen_kr_candle.py 와 같은 소스·같은 패널이라 보고서=홈피 동일.
소스: 네이버 m.stock.naver.com/api/index/{KOSPI|KOSDAQ}/price (OHLC, 60일×5페이지) + 다음 finance.daum.net market_index/days
     (거래량·외국인/기관/개인 순매수, 250일) + data/db/program_trading.json(KIS 프로그램 차익·비차익).
산출: data/charts/kospi_tech.png · kosdaq_tech.png · data/db/kr_tech.json {asof, kospi:{date,close,chg_pct,frgn,inst,indi,vol}, kosdaq:{…}}
cron: 20 16 * * 1-5 · 45 18 * * 1-5 (program_trading 16:15/18:40 뒤)
"""
import json, os, sys, time, urllib.request
from datetime import datetime
from pathlib import Path

import numpy as np, pandas as pd, matplotlib
matplotlib.use("Agg")
import matplotlib.font_manager as fm, matplotlib.pyplot as plt
from matplotlib.lines import Line2D

BASE = Path(__file__).resolve().parent.parent
CH = BASE / "data" / "charts"; CH.mkdir(parents=True, exist_ok=True)
OUTJ = BASE / "data" / "db" / "kr_tech.json"
_f = BASE / "scripts" / "fonts" / "nmr_kr.ttf"
if _f.exists():
    fm.fontManager.addfont(str(_f)); matplotlib.rcParams["font.family"] = "NanumBarunGothic"
matplotlib.rcParams["axes.unicode_minus"] = False
UA = {"User-Agent": "Mozilla/5.0"}


def get(u, ref):
    h = dict(UA); h["Referer"] = ref
    return urllib.request.urlopen(urllib.request.Request(u, headers=h), timeout=20).read().decode("utf-8")


def naver_ohlc(idx):
    """{YYYY-MM-DD: [o,h,l,c]} — pageSize 60 상한, 5페이지 ≈ 300거래일"""
    out = {}
    f = lambda v: float(str(v).replace(",", "")) if v not in (None, "") else None
    for pg in range(1, 6):
        j = json.loads(get(f"https://m.stock.naver.com/api/index/{idx}/price?pageSize=60&page={pg}", "https://m.stock.naver.com/"))
        if not j:
            break
        for x in j:
            d = str(x.get("localTradedAt", ""))[:10]
            o, h, l, c = f(x.get("openPrice")), f(x.get("highPrice")), f(x.get("lowPrice")), f(x.get("closePrice"))
            if d and None not in (o, h, l, c):
                out[d] = [o, h, l, c]
        time.sleep(0.2)
    return out


def daum_days(mkt):
    """[[date, close, vol(천주), 외국인(억), 기관(억), 개인(억)], …] 오름차순 — 250거래일"""
    j = json.loads(get(f"https://finance.daum.net/api/market_index/days?page=1&perPage=250&market={mkt}&pagination=true",
                       "https://finance.daum.net/domestic"))
    rows = []
    for d in j["data"]:
        rows.append([d["date"][:10], d["tradePrice"], int(d["accTradeVolume"]),
                     round(d["foreignStraightPurchasePrice"] / 1e8), round(d["institutionStraightPurchasePrice"] / 1e8),
                     round(d["individualStraightPurchasePrice"] / 1e8)])
    rows.reverse()
    return rows


def rsi(c, n=14):
    d = c.diff(); up = d.clip(lower=0); dn = -d.clip(upper=0)
    return 100 - 100 / (1 + up.ewm(alpha=1 / n, adjust=False).mean() / dn.ewm(alpha=1 / n, adjust=False).mean().replace(0, np.nan))


def build_df(oh, dm):
    """다음 일자 기준으로 네이버 OHLC 결합(네이버 없는 날은 종가 단봉) — 리포트 fetch_kr.build_ohlcv 와 동일 규칙"""
    rows, flows = [], []
    for d, close, vol, F, I, P in dm:
        if d in oh:
            o, h, l, c = oh[d]; rows.append([d, o, h, l, c, vol])
        else:
            rows.append([d, close, close, close, close, vol])
        flows.append([d, F, I, P])
    df = pd.DataFrame(rows, columns=["Date", "Open", "High", "Low", "Close", "Volume"])
    df["Date"] = pd.to_datetime(df["Date"]); df = df.set_index("Date").sort_index()
    df = df[(df[["Open", "High", "Low", "Close"]] > 0).all(axis=1) & (df["High"] >= df["Low"])]
    return df, flows


def candle(df, flows, out, title, prg=None):
    import mplfinance as mpf
    mid = df["Close"].rolling(20).mean(); std = df["Close"].rolling(20).std()
    bbu = mid + 2 * std; bbd = mid - 2 * std; r = rsi(df["Close"])
    fdf = pd.DataFrame(flows, columns=["Date", "F", "I", "P"]); fdf["Date"] = pd.to_datetime(fdf["Date"])
    fdf = fdf.drop_duplicates("Date").set_index("Date").sort_index().reindex(df.index).fillna(0.0)
    cF = fdf["F"].cumsum() / 1e4; cI = fdf["I"].cumsum() / 1e4; cP = fdf["P"].cumsum() / 1e4
    mc = mpf.make_marketcolors(up="#e11d48", down="#2563eb", edge="inherit", wick="inherit", volume="#9ca3af")
    style = mpf.make_mpf_style(marketcolors=mc, gridstyle=":", gridcolor="#e5e7eb", facecolor="white",
                               rc={"font.size": 8, "font.family": matplotlib.rcParams["font.family"], "axes.unicode_minus": False})
    # secondary_y=False 강제 — 리포트 gen_kr_candle.py 2026-08-30 수정과 동일(트윈축 자동 분리로 스케일 오독 방지)
    ap = [mpf.make_addplot(bbu, color="#3b82f6", width=0.7, secondary_y=False), mpf.make_addplot(bbd, color="#10b981", width=0.7, secondary_y=False),
          mpf.make_addplot(r, panel=2, color="#d97706", width=0.9, ylabel="RSI", secondary_y=False),
          mpf.make_addplot(pd.Series(70.0, index=df.index), panel=2, color="#cbd5e1", width=0.5, secondary_y=False),
          mpf.make_addplot(pd.Series(30.0, index=df.index), panel=2, color="#cbd5e1", width=0.5, secondary_y=False),
          mpf.make_addplot(cF, panel=3, color="#dc2626", width=1.1, ylabel="누적순매수(조)", secondary_y=False),
          mpf.make_addplot(cI, panel=3, color="#2563eb", width=1.1, secondary_y=False),
          mpf.make_addplot(cP, panel=3, color="#059669", width=1.1, secondary_y=False)]
    pr = (6, 1.2, 1.4, 2.0); hasprg = False
    if prg and prg.get("t"):
        pt = pd.to_datetime(pd.Series(prg["t"]), format="%Y%m%d", errors="coerce")
        pa = pd.Series(pd.to_numeric(pd.Series(prg["arb"]), errors="coerce").values, index=pt)
        pn = pd.Series(pd.to_numeric(pd.Series(prg["nonarb"]), errors="coerce").values, index=pt)
        pa = pa[~pa.index.duplicated()].reindex(df.index); pn = pn[~pn.index.duplicated()].reindex(df.index)
        if pa.notna().sum() >= 10:
            ap += [mpf.make_addplot(pa, panel=4, color="#e08e3c", width=0.9, ylabel="프로그램(억)", secondary_y=False),
                   mpf.make_addplot(pn, panel=4, color="#1f6feb", width=0.9, secondary_y=False),
                   mpf.make_addplot(pd.Series(0.0, index=df.index), panel=4, color="#cbd5e1", width=0.5, secondary_y=False)]
            pr = (6, 1.2, 1.4, 2.0, 1.8); hasprg = True
    fig, axes = mpf.plot(df, type="candle", style=style, mav=(5, 20, 60, 120), volume=True, addplot=ap,
                         panel_ratios=pr, figratio=(15, 11 if hasprg else 10), figscale=1.15, returnfig=True,
                         datetime_format="%y/%m", xrotation=0, tight_layout=True, title=dict(title=title, fontsize=11))
    axes[6].legend(handles=[Line2D([0], [0], color="#dc2626", lw=1.4, label="외국인"), Line2D([0], [0], color="#2563eb", lw=1.4, label="기관"),
                            Line2D([0], [0], color="#059669", lw=1.4, label="개인")], loc="upper left", fontsize=6.5, frameon=False, ncol=3)
    if hasprg:
        axes[8].legend(handles=[Line2D([0], [0], color="#e08e3c", lw=1.4, label="차익 순매수"), Line2D([0], [0], color="#1f6feb", lw=1.4, label="비차익 순매수")],
                       loc="upper left", fontsize=6.5, frameon=False, ncol=2)
    fig.savefig(out, dpi=150, bbox_inches="tight"); plt.close(fig)


def main():
    prg = {}
    try:
        prg = json.loads((BASE / "data" / "db" / "program_trading.json").read_text(encoding="utf-8"))
    except Exception:
        pass
    meta = {"asof": datetime.now().strftime("%Y-%m-%d %H:%M"), "src": "네이버(OHLC)·다음(거래량·투자자 순매수 억원)·KIS(프로그램) · 1년 일봉"}
    for name, nidx, dmk in (("kospi", "KOSPI", "KOSPI"), ("kosdaq", "KOSDAQ", "KOSDAQ")):
        try:
            oh = naver_ohlc(nidx); dm = daum_days(dmk)
            df, flows = build_df(oh, dm)
            if len(df) < 30:
                print(f"  ⚠ {name} 유효행 부족 {len(df)}", flush=True); continue
            title = f"{nidx} 1년 일봉 — 캔들+이동평균(5/20/60/120)+볼린저 / 거래량 / RSI / 누적순매수 / 프로그램"
            tmp = CH / f"{name}_tech.tmp.png"
            candle(df, flows, str(tmp), title, prg.get(name))
            os.replace(tmp, CH / f"{name}_tech.png")
            last = dm[-1]; prev = dm[-2][1] if len(dm) > 1 else None
            meta[name] = {"date": last[0], "close": last[1], "chg_pct": (round((last[1] / prev - 1) * 100, 2) if prev else None),
                          "frgn": last[3], "inst": last[4], "indi": last[5], "vol": last[2], "rows": len(df),
                          "rsi": round(float(rsi(df["Close"]).iloc[-1]), 1)}
            print(f"  {name}: {len(df)}행 · {last[0]} 종가 {last[1]:,} 외인 {last[3]:+,}억 기관 {last[4]:+,}억 개인 {last[5]:+,}억", flush=True)
        except Exception as e:
            print(f"  ⚠ {name} 실패: {repr(e)[:160]}", flush=True)
    OUTJ.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    print(f"[krtech] ✅ → {CH} · {OUTJ}", flush=True)


if __name__ == "__main__":
    main()
