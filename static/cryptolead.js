/* cryptolead.js — 🪙 코인 선행지표 탭 (2026-09-05 신설)
   데이터: /api/db/cryptolead (scripts/fetch_cryptolead.py · 매일 06:55 cron · LLM 토큰 0)
   구성: ① 종합 신호등(4축) ② 그룹별 지표 카드(현재값·판정·1년 스파크·왜 선행인가) ③ 정책 이벤트(보고서 세션이 채움)
   설계 의도: "앞으로 오를지 / 오름이 유지될지"를 한 화면에서 — 단기 과열(심리·파생)과 중기 수급(지갑·기관·대기자금),
             사이클 밸류(온체인), 매크로 유동성의 4축을 분리해 서로 다른 시간축의 신호가 뒤섞이지 않게 한다. 리서치용, 투자권유 아님. */
(function(){
'use strict';
let D=null; const charts=[];
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
function spark(cv,s,color,k){
  if(!s||s.length<2) return;
  const labels=s.map(x=>x[0]), data=s.map(x=>x[1]);
  // 판정 임계선(참고선) — 지표별 대표 밴드
  const TH={fng:[25,75],kimp:[0,5],mvrv:[1,3],mvrv_z:[0,6],sopr:[1],nupl:[0,0.75],puell:[0.6,3],mayer:[0.85,2.2],funding:[0,0.05],ls_ratio:[0.9,2],taker:[0.9,1.1],cb_prem:[0],ex_netflow:[0],ibit_flow:[0],cot_am:[0],cot_lev:[0],altbreadth:[25,75],dvol:[40,80]}[k]||[];
  const ds=[{data,borderColor:color,backgroundColor:color+'22',fill:true,pointRadius:0,borderWidth:1.3,tension:0.15}];
  TH.forEach(t=>ds.push({data:data.map(()=>t),borderColor:'#94a3b8',borderDash:[3,3],borderWidth:0.8,pointRadius:0,fill:false}));
  charts.push(new Chart(cv,{type:'line',data:{labels,datasets:ds},
    options:{responsive:true,maintainAspectRatio:false,animation:false,interaction:{mode:'index',intersect:false},
      plugins:{legend:{display:false},tooltip:{filter:i=>i.datasetIndex===0,callbacks:{label:c=>nf(c.raw,4)}}},
      scales:{x:{display:true,ticks:{maxTicksLimit:4,font:{size:9},maxRotation:0,callback:(v,i)=>labels[i]?labels[i].slice(2,7):''},grid:{display:false}},
              y:{ticks:{font:{size:9},maxTicksLimit:4},grid:{color:'#f1f5f9'}}}}}));
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
    ${e.s&&e.s.length>1?`<div class="clsp" style="position:relative;height:90px;flex:0 0 90px;overflow:hidden;margin:4px 0"><canvas id="${cvid}"></canvas></div>`:'<div style="height:12px"></div>'}
    <div style="font-size:11.5px;color:#0f172a;margin-top:2px"><b>판정</b> ${e.judge||'—'}</div>
    <div class="note" style="margin-top:3px;color:#64748b"><b>왜 선행</b> ${e.why||''}</div>
  </div>`;
}
function axisBox(a){
  const col=a.score==null?'#94a3b8':a.score>=0.3?'#16a34a':a.score<=-0.3?'#dc2626':'#ca8a04';
  const pos=a.score==null?50:(a.score+1)/2*100;
  return `<div style="flex:1;min-width:190px;border:1px solid #e2e8f0;border-left:4px solid ${col};border-radius:8px;padding:8px 12px;background:#fff">
    <div style="font-size:12px;color:#475569">${a.name}</div>
    <div style="font-size:17px;font-weight:800;color:${col}">${a.label} <span style="font-size:11px;font-weight:400;color:#64748b">${a.score==null?'':(a.score>0?'+':'')+a.score.toFixed(2)} · 🟢${a.bull} 🔴${a.bear} /${a.n}</span></div>
    <div style="position:relative;height:6px;border-radius:3px;background:linear-gradient(90deg,#fecaca,#fef9c3,#bbf7d0);margin-top:6px"><div style="position:absolute;left:${pos}%;top:-3px;width:3px;height:12px;background:#0f172a;border-radius:2px;transform:translateX(-50%)"></div></div>
  </div>`;
}
function render(){
  if(!D) return;
  charts.forEach(c=>{try{c.destroy();}catch(e){}}); charts.length=0;
  $('cl_asof').textContent='기준 '+(D.as_of||'')+' · 서버 매일 06:55 자동 수집'+(D.errors&&D.errors.length?` · 수집 실패 ${D.errors.length}건`:'');
  const O=D.overall||{}, A=D.axes||{};
  const oc=O.score==null?'#94a3b8':O.score>=0.25?'#16a34a':O.score<=-0.25?'#dc2626':'#ca8a04';
  $('cl_overall').innerHTML=`<div style="display:flex;gap:14px;align-items:center;flex-wrap:wrap">
      <div style="font-size:22px;font-weight:900;color:${oc}">${O.text||'—'}</div>
      <div class="note">종합 ${O.score==null?'—':(O.score>0?'+':'')+O.score.toFixed(2)} (−1 ~ +1 · 4축 평균)</div></div>
    <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:10px">${['short','flow','cycle','macro'].filter(k=>A[k]).map(k=>axisBox(A[k])).join('')}</div>
    <div class="note" style="margin-top:8px">읽는 법: <b>단기</b>축이 🔴면 지금 사기엔 과열(눌림 대기), 🟢면 공포 국면(역발상). <b>수급</b>축은 지갑·기관·대기자금이 실제로 사고 있는지 — 상승이 <u>유지</u>될지를 가르는 축.
      <b>밸류</b>축은 사이클 상 위치(바닥권/고점권). <b>매크로</b>축은 달러 유동성 — BTC 는 유동성에 약 2~3개월 후행. 네 축이 모두 🟢인 시점은 드물고, 보통 "수급🟢 + 단기🔴" 같은 조합으로 나타난다.</div>`;
  // 그룹별 카드
  const IND=D.ind||{}; const keys=Object.keys(IND).filter(k=>!k.startsWith('_')&&IND[k].name);
  $('cl_groups').innerHTML=(D.groups||[]).map(g=>{
    const ks=keys.filter(k=>IND[k].group===g); if(!ks.length) return '';
    return `<h3 style="color:${GCOL[g]||'#334155'}">${g} <span class="note">${ks.length}개</span></h3>
      <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:10px">${ks.map(k=>card(k,IND[k])).join('')}</div>`;}).join('');
  keys.forEach(k=>{const cv=$('cl_cv_'+k); if(cv) spark(cv,IND[k].s,GCOL[IND[k].group]||'#334155',k);});
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
