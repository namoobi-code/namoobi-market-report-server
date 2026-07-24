#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""(2026-07-24 일회성) 기존 US 풀에 수급 프록시 3필드 즉시 패치.
다음 정기 빌드부터는 screener_pool.py 의 quoteSummary(defaultKeyStatistics)가 채운다.
  sr_f = shortPercentOfFloat(공매도잔량/유통주식, 소수) · scov = shortRatio(커버일수)
  inst = heldPercentInstitutions(기관보유, 소수)"""
import json, os, sys, time
import urllib.parse as _up
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ta_screen as T

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
POOL = os.path.join(BASE, "data", "db", "screener_pool.json")

def main():
    d = json.load(open(POOL, encoding="utf-8"))
    us = d.get("us") or []
    op, crumb = T.yahoo_opener()
    done = [0]
    def one(r):
        try:
            j = T.jget(f"https://query2.finance.yahoo.com/v10/finance/quoteSummary/{r['c']}"
                       f"?modules=defaultKeyStatistics&crumb={_up.quote(crumb)}", opener=op, timeout=12)
            ks = ((j["quoteSummary"]["result"] or [{}])[0]).get("defaultKeyStatistics", {})
            v = lambda x: (x or {}).get("raw") if isinstance(x, dict) else x
            if v(ks.get("shortPercentOfFloat")) is not None: r["sr_f"] = v(ks.get("shortPercentOfFloat"))
            if v(ks.get("shortRatio")) is not None: r["scov"] = v(ks.get("shortRatio"))
            if v(ks.get("heldPercentInstitutions")) is not None: r["inst"] = v(ks.get("heldPercentInstitutions"))
            done[0] += 1
            if done[0] % 500 == 0: print(f"  {done[0]}...", flush=True)
        except Exception:
            pass
    T.pmap(one, us, workers=6)
    json.dump(d, open(POOL, "w", encoding="utf-8"), ensure_ascii=False)
    nz = sum(1 for r in us if r.get("sr_f") is not None)
    print(f"[patch_us_short] ✅ sr_f 채움 {nz}/{len(us)}")

if __name__ == "__main__":
    main()
