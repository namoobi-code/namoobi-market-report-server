#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""investor_flow.py — 3.2.1 투자자별 수급: 코스피·코스닥 **월별** 순매수 막대 (2026-10-24 신설)

사용자 요청: 한국거래소 '외국인 월별 유가증권시장 순매수/순매도액' 막대그래프(매경 지면)를 3.2.1 에 상시 제공.

소스: 네이버 신(新) 증권 사이트 API (구 finance.naver.com/sise/investorDealTrendDay 는 2026-10 기준 410 Gone,
      KIS FHPTJ04040000 시장별 투자자 일별은 전부 0 으로 와서 못 씀, KRX data.krx.co.kr getJsonData 는 'LOGOUT' 400)
  GET https://stock.naver.com/api/domestic/market/trend/daily?marketType=KOSPI|KOSDAQ&tradeType=KRX&bizdate=YYYYMMDD&startIdx=<페이지>&pageSize=100
  - startIdx 는 '페이지 번호'(0부터, 100행 고정) — bizdate 는 무시되고 항상 최신부터. totalElements 5,379(≈21년).
  - netAmounts[].investorGubun: 8000 개인 · 9000 외국인 · 9999 기관계(합산값은 안 와서 1000+2000+3000+4000+5000+6000 으로 합산)
    1000 금융투자 · 2000 보험 · 3000 투신(사모) · 4000 은행 · 5000 기타금융 · 6000 연기금등 · 7100 기타법인 · 9001 기타외국인
  - diffValue 단위 원 → 억원으로 저장. 당일 값은 장 마감 후 확정(네이버 표기와 동일).
산출: data/db/investor_flow.json
  { as_of, kospi:{daily:{t:[YYYYMMDD], frgn:[], inst:[], indi:[], pension:[], fin:[]}, monthly:[{m:'2026-09', frgn, inst, indi, pension, days}]}, kosdaq:{…} }
cron: 30 18 * * 1-5 (마감 확정 후) + 30 7 * * * (누락 보정)
"""
import json, sys, time, urllib.parse, urllib.request
from collections import OrderedDict
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "data" / "db" / "investor_flow.json"
KST = timezone(timedelta(hours=9))
H = {"User-Agent": "Mozilla/5.0", "Referer": "https://finance.naver.com/", "Accept": "application/json"}
PAGES = int(sys.argv[1]) if len(sys.argv) > 1 else 6          # 100행/페이지 → 6페이지 ≈ 2년 5개월
INST = ("1000", "2000", "3000", "4000", "5000", "6000")       # 기관계 구성

def log(m): print(m, flush=True)

def page(mt, idx):
    q = urllib.parse.urlencode({"marketType": mt, "tradeType": "KRX", "bizdate": datetime.now(KST).strftime("%Y%m%d"), "startIdx": str(idx), "pageSize": "100"})
    for _ in range(3):
        try:
            return json.loads(urllib.request.urlopen(urllib.request.Request(f"https://stock.naver.com/api/domestic/market/trend/daily?{q}", headers=H), timeout=20).read()).get("content") or []
        except Exception as e:
            log(f"  ⚠ {mt} p{idx}: {repr(e)[:60]}"); time.sleep(2)
    return []

def collect(mt):
    rows = {}
    for i in range(PAGES):
        c = page(mt, i)
        if not c: break
        for r in c:
            d = r.get("bizdate"); na = {x["investorGubun"]: float(x.get("diffValue") or 0) for x in (r.get("netAmounts") or [])}
            if not d or not na: continue
            inst = sum(na.get(k, 0.0) for k in INST)
            rows[d] = {"frgn": na.get("9000", 0.0) / 1e8, "inst": inst / 1e8, "indi": na.get("8000", 0.0) / 1e8, "pension": na.get("6000", 0.0) / 1e8, "fin": na.get("1000", 0.0) / 1e8}
        time.sleep(0.3)
    ts = sorted(rows)
    daily = {"t": ts}
    for k in ("frgn", "inst", "indi", "pension", "fin"):
        daily[k] = [round(rows[d][k], 1) for d in ts]
    # 월별 합
    mon = OrderedDict()
    for d in ts:
        m = f"{d[:4]}-{d[4:6]}"; o = mon.setdefault(m, {"m": m, "frgn": 0.0, "inst": 0.0, "indi": 0.0, "pension": 0.0, "fin": 0.0, "days": 0})
        for k in ("frgn", "inst", "indi", "pension", "fin"): o[k] += rows[d][k]
        o["days"] += 1
    monthly = [{**o, **{k: round(o[k]) for k in ("frgn", "inst", "indi", "pension", "fin")}} for o in mon.values()]
    if monthly: monthly[0]["partial"] = True          # 가장 오래된 달은 페이지 경계에 잘려 부분합
    if monthly and ts: monthly[-1]["mtd"] = True      # 이번 달 = 월중 누계
    return {"daily": daily, "monthly": monthly, "last": ts[-1] if ts else None}

def main():
    out = {"as_of": datetime.now(KST).strftime("%Y-%m-%d %H:%M"), "src": "네이버 증권 stock.naver.com/api/domestic/market/trend/daily (KRX 정규장) · 단위 억원 · 기관계=금융투자+보험+투신+은행+기타금융+연기금"}
    for mt in ("kospi", "kosdaq"):
        out[mt] = collect(mt.upper())
        d = out[mt]["daily"]; log(f"[invflow] {mt} {len(d['t'])}일 {d['t'][0] if d['t'] else '-'}~{out[mt]['last']} · 월 {len(out[mt]['monthly'])}개")
    if not out["kospi"]["daily"]["t"]:
        log("[invflow] ❌ 코스피 0행 — 기존 파일 유지"); return
    OUT.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    m = out["kospi"]["monthly"]
    log("[invflow] ✅ 코스피 외국인 최근 월별(억): " + " · ".join(f"{x['m'][2:]} {x['frgn']:+,}" for x in m[-6:]))

if __name__ == "__main__":
    main()
