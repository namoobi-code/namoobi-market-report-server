#!/usr/bin/env python3
"""fetch_celltrion.py — 셀트리온 탭 라이브 블록 갱신 (2026-09-20 신설)

구조
----
data/db/celltrion.json 은 두 층이다.
  ① 큐레이션 층(quarters·annual·products·shares·watch·log) — 회사 공시·IR·증권사 추정을
     출처와 함께 적은 것. **사람/LLM 이 주 1회 갱신**(Cowork 예약 celltrion-weekly).
     회사가 제품별 매출을 공표하지 않으므로 API 로 자동화할 수 없다.
  ② live 층 — 시세·컨센·리비전·수급처럼 이미 매일 서버가 모으는 것을 풀에서 꺼내 붙인다.
     이 스크립트는 **live 만** 다시 쓴다. ①은 건드리지 않는다(주간 갱신과 충돌 방지).

크론: 매일 09:05 / 17:05 (screener_pool·earnings_join 뒤).
"""
import json
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DB = BASE / "data" / "db"
OUT = DB / "celltrion.json"
CODE = "068270"

LIVE_KEYS = ["px", "chg", "mcap", "per", "fper", "pbr", "tp", "upside", "rec", "recn",
             "cr30", "cr90", "tprv", "tprv90", "tpn", "tpu", "tpd",
             "opg", "opg_f", "revg", "revg_f", "gacc", "qup", "yup",
             "rsi", "vs200", "align", "mom", "r1m", "r3m", "r6m", "r1y",
             "frgn", "inst", "fnb20", "onb20", "sr", "lbr", "spr", "edl", "z_grw", "z_mom", "z_qly", "z_val"]


def main():
    d = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    live = {"as_of": datetime.now().strftime("%Y-%m-%d %H:%M")}
    try:
        pool = json.loads((DB / "screener_pool.json").read_text(encoding="utf-8"))
        row = next((r for r in pool.get("kr") or [] if r.get("c") == CODE), None)
        if row:
            live["pool"] = {k: row.get(k) for k in LIVE_KEYS}
            live["price_date"] = pool.get("price_date")
    except Exception as e:
        live["pool_err"] = repr(e)[:80]
    try:
        cons = json.loads((DB / "kr_consensus.json").read_text(encoding="utf-8"))
        cc = (cons.get("r") or {}).get(CODE)
        if cc:
            live["cons"] = cc
            live["cons_asof"] = cons.get("asof")
    except Exception as e:
        live["cons_err"] = repr(e)[:80]
    # 실적 발표 감지 이력(earnings_live) — 최근 발표일·서프라이즈
    try:
        ev = json.loads((DB / "earnings_live.json").read_text(encoding="utf-8"))
        hits = []
        for d8 in sorted(ev.get("days") or {}):
            for it in ev["days"][d8]:
                if it.get("c") == CODE:
                    hits.append({"d": d8, **{k: it.get(k) for k in ("spr", "spr_s", "cons_op", "op", "r1", "r5", "r20")}})
        live["earn"] = hits[-4:]
    except Exception:
        pass
    d["live"] = live
    d.setdefault("as_of", datetime.now().strftime("%Y-%m-%d"))
    OUT.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    p = live.get("pool") or {}
    print(f"[celltrion] live 갱신 · px {p.get('px')} · cr30 {p.get('cr30')} · tp {p.get('tp')} · 분기 {len(d.get('quarters') or [])}개")


if __name__ == "__main__":
    main()
