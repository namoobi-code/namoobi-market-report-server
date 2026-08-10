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
import html as _html, json, re, urllib.request
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

# ── (2026-08-09) 가이던스 파싱 ─────────────────────────────────────────────
#  8-K Item 2.02 에 첨부되는 Exhibit 99.1(실적 보도자료) 본문에는 회사가 직접 제시한
#  **다음 분기 전망(가이던스)** 이 들어 있다. 실적 자체보다 이 숫자가 주가를 더 흔든다
#  (샌디스크: EPS 는 컨센 상회했는데 가이던스가 기대에 못 미쳐 시간외 -5%).
#
#  이것이 "주가가 움직이기 전"에 알 수 있는 **유일한** 경로다 — 애널리스트 컨센서스
#  리비전은 아무리 빨라도 다음 날에나 나온다.
#
#  한계(정직하게): 문장 형식이 회사마다 제각각이라 정규식이 다 잡지는 못한다.
#  못 잡으면 조용히 건너뛴다 — 틀린 숫자를 보여주는 것보다 안 보여주는 편이 낫다.
_MULT = {"billion": 1e9, "bn": 1e9, "b": 1e9, "million": 1e6, "mm": 1e6, "m": 1e6}
_NUM = r"\$?\s?([\d,]+(?:\.\d+)?)\s*(billion|million|bn|mm|b|m)?"

def _to_num(v, unit, hint=None):
    try:
        x = float(v.replace(",", ""))
    except Exception:
        return None
    u = (unit or "").lower()
    if u in _MULT:
        return x * _MULT[u]
    return x * (_MULT[hint] if hint in _MULT else 1)

