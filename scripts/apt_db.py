#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""apt_db.py — 아파트 단지별 실거래 시계열 DB (2026-08-08 신설).

설계 요지
---------
rtms.py 가 지역-월 집계를 위해 **이미 받아온 원시 행**을 그대로 재활용해
단지 단위로도 집계한다 → **추가 API 호출 0회**.

RTMS 응답에 들어있는 단지 식별 필드(실측 2026-08-08):
  매매(AptTrade) : aptNm, umdNm, jibun, excluUseAr, floor, buildYear, dealAmount, cdealType
  전월세(AptRent): aptNm, umdNm, jibun, excluUseAr, floor, buildYear, deposit, monthlyRent,
                   aptSeq(단지 고유코드 "11680-3623"), roadnm
  → 매매엔 aptSeq 가 없으므로 조인키는 (sgg, umd, name, jibun) 4종 복합키.

스키마
------
  apt   단지 마스터 (id, sgg, umd, name, jibun, build_year, apt_seq, road)
  sale  매매   월별 집계 (apt_id, ym, ar) → n, avg, med, mn, mx
  jeon  전세   월별 집계 (apt_id, ym, ar) → n, avg, med          (월세 0 인 계약)
  wol   월세   월별 집계 (apt_id, ym, ar) → n, dep, rent          (월세 > 0)
  done  수집완료 표식 (sgg, ym) — rtms.py 의 --extend 스킵 판정에 사용

  ar = round(전용면적 m²) 정수. 0 은 쓰지 않음(면적 혼합 평균은 무의미).
       프론트는 거래 최다 면적을 기본 선택하고 드롭다운으로 전환한다.
"""
import sqlite3
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DB = BASE / "data" / "db" / "apt.sqlite"

SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS apt(
  id INTEGER PRIMARY KEY,
  sgg TEXT NOT NULL, umd TEXT NOT NULL, name TEXT NOT NULL, jibun TEXT NOT NULL,
  build_year INTEGER, apt_seq TEXT, road TEXT,
  UNIQUE(sgg, umd, name, jibun)
);
CREATE INDEX IF NOT EXISTS ix_apt_name ON apt(name);
CREATE INDEX IF NOT EXISTS ix_apt_sgg  ON apt(sgg);

CREATE TABLE IF NOT EXISTS sale(
  apt_id INTEGER NOT NULL, ym TEXT NOT NULL, ar INTEGER NOT NULL,
  n INTEGER, avg REAL, med REAL, mn REAL, mx REAL,
  PRIMARY KEY(apt_id, ym, ar)
) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS jeon(
  apt_id INTEGER NOT NULL, ym TEXT NOT NULL, ar INTEGER NOT NULL,
  n INTEGER, avg REAL, med REAL,
  PRIMARY KEY(apt_id, ym, ar)
) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS wol(
  apt_id INTEGER NOT NULL, ym TEXT NOT NULL, ar INTEGER NOT NULL,
  n INTEGER, dep REAL, rent REAL,
  PRIMARY KEY(apt_id, ym, ar)
) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS done(
  sgg TEXT NOT NULL, ym TEXT NOT NULL, kind TEXT NOT NULL,
  PRIMARY KEY(sgg, ym, kind)
) WITHOUT ROWID;
"""


