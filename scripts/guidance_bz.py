#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""guidance_bz.py — Benzinga 가이던스 **검증용** 수집 (저속·순차) · 2026-08-10 신설.

왜 Benzinga 인가
----------------
무료 종목 페이지 HTML 안에 구조화된 가이던스 JSON 이 들어 있고, 필드가 우리에게 딱 맞다:
  period("FY"/"Q1".."Q4") · period_year · eps_type("Adj"/"GAAP") · 이전 가이던스
우리 8-K 파서가 가장 자주 틀리는 두 가지(연간↔분기, GAAP↔조정)를 **데이터가 직접** 알려주므로
대조에 최적이다. MarketBeat 는 기간·기준 표기가 없어 컨센 역매칭에 의존해야 했다.

**저속이 필수다** — 동시 20건을 던졌다가 HTTP 429 로 서버 IP 가 한 시간 넘게 막혔다.
그래서 이 수집기는 ①순차 ②요청 간 5초 ③429 를 만나면 지수 백오프 후 그날치 중단
④이미 받은 발표는 캐시로 건너뛰기 로 동작한다. 하루에 다 못 받아도 다음 날 이어서 채운다.

저장(검증 전용 · 판정에는 쓰지 않는다)
  g_rev_p / g_rev_gap_p / g_rev_per_p · g_eps_p / g_eps_gap_p / g_eps_per_p
  g_bz_period(FY/Q1..) · g_bz_type(Adj/GAAP) · g_bz_date

사용: guidance_bz.py [--days 45] [--limit N] [--gap 5]
cron: 매일 09:10 (백필·join 뒤). 오래 걸리므로 flock 으로 중복 실행을 막는다.
"""
import json, re, sys, time, urllib.request
from datetime import datetime, timedelta
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
POOL = BASE / "data" / "db" / "screener_pool.json"
LIVE = BASE / "data" / "db" / "earnings_live_us.json"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"}
ARG = lambda k, d: (int(sys.argv[sys.argv.index(k) + 1]) if k in sys.argv else d)
DAYS, LIMIT, GAP = ARG("--days", 45), ARG("--limit", 0), ARG("--gap", 5)
P_FIELDS = ("g_rev_p", "g_rev_gap_p", "g_rev_per_p", "g_eps_p", "g_eps_gap_p", "g_eps_per_p",
            "g_bz_period", "g_bz_type", "g_bz_date")
NUM = lambda v: (float(v) if v not in (None, "", "0.000") else None)


def fetch(sym):
    """→ (레코드 리스트, 429 여부). 레코드는 최신순."""
    try:
        h = urllib.request.urlopen(urllib.request.Request(
            f"https://www.benzinga.com/quote/{sym.upper()}/earnings-forecasts",
            headers=UA), timeout=25).read().decode("utf-8", "ignore")
    except Exception as e:
        return [], ("429" in str(e))
    out = []
    for m in re.finditer(r"eps_guidance_est", h):
        a, b = h.rfind("{", 0, m.start()), h.find("}", m.end())
        if a < 0 or b < 0:
            continue
        try:
            d = json.loads(h[a:b + 1].replace('\\"', '"'))
        except Exception:
            continue
        if "period_year" not in d:
            continue
        out.append(d)
    out.sort(key=lambda d: str(d.get("date") or ""), reverse=True)
    return out, False


def main():
    pool = {r.get("c"): r for r in (json.loads(POOL.read_text(encoding="utf-8")).get("us") or [])
            if r.get("c")}
    live = json.loads(LIVE.read_text(encoding="utf-8"))
    cut = (datetime.now() - timedelta(days=DAYS)).strftime("%Y%m%d")
    todo = [it for d8 in sorted(live.get("days") or {}, reverse=True) if d8 >= cut
            for it in live["days"][d8]
            if it.get("c") in pool and it.get("g_bz_date") is None]      # 이미 받은 건 건너뛴다
    if LIMIT:
        todo = todo[:LIMIT]
    print(f"[bz] 대상 {len(todo)}건 (최근 {DAYS}일 · 간격 {GAP}초 · 예상 {len(todo)*GAP//60}분)", flush=True)
    got = same = diff = 0
    for n, it in enumerate(todo):
        rows, blocked = fetch(it["c"])
        if blocked:
            print(f"[bz] 429 — {n}건까지 받고 중단(다음 실행에서 이어받는다)", flush=True)
            break
        time.sleep(GAP)
        if not rows:
            continue
        r = pool[it["c"]]
        d = rows[0]                       # 가장 최근 가이던스
        per = {"FY": "0y"}.get(d.get("period")) or (
            "0q" if str(d.get("period", "")).startswith("Q") else None)
        it["g_bz_period"] = f"{d.get('period')}{d.get('period_year')}"
        it["g_bz_type"] = d.get("eps_type")
        it["g_bz_date"] = d.get("date")
        for metric, lo_k, hi_k, base_k, gk in (
                ("eps", "eps_guidance_min", "eps_guidance_max", ("ey0" if per == "0y" else "eq0"), "g_eps"),
                ("rev", "revenue_guidance_min", "revenue_guidance_max", ("ry0" if per == "0y" else "rq0"), "g_rev")):
            lo, hi = NUM(d.get(lo_k)), NUM(d.get(hi_k))
            base = r.get(base_k)
            if lo is None or hi is None or not base:
                continue
            mid = (lo + hi) / 2
            if metric == "rev":
                mid *= 1e6                # 포털 매출은 백만 단위
            it[gk + "_p"] = round(mid / (1e6 if metric == "rev" else 1), 2)
            it[gk + "_gap_p"] = round((mid / base - 1) * 100, 1)
            it[gk + "_per_p"] = per
            got += 1
            mine = it.get(gk)
            if mine:
                (same, diff) = (same + 1, diff) if abs(mid / (1e6 if metric == "rev" else 1) / mine - 1) <= 0.01 \
                    else (same, diff + 1)
        if (n + 1) % 20 == 0:
            _save(live)
            print(f"    [{n+1}/{len(todo)}] 값 {got} · 일치 {same} · 불일치 {diff}", flush=True)
    _save(live)
    print(f"[bz] 완료 — 값 {got}건 · 파싱과 일치 {same} · 불일치 {diff} (검증 전용)")


def _save(live):
    """내 필드만 디스크에 얹는다(다른 수집기 결과를 덮지 않는다)."""
    try:
        disk = json.loads(LIVE.read_text(encoding="utf-8"))
    except Exception:
        disk = live
    idx = {(d8, it["c"]): it for d8, arr in (live.get("days") or {}).items()
           for it in arr if it.get("c")}
    for d8, arr in (disk.get("days") or {}).items():
        for it in arr:
            src = idx.get((d8, it.get("c")))
            if not src:
                continue
            for k in P_FIELDS:
                if src.get(k) is not None:
                    it[k] = src[k]
    tmp = LIVE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(disk, ensure_ascii=False), encoding="utf-8")
    tmp.replace(LIVE)


if __name__ == "__main__":
    main()
