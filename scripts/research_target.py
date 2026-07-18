#!/usr/bin/env python3
"""네이버 리서치 증권사 필터 검색 — NH·삼성·한투·현대차 제공 여부 확정.
각 게시판의 증권사 드롭다운(option value=brokerCode)을 파싱해
타깃 4사 코드로 필터 검색, 최신 리포트 날짜를 뽑는다. (요청 ~30건, 수십 초)
사용: python3 scripts/research_target.py
"""
import json, re, time, urllib.request
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
TARGETS = ["NH투자증권", "삼성증권", "한국투자증권", "현대차증권"]

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

def selects(html):
    """{select name: {label: value}}"""
    out = {}
    for name, body in re.findall(r'<select[^>]*name="([^"]+)"[^>]*>(.*?)</select>', html, re.S):
        opts = {}
        for val, lab in re.findall(r'<option[^>]*value="([^"]*)"[^>]*>(.*?)</option>', body, re.S):
            lab = TAG.sub("", lab).strip()
            if lab: opts[lab] = val
        out[name] = opts
    return out

def rows(html):
    """[(broker, date), ...]"""
    got = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S):
        if "_read.naver?nid=" not in tr: continue
        cells = [TAG.sub("", c).replace("&nbsp;", " ").strip()
                 for c in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
        di = [i for i, c in enumerate(cells) if DATE.match(c)]
        if not di: continue
        broker = next((cells[j] for j in range(di[0]-1, -1, -1) if cells[j]), "?")
        got.append((broker, cells[di[0]]))
    return got

out = {"as_of": datetime.now().strftime("%Y-%m-%d %H:%M"), "boards": []}
for board, path in BOARDS:
    url0 = f"https://finance.naver.com/research/{path}"
    html = fetch(url0)
    sel = selects(html)
    # 증권사 드롭다운 찾기: 옵션 라벨에 '증권'이 여럿 포함된 select
    bname, bopts = None, {}
    for name, opts in sel.items():
        if sum("증권" in k for k in opts) >= 5: bname, bopts = name, opts; break
    rec = {"board": board, "select_name": bname, "n_options": len(bopts),
           "targets": {}, "in_dropdown": {t: (t in bopts) for t in TARGETS}}
    for t in TARGETS:
        if t not in bopts:
            rec["targets"][t] = {"in_dropdown": False}; continue
        code = bopts[t]
        h = fetch(f"{url0}?searchType=brokerCode&{bname}={code}")
        rs = rows(h)
        rec["targets"][t] = {"in_dropdown": True, "code": code, "n_first_page": len(rs),
                             "latest": rs[0][1] if rs else None,
                             "sample": rs[:3]}
        time.sleep(0.3)
    out["boards"].append(rec)
    tgt = {t: (v.get("latest") or ("없음" if v.get("in_dropdown") else "드롭다운에 없음")) for t, v in rec["targets"].items()}
    print(f"[{board}] 드롭다운 {len(bopts)}개사 | " + " · ".join(f"{t}:{v}" for t, v in tgt.items()))

# 드롭다운 전체 목록도 저장(마지막 게시판 기준)
out["dropdown_all"] = sorted(bopts.keys()) if bopts else []
(BASE / "data" / "db" / "research_target_scan.json").write_text(
    json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print("\nsaved: data/db/research_target_scan.json")
