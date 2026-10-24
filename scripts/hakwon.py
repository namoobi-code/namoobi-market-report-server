#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""hakwon.py — 동별 학원가 형성 신호 (NEIS 학원·교습소 개설현황) (2026-10-24 신설 · 월 1회 cron)

출발점: 매경LUXMEN 2026.10 '한국의 부촌' Part3 — "주민 구성이 바뀐 뒤 학원·병원이 따라온다".
  둔촌1동 학문·교육 점포 2022H1 3곳 → 2026H1 55곳(매출 1.9억→203억). 신축 입주 후 학원·병원이 실제로 늘고
  유지되는지가 '비싼 동네'가 '고소득 생활권'으로 넘어가는 보조 신호(김도훈 연구원).
  기사는 카드사 점포 데이터(유료) — 공개 대체재로 **NEIS 학원·교습소 개설현황**(설립일·분야·주소·정원)을 쓴다.
  ⚠ localdata.go.kr(인허가 원천)은 해외 IP 차단(샌드박스·서버 모두) — NEIS 는 키 발급 후 어디서나 열린다(2026-10-24 실측).

소스: https://open.neis.go.kr/hub/acaInsTiInfo?KEY=…&ATPT_OFCDC_SC_CODE=B10(서울)|J10(경기)&pSize=1000
  현재 '개원' 상태만 내려온다 → 설립연도 분포는 생존자 기준(폐원한 학원은 안 보임). 그래서 매달 동별 건수를 hist 에
  쌓아 앞으로는 진짜 순증(개원−폐원)이 보이게 한다.
  '학원가' = REALM_SC_NM 이 '입시.검정 및 보습' 또는 '국제화'(외국어) — 예능·직업기술·독서실은 제외(입지점수와 같은 정의).
  법정동 = FA_RDNDA 의 괄호 '(개포동, 삼성빌딩)' 에서 추출 · 시군구 = ADMST_ZONE_NM.

산출: data/db/hakwon.json
  {asof, src, note, years, dong:[{sido, sgg, dong, n(전체), hw(학원가), cap(학원가 정원), by:{연도:학원가 설립수}, l3(최근 3년 설립), l3p(비중%),
         med_y(설립연도 중앙값)}], sgg:[{sido, sgg, hw, l3, l3p}], hist:{YYYYMM:{"시도|시군구|동": hw}}}
