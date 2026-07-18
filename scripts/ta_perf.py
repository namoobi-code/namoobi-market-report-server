#!/usr/bin/env python3
"""5단계 성과추적: ta_calls의 각 회차 판정 종목 경과 수익률 + 벤치마크 대비 α → data/db/ta_perf.json
그룹 = 승인(리스크 심사 통과) / 채택(토론 채택·미승인) / 관망 / 탈락 — 탈락까지 추적해 생존편향 방지.
stdlib only. cron 매일 실행.
v1.1 (2026-07-17):
 - KR 시세·KOSPI 벤치를 네이버 일봉으로 교체 (장 마감 직후 당일 봉 반영 — 야후 ^KS11/.KS는 반나절~하루 늦음). 실패 시 야후 폴백.
 - α 윈도우를 시장별 price_date(가격이 실제 형성된 날) 기준으로 정합. 기존엔 trade_date 하나로 잘라
   US(기준가=전일 종가)의 벤치 구간이 하루 어긋났다 (스킬 문서의 '성과추적은 price_date' 원칙 준수)."""
import json, os, ast, urllib.request
from datetime import datetime, timedelta

BASE=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB=os.path.join(BASE,"data","db")
UA={"User-Agent":"Mozilla/5.0"}
_cache={}

def _get(url):
    return urllib.request.urlopen(urllib.request.Request(url,headers=UA),timeout=15).read()

