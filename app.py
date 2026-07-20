import json, time, urllib.request, os, re, sqlite3, zlib
from pathlib import Path
from datetime import datetime
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

BASE = Path(__file__).parent
DB   = BASE / "data" / "db"
RPT  = BASE / "data" / "reports"
POLL = BASE / "data" / "poll.db"
RPTD = BASE / "data" / "report"

app = FastAPI(title="namoobi market", docs_url="/api/docs")

def load(name: str):
    p = DB / f"{name}.json"
    if not p.exists():
        raise HTTPException(404, f"{name} not found")
    return json.loads(p.read_text(encoding="utf-8"))

_domains_cache = {"sig": None, "out": None}

@app.get("/api/domains")
def domains():
    files = sorted(DB.glob("*.json"))
    sig = _db_sig(files)
    if _domains_cache["sig"] != sig:
        out = []
        for p in files:
            try:
                d = json.loads(p.read_text(encoding="utf-8"))
                out.append({"name": p.stem, "as_of": d.get("as_of",""), "marker": d.get("marker","")})
            except Exception:
                pass
        _domains_cache.update(sig=sig, out=out)
    return _domains_cache["out"]

@app.get("/api/db/{name}")
def get_db(name: str, request: Request):
    """원본 JSON 바이트를 그대로 전송(파싱/재직렬화 생략) + ETag 재검증 캐시."""
    if not re.fullmatch(r"[a-zA-Z0-9_]+", name):
        raise HTTPException(400, "bad name")
    p = DB / f"{name}.json"
    if not p.exists():
        raise HTTPException(404, f"{name} not found")
    st = p.stat()
    etag = 'W/"%x-%x"' % (int(st.st_mtime), st.st_size)
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers={"ETag": etag, "Cache-Control": "no-cache"})
    return Response(content=p.read_bytes(), media_type="application/json",
                    headers={"ETag": etag, "Cache-Control": "no-cache"})

@app.get("/api/summary")
def summary():
    """대시보드 상단 카드용 — 정책금리·물가·고용·경기선행 한 번에"""
    out = {}
    for k in ("policy_rates", "inflation", "employment", "leading", "semi_cycle"):
        try:
            out[k] = load(k)
        except HTTPException:
            out[k] = None
    return out

@app.get("/api/series/{name}")
def series(name: str, days: int = 0):
    """[[date, value], ...] 형식 시계열"""
    d = load(name)
    data = d.get("data", [])
    if days and isinstance(data, list) and len(data) > days:
        data = data[-days:]
    return {"as_of": d.get("as_of",""), "marker": d.get("marker",""), "data": data}

@app.get("/api/report")
def report_data():
    """보고서가 렌더링하는 전체 데이터 — CAPEX·HBM·파생포지셔닝 등"""
    p = RPTD / "report_data.json"
    if not p.exists():
        raise HTTPException(404, "report_data 없음")
    return json.loads(p.read_text(encoding="utf-8"))

@app.get("/api/deriv")
def deriv_live():
    """3.1.13 파생 포지셔닝 — 서버가 장중·마감 갱신하는 deriv_snapshot.json 라이브 제공.
       report_data(하루 1회 병합)와 분리해 프론트가 장중 폴링으로 최신값을 본다.
       built_at = 스냅샷 파일 갱신시각(KST) — 실제 마지막 취득 시각."""
    p = BASE / "data" / "deriv_snapshot.json"
    if not p.exists():
        raise HTTPException(404, "deriv_snapshot 없음")
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        raise HTTPException(500, f"deriv_snapshot 파싱 실패: {e}")
    from datetime import timezone, timedelta
    kst = timezone(timedelta(hours=9))
    d["built_at"] = datetime.fromtimestamp(p.stat().st_mtime, kst).strftime("%Y-%m-%d %H:%M:%S")
    d["cadence"] = ("장중 5분 자동취득(정규장·장전·시간외·야간 中 데이터 제공 구간) · "
                    "옵션 PCR·IV스큐·GEX는 장중 1시간+장마감 캡처 · 매일 새벽 정산치로 z 재계산")
    # (2026-07-20) 야간선물(KRX 18:00~06:00) — night_ws 웹소켓 데몬(H0MFCNT0)이 기록한 실시간가.
    #   현물은 야간에 멈춰 있어 베이시스로 쓰면 왜곡 → 별도 '야간선물' 정보로만 노출한다.
    nfp = BASE / "data" / "night_fut.json"
    if nfp.exists():
        try:
            nf = json.loads(nfp.read_text(encoding="utf-8"))
            age = time.time() - nfp.stat().st_mtime
            if age < 900 and nf.get("px"):
                nf["age_sec"] = int(age)
                d["night"] = nf
        except Exception:
            pass
    return Response(content=json.dumps(d, ensure_ascii=False),
                    media_type="application/json", headers={"Cache-Control": "no-store"})

