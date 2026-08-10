#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""guidance_backfill.py — 과거 실적 8-K 의 가이던스를 소급 파싱 (2026-08-09 신설).

earnings_8k_watch.py 는 **새로 접수되는** 8-K 만 본다. 그래서 가이던스 갭 필드는
파서를 붙인 시점 이후 발표분에만 채워져, 스크리너에서 '가이던스 갭' 필터가 전부 0건이 된다.

이 스크립트는 EDGAR submissions 를 종목별로 훑어 **최근 실적(Item 2.02) 8-K** 를 찾고,
Exhibit 99.1 보도자료에서 가이던스를 뽑아 earnings_live_us.json 에 채워 넣는다.
파서 자체는 earnings_8k_watch 의 것을 그대로 재사용한다(로직 이원화 방지).

대상: earnings_live_us.json 의 최근 N일 항목 중 g_rev_gap 이 비어 있는 종목
사용: guidance_backfill.py [--days 45] [--workers 4] [--limit N]
      SEC 는 초당 10건 권고 → workers 4 + 0.15s 대기로 여유 있게 둔다.
"""
import json, sys, time, urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from earnings_8k_watch import cik_map, exhibit_text, parse_guidance, guidance_gap

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "data" / "db" / "earnings_live_us.json"
POOL = BASE / "data" / "db" / "screener_pool.json"
H = {"User-Agent": "namoobi research namoobi@gmail.com"}
ARG = lambda k, d: (int(sys.argv[sys.argv.index(k) + 1]) if k in sys.argv else d)
DAYS, WORKERS, LIMIT = ARG("--days", 45), ARG("--workers", 4), ARG("--limit", 0)
# (2026-08-10) --force = 이미 값이 있는 항목도 다시 파싱한다.
# 기본 동작은 '비어 있는 것만'이라, 파서를 고쳐도 **이미 잘못 채워진 값은 그대로 남는다**
# (실측 AMGN GAAP EPS 오채택 · ABT 연간을 분기로 분류 → 고쳐도 화면은 옛 값). 파서를
# 수정한 뒤에는 --force 로 전체를 다시 돌려야 수정이 실제로 반영된다.
FORCE = "--force" in sys.argv


def recent_earn_8k(cik):
    """해당 CIK 의 가장 최근 실적(Item 2.02) 8-K 접수번호."""
    try:
        j = json.loads(urllib.request.urlopen(urllib.request.Request(
            f"https://data.sec.gov/submissions/CIK{int(cik):010d}.json", headers=H), timeout=25).read())
    except Exception:
        return None
    r = j.get("filings", {}).get("recent", {})
    forms, items, accs = r.get("form", []), r.get("items", []), r.get("accessionNumber", [])
    for i in range(len(accs)):
        if forms[i] in ("8-K", "6-K") and "2.02" in (items[i] if i < len(items) else "" or ""):
            return accs[i]
    return None


def main():
    live = json.loads(OUT.read_text(encoding="utf-8"))
    pool_us = {r["c"]: r for r in json.loads(POOL.read_text(encoding="utf-8")).get("us") or []}
    cut = (datetime.now() - timedelta(days=DAYS)).strftime("%Y%m%d")
    todo = {}
    for d8 in sorted(live.get("days") or {}):
        if d8 < cut:
            continue
        for it in live["days"][d8]:
            c = it.get("c")
            # 이미 갭이 있거나, 컨센서스(rq1·eq1)가 없어 비교 자체가 불가능하면 건너뛴다
            if not c:
                continue
            if not FORCE and (it.get("g_rev_gap") is not None or it.get("g_eps_gap") is not None):
                continue
            if FORCE:
                # 재파싱 전에 옛 값을 지운다 — 안 지우면 이번에 기각된 항목(오파싱이라
                # 걸러낸 것)이 옛 값 그대로 남아 "고쳤는데 화면은 그대로"가 된다.
                for k in ("g_rev", "g_rev_gap", "g_rev_per", "g_rev_ev",
                          "g_eps", "g_eps_gap", "g_eps_per", "g_eps_ev", "g_per"):
                    it.pop(k, None)
            r = pool_us.get(c) or {}
            if r.get("rq1") is None and r.get("eq1") is None:
                continue
            it["_d8"] = d8                                # 발표일 보관(기준 분기 판정)
            todo[c] = it
    syms = list(todo)
    if LIMIT:
        syms = syms[:LIMIT]
    mp = cik_map()
    print(f"[gbf] 대상 {len(syms)}종목 (최근 {DAYS}일 · 컨센 보유분)", flush=True)

    def one(sym):
        cik = mp.get(sym.upper())
        if not cik:
            return sym, {}
        # 이미 접수번호를 아는 항목은 EDGAR 조회를 건너뛴다(호출 절약)
        acc = (todo[sym].get("acc")) or recent_earn_8k(cik)
        if not acc:
            return sym, {}
        time.sleep(0.15)
        try:
            g = parse_guidance(exhibit_text(cik, acc))
            d8 = todo[sym].get("_d8")                    # 그 항목의 발표일(기준 분기 판정용)
            ann = f"{d8[:4]}-{d8[4:6]}-{d8[6:8]}" if d8 else None
            return sym, guidance_gap(sym, g, pool_us, ann)
        except Exception:
            return sym, {}

    got = 0
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        for i, (sym, gap) in enumerate(ex.map(one, syms)):
            if gap:
                todo[sym].update(gap); got += 1
            if (i + 1) % 100 == 0:
                live["asof"] = datetime.now().strftime("%Y-%m-%d %H:%M")
                OUT.write_text(json.dumps(live, ensure_ascii=False), encoding="utf-8")
                print(f"    [{i+1}/{len(syms)}] 가이던스 확보 {got}", flush=True)
    live["asof"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    OUT.write_text(json.dumps(live, ensure_ascii=False), encoding="utf-8")
    print(f"[gbf] 완료 — 가이던스 갭 {got}/{len(syms)}종목 채움")


if __name__ == "__main__":
    main()
