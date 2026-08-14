#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""rtms_etc.py — 비(非)아파트 실거래 5종 (2026-08-08 신설 · 매일 07:50 cron).

소스: data.go.kr 국토부 실거래가 — 아파트와 같은 1613000 계열, 전부 자동승인.
      (2026-08-08 활용신청 완료 후 실측으로 6개 엔드포인트 전부 200 확인)

  offi_s  오피스텔 매매   RTMSDataSvcOffiTrade  dealAmount·excluUseAr·offiNm
  offi_r  오피스텔 전월세 RTMSDataSvcOffiRent   deposit·monthlyRent   ← 전월세전환율 산출용
  rh      연립다세대 매매 RTMSDataSvcRHTrade    dealAmount·excluUseAr
  sh      단독다가구 매매 RTMSDataSvcSHTrade    dealAmount·totalFloorAr
  land    토지 매매       RTMSDataSvcLandTrade  dealAmount·dealArea·jimok
  nrg     상업업무용 매매 RTMSDataSvcNrgTrade   dealAmount·buildingAr·buildingUse

설계
  · 원자료는 시군구-월 단위로 SQLite 에 적재(재개 가능) → 출력 JSON 은 시도로 집계.
    아파트(rtms.py)와 같은 이유로 중단·재개가 잦아 done 표식이 필수다.
  · 429(레이트리밋)는 즉시 포기하지 않고 길게 기다렸다 재시도한다(아파트 백필과 동일 정책).
  · 해제거래(cdealType='O') 제외.

사용: rtms_etc.py [--months N] [--full] [--budget N] [--sleep S]
      기본 최근 3개월 갱신 · --full 은 --months 60 과 동일(5년)
"""
import json, sqlite3, sys, time, urllib.request, urllib.error
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rtms import REGIONS, SIDO                      # 시군구 목록·시도 접두사 재사용
import apt_db                                       # 단지별 시계열(오피스텔·연립다세대)도 함께 적재

BASE = Path(__file__).resolve().parent.parent
DB = BASE / "data" / "db" / "rtms_etc.sqlite"
OUT = BASE / "data" / "db" / "rtms_etc.json"
KEY = (BASE / "keys" / "data.go.kr.txt").read_text().strip()

ARG = lambda k, d: (int(sys.argv[sys.argv.index(k) + 1]) if k in sys.argv else d)
MONTHS = 60 if "--full" in sys.argv else ARG("--months", 3)
BUDGET = ARG("--budget", 500000)
SLEEP = float(sys.argv[sys.argv.index("--sleep") + 1]) if "--sleep" in sys.argv else 0.45
CALLS = 0


class _Stop(Exception):
    pass


class _Quota(Exception):
    """이 서비스의 **일일** 요청제한이 소진됨 — 오늘은 이 유형만 건너뛰고 나머지는 계속한다."""


# (2026-08-08) data.go.kr 은 활용신청 건(=유형)마다 일일 호출 한도가 따로 있다.
# 예전엔 토지 한도가 소진되면 fetch 가 최대 1시간씩 자며 전체 수집을 붙잡아
# 서울·부산 28곳에서 더 나아가지 못했다(사용자: "전지역 확인이 안된다").
# → 한도 소진 유형은 DEAD 에 넣고 즉시 건너뛴다. 한도는 자정(KST)에 리셋된다.
DEAD = set()


# key: (서비스, 오퍼레이션, 금액필드, 면적필드)
KINDS = {
    "offi_s": ("RTMSDataSvcOffiTrade", "getRTMSDataSvcOffiTrade", "dealAmount", "excluUseAr"),
    "offi_r": ("RTMSDataSvcOffiRent", "getRTMSDataSvcOffiRent", None, "excluUseAr"),
    "rh":     ("RTMSDataSvcRHTrade", "getRTMSDataSvcRHTrade", "dealAmount", "excluUseAr"),
    "sh":     ("RTMSDataSvcSHTrade", "getRTMSDataSvcSHTrade", "dealAmount", "totalFloorAr"),
    "nrg":    ("RTMSDataSvcNrgTrade", "getRTMSDataSvcNrgTrade", "dealAmount", "buildingAr"),
    # (2026-08-14) 토지는 **맨 마지막**. 이유 두 가지 —
    #   ① 한 실행의 --budget(호출 예산)은 6종이 함께 쓴다. 토지는 (시군구·월)당 거래건수가
    #      많아 페이지가 여러 장 나오므로 다른 5종보다 호출을 훨씬 많이 먹는다.
    #      실측 2026-08-14: 토지 9.2% vs 나머지 5종 90.6~90.9% — 같은 예산을 토지가 삼켰다.
    #   ② 대시보드가 실제로 쓰는 건 주거·상업용이고 토지는 참고 지표다.
    # dict 순서가 곧 수집 순서라 여기 위치가 우선순위다. + LAND_LAST 로 아예 미룬다.
    "land":   ("RTMSDataSvcLandTrade", "getRTMSDataSvcLandTrade", "dealAmount", "dealArea"),
}
# 나머지 5종이 사실상 끝나기 전에는 토지를 건드리지 않는다(--land-now 로 무시 가능).
LAND_LAST = "--land-now" not in sys.argv
LABEL = {"offi_s": "오피스텔 매매", "offi_r": "오피스텔 전월세", "rh": "연립다세대",
         "sh": "단독다가구", "land": "토지", "nrg": "상업업무용"}
# 전월세전환율 주의: 전세 평균보증금과 월세 평균보증금이 '서로 다른 매물군'의 평균이라
# 공식 통계(한국부동산원, 동일 단지·유형 매칭)보다 낮게 나온다. 수준값보다 추세로 읽을 것.
CONV_NOTE = ("전세·월세 각각의 평균으로 계산한 <b>근사치</b> — 두 표본이 같은 매물이 아니라 "
             "공식 통계(부동산원)보다 낮게 나온다. 절대수준보다 <b>방향·추세</b>로 볼 것")

SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS agg(
  kind TEXT, sgg TEXT, ym TEXT,
  n INTEGER, amt REAL, med REAL, ar REAL,      -- amt=평균 거래금액(억) · ar=평균 면적(㎡)
  n2 INTEGER, amt2 REAL, rent REAL,            -- 전월세 전용: 월세 건수·평균보증금·평균월세
  PRIMARY KEY(kind, sgg, ym)
) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS done(kind TEXT, sgg TEXT, ym TEXT, PRIMARY KEY(kind,sgg,ym)) WITHOUT ROWID;
"""


