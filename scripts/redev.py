#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""redev.py — 서울 재개발·재건축 정비사업 추진현황 (2026-08-08 신설 · 매일 08:05 cron).

소스: 서울 클린업시스템(정비사업 정보몽땅) — **로그인·인증 불필요** (실측 2026-08-08)
      https://cleanup.seoul.go.kr/cleanup/bsnssttus/lsubBsnsSttusExcel.do
      → 전 사업장(1,147건)이 담긴 .xls 한 방에 내려온다(페이징 불필요).
      컬럼: 번호·자치구·사업구분·사업장명·대표지번·진행단계·운영구분·운영단계·공개자료수·적시성·충실도

왜 선행지표인가
  정비사업은 "정비구역지정 → 추진위 → 조합설립 → 사업시행인가 → 관리처분인가 →
  이주·철거 → 착공 → 준공"의 단계를 밟는다. 각 단계 통과가 곧 향후 3~10년 공급 일정이자
  해당 구역 가격의 촉매다. 특히 **관리처분인가**는 사업 확정성이 급등하는 분기점.

핵심 기능
  ① 자치구 × 진행단계 스냅샷 (스택바용)
  ② **단계 전환 감지** — 전일 스냅샷과 비교해 단계가 바뀐 사업장을 뽑아 누적 기록.
     이게 이 수집기의 진짜 값어치다(현황보다 '변화'가 신호).

