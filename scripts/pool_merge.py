#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pool_merge.py — screener_pool 안전 저장 (2026-08-10 신설).

왜 필요한가 (실측 사고)
-----------------------
장중 스크립트(intraday_kr/us)는 풀을 통째로 읽어 시세만 갱신하고 통째로 다시 쓴다.
그런데 이 스크립트는 수 분간 돌기 때문에, 그 사이에 다른 수집기(us_consensus·
earnings_join·zacks_spr…)가 써 넣은 값이 **오래된 사본으로 덮여 사라진다.**
  실측 2026-08-10: us_consensus 가 전 종목에 채운 eq0/rq0/ry0/ey0 가 40건만 남고 소실
                   → 가이던스 비교 기준 분기가 전부 '+1q' 폴백으로 밀려 갭이 엉망이 됨
                   (EPS 갭 중앙값 43%, 최대 2954% — 값 자체가 아니라 기준이 틀린 것)
  실측 같은 날: earnings_join 이 정리한 가이던스 필드가 몇 분 뒤 옛 값으로 되돌아옴

해결: **덮어쓰지 말고 병합한다.** 저장 직전에 디스크의 최신본을 다시 읽어,
이 프로세스가 실제로 건드린 필드만 덮어씌운다. 나머지 필드는 디스크 값을 그대로 둔다.
"""
import json, os
from pathlib import Path

DB = Path(__file__).resolve().parent.parent / "data" / "db"
POOL = DB / "screener_pool.json"


def save_pool_merged(pool, own_fields, mkts=("kr", "us"), extra_meta=()):
    """pool(메모리) 중 own_fields 만 디스크 최신본에 반영해 저장.

    pool       : 이 프로세스가 수정한 풀(dict)
    own_fields : 이 프로세스가 책임지는 종목 필드 집합(예: 시세·지표)
    extra_meta : 최상위 메타 키(예: 'live_at') — 이것도 함께 반영
    """
    try:
        disk = json.loads(POOL.read_text(encoding="utf-8"))
    except Exception:
        disk = None
    if not disk:                                    # 디스크가 깨졌으면 통째로 저장(최후수단)
        disk = pool
    else:
        for mk in mkts:
            by = {r.get("c"): r for r in (disk.get(mk) or []) if r.get("c")}
            for r in pool.get(mk) or []:
                d = by.get(r.get("c"))
                if d is None:                       # 신규 종목은 통째로 추가
                    disk.setdefault(mk, []).append(r)
                    continue
                for k in own_fields:
                    if k in r:
                        d[k] = r[k]
                    elif k in d:
                        d.pop(k, None)
        for k in extra_meta:
            if k in pool:
                disk[k] = pool[k]
            else:
                disk.pop(k, None)
    tmp = str(POOL) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(disk, f, ensure_ascii=False)
    os.replace(tmp, POOL)
    return disk
