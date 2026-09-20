#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""hstart.py — 주택 착공실적 월별 (국토교통부 주택건설실적통계, KOSIS DT_MLTM_5387)

용도: '부동산시황' 탭 하단 '월평균 착공 실적' — 한경BUSINESS(아기곰, 2026-09-16) 그래픽 재현.
      기준기간(기본 2012~2021) 월평균 대비 연도별 월평균 착공 물량과 감소율을 아파트/아파트외로 본다.

실측 검증(2026-09-20, 전국):
  아파트   월평균  2012~21 33,204 · 2022 25,146 · 2023 17,074 · 2024 22,469 · 2025 20,122 · 2026(1~7월) 17,326
  아파트외 월평균  2012~21 12,763 · 2022  7,024 · 2023  3,448 · 2024  2,817 · 2025  2,601 · 2026(1~7월)  2,443
  → 기사 수치와 정확히 일치. 아파트외 = 계(다가구 **동수** 기준) − 아파트 (가구수 기준으로 빼면 안 맞는다: 19,734).

표 구조: C1 지역 23개(총계·수도권소계·서울·인천·경기·지방소계·기타광역시·전남광주·부산·대구·광주·대전·울산·
        기타지방·세종·강원·충북·충남·전북·전남·경북·경남·제주) × C3/C4 유형
        (계(동수)·계(가구수)·단독·다가구(동수/가구수)·다세대·연립·아파트). 2011.01~, 단위 호.
        40,000셀 제한이 있어 **1년씩** 나눠 받는다(objL4 를 좁혀도 셀 수는 전체 표로 세는 듯 — 실측 err 31).
        KOSIS 갱신은 매월 말(전월분) — 기본 실행은 최근 2년만 받아 이전 파일과 병합.

산출: data/db/hstart.json
  {asof, src, note, t:[YYYYMM], regions:[...], series:{region:{key:[값|null]}}}
  key: all_b(계·동수) all_h(계·가구수) apt(아파트) non(아파트외=all_b-apt) det(단독) mh_b(다가구 동수) mh_h(다가구 가구수)
       ms(다세대) row(연립)

