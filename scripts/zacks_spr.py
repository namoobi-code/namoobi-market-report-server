#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""zacks_spr.py — US '직전실적 매출컨센 서프라이즈'(sspr) 벌크 수집 (2026-08-10 신설).

왜 Zacks 인가
-------------
야후는 과거 매출 컨센을 안 주고(어닝 캘린더 API 에 revenue 필드 넣으면 400 — 실측),
Zacks earnings-announcements 페이지의 내장 obj_data JSON(sales_table)이 발표일·회계분기·
컨센·실제 쌍을 ~17년치 준다. 종목 상세 패널(us_fin)이 같은 소스를 쓰므로
스크리너 필터 값과 상세 화면 값이 어긋나지 않는다(값·판정 모두 같은 정의).

수집 규칙
---------
· sales_table 최신 행 중 컨센·실제가 **둘 다** 있는 첫 행(발표 완료 분기)
  → sspr = (실제-컨센)/|컨센| ×100 · ssprD = 발표일(YYYYMMDD)
· 컨센이 '--' 뿐인 종목(은행 등 매출 추정 애널 없음 — 실측 MUFG)은 값 없음(정직한 공란)
· 기본 실행: 최근 --days(기본 10)일 내 실적 발표가 감지된 종목(earnings_live_us)만
  → 하루 수십 건 수준. --all 은 전 종목 백필(최초 1회 · ~40분).

사용: zacks_spr.py [--all] [--days 10] [--workers 3] [--limit N]
cron: 매일 08:20 (us_consensus 08:00 뒤)
"""
import json, re, sys, time, urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
POOL = BASE / "data" / "db" / "screener_pool.json"
LIVE = BASE / "data" / "db" / "earnings_live_us.json"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36"}
ARG = lambda k, d: (int(sys.argv[sys.argv.index(k) + 1]) if k in sys.argv else d)
ALL, DAYS, WORKERS, LIMIT = ("--all" in sys.argv), ARG("--days", 10), ARG("--workers", 3), ARG("--limit", 0)


def fetch(sym):
    """Zacks sales_table 최신 발표 행 → (sspr%, 발표일 YYYYMMDD) 또는 None."""
    try:
        h = urllib.request.urlopen(urllib.request.Request(
            f"https://www.zacks.com/stock/research/{sym.upper()}/earnings-announcements",
            headers=UA), timeout=25).read().decode("utf-8", "ignore")
        m = re.search(r"obj_data\s*=\s*(\{.*?\});", h, re.S)
        if not m:
            return None
        rows = (json.loads(m.group(1)).get("earnings_announcements_sales_table") or [])
        clean = lambda s: re.sub(r"<[^>]+>", "", s or "").strip()

        def val(s):
            t = clean(s).replace("$", "").replace(",", "")
            try:
                return float(t)
            except Exception:
                return None
        for r in rows:                       # 최신순 — 컨센·실제 쌍이 있는 첫 행
            if len(r) < 4:
                continue
            vE, vA = val(r[2]), val(r[3])
            if vE is None or vA is None or vE == 0:
                continue
            m2 = re.match(r"(\d{1,2})/(\d{1,2})/(\d{2,4})", clean(r[0]))
            d8 = None
            if m2:
                y = int(m2.group(3)); y += 2000 if y < 100 else 0
                d8 = f"{y:04d}{int(m2.group(1)):02d}{int(m2.group(2)):02d}"
            return round((vA - vE) / abs(vE) * 100, 1), d8
    except Exception:
        pass
    return None


def main():
    pool = json.loads(POOL.read_text(encoding="utf-8"))
    us = pool.get("us") or []
    by = {r.get("c"): r for r in us if r.get("c")}
    if ALL:
        syms = [c for c in by]
    else:
        # 최근 발표 감지 종목 + 아직 값이 없는 종목(신규 상장 등)만
        cut = (datetime.now() - timedelta(days=DAYS)).strftime("%Y%m%d")
        syms = set()
        try:
            lv = json.loads(LIVE.read_text(encoding="utf-8"))
            for d8 in sorted(lv.get("days") or {}):
                if d8 >= cut:
                    for it in lv["days"][d8]:
                        if it.get("c") in by:
                            syms.add(it["c"])
        except Exception:
            pass
        syms = sorted(syms)
    if LIMIT:
        syms = syms[:LIMIT]
    print(f"[zspr] 대상 {len(syms)}종목 (all={ALL})", flush=True)

    done = [0]

    def one(sym):
        time.sleep(0.25)
        r = fetch(sym)
        return sym, r

    got = 0
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        for i, (sym, r) in enumerate(ex.map(one, syms)):
            if r:
                by[sym]["sspr"] = r[0]
                if r[1]:
                    by[sym]["ssprD"] = r[1]
                got += 1
            if (i + 1) % 300 == 0:           # 중간 저장 — 백필 도중 끊겨도 이어감
                pool["zspr_asof"] = datetime.now().strftime("%Y-%m-%d %H:%M")
                POOL.write_text(json.dumps(pool, ensure_ascii=False), encoding="utf-8")
                print(f"    [{i+1}/{len(syms)}] 확보 {got}", flush=True)
    pool["zspr_asof"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    POOL.write_text(json.dumps(pool, ensure_ascii=False), encoding="utf-8")
    print(f"[zspr] 완료 — sspr {got}/{len(syms)} · 풀 보유 {sum(1 for r in us if r.get('sspr') is not None)}")


if __name__ == "__main__":
    main()
