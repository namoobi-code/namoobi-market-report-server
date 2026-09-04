/* share.js — 📊 점유율 추이(Share Watch) 탭 (2026-08-31 신설)
   데이터: /api/db/share (scripts/fetch_share.py · 매일 06:35) + /api/db/moat (B2 구도)
   목적: '점유율만 잘 추적하면 주가가 보이는 대결'(릴리vs노보 원형)을 경쟁사 동시 비교로 —
        배틀마다 전 플레이어를 한 차트에 겹쳐 추이·격차를 보여주고, 리더-2위 스프레드를 산출한다.
   갱신: 자동(아마존·HBM=일일) / 나머지는 보고서 실행 Phase 3.7 이 stale 배틀만 웹서치 갱신. */
(function(){
'use strict';
let D=null, M=null, GR='all', charts={};
const $=id=>document.getElementById(id);
const COLS=['#be185d','#0ea5e9','#b45309','#7c3aed','#0f766e','#e11d48','#4f46e5','#ca8a04','#334155','#16a34a'];
// (2026-09-04) 회사별 고정 색상 — 인덱스 순 배정이면 같은 회사가 카드마다 다른 색이 돼
//   (예: 삼성전자가 D램 카드에선 파랑, HBM 카드에선 하늘색) 카드 간 비교가 어긋난다.
//   키가 이름에 '포함'되면 매칭하므로 '삼성 파운드리'·'엔비디아 데이터센터' 같은 변형도 같은 색으로 묶인다.
const CO_COLOR={
  '삼성':'#0ea5e9','SK하이닉스':'#be185d','마이크론':'#b45309','CXMT':'#7c3aed','난야':'#0f766e',
  '엔비디아':'#166534','GPU(엔비디아)':'#166534','AMD':'#e11d48','브로드컴':'#4f46e5','커스텀 ASIC':'#4f46e5',
  'TSMC':'#be185d','SMIC':'#ca8a04','Amkor':'#0f766e','어드밴테스트':'#4f46e5','테라다인':'#ca8a04',
  '무라타':'#7c3aed','삼성전기':'#0ea5e9',
  'AWS':'#b45309','Azure':'#0ea5e9','GCP':'#16a34a',
  '릴리':'#be185d','노보':'#0ea5e9','다케다':'#4f46e5','알케르메스':'#ca8a04',
  'CATL':'#be185d','LG엔솔':'#0ea5e9','삼성SDI':'#7c3aed','BYD':'#16a34a','EVE':'#b45309',
  '테슬라':'#e11d48','현대차그룹':'#0f766e','GM':'#ca8a04','포드':'#4f46e5','지리':'#7c3aed',
  '립모터':'#0ea5e9','창안':'#b45309','우링':'#334155','하이시움':'#334155','니오':'#16a34a','샤오펑':'#ca8a04',
  'HD현대일렉트릭':'#be185d','효성중공업':'#0ea5e9','센트러스':'#b45309','스페이스X':'#4f46e5','로켓랩':'#ca8a04',
  '삼성바이오':'#0ea5e9','론자':'#b45309','우시바이오':'#e11d48','베링거':'#7c3aed',
  '1위 고객':'#be185d','2위 고객':'#0ea5e9','3위 고객':'#b45309','4위 고객':'#7c3aed'};
function colorOf(name,i){
  const n=String(name||'');
  // 긴 키 우선 매칭 — 'SK하이닉스'가 '삼성'보다 먼저 걸리도록
  const keys=Object.keys(CO_COLOR).sort((a,b)=>b.length-a.length);
  for(const k of keys) if(n.indexOf(k)>=0) return CO_COLOR[k];
  return COLS[i%COLS.length];
}
const GB={'A':['#166534','#dcfce7','A급 — 월간·주간 공개 데이터'],'B':['#1d4ed8','#dbeafe','B급 — 분기·반기(보고서 실행 시 자동 갱신)'],'C':['#7c3aed','#ede9fe','C급 — 캐파(증설) 시계열: 수요 초과 시장에서 캐파가 곧 미래 매출']};

function latestGap(b){
  // 리더-2위 격차와 직전 관측 대비 변화 — '역전 진행'을 한 줄로
  const s=b.series; if(!s||!s.length) return null;
  const cur=s[s.length-1].v, ks=Object.keys(cur).filter(k=>cur[k]!=null);
  if(ks.length<2) return null;
  const sorted=[...ks].sort((a,c)=>(b.unit==='위'?(cur[a]-cur[c]):(cur[c]-cur[a])));
  const lead=sorted[0], second=sorted[1];
  const gap=+(Math.abs(cur[lead]-cur[second])).toFixed(1);
  let dgap=null;
  for(let i=s.length-2;i>=0;i--){
    const p=s[i].v;
    if(p[lead]!=null&&p[second]!=null){ dgap=+(gap-Math.abs(p[lead]-p[second])).toFixed(1); break; }
  }
  return {lead,second,gap,dgap};
}

function render(){
  if(!D) return;
  $('sh_asof').textContent='기준 '+(D.as_of||'')+' · 서버 매일 06:35'+(D.llm_asof?` · 🧠 최근 보고서 갱신 ${D.llm_asof}`:'');
  const bs=(D.battles||[]).filter(b=>GR==='all'||b.grade===GR);
  $('sh_chips').innerHTML=[['all','전체'],['A','A급(고빈도)'],['B','B급(분기)'],['C','C급(캐파)']].map(g=>
    `<button data-g="${g[0]}" style="margin-right:6px;padding:3px 12px;border-radius:14px;border:1px solid ${GR===g[0]?'#334155':'#d6d9de'};background:${GR===g[0]?'#334155':'#fff'};color:${GR===g[0]?'#fff':'#333'};cursor:pointer;font-size:12.5px">${g[1]}</button>`).join('');
  $('sh_chips').querySelectorAll('button').forEach(x=>x.onclick=()=>{GR=x.dataset.g;render();});

  Object.values(charts).forEach(c=>{try{c.destroy();}catch(e){}}); charts={};
  $('sh_grid').innerHTML=bs.map(b=>{
    const g=GB[b.grade]||GB.B;
    const gap=latestGap(b);
    const ks=(b.players&&b.players.length)?b.players.map(p=>p.k)
            :[...new Set(b.series.flatMap(s=>Object.keys(s.v)))];
    // 시점별 전원 비교 표 (최근 5시점, 최신이 위)
    const recent=[...b.series].slice(-5).reverse();
    const tbl=recent.length?`<table style="border-collapse:collapse;font-size:11.5px;background:#fff;width:100%;margin-top:8px">
      <thead><tr style="background:#f8fafc"><th style="border:1px solid #e2e8f0;padding:3px 6px">시점</th>${ks.map(k=>`<th style="border:1px solid #e2e8f0;padding:3px 6px">${k}</th>`).join('')}<th style="border:1px solid #e2e8f0;padding:3px 6px">비고</th></tr></thead>
      <tbody>${recent.map(s=>`<tr><td style="border:1px solid #e2e8f0;padding:2px 6px;white-space:nowrap">${s.d}</td>
        ${ks.map(k=>`<td style="border:1px solid #e2e8f0;padding:2px 6px;text-align:right;font-weight:${s.v[k]!=null?600:400}">${s.v[k]!=null?s.v[k]+(b.unit==='위'?'위':b.unit):'—'}</td>`).join('')}
        <td style="border:1px solid #e2e8f0;padding:2px 6px;color:#94a3b8;font-size:10.5px">${s.note||''}${s.src?` <a href="${s.src}" target="_blank" rel="noopener" style="color:#94a3b8">[근거]</a>`:''}</td></tr>`).join('')}</tbody></table>`:'';
    return `<div style="flex:1 1 480px;max-width:640px;border:1px solid #e2e8f0;border-top:3px solid ${g[0]};border-radius:10px;background:#fff;padding:12px 14px">
      <div style="display:flex;justify-content:space-between;align-items:center;gap:6px">
        <b style="font-size:13.5px">${b.name}</b>
        <span style="white-space:nowrap"><span title="${g[2]}" style="background:${g[1]};color:${g[0]};border-radius:9px;padding:1px 8px;font-size:11px;font-weight:700">${b.grade}급 · ${b.freq}</span>
        ${b.auto?'<span style="background:#dcfce7;color:#166534;border-radius:9px;padding:1px 8px;font-size:11px;margin-left:3px">매일 자동</span>':(b.stale?'<span style="background:#fef3c7;color:#b45309;border-radius:9px;padding:1px 8px;font-size:11px;margin-left:3px">⏳ 다음 보고서 갱신</span>':'<span style="background:#f1f5f9;color:#475569;border-radius:9px;padding:1px 8px;font-size:11px;margin-left:3px">최신</span>')}</span></div>
      <div style="font-size:11px;color:#64748b;margin:3px 0 6px">${b.why}</div>
      ${gap?`<div style="font-size:11.5px;margin-bottom:4px">⚔️ <b>${gap.lead}</b> 리드 — 2위 ${gap.second}와 격차 <b>${gap.gap}${b.unit==='위'?'위':b.unit}</b>${gap.dgap!=null?` (직전 관측 대비 <b style="color:${gap.dgap>0?'#166534':gap.dgap<0?'#b91c1c':'#64748b'}">${gap.dgap>0?'확대 +':gap.dgap<0?'축소 ':''}${gap.dgap}</b>)`:''} ${gap.dgap!=null&&gap.dgap<0?'— <b style="color:#b91c1c">역전 방향 진행</b>':''}</div>`:''}
      <div style="height:210px"><canvas id="sh_cv_${b.id}"></canvas></div>
      ${tbl}
      <div style="font-size:10.5px;color:#94a3b8;margin-top:5px">관련 종목: ${(b.players||[]).map(p=>p.stock?`${p.k}(${p.stock})`:p.k).join(' · ')||'—'} · 출처: ${b.src} · (E)=기관 추정치</div>
    </div>`;}).join('');

  // 차트 — 전 플레이어 동시 라인 + 값 높은 순 툴팁
  bs.forEach(b=>{
    const el=$('sh_cv_'+b.id); if(!el||!b.series.length) return;
    const ks=(b.players&&b.players.length)?b.players.map(p=>p.k)
            :[...new Set(b.series.flatMap(s=>Object.keys(s.v)))];
    charts[b.id]=new Chart(el,{type:'line',data:{labels:b.series.map(s=>s.d),
      datasets:ks.map((k,i)=>({label:k,data:b.series.map(s=>s.v[k]??null),
        borderColor:colorOf(k,i),backgroundColor:colorOf(k,i),
        pointRadius:3,borderWidth:1.8,spanGaps:true}))},
      options:{responsive:true,maintainAspectRatio:false,interaction:{mode:'index',intersect:false},
        plugins:{legend:{labels:{boxWidth:13,font:{size:10.5}}},
          tooltip:{itemSort:(a,c)=>(c.raw??-1e18)-(a.raw??-1e18),callbacks:{label:c=>c.dataset.label+' '+c.raw+(b.unit==='위'?'위':b.unit)}}},
        scales:{x:{ticks:{maxTicksLimit:10,font:{size:9.5}}},
          y:{reverse:(b.unit==='위'),min:(b.unit==='단계'?0:undefined),max:(b.unit==='단계'?8:undefined),
             ticks:{stepSize:(b.unit==='단계'?1:undefined),font:{size:10}},
             title:{display:true,text:b.unit==='위'?'랭크(낮을수록 상위)':(b.unit==='단계'?'개발 단계 (1 Ph1 → 8 다국가 승인)':b.unit),font:{size:10}}}}}});
  });

  // B2 점유 구도 표 (moat.json SHARES — Phase 3.6 이 점검·갱신 제안)
  if(M){
    const b2=(M.rows||[]).filter(r=>r.share);
    $('sh_b2').innerHTML=b2.length?`<table style="border-collapse:collapse;font-size:12px;background:#fff;width:100%">
      <thead><tr style="background:#f8fafc">${['종목','분야','점유 구도(경쟁사 대비)','판정'].map(h=>`<th style="border:1px solid #e2e8f0;padding:4px 7px">${h}</th>`).join('')}</tr></thead>
      <tbody>${b2.map(r=>`<tr>
        <td style="border:1px solid #e2e8f0;padding:3px 7px;font-weight:700;white-space:nowrap">${r.name}</td>
        <td style="border:1px solid #e2e8f0;padding:3px 7px;text-align:center;white-space:nowrap"><span style="background:#eef2ff;color:#4338ca;border-radius:8px;padding:1px 7px;font-size:11px">${r.sec}</span></td>
        <td style="border:1px solid #e2e8f0;padding:3px 7px;color:#334155">${r.share}</td>
        <td style="border:1px solid #e2e8f0;padding:3px 7px;text-align:center;white-space:nowrap">${{buy:'🟢',buy_m:'🟢※',risk:'🔴',watch:'🟡',top:'⚪',top_hot:'⚪🔥',top_warn:'⚪⚠'}[r.verdict]||''}</td></tr>`).join('')}</tbody></table>`
      :'<div class="note">데이터 없음</div>';
  }
}

function load(force){
  if(D&&!force){ render(); return; }
  $('sh_asof').textContent='불러오는 중…';
  Promise.all([
    fetch('/api/db/share',{cache:'no-cache'}).then(r=>{if(!r.ok)throw new Error('HTTP '+r.status);return r.json();}),
    fetch('/api/db/moat',{cache:'no-cache'}).then(r=>r.ok?r.json():null).catch(()=>null)
  ]).then(([s,m])=>{ D=s; M=m; render(); })
  .catch(e=>{ $('sh_asof').textContent='로드 실패: '+e.message+' (서버 수집 전이면 06:35 이후 표시)'; });
}

window.renderShare=function(){ load(false); };
document.addEventListener('DOMContentLoaded',function(){
  const b=$('sh_reload'); if(b) b.onclick=()=>load(true);
});
})();
