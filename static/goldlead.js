/* goldlead.js — 🥇 금 선행지표 탭 (2026-09-22 신설)
   데이터: /api/db/goldlead (scripts/fetch_goldlead.py · 매일 07:05 cron · LLM 토큰 0)
   구성: ① 종합 신호등(4축·실질금리 축 2배 가중) ② 통설 vs 실측 표(20년 월간) ③ 그룹별 지표 카드(현재값·판정·게이지·1년 스파크+금 가격 오버레이·쉬운 설명)
   코인 선행 탭(cryptolead.js)과 같은 문법. 리서치용, 투자권유 아님. */
(function(){
'use strict';
let D=null; const charts=[]; let SHOWHELP=true; try{ SHOWHELP=localStorage.getItem('gl_help')!=='0'; }catch(e){}
const $=id=>document.getElementById(id);
const E=s=>String(s??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
const ST={bull:['🟢','금 우호','#16a34a','#dcfce7'],neu:['🟡','중립','#a16207','#fef9c3'],bear:['🔴','역풍·과열','#dc2626','#fee2e2']};
const GCOL={'실질금리·달러':'#b91c1c','지정학·공포':'#7c3aed','포지셔닝·ETF·광산주':'#1d4ed8','한국·대중 심리':'#be185d','상대가격':'#0f766e'};
const nf=(n,d)=>n==null?'—':Number(n).toLocaleString(undefined,{maximumFractionDigits:d==null?2:d});
function fmtV(k,e){ const v=e.v; if(v==null) return '—'; const u=e.unit||'';
  if(k==='cot_mm'||k==='cot_pm') return (v>0?'+':'')+nf(v,0)+' 계약';
  if(k==='iau_flow') return (v>0?'+':'')+nf(v,0)+' M$';
  if(k==='krx_gold') return nf(v,0)+' 원/g';
  if(k==='kr_prem') return (v>0?'+':'')+v.toFixed(2)+'%';
  if(k==='gdx_rs') return v.toFixed(3)+'×';
  if(u==='%') return nf(v,2)+'%';
  return nf(v, Math.abs(v)>=100?1:2)+(u&&u!=='x'?' '+u:'');
}
let PX=null;
function pxAt(d){ if(!PX||!PX.length||d<PX[0][0]) return null; let lo=0,hi=PX.length-1; while(lo<hi){const m=(lo+hi+1)>>1; if(PX[m][0]<=d) lo=m; else hi=m-1;} return PX[lo][1]; }
function spark(cv,s,color,k){
  if(!s||s.length<2) return;
  const labels=s.map(x=>x[0]), data=s.map(x=>x[1]);
  const TH={real10:[0,2],bei:[2,2.5],vix:[20,30],gs_ratio:[60,80],go_ratio:[15,30],kr_prem:[0,5],cot_mm:[0],iau_flow:[0],cot_pm:[0]}[k]||[];
  const ds=[{label:'지표',data,borderColor:color,backgroundColor:color+'22',fill:true,pointRadius:0,borderWidth:1.3,tension:0.15,yAxisID:'y',order:2}];
  TH.forEach(t=>ds.push({label:'_th',data:data.map(()=>t),borderColor:'#94a3b8',borderDash:[3,3],borderWidth:0.8,pointRadius:0,fill:false,yAxisID:'y',order:3}));
  const px=labels.map(pxAt); const hasPx=px.some(v=>v!=null)&&k!=='krx_gold';
  if(hasPx) ds.push({label:'금',data:px,borderColor:'#d97706',backgroundColor:'transparent',fill:false,pointRadius:0,borderWidth:1.4,tension:0.15,yAxisID:'y2',order:1,spanGaps:false});
  charts.push(new Chart(cv,{type:'line',data:{labels,datasets:ds},options:{responsive:true,maintainAspectRatio:false,animation:false,interaction:{mode:'index',intersect:false},
    plugins:{legend:{display:false},tooltip:{filter:i=>i.dataset.label!=='_th',callbacks:{label:c=>c.dataset.label==='금'?'금 $'+nf(c.raw,0):'지표 '+nf(c.raw,4)}}},
    scales:{x:{display:true,ticks:{maxTicksLimit:4,font:{size:9},maxRotation:0,callback:(v,i)=>labels[i]?labels[i].slice(2,7):''},grid:{display:false}},
            y:{position:'left',ticks:{font:{size:9},maxTicksLimit:4,color:color},grid:{color:'#f1f5f9'}},
            y2:{display:hasPx,position:'right',ticks:{font:{size:9},maxTicksLimit:4,color:'#d97706',callback:v=>'$'+nf(v,0)},grid:{display:false}}}}}));
}
const HELP={
 real10:{what:'물가를 뺀 미국 10년 국채 실질금리(TIPS). "금 대신 안전한 채권을 들면 실제로 얼마를 버나".',read:'수준보다 3개월 변화. −0.25%p 이하 하락(우호) · +0.25%p 이상 상승(역풍).',low:'채권 실질수익이 줄어 이자 없는 금의 상대 매력 상승 — 2020·2024 랠리의 배경.',high:'2013·2022 금 약세의 주범. 교과서 1순위 변수.'},
 bei:{what:'시장이 예상하는 향후 10년 물가상승률(명목금리−실질금리).',read:'3개월 변화 ±0.15%p.',low:'디플레 우려 — 금엔 역풍(실질금리 상승 경로).',high:'인플레 기대 상승 — 통설 "인플레→금"이 실제로 작동하는 경로.'},
 dxy:{what:'달러 가치 지수. 금은 달러로 표시되므로 달러가 싸지면 같은 금이 더 비싸 보인다.',read:'3개월 변화 ±2%.',low:'달러 약세 = 금 우호(20년 실측 동행 r≈−0.47, 가장 강한 통설).',high:'달러 강세 = 금 역풍. 단 2024~25 는 중앙은행 매수로 둘 다 오른 예외 구간.'},
 dff:{what:'미국 기준금리(실효).',read:'6개월 변화 ±0.25%p.',low:'인하 사이클. 단 인하 기대는 미리 반영돼 실제 인하 때 되돌림도 잦다.',high:'인상 사이클 = 역풍(2022).'},
 cpi:{what:'미국 소비자물가 전년비. 인스타 카드 1번 "인플레↑=금↑"의 지표.',read:'판정 없음(참고). 20년 실측에서 CPI 자체는 금과 유의미한 동행이 없다 — 실질금리가 진짜 변수.',low:'—',high:'CPI 가 높아도 연준이 그 이상 올리면(2022) 금은 안 오른다.'},
 gpr:{what:'전 세계 주요 신문에서 전쟁·테러·군사긴장 기사가 얼마나 많이 나왔나를 지수화(1985~).',read:'20년 백분위 80% 이상이면 지정학 위험 상위권.',low:'평시.',high:'통설 "전쟁→금". 실측: 20년 동행 상관 ≈0 — 급등 국면의 며칠만 반영되고 평균적으론 무관.'},
 vix:{what:'미국 주식 옵션이 예상하는 30일 변동성 = 공포지수.',read:'25 이상 공포 국면.',low:'평온.',high:'공포 초기엔 금도 같이 팔린다(2020-03 −12%) → 그 뒤 안전자산으로 회복하는 2단계.'},
 cot_mm:{what:'COMEX 금 선물에서 헤지펀드·CTA(운용사)가 순매수한 계약 수. 투기 자금의 쏠림.',read:'1년 중 백분위. 90% 이상 과밀(조정 취약) · 15% 이하 청산(바닥권).',low:'투기 롱이 다 빠졌다 → 역발상 매수 구간이 잦았다.',high:'롱이 너무 몰렸다 → 작은 악재에 청산 연쇄.'},
 cot_pm:{what:'광산회사·정련사 등 실물 사업자의 순포지션. 보통 생산분을 미리 파는 헤지라 순숏.',read:'판정 없음(참고). 숏이 줄어들면 생산자도 값이 더 오를 걸로 본다는 뜻.',low:'헤지 숏 확대 = 생산자가 현 가격에 만족.',high:'헤지 축소 = 생산자도 강세 예상.'},
 iau_flow:{what:'iShares 금 ETF(IAU)에 돈이 들어왔나 나갔나(백만$). 발행주식 증감×NAV. 서구 투자자 수요.',read:'최근 5일 합 ±100M$. 서버가 매일 기록해 계산 — 1주일쯤 뒤부터 추세.',low:'ETF 환매 = 서구 투자수요 이탈(2021~22 약세장 특징).',high:'ETF 유입 = 2020·2024~25 랠리를 확인해준 지표.'},
 gdx_rs:{what:'금광주 ETF(GDX) ÷ 금 ETF(GLD). 광산주는 금의 레버리지라 금보다 먼저·크게 움직인다.',read:'60일 변화 ±5%.',low:'금이 올라도 광산주가 못 따라오면 랠리 의심.',high:'광산주가 앞서가면 시장이 금 강세를 확신.'},
 kr_prem:{what:'KRX 금현물(원/g)이 국제금(달러×환율 환산)보다 몇 % 비싼가 — 김치프리미엄의 금 버전.',read:'1~3% 정상 · 5% 이상 국내 과열 · 0% 이하 관심 소멸.',low:'국내 개인이 금을 안 산다 → 바닥권 특징.',high:'2025-02 프리미엄 20% 까지 치솟은 뒤 급락한 전례 — 국내 주도 과열 경고.'},
 krx_gold:{what:'한국거래소 금현물 시세(원/g). 국제금 + 환율 효과.',read:'참고(판정 없음).',low:'—',high:'—'},
 gt_world:{what:'전 세계 구글 "gold price" 검색 관심(5년 중 최고=100).',read:'5년 백분위 90% 이상 관심 정점 · 20% 이하 무관심.',low:'무관심 = 역발상.',high:'대중이 금값을 검색하기 시작하면 단기 고점이 잦았다.'},
 gt_kr:{what:'한국 구글 "gold price" 검색 관심.',read:'전세계와 같은 방식.',low:'국내 무관심.',high:'국내 대중 관심 정점 — 한국 프리미엄과 같이 보면 국내 과열이 보인다.'},
 gs_ratio:{what:'금 1온스로 은을 몇 온스 사나. 장기 평균 ~65.',read:'80 이상 금 고평가(은이 따라 오르거나 금이 쉼) · 60 이하 금 저평가.',low:'은이 먼저 달림 = 랠리 후반 과열 신호이기도.',high:'금만 오름 = 안전자산 수요 국면.'},
 go_ratio:{what:'금 1온스로 원유 몇 배럴을 사나.',read:'30 이상 경기둔화·완화 기대(금 강세+유가 약세) · 15 이하 인플레·과열.',low:'유가 급등 국면 — 인플레 통설이 작동하는 드문 구간.',high:'경기둔화 국면 — 실질금리 하락 기대와 동행.'},
};
const GAUGE={
 real10:[-1.5,1.5,-0.25,0.25,'hot',['하락=우호','보합','상승=역풍'],1],bei:[-1,1,-0.15,0.15,'cool',['기대인플레↓','보합','기대인플레↑'],1],
 dxy:[-8,8,-2,2,'hot',['달러 약세=우호','보합','달러 강세=역풍'],1],dff:[-1.5,1.5,-0.25,0.25,'hot',['인하 중','동결','인상 중'],1],
 gpr:[0,100,50,80,'cool',['평시','보통','위험 상위'],1],vix:[10,45,20,25,'cool',['평온','보통','공포=안전자산 수요']],
 cot_mm:[0,100,15,90,'hot',['청산=바닥권','보통','과밀=조정 취약'],1],iau_flow:[-600,600,-100,100,'cool',['환매','보합','유입'],1],
 gdx_rs:[-25,25,-5,5,'cool',['광산주 뒤처짐','동행','광산주 앞섬'],1],kr_prem:[-4,12,0,5,'hot',['관심 소멸','정상','국내 과열']],
 gt_world:[0,100,20,90,'hot',['무관심','보통','관심 정점'],1],gt_kr:[0,100,20,90,'hot',['무관심','보통','관심 정점'],1],
 gs_ratio:[40,110,60,80,'mid',['금 저평가','정상','금 고평가']],go_ratio:[5,50,15,30,'mid',['인플레·과열','정상','둔화·완화 기대']],
};
function gauge(k,v,E0){
  const g=GAUGE[k]; if(!g||v==null) return '';
  const [mn,mx,lo,hi,dir,custom,useJv]=g; if(useJv){ v=E0&&E0.jv; if(v==null) return ''; } const P=x=>Math.max(0,Math.min(100,(x-mn)/(mx-mn)*100));
  const c={hot:['#bbf7d0','#fef9c3','#fecaca'],cool:['#fecaca','#fef9c3','#bbf7d0'],mid:['#fef9c3','#bbf7d0','#fef9c3']}[dir];
  const lbl=custom||{hot:['바닥권','정상','과열'],cool:['약세','중립','강세'],mid:['경계','정상','경계']}[dir];
  return `<div style="margin:3px 0 1px"><div style="position:relative;height:8px;border-radius:4px;overflow:hidden;background:linear-gradient(90deg,${c[0]} 0 ${P(lo)}%,${c[1]} ${P(lo)}% ${P(hi)}%,${c[2]} ${P(hi)}% 100%)"><div style="position:absolute;left:${P(v)}%;top:-1px;width:3px;height:10px;background:#0f172a;border-radius:2px;transform:translateX(-50%)"></div></div>
    <div style="display:flex;justify-content:space-between;font-size:9.5px;color:#94a3b8"><span>${lbl[0]} ${lo}</span><span>${lbl[1]}${useJv&&E0.jl?' · '+E0.jl+' '+(E0.jv>0?'+':'')+E0.jv.toFixed(2):''}</span><span>${hi} ${lbl[2]}</span></div></div>`;
}
function helpBox(k){ const h=HELP[k]; if(!h) return ''; return `<div class="glhelp" style="margin-top:6px;padding:6px 8px;border-radius:6px;background:#fffbeb;border:1px solid #fde68a;font-size:11.5px;line-height:1.5;color:#78350f"><div><b>이게 뭐지?</b> ${h.what}</div><div><b>읽는 법</b> ${h.read}</div><div><b>낮으면</b> ${h.low} <b style="margin-left:4px">높으면</b> ${h.high}</div></div>`; }
function card(k,e){
  const st=ST[e.status]||['⚪','참고','#64748b','#f1f5f9'];
  const stale=e.stale?'<span title="이번 수집 실패 — 직전 값" style="color:#b45309;font-size:10px"> ⚠직전값</span>':'';
  const extra=k==='iau_flow'?` <span class="note">AUM $${nf(e.aum/1e9,1)}B · 누적 ${e.pts}일 · ${e.asof||''}</span>`:k==='kr_prem'&&e.krx?` <span class="note">KRX ${nf(e.krx,0)}원/g</span>`:'';
  const cvid='gl_cv_'+k;
  return `<div class="box" style="padding:10px 12px;border-top:3px solid ${st[2]};display:flex;flex-direction:column;min-width:0">
    <div style="display:flex;justify-content:space-between;align-items:baseline;gap:6px"><div style="font-size:12.5px;font-weight:700;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${E(e.name||k)}${stale}</div>
      <span style="font-size:10.5px;padding:1px 7px;border-radius:9px;background:${st[3]};color:${st[2]};font-weight:700;white-space:nowrap">${st[0]} ${st[1]}</span></div>
    <div style="font-size:19px;font-weight:800;margin:2px 0 0;line-height:1.2">${fmtV(k,e)}<span class="note" style="font-weight:400"> ${e.d||''}</span></div>
    <div class="note" style="min-height:14px">${extra}</div>${gauge(k,e.v,e)}
    ${e.s&&e.s.length>1?`<div class="glsp" style="position:relative;height:100px;flex:0 0 100px;overflow:hidden;margin:4px 0"><canvas id="${cvid}"></canvas></div><div class="note" style="font-size:9.5px;margin-top:-2px"><span style="color:${GCOL[e.group]||'#334155'}">■</span> 지표(왼쪽) <span style="color:#d97706">━</span> 금 선물 $/oz(오른쪽)</div>`:`<div class="note" style="margin:6px 0;padding:5px 8px;background:#f8fafc;border-radius:6px">⏳ 서버가 매일 기록해 추세를 만든다 — 며칠 뒤부터 표시${e.s&&e.s.length===1?' (누적 시작 '+e.s[0][0]+')':''}</div>`}
    <div style="font-size:11.5px;color:#0f172a;margin-top:2px"><b>판정</b> ${E(e.judge||'—')}</div>
    <div class="note" style="margin-top:3px;color:#64748b"><b>왜 선행</b> ${E(e.why||'')}</div>${helpBox(k)}</div>`;
}
function axisBox(a,w){
  const col=a.score==null?'#94a3b8':a.score>=0.3?'#16a34a':a.score<=-0.3?'#dc2626':'#ca8a04'; const pos=a.score==null?50:(a.score+1)/2*100;
  return `<div style="flex:1;min-width:190px;border:1px solid #e2e8f0;border-left:4px solid ${col};border-radius:8px;padding:8px 12px;background:#fff"><div style="font-size:12px;color:#475569">${a.name}${w>1?' <span style="font-size:10px;color:#b91c1c">가중 ×'+w+'</span>':''}</div>
    <div style="font-size:17px;font-weight:800;color:${col}">${a.label} <span style="font-size:11px;font-weight:400;color:#64748b">${a.score==null?'':(a.score>0?'+':'')+a.score.toFixed(2)} · 🟢${a.bull} 🔴${a.bear} /${a.n}</span></div>
    <div style="position:relative;height:6px;border-radius:3px;background:linear-gradient(90deg,#fecaca,#fef9c3,#bbf7d0);margin-top:6px"><div style="position:absolute;left:${pos}%;top:-3px;width:3px;height:12px;background:#0f172a;border-radius:2px;transform:translateX(-50%)"></div></div></div>`;
}
const MYNM={cpi:'인플레(CPI YoY)',real10:'실질금리(10Y TIPS)',dxy:'달러(광의 달러지수)',dff:'기준금리',gpr:'지정학 위험(GPR)',vix:'시장 공포(VIX)'};
function mythTable(M){
  if(!M||!M.length) return '<div class="note">통설 검증 데이터 없음</div>';
  const TD='border:1px solid #e2e8f0;padding:4px 8px;text-align:center;';
  const vc=v=>v==='통설대로'?'#16a34a':v==='부호 반대'?'#dc2626':'#a16207';
  return `<table style="border-collapse:collapse;font-size:12px;background:#fff;width:100%"><thead><tr style="background:#f8fafc">${['통설 (인스타 카드 공식)','지표','기간','동행 상관 r<br><span class="note" style="font-weight:400">같은 12개월 창</span>','선행 상관 (지표가 먼저)<br><span class="note" style="font-weight:400">3·6·12개월 앞</span>','실측 판정'].map(h=>`<th style="${TD}font-size:11.5px">${h}</th>`).join('')}</tr></thead><tbody>${
    M.map(m=>{const lead=(m.lags||[]).filter(r=>r.lag!=='동행').map(r=>`${r.lag}M ${r.r==null?'—':(r.r>0?'+':'')+r.r.toFixed(2)}`).join(' · ');
      return `<tr><td style="${TD}text-align:left">${E(m.myth)}</td><td style="${TD}">${MYNM[m.key]||m.key}</td><td style="${TD}color:#64748b">${E(m.period)}</td>
        <td style="${TD}font-weight:800;color:${m.co==null?'#94a3b8':(m.co*m.sign>0?'#16a34a':'#dc2626')}">${m.co==null?'—':(m.co>0?'+':'')+m.co.toFixed(2)}<span class="note" style="font-weight:400"> (n=${(m.lags||[{}])[0].n||'—'})</span></td>
        <td style="${TD}color:#475569;font-size:11px">${lead}</td><td style="${TD}font-weight:700;color:${vc(m.verdict)}">${E(m.verdict)}</td></tr>`;}).join('')}</tbody></table>
    <div class="note" style="margin-top:5px;line-height:1.6">📖 <b>동행 r</b> = 지표의 12개월 변화와 같은 기간 금 수익률의 상관(통설은 "같이 움직인다"는 주장이므로 이것이 검증 정본). |r|≥0.15 를 유의로 본다. <b>선행 r</b> = 지표가 N개월 먼저 움직이고 금이 따라오는지(예측력) — 부호가 동행과 반대로 나오면 "급등 뒤 되돌림(평균회귀)"이지 통설 반증이 아니다.
      실측 요약: <b>달러·실질금리·기준금리</b>는 통설대로(달러가 가장 강함), <b>인플레(CPI)·전쟁(GPR)·공포(VIX)</b>는 20년 평균으로는 유의미한 동행이 없다 — 인플레는 실질금리를 거쳐야 작동하고, 지정학·공포는 급등 며칠만 반영된다. 월간·수준차 기준, 소스 FRED·야후·GPR.</div>`;
}
function render(){
  if(!D) return; charts.forEach(c=>{try{c.destroy();}catch(e){}}); charts.length=0;
  PX=((D.ind||{})._px||{}).s||null;
  $('gl_asof').textContent='기준 '+(D.as_of||'')+' · 서버 매일 07:05 자동 수집'+(D.errors&&D.errors.length?` · 수집 실패 ${D.errors.length}건`:'');
  const O=D.overall||{}, A=D.axes||{}; const oc=O.score==null?'#94a3b8':O.score>=0.25?'#16a34a':O.score<=-0.25?'#dc2626':'#ca8a04';
  const px=PX&&PX.length?PX[PX.length-1]:null;
  $('gl_overall').innerHTML=`<div style="display:flex;gap:14px;align-items:center;flex-wrap:wrap">
      <div style="font-size:22px;font-weight:900;color:${oc}">${E(O.text||'—')}</div><div class="note">종합 ${O.score==null?'—':(O.score>0?'+':'')+O.score.toFixed(2)} (−1~+1 · 4축 가중평균)${px?' · 금 선물 $'+nf(px[1],0)+' ('+px[0]+')':''}</div>
      <label style="font-size:11.5px;color:#475569;cursor:pointer;margin-left:auto"><input type="checkbox" id="gl_helpchk" ${SHOWHELP?'checked':''}> 쉬운 설명 보기</label></div>
    <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:10px">${['rate','risk','pos','kr'].filter(k=>A[k]).map(k=>axisBox(A[k],k==='rate'?2:1)).join('')}</div>
    <div class="note" style="margin-top:8px;line-height:1.6">읽는 법: <b>실질금리·달러</b>축이 금의 방향을 결정하는 1순위(20년 실측 동행 상관이 가장 강함 → 가중 2배). <b>지정학·공포</b>는 급등 국면에서만 잠깐 작동. <b>포지셔닝·ETF·광산주</b>는 "오름이 유지될지"(투기 과밀이면 취약, ETF 유입·광산주 선행이면 확신). <b>한국·대중</b>은 과열 감지 — 한국 프리미엄 5%↑·검색 정점이면 단기 고점 경계. 아래 통설 표는 인스타 카드 9공식을 20년 데이터로 검증한 결과.</div>`;
  $('gl_myth').innerHTML=mythTable(D.myth);
  const IND=D.ind||{}; const keys=Object.keys(IND).filter(k=>!k.startsWith('_')&&IND[k].name);
  $('gl_groups').innerHTML=(D.groups||[]).map(g=>{ const ks=keys.filter(k=>IND[k].group===g); if(!ks.length) return '';
    return `<h3 style="color:${GCOL[g]||'#334155'}">${g} <span class="note">${ks.length}개</span></h3><div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:10px">${ks.map(k=>card(k,IND[k])).join('')}</div>`;}).join('');
  keys.forEach(k=>{ const e=IND[k], cv=$('gl_cv_'+k); if(cv&&e.s&&e.s.length>1) spark(cv,e.s,GCOL[e.group]||'#334155',k); });
  document.querySelectorAll('.glhelp').forEach(el=>el.style.display=SHOWHELP?'':'none');
  const chk=$('gl_helpchk'); if(chk) chk.onchange=()=>{ SHOWHELP=chk.checked; try{localStorage.setItem('gl_help',SHOWHELP?'1':'0');}catch(e){} document.querySelectorAll('.glhelp').forEach(el=>el.style.display=SHOWHELP?'':'none'); };
}
let _init=false;
function init(){ if(_init) return; _init=true;
  fetch('/api/db/goldlead',{cache:'no-cache'}).then(r=>{ if(!r.ok) throw new Error('HTTP '+r.status); return r.json(); })
    .then(d=>{ D=d; try{render();}catch(err){ $('gl_overall').innerHTML=`<div style="color:#b91c1c;font-weight:700">렌더 오류: ${E(err&&err.message||err)}</div>`; throw err; } })
    .catch(e=>{ $('gl_overall').innerHTML=`<div class="note">goldlead 로딩 실패: ${E(e.message||e)}</div>`; });
}
const tb=document.querySelector('.tab[data-pane="p_gl"]'); if(tb) tb.addEventListener('click',init);
})();