@app.get("/api/policyrates")
def policyrates():
    """주요 6개국 정책금리 월별 시계열"""
    p = RPTD / "policyrates_monthly.json"
    if not p.exists():
        raise HTTPException(404, "policyrates 없음")
    return json.loads(p.read_text(encoding="utf-8"))

# 대시보드가 참조하지 않는 대용량 DB — 번들 제외(필요 시 /api/db/<name> 로 개별 조회)
BUNDLE_SKIP = {"screener_pool", "tp_history", "us_krname"}
_bundle_cache = {"sig": None, "body": None, "etag": None}

def _db_sig(files):
    parts = []
    for p in files:
        st = p.stat()
        parts.append("%s:%d:%d" % (p.name, st.st_mtime, st.st_size))
    if POLL.exists():
        st = POLL.stat()
        parts.append("poll:%d:%d" % (st.st_mtime, st.st_size))
    return "|".join(parts)

@app.get("/api/bundle")
def bundle(request: Request):
    """db/ 전체를 한 번에 — 변경 없으면 메모리 캐시/304로 즉시 응답."""
    files = sorted(p for p in DB.glob("*.json") if p.stem not in BUNDLE_SKIP)
    sig = _db_sig(files)
    if _bundle_cache["sig"] != sig:
        out = {}
        for p in files:
            try:
                out[p.stem] = json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                pass
        poll = {}
        if POLL.exists():
            try:
                c = sqlite3.connect(POLL)
                for m, sym, ts, v in c.execute(
                    "SELECT metric,symbol,ts,value FROM ticks ORDER BY ts"):
                    poll.setdefault(m, {}).setdefault(sym or "_", []).append([ts, v])
                c.close()
            except Exception:
                pass
        out["_poll"] = poll
        body = json.dumps(out, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        _bundle_cache.update(sig=sig, body=body,
                             etag='W/"b%x-%x"' % (zlib.crc32(sig.encode()), len(body)))
    etag = _bundle_cache["etag"]
    hdr = {"ETag": etag, "Cache-Control": "no-cache"}
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=hdr)
    return Response(content=_bundle_cache["body"], media_type="application/json", headers=hdr)

_chart_cache = {}

@app.get("/api/chart/{mkt}/{code}")
def chart_api(mkt: str, code: str):
    """종목 일봉(종가 기준) 프록시 — KR: 네이버 / US: Yahoo v8. 10분 메모리 캐시."""
    if mkt not in ("kr", "us") or not re.fullmatch(r"[A-Za-z0-9.\-]{1,12}", code):
        raise HTTPException(400, "bad params")
    key = f"{mkt}:{code}"; now = time.time()
    hit = _chart_cache.get(key)
    if hit and now - hit[0] < 60:      # 장중 실시간성 — 1분 캐시
        return hit[1]
    try:
        from datetime import date as _d, timedelta as _td, datetime as _dt
        if mkt == "kr":
            E = _d.today().strftime("%Y%m%d"); S = (_d.today() - _td(days=430)).strftime("%Y%m%d")
            url = f"https://api.stock.naver.com/chart/domestic/item/{code}/day?startDateTime={S}&endDateTime={E}"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            rows = json.loads(urllib.request.urlopen(req, timeout=12).read())
            out = {"t": [str(r.get("localDate") or "") for r in rows],
                   "o": [r.get("openPrice") for r in rows], "h": [r.get("highPrice") for r in rows],
                   "l": [r.get("lowPrice") for r in rows], "c": [r.get("closePrice") for r in rows],
                   "v": [r.get("accumulatedTradingVolume") for r in rows]}
        else:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(code)}?range=1y&interval=1d"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            j = json.loads(urllib.request.urlopen(req, timeout=12).read())
            res = j["chart"]["result"][0]; q = res["indicators"]["quote"][0]
            ts = res.get("timestamp") or []
            out = {"t": [_dt.utcfromtimestamp(x).strftime("%Y%m%d") for x in ts],
                   "o": q.get("open"), "h": q.get("high"), "l": q.get("low"),
                   "c": q.get("close"), "v": q.get("volume")}
        _chart_cache[key] = (now, out)
        if len(_chart_cache) > 300:
            _chart_cache.clear()
        return out
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(502, f"chart fetch failed: {e}")

