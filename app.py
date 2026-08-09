import json, time, urllib.request, os, re, sqlite3, zlib, sys
from pathlib import Path
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
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
    # (2026-08-02) 프로그램 차익 순매수(KOSPI200 전용·참고) — program_trading.json에서 z(60일) 계산해 행 주입.
    #   차익거래는 베이시스와 같은 맥락의 확인 지표라 베이시스 행 바로 아래 배치, 자동 판독 집계에선 제외(참고 표기).
    try:
        pg = json.loads((DB / "program_trading.json").read_text(encoding="utf-8"))
        _k = pg.get("kospi") or {}
        arb, ts_ = _k.get("arb") or [], _k.get("t") or []
        if len(arb) >= 60 and d.get("rows"):
            import statistics
            w = [x for x in arb[-60:] if x is not None]
            mu = statistics.fmean(w); sd = statistics.pstdev(w) or 1.0
            zv = round((arb[-1] - mu) / sd, 2)
            cells = [{"v": None, "z": None} if "KOSPI" not in (ix.get("name") or "")
                     else {"v": f"{arb[-1]:+,.0f} 억원 ({ts_[-1][4:6]}-{ts_[-1][6:]})", "z": zv}
                     for ix in (d.get("index") or [])]
            d["rows"].insert(1, {"label": "프로그램 차익 순매수 (참고)", "cells": cells})
    except Exception:
        pass
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

_ov_cache = {}
@app.get("/api/overview")
def stock_overview(mkt: str, code: str):
    """(2026-08-02) 종목 기업개요 — 네이버 온디맨드 프록시 + 24h 캐시.
       KR: finance.naver PC main summary_info(cp949) · US: api.stock.naver.com /stock/{sym}.O|.N/overview"""
    import re as _re, urllib.request as _ur
    key = f"{mkt}:{code}".lower()
    hit = _ov_cache.get(key)
    if hit and time.time() - hit[0] < 86400:
        return hit[1]
    out = {"lines": [], "src": "네이버"}
    try:
        if mkt == "kr":
            if not _re.fullmatch(r"\d{6}", code):
                raise HTTPException(400, "bad code")
            raw = _ur.urlopen(_ur.Request(f"https://finance.naver.com/item/main.naver?code={code}",
                                          headers={"User-Agent": "Mozilla/5.0"}), timeout=10).read()
            try: d = raw.decode("utf-8")          # 2026 현재 UTF-8 (구 euc-kr에서 전환)
            except UnicodeDecodeError: d = raw.decode("cp949", "ignore")
            i = d.find("summary_info")
            if i > 0:
                seg = d[i:i + 3000]
                for pm in _re.findall(r"<p>(.*?)</p>", seg, _re.S):
                    t = _re.sub(r"\s+", " ", _re.sub(r"<[^>]+>", "", pm)).strip()
                    if t and "MY STOCK" not in t and len(t) > 15:
                        out["lines"].append(t)
        else:
            if not _re.fullmatch(r"[A-Za-z0-9.\-]{1,12}", code):
                raise HTTPException(400, "bad code")
            for suf in ("", ".O", ".N", ".K"):    # NYSE=무접미사·나스닥=.O (실측)
                try:
                    j = json.loads(_ur.urlopen(_ur.Request(
                        f"https://api.stock.naver.com/stock/{code}{suf}/overview",
                        headers={"User-Agent": "Mozilla/5.0", "Referer": "https://m.stock.naver.com/",
                                 "Accept": "application/json"}), timeout=10).read())
                    s = (j or {}).get("summary")
                    if s:
                        s = _re.sub(r"<br\s*/?>", "\n", s).replace("\r", "")
                        out["lines"] = [_re.sub(r"<[^>]+>", "", x).strip() for x in s.split("\n") if x.strip()]
                        out["name"] = j.get("companyName")
                        break
                except Exception:
                    continue
    except HTTPException:
        raise
    except Exception:
        pass
    _ov_cache[key] = (time.time(), out)
    if len(_ov_cache) > 3000:
        _ov_cache.clear()
    return out

# ── (2026-08-05) SEC 8-K 워치리스트 — 캘린더 US 뷰에서 조회/추가/삭제 ──
_W8K = BASE / "data" / "watch" / "us_8k_watchlist.txt"

@app.get("/api/8k_watchlist")
def w8k_get():
    syms = []
    try:
        for ln in _W8K.read_text().splitlines():
            s = ln.strip().upper()
            if s and not s.startswith("#") and s not in syms:
                syms.append(s)
    except Exception:
        pass
    info = {}
    try:
        p = json.loads((BASE / "data" / "db" / "screener_pool.json").read_text(encoding="utf-8"))
        info = {r["c"]: r for r in p.get("us") or []}
    except Exception:
        pass
    out = [{"c": s, "n": (info.get(s) or {}).get("kn") or (info.get(s) or {}).get("n") or "",
            "cap": (info.get(s) or {}).get("cap")} for s in syms]
    out.sort(key=lambda x: -(x["cap"] or 0))
    return {"syms": out}

@app.post("/api/8k_watchlist")
def w8k_post(request: Request, add: str = "", remove: str = ""):
    from auth_visitors import current_user
    if not current_user(request):
        raise HTTPException(401, "로그인이 필요합니다")
    add = add.strip().upper(); remove = remove.strip().upper()
    if add and not re.fullmatch(r"[A-Z0-9.\-]{1,10}", add):
        raise HTTPException(400, "티커 형식이 아닙니다")
    lines = []
    try:
        lines = _W8K.read_text().splitlines()
    except Exception:
        pass
    head = [l for l in lines if l.strip().startswith("#")]
    syms = [l.strip().upper() for l in lines if l.strip() and not l.strip().startswith("#")]
    if remove:
        syms = [s for s in syms if s != remove]
    if add and add not in syms:
        syms.append(add)
    _W8K.parent.mkdir(parents=True, exist_ok=True)
    _W8K.write_text("\n".join(head + syms) + "\n")
    return {"ok": True, "count": len(syms)}

@app.get("/api/policyrates")
def policyrates():
    """주요 6개국 정책금리 월별 시계열"""
    p = RPTD / "policyrates_monthly.json"
    if not p.exists():
        raise HTTPException(404, "policyrates 없음")
    return json.loads(p.read_text(encoding="utf-8"))

# 대시보드가 참조하지 않는 대용량 DB — 번들 제외(필요 시 /api/db/<name> 로 개별 조회)
BUNDLE_SKIP = {"screener_pool", "tp_history", "us_krname", "etf_holdings"}
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

_disc_cache = {}


@app.get("/api/disclosure/kr/{code}")
def disclosure_api(code: str):
    """종목 공시 목록 — 네이버 m.stock 프록시. 차트에 마커로 찍고 클릭하면 내용을 보여준다.

    (2026-07-21) 한국 전용. 미국은 SEC EDGAR 가 종목코드→CIK 매핑을 따로 요구하고
    공시 성격도 달라(8-K 등) 같은 UX 로 묶기 어려워 제외한다.
    30분 캐시 — 공시는 실시간성이 낮고 같은 종목을 반복 조회하는 화면이라 충분하다.
    """
    if not re.fullmatch(r"[0-9A-Za-z]{6}", code):
        raise HTTPException(400, "bad code")
    now = time.time()
    hit = _disc_cache.get(code)
    if hit and now - hit[0] < 1800:
        return hit[1]
    try:
        url = ("https://m.stock.naver.com/api/stock/%s/disclosure?pageSize=200&page=1" % code)
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0",
                                                   "Referer": "https://m.stock.naver.com/"})
        rows = json.loads(urllib.request.urlopen(req, timeout=10).read())
        # (2026-07-21) 거래소 시장조치 공지는 뺀다.
        #   '주식선물·옵션 가격제한폭 확대요건 도달' 류는 주가가 크게 움직였다는 사실의 '결과'로
        #   자동 발생하는 공지다. 이걸 주가 차트에 사건으로 찍으면 순환논리이고,
        #   실측(005930 1년): 80건 중 20건이 이 유형이라 정작 실적·자사주 같은 실제 공시를 밀어냈다.
        NOISE = re.compile(r"가격제한폭|매매거래정지|매매거래재개|시장조치|투자유의")
        out = {"items": [{"d": str(r.get("datetime") or "")[:10].replace("-", ""),
                          "t": r.get("title") or "",
                          "at": str(r.get("datetime") or "")[11:16],
                          "src": r.get("author") or "",
                          "id": r.get("disclosureId")}
                         for r in (rows or [])
                         if r.get("datetime") and not NOISE.search(r.get("title") or "")]}
        _disc_cache[code] = (now, out)
        if len(_disc_cache) > 300:
            _disc_cache.clear()
        return out
    except Exception as e:
        return {"items": [], "err": repr(e)[:80]}


@app.get("/dv/{code}/{disc_id}")
def disclosure_doc(code: str, disc_id: int):
    """공시 원본 뷰어 (2026-08-09) — 차트 공시 팝업의 행을 클릭하면 새 탭으로 연다.

    네이버 m.stock 공시 상세 API 의 contents 에 KOSCOM/KIND 원문 HTML 이 통째로
    들어 있어(실측: 표 포함 전문) 별도 파싱 없이 페이지로 감싸기만 한다.
    DART 접수번호는 이 소스에 없으므로 rcpNo 링크는 실적발표(earn_dates) 쪽만 가능.
    """
    if not re.fullmatch(r"[0-9A-Za-z]{6}", code):
        raise HTTPException(400, "bad code")
    try:
        req = urllib.request.Request(
            f"https://m.stock.naver.com/api/stock/{code}/disclosure/{disc_id}",
            headers={"User-Agent": "Mozilla/5.0", "Referer": "https://m.stock.naver.com/"})
        j = json.loads(urllib.request.urlopen(req, timeout=10).read())
        d = j.get("disclosure") or {}
        title = d.get("title") or "공시"
        dt = d.get("datetime") or ""
        body = d.get("contents") or "<p>본문이 제공되지 않는 공시입니다.</p>"
        html = ("<!doctype html><html lang=ko><head><meta charset=utf-8>"
                "<meta name=viewport content='width=device-width,initial-scale=1'>"
                f"<title>{title}</title>"
                "<style>body{font-family:'Malgun Gothic',sans-serif;max-width:880px;margin:20px auto;"
                "padding:0 14px;color:#222;font-size:14px}table{border-collapse:collapse;max-width:100%}"
                "td,th{border:1px solid #ccc;padding:3px 6px;font-size:13px}</style></head><body>"
                f"<h3>{title}</h3><div style='color:#777;font-size:13px'>{dt} · 출처 KOSCOM (네이버 증권 경유)</div><hr>"
                f"{body}</body></html>")
        return HTMLResponse(html)
    except Exception as e:
        raise HTTPException(502, f"공시 원문 조회 실패: {repr(e)[:60]}")


_usfin_cache = {}
_cikmap_cache = {"at": 0, "m": {}}     # 티커→CIK (us_fin·earn_dates 공용 · 주 1회 갱신)


def _cik_map():
    """티커→CIK (SEC 공식 목록 · 주 1회 갱신) — us_fin 의 SEC XBRL 조회에 쓴다."""
    now = time.time()
    if now - _cikmap_cache["at"] > 604800 or not _cikmap_cache["m"]:
        j = json.loads(urllib.request.urlopen(urllib.request.Request(
            "https://www.sec.gov/files/company_tickers.json",
            headers={"User-Agent": "namoobi research namoobi@gmail.com"}), timeout=30).read())
        _cikmap_cache["m"] = {v["ticker"].upper(): str(v["cik_str"]) for v in j.values()}
        _cikmap_cache["at"] = now
    return _cikmap_cache["m"]


