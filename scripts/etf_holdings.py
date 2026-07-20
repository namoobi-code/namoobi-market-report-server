#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""etf_holdings.py — 전 ETF 보유종목(Top10) 벌크 수집. (2026-07-20 신설)

용도: ETF 스크리너의 '🔎 종목:' 역검색 — "이 종목을 담고 있는 ETF" 를 찾으려면
      개별 온디맨드(/api/etf/holdings)로는 불가능하고 전 종목 사전 수집이 필요하다.

  · KR : 네이버 m.stock etfAnalysis → etfTop10MajorConstituentAssets (1콜/ETF)
  · US : Yahoo quoteSummary topHoldings (1콜/ETF, crumb 필요) — AUM 상위 US_TOP 종만
         (5,200여 종 전량은 Yahoo 차단 위험 + 소형 ETF 는 검색 실효성 낮음)

출력: db/etf_holdings.json
  {"as_of":..., "kr":{"396500":[["삼성전자","005930",27.93], ...]}, "us":{"SPY":[["NVIDIA Corp","NVDA",7.5], ...]}}
  → 프론트가 필요할 때만 지연 로드해 역검색(종목명·티커 부분일치)에 쓴다.

실측(2026-07-20): KR 1,146종 ≈ 68초(8워커) · US 상위 1,500종 ≈ 30초(6워커)
"""
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ta_screen as T                      # noqa: E402

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(BASE, "data", "db", "etf_holdings.json")
UA = {"User-Agent": "Mozilla/5.0", "Referer": "https://m.stock.naver.com/"}
US_TOP = 1500                              # US 는 AUM 상위만 (Yahoo 부하·차단 방지)
TOPN = 10                                  # ETF 당 상위 보유종목 수


def _pct(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return round(float(v), 2)
    m = re.search(r"-?[\d.]+", str(v).replace(",", ""))
    return round(float(m.group(0)), 2) if m else None


def _kr(code):
    try:
        u = "https://m.stock.naver.com/api/stock/%s/etfAnalysis" % code
        d = json.loads(urllib.request.urlopen(
            urllib.request.Request(u, headers=UA), timeout=12).read().decode("utf-8", "ignore"))
        out = []
        for x in (d.get("etfTop10MajorConstituentAssets") or [])[:TOPN]:
            nm = (x.get("itemName") or "").strip()
            if nm:
                out.append([nm, (x.get("itemCode") or "").strip(), _pct(x.get("etfWeight"))])
        return code, out
    except Exception:
        return code, []


def _us_factory(op, crumb):
    def _us(code):
        try:
            u = ("https://query1.finance.yahoo.com/v10/finance/quoteSummary/%s"
                 "?modules=topHoldings&crumb=%s"
                 % (urllib.parse.quote(code), urllib.parse.quote(crumb)))
            j = T.jget(u, opener=op, timeout=15)
            th = ((j.get("quoteSummary", {}).get("result") or [{}])[0] or {}).get("topHoldings", {}) or {}
            out = []
            for h in (th.get("holdings") or [])[:TOPN]:
                nm = (h.get("holdingName") or h.get("symbol") or "").strip()
                if not nm:
                    continue
                hp = h.get("holdingPercent") or {}
                w = hp.get("raw")
                w = round(w * 100, 2) if isinstance(w, (int, float)) else _pct(hp.get("fmt"))
                out.append([nm, (h.get("symbol") or "").strip(), w])
            return code, out
        except Exception:
            return code, []
    return _us


def main():
    pool = T.load_db("etf_pool")
    if not pool:
        print("[etf_holdings] etf_pool 없음 — skip"); return 1
    kr = [r["c"] for r in pool.get("kr", []) if r.get("c")]
    us = [r["c"] for r in sorted(pool.get("us", []), key=lambda r: -(r.get("cap") or 0))
          if r.get("c")][:US_TOP]

    print("[etf_holdings] KR %d종 수집…" % len(kr))
    KR = {c: h for c, h in T.pmap(_kr, kr, workers=8) if h}
    print("[etf_holdings]   → %d종 성공" % len(KR))

    US = {}
    try:
        op, crumb = T.yahoo_opener()
        print("[etf_holdings] US 상위 %d종 수집…" % len(us))
        US = {c: h for c, h in T.pmap(_us_factory(op, crumb), us, workers=6) if h}
        print("[etf_holdings]   → %d종 성공" % len(US))
    except Exception as e:
        print("[etf_holdings] US skip:", repr(e)[:70])

    if not KR and not US:
        print("[etf_holdings] 수집 0건 — 기존 파일 유지"); return 1
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    tmp = OUT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"as_of": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                   "topn": TOPN, "kr": KR, "us": US}, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, OUT)
    sz = os.path.getsize(OUT) / 1024
    print("[etf_holdings] ✅ KR %d · US %d 저장 (%.0fKB) → %s" % (len(KR), len(US), sz, OUT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