def months_back(n):
    y, m, out = datetime.now().year, datetime.now().month, []
    for _ in range(n):
        out.append(f"{y}{m:02d}")
        m -= 1
        if m == 0:
            y -= 1; m = 12
    return out[::-1]


def fetch(svc, op, lawd, ym):
    global CALLS
    rows, page = [], 1
    while True:
        CALLS += 1
        if CALLS > BUDGET:
            raise _Stop("호출 예산 소진")
        u = (f"https://apis.data.go.kr/1613000/{svc}/{op}"
             f"?serviceKey={KEY}&LAWD_CD={lawd}&DEAL_YMD={ym}&numOfRows=1000&pageNo={page}")
        if svc in DEAD:
            raise _Quota(svc)
        root = None
        try:
            root = ET.fromstring(urllib.request.urlopen(u, timeout=30).read())
        except urllib.error.HTTPError as he:
            if he.code != 429:
                return rows
            try:
                body = he.read().decode("utf-8", "replace")
            except Exception:
                body = ""
            if "일일" in body or "LIMITED_NUMBER_OF_SERVICE_REQUESTS" in body:
                DEAD.add(svc)
                raise _Quota(svc)
            # 429 는 대개 몇 분이면 풀린다. 예전 사다리는 첫 대기가 60초·다음이 300초라
            # 이미 풀린 뒤에도 30분씩 자고 있었다(실측: 제한 해제 상태로 4분 넘게 sleep).
            # → 짧게 자주 두드리고, 무엇을 하는 중인지 로그로 남긴다.
            for w in (10, 20, 40, 90, 180, 300, 600, 900, 1800, 1800, 3600):
                print(f"    ⏳ 429 — {w}초 대기 후 재시도 ({svc} {lawd} {ym})", flush=True)
                time.sleep(w)
                try:
                    root = ET.fromstring(urllib.request.urlopen(u, timeout=30).read())
                    print("    ✔ 429 해제 — 재개", flush=True)
                    break
                except Exception:
                    continue
            if root is None:
                raise _Stop("HTTP 429 지속 — 장기 대기 후에도 미해제")
        except Exception:
            time.sleep(2)
            try:
                root = ET.fromstring(urllib.request.urlopen(u, timeout=30).read())
            except Exception:
                return rows
        rc = (root.findtext(".//resultCode") or "").strip()
        if rc == "22":                       # 200 으로 오는 일일 한도 초과 — 이 유형만 중단
            DEAD.add(svc)
            raise _Quota(svc)
        if rc not in ("000", "00"):
            return rows
        items = root.findall(".//item")
        rows += [{e.tag: (e.text or "").strip() for e in it} for it in items]
        if page * 1000 >= int(root.findtext(".//totalCount") or 0) or not items:
            break
        page += 1
    return rows


