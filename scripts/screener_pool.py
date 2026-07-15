#!/usr/bin/env python3
# screener_pool.py — 인터랙티브 스크리너용 '전종목 풀'.
# stage1 과 같은 구조(보통주/EQUITY·ETF/스팩 제외)이되 값 임계(시총·가격·거래대금)는 적용하지 않는다.
# 클라이언트가 필드로 실시간 필터링한다. 하루 2회 cron(장 마감 후) 갱신.
import os, sys, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from datetime import date, datetime, timedelta
import ta_screen as T

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
    _pd=T.kr_price_date()
    out={"asof":T.now_kst(),"price_date":_pd,
         "kr":sorted(kr,key=lambda r:-(r["cap"] or 0)),
         "us":sorted(us,key=lambda r:-(r["cap"] or 0))}
    T.save_db("screener_pool",out)
    print(f"screener_pool: KR {len(kr)} · US {len(us)} · price_date {_pd}")
    return out

if __name__=="__main__":
    build()
