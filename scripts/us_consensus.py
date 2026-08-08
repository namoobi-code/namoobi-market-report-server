#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""us_consensus.py — 미국 컨센서스·서프라이즈만 따로 채우는 패치 (2026-08-09 신설).

왜 별도 스크립트인가
--------------------
screener_pool.py 가 이 값들을 함께 받지만, 풀 전체 빌드는 30분~1시간이 걸리고
수급·대차·ETF 등 다른 단계에서 막히면 실적 필드까지 통째로 늦어진다
(실측: 2026-08-09 풀 빌드가 [lend] 단계에서 25분 정지 → 스크리너 필터가 전부 0건).
실적 필드는 Yahoo 한 번 호출이면 끝나므로 독립적으로 돌 수 있어야 한다.

받는 값 (quoteSummary earningsTrend + earningsHistory · 무료)
  spr   최근 분기 EPS 서프라이즈%      (0.137 → 13.7%)
  sprb  최근 4분기 중 컨센 상회 횟수
  spra  4분기 서프라이즈 중위값        (평균은 흑자전환 분기 하나에 폭주 — 실측 INTC +1361%)
  cr30  다음분기·당분기 EPS 컨센 30일 리비전 (Yahoo 가 과거값을 함께 줘 즉시 산출)
  cr7 · cr90 · cup(30일 상향 애널수) · cdn(하향)
  eq1   다음분기 EPS 컨센 · rq1 다음분기 매출 컨센  ← 8-K 가이던스 갭 계산의 기준

사용: us_consensus.py [--limit N] [--workers N]
cron: 풀 빌드와 별개로 매일 08:00 (미 정규장 마감 후)
"""
import http.cookiejar, json, sys, time, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
POOL = BASE / "data" / "db" / "screener_pool.json"
UA = {"User-Agent": "Mozilla/5.0"}
ARG = lambda k, d: (int(sys.argv[sys.argv.index(k) + 1]) if k in sys.argv else d)
LIMIT = ARG("--limit", 0)
WORKERS = ARG("--workers", 6)


def opener():
    """쿠키+crumb 확보. fc.yahoo.com 은 서버 환경에 따라 404 를 뱉으므로(실측) 실패해도 진행한다
    — 쿠키는 getcrumb 응답에서도 받아지기 때문에 crumb 만 얻으면 된다."""
    cj = http.cookiejar.CookieJar()
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    op.addheaders = list(UA.items())
    try:
        op.open("https://fc.yahoo.com", timeout=10)
    except Exception:
        pass
    crumb = op.open("https://query1.finance.yahoo.com/v1/test/getcrumb", timeout=10).read().decode()
    return op, crumb


def _raw(x):
    return (x or {}).get("raw") if isinstance(x, dict) else None


def parse(fd):
    out = {}
    et = (fd.get("earningsTrend") or {}).get("trend", []) or []

    def rv(days):
        vs = []
        for per in ("0q", "+1q"):
            t = next((x for x in et if x.get("period") == per), None)
            if not t:
                continue
            tr = t.get("epsTrend") or {}
            cur, ago = _raw(tr.get("current")), _raw(tr.get(days))
            # 추정치가 음수·0 근처면 비율이 폭주한다 → 양수만
            if cur is not None and ago and ago > 0:
                vs.append(cur / ago - 1.0)
        return round(sum(vs) / len(vs), 4) if vs else None

    for lab, d in (("cr7", "7daysAgo"), ("cr30", "30daysAgo"), ("cr90", "90daysAgo")):
        v = rv(d)
        if v is not None:
            out[lab] = v
    t1 = next((x for x in et if x.get("period") == "+1q"), None)
    if t1:
        rr = t1.get("epsRevisions") or {}
        out["cup"] = _raw(rr.get("upLast30days")) or 0
        out["cdn"] = _raw(rr.get("downLast30days")) or 0
        ee, re_ = t1.get("earningsEstimate") or {}, t1.get("revenueEstimate") or {}
        for k, v in (("eq1", _raw(ee.get("avg"))), ("rq1", _raw(re_.get("avg"))),
                     ("nan1", _raw(ee.get("numberOfAnalysts")))):
            if v is not None:
                out[k] = v

    hs = (fd.get("earningsHistory") or {}).get("history", []) or []
    vs = sorted([((h.get("quarter") or {}).get("fmt") or "", _raw(h.get("surprisePercent")))
                 for h in hs if _raw(h.get("surprisePercent")) is not None], key=lambda x: x[0])
    if vs:
        last4 = sorted(v for _, v in vs[-4:])
        n = len(last4)
        med = last4[n // 2] if n % 2 else (last4[n // 2 - 1] + last4[n // 2]) / 2
        # Yahoo 는 비율(0.137)로 준다 → 화면·필터가 쓰는 %로 환산
        out["spr"] = round(vs[-1][1] * 100, 1)
        out["sprb"] = sum(1 for v in last4 if v > 0)
        out["sprn"] = n
        out["spra"] = round(med * 100, 1)
    return out


def main():
    pool = json.loads(POOL.read_text(encoding="utf-8"))
    us = pool.get("us") or []
    syms = [r["c"] for r in us if r.get("c")]
    if LIMIT:
        syms = syms[:LIMIT]
    op, crumb = opener()
    print(f"[uscons] 대상 {len(syms)}종목", flush=True)

    def one(sym):
        for att in range(2):
            try:
                u = (f"https://query2.finance.yahoo.com/v10/finance/quoteSummary/{sym}"
                     f"?modules=earningsTrend,earningsHistory&crumb={urllib.parse.quote(crumb)}")
                j = json.loads(op.open(u, timeout=15).read())
                return sym, parse((j["quoteSummary"]["result"] or [{}])[0])
            except Exception:
                time.sleep(0.4 * (att + 1))
        return sym, {}

    got = {}
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        for i, (sym, d) in enumerate(ex.map(one, syms)):
            if d:
                got[sym] = d
            if (i + 1) % 500 == 0:
                print(f"    [{i+1}/{len(syms)}] 확보 {len(got)}", flush=True)
    n = 0
    for r in us:
        d = got.get(r.get("c"))
        if d:
            r.update(d); n += 1
    pool["us_cons_asof"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    POOL.write_text(json.dumps(pool, ensure_ascii=False), encoding="utf-8")
    have = lambda k: sum(1 for r in us if r.get(k) is not None)
    print(f"[uscons] 패치 {n}/{len(us)} · spr {have('spr')} · cr30 {have('cr30')} · rq1 {have('rq1')}")


if __name__ == "__main__":
    main()
