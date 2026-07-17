#!/usr/bin/env python3
# screener_pool.py — 인터랙티브 스크리너용 '전종목 풀'.
# stage1 과 같은 구조(보통주/EQUITY·ETF/스팩 제외)이되 값 임계(시총·가격·거래대금)는 적용하지 않는다.
# 클라이언트가 필드로 실시간 필터링한다. 하루 2회 cron(장 마감 후) 갱신.
import os, sys, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from datetime import date, datetime, timedelta
import ta_screen as T

def _score(rs, key, axdef):
    """stage2 score_axes 와 동일 — 축별 z-score(zmap) + 종합(min 3축)."""
    zz={ax:[T.zmap({r[key]:g(r) for r in rs}) for g in fs] for ax,fs in axdef.items()}
    for r in rs:
        k=r[key]
        for ax in axdef: r["z_"+ax]=T.amean([z.get(k) for z in zz[ax]])
        axs=[r["z_"+ax] for ax in axdef if r.get("z_"+ax) is not None]
        r["score"]=sum(axs)/len(axs) if len(axs)>=3 else None

FIN_RE=None
def _isfin(name):
    global FIN_RE
    if FIN_RE is None:
        import re
        FIN_RE=re.compile(r"은행|금융|증권|보험|생명|화재|카드|캐피탈|종금|저축|지주")
    return bool(FIN_RE.search(name or ""))

def _last(l):
    for v in reversed(l or []):
        if v is not None: return v
def _yoy(l):
    a=[v for v in (l or []) if v is not None]
    return (a[-1]/a[-2]-1) if (len(a)>=2 and a[-2] and a[-2]>0) else None

KR_AXDEF={"val":[lambda r:(-r["fper"] if r.get("fper") else None),
                 lambda r:(-r["pbr"] if r.get("pbr") and r["pbr"]>0 else None),
                 lambda r:r.get("divy")],
          "grw":[lambda r:r.get("g_new")],
          "mom":[lambda r:r.get("mom"), lambda r:r.get("near52"), lambda r:r.get("vs200"), lambda r:r.get("rev")],
          "qly":[lambda r:r.get("roe"),
                 lambda r:(-r["de"] if r.get("de") is not None and not r.get("isfin") else None)]}

