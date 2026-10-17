#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fin_quality.py — 재무 건전성 2종: 이자보상배율(ICR)·영업현금흐름/영업이익 (2026-10-17 신설)

왜: 한경MONEY 2026-10 김학균 "저금리 40년 끝났다 — 업종보다 기업의 질": 재무건전성 4대 지표(영업활동현금흐름·부채비율·
    이자보상배율·FCF) 중 부채비율·FCF 는 스크리너에 있었고 **ICR·OCF 가 없었다**. 좀비기업(영업이익으로 이자도 못 갚는 회사)과
    '이익은 흑자인데 현금은 적자'(매출채권·재고 급증)를 걸러내는 데 필요.
어떻게: OpenDART fnlttSinglAcntAll(단일회사 전체 재무제표) 최신 사업보고서(11011) 연결(CFS)→개별(OFS) 폴백.
    영업이익 = dart_OperatingIncomeLoss, 영업활동현금흐름 = ifrs-full_CashFlowsFromUsedInOperatingActivities,
    이자비용 우선순위 = IS ifrs-full_InterestExpense > CF 이자의 지급(InterestPaidClassifiedAsOperatingActivities)
                    > ifrs-full_FinanceCosts(⚠ 외환손실 포함이라 과대 — 삼성전자 실측 금융비용 11.7조 vs 이자지급 0.47조, 최후 폴백만).
    연 1회만 바뀌는 데이터라 (corp, 사업연도) 캐시 — 첫 실행 ~2,500콜(일 한도 2만), 이후엔 새 사업보고서 나온 종목만.
산출: data/db/fin_quality.json  { as_of, year, rows: {code: {yr, op, ie, ocf, icr, ocfop, fs, src}} }
    icr = 영업이익/이자비용 (이자비용 0·미공시면 None, 영업적자면 음수 그대로) · ocfop = OCF/영업이익 (영업이익>0 일 때만)
cron: 30 8 * * 0  (dps_hist 08:00 뒤, 주 1회)  · screener_pool.py 가 매일 빌드 시 병합.
"""
import json, time, urllib.request, sys
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "data" / "db" / "fin_quality.json"
CACHE = BASE / "data" / "watch" / "fin_quality_cache.json"
KEY = (BASE / "keys" / "opendart.txt").read_text().strip()
CORPMAP = BASE / "data" / "watch" / "dart_corp_map.json"

IDS = {
    "op": ("IS", ["dart_OperatingIncomeLoss"]),
    "ocf": ("CF", ["ifrs-full_CashFlowsFromUsedInOperatingActivities"]),
    "ie_is": ("IS", ["ifrs-full_InterestExpense", "dart_InterestExpenseFinanceCosts"]),
    "ie_cf": ("CF", ["ifrs-full_InterestPaidClassifiedAsOperatingActivities", "ifrs-full_InterestPaidClassifiedAsFinancingActivities"]),
    "fc": ("IS", ["ifrs-full_FinanceCosts"]),
}


def num(s):
    try:
        return int(str(s).replace(",", "").strip())
    except Exception:
        return None


def pull(corp, year, fs):
    u = (f"https://opendart.fss.or.kr/api/fnlttSinglAcntAll.json?crtfc_key={KEY}&corp_code={corp}"
         f"&bsns_year={year}&reprt_code=11011&fs_div={fs}")
    j = json.loads(urllib.request.urlopen(u, timeout=30).read())
    if j.get("status") != "000":
        return None
    got = {}
    for x in j.get("list") or []:
        aid, sj, nm = x.get("account_id", ""), x.get("sj_div", ""), x.get("account_nm", "")
        v = num(x.get("thstrm_amount"))
        if v is None:
            continue
        # (2026-10-17 실측) 손익계산서를 단일 포괄손익계산서로 내는 회사(SK하이닉스 등 전체의 ~90%)는 sj_div 가 'CIS' —
        #   'IS' 만 보면 영업이익이 안 잡혀 2,078종 중 1,907종이 '데이터 없음'으로 캐시됐다. IS·CIS 둘 다 받는다.
        sjn = "IS" if sj in ("IS", "CIS") else sj
        for k, (div, ids) in IDS.items():
            if sjn == div and aid in ids and k not in got:
                got[k] = v
        # 계정ID 가 표준이 아닌 회사 — 계정명으로 보조 매칭(이자의 지급 등)
        if "ie_cf" not in got and sj == "CF" and nm.replace(" ", "") in ("이자의지급", "이자지급", "이자지급액"):
            got["ie_cf"] = v
        if "ie_is" not in got and sjn == "IS" and nm.replace(" ", "") in ("이자비용",):
            got["ie_is"] = v
    return got or None


def main():
    pool = json.loads((BASE / "data" / "db" / "screener_pool.json").read_text(encoding="utf-8"))
    codes = [r["c"] for r in pool.get("kr") or []]
    mp = json.loads(CORPMAP.read_text(encoding="utf-8")).get("map", {})
    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    now = datetime.now()
    # 최신 사업보고서 연도: 4월 이후면 전년, 그 전엔 전전년(3월 말 제출)
    year = now.year - 1 if now.month >= 4 else now.year - 2
    rows, n_call, n_new = {}, 0, 0
    for i, c in enumerate(codes):
        corp = mp.get(c)
        if not corp:
            continue
        ck = f"{c}:{year}"
        if ck in cache:
            rows[c] = cache[ck]
            continue
        rec = None; failed = False
        for fs in ("CFS", "OFS"):
            try:
                got = pull(corp, year, fs); n_call += 1
            except Exception as e:
                # (2026-10-17 실측) 2,800콜 넘자 DART 가 응답을 지연시켜(SYN 후 무응답 → 30s 타임아웃) 건당 1분씩 걸렸다.
                #   타임아웃을 '데이터 없음'으로 캐시하면 그 종목은 영영 비므로 — 실패는 캐시하지 않고 다음 주 재시도. 속도도 늦춘다.
                got = None; failed = True; time.sleep(3)
            if got and "op" in got:
                ie, src = None, None
                for k in ("ie_is", "ie_cf", "fc"):
                    if got.get(k) is not None and got[k] > 0:
                        ie, src = abs(got[k]), k; break
                op, ocf = got.get("op"), got.get("ocf")
                rec = {"yr": year, "fs": fs, "op": op, "ie": ie, "ocf": ocf, "src": src,
                       "icr": (round(op / ie, 1) if (ie and op is not None) else None),
                       "ocfop": (round(ocf / op, 2) if (ocf is not None and op and op > 0) else None)}
                break
            time.sleep(0.4)
        if rec or not failed:
            cache[ck] = rec if rec else {"yr": year, "none": True}   # 실패(타임아웃)는 캐시하지 않는다
        if rec:
            rows[c] = rec; n_new += 1
        if n_call and n_call % 200 == 0:
            CACHE.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
            print(f"  … {i+1}/{len(codes)} 호출 {n_call}", flush=True)
    CACHE.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    OUT.write_text(json.dumps({"as_of": now.strftime("%Y-%m-%d %H:%M"), "year": year, "rows": rows}, ensure_ascii=False), encoding="utf-8")
    ic = [r["icr"] for r in rows.values() if r.get("icr") is not None]
    print(f"[finq] ✅ {len(rows)}종목(신규 {n_new}·호출 {n_call}) · ICR 보유 {len(ic)} · ICR<1 {sum(1 for v in ic if v < 1)} → {OUT}", flush=True)


if __name__ == "__main__":
    main()
