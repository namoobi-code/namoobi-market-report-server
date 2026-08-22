#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""relead.py — 부동산 선행지표 허브 + 시차 회귀 예측 (2026-08-21 신설)

목적
  통합차트(rehub)가 "지금까지 무슨 일이 있었나"를 보여준다면, 이 파일은
  **"그래서 앞으로 어디로 가나"** 를 본다. 집값보다 먼저 움직인다고 알려진
  거시·유동성·금융·증시·시장내부 지표를 한 축에 모으고, 각 지표가 실제로
  몇 개월 앞서는지를 데이터로 찾아 회귀로 앞을 그린다.

기준 계열(예측 대상)
  rt_med  아파트 매매 실거래 중위가격 (한국부동산원, ㎡당 만원, 2006~, 시도별)
  ※ KB 중간가는 공개 API 가 없다(KOSIS 미수록·데이터허브는 화면 렌더).
    실거래 기반이라 호가가 섞인 KB 보다 반응이 한 박자 늦을 수 있다는 점은 감안한다.

선행지표 (실측 확인 2026-08-21)
  ── 거시·유동성
     cli      OECD SDMX  KOR CLI(진폭조정)            월 1990~   전국 공통
     m2       ECOS 161Y006/BBHA00  M2 평잔(십억원→조원) 월 2003.10~ 전국 공통
     gdp      ECOS 200Y109/10601   명목 GDP(분기→월계단) 분기 1990~ 전국 공통
     fx       ECOS 731Y001/0000001 원/달러(일별→월평균)  월 1990~   전국 공통
     rate_kr  ECOS 722Y001/0101000 한국은행 기준금리     월 1999~   전국 공통
  ── 금융·대출
     mtg_bal  ECOS 151Y005/11100A0 주택관련대출 잔액(십억원→조원) 월 2007.12~
     mtg_rate ECOS 121Y006/BECBLA0302 주담대 금리(realestate.json 합류)
  ── 증시
     kospi    ECOS 901Y014/1070000 KOSPI 월말 종가       월 2000.02~
  ── 소득
     hdi_pc   KOSIS DT_1C96/T3 1인당 가계총처분가능소득(연간→월계단, 천원→만원) 시도별
  ── 부동산 내부 (이미 수집해 둔 파일에서 합류 — 중복 호출 안 함)
     hppci    realestate.json sale  전국주택매매가격지수
     jeonse   realestate.json js    주택전세가격지수
     csi      realestate.json csi   주택가격전망CSI
     trade / comp / unsold / supply  rehub.json (거래량·준공(=입주물량 대체)·미분양·수급)

  ※ 부동산 뉴스 감성지수는 **과거 아카이브가 없어** 지금은 넣지 않는다.
    news_pool 은 최근분만 보관하므로 소급 산출이 불가능하다(추정으로 채우지 않는다).

예측
  1) 시차 탐색: 지표별로 0~18개월 시차를 옮겨가며 목표와의 상관을 재고 최대 지점을 고른다.
  2) 회귀: 표준화 후 릿지(정규화)로 h=1..HZ 개월 앞을 각각 직접 회귀한다.
     목표는 가격 수준이 아니라 **전년비 로그성장률** — 수준 그대로 쓰면 우상향 추세에
     회귀가 끌려가 미래를 무조건 올려 그린다.
  3) 백테스트: 과거 시점으로 되돌아가 그때까지 자료만으로 12개월을 예측하고 실제와 비교한다.
     (MAPE·방향 적중률) 이 수치가 나쁘면 화면에서도 그대로 보여준다 — 좋게 포장하지 않는다.
  4) 구간: 백테스트 잔차 표준편차로 80% 밴드를 만든다.