def _enrich_kr(kr, d0s):
    """한국 전종목 실측 재무: integration(V·실시간 PER/PBR) + finance/annual(실측 G/Q·하드컷)."""
    d0=datetime.strptime(d0s,"%Y%m%d").date()
    anchors={}
    for lbl,days in (("m1",30),("m12",365)):
        anchors[lbl]={}
        for mkt in ("stk","ksq"):
            _,rows=T.krx_day_back(d0-timedelta(days=days),mkt)
            anchors[lbl][mkt]={r["ISU_CD"]:r for r in rows}
    def fetch(r):
        o={**r}
        try:
            j=T.jget(f"https://m.stock.naver.com/api/stock/{r['c']}/integration",timeout=10)
            o["tot"]={x["code"]:x.get("value") for x in j.get("totalInfos",[])}
            o["cons"]=j.get("consensusInfo") or {}
        except Exception: pass
        try:
            j=T.jget(f"https://m.stock.naver.com/api/stock/{r['c']}/finance/annual",timeout=10)
            fi=j.get("financeInfo") or {}
            actual=sorted([t["key"] for t in fi.get("trTitleList",[]) if t.get("isConsensus")=="N"])[-3:]
            cons=sorted([t["key"] for t in fi.get("trTitleList",[]) if t.get("isConsensus")=="Y"])[:1]
            rd={x["title"]:{k:T.num((v or {}).get("value")) for k,v in (x.get("columns") or {}).items()} for x in fi.get("rowList",[])}
            fin={}
            for tt in ("매출액","영업이익","ROE","부채비율","당좌비율"):
                fin[tt]=[rd.get(tt,{}).get(k) for k in actual]
                if cons: fin[tt+"_E"]=rd.get(tt,{}).get(cons[0])
            o["fin"]=fin
        except Exception: pass
        try:
            S=(date.today()-timedelta(days=400)).strftime("%Y%m%d"); E=date.today().strftime("%Y%m%d")
            dch=T.jget(f"https://api.stock.naver.com/chart/domestic/item/{r['c']}/day?startDateTime={S}&endDateTime={E}",timeout=12)
            cl=[x["closePrice"] for x in dch if x.get("closePrice")]
            if len(cl)>=100: o["ma200"]=cl[-1]/(sum(cl[-200:])/min(200,len(cl)))-1
        except Exception: pass
        return o
    enr=T.pmap(fetch, kr, workers=16)
    for i,r in enumerate(enr):
        t=r.get("tot") or {}; fn=r.get("fin") or {}
        per,cper=T.num(t.get("per")),T.num(t.get("cnsPer"))
        pbr,divy=T.num(t.get("pbr")),T.num(t.get("dividendYieldRatio"))
        hi52=T.num(t.get("highPriceOf52Weeks"))
        fper=cper if (cper and cper>0) else (per if per and per>0 else None)
        mkt="stk" if r.get("mk")=="KOSPI" else "ksq"
        a1,a12=anchors["m1"][mkt].get(r["c"]),anchors["m12"][mkt].get(r["c"])
        mom=None
        if a1 and a12:
            c1,c12=T.num(a1.get("TDD_CLSPRC")),T.num(a12.get("TDD_CLSPRC"))
            sh0,sh12=T.num(a1.get("LIST_SHRS")),T.num(a12.get("LIST_SHRS"))
            if c1 and c12 and not (sh0 and sh12 and abs(sh0/sh12-1)>0.10): mom=c1/c12-1
        near52=(r["px"]/hi52-1) if (hi52 and r.get("px")) else None
        # 컨센서스 목표주가·투자의견 (KR: recommMean 높을수록 매수)
        cons=r.get("cons") or {}
        tp=T.num(cons.get("priceTargetMean")); rec=T.num(cons.get("recommMean"))
        upside=(tp/r["px"]-1) if (tp and tp>0 and r.get("px")) else None
        recn=((rec-1)/4*100) if rec is not None else None
        # 실측 G/Q + 하드컷
        revg,opg=_yoy(fn.get("매출액")),_yoy(fn.get("영업이익"))
        la,le=_last(fn.get("매출액")),fn.get("매출액_E")
        rf=(le/la-1) if (la and le and la>0) else None
        gg=[min(x,3.0) for x in (revg,opg,rf) if x is not None]
        roe=_last(fn.get("ROE")); de=_last(fn.get("부채비율")); cr=_last(fn.get("당좌비율"))
        op3=[v for v in (fn.get("영업이익") or []) if v is not None]
        r.update(fper=fper,per=per,pbr=pbr,divy=divy,mom=mom,near52=near52,
                 roe=roe,de=de,cr=cr,revg=revg,opg=opg,g_new=(sum(gg)/len(gg) if gg else None),
                 op3neg=(len(op3)>=3 and all(v<0 for v in op3[-3:])), isfin=_isfin(r.get("n")), vs200=r.get("ma200"),
                 tp=tp, rec=rec, upside=upside, recn=recn)
        r["growth"]=r.get("g_new")
        r["code"]=r["c"]; r["name"]=r["n"]; r["mkt"]=r.get("mk"); r["close"]=r.get("px"); r["mcap"]=r.get("cap")
        r.pop("tot",None); r.pop("fin",None); r.pop("cons",None); kr[i]=r
    _score(kr,"c",KR_AXDEF)   # rev(tp_rev)는 이 시점 None → tp_history 후 build()에서 재채점

