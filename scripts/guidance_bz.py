#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""guidance_bz.py — Benzinga 가이던스 **검증용** 수집 (저속·순차) · 2026-08-10 신설.

왜 Benzinga 인가
----------------
무료 종목 페이지 HTML 안에 구조화된 가이던스 JSON 이 들어 있고, 필드가 우리에게 딱 맞다:
  period("FY"/"Q1".."Q4") · period_year · eps_type("Adj"/"GAAP") · 이전 가이던스
우리 8-K 파서가 가장 자주 틀리는 두 가지(연간↔분기, GAAP↔조정)를 **데이터가 직접** 알려주므로
대조에 최적이다. MarketBeat 는 기간·기준 표기가 없어 컨센 역매칭에 의존해야 했다.

**저속이 필수다** — 동시 20건을 던졌다가 HTTP 429 로 서버 IP 가 한 시간 넘게 막혔다.
그래서 이 수집기는 ①순차 ②요청 간 5초 ③429 를 만나면 지수 백오프 후 그날치 중단
④이미 받은 발표는 캐시로 건너뛰기 로 동작한다. 하루에 다 못 받아도 다음 날 이어서 채운다.

저장(검증 전용 · 판정에는 쓰지 않는다)
  g_rev_p / g_rev_gap_p / g_rev_per_p · g_eps_p / g_eps_gap_p / g_eps_per_p
  g_bz_period(FY/Q1..) · g_bz_type(Adj/GAAP) · g_bz_date

