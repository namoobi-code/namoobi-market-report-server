#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""applyhome_rem.py — 무순위·잔여세대(줍줍) 공고 리스트 (2026-09-22 신설 · 매일 08:02 cron)

왜 따로인가: 청약홈 오픈API 는 일반 분양공고(getAPTLttotPblancDetail)와 **무순위/잔여세대**
(getRemndrLttotPblancDetail)를 다른 엔드포인트로 준다. applyhome_list.py 는 앞의 것만 받아서
'청약' 탭에 철산자이 더 헤리티지(무순위 4세대)·브리에르(불법행위 재공급 2세대) 같은 줍줍이
안 보였다(2026-09-22 사용자 지적). 이 스크립트가 뒤의 것을 받아 같은 방식으로 예상시세·차익을
붙인다.

소스 (data.go.kr odcloud · 2026-09-22 실측):
  ApplyhomeInfoDetailSvc/v1/getRemndrLttotPblancDetail  공고 마스터 — HOUSE_SECD 04 무순위 · 06 불법행위 재공급
                                                          (2025~ 592건: 무순위 502 · 재공급 90)
  ApplyhomeInfoDetailSvc/v1/getRemndrLttotPblancMdl     주택형별 공급세대·최고분양가 (cond[HOUSE_MANAGE_NO::GTE] 동작)
  ApplyhomeInfoCmpetRtSvc/v1/getRemndrLttotPblancCmpet  주택형별 접수건수·경쟁률 ('(△n)' = 미달)
  ※ 무순위 API 에는 규제지역 플래그(투기과열·조정)가 없다 → 10·15 대책(2025) 규제지역 목록으로 판정.

자격 규칙(표시용 · 확정은 공고 원문):
  · 규제지역(서울 전역 + 경기 12: 과천·광명·의왕·하남·성남 분당/수정/중원·수원 영통/장안/팔달·안양 동안·용인 수지)
    무순위 → 해당 지역 거주 **무주택세대구성원**(거주 범위는 시·군 또는 시·도 — 공고별 상이) · 통장 불필요 · 재당첨 제한
  · 비규제 무순위 → 성년이면 거주지·주택 소유 무관(2023.2.28~) · 통장 불필요 (공고에 따라 제한 가능)
  · 불법행위 재공급 → 해당 시·군 거주 무주택 (최초 공고 당시 자격 준용)

예상시세·차익: applyhome_list.py 의 load_ppsm/act_price/silv_price/est_price 를 그대로 가져다 쓴다.
  줍줍은 대부분 준공·입주 단지라 **단지 자체 실거래(실측)** 매칭이 잘 걸린다 — 철산자이 브리에르 등.

