import json, time, urllib.request, os, re, sqlite3
from pathlib import Path
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
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

@app.get("/api/domains")
def domains():
    out = []
    for p in sorted(DB.glob("*.json")):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            out.append({"name": p.stem, "as_of": d.get("as_of",""), "marker": d.get("marker","")})
        except Exception:
            pass
    return out

@app.get("/api/db/{name}")
def get_db(name: str):
    if not re.fullmatch(r"[a-zA-Z0-9_]+", name):
        raise HTTPException(400, "bad name")
    return load(name)

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

@app.get("/api/policyrates")
def policyrates():
    """주요 6개국 정책금리 월별 시계열"""
    p = RPTD / "policyrates_monthly.json"
    if not p.exists():
        raise HTTPException(404, "policyrates 없음")
    return json.loads(p.read_text(encoding="utf-8"))

@app.get("/api/bundle")
def bundle():
    """db/ 39개 전체를 한 번에 — 대시보드가 라운드트립 1회로 모두 로드"""
    out = {}
    for p in DB.glob("*.json"):
        try:
            out[p.stem] = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    # 폴링 시계열도 함께
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

# ── 추세 스파크라인 (docx 표의 '추세(1Y)' 열과 동일한 PNG) ──
#   리포트 실행 때 생성된 charts/spark_*.png 를 sync_server.py 가 올린다.
CHARTS = BASE / "data" / "charts"
CHARTS.mkdir(parents=True, exist_ok=True)
app.mount("/charts", StaticFiles(directory=CHARTS), name="charts")

app.mount("/", StaticFiles(directory=BASE / "static", html=True), name="static")
