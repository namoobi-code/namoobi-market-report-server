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

def _neg_streak(vals):
    """최근 연도부터 연속으로 영업적자인 햇수 (0=적자 아님)."""
    n=0
    for v in reversed(vals or []):
        if v is not None and v<0: n+=1
        else: break
    return n

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
    # (2026-07-19) 빈칸 3-구분 — 아래 fetch 가 '예외'로 실패한 필드만 오류(_err)로 태그.
    #   API 는 성공했는데 값이 없으면(무배당·미커버 등) N/A 이지 오류가 아니다.
    ERRG={"fund":["per","fper","pbr","divy","payout","tp","rec","upside","recn","frgn"],
          "fin":["revg","opg","roe","de","cr","growth","oploss"],
          "tech":["v20","v50","align","rsi","macd","bb","volx","vs200"]}
    def fetch(r):
        o={**r}; eg=set()
        try:
            j=T.jget(f"https://m.stock.naver.com/api/stock/{r['c']}/integration",timeout=10)
            o["tot"]={x["code"]:x.get("value") for x in j.get("totalInfos",[])}
            o["cons"]=j.get("consensusInfo") or {}
            # (2026-07-26) 2차: 실적발표(IR) 예정일 — 같은 응답이라 추가 콜 0. 대형주 위주 제공
            ir=j.get("irScheduleInfo") or {}
            if ir.get("irScheduleDate"): o["ed"]=ir["irScheduleDate"]
        except Exception: eg.add("fund")
        o["_eg"]=eg
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
        except Exception: o["_eg"].add("fin")
        try:
            S=(date.today()-timedelta(days=400)).strftime("%Y%m%d"); E=date.today().strftime("%Y%m%d")
            dch=T.jget(f"https://api.stock.naver.com/chart/domestic/item/{r['c']}/day?startDateTime={S}&endDateTime={E}",timeout=12)
            rows=[x for x in dch if x.get("closePrice")]
            cl=[x["closePrice"] for x in rows]
            if len(cl)>=100: o["ma200"]=cl[-1]/(sum(cl[-200:])/min(200,len(cl)))-1
            # (2026-07-18) 일봉 기술지표 — 같은 시리즈로 추가 계산(네트워크 비용 0). DB(screener_pool)에 저장돼
            # 1일 2회 cron 때만 갱신되는 스냅샷이다. 학습 프레임: 일봉=방향 필터(이평배열·RSI·거래량·MACD·볼린저).
            n=len(cl)
            if n>=60:
                c=cl[-1]
                ma20=sum(cl[-20:])/20; ma50=sum(cl[-50:])/50; ma200v=sum(cl[-200:])/min(200,n)
                o["v20"]=c/ma20-1; o["v50"]=c/ma50-1
                o["align"]="정배열" if ma20>ma50>ma200v else ("역배열" if ma20<ma50<ma200v else "혼조")
                # RSI(14) — Wilder 평활(시리즈 전체)
                g=l=None
                for i in range(1,n):
                    d1=cl[i]-cl[i-1]; up=max(d1,0.0); dn=max(-d1,0.0)
                    if i<14: g=(g or 0)+up; l=(l or 0)+dn
                    elif i==14: g=(g+up)/14; l=(l+dn)/14
                    else: g=(g*13+up)/14; l=(l*13+dn)/14
                if n>14 and (g is not None):
                    o["rsi"]=round(100.0 if l==0 else 100-100/(1+g/l),1)
                # MACD(12,26,9) — EMA 시리즈 + 시그널, 상태코드
                e12=e26=None; macds=[]
                for i,p in enumerate(cl):
                    e12=p if e12 is None else (p*2/13+e12*11/13)
                    e26=p if e26 is None else (p*2/27+e26*25/27)
                    if i>=25: macds.append(e12-e26)
                if len(macds)>=10:
                    sig=None
                    for m0 in macds: sig=m0 if sig is None else (m0*2/10+sig*8/10)
                    mv=macds[-1]
                    o["macd"]=("골든↑" if mv>sig and mv>0 else "골든↓" if mv>sig else
                               "데드↓" if mv<=sig and mv<0 else "데드↑")
                # 볼린저(20,2) %b
                sd=(sum((x-ma20)**2 for x in cl[-20:])/20)**0.5
                if sd>0: o["bb"]=round((c-(ma20-2*sd))/(4*sd)*100,1)   # 0=하단, 100=상단
                # 거래량 배수 = 최근 거래일 ÷ 직전 20일 평균
                vol=[x.get("accumulatedTradingVolume") or 0 for x in rows]
                if len(vol)>=21:
                    va=sum(vol[-21:-1])/20
                    if va>0: o["volx"]=round(vol[-1]/va,2)
                # (2026-07-26) 기간수익률·변동성 — 같은 일봉 시리즈(네트워크 비용 0), fraction 저장
                for lbl,dd in (("r1m",21),("r3m",63),("r6m",126),("r1y",250)):
                    if n>dd and cl[-dd-1]: o[lbl]=round(cl[-1]/cl[-dd-1]-1,4)
                rets=[cl[i]/cl[i-1]-1 for i in range(max(1,n-20),n) if cl[i-1]]
                if len(rets)>=10:
                    mu=sum(rets)/len(rets)
                    o["vol20"]=round((sum((x-mu)**2 for x in rets)/len(rets))**0.5*100,2)
                # (2026-07-18) 장중 증분 재계산용 상태 스냅샷 — 마지막 완결봉 기준.
                # intraday_kr.py가 '상태 + 당일가' O(1) 갱신으로 전종목 지표를 5분마다 실시간화한다.
                st={"pc":c,"n":n,
                    "s19":sum(cl[-19:]), "q19":sum(x*x for x in cl[-19:])}
                if n>14 and (g is not None): st["g"]=g; st["l"]=l
                if e12 is not None: st["e12"]=e12; st["e26"]=e26
                if len(macds)>=10: st["sig"]=sig
                if n>=50: st["s49"]=sum(cl[-49:])
                m=min(199,n-1)
                if m>0: st["s199"]=sum(cl[-m:]); st["m199"]=m
                if len(vol)>=20: st["va"]=sum(vol[-20:])/20
                o["_st"]=st
        except Exception: o["_eg"].add("tech")
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
        frgn=T.num(t.get("foreignRate"))                    # 외국인 소진율(%)
        _dv,_ep=T.num(t.get("dividend")),T.num(t.get("eps")) # 배당성향 = 주당배당/EPS
        payout=(_dv/_ep) if (_dv is not None and _ep and _ep>0) else None
        # 실측 G/Q + 하드컷
        revg,opg=_yoy(fn.get("매출액")),_yoy(fn.get("영업이익"))
        la,le=_last(fn.get("매출액")),fn.get("매출액_E")
        rf=(le/la-1) if (la and le and la>0) else None
        gg=[min(x,3.0) for x in (revg,opg,rf) if x is not None]
        roe=_last(fn.get("ROE")); de=_last(fn.get("부채비율")); cr=_last(fn.get("당좌비율"))
        op3=[v for v in (fn.get("영업이익") or []) if v is not None]
        # (2026-07-26) 1차 필터: PEG·영업이익률·PSR·회전율·흑자전환 (기존 수집값으로 산출)
        opl=_last(fn.get("영업이익"))
        opm=(opl/la) if (opl is not None and la and la>0) else None            # 매출액 대비 (fraction)
        psr=(r["cap"]/(la*1e8)) if (la and la>0 and r.get("cap")) else None    # 시총(원) / 매출(억원→원)
        peg=(fper/(opg*100)) if (fper and opg and opg>0) else None             # PER / 이익성장률(%)
        turn=(r["tv"]/r["cap"]) if (r.get("tv") and r.get("cap")) else None    # fraction
        tob=bool(len(op3)>=2 and op3[-1]>0 and op3[-2]<0)                      # 적자→흑자 전환
        r.update(opm=opm,psr=psr,peg=peg,turn=turn,tob=tob)
        r.update(fper=fper,per=per,pbr=pbr,divy=divy,mom=mom,near52=near52,
                 roe=roe,de=de,cr=cr,revg=revg,opg=opg,g_new=(sum(gg)/len(gg) if gg else None),
                 op3neg=(len(op3)>=3 and all(v<0 for v in op3[-3:])), oploss=_neg_streak(op3),
                 isfin=_isfin(r.get("n")), vs200=r.get("ma200"),
                 tp=tp, rec=rec, upside=upside, recn=recn, frgn=frgn, payout=payout,
                 v20=r.get("v20"), v50=r.get("v50"), align=r.get("align"),
                 rsi=r.get("rsi"), macd=r.get("macd"), bb=r.get("bb"), volx=r.get("volx"))
        r["growth"]=r.get("g_new")
        r["code"]=r["c"]; r["name"]=r["n"]; r["mkt"]=r.get("mk"); r["close"]=r.get("px"); r["mcap"]=r.get("cap")
        if isinstance(r.get("_st"),dict) and hi52: r["_st"]["hi52"]=hi52   # 52주고점 상태 포함
        # (2026-07-19) 예외로 실패한 그룹의 필드 중 실제로 값이 빈 것만 오류(_err)로 표시
        eg=r.get("_eg") or set()
        err=[k for g in eg for k in ERRG.get(g,[]) if r.get(k) is None]
        if err: r["_err"]=err
        r.pop("tot",None); r.pop("fin",None); r.pop("cons",None); r.pop("_eg",None); kr[i]=r
    # 장중 증분용 상태 DB 저장(풀 행에서는 제거)
    try: T.save_db("ta_state", {"st": {r["c"]: r.pop("_st") for r in kr if isinstance(r.get("_st"),dict)}})
    except Exception as e: print("[pool] ta_state 저장 실패:", repr(e)[:70])
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
        r["v50"]=q.get("fiftyDayAverageChangePercent")   # (2026-07-18) US 50일선 필터용
    op,crumb=T.yahoo_opener()
    import urllib.parse as _up
    _p2=int(time.time()); _p1=_p2-5*365*24*3600
    def _op3neg_us(sym):
        """fundamentals-timeseries annualOperatingIncome → 연속 영업적자 연수(0=아님)."""
        try:
            t=T.jget(f"https://query2.finance.yahoo.com/ws/fundamentals-timeseries/v1/finance/timeseries/{sym}"
                     f"?symbol={sym}&type=annualOperatingIncome&period1={_p1}&period2={_p2}&crumb={_up.quote(crumb)}",opener=op,timeout=12)
            res=(t.get("timeseries",{}) or {}).get("result",[]) or []
            for r0 in res:
                arr=r0.get("annualOperatingIncome") or []
                vals=[(x.get("reportedValue",{}) or {}).get("raw") for x in arr if x]
                vals=[x for x in vals if x is not None]
                if vals: return _neg_streak(vals)
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
                         f"?modules=financialData,assetProfile,earningsTrend,summaryDetail&crumb={_up.quote(crumb)}",opener=op,timeout=12)
                fd=(j["quoteSummary"]["result"] or [{}])[0]
                fdd=fd.get("financialData",{}); ap=fd.get("assetProfile",{}); sd=fd.get("summaryDetail",{})
                def v(x): return (x or {}).get("raw") if isinstance(x,dict) else x
                return {**r,"sector":ap.get("sector"),"payout":v(sd.get("payoutRatio")),
                        "opm":v(fdd.get("operatingMargins")),"psr":v(sd.get("priceToSalesTrailing12Months")),
                        "de":v(fdd.get("debtToEquity")),"cr":v(fdd.get("currentRatio")),
                        "roe":v(fdd.get("returnOnEquity")),"revg":v(fdd.get("revenueGrowth")),
                        "epsg":v(fdd.get("earningsGrowth")),"fcf":v(fdd.get("freeCashflow")),
                        "tp":v(fdd.get("targetMeanPrice")),"tphi":v(fdd.get("targetHighPrice")),
                        "tplo":v(fdd.get("targetLowPrice")),"rec":v(fdd.get("recommendationMean")),
                        "nan":v(fdd.get("numberOfAnalystOpinions")),"oploss":_op3neg_us(r["c"]),
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
    CF=("sector","payout","de","cr","roe","revg","epsg","fcf","tp","tphi","tplo","rec","nan","op3neg","oploss","eps_rev","opm","psr")
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
        r["op3neg"]=((r.get("oploss") or 0)>=3)   # 3년 연속 영업적자(파생)
        # (2026-07-26) 1차 필터: PEG(=PER/EPS성장%)·회전율·1Y수익률(52주 변화율, %→fraction)
        fpe1,eg1=r.get("fpe"),r.get("epsg")
        r["peg"]=(fpe1/(eg1*100)) if (fpe1 and eg1 and eg1>0) else None
        r["turn"]=(r["tv"]/r["cap"]) if (r.get("tv") and r.get("cap")) else None
        r["r1y"]=(r["w52"]/100) if r.get("w52") is not None else None
        r["tob"]=None                        # US: 연도별 영업이익 배열 미보유
        r.pop("fcf",None)
        r["sym"]=r["c"]; r["name"]=r["n"]; r["px"]=r.get("px"); r["mcap"]=r.get("cap")
        us[i]=r
    # (2026-07-18) US 2차 기술지표 — Yahoo spark 배치(6mo 일봉, 20심볼/호출 ≈ 261회, 수 분).
    # 거래량배수는 quotes(당일 거래량 ÷ 3개월 평균)로 요청 추가 없음. 이평배열은 ma20(spark)+ma50/200(quotes).
    def _spark_batch(syms):
        try:
            u=("https://query1.finance.yahoo.com/v7/finance/spark?symbols=%s&range=6mo&interval=1d"
               % _up.quote(",".join(syms)))
            j=T.jget(u,opener=op,timeout=15)
            out={}
            for r0 in (j.get("spark",{}) or {}).get("result") or []:
                sym=r0.get("symbol"); resp=(r0.get("response") or [{}])[0]
                cl=(((resp.get("indicators",{}) or {}).get("quote") or [{}])[0].get("close")) or []
                cl=[x for x in cl if x is not None]
                if len(cl)>=30: out[sym]=cl
            return out
        except Exception: return {}
    try:
        codes=[r["c"] for r in us]
        chunks=[codes[i:i+20] for i in range(0,len(codes),20)]
        closes={}
        for res in T.pmap(_spark_batch, chunks, workers=6): closes.update(res)
        ok_ta=0; sts_us={}   # 장중(intraday_us) 증분용 상태
        for r in us:
            q=qmap.get(r["c"]) or {}
            vol,va3=q.get("regularMarketVolume"),q.get("averageDailyVolume3Month")
            if vol and va3: r["volx"]=round(vol/va3,2)
            cl=closes.get(r["c"])
            if not cl or len(cl)<30: continue
            c=cl[-1]; n=len(cl)
            ma20=sum(cl[-20:])/20; r["v20"]=c/ma20-1
            ma50v,ma200v=q.get("fiftyDayAverage"),q.get("twoHundredDayAverage")
            if ma50v and ma200v:
                r["align"]="정배열" if ma20>ma50v>ma200v else ("역배열" if ma20<ma50v<ma200v else "혼조")
            g=l=None
            for i2 in range(1,n):
                d1=cl[i2]-cl[i2-1]; up=max(d1,0.0); dn=max(-d1,0.0)
                if i2<14: g=(g or 0)+up; l=(l or 0)+dn
                elif i2==14: g=(g+up)/14; l=(l+dn)/14
                else: g=(g*13+up)/14; l=(l*13+dn)/14
            if n>14 and (g is not None):
                r["rsi"]=round(100.0 if l==0 else 100-100/(1+g/l),1)
            e12=e26=None; macds=[]
            for i2,p in enumerate(cl):
                e12=p if e12 is None else (p*2/13+e12*11/13)
                e26=p if e26 is None else (p*2/27+e26*25/27)
                if i2>=25: macds.append(e12-e26)
            if len(macds)>=10:
                sig=None
                for m0 in macds: sig=m0 if sig is None else (m0*2/10+sig*8/10)
                mv=macds[-1]
                r["macd"]=("골든↑" if mv>sig and mv>0 else "골든↓" if mv>sig else
                           "데드↓" if mv<=sig and mv<0 else "데드↑")
            sd=(sum((x-ma20)**2 for x in cl[-20:])/20)**0.5
            if sd>0: r["bb"]=round((c-(ma20-2*sd))/(4*sd)*100,1)
            # (2026-07-26) US 기간수익률·변동성 — spark 6mo 시리즈(126봉)
            for lbl,dd in (("r1m",21),("r3m",63),("r6m",120)):   # spark 6mo ≈125봉 — 125는 성립 안 함
                if n>dd and cl[-dd-1]: r[lbl]=round(c/cl[-dd-1]-1,4)
            rets=[cl[i2]/cl[i2-1]-1 for i2 in range(max(1,n-20),n) if cl[i2-1]]
            if len(rets)>=10:
                mu=sum(rets)/len(rets)
                r["vol20"]=round((sum((x-mu)**2 for x in rets)/len(rets))**0.5*100,2)
            # 장중(intraday_us) 증분 상태 — RSI·MACD·볼린저·20일선용 (이평50/200·거래량평균은 quotes가 매회 제공)
            stu={"pc":c,"s19":sum(cl[-19:]),"q19":sum(x*x for x in cl[-19:])}
            if n>14 and (g is not None): stu["g"]=g; stu["l"]=l
            if e12 is not None: stu["e12"]=e12; stu["e26"]=e26
            if len(macds)>=10: stu["sig"]=sig
            sts_us[r["c"]]=stu
            ok_ta+=1
        # spark 누락 종목은 직전 풀 값 이월
        cfta=0
        for r in us:
            if r.get("rsi") is None and r["c"] in prev:
                p=prev[r["c"]]
                for k in ("v20","align","rsi","macd","bb","volx"):
                    if r.get(k) is None and p.get(k) is not None: r[k]=p[k]
                if r.get("rsi") is not None: cfta+=1
        try: T.save_db("ta_state_us", {"st": sts_us})
        except Exception as e: print("[pool] ta_state_us 저장 실패:", repr(e)[:60])
        print(f"[pool] US 기술지표(spark) {ok_ta}/{len(us)} (+이월 {cfta})")
    except Exception as e:
        print("[pool] US spark 실패:", repr(e)[:80])
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

def _kis_flow(kr):
    """(2026-07-26) KR 전종목 외인·기관 수급 — KIS 종목별 투자자(최근 30거래일).
       fnb20/onb20 = 20거래일 누적 순매수 금액(억원, pbmn 백만원/100 — 실측 검증)
       fst/ost     = 최근 연속 순매수일 수(수량 기준)
       레이트리밋: workers 4 × sleep 0.05 ≈ 초당 15콜 미만 (KIS 한도 20/s)"""
    import kis_api as K
    c=K._creds(); tok=K._token(c)
    ok=[0]
    def one(r):
        try:
            time.sleep(0.05)
            j=K._get(c,tok,"/uapi/domestic-stock/v1/quotations/inquire-investor","FHKST01010900",
                     {"FID_COND_MRKT_DIV_CODE":"J","FID_INPUT_ISCD":r["c"]},tries=2)
            rows=j.get("output") or []          # 최신→과거
            if not rows: return r
            fa=[T.num(x.get("frgn_ntby_tr_pbmn")) for x in rows]
            oa=[T.num(x.get("orgn_ntby_tr_pbmn")) for x in rows]
            fq=[T.num(x.get("frgn_ntby_qty")) for x in rows]
            oq=[T.num(x.get("orgn_ntby_qty")) for x in rows]
            def s(a,nn):
                v=[x for x in a[:nn] if x is not None]
                return round(sum(v)/100,1) if v else None   # 백만원 → 억원
            def streak(a):
                k=0
                for x in a:
                    if x is not None and x>0: k+=1
                    else: break
                return k
            r["fnb20"]=s(fa,20); r["onb20"]=s(oa,20)
            r["fst"]=streak(fq); r["ost"]=streak(oq)
            ok[0]+=1
        except Exception: pass
        # (2026-07-26) 2차: 공매도 비중 — KIS 공매도 일별추이(같은 워커에서 순차 호출)
        #   sr = 최근 거래일 공매도 거래량 비중(%) · sr5 = 최근 5일 평균
        try:
            time.sleep(0.05)
            j2=K._get(c,tok,"/uapi/domestic-stock/v1/quotations/daily-short-sale","FHPST04830000",
                      {"FID_COND_MRKT_DIV_CODE":"J","FID_INPUT_ISCD":r["c"],
                       "FID_INPUT_DATE_1":"","FID_INPUT_DATE_2":""},tries=2)
            rows2=j2.get("output2") or []          # 최신→과거
            rl=[T.num(x.get("ssts_vol_rlim")) for x in rows2]
            if rl and rl[0] is not None: r["sr"]=round(rl[0],2)
            v5=[x for x in rl[:5] if x is not None]
            if v5: r["sr5"]=round(sum(v5)/len(v5),2)
            ok2[0]+=1
        except Exception: pass
        return r
    ok2=[0]
    T.pmap(one, kr, workers=4)
    print(f"[pool] KR 수급(KIS) {ok[0]}/{len(kr)} · 공매도 {ok2[0]}/{len(kr)}")

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
            ed=None   # (2026-07-26) 2차: 다음 어닝일 — quotes.earningsTimestamp(추가 콜 0)
            try:
                ets=q.get("earningsTimestamp")
                if ets: ed=datetime.utcfromtimestamp(ets).strftime("%Y-%m-%d")
            except Exception: pass
            us.append({"c":q["symbol"],"n":(q.get("longName") or q.get("shortName") or "")[:44],
                       "px":px,"chg":q.get("regularMarketChangePercent"),"cap":cap,
                       "tv":round(v3*px) if v3 else None,"yr":yr,"ed":ed,
                       "d200":q.get("twoHundredDayAverageChangePercent")})
    # ── 전종목 z-score enrichment (2단계 랭킹용) ──
    try: _enrich_kr(kr, d0s)
    except Exception as e: print("[pool] KR enrich 실패:", repr(e)[:80])
    try: _kis_flow(kr)
    except Exception as e: print("[pool] KR 수급(KIS) 실패:", repr(e)[:80])
    # (2026-07-20) KR 대차잔고(lb)·대차잔고비율(lbr) — 금융위 주식대차정보(일괄 rank, 1일 1콜)
    try:
        import lend_borrow; lend_borrow.enrich(kr)
    except Exception as e: print("[pool] KR 대차잔고 실패:", repr(e)[:80])
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
    # (2026-07-20) 재빌드 직후 대차잔고 재패치 — 안 하면 lb/lbr 가 매 빌드 때 지워진다
    try:
        import fetch_lending
        fetch_lending.build()
    except Exception as e:
        print("[pool] fetch_lending 실패:", repr(e)[:80])
    # (2026-07-20) 미국 종목 한글명(kn) 재패치 — 재빌드 때마다 지워지므로 대차잔고와 동일하게 복원
    try:
        import fetch_us_krname
        fetch_us_krname.patch_pool()
    except Exception as e:
        print("[pool] us_krname 패치 실패:", repr(e)[:80])
