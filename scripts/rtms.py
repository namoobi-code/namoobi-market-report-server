#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""rtms.py — 국토부 아파트 실거래가 (2026-08-02 신설 · 매일 07:20 cron).

소스: data.go.kr RTMSDataSvcAptTrade(매매) · RTMSDataSvcAptRent(전월세) — XML, 자동승인 키
지역: 서울 25개구 + 경기 주요(성남분당·수원영통·용인수지·화성·과천) + 5대 광역시 대표구 = 35곳
집계: 지역·월별 — 매매 {n 거래건수, avg 평균가(억), med 중위가(억)} · 전세(월세0) {n, dep 평균보증금(억)}
      해제거래(cdealType='O') 제외 · 실거래 신고기한 30일 → 최근 2~3개월은 미완성치(롤링 재수집으로 수렴)
산출: data/db/rtms.json {asof, names, sale:{code:{t,n,avg,med}}, rent:{...}, } + SEOUL(25구 합산) 의사지역
사용: rtms.py [--backfill]  (백필 24개월 · 기본 최근 3개월 롤링)
"""
import json, sys, time, urllib.request, urllib.error
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "data" / "db" / "rtms.json"
KEY = (BASE / "keys" / "data.go.kr.txt").read_text().strip()
MONTHS = 24 if "--backfill" in sys.argv else 3
if "--months" in sys.argv:
    MONTHS = int(sys.argv[sys.argv.index("--months") + 1])
EXTEND = "--extend" in sys.argv        # 이미 수집된 달은 건너뛰고 과거만 채움(최근 3개월은 항상 재수집)
BUDGET = None                          # --budget N: 이번 실행 API 호출 상한(심층 백필 분할용)
if "--budget" in sys.argv:
    BUDGET = int(sys.argv[sys.argv.index("--budget") + 1])
CALLS = 0
class _Stop(Exception): pass
ONLY = None
if "--only" in sys.argv:
    ONLY = set(sys.argv[sys.argv.index("--only") + 1].split(","))

REGIONS = {
    # 서울 25구
    "11110": "서울 종로구", "11140": "서울 중구", "11170": "서울 용산구", "11200": "서울 성동구",
    "11215": "서울 광진구", "11230": "서울 동대문구", "11260": "서울 중랑구", "11290": "서울 성북구",
    "11305": "서울 강북구", "11320": "서울 도봉구", "11350": "서울 노원구", "11380": "서울 은평구",
    "11410": "서울 서대문구", "11440": "서울 마포구", "11470": "서울 양천구", "11500": "서울 강서구",
    "11530": "서울 구로구", "11545": "서울 금천구", "11560": "서울 영등포구", "11590": "서울 동작구",
    "11620": "서울 관악구", "11650": "서울 서초구", "11680": "서울 강남구", "11710": "서울 송파구",
    "11740": "서울 강동구",
    # 부산 16구·군
    "26110": "부산 중구", "26140": "부산 서구", "26170": "부산 동구", "26200": "부산 영도구",
    "26230": "부산 부산진구", "26260": "부산 동래구", "26290": "부산 남구", "26320": "부산 북구",
    "26350": "부산 해운대구", "26380": "부산 사하구", "26410": "부산 금정구", "26440": "부산 강서구",
    "26470": "부산 연제구", "26500": "부산 수영구", "26530": "부산 사상구", "26710": "부산 기장군",
    # 대구
    "27110": "대구 중구", "27140": "대구 동구", "27170": "대구 서구", "27200": "대구 남구",
    "27230": "대구 북구", "27260": "대구 수성구", "27290": "대구 달서구", "27710": "대구 달성군", "27720": "대구 군위군",
    # 인천
    "28110": "인천 중구", "28140": "인천 동구", "28177": "인천 미추홀구", "28185": "인천 연수구",
    "28200": "인천 남동구", "28237": "인천 부평구", "28245": "인천 계양구", "28260": "인천 서구",
    "28710": "인천 강화군",
    # 대전·울산·세종  (광주광역시는 본 API 전 구·전 월 0건 — 국토부 데이터 미제공 이슈로 제외)
    "30110": "대전 동구", "30140": "대전 중구", "30170": "대전 서구", "30200": "대전 유성구", "30230": "대전 대덕구",
    "31110": "울산 중구", "31140": "울산 남구", "31170": "울산 동구", "31200": "울산 북구", "31710": "울산 울주군",
    "36110": "세종시",
    # 경기 (화성은 2026 구 분화: 41593 봉담권·41595 병점권·41597 동탄)
    "41111": "수원 장안구", "41113": "수원 권선구", "41115": "수원 팔달구", "41117": "수원 영통구",
    "41131": "성남 수정구", "41133": "성남 중원구", "41135": "성남 분당구",
    "41150": "의정부시", "41171": "안양 만안구", "41173": "안양 동안구", "41190": "부천시",
    "41210": "광명시", "41220": "평택시", "41250": "동두천시",
    "41271": "안산 상록구", "41273": "안산 단원구",
    "41281": "고양 덕양구", "41285": "고양 일산동구", "41287": "고양 일산서구",
    "41290": "과천시", "41310": "구리시", "41360": "남양주시", "41370": "오산시", "41390": "시흥시",
    "41410": "군포시", "41430": "의왕시", "41450": "하남시",
    "41461": "용인 처인구", "41463": "용인 기흥구", "41465": "용인 수지구",
    "41480": "파주시", "41500": "이천시", "41550": "안성시", "41570": "김포시",
    "41593": "화성 봉담권", "41595": "화성 병점권", "41597": "화성 동탄",
    "41610": "광주시(경기)", "41630": "양주시", "41650": "포천시", "41670": "여주시",
    "41800": "연천군", "41820": "가평군", "41830": "양평군",
    # 강원 (2023~ 51)
    "51110": "춘천시", "51130": "원주시", "51150": "강릉시", "51170": "동해시", "51190": "태백시",
    "51210": "속초시", "51230": "삼척시", "51720": "홍천군", "51730": "횡성군", "51750": "영월군",
    "51760": "평창군", "51770": "정선군", "51780": "철원군", "51790": "화천군", "51800": "양구군",
    "51810": "인제군", "51820": "고성군(강원)", "51830": "양양군",
    # 충북
    "43111": "청주 상당구", "43112": "청주 서원구", "43113": "청주 흥덕구", "43114": "청주 청원구",
    "43130": "충주시", "43150": "제천시", "43720": "보은군", "43730": "옥천군", "43740": "영동군",
    "43745": "증평군", "43750": "진천군", "43760": "괴산군", "43770": "음성군", "43800": "단양군",
    # 충남
    "44131": "천안 동남구", "44133": "천안 서북구", "44150": "공주시", "44180": "보령시", "44200": "아산시",
    "44210": "서산시", "44230": "논산시", "44250": "계룡시", "44270": "당진시",
    "44710": "금산군", "44760": "부여군", "44770": "서천군", "44790": "청양군", "44800": "홍성군",
    "44810": "예산군", "44825": "태안군",
    # 전북 (2024~ 52)
    "52111": "전주 완산구", "52113": "전주 덕진구", "52130": "군산시", "52140": "익산시", "52180": "정읍시",
    "52190": "남원시", "52210": "김제시", "52710": "완주군", "52720": "진안군", "52730": "무주군",
    "52740": "장수군", "52750": "임실군", "52770": "순창군", "52790": "고창군", "52800": "부안군",
    # 전남
    "46110": "목포시", "46130": "여수시", "46150": "순천시", "46170": "나주시", "46230": "광양시",
    "46710": "담양군", "46720": "곡성군", "46730": "구례군", "46770": "고흥군", "46780": "보성군",
    "46790": "화순군", "46800": "장흥군", "46810": "강진군", "46820": "해남군", "46830": "영암군",
    "46840": "무안군", "46860": "함평군", "46870": "영광군", "46880": "장성군", "46890": "완도군",
    "46900": "진도군", "46910": "신안군",
    # 경북
    "47111": "포항 남구", "47113": "포항 북구", "47130": "경주시", "47150": "김천시", "47170": "안동시",
    "47190": "구미시", "47210": "영주시", "47230": "영천시", "47250": "상주시", "47280": "문경시",
    "47290": "경산시", "47730": "의성군", "47750": "청송군", "47760": "영양군", "47770": "영덕군",
    "47820": "청도군", "47830": "고령군", "47840": "성주군", "47850": "칠곡군", "47900": "예천군",
    "47920": "봉화군", "47930": "울진군", "47940": "울릉군",
    # 경남
    "48121": "창원 의창구", "48123": "창원 성산구", "48125": "창원 마산합포구", "48127": "창원 마산회원구",
    "48129": "창원 진해구", "48170": "진주시", "48220": "통영시", "48240": "사천시", "48250": "김해시",
    "48270": "밀양시", "48310": "거제시", "48330": "양산시",
    "48720": "의령군", "48730": "함안군", "48740": "창녕군", "48820": "고성군(경남)", "48840": "남해군",
    "48850": "하동군", "48860": "산청군", "48870": "함양군", "48880": "거창군", "48890": "합천군",
    # 제주
    "50110": "제주시", "50130": "서귀포시",
}
SIDO = {"11": "서울", "26": "부산", "27": "대구", "28": "인천", "30": "대전", "31": "울산", "36": "세종",
        "41": "경기", "51": "강원", "43": "충북", "44": "충남", "52": "전북", "46": "전남",
        "47": "경북", "48": "경남", "50": "제주"}
SEOUL = [c for c in REGIONS if c.startswith("11")]

def months_back(n):
    y, m = datetime.now().year, datetime.now().month
    out = []
    for _ in range(n):
        m -= 1
        if m == 0: y -= 1; m = 12
        out.append(f"{y}{m:02d}")
    return out[::-1]

def fetch(svc, op, lawd, ym):
    """전 페이지 수집 — item dict 리스트."""
    global CALLS
    rows, page = [], 1
    while True:
        CALLS += 1
        if BUDGET and CALLS > BUDGET:
            raise _Stop("호출 예산 소진")
        u = (f"https://apis.data.go.kr/1613000/{svc}/{op}"
             f"?serviceKey={KEY}&LAWD_CD={lawd}&DEAL_YMD={ym}&numOfRows=1000&pageNo={page}")
        try:
            d = urllib.request.urlopen(u, timeout=25).read()
            root = ET.fromstring(d)
        except urllib.error.HTTPError as he:
            if he.code == 429:
                raise _Stop("HTTP 429 요청 과다(국토부 레이트리밋)")
            time.sleep(1)
            try:
                d = urllib.request.urlopen(u, timeout=25).read(); root = ET.fromstring(d)
            except Exception:
                return rows
        except Exception:
            time.sleep(1)
            try:
                d = urllib.request.urlopen(u, timeout=25).read(); root = ET.fromstring(d)
            except Exception:
                return rows
        rc = (root.findtext(".//resultCode") or "").strip()
        if rc == "22":
            raise _Stop("일일 트래픽 한도 초과")
        if rc not in ("000", "00"):
            return rows
        items = root.findall(".//item")
        for it in items:
            rows.append({e.tag: (e.text or "").strip() for e in it})
        total = int(root.findtext(".//totalCount") or 0)
        if page * 1000 >= total or not items: break
        page += 1
    return rows

def num(s):
    try: return float(str(s).replace(",", ""))
    except Exception: return None

def agg_sale(rows):
    px = [num(r.get("dealAmount")) for r in rows if r.get("cdealType", "") != "O"]
    px = sorted(p / 10000 for p in px if p)                     # 만원 → 억
    if not px: return None
    n = len(px)
    med = px[n // 2] if n % 2 else (px[n // 2 - 1] + px[n // 2]) / 2
    return {"n": n, "avg": round(sum(px) / n, 2), "med": round(med, 2)}

def agg_rent(rows):
    dep = [num(r.get("deposit")) for r in rows
           if (num(r.get("monthlyRent")) or 0) == 0]            # 전세 = 월세 0
    dep = [d / 10000 for d in dep if d]
    if not dep: return None
    return {"n": len(dep), "dep": round(sum(dep) / len(dep), 2)}

def main():
    old = {}
    try: old = json.loads(OUT.read_text(encoding="utf-8"))
    except Exception: pass
    sale = old.get("sale") or {}; rent = old.get("rent") or {}
    yms = months_back(MONTHS + 1)                               # 당월 포함(신고분 반영)
    yms.append(datetime.now().strftime("%Y%m"))
    for i, (code, name) in enumerate(REGIONS.items()):
        if ONLY and code not in ONLY: continue
        s = {t: (sale.get(code) or {}).get("m", {}).get(t) for t in (sale.get(code) or {}).get("m", {})} \
            if isinstance((sale.get(code) or {}).get("m"), dict) else {}
        r_ = {t: (rent.get(code) or {}).get("m", {}).get(t) for t in (rent.get(code) or {}).get("m", {})} \
            if isinstance((rent.get(code) or {}).get("m"), dict) else {}
        recent = set(months_back(3)) | {datetime.now().strftime("%Y%m")}
        stopped = None
        try:
            for ym in (reversed(yms) if EXTEND else yms):    # 심층 백필은 최신→과거 순(가까운 과거부터 완성)
                if EXTEND and ym not in recent and (ym in s or ym in r_):
                    continue
                a = agg_sale(fetch("RTMSDataSvcAptTrade", "getRTMSDataSvcAptTrade", code, ym))
                if a: s[ym] = a
                time.sleep(0.3)
                b = agg_rent(fetch("RTMSDataSvcAptRent", "getRTMSDataSvcAptRent", code, ym))
                if b: r_[ym] = b
                time.sleep(0.3)
        except _Stop as e:
            stopped = str(e)
        sale[code] = {"m": s}; rent[code] = {"m": r_}
        print(f"  [{i+1}/{len(REGIONS)}] {name}: 매매 {len(s)}개월 · 전세 {len(r_)}개월"
              + (f"  ⚠ {stopped} — 진행분 저장 후 종료" if stopped else ""))
        if stopped:
            break
    # 합산 의사지역 — 서울(25구)·부산(16구군)
    def agg_region(codes, key_avg):
        allm = sorted({t for c in codes for t in ((sale if key_avg == "avg" else rent).get(c) or {}).get("m", {})})
        out = {}
        src = sale if key_avg == "avg" else rent
        for t in allm:
            rs = [src[c]["m"].get(t) for c in codes if (src.get(c) or {}).get("m", {}).get(t)]
            if not rs: continue
            n = sum(x["n"] for x in rs)
            if key_avg == "avg":
                # 중위가: 시군구 중위가의 거래건수 가중 중위(근사 — 전체 거래 풀링과 유사)
                pairs = sorted((x["med"], x["n"]) for x in rs if x.get("med") is not None)
                med = None
                if pairs:
                    half = sum(w for _, w in pairs) / 2; acc = 0
                    for v, w in pairs:
                        acc += w
                        if acc >= half: med = v; break
                out[t] = {"n": n, "avg": round(sum(x["avg"] * x["n"] for x in rs) / n, 2),
                          "med": round(med, 2) if med is not None else None}
            else:
                out[t] = {"n": n, "dep": round(sum(x["dep"] * x["n"] for x in rs) / n, 2)}
        return out
    names = dict(REGIONS)
    for pfx, snm in SIDO.items():
        codes = [c for c in REGIONS if c.startswith(pfx)]
        if len(codes) < 2: continue
        k = "A" + pfx
        sale[k] = {"m": agg_region(codes, "avg")}; rent[k] = {"m": agg_region(codes, "dep")}
        names[k] = f"{snm} 전체({len(codes)})"
    sale.pop("SEOUL", None); rent.pop("SEOUL", None); sale.pop("BUSAN", None); rent.pop("BUSAN", None)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"asof": datetime.now().strftime("%Y-%m-%d %H:%M"),
                               "names": names, "sale": sale, "rent": rent}, ensure_ascii=False),
                   encoding="utf-8")
    print(f"[rtms] ✅ {len(REGIONS)}지역 · 서울합산 {len(sale['A11']['m'])}개월 → {OUT}")

if __name__ == "__main__":
    main()