def f(s):
    try:
        return float(str(s).replace(",", ""))
    except Exception:
        return None


def med(xs):
    xs = sorted(xs); n = len(xs)
    return xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2


def agg(kind, rows):
    """→ (n, 평균금액억, 중위금액억, 평균면적, 월세건수, 월세평균보증금, 월세평균월세)"""
    _, _, amt_f, ar_f = KINDS[kind]
    if kind == "offi_r":                                   # 전세 / 월세 분리
        je, wo_d, wo_r = [], [], []
        for r in rows:
            d, m = f(r.get("deposit")), f(r.get("monthlyRent")) or 0
            if d is None:
                continue
            (je if m == 0 else wo_d).append(d / 10000)
            if m:
                wo_r.append(m)
        if not je and not wo_d:
            return None
        return (len(je), round(sum(je) / len(je), 3) if je else None,
                round(med(je), 3) if je else None, None,
                len(wo_d), round(sum(wo_d) / len(wo_d), 3) if wo_d else None,
                round(sum(wo_r) / len(wo_r), 1) if wo_r else None)
    px, ar = [], []
    for r in rows:
        if (r.get("cdealType") or "") == "O":
            continue
        v = f(r.get(amt_f))
        if v:
            px.append(v / 10000)                            # 만원 → 억
            a = f(r.get(ar_f))
            if a:
                ar.append(a)
    if not px:
        return None
    return (len(px), round(sum(px) / len(px), 3), round(med(px), 3),
            round(sum(ar) / len(ar), 2) if ar else None, None, None, None)


