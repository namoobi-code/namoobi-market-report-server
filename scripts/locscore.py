#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""locscore.py — 아파트 입지 점수 (서울 25구 · 성남 3구 · 용인 수지) (2026-10-17 신설)

출발점: 고준석(연세대) 인터뷰(한경머니 2026.10) 입지 5요소 —
  ① 교육: 걸어서 다닐 학원가  ② 편의: 종합병원 인접  ③ 자연: 대규모 공원 인접
  ④ 교통: 지하철 2개 노선 이상 환승 가능  ⑤ 단지 규모: 1,500~2,500가구
이걸 '기존 아파트' 하나하나에 공공데이터로 점수를 매긴다. 분양·줍줍 표에 쓰는 세대수와 달리
여기선 단지가 이미 서 있으니 좌표를 잡고 주변을 실제로 센다.

데이터 (모두 2026-10-17 실측):
  · 단지 목록·세대수·사용승인: data.go.kr K-apt
      AptListService4/getSigunguAptList4(sigunguCode) → kaptCode  (V3·2·무번호는 폐기, 4만 산다)
      AptBasisInfoServiceV5/getAphusBassInfoV5(kaptCode) → kaptdaCnt 세대수 · kaptDongCnt · kaptUsedate · kaptAddr(지번) · doroJuso · codeAptNm
      AptBasisInfoServiceV5/getAphusDtlInfoV5(kaptCode) → subwayLine/Station · kaptdWtimesub(도보) · kaptdPcnt(u) 주차 · educationFacility
      ⚠ K-apt 는 의무관리 단지(대략 150세대+·승강기 단지) 위주 — 소형 단지·빌라는 빠진다. 서울 ~3,800 · 성남 ~500.
  · 좌표: VWorld 지오코더(address getcoord, parcel → 실패 시 road)  keys/vworld.txt
  · 주변시설: VWorld 장소검색(search type=place, bbox 격자) — 카테고리로 거른다
      지하철역  '철도시설 > 철도/지하철 > 지하철역'  — 같은 역명이 노선 수만큼 중복 등록 → 중복수 = 노선수(환승 판별)
      학원      '입시·교과학원' · '외국어학원' (요가·태권도·음악은 '학원가'가 아니라 제외)
      종합병원  카테고리에 '종합병원' (상급종합 포함)
      대규모공원 이름 목록(MAJOR_PARKS)으로 검색해 좌표 확보 + 보조로 '공원 > 근린공원'
  · 가격: data/db/apt.sqlite (rtms.py) — 같은 시군구·동·정규화 단지명으로 매칭, 최근 12개월 ㎡당가·84㎡ 환산

점수 규칙(0~100, 화면에서 가중치 조절 → 총점은 프런트가 계산):
  edu   도보 600m 안 입시·외국어 학원 수 — 전체 단지 중 백분위
  hosp  최근접 종합병원 거리  ≤1km 100 · 2km 80 · 3km 60 · 5km 30 · 그 밖 10
  park  최근접 대규모 공원 거리 ≤0.5km 100 · 1km 80 · 1.5km 60 · 2.5km 40 · 그 밖 20 (+근린공원 300m 안 있으면 +10, 상한 100)
  tr    600m 안 역: 환승역(2노선+) 또는 서로 다른 역 2개 100 · 1역 65 · 600~1000m 1역 35 · 없음 0
  size  세대수 1500~2500 100 · 1000~1500/2500~3500 80 · 500~1000 60 · 300~500 40 · <300 20

