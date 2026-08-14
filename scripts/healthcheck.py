#!/usr/bin/env python3
# healthcheck.py — 대시보드 자가진단 (v1.0 · 2026-08-14 신설)
#
#   배경: 2026-08-14 하루에 두 번, "다른 세션의 변경이 조용히 화면을 깨뜨린" 사고가 났다.
#     ① 대형 DB 가 /api/bundle 에 자동 편입되며 38.9MB/6.4초 → 화면이 로딩 대기 중 빈칸
#     ② FactSet full_summary 스키마가 배열→객체로 바뀌며 .map 예외 → daily·AI추론 탭 백지
#   둘 다 사용자가 눈으로 발견하기 전까지 아무도 몰랐다. 이 스크립트가 대신 지켜본다.
#
#   점검 항목 (실측만 — 추정 금지)
#     A. 번들   : 크기·응답시간 (임계 12MB / 3.0초)
#     B. API    : 핵심 엔드포인트 200 여부
#     C. 스키마 : 화면이 .map/.forEach 로 순회하는 필드가 실제 배열인지 (드리프트 조기 경보)
#     D. 신선도 : 매일 갱신돼야 할 DB 가 하루 넘게 안 바뀌었는지
#     E. 자원   : 디스크·메모리·스왑
#   결과 → data/db/health.json (대시보드 배지), 이상 시 keys/gmail_app_password.txt 로 메일.
#
#   사용: python3 scripts/healthcheck.py [--mail]
import json, os, shutil, subprocess, sys, time, urllib.request, datetime as dt

BASE = "/home/ubuntu/namoobi"
DB   = os.path.join(BASE, "data", "db")
HOST = "http://127.0.0.1"
MAIL = "--mail" in sys.argv

BUNDLE_MAX_MB, BUNDLE_MAX_SEC = 12.0, 3.0
APIS = ["/", "/app.js", "/api/bundle", "/api/db/screener_pool", "/api/db/appe",
        "/api/db/crypto_overview", "/api/krliq?days=30", "/api/coin/BTC"]
# 화면이 배열로 순회하는 필드 — 형태가 바뀌면 탭 전체가 죽는다 (2026-08-14 사고)
ARRAY_FIELDS = [
    ("data/report/report_data.json", "news.top_news"),
    ("data/report/report_data.json", "news.events_calendar"),
    ("data/db/berkshire.json",       "data.top_holdings"),
    ("data/db/appe.json",            "groups"),
]
# 매일 갱신돼야 하는 DB (파일명, 허용 지연 시간)
FRESH = [("crypto_overview.json", 6), ("news_pool.json", 6), ("kimp_series.json", 3),
         ("screener_pool.json", 30), ("appe.json", 30), ("kr_liquidity.json", 30)]

def dig(o, path):
    for k in path.split("."):
        if not isinstance(o, dict) or k not in o: return None
        o = o[k]
    return o

def probe(u):
    t0 = time.time()
    try:
        with urllib.request.urlopen(HOST + u, timeout=30) as r:
            n = len(r.read()); return r.status, n, round(time.time() - t0, 3)
    except Exception as e:
        return 0, 0, round(time.time() - t0, 3)

