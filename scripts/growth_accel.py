#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""growth_accel.py — 동분기 YoY 성장 '가속도' 수집 (2026-07-22 신설)

정의: 동분기 YoY 가속 = 이번 분기 YoY − 작년 동분기 YoY.
  예) 매출 Q1'26 YoY(+198%) − Q1'25 YoY(+42%) = +156%p → 성장이 '가속' 중.
  같은 분기끼리만 비교하므로 계절성이 완전히 제거된다(YoY의 방향 변화만 봄).

데이터(추가 API 키 불필요 — 이미 연동된 소스):
  - KR: KIS 손익계산서(분기)  /uapi/domestic-stock/v1/finance/income-statement (FHKST66430200)
        → 30개 분기(누적) 매출/영업이익. 같은 stac_yymm(회계월) 끼리 3년 비교.
  - US: SEC EDGAR companyconcept (무료·키 불필요) — 60+ 분기 XBRL 실측.
        같은 회계분기(fp) fy/fy-1/fy-2 비교.

재무는 분기 단위로만 바뀌므로 매일 돌 필요가 없다 → 주 1회 cron(일요일 새벽).
결과: data/db/growth_accel.json = {"kr":{code:{racc,oacc,gacc}}, "us":{ticker:{...}}, "as_of":...}
screener_pool.py 가 이 파일을 읽어 각 종목 gacc/racc/oacc 로 병합한다(빌드 부담 0).

