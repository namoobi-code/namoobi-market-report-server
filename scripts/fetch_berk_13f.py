#!/usr/bin/env python3
# fetch_berk_13f.py — [부록A] 버크셔 해서웨이 13F 자동 갱신 (v1.0 · 2026-08-14 신설)
#
#   SEC EDGAR 원문(13F-HR INFORMATION TABLE XML)을 직접 파싱해 최신 분기와 직전 분기를 비교하고
#   신규매수·비중확대·비중축소·전량매도·상위보유를 계산해 db/berkshire.json 을 갱신한다.
#   기존에는 에이전트(NewsBerk)가 뉴스로 채워 넣어 공시가 나와도 리포트를 돌리기 전까지 화면이 멈췄다.
#   → 이제 서버 크론이 마감일(2/14·5/15·8/14·11/14) 전후로 EDGAR 를 직접 확인해 스스로 갱신한다.
#
#   사용: python3 scripts/fetch_berk_13f.py [OUTDIR=data/db] [--force]
#   산출: <OUTDIR>/berkshire.json  (marker=filing_date — 리포트 파이프라인의 due 게이트가 이 값으로 변동 감지)
#   원칙: 추정 금지 — 계산 가능한 수치만 기록하고, 서술(summary/cash)은 사실 문장만 조립한다.
import json, os, re, sys, time, urllib.request, datetime as dt
from xml.etree import ElementTree as ET

CIK  = "0001067983"                       # Berkshire Hathaway Inc
UA   = {"User-Agent": "namoobi-market-report namoobi@gmail.com"}
OUT  = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("-") else "data/db"
FORCE= "--force" in sys.argv

def get(url, tries=3):
    last = None
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=25) as r:
                return r.read()
        except Exception as e:
            last = e; time.sleep(1.2 * (i + 1))
    raise last

def filings():
    d = json.loads(get(f"https://data.sec.gov/submissions/CIK{CIK}.json"))
    r = d["filings"]["recent"]
    out = []
    for form, filed, period, acc in zip(r["form"], r["filingDate"], r["reportDate"], r["accessionNumber"]):
        if form == "13F-HR":                       # /A(정정)는 제외 — 정본만
            out.append({"filed": filed, "period": period, "acc": acc.replace("-", "")})
    out.sort(key=lambda x: (x["period"], x["filed"]), reverse=True)
    return out

def info_table(acc):
    """공시 폴더에서 INFORMATION TABLE XML 을 찾아 (issuer,class)별 보유를 합산."""
    base = f"https://www.sec.gov/Archives/edgar/data/{int(CIK)}/{acc}"
    idx  = json.loads(get(base + "/index.json"))
    names = [it["name"] for it in idx["directory"]["item"]]
    cand = [n for n in names if n.lower().endswith(".xml") and "primary_doc" not in n.lower()]
    if not cand:
        raise RuntimeError("information table xml 없음: " + base)
    # 정보표는 보통 유일한 비-primary xml. 여러 개면 크기 큰 쪽(=정보표)
    xml = None
    for n in sorted(cand, key=lambda x: 0 if "info" in x.lower() or "table" in x.lower() else 1):
        try:
            b = get(f"{base}/{n}")
            if b and b"infoTable" in b: xml = b; break
        except Exception: pass
    if xml is None: raise RuntimeError("infoTable 파싱 실패: " + base)
    root = ET.fromstring(xml)
    ns = ""
    m = re.match(r"\{(.+)\}", root.tag)
    if m: ns = "{%s}" % m.group(1)
    hold = {}
    for it in root.iter(ns + "infoTable"):
        def txt(tag, node=it):
            e = node.find(ns + tag)
            return (e.text or "").strip() if e is not None and e.text else ""
        issuer = txt("nameOfIssuer"); cls = txt("titleOfClass"); cusip = txt("cusip")
        val = txt("value")
        sh = it.find(ns + "shrsOrPrnAmt")
        shares = 0
        if sh is not None:
            e = sh.find(ns + "sshPrnamt")
            if e is not None and e.text: shares = int(float(e.text.replace(",", "")))
        try: val = float(val.replace(",", ""))
        except Exception: val = 0.0
        key = cusip.upper().strip()   # CUSIP 9자리 = 종목·클래스 고유키
        h = hold.setdefault(key, {"issuer": issuer, "class": cls, "cusip": cusip, "value": 0.0, "shares": 0})
        h["value"] += val; h["shares"] += shares
    tot = sum(h["value"] for h in hold.values())
    if tot and tot < 5e9:                 # 2023년 이전 양식은 value 단위가 '천 달러'
        for h in hold.values(): h["value"] *= 1000.0
    return hold

