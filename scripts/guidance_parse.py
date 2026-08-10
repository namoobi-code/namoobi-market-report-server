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
# 라벨(매출·EPS)과 금액 사이에 이런 말이 끼면, 그 금액은 **다른 항목**의 것이다.
_OTHER = (r"\b(?:expense|expenditures?|capex|capital expenditure|interest|tax|"
          r"ebitda|ebit|operating income|net income|cash flow|free cash|"
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
_QRE = (r"(first|second|third|fourth)[-\s]quarter|\bQ[1-4]\b|quarter (?:of|ending)|"
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


_FWD = r"guidance|outlook|expect|anticipat|forecast|project|estimat|to be in the range"


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
        y = [m.start() for m in re.finditer(_YRE, seg, re.I)
             if not re.search(r"(?:\bquarter\b|\bQ[1-4]\b)"
                              r"(?:\s+(?:of|the|ended|ending|for)){0,2}\s*(?:fiscal\s+|calendar\s+)?"
                              r"(?:year\s+)?$", seg[:m.start()][-40:], re.I)]
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
    rs = min([p for p in ([txt.find(". ", end)] +
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
    hs, h0 = None, max(0, start - 800)
    for hm in re.finditer(r"(?:guidance|outlook|expects?|expectations|anticipates?)"
                          r"[^.•●▪:]{0,40}:", txt[h0:start], re.I):
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


def parse_guidance(txt):
    """보도자료 평문 → {rev_lo,rev_hi,eps_lo,eps_hi, fy_*} + _ev(근거) + _skip(기각 사유)."""
    out, ev, skip = {}, {}, []
    if not txt:
        return out

    def add(metric, per, lo, hi, ctx, basis=None):
        pre = "" if per == "Q" else "fy_"
        if pre + metric + "_lo" in out:
            return
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
    for metric, label in (("rev", r"(?:revenues?|net sales)"),
                          ("eps", r"(?:diluted\s+)?earnings per share|\beps\b"),
                          ("capex", r"(?:capital expenditures?|\bcapex\b)")):
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
                # (2026-08-10) 라벨과 숫자 사이에 **다른 항목**이 끼어 있으면 그 숫자는
                # 그 항목의 것이다. 실측:
                #   TTMI "…of net sales in the third quarter and R&D expenditures … interest
                #         expense of approximately $11.3 million" → 이자비용을 매출로 채택(−99%)
                #   PWR  "…$1.2 billion - $1.4 billion of revenues and approximately $120 million
                #         to $140 million of adjusted EBITDA" → EBITDA 를 매출로 채택(−99.7%)
                lead = re.split(r"\$", txt[m.start():m.end()], 1)[0]   # 라벨~첫 금액 사이
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
                if re.search(r"\b(?:by|impact(?:ed|s)? (?:on|of)|contribut\w*|incremental|"
                             r"headwind|tailwind|benefit of|reduc\w* by|increas\w* by)\b\s*"
                             r"(?:approximately\s+|about\s+|around\s+)?$",
                             txt[max(0, m.start()):m.start() + lead.__len__()][-45:], re.I) or \
                   re.search(r"estimated impact|impact on", ctx, re.I):
                    skip.append(f"{metric}: 증분·기여분 표현(수준 아님) · {ctx[:110]}")
                    continue
                per = _period(txt, m.start(), m.end())
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
                    bas = _basis(near) or _basis(back) or _basis(ctx)
                    if bas == "gaap":
                        skip.append(f"eps: GAAP 기준 → 조정 컨센과 비교 불가 · {ctx[:130]}")
                        continue
                    adj = bas == "adj"
                    if not (-100 < lo <= hi < 1000):
                        skip.append(f"eps: 값 범위 비정상({lo}~{hi}) · {ctx[:120]}")
                        continue
                    add("eps", per, lo, hi, ctx, "adj" if adj else "unspec")
    if ev:
        out["_ev"] = ev
    if skip:
        out["_skip"] = skip[:20]
    return out
