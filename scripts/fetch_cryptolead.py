#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fetch_cryptolead.py — 🪙 코인 선행지표 수집 (2026-09-05 신설)

'코인 선행지표 검토'(2026-09-05) 결론을 구현한다. "앞으로 오를지 / 오름이 유지될지"를
한 화면에서 판단하기 위해 8개 축의 지표를 무토큰·무료 API 로 매일 모아 판정(🟢🟡🔴)까지 붙인다.
LLM 토큰 0 — 전부 무인증/기보유 키. 각 수집기는 독립 try/except — 실패한 항목은 직전 값 유지.

  ① 심리·한국 수급 : 공포탐욕(crypto_fng DB 재사용) · 김프(kimp_series DB 재사용)
                    · 업비트/바이낸스 BTC 거래대금 비율(개미 열기) · 구글 트렌드 'bitcoin' 전세계·한국(pytrends, 5년 주간) — 실패 시 위키 페이지뷰 폴백(네이버 데이터랩은 2026 유료 이관으로 제외)
  ② 지갑·거래소   : Coin Metrics Community — 거래소 유입/유출($)·거래소 보유량·활성주소·해시레이트·MVRV
                    (실측 2026-09-05: community-api.coinmetrics.io 무인증, 일간, 2년 800행 OK)
  ③ 온체인 밸류   : bitcoin-data.com — MVRV Z·SOPR·NUPL·Puell (무인증이나 분당 제한 엄격 → 20초 간격, 429 면 직전값)
                    + 자체 계산: Mayer(200D)·200W 배율·반감기 경과
  ④ 기관          : 코인베이스 프리미엄(Coinbase−Binance) · IBIT 발행주식수 변화×NAV = ETF 순유입 프록시(iShares 페이지)
                    · CFTC TFF 비트코인 선물 — 자산운용사·레버리지펀드 순포지션(주간, 연도 zip 백필)
  ⑤ 파생          : Binance Futures — 펀딩비(8h→일평균)·미결제약정·롱숏계좌비·테이커 매수/매도비(30일 제한 → hist 누적)
                    · Deribit DVOL(BTC 내재변동성, 1년)
  ⑥ 매크로        : FRED — Fed 순유동성(WALCL−TGA−RRP)·M2 YoY·기준금리·美10년 · Yahoo — DXY
  ⑦ 대기자금      : DefiLlama 스테이블코인 총공급(2년)
  ⑧ 알트          : CoinGecko 시총 50 중 30일 수익률이 BTC 를 이긴 비율(알트 강세 폭) · BTC 도미넌스(crypto_overview 재사용)
  ⑨ 정책          : data/db/cryptolead_policy.json (시황 보고서 세션이 채움) 을 그대로 동봉

