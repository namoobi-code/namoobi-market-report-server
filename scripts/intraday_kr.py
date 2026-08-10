#!/usr/bin/env python3
# intraday_kr.py — 장중(KR) 전종목 지표 5분 증분 갱신.
# 원리: 새벽 빌드가 저장한 '마지막 완결봉 기준 상태'(ta_state) + 네이버 벌크 시세(당일가·누적거래량)로
#       RSI·MACD·이평(20/50/200)·볼린저·52주고점比·거래량배수를 O(1) 재계산해 screener_pool에 반영.
# 거래량배수는 세션 경과 시간 보정(frac) — 장 초반 급등주도 과소평가 없이 포착.
# z-score(2단계)는 하루 2회 기준 유지(장중 미갱신).
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from datetime import datetime, timedelta, timezone
import ta_screen as T

KST = timezone(timedelta(hours=9))

def in_session(now):
    if now.weekday() >= 5:                      # 주말
        return False
    hm = now.hour*60 + now.minute
    return 8*60+58 <= hm <= 15*60+40            # 08:58 ~ 15:40 (정규장 09:00~15:30)

def bulk_vol():
    """네이버 marketValue 벌크 — close·chg·mcap·누적거래량(주수)."""
    out = {}
    for mkt in ("KOSPI", "KOSDAQ"):
        page = 1
        while page <= 40:
            try:
                d = T.jget("https://m.stock.naver.com/api/stocks/marketValue/%s?page=%d&pageSize=100" % (mkt, page))
            except Exception:
                break
            rows = d.get("stocks") or []
            if not rows:
                break
            for x in rows:
                c = x.get("itemCode")
                if not c:
                    continue
                try:
                    out[c] = {"close": float(x.get("closePriceRaw") or 0),
                              "mcap": float(x.get("marketValueRaw") or 0),
                              "vol": float(x.get("accumulatedTradingVolumeRaw") or 0),
                              "chg": float(str(x.get("fluctuationsRatio") or 0).replace(",", ""))}
                except Exception:
                    pass
            page += 1
    return out

def main(force=False):
    now = datetime.now(KST)
    if not force and not in_session(now):
        # (2026-08-09) 장마감 후 live_at 잔존 → 주말 내내 'LIVE' 로 표시되던 문제.
        # 10분에 한 번만 확인해 대용량 풀 로드 비용을 줄인다.
        if now.minute % 10 == 0:
            pool = T.load_db("screener_pool") or {}
            if pool.get("live_at"):
                pool.pop("live_at", None); T.save_db("screener_pool", pool)
                print("장외 — live_at 제거")
        print("장외 — skip"); return
    pool = T.load_db("screener_pool") or {}
    stdb = (T.load_db("ta_state") or {}).get("st") or {}
    kr = pool.get("kr") or []
    if not kr:
        print("풀 없음 — skip"); return
    NV = bulk_vol()
    if len(NV) < 500:
        print(f"벌크 시세 부족({len(NV)}) — skip"); return
    # 세션 경과 비율(09:00~15:30=390분). 장 시작 직후 왜곡 방지 하한 0.05
    hm = now.hour*60 + now.minute
    frac = 1.0 if hm >= 15*60+30 else (max(0.05, (hm-540)/390.0) if hm > 540 else 0.05)
    upd = st_upd = 0
    for r in kr:
        nv = NV.get(r["c"])
        if not nv or not nv.get("close"):
            continue
        P = nv["close"]
        r["px"] = P; r["close"] = P
        r["chg"] = nv.get("chg")
        if nv.get("mcap"):
            r["cap"] = nv["mcap"]; r["mcap"] = nv["mcap"]
        if r.get("tp") and P > 0:
            r["upside"] = r["tp"]/P - 1
        upd += 1
        st = stdb.get(r["c"])
        if not st:
            continue
        pc = st.get("pc") or P
        # 이평·볼린저 (합계 상태 + 당일가)
        s19, q19 = st.get("s19"), st.get("q19")
        ma20 = ma50 = ma200 = None
        if s19 is not None:
            ma20 = (s19+P)/20.0
            r["v20"] = P/ma20 - 1
            var = max(0.0, (q19 + P*P)/20.0 - ma20*ma20)
            sd = var ** 0.5
            if sd > 0:
                r["bb"] = round((P - (ma20 - 2*sd)) / (4*sd) * 100, 1)
        if st.get("s49") is not None:
            ma50 = (st["s49"]+P)/50.0; r["v50"] = P/ma50 - 1
        if st.get("m199"):
            ma200 = (st["s199"]+P)/(st["m199"]+1.0); r["vs200"] = P/ma200 - 1
        if ma20 and ma50 and ma200:
            r["align"] = "정배열" if ma20 > ma50 > ma200 else ("역배열" if ma20 < ma50 < ma200 else "혼조")
        # RSI(14) — Wilder 한 스텝
        if st.get("g") is not None:
            d = P - pc
            g2 = (st["g"]*13 + max(d, 0.0))/14.0
            l2 = (st["l"]*13 + max(-d, 0.0))/14.0
            r["rsi"] = round(100.0 if l2 == 0 else 100 - 100/(1 + g2/l2), 1)
        # MACD(12,26,9) — 한 스텝
        if st.get("e12") is not None:
            e12 = P*2/13.0 + st["e12"]*11/13.0
            e26 = P*2/27.0 + st["e26"]*25/27.0
            mv = e12 - e26
            if st.get("sig") is not None:
                sg = mv*2/10.0 + st["sig"]*8/10.0
                r["macd"] = ("골든↑" if mv > sg and mv > 0 else "골든↓" if mv > sg else
                             "데드↓" if mv <= sg and mv < 0 else "데드↑")
        # 52주 고점比 (당일 신고가 반영)
        hi = st.get("hi52")
        if hi:
            hi = max(hi, P)
            r["near52"] = P/hi - 1
        # 거래량 배수 — 시간 보정
        va = st.get("va")
        if va and nv.get("vol"):
            r["volx"] = round((nv["vol"]/frac)/va, 2)
        st_upd += 1
    pool["live_at"] = now.strftime("%m-%d %H:%M") + " 장중"
    # (2026-08-10) 통째 덮어쓰기 → **병합 저장**. 이 스크립트는 수 분간 돌기 때문에
    # 그 사이 다른 수집기가 쓴 값(컨센·가이던스 등)이 옛 사본으로 지워지는 사고가 있었다.
    save_pool_merged(pool, LIVE_FIELDS, mkts=("kr",), extra_meta=("live_at",))
    print(f"intraday: 시세 {upd} · 지표 {st_upd} / {len(kr)} · frac={frac:.2f} · {pool['live_at']}")

if __name__ == "__main__":
    main(force="--force" in sys.argv)
