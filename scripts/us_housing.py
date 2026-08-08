#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""us_housing.py — 미국 주택 선행지표 (2026-08-08 신설 · 매일 08:00 cron).

소스: FRED graph CSV — **인증키 불필요** (실측 2026-08-08)
      https://fred.stlouisfed.org/graph/fredgraph.csv?id=<SERIES>

  PERMIT        건축허가(천호, SAAR)   1960-01~   ← 착공에 약 6개월 선행
  HOUST         주택착공(천호, SAAR)   1959-01~
  MORTGAGE30US  30년 고정 모기지금리%   1971-04~   주간(목요일 발표)
  USSTHPI       FHFA 주택가격지수      1975 Q1~   분기

왜 보나: 미국 금리·주택 사이클은 글로벌 유동성의 원류라 한국 부동산 심리에도
        참고가 된다. 특히 모기지금리 ↔ 착공의 역상관은 교과서적으로 뚜렷하다.
        (NAHB 주택시장지수는 저작권 때문에 FRED 에 없음 — 실측 확인)

산출: data/db/us_housing.json {asof, series:{key:{label,unit,freq,note,t:[YYYYMMDD],v:[]}}}
"""
import json, urllib.request
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "data" / "db" / "us_housing.json"
UA = {"User-Agent": "Mozilla/5.0 (namoobi market terminal)"}

SERIES = {
    "permit": ("PERMIT", "건축허가", "천호(연율)", "월간",
               "착공에 약 6개월 선행 — 미국 주택 사이클의 가장 앞단"),
    "start":  ("HOUST", "주택착공", "천호(연율)", "월간",
               "실제 삽을 뜬 물량 — 건설투자·자재 수요로 직결"),
    "mort":   ("MORTGAGE30US", "30년 모기지금리", "%", "주간",
               "미국 주택수요의 핵심 변수 — 오르면 착공·거래가 시차를 두고 꺾인다"),
    "hpi":    ("USSTHPI", "주택가격지수(FHFA)", "지수", "분기",
               "실제 가격의 확정치 — 착공·허가보다 뒤에 움직이는 후행 확인용"),
}


def fetch(sid):
    u = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}"
    req = urllib.request.Request(u, headers=UA)
    txt = urllib.request.urlopen(req, timeout=60).read().decode("utf-8", "replace")
    t, v = [], []
    for ln in txt.splitlines()[1:]:                 # 1행은 헤더(observation_date,SERIES)
        p = ln.split(",")
        if len(p) < 2:
            continue
        d = p[0].strip().replace("-", "")
        try:
            val = float(p[1])
        except Exception:
            continue                                # 결측은 '.' 로 온다
        if len(d) == 8:
            t.append(d); v.append(val)
    return t, v


def main():
    out = {}
    for key, (sid, lab, unit, freq, note) in SERIES.items():
        try:
            t, v = fetch(sid)
        except Exception as e:
            print(f"  ⚠ {sid} 실패: {e}")
            continue
        if not t:
            print(f"  ⚠ {sid} 빈 응답")
            continue
        out[key] = {"id": sid, "label": lab, "unit": unit, "freq": freq,
                    "note": note, "t": t, "v": v}
        print(f"  ✅ {sid:14s} {lab:16s} {len(t):>5,}개 {t[0]}~{t[-1]} 최신 {v[-1]}")
    if not out:
        print("[ushouse] ❌ 전량 실패 — 저장 생략(기존 파일 보존)")
        return
    old = {}
    try:
        old = (json.loads(OUT.read_text(encoding="utf-8")) or {}).get("series") or {}
    except Exception:
        pass
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "asof": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "src": "FRED (St. Louis Fed) · 무인증 CSV",
        "series": {**old, **out}}, ensure_ascii=False), encoding="utf-8")
    print(f"[ushouse] → {OUT}")


if __name__ == "__main__":
    main()
