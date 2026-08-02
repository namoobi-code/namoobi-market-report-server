#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""program_trading.py — 3.2.1 프로그램매매(차익·비차익·전체) 일별 + 등락종목수 (2026-08-02 신설).

소스 (실측):
  네이버 PC /sise/programDealTrendDay.naver?bizdate=&sosok=&page=N — 일자별 순매수(억원)
    sosok=''(코스피) · '01'(코스닥). KIS 종합현황(시간)과 교차 검증 일치(7/31 차익 -8,127억 ✓)
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
H = {"User-Agent": "Mozilla/5.0", "Referer": "https://finance.naver.com/sise/sise_program.naver"}
PAGES = 40 if "--backfill" in sys.argv else 3

_NUM = re.compile(r'class="(?:date|rate_up|rate_down|rate_pause|number2?)[^"]*">\s*([\d.,\-]+)\s*<')

def naver_daily(sosok, pages):
    """일자별 (date, 차익순매수, 비차익순매수, 전체순매수) — 단위 억원."""
    rows = {}
    for pg in range(1, pages + 1):
        url = (f"https://finance.naver.com/sise/programDealTrendDay.naver"
               f"?bizdate={datetime.now():%Y%m%d}&sosok={sosok}&page={pg}")
        try:
            d = urllib.request.urlopen(urllib.request.Request(url, headers=H), timeout=15).read().decode("euc-kr", "ignore")
        except Exception:
            break
        # 행: 날짜(26.07.31) + 9숫자(차익 매수/매도/순매수, 비차익 3, 전체 3)
        got = 0
        for m in re.finditer(r'class="date">\s*(\d{2}\.\d{2}\.\d{2})\s*</td>(.*?)</tr>', d, re.S):
            dt8 = "20" + m.group(1).replace(".", "")
            nums = [x.replace(",", "") for x in re.findall(r">\s*(-?[\d,]+)\s*</td>", m.group(2))]
            if len(nums) >= 9:
                try:
                    rows[dt8] = (float(nums[2]), float(nums[5]), float(nums[8]))
                    got += 1
                except ValueError:
                    pass
        if not got:
            break
        time.sleep(0.12)
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
    for name, sosok in (("kospi", ""), ("kosdaq", "02")):   # 실측: ''=코스피 · '02'=코스닥(KIS Q와 일치)
        prev = old.get(name) or {}
        m = dict(zip(prev.get("t") or [], zip(prev.get("arb") or [], prev.get("nonarb") or [], prev.get("whole") or [])))
        new = naver_daily(sosok, PAGES)
        m.update(new)
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
        today = datetime.now().strftime("%Y%m%d")
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
