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

성장률→금액 환산은 도입하지 않는다 (2026-08-16 실측 검토 결론)
------------------------------------------------------------
"revenue growth of 29-30%" 처럼 **성장률만** 제시하는 회사가 있다(실측 FIS·BIO·HAS·
ADP·FLYW). Benzinga 는 이를 전년 실적에 곱해 금액으로 채워 넣는다. 우리도 같은 환산을
할지 따져 본 결과 — **하지 않는다**. 근거(90일 창 실측):

  · 미확보 526건 중 BZ 금액이 8-K 원문에 실제로 있는 것 280건(53%) → 파서 개선 몫.
    원문에 없는 것(환산·콜 전용) 246건(46%).
  · 그 246건의 'BZ값 vs 컨센' 갭은 중앙 0.6% · |갭|<1% 62% · <3% 82%.
    즉 환산값을 넣어도 화면의 가이던스 갭은 **거의 0** 이라 신호가 되지 않는다.
    (컨센 자체가 회사 성장률 가이던스를 이미 반영하므로 구조적으로 수렴한다)
  · |갭|>5% 인 12%는 대부분 EPS(TTWO +189% · AAL −100% · MBC −118%)인데, 흑자전환·
    GAAP↔조정·FX 기준 차이가 섞여 **환산 오차와 진짜 신호를 구분할 수 없다**.

