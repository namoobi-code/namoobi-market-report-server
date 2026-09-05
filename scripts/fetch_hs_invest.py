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

# ── 수주 이벤트 메모 (2026-09-05 신설 — 사용자 요청) ─────────────────────────
# 계약·수주는 통관 통계에 영원히 안 잡힌다(수출 통계 = 실제 선적 시점) → 품목 행 아래
# 메모 행으로 표시해 '앞으로 이 행에 얼마가 언제 유입될지'를 미리 적어 둔다.
# est(반영 예상)는 계약 조건 기반 추정(E) — 실제 통관되면 그 달 수치로 검증한다.
# 스키마: {hs: 품목 행의 hs 문자열과 일치, d: 계약일, txt: 내용, est: 몇월·얼마 예상}
EVENTS = [
    {"hs": "8507", "d": "2026-07-30",
     "txt": "🔋 K배터리 3사 7분기 만에 동시 흑자(2Q26) — ESS 효과. LG엔솔 ESS 수주잔고 ~140GWh + 상반기 신규 3조원 · "
            "삼성SDI 각형 LFP 잔고 2029년까지 가득(2028년 캐파 초과 전망) · SK온 올해 20GWh 수주 목표",
     "est": "반영 주의: 북미 ESS 는 현지생산(랜싱·얼티엄셀즈 JV 등) 중심이라 이 행(한국발 통관)엔 일부만 반영 — "
            "통관 급증을 기대하면 안 됨. 국내(서산·오창 등) 생산분 선적·셀/소재 수출 증가로 완만한 상승 경로(E). "
            "북미 점유 추이는 점유율 추이 탭 '북미 ESS' 배틀 참고"},
    {"hs": "93", "d": "2026-06-19",
     "txt": "🏆 한화에어로 K9 차륜형 자주포(K9MH) 미 육군 시제품 계약 — 미국 첫 수출. "
            "시제품 6문 $1.00억(1,417억원) + 옵션 12문(누적 액면 $2.63억) · 향후 양산 ~500문·약 10조원 추산",
     "est": "반영 예상: 자주포는 HS 9301(자주식 화포) → 이 행(93류)에 잡힘. 이행기간 4년(~2030) 중 "
            "시제품 제작·시험 후 선적 — 통상 12~24개월 후인 2027H2~2028 통관 예상(E). "
            "6문 일괄 선적 시 해당 월 +$1.0억(93류 월 $3~7억 대비 +15~30% 점프), 분할 선적 시 월 +$0.2~0.5억 분산. "
            "옵션 12문 행사 시 최대 +$2.6억 추가"},
]

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "data" / "db" / "hs_invest.json"
URL = "https://tradedata.go.kr/cts/hmpg/retrieveTrade.do"
H = {"Content-Type": "application/x-www-form-urlencoded", "User-Agent": "Mozilla/5.0",
     "Referer": "https://tradedata.go.kr/cts/index.do"}

# (테마, 품목, [HS코드들 — 복수면 합산], 비고)
ITEMS = [
    ("K뷰티", "화장품(기초·색조)", ["3304"], "스킨케어·메이크업"),
    ("K뷰티", "헤어 제품", ["3305"], "샴푸·염모제"),
    ("K뷰티", "└ 샴푸(정밀)", ["330510"], "3305 중 샴푸만 — 닥터그루트 세포라 스토리"),
    ("K뷰티", "향수", ["3303"], ""),
    ("반도체", "반도체(집적회로)", ["8542"], "메모리·시스템"),
    ("반도체", "└ 메모리 반도체(정밀)", ["854232"], "8542 중 메모리만 — HBM 슈퍼사이클 직결(YoY +236% vs 전체 +150%)"),
    ("반도체", "개별소자·센서", ["8541"], "LED·태양전지 포함"),
    ("반도체", "반도체 제조장비", ["8486"], "장비 국산화 수출"),
    ("이차전지", "배터리(축전지)", ["8507"], "리튬이온 포함"),
    ("이차전지", "전구체 화학품", ["2841", "2825"], "리튬·니켈 화합물"),
    ("자동차", "승용차", ["8703"], "전기차 포함"),
    ("자동차", "└ 순수전기차 BEV(정밀)", ["870380"], "8703 중 EV만 — 전체 -1% 속 +16% 괴리"),
    ("자동차", "자동차 부품", ["8708"], ""),
    ("바이오", "의약품(완제)", ["3004"], ""),
    ("바이오", "백신·바이오의약품", ["3002"], "바이오시밀러"),
    ("바이오", "└ 백신(정밀)", ["300241"], "3002 중 백신만 — 전체 +20% 속 -22% 역방향"),
    ("바이오", "└ 항체·면역의약(정밀)", ["300215"], "시밀러·위탁생산 물량 프록시"),
    ("의료기기", "의료기기", ["9018"], "진단·수술기기"),
    ("의료기기", "임플란트·보철", ["9021"], "덴탈"),
    ("의료기기", "└ 치과 임플란트(정밀)", ["902129"], "9021 중 임플란트만"),
    ("의료기기", "X선·방사선기기", ["9022"], "치과CT·디텍터 — 신규 커버"),
    ("IT", "무선통신기기", ["8517"], "휴대폰"),
    ("IT", "컴퓨터·저장장치", ["8471"], "SSD 일부"),
    ("IT", "평판디스플레이 모듈", ["8524"], "HS2022 신설"),
    ("전력기기", "변압기·인덕터", ["8504"], "초고압 변압기 슈퍼사이클 — 신규 커버"),
    ("전력기기", "절연전선·케이블", ["8544"], "HVDC·해저케이블 — 신규 커버"),
    ("태양광", "태양전지 셀·모듈", ["854142", "854143"], "셀 +90%·모듈 +105% — 8541 LED에 묻혀있던 고성장"),
    ("조선", "선박", ["89"], "89류 전체"),
    ("철강", "철강", ["72"], "72류 전체"),
    ("정유", "석유제품", ["2710"], ""),
    ("K푸드", "라면(면류)", ["1902"], "즉석면 포함"),
    ("K푸드", "소스류", ["2103"], "고추장 등"),
    ("K푸드", "김(식용 해조류)", ["121221"], "마른김 — 6자리 정밀"),
    ("K푸드", "음료", ["2202"], ""),
    ("K푸드", "주류", ["2208"], "소주 등"),
    ("방산", "항공기(완제기·부품)", ["88"], "88류 전체 — FA-50·기체부품·MRO"),
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
    fr = f"{y-3 if m<12 else y-2}{(m%12)+1:02d}"        # 37개월 전 (X축 3년치)
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
                               "items": items, "events": EVENTS}, ensure_ascii=False), encoding="utf-8")
    print(f"[hsinv] ✅ {len(items)}품목 · {len(ms)}개월 → {OUT}", flush=True)

if __name__ == "__main__":
    main()
