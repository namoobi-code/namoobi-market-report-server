/* bonds.js — 📜 채권 탭 (2026-10-17 신설)
   데이터: /api/db/bonds (scripts/fetch_bonds.py 매일 07:40 · 기존 DB 재사용 + 채권 ETF 야후)
   구성: ① 금리 고점 통과 4신호 체크리스트(+장단기차·HY·美韓 스프레드) ② 배분 가이드(기사 프레임에 현재 위치)
         ③ 기준금리·10년물 현황 + 1년 추이 ④ 채권 ETF 추세표(KR 8·US 8). 한경MONEY 2026.10 메리츠 윤여삼 인터뷰 기반. 투자권유 아님. */
(function(){
'use strict';
const $=id=>document.getElementById(id);
const E=s=>String(s??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
const nf=(n,d)=>n==null?'—':Number(n).toLocaleString(undefined,{maximumFractionDigits:d==null?2:d});
const pf=(v,d=1)=>v==null?'—':`<span class="${v>0?'up':(v<0?'dn':'')}">${v>0?'+':''}${v.toFixed(d)}%</span>`;
const TD='border:1px solid #e2e8f0;padding:4px 8px;', TH='border:1px solid #e2e8f0;padding:5px 8px;font-size:11.5px;background:#f8fafc;';
let D=null, _init=false; const charts=[];

function spark(cv,s,color,th){
  if(!s||s.length<2||!window.Chart) return;
  const labels=s.map(x=>x[0]), data=s.map(x=>x[1]);
  const ds=[{data,borderColor:color,backgroundColor:color+'22',fill:true,pointRadius:0,borderWidth:1.3,tension:.15}];
  (th||[]).forEach(t=>ds.push({data:data.map(()=>t),borderColor:'#94a3b8',borderDash:[3,3],borderWidth:.8,pointRadius:0,fill:false}));
  charts.push(new Chart(cv,{type:'line',data:{labels,datasets:ds},options:{responsive:true,maintainAspectRatio:false,animation:false,plugins:{legend:{display:false}},
    scales:{x:{ticks:{maxTicksLimit:4,font:{size:9},maxRotation:0,callback:(v,i)=>labels[i]?labels[i].slice(2,7):''},grid:{display:false}},y:{ticks:{font:{size:9},maxTicksLimit:4},grid:{color:'#f1f5f9'}}}}}));
}
function miniSpark(cv,vals,color){
  /* Chart.js 는 responsive:false 미니캔버스에서 그림이 깨졌다(2026-10-17 화면 실측: 점 하나만 보임) → 순수 2D 로 직접 그린다 */
  if(!vals||vals.length<2) return;
  const W=90,H=26,dpr=window.devicePixelRatio||1; cv.width=W*dpr; cv.height=H*dpr; cv.style.width=W+'px'; cv.style.height=H+'px';
  const x=cv.getContext('2d'); x.scale(dpr,dpr); x.clearRect(0,0,W,H);
  const mn=Math.min(...vals), mx=Math.max(...vals), rg=(mx-mn)||1;
  x.beginPath(); vals.forEach((v,i)=>{const px=i/(vals.length-1)*(W-2)+1, py=H-2-(v-mn)/rg*(H-4); i?x.lineTo(px,py):x.moveTo(px,py);});
  x.strokeStyle=color; x.lineWidth=1.3; x.stroke();
}
const TH_LINE={wti:[75],us10:[4.5],jobs:[0],kr10:[]};
function checklist(){
  const C=D.checklist||[], A=D.aux||{}, al=D.alloc||{};
  const n=al.n_ok||0; const col=n>=4?'#16a34a':n>=3?'#65a30d':n>=2?'#ca8a04':'#dc2626';
  let h=`<div style="display:flex;gap:14px;align-items:center;flex-wrap:wrap;margin-bottom:10px">
      <div style="font-size:22px;font-weight:900;color:${col}">${n}/4 충족 — ${E(al.phase||'')}</div>
      <div class="note">메리츠 윤여삼 '금리 고점 통과 신호 4가지'(한경MONEY 2026.10) · 서버 매일 자동 판정 · 기준 ${E(D.as_of||'')}</div></div>
    <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(290px,1fr));gap:10px">`;
  C.forEach(c=>{ h+=`<div class="box" style="padding:10px 12px;border-top:3px solid ${c.ok?'#16a34a':'#dc2626'}">
      <div style="display:flex;justify-content:space-between;align-items:baseline"><b style="font-size:12.5px">${E(c.name)}</b><span style="font-size:11px;padding:1px 7px;border-radius:9px;background:${c.ok?'#dcfce7':'#fee2e2'};color:${c.ok?'#16a34a':'#dc2626'};font-weight:700">${c.ok?'✓ 충족':'✗ 미충족'}</span></div>
      <div style="font-size:19px;font-weight:800;margin:2px 0">${E(c.value)} <span class="note" style="font-weight:400;font-size:11px">${E(c.detail||'')}</span></div>
      <div class="bdc" style="position:relative;height:90px;overflow:hidden;margin:4px 0"><canvas id="bd_cv_${c.key}" style="display:block;width:100%;height:90px"></canvas></div>
      <div class="note" style="font-size:11px"><b>왜</b> ${E(c.why)}</div></div>`;});
  h+=`</div>`;
  const cv=A.curve||{}, hy=A.hy||{};
  h+=`<div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:10px">
    ${cv.cur!=null?`<div style="flex:1;min-width:200px;border:1px solid #e2e8f0;border-radius:8px;padding:8px 12px;background:#fff"><div class="note">보조 · 美 장단기차 10Y−2Y</div><div style="font-size:17px;font-weight:800">${cv.cur.toFixed(2)}%p <span class="note" style="font-weight:400">3M전 ${cv.m3==null?'—':cv.m3.toFixed(2)}</span></div><div class="note" style="font-size:11px">축소(플래트닝)=경기 모멘텀 정점·긴축 체감 신호, 역전이면 경고(기사). 가팔라지는 것도 두 종류 — 2Y가 내려서면 고점 통과 후 전형(불), 10Y가 올라서면 수급 불안(베어·장기채 위험). 판정은 ⓪ 패널 '커브 성격'</div></div>`:''}
    ${hy.cur!=null?`<div style="flex:1;min-width:200px;border:1px solid #e2e8f0;border-radius:8px;padding:8px 12px;background:#fff"><div class="note">보조 · 美 HY 가산금리</div><div style="font-size:17px;font-weight:800">${hy.cur.toFixed(2)}%p <span class="note" style="font-weight:400">3M전 ${hy.m3==null?'—':hy.m3.toFixed(2)}</span></div><div class="note" style="font-size:11px">회사채 신용스프레드의 미국판 — 벌어지면 상환능력 불신, 좁아지면 신뢰. 회사채는 등급 아닌 스프레드로 보라(기사)</div></div>`:''}
    ${A.us_kr!=null?`<div style="flex:1;min-width:200px;border:1px solid #e2e8f0;border-radius:8px;padding:8px 12px;background:#fff"><div class="note">보조 · 美−韓 10년 스프레드</div><div style="font-size:17px;font-weight:800">${A.us_kr.toFixed(0)}bp</div><div class="note" style="font-size:11px">국내 10년은 美 10년을 따라간다 — 스프레드가 넓을수록 국내 금리의 추가 상승 압력은 제한적</div></div>`:''}
  </div>`;
  return h;
}
function alloc(){
  const al=D.alloc||{}; const n=al.n_ok||0;
  const pie=(o,title,on)=>{const cols={'현금성':'#94a3b8','단기채':'#0ea5e9','장기채':'#7c3aed','우량 회사채':'#f59e0b'};
    return `<div style="flex:1;min-width:220px;border:2px solid ${on?'#7c3aed':'#e2e8f0'};border-radius:8px;padding:10px 12px;background:#fff${on?';box-shadow:0 0 0 3px #ede9fe':''}"><div style="font-weight:700;font-size:12.5px">${title}${on?' <span style="font-size:10.5px;color:#7c3aed">◀ 현재 위치</span>':''}</div>
      <div style="display:flex;height:16px;border-radius:8px;overflow:hidden;margin:6px 0">${Object.entries(o).map(([k,v])=>`<div title="${k} ${v}%" style="width:${v}%;background:${cols[k]}"></div>`).join('')}</div>
      <div style="font-size:11.5px">${Object.entries(o).map(([k,v])=>`<span style="color:${cols[k]};font-weight:700">■</span> ${k} ${v}%`).join(' · ')}</div></div>`;};
  return `<div style="display:flex;gap:10px;flex-wrap:wrap">${pie(al.base||{},'고점 확신 전 — 단기채로 대기',n<3)}<div style="align-self:center;font-size:22px;color:#94a3b8">→</div>${pie(al.after||{},'최종금리 확신 후 — 장기채 50%',n>=3)}</div>
    <div class="note" style="margin-top:6px;line-height:1.6">${E(al.note||'')} — 체크리스트 3개 이상 충족이면 오른쪽으로 <b>단계적</b> 이동(한 번에 몰지 말 것). 위험·안전자산 큰 틀(60/40)은 별개이며 이 배분은 채권 몫 안의 구성. 참고용·투자권유 아님.</div>`;
}
function rates(){
  const P=D.policy||[], C=D.countries||[];
  let h=`<div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:8px">${P.map(r=>`<div style="border:1px solid #e2e8f0;border-radius:8px;padding:6px 10px;background:#fff;min-width:110px"><div class="note" style="font-size:10.5px">${E(r.country)} 기준금리</div><div style="font-size:15px;font-weight:800">${E(r.rate)}</div><div class="note" style="font-size:10px">${E(r.asof||'')}</div></div>`).join('')}</div>`;
  h+=`<table style="border-collapse:collapse;font-size:12px;background:#fff"><thead><tr>${['국가 10년물','현재','1일','1주','1개월','3개월','6개월','1년','기준일'].map(x=>`<th style="${TH}">${x}</th>`).join('')}</tr></thead><tbody>${
    C.map(c=>{const bp=v=>v==null?'—':`<span class="${v>0?'up':(v<0?'dn':'')}">${v>0?'+':''}${v.toFixed(0)}bp</span>`;
      return `<tr><td style="${TD}"><b>${E(c.name)}</b></td><td style="${TD}text-align:right;font-weight:700">${c.cur==null?'—':c.cur.toFixed(2)+'%'}</td>${['d1','w1','m1','m3','m6','y1'].map(k=>`<td style="${TD}text-align:right">${bp(c[k])}</td>`).join('')}<td style="${TD}color:#64748b;font-size:11px">${E(c.date||'')}</td></tr>`;}).join('')}</tbody></table>
    <div class="note" style="margin-top:3px">변화는 bp(0.01%p). 소스 FRED·Bundesbank·CNBC·ECOS</div>`;
  return h;
}
function ratesChart(){
  const S=D.series||{}; const cv=$('bd_cv_rates'); if(!cv||!window.Chart) return;
  const cols={US:'#2563eb',KR:'#dc2626',DE:'#64748b',JP:'#16a34a'}, nm={US:'미국',KR:'한국',DE:'독일',JP:'일본'};
  const dates=[...new Set(Object.values(S).flat().map(x=>x[0]))].sort();
  charts.push(new Chart(cv,{type:'line',data:{labels:dates,datasets:Object.entries(S).map(([k,s])=>{const m=new Map(s);return {label:nm[k]||k,data:dates.map(d=>m.get(d)??null),borderColor:cols[k],pointRadius:0,borderWidth:1.4,spanGaps:true,tension:.1};})},
    options:{responsive:true,maintainAspectRatio:false,animation:false,interaction:{mode:'index',intersect:false},plugins:{legend:{labels:{font:{size:10.5}}}},
      scales:{x:{ticks:{maxTicksLimit:8,font:{size:9.5},maxRotation:0,callback:(v,i)=>dates[i]?dates[i].slice(2,7):''}},y:{ticks:{callback:v=>v+'%',font:{size:10}}}}}}));
}
function etfTbl(mk){
  const R=(D.etfs||[]).filter(r=>r.mk===mk);
  const lampOf=r=>r.lamp==='유리'?['🟢','#16a34a']:r.lamp==='보통'?['🟡','#ca8a04']:r.lamp==='불리'?['🔴','#dc2626']:['⚪','#94a3b8'];
  return `<table style="border-collapse:collapse;font-size:12px;background:#fff;width:100%"><thead><tr>${['지금 유리?','ETF','구분','현재가','1주','1개월','3개월','6개월','1년(가격)','분배율<br><span class="note" style="font-weight:400">최근 1년 실지급</span>','총수익 1년≈<br><span class="note" style="font-weight:400">KR=다음 수정주가 · US=가격+분배</span>','200일선比','RSI','1년 추세'].map(x=>`<th style="${TH}">${x}</th>`).join('')}</tr></thead><tbody>${
    R.map(r=>{const [ic,col]=lampOf(r); return `<tr><td style="${TD}white-space:nowrap" title="${E(r.why||'')}"><b style="color:${col}">${ic} ${E(r.lamp||'—')}</b> <span class="note" style="font-size:10px">${r.score??''}</span><div class="note" style="font-size:10px;max-width:220px;white-space:normal;line-height:1.3">${E((r.why||'').split(' · ').slice(0,2).join(' · '))}</div></td><td style="${TD}"><b>${E(r.name)}</b><span class="note" style="font-size:10px"> ${E(r.sym)}</span></td><td style="${TD}font-size:11px;color:#475569">${E(r.grp)}</td><td style="${TD}text-align:right">${r.cur==null?'—':(mk==='kr'?nf(r.cur,0):'$'+nf(r.cur,2))}</td>${['w1','m1','m3','m6','y1'].map(k=>`<td style="${TD}text-align:right">${pf(r[k])}</td>`).join('')}<td style="${TD}text-align:right;color:#0f766e;font-weight:700">${r.dy==null?'—':r.dy.toFixed(2)+'%'}<span class="note" style="font-weight:400;font-size:10px"> ${r.dyn?r.dyn+'회':(r.dy===0?'누적형':'')}</span></td><td style="${TD}text-align:right;font-weight:700">${r.tr1y==null?'—':pf(r.tr1y)}</td><td style="${TD}text-align:right">${pf(r.vs200)}</td><td style="${TD}text-align:right">${r.rsi==null?'—':r.rsi.toFixed(0)}</td><td style="${TD}width:100px"><div class="bdsp" style="width:90px;height:26px;overflow:hidden"><canvas id="bd_sp_${r.sym.replace('.','_')}" width="90" height="26" style="display:block;width:90px;height:26px"></canvas></div></td></tr>`;}).join('')}</tbody></table>
    <div class="note" style="margin-top:4px;line-height:1.6">지금 유리?=만기별 규칙(0~4점): <b>파킹·단기</b>는 고점 미확인일수록 유리(대기자금) · <b>장기·초장기</b>는 체크리스트 3/4↑(고점 통과) + 눌림(200일선 아래·RSI 40↓)일 때 유리, 고점 확신 전엔 '보통'까지만(기사: 소량) · <b>회사채·HY·종합</b>은 HY 가산금리 확대 중이면 불리 · <b>물가연동</b>은 유가 $75↑·인플레 재점화 시 유리. 마우스 올리면 근거 전부.</div>`;
}
function parkingSec(){
  const S=D.short||{}, P=D.parking||[];
  const card=(k,extra)=>{const v=S[k]; if(!v) return ''; const d=v.cur-(v.m3??v.cur);
    return `<div style="flex:1;min-width:170px;border:1px solid #e2e8f0;border-radius:8px;padding:8px 12px;background:#fff"><div class="note">${E(v.name)} <span style="font-size:10px">${E(v.d)}</span></div><div style="font-size:18px;font-weight:800">${v.cur.toFixed(2)}% <span class="note" style="font-weight:400;font-size:11px">3M ${d>0?'+':''}${d.toFixed(2)}%p</span></div><div class="note" style="font-size:10.5px">하루 ${v.daily.toFixed(4)}% · 100만원당 ${Math.round(1e6*v.daily/100)}원/일 ${extra||''}</div></div>`;};
  let h=`<div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:8px">${card('cd91','← CD금리형 기준')}${card('kofr','← KOFR형 기준')}${card('call')}${card('sofr','← 달러MMF 기준(환노출)')}</div>
    <div class="note" style="margin-bottom:8px;line-height:1.6">기사(삼성증권 임은혜): 파킹형은 듀레이션 ≈ 0 이라 금리 변동에 가격이 안 흔들리고, 이자가 <b>일할 계산으로 매일 기준가에 누적(복리)</b>된다 — 위 '하루 이자'가 그 숫자. CD금리형은 시중은행 신용위험 일부, KOFR형은 국채담보 RP 라 사실상 무위험, 머니마켓형은 단기채·CP 액티브로 알파 추구, <b>달러 SOFR형은 원·달러 환율에 그대로 노출</b>(1년 수익률이 음수인 이유 = 환율). 결제 T+1~2, 2025 소득세법 개정으로 연 1회↑ 분배 의무(월분배형 多).</div>`;
  const TYPES=['CD금리형','KOFR형','머니마켓·초단기','SOFR·달러MMF'];
  h+=`<table style="border-collapse:collapse;font-size:11.5px;background:#fff;width:100%"><thead><tr>${['유형','ETF','기초지표','신용위험','환노출','AUM','보수','1개월','3개월','6개월','1년(총수익)'].map(x=>`<th style="${TH}">${x}</th>`).join('')}</tr></thead><tbody>${
    TYPES.map(t=>P.filter(r=>r.type===t).map((r,i)=>`<tr style="${t==='SOFR·달러MMF'?'background:#fffbeb':''}"><td style="${TD}white-space:nowrap">${i===0?'<b>'+E(t)+'</b>':''}</td><td style="${TD}white-space:nowrap"><b>${E(r.name)}</b><span class="note" style="font-size:10px"> ${E(r.c)}</span></td><td style="${TD}font-size:11px">${E(r.base)}</td><td style="${TD}font-size:11px;color:#475569">${E(r.credit)}</td><td style="${TD}text-align:center">${r.fx?'<b style="color:#b45309">원·달러</b>':'없음'}</td><td style="${TD}text-align:right">${r.cap?(r.cap/1e12).toFixed(1)+'조':'—'}</td><td style="${TD}text-align:right">${r.fee==null?'—':r.fee+'%'}</td>${['m1','m3','m6','y1'].map(k=>`<td style="${TD}text-align:right">${pf(r[k],2)}</td>`).join('')}</tr>`).join('')).join('')}</tbody></table>
    <div class="note" style="margin-top:4px">수익률=다음금융 수정주가(분배 포함 총수익). 기사 표(체크 9/14)의 운용규모 상위 16종 — AUM·보수는 ETF 풀 당일값. 머니마켓형 1년 3.1~3.3% > CD형 2.8~3.0% > KOFR형 2.6~2.7%: 신용위험을 조금 더 지는 순서대로 수익이 높다(기사 논리 그대로).</div>`;
  return h;
}
function regimeSec(){
  /* (2026-10-17) 매경ECONOMY '5% 금리 시대' — 긴축 성격(실질 vs 기대인플레)·명목성장률−10Y·인상 사이클 종료 */
  const R=D.regime||{}; if(!R.decomp&&!R.cycle) return '<div class="note">regime 데이터 없음</div>';
  const dc=R.decomp||{}, cur=dc.cur||{}, m3=dc.m3||{}, m6=dc.m6||{}; const G=R.growth_gap||{}, C=R.cycle||{}, ref=R.ref||{};
  const kcol=k=>k==='성장형'?'#16a34a':k==='인플레형'?'#dc2626':k==='혼합'?'#ca8a04':'#64748b';
  const bar=(o)=>{ if(o.us10==null||o.kind==null||o.us10<=0.15&&o.us10>=-0.15) return ''; const tot=Math.abs(o.real)+Math.abs(o.bei)||1; const rw=Math.abs(o.real)/tot*100;
    return `<div style="display:flex;height:14px;border-radius:7px;overflow:hidden;margin:4px 0;max-width:360px"><div title="실질금리 ${o.real>0?'+':''}${o.real}%p" style="width:${rw}%;background:#16a34a"></div><div title="기대인플레 ${o.bei>0?'+':''}${o.bei}%p" style="width:${100-rw}%;background:#dc2626"></div></div>
      <div class="note" style="font-size:10.5px"><span style="color:#16a34a;font-weight:700">■</span> 실질금리 ${o.real>0?'+':''}${o.real}%p · <span style="color:#dc2626;font-weight:700">■</span> 기대인플레 ${o.bei>0?'+':''}${o.bei}%p = 10Y ${o.us10>0?'+':''}${o.us10}%p</div>`;};
  const win=(o,t)=>`<div style="flex:1;min-width:240px;border:1px solid #e2e8f0;border-radius:8px;padding:8px 12px;background:#fff;border-top:3px solid ${kcol(o.kind)}"><div class="note">${t}</div><div style="font-size:15px;font-weight:800;color:${kcol(o.kind)}">${E(o.kind||'—')}</div><div style="font-size:11.5px;line-height:1.4">${E(o.label||'')}</div>${bar(o)}</div>`;
  let h=`<div style="display:flex;gap:10px;flex-wrap:wrap;align-items:stretch">
    <div style="flex:1.2;min-width:280px"><div style="font-weight:700;font-size:12.5px;margin-bottom:4px">① 지금 긴축은 <u>성장형</u>인가 <u>인플레형</u>인가 <span class="note" style="font-weight:400">美10Y 변화 = 실질금리(TIPS) + 기대인플레(BEI)</span></div>
      <div class="note" style="margin-bottom:6px">현재 10Y <b>${cur.us10==null?'—':cur.us10.toFixed(2)}%</b> = 실질 ${cur.real==null?'—':cur.real.toFixed(2)} + 기대인플레 ${cur.bei==null?'—':cur.bei.toFixed(2)} (${E(cur.d||'')})</div>
      <div style="display:flex;gap:8px;flex-wrap:wrap">${win(m3,'최근 3개월')}${win(m6,'최근 6개월')}</div>
      ${(()=>{const ck=R.curve_kind, tp=R.tp; if(!ck&&!tp) return ''; return `<div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:8px">
        ${ck?`<div style="flex:1;min-width:240px;border:1px solid #e2e8f0;border-radius:8px;padding:8px 12px;background:#fff;border-top:3px solid ${ck.risk?'#dc2626':ck.kind.startsWith('불')?'#16a34a':'#ca8a04'}"><div class="note">커브 성격 — 3M 10Y ${ck.d10>0?'+':''}${ck.d10} · 2Y ${ck.d2>0?'+':''}${ck.d2} (10Y−2Y ${ck.curve_m3}→${ck.curve}%p)</div><div style="font-size:15px;font-weight:800;color:${ck.risk?'#dc2626':ck.kind.startsWith('불')?'#16a34a':'#ca8a04'}">${E(ck.kind)}</div><div style="font-size:11.5px;line-height:1.4">${E(ck.label)}</div></div>`:''}
        ${tp?`<div style="flex:1;min-width:240px;border:1px solid #e2e8f0;border-radius:8px;padding:8px 12px;background:#fff;border-top:3px solid ${tp.rising?'#dc2626':'#16a34a'}"><div class="note">美 10Y 기간프리미엄(NY Fed ACM) <span style="font-size:10px">${E(tp.d)}</span></div><div style="font-size:15px;font-weight:800;color:${tp.rising?'#dc2626':'#16a34a'}">${tp.cur.toFixed(2)}%p <span class="note" style="font-weight:400;font-size:11px">3M ${tp.m3==null?'—':(tp.m3>0?'+':'')+tp.m3} · 1Y ${tp.y1==null?'—':(tp.y1>0?'+':'')+tp.y1}</span></div><div style="font-size:11.5px;line-height:1.4">${tp.rising?'프리미엄 확대 중 — 기준금리 경로와 무관한 수급(재정적자·QT·AI 회사채) 요인이 장기금리를 밀어올림. 기준금리 하락이 장기금리 하락으로 안 이어지는 이유(기사)':'프리미엄 안정 — 장기금리는 정책 경로를 따라 움직이는 중'}</div></div>`:''}</div>`;})()}
      <div class="note" style="font-size:11px;margin-top:6px;line-height:1.5"><b>왜</b> 메리츠 이진우: "금리의 절대 수준보다 끌어올리는 요인이 성장인지 비용 상승인지 구분" — ${E(ref.types||'')}. 실질 주도면 증시는 적응하고, 기대인플레 주도면 주식·채권이 동시에 무너진다(할인율 충격).</div>
      <div class="bdm" style="position:relative;height:150px;overflow:hidden;margin-top:6px"><canvas id="bd_cv_regime" style="display:block;width:100%;height:150px"></canvas></div></div>
    <div style="flex:1;min-width:260px"><div style="font-weight:700;font-size:12.5px;margin-bottom:4px">② 경제가 금리를 감당하나 <span class="note" style="font-weight:400">명목성장률 − 10년물</span></div>
      <div style="display:flex;gap:8px;flex-wrap:wrap">${['US','KR'].map(k=>{const g=G[k]; if(!g) return ''; const ok=g.gap!=null&&g.gap>0; return `<div style="flex:1;min-width:120px;border:1px solid #e2e8f0;border-radius:8px;padding:8px 12px;background:#fff;border-top:3px solid ${ok?'#16a34a':'#dc2626'}"><div class="note">${k==='US'?'미국':'한국'} <span style="font-size:10px">${E(g.q)}</span></div><div style="font-size:20px;font-weight:800;color:${ok?'#16a34a':'#dc2626'}">${g.gap>0?'+':''}${nf(g.gap,1)}%p</div><div class="note" style="font-size:10.5px">명목GDP YoY ${nf(g.gdp_yoy,1)}% − 10Y ${nf(g.y10,2)}%</div><div style="font-size:11px;font-weight:700;color:${ok?'#16a34a':'#dc2626'}">${ok?'감당 — 주식 우호 구간':'금리 > 성장 — 이자가 성장을 잠식'}</div></div>`;}).join('')}</div>
      <div class="note" style="font-size:11px;margin-top:6px;line-height:1.5"><b>왜</b> 메리츠 1962년 이후 실측: 명목성장률이 美10Y보다 높았던 시기엔 S&P500 수익률이 장기평균을 웃돌았다(예외 1977·78·2005·2022). 기사의 "5% 고금리 지속 여부는 경제가 이자비용을 감당할 만큼 성장하느냐에 달렸다"를 숫자 하나로. 명목GDP 는 분기(한국은 반도체 호황으로 명목 급증 — 물가 아닌 수출 효과).</div>
      ${ref.hike_eras?`<div class="note" style="font-size:10.5px;margin-top:4px">${E(ref.hike_eras)}</div>`:''}</div></div>`;
  // ③ 인상 사이클
  const U=C.US||{}, K=C.KR||{}, V=C.verdict, cs=C.consensus||{}; const fut=U.futures||[];
  h+=`<div style="margin-top:12px;border-top:1px dashed #e2e8f0;padding-top:10px"><div style="font-weight:700;font-size:12.5px;margin-bottom:4px">③ 인상 사이클은 끝났나 <span class="note" style="font-weight:400">마지막 인상 경과 · FF선물 반영 · 점도표 · 전문가 8인</span>
      ${V?`<span style="margin-left:8px;font-size:11.5px;padding:2px 9px;border-radius:9px;background:${V.ok?'#dcfce7':'#fee2e2'};color:${V.ok?'#16a34a':'#dc2626'};font-weight:700">${E(V.st)}</span>`:''}</div>
    ${V?`<div style="font-size:12px;margin-bottom:6px">${E(V.txt)}</div>`:''}
    <div style="display:flex;gap:8px;flex-wrap:wrap">
      <div style="flex:1;min-width:230px;border:1px solid #e2e8f0;border-radius:8px;padding:8px 12px;background:#fff"><div class="note">🇺🇸 연준 — 상단 ${U.upper==null?'—':U.upper.toFixed(2)}% · 실효 ${U.dff==null?'—':U.dff.toFixed(2)}%</div>
        <div style="font-size:12px;margin-top:3px">마지막 인상 <b>${E(U.last_hike||'—')}</b>${U.days!=null?` <span class="note">(${U.days}일 전)</span>`:''} · 마지막 인하 ${E(U.last_cut||'—')}</div>
        <div style="font-size:12px;margin-top:3px">FF선물 반영: ${fut.length?fut.map(f=>`${E(f.m)}월 <b>${f.implied.toFixed(2)}%</b> (${f.vs_dff>0?'+':''}${f.vs_dff}bp)`).join(' · '):'—'}</div>
        <div style="font-size:11.5px;margin-top:3px" class="note">점도표(9월 SEP): 2026말 ${U.sep?.['2026E']}% (6월 ${U.sep?.prev_2026E}) · 2027말 ${U.sep?.['2027E']}% (6월 ${U.sep?.prev_2027E}) — 연준 스스로 '더 높게 더 오래'로 수정</div></div>
      <div style="flex:1;min-width:230px;border:1px solid #e2e8f0;border-radius:8px;padding:8px 12px;background:#fff"><div class="note">🇰🇷 한국은행 — 기준금리 ${K.rate==null?'—':K.rate.toFixed(2)}%</div>
        <div style="font-size:12px;margin-top:3px">마지막 인상 <b>${E(K.last_hike||'—')}</b>${K.days!=null?` <span class="note">(약 ${K.days}일 전)</span>`:''} · 마지막 인하 ${E(K.last_cut||'—')}</div>
        ${K.y3!=null?`<div style="font-size:12px;margin-top:3px">국고3년 <b>${K.y3.toFixed(2)}%</b> − 기준금리 = <b style="color:${K.y3_gap>=25?'#16a34a':'#dc2626'}">${K.y3_gap>0?'+':''}${K.y3_gap}bp</b> <span class="note" style="font-size:11px">${E(K.y3_txt||'')}</span></div>`:''}
        <div style="font-size:11.5px;margin-top:3px" class="note">전문가 8인(${E(cs.src||'')}): 연말 美 ${E(cs.us_2026||'')} · 韓 ${E(cs.kr_2026||'')} / 2027.6 美 ${E(cs.us_2027_6||'')} · 韓 ${E(cs.kr_2027_6||'')} / 첫 인하 ${E(cs.first_cut||'')}</div></div>
    </div>
    <div class="note" style="font-size:11px;margin-top:6px;line-height:1.5"><b>왜</b> ${E(ref.after_hike||'')} — 채권은 "마지막 인상"이 확인된 뒤에 산 쪽이 압도적으로 유리했다. 선물이 추가 인상을 반영하는 동안은 위 체크리스트와 무관하게 장기채 '소량'. 판정 규칙: 다음 12월물 반영 ≥ +20bp 진행 중 · 8~20bp 막바지 · <8bp 종료 신호. ${E(ref.alt||'')}</div></div>`;
  return h;
}
function regimeChart(){
  const S=((D.regime||{}).decomp||{}).s||{}; const cv=$('bd_cv_regime'); if(!cv||!window.Chart||!S.us10) return;
  const cols={us10:'#1e293b',real:'#16a34a',bei:'#dc2626'}, nm={us10:'美10Y',real:'실질(TIPS)',bei:'기대인플레(BEI)'};
  const dates=[...new Set(Object.values(S).flat().map(x=>x[0]))].sort();
  charts.push(new Chart(cv,{type:'line',data:{labels:dates,datasets:Object.entries(S).map(([k,s])=>{const m=new Map(s);return {label:nm[k],data:dates.map(d=>m.get(d)??null),borderColor:cols[k],pointRadius:0,borderWidth:k==='us10'?1.6:1.2,spanGaps:true,tension:.1};})},
    options:{responsive:true,maintainAspectRatio:false,animation:false,interaction:{mode:'index',intersect:false},plugins:{legend:{labels:{font:{size:10},boxWidth:10}}},
      scales:{x:{ticks:{maxTicksLimit:6,font:{size:9},maxRotation:0,callback:(v,i)=>dates[i]?dates[i].slice(2,7):''}},y:{ticks:{callback:v=>v+'%',font:{size:9.5},maxTicksLimit:5}}}}}));
}
function render(){
  charts.forEach(c=>{try{c.destroy();}catch(e){}}); charts.length=0;
  $('bd_asof').textContent='기준 '+(D.as_of||'')+' · 서버 매일 07:40 자동';
  if($('bd_regime')){ $('bd_regime').innerHTML=regimeSec(); regimeChart(); }
  $('bd_chk').innerHTML=checklist();
  (D.checklist||[]).forEach(c=>{const cv=$('bd_cv_'+c.key); if(cv) spark(cv,c.s,c.ok?'#16a34a':'#dc2626',TH_LINE[c.key]);});
  $('bd_alloc').innerHTML=alloc();
  $('bd_rates').innerHTML=rates(); ratesChart();
  if($('bd_park')) $('bd_park').innerHTML=parkingSec();
  $('bd_etf_kr').innerHTML=etfTbl('kr'); $('bd_etf_us').innerHTML=etfTbl('us');
  (D.etfs||[]).forEach(r=>{const cv=$('bd_sp_'+r.sym.replace('.','_')); if(cv&&r.spark) miniSpark(cv,r.spark,(r.y1||0)>=0?'#dc2626':'#2563eb');});
}
function init(){ if(_init) return; _init=true;
  fetch('/api/db/bonds',{cache:'no-cache'}).then(r=>{if(!r.ok) throw new Error('HTTP '+r.status); return r.json();})
    .then(d=>{D=d; try{render();}catch(err){$('bd_chk').innerHTML=`<div style="color:#b91c1c;font-weight:700">렌더 오류: ${E(err&&err.message||err)}</div>`; throw err;}})
    .catch(e=>{$('bd_chk').innerHTML=`<div class="note">bonds 로딩 실패: ${E(e.message||e)}</div>`;});
}
const tb=document.querySelector('.tab[data-pane="p_bd"]'); if(tb) tb.addEventListener('click',init);
})();
