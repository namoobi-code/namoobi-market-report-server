#!/usr/bin/env python3
# fetch_berk_10q.py — [부록A] 버크셔 분기보고서(10-Q/10-K) 실측 수집 (v1.0 · 2026-08-14 신설)
#
#   13F(보유 명세)는 분기 말 기준·45일 뒤 공시라 늦다. 반면 10-Q 는 약 40일 만에 나오고
#   ① 상장주식 매입·매도 금액 ② 자사주 매입 ③ 현금+단기 미국채 ④ 주식 평가액 을 담는다.
#   → 13F 를 기다리는 동안에도 "버크셔가 사고 있나 팔고 있나"를 실측으로 알 수 있다.
#
#   자료: SEC XBRL companyconcept(현금흐름 YTD → 분기 단독값으로 차분) +
#         10-Q XBRL 인스턴스(brka-YYYYMMDD_htm.xml)에서 USTreasuryBills·현금 잔액.
#         ※ 단기 미국채는 us-gaap 표준태그가 아니라 버크셔 확장태그 USTreasuryBills(보험부문)로 보고된다.
#   사용: python3 scripts/fetch_berk_10q.py [OUTDIR=data/db]
#   산출: <OUTDIR>/berkshire.json 의 data.q_flow (13F 본문은 건드리지 않음) + data.cash 문장 갱신
#   원칙: 추정 금지 — XBRL 에 없으면 그 항목만 비운다(비차단).
import json, os, re, sys, time, urllib.request, datetime as dt
from xml.etree import ElementTree as ET

CIK = "0001067983"
UA  = {"User-Agent": "namoobi-market-report namoobi@gmail.com"}
OUT = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("-") else "data/db"
FORCE = "--force" in sys.argv

def get(url, tries=3):
    last = None
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40) as r:
                return r.read()
        except Exception as e:
            last = e; time.sleep(1.2 * (i + 1))
    raise last

def latest_periodic():
    """가장 최근 10-Q(또는 10-K) 1건."""
    d = json.loads(get(f"https://data.sec.gov/submissions/CIK{CIK}.json"))
    r = d["filings"]["recent"]
    for form, filed, period, acc, doc in zip(r["form"], r["filingDate"], r["reportDate"],
                                             r["accessionNumber"], r["primaryDocument"]):
        if form in ("10-Q", "10-K"):
            return {"form": form, "filed": filed, "period": period, "acc": acc.replace("-", "")}
    return None

def concept(tag):
    """us-gaap 개념의 (start,end)→값. 없으면 {}."""
    try:
        d = json.loads(get(f"https://data.sec.gov/api/xbrl/companyconcept/CIK{CIK}/us-gaap/{tag}.json"))
    except Exception:
        return {}
    out = {}
    for arr in d.get("units", {}).values():
        for x in arr:
            if x.get("form") in ("10-Q", "10-K"):
                out[(x.get("start", ""), x["end"])] = float(x["val"])
    return out

def qtr_value(tag, period):
    """분기 단독값 = 해당 분기 누계(YTD) − 직전 분기까지 누계. 1분기면 누계 그대로."""
    c = concept(tag)
    if not c: return None
    y = period[:4]
    ytd = {k: v for k, v in c.items() if k[1] == period and k[0].startswith(y)}
    if not ytd: return None
    cur = sorted(ytd.items(), key=lambda kv: kv[0][0])[0][1]   # 같은 회계연도 시작(YTD) 항목
    # 직전 분기말 누계 찾기
    pend = {"03-31": None, "06-30": f"{y}-03-31", "09-30": f"{y}-06-30", "12-31": f"{y}-09-30"}[period[5:]]
    if not pend: return cur
    prev = [v for k, v in c.items() if k[1] == pend and k[0].startswith(y)]
    return cur - min(prev) if prev else None

