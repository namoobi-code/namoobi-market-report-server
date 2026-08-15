#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""firesale.py — 급매 압력 지표 (국토부 실거래 apt.sqlite 에서 직접 계산 · 월별)

왜 직접 만드나
  '급매'는 공식 통계가 없다. 호가·매물 데이터는 유료이거나 크롤링이라 못 쓴다.
  그런데 우리는 단지·면적·월 단위 실거래 집계(n·평균·중위·최저·최고)를 이미 갖고 있다.
  같은 단지의 **직전 6개월 중위가**를 기준선으로 두면, 그 아래로 얼마나 빠진 값에
  거래가 체결됐는지를 셀 수 있다. 이게 급매의 관측 가능한 그림자다.

두 가지 지표 (둘 다 %)
  deep  급매 체결 비중  — 그 달 최저체결가(mn)가 직전 6개월 중위가의 90% 미만인
                        (단지·면적) 칸의 비중. "얼마나 많은 단지에서 급매가 나왔나".
  down  하락거래 비중    — 그 달 중위가(med)가 직전 6개월 중위가의 95% 미만인 칸의
                        **거래건수 가중** 비중. "실제 거래의 몇 %가 싸게 팔렸나".

한계 — 반드시 화면에 같이 적을 것
  ① 원자료가 (단지·면적·월) 집계라 개별 거래 한 건씩은 못 본다. mn 은 그 칸의 최저가다.
  ② 직전 6개월에 거래가 없던 칸은 기준선이 없어 제외된다(신축·거래절벽 구간에서 표본이 준다).
  ③ 공식 '급매' 정의가 아니다. 절대수준이 아니라 **방향과 상대 비교**로 읽어야 한다.
  ④ 실거래 DB 가 채워진 시군구만 들어간다(심층 백필 진행 중).

산출: data/db/firesale.json
  {asof, src, note, t:[YYYYMM], deep:{지역:[%]}, down:{지역:[%]}, cells:{지역:[표본수]}}
cron: 30 7 * * *
"""
import json, sqlite3, statistics, sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DB   = BASE / "data" / "db"
OUT  = DB / "firesale.json"
SRC  = DB / "apt.sqlite"

SGG2 = {"11": "서울", "26": "부산", "27": "대구", "28": "인천", "29": "광주", "30": "대전",
        "31": "울산", "36": "세종", "41": "경기", "43": "충북", "44": "충남", "46": "전남",
        "47": "경북", "48": "경남", "50": "제주", "51": "강원", "52": "전북"}

DEEP_CUT = 0.90        # 최저체결가가 기준선의 90% 미만 → 급매 체결
DOWN_CUT = 0.95        # 중위가가 기준선의 95% 미만 → 하락거래
WIN      = 6           # 기준선 = 직전 6개월 중위가의 중앙값
MIN_CELL = 30          # 표본이 이보다 적은 (지역,월) 은 값을 내지 않는다


def ymadd(ym, k):
    y, m = int(ym[:4]), int(ym[4:])
    t = y * 12 + (m - 1) + k
    return "%04d%02d" % (t // 12, t % 12 + 1)


def main():
    if not SRC.exists():
        raise SystemExit(f"✗ {SRC} 없음")
    cx = sqlite3.connect(f"file:{SRC}?mode=ro", uri=True)
    print("apt.sqlite 스트리밍 집계 중…", flush=True)
    # (2026-08-16) fetchall() 금지 — 268만 행을 한 번에 올렸다가 서버(메모리 작은 인스턴스)를
    # 통째로 멈춰 세웠다. 커서를 그대로 순회하며 (단지·면적) 그룹이 바뀔 때마다 버린다.
    cur = cx.execute(
        """SELECT s.apt_id, s.ar, s.ym, s.n, s.med, s.mn, substr(a.sgg,1,2) sd
           FROM sale s JOIN apt a ON a.id=s.apt_id
           WHERE s.med IS NOT NULL AND s.n>0
           ORDER BY s.apt_id, s.ar, s.ym""")
    cur.arraysize = 5000
    rows = cur                                   # 지연 순회 — 메모리에 다 안 올린다

    # (지역, 월) 누적기 — '전국'은 수집된 시군구 전체 합
    deep_hit, deep_tot = defaultdict(int), defaultdict(int)
    down_hit, down_tot = defaultdict(int), defaultdict(int)

    cur_key, hist = None, []          # hist = [(ym, med)] 같은 (단지,면적)의 과거
    for aid, ar, ym, n, med, mn, sd in rows:
        key = (aid, ar)
        if key != cur_key:
            cur_key, hist = key, []
        # 직전 6개월(연속 달력 기준) 안의 중위가들만 기준선으로 쓴다
        lo = ymadd(ym, -WIN)
        base = [m for (t, m) in hist if lo <= t < ym]
        if base:
            ref = statistics.median(base)
            if ref > 0:
                regs = ("전국", SGG2.get(sd))
                for r in regs:
                    if not r:
                        continue
                    deep_tot[(r, ym)] += 1
                    if mn is not None and mn < ref * DEEP_CUT:
                        deep_hit[(r, ym)] += 1
                    down_tot[(r, ym)] += n
                    if med < ref * DOWN_CUT:
                        down_hit[(r, ym)] += n
        hist.append((ym, med))
        if len(hist) > WIN + 2:
            hist.pop(0)

    ts = sorted({ym for (_, ym) in deep_tot})
    regs = sorted({r for (r, _) in deep_tot}, key=lambda x: (x != "전국", x))
    pct = lambda h, t: round(100 * h / t, 2) if t >= MIN_CELL else None
    out = {
        "asof": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "src": "국토부 실거래(RTMS) 아파트 매매 — 서버 자체 계산",
        "note": (f"급매 체결 비중 = 그 달 최저체결가가 같은 단지·면적의 직전 {WIN}개월 중위가의 "
                 f"{int(DEEP_CUT*100)}% 미만인 칸의 비중 · 하락거래 비중 = 중위가가 "
                 f"{int(DOWN_CUT*100)}% 미만인 칸의 거래건수 가중 비중. 공식 통계가 아니라 "
                 f"실거래로 만든 대리지표 — 절대수준보다 방향으로 볼 것"),
        "params": {"deep_cut": DEEP_CUT, "down_cut": DOWN_CUT, "window": WIN, "min_cell": MIN_CELL},
        "t": ts,
        "deep":  {r: [pct(deep_hit[(r, t)], deep_tot[(r, t)]) for t in ts] for r in regs},
        "down":  {r: [pct(down_hit[(r, t)], down_tot[(r, t)]) for t in ts] for r in regs},
        "cells": {r: [deep_tot[(r, t)] for t in ts] for r in regs},
    }
    DB.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    d, w = out["deep"]["전국"], out["down"]["전국"]
    tail = [(ts[i], d[i], w[i]) for i in range(len(ts)) if d[i] is not None][-4:]
    print(f"  → {OUT} ({OUT.stat().st_size // 1024}KB) · {ts[0]}~{ts[-1]} · 지역 {len(regs)}")
    for t, a, b in tail:
        print(f"    {t} 급매 {a}% · 하락거래 {b}%")


if __name__ == "__main__":
    main()