사용: guidance_bz.py [--days 45] [--limit N] [--gap 5]
cron: 매일 09:10 (백필·join 뒤). 오래 걸리므로 flock 으로 중복 실행을 막는다.
"""
import json, re, sys, time, urllib.request
from datetime import datetime, timedelta
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
POOL = BASE / "data" / "db" / "screener_pool.json"
LIVE = BASE / "data" / "db" / "earnings_live_us.json"
# 받아온 레코드를 종목별로 저장한다 — 판정 규칙을 바꿀 때 4.9시간을 다시 쓰지 않기 위함.
BZC = BASE / "data" / "cache" / "bz"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"}
ARG = lambda k, d: (int(sys.argv[sys.argv.index(k) + 1]) if k in sys.argv else d)
DAYS, LIMIT, GAP = ARG("--days", 45), ARG("--limit", 0), ARG("--gap", 5)
# --offline = 캐시에 있는 것만 쓰고 **네트워크를 아예 안 탄다**.
# 판정 규칙을 고친 뒤 전건 재판정할 때 쓴다(429 걱정 없이 몇 분이면 끝난다).
OFFLINE = "--offline" in sys.argv
# (2026-08-14) --force = **이미 g_bz_date 가 있는 종목도 재처리**한다.
# 기간 매칭 로직(want_fy 로 같은 기간 레코드 고르기)을 세션 중간에 고쳤는데,
# "이미 받은 건 건너뛴다"(아래 todo 필터) 때문에 고치기 전에 처리된 종목은
# 영영 재계산되지 않아 옛날(버그 있던) 비교값이 화면에 그대로 남아 있었다
# (실측 VRNS: 캐시엔 분기 레코드가 멀쩡히 있는데 저장된 g_rev_p 는 옛 로직이 고른
# 연간값 737 — 재수집이 아니라 **재계산**만 하면 되는 문제였다).
# 캐시가 이미 있으니(fetch 의 use_cache) 네트워크 호출 없이 몇 초면 끝난다.
FORCE = "--force" in sys.argv
P_FIELDS = ("g_rev_p", "g_rev_gap_p", "g_rev_per_p", "g_eps_p", "g_eps_gap_p", "g_eps_per_p",
            "g_rev_bzp", "g_eps_bzp",
            "g_bz_period", "g_bz_type", "g_bz_date")
NUM = lambda v: (float(v) if v not in (None, "", "0.000") else None)


def fetch(sym, use_cache=True):
    """→ (레코드 리스트, 429 여부). 레코드는 최신순."""
    BZC.mkdir(parents=True, exist_ok=True)
    cp = BZC / f"{sym.upper()}.json"
    if use_cache and cp.exists():
        try:
            return json.loads(cp.read_text(encoding="utf-8")), False
        except Exception:
            pass
    if OFFLINE:
        return [], False
    try:
        h = urllib.request.urlopen(urllib.request.Request(
            f"https://www.benzinga.com/quote/{sym.upper()}/earnings-forecasts",
            headers=UA), timeout=25).read().decode("utf-8", "ignore")
    except Exception as e:
        return [], ("429" in str(e))
    out = []
    for m in re.finditer(r"eps_guidance_est", h):
        a, b = h.rfind("{", 0, m.start()), h.find("}", m.end())
        if a < 0 or b < 0:
            continue
        try:
            d = json.loads(h[a:b + 1].replace('\\"', '"'))
        except Exception:
            continue
        if "period_year" not in d:
            continue
        out.append(d)
    out.sort(key=lambda d: str(d.get("date") or ""), reverse=True)
    # (2026-08-14) **레코드가 있을 때만** 저장한다. 빈 결과를 캐시하면 429·일시 오류로
    # 못 받은 것이 "이 종목은 가이던스 없음"으로 굳어 재시도가 영영 안 된다
    # (실측: 캐시 2,812개 중 1,199개가 빈 파일 — 대조 가능분이 절반으로 줄었다).
    # 빈 결과는 '없다'가 아니라 '못 받았다'다 — SEC FETCH_FAIL 과 같은 원칙.
    if out:
        try:
            cp.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass
    return out, False


def main():
    pool = {r.get("c"): r for r in (json.loads(POOL.read_text(encoding="utf-8")).get("us") or [])
            if r.get("c")}
    live = json.loads(LIVE.read_text(encoding="utf-8"))
    cut = (datetime.now() - timedelta(days=DAYS)).strftime("%Y%m%d")
    todo = [(d8, it) for d8 in sorted(live.get("days") or {}, reverse=True) if d8 >= cut
            for it in live["days"][d8]
            if it.get("c") in pool and (FORCE or it.get("g_bz_date") is None)]  # 이미 받은 건 건너뛴다(--force 면 재계산)
    if LIMIT:
        todo = todo[:LIMIT]
    print(f"[bz] 대상 {len(todo)}건 (최근 {DAYS}일 · 간격 {GAP}초 · 예상 {len(todo)*GAP//60}분)", flush=True)
    got = same = diff = 0
    for n, (d8, it) in enumerate(todo):
        rows, blocked = fetch(it["c"])
        if blocked:
            print(f"[bz] 429 — {n}건까지 받고 중단(다음 실행에서 이어받는다)", flush=True)
            break
        if not OFFLINE:
            time.sleep(GAP)
        if FORCE:
            for k in P_FIELDS:                # 재계산 — 옛 비교값을 반드시 지우고 시작한다
                it.pop(k, None)
        if not rows:
            continue
        # (2026-08-14) **같은 발표의 레코드만** 비교한다. Benzinga 는 과거 발표 레코드를
        # 전부 쌓아두는데, 종전엔 '가장 최근의 분기(또는 연간) 레코드'를 골라서
        # 반년 전 발표의 값과 비교하는 오탐이 다수였다(실측 ONDS: 8월 발표 Q3 가이던스를
        # 3월 발표의 Q1 레코드 39.0 과 비교 → 값불일치 오탐 · AVEX·ARRY·PTRN 동일).
        # 발표일(d8) ±10일 밖의 레코드는 다른 발표의 것이다 — 비교 대상에서 제외하고,
        # 같은 발표 레코드가 하나도 없으면 그 항목은 대조 불가로 둔다(억지로 비교하지 않는다).
        ref = datetime.strptime(d8, "%Y%m%d").date()
        def _near(x):
            try:
                dt_ = datetime.strptime(str(x.get("date"))[:10], "%Y-%m-%d").date()
                return abs((dt_ - ref).days) <= 10
            except Exception:
                return False
        rows_n = [x for x in rows if _near(x)]
        if not rows_n:
            continue
        r = pool[it["c"]]
        it["g_bz_date"] = rows_n[0].get("date")
        it["g_bz_period"] = f"{rows_n[0].get('period')}{rows_n[0].get('period_year')}"
        it["g_bz_type"] = rows_n[0].get("eps_type")
        # (2026-08-11 수정) Benzinga 는 같은 발표에서 **연간과 분기 가이던스를 모두** 싣는다.
        # 무조건 최신 1건만 보면 우리가 연간을 뽑았는데 포털의 분기 레코드와 비교하게 돼
        # '기간 불일치'로 오인된다(실측 NFLX 우리 FY 51,200 / 포털 Q3 12,860 — 둘 다 맞다).
        # → 항목별로 **우리가 확정한 기간과 같은 기간의 레코드**를 골라 견준다.
        # (2026-08-14) 같은 발표·같은 기간에 레코드가 여럿이면(실측 TDUP: 8/5 발표에 Q3·Q4
        # 둘 다) **우리 값에 가장 가까운 것**을 고른다 — 검증의 질문은 "회사가 실제로 이
        # 숫자를 말했는가"이므로, 여러 레코드 중 아무거나 집어 오탐을 만들 이유가 없다.
        for metric, lo_k, hi_k, gk in (
                ("eps", "eps_guidance_min", "eps_guidance_max", "g_eps"),
                ("rev", "revenue_guidance_min", "revenue_guidance_max", "g_rev")):
            want = it.get(gk + "_per") or it.get("g_per") or "0y"
            want_fy = str(want).endswith("y")
            cands = [x for x in rows_n
                     if (str(x.get("period", "")).upper() == "FY") == want_fy
                     and NUM(x.get(lo_k)) is not None]
            if not cands:                     # 같은 발표에 같은 기간 레코드 없음 → 대조 불가
                continue
            mine_v = it.get(gk)
            if mine_v and len(cands) > 1:
                unit = 1e6 if metric == "rev" else 1
                cands.sort(key=lambda x: abs((NUM(x.get(lo_k)) + (NUM(x.get(hi_k)) or NUM(x.get(lo_k)))) / 2
                                             / unit - mine_v))
            d = cands[0]
            per = "0y" if str(d.get("period", "")).upper() == "FY" else "0q"
            base_k = {("eps", "0y"): "ey0", ("eps", "0q"): "eq0",
                      ("rev", "0y"): "ry0", ("rev", "0q"): "rq0"}[(metric, per)]
            it[gk + "_bzp"] = f"{d.get('period')}{d.get('period_year')}"
            lo, hi = NUM(d.get(lo_k)), NUM(d.get(hi_k))
            base = r.get(base_k)
            if lo is None or hi is None or not base:
                continue
            # (2026-08-10 수정) Benzinga 매출 가이던스는 **원 단위 달러**로 온다.
            # 백만으로 착각해 ×1e6 했더니 화면 값이 1,337.50 vs 1,337,500,000 으로 어긋났다
            # (실측 CECO). 컨센(base)도 원 단위이므로 갭은 그대로, 표시값만 백만으로 낮춘다.
            mid = (lo + hi) / 2
            it[gk + "_p"] = round(mid / (1e6 if metric == "rev" else 1), 2)
            it[gk + "_gap_p"] = round((mid / base - 1) * 100, 1)
            it[gk + "_per_p"] = per
            got += 1
            mine = it.get(gk)
            if mine:
                cmpv = mid / (1e6 if metric == "rev" else 1)
                (same, diff) = (same + 1, diff) if abs(cmpv / mine - 1) <= 0.01 else (same, diff + 1)
        if (n + 1) % 20 == 0:
            _save(live)
            print(f"    [{n+1}/{len(todo)}] 값 {got} · 일치 {same} · 불일치 {diff}", flush=True)
    _save(live)
    print(f"[bz] 완료 — 값 {got}건 · 파싱과 일치 {same} · 불일치 {diff} (검증 전용)")


def _save(live):
    """내 필드만 디스크에 얹는다(다른 수집기 결과를 덮지 않는다)."""
    try:
        disk = json.loads(LIVE.read_text(encoding="utf-8"))
    except Exception:
        disk = live
    idx = {(d8, it["c"]): it for d8, arr in (live.get("days") or {}).items()
           for it in arr if it.get("c")}
    for d8, arr in (disk.get("days") or {}).items():
        for it in arr:
            src = idx.get((d8, it.get("c")))
            if not src:
                continue
            for k in P_FIELDS:
                if src.get(k) is not None:
                    it[k] = src[k]
                elif FORCE:
                    # (2026-08-14) --force 재계산에서 값이 비면 **지운 것**이다 — 안 지우면
                    # 새 규칙(발표일 매칭)이 '대조 불가'로 판단한 항목의 옛 비교값이
                    # 디스크에 그대로 남아 오탐이 유지된다.
                    it.pop(k, None)
    tmp = LIVE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(disk, ensure_ascii=False), encoding="utf-8")
    tmp.replace(LIVE)


if __name__ == "__main__":
    main()
