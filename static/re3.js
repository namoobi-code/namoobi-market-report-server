/* re3.js — RE3 시장 국면 신호등 (2026-08-27 신설)
   데이터: /api/db/re3 (scripts/re3.py · 매일 08:05 cron · 신규 수집 없음)
   구성: 지역 칩 → 종합 신호등 + 신호 6개 표 + 국면 히스토리 차트 + 백테스트 표 */
(function(){
'use strict';
let D=null, REG='서울', chart=null;
const $=id=>document.getElementById(id);
const VC={up:['#dc2626','🔴','상승 국면'],mid:['#a16207','🟡','중립'],down:['#2563eb','🔵','하락 국면']};
const SIG={1:['▲','#dc2626','상승신호'],0:['─','#94a3b8','중립'],'-1':['▼','#2563eb','하락신호']};
const THR={trade:'±10%',jsr:'±0.5%p',unsold:'∓10%',rate:'∓0.3%p',bid:'±2%p',delq:'∓0.10%p'};
const fmt=m=>m?m.slice(0,4)+'.'+m.slice(4):'';

function render(){
  if(!D) return;
  const cur=D.cur[REG], bt=D.bt[REG], h=D.hist[REG];
  // 지역 칩
  $('re3_reg').innerHTML=D.regions.map(r=>
    `<button class="chip${r===REG?' on':''}" data-r="${r}" style="margin:0 4px 4px 0;padding:3px 10px;border-radius:14px;border:1px solid ${r===REG?'#9a3412':'#d6d9de'};background:${r===REG?'#9a3412':'#fff'};color:${r===REG?'#fff':'#333'};cursor:pointer;font-size:12px">${r}</button>`).join('');
  $('re3_reg').querySelectorAll('button').forEach(b=>b.onclick=()=>{REG=b.dataset.r;render();renderCalc();});

  // 종합 신호등
  const v=cur&&cur.verdict, vc=v?VC[v]:['#94a3b8','⚪','판정 보류'];
  $('re3_verdict').innerHTML=cur?`
    <div style="display:flex;align-items:center;gap:14px;padding:10px 16px;border:2px solid ${vc[0]};border-radius:10px;background:#fff">
      <div style="font-size:34px">${vc[1]}</div>
      <div><div style="font-size:19px;font-weight:800;color:${vc[0]}">${REG} — ${vc[2]}</div>
        <div class="note">종합 점수 <b>${cur.score===null?'—':cur.score.toFixed(2)}</b> (−1 하락 ~ +1 상승 · 3M 평활) · 기준월 <b>${fmt(cur.month)}</b>
        <span style="opacity:.75">— 지표 발표 시차로 최신월과 1~2개월 차이가 날 수 있음</span></div></div>
    </div>`:'<div class="note">데이터 없음</div>';

  // 신호 표
  $('re3_sig').innerHTML=`<table style="border-collapse:collapse;font-size:12.5px;background:#fff">
    <tr style="background:#f6f7f9">${['신호','현재값','임계값','판정','적용 범위'].map(x=>`<th style="border:1px solid #e2e5ea;padding:4px 10px">${x}</th>`).join('')}</tr>
    ${cur.items.map(it=>{const s=it.sig===null?null:SIG[it.sig];return `<tr>
      <td style="border:1px solid #e2e5ea;padding:4px 10px">${D.labels[it.k]}</td>
      <td style="border:1px solid #e2e5ea;padding:4px 10px;text-align:right">${it.val===null?'—':it.val+it.unit}</td>
      <td style="border:1px solid #e2e5ea;padding:4px 10px;text-align:center;color:#667">${THR[it.k]}</td>
      <td style="border:1px solid #e2e5ea;padding:4px 10px;text-align:center;${s?`color:${s[1]};font-weight:700`:''}">${s?s[0]+' '+s[2]:'집계중'}</td>
      <td style="border:1px solid #e2e5ea;padding:4px 10px;color:#667">${D.scope[it.k]}</td></tr>`;}).join('')}
  </table>
  <p class="note" style="margin:4px 0 0">▲=상승신호 ▼=하락신호. 종합 = 가용 신호 평균(4개 미만이면 보류). "집계중"은 해당 지표의 기준월 데이터 미발표.</p>`;

  // 히스토리 차트 — 중위가(좌) + 국면점수(우)
  if(window.Chart){
    const t=D.t, sc=h.score_s, med=h.med;
    let i0=0; for(let i=0;i<t.length;i++){ if((sc&&sc[i]!=null)||(med&&med[i]!=null)){i0=i;break;} }
    const L=t.slice(i0).map(fmt);
    if(chart) chart.destroy();
    chart=new Chart($('re3_cv'),{type:'line',data:{labels:L,datasets:[
      {label:'실거래 중위가',data:med?med.slice(i0):[],yAxisID:'y',borderColor:'#0f766e',backgroundColor:'transparent',pointRadius:0,borderWidth:1.6,spanGaps:true},
      {label:'국면 점수(3M 평활)',data:sc?sc.slice(i0):[],yAxisID:'y2',borderColor:'#9a3412',backgroundColor:'rgba(154,52,18,.12)',pointRadius:0,borderWidth:1.2,fill:true,spanGaps:true}
    ]},options:{responsive:true,maintainAspectRatio:false,interaction:{mode:'index',intersect:false},
      plugins:{legend:{labels:{boxWidth:18,font:{size:11}}}},
      scales:{x:{ticks:{maxTicksLimit:14,font:{size:10}}},
        y:{position:'left',title:{display:true,text:'중위가(만원)',font:{size:10}},ticks:{font:{size:10}}},
        y2:{position:'right',min:-1,max:1,grid:{drawOnChartArea:false},title:{display:true,text:'국면 점수',font:{size:10}},ticks:{font:{size:10}}}}}});
  }

  // 백테스트 표
  const rows=[['h6','6개월'],['h12','12개월'],['h24','24개월']];
  $('re3_bt').innerHTML=bt&&bt.h6?`<table style="border-collapse:collapse;font-size:12.5px;background:#fff">
    <tr style="background:#f6f7f9"><th style="border:1px solid #e2e5ea;padding:4px 10px">이후 지평</th>
      ${['🔴 상승판정','🟡 중립','🔵 하락판정'].map(x=>`<th style="border:1px solid #e2e5ea;padding:4px 10px">${x}</th>`).join('')}</tr>
    ${rows.map(([k,lb])=>{const b=bt[k];if(!b)return '';const c=x=>x&&x.n?`평균 <b>${x.avg>0?'+':''}${x.avg}%</b> · 승률 ${x.win}% <span style="opacity:.6">(n=${x.n})</span>`:'—';
      return `<tr><td style="border:1px solid #e2e5ea;padding:4px 10px">${lb} 뒤 중위가</td>
        <td style="border:1px solid #e2e5ea;padding:4px 10px">${c(b.up)}</td>
        <td style="border:1px solid #e2e5ea;padding:4px 10px">${c(b.mid)}</td>
        <td style="border:1px solid #e2e5ea;padding:4px 10px">${c(b.down)}</td></tr>`;}).join('')}
  </table>
  <p class="note" style="margin:4px 0 0;line-height:1.7">읽는 법(2026-08-27 실측·서울): <b>6개월</b> 지평에선 상승판정 +5.9% > 중립 +2.9% > 하락판정 +0.3%로 국면 순서대로 갈린다 —
  단기 방향 참고용. 반면 <b>24개월</b> 지평에선 하락판정 뒤가 오히려 가장 높았다(+21.9%) — 하락 국면 신호는 장기 투자자에겐 역발상 <b>바닥 신호</b>였다는 뜻.
  같은 규칙을 과거 전체에 소급 적용한 결과이며, 미래를 보장하지 않는다.</p>`:'<div class="note">백테스트 표본 없음</div>';

  $('re3_asof').textContent='('+D.asof+' 갱신 · 매일 08:05)';
}

/* ── ② 매매 vs 전세·월세 판단기 (2026-08-27) ─────────────────────────
   연간 총비용(만원):
     매매 = 자기자본×기회수익률 + 대출×주담대금리 + 매매가×보유세율 + 취득세/보유년수 − 매매가×기대상승률
     전세 = 전세보증금×기회수익률 (+ 전세대출×전세금리 − 대출분 기회비용 차감)
     월세 = 보증금×기회수익률 + 월세×12
   손익분기 상승률 g* = 매매 비용이 전세와 같아지는 상승률                         */
let jsrChart=null;
const CK='re3_calc_v1';
const FLD=[ // [key,라벨,기본값,단위,step]
  ['P','매매가',87000,'만원',1000],['L','주담대 대출금',30000,'만원',1000],
  ['rm','주담대 금리',null,'%',0.1],['J','전세보증금',52000,'만원',1000],
  ['jl','전세대출금',0,'만원',1000],['rj','전세대출 금리',null,'%',0.1],
  ['D','월세보증금',5000,'만원',500],['M','월세',150,'만원/월',5],
  ['ro','기회비용 수익률',3.0,'%',0.1],['g','기대 상승률(연)',null,'%',0.5],
  ['ht','보유세(연)',0.35,'%',0.05],['at','취득세율',3.3,'%',0.1],['yy','보유 예정',5,'년',1]];

function calcLoad(){ try{return JSON.parse(localStorage.getItem(CK))||{};}catch(e){return {};} }
function calcSave(v){ try{localStorage.setItem(CK,JSON.stringify(v));}catch(e){} }
function calcVals(){
  const sv=calcLoad(), out={};
  FLD.forEach(([k,,dv])=>{
    const el=$('re3c_'+k); let v=el?parseFloat(el.value):NaN;
    if(isNaN(v)) v=sv[k]!==undefined?sv[k]:dv;
    out[k]=v;
  });
  return out;
}
function calcDefaults(){
  const p12=D.pred12&&(D.pred12[REG]||D.pred12['서울']||D.pred12['전국']);
  return {rm:D.mtg||4.5, rj:(D.mtg||4.5)-0.5, g:p12?p12.g:3.0, _p12:p12};
}
function renderCalc(){
  const host=$('re3_calc'); if(!host) return;
  const sv=calcLoad(), df=calcDefaults();
  host.innerHTML='<div style="display:flex;flex-wrap:wrap;gap:6px 14px;background:#fff;border:1px solid #e2e5ea;border-radius:8px;padding:8px 12px;max-width:1100px">'+
    FLD.map(([k,lb,dv,un,st])=>{
      let v=sv[k]!==undefined?sv[k]:(dv!==null?dv:(df[k]!==undefined?df[k]:''));
      if(v!==null&&typeof v==='number') v=Math.round(v*100)/100;
      return `<label style="font-size:12px;display:flex;align-items:center;gap:4px">${lb}
        <input id="re3c_${k}" type="number" step="${st}" value="${v}" style="width:82px;padding:2px 5px;border:1px solid #cfd4da;border-radius:5px;font-size:12px;text-align:right">
        <span style="color:#889">${un}</span></label>`;}).join('')+
    `<button id="re3c_reset" style="font-size:11.5px;padding:3px 10px;border:1px solid #cfd4da;border-radius:6px;background:#f6f7f9;cursor:pointer">기본값으로</button></div>`+
    (df._p12?`<p class="note" style="margin:4px 0 0">기대 상승률 기본값 = RE 예측 ${REG in (D.pred12||{})?REG:'서울'} 12M <b>${df._p12.g>0?'+':''}${df._p12.g}%</b> (80% 밴드 ${df._p12.lo}~${df._p12.hi}% · 기준 ${df._p12.m}) — 밴드가 넓으니 직접 조절해 보세요.</p>`:'');
  host.querySelectorAll('input').forEach(el=>el.addEventListener('input',()=>{calcSave(calcVals());renderCalcOut();}));
  $('re3c_reset').onclick=()=>{try{localStorage.removeItem(CK);}catch(e){} renderCalc();renderCalcOut();};
  renderCalcOut();
}
function renderCalcOut(){
  const o=$('re3_calc_out'); if(!o) return;
  const v=calcVals();
  const eqB=v.P*(1+v.at/100)-v.L;                       // 매매 자기자본(취득세 포함)
  const buyCost=eqB*v.ro/100 + v.L*v.rm/100 + v.P*v.ht/100 + v.P*v.at/100/Math.max(v.yy,1) - v.P*v.g/100;
  const jsEq=v.J-v.jl;
  const jsCost=jsEq*v.ro/100 + v.jl*v.rj/100;
  const woCost=v.D*v.ro/100 + v.M*12;
  const rows=[['🏠 매매',buyCost,`자기자본 ${fmtW(eqB)} 기회비용 + 이자 + 보유세 + 취득세 상각 − 기대상승 ${fmtW(v.P*v.g/100)}`],
              ['🔑 전세',jsCost,`보증금 기회비용${v.jl>0?' + 전세대출 이자':''}`],
              ['📄 월세',woCost,`보증금 기회비용 + 월세 연 ${fmtW(v.M*12)}`]];
  const best=rows.reduce((a,b)=>b[1]<a[1]?b:a);
  // 손익분기: 매매비용 = 전세비용이 되는 g*
  const gStar=((eqB*v.ro/100 + v.L*v.rm/100 + v.P*v.ht/100 + v.P*v.at/100/Math.max(v.yy,1)) - jsCost)/v.P*100;
  o.innerHTML=`<h3 style="margin:4px 0">연간 총비용 비교</h3>
  <table style="border-collapse:collapse;font-size:12.5px;background:#fff;width:100%">
    ${rows.map(([lb,c,why])=>`<tr${lb===best[0]?' style="background:#f0fdf4"':''}>
      <td style="border:1px solid #e2e5ea;padding:5px 10px;white-space:nowrap">${lb}${lb===best[0]?' <b style="color:#166534">◀ 최저</b>':''}</td>
      <td style="border:1px solid #e2e5ea;padding:5px 10px;text-align:right;font-weight:700;white-space:nowrap">${fmtW(c)}/년</td>
      <td style="border:1px solid #e2e5ea;padding:5px 10px;color:#667;font-size:11.5px">${why}</td></tr>`).join('')}
  </table>
  <p class="note" style="margin:6px 0 0;line-height:1.7">연 상승률이 <b>${gStar.toFixed(1)}%</b>를 넘으면 매매가 전세보다 유리해지는 구조
  (현재 가정 ${v.g>0?'+':''}${v.g}%). 월세→전세 환산도 기회비용 수익률(${v.ro}%)에 달려 있으니 함께 조절해 보세요.
  세금은 1주택 단순 가정(중개보수·수리비 제외)이다.</p>`;
}
const fmtW=x=>{const a=Math.abs(x); return (x<0?'−':'')+(a>=10000?(a/10000).toFixed(2)+'억':Math.round(a).toLocaleString()+'만');};

function renderJsr(){
  if(!window.Chart||!D.jsr||!$('re3_jsr')) return;
  const t=D.t, ds=[], col={'전국':'#0e7490','서울':'#9a3412'};
  let i0=t.length-1;
  Object.keys(D.jsr).forEach(k=>{const f=D.jsr[k].findIndex(x=>x!=null); if(f>=0&&f<i0)i0=f;});
  Object.keys(D.jsr).forEach(k=>ds.push({label:k,data:D.jsr[k].slice(i0),borderColor:col[k]||'#64748b',backgroundColor:'transparent',pointRadius:0,borderWidth:1.4,spanGaps:true}));
  if(jsrChart) jsrChart.destroy();
  jsrChart=new Chart($('re3_jsr'),{type:'line',data:{labels:t.slice(i0).map(fmt),datasets:ds},
    options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{labels:{boxWidth:16,font:{size:10}}}},
      scales:{x:{ticks:{maxTicksLimit:8,font:{size:9}}},y:{ticks:{font:{size:9}}}}}});
}

async function boot(){
  try{
    const r=await fetch('/api/db/re3'); D=await r.json();
    if(!D.regions.includes(REG)) REG=D.regions[0];
    render(); renderCalc(); renderJsr();
  }catch(e){ const el=$('re3_verdict'); if(el) el.innerHTML='<div class="note">re3 데이터 로드 실패: '+e.message+'</div>'; }
}
document.addEventListener('DOMContentLoaded',boot);
})();
