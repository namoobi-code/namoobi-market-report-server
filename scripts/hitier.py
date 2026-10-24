#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""hitier.py — 고가 아파트 거래 집중도·신축 분해 (2026-10-24 신설 · 매일 08:08 cron)

출발점: 매경LUXMEN 2026.10 커버스토리 '한국의 부촌' Part 2 (빅밸류 100m 격자·공시가 분석).
  ① "20억 문턱은 한강 따라 넓어졌지만 50억 넘으면 83%가 강남3구" — 가격이 높을수록 좁아진다
  ② "5년간 고가주택 증가율 동대문 +1,295%·강서 +925%" 인데 동대문은 신축 86%, 강서는 신축 1.8%
     — 같은 증가율이라도 '새 아파트가 들어온 것'과 '옛 집값이 오른 것'은 다르다
기사는 공시가·시세(빅밸류 유료) 기준이라 그대로 못 쓰고, 우리 실거래 DB(apt.sqlite · rtms.py)로
**실거래 기준**으로 매달 다시 계산한다 → 기사가 한 장이라면 여기선 '문턱이 넓어지는지 좁아지는지'가 시계열로 보인다.

데이터: data/db/apt.sqlite  sale(apt_id, ym, ar, n, avg, med, mn, mx · 억) · apt(sgg, umd, name, build_year)
  ⚠ sale 은 (단지·월·전용) 집계라 개별 거래가 없다 → 그 집계의 평균가(avg)로 n건을 한꺼번에 분류한다.
    같은 달 같은 면적 거래는 가격이 비슷해 큰 왜곡은 없지만, 경계(20억 근처)에서는 ±몇 건 흔들린다.
  ⚠ 서울 2021~2022 는 거래 자체가 급감한 시기(실측 2022 1.2만 건) — 비율은 표본이 작을 때 튄다.

산출: data/db/hitier.json
  q:[YYYYQn] · tiers:[12,20,30,50]
  conc: {tier: {q: {all, gn3, hr, gn3_pct, hr_pct}}}   서울 전체 거래 중 강남3구·한강벨트 비중 (분기)
  gu:  {구: {n12, t20, t30, t50, p20, p30, p50, new5, new10, old, med84, up5(12억+ 5년 증가율), n12_ago, newshare_ago}}
  by_year: {구: {year: {n, t12, t20, new5share_of_t20}}}
