/* debt.js — 💵 빅테크 조달구조 탭 (2026-08-31 신설)
   데이터: /api/db/bigtech_debt (scripts/fetch_bigtech_debt.py · 매일 06:45 · SEC EDGAR XBRL + FRED)
   목적: 3.1.8 CAPEX 가 '얼마 쓰나'라면 이 화면은 '그 돈을 어디서 구하나'.
        핵심 = 증분부채 ÷ CAPEX — 자기 현금으로 짓던 데이터센터를 빚으로 짓기 시작한 전환점.
   구성: ① 조달 요약표 ② 발행 딜 타임라인 ③ 신용 경고등 ④ 차트 2장 */
(function(){
'use strict';
let D=null, charts={};
const $=id=>document.getElementById(id);
const COLS={'MSFT':'#0ea5e9','AMZN':'#b45309','GOOGL':'#16a34a','META':'#4f46e5','ORCL':'#e11d48'};
const n1=v=>(v==null?'—':(Math.round(v*10)/10).toLocaleString());
const pct=v=>(v==null?'—':(v>0?'+':'')+v+'%');

function tdS(extra){return 'border:1px solid #e2e8f0;padding:3px 7px;'+(extra||'');}

function render(){
  if(!D) return;
  $('dbt_asof').textContent='기준 '+(D.as_of||'')+' · 서버 매일 06:45'+(D.llm_asof?` · 🧠 최근 보고서 갱신 ${D.llm_asof}`:'');
  const agg=D.agg||[], last=agg[agg.length-1]||{};

  // ── ① 조달 요약표 (합산 + 기업별 최신 분기)
  const A=agg.slice(-9);
  const hdr=['시점','총부채','순부채','발행액(LTM)','CAPEX(LTM)','증분부채÷CAPEX'];
  let t1=`<table style="border-collapse:collapse;font-size:12px;background:#fff;width:100%">
    <thead><tr style="background:#f8fafc">${hdr.map(h=>`<th style="${tdS()}">${h}</th>`).join('')}</tr></thead><tbody>`;
  [...A].reverse().forEach((a,i)=>{
    const hot=a.dd_capex!=null&&a.dd_capex>=30;
    t1+=`<tr style="background:${i===0?'#fffbeb':'#fff'}">
      <td style="${tdS('white-space:nowrap;font-weight:'+(i===0?700:400))}">${a.d}</td>
      <td style="${tdS('text-align:right')}">${n1(a.debt)}</td>
      <td style="${tdS('text-align:right;color:'+(a.net>0?'#b91c1c':'#166534'))}">${n1(a.net)}</td>
      <td style="${tdS('text-align:right')}">${n1(a.issue_ltm)}</td>
      <td style="${tdS('text-align:right')}">${n1(a.capex_ltm)}</td>
      <td style="${tdS('text-align:right;font-weight:700;color:'+(hot?'#b91c1c':'#334155'))}">${pct(a.dd_capex)}</td></tr>`;
  });
  t1+='</tbody></table>';
  $('dbt_agg').innerHTML=t1;
  $('dbt_head').innerHTML=`최신 <b>${last.d||'-'}</b> — 5사 합산 총부채 <b>${n1(last.debt)}십억$</b> ·
    LTM 회사채 발행 <b>${n1(last.issue_ltm)}십억$</b> ·
    <b style="color:#b91c1c;font-size:15px">증분부채 ÷ CAPEX = ${pct(last.dd_capex)}</b>
    <span class="note">(1년 전 대비 늘어난 빚이 같은 기간 설비투자의 몇 %인가 — 100%면 전액을 빚으로 지은 셈)</span>`;

  // 기업별 최신
  const cols=['기업','총부채','현금성자산','순부채','발행액(LTM)','CAPEX(LTM)','증분부채÷CAPEX','순부채/EBITDA'];
  let t2=`<table style="border-collapse:collapse;font-size:12px;background:#fff;width:100%">
    <thead><tr style="background:#f8fafc">${cols.map(h=>`<th style="${tdS()}">${h}</th>`).join('')}</tr></thead><tbody>`;
  (D.rows||[]).forEach(r=>{
    const s=(r.series||[])[r.series.length-1]||{};
    const lev=s.nd_ebitda, risky=lev!=null&&lev>=2;
    t2+=`<tr>
      <td style="${tdS('white-space:nowrap;font-weight:700')}"><span style="color:${COLS[r.sym]||'#334155'}">●</span> ${r.name} <span class="note">${r.sym} · ${s.d||''}</span></td>
      <td style="${tdS('text-align:right')}">${n1(s.debt)}</td>
      <td style="${tdS('text-align:right;color:#64748b')}">${n1(s.cash)}</td>
      <td style="${tdS('text-align:right;font-weight:600;color:'+(s.net>0?'#b91c1c':'#166534'))}">${n1(s.net)}${s.net<0?' <span class="note">순현금</span>':''}</td>
      <td style="${tdS('text-align:right')}">${n1(s.issue_ltm)}</td>
      <td style="${tdS('text-align:right')}">${n1(s.capex_ltm)}</td>
      <td style="${tdS('text-align:right;font-weight:700;color:'+(s.dd_capex>=30?'#b91c1c':'#334155'))}">${pct(s.dd_capex)}</td>
      <td style="${tdS('text-align:right;font-weight:'+(risky?700:400)+';color:'+(risky?'#b91c1c':'#334155'))}">${lev==null?'—':lev.toFixed(2)+'x'}</td></tr>`;
  });
  t2+='</tbody></table>';
  $('dbt_co').innerHTML=t2;

  // 참고 집계치(외부)
  const b=D.bench||{};
  $('dbt_bench').innerHTML=(b.items||[]).map(x=>`<b>${x.k}</b> ${x.v}`).join(' · ')+
    (b.url?` <a href="${b.url}" target="_blank" rel="noopener">[${b.src||'출처'}]</a>`:'');

  // ── ② 발행 딜 타임라인
  const ds=[...(D.deals||[])].reverse();
  $('dbt_deals').innerHTML=ds.length?ds.map(d=>{
    const eq=/주식/.test(d.note||'');
    return `<div style="display:flex;gap:9px;align-items:flex-start;padding:6px 0;border-bottom:1px solid #f1f5f9">
      <span style="min-width:62px;font-size:11.5px;color:#64748b;font-weight:600">${d.d}</span>
      <span style="min-width:78px;font-weight:700;font-size:12.5px">${d.co}</span>
      <span style="min-width:74px;text-align:right;font-weight:700;font-size:13px;color:${eq?'#7c3aed':'#1d4ed8'}">${d.amt!=null?d.amt+'십억$':'—'}</span>
      <span style="font-size:11.5px;color:#475569">${d.note||''}${d.llm?' <span style="color:#7c3aed">🧠</span>':''}</span></div>`;
  }).join(''):'<div class="note">데이터 없음</div>';

  // ── ③ 신용 경고등
  const FL={ok:['🟢','#166534','#dcfce7'],warn:['🔴','#b91c1c','#fee2e2'],watch:['🟡','#b45309','#fef3c7']};
  let t3=`<table style="border-collapse:collapse;font-size:12px;background:#fff;width:100%">
    <thead><tr style="background:#f8fafc">${['','기업','S&P','무디스','비고'].map(h=>`<th style="${tdS()}">${h}</th>`).join('')}</tr></thead><tbody>`;
  (D.ratings||[]).forEach(r=>{const f=FL[r.flag]||FL.watch;
    t3+=`<tr style="background:${r.flag==='warn'?f[2]:'#fff'}">
      <td style="${tdS('text-align:center')}">${f[0]}</td>
      <td style="${tdS('white-space:nowrap;font-weight:700')}">${r.co}</td>
      <td style="${tdS('text-align:center;font-weight:700;color:'+f[1])}">${r.sp||'—'}</td>
      <td style="${tdS('text-align:center')}">${r.moody||'—'}</td>
      <td style="${tdS('font-size:11.5px;color:#475569')}">${r.note||''}${r.llm?' <span style="color:#7c3aed">🧠</span>':''}</td></tr>`;});
  t3+='</tbody></table>';
  $('dbt_rate').innerHTML=t3;

  // ── ④ 차트
  Object.values(charts).forEach(c=>{try{c.destroy();}catch(e){}}); charts={};
  // (a) 증분부채/CAPEX(선·우축) + 총부채(막대·좌축)
  charts.a=new Chart($('dbt_cv1'),{data:{labels:agg.map(a=>a.d),datasets:[
      {type:'bar',label:'5사 합산 총부채 (십억$)',data:agg.map(a=>a.debt),backgroundColor:'#cbd5e1',yAxisID:'y'},
      {type:'line',label:'증분부채 ÷ CAPEX (%)',data:agg.map(a=>a.dd_capex??null),borderColor:'#b91c1c',
       backgroundColor:'#b91c1c',pointRadius:3,borderWidth:2.2,spanGaps:true,yAxisID:'y1'}]},
    options:{responsive:true,maintainAspectRatio:false,interaction:{mode:'index',intersect:false},
      plugins:{legend:{labels:{boxWidth:13,font:{size:10.5}}}},
      scales:{x:{ticks:{maxTicksLimit:10,font:{size:9.5}}},
        y:{position:'left',ticks:{font:{size:10}},title:{display:true,text:'총부채(십억$)',font:{size:10}}},
        y1:{position:'right',grid:{drawOnChartArea:false},ticks:{font:{size:10},callback:v=>v+'%'},
            title:{display:true,text:'증분부채 ÷ CAPEX',font:{size:10}}}}}});
  // (b) 기업별 LTM 회사채 발행액
  const rs=(D.rows||[]).filter(r=>(r.series||[]).some(s=>s.issue_ltm!=null));
  const labs=agg.map(a=>a.d);
  charts.b=new Chart($('dbt_cv2'),{type:'line',data:{labels:labs,datasets:rs.map(r=>({
      label:r.name,borderColor:COLS[r.sym],backgroundColor:COLS[r.sym],pointRadius:2.5,borderWidth:1.8,spanGaps:true,
      data:labs.map(L=>{const c=(r.series||[]).filter(s=>s.d<=L&&s.issue_ltm!=null);return c.length?c[c.length-1].issue_ltm:null;})}))},
    options:{responsive:true,maintainAspectRatio:false,interaction:{mode:'index',intersect:false},
      plugins:{legend:{labels:{boxWidth:13,font:{size:10.5}}},
        tooltip:{itemSort:(a,c)=>(c.raw??-1e18)-(a.raw??-1e18),callbacks:{label:c=>c.dataset.label+' '+c.raw+'십억$'}}},
      scales:{x:{ticks:{maxTicksLimit:10,font:{size:9.5}}},
        y:{ticks:{font:{size:10}},title:{display:true,text:'최근 12개월 회사채 발행액(십억$)',font:{size:10}}}}}});
  // (c) 조달비용 환경 — IG·HY OAS
  const oas=D.oas||{}, ig=oas.ig||[], hy=oas.hy||[];
  if(ig.length||hy.length){
    const ls=(ig.length?ig:hy).map(x=>x[0]);
    const pick=(arr)=>ls.map(d=>{const f=arr.find(x=>x[0]===d);return f?f[1]:null;});
    charts.c=new Chart($('dbt_cv3'),{type:'line',data:{labels:ls,datasets:[
        {label:'투자등급(IG) 회사채 가산금리 %',data:pick(ig),borderColor:'#1d4ed8',backgroundColor:'#1d4ed8',pointRadius:0,borderWidth:1.8,yAxisID:'y'},
        {label:'하이일드(HY) 가산금리 %',data:pick(hy),borderColor:'#b45309',backgroundColor:'#b45309',pointRadius:0,borderWidth:1.5,yAxisID:'y1'}]},
      options:{responsive:true,maintainAspectRatio:false,interaction:{mode:'index',intersect:false},
        plugins:{legend:{labels:{boxWidth:13,font:{size:10.5}}}},
        scales:{x:{ticks:{maxTicksLimit:12,font:{size:9.5}}},
          y:{position:'left',ticks:{font:{size:10}},title:{display:true,text:'IG OAS(%)',font:{size:10}}},
          y1:{position:'right',grid:{drawOnChartArea:false},ticks:{font:{size:10}},title:{display:true,text:'HY OAS(%)',font:{size:10}}}}}});
  }
}

function load(force){
  if(D&&!force){ render(); return; }
  $('dbt_asof').textContent='불러오는 중…';
  fetch('/api/db/bigtech_debt',{cache:'no-cache'})
    .then(r=>{if(!r.ok)throw new Error('HTTP '+r.status);return r.json();})
    .then(j=>{D=j;render();})
    .catch(e=>{$('dbt_asof').textContent='로드 실패: '+e.message+' (서버 수집 전이면 06:45 이후 표시)';});
}

window.renderDebt=function(){ load(false); };
document.addEventListener('DOMContentLoaded',function(){
  const b=$('dbt_reload'); if(b) b.onclick=()=>load(true);
});
})();
