/* cryptolead.js — 🪙 코인 선행지표 탭 (2026-09-05 신설)
   데이터: /api/db/cryptolead (scripts/fetch_cryptolead.py · 매일 06:55 cron · LLM 토큰 0)
   구성: ① 종합 신호등(4축) ② 그룹별 지표 카드(현재값·판정·1년 스파크·왜 선행인가) ③ 정책 이벤트(보고서 세션이 채움)
   설계 의도: "앞으로 오를지 / 오름이 유지될지"를 한 화면에서 — 단기 과열(심리·파생)과 중기 수급(지갑·기관·대기자금),
             사이클 밸류(온체인), 매크로 유동성의 4축을 분리해 서로 다른 시간축의 신호가 뒤섞이지 않게 한다. 리서치용, 투자권유 아님. */
(function(){
'use strict';
let D=null; const charts=[]; let SHOWHELP=true; try{ SHOWHELP=localStorage.getItem('cl_help')!=='0'; }catch(e){}
const $=id=>document.getElementById(id);
const ST={bull:['🟢','상승 우호','#16a34a','#dcfce7'],neu:['🟡','중립','#a16207','#fef9c3'],bear:['🔴','과열·역풍','#dc2626','#fee2e2']};
const GCOL={'심리·한국':'#be185d','지갑·거래소':'#0f766e','온체인 밸류':'#7c3aed','기관':'#1d4ed8','파생':'#b45309','매크로':'#334155','대기자금':'#0e7490','알트':'#9333ea'};
const nf=(n,d)=>n==null?'—':Number(n).toLocaleString(undefined,{maximumFractionDigits:d==null?2:d});
function fmtV(k,e){
  const v=e.v; if(v==null) return '—';
  const u=e.unit||'';
  if(k==='ex_supply') return nf(v/1e6,3)+'M BTC';
  if(k==='adr_act') return nf(v/1000,0)+'K';
  if(k==='netliq') return '$'+nf(v/1000,2)+'T';
  if(k==='stable') return '$'+nf(v,1)+'B';
  if(k==='oi') return '$'+nf(v,2)+'B';
  if(k==='ex_netflow'||k==='ibit_flow') return (v>0?'+':'')+nf(v,0)+' M$';
  if(k==='cot_am'||k==='cot_lev') return (v>0?'+':'')+nf(v,0)+' 계약';
  if(k==='funding') return (v>0?'+':'')+v.toFixed(4)+'%';
  if(k==='cb_prem'||k==='kimp') return (v>0?'+':'')+v.toFixed(2)+'%';
  if(k==='halving') return v+'일';
  if(u==='x') return v.toFixed(2)+'×';
  if(u==='%') return nf(v,1)+'%';
  return nf(v, Math.abs(v)>=100?0:Math.abs(v)>=10?1:2)+(u?' '+u:'');
}
/* BTC 가격 오버레이 — (2026-09-05 피드백) 지표와 가격을 같은 기간에 겹쳐야 "이 지표가 가격에 얼마나 앞서/따라가나"가 보인다.
   서버 동봉 _px(Binance 일봉 1000일). 지표 날짜에 정확히 없으면 직전 거래일 종가. 범위 밖(5년 구글트렌드 앞부분)은 null. */
let PX=null;           // [[date,close],...] 오름차순
function pxAt(d){
  if(!PX||!PX.length||d<PX[0][0]) return null;
  let lo=0,hi=PX.length-1;
  while(lo<hi){const m=(lo+hi+1)>>1; if(PX[m][0]<=d) lo=m; else hi=m-1;}
  return PX[lo][1];
}
function spark(cv,s,color,k){
  if(!s||s.length<2) return;
  const labels=s.map(x=>x[0]), data=s.map(x=>x[1]);
  // 판정 임계선(참고선) — 지표별 대표 밴드
  const TH={fng:[25,75],kimp:[0,5],mvrv:[1,3],mvrv_z:[0,6],sopr:[1],nupl:[0,0.75],puell:[0.6,3],mayer:[0.85,2.2],funding:[0,0.05],ls_ratio:[0.9,2],taker:[0.9,1.1],cb_prem:[0],ex_netflow:[0],ibit_flow:[0],cot_am:[0],cot_lev:[0],altbreadth:[25,75],dvol:[40,80],gt_world:[],gt_kr:[],eth_netflow:[0],alt_funding:[0],upbit_alt_share:[]}[k]||[];
  const ds=[{label:'지표',data,borderColor:color,backgroundColor:color+'22',fill:true,pointRadius:0,borderWidth:1.3,tension:0.15,yAxisID:'y',order:2}];
  TH.forEach(t=>ds.push({label:'_th',data:data.map(()=>t),borderColor:'#94a3b8',borderDash:[3,3],borderWidth:0.8,pointRadius:0,fill:false,yAxisID:'y',order:3}));
  const px=labels.map(pxAt); const hasPx=px.some(v=>v!=null);
  if(hasPx) ds.push({label:'BTC',data:px,borderColor:'#f59e0b',backgroundColor:'transparent',fill:false,pointRadius:0,borderWidth:1.4,tension:0.15,yAxisID:'y2',order:1,spanGaps:false});
  charts.push(new Chart(cv,{type:'line',data:{labels,datasets:ds},
    options:{responsive:true,maintainAspectRatio:false,animation:false,interaction:{mode:'index',intersect:false},
      plugins:{legend:{display:false},tooltip:{filter:i=>i.dataset.label!=='_th',callbacks:{label:c=>c.dataset.label==='BTC'?'BTC $'+nf(c.raw,0):'지표 '+nf(c.raw,4)}}},
      scales:{x:{display:true,ticks:{maxTicksLimit:4,font:{size:9},maxRotation:0,callback:(v,i)=>labels[i]?labels[i].slice(2,7):''},grid:{display:false}},
              y:{position:'left',ticks:{font:{size:9},maxTicksLimit:4,color:color},grid:{color:'#f1f5f9'}},
              y2:{display:hasPx,position:'right',ticks:{font:{size:9},maxTicksLimit:4,color:'#d97706',callback:v=>'$'+(v>=1000?(v/1000).toFixed(0)+'k':v)},grid:{display:false}}}}}));
}

/* ── (2026-09-05 피드백 "어떤 지표인지, 의미와 해석방법이 어렵다") 쉬운 설명 + 눈금 게이지 ──
   HELP: what=한 줄로 뭔지(비유) · read=숫자로 읽는 법 · low/high=낮을 때/높을 때 뜻
   GAUGE: [min,max,lo,hi,dir] — 막대 위 현재값 위치. dir 'hot'=높을수록 과열(오른쪽 빨강), 'cool'=높을수록 좋음(오른쪽 초록), 'mid'=양끝 다 경계 */
const NOCHART={   // 추세 차트가 없는 이유 (피드백 2026-09-05)
 halving:'📅 날짜 계산 지표 — 추세가 아니라 "사이클의 어디쯤인가"만 본다.',
 btc_dom:'⏳ 무료 API 가 과거치를 주지 않아 서버가 오늘부터 매일 쌓는다 — 며칠 뒤부터 추세가 그려진다.',
 ibit_flow:'⏳ iShares 페이지는 당일 발행주식수만 공개 — 서버가 매일 기록해 유입액을 계산한다. 1주일쯤 뒤부터 추세 표시.',
 altbreadth:'⏳ 서버 일간 누적 중 — 며칠 뒤부터 추세 표시.'};
const HELP={
 fng:{what:'투자자들이 지금 겁먹었는지 들떠 있는지를 0~100 점수로 만든 것(변동성·거래량·SNS·설문 합산).',read:'0~25 극단 공포 · 25~75 보통 · 75~100 극단 탐욕.',low:'다들 무서워 팔았다 → 팔 사람이 줄어 반등 여지(역발상 매수).',high:'다들 들떠 이미 샀다 → 살 사람이 줄어 단기 고점 경계.'},
 kimp:{what:'같은 비트코인이 한국 거래소(업비트)에서 해외(바이낸스)보다 몇 % 비싼가.',read:'0% 근처 정상 · +3~5% 국내 과열 · 마이너스는 국내 무관심.',low:'국내 사람들이 관심을 끊었다 → 바닥권에서 흔히 보이는 모습.',high:'국내 개인이 웃돈 주고 산다 → 과거 김프 5%↑ 뒤엔 단기 고점이 잦았다.'},
 upbit_ratio:{what:'업비트 하루 BTC 거래대금이 바이낸스의 몇 %인가 — 한국 개인의 참여 열기.',read:'절대값보다 200일 중 순위(백분위)로 본다. 상위 10% 과열 · 하위 15% 무관심.',low:'개미가 빠져나간 상태 → 바닥권 특징.',high:'개미가 몰린 상태 → 국내 주도 과열.'},
 gt_world:{what:'전 세계 사람들이 구글에 "bitcoin"을 얼마나 검색했나(5년 중 최고=100).',read:'5년 중 순위로 본다. 상위 10% 관심 정점 · 하위 20% 무관심.',low:'아무도 안 찾는다 → 역발상 매수 구간이 많았다.',high:'모두가 찾는다 → 2017·2021 고점이 검색 정점과 겹쳤다.'},
 gt_kr:{what:'한국에서 구글에 "bitcoin"을 얼마나 검색했나(5년 중 최고=100).',read:'전세계와 같은 방식. 한국만 높으면 국내 주도 과열.',low:'국내 무관심.',high:'국내 대중 관심 정점.'},
 wiki_ko:{what:'한국어 위키 "비트코인" 문서 하루 조회수(7일 평균) — 처음 알아보는 사람의 수.',read:'2년 중 순위. 상위 10% 관심 정점 · 하위 20% 무관심.',low:'신규 유입 없음.',high:'대중이 처음 알아보기 시작 = 관심 정점.'},
 wiki_en:{what:'영어 위키 "Bitcoin" 문서 하루 조회수(7일 평균).',read:'2년 중 순위. 상위 10% 관심 정점 · 하위 20% 무관심.',low:'글로벌 신규 유입 없음.',high:'글로벌 대중 관심 정점.'},
 ex_netflow:{what:'지난 7일간 거래소 지갑으로 들어온 돈 − 나간 돈(백만$). 거래소에 넣는 건 팔려는 것, 빼서 개인지갑에 두는 건 오래 갖고 있으려는 것.',read:'−500M$ 미만 = 유출 우세(좋음) · ±500 균형 · +500M$ 초과 = 유입 우세(매도 대기).',low:'코인이 거래소 밖으로 빠져나감 → 팔 물량 감소 → 상승에 우호.',high:'코인이 거래소로 몰림 → 팔 준비 → 하락 압력.'},
 ex_supply:{what:'전 세계 거래소가 보관 중인 비트코인 총량. "당장 팔 수 있는 재고".',read:'값 자체보다 30일 변화율. −1% 이하 감소(좋음) · +1% 이상 증가(경계).',low:'재고가 줄어든다 → 공급 부족 → 가격에 우호.',high:'재고가 는다 → 팔려고 갖다 놓는 중.'},
 adr_act:{what:'하루에 실제로 거래에 쓰인 지갑 주소 수 — 네트워크를 쓰는 사람 수.',read:'30일 변화율. +5% 이상 활발 · −5% 이하 한산.',low:'쓰는 사람이 줄어든다 → 가격보다 먼저 꺾이는 일이 많다.',high:'쓰는 사람이 는다 → 실수요 증가.'},
 hashrate:{what:'채굴 컴퓨터들의 총 연산력(7일 평균). 채굴자가 돈이 되면 늘리고 손해면 끈다.',read:'30일 변화율. −10% 이하 급락 = 채굴자 항복 · +5% 이상 확장.',low:'채굴자가 기계를 끈다 = 손해 구간. 역사적으로 바닥 근처지만 채굴자 매도가 잠깐 나온다.',high:'채굴자가 투자를 늘린다 = 앞으로도 돈이 된다고 본다.'},
 mvrv:{what:'지금 시가총액 ÷ 모두가 산 가격의 합(실현 시총). "평균적으로 몇 배 벌고 있나".',read:'1 미만 = 평균 손실(바닥권) · 1~3 정상 · 3 이상 과열 · 3.5~4 사이클 고점.',low:'평균적으로 손해 중 → 더 팔 사람이 적다 → 역사적 바닥권.',high:'평균 3배 이상 수익 → 차익실현 욕구 최고 → 고점권.'},
 mvrv_z:{what:'MVRV 를 "평소 대비 얼마나 튀었나"로 표준화한 점수(변동성으로 나눈 값).',read:'0 근처 바닥 밴드 · 0.5~6 중간 · 6~7 이상 고점 밴드(과거 모든 고점이 이 밴드에 닿음).',low:'역사적 바닥 밴드.',high:'역사적 고점 밴드.'},
 sopr:{what:'오늘 움직인 코인들이 "산 가격 대비 얼마에 팔렸나"의 평균(7일). 1 = 본전.',read:'1 미만 지속 = 손절 매도 · 1 부근 균형 · 1.05 초과 = 이익 실현 활발.',low:'사람들이 손해 보고 판다 → 항복 국면. 오래 지속되면 팔 사람 소진.',high:'사람들이 이익 실현 중. 상승장에서는 1 까지 내려왔다 튕기는 곳이 매수점.'},
 nupl:{what:'전체 보유자의 미실현 이익−손실을 시총으로 나눈 비율. 시장 전체가 얼마나 벌고 있나.',read:'0 미만 항복 · 0~0.25 희망 · 0.25~0.5 낙관 · 0.5~0.75 믿음 · 0.75 이상 도취(고점).',low:'시장 전체가 손실 → 바닥권.',high:'시장 전체가 큰 이익 → 도취 = 고점권.'},
 puell:{what:'채굴자가 오늘 번 돈 ÷ 지난 1년 평균 수입. 채굴자 수익이 평소 대비 얼마나 좋은가.',read:'0.6 미만 채굴자 불황(바닥) · 0.6~3 정상 · 3 이상 채굴자 호황(고점).',low:'채굴자가 못 번다 → 역사적 바닥 신호.',high:'채굴자가 너무 잘 번다 → 채굴자 매도 압력 + 고점 신호.'},
 mayer:{what:'현재가 ÷ 200일 평균가. 장기 평균에서 얼마나 떨어져 있나.',read:'0.8 이하 저평가 · 0.85~2.2 정상 · 2.4 이상 과열.',low:'장기 평균보다 많이 싸다.',high:'장기 평균보다 너무 올랐다 → 되돌림 잦음.'},
 w200:{what:'현재가 ÷ 200주(약 4년) 평균가. 비트코인 역사상 모든 약세장 바닥이 이 선 근처에서 멈췄다.',read:'1.1 미만 바닥선 근접 · 1~4 중간 · 4 이상 사이클 고점권.',low:'역사적 바닥선에 닿음 → 장기 매수 구간.',high:'장기 평균의 4배 → 과거 고점 배율.'},
 halving:{what:'채굴 보상이 절반으로 줄어든 날(반감기)로부터 며칠 지났나. 4년마다 공급이 줄어 사이클을 만든다.',read:'과거 3번 모두 반감기 후 12~18개월(365~550일)에 고점, 그 뒤 약 1년 약세, 다음 반감기 전 회복.',low:'반감기 직후 = 공급 충격 시작.',high:'550일 넘으면 과거 패턴상 고점 이후 구간.'},
 cb_prem:{what:'미국 거래소 코인베이스 가격이 바이낸스보다 몇 % 비싼가. 미국 기관·ETF 는 코인베이스에서 산다.',read:'+0.05% 이상 미국이 사는 중 · ±0.05 중립 · −0.05% 이하 미국이 파는 중.',low:'미국 기관이 팔거나 안 산다.',high:'미국 기관·ETF 매수가 들어오고 있다.'},
 ibit_flow:{what:'세계 최대 비트코인 현물 ETF(블랙록 IBIT)에 돈이 들어왔나 나갔나(백만$). 발행주식 증감×주당가치로 계산.',read:'최근 5일 합 +200M$ 이상 유입 · −200M$ 이하 유출. IBIT 는 전체 ETF 유입의 약 절반.',low:'기관·개인의 ETF 환매 → 매도 압력.',high:'ETF 로 새 돈이 들어옴 → 2024년 이후 가장 큰 매수 주체.'},
 cot_am:{what:'CME 비트코인 선물에서 자산운용사(연기금·펀드)가 순매수한 계약 수(주간). 진짜 기관 수요.',read:'4주 변화율 +10% 이상 늘면 좋음 · −10% 이하 줄면 경계.',low:'기관이 포지션을 줄인다.',high:'기관이 포지션을 늘린다.'},
 cot_lev:{what:'헤지펀드(레버리지 펀드)의 순포지션. 보통 큰 마이너스인데, 이건 "현물 ETF 사고 선물 파는" 무위험 차익거래라 방향 신호가 아니다.',read:'숫자 자체보다 갑자기 숏이 줄어드는지 본다.',low:'숏이 크다 = 차익거래 활발 = 정상.',high:'숏이 급감 = 차익거래 청산 = 시장 전체 위험선호 후퇴 신호.'},
 funding:{what:'무기한 선물에서 롱(상승 베팅)이 숏에게 8시간마다 내는 이자. 롱이 많으면 양수, 숏이 많으면 음수.',read:'0.01% 기본 · 0.05% 이상 롱 과열(연 55%) · 음수 숏 과밀.',low:'숏이 너무 많다 → 가격이 조금만 오르면 숏 청산으로 급등(숏스퀴즈).',high:'롱이 너무 많다 → 조금만 떨어지면 롱 청산 연쇄(롱 스퀴즈).'},
 oi:{what:'아직 청산되지 않은 선물 계약 총액(십억$). 시장에 쌓인 레버리지(빚) 규모.',read:'30일 변화율을 가격 변화와 같이 본다. OI 급증 + 가격 정체 = 위험.',low:'레버리지가 정리됨(디레버리징 완료) → 바닥 다지기.',high:'빚으로 산 포지션이 쌓임 → 청산 연쇄로 변동성 폭발 전조.'},
 ls_ratio:{what:'바이낸스 개인 계좌 중 롱 계좌 수 ÷ 숏 계좌 수.',read:'0.9 이하 숏 우세 · 1 균형 · 2 이상 롱 쏠림.',low:'개미가 하락에 베팅 → 거꾸로 상승 여지(역발상).',high:'개미가 상승에 몰림 → 거꾸로 하락 위험(역발상).'},
 taker:{what:'"지금 당장 사겠다"(시장가 매수) 물량 ÷ "지금 당장 팔겠다" 물량.',read:'1.1 이상 공격적 매수 · 0.9 이하 공격적 매도.',low:'급하게 파는 사람이 많다.',high:'급하게 사는 사람이 많다 = 실제 수요.'},
 dvol:{what:'옵션 시장이 예상하는 앞으로 30일 비트코인 변동폭(연율 %). 주식의 VIX 와 같다.',read:'40 미만 조용함(큰 움직임 전조, 방향은 모름) · 40~80 보통 · 80 이상 패닉.',low:'너무 조용하다 → 곧 큰 움직임(위든 아래든).',high:'공포 극대 → 역사적으로 바닥 근처.'},
 netliq:{what:'미국 연준이 시장에 풀어둔 달러 = 연준 자산 − 재무부 계좌(TGA) − 역레포(RRP). "시장에 실제로 돌아다니는 달러".',read:'13주 변화율. +1% 이상 확대(좋음) · −1% 이하 축소(역풍).',low:'시장에서 달러가 빠져나감 → 위험자산 전체 역풍.',high:'달러가 풀림 → 비트코인이 가장 민감하게 반응하는 변수.'},
 m2:{what:'미국 통화량(M2)이 1년 전보다 몇 % 늘었나. 돈이 많이 풀리면 약 10주 뒤 비트코인이 따라 오른다는 것이 가장 유명한 매크로 선행.',read:'+3% 이상이고 상승 중이면 좋음 · +1% 미만 정체.',low:'돈이 안 풀린다 → 유동성 부족.',high:'돈이 풀린다 → 2~3개월 뒤 우호.'},
 dff:{what:'미국 기준금리(연방기금 실효금리).',read:'6개월 변화. 내려가는 중이면 좋음, 올라가면 역풍.',low:'금리 인하 사이클 = 위험자산 우호(단, 경기침체 때문에 내리면 예외).',high:'금리 인상 = 위험자산 역풍.'},
 dxy:{what:'달러 가치를 주요 6개 통화 대비로 지수화한 것. 비트코인과 반대로 움직이는 경향.',read:'3개월 변화율. −2% 이하 달러 약세(좋음) · +2% 이상 달러 강세(역풍).',low:'달러 약세 → 비트코인 강세 경향.',high:'달러 강세 → 비트코인 약세 경향.'},
 us10y:{what:'미국 10년 국채 금리. "안전하게 벌 수 있는 이자"가 높으면 위험자산 매력이 준다.',read:'3개월 변화율. −5% 이하 금리 하락(좋음) · +5% 이상 상승(역풍).',low:'안전자산 이자가 줄어 위험자산으로 이동.',high:'안전자산 이자가 높아져 위험자산 이탈.'},
 stable:{what:'USDT·USDC 등 달러 스테이블코인 총 발행량(십억$). 코인을 사려고 거래소에 대기 중인 달러.',read:'30일 변화율. +1.5% 이상 신규 발행(좋음) · −1% 이하 소각(이탈).',low:'대기 자금이 빠져나감.',high:'새 달러가 코인판에 들어옴 → 매수 대기 자금 증가.'},
 eth_btc:{what:'이더리움 가격을 비트코인으로 나눈 값. "ETH 1개 = BTC 몇 개". 알트 대장이 BTC 보다 잘 가는지의 대표 척도.',read:'30일 변화율. +8% 이상 ETH 우세(알트 순환 시작) · −8% 이하 BTC 우세.',low:'돈이 BTC 로 집중 → 알트는 참을 때.',high:'ETH 가 BTC 를 이기기 시작 → 역사적으로 알트 전체로 번지는 첫 신호.'},
 alt_mcap_ratio:{what:'주요 알트 12종(ETH·BNB·ADA·DOGE·DOT·LINK·LTC·BCH 등) 시총 합 ÷ BTC 시총. 시총이 어느 쪽으로 이동하는지.',read:'30일 변화율. +5% 이상 알트로 이동 · −5% 이하 BTC 로 집중.',low:'BTC 국면.',high:'알트 순환 진행.'},
 stable_ratio:{what:'스테이블코인 총공급 ÷ (BTC+ETH 시총). "대기 중인 달러가 시장 대비 얼마나 큰가".',read:'30일 변화율. −5% 이하 = 대기자금이 코인으로 들어감(위험선호) · +5% 이상 = 코인에서 스테이블로 대피(위험회피).',low:'돈이 코인으로 투입되는 중 → 알트까지 온기가 퍼지는 국면.',high:'대피 중 → 알트가 가장 먼저 맞는다.'},
 eth_netflow:{what:'지난 7일 ETH 가 거래소로 들어온 돈 − 나간 돈(백만$). BTC 거래소 순유입과 같은 논리.',read:'−300M$ 미만 유출(좋음) · ±300 균형 · +300M$ 초과 유입(매도 대기).',low:'ETH 를 빼서 보관 → 알트 대장 수급 우호.',high:'ETH 를 팔려고 거래소로 → 알트 전체 하락 압력.'},
 upbit_alt_share:{what:'업비트에서 알트(거래대금 상위 30종) 거래대금이 전체(알트+BTC)의 몇 %인가. 한국 개미의 알트 쏠림.',read:'200일 중 백분위. 상위 20% 알트 순환 진행(90%↑ 과열) · 하위 20% 알트 무관심.',low:'개미가 알트를 안 본다 → BTC 국면.',high:'개미가 알트로 몰림 → 순환 진행. 극단이면 국내 주도 과열(김프보다 먼저 나타난다).'},
 alt_funding:{what:'ETH·SOL·XRP·DOGE·BNB 펀딩비 평균 − BTC 펀딩비. 알트 선물 롱이 BTC 보다 얼마나 과열됐나.',read:'+0.02% 이상 알트 롱 과열 · −0.01% 이하 알트 숏 과밀 · 사이는 정상.',low:'알트에 숏이 몰림 → 숏스퀴즈로 급등 여지.',high:'알트에 빚으로 롱이 몰림 → 조금만 떨어져도 연쇄 청산 → 알트 급락.'},
 altbreadth:{what:'시총 상위 50개 알트코인 중 지난 30일 수익률이 비트코인을 이긴 비율.',read:'25% 이하 비트코인 시즌(사이클 초·중반) · 75% 이상 알트시즌(사이클 후반 과열).',low:'돈이 비트코인에만 몰림 = 사이클 초반 특징.',high:'잡코인까지 다 오름 = 사이클 후반, 고점 근처가 잦았다.'},
 btc_dom:{what:'전체 코인 시총 중 비트코인 비중.',read:'30일 변화(%p). −2p 이하 = 알트로 순환 · +2p 이상 = BTC 집중. (서버 누적 30일 뒤부터 판정)',low:'알트 순환 국면.',high:'비트코인 집중 국면.'},
};
const GAUGE={
 fng:[0,100,25,75,'hot'],kimp:[-3,8,0,5,'hot'],mvrv:[0.5,4,1,3,'hot'],mvrv_z:[-1,8,0.5,6,'hot'],sopr:[0.95,1.08,0.98,1.05,'hot'],
 nupl:[-0.3,1,0.25,0.7,'hot'],puell:[0.2,4,0.6,3,'hot'],mayer:[0.5,2.8,0.85,2.2,'hot'],w200:[0.7,5,1.1,4,'hot'],
 funding:[-0.03,0.1,0,0.05,'hot'],ls_ratio:[0.5,3,0.9,2,'hot'],taker:[0.7,1.3,0.9,1.1,'cool'],dvol:[20,120,40,80,'mid',['압축=폭발 전조','정상','패닉=바닥 근처']],
 cb_prem:[-0.3,0.3,-0.05,0.05,'cool'],altbreadth:[0,100,25,75,'cool',['BTC 시즌','혼재','알트시즌(과열 경계)']],
 // 아래는 판정에 쓴 파생값(e.jv: 변화율·백분위)으로 그린다
 upbit_ratio:[0,100,15,90,'hot',['개미 이탈','보통','개미 과열'],1],gt_world:[0,100,20,90,'hot',['무관심','보통','관심 정점'],1],gt_kr:[0,100,20,90,'hot',['무관심','보통','관심 정점'],1],
 wiki_ko:[0,100,20,90,'hot',['무관심','보통','관심 정점'],1],wiki_en:[0,100,20,90,'hot',['무관심','보통','관심 정점'],1],
 ex_netflow:[-2500,2500,-500,500,'hot',['유출=보관','균형','유입=매도 대기']],ex_supply:[-6,6,-1,1,'hot',['감소=축적','보합','증가=매도'],1],
 adr_act:[-25,25,-5,5,'cool',['사용 감소','보합','사용 증가'],1],hashrate:[-25,25,-10,5,'cool',['채굴자 항복','보합','확장'],1],
 ibit_flow:[-1500,1500,-200,200,'cool',['유출','보합','유입'],1],cot_am:[-60,60,-10,10,'cool',['기관 축소','보합','기관 확대'],1],
 oi:[-40,60,-15,25,'hot',['디레버리징','보통','레버리지 누적'],1],netliq:[-6,6,-1,1,'cool',['유동성 축소','보합','유동성 확대'],1],
 m2:[-2,10,1,3,'cool',['정체','완만','확장'],1],dff:[-40,40,-3,3,'hot',['인하 중','동결','인상 중'],1],
 us10y:[-25,25,-5,5,'hot',['금리 하락','보합','금리 상승'],1],dxy:[-8,8,-2,2,'hot',['달러 약세','보합','달러 강세'],1],
 stable:[-5,7,-1,1.5,'cool',['소각=이탈','정체','발행=유입'],1],
 // 알트 순환 축 — 오른쪽(초록)=알트 순환 진행, 왼쪽(빨강)=BTC 국면
 eth_btc:[-25,25,-8,8,'cool',['BTC 우세','보합','ETH 우세'],1],alt_mcap_ratio:[-20,20,-5,5,'cool',['BTC 집중','보합','알트로 이동'],1],
 stable_ratio:[-20,20,-5,5,'hot',['코인 투입','보합','스테이블 대피'],1],eth_netflow:[-1500,1500,-300,300,'hot',['유출=보관','균형','유입=매도 대기']],
 upbit_alt_share:[0,100,20,80,'cool',['알트 무관심','보통','알트 쏠림'],1],alt_funding:[-0.04,0.06,-0.01,0.02,'hot',['알트 숏 과밀','정상','알트 롱 과열']],
 btc_dom:[-6,6,-2,2,'hot',['알트 순환','보합','BTC 집중'],1],halving:[0,1460,365,550,'hot',['상승 국면','과거 고점 구간','고점 이후·약세']],
};
function gauge(k,v,E){
  const g=GAUGE[k]; if(!g||v==null) return '';
  const [mn,mx,lo,hi,dir,custom,useJv]=g; if(useJv){ v=E&&E.jv; if(v==null) return ''; } const P=x=>Math.max(0,Math.min(100,(x-mn)/(mx-mn)*100));
  const c={hot:['#bbf7d0','#fef9c3','#fecaca'],cool:['#fecaca','#fef9c3','#bbf7d0'],mid:['#fef9c3','#bbf7d0','#fef9c3']}[dir];
  const lbl=custom||{hot:['바닥권','정상','과열'],cool:['약세','중립','강세'],mid:['경계','정상','경계']}[dir];
  return `<div style="margin:3px 0 1px">
    <div style="position:relative;height:8px;border-radius:4px;overflow:hidden;background:linear-gradient(90deg,${c[0]} 0 ${P(lo)}%,${c[1]} ${P(lo)}% ${P(hi)}%,${c[2]} ${P(hi)}% 100%)">
      <div style="position:absolute;left:${P(v)}%;top:-1px;width:3px;height:10px;background:#0f172a;border-radius:2px;transform:translateX(-50%)"></div></div>
    <div style="display:flex;justify-content:space-between;font-size:9.5px;color:#94a3b8"><span>${lbl[0]} ${lo}</span><span>${lbl[1]}${useJv&&E.jl?' · '+E.jl+' '+(E.jv>0?'+':'')+E.jv.toFixed(1):''}</span><span>${hi} ${lbl[2]}</span></div></div>`;
}
function helpBox(k){
  const h=HELP[k]; if(!h) return '';
  return `<div class="clhelp" style="margin-top:6px;padding:6px 8px;border-radius:6px;background:#f0f9ff;border:1px solid #bae6fd;font-size:11.5px;line-height:1.5;color:#0c4a6e">
    <div><b>이게 뭐지?</b> ${h.what}</div>
    <div><b>읽는 법</b> ${h.read}</div>
    <div><b>낮으면</b> ${h.low} <b style="margin-left:4px">높으면</b> ${h.high}</div></div>`;
}
function card(k,e){
  const st=ST[e.status]||['⚪','—','#64748b','#f1f5f9'];
  const stale=e.stale?'<span title="이번 수집 실패 — 직전 값" style="color:#b45309;font-size:10px"> ⚠직전값</span>':'';
  const extra=k==='fng'?` <span class="note">${e.label||''}</span>`:k==='cb_prem'&&e.now!=null?` <span class="note">실시간 ${(e.now>0?'+':'')+e.now.toFixed(3)}%</span>`
    :k==='funding'&&e.last8h!=null?` <span class="note">직전 8h ${(e.last8h>0?'+':'')+e.last8h.toFixed(4)}%</span>`
    :k==='ibit_flow'?` <span class="note">AUM $${nf(e.aum/1e9,1)}B · ${e.asof||''}</span>`
    :k==='halving'?` <span class="note">다음 ${e.next} (D-${e.next_days})</span>`
    :k==='w200'?` <span class="note">200W ≈ $${nf(e.w200,0)}</span>`
    :k==='altbreadth'&&e.top?` <span class="note">BTC 30D ${(e.btc30>0?'+':'')+nf(e.btc30,1)}% · 상위 ${e.top.slice(0,3).map(t=>t[0]+' '+(t[1]>0?'+':'')+t[1]+'%').join(' · ')}</span>`:'';
  const cvid='cl_cv_'+k;
  return `<div class="box" style="padding:10px 12px;border-top:3px solid ${st[2]};display:flex;flex-direction:column;min-width:0">
    <div style="display:flex;justify-content:space-between;align-items:baseline;gap:6px">
      <div style="font-size:12.5px;font-weight:700;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${e.name||k}${stale}</div>
      <span style="font-size:10.5px;padding:1px 7px;border-radius:9px;background:${st[3]};color:${st[2]};font-weight:700;white-space:nowrap">${st[0]} ${st[1]}</span></div>
    <div style="font-size:19px;font-weight:800;margin:2px 0 0;line-height:1.2">${fmtV(k,e)}<span class="note" style="font-weight:400"> ${e.d||''}</span></div>
    <div class="note" style="min-height:14px">${extra}</div>
    ${gauge(k,e.v,e)}
    ${e.s&&e.s.length>1?`<div class="clsp" style="position:relative;height:100px;flex:0 0 100px;overflow:hidden;margin:4px 0"><canvas id="${cvid}"></canvas></div><div class="note" style="font-size:9.5px;margin-top:-2px"><span style="color:${GCOL[e.group]||'#334155'}">■</span> 지표(왼쪽 축) <span style="color:#f59e0b">━</span> BTC 가격(오른쪽 축)</div>`:`<div class="note" style="margin:6px 0;padding:5px 8px;background:#f8fafc;border-radius:6px">${NOCHART[k]||'추세 시계열 없음'}${e.s&&e.s.length===1?' (누적 시작 '+e.s[0][0]+')':''}</div>`}
    <div style="font-size:11.5px;color:#0f172a;margin-top:2px"><b>판정</b> ${e.judge||'—'}</div>
    <div class="note" style="margin-top:3px;color:#64748b"><b>왜 선행</b> ${e.why||''}</div>
    ${helpBox(k)}
  </div>`;
}
function axisBox(a,isAlt){
  const col=a.score==null?'#94a3b8':a.score>=0.3?'#16a34a':a.score<=-0.3?'#dc2626':'#ca8a04';
  const pos=a.score==null?50:(a.score+1)/2*100;
  return `<div style="flex:1;min-width:190px;border:1px solid #e2e8f0;border-left:4px solid ${col};border-radius:8px;padding:8px 12px;background:#fff">
    <div style="font-size:12px;color:#475569">${a.name}${isAlt?' <span style="font-size:10px;color:#9333ea">— 시장 종합점수에 미포함(순환 위치 질문)</span>':''}</div>
    <div style="font-size:17px;font-weight:800;color:${col}">${a.label} <span style="font-size:11px;font-weight:400;color:#64748b">${a.score==null?'':(a.score>0?'+':'')+a.score.toFixed(2)} · 🟢${a.bull} 🔴${a.bear} /${a.n}</span></div>
    <div style="position:relative;height:6px;border-radius:3px;background:linear-gradient(90deg,#fecaca,#fef9c3,#bbf7d0);margin-top:6px"><div style="position:absolute;left:${pos}%;top:-3px;width:3px;height:12px;background:#0f172a;border-radius:2px;transform:translateX(-50%)"></div></div>
  </div>`;
}
function render(){
  if(!D) return;
  charts.forEach(c=>{try{c.destroy();}catch(e){}}); charts.length=0;
  PX=((D.ind||{})._px||{}).s||null;
  $('cl_asof').textContent='기준 '+(D.as_of||'')+' · 서버 매일 06:55 자동 수집'+(D.errors&&D.errors.length?` · 수집 실패 ${D.errors.length}건`:'');
  const O=D.overall||{}, A=D.axes||{};
  const oc=O.score==null?'#94a3b8':O.score>=0.25?'#16a34a':O.score<=-0.25?'#dc2626':'#ca8a04';
  $('cl_overall').innerHTML=`<div style="display:flex;gap:14px;align-items:center;flex-wrap:wrap">
      <label style="font-size:11.5px;color:#475569;cursor:pointer;margin-left:auto"><input type="checkbox" id="cl_helpchk" ${SHOWHELP?'checked':''}> 쉬운 설명 보기</label>
      <div style="font-size:22px;font-weight:900;color:${oc}">${O.text||'—'}</div>
      <div class="note">종합 ${O.score==null?'—':(O.score>0?'+':'')+O.score.toFixed(2)} (−1 ~ +1 · 4축 평균)</div></div>
    <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:10px">${['short','flow','cycle','macro','alt'].filter(k=>A[k]).map(k=>axisBox(A[k],k==='alt')).join('')}</div>
    <div class="note" style="margin-top:8px">읽는 법: <b>단기</b>축이 🔴면 지금 사기엔 과열(눌림 대기), 🟢면 공포 국면(역발상). <b>수급</b>축은 지갑·기관·대기자금이 실제로 사고 있는지 — 상승이 <u>유지</u>될지를 가르는 축.
      <b>밸류</b>축은 사이클 상 위치(바닥권/고점권). <b>매크로</b>축은 달러 유동성 — BTC 는 유동성에 약 2~3개월 후행. 네 축이 모두 🟢인 시점은 드물고, 보통 "수급🟢 + 단기🔴" 같은 조합으로 나타난다.
      <b>알트 순환</b>축은 질문이 다르다 — "시장이 오를까"가 아니라 <u>"BTC 를 들고 있을 때냐, 알트로 갈아탈 때냐"</u>. 알트는 BTC 방향을 1.5~3배로 증폭해 따라가므로 위 4축이 🔴면 알트는 더 크게 맞는다. 🟢(순환 진행)이면서 알트 강세폭 75%↑면 사이클 후반 과열.</div>`;
  // 그룹별 카드
  const IND=D.ind||{}; const keys=Object.keys(IND).filter(k=>!k.startsWith('_')&&IND[k].name);
  $('cl_groups').innerHTML=(D.groups||[]).map(g=>{
    const ks=keys.filter(k=>IND[k].group===g); if(!ks.length) return '';
    return `<h3 style="color:${GCOL[g]||'#334155'}">${g} <span class="note">${ks.length}개</span></h3>
      <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:10px">${ks.map(k=>card(k,IND[k])).join('')}</div>`;}).join('');
  keys.forEach(k=>{const cv=$('cl_cv_'+k); if(cv) spark(cv,IND[k].s,GCOL[IND[k].group]||'#334155',k);});
  document.querySelectorAll('#p_cl .clhelp').forEach(el=>el.hidden=!SHOWHELP);
  const hc=$('cl_helpchk'); if(hc) hc.onchange=()=>{ SHOWHELP=hc.checked; try{localStorage.setItem('cl_help',SHOWHELP?'1':'0');}catch(e){} document.querySelectorAll('#p_cl .clhelp').forEach(el=>el.hidden=!SHOWHELP); };
  // 정책
  const P=D.policy||{};
  const ev=P.events||[];
  $('cl_policy').innerHTML=ev.length?`<div class="note" style="margin-bottom:6px">${P.as_of?'갱신 '+P.as_of+' · ':''}${P.summary||''}</div>
    <table style="border-collapse:collapse;font-size:12px;background:#fff;width:100%"><thead><tr style="background:#f8fafc">${['날짜','이벤트','영향','판정'].map(h=>`<th style="border:1px solid #e2e8f0;padding:4px 7px">${h}</th>`).join('')}</tr></thead>
    <tbody>${ev.map(x=>`<tr><td style="border:1px solid #e2e8f0;padding:3px 7px;white-space:nowrap">${x.date||''}</td><td style="border:1px solid #e2e8f0;padding:3px 7px">${x.title||''}</td><td style="border:1px solid #e2e8f0;padding:3px 7px;color:#475569">${x.impact||''}</td><td style="border:1px solid #e2e8f0;padding:3px 7px;white-space:nowrap">${(ST[x.status]||['⚪','—'])[0]} ${(ST[x.status]||['','—'])[1]}</td></tr>`).join('')}</tbody></table>`
    :'<div class="note">아직 없음 — 시황 보고서 실행 시 SEC·스테이블코인 법안·FOMC·ETF 승인 등 정책 이벤트를 LLM 이 판정해 <code>data/db/cryptolead_policy.json</code> 으로 올린다 (형식: {as_of, summary, events:[{date,title,impact,status:bull|neu|bear}]}).</div>';
  if(D.errors&&D.errors.length) $('cl_err').innerHTML='<details><summary class="note" style="cursor:pointer">수집 실패 '+D.errors.length+'건 (직전 값 유지)</summary><div class="note">'+D.errors.map(e=>'· '+e).join('<br>')+'</div></details>';
  else $('cl_err').innerHTML='';
}
function load(force){
  if(D&&!force){ render(); return; }
  $('cl_asof').textContent='불러오는 중…';
  fetch('/api/db/cryptolead',{cache:'no-cache'}).then(r=>{ if(!r.ok) throw new Error('HTTP '+r.status); return r.json(); })
  .then(j=>{ D=j; render(); })
  .catch(e=>{ $('cl_asof').textContent='로드 실패: '+e.message+' (서버 수집 전이면 다음 06:55 이후 표시)'; });
}
window.renderCryptolead=function(){ load(false); };
document.addEventListener('DOMContentLoaded',function(){ const b=$('cl_reload'); if(b) b.onclick=()=>load(true); });
})();
