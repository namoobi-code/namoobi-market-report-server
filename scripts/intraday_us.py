#!/usr/bin/env python3
# intraday_us.py — 미국 장중 전종목 지표 5분 증분 갱신 (한국 밤 시간대).
# 소스: Yahoo v7 벌크 quote(150심볼/호출 ≈ 35회) — 가격·등락·시총·거래량·이평50/200·52주 지표를 매회 신선하게 제공.
# 상태(ta_state_us: 전 세션 종가 기준 RSI/MACD/볼린저/20일선)를 당일가로 O(1) 갱신.
# 거래량배수 = (당일 누적거래량 ÷ 세션 경과비율) ÷ 3개월 평균 — 시간 보정으로 장 초반 급등 포착.
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from datetime import datetime
from zoneinfo import ZoneInfo
import urllib.parse as _up
import ta_screen as T

ET = ZoneInfo("America/New_York")
FIELDS = ",".join([
    "regularMarketPrice","regularMarketChangePercent","marketCap","regularMarketVolume",
    "averageDailyVolume3Month","fiftyDayAverageChangePercent","twoHundredDayAverageChangePercent",
    "fiftyDayAverage","twoHundredDayAverage",
    "fiftyTwoWeekChangePercent","fiftyTwoWeekHighChangePercent"])

def in_session(now_et):
    if now_et.weekday() >= 5:
        return False
    hm = now_et.hour*60 + now_et.minute
    return 9*60+28 <= hm <= 16*60+10          # 정규장 09:30~16:00 ET

def bulk_quotes(codes, op, crumb):
    out = {}
    chunks = [codes[i:i+150] for i in range(0, len(codes), 150)]
    def one(ch):
        try:
            u = ("https://query2.finance.yahoo.com/v7/finance/quote?symbols=%s&fields=%s&crumb=%s"
                 % (_up.quote(",".join(ch)), FIELDS, _up.quote(crumb)))
            j = T.jget(u, opener=op, timeout=15)
            return (j.get("quoteResponse", {}) or {}).get("result") or []
        except Exception:
            return []
    for res in T.pmap(one, chunks, workers=4):
        for q in res:
            if q.get("symbol"):
                out[q["symbol"]] = q
    return out

def main(force=False):
    now = datetime.now(ET)
    if not force and not in_session(now):
        print("미국 장외 — skip"); return
    # (2026-07-20) cron 은 매분 실행하되 US 는 3분마다만 — Yahoo 벌크 35콜/회 부담 완화(무료서버)
    if not force and now.minute % 3 != 0:
        print("US 3분 주기 대기 — skip"); return
    pool = T.load_db("screener_pool") or {}
    stdb = (T.load_db("ta_state_us") or {}).get("st") or {}
    us = pool.get("us") or []
    if not us:
        print("풀 없음 — skip"); return
    op, crumb = T.yahoo_opener()
    Q = bulk_quotes([r["c"] for r in us], op, crumb)
    if len(Q) < 1000:
        print(f"벌크 quote 부족({len(Q)}) — skip"); return
    hm = now.hour*60 + now.minute
    open_m = 9*60+30
    frac = 1.0 if hm >= 16*60 else (max(0.05, (hm-open_m)/390.0) if hm > open_m else 0.05)
    upd = st_upd = 0
    for r in us:
        q = Q.get(r["c"])
        if not q or not q.get("regularMarketPrice"):
            continue
        P = q["regularMarketPrice"]
        r["px"] = P; r["close"] = P
        r["chg"] = q.get("regularMarketChangePercent")
        if q.get("marketCap"):
            r["cap"] = q["marketCap"]; r["mcap"] = q["marketCap"]
        if r.get("tp") and P > 0:
            r["upside"] = r["tp"]/P - 1
        # quotes가 매회 계산해 주는 지표들 — 빌드와 동일 필드·동일 단위로 그대로 갱신
        if q.get("fiftyDayAverageChangePercent") is not None: r["v50"] = q["fiftyDayAverageChangePercent"]
        if q.get("twoHundredDayAverageChangePercent") is not None: r["vs200"] = q["twoHundredDayAverageChangePercent"]
        if q.get("fiftyTwoWeekChangePercent") is not None: r["w52"] = q["fiftyTwoWeekChangePercent"]
        if q.get("fiftyTwoWeekHighChangePercent") is not None: r["hi52"] = q["fiftyTwoWeekHighChangePercent"]
        vol, va3 = q.get("regularMarketVolume"), q.get("averageDailyVolume3Month")
        if vol and va3:
            r["volx"] = round((vol/frac)/va3, 2)
        upd += 1
        st = stdb.get(r["c"])
        if not st:
            continue
        pc = st.get("pc") or P
        s19, q19 = st.get("s19"), st.get("q19")
        ma20 = None
        if s19 is not None:
            ma20 = (s19+P)/20.0
            r["v20"] = P/ma20 - 1
            var = max(0.0, (q19+P*P)/20.0 - ma20*ma20)
            sd = var ** 0.5
            if sd > 0:
                r["bb"] = round((P-(ma20-2*sd))/(4*sd)*100, 1)
        ma50v, ma200v = q.get("fiftyDayAverage"), q.get("twoHundredDayAverage")
        if ma20 and ma50v and ma200v:
            r["align"] = "정배열" if ma20 > ma50v > ma200v else ("역배열" if ma20 < ma50v < ma200v else "혼조")
        if st.get("g") is not None:
            d = P - pc
            g2 = (st["g"]*13 + max(d, 0.0))/14.0
            l2 = (st["l"]*13 + max(-d, 0.0))/14.0
            r["rsi"] = round(100.0 if l2 == 0 else 100 - 100/(1+g2/l2), 1)
        if st.get("e12") is not None:
            e12 = P*2/13.0 + st["e12"]*11/13.0
            e26 = P*2/27.0 + st["e26"]*25/27.0
            mv = e12 - e26
            if st.get("sig") is not None:
                sg = mv*2/10.0 + st["sig"]*8/10.0
                r["macd"] = ("골든↑" if mv > sg and mv > 0 else "골든↓" if mv > sg else
                             "데드↓" if mv <= sg and mv < 0 else "데드↑")
        st_upd += 1
    pool["live_at"] = now.strftime("%m-%d %H:%M ET") + " 미국장중"
    T.save_db("screener_pool", pool)
    print(f"intraday_us: 시세 {upd} · 지표 {st_upd} / {len(us)} · frac={frac:.2f} · {pool['live_at']}")

if __name__ == "__main__":
    main(force="--force" in sys.argv)
