#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""rehub.py — 부동산 통합차트용 지표 허브 (2026-08-16 신설)

목적: 흩어져 있는 부동산 지표를 **한 파일·한 시간축**으로 모아, 화면에서 아무거나 골라
      겹쳐 볼 수 있게 한다. 지금까지는 카드마다 소스가 달라 "가격이 먼저 꺾였나,
      거래량이 먼저 꺾였나" 를 눈으로 맞춰볼 수가 없었다.

시간축 통일
  전부 **월(YYYYMM)** 축에 맞춘다. 분기(K-HAI)·연간(K-HOI) 지표는 해당 기간의 각 달에
  같은 값을 채워 계단 모양이 된다(meta.cycle 로 화면에 그 사실을 표시한다).
  값을 만들어내는 보간은 하지 않는다 — 없는 기간은 null 로 둔다.

수집 (실측 확인 2026-08-16)
  ── 한국부동산원 (KOSIS 408) 월 2006.01~
     rt_idx  DT_KAB_11672_S1   아파트 매매 실거래가격지수      (항목 T1)
     rt_avg  DT_KAB_11672_S15  아파트 매매 실거래 평균가격      (만원)
     rt_med  DT_KAB_11672_S16  아파트 매매 실거래 중위가격      (만원)
  ── 국토교통부 (KOSIS 116) 주택유형별 = 아파트만 뽑는다
     permit  DT_MLTM_1948  인허가(월별 누계 → 당월로 차분)
     start   DT_MLTM_5387  착공(월계)
     comp    DT_MLTM_5373  준공(월계)
     presale DT_MLTM_5557  분양실적(공동주택) 2013.01~
  ── 한국주택금융공사 Open API (houstat.hf.go.kr)
     khai    T186503126543136  주택구입부담지수  분기 2004~
     khoi    T185033126522938  주택구입물량지수  연간 2012~
  ── 이미 수집해 둔 파일에서 합류(중복 호출 안 함)
     csi     realestate.json  주택가격전망CSI (ECOS)
     trade   htrade.json      아파트 매매거래건수 (시도) + rtms.json (시군구)
     unsold / unsold_done  molit.json  미분양 / 준공후 미분양 (시군구까지)

산출: data/db/rehub.json
  {asof, src, meta:{key:{label,unit,axis,cycle,src,note}}, t:[YYYYMM], regions:[...],
   d:{key:{지역:[값|null]}}}

