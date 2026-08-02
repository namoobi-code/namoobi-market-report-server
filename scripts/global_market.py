#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
global_market.py — 글로벌시황 탭 데이터 (2026-08-01 신설)
미래에셋 '국내외 주요지수' 리스트 재현: 지수·선물·상품·환율·암호화폐 + KRX 세부지수(T+1).

소스 (전 심볼 2026-08-01 실측):
  야후 v8 chart  — 해외지수·선물·상품·환율 (지수 ~15분 지연 · 선물/환율 실시간급) + 1년 일봉 이력
  네이버        — KOSPI/KOSDAQ/KOSPI200 실시간(T+0) 현재가 보강 · TOPIX(.TOPX)·베트남 호치민(.VNI)
  업비트        — 암호화폐 KRW 실시간 + 일봉 365
  KRX OPENAPI   — KRX300·BBIG·TOP10 시리즈·코스닥150 등 (T+1 종가, 이력은 매일 누적)
불가: 러시아 RTS(거래정지)·항셍종합(HSCI)·항셍 레드칩(R). (하노이·상해A/B·심천A/B·CSI100·FTSE MIB·IBEX·OMXS30은 2026-08-02 네이버로 추가)

산출: data/db/global_market.json  (표: 그룹·현재가·등락·기간수익률·스파크60)
      data/db/global_hist.json    (종목 클릭 차트용 1년 일봉 {sym:{t,v}})
      data/db/global_krx_hist.json (KRX 세부지수 일별 누적)
