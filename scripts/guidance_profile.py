#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""guidance_profile.py — **종목별 가이던스 프로필** (2026-08-21 신설).

무엇을 푸는가
-------------
8-K 보도자료는 회사마다 표기가 제각각이라, 같은 파서 규칙으로도 어떤 회사는 잡히고
어떤 회사는 안 잡힌다. 그런데 **한 회사는 매 분기 거의 같은 형식으로 낸다** —
같은 지표를, 같은 기간 단위로, 같은 회계 기준으로, 비슷한 자릿수로.
그 규칙성을 종목별로 축적해 두면 다음 발표를 파싱할 때 판단 근거로 쓸 수 있다.

무엇을 근거로 삼는가
--------------------
Benzinga 종목 캐시(data/cache/bz/*.json)에는 2022년부터의 가이던스 레코드가 들어 있다
(1,794종목 · 종목당 최대 20건). 이 레코드는 사람이 정리한 것이라 우리 파서와 독립이며,
period(FY/Q)·eps_type(Adj/GAAP)·revenue_type·currency·값 범위가 모두 들어 있다.
즉 **"이 회사는 무엇을 어떤 기준으로 내는가"의 정답지**다.

산출물: data/db/guidance_profile.json
  {"asof": ..., "sym": {SYM: {
      "n": 레코드수, "first": "2022-10", "last": "2026-07",
      "per":   {"FY": n, "Q": n},          # 제시 기간 분포
      "has":   {"eps": n, "rev": n},       # 지표별 제시 횟수
      "basis": {"eps": "Adj"|"GAAP", "rev": ...},   # 최빈 회계 기준
      "cur":   "USD"|"CAD"|...,            # 보고 통화(컨센과 다르면 갭이 왜곡된다)
      "scale": {"rev": [최소, 최대], "eps": [최소, 최대]},   # 과거 값의 범위
      "gr":    true|false                  # 금액 없이 성장률로만 말하는 습관
  }}}

어디에 쓰는가
-------------
① **단위 미표기 구제** — 표에서 "Revenue $1,178" 처럼 단위가 없으면 자릿수를 확정할 수
   없어 기각해 왔다(실측 22건). 이 회사의 과거 매출 규모가 1.1B 대임을 알면
   그 값이 백만 달러 단위임이 **추정이 아니라 산술로** 정해진다.
② 회계 기준 대조 — 늘 Adj 로 내는 회사에서 GAAP 값만 잡혔다면 표기를 놓친 것이다.
③ 통화 — CAD 로 내는 회사(GFL·ATS 등)를 표시 단계에서 구분한다.
④ 기간 힌트 — 기존 guidance_tendency 의 fy/q 비율과 같은 역할(더 원천에 가깝다).

cron: 매일 09:45 (guidance_bz 09:10 · guidance_history 09:40 뒤). 네트워크 호출 없음.
"""
import json
import collections
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
BZC = BASE / "data" / "cache" / "bz"
OUT = BASE / "data" / "db" / "guidance_profile.json"


def _num(v):
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if x else None


def build():
    prof = {}
    for p in sorted(BZC.glob("*.json")):
        sym = p.stem.upper()
        try:
            rows = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(rows, list) or not rows:
            continue
        per = collections.Counter()
        has = collections.Counter()
        bas = {"eps": collections.Counter(), "rev": collections.Counter()}
        cur = collections.Counter()
        rng = {"eps": [], "rev": []}
        gr = 0
        dates = []
        for r in rows:
            if not isinstance(r, dict):
                continue
            d = str(r.get("date") or "")
            if d:
                dates.append(d[:7])
            pd = str(r.get("period") or "").upper()
            per["FY" if pd.startswith("FY") else ("Q" if pd.startswith("Q") else "?")] += 1
            cur[str(r.get("currency") or "USD").upper()] += 1
            for mk, pre in (("eps", "eps_guidance"), ("rev", "revenue_guidance")):
                lo, hi = _num(r.get(pre + "_min")), _num(r.get(pre + "_max"))
                if lo is None and hi is None:
                    continue
                has[mk] += 1
                t = str(r.get(("eps_type" if mk == "eps" else "revenue_type")) or "").strip()
                if t:
                    bas[mk][t] += 1
                for v in (lo, hi):
                    if v is not None:
                        rng[mk].append(v)
            # 금액 없이 성장률로만 말하는 습관 — notes 가 'up by N%' 로만 서술한다
            nt = str(r.get("notes") or "")
            if "%" in nt and "$" not in nt:
                gr += 1
        n = sum(per.values())
        if not n:
            continue
        e = {"n": n,
             "first": min(dates) if dates else None,
             "last": max(dates) if dates else None,
             "per": {k: v for k, v in per.items() if v and k != "?"},
             "has": dict(has),
             "basis": {k: (c.most_common(1)[0][0] if c else None) for k, c in bas.items()},
             "cur": cur.most_common(1)[0][0] if cur else "USD",
             "scale": {k: [min(v), max(v)] for k, v in rng.items() if v},
             "gr": gr >= max(2, n // 3)}
        prof[sym] = e
    return prof


def main():
    prof = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT.with_suffix(".json.tmp")
    tmp.write_text(json.dumps({"asof": datetime.now().strftime("%Y-%m-%d %H:%M"),
                               "sym": prof}, ensure_ascii=False), encoding="utf-8")
    tmp.replace(OUT)
    nb = sum(1 for e in prof.values() if e["scale"].get("rev"))
    ne = sum(1 for e in prof.values() if e["scale"].get("eps"))
    nc = sum(1 for e in prof.values() if e["cur"] != "USD")
    ng = sum(1 for e in prof.values() if e["gr"])
    print(f"[prof] {len(prof)}종목 · 매출규모 {nb} · EPS규모 {ne} · 비USD {nc} · 성장률형 {ng}")


if __name__ == "__main__":
    main()
