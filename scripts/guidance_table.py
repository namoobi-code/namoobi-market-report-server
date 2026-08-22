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

from guidance_parse import _QRE, _YRE, _YEXCL, _OTHER, _ADJ, _GAAP, _fwd_q

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
# (2026-08-16) **반기 열은 쓰지 않는다** — 반기는 분기도 연간도 아니라서 어느 컨센과도
# 비교할 수 없다. 문장 파서에서는 '연간이 아님' 판정에만 쓰지만, 표에서는 그 열의 값이
# 곧 반기 실적이라 채택하면 반드시 틀린다(실측 DD: "2H'26E $3,660-$3,690 | Full Year
# 2026E $7,160-$7,190" 에서 반기 3,675 가 Q3 컨센 1,835 와 비교돼 +100%).
#   끝에 \b 를 두면 안 된다 — 실측 표기가 "2H'26**E**"(Estimate 접미)라 단어경계가
#   성립하지 않아 규칙이 통째로 불발됐다.
_R_HALF = r"\b[12]H\s?['’]?\s?\d{2}|\b(?:first|second)[-\s]half\b|\bH[12]\b|\bhalf\s+year\b"
# 행 라벨
# (2026-08-22) reported/operating 접두 허용 — 실측 EFX 'Reported Revenue' 행이 라벨
# 불일치로 통째로 무시됐다. reported=보고 기준(전사), operating revenue=영업수익(전사).
_L_REV = r"^(?:total\s+|net\s+|consolidated\s+|reported\s+|operating\s+)*(?:revenues?|net\s+sales|sales)\b"
_L_EPS = (r"(?:earnings|net\s+income|income)\s+per\s+(?:diluted\s+|common\s+)?share|\beps\b")
_L_CAPEX = r"capital\s+(?:expenditures?|spending)|\bcapex\b"
_L_FFO = r"\bffo\b|funds\s+from\s+operations|\baffo\b"


def _clean(s):
    s = (s or "").replace("​", " ").replace("\xa0", " ").replace("–", "-").replace("—", "-")
    return re.sub(r"\s+", " ", s).strip()


def _grid(tb):
    """<table> → colspan 전개한 2차원 텍스트 그리드.

    (2026-08-21 검토·보류) SEC 표에는 전부 빈 더미 행(<td> 24개가 모두 빈 칸)이 섞여
    있어 ncol 을 부풀린다(실측 EFX: 데이터 5열인데 ncol=24). 이를 제거하거나 빈 열까지
    지우면 EFX 계열이 풀릴 것 같지만, **실측하면 오히려 손해다** — 머리글 행 판정이
    한 칸씩 밀려 HLIT 연간 매출이 515M 대신 실적 열 173M 으로 바뀌었다(gt2 31/0 → 30/1).
    빈 행도 열 정렬 정보의 일부이므로 그대로 둔다. EFX 계열은 다른 접근이 필요하다.
    """
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
    # (2026-08-22) ± 표기 셀 — "$0.75 +/- $0.09"(실측 FORM). 종전 정규식은 범위·단일값만
    # 받아 이 셀이 None 이 됐고, 옆의 조정 항목($0.11)이 대신 채택됐다.
    pm = re.match(r"^\$?\s*([\d,]+(?:\.\d+)?)\s*(billion|million|bn|mm|thousand|[BM])?"
                  r"\s*(?:±|\+/-)\s*\$?\s*([\d,]+(?:\.\d+)?)\s*(billion|million|bn|mm|thousand|[BM])?$",
                  s, re.I)
    if pm:
        h = pm.group(4) or pm.group(2)

        def _u(u):
            u = (u or "").lower()
            u = {"b": "billion", "m": "million"}.get(u, u)
            return _MULT.get(u, mult)
        try:
            c = float(pm.group(1).replace(",", "")) * _u(pm.group(2) or h)
            d = float(pm.group(3).replace(",", "")) * _u(h)
        except Exception:
            return None
        return (c - d, c + d)
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


