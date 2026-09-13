#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_gbonds.py — 3.1.1 「주요국 10년 국채금리」 서버 수집 (2026-09-13 신설 · 사용자 요청: 3.1.1 에 국가별 채권수익률 모아서)

  출력: data/db/gbonds.json  → 홈피 3.1.1 패널(app.js) + 보고서 gen_gbonds_chart.py(/api/db/gbonds 회수) 가 같은 데이터를 쓴다.
  대상 11개국: 미국·독일·프랑스·이탈리아·스페인·영국·일본·한국·중국·호주·캐나다 (10년물 벤치마크)
  1순위 = stooq 일별 CSV (무키 · https://stooq.com/q/d/l/?s=10usy.b&i=d ; 심볼 = 10<국가2>y.b)
  2순위 = FRED 월별 OECD 장기금리 IRLTLT01<CC>M156N (미국은 DGS10 일별) — stooq 가 일일 한도('Exceeded the daily hits limit')·
          장애일 때 국가별로 폴백하고 freq 를 'monthly' 로 표기(중국은 FRED 미제공 → 직전 DB 값 유지).
  3순위 = 직전 DB 값 carry-forward(freq 뒤에 '(stale)').
  스키마: {"as_of","source","countries":[{cc,name,cur,date,d1,w1,m1,m3,m6,y1,freq,src}],"spreads":{...bp},"series":{cc:[["YYYY-MM-DD",v],..]}}
  · 변화 단위는 **bp**(수익률은 % 등락률이 아니라 bp 차이로 보는 것이 관행), series 는 최근 3년(일별 ≤ 800점)만 저장(번들 비대화 방지).
  cron: 매일 05:25·15:25 KST (06:00 보고서가 당일 새벽 수집본을 쓴다).  ⚠ 추정 금지 — 실측·폴백·stale 만.
"""
import json, csv, io, os, sys, urllib.request, urllib.error
from datetime import datetime, timedelta
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DB = BASE / "data" / "db"; DB.mkdir(parents=True, exist_ok=True)
OUT = DB / "gbonds.json"

# (cc, 한글명, stooq 심볼, FRED 폴백 시리즈)
ROWS = [
    ("US", "미국",     "10usy.b", "DGS10"),
    ("DE", "독일",     "10dey.b", "IRLTLT01DEM156N"),
    ("FR", "프랑스",   "10fry.b", "IRLTLT01FRM156N"),
    ("IT", "이탈리아", "10ity.b", "IRLTLT01ITM156N"),
    ("ES", "스페인",   "10esy.b", "IRLTLT01ESM156N"),
    ("GB", "영국",     "10uky.b", "IRLTLT01GBM156N"),
    ("JP", "일본",     "10jpy.b", "IRLTLT01JPM156N"),
    ("KR", "한국",     "10kry.b", "IRLTLT01KRM156N"),
    ("CN", "중국",     "10cny.b", None),
    ("AU", "호주",     "10auy.b", "IRLTLT01AUM156N"),
    ("CA", "캐나다",   "10cay.b", "IRLTLT01CAM156N"),
]
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
KEEP_DAYS = 3 * 365 + 10

def _get(url, timeout=25):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="replace")

def stooq(sym):
    """일별 CSV: Date,Open,High,Low,Close,Volume → [(date, close)]. 한도 초과·빈 응답이면 None."""
    try:
        txt = _get(f"https://stooq.com/q/d/l/?s={sym}&i=d")
    except Exception as e:
        print(f"  stooq {sym}: {type(e).__name__}"); return None
    if "Exceeded" in txt[:200] or "Date" not in txt[:50]:
        print(f"  stooq {sym}: 한도/형식 오류 — {txt[:60]!r}"); return None
    out = []
    for row in csv.DictReader(io.StringIO(txt)):
        try:
            out.append((row["Date"], float(row["Close"])))
        except Exception:
            pass
    return out or None

def _fred_key():
    try: return (BASE / "fred.key").read_text().strip()
    except Exception: return ""

def fred(series_id):
    k = _fred_key()
    try:
        if k:
            j = json.loads(_get("https://api.stlouisfed.org/fred/series/observations"
                                f"?series_id={series_id}&api_key={k}&file_type=json"))
            return [(o["date"], float(o["value"])) for o in j.get("observations", []) if o.get("value") not in (".", "", None)]
        rows = list(csv.reader(io.StringIO(_get(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"))))
        return [(d, float(v)) for d, v in rows[1:] if v not in (".", "")]
    except Exception as e:
        print(f"  FRED {series_id}: {type(e).__name__}"); return None

def bp_changes(pts):
    """현재값 + 과거 N일 전 대비 bp 변화(1d=직전 관측, 1w/1m/3m/6m/1y=캘린더 기준 ≤ 그 날짜의 마지막 관측)."""
    if not pts: return {}
    last_d = datetime.strptime(pts[-1][0], "%Y-%m-%d"); cur = pts[-1][1]
    o = {"cur": round(cur, 3), "date": pts[-1][0]}
    o["d1"] = round((cur - pts[-2][1]) * 100, 1) if len(pts) >= 2 else None
    for k, days in (("w1", 7), ("m1", 30), ("m3", 91), ("m6", 182), ("y1", 365)):
        tgt = (last_d - timedelta(days=days)).strftime("%Y-%m-%d")
        cand = [p for p in pts if p[0] <= tgt]
        o[k] = round((cur - cand[-1][1]) * 100, 1) if cand else None
    return o

def main():
    try: prev = json.loads(OUT.read_text(encoding="utf-8"))
    except Exception: prev = {}
    prev_c = {c["cc"]: c for c in prev.get("countries", []) if isinstance(c, dict)}
    prev_s = prev.get("series", {}) if isinstance(prev.get("series"), dict) else {}
    cutoff = (datetime.now() - timedelta(days=KEEP_DAYS)).strftime("%Y-%m-%d")

    countries, series, n_stooq, n_fred, n_stale = [], {}, 0, 0, 0
    for cc, name, sym, fid in ROWS:
        pts, freq, src = stooq(sym), "daily", f"stooq {sym}"
        if pts: n_stooq += 1
        elif fid:
            pts = fred(fid)
            if pts:
                freq, src = ("daily" if fid == "DGS10" else "monthly"), f"FRED {fid}"; n_fred += 1
        if not pts:
            # 3순위: 직전 DB carry-forward
            if cc in prev_c and prev_s.get(cc):
                c = dict(prev_c[cc]); c["freq"] = str(c.get("freq", "")).replace("(stale)", "").strip() + "(stale)"
                countries.append(c); series[cc] = prev_s[cc]; n_stale += 1
                print(f"  {name}: 수집 실패 → 직전값 유지(stale)")
            else:
                print(f"  {name}: 수집 실패·DB 없음 → 제외")
            continue
        pts = sorted(set(pts))
        # (stooq 결측 방어) 이전 시계열과 날짜 union — 하루 빠진 점은 직전 DB 로 메운다
        if prev_s.get(cc):
            d = {p[0]: p[1] for p in prev_s[cc]}; d.update({p[0]: p[1] for p in pts})
            pts = sorted(d.items())
        pts = [p for p in pts if p[0] >= cutoff]
        row = {"cc": cc, "name": name, "freq": freq, "src": src}; row.update(bp_changes(pts))
        countries.append(row); series[cc] = [[d, round(v, 3)] for d, v in pts]

    cur = {c["cc"]: c.get("cur") for c in countries}
    spreads = {}
    for a, b in (("IT", "DE"), ("FR", "DE"), ("ES", "DE"), ("US", "DE"), ("US", "JP"), ("US", "KR")):
        if cur.get(a) is not None and cur.get(b) is not None:
            spreads[f"{a}-{b}"] = round((cur[a] - cur[b]) * 100, 1)   # bp

    out = {"as_of": datetime.now().strftime("%Y-%m-%d %H:%M"),
           "source": f"stooq 일별 {n_stooq}국" + (f" · FRED/OECD 폴백 {n_fred}국" if n_fred else "") + (f" · 직전값 유지 {n_stale}국" if n_stale else ""),
           "unit_note": "수익률 % · 변화는 bp(1bp=0.01%p) · 스프레드는 독일 분트(유로존 벤치마크) 대비 bp",
           "countries": countries, "spreads": spreads, "series": series}
    if not countries:
        print("전 국가 수집 실패 — 기존 DB 유지"); return 1
    OUT.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    print("gbonds 갱신:", " ".join(f'{c["name"]}={c.get("cur")}' for c in countries), "| 스프레드(bp):", spreads)
    return 0

if __name__ == "__main__":
    sys.exit(main())