사용: rehub.py [--full]     (--full 은 KOSIS 를 2006년부터 다시 받는다)
cron: 45 7 * * *           (앞선 htrade·molit 수집이 끝난 뒤)
"""
import json, socket, sys, time, urllib.parse, urllib.request
from datetime import datetime
from pathlib import Path

socket.setdefaulttimeout(40)

BASE = Path(__file__).resolve().parent.parent
DB   = BASE / "data" / "db"
OUT  = DB / "rehub.json"
FULL = "--full" in sys.argv
NOW  = datetime.now()

SIDO = ["전국", "서울", "부산", "대구", "인천", "광주", "대전", "울산", "세종",
        "경기", "강원", "충북", "충남", "전북", "전남", "경북", "경남", "제주"]

# ── 지표 정의 — axis 는 화면 기본값(L=좌축, R=우축). 사용자가 바꿀 수 있다.
META = {
    "csi":     ("주택가격전망CSI",        "100기준", "L", "M", "한국은행 ECOS",
                "100 이상이면 1년 후 집값 상승 전망 우세"),
    "rt_idx":  ("매매실거래가격지수",      "지수",   "L", "M", "한국부동산원",
                "실제 거래된 아파트만 집계 — 표본이 명확해 전문가들이 선호"),
    "rt_avg":  ("평균매매가격",           "만원/㎡", "R", "M", "한국부동산원",
                "아파트 매매 실거래 평균가격 — 원자료 단위가 ㎡당이다(총액 아님)"),
    "rt_med":  ("중위매매가격",           "만원/㎡", "R", "M", "한국부동산원",
                "가격을 순서대로 늘어놨을 때 한가운데 값 — 고가 거래에 덜 흔들린다 · ㎡당"),
    "supply":  ("매매수급동향",           "0~200", "L", "M", "한국부동산원 R-ONE",
                "100 미만이면 공급우위(팔려는 사람이 많다), 초과면 수요우위"),
    "trade":   ("매매거래건수",           "건",     "R", "M", "한국부동산원·국토부",
                "아파트 매매 신고 건수"),
    "permit":  ("인허가실적",             "호",     "R", "M", "국토교통부",
                "아파트 · 월별 누계를 당월로 차분한 값"),
    "start":   ("착공실적",               "호",     "R", "M", "국토교통부", "아파트"),
    "comp":    ("준공실적",               "호",     "R", "M", "국토교통부", "아파트"),
    "presale": ("분양실적",               "호",     "R", "M", "국토교통부",
                "공동주택 분양 · 2013.01~"),
    "unsold":  ("미분양주택",             "호",     "R", "M", "국토교통부", ""),
    "unsold_done": ("준공후 미분양",      "호",     "R", "M", "국토교통부",
                "악성 미분양 — 다 지어놓고 안 팔린 물량"),
    "khai":    ("주택구입부담지수(K-HAI)", "지수",   "L", "Q", "한국주택금융공사",
                "100 = 중간소득 가구가 중간가격 주택 살 때 소득의 25%를 원리금으로 쓴다는 뜻 · 분기"),
    "khoi":    ("주택구입물량지수(K-HOI)", "%",     "L", "Y", "한국주택금융공사",
                "중위소득 가구가 살 수 있는 주택 물량 비중 · 연간"),
    # (2026-08-16 추가) 금리 — 지역 구분이 없는 거시 변수라 어느 지역을 골라도 같은 선이 깔린다.
    # 부동산 지표의 '원인' 쪽이라 배경으로 깔아두고 시차를 보는 용도다.
    "rate_kr": ("한국 기준금리",           "%",     "L", "M", "한국은행 ECOS",
                "한국은행 기준금리 · 전 지역 공통"),
    "rate_us": ("미국 정책금리",           "%",     "L", "M", "FRED",
                "연방기금금리(FEDFUNDS) 월평균 · 전 지역 공통"),
}
GLOBAL_KEYS = ("rate_kr", "rate_us", "csi")     # 지역 구분 없이 '전국' 하나만 있는 지표


def _key(*names):
    for n in names:
        for p in [BASE / "keys" / n, Path("D:/claudeCowork/SECURITY") / n] + \
                 sorted(Path("/sessions").glob(f"*/mnt/claudeCowork/SECURITY/{n}")):
            try:
                k = Path(p).read_text(encoding="utf-8").strip()
                if k:
                    return k
            except Exception:
                pass
    return ""


KOSIS = _key("kosis.txt", "kosis.kr.txt")
HFKEY = _key("hf.txt", "houstat.hf.go.kr.txt")
Y0 = "200601" if FULL else f"{NOW.year - 3}01"
YM_NOW = NOW.strftime("%Y%m")


def get(url, tries=3):
    for k in range(tries):
        try:
            return json.loads(urllib.request.urlopen(url, timeout=40).read())
        except Exception as e:
            if k == tries - 1:
                print(f"    ⚠ {e}")
                return None
            time.sleep(3 * (k + 1))
    return None


def num(v):
    s = str(v if v is not None else "").replace(",", "").strip()
    if s in ("", "-", "X", "x", "None", "null"):
        return None
    try:
        return float(s)
    except Exception:
        return None


# ══════════════════ KOSIS ══════════════════
KAPI = "https://kosis.kr/openapi/Param/statisticsParameterData.do"
KMETA = "https://kosis.kr/openapi/statisticsData.do"


def kosis_regions(org, tbl, obj_kw="행정구역", itm=None):
    """통계표의 지역 코드 → 표시명. 표마다 코드가 달라 이름으로 맞춘다.

    (2026-08-16 수정) 같은 이름이 코드 두 개로 나오는 표가 있다.
      실측: DT_KAB_11672_S15/S16 은 '서울' 이 030(실데이터)과 200(빈 그룹 헤더) 둘 다다.
      먼저 걸린 200 을 잡는 바람에 서울 평균·중위가가 통째로 비었다.
      → 이름이 겹치면 **한 달치를 실제로 찔러보고 값이 나오는 코드**를 고른다.
      자식 코드(UP_ITM_ID 있음)를 먼저 시험해 호출 수를 줄인다.
    """
    u = (f"{KMETA}?method=getMeta&apiKey={KOSIS}&orgId={org}&tblId={tbl}"
         f"&type=ITM&format=json&jsonVD=Y")
    d = get(u) or []
    cand = {}
    if isinstance(d, list):
        for r in d:
            if obj_kw in str(r.get("OBJ_NM") or ""):
                nm = str(r.get("ITM_NM") or "").strip()
                if nm in SIDO:
                    cand.setdefault(nm, []).append((r["ITM_ID"], bool(r.get("UP_ITM_ID"))))
    out = {}
    for nm, lst in cand.items():
        if len(lst) == 1 or not itm:
            out[lst[0][0]] = nm
            continue
        lst.sort(key=lambda x: not x[1])                 # 자식 코드 먼저
        for code, _ in lst:
            q = {"method": "getList", "apiKey": KOSIS, "itmId": itm, "objL1": code,
                 "format": "json", "jsonVD": "Y", "prdSe": "M",
                 "startPrdDe": YM_NOW, "endPrdDe": YM_NOW, "orgId": org, "tblId": tbl}
            # 최신월은 아직 공표 전일 수 있어 1년 전으로 찔러본다
            q["startPrdDe"] = q["endPrdDe"] = f"{int(YM_NOW[:4]) - 1}{YM_NOW[4:]}"
            r = get(KAPI + "?" + urllib.parse.urlencode(q))
            time.sleep(0.3)
            if isinstance(r, list) and r:
                out[code] = nm
                break
        else:
            out[lst[0][0]] = nm
    return out


def kosis_series(org, tbl, itm, regs, objn=1, fixed=None, cumulative=False, grp=None):
    """{지역: {ym: 값}} — 지역 코드를 하나씩 돌며 월별로 받는다.

    fixed: 지역 말고 고정해야 하는 축들 {objL2: 코드, ...}. 국토부 표는
           시도 × 대분류 × 중분류 × 소분류 구조라 '아파트' 를 세 축에서 다 골라야 한다.
    cumulative: 연초 누계로 공표되는 표(인허가)는 당월 값으로 차분한다.
                1월은 그대로, 그 외는 전월 대비 차이. 이걸 빼먹으면 12월 값이
                연간 합계라 월별 그래프가 우상향 톱니로 나온다.
    """
    acc = {}
    SUDO = ("서울", "인천", "경기")
    for code, name in regs.items():
        q = {"method": "getList", "apiKey": KOSIS, "itmId": itm, f"objL{objn}": code,
             "format": "json", "jsonVD": "Y", "prdSe": "M",
             "startPrdDe": Y0, "endPrdDe": YM_NOW, "orgId": org, "tblId": tbl}
        q.update(fixed or {})
        if grp:                                   # 지역마다 상위 그룹이 다른 표(분양실적)
            g = grp.get(name) or grp["_수도권" if name in SUDO else "_지방"]
            q["objL1"] = g
        d = get(KAPI + "?" + urllib.parse.urlencode(q))
        if isinstance(d, list):
            mp = {r["PRD_DE"]: num(r.get("DT")) for r in d if r.get("PRD_DE")}
            if cumulative:
                mp = decum(mp)
            acc[name] = mp
        time.sleep(0.5)
    return acc


def decum(mp):
    """연초 누계 → 당월. (실측: 인허가 1948 은 1월 1.6만 → 12월 38만으로 쌓인다)"""
    out = {}
    for ym in sorted(mp):
        v = mp[ym]
        if v is None:
            continue
        if ym[4:] == "01":
            out[ym] = v
            continue
        pv = mp.get(f"{ym[:4]}{int(ym[4:]) - 1:02d}")
        out[ym] = None if pv is None else max(0.0, v - pv)
    return out


# 국토부 주택유형별 표 — '아파트' 를 대·중·소분류에서 모두 골라야 한다(실측 2026-08-16)
MOLIT = {
    "permit":  dict(tbl="DT_MLTM_1948", itm="13103871090T1", pre="13102871090",
                    fixed={"objL2": "B.0006", "objL3": "C.0007", "objL4": "D.0009"},
                    cumulative=True),
    "start":   dict(tbl="DT_MLTM_5387", itm="13103766969T1", pre="13102766969",
                    fixed={"objL2": "B.0006", "objL3": "C.0007", "objL4": "D.0008"}),
    "comp":    dict(tbl="DT_MLTM_5373", itm="13103766973T1", pre="13102766973",
                    fixed={"objL2": "B.0006", "objL3": "C.0007", "objL4": "D.0008"}),
    # 분양실적은 (구분1=수도권/지방) × (구분2=시도) 구조라 시도마다 상위 그룹이 다르다.
    # '합계'+서울 조합은 빈 응답이 온다(실측 2026-08-16).
    "presale": dict(tbl="DT_MLTM_5557", itm="13103133605T1", pre="13102133605",
                    fixed={"objL3": "13102133605C.0001"}, regn=2,
                    grp={"전국": "13102133605A.0001",
                         "_수도권": "13102133605A.0002", "_지방": "13102133605A.0003"}),
}


def _molit_regions(tbl, pre, regn):
    """국토부 표의 지역축(시도명/구분1·2)에서 시도만 골라낸다. '총계'는 전국으로 본다."""
    u = (f"{KMETA}?method=getMeta&apiKey={KOSIS}&orgId=116&tblId={tbl}"
         f"&type=ITM&format=json&jsonVD=Y")
    d = get(u) or []
    want = {"전국": "전국", "총계": "전국", "합계": "전국", "소계": None}
    out, seen = {}, set()
    for r in d if isinstance(d, list) else []:
        nm = str(r.get("ITM_NM") or "").strip()
        code = str(r.get("ITM_ID") or "")
        # 지역축 판별 — 코드 접두 + 축 문자(A/B) 로 구분한다
        axis = code[len(pre):len(pre) + 1] if code.startswith(pre) else ""
        if regn == 1 and axis != "A":
            continue
        if regn == 2 and axis != "B":
            continue
        nm2 = want.get(nm, nm)
        if nm2 and nm2 in SIDO and nm2 not in seen:
            out[code] = nm2
            seen.add(nm2)
    return out


# ══════════════════ 한국부동산원 R-ONE ══════════════════
RAPI = "https://www.reb.or.kr/r-one/openapi/SttsApiTblData.do"


def rone_series(statbl):
    """{지역: {ym: 값}} — R-ONE 은 시점 하나씩 조회. 시도명만 남긴다.
    (KOSIS 의 수급동향은 2025-03 에서 갱신이 멈춰 있어 R-ONE 을 직접 쓴다 — 실측 2026-08-16)"""
    RKEY = _key("reb.txt", "reb.or.kr.txt")
    if not RKEY:
        print("    ⚠ R-ONE 키 없음")
        return {}
    acc = {}
    y0 = 2012 if FULL else NOW.year - 5
    for y in range(y0, NOW.year + 1):
        for m in range(1, 13):
            if y == NOW.year and m > NOW.month:
                break
            ym = f"{y}{m:02d}"
            d = get(f"{RAPI}?STATBL_ID={statbl}&DTACYCLE_CD=MM"
                    f"&WRTTIME_IDTFR_ID={ym}&Type=json&KEY={RKEY}")
            rows = None
            if isinstance(d, dict):
                for v in d.values():
                    if isinstance(v, list):
                        for e in v:
                            if isinstance(e, dict) and "row" in e:
                                rows = e["row"]
            for r in rows or []:
                nm = str(r.get("CLS_NM") or "").strip()
                v = num(r.get("DTA_VAL"))
                if nm in SIDO and v is not None:
                    acc.setdefault(nm, {})[ym] = round(v, 2)
            time.sleep(0.2)
    return acc


# ══════════════════ 한국주택금융공사 ══════════════════
HFAPI = "https://houstat.hf.go.kr/research/openapi/SttsApiTblData.do"


def hf_series(statbl, cycle, periods):
    """{지역: {기간: 값}} — 기간을 하나씩 조회한다(한 번에 한 시점만 준다)."""
    acc = {}
    for p in periods:
        u = (f"{HFAPI}?STATBL_ID={statbl}&DTACYCLE_CD={cycle}"
             f"&WRTTIME_IDTFR_ID={p}&Type=json&key={HFKEY}")
        d = get(u)
        try:
            rows = d["SttsApiTblData"][1]["row"]
        except Exception:
            continue
        for r in rows:
            nm = str(r.get("ITM_NM") or "").strip()
            v = num(r.get("DTA_VAL"))
            if nm in SIDO and v is not None:
                acc.setdefault(nm, {})[p] = v
        time.sleep(0.3)
    return acc


def quarters(y0):
    """HF 분기 식별자는 YYYY + **분기번호(01~04)** 다. 분기 시작월(01/04/07/10)이 아니다.
    (실측 2026-08-16: 202601·202504 는 응답 O, 202607·202610 은 빈 응답.
     분기 시작월로 착각해 07·10 을 요청하는 바람에 매년 2·3분기가 통째로 비어
     K-HAI 그래프가 빗살처럼 끊겨 보였다.)"""
    out = []
    for y in range(y0, NOW.year + 1):
        for q in range(1, 5):
            if y == NOW.year and q > (NOW.month + 2) // 3:
                break
            out.append(f"{y}{q:02d}")
    return out


def q_to_months(pid):
    """YYYY+분기번호 → 그 분기에 해당하는 세 달"""
    y, q = int(pid[:4]), int(pid[4:])
    if not 1 <= q <= 4:
        return []
    m0 = (q - 1) * 3 + 1
    return [f"{y}{m0+i:02d}" for i in range(3)]


# ══════════════════ 금리 (ECOS · FRED) ══════════════════
def ecos_monthly(stat, item):
    """한국은행 기준금리 등 ECOS 월별 단일 계열 → {ym: 값}"""
    k = _key("ecos.txt", "한국은행OPENAPI인증키.txt")
    if not k:
        print("    ⚠ ECOS 키 없음")
        return {}
    u = (f"https://ecos.bok.or.kr/api/StatisticSearch/{k}/json/kr/1/2000/"
         f"{stat}/M/{Y0}/{YM_NOW}/{item}")
    d = get(u) or {}
    rows = (d.get("StatisticSearch") or {}).get("row") or []
    return {r["TIME"]: num(r.get("DATA_VALUE")) for r in rows
            if len(str(r.get("TIME") or "")) == 6}


def fred_monthly(sid):
    """FRED 월별 단일 계열 → {ym: 값}. 키가 없으면 무인증 CSV 로 폴백한다."""
    k = _key("fred.key", "fred.txt")
    start = f"{Y0[:4]}-{Y0[4:]}-01"
    if k:
        u = (f"https://api.stlouisfed.org/fred/series/observations?series_id={sid}"
             f"&api_key={k}&file_type=json&observation_start={start}")
        d = get(u)
        if isinstance(d, dict) and d.get("observations"):
            return {o["date"][:4] + o["date"][5:7]: num(o.get("value"))
                    for o in d["observations"] if num(o.get("value")) is not None}
    try:                                            # 폴백 — fredgraph CSV(무인증)
        raw = urllib.request.urlopen(
            f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}&cosd={start}",
            timeout=40).read().decode("utf-8", "replace")
    except Exception as e:
        print(f"    ⚠ FRED {sid} 실패: {e}")
        return {}
    out = {}
    for line in raw.splitlines()[1:]:
        p = line.split(",")
        if len(p) >= 2 and num(p[1]) is not None:
            out[p[0][:4] + p[0][5:7]] = num(p[1])
    return out


# ══════════════════ 기존 파일 합류 ══════════════════
def load(name):
    p = DB / f"{name}.json"
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def main():
    if not KOSIS:
        raise SystemExit("KOSIS 키 없음")
    D = {}                                          # {key: {지역: {ym: v}}}

    print("[1/4] 한국부동산원 실거래 3종 (KOSIS 408)")
    for key, tbl, itm in [("rt_idx", "DT_KAB_11672_S1", "T1"),
                          ("rt_avg", "DT_KAB_11672_S15", "T001"),
                          ("rt_med", "DT_KAB_11672_S16", "T001")]:
        regs = kosis_regions(408, tbl, itm=itm)
        D[key] = kosis_series(408, tbl, itm, regs)
        print(f"    {META[key][0]:<16} 지역 {len(D[key])}")

    print("[2/5] 국토부 아파트 공급 4종 (KOSIS 116)")
    for key, cfg in MOLIT.items():
        regn = cfg.get("regn", 1)
        regs = _molit_regions(cfg["tbl"], cfg["pre"], regn)
        fixed = {k: (v if v.startswith(cfg["pre"]) else cfg["pre"] + v)
                 for k, v in cfg["fixed"].items()}
        D[key] = kosis_series(116, cfg["tbl"], cfg["itm"], regs, objn=regn,
                              fixed=fixed, cumulative=cfg.get("cumulative", False),
                              grp=cfg.get("grp"))
        print(f"    {META[key][0]:<16} 지역 {len(D[key])}")

    print("[3/5] 한국부동산원 R-ONE 매매수급동향(아파트)")
    D["supply"] = rone_series("A_2024_00076")
    print(f"    매매수급동향        지역 {len(D['supply'])}")

    print("[4/5] 주택금융공사 K-HAI·K-HOI")
    if HFKEY:
        khai = hf_series("T186503126543136", "QY", quarters(2004 if FULL else NOW.year - 5))
        D["khai"] = {r: {m: v for p, v in mp.items() for m in q_to_months(p)}
                     for r, mp in khai.items()}
        yrs = [str(y) for y in range(2012 if FULL else NOW.year - 8, NOW.year + 1)]
        khoi = hf_series("T185033126522938", "YY", yrs)
        D["khoi"] = {r: {f"{y}{m:02d}": v for y, v in mp.items() for m in range(1, 13)}
                     for r, mp in khoi.items()}
        print(f"    K-HAI 지역 {len(D['khai'])} · K-HOI 지역 {len(D['khoi'])}")
    else:
        D["khai"], D["khoi"] = {}, {}
        print("    ⚠ HF 키 없음 — 건너뜀")

    print("[5/6] 금리 2종 (ECOS·FRED)")
    D["rate_kr"] = {"전국": ecos_monthly("722Y001", "0101000")}
    D["rate_us"] = {"전국": fred_monthly("FEDFUNDS")}
    print(f"    한국 {len(D['rate_kr']['전국'])}개월 · 미국 {len(D['rate_us']['전국'])}개월")

    print("[6/6] 기존 수집분 합류 (csi·거래량·미분양)")
    re_ = load("realestate").get("series") or {}
    if re_.get("csi"):
        s = re_["csi"]
        D["csi"] = {"전국": {t: v for t, v in zip(s.get("t") or [], s.get("v") or [])}}
    ht = load("htrade")
    if ht.get("t"):
        D["trade"] = {r: {t: v for t, v in zip(ht["t"], a) if v is not None}
                      for r, a in (ht.get("apt") or {}).items()}
    ml = load("molit").get("series") or {}
    for key, mk in [("unsold", "unsold"), ("unsold_done", "unsold_done")]:
        s = ml.get(mk) or {}
        if s.get("t"):
            D[key] = {r: {t: v for t, v in zip(s["t"], a) if v is not None}
                      for r, a in (s.get("r") or {}).items()}
    for k in ("csi", "trade", "unsold", "unsold_done"):
        print(f"    {META[k][0]:<16} 지역 {len(D.get(k) or {})}")

    # ── 이전 결과와 병합 (2026-08-21 수정) ────────────────────────────────
    # --full 없이 돌면 최근 3년만 받는데, 예전엔 그걸 그대로 덮어써서 매일 07:45 크론이
    # 과거를 지웠다(실측: 금리·K-HAI 가 2023.01 부터만 남음). 새로 받은 달만 갈아끼운다.
    old = {}
    if OUT.exists():
        try:
            old = json.loads(OUT.read_text(encoding="utf-8"))
        except Exception:
            old = {}
    ot, od = old.get("t") or [], old.get("d") or {}
    for key in META:
        prev = od.get(key) or {}
        cur = D.get(key) or {}
        for reg, arr in prev.items():
            base = {ot[i]: arr[i] for i in range(min(len(ot), len(arr))) if arr[i] is not None}
            base.update(cur.get(reg) or {})          # 새 값이 이기게
            cur[reg] = base
        D[key] = cur

    # ── 월 축 통일 ──
    ts = sorted({t for k in D for r in D[k] for t in D[k][r] if len(str(t)) == 6})
    regions = []
    for r in SIDO:
        if any(r in (D.get(k) or {}) for k in D):
            regions.append(r)
    extra = sorted({r for k in D for r in D[k]} - set(regions))
    regions += extra                                   # 시군구(미분양·거래량)는 뒤에

    out = {
        "asof": NOW.strftime("%Y-%m-%d %H:%M"),
        "src": "한국부동산원·국토교통부(KOSIS) · 한국은행 ECOS · 한국주택금융공사",
        "note": "월 축으로 통일. 분기(K-HAI)·연간(K-HOI) 지표는 해당 기간 각 달에 같은 값이 들어가 계단 모양이 된다.",
        "meta": {k: {"label": v[0], "unit": v[1], "axis": v[2], "cycle": v[3],
                     "src": v[4], "note": v[5]} for k, v in META.items()},
        "t": ts,
        "regions": regions,
        "d": {k: {r: [mp.get(t) for t in ts] for r, mp in (D.get(k) or {}).items()}
              for k in META},
    }
    DB.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"  → {OUT} ({OUT.stat().st_size // 1024}KB) · {ts[0]}~{ts[-1]} · 지역 {len(regions)}")
    for k in META:
        n = len(out["d"].get(k) or {})
        a = (out["d"].get(k) or {}).get("전국") or []
        last = next(((ts[i], a[i]) for i in range(len(a) - 1, -1, -1) if a[i] is not None), None)
        print(f"    {META[k][0]:<20} 지역{n:>4} · 전국 최신 {last}")


def _first_itm(org, tbl):
    """항목이 하나뿐인 표가 많아 첫 항목 코드를 자동으로 집는다."""
    u = (f"{KMETA}?method=getMeta&apiKey={KOSIS}&orgId={org}&tblId={tbl}"
         f"&type=ITM&format=json&jsonVD=Y")
    d = get(u) or []
    for r in d:
        if str(r.get("OBJ_NM") or "") in ("항목", "항목별"):
            return r["ITM_ID"]
    return "T001"


if __name__ == "__main__":
    main()
