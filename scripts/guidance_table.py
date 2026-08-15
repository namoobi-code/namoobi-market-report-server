#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""guidance_table.py v2 — HTML 표 **구조** 기반 가이던스 파서 (2026-08-15 전면 재작성).

v1 의 실패와 교훈
-----------------
v1 은 표를 텍스트로 평탄화한 뒤 휴리스틱으로 행·열을 추측했다. 정형 표(PTC·QCOM)는
맞췄지만 변형 표에서 행·열을 잘못 짚어 전면 적용 시 이상치가 6.2%→12.3% 로 늘었고
(실측 USNA +26,655% · MEC +4,869%), '다중 열 기각분만 보충' 시도조차 문장 파서의
안전장치를 우회해 오염을 만들었다(실측 HLIT +93,543% · ESS +11,002%).

v2 원칙
-------
① **구조를 읽는다** — BeautifulSoup 로 <tr>/<td> 그리드를 만들고 colspan 을 전개해
   열 정렬을 보존한다. 머리글 행에서 열마다 기간(분기/연간)·역할(Low/High/Prior/
   Updated/Actual/%증감)을 판정하고, 데이터 행은 라벨 → 지표 매핑 후 **자기 열의
   의미**에 따라 값을 배치한다. 추측하지 않는다 — 열 의미를 확정 못 하면 버린다.
② **문장 파서와 같은 안전장치** — 기간 정규식(_QRE/_YRE/_YEXCL)·다른항목(_OTHER)·
   REIT FFO·GAAP 배제·단위/범위 새니티를 동일 적용한다(정규식은 guidance_parse 에서
   import — 단일 진실원, 이원화 금지).
③ **검증 게이트** — Benzinga 대조(bz_diff)로 문장 파서 단독 대비 정확도가 떨어지지
   않음을 실측으로 확인한 뒤에만 파이프라인에서 사용한다.

