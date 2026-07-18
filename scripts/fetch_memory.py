#!/usr/bin/env python3
"""[3.1.9] 메모리·HBM 지표 수집 — TrendForce 공개 가격표 직접 파싱.

출력(WORK):
  nmr_memory.json  {"asof":..., "tables":{<표key>:{"label","unit","last_update","rows":[{item,avg,chg,...}]}}, "sources":[...]}

특징: 표준 라이브러리만 사용(샌드박스 안전), 공개 페이지라 로그인 불필요.
      TrendForce 가 표 구조를 바꾸면 해당 표만 비고 나머지는 살아남는다(비차단).
"""
import html as _html
import json, os, re, sys, ssl, urllib.request
from datetime import datetime, timezone, timedelta

KST = timezone(timedelta(hours=9))
WORK = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("WORK", ".")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"}
CTX = ssl.create_default_context()

PAGES = {
    "dram":  "https://www.trendforce.com/price/dram/dram_spot",
    "flash": "https://www.trendforce.com/price/flash/flash_spot",
}

# 페이지 안에서 뽑을 표: (표key, 페이지, 표 제목 앵커, 라벨, 단위)
# 앵커 = pricedetail 링크 URL 조각 (네비게이션 메뉴의 동일 문구와 구분됨)
#
# (v3.59) 모듈현물·GDDR현물·NAND웨이퍼 3종은 수집 중단.
#   · 모듈  = 칩의 조립품. 칩 가격(dram_spot)이 이미 선행지표라 정보 중복.
#   · GDDR  = 그래픽 니치. 변동이 거의 없고(±0.4%) 메모리 3사 실적 기여도 미미.
#   · 웨이퍼 = NAND 현물과 성격 중복.
#   현물·계약 쌍(dram_spot/contract, nand_spot/contract)만 남긴다 — 스팟-계약 갭이
#   계약가 인상 압력의 선행지표라 4종 모두 필요하다.
TABLES = [
    ("dram_spot",     "dram",  "pricedetail/dram/dram_spot",      "DRAM 현물(스팟)",      "USD"),
    ("dram_contract", "dram",  "pricedetail/dram/dram_contract",  "DRAM 고정거래(계약)",  "USD"),
    ("nand_spot",     "flash", "pricedetail/flash/flash_spot",    "NAND 현물(스팟)",      "USD"),
    ("nand_contract", "flash", "pricedetail/flash/flash_contract","NAND 고정거래(계약)",  "USD"),
]

def get(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30, context=CTX) as r:
        return r.read().decode("utf-8", "ignore")

def strip_tags(s):
    s = re.sub(r"<[^>]+>", " ", s)
    s = _html.unescape(s)          # &#9650;(▲) &#9660;(▼) → 실제 문자로. 안 하면 9650 이 숫자로 잡힌다.
    return re.sub(r"\s+", " ", s).replace("\xa0", " ").strip()

def num(s):
    if s is None: return None
    t = str(s).replace(",", "")
    m = re.search(r"-?\d+(?:\.\d+)?", t)
    return float(m.group()) if m else None

def pct(s):
    """'▲ 1.07 %' → +1.07 / '▼ -1.03 %' → -1.03 / '— 0.00 %' → 0.0
    주의: TrendForce 는 화살표를 HTML 엔티티(&#9650;/&#9660;)로 보낸다.
          unescape 하지 않으면 9650/9660 이 숫자로 오인된다."""
    if s is None: return None
    t = _html.unescape(str(s))
    down = "\u25bc" in t or "▼" in t
    m = re.search(r"-?\d+(?:\.\d+)?\s*%", t)     # % 가 붙은 수치만 채택
    if not m: return None
    v = float(m.group().replace("%", "").strip())
    if down and v > 0: v = -v
    return v

