#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""(2026-07-24 일회성) 아침 빌드에서 전 종목 sr=0.0 으로 들어간 사고 복구.
KIS 공매도 일별추이를 다시 받아 '오늘(집계 전 0)' 행을 건너뛰고 sr·sr5만 갱신한다.
다음 정기 빌드부터는 screener_pool.py 의 날짜 가드가 같은 일을 한다."""
import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kis_api as K

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
POOL = os.path.join(BASE, "data", "db", "screener_pool.json")

def num(v):
    try:
        v = str(v).replace(",", "").strip()
        return float(v) if v not in ("", "-") else None
    except Exception: return None

def main():
    d = json.load(open(POOL, encoding="utf-8"))
    kr = d.get("kr") or []
    c = K._creds(); tok = K._token(c)
    today = time.strftime("%Y%m%d")
    fixed = 0
    from concurrent.futures import ThreadPoolExecutor
    def one(r):
        nonlocal fixed
        try:
            time.sleep(0.05)
            j = K._get(c, tok, "/uapi/domestic-stock/v1/quotations/daily-short-sale",
                       "FHPST04830000",
                       {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": r["c"],
                        "FID_INPUT_DATE_1": "", "FID_INPUT_DATE_2": ""}, tries=2)
            rows = j.get("output2") or []
            if rows and str(rows[0].get("stck_bsop_date")) == today and not num(rows[0].get("ssts_vol_rlim")):
                rows = rows[1:]
            rl = [num(x.get("ssts_vol_rlim")) for x in rows]
            if rl and rl[0] is not None:
                r["sr"] = round(rl[0], 2); fixed += 1
            v5 = [x for x in rl[:5] if x is not None]
            if v5: r["sr5"] = round(sum(v5) / len(v5), 2)
        except Exception: pass
    with ThreadPoolExecutor(max_workers=4) as ex:
        list(ex.map(one, kr))
    json.dump(d, open(POOL, "w", encoding="utf-8"), ensure_ascii=False)
    nz = sum(1 for r in kr if r.get("sr"))
    print(f"[repair_sr] ✅ sr 갱신 {fixed}/{len(kr)} · 0이 아닌 sr {nz}")

if __name__ == "__main__":
    main()
