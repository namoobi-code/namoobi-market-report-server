#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fetch_us_krname.py — 미국 종목 티커 → 한글명 매핑 수집. (2026-07-20 신설)

출처: KIS 해외 종목 마스터(무인증 공개 파일)
  https://new.real.download.dws.co.kr/common/master/{nasmst|nysmst|amsmst}.cod.zip
  탭 구분 · cp949 · 필드 [4]=티커 [6]=한글종목명 [7]=영문종목명 [8]=종목유형(2=주식,3=ETF)

한글명이 실제로 한글을 포함할 때만 채택한다(마이너 종목·일부 ETF 는 한글명 칸에도 영문이 들어옴).
출력: db/us_krname.json  {"as_of": "...", "n": 1234, "map": {"NVDA": "엔비디아", ...}}

대시보드(종목 스크리너·캘린더)와 docx 빌더가 이 매핑으로 미국 종목에 한글명을 병기한다.
"""
import io
import json
import os
import re
import sys
import urllib.request
import zipfile
from datetime import datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(BASE, "data", "db", "us_krname.json")
SRC = "https://new.real.download.dws.co.kr/common/master/%s.cod.zip"
FILES = ["nasmst", "nysmst", "amsmst"]
UA = {"User-Agent": "Mozilla/5.0"}
HANGUL = re.compile(r"[가-힣]")


def build():
    m, stat = {}, []
    for name in FILES:
        try:
            raw = urllib.request.urlopen(
                urllib.request.Request(SRC % name, headers=UA), timeout=60).read()
            z = zipfile.ZipFile(io.BytesIO(raw))
            lines = z.read(z.namelist()[0]).decode("cp949", "ignore").splitlines()
        except Exception as e:
            print("  [%s] 실패: %s" % (name, repr(e)[:70]))
            continue
        n = 0
        for l in lines:
            p = l.split("\t")
            if len(p) < 8:
                continue
            tk, kr = p[4].strip(), p[6].strip()
            if not tk or not kr or not HANGUL.search(kr):
                continue          # 한글명 없는 종목(영문만)은 건너뜀 → 프론트가 영문명 사용
            if tk not in m:       # 중복 시 먼저 온 거래소 우선(NAS→NYS→AMS)
                m[tk] = kr
                n += 1
        stat.append("%s %d" % (name, n))
        print("  [%s] %d행 → 한글명 %d종" % (name, len(lines), n))
    return m, stat


def patch_pool(m=None):
    """screener_pool 의 US 행에 kn(한글명) 을 심는다.
       스크리너 표·캘린더(월간 실적발표)가 같은 풀을 쓰므로 한 번에 둘 다 반영된다.
       screener_pool 재빌드 시 kn 이 날아가므로 fetch_lending 과 같이 빌드 직후 재패치한다."""
    if m is None:
        try:
            m = json.load(open(OUT, encoding="utf-8"))["map"]
        except Exception as e:
            print("[us_krname] 매핑 로드 실패 — 패치 skip:", repr(e)[:60]); return 0
    pool_p = os.path.join(BASE, "data", "db", "screener_pool.json")
    if not os.path.exists(pool_p):
        print("[us_krname] screener_pool 없음 — 패치 skip"); return 0
    try:
        pool = json.load(open(pool_p, encoding="utf-8"))
    except Exception as e:
        print("[us_krname] 풀 로드 실패:", repr(e)[:60]); return 0
    n = 0
    for r in pool.get("us", []):
        kr = m.get(str(r.get("c", "")).upper())
        if kr:
            r["kn"] = kr
            n += 1
    tmp = pool_p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(pool, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, pool_p)
    print("[us_krname] 풀 패치 ✅ US %d/%d 종에 한글명 부여" % (n, len(pool.get("us", []))))
    return n


def main():
    print("[us_krname] KIS 해외 마스터에서 한글명 수집")
    m, stat = build()
    if not m:
        print("[us_krname] 수집 0건 — 기존 매핑으로 풀 패치만 시도")
        patch_pool()
        return 1
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    tmp = OUT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"as_of": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                   "source": "KIS 해외 종목 마스터(nas/nys/ams)",
                   "n": len(m), "map": m}, f, ensure_ascii=False)
    os.replace(tmp, OUT)
    print("[us_krname] ✅ %d종 저장 → %s (%s)" % (len(m), OUT, " · ".join(stat)))
    for t in ("NVDA", "AAPL", "MSFT", "TSLA", "BRK.B"):
        if t in m:
            print("   샘플 %-6s %s" % (t, m[t]))
    patch_pool(m)
    return 0


if __name__ == "__main__":
    sys.exit(main())
