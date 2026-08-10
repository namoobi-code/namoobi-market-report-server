#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bz_probe.py — Benzinga 무료 종목 페이지의 가이던스 JSON 커버리지 조사 (2026-08-10).

benzinga.com/quote/{TICKER}/earnings-forecasts 는 Next.js 페이지인데, HTML 안에
guidanceSummary.guidance 배열이 **구조화된 채로** 들어 있다. 필드가 우리에게 딱 맞다:
  date · period("FY"/"Q1".."Q4") · period_year · eps_type("Adj"/"GAAP")
  eps_guidance_min/max/est · revenue_guidance_min/max/est · prior_* · is_primary
기간·회계기준을 **회사가 아니라 데이터가 알려주므로**, 우리 8-K 파서가 가장 자주 틀리는
두 가지(연간↔분기, GAAP↔조정)를 그대로 검증할 수 있다.
"""
import json, re, sys, urllib.request
from concurrent.futures import ThreadPoolExecutor

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"}
NUM = lambda v: (float(v) if v not in (None, "", "0.000") else None)


def fetch(sym):
    """→ [{date, period, year, eps_lo, eps_hi, eps_type, rev_lo, rev_hi, prior_eps_lo…}]"""
    try:
        h = urllib.request.urlopen(urllib.request.Request(
            f"https://www.benzinga.com/quote/{sym.upper()}/earnings-forecasts",
            headers=UA), timeout=25).read().decode("utf-8", "ignore")
    except Exception:
        return []
    # Next.js 페이로드는 따옴표가 \" 로 이스케이프돼 있다. 정규식으로 조각을 긁으면
    # 다른 표(어닝 캘린더)까지 섞이므로, guidanceSummary 위치를 잡아 **배열 하나를 통째로**
    # JSON 파서에 넘긴다(raw_decode 가 끝을 알아서 찾는다).
    # 가이던스 레코드는 평평한 객체다. eps_guidance_est 를 앵커로 잡고 좌우 중괄호까지
    # 잘라내 하나씩 파싱한다(배열 통째 파싱은 Next.js 청크 분할 때문에 실패한다).
    out = []
    for m in re.finditer(r'eps_guidance_est', h):
        a = h.rfind("{", 0, m.start())
        b = h.find("}", m.end())
        if a < 0 or b < 0:
            continue
        try:
            d = json.loads(h[a:b + 1].replace('\\"', '"'))
        except Exception:
            continue
        if "period_year" not in d:
            continue
        out.append({
            "date": d.get("date"), "period": d.get("period"), "year": d.get("period_year"),
            "eps_type": d.get("eps_type"), "primary": d.get("is_primary"),
            "eps_lo": NUM(d.get("eps_guidance_min")), "eps_hi": NUM(d.get("eps_guidance_max")),
            "rev_lo": NUM(d.get("revenue_guidance_min")), "rev_hi": NUM(d.get("revenue_guidance_max")),
            "p_eps_lo": NUM(d.get("eps_guidance_prior_min")), "p_eps_hi": NUM(d.get("eps_guidance_prior_max")),
        })
    return out


if __name__ == "__main__":
    syms = sys.argv[1:] or ["ILMN", "EW", "COR", "NVDA"]
    with ThreadPoolExecutor(max_workers=6) as ex:
        res = list(ex.map(fetch, syms))
    hit = 0
    for s, rows in zip(syms, res):
        if rows:
            hit += 1
            r = rows[0]
            print(f"{s:6s} {len(rows):3d}건 · 최신 {r['date']} {r['period']}{r['year']} "
                  f"{r['eps_type']} EPS {r['eps_lo']}~{r['eps_hi']} · 매출 {r['rev_lo']}~{r['rev_hi']}")
        else:
            print(f"{s:6s}   0건")
    print(f"— 커버리지 {hit}/{len(syms)}")