def exhibit_text(cik, accno):
    """8-K 첨부 중 **실적 보도자료** 본문 → 태그 제거한 평문.

    파일명 규칙이 회사마다 다르다(실측):
      MU   a2026q3ex991-pressrelease.htm   ← 'ex99' 포함
      NVDA q1fy27pr.htm                    ← 'ex99' 없음. 'pr'(press release)
    → ①ex99 ②pressrelease/pr/earnings ③그래도 없으면 '본문 htm 중 가장 큰 것'(주 8-K 문서·
      R*.htm 같은 XBRL 렌더링 파일은 제외) 순으로 고른다.
    """
    an = accno.replace("-", "")
    try:
        idx = json.loads(get(f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{an}/index.json"))
        items = idx.get("directory", {}).get("item", [])
    except Exception:
        return ""
    htm = [i for i in items if str(i.get("name", "")).lower().endswith((".htm", ".html", ".txt"))]
    def pick():
        for pat in (r"ex-?99", r"press.?release", r"(^|[^a-z])pr\.htm", r"earnings"):
            c = [i for i in htm if re.search(pat, i.get("name", ""), re.I)]
            if c:
                return max(c, key=lambda i: int(i.get("size") or 0))["name"]
        c = [i for i in htm
             if not re.match(r"(R\d+|FilingSummary|MetaLinks)", i.get("name", ""), re.I)
             and not re.search(r"index|\.txt$|-\d{8}\.htm$", i.get("name", ""), re.I)]
        return max(c, key=lambda i: int(i.get("size") or 0))["name"] if c else None
    name = pick()
    if not name:
        return ""
    try:
        raw = get(f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{an}/{name}", timeout=30)
    except Exception:
        return ""
    t = raw.decode("utf-8", "ignore")
    t = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", t, flags=re.S | re.I)
    t = re.sub(r"<[^>]+>", " ", t)
    t = _html.unescape(t)                       # &#177;→± &#8217;→' 등 일괄 해제
    t = t.replace("\u2013", "-").replace("\u2014", "-")
    return re.sub(r"\s+", " ", t)


_FYRE = r"full[- ]year|fiscal year|for the year|full fiscal|annual|FY\\s?20\\d\\d"

# (2026-08-10) 가이던스 파서는 guidance_parse.py 로 분리 — 규칙이 길어져 이 파일에 두면
# 8-K 감시 로직과 뒤섞인다. 파서는 후보별로 ①전사 여부 ②GAAP/조정 ③기간 명시 ④단위·범위를
# 모두 확인해야 채택하고, 근거(_ev)·기각 사유(_skip)를 함께 돌려준다.
from guidance_parse import parse_guidance  # noqa: E402  (같은 폴더)


def guidance_gap(sym, g, pool_us, ann=None):
    """가이던스 중간값 vs **그 가이던스가 가리키는 분기**의 컨센서스 → 갭%.

    (2026-08-09 근본 수정) 예전에는 무조건 +1q(rq1·eq1)와 비교했다. 그러나 회사가 실적을
    발표하며 제시하는 '다음 분기'는 **그 시점에 진행 중인 분기**, 즉 Yahoo 의 0q 다.
    +1q 는 그 다음 분기여서 한 칸 밀린 값과 비교하게 된다.
      실측 ESE(2026-08-06 발표, 가이던스 EPS 2.55~2.65 = 중간값 2.60)
        0q(9/30 종료) 컨센 2.57 → 갭 +1.0%  ← 실제(사실상 인라인)
        +1q(12/31 종료) 컨센 1.81 → 갭 +43.3% ← 예전 표시(대폭 상회로 왜곡)
      실측 SNDK: 0q 기준 −1.4% 인데 +1q 기준 −14.0% 로 과장됐다.
    → 발표일 이후에 끝나는 첫 분기를 기준으로 삼는다(보통 0q, 야후가 아직 롤오버 전이면 +1q).

    (2026-08-10) **우선순위 4단계** (사용자 지정):
        ① 진행분기(0q) ② 다음분기(+1q) ③ 올해 FY(0y) ④ 내년 FY(+1y)
    분기 가이던스가 있으면 분기끼리, 없고 연간 가이던스만 있으면 연간 컨센(ry0/ey0·ry1/ey1)과
    같은 기간끼리 비교한다. 매출·EPS 는 각각 독립적으로 우선순위를 적용한다
    (매출은 분기만, EPS 는 연간만 주는 회사가 흔하다).
    """
    r = pool_us.get(sym) or {}
    out = {}
    # 분기 기준 선택: 발표일(ann, YYYY-MM-DD) 이후에 끝나는 첫 컨센 분기
    q_eps, q_rev, q_per = r.get("eq0"), r.get("rq0"), "0q"
    if ann:
        e0, e1 = r.get("q0e"), r.get("q1e")               # 각 분기 종료일(us_consensus 가 저장)
        if e0 and e0 <= ann and e1:                        # 0q 가 이미 끝났으면(롤오버 전) +1q
            q_eps, q_rev, q_per = r.get("eq1"), r.get("rq1"), "+1q"
    if q_eps is None and q_rev is None:                    # 스냅샷 이전 데이터 폴백
        q_eps, q_rev, q_per = r.get("eq1"), r.get("rq1"), "+1q"
    # (2026-08-10 재설계) **갭 크기로 자르는 임계값을 없앴다.**
    # 예전엔 |갭|>60%(→25%)를 오파싱으로 보고 버렸는데, 이는 진짜 큰 갭까지 지우는 땜빵이었다.
    # 이제 파서(guidance_parse.py)가 채택 전에 ①전사 지표 ②조정 기준 ③기간 명시 ④단위·범위를
    # 모두 확인하므로, 여기서는 '같은 기간·같은 기준끼리' 비교만 하면 된다.
    # 값이 크게 벌어지면 그건 실제 신호다(가이던스 쇼크) — 지우지 않는다.
    # (가이던스 lo, hi, 컨센 기준값, 기간라벨) — 앞에서부터 우선 채택
    rev_try = [(g.get("rev_lo"), g.get("rev_hi"), q_rev, q_per),
               (g.get("fy_rev_lo"), g.get("fy_rev_hi"), r.get("ry0"), "0y"),
               (g.get("fy_rev_lo"), g.get("fy_rev_hi"), r.get("ry1"), "+1y")]
    eps_try = [(g.get("eps_lo"), g.get("eps_hi"), q_eps, q_per),
               (g.get("fy_eps_lo"), g.get("fy_eps_hi"), r.get("ey0"), "0y"),
               (g.get("fy_eps_lo"), g.get("fy_eps_hi"), r.get("ey1"), "+1y")]
    for lo, hi, base, per in rev_try:
        if lo and hi and base:
            mid = (lo + hi) / 2
            gp = (mid / base - 1) * 100
            out["g_rev"] = round(mid / 1e6, 1)              # 백만 달러
            out["g_rev_gap"] = round(gp, 1)
            out["g_rev_per"] = per
            break
    for lo, hi, base, per in eps_try:
        if lo and hi and base and base > 0:
            mid = (lo + hi) / 2
            gp = (mid / base - 1) * 100
            out["g_eps"] = round(mid, 2)
            out["g_eps_gap"] = round(gp, 1)
            out["g_eps_per"] = per
            break
    if out:
        # 대표 기간(구버전 호환) — 매출 기준 우선, 없으면 EPS 기준
        out["g_per"] = out.get("g_rev_per") or out.get("g_eps_per") or q_per
    return out


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
        gd = {}
        if is_ern:                                   # 실적 8-K 만 보도자료를 열어 가이던스 확인
            try:
                gd = guidance_gap(sym, parse_guidance(exhibit_text(cik, ac.group(1))), pool_us,
                                  et.strftime("%Y-%m-%d"))     # 발표일 → 기준 분기 판정
            except Exception:
                gd = {}
            if gd.get("g_rev_gap") is not None:
                tag += f" · 가이던스 매출 컨센 대비 {gd['g_rev_gap']:+.1f}%"
            elif gd.get("g_eps_gap") is not None:
                tag += f" · 가이던스 EPS 컨센 대비 {gd['g_eps_gap']:+.1f}%"
        lst = days.setdefault(d8, [])
        cur = next((z for z in lst if z["c"] == sym), None)
        if cur:
            if not any("K" in t and "접수" in t for t in cur.get("tags") or []):
                cur.setdefault("tags", []).insert(0, tag)
                cur["acc"] = ac.group(1); cur["cik"] = cik
                cur.update(gd)                      # 가이던스 갭 필드(g_rev·g_rev_gap·g_eps·g_eps_gap)
                if is_core: cur["core"] = 1
                new += 1
        else:
            r = pool_us.get(sym) or {}
            it2 = {"c": sym, "n": r.get("kn") or r.get("n") or sym, "cap": r.get("cap"),
                   "eps": None, "est": None, "spr": None, "tags": [tag],
                   "acc": ac.group(1), "cik": cik, "t": datetime.now().strftime("%H:%M"), **gd}
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
