#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fetch_alloc.py — 💼 자산배분(포트폴리오 제안) 정본 생성 (2026-10-18 신설 · 사용자 요청)

"홈페이지의 모든 내용을 고려해, 한국 투자자 기준 10억(변경 가능)을 지금 글로벌 상황에서 어떻게 나눌 것인가"를
**규칙 기반**으로 매일 산출한다. LLM 추정 없음 — 입력은 전부 이 서버가 이미 수집·판정 중인 DB 다.

입력(전부 기존 정본 재사용 · 어느 하나 없어도 나머지로 동작):
  bonds.json        금리 고점 통과 4신호(n_ok)·긴축 성격(성장형/인플레형)·장단기차·HY 스프레드·美10Y
  goldlead.json     금 6축 종합 점수(overall.score −1~+1)
  cryptolead.json   코인 종합 점수(overall.score)
  series_semi_status.json  반도체 사이클 3신호(0안전/1주의/2경보)
  share.json(bneck) AI 병목 릴레이 8축 '오름/꺾임' 개수
  global_market.json KOSPI·S&P 1M/3M 수익률, VIX·VKOSPI, 섹터 ETF
  re3.json          부동산 국면·12개월 예측(비율만 제시, 실행 종목 없음)
  screener_pool.json 퀄리티배당(김학균 체크) KR/US 후보 + 테마 바스켓 종목의 현재 지표
  health.json       서버 경보(데이터 결함 시 '신뢰도 낮음' 표기)

산출 알고리즘(투명성이 목적 — 각 조정은 '근거' 문장과 함께 저장):
  ① 기본 비중(중립, 한국 거주 투자자 금융자산): KR주식 25 · US주식 25 · 채권 25(단기 15·장기 10) · 금 10 · 현금 10 · 코인 5
  ② 신호별 가감(±p, 합산 후 0~상한 클램프, 100 정규화). 가감 폭은 작게(±2~5p) — 신호 하나로 뒤집지 않는다.
  ③ 주식 내부 바스켓: 퀄리티배당(상위 5) · 선거 무관 공통축(전력·방산·원전·조선) · AI 인프라(반도체 경보면 축소) · 미국 퀄리티배당 · 미국 AI 벨웨더
  ④ 부동산: 금융자산 10억과 별도로 '순자산 중 부동산 비율' 권고 범위만(re3 국면 기반) — 실행 종목 없음.
  ⑤ 이력 alloc_hist.json 에 매일 1행 append → 화면에서 비중 변화 추적.

