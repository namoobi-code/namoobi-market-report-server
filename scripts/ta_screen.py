#!/usr/bin/env python3
"""TradingAgents 종목 스크리닝 파이프라인 (서버 무-LLM 파트, stdlib only).

stage1: 유니버스 + 거래가능성 하드컷  -> data/db/ta_stage1.json
stage2: 4축 z-score 랭킹 + 재무건전성 -> data/db/ta_stage2.json (최종 30×2)
stage3: 토론 번들(상위 10×2) + 규칙 플래그 -> data/db/ta_stage3.json
all   : 1->2->3 순차. 각 단계 실패 시 기존 JSON 유지(carry-forward).
"""
import json, os, re, sys, time, math, html, traceback
import urllib.request, urllib.parse, http.cookiejar
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB   = os.path.join(BASE, "data", "db")
CACHE= os.path.join(BASE, "data", "ta_cache")
os.makedirs(DB, exist_ok=True); os.makedirs(CACHE, exist_ok=True)
UA={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
KRX_KEY_FILE=os.path.join(BASE,"secrets","krx.key")

def now_kst(): return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
def get(url,headers=None,timeout=20,opener=None):
    if opener: return opener.open(url,timeout=timeout).read()
    req=urllib.request.Request(url,headers={**UA,**(headers or {})})
    return urllib.request.urlopen(req,timeout=timeout).read()
def jget(url,headers=None,timeout=20,opener=None):
    return json.loads(get(url,headers,timeout,opener))
def num(s):
    if s is None: return None
    if isinstance(s,(int,float)): return float(s)
    m=re.search(r"-?[\d,]+(?:\.\d+)?",str(s).replace(" ",""))
    if not m: return None
    try: return float(m.group(0).replace(",",""))
    except: return None
def save_db(name,obj):
    obj["as_of"]=now_kst()
    tmp=os.path.join(DB,f"{name}.json.tmp")
    json.dump(obj,open(tmp,"w"),ensure_ascii=False)
    os.replace(tmp,os.path.join(DB,f"{name}.json"))
def load_db(name):
    try: return json.load(open(os.path.join(DB,f"{name}.json")))
    except Exception: return None

# ---------------- KRX ----------------
def krx(endpoint,basdd):
    key=open(KRX_KEY_FILE).read().strip()
    d=jget(f"https://data-dbg.krx.co.kr/svc/apis/sto/{endpoint}?basDd={basdd}",headers={"AUTH_KEY":key})
    return d.get("OutBlock_1",[])
def krx_day_back(target,mkt,max_back=10):
    for i in range(max_back):
        dd=(target-timedelta(days=i)).strftime("%Y%m%d")
        cache=f"{CACHE}/krx_{mkt}_{dd}.json"
        if os.path.exists(cache):
            rows=json.load(open(cache))
            if rows: return dd,rows
            continue
        try: rows=krx(f"{mkt}_bydd_trd",dd)
        except Exception: rows=[]
        json.dump(rows,open(cache,"w"))
        if rows: return dd,rows
        time.sleep(0.3)
    return None,[]

# ---------------- Yahoo ----------------
def yahoo_opener():
    cj=http.cookiejar.CookieJar()
    op=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    op.addheaders=list(UA.items())
    try: op.open("https://fc.yahoo.com",timeout=10)
    except Exception: pass
    crumb=op.open("https://query1.finance.yahoo.com/v1/test/getcrumb",timeout=10).read().decode()
    return op,crumb

def us_symbols():
    junk=re.compile(r"Warrant|Right|Unit|Preferred|Depositary Shares|Notes? |ETN",re.I)
    syms=[]
    for fn,url,etf_i,test_i,fs in (("nq.txt","https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt",6,3,4),
                                   ("other.txt","https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt",4,6,None)):
        p=f"{CACHE}/{fn}"
        data=get(url).decode("utf-8",errors="replace")
        open(p,"w").write(data)
        rows=[l.rstrip("\n").split("|") for l in data.splitlines()][1:]
        for r in rows:
            if len(r)<8 or "File Creation" in r[0]: continue
            if r[etf_i]!="N" or r[test_i]!="N": continue
            if fs is not None and r[fs]=="D": continue
            if junk.search(r[1]): continue
            syms.append(r[0].replace("$","-P").replace(".","-"))
    return list(dict.fromkeys(syms))

# ================ STAGE 1 ================
def stage1():
    today=date.today()
    d0s,stk=krx_day_back(today,"stk"); _,ksq=krx_day_back(today,"ksq")
    d1,_r1=krx_day_back(datetime.strptime(d0s,"%Y%m%d").date()-timedelta(days=1),"stk")
    # 3거래일 거래대금 평균용
    prev=[]
    t=datetime.strptime(d0s,"%Y%m%d").date()
    for k in range(1,3):
        dd,_=krx_day_back(t-timedelta(days=k),"stk")
        prev.append(dd)
        krx_day_back(t-timedelta(days=k),"ksq")
    base={}
    for mkt in ("stk","ksq"):
        cache=f"{CACHE}/krxbase_{mkt}_{d0s}.json"
        if os.path.exists(cache): rows=json.load(open(cache))
        else:
            rows=krx(f"{mkt}_isu_base_info",d0s); json.dump(rows,open(cache,"w"))
        for b in rows: base[b["ISU_SRT_CD"]]=b
    cutoff=today-timedelta(days=365)
    kr_pass=[]; kr_total=0
    for mkt in ("stk","ksq"):
        _,d0rows=krx_day_back(datetime.strptime(d0s,"%Y%m%d").date(),mkt)
        loads=[{r["ISU_CD"]:r for r in json.load(open(f"{CACHE}/krx_{mkt}_{dd}.json"))} for dd in prev if dd and os.path.exists(f"{CACHE}/krx_{mkt}_{dd}.json")]
        kr_total+=len(d0rows)
        for r in d0rows:
            code=r["ISU_CD"]; b=base.get(code)
            if not b or b.get("SECUGRP_NM")!="주권" or b.get("KIND_STKCERT_TP_NM")!="보통주": continue
            if "스팩" in r["ISU_NM"]: continue
            ldd=b.get("LIST_DD","")
            try:
                if date(int(ldd[:4]),int(ldd[4:6]),int(ldd[6:8]))>cutoff: continue
            except Exception: pass
            close=num(r["TDD_CLSPRC"]); mcap=num(r["MKTCAP"])
            if not close or close<1000 or not mcap or mcap<3000e8: continue
            vals=[num(r["ACC_TRDVAL"])]+[num(x[code]["ACC_TRDVAL"]) for x in loads if code in x]
            vals=[v for v in vals if v is not None]
            if not vals or sum(vals)/len(vals)<30e8: continue
            kr_pass.append({"code":code,"name":r["ISU_NM"],"mkt":r["MKT_NM"],"close":close,
                            "mcap":mcap,"trdval":round(sum(vals)/len(vals))})
    # US
    syms=us_symbols(); us_total=len(syms)
    op,crumb=yahoo_opener()
    quotes=[]
    for i in range(0,len(syms),350):
        chunk=syms[i:i+350]
        url=("https://query1.finance.yahoo.com/v7/finance/quote?symbols="
             +urllib.parse.quote(",".join(chunk))+"&crumb="+urllib.parse.quote(crumb))
        try: quotes+= (jget(url,opener=op).get("quoteResponse") or {}).get("result") or []
        except Exception as e: print("batch fail",i,e)
        time.sleep(0.3)
    json.dump(quotes,open(f"{CACHE}/us_quotes.json","w"))
    us_pass=[]
    cutoff_ms=time.mktime((cutoff.year,cutoff.month,cutoff.day,0,0,0,0,0,0))
    for q in quotes:
        if q.get("quoteType")!="EQUITY": continue
        px=q.get("regularMarketPrice"); mcap=q.get("marketCap"); v3=q.get("averageDailyVolume3Month")
        if not px or px<5 or not mcap or mcap<2e9 or not v3 or v3*px<20e6: continue
        vs200=q.get("twoHundredDayAverageChangePercent")
        if vs200 is not None and vs200<-0.30: continue
        ft=q.get("firstTradeDateMilliseconds")
        if ft and ft/1000>cutoff_ms: continue
        us_pass.append({"sym":q["symbol"],"name":(q.get("longName") or q.get("shortName") or "")[:44],
                        "px":px,"mcap":mcap})
    kr_pass.sort(key=lambda r:-r["mcap"]); us_pass.sort(key=lambda r:-r["mcap"])
    save_db("ta_stage1",{"trade_date":d0s,"kr":{"universe":kr_total,"pass":len(kr_pass),"rows":kr_pass},
                         "us":{"universe":us_total,"pass":len(us_pass),"rows":us_pass}})
    print(f"stage1 ok: KR {kr_total}->{len(kr_pass)} US {us_total}->{len(us_pass)}")

# ================ STAGE 2 ================
def zmap(vals):
    xs=[v for v in vals.values() if v is not None and math.isfinite(v)]
    if len(xs)<20: return {}
    mu=sum(xs)/len(xs); sd=(sum((x-mu)**2 for x in xs)/len(xs))**0.5 or 1
    return {k:max(-3,min(3,(v-mu)/sd)) for k,v in vals.items() if v is not None and math.isfinite(v)}
def amean(zs):
    zs=[z for z in zs if z is not None]
    return sum(zs)/len(zs) if zs else None
def pmap(fn,items,workers=14):
    out=[]
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for fut in as_completed([ex.submit(fn,i) for i in items]): out.append(fut.result())
    return out

def stage2():
    s1=load_db("ta_stage1")
    d0=datetime.strptime(s1["trade_date"],"%Y%m%d").date()
    anchors={}
    for lbl,days in (("m1",30),("m12",365)):
        anchors[lbl]={}
        for mkt in ("stk","ksq"):
            dd,rows=krx_day_back(d0-timedelta(days=days),mkt)
            anchors[lbl][mkt]={r["ISU_CD"]:r for r in rows}
    FIN=re.compile(r"은행|금융|증권|보험|생명|화재|카드|캐피탈|종금|저축|지주")
    def nv_int(r):
        try:
            j=jget(f"https://m.stock.naver.com/api/stock/{r['code']}/integration",timeout=10)
            t={x["code"]:x.get("value") for x in j.get("totalInfos",[])}
            return {**r,"tot":t}
        except Exception as e: return {**r,"err":type(e).__name__}
    kr=pmap(nv_int,s1["kr"]["rows"])
    rows=[]
    for r in kr:
        if "tot" not in r: continue
        t=r["tot"]; mkt="stk" if r["mkt"]=="KOSPI" else "ksq"
        per,cper=num(t.get("per")),num(t.get("cnsPer")); eps,ceps=num(t.get("eps")),num(t.get("cnsEps"))
        pbr,divy=num(t.get("pbr")),num(t.get("dividendYieldRatio"))
        hi52=num(t.get("highPriceOf52Weeks")); frate=num(t.get("foreignRate"))
        fper=cper if cper and cper>0 else (per if per and per>0 else None)
        if fper is None: continue
        growth=min(ceps/eps-1,2.0) if (eps and eps>0 and ceps and ceps>0) else None
        a1,a12=anchors["m1"][mkt].get(r["code"]),anchors["m12"][mkt].get(r["code"])
        mom=None
        if a1 and a12:
            c1,c12=num(a1["TDD_CLSPRC"]),num(a12["TDD_CLSPRC"])
            sh0,sh12=None,num(a12.get("LIST_SHRS"))
            sh0=num((a1 or {}).get("LIST_SHRS"))
            if c1 and c12 and not (sh0 and sh12 and abs(sh0/sh12-1)>0.10): mom=c1/c12-1
        near52=(r["close"]/hi52-1) if hi52 else None
        roe_px=min(pbr/per,0.6) if (pbr and per and 1<per<80 and 0.1<pbr<20) else None
        rows.append({**{k:r[k] for k in ("code","name","mkt","close","mcap")},
                     "fper":fper,"per":per,"pbr":pbr,"divy":divy,"growth":growth,"mom":mom,
                     "near52":near52,"roe_px":roe_px,"frate":frate,"isfin":bool(FIN.search(r["name"]))})
    def score_axes(rs,key,axdef):
        zz={ax:[zmap({r[key]:f(r) for r in rs}) for f in fs] for ax,fs in axdef.items()}
        for r in rs:
            k=r[key]
            for ax in axdef: r["z_"+ax]=amean([z.get(k) for z in zz[ax]])
            axs=[r["z_"+ax] for ax in axdef if r["z_"+ax] is not None]
            r["score"]=sum(axs)/len(axs) if len(axs)>=3 else None
    score_axes(rows,"code",{"val":[lambda r:-r["fper"],lambda r:(-r["pbr"] if r["pbr"] and r["pbr"]>0 else None),lambda r:r["divy"]],
                            "grw":[lambda r:r["growth"]],
                            "mom":[lambda r:r["mom"],lambda r:r["near52"]],
                            "qly":[lambda r:r["roe_px"]]})
    kr150=sorted([r for r in rows if r["score"] is not None],key=lambda r:-r["score"])[:150]
    # KR Layer2: naver annual
    def nv_fin(r):
        try:
            j=jget(f"https://m.stock.naver.com/api/stock/{r['code']}/finance/annual",timeout=10)
            fi=j.get("financeInfo") or {}
            actual=sorted([t["key"] for t in fi.get("trTitleList",[]) if t.get("isConsensus")=="N"])[-3:]
            cons=sorted([t["key"] for t in fi.get("trTitleList",[]) if t.get("isConsensus")=="Y"])[:1]
            rd={x["title"]:{k:num((v or {}).get("value")) for k,v in (x.get("columns") or {}).items()} for x in fi.get("rowList",[])}
            f={}
            for tt in ("매출액","영업이익","ROE","부채비율","당좌비율"):
                f[tt]=[rd.get(tt,{}).get(k) for k in actual]
                if cons: f[tt+"_E"]=rd.get(tt,{}).get(cons[0])
            return {**r,"fin":f}
        except Exception as e: return {**r,"err2":type(e).__name__}
    kr150=pmap(nv_fin,kr150)
    def last(l):
        for v in reversed(l or []):
            if v is not None: return v
    def yoy(l):
        a=[v for v in (l or []) if v is not None]
        return (a[-1]/a[-2]-1) if len(a)>=2 and a[-2] and a[-2]>0 else None
    kr_s,kr_drop=[],[]
    for r in kr150:
        f=r.get("fin")
        if not f: kr_drop.append([r["name"],"재무 미수집"]); continue
        op3=[v for v in (f.get("영업이익") or []) if v is not None]
        de=last(f.get("부채비율")); roe=last(f.get("ROE"))
        if len(op3)>=3 and all(v<0 for v in op3[-3:]): kr_drop.append([r["name"],"3년 연속 영업적자"]); continue
        if not r["isfin"] and de is not None and de>300: kr_drop.append([r["name"],f"부채비율 {de:.0f}%"]); continue
        revg,opg=yoy(f.get("매출액")),yoy(f.get("영업이익"))
        la,le=last(f.get("매출액")),f.get("매출액_E")
        rf=(le/la-1) if (la and le and la>0) else None
        g=[min(x,3.0) for x in (revg,opg,rf) if x is not None]
        kr_s.append({**{k:r[k] for k in ("code","name","mkt","close","mcap","fper","pbr","divy","mom","near52","frate","isfin")},
                     "de":de,"roe":roe,"revg":revg,"opg":opg,"g_new":sum(g)/len(g) if g else None})
    score_axes(kr_s,"code",{"val":[lambda r:-r["fper"],lambda r:(-r["pbr"] if r["pbr"] and r["pbr"]>0 else None),lambda r:r["divy"]],
                            "grw":[lambda r:r["g_new"]],
                            "mom":[lambda r:r["mom"],lambda r:r["near52"]],
                            "qly":[lambda r:r["roe"],lambda r:(-r["de"] if r["de"] is not None and not r["isfin"] else None)]})
    kr_final=sorted([r for r in kr_s if r["score"] is not None],key=lambda r:-r["score"])[:30]
    # ---- US ----
    quotes=json.load(open(f"{CACHE}/us_quotes.json"))
    qmap={q["symbol"]:q for q in quotes}
    us=[]
    for p in load_db("ta_stage1")["us"]["rows"]:
        q=qmap.get(p["sym"])
        if not q: continue
        pe,fpe0=q.get("trailingPE"),q.get("forwardPE")
        if not ((pe and pe>0) or (fpe0 and fpe0>0)): continue
        epsT,epsF=q.get("epsTrailingTwelveMonths"),q.get("epsForward")
        growth=min(epsF/epsT-1,2.0) if (epsT and epsT>0 and epsF and epsF>0) else None
        pb=q.get("priceToBook")
        us.append({"sym":p["sym"],"name":p["name"],"px":p["px"],"mcap":p["mcap"],
                   "fpe":fpe0 if fpe0 and fpe0>0 else pe,"pb":pb if pb and pb>0 else None,
                   "divy":q.get("dividendYield"),"growth":growth,
                   "w52":q.get("fiftyTwoWeekChangePercent"),"hi52":q.get("fiftyTwoWeekHighChangePercent"),
                   "vs200":q.get("twoHundredDayAverageChangePercent"),
                   "roe_px":min(pb/pe,0.6) if (pb and pe and 1<pe<80 and 0.1<pb<20) else None})
    score_axes(us,"sym",{"val":[lambda r:-r["fpe"],lambda r:(-r["pb"] if r["pb"] else None),lambda r:r["divy"]],
                         "grw":[lambda r:r["growth"]],
                         "mom":[lambda r:r["w52"],lambda r:r["hi52"],lambda r:r["vs200"]],
                         "qly":[lambda r:r["roe_px"]]})
    us150=sorted([r for r in us if r["score"] is not None],key=lambda r:-r["score"])[:150]
    op,crumb=yahoo_opener()
    def yqs(r):
        try:
            j=jget(f"https://query2.finance.yahoo.com/v10/finance/quoteSummary/{r['sym']}"
                   f"?modules=financialData,assetProfile&crumb={urllib.parse.quote(crumb)}",opener=op,timeout=12)
            fd=(j["quoteSummary"]["result"] or [{}])[0]
            f=fd.get("financialData",{}); ap=fd.get("assetProfile",{})
            def v(x): return (x or {}).get("raw") if isinstance(x,dict) else x
            return {**r,"sector":ap.get("sector"),"de":v(f.get("debtToEquity")),"cr":v(f.get("currentRatio")),
                    "roe":v(f.get("returnOnEquity")),"revg":v(f.get("revenueGrowth")),
                    "epsg":v(f.get("earningsGrowth")),"fcf":v(f.get("freeCashflow"))}
        except Exception as e: return {**r,"err2":type(e).__name__}
    us150=pmap(yqs,us150,workers=10)
    us_s,us_drop=[],[]
    for r in us150:
        if "err2" in r: us_drop.append([r["sym"],"재무 미수집"]); continue
        isfin="Financial" in (r.get("sector") or "")
        de,cr=r.get("de"),r.get("cr")
        if not isfin and de is not None and de>300: us_drop.append([r["sym"],f"D/E {de:.0f}%"]); continue
        if not isfin and cr is not None and cr<0.8: us_drop.append([r["sym"],f"유동비율 {cr:.2f}"]); continue
        g=[min(x,3.0) for x in (r.get("revg"),r.get("epsg")) if x is not None]
        r["g_new"]=sum(g)/len(g) if g else None
        r["fcfy"]=(r["fcf"]/r["mcap"]) if r.get("fcf") and r.get("mcap") else None
        r["isfin"]=isfin
        us_s.append(r)
    score_axes(us_s,"sym",{"val":[lambda r:-r["fpe"],lambda r:(-r["pb"] if r["pb"] else None),lambda r:r["divy"]],
                           "grw":[lambda r:r["g_new"]],
                           "mom":[lambda r:r["w52"],lambda r:r["hi52"],lambda r:r["vs200"]],
                           "qly":[lambda r:r["roe"],lambda r:r["fcfy"],lambda r:(-r["de"] if r["de"] is not None and not r["isfin"] else None)]})
    us_final=sorted([r for r in us_s if r["score"] is not None],key=lambda r:-r["score"])[:30]
    for r in us_final: r.pop("fcf",None)
    save_db("ta_stage2",{"trade_date":s1["trade_date"],
                         "kr":{"scored":len(rows),"drops":kr_drop,"top":kr_final},
                         "us":{"scored":len(us),"drops":us_drop,"top":us_final}})
    print(f"stage2 ok: KR top{len(kr_final)} US top{len(us_final)}")

# ================ STAGE 3 ================
def tech(sym):
    try:
        c=jget(f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?range=1y&interval=1d")["chart"]["result"][0]
        q=c["indicators"]["quote"][0]
        cl=[x for x in q["close"] if x]; hi=[x for x in q["high"] if x]; lo=[x for x in q["low"] if x]
        vol=[v for v,x in zip(q["volume"],q["close"]) if x]
        n=len(cl)
        if n<60: return {"err":"짧은 이력"}
        gains=[max(cl[i]-cl[i-1],0) for i in range(n-14,n)]; losses=[max(cl[i-1]-cl[i],0) for i in range(n-14,n)]
        rsi=100-100/(1+(sum(gains)/14)/max(sum(losses)/14,1e-9))
        def sma(k): return sum(cl[-k:])/k if n>=k else None
        atr=sum(h-l for h,l in zip(hi[-14:],lo[-14:]))/14/cl[-1]*100
        return {"close":round(cl[-1],2),"ret_1m":round(cl[-1]/cl[-21]-1,3) if n>21 else None,
                "ret_3m":round(cl[-1]/cl[-63]-1,3) if n>63 else None,"ret_1y":round(cl[-1]/cl[0]-1,3),
                "vs_50sma":round(cl[-1]/sma(50)-1,3),"vs_200sma":round(cl[-1]/sma(200)-1,3) if n>=200 else None,
                "hi52_dist":round(cl[-1]/max(cl)-1,3),"rsi14":round(rsi),
                "atr_pct":round(atr,1),"vol_20d_vs_60d":round(sum(vol[-20:])/20/max(sum(vol[-60:])/60,1),2)}
    except Exception as e: return {"err":type(e).__name__}
def kr_news(code):
    try:
        d=jget(f"https://m.stock.naver.com/api/news/stock/{code}?pageSize=6&page=1")
        out=[]
        def walk(x):
            if isinstance(x,dict):
                if x.get("title") and x.get("datetime"): out.append(x)
                for v in x.values(): walk(v)
            elif isinstance(x,list):
                for v in x: walk(v)
        walk(d)
        seen=set(); res=[]
        for it in out:
            t=html.unescape(re.sub("<[^>]+>","",it["title"]))
            if t in seen: continue
            seen.add(t); res.append({"t":t,"src":it.get("officeName",""),"dt":str(it.get("datetime"))[:8]})
            if len(res)>=6: break
        return res or "<뉴스 없음>"
    except Exception as e: return f"<네이버 뉴스 실패: {type(e).__name__}>"
def us_news(sym):
    try:
        d=jget(f"https://query1.finance.yahoo.com/v1/finance/search?q={sym}&newsCount=6&quotesCount=0")
        return [{"t":n.get("title",""),"src":n.get("publisher","")} for n in d.get("news",[])][:6] or "<뉴스 없음>"
    except Exception as e: return f"<야후 뉴스 실패: {type(e).__name__}>"
def stocktwits(sym):
    try:
        req=urllib.request.Request(f"https://api.stocktwits.com/api/2/streams/symbol/{sym}.json",
            headers={"User-Agent":"tradingagents/0.2","Accept":"application/json"})
        d=json.loads(urllib.request.urlopen(req,timeout=10).read())
        ms=d.get("messages",[])
        b=sum(1 for m in ms if ((m.get("entities") or {}).get("sentiment") or {}).get("basic")=="Bullish")
        br=sum(1 for m in ms if ((m.get("entities") or {}).get("sentiment") or {}).get("basic")=="Bearish")
        return {"msgs":len(ms),"bullish":b,"bearish":br}
    except Exception as e: return f"<StockTwits 접근 불가: {type(e).__name__}>"
def flags(t,st=None):
    f=[]
    if isinstance(t,dict) and "err" not in t:
        if t.get("rsi14") is not None:
            if t["rsi14"]>=75: f.append("RSI 과열(≥75)")
            elif t["rsi14"]<=35: f.append("RSI 조정권(≤35) — 모멘텀 훼손 주의")
        if (t.get("ret_1m") or 0)<-0.10: f.append("1개월 −10%↓ 하락")
        if (t.get("hi52_dist") or 0)<-0.30: f.append("52주 고점比 −30%↓")
        if (t.get("vol_20d_vs_60d") or 1)>2: f.append("거래량 급증(20d/60d>2)")
    if isinstance(st,dict) and st.get("msgs",0)>=10:
        b,br=st.get("bullish",0),st.get("bearish",0)
        if b+br>=8 and b/(b+br+1e-9)>=0.9: f.append("소셜 강세 쏠림(≥90%) — 역발상 리스크")
    return f
def stage3():
    s2=load_db("ta_stage2")
    KR=s2["kr"]["top"][:10]; US=s2["us"]["top"][:10]
    def do_kr(r):
        ysym=r["code"]+(".KS" if r["mkt"]=="KOSPI" else ".KQ")
        t=tech(ysym)
        return {"종목":r["name"],"코드":r["code"],"시장":r["mkt"],"시총_조원":round(r["mcap"]/1e12,1),
                "팩터카드":{k:r.get(k) for k in ("fper","pbr","divy","roe","de","revg","opg","frate","z_val","z_grw","z_mom","z_qly","score")},
                "기술지표":t,"뉴스_최근":kr_news(r["code"]),
                "심리":{"외국인소진율%":r.get("frate"),"소셜":"<국내 소셜 미연결 — 결측>"},
                "사전플래그":flags(t)}
    def do_us(r):
        t=tech(r["sym"]); st=stocktwits(r["sym"])
        return {"종목":r["name"],"티커":r["sym"],"시총_십억달러":round(r["mcap"]/1e9),
                "팩터카드":{k:r.get(k) for k in ("fpe","pb","divy","roe","de","cr","revg","epsg","fcfy","sector","z_val","z_grw","z_mom","z_qly","score")},
                "기술지표":t,"뉴스_최근":us_news(r["sym"]),"심리":{"StockTwits":st},
                "사전플래그":flags(t,st if isinstance(st,dict) else None)}
    kr_b=pmap(do_kr,KR,workers=6); us_b=pmap(do_us,US,workers=6)
    save_db("ta_stage3",{"trade_date":s2["trade_date"],"kr":kr_b,"us":us_b,
        "안내":"이 번들은 /namoobi-trading-agents 스킬 실행 시 Bull/Bear 토론 에이전트의 입력으로 사용된다. 서버는 LLM을 쓰지 않는다."})
    print(f"stage3 ok: bundles {len(kr_b)}+{len(us_b)}")

def main():
    which=sys.argv[1] if len(sys.argv)>1 else "all"
    status=load_db("ta_status") or {"runs":[]}
    run={"start":now_kst(),"stages":{}}
    # 실행 중 마킹 — 스킬이 생성 중(running) 데이터에 접근하지 않도록 상태를 먼저 공개한다
    prev_flag=load_db("ta_flag") or {}
    save_db("ta_flag",{**{k:prev_flag[k] for k in ("completed","flag_file","trade_date") if k in prev_flag},
                       "status":"running","started":run["start"]})
    stages=["stage1","stage2","stage3"] if which=="all" else [which]
    for st in stages:
        t0=time.time()
        try:
            {"stage1":stage1,"stage2":stage2,"stage3":stage3}[st]()
            run["stages"][st]={"ok":True,"sec":round(time.time()-t0)}
        except Exception as e:
            traceback.print_exc()
            run["stages"][st]={"ok":False,"err":f"{type(e).__name__}: {e}","sec":round(time.time()-t0)}
            break  # 순차 의존 — 실패 시 후속 중단, 기존 JSON carry-forward
    # 3B(stage3)까지 성공 시 완료 flag — 스킬(/namoobi-trading-agents)이 완료 여부를 판단하는 근거
    if run["stages"].get("stage3",{}).get("ok"):
        import glob as _g
        for f in _g.glob(os.path.join(BASE,"screening_completed_*.txt")):
            try: os.remove(f)
            except OSError: pass
        ts=datetime.now().strftime("%y%m%d_%H%M")
        td=(load_db("ta_stage3") or {}).get("trade_date","")
        flag=os.path.join(BASE,f"screening_completed_{ts}.txt")
        open(flag,"w").write(f"trade_date={td}\ncompleted={now_kst()}\nstages={json.dumps(run['stages'],ensure_ascii=False)}\n")
        save_db("ta_flag",{"status":"completed","completed":now_kst(),"flag_file":os.path.basename(flag),"trade_date":td})
    elif any(not v.get("ok") for v in run["stages"].values()):
        err=next((v.get("err","") for v in run["stages"].values() if not v.get("ok")),"")
        save_db("ta_flag",{**{k:prev_flag[k] for k in ("completed","flag_file","trade_date") if k in prev_flag},
                           "status":"failed","failed_at":now_kst(),"error":err[:200]})
    else:
        # stage3 미포함 부분 실행 성공 — 이전 상태 복원
        save_db("ta_flag",prev_flag if prev_flag else {"status":"unknown"})
    run["end"]=now_kst()
    status["runs"]=(status.get("runs") or [])[-13:]+[run]
    save_db("ta_status",status)
if __name__=="__main__":
    main()
