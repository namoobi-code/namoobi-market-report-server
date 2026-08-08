#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""applyhome.py — 청약홈 분양정보·청약경쟁률 (2026-08-08 신설 · 매일 07:55 cron).

소스: data.go.kr 한국부동산원 청약홈 (odcloud) — 2026-08-08 활용신청 후 실측 확인
  ApplyhomeInfoDetailSvc/v1/getAPTLttotPblancDetail   APT 분양공고   (2,842건)
  ApplyhomeInfoCmpetRtSvc/v1/getAPTLttotPblancCmpet   APT 청약경쟁률 (54,186건)

왜 중요한가: 실거래가는 계약이 끝난 뒤에 잡히는 **후행** 지표지만,
청약경쟁률은 수요자가 지금 얼마나 달려드는지를 보여주는 **선행** 지표다.

집계 방식
  · 경쟁률 원자료는 (공고 × 주택형 × 순위 × 거주지역) 단위라 그대로 합치면 중복된다.
    - 단지 경쟁률 = 총 청약건수(REQ_CNT 합) / 총 공급세대(공고의 TOT_SUPLY_HSHLDCO)
    - 1순위 경쟁률 = 1순위 접수 합 / 총 공급세대   ← 통상 언론이 쓰는 수치
    - 최고 경쟁률 = 주택형별 CMPET_RATE 최댓값
  · 월별·지역별 시계열은 **가중평균**(총접수 합 / 총공급 합) — 단지 단순평균은 소형단지에 휘둘린다.

산출: data/db/applyhome.json {asof, months, regions, series{지역:[경쟁률]}, recent[공고 40건]}
"""
import json, sys, time, urllib.request
from collections import defaultdict
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "data" / "db" / "applyhome.json"
KEY = (BASE / "keys" / "data.go.kr.txt").read_text().strip()
API = "https://api.odcloud.kr/api"
PER = 1000

SIDO_ORDER = ["전국", "서울", "경기", "인천", "부산", "대구", "광주", "대전", "울산", "세종",
              "강원", "충북", "충남", "전북", "전남", "경북", "경남", "제주"]


def fetch_all(path, label):
    rows, page = [], 1
    while True:
        u = f"{API}/{path}?page={page}&perPage={PER}&serviceKey={KEY}"
        for k in range(4):
            try:
                d = json.loads(urllib.request.urlopen(u, timeout=60).read())
                break
            except Exception as e:
                if k == 3:
                    print(f"  ⚠ {label} p{page} 실패: {e}")
                    return rows
                time.sleep(4 * (k + 1))
        cur = d.get("data") or []
        rows += cur
        tot = d.get("totalCount") or 0
        print(f"    {label} {len(rows):,}/{tot:,}", flush=True)
        if not cur or len(rows) >= tot:
            break
        page += 1
        time.sleep(0.4)
    return rows


def num(x):
    try:
        return float(str(x).replace(",", "").strip())
    except Exception:
        return None


def main():
    print("[apply] 분양공고 수집")
    pb = fetch_all("ApplyhomeInfoDetailSvc/v1/getAPTLttotPblancDetail", "공고")
    print("[apply] 청약경쟁률 수집")
    cp = fetch_all("ApplyhomeInfoCmpetRtSvc/v1/getAPTLttotPblancCmpet", "경쟁률")
    if not pb or not cp:
        print("[apply] ❌ 수집 실패 — 저장 생략")
        return

    # 공고 마스터
    info = {}
    for r in pb:
        no = str(r.get("HOUSE_MANAGE_NO") or "").strip()
        if not no:
            continue
        de = str(r.get("RCRIT_PBLANC_DE") or "")[:10]
        info[no] = {
            "name": r.get("HOUSE_NM"), "reg": r.get("SUBSCRPT_AREA_CODE_NM"),
            "de": de, "ym": de.replace("-", "")[:6],
            "sup": num(r.get("TOT_SUPLY_HSHLDCO")) or 0,
            "kind": r.get("HOUSE_SECD_NM"), "rent": r.get("RENT_SECD_NM"),
            "addr": r.get("HSSPLY_ADRES"), "url": r.get("PBLANC_URL"),
            "biz": r.get("BSNS_MBY_NM"), "cons": r.get("CNSTRCT_ENTRPS_NM"),
            "req": 0, "req1": 0, "top": None,
        }
    # 경쟁률 집계
    for r in cp:
        no = str(r.get("HOUSE_MANAGE_NO") or "").strip()
        a = info.get(no)
        if not a:
            continue
        q = num(r.get("REQ_CNT")) or 0
        a["req"] += q
        if str(r.get("SUBSCRPT_RANK_CODE") or "") == "1":
            a["req1"] += q
        c = num(r.get("CMPET_RATE"))
        if c is not None and (a["top"] is None or c > a["top"]):
            a["top"] = c

    done = [a for a in info.values() if a["sup"] and a["req"] and a["ym"]]
    for a in done:
        a["rate"] = round(a["req"] / a["sup"], 2)
        a["rate1"] = round(a["req1"] / a["sup"], 2) if a["req1"] else None

    # 월별·지역별 가중평균 (총접수/총공급)
    acc = defaultdict(lambda: defaultdict(lambda: [0.0, 0.0]))     # ym → reg → [접수, 공급]
    for a in done:
        for reg in (a["reg"], "전국"):
            if not reg:
                continue
            acc[a["ym"]][reg][0] += a["req"]
            acc[a["ym"]][reg][1] += a["sup"]
    ts = sorted(acc)
    regs = [r for r in SIDO_ORDER if any(r in acc[t] for t in ts)]
    series = {r: [round(acc[t][r][0] / acc[t][r][1], 2)
                  if (r in acc[t] and acc[t][r][1]) else None for t in ts] for r in regs}
    cnt = {r: [len([a for a in done if a["ym"] == t and (a["reg"] == r or r == "전국")]) or None
               for t in ts] for r in regs}

    recent = sorted(done, key=lambda a: a["de"], reverse=True)[:40]
    for a in recent:
        a.pop("req1", None)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "asof": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "src": "한국부동산원 청약홈 (data.go.kr)",
        "note": "경쟁률 = 총 청약건수 ÷ 총 공급세대. 월별·지역별은 가중평균(단지 단순평균이 아님)",
        "t": ts, "regions": regs, "series": series, "cnt": cnt,
        "recent": recent}, ensure_ascii=False), encoding="utf-8")
    n = series.get("전국") or []
    lv = next((f"{ts[i]} {v}:1" for i in range(len(n) - 1, -1, -1) if (v := n[i]) is not None), "—")
    print(f"[apply] ✅ 공고 {len(done):,}건 · {ts[0]}~{ts[-1]} · 지역 {len(regs)} · 최신 전국 {lv}")
    print(f"[apply] → {OUT}")


if __name__ == "__main__":
    main()