결론: 환산은 '값을 채우는 것'이지 '정보를 늘리는 것'이 아니다. 정밀도 원칙(원문에
없는 수치는 만들지 않는다)을 유지하고, 남은 재현율은 원문에 금액이 실재하는 280건
(다중 열 표·세로형 표 등)을 파서로 회수해 확보한다.
"""
import re

_MULT = {"billion": 1e9, "bn": 1e9, "b": 1e9, "million": 1e6, "mm": 1e6, "m": 1e6}
_NUM = r"\$?\s?([\d,]+(?:\.\d+)?)\s*(billion|million|bn|mm|b|m)?"

# 전망을 말하는 문맥에서만 숫자를 취한다(과거 실적 서술 배제)
_FORE = r"expect|guidance|outlook|anticipat|forecast|project|estimat"
# 부분 지표 — 전사 매출이 아님
_PART = (r"segment|product line|service revenue|subscription|recurring|licen[cs]|advertis|"
         r"organic|acquired business|supplemental|divisional|by region|geograph|"
         r"drug discovery|software revenue|hardware|instrument|QCT|QTL|QSI|"
         # (2026-08-15 5차) 개별 시설·자산 매출 — "we expect **this facility** to generate
         # total annual revenue of approximately $75 million"(실측 CXW: 신규 수용시설 1곳의
         # 매출 75M 이 전사 연간 매출로 채택돼 컨센 2B 대비 −97%).
         r"facilit(?:y|ies)|this property|per location|"
         # (2026-08-21) 동일 점포·동일 주택 기준 지표는 전사 실적이 아니다 —
         # 실측 AMH(American Homes 4 Rent): 'Same-Home Core revenues growth 1.25% - 3.25%'
         # 가 전사 매출 성장률로 채택됐다. 리츠·유통이 흔히 쓰는 표기다.
         r"same[\s-]?(?:home|store|property|community|center)|comparable\s+(?:store|restaurant|sales)")
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
           "revised", "revises", "revising", "reaffirms", "reaffirmed", "maintains", "high", "low",
           # (2026-08-16) 미확보 641건 감사에서 **정당한 전사 매출인데 기각**된 수식어들 —
           # 전부 전망·개정 동사이거나 표시 기준 수식이라 '부분 지표'와 무관하다.
           #   개정·유지 표현: FSLR "Unchanged" · PRCT "reiterates" · LII "reaffirming" ·
           #     SWIM "Original" · HNST/LDOS "Prior" · SVV "Previous" · AD "Narrowed" ·
           #     KOP "Actual"(전년 실적 열 머리글 뒤의 가이던스 열)
           #   전망 동사: RSKD "anticipate" · RDW "forecasting" · INSP "announced" · CDNA "Quarter"
           #   기준 수식: FIS "Adjusted" · BIO "currency-neutral" · FLYW "FX-Neutral" ·
           #     CBRS "Core"(= core revenue 는 전사 기준 표기) · HIPO "M"(단위 접미)
           # 판정 원칙은 그대로다 — 이 낱말들은 '전사 아님'의 근거가 못 될 뿐,
           # 부분 지표 정규식(_PART)·다른항목(_OTHER)·기간 규칙은 변함없이 적용된다.
           "unchanged", "reiterates", "reiterated", "reiterating", "reaffirming", "affirms",
           "affirming", "affirmed", "original", "prior", "previous", "narrowed", "narrows",
           "narrowing", "actual", "actuals", "anticipate", "anticipated", "forecasting",
           "forecast", "forecasts", "announced", "announces", "quarter", "adjusted",
           "currency-neutral", "currencyneutral", "fx-neutral", "constant", "core", "m", "b",
           "midpoint", "including", "sees", "see", "believes", "targets", "target", "implies",
           # (2026-08-16 2차) 미확보 재감사 —
           #   "or": "growth … 0% to 4%, **or** revenue of $367 million to $382 million"
           #         (실측 CERT: 성장률 뒤 병기된 절대금액이 접속사 때문에 기각, BZ 367~382 일치)
           #   "tour": Lindblad 류 여행사는 'Tour revenues' 가 곧 전사 매출이다
           #         (실측 LIND "● Tour revenues of $830 - $860 million" = BZ 830~860).
           # 세그먼트명(shipbuilding·subsea 등)은 **넣지 않는다** — 그건 진짜 부분 매출이라
           # 전사 합계로 쓰면 과소 계상된다(실측 HII·FTI 는 기각이 정답).
           "or", "tour", "tours"}
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
# (2026-08-15 5차) 분기 어구 **바로 뒤에 results/earnings** 가 붙으면 지난 실적 제목이다
# ("Second Quarter 2026 Financial Results" · "Second quarter results"). 기간 근거로도,
# 전망 판정(_fwd_q)의 씨앗으로도 쓰지 않는다. 실측 ILMN: 연간 가이던스 불릿 뒤에 이어지는
# 섹션 제목 "Second quarter results" 가 기간 근거로 채택돼 연간 EPS 5.35 가 0q 로 태그
# (분기 컨센 대비 +294%). CXW 도 표 앞 "Second Quarter 2026 Financial Results" 가 같은 역할.
_QRES = r"\s*(?:of\s+)?(?:fiscal\s+)?(?:20\d\d\s+)?(?:financial\s+|fiscal\s+)?(?:results|earnings|highlights)\b"
# (2026-08-21) 값 뒤 **설명 종속절** — 이 뒤의 분기 표현은 값의 구성·사유를 설명할 뿐
# 가이던스 기간이 아니다(실측 TGT "…$9.90 to $10.90, which includes second quarter
# tariff refund benefits…"). 값보다 뒤에 있는 분기 토큰에만 적용한다.
_QEXPL = (r"\b(?:which\s+(?:includes?|reflects?|assumes?)|including|reflecting|assuming|"
          r"driven\s+by|due\s+to|benefits?\s+(?:of|from)|related\s+to|attributable\s+to|"
          r"partially\s+offset\s+by|net\s+of)\b[^.•●]{0,25}$")
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
    # (2026-08-16) 라벨~숫자 사이에 **같은 라벨이 다시 나오면 매칭하지 않는다**(negative
    # lookahead). 정규식은 겹치지 않으므로, 앞쪽에 스쳐 지나간 라벨이 먼저 소비되면 뒤에
    # 있는 진짜 라벨은 영영 후보가 되지 못한다. 실측 NE: "Backlog excludes mobilization and
    # **demobilization revenue**. Outlook For the full year 2026, **Revenue guidance is
    # reduced to $2,800-$2,900 million**" 에서 앞 'revenue' 가 라벨로 잡혀 '수식어
    # demobilization → 전사 아님'으로 기각됐고, 명시된 전사 매출 2.8~2.9B(BZ 동일)은
    # 후보 목록에조차 오르지 못했다. 사이에 라벨 재등장을 막으면 엔진이 뒤쪽 라벨에서
    # 다시 시도해 올바른 매칭을 만든다.
    gap = r"(?:(?!" + label + r")[^$%]){0,60}?"
    gap25 = r"(?:(?!" + label + r")[^$%]){0,25}?"
    gap70 = r"(?:(?!" + label + r")[^$]){0,70}?"
    gap60d = r"(?:(?!" + label + r")[^$]){0,60}?"
    # (2026-08-21) FFO 는 리츠의 주당 이익 지표다 — EPS 와 같은 형식(달러 소수, 단위 접미사
    # 없음)이므로 같은 후보 형식을 쓴다.
    if metric in ("eps", "ffo"):
        return [
            ("range", label + gap + _NUM_D + r"\s*(?:to|through|-|and)\s*" + _NUM_D),
            ("rangec", label + gap + _NUM_C + r"\s*(?:to|through|-|and)\s*" + _NUM_C),
            # (2026-08-15) 괄호 병기 — "EPS guidance of 13% to 15% growth ($12.40 to $12.60)"
            # (실측 CAH). 성장률(%) 뒤 괄호 안에 금액 범위가 온다 — $ 필수라 성장률 오인 없음.
            ("prange", label + gap70 + r"\(\s*" + _NUM_D + r"\s*(?:to|through|-|and)\s*" + _NUM_D + r"\s*\)"),
            # (2026-08-15) Low/High 두 열 표 — "Net income per share $ 0.67 $ 0.75"(실측 LFTO).
            # 구분자 없이 $ 금액 두 개가 나란히. 오탐 방지: 루프에서 back 에 'Low … High'
            # 열 머리글이 있을 때만 채택한다.
            ("lowhigh", label + gap25 + _NUM_D + r"\s+" + _NUM_D),
            ("approx", label + gap + r"(?:approximately|about|around)\s*" + _NUM_D),
            ("approxc", label + gap + r"(?:approximately|about|around)\s*" + _NUM_C),
            # (2026-08-21) **± 표기** — 매출·CapEx 에만 있고 EPS 에는 없어서, ± 로만 제시하는
            # 회사의 EPS 가이던스가 통째로 누락됐다. 실측 PENG(Penguin Solutions):
            #   "full-year non-GAAP EPS of $2.60 plus or minus 5 cents"(BZ 2.60) ·
            #   표에도 "Diluted earnings per share $1.97 +/- $0.05 … $2.60 +/- $0.05"
            ("pm", label + gap + _NUM_D + r"\s*(?:±|\+/-|plus or minus)\s*" + _NUM_D),
            # 오차를 센트로 쓰는 형태("$2.60 plus or minus 5 cents")
            ("pmc", label + gap + _NUM_D + r"\s*(?:±|\+/-|plus or minus)\s*" + _NUM_C),
        ]
    return [
        ("range", label + gap + _NUM + r"\s*(?:to|through|-|and)\s*" + _NUM),
        ("pm", label + gap + _NUM + r"\s*(?:±|\+/-|plus or minus)\s*" + _NUM),
        # (2026-08-21) **단일값 가이던스** — 범위 없이 한 숫자만 제시하는 회사가 있는데
        # approximately/about 이 붙지 않으면 잡을 형식이 없었다. 실측 KMTS(Kestra):
        #   "FY27 revenue guidance of $137 million" · "Kestra expects revenue of $137
        #    million in FY27"(BZ 137.0) — 둘 다 후보조차 만들어지지 않았다.
        # 실적 서술("revenue of $X million in the quarter")과 섞이지 않도록,
        # 라벨 인접에 guidance/outlook/target 이 붙었거나 expect 동사가 라벨을 이끄는
        # 형태만 받는다(전망 문맥 검사 _FORE 는 루프에서 별도로 또 걸린다).
        ("single", label + gap25 + r"(?:guidance|outlook|targets?)\s+(?:of|at)\s*" + _NUM),
        ("single2", r"expects?\s+(?:its\s+|full[\s-]?year\s+|annual\s+)?" + label +
                    gap25 + r"(?:of|to be)\s*" + _NUM),
        ("pmpct", label + gap60d + _NUM + r"[^$]{0,20}?(?:±|\+/-|plus or minus)\s*([\d.]+)\s*%"),
        # (2026-08-15) Low/High 두 열 표 — "Revenue $ 2,115 $ 2,175"(실측 MH·GMRS·EQPT).
        # 단위는 표 머리의 '($ in millions)' 선언에서 가져온다(루프에서 처리).
        # (2차) 숫자별 단위 병기형 "$925 million $945 million"(실측 JBI — Range 헤더 표)도 커버.
        ("lowhigh", label + gap25 + r"\$\s?([\d,]+(?:\.\d+)?)(?!\d)\s*(billion|million|bn|mm)?\s+"
                            r"\$\s?([\d,]+(?:\.\d+)?)(?!\d)\s*(billion|million|bn|mm)?(?![\w%])"),
        ("approx", label + gap + r"(?:approximately|about|around)\s*" + _NUM),
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
    if kind == "pmc":                          # "$2.60 plus or minus 5 cents"(실측 PENG)
        c, d = _num(m.group(1), m.group(2)), _num(m.group(3), None)
        d = d / 100 if d is not None else None
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
# (2026-08-21) 표 머리글은 분기와 연도를 **하이픈·슬래시**로 잇는다 — "Q4 - 2026" ·
# "Q4/2026". 종전 패턴은 공백 구분만 허용해 이 연도가 연간 표지로 살아남았다.
# 실측 DOX: "Q4 - 2026 Revenue $1,175 - $1,215 … Non-GAAP Diluted EPS $1.94 - $2.00"
# 에서 Q4(거리 80) 보다 2026(거리 75)이 값에 가까워 분기 EPS 가 연간으로 태그됐다
# (BZ 연간 7.41 대비 −73%).
_YEXCL = (r"(?:\bquarter\b|\bQ[1-4]\b|\b[1-4]Q\b)"
          r"(?:(?:\s*[-–—/]\s*|\s+)(?:of|the|ended|ending|for|fiscal|calendar|year)?)*"
          r"\s*(?:(?:january|february|march|april|may|june|july|august|"
          r"september|october|november|december)\s+\d{1,2}\s*,?\s*)?"
          r"(?:fiscal\s+|calendar\s+)?(?:year\s+)?$")
# (2026-08-21) **연도 뒤에 분기가 붙는 블록 제목** — "2026 Business Outlook Third Quarter •"
# 처럼 회계연도를 앞세우고 분기를 뒤에 쓰는 형식이 흔하다. 이때 연도는 그 분기의 소속
# 연도일 뿐 연간 표지가 아닌데, 값에서 보면 연도·분기가 나란히 있어 '어느 쪽인지 모름'
# 으로 기각되고(둘 다 60자 이내) 회사 프로필 교정으로 연간이 됐다.
#   실측 ALIT: 분기 매출 469~479M 이 fy_rev 로 저장 → BZ 연간 2,088M 대비 −77%.
# 사이에 값·불릿·마침표가 끼지 않을 때만(=같은 제목 줄일 때만) 적용하고,
# "…2026 … Second Quarter Results" 같은 지난 실적 제목은 제외한다.
_YQAFT = (r"[^.•●▪$%\d]{0,30}?\b(?:(?:first|second|third|fourth)\s+quarter|Q[1-4])\b"
          r"(?!\s*(?:results|earnings|highlights))")
# (2026-08-21) **과거 사건을 가리키는 연도**는 기간 근거가 아니다. 실측 CHD:
# "For the third quarter, we expect … driven entirely by the strategic portfolio actions
#  **taken in 2025**. … Overall, adjusted EPS is expected to be approximately $0.89"
# — 문단 머리의 'For the third quarter'(396자 거리)보다 이 '2025'(215자)가 값에 가까워
# 분기 가이던스 0.89 가 연간으로 태그됐다(BZ 연간 3.78 대비 −77%). 완료된 행위를
# 서술하는 동사 뒤의 연도는 후보에서 뺀다.
#   in/during 은 _YRE 매칭 안에 포함될 수 있으므로(실측 CHD 는 'in 2025' 통째로 매칭)
#   앞 문맥에 없을 수도 있다 → 선택으로 둔다.
_YPAST = (r"\b(?:taken|made|completed|announced|incurred|recorded|occurred|closed|"
          r"acquired|divested|launched|implemented|reported)\s+(?:(?:in|during)\s+)?$")
# 값 **뒤**에 오는 '«연도» … Guidance/Outlook' 은 **다음 블록의 캡션**이지 이 값의 기간이
# 아니다. 실측 HLIT: "Q3 2026 GAAP Financial Guidance … Net income per share $0.10 $0.14
#  … **2026 GAAP Financial Guidance**" — 뒤따르는 연간 표 제목이 근거로 채택돼 분기 EPS
# 0.12 가 연간으로 태그(BZ 0.71 대비 −83%).
_YCAP = r"\s*(?:GAAP\s+|Non-GAAP\s+|Adjusted\s+)?(?:Financial\s+)?(?:Guidance|Outlook)\b"


def _fwd_q(seg):
    """이 구간의 분기 표현이 **전망**을 가리키는가.

    (2026-08-10) 헤드라인이 마침표 없이 이어지는 보도자료에서는 한 '문장'에 지난 분기
    실적과 연간 가이던스가 함께 들어온다. 그때 "Third Quarter … EPS of \\$4.48"(실적) 이
    기간 근거로 채택돼 연간 가이던스가 분기로 분류됐다(실측 COR 17.75 → +289%,
    EW 2.95 → +307%, ILMN·AVY·FLS 등 |갭|>300% 26건). 분기 표현 근처(±60자)에
    전망을 뜻하는 말이 없으면 그 분기 표현은 근거로 쓰지 않는다.
    """
    return any(re.search(_FWD, seg[max(0, m.start() - 60):m.start() + 60], re.I)
               for m in re.finditer(_QRE, seg, re.I)
               if not re.match(_QRES, seg[m.end():], re.I))   # '«분기» results' 제목은 제외


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
             if not re.search(_QPAST, seg[:m.start()][-30:], re.I)
             and not re.match(_QRES, seg[m.end():], re.I)      # '«분기» results' 제목 제외
             # (2026-08-21) 값 **뒤**에 오는 **설명 종속절**의 분기는 기간 근거가 아니다.
             # 실측 TGT: "An updated GAAP and Adjusted EPS guidance range of $9.90 to $10.90,
             # **which includes second quarter tariff refund benefits** of ~$1..." — 연간
             # 가이던스인데 뒤따르는 관세 환급 설명의 '2분기'가 근거로 채택돼 분기 컨센
             # 2.04 대비 +410%(연간 컨센 9.91 대비로는 +4.9%로 정상). 이 불릿 안에는 연간
             # 토큰이 없어 Q 가 무투표 당선됐다. 종속절이 수식하는 것은 값의 '구성'이지
             # '기간'이 아니므로 후보에서 뺀다.
             and not (anchor is not None and m.start() > anchor
                      and re.search(_QEXPL, seg[:m.start()][-45:], re.I))]
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
             if not re.search(_YEXCL, seg[:m.start()][-60:], re.I)
             and not re.search(_YPAST, seg[:m.start()][-40:], re.I)   # 과거 사건 연도 제외
             and not re.match(_YQAFT, seg[m.end():], re.I)            # '«연도» … 3분기' 제목
             # 값 뒤의 '«연도» Guidance' 는 다음 블록 캡션이지 이 값의 기간이 아니다
             and not (anchor is not None and m.start() > anchor
                      and re.match(_YCAP, seg[m.end():], re.I))]
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
    # (2026-08-16) 반환값에 **근거 강도**를 함께 싣는다 — (기간, 강함 여부).
    # ①구절 안·②같은 문장은 회사가 그 값 옆에 직접 쓴 기간이므로 '강함'(회사 프로필로도
    # 교정하지 않는다 — 실측 SILC: "raising our full-year revenue guidance to $93 to $95
    # million" 명시를 이력상 분기만 제시한다는 프로필이 뒤집어 +263% 갭).
    # ②-b/②-c 머리글·③앞 400자·④뒤 90자는 떨어진 문맥에서의 추정이므로 '약함'.
    # 단, **반기 토큰만으로 나온 Q 는 강하지 않다** — 반기는 분기를 지목하는 명시가
    # 아니다(실측 IR "1H 46% | 2H 54%" 페이징 주석 · XOS "for the second half of the
    # year" 사유 구절 — 둘 다 FY 100% 회사의 연간 값이라 프로필 교정이 맞다).
    def _nonhalf_q(seg):
        return any(not re.match(r"[12]H\b|(?:first|second)[-\s]half", m_.group(0), re.I)
                   for m_ in re.finditer(_QRE, seg, re.I)
                   if not re.match(_QRES, seg[m_.end():], re.I))
    if r0:
        return r0, (r0 != "Q" or _nonhalf_q(txt[start:end]))
    # ② 같은 문장 안 (마침표·불릿 경계)
    # (2026-08-10) 세미콜론은 경계에서 뺀다 — 세미콜론은 한 문장 안의 나열이라
    # 앞부분의 기간 표시가 뒤 항목에도 그대로 걸린다. 실측 DGX:
    # "Full year 2026 reported diluted EPS … $9.97 and $10.17; and adjusted diluted EPS
    #  expected to be between $11.05 and $11.25" — 세미콜론에서 자르면 뒤 항목이
    # 'Full year 2026' 을 못 봐 연간 11.05 가 분기로 분류된다(+300%대).
    # (2026-08-15) " - - " 도 문장 경계다 — 대시 불릿 보도자료를 _strip 하면 불릿 끝과
    # 다음 불릿 시작이 "…$310 million - - Q2 2026 LINZESS…" 처럼 이어붙는다. 이걸 안 자르면
    # 다음 불릿의 지난 분기 실적("Q2 2026 … net sales were")이 기간 근거로 새어 들어오고,
    # 직전 절의 'guidance' 가 ±60자 창에 걸려 _fwd_q 까지 통과한다(실측 IRWD: 연간
    # 총매출 460~485M 이 0q 로 태그돼 분기 컨센 대비 +289%). 값 범위의 단일 대시
    # ("$460 - $485")와 달리 이중 대시는 불릿 이음에서만 나온다.
    # (2026-08-16) 여는 인용부호(“)도 문장 경계다 — 표·불릿 뒤에 마침표 없이 경영진
    # 인용문이 이어지면("…$350 - $400 “Second quarter benefitted from…", 실측 SNDR)
    # 인용문 속 지난 분기 언급이 값의 기간 근거로 새어 들어온다. 인용문은 항상 새 발화다.
    ls = max(txt.rfind(". ", 0, start), txt.rfind(" - - ", 0, start), txt.rfind(" “", 0, start),
             *(txt.rfind(b, 0, start) for b in ("• ", "● ", "▪ ", "· ")))
    # (2026-08-10) 오른쪽 경계도 **다음 불릿**에서 끊는다. 예전엔 다음 마침표까지만 봐서
    # 불릿 목록이 통째로 한 문장이 됐고, 값 뒤 항목의 분기 표현이 근거로 채택돼
    # 연간 가이던스가 분기로 분류됐다(실측 ILMN·LIFE·BFLY·EW·HLT).
    # (2026-08-15) " The following " 도 오른쪽 경계로 자른다 — 보도자료가 마침표 없이
    # "…range of $0.35 to $0.49 The following revised guidance is provided for … fiscal year 2026:"
    # 처럼 다음 블록 머리글을 이어붙이면, 그 머리글의 연간 표지가 현재 행의 근거로 오인돼
    # 분기 가이던스가 연간으로 분류된다(실측 VECO Q3 Non-GAAP 0.35~0.49 가 fy_ 로 태그).
    # (2026-08-15 5차) "For the full year 2026, …" · "For the third quarter of 2026:" 같은
    # **다음 블록 머리글**도 오른쪽 경계다 — 실측 TDC: 분기 블록 마지막 불릿(Non-GAAP EPS
    # $0.55~0.59) 뒤에 마침표 없이 연간 블록 머리글이 이어져, 그 머리글의 'full year 2026'
    # 이 분기 값의 근거로 잡혀 Q3 값이 연간으로(그리고 연간 값이 분기로) 서로 뒤바뀌었다.
    rs = min([p for p in ([txt.find(". ", end), txt.find(" - - ", end), txt.find(" “", end)] +
                          [txt.find(ph, end) for ph in (" The following ", " The Company ",
                                                        " In addition", " Additionally,", " Separately,",
                                                        " For the full year", " For the fiscal year",
                                                        " For fiscal", " For the first quarter",
                                                        " For the second quarter", " For the third quarter",
                                                        " For the fourth quarter", " For full-year",
                                                        " For full year",
                                                        # (2026-08-16) 표 캡션은 항상 새 블록이다 —
                                                        # 실측 CGNX: Q3 표 마지막 행(Adj. EPS $0.50-$0.54)
                                                        # 뒤에 "Table 2: Full-Year 2026 Guidance" 캡션이
                                                        # 이어져 Y 가 근거로 채택(3배 페널티로도 역전),
                                                        # 분기 값이 연간으로·연간 값이 분기로 뒤바뀜(+221%).
                                                        " Table ")] +
                          [txt.find(b, end) for b in ("• ", "● ", "▪ ", "· ")]) if p > 0] or [-1])
    s0 = (ls + 2 if ls > 0 else max(0, start - 400))
    sent = txt[s0:(rs if rs > 0 else min(len(txt), end + 200))]
    r1 = pick(sent, start - s0)
    # (2026-08-16) ②는 이미 한 문장으로 경계 지어져 있으므로, 문장 앞머리에 전망 동사가
    # 있으면 그 문장의 분기 표현은 전망 기간이다 — 토큰 ±60자 창만 보면 "expects net sales
    # in the range of $14.5 billion and $15.5 billion for the first quarter …"(실측 SMCI)
    # 처럼 값 범위가 길 때 동사가 창 밖으로 2자 벗어나 정당한 Q 가 버려지고, ③에서
    # 대차대조표 날짜("As of June 30, 2026")가 연간 표지로 오채택됐다(Q1 15B 가 0y →
    # FY 컨센 68.5B 대비 −78%).
    if r1 == "Q" and not (_fwd_q(sent) or re.search(_FORE, sent[:max(0, start - s0)], re.I)):
        r1 = None                       # 지난 실적을 말하는 분기 표현이면 근거로 쓰지 않는다
    if r1:
        return r1, (r1 != "Q" or _nonhalf_q(sent))
    # ②-b **블록 머리글** — 보도자료는 "Fiscal year 2026 guidance … we now expect:" ·
    #    "Second Quarter Fiscal Year 2027 Guidance:" 처럼 머리글을 두고 그 아래에 불릿으로
    #    항목을 나열한다. 값이 속한 블록의 머리글이 곧 그 값의 기간이다.
    #    앞 400자를 무작정 훑으면 문서 여기저기의 "Second quarter 2026 results" 같은
    #    **다른 블록 머리글**을 집어 연간 가이던스가 분기로 떨어진다(실측 ILMN·LIFE·BFLY·EW).
    #    → 값 바로 위의 머리글(콜론으로 끝나는 전망 문구)을 먼저 본다.
    #    (2026-08-15) 머리글 허용 길이 40→60자 — "guidance is provided for Veeco's third
    #    quarter 2026:"(43자) 같은 실제 머리글이 40자에 걸려 인식되지 않았다(실측 VECO).
    # (2026-08-15 5차) 머리글 낱말 확장 — "For the full year 2026, Teradata increases the
    # following ranges:"(실측 TDC)처럼 guidance/outlook 낱말 없이 여는 머리글이 있다.
    # 종전엔 이 머리글을 지나쳐 **더 먼** "Outlook For the third quarter of 2026:" 을 집어
    # 연간 EPS 2.65~2.73 이 0q 로 태그됐다(분기 컨센 대비 +365%).
    hs, h0 = None, max(0, start - 800)
    # (2026-08-21) 머리글 허용 길이 60→150 — 지표를 나열하고 기간을 맨 끝에 붙이는
    # 긴 머리글이 흔한데 60자에서 잘려 인식되지 않았다. 실측 UPWK:
    #   "Upwork's guidance for revenue, adjusted EBITDA, diluted weighted-average shares
    #    outstanding, and non-GAAP diluted EPS **for the third quarter of 2026** is:"(133자)
    # 이 안 잡혀 그 아래 분기 EPS 0.31~0.33 이 fy_eps 로 실렸고, 뒤에 오는 진짜 연간
    # 가이던스가 중복 차단에 걸려 버려졌다(BZ 연간 1.40 대비 -77%).
    # 사이에 마침표·불릿·콜론이 못 오므로 한 구절을 벗어나지 않는다.
    for hm in re.finditer(r"(?:guidance|outlook|expects?|expectations|anticipates?|"
                          r"following\s+(?:ranges|updates)|as\s+follows)"
                          r"[^.•●▪:]{0,150}:", txt[h0:start], re.I):
        hs = hm                                   # 가장 가까운(=마지막) 머리글
    # (2026-08-15 5차) ②-c **맨몸 기간 머리글** — 실측 HLT: "Full Year 2026 • System-wide …"
    # 처럼 콜론도 키워드도 없이 기간 어구만으로 불릿 목록을 여는 형식. 기간 어구가 불릿
    # 기호 바로 앞에 오면 그 목록의 기간이다. "Second Quarter 2026 Results • …" 같은 실적
    # 헤드라인은 Results 가 사이에 끼므로 매치되지 않는다.
    # (2026-08-21) ②-d **표 평문 머리글** — 표를 평문화하면 불릿도 콜론도 남지 않고
    # "Q3 2026 Outlook Net Sales 2% to 3% … Normalized EPS $0.18 to $0.20" 처럼 머리글과
    # 항목이 통째로 이어붙는다. 기간 어구 바로 뒤에 Outlook/Guidance/Targets 가 오면
    # 그 자체가 블록 머리글이므로 불릿을 요구하지 않는다.
    #   실측 NWL(Newell) — 'Q3 2026 Outlook' 을 못 읽어 분기 Normalized EPS 0.18~0.20 이
    #   fy_eps 로 실렸다(BZ 연간 0.75 대비 -75%). 바로 뒤에 'Updated Full Year 2026
    #   Outlook' 이 이어져 그쪽이 근거로 새어 들어간 형태.
    # "Full Year **Fiscal** 2027"(실측 DXC)처럼 연간 어구와 연도 사이에 fiscal 이 끼는
    # 표기를 받아야 한다 — 안 받으면 이 머리글이 통째로 밀려 앞의 "Second Quarter …
    # Guidance" 가 대신 잡히고 연간 매출이 분기로 뒤집힌다(gp_cases DXC 회귀로 확인).
    _PHD = (r"(?:(?:full[\s-]?year|fiscal\s+year|FY)\s*(?:of\s+)?(?:fiscal\s+)?20\d\d|"
            r"(?:first|second|third|fourth)\s+quarter\s+(?:of\s+)?"
            r"(?:fiscal\s+(?:year\s+)?)?20\d\d|\bQ[1-4]\s*(?:FY\s*)?20\d\d)")
    hc = None
    for hm in re.finditer(_PHD + r"\s*[::]?\s*(?=[•●▪◦])", txt[h0:start], re.I):
        hc = hm
    for hm in re.finditer(_PHD + r"\s+(?:GAAP\s+|Non-GAAP\s+|Adjusted\s+)?"
                          r"(?:Financial\s+|Business\s+)?(?:Outlook|Guidance|Targets?)\b",
                          txt[h0:start], re.I):
        if hc is None or hm.start() > hc.start():
            hc = hm
    # 값에 더 가까운 머리글이 그 값을 지배한다
    for knd, hm in sorted([("kw", hs), ("bare", hc)],
                          key=lambda x: -(x[1].start() if x[1] else -1)):
        if not hm:
            continue
        if knd == "kw":
            seg = txt[max(0, h0 + hm.start() - 130):h0 + hm.end()]
            r15 = pick(seg, len(seg))             # 머리글 끝(콜론)에 가장 가까운 표현
            if r15 == "Q" and not _fwd_q(seg):
                r15 = None
        else:
            # (2026-08-21) 분기 낱말이 있으면 분기다 — "Q3 FY2026 Outlook" 처럼 분기 머리글에
            # 회계연도가 붙는 표기가 흔한데, FY 만 보고 연간으로 판정하면 정반대가 된다.
            if re.search(r"\bquarter\b|\bQ[1-4]\b", hm.group(0), re.I):
                r15 = "Q" if _fwd_q(txt[h0 + hm.start():h0 + hm.end() + 120]) else None
            elif re.search(r"full[\s-]?year|fiscal\s+year|\bFY\b", hm.group(0), re.I):
                r15 = "Y"
            else:                                  # 분기 머리글 — 뒤 불릿이 전망 문맥일 때만
                r15 = "Q" if _fwd_q(txt[h0 + hm.start():h0 + hm.end() + 120]) else None
        if r15:
            return r15, False
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
        return r2, False
    # ④ 뒤 90자
    return pick(txt[end:end + 90]), False


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
            # (2026-08-21) FFO 도 같은 이유로 교체한다 — 리츠는 Nareit FFO(기본)와
            # Core/Normalized/Adjusted FFO 를 **한 표에 나란히** 싣고, 컨센서스(BZ 포함)는
            # 회사가 주력으로 제시하는 조정 쪽을 쓴다. 먼저 나오는 기본 FFO 가 선점하면
            # 조정 컨센과 어긋난다(실측 VTR: Nareit FFO 3.69~3.76 채택 → BZ Normalized
            # 3.88 대비 −4.1% · CPT: FFO 6.05~6.19 채택 → BZ Core FFO 6.75 대비 −8.9%).
            if not ((metric == "eps" and basis == "adj"
                     and out.get(pre + "eps_basis") != "adj")
                    or (metric == "ffo" and basis == "core"
                        and out.get(pre + "ffo_basis") != "core")):
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
                # (2026-08-21) 단, 리츠는 Nareit FFO 와 Normalized/Core FFO 를 **한 표에 나란히**
                # 싣고 두 값이 3~5% 밖에 안 벌어진다(실측 VTR: Nareit 3.69~3.76 · Normalized
                # 3.82~3.89). 기준이 다르면 다른 항목이므로 중복으로 지우지 않는다.
                if not (metric == "ffo" and basis and out.get(other + "_basis")
                        and basis != out.get(other + "_basis")):
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
    # (2026-08-21) 매출 라벨에 'total sales' 추가 — 종전엔 'net sales' 만 받아 'Total sales'
    # 표기가 통째로 누락됐다(실측 KRUS: "Total sales between $330.5 million and $331.5
    # million" = BZ 331.0). 'sales' 단독은 부분 매출(같은 문서의 'comparable restaurant
    # sales' 등)과 구별이 안 되므로 total/net 수식이 붙은 것만 받는다.
    for metric, label in (("rev", r"(?:revenues?|(?:net|total)\s+sales)"),
                          ("eps", r"(?:diluted\s+)?earnings per (?:diluted\s+|common\s+)?share|\beps\b|"
                                  r"net income per (?:diluted\s+|common\s+)?share(?:s)?(?:\s*,\s*diluted)?"),
                          # (2026-08-21) **리츠 FFO** — 리츠의 컨센서스는 순이익이 아니라
                          # FFO 기준이라, 회사의 EPS 가이던스로는 비교가 성립하지 않아
                          # guidance_gap 이 섹터 판정으로 EPS 를 통째로 버려 왔다(실측:
                          # 부동산 섹터 8-K 192건 중 BZ 가 주당값을 주는 것 96건이 전부 공백).
                          # FFO 자체를 뽑아 별도 필드로 실으면 그 96건이 화면에 살아난다.
                          # 표기가 회사마다 다르다 — 실측 WELL 'normalized FFO' · PLD 'Core FFO' ·
                          # VTR 'Normalized Funds From Operations … per share' · IRM/CCI 'AFFO
                          # per share' · DLR 'FFO / diluted share and unit'.
                          ("ffo", r"(?:core\s+|adjusted\s+|normalized\s+|nareit\s+|real\s+estate\s+)?"
                                  r"(?:\bA?FFO\b|funds\s+from\s+operations)"
                                  r"(?:\s*\([^)]{0,40}\))?"
                                  r"(?:\s*(?:per|/)\s*(?:diluted\s+|common\s+)*"
                                  r"share(?:\s+and\s+unit)?)?"),
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
                   re.search(r"estimated impact|impact on", ctx, re.I) or \
                   re.search(r"\bcontribut\w+\s*:", back, re.I):
                    # (2026-08-16) "…is expected to contribute: • Revenue: $24-26M"(실측 GLBE:
                    # 인수한 Passport 사업부의 **기여분** 블록 — 콜론 뒤 불릿 나열이라 lead 창을
                    # 벗어남) — back 에 'contribute:' 머리글이 있으면 그 아래 값은 기여분이다.
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
                # (2026-08-15 5차) 다중 열 판정의 분기 마커에서도 '«분기» results' 실적 제목은
                # 뺀다 — 실측 CXW: Updated|Prior 두 열(같은 연간 기간) 표인데 표 앞의
                # "Second Quarter 2026 Financial Results" 가 분기 마커로 집계돼 다중 열로
                # 오인, Adjusted Diluted EPS 1.62~1.70 이 기각되고 본문 오기(15.00~15.20)가
                # 살아남았다(+793%).
                # (2026-08-16) 뒤따르는 금액 검사에서 % 배제를 푼다 — "Total Revenue
                # $7,940-$8,010 **~16%** $7,825-$7,925 ~$1,980"(실측 IRM: FY|Y/Y%|Prior|Q3
                # 5열 표)처럼 값 열 사이에 증감률(%) 열이 끼면 % 문자가 검사를 끊어
                # 다중 열 가드가 통과됐고, FY 값 7,975 가 0q 로 태그돼 Q3 컨센 1,980
                # 대비 +300%. %를 건너뛰고도 금액이 이어지면 다중 열이다.
                # (2026-08-16) 뒤 금액이 **비교 연결어** 뒤에 오면 다중 열 표가 아니라
                # 한 문장 안의 신·구 가이던스 대조다 — "revenue to be in the range of
                # $490 million to $500 million, **compared to** the $447 million to $465
                # million range that was previously disclosed"(실측 CDNA: 명시된 신 가이던스
                # 490~500M 이 통째로 기각됐다). 이 경우 앞 범위가 신 값이므로 그대로 쓴다.
                _nx = txt[m.end():m.end() + 65]
                _cmp = re.match(r"[^.•●]{0,28}?\b(?:compared\s+to|versus|vs\.?|up\s+from|"
                                r"down\s+from|previously|prior\s+(?:guidance|range|outlook))\b",
                                _nx, re.I)
                if kind in ("range", "lowhigh") and _ys and not _cmp and \
                   any(not re.match(_QRES, back300[mm.end():], re.I)
                       for mm in re.finditer(_QRE, back300, re.I)) and \
                   re.search(r"^[^.•●]{0,55}?(?:\$\s?[\d,]+|[\d,]+(?:\.\d+)?\s*(?:billion|million|bn|mm)\b)",
                             _nx, re.I):
                    skip.append(f"{metric}: 분기|연간 다중 열 표(열 확정 불가) · {ctx[:110]}")
                    continue
                # (2026-08-14) 장기 목표(long-term outlook/target)는 올해·다음 분기 가이던스가
                # 아니다 — 컨센과 비교하면 반드시 어긋난다(실측 EOLS "Reaffirms 2028 Long-Term
                # Financial Outlook … $450-500M" 을 올해 매출로 채택 → +42%).
                if re.search(r"long[-\s]term\s+(?:financial\s+)?(?:outlook|guidance|target|model|goal)",
                             ctx, re.I) or \
                   re.search(r"run[-\s]rate", back + lead, re.I):
                    # (2026-08-16) run-rate 도 장기 목표다 — "by year-end 2028 … total annual
                    # revenues … run rate is expected to reach $2.2 to $2.3 billion"(실측 ENLT:
                    # 2028년 도달 목표 런레이트 2.25B 가 올해 매출로 채택돼 컨센 805M 대비 +180%).
                    skip.append(f"{metric}: 장기 목표(당기 가이던스 아님) · {ctx[:110]}")
                    continue
                # (2026-08-14) 라벨과 숫자 사이에 **반대편 지표**가 끼면 그 숫자는 그쪽 것이다.
                # 실측 LINC: "(… except … diluted EPS) Low High Revenue $590.0 - $600.0" 에서
                # 괄호 속 'EPS' 라벨이 매출 590~600 을 EPS 로 채택(595.00 — 자릿수부터 불가능).
                if metric in ("eps", "ffo") and re.search(r"\brevenues?\b|\bnet sales\b|\bexcept\b", lead, re.I):
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
                    # (2026-08-16) 신(新) 열에 한정어가 아예 없는 표기도 있다 — 실측 HIPO:
                    # "Prior 2026 FY Guidance | 2026 FY Guidance" 처럼 앞 열만 Prior 로 표시하고
                    # 뒤 열은 맨몸 'Guidance'. updated/revised/current 낱말만 찾으면 규칙이
                    # 통째로 불발돼 구 가이던스(560~570)가 채택된다(BZ 신 580~585 대비 −3%).
                    # prior 마커 뒤에 guidance/outlook 어구가 다시 나오면 그쪽이 신 열이다.
                    _tail = hdr[pm_.end():] if pm_ else ""
                    um_ = pm_ and (re.search(r"\b(?:updated?|revised?|current|new)\b", _tail, re.I)
                                   or re.search(r"\b(?:guidance|outlook)\b", _tail, re.I))
                    if pm_ and um_:
                        n2 = _NUM_D if metric in ("eps", "ffo") else _NUM
                        m2 = re.match(r"[^$\d%]{0,30}?" + n2 + r"\s*(?:to|through|-|and)\s*" + n2,
                                      txt[m.end():m.end() + 90], re.I)
                        if m2:
                            h2 = (m2.group(4) or m2.group(2) or "").lower() if metric not in ("eps", "ffo") else None
                            lo2 = _num(m2.group(1), None if metric in ("eps", "ffo") else m2.group(2), h2)
                            hi2 = _num(m2.group(3), None if metric in ("eps", "ffo") else m2.group(4), h2)
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
                    n2 = _NUM_D if metric in ("eps", "ffo") else _NUM
                    # (2026-08-15) "from a range of A to B **to a range of** C to D"(실측 ICUI)
                    m2 = re.match(r"\s*to\s*(?:a\s+range\s+of\s+)?" + n2 +
                                  r"(?:\s*(?:to|through|-|and)\s*" + n2 + r")?",
                                  txt[m.end():m.end() + 90], re.I)
                    if m2:                                   # from [구범위] to [신범위/값]
                        if metric in ("eps", "ffo"):
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
                per, per_strong = _period(txt, m.start(), m.end())
                if not per and per_hint:
                    # (2026-08-15) 회사 프로필 구제 — 이 회사는 이력상 한 종류 기간만 제시
                    # (2026-08-21) 단, **전망 문맥이 있는 값에만** 적용한다. 프로필은 '이 회사가
                    # 어느 기간을 제시하는가'를 알려줄 뿐 '이 값이 가이던스인가'를 말해주지 않는데,
                    # 종전엔 기간을 못 정한 값이면 무엇이든 구제해 실적 서술까지 가이던스로 실렸다.
                    #   실측 GRMN — 실적 하이라이트 불릿 "Record consolidated revenue of
                    #   approximately $2.02 billion, an 11% increase compared to the prior year
                    #   quarter"(과거 실적)가 fy_rev 로 구제돼 먼저 선점하는 바람에, 같은 문서
                    #   뒤쪽의 진짜 가이던스 "we are raising our full year 2026 guidance. We now
                    #   anticipate revenue of approximately $8.05 billion" 이 무시됐다
                    #   (BZ 연간 8,050M 대비 -75%). 전망 낱말 조건을 걸면 8,050M 이 채택된다.
                    if (re.search(_FWD, lead, re.I) or re.search(_FWD, back[-120:], re.I)
                            or re.search(_FWD, txt[m.end():m.end() + 80], re.I)):
                        per = per_hint
                        ctx += (" [기간: 회사 프로필(이력상 %s만 제시)]"
                                % ("연간" if per_hint == "Y" else "분기"))
                    else:
                        skip.append(f"{metric}: 프로필 구제 보류 — 전망 문맥 없음 · {ctx[:100]}")
                elif per and per_hint and per != per_hint and not per_strong:
                    # (2026-08-15 5차) 회사 프로필 **교정** — 이력상(BZ 2022~) 한 종류 기간만
                    # 제시해 온 회사(90%+·n≥4)에서 문맥 판정이 반대로 나오면, 그 판정은 이웃
                    # 불릿의 다른 지표 기간이 새어 들어온 것이다. 실측: VZ·IR·TEX·SNDR·XOS 는
                    # 전부 이력 FY 100%(n 15~19) 회사인데 연간 EPS·매출이 0q/+1q 로 태그돼
                    # 분기 컨센 대비 +180~365% 갭을 만들었다(VZ 는 옆 불릿의 "third-quarter
                    # 2026" 매출 성장률 문구, IR 은 "1H 48% | 2H 52%" 페이징 주석이 근거로
                    # 오채택). 분기 가이던스를 한 번도 낸 적 없는 회사다 — 프로필로 교정한다.
                    # (2026-08-16) 단, **약한 근거**(머리글·앞 400자·뒤 90자 추정)일 때만 —
                    # 값 옆에 회사가 직접 쓴 기간(①구절 안·②같은 문장)은 프로필보다 우선한다
                    # (실측 SILC: "raising our full-year revenue guidance to $93 to $95 million"
                    # 명시를 '이력상 분기만' 프로필이 뒤집어 +263% 갭 — 명시가 이긴다).
                    per = per_hint
                    ctx += " [기간: 회사 프로필로 교정(이력상 %s만 제시)]" % ("연간" if per_hint == "Y" else "분기")
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
                    # (2026-08-16) lead(라벨~숫자 사이)도 함께 검사한다 — "recognize annual
                    # revenue **related to the license agreement** between $200-$225 million"
                    # (실측 AMCX: 라이선스 계약 관련 부분 매출 212.5M 이 전사 연간 매출로
                    # 채택돼 컨센 2,425M 대비 −91%). 부분 지표 수식이 라벨 뒤에 오는 형태.
                    if re.search(_PART, near + " " + lead, re.I):
                        skip.append(f"rev: 전사 아님(부분 지표) · {ctx[:130]}")
                        continue
                    # (2026-08-15) 라벨 앞 60자에 ®·™ 상표 표기가 있으면 **제품 매출**이다
                    # (실측 IRWD "LINZESS ® (linaclotide) U.S. net sales guidance" — 제품
                    # 매출을 전사 컨센과 비교해 +866%. 상표 뒤에 성분명·지역 수식이 붙어
                    # '직전' 패턴으로는 놓쳤다). 전사 매출 문맥 60자 안에 상표 기호가
                    # 등장하는 경우는 실무상 없다.
                    if re.search(r"[®™]", near):
                        skip.append(f"rev: 상표(®·™) 제품 매출 → 전사 아님 · {ctx[:110]}")
                        continue
                    # (2026-08-15) "Revenue **from sales of Captisol**"(실측 LGND) — 라벨 뒤에
                    # 제품·원천 한정이 붙으면 전사 매출이 아니다.
                    # (3차) "revenue expectation **for our COVID-19 products**, down to ~$4B"
                    # (실측 PFE — 제품군 매출 40억을 전사 615억과 비교해 −93%) 도 같은 부류.
                    if re.search(r"\bfrom\s+(?:the\s+)?(?:sales?\s+of|royalt)|\bproducts?\b", lead, re.I):
                        skip.append(f"rev: 제품·원천 한정 → 전사 아님 · {ctx[:110]}")
                        continue
                    # (2026-08-16) 수식어는 **라벨 직전 토큰**만 본다 — 종전엔 near(앞 60자)
                    # 전체에서 마지막 'X revenue' 를 찾아, 다른 문장에 있던 낱말이 현재
                    # 라벨의 수식어로 오인됐다. 실측 NE: "Backlog excludes mobilization and
                    # **demobilization revenue**. Outlook For the full year 2026, Revenue
                    # guidance is reduced to $2,800-$2,900 million" 에서 앞 문장의
                    # 'demobilization' 이 근거가 돼 명시된 전사 매출 2.8~2.9B(BZ 동일)이 기각.
                    # 라벨 앞이 숫자·문장부호로 끝나면(“…2026, Revenue”) 수식어가 없는 것이니
                    # 검사를 건너뛴다. 진짜 부분 매출은 _PART 정규식이 별도로 막는다.
                    mw = re.search(r"([A-Za-z][\w\-]*)\s*$", near)
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
                elif metric == "ffo":
                    # (2026-08-21) 리츠 FFO — 주당 값만 받는다. 리츠 보도자료는 총액 FFO
                    # ("AFFO of $433 million")와 주당 FFO("$1.47 per share")를 나란히 쓰는데,
                    # 총액에는 단위(million/billion)가 반드시 붙는다. 단위가 붙은 값은 총액이다.
                    if re.search(r"^\s*(?:million|billion|bn|mm)\b", txt[m.end():m.end() + 12], re.I) \
                            or re.search(r"(?:million|billion)\s*$", lead, re.I):
                        skip.append(f"ffo: 총액 표기(주당 아님) · {ctx[:110]}")
                        continue
                    # 조정 명세표의 **비용 항목**은 FFO 가 아니다 — 리츠 가이던스 표는
                    # "General and Administrative expense, net of adjustments **for FFO as
                    # Adjusted** $65 to $75" 처럼 항목명 뒤에 FFO 를 단서로 붙인다. 라벨이
                    # FFO 로 잡히지만 값은 그 비용(백만 달러)이다(실측 UDR 65~75 채택 →
                    # BZ 2.53 대비 +2,667%). 라벨 **앞**에 다른 지표명이 있으면 그 항목이다.
                    # 라벨 바로 앞이 전치사로 이어지면 FFO 는 그 항목을 **수식**할 뿐 주어가
                    # 아니다("… expense, net of adjustments **for** FFO as Adjusted").
                    # 리츠 표는 FFO 행 위아래에 순이익·배당·마진 행이 늘어서므로, 앞 문맥에
                    # 다른 지표명이 있다는 이유만으로 막으면 정상 FFO 까지 사라진다(실측: 그렇게
                    # 했더니 미추출 34→40 으로 늘었다) — 전치사 연결일 때만 막는다.
                    if re.search(r"\b(?:for|of|to|in|on)\s*$", near, re.I) \
                            and re.search(_OTHER, near[-45:], re.I):
                        skip.append(f"ffo: 앞 항목 '{_OTHER_HIT(near[-45:])}' 를 수식 · {ctx[:110]}")
                        continue
                    # 인수·거래의 **효과**를 말하는 문장은 가이던스가 아니다 — "expected to be
                    # accretive to FFO per share … $0.35"(실측 PSA: BZ Core FFO 16.90 대비 −98%).
                    if re.search(r"\b(?:accretive|dilutive)\s+to\s*$|\bimpact\s+(?:on|to)\s*$|"
                                 r"\bcontribut\w+\s+to\s*$", near, re.I):
                        skip.append(f"ffo: 거래 효과 서술(가이던스 아님) · {ctx[:110]}")
                        continue
                    # "Increased 2026 AFFO Guidance **$0.01 to** $1.41 - $1.43"(실측 PSTL) —
                    # 앞 숫자는 상향 **폭**이고 실제 범위는 뒤의 두 값이다. 매칭 직후에
                    # 또 하나의 금액이 대시로 이어지면 (hi, 그 값)이 범위다.
                    _nx = re.match(r"\s*[-–—]\s*\$?\s?([\d.]+)(?!\d)", txt[m.end():m.end() + 14])
                    if _nx and hi > 0 and lo / hi < 0.2:
                        _v = float(_nx.group(1))
                        if hi <= _v < hi * 1.5:
                            lo, hi = hi, _v
                            ctx += " [상향폭 표기 → 뒤 범위 채택]"
                    if not (0 < lo <= hi < 100):
                        skip.append(f"ffo: 값 범위 비정상({lo}~{hi}) · {ctx[:110]}")
                        continue
                    # core/adjusted/normalized 는 리츠가 쓰는 조정 FFO 표기다. BZ 도 이 기준을
                    # 쓰므로(g_bz_type=FFO) 어느 쪽인지 기록해 둔다.
                    # 판정 범위에 **매칭된 라벨 자체**를 넣어야 한다 — lead 는 라벨 '끝'부터라
                    # 라벨 안의 Normalized/Core 가 보이지 않는다(실측 VTR: 'Normalized FFO Per
                    # Share Range* $3.82-$3.89' 가 기본 FFO 로 분류돼 먼저 잡힌 Nareit FFO
                    # 3.69~3.76 을 교체하지 못했다 → BZ 3.88 대비 −4.1%).
                    _fb = "core" if re.search(r"\bAFFO\b|"
                                              r"\b(?:core|adjusted|normalized)\s*"
                                              r"(?:A?FFO\b|funds\s+from)",
                                              txt[m.start():m.start() + 45] + " " + lead + near,
                                              re.I) else "ffo"
                    add("ffo", per, lo, hi, ctx, _fb)
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
                    # (2026-08-15 5차) 검사 범위를 back300+ctx → **라벨 인접(lead+near)** 으로
                    # 좁힌다 — 표에서 EPS 행과 FFO 행을 **별도 항목으로 나란히** 제시하는
                    # 회사(실측 CXW: Diluted EPS·Adjusted Diluted EPS·FFO per share 가 각각
                    # 한 행)는 EPS 가 진짜 EPS 인데, 이웃 행의 FFO 가 back300 에 걸려 정상
                    # EPS 후보가 통째로 기각됐다. 리츠 자체는 종목 sector 속성(guidance_gap 의
                    # Real Estate 판정)이 하류에서 걸러 주므로, 파스 단계 가드는 라벨에 FFO 가
                    # 직접 붙은 경우만 막으면 된다.
                    if re.search(r"\bFFO\b|funds from operations", lead + near, re.I):
                        skip.append(f"eps: REIT(FFO 기반) — EPS 는 FFO 컨센과 비교 불가 · {ctx[:110]}")
                        continue
                    # (2026-08-15) ctx(값 **뒤** 40자 포함)로 기준을 판정하지 않는다 —
                    # "diluted EPS $1.48-$1.58 and **adjusted** diluted EPS $1.55-$1.65" 에서
                    # 앞(GAAP성) 값이 뒤 항목의 'adjusted' 를 끌어와 adj 로 오인, 진짜 조정
                    # 값의 교체(add 오버라이드)까지 막았다(실측 WWW). 기준은 값 **앞** 문맥만.
                    # lead(라벨~숫자 사이)가 가장 가깝다 — "Earnings per Share: GAAP: $1.08"(실측
                    # CSCO)의 GAAP 표기는 lead 에만 있다.
                    # (2026-08-15 5차) **다른 지표에 붙은 adjusted 는 기준 근거가 아니다** —
                    # 표에서 "➣ Adjusted Net Income … ➣ Diluted EPS $…" 처럼 이웃 행 라벨의
                    # 'Adjusted' 가 near/back 에 걸리면 GAAP 성 EPS 가 adj 로 등록되고, 그러면
                    # 뒤따르는 진짜 Adjusted Diluted EPS 의 교체(add 오버라이드)가 "같은 기준
                    # 이미 있음"으로 막힌다(실측 CXW: 오기값 15.00~15.20 이 adj 로 굳어
                    # 1.62~1.70 교체 불발 → +793%). 지표명이 따라붙은 adjusted 는 지우고 판정한다.
                    _oadj = (r"adjusted\s+(?:net\s+income|ebitda\w*|free\s+cash(?:\s+flow)?|"
                             r"operating\s+(?:income|margin|earnings)|revenu\w+|gross\s+(?:margin|profit)|"
                             r"net\s+leverage)")
                    bas = (_basis(lead) or
                           _basis(re.sub(_oadj, " ", near, flags=re.I)) or
                           _basis(re.sub(_oadj, " ", back, flags=re.I)))
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
    # ────────────────────────────────────────────────────────────────────────
    # (2026-08-21) **성장률 가이던스** — 금액을 아예 제시하지 않고 성장률로만 말하는 회사.
    # 실측: 원문에 금액이 없는 미확보 279건 중 성장률 표기가 있는 것 47건
    # (범위% 25 · up/increase 10 · 단일% 8 · 서술형 2 · 역순 2).
    #   예) KARO 'EPS growth between 18% and 23%' · GPC 'Total sales growth 3% to 5.5%' ·
    #       ADP 'EPS growth of 9% to 11%' · BLDR 'net sales growth of approximately 1%'
    # 금액 환산은 도입하지 않는다(이 파일 첫머리 2026-08-16 실측 결론) — 성장률 **그대로**
    # 별도 필드에 싣고 화면에도 성장률로 표시한다. 컨센서스는 금액이라 갭은 만들지 않는다.
    # 'low-single digit' 같은 서술형은 숫자 범위로 바꾸려면 추정이 들어가므로 넣지 않는다.
    # \b 로 닫아 과거형을 배제한다 — 'increased' 는 'increase' 뒤가 d 라 단어경계가 아니다.
    # (실측 PEP: 'Core constant currency EPS **increased** 1% and 3%' 은 지난 실적 서술인데
    #  과거형이 걸려 연간 EPS 성장률 가이던스로 실렸다.)
    _GW = r"\b(?:growth|grow|increase|rise|expand)\b"
    _P = r"(\d+(?:\.\d+)?)\s*%"
    for metric, label in (("rev", r"(?:revenues?|(?:net|total)\s+sales)"),
                          ("eps", r"(?:(?:diluted\s+)?earnings per (?:diluted\s+|common\s+)?share|\beps\b)")):
        if metric + "_lo" in out or "fy_" + metric + "_lo" in out:
            continue                                       # 금액을 이미 확보했으면 성장률은 불필요
        gp = r"(?:(?!" + label + r")[^.•●]){0,70}?"
        forms = [
            ("grange", label + gp + _GW + r"(?:\s+(?:of|between|in|to|at))?"
                       r"[^.•●]{0,28}?" + _P + r"\s*(?:to|-|–|and|through)\s*" + _P),
            ("gpm",    label + gp + _GW + r"[^.•●]{0,28}?" + _P +
                       r"\s*(?:±|\+/-|plus or minus)\s*" + _P),
            ("gsingle", label + gp + _GW + r"\s+of\s+(?:(?:approximately|about|around)\s+)?" + _P),
        ]
        for kind, pat in forms:
            done = False
            for m in re.finditer(pat, txt, re.I):
                seg = txt[max(0, m.start() - 130):m.end() + 40]
                # 전망 문맥은 **같은 문장(불릿)** 또는 **바로 앞 머리글**에서만 인정한다.
                # 앞 130자를 통째로 보면 두 문장 앞의 'Guidance' 가 실적 하이라이트 불릿까지
                # 전망으로 만들어 버린다(실측 CMCO: 제목 '…sales in Q1 FY27; Increases FY27
                # Guidance' 뒤 실적 불릿 'Net sales growth of 125% Y/Y driven by the Kito
                # Crosby Acquisition' 이 연간 매출 성장률 가이던스로 실렸다).
                # 불릿 목록은 머리글에만 guidance/outlook 이 있고 항목엔 없으므로
                # (실측 MIR '…guidance for the fiscal year ending December 31, 2026. •
                #  Revenue growth of approximately 22.0% - 24.0%') 직전 한 문장까지는 본다.
                _BD = ("• ", "● ", "▪ ", "· ", ": ")
                _b = max(txt.rfind(". ", 0, m.start()),
                         *(txt.rfind(x, 0, m.start()) for x in _BD))
                _cur = txt[max(0, _b):m.end() + 40]
                if not re.search(_FORE, _cur, re.I):
                    # 직전 문장을 찾을 때 10자를 물러선다 — "…2026. • Revenue" 처럼 마침표와
                    # 불릿이 붙어 있으면 둘이 별개 경계로 잡혀 직전 문장이 ". " 두 글자가 된다.
                    _b2 = max(txt.rfind(". ", 0, max(0, _b - 10)),
                              *(txt.rfind(x, 0, max(0, _b - 10)) for x in _BD))
                    if not re.search(_FORE, txt[max(0, _b2):max(0, _b)], re.I):
                        continue                           # 전망 문맥이 아니면 실적 서술이다
                # 이미 이룬 결과를 서술하는 동사 뒤의 성장률은 지난 실적이다.
                # 실측 PACK: 'these factors **contributed to** net revenue growth of 14.0%'
                # — 불릿 목록 머리글에 outlook 이 있어 전망 문맥 검사를 통과했다.
                if re.search(r"\b(?:contributed\s+to|drove|delivered|reported|achieved|"
                             r"resulted\s+in|generated|posted|recorded|led\s+to)\s*$",
                             txt[max(0, m.start() - 40):m.start()], re.I):
                    skip.append(f"{metric}성장률: 지난 실적 서술 · {seg[:90]}")
                    continue
                # 라벨과 숫자 사이에 **다른 지표**가 끼면 그 숫자는 그쪽 것이다.
                # 실측 KARO: 'Cartrack Subscription Revenue growth to accelerate, with
                # **EPS growth of 21%**' 에서 앞 revenue 라벨이 EPS 성장률을 가져갔다.
                _other = (r"\beps\b|earnings per share" if metric == "rev"
                          else r"\brevenues?\b|\bnet sales\b|\btotal sales\b")
                if re.search(_other, m.group(0), re.I):
                    skip.append(f"{metric}성장률: 다른 지표의 값 · {m.group(0)[:90]}")
                    continue
                # 세그먼트·부문 성장률은 전사 성장률이 아니다. 라벨 바로 앞 단어가 전사임을
                # 확인해 주는 낱말이 아니면 기각한다(금액 파서와 같은 규칙).
                # 실측 DIS: 'Entertainment SVOD (1) revenue growth of 11%' — 부문 매출이다.
                # 수식어 검사는 **매출에만** 건다 — EPS 는 부문별로 쪼개지 않으므로
                # 'adjusted diluted EPS growth of 9% to 11%'(실측 ADP)의 'diluted' 같은
                # 정상 수식어까지 걸러 버린다.
                if metric == "rev":
                    _nr = txt[max(0, m.start() - 60):m.start() + 40]
                    if re.search(_PART, _nr, re.I):
                        skip.append(f"rev성장률: 전사 아님(부분 지표) · {seg[:90]}")
                        continue
                    _mw = re.search(r"([A-Za-z][\w\-]*)\s*(?:\([^)]{0,10}\)\s*)?$",
                                    txt[max(0, m.start() - 40):m.start()])
                    if _mw and re.sub(r"[^a-z]", "", _mw.group(1).lower()) not in _CORP_W:
                        skip.append(f"rev성장률: 수식어 '{_mw.group(1)}' → 전사 아님 · {seg[:90]}")
                        continue
                try:
                    a = float(m.group(1))
                    b = float(m.group(2)) if m.lastindex and m.lastindex >= 2 else None
                except Exception:
                    continue
                lo, hi = (a, a) if b is None else ((a - b, a + b) if kind == "gpm" else (a, b))
                if lo > hi or not (-100 < lo <= hi < 200):
                    continue
                per, _ = _period(txt, m.start(), m.end())
                if not per and per_hint:
                    per = per_hint
                if not per:
                    skip.append(f"{metric}성장률: 기간 미명시 · {seg[:100]}")
                    continue
                pre = "" if per == "Q" else "fy_"
                if pre + metric + "_gr_lo" in out:
                    continue
                out[pre + metric + "_gr_lo"], out[pre + metric + "_gr_hi"] = round(lo, 1), round(hi, 1)
                ev[pre + metric + "_gr"] = re.sub(r"\s+", " ", seg)[:400]
                done = True
                break
            if done:
                break

    if ev:
        out["_ev"] = ev
    if skip:
        out["_skip"] = skip[:20]
    return out
