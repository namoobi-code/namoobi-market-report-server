#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""etf_meta.py — KR ETF 상장일 + 월배당 메타 (2026-08-06 신설 · 주 1회).

① 상장연도(yr): finance.naver 종목 메인의 '상장일' 행 파싱(불변 — 기수집 스킵).
② 월배당(md)·연분배횟수(dvn): SEIBro 분배금지급현황 실측 API —
   POST /websquare/engine/proworks/callServletService.jsp
   action=exerInfoDtramtPayStatPlist · task=ksd.safe.bip.cnts.etf.process.EtfExerInfoPTask
   START_PAGE/END_PAGE = 행 오프셋(최대 30행/콜, LIST_CNT 무시 — 실측).
   권리기준일(RGT_STD_DT) 이력을 etf_dist.json 에 롤링 누적(13개월) 후
   최근 12개월 분배 발생 '월 수' ≥10 → 월배당 판정.
산출: etf_meta.json {asof, d:{code:{yr,md,dvn}}} · etf_dist.json {asof,d:{code:[YYYYMMDD..]}}
cron: 20 8 * * 0
"""
import json, re, time, urllib.request
from datetime import datetime, timedelta
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "data" / "db" / "etf_meta.json"
DIST = BASE / "data" / "db" / "etf_dist.json"
H = {"User-Agent": "Mozilla/5.0"}

SEIBRO = "https://seibro.or.kr/websquare/engine/proworks/callServletService.jsp"

def seibro_dist(dt_from, dt_to):
    """권리기준일 범위의 분배금 지급 내역 [(code, rgt_dt)] — 30행/콜 페이징."""
    out = []
    sp = 1
    while True:
        body = ('<reqParam action="exerInfoDtramtPayStatPlist" '
                'task="ksd.safe.bip.cnts.etf.process.EtfExerInfoPTask">'
                f'<RGT_STD_DT_FROM value="{dt_from}"/><RGT_STD_DT_TO value="{dt_to}"/>'
                '<ISIN value=""/><MNGCO_CUSTNO value=""/>'
                f'<START_PAGE value="{sp}"/><END_PAGE value="{sp+29}"/><MENU_NO value="179"/></reqParam>')
        req = urllib.request.Request(SEIBRO, data=body.encode(), headers={
            **H, "Content-Type": "application/xml",
            "Referer": "https://seibro.or.kr/websquare/control.jsp"})
        try:
            t = urllib.request.urlopen(req, timeout=25).read().decode("utf-8", "ignore")
        except Exception as e:
            print(f"  [seibro] {sp}행~ 실패: {repr(e)[:60]} — 3초 후 재시도", flush=True)
            time.sleep(3)
            try:
                t = urllib.request.urlopen(req, timeout=25).read().decode("utf-8", "ignore")
            except Exception:
                break
        rows = re.findall(r'<ISIN value="([^"]+)"/>.*?<RGT_STD_DT value="(\d{8})"/>', t, re.S)
        if not rows:
            break
        for isin, dt in rows:
            out.append((isin[3:9], dt))                    # ISIN KR7xxxxxxK → 6자리 코드
        if len(rows) < 30:
            break
        sp += 30
        time.sleep(0.25)
        if sp % 3000 == 1:
            print(f"  [seibro] {sp-1}행 수집…", flush=True)
    return out

def main():
    pool = json.loads((BASE / "data" / "db" / "etf_pool.json").read_text(encoding="utf-8"))
    codes = [r["c"] for r in pool.get("kr") or [] if r.get("c")]
    old = {}
    try:
        old = json.loads(OUT.read_text(encoding="utf-8")).get("d") or {}
    except Exception:
        pass
    d = dict(old)
    ok = 0
    for i, c in enumerate(codes):
        if d.get(c, {}).get("yr"):                      # 상장일은 불변 — 기수집 스킵
            ok += 1
            continue
        try:
            t = urllib.request.urlopen(urllib.request.Request(
                f"https://finance.naver.com/item/main.naver?code={c}", headers=H), timeout=10).read()
            try: t = t.decode("utf-8")
            except UnicodeDecodeError: t = t.decode("cp949", "ignore")
            m = re.search(r"상장일</th>\s*<td[^>]*>\s*(\d{4})년", t)
            if m:
                d.setdefault(c, {})["yr"] = int(m.group(1))
                ok += 1
        except Exception:
            pass
        time.sleep(0.05)
        if i % 300 == 299:
            print(f"  {i+1}/{len(codes)} (확보 {ok})", flush=True)
    # ② SEIBro 분배금 이력 — 증분 수집(기존 이력 마지막 날짜-7일부터) + 롤링 13개월
    dist = {}
    try:
        dist = json.loads(DIST.read_text(encoding="utf-8")).get("d") or {}
    except Exception:
        pass
    all_dt = [x for v in dist.values() for x in v]
    frm = ((datetime.strptime(max(all_dt), "%Y%m%d") - timedelta(days=7)).strftime("%Y%m%d")
           if all_dt else (datetime.now() - timedelta(days=396)).strftime("%Y%m%d"))
    to = datetime.now().strftime("%Y%m%d")
    rows = seibro_dist(frm, to)
    for c, dt in rows:
        a = dist.setdefault(c, [])
        if dt not in a:
            a.append(dt)
    cut = (datetime.now() - timedelta(days=400)).strftime("%Y%m%d")
    dist = {c: sorted(x for x in v if x >= cut) for c, v in dist.items()}
    dist = {c: v for c, v in dist.items() if v}
    DIST.write_text(json.dumps({"asof": datetime.now().strftime("%Y-%m-%d %H:%M"), "d": dist},
                               ensure_ascii=False), encoding="utf-8")
    # 판정 — 최근 12개월(오늘 제외 직전 12개 캘린더월) 분배 발생 월 수
    lo12 = (datetime.now() - timedelta(days=366)).strftime("%Y%m")
    n_md = 0
    for c in codes:
        v = dist.get(c) or []
        months = {x[:6] for x in v if x[:6] >= lo12}
        dvn = len([x for x in v if x[:6] >= lo12])
        m = d.setdefault(c, {})
        m["dvn"] = dvn
        m["md"] = 1 if len(months) >= 10 else 0            # 12개월 중 10개월 이상 분배 = 월배당
        n_md += m["md"]
    OUT.write_text(json.dumps({"asof": datetime.now().strftime("%Y-%m-%d %H:%M"), "d": d},
                              ensure_ascii=False), encoding="utf-8")
    print(f"[etfmeta] ✅ 상장연도 {ok}/{len(codes)}종 · 분배이력 {len(rows)}건 수집 · 월배당 {n_md}종 → {OUT}", flush=True)

if __name__ == "__main__":
    main()
