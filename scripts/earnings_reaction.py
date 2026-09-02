#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""earnings_reaction.py — 실적발표 후 주가 반응·PEAD 계산 (2026-08-09 신설 · 매일 08:10 cron).

무엇을 재나
-----------
  r1  발표 후 첫 거래일 등락률   → '시장이 실제로 어떻게 받아들였나'
  r5  발표 후 5거래일 수익률
  r20 발표 후 20거래일 수익률    → PEAD(발표후 표류) 구간

왜 필요한가
-----------
서프라이즈%(실적 vs 컨센)와 주가 반응은 자주 어긋난다. 샌디스크처럼 **EPS 는 비트인데
가이던스가 나빠 하락**하는 경우가 대표적이다. 두 숫자를 나란히 놓아야
"실적은 좋은데 왜 빠졌나"를 즉시 알 수 있고, 스크리너에서 그런 종목만 골라낼 수 있다.

PEAD(Post-Earnings-Announcement Drift): 서프라이즈 방향으로 주가가 수 주간 계속 흐르는
현상. 발표 당일 반응만으로 끝나지 않으므로 r5·r20 이 실제 매매 판단에 쓰인다.

입력  data/db/earnings_live.json (KR · DART 잠정) · earnings_live_us.json (US · Yahoo)
출력  같은 파일의 각 항목에 r1·r5·r20 (%) 추가 — 이미 계산된 건 건너뛴다.
사용  earnings_reaction.py [--days N]   기본 45일치 전부 재확인
"""
import json, sys, time, urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
KR = BASE / "data" / "db" / "earnings_live.json"
US = BASE / "data" / "db" / "earnings_live_us.json"
UA = {"User-Agent": "Mozilla/5.0"}
DAYS = int(sys.argv[sys.argv.index("--days") + 1]) if "--days" in sys.argv else 45


def get(u, timeout=20):
    return urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=timeout).read()


def kr_closes(code, d8):
    """네이버 일봉 → [(YYYYMMDD, 종가)] 발표일 전후. 상장폐지·거래정지면 빈 리스트."""
    s = (datetime.strptime(d8, "%Y%m%d") - timedelta(days=10)).strftime("%Y%m%d")
    e = (datetime.strptime(d8, "%Y%m%d") + timedelta(days=45)).strftime("%Y%m%d")
    try:
        txt = get(f"https://api.finance.naver.com/siseJson.naver?symbol={code}"
                  f"&requestType=1&startTime={s}&endTime={e}&timeframe=day").decode("utf-8", "ignore")
    except Exception:
        return []
    out = []
    for row in txt.replace("'", '"').split("\n"):
        row = row.strip().rstrip(",")
        if not row.startswith("[") or "날짜" in row:
            continue
        try:
            a = json.loads(row)
            out.append((str(a[0]), float(a[4])))
        except Exception:
            continue
    return sorted(out)


def us_closes(sym, d8, p2=None):
    """Yahoo 일봉 → [(YYYYMMDD, 종가)]. p2(epoch) 를 주면 그 시각까지."""
    p1 = int((datetime.strptime(d8, "%Y%m%d") - timedelta(days=10)).timestamp())
    p2 = p2 or int((datetime.strptime(d8, "%Y%m%d") + timedelta(days=45)).timestamp())
    try:
        j = json.loads(get(f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}"
                           f"?interval=1d&period1={p1}&period2={p2}"))
        r = (j.get("chart", {}).get("result") or [None])[0]
        ts = r["timestamp"]; cl = r["indicators"]["quote"][0]["close"]
    except Exception:
        return []
    return sorted((datetime.fromtimestamp(t, timezone.utc).strftime("%Y%m%d"), c)
                  for t, c in zip(ts, cl) if c is not None)


_CAL = {}   # 거래일 달력 캐시 {"us": [YYYYMMDD…]}


def us_calendar():
    """미국 거래일 달력 — SPY 일봉 날짜(최근 90일). 실패하면 None(위치 기반 폴백).

    (2026-09-02 실측) Yahoo v8 chart 가 종목별로 **중간 일봉을 무작위로 빠뜨린다**
    (ANF·SFL 8/26 발표건: 8/28 봉 누락 → after[2]=8/31 이 D+3 으로 잘못 계산되고
    D+5 는 아예 안 채워짐. 같은 날 발표한 CRM 은 봉이 다 있어 D+5 까지 채워져
    '같은 날인데 종목마다 D+n 이 다른' 표가 됐다). 재요청하면 있기도 하다.
    → 위치(after[i]) 대신 **달력 기준 D+n 날짜의 종가**를 찾고, 그 날짜 봉이 없으면
    그 칸만 비워 두고(다음 실행에서 재시도) 다른 칸은 정확히 채운다.
    """
    if "us" in _CAL:
        return _CAL["us"]
    cal = None
    try:
        cal = [d for d, _ in us_closes("SPY", (datetime.now() - timedelta(days=80)).strftime("%Y%m%d"),
                                       p2=int(time.time()) + 86400)]
        cal = sorted(set(cal)) or None
    except Exception:
        cal = None
    _CAL["us"] = cal
    return cal


def react(closes, d8, cal=None):
    """발표일(d8) 기준 반응률.

    기준가 = 발표일 **이전 마지막** 종가(발표 전 마지막 시세). 장 마감 후·개장 전 발표가
    대부분이라 발표 당일 종가를 기준으로 삼으면 반응이 통째로 잘려 나간다.
    cal(거래일 달력)이 있으면 D+n 을 달력 날짜로 잡아 종가를 찾는다(봉 누락 내성).
    """
    if not closes:
        return {}
    base = None
    for d, c in closes:
        if d < d8:
            base = c
        else:
            break
    after = [(d, c) for d, c in closes if d >= d8]
    if base is None or not after or base <= 0:
        return {}
    out = {}
    horizons = (("r1", 0), ("r3", 2), ("r5", 4), ("r20", 19))   # (2026-09-02) D+3 추가(사용자)
    cal_after = [d for d in (cal or []) if d >= d8] if cal else None
    if cal_after and cal_after[0] <= after[0][0]:
        bymap = dict(after)
        for lab, i in horizons:
            if len(cal_after) > i and cal_after[i] in bymap:
                out[lab] = round((bymap[cal_after[i]] / base - 1) * 100, 2)
        return out
    for lab, i in horizons:
        if len(after) > i:
            out[lab] = round((after[i][1] / base - 1) * 100, 2)
    return out


def run(path, closes_fn, sym_of, cal=None):
    if not path.exists():
        print(f"[react] {path.name} 없음 — 건너뜀")
        return
    j = json.loads(path.read_text(encoding="utf-8"))
    days = j.get("days") or {}
    cut = (datetime.now() - timedelta(days=DAYS)).strftime("%Y%m%d")
    n = skip = 0
    for d8 in sorted(days):
        if d8 < cut:
            continue
        for it in days[d8]:
            # r20 까지 다 찬 항목은 재계산 불필요. 아직 20일이 안 지났으면 매번 갱신한다.
            # (2026-09-02) r3 신설 — 기존 레코드 백필 위해 r3 없으면 재계산
            if it.get("r20") is not None and it.get("r3") is not None:
                skip += 1
                continue
            cl = closes_fn(sym_of(it), d8)
            # (2026-09-02 실측) 같은 종목도 요청 구간(period2)에 따라 빠지는 봉이 다르다
            # (ANF: p2=발표+45일 이면 8/28 누락, p2=지금 이면 있음). 달력상 있어야 할 날이
            # 비면 구간을 바꿔 한 번 더 받아 합친다.
            if cal and cl and closes_fn is us_closes:
                have = {d for d, _ in cl}
                need = [d for d in cal if d8 <= d <= cl[-1][0]]
                if any(d not in have for d in need):
                    cl2 = us_closes(sym_of(it), d8, p2=int(time.time()) + 86400)
                    if cl2:
                        cl = sorted(dict(cl + cl2).items())
            r = react(cl, d8, cal)
            if r:
                it.update(r); n += 1
            # (2026-08-09) 200건마다 중간 저장 — US 는 한 번에 2,500건이라 끝에서만 쓰면
            # 중단 시 수십 분치 작업이 통째로 날아간다.
            if n and n % 200 == 0:
                j["react_asof"] = datetime.now().strftime("%Y-%m-%d %H:%M")
                path.write_text(json.dumps(j, ensure_ascii=False), encoding="utf-8")
                print(f"    💾 중간 저장 {n}건", flush=True)
            time.sleep(0.12)
    j["react_asof"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    path.write_text(json.dumps(j, ensure_ascii=False), encoding="utf-8")
    print(f"[react] {path.name}: 갱신 {n}건 · 완료분 건너뜀 {skip}건")


if __name__ == "__main__":
    run(KR, kr_closes, lambda it: it.get("c"))
    run(US, us_closes, lambda it: it.get("c"), us_calendar())
