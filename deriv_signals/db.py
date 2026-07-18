# -*- coding: utf-8 -*-
"""SQLite 스키마 및 접속 헬퍼.

마운트/네트워크 파일시스템은 SQLite 락을 지원하지 않아 'disk I/O error'가 난다.
connect()는 게시 경로(PUBLISH_DB)에서 먼저 시도하고, 실패하면 로컬 임시 디스크로
자동 폴백한 뒤 publish_db()에서 완성된 DB 파일을 사용자 폴더로 복사한다.
"""
import sqlite3
import shutil
import tempfile
import gzip
from pathlib import Path
from datetime import datetime, timezone
from config import PUBLISH_DB, INSTRUMENTS

_WORK = {"path": PUBLISH_DB, "needs_publish": False}


def active_db():
    return _WORK["path"]


SCHEMA = """
CREATE TABLE IF NOT EXISTS instruments (
    id TEXT PRIMARY KEY, name TEXT, region TEXT,
    spot TEXT, future TEXT, option TEXT, cot TEXT, proxy_spot INTEGER
);
CREATE TABLE IF NOT EXISTS prices_daily (
    id TEXT, date TEXT, spot_close REAL, future_close REAL, vix_close REAL,
    PRIMARY KEY (id, date)
);
CREATE TABLE IF NOT EXISTS positioning_weekly (
    id TEXT, report_date TEXT, open_interest REAL, oi_change REAL,
    lev_net REAL, asset_mgr_net REAL, dealer_net REAL,
    PRIMARY KEY (id, report_date)
);
CREATE TABLE IF NOT EXISTS options_daily (
    id TEXT, date TEXT, expiry_used TEXT, dte INTEGER,
    pcr_oi REAL, pcr_vol REAL, iv_atm REAL, iv_skew_25d REAL, delta_imbalance REAL, gex REAL,
    PRIMARY KEY (id, date)
);
CREATE TABLE IF NOT EXISTS indicators_daily (
    id TEXT, date TEXT, spot_close REAL, spot_ret REAL, fut_ret REAL,
    basis_bp REAL, oi_chg_w REAL, lev_net REAL, asset_mgr_net REAL,
    pcr_oi REAL, pcr_vol REAL, iv_skew_25d REAL, delta_imbalance REAL, gex REAL,
    vkospi REAL,
    fwd_ret_1d REAL, fwd_ret_3d REAL, fwd_ret_5d REAL,
    PRIMARY KEY (id, date)
);
CREATE TABLE IF NOT EXISTS zscores_daily (
    id TEXT, date TEXT,
    z_basis_bp REAL, z_oi_chg_w REAL, z_lev_net REAL, z_asset_mgr_net REAL,
    z_pcr_oi REAL, z_pcr_vol REAL, z_iv_skew_25d REAL, z_delta_imbalance REAL, z_gex REAL,
    z_vkospi REAL,
    PRIMARY KEY (id, date)
);
CREATE TABLE IF NOT EXISTS signal_events (
    id TEXT, date TEXT, indicator TEXT, z_value REAL, direction INTEGER,
    fwd_ret_1d REAL, fwd_ret_3d REAL, fwd_ret_5d REAL,
    PRIMARY KEY (id, date, indicator)
);
CREATE TABLE IF NOT EXISTS validation_summary (
    id TEXT, indicator TEXT, direction INTEGER, n_events INTEGER,
    mean_fwd_1d REAL, hit_1d REAL, mean_fwd_3d REAL, hit_3d REAL,
    mean_fwd_5d REAL, hit_5d REAL, ic_1d REAL, ic_3d REAL, ic_5d REAL,
    PRIMARY KEY (id, indicator, direction)
);
CREATE TABLE IF NOT EXISTS kr_derivatives_daily (
    id TEXT, date TEXT,
    basis_bp REAL, oi REAL,
    pcr_oi REAL, pcr_vol REAL, iv_skew_25d REAL, gex REAL,
    vkospi REAL,          -- 1차: KRX OPEN API 코스피200 변동성지수
    disparity REAL,       -- 2차: data.krx 괴리율(%) = 시장베이시스 - 이론베이시스
    iv_krx REAL,          -- 2차: data.krx 공식 내재변동성
    pcr_krx REAL,         -- 2차: data.krx 공식 P/C Ratio
    PRIMARY KEY (id, date)
);
CREATE TABLE IF NOT EXISTS update_log (
    run_ts TEXT, step TEXT, rows INTEGER, note TEXT
);
"""


def _open(path):
    con = sqlite3.connect(path)
    con.execute("PRAGMA journal_mode=DELETE;")   # 단일 파일 → 복사 시 항상 정합
    con.execute("CREATE TABLE IF NOT EXISTS _probe(a)")
    con.execute("DROP TABLE _probe")
    con.commit()
    return con


