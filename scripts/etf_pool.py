#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# etf_pool.py — ETF 스크리너용 전종목 풀. (2026-07-26 신설)
#   KR(≈1,150): 네이버 etfItemList(시세·AUM·거래대금·NAV·탭코드, euc-kr)
#               + integration.etfKeyIndicator(총보수·괴리율·분배율TTM·1m/3m/1y 수익률·운용사)
#               + 일봉 chart(400d) → r6m·vol20·200일선·고점比 (+r1y 폴백)
#               + krxbase LIST_DD → 상장연도
#   US(≈5,500): nasdaqtraded.txt(ETF=Y) 유니버스
#               + Yahoo v7 quotes 배치(50심볼) → AUM(netAssets)·총보수(netExpenseRatio)·분배율·52주 필드
#               + spark 6mo 배치(20심볼) → r1m/r3m/r6m·vol20
#   저장: save_db('etf_pool') — /api/db/etf_pool 로 서빙. cron: screener_pool 직후 실행 권장.
import os, sys, json, time, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from datetime import date, datetime, timedelta
import urllib.request, urllib.parse
import ta_screen as T

UA = {"User-Agent": "Mozilla/5.0"}
TAB = {1: "국내지수", 2: "업종·테마", 3: "파생", 4: "해외주식", 5: "원자재", 6: "채권", 7: "기타"}
LEV_RE = re.compile(r"레버리지|인버스|(?<![A-Za-z])[23]X|X[23](?![A-Za-z])|Ultra|Bull|Bear|Inverse|-1x|2x|3x", re.I)


def _series_stats(cl):
    """일봉 종가열 → 기간수익률·변동성·200일선·52주 고점比."""
    o = {}
    n = len(cl)
    for lbl, dd in (("r1m", 21), ("r3m", 63), ("r6m", 126), ("r1y", 250)):
        if n > dd and cl[-dd-1]:
            o[lbl] = round(cl[-1]/cl[-dd-1]-1, 4)
    if n >= 21:
        rets = [cl[i]/cl[i-1]-1 for i in range(n-20, n) if cl[i-1]]
        if len(rets) >= 10:
            mu = sum(rets)/len(rets)
            o["vol20"] = round((sum((x-mu)**2 for x in rets)/len(rets))**0.5*100, 2)
    if n >= 100:
        o["v200"] = round(cl[-1]/(sum(cl[-200:])/min(200, n))-1, 4)
    hi = max(cl[-250:]) if n else None
    if hi:
        o["hi"] = round(cl[-1]/hi-1, 4)
    return o


def kr_collect():
    raw = urllib.request.urlopen(urllib.request.Request(
        "https://finance.naver.com/api/sise/etfItemList.nhn", headers=UA), timeout=15).read()
    items = json.loads(raw.decode("euc-kr", "ignore"))["result"]["etfItemList"]
    # 상장일: krxbase(주식용 캐시 재사용 — ETF 도 base info 에 포함)
    base = {}
    try:
        d0s, _ = T.krx_day_back(date.today(), "stk")
        for mkt in ("stk", "ksq"):
            f = f"{T.CACHE}/krxbase_{mkt}_{d0s}.json"
            if os.path.exists(f):
                for b in json.load(open(f)):
                    base[b.get("ISU_SRT_CD")] = b
    except Exception:
        pass
    rows = []
    for it in items:
        c = it.get("itemcode")
        if not c:
            continue
        nm = it.get("itemname") or ""
        yr = None
        b = base.get(c)
        if b:
            try:
                yr = int(str(b.get("LIST_DD", ""))[:4])
            except Exception:
                pass
        rows.append({"c": c, "n": nm, "px": it.get("nowVal"), "chg": it.get("changeRate"),
                     "cap": (it.get("marketSum") or 0)*1e8,       # 억원 → 원
                     "tv": (it.get("amonut") or 0)*1e6,           # 백만원 → 원
                     "nav": it.get("nav"), "asset": TAB.get(it.get("etfTabCode"), "기타"),
                     "lev": bool(it.get("etfTabCode") == 3 or LEV_RE.search(nm)),
                     "md": ("월배당" in nm) or ("월분배" in nm), "yr": yr})

    def enrich(r):
        try:  # 핵심 지표 (총보수·괴리율·분배율·수익률)
            j = T.jget(f"https://m.stock.naver.com/api/stock/{r['c']}/integration", timeout=10)
            k = j.get("etfKeyIndicator") or {}
            r["fee"] = T.num(k.get("totalFee"))
            dv = T.num(k.get("deviationRate"))
            if dv is not None:
                r["dev"] = -dv if k.get("deviationSign") == "-" else dv   # +=고평가(시장가>NAV)
            r["divy"] = T.num(k.get("dividendYieldTtm"))
            r["issuer"] = k.get("issuerName")
            for a, b2 in (("r1m", "returnRate1m"), ("r3m", "returnRate3m"), ("r1y", "returnRate1y")):
                v = T.num(k.get(b2))
                if v is not None:
                    r[a] = round(v/100, 4)
        except Exception:
            pass
        try:  # 일봉 → r6m·vol20·v200·고점比 (+수익률 폴백)
            S = (date.today()-timedelta(days=420)).strftime("%Y%m%d")
            E = date.today().strftime("%Y%m%d")
            ch = T.jget(f"https://api.stock.naver.com/chart/domestic/item/{r['c']}/day?startDateTime={S}&endDateTime={E}", timeout=12)
            cl = [x["closePrice"] for x in ch if x.get("closePrice")]
            if len(cl) >= 30:
                st = _series_stats(cl)
                for k2, v in st.items():
                    r.setdefault(k2, v)
        except Exception:
            pass
        return r
    T.pmap(enrich, rows, workers=16)
    ok = sum(1 for r in rows if r.get("fee") is not None)
    print(f"[etf] KR {len(rows)}종 · 지표 {ok}종")
    return rows