def build_json(cx):
    """시군구 적재분 → 시도·전국 집계 JSON (프론트가 이걸 읽는다)."""
    pre = {c: c[:2] for c in REGIONS}
    out = {}
    for kind in KINDS:
        rows = cx.execute("SELECT sgg,ym,n,amt,med,ar,n2,amt2,rent FROM agg WHERE kind=?",
                          (kind,)).fetchall()
        if not rows:
            continue
        acc = {}                                            # {ym: {region: [n, n*amt, n2, n2*amt2, n2*rent]}}
        for sgg, ym, n, amt, m_, ar, n2, amt2, rent in rows:
            sd = SIDO.get(pre.get(sgg, ""), None)
            if not sd:
                continue
            # (2026-08-08) 시군구 계열도 함께 — 지역 선택기가 시도·시군구를 같이 훑는다.
            # 이름에 시도가 없는 도 단위("수원 장안구")는 앞에 붙여 검색되게 한다.
            nm = REGIONS.get(sgg, sgg)
            sub = nm if nm.startswith(sd) else f"{sd} {nm}"
            for reg in (sd, sub, "전국"):
                a = acc.setdefault(ym, {}).setdefault(reg, [0, 0.0, 0, 0.0, 0.0])
                if n:
                    a[0] += n
                    if amt is not None:
                        a[1] += n * amt
                if n2:
                    a[2] += n2
                    if amt2 is not None:
                        a[3] += n2 * amt2
                    if rent is not None:
                        a[4] += n2 * rent
        ts = sorted(acc)
        SD_SET = set(SIDO.values()) | {"전국"}
        regs = sorted({r for t in ts for r in acc[t]},
                      key=lambda r: (r not in SD_SET, r))     # 시도 먼저, 그 다음 시군구
        g = lambda r, i, d: [(acc[t].get(r) or [0, 0, 0, 0, 0])[i] if t in acc else None for t in ts]
        o = {"label": LABEL.get(kind, kind), "t": ts,
             "sido": [r for r in regs if r in SD_SET],
             "sgg": [r for r in regs if r not in SD_SET],
             "n": {r: [(acc[t].get(r) or [0])[0] or None for t in ts] for r in regs},
             "avg": {r: [round((acc[t][r][1] / acc[t][r][0]), 3)
                         if (t in acc and r in acc[t] and acc[t][r][0]) else None for t in ts]
                     for r in regs}}
        if kind == "offi_r":                                # 월세 계열 + 전월세전환율
            o["wol_n"] = {r: [(acc[t].get(r) or [0, 0, 0])[2] or None for t in ts] for r in regs}
            o["wol_dep"] = {r: [round(acc[t][r][3] / acc[t][r][2], 3)
                                if (t in acc and r in acc[t] and acc[t][r][2]) else None
                                for t in ts] for r in regs}
            o["wol_rent"] = {r: [round(acc[t][r][4] / acc[t][r][2], 1)
                                 if (t in acc and r in acc[t] and acc[t][r][2]) else None
                                 for t in ts] for r in regs}
            # 전월세전환율(%) = 월세×12 / (전세보증금 − 월세보증금) × 100
            conv = {}
            for r in regs:
                v = []
                for i, t in enumerate(ts):
                    je = o["avg"][r][i]; wd = o["wol_dep"][r][i]; wr = o["wol_rent"][r][i]
                    gap = (je - wd) if (je is not None and wd is not None) else None
                    v.append(round(wr * 12 / 10000 / gap * 100, 2)
                             if (gap and gap > 0 and wr) else None)
                conv[r] = v
            o["conv"] = conv
            o["conv_note"] = CONV_NOTE
        out[kind] = o
    return out


