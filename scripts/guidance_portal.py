#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""guidance_portal.py — 가이던스 2단계 승격: 직접 파싱 → 포털 교차검증 (2026-08-10 신설).

설계 (사용자 제안)
------------------
  1단계  회사가 발표하면 **우리가 8-K 보도자료를 직접 파싱**한 값을 즉시 쓴다(발표 수 분 내).
  2단계  며칠 뒤 포털(MarketBeat)이 같은 가이던스를 정리해 올리면 그것과 **대조**한다.
           · 일치(±1%)  → 'verified' 표시. 값은 그대로, 신뢰도만 올라간다.
           · 불일치     → 포털 값으로 교체('portal'). 우리 값은 근거와 함께 남겨 감사 가능.
           · 포털 미제공 → 우리 값 유지('8-K').

왜 포털을 '그대로 대체'하지 않는가 (실측)
-----------------------------------------
MarketBeat 의 'Company Guidance' 열은 회사마다 **매출인지 EPS인지, 단위가 무엇인지**
표기가 없다 — NVDA 는 '$52.9 B - $55.1 B'(매출), QCOM 은 '2.050 - 2.250'(EPS).
게다가 분기 라벨(Q3 2026)이 회사 회계연도 기준이라 우리 분기와 어긋난다.
그래서 라벨을 믿지 않고 **컨센서스 값으로 역매칭**한다 — MarketBeat 가 같은 행에 적어 둔
EPS/매출 컨센이 우리 컨센(eq0/rq0 등)과 일치하는 행만 그 분기의 가이던스로 인정한다.
이 방식으로 QCOM Q4 EPS(2.05~2.25)·WAT Q3 EPS(3.95~4.05)가 우리 파싱값과 정확히 일치함을 확인했다.