def us_collect():
    txt = urllib.request.urlopen(urllib.request.Request(
        "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqtraded.txt", headers=UA), timeout=25).read().decode("utf-8", "ignore")
    lines = [l.split("|") for l in txt.splitlines()[1:] if "|" in l]
    syms = [l[1] for l in lines if len(l) > 7 and l[5] == "Y" and l[7] == "N" and re.fullmatch(r"[A-Z]{1,5}", l[1] or "")]
    names = {l[1]: l[2] for l in lines if len(l) > 2}
    op, crumb = T.yahoo_opener()
    rows = []

    def qbatch(chunk):
        try:
            u = ("https://query1.finance.yahoo.com/v7/finance/quote?symbols=%s&crumb=%s"
                 % (urllib.parse.quote(",".join(chunk)), urllib.parse.quote(crumb)))
            return (T.jget(u, opener=op, timeout=20).get("quoteResponse", {}) or {}).get("result", []) or []
        except Exception:
            return []
    chunks = [syms[i:i+50] for i in range(0, len(syms), 50)]
    for res in T.pmap(qbatch, chunks, workers=6):
        for q in res:
            if q.get("quoteType") != "ETF":
                continue
            px = q.get("regularMarketPrice")
            if not px:
                continue
            v3 = q.get("averageDailyVolume3Month")
            nm = (q.get("longName") or q.get("shortName") or names.get(q.get("symbol"), ""))[:48]
            yr = None
            try:
                ft = q.get("firstTradeDateMilliseconds")
                if ft:
                    yr = datetime.utcfromtimestamp(ft/1000).year
            except Exception:
                pass
            rows.append({"c": q["symbol"], "n": nm, "px": px, "chg": q.get("regularMarketChangePercent"),
                         "cap": q.get("netAssets"), "tv": round(v3*px) if v3 else None,
                         "fee": q.get("netExpenseRatio"), "divy": q.get("dividendYield"),
                         "r1y": (q.get("fiftyTwoWeekChangePercent")/100 if q.get("fiftyTwoWeekChangePercent") is not None else None),
                         "hi": (q.get("fiftyTwoWeekHighChangePercent")),
                         "v200": q.get("twoHundredDayAverageChangePercent"),
                         "exch": q.get("fullExchangeName"), "yr": yr,
                         "lev": bool(LEV_RE.search(nm))})
    # spark 6mo → r1m/r3m/r6m·vol20
    codes = [r["c"] for r in rows]
    by = {r["c"]: r for r in rows}

    def sbatch(chunk):
        try:
            u = ("https://query1.finance.yahoo.com/v7/finance/spark?symbols=%s&range=6mo&interval=1d"
                 % urllib.parse.quote(",".join(chunk)))
            j = T.jget(u, opener=op, timeout=15)
            out = {}
            for r0 in (j.get("spark", {}) or {}).get("result") or []:
                resp = (r0.get("response") or [{}])[0]
                cl = (((resp.get("indicators", {}) or {}).get("quote") or [{}])[0].get("close")) or []
                cl = [x for x in cl if x is not None]
                if len(cl) >= 30:
                    out[r0.get("symbol")] = cl
            return out
        except Exception:
            return {}
    ok2 = 0
    for res in T.pmap(sbatch, [codes[i:i+20] for i in range(0, len(codes), 20)], workers=6):
        for sym, cl in res.items():
            r = by.get(sym)
            if not r:
                continue
            st = _series_stats(cl)
            for k, v in st.items():
                if k in ("r1m", "r3m", "r6m", "vol20"):
                    r.setdefault(k, v)
            ok2 += 1
    print(f"[etf] US {len(rows)}종 · spark {ok2}종")
    return rows


def build():
    kr = kr_collect()
    us = us_collect()
    out = {"asof": T.now_kst(),
           "kr": sorted(kr, key=lambda r: -(r.get("cap") or 0)),
           "us": sorted(us, key=lambda r: -(r.get("cap") or 0))}
    T.save_db("etf_pool", out)
    print(f"etf_pool: KR {len(kr)} · US {len(us)}")
    return out


if __name__ == "__main__":
    build()
