#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fetch_kcons.py — K-소비재 선행지표 수집 (2026-08-29 신설)

'K-소비재 선행지표 스터디'(포브스코리아 2026 '데이터로 보는 K소비재' + 쇼피 카테고리 자료) 구현.
이상적 선행 흐름은 검색량 → 콘텐츠 반응 → 장바구니 → 주문 → 리뷰·재구매 → 수출액 순이지만,
검색·쇼피·SNS 데이터는 공개 API가 없다(쇼피 비공개·구글 트렌드 키워드 API 비공식·틱톡 폐쇄).
→ 무토큰으로 잡을 수 있는 두 축만 구현한다:
  ① 품목군별 수출액 (관세청 tradedata.go.kr · 월간 3년 · 무인증 실측 ✓)
     — 수출은 소비자 수요의 후행이지만 기업 분기 실적 발표보다는 1~2개월 앞선다.
       테마: K뷰티(화장품3304·헤어3305·향수3303·방향제퍼스널케어3307·미용기기8543)
             K푸드(라면1902·소스2103·김121221·당류과자1704·음료2202·주류2208)
             K패션(가방4202·선글라스9004·의류61+62)
     ※ 8543은 전기기기 광범위 코드라 미용기기 외 노이즈 포함(추이용). 61/62는 류(2자리) 전체.
  ② 연동 종목 시세 (야후 일봉 1년) — 품목 수출과 실적 경로가 있는 종목만.
일간 트렌드(구글·유튜브·네이버쇼핑)는 기존 Trends 탭(trends_collect.py)이 담당 — 국내 관심도 보조지표.

