#!/usr/bin/env python3
"""증권사 리서치 서버 수집 v3 (req10·12) — 네이버 증권 리서치 6개 게시판 (JSON API).

(v3 · 2026-09-22 재발방지) 네이버가 finance.naver.com/research/*_list.naver 를 stock.naver.com(Next.js SPA)
으로 이관해 구 HTML 정규식 파서가 2026-09-16 부터 6일 연속 0건을 냈다(보고서 7장 key_reports·홈피 리서치 패널
공란 — 사용자 미인지). 새 소스 = 모바일 JSON API `https://m.stock.naver.com/api/research/<cat>?page=N&pageSize=M`
(cat: market·invest·company·industry·economy·debenture, 로그인 無) — 목록 [{researchId,title,brokerName,writeDate,
endUrl,itemName?}], 상세 `/api/research/<cat>/<id>` → researchContent{content(HTML),attachUrl(PDF)}.
출력 스키마(firms/recent/as_of/marker)는 v2 와 동일해 merge.py·app.js 변경 없음.
⚠ 0건 가드: 6게시판 합계 0건이면 기존 DB 를 덮어쓰지 않고 stderr 경고 + exit 2 (구조 재변경 조기 감지).

시황·투자전략·종목분석·산업분석·경제분석·채권분석 목록에서
① 증권사별 최신 리포트(제목·링크·PDF·작성일)  ② 최근 2일치 전체 모음(카테고리별)
을 DB화한다. 최근 2일치는 본문 첫 부분을 짧게 발췌해 '간단요약'으로 담는다.

보고서 7장·홈피가 이 DB를 그대로 쓴다 — 실행 때 재조사하지 않는다.
"""
import json, re, html, sys, urllib.request
from datetime import datetime, timedelta
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DB   = BASE / "data" / "db"
API  = "https://m.stock.naver.com/api/research/"
WEB  = "https://m.stock.naver.com/research/"

LISTS = [
    ("시황",     "market"),
    ("투자전략",  "invest"),
    ("종목분석",  "company"),
    ("산업분석",  "industry"),
    ("경제분석",  "economy"),
    ("채권분석",  "debenture"),
]
PAGE_SIZE = 30     # 게시판당 1페이지 30건 (구 2p×20 과 동급)

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

def fetch_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode("utf-8", errors="replace"))

def detail(cat_key, rid):
    """상세 API → (간단요약, PDF URL). 실패 시 ("", None) — 비차단."""
    try:
        d = fetch_json(f"{API}{cat_key}/{rid}")
        c = (d or {}).get("researchContent") or {}
        t = re.sub(r"<[^>]+>", " ", c.get("content") or "")
        t = html.unescape(re.sub(r"\s+", " ", t)).strip()
        return t[:120], (c.get("attachUrl") or None)
    except Exception:
        return "", None

def pdf_summary(pdf_url):
    """(req6 2026-07-19) PDF 1페이지에서 핵심 1줄 추출 — 본문이 빈 리포트용 폴백.
    pdftotext(poppler) 사용, 실패 시 ""(비차단). 보일러플레이트(날짜·증권사명·URL 등) 줄은 건너뛴다."""
    import subprocess, tempfile, os
    if not pdf_url:
        return ""
    try:
        req = urllib.request.Request(pdf_url, headers={"User-Agent": "Mozilla/5.0"})
        data = urllib.request.urlopen(req, timeout=12).read(3 * 1024 * 1024)
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(data); tmp = f.name
        try:
            r = subprocess.run(["pdftotext", "-f", "1", "-l", "1", tmp, "-"],
                               capture_output=True, text=True, timeout=15)
            txt = r.stdout or ""
        finally:
            os.unlink(tmp)
        out = []
        for ln in txt.splitlines():
            s = re.sub(r"\s+", " ", ln).strip()
            if len(s) < 12:
                continue
            if re.search(r"(https?://|@|리서치센터|Research|Compliance|투자의견 및|20\d{2}[-./]\s?\d{1,2}[-./]\s?\d{1,2}\s*$)", s):
                continue
            out.append(s)
            if sum(len(x) for x in out) > 90:
                break
        return " ".join(out)[:110]
    except Exception:
        return ""

