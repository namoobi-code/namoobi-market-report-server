#!/usr/bin/env python3
# fetch_appe.py — [부록E] 피지컬 AI(휴머노이드) 밸류체인 — v3.72 신설
#   구성 근거: 한경비즈니스 2026.08.05-11 커버스토리 '피지컬 AI 핵심 밸류체인'(6계층 분해) +
#              모건스탠리 2025 선정 핵심기업 · 골드만삭스/옴디아 출하 통계.
#   6계층: ①두뇌 ②신경·감각 ③근육·관절 ④골격·에너지 ⑤가상훈련장 ⑥완성체
#   sandbox·stdlib·스레드 병렬(Phase 1 bash tool-call). 야후 일봉 2y → nmr_appe.json + nmr_appe_series.json(1Y 스파크).
#   비상장(피겨AI·애지봇·유니트리·1X·샤르파·보스턴다이내믹스·에이로봇 등)은 [부록F] 관계도에만 표기한다.
#   멤버십 변경 시 ROWS 갱신. 추정 금지 — 이력 없으면 '-'(비차단).
import urllib.request, urllib.parse, json, datetime as dt, concurrent.futures as cf, os, sys
UA={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120 Safari/537.36"}
OUT=sys.argv[1] if len(sys.argv)>1 else "."
PFX=sys.argv[2] if len(sys.argv)>2 else "nmr_appe"   # 서버 크론은 "appe" → data/db/appe.json
# (그룹, yahoo심볼, 이름, 설명)
ROWS=[
 # ① 두뇌 — 파운데이션 모델(VLA)·온디바이스 AI 칩·학습 메모리
 ("두뇌(AI·반도체)","NVDA","NVIDIA","로봇 파운데이션 모델 GR00T N1.6·주행칩 젯슨 토르 — 두뇌 설계·훈련·실행 전 과정 장악"),
 ("두뇌(AI·반도체)","GOOGL","Alphabet (구글 딥마인드)","제미나이 로보틱스 1.5·ER 1.6 — 언어·추론을 로봇 동작으로 확장한 VLA"),
 ("두뇌(AI·반도체)","QCOM","Qualcomm","휴머노이드용 드래곤윙 IQ10(700TOPS) — 저전력 온디바이스 추론"),
 ("두뇌(AI·반도체)","AMD","Advanced Micro Devices","로봇 가속기의 유일한 규모 대안 — 수요처가 키우는 2등"),
 ("두뇌(AI·반도체)","ARM","Arm Holdings","저전력 온디바이스 설계 IP 표준 — 로봇 소뇌(엣지)의 기본 아키텍처"),
 ("두뇌(AI·반도체)","005930.KS","삼성전자","DX부문 직속 로봇 전담조직·데이터팩토리, 레인보우로보틱스 자회사 편입"),
 ("두뇌(AI·반도체)","000660.KS","SK하이닉스","로봇 학습·추론 데이터 폭증의 최종 수혜 = HBM 1위"),
 # ② 신경·감각 — 비전·라이다·촉각·IMU (센서 퓨전)
 ("신경·감각(센서)","6758.T","소니그룹 (Sony)","이미지센서 글로벌 1위 — 로봇 '눈'의 기본 공급자"),
 ("신경·감각(센서)","HSAI","헤사이 (Hesai)","라이다 글로벌 1위 — 로봇개 부이봇으로 휴머노이드 표준 선점 시도"),
 ("신경·감각(센서)","STM","STMicroelectronics","MEMS·ToF 센서 — 소형 로봇 감각의 범용 공급자"),
 ("신경·감각(센서)","TXN","Texas Instruments","아날로그·센싱·모터 드라이버 — 로봇 신경계의 저변 부품"),
 ("신경·감각(센서)","6762.T","TDK","초정밀 관성센서(IMU) — LG이노텍과 차세대 멀티센싱 모듈 공동개발(7/28)"),
 ("신경·감각(센서)","011070.KS","LG이노텍","광학 비전 모듈 + TDK IMU 결합 — 밀리초 단위 센서퓨전 모듈화"),
 ("신경·감각(센서)","009150.KS","삼성전기","MLCC·카메라모듈 — 로봇 1대당 수동부품 탑재량 급증 수혜"),
 ("신경·감각(센서)","204320.KS","HL만도","자율주행 레이더·센서 역량의 로보틱스 전용"),
 ("신경·감각(센서)","214430.KQ","아이쓰리시스템","적외선·비냉각 영상센서 — 야간·열 감지 국산화"),
 ("신경·감각(센서)","464080.KQ","에스오에스랩","고정형 라이다 국산화 — 센서 3대 취약부품 대응"),
 ("신경·감각(센서)","030530.KQ","원익홀딩스","로봇 솔루션·지능형 소프트웨어 연계 지주"),
 ("신경·감각(센서)","304100.KQ","솔트룩스","로봇 인지·언어 지능 소프트웨어"),
 # ③ 근육·관절 — 액추에이터(원가 30~60%)·감속기·모터·베어링·영구자석
 ("근육·관절(액추에이터)","6324.T","하모닉드라이브시스템즈","정밀 파동기어 감속기 — 로봇 관절 정밀도의 세계 표준"),
 ("근육·관절(액추에이터)","6268.T","나브테스코 (Nabtesco)","산업용 RV 감속기 강자 — 대형 관절의 내구성 기준"),
 ("근육·관절(액추에이터)","6481.T","THK","LM가이드·리니어 액추에이터 최상위"),
 ("근육·관절(액추에이터)","6594.T","니덱 (Nidec)","소형 정밀모터 세계 1위 — 손가락·관절 구동의 대량공급자"),
 ("근육·관절(액추에이터)","6471.T","NSK","초정밀 베어링 — 관절 마찰·수명의 결정 부품"),
 ("근육·관절(액추에이터)","2049.TW","하이윈 (HIWIN)","볼스크루·리니어 — 리니어 액추에이터 핵심 스크루"),
 ("근육·관절(액추에이터)","TKR","Timken","베어링 글로벌 강자 — 고하중 관절 대응"),
 ("근육·관절(액추에이터)","RRX","Regal Rexnord","모션 컨트롤·베어링 통합 공급"),
 ("근육·관절(액추에이터)","300124.SZ","이노반스 (Inovance)","중국 서보모터 1위 — 중국 휴머노이드 원가경쟁력의 뿌리"),
 ("근육·관절(액추에이터)","002747.SZ","에스툰 오토메이션 (Estun)","중국 로봇 본체·액추에이터 수직계열"),
 ("근육·관절(액추에이터)","LYC.AX","라이너스 (Lynas)","중국 밖 최대 희토류 — 영구자석 공급망 대안"),
 ("근육·관절(액추에이터)","600111.SS","북방희토 (Northern Rare Earths)","희토류 최대 생산 — 모터 자석 원가의 지배 변수"),
 ("근육·관절(액추에이터)","012330.KS","현대모비스","보스턴다이내믹스 아틀라스 핵심 액추에이터 공급 파트너 — 시제품 공급·양산 체제"),
 ("근육·관절(액추에이터)","066570.KS","LG전자","세탁기에서 축적한 DD(다이렉트드라이브) 모터 기술의 로봇 전용"),
 ("근육·관절(액추에이터)","108490.KQ","로보티즈","모듈형 액추에이터 '다이나믹셀' — NASA ISS 프로젝트 납품 이력"),
 ("근육·관절(액추에이터)","389500.KQ","에스비비테크","하모닉 감속기 국산화 — 일본 의존 대체 시도"),
 ("근육·관절(액추에이터)","004380.KS","삼익THK","리니어모션 국내 1위 — THK 기술 제휴"),
 # ④ 골격·에너지 — 경량 소재(CFRP·알루미늄)·휴머노이드 전용 배터리
 ("골격·에너지(소재·배터리)","HXL","Hexcel","항공급 탄소섬유 복합재 — 로봇 팔다리 경량화 대표주"),
 ("골격·에너지(소재·배터리)","3402.T","도레이 (Toray)","탄소섬유 세계 1위 — 현대차그룹과 미래 모빌리티 소재 협력"),
 ("골격·에너지(소재·배터리)","006400.KS","삼성SDI","AI 로봇용 파우치형 전고체 '솔리드스택' 공개 — 2027년 양산 목표"),
 ("골격·에너지(소재·배터리)","373220.KS","LG에너지솔루션","피겨AI·보스턴다이내믹스·테슬라 3대 로봇업체 모두에 배터리 납품"),
 ("골격·에너지(소재·배터리)","096770.KS","SK이노베이션 (SK온)","대전 미래기술원 전고체 파일럿 — 2029년 상용화 목표"),
 ("골격·에너지(소재·배터리)","300750.SZ","CATL","LFP 기반 고밀도 기술로 중국 휴머노이드 시장 공략"),
 ("골격·에너지(소재·배터리)","298050.KS","효성첨단소재","탄소섬유 국산화 — 로봇 경량화 소재 공급"),
 ("골격·에너지(소재·배터리)","199430.KQ","케이엔알시스템","유압·로봇 구동 시스템 — 경량화 부품 국산화 참여"),
 # ⑤ 가상훈련장 — 시뮬레이터·물리엔진(데이터 폭발의 시발점)
 ("가상훈련장(시뮬레이션)","META","Meta Platforms","가정환경 복제 시뮬레이터 '하비타트' + 촉각 스킨 연구"),
 ("가상훈련장(시뮬레이션)","SNPS","Synopsys","앤시스 통합 물리 시뮬레이션 — 로봇 설계·검증의 디지털트윈"),
 ("가상훈련장(시뮬레이션)","U","Unity Software","로봇 학습용 3D 시뮬레이션 엔진 — 합성 데이터 생성 저변"),
 # ⑥ 완성체 — 휴머노이드 메이커
 ("완성체(휴머노이드)","TSLA","Tesla","옵티머스 — 프리몬트·기가텍사스에 전용 라인, 부품 1만 개 공급망 신설"),
 ("완성체(휴머노이드)","005380.KS","현대차","보스턴다이내믹스 아틀라스 2028년 미국 공장 투입 — 부품 조립까지 확장"),
 ("완성체(휴머노이드)","9880.HK","UBTech","워커S 양산 — 중국 산업용 휴머노이드 선두권"),
 ("완성체(휴머노이드)","002594.SZ","BYD","8월 첫 휴머노이드 공개 — 판매 현장 우선 배치"),
 ("완성체(휴머노이드)","XPEV","XPeng (샤오펑)","광저우 공장에서 휴머노이드 '아이언(IRON)' 소량 테스트 생산"),
 ("완성체(휴머노이드)","277810.KQ","레인보우로보틱스","삼성전자 자회사 — 국내 휴머노이드 상용화 축"),
 ("완성체(휴머노이드)","454910.KS","두산로보틱스","협동로봇 국내 1위 — 산업현장 로봇 데이터 축적"),
]
def yfetch(sym):
    u=f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(sym)}?range=2y&interval=1d"
    d=json.load(urllib.request.urlopen(urllib.request.Request(u,headers=UA),timeout=20))
    r=d["chart"]["result"][0]; ts=r.get("timestamp"); pts=[]
    ynm=((r.get("meta") or {}).get("shortName") or "")
    if ts:
        cl=r["indicators"]["quote"][0]["close"]
        pts=[[dt.datetime.utcfromtimestamp(t).date().isoformat(),round(float(c),2)] for t,c in zip(ts,cl) if c is not None]
    return pts,ynm
