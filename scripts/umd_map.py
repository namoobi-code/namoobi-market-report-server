#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""umd_map.py — 법정동(읍면동) → 실거래 시군구 매핑표 (2026-08-08 신설 · 주 1회 cron).

왜 필요한가
-----------
소스마다 '시군구'를 다르게 쪼갠다.
  · 실거래(RTMS) : 화성을 41593 봉담권 / 41595 병점권 / 41597 동탄 으로 3분할
  · 청약홈 주소  : "경기도 화성시 효행구 …" (2026 일반구 분화 반영)
그대로 두면 같은 화성인데 실거래는 3개, 청약은 1~2개로 나와 비교가 안 된다.

해결: **실거래 응답에 들어있는 umdNm(법정동)** 을 시군구 코드별로 모아 역매핑표를 만들고,
      다른 소스(청약 등)는 주소의 읍면동으로 이 표를 조회해 실거래와 같은 시군구명을 쓴다.
      → 전 소스가 하나의 지역 체계로 통일된다.

산출: data/db/umd_map.json  {"비봉면":"화성 봉담권", "반송동":"화성 동탄", ...}
      동명이인(같은 이름 다른 시군구)은 시도까지 붙인 키도 함께 넣는다.
사용: umd_map.py [--months N]   (기본 2개월치 — 법정동은 잘 안 변해 자주 돌 필요 없다)
"""
import json, sys, time, urllib.request
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rtms import REGIONS, SIDO

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "data" / "db" / "umd_map.json"
KEY = (BASE / "keys" / "data.go.kr.txt").read_text().strip()
MONTHS = int(sys.argv[sys.argv.index("--months") + 1]) if "--months" in sys.argv else 2


def yms(n):
    y, m, out = datetime.now().year, datetime.now().month, []
    for _ in range(n + 1):
        m -= 1
        if m == 0:
            y -= 1; m = 12
        out.append(f"{y}{m:02d}")
    return out


def fetch(lawd, ym):
    """전월세가 매매보다 건수가 많아 법정동 커버리지가 좋다."""
    u = ("https://apis.data.go.kr/1613000/RTMSDataSvcAptRent/getRTMSDataSvcAptRent"
         f"?serviceKey={KEY}&LAWD_CD={lawd}&DEAL_YMD={ym}&numOfRows=1000&pageNo=1")
    for k in range(3):
        try:
            root = ET.fromstring(urllib.request.urlopen(u, timeout=30).read())
            return [(it.findtext("umdNm") or "").strip() for it in root.findall(".//item")]
        except Exception:
            if k == 2:
                return []
            time.sleep(4 * (k + 1))
    return []


def main():
    per = defaultdict(Counter)                       # 법정동 → {시군구명: 건수}
    months = yms(MONTHS)
    for i, (code, name) in enumerate(REGIONS.items()):
        got = set()
        for ym in months:
            for u in fetch(code, ym):
                if u:
                    got.add(u)
            time.sleep(0.35)
        for u in got:
            per[u][name] += 1
        if (i + 1) % 40 == 0:
            print(f"  [{i+1}/{len(REGIONS)}] 법정동 {len(per):,}개", flush=True)

    # 동명이인 처리 — 같은 법정동명이 여러 시군구에 있으면 단독 키는 만들지 않고
    # '시도 읍면동' 키만 남긴다(잘못된 매핑이 조용히 섞이는 게 최악).
    plain, withsd, dup = {}, {}, []
    pre = {v: k[:2] for k, v in REGIONS.items()}
    for u, c in per.items():
        names = list(c)
        for n in names:
            withsd[f"{SIDO.get(pre.get(n,''),'')} {u}"] = n
        if len(names) == 1:
            plain[u] = names[0]
        else:
            dup.append(u)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "asof": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "src": "국토부 아파트 전월세 실거래 응답의 umdNm 집계",
        "note": "법정동 → 실거래 시군구명. 동명이인은 '시도 읍면동' 키로만 제공",
        "map": plain, "map_sd": withsd, "dup": sorted(dup)},
        ensure_ascii=False), encoding="utf-8")
    print(f"[umd] ✅ 법정동 {len(per):,}개 · 단독 {len(plain):,} · 시도병기 {len(withsd):,} · 중복명 {len(dup)}")
    hs = {u: n for u, n in plain.items() if "화성" in n}
    print(f"[umd]    화성 매핑 {len(hs)}개 예시: {dict(list(hs.items())[:5])}")
    print(f"[umd] → {OUT}")


if __name__ == "__main__":
    main()