TICK = {  # 주요 보유 종목 티커 (표시용 — 없으면 공란)
 "APPLE":"AAPL","AMERICAN EXPRESS":"AXP","BANK OF AMERICA":"BAC","BANK AMERICA":"BAC","COCA COLA":"KO","COCA-COLA":"KO",
 "CHEVRON":"CVX","OCCIDENTAL PETROLEUM":"OXY","OCCIDENTAL PETRO":"OXY","MOODYS":"MCO","MOODY'S":"MCO","KRAFT HEINZ":"KHC",
 "CHUBB":"CB","DAVITA":"DVA","KROGER":"KR","SIRIUS XM":"SIRI","VERISIGN":"VRSN","VISA":"V",
 "MASTERCARD":"MA","AMAZON":"AMZN","AON":"AON","CONSTELLATION BRANDS":"STZ","DOMINOS":"DPZ",
 "DOMINO'S":"DPZ","UNITEDHEALTH":"UNH","NUCOR":"NUE","DELTA AIR":"DAL","ALPHABET":"GOOGL",
 "NEW YORK TIMES":"NYT","LENNAR":"LEN","MACY":"M","LIBERTY":"LLYVK","POOL":"POOL","HEICO":"HEI",
 "T-MOBILE":"TMUS","LOUISIANA-PACIFIC":"LPX","DIAGEO":"DEO","LAMB WESTON":"LW","ALLY":"ALLY",
 "CHARTER COMMUNICATIONS":"CHTR","LIBERTY MEDIA":"FWONK","ULTA":"ULTA","NVR":"NVR","JEFFERIES":"JEF",
 "CAPITAL ONE":"COF","VERISK":"VRSK","LIBERTY LATIN":"LILA","BATTALION":"","ATLANTA BRAVES":"BATRA"}
def tick(issuer, cls=""):
    u = issuer.upper()
    for k, v in TICK.items():
        if k in u:
            if v == "GOOGL" and "C" in cls.upper().replace("CLASS","").strip()[:2]: return "GOOG"
            return v
    return ""

def num(n):  # 한국식 주식수 표기 (1784만6142주)
    n = int(n)
    if n >= 10 ** 8: return f"{n//10**8}억{(n%10**8)//10**4}만{n%10**4}주".replace("만0주","만주")
    if n >= 10 ** 4: return f"{n//10**4}만{n%10**4}주".replace("만0주","만주")
    return f"{n:,}주"
def usd(v):
    if v >= 1e9:  return f"약 {v/1e8/10:.1f}0억달러".replace(".00억","억") if False else f"약 {v/1e8:.1f}억달러"
    if v >= 1e6:  return f"약 {v/1e8:.2f}억달러"
    return f"약 {v:,.0f}달러"

