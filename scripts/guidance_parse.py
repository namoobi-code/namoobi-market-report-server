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
# (2026-08-15) 오탐으로 확인된 무해 수식어 추가 — "expects to **report** revenue"(실측 TRMB) ·
# "**its** revenue" · "FY27 revenue"(연도 표기) · 불릿 기호 "o Revenue" · "record revenue"(사상 최대)
# · "updating its **full-year** 2026 guidance … Total Revenue"(실측 JBI) 등 — 전부 전사 매출이었다.
_CORP_W = {"total", "net", "consolidated", "company", "companywide", "overall", "projected",
           "reported", "gaap", "quarterly", "annual", "full", "year", "fiscal", "our", "the",
           "of", "in", "and", "expects", "expect", "expected", "anticipates", "projects",
           "guidance", "outlook", "estimates", "estimate", "s", "is", "to", "be", "we",
           "a", "for", "with", "at", "approximately", "about", "around", "range", "revenues",
           "report", "reports", "record", "records", "deliver", "delivers", "generate",
           "generates", "achieve", "achieves", "its", "their", "o", "fy", "fullyear",
           "now", "raised", "raises", "raising", "updated", "updates", "updating",
           "increased", "increases", "increasing", "lowered", "lowers", "lowering",
           "revised", "revises", "revising", "reaffirms", "reaffirmed", "maintains", "high", "low"}
# 라벨(매출·EPS)과 금액 사이에 이런 말이 끼면, 그 금액은 **다른 항목**의 것이다.
# (2026-08-14) ebitda\d* — 보도자료의 각주 번호가 단어에 바로 붙는다("Adjusted EBITDA2",
# "EBITDA1"). \bebitda\b 는 숫자 앞에서 경계가 성립하지 않아 통과됐고, EBITDA 범위가
# 매출·EPS 로 오채택됐다(실측 VSTS 312.5(-88%) · HLF 680(-87%) — 둘 다 EBITDA 값).
_OTHER = (r"\b(?:expense|expenditures?|capex|capital expenditure|interest|tax|"
          r"ebitda\d*|ebit\b|operating income|net income|cash flow|free cash|"
          r"amortization|depreciation|debt|buyback|repurchase|dividend|"
          r"headcount|margin|share count|shares outstanding)\b")


def _OTHER_HIT(s):
    m = re.search(_OTHER, s, re.I)
    return m.group(0) if m else "?"


_ADJ = r"non[-\s]?gaap|adjusted|core\s+(?:eps|earnings)|operating earnings"
_GAAP = r"(?<!non-)(?<!non )\bgaap\b"
# (2026-08-10) 과거 실적을 가리키는 분기 표현은 기간 판정에서 제외한다.
# 실측 SRE: "affirming its 2026 adjusted EPS guidance ... reflecting actual results **through the
# second quarter**" → 연간 가이던스인데 '2분기'로 잡혀 분기 컨센과 비교돼 +396% 오판정.
_QPAST = (r"(?:through|results through|through the|reported|ended|completed|"
          r"in the|during the|versus the|vs\.? the)\s+$")
# (2026-08-14) [1-4]Q 표기 추가 — "3Q 2026 Full Year 2026" 같은 표 머리글(실측 OPRT)에서
# 분기 열을 인식하지 못해 분기 값이 연간으로 분류됐다.
# (2026-08-15) '3rd Qtr' 축약(실측 MIDD)도 추가.
# (2026-08-15 3차) 반기(2H'26E·second half) 표기 추가 — 반기|연간 두 열 표(실측 DD)에서
# 반기 열을 인식 못 해 반기 값이 연간으로 태그됐다. 반기도 '연간이 아닌 기간'으로 취급.
_QRE = (r"(first|second|third|fourth)[-\s]quarter|\bQ[1-4]\b|\b[1-4]Q\b|quarter (?:of|ending)|"
        r"\b[1-4](?:st|nd|rd|th)[-\s](?:qtr|quarter)\b|three months (?:ended|ending)|"
        r"\b[12]H\s?'?\d{2}|\b(?:first|second)[-\s]half\b|"
        r"for the (?:first|second|third|fourth) quarter|next quarter|current quarter")
# (2026-08-10) 연간 표시에 **"연도 + Outlook/전망"** 형태를 추가한다. 실측 오분류:
#   AGCO "Outlook … 2026" · NFLX "Our 2026 outlook" · XRAY "2026 Outlook … net sales"
#   → 연간 가이던스인데 분기로 잡혀 분기 컨센과 비교되며 +300%대 갭이 나왔다
#     (AGCO 10,150 vs 분기 2,330 = +335% → 연간 10,179 대비 -0.3% 가 정답).
#   (2026-08-10 2차) "2026 **standalone adjusted diluted** EPS guidance"(HTO) ·
#   "2026 adjusted EPS of $8.25"(LCII) · "FY’26 Guidance"(PTC) 처럼 연도와 지표 사이에
#   수식어가 몇 개씩 끼면 종전 패턴이 못 잡아 전부 분기로 떨어졌다(+300~700% 갭).
#   규칙을 문법대로 다시 쓴다 — **분기 표시가 없는 연도가 지표를 수식하면 그 해 전체**.
#   연도와 지표 사이 수식어는 최대 4개까지 허용한다.
_YMET = r"(?:guidance|outlook|eps|earnings per share|earnings|revenues?|net sales|sales)"
#  FY26 · FY’26 · FY 2026 셋 다 인정한다(실측 RGEN "FY26 … adjusted EPS to $2.03-$2.09" 가
#  연도 표기로 잡히지 않아 통째로 기각됐다).
_YRE = (r"full[-\s]year|fiscal year|for the year|full fiscal|annual|FY\s?[’']?\s?\d{2}(?:\d{2})?\b|"
        r"\b20\d\d\b(?=(?:\s+[A-Za-z’'\-]+){0,4}\s+" + _YMET + r"\b)|"
        r"\b20\d\d\s+(?:eps\s+|adjusted\s+)?(?:guidance|outlook)|outlook for (?:fiscal\s+)?20\d\d|"
        r"(?:guidance|outlook)\s+for\s+(?:the\s+)?full[-\s]year|"
        # "net sales **for 2026** are expected to be $10.1-$10.2 billion"(실측 AGCO) —
        # 분기 표시 없이 연도만 붙으면 그 해 **전체**를 뜻한다.
        r"(?:for|in|during|through)\s+(?:fiscal\s+|calendar\s+)?20\d\d\b")


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
#  (2026-08-10) 숫자 끝을 반드시 확정한다 — `(?![\d,.])` 가 없으면 "$890 million" 에서
#  정규식이 뒤로 물러나 **"$89"** 만 잡고 "0 million" 을 남겨, 단위 제외 규칙이 무력화된다
#  (실측 KHC 89.0 → 갭 +4,236% · VRRM 12.0 → +952%).
#  뒤에 오는 것이 '숫자' 이거나 '소수점+숫자' 면 숫자를 덜 읽은 것이다.
#  쉼표·마침표 자체는 문장부호이므로 막지 않는다("$5.60," 는 정상).
_NUM_D = r"\$\s?([\d,]+(?:\.\d+)?)(?!\d)(?!\.\d)(?!\s*(?:billion|million|bn|mm)\b)()"   # 주당 금액($)
_NUM_C = r"([\d,]+(?:\.\d+)?)(?!\d)(?!\.\d)\s*(cents?)"    # 60 cents → 0.60


