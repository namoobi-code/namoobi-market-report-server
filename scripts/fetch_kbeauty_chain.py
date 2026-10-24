#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fetch_kbeauty_chain.py — 💄 K뷰티 밸류체인 모니터 + ETF 3종 (2026-10-24 신설 · 매경LUXMEN 2026-10 'K-뷰티 실적, 주가도 우상향')

기사 프레임: "브랜드 → 유통 → ODM → 용기로 이어지는 밸류체인 전반이 동조화" + "ODM fwd PER 10배 초반 vs 2015 전성기 25~30배"
          + K-뷰티 ETF 3종(SOL 화장품TOP3플러스·TIGER 화장품·HANARO K-뷰티) 연초 +46/+33/+29%(9/17 기준).
우리가 매일 보는 것: 계층별 종목의 fwd PER·목표가 상승여력·1M/3M 수익률·영업익 리비전·영업익 전망 성장(전부 screener_pool 실측)
          → 계층 간 '동조/괴리' 판정(3M 평균 수익률 격차) · ODM 밸류 갭(전성기 밴드 대비) · ETF 3종 1M/3M/1Y(etf_pool).
신규 수집 0 — 기존 정본 재조합. cron: 10 7 * * * (screener_pool 06:52 뒤)
산출: data/db/kbeauty_chain.json
"""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DB = BASE / "data" / "db"
OUT = DB / "kbeauty_chain.json"
KST = timezone(timedelta(hours=9))

# 계층 → (코드, 표시명) — 기사·ETF 편입종목 기준. 상장 코드만.
CHAIN = [
    ("브랜드", "소비자 직접 — 성장률 둔화 시 PER 급락(기사: 전년비 10%↓면 PER 10배)", [
        ("051900", "LG생활건강"), ("090430", "아모레퍼시픽"), ("278470", "에이피알"), ("483650", "달바글로벌"), ("214450", "파마리서치")]),
    ("유통", "인디브랜드 해외 진출 플랫폼 — 브랜드 수 증가의 수혜", [("257720", "실리콘투")]),
    ("ODM", "브랜드 다변화의 최종 수혜 — 고객이 누구든 생산은 여기서(기사: 사상 최초 분기 영업익 1,000억)", [
        ("161890", "한국콜마"), ("192820", "코스맥스"), ("241710", "코스메카코리아")]),
    ("용기", "ODM 과 동행 — 펌프·튜브 등 패키징", [("251970", "펌텍코리아")]),
]
ETFS = ["SOL 화장품TOP3플러스", "TIGER 화장품", "HANARO K-뷰티"]
ODM_PEAK = (25, 30)   # 2015 전성기 12M fwd PER 밴드(기사) · 저점 참조 10배(기사 시점)


def load(n):
    try:
        return json.loads((DB / n).read_text(encoding="utf-8"))
    except Exception:
        return None


def main():
    now = datetime.now(KST)
    pool = load("screener_pool.json") or {}
    kr = {r["c"]: r for r in pool.get("kr") or []}
    layers = []
    for name, why, lst in CHAIN:
        rows = []
        for c, n in lst:
            r = kr.get(c) or {}
            rows.append({"c": c, "n": n, "px": r.get("px"), "cap": r.get("cap"), "fper": r.get("fper"), "upside": r.get("upside"),
                         "r1m": r.get("r1m"), "r3m": r.get("r3m"), "rev": r.get("rev"), "opg_f": r.get("opg_f"),
                         "tp_trend": r.get("tp_trend"), "icr": r.get("icr"), "ocfop": r.get("ocfop"), "found": bool(r)})
        def avg(k):
            v = [x[k] for x in rows if x.get(k) is not None]
            return round(sum(v) / len(v), 3) if v else None
        layers.append({"name": name, "why": why, "rows": rows,
                       "avg": {"r1m": avg("r1m"), "r3m": avg("r3m"), "fper": avg("fper"), "upside": avg("upside"), "rev": avg("rev")}})
    # 동조화 판정 — 계층 평균 3M 수익률 격차
    r3 = {l["name"]: l["avg"]["r3m"] for l in layers if l["avg"]["r3m"] is not None}
    sync = None
    if len(r3) >= 2:
        hi = max(r3, key=r3.get); lo = min(r3, key=r3.get); gap = (r3[hi] - r3[lo]) * 100
        if gap < 15: sync = {"state": "동조", "txt": f"계층 간 3M 수익률 격차 {gap:.0f}p — 기사대로 밸류체인 전반 동조화", "gap": round(gap, 1), "hi": hi, "lo": lo}
        else: sync = {"state": "괴리", "txt": f"계층 간 3M 격차 {gap:.0f}p — {hi} 강세({r3[hi]*100:+.0f}%) vs {lo} 약세({r3[lo]*100:+.0f}%) : 동조화 깨짐, 자금이 {hi} 로 쏠림", "gap": round(gap, 1), "hi": hi, "lo": lo}
    # ODM 밸류 갭
    odm = next((l for l in layers if l["name"] == "ODM"), None)
    val = None
    if odm and odm["avg"]["fper"]:
        p = odm["avg"]["fper"]
        pos = "전성기 밴드 안" if ODM_PEAK[0] <= p <= ODM_PEAK[1] else ("전성기 상회" if p > ODM_PEAK[1] else f"전성기 하단까지 +{(ODM_PEAK[0]/p-1)*100:.0f}% 여지")
        val = {"odm_fper": round(p, 1), "peak": ODM_PEAK, "ref_low": 10, "txt": f"ODM 3사 평균 12M fwd PER {p:.1f}배 — 2015 전성기 {ODM_PEAK[0]}~{ODM_PEAK[1]}배 대비 {pos} (기사 시점 10배 초반에서 리레이팅 진행)"}
    # ETF 3종
    ep = load("etf_pool.json") or {}
    em = {e.get("n"): e for e in (ep.get("kr") or [])}
    etfs = []
    for n in ETFS:
        e = em.get(n) or {}
        etfs.append({"n": n, "c": e.get("c"), "px": e.get("px"), "r1m": e.get("r1m"), "r3m": e.get("r3m"), "r6m": e.get("r6m"), "r1y": e.get("r1y"), "asset": e.get("asset"),
                     "article_ytd": {"SOL 화장품TOP3플러스": 45.91, "TIGER 화장품": 32.81, "HANARO K-뷰티": 28.66}[n]})
    OUT.write_text(json.dumps({"as_of": now.strftime("%Y-%m-%d %H:%M"), "layers": layers, "sync": sync, "val": val, "etfs": etfs,
                               "src": "screener_pool(네이버 컨센·실적) · etf_pool · 매경LUXMEN 2026-10(전성기 PER 밴드·ETF 9/17 YTD)"},
                              ensure_ascii=False), encoding="utf-8")
    print(f"[kbc] ✅ {sync and sync['txt']} · {val and val['txt'][:40]} → {OUT}", flush=True)


if __name__ == "__main__":
    main()