사용: guidance_portal.py [--days 30] [--limit N]
cron: 매일 08:40 (guidance_backfill·earnings_join 뒤)
"""
import json, re, sys, time, urllib.request
from datetime import datetime, timedelta
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
POOL = BASE / "data" / "db" / "screener_pool.json"
LIVE = BASE / "data" / "db" / "earnings_live_us.json"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36"}
ARG = lambda k, d: (int(sys.argv[sys.argv.index(k) + 1]) if k in sys.argv else d)
DAYS, LIMIT = ARG("--days", 30), ARG("--limit", 0)
TOL = 0.01                      # 1% 이내면 같은 값으로 본다(반올림 표기 차이 흡수)


def _v(s):
    """'$52.9 B' → 52900(백만) · '2.050' → 2.05 · '' → None"""
    s = (s or "").strip()
    m = re.match(r"\$?\s*([\d,.]+)\s*([BMK])?\b", s)
    if not m:
        return None, None
    try:
        x = float(m.group(1).replace(",", ""))
    except Exception:
        return None, None
    u = (m.group(2) or "").upper()
    if u == "B":
        return x * 1e3, "rev"          # 백만 단위 매출
    if u == "M":
        return x, "rev"
    return x, "eps"                    # 단위 없음 = 주당 금액


def fetch_rows(sym):
    """MarketBeat 추정 표 → [{eps컨센, 매출컨센(백만), 가이던스 lo/hi, 종류}]"""
    try:
        h = urllib.request.urlopen(urllib.request.Request(
            f"https://www.marketbeat.com/stocks/NASDAQ/{sym.upper()}/earnings/", headers=UA),
            timeout=20).read().decode("utf-8", "ignore")
    except Exception:
        return []
    i = h.find("Company Revenue Guidance")
    if i < 0:
        return []
    seg = h[max(0, i - 500):i + 4000]
    out = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", seg, re.S):
        cs = [re.sub(r"<[^>]+>", "", c).strip() for c in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
        # 열: 분기 | 추정수 | 최저 | 최고 | 평균EPS | 매출컨센 | 회사 가이던스
        if len(cs) < 7 or not cs[0]:
            continue
        epsE, _ = _v(cs[4])
        revE, _ = _v(cs[5])
        g = cs[6]
        mg = re.match(r"(.+?)\s*-\s*(.+)$", g)
        if not mg:
            continue
        lo, k1 = _v(mg.group(1))
        hi, k2 = _v(mg.group(2))
        if lo is None or hi is None or k1 != k2:
            continue
        out.append({"per": cs[0], "epsE": epsE, "revE": revE, "lo": lo, "hi": hi, "kind": k1})
    return out


def main():
    pool = json.loads(POOL.read_text(encoding="utf-8"))
    by = {r.get("c"): r for r in (pool.get("us") or []) if r.get("c")}
    live = json.loads(LIVE.read_text(encoding="utf-8"))
    cut = (datetime.now() - timedelta(days=DAYS)).strftime("%Y%m%d")
    todo = []
    for d8 in sorted(live.get("days") or {}):
        if d8 < cut:
            continue
        for it in live["days"][d8]:
            if it.get("c") in by and (it.get("g_rev") is not None or it.get("g_eps") is not None):
                todo.append(it)
    if LIMIT:
        todo = todo[:LIMIT]
    print(f"[gpor] 대조 대상 {len(todo)}건 (최근 {DAYS}일 · 파싱값 보유분)", flush=True)
    ver = rep = 0
    for n, it in enumerate(todo):
        sym = it["c"]
        r = by[sym]
        rows = fetch_rows(sym)
        time.sleep(0.3)
        if not rows:
            it["g_src"] = it.get("g_src") or "8-K"
            continue
        for metric, gk, pk in (("rev", "g_rev", "g_rev_per"), ("eps", "g_eps", "g_eps_per")):
            mine = it.get(gk)
            if mine is None:
                continue
            per = it.get(pk) or "0q"
            # 컨센 역매칭 — 라벨 대신 값으로 어느 분기인지 확정한다
            base = {"0q": ("eq0", "rq0"), "+1q": ("eq1", "rq1"),
                    "0y": ("ey0", "ry0"), "+1y": ("ey1", "ry1")}.get(per)
            if not base:
                continue
            ce, cr = r.get(base[0]), r.get(base[1])
            cr = cr / 1e6 if cr else None
            hit = None
            for row in rows:
                if row["kind"] != metric:
                    continue
                ok_e = ce and row.get("epsE") and abs(row["epsE"] / ce - 1) <= 0.02
                ok_r = cr and row.get("revE") and abs(row["revE"] / cr - 1) <= 0.02
                if ok_e or ok_r:
                    hit = row
                    break
            if not hit:
                it["g_src"] = it.get("g_src") or "8-K"
                continue
            pmid = (hit["lo"] + hit["hi"]) / 2
            if abs(pmid / mine - 1) <= TOL:                 # 일치 → 교차검증 완료
                it[gk + "_src"] = "verified"
                ver += 1
            else:                                            # 불일치 → 포털 채택, 우리 값 보존
                it[gk + "_own"] = mine
                it[gk] = round(pmid, 2 if metric == "eps" else 1)
                cbase = ce if metric == "eps" else cr
                if cbase:
                    it[("g_eps_gap" if metric == "eps" else "g_rev_gap")] = round((pmid / cbase - 1) * 100, 1)
                it[gk + "_src"] = "portal"
                rep += 1
        if (n + 1) % 50 == 0:
            LIVE.write_text(json.dumps(live, ensure_ascii=False), encoding="utf-8")
            print(f"    [{n+1}/{len(todo)}] 검증 {ver} · 교체 {rep}", flush=True)
    LIVE.write_text(json.dumps(live, ensure_ascii=False), encoding="utf-8")
    print(f"[gpor] 완료 — 교차검증 일치 {ver} · 포털 값으로 교체 {rep} / {len(todo)}건")


if __name__ == "__main__":
    main()