def main():
    out = {"as_of": dt.datetime.now().strftime("%Y-%m-%d %H:%M"), "ok": True, "alerts": [], "checks": {}}

    # A·B. API + 번들
    api = {}
    for u in APIS:
        st, n, sec = probe(u)
        api[u] = {"status": st, "bytes": n, "sec": sec}
        if st != 200: out["alerts"].append(f"[API] {u} → HTTP {st or '연결실패'}")
    out["checks"]["api"] = api
    b = api.get("/api/bundle", {})
    mb = b.get("bytes", 0) / 1e6
    out["checks"]["bundle_mb"] = round(mb, 2)
    if mb > BUNDLE_MAX_MB:
        out["alerts"].append(f"[번들] {mb:.1f}MB — 임계 {BUNDLE_MAX_MB}MB 초과. app.py BUNDLE_SKIP 에 대형 DB 추가 필요")
    if b.get("sec", 0) > BUNDLE_MAX_SEC:
        out["alerts"].append(f"[번들] 응답 {b['sec']}초 — 임계 {BUNDLE_MAX_SEC}초 초과")
    # 번들에 새로 끼어든 대형 파일 지목
    big = sorted(((p.stat().st_size, p.stem) for p in __import__("pathlib").Path(DB).glob("*.json")), reverse=True)[:5]
    out["checks"]["db_top5_mb"] = [{"name": n, "mb": round(s / 1e6, 1)} for s, n in big]

    # C. 스키마 드리프트
    sch = {}
    for rel, path in ARRAY_FIELDS:
        f = os.path.join(BASE, rel)
        if not os.path.exists(f): sch[f"{os.path.basename(rel)}:{path}"] = "파일없음"; continue
        try: v = dig(json.load(open(f, encoding="utf-8")), path)
        except Exception as e: sch[f"{os.path.basename(rel)}:{path}"] = f"파싱실패 {str(e)[:40]}"; continue
        t = type(v).__name__
        sch[f"{os.path.basename(rel)}:{path}"] = t
        if v is not None and not isinstance(v, list):
            out["alerts"].append(f"[스키마] {rel} {path} 가 배열이 아님({t}) — 화면 순회 코드가 깨질 수 있음")
    # FactSet full_summary — 배열/{sections}/dict 모두 화면이 흡수하지만 '문자열'이면 표시가 뭉개진다
    try:
        fs = dig(json.load(open(os.path.join(BASE, "data/report/report_data.json"), encoding="utf-8")),
                 "markets.factset.report.full_summary")
        sch["factset.full_summary"] = type(fs).__name__
        if isinstance(fs, str): out["alerts"].append("[스키마] factset full_summary 가 문자열 — 섹션 분해 불가")
    except Exception: pass
    out["checks"]["schema"] = sch

    # D. 신선도
    fr = {}
    now = time.time()
    for name, hrs in FRESH:
        f = os.path.join(DB, name)
        if not os.path.exists(f): fr[name] = "없음"; out["alerts"].append(f"[신선도] {name} 없음"); continue
        age = round((now - os.path.getmtime(f)) / 3600, 1)
        fr[name] = f"{age}h"
        if age > hrs: out["alerts"].append(f"[신선도] {name} {age}시간 전 — 기대 {hrs}시간 이내(크론 확인)")
    out["checks"]["freshness"] = fr

    # E. 자원
    du = shutil.disk_usage("/")
    mem = {}
    try:
        for ln in open("/proc/meminfo"):
            k, v = ln.split(":"); mem[k] = int(v.split()[0]) // 1024
    except Exception: pass
    res = {"disk_used_pct": round(du.used / du.total * 100, 1),
           "disk_free_gb": round(du.free / 1e9, 1),
           "mem_total_mb": mem.get("MemTotal"), "mem_avail_mb": mem.get("MemAvailable"),
           "swap_used_mb": (mem.get("SwapTotal", 0) - mem.get("SwapFree", 0))}
    out["checks"]["resource"] = res
    if res["disk_used_pct"] > 85: out["alerts"].append(f"[자원] 디스크 {res['disk_used_pct']}% 사용")
    if (res.get("mem_avail_mb") or 9999) < 150: out["alerts"].append(f"[자원] 가용 메모리 {res['mem_avail_mb']}MB")
    if res["swap_used_mb"] > 800: out["alerts"].append(f"[자원] 스왑 {res['swap_used_mb']}MB 사용 — 메모리 부족 신호")

    out["ok"] = not out["alerts"]
    os.makedirs(DB, exist_ok=True)
    json.dump(out, open(os.path.join(DB, "health.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(("✅ 정상" if out["ok"] else f"⚠️ 경보 {len(out['alerts'])}건") +
          f" · 번들 {out['checks']['bundle_mb']}MB/{b.get('sec')}s · 가용메모리 {res.get('mem_avail_mb')}MB")
    for a in out["alerts"]: print("   -", a)

    if MAIL and out["alerts"]:
        body = ("namoobi 대시보드 자가진단 경보\n\n" + "\n".join("· " + a for a in out["alerts"]) +
                f"\n\n점검 {out['as_of']} · 번들 {out['checks']['bundle_mb']}MB/{b.get('sec')}초 · "
                f"가용메모리 {res.get('mem_avail_mb')}MB · 디스크 {res['disk_used_pct']}%\n"
                "상세: http://namoobi.duckdns.org/api/db/health\n")
        try:
            payload = json.dumps({"to": "namoobi@gmail.com", "bcc": [],
                                  "subject": f"[namoobi] 서버 경보 {len(out['alerts'])}건 — {out['as_of']}",
                                  "body": body, "attach": []})
            subprocess.run(["python3", os.path.join(BASE, "scripts", "send_report_mail.py")],
                           input=payload.encode(), timeout=60, check=False)
            print("   경보 메일 발송 시도 완료")
        except Exception as e:
            print("   메일 발송 실패:", str(e)[:80])
    return 0

if __name__ == "__main__":
    sys.exit(main())
