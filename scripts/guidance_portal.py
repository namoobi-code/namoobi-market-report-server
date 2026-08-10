#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""guidance_portal.py — 가이던스 **검증용** 포털 값 수집 (2026-08-10 재작성).

역할 (사용자 지정)
------------------
  · 표시·판정에 쓰는 값은 **우리가 8-K 보도자료에서 직접 파싱한 것**뿐이다.
  · 포털(MarketBeat) 값은 **오직 대조·검증용**으로 따로 저장한다 —
    같은 화면·필터에 나란히 놓고 "우리 파싱이 맞나"를 눈으로 확인하기 위함.
  · 포털 값으로 우리 값을 덮어쓰거나 자동 교정하지 **않는다**(그건 파싱 실패를 숨기는 것).

왜 그대로 못 쓰는가 (실측)
--------------------------
MarketBeat 'Company Guidance' 열은 회사마다 매출인지 EPS인지·단위가 무엇인지 표기가 없다
(NVDA '$52.9 B - $55.1 B'=매출 · QCOM '2.050 - 2.250'=EPS). 분기 라벨도 회계연도 기준이라
우리 분기와 어긋난다. 그래서 라벨을 믿지 않고 **컨센 값으로 역매칭**해 기간을 확정한다
(MarketBeat 가 같은 행에 적어 둔 EPS/매출 컨센이 우리 컨센과 일치하는 행만 인정).

저장 필드 (earnings_live_us 의 해당 발표 항목)
  g_rev_gap_p / g_eps_gap_p   포털 기준 갭%  (검증 전용)
  g_rev_p     / g_eps_p       포털 가이던스 중간값
  g_rev_per_p / g_eps_per_p   포털 값이 매칭된 기간(0q/+1q/0y/+1y)

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


