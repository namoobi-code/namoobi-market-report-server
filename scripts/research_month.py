#!/usr/bin/env python3
"""네이버 금융 리서치 6개 게시판 한 달치 증권사 전수 스캔 (일회성).
결과: data/db/research_month_scan.json + stdout 요약.
사용: python3 scripts/research_month.py [일수, 기본 30]
"""
import json, re, sys, time, urllib.request
from datetime import datetime, timedelta
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DAYS = int(sys.argv[1]) if len(sys.argv) > 1 else 30
CUTOFF = (datetime.now() - timedelta(days=DAYS)).strftime("%y.%m.%d")

BOARDS = [
    ("시황",     "market_info_list.naver"),
    ("투자전략", "invest_list.naver"),
    ("종목분석", "company_list.naver"),
    ("산업분석", "industry_list.naver"),
    ("경제분석", "economy_list.naver"),
    ("채권분석", "debenture_list.naver"),
]
DATE = re.compile(r"^\d{2}\.\d{2}\.\d{2}$")
TAG  = re.compile(r"<[^>]+>")

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.read().decode("euc-kr", errors="replace")

def scan(board, path, max_pages=60):
    firms, oldest, newest, rows_n = {}, None, None, 0
    for p in range(1, max_pages + 1):
        html = fetch(f"https://finance.naver.com/research/{path}?&page={p}")
        stop = False
        for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S):
            if "_read.naver?nid=" not in tr: continue
            cells = [TAG.sub("", c).replace("&nbsp;", " ").strip()
                     for c in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
            dates = [i for i, c in enumerate(cells) if DATE.match(c)]
            if not dates: continue
            di = dates[0]; d = cells[di]
            broker = next((cells[j] for j in range(di - 1, -1, -1) if cells[j]), None)
            if not broker: continue
            newest = max(newest or d, d); oldest = min(oldest or d, d)
            if d < CUTOFF: stop = True; continue
            firms[broker] = firms.get(broker, 0) + 1; rows_n += 1
        if stop: break
        time.sleep(0.4)
    return {"board": board, "pages": p, "rows": rows_n,
            "date_range": [oldest, newest], "firms": firms}

out = {"as_of": datetime.now().strftime("%Y-%m-%d %H:%M"), "days": DAYS,
       "cutoff": CUTOFF, "boards": []}
for board, path in BOARDS:
    r = scan(board, path)
    out["boards"].append(r)
    print(f"[{board}] {r['pages']}p rows={r['rows']} range={r['date_range']} firms={len(r['firms'])}")

total = {}
for b in out["boards"]:
    for k, v in b["firms"].items(): total[k] = total.get(k, 0) + v
out["total_firms"] = dict(sorted(total.items(), key=lambda x: -x[1]))
(BASE / "data" / "db" / "research_month_scan.json").write_text(
    json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print("\n== 전체 등장 증권사 (건수순) ==")
for k, v in out["total_firms"].items(): print(f"  {k}: {v}")
print("\nsaved: data/db/research_month_scan.json")