def main():
    fl = filings()
    if len(fl) < 2:
        print("13F 이력 부족"); return 1
    cur, prv = fl[0], fl[1]
    dst = os.path.join(OUT, "berkshire.json")
    old = {}
    try: old = json.loads(open(dst, encoding="utf-8").read())
    except Exception: pass
    if not FORCE and old.get("data", {}).get("filing_date") == cur["filed"] and old.get("marker") == cur["filed"]:
        print(f"변동 없음 — 최신 13F {cur['filed']} (period {cur['period']}) 이미 반영됨"); return 0
    print(f"신규 13F 감지: filed {cur['filed']} · period {cur['period']} (직전 {prv['filed']}/{prv['period']})")
    C, P = info_table(cur["acc"]), info_table(prv["acc"])
    tot = sum(h["value"] for h in C.values()); ptot = sum(h["value"] for h in P.values())

    new, added, reduced, exited = [], [], [], []
    for k, h in C.items():
        p = P.get(k)
        if not p or p["shares"] == 0:
            new.append((h["value"], {"name": h["issuer"] + (f" ({h['class']})" if h["class"] and h["class"].upper()!="COM" else ""),
                                     "ticker": tick(h["issuer"], h["class"]),
                                     "detail": f"신규 {num(h['shares'])} 매입(평가액 {usd(h['value'])})."})); continue
        if h["shares"] > p["shares"] * 1.005:
            pct = h["shares"] / p["shares"] * 100 - 100
            added.append((h["value"] - p["value"], {"name": h["issuer"] + (f" ({h['class']})" if h["class"] and h["class"].upper()!="COM" else ""),
                "ticker": tick(h["issuer"], h["class"]),
                "detail": f"{num(p['shares'])}에서 {num(h['shares'])}로 약 {pct:.1f}% 증가(평가액 {usd(h['value'])})."}))
        elif h["shares"] < p["shares"] * 0.995:
            pct = 100 - h["shares"] / p["shares"] * 100
            reduced.append((p["value"] - h["value"], {"name": h["issuer"] + (f" ({h['class']})" if h["class"] and h["class"].upper()!="COM" else ""),
                "ticker": tick(h["issuer"], h["class"]),
                "detail": f"{num(p['shares'])}에서 {num(h['shares'])}로 약 {pct:.1f}% 감소(평가액 {usd(h['value'])})."}))
    for k, p in P.items():
        if k not in C or C[k]["shares"] == 0:
            exited.append((p["value"], {"name": p["issuer"] + (f" ({p['class']})" if p["class"] and p["class"].upper()!="COM" else ""),
                "ticker": tick(p["issuer"], p["class"]),
                "detail": f"{num(p['shares'])} 전량 매도(전분기 평가액 {usd(p['value'])})."}))
    srt = lambda a: [x[1] for x in sorted(a, key=lambda y: -y[0])]
    new, added, reduced, exited = srt(new), srt(added), srt(reduced), srt(exited)

    top = []
    for h in sorted(C.values(), key=lambda x: -x["value"])[:20]:
        p = P.get(h["cusip"].upper().strip())
        chg = "보유주식수 변동 없음" if (p and p["shares"] == h["shares"]) else (
              f"전분기 {num(p['shares'])} → {num(h['shares'])}" if p else "신규 편입")
        top.append({"name": h["issuer"] + (f" ({h['class']})" if h["class"] and h["class"].upper()!="COM" else ""),
                    "ticker": tick(h["issuer"], h["class"]),
                    "weight_or_value": f"{h['value']/tot*100:.2f}% (${h['value']/1e9:.2f}B)",
                    "note": f"{h['shares']:,}주 보유, {chg}"})

    q = dt.date.fromisoformat(cur["period"])
    qn = f"{q.year} Q{(q.month-1)//3+1} (as of {cur['period']})"
    summary = (f"버크셔 해서웨이가 {cur['filed'][:4]}년 {int(cur['filed'][5:7])}월 {int(cur['filed'][8:10])}일 SEC에 제출한 "
       f"{qn.split(' (')[0]} 13F-HR 공시(기준일 {cur['period']})에 따르면, 보통주 포트폴리오 평가액은 약 {tot/1e8:,.0f}억달러로 "
       f"전분기(약 {ptot/1e8:,.0f}억달러) 대비 {(tot/ptot-1)*100:+.1f}% 변동했다. 보유 종목 수 {len(C)}개"
       f"(전분기 {len(P)}개) · 신규 {len(new)} · 확대 {len(added)} · 축소 {len(reduced)} · 청산 {len(exited)}건. "
       f"각 항목은 평가액 상위 12건까지 표기한다. 수치는 EDGAR 13F-HR 정보표 원문을 합산한 실측이며, 서술적 배경은 별도 확인이 필요하다.")
    data = dict(old.get("data") or {})
    data.update({"quarter": qn, "filing_date": cur["filed"], "summary": summary,
                 "new_buys": new[:12], "added": added[:12], "reduced": reduced[:12], "exited": exited[:12],
                 "top_holdings": top,
                 "sources": [f"https://www.sec.gov/Archives/edgar/data/{int(CIK)}/{cur['acc']}/",
                             f"https://data.sec.gov/submissions/CIK{CIK}.json"]})
    if data.get("cash") and cur["filed"] != (old.get("data", {}) or {}).get("filing_date"):
        data["cash"] = (data["cash"] + "  ※ 현금 항목은 13F 공시 대상이 아니어서 직전 분기 보고서(10-Q/K) 기준이며, "
                        "새 분기 수치는 다음 리포트에서 갱신된다.") if "※" not in data["cash"] else data["cash"]
    out = {"marker": cur["filed"], "as_of": dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
           "auto": "fetch_berk_13f.py (EDGAR 원문 파싱)", "data": data}
    os.makedirs(OUT, exist_ok=True)
    json.dump(out, open(dst, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"저장 {dst} · 총 {tot/1e8:,.0f}억달러 · 종목 {len(C)} · 신규{len(new)}/확대{len(added)}/축소{len(reduced)}/청산{len(exited)}")
    for t in top[:5]: print("   ", t["ticker"], t["name"][:28], t["weight_or_value"], t["note"][:40])
    return 0

if __name__ == "__main__":
    sys.exit(main())