산출: data/db/redev.json  · 이전 스냅샷: data/db/redev_prev.json (비교용, 프론트 미사용)
"""
import csv, io, json, time, urllib.request
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

try:
    import xlrd
except ImportError:
    raise SystemExit("xlrd 필요: pip3 install --break-system-packages xlrd")

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "data" / "db" / "redev.json"
PREV = BASE / "data" / "db" / "redev_prev.json"
URL = "https://cleanup.seoul.go.kr/cleanup/bsnssttus/lsubBsnsSttusExcel.do"
UA = {"User-Agent": "Mozilla/5.0 (namoobi market terminal)"}

# (2026-08-08) 지역마다 같은 단계를 다르게 부른다(서울 '조합설립인가' = 경기 '조합설립',
# '사업시행인가' = '사업시행계획인가' …). 그대로 두면 46종으로 흩어져 지역 비교가 불가능하다.
# → 표준 13단계로 정규화하고 원문(stage_raw)은 따로 보존한다.
ORDER = ["후보지", "정비계획", "정비구역지정", "안전진단", "추진위원회", "조합설립인가",
         "건축심의", "사업시행인가", "관리처분인가", "분양", "착공·철거", "준공",
         "이전고시", "청산·해산", "해제"]
RANK = {s: i for i, s in enumerate(ORDER)}
NORM = {
    "예정구역": "정비계획", "예정구역지정": "정비계획", "정비계획 수립": "정비계획",
    "정비계획 수립 및 정비구역 지정": "정비계획",
    "후보지 1차": "후보지", "후보지 2차": "후보지",
    "후보지 1차(추진위승인)": "추진위원회", "후보지 2차(추진위승인)": "추진위원회",
    "정비구역": "정비구역지정", "정비구역지정(추진위승인)": "추진위원회",
    "추진위원회승인": "추진위원회", "추진위원회 구성": "추진위원회", "추진위구성": "추진위원회",
    "추진위원회 승인": "추진위원회", "조합원 모집신고": "추진위원회",
    "조합창립총회": "추진위원회", "조합규약작성": "추진위원회",
    "조합설립": "조합설립인가",
    "건축심의 및 통합심의": "건축심의", "지구단위계획수립/건축심의/교통심의": "건축심의",
    "사업시행": "사업시행인가", "사업시행계획인가": "사업시행인가",
    "사업계획승인": "사업시행인가", "사업시행자지정(신탁사)": "사업시행인가",
    "관리처분": "관리처분인가", "관리처분계획": "관리처분인가", "관리처분계획인가": "관리처분인가",
    "철거": "착공·철거", "착공": "착공·철거", "철거 및 착공": "착공·철거",
    "착공(부분준공)": "착공·철거",
    "준공인가": "준공", "조합해산": "청산·해산", "조합청산": "청산·해산",
    "청산": "청산·해산", "청산 및 조합해산": "청산·해산",
}
def norm_stage(s):
    s = (s or "").strip()
    return NORM.get(s, s if s in RANK else (s or "기타"))
# 이 단계에 진입하면 '사업 진척' 신호로 강조 표시
KEY_STAGES = {"조합설립인가", "사업시행인가", "관리처분인가", "착공·철거", "준공"}


def fetch():
    """서울 — 클린업시스템 전체 엑셀(무인증)."""
    req = urllib.request.Request(URL, headers=UA)
    raw = urllib.request.urlopen(req, timeout=90).read()
    sh = xlrd.open_workbook(file_contents=raw).sheet_by_index(0)
    rows = []
    for r in range(2, sh.nrows):                       # 0=빈행, 1=헤더
        g = lambda c: str(sh.cell_value(r, c)).strip()
        nm = g(3)
        if not nm:
            continue
        rows.append({"sd": "서울", "gu": g(1), "kind": g(2), "name": nm, "addr": g(4),
                     "stage": g(5), "op": g(6), "opstage": g(7)})
    return rows


def _get(u, headers=None, timeout=60, tries=3):
    for k in range(tries):
        try:
            return urllib.request.urlopen(
                urllib.request.Request(u, headers={**UA, **(headers or {})}), timeout=timeout).read()
        except Exception as e:
            if k == tries - 1:
                raise
            time.sleep(3 * (k + 1))


def fetch_gg():
    """경기 — 경기데이터드림 OpenAPI. 서울보다 컬럼이 훨씬 많다(사업단계·세대수·일정).
    ※ Referer 헤더가 없으면 WAF 가 EUC-KR 오류 HTML 로 막는다(실측 2026-08-08)."""
    key = (BASE / "keys" / "data.gg.go.kr.txt")
    if not key.exists():
        print("    · 경기 건너뜀(키 없음: keys/data.gg.go.kr.txt)")
        return []
    K = key.read_text(encoding="utf-8").strip()
    hdr = {"Referer": "https://data.gg.go.kr/"}
    out, page = [], 1
    while page <= 10:
        u = (f"https://openapi.gg.go.kr/GenrlimprvBizpropls?KEY={K}&Type=json"
             f"&pIndex={page}&pSize=1000")
        try:
            d = json.loads(_get(u, hdr))
        except Exception as e:
            print(f"    ⚠ 경기 p{page} 실패: {e}")
            break
        blk = d.get("GenrlimprvBizpropls")
        if not blk or len(blk) < 2:
            break
        rows = blk[1].get("row") or []
        for r in rows:
            nm = str(r.get("IMPRV_ZONE_NM") or "").strip()
            if not nm:
                continue
            out.append({"sd": "경기", "gu": str(r.get("SIGUN_NM") or "").strip(),
                        "kind": str(r.get("BIZ_TYPE_NM") or "").strip(), "name": nm,
                        "addr": str(r.get("LOCPLC_ADDR") or "").strip(),
                        "stage": str(r.get("BIZ_STEP_NM") or "").strip(),
                        "op": str(r.get("BIZ_IMPLMNTR_NM") or "").strip(), "opstage": "",
                        "hh": r.get("BIZ_IMPLMTN_HSHLD_CNT_TOTSUM"),
                        "ar": r.get("ZONE_AR")})
        total = 0
        try:
            total = int(blk[0]["head"][0]["list_total_count"])
        except Exception:
            pass
        if len(rows) < 1000 or (total and len(out) >= total):
            break
        page += 1
        time.sleep(0.5)
    return out


def fetch_ic():
    """인천 — data.go.kr 파일데이터 CSV(무인증). 컬럼은 6개로 서울보다 적다."""
    u = ("https://www.data.go.kr/cmm/cmm/fileDownload.do"
         "?atchFileId=FILE_000000003675032&fileDetailSn=1&insertDataPrcus=N")
    try:
        raw = _get(u)
    except Exception as e:
        print(f"    ⚠ 인천 실패: {e}")
        return []
    for enc in ("cp949", "utf-8-sig", "utf-8"):
        try:
            txt = raw.decode(enc)
            break
        except Exception:
            txt = None
    if not txt:
        return []
    out = []
    for r in csv.DictReader(io.StringIO(txt)):
        k = {(c or "").replace(" ", ""): (v or "").strip() for c, v in r.items()}
        nm = k.get("구역명") or ""
        if not nm:
            continue
        out.append({"sd": "인천", "gu": k.get("구명", ""), "kind": k.get("사업유형", ""),
                    "name": nm, "addr": k.get("위치", ""), "stage": k.get("진행단계", ""),
                    "op": "", "opstage": "", "ar": k.get("면적(제곱미터)")})
    return out


def fetch_bs():
    """부산 — data.go.kr 3069406 (자동승인). step 이 사업추진단계."""
    key = (BASE / "keys" / "data.go.kr.txt")
    if not key.exists():
        return []
    K = key.read_text(encoding="utf-8").strip()
    out, page = [], 1
    while page <= 10:
        u = ("https://apis.data.go.kr/6260000/MaintenanceBusinessStatus1/getMaintenanceBusiness1"
             f"?serviceKey={K}&numOfRows=500&pageNo={page}&resultType=json")
        try:
            d = json.loads(_get(u))
        except Exception as e:
            print(f"    ⚠ 부산 p{page} 실패: {e}")
            break
        body = list(d.values())[0] if isinstance(d, dict) else {}
        items = (body.get("body") or body).get("items") or []
        if isinstance(items, dict):
            items = items.get("item") or []
        if not isinstance(items, list):
            items = [items]
        if not items:
            break
        for r in items:
            if not isinstance(r, dict):
                continue
            nm = str(r.get("areaName") or "").strip()
            if not nm:
                continue
            loc = str(r.get("location") or "").strip()
            out.append({"sd": "부산", "gu": loc.split()[0] if loc else "",
                        "kind": (nm.split()[-1] if " " in nm else ""),
                        "name": nm, "addr": loc,
                        "stage": str(r.get("step") or "").strip(),
                        "op": str(r.get("businessEntities") or "").strip(), "opstage": "",
                        "hh": r.get("generationJoo"), "ar": r.get("areaUnit")})
        if len(items) < 500:
            break
        page += 1
        time.sleep(0.4)
    return out


def main():
    try:
        rows = fetch()
    except Exception as e:
        print(f"[redev] ❌ 서울 수집 실패: {e} — 저장 생략(기존 파일 보존)")
        return
    if len(rows) < 100:
        print(f"[redev] ❌ 서울 행 수 비정상({len(rows)}) — 페이지 구조 변경 의심, 저장 생략")
        return
    print(f"    · 서울 {len(rows):,}건")
    # (2026-08-08) 서울 외 지역 확장 — 지자체마다 시스템이 달라 소스도 제각각이다.
    for nm, fn in (("경기", fetch_gg), ("인천", fetch_ic), ("부산", fetch_bs)):
        try:
            add = fn()
            print(f"    · {nm} {len(add):,}건")
            rows += add
        except Exception as e:
            print(f"    ⚠ {nm} 수집 실패(건너뜀): {e}")
    for a in rows:                                   # 지역별 표기 차이를 표준 단계로 통일
        a["stage_raw"] = a.get("stage", "")
        a["stage"] = norm_stage(a.get("stage"))
    today = datetime.now().strftime("%Y-%m-%d")

    # ── 단계 전환 감지 (전일 스냅샷 대비) ──
    key = lambda a: f"{a.get('sd','')}|{a['gu']}|{a['name']}"
    cur = {key(a): a["stage"] for a in rows}
    prev, changes = {}, []
    try:
        p = json.loads(PREV.read_text(encoding="utf-8"))
        prev = p.get("map") or {}
    except Exception:
        pass
    if prev:
        idx = {key(a): a for a in rows}
        for k, st in cur.items():
            old = prev.get(k)
            if old and old != st:
                a = idx[k]
                ro, rn = RANK.get(old, -1), RANK.get(st, -1)
                changes.append({"de": today, "gu": a["gu"], "name": a["name"],
                                "kind": a["kind"], "addr": a["addr"],
                                "from": old, "to": st,
                                "fwd": (rn > ro) if (ro >= 0 and rn >= 0) else None,
                                "key": st in KEY_STAGES})
        for k, st in cur.items():                       # 신규 등재
            if k not in prev:
                a = idx[k]
                changes.append({"de": today, "gu": a["gu"], "name": a["name"],
                                "kind": a["kind"], "addr": a["addr"],
                                "from": None, "to": st, "fwd": None,
                                "key": st in KEY_STAGES})

    # 기존 변경 이력에 누적 (최근 300건 유지)
    hist = []
    try:
        hist = (json.loads(OUT.read_text(encoding="utf-8")) or {}).get("changes") or []
    except Exception:
        pass
    hist = (changes + [h for h in hist if h.get("de") != today])[:300]

    # ── 집계 ── (자치구 키에 시도를 붙여 동명 구 구분: 서울 중구 / 부산 중구)
    gu = defaultdict(Counter)
    for a in rows:
        g = f"{a.get('sd','')} {a['gu']}".strip()
        gu[g][a["stage"]] += 1
    sd_cnt = Counter(a.get("sd", "") for a in rows)
    stages = [s for s in ORDER if any(s in c for c in gu.values())]
    for c in gu.values():                               # 표준목록 밖 단계도 뒤에 붙임
        for s in c:
            if s and s not in stages:
                stages.append(s)
    kinds = Counter(a["kind"] for a in rows)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "asof": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "src": "서울 클린업시스템(무인증) · 경기 경기데이터드림 · 인천 data.go.kr(무인증) · 부산 data.go.kr",
        "note": ("단계 전환은 전일 스냅샷과 비교해 감지 — 수집 시작일 이후부터 쌓인다. "
                 "지역마다 운영 시스템이 달라 단계 명칭·상세도가 조금씩 다르다"),
        "n": len(rows), "stages": stages, "sd": dict(sd_cnt.most_common()),
        "key_stages": sorted(KEY_STAGES, key=lambda s: RANK.get(s, 99)),
        "gu": {g: dict(c) for g, c in sorted(gu.items())},
        "kinds": dict(kinds.most_common()),
        "changes": hist,
        "list": sorted(rows, key=lambda a: (-RANK.get(a["stage"], -1), a["gu"]))[:400],
    }, ensure_ascii=False), encoding="utf-8")
    PREV.write_text(json.dumps({"de": today, "map": cur}, ensure_ascii=False), encoding="utf-8")

    top = Counter(a["stage"] for a in rows).most_common(4)
    print(f"[redev] ✅ {len(rows):,}건 · 자치구 {len(gu)} · 단계 {len(stages)}종")
    print(f"[redev]    상위단계 {', '.join(f'{k} {v}' for k, v in top)}")
    print(f"[redev]    오늘 단계전환 {len(changes)}건 · 누적 이력 {len(hist)}건")
    print(f"[redev] → {OUT}")


if __name__ == "__main__":
    main()
