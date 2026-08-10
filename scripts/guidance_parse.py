#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""guidance_parse.py — 8-K 보도자료 가이던스 파서 v3 (2026-08-10 전면 재작성).

설계 원칙 — "100% 보장"의 대상을 바꾼다
--------------------------------------
보도자료는 자유 형식 영문이라 *모든* 회사의 가이던스를 빠짐없이 뽑는 것은 원리적으로
보장할 수 없다(회사마다 문장·표 형식이 다르고, 아예 숫자를 안 주는 곳도 많다).
그래서 보장 대상을 이렇게 정의한다:

    ❌ 재현율(다 뽑는다)  →  보장 불가
    ✅ 정밀도(**표시되는 값은 전부 맞다**) → 규칙으로 보장 + 근거로 검증 가능

이를 위해 후보(candidate) 하나하나가 아래 4가지를 **명시적으로** 만족해야만 채택한다.
하나라도 확정 못 하면 채택하지 않고 사유를 남긴다(사일런트 실패 금지).

  ① 지표 정체성  전사(consolidated) 매출인가? 세그먼트·organic·acquired 등 부분치는 기각
                 (실측 SDGR 'Drug discovery revenue' → 전사 컨센과 비교되어 +44.3% 오판정)
  ② 회계 기준    EPS 는 조정(non-GAAP/adjusted) 인가? 컨센서스가 조정 기준이므로
                 GAAP 전용 값은 기각 (실측 QCOM GAAP 1.22~1.42 → 조정 컨센 2.17 대비 −39%)
  ③ 대상 기간    분기인지 연간인지 **문맥에 명시**돼 있어야 한다. 없으면 기각
                 (실측 PNW 연간 EPS 가이던스 4.55~4.75 가 분기로 분류돼 +47.6% 오판정)
  ④ 단위·범위    million/billion 이 명시되고 상·하단이 정상 범위(≤1.6배)

판정은 **매칭 지점 주변 문맥**으로만 한다. 보도자료 말미의 가이던스 표는 태그를 벗기면
한 덩어리 문자열이 되어(실측 QCOM/PNW), 문장 전체를 보면 전사·세그먼트·GAAP·조정이
모두 섞여 반드시 오판한다.

