#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""trends_collect.py — 무토큰 일일 트렌드 수집 (2026-08-06 신설 · 매일 05:50).

'트렌드 조사 및 자동화 검토' 보고서(2026-08-06) 권고안 구현 — LLM 토큰 0:
  ① 구글 급상승(KR·US): 공식 RSS trends.google.com/trending/rss?geo= (무인증 실측 ✓)
  ② 네이버 쇼핑인사이트: datalab.naver.com 카테고리 인기검색어 XHR (무인증 실측 ✓, TOP20)
     ※ 네이버 실검은 2021 폐지 — 쇼핑 인기검색어가 유일한 공식 랭킹
  ③ 유튜브 인기(KR·US): Data API v3 mostPopular — keys/youtube.txt 존재 시에만
     (trending 웹페이지는 폐지되어 스크래핑 불가 실측 확인)
  ④ 주간 자체 집계: 일간 수집을 trends_hist.json 에 누적(30일) → 최근 7일 등장일수 랭킹
     (구글·유튜브 모두 공식 주간 랭킹 부재 — 보고서 권고안)
인스타그램은 공개 API 부재로 제외(보고서 판정: 무토큰 불가 — 주간 LLM 큐레이션 별도).
산출: data/db/trends.json · trends_hist.json
cron: 50 5 * * *
"""
import json, re, time, urllib.request, urllib.parse
from datetime import datetime, timedelta
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "data" / "db" / "trends.json"
HIST = BASE / "data" / "db" / "trends_hist.json"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

def get(u, to=20, data=None, hdr=None):
    h = dict(UA); h.update(hdr or {})
    return urllib.request.urlopen(urllib.request.Request(u, data=data, headers=h), timeout=to).read()

def google_rss(geo):
    """[{kw, tf(대략 검색량), news, url}] — 공식 급상승 RSS"""
    t = get(f"https://trends.google.com/trending/rss?geo={geo}").decode("utf-8", "ignore")
    out = []
    for m in re.finditer(r"<item>(.*?)</item>", t, re.S):
        it = m.group(1)
        kw = re.search(r"<title>([^<]+)</title>", it)
        tf = re.search(r"approx_traffic>([^<]+)<", it)
        nw = re.search(r"news_item_title>([^<]+)<", it)
        nu = re.search(r"news_item_url>([^<]+)<", it)
        if kw:
            out.append({"kw": kw.group(1).strip(), "tf": (tf.group(1).strip() if tf else ""),
                        "news": (nw.group(1).strip()[:90] if nw else ""),
                        "url": (nu.group(1).strip() if nu else "")})
    return out[:20]

NAVER_CATS = [("50000000", "패션의류"), ("50000002", "화장품/미용"), ("50000003", "디지털/가전"),
              ("50000006", "식품"), ("50000007", "스포츠/레저"), ("50000008", "생활/건강")]

def naver_shop(cid):
    """카테고리 인기검색어 TOP20 — datalab 웹 XHR (무인증 실측)"""
    ed = datetime.now().date() - timedelta(days=1)
    sd = ed - timedelta(days=6)
    body = urllib.parse.urlencode({"cid": cid, "timeUnit": "date", "startDate": str(sd), "endDate": str(ed),
                                   "age": "", "gender": "", "device": "", "page": "1", "count": "20"}).encode()
    j = json.loads(get("https://datalab.naver.com/shoppingInsight/getCategoryKeywordRank.naver", data=body,
                       hdr={"Referer": "https://datalab.naver.com/shoppingInsight/sCategory.naver",
                            "Content-Type": "application/x-www-form-urlencoded"}))
    return [r.get("keyword") for r in (j.get("ranks") or [])][:20]

def tr_ko(text):
    """(2026-08-06) 무토큰 한글 번역 — 구글 gtx 무인증 엔드포인트 (실측 ✓). 글로벌 항목 한글 열용."""
    if not text:
        return ""
    try:
        u = ("https://translate.googleapis.com/translate_a/single?"
             + urllib.parse.urlencode({"client": "gtx", "sl": "auto", "tl": "ko", "dt": "t", "q": text[:300]}))
        j = json.loads(get(u, 12))
        return "".join(x[0] for x in j[0] if x and x[0])[:120]
    except Exception:
        return ""

# (2026-08-06) 네이버 데이터랩 장기 시계열 — 키워드 바스켓 (보고서 '네이버 시즌/장기' 구현)
#   공식 오픈API(무료 일 1,000콜) — keys/naver_datalab.txt 에 "클라이언트ID:시크릿" 저장 시 활성화.
#   웹 XHR(qcHash)은 봇 차단으로 기각(실측). 랭킹이 아니라 지정 키워드 상대비교라 바스켓 사전 정의(보고서 권고).
BASKET = [("AI", ["AI", "인공지능", "챗GPT"]), ("주식투자", ["주식", "미국주식"]),
          ("금테크", ["금값", "금투자"]), ("부동산", ["아파트 매매", "부동산"]),
          ("전기차", ["전기차", "테슬라"]), ("다이어트", ["다이어트", "위고비"]),
          ("해외여행", ["해외여행", "항공권"]), ("캠핑", ["캠핑", "캠핑용품"]),
          ("K뷰티", ["선크림", "쿠션"]), ("위스키", ["위스키", "하이볼"])]

def naver_datalab(cid, csec):
    """5년 월간 — {name:[..ratio]}, 라벨은 첫 그룹 기준"""
    ed = datetime.now().date().replace(day=1) - timedelta(days=1)
    sd = ed.replace(year=ed.year-5, day=1)
    out, labels = {}, []
    for i in range(0, len(BASKET), 5):                  # 콜당 최대 5그룹
        body = json.dumps({"startDate": str(sd), "endDate": str(ed), "timeUnit": "month",
                           "keywordGroups": [{"groupName": n, "keywords": k} for n, k in BASKET[i:i+5]]}).encode()
        j = json.loads(get("https://openapi.naver.com/v1/datalab/search", data=body,
                           hdr={"X-Naver-Client-Id": cid, "X-Naver-Client-Secret": csec,
                                "Content-Type": "application/json"}))
        for g in j.get("results") or []:
            pts = {p["period"][:7]: p["ratio"] for p in g.get("data") or []}
            if not labels:
                labels = sorted(pts)
            out[g["title"]] = [pts.get(l) for l in labels]
        time.sleep(0.3)
    return labels, out

def youtube_popular(region, key):
    """공식 Data API mostPopular — [{id,t,ch,v}]"""
    u = ("https://www.googleapis.com/youtube/v3/videos?part=snippet,statistics&chart=mostPopular"
         f"&regionCode={region}&maxResults=20&key={key}")
    j = json.loads(get(u))
    out = []
    for x in j.get("items") or []:
        sn, st = x.get("snippet") or {}, x.get("statistics") or {}
        out.append({"id": x.get("id"), "t": (sn.get("title") or "")[:90],
                    "ch": (sn.get("channelTitle") or "")[:40],
                    "v": int(st.get("viewCount") or 0)})
    return out

def main():
    now = datetime.now()
    d8 = now.strftime("%Y%m%d")
    data = {"asof": now.strftime("%Y-%m-%d %H:%M")}
    # ① 구글
    for geo, k in (("KR", "g_kr"), ("US", "g_us")):
        try:
            data[k] = google_rss(geo)
            print(f"[trends] 구글 {geo}: {len(data[k])}건")
        except Exception as e:
            data[k] = []; print(f"[trends] 구글 {geo} 실패: {repr(e)[:60]}")
        time.sleep(0.5)
    # ①-2 글로벌 항목 한글 열 — gtx 무토큰 번역 (US 키워드·뉴스)
    for x in data.get("g_us") or []:
        x["ko"] = tr_ko(x["kw"])
        x["news_ko"] = tr_ko(x["news"]) if x.get("news") else ""
        time.sleep(0.15)
    print(f"[trends] 구글 US 한글화 {sum(1 for x in data['g_us'] if x.get('ko'))}건")
    # ② 네이버 쇼핑
    ns = {}
    for cid, nm in NAVER_CATS:
        try:
            ns[nm] = naver_shop(cid)
        except Exception as e:
            ns[nm] = []; print(f"[trends] 네이버 {nm} 실패: {repr(e)[:60]}")
        time.sleep(0.4)
    data["naver_shop"] = ns
    print(f"[trends] 네이버 쇼핑: {sum(1 for v in ns.values() if v)}/{len(NAVER_CATS)}개 분야")
    # ③ 유튜브 (키 있을 때만)
    ykey = None
    kf = BASE / "keys" / "youtube.txt"
    if kf.exists():
        ykey = kf.read_text().strip() or None
    data["yt_enabled"] = bool(ykey)
    for rg, k in (("KR", "y_kr"), ("US", "y_us")):
        data[k] = []
        if ykey:
            try:
                data[k] = youtube_popular(rg, ykey)
                print(f"[trends] 유튜브 {rg}: {len(data[k])}건")
            except Exception as e:
                print(f"[trends] 유튜브 {rg} 실패: {repr(e)[:60]}")
    # 유튜브 US 제목 한글 열
    for x in data.get("y_us") or []:
        x["ko"] = tr_ko(x["t"])
        time.sleep(0.15)
    # ③-2 네이버 데이터랩 장기 시계열 (키 있을 때만)
    data["nv_enabled"] = False
    nf = BASE / "keys" / "naver_datalab.txt"
    if nf.exists() and ":" in nf.read_text():
        cid, csec = nf.read_text().strip().split(":", 1)
        try:
            labels, series = naver_datalab(cid.strip(), csec.strip())
            data["nv_trend"] = {"labels": labels, "series": series}
            data["nv_enabled"] = True
            print(f"[trends] 데이터랩 바스켓 {len(series)}그룹 · {len(labels)}개월")
        except Exception as e:
            print(f"[trends] 데이터랩 실패: {repr(e)[:70]}")
    # ④ 누적 + 주간 자체 집계 (등장일수 — 여러 날 랭킹에 오른 키워드가 '진짜' 주간 트렌드)
    hist = {}
    try:
        hist = json.loads(HIST.read_text(encoding="utf-8")).get("days") or {}
    except Exception:
        pass
    hist[d8] = {"g_kr": [x["kw"] for x in data["g_kr"]], "g_us": [x["kw"] for x in data["g_us"]],
                "y_kr": [(x["ch"] or x["t"]) for x in data["y_kr"]],
                "y_us": [(x["ch"] or x["t"]) for x in data["y_us"]]}
    cut = (now - timedelta(days=30)).strftime("%Y%m%d")
    hist = {k: v for k, v in hist.items() if k >= cut}
    HIST.write_text(json.dumps({"days": hist}, ensure_ascii=False), encoding="utf-8")
    wk_cut = (now - timedelta(days=7)).strftime("%Y%m%d")
    wk = {}
    for key in ("g_kr", "g_us", "y_kr", "y_us"):
        cnt = {}
        for d, v in hist.items():
            if d >= wk_cut:
                for kw in v.get(key) or []:
                    cnt[kw] = cnt.get(kw, 0) + 1
        wk[key] = sorted(cnt.items(), key=lambda x: -x[1])[:15]
    data["weekly"] = wk
    data["hist_days"] = len([d for d in hist if d >= wk_cut])
    OUT.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    print(f"[trends] ✅ 저장 → {OUT} (주간 누적 {data['hist_days']}일치)")

if __name__ == "__main__":
    main()