def ret(series):
    pts=[(dt.date.fromisoformat(str(x[0])[:10]),float(x[1])) for x in series if x[1] is not None]
    if len(pts)<2: return {}
    pts.sort(); cur=pts[-1][1]; last=pts[-1][0]
    out={"current":round(cur,2)}
    for k,days in [("1w_pct",7),("1mo_pct",30),("3mo_pct",91),("6mo_pct",182),("1y_pct",365)]:
        tgt=last-dt.timedelta(days=days); cand=[p for p in pts if p[0]<=tgt]
        out[k]=round((cur/cand[-1][1]-1)*100,1) if cand and cand[-1][1] else None
    if len(pts)>=2 and pts[-2][1]:
        out["1d_pct"]=round((pts[-1][1]/pts[-2][1]-1)*100,2); out["chg"]=round(cur-pts[-2][1],2)
    if len(pts)>=3 and pts[-3][1]:
        out["prev_pct"]=round((pts[-2][1]/pts[-3][1]-1)*100,2)
    return out
def koTrend(r):
    y=r.get("1y_pct"); m3=r.get("3mo_pct")
    if y is not None:
        s="강세" if y>0 else "약세"; t=f"1년 {y:+.0f}%"
        if m3 is not None: t+=f", 3개월 {m3:+.0f}%"+(" 가속" if (m3 or 0)>0 and y>0 else (" 조정" if (m3 or 0)<0 else ""))
        return t+f" ({s})"
    if m3 is not None: return f"3개월 {m3:+.0f}% "+("상승" if m3>=0 else "조정")+" (상장 후)"
    return "이력 부족"