def _is_year_cell(s):
    """셀이 **연도 하나**뿐인가 — 표 머리글의 기간 라벨이지 금액이 아니다.
    (2026-08-16) 실측 REZI: 머리글 행 "($ in millions) | Q3 2026 | 2026" 의 '2026' 이
    금액으로 인식돼 그 행이 데이터 행으로 판정 → 머리글이 통째로 유실되고 열 기간이
    전부 미확정이 됐다(Revenue Q3 705~730 · FY 2,900~2,950 이 둘 다 버려짐)."""
    return bool(re.match(r"^\s*(?:FY\s*)?(?:19|20)\d\d\s*$", _clean(s or "")))


def _col_meta(head_rows, ncol, gcap=False):
    """머리글 행들 → 열별 {per: 'Q'|'Y'|None, role: set}. 위→아래로 덮어쓴다.

    gcap: 범위(Low/High)를 제시하는 가이던스 표인가. True 면 'months ended' 를 실적 열
          표기로 보지 않는다 — 가이던스 표도 대상 기간을 'For the three months ended
          September 30, 2026' 로 쓴다(실측 OPK: 전 값 열이 act 로 찍혀 통째로 버려졌다).
          ※ 이 완화만으로는 OPK 가 회수되지 않는다. 빈 더미 행 제거가 함께 있어야
             열 정렬이 맞는데, 그 처리는 HLIT 를 깨뜨려 보류했다(_grid 주석 참조).
    """
    meta = [{"per": None, "role": set()} for _ in range(ncol)]
    for row in head_rows:
        # (2026-08-21) **표 제목 행**(colspan 으로 전 열이 같은 문구)은 열 구분 정보가 아니다.
        # 실측 EFX: 제목 '2026 Third Quarter and Full Year Guidance' 가 24열 전부에 퍼져
        # 라벨 열까지 분기(Q)로 칠했고, 그 아래 'Q3 2026 | FY 2026' 두 단 머리글의
        # 열 구분이 묻혔다. 제목은 표 전체 캡션으로만 쓰고 열 판정에서는 건너뛴다.
        _nz = [c for c in row[:ncol] if c]
        if (len(_nz) >= 3 and len(set(_nz)) == 1
                and re.search(_QRE, _nz[0], re.I) and re.search(_YRE, _nz[0], re.I)):
            continue        # 분기·연간이 함께 든 제목 행은 열 구분 정보가 아니다
        for i in range(min(len(row), ncol)):
            c = row[i]
            if not c:
                continue
            if re.search(_QRE, c, re.I):
                meta[i]["per"] = "Q"
            elif _is_year_cell(c):
                # (2026-08-16) 열 머리글의 **맨몸 연도**("2026")는 연간 열이다 — 문장에서라면
                # 모호하지만 표 머리글에서는 그 열의 기간 라벨 외에 다른 뜻이 없다.
                # 실측 REZI 머리글 "Q3 2026 | 2026" = 분기 열 | 연간 열.
                meta[i]["per"] = "Y"
            else:
                ym = re.search(_YRE, c, re.I)
                if ym and not re.search(_YEXCL, c[:ym.start()][-60:], re.I):
                    meta[i]["per"] = "Y"
            for role, pat in (("prior", _R_PRIOR), ("cur", _R_CUR), ("lo", _R_LOW),
                              ("hi", _R_HIGH), ("mid", _R_MID), ("pct", _R_PCT), ("act", _R_ACT),
                              ("half", _R_HALF),
                              # (2026-08-22) GAAP↔Non-GAAP **조정표** 열 — 'GAAP | Reconciling
                              # Items | Non-GAAP' 3열 형식(실측 FORM). 열 기준을 구분해
                              # Non-GAAP 열을 우선 채택하고 조정 항목 열은 버린다.
                              ("gaapc", _GAAP), ("adjc", _ADJ),
                              ("recon", r"\breconcil\w+")):
                if role == "act" and gcap and not re.search(
                        r"\bactuals?\b|\breported\b|\bytd\b", c, re.I):
                    continue          # 가이던스 표의 'months ended' 는 대상 기간 표기다
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


def _runs(row):
    """행의 셀들을 **연속 중복을 접어** 순서대로 — colspan 전개 복제와 빈 스페이서를 걷어낸
    '논리적 셀 나열'. 열 인덱스는 버리고 순서만 남긴다."""
    out, prev = [], None
    for c in row:
        c = _clean(c)
        if not c:
            prev = None
            continue
        if c != prev:
            out.append(c)
        prev = c
    return out


