/* kcons.js — K-소비재 선행지표 탭 (2026-08-29 신설)
   데이터: /api/db/kcons (scripts/fetch_kcons.py · 매일 06:25 cron · LLM 토큰 0)
   구성: ① 테마 요약 카드 ② 테마별 품목 수출 차트+표 ③ 연동 종목 표 ④ 테마 수출 vs 상대주가
   설계 의도: 이상적 선행 흐름은 검색 → 콘텐츠 반응 → 장바구니 → 주문 → 리뷰·재구매 → 수출이지만
             검색·쇼피·SNS는 공개 API가 없다. 무토큰으로 잡히는 '수출(월간) × 주가' 축을 구현하고
             국내 관심도는 기존 Trends 탭(구글·유튜브·네이버쇼핑)을 보조지표로 쓴다. */
(function(){
'use strict';
let D=null, TH='K뷰티', MODE='idx', ch1=null, ch2=null;   // MODE: idx(지수)|abs(절대값) — 화장품이 축을 지배해 소품목 급등이 안 보이는 문제(2026-08-29 피드백)

// 품목 → 관련 종목 매핑 (연동 논리 — 직결 상장사가 없으면 정직하게 표기)
const ITEM_MAP={
 '화장품(기초·색조)':'아모레퍼시픽·LG생활건강·코스맥스·한국콜마·실리콘투·브이티',
 '헤어 제품':'LG생활건강(닥터그루트)·아모레퍼시픽(려·라보에이치)',
 '향수':'직결 상장사 희소 — 코스맥스·한국콜마(ODM 일부), 니치 브랜드 다수 비상장',
 '방향제·퍼스널케어':'LG생활건강·애경산업(비편입) — 생활용품 부문',
 '미용기기(광범위)':'에이피알(뷰티 디바이스)·클래시스(미용 의료기기)',
 '라면(면류)':'삼양식품(불닭)·농심(신라면)',
 '소스류':'CJ제일제당(비비고)·대상(청정원)·삼양식품(불닭소스)',
 '김':'동원F&B·CJ씨푸드(비편입) — 조미김 수출',
 '당류과자':'오리온·롯데웰푸드(비편입)',
 '음료':'롯데칠성·LG생활건강(음료 부문)',
 '주류':'하이트진로(소주)·롯데칠성(처음처럼)',
 '가방·잡화':'F&F·더네이쳐홀딩스 — 브랜드 잡화',
 '선글라스·안경':'직결 상장사 희소 — 젠틀몬스터 등 주요 브랜드 비상장',
 '의류(편물+직물)':'영원무역(OEM 생산)·F&F·휠라홀딩스(브랜드)'};
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
  // 표시 모드: 지수(품목별 12M누적 첫 유효값=100 — 규모 무관 증감률 비교) / 절대값(천$)
  $('kc_mode').innerHTML=[['idx','지수 (시작=100)'],['abs','절대값 (천$)']].map(m=>
    `<button data-m="${m[0]}" style="margin-left:6px;padding:2px 10px;border-radius:12px;border:1px solid ${MODE===m[0]?'#334155':'#d6d9de'};background:${MODE===m[0]?'#334155':'#fff'};color:${MODE===m[0]?'#fff':'#333'};cursor:pointer;font-size:11.5px">${m[1]}</button>`).join('');
  $('kc_mode').querySelectorAll('button').forEach(b=>b.onclick=()=>{MODE=b.dataset.m;render();});
  if(ch1) ch1.destroy();
  // (2026-08-29 피드백) 12M 누적은 앞 11개월을 소모 — 빈 구간을 그리지 말고 실제 시작점(12번째 달)부터 축을 시작
  const i0=Math.min(11,Math.max(0,M.length-1));
  ch1=new Chart($('kc_cv1'),{type:'line',data:{labels:M.slice(i0),datasets:its.map((x,i)=>{
      const r=roll12(x.exp||[]).slice(i0);
      let data=r, abs=r;
      if(MODE==='idx'){ const base=r.find(v=>v!=null&&v>0); data=r.map(v=>(v!=null&&base)?+(v/base*100).toFixed(1):null); }
      // (2026-08-29 피드백) 선만으론 향수 371 같은 최종 지수 인지가 어렵다 — 범례에 최종값 병기 + 선 끝 점 강조
      const last=[...data].reverse().find(v=>v!=null);
      const lastIdx=data.length-1-[...data].reverse().findIndex(v=>v!=null);
      return {label:x.nm+(MODE==='idx'&&last!=null?' → '+Math.round(last):''),data:data,_abs:abs,
        borderColor:ITEM_COLORS[i%ITEM_COLORS.length],backgroundColor:ITEM_COLORS[i%ITEM_COLORS.length],
        pointRadius:data.map((_,j)=>j===lastIdx?3:0),borderWidth:1.7,spanGaps:true};})},
    options:{responsive:true,maintainAspectRatio:false,interaction:{mode:'index',intersect:false},
      plugins:{legend:{labels:{boxWidth:14,font:{size:11}}},
        tooltip:{itemSort:(a,b)=>(b.raw??-1e18)-(a.raw??-1e18),   // (2026-08-29 피드백) 팝업 값 높은 순
          callbacks:{label:c=>{const nm=c.dataset.label.replace(/ → -?\d+$/,'');   // 범례의 '→ 최종값' 중복 제거
            return MODE==='idx'?nm+' '+c.raw+' ('+nf(c.dataset._abs[c.dataIndex])+'천$)':nm+' '+nf(c.raw)+'천$';}}}},
      scales:{x:{ticks:{maxTicksLimit:12,font:{size:10}}},
        y:MODE==='idx'
          ?{ticks:{font:{size:10}},title:{display:true,text:'12개월 누적 지수 (시작월=100) — 규모 무관 증감률 비교',font:{size:10}}}
          :{ticks:{font:{size:10},callback:v=>(v/1000000).toFixed(1)+'십억$'},title:{display:true,text:'12개월 누적 수출(천$) — 계절성 제거 추세',font:{size:10}}}}}});

  const n=M.length-1;
  $('kc_tbl').innerHTML=`<table style="border-collapse:collapse;font-size:12.5px;background:#fff;width:100%">
    <thead><tr style="background:#f8fafc">${['품목군','최근월(천$)','전년동월比','12M누적(천$)','누적 YoY','관련 종목 (연동 경로)'].map(h=>`<th style="border:1px solid #e2e8f0;padding:4px 7px;font-size:11.5px">${h}</th>`).join('')}</tr></thead>
    <tbody>${[...its].sort((a,b)=>{   // (2026-08-29 피드백 2차) 차트(지수)와 같은 기준 — 3년 지수 높은 순(향수 맨 위)
      const g=x=>{const r=roll12(x.exp||[]);const b=r.find(v=>v!=null&&v>0);return (b&&r[n]!=null)?r[n]/b:-1e18;};
      return g(b)-g(a);}).map(x=>{
      const r=roll12(x.exp||[]);
      const ry=(r[n]!=null&&n>=12&&r[n-12])?((r[n]/r[n-12]-1)*100):null;
      const yo=yoy(x.exp||[],n);
      return `<tr><td style="border:1px solid #e2e8f0;padding:3px 7px;font-weight:600">${x.nm}<span style="font-size:10px;color:#94a3b8"> HS ${x.hs}</span></td>
      <td style="border:1px solid #e2e8f0;padding:3px 7px;text-align:right;font-weight:700">${nf(x.exp[n])}</td>
      <td style="border:1px solid #e2e8f0;padding:3px 7px;text-align:right;color:${pc(yo)}">${pf(yo)}</td>
      <td style="border:1px solid #e2e8f0;padding:3px 7px;text-align:right">${nf(r[n])}</td>
      <td style="border:1px solid #e2e8f0;padding:3px 7px;text-align:right;font-weight:700;color:${pc(ry)}">${pf(ry)}</td>
      <td style="border:1px solid #e2e8f0;padding:3px 7px;color:#334155;font-size:11.5px">${ITEM_MAP[x.nm]||x.note||''}</td></tr>`;}).join('')}</tbody></table>`;

  // ── ③ 연동 종목 표 (선택 테마) ────────────────────────────────────────
  const ST=(D.stocks||[]).filter(s=>s.th===TH);
  $('kc_stk').innerHTML=ST.length?`<table style="border-collapse:collapse;font-size:12.5px;background:#fff;width:100%">
    <thead><tr style="background:#f8fafc">${['종목','현재가','1일','1개월','3개월','1년','3년','수출 지표와의 연결'].map(h=>`<th style="border:1px solid #e2e8f0;padding:4px 7px;font-size:11.5px">${h}</th>`).join('')}</tr></thead>
    <tbody>${[...ST].sort((a,b)=>((b.y3??-1e18)-(a.y3??-1e18))).map(r=>`<tr>   <!-- (2026-08-29 피드백) 3년 수익률(차트 기준) 높은 순 -->
      <td style="border:1px solid #e2e8f0;padding:3px 7px;font-weight:700">${r.name}<span style="font-size:10.5px;color:#94a3b8"> ${r.sym.replace(/\.(KS|KQ)$/,'')}</span></td>
      <td style="border:1px solid #e2e8f0;padding:3px 7px;text-align:right">${nf(r.cur)}</td>
      ${['d1','m1','m3','y1','y3'].map(k=>`<td style="border:1px solid #e2e8f0;padding:3px 7px;text-align:right;color:${pc(r[k])};font-weight:${k==='y3'?'700':'400'}">${pf(r[k])}</td>`).join('')}
      <td style="border:1px solid #e2e8f0;padding:3px 7px;color:#475569;font-size:11.5px">${r.why||''}</td></tr>`).join('')}</tbody></table>`
    :'<div class="note">종목 없음</div>';

  // ── ④ 테마 수출 12M 누적 vs 대표주 상대주가 ──────────────────────────
  if(ch2) ch2.destroy();
  const spark=ST.filter(s=>s.spark&&s.spark.length);
  if(spark.length){
    // (2026-08-29 피드백) X축 날짜 표시 — spark_d(수집기 동봉 날짜)가 가장 긴 종목을 라벨 축으로 사용
    const ref=spark.reduce((a,b)=>((b.spark_d||[]).length>(a.spark_d||[]).length?b:a),spark[0]);
    const L=Math.max(...spark.map(s=>s.spark.length));
    const labels=(ref.spark_d&&ref.spark_d.length===L)?ref.spark_d:Array.from({length:L},(_,i)=>'');
    ch2=new Chart($('kc_cv2'),{type:'line',data:{labels:labels,
      datasets:spark.map((s,i)=>{const b=s.spark[0]||1;
        return {label:s.name,data:s.spark.map(v=>+(v/b*100).toFixed(1)),
          borderColor:ITEM_COLORS[i%ITEM_COLORS.length],backgroundColor:'transparent',pointRadius:0,borderWidth:1.4,spanGaps:true};})},
      options:{responsive:true,maintainAspectRatio:false,interaction:{mode:'index',intersect:false},
        plugins:{legend:{labels:{boxWidth:13,font:{size:10.5}}},tooltip:{itemSort:(a,b)=>(b.raw??-1e18)-(a.raw??-1e18),callbacks:{label:c=>c.dataset.label+' '+c.raw}}},
        scales:{x:{ticks:{maxTicksLimit:13,font:{size:10},maxRotation:0}},y:{ticks:{font:{size:10}},title:{display:true,text:TH+' 연동 종목 상대주가 (3년 전=100 — 수출 지수와 동일 시점)',font:{size:10}}}}}});
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
