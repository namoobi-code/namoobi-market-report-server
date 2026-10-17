#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fetch_bonds.py — 📜 채권 탭 데이터 (2026-10-17 신설)

한경MONEY 2026.10 메리츠 윤여삼 '고점 확신 전까진 단기채' 인터뷰를 운영 가능한 형태로:
  ① 금리 고점 통과 4신호 체크리스트 — 전부 기존 서버 DB 재사용(신규 수집 0)
       유가 WTI<75 · 美 고용·소비 질서 있는 둔화 · 美10년 4.5% 안팎 완만 하락 · 국내 장기금리 신고점 미경신
       + 보조: 장단기차(10Y-2Y) 플래트닝 · HY 가산금리 · 美-韓 10년 스프레드
  ② 금리 현황 — 기준금리(policy_rates)·10년물 10개국(gbonds)·1년 추이
  ③ 채권 ETF 추세표 — KR 상장 8종 + US 8종 (야후 1년 일봉, 기간수익률·스파크)
  ④ 배분 가이드 — 기사 프레임(현금10/단기50/장기20/우량회사채20 → 고점 확인 후 장기채 50)에 체크리스트 충족 수를 대입
  ⑤ (2026-10-17 매경ECONOMY '5% 금리 시대') 긴축 성격 패널 regime() — 실질/기대인플레 분해 · 명목성장률−10Y · 인상 사이클 종료(FF선물·마지막 인상 경과)

