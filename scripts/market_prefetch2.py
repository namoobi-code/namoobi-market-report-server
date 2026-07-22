#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""market_prefetch2.py — (2026-07-19 서버화 2차) 보고서 실행 전 사전수집 크론.

목적: /namoobi-market-report 실행 시 세션(에이전트)이 웹서치·Chrome 으로 하던 조사를
서버가 주기 수집해 DB(/api/db/<name>)로 제공 — 토큰·시간·확률적 오류 절감.

서브커맨드: all | brokers3 | calendar | policy | factset | ism | ib | rebalance
산출(data/db/):
  brokers3.json        한국투자 '한눈에 투데이' 모닝브리프 본문(+미래에셋 시도) — Chrome 대체
  events_calendar.json 경제 이벤트 캘린더 뼈대(FRED next 발표일+중앙은행 회의+만기 규칙+직전 보고서 이벤트)
  policy_rates.json    6개국 정책금리 실측(FRED·ECOS·global-rates) + nmr_policyrates_monthly 이력 upsert
  factset_insight.json FactSet Insight RSS 최신 글(HubSpot JS 캐시 우회 — Chrome 대체)
  ism_pmi.json         ISM 제조/서비스 최신 공표치(구글뉴스 헤드라인 파싱, best-effort)
  ib_insights.json     IB 5사 하우스뷰 관련 최신 보도 풀(24시간 보존)
  rebalance_news.json  S&P500·나스닥100 지수변경 헤드라인 모니터(마커 변동시에만 에이전트 발행)
