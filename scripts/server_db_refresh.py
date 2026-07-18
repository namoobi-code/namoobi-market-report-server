#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""server_db_refresh.py — 통합 DB(json) 중 '서버 수집 가능' 섹션 매일 갱신. (2026-07-17 신설 · 안전 버전)

대상 4종 (전부 stdlib·무LLM — repo 코드 재사용, 로직 미러는 merge.py 의 한 줄 sync 호출만):
  ① customs        관세청 수출 10일 잠정치  → db/customs.json          (fetch_customs.py + nmr_db.sync)
  ② leading        경기선행지수 순환변동치  → db/leading.json + db/series_leading.json
  ③ krx_brief      KRX 증시 Brief·공매도 브리프 PDF 캡쳐 → data/krx_brief/ + db/krx_brief.json (스크립트 자가 기록)
  ④ series_hy_oas  美 HY 스프레드(FRED BAMLH0A0HYM2) → data/nmr_hy_history.json + db/series_hy_oas.json

PC 리포트 실행은 기존 그대로(동일 수집·merge 동기화) — 서버는 PC 미실행일 공백을 메우고
대시보드(namoobi.duckdns.org) 최신성을 보장한다. WebSearch/LLM/Chrome 필요 섹션(점도표·정책금리·
ISM·버크셔·OECD CLI 등)은 서버 수집 불가 — PC 전용 유지.

키: ~/namoobi/secrets/.env 의 DATA_GO_KR_KEY·FRED_API_KEY (env 주입 — fetch_customs·nmr_fred 가 env 1순위)
cron: 35 15 * * *  ·  35 6 * * *  (기존 배치 5분 전)
"""
import os, sys, json, glob, subprocess, datetime

BASE = os.path.expanduser("~/namoobi")
S = os.path.join(BASE, "scripts")
sys.path.insert(0, S)
WORK = os.path.join(BASE, "work")
os.makedirs(WORK, exist_ok=True)
DB = os.path.join(BASE, "data", "db")
DATA = os.path.join(BASE, "data")

# secrets/.env → 환경변수 (fetch_customs=DATA_GO_KR_KEY, nmr_fred=FRED_API_KEY 가 env 1순위)
try:
    for ln in open(os.path.join(BASE, "secrets", ".env")):
        ln = ln.strip()
        if "=" in ln and not ln.startswith("#"):
            k, v = ln.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())
except Exception:
    pass

import nmr_db  # noqa: E402

TODAY = datetime.date.today().isoformat()
RUNM = TODAY[:7]


def _load(p):
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return None


def _run(args, timeout, cwd=WORK):
    r = subprocess.run(args, timeout=timeout, cwd=cwd, capture_output=True, text=True)
    tail = (r.stdout or "").strip().splitlines()[-2:]
    print("   ", args[-2] if len(args) > 1 else args[0], "rc=%d" % r.returncode, "|", " / ".join(tail))
    return r.returncode == 0


def sec_customs():
    """merge.py L1003 미러: 변경 시에만 nmr_customs.json 생성 → sync, 없으면 DB 유지."""
    _run([sys.executable, os.path.join(S, "fetch_customs.py"), WORK], 240)
    cs = _load(os.path.join(WORK, "nmr_customs.json"))
    ok = isinstance(cs, dict) and cs.get("series") and cs.get("months")
    r = nmr_db.sync("customs", cs if ok else None, TODAY, ((cs or {}).get("marker") or RUNM) if ok else RUNM, DB)
    print("[customs]", "갱신" if ok else "변경없음(DB 유지)", "| marker", (r or {}).get("marker") if isinstance(r, dict) else "")


def sec_leading():
    """merge.py L986·L992 미러: leading sync + series_leading 누적."""
    _run([sys.executable, os.path.join(S, "fetch_leading.py"), WORK], 120)
    kl = (_load(os.path.join(WORK, "nmr_leading.json")) or {}).get("korea_leading")
    if kl:
        marker = max((str(x.get("period") or "") for x in kl), default="") or RUNM
        nmr_db.sync("leading", kl, TODAY, marker, DB)
    lsr = _load(os.path.join(WORK, "nmr_leading_series.json"))
    if isinstance(lsr, list) and lsr:
        d = nmr_db.dbseries("leading", lsr, DB)
        print("[leading] series", d.get("status"), "(%d pts)" % len(d.get("data") or []))
    else:
        print("[leading] 실측 실패 — DB 유지(비차단)")


def sec_krx_brief():
    """fetch_krx_brief 는 영구저장(data/krx_brief/)·DB(db/krx_brief.json) 자가 기록 — argv=data 루트."""
    ok = _run([sys.executable, os.path.join(S, "fetch_krx_brief.py"), DATA], 180)
    print("[krx_brief]", "OK" if ok else "실패(직전 회차 유지·비차단)")


def sec_oecd():
    """(v3.67) OECD CLI — SDMX 직접 수집(fetch_oecd_cli.py) + merge L997 미러 sync."""
    _run([sys.executable, os.path.join(S, "fetch_oecd_cli.py"), WORK], 120)
    oc = _load(os.path.join(WORK, "nmr_oecd_cli.json"))
    ok = isinstance(oc, dict) and oc.get("months") and oc.get("series")
    nmr_db.sync("oecd_cli", oc if ok else None, TODAY,
                ((oc or {}).get("data_updated") or RUNM) if ok else RUNM, DB)
    print("[oecd_cli]", ("갱신 ~" + (oc.get("months") or ["?"])[-1]) if ok else "실패 — DB 유지(비차단)")


def sec_hy():
    """fetch_kr.py HY 블록 미러(스키마 동일): FRED 일별 → nmr_hy_history 누적 + db/series_hy_oas.json."""
    try:
        from nmr_fred import fred_key, fred_series
        if not fred_key():
            print("[hy] FRED_API_KEY 없음 — skip")
            return
        start = (datetime.date.today() - datetime.timedelta(days=1200)).isoformat()
        daily = fred_series("BAMLH0A0HYM2", start=start)
        if not daily:
            print("[hy] FRED 응답 없음 — skip")
            return
        hp = os.path.join(DATA, "nmr_hy_history.json")
        hist = _load(hp) or {}
        mer = {d: v for d, v in (hist.get("series") or [])}
        for d, v in daily:
            if v is not None:
                mer[d] = v
        hist["series"] = [[d, mer[d]] for d in sorted(mer)]
        hist["updated"] = TODAY
        json.dump(hist, open(hp, "w"), ensure_ascii=False)
        json.dump({"as_of": TODAY, "marker": hist["series"][-1][0],
                   "source": "FRED BAMLH0A0HYM2 (ICE BofA US HY OAS) 일별 누적", "data": hist["series"]},
                  open(os.path.join(DB, "series_hy_oas.json"), "w"), ensure_ascii=False)
        print("[hy] %d pts · 최신 %s=%s" % (len(hist["series"]), hist["series"][-1][0], hist["series"][-1][1]))
    except Exception as e:
        print("[hy] skip(비차단):", repr(e)[:70])


def main():
    print("=== server_db_refresh", datetime.datetime.now().isoformat(timespec="seconds"))
    for f in (sec_customs, sec_leading, sec_oecd, sec_krx_brief, sec_hy):
        try:
            f()
        except Exception as e:
            print("[%s] 실패(비차단): %s" % (f.__name__, repr(e)[:80]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
