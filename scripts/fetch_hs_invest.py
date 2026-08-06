#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fetch_hs_invest.py — 3.1.10 투자 관점 품목별 월간 수출 (2026-08-06 신설 · 매일 1회).

소스: 관세청 수출입무역통계(tradedata.go.kr) 내부 조회 — 무인증 POST (실측 재현):
  POST /cts/hmpg/retrieveTrade.do
  hsSgnGrpCol/hsSgnWhrCol = HS2_SGN(류)·HS4_SGN(호)·HS6_SGN(소호) — 자릿수별 실측 확인
  응답 items[].priodTitle(YYYY.MM)·expUsdAmt(수출 천달러) · '총계' 행 제외
※ data.go.kr Itemtrade API 는 보유 키 미신청(403) — 포털 직접 조회로 대체.
산출: data/db/hs_invest.json {asof, months:[...], items:[{th,nm,hs,note,exp:[천달러]}]}
cron: 35 8 * * *  (월간 확정치 — 익월 15일경 새 달 반영)
"""
import json, re, time, urllib.request, urllib.parse
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "data" / "db" / "hs_invest.json"
URL = "https://tradedata.go.kr/cts/hmpg/retrieveTrade.do"
H = {"Content-Type": "application/x-www-form-urlencoded", "User-Agent": "Mozilla/5.0",
     "Referer": "https://tradedata.go.kr/cts/index.do"}

# (테마, 품목, [HS코드들 — 복수면 합산], 비고)
ITEMS = [
    ("K뷰티", "화장품(기초·색조)", ["3304"], "스킨케어·메이크업"),
    ("K뷰티", "헤어 제품", ["3305"], "샴푸·염모제"),
    ("K뷰티", "향수", ["3303"], ""),
    ("반도체", "반도체(집적회로)", ["8542"], "메모리·시스템"),
    ("반도체", "개별소자·센서", ["8541"], "LED·태양전지 포함"),
    ("반도체", "반도체 제조장비", ["8486"], "장비 국산화 수출"),
    ("이차전지", "배터리(축전지)", ["8507"], "리튬이온 포함"),
    ("이차전지", "전구체 화학품", ["2841", "2825"], "리튬·니켈 화합물"),
    ("자동차", "승용차", ["8703"], "전기차 포함"),
    ("자동차", "자동차 부품", ["8708"], ""),
    ("바이오", "의약품(완제)", ["3004"], ""),
    ("바이오", "백신·바이오의약품", ["3002"], "바이오시밀러"),
    ("의료기기", "의료기기", ["9018"], "진단·수술기기"),
    ("의료기기", "임플란트·보철", ["9021"], "덴탈"),
    ("IT", "무선통신기기", ["8517"], "휴대폰"),
    ("IT", "컴퓨터·저장장치", ["8471"], "SSD 일부"),
    ("IT", "평판디스플레이 모듈", ["8524"], "HS2022 신설"),
    ("조선", "선박", ["89"], "89류 전체"),
    ("철강", "철강", ["72"], "72류 전체"),
    ("정유", "석유제품", ["2710"], ""),
    ("K푸드", "라면(면류)", ["1902"], "즉석면 포함"),
    ("K푸드", "소스류", ["2103"], "고추장 등"),
    ("K푸드", "김(식용 해조류)", ["121221"], "마른김 — 6자리 정밀"),
    ("K푸드", "음료", ["2202"], ""),
    ("K푸드", "주류", ["2208"], "소주 등"),
    ("방산", "전차·장갑차", ["8710"], ""),
    ("방산", "무기·탄약", ["93"], "93류 전체"),
    ("미용기기", "미용·전기기기", ["8543"], "피부미용기기 등"),
    ("엔터", "악기", ["92"], "92류 전체"),
]

def grpcol(hs):
    return {2: "HS2_SGN", 4: "HS4_SGN", 6: "HS6_SGN"}[len(hs)]

def fetch(hs, fr, to):
    """{YYYY.MM: 수출 천달러}"""
    body = urllib.parse.urlencode({
        "tradeKind": "ETS_MNK_1020000A", "priodKind": "MON",
        "priodFr": fr, "priodTo": to, "statsBase": "acptDd", "ttwgTpcd": "1000",
        "showPagingLine": "100", "hsSgnGrpCol": grpcol(hs), "hsSgnWhrCol": grpcol(hs),
        "hsSgn": hs}).encode()
    j = json.loads(urllib.request.urlopen(
        urllib.request.Request(URL, data=body, headers=H), timeout=30).read())
    out = {}
    for x in j.get("items") or []:
        p = (x.get("priodTitle") or "").strip()
        if not re.match(r"^\d{4}\.\d{2}$", p):
            continue                                    # '총계' 행 제외
        v = (x.get("expUsdAmt") or "").replace(",", "").strip()
        out[p] = int(v) if v else 0
    return out

def main():
    now = datetime.now()
    y, m = now.year, now.month
    fr = f"{y-2 if m<12 else y-1}{(m%12)+1:02d}"        # 25개월 전
    to = f"{y}{m:02d}"
    items = []
    months = set()
    for th, nm, codes, note in ITEMS:
        acc = {}
        for hs in codes:
            try:
                d = fetch(hs, fr, to)
                for k, v in d.items():
                    acc[k] = acc.get(k, 0) + v
            except Exception as e:
                print(f"  ⚠ {nm}({hs}) 실패: {repr(e)[:60]}", flush=True)
            time.sleep(0.4)
        months |= set(acc.keys())
        items.append({"th": th, "nm": nm, "hs": "+".join(codes), "note": note, "_d": acc})
        print(f"  {th}/{nm}: {len(acc)}개월", flush=True)
    ms = sorted(months)
    for it in items:
        d = it.pop("_d")
        it["exp"] = [d.get(k) for k in ms]
    OUT.write_text(json.dumps({"asof": now.strftime("%Y-%m-%d %H:%M"), "months": ms,
                               "items": items}, ensure_ascii=False), encoding="utf-8")
    print(f"[hsinv] ✅ {len(items)}품목 · {len(ms)}개월 → {OUT}", flush=True)

if __name__ == "__main__":
    main()
