#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gt_audit.py — 표 파서(guidance_table) 검증 하네스 · 2026-08-10 신설.

표 파서를 본선에 넣었다가 이상치가 매출 6.2%→12.3% 로 늘어 되돌렸다. 다시 켜려면
"어느 표에서 왜 틀리는지"를 표본으로 확인해야 하는데, 손으로 기대값 50개를 만드는 건
느리고 반복도 안 된다. 그래서 **문장 파서와 표 파서를 나란히 돌려 불일치만 뽑는다.**

  · 둘 다 값이 있고 서로 다르면 → 눈으로 볼 후보(근거 문구가 함께 나온다)
  · 표만 값이 있으면 → 표 파서가 커버리지를 넓히는 사례
  · 문장만 값이 있으면 → 표 파서가 놓친 사례

**SEC 를 부르지 않는다** — data/cache/exhibit 에 받아 둔 원문만 읽는다. 몇 번이든 돌려도 된다.
사용: gt_audit.py [--limit 60] [--metric rev|eps|all]
"""
import gzip, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from guidance_parse import parse_guidance
from guidance_table import parse_tables
from earnings_8k_watch import _strip

BASE = Path(__file__).resolve().parent.parent
CACHE = BASE / "data" / "cache" / "exhibit"
LIVE = BASE / "data" / "db" / "earnings_live_us.json"
ARG = lambda k, d: (int(sys.argv[sys.argv.index(k) + 1]) if k in sys.argv else d)
LIMIT = ARG("--limit", 60)
MET = sys.argv[sys.argv.index("--metric") + 1] if "--metric" in sys.argv else "all"
KEYS = [k for k in ("rev", "fy_rev", "eps", "fy_eps") if MET == "all" or MET in k]


def main():
    live = json.loads(LIVE.read_text(encoding="utf-8"))
    acc2sym = {it["acc"]: it["c"] for d8 in live.get("days", {}) for it in live["days"][d8]
               if it.get("acc") and it.get("c")}
    files = sorted(CACHE.glob("*.html.gz"))[:LIMIT]
    n = both = onlyT = onlyS = disagree = 0
    for f in files:
        acc = f.name.replace(".html.gz", "")
        try:
            raw = gzip.decompress(f.read_bytes()).decode("utf-8", "ignore")
        except Exception:
            continue
        n += 1
        gs, gt = parse_guidance(_strip(raw)), parse_tables(raw)
        sym = acc2sym.get(acc, acc[:12])
        for k in KEYS:
            a, b = gs.get(k + "_lo"), gt.get(k + "_lo")
            if a and b:
                both += 1
                if abs(a / b - 1) > 0.01:
                    disagree += 1
                    print(f"[다름] {sym:6s} {k:7s} 문장 {a:,.2f} / 표 {b:,.2f}")
                    print(f"        표 근거: {(gt.get('_ev') or {}).get(k, '')}")
                    print(f"        문장 근거: {' '.join(((gs.get('_ev') or {}).get(k) or '').split())[:130]}")
            elif b and not a:
                onlyT += 1
            elif a and not b:
                onlyS += 1
    print(f"\n— 표본 {n}건 · 둘 다 {both}(불일치 {disagree}) · 표만 {onlyT} · 문장만 {onlyS}")
    print("  불일치 사례의 '표 근거'(열 머리글·행 이름)를 보고 규칙을 좁힌 뒤 다시 돌린다.")


if __name__ == "__main__":
    main()
