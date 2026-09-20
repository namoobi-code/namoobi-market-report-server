#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""rerank.py — 아파트 매매가격지수 · 전국 236개 지역 월별 (한국부동산원 R-ONE)

용도: '부동산시황' 탭 — 기간을 골라 상승률이 높은 지역부터 줄 세운다.
      동아일보 그래픽(2025.06~2026.08 수도권 TOP10) 을 실측으로 재현했다:
      분당 29.86 · 성동 21.14 · 수지 20.80 · 동안 20.67 · 영등포 18.21 · 송파 17.56 (정확히 일치)

통계표: R-ONE A_2024_00045 "(월) 매매가격지수_아파트" · 2003~ · 시점 하나씩 조회.
        한 시점에 236행(전국·권역·시도·시군구가 섞여 있다) — pSize=1000 으로 한 번에 받는다.
        메타의 DATA_END_YY 는 낡은 값이라 믿지 말고 실제로 찔러본다(실측: 2024 라 적혀 있으나 2026.08 까지 옴).

계층 처리: CLS_FULLNM 이 '경기>경부1권>성남시>분당구' 식 경로다. 어떤 경로가 다른 경로의
          접두어면 상위 집계(성남시·경부1권)다. 순위표는 **말단(leaf)만** 세우고, 상위는 따로 표시한다.

산출: data/db/rerank.json
  {asof, src, t:[YYYYMM], regions:{full:{short, sido, leaf}}, idx:{full:[값|null]}}

사용: rerank.py [--full]   (--full 2003.11부터 · 기본 최근 6개월 갱신 후 이전 파일과 병합)
cron: 50 7 * * *
"""
import json, socket, sys, time, urllib.request
from datetime import datetime
from pathlib import Path

socket.setdefaulttimeout(45)
BASE = Path(__file__).resolve().parent.parent
DB   = BASE / "data" / "db"
OUT  = DB / "rerank.json"
FULL = "--full" in sys.argv
NOW  = datetime.now()
API  = "https://www.reb.or.kr/r-one/openapi/SttsApiTblData.do"
TBL  = "A_2024_00045"


def _key():
    for p in [BASE / "keys" / "reb.txt", Path("D:/claudeCowork/SECURITY/reb.or.kr.txt")] + \
             sorted(Path("/sessions").glob("*/mnt/claudeCowork/SECURITY/reb.or.kr.txt")):
        try:
            k = Path(p).read_text(encoding="utf-8").strip()
            if k:
                return k
        except Exception:
            pass
    raise SystemExit("R-ONE 키 없음 — keys/reb.txt")


KEY = _key()


def fetch(ym):
    """{full_name: 값} — 그 달 전 지역."""
    u = (f"{API}?STATBL_ID={TBL}&DTACYCLE_CD=MM&WRTTIME_IDTFR_ID={ym}"
         f"&Type=json&pIndex=1&pSize=1000&KEY={KEY}")
    for k in range(3):
        try:
            d = json.load(urllib.request.urlopen(
                urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"}), timeout=40))
            rows = []
            for v in d.values():
                if isinstance(v, list):
                    for e in v:
                        if isinstance(e, dict) and "row" in e:
                            rows = e["row"]
            out = {}
            for r in rows:
                fn = str(r.get("CLS_FULLNM") or "").strip()
                try:
                    out[fn] = round(float(r.get("DTA_VAL")), 3)
                except Exception:
                    pass
            return out
        except Exception as e:
            if k == 2:
                print(f"    ⚠ {ym} 실패: {e}")
                return {}
            time.sleep(3)
    return {}


def months(y0, m0):
    y, m = y0, m0
    while (y, m) <= (NOW.year, NOW.month):
        yield f"{y}{m:02d}"
        m += 1
        if m > 12:
            y, m = y + 1, 1


def main():
    if FULL:
        ms = list(months(2003, 11))
    else:
        y, m = NOW.year, NOW.month - 6
        while m <= 0:
            y, m = y - 1, m + 12
        ms = list(months(y, m))
    print(f"rerank: {ms[0]}~{ms[-1]} {len(ms)}개월 {'(전체)' if FULL else '(최근 6개월 갱신)'}")

    data = {}                                    # {ym: {full: v}}
    miss = 0
    for ym in ms:
        r = fetch(ym)
        if r:
            data[ym] = r
        else:
            miss += 1
        time.sleep(0.25)
    print(f"  받은 달 {len(data)} · 빈 달 {miss}")
    if not data:
        raise SystemExit("✗ 수집 0")

    # 이전 파일과 병합 — 최근 6개월만 새로 받으므로 과거는 파일에서 가져온다
    old = {}
    if OUT.exists() and not FULL:
        try:
            old = json.loads(OUT.read_text(encoding="utf-8"))
        except Exception:
            old = {}
    ot, oi = old.get("t") or [], old.get("idx") or {}
    merged = {}                                  # {full: {ym: v}}
    for fn, arr in oi.items():
        merged[fn] = {ot[i]: arr[i] for i in range(min(len(ot), len(arr))) if arr[i] is not None}
    for ym, mp in data.items():
        for fn, v in mp.items():
            merged.setdefault(fn, {})[ym] = v

    ts = sorted({ym for mp in merged.values() for ym in mp})
    names = sorted(merged)
    # 계층: 다른 경로의 접두어면 상위 집계
    regions = {}
    for fn in names:
        leaf = not any(o != fn and o.startswith(fn + ">") for o in names)
        parts = fn.split(">")
        regions[fn] = {"short": parts[-1], "sido": parts[0], "leaf": leaf, "depth": len(parts)}

    out = {
        "asof": NOW.strftime("%Y-%m-%d %H:%M"),
        "src": "한국부동산원 R-ONE · (월) 매매가격지수_아파트 (A_2024_00045)",
        "note": "기준시점=100 인 지수. 두 시점의 비율로 상승률을 계산한다. 최근 1~2개월은 잠정치.",
        "t": ts,
        "regions": regions,
        "idx": {fn: [merged[fn].get(t) for t in ts] for fn in names},
    }
    DB.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    leafs = sum(1 for r in regions.values() if r["leaf"])
    print(f"  → {OUT} ({OUT.stat().st_size // 1024}KB) · {ts[0]}~{ts[-1]} · 지역 {len(names)} (말단 {leafs})")


if __name__ == "__main__":
    main()