def _ordinal_meta(head_rows):
    """머리글 행들 → (기간 나열, 역할 나열) — **순서 기반** 폴백용.

    (2026-08-22) 열 인덱스 정렬은 SEC 표의 빈 스페이서·행마다 다른 colspan 때문에
    어긋난다(실측 EFX: 머리글 'Q3 2026' 이 3~8열인데 값은 3~5·9~11열 — 같은 표인데
    행마다 전개 폭이 다르다). 빈 행을 지우면 다른 표가 깨진다(실측 HLIT 회귀).
    → 열 위치를 포기하고 **등장 순서**로 짝짓는다: 기간 행의 논리적 나열 [Q3, FY] 과
    Low/High 행의 나열 [lo, hi, lo, hi], 데이터 행의 숫자 나열 [a, b, c, d] 가
    개수까지 정확히 맞아떨어질 때만(2×기간 = 역할 = 숫자) 순서대로 배정한다.
    하나라도 어긋나면 채택하지 않는다 — 추측이 아니라 검산이다.
    """
    pers, roles = [], []
    for row in head_rows:
        rr = _runs(row)
        if not rr:
            continue
        # 기간 행 후보 — 모든 논리 셀이 기간으로 분류되고 Q·Y 가 둘 다 있으면 최우선
        cls = []
        for c in rr:
            if re.search(_QRE, c, re.I) or re.search(r"\bthree\s+months\b", c, re.I):
                cls.append("Q")
            elif _is_year_cell(c) or re.search(r"\b(?:twelve\s+months|year\s+end)", c, re.I) \
                    or (re.search(_YRE, c, re.I)
                        and not re.search(_YEXCL, c[:_ys(c)][-60:], re.I)):
                cls.append("Y")
            else:
                cls.append(None)
        if all(cls) and 1 <= len(cls) <= 4:
            if not pers or ("Q" in cls and "Y" in cls):
                pers = cls
        # 역할 행 후보 — 전부 Low/High 이고 lo·hi 가 번갈아 나오면 채택
        rcls = []
        for c in rr:
            if re.search(_R_HIGH, c, re.I):
                rcls.append("hi")
            elif re.search(_R_LOW, c, re.I):
                rcls.append("lo")
            else:
                rcls.append(None)
        if rcls and all(rcls) and len(rcls) % 2 == 0 \
                and all(rcls[i] == ("lo", "hi")[i % 2] for i in range(len(rcls))):
            if not roles or len(rcls) > len(roles):
                roles = rcls
    return pers, roles


def _ys(c):
    m = re.search(_YRE, c, re.I)
    return m.start() if m else 0


def _pick_cols(meta, vals, per):
    """한 기간(per)의 값 열들에서 (lo, hi) 확정. 확정 못 하면 None(추측 금지)."""
    idx = [i for i, mt in enumerate(meta)
           if mt["per"] == per and vals.get(i) is not None
           and not (mt["role"] & {"act", "pct", "mid", "half", "recon"})]
    if not idx:
        return None, None
    # (2026-08-22) GAAP↔Non-GAAP 조정표 — Non-GAAP(조정) 열이 있으면 그쪽만 쓴다.
    # 컨센서스가 조정 기준이라 GAAP 열을 집으면 반드시 어긋난다(실측 FORM:
    # 'GAAP | Reconciling Items | Non-GAAP' 3열에서 GAAP 0.75 와 조정항목 0.11 을 집어
    # BZ Non-GAAP 0.86 과 불일치). 문장 파서의 'GAAP 기준 기각' 규칙과 같은 원칙이다.
    adjc = [i for i in idx if "adjc" in meta[i]["role"]]
    if adjc:
        idx = adjc
    elif any("gaapc" in meta[i]["role"] for i in idx) \
            and not all("gaapc" in meta[i]["role"] for i in idx):
        idx = [i for i in idx if "gaapc" not in meta[i]["role"]]
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
    # (2026-08-16) 같은 자격의 열이 여럿이어도 **값이 전부 같으면** colspan 전개로 한 셀이
    # 여러 열에 복제된 것이다 — 모호성이 없으므로 그 값을 쓴다. 종전엔 이 경우까지
    # '열 확정 불가'로 버려, 구조가 멀쩡한 표가 통째로 기각됐다(실측 GO: Previous 3열|
    # Current 2열 복제 · REZI: Q3 3열|FY 2열 복제 — 둘 다 원문에 금액이 명시된 표).
    vs = [vals[i] for i in use]
    if all(v == vs[0] for v in vs) and use[-1] - use[0] == len(use) - 1:
        # 값이 같고 열 인덱스가 **연속**이어야 colspan 복제다. 값만 같고 떨어져 있으면
        # 우연히 일치한 별개 열일 수 있으므로 추측하지 않는다.
        return vs[0]
    # 값이 서로 다른 다중 열인데 Low/High 구분도 없다 → 어느 열이 가이던스인지 모른다
    return None, None


