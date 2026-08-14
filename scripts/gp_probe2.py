#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gp_probe2.py — 재현율 개선용 실측 표본 테스트 (2026-08-15). 실제 8-K 원문 발췌."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from guidance_parse import parse_guidance

CASES = [
    # A. Low/High 두 열 표 — 구분자 없는 숫자 2개 + (in millions) 단위 헤더 (실측 MH)
    ("MH-표", "Actual results may differ materially from what is indicated below. Fiscal Year 2027 "
     "Guidance ($ in millions) Low High Revenue $ 2,115 $ 2,175 Re-occurring Revenue 1,587 1,627 "
     "Adjusted EBITDA (1) 750 790 Earnings Conference Call and Webcast",
     {"fy_rev_lo": 2115e6, "fy_rev_hi": 2175e6}),
    # B. GMRS — (in millions) + Low High + 'Net revenue'
    ("GMRS-표", "GMR is reaffirming the following guidance for the full year 2026: (in millions) "
     "Range for the year ending December 31, 2026 Low High Net revenue $ 5,890 $ 6,180 "
     "Adjusted EBITDA (2) $ 1,135 $ 1,195 Cash used for net capital expenditures",
     {"fy_rev_lo": 5890e6, "fy_rev_hi": 6180e6}),
    # C. 'net income per share' 라벨 (실측 LFTO)
    ("LFTO-eps", "Fiscal Year 2026 Financial Guidance Summary (Unaudited, in millions, except "
     "percentages and per share data) Low High Gross margin % 51.0% 52.0% Gross profit $ 258 $ 273 "
     "Operating profit (2) $ 99 $ 111 Tax rate 23.0% 23.0% Net income per share $ 0.67 $ 0.75 Shares (3) 110.4",
     {"fy_eps_lo": 0.67, "fy_eps_hi": 0.75}),
    # D. 'net income per diluted share, excluding special items, non-GAAP' (실측 EAT)
    ("EAT-eps", "For fiscal 2027 the Company estimates the impact of the additional operating week to be "
     "an increase of approximately 2.0% in Total revenues and $0.70 in Net income per diluted share, "
     "excluding special items, non-GAAP: Total revenues $6.15 billion - $6.27 billion Net income per "
     "diluted share, excluding special items, non-GAAP $12.60 - $13.40 Capital expenditures $265.0 "
     "million - $285.0 million",
     {"fy_rev_lo": 6.15e9, "fy_rev_hi": 6.27e9, "fy_eps_lo": 12.60, "fy_eps_hi": 13.40}),
    # E. 'Adjusted net income per common share, diluted' + approximately (실측 KLC)
    ("KLC-eps", "For the full year 2026, revenue is expected to be approximately $2.66 billion to "
     "$2.70 billion and adjusted EBITDA is expected to be approximately $200 million to $220 million. "
     "Adjusted net income per common share, diluted is expected to be approximately $0.05 to $0.15.",
     {"fy_rev_lo": 2.66e9, "fy_rev_hi": 2.70e9, "fy_eps_lo": 0.05, "fy_eps_hi": 0.15}),
    # F. 'expects to report revenue' — 수식어 report 오탐 (실측 TRMB)
    ("TRMB-rev", "Forward-Looking Guidance For the full-year 2026, Trimble expects to report revenue "
     "between $3,900 million and $3,950 million, GAAP loss per share of $0.07 to $0.12, and non-GAAP "
     "earnings per share of $3.60 to $3.70.",
     {"fy_rev_lo": 3900e6, "fy_rev_hi": 3950e6, "fy_eps_lo": 3.60, "fy_eps_hi": 3.70}),
    # G. YETI — 'Raises 2026 adjusted EPS to $2.94 to $3.00 … up from $2.83 to $2.89'
    ("YETI-eps", "Update on 2026 Outlook • Maintains 2026 sales growth of 7% to 8% • Increases 2026 "
     "adjusted operating income margin to 14.9%, up from 14.6% previously • Raises 2026 adjusted EPS "
     "to $2.94 to $3.00, reflecting 19% to 21% growth, up from $2.83 to $2.89 or 14% to 17% growth previously",
     {"fy_eps_lo": 2.94, "fy_eps_hi": 3.00}),
    # H. UPWK — 불릿 목록 FY 가이던스 (머리글 콜론까지 110자)
    ("UPWK-rev", "Upwork's guidance for revenue, adjusted EBITDA, diluted weighted-average shares "
     "outstanding, and non-GAAP diluted EPS for full year 2026 is: • Revenue: $730 million to $750 "
     "million • Adjusted EBITDA: $225 million to $235 million",
     {"fy_rev_lo": 730e6, "fy_rev_hi": 750e6}),
    # I. WWW — diluted EPS + adjusted diluted EPS 나란히 (조정 쪽 채택 기대)
    ("WWW-eps", "For fiscal 2026 the Company now expects: • Effective tax rate to be approximately "
     "18.0%, unchanged from the previous outlook. • Diluted earnings per share in the range of $1.48 "
     "to $1.58 and adjusted diluted earnings per share in the range of $1.55 to $1.65.",
     {"fy_eps_lo": 1.55, "fy_eps_hi": 1.65}),
    # J. CAH — 괄호 병기 '13% to 15% growth ($12.40 to $12.60)'
    ("CAH-eps", "Cardinal Health provides fiscal year 2027 non-GAAP EPS guidance of 13% to 15% growth "
     "($12.40 to $12.60), above the Company's long-term EPS guidance.",
     {"fy_eps_lo": 12.40, "fy_eps_hi": 12.60}),
]


def main():
    ok = 0
    for name, txt, want in CASES:
        g = parse_guidance(txt)
        got = {k: g.get(k) for k in want}
        good = all(got.get(k) == v for k, v in want.items())
        ok += good
        print(("OK " if good else "MISS") + f" {name:10s} 기대 {want}")
        if not good:
            print(f"     실제 {dict((k, v) for k, v in g.items() if not k.startswith('_'))}")
            for s in (g.get("_skip") or [])[:4]:
                print(f"     skip: {s[:140]}")
    print(f"— {ok}/{len(CASES)}")


if __name__ == "__main__":
    main()