사용: hstart.py [--full]      cron: 55 7 * * *
"""
import json, socket, sys, time, urllib.request
from datetime import datetime
from pathlib import Path

socket.setdefaulttimeout(90)
BASE = Path(__file__).resolve().parent.parent
DB   = BASE / "data" / "db"
OUT  = DB / "hstart.json"
FULL = "--full" in sys.argv
NOW  = datetime.now()
API  = "https://kosis.kr/openapi/Param/statisticsParameterData.do"
TBL  = "DT_MLTM_5387"
KEYMAP = {("계(다가구동수기준)", "계(다가구동수기준)"): "all_b", ("계(다가구가구수기준)", "계(다가구가구수기준)"): "all_h",
          ("단독", "단독"): "det", ("다가구", "동수"): "mh_b", ("다가구", "가구수"): "mh_h",
          ("다세대", "다세대"): "ms", ("연립", "연립"): "row", ("아파트", "아파트"): "apt"}
REG_ORDER = ["총계", "수도권소계", "지방소계", "서울", "인천", "경기", "부산", "대구", "광주", "대전", "울산", "세종",
             "강원", "충북", "충남", "전북", "전남", "전남광주", "경북", "경남", "제주", "기타광역시", "기타지방"]
REG_NM = {"총계": "전국", "수도권소계": "수도권", "지방소계": "지방"}


def _key():
    for p in [BASE / "keys" / "kosis.txt", Path("D:/claudeCowork/SECURITY/kosis.kr.txt")] + \
             sorted(Path("/sessions").glob("*/mnt/claudeCowork/SECURITY/kosis.kr.txt")):
        try:
            k = Path(p).read_text(encoding="utf-8").strip()
            if k:
                return k
        except Exception:
            pass
    raise SystemExit("KOSIS 키 없음 — keys/kosis.txt")


KEY = _key()


C4 = "13102766969D."
GROUPS = [C4 + "0001+" + C4 + "0002+" + C4 + "0008",                       # 계(동수)·계(가구수)·아파트
          C4 + "0003+" + C4 + "0004+" + C4 + "0005+" + C4 + "0006+" + C4 + "0007"]   # 단독·다가구동·다가구가구·다세대·연립


def fetch_year(y):
    """1년 × 유형 그룹 2 × 반기 2 = 4회 — objL4=ALL 이면 40,000셀 초과(실측)."""
    out = []
    for g in GROUPS:
        for a, b in (("01", "06"), ("07", "12")):     # 반기 — 1년 단위는 그룹에 따라 간헐적으로 err 31 (실측)
            out += _fetch(f"{API}?method=getList&apiKey={KEY}&orgId=116&tblId={TBL}&objL1=ALL&objL2=ALL&objL3=ALL"
                          f"&objL4={g}&itmId=ALL&prdSe=M&startPrdDe={y}{a}&endPrdDe={y}{b}&format=json&jsonVD=Y", y)
            time.sleep(0.3)
    return out


def _fetch(u, y):
    for k in range(3):
        try:
            d = json.load(urllib.request.urlopen(u, timeout=90))
            if isinstance(d, dict):
                if d.get("err") == "30":       # 데이터 없음
                    return []
                raise RuntimeError(d.get("errMsg"))
            return d
        except Exception as e:
            if k == 2:
                print(f"    ⚠ {y} 실패: {e}")
                return []
            time.sleep(3)
    return []


def main():
    y0 = 2011 if FULL else NOW.year - 2
    print(f"hstart: {y0}~{NOW.year} {'(전체)' if FULL else '(최근 2년 갱신)'}")
    data = {}                                   # {region: {key: {ym: v}}}
    for y in range(y0, NOW.year + 1):
        rows = fetch_year(y)
        n = 0
        for r in rows:
            k = KEYMAP.get((r.get("C3_NM"), r.get("C4_NM")))
            if not k:
                continue
            reg = REG_NM.get(r["C1_NM"], r["C1_NM"])
            try:
                data.setdefault(reg, {}).setdefault(k, {})[r["PRD_DE"]] = int(float(r["DT"]))
                n += 1
            except Exception:
                pass
        print(f"  {y}: {len(rows)}행 → {n}셀")
        time.sleep(0.3)
    if not data:
        raise SystemExit("✗ 수집 0")

    old = {}
    if OUT.exists() and not FULL:
        try:
            old = json.loads(OUT.read_text(encoding="utf-8"))
        except Exception:
            old = {}
    ot = old.get("t") or []
    merged = {}
    for reg, ks in (old.get("series") or {}).items():
        for k, arr in ks.items():
            merged.setdefault(reg, {})[k] = {ot[i]: arr[i] for i in range(min(len(ot), len(arr))) if arr[i] is not None}
    for reg, ks in data.items():
        for k, mp in ks.items():
            merged.setdefault(reg, {}).setdefault(k, {}).update(mp)
    for reg, ks in merged.items():             # 아파트외 = 계(동수) − 아파트
        if "all_b" in ks and "apt" in ks:
            ks["non"] = {m: ks["all_b"][m] - ks["apt"][m] for m in ks["all_b"] if m in ks["apt"]}

    ts = sorted({m for ks in merged.values() for mp in ks.values() for m in mp})
    regs = [REG_NM.get(r, r) for r in REG_ORDER if REG_NM.get(r, r) in merged] + \
           sorted(r for r in merged if r not in {REG_NM.get(x, x) for x in REG_ORDER})
    out = {
        "asof": NOW.strftime("%Y-%m-%d %H:%M"),
        "src": "국토교통부 주택건설실적통계 · 주택유형별 착공실적(월계) — KOSIS DT_MLTM_5387",
        "note": "단위 호. 아파트외 = 계(다가구 동수기준) − 아파트 (한경BUSINESS 그래픽과 동일 정의). 최근월은 잠정치.",
        "t": ts,
        "regions": regs,
        "series": {reg: {k: [merged[reg][k].get(t) for t in ts] for k in merged[reg]} for reg in regs},
    }
    DB.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    a = merged["전국"]["apt"]
    print(f"  → {OUT} ({OUT.stat().st_size // 1024}KB) · {ts[0]}~{ts[-1]} · 지역 {len(regs)} · 전국 아파트 최근 {ts[-1]}={a.get(ts[-1])}")


if __name__ == "__main__":
    main()
