#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gp_cases.py — 가이던스 파서 회귀 케이스 (실측 보도자료 문장).

기대값은 8-K 원문을 눈으로 확인한 것이다. `python3 scripts/gp_cases.py` 로 돌려
전부 OK 가 나와야 한다. SEC 를 호출하지 않으므로 몇 번이든 돌릴 수 있다.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from guidance_parse import parse_guidance

# (이름, 문장, 기대 키 일부)
CASES = [
    # ── 연간(FY)로 잡혀야 하는 것들 ────────────────────────────────
    ("GPC", "July 21, 2026 FOR IMMEDIATE RELEASE Genuine Parts Company Reports Second Quarter "
            "2026 Results Reaffirms 2026 Outlook for Adjusted EPS of $7.50 to $8.00 Updates Select Elements",
     {"fy_eps_lo": 7.50, "fy_eps_hi": 8.00}),
    ("ILMN-rev", "Fiscal year 2026 guidance For fiscal year 2026, we now expect: "
                 "• Total revenue of $4.60-$4.64 billion, versus prior guidance",
     {"fy_rev_lo": 4.60e9, "fy_rev_hi": 4.64e9}),
    ("ILMN-eps", "For fiscal year 2026, we now expect: • Non-GAAP operating margin of 23.4%-23.6%, "
                 "unchanged from prior guidance • Non-GAAP diluted EPS of $5.30-$5.40, versus prior guidance",
     {"fy_eps_lo": 5.30, "fy_eps_hi": 5.40}),
    ("BFLY", "Guidance Raised revenue guidance and adjusted EBITDA guidance for the Fiscal Year 2026: "
             "• Revenue of $119 million to $123 million, or approximately 22% growth",
     {"fy_rev_lo": 119e6, "fy_rev_hi": 123e6}),
    ("CSTL", "Raising full-year 2026 revenue guidance to $365-375 million from $345-355 million",
     {"fy_rev_lo": 365e6, "fy_rev_hi": 375e6}),
    ("LIFE", "For the full fiscal year 2026, Ethos expects the following: "
             "• Total Revenue: Between $727 million and $731 million",
     {"fy_rev_lo": 727e6, "fy_rev_hi": 731e6}),
    ("DXC", "Full Year Fiscal 2027 and Second Quarter Fiscal Year 2027 Guidance Full Year Fiscal 2027 "
            "• Total revenue in the range of $12.10 billion and $12.35 billion",
     {"fy_rev_lo": 12.10e9, "fy_rev_hi": 12.35e9}),
    ("HSIC", "reported diluted EPS of $1.27 compared to $1.10 non-GAAP diluted EPS in Q2 2025 "
             "● Raises guidance for 2026 to the following: non-GAAP diluted EPS to $5.29 to $5.39",
     {"fy_eps_lo": 5.29, "fy_eps_hi": 5.39}),
    ("RGEN-eps", "adjusted operating income increased 55% • Raising both FY26 organic revenue growth "
                 "guidance to 10.5%-13.5% and adjusted EPS to $2.03-$2.09 WALTHAM, Mass., July 28, 2026",
     {"fy_eps_lo": 2.03, "fy_eps_hi": 2.09}),
    ("EW", "Increasing TMTT sales guidance: $760 to $780 million from $740 to $780 million "
           "• Reaffirming full year adjusted EPS guidance of $2.95 to $3.05, growing 17%",
     {"fy_eps_lo": 2.95, "fy_eps_hi": 3.05}),
    # ── 분기로 남아야 하는 것들(회귀 방지) ─────────────────────────
    ("QCOM", "Current Guidance Q4 FY26 Estimates Revenues $9.7B - $10.5B",
     {"rev_lo": 9.7e9, "rev_hi": 10.5e9}),
    ("WAT", "The Company expects third quarter 2026 adjusted EPS to be in the range of $3.95 to $4.05",
     {"eps_lo": 3.95, "eps_hi": 4.05}),
    ("FLEX", "Second Quarter Fiscal Year 2027 Guidance: - Net Sales: $7.95 billion to $8.25 billion",
     {"rev_lo": 7.95e9, "rev_hi": 8.25e9}),
    ("NET", "Financial Outlook For the third quarter of fiscal 2026, we expect: "
            "- Total revenue of $736.0 to $737.0 million",
     {"rev_lo": 736e6, "rev_hi": 737e6}),
    # ── 채택하면 안 되는 것들 ──────────────────────────────────────
    ("TTMI(이자비용)", "We expect SG&A expense to be approximately 7% of net sales in the third quarter "
                   "and R&D expenditures to be approximately 1% of net sales. We expect interest "
                   "expense of approximately $11.3 million", {}),
    ("PWR(EBITDA)", "For the full year of 2026, Quanta expects these acquisitions to contribute "
                    "approximately $1.2 billion - $1.4 billion of revenues and approximately "
                    "$120 million to $140 million of adjusted EBITDA", {}),
    ("WEX(증분)", "this assumption increased 2026 revenue and EPS guidance by approximately "
                "$32 million and $0.30", {}),
    ("INCY(영향)", "Estimated impact on third and fourth quarters of 2026 net sales from improved "
                 "GTN $40 - $50 million", {}),
]


def main():
    bad = 0
    for name, txt, exp in CASES:
        got = {k: v for k, v in parse_guidance(txt).items() if not k.startswith("_")}
        if exp:
            ok = all(abs((got.get(k) or 0) - v) <= max(abs(v) * 0.001, 0.005) for k, v in exp.items())
        else:
            ok = not got
        if not ok:
            bad += 1
        print(f"{'OK ' if ok else '실패'} {name:14s} 기대 {exp} / 실제 {got}")
    print(f"— {len(CASES) - bad}/{len(CASES)} 통과")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