def _enrich_us(us):
    """미국 전종목 실측 재무: 캐시 quotes(V·M) + quoteSummary(실측 G/Q·하드컷)."""
    prev={}
    try:
        for r in (T.load_db("screener_pool") or {}).get("us",[]): prev[r.get("c")]=r
    except Exception: pass
    uq=f"{T.CACHE}/us_quotes.json"; qmap={}
    if os.path.exists(uq):
        for q in json.load(open(uq)):
            if q.get("quoteType")=="EQUITY": qmap[q.get("symbol")]=q
    for r in us:
        q=qmap.get(r["c"]) or {}
        pe,fpe0=q.get("trailingPE"),q.get("forwardPE")
        pb=q.get("priceToBook")
        r["fpe"]=fpe0 if (fpe0 and fpe0>0) else (pe if pe and pe>0 else None)
        r["pb"]=pb if (pb and pb>0) else None
        r["divy"]=q.get("dividendYield")
        r["w52"]=q.get("fiftyTwoWeekChangePercent"); r["hi52"]=q.get("fiftyTwoWeekHighChangePercent")
        r["vs200"]=q.get("twoHundredDayAverageChangePercent")
    op,crumb=T.yahoo_opener()
    import urllib.parse as _up
    _p2=int(time.time()); _p1=_p2-5*365*24*3600
    def _op3neg_us(sym):
        """fundamentals-timeseries annualOperatingIncome → 최근 3년 연속 영업적자 여부."""
        try:
            t=T.jget(f"https://query2.finance.yahoo.com/ws/fundamentals-timeseries/v1/finance/timeseries/{sym}"
                     f"?symbol={sym}&type=annualOperatingIncome&period1={_p1}&period2={_p2}&crumb={_up.quote(crumb)}",opener=op,timeout=12)
            res=(t.get("timeseries",{}) or {}).get("result",[]) or []
            for r0 in res:
                arr=r0.get("annualOperatingIncome") or []
                vals=[(x.get("reportedValue",{}) or {}).get("raw") for x in arr if x]
                vals=[x for x in vals if x is not None]
                if len(vals)>=3: return all(v<0 for v in vals[-3:])
        except Exception: pass
        return None
    def _eps_rev(fd):
        """EPS 추정치 리비전: FY1(0y)·FY2(+1y) 컨센 EPS의 90일 변화율 평균."""
        et=(fd.get("earningsTrend") or {}).get("trend",[]) or []
        revs=[]
        for per in ("0y","+1y"):
            t=next((x for x in et if x.get("period")==per),None)
            if not t: continue
            tr=t.get("epsTrend") or {}
            cur=(tr.get("current") or {}).get("raw"); ago=(tr.get("90daysAgo") or {}).get("raw")
            if cur is not None and ago and ago>0: revs.append(cur/ago-1.0)
        return (sum(revs)/len(revs)) if revs else None
    def yqs(r):
        for att in range(3):
            try:
                j=T.jget(f"https://query2.finance.yahoo.com/v10/finance/quoteSummary/{r['c']}"
                         f"?modules=financialData,assetProfile,earningsTrend&crumb={_up.quote(crumb)}",opener=op,timeout=12)
                fd=(j["quoteSummary"]["result"] or [{}])[0]
                fdd=fd.get("financialData",{}); ap=fd.get("assetProfile",{})
                def v(x): return (x or {}).get("raw") if isinstance(x,dict) else x
                return {**r,"sector":ap.get("sector"),"de":v(fdd.get("debtToEquity")),"cr":v(fdd.get("currentRatio")),
                        "roe":v(fdd.get("returnOnEquity")),"revg":v(fdd.get("revenueGrowth")),
                        "epsg":v(fdd.get("earningsGrowth")),"fcf":v(fdd.get("freeCashflow")),
                        "tp":v(fdd.get("targetMeanPrice")),"tphi":v(fdd.get("targetHighPrice")),
                        "tplo":v(fdd.get("targetLowPrice")),"rec":v(fdd.get("recommendationMean")),
                        "nan":v(fdd.get("numberOfAnalystOpinions")),"op3neg":_op3neg_us(r["c"]),
                        "eps_rev":_eps_rev(fd)}
            except Exception:
                time.sleep(0.5*(att+1))
        return r
    us2=T.pmap(yqs, us, workers=6)
    # 갭필: quoteSummary 실패분(assetProfile 미수신 = 'sector' 키 없음)을 저동시성으로 여러 라운드 재시도
    by={r["c"]:r for r in us2}
    for rnd in range(2):
        miss=[by[c] for c in by if "sector" not in by[c]]
        if not miss: break
        time.sleep(2)
        for r in T.pmap(yqs, miss, workers=5): by[r["c"]]=r
    ok=sum(1 for c in by if "sector" in by[c])
    print(f"[pool] US quoteSummary 커버리지 {ok}/{len(by)} (갭필 후)")
    # 이월(carry-forward): 그래도 실패한 종목은 직전 풀의 컨센서스·재무값 재사용(하루새 거의 불변)
    CF=("sector","de","cr","roe","revg","epsg","fcf","tp","tphi","tplo","rec","nan","op3neg","eps_rev")
    cf=0
    for c in by:
        if "sector" not in by[c] and c in prev:
            p=prev[c]
            for k in CF:
                if p.get(k) is not None: by[c][k]=p.get(k)
            if "sector" in by[c]: by[c]["_cf"]=True; cf+=1
    if cf: print(f"[pool] US carry-forward {cf}종(직전 풀 값 이월)")
    us2=[by[r["c"]] for r in us]
    for i,r in enumerate(us2):
        gg=[min(x,3.0) for x in (r.get("revg"),r.get("epsg")) if x is not None]
        r["g_new"]=(sum(gg)/len(gg) if gg else None); r["growth"]=r["g_new"]
        r["fcfy"]=(r["fcf"]/r["cap"]) if (r.get("fcf") and r.get("cap")) else None
        r["isfin"]="Financial" in (r.get("sector") or "")
        # 컨센서스 목표주가·투자의견 (US: recommendationMean 낮을수록 매수)
        tp=r.get("tp"); rec=r.get("rec")
        r["upside"]=(tp/r["px"]-1) if (tp and tp>0 and r.get("px")) else None
        r["recn"]=((5-rec)/4*100) if rec is not None else None
        r["rev"]=r.get("eps_rev")            # US 리비전 = EPS 추정치 변화율(즉시)
        r.pop("fcf",None)
        r["sym"]=r["c"]; r["name"]=r["n"]; r["px"]=r.get("px"); r["mcap"]=r.get("cap")
        us[i]=r
    _score(us,"c",{"val":[lambda r:(-r["fpe"] if r.get("fpe") else None),
                          lambda r:(-r["pb"] if r.get("pb") else None),
                          lambda r:r.get("divy")],
                   "grw":[lambda r:r.get("g_new")],
                   "mom":[lambda r:r.get("w52"), lambda r:r.get("hi52"), lambda r:r.get("vs200"), lambda r:r.get("rev")],
                   "qly":[lambda r:r.get("roe"), lambda r:r.get("fcfy"),
                          lambda r:(-r["de"] if r.get("de") is not None and not r.get("isfin") else None)]})

