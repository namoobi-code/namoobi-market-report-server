#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fetch_bigtech_debt.py — 💵 빅테크 조달구조(회사채·부채) 정본 (2026-08-31 신설)

3.1.8 AI 빅테크 CAPEX 의 짝 — '얼마 쓰나' 옆에 '그 돈을 어디서 구하나'.
핵심 신호 = 증분부채 ÷ CAPEX (FY24 9% → 2026 6월 LTM 32%, FactSet 2026-07-23).
자기 현금으로 짓던 데이터센터를 빚으로 짓기 시작했다는 뜻이고,
이는 3.1.15 HY 스프레드·3.1.9 메모리 사이클과 한 줄로 이어진다.

수집(전부 무인증·무료·stdlib):
  ① SEC EDGAR XBRL companyconcept (data.sec.gov) — 5사 분기 실측
     총부채·현금성자산·회사채 발행액/상환액·CAPEX·영업이익·감가상각
     ※ 회사마다 태그가 달라 TAGS 에 회사별 후보 리스트를 둔다(첫 히트 사용).
  ② FRED — IG 회사채 OAS(BAMLC0A0CM)·HY OAS(BAMLH0A0HYM2) = 조달비용 환경
  ③ 딜 타임라인·신용등급 = 시드 + debt_llm.json(보고서 Phase 3.8 웹서치 갱신) upsert

  ④ (2026-10-24) 네오클라우드 6사(CRWV·NBIS·IREN·CIFR·WULF·APLD) 별도 블록 `neo` — 금융리스 합산·이자보상·CAPEX÷매출