cron: */10 * * * *  (야후 ~75콜/회·스레드 12 — 1분 내 완료)
"""
import json, time, urllib.request, urllib.parse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, date, timedelta
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DB = BASE / "data" / "db"
H = {"User-Agent": "Mozilla/5.0 (namoobi)"}

def jget(url, timeout=15, tries=2):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=H)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception:
            if i == tries - 1: return None
            time.sleep(0.5)

# (그룹, 심볼, 이름, 소스, 표시배수, 소수점)  src: Y=야후 N=네이버(이력은 야후 병행 시 심볼)
U = [
 ("kr","^KS11","KOSPI","NY",1,2), ("kr","^KQ11","KOSDAQ","NY",1,2), ("kr","^KS200","KOSPI200","NY",1,2),
 ("kr","NAVKR.KPI100","코스피 100","NK",1,2), ("kr","NAVKR.KVALUE","코리아 밸류업 지수","NK",1,2),
 ("us","^DJI","다우 산업","Y",1,2), ("us","^DJT","다우 운송","Y",1,2), ("us","^IXIC","나스닥 종합","Y",1,2),
 ("us","^NDX","나스닥 100","Y",1,2), ("us","^GSPC","S&P 500","Y",1,2), ("us","^SOX","필라델피아 반도체","Y",1,2),
 ("us","^NYA","NYSE 종합","Y",1,2), ("us","^XAX","아멕스 종합","Y",1,2), ("us","^VIX","VIX","Y",1,2),
 ("us","^RUT","러셀 2000","Y",1,2),
 ("us","NQ=F","E-mini 나스닥100 선물","Y",1,2), ("us","ES=F","E-mini S&P500 선물","Y",1,2),
 ("us","YM=F","다우 선물","Y",1,2), ("us","RTY=F","러셀2000 선물","Y",1,2),
 ("as","000001.SS","상해종합","Y",1,2), ("as","399106.SZ","심천종합지수","Y",1,2), ("as","399001.SZ","심천성분지수","Y",1,2),
 ("as","000300.SS","CSI300","Y",1,2), ("as","000688.SS","과창판 50","Y",1,2), ("as","399006.SZ","차이넥스트","Y",1,2),
 ("as","NAV.SSEA","상해 A","N",1,2), ("as","NAV.SSEB","상해 B","N",1,2),
 ("as","NAV.SZSA","심천 A","N",1,2), ("as","NAV.SZSB","심천 B","N",1,2), ("as","NAV.CSI100","CSI100","N",1,2),
 ("as","NF.SFCc1","China A50 선물","NF",1,2),
 ("as","^HSI","항셍","Y",1,2), ("as","NF.HSIc1","항셍 선물","NF",1,2),
 ("as","^HSCE","항셍 차이나기업(H)","Y",1,2), ("as","NF.HCEIc1","홍콩H 선물","NF",1,2),
 ("as","HSTECH.HK","항셍 테크지수","Y",1,2),
 ("as","^N225","니케이225","Y",1,2), ("as","NF.SSIcm1","니케이225 선물","NF",1,2), ("as","NAV.TOPX","TOPIX","N",1,2),
 ("as","NAV.VNI","베트남 호치민","N",1,2), ("as","NAV.HNXI","베트남 하노이","N",1,2),
 ("as","^TWII","대만 가권","Y",1,2), ("as","^BSESN","인도 SENSEX","Y",1,2), ("as","^SET.BK","태국 SET","Y",1,2),
 ("as","^KLSE","말레이시아 KLCI","Y",1,2), ("as","^JKSE","인도네시아 IDX종합","Y",1,2),
 ("as","PSEI.PS","필리핀","Y",1,2), ("as","^AORD","호주 ALL ORDS","Y",1,2), ("as","^AXJO","호주 ASX 200","Y",1,2),
 ("eu","^STOXX50E","유로스톡스 50","Y",1,2), ("eu","NF.STXEc1","유로스톡스50 선물","NF",1,2),
 ("eu","^FTSE","영국 FTSE 100","Y",1,2), ("eu","^GDAXI","독일 DAX 40","Y",1,2), ("eu","NF.FDXc1","독일 DAX 선물","NF",1,2),
 ("eu","^FCHI","프랑스 CAC 40","Y",1,2), ("eu","^BFX","벨기에 BEL-20","Y",1,2), ("eu","^AEX","네덜란드 AEX","Y",1,2),
 ("eu","PSI20.LS","포르투갈 PSI20","Y",1,2), ("eu","GD.AT","그리스 종합","Y",1,2),
 ("eu","FTSEMIB.MI","이탈리아 FTSE MIB","Y",1,2), ("eu","NAV.IBEX","스페인 IBEX 35","N",1,2),
 ("eu","NAV.OMXS30","스웨덴 OMXS30","N",1,2),
 ("eu","^ISEQ","아일랜드 ISEQ","Y",1,2), ("eu","NAV.OMXC20","덴마크 OMXC20","N",1,2),
 ("eu","^OMXH25","핀란드 OMXH25","Y",1,2), ("eu","NAV.BUX","헝가리 BUX","N",1,2),
 ("eu","^GSPTSE","캐나다 S&P TSX","Y",1,2), ("eu","^BVSP","브라질 BOVESPA","Y",1,2),
 ("eu","^MXX","멕시코 IPC","Y",1,2), ("eu","^MERV","아르헨티나 MERVAL","Y",1,1), ("eu","^IPSA","칠레 IPSA","Y",1,2),
 ("cmd","CL=F","WTI","Y",1,2), ("cmd","BZ=F","브렌트유","Y",1,2), ("cmd","NG=F","천연가스","Y",1,3),
 ("cmd","GC=F","금","Y",1,1), ("cmd","SI=F","은","Y",1,3), ("cmd","HG=F","구리","Y",1,4),
 ("cmd","ZC=F","옥수수","Y",1,1), ("cmd","ZS=F","대두","Y",1,1), ("cmd","ZW=F","소맥","Y",1,1),
 ("cmd","ZR=F","쌀","Y",1,3), ("cmd","ZO=F","귀리","Y",1,1),
 ("cmd","HO=F","난방유","Y",1,3), ("cmd","ND.CMDT_GO","가스오일(ICE)","ND",1,2), ("cmd","ND.OIL_DU","두바이유","ND",1,2),
 ("cmd","PL=F","백금","Y",1,1), ("cmd","PA=F","팔라듐","Y",1,1), ("cmd","ND.GOLD_KR","국내 금(원/g)","ND",1,2),
 ("cmd","ND.CMDT_PDY","납(LME)","ND",1,2), ("cmd","ND.CMDT_ZDY","아연(LME)","ND",1,2),
 ("cmd","ND.CMDT_NDY","니켈(LME)","ND",1,2), ("cmd","ND.CMDT_AAY","알루미늄합금(LME)","ND",1,2),
 ("cmd","ND.CMDT_SDY","주석(LME)","ND",1,2),
 ("cmd","SB=F","설탕","Y",1,2), ("cmd","ZM=F","대두박","Y",1,1), ("cmd","ZL=F","대두유","Y",1,2),
 ("cmd","CT=F","면화","Y",1,2), ("cmd","OJ=F","오렌지주스","Y",1,2), ("cmd","KC=F","커피","Y",1,1),
 ("cmd","CC=F","코코아","Y",1,0),
 ("cmd","ND.OIL_GSL","휘발유(국내 원/L)","ND",1,2), ("cmd","ND.OIL_LO","경유(국내 원/L)","ND",1,2),
 ("fx","DX-Y.NYB","US Dollar Index","Y",1,3), ("fx","KRW=X","원/달러","Y",1,2),
 ("fx","JPYKRW=X","원/일본 엔(100)","Y",100,2), ("fx","CNYKRW=X","원/중국 위안","ND",1,2),
 ("fx","EURKRW=X","원/유로","Y",1,2), ("fx","GBPKRW=X","원/영국 파운드","Y",1,2),
 ("fx","HKDKRW=X","원/홍콩 달러","Y",1,2), ("fx","AUDKRW=X","원/호주 달러","Y",1,2),
 ("fx","SGDKRW=X","원/싱가폴 달러","Y",1,2), ("fx","CADKRW=X","원/캐나다 달러","Y",1,2),
 ("fx","INRKRW=X","원/인도 루피","Y",1,2), ("fx","IDRKRW=X","원/인니 루피아(100)","Y",100,3),
 ("fx","BRLKRW=X","원/브라질 레알","ND",1,2), ("fx","TWDKRW=X","원/대만 달러","Y",1,2),
 ("fx","CHFKRW=X","원/스위스 프랑","Y",1,2), ("fx2","NZDKRW=X","원/뉴질랜드 달러","Y",1,2),
 ("fx2","SEKKRW=X","원/스웨덴 크로나","ND",1,2), ("fx2","CZKKRW=X","원/체코 코루나","ND",1,2),
 ("fx2","CLPKRW=X","원/칠레 페소","ND",1,3), ("fx2","TRYKRW=X","원/튀르키예 리라","ND",1,2),
 ("fx","EURUSD=X","달러/유로","Y",1,4),
 ("fx","GBPUSD=X","달러/영국 파운드","Y",1,4), ("fx","JPY=X","달러/엔","Y",1,2), ("fx","AUDUSD=X","달러/호주 달러","Y",1,4),
 ("fx","MXN=X","달러/멕시코 페소","Y",1,2), ("fx2","ZAR=X","달러/남아공 랜드","Y",1,2),
 ("fx2","NOK=X","달러/노르웨이 크로네","Y",1,4), ("fx2","DKK=X","달러/덴마크 크로네","Y",1,4),
 ("fx2","PLN=X","달러/폴란드 즈워티","Y",1,4), ("fx2","THB=X","달러/태국 바트","Y",1,2),
 ("fx2","PHP=X","달러/필리핀 페소","Y",1,2), ("fx2","VND=X","달러/베트남 동","Y",1,0),
 ("fx2","MYR=X","달러/말레이시아 링깃","Y",1,4), ("fx2","SAR=X","달러/사우디 리얄","Y",1,4),
 ("fx2","AED=X","달러/UAE 디르함","Y",1,4), ("fx2","ILS=X","달러/이스라엘 세켈","Y",1,4),
 ("fx2","ARS=X","달러/아르헨티나 페소","Y",1,1), ("fx2","COP=X","달러/콜롬비아 페소","Y",1,1),
 ("fx2","HUF=X","달러/헝가리 포린트","Y",1,2), ("fx2","RUB=X","달러/러시아 루블(역외)","Y",1,2),
 ("fx","CNY=X","달러/중국 위안","Y",1,4), ("fx","HKD=X","달러/홍콩 달러","Y",1,4),
 ("fx","TWD=X","달러/대만 달러","Y",1,2), ("fx","SGD=X","달러/싱가폴 달러","Y",1,4),
 ("fx","CHF=X","달러/스위스 프랑","Y",1,4), ("fx","CAD=X","달러/캐나다 달러","Y",1,4),
 ("fx","BRL=X","달러/브라질 레알","Y",1,4), ("fx2","TRY=X","달러/튀르키예 리라","Y",1,2),
 ("fx2","UAH=X","달러/우크라이나 흐리브냐","Y",1,2),
 ("me","^TASI.SR","사우디 TASI","Y",1,2), ("me","^TA125.TA","이스라엘 TA-125","Y",1,2),
 ("me","DFMGI.AE","두바이 DFM","Y",1,2), ("me","^J203.JO","남아공 JSE 올셰어","Y",1,2),
 ("me","^CASE30","이집트 EGX30","Y",1,2),
 ("cr","KRW-BTC","비트코인","U",1,0), ("cr","KRW-ETH","이더리움","U",1,0),
 ("cr","KRW-SOL","솔라나","U",1,0), ("cr","KRW-XRP","리플","U",1,0),
]
# (2026-08-02) 환율 — 기타 통화(네이버 국제시장 4페이지 전체) · 표는 접힘(더보기), 소수점은 값 크기 자동
FX2 = [("JOD","요르단 디나르"),("MAD","모로코 디르함"),("MOP","마카오 파타카"),("GMD","감비아 달라시"),
 ("GTQ","과테말라 케트살"),("GNF","기니 프랑"),("NAD","나미비아 달러"),("NGN","나이지리아 나이라"),
 ("NPR","네팔 루피"),("NIO","니카라과 코르도바"),("XCD","동카리브 달러"),("DJF","지부티 프랑"),
 ("LAK","라오스 킵"),("LBP","레바논 파운드"),("LSL","레소토 로티"),("RON","루마니아 레우"),
 ("RWF","르완다 프랑"),("MGA","마다가스카르 아리아리"),("MWK","말라위 콰차"),("MKD","마케도니아 디나르"),
 ("MUR","모리셔스 루피"),("MDL","몰도바 레우"),("MVR","몰디브 루피야"),("BHD","바레인 디나르"),
 ("BBD","바베이도스 달러"),("BSD","바하마 달러"),("BDT","방글라데시 타카"),("BZD","벨리즈 달러"),
 ("BWP","보츠와나 풀라"),("BOB","볼리비아 볼리비아노"),("BIF","부룬디 프랑"),("BND","브루나이 달러"),
 ("LYD","리비아 디나르"),("SCR","세이셸 루피"),("SOS","소말리아 실링"),("LKR","스리랑카 루피"),
 ("SZL","에스와티니 릴랑게니"),("ISK","아이슬란드 크로나"),("HTG","아이티 구르드"),("ALL","알바니아 렉"),
 ("DZD","알제리 디나르"),("ETB","에티오피아 비르"),("SVC","엘살바도르 콜론"),("YER","예멘 리얄"),
 ("OMR","오만 리알"),("HNL","온두라스 렘피라"),("UGX","우간다 실링"),("UYU","우루과이 페소"),
 ("UZS","우즈베키스탄 숨"),("IQD","이라크 디나르"),("JMD","자메이카 달러"),("XAF","중앙아프리카 프랑"),
 ("KZT","카자흐스탄 텡게"),("QAR","카타르 리얄"),("KES","케냐 실링"),("CVE","카보베르데 에스쿠도"),
 ("KMF","코모로 프랑"),("CRC","코스타리카 콜론"),("CUP","쿠바 페소"),("KWD","쿠웨이트 디나르"),
 ("TZS","탄자니아 실링"),("TND","튀니지 디나르"),("TTD","트리니다드 달러"),("PAB","파나마 발보아"),
 ("PYG","파라과이 과라니"),("PKR","파키스탄 루피"),("PGK","파푸아뉴기니 키나"),("PEN","페루 솔"),
 ("XPF","태평양 프랑"),("FJD","피지 달러"),("EGP","이집트 파운드"),("IRR","이란 리얄")]
U += [("fx2", c + "=X", "달러/" + n, "Y", 1, None) for c, n in FX2]
U += [("fx2", "ND.FX_USDGEL", "달러/조지아 라리", "ND", 1, None)]   # 야후 미제공 — 네이버 일별시세

NAVER_LIVE = {"^KS11": "KOSPI", "^KQ11": "KOSDAQ", "^KS200": "KPI200"}   # T+0 현재가 보강
NAVER_IDX  = {"NAV.TOPX": ".TOPX", "NAV.VNI": ".VNI", "NAV.HNXI": ".HNXI", "NAV.SSEA": ".SSEA",
              "NAV.SSEB": ".SSEB", "NAV.SZSA": ".SZSA", "NAV.SZSB": ".SZSB", "NAV.CSI100": ".CSI100",
              "NAV.IBEX": ".IBEX", "NAV.OMXS30": ".OMXS30", "NAV.OMXC20": ".OMXC20", "NAV.BUX": ".BUX"}
NK_CODES = {"NAVKR.KPI100": "KPI100", "NAVKR.KVALUE": "KVALUE"}   # 네이버 국내지수(실시간+이력) — 2026-08-02 실측
NAVER_HIST_FB = {"399106.SZ": ".SZSC"}   # 야후가 시세만 주는 심볼의 이력 대체(2026-08-02 실측)
# (2026-08-02) 텐센트 kline — 야후·네이버 모두 이력 미제공(차이넥스트·과창판50·항셍테크).
#   이스트머니는 서버(해외 IP)에서 차단되어 텐센트(web.ifzq.gtimg.cn)로 확정 — 서버 실측 정상.
EM_HIST = {"399006.SZ": "sz399006", "000688.SS": "sh000688", "HSTECH.HK": "hkHSTECH"}
# (2026-08-02) 선물 만기 주기 메타 — 표의 취득시점 옆에 표기(연속선물이라 롤오버는 소스가 자동)
FUT_CYCLE = {
    "ES=F": "분기물(3·6·9·12월)", "NQ=F": "분기물(3·6·9·12월)", "YM=F": "분기물(3·6·9·12월)", "RTY=F": "분기물(3·6·9·12월)",
    "CL=F": "매월물", "BZ=F": "매월물", "NG=F": "매월물", "HO=F": "매월물", "ND.CMDT_GO": "매월물",
    "GC=F": "격월물(2·4·6·8·10·12월)", "SI=F": "액티브월(1·3·5·7·9·12월)", "HG=F": "액티브월(3·5·7·9·12월)",
    "PL=F": "액티브월(1·4·7·10월)", "PA=F": "액티브월(3·6·9·12월)",
    "ZC=F": "액티브월(3·5·7·9·12월)", "ZW=F": "액티브월(3·5·7·9·12월)", "ZO=F": "액티브월(3·5·7·9·12월)",
    "ZS=F": "액티브월(1·3·5·7·8·9·11월)", "ZM=F": "액티브월(연 8회)", "ZL=F": "액티브월(연 8회)",
    "ZR=F": "액티브월(1·3·5·7·9·11월)", "SB=F": "액티브월(3·5·7·10월)", "CT=F": "액티브월(3·5·7·10·12월)",
    "OJ=F": "액티브월(1·3·5·7·9·11월)", "KC=F": "액티브월(3·5·7·9·12월)", "CC=F": "액티브월(3·5·7·9·12월)",
    "NF.HSIc1": "매월물", "NF.HCEIc1": "매월물", "NF.SFCc1": "매월물",
    "NF.SSIcm1": "분기물(3·6·9·12월)", "NF.STXEc1": "분기물(3·6·9·12월)", "NF.FDXc1": "분기물(3·6·9·12월)"}

# (2026-08-02) 네이버 해외선물 — 항셍·홍콩H·A50·니케이·유로스톡스·DAX 선물 (야후 미제공)
NF_CODES = {"NF.HSIc1": "HSIc1", "NF.HCEIc1": "HCEIc1", "NF.SFCc1": "SFCc1",
            "NF.SSIcm1": "SSIcm1", "NF.STXEc1": "STXEc1", "NF.FDXc1": "FDXc1"}

def naver_fut(code):
    j = jget(f"https://api.stock.naver.com/futures/{urllib.parse.quote(code)}/basic")
    try:
        f = lambda x: float(str(x).replace(",", ""))
        return {"px": f(j["closePrice"]), "at": (j.get("localTradedAt") or "")[5:10].replace("-", "/") + " 종가(네이버)"}
    except Exception:
        return None

def naver_fut_hist(code, pages=9):
    t, v = [], []
    f = lambda x: float(str(x).replace(",", ""))
    for pg in range(1, pages + 1):
        j = jget(f"https://api.stock.naver.com/futures/{urllib.parse.quote(code)}/price?pageSize=50&page={pg}") or []
        if not j: break
        for x in j:
            try: t.append(x["localTradedAt"][:10].replace("-", "")); v.append(f(x["closePrice"]))
            except Exception: pass
        if len(j) < 50: break
    pair = sorted(zip(t, v))
    return {"t": [a for a, b in pair], "v": [b for a, b in pair]}

# (2026-08-02) 표기 통일 — 야후는 EURUSD 등 "xx/달러"만 제공 → 달러/xx 기준으로 역수 변환
INVERT = {"EURUSD=X", "GBPUSD=X", "AUDUSD=X"}

def em_hist(code):
    j = jget(f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={code},day,,,500,qfq") or {}
    d = (j.get("data") or {}).get(code) or {}
    kl = d.get("day") or d.get("qfqday") or []
    t, v = [], []
    for p in kl:
        try: t.append(str(p[0]).replace("-", "")); v.append(float(p[2]))   # [date,open,close,...]
        except Exception: pass
    return {"t": t, "v": v}
# (2026-08-02) 네이버 marketindex 일별시세(HTML) — 야후 미제공 상품(LME 현물·가스오일·두바이유·국내금·국내유가)
ND_CODES = {"ND.CMDT_GO": ("worldDailyQuote", "CMDT_GO", 2), "ND.OIL_DU": ("worldDailyQuote", "OIL_DU", 2),
            "ND.CMDT_PDY": ("worldDailyQuote", "CMDT_PDY", 2), "ND.CMDT_ZDY": ("worldDailyQuote", "CMDT_ZDY", 2),
            "ND.CMDT_NDY": ("worldDailyQuote", "CMDT_NDY", 2), "ND.CMDT_AAY": ("worldDailyQuote", "CMDT_AAY", 2),
            "ND.CMDT_SDY": ("worldDailyQuote", "CMDT_SDY", 2), "ND.GOLD_KR": ("goldDailyQuote", "CMDT_GC", None),
            "ND.OIL_GSL": ("oilDailyQuote", "OIL_GSL", None), "ND.OIL_LO": ("oilDailyQuote", "OIL_LO", None),
            "CNYKRW=X": ("exchangeDailyQuote", "FX_CNYKRW", None), "BRLKRW=X": ("exchangeDailyQuote", "FX_BRLKRW", None),
            "SEKKRW=X": ("exchangeDailyQuote", "FX_SEKKRW", None), "CZKKRW=X": ("exchangeDailyQuote", "FX_CZKKRW", None),
            "CLPKRW=X": ("exchangeDailyQuote", "FX_CLPKRW", None), "TRYKRW=X": ("exchangeDailyQuote", "FX_TRYKRW", None),
            "ND.FX_USDGEL": ("worldDailyQuote", "FX_USDGEL", 2)}

def yahoo_1y(sym):
    j = jget(f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(sym)}?range=2y&interval=1d")
    try:
        r = j["chart"]["result"][0]; m = r["meta"]
        ts = r["timestamp"]; cl = r["indicators"]["quote"][0]["close"]
        t, v = [], []
        for k, c in zip(ts, cl):
            if c is None: continue
            t.append(datetime.utcfromtimestamp(k).strftime("%Y%m%d")); v.append(round(c, 6))
        px = m.get("regularMarketPrice"); pc = m.get("chartPreviousClose") or m.get("previousClose")
        if px is not None and (not v or t[-1] < datetime.utcnow().strftime("%Y%m%d")):
            pass
        ptime = m.get("regularMarketTime")
        sn = m.get("shortName") or ""
        return {"t": t, "v": v, "px": px, "pc": pc, "sn": sn,
                "at": datetime.utcfromtimestamp(ptime).strftime("%m/%d %H:%M") + "Z" if ptime else None}
    except Exception:
        return None

def naver_idx(code):
    j = jget(f"https://api.stock.naver.com/index/{urllib.parse.quote(code)}/basic")
    try:
        f = lambda s: float(str(s).replace(",", ""))
        return {"px": f(j["closePrice"]), "chg": f(j.get("compareToPreviousClosePrice") or 0),
                "at": (j.get("localTradedAt") or "")[5:16].replace("T", " ")}
    except Exception:
        return None

def naver_kr(code):
    j = jget(f"https://m.stock.naver.com/api/index/{code}/basic")
    try:
        f = lambda s: float(str(s).replace(",", ""))
        return {"px": f(j["closePrice"]), "chg": f(j.get("compareToPreviousClosePrice") or 0)}
    except Exception:
        return None

def naver_kr_hist(code, pages=6):
    """국내지수 일봉 이력(최근 ~1.2년) — 야후 ^KS200 결측 대체 (2026-08-02)."""
    t, v = [], []
    f = lambda s: float(str(s).replace(",", ""))
    for pg in range(1, pages + 1):
        j = jget(f"https://m.stock.naver.com/api/index/{code}/price?pageSize=50&page={pg}") or []
        if not j: break
        for x in j:
            try: t.append(x["localTradedAt"].replace("-", "")); v.append(f(x["closePrice"]))
            except Exception: pass
        if len(j) < 50: break
    pair = sorted(zip(t, v))
    return {"t": [a for a, b in pair], "v": [b for a, b in pair]}


def naver_world_hist(code, pages=6):
    """해외지수(worldstock) 일봉 이력 — TOPIX(.TOPX)·베트남(.VNI) 등."""
    import urllib.parse as up
    t, v = [], []
    f = lambda x: float(str(x).replace(",", ""))
    for pg in range(1, pages + 1):
        j = jget(f"https://api.stock.naver.com/index/{up.quote(code)}/price?pageSize=50&page={pg}") or []
        if not j: break
        for x in j:
            try: t.append(x["localTradedAt"][:10].replace("-", "")); v.append(f(x["closePrice"]))
            except Exception: pass
        if len(j) < 50: break
    pair = sorted(zip(t, v))
    return {"t": [a for a, b in pair], "v": [b for a, b in pair]}

import re as _re
_MI_PAT = _re.compile(r'class="date">\s*([\d.]+)\s*</td>\s*<td class="num">\s*([\d,.]+)')
def naver_mi_hist(ep, cd, fdtc, pages):
    """네이버 marketindex 일별시세 HTML 파싱(euc-kr) — 첫 실행 pages=40 백필, 이후 2페이지 증분."""
    rows = {}
    for pg in range(1, pages + 1):
        u = (f"https://finance.naver.com/marketindex/{ep}.naver?marketindexCd={cd}"
             + (f"&fdtc={fdtc}" if fdtc is not None else "") + f"&page={pg}")
        try:
            req = urllib.request.Request(u, headers=H)
            h = urllib.request.urlopen(req, timeout=12).read().decode("euc-kr", "ignore")
        except Exception:
            break
        found = _MI_PAT.findall(h)
        if not found: break
        for d_, v_ in found:
            try: rows[d_.replace(".", "")] = float(v_.replace(",", ""))
            except Exception: pass
        if len(found) < 5: break
        time.sleep(0.05)
    ts = sorted(rows)
    return {"t": ts, "v": [rows[k] for k in ts]}

def upbit(markets):
    j = jget("https://api.upbit.com/v1/ticker?markets=" + ",".join(markets)) or []
    out = {}
    for x in j:
        out[x["market"]] = {"px": x["trade_price"], "pc": x["prev_closing_price"],
                            "at": "실시간"}
    return out

def upbit_hist(market):
    """업비트 일봉 — 1콜 최대 200개라 to 파라미터로 2페이지 페이징(약 400일)."""
    j = jget(f"https://api.upbit.com/v1/candles/days?market={market}&count=200") or []
    if j:
        to = j[-1]["candle_date_time_utc"]
        j += jget(f"https://api.upbit.com/v1/candles/days?market={market}&count=200&to={to}") or []
    seen = {}
    for x in j:
        seen[x["candle_date_time_kst"][:10].replace("-", "")] = x["trade_price"]
    ts = sorted(seen)
    return {"t": ts, "v": [seen[k] for k in ts]}

def rets(t, v, px):
    """기간수익률: 최근가(px) 대비 과거 최근접 종가."""
    if not t or px is None: return {}
    last = datetime.strptime(t[-1], "%Y%m%d").date()
    today = datetime.now().strftime("%Y%m%d")
    out = {}
    for k, days in [("d1", 1), ("w1", 7), ("m1", 30), ("m3", 91), ("m6", 182), ("y1", 364)]:
        if k == "d1":
            # 직전 거래일 종가 대비. 휴장(현재가=마지막 봉)이면 마지막 거래일의 등락을 표시(미래에셋과 동일)
            same_bar = t[-1] == today or (v[-1] and abs(px - v[-1]) / abs(v[-1]) < 5e-3)
            base = (v[-2] if len(v) >= 2 else None) if same_bar else v[-1]
        else:
            tgt = (last - timedelta(days=days)).strftime("%Y%m%d")
            base = None
            for i in range(len(t) - 1, -1, -1):
                if t[i] <= tgt: base = v[i]; break
            if base is None and t:                      # 이력 시작이 목표일 직후면 근사(+35일 허용)
                lim = (datetime.strptime(tgt, "%Y%m%d") + timedelta(days=35)).strftime("%Y%m%d")
                if t[0] <= lim: base = v[0]
        out[k] = round((px / base - 1) * 100, 2) if base else None
    return out

def spark(v, n=60):
    if not v: return []
    if len(v) <= n: return [round(x, 4) for x in v]
    step = (len(v) - 1) / (n - 1)
    return [round(v[int(i * step)], 4) for i in range(n)]

def krx_fetch(hist):
    """KRX 세부지수 T+1 — krx/kospi/kosdaq 일별시세 3콜, 원하는 지수만 필터·일별 누적."""
    try:
        key = (BASE / "secrets" / "krx.key").read_text(encoding="utf-8").strip()
    except Exception:
        return [], hist
    # (실측 2026-08-01) BBIG·2차전지 등 K-뉴딜 TOP10 시리즈는 KRX OPENAPI 미제공 → 제공 지수로 구성
    WANT = ["KRX 300", "KRX 100", "KRX 300 정보기술", "KRX 300 금융",
            "KRX 300 헬스케어", "KRX 300 자유소비재", "코스닥 150", "코스닥 글로벌",
            "코스피 200 정보기술", "코스피 200 금융"]
    rows = []
    for d_off in range(1, 6):                       # 직전 영업일 탐색
        bas = (date.today() - timedelta(days=d_off)).strftime("%Y%m%d")
        got = []
        for ep in ("krx_dd_trd", "kospi_dd_trd", "kosdaq_dd_trd"):
            try:
                req = urllib.request.Request(f"http://data-dbg.krx.co.kr/svc/apis/idx/{ep}?basDd={bas}",
                                             headers={"AUTH_KEY": key})
                j = json.loads(urllib.request.urlopen(req, timeout=20).read())
                got += j.get("OutBlock_1") or []
            except Exception:
                pass
        if got:
            byname = {x.get("IDX_NM", "").strip(): x for x in got}
            for nm in WANT:
                x = byname.get(nm)
                if not x: continue
                try:
                    _f = lambda s: float(str(s).replace(",", ""))          # KRX는 천단위 콤마 포함
                    px = _f(x["CLSPRC_IDX"]); chg = _f(x.get("CMPPREVDD_IDX") or 0)
                    rows.append({"s": "KRX:" + nm, "name": nm.replace(" K-뉴딜지수", " TOP10"),
                                 "px": px, "chg_abs": chg, "at": bas[4:6] + "/" + bas[6:] + " 종가(T+1)"})
                    h = hist.setdefault(nm, {"t": [], "v": []})
                    if not h["t"] or h["t"][-1] != bas:
                        h["t"].append(bas); h["v"].append(px)
                        h["t"] = h["t"][-500:]; h["v"] = h["v"][-500:]
                except Exception:
                    pass
            break
    return rows, hist

def main():
    t0 = time.time()
    ysyms = [s for g, s, n, src, m, d in U if "Y" in src]
    # (2026-08-02) 야후 이력 미제공 원화 크로스는 합성 대신 네이버 고시환율(ND 소스)로 전환 — 합성 로직 제거
    with ThreadPoolExecutor(12) as ex:
        ydata = dict(zip(ysyms, ex.map(yahoo_1y, ysyms)))
    nlive = {s: naver_kr(c) for s, c in NAVER_LIVE.items()}
    nidx = {s: naver_idx(c) for s, c in NAVER_IDX.items()}
    ups = upbit([s for g, s, n, src, m, d in U if src == "U"])
    uph = {}
    for g, s, n, src, m, d in U:
        if src == "U": uph[s] = upbit_hist(s); time.sleep(0.15)

    hist_all = {}
    rows_by_grp = {}
    acc = {}                                            # (2026-08-02) 이력 미제공 심볼 일별 자동누적
    try: acc = json.loads((DB / "global_acc_hist.json").read_text(encoding="utf-8"))
    except Exception: pass
    today_s = datetime.now().strftime("%Y%m%d")
    for g, s, name, src, mult, dec in U:
        r = {"s": s, "name": name, "mult": mult, "dec": dec}
        series = None
        if src == "U":
            series = uph.get(s); q = ups.get(s) or {}
            r["px"] = q.get("px"); r["at"] = q.get("at")
            if q.get("pc"): r["ret_d1_live"] = round((q["px"] / q["pc"] - 1) * 100, 2)
        elif src == "NK":
            q = naver_kr(NK_CODES[s])
            nh = naver_kr_hist(NK_CODES[s])
            series = nh if nh["t"] else None
            if q: r["px"] = q["px"]; r["at"] = "실시간(네이버)"
            elif series: r["px"] = series["v"][-1]
        elif src == "NF":
            q = naver_fut(NF_CODES[s])
            nh = naver_fut_hist(NF_CODES[s])
            series = nh if nh["t"] else None
            if q: r["px"] = q["px"]; r["at"] = q["at"]
            elif series: r["px"] = series["v"][-1]
        elif src == "ND":
            ep, cd, fdtc = ND_CODES[s]
            a = acc.get(s) or {"t": [], "v": []}
            nh = naver_mi_hist(ep, cd, fdtc, pages=60 if len(a["t"]) < 380 else 2)   # 1년 수익률에 ~380거래일 필요
            m2 = dict(zip(a["t"], a["v"])); m2.update(dict(zip(nh["t"], nh["v"])))
            ts_ = sorted(m2)
            series = {"t": ts_, "v": [m2[k] for k in ts_]}
            acc[s] = {"t": ts_[-600:], "v": series["v"][-600:]}
            if ts_:
                r["px"] = series["v"][-1]
                r["at"] = ts_[-1][4:6] + "/" + ts_[-1][6:] + (" 고시(네이버)" if ep == "exchangeDailyQuote" else " 종가(네이버)")
        else:
            y = ydata.get(s)
            if y: series = {"t": y["t"], "v": y["v"]}; r["px"] = y["px"]; r["at"] = y["at"]
            if y and s.endswith("=F") and y.get("sn"):
                # 월물 표기(예: "Nasdaq 100 Sep 26" → 26.09월물) — 야후 =F는 최근월 연속이라 롤오버 자동 반영
                import re as _re2
                _mm = _re2.search(r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{2})\b", y["sn"])
                if _mm:
                    _mon = {"Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
                            "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12}[_mm.group(1)]
                    r["at"] = f"{_mm.group(2)}.{_mon:02d}월물 · " + (r.get("at") or "")
            if src == "NY" and nlive.get(s):                     # 국내 3종: 네이버 실시간 + 네이버 이력(야후 결측 대체)
                r["px"] = nlive[s]["px"]; r["at"] = "실시간(네이버)"
                nh = naver_kr_hist(NAVER_LIVE[s])
                if nh["t"]: series = nh
            if src == "N" and nidx.get(s):
                q = nidx[s]; r["px"] = q["px"]; r["at"] = q["at"]
                nh = naver_world_hist(NAVER_IDX[s])
                series = nh if nh["t"] else {"t": [], "v": []}
        # 이력 부족(소스가 시세만 제공) → ① 네이버 대체 이력 ② 일별 자동누적으로 시간이 지나며 자동 표시
        if (not series or len(series["t"]) < 30) and NAVER_HIST_FB.get(s):
            nh = naver_world_hist(NAVER_HIST_FB[s])
            if nh["t"]: series = nh
        if (not series or len(series["t"]) < 30) and EM_HIST.get(s):
            eh = em_hist(EM_HIST[s])
            if eh["t"]: series = eh
        if (not series or len(series["t"]) < 30) and r.get("px") is not None:
            a = acc.get(s) or {"t": [], "v": []}
            m = dict(zip(a["t"], a["v"]))
            if series: m.update(dict(zip(series["t"], series["v"])))
            m[today_s] = r["px"]
            ts_ = sorted(m)
            series = {"t": ts_, "v": [m[k] for k in ts_]}
            acc[s] = {"t": ts_[-600:], "v": series["v"][-600:]}
        if FUT_CYCLE.get(s):                              # 선물 만기 주기 표기
            r["at"] = ((r.get("at") + " · ") if r.get("at") else "") + FUT_CYCLE[s]
        if r.get("dec") is None:                          # fx2: 소수점 자동
            px0 = r.get("px")
            r["dec"] = (0 if px0 >= 1000 else 2 if px0 >= 10 else 4) if px0 else 2
        if s in INVERT:
            if r.get("px"): r["px"] = round(1.0 / r["px"], 6)
            if series and series.get("v"):
                t3, v3 = [], []
                for d3, x3 in zip(series["t"], series["v"]):
                    if x3: t3.append(d3); v3.append(round(1.0 / x3, 6))
                series = {"t": t3, "v": v3}
        if series and series["t"]:
            # 장중 현재가를 시리즈 말미에 반영해 기간수익률 일관성 확보
            if r.get("px") is not None:
                if series["t"][-1] == today_s: series["v"][-1] = r["px"]
            r["ret"] = rets(series["t"], series["v"], r.get("px"))
            r["spark"] = spark(series["v"][-252:])
            hist_all[s] = series
        rows_by_grp.setdefault(g, []).append(r)

    GRP = [("kr", "국내 대표 (실시간)"), ("us", "미국"),
           ("as", "아시아·중화권"), ("eu", "유럽·미주"), ("me", "중동·아프리카"), ("cmd", "상품"), ("fx", "환율 — 주요 통화"), ("fx2", "환율 — 기타 통화"), ("cr", "암호화폐 (업비트 실시간)")]
    out = {"asof": datetime.now().strftime("%Y-%m-%d %H:%M"),
           "src": "야후(지수 ~15분 지연·선물/환율 실시간급)+네이버(국내 T+0·TOPIX·VNI)+업비트(실시간)+KRX(T+1)",
           "groups": [{"key": k, "label": lb, "rows": rows_by_grp.get(k, [])} for k, lb in GRP]}
    DB.mkdir(parents=True, exist_ok=True)
    (DB / "global_market.json").write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    (DB / "global_hist.json").write_text(json.dumps(hist_all, ensure_ascii=False), encoding="utf-8")
    (DB / "global_acc_hist.json").write_text(json.dumps(acc, ensure_ascii=False), encoding="utf-8")
    n = sum(len(v) for v in rows_by_grp.values())
    print(f"[global] ✅ {n}종 · hist {len(hist_all)}종 · {time.time()-t0:.0f}s")

if __name__ == "__main__":
    main()
