#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bz_diff.py — Benzinga 대조 리포트 = **파서 개선 큐** (2026-08-10 신설).

Benzinga 는 period(FY/Q1~Q4)와 eps_type(Adj/GAAP)을 데이터로 직접 준다. 우리 8-K 파서가
가장 자주 틀리는 두 축이 정확히 그것이다. 그래서 둘을 맞대어 **어긋난 종목만** 뽑으면,
사람이 화면을 훑으며 이상치를 찾을 필요가 없다 — 고칠 대상이 자동으로 목록이 된다.

분류
  [기간]  우리가 분기로 본 것을 Benzinga 는 연간이라 함(또는 반대) → 대개 우리 오류
  [값]    기간은 같은데 값이 1% 넘게 다름 → 어느 쪽이 맞는지 근거 문장으로 확인
  [누락]  Benzinga 에는 있는데 우리는 못 뽑음 → 재현율 개선 대상
  [단독]  우리만 있음 → Benzinga 미수록(문제 아님. 우리 커버리지가 더 넓다)

SEC·Benzinga 를 호출하지 않는다(이미 저장된 값만 읽는다). 몇 번이든 돌려도 된다.
사용: bz_diff.py [--kind 기간|값|누락|all] [--limit 40]
"""
import json, sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
LIVE = BASE / "data" / "db" / "earnings_live_us.json"
ARG = lambda k, d: (int(sys.argv[sys.argv.index(k) + 1]) if k in sys.argv else d)
LIMIT = ARG("--limit", 40)
KIND = sys.argv[sys.argv.index("--kind") + 1] if "--kind" in sys.argv else "all"
PER_KO = {"0q": "진행분기", "+1q": "다음분기", "0y": "올해(FY)", "+1y": "내년(FY)"}


def main():
    live = json.loads(LIVE.read_text(encoding="utf-8"))
    rows, stat = [], {"기간": 0, "값": 0, "누락": 0, "단독": 0, "일치": 0}
    for d8 in sorted(live.get("days") or {}):
        for it in live["days"][d8]:
            if not it.get("g_bz_date"):
                continue                      # Benzinga 미수집 — 대조 불가
            bzp_sym = str(it.get("g_bz_period") or "")      # 예: FY2026 · Q32026 (종목의 '최신' 레코드일 뿐)
            for metric, gk, ko in (("rev", "g_rev", "매출"), ("eps", "g_eps", "EPS")):
                mine, mper = it.get(gk), it.get(gk + "_per")
                port = it.get(gk + "_p")
                # (2026-08-14) g_bz_period 는 종목당 1개(가장 최근 레코드)뿐이라, 매출·EPS 가
                # 각각 다른 기간의 Benzinga 레코드와 매칭됐어도 항상 같은 값으로 비교했다
                # → 매출은 분기로 정확히 맞았는데 종목 레벨 라벨이 연간이라 '기간불일치'로
                # 오판정되는 사례가 다수(실측 VRNS: 분기값 186.5로 정확히 일치했는데도 오탐).
                # gk+'_bzp' 가 그 지표가 실제로 매칭된 레코드의 기간이므로 이걸 써야 한다.
                bzp = str(it.get(gk + "_bzp") or bzp_sym)
                bz_is_fy = bzp.upper().startswith("FY")
                if mine is None and port is None:
                    continue
                if mine is None:
                    stat["누락"] += 1
                    rows.append(("누락", it["c"], ko, f"우리 없음 / 포털 {port:,.2f} ({bzp_sym})", ""))
                    continue
                if port is None:
                    stat["단독"] += 1
                    continue
                my_is_fy = str(mper or "").endswith("y")
                if my_is_fy != bz_is_fy:
                    stat["기간"] += 1
                    rows.append(("기간", it["c"], ko,
                                 f"우리 {PER_KO.get(mper, mper)} {mine:,.2f} / Benzinga {bzp} {port:,.2f}",
                                 " ".join((it.get(gk + "_ev") or "").split())[:120]))
                elif abs(mine / port - 1) > 0.01:
                    stat["값"] += 1
                    rows.append(("값", it["c"], ko, f"우리 {mine:,.2f} / 포털 {port:,.2f} "
                                                   f"({(mine/port-1)*100:+.1f}%)",
                                 " ".join((it.get(gk + "_ev") or "").split())[:120]))
                else:
                    stat["일치"] += 1
    print(f"[bz-diff] 일치 {stat['일치']} · 기간불일치 {stat['기간']} · 값불일치 {stat['값']} · "
          f"우리누락 {stat['누락']} · 우리단독 {stat['단독']}")
    if stat["일치"] + stat["기간"] + stat["값"]:
        acc = stat["일치"] / (stat["일치"] + stat["기간"] + stat["값"]) * 100
        print(f"           대조 가능분 정확도 {acc:.1f}%")
    print()
    shown = 0
    for kind, sym, ko, msg, ev in rows:
        if KIND not in ("all", kind) or shown >= LIMIT:
            continue
        shown += 1
        print(f"[{kind}] {sym:6s} {ko}  {msg}")
        if ev:
            print(f"        근거: {ev}")


if __name__ == "__main__":
    main()