def parse_tables(html, txt_hint=""):
    """8-K 원문 HTML → 가이던스 dict (parse_guidance 와 같은 키). 확정 못 하면 비운다.

    (2026-08-15 성능) 전체 문서를 bs4 로 파싱하지 않는다 — 보도자료에는 재무제표
    수십 개 표가 붙어 있어 전 종목 상시 실행 시 재파싱이 시간대 단위로 늘어난다(실측).
    정규식으로 <table> 블록을 끊고, **직전 문맥 250자 + 표 앞부분에 전망 키워드가
    있는 블록만** bs4 로 파싱한다(재무제표·비교 표는 bs4 진입 전에 걸러진다).
    """
    out, ev = {}, {}
    if not html:
        return out
    cands = []
    for tm in re.finditer(r"<table[\s\S]*?</table>", html, re.I):
        pre = _clean(re.sub(r"<[^>]+>", " ", html[max(0, tm.start() - 1500):tm.start()]))[-250:]
        if re.search(_FORE, pre + " " + _clean(re.sub(r"<[^>]+>", " ", tm.group(0)[:4000])), re.I):
            cands.append((pre, tm.group(0)))
    for cap, seg in cands[:15]:
        try:
            tb = BeautifulSoup(seg, "html.parser").find("table")
        except Exception:
            continue
        if tb is None:
            continue
        grid = _grid(tb)
        if len(grid) < 2:
            continue
        ncol = max(len(r) for r in grid)
        head_txt = cap + " " + " ".join(" ".join(r) for r in grid[:3])
        # 전망 판정 — 캡션 말미 250자 + 표 머리글(멀리 있는 guidance 단어에 실적 표가
        # 낚이지 않게, 실측 HLIT).
        near_txt = cap + " " + " ".join(" ".join(r) for r in grid[:3])
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
            # 연도 셀(기간 라벨)은 금액으로 치지 않는다 — 머리글이 끊기면 열 기간이 통째로 미확정
            if any(_cell_val(c, mult) and not _is_year_cell(c) for c in row[1:]):
                break
            head_rows.append(row)
            data_start = ri + 1
        if not head_rows:
            continue
        # (2026-08-21) 'months ended' 를 실적 열로 볼지 — 캡션에 guidance 가 있다는 것만으로는
        # 부족하다(실적 비교 표도 가이던스 문단 근처에 붙는다. 실측 HLIT: 완화했더니 연간
        # 매출이 173M 으로, 정답 515M 대신 실적 열을 집었다). 머리글에 **Low 와 High 가
        # 모두** 있는 표, 즉 범위를 제시하는 전망 표일 때만 완화한다 —
        # 실측 OPK 'For the three months ended September 30, 2026 … Low High Low High'.
        _gcap = bool(re.search(r"\b(?:guidance|outlook)\b", cap, re.I)
                     and re.search(_R_LOW, head_txt, re.I)
                     and re.search(_R_HIGH, head_txt, re.I))
        meta = _col_meta(head_rows, ncol, _gcap)
        opers, oroles = _ordinal_meta(head_rows)      # 순서 기반 폴백용 (2026-08-22)
        # 표 전체가 한 기간이면(캡션 명시) 기간 없는 열에 부여.
        # (2026-08-15 2차) 캡션의 분기 토큰은 **전망 문맥일 때만** 인정 — "reported second
        # quarter results" 같은 실적 문구의 분기가 표 기간으로 오인돼 연간 표가 분기로
        # 분류됐다(실측 CNMD 연간 매출 1,358 이 0q 로 +304% · PIII +286%). 과거 표기
        # ('months ended')가 낀 캡션의 분기도 제외한다. 문장 파서의 _fwd_q 를 공유한다.
        if not any(mt["per"] for mt in meta):
            # (2026-08-15 3차) 캡션에 실적 분기 문구와 연간 가이던스 문구가 **공존**하면
            # (예: "…third quarter results … full year 2026 guidance:") Q 를 무조건
            # 우선하던 종전 로직이 연간 표를 분기로 분류했다(실측 GRDN 연간 매출 1.43B 이
            # 0q 로 +294% · PIII +286%).
            # (2026-08-15 4차) '마지막 기간 토큰' 규칙도 부족했다 — 실측 PIII 캡션
            # "Revised Fiscal 2026 Guidance • Full-year revised guidance reflects the impact
            #  of underlying first half performance … recognized in the quarter." 에서
            # 마지막 토큰은 과거 실적을 서술하는 'first half/quarter' 라 다시 Q 로 떨어졌다.
            # 보도자료에서 표를 명명하는 것은 **Guidance/Outlook 머리글**이고 기간 수식어는
            # 그 어구에 붙는다("Revised Fiscal 2026 Guidance"). 따라서:
            #   ① 캡션의 **마지막** guidance/outlook 어구 앞 80자에서 기간 토큰을 찾아 채택
            #   ② 머리글에 기간이 없으면, 마지막 유효 기간 토큰(전망 문맥의 Q 또는 연간)
            cper = None
            golast = None
            for gm in re.finditer(r"\b(?:guidance|outlook)\b", head_txt, re.I):
                golast = gm
            if golast:
                seg = head_txt[max(0, golast.start() - 80):golast.start()]
                qp = [m.start() for m in re.finditer(_QRE, seg, re.I)
                      if not re.search(r"(?:months|quarter|year)\s+ended\b",
                                       seg[max(0, m.start() - 40):m.start() + 40], re.I)]
                yp = [m.start() for m in re.finditer(_YRE, seg, re.I)
                      if not re.search(_YEXCL, seg[:m.start()][-60:], re.I)]
                if qp or yp:
                    cper = "Q" if max(qp, default=-1) > max(yp, default=-1) else "Y"
            if not cper:
                qlast = ylast = -1
                for qm in re.finditer(_QRE, head_txt, re.I):
                    seg = head_txt[max(0, qm.start() - 60):qm.start() + 60]
                    if _fwd_q(seg) and not re.search(r"(?:months|quarter|year)\s+ended\b", seg, re.I):
                        qlast = qm.start()
                for ym in re.finditer(_YRE, head_txt, re.I):
                    if not re.search(_YEXCL, head_txt[:ym.start()][-60:], re.I):
                        ylast = ym.start()
                if qlast >= 0 or ylast >= 0:
                    cper = "Q" if qlast > ylast else "Y"
            if not cper:
                continue                               # 기간을 알 수 없는 표 — 버린다
            for mt in meta:
                mt["per"] = cper
        # (2026-08-16) **민감도 표** 가드 — "Effect on Adjusted EPS of a 10% change in fuel
        # prices"(실측 NCLH: 유가 민감도 0.02 가 Q3 EPS 로 채택돼 BZ 0.90 대비 −98%) 같은
        # 표는 가이던스가 아니라 변수 민감도다. 캡션·머리글에 민감도 문구가 있으면 표 전체 기각.
        if re.search(r"sensitivit|effect\s+o[fn]\s|impact\s+of\s+a\s|\b10%\s+change|"
                     r"change\s+in\s+(?:fuel|currency|fx|foreign|interest)", head_txt, re.I):
            continue
        table_has_ffo = any(re.search(_L_FFO, _clean(r[0]), re.I) for r in grid if r)
        for row in grid[data_start:]:
            if not row:
                continue
            # (2026-08-16) 한 <table> 안에 **블록이 여러 개** 오는 표가 있다 — 실측 NWL:
            # 위쪽 "Q3 2026 Outlook" 블록 아래에 "Updated Full Year 2026 | Previous Full
            # Year 2026" 블록이 이어진다. 첫 머리글만 붙들고 있으면 아래 블록의 연간 값이
            # 분기로 채택된다(연간 EPS 0.75 가 Q3 컨센 0.19 대비 +196%).
            # 데이터 도중 **금액 없는 기간·역할 머리글 행**을 만나면 그 행으로 열 의미를 갈아끼운다.
            if not any(_cell_val(c, mult) and not _is_year_cell(c) for c in row[1:]):
                if any(c and (re.search(_QRE, c, re.I) or _is_year_cell(c)
                              or re.search(_YRE, c, re.I)
                              or re.search(_R_PRIOR + "|" + _R_CUR + "|" + _R_LOW + "|" + _R_HIGH,
                                           c, re.I))
                       for c in row[1:]):
                    meta = _col_meta([row], ncol, _gcap)
                    _p2, _r2 = _ordinal_meta([row])
                    opers, oroles = (_p2 or opers), (_r2 or oroles)
                    continue
            label = _clean(row[0])
            if not label or _cell_val(label, mult):
                continue
            # 지표 판정 + 행 단위 안전장치(문장 파서와 동일 원칙)
            if re.search(_L_FFO, label, re.I):
                continue
            # (2026-08-16) **증분·영향·비경상 행** 가드 — "Diluted EPS impact"(실측 BOOT:
            # 관세 영향 0.38~0.06 이 연간 EPS 로 채택돼 BZ 9.02 대비 −95%) ·
            # "Revenue from contract termination"(실측 THC: 계약해지 매출이 전사 매출로
            # 채택돼 BZ 22,200 대비 −93%). 라벨에 영향·증분·해지 수식이 붙은 행은
            # 지표의 수준(level)이 아니다.
            if re.search(r"impact|effect|sensitiv|headwind|tailwind|contribution|"
                         r"termination|incremental|dilution\s+from|benefit\s+from", label, re.I):
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
            # 순서 기반 폴백용 — 논리적 숫자 나열(연속 중복 접기 · %·라벨 셀 제외)
            onums = [v for v in (_cell_val(c, rmult) for c in _runs(row[1:])) if v is not None]
            # (2026-08-16) **단위 미확정 기각** — 캡션·라벨에 단위 선언이 없고 셀에도 단위
            # 접미(billion/million/[BM])가 없으면 자릿수를 확정할 수 없다(문장 파서의
            # '단위 미표기 기각'과 동일 원칙). 실측 FSTR: 천단위 관례 표("Net sales $540,000",
            # 단위 주석 없음)를 원화폐 달러로 읽어 매출 0.54M 채택 → 컨센 560M 대비 −99.9%.
            if metric in ("rev", "capex") and mult == 1.0 and rmult == 1.0 and \
               not re.search(r"billion|million|\bbn\b|\bmm\b|[\d.]\s*[BM]\b",
                             " ".join(row[1:]), re.I):
                continue
            # ① 열 인덱스 기반(기존) → ② 실패 시 순서 기반 폴백.
            # 폴백은 기간 나열 × 2 = Low/High 나열 = 숫자 나열이 **정확히 맞을 때만** 쓴다.
            _pairs = []
            for per, pre in (("Q", ""), ("Y", "fy_")):
                lo, hi = _pick_cols(meta, vals, per)
                if lo is not None and hi is not None:
                    _pairs.append((per, pre, lo, hi))
            if not _pairs and opers and oroles \
                    and len(oroles) == 2 * len(opers) and len(onums) == len(oroles):
                _pairs = [(opers[j], ("" if opers[j] == "Q" else "fy_"),
                           onums[2 * j][0], onums[2 * j + 1][1])
                          for j in range(len(opers))]
                _pairs = [(p, pr, lo, hi) for p, pr, lo, hi in _pairs if lo <= hi]
            for per, pre, lo, hi in _pairs:
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