전부 비차단: 실패 항목은 기존 DB 유지·경고만.
"""
import json, os, re, sys, html, urllib.request, urllib.parse
from datetime import datetime, timedelta, date
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DB = BASE / "data" / "db"
DATA = BASE / "data"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
NOW = datetime.now()


def fetch(url, timeout=15):
    req = urllib.request.Request(url, headers=UA)
    return urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8", "ignore")


def load(name, default=None):
    try:
        return json.load(open(DB / f"{name}.json", encoding="utf-8"))
    except Exception:
        return default if default is not None else {}


def save(name, obj):
    obj["as_of"] = NOW.strftime("%Y-%m-%d %H:%M")
    obj.setdefault("marker", NOW.strftime("%Y-%m-%d"))
    DB.mkdir(parents=True, exist_ok=True)
    (DB / f"{name}.json").write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")
    print(f"[{name}] 저장 OK")


def key_of(fname):
    for p in (BASE / "keys" / fname, BASE / fname):
        try:
            v = p.read_text(encoding="utf-8").strip().split()[0]
            if v:
                return v
        except Exception:
            pass
    return None


def gnews(query, hours=48, cap=20, lang="ko"):
    """구글뉴스 RSS → [{title,url,date,src}] (발행 hours 이내만)."""
    try:
        loc = "&hl=ko&gl=KR&ceid=KR:ko" if lang == "ko" else "&hl=en-US&gl=US&ceid=US:en"
        u = ("https://news.google.com/rss/search?q=" + urllib.parse.quote(query) + loc)
        x = fetch(u, 15)
        out = []
        cutoff = NOW - timedelta(hours=hours)
        for it in re.findall(r"<item>(.*?)</item>", x, re.S)[:cap * 2]:
            t = re.search(r"<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", it, re.S)
            l = re.search(r"<link>(.*?)</link>", it, re.S)
            d = re.search(r"<pubDate>(.*?)</pubDate>", it)
            s = re.search(r"<source[^>]*>(.*?)</source>", it)
            if not (t and l):
                continue
            try:
                pd = datetime.strptime(d.group(1).strip()[:25], "%a, %d %b %Y %H:%M:%S")
                pd = pd + timedelta(hours=9)  # GMT→KST
            except Exception:
                pd = NOW
            if pd < cutoff:
                continue
            out.append({"title": html.unescape(t.group(1)).strip()[:120],
                        "url": html.unescape(l.group(1)).strip(),
                        "date": pd.strftime("%Y-%m-%d %H:%M"),
                        "src": html.unescape(s.group(1)).strip() if s else ""})
            if len(out) >= cap:
                break
        return out
    except Exception as e:
        print("  gnews 실패:", query[:20], repr(e)[:60])
        return []


# ── 1) 증권사(한투 모닝브리프 — Chrome 대체; 삼성·미래에셋 목록은 broker_reports(네이버)가 커버) ──
def brokers3():
    out = load("brokers3", {})
    try:
        for back in range(0, 5):
            d = (NOW - timedelta(days=back)).strftime("%Y-%m-%d")
            h = fetch("https://securities.koreainvestment.com/main/research/research/"
                      f"Strategy.jsp?jkGubun=99&fromDate={d}", 15)
            txt = re.sub(r"<[^>]+>", "\n", h)
            txt = html.unescape(re.sub(r"[\t ]+", " ", txt))
            m = re.search(r"한눈에 투데이[\s\S]{0,1400}?리서치본부\s*[\d. ]+", txt)
            if m:
                body = re.sub(r"\n{2,}", "\n", m.group(0)).strip()
                out["korea_inv"] = {"today": body[:1300], "asof": d,
                                    "url": "https://securities.koreainvestment.com/main/research/research/Strategy.jsp?jkGubun=99"}
                break
    except Exception as e:
        print("  한투 실패(기존 유지):", repr(e)[:70])
    out["note"] = "삼성·미래에셋 리포트 목록은 broker_reports(네이버 수집) DB 참조"
    save("brokers3", out)


# ── 2) 경제 이벤트 캘린더 ──
_FRED_IDMAP = {"CPI": "CPIAUCSL", "PPI": "PPIFIS", "PCE 물가": "PCEPI", "고용보고서(NFP)": "PAYEMS",
               "소매판매": "RSAFS", "GDP": "GDP", "신규 실업수당": "ICSA"}
_FRED_TOP = ("CPI", "고용보고서(NFP)", "PCE 물가")


def _fred_release_dates(limit=60):
    """label -> 최근 발표일(오름차순) 리스트. 다음 발표일(미래)·지난 이벤트(과거) 공용.
       (2026-07-22) 기존 _fred_next_releases 는 미래만 뽑아 '지난 이벤트'가 안 쌓였다.
       과거 발표일도 함께 반환해 past 를 결정적으로 재생성한다.
       limit=60: 주간 지표(신규 실업수당)는 FRED 예정일이 20개 넘게 미래에 깔려 있어
       desc·limit=20 이면 과거는 물론 코앞 다음 회차(주 목요일)도 못 잡는다 → 현재를 확실히 감싼다."""
    key = key_of("fred.key")
    if not key:
        return {}
    out = {}
    for label, sid in _FRED_IDMAP.items():
        try:
            ru = f"https://api.stlouisfed.org/fred/series/release?series_id={sid}&api_key={key}&file_type=json"
            rid = json.loads(fetch(ru))["releases"][0]["id"]
            du = (f"https://api.stlouisfed.org/fred/release/dates?release_id={rid}&api_key={key}"
                  f"&file_type=json&sort_order=desc&limit={limit}&include_release_dates_with_no_data=true")
            out[label] = sorted(x["date"] for x in json.loads(fetch(du))["release_dates"])
        except Exception:
            pass
    return out


def _expiries_past(cutoff, tds):
    """지난 창(cutoff≤d<오늘)에 든 만기 — KR 둘째 목요일 / 美 셋째 금요일(3·6·9·12월)."""
    ev = []
    for back in (0, 1):
        yy, mm = NOW.year, NOW.month - back
        if mm <= 0:
            mm += 12
            yy -= 1
        thu = [d for d in range(1, 29) if date(yy, mm, d).weekday() == 3]
        fri = [d for d in range(1, 29) if date(yy, mm, d).weekday() == 4]
        kd = date(yy, mm, thu[1]).isoformat()
        if cutoff <= kd < tds:
            ev.append({"date": kd, "region": "한국", "event": "선물옵션 동시만기",
                       "importance": "★★", "source": "거래소 규칙(매월 둘째 목요일)"})
        if mm in (3, 6, 9, 12):
            qd = date(yy, mm, fri[2]).isoformat()
            if cutoff <= qd < tds:
                ev.append({"date": qd, "region": "미국", "event": "쿼드러플 위칭(선물옵션 동시만기)",
                           "importance": "★★★", "source": "거래소 규칙(3·6·9·12월 셋째 금요일)"})
    return ev


def _expiries(months=3):
    """만기 규칙: KR 선물옵션 동시만기=매월 둘째 목요일 / 美 쿼드러플위칭=3·6·9·12월 셋째 금요일."""
    ev = []
    y, m = NOW.year, NOW.month
    for i in range(months + 1):
        mm = m + i
        yy = y + (mm - 1) // 12
        mm = (mm - 1) % 12 + 1
        thu = [d for d in range(1, 29) if date(yy, mm, d).weekday() == 3]
        fri = [d for d in range(1, 29) if date(yy, mm, d).weekday() == 4]
        kd = date(yy, mm, thu[1])
        if kd >= NOW.date():
            ev.append({"date": kd.isoformat(), "region": "한국", "event": "선물옵션 동시만기",
                       "importance": "★★", "source": "거래소 규칙(매월 둘째 목요일)"})
        if mm in (3, 6, 9, 12):
            qd = date(yy, mm, fri[2])
            if qd >= NOW.date():
                ev.append({"date": qd.isoformat(), "region": "미국", "event": "쿼드러플 위칭(선물옵션 동시만기)",
                           "importance": "★★★", "source": "거래소 규칙(3·6·9·12월 셋째 금요일)"})
    return ev


def calendar():
    ev = []
    tds = NOW.strftime("%Y-%m-%d")
    relmap = _fred_release_dates()          # label -> 발표일(오름차순), 미래·과거 공용
    # FRED 다음 발표일(미래)
    for label, ds in relmap.items():
        fut = [x for x in ds if x > tds]
        if fut:
            ev.append({"date": fut[0], "region": "미국", "event": f"{label} 발표",
                       "importance": "★★★" if label in _FRED_TOP else "★★",
                       "source": "FRED release calendar(실측)"})
    # FOMC(기존 DB) + 중앙은행 회의(시드 — 보고서 실행이 확정 일정으로 갱신)
    fm = load("fomc_meetings", {})
    rows = fm.get("data") if isinstance(fm.get("data"), list) else (fm.get("data", {}).get("rows") if isinstance(fm.get("data"), dict) else fm.get("rows"))
    for r in (rows or []):
        dt = str(r.get("date", ""))[:10]
        if dt > NOW.strftime("%Y-%m-%d"):
            ev.append({"date": dt, "region": "미국", "event": "FOMC 회의", "importance": "★★★",
                       "source": "db/fomc_meetings"})
    cb = load("cb_meetings", {})
    for r in (cb.get("rows") or []):
        if str(r.get("date", ""))[:10] >= NOW.strftime("%Y-%m-%d"):
            ev.append(r)
    ev += _expiries()
    # 직전 보고서의 검증된 이벤트(뉴스에이전트 출처 확인분) 병합
    try:
        rd = json.load(open(DATA / "report" / "report_data.json", encoding="utf-8"))
        for sec, imp in (("events_calendar", None), ("bigtech_events", None)):
            for r in (rd.get("news", {}).get(sec) or []):
                dt = str(r.get("date", ""))[:10]
                if re.match(r"\d{4}-\d{2}-\d{2}", dt) and dt >= NOW.strftime("%Y-%m-%d"):
                    ev.append({"date": dt, "region": r.get("region", "빅테크" if sec == "bigtech_events" else ""),
                               "event": r.get("event", ""), "importance": r.get("importance", "★★"),
                               "source": r.get("source", "직전 보고서(출처 확인분)")})
        lt = [r for r in (rd.get("news", {}).get("events_calendar_longterm") or []) if r.get("event")]
    except Exception:
        lt = []
    # dedupe(날짜+이벤트 앞 10자)
    seen, ded = set(), []
    for r in sorted(ev, key=lambda x: x["date"]):
        k = (r["date"], re.sub(r"\s", "", str(r["event"]))[:10])
        if k in seen or not r.get("event"):
            continue
        seen.add(k)
        ded.append(r)
    # (2026-07-26) 지난 이벤트 보존(최근 7일) — 직전 DB의 upcoming·past 를 이월.
    #   생성 로직이 미래만 만들기 때문에, 어제까지 '다가오는'에 있던 것이 오늘 지난 이벤트가 된다.
    #   캘린더 우측 '지난 이벤트' 패널(자동 반영 확인용)의 데이터 원천.
    prev = load("events_calendar", {})
    cutoff = (NOW.date() - timedelta(days=7)).isoformat()
    pseen, past = set(), []
    # (2026-07-22) 지난 이벤트를 '이월'에만 의존하지 않고 실측 과거조회로 결정적 재생성.
    #   기존엔 어제 upcoming→오늘 past 이월뿐이라, 연속 실행이 끊기거나 FRED가 '다음 발표일'만
    #   주는 탓에 지난 이벤트가 1건(LPR)만 남았다. FRED 최근 발표 + 지난 FOMC/중앙은행/만기 직접 재생성.
    gen = []
    for label, ds in relmap.items():
        for x in ds:
            if cutoff <= x < tds:
                gen.append({"date": x, "region": "미국", "event": f"{label} 발표",
                            "importance": "★★★" if label in _FRED_TOP else "★★",
                            "source": "FRED release calendar(실측)"})
    for r in (rows or []):
        dt = str(r.get("date", ""))[:10]
        if cutoff <= dt < tds:
            gen.append({"date": dt, "region": "미국", "event": "FOMC 회의", "importance": "★★★", "source": "db/fomc_meetings"})
    for r in (cb.get("rows") or []):
        dt = str(r.get("date", ""))[:10]
        if cutoff <= dt < tds:
            gen.append(r)
    gen += _expiries_past(cutoff, tds)
    # 실측 재생성분(gen) + 이월분(prev: 직전 보고서 검증 이벤트 등 생성기 밖 출처) 병합·중복제거
    for r in sorted(gen + (prev.get("past") or []) + (prev.get("upcoming") or []), key=lambda x: str(x.get("date", ""))):
        dt = str(r.get("date", ""))[:10]
        if not (cutoff <= dt < tds) or not r.get("event"):
            continue
        k = (dt, re.sub(r"\s", "", str(r.get("event", "")))[:10])
        if k in pseen:
            continue
        pseen.add(k)
        past.append(r)
    save("events_calendar", {"upcoming": ded[:40], "longterm": lt[:12], "past": past[-40:],
                             "desc": "FRED 발표일정(실측)+FOMC DB+중앙은행 회의 시드+만기 규칙+직전 보고서 검증 이벤트 · past=지난 7일(실측 재생성+이월)"})


# ── 3) 정책금리 6개국 ──
def policy():
    prev = {r.get("country"): r for r in (load("policy_rates", {}).get("rows") or [])}
    rows = []
    key = key_of("fred.key")

    def fred_last(sid):
        u = (f"https://api.stlouisfed.org/fred/series/observations?series_id={sid}&api_key={key}"
             "&file_type=json&sort_order=desc&limit=5")
        for o in json.loads(fetch(u))["observations"]:
            if o["value"] not in (".", ""):
                return float(o["value"]), o["date"]
        return None, None

    try:
        up, d1 = fred_last("DFEDTARU")
        lo, _ = fred_last("DFEDTARL")
        rows.append({"country": "미국", "rate": f"{lo:.2f}~{up:.2f}%", "asof": d1, "source": "FRED DFEDTARU/L(실측)"})
    except Exception as e:
        rows.append(prev.get("미국") or {"country": "미국", "rate": None})
        print("  미국 실패:", repr(e)[:60])
    try:
        v, d1 = fred_last("ECBDFR")
        rows.append({"country": "유로존", "rate": f"{v:.2f}%", "asof": d1, "source": "FRED ECBDFR(예금금리·실측)"})
    except Exception:
        rows.append(prev.get("유로존") or {"country": "유로존", "rate": None})
    # 한국(ECOS 722Y001) — 1/500 로 전체 구간 수신 후 마지막 행(앞 10행만 받으면 옛 값이 잡힘)
    try:
        ek = key_of("ecos.txt")
        u = (f"https://ecos.bok.or.kr/api/StatisticSearch/{ek}/json/kr/1/500/722Y001/D/"
             f"{(NOW - timedelta(days=400)).strftime('%Y%m%d')}/{NOW.strftime('%Y%m%d')}/0101000")
        js = json.loads(fetch(u))["StatisticSearch"]["row"]
        last = js[-1]
        rows.append({"country": "한국", "rate": f"{float(last['DATA_VALUE']):.2f}%",
                     "asof": f"{last['TIME'][:4]}-{last['TIME'][4:6]}-{last['TIME'][6:8]}",
                     "source": "한국은행 ECOS 722Y001(실측)"})
    except Exception as e:
        rows.append(prev.get("한국") or {"country": "한국", "rate": None})
        print("  한국 실패:", repr(e)[:60])
    # 영국·일본·중국(global-rates)
    try:
        h = fetch("https://www.global-rates.com/en/interest-rates/central-banks/", 15)
        blocks = re.split(r'href=[\'"][^\'"]*central-banks/\d+/', h)
        smap = {"british-boe-official-bank-rate": "영국", "japanese": "일본", "boj": "일본",
                "chinese-pbc-loan-prime-rate": "중국"}
        found = {}
        for b in blocks[1:]:
            slug = b.split("/", 1)[0]
            pct = re.search(r"([0-9]{1,2}\.[0-9]{2,3})\s*%", b)
            for sk, cn in smap.items():
                if sk in slug and pct and cn not in found:
                    found[cn] = pct.group(1)
        for cn in ("일본", "중국", "영국"):
            if found.get(cn):
                rows.append({"country": cn, "rate": f"{float(found[cn]):.2f}%",
                             "asof": NOW.strftime("%Y-%m-%d"), "source": "global-rates(실측 스크랩)"})
            else:
                rows.append(prev.get(cn) or {"country": cn, "rate": None})
    except Exception as e:
        for cn in ("일본", "중국", "영국"):
            rows.append(prev.get(cn) or {"country": cn, "rate": None})
        print("  global-rates 실패:", repr(e)[:60])
    rows = [r for r in rows if r and r.get("rate")]
    save("policy_rates", {"rows": rows, "desc": "미국 FRED·한국 ECOS·유로존 FRED·영일중 global-rates — 매일 갱신"})
    # 이력(monthly) upsert — 정책금리 차트 소스 자동 최신화
    try:
        pmp = DATA / "nmr_policyrates_monthly.json"
        if not pmp.exists():
            pmp = DATA / "report" / "policyrates_monthly.json"   # sync_server 업로드 경로
        pm = json.load(open(pmp, encoding="utf-8"))
        chg = 0
        for r in rows:
            cn = r["country"]
            ser = pm.setdefault("series", {}).setdefault(cn, [])
            mid = re.findall(r"[0-9]+\.[0-9]+", r["rate"])
            val = float(mid[-1]) if cn == "미국" and mid else (float(mid[0]) if mid else None)
            if val is None:
                continue
            if not ser or abs(ser[-1][1] - val) > 1e-9:
                ser.append([r.get("asof") or NOW.strftime("%Y-%m-%d"), val])
                chg += 1
            pm.setdefault("current", {})[cn] = val
        if chg:
            pm["updated"] = NOW.strftime("%Y-%m-%d")
            json.dump(pm, open(pmp, "w", encoding="utf-8"), ensure_ascii=False)
        print(f"  monthly 이력 upsert: 변경 {chg}건")
    except Exception as e:
        print("  monthly upsert skip:", repr(e)[:60])


# ── 4) FactSet Insight RSS ──
def factset():
    try:
        x = fetch("https://insight.factset.com/rss.xml", 15)
        posts = []
        for it in re.findall(r"<item>(.*?)</item>", x, re.S)[:15]:
            t = re.search(r"<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", it, re.S)
            l = re.search(r"<link>(.*?)</link>", it, re.S)
            d = re.search(r"<pubDate>(.*?)</pubDate>", it)
            if not (t and l):
                continue
            try:
                pd = datetime.strptime(d.group(1).strip()[:25], "%a, %d %b %Y %H:%M:%S").strftime("%Y-%m-%d")
            except Exception:
                pd = ""
            posts.append({"title": html.unescape(t.group(1)).strip(), "url": l.group(1).strip(), "date": pd})
        if posts:
            save("factset_insight", {"posts": posts,
                                     "desc": "FactSet Insight RSS(HubSpot 캐시 우회) — 최신 글 판별용, Chrome 불필요"})
    except Exception as e:
        print("  factset rss 실패(기존 유지):", repr(e)[:60])


# ── 5) ISM PMI (구글뉴스 헤드라인 파싱 — best effort) ──
def ism():
    out = load("ism_pmi", {})
    for k, q in (("mfg", "ISM Manufacturing PMI"), ("svc", "ISM Services PMI")):
        cands = gnews(q, hours=24 * 40, cap=10, lang="en") + gnews(q.replace("Manufacturing", "제조업").replace("Services", "서비스업"), hours=24 * 40, cap=10)
        for it in cands:
            # (2026-07-22 재발방지) 토픽 필터 — svc 쿼리 결과에 제조업 헤드라인이 섞여 svc 에 mfg 값이 복제되던 오염 방지
            if k == "svc" and not ("Services" in it["title"] or "서비스" in it["title"]): continue
            if k == "mfg" and not ("Manufacturing" in it["title"] or "제조업" in it["title"]): continue
            m = re.search(r"(\d{2}\.\d)\b", it["title"])
            mon = re.search(r"(1[0-2]|[1-9])월|January|February|March|April|May|June|July|August|September|October|November|December", it["title"])
            if m and ("ISM" in it["title"] or "PMI" in it["title"]):
                out[k] = {"value": float(m.group(1)), "headline": it["title"], "url": it["url"],
                          "news_date": it["date"], "month_hint": mon.group(0) if mon else ""}
                break
    save("ism_pmi", out if out else {"note": "미확보 — 에이전트 웹서치 폴백"})


# ── 6·7) IB 인사이트 풀(24h) ──
IBQ = {"ubs": "UBS CIO global markets", "goldman": "Goldman Sachs research forecast",
       "jpmorgan": "JPMorgan strategist markets", "morgan_stanley": "Morgan Stanley outlook markets",
       "blackrock": "BlackRock Investment Institute weekly"}


def ib():
    out = {}
    for k, q in IBQ.items():
        out[k] = gnews(q, hours=24, cap=6)   # (사용자 규칙) 24시간 이내 보도만 보유
    save("ib_insights", {"pool": out, "keep_hours": 24,
                         "desc": "IB 5사 하우스뷰 관련 최신 보도(24h) — GlobalSecuritiesAgent 1차 소스"})


# ── 8) 리밸런싱 모니터 ──
def rebalance():
    pool = (gnews("S&P 500 index changes constituents", 72, 8)
            + gnews("나스닥100 편입 편출", 72, 8) + gnews("Nasdaq-100 index add removed", 72, 8))
    seen, ded = set(), []
    for it in pool:
        k = re.sub(r"\W", "", it["title"])[:30]
        if k in seen:
            continue
        seen.add(k)
        ded.append(it)
    marker = ",".join(sorted(re.sub(r"\W", "", x["title"])[:16] for x in ded))[:200] or "none"
    save("rebalance_news", {"items": ded[:12], "change_marker": marker,
                            "desc": "지수변경 헤드라인 모니터 — 마커 변동시에만 IndexRebalanceAgent 발행"})


def main():
    want = sys.argv[1] if len(sys.argv) > 1 else "all"
    jobs = {"brokers3": brokers3, "calendar": calendar, "policy": policy, "factset": factset,
            "ism": ism, "ib": ib, "rebalance": rebalance}
    for name, fn in jobs.items():
        if want in ("all", name):
            try:
                fn()
            except Exception as e:
                print(f"[{name}] 실패(비차단):", repr(e)[:90])


if __name__ == "__main__":
    main()
