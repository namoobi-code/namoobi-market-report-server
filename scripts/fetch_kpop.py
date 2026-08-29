#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fetch_kpop.py — K-POP 선행지표 수집 (2026-08-29 신설)

'K-POP 선행지표 검토'(2026-08-29) 결론을 구현한다. 엔터 4사 실적은 ① 앨범이 팔리고
② 그게 수출로 잡히고 ③ 분기 실적에 찍히는 순서라, 앞 두 단계가 실적 발표를 선행한다.
LLM 토큰 0 — 전부 무인증/기보유 키.

  ① 써클차트 주간 앨범 TOP100 — circlechart.kr/data/api/chart/album (무인증 POST 실측 ✓)
     주간 판매량(Album_CNT)을 아티스트→소속사 매핑으로 합산 = "소속사별 주간 앨범 판매량".
     초동(발매 첫 주)은 컴백 화력의 직접 측정치이자 분기 실적의 선행 변수.
  ② 음반 수출액 — 관세청 tradedata.go.kr, HS 8523491040 (월간·3년)
     ※ 4자리 8523 은 SSD·반도체 미디어가 섞여 연 250억$ 규모라 쓸 수 없다(실측).
       10자리 8523491040 = 2025년 3.02억$ 로 알려진 음반 수출 통계와 일치 — 이걸 쓴다.
     발표는 익월이라 분기 실적을 1~2개월 선행한다.
  ③ 유튜브 채널 구독자·누적조회수 — Data API v3 channels.list (keys/youtube.txt · 쿼터 1/건)
     레이블 4사 + 주요 그룹. 일간 누적해 증가분(Δ)을 본다 — 컴백 화력의 실시간 대리변수.
  ④ 엔터 종목 시세 — 야후 일봉 1년. 위 지표와 같은 화면에서 겹쳐 보기 위한 것.

