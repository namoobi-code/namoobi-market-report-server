#!/usr/bin/env python3
"""네이버 금융 리서치 6개 게시판 장기(기본 365일) 스캔 — NH·삼성·한투·현대차 존재 확인용.
사용: python3 scripts/research_year.py [일수=365] [게시판당 최대페이지=999]
결과: data/db/research_year_scan.json + stdout 요약. 타깃 증권사 발견 시 즉시 로그.
"""
import json, re, sys, time, urllib.request
from datetime import datetime, timedelta
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DAYS = int(sys.argv[1]) if len(sys.argv) > 1 else 365
MAXP = int(sys.argv[2]) if len(sys.argv) > 2 else 999
CUTOFF = (datetime.now() - timedelta(days=DAYS)).strftime("%y.%m.%d")
TARGETS = ("NH투자증권", "삼성증권", "한국투자증권", "현대차증권")

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

def options(html):
    """페이지 내 모든 select 옵션 텍스트(증권사 드롭다운 존재 시 제공사 전체 목록)."""
    out = []
    for sel in re.findall(r"<select[^>]*>(.*?)</select>", html, re.S):
        opts = [TAG.sub("", o).strip() for o in re.findall(r"<option[^>]*>(.*?)</option>", sel, re.S)]
        opts = [o for o in opts if o and not o.isdigit()]
        if opts: out.append(opts)
    return out

def scan(board, path):
    firms, oldest, newest, hits = {}, None, None, []
    opts = None
    p = 0
    for p in range(1, MAXP + 1):
        try: html = fetch(f"https://finance.naver.com/research/{path}?&page={p}")
        except Exception as e:
            print(f"  ! p{p} {type(e).__name__} — 5초 대기 후 재시도"); time.sleep(5)
            try: html = fetch(f"https://finance.naver.com/research/{path}?&page={p}")
            except Exception: break
        if p == 1: opts = options(html)
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
            firms[broker] = firms.get(broker, 0) + 1
            if any(t in broker for t in TARGETS):
                hits.append([broker, d]); print(f"  ★ 타깃 발견: {broker} {d} (p{p})")
        if stop: break
        if p % 25 == 0: print(f"  … {board} p{p} ({newest}~{oldest})")
        time.sleep(0.3)
    return {"board": board, "pages": p, "date_range": [oldest, newest],
            "n_firms": len(firms), "firms": dict(sorted(firms.items(), key=lambda x: -x[1])),
            "target_hits": hits, "select_options": opts}

out = {"as_of": datetime.now().strftime("%Y-%m-%d %H:%M"), "days": DAYS, "cutoff": CUTOFF, "boards": []}
for board, path in BOARDS:
    print(f"[{board}] 스캔 시작 (cutoff {CUTOFF})")
    r = scan(board, path)
    out["boards"].append(r)
    print(f"[{board}] 완료: {r['pages']}p, {r['n_firms']}개사, 타깃 {len(r['target_hits'])}건, 범위 {r['date_range']}")

total = {}
for b in out["boards"]:
    for k, v in b["firms"].items(): total[k] = total.get(k, 0) + v
out["total_firms"] = dict(sorted(total.items(), key=lambda x: -x[1]))
out["target_summary"] = {t: sum(1 for b in out["boards"] for h in b["target_hits"] if t in h[0]) for t in TARGETS}
(BASE / "data" / "db" / "research_year_scan.json").write_text(
    json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print("\n== 타깃 4사 등장 건수 ==")
for t, n in out["target_summary"].items(): print(f"  {t}: {n}")
print("saved: data/db/research_year_scan.json")
