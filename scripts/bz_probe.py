#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bz_probe.py — Benzinga 불일치(기간·값) 전건 심층 진단 (2026-08-14 신설, 일회성 분석 도구).

bz_diff 는 '어긋났다'까지만 알려준다. 원인을 고치려면 건별로
  ① 우리 값·기간·근거문장(_ev)
  ② Benzinga 의 **전체 레코드**(연간·분기 둘 다 — 어느 쪽과 맞는지 즉시 보인다)
  ③ 캐시된 8-K 원문에서 값 주변 텍스트
를 한 화면에 놓고 봐야 한다. 네트워크 호출 없음(전부 캐시·저장값).

사용: bz_probe.py [--kind 기간|값] [--limit 30]
"""
import gzip, json, re, sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
LIVE = BASE / "data" / "db" / "earnings_live_us.json"
BZC = BASE / "data" / "cache" / "bz"
EXC = BASE / "data" / "cache" / "exhibit"
ARG = lambda k, d: (int(sys.argv[sys.argv.index(k) + 1]) if k in sys.argv else d)
LIMIT = ARG("--limit", 30)
KIND = sys.argv[sys.argv.index("--kind") + 1] if "--kind" in sys.argv else "all"
NUM = lambda v: (float(v) if v not in (None, "", "0.000") else None)


def bz_records(sym):
    p = BZC / f"{sym}.json"
    if not p.exists():
        return []
    try:
        rows = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return []
    out = []
    for x in rows[:6]:
        out.append(f"{x.get('period')}{x.get('period_year')} {x.get('eps_type')} "
                   f"rev={NUM(x.get('revenue_guidance_min'))}-{NUM(x.get('revenue_guidance_max'))} "
                   f"eps={NUM(x.get('eps_guidance_min'))}-{NUM(x.get('eps_guidance_max'))} ({x.get('date')})")
    return out


def exhibit_snips(acc, needles):
    """캐시된 원문에서 needle 숫자 주변 텍스트."""
    p = EXC / f"{acc}.html.gz"
    if not acc or not p.exists():
        return []
    try:
        import html as _h
        t = gzip.open(p, "rt", encoding="utf-8", errors="ignore").read()
        t = re.sub(r"<[^>]+>", " ", t)
        t = _h.unescape(t)
        t = re.sub(r"\s+", " ", t)
    except Exception:
        return []
    outs = []
    for nd in needles:
        if nd is None:
            continue
        for pat in (f"{nd:,.2f}".rstrip("0").rstrip("."), f"{nd:,.0f}", str(nd)):
            i = t.find(pat)
            if i > 0:
                outs.append(t[max(0, i - 220):i + 160])
                break
    return outs


def main():
    live = json.loads(LIVE.read_text(encoding="utf-8"))
    shown = 0
    for d8 in sorted(live.get("days") or {}, reverse=True):
        for it in live["days"][d8]:
            if not it.get("g_bz_date") or shown >= LIMIT:
                continue
            for metric, gk, ko in (("rev", "g_rev", "매출"), ("eps", "g_eps", "EPS")):
                mine, mper = it.get(gk), it.get(gk + "_per")
                port = it.get(gk + "_p")
                if mine is None or port is None:
                    continue
                bzp = str(it.get(gk + "_bzp") or it.get("g_bz_period") or "")
                my_fy = str(mper or "").endswith("y")
                bz_fy = bzp.upper().startswith("FY")
                kind = ("기간" if my_fy != bz_fy else
                        ("값" if abs(mine / port - 1) > 0.01 else None))
                if kind is None or KIND not in ("all", kind) or shown >= LIMIT:
                    continue
                shown += 1
                print(f"==== [{kind}] {it['c']} {ko}  우리 {mper} {mine:,.2f} / BZ {bzp} {port:,.2f} ====")
                print(f"  ev: {' '.join((it.get(gk+'_ev') or '').split())[:200]}")
                for r in bz_records(it["c"]):
                    print(f"  bz: {r}")
                for s in exhibit_snips(it.get("acc"), [mine if metric == "eps" else None]):
                    print(f"  8k: …{s}…")
                print()


if __name__ == "__main__":
    main()
