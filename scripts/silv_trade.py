#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""silv_trade.py — 국토부 아파트 분양권 전매 실거래 (2026-08-16 신설 · 매일 07:40 cron).

왜: 미입주 단지(완료 공고·잔여세대 등)는 매매 실거래가 없어 예상시세를 주변 신축으로
추정할 수밖에 없다 → 분양권 전매 실거래(프리미엄 반영)가 있으면 그 단지의 '실측'이 된다.
청약 탭 예상시세 우선순위: 입주 후 매매 실측 > 분양권 실측 > 주변 신축 추정.

소스: data.go.kr RTMSDataSvcSilvTrade (XML) — 2026-08-16 활용신청 승인 실측.
      필드: aptNm, dealAmount(만원), excluUseAr, umdNm, cdealType(해제 'O'), dealYear/Month
지역: rtms.py REGIONS 전체 · 기본 최근 6개월 (--months N)
산출: data/db/silv.json {asof, months, data: {sgg: [[정규화단지명, 전용반올림, 평균억, n]…]}}
"""
import json, re, sys, time, urllib.request
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rtms import REGIONS

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "data" / "db" / "silv.json"
KEY = (BASE / "keys" / "data.go.kr.txt").read_text().strip()
MONTHS = int(sys.argv[sys.argv.index("--months") + 1]) if "--months" in sys.argv else 6


def months_list(n):
    d = date.today().replace(day=1)
    out = []
    for _ in range(n):
        out.append(d.strftime("%Y%m"))
        d = (d - timedelta(days=1)).replace(day=1)
    return out


def main():
    yms = months_list(MONTHS)
    acc = defaultdict(lambda: [0.0, 0])           # (sgg, norm명, ar반올림) → [합(억), n]
    calls = fails = rows = 0
    for sgg in REGIONS:
        for ym in yms:
            u = (f"https://apis.data.go.kr/1613000/RTMSDataSvcSilvTrade/"
                 f"getRTMSDataSvcSilvTrade?serviceKey={KEY}&LAWD_CD={sgg}"
                 f"&DEAL_YMD={ym}&numOfRows=800")
            calls += 1
            try:
                x = urllib.request.urlopen(u, timeout=30).read()
                for it in ET.fromstring(x).iter("item"):
                    g = lambda k: (it.findtext(k) or "").strip()
                    if g("cdealType") == "O":     # 해제 거래 제외
                        continue
                    amt = float(g("dealAmount").replace(",", "") or 0) / 1e4
                    ar = float(g("excluUseAr") or 0)
                    nm = re.sub(r"[^0-9A-Za-z가-힣]", "", g("aptNm").lower())
                    if amt <= 0 or ar < 20 or len(nm) < 3:
                        continue
                    k = (sgg, nm, round(ar))
                    acc[k][0] += amt
                    acc[k][1] += 1
                    rows += 1
            except Exception:
                fails += 1
            time.sleep(0.15)
    data = defaultdict(list)
    for (sgg, nm, ar), (s, n) in acc.items():
        data[sgg].append([nm, ar, round(s / n, 2), n])
    OUT.write_text(json.dumps({
        "asof": date.today().isoformat(), "months": yms,
        "data": data}, ensure_ascii=False), encoding="utf-8")
    print(f"[silv] ✅ 호출 {calls}(실패 {fails}) · 거래 {rows:,}건 · "
          f"단지·면적 {len(acc):,}키 · {len(data)}개 시군구 → {OUT}")


if __name__ == "__main__":
    main()
