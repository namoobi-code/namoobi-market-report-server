#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""earnings_8k_watch.py — SEC 8-K 실시간 감시 (2026-08-05 신설 · 워치리스트 한정).

야후 정형 수치(earnings_watch_us)보다 빠른 최초 신호: 8-K 는 발표 수 분 내 EDGAR 접수
(실측: PLTR 마감 6분 뒤 16:06 ET · getcurrent atom 피드에 CIK·접수시각 포함).
전 종목 감시는 소음이 커서, data/watch/us_8k_watchlist.txt 에 적힌 종목만 본다(사용자 요청).

동작: getcurrent 8-K atom(최신 100건, 호출 1회/분) → 워치리스트 CIK 매칭 →
      submissions JSON 으로 Item 2.02(실적) 여부 확인 → earnings_live_us.json 의
      해당 종목에 '📄 8-K(실적) 접수 HH:MM ET' 태그를 붙이거나 새 항목 생성.
      이후 야후 수집기가 EPS 수치를 채우면 태그는 유지된다.
cron: * 5-8 * * 2-6 · * 19-22 * * 1-5 (flock)
"""
import json, re, urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "data" / "db" / "earnings_live_us.json"
WATCH = BASE / "data" / "watch" / "us_8k_watchlist.txt"
CIKMAP = BASE / "data" / "watch" / "cik_map.json"
H = {"User-Agent": "namoobi research namoobi@gmail.com"}
ET = timezone(timedelta(hours=-4))          # 미 동부(서머타임 EDT). 겨울(-5) 오차 1시간은 라벨용이라 허용

def get(u, timeout=20):
    return urllib.request.urlopen(urllib.request.Request(u, headers=H), timeout=timeout).read()

def cik_map():
    """티커→CIK — 주 1회 갱신 캐시."""
    try:
        m = json.loads(CIKMAP.read_text())
        if (datetime.now() - datetime.fromisoformat(m["at"])).days < 7:
            return m["map"]
    except Exception:
        pass
    j = json.loads(get("https://www.sec.gov/files/company_tickers.json"))
    mp = {v["ticker"].upper(): str(v["cik_str"]) for v in j.values()}
    CIKMAP.parent.mkdir(parents=True, exist_ok=True)
    CIKMAP.write_text(json.dumps({"at": datetime.now().isoformat(), "map": mp}))
    return mp

def items_of(cik, accno):
    """해당 접수번호의 8-K Item 목록 (2.02=실적) — 매칭 시에만 1회 호출."""
    try:
        j = json.loads(get(f"https://data.sec.gov/submissions/CIK{int(cik):010d}.json"))
        rec = j["filings"]["recent"]
        for i in range(len(rec["accessionNumber"])):
            if rec["accessionNumber"][i] == accno:
                return rec.get("items", [""] * 9999)[i] or ""
    except Exception:
        pass
    return ""

def main():
    # (2026-08-05) 전 종목 감시로 확장 — 피드 1콜/분이라 종목 수와 무관(사용자 확인).
    #   소음 방지: 비핵심 종목은 Item 2.02(실적) 8-K 만 기록 · 6-K 는 핵심만.
    #   핵심(us_8k_watchlist.txt) = 모든 8-K·6-K 기록 + 스트립 항상 표시(core 플래그).
    core_syms = [s.strip().upper() for s in WATCH.read_text().splitlines()
                 if s.strip() and not s.strip().startswith("#")]
    mp = cik_map()
    pool_syms = []
    try:
        p0 = json.loads((BASE / "data" / "db" / "screener_pool.json").read_text(encoding="utf-8"))
        pool_syms = [r["c"] for r in p0.get("us") or [] if r.get("c")]
    except Exception:
        pass
    core = {mp[s] for s in core_syms if s in mp}
    watch = {mp[s]: s for s in set(pool_syms) | set(core_syms) if s in mp}
    # (2026-08-05) ADR(외국계: TSM·ASML 등)은 8-K 대신 6-K 로 실적을 낸다 → 두 피드 모두 감시
    d = ""
    for ftype in ("8-K", "6-K"):
        d += get(f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type={ftype}"
                 "&company=&dateb=&owner=include&count=100&output=atom").decode("utf-8", "ignore")
    live = {}
    try:
        live = json.loads(OUT.read_text(encoding="utf-8"))
    except Exception:
        pass
    days = live.setdefault("days", {})
    seen_acc = {it.get("acc") for v in days.values() for it in v if it.get("acc")}
    pool_us = {}
    try:
        p = json.loads((BASE / "data" / "db" / "screener_pool.json").read_text(encoding="utf-8"))
        pool_us = {r["c"]: r for r in p.get("us") or []}
    except Exception:
        pass
    new = 0
    for e in re.findall(r"<entry>(.*?)</entry>", d, re.S):
        m = re.search(r"\((\d{7,10})\)", e)                       # (CIK)
        up = re.search(r"<updated>(.*?)</updated>", e)
        ac = re.search(r"AccNo:&lt;/b&gt;\s*([\d-]+)", e)
        if not (m and up and ac):
            continue
        cik = str(int(m.group(1)))
        sym = watch.get(cik)
        if not sym or ac.group(1) in seen_acc:
            continue
        ts = datetime.fromisoformat(up.group(1))
        et = ts.astimezone(ET)
        d8 = et.strftime("%Y%m%d")
        ft = "6-K" if "6-K" in (re.search(r"<title>([^<]*)", e) or [None, ""])[1] else "8-K"
        is_core = cik in core
        if ft == "6-K" and not is_core:
            continue                                   # 전 종목 6-K 는 수시보고 소음 — 핵심만
        its = items_of(cik, ac.group(1)) if ft == "8-K" else ""
        is_ern = "2.02" in its
        if ft == "8-K" and not is_core and not is_ern:
            continue                                   # 비핵심은 실적(2.02) 8-K 만 기록
        tag = f"📄 {ft}{'(실적)' if is_ern else ''} 접수 {et.strftime('%H:%M')}ET"
        lst = days.setdefault(d8, [])
        cur = next((z for z in lst if z["c"] == sym), None)
        if cur:
            if not any("K" in t and "접수" in t for t in cur.get("tags") or []):
                cur.setdefault("tags", []).insert(0, tag)
                cur["acc"] = ac.group(1); cur["cik"] = cik
                if is_core: cur["core"] = 1
                new += 1
        else:
            r = pool_us.get(sym) or {}
            it2 = {"c": sym, "n": r.get("kn") or r.get("n") or sym, "cap": r.get("cap"),
                   "eps": None, "est": None, "spr": None, "tags": [tag],
                   "acc": ac.group(1), "cik": cik, "t": datetime.now().strftime("%H:%M")}
            if is_core: it2["core"] = 1
            lst.append(it2)
            new += 1
        print(f"  📄 {sym} 8-K {its or 'items미상'} {et.strftime('%m/%d %H:%M')}ET acc={ac.group(1)}")
    if new:
        live["asof"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        OUT.write_text(json.dumps(live, ensure_ascii=False), encoding="utf-8")
    print(f"[8k] 워치 {len(watch)}종 · 신규 {new}건")

if __name__ == "__main__":
    main()
