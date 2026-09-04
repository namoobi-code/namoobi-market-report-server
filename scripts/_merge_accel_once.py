#!/usr/bin/env python3
# v2 growth_accel 완료 직후 풀에 in-place 병합 (전체 재빌드 없이). 1회용 워처가 호출.
import json, time, os
B="/home/ubuntu/namoobi/data/db"
p=json.load(open(f"{B}/screener_pool.json",encoding="utf-8"))
g=json.load(open(f"{B}/growth_accel.json",encoding="utf-8"))
n=0
for mk in ("kr","us"):
    gm=g.get(mk) or {}
    for r in (p.get(mk) or []):
        v=gm.get(r.get("c"))
        if v:
            r["gacc"]=v.get("gacc"); r["racc"]=v.get("racc"); r["oacc"]=v.get("oacc")
            r["qtoby"]=v.get("qtoby"); r["qtobq"]=v.get("qtobq"); r["opmch"]=v.get("opmch")
            n+=1
json.dump(p,open(f"{B}/screener_pool.json","w"),ensure_ascii=False)
print(f"[merge_accel] in-place 병합 {n}종  as_of={g.get(as_of)}")