# ── ETF 주요 구성종목·비중 (상세 열 때 온디맨드) ──
#   KR: 네이버 모바일 etfAnalysis → etfTop10MajorConstituentAssets (Top10 종목·비중)
#   US: Yahoo quoteSummary topHoldings (crumb 인증 필요 → ta_screen.yahoo_opener 재사용)
#   6시간 메모리 캐시. 실패해도 200 + 빈 holdings (프론트가 '정보 없음' 표기).
_hold_cache = {}
_yop = {"op": None, "crumb": None, "ts": 0.0}

def _pctnum(s):
    if s is None:
        return None
    if isinstance(s, (int, float)):
        return float(s)
    m = re.search(r"-?[\d.]+", str(s).replace(",", ""))
    return float(m.group(0)) if m else None

def _yahoo_oc():
    import sys as _sys
    if _yop["op"] and time.time() - _yop["ts"] < 1800:
        return _yop["op"], _yop["crumb"]
    _sys.path.insert(0, str(BASE / "scripts"))
    import ta_screen as _T
    op, crumb = _T.yahoo_opener()
    _yop.update(op=op, crumb=crumb, ts=time.time())
    return op, crumb

@app.get("/api/etf/holdings/{mkt}/{code}")
def etf_holdings(mkt: str, code: str):
    if mkt not in ("kr", "us") or not re.fullmatch(r"[A-Za-z0-9.\-]{1,12}", code):
        raise HTTPException(400, "bad params")
    key = f"{mkt}:{code}"; now = time.time()
    hit = _hold_cache.get(key)
    if hit and now - hit[0] < 6 * 3600:
        return hit[1]
    out = {"mkt": mkt, "code": code, "holdings": []}
    try:
        if mkt == "kr":
            url = f"https://m.stock.naver.com/api/stock/{code}/etfAnalysis"
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0", "Referer": "https://m.stock.naver.com/"})
            d = json.loads(urllib.request.urlopen(req, timeout=12).read().decode("utf-8", "ignore"))
            for x in (d.get("etfTop10MajorConstituentAssets") or []):
                nm = x.get("itemName")
                if not nm:
                    continue
                out["holdings"].append({"n": nm, "c": x.get("itemCode") or "",
                                        "w": _pctnum(x.get("etfWeight"))})
        else:
            import sys as _sys
            _sys.path.insert(0, str(BASE / "scripts"))
            import ta_screen as _T
            op, crumb = _yahoo_oc()
            url = ("https://query1.finance.yahoo.com/v10/finance/quoteSummary/%s"
                   "?modules=topHoldings&crumb=%s"
                   % (urllib.parse.quote(code), urllib.parse.quote(crumb)))
            j = _T.jget(url, opener=op, timeout=15)
            th = ((j.get("quoteSummary", {}).get("result") or [{}])[0] or {}).get("topHoldings", {}) or {}
            for h in (th.get("holdings") or []):
                nm = h.get("holdingName") or h.get("symbol")
                if not nm:
                    continue
                hp = h.get("holdingPercent") or {}
                w = hp.get("raw")
                w = round(w * 100, 2) if isinstance(w, (int, float)) else _pctnum(hp.get("fmt"))
                out["holdings"].append({"n": nm, "c": h.get("symbol") or "", "w": w})
    except Exception as e:
        out["err"] = str(e)[:120]
    _hold_cache[key] = (now, out)
    if len(_hold_cache) > 600:
        _hold_cache.clear()
    return out

# ── 종목별 투자자 수급 (외국인·기관·개인 누적순매수) ──
#   1년치: 네이버 frgn.naver 13페이지 (외국인·기관 순매매량만 제공)
#   최근 30거래일: KIS FHKST01010900 (개인 포함 3주체 실측 — 네이버 값과 일치 검증됨)
#   병합: KIS 구간은 KIS 우선(개인 실측), 그 이전 개인은 null → 프론트가 −(외인+기관) 추정 점선
_inv_cache = {}

