#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gt2_test.py — 표 파서 v2 실측 케이스 테스트 (2026-08-15).

다중 열 표라서 문장 파서가 기각한 실제 종목들의 캐시 원문에 v2 를 돌리고,
**Benzinga 같은 발표 레코드를 정답**으로 대조한다. 네트워크 호출 없음.
사용: gt2_test.py [SYM ...]  (미지정 시 기본 표본)
"""
import gzip, json, sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from guidance_table import parse_tables

BASE = Path(__file__).resolve().parent.parent
LIVE = BASE / "data" / "db" / "earnings_live_us.json"
EXC = BASE / "data" / "cache" / "exhibit"
BZC = BASE / "data" / "cache" / "bz"
NUM = lambda v: (float(v) if v not in (None, "", "0.000") else None)
DEFAULT = ["MIDD", "ATI", "AKAM", "AMPL", "OPRT", "CRNC", "PBYI", "LFTO", "MH", "DD",
           "UTI", "ASTH", "AIP", "CGNX", "HLIT", "GMRS", "VTRS", "CCSI", "MEC", "ESS"]


def bz_truth(sym, d8):
    """같은 발표(±10일) BZ 레코드 → {('rev','Q'):(lo,hi), ...}"""
    p = BZC / f"{sym}.json"
    if not p.exists():
        return {}
    try:
        rows = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}
    ref = datetime.strptime(d8, "%Y%m%d").date()
    out = {}
    for x in rows:
        try:
            dd = datetime.strptime(str(x.get("date"))[:10], "%Y-%m-%d").date()
        except Exception:
            continue
        if abs((dd - ref).days) > 10:
            continue
        per = "Y" if str(x.get("period", "")).upper() == "FY" else "Q"
        for mk, lk, hk in (("rev", "revenue_guidance_min", "revenue_guidance_max"),
                           ("eps", "eps_guidance_min", "eps_guidance_max")):
            lo, hi = NUM(x.get(lk)), NUM(x.get(hk))
            if lo is not None and (mk, per) not in out:
                out[(mk, per)] = (lo, hi if hi is not None else lo)
    return out


def main():
    syms = [s.upper() for s in sys.argv[1:]] or DEFAULT
    live = json.loads(LIVE.read_text(encoding="utf-8"))
    items = {}
    for d8 in sorted(live.get("days") or {}, reverse=True):
        for it in live["days"][d8]:
            c = it.get("c")
            if c in syms and c not in items and it.get("acc"):
                items[c] = (d8, it["acc"])
    ok = bad = miss = 0
    for sym in syms:
        if sym not in items:
            print(f"SKIP {sym:6s} 항목/acc 없음")
            continue
        d8, acc = items[sym]
        p = EXC / f"{acc}.html.gz"
        if not p.exists():
            print(f"SKIP {sym:6s} 원문 캐시 없음")
            continue
        html = gzip.open(p, "rt", encoding="utf-8", errors="ignore").read()
        g = parse_tables(html)
        truth = bz_truth(sym, d8)
        got = {}
        for per, pre in (("Q", ""), ("Y", "fy_")):
            for mk in ("rev", "eps"):
                lo = g.get(f"{pre}{mk}_lo")
                if lo is not None:
                    got[(mk, per)] = (lo, g.get(f"{pre}{mk}_hi"))
        if not got and not truth:
            print(f"—    {sym:6s} 표값 없음 · BZ 정답도 없음")
            continue
        line = []
        for key in sorted(set(got) | set(truth)):
            mk, per = key
            gv, tv = got.get(key), truth.get(key)
            unit = 1 if mk == "eps" else 1.0
            if gv and tv:
                mg, mt = (gv[0] + gv[1]) / 2, (tv[0] + tv[1]) / 2
                if mt and abs(mg / mt - 1) <= 0.02:
                    ok += 1; line.append(f"{mk}/{per} OK({mg:,.2f})")
                else:
                    bad += 1; line.append(f"{mk}/{per} FAIL(우리 {mg:,.2f} vs BZ {mt:,.2f})")
            elif gv and not tv:
                line.append(f"{mk}/{per} 단독({(gv[0]+gv[1])/2:,.2f})")
            else:
                miss += 1; line.append(f"{mk}/{per} 미추출(BZ {(tv[0]+tv[1])/2:,.2f})")
        print(f"{sym:6s} " + " · ".join(line))
    print(f"\n일치 {ok} · 불일치 {bad} · 미추출 {miss}")


if __name__ == "__main__":
    main()