def connect():
    DB.parent.mkdir(parents=True, exist_ok=True)
    # (2026-08-08) 아파트 백필과 비아파트 수집이 이 DB 를 동시에 쓴다.
    # SQLite 는 쓰기가 1개만 가능하므로 넉넉히 기다리게 하고, 각 수집기는 월 단위로 커밋해
    # 잠금 구간을 짧게 유지한다(지역 단위로 커밋하면 7분씩 잡혀 상대가 타임아웃난다).
    cx = sqlite3.connect(DB, timeout=180)
    cx.execute("PRAGMA busy_timeout=180000")
    cx.executescript(SCHEMA)
    # (2026-08-08) 오피스텔·연립다세대까지 담기 위해 kind 컬럼 추가(기존 행은 'apt').
    # 같은 (sgg,umd,name,jibun) 이 두 유형으로 동시에 존재하는 경우는 없어 UNIQUE 는 그대로 둔다.
    cols = {r[1] for r in cx.execute("PRAGMA table_info(apt)")}
    if "kind" not in cols:
        cx.execute("ALTER TABLE apt ADD COLUMN kind TEXT DEFAULT 'apt'")
        cx.execute("UPDATE apt SET kind='apt' WHERE kind IS NULL")
        cx.execute("CREATE INDEX IF NOT EXISTS ix_apt_kind ON apt(kind)")
        # done 표식도 유형별로 바뀌었다('sale'→'apt_sale'). 그대로 두면 이미 끝낸
        # 수만 개월을 처음부터 다시 훑게 되므로 반드시 함께 이관한다.
        cx.execute("UPDATE done SET kind='apt_sale' WHERE kind='sale'")
        cx.execute("UPDATE done SET kind='apt_rent' WHERE kind='rent'")
        cx.commit()
    return cx


def _f(s):
    try:
        return float(str(s).replace(",", ""))
    except Exception:
        return None


def _med(xs):
    xs = sorted(xs)
    n = len(xs)
    return xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2


def _name_of(r, kind, name_field):
    """유형별 '무엇을 하나의 단위로 볼 것인가' — 국토부가 주는 식별정보가 제각각이다(실측 2026-08-08).

      아파트/오피스텔/연립다세대 : 건물명 그대로 (지번 마스킹 0%)
      상업업무용                 : 건물명 없음 → '법정동 지번' (지번 38% 마스킹, 나머지만)
      단독다가구·토지            : 건물명 없음 + 지번 100% 마스킹 → **법정동 단위**까지만
    """
    if kind in ("sh", "land"):
        return r.get("umdNm", "") or ""
    if kind == "nrg":
        jb = (r.get("jibun") or "").strip()
        if not jb or "*" in jb:
            return ""                                 # 마스킹 건은 개별 식별 불가 → 버림
        return f"{r.get('umdNm','')} {jb}".strip()
    return r.get(name_field, "") or r.get("aptNm", "")


def _apt_id(cx, sgg, r, cache, kind="apt", name_field="aptNm"):
    """단지(또는 그에 준하는 단위) 마스터 upsert → id."""
    nm = _name_of(r, kind, name_field)
    # 단독·토지는 법정동이 곧 단위라 지번을 키에서 뺀다(안 그러면 마스킹 지번마다 새 행이 생긴다)
    jb = "" if kind in ("sh", "land", "nrg") else (r.get("jibun", "") or "")
    key = (sgg, r.get("umdNm", ""), nm, jb)
    if key in cache:
        return cache[key]
    if not key[2]:
        return None                                  # 단지명 없는 행은 버림
    by = None
    try:
        by = int(r.get("buildYear") or 0) or None
    except Exception:
        pass
    cx.execute(
        "INSERT INTO apt(sgg,umd,name,jibun,build_year,apt_seq,road,kind) VALUES(?,?,?,?,?,?,?,?) "
        "ON CONFLICT(sgg,umd,name,jibun) DO UPDATE SET "
        "  build_year=COALESCE(apt.build_year,excluded.build_year),"
        "  apt_seq   =COALESCE(apt.apt_seq,   excluded.apt_seq),"
        "  road      =COALESCE(apt.road,      excluded.road),"
        "  kind      =COALESCE(apt.kind,      excluded.kind)",
        (*key, by, r.get("aptSeq") or None, r.get("roadnm") or None, kind))
    aid = cx.execute("SELECT id FROM apt WHERE sgg=? AND umd=? AND name=? AND jibun=?",
                     key).fetchone()[0]
    cache[key] = aid
    return aid


