# -*- coding: utf-8 -*-
"""
krx_openapi.py — KRX OPEN API (openapi.krx.co.kr) 공용 클라이언트.

  엔드포인트 : http://data-dbg.krx.co.kr/svc/apis/{cat}/{api}?basDd=YYYYMMDD
  인증       : 헤더 AUTH_KEY
  응답 루트  : OutBlock_1

인증키 탐색 순서(값은 절대 출력하지 않음):
  1) 환경변수 KRX_API_KEY
  2) 상위 디렉터리들의 SECURITY/openapi.krx.co.kr.txt  (권장: D:\\claudeCowork\\SECURITY\\)
  3) secrets.env 의 KRX_API_KEY=...

일자별 응답은 basDd 단위로 디스크 캐시 → 1년 백필은 최초 1회만 네트워크를 태우고,
일일 업데이트는 신규 영업일만 조회한다.
"""
import os
import json
import time
import gzip
import urllib.request
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

BASE = "https://data-dbg.krx.co.kr/svc/apis"  # (v3.59.1) http는 302 리다이렉트 — https 직결
_BASE_DIR = Path(__file__).resolve().parent


# ── 인증키 ────────────────────────────────────────────
def _find_key():
    k = os.environ.get("KRX_API_KEY")
    if k and k.strip():
        return k.strip()
    cands = []
    for anc in [_BASE_DIR, *_BASE_DIR.parents]:
        cands.append(anc / "SECURITY" / "openapi.krx.co.kr.txt")
        cands.append(anc / "openapi.krx.co.kr.txt")
        cands.append(anc / "SECURITY" / "secrets.env")
        cands.append(anc / "secrets.env")
    # (v3.59.1) 연결폴더 SECURITY 절대경로 폴백 — $RUN(outputs/nmr_runsrc) 추출본 실행 시
    # 조상 경로에 SECURITY 가 없어 키를 못 찾는다(2026-07-11 3.1.13 KOSPI200 결측의 근본 원인).
    import glob as _g
    for pat in ("/sessions/*/mnt/*/SECURITY/openapi.krx.co.kr.txt",
                "/sessions/*/mnt/*/SECURITY/secrets.env"):
        for hit in sorted(_g.glob(pat)):
            cands.append(Path(hit))
    for c in cands:
        try:
            if not c.is_file():
                continue
            txt = c.read_text(encoding="utf-8", errors="ignore")
            if c.name.endswith(".env"):
                for line in txt.splitlines():
                    t = line.strip()
                    if t.startswith("KRX_API_KEY") and "=" in t:
                        v = t.split("=", 1)[1].strip()
                        if v:
                            return v
            else:
                v = txt.strip().split()[0] if txt.strip() else ""
                if v:
                    return v
        except Exception:
            pass
    return None


API_KEY = _find_key()


# ── 캐시 ──────────────────────────────────────────────
def _cache_dir():
    db = os.environ.get("DERIV_DB")
    root = Path(db).resolve().parent if db else _BASE_DIR
    d = root / "krx_cache"
    try:
        d.mkdir(parents=True, exist_ok=True)
    except Exception:
        import tempfile
        d = Path(tempfile.gettempdir()) / "krx_cache"
        d.mkdir(parents=True, exist_ok=True)
    return d


def _cache_path(cat, api, bas_dd):
    return _cache_dir() / f"{cat}_{api}_{bas_dd}.json.gz"


def call(cat, api, bas_dd, tries=3, use_cache=True):
    """하루치 조회 → list[dict]. 실패/휴장일은 []."""
    if not API_KEY:
        return []
    cp = _cache_path(cat, api, bas_dd)
    if use_cache and cp.exists():
        try:
            with gzip.open(cp, "rt", encoding="utf-8") as fh:
                return json.load(fh)
        except Exception:
            pass
    url = f"{BASE}/{cat}/{api}?basDd={bas_dd}"
    req = urllib.request.Request(url, headers={"AUTH_KEY": API_KEY, "User-Agent": "Mozilla/5.0"})
    rows = []
    for t in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=25) as r:
                rows = json.loads(r.read().decode("utf-8", "ignore")).get("OutBlock_1", []) or []
            break
        except Exception:
            if t == tries - 1:
                return []
            time.sleep(1.2)
    if use_cache:
        try:
            with gzip.open(cp, "wt", encoding="utf-8") as fh:
                json.dump(rows, fh, ensure_ascii=False)
        except Exception:
            pass
    return rows


def call_range(cat, api, dates, workers=6):
    """여러 영업일 병렬 조회 → {basDd: rows}. 휴장일은 빈 리스트라 자연 제외."""
    out = {}
    if not API_KEY or not dates:
        return out
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(call, cat, api, d): d for d in dates}
        for f in futs:
            d = futs[f]
            try:
                r = f.result()
            except Exception:
                r = []
            if r:
                out[d] = r
    return out


# ── 파싱 헬퍼 ─────────────────────────────────────────
def num(v):
    """'1,219.62' → 1219.62 / '' → None"""
    try:
        if v is None:
            return None
        s = str(v).replace(",", "").strip()
        if not s or s in ("-", "."):
            return None
        return float(s)
    except Exception:
        return None


def ymd(d):
    return f"{d[:4]}-{d[4:6]}-{d[6:8]}"


def business_days(back_days):
    """오늘 기준 back_days 일 전까지의 월~금 날짜 문자열(YYYYMMDD) 리스트(최신순)."""
    from datetime import date, timedelta
    out, t = [], date.today()
    for i in range(back_days + 1):
        d = t - timedelta(days=i)
        if d.weekday() < 5:
            out.append(d.strftime("%Y%m%d"))
    return out


if __name__ == "__main__":
    print("KRX OPEN API key:", "OK(로드됨)" if API_KEY else "없음")
    d = business_days(7)[0]
    for cat, api in [("idx", "kospi_dd_trd"), ("drv", "fut_bydd_trd"), ("idx", "drvprod_dd_trd")]:
        print(f"  {cat}/{api} @{d}: {len(call(cat, api, d))}행")