def main():
    DB.parent.mkdir(parents=True, exist_ok=True)
    cx = sqlite3.connect(DB, timeout=180)
    cx.execute("PRAGMA busy_timeout=180000")
    cx.executescript(SCHEMA)
    acx = apt_db.connect(etc=True); acache = {}   # 단지별 DB — 비아파트 전용 파일(락 충돌 회피)
    yms = months_back(MONTHS)
    recent = set(months_back(3))
    stopped = None
    # (2026-08-08) 수집 순서 = 법정동코드 오름차순이라 서울(11)·부산(26) 다음에야 경기(41)가
    #   나온다. 지역당 6종×N개월이라 한 바퀴가 길어서 경기·인천이 하염없이 밀린다.
    #   → 수도권(서울·경기·인천)을 앞으로 당긴다. done 표식 기반이라 순서를 바꿔도 안전하다.
    PRIOR = {"11": 0, "41": 1, "28": 2, "26": 3}
    order = sorted(REGIONS.items(), key=lambda kv: (PRIOR.get(kv[0][:2], 9), kv[0]))
    # (2026-08-14) 토지 보류 판정 — 나머지 5종이 목표의 99% 를 넘어야 토지를 시작한다.
    skip_land = False
    if LAND_LAST:
        tgt = len(REGIONS) * len(yms)
        cnt = {k: cx.execute("SELECT COUNT(*) FROM done WHERE kind=?", (k,)).fetchone()[0]
               for k in KINDS}
        others = {k: v for k, v in cnt.items() if k != "land"}
        lo = min(others.values()) if others else 0
        if lo < tgt * 0.99:
            skip_land = True
            worst = min(others, key=others.get)
            print(f"  ⏸ 토지 보류 — 나머지 5종 중 '{LABEL[worst]}' 가 {lo:,}/{tgt:,}"
                  f"({100*lo/tgt:.1f}%) 라 예산을 먼저 쓴다. 5종이 99% 넘으면 자동으로 시작한다"
                  f" (지금 바로 받으려면 --land-now). 토지 현재 {cnt['land']:,}/{tgt:,}", flush=True)
    try:
        for i, (code, name) in enumerate(order):
            got = 0
            for kind, (svc, op, _, _) in KINDS.items():
                if kind == "land" and skip_land:
                    continue
                if svc in DEAD:
                    continue
                try:
                  for ym in reversed(yms):                    # 최신 → 과거
                     if ym not in recent and cx.execute(
                             "SELECT 1 FROM done WHERE kind=? AND sgg=? AND ym=?",
                             (kind, code, ym)).fetchone():
                         continue
                     raw = fetch(svc, op, code, ym)
                     # (2026-08-08) 같은 응답으로 단지별 시계열도 적재 — 추가 호출 0회.
                     # 국토부가 건물명을 주는 오피스텔·연립다세대만 가능(단독·토지·상업용은 미제공).
                     # 유형별 식별 가능 수준(실측 2026-08-08):
                     #   오피스텔·연립다세대 = 건물명 / 상업업무용 = 법정동+지번(62%)
                     #   단독다가구·토지 = 전부 마스킹 → 법정동 단위
                     K2 = {"offi_s": ("offi", "offiNm"), "offi_r": ("offi", "offiNm"),
                           "rh": ("rh", "mhouseNm"), "sh": ("sh", ""),
                           "land": ("land", ""), "nrg": ("nrg", "")}
                     if kind in K2:
                         k2, nf = K2[kind]
                         try:
                             if kind == "offi_r":
                                 apt_db.ingest_rent(acx, code, ym, raw, acache, k2, nf)
                             else:
                                 apt_db.ingest_sale(acx, code, ym, raw, acache, k2, nf)
                             acx.commit()      # 잠금 구간 최소화
                         except Exception as e:
                             print(f"    ⚠ 단지DB 적재 실패({kind} {code} {ym}): {e}")
                     a = agg(kind, raw)
                     if a:
                         cx.execute("INSERT OR REPLACE INTO agg"
                                    "(kind,sgg,ym,n,amt,med,ar,n2,amt2,rent)"
                                    " VALUES(?,?,?,?,?,?,?,?,?,?)", (kind, code, ym, *a))
                         got += 1
                     cx.execute("INSERT OR REPLACE INTO done(kind,sgg,ym) VALUES(?,?,?)",
                                (kind, code, ym))
                     time.sleep(SLEEP)
                except _Quota:
                    print(f"  \u26d4 {LABEL[kind]} 일일 요청제한 소진 — 오늘은 건너뛴다", flush=True)
            cx.commit(); acx.commit()
            print(f"  [{i+1}/{len(REGIONS)}] {name}: {got}건 적재 (누적호출 {CALLS:,})", flush=True)
            if (i + 1) % 10 == 0:
                OUT.write_text(json.dumps({"asof": datetime.now().strftime("%Y-%m-%d %H:%M"),
                                           "src": "국토교통부 실거래가 (data.go.kr)",
                                           "types": build_json(cx)}, ensure_ascii=False),
                               encoding="utf-8")
                print(f"      💾 중간 저장 ({i+1}지역)", flush=True)
    except _Stop as e:
        stopped = str(e)
        print(f"  ⚠ {stopped} — 진행분 저장 후 종료")
    cx.commit(); acx.commit()
    OUT.write_text(json.dumps({"asof": datetime.now().strftime("%Y-%m-%d %H:%M"),
                               "src": "국토교통부 실거래가 (data.go.kr) · 시군구 집계 → 시도",
                               "types": build_json(cx)}, ensure_ascii=False), encoding="utf-8")
    d = json.loads(OUT.read_text(encoding="utf-8"))["types"]
    for k, v in d.items():
        print(f"[etc] ✅ {k:7s} {v['label']:8s} {len(v['t'])}개월 {v['t'][0]}~{v['t'][-1]}")
    print(f"[etc] 호출 {CALLS:,}회 → {OUT}")
    print(f"[etc] 단지DB {apt_db.stats(acx)}")
    acx.close(); cx.close()


if __name__ == "__main__":
    main()
