#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""earnings_watch_us.py — 미국 어닝 서프라이즈 감지 (2026-08-05 신설).

미국 실적의 최초 발표 = 보도자료 + SEC 8-K(실측: PLTR 마감 6분 뒤 접수)이지만,
정형 수치는 Yahoo 가 발표 직후 earningsHistory 에 실제 EPS·서프라이즈% 를 반영한다
(실측: PLTR 발표 다음날 epsActual 0.41 / est 0.346 / 서프 +18.5% 확인) → 이를 폴링.

대상: screener_pool.us 중 어닝일(ed)이 [오늘-lookback, 오늘] 인 종목만 (호출 최소화 · 기수집 스킵)
판정: 서프라이즈 ≥+10% '어닝비트' · ≤-10% '어닝미스' · 예상밖 흑자/적자
산출: data/db/earnings_live_us.json {asof, days:{YYYYMMDD:[{c,n,cap,eps,est,spr,tags,t}]}} 45일 유지
사용: earnings_watch_us.py [--days N]   (기본 lookback 2일 · 백필 시 --days 45)
cron: */5 05-08 * * 2-6 (애프터장 발표=KST 새벽) + */5 19-22 * * 1-5 (프리장 발표=KST 저녁) · flock 중복방지
"""
import http.cookiejar, json, sys, time, urllib.request, urllib.parse
from datetime import datetime, timedelta
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "data" / "db" / "earnings_live_us.json"
LOOK = 2
if "--days" in sys.argv:
    LOOK = int(sys.argv[sys.argv.index("--days") + 1])
UA = {"User-Agent": "Mozilla/5.0"}

def yahoo_opener():
    cj = http.cookiejar.CookieJar()
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    op.addheaders = list(UA.items())
    try: op.open("https://fc.yahoo.com", timeout=10)
    except Exception: pass
    crumb = op.open("https://query1.finance.yahoo.com/v1/test/getcrumb", timeout=10).read().decode()
    return op, crumb

def main():
    old = {}
    try: old = json.loads(OUT.read_text(encoding="utf-8"))
    except Exception: pass
    days = old.get("days") or {}
    # 8-K 감시기가 먼저 만든 항목(eps 미채움)은 '기수집'으로 치지 않는다 — 야후 수치를 채워야 함
    seen = {it["c"] for v in days.values() for it in v if it.get("eps") is not None}
    pool = json.loads((BASE / "data" / "db" / "screener_pool.json").read_text(encoding="utf-8"))
    today = datetime.now().date()
    lo = (today - timedelta(days=LOOK)).isoformat()
    cand = [r for r in (pool.get("us") or [])
            if r.get("ed") and lo <= r["ed"] <= today.isoformat() and r.get("c") not in seen]
    cand.sort(key=lambda r: -(r.get("cap") or 0))   # (2026-08-05) 시총 큰 주요종목부터 — 먼저·빨리 잡히게
    print(f"[us] 어닝창({lo}~{today}) 후보 {len(cand)}종 (기수집 제외)")
    if not cand:
        return save(days, 0)
    op, crumb = yahoo_opener()
    new = 0
    for i, r in enumerate(cand):
        sym = r["c"]
        try:
            u = (f"https://query2.finance.yahoo.com/v10/finance/quoteSummary/{urllib.parse.quote(sym)}"
                 f"?modules=earningsHistory&crumb={urllib.parse.quote(crumb)}")
            j = json.loads(op.open(u, timeout=12).read())
            eh = ((j["quoteSummary"]["result"][0].get("earningsHistory") or {}).get("history")) or []
        except Exception:
            continue
        # 최신 분기 중 실제치가 이미 채워진 항목 — 분기말이 어닝일보다 과거인 최신 것
        best = None
        for x in eh:
            ea = (x.get("epsActual") or {}).get("raw")
            if ea is None:
                continue
            q = (x.get("quarter") or {}).get("fmt") or ""
            if best is None or q > best[0]:
                best = (q, x)
        if not best:
            continue
        q, x = best
        # 이 분기 실제치가 '이번 어닝'인지 — 분기말이 어닝일 기준 5개월 이내면 이번 발표로 본다
        try:
            if (datetime.fromisoformat(r["ed"]).date() - datetime.fromisoformat(q).date()).days > 150:
                continue
        except Exception:
            pass
        ea = (x.get("epsActual") or {}).get("raw")
        ee = (x.get("epsEstimate") or {}).get("raw")
        sp = (x.get("surprisePercent") or {}).get("raw")
        sp = round(sp * 100, 1) if sp is not None else None
        tg = []
        if sp is not None:
            if sp >= 10: tg.append(f"어닝비트 +{sp:.0f}%")
            elif sp <= -10: tg.append(f"어닝미스 {sp:.0f}%")
        if ee is not None and ea is not None:
            if ee <= 0 < ea: tg.append("예상밖 흑자")
            elif ea < 0 <= ee: tg.append("예상밖 적자")
        d8 = r["ed"].replace("-", "")
        it = {"c": sym, "n": r.get("kn") or r.get("n") or sym, "cap": r.get("cap"),
              "eps": ea, "est": ee, "spr": sp, "tags": tg,
              "t": datetime.now().strftime("%H:%M")}
        days.setdefault(d8, [])
        # (2026-08-05) 8-K 감시기(earnings_8k_watch)가 먼저 만든 항목의 태그·접수번호는 보존
        prev = next((z for z in days[d8] if z["c"] == sym), None)
        if prev:
            for t_ in prev.get("tags") or []:
                if "8-K" in t_ and t_ not in it["tags"]:
                    it["tags"].insert(0, t_)
            if prev.get("acc"):
                it["acc"] = prev["acc"]
        days[d8] = [z for z in days[d8] if z["c"] != sym] + [it]
        new += 1
        if new <= 25 or tg:
            print(f"  🔔 {sym} {it['n']} EPS {ea} vs {ee} 서프 {sp}% {tg}")
        time.sleep(0.06)
        if i % 200 == 199:
            print(f"  {i+1}/{len(cand)}")
    save(days, new)

def save(days, new):
    cut = (datetime.now() - timedelta(days=45)).strftime("%Y%m%d")
    days = {d: v for d, v in days.items() if d >= cut}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"asof": datetime.now().strftime("%Y-%m-%d %H:%M"), "days": days},
                              ensure_ascii=False), encoding="utf-8")
    tot = sum(len(v) for v in days.values())
    print(f"[us] ✅ 신규 {new}건 · 누적 {tot}건({len(days)}일) → {OUT}")

if __name__ == "__main__":
    main()