@app.get("/api/us_fin/{sym}")
def us_fin(sym: str):
    """미국 종목 분기 실적 + 컨센 추정 + 목표가 스냅샷 — 차트 하단 표용 (2026-08-09 · KR 대칭).

      q     분기 매출/영업익/순익 실적 (Yahoo fundamentals-timeseries · 최신 분기는 10-Q 제출까지 며칠 지연)
      est   컨센 추정 — 0q/+1q 분기(EPS·매출) + 0y/+1y 연간(EPS·매출) (earningsTrend)
      rev   EPS 추정 리비전 곡선 — 90/30/7일 전 값과 현재 (Yahoo 가 과거값을 직접 제공 → 즉시 4점)
      snap  일별 스냅샷(us_consensus.sqlite · 2026-08-09 시작) — 목표가·추정 누적
    6시간 캐시. 단위: 매출/영업익/순익 = 백만$ · EPS = $.
    """
    if not re.fullmatch(r"[A-Za-z.\-]{1,10}", sym or ""):
        raise HTTPException(400, "bad sym")
    sym = sym.upper()
    now = time.time()
    hit = _usfin_cache.get(sym)
    if hit and now - hit[0] < 21600:
        return hit[1]
    UA2 = {"User-Agent": "Mozilla/5.0"}
    raw = lambda x: (x or {}).get("raw") if isinstance(x, dict) else None
    try:
        # ① 분기 실적 3종 (백만$ 로 환산)
        p2 = int(time.time()); p1 = p2 - 3 * 365 * 86400
        ts = json.loads(urllib.request.urlopen(urllib.request.Request(
            f"https://query2.finance.yahoo.com/ws/fundamentals-timeseries/v1/finance/timeseries/{sym}"
            f"?type=quarterlyTotalRevenue,quarterlyOperatingIncome,quarterlyNetIncome,quarterlyDilutedEPS"
            f"&period1={p1}&period2={p2}", headers=UA2), timeout=25).read())
        acc = {}
        for r0 in (ts.get("timeseries", {}).get("result") or []):
            k = next((x for x in r0 if x.startswith("quarterly")), None)
            if not k:
                continue
            for z in (r0.get(k) or []):
                if z and z.get("asOfDate") and (z.get("reportedValue") or {}).get("raw") is not None:
                    v0 = z["reportedValue"]["raw"]
                    acc.setdefault(z["asOfDate"], {})[k] = v0 if k == "quarterlyDilutedEPS" else v0 / 1e6
        q = [{"p": d[:7].replace("-", "/"),
              "s": v.get("quarterlyTotalRevenue"), "o": v.get("quarterlyOperatingIncome"),
              "n": v.get("quarterlyNetIncome"), "eps": v.get("quarterlyDilutedEPS")}
             for d, v in sorted(acc.items())]
        # ── (2026-08-09) 1순위 소스: stockanalysis.com 분기 손익 ─────────────────
        # SEC 는 4분기(12월)를 **따로 신고하지 않는다**(10-K 에 연간만) → 그 분기가 통째로 빈다.
        # 임의 계산(연간−3분기) 대신, Q4 를 실제로 제공하는 곳을 쓴다.
        # 실측 ABNB 2024/12: 이 소스 매출 2,480 · EPS 0.73 (= 회사 발표치. 유도값 0.71 과 다름)
        # 12분기 제공 · 마진 계산용 영업익·순익 포함.
        sa_ok = False
        try:
            sa = json.loads(urllib.request.urlopen(urllib.request.Request(
                f"https://stockanalysis.com/stocks/{sym.lower()}/financials/__data.json?p=quarterly",
                headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"}), timeout=25).read())
            arr = [n for n in sa.get("nodes", []) if n.get("type") == "data"][-1]["data"]
            def _dr(i):
                v = arr[i]
                if isinstance(v, list):  return [_dr(x) for x in v]
                if isinstance(v, dict):  return {k: _dr(x) for k, x in v.items()}
                return v
            blk = None
            for i0, v0 in enumerate(arr):
                if isinstance(v0, dict) and {"datekey", "revenue", "epsdil"} <= set(v0):
                    blk = _dr(i0); break
            if blk and blk.get("datekey"):
                num = lambda x: None if x in (None, "", "-") else float(x)
                qsa = []
                for k2, d2 in enumerate(blk["datekey"]):
                    g = lambda key, dv=1: (num((blk.get(key) or [None] * 99)[k2]) or None)
                    rv2, op2 = g("revenue"), g("opinc")
                    ni2, ep2 = g("netinccmn"), g("epsdil")
                    qsa.append({"p": str(d2)[:7].replace("-", "/"),
                                "s": rv2 / 1e6 if rv2 is not None else None,
                                "o": op2 / 1e6 if op2 is not None else None,
                                "n": ni2 / 1e6 if ni2 is not None else None,
                                "eps": ep2})
                if len(qsa) >= 6:
                    # (2026-08-09) 소스는 20분기를 준다 — 12개로 자르면 앞쪽 4행의 YoY 기준
                    # (t−4)이 잘려 '—' 가 됐다. 전량 보관하고, 표시 개수는 프론트가 정한다.
                    q = sorted(qsa, key=lambda z: z["p"])
                    sa_ok = True
        except Exception:
            pass
        # (2026-08-09) **실적 표는 한 소스만 쓴다** — 소스를 섞으면 같은 분기의 값이
        # 소스마다 달라(EPS 유도치 vs 보고치, 분기 개수 차이) 표 안에서 앞뒤가 안 맞는다.
        # 위 stockanalysis 가 매출·영업익·순익·희석EPS 를 20분기 한 번에 주므로 그것만 쓴다.
        # 실패했을 때만(sa_ok=False) 위 Yahoo timeseries 5분기가 폴백으로 남는다.
        # ② 컨센 추정 + 리비전 곡선 (quoteSummary — crumb 필요)
        est, rev = [], []
        try:
            import http.cookiejar
            cj = http.cookiejar.CookieJar()
            op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
            op.addheaders = list(UA2.items())
            try:
                op.open("https://fc.yahoo.com", timeout=8)
            except Exception:
                pass
            crumb = op.open("https://query1.finance.yahoo.com/v1/test/getcrumb", timeout=10).read().decode()
            j = json.loads(op.open(
                f"https://query2.finance.yahoo.com/v10/finance/quoteSummary/{sym}"
                f"?modules=earningsTrend,earningsHistory&crumb={urllib.parse.quote(crumb)}", timeout=15).read())
            _res0 = (j["quoteSummary"]["result"] or [{}])[0]
            et = (_res0.get("earningsTrend") or {}).get("trend") or []
            # (2026-08-09) 발표 시점 EPS 컨센 + 서프라이즈 — 최근 4분기(earningsHistory).
            # 분기표의 'EPS컨센(발표시점)·서프판정' 열 재료. 매출 쪽은 소스가 없어(야후 미제공)
            # 오늘 시작한 0q 스냅샷이 쌓인 뒤부터 채워진다.
            for h0 in ((_res0.get("earningsHistory") or {}).get("history") or []):
                qf = ((h0.get("quarter") or {}).get("fmt") or "")[:7].replace("-", "/")
                for r2 in q:
                    if r2["p"] == qf:
                        if raw(h0.get("epsEstimate")) is not None:
                            r2["epsE"] = raw(h0.get("epsEstimate"))
                        if raw(h0.get("surprisePercent")) is not None:
                            r2["sprE"] = round(raw(h0.get("surprisePercent")) * 100, 1)
            for t0 in et:
                per = t0.get("period")
                if per in ("0q", "+1q", "0y", "+1y"):
                    ee, re_ = t0.get("earningsEstimate") or {}, t0.get("revenueEstimate") or {}
                    est.append({"per": per, "end": t0.get("endDate"),
                                "eps": raw(ee.get("avg")), "rev": (raw(re_.get("avg")) or 0) / 1e6 or None,
                                "nan": raw(ee.get("numberOfAnalysts")),
                                "epsY": raw(ee.get("yearAgoEps")), "revY": (raw(re_.get("yearAgoRevenue")) or 0) / 1e6 or None})
                    tr = t0.get("epsTrend") or {}
                    rev.append({"per": per, "cur": raw(tr.get("current")), "d7": raw(tr.get("7daysAgo")),
                                "d30": raw(tr.get("30daysAgo")), "d90": raw(tr.get("90daysAgo"))})
        except Exception:
            pass
        # ③ 스냅샷 (목표가·추정 일별 — 2026-08-09 적립 시작)
        snap = []
        try:
            db = DB / "us_consensus.sqlite"
            if db.exists():
                cx = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=10)
                snap = [{"d": r0[0], "eq0": r0[1], "rq0": r0[2], "eq1": r0[3], "rq1": r0[4], "tp": r0[5]}
                        for r0 in cx.execute("SELECT d,eq0,rq0,eq1,rq1,tp FROM snap WHERE sym=? ORDER BY d", (sym,))]
                cx.close()
                # (2026-08-09 재수정) 매출 컨센(발표 시점) — 조건은 하나뿐이다:
                #   "그 분기가 끝난 뒤 ~ **그 분기 실적을 발표하기 전**" 사이의 스냅샷 rq0.
                # 발표가 끝나면 0q 가 다음 분기로 넘어가므로 그 뒤 스냅샷은 다른 분기 값이다
                # (실측 SNDK: 08-09 rq0=10,695 는 6월 분기가 아니라 9월 분기 추정이었다).
                # 스냅샷 적립은 08-09 시작 → 그 이전에 발표된 분기는 값이 없는 게 정상.
                anns = {}
                try:
                    lv = json.loads((DB / "earnings_live_us.json").read_text(encoding="utf-8"))
                    for d8 in sorted(lv.get("days") or {}):
                        for it in lv["days"][d8]:
                            if it.get("c") == sym:
                                anns.setdefault(d8, 1)
                except Exception:
                    pass
                for r2 in q:
                    y0, m0 = int(r2["p"][:4]), int(r2["p"][5:7])
                    qe = f"{y0:04d}-{m0:02d}-31"
                    am = y0 * 12 + m0
                    ann = next((f"{d[:4]}-{d[4:6]}-{d[6:8]}" for d in sorted(anns)
                                if 1 <= (int(d[:4]) * 12 + int(d[4:6])) - am <= 4), None)
                    if not ann:
                        continue
                    cand = [s for s in snap if s.get("rq0") and qe < s["d"] < ann]
                    if cand:
                        r2["sE"] = round(cand[-1]["rq0"] / 1e6, 1)   # 발표 직전 값
        except Exception:
            pass
        # ④ 최근 가이던스 (8-K 보도자료 파싱 · earnings_live_us) — 매출·EPS 중간값 + 컨센 갭
        gd = None
        try:
            live = json.loads((DB / "earnings_live_us.json").read_text(encoding="utf-8"))
            for d8 in sorted(live.get("days") or {}):
                for it in live["days"][d8]:
                    if it.get("c") == sym and (it.get("g_rev") is not None or it.get("g_eps") is not None):
                        gd = {"d": d8, "rev": it.get("g_rev"), "revGap": it.get("g_rev_gap"),
                              "eps": it.get("g_eps"), "epsGap": it.get("g_eps_gap"), "acc": it.get("acc")}
        except Exception:
            pass
        # (2026-08-09) 예전엔 여기서 10분기로 잘라 앞쪽 행의 YoY 기준(t−4)이 사라졌다.
        # 전량(최대 20분기)을 주고 표시 개수는 프론트가 정한다.
        res = {"q": q[-20:], "est": est, "rev": rev, "snap": snap, "gd": gd,
               "unit": "백만$ · EPS=$",
               "src": "stockanalysis 분기 손익(실적) + Yahoo earningsTrend(컨센) + 일별 스냅샷"}
        _usfin_cache[sym] = (now, res)
        if len(_usfin_cache) > 300:
            _usfin_cache.clear()
        return res
    except Exception as ex:
        return {"q": [], "est": [], "rev": [], "snap": [], "err": repr(ex)[:80]}


_seg_cache = {}

@app.get("/api/kr_seg/{code}")
def kr_seg(code: str):
    """매출 구성(제품·부문) 소스 비교 — 자동 (2026-08-09).

    ① DART 정기보고서 3종(사업/반기/분기 최신 각 1건)의 「매출실적」 표를 원문에서 그대로 추출
       + '지배적 단일 사업부문 기재 생략' 여부 감지 (실측 SK하이닉스: 제품별 분리 없음)
    ② WISEreport 기업현황(c1020001)의 주요제품 매출구성(%) — FnGuide 계열 요약
    ③ 기업 IR 링크 — 분기 제품별(예: DRAM/NAND·응용처) 비중은 IR 자료가 유일한 정본
    온디맨드 · 24시간 캐시(보고서는 분기에 한 번 바뀜). 어떤 종목이든 동작한다.
    """
    if not re.fullmatch(r"\d{6}", code or ""):
        raise HTTPException(400, "bad code")
    now = time.time()
    hit = _seg_cache.get(code)
    if hit and now - hit[0] < 600:                    # 메모리 10분 (빠른 재조회용)
        return hit[1]
    import io, zipfile
    CL = lambda x: re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", x)).strip()
    # ── (2026-08-09) 디스크 영구 캐시 — 사용자 첫 조회가 수십 초 걸리는 문제 해소.
    #    새벽 cron(kr_seg_warm.py)이 시총 상위 + 기존 조회 종목을 미리 만들어 둔다.
    #    24h 지나면 목록 1콜로 '새 보고서 여부'만 확인 — 같으면 재파싱 없이 그대로 쓴다.
    segdb_p = DB / "kr_seg_db.json"
    try:
        segdb = json.loads(segdb_p.read_text(encoding="utf-8"))
    except Exception:
        segdb = {}
    ent = segdb.get(code)
    def _picked_list(key, cc):
        bgn = (datetime.now() - timedelta(days=400)).strftime("%Y%m%d")
        j = json.loads(urllib.request.urlopen(
            f"https://opendart.fss.or.kr/api/list.json?crtfc_key={key}&corp_code={cc}"
            f"&bgn_de={bgn}&end_de={datetime.now().strftime('%Y%m%d')}&pblntf_ty=A&page_count=30",
            timeout=20).read())
        picked, seen = [], set()
        for r0 in j.get("list") or []:                # 최신순 — 유형별 첫 건만
            for ty in ("사업보고서", "반기보고서", "분기보고서"):
                if ty in (r0.get("report_nm") or "") and ty not in seen:
                    seen.add(ty); picked.append((ty, r0))
        return picked[:3]
    def _save(ent2):
        segdb[code] = ent2
        try:
            segdb_p.write_text(json.dumps(segdb, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass
    key = cc = None
    try:
        key = (BASE / "keys" / "opendart.txt").read_text().strip()
        cc = (json.loads((BASE / "data" / "watch" / "dart_corp_map.json").read_text(encoding="utf-8"))
              .get("map") or {}).get(code)
    except Exception:
        pass
    if ent:
        if now - ent.get("at", 0) < 86400:
            _seg_cache[code] = (now, ent["res"]); return ent["res"]
        try:                                          # 하루 지남 → 새 보고서 있는지만 확인(1콜)
            picked = _picked_list(key, cc) if (key and cc) else []
            rset = [p[1]["rcept_no"] for p in picked]
            if rset == ent.get("rset"):
                ent["at"] = now; _save(ent)
                _seg_cache[code] = (now, ent["res"]); return ent["res"]
        except Exception:                             # 확인 실패 시 저장분이라도 반환
            _seg_cache[code] = (now, ent["res"]); return ent["res"]
    res = {"reports": [], "wise": None, "ir": None}
    rset = []
    try:
        if key and cc:
            picked = _picked_list(key, cc)
            rset = [p[1]["rcept_no"] for p in picked]
            for ty, r0 in picked:
                try:
                    b = urllib.request.urlopen(
                        f"https://opendart.fss.or.kr/api/document.xml?crtfc_key={key}"
                        f"&rcept_no={r0['rcept_no']}", timeout=60).read()
                    z = zipfile.ZipFile(io.BytesIO(b))
                    n = max(z.namelist(), key=lambda x: z.getinfo(x).file_size)
                    h = z.read(n).decode("utf-8", "ignore")
                    i = h.find("매출실적")
                    rows = []
                    if i > 0:
                        j2 = h.find("수주상황", i)
                        win = h[i:(j2 if 0 < j2 < i + 40000 else i + 15000)]
                        for tr in re.findall(r"<TR[^>]*>(.*?)</TR>", win, re.S | re.I):
                            cs = [CL(x2) for x2 in re.findall(r"<T[DHEU][^>]*>(.*?)</T[DHEU]>", tr, re.S | re.I)]
                            cs = [c2 for c2 in cs if c2 != ""]
                            if cs:
                                rows.append(cs[:8])
                    unit = "백만원" if "단위: 백만원" in h[i:i + 400] else ""
                    res["reports"].append({
                        "nm": r0["report_nm"], "dt": r0["rcept_dt"], "rno": r0["rcept_no"],
                        "unit": unit, "rows": rows[:14],
                        "seg_skip": ("부문별 기재를 생략" in h)})
                except Exception:
                    continue
    except Exception:
        pass
    try:  # WISEreport 주요제품 매출구성
        h = urllib.request.urlopen(urllib.request.Request(
            f"https://navercomp.wisereport.co.kr/v2/company/c1020001.aspx?cmp_cd={code}",
            headers={"User-Agent": "Mozilla/5.0"}), timeout=20).read().decode("utf-8", "replace")
        m = re.search(r"매출구성\((\d{4}\s*/\s*\d{2})\)", h)
        asof = m.group(1).replace(" ", "") if m else ""
        items = []
        mt = re.search(r'id="cTB203".*?</table>', h, re.S)
        if mt:
            for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", mt.group(0), re.S):
                cs = [CL(x2) for x2 in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", tr, re.S)]
                if len(cs) >= 2 and cs[0] not in ("제품명", "") and re.search(r"[\d.]", cs[1]):
                    items.append({"n": cs[0], "p": cs[1]})
        if items:
            res["wise"] = {"asof": asof, "items": items[:8],
                           "url": f"https://navercomp.wisereport.co.kr/v2/company/c1020001.aspx?cmp_cd={code}"}
        # (2026-08-09) 최근연혁(cTB202) — 기업개요 아래 표시용
        mt2 = re.search(r'id="cTB202".*?</table>', h, re.S)
        hist = []
        if mt2:
            for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", mt2.group(0), re.S):
                cs = [CL(x2) for x2 in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", tr, re.S)]
                cs = [c2 for c2 in cs if c2]
                if len(cs) >= 2 and re.match(r"\d{4}/\d{2}", cs[0]):
                    hist.append({"d": cs[0], "t": cs[1]})
        if hist:
            res["hist"] = hist[:8]
    except Exception:
        pass
    # (2026-08-09 실측) skhynix 옛 경로(kor/ir/financialInfo/earningsCall.do)는 404 —
    # 개편 후 UI-FR-IR06 이 'Latest Earnings Release'(분기 실적자료 PDF 목록)
    IRS = {"000660": "https://www.skhynix.com/ir/UI-FR-IR06/",
           "005930": "https://www.samsung.com/global/ir/reports-disclosures/earnings-release/"}
    res["ir"] = IRS.get(code)
    _save({"at": now, "rset": rset, "res": res})
    _seg_cache[code] = (now, res)
    if len(_seg_cache) > 200:
        _seg_cache.clear()
    return res


_earn_cache = {}

@app.get("/api/earn_dates/us/{sym}")
def earn_dates_us(sym: str, days: int = 400):
    """미국 종목의 **과거 실적발표일** 목록 — SEC EDGAR 8-K Item 2.02 접수일.

    (2026-08-09) 차트에 1년치 발표일을 찍기 위해 신설.
    Yahoo 는 '다음 발표 예정일' 하나와 분기 **말일**(quarter end)만 줄 뿐,
    실제 발표일을 주지 않는다. 실적 8-K 의 접수일이 곧 발표일이므로 그걸 쓴다
    (실측: PLTR 마감 6분 뒤 접수 — earnings_8k_watch.py 와 동일 근거).

    ADR(TSM·ASML 등)은 8-K 대신 6-K 로 내므로 둘 다 본다. 6-K 는 Item 구분이 없어
    실적 여부를 못 가리니, 6-K 는 분기당 1건씩만 남겨 소음을 줄인다.
    캐시 12시간 — 과거 발표일은 바뀌지 않는다.
    """
    sym = (sym or "").upper()
    if not re.fullmatch(r"[A-Z0-9.\-]{1,10}", sym):
        raise HTTPException(400, "bad symbol")
    now = time.time()
    hit = _earn_cache.get(sym)
    if hit and now - hit[0] < 43200:
        return hit[1]
    H = {"User-Agent": "namoobi research namoobi@gmail.com"}
    def _get(u, t=20):
        return urllib.request.urlopen(urllib.request.Request(u, headers=H), timeout=t).read()
    try:
        if now - _cikmap_cache["at"] > 604800 or not _cikmap_cache["m"]:
            j = json.loads(_get("https://www.sec.gov/files/company_tickers.json", 30))
            _cikmap_cache["m"] = {v["ticker"].upper(): str(v["cik_str"]) for v in j.values()}
            _cikmap_cache["at"] = now
        cik = _cikmap_cache["m"].get(sym)
        if not cik:
            return {"items": [], "note": "CIK 미매핑"}
        j = json.loads(_get(f"https://data.sec.gov/submissions/CIK{int(cik):010d}.json", 30))
        r = j.get("filings", {}).get("recent", {})
        forms = r.get("form", []); items = r.get("items", [])
        dates = r.get("filingDate", []); accs = r.get("accessionNumber", [])
        cut = (datetime.now() - timedelta(days=max(30, min(days, 1200)))).strftime("%Y-%m-%d")
        out, seen_q = [], set()
        for i in range(len(accs)):
            d = dates[i] if i < len(dates) else ""
            if not d or d < cut:
                continue
            f = forms[i] if i < len(forms) else ""
            it = (items[i] if i < len(items) else "") or ""
            if f == "8-K" and "2.02" in it:
                out.append({"d": d.replace("-", ""), "acc": accs[i], "f": "8-K"})
            elif f == "6-K":
                q = d[:4] + str((int(d[5:7]) - 1) // 3)      # 분기당 1건만
                if q in seen_q:
                    continue
                seen_q.add(q)
                out.append({"d": d.replace("-", ""), "acc": accs[i], "f": "6-K"})
        out.sort(key=lambda x: x["d"])
        res = {"items": out, "cik": cik}
        _earn_cache[sym] = (now, res)
        if len(_earn_cache) > 400:
            _earn_cache.clear()
        return res
    except Exception as e:
        return {"items": [], "err": repr(e)[:80]}


@app.get("/api/earn_dates/kr/{code}")
def earn_dates_kr(code: str, days: int = 400):
    """한국 종목의 **과거 실적발표일** — DART 영업(잠정)실적 공정공시 접수일.

    (2026-08-09) 미국(SEC 8-K Item 2.02)과 같은 목적. 한국의 실적 최초 발표처는
    DART '영업(잠정)실적(공정공시)' 이고, 그 접수일이 곧 발표일이다.
    잠정실적을 안 내는 회사도 있어 '매출액또는손익구조 30% 이상 변경' 공시도 함께 잡는다.

    같은 날 원공시 + [기재정정] 이 함께 오면 하루로 합친다(마커가 겹쳐 보이는 걸 방지).
    캐시 12시간 — 과거 발표일은 바뀌지 않는다.
    """
    if not re.fullmatch(r"\d{6}", code or ""):
        raise HTTPException(400, "bad code")
    now = time.time()
    hit = _earn_cache.get("kr:" + code)
    if hit and now - hit[0] < 43200:
        return hit[1]
    try:
        key = (BASE / "keys" / "opendart.txt").read_text().strip()
        mp = json.loads((BASE / "data" / "watch" / "dart_corp_map.json").read_text())["map"]
        cc = mp.get(code)
        if not cc:
            return {"items": [], "note": "DART 고유번호 미매핑"}
        b = (datetime.now() - timedelta(days=max(30, min(days, 1200)))).strftime("%Y%m%d")
        e = datetime.now().strftime("%Y%m%d")
        seen, out = set(), []
        for page in (1, 2):            # 거래소공시는 1년에 60~80건이라 2페이지면 충분
            u = (f"https://opendart.fss.or.kr/api/list.json?crtfc_key={key}&corp_code={cc}"
                 f"&bgn_de={b}&end_de={e}&pblntf_ty=I&page_count=100&page_no={page}")
            j = json.loads(urllib.request.urlopen(u, timeout=25).read())
            if j.get("status") != "000":
                break
            lst = j.get("list") or []
            for r in lst:
                nm = r.get("report_nm") or ""
                if "잠정" not in nm and "손익구조" not in nm:
                    continue
                d = (r.get("rcept_dt") or "")
                if not d or d in seen:
                    continue
                seen.add(d)
                out.append({"d": d, "rno": r.get("rcept_no"), "t": nm.strip()})
            if len(lst) < 100:
                break
        out.sort(key=lambda x: x["d"])
        res = {"items": out, "corp": cc}
        _earn_cache["kr:" + code] = (now, res)
        if len(_earn_cache) > 400:
            _earn_cache.clear()
        return res
    except Exception as ex:
        return {"items": [], "err": repr(ex)[:80]}


_krfin_cache = {}
_wise_enc = {"at": 0, "v": ""}

@app.get("/api/kr_fin/{code}")
def kr_fin(code: str):
    """한국 종목 분기 재무 + 컨센서스 + 목표주가 변동 — 차트 하단 표용 (2026-08-09).

    한 번의 WISEreport 조회로 세 가지를 돌려준다(온디맨드 · 6시간 캐시):
      q     분기 매출/영업익/순익 — 확정 5분기 + 컨센(E) 3분기 → 프론트가 YoY·QoQ 계산
      tp    증권사별 목표주가 변동표(cTB24 · 최근 ~90일) — 발간일·목표가·직전比
      snap  컨센 영업이익 추정치의 일별 스냅샷(kr_consensus.sqlite) — 추이 그래프용
    """
    if not re.fullmatch(r"\d{6}", code or ""):
        raise HTTPException(400, "bad code")
    now = time.time()
    hit = _krfin_cache.get(code)
    if hit and now - hit[0] < 21600:
        return hit[1]
    UA2 = {"User-Agent": "Mozilla/5.0", "Referer": "https://navercomp.wisereport.co.kr/"}
    def _get(u):
        return urllib.request.urlopen(urllib.request.Request(u, headers=UA2), timeout=25).read().decode("utf-8", "replace")
    CL = lambda x: re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", x)).strip()
    def _num(t):
        t = (t or "").replace(",", "").strip()
        try:
            return float(t)
        except Exception:
            return None
    try:
        # encparam — 전 종목 공용(실측), 1시간 캐시
        if now - _wise_enc["at"] > 3600 or not _wise_enc["v"]:
            b0 = _get("https://navercomp.wisereport.co.kr/v2/company/c1010001.aspx?cmp_cd=005930")
            m0 = re.search(r"encparam\s*[:=]\s*['\"]([^'\"]+)", b0)
            if m0:
                _wise_enc["v"] = m0.group(1); _wise_enc["at"] = now
        enc = _wise_enc["v"]
        # ① 분기(freq_typ=Q) + 연간(freq_typ=Y) 재무 — 확정+컨센(E)
        #    연간은 분기 컨센이 못 미치는 2027(E)·2028(E)까지 준다(실측 SK하이닉스 — 2029는 미제공)
        def _cf1001(freq):
            h = _get(f"https://navercomp.wisereport.co.kr/v2/company/ajax/cF1001.aspx"
                     f"?cmp_cd={code}&fin_typ=0&freq_typ={freq}&encparam={enc}")
            heads = [CL(t) for t in re.findall(r"<th[^>]*>(.*?)</th>", h, re.S)]
            pers = [x for x in heads if re.search(r"\d{4}/\d{2}", x)]
            rows = {}
            for r0 in re.findall(r"<tr[^>]*>(.*?)</tr>", h, re.S):
                c = [CL(x) for x in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", r0, re.S)]
                if not c:
                    continue
                key = {"매출액": "sales", "영업이익(발표기준)": "op", "당기순이익": "ni"}.get(c[0])
                if key and (key != "op" or "op" not in rows):
                    rows[key] = c[1:1 + len(pers)]
            out = []
            for i, per in enumerate(pers):
                m = re.match(r"(\d{4}/\d{2})(\(E\))?", per)
                if not m:
                    continue
                gv = lambda k: _num(rows[k][i]) if rows.get(k) and i < len(rows[k]) else None
                out.append({"p": m.group(1), "e": bool(m.group(2)),
                            "s": gv("sales"), "o": gv("op"), "n": gv("ni")})
            return out
        q = _cf1001("Q")
        yr = _cf1001("Y")
        # (2026-08-09) 잠정실적 반영 — WISEreport 는 확정 공시 전까지 해당 분기를 (E) 로
        # 유지한다(실측: SK하이닉스 7/29 발표 후 8월에도 2026/06(E)). DART 잠정공시 값으로
        # 그 분기를 실제값으로 덮고 prov 뱃지를 단다. 덮기 전 컨센은 cons_* 로 보존.
        try:
            live = json.loads((DB / "earnings_live.json").read_text(encoding="utf-8"))
            ev = evd = None
            for d8 in sorted(live.get("days") or {}):
                for it in live["days"][d8]:
                    if it.get("c") == code:
                        ev, evd = it, d8
            if ev:
                y0, m0_ = int(evd[:4]), int(evd[4:6])
                qe = (f"{y0-1}/12" if m0_ <= 3 else f"{y0}/03" if m0_ <= 6
                      else f"{y0}/06" if m0_ <= 9 else f"{y0}/09")
                for r0 in q:
                    if r0["p"] == qe and r0.get("e"):
                        r0["prov"] = evd
                        for k, sk in (("s", "sales"), ("o", "op"), ("n", "ni")):
                            if ev.get(sk) is not None:
                                r0["cons_" + k] = r0[k]
                                r0[k] = ev[sk]
        except Exception:
            pass
        # ② 목표주가 변동표(cTB24) — 개별 종목 페이지에서
        b = _get(f"https://navercomp.wisereport.co.kr/v2/company/c1010001.aspx?cmp_cd={code}")
        tp = []
        mt = re.search(r'id="cTB24".*?</table>', b, re.S)
        if mt:
            for r0 in re.findall(r"<tr[^>]*>(.*?)</tr>", mt.group(0), re.S):
                c = [CL(x) for x in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", r0, re.S)]
                if len(c) >= 6 and re.match(r"\d\d/\d\d/\d\d", c[1] or ""):
                    tp.append({"b": c[0], "d": c[1], "tp": _num(c[2]),
                               "prev": _num(c[3]), "chg": _num(c[4]), "op": c[5]})
        # ③ 컨센 영업이익 스냅샷(일별) — 추이 그래프
        snap = []
        try:
            db = DB / "kr_consensus.sqlite"
            if db.exists():
                cx = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=10)
                snap = [{"d": r0[0], "p": r0[1], "o": r0[2], "s": r0[3]}
                        for r0 in cx.execute(
                            "SELECT d,period,op,sales FROM snap WHERE code=? ORDER BY d,period", (code,))]
                cx.close()
        except Exception:
            pass
        res = {"q": q, "y": yr, "tp": tp, "snap": snap, "unit": "억원",
               "src": "WISEreport 분기표·증권사 목표가 + 컨센 일별 스냅샷"}
        _krfin_cache[code] = (now, res)
        if len(_krfin_cache) > 200:
            _krfin_cache.clear()
        return res
    except Exception as ex:
        return {"q": [], "y": [], "tp": [], "snap": [], "err": repr(ex)[:80]}


def _logged_in(request) -> bool:
    """namoobi 로그인 세션 여부. KIS 를 쓰는 엔드포인트는 이걸로 막는다.

    (2026-07-21) 분봉·호가·체결은 KIS 실계정을 호출한다. 공개로 열어두면
    유량제한에 걸려 파생·수급 수집 배치까지 같이 죽는다.
    클라이언트에서 버튼만 비활성화하면 URL 직접 호출로 뚫리므로 서버에서 막는다.
    """
    try:
        from auth_visitors import current_user
        return bool(current_user(request))
    except Exception:
        return False


_invt_cache = {}


@app.get("/api/invtable/kr/{code}")
def invtable_api(code: str, n: int = 20):
    """외국인·기관 순매매 일별 표 — 네이버 trend API.

    (2026-07-21) 일봉 차트 하단에 붙인다. 차트의 수급 '선'은 추세를 보고,
    이 표는 '어느 날 누가 얼마나' 를 숫자로 확인하는 용도다.
    제공: 종가·전일비·등락률·거래량·기관 순매수·외국인 순매수·개인 순매수·외국인 보유율
    (보유주수는 이 API 에 없다 — 보유율로 대체)
    ※ 투자자별 순매매는 장 마감 후 확정치다. 장중 값은 잠정치조차 공개 API 로는 안 나온다.
    """
    if not re.fullmatch(r"[0-9A-Za-z]{6}", code):
        raise HTTPException(400, "bad code")
    n = max(5, min(int(n or 20), 60))
    now = time.time()
    key = f"{code}:{n}"
    hit = _invt_cache.get(key)
    if hit and now - hit[0] < 600:
        return hit[1]
    try:
        url = ("https://m.stock.naver.com/api/stock/%s/trend?pageSize=%d&page=1" % (code, n))
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0",
                                                   "Referer": "https://m.stock.naver.com/"})
        rows = json.loads(urllib.request.urlopen(req, timeout=10).read())

        def _i(z):
            try:
                return int(str(z).replace(",", "").replace("+", "").strip())
            except Exception:
                return None
        out = [{"d": r.get("bizdate"),
                "px": _i(r.get("closePrice")),
                "chg": _i(r.get("compareToPreviousClosePrice")),
                "up": ((r.get("compareToPreviousPrice") or {}).get("code") in ("1", "2")),
                "vol": _i(r.get("accumulatedTradingVolume")),
                "org": _i(r.get("organPureBuyQuant")),
                "frg": _i(r.get("foreignerPureBuyQuant")),
                "ind": _i(r.get("individualPureBuyQuant")),
                "hold": r.get("foreignerHoldRatio")} for r in (rows or [])]
        res = {"items": out}
        _invt_cache[key] = (now, res)
        if len(_invt_cache) > 200:
            _invt_cache.clear()
        return res
    except Exception as e:
        return {"items": [], "err": repr(e)[:80]}


_ob_cache = {}


@app.get("/api/orderbook/kr/{code}")
def orderbook_api(request: Request, code: str):
    """호가 10단계 · 체결강도 · 최근 체결 — KIS 실전계정 REST(실시간).

    (2026-07-21) 네이버 호가·거래원은 20분 지연이라 단타 판단에 못 쓴다.
    KIS 는 실전 계정이면 지연이 없어 그대로 쓸 수 있다(mode=real 확인).
      · 호가   FHKST01010200 → askp1~10 / bidp1~10 + 잔량 + 총잔량
      · 체결강도 FHKST01010300 의 tday_rltv (당일 누적, 100 초과면 매수 우위)
      · 체결   같은 응답의 output 30건(초 단위)
    검증: 2026-07-21 마감값이 네이버 호가창과 완전 일치
          (매도 183,629@259,000 · 매수 38,824@258,500 · 총잔량 1,220,989 / 337,861)
    """
    if not re.fullmatch(r"[0-9]{6}", code):
        raise HTTPException(400, "bad code")
    if not _logged_in(request):
        raise HTTPException(401, "로그인 후 이용 가능합니다(KIS 부하 보호)")
    now = time.time()
    hit = _ob_cache.get(code)
    if hit and now - hit[0] < 5:          # 실시간이라 5초만 캐시(연타 방어)
        return hit[1]
    try:
        sys.path.insert(0, str(BASE / "scripts"))
        import kis_api as _K
        c = _K._creds()
        if not c:
            return {"err": "KIS 키 없음"}
        tok = _K._token(c)
        a = _K._get(c, tok, "/uapi/domestic-stock/v1/quotations/inquire-asking-price-exp-ccn",
                    "FHKST01010200", {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": code})
        o1 = a.get("output1") or {}
        o2 = a.get("output2") or {}

        def _i(z):
            try:
                return int(str(z).replace(",", "").strip())
            except Exception:
                return None
        ask = [{"p": _i(o1.get("askp%d" % i)), "q": _i(o1.get("askp_rsqn%d" % i))} for i in range(1, 11)]
        bid = [{"p": _i(o1.get("bidp%d" % i)), "q": _i(o1.get("bidp_rsqn%d" % i))} for i in range(1, 11)]
        # (2026-07-21) 체결 소스를 inquire-ccnl → inquire-time-itemconclusion 으로 교체.
        #   후자는 각 체결에 '그 시점의 매도/매수호가(askp/bidp)'를 준다 → 체결가를 호가와 비교해
        #   매수(매도호가 이상)·매도(매수호가 이하)를 실측 판정할 수 있다.
        #   틱 규칙(직전가 대비)은 삼성전자처럼 같은 가격 연속 체결이면 전부 '중립(—)'이 돼 무의미했다.
        from datetime import timezone as _tz0, timedelta as _td0
        _kn = datetime.now(_tz0(_td0(hours=9)))
        _hh0 = "%02d%02d00" % (min(_kn.hour, 15) if _kn.hour != 15 or _kn.minute <= 30 else 15,
                               _kn.minute if not (_kn.hour == 15 and _kn.minute > 30) else 30)
        t = _K._get(c, tok, "/uapi/domestic-stock/v1/quotations/inquire-time-itemconclusion",
                    "FHPST01060000", {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": code,
                                      "FID_INPUT_HOUR_1": _hh0})
        tk = t.get("output2") or []
        if not tk:      # 장 시작 전 등 — 마감 스냅으로 폴백
            t = _K._get(c, tok, "/uapi/domestic-stock/v1/quotations/inquire-time-itemconclusion",
                        "FHPST01060000", {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": code,
                                          "FID_INPUT_HOUR_1": "153000"})
            tk = t.get("output2") or []
        # 장중 투자자 가집계(잠정) — 거래소가 장중 몇 차례 발표하는 외인·기관 추정 순매수.
        #   확정치는 마감 후에 나오므로, 장중에 방향을 보려면 이 잠정치뿐이다.
        frg = org = None; est_series = []
        try:
            iv = _K._get(c, tok, "/uapi/domestic-stock/v1/quotations/investor-trend-estimate",
                         "HHPTJ04160200", {"MKSC_SHRN_ISCD": code})
            rows = iv.get("output2") or []
            # 회차(bsop_hour_gb 1~5)별 '당일 누적' 추정 순매수 — 오름차순 = 시간 진행.
            series = sorted(rows, key=lambda z: str(z.get("bsop_hour_gb") or ""))
            est_series = [{"gb": _i(z.get("bsop_hour_gb")),
                           "frg": _i(z.get("frgn_fake_ntby_qty")),
                           "org": _i(z.get("orgn_fake_ntby_qty"))} for z in series]
            if series:
                last = series[-1]
                frg, org = _i(last.get("frgn_fake_ntby_qty")), _i(last.get("orgn_fake_ntby_qty"))
        except Exception:
            est_series = []

        # ── 체결·호가에 나타난 '압력' 요약 (매매 권유가 아니라 현재 주문흐름의 서술)
        st = None
        try:
            st = float(tk[0].get("tday_rltv")) if tk else None
        except Exception:
            st = None
        at_, bt_ = _i(o1.get("total_askp_rsqn")), _i(o1.get("total_bidp_rsqn"))
        ratio = (bt_ / at_) if (at_ and bt_) else None          # 매수잔량 ÷ 매도잔량
        # (2026-07-21) '최근 30체결 중 상승'(수 초 노이즈·거의 항상 100%)을 빼고
        #   체결강도 '추세'(1시간 전 대비)로 대체 — 힘이 붙는 중인지 빠지는 중인지가 진짜 정보다.
        st_prev = None
        try:
            from datetime import timezone as _tz, timedelta as _td3
            _kst = _tz(_td3(hours=9))
            _nm = datetime.now(_kst); _m = _nm.hour * 60 + _nm.minute - 60
            _m = min(max(_m, 9 * 60 + 30), 15 * 60 + 30)
            _hh = "%02d%02d00" % (_m // 60, _m % 60)
            _r = _K._get(c, tok, "/uapi/domestic-stock/v1/quotations/inquire-time-itemconclusion",
                         "FHPST01060000", {"FID_COND_MRKT_DIV_CODE": "J",
                                          "FID_INPUT_ISCD": code, "FID_INPUT_HOUR_1": _hh})
            _o = (_r.get("output2") or [])
            if _o:
                st_prev = float(_o[0].get("tday_rltv") or 0)
        except Exception:
            st_prev = None
        parts, sc = [], 0
        if st is not None:
            v = 2 if st >= 120 else (1 if st >= 105 else (0 if st > 95 else (-1 if st > 80 else -2)))
            sc += v; parts.append({"k": "체결강도(당일 누적)", "v": round(st, 1), "s": v,
                                   "d": "100 초과 = 매수 체결 우위"})
        if st is not None and st_prev is not None:
            d1 = st - st_prev
            v = 1 if d1 >= 3 else (-1 if d1 <= -3 else 0)
            sc += v; parts.append({"k": "체결강도 추세(1시간)", "v": "%+.1f" % d1, "s": v,
                                   "d": "1시간 전 대비 — 오르면 매수세 유입, 내리면 이탈. 방금 30체결(수 초)보다 이 추세가 신뢰도 높다"})
        if ratio is not None:
            v = 1 if ratio >= 1.2 else (-1 if ratio <= 0.83 else 0)
            sc += v; parts.append({"k": "호가 잔량비(매수÷매도)", "v": round(ratio, 2), "s": v,
                                   "d": "1 초과 = 아래 받치는 물량이 두꺼움. 단 위쪽 매도벽은 저항이자 돌파 시 신호라 해석이 갈린다"})
        if frg is not None and org is not None:
            tot = frg + org
            v = 1 if tot > 0 else (-1 if tot < 0 else 0)
            sc += v; parts.append({"k": "외인+기관 가집계", "v": tot, "s": v,
                                   "d": "장중 추정 순매수(잠정) — 확정치는 마감 후"})
        lab = ("매수 우위" if sc >= 3 else "약한 매수 우위" if sc >= 1 else
               "중립" if sc == 0 else "약한 매도 우위" if sc >= -2 else "매도 우위")
        res = {"ask": ask, "bid": bid,
               "ask_tot": at_, "bid_tot": bt_,
               "at": o1.get("aspr_acpt_hour"),
               "px": _i(o2.get("stck_prpr")),
               "strength": (tk[0].get("tday_rltv") if tk else None),
               "frg_est": frg, "org_est": org, "est_series": est_series,
               "score": sc, "label": lab, "parts": parts,
               "ticks": [{"t": x.get("stck_cntg_hour"), "p": _i(x.get("stck_prpr")),
                          "v": _i(x.get("cnqn")), "sg": x.get("prdy_vrss_sign"),
                          "ask": _i(x.get("askp")), "bid": _i(x.get("bidp"))}
                         for x in tk[:30]],
               "src": "KIS(%s) 실시간" % c.get("mode")}
        # (2026-07-21) 체결별 매수/매도 판정 — 호가 우선 + 틱 규칙 보조(혼합).
        #   1차: 체결가 >= 매도호가 → 매수 주도 / <= 매수호가 → 매도 주도
        #   2차(중간가 체결): 직전 체결가 대비 오르면 매수·내리면 매도로 보조 판정
        #   그래도 안 갈리면 중립(중간가 매칭 — NXT 중간가·종가 단일가에서 흔함, 매수·매도 균형).
        _tks = res["ticks"]
        _prev = None
        for i in range(len(_tks) - 1, -1, -1):
            p_, a_, b_ = _tks[i]["p"], _tks[i].get("ask"), _tks[i].get("bid")
            older = _tks[i + 1]["p"] if i + 1 < len(_tks) else None
            d = None
            if p_ is not None and a_ and b_:
                if p_ >= a_:
                    d = "buy"
                elif p_ <= b_:
                    d = "sell"
            if d is None and p_ is not None and older is not None:   # 중간가 → 틱 규칙 보조
                d = "buy" if p_ > older else ("sell" if p_ < older else None)
            if d is None:
                d = "mid"
            _tks[i]["side"] = d
            if d in ("buy", "sell"):
                _prev = d
        bq = sum(t["v"] or 0 for t in _tks if t["side"] == "buy")
        sq = sum(t["v"] or 0 for t in _tks if t["side"] == "sell")
        res["tick_buy"] = bq
        res["tick_sell"] = sq
        _ob_cache[code] = (now, res)
        if len(_ob_cache) > 200:
            _ob_cache.clear()
        return res
    except Exception as e:
        return {"err": repr(e)[:100]}


_str_cache = {}


@app.get("/api/strength/kr/{code}")
def strength_curve_api(request: Request, code: str):
    """체결강도 '장중 추이' — 09:30부터 30분 간격으로 스냅샷.

    (2026-07-21) '최근 30체결'은 삼성전자처럼 유동성 큰 종목에선 1~2초라 노이즈다.
    체결강도(tday_rltv)는 당일 누적이라 값 하나론 흐름을 못 본다.
    → inquire-time-itemconclusion 의 FID_INPUT_HOUR_1 로 특정 시각의 체결강도를 조회할 수 있어
      하루를 30분 간격으로 훑어 곡선을 만든다. '매수세가 붙는 중인지 빠지는 중인지'가 보인다.
    실측(005930): 10시 68.7 → 11:30 90.0 → 13시 86.8 → 14:30 81.1 → 15시 82.9
    과거 시각 값은 고정이라 캐시를 길게 잡는다(5분).
    """
    if not re.fullmatch(r"[0-9]{6}", code):
        raise HTTPException(400, "bad code")
    if not _logged_in(request):
        raise HTTPException(401, "로그인 후 이용 가능합니다")
    now = time.time()
    hit = _str_cache.get(code)
    if hit and now - hit[0] < 300:
        return hit[1]
    try:
        from concurrent.futures import ThreadPoolExecutor
        sys.path.insert(0, str(BASE / "scripts"))
        import kis_api as _K
        c = _K._creds()
        if not c:
            return {"err": "KIS 키 없음"}
        tok = _K._token(c)
        # KST 현재 분 — 장중이면 지금까지, 마감 후면 15:30 까지
        from datetime import timezone, timedelta
        kst = timezone(timedelta(hours=9))
        nm = datetime.now(kst)
        cur = nm.hour * 60 + nm.minute
        cur = min(max(cur, 9 * 60 + 30), 15 * 60 + 30)
        slots = list(range(9 * 60 + 30, cur + 1, 30))
        if slots and slots[-1] != cur:
            slots.append(cur)

        def _one(m):
            hh = "%02d%02d00" % (m // 60, m % 60)
            try:
                r = _K._get(c, tok, "/uapi/domestic-stock/v1/quotations/inquire-time-itemconclusion",
                            "FHPST01060000", {"FID_COND_MRKT_DIV_CODE": "J",
                                              "FID_INPUT_ISCD": code, "FID_INPUT_HOUR_1": hh})
                o = (r.get("output2") or [])
                if not o:
                    return None
                x = o[0]
                return {"t": "%02d:%02d" % (m // 60, m % 60),
                        "cttr": float(x.get("tday_rltv") or 0),
                        "vol": int(x.get("acml_vol") or 0)}
            except Exception:
                return None

        with ThreadPoolExecutor(max_workers=8) as ex:
            pts = [p for p in ex.map(_one, slots) if p]
        # 구간 거래량(그 30분에 실제로 붙은 양) = 누적 차분
        for i in range(len(pts) - 1, 0, -1):
            pts[i]["dvol"] = pts[i]["vol"] - pts[i - 1]["vol"]
        if pts:
            pts[0]["dvol"] = pts[0]["vol"]
        res = {"pts": pts, "src": "KIS 실시간"}
        _str_cache[code] = (now, res)
        if len(_str_cache) > 200:
            _str_cache.clear()
        return res
    except Exception as e:
        return {"err": repr(e)[:100]}


_tick_cache = {}


@app.get("/api/ticks/kr/{code}")
def ticks_api(request: Request, code: str, pages: int = 6):
    """시간별 시세(체결가 + 그 시점 매도/매수 호가) — 네이버 sise_time 파싱.

    (2026-07-21) 분봉 차트 아래에 붙여 '공격성'을 같이 본다.
      체결가 >= 매도호가 → 공격적 매수(사는 쪽이 값을 올려 가져감)
      체결가 <= 매수호가 → 공격적 매도(파는 쪽이 값을 내려 던짐)
      그 사이            → 중립
    호가 스냅샷이 체결 직후 값이라 정확히 일치하지 않는 경우가 있어 '=' 가 아니라 부등호로 판정한다.
    한 페이지 10행(1분 단위) — 기본 6페이지 ≈ 60분.

    ※ 네이버 고지대로 이 데이터는 20분 지연이다. 실시간 진입 판단용이 아니라
      '방금까지 매수·매도 중 어느 쪽이 공격적이었나'를 사후 확인하는 용도다.
    """
    if not re.fullmatch(r"[0-9A-Za-z]{6}", code):
        raise HTTPException(400, "bad code")
    if not _logged_in(request):
        raise HTTPException(401, "로그인 후 이용 가능합니다")
    pages = max(1, min(int(pages or 6), 12))
    now = time.time()
    key = f"{code}:{pages}"
    hit = _tick_cache.get(key)
    if hit and now - hit[0] < 30:
        return hit[1]
    out, seen = [], set()

    def _parse(html):
        rows = []
        for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S):
            tds = [re.sub(r"<[^>]+>", "", x).replace("&nbsp;", " ").strip()
                   for x in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
            tds = [t for t in tds if t.strip()]
            if len(tds) >= 7 and re.match(r"^\d{2}:\d{2}", tds[0]):
                rows.append(tds)
        return rows

    def _get(tt, pg):
        url = ("https://finance.naver.com/item/sise_time.naver"
               "?code=%s&thistime=%s&page=%d" % (code, tt, pg))
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0",
                                                   "Referer": "https://finance.naver.com/"})
        return urllib.request.urlopen(req, timeout=10).read().decode("euc-kr", "ignore")

    try:
        # thistime 은 '거래일'이어야 한다. 휴장일·장 시작 전이면 빈 표가 온다(실측).
        # → 오늘(현재시각)부터 시작해 하루씩 거슬러 올라가며 데이터가 있는 날을 찾는다.
        from datetime import timedelta as _td2
        cands = [datetime.now().strftime("%Y%m%d%H%M%S")] + [
            (datetime.now() - _td2(days=k)).strftime("%Y%m%d") + "160000" for k in range(0, 8)]
        thistime, first = None, []
        for tt in cands:
            r0 = _parse(_get(tt, 1))
            if r0:
                thistime, first = tt, r0
                break
        if not thistime:
            return {"items": [], "err": "최근 8일 내 시간별시세 없음"}
        for pg in range(1, pages + 1):
            url = None
            n0 = len(out)
            for tds in (first if pg == 1 else _parse(_get(thistime, pg))):
                if tds[0] in seen:
                    continue
                seen.add(tds[0])

                def _n(z):
                    try:
                        return int(str(z).replace(",", "").strip())
                    except Exception:
                        return None
                px, ask, bid = _n(tds[1]), _n(tds[3]), _n(tds[4])
                side = None
                if px is not None and ask is not None and bid is not None:
                    side = "buy" if px >= ask else ("sell" if px <= bid else "mid")
                out.append({"t": tds[0], "px": px, "ask": ask, "bid": bid,
                            "cum": _n(tds[5]), "vol": _n(tds[6]), "side": side})
            if len(out) == n0:       # 더 이상 안 나오면 중단(장 시작 전 구간 등)
                break
        # 체결강도 = 공격적 매수 거래량 / 공격적 매도 거래량 × 100 (100 초과면 매수 우위)
        bv = sum(r["vol"] or 0 for r in out if r["side"] == "buy")
        sv = sum(r["vol"] or 0 for r in out if r["side"] == "sell")
        res = {"items": out, "buy_vol": bv, "sell_vol": sv,
               "date": thistime[:8],
               "strength": round(bv / sv * 100, 1) if sv else None,
               "delay": "20분 지연(네이버 고지)"}
        _tick_cache[key] = (now, res)
        if len(_tick_cache) > 200:
            _tick_cache.clear()
        return res
    except Exception as e:
        return {"items": [], "err": repr(e)[:80]}


_chart_cache = {}

def _agg(t, o, h, l, c, v, keyfn):
    """봉 합치기 — keyfn(시각문자열)이 같은 것끼리 시가=처음·고가=max·저가=min·종가=마지막·거래량=합.
    분봉→N분봉, 일봉→주봉·월봉 모두 이 하나로 처리한다."""
    T, O, H, L, C, V = [], [], [], [], [], []
    prev = None
    for i in range(len(t)):
        if c[i] is None:
            continue
        k = keyfn(t[i])
        if k != prev:
            T.append(t[i]); O.append(o[i]); H.append(h[i]); L.append(l[i]); C.append(c[i]); V.append(v[i] or 0)
            prev = k
        else:
            if H[-1] is None or (h[i] is not None and h[i] > H[-1]): H[-1] = h[i]
            if L[-1] is None or (l[i] is not None and l[i] < L[-1]): L[-1] = l[i]
            C[-1] = c[i]; V[-1] = (V[-1] or 0) + (v[i] or 0)
    return {"t": T, "o": O, "h": H, "l": L, "c": C, "v": V}


# 지원 주기 — 네이버 차트와 동일 구성(분봉 드롭다운 + 일/주/월)
TF_MIN = {"1m": 1, "3m": 3, "5m": 5, "10m": 10, "30m": 30, "60m": 60}


@app.get("/api/chart/{mkt}/{code}")
def chart_api(request: Request, mkt: str, code: str, tf: str = "d", pp: int = 0):
    """종목 차트 프록시 — KR: 네이버 / US: Yahoo v8.

    tf: 1m·3m·5m·10m·30m·60m(분봉) · d(일) · w(주) · M(월)
      · KR 분봉은 네이버가 1분봉만 준다(interval 파라미터 무시) → 서버에서 N분으로 합친다.
        실측: 1분봉 3,400개 = 최근 9거래일. 5분 집계 시 약 680봉.
      · US 분봉은 Yahoo 가 1m(최근 5일)·5m(최근 1개월)을 준다. 3분은 1m 에서, 10·30·60분은 5m 에서 합친다.
      · 주·월봉은 일봉을 합쳐서 만든다(추가 호출 없음).
    캐시: 분봉 30초 / 그 외 60초.
    """
    if mkt not in ("kr", "us") or not re.fullmatch(r"[A-Za-z0-9.\-]{1,12}", code):
        raise HTTPException(400, "bad params")
    if tf not in TF_MIN and tf not in ("d", "w", "M"):
        raise HTTPException(400, "bad tf")
    if tf in TF_MIN and not _logged_in(request):
        raise HTTPException(401, "분봉은 로그인 후 이용 가능합니다(KIS·외부 API 부하 보호)")
    pp = 1 if (pp and tf in TF_MIN) else 0   # 시간외포함은 분봉에서만 의미 (KR=KIS UN 통합 · US=Yahoo prepost)
    key = f"{mkt}:{code}:{tf}:{pp}"; now = time.time()
    hit = _chart_cache.get(key)
    if hit and now - hit[0] < (30 if tf in TF_MIN else 60):
        return hit[1]
    try:
        from datetime import date as _d, timedelta as _td, datetime as _dt
        if tf in TF_MIN:
            n = TF_MIN[tf]
            base = None
            if mkt == "kr" and pp:
                # (2026-08-04) 시간외포함 — KIS 일별분봉(FHKST03010230) UN(KRX+NXT 통합).
                #   프리마켓 08:00~08:50 · 정규 09:00~15:30 · 애프터 ~20:00 (NXT 체결 포함, 실측).
                #   네이버 분봉은 정규장(09:00~15:30)만 줘서 못 쓴다(넓은 시간창 요청해도 동일 — 실측).
                #   120봉/호출·과거 페이징 → 최근 3거래일만(호출 ~20회, 30초 캐시로 방어).
                sys.path.insert(0, str(BASE / "scripts"))
                import kis_api as _K
                c_ = _K._creds(); tok_ = _K._token(c_)
                acc, dt8, hr6, seen = [], _d.today().strftime("%Y%m%d"), "200000", set()
                for _pg in range(24):
                    j = _K._get(c_, tok_, "/uapi/domestic-stock/v1/quotations/inquire-time-dailychartprice",
                                "FHKST03010230",
                                {"FID_COND_MRKT_DIV_CODE": "UN", "FID_INPUT_ISCD": code,
                                 "FID_INPUT_DATE_1": dt8, "FID_INPUT_HOUR_1": hr6,
                                 "FID_PW_DATA_INCU_YN": "Y", "FID_FAKE_TICK_INCU_YN": "N"})
                    o2 = j.get("output2") or []
                    o2 = [x for x in o2 if (x.get("stck_bsop_date"), x.get("stck_cntg_hour")) not in seen]
                    if not o2:
                        break
                    for x in o2:
                        seen.add((x.get("stck_bsop_date"), x.get("stck_cntg_hour")))
                    acc.extend(o2)
                    if len({x["stck_bsop_date"] for x in acc}) > 3:      # 3거래일 초과분 등장 → 중단
                        break
                    last = o2[-1]; dt8, hr6 = last["stck_bsop_date"], last["stck_cntg_hour"]
                    time.sleep(0.05)
                acc = [x for x in acc if str(x.get("stck_prpr") or "0") != "0"]   # 무체결(0 채움) 분 제거
                days3 = sorted({x["stck_bsop_date"] for x in acc})[-3:]
                acc = [x for x in acc if x["stck_bsop_date"] in days3]
                acc.reverse()                                            # DESC → ASC

                def _f(x, k):
                    try: return float(x.get(k))
                    except Exception: return None
                if acc:
                    base = {"t": [x["stck_bsop_date"] + str(x.get("stck_cntg_hour") or "")[:4] for x in acc],
                            "o": [_f(x, "stck_oprc") for x in acc], "h": [_f(x, "stck_hgpr") for x in acc],
                            "l": [_f(x, "stck_lwpr") for x in acc], "c": [_f(x, "stck_prpr") for x in acc],
                            "v": [_f(x, "cntg_vol") for x in acc]}
                # (2026-08-04 실측) ETF 는 NXT 미상장(NX 현재가 0)이고 KIS 통합 분봉도 0건이다:
                #   일별분봉(FHKST03010230) UN = 과거일 포함 전부 0건 · 당일분봉(FHKST03010200) UN·NX = 전 봉 0값
                #   · J 는 15:30 이후가 종가 채움봉(vol 0).
                #   다만 KRX 시간외단일가(16:00~18:00, 10분 단위)는 ETF 도 실체결이 있고
                #   시간외시간별체결(FHPST02310000)로 당일치를 받을 수 있다(실측 069500 12건) → 아래에서 병합.
            _ppf = _ppo = bool(pp and mkt == "kr" and base is None)   # 시간외 미제공 폴백 여부(단일가 병합 성공 시 ppo 로 전환)
            if mkt == "kr" and base is None:
                E = _d.today().strftime("%Y%m%d") + "1600"
                S = (_d.today() - _td(days=20)).strftime("%Y%m%d") + "0900"
                url = (f"https://api.stock.naver.com/chart/domestic/item/{code}"
                       f"/minute?startDateTime={S}&endDateTime={E}")
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0",
                                                           "Referer": "https://m.stock.naver.com/"})
                rows = json.loads(urllib.request.urlopen(req, timeout=15).read())
                t = [str(r.get("localDateTime") or "")[:12] for r in rows]
                base = {"t": t,
                        "o": [r.get("openPrice") for r in rows], "h": [r.get("highPrice") for r in rows],
                        "l": [r.get("lowPrice") for r in rows], "c": [r.get("currentPrice") for r in rows],
                        "v": [r.get("accumulatedTradingVolume") for r in rows]}
                if pp:
                    try:      # 당일 시간외단일가 체결(16:00~18:00) 병합 — 단일가라 봉은 플랫(o=h=l=c)
                        j = _K._get(c_, tok_, "/uapi/domestic-stock/v1/quotations/inquire-time-overtimeconclusion",
                                    "FHPST02310000",
                                    {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": code,
                                     "FID_HOUR_CLS_CODE": "1"})
                        # 자정 이후에도 TR 은 직전 거래일 시간외를 준다 → 날짜는 마지막 정규장 봉 기준으로 라벨
                        today8 = base["t"][-1][:8] if base["t"] else _d.today().strftime("%Y%m%d")
                        for xx in reversed(j.get("output2") or []):       # DESC → ASC
                            try:
                                p_ = float(xx.get("stck_prpr") or 0); v_ = float(xx.get("cntg_vol") or 0)
                            except Exception:
                                continue
                            hh = str(xx.get("stck_cntg_hour") or "")[:4]
                            if p_ <= 0 or len(hh) < 4:
                                continue
                            tt = today8 + hh
                            if base["t"] and tt <= base["t"][-1]:
                                continue
                            base["t"].append(tt); base["o"].append(p_); base["h"].append(p_)
                            base["l"].append(p_); base["c"].append(p_); base["v"].append(v_)
                            _ppf = False                                  # 시간외단일가라도 붙었으면 '미제공' 아님
                    except Exception:
                        pass
            if mkt == "us":
                iv, rg = ("1m", "5d") if n <= 3 else ("5m", "1mo")
                # (2026-08-04) pp=1 이면 프리장(04:00~)·애프터장(~20:00 ET) 체결 포함(야후 Extended Hours).
                #   기본(pp=0)은 정규장만 — 프론트 토글 default 정규장.
                url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(code)}"
                       f"?range={rg}&interval={iv}&includePrePost={'true' if pp else 'false'}")
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                j = json.loads(urllib.request.urlopen(req, timeout=15).read())
                res = j["chart"]["result"][0]; q = res["indicators"]["quote"][0]
                off = (res.get("meta") or {}).get("gmtoffset") or 0     # 현지 거래시각으로 표시
                ts = res.get("timestamp") or []
                base = {"t": [_dt.utcfromtimestamp(x + off).strftime("%Y%m%d%H%M") for x in ts],
                        "o": q.get("open"), "h": q.get("high"), "l": q.get("low"),
                        "c": q.get("close"), "v": q.get("volume")}
                # (2026-08-04) 사용자 요청으로 이상틱 필터 없음(실제 체결 그대로 — 급등락 즉시 확인용).
                #   결측 OHLC만 종가로 보정(렌더 깨짐 방지).
                for i in range(len(base["c"] or [])):
                    c_ = base["c"][i]
                    if c_ is None: continue
                    if base["o"][i] is None: base["o"][i] = c_
                    if base["h"][i] is None: base["h"][i] = max(base["o"][i], c_)
                    if base["l"][i] is None: base["l"][i] = min(base["o"][i], c_)
            # 분 단위 버킷 — 같은 날짜 안에서 (시*60+분)//n
            def _kf(s):
                return s[:8] + str((int(s[8:10]) * 60 + int(s[10:12])) // n)
            out = _agg(base["t"], base["o"], base["h"], base["l"], base["c"], base["v"], _kf) \
                if n > 1 else base
            out["tf"] = tf
            if _ppf:
                out["ppf"] = 1     # 프론트: '시간외 미제공 종목(정규장 표시)' 안내
            elif _ppo:
                out["ppo"] = 1     # 프론트: 'NXT 미상장 — 시간외단일가(16:00~18:00)만 포함' 안내
        else:
            # 필요한 이력 = 표시 250봉 + 최장 이동평균(240) + 줌아웃 여유.
            #   일 10년(≈2,500봉) · 주 15년(≈780주) · 월 30년(≈360개월)
            #   실측: 네이버 일봉은 1990년까지, Yahoo 는 상장 이후 전부 준다.
            YRS = {"d": 10, "w": 15, "M": 30}[tf]
            if mkt == "kr":
                E = _d.today().strftime("%Y%m%d")
                S = (_d.today() - _td(days=int(YRS * 366))).strftime("%Y%m%d")
                url = f"https://api.stock.naver.com/chart/domestic/item/{code}/day?startDateTime={S}&endDateTime={E}"
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                rows = json.loads(urllib.request.urlopen(req, timeout=20).read())
                out = {"t": [str(r.get("localDate") or "") for r in rows],
                       "o": [r.get("openPrice") for r in rows], "h": [r.get("highPrice") for r in rows],
                       "l": [r.get("lowPrice") for r in rows], "c": [r.get("closePrice") for r in rows],
                       "v": [r.get("accumulatedTradingVolume") for r in rows]}
            else:
                # range=max 는 Yahoo 가 자동으로 주/월로 다운샘플해 버린다(실측: 27년치가 331봉).
                # 반드시 period1/period2 로 기간을 지정해야 진짜 일봉이 온다.
                _p2 = int(time.time()); _p1 = _p2 - int(YRS * 366 * 86400)
                url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(code)}"
                       f"?period1={_p1}&period2={_p2}&interval=1d")
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                j = json.loads(urllib.request.urlopen(req, timeout=20).read())
                res = j["chart"]["result"][0]; q = res["indicators"]["quote"][0]
                ts = res.get("timestamp") or []
                out = {"t": [_dt.utcfromtimestamp(x).strftime("%Y%m%d") for x in ts],
                       "o": q.get("open"), "h": q.get("high"), "l": q.get("low"),
                       "c": q.get("close"), "v": q.get("volume")}
            if tf == "w":
                out = _agg(out["t"], out["o"], out["h"], out["l"], out["c"], out["v"],
                           lambda s: _dt.strptime(s, "%Y%m%d").strftime("%G%V"))   # ISO 주
            elif tf == "M":
                out = _agg(out["t"], out["o"], out["h"], out["l"], out["c"], out["v"], lambda s: s[:6])
            out["tf"] = tf
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
_hold_qcache = {}   # ETF 구성종목 시세(현재가·전일비·등락률) 45초 캐시
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

def _etf_quotes(mkt, codes):
    """구성종목 코드 → {code: {px 현재가, chg 전일비(부호), chgp 등락률%(부호)}}.
       KR: 네이버 폴링 배치(1회 호출, delayTime=0 실시간). US: Yahoo v7 quote(crumb). 실패 비차단."""
    codes = [c for c in dict.fromkeys(codes) if c]
    if not codes:
        return {}
    qm = {}
    try:
        if mkt == "kr":
            qu = "https://polling.finance.naver.com/api/realtime/domestic/stock/" + ",".join(codes)
            qreq = urllib.request.Request(qu, headers={
                "User-Agent": "Mozilla/5.0", "Referer": "https://finance.naver.com/"})
            qd = json.loads(urllib.request.urlopen(qreq, timeout=10).read().decode("utf-8", "ignore"))
            for it in (qd.get("datas") or []):
                # compareToPreviousClosePrice·fluctuationsRatio 는 이미 부호 포함(하락 = 음수).
                qm[it.get("itemCode")] = {"px": _pctnum(it.get("closePrice")),
                                          "chg": _pctnum(it.get("compareToPreviousClosePrice")),
                                          "chgp": _pctnum(it.get("fluctuationsRatio"))}
        else:
            import sys as _sys
            _sys.path.insert(0, str(BASE / "scripts"))
            import ta_screen as _T
            op, crumb = _yahoo_oc()
            qu = ("https://query1.finance.yahoo.com/v7/finance/quote?symbols=%s&crumb=%s"
                  % (urllib.parse.quote(",".join(codes)), urllib.parse.quote(crumb)))
            qj = _T.jget(qu, opener=op, timeout=12)
            for it in ((qj.get("quoteResponse", {}) or {}).get("result") or []):
                rnd = lambda v: round(v, 2) if isinstance(v, (int, float)) else None
                qm[it.get("symbol")] = {"px": rnd(it.get("regularMarketPrice")),
                                        "chg": rnd(it.get("regularMarketChange")),
                                        "chgp": rnd(it.get("regularMarketChangePercent"))}
    except Exception:
        pass
    return qm

@app.get("/api/etf/holdings/{mkt}/{code}")
def etf_holdings(mkt: str, code: str):
    if mkt not in ("kr", "us") or not re.fullmatch(r"[A-Za-z0-9.\-]{1,12}", code):
        raise HTTPException(400, "bad params")
    key = f"{mkt}:{code}"; now = time.time()
    # ── 구성종목(이름·비중·코드): 6시간 캐시 ──
    hit = _hold_cache.get(key)
    if hit and now - hit[0] < 6 * 3600:
        base = hit[1]
    else:
        base = {"mkt": mkt, "code": code, "holdings": []}
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
                    base["holdings"].append({"n": nm, "c": x.get("itemCode") or "",
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
                    base["holdings"].append({"n": nm, "c": h.get("symbol") or "", "w": w})
        except Exception as e:
            base["err"] = str(e)[:120]
        _hold_cache[key] = (now, base)
        if len(_hold_cache) > 600:
            _hold_cache.clear()
    # ── 시세·전일비·등락률 조인: 45초 캐시(장중 변동 반영, 네이버처럼) ──
    out = {"mkt": mkt, "code": code, "holdings": [dict(h) for h in base["holdings"]]}
    if base.get("err"):
        out["err"] = base["err"]
    qhit = _hold_qcache.get(key)
    if qhit and now - qhit[0] < 45:
        qm = qhit[1]
    else:
        qm = _etf_quotes(mkt, [h.get("c") for h in out["holdings"]])
        _hold_qcache[key] = (now, qm)
        if len(_hold_qcache) > 800:
            _hold_qcache.clear()
    for h in out["holdings"]:
        q = qm.get(h.get("c"))
        if q:
            h.update(q)
    out["quoted"] = bool(qm)
    return out

# ── 종목별 투자자 수급 (외국인·기관·개인 누적순매수) ──
#   1년치: 네이버 frgn.naver 13페이지 (외국인·기관 순매매량만 제공)
#   최근 30거래일: KIS FHKST01010900 (개인 포함 3주체 실측 — 네이버 값과 일치 검증됨)
#   병합: KIS 구간은 KIS 우선(개인 실측), 그 이전 개인은 null → 프론트가 −(외인+기관) 추정 점선
_inv_cache = {}

def _frgn_naver(code: str, pages: int = 80):
    # (2026-07-21) 13페이지(≈1년) → 80페이지(≈6.5년).
    #   일봉 이력을 10년으로 늘린 뒤 수급 패널만 1년이라 화면 오른쪽 끝에만 그려졌다.
    #   실측: frgn.naver 는 2005년까지 제공하고, 10워커 병렬로 80페이지 3.7초.
    #   확정치라 하루 1번만 바뀌므로 캐시를 길게 잡아 반복 호출을 없앤다.
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
    if hit and now - hit[0] < 21600:     # 6시간 캐시 — 투자자별 순매매는 마감 후 확정이라 하루 1번만 바뀐다
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

@app.get("/api/stock_deriv/{code}")
def stock_deriv_api(code: str):
    """종목별 파생 포지셔닝 — KR 파생상장 전 종목(FSC T+1) + US 옵션 종목(Yahoo, 티커).
       5지표(베이시스·선물OI·PCR(OI)·IV스큐·GEX — US는 옵션 3종만) 시계열 + 60일 z.
       미수록 종목은 404 → 프론트가 프록시 카드로 대체."""
    if not re.fullmatch(r"[A-Za-z0-9.\-]{1,12}", code):
        raise HTTPException(400, "bad code")
    p = DB / "stock_deriv.json"
    if not p.exists():
        raise HTTPException(404, "stock_deriv 없음")
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        raise HTTPException(500, f"stock_deriv 파싱 실패: {e}")
    s = (d.get("stocks") or {}).get(code)
    if not s or not s.get("days"):
        raise HTTPException(404, "파생 미상장 종목")
    # (2026-07-24) 주식선물만 상장·옵션 미상장 종목 구분 — 프론트가 '누적 중'이 아니라
    #   '옵션 미상장'으로 안내하도록 이력 전체에서 옵션값 존재 여부를 내려준다
    has_opt = any((x.get("pcr_oi") is not None) or (x.get("gex") is not None)
                  for x in s["days"])
    out = {"asof": d.get("asof"), "src": d.get("src"), "name": s.get("name"),
           "z": s.get("z"), "latest": s.get("latest"), "has_opt": has_opt,
           # 스파크라인용 최근 60일만 (전송량 절약)
           "days": s["days"][-60:]}
    return Response(content=json.dumps(out, ensure_ascii=False),
                    media_type="application/json", headers={"Cache-Control": "no-cache"})

_gh_cache = {"mtime": 0, "data": None}   # (2026-08-02) 10년 이력 확장으로 파일이 커져 mtime 캐시
@app.get("/api/global_hist_one")
def global_hist_one(s: str):
    """(2026-08-02) 글로벌시황 차트 — 종목 1개 이력만(전체 전송 제거, 회선 병목 해소)."""
    if not re.fullmatch(r"[A-Za-z0-9.^=\-_: ]{1,20}", s):
        raise HTTPException(400, "bad sym")
    p = DB / "global_hist.json"
    if not p.exists():
        raise HTTPException(404, "no hist")
    try:
        mt = p.stat().st_mtime
        if _gh_cache["mtime"] != mt:
            _gh_cache["data"] = json.loads(p.read_text(encoding="utf-8"))
            _gh_cache["mtime"] = mt
        d = _gh_cache["data"]
    except Exception as e:
        raise HTTPException(500, str(e))
    h = d.get(s)
    if not h:
        raise HTTPException(404, "sym 없음")
    return Response(content=json.dumps(h, ensure_ascii=False),
                    media_type="application/json", headers={"Cache-Control": "max-age=300"})

_pop_cache = {"t": 0, "data": None}
@app.get("/api/popular")
def popular():
    """(2026-08-02) 네이버 인기 검색 종목 TOP10 프록시 — 3분 캐시. 글로벌시황 우측 패널용."""
    import time as _t, urllib.request as _ur
    now = _t.time()
    if _pop_cache["data"] and now - _pop_cache["t"] < 180:
        return _pop_cache["data"]
    try:
        req = _ur.Request("https://m.stock.naver.com/api/stocks/searchTop?page=1&pageSize=30",
                          headers={"User-Agent": "Mozilla/5.0 (namoobi)"})
        j = json.loads(_ur.urlopen(req, timeout=10).read().decode("utf-8"))
        f = lambda s: float(str(s).replace(",", "")) if s not in (None, "") else None
        rows = [{"name": x.get("stockName"), "code": x.get("itemCode"),
                 "px": f(x.get("closePrice")), "chg": f(x.get("compareToPreviousClosePrice")),
                 "pct": f(x.get("fluctuationsRatio")), "mkt": x.get("marketStatus")}
                for x in (j.get("stocks") or [])[:30]]
        out = {"asof": __import__("datetime").datetime.now().strftime("%H:%M"), "rows": rows}
        _pop_cache["t"] = now; _pop_cache["data"] = out
        return out
    except Exception:
        return _pop_cache["data"] or {"asof": None, "rows": []}

_sdl_cache = {}
@app.get("/api/stock_deriv_live/{code}")
def stock_deriv_live(code: str):
    """(2026-07-24) 종목 파생 카드 장중 온디맨드 — 개별 주식선물 T+0 (KIS, 5분 캐시).
       베이시스·선물OI만 장중 갱신 가능(옵션 3종은 장중 호가 공백으로 왜곡 → 확정치 유지)."""
    if not re.fullmatch(r"\d{6}", code):
        raise HTTPException(400, "bad code")
    now = time.time()
    hit = _sdl_cache.get(code)
    if hit and now - hit[0] < 300:
        return hit[1]
    try:
        sys.path.insert(0, str(BASE / "scripts"))
        import kis_api as K
        q = K.stock_futures_quote(code)
    except Exception as e:
        raise HTTPException(502, f"KIS 조회 실패: {e}")
    if not q:
        raise HTTPException(404, "주식선물 미상장")
    from datetime import timezone, timedelta
    kst = timezone(timedelta(hours=9))
    q["t"] = datetime.now(kst).strftime("%H:%M")
    q["basis_pct"] = round(q["basis"] / q["spot"] * 100, 3) if q.get("spot") else None
    # (2026-07-24) 장중 z — 확정 60일 분포에 장중값을 대입해 실시간 z 산출 (베이시스% · OI 일간변화)
    try:
        sd = json.loads((DB / "stock_deriv.json").read_text(encoding="utf-8"))
        days = ((sd.get("stocks") or {}).get(code) or {}).get("days") or []
        def _zlive(series, live):
            xs = [x for x in series if x is not None][-60:]
            if live is None or len(xs) < 20:
                return None
            mu = sum(xs) / len(xs)
            sdv = (sum((x - mu) ** 2 for x in xs) / len(xs)) ** 0.5
            return round((live - mu) / sdv, 2) if sdv > 1e-9 else None
        bp = [d.get("basis_pct") for d in days]
        oi = [d.get("fut_oi") for d in days]
        oic = [(oi[i] - oi[i - 1]) if (oi[i] is not None and oi[i - 1] is not None) else None
               for i in range(1, len(oi))]
        q["z_basis_live"] = _zlive(bp, q.get("basis_pct"))
        q["z_oi_live"] = _zlive(oic, q.get("oi_chg"))
    except Exception:
        pass
    _sdl_cache[code] = (now, q)
    if len(_sdl_cache) > 300:
        _sdl_cache.clear()
    return q

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
            "SELECT month,m2,kospi,kosdaq,tdep FROM kr_liq_monthly ORDER BY month").fetchall()
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

# ── (2026-08-08) 아파트 단지별 실거래 — scripts/apt_db.py 가 rtms 수집과 함께 적재 ──
APTDB = DB / "apt.sqlite"
# (2026-08-08) 비아파트는 별도 파일 — 아파트 심층 백필과 동시에 수집하려면 파일을 나눠야
# SQLite 쓰기 락이 충돌하지 않는다. 유형(kind)으로 어느 파일을 열지 고른다.
APTDB_ETC = DB / "apt_etc.sqlite"

def _aptpath(kind=""):
    return APTDB if (kind or "apt") == "apt" else APTDB_ETC

def _aptcx(kind=""):
    path = _aptpath(kind)
    if not path.exists():
        raise HTTPException(404, "단지 DB 미생성 — rtms 수집 후 사용 가능")
    cx = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=10)
    cx.row_factory = sqlite3.Row
    return cx

SGG2 = {"11": "서울", "26": "부산", "27": "대구", "28": "인천", "29": "광주", "30": "대전",
        "31": "울산", "36": "세종", "41": "경기", "43": "충북", "44": "충남", "46": "전남",
        "47": "경북", "48": "경남", "50": "제주", "51": "강원", "52": "전북"}

@app.get("/api/apt/search")
def apt_search(q: str = "", region: str = "", kind: str = "", n: int = 30):
    """단지 검색 — 단지명(q)과 지역(region)을 함께 쓸 수 있다.

    (2026-08-08) 지역만으로도 훑을 수 있게 확장. region 은 '서울'(시도) 또는
    '서울 강남구'(시군구) 또는 법정동('역삼동') 어느 쪽이든 받는다.
    """
    q = (q or "").strip()
    region = (region or "").strip()
    if len(q) < 2 and not region:
        return {"rows": []}
    esc = lambda s: s.replace("%", chr(92) + "%").replace("_", chr(92) + "_")
    where, args = [], []
    if kind in ("apt", "offi", "rh", "sh", "land", "nrg"):
        where.append("COALESCE(a.kind,'apt')=?"); args.append(kind)
    if len(q) >= 2:
        where.append("a.name LIKE ? ESCAPE '\\'"); args.append(f"%{esc(q)}%")
    if region:
        # 시도명이면 코드 prefix 로, 그 외엔 법정동/시군구명으로 매칭
        pre = [k for k, v in SGG2.items() if v == region]
        if pre:
            where.append("substr(a.sgg,1,2)=?"); args.append(pre[0])
        else:
            t = region.split()
            if len(t) > 1 and t[0] in SGG2.values():        # '경기 화성시' → 시도 + 나머지
                p2 = [k for k, v in SGG2.items() if v == t[0]]
                where.append("substr(a.sgg,1,2)=?"); args.append(p2[0])
                region = " ".join(t[1:])
            where.append("a.umd LIKE ? ESCAPE '\\'"); args.append(f"%{esc(region)}%")
    args += [q, max(1, min(n, 200))]
    with _aptcx(kind) as cx:
        rows = cx.execute(
            f"""SELECT a.id, a.name, a.umd, a.sgg, a.build_year, COALESCE(a.kind,'apt') AS kind,
                       (SELECT COUNT(*) FROM sale s WHERE s.apt_id=a.id) AS ns,
                       (SELECT MAX(ym)   FROM sale s WHERE s.apt_id=a.id) AS last
                FROM apt a WHERE {' AND '.join(where)}
                ORDER BY (a.name = ?) DESC, ns DESC LIMIT ?""", args).fetchall()
    return {"rows": [dict(r) for r in rows]}

@app.get("/api/apt/regions")
def apt_regions(kind: str = "apt"):
    """단지 DB 에 실제로 있는 지역 목록 — 지역 선택기용 (시도 / 시도+법정동)."""
    with _aptcx(kind) as cx:
        rows = cx.execute(
            "SELECT sgg, umd, COUNT(*) n FROM apt GROUP BY sgg, umd HAVING n>0").fetchall()
        kinds = dict(cx.execute(
            "SELECT COALESCE(kind,'apt'), COUNT(*) FROM apt GROUP BY 1").fetchall())
    sido, dong = {}, {}
    for r in rows:
        sd = SGG2.get(str(r["sgg"])[:2])
        if not sd:
            continue
        sido[sd] = sido.get(sd, 0) + r["n"]
        if r["umd"]:
            k = f"{sd} {r['umd']}"
            dong[k] = dong.get(k, 0) + r["n"]
    return {"kinds": kinds,
            "sido": [{"r": k, "n": v} for k, v in sorted(sido.items(), key=lambda x: -x[1])],
            "dong": [{"r": k, "n": v} for k, v in sorted(dong.items(), key=lambda x: -x[1])[:3000]]}

@app.get("/api/apt/series")
def apt_series(id: int, ar: int = 0, kind: str = "apt"):
    """단지 1개의 매매·전세·월세 월별 시계열. ar=0 이면 거래 최다 면적 자동 선택."""
    with _aptcx(kind) as cx:
        a = cx.execute("SELECT * FROM apt WHERE id=?", (id,)).fetchone()
        if not a:
            raise HTTPException(404, "단지 없음")
        # 면적 목록 — 매매+전세 거래건수 합 기준 정렬
        ars = cx.execute(
            """SELECT ar, SUM(n) AS n FROM (
                   SELECT ar,n FROM sale WHERE apt_id=:i
                   UNION ALL SELECT ar,n FROM jeon WHERE apt_id=:i
                   UNION ALL SELECT ar,n FROM wol  WHERE apt_id=:i)
               GROUP BY ar ORDER BY n DESC""", {"i": id}).fetchall()
        if not ars:
            raise HTTPException(404, "거래 없음")
        if ar <= 0:
            ar = ars[0]["ar"]
        g = lambda sql: [dict(r) for r in cx.execute(sql, (id, ar)).fetchall()]
        out = {
            "apt": dict(a), "ar": ar,
            "ars": [{"ar": r["ar"], "n": r["n"]} for r in ars],
            "sale": g("SELECT ym,n,avg,med,mn,mx FROM sale WHERE apt_id=? AND ar=? ORDER BY ym"),
            "jeon": g("SELECT ym,n,avg,med FROM jeon WHERE apt_id=? AND ar=? ORDER BY ym"),
            "wol":  g("SELECT ym,n,dep,rent FROM wol  WHERE apt_id=? AND ar=? ORDER BY ym"),
        }
    return Response(content=json.dumps(out, ensure_ascii=False),
                    media_type="application/json", headers={"Cache-Control": "max-age=600"})

@app.get("/api/apt/stat")
def apt_stat():
    """단지 DB 적재 현황 — 프론트 안내 문구용."""
    out = {"apt": 0, "sale": 0, "jeon": 0, "wol": 0, "sgg": 0, "ym0": None, "ym1": None}
    for k in ("apt", "offi"):                      # 아파트 파일 + 비아파트 파일 합산
        try:
            with _aptcx(k) as cx:
                q = lambda s: cx.execute(s).fetchone()[0]
                out["apt"] += q("SELECT COUNT(*) FROM apt"); out["sale"] += q("SELECT COUNT(*) FROM sale")
                out["jeon"] += q("SELECT COUNT(*) FROM jeon"); out["wol"] += q("SELECT COUNT(*) FROM wol")
                out["sgg"] = max(out["sgg"], q("SELECT COUNT(DISTINCT sgg) FROM done"))
                a, b = q("SELECT MIN(ym) FROM done"), q("SELECT MAX(ym) FROM done")
                if a and (out["ym0"] is None or a < out["ym0"]): out["ym0"] = a
                if b and (out["ym1"] is None or b > out["ym1"]): out["ym1"] = b
        except HTTPException:
            pass
    return out

# ── 추세 스파크라인 (docx 표의 '추세(1Y)' 열과 동일한 PNG) ──
#   리포트 실행 때 생성된 charts/spark_*.png 를 sync_server.py 가 올린다.
CHARTS = BASE / "data" / "charts"
CHARTS.mkdir(parents=True, exist_ok=True)
app.mount("/charts", StaticFiles(directory=CHARTS), name="charts")

app.mount("/", StaticFiles(directory=BASE / "static", html=True), name="static")
