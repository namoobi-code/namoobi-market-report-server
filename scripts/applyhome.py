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
from collections import Counter, defaultdict
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


# 시도 정식명 → 짧은 이름 (공고의 SUBSCRPT_AREA_CODE_NM 과 표기를 맞춘다)
SD_SHORT = {"서울특별시": "서울", "부산광역시": "부산", "대구광역시": "대구", "인천광역시": "인천",
            "광주광역시": "광주", "대전광역시": "대전", "울산광역시": "울산",
            "세종특별자치시": "세종", "경기도": "경기", "강원특별자치도": "강원", "강원도": "강원",
            "충청북도": "충북", "충청남도": "충남", "전북특별자치도": "전북", "전라북도": "전북",
            "전라남도": "전남", "경상북도": "경북", "경상남도": "경남", "제주특별자치도": "제주"}


def load_umd():
    """법정동 → 실거래 시군구명 매핑 (umd_map.py 산출물).

    소스마다 시군구 쪼개는 방식이 달라(실거래는 화성을 봉담권/병점권/동탄으로 3분할,
    청약 주소는 2026 신설 일반구 표기) 그대로 두면 같은 지역이 서로 다른 이름으로 갈린다.
    실거래 기준으로 통일해야 두 카드의 지역 목록이 맞물린다.
    """
    p = BASE / "data" / "db" / "umd_map.json"
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        return d.get("map") or {}, d.get("map_sd") or {}
    except Exception:
        return {}, {}


UMD, UMD_SD = load_umd()


def parse_sgg(addr, fallback_sd):
    """공급위치 주소 → '시도 시군구'. 예) '경기도 용인시 처인구 역북동 …' → '경기 용인시 처인구'

    실측 주소 형식이 '시도 시군구 [자치구] 읍면동 …' 로 일정하다.
    창원·용인·수원 등 특례시는 '○○시 ○○구' 두 토큰을 합쳐야 실제 행정구역이 된다.
    """
    t = (addr or "").split()
    if len(t) < 2:
        return None
    sd = SD_SHORT.get(t[0])
    if not sd:
        return None
    if sd != fallback_sd and fallback_sd:      # 공고 지역과 주소 시도가 다르면 주소를 신뢰
        pass
    g = t[1]
    if not g.endswith(("시", "군", "구")):
        return None
    # ① 읍면동으로 실거래 시군구를 역조회 — 가장 정확하다.
    #    (화성처럼 실거래가 권역으로 쪼개는 곳도 여기서 정확히 맞춰진다)
    for tok in t[2:6]:
        if not tok.endswith(("동", "읍", "면", "리", "가")):
            continue
        hit = UMD_SD.get(f"{sd} {tok}") or UMD.get(tok)
        if hit:
            return hit if hit.startswith(sd) else f"{sd} {hit}"
    # ② 매핑 실패 시 주소 그대로 — 특례시의 일반구는 합쳐 준다
    if len(t) > 2 and g.endswith("시") and t[2].endswith("구"):
        g = f"{g} {t[2]}"
    return f"{sd} {g}"


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
            "sgg": parse_sgg(r.get("HSSPLY_ADRES"), r.get("SUBSCRPT_AREA_CODE_NM")),
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

    # 월별·지역별 가중평균 (총접수/총공급) — 시도 + 시군구 둘 다
    acc = defaultdict(lambda: defaultdict(lambda: [0.0, 0.0, 0]))  # ym → reg → [접수, 공급, 공고수]
    for a in done:
        for reg in (a["reg"], a.get("sgg"), "전국"):
            if not reg:
                continue
            x = acc[a["ym"]][reg]
            x[0] += a["req"]; x[1] += a["sup"]; x[2] += 1
    ts = sorted(acc)
    sido = [r for r in SIDO_ORDER if any(r in acc[t] for t in ts)]
    # 시군구는 공고가 3건 이상인 곳만(1~2건짜리는 노이즈)
    sgg_n = Counter()
    for t in ts:
        for r, x in acc[t].items():
            if " " in r:
                sgg_n[r] += x[2]
    sgg = [r for r, n in sgg_n.most_common() if n >= 3]
    regs = sido + sgg
    series = {r: [round(acc[t][r][0] / acc[t][r][1], 2)
                  if (r in acc[t] and acc[t][r][1]) else None for t in ts] for r in regs}
    cnt = {r: [(acc[t][r][2] if r in acc[t] else 0) or None for t in ts] for r in regs}

    recent = sorted(done, key=lambda a: a["de"], reverse=True)[:40]
    for a in recent:
        a.pop("req1", None)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "asof": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "src": "한국부동산원 청약홈 (data.go.kr)",
        "note": "경쟁률 = 총 청약건수 ÷ 총 공급세대. 월별·지역별은 가중평균(단지 단순평균이 아님)",
        "t": ts, "regions": regs, "sido": sido, "sgg": sgg,
        "n_pblanc": {r: sgg_n[r] for r in sgg},
        "series": series, "cnt": cnt,
        "recent": recent}, ensure_ascii=False), encoding="utf-8")
    n = series.get("전국") or []
    lv = next((f"{ts[i]} {v}:1" for i in range(len(n) - 1, -1, -1) if (v := n[i]) is not None), "—")
    print(f"[apply] ✅ 공고 {len(done):,}건 · {ts[0]}~{ts[-1]} · 지역 {len(regs)} · 최신 전국 {lv}")
    print(f"[apply] → {OUT}")


if __name__ == "__main__":
    main()