def _dump_path():
    # 마운트(D:)는 바이너리 sqlite 쓰기 시 간헐 손상 → 텍스트 gzip SQL 덤프를 '영구 누적본'으로 사용.
    return str(PUBLISH_DB) + ".sql.gz"


def _integrity_ok(path):
    try:
        c = sqlite3.connect(str(path)); r = c.execute("PRAGMA integrity_check").fetchone(); c.close()
        return bool(r) and r[0] == "ok"
    except Exception:
        return False


def _rebuild_from_dump(local):
    dp = _dump_path()
    if not Path(dp).exists():
        return False
    try:
        with gzip.open(dp, "rt", encoding="utf-8") as fh:
            sql = fh.read()
        if not sql.strip():
            return False
        try: Path(local).unlink()
        except Exception: pass
        con = sqlite3.connect(str(local)); con.executescript(sql); con.commit(); con.close()
        return True
    except Exception:
        return False


def _seed_local():
    d = Path(tempfile.gettempdir()) / "deriv_signals"
    d.mkdir(parents=True, exist_ok=True)
    local = d / "deriv_signals.db"
    if local.exists():
        return local
    seeded = False
    # 1) 마운트 바이너리 DB 가 '온전하면' 복사(빠름)
    if Path(PUBLISH_DB).exists() and _integrity_ok(PUBLISH_DB):
        try:
            shutil.copy(PUBLISH_DB, local); seeded = _integrity_ok(local)
        except Exception:
            seeded = False
    # 2) 부재/손상이면 gzip 덤프로 재구성(마운트 바이너리 손상에도 누적 이력 보존)
    if not seeded:
        try: Path(local).unlink()
        except Exception: pass
        _rebuild_from_dump(local)
    return local


def connect():
    # (안정화) 항상 로컬 작업 DB 사용 — 마운트 sqlite 직접조작 금지(disk I/O·손상 회피).
    local = _seed_local()
    _WORK["path"] = local
    _WORK["needs_publish"] = True
    return _open(local)


def publish_db():
    src = _WORK["path"]
    if Path(src) == Path(PUBLISH_DB):
        return str(PUBLISH_DB)
    # 1) 바이너리 복사(뷰어·호환용, 손상돼도 무방 — 덤프가 실질 누적본)
    try:
        shutil.copy(src, PUBLISH_DB)
    except Exception:
        pass
    # 2) gzip SQL 덤프(텍스트 → 마운트 쓰기 안정) = 실질 영구 누적본
    try:
        con = sqlite3.connect(str(src))
        tmp = str(_dump_path()) + ".tmp"
        with gzip.open(tmp, "wt", encoding="utf-8") as fh:
            for line in con.iterdump():
                fh.write(line + "\n")
        con.close()
        try:
            import os as _os; _os.replace(tmp, _dump_path())   # 원자적 교체
        except Exception:
            shutil.copy(tmp, _dump_path())
    except Exception as e:
        return f"덤프 실패: {e}"
    return str(PUBLISH_DB)


MIGRATIONS = [
    ("options_daily", "gex"),          # 구버전 DB(GEX 도입 이전)에 누락 → analyze KeyError 방지
    ("kr_derivatives_daily", "gex"),
    ("kr_derivatives_daily", "vkospi"),
    ("kr_derivatives_daily", "disparity"),
    ("kr_derivatives_daily", "iv_krx"),
    ("kr_derivatives_daily", "pcr_krx"),
    ("indicators_daily", "gex"),
    ("indicators_daily", "vkospi"),
    ("zscores_daily", "z_gex"),
    ("zscores_daily", "z_vkospi"),
]


def migrate(con):
    """기존 DB에 신규 컬럼 추가(있으면 무시) — 재백필 없이도 스키마가 따라온다."""
    for tbl, col in MIGRATIONS:
        try:
            con.execute(f"ALTER TABLE {tbl} ADD COLUMN {col} REAL")
        except Exception:
            pass          # 이미 존재
    con.commit()


def init_db():
    con = connect()
    con.executescript(SCHEMA)
    migrate(con)
    for r in INSTRUMENTS:
        con.execute(
            """INSERT INTO instruments(id,name,region,spot,future,option,cot,proxy_spot)
               VALUES(?,?,?,?,?,?,?,?)
               ON CONFLICT(id) DO UPDATE SET
                 name=excluded.name, region=excluded.region, spot=excluded.spot,
                 future=excluded.future, option=excluded.option, cot=excluded.cot,
                 proxy_spot=excluded.proxy_spot""",
            (r["id"], r["name"], r["region"], r["spot"], r["future"],
             r["option"], r["cot"], int(r["proxy_spot"])),
        )
    con.commit()
    con.close()


def log(con, step, rows, note=""):
    con.execute(
        "INSERT INTO update_log(run_ts,step,rows,note) VALUES(?,?,?,?)",
        (datetime.now(timezone.utc).isoformat(timespec="seconds"), step, int(rows), note),
    )
    con.commit()


if __name__ == "__main__":
    init_db()
    print("initialized:", active_db())