def ingest_sale(cx, sgg, ym, rows, cache, kind="apt", name_field="aptNm"):
    """매매 원시행 → 단지·면적별 월간 집계 upsert. 해제거래(cdealType='O') 제외."""
    buck = {}
    for r in rows:
        if (r.get("cdealType") or "") == "O":
            continue
        px = _f(r.get("dealAmount"))
        # 유형마다 면적 필드가 다르다. 토지·단독은 전용면적이 없어 0(=면적 무관)으로 담는다.
        ar = (_f(r.get("excluUseAr")) or _f(r.get("totalFloorAr"))
              or _f(r.get("dealArea")) or _f(r.get("buildingAr")))
        if not px:
            continue
        ar = ar or 0
        aid = _apt_id(cx, sgg, r, cache, kind, name_field)
        if aid is None:
            continue
        buck.setdefault((aid, round(ar)), []).append(px / 10000)      # 만원 → 억 (ar=0 은 면적 무관)
    cx.executemany(
        "INSERT OR REPLACE INTO sale(apt_id,ym,ar,n,avg,med,mn,mx) VALUES(?,?,?,?,?,?,?,?)",
        [(aid, ym, ar, len(v), round(sum(v) / len(v), 3), round(_med(v), 3),
          round(min(v), 3), round(max(v), 3)) for (aid, ar), v in buck.items()])
    cx.execute("INSERT OR REPLACE INTO done(sgg,ym,kind) VALUES(?,?,?)", (sgg, ym, kind + "_sale"))
    return len(buck)


def ingest_rent(cx, sgg, ym, rows, cache, kind="apt", name_field="aptNm"):
    """전월세 원시행 → 전세(월세0)·월세(월세>0) 분리 집계 upsert."""
    jb, wb = {}, {}
    for r in rows:
        dep = _f(r.get("deposit"))
        mr = _f(r.get("monthlyRent")) or 0
        ar = _f(r.get("excluUseAr"))
        if dep is None or not ar:
            continue
        aid = _apt_id(cx, sgg, r, cache, kind, name_field)
        if aid is None:
            continue
        k = (aid, round(ar))
        (jb if mr == 0 else wb).setdefault(k, []).append(
            dep / 10000 if mr == 0 else (dep / 10000, mr))
    cx.executemany(
        "INSERT OR REPLACE INTO jeon(apt_id,ym,ar,n,avg,med) VALUES(?,?,?,?,?,?)",
        [(aid, ym, ar, len(v), round(sum(v) / len(v), 3), round(_med(v), 3))
         for (aid, ar), v in jb.items()])
    cx.executemany(
        "INSERT OR REPLACE INTO wol(apt_id,ym,ar,n,dep,rent) VALUES(?,?,?,?,?,?)",
        [(aid, ym, ar, len(v),
          round(sum(d for d, _ in v) / len(v), 3),
          round(sum(m for _, m in v) / len(v), 1)) for (aid, ar), v in wb.items()])
    cx.execute("INSERT OR REPLACE INTO done(sgg,ym,kind) VALUES(?,?,?)", (sgg, ym, kind + "_rent"))
    return len(jb) + len(wb)


def has(cx, sgg, ym, kind):
    return cx.execute("SELECT 1 FROM done WHERE sgg=? AND ym=? AND kind=?",
                      (sgg, ym, kind)).fetchone() is not None


def stats(cx):
    q = lambda s: cx.execute(s).fetchone()[0]
    return {"apt": q("SELECT COUNT(*) FROM apt"), "sale": q("SELECT COUNT(*) FROM sale"),
            "jeon": q("SELECT COUNT(*) FROM jeon"), "wol": q("SELECT COUNT(*) FROM wol"),
            "done": q("SELECT COUNT(*) FROM done")}


if __name__ == "__main__":
    with connect() as cx:
        print("[apt_db]", stats(cx), "→", DB)