def main():
    per, recent = {}, {c: [] for c, _ in LISTS}
    d2 = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")
    fetch_budget = 40                                # 요약용 상세 조회 상한
    total_seen = 0

    for cat, key in LISTS:
        try:
            rows = fetch_json(f"{API}{key}?page=1&pageSize={PAGE_SIZE}")
        except Exception as e:
            print(f"{cat} 실패: {type(e).__name__} {e}")
            continue
        if isinstance(rows, dict):                   # 방어: {list:[...]} 형태로 바뀔 경우
            rows = rows.get("list") or rows.get("researchSummaries") or []
        for r in rows or []:
            broker = (r.get("brokerName") or "").strip()
            rid = r.get("researchId")
            if not broker or not rid:
                continue
            total_seen += 1
            dt = (r.get("writeDate") or "")[:10]     # YYYY-MM-DD
            item = {"cat": cat,
                    "title": html.unescape(re.sub(r"\s+", " ", r.get("title") or "")).strip()[:80],
                    "stock": (r.get("itemName") or None) if cat == "종목분석" else ((r.get("category") or None) if cat == "산업분석" else None),
                    "url": r.get("endUrl") or f"{WEB}{key}/{rid}",
                    "pdf": None,
                    "date": dt,
                    "broker": broker,
                    "_key": key, "_rid": rid, "_dt": dt}
            per.setdefault(broker, []).append(item)
            recent[cat].append(item)

    # (재발방지 가드) 전 게시판 0건 = 소스 구조 재변경 가능성 → 기존 DB 보존·경고 종료
    if total_seen == 0:
        sys.stderr.write("broker_reports v3: ⚠ 6게시판 합계 0건 — 네이버 리서치 API 구조 변경 의심, 기존 DB 유지(미갱신)\n")
        sys.exit(2)

    # (req6-fix 2026-07-19) '최근 2일' 창이 주말·휴장일엔 0건이 되는 문제 — 최신 리포트 일자까지 창을 내려서
    #   항상 '가장 최근 발행일 이후' 리포트는 포함한다(예: 일요일 실행 → 목요일 발행분 유지).
    _all_dt = [it["_dt"] for arr in recent.values() for it in arr if it["_dt"]]
    cutoff = min(d2, max(_all_dt)) if _all_dt else d2
    for cat in recent:
        recent[cat] = [it for it in recent[cat] if it["_dt"] >= cutoff]

    # 최근 2일치엔 간단요약 + PDF (예산 내) — 본문 비면 PDF 1페이지 추출 폴백
    for cat in recent:
        for it in recent[cat]:
            if fetch_budget <= 0:
                break
            s, pdf = detail(it["_key"], it["_rid"])
            it["pdf"] = pdf
            it["summary"] = s or pdf_summary(pdf)
            fetch_budget -= 1

    for arr in list(per.values()) + list(recent.values()):
        for it in arr:
            for k in ("_key", "_rid", "_dt"):
                it.pop(k, None)

    firms = [{"broker": b, "official": OFFICIAL.get(b, ""), "naver": WEB,
              "reports": items[:5]} for b, items in per.items()]
    firms.sort(key=lambda f: -len(per[f["broker"]]))

    out = {"firms": firms,
           "recent": recent,
           "as_of": datetime.now().strftime("%Y-%m-%d %H:%M"),
           "marker": datetime.now().strftime("%Y-%m-%d"),
           "desc": "네이버 증권 리서치 6개 게시판(m.stock.naver.com JSON API, 각 30건) — 증권사별 최신 리포트 + 최근 2일 전체 모음(요약 포함)"}
    (DB / "broker_reports.json").write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    n_rec = sum(len(v) for v in recent.values())
    print(f"broker_reports v3: {len(firms)}개사 · 최근2일 {n_rec}건 "
          f"({', '.join(f'{c} {len(v)}' for c, v in recent.items())})")

if __name__ == "__main__":
    main()
