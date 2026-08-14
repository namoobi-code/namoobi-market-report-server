#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bz_gap_audit.py — '우리 누락'(Benzinga 는 있는데 우리 파싱은 없음) 원인 분류 (2026-08-14).

질문: 8-K 에 가이던스가 **있었는데 파서가 못 뽑아 버린** 케이스가 얼마나 되나?
방법: 누락 건마다 캐시된 8-K 원문에서 Benzinga 값(하한·상한)을 몇 가지 표기로 찾아 본다.
  [원문에있음]  8-K 에 그 숫자가 있다 → 파서 개선 대상 (skip 사유 함께 출력)
  [원문에없음]  8-K 에 그 숫자가 없다 → 보도자료 밖(콜·프레젠테이션·웹사이트) 제공
  [캐시없음]    원문 캐시가 없어 판단 불가
네트워크 호출 없음. 사용: bz_gap_audit.py [--limit 30] [--metric rev|eps]
"""
import gzip, html as _h, json, re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from guidance_parse import parse_guidance

BASE = Path(__file__).resolve().parent.parent
LIVE = BASE / "data" / "db" / "earnings_live_us.json"
EXC = BASE / "data" / "cache" / "exhibit"
BZC = BASE / "data" / "cache" / "bz"
ARG = lambda k, d: (int(sys.argv[sys.argv.index(k) + 1]) if k in sys.argv else d)
LIMIT = ARG("--limit", 30)
MET = sys.argv[sys.argv.index("--metric") + 1] if "--metric" in sys.argv else "both"


def _txt(acc):
    p = EXC / f"{acc}.html.gz"
    if not acc or not p.exists():
        return None
    t = gzip.open(p, "rt", encoding="utf-8", errors="ignore").read()
    t = re.sub(r"<[^>]+>", " ", t)
    t = _h.unescape(t).replace("–", "-").replace("—", "-")
    return re.sub(r"\s+", " ", t)


def _bz_range(sym, metric, per_want):
    """캐시된 BZ 레코드에서 해당 기간의 (lo, hi)."""
    p = BZC / f"{sym}.json"
    if not p.exists():
        return None, None
    try:
        rows = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None, None
    lo_k = "revenue_guidance_min" if metric == "rev" else "eps_guidance_min"
    hi_k = "revenue_guidance_max" if metric == "rev" else "eps_guidance_max"
    fy = str(per_want or "").upper().startswith("FY")
    for x in rows:
        if (str(x.get("period", "")).upper() == "FY") == fy and x.get(lo_k) not in (None, "", "0.000"):
            return float(x[lo_k]), float(x.get(hi_k) or x[lo_k])
    return None, None


def _found(t, v, metric):
    """원문 t 에 값 v 가 있는가 — 대표 표기 몇 가지로 검색."""
    if v is None:
        return False
    cands = []
    if metric == "eps":
        cands = [f"${v:.2f}".rstrip("0").rstrip("."), f"${v:.2f}", f"{v:.2f}"]
    else:
        b = v / 1e9
        m = v / 1e6
        for x in (f"{b:.3f}", f"{b:.2f}", f"{b:.1f}"):
            cands.append(x.rstrip("0").rstrip(".") + " billion")
            cands.append("$" + x.rstrip("0").rstrip("."))
        cands.append(f"{m:,.1f}".rstrip("0").rstrip("."))
        cands.append(f"{m:,.0f}")
    return any(c in t for c in cands if len(c) >= 3)


def main():
    live = json.loads(LIVE.read_text(encoding="utf-8"))
    stat = {"원문에있음": 0, "원문에없음": 0, "캐시없음": 0}
    shown = 0
    for d8 in sorted(live.get("days") or {}, reverse=True):
        for it in live["days"][d8]:
            for metric, gk in (("rev", "g_rev"), ("eps", "g_eps")):
                if MET not in ("both", metric):
                    continue
                if it.get(gk) is not None or it.get(gk + "_p") is None:
                    continue                     # 누락 케이스만
                t = _txt(it.get("acc"))
                if t is None:
                    stat["캐시없음"] += 1
                    continue
                lo, hi = _bz_range(it["c"], metric, it.get(gk + "_bzp") or it.get("g_bz_period"))
                hit = _found(t, lo, metric) or _found(t, hi, metric)
                key = "원문에있음" if hit else "원문에없음"
                stat[key] += 1
                if hit and shown < LIMIT:
                    shown += 1
                    g = parse_guidance(t)
                    sk = [s for s in (g.get("_skip") or []) if s.startswith(metric)]
                    print(f"[{it['c']:6s}] {metric} BZ {lo}~{hi} ({it.get(gk+'_bzp') or it.get('g_bz_period')})")
                    for s in sk[:3]:
                        print(f"    skip: {s[:150]}")
                    if not sk:
                        print("    skip: (사유 기록 없음 — 후보 자체가 안 잡힘)")
    print()
    print("[집계]", stat)


if __name__ == "__main__":
    main()
