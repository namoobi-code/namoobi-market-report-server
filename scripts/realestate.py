#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
realestate.py — 부동산 탭 데이터 수집 (한국은행 ECOS, 월간)

시리즈 (전부 실측 확인 2026-08-01):
  csi        511Y002/FMFB/99988   주택가격전망CSI(전체) — 100↑=1년 후 집값 상승 예상 우세
  sale       901Y062/P63A         주택매매가격지수 총지수(전국) — 한국부동산원 원천
  sale_apt   901Y062/P63AC        아파트(전국)
  sale_apt_s 901Y062/P63ACA       아파트(서울)
  js         901Y063/P64A         주택전세가격지수 총지수(전국)
  js_apt     901Y063/P64AC        아파트(전국)
  js_apt_s   901Y063/P64ACA       아파트(서울)
  mtg        121Y006/BECBLA0302   예금은행 주택담보대출 금리(신규취급, %)

산출: data/db/realestate.json  {"asof","src","series":{key:{"t":[YYYYMM],"v":[..]}}}
cron: 10 7 * * *  (월간 지표 — 하루 1회면 충분)
"""
import json, os, urllib.request
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DB   = BASE / "data" / "db"
OUT  = DB / "realestate.json"

def _key():
    for p in [BASE/"keys"/"ecos.txt", Path("D:/claudeCowork/SECURITY")/"한국은행OPENAPI인증키.txt"] + \
             sorted(Path("/sessions").glob("*/mnt/claudeCowork/SECURITY/한국은행OPENAPI인증키.txt")):
        try: return Path(p).read_text(encoding="utf-8").strip()
        except Exception: pass
    raise SystemExit("ECOS 키 없음 (keys/ecos.txt)")

KEY = _key()
END = datetime.now().strftime("%Y%m")

SERIES = [
    ("csi",        "511Y002", "FMFB",       "99988"),
    ("sale",       "901Y062", "P63A",       None),
    ("sale_apt",   "901Y062", "P63AC",      None),
    ("sale_apt_s", "901Y062", "P63ACA",     None),
    ("js",         "901Y063", "P64A",       None),
    ("js_apt",     "901Y063", "P64AC",      None),
    ("js_apt_s",   "901Y063", "P64ACA",     None),
    ("mtg",        "121Y006", "BECBLA0302", None),
    ("tdep",       "104Y015", "BDAA31",     None),   # (2026-08-02) 은행 정기예금 말잔(십억원) — 증시 자금이동 참고
]

def fetch(stat, item1, item2):
    url = (f"https://ecos.bok.or.kr/api/StatisticSearch/{KEY}/json/kr/1/1000/"
           f"{stat}/M/201001/{END}/{item1}" + (f"/{item2}" if item2 else ""))
    for t in range(3):
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                j = json.loads(r.read().decode("utf-8"))
            rows = (j.get("StatisticSearch") or {}).get("row") or []
            # item2 미지정 시에도 하위분류가 섞이면 첫 분류만 (총지수류는 단일)
            out = {}
            for x in rows:
                tt = x.get("TIME"); v = x.get("DATA_VALUE")
                if tt and v not in (None, ""):
                    out.setdefault(tt, float(v))       # 같은 TIME 중복이면 첫 값
            ts = sorted(out)
            return {"t": ts, "v": [out[k] for k in ts]}
        except Exception as e:
            if t == 2: print(f"  [warn] {stat}/{item1} 실패: {e}")
    return {"t": [], "v": []}

REGIONS = {"REG00":"전국","REG11":"서울","REG41":"경기","REG28":"인천","REG26":"부산","REG27":"대구",
           "REG30":"대전","REG31":"울산","REG36":"세종","REG29":"광주","REG42":"강원","REG43":"충북",
           "REG44":"충남","REG45":"전북","REG46":"전남","REG47":"경북","REG48":"경남","REG51":"제주"}

def fetch_mcap():
    """(2026-08-01) 시도별 주택 시가총액(291Y524, 연간·십억원) — 국민대차대조표.
       기사 검증: 2025 전국 7,710조·서울 2,894조·경기 2,192조·인천 341조 → 수도권 70.4%"""
    out = {}
    for code, name in REGIONS.items():
        url = (f"https://ecos.bok.or.kr/api/StatisticSearch/{KEY}/json/kr/1/100/"
               f"291Y524/A/2010/{datetime.now().year}/{code}")
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                j = json.loads(r.read().decode("utf-8"))
            rows = (j.get("StatisticSearch") or {}).get("row") or []
            d = {x["TIME"]: float(x["DATA_VALUE"]) for x in rows if x.get("DATA_VALUE") not in (None, "")}
            ts = sorted(d)
            out[name] = {"t": ts, "v": [round(d[k]/1000, 1) for k in ts]}   # 십억원 → 조원
        except Exception as e:
            print(f"  [warn] mcap {name} 실패: {e}")
    return out

def main():
    series = {}
    for key, stat, i1, i2 in SERIES:
        series[key] = fetch(stat, i1, i2)
        print(f"  {key}: {len(series[key]['t'])}개월 · 최신 {series[key]['t'][-1] if series[key]['t'] else '—'} = {series[key]['v'][-1] if series[key]['v'] else '—'}")
    mcap = fetch_mcap()
    print(f"  mcap: {len(mcap)}개 시도 · 전국 최신 {mcap.get('전국',{}).get('v',[None])[-1]}조")
    DB.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "asof": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "src": "한국은행 ECOS — 소비자동향조사(511Y002)·주택매매/전세가격지수(901Y062/063, 한국부동산원 원천)·예금은행 대출금리(121Y006)·시도별 주택시가총액(291Y524, 국민대차대조표)",
        "series": series, "mcap": mcap}, ensure_ascii=False), encoding="utf-8")
    print(f"[realestate] ✅ 저장 → {OUT}")

if __name__ == "__main__":
    main()
