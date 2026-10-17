#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fetch_dividend.py — 💰 배당 탭 데이터 (2026-10-17 신설)

한경MONEY 2026.10 '배당 여력 4배로… 이번 가을 배당주 지도' 체크리스트 4가지를 종목별로 기계 판정:
  ① 배당을 낼 여력(잉여현금흐름·배당성향) ② 계속 낼 수 있나(3~5년 이력·신규투자 부담) ③ 총주주환원의 질 ④ 배당락 이후 리스크
+ 사용자 요청 항목: 지금 시점 유리한가 · 예상 배당률 · 배당 날짜/주기 · 주가 하락 가능성 · 배당성장 · 몇 년째 성장 · 분리과세 적격(KR, 2026 시행)

소스(전부 기존 DB + 야후 배당 이벤트)
  screener_pool(divy·payout·주가·RSI·200일선·변동성·이익성장·FCF수익률) · dps_hist(KR DPS 5개년·연속증가, DART) ·
  div_hist_us(US 연속증가연수·지급횟수·지급월그룹·5년 MDD) · 야후 chart events=div (실제 배당락일·금액 → 주기·다음 배당락 추정·배당락 폭)
  → data/db/dividend_hist.json 에 배당 이벤트 캐시(7일), data/db/dividend.json 화면용.
