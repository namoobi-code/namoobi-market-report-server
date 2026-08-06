#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""div_hist_us.py — US 배당 이력 (2026-08-06 신설 · 주 1회).

야후 v8 chart events=div 실측 기반(range=30y·interval=1mo — max 는 중간 연도 손실 실측 확인):
  dgy  = 배당 연속 증가 연수 — '건당 평균 배당(연합계÷지급횟수)' 기준.
         연간 합계는 지급 밀림(연 11/13회)에 취약해 O 리얼티인컴이 1년으로 오판됐다(실측)
         → 건당 평균으로 O=30년+, MMM(2024 감액)=0 정확 판정. 30년 도달 시 '30년+' 캡.
         ※ 야후 이력 한계로 KO·PG 는 실제(60년+)보다 짧게(22~23년) 나옴 — 보수적 오차라 함정 없음.
  freq = 최근 12개월 지급 횟수 · md = freq≥10(월배당)
  pmg  = 분기배당 지급월 그룹: 1=1·4·7·10월, 2=2·5·8·11월, 3=3·6·9·12월 (최근 4건 최빈)
         → 그룹별 1종목씩 3종목이면 매월 배당 수령(월배당 달력 조합)
  mdd5 = 최근 5년 월봉 최대낙폭(%) — '폭락 이력' 지표
대상: screener_pool.us 중 배당 지급 종목(divy>0). 산출: data/db/div_hist_us.json
cron: 40 8 * * 0
"""
import json, time
from datetime import datetime, timezone, timedelta
from pathlib import Path
import ta_screen as T

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "data" / "db" / "div_hist_us.json"

def one(sym):
    try:
        j = T.jget(f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}"
                   "?range=30y&interval=1mo&events=div", timeout=15)
        res = j["chart"]["result"][0]
    except Exception:
        return None
    divs = (res.get("events") or {}).get("dividends") or {}
    if not divs:
        return None
    s, n, ts = {}, {}, []
    for v in divs.values():
        d = datetime.fromtimestamp(v["date"], timezone.utc)
        s[d.year] = s.get(d.year, 0) + v["amount"]
        n[d.year] = n.get(d.year, 0) + 1
        ts.append((v["date"], d.month))
    avg = {y: s[y]/n[y] for y in s}
    last = datetime.now().year - 1                     # 직전 완결연도부터 역방향
    inc = 0; y = last
    while y in avg and y-1 in avg and avg[y] > avg[y-1]*1.001:
        inc += 1; y -= 1
    # 이력 시작(range=30y)까지 전부 증가 = 비교 가능 횟수(최대 29)에 도달 → '30년+' 캡
    if inc >= 28 and (y-1) not in avg:
        inc = 30
    ts.sort()
    cut12 = (datetime.now(timezone.utc) - timedelta(days=366)).timestamp()
    freq = sum(1 for t, _ in ts if t >= cut12)
    md = 1 if freq >= 10 else 0
    pmg = None
    if not md and ts:
        gs = [((m-1) % 3)+1 for _, m in ts[-4:]]       # 1·4·7·10→1, 2·5·8·11→2, 3·6·9·12→3
        pmg = max(set(gs), key=gs.count)
    mdd5 = None
    try:
        cl = [x for x in res["indicators"]["quote"][0]["close"] if x][-60:]
        pk = cl[0]; dd = 0
        for c in cl:
            pk = max(pk, c); dd = min(dd, c/pk-1)
        mdd5 = round(dd*100, 1)
    except Exception:
        pass
    return {"dgy": min(inc, 30), "freq": freq, "md": md, "pmg": pmg, "mdd5": mdd5,
            "y": {str(k): round(avg[k], 4) for k in sorted(avg)[-6:]}}

def main():
    pool = json.loads((BASE / "data" / "db" / "screener_pool.json").read_text(encoding="utf-8"))
    syms = [r["c"] for r in pool.get("us") or [] if (r.get("divy") or 0) > 0]
    print(f"[divus] 배당 지급 {len(syms)}종 수집 시작")
    d = {}
    def w(sym):
        time.sleep(0.05)
        r = one(sym)
        if r: d[sym] = r
    for _ in T.pmap(w, syms, workers=6):
        pass
    OUT.write_text(json.dumps({"asof": datetime.now().strftime("%Y-%m-%d %H:%M"), "d": d},
                              ensure_ascii=False), encoding="utf-8")
    k10 = sum(1 for v in d.values() if v["dgy"] >= 10)
    k30 = sum(1 for v in d.values() if v["dgy"] >= 30)
    mdn = sum(1 for v in d.values() if v["md"])
    print(f"[divus] ✅ {len(d)}종 · 10년↑ {k10} · 30년+ {k30} · 월배당 {mdn} → {OUT}", flush=True)

if __name__ == "__main__":
    main()
