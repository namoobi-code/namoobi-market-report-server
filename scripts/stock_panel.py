#!/usr/bin/env python3
"""stock_panel.py — 종목 팩터 패널 일별 적재 (2026-09-05 신설)

왜 필요한가
-----------
screener_pool.json 은 매일 **덮어쓰기**라 "3개월 전 이 종목의 리비전·성장·RSI 가
얼마였나"를 복원할 수 없다. 횡단면(cross-sectional) 예측 모델은 과거 시점의 팩터값과
그 이후 실현 수익률을 짝지어야 학습·백테스트가 되므로, point-in-time 패널이 없으면
모델 자체를 만들 수 없다. 가격 파생 팩터(모멘텀·RSI·이평)는 주가로 소급 계산되지만
**컨센서스·리비전·수급은 소급이 원천 불가능**하다 — 오늘 안 쌓으면 영원히 없다.

그래서 이 스크립트는 판단하지 않는다. 그날의 풀을 **그대로 스냅샷**해 둘 뿐이다.
(모델·가중치는 나중에 바뀌어도, 원자료는 한 번 놓치면 복구할 수 없다.)

설계
----
- 키 = (d, mk, c) · d = 풀의 **price_date**(실행일이 아니라 시세 기준일 — 점간 정합성)
- 하루 2회(풀 재빌드 06:52 / 15:52 + earnings_join 패치 후) 실행해도 멱등:
  INSERT OR REPLACE 라 나중 실행(= 패치가 더 채워진 상태)이 이긴다
- 수치 필드는 **가리지 않고 전부** 저장한다. 지금 안 쓰는 팩터가 6개월 뒤 유효할 수
  있고, 그때 과거를 만들어낼 방법은 없다. (실측 2026-09-05: 7,737행 = 하루 ~4MB,
  연 ~1GB. 서버 여유 89GB 대비 무시 가능)
- meta 테이블(코드→이름·섹터)은 별도 — 패널을 숫자만으로 가볍게 유지

사용:  python3 scripts/stock_panel.py            (일별 적재)
       python3 scripts/stock_panel.py --stat     (적재 현황)
       python3 scripts/stock_panel.py --backup   (panel 테이블만 gzip 백업·4개 회전)
"""
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
POOL = BASE / "data" / "db" / "screener_pool.json"
DB = BASE / "data" / "db" / "stock_panel.sqlite"

# 저장 대상 수치 필드 — KR·US 합집합. 한쪽에만 있는 필드는 다른 시장에서 NULL.
# (신규 팩터가 풀에 생기면 여기 추가만 하면 된다 — 기존 행은 NULL 로 남고 무해)
COLS = [
    # 가격·거래
    "px", "cap", "mcap", "chg", "tv", "turn", "vol20", "volx",
    "mom", "r1m", "r3m", "r6m", "r1y", "r1", "r5", "r20",
    "rsi", "v20", "v50", "vs200", "d200", "macd", "bb", "adx", "near52", "hi52", "w52",
    # 밸류
    "per", "pbr", "pb", "psr", "peg", "fper", "fpe", "divy", "payout", "fcfy",
    "upside", "tp", "tphi", "tplo",
    # 퀄리티·성장
    "roe", "opm", "opmch", "opg", "revg", "epsg", "gacc", "oacc", "racc",
    "growth", "g_new", "opg_f", "revg_f", "tob", "qtoby", "qtobq", "oyoy", "syoy",
    "de", "cr",
    # 컨센서스·리비전
    "cr7", "cr30", "cr90", "pr7", "pr30", "pr90",
    "tprv", "tprv90", "tpn", "tpu", "tpd", "tp_rev",
    "rev", "rec", "recn", "nan", "nan1", "scov", "cup", "cdn",
    "eps_rev", "ey0", "ey1", "q0e", "q1e", "rq0", "rq1", "ry0", "ry1", "eq0", "eq1",
    # 실적 서프라이즈
    "spr", "sspr", "sprb", "sprn", "spra",
    # 수급
    "frgn", "inst", "fnb20", "onb20", "fst", "ost", "sr", "sr5", "sr_f",
    "lb", "lbr", "lbs",
    # 합성 점수·플래그
    "z_grw", "z_mom", "z_qly", "z_val", "score",
    "isfin", "oploss", "op3neg", "qup", "yup",
]

SCHEMA = f"""
CREATE TABLE IF NOT EXISTS panel(
  d TEXT NOT NULL, mk TEXT NOT NULL, c TEXT NOT NULL,
  {", ".join(f"{k} REAL" for k in COLS)},
  PRIMARY KEY(d, mk, c)
) WITHOUT ROWID;
CREATE INDEX IF NOT EXISTS ix_panel_c ON panel(mk, c, d);
CREATE TABLE IF NOT EXISTS meta(
  mk TEXT NOT NULL, c TEXT NOT NULL, name TEXT, kn TEXT, sector TEXT,
  first_d TEXT, last_d TEXT, PRIMARY KEY(mk, c)
);
"""


