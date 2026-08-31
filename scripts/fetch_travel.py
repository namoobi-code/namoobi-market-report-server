#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fetch_travel.py — ✈️ 여행 시소(Travel Seesaw) 정본 (2026-08-31 신설)

한국인이 나가는 여행(아웃바운드)과 외국인이 들어오는 여행(인바운드)은 하나의 테마가 아니라 시소다.
원화 약세 → 외국인에겐 한국이 싸짐(인바운드↑) / 한국인에겐 해외가 비싸짐(아웃바운드↓).
그래서 하나투어와 호텔신라를 같은 화면에 놓고 '반대로' 읽는다.

선행 사슬:
  ① 의향(검색)  네이버 데이터랩(아웃)·구글 트렌즈(인)          T+0~7일
  ② 예약(공항)  공항 예상승객·인천 입출국장 승객예고            T+0(미래시점 포함)
  ③ 지출(국가)  ECOS 여행수입(외국인 지출)·여행지급(한국인 지출)  T+45일
  ④ 실적        분기 실적                                      T+90일

수집(전부 무인증·무료·stdlib):
  · 한국공항공사 일별 예상승객   apis.data.go.kr/B551178/airport-daily-expect-passenger/info
      schDate=YYYYMMDD, numOfRows≤100(200 이상은 HTTP_ERROR). 필드 TOF(I=국제/D=국내)·AOD(A=도착/D=출발)
      → 국제 도착=인바운드, 국제 출발=아웃바운드로 분해
  · 인천공항 승객예고(출·입국장별) apis.data.go.kr/B551177/passgrAnncmt/getPassgrAnncmt
      당일 25시간치만 반환 → 매일 누적 필수. t1eg*/t2eg*=입국장(인바운드), t1dg*/t2dg*=출국장(아웃바운드)
  · 구글 트렌즈  ⚠ 쿠키 워밍업(google.com 선방문 → NID)이 없으면 429. 있으면 200.
      explore → TIMESERIES token → widgetdata/multiline. 국가별 현지어 키워드 주간 53점.
  · 네이버 데이터랩 검색어 트렌드(아웃바운드 의향) — SECURITY/naver_datalab.txt "id:secret"
  · ECOS 301Y013 2C1000(여행수입)·2C0000(여행수지) → 여행지급 = 수입 − 수지
  · 야후 chart v8 — 연동 종목 주가·환율·WTI

