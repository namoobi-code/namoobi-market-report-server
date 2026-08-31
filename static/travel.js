/* travel.js — ✈️ 여행 시소(Travel Seesaw) 탭 (2026-08-31 신설)
   데이터: /api/db/travel (scripts/fetch_travel.py · 매일 06:50)
   목적: 아웃바운드(한국인 해외여행)와 인바운드(외국인 방한)는 하나의 테마가 아니라 시소다.
        원화 약세 → 외국인에겐 한국이 싸짐(인↑) / 한국인에겐 해외가 비싸짐(아웃↓).
        그래서 하나투어와 호텔신라를 같은 화면에 놓고 '반대로' 읽는다.
   구성: ① 시소 헤더 ② 아웃바운드 ③ 인바운드 ④ 선행성 검증판 */
(function(){
'use strict';
let D=null, charts={};
const $=id=>document.getElementById(id);
const C=['#be185d','#0ea5e9','#b45309','#7c3aed','#0f766e','#e11d48','#4f46e5','#ca8a04','#16a34a','#334155'];
const n0=v=>(v==null?'—':Math.round(v).toLocaleString());
const sg=v=>(v>0?'+':'')+v;
const td=s=>'border:1px solid #e2e8f0;padding:3px 7px;'+(s||'');

function kill(){Object.values(charts).forEach(c=>{try{c.destroy();}catch(e){}});charts={};}
function line(id,labels,sets,ytitle,opt){
  const el=$(id); if(!el) return;
  charts[id]=new Chart(el,{type:'line',data:{labels,datasets:sets},
    options:Object.assign({responsive:true,maintainAspectRatio:false,interaction:{mode:'index',intersect:false},
      plugins:{legend:{labels:{boxWidth:12,font:{size:10}}}},
      scales:{x:{ticks:{maxTicksLimit:10,font:{size:9}}},
        y:{ticks:{font:{size:10}},title:{display:!!ytitle,text:ytitle,font:{size:10}}}}},opt||{})});
}
// 시계열 → 최근 N% 변화 (마지막값 vs n번째 전)
function chg(s,n){ if(!s||s.length<n+1) return null; const a=s[s.length-1][1],b=s[s.length-1-n][1];
  return (b? +(((a/b)-1)*100).toFixed(1) : null); }

function render(){
  if(!D) return;
  $('tv_asof').textContent='기준 '+(D.as_of||'')+' · 서버 매일 06:50';
  const air=(D.air||[]).filter(x=>x.kac);
  const last=air[air.length-1]||{}, kac=last.kac||{};
  const icnDays=(D.air||[]).filter(x=>x.icn);
  const icn=(icnDays[icnDays.length-1]||{}).icn||{};

  // ── ① 시소 헤더
  const fx=(D.fx||[]);
  const fxrow=fx.map(f=>{const s=f.series||[];const c=chg(s,12);
    return `<span style="margin-right:14px"><b>${f.name}</b> ${s.length?(+s[s.length-1][1]).toFixed(f.sym==='CL=F'?1:2):'—'}
      ${c!=null?`<span style="color:${c>0?'#b91c1c':'#166534'};font-size:11px">${sg(c)}%<span class="note">(1y)</span></span>`:''}</span>`;}).join('');
  // 시소 판정 — 공항 국제 도착/출발 최근 7일 평균 비교
  const r7=air.slice(-7), p7=air.slice(-14,-7);
  const avg=(a,k)=>a.length?a.reduce((s,x)=>s+(x.kac[k]||0),0)/a.length:0;
  const inNow=avg(r7,'in'), outNow=avg(r7,'out'), inPrev=avg(p7,'in'), outPrev=avg(p7,'out');
  const inD=inPrev?((inNow/inPrev-1)*100):null, outD=outPrev?((outNow/outPrev-1)*100):null;
  let tilt='균형', tc='#475569';
  if(inD!=null&&outD!=null){ const g=inD-outD;
    if(g>2){tilt='인바운드 쪽으로 기움';tc='#166534';} else if(g<-2){tilt='아웃바운드 쪽으로 기움';tc='#be185d';} }
  $('tv_head').innerHTML=`
    <div style="display:flex;align-items:stretch;gap:10px;flex-wrap:wrap">
      <div style="flex:1 1 240px;border:1px solid #fbcfe8;border-radius:10px;background:#fdf2f8;padding:10px 12px">
        <div style="font-size:12px;color:#9d174d;font-weight:700">🛫 아웃바운드 — 한국인이 나간다</div>
        <div style="font-size:20px;font-weight:800;margin:3px 0">${n0(outNow)}<span style="font-size:11px;font-weight:400"> 명/일</span></div>
        <div class="note">국제선 출발 예상승객 7일 평균 ${outD!=null?`· 직전 7일 대비 <b style="color:${outD>0?'#166534':'#b91c1c'}">${sg(outD.toFixed(1))}%</b>`:''}</div>
      </div>
      <div style="flex:0 0 150px;display:flex;flex-direction:column;justify-content:center;align-items:center;text-align:center">
        <div style="font-size:22px">⚖️</div>
        <div style="font-size:12.5px;font-weight:800;color:${tc}">${tilt}</div>
        <div class="note" style="font-size:10px">원화 약세는 인바운드에 유리<br>· 아웃바운드에 불리</div>
      </div>
      <div style="flex:1 1 240px;border:1px solid #bbf7d0;border-radius:10px;background:#f0fdf4;padding:10px 12px">
        <div style="font-size:12px;color:#166534;font-weight:700">🛬 인바운드 — 외국인이 들어온다</div>
        <div style="font-size:20px;font-weight:800;margin:3px 0">${n0(inNow)}<span style="font-size:11px;font-weight:400"> 명/일</span></div>
        <div class="note">국제선 도착 예상승객 7일 평균 ${inD!=null?`· 직전 7일 대비 <b style="color:${inD>0?'#166534':'#b91c1c'}">${sg(inD.toFixed(1))}%</b>`:''}</div>
      </div>
    </div>
    <div style="margin-top:8px;font-size:12px">${fxrow}</div>
    ${icn.in?`<div class="note" style="margin-top:4px">인천공항 승객예고(당일 ${icnDays[icnDays.length-1].d}) — 입국 <b>${n0(icn.in)}</b> · 출국 <b>${n0(icn.out)}</b> 명</div>`:''}`;

  // 공항 차트 (국제 도착 vs 출발)
  kill();
  const L=air.map(x=>x.d.slice(4,6)+'/'+x.d.slice(6,8));
  line('tv_cv_air',L,[
    {label:'국제선 도착(인바운드)',data:air.map(x=>x.kac.in),borderColor:'#166534',backgroundColor:'#166534',pointRadius:0,borderWidth:1.9},
    {label:'국제선 출발(아웃바운드)',data:air.map(x=>x.kac.out),borderColor:'#be185d',backgroundColor:'#be185d',pointRadius:0,borderWidth:1.9}],
    '예상 승객수(명/일)');

  // ── ② 아웃바운드
  const go=(D.gt_out||[]);
  if(go.length){
    const ls=go[0].series.map(p=>p[0].slice(2));
    line('tv_cv_out_s',ls,go.map((g,i)=>({label:g.name,data:g.series.map(p=>p[1]),
      borderColor:C[i%C.length],backgroundColor:C[i%C.length],pointRadius:0,borderWidth:1.8})),'검색 관심도(100=최고)');
  }
  const ec=D.ecos||[];
  if(ec.length){
    const e=ec.slice(-60), el=e.map(x=>x.d);
    line('tv_cv_pay',el,[
      {label:'여행지급 — 한국인이 해외서 쓴 돈',data:e.map(x=>x.pay),borderColor:'#be185d',backgroundColor:'#be185d',pointRadius:0,borderWidth:1.9},
      {label:'여행수입 — 외국인이 한국서 쓴 돈',data:e.map(x=>x.rev),borderColor:'#166534',backgroundColor:'#166534',pointRadius:0,borderWidth:1.9}],
      '백만 달러/월');
    const l=ec[ec.length-1];
    $('tv_ecos').innerHTML=`최근 <b>${l.d}</b> — 여행수입 <b>${n0(l.rev)}</b> · 여행지급 <b>${n0(l.pay)}</b> ·
      여행수지 <b style="color:${l.bal>0?'#166534':'#b91c1c'}">${n0(l.bal)}</b>백만$
      <span class="note">(수지 플러스 = 외국인이 쓰고 간 돈이 더 많음 — 2020년 이전엔 거의 항상 마이너스였다)</span>`;
  }
  $('tv_out_st').innerHTML=stockTbl(D.outb);
  $('tv_in_st').innerHTML=stockTbl(D.inb);

  // ── ③ 인바운드 — 국가별 검색 관심도
  const gi=(D.gt||[]);
  if(gi.length){
    const ls=gi[0].series.map(p=>p[0].slice(2));
    line('tv_cv_in_s',ls,gi.map((g,i)=>({label:g.name+' ('+g.kw+')',data:g.series.map(p=>p[1]),
      borderColor:C[i%C.length],backgroundColor:C[i%C.length],pointRadius:0,borderWidth:1.8})),'검색 관심도(100=최고)');
    $('tv_in_rank').innerHTML=`<table style="border-collapse:collapse;font-size:12px;background:#fff;width:100%">
      <thead><tr style="background:#f8fafc">${['국가','검색어','현재','4주 전 대비','12주 전 대비'].map(h=>`<th style="${td()}">${h}</th>`).join('')}</tr></thead>
      <tbody>${gi.map(g=>{const s=g.series,c4=chg(s,4),c12=chg(s,12);
        return `<tr><td style="${td('font-weight:700;white-space:nowrap')}">${g.name}</td>
        <td style="${td('color:#475569')}">${g.kw}</td>
        <td style="${td('text-align:right;font-weight:700')}">${s[s.length-1][1]}</td>
        ${[c4,c12].map(c=>`<td style="${td('text-align:right;color:'+(c>0?'#166534':c<0?'#b91c1c':'#64748b'))}">${c==null?'—':sg(c)+'%'}</td>`).join('')}</tr>`;}).join('')}
      </tbody></table>`;
  }
  // ③-a 카지노 월매출 — 내국인 출입 금지라 매출 전액이 방한 외국인 소비(T+2일)
  const cas=D.casino;
  if(cas&&Object.keys(cas).length){
    const names=Object.keys(cas);
    const all=[...new Set(names.flatMap(n=>cas[n].series.map(s=>s.d)))].sort();
    line('tv_cv_casino',all,names.map((n,i)=>({label:n,data:all.map(d=>{
        const f=cas[n].series.find(s=>s.d===d);return f?f.rev:null;}),
      borderColor:C[i%C.length],backgroundColor:C[i%C.length],pointRadius:2.5,borderWidth:2,spanGaps:true})),
      '카지노 매출(십억원/월)');
    $('tv_casino').innerHTML=`<table style="border-collapse:collapse;font-size:12px;background:#fff;width:100%">
      <thead><tr style="background:#f8fafc">${['','월'].concat(all.slice(-6)).map((h,i)=>`<th style="${td()}">${i===0?'회사':i===1?'':h}</th>`).join('')}</tr></thead>
      <tbody>${names.map(n=>{const S=cas[n].series;
        return `<tr><td style="${td('font-weight:700;white-space:nowrap')}" rowspan="2">${n} <span class="note">${cas[n].stock}</span></td>
          <td style="${td('color:#64748b;font-size:11px')}">매출</td>
          ${all.slice(-6).map(d=>{const f=S.find(s=>s.d===d);return `<td style="${td('text-align:right;font-weight:600')}">${f?f.rev:'—'}</td>`;}).join('')}</tr>
        <tr><td style="${td('color:#64748b;font-size:11px')}">YoY</td>
          ${all.slice(-6).map(d=>{const f=S.find(s=>s.d===d),y=f?f.yoy:null;
            return `<td style="${td('text-align:right;font-size:11px;color:'+(y==null?'#94a3b8':y>0?'#166534':'#b91c1c'))}">${y==null?'—':sg(y.toFixed(1))+'%'}</td>`;}).join('')}</tr>`;}).join('')}
      </tbody></table>
      <div class="note" style="margin-top:4px">단위 십억원. 외국인 전용 카지노는 <b>내국인 출입이 법으로 금지</b>돼 매출 전액이 방한 외국인 소비다 —
        백화점·면세점 실적보다 6주 이상 빠르고, 중화권 큰손 비중이 커서 <b>중국 인바운드의 실적 대리지표</b>가 된다. 매월 초 DART 공정공시(T+2일).</div>`;
  }

  // ③-b 인천 노선 공급 — 국가·권역별 도착편 (중국의 유일한 고빈도 대리지표)
  const rt=D.routes, rh=(D.routes_hist||[]);
  if(rt&&rt.co){
    const order=['중국','일본','홍콩·마카오·대만','동남아','미주','유럽·중동','기타'];
    const ks=order.filter(k=>rt.co[k]!=null);
    const tot=rt.total||1;
    // 이력이 쌓이면 직전 스냅샷 대비 증감
    const prev=rh.length>1?rh[rh.length-2]:null;
    $('tv_routes').innerHTML=`<div style="font-size:12.5px;margin-bottom:6px">인천공항 도착 여객편 <b>${rt.total.toLocaleString()}편</b>
        <span class="note">향후 ${rt.days}일치 스케줄 (${rt.span}) — 항공사가 수요를 보고 미리 깐 좌석이라 실제 입국객보다 앞선다</span></div>
      <table style="border-collapse:collapse;font-size:12px;background:#fff;width:100%">
      <thead><tr style="background:#f8fafc">${['권역','도착 편수','비중','직전 대비'].map(h=>`<th style="${td()}">${h}</th>`).join('')}</tr></thead>
      <tbody>${ks.map(k=>{const v=rt.co[k],p=prev?prev[k]:null,d=(p!=null&&p)?((v/p-1)*100):null;
        return `<tr${k==='중국'?' style="background:#fef2f2"':''}>
        <td style="${td('font-weight:'+(k==='중국'?700:400))}">${k}${k==='중국'?' <span class="note">★ 검색 프록시 불가 — 이 지표로 본다</span>':''}</td>
        <td style="${td('text-align:right;font-weight:600')}">${v.toLocaleString()}</td>
        <td style="${td('text-align:right;color:#64748b')}">${(v/tot*100).toFixed(1)}%</td>
        <td style="${td('text-align:right;color:'+(d==null?'#94a3b8':d>0?'#166534':d<0?'#b91c1c':'#64748b'))}">${d==null?'—':sg(d.toFixed(1))+'%'}</td></tr>`;}).join('')}
      </tbody></table>
      <div class="note" style="margin-top:4px">직전 대비는 이력이 이틀 이상 쌓인 뒤부터 표시된다(매일 06:50 스냅샷 누적).</div>`;
    // 노선 공급 추이 차트 (이력 2일 이상일 때만)
    if(rh.length>1){
      line('tv_cv_routes',rh.map(x=>x.d.slice(4,6)+'/'+x.d.slice(6,8)),
        ks.map((k,i)=>({label:k,data:rh.map(x=>x[k]??null),borderColor:C[i%C.length],
          backgroundColor:C[i%C.length],pointRadius:2,borderWidth:1.8,spanGaps:true})),'주간 도착 편수');
      const cv=$('tv_cv_routes'); if(cv&&cv.parentElement) cv.parentElement.style.display='';
    } else { const cv=$('tv_cv_routes'); if(cv&&cv.parentElement) cv.parentElement.style.display='none'; }
    // 출발지 상위
    $('tv_routes_top').innerHTML=`<table style="border-collapse:collapse;font-size:11.5px;background:#fff;width:100%">
      <thead><tr style="background:#f8fafc">${['#','출발 공항','권역','편수'].map(h=>`<th style="${td()}">${h}</th>`).join('')}</tr></thead>
      <tbody>${(rt.top||[]).map((t,i)=>`<tr><td style="${td('text-align:center;color:#94a3b8')}">${i+1}</td>
        <td style="${td('font-weight:600')}">${t.name} <span class="note">${t.code}</span></td>
        <td style="${td('color:#475569')}">${t.co}</td>
        <td style="${td('text-align:right;font-weight:600')}">${t.n}</td></tr>`).join('')}</tbody></table>`;
  }

  // 공항별 인바운드 구성
  const ba=kac.byarp||{};
  const ks=Object.keys(ba).sort((a,b)=>ba[b].in-ba[a].in).slice(0,8);
  $('tv_arp').innerHTML=ks.length?`<table style="border-collapse:collapse;font-size:12px;background:#fff;width:100%">
    <thead><tr style="background:#f8fafc">${['공항','국제 도착(인)','국제 출발(아웃)','도착−출발'].map(h=>`<th style="${td()}">${h}</th>`).join('')}</tr></thead>
    <tbody>${ks.map(k=>{const v=ba[k],d=v.in-v.out;
      return `<tr><td style="${td('font-weight:700')}">${(D.airport_ko||{})[k]||k} <span class="note">${k}</span></td>
      <td style="${td('text-align:right')}">${n0(v.in)}</td><td style="${td('text-align:right')}">${n0(v.out)}</td>
      <td style="${td('text-align:right;font-weight:700;color:'+(d>0?'#166534':'#b91c1c'))}">${sg(n0(d))}</td></tr>`;}).join('')}
    </tbody></table><div class="note" style="margin-top:4px">${last.d} 기준. 도착−출발이 플러스면 그날 그 공항으로 순유입.</div>`:'';

  // ── ④ 선행성 검증판
  const ld=(D.lead||[]);
  if(ld.length){
    const best=l=>{let bi=-1,bv=0;l.c.forEach((v,i)=>{if(v!=null&&Math.abs(v)>Math.abs(bv)){bv=v;bi=i;}});return[bi,bv];};
    const rows=[...ld].sort((a,b)=>Math.abs(best(b)[1])-Math.abs(best(a)[1]));
    $('tv_lead').innerHTML=`<table style="border-collapse:collapse;font-size:12px;background:#fff;width:100%">
      <thead><tr style="background:#f8fafc">${['선행지표','종목','동월','1개월 뒤','2개월 뒤','3개월 뒤','최적'].map(h=>`<th style="${td()}">${h}</th>`).join('')}</tr></thead>
      <tbody>${rows.map(l=>{const[bi,bv]=best(l);
        return `<tr><td style="${td('color:#475569;white-space:nowrap')}">${l.ind}</td>
        <td style="${td('font-weight:700;white-space:nowrap')}">${l.stock}</td>
        ${l.c.map((v,i)=>`<td style="${td('text-align:right;'+(i===bi?'background:#fef9c3;font-weight:700;':'')+'color:'+(v==null?'#94a3b8':Math.abs(v)>=0.5?'#166534':Math.abs(v)>=0.3?'#334155':'#94a3b8'))}">${v==null?'—':v.toFixed(2)}</td>`).join('')}
        <td style="${td('text-align:center;font-weight:700;color:'+(Math.abs(bv)>=0.5?'#166534':'#64748b'))}">${bi<0?'—':(bi===0?'동월':bi+'개월 뒤')}</td></tr>`;}).join('')}
      </tbody></table>
      <div class="note" style="margin-top:5px">각 칸 = 선행지표 YoY 와 주가 YoY 의 상관계수(월별, 최근 8년). <b>0.5 이상이면 의미 있는 동행·선행</b>,
      0.3 미만이면 연결이 약하다는 뜻이므로 그 조합은 신뢰하지 않는다. 노란 칸 = 그 종목에서 상관이 가장 큰 시차 —
      <b>'1~3개월 뒤'가 최적이면 그 지표가 주가를 실제로 선행</b>한다는 관측이다. 추정 아님·전 구간 실측.</div>`;
  }
}

function stockTbl(list){
  if(!list||!list.length) return '<div class="note">데이터 없음</div>';
  const rows=list.map(s=>{const q=s.series||[];const c1=chg(q,1),c3=chg(q,3),c12=chg(q,12);
    return{name:s.name,sym:s.sym,px:q.length?q[q.length-1][1]:null,c1,c3,c12};})
    .sort((a,b)=>(b.c3??-1e9)-(a.c3??-1e9));
  return `<table style="border-collapse:collapse;font-size:12px;background:#fff;width:100%">
    <thead><tr style="background:#f8fafc">${['종목','현재가','1개월','3개월','1년'].map(h=>`<th style="${td()}">${h}</th>`).join('')}</tr></thead>
    <tbody>${rows.map(r=>`<tr>
      <td style="${td('font-weight:700;white-space:nowrap')}">${r.name} <span class="note">${r.sym.split('.')[0]}</span></td>
      <td style="${td('text-align:right')}">${r.px==null?'—':Math.round(r.px).toLocaleString()}</td>
      ${[r.c1,r.c3,r.c12].map(c=>`<td style="${td('text-align:right;font-weight:'+(c!=null&&Math.abs(c)>=15?700:400)+';color:'+(c==null?'#94a3b8':c>0?'#b91c1c':'#1d4ed8'))}">${c==null?'—':sg(c)+'%'}</td>`).join('')}
    </tr>`).join('')}</tbody></table>
    <div class="note" style="margin-top:3px">월봉 종가 기준 · 3개월 수익률 높은 순</div>`;
}

function load(force){
  if(D&&!force){ render(); return; }
  $('tv_asof').textContent='불러오는 중…';
  fetch('/api/db/travel',{cache:'no-cache'})
    .then(r=>{if(!r.ok)throw new Error('HTTP '+r.status);return r.json();})
    .then(j=>{D=j;render();})
    .catch(e=>{$('tv_asof').textContent='로드 실패: '+e.message+' (서버 수집 전이면 06:50 이후 표시)';});
}
window.renderTravel=function(){ load(false); };
document.addEventListener('DOMContentLoaded',function(){
  const b=$('tv_reload'); if(b) b.onclick=()=>load(true);
});
})();