산출: data/db/relead.json
사용: relead.py [--full]        cron: 55 7 * * *  (rehub 07:45 뒤)
"""
import json, math, socket, sys, urllib.parse, urllib.request
from datetime import datetime
from pathlib import Path

socket.setdefaulttimeout(45)
BASE = Path(__file__).resolve().parent.parent
DB = BASE / "data" / "db"
OUT = DB / "relead.json"
NOW = datetime.now()
FULL = "--full" in sys.argv
HZ = 12                      # 예측 지평(개월)
MAXLAG = 18                  # 시차 탐색 상한(개월)
SIDO = ["전국", "서울", "부산", "대구", "인천", "광주", "대전", "울산", "세종",
        "경기", "강원", "충북", "충남", "전북", "전남", "경북", "경남", "제주"]

META = {
    # key: (label, unit, group, cycle, src, note)
    "cli":      ("경기선행지수(CLI)", "지수", "거시", "M", "OECD",
                 "OECD 한국 경기선행지수(진폭조정) · 100 위면 확장 국면 · 전 지역 공통"),
    "m2":       ("통화량(M2)", "조원", "거시", "M", "한국은행 ECOS",
                 "평잔 원계열 · 시중에 풀린 돈의 총량 · 전 지역 공통"),
    "gdp":      ("명목 GDP", "조원", "거시", "Q", "한국은행 ECOS",
                 "분기 자료라 3개월 계단 · 전 지역 공통"),
    "fx":       ("원/달러 환율", "원", "거시", "M", "한국은행 ECOS",
                 "매매기준율 월평균 · 원화 약세(환율 상승)는 자산가격에 상승 압력 · 전 지역 공통"),
    "rate_kr":  ("한국 기준금리", "%", "거시", "M", "한국은행 ECOS", "전 지역 공통"),
    "mtg_bal":  ("주택담보대출 잔액", "조원", "금융", "M", "한국은행 ECOS",
                 "예금취급기관 주택관련대출 · 집 사는 데 실제로 쓰인 돈 · 전 지역 공통"),
    "mtg_rate": ("주담대 금리", "%", "금융", "M", "한국은행 ECOS", "신규취급 기준 · 전 지역 공통"),
    "kospi":    ("KOSPI", "p", "증시", "M", "한국은행 ECOS", "월말 종가 · 전 지역 공통"),
    "hdi_pc":   ("1인당 가계총처분가능소득", "만원", "소득", "Y", "국가데이터처 KOSIS",
                 "가계가 실제로 쓸 수 있는 돈 · 연간이라 12개월 계단 · 시도별"),
    "hppci":    ("전국주택매매가격지수", "지수", "부동산", "M", "한국부동산원", "전 지역 공통"),
    "jeonse":   ("주택전세가격지수", "지수", "부동산", "M", "한국부동산원", "전 지역 공통"),
    "csi":      ("주택가격전망CSI", "100기준", "심리", "M", "한국은행 ECOS",
                 "100 위면 1년 후 상승 전망 우세 · 전 지역 공통"),
    "trade":    ("매매거래건수", "건", "부동산", "M", "한국부동산원·국토부", "시도별"),
    "comp":     ("준공실적", "호", "부동산", "M", "국토교통부",
                 "입주물량 대체 지표 — 입주물량 자체는 공개 API 가 없다 · 시도별"),
    "unsold":   ("미분양주택", "호", "부동산", "M", "국토교통부", "시도별"),
    "supply":   ("매매수급동향", "0~200", "부동산", "M", "한국부동산원 R-ONE", "시도별"),
    # (2026-08-21 추가) 통합차트(rehub)에만 있던 지표 11종.
    #   C(16종) vs D(+공급 9종) vs E(+가격계열 2종) 백테스트 결과 E 가 6개 시험지역 전부 최적:
    #     서울 5.51%→4.10% · 경기 4.88%→3.65% · 광주 4.21%→2.56% (방향적중도 71%→79%, 76%→86%)
    "permit":   ("인허가실적", "호", "공급", "M", "국토교통부",
                 "아파트 · 착공보다 앞선 단계 — 2~3년 뒤 입주물량의 씨앗 · 시도별"),
    "start":    ("착공실적", "호", "공급", "M", "국토교통부", "아파트 · 시도별"),
    "presale":  ("분양실적", "호", "공급", "M", "국토교통부", "공동주택 · 2013.01~ · 시도별"),
    "unsold_done": ("준공후 미분양", "호", "공급", "M", "국토교통부",
                 "악성 미분양 — 다 짓고도 안 팔린 물량 · 시도별"),
    "khai":     ("주택구입부담지수(K-HAI)", "지수", "부담", "Q", "한국주택금융공사",
                 "100 = 중간소득 가구가 중간가격 주택 살 때 소득의 25%를 원리금으로 · 분기 · 시도별"),
    "khoi":     ("주택구입물량지수(K-HOI)", "%", "부담", "Y", "한국주택금융공사",
                 "중위소득 가구가 살 수 있는 주택 비중 · 연간 · 시도별"),
    "rate_us":  ("미국 정책금리", "%", "거시", "M", "FRED",
                 "연방기금금리 월평균 · 전 지역 공통"),
    "grdp":     ("지역내총생산(GRDP)", "조원", "소득", "Y", "국가데이터처 KOSIS",
                 "명목 · 그 지역 경제 규모 · 연간 · 시도별"),
    "grdp_pc":  ("1인당 GRDP", "만원", "소득", "Y", "국가데이터처 KOSIS", "명목 · 연간 · 시도별"),
    # 가격계열 자신 — 기준계열(중위가)과 같은 실거래 원천이라 사실상 자기회귀 항이다.
    #   '시차가 예측 기간 이상' 규칙이 걸려 있어 미래값을 쓰지는 않는다(과거 관측치만).
    "rt_idx":   ("매매실거래가격지수", "지수", "가격", "M", "한국부동산원",
                 "기준계열과 같은 실거래 원천 — 가격 자신의 과거 흐름(자기회귀 항) · 시도별"),
    "rt_avg":   ("평균매매가격", "만원/㎡", "가격", "M", "한국부동산원",
                 "실거래 평균가 · 중위가와 벌어지는 폭이 고가거래 쏠림을 알려준다 · 시도별"),
    # (2026-08-22 추가) 인덱서고 지표 목록 검토 후 원천(KOSIS)에서 직접 수집한 3종.
    #   전세가율은 갭투자 유인의 척도라 매매가 선행지표로 가장 널리 인용되고,
    #   세대수는 '집이 필요한 단위' 그 자체라 수요의 바닥을 이룬다.
    #   ※ 전월세전환율(DT_KAB_11671_N06)은 축 구조가 달라 이번엔 제외했다.
    "jr":       ("전세가율", "%", "가격", "M", "한국부동산원",
                 "매매가격 대비 전세가격 비율 · 높을수록 갭이 작아 매수 전환 유인이 커진다 · 시도별"),
    #   ※ 세대수(DT_1B040B3)는 objL1=ALL 도, 시도코드 지정도 빈 응답이라 보류했다.
    #     주기·코드 체계가 이 표만 다른 듯하다 — 추정으로 채우지 않고 다음에 다시 본다.
    "supply_j": ("전세수급동향", "0~200", "부동산", "M", "한국부동산원",
                 "100 미만이면 전세 공급우위 · 전세난은 매매 전환 압력으로 이어진다 · 시도별"),
}
GLOBAL_KEYS = {"cli", "m2", "gdp", "fx", "rate_kr", "rate_us", "mtg_bal", "mtg_rate",
               "kospi", "hppci", "jeonse", "csi"}
TARGET = "rt_med"
TARGET_LABEL = "아파트 매매 실거래 중위가격"


def get(url, tries=3):
    for k in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "namoobi-relead"})
            return json.loads(urllib.request.urlopen(req, timeout=45).read())
        except Exception as e:
            if k == tries - 1:
                print(f"    ⚠ {str(e)[:80]}")
                return None
    return None


def num(v):
    s = str(v if v is not None else "").replace(",", "").strip()
    if s in ("", "-", "X", "x", "None", "null"):
        return None
    try:
        return float(s)
    except Exception:
        return None


def _key(*names):
    for n in names:
        for p in [BASE / "keys" / n, Path("D:/claudeCowork/SECURITY") / n] + \
                 sorted(Path("/sessions").glob(f"*/mnt/claudeCowork/SECURITY/{n}")):
            try:
                t = Path(p).read_text(encoding="utf-8").strip()
                if t:
                    return t
            except Exception:
                pass
    return ""


ECOS = _key("ecos.txt", "한국은행OPENAPI인증키.txt")
KOSIS = _key("kosis.txt", "kosis.kr.txt")


def load(name):
    try:
        return json.loads((DB / f"{name}.json").read_text(encoding="utf-8"))
    except Exception:
        return {}


# ══════════════════ 수집 ══════════════════
def ecos(stat, item, cycle="M", s="199001", e=None, scale=1.0):
    """ECOS 월/분기 계열 → {YYYYMM: 값}. 분기는 그 분기 3개월에 같은 값을 채운다."""
    e = e or (NOW.strftime("%Y%m") if cycle == "M" else f"{NOW.year}Q4")
    u = (f"https://ecos.bok.or.kr/api/StatisticSearch/{ECOS}/json/kr/1/9000/"
         f"{stat}/{cycle}/{s}/{e}/{item}")
    d = get(u) or {}
    rows = (d.get("StatisticSearch") or {}).get("row") or []
    out = {}
    for r in rows:
        v = num(r.get("DATA_VALUE"))
        t = str(r.get("TIME") or "")
        if v is None:
            continue
        if cycle == "M" and len(t) == 6:
            out[t] = v * scale
        elif cycle == "Q" and "Q" in t:
            y, q = t.split("Q")
            for m in range(int(q) * 3 - 2, int(q) * 3 + 1):
                out[f"{y}{m:02d}"] = v * scale
    return out


def ecos_daily_monthly(stat, item, s="19900101"):
    """일별 계열 → 월평균. (환율은 ECOS 가 일별로만 준다)"""
    e = NOW.strftime("%Y%m%d")
    u = (f"https://ecos.bok.or.kr/api/StatisticSearch/{ECOS}/json/kr/1/40000/"
         f"{stat}/D/{s}/{e}/{item}")
    d = get(u) or {}
    rows = (d.get("StatisticSearch") or {}).get("row") or []
    acc = {}
    for r in rows:
        v, t = num(r.get("DATA_VALUE")), str(r.get("TIME") or "")
        if v is None or len(t) != 8:
            continue
        acc.setdefault(t[:6], []).append(v)
    return {k: sum(v) / len(v) for k, v in acc.items() if v}


def oecd_cli():
    """OECD SDMX 한국 CLI(진폭조정, 월). 무키·무로그인."""
    u = ("https://sdmx.oecd.org/public/rest/data/OECD.SDD.STES,DSD_STES@DF_CLI,4.1/"
         "KOR.M.LI...AA...H?startPeriod=1990-01&format=jsondata")
    d = get(u)
    if not d:
        return {}
    try:
        ds = d["data"]["dataSets"][0]["series"]
        obs_dim = d["data"]["structures"][0]["dimensions"]["observation"][0]["values"]
        periods = [v["id"] for v in obs_dim]
        ser = next(iter(ds.values()))["observations"]
        out = {}
        for idx, val in ser.items():
            p = periods[int(idx)]                     # 'YYYY-MM'
            if val and val[0] is not None:
                out[p.replace("-", "")] = float(val[0])
        return out
    except Exception as e:
        print("    ⚠ CLI 파싱 실패:", str(e)[:80])
        return {}


KAPI = "https://kosis.kr/openapi/Param/statisticsParameterData.do"
KOSIS_SIDO = {
    "전국": "전국", "서울특별시": "서울", "부산광역시": "부산", "대구광역시": "대구",
    "인천광역시": "인천", "광주광역시": "광주", "대전광역시": "대전", "울산광역시": "울산",
    "세종특별자치시": "세종", "경기도": "경기", "강원특별자치도": "강원", "강원도": "강원",
    "충청북도": "충북", "충청남도": "충남", "전북특별자치도": "전북", "전라북도": "전북",
    "전라남도": "전남", "경상북도": "경북", "경상남도": "경남", "제주특별자치도": "제주",
}


def kosis_annual(org, tbl, itm, scale=1.0, y0=2000):
    """연간 시도별 → {지역: {YYYYMM: 값}} (그 해 12개월 계단)."""
    q = {"method": "getList", "apiKey": KOSIS, "itmId": itm, "objL1": "ALL",
         "format": "json", "jsonVD": "Y", "prdSe": "Y", "startPrdDe": str(y0),
         "endPrdDe": str(NOW.year), "orgId": org, "tblId": tbl}
    d = get(KAPI + "?" + urllib.parse.urlencode(q))
    acc = {}
    if not isinstance(d, list):
        return acc
    for r in d:
        nm = KOSIS_SIDO.get(str(r.get("C1_NM") or "").strip())
        v, y = num(r.get("DT")), str(r.get("PRD_DE") or "")
        if not nm or v is None or len(y) != 4:
            continue
        mp = acc.setdefault(nm, {})
        for m in range(1, 13):
            mp[f"{y}{m:02d}"] = v * scale
    return acc


def kosis_monthly(org, tbl, itm, fixed=None, scale=1.0, y0="200601"):
    """KOSIS 월별 통계표 → {지역: {YYYYMM: 값}}.

    표마다 지역이 C1/C2 어디에 오는지 다르고, 이름도 '서울' 과 '서울특별시' 가 섞인다.
    → 행마다 C1~C3 을 훑어 아는 지역명이 나오면 그걸 쓴다(추정하지 않고 매칭만).
    """
    q = {"method": "getList", "apiKey": KOSIS, "itmId": itm, "format": "json",
         "jsonVD": "Y", "prdSe": "M", "startPrdDe": y0,
         "endPrdDe": NOW.strftime("%Y%m"), "orgId": str(org), "tblId": tbl}
    q.update(fixed or {})
    d = get(KAPI + "?" + urllib.parse.urlencode(q))
    acc = {}
    if not isinstance(d, list):
        return acc
    for r in d:
        nm = None
        for f in ("C1_NM", "C2_NM", "C3_NM"):
            v = str(r.get(f) or "").strip()
            if v in SIDO:
                nm = v
                break
            if v in KOSIS_SIDO:
                nm = KOSIS_SIDO[v]
                break
        v, t = num(r.get("DT")), str(r.get("PRD_DE") or "")
        if not nm or v is None or len(t) != 6:
            continue
        acc.setdefault(nm, {})[t] = v * scale
    return acc


def from_hub(hub, key):
    """rehub.json 의 {t, d:{key:{지역:[...]}}} → {지역: {YYYYMM: 값}}"""
    t = hub.get("t") or []
    src = (hub.get("d") or {}).get(key) or {}
    out = {}
    for reg, arr in src.items():
        mp = {t[i]: arr[i] for i in range(min(len(t), len(arr))) if arr[i] is not None}
        if mp:
            out[reg] = mp
    return out


def from_re(re_, key):
    s = (re_.get("series") or {}).get(key) or {}
    t, v = s.get("t") or [], s.get("v") or []
    return {"전국": {str(t[i]): v[i] for i in range(min(len(t), len(v))) if v[i] is not None}}


# ══════════════════ 예측 엔진 ══════════════════
# 지표를 그대로 쓸지(수준), 전년비로 바꿀지 — 단위가 다른 계열을 같은 회귀에 넣기 위한 구분.
#   금리·심리지수처럼 이미 '수준 자체가 의미'인 것은 그대로,
#   통화량·대출잔액처럼 계속 커지는 것은 전년비로 바꿔야 추세에 회귀가 끌려가지 않는다.
TRANS = {"rate_kr": "lvl", "rate_us": "lvl", "mtg_rate": "lvl", "csi": "lvl",
         "supply": "lvl", "cli": "lvl", "khai": "lvl", "khoi": "lvl",
         "jr": "lvl", "supply_j": "lvl"}
RIDGE = 1.0            # 표준화 기준 정규화 강도 — 표본이 200개 남짓이라 과적합 방지용
TOPK = 6               # 회귀에 넣을 지표 수 상한(상관 상위)
BT_ORIGINS = 48        # 백테스트로 되돌아가 볼 시점 수(개월)


SMOOTH = 3        # 기준계열 평활 창(개월)


def ma(seq, w=SMOOTH):
    """뒤쪽 w개월 이동평균(중심이 아니라 '지나간 w개월' — 미래를 쓰지 않는다).

    (2026-08-21) 실거래 중위가격은 그 달에 어떤 단지가 팔렸느냐에 따라 월별로 크게 튄다.
    원자료를 그대로 회귀에 넣으면 예측선이 톱니처럼 흔들려(서울 실측: 1635→1464→1428→1696)
    쓸 수 없다. 3개월 평균으로 잡음을 눌러 추세만 남긴다.
    """
    out = [None] * len(seq)
    for i in range(w - 1, len(seq)):
        win = seq[i - w + 1:i + 1]
        if all(v is not None for v in win):
            out[i] = sum(win) / w
    return out


def yoy_log(seq):
    """전년비 로그성장률. 12개월 전이 없거나 0 이하면 None."""
    out = [None] * len(seq)
    for i in range(12, len(seq)):
        a, b = seq[i], seq[i - 12]
        if a is None or b is None or a <= 0 or b <= 0:
            continue
        out[i] = math.log(a / b)
    return out


def step_log(prices, h):
    """i 시점 대비 h개월 뒤 로그변화율. 예측의 '목표' 다.

    (2026-08-21) 처음엔 전년비 성장률을 맞추고 12개월 전 값에 곱해 수준을 복원했는데,
    복원 기준이 되는 '12개월 전 값' 자체가 달마다 달라 예측선이 계단처럼 튀었다
    (서울 실측: 1390→1559→1514→1561). 마지막 관측치 하나를 공통 기준으로 삼아
    거기서 h개월 누적으로 얼마나 움직이는지를 직접 맞추면 경로가 매끄럽게 이어진다.
    """
    out = [None] * len(prices)
    for i in range(len(prices) - h):
        a, b = prices[i + h], prices[i]
        if a and b and a > 0 and b > 0:
            out[i] = math.log(a / b)
    return out


def transform(key, seq):
    return list(seq) if TRANS.get(key) == "lvl" else yoy_log(seq)


def corr(a, b):
    p = [(x, y) for x, y in zip(a, b) if x is not None and y is not None]
    n = len(p)
    if n < 24:
        return 0.0, n
    ax = sum(x for x, _ in p) / n
    by = sum(y for _, y in p) / n
    sxy = sum((x - ax) * (y - by) for x, y in p)
    sxx = math.sqrt(sum((x - ax) ** 2 for x, _ in p))
    syy = math.sqrt(sum((y - by) ** 2 for _, y in p))
    if sxx == 0 or syy == 0:
        return 0.0, n
    return sxy / (sxx * syy), n


# (2026-08-21) 지표 집합을 **전 지역 동일**하게 고정한다.
#   처음엔 지역마다 상관 상위 6개를 자동으로 골랐는데, 그러면 같은 전국 지표가
#   지역에 따라 뽑히기도 하고 빠지기도 해 "왜 서울은 오르고 부산은 내리나" 를
#   설명할 수 없었다(선택 자체가 과적합의 원천이기도 하다).
#   A/B 백테스트 실측(48시점·18개 시도): 고정 집합이 14개 지역에서 더 정확했다.
#     예) 경기 7.14%→5.83%, 대구 4.29%→3.43%, 울산 6.40%→5.73%
#   지역 차이는 이제 '지표 조합' 이 아니라 **그 지역 값·시차·회귀계수** 에서만 나온다.
#   그리고 '몇 개를 넣을 것인가' 도 실측으로 정했다.
#   B(핵심 7개) vs C(수집한 전 지표) 백테스트 — C 가 18개 지역 전부에서 우세했다.
#     서울 MAPE 7.20%→4.88%·방향 65.4%→76.3% · 전국 8.83%→5.14%·84.6%→86.0%
#     세종 11.81%→6.22% · 경기 7.96%→5.27%(방향 56.1%→77.2%)
#   변수를 늘리면 과적합이 걱정이지만, ① 릿지 정규화 ② 지평별 시차 재탐색
#   ③ 워크포워드 백테스트(그 시점 자료만) 로 걸러본 결과 늘리는 쪽이 실제로 나았다.
#   → 수집한 지표를 **전부** 쓴다. 지역 차이는 값·시차·회귀계수에서만 나온다.
FIXED_KEYS = list(META)


def best_lag_ge(x, y, h, maxlag=MAXLAG):
    """시차를 h 이상 구간에서만 고른다.

    지평 h 를 예측하려면 최소 h 개월 선행하는 값이어야 관측된 자료만으로 계산된다.
    고정 집합에서도 모든 지평을 커버하려면, 지표마다 '그 지평에 쓸 수 있는 시차 중
    상관이 가장 큰 것' 을 골라야 한다(지표를 버리는 대신 시차를 옮긴다).
    """
    bl, bc = h, 0.0
    for L in range(h, maxlag + 1):
        xs = [None] * L + x[:len(x) - L]
        c, _ = corr(xs, y)
        if abs(c) > abs(bc):
            bl, bc = L, c
    return bl, bc


def best_lag(x, y, maxlag=MAXLAG):
    """x 를 0~maxlag 개월 뒤로 밀며 y 와의 상관이 가장 큰 시차를 찾는다.
    lag=L 이면 'x 가 L 개월 선행' 이라는 뜻이다."""
    bl, bc, bn = 0, 0.0, 0
    for L in range(0, maxlag + 1):
        xs = [None] * L + x[:len(x) - L] if L else list(x)
        c, n = corr(xs, y)
        if abs(c) > abs(bc):
            bl, bc, bn = L, c, n
    return bl, bc, bn


def ridge_fit(X, y, lam=RIDGE):
    """표준화 → 릿지 정규방정식(가우스 소거). numpy 없이 순수 파이썬으로 푼다
    (서버 크론은 시스템 python3 로 도는 스크립트가 많아 의존성을 늘리지 않는다)."""
    n, p = len(X), len(X[0])
    mu = [sum(r[j] for r in X) / n for j in range(p)]
    sd = [math.sqrt(sum((r[j] - mu[j]) ** 2 for r in X) / n) or 1.0 for j in range(p)]
    Z = [[(r[j] - mu[j]) / sd[j] for j in range(p)] for r in X]
    ym = sum(y) / n
    yc = [v - ym for v in y]
    A = [[sum(Z[i][a] * Z[i][b] for i in range(n)) + (lam if a == b else 0.0)
          for b in range(p)] + [sum(Z[i][a] * yc[i] for i in range(n))] for a in range(p)]
    for c in range(p):                                   # 가우스 소거
        piv = max(range(c, p), key=lambda r: abs(A[r][c]))
        if abs(A[piv][c]) < 1e-12:
            return None
        A[c], A[piv] = A[piv], A[c]
        d = A[c][c]
        A[c] = [v / d for v in A[c]]
        for r in range(p):
            if r != c and A[r][c]:
                f = A[r][c]
                A[r] = [A[r][k] - f * A[c][k] for k in range(p + 1)]
    beta = [A[i][p] for i in range(p)]
    return {"mu": mu, "sd": sd, "ym": ym, "beta": beta}


def ridge_pred(m, row):
    return m["ym"] + sum(m["beta"][j] * (row[j] - m["mu"][j]) / m["sd"][j]
                         for j in range(len(row)))


def build_xy(feat, ytr, h, lags, keys, upto=None, force=None):
    """h 개월 앞 예측용 표본. 시차가 h 이상인 지표만 쓴다(미래 입력 금지).

    y_{i} 를 맞추는 데 쓰는 x 는 x_{i-(L-h)} — L 개월 선행 지표를 h 개월 앞 예측에
    쓰면 아직 (L-h) 개월치 여유가 남아 있다는 뜻이라, 관측된 값만으로 계산된다.
    """
    # (2026-08-21) 지표 선택은 '지평마다 다시' 한다.
    #   전체 상관 순으로 6개를 먼저 뽑아버리면 시차가 짧은 지표가 자리를 차지해,
    #   10~12개월 앞을 볼 때 쓸 지표가 하나도 안 남는 지역이 생겼다(울산·전남 실측 0개월).
    use = force if force is not None else sorted(
        [k for k in keys if lags[k]["lag"] >= h],
        key=lambda k: -abs(lags[k]["corr"]))[:TOPK]
    if not use:
        return [], [], []
    N = len(ytr) if upto is None else upto + 1
    X, Y = [], []
    for i in range(N):
        if ytr[i] is None:
            continue
        row, ok = [], True
        for k in use:
            j = i - (lags[k]["lag"] - h)
            v = feat[k][j] if 0 <= j < len(feat[k]) else None
            if v is None:
                ok = False
                break
            row.append(v)
        if ok:
            X.append(row)
            Y.append(ytr[i])
    return X, Y, use


def forecast(feat, ytr, prices, keys, t_last, horizons=HZ, upto=None):
    """t_last(관측 마지막 인덱스) 기준 1~horizons 개월 앞 가격 예측.

    지표 집합은 고정이고, 시차만 지평별로 [h, MAXLAG] 안에서 다시 고른다.
    """
    out = {}
    for h in range(1, horizons + 1):
        cut = (upto if upto is not None else t_last) + 1
        lags = {}
        for k in keys:
            L, c = best_lag_ge(feat[k][:cut], ytr[:cut], h)
            lags[k] = {"lag": L, "corr": round(c, 3)}
        # (2026-08-21) 예측 시점에 값이 비어 있는 지표는 **모델에서 빼고** 나머지로 다시 적합한다.
        #   예전엔 하나라도 비면 그 지평 전체를 버려서, 지역 지표(거래량·미분양 등)의
        #   공표 지연 한 칸 때문에 12개월 중 1~3개월만 그려지는 지역이 속출했다(전북 실측 1개월).
        elig = sorted(keys, key=lambda k: -abs(lags[k]["corr"]))
        avail = []
        for k in elig:
            j = t_last - (lags[k]["lag"] - h)
            if 0 <= j < len(feat[k]) and feat[k][j] is not None:
                avail.append(k)
            if len(avail) >= len(keys):
                break
        if not avail:
            continue
        # (2026-08-21) 표본이 짧은 지표 하나가 전체 회귀 표본을 잘라먹는 문제.
        #   회귀는 '모든 지표가 동시에 있는 달' 만 쓸 수 있다. 미분양은 2022년부터라
        #   전년비로 바꾸면 41개월뿐 — 이걸 넣는 순간 표본이 36 미만이 되어 그 지평이
        #   통째로 버려졌다(실측: 서울 예측 12개월 → 0개월).
        #   → 상관 낮은 쪽부터 하나씩 빼면서 표본이 충분해지는 조합을 찾는다.
        #   빼는 순서가 중요하다. 상관이 낮은 쪽부터 뺐더니 정작 표본을 깎는 지표(미분양)가
        #   상관이 높아 끝까지 남아 전 지평이 죽었다(실측: 대구·인천·광주 0개월).
        #   → 표본을 가장 많이 깎는 지표(관측 수 최소)부터 뺀다.
        sel = list(avail)
        X, Y, use = [], [], []
        while len(sel) >= 3:
            X, Y, use = build_xy(feat, step_log(prices, h), h, lags, keys,
                                 upto=upto, force=sel)
            if len(X) >= 60:
                break
            sel.remove(min(sel, key=lambda k: sum(1 for v in feat[k] if v is not None)))
        if len(X) < 36:
            continue
        m = ridge_fit(X, Y)
        if not m:
            continue
        row = [feat[k][t_last - (lags[k]["lag"] - h)] for k in use]
        g = ridge_pred(m, row)                       # 마지막 관측 대비 h개월 누적 로그변화율
        base = prices[t_last]
        if not base:
            continue
        out[h] = {"growth": g, "price": base * math.exp(g), "n": len(X), "k": len(use),
                  "lags": {k: lags[k]["lag"] for k in use},
                  "corrs": {k: lags[k]["corr"] for k in use}}
    return out


def lags_for(feat, ytr, keys, upto=None):
    """지표별 최적 선행시차. upto 를 주면 그 시점까지 자료만 쓴다(백테스트 정직성)."""
    out = {}
    for k in keys:
        x = feat[k] if upto is None else feat[k][:upto + 1]
        y = ytr if upto is None else ytr[:upto + 1]
        L, c, n = best_lag(x, y)
        out[k] = {"lag": L, "corr": round(c, 3), "n": n}
    return out


def backtest(feat, ytr, prices, keys, origins=BT_ORIGINS):
    """과거로 되돌아가 그때 자료만으로 12개월을 예측하고 실제와 비교.

    시차 탐색까지 그 시점 자료로 다시 한다 — 전체 기간으로 찾은 시차를 쓰면
    '미래를 알고 고른 시차' 가 되어 성적이 부풀려진다.
    """
    n = len(prices)
    errs = {h: [] for h in range(1, HZ + 1)}
    nerrs = {h: [] for h in range(1, HZ + 1)}      # 기준선: '지금 값 그대로' 라고 찍었을 때의 오차
    pairs = {h: [] for h in range(1, HZ + 1)}      # (예측 변화율, 실제 변화율) — 보정계수 산출용
    hits = {h: [0, 0] for h in range(1, HZ + 1)}
    for o in range(n - HZ - origins, n - HZ):
        if o < 60 or prices[o] is None:
            continue
        fc = forecast(feat, ytr, prices, keys, o, upto=o)
        for h, r in fc.items():
            act = prices[o + h] if o + h < n else None
            if act is None or act <= 0:
                continue
            errs[h].append(abs(r["price"] - act) / act)
            nerrs[h].append(abs(prices[o] - act) / act)
            pairs[h].append((math.log(r["price"] / prices[o]), math.log(act / prices[o])))
            up_p, up_a = r["price"] > prices[o], act > prices[o]
            hits[h][0] += 1
            hits[h][1] += 1 if up_p == up_a else 0
    by_h = {}
    for h in range(1, HZ + 1):
        e = errs[h]
        if not e:
            continue
        mape = sum(e) / len(e)
        sd = math.sqrt(sum((x - mape) ** 2 for x in e) / len(e)) if len(e) > 1 else 0.0
        nv = sum(nerrs[h]) / len(nerrs[h]) if nerrs[h] else None
        skill = max(0.0, min(1.0, 1 - mape / nv)) if nv else 0.0     # 단순 예측 대비 오차 감소율(참고 표시용)
        # 보정계수 = 백테스트에서 '예측한 변화율' 대비 '실제 일어난 변화율' 의 회귀 기울기.
        #   1 이면 예측폭이 딱 맞았다는 뜻, 0.5 면 절반만 실현됐다는 뜻이라 그만큼 줄여 그린다.
        #   오차 감소율(skill)을 그대로 쓰면 지나치게 눌려 예측선이 통째로 평평해진다(서울 실측 +0.0%).
        pr = pairs[h]
        calib = 0.0
        if len(pr) >= 12:
            mx = sum(a for a, _ in pr) / len(pr)
            my = sum(b for _, b in pr) / len(pr)
            vxx = sum((a - mx) ** 2 for a, _ in pr)
            cxy = sum((a - mx) * (b - my) for a, b in pr)
            if vxx > 1e-12:
                calib = max(0.0, min(1.5, cxy / vxx))
        by_h[h] = {"mape": round(mape * 100, 2), "sd": round(sd * 100, 2),
                   "naive": round(nv * 100, 2) if nv else None, "skill": round(skill, 3),
                   "calib": round(calib, 3),
                   "n": len(e), "hit": round(100 * hits[h][1] / hits[h][0], 1) if hits[h][0] else None}
    alle = [x for h in errs for x in errs[h]]
    allh = [hits[h] for h in hits if hits[h][0]]
    return {
        "by_h": by_h,
        "mape": round(100 * sum(alle) / len(alle), 2) if alle else None,
        "hit": round(100 * sum(a[1] for a in allh) / sum(a[0] for a in allh), 1) if allh else None,
        "n": len(alle),
        "origins": origins,
    }


def add_months(ym, k):
    y, m = int(ym[:4]), int(ym[4:])
    m += k
    y += (m - 1) // 12
    m = (m - 1) % 12 + 1
    return f"{y}{m:02d}"


# ══════════════════ main ══════════════════
def main():
    print(f"relead — 부동산 선행지표·예측 ({NOW:%Y-%m-%d %H:%M})")
    hub, re_ = load("rehub"), load("realestate")
    if not hub.get("t"):
        print("  ⚠ rehub.json 이 없다 — 먼저 rehub.py 를 돌려야 한다"); return 1

    D = {}
    print("[1/3] 거시·금융·증시 수집 (ECOS·OECD·KOSIS)")
    D["cli"] = {"전국": oecd_cli()}
    D["m2"] = {"전국": ecos("161Y006", "BBHA00", scale=1e-3)}          # 십억원 → 조원
    D["gdp"] = {"전국": ecos("200Y109", "10601", cycle="Q", s="1990Q1", scale=1e-3)}
    D["fx"] = {"전국": ecos_daily_monthly("731Y001", "0000001")}
    D["rate_kr"] = {"전국": ecos("722Y001", "0101000")}
    D["mtg_bal"] = {"전국": ecos("151Y005", "11100A0", scale=1e-3)}    # 십억원 → 조원
    D["kospi"] = {"전국": ecos("901Y014", "1070000")}
    D["hdi_pc"] = kosis_annual(101, "DT_1C96", "T3", scale=0.1)        # 천원 → 만원
    for k in ("cli", "m2", "gdp", "fx", "rate_kr", "mtg_bal", "kospi"):
        v = D[k]["전국"]
        print(f"    {META[k][0]:<18} {len(v):>4}개월" + (f"  최신 {sorted(v)[-1]}" if v else "  ⚠ 비었음"))
    print(f"    {META['hdi_pc'][0]:<18} 지역 {len(D['hdi_pc'])}")

    print("[1.5/3] 인덱서고 검토분 3종 (KOSIS 408·101)")
    D["jr"] = kosis_monthly(408, "DT_08002_07_007A", "T001", {"objL1": "ALL", "objL2": "0001"})
    D["supply_j"] = kosis_monthly(408, "DT_40803_N0009", "index", {"objL1": "01", "objL2": "ALL"})
    for k in ("jr", "supply_j"):
        v = D[k].get("서울") or {}
        print(f"    {META[k][0]:<12} 지역 {len(D[k]):>2}" + (f" · 서울 최신 {sorted(v)[-1]} {v[sorted(v)[-1]]:.1f}" if v else " ⚠ 비었음"))

    print("[2/3] 이미 수집된 파일에서 합류 (rehub·realestate)")
    D["mtg_rate"] = from_re(re_, "mtg")
    D["hppci"] = from_re(re_, "sale")
    D["jeonse"] = from_re(re_, "js")
    D["csi"] = from_re(re_, "csi")
    for k in ("trade", "comp", "unsold", "supply",
              "permit", "start", "presale", "unsold_done", "khai", "khoi",
              "rate_us", "grdp", "grdp_pc", "rt_idx", "rt_avg"):
        D[k] = from_hub(hub, k)
    tgt = from_hub(hub, TARGET)
    print(f"    기준계열 {TARGET_LABEL} 지역 {len(tgt)} · 합류 지표 {len([k for k in D if k not in GLOBAL_KEYS])}종")

    # ── 월 축 통일 (기준계열이 있는 구간만)
    ts = sorted({t for mp in tgt.values() for t in mp})
    if not ts:
        print("  ⚠ 기준계열 없음"); return 1
    T = []
    cur = ts[0]
    while cur <= ts[-1]:
        T.append(cur)
        cur = add_months(cur, 1)
    idx = {t: i for i, t in enumerate(T)}

    def arr(mp):
        a = [None] * len(T)
        for t, v in mp.items():
            if t in idx:
                a[idx[t]] = v
        return a

    regions = [r for r in SIDO if r in tgt]
    print(f"[3/3] 시차 탐색 + 회귀 예측 + 백테스트 — 축 {T[0]}~{T[-1]} ({len(T)}개월) · 지역 {len(regions)}")

    lead, pred, out_d = {}, {}, {}
    for k in META:
        out_d[k] = {r: arr(mp) for r, mp in (D.get(k) or {}).items() if r in SIDO}
    price_out = {}

    for reg in regions:
        prices_raw = arr(tgt[reg])
        prices = ma(prices_raw)                 # 모델·예측은 3개월 평균 기준
        price_out[reg] = {"raw": prices_raw, "ma": prices}
        ytr = yoy_log(prices)
        feat, keys = {}, []
        for k in META:
            src = D.get(k) or {}
            mp = src.get("전국" if k in GLOBAL_KEYS else reg) or (src.get("전국") if k in GLOBAL_KEYS else None)
            if not mp:
                continue
            f = transform(k, arr(mp))
            # 최소 표본 — 고정 집합의 지표는 48개월만 있어도 받는다.
            #   (2026-08-21) 60개월로 잡았더니 미분양이 53개월치뿐이라 통째로 빠졌다.
            #   회귀 표본은 build_xy 에서 36개 미만이면 어차피 걸러진다.
            #   전년비로 바꾸면 앞 12개월이 날아간다 — 미분양은 53개월 → 41개로 줄어
            #   48 기준에도 걸렸다. 고정 집합은 36개월(회귀 최소 표본)까지 받는다.
            need = 36 if k in FIXED_KEYS else 60
            if sum(1 for v in f if v is not None) < need:
                continue
            feat[k] = f
            keys.append(k)
        if len(keys) < 3:
            continue
        lg_all = lags_for(feat, ytr, keys)
        lead[reg] = dict(sorted(lg_all.items(), key=lambda kv: -abs(kv[1]["corr"])))
        model_keys = [k for k in FIXED_KEYS if k in feat]      # 전 지역 동일 집합
        t_last = max(i for i, v in enumerate(prices) if v is not None)
        fc = forecast(feat, ytr, prices, model_keys, t_last)
        bt = backtest(feat, ytr, prices, model_keys)
        # (2026-08-21) 원시 회귀값을 그대로 쓰면 지평마다 지표 조합이 달라 경로가 튄다
        #   (전국 실측: 12개월 후 -27.8% 로 폭락 예측). 두 가지를 건다.
        #   ① 보정 — 백테스트에서 예측폭이 실제로 몇 배 실현됐는지(회귀 기울기)만큼만 반영한다.
        #      과거에 헛짚은 지평은 계수가 0 에 가까워 자동으로 평평해진다.
        #   ② 지평 평활 — 이웃 지평 3개를 평균해 모델 간 잡음을 없앤다.
        base = prices[t_last]
        g = {h: fc[h]["growth"] * (bt["by_h"].get(h, {}).get("calib", 0.0)) for h in fc}
        gs, guard = {}, {}
        for h in sorted(g):
            nb = [g[x] for x in (h - 1, h, h + 1) if x in g]
            v = sum(nb) / len(nb)
            #   ③ 역사 범위 가드 — 그 지역에서 h개월 동안 실제로 일어났던 변화의 5~95% 구간을 넘지 않는다.
            #      회귀는 표본 밖으로 얼마든지 뻗을 수 있어, 겪어본 적 없는 폭락·폭등을 그리는 걸 막는다
            #      (부산 실측: 보정 후에도 -14.6% 로 과거 최저 -14.4% 를 넘어섰다).
            hist = sorted(math.log(prices[i + h] / prices[i])
                          for i in range(len(prices) - h)
                          if prices[i] and prices[i + h] and prices[i] > 0 and prices[i + h] > 0)
            if len(hist) >= 40:
                lo_, hi_ = hist[int(len(hist) * 0.05)], hist[int(len(hist) * 0.95)]
                if v < lo_ or v > hi_:
                    guard[h] = True
                v = max(lo_, min(hi_, v))
            gs[h] = v
        z = 1.2816                                        # 80% 구간
        ft, fp, flo, fhi = [], [], [], []
        for h in sorted(gs):
            sd = (bt["by_h"].get(h) or {}).get("sd") or (bt["by_h"].get(h) or {}).get("mape") or 0
            band = sd / 100 * z
            p = base * math.exp(gs[h])
            ft.append(add_months(T[t_last], h))
            fp.append(round(p, 2))
            flo.append(round(p * (1 - band), 2))
            fhi.append(round(p * (1 + band), 2))
        pred[reg] = {"t": ft, "price": fp, "lo": flo, "hi": fhi,
                     "guarded": sorted(guard),
                     "last": {"t": T[t_last], "price": round(prices[t_last], 2),
                              "raw": prices_raw[t_last]},
                     # 12개월 지평에서 실제로 회귀에 들어간 지표만 싣는다.
                     #   표본이 짧아 그 지평에서 빠진 지표는 lag 가 없어 화면 표가 깨졌다.
                     "used": [{"key": k, "label": META[k][0],
                                "lag": (fc.get(HZ, {}).get("lags") or {})[k],
                                "corr": (fc.get(HZ, {}).get("corrs") or {}).get(k)}
                              for k in model_keys if k in (fc.get(HZ, {}).get("lags") or {})],
                     "n_model_keys": len(model_keys),
                     "fixed_set": True,
                     "backtest": bt}
        print(f"    {reg:<3} 모델지표 {len(model_keys)}(고정) · 예측 {len(fp)}개월 · 백테스트 MAPE {bt['mape']}% · 방향적중 {bt['hit']}%")

    out = {
        "asof": NOW.strftime("%Y-%m-%d %H:%M"),
        "src": "한국부동산원·국토교통부·국가데이터처(KOSIS) · 한국은행 ECOS · OECD",
        "note": ("기준계열은 한국부동산원 아파트 매매 실거래 중위가격(㎡당 만원). "
                 "예측은 선행지표의 시차를 데이터로 찾아 회귀한 결과이며, 함께 표시된 "
                 "백테스트 성적(과거 구간 재현 오차)을 보고 신뢰 수준을 판단할 것. "
                 "투자 판단의 근거가 아니라 흐름 참고용이다."),
        "target": {"key": TARGET, "label": TARGET_LABEL, "unit": "만원/㎡",
                   "src": "한국부동산원", "smooth": SMOOTH,
                   "note": f"월별 실거래 중위가는 표본 구성에 따라 크게 튀어, 모델과 예측선은 {SMOOTH}개월 평균 기준이다(원자료도 함께 싣는다)."},
        "horizon": HZ, "maxlag": MAXLAG,
        "fixed_keys": [{"key": k, "label": META[k][0]} for k in FIXED_KEYS],
        "t": T, "regions": regions,
        "meta": {k: {"label": v[0], "unit": v[1], "group": v[2], "cycle": v[3],
                     "src": v[4], "note": v[5]} for k, v in META.items()},
        "d": out_d, "price": price_out, "lead": lead, "pred": pred,
    }
    DB.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"  → {OUT} ({OUT.stat().st_size // 1024}KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
