#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_gbonds.py — 3.1.1 「주요국 10년 국채금리」 서버 수집 (2026-09-13 신설 · 사용자 요청: 3.1.1 에 국가별 채권수익률 모아서)

  출력: data/db/gbonds.json  → 홈피 3.1.1 패널(app.js) + 보고서 gen_gbonds_chart.py(/api/db/gbonds 회수) 가 같은 데이터를 쓴다.
  대상 11개국: 미국·독일·프랑스·이탈리아·스페인·영국·일본·한국·중국·호주·캐나다 (10년물 벤치마크)

  ⚠ 2026-09-13 실측: stooq 는 JS 브라우저 검증(proof-of-work)을 걸어 curl/python 요청은 IP 불문 HTML 로 튕긴다
     (한도·UA 문제가 아님) → stooq 를 버리고 **각국 공식기관 일별 CSV/API** 로 교체.
  1순위(official · 일별):
     US FRED DGS10 · DE 분데스방크 BBSIS(10년 만기 Bund 수익률) · GB 영란은행 IUDMNPY · JP 재무성 jgbcme_all.csv(10Y 열)
     KR 한국은행 ECOS 817Y002/010210000(국고채10년) — ecos.key 없으면 sample 키(호출당 ≤10건 → 최근 12일만 받고 직전 DB 와 합쳐 누적)
     AU RBA F2 FCMYGBAG10D · CA 캐나다은행 Valet BD.CDN.10YR.DQ.YLD
  1-b순위(quote · 최신 1점): FR·IT·ES·CN 은 공식 무키 일별 CSV 가 없어 CNBC 시세 JSON(FR10Y-FR 등) 최신값 1점을 받고
     직전 DB 시계열과 합쳐 누적한다(클라우드 프록시에서는 403 — 서버에서 되는지 실행 로그로 확인).
  2순위 = FRED 월별 OECD 장기금리 IRLTLT01<CC>M156N — freq 'monthly' 표기(중국은 FRED 미제공).
  3순위 = 직전 DB 값 carry-forward(freq 뒤에 '(stale)').
  스키마: {"as_of","source","countries":[{cc,name,cur,date,d1,w1,m1,m3,m6,y1,freq,src}],"spreads":{...bp},"series":{cc:[["YYYY-MM-DD",v],..]}}
  · 변화 단위는 **bp**(수익률은 % 등락률이 아니라 bp 차이로 보는 것이 관행), series 는 최근 3년(일별 ≤ 800점)만 저장(번들 비대화 방지).
  · 새 소스 점은 항상 직전 DB 시계열과 날짜 union 하므로, 첫 회는 FRED 월별 이력 + 이후 일별 점이 섞여 쌓인다(정상).
  cron: 매일 05:25·15:25 KST (06:00 보고서가 당일 새벽 수집본을 쓴다).  ⚠ 추정 금지 — 실측·폴백·stale 만.