산출: data/db/kpop.json (현재 상태) · data/db/kpop_hist.json (유튜브 일간 누적 400일)
cron: 20 6 * * *   (①②는 주/월 단위라 매일 돌려도 값은 가끔 바뀐다 — 무해)
"""
import json, re, time, urllib.request, urllib.parse
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DB   = BASE / "data" / "db"
OUT  = DB / "kpop.json"
HIST = DB / "kpop_hist.json"
KEYS = BASE / "keys"
UA   = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"}
KST  = timezone(timedelta(hours=9))

# ── 아티스트 → 소속사(상장사) 매핑 ────────────────────────────────────────────
#   써클차트 ARTIST_NAME 에 대한 부분일치 키워드. 레이블은 모회사로 귀속한다
#   (빅히트·플레디스·쏘스뮤직·어도어·빌리프랩 → 하이브 / SM·JYP·YG 동일).
#   ⚠ 지분 100%가 아닌 곳도 있으므로 '실적 방향'의 대리지표로만 쓸 것.
LABELS = [
    ("하이브", "352820", "#7c3aed", [
        "BTS", "방탄소년단", "정국", "JUNG KOOK", "지민", "JIMIN", "RM", "SUGA", "j-hope", "제이홉", "진 ", "JIN",
        "V ", "뷔", "TOMORROW X TOGETHER", "투모로우바이투게더", "TXT", "ENHYPEN", "엔하이픈",
        "SEVENTEEN", "세븐틴", "부석순", "BOYNEXTDOOR", "보이넥스트도어", "NewJeans", "뉴진스",
        "LE SSERAFIM", "르세라핌", "ILLIT", "아일릿", "&TEAM", "CORTIS", "코르티스", "KATSEYE",
        "TWS", "투어스", "fromis_9", "프로미스나인", "ZICO", "지코", "AtEEZ" ]),
    ("JYP",   "035900", "#0ea5e9", [
        "Stray Kids", "스트레이 키즈", "TWICE", "트와이스", "ITZY", "있지", "NMIXX", "엔믹스",
        "NiziU", "니쥬", "DAY6", "데이식스", "Xdinary Heroes", "엑스디너리 히어로즈",
        "KickFlip", "킥플립", "VCHA", "지수(JISOO of TWICE)", "나연", "지효", "미나", "채영", "쯔위" ]),
    ("에스엠", "041510", "#f59e0b", [
        "aespa", "에스파", "NCT", "엔시티", "RIIZE", "라이즈", "EXO", "엑소", "Red Velvet", "레드벨벳",
        "SHINee", "샤이니", "SUPER JUNIOR", "슈퍼주니어", "TVXQ", "동방신기", "WayV", "웨이션브이",
        "Girls' Generation", "소녀시대", "태연", "TAEYEON", "KEY", "백현", "BAEKHYUN", "도영", "DOYOUNG",
        "MARK", "마크", "Hearts2Hearts", "하츠투하츠" ]),
    ("와이지", "122870", "#ec4899", [
        "BLACKPINK", "블랙핑크", "지수", "JISOO", "제니", "JENNIE", "로제", "ROSÉ", "LISA", "리사",
        "BABYMONSTER", "베이비몬스터", "TREASURE", "트레저", "AKMU", "악뮤", "악동뮤지션",
        "WINNER", "위너", "BIGBANG", "빅뱅", "지드래곤", "G-DRAGON" ]),
]
OTHER = ("기타", "", "#94a3b8")   # 위 4사 외 (스타쉽·큐브·플레이엠·판타지오 등)

# ── 유튜브 채널 (레이블 4 + 주요 그룹) ────────────────────────────────────────
#   channelId 는 2026-08-29 search API 로 1회 확인해 상수화(이후 쿼터 소모 없음).
YT = [
    ("레이블", "하이브", "UC3IZKseVpdzPSBaWxBxundA", "HYBE LABELS"),
    ("레이블", "JYP",   "UCaO6TYtlC8U5ttz62hTrZgg", "JYP Entertainment"),
    ("레이블", "에스엠", "UCEf_Bc-KVd7onSeifS3py9g", "SMTOWN"),
    ("레이블", "와이지", "UCQi67q4kGdmnJaRzX81uK5g", "YG ENTERTAINMENT"),
    ("그룹",  "하이브", "UCLkAepWjdylmXSltofFvsYQ", "BANGTANTV (BTS)"),
    ("그룹",  "하이브", "UCfkXDY7vwkcJ8ddFGz8KusA", "SEVENTEEN"),
    ("그룹",  "하이브", "UCArLZtok93cO5R9RI4_Y5Jw", "ENHYPEN"),
    ("그룹",  "하이브", "UCtiObj3CsEAdNU6ZPWDsddQ", "TOMORROW X TOGETHER"),
    ("그룹",  "하이브", "UCs-QBT4qkj_YiQw1ZntDO3g", "LE SSERAFIM"),
    ("그룹",  "하이브", "UCMki_UkHb4qSc0qyEcOHHJw", "NewJeans"),
    ("그룹",  "JYP",   "UC9rMiEjNaCSsebs31MRDCRA", "Stray Kids"),
    ("그룹",  "JYP",   "UCzgxx_DM2Dcb9Y1spb9mUJA", "TWICE"),
    ("그룹",  "JYP",   "UCDhM2k2Cua-JdobAh5moMFg", "ITZY"),
    ("그룹",  "에스엠", "UC9GtSLeksfK4yuJ_g1lgQbg", "aespa"),
    ("그룹",  "와이지", "UCOmHUn--16B90oW2L6FRR3A", "BLACKPINK"),
    ("그룹",  "기타",   "UCYDmx2Sfpnaxg488yBpZIGg", "STARSHIP (IVE)"),
]

# ── 연동 종목 (야후 심볼, 표시명, 연결 논리) ─────────────────────────────────
STOCKS = [
    ("352820.KS", "하이브",   "직결", "앨범 판매·음반 수출·글로벌 스트리밍 — 4사 중 해외 비중 최대"),
    ("035900.KQ", "JYP Ent.", "직결", "스키즈·트와이스 컴백 주기가 분기 실적을 좌우"),
    ("041510.KQ", "에스엠",   "직결", "에스파·NCT — 앨범 판매량 비중이 큰 구조"),
    ("122870.KQ", "와이지",   "직결", "블핑 완전체 활동 여부가 실적 진폭을 결정"),
    ("376300.KQ", "디어유",   "팬덤", "버블 구독자 = 팬덤 활동지표와 가장 직결(유튜브 구독 증가율로 대용)"),
    ("035760.KQ", "CJ ENM",   "간접", "음악 부문·콘서트 제작 — 순수 K-POP 노출은 희석"),
    ("LYV",       "Live Nation", "공연", "K-POP 북미·글로벌 투어 주관 — 공연 매출 사이클"),
    ("SPOT",      "Spotify",  "스트리밍", "글로벌 스트리밍 파이 — K-POP 소비의 최종 창구"),
]

# ══════════════════════════════════════════════════════════════════════════
def get(u, to=25, data=None, hdr=None):
    h = dict(UA); h.update(hdr or {})
    return urllib.request.urlopen(urllib.request.Request(u, data=data, headers=h), timeout=to).read()

def label_of(artist):
    a = (artist or "").upper()
    for nm, code, color, keys in LABELS:
        for k in keys:
            if k.upper() in a:
                return nm
    return OTHER[0]

# ── ① 써클차트 주간 앨범 ────────────────────────────────────────────────────
def circle_week(year, week):
    """해당 주차 앨범 TOP100 → [{rank,artist,album,cnt,total,label}]"""
    body = urllib.parse.urlencode({
        "nationGbn": "T", "termGbn": "week", "hitYear": str(year), "targetTime": str(week),
        "yearTime": "3", "curUrl": "/page_chart/album.circle", "PageSize": "100"}).encode()
    j = json.loads(get("https://circlechart.kr/data/api/chart/album", data=body,
                       hdr={"Content-Type": "application/x-www-form-urlencoded"}).decode("utf-8", "replace"))
    L = j.get("List") or {}
    rows = []
    for k in sorted(L, key=lambda x: int(x)):
        x = L[k]
        try:
            cnt = int((x.get("Album_CNT") or "0").replace(",", ""))
        except Exception:
            cnt = 0
        try:
            tot = int((x.get("Total_CNT") or "0").replace(",", ""))
        except Exception:
            tot = 0
        art = (x.get("ARTIST_NAME") or "").strip()
        rows.append({"rank": int(x.get("SERVICE_RANKING") or 0), "artist": art,
                     "album": (x.get("ALBUM_NAME") or "").strip(), "cnt": cnt, "total": tot,
                     "new": (x.get("RankStatus") or "") == "new", "label": label_of(art)})
    return [r for r in rows if r["rank"]]

def collect_circle(nweeks=13):
    """최근 nweeks 주 — 주차별 소속사 합산 + 최신주 TOP20"""
    now = datetime.now(KST)
    weeks, cur = [], now
    while len(weeks) < nweeks:
        y, w, _ = cur.isocalendar()
        weeks.append((y, w))
        cur -= timedelta(days=7)
    weeks.reverse()
    series, latest, ok = [], [], 0
    for y, w in weeks:
        try:
            rows = circle_week(y, w)
        except Exception as e:
            print(f"  ⚠ 써클 {y}-{w}주 실패: {repr(e)[:70]}", flush=True)
            rows = []
        if rows:
            ok += 1
            latest = rows
        agg = {}
        for r in rows:
            agg[r["label"]] = agg.get(r["label"], 0) + r["cnt"]
        series.append({"y": y, "w": w, "sum": sum(agg.values()), "by": agg})
        time.sleep(0.5)
    # 집계 전인 주(당주)는 합계 0 으로 내려온다 — 0 막대를 그리면 '급감'으로 오독되므로 잘라낸다(실측).
    while series and series[-1]["sum"] == 0:
        series.pop()
    top = sorted(latest, key=lambda r: r["rank"])[:20]
    print(f"  써클차트: {ok}/{len(weeks)}주 · 최신주 TOP{len(top)}", flush=True)
    return {"series": series, "top": top,
            "latest_week": (f"{series[-1]['y']}년 {series[-1]['w']}주" if series else "")}

# ── ② 음반 수출 (관세청) ────────────────────────────────────────────────────
TRADE_URL = "https://tradedata.go.kr/cts/hmpg/retrieveTrade.do"
TRADE_H   = {"Content-Type": "application/x-www-form-urlencoded",
             "Referer": "https://tradedata.go.kr/cts/index.do"}

def collect_export(hs="8523491040", years=3):
    now = datetime.now(KST)
    fr  = f"{now.year - years}{now.month:02d}"
    to  = f"{now.year}{now.month:02d}"
    body = urllib.parse.urlencode({
        "tradeKind": "ETS_MNK_1020000A", "priodKind": "MON", "priodFr": fr, "priodTo": to,
        "statsBase": "acptDd", "ttwgTpcd": "1000", "showPagingLine": "100",
        "hsSgnGrpCol": "HS10_SGN", "hsSgnWhrCol": "HS10_SGN", "hsSgn": hs}).encode()
    j = json.loads(get(TRADE_URL, data=body, hdr=TRADE_H))
    d = {}
    for x in j.get("items") or []:
        p = (x.get("priodTitle") or "").strip()
        if not re.match(r"^\d{4}\.\d{2}$", p):
            continue
        v = (x.get("expUsdAmt") or "").replace(",", "").strip()
        d[p] = int(v) if v else 0
    ms = sorted(d)
    print(f"  음반수출(HS {hs}): {len(ms)}개월 · 최근 {ms[-1] if ms else '-'} {d.get(ms[-1],0):,}천$", flush=True)
    return {"hs": hs, "months": ms, "exp": [d[m] for m in ms]}

# ── ③ 유튜브 채널 통계 ──────────────────────────────────────────────────────
def collect_youtube():
    kf = KEYS / "youtube.txt"
    if not kf.exists():
        print("  ⚠ keys/youtube.txt 없음 — 유튜브 생략", flush=True)
        return []
    key = kf.read_text(encoding="utf-8").strip()
    ids = [c[2] for c in YT]
    out = {}
    for i in range(0, len(ids), 50):
        u = ("https://www.googleapis.com/youtube/v3/channels?part=statistics,snippet&id="
             + ",".join(ids[i:i+50]) + "&key=" + key)
        try:
            d = json.loads(get(u))
        except Exception as e:
            print(f"  ⚠ 유튜브 실패: {repr(e)[:70]}", flush=True)
            return []
        for it in d.get("items", []):
            s = it.get("statistics", {})
            out[it["id"]] = {"sub": int(s.get("subscriberCount") or 0),
                             "view": int(s.get("viewCount") or 0)}
    rows = []
    for kind, lab, cid, nm in YT:
        st = out.get(cid)
        if st:
            rows.append({"kind": kind, "label": lab, "id": cid, "name": nm, **st})
    print(f"  유튜브: {len(rows)}/{len(YT)}채널", flush=True)
    return rows

# ── ④ 엔터 종목 시세 (야후 일봉 1년) ────────────────────────────────────────
def yahoo(sym, rng="1y"):
    u = (f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(sym)}"
         f"?range={rng}&interval=1d")
    j = json.loads(get(u, to=20))
    r = (j.get("chart") or {}).get("result") or []
    if not r:
        return None
    r = r[0]
    ts = r.get("timestamp") or []
    cl = ((r.get("indicators") or {}).get("quote") or [{}])[0].get("close") or []
    pts = [(t, c) for t, c in zip(ts, cl) if c is not None]
    if not pts:
        return None
    closes = [c for _, c in pts]
    meta = r.get("meta") or {}
    return {"cur": closes[-1], "ccy": meta.get("currency") or "",
            "d1": pct(closes[-2], closes[-1]) if len(closes) > 1 else None,
            "m1": pct(closes[-22], closes[-1]) if len(closes) > 22 else None,
            "m3": pct(closes[-64], closes[-1]) if len(closes) > 64 else None,
            "y1": pct(closes[0], closes[-1]),
            "spark": [round(c, 2) for c in closes[::max(1, len(closes)//60)]][-60:]}

def pct(a, b):
    try:
        return round((b / a - 1) * 100, 1) if a else None
    except Exception:
        return None

def collect_stocks():
    rows = []
    for sym, nm, tag, why in STOCKS:
        q = None
        try:
            q = yahoo(sym)
        except Exception as e:
            print(f"  ⚠ {nm}({sym}) 시세 실패: {repr(e)[:50]}", flush=True)
        rows.append({"sym": sym, "name": nm, "tag": tag, "why": why, **(q or {})})
        time.sleep(0.25)
    print(f"  시세: {sum(1 for r in rows if r.get('cur'))}/{len(STOCKS)}종목", flush=True)
    return rows

# ── 이력 누적 (유튜브 일간 Δ 계산용) ────────────────────────────────────────
def push_hist(yt):
    try:
        h = json.loads(HIST.read_text(encoding="utf-8"))
    except Exception:
        h = {"days": []}
    today = datetime.now(KST).strftime("%Y-%m-%d")
    h["days"] = [d for d in h.get("days", []) if d.get("d") != today]
    h["days"].append({"d": today, "yt": {r["id"]: [r["sub"], r["view"]] for r in yt}})
    h["days"] = sorted(h["days"], key=lambda x: x["d"])[-400:]
    HIST.write_text(json.dumps(h, ensure_ascii=False), encoding="utf-8")
    return h

def yt_delta(yt, h):
    """구독자 7일·30일 증가분 — 이력이 없으면 None(추정 금지)"""
    days = h.get("days", [])
    def at(back):
        if len(days) <= back:
            return None
        return days[-1 - back].get("yt") or {}
    for r in yt:
        for back, k in ((7, "d7"), (30, "d30")):
            prev = at(back)
            v = (prev or {}).get(r["id"])
            r[k] = (r["sub"] - v[0]) if v else None
    return yt

# ══════════════════════════════════════════════════════════════════════════
def main():
    print("[kpop] 수집 시작", flush=True)
    circle = collect_circle()
    try:
        export = collect_export()
    except Exception as e:
        print(f"  ⚠ 수출 실패: {repr(e)[:70]}", flush=True)
        export = {"hs": "8523491040", "months": [], "exp": []}
    yt = collect_youtube()
    if yt:
        yt = yt_delta(yt, push_hist(yt))
    stocks = collect_stocks()
    DB.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "as_of": datetime.now(KST).strftime("%Y-%m-%d %H:%M"),
        "labels": [{"name": n, "code": c, "color": col} for n, c, col, _ in LABELS]
                  + [{"name": OTHER[0], "code": OTHER[1], "color": OTHER[2]}],
        "circle": circle, "export": export, "youtube": yt, "stocks": stocks,
    }, ensure_ascii=False), encoding="utf-8")
    print(f"[kpop] ✅ → {OUT}", flush=True)

if __name__ == "__main__":
    main()