def chart(sym, rng="6mo"):  # 야후 일봉 [(YYYYMMDD, close)]
    key="y:"+sym
    if key in _cache: return _cache[key]
    try:
        d=json.loads(_get(f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?range={rng}&interval=1d"))["chart"]["result"][0]
        rows=[(datetime.fromtimestamp(t).strftime("%Y%m%d"),c) for t,c in
              zip(d["timestamp"], d["indicators"]["quote"][0]["close"]) if c]
    except Exception:
        rows=[]
    _cache[key]=rows
    return rows

def naver_daily(sym):  # 네이버 일봉 — 6자리 종목코드 또는 'KOSPI' 등 지수 심볼
    key="n:"+sym
    if key in _cache: return _cache[key]
    try:
        s=(datetime.now()-timedelta(days=220)).strftime("%Y%m%d"); e=datetime.now().strftime("%Y%m%d")
        txt=_get(f"https://api.finance.naver.com/siseJson.naver?symbol={sym}&requestType=1&startTime={s}&endTime={e}&timeframe=day").decode("utf-8","ignore")
        data=ast.literal_eval(txt.strip())
        rows=[(str(r[0]),float(r[4])) for r in data[1:] if r and len(r)>4 and r[4]]
    except Exception:
        rows=[]
    _cache[key]=rows
    return rows

def kr_series(info):  # KR 종목: 네이버 우선 → ysym → .KS/.KQ 추정 순 폴백
    r=naver_daily(str(info.get("code","")))
    if r: return r
    if info.get("ysym"):
        r=chart(str(info["ysym"]))
        if r: return r
    for suf in (".KS",".KQ"):
        r=chart(str(info.get("code",""))+suf)
        if r: return r
    return []

def kr_bench_rows():
    r=naver_daily("KOSPI")
    return r if r else chart("^KS11")

def pdate_of(info, fallback):  # 가격 형성일 YYYYMMDD (없으면 fallback)
    p=str(info.get("price_date","") or "").replace("-","")
    return p if len(p)==8 and p.isdigit() else fallback

def horizons(rows, cut_date, base):
    after=[c for d,c in rows if d>cut_date]
    if not base or not after: return {}
    def r(i): return round(after[i]/base-1,4) if len(after)>i else None
    return {"ret_now":round(after[-1]/base-1,4),"days":len(after),
            "ret_1d":r(0),"ret_1w":r(4),"ret_1m":r(20)}

def bench(rows, cut_date):
    b=[c for d,c in rows if d<=cut_date]
    if not b: return {}
    return horizons(rows, cut_date, b[-1])

def main():
    calls=json.load(open(os.path.join(DB,"ta_calls.json"))).get("calls",[])
    out_calls=[]; agg={}
    for call in calls:
        td=call.get("trade_date",""); px=call.get("px_snapshot",{})
        appr={a.get("종목") for a in call.get("approved",[])}
        verd={v.get("종목"):v.get("판정") for v in call.get("verdicts",[])}
        # 시장별 기준일 = 해당 시장 px_snapshot의 price_date (KRX 기본정보일인 trade_date와 다를 수 있다)
        krd=[pdate_of(i,td) for i in px.values() if i.get("시장","US")=="KR"]
        usd=[pdate_of(i,td) for i in px.values() if i.get("시장","US")!="KR"]
        cutK=max(krd) if krd else td; cutU=max(usd) if usd else td
        bK=bench(kr_bench_rows(), cutK); bU=bench(chart("SPY"), cutU)
        stocks=[]
        for name,info in px.items():
            mkt=info.get("시장","US"); base=info.get("close")
            rows=kr_series(info) if mkt=="KR" else chart(str(info.get("ysym") or info.get("code","")))
            h=horizons(rows, pdate_of(info, cutK if mkt=="KR" else cutU), base)
            if not h: continue
            bm=bK if mkt=="KR" else bU
            grp="승인" if name in appr else {"채택":"채택(미승인)","관망":"관망","탈락":"탈락"}.get(verd.get(name),"관망")
            alpha=round(h["ret_now"]-bm.get("ret_now",0),4) if bm else None
            stocks.append({"종목":name,"시장":mkt,"그룹":grp,"기준가":base,**h,"alpha_now":alpha})
            a=agg.setdefault(grp,{"n":0,"ret":0.0,"alpha":0.0,"an":0})
            a["n"]+=1; a["ret"]+=h["ret_now"]
            if alpha is not None: a["alpha"]+=alpha; a["an"]+=1
        groups={}
        for g in ("승인","채택(미승인)","관망","탈락"):
            gs=[s for s in stocks if s["그룹"]==g]
            if gs: groups[g]={"n":len(gs),"avg_ret":round(sum(x["ret_now"] for x in gs)/len(gs),4),
                              "avg_alpha":round(sum(x["alpha_now"] or 0 for x in gs)/len(gs),4)}
        out_calls.append({"trade_date":td,"판정생성":call.get("as_of",""),
                          "price_date":{"KR":cutK,"US":cutU},
                          "경과거래일":max((s["days"] for s in stocks),default=0),
                          "bench":{"KOSPI":bK.get("ret_now"),"SPY":bU.get("ret_now")},
                          "groups":groups,"stocks":sorted(stocks,key=lambda s:s["그룹"])})
    summary={g:{"n":a["n"],"avg_ret":round(a["ret"]/a["n"],4),
                "avg_alpha":round(a["alpha"]/a["an"],4) if a["an"] else None}
             for g,a in agg.items() if a["n"]}
    obj={"as_of":datetime.now().strftime("%Y-%m-%d %H:%M:%S"),"runs":len(out_calls),
         "summary":summary,"calls":out_calls,
         "설명":"기준가=판정 시점에 본 종가(시장별 price_date). α=같은 price_date 구간 벤치마크(KR=KOSPI·US=SPY) 대비 초과수익. KR 시세=네이버 일봉(당일 반영, 야후 폴백). 탈락군까지 추적(생존편향 방지)."}
    tmp=os.path.join(DB,"ta_perf.json.tmp")
    json.dump(obj,open(tmp,"w"),ensure_ascii=False)
    os.replace(tmp,os.path.join(DB,"ta_perf.json"))
    print("ta_perf:",len(out_calls),"runs |",json.dumps(summary,ensure_ascii=False))

if __name__=="__main__":
    main()