산출: data/db/applyhome_rem.json {asof, src, note, sido, items[공고]}
"""
import json, re, sys, time, urllib.request
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE / "scripts"))
from applyhome_list import (KEY, API, PER, fetch_all, num, ival, ty_area, parse_lvl2, parse_dong,  # noqa: E402
                            sane_pr, load_ppsm, sgg_codes, act_price, est_price, silv_price)

OUT = BASE / "data" / "db" / "applyhome_rem.json"
BACK_DAYS = 400
SINCE_DE = (date.today() - timedelta(days=BACK_DAYS)).isoformat()
SINCE_NO = SINCE_DE[:4] + "000000"

# 10·15 대책(2025.10.16~) 투기과열·조정대상 — 서울 전역 + 경기 12곳 (시·구 단위)
REG_GG = {"과천시", "광명시", "의왕시", "하남시"}
REG_GG_GU = {("성남시", ("분당구", "수정구", "중원구")), ("수원시", ("영통구", "장안구", "팔달구")),
             ("안양시", ("동안구",)), ("용인시", ("수지구",))}


def regulated(reg, addr):
    if reg == "서울":
        return True
    if reg != "경기":
        return False
    t = (addr or "").split()
    city = t[1] if len(t) > 1 else ""
    gu = t[2] if len(t) > 2 else ""
    if city in REG_GG:
        return True
    for c, gus in REG_GG_GU:
        if city == c and gu in gus:
            return True
    return False


def elig(secd, regd, reg, sgg):
    if secd == "06":
        return f"{reg} {sgg or ''} 거주 무주택 (재공급·최초 공고 자격 준용)".replace("  ", " ")
    if regd:
        return f"규제지역 — {reg} 거주 무주택세대구성원 (거주 범위 시·군/시·도는 공고 확인)"
    return "비규제 — 성년이면 거주지·주택 소유 무관 (공고별 제한 가능)"


def main():
    c_no = f"&cond%5BHOUSE_MANAGE_NO%3A%3AGTE%5D={SINCE_NO}"
    c_de = f"&cond%5BRCRIT_PBLANC_DE%3A%3AGTE%5D={SINCE_DE}"
    print(f"[rem] 수집 시작 — 공고일 {SINCE_DE} 이후")
    pb = fetch_all("ApplyhomeInfoDetailSvc/v1/getRemndrLttotPblancDetail", "무순위공고", c_de)
    md = fetch_all("ApplyhomeInfoDetailSvc/v1/getRemndrLttotPblancMdl", "주택형", c_no)
    cp = fetch_all("ApplyhomeInfoCmpetRtSvc/v1/getRemndrLttotPblancCmpet", "경쟁률", c_no)
    if not pb or not md:
        print("[rem] ❌ 수집 실패 — 저장 생략")
        return
    K = lambda r: (str(r.get("HOUSE_MANAGE_NO") or "").strip(), str(r.get("HOUSE_TY") or "").strip())
    cmpet = {}
    for r in cp:
        cmpet[K(r)] = {"req": ival(r.get("REQ_CNT")), "sup": ival(r.get("SUPLY_HSHLDCO")),
                       "short": "△" in str(r.get("CMPET_RATE") or "")}
    mdl = defaultdict(list)
    for r in md:
        mdl[str(r.get("HOUSE_MANAGE_NO") or "").strip()].append(r)

    REG, PPSM, APTS, ASALE = load_ppsm()
    SILV = {}
    silv_f = BASE / "data" / "db" / "silv.json"
    if silv_f.exists():
        SILV = json.loads(silv_f.read_text(encoding="utf-8")).get("data", {})

    items, sido = [], set()
    for r in pb:
        no = str(r.get("HOUSE_MANAGE_NO") or "").strip()
        if not no or no not in mdl:
            continue
        reg = r.get("SUBSCRPT_AREA_CODE_NM") or ""
        addr = r.get("HSSPLY_ADRES") or ""
        sgg = parse_lvl2(addr)
        codes = sgg_codes(REG, reg, sgg) if REG else []
        secd = str(r.get("HOUSE_SECD") or "")
        regd = regulated(reg, addr)
        name = r.get("HOUSE_NM")
        tys, prs, gv = [], [], []
        for m in sorted(mdl[no], key=lambda x: str(x.get("HOUSE_TY") or "")):
            ht = str(m.get("HOUSE_TY") or "").strip()
            ar = ty_area(ht)
            gen, spc = ival(m.get("SUPLY_HSHLDCO")), ival(m.get("SPSPLY_HSHLDCO"))
            pr = num(m.get("LTTOT_TOP_AMOUNT"))
            pr = sane_pr(round(pr / 10000, 2), ar) if pr else None
            if pr:
                prs.append(pr)
            est = estb = cmpn = dg = 0
            act = slv = None
            if pr:
                est, estb, cmpn, dg = est_price(PPSM, codes, ar, APTS, ASALE, parse_dong(addr))
                # 줍줍은 대개 준공·입주 단지 — 공고의 입주예정월이 미래(잔여세대 입주 시점)라도
                # 단지 자체 실거래가 있으면 실측을 쓴다. act_price 의 '미입주면 건너뜀'을 우회하려고
                # 연도만 남긴 과거 월(YYYY01)을 넘긴다(준공년 ±1 검사는 그대로 유효).
                mvn = str(r.get("MVN_PREARNGE_YM") or "")[:4]
                act = act_price(APTS, ASALE, codes, name, (mvn + "01") if mvn else None, ar)
                slv = silv_price(SILV, codes, name, ar) if not act else None
                if act:
                    est, estb, cmpn, dg = act, 0, 0, 0
                elif slv:
                    est, estb, cmpn, dg = slv, 0, 0, 0
            t = {"t": ht, "ar": ar, "pr": pr, "gen": gen, "spc": spc, "est": est or None, "estb": estb,
                 "act": 1 if act else 0, "slv": 1 if slv else 0, "cmp": cmpn, "dg": dg}
            c = cmpet.get((no, ht))
            if c and (c["req"] or c["sup"]):
                t["req"] = c["req"]
                t["rt"] = round(c["req"] / (gen + spc), 2) if (gen + spc) else None
                if c["short"]:
                    t["short"] = 1
            if est and pr:
                gv.append((est - pr, (gen + spc) or 1, pr))
            tys.append({k: v for k, v in t.items() if v not in (None, 0, [])})
        gain = gpct = None
        if gv:
            W = sum(x[1] for x in gv)
            gain = sum(x[0] * x[1] for x in gv) / W
            base = sum(x[2] * x[1] for x in gv) / W
            gain, gpct = round(gain, 1), (round(gain / base * 100) if base else None)
        sido.add(reg)
        it = {"no": no, "name": name, "secd": secd, "kind": r.get("HOUSE_SECD_NM"),
              "reg": reg, "sgg": sgg, "addr": addr, "regd": 1 if regd else 0,
              "elig": elig(secd, regd, reg, sgg),
              "url": r.get("PBLANC_URL"), "hmpg": r.get("HMPG_ADRES"), "biz": r.get("BSNS_MBY_NM"),
              "sup": ival(r.get("TOT_SUPLY_HSHLDCO")),
              "de": str(r.get("RCRIT_PBLANC_DE") or "")[:10],
              "sp_bg": str(r.get("SPSPLY_RCEPT_BGNDE") or "")[:10],
              "rc_bg": str(r.get("SUBSCRPT_RCEPT_BGNDE") or "")[:10],
              "rc_ed": str(r.get("SUBSCRPT_RCEPT_ENDDE") or "")[:10],
              "prz": str(r.get("PRZWNER_PRESNATN_DE") or "")[:10],
              "ctr": str(r.get("CNTRCT_CNCLS_BGNDE") or "")[:10],
              "mvn": r.get("MVN_PREARNGE_YM"),
              "pr": [min(prs), max(prs)] if prs else None,
              "gain": gain, "gpct": gpct, "ty": tys}
        items.append({k: v for k, v in it.items() if v not in (None, "", [])})

    items.sort(key=lambda x: x.get("rc_bg") or x.get("de") or "", reverse=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "asof": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "src": "한국부동산원 청약홈 무순위/잔여세대 (data.go.kr) · 매일 08:02 갱신",
        "note": ("무순위·불법행위 재공급 공고. 자격은 규칙 기반 표시(규제지역: 10·15 대책 서울 전역+경기 12곳) — "
                 "확정 자격·거주 범위·실거주 의무는 공고 원문 확인. 예상시세는 단지 자체 실거래(실측) 우선."),
        "since": SINCE_DE,
        "sido": [s for s in ["서울", "경기", "인천", "부산", "대구", "광주", "대전", "울산", "세종", "강원",
                             "충북", "충남", "전북", "전남", "경북", "경남", "제주"] if s in sido],
        "items": items}, ensure_ascii=False), encoding="utf-8")
    up = sum(1 for i in items if (i.get("rc_ed") or "") >= date.today().isoformat())
    print(f"[rem] ✅ 공고 {len(items):,}건 (접수예정·접수중 {up}건) → {OUT} ({OUT.stat().st_size//1024}KB)")


if __name__ == "__main__":
    main()
