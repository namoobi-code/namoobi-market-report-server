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
import gzip, html as _html, json, re, time, urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "data" / "db" / "earnings_live_us.json"
WATCH = BASE / "data" / "watch" / "us_8k_watchlist.txt"
CIKMAP = BASE / "data" / "watch" / "cik_map.json"
H = {"User-Agent": "namoobi research namoobi@gmail.com"}
ET = timezone(timedelta(hours=-4))          # 미 동부(서머타임 EDT). 겨울(-5) 오차 1시간은 라벨용이라 허용

def get(u, timeout=20, tries=3):
    """SEC 요청 — 읽기 타임아웃은 **재시도**한다.

    (2026-08-21) SEC/EDGAR 는 간헐적으로 응답이 느려 read timeout 을 던진다. 종전에는
    그대로 예외가 올라가 **그 회차 전체가 중단**됐다(실측: 2,083회 실행 중 202회(9.7%)가
    Traceback 으로 종료. 죽는 지점은 대부분 main() 의 EDGAR 최신 공시 피드 호출로,
    한 건 실패가 5,163종 워치 전체를 날린다). 매분 폴링이라 다음 회차가 메워 주지만,
    실적 발표가 몰리는 시간대에 연달아 실패하면 감지가 지연된다.
    지수 백오프로 3회까지 재시도하고, 그래도 실패하면 예외를 올려 호출부 판단에 맡긴다.
    """
    last = None
    for i in range(tries):
        try:
            return urllib.request.urlopen(
                urllib.request.Request(u, headers=H), timeout=timeout).read()
        except Exception as e:                       # 타임아웃·일시적 5xx·연결 끊김
            last = e
            if i < tries - 1:
                time.sleep(1.5 * (i + 1))            # 1.5s → 3.0s
    raise last

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

# 직전에 내려받은 첨부의 원문 HTML — {(cik, accno): html}. 표 파서가 재사용한다.
RAW_CACHE = {}

# (2026-08-10) 첨부 원문을 **디스크에 캐시**한다.
# 파서를 고칠 때마다 전 종목을 다시 파싱해야 하는데, 그때마다 SEC 를 다시 부르면
# 속도 제한에 걸린다(실제로 걸려서 가이던스가 통째로 비는 사고가 났다).
# 보도자료는 한 번 제출되면 바뀌지 않으므로 접수번호로 캐시하면 영구 재사용할 수 있다.
# → 재파싱은 SEC 호출 0회. 몇 번을 돌리든 상관없다.
EXC_DIR = Path(__file__).resolve().parent.parent / "data" / "cache" / "exhibit"


def _exc_path(accno, suffix=""):
    EXC_DIR.mkdir(parents=True, exist_ok=True)
    return EXC_DIR / f"{accno}{suffix}.html.gz"


