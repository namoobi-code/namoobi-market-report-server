#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""migration.py — 시도별 인구이동(전입·전출·순이동) (2026-08-08 신설 · 매일 08:10 cron).

소스: data.go.kr 행정안전부_지역별 인구이동 현황 (15108093) — 2026-08-08 활용신청 후 실측
      GET apis.data.go.kr/1741000/ppltnDataStus/selectPpltnDataStus
      필수: mvinAdmmCd(전입) · mvtAdmmCd(전출) · srchFrYm · srchToYm(3개월 이내)
      lv=1(시도) · type=json · 2022.10부터 제공

왜 선행지표인가: 사람이 먼저 움직이고 집값이 따라온다. 특정 지역 순유입이 이어지면
   6~18개월 뒤 그 지역 전월세·매매가가 반응하는 패턴이 반복 관찰된다.
   특히 **30대 순이동**은 생애최초 주택수요와 직결돼 총량보다 신호가 선명하다.

제약 (실측):
   · 전입·전출 코드를 **둘 다** 지정해야 한다(전체 조회 와일드카드 없음)
     → 17개 시도 × 16 = 272개 방향쌍을 각각 호출해야 한다.
   · 한 요청당 최대 3개월 → 과거 백필은 3개월 단위로 끊어 돈다.

산출: data/db/migration.json
      {asof, t:[YYYYMM], regions, net/in/out:{지역:[…]}, net30:{…}, flows:{"전출>전입":[…]}}