출력: parse_guidance 와 같은 키(rev_lo/hi·eps_lo/hi·fy_*·*_basis) + _ev(근거).
"""
import re

from bs4 import BeautifulSoup

from guidance_parse import _QRE, _YRE, _YEXCL, _OTHER, _ADJ, _GAAP

_MULT = {"billion": 1e9, "bn": 1e9, "million": 1e6, "mm": 1e6, "thousand": 1e3}
_FORE = r"guidance|outlook|expect|anticipat|forecast|project|estimat"
# 열 역할
_R_PRIOR = r"\b(?:prior|previous|initial|original)\b"
_R_CUR = r"\b(?:updated?|revised?|current|new)\b"
_R_LOW = r"\blow(?:\s*end)?\b"
_R_HIGH = r"\bhigh(?:\s*end)?\b"
_R_MID = r"\bmid(?:point)?\b"
_R_PCT = r"%|\bpercent\b|growth|change|vs\.?|versus|yoy|y/y"
# 'Months **Ended**'(과거분사)=이미 끝난 기간의 실적 열. 'Ending'(진행형)=전망 열이라 제외.
_R_ACT = r"\bactuals?\b|\bactual\b|\breported\b|\bytd\b|\b(?:months|year)\s+ended\b"
# 행 라벨
_L_REV = r"^(?:total\s+|net\s+|consolidated\s+)*(?:revenues?|net\s+sales|sales)\b"
_L_EPS = (r"(?:earnings|net\s+income|income)\s+per\s+(?:diluted\s+|common\s+)?share|\beps\b")
_L_CAPEX = r"capital\s+(?:expenditures?|spending)|\bcapex\b"
_L_FFO = r"\bffo\b|funds\s+from\s+operations|\baffo\b"


def _clean(s):
    s = (s or "").replace("​", " ").replace("\xa0", " ").replace("–", "-").replace("—", "-")
    return re.sub(r"\s+", " ", s).strip()


def _grid(tb):
    """<table> → colspan 전개한 2차원 텍스트 그리드."""
    rows = []
    for tr in tb.find_all("tr"):
        cells = []
        for td in tr.find_all(["td", "th"]):
            txt = _clean(td.get_text(" "))
            try:
                span = max(1, min(int(td.get("colspan") or 1), 20))
            except Exception:
                span = 1
            cells.extend([txt] * span)
        if cells:
            rows.append(cells)
    return rows


def _cell_val(s, mult):
    """셀 → (lo, hi) 금액. 범위·단일값·괄호음수·각주번호 처리. 숫자 아니면 None."""
    s = _clean(s)
    if not s or re.search(r"%", s):
        return None                                   # 퍼센트 셀은 금액이 아니다
    s = re.sub(r"\((\d{1,2})\)", " ", s)              # 각주 "(1)" 제거 (음수 괄호는 소수·큰수라 보존)
    neg = bool(re.match(r"^\(\s*\$?\s*[\d,.]+\s*\)$", s))
    s = s.strip("()")
    m = re.match(r"^\$?\s*([\d,]+(?:\.\d+)?)\s*(billion|million|bn|mm|thousand|[BM])?"
                 r"\s*(?:-|to|–)\s*\$?\s*([\d,]+(?:\.\d+)?)\s*(billion|million|bn|mm|thousand|[BM])?$",
                 s, re.I)
    one = re.match(r"^\$?\s*([\d,]+(?:\.\d+)?)\s*(billion|million|bn|mm|thousand|[BM])?$", s, re.I)

    def n(v, u):
        try:
            x = float(v.replace(",", ""))
        except Exception:
            return None
        u = (u or "").lower()
        if u == "b":
            u = "billion"
        if u == "m":
            u = "million"
        return x * _MULT.get(u, mult)
    if m:
        h = m.group(4) or m.group(2)
        lo, hi = n(m.group(1), m.group(2) or h), n(m.group(3), h)
    elif one:
        lo = hi = n(one.group(1), one.group(2))
    else:
        return None
    if lo is None or hi is None:
        return None
    if neg:
        lo, hi = -hi, -lo
    return (lo, hi) if lo <= hi else (hi, lo)


def _col_meta(head_rows, ncol):
    """머리글 행들 → 열별 {per: 'Q'|'Y'|None, role: set}. 위→아래로 덮어쓴다."""
    meta = [{"per": None, "role": set()} for _ in range(ncol)]
    for row in head_rows:
        for i in range(min(len(row), ncol)):
            c = row[i]
            if not c:
                continue
            if re.search(_QRE, c, re.I):
                meta[i]["per"] = "Q"
            else:
                ym = re.search(_YRE, c, re.I)
                if ym and not re.search(_YEXCL, c[:ym.start()][-60:], re.I):
                    meta[i]["per"] = "Y"
            for role, pat in (("prior", _R_PRIOR), ("cur", _R_CUR), ("lo", _R_LOW),
                              ("hi", _R_HIGH), ("mid", _R_MID), ("pct", _R_PCT), ("act", _R_ACT)):
                if re.search(pat, c, re.I):
                    meta[i]["role"].add(role)
    # 두 단 머리글: 기간이 일부 열에만 붙으면(colspan 전개 후에도) 왼쪽 값을 상속하되,
    # **다른 기간이 나오기 전까지만** 잇는다.
    last = None
    for i in range(ncol):
        if meta[i]["per"]:
            last = meta[i]["per"]
        elif last and not (meta[i]["role"] & {"act", "pct"}):
            meta[i]["per"] = last
    return meta


def _pick_cols(meta, vals, per):
    """한 기간(per)의 값 열들에서 (lo, hi) 확정. 확정 못 하면 None(추측 금지)."""
    idx = [i for i, mt in enumerate(meta)
           if mt["per"] == per and vals.get(i) is not None
           and not (mt["role"] & {"act", "pct", "mid"})]
    if not idx:
        return None, None
    cur = [i for i in idx if "cur" in meta[i]["role"]]
    pri = [i for i in idx if "prior" in meta[i]["role"]]
    unq = [i for i in idx if i not in cur and i not in pri]
    use = cur or unq or pri                # 개정(cur) > 무표기 > 직전(prior)
    lo_c = [i for i in use if "lo" in meta[i]["role"]]
    hi_c = [i for i in use if "hi" in meta[i]["role"]]
    if lo_c and hi_c:
        return vals[lo_c[0]][0], vals[hi_c[0]][1]
    if len(use) == 1:
        return vals[use[0]]
    # 같은 자격의 열이 여럿인데 Low/High 구분도 없다 → 어느 열이 가이던스인지 모른다
    return None, None


def parse_tables(html, txt_hint=""):
    """8-K 원문 HTML → 가이던스 dict (parse_guidance 와 같은 키). 확정 못 하면 비운다."""
    out, ev = {}, {}
    if not html:
        return out
    try:
        soup = BeautifulSoup(html, "html.parser")
    except Exception:
        return out
    for tb in soup.find_all("table"):
        grid = _grid(tb)
        if len(grid) < 2:
            continue
        ncol = max(len(r) for r in grid)
        # 표 앞 문맥(캡션) — 전망 표인지, 단위 선언, 표 전체 기간.
        # (수정) 빈 문자열 노드가 홉을 소진해 캡션의 'OUTLOOK' 을 못 보던 문제 —
        # 비어 있지 않은 노드만 세고 범위를 넓힌다(실측 AKAM: 캡션 '2026 FINANCIAL
        # OUTLOOK' 이 바로 위에 있는데 표 전체가 비전망으로 기각).
        cap = ""
        node, hops = tb, 0
        while node is not None and hops < 25 and len(cap) < 800:
            node = node.find_previous(string=True)
            if node is None:
                break
            s = _clean(str(node))
            if s:
                cap = s + " " + cap
                hops += 1
        head_txt = cap + " " + " ".join(" ".join(r) for r in grid[:3])
        # (수정) 전망 판정은 **캡션 말미 250자 + 표 머리글**로만 — 캡션을 800자나 보면
        # 몇 문단 앞의 'guidance' 단어가 지난 분기 **실적 표**까지 전망으로 만든다
        # (실측 HLIT: Q2 실적 표의 133.5 를 Q3 가이던스 130 대신 채택).
        near_txt = cap[-250:] + " " + " ".join(" ".join(r) for r in grid[:3])
        if not re.search(_FORE, near_txt, re.I):
            continue                                   # 전망 표가 아니다(실적 비교 표 등)
        # 비교 표 가드 — 서로 다른 분기·연도 조합이 2개 이상인데 Low/High·Prior/Updated
        # 구분도 없으면 [당기|전기|전년] 실적 비교 표다(실측 HLIT table3: Q2'26|Q1'26|Q2'25).
        pers = set(re.findall(r"\bQ[1-4]\s*'?\s*20\d\d|\b(?:first|second|third|fourth)\s+quarter\s+(?:of\s+)?20\d\d",
                              " ".join(" ".join(r) for r in grid[:4]), re.I))
        if len(pers) >= 2 and not re.search(_R_LOW + "|" + _R_PRIOR + "|" + _R_CUR, head_txt, re.I):
            continue
        um = re.search(r"\(?\s*(?:\$\s*)?in\s+(million|billion|thousand)s?\b", head_txt, re.I)
        mult = _MULT.get((um.group(1).lower() if um else ""), 1.0)
        # 머리글 행 = 숫자 셀이 없는 상위 행들(최대 4)
        head_rows, data_start = [], 0
        for ri, row in enumerate(grid[:4]):
            if any(_cell_val(c, mult) for c in row[1:]):
                break
            head_rows.append(row)
            data_start = ri + 1
        if not head_rows:
            continue
        meta = _col_meta(head_rows, ncol)
        # 표 전체가 한 기간이면(캡션 명시) 기간 없는 열에 부여
        if not any(mt["per"] for mt in meta):
            cper = None
            if re.search(_QRE, head_txt, re.I):
                cper = "Q"
            else:
                ym = re.search(_YRE, head_txt, re.I)
                if ym and not re.search(_YEXCL, head_txt[:ym.start()][-60:], re.I):
                    cper = "Y"
            if not cper:
                continue                               # 기간을 알 수 없는 표 — 버린다
            for mt in meta:
                mt["per"] = cper
        table_has_ffo = any(re.search(_L_FFO, _clean(r[0]), re.I) for r in grid if r)
        for row in grid[data_start:]:
            if not row:
                continue
            label = _clean(row[0])
            if not label or _cell_val(label, mult):
                continue
            # 지표 판정 + 행 단위 안전장치(문장 파서와 동일 원칙)
            if re.search(_L_FFO, label, re.I):
                continue
            metric = None
            if re.search(_L_REV, label, re.I) and not re.search(
                    r"organic|segment|product|royalt|per\s+share|inorganic|same[-\s]store", label, re.I):
                metric = "rev"
            elif re.search(_L_EPS, label, re.I):
                if table_has_ffo:
                    continue                           # REIT 표 — EPS 는 FFO 컨센과 비교 불가
                if re.search(_GAAP, label, re.I) and not re.search(_ADJ, label, re.I):
                    continue                           # GAAP 전용 행
                metric = "eps"
            elif re.search(_L_CAPEX, label, re.I):
                metric = "capex"
            if not metric:
                continue
            # _OTHER 는 rev 행에만 — eps 라벨('Net Income Per Share')의 'net income' 이
            # _OTHER 와 충돌해 정당한 행이 기각됐다(실측 AMPL). 라벨이 이미 지표 정규식을
            # 통과했으므로 EBITDA 류는 애초에 여기 못 온다.
            if metric == "rev" and re.search(_OTHER, label, re.I):
                continue
            # (수정) 라벨 셀 안의 단위 선언 인정 — "Revenue (in millions)"(실측 AKAM)처럼
            # 단위가 캡션이 아니라 행 라벨에 붙는 표가 있다.
            rmult = mult
            lm = re.search(r"\(\s*in\s+(million|billion|thousand)s?\b", label, re.I)
            if lm:
                rmult = _MULT[lm.group(1).lower()]
            vals = {i: _cell_val(row[i], rmult) for i in range(1, min(len(row), ncol))}
            for per, pre in (("Q", ""), ("Y", "fy_")):
                lo, hi = _pick_cols(meta, vals, per)
                if lo is None or hi is None:
                    continue
                # 새니티 — 문장 파서와 동일
                if metric == "rev" and not (0 < lo <= hi and lo > 1e5 and hi / lo < 1.6):
                    continue
                if metric == "eps" and not (-100 < lo <= hi < 150):
                    continue
                if metric == "capex" and not (0 < lo <= hi and lo > 1e5 and hi / lo < 3):
                    continue
                k = pre + metric
                if k + "_lo" in out:
                    # 이미 있으면 조정(adj) 라벨이 무표기 값을 교체할 때만 허용
                    if not (metric == "eps" and re.search(_ADJ, label, re.I)
                            and out.get(k + "_basis") != "adj"):
                        continue
                out[k + "_lo"], out[k + "_hi"] = ((lo, hi) if metric != "eps"
                                                  else (round(lo, 2), round(hi, 2)))
                if metric == "eps":
                    out[k + "_basis"] = "adj" if re.search(_ADJ, label, re.I) else "unspec"
                ev[k] = ("[표] " + " | ".join(h for h in (" ".join(head_rows[0][:6]),) if h)
                         + f" | {label}: " + " · ".join(row[1:8]))[:300]
    if ev:
        out["_ev"] = ev
    return out