판정 기준은 기사 수치 그대로. 투자권유 아님 — 기사 프레임의 '현재 위치' 표시용.
cron: 40 7 * * *   (gbonds·employment·global_market 갱신 뒤)
"""
import json, sys, time, urllib.parse as _up
from datetime import datetime, timedelta, timezone, date
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DB = BASE / "data" / "db"
OUT = DB / "bonds.json"
KST = timezone(timedelta(hours=9))
sys.path.insert(0, str(BASE / "scripts"))

def jload(p, default=None):
    try: return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception: return default if default is not None else {}
def log(m): print(m, flush=True)
def pct(v, d=1): return None if v is None else round(v, d)

# (2026-10-17 사용자 지적 "왜 초단기 ETF 는 없나") 기사의 '현금성 10%' = 파킹형(KOFR·CD금리). 야후 가격이 누적형 금리를 제대로 반영하는
# 종목만 채택(실측: TIGER CD금리 1y +2.78%·TIGER KOFR +2.02% 정상 / KODEX KOFR·CD 는 +0.0x% 로 야후 데이터 결함 → 제외).
# 미국 SGOV·BIL 은 월 분배형이라 가격이 평평 — 수익은 분배금(연 4%대). 화면 주석으로 안내.
ETFS_KR = [  # (2026-10-17 사용자 지적 "국고채 1년은 왜 뺐냐") 만기 사다리 순 — 파킹 → 1년 이내 → 3년 → 10년 → 30년 → 회사채 → 미국채(KR상장)
           ("423160.KS", "KODEX KOFR금리액티브", "초단기·파킹(KOFR 하루)"), ("357870.KS", "TIGER CD금리투자KIS", "초단기·파킹(CD 91일)"),
           ("153130.KS", "KODEX 단기채권", "단기 1년 이내(국공채·은행채)"), ("157450.KS", "TIGER 단기통안채", "단기 1년 이내(통안채)"),
           ("114260.KS", "KODEX 국고채3년", "국고채 3년"), ("471230.KS", "KODEX 국고채10년액티브", "국고채 10년"),
           ("439870.KS", "KODEX 국고채30년액티브", "국고채 30년"), ("385560.KS", "RISE KIS국고채30년Enhanced", "국고채 30년(강화)"),
           ("273130.KS", "KODEX 종합채권(AA-이상)액티브", "우량 회사채 혼합"), ("305080.KS", "TIGER 미국채10년선물", "미국 10년(KR상장)"),
           ("453850.KS", "ACE 미국30년국채액티브(H)", "미국 30년(KR상장·환헤지)"), ("304660.KS", "KODEX 미국채울트라30년선물(H)", "미국 초장기(KR상장·환헤지)")]
ETFS_US = [("SGOV", "iShares 0-3M T-Bill", "초단기·파킹(월분배)"), ("BIL", "SPDR 1-3M T-Bill", "초단기·파킹(월분배)"), ("SHV", "iShares 0-1Y Treasury", "단기 1년 이내"), ("SHY", "iShares 1-3Y Treasury", "단기 1-3년"), ("IEF", "iShares 7-10Y Treasury", "미국 중기"),
           ("TLT", "iShares 20+Y Treasury", "미국 장기"), ("EDV", "Vanguard Ext. Duration", "미국 초장기"),
           ("TIP", "iShares TIPS", "물가연동"), ("LQD", "iShares IG Corp", "우량 회사채"),
           ("HYG", "iShares High Yield", "하이일드"), ("BND", "Vanguard Total Bond", "종합")]

def last_n(series, n_days):
    """[[d,v],...] → n일 전 값"""
    if not series: return None
    d0 = (datetime.strptime(series[-1][0], "%Y-%m-%d") - timedelta(days=n_days)).strftime("%Y-%m-%d")
    prev = None
    for d, v in series:
        if d <= d0: prev = v
        else: break
    return prev

def checklist():
    gb = jload(DB / "gbonds.json"); S = gb.get("series") or {}
    out = []
    # ① 유가
    gh = (jload(DB / "global_hist.json").get("CL=F") or {})
    wti = [[f"{t[:4]}-{t[4:6]}-{t[6:]}", v] for t, v in zip(gh.get("t") or [], gh.get("v") or []) if v]
    if wti:
        cur = wti[-1][1]; m1 = last_n(wti, 30)
        ok = cur < 75
        out.append({"key": "wti", "name": "유가 WTI $75 하회", "ok": ok, "value": f"${cur:.1f}", "detail": f"1개월 {'+' if m1 and cur>=m1 else ''}{(cur/m1-1)*100:.1f}%" if m1 else "",
                    "why": "유가가 공급 물가 충격과 추가 긴축 압력을 만든다 — $75 하회가 가장 단순하고 중요한 조건(기사)", "s": wti[-260:]})
    # ② 美 고용·소비 — 질서 있는 둔화 (급랭도 과열도 아님)
    nfp = jload(DB / "series_emp_nfp.json"); nfp = nfp.get("data", nfp) if isinstance(nfp, dict) else nfp
    # series_emp_nfp 는 'YYYY-MM'=월간 증감(천명) 과 'YYYY-MM-DD'=고용 레벨(15만8천천명) 이 섞여 있다(1차 실행 3M평균 53,007 오류).
    # 증감 행(7자리 키)만 쓴다.
    nfp = [[d, v] for d, v in nfp if len(d) == 7]
    jb = jload(DB / "series_emp_jobless.json"); jb = jb.get("data", jb) if isinstance(jb, dict) else jb
    if nfp and jb:
        n3 = [v for _, v in nfp[-3:]]; avg = sum(n3) / len(n3); claims = jb[-1][1]
        if avg < 0 or claims >= 28: st, ok = "급랭(침체 신호)", False
        elif avg > 200 or claims < 18: st, ok = "과열(추가 긴축 기대)", False
        else: st, ok = "질서 있는 둔화", True
        out.append({"key": "jobs", "name": "美 고용·소비 질서 있는 둔화", "ok": ok, "value": f"NFP 3M평균 {avg:.0f}천 · 청구 {claims:.1f}만",
                    "detail": st, "why": "고용이 너무 강하면 Fed 추가 인상 기대로 채권·주식 동반 부담, 급랭하면 금융시장 충격 — 사이가 '질서 있는 둔화'(기사)",
                    "s": [[d, v] for d, v in nfp[-24:]]})
    # ③ 美 10년물
    us = S.get("US") or []
    if us:
        cur = us[-1][1]; m1 = last_n(us, 30); m3 = last_n(us, 90)
        ok = cur <= 4.6 and (m1 is None or cur <= m1)
        out.append({"key": "us10", "name": "美 10년물 4.5% 안팎 완만한 하락", "ok": ok, "value": f"{cur:.2f}%",
                    "detail": f"1M {cur-m1:+.2f}%p · 3M {cur-m3:+.2f}%p" if m1 and m3 else "", "why": "국내 10년 금리는 美 10년과 높은 상관 — 4.5% 안팎으로 완만히 내려와야 국내 고점 통과 신뢰(기사)", "s": us[-260:]})
    # ④ 국내 장기금리 신고점 미경신
    kr = S.get("KR") or []
    if kr:
        cur = kr[-1][1]; y = kr[-260:]; hi = max(v for _, v in y); hid = max(y, key=lambda x: x[1])[0]
        days = (datetime.strptime(kr[-1][0], "%Y-%m-%d") - datetime.strptime(hid, "%Y-%m-%d")).days
        ok = cur < hi - 0.05 and days >= 20
        out.append({"key": "kr10", "name": "국내 장기금리 신고점 미경신", "ok": ok, "value": f"{cur:.2f}%",
                    "detail": f"1년 고점 {hi:.2f}% ({hid}, {days}일 전)", "why": "국고 10년이 새 고점을 만들지 않으면 고점 통과 신뢰 상승(기사) — 10년물은 美 장기금리·유가·재정 부담까지 반영", "s": kr[-260:]})
    # 보조 — 장단기차·HY·美韓 스프레드
    cv = jload(DB / "series_curve_10_2.json"); cv = cv.get("data", cv) if isinstance(cv, dict) else cv
    hy = (jload(DB / "series_hy_oas.json").get("data") or [])
    aux = {}
    if cv: aux["curve"] = {"cur": cv[-1][1], "d": cv[-1][0], "m3": last_n(cv, 90), "s": cv[-260:]}
    if hy: aux["hy"] = {"cur": hy[-1][1], "d": hy[-1][0], "m3": last_n(hy, 90), "s": hy[-260:]}
    aux["us_kr"] = (gb.get("spreads") or {}).get("US-KR")
    n_ok = sum(1 for c in out if c["ok"])
    phase = ("고점 통과 확인 — 장기채 비중 확대 구간" if n_ok == 4 else "고점 접근 — 장기채 분할 매수 시작 검토" if n_ok == 3
             else "혼조 — 단기채 중심 유지, 장기채는 소량" if n_ok == 2 else "고점 미확인 — 단기채로 유동성 확보·대기")
    return out, aux, n_ok, phase

def etfs():
    import ta_screen as T
    op, _ = T.yahoo_opener()
    rows = []
    # 국내 ETF 수익률은 야후가 금리형(KOFR·CD·단기채) 가격 누적을 못 잡는다(실측 KODEX KOFR 1y +0.06% vs 실제 +2.71%).
    # → 우리 ETF 풀(etf_pool.json · 다음금융)을 정본으로 쓰고 야후는 스파크(추세선)만.
    pool = {}
    try:
        for r in (jload(DB / "etf_pool.json").get("kr") or []):
            pool[str(r.get("c"))] = r
    except Exception: pass
    for lst, mk in ((ETFS_KR, "kr"), (ETFS_US, "us")):
        syms = [s for s, _, _ in lst]
        u = "https://query1.finance.yahoo.com/v7/finance/spark?symbols=%s&range=1y&interval=1d" % _up.quote(",".join(syms))
        try: j = T.jget(u, opener=op, timeout=25)
        except Exception as e: log(f"  ⚠ etf {mk}: {e}"); continue
        got = {}
        for r0 in (j.get("spark", {}) or {}).get("result") or []:
            resp = (r0.get("response") or [{}])[0]
            ts = resp.get("timestamp") or []; cl = ((resp.get("indicators", {}) or {}).get("quote") or [{}])[0].get("close") or []
            s = [[datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%d"), float(c)] for t, c in zip(ts, cl) if c]
            if s: got[r0.get("symbol")] = s
        for sym, nm, grp in lst:
            s = got.get(sym)
            if not s:
                pr = pool.get(sym.split(".")[0]) if mk == "kr" else None
                if pr and pr.get("px"):
                    rows.append({"sym": sym, "name": nm, "grp": grp, "mk": mk, "cur": pr["px"], "src": "pool",
                                 "m1": pr.get("r1m") and round(pr["r1m"]*100, 2), "m3": pr.get("r3m") and round(pr["r3m"]*100, 2),
                                 "m6": pr.get("r6m") and round(pr["r6m"]*100, 2), "y1": pr.get("r1y") and round(pr["r1y"]*100, 2)})
                else: rows.append({"sym": sym, "name": nm, "grp": grp, "mk": mk})
                continue
            cur = s[-1][1]
            def ret(n):
                p = last_n(s, n)
                if p is None and n >= 365 and len(s) > 200: p = s[0][1]   # range=1y 가 365일에 며칠 못 미쳐 1년 수익률이 비던 결함(SGOV·BIL 실측)
                return round((cur / p - 1) * 100, 2) if p else None
            row = {"sym": sym, "name": nm, "grp": grp, "mk": mk, "cur": cur, "d": s[-1][0],
                   "w1": ret(7), "m1": ret(30), "m3": ret(91), "m6": ret(182), "y1": ret(365),
                   "spark": [v for _, v in s[::max(1, len(s) // 60)]]}
            # (2026-10-17 사용자 요청 "채권에 유리한지") 기술 상태 — 200일선比·RSI14·52주 고점比
            cl = [v for _, v in s]
            row["vs200"] = round((cur / (sum(cl[-200:]) / min(200, len(cl))) - 1) * 100, 1)
            dd = [cl[i] - cl[i - 1] for i in range(len(cl) - 14, len(cl))]; up = sum(x for x in dd if x > 0); dn = -sum(x for x in dd if x < 0)
            row["rsi"] = round(100 - 100 / (1 + up / dn), 0) if dn else 100.0
            row["hi52"] = round((cur / max(cl) - 1) * 100, 1)
            # (2026-10-17 정정) 풀(다음금융) r1y 는 수정주가 기준 = 분배 포함 총수익(실측 KODEX KOFR: 풀 +2.71% = 분배율 2.64%,
            #   야후 원가격 +0.06%). 처음엔 야후가 틀린 줄 알고 가격 열을 풀로 덮었는데 그러면 분배를 두 번 더하게 된다.
            #   → 가격 열은 야후(원가격), 총수익 1년은 풀 r1y 로 분리한다. 두 소스의 기준일 차이로 ±1%p 어긋날 수 있음.
            pr = pool.get(sym.split(".")[0]) if mk == "kr" else None
            if pr and pr.get("px"):
                row["cur"] = pr["px"]
                if pr.get("r1y") is not None: row["tr1y_pool"] = round(pr["r1y"] * 100, 2)
            rows.append(row)
        time.sleep(0.5)
    # (2026-10-17 사용자 요청 "분배금 몇 % 주는지도") TTM 분배율 — 야후 chart events=div 로 최근 1년 실제 분배금 합 ÷ 현재가.
    #   KR·US 공통(실측: KODEX KOFR 12건 2.64% = 풀 divy 일치 · 국고채3년 0건=누적형 · TLT 4.86% · HYG 6.12%).
    #   총수익 1년 ≈ 가격수익 + 분배율 — 미국처럼 월분배형은 이 합이 진짜 수익.
    for r in rows:
        try:
            j = T.jget(f"https://query1.finance.yahoo.com/v8/finance/chart/{_up.quote(r['sym'])}?range=1y&interval=1d&events=div", opener=op, timeout=20)
            res = j["chart"]["result"][0]; dv = (res.get("events") or {}).get("dividends") or {}
            tot = sum(x["amount"] for x in dv.values()); px = res["meta"].get("regularMarketPrice") or r.get("cur")
            r["dy"] = round(tot / px * 100, 2) if px else None; r["dyn"] = len(dv)
            if r.get("tr1y_pool") is not None: r["tr1y"] = r.pop("tr1y_pool"); r["tr_src"] = "다음 수정주가"
            elif r.get("y1") is not None and r["dy"] is not None: r["tr1y"] = round(r["y1"] + r["dy"], 2); r["tr_src"] = "가격+분배"
            time.sleep(0.2)
        except Exception as e:
            log(f"  ⚠ div {r['sym']}: {repr(e)[:50]}")
    return rows

# ── (2026-10-17 한경MONEY 2026.10 '일할 복리로 쌓이는 안전자산' 반영) 파킹형 ETF 4유형 16종 + 초단기 기준금리 ──
PARK = [  # 유형, 코드, 이름, 기초지표, 신용위험, 환노출
    ("CD금리형", "459580", "KODEX CD금리액티브(합성)", "CD 91일", "시중은행 신용위험 일부", False), ("CD금리형", "357870", "TIGER CD금리투자KIS(합성)", "CD 91일", "시중은행 신용위험 일부", False),
    ("CD금리형", "481050", "KODEX CD1년금리플러스액티브(합성)", "CD 1년", "시중은행 신용위험 일부", False), ("CD금리형", "477080", "RISE CD금리액티브(합성)", "CD 91일", "시중은행 신용위험 일부", False),
    ("KOFR형", "423160", "KODEX KOFR금리액티브(합성)", "KOFR(국채담보 RP 1일)", "무위험", False), ("KOFR형", "449170", "TIGER KOFR금리액티브(합성)", "KOFR", "무위험", False),
    ("KOFR형", "479520", "RISE KOFR금리액티브(합성)", "KOFR", "무위험", False), ("KOFR형", "453010", "PLUS KOFR금리", "KOFR", "무위험", False),
    ("머니마켓·초단기", "488770", "KODEX 머니마켓액티브", "단기채·CP·전단채", "편입자산 일부", False), ("머니마켓·초단기", "0043B0", "TIGER 머니마켓액티브", "단기채·CP", "편입자산 일부", False),
    ("머니마켓·초단기", "455890", "RISE 머니마켓액티브", "단기채·CP", "편입자산 일부", False), ("머니마켓·초단기", "469830", "SOL 초단기채권액티브", "초단기채", "편입자산 일부", False),
    ("SOFR·달러MMF", "0048J0", "KODEX 미국머니마켓액티브", "SOFR·美 단기국채", "무위험(美 국채담보)", True), ("SOFR·달러MMF", "456610", "TIGER 미국달러SOFR금리액티브(합성)", "SOFR", "무위험", True),
    ("SOFR·달러MMF", "455030", "KODEX 미국달러SOFR금리액티브(합성)", "SOFR", "무위험", True), ("SOFR·달러MMF", "456880", "ACE 미국달러SOFR금리(합성)", "SOFR", "무위험", True)]

def short_rates():
    """초단기 기준금리 — CD 91일·KOFR(ECOS 817Y002 일별) · SOFR(FRED). 하루 이자 = 연 ÷ 365 (기사 '일할 계산')."""
    out = {}
    try:
        import urllib.request
        K = (BASE / "keys" / "ecos.txt").read_text().strip()
        s0 = (date.today() - timedelta(days=400)).strftime("%Y%m%d"); s1 = date.today().strftime("%Y%m%d")
        for key, code, nm in (("cd91", "010502000", "CD 91일"), ("kofr", "010901000", "KOFR"), ("call", "010101000", "콜금리 1일")):
            j = json.loads(urllib.request.urlopen(f"https://ecos.bok.or.kr/api/StatisticSearch/{K}/json/kr/1/400/817Y002/D/{s0}/{s1}/{code}", timeout=25).read())
            rows = (j.get("StatisticSearch") or {}).get("row") or []
            ser = [[f"{r['TIME'][:4]}-{r['TIME'][4:6]}-{r['TIME'][6:]}", float(r["DATA_VALUE"])] for r in rows if r.get("DATA_VALUE")]
            if ser: out[key] = {"name": nm, "cur": ser[-1][1], "d": ser[-1][0], "m3": last_n(ser, 90), "s": ser[-260:]}
    except Exception as e: log(f"  ⚠ ecos short: {repr(e)[:60]}")
    try:
        from nmr_fred import fred_series
        ser = fred_series("SOFR", start=(date.today() - timedelta(days=400)).isoformat())
        if ser: out["sofr"] = {"name": "SOFR(美)", "cur": ser[-1][1], "d": ser[-1][0], "m3": last_n(ser, 90), "s": ser[-260:]}
    except Exception as e: log(f"  ⚠ sofr: {repr(e)[:60]}")
    for v in out.values(): v["daily"] = round(v["cur"] / 365, 5)     # 하루 이자(%)
    return out

def parking():
    pool = {str(r.get("c")): r for r in (jload(DB / "etf_pool.json").get("kr") or [])}
    rows = []
    for typ, c, nm, base, credit, fx in PARK:
        r = pool.get(c) or {}
        rows.append({"type": typ, "c": c, "name": nm, "base": base, "credit": credit, "fx": fx, "px": r.get("px"), "cap": r.get("cap"), "fee": r.get("fee"),
                     "m1": pct((r.get("r1m") or 0) * 100, 2) if r.get("r1m") is not None else None, "m3": pct((r.get("r3m") or 0) * 100, 2) if r.get("r3m") is not None else None,
                     "m6": pct((r.get("r6m") or 0) * 100, 2) if r.get("r6m") is not None else None, "y1": pct((r.get("r1y") or 0) * 100, 2) if r.get("r1y") is not None else None,
                     "divy": r.get("divy")})
    return rows

def judge_etfs(rows, chk, aux, n_ok, sr):
    """만기(듀레이션)별 '지금 유리한가' — 기사 프레임(고점 확인 전 단기채, 확인 후 장기채)을 ETF 행에 대입.
       bucket: park(파킹) / short(1~3년) / mid(7~10년) / long(20년+·초장기) / credit(회사채·HY·종합) / tips(물가연동)
       점수 0~4 → 🟢 유리(3↑) 🟡 보통(2) 🔴 불리(≤1). 근거는 why 에 열거."""
    us10 = next((c for c in chk if c["key"] == "us10"), {}); kr10 = next((c for c in chk if c["key"] == "kr10"), {})
    hy = aux.get("hy") or {}; hy_widen = hy.get("cur") is not None and hy.get("m3") is not None and hy["cur"] > hy["m3"] + 0.2
    curve = (aux.get("curve") or {}).get("cur")
    def bucket(g):
        if "파킹" in g or "초단기" in g: return "park"
        if "1년" in g or "단기" in g or "3년" in g: return "short"
        if "중기" in g or "7-10" in g or "10년" in g: return "mid"
        if "물가" in g: return "tips"
        if "회사채" in g or "하이일드" in g or "종합" in g: return "credit"
        return "long"
    for r in rows:
        if not r.get("cur"): continue
        b = bucket(r["grp"]); sc = 0; why = []
        if b == "park":
            sc = 3; why.append("듀레이션 0 — 금리 변동 무관")
            if n_ok < 3: sc += 1; why.append(f"고점 미확인({n_ok}/4) = 대기자금 둘 곳")
            else: why.append("고점 통과 신호 — 장기채로 옮길 때")
        elif b == "short":
            sc = 2; why.append("금리 민감도 낮음")
            if n_ok < 3: sc += 1; why.append("고점 확인 전 — 기사 '단기채 50%' 구간")
            if r.get("vs200") is not None and r["vs200"] <= 0: sc += 1; why.append("200일선 아래")
        elif b in ("mid", "long"):
            if n_ok >= 3: sc += 2; why.append(f"고점 통과 신호 {n_ok}/4 — 장기채 비중 확대 구간")
            elif n_ok == 2: sc += 1; why.append("혼조(2/4) — 분할 소량")
            else: why.append(f"고점 미확인({n_ok}/4) — 금리 더 오르면 손실 확대")
            if r.get("vs200") is not None and r["vs200"] <= -3: sc += 1; why.append("200일선 아래(눌림)")
            if r.get("rsi") is not None and r["rsi"] < 40: sc += 1; why.append(f"RSI {r['rsi']:.0f} 과매도")
            if b == "long" and curve is not None and curve < 0.3: why.append("장단기차 축소 — 장기채 추가 상승여력 제한")
            if r.get("dy") and r["dy"] >= 4.5: sc = min(4, sc + 1); why.append(f"분배율 {r['dy']}% — 캐리 확보")
            if b == "long" and n_ok < 3: sc = min(sc, 2); why.append("고점 확신 전 장기채는 '소량'까지(기사) — 유리 판정 보류")
        elif b == "credit":
            sc = 2
            if hy_widen: sc -= 1; why.append(f"HY 가산금리 확대 중({hy.get('m3')}→{hy.get('cur')}%p) — 상환능력 불신")
            else: why.append("신용스프레드 안정")
            if n_ok >= 3: sc += 1; why.append("금리 고점 통과 신호")
            if r.get("dy") and r["dy"] >= 5: sc += 1; why.append(f"분배율 {r['dy']}%")
        elif b == "tips":
            sc = 2; why.append("기대인플레 상승 시 유리 — 유가·CPI 재가속 국면의 보험")
            if not next((c["ok"] for c in chk if c["key"] == "wti"), True): sc += 1; why.append("유가 $75↑ — 인플레 재점화 위험")
        r["score"] = max(0, min(4, sc)); r["lamp"] = "유리" if r["score"] >= 3 else "보통" if r["score"] == 2 else "불리"; r["why"] = " · ".join(why)
    return rows

def regime():
    """(2026-10-17) 매경ECONOMY 2026.10.7 커버스토리 '5% 금리 시대' 3가지를 기계 판정:
       ① 긴축 성격 — 메리츠 이진우 "금리 절대 수준보다 끌어올리는 요인이 성장(실질금리)인지 비용(기대인플레)인지".
          美 10Y 변화(3M·6M)를 실질금리(DFII10) + 기대인플레(T10YIE) 로 분해 → 실질 주도=성장형(2015~18 S&P +25%) / BEI 주도=인플레형(2022 S&P −18%).
       ② 명목성장률 − 10Y — 메리츠 1962~ 실측 "명목성장률 > 10Y 금리였던 시기엔 S&P 장기평균 상회". FRED GDP(SAAR)·ECOS 200Y109 명목GDP YoY vs 10년물.
       ③ 인상 사이클 종료 — 현대차증권 "마지막 인상 후 글로벌 채권 6M +4.6%·12M +6.6%(이전 6M +0.7%)". 마지막 인상일(FRED DFEDTARU·ECOS 722Y001) 경과,
          FF선물(ZQ 12월·내년 6월물, 야후 .CBT) 이 반영한 추가 인상 폭, 9월 SEP 중간값·전문가 8인 컨센(정적 큐레이션)."""
    from nmr_fred import fred_series
    s2 = (date.today() - timedelta(days=400)).isoformat()
    R = {}
    try:
        real = fred_series("DFII10", start=s2); bei = fred_series("T10YIE", start=s2); us10 = fred_series("DGS10", start=s2)
        def dec(n):
            out = {}
            for k, s in (("us10", us10), ("real", real), ("bei", bei)):
                p = last_n(s, n); out[k] = round(s[-1][1] - p, 2) if (s and p is not None) else None
            tot = out["us10"]
            if tot is None or out["real"] is None or out["bei"] is None: out["kind"] = None; return out
            if abs(tot) < 0.15: out["kind"] = "보합"; out["label"] = "금리 횡보 — 성격 판정 유보"
            elif tot < 0: out["kind"] = "하락"; out["label"] = "금리 하락 국면" + ("(실질 주도 — 성장 둔화 우려)" if out["real"] < out["bei"] else "(기대인플레 하락 — 물가 안정)")
            else:
                sh = min(1.0, max(0.0, out["real"] / tot))   # BEI 가 반대로 움직이면 100% 로 캡
                out["real_share"] = round(sh * 100)
                if sh >= 0.6: out["kind"] = "성장형"; out["label"] = f"성장형 긴축 — 실질금리가 상승분의 {sh*100:.0f}% (주식에 우호, 2015~18 유형)"
                elif sh <= 0.4: out["kind"] = "인플레형"; out["label"] = f"인플레형 긴축 — 기대인플레가 상승분의 {(1-sh)*100:.0f}% (주식·채권 동반 약세, 2022 유형)"
                else: out["kind"] = "혼합"; out["label"] = f"혼합 — 실질 {sh*100:.0f}% · 기대인플레 {(1-sh)*100:.0f}%"
            return out
        R["decomp"] = {"m3": dec(90), "m6": dec(180), "cur": {"us10": us10[-1][1] if us10 else None, "real": real[-1][1] if real else None, "bei": bei[-1][1] if bei else None, "d": us10[-1][0] if us10 else None},
                       "s": {"us10": us10[-260:], "real": real[-260:], "bei": bei[-260:]}}
    except Exception as e: log(f"  ⚠ regime decomp: {repr(e)[:80]}")
    # ② 명목성장률 − 10Y
    g = {}
    try:
        gdp = fred_series("GDP", start="2022-01-01")
        if len(gdp) >= 5:
            yoy = (gdp[-1][1] / gdp[-5][1] - 1) * 100; cur10 = (R.get("decomp") or {}).get("cur", {}).get("us10")
            g["US"] = {"gdp_yoy": round(yoy, 1), "q": gdp[-1][0][:7], "y10": cur10, "gap": round(yoy - cur10, 1) if cur10 is not None else None}
    except Exception as e: log(f"  ⚠ regime gdp us: {repr(e)[:60]}")
    try:
        import urllib.request
        K = (BASE / "keys" / "ecos.txt").read_text().strip()
        j = json.loads(urllib.request.urlopen(f"https://ecos.bok.or.kr/api/StatisticSearch/{K}/json/kr/1/100/200Y109/Q/2022Q1/{date.today().year}Q4/10601", timeout=25).read())
        rows = [(r["TIME"], float(r["DATA_VALUE"])) for r in ((j.get("StatisticSearch") or {}).get("row") or []) if r.get("DATA_VALUE")]
        kr10 = ((jload(DB / "gbonds.json").get("series") or {}).get("KR") or [])
        if len(rows) >= 8 and kr10:
            # 원계열(계절 미조정)이라 단일 분기 YoY 는 들쭉날쭉(1차 실측 2026Q2 +26%) → 최근 4분기 합 / 전년 4분기 합
            yoy = (sum(v for _, v in rows[-4:]) / sum(v for _, v in rows[-8:-4]) - 1) * 100
            g["KR"] = {"gdp_yoy": round(yoy, 1), "q": rows[-1][0] + " 4Q합", "y10": kr10[-1][1], "gap": round(yoy - kr10[-1][1], 1)}
    except Exception as e: log(f"  ⚠ regime gdp kr: {repr(e)[:60]}")
    R["growth_gap"] = g
    # ③ 인상 사이클 종료
    cyc = {}
    try:
        tu = fred_series("DFEDTARU", start="2022-01-01"); dff = fred_series("DFF", start=s2)
        last_hike = next((tu[i][0] for i in range(len(tu) - 1, 0, -1) if tu[i][1] > tu[i - 1][1]), None)
        last_cut = next((tu[i][0] for i in range(len(tu) - 1, 0, -1) if tu[i][1] < tu[i - 1][1]), None)
        us = {"upper": tu[-1][1] if tu else None, "dff": dff[-1][1] if dff else None, "last_hike": last_hike, "last_cut": last_cut,
              "days": (date.today() - datetime.strptime(last_hike, "%Y-%m-%d").date()).days if last_hike else None}
        # FF 선물: 다음 12월물·그 다음 6월물 (야후 ZQ<월코드><yy>.CBT, 가격=100−기간평균 FFR)
        import ta_screen as T
        op, _ = T.yahoo_opener(); y = date.today().year; yy = y if date.today().month <= 10 else y + 1
        fut = []
        for code, yr, nm in (("Z", yy, f"{yy}.12"), ("M", yy + 1, f"{yy+1}.6")):
            try:
                jj = T.jget(f"https://query1.finance.yahoo.com/v8/finance/chart/{_up.quote(f'ZQ{code}{str(yr)[2:]}.CBT')}?range=5d&interval=1d", opener=op, timeout=15)
                px = [v for v in jj["chart"]["result"][0]["indicators"]["quote"][0]["close"] if v]
                if px:
                    imp = round(100 - px[-1], 3); fut.append({"m": nm, "implied": imp, "vs_dff": round((imp - us["dff"]) * 100) if us["dff"] is not None else None})
            except Exception as e: log(f"  ⚠ ZQ{code}{yr}: {repr(e)[:50]}")
        us["futures"] = fut
        us["sep"] = {"src": "FOMC 2026.9 SEP 중간값(매경 2026.10.7)", "2026E": 4.1, "2027E": 4.1, "prev_2026E": 3.8, "prev_2027E": 3.6}
        cyc["US"] = us
    except Exception as e: log(f"  ⚠ regime cycle us: {repr(e)[:60]}")
    try:
        import urllib.request
        K = (BASE / "keys" / "ecos.txt").read_text().strip()
        j = json.loads(urllib.request.urlopen(f"https://ecos.bok.or.kr/api/StatisticSearch/{K}/json/kr/1/200/722Y001/M/202001/{date.today().strftime('%Y%m')}/0101000", timeout=25).read())
        rows = [(r["TIME"], float(r["DATA_VALUE"])) for r in ((j.get("StatisticSearch") or {}).get("row") or []) if r.get("DATA_VALUE")]
        lh = next((rows[i][0] for i in range(len(rows) - 1, 0, -1) if rows[i][1] > rows[i - 1][1]), None)
        lc = next((rows[i][0] for i in range(len(rows) - 1, 0, -1) if rows[i][1] < rows[i - 1][1]), None)
        f = lambda t: f"{t[:4]}-{t[4:]}" if t else None
        cyc["KR"] = {"rate": rows[-1][1] if rows else None, "last_hike": f(lh), "last_cut": f(lc),
                     "days": (date.today() - datetime.strptime(lh, "%Y%m").date()).days if lh else None}
    except Exception as e: log(f"  ⚠ regime cycle kr: {repr(e)[:60]}")
    # 전문가 컨센 — 매경이코노미 채권 전문가 8인 설문(2026.10.7) 정적 큐레이션
    cyc["consensus"] = {"src": "매경ECONOMY 2026.10.7 채권 전문가 8인", "us_2026": "4.25% (8/8 연내 1회 더)", "us_2027_6": "4.25% 5명 · 4.5% 3명", "kr_2026": "3.25% (8/8 연내 1회 더)",
                        "kr_2027_6": "3.5% 7명", "first_cut": "美 2027 4Q~2028 · 韓 2028 2Q (AI 설비투자 피크아웃이 전환점)"}
    # 판정: 시장이 추가 인상을 얼마나 반영하는가
    fut = (cyc.get("US") or {}).get("futures") or []
    near = fut[0]["vs_dff"] if fut and fut[0].get("vs_dff") is not None else None
    if near is None: cyc["verdict"] = None
    elif near >= 20: cyc["verdict"] = {"st": "진행 중", "ok": False, "txt": f"선물이 {fut[0]['m']}까지 +{near}bp(≈{near/25:.1f}회) 추가 인상을 반영 — 사이클 미종료, 장기채 '소량' 유지"}
    elif near >= 8: cyc["verdict"] = {"st": "막바지", "ok": False, "txt": f"선물 반영 +{near}bp — 한 차례 미만. 종료 임박이나 확인 전(기사: 마지막 인상 전 6M 채권 +0.7%)"}
    else: cyc["verdict"] = {"st": "종료 신호", "ok": True, "txt": f"선물이 추가 인상을 거의 반영 안 함({near:+d}bp) — 마지막 인상 후 6M +4.6%·12M +6.6% 구간 진입 가능성"}
    R["cycle"] = cyc
    R["ref"] = {"hike_eras": "1990년 이후 美 금리 인상기 6차례 S&P500 누적 평균 +7.4% (1994 +4.3 · 1997 +1.5 · 1999 +3.5 · 2004 +11.3 · 2015 +22.7 · 2022 +1.3, 블룸버그·현대차증권)",
                "types": "성장형(2015.12~18) S&P +25%·종합채권 +5% / 인플레형(2022) S&P −18%·종합채권 −13% (신한투자증권)",
                "after_hike": "글로벌 채권 마지막 인상 후 6M +4.6%·12M +6.6% vs 인상 전 6M +0.7%·12M +0.4% (현대차증권)",
                "alt": "과거 美 인상기 글로벌 인프라 +8.2%·원자재 +9.2% (2004~, 연환산) / 韓 리츠·인프라 −12% (현대차증권)"}
    return R

def main():
    log("[bonds] 시작")
    chk, aux, n_ok, phase = checklist()
    reg = {}
    try: reg = regime()
    except Exception as e: log(f"  ⚠ regime: {repr(e)[:80]}")
    pr = jload(DB / "policy_rates.json").get("rows") or []
    gb = jload(DB / "gbonds.json")
    countries = gb.get("countries") or []
    series = {k: v[-260:] for k, v in (gb.get("series") or {}).items() if k in ("US", "KR", "DE", "JP")}
    rows = []
    try: rows = etfs()
    except Exception as e: log(f"  ⚠ etfs: {e}")
    # 배분 가이드 — 기사 프레임 (투자권유 아님)
    alloc = {"base": {"현금성": 10, "단기채": 50, "장기채": 20, "우량 회사채": 20},
             "after": {"현금성": 10, "단기채": 20, "장기채": 50, "우량 회사채": 20},
             "n_ok": n_ok, "phase": phase,
             "note": "메리츠 윤여삼(한경MONEY 2026.10): 고점 확신 전 단기채 50%로 유동성 확보, 최종금리 3.25~3.5% 확신 시 장기채 50%로 점진 전환. 회사채는 신용등급만 믿지 말고 신용스프레드·부채비율(200%)·이자보상배율(2배)을 함께. 초장기채·레버리지 ETF 몰빵 금지, 분할 매수·만기 분산."}
    sr = short_rates(); pk = parking()
    rows = judge_etfs(rows, chk, aux, n_ok, sr)
    OUT.write_text(json.dumps({"as_of": datetime.now(KST).strftime("%Y-%m-%d %H:%M"), "checklist": chk, "aux": aux, "short": sr, "parking": pk,
                               "policy": pr, "countries": countries, "series": series, "etfs": rows, "alloc": alloc, "regime": reg},
                              ensure_ascii=False), encoding="utf-8")
    log(f"[bonds] ✅ 체크리스트 {n_ok}/4 · {phase} · ETF {sum(1 for r in rows if r.get('cur'))}/{len(rows)} → {OUT}")

if __name__ == "__main__":
    main()