cron: 8 8 * * *
"""
import json, sqlite3
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DB = BASE / "data" / "db" / "apt.sqlite"
OUT = BASE / "data" / "db" / "hitier.json"
TIERS = (12, 20, 30, 50)
GN3 = {"11680": "강남구", "11650": "서초구", "11710": "송파구"}
HR = {"11170": "용산구", "11200": "성동구", "11440": "마포구", "11590": "동작구", "11470": "양천구",
      "11560": "영등포구", "11215": "광진구", "11740": "강동구"}          # 한강벨트(기사 분류)
GU = {"11110": "종로구", "11140": "중구", "11170": "용산구", "11200": "성동구", "11215": "광진구", "11230": "동대문구",
      "11260": "중랑구", "11290": "성북구", "11305": "강북구", "11320": "도봉구", "11350": "노원구", "11380": "은평구",
      "11410": "서대문구", "11440": "마포구", "11470": "양천구", "11500": "강서구", "11530": "구로구", "11545": "금천구",
      "11560": "영등포구", "11590": "동작구", "11620": "관악구", "11650": "서초구", "11680": "강남구", "11710": "송파구",
      "11740": "강동구"}


def q_of(ym):
    return f"{ym[:4]}Q{(int(ym[4:6]) - 1) // 3 + 1}"


def main():
    cx = sqlite3.connect(DB)
    now = date.today()
    ym_now = now.strftime("%Y%m")
    ym12 = (now.replace(day=1).replace(year=now.year - 1)).strftime("%Y%m")
    rows = cx.execute("SELECT a.sgg, s.ym, s.ar, s.n, s.avg, a.build_year FROM sale s JOIN apt a ON a.id=s.apt_id "
                      "WHERE a.sgg LIKE '11%' AND s.ym>='200601' AND s.n>0 AND s.avg>0").fetchall()
    cx.close()
    print(f"[hitier] 서울 집계행 {len(rows):,}")

    # ① 분기별 집중도
    conc = {t: defaultdict(lambda: {"all": 0, "gn3": 0, "hr": 0}) for t in TIERS}
    tot_q = defaultdict(int)
    for sgg, ym, ar, n, avg, by in rows:
        q = q_of(ym)
        tot_q[q] += n
        for t in TIERS:
            if avg >= t:
                c = conc[t][q]
                c["all"] += n
                if sgg in GN3:
                    c["gn3"] += n
                if sgg in HR:
                    c["hr"] += n
    qs = sorted(tot_q)
    cur_q = q_of(ym_now)
    conc_out = {}
    for t in TIERS:
        conc_out[str(t)] = {}
        for q in qs:
            c = conc[t].get(q)
            if not c or not c["all"]:
                continue
            conc_out[str(t)][q] = {"all": c["all"], "gn3": c["gn3"], "hr": c["hr"],
                                   "gn3_pct": round(100 * c["gn3"] / c["all"], 1), "hr_pct": round(100 * c["hr"] / c["all"], 1),
                                   "share": round(100 * c["all"] / tot_q[q], 2)}      # 전체 거래 중 그 가격대 비중

    # ② 구별 최근 12개월 + 신축 분해 + 5년 전 비교
    yr = now.year
    gu = {}
    byy = defaultdict(lambda: defaultdict(lambda: {"n": 0, "t12": 0, "t20": 0, "new5_20": 0}))
    acc = defaultdict(lambda: {"n12": 0, "t20": 0, "t30": 0, "t50": 0, "new5": 0, "new10": 0, "old": 0,
                               "p84": [], "n_ago": 0, "t12_ago": 0, "t12_now": 0, "new5_ago": 0, "new5_now": 0})
    ago0, ago1 = f"{yr-5}01", f"{yr-5}{now.month:02d}"       # 5년 전 같은 1~M월 vs 올해 1~M월
    now0 = f"{yr}01"
    for sgg, ym, ar, n, avg, by in rows:
        if sgg not in GU:
            continue
        a = acc[sgg]
        age = (int(ym[:4]) - by) if by else None
        y = ym[:4]
        b = byy[sgg][y]
        b["n"] += n
        if avg >= 12:
            b["t12"] += n
        if avg >= 20:
            b["t20"] += n
            if age is not None and age <= 5:
                b["new5_20"] += n
        if ym12 <= ym <= ym_now:
            a["n12"] += n
            for t, k in ((20, "t20"), (30, "t30"), (50, "t50")):
                if avg >= t:
                    a[k] += n
            if avg >= 20:
                if age is None:
                    pass
                elif age <= 5:
                    a["new5"] += n
                elif age <= 10:
                    a["new10"] += n
                else:
                    a["old"] += n
            if 80 <= ar <= 90:
                a["p84"].append((avg, n))
        if ago0 <= ym <= ago1:
            a["n_ago"] += n
            if avg >= 12:
                a["t12_ago"] += n
                if age is not None and age <= 5:
                    a["new5_ago"] += n
        if now0 <= ym <= ym_now:
            if avg >= 12:
                a["t12_now"] += n
                if age is not None and age <= 5:
                    a["new5_now"] += n
    for sgg, a in acc.items():
        n = a["n12"] or 1
        t20 = a["t20"]
        w = sum(k for _, k in a["p84"])
        gu[GU[sgg]] = {
            "n12": a["n12"], "t20": t20, "t30": a["t30"], "t50": a["t50"],
            "p20": round(100 * t20 / n, 1), "p30": round(100 * a["t30"] / n, 1), "p50": round(100 * a["t50"] / n, 1),
            "new5": round(100 * a["new5"] / t20, 1) if t20 else None, "new10": round(100 * a["new10"] / t20, 1) if t20 else None,
            "old": round(100 * a["old"] / t20, 1) if t20 else None,
            "p84": round(sum(p * k for p, k in a["p84"]) / w, 2) if w else None,
            "t12_ago": a["t12_ago"], "t12_now": a["t12_now"],
            "up5": round(100 * (a["t12_now"] / a["t12_ago"] - 1)) if a["t12_ago"] >= 20 else None,
            "new5_now": round(100 * a["new5_now"] / a["t12_now"], 1) if a["t12_now"] else None,
            "gn3": 1 if sgg in GN3 else 0, "hr": 1 if sgg in HR else 0,
        }
    out = {
        "asof": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "src": "국토교통부 아파트 실거래가 (apt.sqlite · rtms.py) · 서울 25구",
        "note": ("실거래 기준(기사는 공시가·AI시세). 단지·월·전용 집계 평균가로 분류해 경계값 근처 ±몇 건 오차. "
                 "신축=거래 시점 기준 준공 5년 이내, 준신축 5~10년, 구축 10년 초과. 5년 증가율은 5년 전 1~M월 vs 올해 1~M월 12억+ 거래건수."),
        "q": qs, "cur_q": cur_q, "tiers": list(TIERS), "conc": conc_out,
        "win12": f"{ym12}~{ym_now}", "ago": f"{ago0}~{ago1}", "now": f"{now0}~{ym_now}",
        "gu": gu,
        "by_year": {GU[s]: {y: dict(v) for y, v in d.items() if y >= "2015"} for s, d in byy.items() if s in GU},
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    c = conc_out["50"].get(cur_q) or conc_out["50"][qs[-1]]
    print(f"  → {OUT} ({OUT.stat().st_size//1024}KB) · {cur_q} 50억+ {c['all']}건 중 강남3구 {c['gn3_pct']}% · 20억+ 강남3구 {conc_out['20'][qs[-1]]['gn3_pct']}%")
    for g in ("강남구", "동대문구", "강서구", "성동구"):
        v = gu.get(g, {})
        print(f"    {g}: 12M {v.get('n12')}건 · 20억+ {v.get('p20')}% · 신축/준신축/구축 {v.get('new5')}/{v.get('new10')}/{v.get('old')} · 12억+ 5년 {v.get('up5')}% (신축비중 {v.get('new5_now')}%)")


if __name__ == "__main__":
    main()