def _tp_history(rows):
    """KR 전용: 목표주가를 날짜별로 누적(tp_history.json), 90일 변화율(tp_rev)·추세(tp_trend) 계산 → rev.
    (US는 Yahoo EPS 리비전을 즉시 받으므로 누적 불필요.)"""
    H=T.load_db("tp_history") or {}
    hist=H.get("hist") or {}
    tds=date.today().isoformat()
    for r in rows:
        tp=r.get("tp")
        if tp is None or tp<=0: continue
        hist.setdefault(r["c"],{})[tds]=round(tp,2)
    for c in list(hist):                       # 종목별 최근 90일만 보관
        d=hist[c]
        if len(d)>90:
            for k in sorted(d)[:-90]: d.pop(k,None)
    cutoff=(date.today()-timedelta(days=90)).isoformat()
    for r in rows:                             # 목표주가 추세: 90일 구간 순증감 + 상향 '꾸준함'
        d=hist.get(r["c"]) or {}
        ks=[k for k in sorted(d) if k>=cutoff]
        if not r.get("tp") or len(ks)<2:
            r["tp_rev"]=None; r["tp_trend"]=None; r["rev"]=None; continue
        seq=[d[k] for k in ks]
        levels=[seq[0]]                        # 유의미한 변경만 남긴 계단열
        for p in seq[1:]:
            if levels[-1] and abs(p-levels[-1])/levels[-1]>1e-4: levels.append(p)
        r["tp_rev"]=(levels[-1]/levels[0]-1) if levels[0] else None
        if len(levels)<2:
            r["tp_trend"]="flat"
        else:
            diffs=[levels[i+1]-levels[i] for i in range(len(levels)-1)]
            ups=sum(1 for x in diffs if x>0); downs=sum(1 for x in diffs if x<0)
            net=r["tp_rev"] or 0
            if   ups>=1 and downs==0: r["tp_trend"]="up_steady"    # 꾸준상승(하향 0회)
            elif downs>=1 and ups==0: r["tp_trend"]="down_steady"  # 꾸준하락
            elif net>0.001:  r["tp_trend"]="up"
            elif net<-0.001: r["tp_trend"]="down"
            else: r["tp_trend"]="flat"
        r["rev"]=r["tp_rev"]                    # KR 리비전 = 목표주가 변화율
    T.save_db("tp_history",{"hist":hist})

