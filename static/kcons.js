/* kcons.js — K-소비재 선행지표 탭 (2026-08-29 신설)
   데이터: /api/db/kcons (scripts/fetch_kcons.py · 매일 06:25 cron · LLM 토큰 0)
   구성: ① 테마 요약 카드 ② 테마별 품목 수출 차트+표 ③ 연동 종목 표 ④ 테마 수출 vs 상대주가
   설계 의도: 이상적 선행 흐름은 검색 → 콘텐츠 반응 → 장바구니 → 주문 → 리뷰·재구매 → 수출이지만
             검색·쇼피·SNS는 공개 API가 없다. 무토큰으로 잡히는 '수출(월간) × 주가' 축을 구현하고
             국내 관심도는 기존 Trends 탭(구글·유튜브·네이버쇼핑)을 보조지표로 쓴다. */
(function(){
'use strict';
let D=null, TH='K뷰티', ch1=null, ch2=null;
const $=id=>document.getElementById(id);
const nf=n=>(n==null?'—':Number(n).toLocaleString());
const pf=v=>v==null?'—':(v>0?'+':'')+v.toFixed(1)+'%';
const pc=v=>v==null?'#64748b':(v>0?'#dc2626':v<0?'#2563eb':'#64748b');
const COL=t=>((D&&D.themes||[]).find(x=>x.name===t)||{}).color||'#94a3b8';
const ITEM_COLORS=['#be185d','#0ea5e9','#b45309','#7c3aed','#0f766e','#e11d48','#4f46e5','#ca8a04'];

function roll12(v){ return v.map((_,i)=>i<11?null:v.slice(i-11,i+1).reduce((a,b)=>a+(b||0),0)); }
function yoy(v,i){ return (i>=12&&v[i-12])?((v[i]/v[i-12]-1)*100):null; }

function render(){
  if(!D) return;
  $('kc_asof').textContent='기준 '+(D.as_of||'')+' · 서버 매일 06:25 자동 수집';
  const E=D.export||{}, M=E.months||[], IT=E.items||[];
  const themes=(D.themes||[]).map(t=>t.name);

  // ── ① 테마 요약 카드: 최근월 합계 YoY + 12M 누적 YoY ──────────────────
  $('kc_sum').innerHTML=themes.map(t=>{
    const its=IT.filter(x=>x.th===t);
    const sum=i=>its.reduce((a,x)=>a+(x.exp[i]||0),0);
    const n=M.length-1;
    const cur=sum(n), prev12=n>=12?sum(n-12):null;
    const yo=prev12?((cur/prev12-1)*100):null;
    const tot=M.map((_,i)=>sum(i)), r=roll12(tot);
    const ry=(r[n]!=null&&n>=12&&r[n-12])?((r[n]/r[n-12]-1)*100):null;
    return `<div style="flex:1;min-width:170px;border:1px solid #e2e8f0;border-left:4px solid ${COL(t)};border-radius:8px;padding:8px 12px;background:#fff">
      <div style="font-size:12.5px;font-weight:700;color:${COL(t)}">${t} <span style="font-weight:400;color:#94a3b8">${its.length}품목군</span></div>
      <div style="font-size:15.5px;font-weight:800">${nf(cur)}<span style="font-size:11px;font-weight:400;color:#64748b">천$ (${M[n]||''})</span></div>
      <div style="font-size:11.5px">전년동월比 <b style="color:${pc(yo)}">${pf(yo)}</b> · 12M누적 <b style="color:${pc(ry)}">${pf(ry)}</b></div></div>`;}).join('');

  // ── ② 테마 칩 + 품목 차트·표 ─────────────────────────────────────────
  $('kc_chips').innerHTML=themes.map(t=>
    `<button data-t="${t}" style="margin-right:6px;padding:3px 13px;border-radius:14px;border:1px solid ${t===TH?COL(t):'#d6d9de'};background:${t===TH?COL(t):'#fff'};color:${t===TH?'#fff':'#333'};cursor:pointer;font-size:12.5px">${t}</button>`).join('');
  $('kc_chips').querySelectorAll('button').forEach(b=>b.onclick=()=>{TH=b.dataset.t;render();});

  const its=IT.filter(x=>x.th===TH);
  if(ch1) ch1.destroy();
  ch1=new Chart($('kc_cv1'),{type:'line',data:{labels:M,datasets:its.map((x,i)=>{
      const r=roll12(x.exp||[]);
      return {label:x.nm,data:r,borderColor:ITEM_COLORS[i%ITEM_COLORS.length],backgroundColor:'transparent',pointRadius:0,borderWidth:1.7,spanGaps:true};})},
    options:{responsive:true,maintainAspectRatio:false,interaction:{mode:'index',intersect:false},
      plugins:{legend:{labels:{boxWidth:14,font:{size:11}}},tooltip:{callbacks:{label:c=>c.dataset.label+' '+nf(c.raw)+'천$'}}},
      scales:{x:{ticks:{maxTicksLimit:12,font:{size:10}}},
        y:{ticks:{font:{size:10},callback:v=>(v/1000000).toFixed(1)+'십억$'},title:{display:true,text:'12개월 누적 수출(천$) — 계절성 제거 추세',font:{size:10}}}}}});

  const n=M.length-1;
  $('kc_tbl').innerHTML=`<table style="border-collapse:collapse;font-size:12.5px;background:#fff;width:100%">
    <thead><tr style="background:#f8fafc">${['품목군','HS','최근월(천$)','전년동월比','12M누적(천$)','누적 YoY','비고'].map(h=>`<th style="border:1px solid #e2e8f0;padding:4px 7px;font-size:11.5px">${h}</th>`).join('')}</tr></thead>
    <tbody>${its.map(x=>{
      const r=roll12(x.exp||[]);
      const ry=(r[n]!=null&&n>=12&&r[n-12])?((r[n]/r[n-12]-1)*100):null;
      const yo=yoy(x.exp||[],n);
      return `<tr><td style="border:1px solid #e2e8f0;padding:3px 7px;font-weight:600">${x.nm}</td>
      <td style="border:1px solid #e2e8f0;padding:3px 7px;text-align:center;color:#94a3b8;font-size:11px">${x.hs}</td>
      <td style="border:1px solid #e2e8f0;padding:3px 7px;text-align:right;font-weight:700">${nf(x.exp[n])}</td>
      <td style="border:1px solid #e2e8f0;padding:3px 7px;text-align:right;color:${pc(yo)}">${pf(yo)}</td>
      <td style="border:1px solid #e2e8f0;padding:3px 7px;text-align:right">${nf(r[n])}</td>
      <td style="border:1px solid #e2e8f0;padding:3px 7px;text-align:right;font-weight:700;color:${pc(ry)}">${pf(ry)}</td>
      <td style="border:1px solid #e2e8f0;padding:3px 7px;color:#64748b;font-size:11.5px">${x.note||''}</td></tr>`;}).join('')}</tbody></table>`;

  // ── ③ 연동 종목 표 (선택 테마) ────────────────────────────────────────
  const ST=(D.stocks||[]).filter(s=>s.th===TH);
  $('kc_stk').innerHTML=ST.length?`<table style="border-collapse:collapse;font-size:12.5px;background:#fff;width:100%">
    <thead><tr style="background:#f8fafc">${['종목','현재가','1일','1개월','3개월','1년','수출 지표와의 연결'].map(h=>`<th style="border:1px solid #e2e8f0;padding:4px 7px;font-size:11.5px">${h}</th>`).join('')}</tr></thead>
    <tbody>${ST.map(r=>`<tr>
      <td style="border:1px solid #e2e8f0;padding:3px 7px;font-weight:700">${r.name}<span style="font-size:10.5px;color:#94a3b8"> ${r.sym.replace(/\.(KS|KQ)$/,'')}</span></td>
      <td style="border:1px solid #e2e8f0;padding:3px 7px;text-align:right">${nf(r.cur)}</td>
      ${['d1','m1','m3','y1'].map(k=>`<td style="border:1px solid #e2e8f0;padding:3px 7px;text-align:right;color:${pc(r[k])};font-weight:${k==='y1'?'700':'400'}">${pf(r[k])}</td>`).join('')}
      <td style="border:1px solid #e2e8f0;padding:3px 7px;color:#475569;font-size:11.5px">${r.why||''}</td></tr>`).join('')}</tbody></table>`
    :'<div class="note">종목 없음</div>';

  // ── ④ 테마 수출 12M 누적 vs 대표주 상대주가 ──────────────────────────
  if(ch2) ch2.destroy();
  const spark=ST.filter(s=>s.spark&&s.spark.length);
  if(spark.length){
    const L=Math.max(...spark.map(s=>s.spark.length));
    ch2=new Chart($('kc_cv2'),{type:'line',data:{labels:Array.from({length:L},()=>''),
      datasets:spark.map((s,i)=>{const b=s.spark[0]||1;
        return {label:s.name,data:s.spark.map(v=>+(v/b*100).toFixed(1)),
          borderColor:ITEM_COLORS[i%ITEM_COLORS.length],backgroundColor:'transparent',pointRadius:0,borderWidth:1.4,spanGaps:true};})},
      options:{responsive:true,maintainAspectRatio:false,interaction:{mode:'index',intersect:false},
        plugins:{legend:{labels:{boxWidth:13,font:{size:10.5}}},tooltip:{callbacks:{title:()=>'',label:c=>c.dataset.label+' '+c.raw}}},
        scales:{x:{ticks:{display:false}},y:{ticks:{font:{size:10}},title:{display:true,text:TH+' 연동 종목 상대주가 (1년 전=100)',font:{size:10}}}}}});
  }
}

function load(force){
  if(D&&!force){ render(); return; }
  $('kc_asof').textContent='불러오는 중…';
  fetch('/api/db/kcons',{cache:'no-cache'}).then(r=>{
    if(!r.ok) throw new Error('HTTP '+r.status);
    return r.json();
  }).then(j=>{ D=j; render(); })
  .catch(e=>{ $('kc_asof').textContent='로드 실패: '+e.message+' (서버 수집 전이면 다음 06:25 이후 표시)'; });
}

window.renderKcons=function(){ load(false); };
document.addEventListener('DOMContentLoaded',function(){
  const b=$('kc_reload'); if(b) b.onclick=()=>load(true);
});
})();
