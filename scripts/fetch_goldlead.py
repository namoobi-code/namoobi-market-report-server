#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fetch_goldlead.py — 🥇 금 선행지표 수집 + 통설 vs 실측 (2026-09-22 신설)

코인 선행 탭(fetch_cryptolead.py)과 같은 구조. LLM 토큰 0 — 전부 무료·무인증/기보유 키.
인스타 '금 가격 핵심 공식' 류의 9개 통설(인플레↑·미국 강세↓·혼란↑·달러↓/↑·전쟁↑·종전↓·금리↑↓)을
지표로 환원하면 사실상 5개다: 실질금리 · 달러 · 인플레 · 기준금리 · 지정학. 그 5개를 매일 관측하고,
**20년 월간 데이터로 금 12개월 수익률과의 시차 상관을 실측**해 통설이 맞는지 표로 보여준다(RE 탭 방식).

축 (6) — 각 수집기는 독립 try/except, 실패 항목은 직전 값 유지(stale)
  ① 실질금리·달러 : FRED DFII10(10Y TIPS 실질금리)·T10YIE(BEI)·DFF·CPI YoY(CPIAUCSL) · Yahoo DXY
  ② 지정학·공포   : GPR 지수(Caldara-Iacoviello 월간 xls, 1985~) · VIX
  ③ 포지셔닝     : CFTC Disaggregated — COMEX 금(088691) 운용사(Managed Money) 순포지션·OI (주간, 연도 zip 백필)
  ④ ETF 수급      : IAU(iShares Gold Trust) 발행주식수×NAV 일간 누적 → 순유입 프록시 (GLD 는 CSV 가 PDF 로 막혀 제외)
  ⑤ 한국·심리     : KRX 금현물 vs 국제금(달러×환율) 괴리율 = 한국 프리미엄(김프의 금 버전) · 구글 트렌드 'gold price' 전세계·한국
  ⑥ 상대가격      : 금/은 비율 · 금/유가 비율 · GDX/GLD 상대강도(광산주가 금에 선행하는 경향)

