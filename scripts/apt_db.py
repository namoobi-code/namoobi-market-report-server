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
    cx = sqlite3.connect(DB, timeout=60)
    cx.executescript(SCHEMA)
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


def _apt_id(cx, sgg, r, cache):
    """단지 마스터 upsert → id. cache 는 실행 중 중복 조회 방지용 dict."""
    key = (sgg, r.get("umdNm", ""), r.get("aptNm", ""), r.get("jibun", ""))
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
        "INSERT INTO apt(sgg,umd,name,jibun,build_year,apt_seq,road) VALUES(?,?,?,?,?,?,?) "
        "ON CONFLICT(sgg,umd,name,jibun) DO UPDATE SET "
        "  build_year=COALESCE(apt.build_year,excluded.build_year),"
        "  apt_seq   =COALESCE(apt.apt_seq,   excluded.apt_seq),"
        "  road      =COALESCE(apt.road,      excluded.road)",
        (*key, by, r.get("aptSeq") or None, r.get("roadnm") or None))
    aid = cx.execute("SELECT id FROM apt WHERE sgg=? AND umd=? AND name=? AND jibun=?",
                     key).fetchone()[0]
    cache[key] = aid
    return aid


def ingest_sale(cx, sgg, ym, rows, cache):
    """매매 원시행 → 단지·면적별 월간 집계 upsert. 해제거래(cdealType='O') 제외."""
    buck = {}
    for r in rows:
        if (r.get("cdealType") or "") == "O":
            continue
        px = _f(r.get("dealAmount"))
        ar = _f(r.get("excluUseAr"))
        if not px or not ar:
            continue
        aid = _apt_id(cx, sgg, r, cache)
        if aid is None:
            continue
        buck.setdefault((aid, round(ar)), []).append(px / 10000)      # 만원 → 억
    cx.executemany(
        "INSERT OR REPLACE INTO sale(apt_id,ym,ar,n,avg,med,mn,mx) VALUES(?,?,?,?,?,?,?,?)",
        [(aid, ym, ar, len(v), round(sum(v) / len(v), 3), round(_med(v), 3),
          round(min(v), 3), round(max(v), 3)) for (aid, ar), v in buck.items()])
    cx.execute("INSERT OR REPLACE INTO done(sgg,ym,kind) VALUES(?,?,'sale')", (sgg, ym))
    return len(buck)


def ingest_rent(cx, sgg, ym, rows, cache):
    """전월세 원시행 → 전세(월세0)·월세(월세>0) 분리 집계 upsert."""
    jb, wb = {}, {}
    for r in rows:
        dep = _f(r.get("deposit"))
        mr = _f(r.get("monthlyRent")) or 0
        ar = _f(r.get("excluUseAr"))
        if dep is None or not ar:
            continue
        aid = _apt_id(cx, sgg, r, cache)
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
    cx.execute("INSERT OR REPLACE INTO done(sgg,ym,kind) VALUES(?,?,'rent')", (sgg, ym))
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
