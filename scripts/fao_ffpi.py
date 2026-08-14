#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fao_ffpi.py — FAO 세계 식량가격지수(FFPI) 수집 (2026-08-14 신설).

FAO 가 매월 첫째 주에 발표하는 공식 CSV(1990~현재, 2014-2016=100)를 받아
data/db/fao_ffpi.json 으로 저장한다. 4.3 농산물 섹션에서 표+시계열로 쓴다.

열: 날짜, 종합(Food Price Index), 육류, 유제품, 곡물, 유지류, 설탕
실측(2026-07): 종합 131.1 · 곡물 113.8 · 유지류 195.7 · 설탕 95.0 — 뉴스 보도와 일치.

cron: 매월 3~9일 07:40 (발표일이 첫째 주 금요일 부근이라 그 주간에 매일 확인,
      값이 안 바뀌면 그대로 재저장될 뿐이라 무해)
"""
import csv
import io
import json
import urllib.request
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "data" / "db" / "fao_ffpi.json"
URL = ("https://www.fao.org/media/docs/worldfoodsituationlibraries/"
       "default-document-library/food_price_indices_data.csv?sfvrsn=523ebd2a_82&download=true")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"}
COLS = ["total", "meat", "dairy", "cereals", "oils", "sugar"]
KO = {"total": "종합", "meat": "육류", "dairy": "유제품",
      "cereals": "곡물", "oils": "유지류", "sugar": "설탕"}


def main():
    raw = urllib.request.urlopen(urllib.request.Request(URL, headers=UA), timeout=40).read()
    rows = list(csv.reader(io.StringIO(raw.decode("utf-8", "ignore"))))
    series = []                                       # [[YYYY-MM, 종합, 육류, 유제품, 곡물, 유지, 설탕], ...]
    for r in rows:
        if not r or not r[0][:4].isdigit() or "-" not in r[0]:
            continue
        try:
            vals = [round(float(r[i + 1]), 1) for i in range(6)]
        except Exception:
            continue
        series.append([r[0][:7]] + vals)
    if len(series) < 100:                             # 파싱이 깨졌으면 기존 파일을 지키지 않고 중단
        raise SystemExit(f"[ffpi] 행 {len(series)}개 — 형식 변경 의심, 저장하지 않음")

    latest = series[-1]
    prev = series[-2]
    yago = next((s for s in series if s[0] == f"{int(latest[0][:4])-1}{latest[0][4:]}"), None)
    snap = []
    for i, k in enumerate(COLS):
        cur = latest[i + 1]
        snap.append({
            "key": k, "name": KO[k], "value": cur,
            "mom": round(cur - prev[i + 1], 1),
            "yoy": round((cur / yago[i + 1] - 1) * 100, 1) if yago else None,
        })
    out = {
        "asof": latest[0], "updated": datetime.now().strftime("%Y-%m-%d"),
        "base": "2014-2016=100", "src": "FAO Food Price Index (공식 CSV)",
        "snap": snap,
        "series": series[-240:],                      # 최근 20년이면 차트에 충분
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    print(f"[ffpi] {latest[0]} 종합 {latest[1]} · 곡물 {latest[4]} · 유지류 {latest[5]} · "
          f"설탕 {latest[6]} — {len(series)}개월 저장")


if __name__ == "__main__":
    main()
