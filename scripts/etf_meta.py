#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""etf_meta.py — KR ETF 상장일 메타 (2026-08-06 신설 · 주 1회).

krxbase 캐시(주식 전용)에 ETF 가 없어 상장기간이 전부 null 이던 버그의 정공 수정:
finance.naver 종목 메인의 '상장일' 행을 전 ETF 1회씩 파싱(실측: "2023년 06월 20일").
월배당(md)은 신뢰 소스 미확보(이름 무효·wisereport 렌더전용) — 확보 시 이 파일에 추가 예정.
산출: data/db/etf_meta.json {asof, d:{code:{yr}}}
cron: 20 8 * * 0
"""
import json, re, time, urllib.request
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "data" / "db" / "etf_meta.json"
H = {"User-Agent": "Mozilla/5.0"}

def main():
    pool = json.loads((BASE / "data" / "db" / "etf_pool.json").read_text(encoding="utf-8"))
    codes = [r["c"] for r in pool.get("kr") or [] if r.get("c")]
    old = {}
    try:
        old = json.loads(OUT.read_text(encoding="utf-8")).get("d") or {}
    except Exception:
        pass
    d = dict(old)
    ok = 0
    for i, c in enumerate(codes):
        if d.get(c, {}).get("yr"):                      # 상장일은 불변 — 기수집 스킵
            ok += 1
            continue
        try:
            t = urllib.request.urlopen(urllib.request.Request(
                f"https://finance.naver.com/item/main.naver?code={c}", headers=H), timeout=10).read()
            try: t = t.decode("utf-8")
            except UnicodeDecodeError: t = t.decode("cp949", "ignore")
            m = re.search(r"상장일</th>\s*<td[^>]*>\s*(\d{4})년", t)
            if m:
                d.setdefault(c, {})["yr"] = int(m.group(1))
                ok += 1
        except Exception:
            pass
        time.sleep(0.05)
        if i % 300 == 299:
            print(f"  {i+1}/{len(codes)} (확보 {ok})", flush=True)
    OUT.write_text(json.dumps({"asof": datetime.now().strftime("%Y-%m-%d %H:%M"), "d": d},
                              ensure_ascii=False), encoding="utf-8")
    print(f"[etfmeta] ✅ 상장연도 {ok}/{len(codes)}종 → {OUT}", flush=True)

if __name__ == "__main__":
    main()