def build():
    today=date.today()
    d0s,_=T.krx_day_back(today,"stk"); T.krx_day_back(today,"ksq")
    # KR 3거래일 거래대금 평균용 이전일 캐시
    prev=[]; t=datetime.strptime(d0s,"%Y%m%d").date()
    for k in range(1,3):
        dd,_=T.krx_day_back(t-timedelta(days=k),"stk"); prev.append(dd)
        T.krx_day_back(t-timedelta(days=k),"ksq")
    NV=T.naver_bulk()
    base={}
    for mkt in ("stk","ksq"):
        cache=f"{T.CACHE}/krxbase_{mkt}_{d0s}.json"
        rows=json.load(open(cache)) if os.path.exists(cache) else T.krx(f"{mkt}_isu_base_info",d0s)
        if not os.path.exists(cache): json.dump(rows,open(cache,"w"))
        for b in rows: base[b["ISU_SRT_CD"]]=b
    kr=[]
    for mkt in ("stk","ksq"):
        _,d0rows=T.krx_day_back(datetime.strptime(d0s,"%Y%m%d").date(),mkt)
        loads=[{r["ISU_CD"]:r for r in json.load(open(f"{T.CACHE}/krx_{mkt}_{dd}.json"))}
               for dd in prev if dd and os.path.exists(f"{T.CACHE}/krx_{mkt}_{dd}.json")]
        for r in d0rows:
            code=r["ISU_CD"]; b=base.get(code)
            if not b or b.get("SECUGRP_NM")!="주권" or b.get("KIND_STKCERT_TP_NM")!="보통주": continue
            if "스팩" in r["ISU_NM"]: continue
            ldd=b.get("LIST_DD","")
            try: yr=int(ldd[:4])
            except Exception: yr=None
            nv=NV.get(code)
            close=(nv["close"] if nv and nv.get("close") else T.num(r["TDD_CLSPRC"]))
            mcap =(nv["mcap"]  if nv and nv.get("mcap")  else T.num(r["MKTCAP"]))
            chg  =(nv.get("chg_pct") if nv else None)
            _t0=(nv["trdval"] if nv and nv.get("trdval") else T.num(r["ACC_TRDVAL"]))
            vals=[_t0]+[T.num(x[code]["ACC_TRDVAL"]) for x in loads if code in x]
            vals=[v for v in vals if v is not None]
            tv=round(sum(vals)/len(vals)) if vals else None
            if not close or not mcap: continue
            kr.append({"c":code,"n":r["ISU_NM"],"mk":r["MKT_NM"],"px":close,"chg":chg,
                       "cap":mcap,"tv":tv,"yr":yr})
    # US — 캐시된 quotes 재사용(있으면), 없으면 stage1 이 채운다
    us=[]
    uq=f"{T.CACHE}/us_quotes.json"
    if os.path.exists(uq):
        for q in json.load(open(uq)):
            if q.get("quoteType")!="EQUITY": continue
            px=q.get("regularMarketPrice"); cap=q.get("marketCap")
            v3=q.get("averageDailyVolume3Month")
            if not px or not cap: continue
            ft=q.get("firstTradeDateMilliseconds")
            yr=None
            try: yr=datetime.utcfromtimestamp(ft/1000).year if ft else None
            except Exception: pass
            us.append({"c":q["symbol"],"n":(q.get("longName") or q.get("shortName") or "")[:44],
                       "px":px,"chg":q.get("regularMarketChangePercent"),"cap":cap,
                       "tv":round(v3*px) if v3 else None,"yr":yr,
                       "d200":q.get("twoHundredDayAverageChangePercent")})
    # ── 전종목 z-score enrichment (2단계 랭킹용) ──
    try: _enrich_kr(kr, d0s)
    except Exception as e: print("[pool] KR enrich 실패:", repr(e)[:80])
    try: _enrich_us(us)
    except Exception as e: print("[pool] US enrich 실패:", repr(e)[:80])
    try: _tp_history(kr); _score(kr,"c",KR_AXDEF)   # KR만 누적→rev(tp_rev) 세팅 후 M축 재채점
    except Exception as e: print("[pool] tp_history 실패:", repr(e)[:80])
    _pd=T.kr_price_date()
    out={"asof":T.now_kst(),"price_date":_pd,
         "kr":sorted(kr,key=lambda r:-(r["cap"] or 0)),
         "us":sorted(us,key=lambda r:-(r["cap"] or 0))}
    T.save_db("screener_pool",out)
    print(f"screener_pool: KR {len(kr)} · US {len(us)} · price_date {_pd}")
    return out

if __name__=="__main__":
    build()