def exhibit_texts_extra(cik, accno, max_n=2):
    """같은 8-K 의 **보조 첨부**(Exhibit 99.2 프레젠테이션·prepared remarks 등) 평문 목록.

    (2026-08-15) exhibit_text() 는 첨부 1개(가장 큰 ex99)만 읽는다 — 원래 SEC 호출을
    아끼려던 선택인데, 가이던스를 99.2 에 싣는 회사가 실재해(실측 '원문에 없음' 57건 분석)
    주 첨부에서 가이던스를 못 찾았을 때만 나머지 ex99 첨부를 추가로 읽는다.
    파일별 캐시(_2·_3 접미사)로 재실행 시 SEC 호출 없음.
    """
    an = accno.replace("-", "")
    outs = []
    # 캐시 우선 — 인덱스 조회도 생략
    cached = [_exc_path(accno, f"_{i}") for i in range(2, 2 + max_n)]
    if any(p.exists() for p in cached):
        for p in cached:
            if p.exists():
                try:
                    outs.append(_strip(gzip.decompress(p.read_bytes()).decode("utf-8", "ignore")))
                except Exception:
                    pass
        return outs
    try:
        idx = json.loads(get(f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{an}/index.json"))
        items = idx.get("directory", {}).get("item", [])
    except Exception:
        return []
    ex = sorted([i for i in items
                 if re.search(r"ex-?99", str(i.get("name", "")), re.I)
                 and str(i.get("name", "")).lower().endswith((".htm", ".html"))],
                key=lambda i: -int(i.get("size") or 0))
    for n, i in enumerate(ex[1:1 + max_n]):     # [0]=주 첨부(exhibit_text 가 이미 읽음)
        try:
            raw = get(f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{an}/{i['name']}", timeout=30)
            t = raw.decode("utf-8", "ignore")
            p = _exc_path(accno, f"_{n + 2}")
            tmp = p.with_suffix(".tmp")
            tmp.write_bytes(gzip.compress(t.encode("utf-8"), 6))
            tmp.replace(p)
            outs.append(_strip(t))
            time.sleep(0.15)
        except Exception:
            pass
    return outs


def _strip(t):
    t = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", t, flags=re.S | re.I)
    t = re.sub(r"<[^>]+>", " ", t)
    t = _html.unescape(t)                       # &#177;→± &#8217;→' 등 일괄 해제
    t = t.replace("–", "-").replace("—", "-")
    # (2026-08-15) 제로폭 공백(U+200B)·BOM — Word 기반 8-K 표의 셀 사이에 끼는데
    # 정규식 \s 에 안 잡혀 "Net revenue ​ $ 5,890 ​ $ 6,180" 같은 표 행이 통째로
    # 매칭 실패했다(실측 GMRS — Low/High 표가 있는데도 후보 미매칭).
    t = t.replace("​", " ").replace("﻿", " ")
    return re.sub(r"\s+", " ", t)


def exhibit_raw(cik, accno):
    """표 파서용 **원문 HTML** — 디스크 캐시에서 직접 읽는다.

    (2026-08-21) 종전에는 표 파서가 RAW_CACHE 만 봤는데, 이 캐시는 8개가 넘으면
    통째로 비우고(clear) 워커 4개가 동시에 쓴다. 그래서 대량 배치에서는 자기 원문이
    남의 것에 밀려 사라지고, 표 파서가 빈 문자열을 받아 조용히 {} 를 반환했다
    (실측 WEX: 단독 실행하면 fy_eps 19.68~20.08(BZ 19.88 과 일치)을 정확히 뽑는데
     백필로 돌리면 값이 없다). 표 파서 v2 를 고쳐도 실측이 안 움직이던 원인이다.
    보도자료는 제출 뒤 바뀌지 않으므로 디스크 캐시를 직접 읽으면 SEC 호출은 0회다.
    """
    t = RAW_CACHE.get((str(cik), accno))
    if t:
        return t
    cp = _exc_path(accno)
    if cp.exists():
        try:
            return gzip.decompress(cp.read_bytes()).decode("utf-8", "ignore")
        except Exception:
            pass
    return ""


def exhibit_text(cik, accno):
    """8-K 첨부 중 **실적 보도자료** 본문 → 태그 제거한 평문.

    파일명 규칙이 회사마다 다르다(실측):
      MU   a2026q3ex991-pressrelease.htm   ← 'ex99' 포함
      NVDA q1fy27pr.htm                    ← 'ex99' 없음. 'pr'(press release)
    → ①ex99 ②pressrelease/pr/earnings ③그래도 없으면 '본문 htm 중 가장 큰 것'(주 8-K 문서·
      R*.htm 같은 XBRL 렌더링 파일은 제외) 순으로 고른다.
    """
    an = accno.replace("-", "")
    # 캐시가 있으면 SEC 를 부르지 않는다. 보도자료는 제출 뒤 바뀌지 않는다.
    cp = _exc_path(accno)
    if cp.exists():
        try:
            t = gzip.decompress(cp.read_bytes()).decode("utf-8", "ignore")
            if len(RAW_CACHE) > 8:
                RAW_CACHE.clear()
            RAW_CACHE[(str(cik), accno)] = t
            return _strip(t)
        except Exception:
            pass
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
    # (2026-08-10) 원문 HTML 을 남겨 둔다 — 표 파서(guidance_table)가 같은 첨부를 다시
    # 내려받지 않게 하기 위함이다(SEC 호출을 두 배로 늘리면 곧바로 차단당한다).
    if len(RAW_CACHE) > 8:        # 워커 4개가 동시에 쓰므로 통째로 비우면 남의 것을 지운다
        RAW_CACHE.clear()
    RAW_CACHE[(str(cik), accno)] = t
    try:                          # 다음 재파싱부터는 SEC 호출 없이 이 파일을 쓴다
        tmp = cp.with_suffix(".tmp")
        tmp.write_bytes(gzip.compress(t.encode("utf-8"), 6))
        tmp.replace(cp)
    except Exception:
        pass
    return _strip(t)


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
    # (2026-08-15) REIT 는 **종목 섹터 속성**으로 판정해 EPS 갭을 만들지 않는다.
    # 리츠의 컨센서스는 FFO 기준이라 회사의 net income per share 가이던스와 비교하면
    # 반드시 어긋난다(실측 CSR +967% · LTC +292% · O +64%). 종전엔 파서가 문맥 300자
    # 안의 'FFO' 단어로 판정했는데 단어가 창 밖이면 놓쳤다 — 섹터가 근본 판정 기준이다.
    is_reit = "real estate" in str(r.get("sector") or "").lower()
    if is_reit:
        g = {k: v for k, v in g.items() if "eps" not in k}
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
    _ev = g.get("_ev") or {}
    # (2026-08-10) 값으로 기간을 되돌리는 '자동 교정'은 넣지 않는다 —
    # 그건 파싱 실패를 숨기는 땜빵이다. 기간은 **파서가 문장에서 확정**하고,
    # 확정 못 하면 값을 내보내지 않는다(guidance_parse._period).
    rev_try = [(g.get("rev_lo"), g.get("rev_hi"), q_rev, q_per, "rev"),
               (g.get("fy_rev_lo"), g.get("fy_rev_hi"), r.get("ry0"), "0y", "fy_rev"),
               (g.get("fy_rev_lo"), g.get("fy_rev_hi"), r.get("ry1"), "+1y", "fy_rev")]
    eps_try = [(g.get("eps_lo"), g.get("eps_hi"), q_eps, q_per, "eps"),
               (g.get("fy_eps_lo"), g.get("fy_eps_hi"), r.get("ey0"), "0y", "fy_eps"),
               (g.get("fy_eps_lo"), g.get("fy_eps_hi"), r.get("ey1"), "+1y", "fy_eps")]
    for lo, hi, base, per, evk in rev_try:
        if lo and hi and base:
            mid = (lo + hi) / 2
            out["g_rev"] = round(mid / 1e6, 1)              # 백만 달러
            out["g_rev_gap"] = round((mid / base - 1) * 100, 1)
            out["g_rev_per"] = per
            # (2026-08-21) 기준(GAAP/조정) 을 함께 싣는다. 파서는 예전부터 이 값을 만들고
            # 있었는데 여기서 out 에 담지 않아 전 레코드가 basis=None 이었다(실측: 저장된
            # 8-K 레코드 전량). BZ 불일치 80건 중 57건이 BZ 'Adj' 표기라 기준 대조가 필요하다.
            if g.get(evk + "_basis"):
                out["g_rev_basis"] = g[evk + "_basis"]
            if _ev.get(evk):                                # 근거 문장 — 화면에서 검증 가능하게
                out["g_rev_ev"] = _ev[evk][:300]
            break
    for lo, hi, base, per, evk in eps_try:
        if lo and hi and base and base > 0:
            mid = (lo + hi) / 2
            out["g_eps"] = round(mid, 2)
            out["g_eps_gap"] = round((mid / base - 1) * 100, 1)
            out["g_eps_per"] = per
            if g.get(evk + "_basis"):
                out["g_eps_basis"] = g[evk + "_basis"]
            if _ev.get(evk):
                out["g_eps_ev"] = _ev[evk][:300]
            break
    # (2026-08-15 제거) 갭 크기 기반 차단 가드를 뒀었으나 사용자 지시로 제거 —
    # 값 필터링은 땜빵이다. 극단 갭을 만드는 원인(기간 오분류 등)은 파서에서 고친다.
    if out:
        # 대표 기간(구버전 호환) — 매출 기준 우선, 없으면 EPS 기준
        out["g_per"] = out.get("g_rev_per") or out.get("g_eps_per") or q_per
    # (2026-08-10) 설비투자 가이던스 — 컨센서스가 없으므로 갭은 계산하지 않고 **값만** 싣는다.
    # 회사가 제시할 때만 채우고, 없으면 화면에 '미제시'로 둔다(추정하지 않는다).
    for pre, per in (("", q_per), ("fy_", "0y")):
        lo, hi = g.get(pre + "capex_lo"), g.get(pre + "capex_hi")
        if lo and hi and "g_capex" not in out:
            out["g_capex"] = round((lo + hi) / 2 / 1e6, 1)      # 백만 달러
            out["g_capex_per"] = per
            if (g.get("_ev") or {}).get(pre + "capex"):
                out["g_capex_ev"] = g["_ev"][pre + "capex"][:300]
    # (2026-08-21) **리츠 FFO 가이던스** — 리츠의 컨센서스는 FFO 기준이라 회사의 EPS
    # 가이던스는 위(is_reit)에서 통째로 버리는데, 그러면 리츠는 가이던스 칸이 늘 비었다
    # (실측: 부동산 섹터 8-K 192건 중 BZ 가 주당값을 주는 것 96건이 전량 공백).
    # 회사가 낸 FFO 값 자체는 유효한 선행 정보이므로, 무료 FFO 컨센서스가 없는 만큼
    # 갭은 계산하지 않고 **값만** 싣는다(CapEx 와 같은 취급).
    for pre, per in (("", q_per), ("fy_", "0y")):
        lo, hi = g.get(pre + "ffo_lo"), g.get(pre + "ffo_hi")
        if lo and hi and "g_ffo" not in out:
            out["g_ffo"] = round((lo + hi) / 2, 2)
            out["g_ffo_per"] = per
            if g.get(pre + "ffo_basis"):
                out["g_ffo_basis"] = g[pre + "ffo_basis"]      # core(조정 FFO) · ffo(기본)
            if _ev.get(pre + "ffo"):
                out["g_ffo_ev"] = _ev[pre + "ffo"][:300]
    # (2026-08-21) **성장률 가이던스** — 금액을 안 주고 성장률로만 말하는 회사(실측 47건).
    # 금액 환산은 도입하지 않는다(guidance_parse 첫머리 2026-08-16 실측 결론) — 성장률
    # 그대로 싣는다. 컨센서스는 금액이라 갭은 만들지 않는다. 금액을 확보한 지표는
    # 파서 단계에서 이미 건너뛰므로 여기서 금액과 겹치지 않는다.
    for met, key in (("rev", "g_rev_gr"), ("eps", "g_eps_gr")):
        for pre, per in (("", q_per), ("fy_", "0y")):
            lo, hi = g.get(pre + met + "_gr_lo"), g.get(pre + met + "_gr_hi")
            if lo is not None and hi is not None and key not in out:
                out[key] = round((lo + hi) / 2, 1)
                out[key + "_lo"], out[key + "_hi"] = lo, hi
                out[key + "_per"] = per
                if _ev.get(pre + met + "_gr"):
                    out[key + "_ev"] = _ev[pre + met + "_gr"][:300]
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
    # (2026-08-21) 두 피드는 **독립적으로** 처리한다 — 재시도까지 실패한 쪽이 있어도
    # 나머지 피드로 감시를 이어간다. 종전엔 6-K 한 건이 죽으면 8-K 결과까지 버려졌다.
    d = ""
    feed_err = []
    for ftype in ("8-K", "6-K"):
        try:
            d += get(f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type={ftype}"
                     "&company=&dateb=&owner=include&count=100&output=atom").decode("utf-8", "ignore")
        except Exception as e:
            feed_err.append(f"{ftype}:{type(e).__name__}")
    if not d:                                    # 두 피드 모두 실패 — 이번 회차만 건너뛴다
        print(f"[8k] 피드 수신 실패({', '.join(feed_err)}) — 이번 회차 건너뜀", flush=True)
        return
    if feed_err:
        print(f"[8k] 일부 피드 실패({', '.join(feed_err)}) — 나머지로 진행", flush=True)
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
        # (2026-08-15) Item 7.01(Reg FD) 도 본다 — **분기 중 가이던스 상향/하향·인베스터데이
        # 자료는 실적일이 아니라 7.01 로 나온다**(사용자 지적: 놓치는 채널). 소음 방지:
        # 비핵심 종목의 7.01 은 첨부에서 가이던스가 실제로 파싱될 때만 기록한다.
        is_fd = (not is_ern) and ("7.01" in its)
        if ft == "8-K" and not is_core and not is_ern and not is_fd:
            continue                                   # 비핵심은 실적(2.02)·RegFD(7.01) 만 후보
        tag = f"📄 {ft}{'(실적)' if is_ern else ('(RegFD)' if is_fd else '')} 접수 {et.strftime('%H:%M')}ET"
        gd = {}
        if is_ern or is_fd:                          # 실적·RegFD 8-K 는 보도자료를 열어 가이던스 확인
            try:
                gd = guidance_gap(sym, parse_guidance(exhibit_text(cik, ac.group(1))), pool_us,
                                  et.strftime("%Y-%m-%d"))     # 발표일 → 기준 분기 판정
            except Exception:
                gd = {}
            if is_fd and not is_core and not gd:
                continue                             # 가이던스 없는 수시보고(7.01) — 기록하지 않는다
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
