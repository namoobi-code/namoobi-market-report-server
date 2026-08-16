# -*- coding: utf-8 -*-
"""미확보 535건 전수 — BZ 금액이 8-K 원문에 실제로 등장하는가?
 있음 → 파서 개선으로 회수 가능(상한)  /  없음 → 환산·콜 전용(도입 판단 대상)
 없음 군에 대해서는 'BZ값 vs 컨센' 갭 분포를 따로 재 신호 유무를 본다."""
import gc, gzip, json, re, signal, sys
from datetime import datetime, timedelta
from pathlib import Path
sys.path.insert(0, "scripts")
from earnings_8k_watch import _strip
live = json.load(open("data/db/earnings_live_us.json"))
pool = {r.get("c"): r for r in json.load(open("data/db/screener_pool.json"))["us"]}
EXC = Path("data/cache/exhibit")
cut = (datetime.now() - timedelta(days=90)).strftime("%Y%m%d")
tasks = {}
for d8 in sorted(live["days"], reverse=True):
    if d8 < cut: continue
    for it in live["days"][d8]:
        c = it.get("c"); r = pool.get(c)
        if not r or not it.get("acc"): continue
        for m in ("rev","eps"):
            bzv = it.get(f"g_{m}_p")
            if bzv is None or it.get(f"g_{m}") is not None: continue
            if m == "eps" and "Real Estate" in str(r.get("sector") or ""): continue
            per = it.get(f"g_{m}_per_p") or "0y"
            bk = {("rev","0y"):"ry0",("rev","0q"):"rq0",("eps","0y"):"ey0",("eps","0q"):"eq0"}.get((m,per))
            base = r.get(bk) if bk else None
            tasks.setdefault(it["acc"], []).append((c, m, bzv, base))
def forms(m, v):
    """BZ 값의 원문 표기 후보들"""
    out = set()
    if m == "eps":
        for f in ("%.2f", "%.3f"): out.add(f % v)
        out.add(("%.2f" % v).rstrip("0").rstrip("."))
    else:
        mm = v            # 백만 단위
        out.add(f"{mm:,.0f}"); out.add(f"{mm:,.1f}")
        b = mm/1000
        out.add(f"{b:,.2f}"); out.add(f"{b:,.1f}")
        if abs(b - round(b)) < 1e-9: out.add(f"{b:,.0f}")
    return {x for x in out if x and len(x) >= 3}
signal.signal(signal.SIGALRM, lambda a,b: (_ for _ in ()).throw(TimeoutError()))
hit = miss = 0; miss_rows = []; hit_ex = []
for n, (acc, items) in enumerate(tasks.items()):
    p = EXC / f"{acc}.html.gz"
    if not p.exists(): continue
    try:
        txt = _strip(gzip.open(p,"rt",encoding="utf-8",errors="ignore").read())
    except Exception:
        continue
    signal.alarm(15)
    try:
        for c, m, bzv, base in items:
            if any(f in txt for f in forms(m, bzv)):
                hit += 1
                if len(hit_ex) < 10: hit_ex.append(f"{c}/{m}")
            else:
                miss += 1
                if base:
                    unit = 1e6 if m=="rev" else 1
                    miss_rows.append((c, m, round((bzv*unit/base-1)*100, 1)))
    except TimeoutError:
        pass
    finally:
        signal.alarm(0); del txt; gc.collect()
    if (n+1) % 60 == 0: print(f"  …{n+1}/{len(tasks)}", flush=True)
tot = hit + miss
print(f"\n미확보 {tot}건 · BZ 금액이 원문에 **있음** {hit}건 ({hit*100//max(1,tot)}%) → 파서 개선 여지")
print(f"                    · 원문에 **없음** {miss}건 ({miss*100//max(1,tot)}%) → 환산·콜 전용")
print("있음 예:", ", ".join(hit_ex))
g = sorted(abs(v) for _,_,v in miss_rows)
if g:
    n2 = len(g)
    print(f"\n[원문에 없는 군의 'BZ값 vs 컨센' 갭] {n2}건 · 중앙 {g[n2//2]:.1f}% · "
          f"|갭|<1% {sum(1 for v in g if v<1)*100//n2}% · <3% {sum(1 for v in g if v<3)*100//n2}% · "
          f">5% {sum(1 for v in g if v>5)*100//n2}%")
    print("  큰 순:", sorted(miss_rows, key=lambda x:-abs(x[2]))[:8])
