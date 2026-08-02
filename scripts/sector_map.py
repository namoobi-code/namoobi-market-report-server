#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""sector_map.py — 종목 업종 분류 맵 (2026-08-02 신설 · 주 1회 cron + 증분).

  KR: KRX 업종(KIS inquire-price bstp_kor_isnm, 예 "전기·전자")
      WICS 대분류(와이즈인덱스 GetIndexComponets G10~G55, 예 "IT")
      WICS 세부(네이버 업종별시세 upjong, 예 "반도체와반도체장비") — FnGuide WICS 산업, GICS 준용
  US: 세부업종 한글(네이버 api.stock basic industryCodeType.industryGroupKor, 예 "반도체")
      — 섹터(GICS급)는 screener_pool.us[].sector(야후)가 이미 보유

산출: data/db/sector_map.json {asof, kr:{code:{krx,wics,wics2}}, us:{sym:{ind}}}
사용: sector_map.py [--full]   (기본: KIS·US는 기존 맵에 없는 종목만 증분 — WICS/네이버업종은 매회 전체)
cron: 30 7 * * 0 (일요일)
"""
import json, re, sys, time, urllib.request, urllib.parse
from datetime import datetime, timedelta
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "data" / "db" / "sector_map.json"
H = {"User-Agent": "Mozilla/5.0"}
FULL = "--full" in sys.argv

def raw_get(url, headers=None, timeout=15):
    try:
        return urllib.request.urlopen(urllib.request.Request(url, headers=headers or H), timeout=timeout).read()
    except Exception:
        return None

def dec(b):
    if b is None: return ""
    try: return b.decode("utf-8")
    except UnicodeDecodeError: return b.decode("cp949", "ignore")

def wics_map():
    """와이즈인덱스 WICS 10개 대분류 구성종목 → code→섹터명."""
    out = {}; dt8 = None
    for d in range(0, 10):                                  # 최근 영업일 탐색
        t = (datetime.now() - timedelta(days=d)).strftime("%Y%m%d")
        r = raw_get(f"http://www.wiseindex.com/Index/GetIndexComponets?ceil_yn=0&dt={t}&sec_cd=G10",
                    {"User-Agent": "Mozilla/5.0", "Referer": "http://www.wiseindex.com/"})
        try:
            if r and (json.loads(r).get("list") or []): dt8 = t; break
        except Exception: pass
    if not dt8: return out
    for sec in ("G10", "G15", "G20", "G25", "G30", "G35", "G40", "G45", "G50", "G55"):
        r = raw_get(f"http://www.wiseindex.com/Index/GetIndexComponets?ceil_yn=0&dt={dt8}&sec_cd={sec}",
                    {"User-Agent": "Mozilla/5.0", "Referer": "http://www.wiseindex.com/"})
        try:
            for x in json.loads(r).get("list") or []:
                out[x["CMP_CD"]] = x.get("SEC_NM_KOR")
        except Exception: pass
        time.sleep(0.3)
    return out

def naver_upjong():
    """네이버 업종별시세(WICS 산업 기반 세부업종) → code→업종명. 약 80업종."""
    out = {}
    page = dec(raw_get("https://finance.naver.com/sise/sise_group.naver?type=upjong"))
    ups = re.findall(r'sise_group_detail\.naver\?type=upjong&(?:amp;)?no=(\d+)"[^>]*>([^<]+)', page)
    for no, nm in ups:
        p2 = dec(raw_get(f"https://finance.naver.com/sise/sise_group_detail.naver?type=upjong&no={no}"))
        for cd in set(re.findall(r'/item/main\.naver\?code=(\d{6})', p2)):
            out[cd] = nm.strip()
        time.sleep(0.12)
    return out

def kis_krx(codes, old):
    """KIS 주식현재가 → KRX 업종명. 증분(맵에 없는 종목만)."""
    res = {}
    try:
        sys.path.insert(0, str(BASE / "scripts"))
        import kis_api as K
        c = K._creds(); tok = K._token(c)
        todo = [cd for cd in codes if FULL or cd not in old]
        print(f"  KRX(KIS) 대상 {len(todo)}종목")
        for i, cd in enumerate(todo):
            try:
                j = K._get(c, tok, "/uapi/domestic-stock/v1/quotations/inquire-price", "FHKST01010100",
                           {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": cd})
                nm = (j.get("output") or {}).get("bstp_kor_isnm")
                if nm: res[cd] = nm.strip()
            except Exception: pass
            time.sleep(0.06)
            if todo and i % 500 == 499: print(f"  KIS {i+1}/{len(todo)}")
    except Exception as e:
        print("KIS KRX 실패:", repr(e))
    return res

def us_ind(syms, old):
    """네이버 미국종목 basic → 세부업종 한글. NYSE=무접미사·나스닥=.O (기업개요와 동일 규칙)."""
    res = {}
    todo = [s for s in syms if FULL or s not in old]
    print(f"  US 세부업종 대상 {len(todo)}종목")
    for i, s in enumerate(todo):
        for suf in ("", ".O", ".N", ".K"):
            r = raw_get(f"https://api.stock.naver.com/stock/{urllib.parse.quote(s)}{suf}/basic", timeout=8)
            if not r: continue
            try:
                j = json.loads(r)
                g = (j.get("industryCodeType") or {}).get("industryGroupKor")
                if g: res[s] = g
                if j.get("reutersCode"): break        # 심볼 확인됨(업종 없어도 다음 접미사 불필요)
            except Exception:
                continue
        time.sleep(0.05)
        if todo and i % 500 == 499: print(f"  US {i+1}/{len(todo)}")
    return res

def main():
    old = {}
    try: old = json.loads(OUT.read_text(encoding="utf-8"))
    except Exception: pass
    okr = old.get("kr") or {}; ous = old.get("us") or {}
    pool = json.loads((BASE / "data" / "db" / "screener_pool.json").read_text(encoding="utf-8"))
    kr_codes = [r["code"] for r in pool.get("kr") or [] if r.get("code")]
    us_syms = [r["sym"] for r in pool.get("us") or [] if r.get("sym")]
    w = wics_map(); print(f"  WICS 대분류: {len(w)}종목")
    u2 = naver_upjong(); print(f"  WICS 세부(네이버 업종): {len(u2)}종목")
    kx = kis_krx(kr_codes, {cd for cd, v in okr.items() if v.get("krx")})
    ui = us_ind(us_syms, {s for s, v in ous.items() if v.get("ind")})
    kr = {}
    for cd in set(kr_codes) | set(okr):
        e = dict(okr.get(cd) or {})
        if cd in w: e["wics"] = w[cd]
        if cd in u2: e["wics2"] = u2[cd]
        if cd in kx: e["krx"] = kx[cd]
        if e: kr[cd] = e
    us = {}
    for s in set(us_syms) | set(ous):
        e = dict(ous.get(s) or {})
        if s in ui: e["ind"] = ui[s]
        if e: us[s] = e
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"asof": datetime.now().strftime("%Y-%m-%d %H:%M"), "kr": kr, "us": us},
                              ensure_ascii=False), encoding="utf-8")
    print(f"[sector] ✅ kr {len(kr)} · us {len(us)} → {OUT}")

if __name__ == "__main__":
    main()