def ccy(sym):
    if sym.endswith(".T"): return "JPY"
    if sym.endswith((".KS",".KQ")): return "KRW"
    if sym.endswith(".TW"): return "TWD"
    if sym.endswith((".SS",".SZ")): return "CNY"
    if sym.endswith(".HK"): return "HKD"
    if sym.endswith(".AX"): return "AUD"
    return "USD"
def work(row):
    grp,sym,name,desc=row
    try:
        pts,ynm=yfetch(sym); r=ret(pts)
        r.update({"code":sym,"symbol":sym,"name":name,"desc":desc,"group":grp,"ccy":ccy(sym),
                  "yname":ynm,"trend":koTrend(r)})
        ser=[p for p in pts if dt.date.fromisoformat(p[0])>=dt.date.today()-dt.timedelta(days=366)]
        return sym,grp,r,ser,None
    except Exception as e: return sym,grp,None,None,str(e)[:120]
GROUPS=[]
for g,_,_,_ in ROWS:
    if g not in GROUPS: GROUPS.append(g)
out={"groups":GROUPS,"rows":{g:[] for g in GROUPS},"asof":dt.date.today().isoformat()}
series={}; errs=[]
order={r[1]:i for i,r in enumerate(ROWS)}
with cf.ThreadPoolExecutor(max_workers=12) as ex:
    for sym,grp,r,ser,err in ex.map(work,ROWS):
        if err or r is None: errs.append(f"{sym}:{err}"); continue
        out["rows"][grp].append(r)
        if ser: series[sym]=ser
for g in out["rows"]: out["rows"][g].sort(key=lambda r:order[r["code"]])
out["as_of"]=dt.datetime.now().strftime("%Y-%m-%d %H:%M")
json.dump(out,open(os.path.join(OUT,PFX+".json"),"w"),ensure_ascii=False,indent=1)
json.dump(series,open(os.path.join(OUT,PFX+"_series.json"),"w"),ensure_ascii=False)
n=sum(len(v) for v in out["rows"].values())
def pc(v): return "   -  " if v is None else f"{v:+6.1f}"
for g in GROUPS:
    print(f"◆ {g}")
    for r in out["rows"][g]:
        print(f"  {r['code']:10s} {r['name'][:22]:22s} | yahoo={r.get('yname','')[:24]:24s} {(r.get('current') or 0):>11,.2f} {pc(r.get('1mo_pct'))} {pc(r.get('1y_pct'))}")
print(f"총 {n}/{len(ROWS)} · series {len(series)} · errs {errs}")
