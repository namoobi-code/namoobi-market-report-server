#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ipju.py — 공동주택 입주예정물량 (한국부동산원·부동산114 공동 추정 · 향후 2년) (2026-10-17 신설)

왜: 고준석 인터뷰(한경머니 2026.10) "서울 입주 2025 4.7만 → 2026 2.4만 → 2027 1.8만 → 2028 1.5만".
    우리 착공 차트(2023년 -49%)가 입주 급감으로 이어지는지 단지 단위로 확인하려고 붙인다.

소스: data.go.kr 15111714 '한국부동산원_주택공급정보_입주예정물량정보' (odcloud · 2026-10-17 활용신청 승인)
  https://api.odcloud.kr/api/15111714/v1/uddi:0b257760-ac19-4841-adb4-b38b4d153397
  컬럼: 입주예정월(YYYY-MM, 미정 '00') · 지역(시도) · 사업유형(분양/임대) · 주소 · 아파트명 · 세대수
  범위: 30세대 이상 공동주택 · 기준시점 반기(현재 2026.06말 → 2026.07~2028.06, 703건) · 반기 갱신(차기 2027-02)
  ⚠ 기사·부동산114 수치(아파트만)와 다르다 — 이 자료는 임대·도시형생활주택까지 포함(서울 2027 = 22,428 vs 기사 1.8만).

산출: data/db/ipju.json
  {asof, src, base(기준시점 추정), months[YYYY-MM], sido{시도:{월:세대}}, sgg{시도 시군구:{월:세대}},
   items[{ym, reg, sgg, kind, addr, name, n}]}
  시군구: 서울·광역시는 '구', 도는 '시·군'(성남시 처럼 — 분당/수정/중원 구는 sgg2 에 따로).

cron: 5 8 * * 1 (주 1회 — 자료가 반기 갱신이라 그 이상은 의미 없음)
"""
import json, re, time, urllib.request
from collections import defaultdict
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "data" / "db" / "ipju.json"
URL = "https://api.odcloud.kr/api/15111714/v1/uddi:0b257760-ac19-4841-adb4-b38b4d153397"


def _key():
    for p in (BASE / "keys" / "data.go.kr.txt", BASE.parent / "SECURITY" / "data.go.kr.txt"):
        if p.exists():
            return p.read_text().strip()
    raise SystemExit("data.go.kr 키 없음")


def fetch():
    rows, page = [], 1
    while True:
        u = f"{URL}?page={page}&perPage=1000&serviceKey={_key()}"
        d = json.loads(urllib.request.urlopen(u, timeout=60).read())
        if "data" not in d:
            raise SystemExit(f"✗ {d}")
        rows += d["data"]
        if len(rows) >= (d.get("matchCount") or d.get("totalCount") or 0) or not d["data"]:
            return rows
        page += 1
        time.sleep(0.3)


def parse_sgg(addr):
    """'경기도 성남시 분당구 …' → ('성남시','분당구') · '서울특별시 강북구 …' → ('강북구', None)"""
    t = (addr or "").split()
    if len(t) < 2:
        return None, None
    a = t[1]
    b = t[2] if len(t) > 2 and t[2].endswith("구") and a.endswith("시") else None
    return (a if a.endswith(("시", "군", "구")) else None), b


def main():
    rows = fetch()
    print(f"[ipju] {len(rows)}건")
    items, sido, sgg = [], defaultdict(lambda: defaultdict(int)), defaultdict(lambda: defaultdict(int))
    for r in rows:
        ym = str(r.get("입주예정월") or "")
        if not re.match(r"\d{4}-\d{2}", ym):
            ym = ym[:4] + "-00" if ym[:4].isdigit() else "미정"
        reg = str(r.get("지역") or "").strip()
        n = int(float(r.get("세대수") or 0))
        a, b = parse_sgg(r.get("주소"))
        it = {"ym": ym, "reg": reg, "sgg": a, "sgg2": b, "kind": r.get("사업유형"),
              "addr": r.get("주소"), "name": r.get("아파트명"), "n": n}
        items.append({k: v for k, v in it.items() if v not in (None, "")})
        sido[reg][ym] += n
        sido["전국"][ym] += n
        if a:
            sgg[f"{reg} {a}"][ym] += n
            if b:
                sgg[f"{reg} {a} {b}"][ym] += n
    months = sorted({m for m in sido["전국"] if re.match(r"\d{4}-\d{2}$", m) and not m.endswith("-00")})
    items.sort(key=lambda x: (x["ym"], x["reg"], -x["n"]))
    out = {
        "asof": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "src": "한국부동산원·부동산114 공동주택 입주예정물량 (data.go.kr 15111714) · 반기 갱신",
        "base": f"{months[0]} ~ {months[-1]}" if months else "",
        "note": ("30세대 이상 공동주택(임대·도시형생활주택 포함) 추정치 — 아파트만 집계한 언론·부동산114 수치보다 크다. "
                 "기준시점 이후 일정 변경·후분양은 미반영. 입주월 미정은 '00'."),
        "months": months,
        "sido": {k: dict(v) for k, v in sido.items()},
        "sgg": {k: dict(v) for k, v in sgg.items()},
        "items": items,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    s = sido["서울"]
    print(f"  → {OUT} ({OUT.stat().st_size // 1024}KB) · {out['base']} · 서울 "
          + " · ".join(f"{y} {sum(v for m, v in s.items() if m.startswith(y)):,}" for y in ("2026", "2027", "2028")))


if __name__ == "__main__":
    main()