산출물에는 값과 함께 근거 문맥(_ev)·기각 사유(_skip)를 담아 guidance_check.py 로
언제든 감사할 수 있다.
"""
import re

_MULT = {"billion": 1e9, "bn": 1e9, "b": 1e9, "million": 1e6, "mm": 1e6, "m": 1e6}
_NUM = r"\$?\s?([\d,]+(?:\.\d+)?)\s*(billion|million|bn|mm|b|m)?"

# 전망을 말하는 문맥에서만 숫자를 취한다(과거 실적 서술 배제)
_FORE = r"expect|guidance|outlook|anticipat|forecast|project|estimat"
# 부분 지표 — 전사 매출이 아님
_PART = (r"segment|product line|service revenue|subscription|recurring|licen[cs]|advertis|"
         r"organic|acquired business|supplemental|divisional|by region|geograph|"
         r"drug discovery|software revenue|hardware|instrument|QCT|QTL|QSI")
# 전사 매출임을 확인해 주는 수식어(바로 앞 단어)
_CORP_W = {"total", "net", "consolidated", "company", "companywide", "overall", "projected",
           "reported", "gaap", "quarterly", "annual", "full", "year", "fiscal", "our", "the",
           "of", "in", "and", "expects", "expect", "expected", "anticipates", "projects",
           "guidance", "outlook", "estimates", "estimate", "s", "is", "to", "be", "we",
           "a", "for", "with", "at", "approximately", "about", "around", "range", "revenues"}
_ADJ = r"non[-\s]?gaap|adjusted|core\s+(?:eps|earnings)|operating earnings"
_GAAP = r"(?<!non-)(?<!non )\bgaap\b"
_QRE = (r"(first|second|third|fourth)[-\s]quarter|\bQ[1-4]\b|quarter (?:of|ending|ended)|"
        r"for the (?:first|second|third|fourth) quarter|next quarter|current quarter")
_YRE = r"full[-\s]year|fiscal year|for the year|full fiscal|annual|FY\s?20\d\d|\b20\d\d\s+(?:eps\s+)?guidance"


def _num(v, unit, hint=None):
    try:
        x = float(v.replace(",", ""))
    except Exception:
        return None
    u = (unit or "").lower()
    if u in _MULT:
        return x * _MULT[u]
    return x * (_MULT[hint] if hint in _MULT else 1)


# (2026-08-10) EPS 는 **금액 표기($ 또는 cents)만** 받는다.
#  실측 오파싱이 전부 성장률 문장이었다 — "EPS growth of 20-25 percent"(HNI),
#  "core EPS to grow approximately 28%"(GLW), "EPS growth of 14-16%"(ATEN) 를
#  주당 금액으로 읽어 갭이 1,000~10,000% 로 튀었다. 정상 가이던스는 예외 없이 $ 표기
#  (QCOM $2.05-$2.25 · WAT $3.95-$4.05 · PNW $4.55-$4.75) 이므로 $ 를 필수로 두면
#  성장률 문장이 구조적으로 걸러진다. 'NN cents' 표기(실측 SOFI)는 /100 해서 인정.
_NUM_D = r"\$\s?([\d,]+(?:\.\d+)?)()"                      # 금액($) — 단위 그룹은 빈 자리
_NUM_C = r"([\d,]+(?:\.\d+)?)\s*(cents?)"                  # 60 cents → 0.60


def _forms(label, metric):
    """실측된 표기 4종 — 범위형·±금액·±퍼센트·근사형. EPS 는 금액 표기만."""
    if metric == "eps":
        return [
            ("range", label + r"[^$%]{0,60}?" + _NUM_D + r"\s*(?:to|through|-|and)\s*" + _NUM_D),
            ("rangec", label + r"[^$%]{0,60}?" + _NUM_C + r"\s*(?:to|through|-|and)\s*" + _NUM_C),
            ("approx", label + r"[^$%]{0,60}?(?:approximately|about|around)\s*" + _NUM_D),
            ("approxc", label + r"[^$%]{0,60}?(?:approximately|about|around)\s*" + _NUM_C),
        ]
    return [
        ("range", label + r"[^$%]{0,60}?" + _NUM + r"\s*(?:to|through|-|and)\s*" + _NUM),
        ("pm", label + r"[^$%]{0,60}?" + _NUM + r"\s*(?:±|\+/-|plus or minus)\s*" + _NUM),
        ("pmpct", label + r"[^$]{0,60}?" + _NUM + r"[^$]{0,20}?(?:±|\+/-|plus or minus)\s*([\d.]+)\s*%"),
        ("approx", label + r"[^$%]{0,60}?(?:approximately|about|around)\s*" + _NUM),
    ]


def _pair(kind, m):
    if kind == "rangec":                       # "60 cents to 65 cents" → 0.60~0.65
        a, b = _num(m.group(1), None), _num(m.group(3), None)
        return (a / 100 if a is not None else None, b / 100 if b is not None else None)
    if kind == "approxc":
        a = _num(m.group(1), None)
        a = a / 100 if a is not None else None
        return a, a
    if kind == "range":
        h = (m.group(4) or m.group(2) or "").lower()
        return _num(m.group(1), m.group(2), h), _num(m.group(3), m.group(4), h)
    if kind == "pm":
        h = (m.group(2) or m.group(4) or "").lower()
        c, d = _num(m.group(1), m.group(2), h), _num(m.group(3), m.group(4), h)
        return (c - d, c + d) if (c is not None and d is not None) else (None, None)
    if kind == "pmpct":
        c = _num(m.group(1), m.group(2))
        try:
            p = float(m.group(3)) / 100
        except Exception:
            return None, None
        return (c * (1 - p), c * (1 + p)) if c is not None else (None, None)
    a = _num(m.group(1), m.group(2))
    return a, a


def _period(txt, start, end):
    """이 후보가 가리키는 기간 — 'Q'(분기) · 'Y'(연간) · None(확정 불가 → 기각).

    **가장 가까운 기간 표현**을 쓴다. 실측상 기간은 문단 머리에 한 번만 쓰고
    ("Outlook for the third quarter of fiscal 2027 is as follows: • Revenue …")
    이후 항목엔 반복하지 않는 경우가 많아, 매칭 지점 바로 앞만 보면 멀쩡한 값을
    '기간 미명시'로 버리게 된다. 그래서 앞 400자에서 **마지막**(=가장 가까운) 표현을
    찾고, 없으면 뒤 90자까지 본다. 그래도 없으면 확정 불가 → 기각.
    """
    # 매칭 구간(start~end) 안에 기간 표현이 들어 있는 경우도 있다 —
    # 실측 PNW "2026 EPS guidance of $4.55-$4.75" 는 라벨(EPS) 바로 앞에 연도가 붙어
    # start 이전만 보면 놓친다. 그래서 스캔 범위를 end 까지로 잡는다.
    back = txt[max(0, start - 400):end]
    cand = [(m.start(), "Q") for m in re.finditer(_QRE, back, re.I)]
    cand += [(m.start(), "Y") for m in re.finditer(_YRE, back, re.I)]
    if cand:
        return max(cand)[1]                       # 가장 뒤(가까운) 표현
    fwd = txt[end:end + 90]
    q, y = re.search(_QRE, fwd, re.I), re.search(_YRE, fwd, re.I)
    if q and (not y or q.start() < y.start()):
        return "Q"
    if y:
        return "Y"
    return None


def parse_guidance(txt):
    """보도자료 평문 → {rev_lo,rev_hi,eps_lo,eps_hi, fy_*} + _ev(근거) + _skip(기각 사유)."""
    out, ev, skip = {}, {}, []
    if not txt:
        return out

    def add(metric, per, lo, hi, ctx, basis=None):
        pre = "" if per == "Q" else "fy_"
        if pre + metric + "_lo" in out:
            return
        out[pre + metric + "_lo"], out[pre + metric + "_hi"] = (
            (lo, hi) if metric == "rev" else (round(lo, 2), round(hi, 2)))
        if basis:
            out[pre + metric + "_basis"] = basis
        ev[pre + metric] = re.sub(r"\s+", " ", ctx)[:400]

    for metric, label in (("rev", r"(?:revenues?|net sales)"),
                          ("eps", r"(?:diluted\s+)?earnings per share|\beps\b")):
        for kind, pat in _forms(label, metric):
            for m in re.finditer(pat, txt, re.I):
                lo, hi = _pair(kind, m)
                if lo is None or hi is None:
                    continue
                # 앞 문맥은 용도별로 길이를 달리한다 — 기간·기준은 넓게(130자), 지표 수식어는
                # 좁게(60자) 봐야 한다. 넓게 보면 **직전 문장**의 'organic·acquired' 같은 단어가
                # 딸려 들어와 멀쩡한 전사 매출까지 기각된다(실측 WAT 'Total Company reported revenue').
                back = txt[max(0, m.start() - 130):m.start()]     # 기간·기준 판정용
                near = txt[max(0, m.start() - 60):m.start()]      # 지표 수식어 판정용
                ctx = txt[max(0, m.start() - 130):min(len(txt), m.end() + 40)]
                if not re.search(_FORE, ctx, re.I):
                    continue                                       # 전망 문맥 아님 → 조용히 통과
                per = _period(txt, m.start(), m.end())
                if not per:
                    skip.append(f"{metric}: 기간 미명시(분기/연간 확정 불가) · {ctx[:130]}")
                    continue
                if metric == "rev":
                    if re.search(_PART, near, re.I):
                        skip.append(f"rev: 전사 아님(부분 지표) · {ctx[:130]}")
                        continue
                    mw = None
                    for mw in re.finditer(r"([A-Za-z][\w\-]*)\s+(?:revenues?|net sales)", near + " revenue", re.I):
                        pass
                    if mw and re.sub(r"[^a-z]", "", mw.group(1).lower()) not in _CORP_W:
                        skip.append(f"rev: 수식어 '{mw.group(1)}' → 전사 아님 · {ctx[:120]}")
                        continue
                    if not re.search(r"(billion|million|bn|mm)\b|\$\s?[\d,.]+\s*[BM]\b", ctx):
                        skip.append(f"rev: 단위 미표기 → 자릿수 확정 불가 · {ctx[:120]}")
                        continue
                    if not (0 < lo <= hi and lo > 1e5 and hi / lo < 1.6):
                        skip.append(f"rev: 범위 비정상({lo:.0f}~{hi:.0f}) · {ctx[:120]}")
                        continue
                    add("rev", per, lo, hi, ctx)
                else:
                    adj = bool(re.search(_ADJ, ctx, re.I))
                    if re.search(_GAAP, ctx, re.I) and not adj:
                        skip.append(f"eps: GAAP 기준 → 조정 컨센과 비교 불가 · {ctx[:130]}")
                        continue
                    if not (-100 < lo <= hi < 1000):
                        skip.append(f"eps: 값 범위 비정상({lo}~{hi}) · {ctx[:120]}")
                        continue
                    add("eps", per, lo, hi, ctx, "adj" if adj else "unspec")
    if ev:
        out["_ev"] = ev
    if skip:
        out["_skip"] = skip[:20]
    return out