산출: data/db/goldlead.json (화면) · data/db/goldlead_hist.json (일간 누적)
cron: 5 7 * * *
"""
import csv, io, json, re, sys, time, zipfile, urllib.request
from datetime import datetime, timedelta, timezone, date
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DB   = BASE / "data" / "db"
OUT  = DB / "goldlead.json"
HIST = DB / "goldlead_hist.json"
KST  = timezone(timedelta(hours=9))
UA   = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"}
sys.path.insert(0, str(BASE / "scripts"))
try:
    from nmr_fred import fred_series
except Exception:
    fred_series = None
OZ = 31.1034768

ERRORS = []
def log(m): print(m, flush=True)
def err(k, e): ERRORS.append(f"{k}: {repr(e)[:90]}"); log(f"  ⚠ {k}: {repr(e)[:120]}")
def get(url, t=25, hdr=None, raw=False, tries=2):
    last_e = None
    for i in range(tries):
        try:
            b = urllib.request.urlopen(urllib.request.Request(url, headers={**UA, **(hdr or {})}), timeout=t).read()
            return b if raw else b.decode("utf-8", "replace")
        except Exception as e:
            last_e = e; time.sleep(1.5 * (i + 1))
    raise last_e
def jget(url, **kw): return json.loads(get(url, **kw))
def jload(p, default=None):
    try: return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception: return default if default is not None else {}
def today(): return datetime.now(KST).strftime("%Y-%m-%d")
def utc(ts): return datetime.fromtimestamp(ts, timezone.utc)
def last(s): return s[-1][1] if s else None
def at_back(s, n):
    if not s: return None
    d0 = datetime.strptime(s[-1][0], "%Y-%m-%d") - timedelta(days=n); prev = None
    for d, v in s:
        if datetime.strptime(d, "%Y-%m-%d") <= d0: prev = v
        else: break
    return prev
def pct(a, b): return None if (a is None or b in (None, 0)) else (a / b - 1) * 100
def chg(s, n): return pct(last(s), at_back(s, n))
def diff(s, n):
    a, b = last(s), at_back(s, n); return None if a is None or b is None else a - b
def rank(s, n=365):
    vals = [v for _, v in s[-n:] if v is not None]
    if len(vals) < 10: return None
    return sum(1 for v in vals if v <= vals[-1]) / len(vals) * 100
def trim(s, n=400): return [[d, (round(v, 4) if isinstance(v, float) else v)] for d, v in s[-n:]]

IND = {}
def put(key, s=None, v=None, **kw):
    e = IND.setdefault(key, {})
    if s is not None: e["s"] = trim(s); e["v"] = last(s); e["d"] = s[-1][0]
    if v is not None: e["v"] = v
    e.update(kw)

def yahoo(sym, rng="1y", itv="1d"):
    j = jget(f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.request.quote(sym)}?range={rng}&interval={itv}")["chart"]["result"][0]
    ts, cl = j["timestamp"], j["indicators"]["quote"][0]["close"]
    return [[utc(t).strftime("%Y-%m-%d"), float(c)] for t, c in zip(ts, cl) if c is not None]

# ── ① 실질금리·달러 ────────────────────────────────────────────────────────
def c_rates():
    if not fred_series: raise RuntimeError("nmr_fred 없음")
    s3 = (date.today() - timedelta(days=3 * 365)).isoformat()
    put("real10", s=fred_series("DFII10", start=s3))
    put("bei", s=fred_series("T10YIE", start=s3))
    dff = fred_series("DFF", start=(date.today() - timedelta(days=400)).isoformat())
    put("dff", s=dff[::7] + ([dff[-1]] if dff and dff[-1] not in dff[::7] else []))
    cpi = fred_series("CPIAUCSL", start=(date.today() - timedelta(days=6 * 365)).isoformat())
    put("cpi", s=[[cpi[i][0], (cpi[i][1] / cpi[i - 12][1] - 1) * 100] for i in range(12, len(cpi))])
def c_dxy():
    put("dxy", s=yahoo("DX-Y.NYB", "1y"))

# ── ② 지정학·공포 ────────────────────────────────────────────────────────
def c_gpr():
    import xlrd
    b = get("https://www.matteoiacoviello.com/gpr_files/data_gpr_export.xls", t=60, raw=True)
    wb = xlrd.open_workbook(file_contents=b); sh = wb.sheet_by_index(0)
    hdr = [str(c.value).strip() for c in sh.row(0)]
    ci = hdr.index("GPR") if "GPR" in hdr else next(i for i, h in enumerate(hdr) if h.upper().startswith("GPR"))
    mi = next(i for i, h in enumerate(hdr) if h.lower() in ("month", "date"))
    s = []
    for r in range(1, sh.nrows):
        m, v = sh.cell(r, mi), sh.cell(r, ci)
        if v.value in ("", None): continue
        if m.ctype == xlrd.XL_CELL_DATE:
            y, mo, *_ = xlrd.xldate_as_tuple(m.value, wb.datemode); d = f"{y:04d}-{mo:02d}-01"
        else:
            t = str(m.value).strip(); d = t[:10] if len(t) >= 7 else None
            if d and len(d) == 7: d += "-01"
        if d: s.append([d, float(v.value)])
    s = sorted(s)
    IND["_gpr_full"] = {"s": [[d, round(v, 2)] for d, v in s]}      # 통설검증용 전기간
    put("gpr", s=s[-240:])
def c_vix():
    put("vix", s=yahoo("^VIX", "1y"))

# ── ③ CFTC 포지셔닝 (Disaggregated, 선물만) ──────────────────────────────
def c_cot(hist):
    H = hist.setdefault("cot", {})
    def parse(txt):
        rd = csv.reader(io.StringIO(txt)); hdr = next(rd)
        idx = {h.strip(): i for i, h in enumerate(hdr)}
        need = ("Report_Date_as_YYYY-MM-DD", "CFTC_Contract_Market_Code", "Open_Interest_All",
                "M_Money_Positions_Long_All", "M_Money_Positions_Short_All", "Prod_Merc_Positions_Long_All", "Prod_Merc_Positions_Short_All")
        if not all(n in idx for n in need):
            # 헤더 없는 newcot 형식(주간 파일)은 열 위치 고정: 2=날짜(yymmdd) 3=코드 7=OI 13/14=MM L/S 8/9=PM L/S
            for row in [hdr] + list(rd):
                if len(row) > 14 and row[3].strip() == "088691":
                    d = row[2].strip(); d = f"20{d[:2]}-{d[2:4]}-{d[4:6]}" if len(d) == 6 else d
                    H[d] = [int(row[7]), int(row[13]) - int(row[14]), int(row[8]) - int(row[9])]
            return
        for row in rd:
            if len(row) <= max(idx.values()): continue
            if row[idx["CFTC_Contract_Market_Code"]].strip() == "088691":
                H[row[idx["Report_Date_as_YYYY-MM-DD"]].strip()] = [int(row[idx["Open_Interest_All"]]),
                    int(row[idx["M_Money_Positions_Long_All"]]) - int(row[idx["M_Money_Positions_Short_All"]]),
                    int(row[idx["Prod_Merc_Positions_Long_All"]]) - int(row[idx["Prod_Merc_Positions_Short_All"]])]
    if len(H) < 20:
        for y in (date.today().year - 1, date.today().year):
            try:
                b = get(f"https://www.cftc.gov/files/dea/history/fut_disagg_txt_{y}.zip", t=90, raw=True)
                z = zipfile.ZipFile(io.BytesIO(b)); parse(z.read(z.namelist()[0]).decode("utf-8", "replace"))
            except Exception as e: err(f"cot_zip{y}", e)
    parse(get("https://www.cftc.gov/dea/newcot/f_disagg.txt", t=60))
    ks = sorted(H)
    put("cot_mm", s=[[k, H[k][1]] for k in ks], oi=[[k, H[k][0]] for k in ks][-60:])
    put("cot_pm", s=[[k, H[k][2]] for k in ks])

# ── ④ ETF 수급 (IAU) ───────────────────────────────────────────────────────
def c_etf(hist):
    t = get("https://www.ishares.com/us/products/239561/ishares-gold-trust-fund", t=30)
    sh = re.search(r"Shares Outstanding.{0,400}?([\d,]{6,})", t, re.S)
    na = re.search(r"Net Assets of Fund[^$]{0,200}\$\s*([\d,\.]+)", t, re.S)
    asof = re.search(r"as of ([A-Z][a-z]{2} \d{1,2}, \d{4})", t)
    if not (sh and na): raise RuntimeError("IAU 페이지 파싱 실패")
    shares = float(sh.group(1).replace(",", "")); nav_tot = float(na.group(1).replace(",", ""))
    d = datetime.strptime(asof.group(1), "%b %d, %Y").strftime("%Y-%m-%d") if asof else today()
    H = hist.setdefault("iau", {}); H[d] = [shares, nav_tot]
    ks = sorted(H); flow = []
    for i in range(1, len(ks)):
        s0, n0 = H[ks[i - 1]]; s1, n1 = H[ks[i]]
        flow.append([ks[i], (s1 - s0) * (n1 / s1) / 1e6])
    put("iau_flow", s=flow if flow else [[d, 0.0]], shares=shares, aum=nav_tot, asof=d, pts=len(ks))

# ── ⑤ 한국·심리 ───────────────────────────────────────────────────────────
def c_korea(d_px):
    gh = jload(DB / "global_hist.json").get("ND.GOLD_KR") or {}
    kr = {f"{t[:4]}-{t[4:6]}-{t[6:]}": v for t, v in zip(gh.get("t") or [], gh.get("v") or []) if v}
    fx = dict(yahoo("KRW=X", "5y")); gd = dict(d_px)
    s = []
    for d in sorted(kr):
        if d in fx and d in gd and gd[d]:
            intl = gd[d] * fx[d] / OZ                      # 국제금 원/g 환산
            s.append([d, (kr[d] / intl - 1) * 100])
    if s: put("kr_prem", s=s, krx=kr[sorted(kr)[-1]])
    put("krx_gold", s=[[d, kr[d]] for d in sorted(kr)])
def c_trends():
    import warnings; warnings.filterwarnings("ignore")
    from pytrends.request import TrendReq
    for geo, key in (("", "gt_world"), ("KR", "gt_kr")):
        pt = TrendReq(hl="en-US", tz=540, timeout=(10, 25))
        pt.build_payload(["gold price"], timeframe="today 5-y", geo=geo)
        df = pt.interest_over_time()
        s = [[str(i)[:10], float(v)] for i, v in zip(df.index, df["gold price"])]
        if len(s) > 50: put(key, s=s)
        time.sleep(4)

# ── ⑥ 상대가격 ───────────────────────────────────────────────────────────
def c_ratios(d_px):
    gd = dict(d_px)
    si = dict(yahoo("SI=F", "2y")); cl = dict(yahoo("CL=F", "2y")); gdx = dict(yahoo("GDX", "2y")); gld = dict(yahoo("GLD", "2y"))
    put("gs_ratio", s=[[d, gd[d] / si[d]] for d in sorted(si) if d in gd and si[d]])
    put("go_ratio", s=[[d, gd[d] / cl[d]] for d in sorted(cl) if d in gd and cl[d]])
    rs = [[d, gdx[d] / gld[d]] for d in sorted(gdx) if d in gld and gld[d]]
    put("gdx_rs", s=rs)

# ── 통설 vs 실측 (20년 월간) ────────────────────────────────────────────────
def c_myth():
    """금 12M 선행 수익률 vs 지표(12M 변화 또는 수준) 의 시차별 상관. 통설 부호와 대조."""
    gm = yahoo("GC=F", "max", "1mo")
    gm = {d[:7]: v for d, v in gm}
    months = sorted(gm)
    def fwd12(m):
        i = months.index(m); return None if i + 12 >= len(months) else (gm[months[i + 12]] / gm[m] - 1) * 100
    def monthly(s):
        o = {}
        for d, v in s: o[d[:7]] = v
        return o
    s6 = "2000-01-01"
    X = {}
    if fred_series:
        try:
            cpi = monthly(fred_series("CPIAUCSL", start=s6)); ks = sorted(cpi)
            X["cpi"] = {ks[i]: (cpi[ks[i]] / cpi[ks[i - 12]] - 1) * 100 for i in range(12, len(ks))}
            X["real10"] = monthly(fred_series("DFII10", start="2003-01-01"))
            X["dff"] = monthly(fred_series("DFF", start=s6))
        except Exception as e: err("myth_fred", e)
    # 달러: 야후 DXY 월봉은 2019~ 뿐(1차 실측 n=79) → FRED 광의 달러지수 DTWEXBGS(2006~)로 대체
    try:
        if fred_series: X["dxy"] = monthly(fred_series("DTWEXBGS", start="2006-01-01"))
        else: X["dxy"] = monthly(yahoo("DX-Y.NYB", "max", "1mo"))
    except Exception as e: err("myth_dxy", e)
    try: X["vix"] = monthly(yahoo("^VIX", "max", "1mo"))
    except Exception as e: err("myth_vix", e)
    if IND.get("_gpr_full"): X["gpr"] = monthly(IND["_gpr_full"]["s"])
    # 통설: (지표, 통설 부호, 설명) — 변화 기준(12M Δ)으로 검정
    MYTH = [("cpi", +1, "인플레 상승 → 금 상승"), ("real10", -1, "실질금리 상승 → 금 하락 (교과서)"),
            ("dxy", -1, "달러 강세 → 금 하락"), ("dff", -1, "기준금리 인상 → 금 하락"),
            ("gpr", +1, "지정학 위험(전쟁) 상승 → 금 상승"), ("vix", +1, "시장 공포 상승 → 금 상승")]
    def corr(a, b):
        n = len(a)
        if n < 24: return None
        ma, mb = sum(a) / n, sum(b) / n
        sa = sum((x - ma) ** 2 for x in a) ** .5; sb = sum((y - mb) ** 2 for y in b) ** .5
        return None if not sa or not sb else sum((x - ma) * (y - mb) for x, y in zip(a, b)) / sa / sb
    out = []
    for k, sign, txt in MYTH:
        if k not in X: continue
        xs = X[k]; km = sorted(xs)
        dx = {km[i]: xs[km[i]] - xs[km[i - 12]] for i in range(12, len(km))}     # 지표 12M 변화(수준차)
        rows = []
        # 동행(같은 12개월 창) — 통설은 "같이 움직인다"는 주장이므로 이 행이 통설 검증의 정본.
        # 아래 lag 행은 "지표가 먼저 움직이고 금이 따라오나"(예측력) — 다른 질문이다. 1차 실측에서
        # 실질금리가 lag 행만으로 '부호 반대'(+0.49)로 나왔는데, 이는 급등 뒤 되돌림(평균회귀)이지
        # 통설이 틀렸다는 뜻이 아니었다 → 두 질문을 분리해 표기한다.
        a, b = [], []
        for m in months:
            i = months.index(m)
            if i + 12 < len(months) and months[i + 12] in dx and fwd12(m) is not None:
                a.append(dx[months[i + 12]]); b.append(fwd12(m))
        r0 = corr(a, b); rows.append({"lag": "동행", "r": None if r0 is None else round(r0, 3), "n": len(a)})
        for lag in (3, 6, 12):
            a, b = [], []
            for m in months:
                i = months.index(m) - lag
                if i < 0: continue
                mm = months[i]
                if mm in dx and fwd12(m) is not None:
                    a.append(dx[mm]); b.append(fwd12(m))
            r = corr(a, b)
            rows.append({"lag": lag, "r": None if r is None else round(r, 3), "n": len(a)})
        co = rows[0]["r"]
        verdict = "표본 부족" if co is None else ("통설대로" if co * sign > 0.15 else "부호 반대" if co * sign < -0.15 else "유의미하지 않음(|r|<0.15)")
        lead = max([r for r in rows[1:] if r["r"] is not None], key=lambda r: abs(r["r"]), default=None)
        km0 = sorted(dx)
        out.append({"key": k, "myth": txt, "sign": sign, "lags": rows, "co": co, "lead": lead, "verdict": verdict,
                    "period": f"{km0[0][:4]}~{km0[-1][:4]}"})
    IND["_myth"] = out

# ── 판정 ───────────────────────────────────────────────────────────────────
def judge():
    def S(k, st, txt, jv=None, jl=None):
        e = IND.setdefault(k, {}); e.update(status=st, judge=txt)
        if jv is not None: e.update(jv=round(jv, 3), jl=jl)
    v = lambda k: IND.get(k, {}).get("v"); s = lambda k: IND.get(k, {}).get("s") or []
    x = diff(s("real10"), 90)
    if x is not None: S("real10", "bull" if x <= -0.25 else "bear" if x >= 0.25 else "neu", f"3개월 {x:+.2f}%p (현재 {v('real10'):.2f}%) — " + ("실질금리 하락=금 보유 기회비용 감소(우호)" if x <= -0.25 else "실질금리 상승=금 역풍(교과서 1순위 변수)" if x >= 0.25 else "보합"), jv=x, jl="3M Δ %p")
    x = diff(s("bei"), 90)
    if x is not None: S("bei", "bull" if x >= 0.15 else "bear" if x <= -0.15 else "neu", f"3개월 {x:+.2f}%p (현재 {v('bei'):.2f}%) — " + ("기대인플레 상승=금 우호" if x >= 0.15 else "기대인플레 하락" if x <= -0.15 else "보합"), jv=x, jl="3M Δ %p")
    x = chg(s("dxy"), 90)
    if x is not None: S("dxy", "bull" if x <= -2 else "bear" if x >= 2 else "neu", f"3개월 {x:+.1f}% — " + ("달러 약세=금 우호" if x <= -2 else "달러 강세=금 역풍" if x >= 2 else "보합"), jv=x, jl="3M %")
    x = diff(s("dff"), 180)
    if x is not None: S("dff", "bull" if x <= -0.25 else "bear" if x >= 0.25 else "neu", f"6개월 {x:+.2f}%p (현재 {v('dff'):.2f}%) — " + ("인하 사이클" if x <= -0.25 else "인상 사이클" if x >= 0.25 else "동결"), jv=x, jl="6M Δ %p")
    x = v("cpi")
    if x is not None:
        r = v("real10")
        S("cpi", "neu", f"CPI YoY {x:.1f}% — 통설은 '인플레↑=금↑'이지만 실측은 실질금리가 결정(2022년 CPI 9% 에도 금 보합). 참고 지표" + (f" · 실질금리 {r:.2f}%" if r is not None else ""))
    r = rank(s("gpr"), 240)
    if r is not None: S("gpr", "bull" if r >= 80 else "neu", f"20년 백분위 {r:.0f}% (지수 {v('gpr'):.0f}) — " + ("지정학 위험 상위권=안전자산 수요" if r >= 80 else "보통 — 지정학은 급등 국면만 금에 반영되고 평시엔 무관"), jv=r, jl="20Y 백분위 %")
    x = v("vix")
    if x is not None: S("vix", "bull" if x >= 25 else "neu", f"{x:.1f} — " + ("공포 국면=금 수요·단, 유동성 위기 초기엔 금도 같이 팔림(2020-03)" if x >= 25 else "평온"))
    r = rank(s("cot_mm"), 260)
    if r is not None: S("cot_mm", "bear" if r >= 90 else "bull" if r <= 15 else "neu", f"운용사 순롱 {v('cot_mm'):,.0f}계약 · 1년 백분위 {r:.0f}% — " + ("투기 롱 과밀=단기 조정 취약" if r >= 90 else "투기 포지션 청산됨=바닥권 특징" if r <= 15 else "보통"), jv=r, jl="1Y 백분위 %")
    x = v("cot_pm")
    if x is not None: S("cot_pm", "neu", f"생산·상업 순포지션 {x:,.0f}계약 — 생산자 헤지 숏이 정상. 숏 축소는 생산자도 가격 상승 예상(참고)")
    e = IND.get("iau_flow", {})
    if e.get("s"):
        f5 = sum(vv for _, vv in e["s"][-5:])
        S("iau_flow", "bull" if f5 >= 100 else "bear" if f5 <= -100 else "neu", f"최근 5일 {f5:+,.0f}M$ (AUM ${e.get('aum',0)/1e9:.1f}B · 누적 {e.get('pts')}일) — " + ("ETF 유입=서구 투자 수요 회복" if f5 >= 100 else "ETF 환매" if f5 <= -100 else "중립") + ("" if e.get("pts", 0) > 5 else " · 누적 초기라 판정 유보"), jv=f5, jl="5D 합 M$")
    x = v("kr_prem")
    if x is not None: S("kr_prem", "bear" if x >= 5 else "bull" if x <= 0 else "neu", f"{x:+.2f}% — " + ("국내 금 과열(프리미엄 5%↑ — 2025-02 20% 급등 후 급락 전례)" if x >= 5 else "국내 프리미엄 소멸=개인 관심 식음" if x <= 0 else "정상 범위(1~3%)"), jv=x, jl="%")
    for k in ("gt_world", "gt_kr"):
        r = rank(s(k), 261)
        if r is not None: S(k, "bear" if r >= 90 else "bull" if r <= 20 else "neu", f"5년 백분위 {r:.0f}% (지수 {v(k):.0f}/100) — " + ("검색 폭증=대중 관심 정점(단기 고점 동행)" if r >= 90 else "무관심=역발상" if r <= 20 else "보통"), jv=r, jl="5년 백분위 %")
    x = v("gs_ratio")
    if x is not None: S("gs_ratio", "neu", f"{x:.1f} — 80↑ 이면 은 대비 금 고평가(은이 따라 오르거나 금이 쉬는 구간), 60↓ 은 금 저평가. 장기 평균 ~65")
    x = v("go_ratio")
    if x is not None: S("go_ratio", "neu", f"{x:.1f}배럴 — 30↑ 은 '금 비싸고 유가 싸다'=경기둔화·완화 기대 구간, 15↓ 은 인플레·경기과열 구간")
    x = chg(s("gdx_rs"), 60)
    if x is not None: S("gdx_rs", "bull" if x >= 5 else "bear" if x <= -5 else "neu", f"60일 {x:+.1f}% — " + ("광산주가 금을 앞서 오름=금 강세 확신(광산주는 금의 레버리지)" if x >= 5 else "광산주가 금보다 약함=금 랠리 의심 신호" if x <= -5 else "동행"), jv=x, jl="60D %")

    AX = {"rate": ["real10", "bei", "dxy", "dff"], "risk": ["gpr", "vix"], "pos": ["cot_mm", "iau_flow", "gdx_rs"], "kr": ["kr_prem", "gt_world", "gt_kr"]}
    NM = {"rate": "실질금리·달러 (핵심)", "risk": "지정학·공포", "pos": "포지셔닝·ETF·광산주", "kr": "한국·대중 심리 (과열 감지)"}
    axes = {}
    for a, ks in AX.items():
        sc = [{"bull": 1, "neu": 0, "bear": -1}[IND[k]["status"]] for k in ks if IND.get(k, {}).get("status")]
        m = sum(sc) / len(sc) if sc else None
        axes[a] = {"name": NM[a], "score": None if m is None else round(m, 2), "n": len(sc), "keys": ks,
                   "label": "—" if m is None else ("우호" if m >= 0.3 else "비우호" if m <= -0.3 else "중립"), "bull": sc.count(1), "bear": sc.count(-1)}
    w = {"rate": 2, "risk": 1, "pos": 1, "kr": 1}           # 실질금리·달러 축 가중 2배 — 실측 상관이 가장 강한 축
    ms = [(axes[a]["score"], w[a]) for a in axes if axes[a]["score"] is not None]
    tot = round(sum(s * ww for s, ww in ms) / sum(ww for _, ww in ms), 2) if ms else None
    if tot is None: txt = "데이터 부족"
    else:
        ra, kr = axes["rate"]["score"], axes["kr"]["score"]
        head = "상승 우호" if tot >= 0.25 else "역풍 우세" if tot <= -0.25 else "혼조"
        if ra is not None and kr is not None and ra >= 0.3 and kr <= -0.3: head = "매크로 우호나 국내·대중 과열 — 눌림 대기"
        if ra is not None and ra <= -0.3: head = "실질금리·달러 역풍 — 금 추세 의심"
        txt = head + " · " + " / ".join(f"{axes[a]['name'].split(' ')[0]} {axes[a]['label']}" for a in axes if axes[a]["score"] is not None)
    return axes, {"score": tot, "text": txt}

META = {
 "real10":  ("10년 실질금리 (TIPS)", "%", "실질금리·달러", "금은 이자가 없다 — 실질금리가 오르면 금 보유의 기회비용이 커진다. 2013·2022 금 약세의 주범. FRED DFII10"),
 "bei":     ("10년 기대인플레 (BEI)", "%", "실질금리·달러", "명목금리−실질금리. 기대인플레 상승은 실질금리를 낮춰 금에 우호 — 통설 '인플레→금'의 실제 경로"),
 "dxy":     ("달러지수 DXY", "", "실질금리·달러", "금은 달러로 표시 — 달러 약세면 같은 금이 더 비싸진다. 단 2024~25 는 달러·금 동반 강세(중앙은행 매수)로 통설이 깨진 구간"),
 "dff":     ("연방기금금리", "%", "실질금리·달러", "인하 사이클=금 우호 통설. 단 인하 '기대'가 먼저 반영돼 실제 인하 시점엔 되돌림도 잦다"),
 "cpi":     ("美 CPI YoY", "%", "실질금리·달러", "통설 1번 '인플레↑=금↑'. 실측은 CPI 자체보다 실질금리가 결정 — 2022 CPI 9% 에도 금 보합"),
 "gpr":     ("지정학 위험 지수 (GPR)", "", "지정학·공포", "Caldara-Iacoviello 월간(1985~). 전쟁·테러 보도 빈도 — 통설 '전쟁→금'의 정량 검증 도구"),
 "vix":     ("VIX", "", "지정학·공포", "시장 공포. 금은 공포 초기에 같이 팔리고(유동성 확보) 이후 안전자산으로 회복하는 2단계 패턴"),
 "cot_mm":  ("CFTC 운용사(투기) 순포지션", "계약", "포지셔닝·ETF·광산주", "COMEX 금 선물 Managed Money 순롱 — 과밀이면 조정 취약, 청산되면 바닥권. 주간"),
 "cot_pm":  ("CFTC 생산·상업 순포지션", "계약", "포지셔닝·ETF·광산주", "광산·정련사 헤지 — 보통 순숏. 숏 축소는 생산자도 상승을 본다는 뜻(참고)"),
 "iau_flow":("IAU 순유입 프록시", "M$", "포지셔닝·ETF·광산주", "iShares Gold Trust 발행주식 증감×NAV. 서구 투자수요의 온도계 — 2020·2024~25 랠리의 확인 지표"),
 "gdx_rs":  ("GDX/GLD 상대강도", "x", "포지셔닝·ETF·광산주", "광산주는 금의 레버리지 — 금보다 먼저 오르면 강세 확신, 뒤처지면 랠리 의심"),
 "kr_prem": ("한국 금 프리미엄 (KRX 금현물)", "%", "한국·대중 심리", "KRX 금현물(원/g) ÷ 국제금×환율 − 1. 김프의 금 버전 — 2025-02 프리미엄 20% 급등 뒤 급락 전례"),
 "krx_gold":("KRX 금현물 (원/g)", "원", "한국·대중 심리", "국내 금 시세 — 환율 효과 포함"),
 "gt_world":("구글 트렌드 'gold price' (전세계)", "", "한국·대중 심리", "대중 관심 정점은 단기 고점과 동행하는 경향(5년 주간)"),
 "gt_kr":   ("구글 트렌드 'gold price' (한국)", "", "한국·대중 심리", "국내 대중 관심 — 급등은 국내 주도 과열"),
 "gs_ratio":("금/은 비율", "x", "상대가격", "80↑ 금 고평가·60↓ 저평가. 은은 금 랠리 후반에 따라붙는다"),
 "go_ratio":("금/유가 비율", "배럴", "상대가격", "'금 비싸고 기름 싸다'=경기둔화·완화 기대. 실질금리와 함께 보면 국면이 읽힌다"),
}
GROUPS = ["실질금리·달러", "지정학·공포", "포지셔닝·ETF·광산주", "한국·대중 심리", "상대가격"]

def main():
    log("[goldlead] 수집 시작")
    prev = jload(OUT).get("ind") or {}
    hist = jload(HIST)
    try:
        d_px = yahoo("GC=F", "5y"); IND["_px"] = {"s": trim(d_px, 1300)}
    except Exception as e:
        err("price", e); d_px = []
    for name, fn in (("rates", c_rates), ("dxy", c_dxy), ("gpr", c_gpr), ("vix", c_vix), ("cot", lambda: c_cot(hist)),
                     ("etf", lambda: c_etf(hist)), ("korea", lambda: c_korea(d_px)), ("trends", c_trends),
                     ("ratios", lambda: c_ratios(d_px)), ("myth", c_myth)):
        try:
            t = time.time(); fn(); log(f"  ✓ {name} {time.time() - t:.1f}s")
        except Exception as e: err(name, e)
    for k, e in prev.items():
        if k not in IND and e.get("s"): IND[k] = e; IND[k]["stale"] = True
    axes, overall = judge()
    for k, m in META.items():
        if k in IND: IND[k].update(name=m[0], unit=m[1], group=m[2], why=m[3])
    myth = IND.pop("_myth", None) or (jload(OUT).get("myth"))
    IND.pop("_gpr_full", None)
    now = datetime.now(KST)
    DB.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"as_of": now.strftime("%Y-%m-%d %H:%M"), "ind": IND, "axes": axes, "overall": overall,
                               "myth": myth, "groups": GROUPS, "errors": ERRORS}, ensure_ascii=False), encoding="utf-8")
    HIST.write_text(json.dumps(hist, ensure_ascii=False), encoding="utf-8")
    log(f"[goldlead] ✅ {len([k for k in IND if not k.startswith('_')])}개 지표 · 종합 {overall} · 오류 {len(ERRORS)} → {OUT}")

if __name__ == "__main__":
    main()