def parse_tables(html):
    """<table> 단위로 (헤더, 행들) 추출."""
    out = []
    for tb in re.findall(r"<table[^>]*>(.*?)</table>", html, re.S | re.I):
        rows = []
        for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", tb, re.S | re.I):
            cells = [strip_tags(c) for c in
                     re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", tr, re.S | re.I)]
            if cells: rows.append(cells)
        if len(rows) >= 2: out.append(rows)
    return out

# ═══════════════════════════════════════════════════════════════════
#  (v3.58) 확장 — HBM 지표 + 메모리 3사 밸류에이션
# ═══════════════════════════════════════════════════════════════════
HBM_API = "https://siliconanalysts.com/api/v1/hbm"
YQ = "https://query1.finance.yahoo.com/v7/finance/quote?symbols=%s"
TICKERS = [("SK하이닉스", "000660.KS", "KRW"), ("삼성전자", "005930.KS", "KRW"),
           ("Micron", "MU", "USD")]

def _n(x):
    if x is None: return None
    if isinstance(x, (int, float)): return float(x)
    m = re.findall(r"-?\d+(?:\.\d+)?", str(x).replace(",", ""))
    if not m: return None
    return (float(m[0]) + float(m[1])) / 2 if len(m) >= 2 and re.search(r"\d\s*[-~]\s*\d", str(x)) else float(m[0])

def fetch_hbm():
    """HBM 점유율·ASP·공급사 매출 — Silicon Analysts 공개 API(무료)."""
    try:
        d = json.loads(get(HBM_API))["data"]
    except Exception as e:
        print(f"[memory] ⚠️ HBM API 실패: {e}"); return None
    out = {}
    out["share"] = [{"vendor": r["name"], "share_pct": _n(r.get("share")), "note": r.get("note", "")}
                    for r in (d.get("marketShare") or [])]
    out["supplier_revenue"] = [{"vendor": r["name"], "share_pct": _n(r.get("share")),
                                "revenue_bn": _n(r.get("revenue")), "note": r.get("note", "")}
                               for r in (d.get("supplierRevenue") or [])]
    # (req7-⑦ 2026-07-17) ASP 오염 가드 — 2026-07-13 실측: API 가 'DRAM (HBM context...)' 행과
    #   단위 붕괴값(HBM3E 12-Hi 2600→8.33 $/GB 형)을 섞어 보냄 → HBM 스택가($100 이상)만 채택.
    out["asp"] = [{"product": r["product"], "price": r.get("price"), "price_mid": _n(r.get("price")),
                   "trend": r.get("trend"), "change": r.get("change"), "driver": r.get("driver", "")}
                  for r in (d.get("spotPrices") or [])
                  if str(r.get("product", "")).startswith("HBM") and (_n(r.get("price")) or 0) >= 100]
    out["specs"] = [{"gen": r["type"], "bandwidth": r.get("bw"), "capacity": r.get("cap"),
                     "pin": r.get("pin"), "note": r.get("note", "")} for r in (d.get("specs") or [])]
    out["platform_revenue"] = [{"platform": r["platform"], "units_m": _n(r.get("units")),
                                "hbm_gb": _n(r.get("density")), "hbm_price_k": _n(r.get("price")),
                                "revenue_bn": _n(r.get("revenue"))} for r in (d.get("revenueForecast") or [])]
    out["source"] = HBM_API
    n = sum(len(v) for v in out.values() if isinstance(v, list))
    print(f"[memory] ✅ HBM 지표      {n}행 (점유율·ASP·공급사매출·스펙)")
    return out

def naver_annual(code6):
    """네이버 기업실적분석 — 연도별 EPS·PER·BPS·ROE·매출·영업이익 (실적 + 3년치 컨센서스).

    ★ 소스: 네이버 PC 종목분석 iframe = FnGuide(navercomp.wisereport.co.kr)
      모바일 API(/finance/annual)는 당해년도(2026) 하나만 준다.
      PC 표에는 2027·2028(E)까지 있다 — 이쪽이 정본이다.

    2단계 호출: ① c1010001.aspx 에서 encparam·id 토큰 추출 (페이지마다 새로 생성)
                ② ajax/cF1001.aspx 를 토큰과 함께 호출 → 연도별 표 HTML

    실측(SK하이닉스 2026-07-13):
      EPS  2021~2025 실적 → 2026(E) 318,735 · 2027(E) 444,359 · 2028(E) 433,625
      (E) 표기로 실적/컨센서스가 명시되므로 매핑이 확실하다.

    반환: {"2026": {"eps":318735, "per":6.84, "bps":..., "roe":..., "revenue":...,
                    "is_consensus": True}, ...}   · 매출·영업이익 단위 = 억원
    """
    PAGE = f"https://navercomp.wisereport.co.kr/v2/company/c1010001.aspx?cmp_cd={code6}"
    try:
        h = get(PAGE)
        enc = (re.search(r"encparam\s*[:=]\s*['\"]([^'\"]+)['\"]", h) or [None, None])[1]
        idp = (re.search(r"[^a-zA-Z]id\s*:\s*['\"]([A-Za-z0-9+/=]{6,})['\"]", h) or [None, None])[1]
        if not enc:
            print(f"[memory] ⚠️ FnGuide 토큰 추출 실패({code6}) — 연도별 실적 생략")
            return {}
        u = ("https://navercomp.wisereport.co.kr/v2/company/ajax/cF1001.aspx"
             f"?cmp_cd={code6}&fin_typ=0&freq_typ=Y&encparam={enc}&id={idp or ''}")
        req = urllib.request.Request(u, headers={**UA, "Referer": PAGE,
                                                "X-Requested-With": "XMLHttpRequest"})
        with urllib.request.urlopen(req, timeout=30, context=CTX) as r:
            html = r.read().decode("utf-8", "ignore")
    except Exception as e:
        print(f"[memory] ⚠️ 네이버 연도별 실적 실패({code6}): {e}")
        return {}

    # 연도 헤더 — '(E)' 가 붙으면 컨센서스
    yrs = re.findall(r"(20\d{2})/\d{2}(\(E\))?", html)
    if not yrs:
        return {}
    cols = [(y, bool(e)) for y, e in yrs]

    FLD = {"매출액": "revenue", "영업이익": "op", "당기순이익": "net",
           "영업이익률": "opm", "ROE": "roe", "EPS": "eps", "PER": "per",
           "BPS": "bps", "PBR": "pbr"}

    def cells(label):
        m = re.search(r">\s*%s[^<]*<.*?</tr>" % re.escape(label), html, re.S)
        if not m:
            return []
        return [re.sub(r"<[^>]+>", "", t).replace("&nbsp;", "").strip()
                for t in re.findall(r"<td[^>]*>(.*?)</td>", m.group(), re.S)]

    def _num(v):
        if v in (None, "", "-", "N/A"):
            return None
        try:
            return float(str(v).replace(",", ""))
        except Exception:
            return None

    out = {}
    for label, key in FLD.items():
        vals = cells(label)
        for i, (yr, is_e) in enumerate(cols):
            if i >= len(vals):
                break
            v = _num(vals[i])
            if v is None:
                continue
            out.setdefault(yr, {"is_consensus": is_e})[key] = v
    return out


def naver_consensus(code6):
    """네이버 당일 컨센서스 — 추정EPS/추정PER·실적EPS/PER·목표주가.

    KRX OPEN API 는 T+1 이라 못 주고, Yahoo quoteSummary 는 인증이 필요하다.
    네이버 /integration 은 무인증·당일값이며 국내 증권사 컨센서스 집계를 그대로 준다.
    """
    try:
        d = json.loads(get(f"https://m.stock.naver.com/api/stock/{code6}/integration"))
    except Exception as e:
        print(f"[memory] ⚠️ 네이버 컨센서스 실패({code6}): {e}")
        return None
    T = {x.get("key"): x.get("value") for x in (d.get("totalInfos") or [])}
    def n(k):
        v = T.get(k)
        if not v: return None
        try: return float(str(v).replace(",", "").replace("배", "").replace("원", "").replace("%", ""))
        except Exception: return None
    out = {"fwd_eps": n("추정EPS"), "fwd_per": n("추정PER"),
           "eps_ttm": n("EPS"), "per_ttm": n("PER"), "asof": datetime.now(KST).strftime("%Y-%m-%d")}
    cs = d.get("consensusInfo") or {}
    if cs.get("priceTargetMean"):
        try:
            out["target"] = float(str(cs["priceTargetMean"]).replace(",", ""))
            out["recomm"] = cs.get("recommMean")
            out["target_asof"] = cs.get("createDate")
        except Exception: pass
    return {k: v for k, v in out.items() if v is not None}


def fetch_valuation():
    """메모리 3사 주가·EPS·PER.
    price 는 Yahoo chart API(공개·무인증)로 실시간 취득.
    EPS 컨센서스는 quote API 가 401(인증 필요)이라 HBMAgent 가 MCP(UsStockInfo)로 채워
    nmr_hbm.json.eps_per 로 넘겨주거나, 직전 DB(db/memory.json.valuation)를 carry-forward 한다.
    PER 은 항상 '현재가 / EPS' 로 직접 계산한다 — 벤더 PER 은 기준주가가 제각각이라 신뢰 불가.
    """
    CHART = "https://query1.finance.yahoo.com/v8/finance/chart/%s?interval=1d&range=1d"
    rows = []
    for name, tk, cur in TICKERS:
        px = None
        try:
            d = json.loads(get(CHART % tk))
            px = d["chart"]["result"][0]["meta"].get("regularMarketPrice")
        except Exception as e:
            print(f"[memory] ⚠️ {name} 주가 실패: {e}")
        r = {"name": name, "ticker": tk, "currency": cur, "price": px,
             "eps_ttm": None, "eps_2026E": None, "eps_2027E": None,
             "per_ttm": None, "per_2026E": None, "per_2027E": None,
             "_eps_note": "EPS 컨센서스는 MCP(UsStockInfo) 또는 DB carry-forward 로 채운다"}

        # ★ (2026-07-13) 한국 2사는 네이버가 '당일' 컨센서스를 준다 — 이걸 정본으로 쓴다.
        #   종전엔 DB(hbm_eps) 의 연도별 추정치를 carry-forward 했는데, 메모리 슈퍼사이클로
        #   컨센서스가 대폭 상향된 것이 반영되지 않아 보고서가 3배 틀린 PER 을 보여주고 있었다:
        #     SK하이닉스 DB 2026 EPS 110,559(PER 16.7배)  vs  네이버 당일 318,735(PER 5.79배)
        #     삼성전자   DB 2026 EPS  16,693(PER 15.3배)  vs  네이버 당일  46,664(PER 5.45배)
        #   PER 16.7배와 5.8배는 투자판단이 완전히 다르다. 낡은 추정치를 그대로 두면 안 된다.
        if tk.endswith(".KS"):
            code6 = tk.split(".")[0]
            ann = naver_annual(code6)
            if ann:
                r["annual_naver"] = ann           # ★ 연도별 EPS·PER (실적 + 컨센서스, 연도키 명시)
            nv = naver_consensus(code6)
            if nv:
                r["consensus_live"] = nv          # 네이버 당일 컨센서스 (정본)
                if nv.get("fwd_eps"):
                    r["eps_fwd"] = nv["fwd_eps"]
                    if px:
                        r["per_fwd"] = round(px / nv["fwd_eps"], 2)
                if nv.get("eps_ttm"):
                    r["eps_ttm"] = nv["eps_ttm"]
                    if px:
                        r["per_ttm"] = round(px / nv["eps_ttm"], 2)
        rows.append(r)
    ok = sum(1 for r in rows if r["price"])
    nc = sum(1 for r in rows if r.get("consensus_live"))
    na = sum(1 for r in rows if r.get("annual_naver"))
    print(f"[memory] ✅ 밸류에이션    {ok}/{len(rows)}사 주가 · 당일 컨센서스 {nc}사 · "
          f"연도별 실적/컨센서스 {na}사 (Micron 은 MCP/DB 보완)")
    return rows


def compute_ddr5_gap(result):
    """(req12 2026-07-12) HBM : DDR5 GB당 단가 격차 — 환산 추정.
    HBM $/GB = Silicon Analysts ASP(HBM3E 8-Hi, USD/스택) ÷ 스택 용량(24GB)
    DDR5 $/GB = TrendForce DDR5 16Gb(=2GB) 계약가 평균 ÷ 2
    배율 = HBM $/GB ÷ DDR5 $/GB. 모두 공개 소스 — 주기적으로 계산 가능(매 실행)."""
    try:
        hbm = result.get("hbm") or {}
        asp = None
        for a in (hbm.get("asp") or []):
            if "HBM3E" in str(a.get("product", "")) and a.get("price_mid"):
                asp = float(a["price_mid"]); break
        if asp is None:
            for a in (hbm.get("asp") or []):
                if a.get("price_mid"): asp = float(a["price_mid"]); break
        cap_gb = 24.0
        for sp in (hbm.get("specs") or []):
            if "HBM3E" in str(sp.get("gen", "")):
                import re as _re2
                mm = _re2.findall(r"(\d+)\s*GB", str(sp.get("capacity", "")))
                if mm: cap_gb = float(mm[0]); break
        ddr5 = None; ddr5_gb = 2.0; ddr5_src = "DDR5 16Gb 계약가"
        rows_dc = ((result.get("tables") or {}).get("dram_contract") or {}).get("rows", [])
        for r in rows_dc:
            if "DDR5 16Gb" in str(r.get("item", "")) and r.get("avg"):
                ddr5 = float(r["avg"]); break
        if ddr5 is None:
            import re as _re3
            for r in rows_dc:
                it = str(r.get("item", ""))
                if it.startswith("DDR5") and r.get("avg"):
                    mm = _re3.search(r"(\d+)\s*GB", it)
                    if mm:
                        ddr5 = float(r["avg"]); ddr5_gb = float(mm.group(1)); ddr5_src = it + " 모듈가 환산"; break
        # (req7-⑨ 2026-07-17) DDR5 '현물' 기반 배율 추가 — 계약가 분모는 월 1회라 그래프가 일직선.
        #   현물(매일 변동) 분모 배율을 병기해 일별 움직임을 보이게 한다.
        ddr5_spot = None
        for r in ((result.get("tables") or {}).get("dram_spot") or {}).get("rows", []):
            if "DDR5 16Gb" in str(r.get("item", "")) and r.get("avg"):
                ddr5_spot = float(r["avg"]); break
        if asp and ddr5 and cap_gb:
            h_gb = asp / cap_gb; d_gb = ddr5 / ddr5_gb
            ratio = round(h_gb / d_gb, 1)
            ratio_spot = (round(h_gb / (ddr5_spot / 2.0), 1) if ddr5_spot else None)
            result.setdefault("hbm", {})["ddr5_gap"] = {
                "hbm_per_gb": round(h_gb, 2), "ddr5_per_gb": round(d_gb, 2), "ratio": ratio,
                "ddr5_spot_per_gb": (round(ddr5_spot / 2.0, 2) if ddr5_spot else None), "ratio_spot": ratio_spot,
                "basis": f"HBM3E {cap_gb:.0f}GB 스택 ASP ${asp:,.0f} ÷ {cap_gb:.0f}GB vs {ddr5_src} ${ddr5:.2f} ÷ {ddr5_gb:.0f}GB (환산 추정)",
                "source": "Silicon Analysts 공개 API + TrendForce 공개 가격표"}
            print(f"[memory] ✅ HBM:DDR5 격차  {ratio}배 (HBM ${h_gb:.1f}/GB vs DDR5 ${d_gb:.2f}/GB)")
    except Exception as e:
        print(f"[memory] ⚠️ HBM:DDR5 격차 계산 실패(비차단): {e}")


def enrich_valuation(result, dbdir):
    """(req13 2026-07-12) 메모리 3사 EPS·PER 단일소스 — db/hbm_eps.json 하나만 쓴다.
    EPS = DB 컨센서스(HBMAgent 가 변동 시 갱신) / PER = 오늘 종가 ÷ EPS 재계산(매일).
    대시보드 ⑩과 docx 표가 모두 이 파일을 읽어 값이 항상 일치한다."""
    try:
        p = os.path.join(dbdir, "hbm_eps.json")
        sd = json.load(open(p, encoding="utf-8"))
        store = sd.get("data") if isinstance(sd, dict) and "data" in sd else (sd or {})
        alias = {"Micron": "마이크론", "마이크론": "마이크론"}
        prices, notes = {}, []
        for row in (result.get("valuation") or []):
            nm = alias.get(row.get("name"), row.get("name"))
            px = row.get("price")
            if not px: continue
            prices[nm] = {"price": px, "currency": row.get("currency"), "asof": result.get("asof")}
            eo = store.get(nm) or store.get(row.get("name")) or {}
            for yy in ("2025", "2026", "2027", "2028"):
                ev = eo.get(f"y{yy}_eps")
                try: ev = float(str(ev).replace(",", "")) if ev not in (None, "") else None
                except Exception: ev = None
                if ev:
                    eo[f"y{yy}_per"] = round(px / ev, 2)
            key = nm if nm in store else row.get("name")
            store[key or nm] = eo
            row["eps_2026E"] = eo.get("y2026_eps"); row["per_2026E"] = eo.get("y2026_per")
            row["eps_2027E"] = eo.get("y2027_eps"); row["per_2027E"] = eo.get("y2027_per")
            fmt = "{:,.0f}".format(px) if row.get("currency") == "KRW" else "${:,.2f}".format(px)
            notes.append(f"{row.get('name')} {fmt}")
        if prices:
            sd = {"as_of": result.get("asof"), "source": "single-source: EPS=컨센서스, PER=종가÷EPS 매일 재계산",
                  "price_note": "기준가(" + (result.get("asof") or "") + " 종가): " + " · ".join(notes),
                  "prices": prices, "data": store}
            json.dump(sd, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            print(f"[memory] ✅ EPS·PER 단일소스 갱신 — {len(prices)}사 최신가 기준 PER 재계산")
    except Exception as e:
        print(f"[memory] ⚠️ EPS·PER 단일소스 갱신 실패(비차단): {e}")


def accumulate(result, dbdir):
    """수집 결과를 날짜 union 으로 시계열 DB에 누적한다 (매일 1점씩 자라남).

    생성되는 시계열:
      series_mem_dram_spot / dram_contract / nand_spot / nand_contract   ← 가격 4종
      series_mem_hbm_asp                                      ← HBM ASP (가속기당)
      series_mem_hbm_share                                    ← HBM 업체별 점유율
      series_mem_leading_px                                   ← (v3.60) 선행지표 6종 종가
      series_mem_mem_vs_gpu                                   ← (v3.60) 메모리/GPU 상대강도
    각 항목의 data = [[YYYY-MM-DD, {항목명: 값, ...}], ...]
    """
    import nmr_db
    asof = result.get("asof")
    if not asof: return 0

    snaps = {}
    for tk, t in (result.get("tables") or {}).items():
        d = {r["item"]: r["avg"] for r in (t.get("rows") or []) if r.get("avg") is not None}
        if d: snaps[tk] = d

    hbm = result.get("hbm") or {}
    asp = {a["product"]: a["price_mid"] for a in (hbm.get("asp") or []) if a.get("price_mid")}
    if asp: snaps["hbm_asp"] = asp
    shr = {r["vendor"]: r["share_pct"] for r in (hbm.get("share") or []) if r.get("share_pct")}
    if shr: snaps["hbm_share"] = shr

    # (v3.60) 선행지표 — 종가 6종 + 메모리/GPU 상대강도를 각각 시계열로
    lead = result.get("leading") or {}
    lpx = {v["label"]: v["price"] for v in lead.values()
           if isinstance(v, dict) and v.get("price") is not None}
    if lpx: snaps["leading_px"] = lpx
    rs = (lead.get("MEM_VS_GPU") or {}).get("value")
    if rs is not None: snaps["mem_vs_gpu"] = {"메모리/GPU 상대강도": rs}

    # (req12) HBM:DDR5 GB당 단가 격차 — 매일 환산 누적
    gap = (hbm.get("ddr5_gap") or {})
    if gap.get("ratio") is not None:
        snaps["hbm_ddr5_gap"] = {"HBM $/GB": gap.get("hbm_per_gb"), "DDR5 $/GB": gap.get("ddr5_per_gb"),
                                 "배율": gap.get("ratio"), "배율(계약)": gap.get("ratio"),
                                 "배율(현물)": gap.get("ratio_spot"), "DDR5 현물 $/GB": gap.get("ddr5_spot_per_gb")}

    n = 0
    for key, snap in snaps.items():
        name = "series_mem_" + key
        cur = (nmr_db._load(name, dbdir) or {}).get("data") or []
        merged = [x for x in cur if x[0] != asof] + [[asof, snap]]
        merged.sort(key=lambda x: x[0])
        nmr_db.set_(name, "", asof, dbdir, merged)
        n += 1
        print(f"[memory]    {name:26s} {len(merged):3d}일치 · {len(snap)}개 항목")
    return n


# ══════════════════════════════════════════════════════════════════
#  (v3.60) 선행지표 — 전부 일별 갱신 가능 (Yahoo 무인증 chart API)
# ══════════════════════════════════════════════════════════════════
LEAD = [
    ("SOX",  "^SOX",   "필라델피아 반도체지수",      "반도체 업황 종합 체온계"),
    ("NVDA", "NVDA",   "엔비디아",                  "HBM 최대 수요처"),
    ("AMD",  "AMD",    "AMD",                       "HBM 2번째 수요처"),
    ("TSM",  "TSM",    "TSMC",                      "CoWoS 패키징 = HBM 출하의 물리적 상한"),
    ("KOSPI","^KS11",  "코스피",                    "삼성+SK 시총 55~60% — 메모리 사이클이 곧 지수"),
    ("MU",   "MU",     "마이크론",                  "메모리 공급자 대표"),
]
LCHART = "https://query2.finance.yahoo.com/v8/finance/chart/%s?interval=1d&range=1y"

def fetch_leading():
    """선행지표: 반도체 지수·HBM 수요처·CoWoS 병목 + 메모리/GPU 상대강도.
    상대강도(MU÷NVDA) 가 1 초과면 가치가 수요처→공급자로 이동 = 공급부족 심화."""
    import time as _t
    out = {}
    for key, tk, label, why in LEAD:
        px = chg1y = chg1m = None; ser1y = []
        for a in range(3):
            try:
                d = json.loads(get(LCHART % tk))
                r = d["chart"]["result"][0]
                c = [x for x in r["indicators"]["quote"][0]["close"] if x]
                px = r["meta"].get("regularMarketPrice") or c[-1]
                chg1y = round((c[-1] / c[0] - 1) * 100, 1)
                chg1m = round((c[-1] / c[-22] - 1) * 100, 1) if len(c) > 22 else None
                # (req7-⑩ 2026-07-17) 1년 일별 종가 시계열 — ⑩ 통합 라인차트(종목별 색상)용
                try:
                    _ts = r.get("timestamp") or []
                    _cl = r["indicators"]["quote"][0]["close"]
                    _ser1y = [[_t.strftime("%Y-%m-%d", _t.gmtime(t0)), round(float(v0), 2)]
                              for t0, v0 in zip(_ts, _cl) if v0]
                    ser1y = _ser1y[-260:]
                except Exception:
                    ser1y = []
                break
            except Exception:
                if a == 2: break
                _t.sleep(3)
        if px is None:
            print(f"[memory] ⚠️ 선행지표 {key} 수집 실패(비차단)"); continue
        out[key] = {"ticker": tk, "label": label, "why": why,
                    "price": px, "chg_1y_pct": chg1y, "chg_1m_pct": chg1m,
                    "series_1y": ser1y}
        _t.sleep(1.0)

    # ★ 메모리/GPU 상대강도 — 가치 이동 신호
    mu, nv = out.get("MU"), out.get("NVDA")
    if mu and nv and nv.get("chg_1y_pct") not in (None, -100):
        rs = round((1 + mu["chg_1y_pct"] / 100) / (1 + nv["chg_1y_pct"] / 100), 2)
        out["MEM_VS_GPU"] = {
            "label": "메모리/GPU 상대강도 (MU ÷ NVDA, 1년)",
            "why": "1 초과 = 가치가 수요처(GPU)에서 공급자(메모리)로 이동 = 공급부족 심화",
            "value": rs,
            "signal": "공급자 우위" if rs > 1.2 else ("균형" if rs > 0.8 else "수요처 우위"),
        }
    print(f"[memory] ✅ 선행지표      {len(out)}종 (SOX·NVDA·AMD·TSM·코스피·MU + 상대강도)")
    return out


def main():
    htmls, srcs = {}, []
    for k, u in PAGES.items():
        try:
            htmls[k] = get(u); srcs.append(u)
        except Exception as e:
            print(f"[memory] ⚠️ {k} 수집 실패: {e}")

    result = {"asof": datetime.now(KST).strftime("%Y-%m-%d"),
              "fetched_at": datetime.now(KST).isoformat(timespec="seconds"),
              "tables": {}, "sources": srcs}

    for key, page, anchor, label, unit in TABLES:
        html = htmls.get(page)
        if not html: continue
        # 앵커는 페이지에 여러 번 나온다(섹션 헤더 + 하단 링크). 표가 뒤따르는 첫 앵커를 쓴다.
        tbs, seg = None, ""
        for m in re.finditer(re.escape(anchor), html):
            seg = html[m.start(): m.start() + 20000]
            cand = parse_tables(seg)
            if cand:
                tbs = cand; break
        if not tbs:
            print(f"[memory] ⚠️ {key} 표 파싱 실패(앵커 뒤 표 없음)"); continue
        head, *body = tbs[0]
        low = [h.lower() for h in head]
        def col(*names):
            for n in names:
                for j, h in enumerate(low):
                    if n in h: return j
            return None
        c_avg = col("session average", "average")
        c_chg = col("session change", "average change", "change")
        rows = []
        for r in body:
            if not r or not r[0] or len(r) < 2: continue
            item = r[0]
            if not re.search(r"\d", item) and "Gb" not in item and "GB" not in item: continue
            avg = num(r[c_avg]) if c_avg is not None and c_avg < len(r) else None
            chg = pct(r[c_chg]) if c_chg is not None and c_chg < len(r) else None
            if avg is None: continue
            rows.append({"item": item, "avg": avg, "chg_pct": chg})
        if rows:
            m = re.search(r"Last Update\s*([\d\-]+\s*[\d:]*)", seg)
            result["tables"][key] = {"label": label, "unit": unit,
                                     "last_update": m.group(1).strip() if m else "",
                                     "rows": rows}
            print(f"[memory] ✅ {key:14s} {len(rows)}행")

    hbm = fetch_hbm()
    if hbm: result["hbm"] = hbm
    lead = fetch_leading()
    if lead: result["leading"] = lead
    val = fetch_valuation()
    if val: result["valuation"] = val
    compute_ddr5_gap(result)   # (req12) HBM:DDR5 GB당 단가 격차 — 환산 추정(매 실행)
    if hbm: result["sources"].append(HBM_API)
    if val: result["sources"].append("Yahoo Finance quote API")

    # (v3.60) 메타데이터(의미·해석방법·갱신주기) 첨부 — 보고서·대시보드·docx 가 이걸 그대로 표시한다.
    #   매일 변하지 않는 값은 실제 변동 주기를 명시 (예: 계약가=월 1회, HBM 점유율=분기 1회).
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import nmr_meta
        result["meta"] = nmr_meta.META
        print(f"[memory] ✅ 메타데이터    {len(nmr_meta.META)}개 지표 (의미·해석·갱신주기)")
    except Exception as e:
        print(f"[memory] ⚠️ 메타데이터 첨부 실패(비차단): {e}")

    dbdir_pre = sys.argv[2] if len(sys.argv) > 2 else os.environ.get("NMR_DB")
    if dbdir_pre and os.path.isdir(dbdir_pre):
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        enrich_valuation(result, dbdir_pre)   # (req13) 저장 전에 EPS·PER 주입 — WORK/nmr_memory.json 도 일치
    p = os.path.join(WORK, "nmr_memory.json")
    json.dump(result, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    n = sum(len(t["rows"]) for t in result["tables"].values())
    print(f"[memory] 완료 → {p} ({len(result['tables'])}개 표 · {n}개 지표)")

    # DB 디렉토리가 주어지면 시계열 누적까지 수행 (서버 daily cron 모드)
    dbdir = sys.argv[2] if len(sys.argv) > 2 else os.environ.get("NMR_DB")
    if dbdir and os.path.isdir(dbdir):
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        try:
            import nmr_db
            # 스냅샷(db/memory.json)도 갱신 — 서버 대시보드가 리포트 미실행일에도 최신 표·선행지표·메타를 본다.
            nmr_db.set_("memory", result["asof"], result["asof"], dbdir, result)
            k = accumulate(result, dbdir)
            print(f"[memory] ✅ 스냅샷 db/memory.json + 시계열 누적 {k}종 → {dbdir}")
        except Exception as e:
            print(f"[memory] ⚠️ 누적 실패(비차단): {e}")
    return 0

if __name__ == "__main__":
    try: sys.exit(main())
    except Exception as e:
        print(f"[memory] ⚠️ 예외(비차단): {e}"); sys.exit(0)
