#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# fetch_lending.py — 종목별 대차잔고 → screener_pool 패치. (2026-07-20 신설)
#   소스: 금융위원회_주식대차정보(data.go.kr) getStLendAndBorrItemRank_V2
#         basDt 하나로 전종목(약 2,770) 1일 1콜(페이지네이션). 기준일 +1영업일 13시 이후 갱신.
#   필드: lnbRmanStckCnt(대차잔여주식수)·lnbBal(대차잔고 금액) · 상장주식수=KRX base LIST_SHRS
#   저장: 풀 KR 각 행에 lb(대차잔고 억원)·lbr(대차잔고비율 %). screener_pool 재빌드 직후 cron 실행.
import os, sys, json, time, glob, urllib.request
from datetime import date, timedelta
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ta_screen as T

BASE = "https://apis.data.go.kr/1160100/GetStocLendBorrInfoService_V2"


def _key():
    for anc in [T.CACHE, os.path.dirname(os.path.abspath(__file__))]:
        for p in (os.path.join(anc, "..", "..", "SECURITY", "data.go.kr.txt"),
                  "/home/ubuntu/SECURITY/data.go.kr.txt"):
            if os.path.exists(p):
                return open(p).read().strip()
    k = os.environ.get("DATA_GO_KR_KEY")
    if k:
        return k.strip()
    # (2026-07-20) 서버 정식 위치 — ~/namoobi/secrets/.env 의 DATA_GO_KR_KEY= 행 (cron 환경에 env 없음)
    try:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        for ln in open(os.path.join(base, "secrets", ".env")):
            ln = ln.strip()
            if ln.startswith("DATA_GO_KR_KEY=") and not ln.startswith("#"):
                return ln.split("=", 1)[1].strip()
    except Exception:
        pass
    # 서버 상위 디렉터리 탐색
    for anc in [os.path.dirname(os.path.abspath(__file__))]:
        for up in range(1, 6):
            cand = os.path.join(anc, *([".."]*up), "SECURITY", "data.go.kr.txt")
            if os.path.exists(cand):
                return open(cand).read().strip()
    raise RuntimeError("data.go.kr 키를 찾을 수 없음")


def _get(url, tries=5):
    for i in range(tries):
        try:
            return json.loads(urllib.request.urlopen(url, timeout=40).read())
        except Exception:
            if i == tries-1:
                raise
            time.sleep(3)


def _latest_basdt(key):
    """최신 데이터 있는 영업일(basDt) 탐색 — 오늘부터 최대 7일 역순."""
    for k in range(1, 8):
        dd = (date.today()-timedelta(days=k)).strftime("%Y%m%d")
        try:
            j = _get(f"{BASE}/getStLendAndBorrItemRank_V2?serviceKey={key}&resultType=json&numOfRows=1&pageNo=1&basDt={dd}")
            if (j["response"]["body"].get("totalCount") or 0) > 0:
                return dd
        except Exception:
            continue
    return None


def _list_shrs():
    shr = {}
    for f in glob.glob(f"{T.CACHE}/krxbase_*.json"):
        try:
            for x in json.load(open(f)):
                c = x.get("ISU_SRT_CD"); v = x.get("LIST_SHRS")
                if c and v:
                    shr[c] = T.num(v)
        except Exception:
            pass
    return shr


def build():
    key = _key()
    basDt = _latest_basdt(key)
    if not basDt:
        print("[lending] 최신 대차 데이터 없음 — skip"); return
    page = 1; rows = []
    while True:
        j = _get(f"{BASE}/getStLendAndBorrItemRank_V2?serviceKey={key}&resultType=json&numOfRows=1000&pageNo={page}&basDt={basDt}")
        b = j["response"]["body"]; its = (b.get("items") or {}).get("item", []) or []
        rows += its
        tc = b.get("totalCount") or 0
        if page*1000 >= tc or not its:
            break
        page += 1
    lb = {x.get("isinCd"): x for x in rows}      # isinCd = 6자리 단축코드
    shr = _list_shrs()
    pool = T.load_db("screener_pool")
    if not pool or not pool.get("kr"):
        print("[lending] screener_pool 없음 — skip"); return
    kr = pool["kr"]; match = withr = 0
    for r in kr:
        x = lb.get(r["c"])
        if not x:
            continue
        match += 1
        rman = T.num(x.get("lnbRmanStckCnt")); bal = T.num(x.get("lnbBal"))
        r["lb"] = round(bal/1e8, 1) if bal else None      # 대차잔고 금액(억원)
        s = shr.get(r["c"])
        if rman is not None and s and s > 0:
            r["lbr"] = round(rman/s*100, 2); withr += 1     # 대차잔고비율(%)
    pool["lending_asof"] = basDt
    T.save_db("screener_pool", pool)
    print(f"[lending] basDt {basDt} · 매칭 {match}/{len(kr)} · 비율 {withr}")


if __name__ == "__main__":
    build()
