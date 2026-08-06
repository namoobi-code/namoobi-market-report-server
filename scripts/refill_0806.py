#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""refill_0806.py — 08-06 사고 원오프 복구 (실행 후 삭제 가능).
① US: spark 6mo 재수집 → r1m/r3m/r6m/vol20 + mom(12-1M) 재계산 (오전 spark 전면 실패로 소실)
② KR: KIS 종목별 투자자 재수집 → fst/ost (오늘 미집계 행 스킵 로직 적용)"""
import json, time, urllib.parse as _up
from pathlib import Path
import ta_screen as T
import kis_api as K

BASE = Path(__file__).resolve().parent.parent
PF = BASE / "data" / "db" / "screener_pool.json"
pool = json.loads(PF.read_text(encoding="utf-8"))
us, kr = pool.get("us") or [], pool.get("kr") or []

# ① US spark
def _spark_batch(syms):
    try:
        u = ("https://query1.finance.yahoo.com/v7/finance/spark?symbols=%s&range=6mo&interval=1d"
             % _up.quote(",".join(syms)))
        j = T.jget(u, timeout=15)
        out = {}
        for r0 in (j.get("spark", {}) or {}).get("result") or []:
            sym = r0.get("symbol"); resp = (r0.get("response") or [{}])[0]
            cl = (((resp.get("indicators", {}) or {}).get("quote") or [{}])[0].get("close")) or []
            cl = [x for x in cl if x is not None]
            if len(cl) >= 30: out[sym] = cl
        return out
    except Exception:
        return {}

codes = [r["c"] for r in us]
closes = {}
for res in T.pmap(_spark_batch, [codes[i:i+20] for i in range(0, len(codes), 20)], workers=6):
    closes.update(res)
n_us = 0
for r in us:
    cl = closes.get(r["c"])
    if not cl or len(cl) < 30: continue
    c = cl[-1]; n = len(cl)
    for lbl, dd in (("r1m", 21), ("r3m", 63), ("r6m", 120)):
        if n > dd and cl[-dd-1]: r[lbl] = round(c/cl[-dd-1]-1, 4)
    rets = [cl[i]/cl[i-1]-1 for i in range(max(1, n-20), n) if cl[i-1]]
    if len(rets) >= 10:
        mu = sum(rets)/len(rets)
        r["vol20"] = round((sum((x-mu)**2 for x in rets)/len(rets))**0.5*100, 2)
    a, b = r.get("r1y"), r.get("r1m")
    if a is not None and b is not None and (1+b) > 0:
        r["mom"] = round((1+a)/(1+b)-1, 4)
    n_us += 1
print(f"[refill] US spark {len(closes)}종 · 갱신 {n_us}종", flush=True)

# ② KR fst/ost
c_ = K._creds(); tok = K._token(c_)
okk = [0]
def one(r):
    try:
        time.sleep(0.05)
        j = K._get(c_, tok, "/uapi/domestic-stock/v1/quotations/inquire-investor", "FHKST01010900",
                   {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": r["c"]}, tries=2)
        rows = j.get("output") or []
        if not rows: return
        fq = [T.num(x.get("frgn_ntby_qty")) for x in rows]
        oq = [T.num(x.get("orgn_ntby_qty")) for x in rows]
        def _skip(a):
            i = 0
            while i < len(a) and a[i] is None: i += 1
            return a[i:]
        def streak(a):
            k = 0
            for x in _skip(a):
                if x is not None and x > 0: k += 1
                else: break
            return k
        r["fst"] = streak(fq); r["ost"] = streak(oq)
        okk[0] += 1
    except Exception:
        pass

for _ in T.pmap(one, kr, workers=4): pass
print(f"[refill] KR fst/ost {okk[0]}/{len(kr)}종", flush=True)

PF.write_text(json.dumps(pool, ensure_ascii=False), encoding="utf-8")
nz = sum(1 for r in kr if r.get("fst"))
print(f"[refill] ✅ 저장 — US r1m {sum(1 for r in us if r.get('r1m') is not None)}종 · KR fst>0 {nz}종", flush=True)
