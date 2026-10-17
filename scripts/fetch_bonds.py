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

ETFS_KR = [("148070.KS", "KOSEF 국고채10년", "국내 장기"), ("114260.KS", "KODEX 국고채3년", "국내 단기"),
           ("439870.KS", "KODEX 국고채30년액티브", "국내 초장기"), ("385560.KS", "RISE KIS국고채30년Enhanced", "국내 초장기"),
           ("273130.KS", "KODEX 종합채권(AA-이상)액티브", "국내 회사채 혼합"), ("305080.KS", "TIGER 미국채10년선물", "미국 장기(KR상장)"),
           ("453850.KS", "ACE 미국30년국채액티브(H)", "미국 초장기(KR상장·환헤지)"), ("423160.KS", "KODEX 미국채울트라30년선물(H)", "미국 초장기(KR상장·환헤지)")]
ETFS_US = [("SHY", "iShares 1-3Y Treasury", "미국 단기"), ("IEF", "iShares 7-10Y Treasury", "미국 중기"),
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
            if not s: rows.append({"sym": sym, "name": nm, "grp": grp, "mk": mk}); continue
            cur = s[-1][1]
            def ret(n):
                p = last_n(s, n); return round((cur / p - 1) * 100, 2) if p else None
            rows.append({"sym": sym, "name": nm, "grp": grp, "mk": mk, "cur": cur, "d": s[-1][0],
                         "w1": ret(7), "m1": ret(30), "m3": ret(91), "m6": ret(182), "y1": ret(365),
                         "spark": [v for _, v in s[::max(1, len(s) // 60)]]})
        time.sleep(0.5)
    return rows

def main():
    log("[bonds] 시작")
    chk, aux, n_ok, phase = checklist()
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
    OUT.write_text(json.dumps({"as_of": datetime.now(KST).strftime("%Y-%m-%d %H:%M"), "checklist": chk, "aux": aux,
                               "policy": pr, "countries": countries, "series": series, "etfs": rows, "alloc": alloc},
                              ensure_ascii=False), encoding="utf-8")
    log(f"[bonds] ✅ 체크리스트 {n_ok}/4 · {phase} · ETF {sum(1 for r in rows if r.get('cur'))}/{len(rows)} → {OUT}")

if __name__ == "__main__":
    main()