def _frgn_naver(code: str, pages: int = 13):
    """finance.naver.com/item/frgn.naver 표 파싱 → [(YYYYMMDD, 기관, 외인)]"""
    from concurrent.futures import ThreadPoolExecutor
    def one(p):
        url = f"https://finance.naver.com/item/frgn.naver?code={code}&page={p}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        html = urllib.request.urlopen(req, timeout=12).read().decode("euc-kr", "ignore")
        out = []
        for m in re.finditer(r"<tr[^>]*>(.*?)</tr>", html, re.S):
            cells = [re.sub(r"<[^>]+>", "", c).strip().replace(",", "")
                     for c in re.findall(r"<td[^>]*>(.*?)</td>", m.group(1), re.S)]
            # 일별 표만: 날짜·종가·전일비·등락률·거래량·기관·외인·보유주수·보유율(%) = 9칸
            if len(cells) < 9 or "%" not in cells[8]:
                continue
            dm = re.match(r"(\d{4})\.(\d{2})\.(\d{2})", cells[0])
            if not dm:
                continue
            try:
                org, frg = int(cells[5]), int(cells[6])
            except ValueError:
                continue
            out.append((dm.group(1) + dm.group(2) + dm.group(3), org, frg))
        return out
    rows = []
    with ThreadPoolExecutor(max_workers=6) as ex:
        for part in ex.map(one, range(1, pages + 1)):
            rows.extend(part)
    return rows

