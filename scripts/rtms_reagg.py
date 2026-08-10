#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""rtms_reagg.py — rtms.json 의 합산 계열(A*)만 다시 계산한다 (2026-08-10 신설).

rtms.py 는 246개 시군구를 국토부 API 로 훑는 데 오래 걸린다. 합산 로직만 바뀐 경우
(예: '전국 전체(AKR)' 추가) 전체 수집을 다시 돌릴 이유가 없다.
이미 저장된 시군구 시계열을 그대로 읽어 합산 계열만 갈아 끼운다.

사용: python3 scripts/rtms_reagg.py
"""
import json
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "data" / "db" / "rtms.json"
SIDO = {"11": "서울", "26": "부산", "27": "대구", "28": "인천", "30": "대전", "31": "울산",
        "36": "세종", "41": "경기", "51": "강원", "43": "충북", "44": "충남", "52": "전북",
        "46": "전남", "47": "경북", "48": "경남", "50": "제주"}


def agg(src, codes, price_key):
    """rtms.py 의 agg_region 과 동일 — 거래건수 가중 평균, 가중 중위(근사)."""
    allm = sorted({t for c in codes for t in (src.get(c) or {}).get("m", {})})
    out = {}
    for t in allm:
        rs = [src[c]["m"][t] for c in codes
              if (src.get(c) or {}).get("m", {}).get(t) and src[c]["m"][t].get("n")]
        if not rs:
            continue
        n = sum(x["n"] for x in rs)
        if not n:
            continue
        if price_key == "avg":
            pairs = sorted((x["med"], x["n"]) for x in rs if x.get("med") is not None)
            med = None
            if pairs:
                half = sum(w for _, w in pairs) / 2
                acc = 0
                for v, w in pairs:
                    acc += w
                    if acc >= half:
                        med = v
                        break
            vs = [x for x in rs if x.get("avg") is not None]
            nv = sum(x["n"] for x in vs) or 1
            out[t] = {"n": n,
                      "avg": round(sum(x["avg"] * x["n"] for x in vs) / nv, 2) if vs else None,
                      "med": round(med, 2) if med is not None else None}
        else:
            vs = [x for x in rs if x.get("dep") is not None]
            nv = sum(x["n"] for x in vs) or 1
            out[t] = {"n": n,
                      "dep": round(sum(x["dep"] * x["n"] for x in vs) / nv, 2) if vs else None}
    return out


def main():
    d = json.loads(OUT.read_text(encoding="utf-8"))
    sale, rent, names = d["sale"], d["rent"], d["names"]
    regs = [c for c in names if not str(c).startswith("A")]
    print(f"시군구 {len(regs)}개")

    for pfx, snm in SIDO.items():
        codes = [c for c in regs if c.startswith(pfx)]
        if len(codes) < 2:
            continue
        k = "A" + pfx
        sale[k] = {"m": agg(sale, codes, "avg")}
        rent[k] = {"m": agg(rent, codes, "dep")}
        names[k] = f"{snm} 전체({len(codes)})"

    sale["AKR"] = {"m": agg(sale, regs, "avg")}
    rent["AKR"] = {"m": agg(rent, regs, "dep")}
    names["AKR"] = f"전국 전체({len(regs)})"

    d["reagg"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    OUT.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    m = sale["AKR"]["m"]
    ks = sorted(m)[-4:]
    print(f"  AKR {len(m)}개월 · 최근: " + " · ".join(f"{t} {m[t]['n']:,}건/{m[t]['avg']}억" for t in ks))
    print(f"  → {OUT} ({OUT.stat().st_size // 1024}KB)")


if __name__ == "__main__":
    main()
