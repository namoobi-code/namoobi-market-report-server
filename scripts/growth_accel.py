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
        # (2026-07-23) 분기 흑자전환 2종 + 분기 마진 YoY 변화 — 같은 분기 시계열로 추가 호출 0
        if op:
            per = max(op); mm = per[4:]; yr = int(per[:4])
            o0 = op.get(per)                                   # 당분기 영업이익
            oy = op.get(f"{yr-1}{mm}")                         # 전년동기
            pers = sorted(op)                                  # 직전분기(달력상 바로 앞 결산월)
            op_prev = op.get(pers[pers.index(per)-1]) if pers.index(per) >= 1 else None
            if o0 is not None:
                if oy is not None:
                    out["qtoby"] = 1 if (oy < 0 and o0 > 0) else 0     # 전년동기 적자→당분기 흑자(계절성 안전)
                if op_prev is not None:
                    out["qtobq"] = 1 if (op_prev < 0 and o0 > 0) else 0  # 직전분기 적자→당분기 흑자(가장 빠름·계절성 주의)
            # 마진 YoY 변화 = 당분기 OPM − 전년동기 OPM (%p, 소수)
            r0, ry = rv.get(per), rv.get(f"{yr-1}{mm}")
            if o0 is not None and oy is not None and r0 and ry and r0 > 0 and ry > 0:
                out["opmch"] = round(o0 / r0 - oy / ry, 4)
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


_sec_lock = __import__("threading").Lock()
_sec_last = [0.0]
def _sec_get(url):
    """SEC fair-access(≤10 req/s) 준수 — 전역 스로틀(요청 간 최소 0.12s) + 403/429 백오프.
       (2026-07-23) 1차 전체 실행에서 무스로틀 6워커로 차단당해 US 59/5192 — 원인 수정."""
    for att in range(3):
        with _sec_lock:
            wait = 0.12 - (time.time() - _sec_last[0])
            if wait > 0:
                time.sleep(wait)
            _sec_last[0] = time.time()
        try:
            return json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=SEC_UA), timeout=20).read())
        except urllib.error.HTTPError as e:
            if e.code in (403, 429) and att < 2:
                time.sleep(20 * (att + 1))     # 차단 해제 대기 후 재시도
                continue
            raise


def _sec_ticker_cik():
    d = _sec_get("https://www.sec.gov/files/company_tickers.json")
    return {v["ticker"].upper(): f'{int(v["cik_str"]):010d}' for v in d.values()}


def _sec_concept_qtr(cik, concept):
    """개념의 분기(3개월) 값 → {"by": {fp:{fy:val}}, "latest": (fp,fy), "seq": [(end,val)...날짜순]}."""
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
    by, latest, seq = {}, None, {}
    for x in q:
        by.setdefault(x["fp"], {})[x["fy"]] = x["val"]
        seq[x["end"]] = x["val"]              # end 날짜별(중복 재보고는 마지막 값)
        if latest is None or x["end"] > latest["end"]:
            latest = x
    return {"by": by, "latest": (latest["fp"], latest["fy"]), "seq": sorted(seq.items())}


def _accel_of(qd):
    if not qd: return None
    fp, fy = qd["latest"]; m = qd["by"].get(fp, {})
    return _accel_from_series(m, m.get(fy), m.get(fy - 1), m.get(fy - 2))


def _us_one(cik, ticker):
    try:
        rq = None
        for cc in _REV_CONCEPTS:
            rq = _sec_concept_qtr(cik, cc)
            if rq: break
        oq = _sec_concept_qtr(cik, _OP_CONCEPTS[0])
        racc, oacc = _accel_of(rq), _accel_of(oq)
        out = {}
        if racc is not None: out["racc"] = round(racc, 4)
        if oacc is not None: out["oacc"] = round(oacc, 4)
        if "racc" in out and "oacc" in out: out["gacc"] = round((out["racc"] + out["oacc"]) / 2, 4)
        elif "racc" in out: out["gacc"] = out["racc"]
        elif "oacc" in out: out["gacc"] = out["oacc"]
        # (2026-07-23) 분기 흑자전환 2종 + 마진 YoY 변화 (KR 동일 정의)
        if oq:
            fp, fy = oq["latest"]; m = oq["by"].get(fp, {})
            o0, oy = m.get(fy), m.get(fy - 1)
            seqv = [v for _, v in oq["seq"]]
            op_prev = seqv[-2] if len(seqv) >= 2 else None
            if o0 is not None:
                if oy is not None:
                    out["qtoby"] = 1 if (oy < 0 and o0 > 0) else 0
                if op_prev is not None:
                    out["qtobq"] = 1 if (op_prev < 0 and o0 > 0) else 0
            if rq:
                mr = rq["by"].get(fp, {})
                r0, ry = mr.get(fy), mr.get(fy - 1)
                if o0 is not None and oy is not None and r0 and ry and r0 > 0 and ry > 0:
                    out["opmch"] = round(o0 / r0 - oy / ry, 4)
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
    with ThreadPoolExecutor(max_workers=3) as ex:           # 전역 스로틀(_sec_get)이 실제 속도 제어(~8 req/s)
        futs = [ex.submit(_us_one, cik, t) for cik, t in pairs]
        for i, f in enumerate(as_completed(futs)):
            t, v = f.result()
            if v:
                res[t] = v
            if (i + 1) % 500 == 0:
                print(f"[accel] US {i+1}/{len(pairs)} (수집 {len(res)})")
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
    # (2026-07-23) 기존 파일과 병합 — 일시 실패(레이트리밋 등)한 종목은 직전 값 유지
    try:
        prev = json.load(open(OUT, encoding="utf-8"))
        KR = {**(prev.get("kr") or {}), **KR}
        US = {**(prev.get("us") or {}), **US}
    except Exception:
        pass
    obj = {"kr": KR, "us": US, "as_of": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
           "desc": "동분기 YoY 성장 가속(이번분기 YoY − 작년동기 YoY). KR=KIS 손익계산서 / US=SEC EDGAR. 값=소수(×100=%p)"}
    os.makedirs(DB, exist_ok=True)
    json.dump(obj, open(OUT, "w"), ensure_ascii=False)
    print(f"[accel] ✅ 저장 {OUT} — KR {len(KR)} · US {len(US)}")


if __name__ == "__main__":
    sys.exit(main())
