#!/usr/bin/env python3
"""보고서 사전수집 v1 (req33) — 실행 때 조사하던 것을 서버가 매일 미리 DB화.

  ① M7 실적 전망(3.1.7)  — Yahoo earningsTrend: EPS·매출 추정, 리비전(7/30/60일 전), 애널 수
  ② 뉴스 헤드라인 풀(1장) — 구글뉴스 RSS 주제별. 보고서는 이 풀에서 Top10 선별·요약만.
  ③ FactSet Earnings Insight(3.1.6) — insight.factset.com 최신 발간물 제목·URL·PDF
  ④ ETF 시세표(3.3.1)   — Yahoo v7 벌크: 미국 주요 ETF 현재가·기간수익률

FMP 키가 서버에 없어 M7·ETF 는 Yahoo 무인증 경로를 쓴다 (ta_screen 헬퍼 재사용).
"""
import json, re, sys, os, html, urllib.parse, urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DB   = BASE / "data" / "db"
sys.path.insert(0, str(BASE / "scripts"))
import ta_screen as T

M7 = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA"]

ETFS = ["SPY","QQQ","DIA","IWM","VTI","XLK","XLF","XLE","XLV","XLI","XLP","XLU","XLB","XLRE","XLC","XLY",
        "SMH","SOXX","ARKK","IGV","XBI","ITA","PAVE","URA","LIT","JETS","XHB",
        "SCHD","VIG","JEPI","NOBL","GLD","SLV","TLT","IEF","HYG","LQD","BIL",
        "EFA","EEM","VEA","VWO","FEZ","EWJ","EWY","INDA","FXI","MCHI","KWEB","ARGT","EWZ","EWW","EWC","EWA","KSA","TUR"]

NEWS_TOPICS = [
    ("증시·매크로", "미국 증시 연준 금리"),
    ("반도체·AI",   "반도체 AI 엔비디아 HBM"),
    ("한국 증시",   "코스피 외국인 순매수"),
    ("빅테크",      "빅테크 실적 MS 아마존 구글 메타"),
    ("원자재·환율", "유가 금값 달러 환율"),
    ("암호화폐",    "비트코인 암호화폐"),
]