캐시: data/db/locscore_cache.json {kapt:{code:{...}}, geo:{code:[x,y]}, poi:{...}} — 재실행 때 API 재호출 없음(--refresh 로 강제)
산출: data/db/locscore.json {asof, note, regions, apts:[...], pois_n}
사용: locscore.py [--refresh-kapt] [--refresh-poi] [--limit N]
cron: 월 1회 (1일 09:30) — 단지·시설은 느리게 변한다. 가격만 매번 새로 붙는다.
"""
import json, math, re, sqlite3, sys, time, urllib.parse, urllib.request
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DB = BASE / "data" / "db"
CACHE = DB / "locscore_cache.json"
OUT = DB / "locscore.json"
APT_DB = DB / "apt.sqlite"
sys.path.insert(0, str(BASE / "scripts"))
from rtms import REGIONS  # noqa: E402

ARGS = sys.argv[1:]
LIMIT = int(ARGS[ARGS.index("--limit") + 1]) if "--limit" in ARGS else 0

# 대상 시군구: 서울 전체 + 성남 3구 + 용인 수지
SGG = {c: n for c, n in REGIONS.items() if c.startswith("11") or c in ("41131", "41133", "41135", "41465")}

MAJOR_PARKS = ["한강공원", "올림픽공원", "서울숲", "북서울꿈의숲", "서울어린이대공원", "남산공원", "보라매공원", "월드컵공원",
               "하늘공원", "용산가족공원", "양재시민의숲", "선유도공원", "서서울호수공원", "푸른수목원", "서울식물원", "경의선숲길",
               "낙산공원", "응봉공원", "중랑캠핑숲", "길동생태공원", "일자산허브천문공원", "천호공원", "서울창포원", "노을공원",
               "매헌시민의숲", "탄천", "양재천", "안양천", "중랑천", "불광천", "홍제천", "성내천", "우이천", "도림천", "정릉천", "청계천",
               "분당중앙공원", "율동공원", "탄천종합운동장", "황새울공원", "성남시민공원", "희망대공원", "화랑공원", "낙생대공원",
               "운중천", "분당천", "수지체육공원", "고기리", "광교호수공원", "서울대공원", "과천중앙공원", "서울랜드"]


def _key(*names):
    for n in names:
        for p in (BASE / "keys" / n, BASE.parent / "SECURITY" / n):
            if p.exists():
                k = p.read_text(encoding="utf-8").strip()
                m = re.search(r"[A-Za-z0-9%+/=_-]{20,}", k)
                if m:
                    return m.group(0)
    raise SystemExit(f"키 없음: {names}")


DK = _key("data.go.kr.txt")
VK = _key("vworld.txt")


def get(u, tries=3, sleep=0.15):
    for k in range(tries):
        try:
            b = urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"}), timeout=40).read()
            s = re.sub(r"[\x00-\x1f]", " ", b.decode("utf-8", "ignore"))
            time.sleep(sleep)
            return json.loads(s)
        except Exception as e:
            if k == tries - 1:
                print(f"    ⚠ {e} · {u[:90]}")
                return None
            time.sleep(2 * (k + 1))


def load_cache():
    if CACHE.exists():
        try:
            return json.loads(CACHE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"kapt": {}, "geo": {}, "poi": {}}


def save_cache(c):
    CACHE.write_text(json.dumps(c, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


# ─────────── 1. K-apt 단지 ───────────
def kapt_list(sgg):
    out, page = [], 1
    while True:
        d = get(f"https://apis.data.go.kr/1613000/AptListService4/getSigunguAptList4?serviceKey={DK}"
                f"&sigunguCode={sgg}&pageNo={page}&numOfRows=500&_type=json")
        body = ((d or {}).get("response") or {}).get("body") or {}
        items = body.get("items") or []
        if isinstance(items, dict):
            items = items.get("item") or []
        out += items
        if len(out) >= int(body.get("totalCount") or 0) or not items:
            return out
        page += 1


def kapt_info(code):
    d = get(f"https://apis.data.go.kr/1613000/AptBasisInfoServiceV5/getAphusBassInfoV5?serviceKey={DK}&kaptCode={code}&_type=json")
    b = (((d or {}).get("response") or {}).get("body") or {}).get("item") or {}
    if not b:
        return None
    d2 = get(f"https://apis.data.go.kr/1613000/AptBasisInfoServiceV5/getAphusDtlInfoV5?serviceKey={DK}&kaptCode={code}&_type=json")
    t = (((d2 or {}).get("response") or {}).get("body") or {}).get("item") or {}
    num = lambda v: (float(v) if str(v).replace(".", "", 1).isdigit() else None)
    return {"nm": b.get("kaptName"), "addr": b.get("kaptAddr"), "road": b.get("doroJuso"), "typ": b.get("codeAptNm"),
            "hh": int(num(b.get("kaptdaCnt")) or 0), "dong": int(num(b.get("kaptDongCnt")) or 0),
            "use": str(b.get("kaptUsedate") or "")[:6], "bjd": b.get("bjdCode"), "top": b.get("kaptTopFloor"),
            "heat": b.get("codeHeatNm"), "hall": b.get("codeHallNm"), "sale": b.get("codeSaleNm"),
            "pk": int(num(t.get("kaptdPcnt")) or 0) + int(num(t.get("kaptdPcntu")) or 0),
            "sub": t.get("subwayLine"), "subst": t.get("subwayStation"), "subw": t.get("kaptdWtimesub"),
            "edu": t.get("educationFacility"), "welf": t.get("welfareFacility")}


# ─────────── 2. 좌표 ───────────
def geocode(addr, typ="parcel"):
    if not addr:
        return None
    d = get(f"https://api.vworld.kr/req/address?service=address&request=getcoord&version=2.0&crs=epsg:4326"
            f"&address={urllib.parse.quote(addr)}&refine=true&simple=false&format=json&type={typ}&key={VK}", sleep=0.08)
    r = (d or {}).get("response") or {}
    p = (r.get("result") or {}).get("point")
    return [round(float(p["x"]), 6), round(float(p["y"]), 6)] if p else None


def clean_jibun(addr):
    """K-apt kaptAddr '경기도성남분당구분당동92풍림아이원빌라' 처럼 붙어 있고 단지명이 꼬리로 붙는다 →
    시도/시군구/동/지번 복원. 실패하면 도로명으로."""
    a = str(addr or "").replace(" ", "")
    m = re.match(r"(서울특별시|서울|경기도)(.+?(?:구|시))?(?:(.+?(?:구)))?(.+?(?:동|가|읍|면)\d*)(산?\d+(?:-\d+)?)", a)
    if not m:
        return None
    sido = "서울특별시" if m.group(1).startswith("서울") else "경기도"
    g2 = m.group(2) or ""
    g3 = m.group(3) or ""
    # '성남분당구' → '성남시 분당구'
    if g2 and not g2.endswith("시") and g2.endswith("구") and sido == "경기도" and not g3:
        mm = re.match(r"(.+?)(분당구|수정구|중원구|수지구|기흥구|처인구)$", g2)
        if mm:
            g2, g3 = mm.group(1) + "시", mm.group(2)
    return " ".join(x for x in (sido, g2, g3, m.group(4), m.group(5)) if x)


# ─────────── 3. POI ───────────
def vsearch(q, bbox, maxpage=5):
    out = []
    for p in range(1, maxpage + 1):
        d = get(f"https://api.vworld.kr/req/search?service=search&request=search&version=2.0&crs=epsg:4326&size=1000"
                f"&page={p}&query={urllib.parse.quote(q)}&type=place&bbox={bbox}&format=json&errorformat=json&key={VK}", sleep=0.1)
        r = (d or {}).get("response") or {}
        items = (r.get("result") or {}).get("items") or []
        out += items
        tot = int((r.get("record") or {}).get("total") or 0)
        if not items or len(out) >= tot:
            break
    return out


def grid(x0, y0, x1, y1, step=0.04):
    x = x0
    while x < x1:
        y = y0
        while y < y1:
            yield f"{x:.3f},{y:.3f},{min(x+step, x1):.3f},{min(y+step, y1):.3f}"
            y += step
        x += step


AREAS = [(126.76, 37.42, 127.20, 37.72), (127.02, 37.28, 127.22, 37.48)]   # 서울 · 성남/수지(겹침 허용 → 중복 제거)


def collect_pois():
    st, hk, hp, pk = {}, {}, {}, {}
    key = lambda i: (i.get("title", "").strip(), round(float(i["point"]["x"]), 4), round(float(i["point"]["y"]), 4))
    cells = [b for a in AREAS for b in grid(*a)]
    print(f"[poi] 격자 {len(cells)}칸")
    for n, b in enumerate(cells, 1):
        for i in vsearch("지하철역", b, 2):
            if "지하철역" in i.get("category", ""):
                st.setdefault(key(i), i)
        for i in vsearch("학원", b, 6):
            c = i.get("category", "")
            if "입시·교과학원" in c or "외국어학원" in c:
                hk.setdefault(key(i), i)
        for i in vsearch("종합병원", b, 1):
            if "종합병원" in i.get("category", ""):
                hp.setdefault(key(i), i)
        for i in vsearch("공원", b, 3):
            if i.get("category", "").startswith("공원"):
                pk.setdefault(key(i), i)
        if n % 20 == 0:
            print(f"    {n}/{len(cells)} · 역 {len(st)} · 학원 {len(hk)} · 종합병원 {len(hp)} · 공원 {len(pk)}", flush=True)
    # 역: 같은 이름 + 300m 안이면 같은 역 → 노선수 = 레코드 수
    stations = []
    for (nm, x, y), i in st.items():
        hit = None
        for s in stations:
            if s["nm"] == nm and hav(x, y, s["x"], s["y"]) < 0.3:
                hit = s
                break
        if hit:
            hit["lines"] += 1
        else:
            stations.append({"nm": nm, "x": x, "y": y, "lines": 1})
    # 대규모 공원 — 이름 검색(서울·경기 안)
    majors = []
    for q in MAJOR_PARKS:
        for i in vsearch(q, "126.70,37.25,127.30,37.75", 1):
            t = i.get("title", "")
            if q in t and (i.get("category", "").startswith("공원") or "하천" in i.get("category", "") or "공원" in t or q in ("탄천", "양재천", "안양천", "중랑천", "불광천", "홍제천", "성내천", "우이천", "도림천", "정릉천", "청계천", "운중천", "분당천", "고기리")):
                majors.append({"nm": t, "x": round(float(i["point"]["x"]), 5), "y": round(float(i["point"]["y"]), 5)})
    print(f"[poi] 역 {len(stations)}(환승 {sum(1 for s in stations if s['lines']>=2)}) · 학원 {len(hk)} · 종합병원 {len(hp)} · 근린공원 {len(pk)} · 대규모공원 지점 {len(majors)}")
    pt = lambda i: [round(float(i["point"]["x"]), 5), round(float(i["point"]["y"]), 5)]
    return {"asof": date.today().isoformat(), "st": stations, "hk": [pt(i) for i in hk.values()],
            "hp": [{"nm": i["title"], "x": pt(i)[0], "y": pt(i)[1]} for i in hp.values()],
            "pk": [pt(i) for i in pk.values()], "mj": majors}


def hav(x1, y1, x2, y2):
    R = 6371.0
    p1, p2 = math.radians(y1), math.radians(y2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(x2 - x1) / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


# ─────────── 4. 가격 (apt.sqlite) ───────────
def norm(s):
    return re.sub(r"[^0-9a-z가-힣]", "", str(s or "").lower().replace("아파트", ""))


def load_prices():
    if not APT_DB.exists():
        return {}
    ym = (date.today().replace(day=1).replace(year=date.today().year - 1)).strftime("%Y%m")
    cx = sqlite3.connect(APT_DB)
    rows = cx.execute("SELECT a.sgg, a.umd, a.name, a.build_year, SUM(s.avg/s.ar*s.n), SUM(s.n), "
                      "SUM(CASE WHEN s.ar BETWEEN 80 AND 90 THEN s.avg*s.n END), SUM(CASE WHEN s.ar BETWEEN 80 AND 90 THEN s.n END) "
                      "FROM sale s JOIN apt a ON a.id=s.apt_id WHERE s.ym>=? AND s.ar>=20 AND s.avg>0 "
                      "GROUP BY a.id", (ym,)).fetchall()
    cx.close()
    by = defaultdict(list)
    for sgg, umd, nm, by_, wp, n, p84, n84 in rows:
        if sgg in SGG and n:
            by[(sgg, umd)].append((norm(nm), by_, wp / n, n, (p84 / n84) if n84 else None, n84 or 0))
    return by


def match_price(PR, sgg, umd, name, use):
    cands = PR.get((sgg, umd)) or []
    nn = norm(name)
    best = None
    for anm, by_, ppsm, n, p84, n84 in cands:
        if not anm or not nn:
            continue
        ok = anm == nn or (len(anm) >= 3 and (anm in nn or nn in anm))
        if not ok:
            continue
        if use and by_ and abs(int(use[:4]) - by_) > 2:
            continue
        sc = (anm == nn, n)
        if best is None or sc > best[0]:
            best = (sc, ppsm, n, p84, n84)
    return best[1:] if best else (None, 0, None, 0)


# ─────────── 5. 점수 ───────────
def score_hosp(d):
    return 100 if d <= 1 else 80 if d <= 2 else 60 if d <= 3 else 30 if d <= 5 else 10


def score_park(d, near_small):
    s = 100 if d <= 0.5 else 80 if d <= 1 else 60 if d <= 1.5 else 40 if d <= 2.5 else 20
    return min(100, s + (10 if near_small else 0))


def score_size(hh):
    if not hh:
        return None
    return 100 if 1500 <= hh <= 2500 else 80 if 1000 <= hh <= 3500 else 60 if hh >= 500 else 40 if hh >= 300 else 20


def main():
    C = load_cache()
    # 1) 단지
    if "--refresh-kapt" in ARGS or not C["kapt"]:
        codes = {}
        for sgg, nm in SGG.items():
            lst = kapt_list(sgg)
            for i in lst:
                codes[i["kaptCode"]] = (sgg, i.get("kaptName"), i.get("bjdCode"), i.get("as3"))
            print(f"[kapt] {nm} {len(lst)}")
        C["codes"] = {k: list(v) for k, v in codes.items()}
        save_cache(C)
    codes = C.get("codes") or {}
    todo = [c for c in codes if c not in C["kapt"]]
    if LIMIT:
        todo = todo[:LIMIT]
    print(f"[kapt] 단지 {len(codes)} · 상세 미수집 {len(todo)}")
    for n, c in enumerate(todo, 1):
        info = kapt_info(c)
        C["kapt"][c] = info or {}
        if n % 100 == 0:
            print(f"    {n}/{len(todo)}", flush=True)
            save_cache(C)
    save_cache(C)
    # 2) 좌표
    todo = [c for c, v in C["kapt"].items() if v and c not in C["geo"]]
    print(f"[geo] 미지오코딩 {len(todo)}")
    for n, c in enumerate(todo, 1):
        v = C["kapt"][c]
        pt = geocode(clean_jibun(v.get("addr"))) or geocode(re.sub(r"(로|길)(\d)", r"\1 \2", str(v.get("road") or "")), "road") \
            or geocode(clean_jibun(v.get("addr")) and clean_jibun(v.get("addr")).rsplit(" ", 1)[0])
        C["geo"][c] = pt or []
        if n % 200 == 0:
            print(f"    {n}/{len(todo)}", flush=True)
            save_cache(C)
    save_cache(C)
    # 3) POI
    if "--refresh-poi" in ARGS or not C["poi"]:
        C["poi"] = collect_pois()
        save_cache(C)
    P = C["poi"]
    # 4) 점수
    PR = load_prices()
    apts = []
    for c, v in C["kapt"].items():
        pt = C["geo"].get(c)
        if not v or not pt or not v.get("hh"):
            continue
        sgg, _nm, bjd, dongnm = codes.get(c, (None, None, None, None))
        if sgg not in SGG:
            continue
        x, y = pt
        # 역
        near = [(hav(x, y, s["x"], s["y"]), s) for s in P["st"]]
        near = [(d, s) for d, s in near if d <= 1.0]
        in600 = [(d, s) for d, s in near if d <= 0.6]
        if any(s["lines"] >= 2 for d, s in in600) or len({s["nm"] for d, s in in600}) >= 2:
            tr = 100
        elif in600:
            tr = 65
        elif near:
            tr = 35
        else:
            tr = 0
        st_show = sorted(near, key=lambda a: a[0])[:3]
        # 학원
        edu_n = sum(1 for hx, hy in P["hk"] if abs(hx - x) < 0.008 and abs(hy - y) < 0.006 and hav(x, y, hx, hy) <= 0.6)
        # 병원
        hd, hn = min(((hav(x, y, h["x"], h["y"]), h["nm"]) for h in P["hp"]), default=(99, None))
        # 공원
        pd_, pn = min(((hav(x, y, m["x"], m["y"]), m["nm"]) for m in P["mj"]), default=(99, None))
        small = any(abs(px - x) < 0.005 and abs(py - y) < 0.004 and hav(x, y, px, py) <= 0.3 for px, py in P["pk"])
        umd = (dongnm or "").strip() or None
        ppsm, ntr, p84, n84 = match_price(PR, sgg, umd, v.get("nm"), v.get("use"))
        apts.append({
            "k": c, "nm": v.get("nm"), "sgg": SGG[sgg], "umd": umd, "x": x, "y": y,
            "hh": v.get("hh"), "dg": v.get("dong"), "use": v.get("use"), "typ": v.get("typ"),
            "pk": v.get("pk") or None, "pkr": round(v["pk"] / v["hh"], 2) if v.get("pk") and v.get("hh") else None,
            "edu_n": edu_n, "hosp_d": round(hd, 2), "hosp": hn, "park_d": round(pd_, 2), "park": pn, "park_s": 1 if small else 0,
            "st": [{"nm": s["nm"], "d": round(d, 2), "ln": s["lines"]} for d, s in st_show],
            "s_hosp": score_hosp(hd), "s_park": score_park(pd_, small), "s_tr": tr, "s_size": score_size(v.get("hh")),
            "ppsm": round(ppsm, 1) if ppsm else None, "ntr": ntr, "p84": round(p84, 2) if p84 else None, "n84": n84,
            "p84e": round(ppsm * 84, 2) if ppsm else None,
        })
    # 학원 백분위
    vals = sorted(a["edu_n"] for a in apts)
    import bisect
    for a in apts:
        a["s_edu"] = round(100 * bisect.bisect_left(vals, a["edu_n"]) / max(1, len(vals) - 1))
    apts.sort(key=lambda a: (a["sgg"], a["nm"]))
    out = {"asof": datetime.now().strftime("%Y-%m-%d %H:%M"),
           "src": "K-apt 단지정보(국토부) · VWorld 지오코더/장소검색(국토부) · 국토부 실거래가(apt.sqlite)",
           "note": ("입지 5요소(고준석) 규칙 점수. 교육=600m 내 입시·외국어 학원 수 백분위, 편의=최근접 종합병원 거리, "
                    "자연=대규모 공원(수동 목록) 거리+근린공원, 교통=600m 내 환승역/역 수, 규모=세대수 1,500~2,500 만점. "
                    "K-apt 등록 단지(의무관리·대체로 150세대+)만 포함. 가격=최근 12개월 실거래 ㎡당가(단지명 매칭)."),
           "regions": sorted({a["sgg"] for a in apts}),
           "poi_asof": P.get("asof"), "poi_n": {"st": len(P["st"]), "hk": len(P["hk"]), "hp": len(P["hp"]), "mj": len(P["mj"])},
           "apts": apts}
    OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    pr = sum(1 for a in apts if a["ppsm"])
    print(f"[loc] ✅ 단지 {len(apts)} (가격 매칭 {pr}) → {OUT} ({OUT.stat().st_size//1024}KB)")


if __name__ == "__main__":
    main()
