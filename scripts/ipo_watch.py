#!/usr/bin/env python3
"""패스트 엔트리 후보(대형 IPO)·지수 편입 뉴스 서버 자동 수집 (req8).

구글뉴스 RSS 로 매일 수집해 DB화한다. 보고서 실행 때는 이 목록을 바탕으로
AI 가 후보 판정만 하면 되므로 조사 시간이 줄어든다.
"""
import json, re, urllib.request, urllib.parse, html
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DB   = BASE / "data" / "db"

QUERIES = [
    ("대형 IPO 상장",        "ipo"),
    ("나스닥 상장 추진",      "ipo"),
    ("S&P500 편입",          "index"),
    ("나스닥100 편입",        "index"),
    ("지수 리밸런싱 편입 제외", "index"),
]

def rss(q):
    url = ("https://news.google.com/rss/search?q=" + urllib.parse.quote(q)
           + "&hl=ko&gl=KR&ceid=KR:ko")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as r:
        root = ET.fromstring(r.read())
    out = []
    for it in root.iter("item"):
        t  = html.unescape(it.findtext("title") or "")
        lk = it.findtext("link") or ""
        pd = it.findtext("pubDate") or ""
        try:
            dt = datetime.strptime(pd[:16].strip(), "%a, %d %b %Y").strftime("%Y-%m-%d")
        except Exception:
            dt = ""
        src = t.rsplit(" - ", 1)[-1] if " - " in t else ""
        ttl = t.rsplit(" - ", 1)[0] if " - " in t else t
        out.append({"title": ttl[:110], "src": src[:24], "date": dt, "url": lk})
    return out

def main():
    items, seen = [], set()
    for q, cat in QUERIES:
        try:
            for r in rss(q)[:15]:
                key = re.sub(r"\W", "", r["title"])[:40]
                if key in seen:
                    continue
                seen.add(key)
                r["cat"] = cat
                r["q"] = q
                items.append(r)
        except Exception as e:
            print(f"{q} 실패: {type(e).__name__}")
    items.sort(key=lambda r: r["date"], reverse=True)
    out = {"items": items[:60],
           "as_of": datetime.now().strftime("%Y-%m-%d %H:%M"),
           "marker": datetime.now().strftime("%Y-%m-%d"),
           "desc": "구글뉴스 RSS — 대형 IPO·지수 편입 관련 헤드라인, 서버 매일 수집"}
    (DB / "ipo_news.json").write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    print(f"ipo_news: {len(out['items'])}건 (ipo {sum(1 for i in items if i['cat']=='ipo')} · index {sum(1 for i in items if i['cat']=='index')})")

if __name__ == "__main__":
    main()
