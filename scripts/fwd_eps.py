#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fwd_eps.py — 시장 12개월 선행이익 프록시 + KOSPI 일봉 (매일 1회, 장 마감 풀 빌드 후)

배경: 기사(에프앤가이드 QuantiWise)의 'KOSPI 12개월 선행 EPS' 차트를 무료로 재현.
  QuantiWise 는 유료 → 스크리너 풀의 종목별 선행PER(네이버 컨센서스)로 자체 집계:
    시장 선행이익 E = Σ(시총 ÷ 선행PER)   (시총상위 KOSPI 200종 중 fper 보유분 — 실측 185종)
    시장 선행PER   = Σ시총 ÷ E
  ※ 컨센서스 과거 스냅샷은 무료 소스에 없어 백필 불가 — 수집 개시일부터 매일 누적.
KOSPI: 당일 종가는 네이버, 과거 2년은 ECOS 802Y001(차트 배경·DDR5 오버레이용)로 갱신.

산출: data/db/fwd_eps.json
  {"asof","t":[YYYYMMDD],"e":[조원],"fper":[],"kospi":[],"n":[표본수],
   "kospi_hist":{"t":[YYYYMMDD],"v":[]}}
cron: 20 16 * * 1-5
"""
import json, urllib.request
from datetime import datetime, timedelta
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DB   = BASE / "data" / "db"
OUT  = DB / "fwd_eps.json"

def _ecos_key():
    for p in [BASE/"keys"/"ecos.txt"] + sorted(Path("/sessions").glob("*/mnt/claudeCowork/SECURITY/한국은행OPENAPI인증키.txt")) + [Path("D:/claudeCowork/SECURITY/한국은행OPENAPI인증키.txt")]:
        try: return Path(p).read_text(encoding="utf-8").strip()
        except Exception: pass
    return None

def _jget(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (namoobi)"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.loads(r.read().decode("utf-8"))

def main():
    pool = json.loads((DB/"screener_pool.json").read_text(encoding="utf-8"))
    kr = [r for r in pool.get("kr") or [] if r.get("mk") == "KOSPI" and r.get("cap")]
    kr.sort(key=lambda r: -r["cap"])
    uni = [r for r in kr[:200] if r.get("fper") and r["fper"] > 0]
    E = sum(r["cap"]/r["fper"] for r in uni)              # 원
    C = sum(r["cap"] for r in uni)
    e_tril = round(E/1e12, 1)                              # 조원
    fper = round(C/E, 2)

    # 당일 KOSPI 종가 (네이버)
    kospi = None
    try:
        j = _jget("https://m.stock.naver.com/api/index/KOSPI/basic")
        kospi = float(str(j.get("closePrice") or "").replace(",", "")) or None
    except Exception as ex:
        print("  [warn] naver KOSPI 실패:", ex)

    prev = {}
    if OUT.exists():
        try: prev = json.loads(OUT.read_text(encoding="utf-8"))
        except Exception: pass
    t = prev.get("t") or []; e = prev.get("e") or []; fp = prev.get("fper") or []
    ks = prev.get("kospi") or []; nn = prev.get("n") or []
    today = datetime.now().strftime("%Y%m%d")
    if t and t[-1] == today:                               # 같은 날 재실행 → 덮어쓰기
        t.pop(); e.pop(); fp.pop(); ks.pop(); nn.pop()
    t.append(today); e.append(e_tril); fp.append(fper); ks.append(kospi); nn.append(len(uni))

    # KOSPI 과거 2년 (ECOS) — DDR5 오버레이 배경
    hist = prev.get("kospi_hist") or {"t": [], "v": []}
    ek = _ecos_key()
    if ek:
        try:
            s = (datetime.now()-timedelta(days=740)).strftime("%Y%m%d")
            j = _jget(f"https://ecos.bok.or.kr/api/StatisticSearch/{ek}/json/kr/1/600/802Y001/D/{s}/{today}/0001000")
            rows = (j.get("StatisticSearch") or {}).get("row") or []
            hist = {"t": [x["TIME"] for x in rows], "v": [float(x["DATA_VALUE"]) for x in rows]}
        except Exception as ex:
            print("  [warn] ECOS KOSPI 이력 실패:", ex)

    DB.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "asof": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "src": "선행이익=스크리너 풀 종목별 선행PER(네이버 컨센서스) 시총가중 집계(KOSPI 시총상위 200 중 보유분) · KOSPI=네이버(당일)+ECOS 802Y001(이력)",
        "t": t[-500:], "e": e[-500:], "fper": fp[-500:], "kospi": ks[-500:], "n": nn[-500:],
        "kospi_hist": hist}, ensure_ascii=False), encoding="utf-8")
    print(f"[fwd_eps] ✅ {today} 선행이익 {e_tril}조 · 선행PER {fper} · 표본 {len(uni)} · KOSPI {kospi} · 이력 {len(hist['t'])}일")

if __name__ == "__main__":
    main()
