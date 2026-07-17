#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""backfill_tp_history.py — KR 목표주가 컨센서스 '월별 1년' 백필 (v2026-07-18).

배경: 스크리너 '목표추세'(rev/tp_trend)는 tp_history(일별 자체 스냅샷)가 2점 이상 모여야
계산돼 신규 가동 직후엔 전 종목 '누적중'으로 표시됐다.
소스: WiseReport 기업 스냅샷(comp.wisereport.co.kr/company/c1010001.aspx?cmp_cd=CODE, 무로그인)
페이지에 내장된 chartData2.target_price = 최근 1년 월말 목표주가 컨센서스(12포인트, FnGuide 산출).
실측(2026-07-18, 005930): 84,083(25/08) → 513,958(26/07/16) — 12점 + 투자의견(deg) 동반.

동작: screener_pool(kr)에서 tp 보유 종목을 골라 월별 포인트를 tp_history 에 '없는 날짜만' upsert.
      기존 일별 스냅샷과 공존(계단열 로직이 유의미 변경만 사용). 주 1회 cron 이면 충분(월말 신규점).
Usage: backfill_tp_history.py [--limit N] [--sleep 0.25] [--codes 005930,000660]
"""
import json, os, re, sys, time, urllib.request
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ta_screen as T

LIMIT = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else 10**9
SLEEP = float(sys.argv[sys.argv.index("--sleep") + 1]) if "--sleep" in sys.argv else 0.25
ONLY = (sys.argv[sys.argv.index("--codes") + 1].split(",") if "--codes" in sys.argv else None)
UA = {"User-Agent": "Mozilla/5.0", "Referer": "https://comp.wisereport.co.kr/"}

def fetch_tp_series(code):
    url = f"https://comp.wisereport.co.kr/company/c1010001.aspx?cmp_cd={code}"
    h = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20).read().decode("utf-8", "replace")
    m = re.search(r"chartData2\s*=\s*(\{.*?\});", h, re.S)
    if not m:
        return []
    tp = (json.loads(m.group(1)).get("target_price") or [])
    out = []
    for p in tp:
        try:
            d = date.fromtimestamp(p["x"] / 1000).isoformat()
            v = float(p["y"])
            if v > 0:
                out.append((d, round(v, 2)))
        except Exception:
            pass
    return out

def main():
    pool = (T.load_db("screener_pool") or {})
    kr = (pool.get("data") or pool).get("kr") or pool.get("kr") or []
    # 기본 = tp(컨센서스) 보유 종목만(나머지는 애널리스트 무커버리지라 시계열 자체가 없음).
    # --all = 전 종목 스캔 — 풀 tp 가 비어도 WiseReport(FnGuide)엔 있는 엣지 케이스 회수용(주간 cron 권장).
    codes = [r["c"] for r in kr] if "--all" in sys.argv else [r["c"] for r in kr if r.get("tp")]
    if ONLY:
        codes = [c for c in codes if c in ONLY] or ONLY
    codes = codes[:LIMIT]
    db = T.load_db("tp_history") or {}
    hist = db.get("hist") or {}
    ok = miss = added = 0
    for i, c in enumerate(codes):
        try:
            pts = fetch_tp_series(c)
        except Exception:
            pts = []
        if pts:
            ok += 1
            d = hist.setdefault(c, {})
            for iso, v in pts:
                if iso not in d:
                    d[iso] = v; added += 1
        else:
            miss += 1
        if (i + 1) % 50 == 0:
            print(f"  {i+1}/{len(codes)} ok={ok} miss={miss} added={added}", flush=True)
        time.sleep(SLEEP)
    T.save_db("tp_history", {"hist": hist})
    print(f"backfill 완료 — 종목 {len(codes)} (ok {ok} / miss {miss}) · 신규 포인트 {added} · "
          f"보유종목 {len(hist)}")

if __name__ == "__main__":
    main()
