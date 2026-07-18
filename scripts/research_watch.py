#!/usr/bin/env python3
"""증권사 리서치 서버 수집 v2 (req10·12) — 네이버 금융 리서치 6개 게시판.

시황·투자전략·종목분석·산업분석·경제분석·채권분석 목록에서
① 증권사별 최신 리포트(제목·링크·PDF·작성일)  ② 최근 2일치 전체 모음(카테고리별)
을 DB화한다. 최근 2일치는 본문 첫 문장을 짧게 발췌해 '간단요약'으로 담는다.

보고서 7장·홈피가 이 DB를 그대로 쓴다 — 실행 때 재조사하지 않는다.
"""
import json, re, html, urllib.request
from datetime import datetime, timedelta
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DB   = BASE / "data" / "db"
NV   = "https://finance.naver.com/research/"

LISTS = [
    ("시황",     "market_info_list.naver"),
    ("투자전략",  "invest_list.naver"),
    ("종목분석",  "company_list.naver"),
    ("산업분석",  "industry_list.naver"),
    ("경제분석",  "economy_list.naver"),
    ("채권분석",  "debenture_list.naver"),
]

OFFICIAL = {
    "KB증권": "https://rc.kbsec.com/today/index.able",
    "NH투자증권": "https://m.nhqv.com/research/boardList?rshPprDitCd=02",
    "삼성증권": "https://www.samsungpop.com/mbw/research.do",
    "미래에셋증권": "https://securities.miraeasset.com/bbs/board/message/list.do?categoryId=1521",
    "한국투자증권": "https://research.truefriend.com",
    "신한투자증권": "https://bbs2.shinhaninvest.com/bbs/report",
    "키움증권": "https://invest.kiwoom.com/inv/research",
    "메리츠증권": "https://home.imeritz.com/include/resource/research/rsList.do",
    "하나증권": "https://www.hanaw.com/main/research/research/list.cmd",
    "교보증권": "https://www.iprovest.com",
    "유안타증권": "https://www.myasset.com/myasset/research/rs_list.cmd",
    "한화투자증권": "https://www.hanwhawm.com/main/research/main/list.cmd",
    "대신증권": "https://money2.daishin.com/e5/mboard/ptype_basic/basic_research/DW_Basic_List.aspx",
    "현대차증권": "https://www.hmsec.com/mn/research/research_list.do",
    "IBK투자증권": "https://www.ibks.com",
    "DB금융투자": "https://www.db-fi.com",
    "유진투자증권": "https://www.eugenefn.com",
    "SK증권": "https://www.sks.co.kr",
    "다올투자증권": "https://www.daolsecurities.com",
    "iM증권": "https://www.imfnsec.com",
    "DS투자증권": "https://www.ds-sec.co.kr",
    "LS증권": "https://www.ls-sec.co.kr",
}

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.read().decode("euc-kr", errors="replace")

# 행: 제목a → (종목분석·산업분석은 앞에 종목/산업 td) → 증권사 td → 첨부 td → 날짜 td
ROW = re.compile(
    r'<td[^>]*><a href="((?:market_info|invest|company|industry|economy|debenture)_read\.naver[^"]+)"[^>]*>([^<]+)</a></td>\s*'
    r'(?:<td[^>]*>(?:<a[^>]*>)?([^<]*)(?:</a>)?</td>\s*)?'
    r'<td>([^<]+)</td>\s*<td class="file">(?:\s*<a href="([^"]+)")?[^<]*(?:<img[^>]*>)?\s*</a>?\s*</td>\s*'
    r'<td[^>]*>\s*(\d{2}\.\d{2}\.\d{2})', re.S)

def summary_of(read_url):
    """리포트 상세 페이지 본문 첫 부분 발췌 (간단요약)."""
    try:
        h = fetch(read_url)
        m = re.search(r'<td class="view_cnt">(.*?)</td>', h, re.S)
        if not m:
            return ""
        t = re.sub(r"<[^>]+>", " ", m.group(1))
        t = html.unescape(re.sub(r"\s+", " ", t)).strip()
        return t[:120]
    except Exception:
        return ""

def main():
    per, recent = {}, {c: [] for c, _ in LISTS}
    d2 = (datetime.now() - timedelta(days=2)).strftime("%y.%m.%d")
    fetch_budget = 40                                # 요약용 상세 조회 상한

    for cat, page in LISTS:
        for p in (1, 2):
            try:
                h = fetch(f"{NV}{page}?&page={p}")
            except Exception as e:
                print(f"{cat} p{p} 실패: {type(e).__name__}")
                continue
            for lk, title, extra, broker, pdf, dt in ROW.findall(h):
                broker = broker.strip()
                if not broker:
                    continue
                item = {"cat": cat, "title": html.unescape(re.sub(r"\s+", " ", title)).strip()[:80],
                        "stock": html.unescape((extra or "").strip()) or None,
                        "url": NV + lk.replace("&amp;", "&"),
                        "pdf": pdf or None,
                        "date": "20" + dt.replace(".", "-"),
                        "broker": broker}
                per.setdefault(broker, []).append(item)
                if dt >= d2:
                    recent[cat].append(item)

    # 최근 2일치엔 간단요약 (예산 내)
    for cat in recent:
        for it in recent[cat]:
            if fetch_budget <= 0:
                break
            it["summary"] = summary_of(it["url"])
            fetch_budget -= 1

    firms = [{"broker": b, "official": OFFICIAL.get(b, ""), "naver": NV,
              "reports": items[:5]} for b, items in per.items()]
    firms.sort(key=lambda f: -len(per[f["broker"]]))

    out = {"firms": firms,
           "recent": recent,
           "as_of": datetime.now().strftime("%Y-%m-%d %H:%M"),
           "marker": datetime.now().strftime("%Y-%m-%d"),
           "desc": "네이버 금융 리서치 6개 게시판(각 2p) — 증권사별 최신 리포트 + 최근 2일 전체 모음(요약 포함)"}
    (DB / "broker_reports.json").write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    n_rec = sum(len(v) for v in recent.values())
    print(f"broker_reports v2: {len(firms)}개사 · 최근2일 {n_rec}건 "
          f"({', '.join(f'{c} {len(v)}' for c, v in recent.items())})")

if __name__ == "__main__":
    main()
