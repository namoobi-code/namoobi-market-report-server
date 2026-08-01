#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
margin_debt.py — 미국 신용잔고(FINRA Margin Debt) 월간 + 증가율(YoY) + S&P500 월봉

배경(기사 '미국 주식시장 1차 경계신호'): 신용잔고 YoY 증가율은 과열 지표 —
  고점(2000년 72%·2007년 58%·2021년 63%) 도달 후 꺾이면 0~9개월 내 대세 하락 선행.
  2026년 5월 54%(5년 최고) → 6월 49% 하락 전환이 기사 포인트.

소스(실측 2026-08-01):
  FINRA https://www.finra.org/sites/default/files/2021-03/margin-statistics.xlsx
    — 경로는 2021-03 이지만 파일은 매월 제자리 갱신(최신 2026-06 확인) · 1997-01~ 풀 히스토리
  S&P500 월봉 = Yahoo ^GSPC v8 chart (30y)

산출: data/db/margin_debt.json {"asof","t":[YYYY-MM],"debit":[백만$],"yoy":[%],"spx":{"t":[],"v":[]}}
cron: 20 7 * * *  (월 1회 갱신 파일이라 매일 체크로 충분)
"""
import json, re, zipfile, io, urllib.request
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DB   = BASE / "data" / "db"
OUT  = DB / "margin_debt.json"
URL  = "https://www.finra.org/sites/default/files/2021-03/margin-statistics.xlsx"

def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (namoobi)"})
    with urllib.request.urlopen(req, timeout=40) as r:
        return r.read()

def parse_xlsx(raw):
    z = zipfile.ZipFile(io.BytesIO(raw))
    xml = z.read("xl/worksheets/sheet1.xml").decode("utf-8", "ignore")
    rows = re.findall(r"<row[^>]*>(.*?)</row>", xml, re.S)
    pat = re.compile(r'<c r="([A-Z]+)\d+"[^>]*>(?:<is><t>([^<]*)</t></is>|<v>([^<]*)</v>)?')
    out = {}
    for r in rows[1:]:
        c = {}
        for m in pat.finditer(r):
            col, ist, v = m.groups()
            c[col] = ist if ist is not None else v
        ym, debit = c.get("A"), c.get("B")
        if ym and debit and re.fullmatch(r"\d{4}-\d{2}", str(ym)):
            out[str(ym)] = float(debit)
    return out   # {YYYY-MM: 백만$}

def spx_monthly():
    try:
        j = json.loads(_get("https://query1.finance.yahoo.com/v8/finance/chart/%5EGSPC?range=30y&interval=1mo"))
        res = j["chart"]["result"][0]
        ts = res["timestamp"]; cl = res["indicators"]["quote"][0]["close"]
        t, v = [], []
        for k, c in zip(ts, cl):
            if c is None: continue
            t.append(datetime.utcfromtimestamp(k).strftime("%Y-%m")); v.append(round(c, 2))
        return {"t": t, "v": v}
    except Exception as e:
        print("  [warn] S&P500 월봉 실패:", e)
        return {"t": [], "v": []}

def main():
    d = parse_xlsx(_get(URL))
    ts = sorted(d)
    debit = [d[k] for k in ts]
    yoy = []
    for i, k in enumerate(ts):
        y, m = k.split("-")
        prev = f"{int(y)-1}-{m}"
        yoy.append(round((d[k]/d[prev]-1)*100, 1) if prev in d and d[prev] else None)
    spx = spx_monthly()
    DB.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "asof": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "src": "FINRA Margin Statistics(xlsx, 매월 제자리 갱신·1997~) · S&P500=Yahoo ^GSPC 월봉",
        "t": ts, "debit": debit, "yoy": yoy, "spx": spx}, ensure_ascii=False), encoding="utf-8")
    print(f"[margin_debt] ✅ {len(ts)}개월 · 최신 {ts[-1]} 잔고 ${debit[-1]/1e6:.2f}조 · YoY {yoy[-1]}% · SPX {len(spx['t'])}개월")

if __name__ == "__main__":
    main()
