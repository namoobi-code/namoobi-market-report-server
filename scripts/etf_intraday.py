#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# etf_intraday.py — 장중 ETF 풀 5분 증분 갱신. (2026-07-26 신설, 종목 intraday 와 동형)
#   KR(정규장): 네이버 etfItemList 1콜 → px·chg·cap·tv 실시간 + 앵커(a1m/a3m/a6m/a1y·ma200a·hi52a)로
#               수익률 4종·200일선·고점比 O(1) 재계산.
#   US(미국장): Yahoo v7 quotes 배치(50/콜) → px·chg·cap·tv + 52주변화율(r1y)·200일선·고점比 실시간,
#               앵커로 r1m/r3m/r6m 재계산.
#   변동성(vol20)은 일봉 필요 → 하루 2회 기준 유지.
import os, sys, json, re, urllib.request, urllib.parse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from datetime import datetime, timedelta, timezone
import ta_screen as T

KST = timezone(timedelta(hours=9))
UA = {"User-Agent": "Mozilla/5.0"}


def _kr_session(now):
    # (2026-07-26) 정규장 + 시간외 전체 — 장전 시간외 08:30 ~ 시간외 단일가 18:00 (KST)
    if now.weekday() >= 5:
        return False
    hm = now.hour*60 + now.minute
    return 8*60+28 <= hm <= 18*60+2


def _us_session(now):
    # (2026-07-26) 정규장 + 프리·애프터마켓 전체 (KST). 썸머타임 적용/미적용 모두 커버:
    #   프리 17:00(썸머)/18:00 ~ 정규 22:30/23:30~05:00/06:00 ~ 애프터 07:00 → 16:50~07:10 로 넓게.
    wd = now.weekday()
    hm = now.hour*60 + now.minute
    if wd <= 3:                        # 월~목: 당일 저녁 프리 ~ 다음날 새벽 애프터
        return hm >= 16*60+50 or hm <= 7*60+10
    if wd == 4:                        # 금: 저녁 프리 이후만 (토 새벽까지는 아래에서)
        return hm >= 16*60+50
    if wd == 5:                        # 토: 금 장 애프터 새벽까지
        return hm <= 7*60+10
    return False                       # 일: 없음


def _rr(px, anchor):
    return round(px/anchor-1, 4) if (anchor and px) else None


def update_kr(pool):
    try:
        raw = urllib.request.urlopen(urllib.request.Request(
            "https://finance.naver.com/api/sise/etfItemList.nhn", headers=UA), timeout=15).read()
        items = json.loads(raw.decode("euc-kr", "ignore"))["result"]["etfItemList"]
    except Exception as e:
        print("[etf-live] KR etfItemList 실패:", repr(e)[:80]); return 0
    live = {x.get("itemcode"): x for x in items if x.get("itemcode")}
    n = 0
    for r in pool.get("kr", []):
        x = live.get(r["c"])
        if not x or not x.get("nowVal"):
            continue
        P = x["nowVal"]
        r["px"] = P; r["chg"] = x.get("changeRate")
        if x.get("marketSum"):
            r["cap"] = x["marketSum"]*1e8
        if x.get("amonut"):
            r["tv"] = x["amonut"]*1e6
        if r.get("nav"):
            r["nav"] = x.get("nav") or r["nav"]
        for a, albl in (("r1m", "a1m"), ("r3m", "a3m"), ("r6m", "a6m"), ("r1y", "a1y")):
            if r.get(albl):
                v = _rr(P, r[albl])
                if v is not None:
                    r[a] = v
        if r.get("ma200a"):
            r["v200"] = _rr(P, r["ma200a"])
        if r.get("hi52a"):
            hi = max(r["hi52a"], P)
            r["hi"] = round(P/hi-1, 4)
        n += 1
    return n


def update_us(pool):
    us = pool.get("us", [])
    if not us:
        return 0
    op, crumb = T.yahoo_opener()
    syms = [r["c"] for r in us]
    by = {r["c"]: r for r in us}
    q = {}

    def batch(chunk):
        try:
            u = ("https://query1.finance.yahoo.com/v7/finance/quote?symbols=%s&crumb=%s"
                 % (urllib.parse.quote(",".join(chunk)), urllib.parse.quote(crumb)))
            return (T.jget(u, opener=op, timeout=20).get("quoteResponse", {}) or {}).get("result", []) or []
        except Exception:
            return []
    for res in T.pmap(batch, [syms[i:i+50] for i in range(0, len(syms), 50)], workers=6):
        for x in res:
            q[x.get("symbol")] = x
    n = 0
    for r in us:
        x = q.get(r["c"])
        if not x:
            continue
        # (2026-07-26) 프리/애프터마켓이면 그 실체결가 사용 — 정규장 종가(stale)가 아니라 실시간
        state = x.get("marketState")
        if state in ("PRE", "PREPRE") and x.get("preMarketPrice"):
            P = x["preMarketPrice"]; ch = x.get("preMarketChangePercent")
        elif state in ("POST", "POSTPOST", "CLOSED") and x.get("postMarketPrice"):
            P = x["postMarketPrice"]; ch = x.get("postMarketChangePercent")
        else:
            P = x.get("regularMarketPrice"); ch = x.get("regularMarketChangePercent")
        if not P:
            continue
        r["px"] = P; r["chg"] = ch
        if x.get("netAssets"):
            r["cap"] = x["netAssets"]
        v3 = x.get("averageDailyVolume3Month")
        if v3:
            r["tv"] = round(v3*P)
        if x.get("fiftyTwoWeekChangePercent") is not None:
            r["r1y"] = x["fiftyTwoWeekChangePercent"]/100
        if x.get("fiftyTwoWeekHighChangePercent") is not None:
            r["hi"] = x["fiftyTwoWeekHighChangePercent"]/100
        if x.get("twoHundredDayAverageChangePercent") is not None:
            r["v200"] = x["twoHundredDayAverageChangePercent"]/100
        for a, albl in (("r1m", "a1m"), ("r3m", "a3m"), ("r6m", "a6m")):
            if r.get(albl):
                vv = _rr(P, r[albl])
                if vv is not None:
                    r[a] = vv
        n += 1
    return n


def main(force=False):
    now = datetime.now(KST)
    kr_on, us_on = _kr_session(now), _us_session(now)
    # (2026-07-26) 1분 주기 — KR 은 매분(네이버 1콜, 부담 0).
    #   US 는 5,221종÷50 ≈ 105콜/실행이라 매분이면 Yahoo 차단 위험 → 3분마다만 실행.
    #   (2026-07-20) force=True(관리자 수동 갱신)면 시간·주기 무시하고 양시장 즉시 갱신.
    us_run = us_on and (now.minute % 3 == 0)
    if force:
        kr_on = us_run = True
    if not (kr_on or us_run):
        print("장외/스킵"); return
    pool = T.load_db("etf_pool")
    if not pool or not pool.get("kr"):
        print("etf_pool 없음 — skip"); return
    nk = update_kr(pool) if kr_on else 0
    nu = update_us(pool) if us_run else 0
    _ = force  # (force 는 위 게이트에서만 사용)
    pool["live_at"] = now.strftime("%m-%d %H:%M") + " 장중"
    T.save_db("etf_pool", pool)
    print(f"[etf-live] {pool['live_at']} · KR {nk} · US {nu}")


if __name__ == "__main__":
    main()