산출: data/db/travel.json  (+ 이력 data/db/travel_hist.json — 공항 일별 누적)
cron: 50 6 * * *
"""
import json, subprocess, time, glob, os, sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DB   = BASE / "data" / "db"
OUT  = DB / "travel.json"
HIST = DB / "travel_hist.json"
KST  = timezone(timedelta(hours=9))
UA   = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
JAR  = "/tmp/nmr_gt.jar"

# ── 연동 종목
OUTB = [("하나투어","039130.KS"),("모두투어","080160.KQ"),("노랑풍선","104620.KQ"),("참좋은여행","094850.KQ"),
        ("제주항공","089590.KS"),("진에어","272450.KS"),("티웨이항공","091810.KS"),("대한항공","003490.KS")]
INB  = [("호텔신라","008770.KS"),("신세계","004170.KS"),("현대백화점","069960.KS"),("롯데쇼핑","023530.KS"),
        ("파라다이스","034230.KS"),("GKL","114090.KS"),("글로벌텍스프리","204620.KQ"),("아모레퍼시픽","090430.KS")]
FX   = [("원/엔(100엔)","JPYKRW=X"),("원/위안","CNYKRW=X"),("원/달러","KRW=X"),("WTI","CL=F")]

# 구글 트렌즈 — 인바운드: 방한 수요 상위국 현지어로 '한국 여행' 검색
#   ⚠ 중국 본토는 구글 자체가 차단이라 검색 프록시가 성립하지 않는다 → 인천 노선 공급·카지노 매출로 대체
GT_IN  = [("일본","JP","ja","韓国旅行"),("대만","TW","zh-TW","韓國旅遊"),
          ("홍콩","HK","zh-TW","韓國旅遊"),("태국","TH","th","เที่ยวเกาหลี"),
          ("베트남","VN","vi","du lịch hàn quốc"),("미국","US","en","korea travel")]
# 아웃바운드: 한국인의 해외여행 의향 (네이버 데이터랩 API 는 앱 scope 미승인 → 트렌즈로 통일,
#   양쪽을 같은 소스로 재면 시소 비교가 정합적이다)
GT_OUT = [("해외여행","KR","ko","해외여행"),("항공권","KR","ko","항공권"),
          ("일본여행","KR","ko","일본여행"),("동남아","KR","ko","베트남 여행")]

AIRPORT_KO = {"ICN":"인천","GMP":"김포","PUS":"김해","CJU":"제주","TAE":"대구","CJJ":"청주",
              "KWJ":"광주","USN":"울산","YNY":"양양","RSU":"여수","KUV":"군산","HIN":"사천",
              "KPO":"포항","WJU":"원주","MWX":"무안"}


def sec(name):
    for p in glob.glob("/sessions/*/mnt/claudeCowork/SECURITY/" + name) + \
             [os.path.expanduser("~/namoobi/secrets/" + name), str(BASE.parent / "SECURITY" / name)]:
        try:
            t = open(p, encoding="utf-8").read().strip()
            if t: return t
        except Exception: pass
    return None


def curl(u, to=25, jar=None, hdr=None, post=None):
    c = ["curl", "-s", "--compressed", "--max-time", str(to), "-H", "User-Agent: " + UA]
    if jar: c += ["-b", jar, "-c", jar]
    for h in (hdr or []): c += ["-H", h]
    if post is not None: c += ["-d", post]
    try:
        return subprocess.run(c + [u], capture_output=True, text=True, timeout=to + 6).stdout or ""
    except Exception:
        return ""


def jload(s):
    try: return json.loads(s)
    except Exception: return None


# ══════════════════ ① 공항 (한국공항공사 일별 예상승객) ══════════════════
def kac_day(key, d):
    """하루치 → {'in':국제도착, 'out':국제출발, 'dom':국내, 'byarp':{공항:{in,out}}}"""
    B = "https://apis.data.go.kr/B551178/airport-daily-expect-passenger/info"
    rows, pn, tc = [], 1, 1
    while len(rows) < tc and pn <= 8:
        j = jload(curl(f"{B}?serviceKey={key}&type=json&numOfRows=100&pageNo={pn}&schDate={d}", 30))
        if not j or "response" not in j: break
        b = j["response"].get("body") or {}
        it = b.get("items")
        it = it.get("item") if isinstance(it, dict) else it
        if not it: break
        try: tc = int(b.get("totalCount") or 0)
        except Exception: tc = len(it)
        rows += it; pn += 1; time.sleep(0.18)
    if not rows: return None
    o = {"in": 0.0, "out": 0.0, "dom": 0.0, "byarp": {}}
    for x in rows:
        v = x.get("PCT") or 0
        try: v = float(v)
        except Exception: continue
        intl = (x.get("TOF") == "I"); arr = (x.get("AOD") == "A")
        if intl:
            k = "in" if arr else "out"
            o[k] += v
            a = o["byarp"].setdefault(x.get("ARP", "?"), {"in": 0.0, "out": 0.0})
            a[k] += v
        else:
            o["dom"] += v
    for k in ("in", "out", "dom"): o[k] = round(o[k])
    for a in o["byarp"].values():
        a["in"] = round(a["in"]); a["out"] = round(a["out"])
    return o


# ══════════════════ ② 인천 승객예고(출·입국장별) ══════════════════
def icn_notice(key):
    """당일 25시간치만 제공 → 일 합계로 접어 이력에 누적"""
    u = ("https://apis.data.go.kr/B551177/passgrAnncmt/getPassgrAnncmt"
         f"?serviceKey={key}&type=json&numOfRows=100&pageNo=1")
    j = jload(curl(u, 30))
    if not j or "response" not in j: return None
    it = (j["response"].get("body") or {}).get("items") or []
    if isinstance(it, dict): it = it.get("item") or []
    days = {}
    for x in it:
        d = x.get("adate")
        # ⚠ 이 API 는 시간대 행 끝에 '합계' 행을 함께 준다 — 그대로 넣으면 일자 축이 오염된다
        if not d or not str(d).isdigit() or len(str(d)) != 8: continue
        s = days.setdefault(d, {"in": 0.0, "out": 0.0})
        for k, v in x.items():
            if not k.endswith(("sum1", "sum2")): continue
            try: f = float(v)
            except Exception: continue
            if "eg" in k: s["in"] += f          # entry gate = 입국장 = 인바운드
            elif "dg" in k: s["out"] += f       # departure gate = 출국장 = 아웃바운드
    return {d: {"in": round(v["in"]), "out": round(v["out"])} for d, v in days.items() if v["in"] or v["out"]}


# ══════════════════ ③ 구글 트렌즈 (쿠키 워밍업 필수) ══════════════════
def gt_warm():
    try: os.remove(JAR)
    except Exception: pass
    curl("https://www.google.com/", 20, JAR)
    curl("https://trends.google.com/trends/explore?geo=JP", 20, JAR)


def gt_series(kw, geo, hl, time_="today 12-m"):
    import urllib.parse
    req = {"comparisonItem": [{"keyword": kw, "geo": geo, "time": time_}], "category": 0, "property": ""}
    u = ("https://trends.google.com/trends/api/explore?hl=%s&tz=-540&req=" % hl
         + urllib.parse.quote(json.dumps(req, separators=(",", ":"), ensure_ascii=False)) + "&tz=-540")
    t = curl(u, 25, JAR, ["Accept-Language: %s,en;q=0.9" % hl])
    if "{" not in t: return None
    j = jload(t[t.index("{"):])
    if not j: return None
    w = [x for x in j.get("widgets", []) if x.get("id") == "TIMESERIES"]
    if not w: return None
    w = w[0]; time.sleep(0.9)
    u2 = ("https://trends.google.com/trends/api/widgetdata/multiline?hl=%s&tz=-540&req=" % hl
          + urllib.parse.quote(json.dumps(w["request"], separators=(",", ":"), ensure_ascii=False))
          + "&token=" + urllib.parse.quote(w["token"]) + "&tz=-540")
    d = curl(u2, 25, JAR, ["Accept-Language: %s,en;q=0.9" % hl])
    if "{" not in d: return None
    jj = jload(d[d.index("{"):])
    if not jj: return None
    out = []
    for p in (jj.get("default", {}).get("timelineData") or []):
        try:
            ts = int(p["time"])
            out.append([datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d"), int(p["value"][0])])
        except Exception: pass
    return out or None


# ══════════════════ ④ 네이버 데이터랩 ══════════════════
def naver_trend(groups, days=400):
    cred = sec("naver_datalab.txt")
    if not cred or ":" not in cred: return None
    cid, csec = cred.split(":", 1)
    end = datetime.now(KST).date() - timedelta(days=1)
    body = json.dumps({"startDate": str(end - timedelta(days=days)), "endDate": str(end), "timeUnit": "week",
                       "keywordGroups": [{"groupName": g, "keywords": k} for g, k in groups]}, ensure_ascii=False)
    r = curl("https://openapi.naver.com/v1/datalab/search", 25, None,
             ["X-Naver-Client-Id: " + cid.strip(), "X-Naver-Client-Secret: " + csec.strip(),
              "Content-Type: application/json"], body)
    j = jload(r)
    if not j or "results" not in j: return None
    return {x["title"]: [[p["period"], round(p["ratio"], 1)] for p in x["data"]] for x in j["results"]}


# ══════════════════ ⑤ ECOS 여행수지 ══════════════════
def ecos_travel():
    k = sec("한국은행OPENAPI인증키.txt")
    if not k: return None
    k = k.split()[0]
    st = (datetime.now(KST) - timedelta(days=365 * 8)).strftime("%Y%m")
    en = datetime.now(KST).strftime("%Y%m")
    got = {}
    for code, lab in (("2C1000", "수입"), ("2C0000", "수지")):
        j = jload(curl(f"https://ecos.bok.or.kr/api/StatisticSearch/{k}/json/kr/1/200/301Y013/M/{st}/{en}/{code}", 25))
        rows = (j or {}).get("StatisticSearch", {}).get("row", [])
        got[lab] = {r["TIME"]: float(r["DATA_VALUE"]) for r in rows if r.get("DATA_VALUE")}
    if not got.get("수입"): return None
    out = []
    for t in sorted(got["수입"]):
        rev = got["수입"][t]; bal = got["수지"].get(t)
        out.append({"d": t[:4] + "-" + t[4:], "rev": round(rev, 1),
                    "pay": (round(rev - bal, 1) if bal is not None else None),
                    "bal": (round(bal, 1) if bal is not None else None)})
    return out


# ══════════════════ ⑥ 야후 주가·환율 ══════════════════
def yahoo(sym, rng="3y", iv="1mo"):
    j = jload(curl(f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?range={rng}&interval={iv}", 20))
    try:
        r = j["chart"]["result"][0]
        ts = r["timestamp"]; cl = r["indicators"]["quote"][0]["close"]
        return [[datetime.utcfromtimestamp(t).strftime("%Y-%m"), c] for t, c in zip(ts, cl) if c]
    except Exception:
        return None


def yoy(ser):
    """[[YYYY-MM, v]] → {YYYY-MM: YoY%}"""
    m = {d: v for d, v in ser}
    o = {}
    for d, v in ser:
        y, mo = d.split("-")
        p = m.get(f"{int(y)-1}-{mo}")
        if p: o[d] = (v / p - 1) * 100
    return o


def corr(a, b, lag=0):
    """a(선행지표 YoY) 를 lag개월 앞선 것으로 보고 b(주가 YoY)와 상관"""
    ks = []
    for d in a:
        y, mo = map(int, d.split("-"))
        mo += lag; y += (mo - 1) // 12; mo = (mo - 1) % 12 + 1
        t = f"{y}-{mo:02d}"
        if t in b: ks.append((a[d], b[t]))
    n = len(ks)
    if n < 12: return None
    ax = sum(x for x, _ in ks) / n; by = sum(y for _, y in ks) / n
    sa = sum((x - ax) ** 2 for x, _ in ks) ** .5
    sb = sum((y - by) ** 2 for _, y in ks) ** .5
    if not sa or not sb: return None
    return round(sum((x - ax) * (y - by) for x, y in ks) / (sa * sb), 2)


def main():
    print("[travel] 생성 시작", flush=True)
    key = sec("data.go.kr.txt")
    today = datetime.now(KST).date()
    hist = {}
    try: hist = json.loads(HIST.read_text(encoding="utf-8"))
    except Exception: pass
    days = hist.setdefault("days", {})

    # ① 공항 예상승객 — 첫 실행이면 90일 백필, 이후 최근 10일만 갱신
    if key:
        back = 90 if len(days) < 30 else 10
        got = 0
        for i in range(back, -3, -1):
            d = (today - timedelta(days=i)).strftime("%Y%m%d")
            if d in days and days[d].get("kac") and i > 2: continue
            r = kac_day(key, d)
            if r:
                days.setdefault(d, {})["kac"] = r; got += 1
        print(f"  공항 예상승객: {got}일 신규 (누적 {len([1 for v in days.values() if v.get('kac')])}일)", flush=True)
        # ② 인천 승객예고(당일) 누적
        icn = icn_notice(key)
        if icn:
            for d, v in icn.items(): days.setdefault(d, {})["icn"] = v
            print(f"  인천 승객예고: {list(icn.items())[:1]}", flush=True)
    HIST.write_text(json.dumps(hist, ensure_ascii=False), encoding="utf-8")

    # ③ 구글 트렌즈 (인바운드 6개국 + 아웃바운드 4키워드) — 실패 시 1회 재시도(쿠키 재발급)
    gt_warm()
    def pull(lst, tag):
        o = []
        for name, geo, hl, kw in lst:
            s = gt_series(kw, geo, hl); time.sleep(1.1)
            if not s:
                gt_warm(); time.sleep(1.0)
                s = gt_series(kw, geo, hl); time.sleep(1.1)
            if s: o.append({"name": name, "geo": geo, "kw": kw, "series": s})
            print(f"  트렌즈[{tag}] {name}({kw}): {'✅ '+str(len(s))+'점 최근'+str(s[-1][1]) if s else '❌'}", flush=True)
        return o
    gts   = pull(GT_IN, "인")
    gtout = pull(GT_OUT, "아웃")
    nv = None   # 네이버 데이터랩 검색어 트렌드 API 는 앱 scope 미승인(errorCode 024) — 트렌즈로 대체

    # ⑤ ECOS
    ec = ecos_travel()
    print(f"  ECOS 여행수지: {'✅ '+str(len(ec))+'개월 최근 '+ec[-1]['d'] if ec else '❌'}", flush=True)

    # ⑥ 주가·환율 + 선행성 검증
    def px(lst):
        o = []
        for nm, sy in lst:
            s = yahoo(sy); time.sleep(0.2)
            if s: o.append({"name": nm, "sym": sy, "series": s})
        return o
    ob, ib, fx = px(OUTB), px(INB), px(FX)
    print(f"  주가: 아웃 {len(ob)}종 · 인 {len(ib)}종 · 환율/유가 {len(fx)}", flush=True)

    lead = []
    if ec:
        rev = yoy([[x["d"], x["rev"]] for x in ec])
        pay = yoy([[x["d"], x["pay"]] for x in ec if x["pay"] is not None])
        for lbl, base, grp in (("여행수입(외국인 지출)", rev, ib), ("여행지급(한국인 지출)", pay, ob)):
            for st in grp:
                sy = yoy(st["series"])
                row = {"ind": lbl, "stock": st["name"],
                       "c": [corr(base, sy, l) for l in (0, 1, 2, 3)]}
                if any(v is not None for v in row["c"]): lead.append(row)
    print(f"  선행성 검증: {len(lead)}쌍", flush=True)

    ds = sorted(days)
    OUT.write_text(json.dumps({
        "as_of": datetime.now(KST).strftime("%Y-%m-%d %H:%M"),
        "air": [{"d": d, **days[d]} for d in ds],
        "airport_ko": AIRPORT_KO,
        "gt": gts, "gt_out": gtout, "naver": nv, "ecos": ec,
        "outb": ob, "inb": ib, "fx": fx, "lead": lead,
    }, ensure_ascii=False), encoding="utf-8")
    last = ds[-1] if ds else None
    k = days.get(last, {}).get("kac", {}) if last else {}
    print(f"[travel] ✅ 공항 {len(ds)}일(최신 {last} 국제도착 {k.get('in')} 출발 {k.get('out')}) · "
          f"트렌즈 {len(gts)}국 · ECOS {len(ec or [])}개월 → {OUT}", flush=True)


if __name__ == "__main__":
    main()