def save(name, obj):
    obj["as_of"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    obj["marker"] = datetime.now().strftime("%Y-%m-%d")
    (DB / f"{name}.json").write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")

# ── ① M7 실적 전망 ────────────────────────────────────────
def m7_outlook(op, crumb):
    out = []
    for sym in M7:
        try:
            u = (f"https://query2.finance.yahoo.com/v10/finance/quoteSummary/{sym}"
                 f"?modules=earningsTrend%2CfinancialData&crumb={urllib.parse.quote(crumb)}")
            j = T.jget(u, opener=op, timeout=15)
            r0 = j["quoteSummary"]["result"][0]
            fd = r0.get("financialData") or {}
            row = {"sym": sym,
                   "price": (fd.get("currentPrice") or {}).get("raw"),
                   "target": (fd.get("targetMeanPrice") or {}).get("raw"),
                   "rec": fd.get("recommendationKey"),
                   "analysts": (fd.get("numberOfAnalystOpinions") or {}).get("raw"),
                   "trend": []}
            for t in (r0.get("earningsTrend") or {}).get("trend", []):
                if t.get("period") not in ("0q", "+1q", "0y", "+1y"):
                    continue
                ep = t.get("epsTrend") or {}
                row["trend"].append({
                    "period": t["period"], "end": t.get("endDate"),
                    "eps": (ep.get("current") or {}).get("raw"),
                    "eps_7d": (ep.get("7daysAgo") or {}).get("raw"),
                    "eps_30d": (ep.get("30daysAgo") or {}).get("raw"),
                    "eps_60d": (ep.get("60daysAgo") or {}).get("raw"),
                    "rev": ((t.get("revenueEstimate") or {}).get("avg") or {}).get("raw"),
                    "growth": (t.get("growth") or {}).get("raw")})
            out.append(row)
        except Exception as e:
            print(f"  m7 {sym} 실패: {type(e).__name__}")
    if out:
        save("m7_estimates", {"rows": out,
             "desc": "Yahoo earningsTrend — EPS·매출 컨센서스와 7/30/60일 전 값(리비전 방향), 목표주가·투자의견"})
        print(f"m7_estimates: {len(out)}종목")

# ── ② 뉴스 헤드라인 풀 ────────────────────────────────────
def news_pool():
    topics = {}
    for cat, q in NEWS_TOPICS:
        try:
            u = ("https://news.google.com/rss/search?q=" + urllib.parse.quote(q)
                 + "&hl=ko&gl=KR&ceid=KR:ko")
            req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
            root = ET.fromstring(urllib.request.urlopen(req, timeout=15).read())
            items = []
            for it in list(root.iter("item"))[:15]:
                t = html.unescape(it.findtext("title") or "")
                src = t.rsplit(" - ", 1)[-1] if " - " in t else ""
                items.append({"title": t.rsplit(" - ", 1)[0][:110], "src": src[:24],
                              "url": it.findtext("link") or "",
                              "pub": (it.findtext("pubDate") or "")[:22]})
            topics[cat] = items
        except Exception as e:
            print(f"  news {cat} 실패: {type(e).__name__}")
    if topics:
        save("news_pool", {"topics": topics,
             "desc": "구글뉴스 RSS 주제별 헤드라인 풀 — 보고서 1장은 여기서 Top10 선별·요약만 (재검색 불필요)"})
        print(f"news_pool: {sum(len(v) for v in topics.values())}건 · {len(topics)}주제")

# ── ③ FactSet Earnings Insight ────────────────────────────
def factset():
    try:
        req = urllib.request.Request("https://insight.factset.com/topic/earnings",
                                     headers={"User-Agent": "Mozilla/5.0"})
        h = urllib.request.urlopen(req, timeout=15).read().decode(errors="replace")
        links = re.findall(r'href="(https://insight\.factset\.com/[a-z0-9-]{20,})"', h)
        posts, seen = [], set()
        for lk in links:
            if lk in seen:
                continue
            seen.add(lk)
            title = lk.rsplit("/", 1)[-1].replace("-", " ").title()
            posts.append({"title": title, "url": lk})
            if len(posts) >= 5:
                break
        if posts:
            save("factset_insight", {"posts": posts, "topic_url": "https://insight.factset.com/topic/earnings",
                 "desc": "FactSet Earnings Insight 최신 발간물 (주간 금요일 발행)"})
            print(f"factset: {posts[0]['title'][:50]}")
    except Exception as e:
        print(f"  factset 실패: {type(e).__name__}")

# ── ④ ETF 시세표 ──────────────────────────────────────────
def etf_quotes(op, crumb):
    fields = ("symbol,shortName,regularMarketPrice,regularMarketChangePercent,"
              "fiftyDayAverageChangePercent,twoHundredDayAverageChangePercent,"
              "fiftyTwoWeekChangePercent,ytdReturn,trailingAnnualDividendYield")
    u = ("https://query2.finance.yahoo.com/v7/finance/quote?symbols=" + ",".join(ETFS)
         + "&fields=" + fields + "&crumb=" + urllib.parse.quote(crumb))
    j = T.jget(u, opener=op, timeout=20)
    rows = []
    for q in (j.get("quoteResponse") or {}).get("result") or []:
        rows.append({"sym": q.get("symbol"), "name": (q.get("shortName") or "")[:36],
                     "px": q.get("regularMarketPrice"), "d1": q.get("regularMarketChangePercent"),
                     "vs50": q.get("fiftyDayAverageChangePercent"),
                     "vs200": q.get("twoHundredDayAverageChangePercent"),
                     "w52": q.get("fiftyTwoWeekChangePercent"), "ytd": q.get("ytdReturn"),
                     "dvd": q.get("trailingAnnualDividendYield")})
    if rows:
        save("etf_quotes", {"rows": rows,
             "desc": "미국 주요 ETF 시세 스냅샷 (Yahoo 벌크) — 3.3.1 표의 기초 데이터, 서버 매일 수집"})
        print(f"etf_quotes: {len(rows)}종목")

def main():
    if "--news" in sys.argv:            # 뉴스만 (매시 갱신용 — 최신 헤드라인 놓치지 않도록)
        news_pool(); return
    op, crumb = T.yahoo_opener()
    for name, fn in (("m7", lambda: m7_outlook(op, crumb)), ("news", news_pool),
                     ("factset", factset), ("etf", lambda: etf_quotes(op, crumb))):
        try:
            fn()
        except Exception as e:
            print(f"{name} 실패: {type(e).__name__} {e}")

if __name__ == "__main__":
    main()
