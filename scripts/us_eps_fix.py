#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""us_eps_fix.py — US 실적 라이브의 EPS/컨센/서프 보정 (2026-08-09 신설 · 매일 09:00 cron).

왜
--
earnings_watch_us 는 발표 직후 야후 earningsHistory 를 읽는데, 그 시점에 야후가 아직
이번 분기를 안 올렸으면 **직전 분기 값이 붙는다**(실측 ABNB 2026-08-06 발표 → Q1 0.26/0.30,
서프 −14.1% 로 저장. 실제 Q2 는 1.37/1.25, +9.5%). 캘린더와 차트 팝업이 어긋나는 원인.

무엇을
------
최근 45일 US 발표 항목을 훑어 **발표일 직전 분기(분기말→발표 0~100일)** 의 값으로 다시 맞춘다.
이미 올바른 항목은 건드리지 않고, 바뀐 것만 eps/est/spr/tags 를 갱신한다.
사용: us_eps_fix.py [--days 45]
"""
import http.cookiejar, json, sys, time, urllib.parse, urllib.request
from datetime import datetime, timedelta
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
LIVE = BASE / "data" / "db" / "earnings_live_us.json"
UA = {"User-Agent": "Mozilla/5.0"}
DAYS = int(sys.argv[sys.argv.index("--days") + 1]) if "--days" in sys.argv else 45


def opener():
    cj = http.cookiejar.CookieJar()
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    op.addheaders = list(UA.items())
    try:
        op.open("https://fc.yahoo.com", timeout=8)
    except Exception:
        pass
    return op, op.open("https://query1.finance.yahoo.com/v1/test/getcrumb", timeout=10).read().decode()


def main():
    j = json.loads(LIVE.read_text(encoding="utf-8"))
    cut = (datetime.now() - timedelta(days=DAYS)).strftime("%Y%m%d")
    todo = [(d8, it) for d8 in sorted(j.get("days") or {}) if d8 >= cut for it in j["days"][d8]]
    op, crumb = opener()
    print(f"[epsfix] 대상 {len(todo)}건 (최근 {DAYS}일)", flush=True)
    fixed = same = err = 0
    for d8, it in todo:
        sym = it.get("c")
        if not sym:
            continue
        try:
            u = (f"https://query2.finance.yahoo.com/v10/finance/quoteSummary/{urllib.parse.quote(sym)}"
                 f"?modules=earningsHistory&crumb={urllib.parse.quote(crumb)}")
            eh = ((json.loads(op.open(u, timeout=12).read())["quoteSummary"]["result"][0]
                   .get("earningsHistory") or {}).get("history")) or []
        except Exception:
            err += 1; time.sleep(0.2); continue
        ed = datetime.strptime(d8, "%Y%m%d").date()
        best = None
        for x in eh:                                    # 발표일 직전 분기(0~100일) 중 가장 최근
            q = (x.get("quarter") or {}).get("fmt") or ""
            ea = (x.get("epsActual") or {}).get("raw")
            if not q or ea is None:
                continue
            try:
                gap = (ed - datetime.fromisoformat(q).date()).days
            except Exception:
                continue
            if 0 <= gap <= 100 and (best is None or q > best[0]):
                best = (q, x)
        if not best:
            time.sleep(0.15); continue
        x = best[1]
        ea = (x.get("epsActual") or {}).get("raw")
        ee = (x.get("epsEstimate") or {}).get("raw")
        sp = (x.get("surprisePercent") or {}).get("raw")
        sp = round(sp * 100, 1) if sp is not None else None
        if it.get("eps") == ea and it.get("est") == ee and it.get("spr") == sp:
            same += 1; time.sleep(0.15); continue
        tg = [t for t in (it.get("tags") or []) if "접수" in t or "가이던스" in t]
        if sp is not None:
            if sp >= 10: tg.append(f"어닝비트 +{sp:.0f}%")
            elif sp <= -10: tg.append(f"어닝미스 {sp:.0f}%")
        if ee is not None and ea is not None:
            if ee <= 0 < ea: tg.append("예상밖 흑자")
            elif ea < 0 <= ee: tg.append("예상밖 적자")
        it.update({"eps": ea, "est": ee, "spr": sp, "tags": tg, "qe": best[0]})
        fixed += 1
        if fixed % 50 == 0:
            LIVE.write_text(json.dumps(j, ensure_ascii=False), encoding="utf-8")
            print(f"    보정 {fixed}건…", flush=True)
        time.sleep(0.15)
    j["asof"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    LIVE.write_text(json.dumps(j, ensure_ascii=False), encoding="utf-8")
    print(f"[epsfix] 완료 — 보정 {fixed} · 동일 {same} · 실패 {err}")


if __name__ == "__main__":
    main()
