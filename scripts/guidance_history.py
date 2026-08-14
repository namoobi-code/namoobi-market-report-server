#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""guidance_history.py — 가이던스 **과거 이력 DB** + 회사별 성향 지표 (2026-08-15 신설).

발견: Benzinga 종목 캐시(data/cache/bz/*.json)에는 최신뿐 아니라 **2022년부터의
전체 가이던스 레코드**가 들어 있다(실측 VRNS 2022-10~현재 20개). 네트워크 호출 없이
캐시를 풀어 이력 DB 를 만들면 4년치 아카이브가 즉시 생긴다.

산출물 2개
  data/db/guidance_history.json   전체 이력(심볼별 행 목록) — 분석·백테스트용(무거움)
  data/db/guidance_tendency.json  회사별 성향 요약(작음) — 프론트 상세 페이지 표시용
     {SYM: {"up":상향횟수, "dn":하향, "same":유지, "n":레코드수, "first":"2022-10",
            "last":"2026-08", "fy":연간제공비율%, "q":분기제공비율%}}

성향 판정: 같은 대상 기간(예: FY2026)의 레코드를 날짜순으로 늘어놓고 중간값이
직전 대비 +0.5% 넘게 오르면 상향, −0.5% 넘게 내리면 하향, 그 사이면 유지.
EPS 가 있으면 EPS 기준, 없으면 매출 기준. **회사가 가이던스를 올리는/내리는 습관**
— Benzinga 도 제공하지 않는 자체 파생 신호다.

cron: 매일 09:40 (guidance_bz 09:10 뒤). 네트워크 호출 없음, 수 초면 끝난다.
"""
import json
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
BZC = BASE / "data" / "cache" / "bz"
HIST = BASE / "data" / "db" / "guidance_history.json"
TEND = BASE / "data" / "db" / "guidance_tendency.json"
NUM = lambda v: (float(v) if v not in (None, "", "0.000") else None)


def main():
    hist, tend = {}, {}
    files = sorted(BZC.glob("*.json"))
    for p in files:
        sym = p.stem
        try:
            rows = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        norm, seen = [], set()
        for x in rows:
            per = f"{x.get('period')}{x.get('period_year')}"
            d = str(x.get("date") or "")[:10]
            rl, rh = NUM(x.get("revenue_guidance_min")), NUM(x.get("revenue_guidance_max"))
            el, eh = NUM(x.get("eps_guidance_min")), NUM(x.get("eps_guidance_max"))
            if not d or (rl is None and el is None):
                continue
            key = (d, per, rl, el)
            if key in seen:
                continue                       # 같은 발표가 페이지에 중복 수록되는 경우 제거
            seen.add(key)
            norm.append([d, per, x.get("eps_type") or "",
                         rl, rh if rh is not None else rl,
                         el, eh if eh is not None else el])
        if not norm:
            continue
        norm.sort(key=lambda r: r[0])
        # 성향: 같은 대상 기간 안에서의 개정 방향
        up = dn = same = 0
        by_per = {}
        for r in norm:
            by_per.setdefault(r[1], []).append(r)
        for per, rs in by_per.items():
            prev = None
            for r in rs:
                mid = ((r[5] + r[6]) / 2 if r[5] is not None else
                       (r[3] + r[4]) / 2 if r[3] is not None else None)
                if mid is None:
                    continue
                if prev is not None and prev != 0:
                    ch = mid / prev - 1
                    if ch > 0.005:
                        up += 1
                    elif ch < -0.005:
                        dn += 1
                    else:
                        same += 1
                prev = mid
        n = len(norm)
        nfy = sum(1 for r in norm if r[1].upper().startswith("FY"))
        hist[sym] = norm[-80:]                 # 심볼당 최근 80행이면 4년+ 충분
        tend[sym] = {"up": up, "dn": dn, "same": same, "n": n,
                     "first": norm[0][0][:7], "last": norm[-1][0][:7],
                     "fy": round(nfy / n * 100), "q": round((n - nfy) / n * 100)}
    meta = {"asof": datetime.now().strftime("%Y-%m-%d %H:%M"), "n_sym": len(hist),
            "src": "Benzinga 캐시(2022~) — 검증·참고용, 판정 미사용"}
    for path, obj in ((HIST, {**meta, "sym": hist}), (TEND, {**meta, "sym": tend})):
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)
    tot = sum(len(v) for v in hist.values())
    print(f"[ghist] {len(hist)}종목 · 이력 {tot}행 · tendency {TEND.stat().st_size//1024}KB")


if __name__ == "__main__":
    main()
