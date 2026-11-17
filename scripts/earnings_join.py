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
import sys as _sys
_sys.path.insert(0, str(Path(__file__).resolve().parent))
from pool_merge import save_pool_merged
# (2026-08-10) 이 스크립트가 책임지는 필드만 병합 저장 — 다른 수집기 결과를 덮지 않는다
JOIN_FIELDS = ("nig0","nig1","nirev90","nirev30","niacc","ni_lbl","divfcf","divfcf_src","fcfy_kr","dpsg","dps_e","cr30","cr90","tprv","tprv90","tpn","tpu","tpd","qup","yup","opm_fy0","opm_fy1","mexp","fy_lbl","edl","r1","r5","r20","gap","gapR","gapE","gapRp","gapEp","pgapR","pgapE","spr","sspr","syoy","oyoy","nyoy","sqoq","oqoq","nqoq","opmn","opmy","oqt","nqt")

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
    try: FQ = {k: v for k, v in (json.loads((CONS.parent / "fin_quality.json").read_text(encoding="utf-8")).get("rows") or {}).items() if v and not v.get("none")}
    except Exception: FQ = {}
    try: DPSH = json.loads((CONS.parent / "dps_hist.json").read_text(encoding="utf-8")).get("d") or {}
    except Exception: DPSH = {}
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
                # (2026-09-02) 전망 전구간 증가 플래그 — 모든 미래(E) 분기 YoY / 연간 전년比 양수
                for k in ("qup", "yup"):
                    if cc.get(k) is not None:
                        patch[k] = cc[k]
                # (2026-10-17) 내년 영업이익률 개선 전망 — 하나증권 기사 기준. FY(E) 가장 이른 두 해 = 올해·내년.
                fy = cc.get("fy") or {}
                ks = sorted(fy)
                if len(ks) >= 2:
                    m0 = fy[ks[0]]["op"] / fy[ks[0]]["s"] * 100; m1 = fy[ks[1]]["op"] / fy[ks[1]]["s"] * 100
                    patch["opm_fy0"] = round(m0, 2); patch["opm_fy1"] = round(m1, 2); patch["mexp"] = round(m1 - m0, 2); patch["fy_lbl"] = f"{ks[0][2:]}→{ks[1][2:]}"
                # (2026-11-17 메리츠 '퀄리티' 선별 — 매경ECONOMY 11.11) 순이익 컨센: 올해(E)·내년(E) 증가율(%), 내년 순이익 90/30일 리비전(%), 가속(%p=하나증권 조건)
                nf = cc.get("nfy") or {}
                def _g(a, b): return round((a - b) / abs(b) * 100, 1) if (a is not None and b is not None and abs(b) >= 1) else None
                if nf:
                    patch["nig0"] = _g(nf.get("ni0"), nf.get("nip")); patch["nig1"] = _g(nf.get("ni1"), nf.get("ni0"))
                    for lab, k in (("nirev90", "ni1_90"), ("nirev30", "ni1_30")):
                        pv = nf.get(k)
                        patch[lab] = round((nf["ni1"] / pv - 1) * 100, 1) if (pv and pv > 0 and nf.get("ni1") is not None) else None
                    if patch["nig0"] is not None and patch["nig1"] is not None: patch["niacc"] = round(patch["nig1"] - patch["nig0"], 1)
                    patch["ni_lbl"] = f"{nf['y0'][2:]}→{nf['y1'][2:]}"
                # 내년 DPS 증가율(컨센, %) — 메리츠 ② '배당 증가'. 기사 기준은 전망치라 과거 연속증가(dinc)와 다르다(실측: 기사 15종 중 dinc≥1 은 5종뿐)
                if nf.get("dps1") is not None and nf.get("dps0"):
                    patch["dpsg"] = round((nf["dps1"] / nf["dps0"] - 1) * 100, 1); patch["dps_e"] = f"{nf.get('dpsp')}→{nf['dps0']}→{nf['dps1']}"
                # 배당 ÷ FCF (%) — 메리츠 ② "배당액이 잉여현금흐름의 50% 이하". 비금융=DART 배당금의 지급 ÷ (영업현금흐름−유형자산 취득), 금융사=배당성향(순이익 기준, 기사 주석)
                q = FQ.get(c) or {}
                # 1순위 = 내년(E) 컨센: 배당총액(순이익×배당성향) ÷ FCF. 없으면 DART 최근 사업연도 실적(아래)
                _fe = None
                if not r.get("isfin") and nf.get("fcf1") is not None and nf.get("po1") is not None and nf.get("ni1") is not None:
                    _dt = nf["ni1"] * nf["po1"] / 100
                    _fe = round(_dt / nf["fcf1"] * 100, 1) if nf["fcf1"] > 0 else (999.0 if _dt > 0 else 0.0)
                if r.get("isfin") and nf.get("po1") is not None:
                    patch["divfcf"] = round(nf["po1"], 1); patch["divfcf_src"] = "niE"
                elif _fe is not None:
                    patch["divfcf"] = _fe; patch["divfcf_src"] = "fcfE"
                    if q.get("fcf") is not None and r.get("cap"): patch["fcfy_kr"] = round(q["fcf"] / r["cap"], 4)
                elif r.get("isfin"):
                    if r.get("payout") is not None: patch["divfcf"] = round(r["payout"] * 100, 1); patch["divfcf_src"] = "ni"
                elif q.get("fcf") is not None:
                    if r.get("cap"): patch["fcfy_kr"] = round(q["fcf"] / r["cap"], 4)
                    _dv = q.get("div")
                    if _dv is None:      # 현금흐름표 계정명이 표준이 아닌 회사(420종 중 61종) — 최근 확정 DPS × 주식수(시총÷주가) 로 대체
                        try:
                            _y = (DPSH.get(c) or {}).get("y") or {}
                            if _y and r.get("cap") and r.get("px"): _dv = float(_y[max(_y)]) * r["cap"] / r["px"]
                        except Exception: _dv = None
                    if _dv is not None:
                        q = dict(q); q["div"] = _dv
                        patch["divfcf"] = round(q["div"] / q["fcf"] * 100, 1) if q["fcf"] > 0 else (999.0 if q["div"] > 0 else 0.0); patch["divfcf_src"] = "fcf"
            else:
                # US: 내년 마진 개선 프록시 = EPS 컨센 성장 − 매출 컨센 성장 (%p). 야후가 영업이익 전망을 안 주므로 근사.
                try:
                    if r.get("ey0") and r.get("ey1") and r.get("ry0") and r.get("ry1") and r["ey0"] > 0 and r["ry0"] > 0:
                        patch["mexp"] = round(((r["ey1"] / r["ey0"] - 1) - (r["ry1"] / r["ry0"] - 1)) * 100, 2)
                except Exception:
                    pass
            d8, it = ev.get(c, (None, None))
            # (2026-08-10) 가이던스 필드는 매 실행마다 **초기화 후 재기록** — 소급 재파싱으로
            # 값이 빠진 경우(예: ±25% 초과 오파싱 제거)에도 풀에 옛 값이 남으면 안 된다.
            for k in ("gapR", "gapE", "gapRp", "gapEp", "gap", "pgapR", "pgapE"):
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
                # (2026-08-10) 포털 갭 — **검증 전용**. 우리 파싱값(gapR/gapE) 옆에 나란히 보여
                # 파싱이 맞는지 눈으로 대조하기 위한 것이며, 비트/미스 판정에는 절대 쓰지 않는다.
                if it.get("g_rev_gap_p") is not None:
                    patch["pgapR"] = it["g_rev_gap_p"]
                if it.get("g_eps_gap_p") is not None:
                    patch["pgapE"] = it["g_eps_gap_p"]
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
    save_pool_merged(pool, JOIN_FIELDS, mkts=("kr","us"), extra_meta=("ern_join_asof",))
    tot = {mk: len(pool.get(mk) or []) for mk in ("kr", "us")}
    print(f"[join] KR {stat.get('kr',0)}/{tot['kr']} · US {stat.get('us',0)}/{tot['us']} 종목에 실적·전망 패치")


if __name__ == "__main__":
    main()
