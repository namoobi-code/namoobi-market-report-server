#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""src_probe.py — 가이던스(매출·EPS) 대체 소스 접근성 프로브 (2026-08-10).

Benzinga 가 429(속도 제한)로 막혀 있어, 같은 성격의 데이터를 주는 다른 창구를
하나씩 두드려 본다. 순차 + 간격을 둬서 새로 차단당하지 않게 한다.
"""
import time, urllib.request, sys

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36",
      "Accept": "text/html,application/json,*/*"}

T = sys.argv[1] if len(sys.argv) > 1 else "ILMN"
TARGETS = [
    ("Benzinga 종목페이지", f"https://www.benzinga.com/quote/{T}/earnings-forecasts", "eps_guidance_est"),
    ("Benzinga 홈(차단범위 확인)", "https://www.benzinga.com/", "Benzinga"),
    ("StreetInsider 가이던스", f"https://www.streetinsider.com/ec_earnings.php?q={T}", "uidance"),
    ("StockAnalysis 전망", f"https://stockanalysis.com/stocks/{T}/forecast/", "uidance"),
    ("Zacks 실적발표", f"https://www.zacks.com/stock/research/{T}/earnings-announcements", "guidance_table"),
    ("Nasdaq 실적전망", f"https://api.nasdaq.com/api/analyst/{T}/earnings-forecast", "eps"),
    ("Finnhub 무료", f"https://finnhub.io/api/v1/stock/revenue-estimate?symbol={T}", "data"),
    ("TipRanks 전망", f"https://www.tipranks.com/stocks/{T.lower()}/forecast", "uidance"),
]

for name, url, key in TARGETS:
    try:
        r = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20)
        h = r.read().decode("utf-8", "ignore")
        print(f"{name:26s} HTTP {r.status} · {len(h):>7,}자 · '{key}' {h.count(key)}회")
    except Exception as e:
        print(f"{name:26s} 실패 — {e}")
    time.sleep(4)
