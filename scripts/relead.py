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
}
GLOBAL_KEYS = {"cli", "m2", "gdp", "fx", "rate_kr", "mtg_bal", "mtg_rate",
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