def _kis_investor(code: str):
    """KIS 종목별 투자자매매동향(일별 30행) → {YYYYMMDD: (기관, 외인, 개인)}"""
    import sys as _s
    sp = str(BASE / "scripts")
    if sp not in _s.path:
        _s.path.insert(0, sp)
    import kis_api as K
    c = K._creds(); tok = K._token(c)
    j = K._get(c, tok, "/uapi/domestic-stock/v1/quotations/inquire-investor", "FHKST01010900",
               {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": code})
    out = {}
    for r in (j.get("output") or []):
        try:
            out[r["stck_bsop_date"]] = (int(r["orgn_ntby_qty"]), int(r["frgn_ntby_qty"]), int(r["prsn_ntby_qty"]))
        except (KeyError, ValueError, TypeError):
            continue
    return out

@app.get("/api/investor/kr/{code}")
def investor_api(code: str):
    if not re.fullmatch(r"\d{6}", code):
        raise HTTPException(400, "bad code")
    now = time.time(); hit = _inv_cache.get(code)
    if hit and now - hit[0] < 1800:      # 30분 캐시
        return hit[1]
    data = {}
    try:
        for d, org, frg in _frgn_naver(code):
            data[d] = {"o": org, "f": frg, "p": None}
    except Exception:
        pass
    kis_from = None
    try:
        k = _kis_investor(code)
        for d, (o_, f_, p_) in k.items():
            data[d] = {"o": o_, "f": f_, "p": p_}
        if k:
            kis_from = min(k)
    except Exception:
        pass
    if not data:
        raise HTTPException(502, "investor fetch failed")
    ts = sorted(data)
    out = {"t": ts,
           "orgn": [data[d]["o"] for d in ts],
           "frgn": [data[d]["f"] for d in ts],
           "prsn": [data[d]["p"] for d in ts],
           "kis_from": kis_from}
    _inv_cache[code] = (now, out)
    if len(_inv_cache) > 200:
        _inv_cache.clear()
    return out

@app.get("/api/reports")
def reports():
    out = []
    for p in sorted(RPT.glob("*.docx"), reverse=True):
        m = re.search(r"(\d{8})_(\d{4})", p.name)
        dt = ""
        if m:
            dt = f"{m.group(1)[:4]}-{m.group(1)[4:6]}-{m.group(1)[6:]} {m.group(2)[:2]}:{m.group(2)[2:]}"
        out.append({"file": p.name, "datetime": dt, "size_mb": round(p.stat().st_size/1024/1024, 1)})
    return out

@app.get("/reports/{fname}")
def download(fname: str):
    if not re.fullmatch(r"[\w\-\.]+\.docx", fname):
        raise HTTPException(400, "bad filename")
    p = RPT / fname
    if not p.exists():
        raise HTTPException(404, "not found")
    return FileResponse(p, filename=fname,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")

@app.get("/krxbrief/{sub}/{fname}")
def krxbrief_img(sub: str, fname: str):
    if not (re.fullmatch(r"[\w\-]+", sub) and re.fullmatch(r"[\w\-]+\.png", fname)):
        raise HTTPException(400, "bad path")
    p = BASE / "data" / "krx_brief" / sub / fname
    if not p.exists():
        raise HTTPException(404, "not found")
    return FileResponse(p, media_type="image/png")

@app.get("/api/poll/{metric}")
def poll(metric: str, limit: int = 200):
    """서버가 1일 2회 수집한 김치프리미엄·공포탐욕 시계열"""
    if not POLL.exists():
        return []
    c = sqlite3.connect(POLL)
    try:
        rows = c.execute(
            "SELECT ts, symbol, value FROM ticks WHERE metric=? ORDER BY ts DESC LIMIT ?",
            (metric, limit)).fetchall()
    except sqlite3.OperationalError:
        return []
    finally:
        c.close()
    return [{"ts": r[0], "symbol": r[1], "value": r[2]} for r in reversed(rows)]

KRLIQ = BASE / "data" / "kr_liquidity.db"

@app.get("/api/krliq")
def krliq(days: int = 420):
    """3.1.14 국내 유동성·레버리지 — 서버가 1일 3회 수집 (scripts/fetch_kr_liquidity.py).
    daily: [date, 예탁금, 미수금, 반대매매금액, 반대매매비중%, 신용전체, 신용코스피, 신용코스닥,
            코스피, 코스피거래대금, 코스닥, 코스닥거래대금]  (금액 원 단위)
    monthly: [month, M2(십억원), 코스피종가, 코스닥종가]
    verdict: ① 예탁금 5일 증감 × 회전배수 5일 방향 2×2 자동 판정"""
    if not KRLIQ.exists():
        raise HTTPException(404, "kr_liquidity.db not found")
    c = sqlite3.connect(KRLIQ)
    try:
        daily = c.execute(
            "SELECT date,deposit,ucol,opp_amt,opp_ratio,crd_whl,crd_kospi,crd_kosdaq,"
            "kospi,kospi_trdval,kosdaq,kosdaq_trdval FROM kr_liq_daily "
            "ORDER BY date DESC LIMIT ?", (days,)).fetchall()[::-1]
        monthly = c.execute(
            "SELECT month,m2,kospi,kosdaq FROM kr_liq_monthly ORDER BY month").fetchall()
        vrows = c.execute(         # 판정은 days 파라미터와 무관하게 최근 40행에서 계산
            "SELECT date,deposit,kospi_trdval FROM kr_liq_daily "
            "WHERE deposit IS NOT NULL AND kospi_trdval IS NOT NULL "
            "ORDER BY date DESC LIMIT 40").fetchall()[::-1]
    finally:
        c.close()
    verdict = None
    dep = vrows
    if len(dep) >= 6:
        d5 = (dep[-1][1] / dep[-6][1] - 1) * 100
        t_now, t_prev = dep[-1][2] / dep[-1][1], dep[-6][2] / dep[-6][1]
        t5 = (t_now - t_prev)
        lab = (("유입·가동", "강세") if d5 > 0 and t5 > 0 else
               ("유입·관망", "중립") if d5 > 0 else
               ("이탈·소진성 회전", "경계") if t5 > 0 else ("이탈·위축", "약세"))
        verdict = {"label": lab[0], "tone": lab[1], "dep_5d_pct": round(d5, 2),
                   "turn_5d_chg": round(t5, 4), "as_of": dep[-1][0]}
    return {"daily": daily, "monthly": monthly, "verdict": verdict}

@app.get("/api/health")
def health():
    return {"ok": True,
            "db_files": len(list(DB.glob("*.json"))),
            "reports": len(list(RPT.glob("*.docx"))),
            "now": datetime.now().isoformat(timespec="seconds")}

APK = BASE / "data" / "apk"

@app.get("/api/apk")
def apk_releases():
    """GitHub 릴리스 캐시 (scripts/sync_apk.py가 갱신)"""
    p = APK / "releases.json"
    if not p.exists():
        return []
    return json.loads(p.read_text(encoding="utf-8"))

@app.get("/apk/{fname}")
def apk_download(fname: str):
    if not re.fullmatch(r"[\w\-\.]+\.apk", fname):
        raise HTTPException(400, "bad filename")
    p = APK / fname
    if not p.exists():
        raise HTTPException(404, "not found")
    return FileResponse(p, filename=fname,
        media_type="application/vnd.android.package-archive")

# ── (2026-07-12) 6.2 코인 4종 1년 차트 (가격·거래량) ──
#   Binance 공개 klines 를 서버가 대신 받아 1시간 캐시한다. 인증·과금 없음.
#   클라이언트가 직접 부르면 CORS·사내망 차단에 걸리므로 서버 프록시로 우회한다.
COINS = {"BTC": "BTCUSDT", "ETH": "ETHUSDT", "XRP": "XRPUSDT", "SOL": "SOLUSDT"}
_coin_cache: dict = {}

@app.get("/api/coin/{sym}")
def coin_series(sym: str):
    sym = sym.upper()
    if sym not in COINS:
        raise HTTPException(404, "unknown symbol")
    now = time.time()
    hit = _coin_cache.get(sym)
    if hit and now - hit[0] < 3600:          # 1시간 캐시
        return hit[1]
    url = ("https://api.binance.com/api/v3/klines"
           f"?symbol={COINS[sym]}&interval=1d&limit=365")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "namoobi-dashboard"})
        with urllib.request.urlopen(req, timeout=15) as r:
            raw = json.loads(r.read().decode())
        out = {"symbol": sym, "pair": COINS[sym],
               "data": [{"t": k[0], "c": float(k[4]), "v": float(k[7])} for k in raw]}
        _coin_cache[sym] = (now, out)
        return out
    except Exception as e:
        if hit:                               # 실패 시 만료 캐시라도 준다
            return hit[1]
        return {"symbol": sym, "data": [], "error": str(e)}

# ── 로그인 + 방문자 통계 (개발자 전용) ──
#   반드시 아래 StaticFiles 마운트보다 먼저 등록해야 한다.
#   mount("/") 가 모든 경로를 가로채므로, 뒤에 붙이면 라우트가 죽는다.
try:
    from auth_visitors import router as _av_router
    app.include_router(_av_router)
except Exception as _e:
    print(f"[app] auth_visitors 로드 실패: {_e}")

# ── (2026-07-20) 관리자 수동 즉시 갱신 — 로그인 사용자만. START 재클릭 시 1분/3분 안 기다리고 강제 refresh ──
#   단일 워커라 동기 실행은 사이트를 멈춘다 → 백그라운드 subprocess + flock 로 중복 방지. 프론트가 풀 live_at 변화를 재폴링.
import subprocess as _sp
_REFRESH_MODS = {"screener": ("intraday_kr", "intraday_us"), "etf": ("etf_intraday",)}

@app.post("/api/admin/refresh/{which}")
def admin_refresh(which: str, request: Request):
    from auth_visitors import current_user
    if not current_user(request):
        raise HTTPException(401, "관리자 로그인이 필요합니다")
    mods = _REFRESH_MODS.get(which)
    if not mods:
        raise HTTPException(400, "대상이 올바르지 않습니다")
    lock = f"/tmp/refresh_{which}.lock"
    # 이미 실행 중이면(락 점유) 스킵 안내 — 그 실행이 곧 풀을 갱신한다
    import fcntl
    try:
        _lf = open(lock, "w")
        fcntl.flock(_lf, fcntl.LOCK_EX | fcntl.LOCK_NB)
        fcntl.flock(_lf, fcntl.LOCK_UN); _lf.close()
    except BlockingIOError:
        return {"busy": True, "which": which}
    code = "import sys; sys.path.insert(0,'scripts'); " + \
           "; ".join(f"import {m}; {m}.main(force=True)" for m in mods)
    try:
        _sp.Popen(["/usr/bin/flock", "-n", lock, "python3", "-c", code],
                  cwd=str(BASE), stdout=_sp.DEVNULL, stderr=_sp.DEVNULL,
                  start_new_session=True)
    except Exception as e:
        raise HTTPException(500, f"갱신 실행 실패: {e}")
    return {"started": True, "which": which}

# ── 추세 스파크라인 (docx 표의 '추세(1Y)' 열과 동일한 PNG) ──
#   리포트 실행 때 생성된 charts/spark_*.png 를 sync_server.py 가 올린다.
CHARTS = BASE / "data" / "charts"
CHARTS.mkdir(parents=True, exist_ok=True)
app.mount("/charts", StaticFiles(directory=CHARTS), name="charts")

app.mount("/", StaticFiles(directory=BASE / "static", html=True), name="static")
