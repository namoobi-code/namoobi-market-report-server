#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""program_trading.py — 3.2.1 프로그램매매(차익·비차익·전체) 일별 + 등락종목수 (2026-08-02 신설).

소스 (실측):
  (2026-10-31 교체) KIS 프로그램매매 종합현황(일별) FHPPG04600001 /quotations/comp-program-trade-daily — 단위 백만원 → /100 = 억원.
    FID_MRKT_CLS_CODE K=코스피 · Q=코스닥, 날짜 범위 지정. 구 네이버 PC 페이지(programDealTrendDay.naver)는
    2026-09 "이 페이지는 더 이상 제공되지 않습니다"로 폐쇄돼 9/17 이후 신규 0일로 멈췄다(홈피 3.2.1 프로그램 행이 6주 전 값).
    두 소스는 같은 KRX 집계 — 완결일 실측 일치(9/15 차익 -1,342 · 전체 -9,189 ✓, 9/16 562 · -12,437 ✓). 네이버 9/17 행은
    장중 부분값(차익 1,239 vs KIS 확정 2,130)이라 KIS 로 덮어쓴다(20260917 이후 KIS 로 재수집).
  KIS 지수현재가(FHPUP02100000) — 등락종목수(상승·상한·보합·하락·하한), 이력은 일별 누적

산출: data/db/program_trading.json
  {asof, kospi:{t,arb,nonarb,whole}, kosdaq:{...}, updown:{kospi:{...},kosdaq:{...}},
   updown_hist:{kospi:{t,up,down}, kosdaq:{...}}}
cron: 16:15(당일 확정) · 18:40(안전망). 첫 실행 --backfill 40 페이지(약 1년).
"""
import json, re, sys, time, urllib.request
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "data" / "db" / "program_trading.json"
DAYS = 400 if "--backfill" in sys.argv else 20   # 조회 일수(달력) — 평시 20일(재시도 여유), 백필 400일


def kis_daily(mk, days):
    """일자별 {YYYYMMDD: (차익순매수, 비차익순매수, 전체순매수)} — 단위 억원. mk: 'K' 코스피 · 'Q' 코스닥.
    KIS 는 한 호출에 ~35영업일까지 돌려주므로 45일 단위로 잘라 과거로 내려간다."""
    from datetime import timedelta
    sys.path.insert(0, str(BASE / "scripts"))
    import kis_api as K
    c = K._creds(); tok = K._token(c)
    rows = {}
    end = datetime.now()
    while (datetime.now() - end).days < days:
        start = end - timedelta(days=45)
        try:
            j = K._get(c, tok, "/uapi/domestic-stock/v1/quotations/comp-program-trade-daily", "FHPPG04600001",
                       {"FID_COND_MRKT_DIV_CODE": "J", "FID_MRKT_CLS_CODE": mk, "FID_COND_SCR_DIV_CODE": "20460",
                        "FID_INPUT_DATE_1": start.strftime("%Y%m%d"), "FID_INPUT_DATE_2": end.strftime("%Y%m%d")})
        except Exception as e:
            print(f"  [warn] KIS 프로그램 일별 실패({mk} {start:%m%d}~{end:%m%d}): {e}"); break
        got = 0
        for r in j.get("output") or []:
            try:
                rows[r["stck_bsop_date"]] = (round(float(r["arbt_smtn_ntby_tr_pbmn"]) / 100, 1),
                                             round(float(r["nabt_smtn_ntby_tr_pbmn"]) / 100, 1),
                                             round(float(r["whol_smtn_ntby_tr_pbmn"]) / 100, 1))
                got += 1
            except (KeyError, ValueError):
                pass
        if not got:
            break
        end = start - timedelta(days=1)
        time.sleep(0.3)
    return rows

def kis_updown():
    """KIS 지수현재가 — 등락종목수 (장중/장후 당일값)."""
    try:
        sys.path.insert(0, str(BASE / "scripts"))
        import kis_api as K
        c = K._creds(); tok = K._token(c)
        out = {}
        for name, code in (("kospi", "0001"), ("kosdaq", "1001")):
            j = K._get(c, tok, "/uapi/domestic-stock/v1/quotations/inquire-index-price",
                       "FHPUP02100000", {"FID_COND_MRKT_DIV_CODE": "U", "FID_INPUT_ISCD": code})
            o = j.get("output") or {}
            out[name] = {"up": int(o.get("ascn_issu_cnt") or 0), "uplm": int(o.get("uplm_issu_cnt") or 0),
                         "flat": int(o.get("stnr_issu_cnt") or 0), "down": int(o.get("down_issu_cnt") or 0),
                         "lslm": int(o.get("lslm_issu_cnt") or 0)}
            time.sleep(0.25)
        return out
    except Exception as e:
        print(f"  [warn] KIS 등락 실패: {e}")
        return {}

def main():
    old = {}
    try: old = json.loads(OUT.read_text(encoding="utf-8"))
    except Exception: pass
    out = {"asof": datetime.now().strftime("%Y-%m-%d %H:%M")}
    for name, mk in (("kospi", "K"), ("kosdaq", "Q")):
        prev = old.get(name) or {}
        m = dict(zip(prev.get("t") or [], zip(prev.get("arb") or [], prev.get("nonarb") or [], prev.get("whole") or [])))
        new = kis_daily(mk, DAYS)
        m.update(new)                                   # KIS 확정값이 네이버 장중 부분값(9/17)을 덮어쓴다
        ts = sorted(m)[-600:]
        out[name] = {"t": ts, "arb": [m[t][0] for t in ts], "nonarb": [m[t][1] for t in ts],
                     "whole": [m[t][2] for t in ts]}
        print(f"  {name}: 신규 {len(new)}일 · 누적 {len(ts)}일 · 최신 {ts[-1] if ts else '—'} "
              f"차익 {out[name]['arb'][-1] if ts else '—'}억")
    ud = kis_updown()
    if ud:
        out["updown"] = ud
        out["updown_asof"] = datetime.now().strftime("%m/%d %H:%M")
        hist = old.get("updown_hist") or {}
        # (2026-10-31) 키는 '오늘'이 아니라 프로그램 일별의 최신 영업일 — 주말·휴일에 돌면 KIS 가 직전 영업일 등락을 돌려주므로 토요일 키가 생겼다
        today = (out.get("kospi") or {}).get("t", [datetime.now().strftime("%Y%m%d")])[-1]
        for k in ("kospi", "kosdaq"):
            h = hist.get(k) or {"t": [], "up": [], "down": []}
            m2 = dict(zip(h["t"], zip(h["up"], h["down"])))
            m2[today] = (ud[k]["up"], ud[k]["down"])
            ts = sorted(m2)[-600:]
            hist[k] = {"t": ts, "up": [m2[t][0] for t in ts], "down": [m2[t][1] for t in ts]}
        out["updown_hist"] = hist
    elif old.get("updown"):
        out["updown"] = old["updown"]; out["updown_asof"] = old.get("updown_asof")
        out["updown_hist"] = old.get("updown_hist") or {}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    print(f"[program] ✅ 저장 → {OUT}")

if __name__ == "__main__":
    main()
