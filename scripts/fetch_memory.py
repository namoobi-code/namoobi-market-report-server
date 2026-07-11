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
TABLES = [
    ("dram_spot",     "dram",  "pricedetail/dram/dram_spot",      "DRAM 현물(스팟)",      "USD"),
    ("dram_contract", "dram",  "pricedetail/dram/dram_contract",  "DRAM 고정거래(계약)",  "USD"),
    ("module_spot",   "dram",  "pricedetail/dram/module_spot",    "DRAM 모듈 현물",       "USD"),
    ("gddr_spot",     "dram",  "pricedetail/dram/gddr_spot",      "GDDR 현물",            "USD"),
    ("nand_spot",     "flash", "pricedetail/flash/flash_spot",    "NAND 현물(스팟)",      "USD"),
    ("nand_contract", "flash", "pricedetail/flash/flash_contract","NAND 고정거래(계약)",  "USD"),
    ("nand_wafer",    "flash", "pricedetail/flash/wafer_spot",    "NAND 웨이퍼 현물",     "USD"),
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
    out["asp"] = [{"product": r["product"], "price": r.get("price"), "price_mid": _n(r.get("price")),
                   "trend": r.get("trend"), "change": r.get("change"), "driver": r.get("driver", "")}
                  for r in (d.get("spotPrices") or [])]
    out["specs"] = [{"gen": r["type"], "bandwidth": r.get("bw"), "capacity": r.get("cap"),
                     "pin": r.get("pin"), "note": r.get("note", "")} for r in (d.get("specs") or [])]
    out["platform_revenue"] = [{"platform": r["platform"], "units_m": _n(r.get("units")),
                                "hbm_gb": _n(r.get("density")), "hbm_price_k": _n(r.get("price")),
                                "revenue_bn": _n(r.get("revenue"))} for r in (d.get("revenueForecast") or [])]
    out["source"] = HBM_API
    n = sum(len(v) for v in out.values() if isinstance(v, list))
    print(f"[memory] ✅ HBM 지표      {n}행 (점유율·ASP·공급사매출·스펙)")
    return out

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
        rows.append({"name": name, "ticker": tk, "currency": cur, "price": px,
                     "eps_ttm": None, "eps_2026E": None, "eps_2027E": None,
                     "per_ttm": None, "per_2026E": None, "per_2027E": None,
                     "_eps_note": "EPS 컨센서스는 MCP(UsStockInfo) 또는 DB carry-forward 로 채운다"})
    ok = sum(1 for r in rows if r["price"])
    print(f"[memory] ✅ 밸류에이션    {ok}/{len(rows)}사 주가 취득 (EPS 는 MCP/DB 보완)")
    return rows


def accumulate(result, dbdir):
    """수집 결과를 날짜 union 으로 시계열 DB에 누적한다 (매일 1점씩 자라남).

    생성되는 시계열:
      series_mem_dram_spot / dram_contract / module_spot / gddr_spot
      series_mem_nand_spot / nand_contract / nand_wafer      ← 가격 7종
      series_mem_hbm_asp                                      ← HBM ASP (가속기당)
      series_mem_hbm_share                                    ← HBM 업체별 점유율
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
    val = fetch_valuation()
    if val: result["valuation"] = val
    if hbm: result["sources"].append(HBM_API)
    if val: result["sources"].append("Yahoo Finance quote API")

    p = os.path.join(WORK, "nmr_memory.json")
    json.dump(result, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    n = sum(len(t["rows"]) for t in result["tables"].values())
    print(f"[memory] 완료 → {p} ({len(result['tables'])}개 표 · {n}개 지표)")

    # DB 디렉토리가 주어지면 시계열 누적까지 수행 (서버 daily cron 모드)
    dbdir = sys.argv[2] if len(sys.argv) > 2 else os.environ.get("NMR_DB")
    if dbdir and os.path.isdir(dbdir):
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        try:
            k = accumulate(result, dbdir)
            print(f"[memory] ✅ 시계열 누적 {k}종 → {dbdir}")
        except Exception as e:
            print(f"[memory] ⚠️ 누적 실패(비차단): {e}")
    return 0

if __name__ == "__main__":
    try: sys.exit(main())
    except Exception as e:
        print(f"[memory] ⚠️ 예외(비차단): {e}"); sys.exit(0)
