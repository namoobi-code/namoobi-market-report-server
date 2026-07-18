#!/usr/bin/env python3
"""증권사 리서치 서버 수집 (req12) — 네이버 금융 리서치 게시판.

시황(market_info)·투자정보(invest)·종목분석(company) 목록에서
증권사별 최신 리포트(제목·PDF 링크·날짜)를 모아 DB화한다.
보고서(7장)와 홈피가 이 목록에서 대표 리포트+링크를 바로 쓴다.

증권사 공식 리서치 포털 링크도 함께 담는다 (req12: 둘 다).
"""
import json, re, urllib.request
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DB   = BASE / "data" / "db"

LISTS = [
    ("시황",   "https://finance.naver.com/research/market_info_list.naver?&page={p}", "market_info_read"),
    ("투자전략", "https://finance.naver.com/research/invest_list.naver?&page={p}",      "invest_read"),
    ("종목분석", "https://finance.naver.com/research/company_list.naver?&page={p}",     "company_read"),
]

# 보고서 7장에서 다루는 증권사 + 공식 리서치 페이지
OFFICIAL = {
    "KB증권":     "https://rc.kbsec.com/report/reportList.able",
    "NH투자증권":  "https://www.nhqv.com/research",
    "삼성증권":    "https://www.samsungpop.com/mbw/research.do",
    "미래에셋증권": "https://securities.miraeasset.com/bbs/board/message/list.do?categoryId=1521",
    "한국투자증권": "https://research.truefriend.com",
    "신한투자증권": "https://bbs2.shinhaninvest.com/bbs/report",
    "키움증권":    "https://invest.kiwoom.com/inv/research",
    "메리츠증권":  "https://home.imeritz.com/include/resource/research/rsList.do",
    "하나증권":    "https://www.hanaw.com/main/research/research/list.cmd",
    "교보증권":    "https://www.iprovest.com/weblogic/RSDownloadServlet",
    "유안타증권":  "https://www.myasset.com/myasset/research/rs_list.cmd",
    "한화투자증권": "https://www.hanwhawm.com/main/research/main/list.cmd",
    "대신증권":    "https://money2.daishin.com/e5/mboard/ptype_basic/basic_research/DW_Basic_List.aspx",
    "현대차증권":  "https://www.hmsec.com/mn/research/research_list.do",
    "IBK투자증권": "https://www.ibks.com/research",
    "DB금융투자":  "https://www.db-fi.com/research",
    "유진투자증권": "https://www.eugenefn.com/research",
    "SK증권":     "https://www.sks.co.kr/research",
    "다올투자증권": "https://www.daolsecurities.com/research",
    "LS증권":     "https://www.ls-sec.co.kr/research",
}

ROW = re.compile(
    r'<a href="((?:market_info|invest|company)_read\.naver\?nid=\d+[^"]*)"[^>]*>([^<]+)</a>\s*</td>\s*'
    r'(?:<td>([^<]*)</td>\s*)?<td>([^<]*)</td>\s*<td class="file">\s*'
    r'(?:<a href="(https://stock\.pstatic\.net[^"]+)")?', re.S)

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.read().decode("euc-kr", errors="replace")

def main():
    per = {}          # 증권사 → [리포트,...]
    for cat, tpl, _tag in LISTS:
        for p in (1, 2):
            try:
                html = fetch(tpl.format(p=p))
            except Exception as e:
                print(f"{cat} p{p} 실패: {type(e).__name__}")
                continue
            # 표 행 단위 파싱 (제목 td → 종목분석은 종목 td가 하나 더 → 증권사 td → 첨부 td → 날짜)
            rows = re.findall(
                r'<td[^>]*><a href="((?:market_info|invest|company)_read\.naver[^"]+)"[^>]*>([^<]+)</a></td>\s*'
                r'(?:<td[^>]*>(?:<a[^>]*>)?([^<]*)(?:</a>)?</td>\s*)?'
                r'<td>([^<]+)</td>\s*<td class="file">(?:\s*<a href="([^"]+)")?', html)
            for lk, title, extra, broker, pdf in rows:
                broker = broker.strip()
                if not broker:
                    continue
                item = {"cat": cat, "title": re.sub(r"\s+", " ", title).strip()[:80],
                        "stock": (extra or "").strip() or None,
                        "url": "https://finance.naver.com/research/" + lk.replace("&amp;", "&"),
                        "pdf": pdf or None}
                per.setdefault(broker, []).append(item)
    # 증권사별 최신 5건만
    firms = []
    for broker, items in per.items():
        firms.append({"broker": broker,
                      "official": OFFICIAL.get(broker, ""),
                      "naver": "https://finance.naver.com/research/",
                      "reports": items[:5]})
    firms.sort(key=lambda f: -len(per[f["broker"]]))
    out = {"firms": firms,
           "as_of": datetime.now().strftime("%Y-%m-%d %H:%M"),
           "marker": datetime.now().strftime("%Y-%m-%d"),
           "desc": "네이버 금융 리서치(시황·투자전략·종목분석 각 2p) — 증권사별 최신 리포트·PDF·공식 리서치 링크"}
    (DB / "broker_reports.json").write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    print(f"broker_reports: {len(firms)}개사 · 총 {sum(len(f['reports']) for f in firms)}건")
    for f in firms[:6]:
        print(f"  {f['broker']}: {len(f['reports'])}건 · 예: {f['reports'][0]['title'][:36]}")

if __name__ == "__main__":
    main()