def _forms(label, metric):
    """실측된 표기들 — 범위형·±금액·±퍼센트·근사형·표(Low/High)·괄호병기. EPS 는 금액 표기만.

    (2026-08-15) **치명 버그 수정**: label 을 괄호 없이 이어붙여 `A|B` 알터네이션이
    패턴 전체를 갈랐다 — "…earnings per share…" 표기는 라벨만 매칭되고 숫자 그룹이
    비어 조용히 버려졌다(약어 EPS 만 동작). 재현율 손실의 최대 단일 원인
    (실측 WWW·EAT·TRMB·YETI 등 'earnings per share' 문장 전멸).
    """
    label = r"(?:" + label + r")"
    if metric == "eps":
        return [
            ("range", label + r"[^$%]{0,60}?" + _NUM_D + r"\s*(?:to|through|-|and)\s*" + _NUM_D),
            ("rangec", label + r"[^$%]{0,60}?" + _NUM_C + r"\s*(?:to|through|-|and)\s*" + _NUM_C),
            # (2026-08-15) 괄호 병기 — "EPS guidance of 13% to 15% growth ($12.40 to $12.60)"
            # (실측 CAH). 성장률(%) 뒤 괄호 안에 금액 범위가 온다 — $ 필수라 성장률 오인 없음.
            ("prange", label + r"[^$]{0,70}?\(\s*" + _NUM_D + r"\s*(?:to|through|-|and)\s*" + _NUM_D + r"\s*\)"),
            # (2026-08-15) Low/High 두 열 표 — "Net income per share $ 0.67 $ 0.75"(실측 LFTO).
            # 구분자 없이 $ 금액 두 개가 나란히. 오탐 방지: 루프에서 back 에 'Low … High'
            # 열 머리글이 있을 때만 채택한다.
            ("lowhigh", label + r"[^$%]{0,25}?" + _NUM_D + r"\s+" + _NUM_D),
            ("approx", label + r"[^$%]{0,60}?(?:approximately|about|around)\s*" + _NUM_D),
            ("approxc", label + r"[^$%]{0,60}?(?:approximately|about|around)\s*" + _NUM_C),
        ]
    return [
        ("range", label + r"[^$%]{0,60}?" + _NUM + r"\s*(?:to|through|-|and)\s*" + _NUM),
        ("pm", label + r"[^$%]{0,60}?" + _NUM + r"\s*(?:±|\+/-|plus or minus)\s*" + _NUM),
        ("pmpct", label + r"[^$]{0,60}?" + _NUM + r"[^$]{0,20}?(?:±|\+/-|plus or minus)\s*([\d.]+)\s*%"),
        # (2026-08-15) Low/High 두 열 표 — "Revenue $ 2,115 $ 2,175"(실측 MH·GMRS·EQPT).
        # 단위는 표 머리의 '($ in millions)' 선언에서 가져온다(루프에서 처리).
        # (2차) 숫자별 단위 병기형 "$925 million $945 million"(실측 JBI — Range 헤더 표)도 커버.
        ("lowhigh", label + r"[^$%]{0,25}?\$\s?([\d,]+(?:\.\d+)?)(?!\d)\s*(billion|million|bn|mm)?\s+"
                            r"\$\s?([\d,]+(?:\.\d+)?)(?!\d)\s*(billion|million|bn|mm)?(?![\w%])"),
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
    if kind in ("range", "prange", "lowhigh"):     # (2026-08-15) 신설 2종은 그룹 구조가 같다
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


_FWD = r"guidance|outlook|expect|anticipat|forecast|project|estimat|to be in the range"

# (2026-08-15) '분기에 붙은 연도' 제외 패턴 — pick()과 다중 열 가드가 공유한다.
# "Q1 FY 2027"·"third quarter 2026"·"quarter ending September 30, 2026" 의 연도는
# 분기 소속이지 연간 표지가 아니다.
_YEXCL = (r"(?:\bquarter\b|\bQ[1-4]\b|\b[1-4]Q\b)"
          r"(?:\s+(?:of|the|ended|ending|for|fiscal|calendar|year))*"
          r"\s*(?:(?:january|february|march|april|may|june|july|august|"
          r"september|october|november|december)\s+\d{1,2}\s*,?\s*)?"
          r"(?:fiscal\s+|calendar\s+)?(?:year\s+)?$")


def _fwd_q(seg):
    """이 구간의 분기 표현이 **전망**을 가리키는가.

    (2026-08-10) 헤드라인이 마침표 없이 이어지는 보도자료에서는 한 '문장'에 지난 분기
    실적과 연간 가이던스가 함께 들어온다. 그때 "Third Quarter … EPS of \\$4.48"(실적) 이
    기간 근거로 채택돼 연간 가이던스가 분기로 분류됐다(실측 COR 17.75 → +289%,
    EW 2.95 → +307%, ILMN·AVY·FLS 등 |갭|>300% 26건). 분기 표현 근처(±60자)에
    전망을 뜻하는 말이 없으면 그 분기 표현은 근거로 쓰지 않는다.
    """
    return any(re.search(_FWD, seg[max(0, m.start() - 60):m.start() + 60], re.I)
               for m in re.finditer(_QRE, seg, re.I))


def _period(txt, start, end):
    """이 후보가 가리키는 기간 — 'Q'(분기) · 'Y'(연간) · None(확정 불가 → 기각).

    **문법 구조 우선순위**로 판정한다. 기간을 수식하는 말은 그 값에 가장 가까운 구절에
    붙어 있고, 멀리 있는 표현은 다른 내용일 뿐이다.

      ① 매칭 구절 안(라벨~숫자)  — "net sales **for 2026** are expected to be $10.1-$10.2B"
                                    (실측 AGCO: 앞 문장의 'second quarter of 2026' 이 더 가까워
                                     분기로 오분류됐다 → 구절 안이 최우선이어야 한다)
      ② 같은 문장 안             — "Our 2026 outlook … we are narrowing our revenue forecast to $51.0-$51.4B"
                                    (실측 NFLX)
      ③ 앞 400자에서 가장 가까운 표현 — 표·불릿처럼 문단 머리에 한 번만 쓰는 형식
                                    ("Outlook for the third quarter of fiscal 2027 is as follows: • Revenue …")
      ④ 그래도 없으면 뒤 90자
    어디서도 확정 못 하면 None → 채택하지 않는다(추측하지 않는다).
    """
    def pick(seg, anchor=None):
        """seg 안에서 기간 표현을 찾되, **숫자에 가장 가까운** 것을 택한다.

        (2026-08-10 수정) 예전엔 '더 뒤에 나온 표현'을 골랐는데, 뒤에 있다고 값에
        가까운 건 아니다. 실측 ABT: 헤드라인 불릿이 마침표 없이 ' - ' 로만 이어져
        한 문장으로 잡히는 바람에, 값 **뒤** 불릿의 'second quarter' 가 값 **바로 앞**
        'full-year 2026' 을 이겨 연간 가이던스 5.45~5.60 이 분기로 분류됐다
        (분기 컨센 1.42 대비 +289%). 영어는 기간 수식어가 값 앞에 오므로
        앞쪽 표현을 우선하고(뒤쪽은 거리 3배 페널티), 그중 가장 가까운 것을 쓴다.
        """
        q = [m.start() for m in re.finditer(_QRE, seg, re.I)
             if not re.search(_QPAST, seg[:m.start()][-30:], re.I)]
        # 연도 앞에 분기 표시가 붙어 있으면(“third quarter 2026” · “Q3 2026”) 그건 분기다.
        # 연도만 보고 연간으로 세면 분기 가이던스를 연간 컨센과 비교하게 된다.
        # (2026-08-10 2차) 범위를 40자로 넓힌다. "Second Quarter **Fiscal Year 2027** Guidance"
        # (FLEX) · "third quarter of **fiscal 2026**"(NET) 처럼 분기 뒤에 회계연도가 따라붙는
        # 표기가 흔한데, 25자만 보면 연도 토큰이 살아남아 분기 가이던스가 연간으로 분류된다
        # (연간 컨센과 비교돼 −75% 대 갭). 분기 낱말이 앞 40자 안에 있으면 그 연도는 분기 소속이다.
        # (2026-08-10 3차) 분기 낱말이 앞 40자 안에 '있기만 하면' 빼는 건 과했다.
        # "Reports Second Quarter 2026 Results **Reaffirms 2026 Outlook** for Adjusted EPS"(GPC)
        # 처럼 앞 문구가 지난 분기 실적이고 뒤가 연간 전망인 문장이 흔하다.
        # 분기 낱말이 연도에 **바로 붙어 있을 때만**(사이에 of/the/fiscal/공백뿐) 그 연도를
        # 분기 소속으로 본다 — "Second Quarter Fiscal Year 2027"(FLEX) · "third quarter of fiscal 2026"(NET).
        # (2026-08-14 4차) 분기와 연도 사이에 **날짜**가 끼는 표기를 허용한다.
        # "for the third quarter ending September 30, 2026 as follows:"(실측 DOCN·ALIT 계열)
        # 에서 'September 30,' 이 종전 패턴(of/the/ended… 2개)에 안 맞아 연도 '2026' 이
        # 연간 표지로 살아남았고, 값에 더 가깝다는 이유로 분기 가이던스가 연간으로 분류됐다
        # (연간 컨센과 비교돼 −74% 대 갭). 월 이름+일자를 낀 형태까지 분기 소속으로 본다.
        y = [m.start() for m in re.finditer(_YRE, seg, re.I)
             if not re.search(_YEXCL, seg[:m.start()][-60:], re.I)]
        if not q and not y:
            return None
        if anchor is None:                      # 구절 안 등 기준점이 없으면 뒤쪽 우선(종전 동작)
            if q and not y:
                return "Q"
            if y and not q:
                return "Y"
            return "Q" if max(q) > max(y) else "Y"
        d = lambda p: (anchor - p) if p <= anchor else (p - anchor) * 3
        dq = min([d(p) for p in q], default=None)
        dy = min([d(p) for p in y], default=None)
        if dq is None:
            return "Y"
        if dy is None:
            return "Q"
        # 분기·연간 표시가 값 바로 앞에 **나란히** 있으면 어느 쪽 값인지 알 수 없다.
        # 실측 PTC: "…Non-GAAP EPS Guidance | FY’26 Guidance | Q4’26 Guidance | EPS $8.46 to $9.18 | $0.94 to $1.17"
        # 은 열 머리글이 두 개 늘어선 표라, 거리로 고르면 Q4 열이 이겨 연간 값 8.46 이
        # 분기로 분류된다(+300%대). 추측하지 않고 기각한다.
        if dq <= 60 and dy <= 60:
            return None
        return "Q" if dq < dy else "Y"

    # ① 매칭 구절 안 — 여기서도 '값에 가까운 표현'이 이겨야 한다
    r0 = pick(txt[start:end], 0)
    if r0:
        return r0
    # ② 같은 문장 안 (마침표·불릿 경계)
    # (2026-08-10) 세미콜론은 경계에서 뺀다 — 세미콜론은 한 문장 안의 나열이라
    # 앞부분의 기간 표시가 뒤 항목에도 그대로 걸린다. 실측 DGX:
    # "Full year 2026 reported diluted EPS … $9.97 and $10.17; and adjusted diluted EPS
    #  expected to be between $11.05 and $11.25" — 세미콜론에서 자르면 뒤 항목이
    # 'Full year 2026' 을 못 봐 연간 11.05 가 분기로 분류된다(+300%대).
    ls = max(txt.rfind(". ", 0, start), *(txt.rfind(b, 0, start) for b in ("• ", "● ", "▪ ", "· ")))
    # (2026-08-10) 오른쪽 경계도 **다음 불릿**에서 끊는다. 예전엔 다음 마침표까지만 봐서
    # 불릿 목록이 통째로 한 문장이 됐고, 값 뒤 항목의 분기 표현이 근거로 채택돼
    # 연간 가이던스가 분기로 분류됐다(실측 ILMN·LIFE·BFLY·EW·HLT).
    # (2026-08-15) " The following " 도 오른쪽 경계로 자른다 — 보도자료가 마침표 없이
    # "…range of $0.35 to $0.49 The following revised guidance is provided for … fiscal year 2026:"
    # 처럼 다음 블록 머리글을 이어붙이면, 그 머리글의 연간 표지가 현재 행의 근거로 오인돼
    # 분기 가이던스가 연간으로 분류된다(실측 VECO Q3 Non-GAAP 0.35~0.49 가 fy_ 로 태그).
    rs = min([p for p in ([txt.find(". ", end)] +
                          [txt.find(ph, end) for ph in (" The following ", " The Company ",
                                                        " In addition", " Additionally,", " Separately,")] +
                          [txt.find(b, end) for b in ("• ", "● ", "▪ ", "· ")]) if p > 0] or [-1])
    s0 = (ls + 2 if ls > 0 else max(0, start - 400))
    sent = txt[s0:(rs if rs > 0 else min(len(txt), end + 200))]
    r1 = pick(sent, start - s0)
    if r1 == "Q" and not _fwd_q(sent):
        r1 = None                       # 지난 실적을 말하는 분기 표현이면 근거로 쓰지 않는다
    if r1:
        return r1
    # ②-b **블록 머리글** — 보도자료는 "Fiscal year 2026 guidance … we now expect:" ·
    #    "Second Quarter Fiscal Year 2027 Guidance:" 처럼 머리글을 두고 그 아래에 불릿으로
    #    항목을 나열한다. 값이 속한 블록의 머리글이 곧 그 값의 기간이다.
    #    앞 400자를 무작정 훑으면 문서 여기저기의 "Second quarter 2026 results" 같은
    #    **다른 블록 머리글**을 집어 연간 가이던스가 분기로 떨어진다(실측 ILMN·LIFE·BFLY·EW).
    #    → 값 바로 위의 머리글(콜론으로 끝나는 전망 문구)을 먼저 본다.
    #    (2026-08-15) 머리글 허용 길이 40→60자 — "guidance is provided for Veeco's third
    #    quarter 2026:"(43자) 같은 실제 머리글이 40자에 걸려 인식되지 않았다(실측 VECO).
    hs, h0 = None, max(0, start - 800)
    for hm in re.finditer(r"(?:guidance|outlook|expects?|expectations|anticipates?)"
                          r"[^.•●▪:]{0,60}:", txt[h0:start], re.I):
        hs = hm                                   # 가장 가까운(=마지막) 머리글
    if hs:
        seg = txt[max(0, h0 + hs.start() - 130):h0 + hs.end()]
        r15 = pick(seg, len(seg))                 # 머리글 끝(콜론)에 가장 가까운 표현
        if r15 == "Q" and not _fwd_q(seg):
            r15 = None
        if r15:
            return r15
    # ③ 앞 문맥 400자 — 가장 가까운 표현.
    #    단, 여기서 나온 **분기 표시는 전망 문맥일 때만** 인정한다. 문단 머리의
    #    "Outlook for the third quarter of fiscal 2027 is as follows:" 는 정당하지만,
    #    멀리 있는 "second quarter results" 같은 지난 실적 언급까지 기간 근거로 쓰면
    #    연도 표시가 없는 연간 가이던스가 분기로 떨어진다(실측 EW 2.95 → 분기 컨센 대비 +324%).
    b0 = max(0, start - 400)
    seg3 = txt[b0:end]
    r2 = pick(seg3, start - b0)
    if r2 == "Q" and not _fwd_q(seg3):
        r2 = None
    if r2:
        return r2
    # ④ 뒤 90자
    return pick(txt[end:end + 90])


def parse_guidance(txt, per_hint=None):
    """보도자료 평문 → {rev_lo,rev_hi,eps_lo,eps_hi, fy_*} + _ev(근거) + _skip(기각 사유).

    per_hint ('Y'|'Q'|None): **회사별 프로필 힌트** (2026-08-15). Benzinga 이력(2022~)에서
    이 회사가 한 종류 기간만 제시해 왔음이 확인되면(예: 연간만 90%+, 4회 이상),
    문맥에서 기간을 확정하지 못해 버리던 후보를 그 기간으로 구제한다.
    다중 열 표 기각에는 적용하지 않는다(열 구조가 있으면 두 기간이 공존한다는 뜻).
    """
    out, ev, skip = {}, {}, []
    if not txt:
        return out

    def add(metric, per, lo, hi, ctx, basis=None):
        pre = "" if per == "Q" else "fy_"
        if pre + metric + "_lo" in out:
            # (2026-08-14) 같은 기간에 이미 값이 있어도, 기존이 기준 미명시(unspec)이고
            # 새 후보가 명시적 **조정(adj)** 기준이면 교체한다. 보도자료가 "diluted EPS
            # $A–$B, and adjusted EPS $C–$D" 로 나란히 쓰면 먼저 나온 GAAP-성격 값이
            # 선점해 조정 컨센과 비교돼 갭이 틀어졌다(실측 ROK 12.87→13.15 정답 ·
            # INGR 9.45→10.6 · TKR 3.90→6.20 · DORM 8.08→8.65 — 전부 조정 쪽이 정답).
            if not (metric == "eps" and basis == "adj"
                    and out.get(pre + "eps_basis") != "adj"):
                return
        else:
            # (2026-08-10) 같은 수치가 이미 **다른 기간**으로 등록돼 있으면 무시한다.
            # 한 회사의 같은 숫자가 분기이면서 동시에 연간일 수는 없다 — 같은 문장이 본문에
            # 두 번 나오는데 한쪽에만 연도가 붙은 경우다(실측 IDXX: "Increases 2026 EPS
            # outlook to $14.69"(연간) 와 "updated its EPS outlook range to $14.69"(연도 없음)
            # → 뒤엣것이 분기로 잡혀 분기 컨센 대비 +340%). 값 기반 '교정'이 아니라 중복 제거다.
            # 값이 완전히 같지 않아도 ±5% 안이면 같은 항목이다(실측 COR: 연간 17.70~17.90 과
            # 17.75~17.95 — 표와 헤드라인의 반올림 차이). 분기 EPS 가 연간 EPS 와 5% 이내로
            # 붙는 일은 실무상 없으므로, 이 경우 뒤늦게 잡힌 쪽을 버린다.
            other = ("fy_" if pre == "" else "") + metric
            ol, oh = out.get(other + "_lo"), out.get(other + "_hi")
            if ol and oh and lo and hi and abs(lo / ol - 1) <= 0.05 and abs(hi / oh - 1) <= 0.05:
                return
        out[pre + metric + "_lo"], out[pre + metric + "_hi"] = (
            (lo, hi) if metric == "rev" else (round(lo, 2), round(hi, 2)))
        if basis:
            out[pre + metric + "_basis"] = basis
        ev[pre + metric] = re.sub(r"\s+", " ", ctx)[:400]

    # (2026-08-10) 설비투자(CapEx) 가이던스 추가 — 회사가 제시할 때만 채운다.
    # 애널리스트 CapEx 컨센서스는 무료로 구할 수 없어(FMP·Yahoo·Massive 모두 없음),
    # 회사 발표가 유일한 근거다. 없으면 화면에 '미제시'로 둔다(추정하지 않는다).
    # (2026-08-15) EPS 라벨 확장 — "Net income per (diluted|common) share" 표기(실측 LFTO·KLC·EAT).
    # 보통주 주당 순이익 = EPS 다. 'loss per share' 는 제외(음수 전용 표기, 컨센 비교 부적합).
    # (2차) "Earnings per **diluted** share"(실측 미매칭 표본) — 어순이 바뀐 표기도 흔하다.
    for metric, label in (("rev", r"(?:revenues?|net sales)"),
                          ("eps", r"(?:diluted\s+)?earnings per (?:diluted\s+|common\s+)?share|\beps\b|"
                                  r"net income per (?:diluted\s+|common\s+)?share(?:s)?(?:\s*,\s*diluted)?"),
                          ("capex", r"(?:capital expenditures?|\bcapex\b)")):
        for kind, pat in _forms(label, metric):
            for m in re.finditer(pat, txt, re.I):
                lo, hi = _pair(kind, m)
                if lo is None or hi is None:
                    continue
                # (2026-08-15) Low/High 두 열 표 형식은 **열 머리글이 실제로 있을 때만** 믿는다
                # — 구분자 없는 숫자 나열은 다른 표(실적 비교 등)에서도 흔해 오탐 위험이 크다.
                back300 = txt[max(0, m.start() - 300):m.start()]
                if kind == "lowhigh":
                    _lh = re.search(r"\blow\b[\s\S]{0,40}?\bhigh\b", back300, re.I)
                    # (2026-08-15 2차) 숫자마다 단위가 병기된 형태("$925 million $945 million")는
                    # Low/High 머리글이 없어도 back 에 'Range' 표기가 있으면 범위로 인정한다
                    # (실측 JBI — 'Range Year-Over-Year Growth' 머리글 표). 단위 없는 맨몸 숫자는
                    # 실적 비교 표(당기|전기)와 구별이 안 되므로 Low/High 머리글을 계속 요구한다.
                    _units = bool((m.group(2) or "") and (m.group(4) or ""))
                    if not _lh and not (_units and re.search(r"\brange\b", back300, re.I)):
                        continue
                # (2026-08-15) Low·Midpoint·High **3열** 표(실측 CCSI) — 앞 두 값(하단·중간)이
                # 아니라 첫·셋째 값(하단·상단)이 범위다.
                if kind == "lowhigh" and re.search(r"\blow\b[\s\S]{0,25}?\bmid", back300, re.I):
                    m5 = re.match(r"\s*\$?\s?([\d,]+(?:\.\d+)?)(?!\d)", txt[m.end():m.end() + 20])
                    v5 = _num(m5.group(1), None) if m5 else None
                    if v5 is not None:
                        hi = v5
                # 앞 문맥은 용도별로 길이를 달리한다 — 기간·기준은 넓게(130자), 지표 수식어는
                # 좁게(60자) 봐야 한다. 넓게 보면 **직전 문장**의 'organic·acquired' 같은 단어가
                # 딸려 들어와 멀쩡한 전사 매출까지 기각된다(실측 WAT 'Total Company reported revenue').
                back = txt[max(0, m.start() - 130):m.start()]     # 기간·기준 판정용
                near = txt[max(0, m.start() - 60):m.start()]      # 지표 수식어 판정용
                ctx = txt[max(0, m.start() - 130):min(len(txt), m.end() + 40)]
                # (2026-08-15) 전망 문맥 창 130→300자 — 불릿 목록은 guidance/outlook 이 목록
                # **머리글**에 한 번만 나오고 각 항목엔 없다. 130자로는 머리글에 못 미쳐
                # 정당한 가이던스가 통째로 조용히 버려졌다(실측 UPWK "guidance for … is: •
                # Revenue: $730-750M" — 머리글이 135자 앞 · YETI "Update on 2026 Outlook" 블록).
                if not re.search(_FORE, back300 + txt[m.start():min(len(txt), m.end() + 40)], re.I):
                    continue                                       # 전망 문맥 아님 → 조용히 통과
                # (2026-08-10) 라벨과 숫자 사이에 **다른 항목**이 끼어 있으면 그 숫자는
                # 그 항목의 것이다. 실측:
                #   TTMI "…of net sales in the third quarter and R&D expenditures … interest
                #         expense of approximately $11.3 million" → 이자비용을 매출로 채택(−99%)
                #   PWR  "…$1.2 billion - $1.4 billion of revenues and approximately $120 million
                #         to $140 million of adjusted EBITDA" → EBITDA 를 매출로 채택(−99.7%)
                # (2026-08-15) lead 는 **라벨 끝**부터 잰다 — 라벨 자체에 든 단어가 _OTHER 에
                # 걸리면 안 된다(실측 KLC·LFTO: 라벨 'net income per share' 의 'net income' 이
                # _OTHER 의 net income 과 충돌해 정당한 EPS 가이던스가 전부 기각됐다).
                lm_ = re.match(r"(?:" + label + r")", txt[m.start():], re.I)
                lead = re.split(r"\$", txt[m.start() + (lm_.end() if lm_ else 0):m.end()], 1)[0]
                # 금액 뒤 60자도 본다 — "…$120 million to $140 million **of adjusted EBITDA**"
                # 처럼 범위 뒤에 항목명이 오는 표기가 흔하다(실측 PWR).
                tail = txt[m.end():m.end() + 60]
                # CapEx 는 라벨 자체가 'capital expenditures' 라 _OTHER 에 걸린다 — 제외
                bad = None if metric == "capex" else (_OTHER_HIT(lead) if re.search(_OTHER, lead, re.I)
                       else (_OTHER_HIT(tail) if re.search(
                           r"^[^.•]{0,60}?\b(?:of|in)\s+(?:adjusted\s+|non-gaap\s+)?" + _OTHER,
                           tail, re.I) else None))
                if bad:
                    skip.append(f"{metric}: 숫자가 다른 항목({bad})의 것 · {ctx[:110]}")
                    continue
                # 증분·기여분은 수준(level)이 아니다 — 가이던스 값으로 쓰면 안 된다. 실측:
                #   WEX "increased 2026 revenue and EPS guidance **by** approximately $32 million"
                #   INCY "Estimated **impact** on … net sales from improved GTN $40 - $50 million"
                # (2026-08-15 3차) 검사 창을 lead 자체로 교정 — lead 정의를 '라벨 끝부터'로
                # 바꾸면서 옛 슬라이스(m.start()+len(lead))가 엉뚱한 위치를 가리켜 증분/영향
                # 표현이 통째로 새기 시작했다(실측 PRGO 'EPS impact of ~$0.60' · TXT 'impacted
                # by $0.20-0.30' · WEX 'increasing revenue by ~$17M' 재발).
                if re.search(r"\b(?:by|impact(?:ed|s)? (?:on|of)|contribut\w*|incremental|"
                             r"headwind|tailwind|benefit of|reduc\w* by|increas\w* by)\b\s*"
                             r"(?:approximately\s+|about\s+|around\s+)?$",
                             lead[-45:], re.I) or \
                   re.search(r"estimated impact|impact on", ctx, re.I):
                    skip.append(f"{metric}: 증분·기여분 표현(수준 아님) · {ctx[:110]}")
                    continue
                # (2026-08-15 2차) **분기|연간 다중 열 표** — 머리글에 분기·연간이 나란히 있고
                # 라벨 뒤에 금액 범위가 연달아 오면, 각 범위가 어느 열(기간) 것인지 문장
                # 규칙으로는 확정할 수 없다. 추측하면 반드시 틀린다(실측 MIDD·ATI·AKAM·ASTH·
                # AIP·CGNX: 분기 열 값이 연간으로 태그돼 연간 컨센과 비교 → −60~−75% 갭).
                # 정밀도 원칙대로 기각한다 — 이런 표는 추후 표 파서(guidance_table)의 몫.
                # (2026-08-15 3차) 연간 마커는 '분기에 붙은 연도'(Q1 FY 2027 등)를 제외하고 센다
                # — 안 그러면 단일 분기 표("Q1 FY 2027 Guidance")까지 다중 열로 오인해
                # 정상 후보를 죽인다(실측 CSCO Non-GAAP EPS 기각 → GAAP 값이 대신 채택).
                _ys = [mm.start() for mm in re.finditer(_YRE, back300, re.I)
                       if not re.search(_YEXCL, back300[:mm.start()][-60:], re.I)]
                if kind in ("range", "lowhigh") and _ys and \
                   re.search(_QRE, back300, re.I) and \
                   re.search(r"^[^.•●%]{0,45}?(?:\$\s?[\d,]+|[\d,]+(?:\.\d+)?\s*(?:billion|million|bn|mm)\b)",
                             txt[m.end():m.end() + 55], re.I):
                    skip.append(f"{metric}: 분기|연간 다중 열 표(열 확정 불가) · {ctx[:110]}")
                    continue
                # (2026-08-14) 장기 목표(long-term outlook/target)는 올해·다음 분기 가이던스가
                # 아니다 — 컨센과 비교하면 반드시 어긋난다(실측 EOLS "Reaffirms 2028 Long-Term
                # Financial Outlook … $450-500M" 을 올해 매출로 채택 → +42%).
                if re.search(r"long[-\s]term\s+(?:financial\s+)?(?:outlook|guidance|target|model|goal)",
                             ctx, re.I):
                    skip.append(f"{metric}: 장기 목표(당기 가이던스 아님) · {ctx[:110]}")
                    continue
                # (2026-08-14) 라벨과 숫자 사이에 **반대편 지표**가 끼면 그 숫자는 그쪽 것이다.
                # 실측 LINC: "(… except … diluted EPS) Low High Revenue $590.0 - $600.0" 에서
                # 괄호 속 'EPS' 라벨이 매출 590~600 을 EPS 로 채택(595.00 — 자릿수부터 불가능).
                if metric == "eps" and re.search(r"\brevenues?\b|\bnet sales\b|\bexcept\b", lead, re.I):
                    skip.append(f"eps: 라벨~숫자 사이에 매출 표현 → 매출 값 · {ctx[:110]}")
                    continue
                if metric == "rev" and re.search(r"\beps\b|earnings per share|per[-\s]share", lead, re.I):
                    skip.append(f"rev: 라벨~숫자 사이에 EPS 표현 → EPS 값 · {ctx[:110]}")
                    continue
                # (2026-08-14) 'Prior/Previous … Updated/Revised …' 두 열 표 — 라벨 뒤 첫 범위는
                # **직전(구) 가이던스**다. 머리글에 prior 가 updated 보다 먼저 나오고 범위가
                # 연달아 두 개면 뒤(개정) 범위를 쓴다(실측 KTB 5.20→5.30 정답 · CTEV 992.5→1,010 ·
                # ELF 1,850→1,953 · INDV 1,250→1,330 · FBIN 3.15→3.37 — 전부 개정 열이 정답).
                # SUPN 처럼 'Current … Previous …' 순서(개정이 먼저)면 첫 범위가 맞으므로 그대로 둔다.
                if kind == "range":
                    hdr = txt[max(0, m.start() - 300):m.start()]
                    # (2026-08-15) 'Initial … Outlook / Current … Outlook'(실측 PBH)도 구→신 표기다.
                    pm_ = re.search(r"\b(?:prior|previous|initial)\b[^.•●]{0,80}?(?:guidance|outlook)", hdr, re.I)
                    # (2026-08-14 2차) updated-마커는 **prior 마커 뒤에서만** 찾는다 — 표 제목의
                    # "Full Year 2026 Outlook Update …" 같은 문구가 updated 로 먼저 잡히면
                    # 순서 판정(prior 먼저)이 뒤집혀 규칙이 통째로 무시된다(실측 KTB).
                    # (2026-08-15 2차) 'Guidance - Previous | Guidance - Updated'(실측 STLN)처럼
                    # 한정어가 guidance 뒤에 붙는 표기는 prior 뒤의 updated/revised/current
                    # 낱말만으로 인정한다(guidance 낱말 재요구 시 놓침).
                    um_ = pm_ and re.search(r"\b(?:updated?|revised?|current)\b", hdr[pm_.end():], re.I)
                    if pm_ and um_:
                        n2 = _NUM_D if metric == "eps" else _NUM
                        m2 = re.match(r"[^$\d%]{0,30}?" + n2 + r"\s*(?:to|through|-|and)\s*" + n2,
                                      txt[m.end():m.end() + 90], re.I)
                        if m2:
                            h2 = (m2.group(4) or m2.group(2) or "").lower() if metric != "eps" else None
                            lo2 = _num(m2.group(1), None if metric == "eps" else m2.group(2), h2)
                            hi2 = _num(m2.group(3), None if metric == "eps" else m2.group(4), h2)
                            if lo2 is not None and hi2 is not None:
                                lo, hi = lo2, hi2
                                ctx += " [개정 열 채택: %s~%s]" % (m2.group(1), m2.group(3))
                # (2026-08-14) '가이던스를 A에서 B로 상향/하향' — "raising … guidance from $A to $B"
                # 의 from~to 는 범위가 아니라 **개정**(A=구, B=신)이다(실측 HYLN "Increasing …
                # guidance from $10 million to $15 million" 을 범위 10~15 로 읽어 12.5 표시 —
                # 정답은 새 가이던스 15). "from 구범위 to 신범위" 꼴(실측 CTOS)이면 신범위를 쓴다.
                if kind == "range" and re.search(r"\bfrom\s+(?:a\s+range\s+of\s+)?$", lead[-22:], re.I) and \
                   re.search(r"\b(?:increas\w+|rais\w+|lower\w+|updat\w+|revis\w+|narrow\w+|cut\w+)\b",
                             back + lead, re.I):
                    n2 = _NUM_D if metric == "eps" else _NUM
                    # (2026-08-15) "from a range of A to B **to a range of** C to D"(실측 ICUI)
                    m2 = re.match(r"\s*to\s*(?:a\s+range\s+of\s+)?" + n2 +
                                  r"(?:\s*(?:to|through|-|and)\s*" + n2 + r")?",
                                  txt[m.end():m.end() + 90], re.I)
                    if m2:                                   # from [구범위] to [신범위/값]
                        if metric == "eps":
                            a, b = _num(m2.group(1), None), (_num(m2.group(3), None)
                                                             if m2.group(3) else None)
                        else:
                            h2 = (m2.group(4) or m2.group(2) or "").lower()
                            a = _num(m2.group(1), m2.group(2), h2)
                            b = _num(m2.group(3), m2.group(4), h2) if m2.group(3) else None
                        if a is not None:
                            lo, hi = (a, b) if b is not None else (a, a)
                            ctx += " [from→to 개정: 신 가이던스 채택]"
                    else:                                    # from A to B 자체가 매치된 경우 → B
                        lo = hi
                        ctx += " [from→to 개정: 새 값(B)만 채택]"
                # (2026-08-14) '범위의 상단/하단' 명시 — "at the high-end of the range of $8.4-$8.6"
                # 은 중간값이 아니라 상단이다(실측 GPK 8,500→8,600 정답 · AIRS 154→151 정답).
                em_ = re.search(r"\b(?:at|toward|towards|near)\s+the\s+"
                                r"(high(?:er)?|upper|top|low(?:er)?|bottom)[-\s]end\b",
                                back + lead, re.I)
                if em_:
                    if em_.group(1).lower()[0] in ("h", "u", "t"):
                        lo = hi
                    else:
                        hi = lo
                per = _period(txt, m.start(), m.end())
                if not per and per_hint:
                    # (2026-08-15) 회사 프로필 구제 — 이 회사는 이력상 한 종류 기간만 제시
                    per = per_hint
                    ctx += " [기간: 회사 프로필(이력상 %s만 제시)]" % ("연간" if per_hint == "Y" else "분기")
                if not per:
                    skip.append(f"{metric}: 기간 미명시(분기/연간 확정 불가) · {ctx[:130]}")
                    continue
                if metric == "capex":
                    # 단위 표기가 있어야 자릿수를 확정할 수 있다(주당 금액이 아니다)
                    if not re.search(r"(billion|million|bn|mm)\b|\$\s?[\d,.]+\s*[BM]\b", ctx):
                        skip.append(f"capex: 단위 미표기 · {ctx[:110]}")
                        continue
                    if not (0 < lo <= hi and lo > 1e5 and hi / lo < 3):
                        skip.append(f"capex: 범위 비정상({lo:.0f}~{hi:.0f}) · {ctx[:110]}")
                        continue
                    add("capex", per, lo, hi, ctx)
                elif metric == "rev":
                    if re.search(_PART, near, re.I):
                        skip.append(f"rev: 전사 아님(부분 지표) · {ctx[:130]}")
                        continue
                    # (2026-08-15) 라벨 직전에 ®·™ 상표 표기가 붙으면 **제품 매출**이다
                    # (실측 IRWD "LINZESS® revenue guidance" — 제품 매출을 전사 컨센과
                    # 비교해 +866%). 전사 매출 앞에 상표 기호가 오는 경우는 없다.
                    if re.search(r"[®™]\s*(?:\([^)]{0,20}\))?\s*$", near):
                        skip.append(f"rev: 상표(®·™) 제품 매출 → 전사 아님 · {ctx[:110]}")
                        continue
                    # (2026-08-15) "Revenue **from sales of Captisol**"(실측 LGND) — 라벨 뒤에
                    # 제품·원천 한정이 붙으면 전사 매출이 아니다.
                    # (3차) "revenue expectation **for our COVID-19 products**, down to ~$4B"
                    # (실측 PFE — 제품군 매출 40억을 전사 615억과 비교해 −93%) 도 같은 부류.
                    if re.search(r"\bfrom\s+(?:the\s+)?(?:sales?\s+of|royalt)|\bproducts?\b", lead, re.I):
                        skip.append(f"rev: 제품·원천 한정 → 전사 아님 · {ctx[:110]}")
                        continue
                    mw = None
                    for mw in re.finditer(r"([A-Za-z][\w\-]*)\s+(?:revenues?|net sales)", near + " revenue", re.I):
                        pass
                    if mw and re.sub(r"[^a-z]", "", mw.group(1).lower()) not in _CORP_W:
                        skip.append(f"rev: 수식어 '{mw.group(1)}' → 전사 아님 · {ctx[:120]}")
                        continue
                    # (2026-08-15) 표 머리의 '($ in millions)' 선언 인정 — 표 형식은 단위를
                    # 머리에 한 번만 쓰고 숫자는 맨몸("3,870 - 3,970")으로 나열한다(실측
                    # MWH·OCTV·AEBI·MH·GMRS·EQPT). 숫자별 단위를 요구하면 전부 기각됐다.
                    tblu = re.search(r"\(\s*(?:\$\s*)?in\s+(million|billion)s?\b", back300 + ctx, re.I)
                    if not re.search(r"(billion|million|bn|mm)\b|\$\s?[\d,.]+\s*[BM]\b", ctx) and not tblu:
                        skip.append(f"rev: 단위 미표기 → 자릿수 확정 불가 · {ctx[:120]}")
                        continue
                    if tblu and lo < 1e5:                  # 맨몸 숫자 → 머리 선언 단위로 환산
                        mult = 1e9 if tblu.group(1).lower() == "billion" else 1e6
                        lo, hi = lo * mult, hi * mult
                    if not (0 < lo <= hi and lo > 1e5 and hi / lo < 1.6):
                        skip.append(f"rev: 범위 비정상({lo:.0f}~{hi:.0f}) · {ctx[:120]}")
                        continue
                    add("rev", per, lo, hi, ctx)
                else:
                    # 회계 기준 판정은 **가까운 것부터** 본다.
                    # 넓은 ctx 하나로 판정하면 GAAP↔non-GAAP 조정표에서 두 단어가 함께 잡혀
                    # GAAP 값이 조정값으로 오인된다(실측 AMGN: "Reconciliation of GAAP EPS
                    # Guidance to Non-GAAP EPS Guidance / GAAP diluted EPS guidance $15.80-$17.08"
                    # → 조정 컨센 22.9 대비 −28% 로 잘못 표시). 숫자 바로 앞 라벨(near)이
                    # 기준을 명시하면 그것이 결론이고, 침묵할 때만 넓은 문맥으로 넘어간다.
                    def _basis(seg):
                        a = bool(re.search(_ADJ, seg, re.I))
                        g = bool(re.search(_GAAP, seg, re.I))
                        return "adj" if (a and not g) else ("gaap" if (g and not a) else None)
                    # (2026-08-15) REIT 가드 — FFO 를 쓰는 리츠의 'net income per share' 가이던스는
                    # FFO 기반 컨센서스와 비교할 수 없다(실측 O 1.60 vs 컨센 FFO 4.45 ·
                    # PK 0.40 vs 1.95 · UE 0.59 vs 1.52 — 전부 리츠).
                    if re.search(r"\bFFO\b|funds from operations", back300 + ctx, re.I):
                        skip.append(f"eps: REIT(FFO 기반) — EPS 는 FFO 컨센과 비교 불가 · {ctx[:110]}")
                        continue
                    # (2026-08-15) ctx(값 **뒤** 40자 포함)로 기준을 판정하지 않는다 —
                    # "diluted EPS $1.48-$1.58 and **adjusted** diluted EPS $1.55-$1.65" 에서
                    # 앞(GAAP성) 값이 뒤 항목의 'adjusted' 를 끌어와 adj 로 오인, 진짜 조정
                    # 값의 교체(add 오버라이드)까지 막았다(실측 WWW). 기준은 값 **앞** 문맥만.
                    # lead(라벨~숫자 사이)가 가장 가깝다 — "Earnings per Share: GAAP: $1.08"(실측
                    # CSCO)의 GAAP 표기는 lead 에만 있다.
                    bas = _basis(lead) or _basis(near) or _basis(back)
                    # (2026-08-15) "…$30.00 to $31.00, **or $34.25 to $35.25 on an adjusted basis**"
                    # (실측 PH) · "GAAP: $1.08-$1.10; **Non-GAAP: $1.32-$1.34**"(실측 CSCO) —
                    # 조정 값이 바로 뒤에 병기되면 그쪽이 컨센 비교 대상이다.
                    t0 = txt[m.end():m.end() + 100]
                    m3 = (re.match(r"\s*,?\s*or\s*" + _NUM_D + r"\s*(?:to|-|and)\s*" + _NUM_D +
                                   r"\s*on an adjusted basis", t0, re.I) or
                          re.match(r"\s*[;,]?\s*Non-GAAP:?\s*" + _NUM_D + r"\s*(?:to|-|and)\s*" + _NUM_D,
                                   t0, re.I))
                    if m3:
                        a3, b3 = _num(m3.group(1), None), _num(m3.group(3), None)
                        if a3 is not None and b3 is not None:
                            lo, hi, bas = a3, b3, "adj"
                            ctx += " [병기된 조정 값 채택]"
                    # (2026-08-14) "reported (diluted) EPS" 는 GAAP 기준이다 — 보도자료가
                    # "reported EPS $A–$B and adjusted EPS $C–$D" 로 나란히 쓸 때 reported 쪽이
                    # 기준 미명시로 통과돼 조정 컨센과 비교됐다(실측 INGR 9.45(GAAP) vs 조정 10.6 ·
                    # DGX 10.07(reported) vs 조정 11.15).
                    if bas is None and re.search(r"\breported\s+(?:diluted\s+)?$", near, re.I):
                        bas = "gaap"
                    if bas == "gaap":
                        skip.append(f"eps: GAAP 기준 → 조정 컨센과 비교 불가 · {ctx[:130]}")
                        continue
                    adj = bas == "adj"
                    # (2026-08-14) 상한 1000→150 — 미국 상장사에 EPS 가이던스 150달러 이상은
                    # 실존하지 않는다. 자릿수 오인(매출을 EPS 로 읽는 사고, 실측 LINC 595.00)의
                    # 마지막 방어선.
                    if not (-100 < lo <= hi < 150):
                        skip.append(f"eps: 값 범위 비정상({lo}~{hi}) · {ctx[:120]}")
                        continue
                    add("eps", per, lo, hi, ctx, "adj" if adj else "unspec")
    if ev:
        out["_ev"] = ev
    if skip:
        out["_skip"] = skip[:20]
    return out
