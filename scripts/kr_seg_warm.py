#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""kr_seg_warm.py — 매출 구성 패널 사전 워밍 (2026-08-09 신설 · 매일 05:30 cron).

왜
--
/api/kr_seg 는 종목당 DART 정기보고서 3건(각 4~8MB)을 내려받아 파싱한다 →
첫 조회가 수십 초. 사용자가 이 비용을 내지 않도록 새벽에 미리 만들어 둔다.

어떻게
------
localhost 엔드포인트를 그대로 호출한다(파싱 로직 이원화 방지 — 구현은 app.py 한 곳).
엔드포인트가 디스크(kr_seg_db.json)에 영구 저장하므로:
  · 이미 있고 보고서가 안 바뀐 종목 → 목록 1콜만 (몇백 ms)
  · 새 보고서가 나온 종목만 재파싱 (분기보고서 시즌에만 몰림)
대상: 시총 상위 N(기본 300) + 이미 캐시에 있는 종목(사용자가 한 번이라도 본 것).

사용: kr_seg_warm.py [--top N]
"""
import json, sys, time, urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
POOL = BASE / "data" / "db" / "screener_pool.json"
SEGDB = BASE / "data" / "db" / "kr_seg_db.json"
TOP = int(sys.argv[sys.argv.index("--top") + 1]) if "--top" in sys.argv else 300


def main():
    try:
        kr = json.loads(POOL.read_text(encoding="utf-8")).get("kr") or []
    except Exception:
        kr = []
    top = [r["c"] for r in sorted(kr, key=lambda r: -(r.get("cap") or 0))[:TOP] if r.get("c")]
    try:
        cached = list(json.loads(SEGDB.read_text(encoding="utf-8")))
    except Exception:
        cached = []
    codes = list(dict.fromkeys(top + cached))         # 순서 보존 중복 제거
    print(f"[segwarm] 대상 {len(codes)}종목 (top{TOP} + 캐시 {len(cached)})", flush=True)
    ok = err = 0
    t0 = time.time()
    for i, c in enumerate(codes):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:8000/api/kr_seg/{c}", timeout=300).read()
            ok += 1
        except Exception:
            err += 1
        if (i + 1) % 50 == 0:
            print(f"    [{i+1}/{len(codes)}] ok {ok} · err {err} · {int(time.time()-t0)}s", flush=True)
        time.sleep(0.3)                               # DART 예의(신규 파싱 시 내부에서 3콜+다운로드)
    print(f"[segwarm] 완료 ok {ok} · err {err} · {int(time.time()-t0)}s")


if __name__ == "__main__":
    main()
