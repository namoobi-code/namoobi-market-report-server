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
  $('re3_reg').querySelectorAll('button').forEach(b=>b.onclick=()=>{REG=b.dataset.r;render();});

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

async function boot(){
  try{
    const r=await fetch('/api/db/re3'); D=await r.json();
    if(!D.regions.includes(REG)) REG=D.regions[0];
    render();
  }catch(e){ const el=$('re3_verdict'); if(el) el.innerHTML='<div class="note">re3 데이터 로드 실패: '+e.message+'</div>'; }
}
document.addEventListener('DOMContentLoaded',boot);
})();