cron: 20 9 3 * *
"""
import json, re, time, urllib.request
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "data" / "db" / "hakwon.json"
HW_REALM = ("입시.검정 및 보습", "국제화")
OFFICES = {"B10": "서울", "J10": "경기"}


def _key():
    for p in (BASE / "keys" / "neis.txt", BASE.parent / "SECURITY" / "open.neis.go.kr.txt", BASE.parent / "SECURITY" / "neis.txt"):
        if p.exists():
            m = re.search(r"[A-Za-z0-9]{20,}", p.read_text(encoding="utf-8"))
            if m:
                return m.group(0)
    raise SystemExit("NEIS 키 없음 — keys/neis.txt")


KEY = _key()


def fetch(office):
    rows, p = [], 1
    while True:
        u = f"https://open.neis.go.kr/hub/acaInsTiInfo?KEY={KEY}&Type=json&pIndex={p}&pSize=1000&ATPT_OFCDC_SC_CODE={office}"
        for k in range(3):
            try:
                d = json.load(urllib.request.urlopen(u, timeout=60))
                break
            except Exception as e:
                if k == 2:
                    print(f"  ⚠ {office} p{p} {e}")
                    return rows
                time.sleep(3)
        k0 = list(d)[0]
        if k0 == "RESULT":
            break
        cur = d[k0][1].get("row") or []
        rows += cur
        tot = int(d[k0][0]["head"][0]["list_total_count"])
        if len(rows) >= tot or not cur:
            break
        p += 1
        time.sleep(0.2)
    return rows


def dong_of(r):
    m = re.search(r"\(([가-힣0-9]+(?:동|가|읍|면|리))\b", r.get("FA_RDNDA") or "")
    if m:
        return m.group(1)
    m = re.search(r"\s([가-힣0-9]+(?:동|읍|면))\s", (r.get("FA_RDNMA") or "") + " ")
    return m.group(1) if m else None


def main():
    now = date.today()
    years = [str(y) for y in range(2010, now.year + 1)]
    D = defaultdict(lambda: {"n": 0, "hw": 0, "cap": 0, "by": defaultdict(int), "yrs": []})
    for off, sido in OFFICES.items():
        rows = fetch(off)
        print(f"[hakwon] {sido} {len(rows):,}건")
        for r in rows:
            if (r.get("REG_STTUS_NM") or "개원") != "개원":
                continue
            sgg = (r.get("ADMST_ZONE_NM") or "").strip()
            dong = dong_of(r)
            if not sgg or not dong:
                continue
            a = D[(sido, sgg, dong)]
            a["n"] += 1
            if r.get("REALM_SC_NM") in HW_REALM:
                a["hw"] += 1
                try:
                    a["cap"] += int(r.get("TOFOR_SMTOT") or 0)
                except Exception:
                    pass
                y = str(r.get("ESTBL_YMD") or "")[:4]
                if y.isdigit():
                    a["by"][y] += 1
                    a["yrs"].append(int(y))
    l3y = {str(now.year - i) for i in range(3)}
    dong = []
    for (sido, sgg, dg), a in D.items():
        if a["hw"] < 1:
            continue
        l3 = sum(v for y, v in a["by"].items() if y in l3y)
        ys = sorted(a["yrs"])
        dong.append({"sido": sido, "sgg": sgg, "dong": dg, "n": a["n"], "hw": a["hw"], "cap": a["cap"],
                     "by": {y: a["by"][y] for y in years if a["by"].get(y)}, "l3": l3,
                     "l3p": round(100 * l3 / a["hw"], 1), "med_y": ys[len(ys) // 2] if ys else None})
    dong.sort(key=lambda x: -x["hw"])
    S = defaultdict(lambda: {"hw": 0, "l3": 0, "n": 0})
    for x in dong:
        s = S[(x["sido"], x["sgg"])]
        s["hw"] += x["hw"]; s["l3"] += x["l3"]; s["n"] += x["n"]
    sgg = sorted([{"sido": k[0], "sgg": k[1], **v, "l3p": round(100 * v["l3"] / v["hw"], 1) if v["hw"] else 0} for k, v in S.items()], key=lambda x: -x["hw"])
    hist = {}
    if OUT.exists():
        try:
            hist = json.loads(OUT.read_text(encoding="utf-8")).get("hist") or {}
        except Exception:
            hist = {}
    hist[now.strftime("%Y%m")] = {f"{x['sido']}|{x['sgg']}|{x['dong']}": x["hw"] for x in dong}
    out = {"asof": datetime.now().strftime("%Y-%m-%d %H:%M"),
           "src": "교육부 NEIS 학원·교습소 개설현황 (open.neis.go.kr acaInsTiInfo) · 서울·경기 · 개원 상태만",
           "note": ("학원가 = 입시·검정·보습 + 국제화(외국어). 설립연도 분포는 현재 개원 중인 학원 기준(폐원분 제외 → 생존자 편향). "
                    "hist 에 매달 동별 건수를 쌓아 이후 순증을 본다. 법정동은 도로명 상세주소 괄호에서 추출."),
           "years": years, "l3y": sorted(l3y), "dong": dong, "sgg": sgg, "hist": hist}
    OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    top = sorted(dong, key=lambda x: -x["l3"])[:6]
    print(f"  → {OUT} ({OUT.stat().st_size//1024}KB) · 동 {len(dong)} · 학원가 {sum(x['hw'] for x in dong):,} · 최근3년 신설 상위: "
          + " · ".join(f"{x['sgg']} {x['dong']} {x['l3']}/{x['hw']}" for x in top))


if __name__ == "__main__":
    main()
