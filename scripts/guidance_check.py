#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""guidance_check.py — 가이던스 파서 **정밀도 검증 하네스** (2026-08-10 신설).

왜 필요한가
-----------
보도자료는 자유 형식 영어 문장이라 정규식이 "무조건 맞는다"는 보장을 만들 수 없다.
그래서 보장해야 할 것을 바꾼다 —
  ❌ (불가능) 모든 회사의 가이던스를 다 뽑아낸다
  ✅ (가능·검증됨) **화면에 표시되는 값은 근거 문장과 함께 재현 가능하고, 규칙을 통과한 것만**
이 스크립트는 종목별로 ①파싱 결과 ②그 값을 뽑아낸 **원문 문장** ③채택/기각 사유를
나란히 출력해, 사람이 눈으로 정오를 확인(=정밀도 측정)할 수 있게 한다.

사용: guidance_check.py SYM [SYM ...]
"""
import json, re, sys, urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from earnings_8k_watch import cik_map, exhibit_text, parse_guidance, H

BASE = Path(__file__).resolve().parent.parent


def latest_earn_8k(cik):
    j = json.loads(urllib.request.urlopen(urllib.request.Request(
        f"https://data.sec.gov/submissions/CIK{int(cik):010d}.json", headers=H), timeout=25).read())
    r = j["filings"]["recent"]
    for i in range(len(r["accessionNumber"])):
        if r["form"][i] in ("8-K", "6-K") and "2.02" in (r["items"][i] or ""):
            return r["accessionNumber"][i]
    return None


def main():
    mp = cik_map()
    for sym in sys.argv[1:]:
        cik = mp.get(sym.upper())
        if not cik:
            print(f"== {sym}: CIK 없음"); continue
        acc = latest_earn_8k(cik)
        if not acc:
            print(f"== {sym}: 실적 8-K 없음"); continue
        txt = exhibit_text(cik, acc)
        g = parse_guidance(txt)
        print("=" * 70)
        print(f"== {sym}  (8-K {acc} · 본문 {len(txt):,}자)")
        show = {k: v for k, v in g.items() if not k.startswith("_")}
        print("   파싱값:", {k: (round(v / 1e6, 1) if isinstance(v, float) and v > 1e5 else v)
                            for k, v in show.items()} or "없음")
        for k, ev in (g.get("_ev") or {}).items():
            print(f"   [{k}] 근거: {ev[:220]}")
        for rsn in (g.get("_skip") or []):
            print(f"   [기각] {rsn[:200]}")


if __name__ == "__main__":
    main()
