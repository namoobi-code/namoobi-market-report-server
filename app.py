import json, os, re, sqlite3
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

@app.get("/api/health")
def health():
    return {"ok": True,
            "db_files": len(list(DB.glob("*.json"))),
            "reports": len(list(RPT.glob("*.docx"))),
            "now": datetime.now().isoformat(timespec="seconds")}

app.mount("/", StaticFiles(directory=BASE / "static", html=True), name="static")
