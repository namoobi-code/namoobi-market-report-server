/* kpop.js — K-POP 선행지표 탭 (2026-08-29 신설)
   데이터: /api/db/kpop (scripts/fetch_kpop.py · 매일 06:20 cron · 신규 LLM 토큰 0)
   구성: ① 소속사별 주간 앨범 판매량(써클차트) ② 음반 수출액(관세청 HS 8523491040)
         ③ 유튜브 채널 화력(구독자·Δ) ④ 연동 종목 시세 표
   설계 의도: 엔터 실적은 '앨범이 팔린다 → 수출로 잡힌다 → 분기 실적에 찍힌다' 순서라
             앞 두 단계가 실적 발표를 선행한다. 그 선행 구간만 모아 본다. */
(function(){
'use strict';
let D=null, ch1=null, ch2=null, ch3=null, YTKIND='레이블';
const $=id=>document.getElementById(id);
const nf=n=>(n==null?'—':Number(n).toLocaleString());
const pf=v=>v==null?'—':(v>0?'+':'')+v.toFixed(1)+'%';
const pc=v=>v==null?'#64748b':(v>0?'#dc2626':v<0?'#2563eb':'#64748b');
const COL=nm=>((D&&D.labels||[]).find(l=>l.name===nm)||{}).color||'#94a3b8';

function render(){
  if(!D) return;
  $('kp_asof').textContent='기준 '+(D.as_of||'')+' · 서버 매일 06:20 자동 수집';

  // ── ① 소속사별 주간 앨범 판매량 ──────────────────────────────────────
  const S=(D.circle&&D.circle.series)||[];
  const names=(D.labels||[]).map(l=>l.name);
  if(S.length){
    const L=S.map(s=>s.w+'주');
    const ds=names.map(n=>({label:n,data:S.map(s=>(s.by||{})[n]||0),
      backgroundColor:COL(n),borderColor:COL(n),borderWidth:0}));
    if(ch1) ch1.destroy();
    ch1=new Chart($('kp_cv1'),{type:'bar',data:{labels:L,datasets:ds},
      options:{responsive:true,maintainAspectRatio:false,interaction:{mode:'index',intersect:false},
        plugins:{legend:{labels:{boxWidth:14,font:{size:11}}},
          tooltip:{callbacks:{label:c=>c.dataset.label+' '+nf(c.raw)+'장'}}},
        scales:{x:{stacked:true,ticks:{font:{size:10}}},
          y:{stacked:true,ticks:{font:{size:10},callback:v=>(v/10000)+'만'},title:{display:true,text:'주간 판매량(장)',font:{size:10}}}}}});
    // 최근 4주 소속사 요약
    const last=S[S.length-1], prev=S[S.length-2];
    $('kp_wk_sum').innerHTML=names.map(n=>{
      const c=(last.by||{})[n]||0, p=(prev&&prev.by||{})[n]||0;
      const d=p?((c/p-1)*100):null;
      return `<div style="flex:1;min-width:120px;border:1px solid #e2e8f0;border-left:4px solid ${COL(n)};border-radius:8px;padding:7px 10px;background:#fff">
        <div style="font-size:12px;color:#64748b">${n}</div>
        <div style="font-size:16px;font-weight:800">${nf(c)}<span style="font-size:11px;font-weight:400;color:#64748b">장</span></div>
        <div style="font-size:11px;color:${pc(d)}">전주比 ${d==null?'—':pf(d)}</div></div>`;}).join('');
  }
  // 최신주 TOP20
  const T=(D.circle&&D.circle.top)||[];
  $('kp_top').innerHTML=T.length?`<table style="border-collapse:collapse;font-size:12.5px;background:#fff;width:100%">
    <thead><tr style="background:#f8fafc">${['#','아티스트','앨범','소속사','주간 판매','누적'].map(h=>`<th style="border:1px solid #e2e8f0;padding:4px 7px;font-size:11.5px">${h}</th>`).join('')}</tr></thead>
    <tbody>${T.map(r=>`<tr>
      <td style="border:1px solid #e2e8f0;padding:3px 7px;text-align:center">${r.rank}${r.new?' <span style="color:#dc2626;font-size:10px">NEW</span>':''}</td>
      <td style="border:1px solid #e2e8f0;padding:3px 7px;font-weight:600">${r.artist}</td>
      <td style="border:1px solid #e2e8f0;padding:3px 7px;color:#475569">${r.album}</td>
      <td style="border:1px solid #e2e8f0;padding:3px 7px;text-align:center"><span style="background:${COL(r.label)};color:#fff;border-radius:9px;padding:1px 8px;font-size:11px">${r.label}</span></td>
      <td style="border:1px solid #e2e8f0;padding:3px 7px;text-align:right;font-weight:700">${nf(r.cnt)}</td>
      <td style="border:1px solid #e2e8f0;padding:3px 7px;text-align:right;color:#64748b">${nf(r.total)}</td></tr>`).join('')}</tbody></table>`
    :'<div class="note">데이터 없음</div>';

  // ── ② 음반 수출액 ────────────────────────────────────────────────────
  const E=D.export||{};
  if((E.months||[]).length){
    const m=E.months, v=E.exp;
    // 12개월 이동합 — 계절성(컴백 몰림)을 걷어낸 추세
    const roll=v.map((_,i)=>i<11?null:v.slice(i-11,i+1).reduce((a,b)=>a+b,0));
    if(ch2) ch2.destroy();
    ch2=new Chart($('kp_cv2'),{data:{labels:m,datasets:[
      {type:'bar',label:'월 수출액(천$)',data:v,yAxisID:'y',backgroundColor:'#c026d3',borderWidth:0},
      {type:'line',label:'12개월 누적(천$)',data:roll,yAxisID:'y2',borderColor:'#0f766e',backgroundColor:'transparent',pointRadius:0,borderWidth:1.8,spanGaps:true}]},
      options:{responsive:true,maintainAspectRatio:false,interaction:{mode:'index',intersect:false},
        plugins:{legend:{labels:{boxWidth:14,font:{size:11}}},
          tooltip:{callbacks:{label:c=>c.dataset.label+' '+nf(c.raw)}}},
        scales:{x:{ticks:{maxTicksLimit:12,font:{size:10}}},
          y:{position:'left',ticks:{font:{size:10},callback:v=>(v/1000).toFixed(0)+'백만$'}},
          y2:{position:'right',grid:{drawOnChartArea:false},ticks:{font:{size:10},callback:v=>(v/1000).toFixed(0)+'백만$'}}}}});
    const last=v[v.length-1], yoy=v.length>12?((last/v[v.length-13]-1)*100):null;
    const y1=roll[roll.length-1], y0=roll.length>12?roll[roll.length-13]:null;
    $('kp_exp_sum').innerHTML=`최근 <b>${m[m.length-1]}</b> 수출액 <b>${nf(last)}</b>천$
      · 전년동월比 <b style="color:${pc(yoy)}">${pf(yoy)}</b>
      · 12개월 누적 <b>${y1==null?'—':nf(y1)}</b>천$ ${y0?`(전년 동기比 <b style="color:${pc((y1/y0-1)*100)}">${pf((y1/y0-1)*100)}</b>)`:''}
      <span class="note">— HS ${E.hs} · 관세청 수출입무역통계, 익월 발표(실적 1~2개월 선행)</span>`;
  }

  // ── ③ 유튜브 화력 ────────────────────────────────────────────────────
  const Y=(D.youtube||[]).filter(r=>r.kind===YTKIND);
  $('kp_yt_tab').innerHTML=['레이블','그룹'].map(k=>
    `<button class="chip" data-k="${k}" style="margin-right:6px;padding:3px 12px;border-radius:14px;border:1px solid ${k===YTKIND?'#be185d':'#d6d9de'};background:${k===YTKIND?'#be185d':'#fff'};color:${k===YTKIND?'#fff':'#333'};cursor:pointer;font-size:12px">${k}</button>`).join('');
  $('kp_yt_tab').querySelectorAll('button').forEach(b=>b.onclick=()=>{YTKIND=b.dataset.k;render();});
  const anyD=Y.some(r=>r.d7!=null);
  $('kp_yt').innerHTML=Y.length?`<table style="border-collapse:collapse;font-size:12.5px;background:#fff;width:100%">
    <thead><tr style="background:#f8fafc">${['채널','소속사','구독자','7일 Δ','30일 Δ','누적 조회수'].map(h=>`<th style="border:1px solid #e2e8f0;padding:4px 7px;font-size:11.5px">${h}</th>`).join('')}</tr></thead>
    <tbody>${Y.sort((a,b)=>b.sub-a.sub).map(r=>`<tr>
      <td style="border:1px solid #e2e8f0;padding:3px 7px;font-weight:600"><a href="https://www.youtube.com/channel/${r.id}" target="_blank" rel="noopener" style="color:#1d4ed8;text-decoration:none">${r.name}</a></td>
      <td style="border:1px solid #e2e8f0;padding:3px 7px;text-align:center"><span style="background:${COL(r.label)};color:#fff;border-radius:9px;padding:1px 8px;font-size:11px">${r.label}</span></td>
      <td style="border:1px solid #e2e8f0;padding:3px 7px;text-align:right;font-weight:700">${nf(r.sub)}</td>
      <td style="border:1px solid #e2e8f0;padding:3px 7px;text-align:right;color:${pc(r.d7)}">${r.d7==null?'<span style="color:#94a3b8">누적 중</span>':(r.d7>0?'+':'')+nf(r.d7)}</td>
      <td style="border:1px solid #e2e8f0;padding:3px 7px;text-align:right;color:${pc(r.d30)}">${r.d30==null?'<span style="color:#94a3b8">누적 중</span>':(r.d30>0?'+':'')+nf(r.d30)}</td>
      <td style="border:1px solid #e2e8f0;padding:3px 7px;text-align:right;color:#64748b">${nf(r.view)}</td></tr>`).join('')}</tbody></table>
    ${anyD?'':'<div class="note" style="margin-top:5px">Δ(증가분)는 수집 이력이 쌓이는 대로 채워진다 — 7일·30일 전 관측치가 있어야 계산되며, 없는 값은 추정하지 않는다.</div>'}`
    :'<div class="note">유튜브 데이터 없음 (keys/youtube.txt 확인)</div>';

  // ── ④ 연동 종목 ──────────────────────────────────────────────────────
  const ST=D.stocks||[];
  const TAGC={'직결':'#be185d','팬덤':'#7c3aed','공연':'#0f766e','스트리밍':'#0ea5e9','간접':'#94a3b8'};
  $('kp_stk').innerHTML=ST.length?`<table style="border-collapse:collapse;font-size:12.5px;background:#fff;width:100%">
    <thead><tr style="background:#f8fafc">${['종목','연결','현재가','1일','1개월','3개월','1년','왜 연동되나'].map(h=>`<th style="border:1px solid #e2e8f0;padding:4px 7px;font-size:11.5px">${h}</th>`).join('')}</tr></thead>
    <tbody>${ST.map(r=>`<tr>
      <td style="border:1px solid #e2e8f0;padding:3px 7px;font-weight:700">${r.name}<span style="font-size:10.5px;color:#94a3b8"> ${r.sym}</span></td>
      <td style="border:1px solid #e2e8f0;padding:3px 7px;text-align:center"><span style="background:${TAGC[r.tag]||'#94a3b8'};color:#fff;border-radius:9px;padding:1px 8px;font-size:11px">${r.tag}</span></td>
      <td style="border:1px solid #e2e8f0;padding:3px 7px;text-align:right">${r.cur==null?'—':nf(Math.round(r.cur*100)/100)}<span style="font-size:10px;color:#94a3b8"> ${r.ccy||''}</span></td>
      ${['d1','m1','m3','y1'].map(k=>`<td style="border:1px solid #e2e8f0;padding:3px 7px;text-align:right;color:${pc(r[k])};font-weight:${k==='y1'?'700':'400'}">${pf(r[k])}</td>`).join('')}
      <td style="border:1px solid #e2e8f0;padding:3px 7px;color:#475569;font-size:11.5px">${r.why||''}</td></tr>`).join('')}</tbody></table>`
    :'<div class="note">시세 없음</div>';

  // 판매 vs 주가 오버레이 — 4사 주간 판매 합계와 주가(1년)를 같은 화면에
  const S4=S.filter(s=>s.sum>0);
  if(S4.length&&ST.length){
    const big=ST.filter(r=>r.tag==='직결'&&r.spark&&r.spark.length);
    if(big.length){
      const n=Math.max(...big.map(b=>b.spark.length));
      const labels=Array.from({length:n},(_,i)=>'');
      if(ch3) ch3.destroy();
      ch3=new Chart($('kp_cv3'),{type:'line',data:{labels:labels,datasets:big.map(b=>{
          const base=b.spark[0]||1;
          return {label:b.name,data:b.spark.map(v=>+(v/base*100).toFixed(1)),
            borderColor:COL(b.name==='JYP Ent.'?'JYP':(b.name==='하이브'?'하이브':(b.name==='에스엠'?'에스엠':'와이지'))),
            backgroundColor:'transparent',pointRadius:0,borderWidth:1.6,spanGaps:true};})},
        options:{responsive:true,maintainAspectRatio:false,interaction:{mode:'index',intersect:false},
          plugins:{legend:{labels:{boxWidth:14,font:{size:11}}},tooltip:{callbacks:{title:()=>'',label:c=>c.dataset.label+' '+c.raw}}},
          scales:{x:{ticks:{display:false}},y:{ticks:{font:{size:10}},title:{display:true,text:'1년 전=100 기준 상대주가',font:{size:10}}}}}});
    }
  }
}

function load(force){
  if(D&&!force){ render(); return; }
  $('kp_asof').textContent='불러오는 중…';
  fetch('/api/db/kpop',{cache:'no-cache'}).then(r=>{
    if(!r.ok) throw new Error('HTTP '+r.status);
    return r.json();
  }).then(j=>{ D=j; render(); })
  .catch(e=>{ $('kp_asof').textContent='로드 실패: '+e.message+' (서버 수집 전이면 다음 06:20 이후 표시)'; });
}

window.renderKpop=function(){ load(false); };
document.addEventListener('DOMContentLoaded',function(){
  const b=document.getElementById('kp_reload'); if(b) b.onclick=()=>load(true);
});
})();
