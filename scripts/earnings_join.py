#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""earnings_join.py — 실적·전망·주가반응을 스크리너 풀에 합치기 (2026-08-09 신설).

세 파이프라인이 각자 다른 파일에 결과를 쌓는다.
    screener_pool.json     종목 마스터(스크리너가 읽는 정본)
    earnings_live{,_us}.json  발표 결과 + 가이던스 갭 + 주가반응(r1/r5/r20)
    kr_consensus.json      한국 분기 컨센서스와 30일 리비전
이 스크립트가 뒤 두 개를 풀에 **패치**해, 스크리너에서 "그런 일이 있었던 종목"을
전체 필터로 걸러낼 수 있게 만든다.

풀에 붙는 필드
--------------
  spr    최근 실적 서프라이즈%   (US=EPS 서프 · KR=영업이익 컨센 대비)
  sprb   최근 4분기 중 비트 횟수 (US만 · Yahoo earningsHistory)
  cr30   컨센서스 30일 리비전%   (US=EPS추정 · KR=영업이익 추정)
  gap    가이던스 vs 컨센 갭%    (US만 · 8-K 보도자료 파싱)
  r1/r5/r20  발표 후 1·5·20거래일 수익률(%)
  edl    마지막 실적발표일(YYYYMMDD)

US 의 spr·sprb·cr30 은 screener_pool.py 가 Yahoo 에서 직접 받아 이미 들어 있다.
여기서는 **발표 이벤트에서만 알 수 있는 값**(가이던스 갭·주가반응)과 KR 전량을 채운다.
사용: earnings_join.py
"""
import json
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
POOL = BASE / "data" / "db" / "screener_pool.json"
CONS = BASE / "data" / "db" / "kr_consensus.json"
ERN = {"kr": BASE / "data" / "db" / "earnings_live.json",
       "us": BASE / "data" / "db" / "earnings_live_us.json"}


def load(p, d=None):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return d if d is not None else {}


def latest_events(path):
    """종목별 **가장 최근** 발표 이벤트 1건 → {code: (d8, item)}."""
    j = load(path)
    out = {}
    for d8 in sorted(j.get("days") or {}):
        for it in j["days"][d8]:
            c = it.get("c")
            if c:
                out[c] = (d8, it)          # 날짜 오름차순이므로 뒤가 최신
    return out


def main():
    pool = load(POOL)
    if not pool:
        raise SystemExit("screener_pool.json 없음 — 풀 빌드 후 실행할 것")
    cons = (load(CONS) or {}).get("r", {})
    stat = {}
    for mk in ("kr", "us"):
        ev = latest_events(ERN[mk])
        n = 0
        for r in pool.get(mk) or []:
            c = r.get("c")
            patch = {}
            if mk == "kr":
                cc = cons.get(c) or {}
                if cc.get("op30") is not None:
                    patch["cr30"] = cc["op30"]          # 비율(0.05 = +5%)
            d8, it = ev.get(c, (None, None))
            if it:
                patch["edl"] = d8
                for k in ("r1", "r5", "r20"):
                    if it.get(k) is not None:
                        patch[k] = it[k]
                g = it.get("g_rev_gap")
                if g is None:
                    g = it.get("g_eps_gap")
                if g is not None:
                    patch["gap"] = g
                # KR 서프라이즈는 발표 이벤트에만 있다(US 는 풀에 이미 있음)
                if mk == "kr" and it.get("spr") is not None:
                    patch["spr"] = it["spr"]
            if patch:
                r.update(patch); n += 1
        stat[mk] = n
    pool["ern_join_asof"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    POOL.write_text(json.dumps(pool, ensure_ascii=False), encoding="utf-8")
    tot = {mk: len(pool.get(mk) or []) for mk in ("kr", "us")}
    print(f"[join] KR {stat.get('kr',0)}/{tot['kr']} · US {stat.get('us',0)}/{tot['us']} 종목에 실적·전망 패치")


if __name__ == "__main__":
    main()