def _v(s):
    """'$52.9 B' → (52900, 'rev') · '2.050' → (2.05, 'eps') · '' → (None, None)"""
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
    """MarketBeat 추정 표 → [{epsE, revE(백만), lo, hi, kind}]

    URL 에 거래소가 들어가는데 우리 풀에는 거래소 구분이 없어 NASDAQ·NYSE 를 차례로 시도한다
    (실측: NVDA·QCOM 은 NASDAQ, ABT 는 NYSE — 하나만 쓰면 NYSE 종목이 전부 빈다).
    """
    h = ""
    for exch in ("NASDAQ", "NYSE", "NYSEAMERICAN"):
        try:
            h = urllib.request.urlopen(urllib.request.Request(
                f"https://www.marketbeat.com/stocks/{exch}/{sym.upper()}/earnings/", headers=UA),
                timeout=20).read().decode("utf-8", "ignore")
        except Exception:
            h = ""
        if "Company Revenue Guidance" in h:
            break
    # 열 구성이 종목마다 다르다(실측): 매출 가이던스만·EPS 가이던스만·둘 다·매출컨센 유무.
    #   NVDA  분기|추정수|최저|최고|평균EPS|매출컨센|회사 매출 가이던스
    #   ABT   분기|추정수|최저|최고|평균EPS|회사 EPS 가이던스              ← 6열
    #   QCOM  분기|추정수|최저|최고|평균EPS|매출컨센|회사 EPS 가이던스|회사 매출 가이던스
    # 위치를 고정하면 6열짜리가 통째로 빠진다(실측 ABT·AMGN·XRAY·SRE 전부 0건).
    # 그래서 **헤더 이름으로 열 번호를 찾는다**.
    m = re.search(r"<thead>(.*?)</thead>(.*?)</tbody>", h, re.S)
    while m and "Guidance" not in m.group(1):
        h = h[m.end():]
        m = re.search(r"<thead>(.*?)</thead>(.*?)</tbody>", h, re.S)
    if not m:
        return []
    cols = [re.sub(r"<[^>]+>", "", c).strip()
            for c in re.findall(r"<th[^>]*>(.*?)</th>", m.group(1), re.S)]
    ix = lambda name: next((i for i, c in enumerate(cols) if c == name), None)
    i_eps, i_rev = ix("Average Estimate"), ix("Revenue Estimate")
    i_geps, i_grev = ix("Company EPS Guidance"), ix("Company Revenue Guidance")
    out = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", m.group(2), re.S):
        cs = [re.sub(r"<[^>]+>", "", c).strip() for c in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
        if len(cs) < len(cols) or not cs[0]:
            continue
        epsE = _v(cs[i_eps])[0] if i_eps is not None else None
        revE = _v(cs[i_rev])[0] if i_rev is not None else None
        for gi, metric in ((i_geps, "eps"), (i_grev, "rev")):
            if gi is None:
                continue
            mg = re.match(r"(.+?)\s*-\s*(.+)$", cs[gi])
            if not mg:
                continue
            lo = _v(mg.group(1))[0]
            hi = _v(mg.group(2))[0]
            if lo is None or hi is None or hi < lo:
                continue
            out.append({"epsE": epsE, "revE": revE, "lo": lo, "hi": hi, "kind": metric})
    return out


P_FIELDS = ("g_rev_p", "g_rev_gap_p", "g_rev_per_p", "g_eps_p", "g_eps_gap_p", "g_eps_per_p")


def _save(live):
    """저장 직전 디스크를 다시 읽어 **내 필드만** 얹는다.

    (2026-08-10) 이 파일은 여러 스크립트가 통째로 읽고 쓴다. 그대로 덮어쓰면 내가
    읽은 뒤에 다른 스크립트가 채운 값이 사라진다 — 실측으로 가이던스 갭 479건이
    한 번에 날아갔다(풀에서 겪은 덮어쓰기와 같은 문제). 임시 파일에 쓰고 rename 해
    중간에 죽어도 파일이 깨지지 않게 한다.
    """
    try:
        disk = json.loads(LIVE.read_text(encoding="utf-8"))
    except Exception:
        disk = live
    idx = {}
    for d8, arr in (live.get("days") or {}).items():
        for it in arr:
            if it.get("c"):
                idx[(d8, it["c"])] = it
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


def main():
    pool = json.loads(POOL.read_text(encoding="utf-8"))
    by = {r.get("c"): r for r in (pool.get("us") or []) if r.get("c")}
    live = json.loads(LIVE.read_text(encoding="utf-8"))
    cut = (datetime.now() - timedelta(days=DAYS)).strftime("%Y%m%d")
    todo = [it for d8 in sorted(live.get("days") or {}) if d8 >= cut
            for it in live["days"][d8] if it.get("c") in by]
    if LIMIT:
        todo = todo[:LIMIT]
    print(f"[gpor] 검증 대상 {len(todo)}건 (최근 {DAYS}일)", flush=True)
    got = same = diff = 0
    for n, it in enumerate(todo):
        sym = it["c"]
        r = by[sym]
        rows = fetch_rows(sym)
        time.sleep(0.3)
        if not rows:
            continue
        for metric, gk in (("rev", "g_rev"), ("eps", "g_eps")):
            # 기간은 우리 파싱 결과의 기간을 기준으로 같은 기간의 포털 값을 찾는다.
            # (우리 값이 없으면 진행분기 0q 기준으로 조회 — 검증 목적상 그래도 보여준다)
            per = it.get(gk + "_per") or it.get("g_per") or "0q"
            base = {"0q": ("eq0", "rq0"), "+1q": ("eq1", "rq1"),
                    "0y": ("ey0", "ry0"), "+1y": ("ey1", "ry1")}.get(per)
            if not base:
                continue
            ce = r.get(base[0])
            cr = r.get(base[1])
            cr = cr / 1e6 if cr else None
            hit = None
            for row in rows:
                if row["kind"] != metric:
                    continue
                ok_e = ce and row.get("epsE") and abs(row["epsE"] / ce - 1) <= 0.02
                ok_r = cr and row.get("revE") and abs(row["revE"] / cr - 1) <= 0.02
                if ok_e or ok_r:                       # 컨센 역매칭으로 기간 확정
                    hit = row
                    break
            if not hit:
                continue
            mid = (hit["lo"] + hit["hi"]) / 2
            cbase = ce if metric == "eps" else cr
            if not cbase:
                continue
            it[gk + "_p"] = round(mid, 2 if metric == "eps" else 1)
            it[gk + "_gap_p"] = round((mid / cbase - 1) * 100, 1)
            it[gk + "_per_p"] = per
            got += 1
            mine = it.get(gk)
            if mine:
                if abs(mid / mine - 1) <= 0.01:
                    same += 1
                else:
                    diff += 1
        if (n + 1) % 50 == 0:
            _save(live)
            print(f"    [{n+1}/{len(todo)}] 포털값 {got} · 일치 {same} · 불일치 {diff}", flush=True)
    _save(live)
    print(f"[gpor] 완료 — 포털값 {got}건 · 우리 파싱과 일치 {same} · 불일치 {diff} "
          f"(포털 값은 검증 전용 — 판정·표시에는 사용하지 않음)")


if __name__ == "__main__":
    main()