⚠ 리서치용. 투자 권유 아님 — 화면에 명시. 세금·환율 헤지·개인 사정(소득·부채·연령) 미반영.
산출: data/db/alloc.json · data/db/alloc_hist.json
cron: 55 7 * * *  (bonds 07:40·goldlead 07:05·cryptolead 06:55·share 06:35 뒤)
"""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DB = BASE / "data" / "db"
OUT = DB / "alloc.json"
HIST = DB / "alloc_hist.json"
KST = timezone(timedelta(hours=9))


def load(n):
    try:
        return json.loads((DB / n).read_text(encoding="utf-8"))
    except Exception:
        return None


# ── 기본 비중 ───────────────────────────────────────────────────────────────
BASE_W = {"kr_eq": 25, "us_eq": 25, "bond_s": 15, "bond_l": 10, "gold": 10, "cash": 10, "crypto": 5}
CAP = {"kr_eq": (10, 40), "us_eq": (10, 40), "bond_s": (5, 40), "bond_l": (0, 30), "gold": (3, 20), "cash": (5, 30), "crypto": (0, 10)}
LABEL = {"kr_eq": "한국 주식", "us_eq": "미국 주식", "bond_s": "단기채·현금성(MMF·CD·단기채)", "bond_l": "장기채(국고 10~30년)",
         "gold": "금(KRX 금현물·금 ETF)", "cash": "현금(예비·분할매수 대기)", "crypto": "코인(BTC 중심)"}
VEHICLE = {"kr_eq": "KODEX 200·직접 종목(아래 바스켓)", "us_eq": "TIGER 미국S&P500·직접 종목(아래 바스켓)",
           "bond_s": "KODEX KOFR금리액티브 · KODEX 단기채권 · TIGER CD금리", "bond_l": "KODEX 국고채10년액티브 · KODEX 국고채30년액티브 · TIGER 미국채10년선물",
           "gold": "KRX 금현물(세제 유리) · ACE KRX금현물", "cash": "CMA·파킹통장", "crypto": "BTC 현물(업비트) · 알트는 제외"}

# 테마 바스켓(선거 결과 무관 공통축 — 점유율 추이·해자워치·K-수출 탭 근거) · 코드로 풀에서 현재 지표를 붙인다
THEMES_KR = {
    "전력 인프라": [("267260", "HD현대일렉트릭"), ("298040", "효성중공업"), ("010120", "LS일렉트릭")],
    "방산": [("012450", "한화에어로스페이스"), ("079550", "LIG넥스원"), ("064350", "현대로템")],
    "원전·조선": [("034020", "두산에너빌리티"), ("009540", "HD한국조선해양"), ("042660", "한화오션")],
    "AI 반도체": [("000660", "SK하이닉스"), ("005930", "삼성전자"), ("042700", "한미반도체")],
}
THEMES_US = {
    "AI 인프라": [("NVDA", "엔비디아"), ("AVGO", "브로드컴"), ("VRT", "버티브"), ("MU", "마이크론")],
    "전력·원전": [("GEV", "GE버노바"), ("CEG", "컨스텔레이션"), ("ETN", "이튼")],
    "국방": [("LMT", "록히드마틴"), ("RTX", "RTX"), ("NOC", "노스롭")],
}


def main():
    now = datetime.now(KST)
    W = dict(BASE_W)
    why = {k: [] for k in W}          # 자산군별 근거
    sig = []                           # 신호 대시보드 행
    conf = "정상"

    def adj(k, p, reason):
        W[k] += p
        why[k].append(f"{'+' if p > 0 else ''}{p}p · {reason}")

    # ── 1) 채권: 금리 고점 통과 체크리스트 (bonds) ──
    b = load("bonds.json") or {}
    al = b.get("alloc") or {}
    n_ok = al.get("n_ok")
    chk = b.get("checklist") or []
    reg = ((b.get("regime") or {}).get("decomp") or {})
    kind = (reg.get("m3") or {}).get("kind")
    us10 = (reg.get("cur") or {}).get("us10")
    aux = b.get("aux") or {}
    hy = (aux.get("hy") or {}).get("cur") if isinstance(aux.get("hy"), dict) else None
    curve = (aux.get("curve") or {}).get("cur") if isinstance(aux.get("curve"), dict) else None
    if n_ok is not None:
        sig.append({"k": "금리 고점 4신호", "v": f"{n_ok}/4 충족", "src": "채권 탭",
                    "detail": " · ".join(f"{'✓' if c.get('ok') else '✗'} {c.get('name')} ({c.get('value')})" for c in chk)})
        if n_ok >= 3:
            adj("bond_l", +8, f"금리 고점 통과 신호 {n_ok}/4 — 장기채 비중 확대(윤여삼 프레임)"); adj("bond_s", -5, "단기채→장기채 전환")
        elif n_ok <= 1:
            adj("bond_l", -5, f"고점 신호 {n_ok}/4 뿐 — 장기채 아직 이르다, 단기채 유지"); adj("bond_s", +3, "단기채로 유동성 확보")
        else:
            why["bond_l"].append(f"±0 · 고점 신호 {n_ok}/4 혼조 — 장기채 소량 유지")
    if us10 is not None:
        sig.append({"k": "美 10년물", "v": f"{us10:.2f}%", "src": "채권 탭", "detail": f"긴축 성격: {kind or '—'} (실질금리 주도=성장형은 주식에 덜 해롭다)"})
        if us10 >= 5.0:
            adj("bond_s", +3, f"美10Y {us10:.1f}% — 단기 캐리만으로 5%대, 현금성 매력 ↑"); adj("us_eq", -3, "장기금리 5%대는 성장주 멀티플 압박")
    if kind == "인플레형":
        adj("gold", +3, "인플레형 긴축(BEI 주도) — 금 헤지"); adj("bond_l", -3, "인플레형은 장기채에 불리")
    if hy is not None:
        sig.append({"k": "HY 스프레드", "v": f"{hy:.2f}%p", "src": "채권 탭", "detail": "4%p 이상이면 신용 경계, 3%p 미만이면 과열"})
        if hy >= 4.5:
            adj("cash", +4, f"HY 스프레드 {hy:.1f}%p — 신용 경계, 현금 확대"); adj("kr_eq", -2, "신용 경계 국면"); adj("us_eq", -2, "신용 경계 국면")
    if curve is not None:
        sig.append({"k": "美 장단기차(10Y-2Y)", "v": f"{curve:+.2f}%p", "src": "채권 탭", "detail": "역전(−)이면 경기 둔화 선행"})

    # ── 2) 글로벌 시장 (global_market): 국면·변동성 ──
    gm = load("global_market.json") or {}
    rows = {}
    for g in gm.get("groups") or []:
        for r in g.get("rows") or []:
            rows[r.get("s")] = r
    def ret(s, k):
        return ((rows.get(s) or {}).get("ret") or {}).get(k)
    kospi_m1, kospi_m3, kospi_y1 = ret("^KS11", "m1"), ret("^KS11", "m3"), ret("^KS11", "y1")
    spx_m1, spx_m3 = ret("^GSPC", "m1"), ret("^GSPC", "m3")
    vix = (rows.get("^VIX") or {}).get("px"); vk = (rows.get("DV.VKOSPI") or {}).get("px")
    if kospi_m1 is not None:
        sig.append({"k": "KOSPI 1M / 3M / 1Y", "v": f"{kospi_m1:+.1f}% / {kospi_m3:+.1f}% / {kospi_y1:+.1f}%", "src": "글로벌시황 탭",
                    "detail": "1M −10% 이하 급락은 '분할매수 구간', 1Y +50% 이상은 '과열 후 조정' 양면"})
        if kospi_m1 <= -10:
            adj("kr_eq", +3, f"KOSPI 1개월 {kospi_m1:+.1f}% 급락 — 분할매수 구간(한 번에 넣지 않는다)"); adj("cash", -2, "현금 일부를 분할매수 재원으로")
        elif kospi_m1 >= 10:
            adj("kr_eq", -3, f"KOSPI 1개월 {kospi_m1:+.1f}% 급등 — 추격 자제")
    if spx_m1 is not None:
        sig.append({"k": "S&P500 1M / 3M", "v": f"{spx_m1:+.1f}% / {spx_m3:+.1f}%", "src": "글로벌시황 탭", "detail": ""})
    if vix is not None:
        sig.append({"k": "VIX / VKOSPI", "v": f"{vix:.1f} / {vk:.1f}" if vk else f"{vix:.1f}", "src": "글로벌시황 탭",
                    "detail": "VIX 30↑ 공포(역발상 매수 후보), 15↓ 안도(헤지 저렴)"})
        if vix >= 30:
            adj("us_eq", +3, f"VIX {vix:.0f} 공포 구간 — 역발상 분할매수"); adj("kr_eq", +2, "공포 구간 분할매수")
        elif vix <= 14:
            adj("cash", +2, f"VIX {vix:.0f} 안도 구간 — 헤지·현금 소폭 확대")
    if vk is not None and vk >= 40:
        adj("kr_eq", -2, f"VKOSPI {vk:.0f} — 변동성 극단, 포지션 크기 축소(분할)")

    # ── 3) 반도체 사이클 · AI 병목 ──
    ss = load("series_semi_status.json") or {}
    semi = (ss.get("data") or [[None, {}]])[-1][1] if ss.get("data") else {}
    semi_alert = sum(1 for v in semi.values() if v == 2)
    ai_cut = False
    if semi:
        lab = {0: "안전", 1: "주의", 2: "경보"}
        sig.append({"k": "반도체 사이클 3신호", "v": " · ".join(f"{k} {lab.get(v, v)}" for k, v in semi.items()), "src": "3.1.9 HBM 탭",
                    "detail": "재고주수·DRAM 계약가 QoQ·CAPEX YoY — 경보 2개 이상이면 반도체 비중 축소"})
        if semi_alert >= 2:
            adj("kr_eq", -3, f"반도체 경보 {semi_alert}/3 — KR 지수의 반도체 비중(40%↑) 고려 축소"); ai_cut = True
        elif semi_alert == 1:
            why["kr_eq"].append("±0 · 반도체 경보 1/3 — AI 반도체 바스켓만 축소"); ai_cut = True
    sh = load("share.json") or {}
    bn = next((x for x in sh.get("battles") or [] if x.get("id") == "bneck"), None)
    if bn and bn.get("series"):
        note = bn["series"][-1].get("note") or ""
        import re
        m = re.search(r"▲오름 (\d+) / ▼꺾임 (\d+)", note)
        if m:
            up, dn = int(m.group(1)), int(m.group(2))
            sig.append({"k": "AI 병목 릴레이 8축", "v": f"▲오름 {up} / ▼꺾임 {dn}", "src": "점유율 추이 탭", "detail": note[:140]})
            if dn >= 5:
                adj("us_eq", -3, f"AI 병목 8축 중 꺾임 {dn} — AI 인프라 과열 식는 중"); ai_cut = True
            elif up >= 6:
                adj("us_eq", +2, f"AI 병목 8축 중 오름 {up} — 사이클 확장 지속")

    # ── 4) 금 · 코인 ──
    gl = load("goldlead.json") or {}
    gs = (gl.get("overall") or {}).get("score")
    if gs is not None:
        sig.append({"k": "금 선행 6축", "v": f"{gs:+.2f} · {(gl.get('overall') or {}).get('text', '')[:60]}", "src": "금 선행 탭", "detail": "−1~+1 · +0.3↑ 우호 / −0.3↓ 비우호"})
        if gs >= 0.3: adj("gold", +3, f"금 선행 종합 {gs:+.2f} 우호")
        elif gs <= -0.3: adj("gold", -3, f"금 선행 종합 {gs:+.2f} 비우호")
        else: why["gold"].append(f"±0 · 금 선행 종합 {gs:+.2f} 혼조 — 기본 10% 유지(원화 약세 헤지 겸)")
    cl = load("cryptolead.json") or {}
    cs = (cl.get("overall") or {}).get("score")
    fng = ((cl.get("ind") or {}).get("fng") or {}).get("v")
    if cs is not None:
        sig.append({"k": "코인 선행 종합", "v": f"{cs:+.2f} · F&G {fng if fng is not None else '—'}", "src": "코인 선행 탭", "detail": (cl.get("overall") or {}).get("text", "")[:100]})
        if cs >= 0.3: adj("crypto", +2, f"코인 선행 {cs:+.2f} 우호")
        elif cs <= -0.3: adj("crypto", -3, f"코인 선행 {cs:+.2f} 비우호")
        if fng is not None and fng <= 20: adj("crypto", +2, f"공포탐욕 {fng} 극단 공포 — 역발상 소량")
        elif fng is not None and fng >= 80: adj("crypto", -2, f"공포탐욕 {fng} 극단 탐욕")

    # ── 5) 서버 건강 ──
    h = load("health.json") or {}
    if h and not h.get("ok"):
        conf = "낮음 — 서버 경보: " + "; ".join(h.get("alerts") or [])[:120]

    # ── 클램프·정규화 ──
    for k, (lo, hi) in CAP.items():
        W[k] = max(lo, min(hi, W[k]))
    tot = sum(W.values())
    W = {k: round(v / tot * 100, 1) for k, v in W.items()}
    # 반올림 오차는 현금에
    W["cash"] = round(W["cash"] + (100 - sum(W.values())), 1)

    # ── 부동산: 비율만 (re3) ──
    re3 = load("re3.json") or {}
    p12 = (re3.get("pred12") or {})
    cur = (re3.get("cur") or {})
    def _g(r): return (p12.get(r) or {}).get("g")
    re_rows = [{"r": r, "g": _g(r), "verdict": (cur.get(r) or {}).get("verdict")} for r in ("전국", "서울", "경기", "부산", "대구", "인천") if r in p12]
    nat, seoul = _g("전국"), _g("서울")
    if seoul is not None and seoul >= 5: re_band = "순자산의 40~50% (서울·수도권 보유 유지, 신규는 분양·급매 선별)"
    elif nat is not None and nat <= 0: re_band = "순자산의 30% 이하 (보유분 축소·현금화 검토)"
    else: re_band = "순자산의 30~40% (현 보유 유지, 추가 매입 보류)"
    realestate = {"band": re_band, "rows": re_rows, "note": "RE3 국면·12개월 예측(참고치) 기반 비율 권고 — 금융자산 배분(위 100%)과 별도. 실행 종목 없음."}

    # ── 주식 바스켓 ──
    pool = load("screener_pool.json") or {}
    kr = {r["c"]: r for r in pool.get("kr") or []}; us = {r["c"]: r for r in pool.get("us") or []}
    # 배당 이력은 풀이 아니라 별도 DB(app.js mergeSec 와 동일 병합): KR dps_hist(inc=DPS 연속증가) · US div_hist_us(dgy=배당성장연수)
    for c, v in ((load("dps_hist.json") or {}).get("d") or {}).items():
        if c in kr: kr[c]["dinc"] = v.get("inc")
    for c, v in ((load("div_hist_us.json") or {}).get("d") or {}).items():
        if c in us: us[c]["dgy"] = v.get("dgy"); us[c]["mdd5"] = v.get("mdd5")
    def pick(r, isus=False):
        if not r: return None
        return {"c": r["c"], "n": r.get("n"), "px": r.get("px"), "cap": r.get("cap"), "divy": r.get("divy"), "icr": r.get("icr"),
                "ocfop": r.get("ocfop"), "de": r.get("de"), "mom": r.get("mom"), "upside": r.get("upside"), "r1m": r.get("r1m"),
                "payout": (r.get("payout") * 100 if (isus and r.get("payout") is not None) else r.get("payout") * 100 if r.get("payout") is not None else None)}
    def qdiv_kr():
        c = [r for r in kr.values() if (r.get("dinc") or 0) >= 2 and r.get("payout") is not None and r["payout"] <= 0.7 and (r.get("divy") or 0) >= 3
             and (r.get("ocfop") or 0) >= 0.5 and (r.get("icr") or 0) >= 1 and (r.get("de") or 9e9) <= 200 and (r.get("cap") or 0) >= 3e11 and not r.get("isfin")]
        c.sort(key=lambda r: -(r.get("divy") or 0)); return [pick(r) for r in c[:5]]
    def qdiv_us():
        c = [r for r in us.values() if (r.get("dgy") or 0) >= 5 and r.get("payout") is not None and r["payout"] <= 0.7 and (r.get("divy") or 0) >= 3
             and (r.get("ocfop") or 0) >= 0.5 and (r.get("icr") or 0) >= 1 and (r.get("de") or 9e9) <= 200 and (r.get("cap") or 0) >= 2e9 and not r.get("isfin")]
        c.sort(key=lambda r: -(r.get("divy") or 0)); return [pick(r, True) for r in c[:5]]
    def theme(tm, src, isus):
        out = {}
        for name, lst in tm.items():
            out[name] = [pick(src.get(c), isus) or {"c": c, "n": n} for c, n in lst]
        return out
    # 주식 슬리브 내부 비중(합 100) — AI 축소 플래그 반영
    kr_in = {"퀄리티 배당(김학균 체크)": 40, "전력 인프라": 20, "방산": 15, "원전·조선": 15, "AI 반도체": 10}
    us_in = {"미국 퀄리티 배당": 40, "AI 인프라": 30, "전력·원전": 15, "국방": 15}
    if ai_cut:
        kr_in["AI 반도체"] = 5; kr_in["퀄리티 배당(김학균 체크)"] = 45
        us_in["AI 인프라"] = 20; us_in["미국 퀄리티 배당"] = 50
    baskets = {
        "kr": {"weights": kr_in, "lists": {"퀄리티 배당(김학균 체크)": qdiv_kr(), **theme(THEMES_KR, kr, False)}},
        "us": {"weights": us_in, "lists": {"미국 퀄리티 배당": qdiv_us(), **theme(THEMES_US, us, True)}},
        "note": ("바스켓 안에서는 동일가중 · 한 종목 상한 = 총자산 3% · 급락 국면(KOSPI 1M −10% 이하)은 3회 분할. "
                 "퀄리티 배당 = 배당 지속·성향≤70·수익률≥3·영업현금/영업이익≥0.5·ICR≥1·부채≤200(한경MONEY 김학균). "
                 + ("AI 반도체·AI 인프라는 반도체 경보/병목 꺾임으로 **축소** 상태." if ai_cut else "")),
    }

    # ── 한 줄 요약 ──
    top = sorted(W.items(), key=lambda kv: -kv[1])
    regime_txt = []
    if n_ok is not None: regime_txt.append(f"금리 고점 신호 {n_ok}/4")
    if kind: regime_txt.append(f"{kind} 긴축")
    if kospi_m1 is not None: regime_txt.append(f"KOSPI 1M {kospi_m1:+.0f}%")
    if vix is not None: regime_txt.append(f"VIX {vix:.0f}")
    if semi_alert: regime_txt.append(f"반도체 경보 {semi_alert}/3")
    summary = (f"{' · '.join(regime_txt)} → " + " / ".join(f"{LABEL[k].split('(')[0]} {v:.0f}%" for k, v in top[:4]))

    # ── 이력 ──
    hist = load("alloc_hist.json") or []
    today = now.strftime("%Y-%m-%d")
    hist = [x for x in hist if x.get("d") != today] + [{"d": today, "w": W, "s": summary}]
    hist = hist[-400:]
    HIST.write_text(json.dumps(hist, ensure_ascii=False), encoding="utf-8")
    prev = next((x for x in reversed(hist[:-1]) if x.get("d") <= (now - timedelta(days=7)).strftime("%Y-%m-%d")), (hist[-2] if len(hist) > 1 else None))
    diff = {k: round(W[k] - (prev["w"].get(k, W[k]) if prev else W[k]), 1) for k in W}

    OUT.write_text(json.dumps({
        "as_of": now.strftime("%Y-%m-%d %H:%M"), "confidence": conf, "summary": summary,
        "weights": W, "base": BASE_W, "label": LABEL, "vehicle": VEHICLE, "why": why, "signals": sig,
        "diff7": diff, "prev_d": prev["d"] if prev else None,
        "baskets": baskets, "realestate": realestate,
        "disclaimer": "서버 수집 신호를 고정 규칙으로 합산한 리서치 결과 — 투자 권유 아님. 세금·환헤지·개인 사정 미반영. 변경은 분할로.",
    }, ensure_ascii=False), encoding="utf-8")
    print(f"[alloc] ✅ {summary} → {OUT}", flush=True)


if __name__ == "__main__":
    main()