"""
import json, csv, io, os, sys, urllib.request, urllib.error
from datetime import datetime, timedelta
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DB = BASE / "data" / "db"; DB.mkdir(parents=True, exist_ok=True)
OUT = DB / "gbonds.json"

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)", "Accept": "*/*"}
KEEP_DAYS = 3 * 365 + 10

def _get(url, timeout=30, headers=None):
    req = urllib.request.Request(url, headers=headers or UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="replace")

def _key(name):
    try: return (BASE / name).read_text().strip()
    except Exception: return ""

def _since(days=KEEP_DAYS):
    return datetime.now() - timedelta(days=days)

# ───────── 공식기관 일별 소스 ─────────
def fred(series_id):
    k = _key("fred.key")
    try:
        if k:
            j = json.loads(_get("https://api.stlouisfed.org/fred/series/observations"
                                f"?series_id={series_id}&api_key={k}&file_type=json"))
            return [(o["date"], float(o["value"])) for o in j.get("observations", []) if o.get("value") not in (".", "", None)]
        rows = list(csv.reader(io.StringIO(_get(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"))))
        return [(d, float(v)) for d, v in rows[1:] if v not in (".", "")]
    except Exception as e:
        print(f"  FRED {series_id}: {type(e).__name__}"); return None

def src_us():
    return fred("DGS10")

def src_de():
    """분데스방크 BBSIS 일별(세미콜론 CSV · 소수점 콤마): '2026-09-11;3,53;'"""
    txt = _get("https://api.statistiken.bundesbank.de/rest/data/BBSIS/D.I.ZAR.ZI.EUR.S1311.B.A604.R10XX.R.A.A._Z._Z.A"
               f"?format=csv&startPeriod={_since().strftime('%Y-%m-%d')}")
    out = []
    for line in txt.splitlines():
        p = line.split(";")
        if len(p) >= 2 and len(p[0]) == 10 and p[0][4] == "-":
            try: out.append((p[0], float(p[1].replace(",", "."))))
            except ValueError: pass
    return out

def src_gb():
    """영란은행 IUDMNPY(10년 명목 par 수익률) 'DATE,IUDMNPY / 01 Sep 2026,5.1333'"""
    txt = _get("https://www.bankofengland.co.uk/boeapps/database/_iadb-fromshowcolumns.asp?csv.x=yes"
               f"&Datefrom={_since().strftime('%d/%b/%Y')}&Dateto=now&SeriesCodes=IUDMNPY&CSVF=TN&UsingCodes=Y&VPD=Y&VFD=N")
    out = []
    for row in csv.reader(io.StringIO(txt)):
        if len(row) >= 2 and row[0] != "DATE":
            try: out.append((datetime.strptime(row[0], "%d %b %Y").strftime("%Y-%m-%d"), float(row[1])))
            except ValueError: pass
    return out

def src_jp():
    """일본 재무성 'Date,1Y,…,10Y,…' (2026/8/31,…). historical/jgbcme_all.csv 는 전월까지라 당월분 jgbcme.csv 를 합친다."""
    out, cutoff = {}, _since()
    for u in ("https://www.mof.go.jp/english/policy/jgbs/reference/interest_rate/historical/jgbcme_all.csv",
              "https://www.mof.go.jp/english/policy/jgbs/reference/interest_rate/jgbcme.csv"):
        try: rows = list(csv.reader(io.StringIO(_get(u))))
        except Exception as e:
            print(f"  MOF {u.rsplit('/',1)[-1]}: {type(e).__name__}"); continue
        hdr = next((r for r in rows if r and r[0] == "Date"), None)
        if not hdr: continue
        i10 = hdr.index("10Y")
        for r in rows:
            try:
                d = datetime.strptime(r[0], "%Y/%m/%d")
                if d >= cutoff: out[d.strftime("%Y-%m-%d")] = float(r[i10])
            except (ValueError, IndexError): pass
    return sorted(out.items())

def src_kr():
    """한국은행 ECOS 817Y002(시장금리·일별) 010210000=국고채10년. ecos.key 없으면 sample 키(≤10건) 로 최근 12일."""
    k = _key("ecos.key")
    end = datetime.now()
    start = _since() if k else end - timedelta(days=12)
    key, n = (k, 2000) if k else ("sample", 10)
    j = json.loads(_get(f"https://ecos.bok.or.kr/api/StatisticSearch/{key}/json/kr/1/{n}/817Y002/D/"
                        f"{start.strftime('%Y%m%d')}/{end.strftime('%Y%m%d')}/010210000"))
    rows = j.get("StatisticSearch", {}).get("row", [])
    if not rows: raise RuntimeError(str(j.get("RESULT", j))[:120])
    out = []
    for r in rows:
        try: out.append((datetime.strptime(r["TIME"], "%Y%m%d").strftime("%Y-%m-%d"), float(r["DATA_VALUE"])))
        except (ValueError, KeyError): pass
    return out

def src_au():
    """RBA F2 f2-data.csv: 'Series ID,FCMYGBAG2D,…,FCMYGBAG10D,…' 이후 '09-Sep-2026,4.835,…'"""
    txt = _get("https://www.rba.gov.au/statistics/tables/csv/f2-data.csv")
    rows = list(csv.reader(io.StringIO(txt.lstrip("﻿"))))
    hdr = next(r for r in rows if r and r[0] == "Series ID"); i10 = hdr.index("FCMYGBAG10D"); cutoff = _since()
    out = []
    for r in rows:
        try:
            d = datetime.strptime(r[0], "%d-%b-%Y")
            if d >= cutoff and r[i10]: out.append((d.strftime("%Y-%m-%d"), float(r[i10])))
        except (ValueError, IndexError): pass
    return out

def src_ca():
    """캐나다은행 Valet BD.CDN.10YR.DQ.YLD csv: '"2026-09-10","3.94"'"""
    txt = _get(f"https://www.bankofcanada.ca/valet/observations/BD.CDN.10YR.DQ.YLD/csv?start_date={_since().strftime('%Y-%m-%d')}")
    out = []
    for row in csv.reader(io.StringIO(txt)):
        if len(row) >= 2 and len(row[0]) == 10 and row[0][4] == "-":
            try: out.append((row[0], float(row[1])))
            except ValueError: pass
    return out

_CNBC = {}
def src_cnbc(sym):
    """CNBC 시세 JSON — 최신 1점만(누적은 직전 DB union). 첫 호출에 4국 한꺼번에 받아 캐시."""
    if not _CNBC:
        syms = "FR10Y-FR|IT10Y-IT|ES10Y-ES|CN10Y-CN"
        j = json.loads(_get("https://quote.cnbc.com/quote-html-webservice/restQuote/symbolType/symbol"
                            f"?symbols={syms}&requestMethod=itv&noform=1&partnerId=2&fund=1&exthrs=1&output=json",
                            headers={**UA, "Accept": "application/json"}))
        for q in j.get("FormattedQuoteResult", {}).get("FormattedQuote", []):
            try:
                lt = q.get("last_time") or ""                       # '2026-09-12T16:59:59.000-0400'
                _CNBC[q["symbol"]] = (lt[:10], float(str(q["last"]).replace("%", "").replace(",", "")))
            except (ValueError, KeyError, TypeError): pass
    p = _CNBC.get(sym)
    return [p] if p and len(p[0]) == 10 else None

# (cc, 한글명, 1순위 수집함수, 1순위 라벨, FRED 폴백 시리즈)
ROWS = [
    ("US", "미국",     src_us,                          "FRED DGS10",            None),
    ("DE", "독일",     src_de,                          "Bundesbank BBSIS 10Y",  "IRLTLT01DEM156N"),
    ("FR", "프랑스",   lambda: src_cnbc("FR10Y-FR"),    "CNBC FR10Y",            "IRLTLT01FRM156N"),
    ("IT", "이탈리아", lambda: src_cnbc("IT10Y-IT"),    "CNBC IT10Y",            "IRLTLT01ITM156N"),
    ("ES", "스페인",   lambda: src_cnbc("ES10Y-ES"),    "CNBC ES10Y",            "IRLTLT01ESM156N"),
    ("GB", "영국",     src_gb,                          "BoE IUDMNPY",           "IRLTLT01GBM156N"),
    ("JP", "일본",     src_jp,                          "MOF JGB 10Y",           "IRLTLT01JPM156N"),
    ("KR", "한국",     src_kr,                          "ECOS 국고채10년",        "IRLTLT01KRM156N"),
    ("CN", "중국",     lambda: src_cnbc("CN10Y-CN"),    "CNBC CN10Y",            None),
    ("AU", "호주",     src_au,                          "RBA FCMYGBAG10D",       "IRLTLT01AUM156N"),
    ("CA", "캐나다",   src_ca,                          "BoC 10YR",              "IRLTLT01CAM156N"),
]

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
    cutoff = _since().strftime("%Y-%m-%d")

    countries, series, n_off, n_fred, n_stale = [], {}, 0, 0, 0
    for cc, name, fn, label, fid in ROWS:
        pts, freq, src = None, "daily", label
        try:
            pts = fn()
            if not pts: print(f"  {label}: 빈 응답")
        except Exception as e:
            print(f"  {label}: {type(e).__name__} {str(e)[:80]}")
        if pts: n_off += 1
        elif fid:
            pts = fred(fid)
            if pts:
                freq, src = "monthly", f"FRED {fid}"; n_fred += 1
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
        # 직전 시계열과 날짜 union — 결측·짧은 창(ECOS sample·CNBC 1점)을 직전 DB 로 메워 누적한다
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
           "source": f"공식기관 일별 {n_off}국" + (f" · FRED/OECD 월별 폴백 {n_fred}국" if n_fred else "") + (f" · 직전값 유지 {n_stale}국" if n_stale else ""),
           "unit_note": "수익률 % · 변화는 bp(1bp=0.01%p) · 스프레드는 독일 분트(유로존 벤치마크) 대비 bp",
           "countries": countries, "spreads": spreads, "series": series}
    if not countries:
        print("전 국가 수집 실패 — 기존 DB 유지"); return 1
    OUT.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    print("gbonds 갱신:", " ".join(f'{c["name"]}={c.get("cur")}' for c in countries), "| 스프레드(bp):", spreads)
    return 0

if __name__ == "__main__":
    sys.exit(main())