유니버스: KR 시총 3,000억↑·배당수익률 2%↑ (≈210) · US 시총 $5B↑·2%↑ (≈420)
cron: 10 8 * * *
"""
import json, sys, time, urllib.parse as _up
from datetime import datetime, timedelta, timezone, date
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DB = BASE / "data" / "db"
OUT = DB / "dividend.json"; HIST = DB / "dividend_hist.json"
KST = timezone(timedelta(hours=9))
sys.path.insert(0, str(BASE / "scripts"))
import ta_screen as T

def jload(p, default=None):
    try: return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception: return default if default is not None else {}
def log(m): print(m, flush=True)
def pct(v, d=1): return None if v is None else round(v, d)

def div_events(sym, op):
    j = T.jget(f"https://query1.finance.yahoo.com/v8/finance/chart/{_up.quote(sym)}?range=2y&interval=1d&events=div", opener=op, timeout=20)
    dv = (j["chart"]["result"][0].get("events") or {}).get("dividends") or {}
    ev = sorted([[datetime.fromtimestamp(v["date"], timezone.utc).strftime("%Y-%m-%d"), float(v["amount"])] for v in dv.values()])
    return ev

def cycle_from(ev):
    """최근 12개월 지급 횟수 → 주기 라벨, 다음 배당락 추정일(마지막 배당락 + 365/횟수)"""
    if not ev: return None, None, None, None
    today = date.today(); cut = (today - timedelta(days=370)).isoformat()
    last12 = [e for e in ev if e[0] >= cut]
    n = len(last12)
    freq = 12 if n >= 10 else 4 if n >= 3 else 2 if n == 2 else 1
    lab = {12: "월배당", 4: "분기", 2: "반기", 1: "연 1회"}[freq]
    last_d = date.fromisoformat(ev[-1][0]); nxt = last_d + timedelta(days=round(365 / freq))
    while nxt < today: nxt += timedelta(days=round(365 / freq))
    ttm = sum(a for _, a in last12)
    return freq, lab, nxt.isoformat(), ttm

def main():
    log("[dividend] 시작")
    pool = jload(DB / "screener_pool.json"); dps = (jload(DB / "dps_hist.json").get("d") or {}); dus = (jload(DB / "div_hist_us.json").get("d") or {})
    gb = jload(DB / "gbonds.json"); y10 = {c["cc"]: c["cur"] for c in gb.get("countries") or []}
    hist = jload(HIST); hist.setdefault("ev", {})
    op, _ = T.yahoo_opener()
    today = date.today(); rows = []
    uni = [("kr", r) for r in pool.get("kr") or [] if (r.get("divy") or 0) >= 2 and (r.get("cap") or 0) >= 3e11 and not r.get("isfin_x")] + \
          [("us", r) for r in pool.get("us") or [] if (r.get("divy") or 0) >= 2 and (r.get("cap") or 0) >= 5e9]
    log(f"  유니버스 {len(uni)}")
    fetched = 0
    for mk, r in uni:
        c = r.get("c"); sym = (c + (".KQ" if (r.get("mkt") or "").upper().startswith("KOSDAQ") else ".KS")) if mk == "kr" else c
        h = hist["ev"].get(sym)
        if not h or (today - date.fromisoformat(h["at"])).days > 7:
            try:
                ev = div_events(sym, op); hist["ev"][sym] = {"at": today.isoformat(), "ev": ev}; fetched += 1; time.sleep(0.15)
            except Exception:
                ev = (h or {}).get("ev") or []
        else: ev = h["ev"]
        freq, lab, nxt, ttm = cycle_from(ev)
        px = r.get("px") or 0
        row = {"mk": mk, "c": c, "name": r.get("name") or r.get("kn") or c, "px": px, "cap": r.get("cap"),
               "divy": r.get("divy"), "payout": pct((r.get("payout") or 0) * 100, 0) if r.get("payout") is not None else None,
               "freq": freq, "cyc": lab, "next_ex": nxt, "last_ex": ev[-1][0] if ev else None, "last_amt": ev[-1][1] if ev else None,
               "rsi": r.get("rsi"), "vs200": pct((r.get("vs200") or 0) * 100, 1) if r.get("vs200") is not None else None,
               "vol20": r.get("vol20"), "hi52": pct(((r.get("hi52") if mk == "us" else r.get("near52")) or 0) * 100, 1) if (r.get("hi52") if mk == "us" else r.get("near52")) is not None else None,
               "grw": pct(((r.get("opg") if mk == "kr" else r.get("epsg")) or 0) * 100, 0) if (r.get("opg") if mk == "kr" else r.get("epsg")) is not None else None,
               "fcfy": pct((r.get("fcfy") or 0) * 100, 1) if r.get("fcfy") is not None else None}
        # 배당락 예상 폭(건당 배당÷주가)
        row["drop"] = pct(row["last_amt"] / px * 100, 2) if row["last_amt"] and px else None
        if mk == "kr":
            d = dps.get(c) or {}; y = {int(k): v for k, v in (d.get("y") or {}).items()}
            ys = sorted(y); row["inc"] = d.get("inc"); row["dps_hist"] = {str(k): y[k] for k in ys}
            if ys:
                last = y[ys[-1]]; row["dps_last"] = last; row["dps_year"] = ys[-1]
                if len(ys) >= 4 and y[ys[-4]] > 0: row["cagr3"] = pct(((last / y[ys[-4]]) ** (1 / 3) - 1) * 100, 1)
                g = (row.get("cagr3") or 0) / 100 if (d.get("inc") or 0) >= 2 else 0
                row["dps_est"] = round(last * (1 + min(max(g, 0), 0.3))); row["est_note"] = "확정 DPS×최근 3년 CAGR(상한 30%)" if g else "직전 확정 DPS 유지 가정"
                row["ydiv_est"] = pct(row["dps_est"] / px * 100, 2) if px else None
                # 분리과세 적격(2026 시행, 기사): 배당 안 줄이고 (성향≥40%) 또는 (성향≥25% & DPS 10%↑)
                prev = y[ys[-2]] if len(ys) >= 2 else None; po = row["payout"] or 0
                if prev is not None and last >= prev:
                    row["sep_tax"] = bool(po >= 40 or (po >= 25 and last >= prev * 1.1))
                else: row["sep_tax"] = False
            # 월배당 조합용 지급월(분기배당일 때)
            if ev and freq and freq >= 4: row["pay_months"] = sorted({int(e[0][5:7]) for e in ev[-4:]})
        else:
            u = dus.get(c) or {}; row["inc"] = u.get("dgy"); row["mdd5"] = u.get("mdd5"); row["pmg"] = u.get("pmg")
            yy = {int(k): v for k, v in (u.get("y") or {}).items()}; ys = sorted(k for k in yy if k < today.year)
            row["dps_hist"] = {str(k): round(yy[k], 3) for k in ys[-5:]}
            if ys:
                row["dps_last"] = round(yy[ys[-1]], 3); row["dps_year"] = ys[-1]
                if len(ys) >= 4 and yy[ys[-4]] > 0: row["cagr3"] = pct(((yy[ys[-1]] / yy[ys[-4]]) ** (1 / 3) - 1) * 100, 1)
            if row["last_amt"] and freq: row["dps_est"] = round(row["last_amt"] * freq, 3); row["est_note"] = "직전 건당 배당×연 지급횟수"; row["ydiv_est"] = pct(row["dps_est"] / px * 100, 2) if px else None
            if ev and freq and freq >= 4: row["pay_months"] = sorted({int(e[0][5:7]) for e in ev[-freq:]})
        # ── 판정 ───────────────────────────────────────────
        po = row.get("payout"); s_safe = 0; why = []
        if po is not None and po <= (70 if mk == "kr" else 85): s_safe += 1
        else: why.append("배당성향 높음" if po is not None else "성향 미확인")
        if (row.get("grw") or -1) >= 0: s_safe += 1
        else: why.append("이익 감소")
        if (row.get("inc") or 0) >= 3: s_safe += 1
        else: why.append("연속증가 3년 미만")
        if mk == "us" and row.get("fcfy") is not None and row["divy"] is not None and row["fcfy"] < row["divy"]: why.append("FCF<배당")
        row["safe"] = s_safe; row["safe_why"] = " · ".join(why)
        s_tm = 0; tw = []
        if row.get("vs200") is not None and row["vs200"] <= 0: s_tm += 1; tw.append("200일선 아래(눌림)")
        if row.get("rsi") is not None and row["rsi"] < 50: s_tm += 1; tw.append(f"RSI {row['rsi']:.0f}")
        dd = (date.fromisoformat(nxt) - today).days if nxt else None; row["dday"] = dd
        if dd is not None and dd <= 45: s_tm += 1; tw.append(f"배당락 D-{dd}")
        bench = y10.get("KR" if mk == "kr" else "US")
        if bench and row["divy"] and row["divy"] >= bench: s_tm += 1; tw.append(f"배당률≥국채{bench:.1f}%")
        row["timing"] = s_tm; row["timing_why"] = " · ".join(tw) or "눌림·과매도·임박 신호 없음"
        # 하락 가능성(위험) — 변동성·고점대비·5년MDD·배당락폭
        risk = 0; rw = []
        if (row.get("vol20") or 0) >= (3 if mk == "kr" else 2): risk += 1; rw.append("변동성 높음")
        if mk == "us" and (row.get("mdd5") or 0) <= -40: risk += 1; rw.append(f"5년 MDD {row['mdd5']:.0f}%")
        if (row.get("hi52") or 0) <= -25: risk += 1; rw.append("52주 고점比 −25%↓")
        if (row.get("drop") or 0) >= 3: risk += 1; rw.append(f"배당락 폭 {row['drop']}%")
        row["risk"] = risk; row["risk_why"] = " · ".join(rw) or "낮음"
        # 특별배당·일회성 의심: 직전 확정 DPS 가 전년의 2배↑ 이거나 배당성향 100%↑ — 기사 "배당수익률만 보고 고르면 낭패"
        hist_y = row.get("dps_hist") or {}; hv = [v for _, v in sorted(hist_y.items())]
        row["special"] = bool((len(hv) >= 2 and hv[-2] and hv[-1] >= hv[-2] * 2) or (po is not None and po >= 100))
        if row["special"]:
            row["est_note"] = "⚠ 특별배당/성향 100%↑ 의심 — 증가율 미적용, 직전 DPS 유지 가정"
            if row.get("dps_last") and mk == "kr": row["dps_est"] = round(row["dps_last"]); row["ydiv_est"] = pct(row["dps_est"] / px * 100, 2) if px else None
        # 종합 — 배당률 기여는 6% 에서 캡(고배당 함정 억제), 특별배당 의심 −1.5
        row["score"] = round(s_safe * 1.5 + s_tm + min(row["divy"] or 0, 6) / 2 - risk - (1.5 if row["special"] else 0), 2)
        rows.append(row)
    HIST.write_text(json.dumps(hist, ensure_ascii=False), encoding="utf-8")
    rows.sort(key=lambda r: -r["score"])
    # 고배당 ETF (국내 풀 — 이름에 배당/고배당/커버드콜, 분배율순)
    etfs = []
    for r in (jload(DB / "etf_pool.json").get("kr") or []):
        n = r.get("n") or ""
        if any(k in n for k in ("배당", "커버드콜", "인컴")) and r.get("divy"):
            etfs.append({"c": r["c"], "n": n, "px": r.get("px"), "divy": r.get("divy"), "r1y": pct((r.get("r1y") or 0) * 100, 1) if r.get("r1y") is not None else None, "fee": r.get("fee"), "cap": r.get("cap")})
    etfs.sort(key=lambda x: -(x["cap"] or 0)); etfs = etfs[:25]
    OUT.write_text(json.dumps({"as_of": datetime.now(KST).strftime("%Y-%m-%d %H:%M"), "y10": y10,
                               "kr": [r for r in rows if r["mk"] == "kr"][:80], "us": [r for r in rows if r["mk"] == "us"][:80],
                               "n": {"kr": sum(1 for r in rows if r["mk"] == "kr"), "us": sum(1 for r in rows if r["mk"] == "us")},
                               "etfs": etfs, "ref": {"kospi_mfg_ni": {"2025": 169, "2026E": 751, "2027E": 973}, "kospi_mfg_fcf": {"2025": 99, "2026E": 522, "2027E": 778},
                                                     "src": "리딩투자증권(한경MONEY 2026.10) — 유가증권 제조업 상장사 순이익·잉여현금흐름, 조원"}},
                              ensure_ascii=False), encoding="utf-8")
    log(f"[dividend] ✅ KR {sum(1 for r in rows if r['mk']=='kr')} · US {sum(1 for r in rows if r['mk']=='us')} · 배당이벤트 신규 {fetched} · ETF {len(etfs)} → {OUT}")

if __name__ == "__main__":
    main()