값 단위: 소수(예: 1.562 = +156.2%p). 프론트에서 *100.
"""
import os, sys, json, time, datetime, urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(BASE, "data", "db")
OUT = os.path.join(DB, "growth_accel.json")
sys.path.insert(0, os.path.join(BASE, "scripts"))
UA = {"User-Agent": "Mozilla/5.0"}
SEC_UA = {"User-Agent": "namoobi-market-report research@namoobi.example"}


def _accel_from_series(byperiod, keyfn_now, keyfn_prev, keyfn_prev2):
    """3개 동일-분기 값(P0=최신, P1=전년, P2=전전년)으로 가속도 = (P0/P1-1)-(P1/P2-1). 매출용(양수 가정)."""
    p0, p1, p2 = keyfn_now, keyfn_prev, keyfn_prev2
    if p0 is None or p1 is None or p2 is None:
        return None
    if p1 <= 0 or p2 <= 0:
        return None
    return (p0 / p1 - 1) - (p1 / p2 - 1)


# ───────────────────────── KR (KIS) ─────────────────────────
def _kr_one(kis, c, tok, code):
    try:
        j = kis._get(c, tok, "/uapi/domestic-stock/v1/finance/income-statement", "FHKST66430200",
                     {"FID_DIV_CLS_CODE": "1", "fid_cond_mrkt_div_code": "J", "fid_input_iscd": code})
        rows = j.get("output") or []
        if not rows:
            return code, None
        def series(fld):
            s = {}
            for r in rows:
                v = r.get(fld)
                try:
                    s[r["stac_yymm"]] = float(v)
                except (TypeError, ValueError):
                    pass
            return s
        rv, op = series("sale_account"), series("bsop_prti")
        out = {}
        for name, s in (("racc", rv), ("oacc", op)):
            if not s:
                continue
            per = max(s)                       # 최신 회계월 YYYYMM
            mm = per[4:]; yr = int(per[:4])
            a = _accel_from_series(s, s.get(per), s.get(f"{yr-1}{mm}"), s.get(f"{yr-2}{mm}"))
            if a is not None:
                out[name] = round(a, 4)
        if "racc" in out and "oacc" in out:
            out["gacc"] = round((out["racc"] + out["oacc"]) / 2, 4)
        elif "racc" in out:
            out["gacc"] = out["racc"]
        elif "oacc" in out:
            out["gacc"] = out["oacc"]
        return code, (out or None)
    except Exception:
        return code, None


def collect_kr(codes, workers=8):
    import kis_api as kis
    c = kis._creds()
    if not c:
        print("[accel] KIS 키 없음 — KR skip"); return {}
    tok = kis._token(c)
    res = {}
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(_kr_one, kis, c, tok, code) for code in codes]
        for i, f in enumerate(as_completed(futs)):
            code, v = f.result()
            if v:
                res[code] = v
            if (i + 1) % 300 == 0:
                print(f"[accel] KR {i+1}/{len(codes)}")
    print(f"[accel] KR 완료 {len(res)}/{len(codes)}")
    return res


# ───────────────────────── US (SEC) ─────────────────────────
_REV_CONCEPTS = ["RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues",
                 "RevenueFromContractWithCustomerIncludingAssessedTax", "SalesRevenueNet"]
_OP_CONCEPTS = ["OperatingIncomeLoss"]


def _sec_get(url):
    return json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=SEC_UA), timeout=20).read())


def _sec_ticker_cik():
    d = _sec_get("https://www.sec.gov/files/company_tickers.json")
    return {v["ticker"].upper(): f'{int(v["cik_str"]):010d}' for v in d.values()}


def _sec_concept_series(cik, concept):
    """개념의 분기(3개월) 값을 회계분기(fp,fy) → val 로. 최신·전년·전전년 계산용."""
    try:
        d = _sec_get(f"https://data.sec.gov/api/xbrl/companyconcept/CIK{cik}/us-gaap/{concept}.json")
    except Exception:
        return None
    usd = (d.get("units") or {}).get("USD") or []
    from datetime import date as _d
    def mlen(s, e):
        try: return (_d.fromisoformat(e) - _d.fromisoformat(s)).days
        except Exception: return 0
    q = [x for x in usd if x.get("start") and x.get("end") and 80 <= mlen(x["start"], x["end"]) <= 100 and x.get("fp") and x.get("fy")]
    if not q:
        return None
    by = {}                       # (fp) -> {fy: val}
    latest = None
    for x in q:
        by.setdefault(x["fp"], {})[x["fy"]] = x["val"]
        if latest is None or x["end"] > latest["end"]:
            latest = x
    fp, fy = latest["fp"], latest["fy"]
    m = by.get(fp, {})
    return _accel_from_series(m, m.get(fy), m.get(fy - 1), m.get(fy - 2))


def _us_one(cik, ticker):
    try:
        racc = None
        for cc in _REV_CONCEPTS:
            racc = _sec_concept_series(cik, cc)
            if racc is not None:
                break
        oacc = _sec_concept_series(cik, _OP_CONCEPTS[0])
        out = {}
        if racc is not None: out["racc"] = round(racc, 4)
        if oacc is not None: out["oacc"] = round(oacc, 4)
        if "racc" in out and "oacc" in out: out["gacc"] = round((out["racc"] + out["oacc"]) / 2, 4)
        elif "racc" in out: out["gacc"] = out["racc"]
        elif "oacc" in out: out["gacc"] = out["oacc"]
        return ticker, (out or None)
    except Exception:
        return ticker, None


def collect_us(tickers, workers=6):
    try:
        t2c = _sec_ticker_cik()
    except Exception as e:
        print("[accel] SEC ticker map 실패 — US skip:", repr(e)[:80]); return {}
    pairs = [(t2c[t.upper()], t) for t in tickers if t.upper() in t2c]
    res = {}
    with ThreadPoolExecutor(max_workers=workers) as ex:     # SEC 레이트리밋 ~10/s
        futs = [ex.submit(_us_one, cik, t) for cik, t in pairs]
        for i, f in enumerate(as_completed(futs)):
            t, v = f.result()
            if v:
                res[t] = v
            if (i + 1) % 500 == 0:
                print(f"[accel] US {i+1}/{len(pairs)}")
            time.sleep(0.02)                                # 소폭 스로틀
    print(f"[accel] US 완료 {len(res)}/{len(pairs)} (SEC 매칭 {len(pairs)}/{len(tickers)})")
    return res


def _universe():
    try:
        d = json.load(open(os.path.join(DB, "screener_pool.json"), encoding="utf-8"))
        kr = [r["c"] for r in (d.get("kr") or []) if r.get("c")]
        us = [r["c"] for r in (d.get("us") or []) if r.get("c")]
        return kr, us
    except Exception:
        return [], []


def main():
    lim = None
    for a in sys.argv[1:]:
        if a.startswith("--limit="):
            lim = int(a.split("=")[1])
    kr, us = _universe()
    if lim:
        kr, us = kr[:lim], us[:lim]
    print(f"[accel] universe KR {len(kr)} · US {len(us)}  {datetime.datetime.now():%H:%M:%S}")
    KR = collect_kr(kr) if kr else {}
    US = collect_us(us) if us else {}
    obj = {"kr": KR, "us": US, "as_of": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
           "desc": "동분기 YoY 성장 가속(이번분기 YoY − 작년동기 YoY). KR=KIS 손익계산서 / US=SEC EDGAR. 값=소수(×100=%p)"}
    os.makedirs(DB, exist_ok=True)
    json.dump(obj, open(OUT, "w"), ensure_ascii=False)
    print(f"[accel] ✅ 저장 {OUT} — KR {len(KR)} · US {len(US)}")


if __name__ == "__main__":
    sys.exit(main())
