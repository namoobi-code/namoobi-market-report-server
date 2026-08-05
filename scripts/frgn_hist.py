#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""frgn_hist.py — 외국인 보유비중(지분율) 일일 스냅샷 + 4주 변화 산출 (2026-08-05 신설).

'지분율 꾸준히 개선' 전략의 정식 지표: 외인모멘텀 프리셋이 쓰는 순매수 프록시를 넘어
실제 지분율(%)의 4주(20영업일) 변화율(%p)을 만든다.

동작: screener_pool.kr 의 frgn(외인보유비중 %)을 매 영업일 마감 후 스냅샷
  → data/db/frgn_hist.json {days:{YYYYMMDD:{code:frgn}}} (70일 유지)
  → 최신일 vs 20영업일 전(부족하면 가장 오래된 날, 최소 5영업일) 차이를
    data/db/frgn4w.json {asof, base, ndays, d:{code:Δ%p}} 로 산출(프론트 병합용)
cron: 20 16 * * 1-5 (장 마감·풀 확정 후)

--backfill: 네이버 종목별 '외국인·기관 순매매'(finance.naver.com/item/frgn.naver) 1페이지가
  정확히 20영업일치 '일별 외국인 보유율'을 준다(실측 005930: 07-07 46.55 → 08-04 46.63)
  → 전 종목 1회 수집으로 4주 이력을 즉시 완성(이후엔 일일 스냅샷이 이어감).
"""
import json, re, sys, time, urllib.request
from datetime import datetime, timedelta
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
HIST = BASE / "data" / "db" / "frgn_hist.json"
OUT = BASE / "data" / "db" / "frgn4w.json"

def backfill(days):
    """전 종목 네이버 frgn 1페이지(20영업일 보유율) → days 병합."""
    pool = json.loads((BASE / "data" / "db" / "screener_pool.json").read_text(encoding="utf-8"))
    codes = [r["c"] for r in pool.get("kr") or [] if r.get("c")]
    H = {"User-Agent": "Mozilla/5.0"}
    ok = 0
    for i, c in enumerate(codes):
        try:
            d = urllib.request.urlopen(urllib.request.Request(
                f"https://finance.naver.com/item/frgn.naver?code={c}", headers=H), timeout=10).read()
            try: t = d.decode("utf-8")
            except UnicodeDecodeError: t = d.decode("cp949", "ignore")
            rows = re.findall(r"(\d{4}\.\d{2}\.\d{2})</span>(.*?)</tr>", t, re.S)
            got = False
            for dt_, seg in rows:
                pcts = re.findall(r"([\d.]+)%", seg)
                if not pcts:
                    continue
                d8 = dt_.replace(".", "")
                days.setdefault(d8, {})[c] = float(pcts[-1])   # 행의 마지막 % = 보유율
                got = True
            if got: ok += 1
        except Exception:
            pass
        time.sleep(0.04)
        if i % 300 == 299:
            print(f"  {i+1}/{len(codes)} (성공 {ok})", flush=True)
    print(f"[frgn] 백필 완료 — {ok}/{len(codes)}종", flush=True)
    return days

def main():
    pool = json.loads((BASE / "data" / "db" / "screener_pool.json").read_text(encoding="utf-8"))
    snap = {r["c"]: round(float(r["frgn"]), 2) for r in pool.get("kr") or []
            if r.get("c") and r.get("frgn") is not None}
    if not snap:
        print("[frgn] 풀에 frgn 없음 — 종료")
        return
    h = {}
    try:
        h = json.loads(HIST.read_text(encoding="utf-8"))
    except Exception:
        pass
    days = h.get("days") or {}
    if "--backfill" in sys.argv:
        days = backfill(days)
    d8 = datetime.now().strftime("%Y%m%d")
    days.setdefault(d8, {}).update(snap)              # 같은 날 재실행이면 갱신(백필분 보존)
    cut = (datetime.now() - timedelta(days=70)).strftime("%Y%m%d")
    days = {d: v for d, v in days.items() if d >= cut}
    HIST.write_text(json.dumps({"asof": datetime.now().strftime("%Y-%m-%d %H:%M"), "days": days},
                               ensure_ascii=False), encoding="utf-8")
    # 4주 변화 — 20영업일 전(없으면 가장 오래된 날). 5영업일 미만이면 산출 보류
    keys = sorted(days)
    base = keys[-21] if len(keys) >= 21 else keys[0]
    if len(keys) < 5:
        OUT.write_text(json.dumps({"asof": d8, "base": base, "ndays": len(keys), "d": {}},
                                  ensure_ascii=False), encoding="utf-8")
        print(f"[frgn] 스냅샷 {len(snap)}종 저장 · 이력 {len(keys)}일 — 5일 미만이라 Δ 보류")
        return
    old = days[base]
    delta = {c: round(v - old[c], 2) for c, v in days[keys[-1]].items() if c in old}
    OUT.write_text(json.dumps({"asof": d8, "base": base, "ndays": len(keys), "d": delta},
                              ensure_ascii=False), encoding="utf-8")
    up = sum(1 for v in delta.values() if v > 0)
    print(f"[frgn] ✅ 스냅샷 {len(snap)}종 · 이력 {len(keys)}일 · Δ({base}→{keys[-1]}) {len(delta)}종 (상승 {up})")

if __name__ == "__main__":
    main()
