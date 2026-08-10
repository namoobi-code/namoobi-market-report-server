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


def quarter_end(d8):
    """공시일 → 그 잠정실적이 속한 분기말(YYYY/MM). earnings_watch.py 와 동일 규칙."""
    y, m = int(d8[:4]), int(d8[4:6])
    if m <= 3:  return f"{y-1}/12"
    if m <= 6:  return f"{y}/03"
    if m <= 9:  return f"{y}/06"
    return f"{y}/09"


def kr_surprise_backfill(ev):
    """(2026-08-09) 과거 45일치 KR 발표에 서프라이즈%를 소급 계산.

    서프라이즈 계산은 2026-08-09 에 붙였기 때문에 그 이전 공시분은 spr 이 비어 있다.
    WISEreport 는 실적이 확정되기 전까지 해당 분기를 (E) 로 계속 들고 있어서(실측: 8월 현재도
    2026/06(E) 유지), 오늘 뜬 스냅샷으로 지난 분기 발표분까지 되짚을 수 있다.
    → 필터가 0건만 반환하던 원인(데이터 커버리지)이 이걸로 해소된다.
    """
    import sqlite3
    db = BASE / "data" / "db" / "kr_consensus.sqlite"
    if not db.exists():
        return 0
    cx = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=15)
    n = 0
    for c, (d8, it) in ev.items():
        # (2026-08-09 수정) 영업익 서프가 이미 있어도 매출 서프가 비었으면 계속 진행한다.
        # 예전엔 spr 존재 시 통째로 건너뛰어 spr_s 가 계산될 기회가 없었다(SK하이닉스 실측).
        need_op = it.get("spr") is None and it.get("op") is not None
        need_s  = it.get("spr_s") is None and it.get("sales") is not None
        if not (need_op or need_s):
            continue
        r = cx.execute("SELECT op,sales FROM snap WHERE code=? AND period=? ORDER BY d DESC LIMIT 1",
                       (c, quarter_end(d8))).fetchone()
        est, sest = (r[0], r[1]) if r else (None, None)
        if need_op and est and abs(est) > 10:           # 컨센 10억원 미만은 비율이 무의미
            it["spr"] = round((it["op"] / est - 1) * 100, 1)
            it["cons_op"] = est
            n += 1
        if need_s and sest and sest > 10:
            it["spr_s"] = round((it["sales"] / sest - 1) * 100, 1)
            it["cons_sales"] = sest
            n += 1
    cx.close()
    return n


def main():
    pool = load(POOL)
    if not pool:
        raise SystemExit("screener_pool.json 없음 — 풀 빌드 후 실행할 것")
    cons = (load(CONS) or {}).get("r", {})
    stat = {}
    kr_ev = latest_events(ERN["kr"])
    bf = kr_surprise_backfill(kr_ev)
    if bf:
        # 되짚은 값은 원본에도 남긴다 — 모달에서도 보여야 하고, 다음 실행 때 재계산하지 않도록
        j = load(ERN["kr"])
        for d8 in j.get("days") or {}:
            for it in j["days"][d8]:
                src = kr_ev.get(it.get("c"))
                if src and src[0] == d8:
                    for k in ("spr", "cons_op", "spr_s", "cons_sales"):
                        if src[1].get(k) is not None:
                            it[k] = src[1][k]
        ERN["kr"].write_text(json.dumps(j, ensure_ascii=False), encoding="utf-8")
    print(f"[join] KR 서프라이즈 소급 계산 {bf}건")
    for mk in ("kr", "us"):
        ev = kr_ev if mk == "kr" else latest_events(ERN[mk])
        n = 0
        for r in pool.get(mk) or []:
            c = r.get("c")
            patch = {}
            if mk == "kr":
                cc = cons.get(c) or {}
                if cc.get("op30") is not None:
                    patch["cr30"] = cc["op30"]          # 비율(0.05 = +5%)
                if cc.get("op90") is not None:
                    patch["cr90"] = cc["op90"]
                # 목표주가 리비전 — 한국의 이익추정 리비전(op30)은 스냅샷 30일이 필요해
                # 당장은 비어 있다. 증권사 목표가 변동은 오늘 바로 쓸 수 있는 대체 신호다.
                if cc.get("tp30") is not None:
                    patch["tprv"] = cc["tp30"]          # % 단위
                    patch["tpn"] = cc.get("tpn"); patch["tpu"] = cc.get("tpu"); patch["tpd"] = cc.get("tpd")
                if cc.get("tp90") is not None:
                    patch["tprv90"] = cc["tp90"]
            d8, it = ev.get(c, (None, None))
            # (2026-08-10) 가이던스 필드는 매 실행마다 **초기화 후 재기록** — 소급 재파싱으로
            # 값이 빠진 경우(예: ±25% 초과 오파싱 제거)에도 풀에 옛 값이 남으면 안 된다.
            for k in ("gapR", "gapE", "gapRp", "gapEp", "gap"):
                r.pop(k, None)
            if it:
                patch["edl"] = d8
                for k in ("r1", "r5", "r20"):
                    if it.get(k) is not None:
                        patch[k] = it[k]
                # (2026-08-10) 가이던스 갭 매출·EPS 분리 — 스크리너 필터가 두 축을 따로 쓴다
                # (gap=병합값은 구버전 호환으로 유지)
                if it.get("g_rev_gap") is not None:
                    patch["gapR"] = it["g_rev_gap"]
                    patch["gapRp"] = it.get("g_rev_per") or it.get("g_per")   # 비교 기간(0q/+1q/0y/+1y)
                if it.get("g_eps_gap") is not None:
                    patch["gapE"] = it["g_eps_gap"]
                    patch["gapEp"] = it.get("g_eps_per") or it.get("g_per")
                g = it.get("g_rev_gap")
                if g is None:
                    g = it.get("g_eps_gap")
                if g is not None:
                    patch["gap"] = g
                # KR 서프라이즈는 발표 이벤트에만 있다(US 는 풀에 이미 있음)
                if mk == "kr":
                    # (2026-08-09) 서프 2종 + YoY/QoQ/마진 상세 — 차트 팝업과 스크리너가 동일 소스를 쓴다
                    for src_k, dst_k in (("spr", "spr"), ("spr_s", "sspr"),
                                         ("sales_yoy", "syoy"), ("op_yoy", "oyoy"), ("ni_yoy", "nyoy"),
                                         ("sales_qoq", "sqoq"), ("op_qoq", "oqoq"), ("ni_qoq", "nqoq"),
                                         ("opm", "opmn"), ("opm_ch", "opmy"),
                                         ("op_qturn", "oqt"), ("ni_qturn", "nqt")):
                        if it.get(src_k) is not None:
                            patch[dst_k] = it[src_k]
            if patch:
                r.update(patch); n += 1
        stat[mk] = n
    pool["ern_join_asof"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    POOL.write_text(json.dumps(pool, ensure_ascii=False), encoding="utf-8")
    tot = {mk: len(pool.get(mk) or []) for mk in ("kr", "us")}
    print(f"[join] KR {stat.get('kr',0)}/{tot['kr']} · US {stat.get('us',0)}/{tot['us']} 종목에 실적·전망 패치")


if __name__ == "__main__":
    main()