"""
import json, sys, time, urllib.request
from collections import defaultdict
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "data" / "db" / "migration.json"
KEY = (BASE / "keys" / "data.go.kr.txt").read_text().strip()
API = "https://apis.data.go.kr/1741000/ppltnDataStus/selectPpltnDataStus"

ARG = lambda k, d: (int(sys.argv[sys.argv.index(k) + 1]) if k in sys.argv else d)
MONTHS = 60 if "--full" in sys.argv else ARG("--months", 6)
SLEEP = 0.25

# 시도 코드 — 2026-08-08 실측 확인(강원=51, 전북=52 신 코드)
SIDO = {"11": "서울", "26": "부산", "27": "대구", "28": "인천", "29": "광주", "30": "대전",
        "31": "울산", "36": "세종", "41": "경기", "43": "충북", "44": "충남", "46": "전남",
        "47": "경북", "48": "경남", "50": "제주", "51": "강원", "52": "전북"}
FIRST = "202210"                       # API 제공 시작월


def _back(t, k):
    y, m = int(t[:4]), int(t[4:]) - k
    while m <= 0:
        y -= 1; m += 12
    return f"{y}{m:02d}"


def latest_month():
    """실제 공표된 마지막 월을 찾는다.
    (미공표 월을 창에 넣으면 API 가 INVALID_REQUEST_PARAMETER_ERROR 로 창 전체를 거부한다.
     인구이동은 익월 말경 공표라 현재월·전월이 아직 없을 수 있다.)"""
    cur = datetime.now().strftime("%Y%m")
    for k in range(0, 6):
        t = _back(cur, k)
        if t < FIRST:
            break
        if call("41", "11", t, t):
            return t
        time.sleep(0.3)
    return _back(cur, 2)


def ymlist(n, last):
    out = []
    t = last
    for _ in range(n):
        if t < FIRST:
            break
        out.append(t)
        t = _back(t, 1)
    return out[::-1]


def call(inc, outc, fr, to):
    u = (f"{API}?serviceKey={KEY}&mvinAdmmCd={inc}00000000&mvtAdmmCd={outc}00000000"
         f"&srchFrYm={fr}&srchToYm={to}&lv=1&type=json&numOfRows=100&pageNo=1")
    for k in range(3):
        try:
            d = json.loads(urllib.request.urlopen(u, timeout=30).read())["Response"]
            it = (d.get("items") or {})
            it = it.get("item") if isinstance(it, dict) else None
            if not it:
                return []
            return it if isinstance(it, list) else [it]
        except Exception:
            if k == 2:
                return []
            time.sleep(2 * (k + 1))
    return []


def n(x):
    try:
        return int(str(x).replace(",", ""))
    except Exception:
        return 0


def age30(r):
    """30~39세 남녀 합 — 생애최초 주택수요 연령대."""
    s = 0
    for a in range(30, 40):
        s += n(r.get(f"male{a}AgeNmprCnt")) + n(r.get(f"feml{a}AgeNmprCnt"))
    return s


def main():
    last = latest_month()
    yms = ymlist(MONTHS, last)
    print(f"[mig] 최신 공표월 {last} · 대상 {len(yms)}개월 ({yms[0]}~{yms[-1]})" if yms else "[mig] 대상 월 없음")
    if not yms:
        return
    # 기존 적재분 (증분 갱신)
    flows, flows30 = {}, {}
    try:
        old = json.loads(OUT.read_text(encoding="utf-8"))
        ot = old.get("t") or []
        for k, v in (old.get("flows") or {}).items():
            flows[k] = dict(zip(ot, v))
        for k, v in (old.get("flows30") or {}).items():
            flows30[k] = dict(zip(ot, v))
    except Exception:
        pass

    pairs = [(o, i) for o in SIDO for i in SIDO if o != i]
    calls = 0
    # 3개월 창으로 끊어 호출
    win = [yms[i:i + 3] for i in range(0, len(yms), 3)]
    for wi, w in enumerate(win):
        fr, to = w[0], w[-1]
        got = 0
        for (o, i) in pairs:
            key = f"{SIDO[o]}>{SIDO[i]}"
            if all(m in flows.get(key, {}) for m in w) and "--force" not in sys.argv:
                continue                                     # 이미 있음
            for r in call(i, o, fr, to):
                ym = str(r.get("statsYm") or "")
                if len(ym) != 6:
                    continue
                flows.setdefault(key, {})[ym] = n(r.get("totNmprCnt"))
                flows30.setdefault(key, {})[ym] = age30(r)
                got += 1
            calls += 1
            time.sleep(SLEEP)
        print(f"  [{wi+1}/{len(win)}] {fr}~{to}: {got}건 (누적호출 {calls:,})", flush=True)

    ts = sorted({m for v in flows.values() for m in v})
    if not ts:
        print("[mig] ❌ 데이터 없음 — 저장 생략"); return
    regs = list(SIDO.values())

    def agg(F):
        _in = {r: [0] * len(ts) for r in regs}
        _out = {r: [0] * len(ts) for r in regs}
        for key, mp in F.items():
            o, i = key.split(">")
            for j, t in enumerate(ts):
                v = mp.get(t)
                if v is None:
                    continue
                if i in _in:
                    _in[i][j] += v
                if o in _out:
                    _out[o][j] += v
        net = {r: [_in[r][j] - _out[r][j] for j in range(len(ts))] for r in regs}
        return _in, _out, net

    IN, OUT_, NET = agg(flows)
    _, _, NET30 = agg(flows30)
    # 수도권 파생
    CAP = ["서울", "인천", "경기"]
    for D in (IN, OUT_, NET, NET30):
        D["수도권"] = [sum(D[c][j] for c in CAP) for j in range(len(ts))]
    # 수도권 내부 이동은 상쇄되므로 순이동은 그대로 두되, 전입/전출은 내부분 제외가 정확
    inner = [sum(flows.get(f"{a}>{b}", {}).get(t, 0) for a in CAP for b in CAP if a != b)
             for t in ts]
    IN["수도권"] = [IN["수도권"][j] - inner[j] for j in range(len(ts))]
    OUT_["수도권"] = [OUT_["수도권"][j] - inner[j] for j in range(len(ts))]

    last = ts[-1]
    li = len(ts) - 1
    top = sorted(((k, v.get(last, 0)) for k, v in flows.items()),
                 key=lambda x: -x[1])[:15]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "asof": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "src": "행정안전부 지역별 인구이동 현황 (data.go.kr)",
        "note": "순이동 = 전입 − 전출(시도 간). 2022.10부터 제공 · 시도 내부 이동은 제외",
        "t": ts, "regions": regs + ["수도권"],
        "in": {r: v for r, v in IN.items()}, "out": {r: v for r, v in OUT_.items()},
        "net": NET, "net30": NET30,
        "flows": {k: [v.get(t) for t in ts] for k, v in flows.items()},
        "top_last": [{"k": k, "v": v} for k, v in top],
    }, ensure_ascii=False), encoding="utf-8")

    rank = sorted(((r, NET[r][li]) for r in regs), key=lambda x: -x[1])
    print(f"[mig] ✅ {len(ts)}개월 {ts[0]}~{ts[-1]} · 방향쌍 {len(flows)} · 호출 {calls:,}")
    print(f"[mig]    {last} 순유입 상위: " + ", ".join(f"{r} {v:+,}" for r, v in rank[:3]))
    print(f"[mig]    {last} 순유출 상위: " + ", ".join(f"{r} {v:+,}" for r, v in rank[-3:]))
    print(f"[mig] → {OUT}")


if __name__ == "__main__":
    main()