산출: data/db/cryptolead.json (화면용) · data/db/cryptolead_hist.json (30일 제한 API 의 일간 누적)
cron: 55 6 * * *   (crypto_intel 이 10분마다 갱신하는 fng·kimp 는 최신본을 읽어 쓴다)
"""
import json, re, io, sys, time, zipfile, urllib.request, urllib.parse
from datetime import datetime, timedelta, timezone, date
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DB   = BASE / "data" / "db"
OUT  = DB / "cryptolead.json"
HIST = DB / "cryptolead_hist.json"
KEYS = BASE / "keys"
KST  = timezone(timedelta(hours=9))
UA   = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"}
sys.path.insert(0, str(BASE / "scripts"))
try:
    from nmr_fred import fred_series
except Exception:
    fred_series = None

ERRORS = []
def log(m): print(m, flush=True)
def err(k, e):
    ERRORS.append(f"{k}: {repr(e)[:90]}"); log(f"  ⚠ {k}: {repr(e)[:120]}")

def get(url, t=25, hdr=None, data=None, raw=False, tries=2):
    last = None
    for i in range(tries):
        try:
            r = urllib.request.Request(url, headers={**UA, **(hdr or {})}, data=data)
            b = urllib.request.urlopen(r, timeout=t).read()
            return b if raw else b.decode("utf-8", "replace")
        except Exception as e:
            last = e; time.sleep(1.5 * (i + 1))
    raise last
def jget(url, **kw): return json.loads(get(url, **kw))
def jload(p, default=None):
    try: return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception: return default if default is not None else {}
def today(): return datetime.now(KST).strftime("%Y-%m-%d")
def utc(ts): return datetime.fromtimestamp(ts, timezone.utc)
def f(v):
    try: return float(v)
    except Exception: return None

# ── 시계열 유틸 (s = [[YYYY-MM-DD, val], ...] 오름차순) ──────────────────────
def last(s): return s[-1][1] if s else None
def at_back(s, n):
    """n일 전(달력) 값 — 없으면 그 이전 최근값"""
    if not s: return None
    d0 = datetime.strptime(s[-1][0], "%Y-%m-%d") - timedelta(days=n)
    prev = None
    for d, v in s:
        if datetime.strptime(d, "%Y-%m-%d") <= d0: prev = v
        else: break
    return prev
def pct(a, b): return None if (a is None or b in (None, 0)) else (a / b - 1) * 100
def chg(s, n): return pct(last(s), at_back(s, n))
def rank(s, n=365):
    """최근 n일 구간에서 현재값의 백분위(0~100)"""
    vals = [v for _, v in s[-n:] if v is not None]
    if len(vals) < 10: return None
    cur = vals[-1]
    return sum(1 for v in vals if v <= cur) / len(vals) * 100
def sma(s, n):
    vals = [v for _, v in s[-n:] if v is not None]
    return sum(vals) / len(vals) if len(vals) >= n * 0.8 else None
def trim(s, n=400): return [[d, (round(v, 4) if isinstance(v, float) else v)] for d, v in s[-n:]]
def daily_from_ts(rows, key_ts, key_v, ms=True):
    out = {}
    for r in rows:
        ts = int(r[key_ts]) / (1000 if ms else 1)
        out[utc(ts).strftime("%Y-%m-%d")] = f(r[key_v])
    return sorted([[d, v] for d, v in out.items() if v is not None])

# ══════════════════════════════════════════════════════════════════════════
# 수집기 — 각각 {key: series or value} 를 IND 에 채운다
IND = {}      # key -> dict(v, s, d, extra...)
def put(key, s=None, v=None, **kw):
    e = IND.setdefault(key, {})
    if s is not None:
        e["s"] = trim(s); e["v"] = last(s); e["d"] = s[-1][0]
    if v is not None: e["v"] = v
    e.update(kw)

def price_btc():
    """Binance 일봉 1000일 + 주봉 300주 — Mayer·200W·차트 오버레이"""
    k = jget("https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1d&limit=1000")
    d = [[utc(r[0] / 1000).strftime("%Y-%m-%d"), float(r[4])] for r in k]
    qv = [[utc(r[0] / 1000).strftime("%Y-%m-%d"), float(r[7])] for r in k]   # quote volume USDT
    w = jget("https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1w&limit=300")
    wk = [[utc(r[0] / 1000).strftime("%Y-%m-%d"), float(r[4])] for r in w]     # (2026-09-05) 날짜 동봉 — 200주 배율 시계열용
    return d, qv, wk

def c_sentiment(qv_bn):
    # 공포탐욕 — crypto_intel 이 10분마다 갱신
    fg = jload(DB / "crypto_fng.json")
    if fg.get("hist"):
        put("fng", s=[[r["date"], r["v"]] for r in fg["hist"]], label=fg["now"].get("label"))
    # 김프 BTC — kimp_series (일 단위 포인트)
    km = jload(DB / "kimp_series.json")
    sb = (km.get("s") or {}).get("BTC") or []
    if sb:
        byday = {}
        for t, v in sb: byday[t[:10]] = v
        put("kimp", s=sorted(byday.items()), now=(km.get("now") or {}).get("BTC"))
    # 업비트/바이낸스 BTC 거래대금 비율 — 200일 (업비트 KRW → USD 환산: kimp_series 의 fx)
    try:
        up = jget("https://api.upbit.com/v1/candles/days?market=KRW-BTC&count=200")
        fx = km.get("fx") or 1400
        ups = {r["candle_date_time_utc"][:10]: r["candle_acc_trade_price"] / fx for r in up}
        bn = dict(qv_bn)
        s = sorted([[d, ups[d] / bn[d] * 100] for d in ups if d in bn and bn[d]])
        put("upbit_ratio", s=s)
    except Exception as e: err("upbit_ratio", e)
    # 구글 트렌드 'bitcoin' — 전세계·한국, 5년 주간 (pytrends 비공식 · 서버 실측 2026-09-05 OK. retries 인자는 urllib3 신버전과 충돌하므로 주지 말 것)
    #   (사용자 피드백 2026-09-05 "위키보다 구글") — 구글이 주지표, 아래 위키는 구글 실패 시 폴백
    gt_ok = False
    try:
        import warnings; warnings.filterwarnings("ignore")
        from pytrends.request import TrendReq
        for geo, key in (("", "gt_world"), ("KR", "gt_kr")):
            pt = TrendReq(hl="en-US", tz=540, timeout=(10, 25))
            pt.build_payload(["bitcoin"], timeframe="today 5-y", geo=geo)
            df = pt.interest_over_time()
            s = [[str(i)[:10], float(v)] for i, v in zip(df.index, df["bitcoin"])]
            if len(s) > 50: put(key, s=s); gt_ok = True
            time.sleep(4)
    except Exception as e: err("google_trends", e)
    if gt_ok: return
    # (폴백) 위키피디아 '비트코인'(ko)·'Bitcoin'(en) 일간 페이지뷰 — 대중 관심 대리지표. 7일 평균, 2년
    #   (2026-09-05) 네이버 데이터랩 검색어트렌드는 NAVER API HUB(NCP 유료)로 이관·종료 공지 → 무료 공식 API 인 위키미디어로 교체
    for proj, art, key in (("ko.wikipedia", "%EB%B9%84%ED%8A%B8%EC%BD%94%EC%9D%B8", "wiki_ko"), ("en.wikipedia", "Bitcoin", "wiki_en")):
        try:
            d1 = date.today() - timedelta(days=1); d0 = d1 - timedelta(days=730)
            j = jget(f"https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/{proj}/all-access/user/{art}/daily/"
                     f"{d0.strftime('%Y%m%d')}/{d1.strftime('%Y%m%d')}", hdr={"User-Agent": "namoobi-terminal/1.0 (namoobi@gmail.com)"})
            raw_s = [[r["timestamp"][:4] + "-" + r["timestamp"][4:6] + "-" + r["timestamp"][6:8], r["views"]] for r in j["items"]]
            s = [[raw_s[i][0], sum(v for _, v in raw_s[max(0, i - 6):i + 1]) / len(raw_s[max(0, i - 6):i + 1])] for i in range(len(raw_s))]
            put(key, s=s)
        except Exception as e: err(key, e)

def c_coinmetrics():
    j = jget("https://community-api.coinmetrics.io/v4/timeseries/asset-metrics?assets=btc"
             "&metrics=FlowInExUSD,FlowOutExUSD,SplyExNtv,CapMVRVCur,AdrActCnt,HashRate&frequency=1d&page_size=800"
             "&start_time=" + (date.today() - timedelta(days=760)).isoformat(), t=40)
    rows = j["data"]
    D = lambda k: [[r["time"][:10], f(r.get(k))] for r in rows if f(r.get(k)) is not None]
    fi, fo = D("FlowInExUSD"), D("FlowOutExUSD")
    fo_d = dict(fo)
    net = [[d, (v - fo_d[d]) / 1e6] for d, v in fi if d in fo_d]           # $M, 양수=순유입(매도 대기)
    net7 = [[net[i][0], sum(v for _, v in net[max(0, i - 6):i + 1])] for i in range(len(net))]
    put("ex_netflow", s=net7, daily=trim(net, 90))
    put("ex_supply", s=D("SplyExNtv"))
    put("mvrv", s=D("CapMVRVCur"))
    put("adr_act", s=D("AdrActCnt"))
    hr = [[d, v / 1e6] for d, v in D("HashRate")]                              # EH/s
    hr7 = [[hr[i][0], sum(v for _, v in hr[max(0, i - 6):i + 1]) / len(hr[max(0, i - 6):i + 1])] for i in range(len(hr))]
    put("hashrate", s=hr7)

def c_bitcoindata(prev):
    for ep, key in (("mvrv-zscore", "mvrv_z"), ("sopr", "sopr"), ("nupl", "nupl"), ("puell-multiple", "puell")):
        try:
            j = jget(f"https://bitcoin-data.com/v1/{ep}", t=30, tries=1)
            fld = [k for k in j[-1].keys() if k not in ("d", "unixTs")][0]
            s = sorted([[r["d"], f(r[fld])] for r in j if f(r.get(fld)) is not None])
            if key == "sopr":   # 7일 평균으로 노이즈 제거
                s = [[s[i][0], sum(v for _, v in s[max(0, i - 6):i + 1]) / len(s[max(0, i - 6):i + 1])] for i in range(len(s))]
            put(key, s=s)
        except Exception as e:
            err(key, e)
            if prev.get(key): IND[key] = prev[key]; IND[key]["stale"] = True
        time.sleep(20)

def c_cycle(d_px, wk):
    px = d_px[-1][1]
    m200 = sma(d_px, 200)
    if m200: put("mayer", s=[[d, v / (sum(x[1] for x in d_px[i - 199:i + 1]) / 200)] for i, (d, v) in enumerate(d_px) if i >= 199])
    if len(wk) >= 200:
        # (2026-09-05 피드백 "추세 차트 없는 건 왜") 200주 배율 시계열 — 각 일자에 그 시점까지의 200주 이평 적용
        wd = [d for d, _ in wk]; wv = [v for _, v in wk]
        import bisect
        s = []
        for d, v in d_px[-400:]:
            i = bisect.bisect_right(wd, d)        # d 이전(포함) 주봉 개수
            if i >= 200: s.append([d, v / (sum(wv[i - 200:i]) / 200)])
        w200 = sum(wv[-200:]) / 200
        if s: put("w200", s=s, w200=w200)
        else: put("w200", v=px / w200, w200=w200)
    halv = date(2024, 4, 20); nxt = date(2028, 4, 15)
    put("halving", v=(date.today() - halv).days, next_days=(nxt - date.today()).days, last=halv.isoformat(), next=nxt.isoformat())

def c_institution(d_px, hist):
    # 코인베이스 프리미엄 — 일봉 300일(양쪽 종가) + 현재 호가
    try:
        cb = jget("https://api.exchange.coinbase.com/products/BTC-USD/candles?granularity=86400")
        cbd = {utc(r[0]).strftime("%Y-%m-%d"): r[4] for r in cb}
        bn = dict(d_px)
        s = sorted([[d, (cbd[d] / bn[d] - 1) * 100] for d in cbd if d in bn])
        t1 = jget("https://api.exchange.coinbase.com/products/BTC-USD/ticker")
        t2 = jget("https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT")
        now = (float(t1["price"]) / float(t2["price"]) - 1) * 100
        put("cb_prem", s=s, now=round(now, 3))
    except Exception as e: err("cb_prem", e)
    # IBIT — 발행주식수·순자산 (iShares 페이지) → 일간 누적 → Δ주식수 × NAV = 순유입 프록시
    try:
        t = get("https://www.ishares.com/us/products/333011/ishares-bitcoin-trust", t=30)
        sh = re.search(r"Shares Outstanding.{0,400}?([\d,]{6,})", t, re.S)
        na = re.search(r"Net Assets of Fund[^$]{0,200}\$\s*([\d,\.]+)", t, re.S)
        asof = re.search(r"as of ([A-Z][a-z]{2} \d{1,2}, \d{4})", t)
        if sh and na:
            shares = float(sh.group(1).replace(",", "")); nav_tot = float(na.group(1).replace(",", ""))
            d = datetime.strptime(asof.group(1), "%b %d, %Y").strftime("%Y-%m-%d") if asof else today()
            H = hist.setdefault("ibit", {}); H[d] = [shares, nav_tot]
            ks = sorted(H)
            flow = []
            for i in range(1, len(ks)):
                s0, n0 = H[ks[i - 1]]; s1, n1 = H[ks[i]]
                flow.append([ks[i], (s1 - s0) * (n1 / s1) / 1e6])       # $M
            put("ibit_flow", s=flow if flow else [[d, 0.0]], shares=shares, aum=nav_tot, asof=d,
                pts=len(ks))
    except Exception as e: err("ibit", e)
    # CFTC TFF 비트코인 선물 — 주간
    try:
        H = hist.setdefault("cot", {})
        def parse(txt):
            for ln in txt.split("\n"):
                if ln.startswith('"BITCOIN - CHICAGO MERCANTILE'):
                    c = [x.strip().strip('"') for x in ln.split(",")]
                    # 7:OI 8-10 Dealer L/S/Sp 11-13 AssetMgr 14-16 LevMoney 17-19 Other 20-21 TotRept 22-23 NonRept
                    H[c[2]] = [int(c[7]), int(c[11]) - int(c[12]), int(c[14]) - int(c[15]), int(c[22]) - int(c[23])]
        if len(H) < 20:
            for y in (date.today().year - 1, date.today().year):
                try:
                    b = get(f"https://www.cftc.gov/files/dea/history/fut_fin_txt_{y}.zip", t=60, raw=True)
                    z = zipfile.ZipFile(io.BytesIO(b)); parse(z.read(z.namelist()[0]).decode("utf-8", "replace"))
                except Exception as e: err(f"cot_zip{y}", e)
        parse(get("https://www.cftc.gov/dea/newcot/FinFutWk.txt", t=40))
        ks = sorted(H)
        put("cot_am",  s=[[k, H[k][1]] for k in ks], oi=[[k, H[k][0]] for k in ks][-60:])
        put("cot_lev", s=[[k, H[k][2]] for k in ks])
        put("cot_ret", s=[[k, H[k][3]] for k in ks])
    except Exception as e: err("cot", e)

def c_derivs(hist):
    # 펀딩비 — 8h 1000건 → 일평균(%)
    try:
        fr = jget("https://fapi.binance.com/fapi/v1/fundingRate?symbol=BTCUSDT&limit=1000")
        by = {}
        for r in fr: by.setdefault(utc(r["fundingTime"] / 1000).strftime("%Y-%m-%d"), []).append(float(r["fundingRate"]) * 100)
        put("funding", s=sorted([[d, sum(v) / len(v)] for d, v in by.items()]), last8h=float(fr[-1]["fundingRate"]) * 100)
    except Exception as e: err("funding", e)
    # 30일 제한 지표 → hist 누적
    H = hist.setdefault("deriv", {})
    try:
        for r in jget("https://fapi.binance.com/futures/data/openInterestHist?symbol=BTCUSDT&period=1d&limit=30"):
            H.setdefault(utc(r["timestamp"] / 1000).strftime("%Y-%m-%d"), {})["oi"] = float(r["sumOpenInterestValue"]) / 1e9
        for r in jget("https://fapi.binance.com/futures/data/globalLongShortAccountRatio?symbol=BTCUSDT&period=1d&limit=30"):
            H.setdefault(utc(r["timestamp"] / 1000).strftime("%Y-%m-%d"), {})["ls"] = float(r["longShortRatio"])
        for r in jget("https://fapi.binance.com/futures/data/takerlongshortRatio?symbol=BTCUSDT&period=1d&limit=30"):
            H.setdefault(utc(r["timestamp"] / 1000).strftime("%Y-%m-%d"), {})["taker"] = float(r["buySellRatio"])
    except Exception as e: err("deriv30", e)
    ks = sorted(H)
    for k, nm in (("oi", "oi"), ("ls", "ls_ratio"), ("taker", "taker")):
        s = [[d, H[d][k]] for d in ks if k in H[d]]
        if s: put(nm, s=s)
    # Deribit DVOL 1년
    try:
        now = int(time.time() * 1000)
        j = jget(f"https://www.deribit.com/api/v2/public/get_volatility_index_data?currency=BTC&resolution=86400"
                 f"&start_timestamp={now - 400 * 86400000}&end_timestamp={now}")
        put("dvol", s=daily_from_ts([{"t": r[0], "v": r[4]} for r in j["result"]["data"]], "t", "v"))
    except Exception as e: err("dvol", e)

def c_macro():
    if fred_series:
        try:
            start = (date.today() - timedelta(days=3 * 365)).isoformat()
            wal = fred_series("WALCL", start=start); tga = fred_series("WTREGEN", start=start); rrp = fred_series("RRPONTSYD", start=start)
            def near(s, d):
                p = None
                for dd, v in s:
                    if dd <= d: p = v
                    else: break
                return p
            nl = []
            for d, v in wal:
                t_, r_ = near(tga, d), near(rrp, d)
                if t_ is not None and r_ is not None: nl.append([d, (v - t_) / 1000 - r_])     # $bn (WALCL·WTREGEN 은 백만$, RRP 는 십억$ — 실측 2026-09-05)
            if nl: put("netliq", s=nl)
        except Exception as e: err("netliq", e)
        try:
            m2 = fred_series("M2SL", start=(date.today() - timedelta(days=6 * 365)).isoformat())
            yoy = [[m2[i][0], (m2[i][1] / m2[i - 12][1] - 1) * 100] for i in range(12, len(m2))]
            put("m2", s=yoy, level=m2[-1][1])
        except Exception as e: err("m2", e)
        try:
            dff = fred_series("DFF", start=(date.today() - timedelta(days=400)).isoformat())
            put("dff", s=dff[::7] + ([dff[-1]] if dff and dff[-1] not in dff[::7] else []))
            put("us10y", s=fred_series("DGS10", start=(date.today() - timedelta(days=400)).isoformat()))
        except Exception as e: err("rates", e)
    try:
        j = jget("https://query1.finance.yahoo.com/v8/finance/chart/DX-Y.NYB?range=1y&interval=1d")["chart"]["result"][0]
        ts, cl = j["timestamp"], j["indicators"]["quote"][0]["close"]
        put("dxy", s=[[utc(t).strftime("%Y-%m-%d"), c] for t, c in zip(ts, cl) if c])
    except Exception as e: err("dxy", e)

def c_stable():
    j = jget("https://stablecoins.llama.fi/stablecoincharts/all", t=40)
    s = []
    for r in j:
        v = (r.get("totalCirculatingUSD") or {}).get("peggedUSD")
        if v: s.append([utc(int(r["date"])).strftime("%Y-%m-%d"), v / 1e9])
    put("stable", s=s[-760:])

def c_alt(hist):
    STABLE = {"usdt", "usdc", "dai", "usds", "fdusd", "usde", "tusd", "pyusd", "usd1", "usdd", "frax", "busd", "usdtb", "rlusd", "usd0", "buidl", "gho", "lusd", "paxg", "xaut", "usdy", "usyc", "susds", "susde"}
    WRAP = {"wbtc", "steth", "weth", "wsteth", "weeth", "cbbtc", "reth", "wbeth", "rseth", "lbtc", "meth", "ezeth", "jitosol", "bnsol", "tbtc"}
    j = jget("https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=80&page=1&price_change_percentage=30d")
    btc = next(x for x in j if x["symbol"] == "btc")["price_change_percentage_30d_in_currency"]
    alts = [x for x in j if x["symbol"] not in STABLE | WRAP | {"btc"} and x.get("price_change_percentage_30d_in_currency") is not None][:50]
    beat = sum(1 for x in alts if x["price_change_percentage_30d_in_currency"] > btc)
    ratio = beat / len(alts) * 100
    H = hist.setdefault("alt", {}); H[today()] = round(ratio, 1)
    if len(H) < 30 and not hist.get("alt_backfilled"):
        # (2026-09-05) 1회 백필 — CoinGecko market_chart(무료·1년 일봉)로 코인별 30일 수익률을 재구성해 과거 알트 강세폭 계산.
        #   50코인+BTC 51콜, 무료 분당 제한(~30) 때문에 2.5초 간격 ≈ 2분. 실패 코인은 제외(분모에서 뺌).
        try:
            def mc(cid):
                # 무료 CoinGecko 는 실측 분당 ~10콜 — 429 면 40초 쉬고 1회 재시도
                u = f"https://api.coingecko.com/api/v3/coins/{cid}/market_chart?vs_currency=usd&days=365&interval=daily"
                try: j2 = jget(u, t=30, tries=1)
                except Exception:
                    time.sleep(40); j2 = jget(u, t=30, tries=1)
                out = {}
                for ts, pr in j2["prices"]: out[utc(ts / 1000).strftime("%Y-%m-%d")] = pr
                return out
            btcp = mc("bitcoin"); time.sleep(6)
            series = []
            for x in alts:
                try: series.append(mc(x["id"]))
                except Exception as e2: log(f"    alt backfill skip {x['id']}: {repr(e2)[:50]}")
                time.sleep(6)
            days = sorted(btcp)
            for i, d in enumerate(days):
                if i < 30 or d in H: continue
                d0 = days[i - 30]
                if d0 not in btcp or not btcp[d0]: continue
                b = btcp[d] / btcp[d0] - 1
                cnt = beat2 = 0
                for sc in series:
                    if d in sc and d0 in sc and sc[d0]:
                        cnt += 1; beat2 += (sc[d] / sc[d0] - 1) > b
                if cnt >= 20: H[d] = round(beat2 / cnt * 100, 1)
            if len(H) >= 30: hist["alt_backfilled"] = today()     # 충분히 채웠을 때만 완료 표시 — 아니면 다음 실행에 재시도
            log(f"    alt backfill: {len(H)}일 (코인 {len(series)}개)")
        except Exception as e: err("alt_backfill", e)
    put("altbreadth", s=sorted([[d, v] for d, v in H.items()]), n=len(alts), btc30=btc,
        top=[[x["symbol"].upper(), round(x["price_change_percentage_30d_in_currency"], 1)] for x in sorted(alts, key=lambda x: -x["price_change_percentage_30d_in_currency"])[:8]])
    ov = jload(DB / "crypto_overview.json")
    if ov.get("btc_dom"):
        H2 = hist.setdefault("dom", {}); H2[today()] = round(ov["btc_dom"], 2)
        put("btc_dom", s=sorted([[d, v] for d, v in H2.items()]))

# ══════════════════════════════════════════════════════════════════════════
# 판정 — status: bull(상승 우호) / neu / bear(하락·과열 경계). 각 지표에 threshold 설명(thr)도 동봉.

# ── ⑩ 알트 순환 축 (2026-09-05 사용자 결정 "BTC/알트 분리 → 5번째 축") ─────────────────────
#   질문이 다르다: 위 4축은 "시장(=BTC)이 오를까", 이 축은 "BTC 를 들고 있을 때냐 알트로 갈아탈 때냐"(자금 순환 위치).
#   알트는 BTC 방향을 증폭해 따라가므로 BTC 지표를 복제하지 않고 '순환'에만 있는 지표를 모은다.
def c_altcycle(hist):
    # a) ETH/BTC — 알트시즌의 고전적 방아쇠 (Binance 일봉 1000일)
    try:
        k = jget("https://api.binance.com/api/v3/klines?symbol=ETHBTC&interval=1d&limit=1000")
        put("eth_btc", s=[[utc(r[0] / 1000).strftime("%Y-%m-%d"), float(r[4])] for r in k])
    except Exception as e: err("eth_btc", e)
    # b) 주요 알트 시총 / BTC 시총 + 스테이블 공급 / (BTC+ETH 시총) — Coin Metrics Community(시총은 구형 100자산만 제공 → 12종 바스켓)
    try:
        basket = "eth,bnb,ada,doge,dot,link,ltc,bch,aave,algo,etc,icp"
        j = jget("https://community-api.coinmetrics.io/v4/timeseries/asset-metrics?assets=btc," + basket +
                 "&metrics=CapMrktCurUSD&frequency=1d&page_size=10000&start_time=" + (date.today() - timedelta(days=760)).isoformat(), t=60)
        by = {}
        for r in j["data"]:
            v = f(r.get("CapMrktCurUSD"))
            if v: by.setdefault(r["time"][:10], {})[r["asset"]] = v
        ratio = sorted([[d, sum(v for a, v in m.items() if a != "btc") / m["btc"] * 100] for d, m in by.items() if "btc" in m and len(m) >= 8])
        put("alt_mcap_ratio", s=ratio, n=len(basket.split(",")))
        st = IND.get("stable", {}).get("s") or []
        if st:
            bm = {d: m.get("btc", 0) + m.get("eth", 0) for d, m in by.items() if "btc" in m and "eth" in m}
            put("stable_ratio", s=sorted([[d, v / (bm[d] / 1e9) * 100] for d, v in st if d in bm and bm[d]]))
    except Exception as e: err("alt_mcap", e)
    # c) ETH 거래소 순유입 7일합 (Coin Metrics — flow 는 btc·eth 만 제공)
    try:
        j = jget("https://community-api.coinmetrics.io/v4/timeseries/asset-metrics?assets=eth&metrics=FlowInExUSD,FlowOutExUSD&frequency=1d&page_size=800"
                 "&start_time=" + (date.today() - timedelta(days=420)).isoformat(), t=40)
        net = [[r["time"][:10], (f(r["FlowInExUSD"]) - f(r["FlowOutExUSD"])) / 1e6] for r in j["data"] if f(r.get("FlowInExUSD")) is not None and f(r.get("FlowOutExUSD")) is not None]
        put("eth_netflow", s=[[net[i][0], sum(v for _, v in net[max(0, i - 6):i + 1])] for i in range(len(net))])
    except Exception as e: err("eth_netflow", e)
    # d) 업비트 알트 거래대금 비중 — 거래대금 상위 30 알트 200일 일봉 합 ÷ (알트+BTC). 국내 개미는 알트에 몰린다.
    try:
        kr = [m["market"] for m in jget("https://api.upbit.com/v1/market/all") if m["market"].startswith("KRW-")]
        tk = []
        for i in range(0, len(kr), 100):
            tk += jget("https://api.upbit.com/v1/ticker?markets=" + ",".join(kr[i:i + 100])); time.sleep(0.2)
        top = [x["market"] for x in sorted(tk, key=lambda x: -x["acc_trade_price_24h"]) if x["market"] != "KRW-BTC"][:30]
        agg = {}
        for m in ["KRW-BTC"] + top:
            for r in jget(f"https://api.upbit.com/v1/candles/days?market={m}&count=200"):
                d = r["candle_date_time_utc"][:10]; a = agg.setdefault(d, [0.0, 0.0])
                a[0 if m == "KRW-BTC" else 1] += r["candle_acc_trade_price"]
            time.sleep(0.15)
        put("upbit_alt_share", s=sorted([[d, a[1] / (a[0] + a[1]) * 100] for d, a in agg.items() if a[0] + a[1] > 0]), top=[m[4:] for m in top[:8]])
    except Exception as e: err("upbit_alt_share", e)
    # e) 알트 펀딩비 − BTC 펀딩비 (ETH·SOL·XRP·DOGE·BNB 일평균) — 알트 레버리지 과열
    try:
        def fday(sym):
            by = {}
            for r in jget(f"https://fapi.binance.com/fapi/v1/fundingRate?symbol={sym}&limit=1000"):
                by.setdefault(utc(r["fundingTime"] / 1000).strftime("%Y-%m-%d"), []).append(float(r["fundingRate"]) * 100)
            return {d: sum(v) / len(v) for d, v in by.items()}
        b = fday("BTCUSDT"); alts = [fday(s) for s in ("ETHUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT", "BNBUSDT")]
        s = []
        for d in sorted(b):
            vs = [a[d] for a in alts if d in a]
            if len(vs) >= 3: s.append([d, sum(vs) / len(vs) - b[d]])
        put("alt_funding", s=s)
    except Exception as e: err("alt_funding", e)

def judge():
    def S(k, st, txt, jv=None, jl=None):
        e = IND.setdefault(k, {}); e.update(status=st, judge=txt)
        if jv is not None: e.update(jv=round(jv, 3), jl=jl)     # 판정에 쓴 파생값(변화율·백분위) — 화면 게이지용
    g = lambda k: IND.get(k, {})
    v = lambda k: g(k).get("v")
    s = lambda k: g(k).get("s") or []

    x = v("fng")
    if x is not None: S("fng", "bull" if x <= 25 else "bear" if x >= 75 else "neu", f"{x} — " + ("극단 공포=역발상 매수 구간" if x <= 25 else "극단 탐욕=단기 고점 경계" if x >= 75 else "중립 구간"))
    x = v("kimp")
    if x is not None: S("kimp", "bear" if x >= 5 else "bull" if x <= 0 else "neu", f"{x:+.2f}% — " + ("국내 과열(김프 5%↑는 역사적 단기 고점 신호)" if x >= 5 else "역프/무프=국내 관심 식음, 바닥권 특징" if x <= 0 else "정상 범위"))
    r = rank(s("upbit_ratio"), 200)
    if r is not None: S("upbit_ratio", "bear" if r >= 90 else "bull" if r <= 15 else "neu", f"200일 백분위 {r:.0f}% — " + ("개미 거래대금 급증=과열" if r >= 90 else "개미 이탈=바닥권 특징" if r <= 15 else "보통"), jv=r, jl="200일 백분위 %")
    for k in ("gt_world", "gt_kr"):
        r = rank(s(k), 261)
        if r is not None: S(k, "bear" if r >= 90 else "bull" if r <= 20 else "neu", f"5년 백분위 {r:.0f}% (지수 {v(k):.0f}/100) — " + ("검색 폭증=대중 관심 정점(2017·2021 고점 동행)" if r >= 90 else "무관심=역발상 구간" if r <= 20 else "보통"), jv=r, jl="5년 백분위 %")
    for k in ("wiki_ko", "wiki_en"):
        r = rank(s(k), 730)
        if r is not None: S(k, "bear" if r >= 90 else "bull" if r <= 20 else "neu", f"2년 백분위 {r:.0f}% — " + ("조회 폭증=대중 관심 정점(단기 고점 동행)" if r >= 90 else "무관심=역발상 구간" if r <= 20 else "보통"), jv=r, jl="2년 백분위 %")

    x = v("ex_netflow")
    if x is not None: S("ex_netflow", "bull" if x < -500 else "bear" if x > 500 else "neu", f"7일 순유입 {x:+,.0f}M$ — " + ("거래소 유출 우세=장기 보관, 매도 압력↓" if x < -500 else "거래소 유입 우세=매도 대기 물량↑" if x > 500 else "균형"))
    c = chg(s("ex_supply"), 30)
    if c is not None: S("ex_supply", "bull" if c < -1 else "bear" if c > 1 else "neu", f"거래소 보유량 30일 {c:+.1f}% — " + ("감소=축적 국면" if c < -1 else "증가=분산·매도 국면" if c > 1 else "보합"), jv=c, jl="30일 변화 %")
    c = chg(s("adr_act"), 30)
    if c is not None: S("adr_act", "bull" if c > 5 else "bear" if c < -5 else "neu", f"활성주소 30일 {c:+.1f}% — 네트워크 사용 " + ("증가" if c > 5 else "감소" if c < -5 else "보합"), jv=c, jl="30일 변화 %")
    c = chg(s("hashrate"), 30)
    if c is not None: S("hashrate", "bear" if c < -10 else "bull" if c > 5 else "neu", f"해시레이트(7D) 30일 {c:+.1f}% — " + ("급락=채굴자 항복(역사적 바닥 근처지만 단기 매도 압력)" if c < -10 else "상승=채굴자 확신" if c > 5 else "보합"), jv=c, jl="30일 변화 %")

    x = v("mvrv")
    if x is not None: S("mvrv", "bull" if x < 1.0 else "bear" if x >= 3.0 else "neu", f"MVRV {x:.2f} — " + ("1 미만=시장 전체 손실=역사적 바닥권" if x < 1 else "3 이상=과열, 3.5~4 는 사이클 고점" if x >= 3 else "1~3 정상"))
    x = v("mvrv_z")
    if x is not None: S("mvrv_z", "bull" if x < 0.5 else "bear" if x >= 6 else "neu", f"Z {x:.2f} — " + ("0 근처=바닥 밴드" if x < 0.5 else "6 이상=고점 밴드" if x >= 6 else "중간"))
    x = v("sopr")
    if x is not None: S("sopr", "bull" if x < 0.98 else "bear" if x > 1.05 else "neu", f"SOPR(7D) {x:.3f} — " + ("1 미만 지속=손절 매도 소진 국면" if x < 0.98 else "1.05 초과=차익실현 활발" if x > 1.05 else "1 부근=균형(상승장에선 1 지지가 매수점)"))
    x = v("nupl")
    if x is not None: S("nupl", "bull" if x < 0.25 else "bear" if x >= 0.7 else "neu", f"NUPL {x:.2f} — " + ("0.25 미만=희망/항복 구간" if x < 0.25 else "0.7 이상=도취(euphoria)" if x >= 0.7 else "낙관/믿음 구간"))
    x = v("puell")
    if x is not None: S("puell", "bull" if x < 0.6 else "bear" if x >= 3 else "neu", f"Puell {x:.2f} — " + ("0.6 미만=채굴 수익 바닥" if x < 0.6 else "3 이상=채굴 수익 과열" if x >= 3 else "정상"))
    x = v("mayer")
    if x is not None: S("mayer", "bull" if x < 0.85 else "bear" if x >= 2.2 else "neu", f"Mayer {x:.2f} — 200일선 대비 " + ("15%↓ 저평가" if x < 0.85 else "2.2 배↑ 과열" if x >= 2.2 else "정상"))
    x = v("w200")
    if x is not None: S("w200", "bull" if x < 1.1 else "bear" if x >= 4 else "neu", f"200주선 배율 {x:.2f} — " + ("200주선 근접=역사적 바닥선(2015·2018·2022 모두 지지)" if x < 1.1 else "4배 이상=사이클 고점권" if x >= 4 else "중간"))
    x = v("halving")
    if x is not None: S("halving", "neu", f"반감기 후 {x}일 — 과거 3회 고점은 반감기 후 12~18개월(365~550일), 이후 1년 약세")

    x = v("cb_prem")
    if x is not None: S("cb_prem", "bull" if x > 0.05 else "bear" if x < -0.05 else "neu", f"{x:+.3f}% — " + ("코인베이스 프리미엄=미국 기관·ETF 매수 우세" if x > 0.05 else "디스카운트=미국 매도 우세" if x < -0.05 else "중립"))
    fs = s("ibit_flow")
    if fs:
        w = sum(v_ for _, v_ in fs[-5:])
        S("ibit_flow", "bull" if w > 200 else "bear" if w < -200 else "neu", f"IBIT 최근 {min(5, len(fs))}일 {w:+,.0f}M$ — " + ("순유입" if w > 200 else "순유출" if w < -200 else "보합") + (" (관측 축적 중)" if g("ibit_flow").get("pts", 0) < 7 else ""), jv=w, jl="최근 5일 합 M$")
    x = v("cot_am"); c = chg(s("cot_am"), 28)
    if x is not None: S("cot_am", "bull" if (c or 0) > 10 else "bear" if (c or 0) < -10 else "neu", f"자산운용사 순포지션 {x:+,} 계약 (4주 {c:+.0f}%)" if c is not None else f"{x:+,} 계약", jv=c, jl="4주 변화 %")
    x = v("cot_lev")
    if x is not None: S("cot_lev", "neu", f"레버리지펀드 순 {x:+,} — 순숏은 베이시스 차익거래(현물 ETF 롱+선물 숏)라 방향 신호 아님. 숏 축소는 베이시스 붕괴=위험선호 후퇴")

    x = v("funding")
    if x is not None: S("funding", "bear" if x >= 0.05 else "bull" if x < 0 else "neu", f"일평균 {x:+.4f}%(8h) — " + ("롱 과열(연 55%↑)=청산 캐스케이드 위험" if x >= 0.05 else "음수=숏 과밀, 숏스퀴즈 여지" if x < 0 else "정상(0.01% 기본)"))
    so = s("oi"); c = pct(last(so), so[0][1]) if 14 <= len(so) < 32 else chg(so, 30); px = chg(IND.get("_px", {}).get("s") or [], min(30, max(1, len(so) - 1)))
    if c is not None: S("oi", "bear" if (c > 25 and (px or 0) < 5) else "bull" if c < -15 else "neu", f"미결제약정 30일 {c:+.0f}% (가격 {px:+.0f}%) — " + ("레버리지 누적+가격 정체=변동성 폭발 전조" if (c > 25 and (px or 0) < 5) else "디레버리징 완료" if c < -15 else "보통") if px is not None else f"OI 30일 {c:+.0f}%", jv=c, jl="30일 변화 %")
    x = v("ls_ratio")
    if x is not None: S("ls_ratio", "bear" if x >= 2 else "bull" if x <= 0.9 else "neu", f"롱/숏 계좌비 {x:.2f} — " + ("롱 쏠림(역발상 하락 위험)" if x >= 2 else "숏 우세(역발상 상승 여지)" if x <= 0.9 else "균형"))
    x = v("taker")
    if x is not None: S("taker", "bull" if x >= 1.1 else "bear" if x <= 0.9 else "neu", f"테이커 매수/매도 {x:.2f} — " + ("공격적 매수 우세" if x >= 1.1 else "공격적 매도 우세" if x <= 0.9 else "균형"))
    x = v("dvol")
    if x is not None: S("dvol", "neu", f"DVOL {x:.0f} — " + ("40 미만=변동성 압축, 큰 움직임 전조(방향 미정)" if x < 40 else "80 이상=패닉·항복 국면(역사적 바닥 근처)" if x >= 80 else "정상"))

    c = chg(s("netliq"), 91)
    if c is not None: S("netliq", "bull" if c > 1 else "bear" if c < -1 else "neu", f"Fed 순유동성 13주 {c:+.1f}% — " + ("확대=위험자산 우호" if c > 1 else "축소=위험자산 역풍" if c < -1 else "보합"), jv=c, jl="13주 변화 %")
    x = v("m2"); c = chg(s("m2"), 91)
    if x is not None: S("m2", "bull" if (x > 3 and (c or 0) >= 0) else "bear" if x < 1 else "neu", f"M2 YoY {x:+.1f}% — " + ("확장, BTC 는 M2 를 약 10주 후행" if x > 3 else "정체=유동성 부족" if x < 1 else "완만"), jv=x, jl="YoY %")
    x = v("dff"); c = chg(s("dff"), 180)
    if x is not None: S("dff", "bull" if (c or 0) < -3 else "bear" if (c or 0) > 3 else "neu", f"기준금리 {x:.2f}% (6개월 {c:+.0f}%)" if c is not None else f"{x:.2f}%", jv=c, jl="6개월 변화 %")
    c = chg(s("dxy"), 91)
    if c is not None: S("dxy", "bull" if c < -2 else "bear" if c > 2 else "neu", f"DXY 3개월 {c:+.1f}% — 달러 " + ("약세=BTC 우호" if c < -2 else "강세=BTC 역풍" if c > 2 else "보합"), jv=c, jl="3개월 변화 %")
    c = chg(s("us10y"), 91)
    if c is not None: S("us10y", "bull" if c < -5 else "bear" if c > 5 else "neu", f"美10년 3개월 {c:+.0f}% — 금리 " + ("하락=할인율↓" if c < -5 else "상승=할인율↑" if c > 5 else "보합"), jv=c, jl="3개월 변화 %")

    c = chg(s("stable"), 30)
    if c is not None: S("stable", "bull" if c > 1.5 else "bear" if c < -1 else "neu", f"스테이블 공급 30일 {c:+.1f}% — " + ("신규 발행=매수 대기자금 유입" if c > 1.5 else "소각=자금 이탈" if c < -1 else "정체"), jv=c, jl="30일 변화 %")
    # ── 알트 순환 축: bull=알트로 자금 순환 중(알트 우호) · bear=BTC 집중/위험회피 · 과열은 문구로 경고
    x = v("altbreadth")
    if x is not None: S("altbreadth", "bull" if x >= 75 else "bear" if x <= 25 else "neu", f"알트 50 중 {x:.0f}% 가 BTC 를 이김(30D) — " + ("알트시즌 진행 중 — 사이클 후반 과열 경계" if x >= 75 else "BTC 시즌=자금이 BTC 에만" if x <= 25 else "혼재"))
    x = v("btc_dom"); c = None
    if x is not None:
        sd = s("btc_dom"); c = (x - at_back(sd, 30)) if at_back(sd, 30) is not None else None
        S("btc_dom", ("bull" if c < -2 else "bear" if c > 2 else "neu") if c is not None else "neu", f"BTC 도미넌스 {x:.1f}%" + (f" (30일 {c:+.1f}p) — " + ("하락=알트로 순환" if c < -2 else "상승=BTC 집중" if c > 2 else "보합") if c is not None else " — 30일 누적 전(추세 판정 대기)"), jv=c, jl="30일 변화 %p")
    c = chg(s("eth_btc"), 30)
    if c is not None: S("eth_btc", "bull" if c > 8 else "bear" if c < -8 else "neu", f"ETH/BTC {v('eth_btc'):.4f} (30일 {c:+.1f}%) — " + ("ETH 가 BTC 를 이김=알트 순환 시작 신호" if c > 8 else "ETH 가 BTC 에 밀림=BTC 국면" if c < -8 else "보합"), jv=c, jl="30일 변화 %")
    c = chg(s("alt_mcap_ratio"), 30)
    if c is not None: S("alt_mcap_ratio", "bull" if c > 5 else "bear" if c < -5 else "neu", f"알트12/BTC 시총비 {v('alt_mcap_ratio'):.1f}% (30일 {c:+.1f}%) — " + ("알트로 시총 이동" if c > 5 else "BTC 로 시총 집중" if c < -5 else "보합"), jv=c, jl="30일 변화 %")
    c = chg(s("stable_ratio"), 30)
    if c is not None: S("stable_ratio", "bull" if c < -10 else "bear" if c > 10 else "neu", f"스테이블/(BTC+ETH) {v('stable_ratio'):.1f}% (30일 {c:+.1f}%) — " + ("대기자금이 코인으로 투입=위험선호" if c < -10 else "코인→스테이블 대피=위험회피" if c > 10 else "보합"), jv=c, jl="30일 변화 %")
    x = v("eth_netflow")
    if x is not None: S("eth_netflow", "bull" if x < -300 else "bear" if x > 300 else "neu", f"ETH 7일 순유입 {x:+,.0f}M$ — " + ("거래소 유출=보관(알트 대장 수급 우호)" if x < -300 else "거래소 유입=매도 대기" if x > 300 else "균형"))
    r = rank(s("upbit_alt_share"), 200)
    if r is not None: S("upbit_alt_share", "bull" if r >= 80 else "bear" if r <= 20 else "neu", f"업비트 알트 비중 {v('upbit_alt_share'):.0f}% (200일 백분위 {r:.0f}%) — " + ("국내 개미가 알트로 — 순환 진행, 90%↑면 과열" if r >= 80 else "알트 무관심=BTC 국면" if r <= 20 else "보통"), jv=r, jl="200일 백분위 %")
    x = v("alt_funding")
    if x is not None: S("alt_funding", "bear" if x > 0.02 else "bull" if x < -0.01 else "neu", f"알트−BTC 펀딩비 {x:+.4f}% — " + ("알트 롱 레버리지 과열=청산 위험" if x > 0.02 else "알트 숏 과밀=숏스퀴즈 여지" if x < -0.01 else "정상"))

    # 축 점수
    AX = {"short": ["fng", "kimp", "upbit_ratio", "gt_world", "gt_kr", "wiki_ko", "wiki_en", "funding", "ls_ratio", "taker", "oi"],
          "flow":  ["ex_netflow", "ex_supply", "cb_prem", "ibit_flow", "cot_am", "stable", "adr_act"],
          "cycle": ["mvrv", "mvrv_z", "sopr", "nupl", "puell", "mayer", "w200", "hashrate"],
          "macro": ["netliq", "m2", "dff", "dxy", "us10y"],
          "alt":   ["eth_btc", "btc_dom", "alt_mcap_ratio", "stable_ratio", "altbreadth", "upbit_alt_share", "eth_netflow", "alt_funding"]}
    NM = {"short": "단기 과열·심리", "flow": "중기 수급(지갑·기관·대기자금)", "cycle": "사이클 밸류에이션", "macro": "매크로 유동성", "alt": "알트 순환 (BTC↔알트)"}
    axes = {}
    for a, ks in AX.items():
        sc = [{"bull": 1, "neu": 0, "bear": -1}[IND[k]["status"]] for k in ks if IND.get(k, {}).get("status")]
        m = sum(sc) / len(sc) if sc else None
        axes[a] = {"name": NM[a], "score": None if m is None else round(m, 2), "n": len(sc), "keys": ks,
                   "label": "—" if m is None else (("알트 순환 진행" if m >= 0.3 else "BTC 국면" if m <= -0.3 else "혼재") if a == "alt" else ("우호" if m >= 0.3 else "비우호" if m <= -0.3 else "중립")),
                   "bull": sc.count(1), "bear": sc.count(-1)}
    ms = [a["score"] for k, a in axes.items() if a["score"] is not None and k != "alt"]   # 알트 축은 '순환 위치' 질문이라 시장 종합점수에서 제외
    tot = round(sum(ms) / len(ms), 2) if ms else None
    sh, fl, cy, ma = (axes[a]["score"] for a in ("short", "flow", "cycle", "macro"))
    if tot is None: txt = "데이터 부족"
    else:
        parts = []
        if fl is not None: parts.append("수급 " + ("우호" if fl >= 0.3 else "비우호" if fl <= -0.3 else "중립"))
        if ma is not None: parts.append("매크로 " + ("우호" if ma >= 0.3 else "역풍" if ma <= -0.3 else "중립"))
        if cy is not None: parts.append("밸류 " + ("저평가권" if cy >= 0.3 else "과열권" if cy <= -0.3 else "중간"))
        if sh is not None: parts.append("단기 " + ("과열 주의" if sh <= -0.3 else "공포·역발상" if sh >= 0.3 else "중립"))
        head = ("상승 여지 우세" if tot >= 0.25 else "하락·조정 위험 우세" if tot <= -0.25 else "혼조")
        if fl is not None and sh is not None and fl >= 0.3 and sh <= -0.3: head = "추세 유효하나 단기 과열 — 눌림 대기"
        if fl is not None and sh is not None and fl <= -0.3 and sh >= 0.3: head = "공포 국면이나 수급 미확인 — 바닥 확인 전"
        al = axes["alt"]["score"]
        if al is not None:
            ab = v("altbreadth") or 0
            parts.append("알트 " + ("순환 진행(후반 과열 경계)" if al >= 0.3 and ab >= 75 else "순환 진행" if al >= 0.3 else "BTC 국면" if al <= -0.3 else "혼재"))
        txt = head + " · " + " / ".join(parts)
    return axes, {"score": tot, "text": txt}

META = {   # 화면 표기용 이름·단위·그룹·왜 선행인가 (JS 가 그대로 씀)
 "fng":        ("공포·탐욕 지수", "", "심리·한국", "군중 심리의 극단이 단기 반전점을 만든다 — alternative.me"),
 "kimp":       ("김치 프리미엄 BTC", "%", "심리·한국", "업비트÷(바이낸스×환율)−1. 국내 개인 과열·이탈의 온도계"),
 "upbit_ratio":("업비트/바이낸스 BTC 거래대금", "%", "심리·한국", "국내 개인 참여 강도 — 급증은 국내 주도 과열, 급감은 무관심"),
 "gt_world":   ("구글 트렌드 'bitcoin' (전세계)", "", "심리·한국", "검색 관심 지수(5년 주간, 최대=100) — 2017·2021 고점이 모두 검색 정점과 일치"),
 "gt_kr":      ("구글 트렌드 'bitcoin' (한국)", "", "심리·한국", "국내 대중 관심 — 급등은 국내 주도 과열, 바닥권은 무관심"),
 "wiki_ko":    ("위키 '비트코인' 조회수 (KO·7D)", "", "심리·한국", "국내 대중 관심 — 검색 폭증은 가격 정점과 동행 (위키미디어 페이지뷰)"),
 "wiki_en":    ("위키 'Bitcoin' 조회수 (EN·7D)", "", "심리·한국", "글로벌 대중 관심 — 2017·2021 고점 모두 조회수 정점과 일치"),
 "ex_netflow": ("거래소 순유입 (7일 합)", "M$", "지갑·거래소", "거래소로 들어오면 팔려는 것, 나가면 보관하려는 것 — Coin Metrics"),
 "ex_supply":  ("거래소 BTC 보유량", "BTC", "지갑·거래소", "거래소 잔고 감소 = 매도 가능 물량 감소 = 공급 충격 준비"),
 "adr_act":    ("활성 주소 수", "", "지갑·거래소", "실사용·신규 유입의 대리변수 — 가격보다 먼저 꺾이는 경우가 많다"),
 "hashrate":   ("해시레이트 (7D 평균)", "EH/s", "지갑·거래소", "채굴자 항복(급락)은 역사적 바닥 근처, 회복은 확신"),
 "mvrv":       ("MVRV", "x", "온체인 밸류", "시가총액÷실현시총. 1 미만 바닥·3.5 이상 고점 — 사이클 위치의 표준"),
 "mvrv_z":     ("MVRV Z-Score", "", "온체인 밸류", "MVRV 를 변동성으로 표준화 — 0 근처 바닥 밴드, 7 근처 고점 밴드"),
 "sopr":       ("SOPR (7D)", "", "온체인 밸류", "이동한 코인의 실현 손익비. 1 아래 지속=손절 소진, 상승장에선 1 이 지지선"),
 "nupl":       ("NUPL", "", "온체인 밸류", "미실현 순손익 비율 — 항복(<0)·희망·낙관·믿음·도취(>0.75)"),
 "puell":      ("Puell Multiple", "x", "온체인 밸류", "일 채굴수익÷1년 평균 — 채굴자 수익 극단이 고점·바닥"),
 "mayer":      ("Mayer Multiple", "x", "온체인 밸류", "가격÷200일선 — 2.4 이상 과열, 0.8 이하 저평가"),
 "w200":       ("200주 이평 배율", "x", "온체인 밸류", "역사적 모든 약세장 바닥이 200주선 근처에서 형성"),
 "halving":    ("반감기 경과", "일", "온체인 밸류", "공급 감소 → 12~18개월 뒤 고점의 4년 주기 (과거 3회)"),
 "cb_prem":    ("코인베이스 프리미엄", "%", "기관", "미국 기관·ETF 는 코인베이스에서 산다 — 프리미엄=미국 매수 우세"),
 "ibit_flow":  ("IBIT 순유입 프록시", "M$", "기관", "발행주식 증감×NAV. 현물 ETF 유입은 2024 이후 최대 수급원(IBIT≈절반)"),
 "cot_am":     ("CFTC 자산운용사 순포지션", "계약", "기관", "CME 비트코인 선물의 실수요 기관 순롱 — 주간"),
 "cot_lev":    ("CFTC 레버리지펀드 순포지션", "계약", "기관", "헤지펀드 순숏=베이시스 차익거래. 숏 급감은 차익거래 청산=위험선호 후퇴"),
 "funding":    ("펀딩비 (일평균)", "%", "파생", "무기한 선물 롱·숏 균형가. 높으면 롱 과열=청산 위험, 음수면 숏 과밀"),
 "oi":         ("미결제약정 (Binance)", "B$", "파생", "레버리지 누적 규모 — 가격 정체 속 급증은 변동성 폭발 전조"),
 "ls_ratio":   ("롱/숏 계좌 비율", "", "파생", "개인 포지션 쏠림 — 역발상 지표"),
 "taker":      ("테이커 매수/매도 비", "", "파생", "시장가 공격 매수 vs 매도 — 실제 수요 방향"),
 "dvol":       ("DVOL (BTC 내재변동성)", "", "파생", "옵션이 보는 변동성 — 압축 후 폭발, 극단 공포는 바닥"),
 "netliq":     ("Fed 순유동성 (WALCL−TGA−RRP)", "B$", "매크로", "달러 시스템 유동성 — BTC 와 상관 가장 높은 매크로 변수"),
 "m2":         ("美 M2 YoY", "%", "매크로", "통화량 확장을 BTC 가 약 10주 후행 추종한다는 것이 가장 유명한 매크로 선행"),
 "dff":        ("연방기금금리", "%", "매크로", "인하 사이클=위험자산 우호 (단, 경기침체형 인하는 예외)"),
 "dxy":        ("달러지수 DXY", "", "매크로", "달러 약세 = BTC 강세의 역상관"),
 "us10y":      ("美 10년 국채금리", "%", "매크로", "할인율 — 상승은 성장·위험자산 밸류에이션 압박"),
 "stable":     ("스테이블코인 총공급", "B$", "대기자금", "USDT·USDC 신규 발행 = 거래소에 들어온 매수 대기 달러 — DefiLlama"),
 "eth_btc":    ("ETH/BTC 비율", "", "알트", "알트시즌의 고전적 방아쇠 — ETH 가 BTC 를 이기기 시작하면 알트 전체로 번진다"),
 "alt_mcap_ratio": ("주요 알트12 시총 / BTC 시총", "%", "알트", "시총이 BTC 에서 알트로 이동하는지 — 순환의 직접 측정 (Coin Metrics 구형 대형알트 바스켓)"),
 "stable_ratio": ("스테이블 공급 / (BTC+ETH 시총)", "%", "알트", "대기자금 비중 — 떨어지면 돈이 코인으로 들어가는 중(위험선호), 오르면 대피"),
 "eth_netflow": ("ETH 거래소 순유입 (7일 합)", "M$", "알트", "알트 대장의 거래소 유출입 — BTC 와 같은 논리"),
 "upbit_alt_share": ("업비트 알트 거래대금 비중", "%", "알트", "한국 개미는 알트에 몰린다 — 국내 과열은 김프보다 이 지표가 빠르다"),
 "alt_funding": ("알트 − BTC 펀딩비 격차", "%", "알트", "알트 무기한 선물 레버리지가 BTC 보다 얼마나 과열됐나"),
 "altbreadth": ("알트 강세 폭 (30D)", "%", "알트", "시총 50 중 BTC 를 이긴 비율 — 75%↑ 알트시즌=사이클 후반"),
 "btc_dom":    ("BTC 도미넌스", "%", "알트", "자금 순환 위치 — BTC 집중(초기) → 알트 확산(후기)"),
}

def main():
    log("[cryptolead] 수집 시작")
    prev = jload(OUT).get("ind") or {}
    hist = jload(HIST)
    try:
        d_px, qv, wk = price_btc()
        IND["_px"] = {"s": trim(d_px, 1000)}     # (2026-09-05 피드백) 전 카드 차트에 BTC 가격 오버레이 — Binance 일봉 최대 1000일
    except Exception as e:
        err("price", e); d_px, qv, wk = [], [], []
    for name, fn in (("sentiment", lambda: c_sentiment(qv)), ("coinmetrics", c_coinmetrics),
                     ("cycle", lambda: c_cycle(d_px, wk)), ("institution", lambda: c_institution(d_px, hist)),
                     ("derivs", lambda: c_derivs(hist)), ("macro", c_macro), ("stable", c_stable),
                     ("alt", lambda: c_alt(hist)), ("altcycle", lambda: c_altcycle(hist)), ("bitcoindata", lambda: c_bitcoindata(prev))):
        try:
            t = time.time(); fn(); log(f"  ✓ {name} {time.time() - t:.1f}s")
        except Exception as e: err(name, e)
    # 실패한 지표는 직전 값 유지(stale 표시)
    for k, e in prev.items():
        if k not in IND and e.get("s"):
            IND[k] = e; IND[k]["stale"] = True
    if IND.get("gt_world", {}).get("s"):            # 구글 트렌드가 살아 있으면 위키 폴백은 화면에서 뺀다(직전값 잔존 방지)
        IND.pop("wiki_ko", None); IND.pop("wiki_en", None)
    axes, overall = judge()
    for k, m in META.items():
        if k in IND: IND[k].update(name=m[0], unit=m[1], group=m[2], why=m[3])
    policy = jload(DB / "cryptolead_policy.json")
    DB.mkdir(parents=True, exist_ok=True)
    now = datetime.now(KST)
    OUT.write_text(json.dumps({"as_of": now.strftime("%Y-%m-%d %H:%M"), "marker": now.strftime("%Y-%m-%d"),
                               "ind": IND, "axes": axes, "overall": overall, "policy": policy,
                               "groups": ["심리·한국", "지갑·거래소", "온체인 밸류", "기관", "파생", "매크로", "대기자금", "알트"],   # 알트 = 5번째 축(순환)
                               "errors": ERRORS}, ensure_ascii=False), encoding="utf-8")
    HIST.write_text(json.dumps(hist, ensure_ascii=False), encoding="utf-8")
    log(f"[cryptolead] ✅ {len([k for k in IND if not k.startswith('_')])}개 지표 · 종합 {overall} · 오류 {len(ERRORS)} → {OUT}")

if __name__ == "__main__":
    main()
