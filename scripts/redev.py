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
import json, urllib.request
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

# 진행단계 표준 순서 — 뒤로 갈수록 사업 확정성↑ (차트 정렬·전환 방향 판정에 사용)
ORDER = ["정비계획 수립", "정비구역지정", "안전진단", "추진위구성", "추진위원회승인",
         "조합원 모집신고", "조합창립총회", "조합규약작성", "조합설립인가",
         "지구단위계획수립/건축심의/교통심의", "사업계획승인", "사업시행인가",
         "관리처분인가", "분양", "철거", "철거 및 착공", "착공", "준공인가",
         "이전고시", "조합청산", "청산 및 조합해산", "조합해산"]
RANK = {s: i for i, s in enumerate(ORDER)}
# 이 단계에 진입하면 '사업 진척' 신호로 강조 표시
KEY_STAGES = {"조합설립인가", "사업시행인가", "관리처분인가", "착공", "준공인가"}


def fetch():
    req = urllib.request.Request(URL, headers=UA)
    raw = urllib.request.urlopen(req, timeout=90).read()
    sh = xlrd.open_workbook(file_contents=raw).sheet_by_index(0)
    rows = []
    for r in range(2, sh.nrows):                       # 0=빈행, 1=헤더
        g = lambda c: str(sh.cell_value(r, c)).strip()
        nm = g(3)
        if not nm:
            continue
        rows.append({"gu": g(1), "kind": g(2), "name": nm, "addr": g(4),
                     "stage": g(5), "op": g(6), "opstage": g(7)})
    return rows


def main():
    try:
        rows = fetch()
    except Exception as e:
        print(f"[redev] ❌ 수집 실패: {e} — 저장 생략(기존 파일 보존)")
        return
    if len(rows) < 100:
        print(f"[redev] ❌ 행 수 비정상({len(rows)}) — 페이지 구조 변경 의심, 저장 생략")
        return
    today = datetime.now().strftime("%Y-%m-%d")

    # ── 단계 전환 감지 (전일 스냅샷 대비) ──
    key = lambda a: f"{a['gu']}|{a['name']}"
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

    # ── 집계 ──
    gu = defaultdict(Counter)
    for a in rows:
        gu[a["gu"]][a["stage"]] += 1
    stages = [s for s in ORDER if any(s in c for c in gu.values())]
    for c in gu.values():                               # 표준목록 밖 단계도 뒤에 붙임
        for s in c:
            if s and s not in stages:
                stages.append(s)
    kinds = Counter(a["kind"] for a in rows)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "asof": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "src": "서울 클린업시스템(정비사업 정보몽땅) · 무인증",
        "note": "단계 전환은 전일 스냅샷과 비교해 감지 — 수집 시작일 이후부터 쌓인다",
        "n": len(rows), "stages": stages,
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
