#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fetch_cn_export.py — 🇨🇳 K-브랜드 대중국 수출 선행지표 (2026-10-17 신설 · 이코노미스트 'K브랜드, 다시 중국으로' 커버)

왜: 중국 매출은 **통관(월) → 현지 판매 → 분기 공시** 순으로 드러난다. 통관이 실적 발표를 2~4개월 선행하므로
    '대중국 수출 YoY 전환'을 잡으면 중국 재진출 종목(아모레·LG생건·코스맥스·F&F·무신사 파트너 등)을 먼저 볼 수 있다.
어떻게: 관세청 tradedata.go.kr 무인증 POST — 수출입 실적 화면의 '품목별+국가별'(tradeKind ETS_MNK_1020000E).
    2026-10-17 브라우저 XHR 실측 캡처 페이로드:
      tradeKind=ETS_MNK_1020000E&priodKind=MON&priodFr=2026.01&priodTo=2026.08&statsBase=acptDd&ttwgTpcd=1000
      &selectPaging=1&showPagingLine=100&sortColumn=&sortOrder=&cntyNm=중국&hsSgnGrpCol=HS4_SGN&hsSgnWhrCol=HS4_SGN&hsSgn=3304
    ⚠ cntyNm 은 국가 **한글명**(코드 CN 아님 — 코드로 보내면 0건, 실측). 월별 조회는 **역년 1년 한도**라 연도별로 나눠 호출.
한계: 품목별이지 회사별이 아니다 — 3304 에는 아모레·LG생건·코스맥스·중소 브랜드가 섞인다. 품목 비중이 큰 중소형주일수록 신호가 선명.

산출: data/db/cn_export.json  { asof, months[], items[{th,nm,hs,note,exp[],tot[]}], }  exp=대중국(천$), tot=전세계(hs_invest 와 동일 산식)
cron: 50 8 * * *  (fetch_hs_invest 08:35 뒤 · 관세청 월 확정치는 익월 15일경)
"""
import json, re, time, urllib.request, urllib.parse
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "data" / "db" / "cn_export.json"
URL = "https://tradedata.go.kr/cts/hmpg/retrieveTrade.do"
H = {"Content-Type": "application/x-www-form-urlencoded", "User-Agent": "Mozilla/5.0",
     "Referer": "https://tradedata.go.kr/cts/index.do"}

# (테마, 품목, HS, 관련 종목 메모) — 기사 등장 업종 위주. 의류는 편물(61)·직물(62) 류 합산.
ITEMS = [
    ("K뷰티", "화장품(기초·색조)", ["3304"], "아모레퍼시픽·LG생활건강·코스맥스·한국콜마·에이피알 — 中 로컬 점유 57%(2025)와 정면 경쟁"),
    ("K뷰티", "헤어 제품", ["3305"], "LG생활건강·아모레퍼시픽"),
    ("K뷰티", "향수", ["3303"], "코스맥스·한국콜마(ODM)"),
    ("K뷰티", "미용기기", ["8543"], "에이피알·클래시스 — 中 '이성 소비' 프리미엄 기기"),
    ("K패션", "의류(편물·직물)", ["61", "62"], "F&F(MLB)·삼성물산패션(준지·빈폴)·LF(헤지스)·코오롱FnC·무신사(비상장)"),
    ("K패션", "가방·잡화", ["4202"], "F&F·더네이쳐홀딩스"),
    ("K패션", "신발", ["64"], "휠라홀딩스·화승엔터(OEM)"),
    ("K푸드", "라면(면류)", ["1902"], "농심·삼양식품·오뚜기"),
    ("K푸드", "소스류", ["2103"], "CJ제일제당·대상·삼양식품"),
    ("K푸드", "김", ["121221"], "동원F&B·CJ씨푸드"),
    ("K푸드", "음료", ["2202"], "롯데칠성·LG생활건강"),
    ("K푸드", "주류", ["2208"], "하이트진로·롯데칠성"),
]


def grpcol(hs):
    return {2: "HS2_SGN", 4: "HS4_SGN", 6: "HS6_SGN"}[len(hs)]


def fetch_year(hs, year, m_to, cnty):
    """한 역년 대중국 수출 {YYYY.MM: 천$} — 연도별 호출.
    ⚠ 서버 버그 실측(2026-10-17): 같은 해 안의 범위(2025.01~2025.12)를 주면 **0건**, 해를 걸치는 범위(2025.06~2026.05)를
    주면 priodFr 해의 1~12월 전체를 돌려준다. 그래서 '연도 Y' 는 Y.06~(Y+1).05 로 요청한다(m_to 는 미사용·호환용)."""
    body = urllib.parse.urlencode({
        "tradeKind": "ETS_MNK_1020000E", "priodKind": "MON",
        "priodFr": f"{year}.06", "priodTo": f"{year + 1}.05", "statsBase": "acptDd", "ttwgTpcd": "1000",
        "selectPaging": "1", "showPagingLine": "100", "sortColumn": "", "sortOrder": "",
        "cntyNm": cnty, "hsSgnGrpCol": grpcol(hs), "hsSgnWhrCol": grpcol(hs), "hsSgn": hs}).encode()
    j = json.loads(urllib.request.urlopen(urllib.request.Request(URL, data=body, headers=H), timeout=60).read())
    out = {}
    for x in j.get("items") or []:
        p = (x.get("priodTitle") or "").strip()
        if not re.match(r"^\d{4}\.\d{2}$", p):
            continue
        v = (x.get("expUsdAmt") or "").replace(",", "").strip()
        out[p] = int(v) if v else 0
    return out


def main():
    now = datetime.now()
    y, m = now.year, now.month
    years = [y - 3, y - 2, y - 1, y]
    # 전세계 합계는 hs_invest.json 에서 가져온다(같은 산식·같은 날 수집) — 없으면 비중 생략
    tot = {}
    try:
        hv = json.loads((BASE / "data" / "db" / "hs_invest.json").read_text(encoding="utf-8"))
        for it in hv.get("items", []):
            tot[it["hs"]] = dict(zip(hv["months"], it["exp"]))
    except Exception:
        pass
    items, months = [], set()
    for th, nm, codes, note in ITEMS:
        acc = {}
        for hs in codes:
            for yy in years:
                try:
                    d = fetch_year(hs, yy, 12 if yy < y else m, "중국")
                    for k, v in d.items():
                        acc[k] = acc.get(k, 0) + v
                except Exception as e:
                    print(f"  ⚠ {nm}({hs},{yy}) 실패: {repr(e)[:60]}", flush=True)
                time.sleep(0.4)
        months |= set(acc.keys())
        key = "+".join(codes)
        items.append({"th": th, "nm": nm, "hs": key, "note": note, "_d": acc,
                      "_t": tot.get(key) or tot.get(codes[0]) or {}})
        print(f"  {th}/{nm}: {len(acc)}개월", flush=True)
    ms = sorted(months)[-37:]
    for it in items:
        d, t = it.pop("_d"), it.pop("_t")
        it["exp"] = [d.get(k) for k in ms]
        it["tot"] = [t.get(k) for k in ms]       # 전세계 수출(천$) — hs_invest 품목이 있을 때만
    OUT.write_text(json.dumps({"asof": now.strftime("%Y-%m-%d %H:%M"), "months": ms, "items": items,
                               "src": "관세청 tradedata.go.kr 품목별+국가별(ETS_MNK_1020000E) · 수출 천달러 · 수리일 기준"},
                              ensure_ascii=False), encoding="utf-8")
    print(f"[cnexp] ✅ {len(items)}품목 · {len(ms)}개월 → {OUT}", flush=True)


if __name__ == "__main__":
    main()