산출: data/db/kcons.json
cron: 25 6 * * *   (수출은 월간·월중 갱신이라 매일 돌려도 값은 가끔 바뀐다 — 무해)
"""
import json, re, time, urllib.request, urllib.parse
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
OUT  = BASE / "data" / "db" / "kcons.json"
UA   = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"}
KST  = timezone(timedelta(hours=9))

# (테마, 품목명, [HS코드 — 복수면 합산], 비고)
ITEMS = [
    ("K뷰티", "화장품(기초·색조)", ["3304"], "세럼·선크림·틴트 — K뷰티 본진"),
    ("K뷰티", "헤어 제품",        ["3305"], "샴푸·트리트먼트 — 두피케어 확장"),
    ("K뷰티", "향수",            ["3303"], "니치 향수 성장"),
    ("K뷰티", "방향제·퍼스널케어", ["3307"], "디퓨저·데오도런트 등 K리빙 경계"),
    ("K뷰티", "미용기기(광범위)",  ["8543"], "뷰티 디바이스 — 타 전기기기 노이즈 포함, 추이용"),
    ("K푸드", "라면(면류)",       ["1902"], "불닭 등 — K푸드 대장 품목"),
    ("K푸드", "소스류",          ["2103"], "고추장·불닭소스·쌈장"),
    ("K푸드", "김",              ["121221"], "마른김 — 6자리 정밀"),
    ("K푸드", "당류과자",         ["1704"], "무설탕 사탕·젤리 — 쇼피 간식 트렌드"),
    ("K푸드", "음료",            ["2202"], "커피·콤부차·분말음료"),
    ("K푸드", "주류",            ["2208"], "소주 등"),
    ("K패션", "가방·잡화",        ["4202"], "미니백·크로스백·솔더백"),
    ("K패션", "선글라스·안경",     ["9004"], "메탈 프레임 데일리 스타일링"),
    ("K패션", "의류(편물+직물)",   ["61", "62"], "후드·오버사이즈 — 61·62류 전체 합산"),
]
THEME_COLOR = {"K뷰티": "#be185d", "K푸드": "#b45309", "K패션": "#4f46e5"}

# (야후심볼, 표시명, 테마, 연결 논리)
STOCKS = [
    ("090430.KS", "아모레퍼시픽",  "K뷰티", "브랜드 대장 — 화장품 수출·비중국 리밸런싱의 척도"),
    ("051900.KS", "LG생활건강",   "K뷰티", "화장품+생활용품 — 3304·3307 동시 노출"),
    ("192820.KQ", "코스맥스",     "K뷰티", "세계 1위 ODM — 인디브랜드 수출 급증분을 생산으로 흡수"),
    ("161890.KS", "한국콜마",     "K뷰티", "ODM 양강 — 선크림 등 기초 수출과 직결"),
    ("257720.KQ", "실리콘투",     "K뷰티", "K뷰티 역직구·글로벌 유통 플랫폼 — 수출 통계와 가장 직결"),
    ("278470.KS", "에이피알",     "K뷰티", "뷰티 디바이스(8543)+화장품 — 기기 수출의 대표"),
    ("018290.KQ", "브이티",       "K뷰티", "리들샷 — 일본·동남아 확산 국면"),
    ("214150.KQ", "클래시스",     "K뷰티", "미용 의료기기 수출 — 슈링크 신흥국 확장"),
    ("003230.KS", "삼양식품",     "K푸드", "불닭볶음면 — 라면(1902) 수출과 실적이 정비례하는 대장"),
    ("004370.KS", "농심",        "K푸드", "신라면 — 미국 공장 증설, 라면 수출 양강"),
    ("097950.KS", "CJ제일제당",   "K푸드", "비비고 — 소스·간편식 글로벌, 미국 현지생산 비중 큼"),
    ("271560.KS", "오리온",       "K푸드", "과자(1704 등) — 중국·베트남·러시아 현지법인 중심"),
    ("001680.KS", "대상",        "K푸드", "김치·소스(2103) — 종가집 수출"),
    ("005300.KS", "롯데칠성",     "K푸드", "음료(2202)·소주(2208) 동시 노출"),
    ("000080.KS", "하이트진로",   "K푸드", "소주(2208) 수출 대표"),
    ("383220.KS", "F&F",         "K패션", "MLB·디스커버리 — 중국·동남아 K패션 브랜드 대표"),
    ("081660.KS", "휠라홀딩스",   "K패션", "휠라+타이틀리스트 — 글로벌 브랜드 포트폴리오"),
    ("111770.KS", "영원무역",     "K패션", "노스페이스 등 OEM — 의류(61·62) 수출 물량의 생산자"),
    ("298540.KQ", "더네이쳐홀딩스","K패션", "내셔널지오그래픽 어패럴 — 아시아 확장 국면"),
]

# ══════════════════════════════════════════════════════════════════════════
def get(u, to=30, data=None, hdr=None):
    h = dict(UA); h.update(hdr or {})
    return urllib.request.urlopen(urllib.request.Request(u, data=data, headers=h), timeout=to).read()

# ── ① 관세청 품목군별 수출 (fetch_hs_invest.py 검증 패턴 재사용) ─────────────
TRADE_URL = "https://tradedata.go.kr/cts/hmpg/retrieveTrade.do"
TRADE_H   = {"Content-Type": "application/x-www-form-urlencoded",
             "Referer": "https://tradedata.go.kr/cts/index.do"}

def grpcol(hs):
    return {2: "HS2_SGN", 4: "HS4_SGN", 6: "HS6_SGN", 10: "HS10_SGN"}[len(hs)]

def fetch_hs(hs, fr, to):
    body = urllib.parse.urlencode({
        "tradeKind": "ETS_MNK_1020000A", "priodKind": "MON", "priodFr": fr, "priodTo": to,
        "statsBase": "acptDd", "ttwgTpcd": "1000", "showPagingLine": "100",
        "hsSgnGrpCol": grpcol(hs), "hsSgnWhrCol": grpcol(hs), "hsSgn": hs}).encode()
    j = json.loads(get(TRADE_URL, data=body, hdr=TRADE_H))
    out = {}
    for x in j.get("items") or []:
        p = (x.get("priodTitle") or "").strip()
        if not re.match(r"^\d{4}\.\d{2}$", p):
            continue
        v = (x.get("expUsdAmt") or "").replace(",", "").strip()
        out[p] = int(v) if v else 0
    return out

def collect_export():
    now = datetime.now(KST)
    fr = f"{now.year-3}{now.month:02d}"
    to = f"{now.year}{now.month:02d}"
    items, months = [], set()
    for th, nm, codes, note in ITEMS:
        acc = {}
        for hs in codes:
            try:
                d = fetch_hs(hs, fr, to)
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
    return {"months": ms, "items": items}

# ── ② 연동 종목 시세 (야후 일봉 1년 — fetch_kpop.py 검증 패턴 재사용) ────────
def pct(a, b):
    try:
        return round((b / a - 1) * 100, 1) if a else None
    except Exception:
        return None

def yahoo(sym):
    u = (f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(sym)}"
         f"?range=1y&interval=1d")
    j = json.loads(get(u, to=20))
    r = (j.get("chart") or {}).get("result") or []
    if not r:
        return None
    r = r[0]
    ts = r.get("timestamp") or []
    cl = ((r.get("indicators") or {}).get("quote") or [{}])[0].get("close") or []
    pts = [(t, c) for t, c in zip(ts, cl) if c is not None]
    if not pts:
        return None
    closes = [c for _, c in pts]
    step = max(1, len(pts) // 60)
    samp = pts[::step][-60:]
    return {"cur": round(closes[-1], 1),
            "d1": pct(closes[-2], closes[-1]) if len(closes) > 1 else None,
            "m1": pct(closes[-22], closes[-1]) if len(closes) > 22 else None,
            "m3": pct(closes[-64], closes[-1]) if len(closes) > 64 else None,
            "y1": pct(closes[0], closes[-1]),
            "spark": [round(c, 1) for _, c in samp],
            # (2026-08-29) X축 날짜 미표시 피드백 — 샘플과 같은 보폭의 날짜(YY.MM.DD)를 함께 내린다
            "spark_d": [datetime.fromtimestamp(t, KST).strftime("%y.%m.%d") for t, _ in samp]}

def collect_stocks():
    rows = []
    for sym, nm, th, why in STOCKS:
        q = None
        try:
            q = yahoo(sym)
        except Exception as e:
            print(f"  ⚠ {nm}({sym}) 시세 실패: {repr(e)[:50]}", flush=True)
        rows.append({"sym": sym, "name": nm, "th": th, "why": why, **(q or {})})
        time.sleep(0.25)
    print(f"  시세: {sum(1 for r in rows if r.get('cur'))}/{len(STOCKS)}종목", flush=True)
    return rows

# ══════════════════════════════════════════════════════════════════════════
def main():
    print("[kcons] 수집 시작", flush=True)
    export = collect_export()
    stocks = collect_stocks()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "as_of": datetime.now(KST).strftime("%Y-%m-%d %H:%M"),
        "themes": [{"name": t, "color": c} for t, c in THEME_COLOR.items()],
        "export": export, "stocks": stocks,
    }, ensure_ascii=False), encoding="utf-8")
    print(f"[kcons] ✅ {len(export['items'])}품목 · {len(export['months'])}개월 · {len(stocks)}종목 → {OUT}", flush=True)

if __name__ == "__main__":
    main()