산출: data/db/bigtech_debt.json
cron: 45 6 * * *
"""
import json, subprocess, time, sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DB   = BASE / "data" / "db"
OUT  = DB / "bigtech_debt.json"
KST  = timezone(timedelta(hours=9))
UA   = "namoobi-market-report namoobi@gmail.com"

sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from nmr_fred import fred_series
except Exception:
    fred_series = None

# 회사: (심볼, 한글명, CIK, 결산월)
CO = [
    ("MSFT",  "마이크로소프트", "0000789019", 6),
    ("AMZN",  "아마존",         "0001018724", 12),
    ("GOOGL", "알파벳",         "0001652044", 12),
    ("META",  "메타",           "0001326801", 12),
    ("ORCL",  "오라클",         "0001341439", 5),
]

# ── (2026-10-24) 네오클라우드 그룹 — 매경ECONOMY 2026.10.21 커버 'AIDC NO WAY OUT' 반영.
#   기사의 핵심 경고: 투자 회수 부담은 데이터센터를 '운영하는' 쪽이 진다(코어위브 총부채 510억$·GPU 담보대출 85억$,
#   코어사이언티픽 계약 590MW 중 과금 395MW). 신용 리스크가 빅테크(순현금)에서 네오클라우드(순부채)로 옮겨갔는데
#   이 탭은 빅테크 5사만 보고 있었다. 같은 XBRL 파이프라인으로 6사를 붙인다.
#   빅테크와 다른 점: ① GPU 금융리스가 부채의 큰 몫이라 **금융리스 부채를 총부채에 합산** ② 이자비용·매출을 받아
#   이자보상배율(LTM EBITDA÷이자)·CAPEX÷매출을 추가로 본다 ③ 적자 기업이 많아 순부채/EBITDA 는 EBITDA>0 일 때만.
#   갤럭시디지털(GLXY)은 금융사 혼합이라 제외, 코어사이언티픽(CORZ)은 코어위브 피인수 절차로 제외.
CO_NEO = [
    ("CRWV", "코어위브",       "0001769628", 12),
    ("NBIS", "네비우스",       "0001513845", 12),
    ("IREN", "아이렌",         "0001878848", 6),
    ("CIFR", "사이퍼마이닝",   "0001819989", 12),
    ("WULF", "테라울프",       "0001083301", 12),
    ("APLD", "어플라이드디지털","0001144879", 5),
]

# 항목별 태그 후보 — 회사별 XBRL 태그 차이를 흡수(실측 probe 2026-08-31 기준)
TAGS = {
    # instant(잔액) — 합산
    "debt_lt":  ["LongTermDebtNoncurrent", "LongTermNotesAndLoans", "LongTermDebt"],
    "debt_st":  ["LongTermDebtCurrent", "NotesPayableCurrent", "DebtCurrent", "CommercialPaper"],
    "cash":     ["CashAndCashEquivalentsAtCarryingValue"],
    "sti":      ["ShortTermInvestments", "MarketableSecuritiesCurrent",
                 "AvailableForSaleSecuritiesDebtSecuritiesCurrent"],
    # duration(기간) — 분기 환산
    "issue":    ["ProceedsFromIssuanceOfLongTermDebt", "ProceedsFromIssuanceOfSeniorLongTermDebt",
                 "ProceedsFromDebtMaturingInMoreThanThreeMonths", "ProceedsFromDebtNetOfIssuanceCosts"],
    "repay":    ["RepaymentsOfLongTermDebt", "RepaymentsOfDebtMaturingInMoreThanThreeMonths",
                 "RepaymentsOfDebtAndCapitalLeaseObligations", "RepaymentsOfDebt"],
    "capex":    ["PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireProductiveAssets"],
    "opinc":    ["OperatingIncomeLoss"],
    "da":       ["DepreciationDepletionAndAmortization", "DepreciationAmortizationAndAccretionNet",
                 "Depreciation", "DepreciationAndAmortization"],
}
INSTANT = {"debt_lt", "debt_st", "cash", "sti"}
# 네오클라우드 전용 태그 — probe 2026-10-24 (APLD 는 LongTermNotesPayable, IREN 은 InterestExpenseNonoperating)
TAGS_NEO = dict(TAGS)
TAGS_NEO.update({
    # 코어위브는 2026 부터 LongTermDebt* 대신 DebtInstrumentCarryingAmount(총액 35.6B) 하나로 신고,
    # 테라울프는 ConvertibleDebt(1.1B) — 둘 다 빠지면 '부채 0'이 된다(2026-10-24 probe).
    "debt_lt":  ["LongTermDebtNoncurrent", "LongTermNotesPayable", "LongTermDebt", "LongTermNotesAndLoans",
                 "ConvertibleDebtNoncurrent", "ConvertibleNotesPayable", "ConvertibleDebt", "DebtInstrumentCarryingAmount"],
    "debt_st":  ["LongTermDebtCurrent", "NotesPayableCurrent", "DebtCurrent", "ConvertibleDebtCurrent"],
    "fl_lt":    ["FinanceLeaseLiabilityNoncurrent"],
    "fl_st":    ["FinanceLeaseLiabilityCurrent"],
    "oplease":  ["OperatingLeaseLiability", "OperatingLeaseLiabilityNoncurrent"],   # 코어위브 16B — 부채엔 안 넣고 별도 표시
    "interest": ["InterestExpenseDebt", "InterestExpenseNonoperating", "InterestExpense"],
    "revenue":  ["RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues"],
    "issue":    ["ProceedsFromIssuanceOfLongTermDebt", "ProceedsFromIssuanceOfDebt", "ProceedsFromNotesPayable",
                 "ProceedsFromIssuanceOfSecuredDebt"],
})
INSTANT_NEO = INSTANT | {"fl_lt", "fl_st", "oplease"}
# 네오클라우드 딜·사실 시드 (매경ECONOMY 2026.10.21-27 커버스토리 + 홈피 뉴스 2026-10-17)
DEALS_NEO = [
    {"d": "2026-03", "co": "코어위브", "amt": 8.5,  "note": "GPU 인프라+장기 고객계약 담보 대출 — 무디스 A3(투자적격). GPU 가 담보자산이 된 첫 대형 사례"},
    {"d": "2026-06", "co": "코어사이언티픽", "amt": None, "note": "코어위브와 590MW 장기임대 계약 중 과금 개시 395MW(67%) — 나머지는 구축·시운전. '계약≠매출' 격차의 실측"},
    {"d": "2026-10", "co": "코어위브", "amt": 51.0, "note": "총부채 510억$ 초과(블록미디어 10/17) — 주간 -23%, AI 인프라 부채 우려의 진원"},
    {"d": "2026-10", "co": "엔비디아", "amt": None, "note": "보험사들과 네오클라우드 채무불이행 보험 상품 개발 협의 — 대출금 미상환 시 담보 GPU 처분 손실을 보험이 보전"},
]
NOTES_NEO = [
    "읽는 법: 빅테크는 순현금이라 '증분부채÷CAPEX 44%'가 경고였지만, 네오클라우드는 이 값이 100%를 넘는 게 정상이다 — 자기 현금이 없어 전액을 빚·리스로 짓는다. 여기서 봐야 할 건 ① 이자보상배율(LTM EBITDA÷이자)이 1 아래로 가는가 ② CAPEX÷매출이 줄기 시작하는가(투자 둔화) ③ 금융리스 비중.",
    "GPU 감가상각 5년·건물 20년(IREN 기준)이라 GPU 보유 사업자는 짧은 회수기간을 떠안는다. 임대료 하락·기술 진부화·전력 지연이 겹치면 이자비용 → 차환 리스크로 간다(매경ECONOMY 2026.10.21).",
    "데이터센터 보험 시장 106억$(2026) → 242억$(2030e, 스위스리) · AM베스트: 보험 업계가 감당해본 적 없는 보장 규모. 액침냉각 사고가 FM 15년 손해액의 24%.",
]

# ── ② 발행 딜 타임라인 시드 (Phase 3.8 이 최신 딜을 upsert)
DEALS_SEED = [
    {"d": "2025-09", "co": "오라클",   "amt": 18.0, "note": "AI 데이터센터 자금 — 이후 S&P 강등의 배경"},
    {"d": "2025-10", "co": "메타",     "amt": 30.0, "note": "비M&A 투자등급 회사채 사상 최대 단일 발행"},
    {"d": "2025-11", "co": "알파벳",   "amt": 17.5, "note": "달러·유로 이중 통화"},
    {"d": "2025-11", "co": "아마존",   "amt": 15.0, "note": "2021년 이후 첫 대형 복귀 발행"},
    {"d": "2026-03", "co": "아마존",   "amt": None, "note": "청약배수 3.2배 — 수요 강함"},
    {"d": "2026-06", "co": "알파벳",   "amt": 84.75, "note": "★ 주식 발행(채권 아님) — 상장기업 사상 최대 증자, 버크셔 100억$ 사모 포함"},
    {"d": "2026-07", "co": "아마존",   "amt": 25.0, "note": "청약배수 2.5배 — 3월 3.2배 대비 하락(수요 둔화 신호)"},
]
# ── ③ 신용 경고등 시드
RATINGS_SEED = [
    {"co": "마이크로소프트", "sp": "AAA",  "moody": "Aaa",          "flag": "ok",   "note": "최상위 — 여유 큼"},
    {"co": "알파벳",         "sp": "AA+",  "moody": "Aa2",          "flag": "ok",   "note": "증자로 등급 여력 선제 확보"},
    {"co": "아마존",         "sp": "AA",   "moody": "A1",           "flag": "ok",   "note": "발행 지속, 레버리지 낮음"},
    {"co": "메타",           "sp": "AA-",  "moody": "Aa3",          "flag": "ok",   "note": "300억$ 발행에도 순현금"},
    {"co": "오라클",         "sp": "BBB-", "moody": "Baa2 (부정적)", "flag": "warn",
     "note": "⚠ S&P 2026-07-09 BBB→BBB- 강등(투자등급 마지노선 1단계 위) — CAPEX 급증·FCF 마이너스·고객 집중(OpenAI). 무디스도 내리면 채권가격·CDS 압박"},
]
# 집계 참고치(FactSet 2026-07-23) — 자체 계산과 대조용
BENCH = {
    "src": "FactSet Insight 2026-07-23 'Hyperscalers Tap External Financing as AI Capex Outruns Cash Flow'",
    "url": "https://insight.factset.com/hyperscalers-tap-external-financing-as-ai-capex-outruns-cash-flow",
    "items": [
        {"k": "증분부채 ÷ CAPEX", "v": "FY24 9% → 2026-06 LTM 32%"},
        {"k": "5사 합산 총부채",   "v": "약 7,000억$"},
        {"k": "FY26 합산 CAPEX",  "v": "6,900억$ 초과 (YoY +80%)"},
        {"k": "오프밸런스 리스 약정", "v": "약 8,200억$ (오라클이 최대 노출)"},
    ],
}


def curl(u, timeout=25):
    try:
        r = subprocess.run(["curl", "-s", "--compressed", "--max-time", str(timeout),
                            "-H", "User-Agent: " + UA, u],
                           capture_output=True, text=True, timeout=timeout + 5)
        return r.stdout or ""
    except Exception:
        return ""


def concept(cik, tag):
    """EDGAR companyconcept → USD 관측 리스트. 실패 시 []"""
    j = curl("https://data.sec.gov/api/xbrl/companyconcept/CIK%s/us-gaap/%s.json" % (cik, tag))
    if not j.strip().startswith("{"):
        return []
    try:
        return json.loads(j).get("units", {}).get("USD", [])
    except Exception:
        return []


def pick_instant(obs, since):
    """잔액 태그 → {end: val} (같은 날짜는 최신 신고분 우선)"""
    out = {}
    for x in obs:
        e = x.get("end", "")
        if e < since or x.get("val") is None:
            continue
        # accn(접수번호)이 큰 쪽이 최신 신고 — 정정 반영
        p = out.get(e)
        if p is None or x.get("accn", "") >= p[1]:
            out[e] = (float(x["val"]), x.get("accn", ""))
    return {k: v[0] for k, v in out.items()}


def pick_quarter(obs, since):
    """기간 태그 → 분기값 {end: val}.

    ⚠ 10-Q 는 항목에 따라 '분기'가 아니라 '회계연도 누적(YTD)'으로 신고한다
    (메타·알파벳의 채권 발행액이 대표적 — 분기 태그가 아예 없다).
    그래서 ① 분기(80~100일) 관측을 먼저 취하고, ② 없는 분기는 같은 시작일을 공유하는
    누적 관측끼리 차분해 분기값을 복원한다. 이 처리를 빼면 발행액이 통째로 비어버린다.
    """
    D = lambda s: datetime.strptime(s, "%Y-%m-%d")
    per = {}
    for x in obs:
        s, e, v = x.get("start"), x.get("end", ""), x.get("val")
        if not s or e < since or v is None:
            continue
        try:
            days = (D(e) - D(s)).days
        except Exception:
            continue
        if days < 20 or days > 400:
            continue
        c = per.get(e)
        if c is None or days < c[0] or (days == c[0] and x.get("accn", "") >= c[2]):
            per[e] = (days, float(v), x.get("accn", ""), s)
    out = {e: abs(v) for e, (d, v, a, s) in per.items() if 80 <= d <= 100}
    for e in sorted(per):                       # ② 누적 차분으로 복원
        if e in out:
            continue
        d, v, a, s = per[e]
        if d < 150:
            continue
        prev = [(pe, pv, pd) for pe, (pd, pv, pa, ps) in per.items() if ps == s and pe < e]
        if not prev:
            continue
        pe, pv, pd = max(prev)
        if 80 <= (d - pd) <= 100:
            out[e] = abs(v - pv)
    return out


def series_for(cik, key, since, tags=None, instant=None):
    """태그 후보 중 '분기 관측이 가장 많은' 것을 채택.
    (첫 히트 방식은 오라클처럼 옛 태그가 먼저 잡히면 2점짜리를 쓰게 된다)"""
    tags = tags or TAGS; instant = instant or INSTANT
    inst = key in instant
    best, btag = {}, None
    for tag in tags[key]:
        obs = concept(cik, tag)
        time.sleep(0.12)                      # EDGAR 예의 (권고 10 req/s 이하)
        if not obs:
            continue
        d = pick_instant(obs, since) if inst else pick_quarter(obs, since)
        if not d:
            continue
        if inst:
            # (2026-10-24 개정) 잔액은 '날짜별 첫 히트' — 회사가 중간에 태그를 바꾸면(코어위브 LongTermDebt→
            # DebtInstrumentCarryingAmount) 종전 '태그 첫 히트 고정'은 최근 분기를 통째로 0 으로 만들었다.
            # 앞 순위 태그가 가진 날짜는 유지하고, 없는 날짜만 뒤 순위 태그로 채운다.
            added = 0
            for k, v in d.items():
                if k not in best:
                    best[k] = v; added += 1
            if added:
                btag = (btag or "") + ("+" if btag else "") + tag
            continue
        if len(d) > len(best):
            best, btag = d, tag
    return best, ([btag] if btag else [])


def ltm(d, end):
    """end 포함 직전 4개 분기 합. 4개 미만이면 None"""
    ks = sorted([k for k in d if k <= end])[-4:]
    return round(sum(d[k] for k in ks), 2) if len(ks) == 4 else None


def collect_neo(since="2022-01-01"):
    """네오클라우드 6사 — 총부채(+금융리스)·현금·CAPEX·매출·영업이익·D&A·이자 분기 시계열과 LTM 비율."""
    B = 1e9
    rows, allq = [], set()
    for sym, name, cik, fye in CO_NEO:
        raw = {}
        for key in TAGS_NEO:
            raw[key], tg = series_for(cik, key, since, TAGS_NEO, INSTANT_NEO)
            print(f"   [neo] {sym} {key}: {len(raw[key])}점 {tg}", flush=True)
        qs = sorted(set(raw["debt_lt"]) | set(raw["debt_st"]) | set(raw["fl_lt"]) | set(raw["cash"]))
        ser = []
        for q in qs:
            parts = [raw[k].get(q) for k in ("debt_lt", "debt_st", "fl_lt", "fl_st")]
            if all(v is None for v in parts) and raw["cash"].get(q) is None:
                continue
            debt = sum(v or 0 for v in parts)
            fl = (raw["fl_lt"].get(q) or 0) + (raw["fl_st"].get(q) or 0)
            cash = (raw["cash"].get(q) or 0) + (raw["sti"].get(q) or 0)
            e = {"d": q, "debt": round(debt / B, 2), "flease": round(fl / B, 2),
                 "cash": round(cash / B, 2), "net": round((debt - cash) / B, 2)}
            if raw["oplease"].get(q) is not None:
                e["oplease"] = round(raw["oplease"][q] / B, 2)
            for k in ("issue", "capex", "revenue", "opinc", "interest"):
                v = raw[k].get(q)
                if v is not None:
                    e[k] = round(v / B, 3)
            lc, lr = ltm(raw["capex"], q), ltm(raw["revenue"], q)
            lo, ld, li = ltm(raw["opinc"], q), ltm(raw["da"], q), ltm(raw["interest"], q)
            if lc is not None:
                e["capex_ltm"] = round(lc / B, 2)
                prev = [k for k in qs if k <= q][-5:]
                if len(prev) == 5:
                    p0 = prev[0]
                    d0 = sum((raw[k].get(p0) or 0) for k in ("debt_lt", "debt_st", "fl_lt", "fl_st"))
                    if d0 and lc:
                        e["dd_capex"] = round((debt - d0) / lc * 100, 1)
            if lr:
                e["rev_ltm"] = round(lr / B, 2)
                if lc is not None:
                    e["capex_rev"] = round(lc / lr * 100, 0)
            if lo is not None and ld is not None:
                ebitda = lo + ld
                e["ebitda_ltm"] = round(ebitda / B, 2)
                if ebitda > 0:
                    e["nd_ebitda"] = round((debt - cash) / ebitda, 2)
                if li:
                    e["int_ltm"] = round(li / B, 3)
                    e["int_cov"] = round(ebitda / li, 2)        # 음수면 EBITDA 적자
            ser.append(e); allq.add(q)
        rows.append({"sym": sym, "name": name, "fye": fye, "series": ser})
        print(f"  ✅ [neo] {sym} {len(ser)}분기 (최신 {ser[-1]['d'] if ser else '-'})", flush=True)
    # 합산 — 달력 분기말 축, 각 사 직전 관측 이월, 관측 수 n 표기(6사 미만 분기는 근사)
    agg = []
    for q in sorted(allq):
        if q[5:7] not in ("03", "06", "09", "12"):
            continue
        pts = []
        for r in rows:
            c = [x for x in r["series"] if x["d"] <= q and x["d"] >= f"{int(q[:4])-1}-{q[5:7]}-01"]
            if c:
                pts.append(c[-1])
        if len(pts) < 4:
            continue
        a = {"d": q, "n": len(pts), "debt": round(sum(p["debt"] for p in pts), 1),
             "flease": round(sum(p["flease"] for p in pts), 1), "net": round(sum(p["net"] for p in pts), 1)}
        for k in ("capex_ltm", "rev_ltm", "ebitda_ltm", "int_ltm"):
            v = [p.get(k) for p in pts if p.get(k) is not None]
            if v:
                a[k] = round(sum(v), 2)
        if a.get("ebitda_ltm") is not None and a.get("int_ltm"):
            a["int_cov"] = round(a["ebitda_ltm"] / a["int_ltm"], 2)
        if a.get("capex_ltm") and a.get("rev_ltm"):
            a["capex_rev"] = round(a["capex_ltm"] / a["rev_ltm"] * 100, 0)
        agg.append(a)
    for i, a in enumerate(agg):
        if i >= 4 and a.get("capex_ltm"):
            a["dd_capex"] = round((a["debt"] - agg[i - 4]["debt"]) / a["capex_ltm"] * 100, 1)
    return {"rows": rows, "agg": agg, "deals": DEALS_NEO, "notes": NOTES_NEO,
            "src": "매경ECONOMY 2026.10.21-27 커버스토리 'AIDC NO WAY OUT' · SEC EDGAR XBRL"}


def main():
    print("[debt] 생성 시작", flush=True)
    since = "2019-01-01"
    B = 1e9
    rows, allq = [], set()
    for sym, name, cik, fye in CO:
        raw = {}
        for key in TAGS:
            raw[key], tg = series_for(cik, key, since)
            print(f"   {sym} {key}: {len(raw[key])}점 {tg}", flush=True)
        # 분기 축 = 잔액(총부채) 관측일
        qs = sorted(set(raw["debt_lt"]) | set(raw["debt_st"]))
        ser = []
        for q in qs:
            dl = raw["debt_lt"].get(q)
            ds = raw["debt_st"].get(q)
            if dl is None and ds is None:
                continue
            debt = (dl or 0) + (ds or 0)
            cash = (raw["cash"].get(q) or 0) + (raw["sti"].get(q) or 0)
            e = {"d": q, "debt": round(debt / B, 1), "cash": round(cash / B, 1),
                 "net": round((debt - cash) / B, 1)}
            for k, lbl in (("issue", "issue"), ("repay", "repay"), ("capex", "capex")):
                v = raw[k].get(q)
                if v is not None:
                    e[lbl] = round(v / B, 1)
            # LTM 지표
            lc = ltm(raw["capex"], q)
            li = ltm(raw["issue"], q)
            lo = ltm(raw["opinc"], q)
            ld = ltm(raw["da"], q)
            if lc:
                e["capex_ltm"] = round(lc / B, 1)
                # 증분부채(YoY) ÷ LTM CAPEX — 핵심 신호
                prev = [k for k in qs if k <= q][-5:]
                if len(prev) == 5:
                    p0 = prev[0]
                    d0 = (raw["debt_lt"].get(p0) or 0) + (raw["debt_st"].get(p0) or 0)
                    if d0:
                        e["dd_capex"] = round((debt - d0) / lc * 100, 1)
            if li:
                e["issue_ltm"] = round(li / B, 1)
            if lo is not None and ld is not None and (lo + ld) > 0:
                e["nd_ebitda"] = round((debt - cash) / (lo + ld), 2)
            ser.append(e)
            allq.add(q)
        ser = [s for s in ser if s["d"] >= "2020-01-01"]
        rows.append({"sym": sym, "name": name, "fye": fye, "series": ser})
        print(f"  ✅ {sym} {len(ser)}분기 (최신 {ser[-1]['d'] if ser else '-'})", flush=True)

    # 합산 시계열 — 5사 모두 관측이 있는 분기만(결산월이 달라 근사치임을 명시)
    agg = []
    for q in sorted(allq):
        # 달력 분기말만 축으로 쓴다 — 오라클(5·8·11·2월 결산)의 어긋난 시점이 섞이면
        # 합산 시계열이 톱니처럼 흔들린다. 오라클 값은 직전 관측이 이월된다(캡션에 명시).
        if q < "2020-01-01" or q[5:7] not in ("03", "06", "09", "12"):
            continue
        pts = []
        for r in rows:
            # 각 사의 q 이전 최근 관측(결산월 차이 보정)
            c = [s for s in r["series"] if s["d"] <= q]
            if c:
                pts.append(c[-1])
        if len(pts) < len(rows):
            continue
        a = {"d": q,
             "debt": round(sum(p["debt"] for p in pts), 1),
             "net":  round(sum(p["net"] for p in pts), 1)}
        cl = [p.get("capex_ltm") for p in pts]
        il = [p.get("issue_ltm") for p in pts]
        if all(v is not None for v in cl):
            a["capex_ltm"] = round(sum(cl), 1)
        if all(v is not None for v in il):
            a["issue_ltm"] = round(sum(il), 1)
        agg.append(a)
    # 합산 증분부채/CAPEX (YoY)
    for i, a in enumerate(agg):
        if i >= 4 and a.get("capex_ltm"):
            a["dd_capex"] = round((a["debt"] - agg[i - 4]["debt"]) / a["capex_ltm"] * 100, 1)

    # ── FRED 조달비용 환경
    oas = {}
    if fred_series:
        for k, sid in (("ig", "BAMLC0A0CM"), ("hy", "BAMLH0A0HYM2")):
            try:
                s = fred_series(sid, start="2020-01-01", freq="m")
                oas[k] = [[d, v] for d, v in s][-84:]
                print(f"   FRED {sid}: {len(oas[k])}개월", flush=True)
            except Exception as e:
                print(f"   FRED {sid} 실패: {e}", flush=True)

    # ── LLM 갱신(Phase 3.8) upsert
    llm = {}
    try:
        llm = json.loads((DB / "debt_llm.json").read_text(encoding="utf-8"))
    except Exception:
        pass
    deals = list(DEALS_SEED)
    for d in llm.get("deals", []):
        deals = [x for x in deals if not (x["d"] == d.get("d") and x["co"] == d.get("co"))]
        d["llm"] = True
        deals.append(d)
    deals.sort(key=lambda x: x["d"])
    ratings = {r["co"]: r for r in RATINGS_SEED}
    for r in llm.get("ratings", []):
        if r.get("co"):
            r["llm"] = True
            ratings[r["co"]] = r

    # ── (2026-10-24) 네오클라우드 그룹 — 실패해도 빅테크 블록은 그대로 저장(비차단)
    try:
        neo = collect_neo()
    except Exception as e:
        print(f"   [neo] 실패: {e}", flush=True); neo = None

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "as_of": datetime.now(KST).strftime("%Y-%m-%d %H:%M"),
        "unit": "십억 달러(USD bn)",
        "rows": rows, "agg": agg, "oas": oas,
        "deals": deals, "ratings": [ratings[k["co"]] for k in RATINGS_SEED],
        "bench": BENCH, "llm_asof": llm.get("as_of"),
        "neo": neo,
    }, ensure_ascii=False), encoding="utf-8")
    last = agg[-1] if agg else {}
    print(f"[debt] ✅ 5사 · 합산 {len(agg)}분기 · 최신 {last.get('d')} "
          f"총부채 {last.get('debt')}B · 증분부채/CAPEX {last.get('dd_capex')}% → {OUT}", flush=True)


if __name__ == "__main__":
    main()