def instance_facts(acc, period):
    """10-Q 인스턴스에서 분기말 잔액(현금·제한현금·단기 미국채·주식 평가액)."""
    base = f"https://www.sec.gov/Archives/edgar/data/{int(CIK)}/{acc}"
    idx = json.loads(get(base + "/index.json"))
    xml = next((it["name"] for it in idx["directory"]["item"] if it["name"].endswith("_htm.xml")), None)
    if not xml: return {}
    root = ET.fromstring(get(f"{base}/{xml}"))
    inst = {}
    for c in root.iter():
        if c.tag.endswith("}context"):
            cid = c.get("id"); i = None
            for e in c.iter():
                if e.tag.endswith("}instant"): i = (e.text or "").strip()
            if i: inst[cid] = i
    want = {"CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents": "cash_incl_restricted",
            "RestrictedCashAndCashEquivalents": "restricted",
            "USTreasuryBills": "tbills", "EquitySecuritiesFvNi": "equity_fv"}
    got = {}
    for e in root.iter():
        tg = e.tag.split("}")[-1]
        if tg in want and inst.get(e.get("contextRef")) == period and e.text:
            try: v = float(e.text)
            except Exception: continue
            k = want[tg]
            got[k] = max(got.get(k, 0.0), v)     # 세그먼트 분할 표기 시 최대값(=합계 행)
    return got

def main():
    f = latest_periodic()
    if not f: print("10-Q/10-K 없음"); return 1
    dst = os.path.join(OUT, "berkshire.json")
    try: doc = json.loads(open(dst, encoding="utf-8").read())
    except Exception: doc = {"data": {}}
    cur = (doc.get("data") or {}).get("q_flow") or {}
    if not FORCE and cur.get("filed") == f["filed"] and cur.get("period") == f["period"]:
        print(f"변동 없음 — 최신 {f['form']} {f['filed']} (period {f['period']}) 이미 반영됨"); return 0
    print(f"신규 {f['form']} 감지: filed {f['filed']} · period {f['period']}")
    buy  = qtr_value("PaymentsToAcquireEquitySecuritiesFvNi", f["period"])
    sell = qtr_value("ProceedsFromSaleOfEquitySecuritiesFvNi", f["period"])
    bb   = qtr_value("PaymentsForRepurchaseOfCommonStock", f["period"])
    inst = instance_facts(f["acc"], f["period"])
    cash = (inst.get("cash_incl_restricted") or 0) - (inst.get("restricted") or 0) or None
    tb   = inst.get("tbills")
    tot  = (cash + tb) if (cash and tb) else None
    q    = dt.date.fromisoformat(f["period"])
    qn   = f"{q.year} Q{(q.month-1)//3+1}"
    net  = (buy - sell) if (buy is not None and sell is not None) else None
    def a(v): return None if v is None else round(v / 1e8, 1)          # 억달러
    qf = {"quarter": qn, "period": f["period"], "form": f["form"], "filed": f["filed"],
          "equity_buy_100m": a(buy), "equity_sell_100m": a(sell), "equity_net_100m": a(net),
          "buyback_100m": a(bb), "equity_fv_100m": a(inst.get("equity_fv")),
          "cash_100m": a(cash), "tbills_100m": a(tb), "cash_total_100m": a(tot),
          "note": "현금흐름은 분기 단독값(누계 차분) · 단기 미국채=버크셔 확장태그 USTreasuryBills · 단위 억달러"}
    prev_tot = cur.get("cash_total_100m")
    parts = []
    if tot:  parts.append(f"현금 및 단기 미국채 합계 {tot/1e8:,.0f}억달러({f['period']} 기준"
                          + (f", 전분기 {prev_tot:,.0f}억달러 대비 {tot/1e8-prev_tot:+,.0f}억달러" if prev_tot else "") + ")")
    if cash and tb: parts.append(f"내역: 현금·현금성자산 {cash/1e8:,.0f}억 + 단기 미국채 {tb/1e8:,.0f}억")
    if net is not None:
        parts.append(f"{qn} 상장주식 순{'매수' if net>0 else '매도'} {abs(net)/1e8:,.0f}억달러"
                     f"(매입 {buy/1e8:,.0f}억 · 매도 {sell/1e8:,.0f}억)")
    if bb: parts.append(f"자사주 매입 {bb/1e8:,.1f}억달러")
    if parts:
        doc.setdefault("data", {})["cash"] = " · ".join(parts) + f". [{f['form']} {f['filed']} 제출 XBRL 실측]"
    doc.setdefault("data", {})["q_flow"] = qf
    doc["as_of_10q"] = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    os.makedirs(OUT, exist_ok=True)
    json.dump(doc, open(dst, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(" 저장:", dst)
    for k in ("equity_buy_100m", "equity_sell_100m", "equity_net_100m", "buyback_100m",
              "cash_100m", "tbills_100m", "cash_total_100m", "equity_fv_100m"):
        print(f"   {k:20s} {qf[k]}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
