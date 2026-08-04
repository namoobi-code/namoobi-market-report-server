#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""rtms.py — 국토부 아파트 실거래가 (2026-08-02 신설 · 매일 07:20 cron).

소스: data.go.kr RTMSDataSvcAptTrade(매매) · RTMSDataSvcAptRent(전월세) — XML, 자동승인 키
지역: 서울 25개구 + 경기 주요(성남분당·수원영통·용인수지·화성·과천) + 5대 광역시 대표구 = 35곳
집계: 지역·월별 — 매매 {n 거래건수, avg 평균가(억), med 중위가(억)} · 전세(월세0) {n, dep 평균보증금(억)}
      해제거래(cdealType='O') 제외 · 실거래 신고기한 30일 → 최근 2~3개월은 미완성치(롤링 재수집으로 수렴)
산출: data/db/rtms.json {asof, names, sale:{code:{t,n,avg,med}}, rent:{...}, } + SEOUL(25구 합산) 의사지역
사용: rtms.py [--backfill]  (백필 24개월 · 기본 최근 3개월 롤링)
"""
import json, sys, time, urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "data" / "db" / "rtms.json"
KEY = (BASE / "keys" / "data.go.kr.txt").read_text().strip()
MONTHS = 24 if "--backfill" in sys.argv else 3
ONLY = None
if "--only" in sys.argv:
    ONLY = set(sys.argv[sys.argv.index("--only") + 1].split(","))

REGIONS = {
    "11110": "서울 종로구", "11140": "서울 중구", "11170": "서울 용산구", "11200": "서울 성동구",
    "11215": "서울 광진구", "11230": "서울 동대문구", "11260": "서울 중랑구", "11290": "서울 성북구",
    "11305": "서울 강북구", "11320": "서울 도봉구", "11350": "서울 노원구", "11380": "서울 은평구",
    "11410": "서울 서대문구", "11440": "서울 마포구", "11470": "서울 양천구", "11500": "서울 강서구",
    "11530": "서울 구로구", "11545": "서울 금천구", "11560": "서울 영등포구", "11590": "서울 동작구",
    "11620": "서울 관악구", "11650": "서울 서초구", "11680": "서울 강남구", "11710": "서울 송파구",
    "11740": "서울 강동구",
    "41135": "성남 분당구", "41117": "수원 영통구", "41465": "용인 수지구", "41597": "화성 동탄구", "41290": "과천시",
    "26350": "부산 해운대구", "27260": "대구 수성구", "28185": "인천 연수구", "31140": "울산 남구", "30200": "대전 유성구",
    # 참고: 화성시(41590)는 2026 일반구 분화(41593 봉담·41595 병점·41597 동탄) — 최대 거래권 동탄 채택.
    #       광주광역시는 본 API에 전 구·전 월 0건(국토부 데이터 미제공 이슈)이라 울산 남구로 대체.
}
SEOUL = [c for c in REGIONS if c.startswith("11")]

def months_back(n):
    y, m = datetime.now().year, datetime.now().month
    out = []
    for _ in range(n):
        m -= 1
        if m == 0: y -= 1; m = 12
        out.append(f"{y}{m:02d}")
    return out[::-1]

def fetch(svc, op, lawd, ym):
    """전 페이지 수집 — item dict 리스트."""
    rows, page = [], 1
    while True:
        u = (f"https://apis.data.go.kr/1613000/{svc}/{op}"
             f"?serviceKey={KEY}&LAWD_CD={lawd}&DEAL_YMD={ym}&numOfRows=1000&pageNo={page}")
        try:
            d = urllib.request.urlopen(u, timeout=25).read()
            root = ET.fromstring(d)
        except Exception:
            time.sleep(1)
            try:
                d = urllib.request.urlopen(u, timeout=25).read(); root = ET.fromstring(d)
            except Exception:
                return rows
        if (root.findtext(".//resultCode") or "") not in ("000", "00"):
            return rows
        items = root.findall(".//item")
        for it in items:
            rows.append({e.tag: (e.text or "").strip() for e in it})
        total = int(root.findtext(".//totalCount") or 0)
        if page * 1000 >= total or not items: break
        page += 1
    return rows

def num(s):
    try: return float(str(s).replace(",", ""))
    except Exception: return None

def agg_sale(rows):
    px = [num(r.get("dealAmount")) for r in rows if r.get("cdealType", "") != "O"]
    px = sorted(p / 10000 for p in px if p)                     # 만원 → 억
    if not px: return None
    n = len(px)
    med = px[n // 2] if n % 2 else (px[n // 2 - 1] + px[n // 2]) / 2
    return {"n": n, "avg": round(sum(px) / n, 2), "med": round(med, 2)}

def agg_rent(rows):
    dep = [num(r.get("deposit")) for r in rows
           if (num(r.get("monthlyRent")) or 0) == 0]            # 전세 = 월세 0
    dep = [d / 10000 for d in dep if d]
    if not dep: return None
    return {"n": len(dep), "dep": round(sum(dep) / len(dep), 2)}

def main():
    old = {}
    try: old = json.loads(OUT.read_text(encoding="utf-8"))
    except Exception: pass
    sale = old.get("sale") or {}; rent = old.get("rent") or {}
    yms = months_back(MONTHS + 1)                               # 당월 포함(신고분 반영)
    yms.append(datetime.now().strftime("%Y%m"))
    for i, (code, name) in enumerate(REGIONS.items()):
        if ONLY and code not in ONLY: continue
        s = {t: (sale.get(code) or {}).get("m", {}).get(t) for t in (sale.get(code) or {}).get("m", {})} \
            if isinstance((sale.get(code) or {}).get("m"), dict) else {}
        r_ = {t: (rent.get(code) or {}).get("m", {}).get(t) for t in (rent.get(code) or {}).get("m", {})} \
            if isinstance((rent.get(code) or {}).get("m"), dict) else {}
        for ym in yms:
            a = agg_sale(fetch("RTMSDataSvcAptTrade", "getRTMSDataSvcAptTrade", code, ym))
            if a: s[ym] = a
            time.sleep(0.12)
            b = agg_rent(fetch("RTMSDataSvcAptRent", "getRTMSDataSvcAptRent", code, ym))
            if b: r_[ym] = b
            time.sleep(0.12)
        sale[code] = {"m": s}; rent[code] = {"m": r_}
        print(f"  [{i+1}/{len(REGIONS)}] {name}: 매매 {len(s)}개월 · 전세 {len(r_)}개월")
    # 서울 전체(25구 합산) 의사지역
    allm = sorted({t for c in SEOUL for t in (sale.get(c) or {}).get("m", {})})
    sm = {}
    for t in allm:
        rs = [(sale[c]["m"].get(t)) for c in SEOUL if (sale.get(c) or {}).get("m", {}).get(t)]
        if rs:
            n = sum(x["n"] for x in rs)
            sm[t] = {"n": n, "avg": round(sum(x["avg"] * x["n"] for x in rs) / n, 2), "med": None}
    rm = {}
    allr = sorted({t for c in SEOUL for t in (rent.get(c) or {}).get("m", {})})
    for t in allr:
        rs = [(rent[c]["m"].get(t)) for c in SEOUL if (rent.get(c) or {}).get("m", {}).get(t)]
        if rs:
            n = sum(x["n"] for x in rs)
            rm[t] = {"n": n, "dep": round(sum(x["dep"] * x["n"] for x in rs) / n, 2)}
    sale["SEOUL"] = {"m": sm}; rent["SEOUL"] = {"m": rm}
    names = dict(REGIONS); names["SEOUL"] = "서울 전체(25개구)"
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"asof": datetime.now().strftime("%Y-%m-%d %H:%M"),
                               "names": names, "sale": sale, "rent": rent}, ensure_ascii=False),
                   encoding="utf-8")
    print(f"[rtms] ✅ {len(REGIONS)}지역 · 서울합산 {len(sm)}개월 → {OUT}")

if __name__ == "__main__":
    main()
