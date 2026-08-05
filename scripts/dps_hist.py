#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dps_hist.py — 주당배당금(DPS) 5개년 이력 + 연속 증가 연수 (2026-08-06 신설).

'매년 배당을 늘려온 회사' 판정의 정공법. 네이버 연간 재무는 확정 3개년뿐이라
DART 배당공시(alotMatter — 사업보고서 '배당에 관한 사항')를 쓴다:
  bsns_year=Y 한 콜에 당기/전기/전전기 3개년 → 2콜(최근·-2년)로 5개년 확보.
판정: dinc = 최신 확정연도에서 거꾸로 '전년 대비 증가(>)'가 이어진 횟수 (3이면 3년 연속 증가)
산출: data/db/dps_hist.json {asof, d:{code:{inc,y:{연도:원}}}}
사용: dps_hist.py [--backfill]  (기본=corp맵 캐시 사용 · 주 1회 cron 일 08:00)
"""
import io, json, re, sys, time, urllib.request, zipfile
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "data" / "db" / "dps_hist.json"
CORPMAP = BASE / "data" / "watch" / "dart_corp_map.json"
KEY = (BASE / "keys" / "opendart.txt").read_text().strip()

def get(u, timeout=25):
    return urllib.request.urlopen(u, timeout=timeout).read()

def corp_map():
    """상장 stock_code(6) → DART corp_code — 주 1회 캐시."""
    try:
        m = json.loads(CORPMAP.read_text())
        if (datetime.now() - datetime.fromisoformat(m["at"])).days < 7:
            return m["map"]
    except Exception:
        pass
    raw = get(f"https://opendart.fss.or.kr/api/corpCode.xml?crtfc_key={KEY}")
    z = zipfile.ZipFile(io.BytesIO(raw))
    root = ET.fromstring(z.read(z.namelist()[0]))
    mp = {}
    for e in root.iter("list"):
        sc = (e.findtext("stock_code") or "").strip()
        if len(sc) == 6:
            mp[sc] = e.findtext("corp_code")
    CORPMAP.parent.mkdir(parents=True, exist_ok=True)
    CORPMAP.write_text(json.dumps({"at": datetime.now().isoformat(), "map": mp}))
    return mp

def num(s):
    s = str(s or "").replace(",", "").strip()
    try:
        return float(s)
    except ValueError:
        return None

def dps_years(corp, years):
    """alotMatter — 보통주 '주당 현금배당금(원)' {연도:원}. bsns_year Y 콜 = Y·Y-1·Y-2."""
    out = {}
    for y in years:
        try:
            j = json.loads(get(f"https://opendart.fss.or.kr/api/alotMatter.json?crtfc_key={KEY}"
                               f"&corp_code={corp}&bsns_year={y}&reprt_code=11011"))
            if j.get("status") != "000":
                continue
            for r in j.get("list") or []:
                if "주당 현금배당금" not in (r.get("se") or ""):
                    continue
                knd = r.get("stock_knd") or ""
                if knd and "보통" not in knd:                 # 우선주 행 제외
                    continue
                for k, yy in (("thstrm", y), ("frmtrm", y - 1), ("lwfr", y - 2)):
                    v = num(r.get(k))
                    if v is not None and str(yy) not in out:
                        out[str(yy)] = v
        except Exception:
            pass
        time.sleep(0.06)
    return out

def main():
    pool = json.loads((BASE / "data" / "db" / "screener_pool.json").read_text(encoding="utf-8"))
    codes = [r["c"] for r in pool.get("kr") or [] if r.get("c")]
    mp = corp_map()
    latest = datetime.now().year - 1                      # 최근 확정 사업연도 (8월 기준 전년도 보고서 확정)
    d = {}
    ok = 0
    for i, c in enumerate(codes):
        corp = mp.get(c)
        if not corp:
            continue
        ys = dps_years(corp, (latest, latest - 2))        # 5개년
        if not ys:
            continue
        # 연속 증가 연수 — 최신 연도부터 거꾸로 '전년보다 증가(>)' 이어진 횟수
        inc = 0
        y = latest
        while str(y) in ys and str(y - 1) in ys and ys[str(y)] > ys[str(y - 1)]:
            inc += 1
            y -= 1
        d[c] = {"inc": inc, "y": ys}
        ok += 1
        if i % 300 == 299:
            print(f"  {i+1}/{len(codes)} (성공 {ok})", flush=True)
    OUT.write_text(json.dumps({"asof": datetime.now().strftime("%Y-%m-%d %H:%M"), "latest": latest,
                               "d": d}, ensure_ascii=False), encoding="utf-8")
    inc3 = sum(1 for v in d.values() if v["inc"] >= 3)
    print(f"[dps] ✅ {ok}/{len(codes)}종 · 3년연속증가 {inc3}종 → {OUT}", flush=True)

if __name__ == "__main__":
    main()