def num(v):
    """숫자만 통과 — bool 은 0/1 로, 문자열('정배열' 등)·None 은 NULL."""
    if isinstance(v, bool):
        return 1.0 if v else 0.0
    if isinstance(v, (int, float)):
        return float(v)
    return None


def main():
    if not POOL.exists():
        raise SystemExit(f"풀 없음: {POOL}")
    pool = json.loads(POOL.read_text(encoding="utf-8"))
    # 시세 기준일 — 실행일이 아니라 풀이 쓴 종가 날짜여야 forward return 과 축이 맞는다
    d = pool.get("price_date") or datetime.now().strftime("%Y-%m-%d")

    DB.parent.mkdir(parents=True, exist_ok=True)
    cx = sqlite3.connect(DB, timeout=120)
    cx.execute("PRAGMA journal_mode=WAL")
    cx.executescript(SCHEMA)

    ins = f"INSERT OR REPLACE INTO panel VALUES({','.join(['?'] * (3 + len(COLS)))})"
    total = 0
    for mk in ("kr", "us"):
        rows, metas = [], []
        for r in pool.get(mk) or []:
            c = r.get("c") or r.get("code") or r.get("sym")
            if not c:
                continue
            rows.append([d, mk, str(c)] + [num(r.get(k)) for k in COLS])
            metas.append((mk, str(c), r.get("name"), r.get("kn"), r.get("sector"), d, d))
        cx.executemany(ins, rows)
        # meta: 이름은 최신으로 갱신하되 first_d(최초 관측일)는 보존 — 상장·편입 시점 추적용
        cx.executemany(
            "INSERT INTO meta(mk,c,name,kn,sector,first_d,last_d) VALUES(?,?,?,?,?,?,?) "
            "ON CONFLICT(mk,c) DO UPDATE SET name=excluded.name, kn=excluded.kn, "
            "sector=excluded.sector, last_d=excluded.last_d", metas)
        total += len(rows)
        print(f"  {mk.upper()}: {len(rows)}행", flush=True)
    cx.commit()

    nd = cx.execute("SELECT COUNT(DISTINCT d) FROM panel").fetchone()[0]
    nr = cx.execute("SELECT COUNT(*) FROM panel").fetchone()[0]
    rng = cx.execute("SELECT MIN(d), MAX(d) FROM panel").fetchone()
    cx.close()
    mb = DB.stat().st_size / 1024 / 1024
    print(f"[panel] {d} 적재 {total}행 · 누적 {nd}일 {nr}행 ({rng[0]}~{rng[1]}) · {mb:.1f}MB", flush=True)


def backup():
    """panel 테이블만 주간 gzip 백업 (2026-09-05).

    px(종가)는 야후에서 언제든 5년치를 다시 받을 수 있으므로 백업하지 않는다.
    반면 panel(컨센·리비전·수급 스냅샷)은 **그날 지나면 어디서도 못 구한다** —
    서버 디스크 사고·코드 버그로 한 번 날아가면 축적한 개월 수만큼 되돌아간다.
    그래서 재현 가능한 것과 불가능한 것을 갈라 후자만 따로 뜬다(용량도 1/40).
    최근 4개만 남기고 회전.
    """
    import gzip
    import shutil as _sh
    bdir = DB.parent / "backup"
    bdir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d")
    tmp = bdir / f"panel_{stamp}.sqlite"
    src = sqlite3.connect(f"file:{DB}?mode=ro", uri=True, timeout=180)
    dst = sqlite3.connect(tmp)
    src.backup(dst)                      # 온라인 백업 — 크론 적재 중이어도 안전
    dst.execute("DROP TABLE IF EXISTS px")   # 재현 가능한 것은 버려 용량 축소
    dst.execute("VACUUM")
    dst.close(); src.close()
    out = bdir / f"panel_{stamp}.sqlite.gz"
    with open(tmp, "rb") as fi, gzip.open(out, "wb", compresslevel=6) as fo:
        _sh.copyfileobj(fi, fo)
    tmp.unlink()
    olds = sorted(bdir.glob("panel_*.sqlite.gz"))
    for f in olds[:-4]:
        f.unlink()
    print(f"[backup] {out.name} · {out.stat().st_size/1024/1024:.1f}MB · 보관 {len(olds[-4:])}개", flush=True)


def stat():
    if not DB.exists():
        print("panel DB 없음"); return
    cx = sqlite3.connect(DB)
    nd, nr = cx.execute("SELECT COUNT(DISTINCT d), COUNT(*) FROM panel").fetchone()
    rng = cx.execute("SELECT MIN(d), MAX(d) FROM panel").fetchone()
    print(f"누적 {nd}일 · {nr}행 · {rng[0]}~{rng[1]} · {DB.stat().st_size/1024/1024:.1f}MB")
    for row in cx.execute("SELECT d, mk, COUNT(*) FROM panel GROUP BY d, mk ORDER BY d DESC LIMIT 10"):
        print("  ", row)
    cx.close()


if __name__ == "__main__":
    if "--stat" in sys.argv:
        stat()
    elif "--backup" in sys.argv:
        backup()
    else:
        main()
