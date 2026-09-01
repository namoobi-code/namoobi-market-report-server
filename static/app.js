const $=id=>document.getElementById(id);
const esc=s=>String(s??'').replace(/[<>&]/g,c=>({'<':'&lt;','>':'&gt;','&':'&amp;'}[c]));
/* (2026-08-10) 가이던스 비교 기간 라벨 — 우선순위 ①진행분기 ②다음분기 ③올해(FY) ④내년(FY).
   상세표·캘린더 팝업·차트 팝업이 **같은 라벨**을 쓰도록 전역 공용으로 둔다. */
function _GPER(p){ return ({'0q':'진행분기','+1q':'다음분기','0y':'올해(FY)','+1y':'내년(FY)'})[p]||'해당분기'; }

/* ══════════════════════════════════════════════════════════════════
   대시보드 자동 새로고침 — 켜둔 화면에 서버 갱신(cron·장중 증분)을 자동 반영. (2026-07-17 도입 → 07-19 재구성 때 유실 → 07-26 복원)
   무작정 reload 하면 조작을 끊으므로: 탭 보이는 중 + 최근 60초 무조작 + 필터 팝오버 안 열림 일 때만.
   스크리너·ETF·수급 패널은 자체 5분/10분 폴링으로 이미 실시간 → 그 화면에선 reload 생략(조작 보호).
   활성 탭/화면은 sessionStorage 로 저장·복원. ══════════════════════════════════════════════════════════════════ */
(function(){
  const REFRESH_MIN=10, IDLE_MS=60*1000;
  let lastAct=Date.now();
  ['mousemove','keydown','click','scroll','touchstart','input'].forEach(ev=>
    document.addEventListener(ev,()=>{lastAct=Date.now();},{passive:true,capture:true}));
  // 복원
  try{ const v=sessionStorage.getItem('nmr_view');
    if(v){ sessionStorage.removeItem('nmr_view');
      setTimeout(()=>{ if(v==='screener'){const b=document.getElementById('btn_screener'); if(b)b.click();}
        else{const t=document.querySelector('.tab[data-pane="'+v+'"]'); if(t)t.click();} },500); }
  }catch(e){}
  function curView(){
    const sb=document.getElementById('btn_screener');
    if(sb&&sb.classList.contains('on')) return 'screener';
    const t=document.querySelector('.tab.on'); return (t&&t.dataset.pane)||'p_db';
  }
  setInterval(()=>{
    if(document.visibilityState!=='visible') return;          // 백그라운드 탭
    if(Date.now()-lastAct<IDLE_MS) return;                    // 조작 중
    if(document.querySelector('.fpop.open, .fpop.open, #scr_colpanel[style*="block"], #etf_colpanel:not([style*="none"])')) return; // 패널 조작 중
    const v=curView();
    // 스크리너·ETF 는 자체 폴링으로 실시간 → 전체 reload 생략(필터·정렬·컬럼 보존)
    if(v==='screener'||v==='p_etf') return;
    try{ sessionStorage.setItem('nmr_view',v); }catch(e){}
    location.reload();
  }, REFRESH_MIN*60*1000);
})();
const C={r:'#d64545',b:'#2f6fd0',g:'#1e9e6a',o:'#e08c1a',p:'#8358c4',k:'#16191d',gy:'#9aa3ad'};
// 17개국용 서로 다른 색
const PAL=['#d64545','#2f6fd0','#1e9e6a','#e08c1a','#8358c4','#0d9488','#be185d','#65a30d',
           '#c2410c','#0369a1','#7c3aed','#b45309','#15803d','#9f1239','#1d4ed8','#4d7c0f','#a16207'];

// 우측 끝 라벨 플러그인 (보고서 CLI 차트와 동일)
const rightLabels={id:'rightLabels',afterDatasetsDraw(ch){
  const ctx=ch.ctx, area=ch.chartArea;
  // 1) 각 시리즈의 마지막 점 수집
  const items=[];
  ch.data.datasets.forEach((ds,i)=>{
    const meta=ch.getDatasetMeta(i); if(meta.hidden) return;
    for(let j=ds.data.length-1;j>=0;j--){
      if(ds.data[j]!=null && meta.data[j]){
        items.push({y:meta.data[j].y, x:meta.data[j].x, v:ds.data[j],
                    lab:ds.label, c:ds.borderColor, bold:ds.borderWidth>=2.5});
        break;
      }
    }
  });
  if(!items.length) return;
  // 2) 겹침 방지 — y 정렬 후 최소간격 확보 (한 번 아래로, 한 번 위로 밀며 수렴)
  const H=area.bottom-area.top;
  const GAP=Math.max(9, Math.min(13, H/(items.length+1)));   // 높이에 맞춰 간격 자동
  items.sort((a,b)=>a.y-b.y);
  items.forEach(it=>it.ly=it.y);
  // 위→아래 밀기
  for(let i=1;i<items.length;i++)
    if(items[i].ly-items[i-1].ly<GAP) items[i].ly=items[i-1].ly+GAP;
  // 아래로 넘치면 아래→위로 되밀기
  if(items[items.length-1].ly > area.bottom){
    items[items.length-1].ly = area.bottom;
    for(let i=items.length-2;i>=0;i--)
      if(items[i+1].ly-items[i].ly<GAP) items[i].ly=items[i+1].ly-GAP;
  }
  // 최종 클램프 (영역 밖으로 나가지 않게)
  items.forEach(it=>{ it.ly=Math.max(area.top+2, Math.min(area.bottom-2, it.ly)); });
  // 3) 라벨 + 연결선 그리기
  ctx.save();
  items.forEach(it=>{
    const lx = area.right + 8;
    if(Math.abs(it.ly-it.y) > 2){          // 밀려난 만큼 얇은 지시선
      ctx.strokeStyle=it.c; ctx.globalAlpha=.45; ctx.lineWidth=.9;
      ctx.beginPath(); ctx.moveTo(it.x+2,it.y); ctx.lineTo(lx-2,it.ly); ctx.stroke();
      ctx.globalAlpha=1;
    }
    ctx.fillStyle=it.c;
    ctx.font=(it.bold?'700 ':'')+'10.5px -apple-system,sans-serif';
    ctx.textBaseline='middle';
    ctx.fillText(`${it.lab} ${Number(it.v).toFixed(1)}`, lx, it.ly);
  });
  ctx.restore();
}};

function mk(el,labels,sets,o={}){
  if(!el||!labels?.length) return;
  const bar=o.bar;
  new Chart(el,{type:bar?'bar':'line',
    data:{labels,datasets:sets.map(s=>({label:s.n,data:s.d,borderColor:s.c,
      backgroundColor:(bar&&!s.dash)?s.c:(s.bg||s.c),
      type:(bar&&s.dash)?'line':undefined,
      borderWidth:s.w||1.7,pointRadius:s.pt||0,tension:.15,
      fill:s.dash?false:(s.fill??false),borderDash:s.dash||[],spanGaps:true}))},
    plugins:o.right?[rightLabels]:[],
    options:{responsive:true,maintainAspectRatio:false,animation:false,
      layout:{padding:{right:o.right?140:4}},
      interaction:{intersect:false,mode:'index'},
      plugins:{legend:{display:o.legend??false,position:o.legendPos||'top',
        labels:{boxWidth:10,boxHeight:2,font:{size:10},padding:7}},
        annotation:undefined},
      scales:{x:{ticks:{maxTicksLimit:o.xt||7,font:{size:9.5}},grid:{display:false},stacked:o.stack},
              y:{beginAtZero:o.y0,ticks:{font:{size:9.5}},grid:{color:'#eef0f3'},stacked:o.stack}}}});
}
const S=(b,n)=>b[n]?.data||[];
const L=a=>a.map(x=>x[0]), V=a=>a.map(x=>x[1]);

function mixfix(rows,thr,conv){const out=[];let prev=null;
  for(const [d,v] of rows){ if(v==null) continue;
    if(Math.abs(v)>thr){ if(prev!=null) out.push([d,conv(prev,v)]); prev=v; }
    else { out.push([d,v]); prev=null; } }
  return out;}
const fixNfp=r=>mixfix(r,5000,(a,b)=>+(b-a).toFixed(1));
const fixRetail=r=>mixfix(r,50,(a,b)=>+((b/a-1)*100).toFixed(2));
const fixJobless=r=>r.filter(x=>x[1]!=null).map(([d,v])=>[d,Math.abs(v)>10000?+(v/10000).toFixed(1):v]).slice(-52);
function fixGdp(r,ann){let g=r.filter(x=>x[1]!=null&&Math.abs(x[1])<50);
  if(g.length<2&&ann?.length) g=ann.filter(x=>x[1]!=null&&Math.abs(x[1])<50);
  const o=[];for(const x of g){if(!o.length||x[1]!==o[o.length-1][1])o.push(x);} return o.slice(-8);}

(async()=>{
  const [b,rd,pr,rs,h] = await Promise.all([
    /* (2026-08-14) cache:'no-cache' — 브라우저가 디스크 캐시본을 조용히 재사용해
       한 달 전 CPI 가 표시된 사고가 있었다. 서버 재검증을 강제하되 304 는 그대로 살려
       변경 없으면 40MB 를 다시 받지 않는다. */
    fetch('/api/bundle',{cache:'no-cache'}).then(r=>r.json()),
    fetch('/api/report').then(r=>r.ok?r.json():null).catch(()=>null),
    fetch('/api/policyrates').then(r=>r.ok?r.json():null).catch(()=>null),
    fetch('/api/reports').then(r=>r.json()),
    fetch('/api/health').then(r=>r.json()),
  ]);
  const M = rd?.markets || {};

  $('meta').innerHTML=`최신 리포트 <b>${esc(rs[0]?.datetime||'—')}</b>`;
  // (2026-07-12) 앱셸 — 헤더·좌측(아카이브·APK·DB인벤토리)·nav 는 고정, 본문(.mainc)만 스크롤.
  //   좌측 항목(보고서·DB)은 항상 보이므로 nav 에서 뺀다 — nav 는 본문 섹션 점프 전용.
  $('nav').innerHTML=[
    ['s311','3.1.1 금리'],['s333','3.1.1 HY'],['s312','3.1.2 물가'],['s313','3.1.3 고용'],['s314','3.1.4 OECD CLI'],
    ['s315','3.1.5 경기선행'],['d316','3.1.6 FactSet'],['s318','3.1.8 CAPEX'],['s319','3.1.9 HBM'],['s3110','3.1.10 수출'],
    ['s3111','3.1.11 반도체'],['s3113','3.1.13 파생'],['s3114','3.1.14 유동성'],['s_veps','3.1.15 선행지표'],['s_appe','부록E 피지컬AI'],['d332','3.3.2 리밸런싱'],['s32','3.2 KRX'],['d6','6 크립토'],['s78','7.8 네이버'],
    ['sberk','버크셔']]
    .map(([i,t])=>`<a href="#${i}" data-go="${i}">${t}</a>`).join('');
  // 앵커 클릭: 본문 컨테이너 내부 스크롤 (URL 해시 오염 없이)
  document.querySelectorAll('nav a[data-go]').forEach(a=>a.addEventListener('click',e=>{
    const el=document.getElementById(a.dataset.go);
    if(el){ e.preventDefault(); el.scrollIntoView({behavior:'smooth',block:'start'}); }
  }));

  /* ── 3.1.1 금리·통화정책 ── */
  $('rates').innerHTML=(b.policy_rates?.data||[]).map(r=>`<div class="card">
    <div class="k">${esc(r.country)}</div><div class="v">${esc(r.rate)}</div>
    <div class="s">${esc(r.asof)} · ${esc((r.note||'').slice(0,54))}</div></div>`).join('');

  if(pr?.series){
    const all=[...new Set(Object.values(pr.series).flat().map(x=>x[0]))].sort();
    const ds=Object.entries(pr.series).map(([n,v],i)=>{
      const m=Object.fromEntries(v);
      let last=null;
      return {n, c:PAL[i], w:2, d:all.map(d=>{ if(m[d]!=null) last=m[d]; return last; })};
    });
    mk($('c_pol'),all,ds,{legend:true,right:true,xt:8});
  }

  /* (2차 req4 2026-07-18) 점도표 — 6월 vs 3월 변화값 컬럼 추가 (docx와 동일) */
  const dp=b.dot_plot?.data;
  if(dp?.rows) $('dot').innerHTML=`<tr><th>시점</th><th style="text-align:right">6월</th><th style="text-align:right">3월</th><th style="text-align:right">변화</th><th>비고</th></tr>`+
    dp.rows.map(r=>{
      const f=x=>parseFloat(String(x).replace(/[^0-9.\-]/g,''));
      const j=f(r.jun), m2=f(r.mar);
      const d2=(isFinite(j)&&isFinite(m2))?(j-m2):null;
      const ch=d2==null?'—':(Math.abs(d2)<0.001?'동일':(d2>0?'+':'')+d2.toFixed(2).replace(/0+$/,'').replace(/\.$/,'')+'%p');
      return `<tr><td><b>${esc(r.year)}</b></td><td class="num">${esc(r.jun)}</td>
      <td class="num note">${esc(r.mar)}</td>
      <td class="num ${d2>0?'up':d2<0?'dn':'note'}">${ch}</td>
      <td class="note">${esc((r.note||'').slice(0,58))}</td></tr>`;}).join('');
  /* (req2 2026-07-18) FOMC 일정 — 이틀 회의('07-28~29'와 '07-29')가 두 줄로 들어와도
     종료일 기준으로 1건으로 합치고(설명 긴 쪽 유지), 미래 3건 + 과거 5건만 보인다 */
  const fm=b.fomc_meetings?.data;
  if(fm){
    const uniq={};
    fm.forEach(r=>{
      const end=(r.date||'').includes('~')
        ? r.date.slice(0,8)+r.date.split('~').pop()   // '2025-07-29~30' → '2025-07-30'
        : r.date;
      if(!uniq[end] || (r.note||'').length>(uniq[end].note||'').length)
        uniq[end]={...r, date:end, range:(r.date||'').includes('~')?r.date:uniq[end]?.range};
    });
    const rows=Object.values(uniq).sort((a,b2)=>a.date<b2.date?1:-1);   // 최신순
    const today=new Date().toISOString().slice(0,10);
    const fut=rows.filter(r=>r.date>=today).slice(-3);                  // 가까운 미래 3
    const past=rows.filter(r=>r.date<today).slice(0,5);                 // 최근 과거 5
    $('fomc').innerHTML=`<tr><th>일자</th><th>상태</th><th>비고</th></tr>`+
      [...fut,...past].map(r=>`<tr${r.date>=today?' style="background:#f0f7ff"':''}>
        <td><b>${esc(r.range||r.date)}</b></td><td>${esc(r.stance)}</td>
        <td class="note">${esc(r.note)}</td></tr>`).join('');
  }

  const t10=S(b,'series_us10y_daily'), t2=S(b,'series_us2y_daily'), sp=S(b,'series_curve_10_2');
  mk($('c_ust'),L(t10),[{n:'10년물',d:V(t10),c:C.r},{n:'2년물',d:V(t2),c:C.b}],{legend:true});
  mk($('c_spread'),L(sp),[{n:'10Y−2Y',d:V(sp),c:C.p,fill:true,bg:'rgba(131,88,196,.08)'}]);
  /* (2차 req1 2026-07-18) 현재값을 차트 위 텍스트로 — 값은 차트와 같은 시계열의 마지막 점이라 항상 일치 */
  {const lv=a=>{const v=V(a);return v.length?v[v.length-1]:null;};
   const s10=lv(t10), s2=lv(t2), spv=lv(sp);
   const el=$('spread_now');
   if(el&&spv!=null) el.innerHTML=`현재 <b>${spv>0?'+':''}${spv.toFixed(2)}%p</b> → ${
     spv>0?'정상(양전환)':'역전(경기침체 신호)'}${s10!=null&&s2!=null?` <span class="note">(10Y=${s10.toFixed(2)}% · 2Y=${s2.toFixed(2)}%)</span>`:''}`;
   const eu=$('ust_now');
   if(eu&&s10!=null) eu.innerHTML=`10년물 <b>${s10.toFixed(2)}%</b> · 2년물 <b>${s2!=null?s2.toFixed(2):'—'}%</b>`;}

  /* ── 3.1.2 물가 ── (2차 req5 2026-07-18) docx 표와 동일 컬럼: 지표·YoY·MoM·기준월·발표날짜·의미·시장영향·예상영향 */
  /* (2026-08-14) 표 옆에 데이터 기준일(as_of) 표시 — 화면이 옛 값을 들고 있으면
     여기서 바로 드러난다. 값만 보고는 언제 것인지 알 수 없었다. */
  {const _ia=$('infl_asof'); if(_ia) _ia.textContent=b.inflation?.as_of?`데이터 기준 ${b.inflation.as_of}`:'';}
  $('infl').innerHTML=`<tr><th>지표</th><th style="text-align:right">최신값 YoY</th><th style="text-align:right">최신값 MoM</th>
    <th>기준월</th><th>발표날짜</th><th>의미</th><th>시장영향</th><th>예상영향</th></tr>`+(b.inflation?.data||[]).map(r=>`<tr>
    <td><b>${esc(r.name)}</b></td><td class="num up">${r.yoy!=null?(r.yoy>0?'+':'')+r.yoy+'%':'—'}</td>
    <td class="num ${r.mom>0?'up':'dn'}">${r.mom!=null?(r.mom>0?'+':'')+r.mom+'%':'—'}</td>
    <td class="note">${esc(r.asof)}</td><td class="note">${esc(r.release||'')}</td>
    <td class="note">${esc(r.meaning||'')}</td><td class="note">${esc(r.impact||'')}</td>
    <td class="note">${esc(r.interp)}</td></tr>`).join('');
  const ic=S(b,'series_infl_CPI'),icc=S(b,'series_infl_Core_CPI'),ip=S(b,'series_infl_PCE'),
        ipc=S(b,'series_infl_Core_PCE'),ippi=S(b,'series_infl_PPI');
  mk($('c_infl'),L(ic),[{n:'CPI',d:V(ic),c:C.r},{n:'Core CPI',d:V(icc),c:C.o},{n:'PCE',d:V(ip),c:C.b},
    {n:'Core PCE',d:V(ipc),c:C.g},{n:'PPI',d:V(ippi),c:C.gy}],{legend:true});
  const bei=S(b,'series_infl_exp');
  mk($('c_bei'),L(bei),[{n:'BEI',d:V(bei),c:C.p}]);
  /* (req7 2026-07-19) BEI 현재값 텍스트 표시 — 차트 컨테이너 바로 위에 최신값·기준일 캡션 */
  try{ const bv=V(bei), bl=L(bei), be=$('c_bei');
    if(be&&bv&&bv.length){ let cap=document.getElementById('bei_now');
      if(!cap){ cap=document.createElement('div'); cap.id='bei_now'; cap.className='note';
        cap.style.cssText='margin:2px 0 4px;font-weight:600'; be.parentNode.insertBefore(cap,be); }
      cap.innerHTML=`현재 <b>${(+bv[bv.length-1]).toFixed(2)}%</b> <span style="font-weight:400">(${esc(bl[bl.length-1]||'')} 기준 · 10Y BEI 실시간)</span>`; } }catch(e){}

  /* ── 3.1.3 고용 ── (req3 2026-07-18) docx 표와 동일 컬럼: 지표·최신수치·기준·발표일자·의미·시장영향·예상영향 */
  $('emp').innerHTML=`<tr><th>지표</th><th style="text-align:right">최신 수치</th><th>기준</th><th>발표일자</th>
    <th>의미</th><th>시장영향</th><th>예상영향</th></tr>`+
    (b.employment?.data||[]).map(r=>`<tr><td><b>${esc(r.name)}</b></td><td class="num">${esc(r.value)}</td>
    <td class="note">${esc(r.asof)}</td><td class="note">${esc(r.release||'')}</td>
    <td class="note">${esc(r.meaning||'')}${r.freq?' · '+esc(r.freq):''}</td>
    <td class="note">${esc(r.impact||'')}</td><td class="note">${esc(r.interp)}</td></tr>`).join('');
  const jb=fixJobless(S(b,'series_emp_jobless')), un=S(b,'series_emp_unemp').slice(-24),
        nf=fixNfp(S(b,'series_emp_nfp')).slice(-24), rt=fixRetail(S(b,'series_emp_retail')).slice(-24),
        im=S(b,'series_emp_ism_mfg').slice(-24), iv=S(b,'series_emp_ism_svc').slice(-24),
        gd=fixGdp(S(b,'series_emp_gdp'),S(b,'series_emp_gdp_ann'));
  const nfM=S(b,'series_emp_nfp_mom'), rtM=S(b,'series_emp_retail_mom');
  const align=(base,src)=>{const m=Object.fromEntries(src);return base.map(([d])=>m[d]??null);};
  mk($('c_jobless'),L(jb),[{n:'청구',d:V(jb),c:C.r}]);
  mk($('c_unemp'),L(un),[{n:'실업률',d:V(un),c:C.o}]);
  mk($('c_nfp'),L(nf),[{n:'NFP',d:V(nf),c:C.b},{n:'원본 MoM',d:align(nf,nfM),c:C.k,dash:[4,3]}],{bar:true,legend:true});
  mk($('c_retail'),L(rt),[{n:'소매판매',d:V(rt),c:C.g},{n:'원본 MoM',d:align(rt,rtM),c:C.k,dash:[4,3]}],{bar:true,legend:true});
  mk($('c_ism'),L(im),[{n:'제조업',d:V(im),c:C.r},{n:'서비스',d:V(iv),c:C.b}],{legend:true});
  mk($('c_gdp'),L(gd),[{n:'GDP 연율',d:V(gd),c:C.p}],{bar:true});

  /* ── 3.1.4 OECD CLI (확대·국가별 색·우측 라벨) ── */
  const cl=b.oecd_cli?.data;
  if(cl){
    const ds=Object.entries(cl.series).map(([n,v],i)=>{
      const kr=n==='대한민국';
      return {n,d:v,c:PAL[i%PAL.length],w:kr?3.2:1.3};
    });
    mk($('c_cli'),cl.months,ds,{right:true,xt:10});
    $('cli_src').innerHTML=`출처: ${esc(cl.source)} · 자료갱신 ${esc(cl.data_downloaded||b.oecd_cli.as_of)} · 대한민국 굵은 선`;
  }

  /* ── 3.1.5 경기선행지수 (한국) ── */
  const kl=(M.korea_leading||b.leading?.data||[]);
  if(kl.length){
    $('lead').innerHTML=`<tr><th>시점</th><th style="text-align:right">지수</th><th style="text-align:right">전월비</th></tr>`+
      kl.map(r=>`<tr><td>${esc(r.period)}</td><td class="num">${esc(r.value)}</td>
      <td class="num ${String(r.mom).startsWith('+')?'up':'dn'}">${esc(r.mom)}</td></tr>`).join('');
    // 장기 시계열(db/series_leading, 28개월+) 우선 — 없으면 표의 4개월로 폴백
    const lsr=S(b,'series_leading');
    if(lsr.length>=2){
      $('lead_k').textContent=`순환변동치 추이 (기준 100) · ${lsr[0][0]} ~ ${lsr[lsr.length-1][0]} · ${lsr.length}개월`;
      mk($('c_lead'),L(lsr),[{n:'순환변동치',d:V(lsr),c:C.g,w:2.2,fill:true,bg:'rgba(30,158,106,.08)'}],{xt:8});
    } else {
      const asc=[...kl].reverse();
      mk($('c_lead'),asc.map(r=>r.period),[{n:'순환변동치',d:asc.map(r=>r.value),c:C.g,w:2.4,pt:3,fill:true,bg:'rgba(30,158,106,.08)'}]);
    }
    $('lead_note').innerHTML=esc(M.korea_leading_comment||'기준 100 위는 경기 확장 국면, 아래는 수축 국면을 시사한다. 4개월 연속 상승 중.');
  }

  /* ── 3.1.8 CAPEX (db/capex.json) ── */
  const cxd=b.capex?.data;
  if(cxd){
    $('capex_asof').textContent=`${cxd.asof} · 2023~2025 실측 교차검증`;
    /* (2차 req6 2026-07-18) docx와 동일한 구조 — 회사별 4행: CAPEX / 매출 / Capex매출 / FCF */
    const YS=cxd.years, NM=cxd.companies;
    const fx=v=>(v===''||v==null)?'—':Number(v).toLocaleString(undefined,{maximumFractionDigits:0});
    const sub=(lab,arr,cls)=>`<tr><td class="note" style="padding-left:18px">└ ${lab}</td>
      ${YS.map((y,i)=>{const v=(arr||[])[i];
        return `<td class="num note ${cls&&typeof v==='number'&&v<0?'dn':''}">${
          lab==='Capex/매출'?(v==null||v===''?'—':fx(v)+'%'):fx(v)}</td>`;}).join('')}</tr>`;
    $('capex_t').innerHTML=
      `<tr><th>항목 (십억 $)</th>${YS.map(y=>`<th style="text-align:right">${y}${y>=2026?'E':''}</th>`).join('')}</tr>`+
      NM.map((n,ci)=>
        `<tr><td><b style="color:${PAL[ci]}">${esc(n)}</b> <span class="note">CAPEX</span></td>
          ${(cxd.capex[n]||[]).map(v=>`<td class="num"><b>${fx(v)}</b></td>`).join('')}</tr>`+
        sub('매출',cxd.revenue&&cxd.revenue[n])+
        sub('Capex/매출',cxd.capex_to_rev&&cxd.capex_to_rev[n])+
        sub('FCF',cxd.fcf&&cxd.fcf[n],true)).join('')+
      `<tr><td colspan="${1+YS.length}" class="note">단위: 십억 달러 · 2026E 이후는 가이던스/컨센서스 · FCF 음수는 빨간색</td></tr>`;
    const S4=o=>NM.map((n,i)=>({n,c:PAL[i],w:2,pt:2,d:o[n].map(v=>v===''?null:v)}));
    mk($('c_capex'),YS,S4(cxd.capex),{legend:true});
    mk($('c_rev'),  YS,S4(cxd.revenue),{legend:true});
    mk($('c_fcf'),  YS,S4(cxd.fcf),{legend:true});
    mk($('c_ratio'),YS,S4(cxd.capex_to_rev),{legend:true});
    $('capex_c').innerHTML=esc(cxd.comment||'');
  }

  /* ── 3.1.9 메모리 + HBM (db/memory.json + series_mem_*) ── */
  const md=b.memory?.data;
  const SR=k=>(b['series_mem_'+k]?.data)||[];
  // 누적 시계열 → Chart.js 데이터셋
  function memTrend(el,key,opt={}){
    const ser=[...SR(key)].sort((a,b2)=>a[0]<b2[0]?-1:1);
    if(!ser.length) return;
    const items=[...new Set(ser.flatMap(r=>Object.keys(r[1])))];
    mk($(el), ser.map(r=>r[0].slice(5)),
      items.map((it,i)=>({n:it,d:ser.map(r=>r[1][it]??null),c:PAL[i%PAL.length],w:2,pt:3})),
      Object.assign({legend:true,y0:true,xt:8},opt));
  }
  // 표: 현재값 + 변동률
  function priceTbl(id,tkey){
    const t=md?.tables?.[tkey]; if(!t||!$(id)) return;   // (3차) 표 표시 폐지 — 차트만 (docx 3.1.9 구성)
    $(id).innerHTML=`<tr><th>품목</th><th style="text-align:right">평균가</th><th style="text-align:right">변동</th></tr>`+
      t.rows.map(r=>{const c=r.chg_pct;
        return `<tr><td><b>${esc(r.item)}</b></td><td class="num">${r.avg.toLocaleString(undefined,{minimumFractionDigits:2})}</td>
        <td class="num ${c>0?'up':(c<0?'dn':'note')}" ${Math.abs(c||0)>=5?'style="font-weight:800"':''}>${c==null?'—':(c>0?'+':'')+c.toFixed(2)+'%'}</td></tr>`;}).join('')+
      `<tr><td colspan="3" class="note">갱신 ${esc(t.last_update)} · TrendForce</td></tr>`;
  }
  if(md){
    $('mem_asof').textContent=`${md.asof} · 매일 08:30 서버 자동 수집`;
    const H=md.hbm||{};

    // ① HBM 시장규모 — (req9 2026-07-12) 연간 시계열 DB(series_mem_hbm_market, Yole 추정) 우선
    { const ms=[...SR('hbm_market')].sort((a,b2)=>a[0]<b2[0]?-1:1);
      if(ms.length){
        const yr=ms.map(r=>r[0]); const vals=ms.map(r=>Object.values(r[1])[0]);
        const yoy=vals.map((v,i)=>(i>0&&vals[i-1])?+((v/vals[i-1]-1)*100).toFixed(0):null);
        mk($('c_hbm_mkt'),yr,[{n:'시장규모($B)',d:vals,c:C.g},
          {n:'수요 증가율(%)',d:yoy,c:C.p,dash:[5,3],w:2.2}],{bar:true,legend:true,y0:true});
        ($('hbm_mkt_src')||{}).textContent='[추정] Yole Group·TrendForce 연간 전망 — 연 1~2회 갱신(조사기관 발표 시)';
      } else if(H.market){
        const yr=H.market.revenue_bn.map(r=>r[0]);
        const dy=Object.fromEntries(H.market.demand_yoy||[]);
        mk($('c_hbm_mkt'),yr,[{n:'시장규모($B)',d:H.market.revenue_bn.map(r=>r[1]),c:C.g},
          {n:'수요 증가율(%)',d:yr.map(y=>dy[y]??null),c:C.p,dash:[5,3],w:2.2}],{bar:true,legend:true,y0:true});
        ($('hbm_mkt_src')||{}).textContent=H.market.revenue_src;
      } }
    // ② HBM ASP
    if(H.asp){
      if($('asp_t')) $('asp_t').innerHTML=`<tr><th>제품</th><th style="text-align:right">가격(USD)</th><th style="text-align:right">변동</th><th>동인</th></tr>`+
        H.asp.map(a=>`<tr><td><b>${esc(a.product)}</b></td><td class="num">${esc(a.price)}</td>
        <td class="num ${a.trend==='up'?'up':'note'}">${esc(a.change||'—')}</td>
        <td class="note">${esc((a.driver||'').slice(0,40))}</td></tr>`).join('');
    }
    memTrend('c_asp','hbm_asp');
    // ③ 점유율
    if(H.share){
      const sr=Object.fromEntries((H.supplier_revenue||[]).map(r=>[r.vendor,r]));
      if($('share_t')) $('share_t').innerHTML=`<tr><th>업체</th><th style="text-align:right">HBM 점유율</th><th style="text-align:right">매출 기준</th><th>비고</th></tr>`+
        H.share.map(r=>{const v=sr[r.vendor]||{};
        return `<tr><td><b>${esc(r.vendor)}</b></td><td class="num">${r.share_pct}%</td>
        <td class="num note">${v.share_pct?`${v.share_pct}% ($${v.revenue_bn}B)`:'—'}</td>
        <td class="note">${esc(r.note||'')}</td></tr>`;}).join('');
    }
    memTrend('c_share','hbm_share');
    // ④⑤⑥ 가격 표 + 추세
    priceTbl('ds_t','dram_spot');    memTrend('c_ds','dram_spot');
    priceTbl('dc_t','dram_contract');memTrend('c_dc','dram_contract');
    // ⑥ NAND 현물 · ⑦ NAND 계약 — DRAM(④⑤)과 동일 패턴으로 각각 독립
    priceTbl('ns_t','nand_spot');     memTrend('c_ns','nand_spot');
    priceTbl('nc_t','nand_contract'); memTrend('c_nc','nand_contract');

    // ⑧ 스팟 − 계약 갭 (DRAM · NAND 동일 규격끼리 매칭)
    const dsr=Object.fromEntries((md.tables.dram_spot?.rows||[]).map(r=>[r.item,r]));
    const dcr=Object.fromEntries((md.tables.dram_contract?.rows||[]).map(r=>[r.item,r]));
    const nsr=Object.fromEntries((md.tables.nand_spot?.rows||[]).map(r=>[r.item,r]));
    const ncr=Object.fromEntries((md.tables.nand_contract?.rows||[]).map(r=>[r.item,r]));
    const GP=[['DDR4 8Gb','DDR4 8Gb (1Gx8) 3200','DDR4 8Gb 1Gx8'],
              ['DDR4 16Gb','DDR4 16Gb (2Gx8) 3200','DDR4 16Gb 2Gx8'],
              ['NAND 64Gb','MLC 64Gb 8GBx8','NAND 64Gb 8Gx8 MLC'],
              ['NAND 32Gb','MLC 32Gb 4GBx8','NAND 32Gb 4Gx8 MLC']];
    const gl=[],gv=[],grows=[];
    GP.forEach(([lab,si,ci])=>{
      const sp=dsr[si]||nsr[si], ct=dcr[ci]||ncr[ci];
      if(!sp||!ct||!ct.avg) return;
      const gap=+((sp.avg/ct.avg-1)*100).toFixed(1);
      gl.push(lab); gv.push(gap); grows.push([lab,sp.avg,ct.avg,gap]);
    });
    if(grows.length){
      $('gap_t').innerHTML=`<tr><th>규격</th><th style="text-align:right">현물</th><th style="text-align:right">계약</th>
        <th style="text-align:right">갭</th><th>해석</th></tr>`+
        grows.map(([lab,sp,ct,g])=>{const pos=g>0;
          return `<tr><td><b>${esc(lab)}</b></td><td class="num">${sp.toFixed(2)}</td><td class="num">${ct.toFixed(2)}</td>
          <td class="num ${pos?'up':'dn'}" style="font-weight:800">${pos?'+':''}${g.toFixed(1)}%</td>
          <td class="note">${pos?`현물이 계약가 ${g.toFixed(0)}% 상회 → 인상 압력`:`현물이 계약가 ${Math.abs(g).toFixed(0)}% 하회 → 압력 없음`}</td></tr>`;
        }).join('');
      mk($('c_spgap'),gl,[{n:'스팟−계약 갭(%)',d:gv,c:gv.map(v=>v>0?C.r:C.b)}],{bar:true});
      ($('spgap_src')||{}).textContent='현물가가 계약가를 상회하는 폭. 갭이 클수록 다음 계약 협상에서 계약가 인상 압력이 커진다 — 메모리 3사 실적의 선행지표. DDR4 8Gb 갭 +89%, NAND 64Gb 갭 +55%로 인상 압력이 지속되고 있다.';
    }

    // ⑨ HBM:DDR5 격차 — (req12 2026-07-12) 매일 환산 시계열(series_mem_hbm_ddr5_gap) 우선
    { const gs=[...SR('hbm_ddr5_gap')].sort((a,b2)=>a[0]<b2[0]?-1:1);
      if(gs.length){
        const last=gs[gs.length-1][1]||{};
        mk($('c_gap'),gs.map(r=>r[0].slice(5)),
          [{n:'배율(HBM÷DDR5)',d:gs.map(r=>r[1]['배율']??null),c:C.p,w:2.4},
           {n:'HBM $/GB',d:gs.map(r=>r[1]['HBM $/GB']??null),c:C.o,dash:[4,3]},
           {n:'DDR5 $/GB',d:gs.map(r=>r[1]['DDR5 $/GB']??null),c:C.b,dash:[4,3]}],{legend:true,y0:true});
        ($('gap_src')||{}).textContent=`[환산 추정] HBM3E 스택 ASP÷용량 vs DDR5 계약가 $/GB — 최신 ${last['배율']}배 (HBM $${last['HBM $/GB']}/GB vs DDR5 $${last['DDR5 $/GB']}/GB). 통상 5~6배 · 배율 급락=범용 DRAM 급등(삼성 상대 유리) 신호 · 매일 계산·누적.`;
      } else if(H.per_gb){
        const p=H.per_gb;
        mk($('c_gap'),['DDR5 현물','HBM3','HBM3E','HBM4E'],
          [{n:'USD/GB',d:[p.ddr5_spot_usd_per_gb,p.hbm3_usd_per_gb,p.hbm3e_usd_per_gb,p.hbm4_usd_per_gb],c:C.r}],
          {bar:true,y0:true});
        ($('gap_src')||{}).textContent=`DDR5 현물이 HBM3E의 ${p.premium_x}배 — 통상 HBM이 5~6배 프리미엄인데 역전됨. ${p.note}`;
      } }
    // ⑪ 선행지표 (매일) + 메모리/GPU 상대강도
    const LD=md.leading||{};
    if(Object.keys(LD).length){
      const ORD=['SOX','NVDA','AMD','TSM','KOSPI','MU'];
      const pc=v=>v==null?'—':`<span class="${v>0?'up':'dn'}">${v>0?'+':''}${v.toFixed(1)}%</span>`;
      $('lead_t').innerHTML=`<tr><th>지표</th><th style="text-align:right">현재값</th><th style="text-align:right">1년</th><th style="text-align:right">1개월</th><th>왜 선행지표인가</th></tr>`+
        ORD.filter(k=>LD[k]?.price!=null).map(k=>{const o=LD[k];
          return `<tr><td><b>${esc(o.label)}</b></td>
          <td class="num">${o.price.toLocaleString(undefined,{maximumFractionDigits:2})}</td>
          <td class="num"><b>${pc(o.chg_1y_pct)}</b></td><td class="num">${pc(o.chg_1m_pct)}</td>
          <td class="note">${esc(o.why||'')}</td></tr>`;}).join('')+
        `<tr><td colspan="5" class="note">Yahoo Finance 무인증 chart API · 매일 자동 수집</td></tr>`;
      const kk=ORD.filter(k=>LD[k]?.chg_1y_pct!=null);
      mk($('c_lead1y'),kk.map(k=>LD[k].label),
        [{n:'1년 수익률(%)',d:kk.map(k=>LD[k].chg_1y_pct),c:C.b}],{bar:true,y0:true});
      const rs=LD.MEM_VS_GPU;
      if(rs&&rs.value!=null){
        $('rs_box').style.display='';
        $('rs_k').innerHTML=`★ 메모리 / GPU 상대강도 = <b class="${rs.value>1?'up':'dn'}" style="font-size:1.25em">${rs.value}배</b> — ${esc(rs.signal||'')}`;
        $('rs_note').textContent='마이크론이 엔비디아보다 1년간 '+rs.value+'배 더 올랐다. HBM 을 사는 쪽보다 파는 쪽이 압도적으로 오른다는 것은 가치가 수요처에서 공급자로 이동했다는 뜻 — 메모리가 협상력을 쥐었고 공급부족이 극심하다는 신호다. 이 비율이 꺾이기 시작하면 공급부족 완화 = 사이클 고점 경계 신호로 읽는다.';
      }
      memTrend('c_rs','mem_vs_gpu');
    }

    // ⑫ 지표 사전 — 의미·해석·변동주기 (nmr_meta.py 단일 진실원천)
    const MT=md.meta||{};
    if(Object.keys(MT).length){
      if($('dict_t')) $('dict_t').innerHTML=`<tr><th>지표</th><th>변동 주기</th><th>의미</th><th>해석 방법</th></tr>`+
        Object.values(MT).filter(o=>o&&o.label).map(o=>{
          const daily=/매일/.test(o.cadence||'');
          return `<tr><td><b>${esc(o.label)}</b></td>
          <td style="white-space:nowrap;color:${daily?'#16a34a':'#d97706'}"><b>${esc(o.cadence||'-')}</b></td>
          <td class="note">${esc(o.meaning||'')}</td>
          <td class="note">${esc(o.howto||'')}</td></tr>`;}).join('')+
        `<tr><td colspan="4" class="note">녹색=매일 갱신 · 주황=주/월/분기/연 단위 갱신</td></tr>`;
    }

    // ⑨ 밸류에이션
    if(md.valuation){
      const V=md.valuation;
      const f=(v,K)=>v==null?'—':(K?Math.round(v).toLocaleString():v.toLocaleString(undefined,{maximumFractionDigits:2}));
      /* (3차 2026-07-18) docx 표3과 동일: 종목 | 2025(실적) | 2026E | 2027E | 2028E | 통화 — 셀='EPS x · PER y' */
      const HE=(b.hbm_eps&&(b.hbm_eps.data||b.hbm_eps))||{};
      const ORD=[['SK하이닉스','SK하이닉스'],['삼성전자','삼성전자'],['Micron','Micron (MU)']];
      const cellv=(e,y,K)=>{const ep=e['y'+y+'_eps'],pr=e['y'+y+'_per'];
        if(ep==null)return '—';
        return `EPS ${K?Math.round(ep).toLocaleString():ep.toLocaleString(undefined,{maximumFractionDigits:2})} · PER ${pr!=null?pr+'x':'—'}`;};
      if($('val_t')&&Object.keys(HE).length)
        $('val_t').innerHTML=`<tr><th>종목</th><th>2025(실적)</th><th>2026(E)</th><th>2027(E)</th><th>2028(E)</th><th>통화</th></tr>`+
          ORD.filter(([k])=>HE[k]).map(([k,lab])=>{const e=HE[k],K=e.currency==='KRW';
            return `<tr><td><b>${esc(lab)}</b></td><td class="num">${cellv(e,2025,K)}</td>
            <td class="num dn"><b>${cellv(e,2026,K)}</b></td><td class="num" style="color:var(--ok)">${cellv(e,2027,K)}</td>
            <td class="num note">${cellv(e,2028,K)}</td><td class="note">${esc(e.currency||'')}</td></tr>`;}).join('')+
          `<tr><td colspan="6" class="note">단일 소스 db/hbm_eps.json — 네이버 실적·컨센서스 매일 자동 갱신, PER = 최신 종가 ÷ EPS 재계산 (docx 3.1.9 표와 동일값) · ${esc((b.hbm_eps&&b.hbm_eps.price_note)||md.asof_valuation||'')}</td></tr>`;
    }
  }

  /* ── 3.1.10 관세청 수출 ── */
  const cs=b.customs?.data;
  if(cs){
    const m=cs.months.slice(-24);
    const it=[['total','전체'],['semiconductor','반도체'],['steel','철강'],['car','승용차'],['petroleum','석유'],
      ['wireless','무선통신'],['ship','선박'],['autoparts','자동차부품'],['computer','컴퓨터주변기기'],
      ['precision','정밀기기'],['appliance','가전제품']];   // (2026-08-05) API 제공 전 품목(00~10) — 이 11개가 전부(실측)
    /* (2026-08-05) 전체+8품목 3×3 그리드 — rows(월×차수 전 품목)를 피벗해 품목별 차트 */
    {const rmap={}; (cs.rows||[]).forEach(r=>{ rmap[r.yyyymm+'_'+r.seq]=r; });
     it.forEach(([k])=>{ const cv=$('c_cus_'+k); if(!cv) return;
       const seq=[1,2,3].map(sq=>m.map(mo=>{ const r=rmap[mo.replace('-','')+'_'+sq];
         const v=r?r[k]:null; return v!=null?v/1000:null; }));
       mk(cv,m,[{n:'1~10일',d:seq[0],c:C.b},{n:'1~20일',d:seq[1],c:C.o},{n:'월전체',d:seq[2],c:C.r}],
          {legend:true,bar:true}); });}
    const P=['p10','p20','pm'],PN=['1~10일','1~20일','월전체'];
    $('cus_tbl').innerHTML=`<tr><th>품목</th>${PN.map(x=>`<th style="text-align:right">${x}</th>`).join('')}</tr>`+
      it.map(([k,lab])=>`<tr><td><b>${lab}</b></td>${P.map(p=>{const v=cs.latest[p]?.[k];
        return `<td class="num">${v!=null?(v/1000).toLocaleString(undefined,{maximumFractionDigits:0}):'—'}</td>`;}).join('')}</tr>`).join('')+
      `<tr><td colspan="4" class="note">${esc(cs.latest.yyyymm)} 기준 · 백만 달러</td></tr>`;
  }
  /* (2026-08-06) 3.1.10 하단 — 투자 관점 품목별 월간 수출 (HS코드 · 2년 · fetch_hs_invest.py)
     표: 테마|품목|HS|비고|최신월|YoY|차트(24개월 막대). 10일 잠정치 미제공 품목(화장품·배터리 등)을 월간으로 보완 */
  if($('hsi_tbl')) fetch('/api/db/hs_invest').then(x=>x.ok?x.json():null).then(hv=>{
    if(!hv||!hv.items) return;
    const ms=(hv.months||[]).slice(-36);               // (2026-08-06) X축 3년치
    const off=hv.months.length-ms.length;
    $('hsi_asof').textContent='· 수집 '+(hv.asof||'');
    /* (2026-08-06) 관련 종목 — 관세청 통계는 기업별 비공개(비밀보호)라 품목별 대표 상장사 수동 큐레이션.
       품목 수출 추세 → 관련주 연결용. 클릭 시 네이버 금융 새 탭. */
    const HSI_REL={
      '3304':[['아모레퍼시픽','090430'],['LG생활건강','051900'],['코스맥스','192820'],['한국콜마','161890'],['실리콘투','257720']],
      '3305':[['LG생활건강','051900'],['아모레퍼시픽','090430']],
      '3303':[['신세계인터내셔날','031430'],['코스맥스','192820']],
      '8542':[['삼성전자','005930'],['SK하이닉스','000660']],
      '8541':[['서울반도체','046890'],['HD현대에너지솔루션','322000']],
      '8486':[['한미반도체','042700'],['주성엔지니어링','036930'],['원익IPS','240810']],
      '8507':[['LG에너지솔루션','373220'],['삼성SDI','006400'],['SK이노베이션','096770']],
      '2841+2825':[['에코프로머티','450080'],['포스코퓨처엠','003670']],
      '8703':[['현대차','005380'],['기아','000270']],
      '8708':[['현대모비스','012330'],['한온시스템','018880'],['HL만도','204320']],
      '3004':[['셀트리온','068270'],['한미약품','128940'],['유한양행','000100']],
      '3002':[['삼성바이오로직스','207940'],['셀트리온','068270'],['SK바이오사이언스','302440']],
      '9018':[['바텍','043150'],['아이센스','099190'],['인바디','041830']],
      '9021':[['덴티움','145720'],['디오','039840']],
      '8517':[['삼성전자','005930']],
      '8471':[['삼성전자','005930']],
      '8524':[['LG디스플레이','034220'],['삼성전자','005930']],
      '89':[['HD한국조선해양','009540'],['삼성중공업','010140'],['한화오션','042660']],
      '72':[['POSCO홀딩스','005490'],['현대제철','004020']],
      '2710':[['SK이노베이션','096770'],['S-Oil','010950'],['GS','078930']],
      '1902':[['농심','004370'],['삼양식품','003230'],['오뚜기','007310']],
      '2103':[['CJ제일제당','097950'],['대상','001680'],['삼양식품','003230']],
      '121221':[['CJ씨푸드','011150'],['사조씨푸드','014710']],
      '2202':[['롯데칠성','005300'],['LG생활건강','051900']],
      '2208':[['하이트진로','000080'],['롯데칠성','005300']],
      '88':[['한국항공우주','047810'],['한화에어로스페이스','012450'],['대한항공','003490']],
      '854232':[['SK하이닉스','000660'],['삼성전자','005930']],
      '870380':[['현대차','005380'],['기아','000270']],
      '300241':[['SK바이오사이언스','302440']],
      '300215':[['셀트리온','068270'],['삼성바이오로직스','207940']],
      '902129':[['덴티움','145720'],['디오','039840']],
      '9022':[['바텍','043150'],['뷰웍스','100120'],['레이','228670']],
      '330510':[['LG생활건강','051900'],['아모레퍼시픽','090430']],
      '8504':[['HD현대일렉트릭','267260'],['효성중공업','298040'],['LS일렉트릭','010120']],
      '8544':[['대한전선','001440'],['LS','006260']],
      '854142+854143':[['한화솔루션','009830'],['HD현대에너지솔루션','322000']],
      '8710':[['현대로템','064350'],['한화에어로스페이스','012450']],
      '93':[['한화에어로스페이스','012450'],['LIG넥스원','079550'],['풍산','103140']],
      '8543':[['에이피알','278470'],['클래시스','214150'],['원텍','336570']],
      '92':[['삼익악기','002450']]};
    const _rel=hs=>((HSI_REL[hs]||[]).map(([n,c])=>
      `<a href="https://finance.naver.com/item/main.naver?code=${c}" target="_blank" style="white-space:nowrap">${esc(n)}</a>`).join(' · '))||'—';
    // (2026-08-06) 최신월 + 최신 3·6개월 누적, 각각 전년 동일월(구간) 대비 YoY
    const _fmtM=v=>v!=null?('$'+(v/1000).toLocaleString(undefined,{maximumFractionDigits:0})+'M'):'—';
    const _fmtY=y=>`<td class="num ${y>0?'up':(y<0?'dn':'')}">${y!=null?((y>0?'+':'')+y.toFixed(1)+'%'):'—'}</td>`;
    const _sum=(e,a,b)=>{ if(a<0) return null; const s=e.slice(a,b+1); return s.some(v=>v==null)?null:s.reduce((x,y)=>x+y,0); };
    $('hsi_tbl').innerHTML=`<tr><th>테마</th><th>품목</th><th>HS코드</th><th>비고</th><th>관련 종목</th>
      <th style="text-align:right">최신월</th><th style="text-align:right">YoY</th>
      <th style="text-align:right">최근 3개월</th><th style="text-align:right">3M YoY</th>
      <th style="text-align:right">최근 6개월</th><th style="text-align:right">6M YoY</th>
      <th style="text-align:right">최근 1년</th><th style="text-align:right">1Y YoY</th>
      <th style="min-width:320px">월간 수출 (3년)</th></tr>`+
      hv.items.map((r,i)=>{
        const e=(r.exp||[]).slice(off);
        let li=e.length-1; while(li>=0&&e[li]==null) li--;          // 최신 유효월
        const last=li>=0?e[li]:null, yoy=(li>=12&&e[li-12])?(last/e[li-12]-1)*100:null;
        const s3=_sum(e,li-2,li),  p3=_sum(e,li-14,li-12), y3=(s3!=null&&p3)?(s3/p3-1)*100:null;
        const s6=_sum(e,li-5,li),  p6=_sum(e,li-17,li-12), y6=(s6!=null&&p6)?(s6/p6-1)*100:null;
        const s12=_sum(e,li-11,li), p12=_sum(e,li-23,li-12), y12=(s12!=null&&p12)?(s12/p12-1)*100:null;
        return `<tr><td><b>${esc(r.th)}</b></td><td>${esc(r.nm)}</td>
          <td class="note">${esc(r.hs)}</td><td class="note">${esc(r.note||'')}</td>
          <td style="font-size:12px;max-width:190px">${_rel(r.hs)}</td>
          <td class="num">${_fmtM(last)}</td>${_fmtY(yoy)}
          <td class="num">${_fmtM(s3)}</td>${_fmtY(y3)}
          <td class="num">${_fmtM(s6)}</td>${_fmtY(y6)}
          <td class="num">${_fmtM(s12)}</td>${_fmtY(y12)}
          <td><canvas id="c_hsi_${i}" style="max-height:56px"></canvas></td></tr>`;
      }).join('');
    hv.items.forEach((r,i)=>{ const cv=$('c_hsi_'+i); if(!cv) return;
      const e=(r.exp||[]).slice(off).map(v=>v!=null?v/1000:null);
      mk(cv,ms,[{n:'수출',d:e,c:C.r}],{bar:true}); });
  }).catch(()=>{});

  /* ── 3.1.11 반도체 사이클 ── */
  const sc=b.semi_cycle?.data;
  if(sc){
    $('stages').innerHTML=(sc.stages?.list||[]).map(s=>`<div class="stage ${s===sc.stages.current?'on':''}">${esc(s)}</div>`).join('');
    $('semi_sum').innerHTML=esc(sc.summary||sc.stages?.note||'');
    $('semi_tiles').innerHTML=(sc.tiles||[]).map(t=>`<div class="card"><div class="k">${esc(t.lab)}</div>
      <div class="v" style="font-size:16px">${esc(t.num)}</div><div class="s">${esc((t.sub||'').slice(0,70))}</div></div>`).join('');
    const cls=s=>s==='안전'?'p-ok':(s==='주의'||s==='둔화')?'p-warn':'p-bad';
    $('semi_sig').innerHTML=`<tr><th>신호</th><th>현재값</th><th>판정</th><th>경보 임계선</th></tr>`+
      (sc.signals||[]).map(g=>`<tr><td><b>${esc(g.name)}</b></td><td>${esc(g.value)}</td>
      <td><span class="pill ${cls(g.status)}">${esc(g.status)}</span></td>
      <td class="note">${esc((g.threshold||'').slice(0,58))}</td></tr>`).join('');
    // (req7 2026-07-12) 정량 미공개 신호는 판정상태 타임라인으로 — c_pq=QoQ 수치, c_inv=3신호 판정 누적
    const sr=sc.series||{};
    { const o=sr.price_qoq;
      if(o&&$('c_pq')) mk($('c_pq'),(o.labels||[]).map(l=>String(l).split(' ')[0].split('(')[0]),
        [{n:'QoQ %',d:o.values,c:C.r}],{bar:true,y0:true}); }
    { const st=(b.series_semi_status&&b.series_semi_status.data)||[];
      if(st.length&&$('c_inv')){
        const KEYS=[['inventory','재고주수',C.g,0.05],['price_qoq','DRAM 계약가 QoQ',C.o,0],['capex_yoy','CAPEX YoY',C.b,-0.05]];
        mk($('c_inv'),st.map(r=>r[0].slice(5)),
          KEYS.map(([k,n,c,off])=>({n,d:st.map(r=>{const v=(r[1]||{})[k];return v==null?null:v+off;}),c,w:2,pt:3})),
          {legend:true,y0:true}); } }
    $('semi_panels').innerHTML=(sc.panels||[]).map(p=>`<div class="box"><table>
      <tr><th colspan="2">${esc(p.title)}</th></tr>
      ${(p.rows||[]).map(r=>`<tr><td class="note" style="width:44%">${esc(r[0])}</td><td>${esc(r[1])}</td></tr>`).join('')}
      </table></div>`).join('');
  }

  /* ── 3.1.13 파생 포지셔닝 ── (2026-07-20) report_data(하루1회)와 분리 — /api/deriv 라이브 폴링(장중 5분) */
  function renderDeriv(dv){
    if(!dv||!$('deriv_t')) return;
    $('deriv_idx').innerHTML=(dv.index||[]).map(x=>`<div class="card">
      <div class="k">${esc(x.name)}</div><div class="v" style="font-size:18px">${esc(x.close)}</div>
      <div class="s"><span class="${String(x.ret1).startsWith('+')?'up':'dn'}">1일 ${esc(x.ret1)}</span> ·
        <span class="${String(x.ret5).startsWith('+')?'up':'dn'}">5일 ${esc(x.ret5)}</span></div></div>`).join('');
    const names=(dv.index||[]).map(x=>x.name);
    /* (2026-07-24) 🤖 자동 판독 — z 매트릭스에서 규칙 기반으로 지수별 종합 1줄 생성.
       부호는 이미 정규화(z+=주식 우호)돼 있어 라벨 불문 z 부호로 집계하되,
       '선물 OI 변화'는 조건부(가격과 함께 봐야 함)라 집계에서 제외. |z|≥1 만 셈. */
    const _autoRow=(()=>{ try{
      /* (2026-07-24) 지수별 종합 1줄만 — 신호 기준(|z|≥1.5)으로 통일.
         지표별 세부 해석은 아래 ③ 활성 신호 박스가 담당(중복 제거). */
      const per=names.map((n,i)=>{ let fav=0,unf=0;
        for(const r of (dv.rows||[])){ if(/OI|참고/.test(r.label||'')) continue;
          const z=(r.cells||[])[i]&&r.cells[i].z; if(z==null) continue;
          if(z>=1.5) fav++; if(z<=-1.5) unf++; }
        const v= fav>unf?`<b style="color:#c0392b">강세 우위</b> (우호 ${fav}·비우호 ${unf})`:
                 unf>fav?`<b style="color:#1e6fd6">약세 우위</b> (비우호 ${unf}·우호 ${fav})`:
                 (fav||unf)?`<b>중립·혼조</b> (${fav}:${unf})`:
                 `<b>중립</b> <span class="note">— 신호 없음(전 지표 평소 범위)</span>`;
        return `<b>${esc(n)}</b>: ${v}`; });
      return `<tr><td colspan="${1+names.length*2}" style="background:#f6faf6;line-height:1.8;font-size:12.5px">🤖 <b>자동 판독</b> <span class="note">(|z|≥1.5 신호만 집계 — z(+)=우호·z(−)=비우호 · OI(조건부)·참고 항목은 제외 · 세부 해석은 아래 ③ 활성 신호)</span><br>${per.join(' &nbsp;·&nbsp; ')}</td></tr>`;
    }catch(e){ return ''; } })();
    $('deriv_t').innerHTML=_autoRow+`<tr><th>지표</th>${names.map(n=>`<th colspan="2" style="text-align:center">${esc(n)}</th>`).join('')}</tr>
      <tr><th></th>${names.map(()=>`<th style="text-align:right">값</th><th style="text-align:right">z</th>`).join('')}</tr>`+
      (dv.rows||[]).map(r=>`<tr><td><b>${esc(r.label)}</b></td>${(r.cells||[]).map(c=>{
        const z=c.z, hot=z!=null&&Math.abs(z)>=1.5;
        const hasV=c.v!=null&&!['-','—',''].includes(String(c.v).trim());
        if(!hasV) return `<td class="num note" colspan="2" style="text-align:center">N/A</td>`;
        return `<td class="num">${esc(c.v)}</td><td class="num ${hot?(z>0?'up':'dn'):'note'}" ${hot?'style="font-weight:800"':''}>${z!=null?z.toFixed(2):'<span class="note" style="font-style:italic">making</span>'}</td>`;
      }).join('')}</tr>`).join('')+
      (dv.night?(()=>{const n=dv.night, up=Number(n.chg_pct)>=0,
        hms=String(n.mkt_time||'').replace(/^(\d{2})(\d{2})(\d{2}).*$/,'$1:$2:$3');
        return `<tr><td colspan="${1+names.length*2}" class="note" style="background:#f3f6ff;line-height:1.75">
        🌙 <b>야간선물</b> (KRX 야간세션 18:00~06:00) — KOSPI200 <b>${esc(Number(n.px).toLocaleString())}</b>
        <b class="${up?'up':'dn'}">${up?'+':''}${esc(n.chg_pct)}%</b> <span class="note">(주간 정규장 종가 대비)</span><br>
        · <b>기준시각 ${esc(n.ts)} KST</b>${hms?` <span class="note">(거래소 체결 ${esc(hms)})</span>`:''} — 조회 시점 기준 <b>${esc(n.age_sec)}초 전</b> 값<br>
        · <b>갱신주기</b> — 수집: 웹소켓 <b>실시간</b>(체결 발생 즉시 기록) · 화면: <b>5분마다</b> 자동 폴링(새로고침하면 즉시 최신)<br>
        · 야간엔 현물(코스피200 지수)이 멈춰 있어 <b>베이시스·z에는 반영하지 않고</b> 참고용으로만 표시합니다</td></tr>`;})():'')+
      `<tr><td colspan="${1+names.length*2}" class="note">${esc(dv.asof||'')}${dv.built_at?` · <b>🔄 마지막 취득 ${esc(dv.built_at)} KST</b>`:''}</td></tr>`+
      (dv.cadence?`<tr><td colspan="${1+names.length*2}" class="note">갱신주기 — ${esc(dv.cadence)}</td></tr>`:'')+
      `<tr><td colspan="${1+names.length*2}" class="note">※ 기준일 안내 — <b>미국 COT는 주간 지표</b>라 1주 내외 지연이 정상입니다(화요일 포지션을 그 주 금요일에 CFTC가 공표 → 다음 갱신은 금요일). 일중 타이밍이 아니라 <b>주간 포지셔닝(구조적 쏠림)</b>으로 읽습니다. 반면 선물 베이시스·KOSPI200 현물/수급·옵션 지표는 당일~T+1 로 단기 신호를 담당합니다. 한국 수급·공매도 등 KRX 공표 항목도 T+1~T+2 지연이 정상이며, 값 옆 (MM-DD) 는 그 값의 실제 기준일입니다.</td></tr>`+
      `<tr><td colspan="${1+names.length*2}" class="note">※ z 공란(—) 안내 — 풋콜비율·IV 스큐·딜러 감마(GEX)는 옵션 체인 과거 스냅샷이 공개 소스에 없어 2026-07-11 수집 개시분부터 자체 누적 중이며, 롤링 60거래일이 쌓이는 2026년 10월경부터 z가 자동 산출됩니다(그때까지 현재값 + 'making'(누적 진행 중) 표시). 한국 외국인·기관 수급 z도 주간 이력 누적 후 순차 산출. N/A = 해당 지수에서 조사 불가 항목(KOSPI200 옵션 지표는 VKOSPI로 대체, VKOSPI는 한국 전용 — 미국은 VIX).</td></tr>`;
    $('dv_us').textContent=dv.market_us||'—';
    $('dv_kr').textContent=dv.market_kr||'—';
    $('dv_syn').textContent=dv.synthesis||'';
    // (req7 2026-07-18) ③ 활성 신호 |z|≥1.5 — docx와 동일하게, 빨간 박스로 강조
    const sg=dv.signals||dv.active_signals||[];
    if($('dv_sig')) $('dv_sig').style.display=sg.length?'block':'none';
    // (2026-07-20) 부호 정규화 후: z(+)=주식 우호(빨강) / z(−)=비우호(파랑).
    //   단 '선물 OI 변화'는 가격 방향과 함께 봐야 하는 조건부라 주황(중립)으로 뺀다.
    //   ⚠ 로 시작하는 stale 경고 줄은 색 없이 회색 처리.
    if(sg.length&&$('dv_sig_list')) $('dv_sig_list').innerHTML=sg.map(s2=>{
      const t=String(s2);
      if(/^\s*⚠/.test(t)) return `<div class="note" style="font-weight:600">${esc(t)}</div>`;
      const m=t.match(/z=([+-])/), cond=/OI/.test(t);
      const cls=cond?'sig-neu':(m&&m[1]==='+'?'sig-up':'sig-dn');
      const bdg=cond?'조건부':(cls==='sig-up'?'▲ 주식 우호':'▼ 비우호');
      return `<div class="${cls}">• ${esc(t)}<span class="sigbadge">${bdg}</span></div>`;
    }).join('');
  }
  renderDeriv(M.deriv_positioning);
  {let dvTimer=null; const dvPull=()=>fetch('/api/deriv',{cache:'no-store'}).then(r=>r.ok?r.json():null).then(d=>{if(d&&d.rows)renderDeriv(d);}).catch(()=>{});
   dvPull(); if(!window.__dvTimer) window.__dvTimer=setInterval(dvPull,300000);}

  /* ── KRX ── */
  const kx=b.krx_brief?.data;
  if(kx) $('krx').innerHTML='<div class="note" style="grid-column:1/-1;margin-bottom:2px">🖥 서버 자체 수집 — 매일 2회(06:35·15:35 KST) KRX 게시판 최신 회차 자동 조사 + 리포트 실행 시 회차 체크(주말·휴장일은 직전 거래일 회차)</div>'+
    Object.entries(kx).filter(([k])=>k==='krx'||k==='short').map(([k,v])=>{
      const pfx=k==='krx'?'krx_brief':'short_brief', dir=`${k==='krx'?'krx':'short'}_${v.att_seq}`;
      let imgs='';
      for(let i=1;i<=(v.pages||0);i++) imgs+=`<a href="/krxbrief/${dir}/${pfx}_p${i}.png" target="_blank"><img src="/krxbrief/${dir}/${pfx}_p${i}.png" style="width:100%;border:1px solid var(--line,#ddd);border-radius:6px;margin-top:8px" loading="lazy" alt="${esc(v.title)} p${i}"></a>`;
      return `<div class="card"><div class="k">${k==='krx'?'KRX 증시 Brief':'공매도 데일리 브리프'}</div>
    <div class="v" style="font-size:14px">${esc(v.title)}</div>
    <div class="s">등록 ${esc(v.date)} · ${esc(v.pages)}p · <a href="https://open.krx.co.kr/contents/MKD/01/0101/01010000/MKD01010000.jsp" target="_blank" rel="noopener">원문(KRX)</a></div>${imgs}</div>`;}).join('');

  /* ── 3.1.1 HY 스프레드 — DB 시계열(series_hy_oas)에서 계산, docx와 동일한 표+차트 ── */
  {const hs=S(b,'series_hy_oas'), hy=M.hy_spread||{};
  if(hs.length>2||hy.current!=null){
    let cur, vals;
    if(hs.length>2){
      const pts=hs.map(x=>[new Date(x[0]),x[1]]), last=pts[pts.length-1][0];
      const at=days=>{const t=new Date(last-days*864e5),c=pts.filter(p=>p[0]<=t);return (c.length?c[c.length-1]:pts[0])[1];};
      cur=pts[pts.length-1][1];
      vals=[['현재',cur],['1일',pts[pts.length-2][1]],['1주',at(7)],['1개월',at(30)],['3개월',at(91)],['6개월',at(182)],['1년',at(365)]];
    }else{
      cur=hy.current;
      vals=[['현재',cur],['1일',hy.d1],['1주',hy.w1],['1개월',hy.m1],['3개월',hy.m3],['6개월',hy.m6],['1년',hy.y1]];
    }
    // (req1 2026-07-12) OAS 레벨 표 폐지 — 현재값+차트만 (docx 3.1.1 과 동일)
    if($('hy_cur')) $('hy_cur').innerHTML=`— 현재 <b>${cur==null?'-':Number(cur).toFixed(2)+'%'}</b> <span class="note">(기준 ${esc(hs.length?hs[hs.length-1][0]:(hy.asof||''))})</span>`;
    if(hs.length){const yr=hs.slice(-262); mk($('c_hy'),L(yr),[{n:'HY OAS',d:V(yr),c:C.o,w:2,fill:true,bg:'rgba(224,140,26,.08)'}]);}
  }}

  /* ── 버크셔 ── */
  const bk=b.berkshire?.data;
  if(bk){
    // (2026-08-14) 자동 갱신 출처·시각 표기 — 서버 크론(fetch_berk_13f.py)이 EDGAR 원문을 직접 파싱해 갱신
    const _bo=b.berkshire||{}; const _bsrc=_bo.auto?`<span class="note">🖥 EDGAR 자동 갱신 · 확인 ${esc(_bo.as_of||'')}</span>`:'';
    // (2026-08-14) 10-Q 분기 자금흐름(XBRL 실측) — 13F보다 먼저 나오는 '사고 있나 팔고 있나' 지표
    const _qf=bk.q_flow||null;
    const _qtbl=_qf?`<div class="box" style="overflow-x:auto;margin-top:10px"><table>
      <tr><th>${_qf.quarter} 자금 흐름 <span class="note">(${esc(_qf.form)} ${esc(_qf.filed)} 제출 · 단위 억달러)</span></th>
          <th>상장주식 매입</th><th>매도</th><th>순매수</th><th>자사주 매입</th><th>현금+단기국채</th><th>주식 평가액</th></tr>
      <tr><td class="note">XBRL 실측 · 분기 단독값(누계 차분)</td>
          <td class="num">${_qf.equity_buy_100m??'-'}</td><td class="num">${_qf.equity_sell_100m??'-'}</td>
          <td class="num"><b class="${(_qf.equity_net_100m||0)>=0?'up':'dn'}">${_qf.equity_net_100m??'-'}</b></td>
          <td class="num">${_qf.buyback_100m??'-'}</td>
          <td class="num">${_qf.cash_total_100m??'-'}</td><td class="num">${_qf.equity_fv_100m??'-'}</td></tr></table></div>`:'';
    $('berk_sum').innerHTML=`<b>${esc(bk.quarter)}</b> · 공시 ${esc(bk.filing_date)} ${_bsrc}<br>${esc(bk.summary)}<br><br><b>현금:</b> ${esc(bk.cash||'—')}`+_qtbl;
    const sec=(t,arr,cl)=>`<div class="box"><table><tr><th colspan="2">${t} (${(arr||[]).length})</th></tr>
      ${(arr||[]).map(x=>`<tr><td style="width:34%"><b class="${cl}">${esc(x.ticker||'')}</b> ${esc(x.name)}</td>
      <td class="note">${esc(x.detail)}</td></tr>`).join('')||'<tr><td class="note">없음</td></tr>'}</table></div>`;
    $('berk_moves').innerHTML=sec('신규 매수',bk.new_buys,'up')+sec('비중 확대',bk.added,'up')+
      sec('비중 축소',bk.reduced,'dn')+sec('전량 매도',bk.exited,'dn');
    // (req17 2026-07-18) A.5 상위 보유 종목
    const th=bk.top_holdings||[];
    const bt=$('berk_top');
    if(bt&&th.length) bt.innerHTML=`<tr><th>#</th><th>종목</th><th>비중 · 평가액</th><th>비고</th></tr>`+
      th.map((x,i)=>`<tr><td>${i+1}</td><td><b>${esc(x.ticker||'')}</b> ${esc(x.name||'')}</td>
        <td class="num">${esc(x.weight_or_value||'')}</td><td class="note">${esc(x.note||'')}</td></tr>`).join('');
  }
  /* (req8 2026-07-18) 패스트 엔트리 후보 — 서버 매일 뉴스 수집 */
  fetch('/api/db/ipo_news').then(r=>r.json()).then(nw=>{
    const el=$('d_ipo'); if(!el) return;
    el.innerHTML=`<tr><th>일자</th><th>분류</th><th>헤드라인</th><th>매체</th></tr>`+
      (nw.items||[]).slice(0,25).map(i=>`<tr><td class="note">${esc(i.date||'')}</td>
        <td>${i.cat==='ipo'?'<span class="pill p-ok">IPO</span>':'<span class="pill">지수편입</span>'}</td>
        <td><a href="${esc(i.url)}" target="_blank" rel="noopener">${esc(i.title)}</a></td>
        <td class="note">${esc(i.src||'')}</td></tr>`).join('')+
      `<tr><td colspan="4" class="note">${esc(nw.desc||'')} · ${esc(nw.as_of||'')}</td></tr>`;
  }).catch(()=>{});

  /* ── 서버 폴링 ── (req18 2026-07-18) 김프·공포탐욕·원달러 카드는 폐지 —
     daily 탭 6장에서 서버 수집 DB(kimp_series·crypto_fng)로 더 정밀하게 제공한다 */

  /* ── DB 인벤토리 (항목 설명 + 기준일) ── */
  const DESC={
    berkshire:'버크셔 해서웨이 13F 보유지분 변동 + 10-Q 분기 자금흐름(매입·매도·자사주·현금+단기국채) — 🖥 서버가 EDGAR 원문·XBRL 직접 파싱해 자동 갱신',
    capex:'AI 빅테크 연간 CAPEX·매출·FCF 표 (3.1.8, 실적=FMP·전망=가이던스/컨센서스)',
    customs:'관세청 수출 잠정치 10일 단위 — 전체·반도체 등 품목별 (3.1.10)',
    dot_plot:'FOMC 점도표 SEP 중간값 — 2026~2028말·장기중립 (3.1.1)',
    employment:'미국 고용·경기 스냅샷 — NFP·실업률·ISM·GDP·소매판매 (3.1.3 표)',
    fomc_meetings:'향후 FOMC 일정·상태·비고 (3.1.1)',
    hbm_eps:'HBM 3사(SK하이닉스·삼성전자·마이크론) EPS/PER 추정 (3.1.9)',
    inflation:'미국 물가 스냅샷 — CPI·근원CPI·PCE·PPI·기대인플레 (3.1.2 표)',
    krx_brief:'KRX 증시 Brief·공매도 데일리 브리프 회차 메타 (3.2.4/3.2.5)',
    leading:'한국 경기선행지수 순환변동치 최근월 요약 (3.1.5)',
    memory:'메모리(DRAM·NAND·HBM) 가격·시장 스냅샷 (3.1.9)',
    appe:'피지컬 AI(휴머노이드) 밸류체인 상장 54종 — 6계층(두뇌·센서·액추에이터·소재배터리·시뮬레이션·완성체) 시세·수익률 (부록E)',
    kr_liquidity:'국내 유동성·레버리지 — 예탁금·미수금·반대매매·신용잔고(코스피/코스닥)·M2 (3.1.14, 원본=data/kr_liquidity.db)',
    oecd_cli:'OECD 경기선행지수(CLI) 주요국 월별 (3.1.4)',
    policy_rates:'주요 6개국 정책금리 daily 실측 — 美FRED·韓ECOS·유로존FRED·영일중 global-rates, monthly 이력 자동 upsert (3.1.1)',
    events_calendar:'경제 이벤트 캘린더 뼈대 — FRED 발표일정(실측)+FOMC+중앙은행 회의+만기 규칙+직전 보고서 검증분 (2장·📅 캘린더 탭)',
    cb_meetings:'중앙은행 회의 일정 시드 — ECB·BOJ·BOE·한은·LPR (events_calendar 입력)',
    brokers3:'한국투자 한눈에 투데이 모닝브리프 본문(직전 영업일 자동) — 7장 Chrome 대체',
    ism_pmi:'ISM 제조/서비스 최신 공표치 — PRNewswire 헤드라인 실측 파싱 (3.1.3)',
    ib_insights:'글로벌 IB 5사 관련 최신 보도 풀(24시간 보존) — 8장 GlobalSecurities 1차 소스',
    rebalance_news:'지수변경 헤드라인 모니터 — change_marker 불변이면 리밸런싱 에이전트 미발행 (3.3.2 게이트)',
    factset_insight:'FactSet Insight RSS 최신 글 목록 — 3.1.6 최신 블로그 판별(Chrome 대체)',
    news_pool:'구글뉴스 헤드라인 풀 10주제(48h 보존, AI 산업만 24h) — 1장 Top10·부록B 선별 소스',
    broker_reports:'네이버 금융리서치 6게시판 — 증권사별 최신 리포트+최근 2일 요약(PDF 추출) (7.8)',
    ipo_news:'대형 IPO·지수편입 헤드라인 (3.3.2 패스트엔트리 후보 판정)',
    m7_estimates:'M7 EPS·매출 컨센서스+리비전·목표가·투자의견 (3.1.7 기초)',
    etf_quotes:'미국 주요 ETF 56종 시세·기간수익률 스냅샷 (3.3.1 기초·폴백)',
    crypto_overview:'암호화폐 시장 개요 — 시총·거래대금·도미넌스 (6.1)',
    crypto_movers:'암호화폐 Top Gainers/Losers 각 10종 (6.4)',
    crypto_fng:'크립토 공포·탐욕 지수 1년 이력 (6.2)',
    kimp_series:'김치프리미엄 10분 시계열(BTC·ETH·XRP·SOL, 1년 백필) (6.3)',
    semi_cycle:'반도체 사이클→코스피 점검판 3대 신호 (3.1.11)',
    series_curve_10_2:'미국 장단기 금리차 10Y−2Y 일별 시계열 (3.1.1 차트)',
    series_emp_gdp:'미국 실질 GDP 성장률(연율) 분기 시계열 (3.1.3 차트)',
    series_emp_ism_mfg:'ISM 제조업 PMI 월별 시계열 (3.1.3 차트)',
    series_emp_ism_svc:'ISM 서비스업 PMI 월별 시계열 (3.1.3 차트)',
    series_emp_jobless:'신규 실업수당 청구건수 주간 시계열 (3.1.3 차트)',
    series_emp_nfp:'비농업고용(NFP) 시계열 (3.1.3 차트)',
    series_emp_nfp_mom:'NFP 월 신규고용(전월차) — nfp 폴백·차트 교차검증선',
    series_emp_retail:'소매판매 시계열 (3.1.3 차트)',
    series_emp_retail_mom:'소매판매 전월비 — retail 폴백·차트 교차검증선',
    series_emp_unemp:'실업률 월별 시계열 (3.1.3 차트)',
    series_fed_funds_5y:'미국 연방기금 실효금리 5년 일별 시계열 (3.1.1)',
    series_hy_oas:'하이일드 스프레드(ICE BofA US HY OAS) 일별 누적 — 3.1.1 HY 표·차트 소스',
    series_infl_CPI:'CPI 전년비 월별 시계열 (3.1.2 차트)',
    series_infl_Core_CPI:'근원 CPI 전년비 월별 시계열 (3.1.2 차트)',
    series_infl_Core_PCE:'근원 PCE 전년비 월별 시계열 (3.1.2 차트)',
    series_infl_PCE:'PCE 전년비 월별 시계열 (3.1.2 차트)',
    series_infl_PPI:'PPI 전년비 월별 시계열 (3.1.2 차트)',
    series_infl_exp:'기대인플레이션(10Y BEI) 일별 시계열 (3.1.2 차트)',
    series_inflidx_CPI:'CPI 지수(레벨) 월별 — 전년비 계산·검증용 원계열',
    series_inflidx_Core_CPI:'근원 CPI 지수(레벨) 월별 — 원계열',
    series_inflidx_Core_PCE:'근원 PCE 지수(레벨) 월별 — 원계열',
    series_inflidx_PCE:'PCE 지수(레벨) 월별 — 원계열',
    series_inflidx_PPI:'PPI 지수(레벨) 월별 — 원계열',
    series_leading:'한국 경기선행지수 순환변동치 월별 시계열 (3.1.5 차트)',
    series_mem_dram_contract:'DRAM 고정거래가(계약가) 시계열 (3.1.9 대시보드)',
    series_mem_dram_spot:'DRAM 현물가 시계열 (3.1.9 대시보드)',
    series_mem_hbm_asp:'HBM ASP(평균판매가) 추정 시계열 (3.1.9)',
    series_mem_hbm_share:'HBM 시장 점유율(3사) 시계열 (3.1.9)',
    series_mem_leading_px:'메모리 선행가격 지표 시계열 (3.1.9)',
    series_mem_mem_vs_gpu:'메모리 vs GPU 상대 지표 시계열 (3.1.9)',
    series_mem_nand_contract:'NAND 고정거래가(계약가) 시계열 (3.1.9)',
    series_mem_nand_spot:'NAND 현물가 시계열 (3.1.9)',
    series_us10y_daily:'미국 10년물 국채금리 일별 시계열 (3.1.1 차트)',
    series_us2y_daily:'미국 2년물 국채금리 일별 시계열 (3.1.1 차트)',
    series_semi_status:'반도체 사이클 3신호 판정상태 타임라인 — 0안전/1주의/2경보 (3.1.11 차트)',
    ta_stage1:'TradingAgents 1단계 — 유니버스·거래가능성 하드컷 통과 종목 (한국·미국)',
    ta_stage2:'TradingAgents 2단계 — 4축 z-score 랭킹 (축별 표준화 점수·종합)',
    ta_stage3:'TradingAgents 3단계 — 실측 재무 팩터 후보 번들 (/namoobi-trading-agents 토론 입력)',
    ta_calls:'TradingAgents 판정 기록 — 회차별 토론 채택/관망/탈락 (/namoobi-trading-agents 실행 시 기록)',
    ta_verdict:'TradingAgents 최종 판정 — 리스크 심사 결과·승인 종목·가격 스냅샷 (스킬 실행 시 기록)',
    ta_perf:'TradingAgents 5단계 성과추적 — 판정 종목 경과 수익률·벤치마크 α (탈락 포함, 생존편향 방지)',
    ta_status:'TradingAgents 스크리닝 파이프라인 실행 상태·회차 로그',
    health:'서버 자가진단 — 번들 크기·API 응답·스키마 드리프트·DB 신선도·자원 (2시간마다, 헤더 배지)',
    ta_flag:'TradingAgents 스크리닝 완료 플래그 — 거래일·완료 여부'};
  // (2026-07-17) 수집 주체 — 🖥 서버 cron 자체 수집(리포트 실행과 무관하게 최신) vs 📄 리포트 실행 시 수집
  const SRV={customs:'06:35·15:35',leading:'06:35·15:35',series_leading:'06:35·15:35',krx_brief:'06:35·15:35',
    series_hy_oas:'06:35·15:35',memory:'06:45·15:45',kr_liquidity:'06:35·14:10·16:10',appe:'06:50·15:50',berkshire:'06:20·12:20(13F·10-Q 공시 감지)',health:'2시간마다',
    // (2026-07-19 서버화 2차) market_prefetch2(05:45·16:05)·report_prefetch·개별 크론
    policy_rates:'05:45·16:05',events_calendar:'05:45·16:05',cb_meetings:'05:45·16:05',brokers3:'05:45·16:05',
    ism_pmi:'05:45·16:05',ib_insights:'05:45·16:05',rebalance_news:'05:45·16:05',factset_insight:'05:45·16:05',
    news_pool:'매시:10+05:55',broker_reports:'05:50·07:10·16:10',m7_estimates:'05:50·15:50',etf_quotes:'05:50·15:50',
    ipo_news:'07:20',employment:'07:40',series_emp_nfp:'07:40',series_emp_unemp:'07:40',series_emp_retail:'07:40',
    series_emp_gdp:'07:40',series_emp_jobless:'07:40',
    crypto_overview:'매시',crypto_movers:'매시',crypto_fng:'매시',kimp_series:'10분',
    series_mem_dram_spot:'06:45·15:45',series_mem_dram_contract:'06:45·15:45',series_mem_nand_spot:'06:45·15:45',
    series_mem_nand_contract:'06:45·15:45',series_mem_hbm_asp:'06:45·15:45',series_mem_hbm_share:'06:45·15:45',
    series_mem_hbm_ddr5_gap:'06:45·15:45',series_mem_leading_px:'06:45·15:45',series_mem_mem_vs_gpu:'06:45·15:45',
    ta_stage1:'06:50·15:50',ta_stage2:'06:50·15:50',ta_stage3:'06:50·15:50',ta_status:'06:50·15:50',ta_flag:'06:50·15:50',ta_perf:'07:10'};
  const inv=Object.keys(b).filter(k=>k!=='_poll').sort().map(k=>{
    const d=b[k],dat=d?.data; let n='—',kind='—';
    if(Array.isArray(dat)&&dat.length&&Array.isArray(dat[0])){kind='시계열';n=dat.length+'점';}
    else if(Array.isArray(dat)){kind='표';n=dat.length+'행';}
    else if(dat&&typeof dat==='object'){kind='복합';n=Object.keys(dat).length+'키';}
    else if(!dat&&d&&typeof d==='object'){ // (2026-07-17) data 래퍼 없는 파일(ta_* 등) — 최상위 구조로 판정
      const ks=Object.keys(d).filter(x=>x!=='as_of'&&x!=='marker');
      const arr=ks.map(x=>d[x]).find(v=>Array.isArray(v)&&v.length);
      if(arr){kind='복합';n=ks.length+'키·'+arr.length+'행';} else if(ks.length){kind='복합';n=ks.length+'키';} }
    // (2026-07-12) 기준일 자동 폴백 — as_of 공란이면 marker(날짜꼴) → 시계열 최신일 → '—'
    let ao=d?.as_of;
    if(!ao){ const mk2=String(d?.marker||'').slice(0,10);
      if(/^\d{4}-\d{2}-\d{2}$/.test(mk2)) ao=mk2;
      else if(Array.isArray(dat)&&dat.length&&Array.isArray(dat[0])){ const l=String(dat[dat.length-1][0]).slice(0,10); if(/^\d{4}-\d{2}-\d{2}$/.test(l)) ao=l; } }
    return {k,kind,n,asof:ao||'—',desc:DESC[k]||'',srv:SRV[k]||null};
  });
  // (2026-07-12) 좌측 사이드바 컴팩트 — 항목당 2줄(1줄: 이름+형태·규모·기준일 / 2줄: 설명)
  // (2026-07-17) 수집주체 배지 + as_of 자동 최신화(10분 주기 /api/domains 재조회)
  $('inv').innerHTML=inv.map(r=>`<div class="it">
    <div class="l1"><b>${esc(r.k)}</b><span class="m">${r.srv?'🖥':'📄'} ${r.kind} ${r.n} · <span data-inv="${esc(r.k)}">${esc(r.asof)}</span></span></div>
    <div class="l2">${r.srv?'<b style="color:#2f6fd0">서버 자체 수집 '+r.srv+' KST</b> · ':''}${esc(r.desc)}</div></div>`).join('');
  const nSrv=inv.filter(r=>r.srv).length;
  $('inv_n').textContent=`${inv.length}종 (🖥 서버 자체 수집 ${nSrv} · 📄 리포트 실행 수집 ${inv.length-nSrv})`;
  async function refreshInv(){ try{
    const ds=await (await fetch('/api/domains')).json();
    ds.forEach(d=>{ const el=document.querySelector(`[data-inv="${d.name}"]`);
      if(el){ let a=d.as_of||''; if(!a&&/^\d{4}-\d{2}-\d{2}/.test(String(d.marker||''))) a=String(d.marker).slice(0,10); if(a) el.textContent=a; }});
  }catch(e){} }
  setInterval(refreshInv, 600000);

  /* ── 보고서 (최신 5건만 — 서버는 7일치 보관, 목록은 5건으로 컷) ── */
  $('reports').innerHTML=rs.slice(0,3).map(r=>`<div class="rpt">
    <div><b>${esc(r.datetime)}</b> <span class="note">· ${r.size_mb}MB</span></div>
    <a class="dl" href="/reports/${encodeURIComponent(r.file)}">다운로드</a></div>`).join('');
})();


/* ── 안드로이드 APK 릴리스 (GitHub Releases 캐시 · sync_apk.py) ── */
fetch('/api/apk').then(r=>r.json()).then(rs=>{
  const el=document.getElementById('apkbox');
  if(!el) return;
  if(!Array.isArray(rs)||!rs.length){el.innerHTML='<div class="rpt">릴리스 없음</div>';return;}
  el.innerHTML=rs.slice(0,1).map(r=>`<div class="rpt">
    <div><b>${r.tag}</b> · ${r.published}${r.notes?`<br><span style="opacity:.75;font-size:11px">${r.notes}</span>`:''}<br><span style="opacity:.55;font-size:11px">${r.file} · ${r.size_mb}MB</span></div>
    <a class="dl" href="/apk/${encodeURIComponent(r.file)}">다운로드</a></div>`).join('');
}).catch(()=>{});

/* ══════════════════════════════════════════════════════════════════
   (2026-07-12) 상단 탭 — 우측 영역(nav+본문) 통째 전환
     ① daily 조사 data  : 매 실행 새로 조사 (docx 1~8·13장)   — 향후 개발
     ② DB data          : 누적·버전관리 (현행 화면)            — 가동 중
     ③ AI 추론 data     : 모델 판단 (docx 9~12장)              — 향후 개발
     ④ TradingAgents    : 전종목 스크리닝                       — 설계 단계
   1/3/4 는 골격만 두고, 들어갈 내용을 표로 명시해 둔다.
   ══════════════════════════════════════════════════════════════════ */
(function(){
  const esc2=t=>String(t??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
  const tbl=(id,head,rows)=>{const el=document.getElementById(id); if(!el)return;
    el.innerHTML=`<tr>${head.map(h=>`<th>${h}</th>`).join('')}</tr>`+
      rows.map(r=>`<tr>${r.map((c,i)=>`<td${i===0?' style="white-space:nowrap"':''}>${c}</td>`).join('')}</tr>`).join('');};



  tbl('tbl_ta',['단계','내용','산출'],[
    ['<b>1</b> 유니버스','코스피·코스닥 전종목 + 미국 상장 전종목','종목 마스터 DB'],
    ['<b>2</b> 정량 필터','밸류(PER·PBR)·성장(매출·EPS 증가율)·수급·모멘텀·재무건전성으로 <b>수십 개까지 압축</b>','1차 후보'],
    ['<b>3</b> 에이전트 토론','후보에만 적용 — 펀더멘털·기술·심리·뉴스 분석가가 의견 → 강세/약세 리서처 반박 토론','종목별 논거'],
    ['<b>4</b> 리스크 심사','포트폴리오 관점(집중도·상관관계·변동성)에서 최종 채택 여부 결정','추천 리스트'],
    ['<b>5</b> 성과 추적','추천 시점·가격을 DB에 기록해 <b>사후 수익률을 검증</b>','스크리닝 성적표'],
  ]);

  tbl('tbl_auto',['단계','내용','되돌릴 수 있나'],[
    ['<b>1</b> 백테스트','④가 고른 종목을 과거 데이터로 검증 — 수수료·세금·슬리피지 반영','<span class="up">위험 없음</span>'],
    ['<b>2</b> 페이퍼 트레이딩','KIS <b>모의투자 계좌</b>로 실시간 주문 흐름 검증 (수개월)','<span class="up">위험 없음</span>'],
    ['<b>3</b> 안전장치 구현','킬 스위치·손실 한도·주문 한도·멱등키·감사 로그','<span class="up">위험 없음</span>'],
    ['<b>4</b> 소액 실계좌','잃어도 되는 금액만. 로그를 매일 눈으로 확인','<span class="dn">실제 손실 가능</span>'],
    ['<b>5</b> 단계적 증액','수개월간 페이퍼 결과와 실계좌 결과가 일치할 때만','<span class="dn">실제 손실 가능</span>'],
  ]);

  tbl('tbl_fire',['항목','왜 중요한가'],[
    ['<b>건강보험료</b>','퇴사 = 직장가입자 → <b>지역가입자</b>. 소득이 없어도 <b>재산·자동차</b>로 부과된다. 자산이 클수록 보험료도 크다'],
    ['<b>세금</b>','금융소득 2천만원 초과 시 종합과세. 해외주식 양도세 22%. 인출 방식에 따라 실수령액이 달라진다'],
    ['<b>국민연금 공백</b>','수령 개시(65세)까지의 <b>브리지 기간</b>을 자산으로 버텨야 한다. 조기 은퇴일수록 이 구간이 길다'],
    ['<b>인플레이션</b>','연 2~3%면 20년 뒤 생활비는 <b>1.5~1.8배</b>. 목표액을 명목으로 잡으면 부족해진다'],
    ['<b>수익률 순서 위험</b>','은퇴 <b>직후</b> 폭락하면 같은 평균 수익률이어도 자산이 먼저 고갈된다. 초기 몇 년이 결정적'],
    ['<b>지출의 현실</b>','시간이 남으면 지출이 는다. 의료비는 나이 들수록 는다. 과거 지출 실측으로 잡을 것'],
  ]);

  /* ── 경제적 자유 계산기 (순수 클라이언트 산수 · 서버 불필요) ── */
  const F={asset:20000,spend:4000,save:3000,ret:6,infl:2.5,swr:4};
  const FD=[['asset','현재 순자산','만원'],['spend','연간 지출','만원'],['save','연간 저축','만원'],
            ['ret','기대 수익률','%'],['infl','물가상승률','%'],['swr','인출률 (4%룰)','%']];
  const fin=document.getElementById('fire_in');
  if(fin){
    fin.innerHTML=FD.map(([k,l,u])=>
      `<div class="fr"><label for="f_${k}">${l}</label>
       <input id="f_${k}" type="number" step="any" value="${F[k]}"><span class="u">${u}</span></div>`).join('');
    let chart=null;
    const won=v=>v>=10000?`${(v/10000).toFixed(2)}억`:`${Math.round(v).toLocaleString()}만`;
    const calc=()=>{
      FD.forEach(([k])=>{const v=parseFloat(document.getElementById('f_'+k).value); if(!isNaN(v))F[k]=v;});
      const real=(1+F.ret/100)/(1+F.infl/100)-1;          // 실질 수익률
      const target=F.spend*(100/F.swr);                    // 목표 자산 (오늘 물가 기준)
      let a=F.asset, yrs=null; const path=[a];
      for(let y=1;y<=60;y++){ a=a*(1+real)+F.save; path.push(a); if(yrs===null&&a>=target){yrs=y;} }
      const rate=F.save/(F.save+F.spend)*100;              // 저축률
      const pct=Math.min(100,F.asset/target*100);
      const out=document.getElementById('fire_out');
      out.innerHTML=
        `<div class="fo"><span class="fl">퇴사까지</span><span class="fv big">${yrs===null?'60년+':yrs+'년'}</span></div>
         <div class="fo"><span class="fl">목표 순자산 <span class="note">(연지출 × ${(100/F.swr).toFixed(0)})</span></span><span class="fv">${won(target)}원</span></div>
         <div class="fo"><span class="fl">현재 진척률</span><span class="fv" style="color:${pct>=100?'var(--ok)':'var(--tx)'}">${pct.toFixed(1)}%</span></div>
         <div class="fo"><span class="fl">저축률</span><span class="fv">${rate.toFixed(1)}%</span></div>
         <div class="fo"><span class="fl">실질 수익률 <span class="note">(물가 차감)</span></span><span class="fv">${(real*100).toFixed(2)}%</span></div>
         <div class="fo"><span class="fl">은퇴 후 연 인출액</span><span class="fv">${won(target*F.swr/100)}원</span></div>
         <div class="note" style="margin-top:10px;line-height:1.5">모든 금액은 <b>오늘 물가 기준</b>(실질). 물가상승률을 수익률에서 차감해 계산하므로 목표액을 미래가치로 부풀릴 필요가 없다.</div>`;
      const cv=document.getElementById('c_fire');
      if(cv&&window.Chart){
        const n=Math.min(path.length, (yrs||40)+6);
        const data=path.slice(0,n).map(v=>Math.round(v/100));   // 만원 → 백만원
        if(chart)chart.destroy();
        chart=new Chart(cv,{type:'line',data:{labels:[...Array(n).keys()],
          datasets:[{label:'순자산',data,borderColor:'#1e9e6a',backgroundColor:'rgba(30,158,106,.08)',
                     fill:true,borderWidth:2,pointRadius:0,tension:.15},
                    {label:'목표',data:Array(n).fill(Math.round(target/100)),borderColor:'#d64545',
                     borderDash:[6,4],borderWidth:1.5,pointRadius:0,fill:false}]},
          options:{responsive:true,maintainAspectRatio:false,animation:false,
            plugins:{legend:{display:true,labels:{boxWidth:10,font:{size:10}}}},
            scales:{x:{title:{display:true,text:'연차',font:{size:10}},ticks:{font:{size:10}}},
                    y:{ticks:{font:{size:10}}}}}});
      }
    };
    fin.querySelectorAll('input').forEach(i=>i.addEventListener('input',calc));
    calc();
  }

  // (2026-07-26) 캘린더 페인 — calendar.html 과 같은 데이터(/api/db/events_calendar)를 대시보드 안에서 렌더
  let calLoaded=false;
  function renderCalPane(){
    if(calLoaded) return; calLoaded=true;
    const esc=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
    const impC=s=>String(s||'').includes('★★★')?'cal-imp3':(String(s||'').includes('★★')?'cal-imp2':'cal-imp1');
    const wd=d0=>{try{return ['일','월','화','수','목','금','토'][new Date(d0+'T00:00:00').getDay()]}catch(e){return ''}};
    const dd=d0=>{try{const t=new Date();t.setHours(0,0,0,0);const n=Math.round((new Date(d0+'T00:00:00')-t)/86400000);
      if(n===0)return '<span class="cal-dday cal-today">TODAY</span>';
      if(n>0&&n<=3)return `<span class="cal-dday cal-soon">D-${n}</span>`;
      if(n>0)return `<span class="cal-dday">D-${n}</span>`;
      return '';}catch(e){return ''}};
    const row=r=>`<tr><td><b>${esc((r.date||'').slice(5))}</b><span class="note">(${wd(r.date)})</span> ${dd(r.date)}</td>
      <td><span class="cal-region">${esc(r.region||'-')}</span></td><td>${esc(r.event||'')}</td>
      <td class="${impC(r.importance)}">${esc(r.importance||'')}</td><td class="note" style="font-size:11px">${esc(r.source||'')}</td></tr>`;
    fetch('/api/db/events_calendar').then(r=>r.json()).then(d=>{
      const g=i=>document.getElementById(i);
      g('cal_asof').textContent='갱신: '+(d.as_of||'');
      const today=new Date().toISOString().slice(0,10);
      // (2026-07-26) 다가오는/중장기 자체 표 삭제 — 2.1/2.2/2.3(d_ev·d_evl·d_evb, 이동해 옴)이 대체.
      //   여기서는 '지난 이벤트(최근 1주)'만 렌더한다.
      const wk=new Date(Date.now()-7*86400000).toISOString().slice(0,10); const seen=new Set();
      const past=[...(d.past||[]),...(d.upcoming||[])].filter(r=>r.date&&r.date<today&&r.date>=wk)
        .filter(r=>{const k=r.date+'|'+r.event; if(seen.has(k))return false; seen.add(k); return true;})
        .sort((a,b)=>b.date<a.date?-1:1);
      g('cal_past').insertAdjacentHTML('beforeend',
        past.map(r=>`<tr><td style="white-space:nowrap"><b>${esc((r.date||'').slice(5))}</b><span class="note">(${wd(r.date)})</span></td>
          <td>${esc(r.event||'')} <span class="cal-region">${esc(r.region||'-')}</span></td></tr>`).join('')
        ||'<tr><td colspan="2" class="note">최근 1주 지난 이벤트 없음 — 내일 갱신부터 쌓입니다</td></tr>');
    }).catch(e=>{const a=document.getElementById('cal_asof'); if(a)a.textContent='로드 실패';});
  }
  // (2026-07-26) 종목별 어닝 월간 달력 (구글캘린더식) — 풀 DB의 ed(실적발표일) 사용
  let calView='ev', mcY=new Date().getFullYear(), mcM=new Date().getMonth(); // 0-based month
  /* (2026-08-05) 실적 속보 스트립 — KR=DART 잠정실적(5분 감지) · US=Yahoo EPS 서프라이즈(15분 감지).
     반환: {byCode, days} — 달력 칩 ✅ 마킹·팝업 결과용.
     US 는 종목이 너무 많아 스트립엔 '서프라이즈(|스프|≥10%) 또는 시총 $100B↑ 주요종목'만 표시(사용자 요청). */
  function _ernStrip(live, mk){
    const box=document.getElementById('mc_live'); const byCode={};
    const days=(live&&live.days)||{};
    Object.keys(days).forEach(d=>days[d].forEach(it=>{ byCode[it.c]=Object.assign({d8:d},it); }));
    const keys=Object.keys(days).sort().slice(-3);          // 스트립은 최근 3영업일 (보관은 45일)
    if(!box) return {byCode, days};
    if(!keys.length){ box.style.display='none'; return {byCode, days}; }
    const E2=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
    const pct=v=>v==null?'<span class="note">—</span>':`<b class="${v>0?'up':(v<0?'dn':'')}">${v>0?'+':''}${(+v).toFixed(1)}%</b>`;
    const rows=keys.slice().reverse().map(d=>{
      let items=days[d].slice();
      /* (2026-08-05 사용자 확정) US 표시 규칙: 핵심 리스트(100종)만 항상 표시,
         그 외 전 종목은 서프라이즈(±10% & $2B↑ 잡음 컷)일 때만 */
      if(mk==='us') items=items.filter(it=>
        it.core || (it.spr!=null&&Math.abs(it.spr)>=10&&(it.cap||0)>=2e9));
      /* (2026-08-05 사용자 확정) 부호 그대로 내림차순: +큰 것 → 0 → −큰 것 · 수치 대기(null)=맨 뒤 */
      const _sv=it=>{ const v=mk==='us'?it.spr:it.op_yoy; return v==null?-1e18:v; };
      items.sort((a,b)=>_sv(b)-_sv(a));
      /* 일별 표시 상한 40 — 핵심(core) 종목은 상한에 밀리지 않게 보호 (2026-08-05 LLY 누락 수정) */
      if(mk==='us'&&items.length>40){
        const keep=new Set(items.filter(i=>i.core).map(i=>i.c));
        for(const i of items){ if(keep.size>=40) break; keep.add(i.c); }
        items=items.filter(i=>keep.has(i.c));
      }
      const chips=items.map(it=>{
        /* US 소스 표기 — (S)=SEC 8-K/6-K 감지 · (Y)=야후 EPS 확정 · 둘 다면 (S)(Y) */
        const t8=(it.tags||[]).find(t=>t.includes('접수'));
        const hasY=it.spr!=null||it.eps!=null;
        /* (S) 클릭 → SEC 원문(보도자료) — 야후 수치 대기 중에도 직접 확인 가능 */
        const secU=(it.cik&&it.acc)?`https://www.sec.gov/Archives/edgar/data/${it.cik}/${String(it.acc).replace(/-/g,'')}/`:null;
        const src=mk==='us'?`<b class="note" style="color:#8a6d3b">${t8?(secU?`<a href="${secU}" target="_blank" rel="noopener" title="SEC 원문(8-K 보도자료) 새 창" style="color:#8a6d3b;text-decoration:underline">(S)</a>`:'(S)'):''}${hasY?'(Y)':''}</b>`:'';
        const tg=(it.tags||[]).filter(t=>!(mk==='us'&&t.includes('접수')))   // 접수 태그는 (S)로 대체
          /* US 어닝비트/미스 태그의 수치는 본문 EPS서프와 중복 → 라벨만 표시 (2026-08-05) */
          .map(t=>mk==='us'?t.replace(/^(어닝비트|어닝미스)\s*[+\-−]?\d+(\.\d+)?%$/,'$1'):t)
          .map(t=>`<span class="mc-tag ${/급증|흑자|비트/.test(t)?'up':'dn'}">${E2(t)}</span>`).join('');
        const tip=mk==='us'
          ? `${it.n} (${it.c}) · EPS 실제 ${it.eps??'—'} vs 예상 ${it.est??'—'} · 서프라이즈 ${it.spr??'—'}%${t8?' · '+t8:''} · ${it.t} 수집`
          : `${it.n} (${it.cons}) · 매출 ${it.sales??'—'}억 (YoY ${it.sales_yoy??'—'}%) · 영업익 ${it.op??'—'}억 (YoY ${it.op_yoy??'—'}%) · 순이익YoY ${it.ni_yoy??'—'}% · ${it.t} 수집`;
        const val=mk==='us'
          ? (hasY?`EPS서프 ${pct(it.spr)}`:(t8?E2(t8.replace('📄 ','')):''))   // 야후 전이면 8-K 접수 내용 표시
          : `영업익 ${pct(it.op_yoy)}`;
        return `<span class="mc-live-it" title="${E2(tip)}"><b>${E2(it.n)}</b> ${val}${tg}${src}</span>`; }).join('');
      return `<div class="mc-live-day"><b class="note">${d.slice(4,6)}/${d.slice(6,8)} (${days[d].length}건${mk==='us'&&items.length<days[d].length?` · 표시 ${items.length}`:''})</b> ${chips}</div>`; }).join('');
    box.innerHTML=`<div class="mc-live-h">🔔 실적 속보 <span class="note" style="font-weight:400">${mk==='us'
      ?'— (S)=SEC 8-K 감지(1분) · (Y)=야후 EPS 확정(5분) · 핵심 100종 항상 표시, 그 외는 서프라이즈 ±10%만 · ✅=발표 완료(전 종목)'
      :'— DART 영업(잠정)실적 5분 주기 자동 감지 · 영업익 변화 큰 순 · 마우스오버=상세 · 달력의 ✅=발표 완료'}</span></div>${rows}`;
    box.style.display='';
    return {byCode, days};
  }
  /* (2026-08-05) SEC 8-K 워치리스트 관리 박스 — US 뷰 전용. 조회는 공개, 추가/삭제는 로그인 필요(서버 401). */
  let _w8kOpen = localStorage.getItem('w8k_open')==='1';
  function _w8kBox(mk){
    const box=document.getElementById('mc_8k'); if(!box) return;
    if(mk!=='us'){ box.style.display='none'; return; }
    fetch('/api/8k_watchlist').then(r=>r.ok?r.json():null).then(d=>{
      const syms=(d&&d.syms)||[];
      const E2=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
      const capF=v=>v==null?'':(v>=1e12?' $'+(v/1e12).toFixed(1)+'T':' $'+(v/1e9).toFixed(0)+'B');
      box.innerHTML=`<div style="display:flex;align-items:center;gap:8px;cursor:pointer" id="w8k_hd">
          <b style="font-size:12.5px">📄 SEC 8-K 감시 — 전 종목 · 핵심 리스트 ${syms.length}종</b>
          <span class="note">핵심 종목 관리 ${_w8kOpen?'▲':'▼'}</span></div>
        <div id="w8k_body" style="display:${_w8kOpen?'':'none'}">
          <div class="w8k-list">${syms.map(s=>
            `<span class="w8k-it" title="${E2(s.n)}${capF(s.cap)}"><b>${E2(s.c)}</b> <span class="note">${E2(s.n).slice(0,14)}</span><button class="w8k-x" data-del="${E2(s.c)}" title="감시에서 제거">✕</button></span>`).join('')}</div>
          <div style="display:flex;gap:6px;margin-top:6px;align-items:center">
            <input id="w8k_in" placeholder="티커 추가 (예: SNOW)" style="border:1px solid var(--line);border-radius:6px;padding:3px 8px;font-size:12px;width:160px" autocomplete="off">
            <button class="cp-x" id="w8k_add">＋ 추가</button>
            <span class="note">ADR(TSM 등)은 6-K 피드로 함께 감지 · 추가/삭제는 로그인 필요</span></div>
        </div>`;
      box.style.display='';
      document.getElementById('w8k_hd').onclick=()=>{ _w8kOpen=!_w8kOpen;
        localStorage.setItem('w8k_open',_w8kOpen?'1':'0'); _w8kBox(mk); };
      const post=q=>fetch('/api/8k_watchlist?'+q,{method:'POST'}).then(r=>{
        if(r.status===401){ alert('추가/삭제는 관리자 로그인이 필요합니다'); return null; }
        return r.ok?r.json():null; }).then(x=>{ if(x) _w8kBox(mk); });
      box.querySelectorAll('.w8k-x').forEach(b=>b.onclick=e=>{ e.stopPropagation();
        if(confirm(b.dataset.del+' 을 8-K 감시에서 제거할까요?')) post('remove='+encodeURIComponent(b.dataset.del)); });
      const inp=document.getElementById('w8k_in');
      const doAdd=()=>{ const v=(inp.value||'').trim().toUpperCase(); if(!v) return;
        post('add='+encodeURIComponent(v)); inp.value=''; };
      document.getElementById('w8k_add').onclick=doAdd;
      inp.onkeydown=e=>{ if(e.key==='Enter') doAdd(); };
    }).catch(()=>{ box.style.display='none'; });
  }
  function renderMonthCal(mk){
    const grid=document.getElementById('mc_grid'); if(!grid) return;
    _w8kBox(mk);
    const done=pool=>{ const build=LV=>{
      const LIVEBY=(LV&&LV.byCode)||{};
      const evs={};
      for(const r of (pool[mk]||[])) if(r.ed) (evs[r.ed]=evs[r.ed]||[]).push(r);
      /* (2026-08-05) 발표일 기준 칩 병합 — 예정일(ed)은 발표 후 다음 분기로 롤포워드돼
         과거 달에서 칩이 사라진다 → DART 실적속보의 접수일 기준으로 칩을 보완(✅ 포함) */
      if(LV&&LV.days){ for(const d8 in LV.days){
        const key=`${d8.slice(0,4)}-${d8.slice(4,6)}-${d8.slice(6,8)}`;
        for(const it of LV.days[d8]){ const lst=(evs[key]=evs[key]||[]);
          if(!lst.some(r=>r.c===it.c)) lst.push({c:it.c,n:it.n,cap:0}); } } }
      /* (2026-08-05) 발표 완료 종목은 '실제 발표일' 칸에만 — 예정일(ed)이 달라 다른 날에도
         적혀 있으면(예: 8/4 발표인데 예정일 8/5 칸에 그대로) 혼동되므로 그 칸에서 제거 */
      /* (2026-08-23) '발표 완료' 판정은 **실적 매칭이 있는 레코드**만 — 핵심 리스트 종목은
         실적이 아닌 일반 8-K(임원 변동·기타 공시)도 기록되는데, 레코드 존재만 보면 그
         일반 8-K 가 발표 완료로 오인돼 **예정일 칸에서 종목이 사라진다**.
         실측 NVDA: 8/17 일반 8-K(eps=null) 때문에 8/26 발표 예정 칸에서 제거돼
         시총 1위가 달력에 안 보였다(CRM 도 동일 경로). */
      /* (2026-08-23 2차) 수집기가 실적 여부를 ern 플래그로 명시 저장한다(8-K Item 2.02 판정).
         플래그가 있으면 그것이 정답이고, 플래그 이전의 옛 레코드만 휴리스틱으로 추정한다. */
      const isErn=lv=>!!lv&&(lv.ern!=null?lv.ern===1:(lv.eps!=null||lv.spr!=null||lv.op_yoy!=null||lv.sales_yoy!=null));
      if(LV){ for(const key in evs){ const k8=key.replace(/-/g,'');
        evs[key]=evs[key].filter(r=>{ const lv=LIVEBY[r.c]; return !isErn(lv) || lv.d8===k8; });
        if(!evs[key].length) delete evs[key]; } }
      for(const d in evs) evs[d].sort((a,b)=>(b.cap||0)-(a.cap||0));
      const first=new Date(mcY,mcM,1), off=first.getDay(), dim=new Date(mcY,mcM+1,0).getDate();
      const tds=new Date(); tds.setHours(0,0,0,0);
      const esc=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
      let h=['일','월','화','수','목','금','토'].map((w,i)=>`<div class="mc-wd ${i===0?'sun':i===6?'sat':''}">${w}</div>`).join('');
      const cells=Math.ceil((off+dim)/7)*7;
      let cnt=0;
      for(let i=0;i<cells;i++){
        const dnum=i-off+1, inM=dnum>=1&&dnum<=dim;
        const dt=new Date(mcY,mcM,dnum);
        const key=inM?`${mcY}-${String(mcM+1).padStart(2,'0')}-${String(dnum).padStart(2,'0')}`:null;
        const list=key?(evs[key]||[]):[];
        cnt+=list.length;
        const isT=inM&&dt.getTime()===tds.getTime();
        const wd=i%7;
        const chips=list.slice(0,4).map(r=>{
          const lv=LIVEBY[r.c];                        // (2026-08-05) 발표 완료 종목 ✅ + 결과 툴팁
          const ern=isErn(lv);                         // (2026-08-23) 일반 8-K 는 ✅로 표시하지 않는다
          const tip=ern?` — 발표됨: 영업익YoY ${lv.op_yoy??'—'}% · 매출YoY ${lv.sales_yoy??'—'}%${(lv.tags||[]).length?' · '+lv.tags.join('·'):''}`:'';
          return `<span class="mc-chip" title="${esc(mk==='kr'?r.n:((r.kn?r.kn+' · ':'')+r.n))} (${esc(r.c)}) 실적발표${esc(tip)}">${ern?'✅':''}${esc(mk==='kr'?r.n:(r.kn||r.c))}</span>`;}).join('')
          +(list.length>4?`<span class="mc-more">+${list.length-4}종 더 보기</span>`:'');
        h+=`<div class="mc-cell ${inM?'':'out'} ${isT?'tdy':''} ${list.length?'has':''}" ${list.length?`data-k="${key}"`:''}
             title="${list.length?'클릭하면 이날 전체 '+list.length+'종 표시':''}"><div class="mc-d ${wd===0?'sun':wd===6?'sat':''}">${inM?dnum:''}</div>${inM?chips:''}</div>`;
      }
      grid.innerHTML=h;
      /* (2026-07-26) 날짜 칸 클릭 → 그날 전체 종목 팝업 (많아서 잘린 날 대응) */
      grid.querySelectorAll('.mc-cell.has').forEach(cell=>cell.onclick=()=>{
        const key=cell.dataset.k, list=evs[key]||[];
        const wdn=['일','월','화','수','목','금','토'][new Date(key+'T00:00:00').getDay()];
        const old=document.querySelector('.mc-pop'); if(old) old.remove();
        const pop=document.createElement('div'); pop.className='mc-pop';
        /* (2026-08-09) 한 줄에 '실적 → 전망 → 주가'가 한눈에 들어오게 확장.
           실적만으로는 왜 움직였는지 모른다 — 샌디스크처럼 EPS 는 비트인데 가이던스가
           나빠 빠지는 경우가 흔하다. 그래서 ①서프라이즈 ②가이던스/컨센 ③주가반응을 같이 둔다. */
        const pct=(v,d)=>v==null?null:`<b class="${v>0?'up':(v<0?'dn':'note')}">${v>0?'+':''}${(+v).toFixed(d==null?1:d)}%</b>`;
        const row=(r,i)=>{
          const lv0=LIVEBY[r.c];
          /* (2026-08-23) 팝업도 isErn 기준 — 일반 8-K(임원·계약·RegFD) 레코드는 발표로
             취급하지 않는다. 실측: NVDA 8/17 일반 8-K 의 '접수 08:41ET · 수치 대기'가
             8/26 발표 예정 팝업에 ✅와 함께 새어 들어와, 발표가 이미 끝난 것처럼 보였다
             (달력 칩과 같은 버그의 팝업 경로 — SEC 확인 결과 8/17 은 Item 1.01/2.03/7.01). */
          const lv=isErn(lv0)?lv0:null;  // 발표 완료 → ✅ + 결과 요약
          const rv=lv?(mk==='us'?lv.spr:(lv.spr!=null?lv.spr:lv.op_yoy)):null;
          const t8p=lv&&(lv.tags||[]).find(t=>t.includes('접수'));
          const secU=(lv&&lv.cik&&lv.acc)?`https://www.sec.gov/Archives/edgar/data/${lv.cik}/${String(lv.acc).replace(/-/g,'')}/`:null;
          let res='';
          if(lv&&rv==null&&t8p){
            res=` <span class="note">— ${esc(t8p.replace('📄 ',''))} · <b>수치 대기</b>${secU?` · <a href="${secU}" target="_blank" rel="noopener">SEC 원문</a>`:''}</span>`;
          }else if(lv){
            const bits=[];
            /* ① 실적 — 컨센서스 대비. (2026-08-09) US 는 미국식 순서에 맞춰
               'EPS서프 + (실제 vs 컨센)' 을 한 덩어리로 보여 차트 팝업과 구조를 통일한다. */
            /* (2026-08-10) 미국은 실적발표 요약 템플릿 문구로 통일 —
               'EPS Consensus 대비 Beat/Miss' · 'Revenue Consensus 대비 …' (차트 팝업과 동일).
               YoY/QoQ·마진은 분기 재무가 필요해 종목 상세(차트 팝업)에서 제공한다. */
            if(mk==='us'){
              if(rv!=null) bits.push(`<b>EPS</b> Consensus 대비 ${rv>0?'Beat':'Miss'} ${pct(rv)}`
                + ((lv.eps!=null&&lv.est!=null)?` <span class="note">(Actual ${(+lv.eps).toFixed(2)} vs Consensus ${(+lv.est).toFixed(2)})</span>`:''));
              if(r.sspr!=null) bits.push(`<b>Revenue</b> Consensus 대비 ${r.sspr>0?'Beat':'Miss'} ${pct(r.sspr)}`);
            }else{
              bits.push(`${lv.spr!=null?'영업익 컨센比':'영업익YoY'} ${pct(rv)||'—'}`);
              if(lv.spr_s!=null) bits.push(`매출 컨센比 ${pct(lv.spr_s)}`);
            }
            if(mk==='kr'){
              const yy=[]; if(lv.sales_yoy!=null) yy.push('매출'+pct(lv.sales_yoy));
              if(lv.spr!=null&&lv.op_yoy!=null) yy.push('영업익'+pct(lv.op_yoy));
              if(lv.ni_yoy!=null) yy.push('순익'+pct(lv.ni_yoy));
              if(yy.length) bits.push(`<span class="note">YoY</span> ${yy.join(' ')}`);
              const qq=[]; if(lv.op_qoq!=null) qq.push('영업익'+pct(lv.op_qoq));
              if(lv.op_qturn) qq.push('⚡'+esc(lv.op_qturn));
              if(qq.length) bits.push(`<span class="note">QoQ</span> ${qq.join(' ')}`);
              if(lv.opm!=null) bits.push(`<span class="note">이익률</span> ${lv.opm}%${lv.opm_ch!=null?` (${lv.opm_ch>0?'+':''}${lv.opm_ch}%p)`:''}`);
            }
            /* ② 전망 — 가이던스 갭(US) / 컨센 30일 리비전(KR·US 공통)
               (2026-08-10) 매출·EPS 를 **둘 다** 보여주고, 어느 기간과 비교한 값인지
               라벨을 붙인다(우선순위 진행분기→다음분기→올해FY→내년FY · _GPER). */
            if(lv.g_rev_gap!=null) bits.push(`가이던스 매출 ${pct(lv.g_rev_gap)} <span class="note">vs ${_GPER(lv.g_rev_per||lv.g_per)} 컨센</span>`);
            if(lv.g_eps_gap!=null) bits.push(`가이던스 EPS ${pct(lv.g_eps_gap)} <span class="note">vs ${_GPER(lv.g_eps_per||lv.g_per)} 컨센</span>`);
            if(lv.cons_rev30!=null) bits.push(`<span class="note">컨센30일</span> ${pct(lv.cons_rev30*100)}`);
            // ③ 주가 — 실제로 어떻게 받아들였나
            const rr=[]; if(lv.r1!=null) rr.push(`D+1 ${pct(lv.r1)}`);
            if(lv.r5!=null) rr.push(`D+5 ${pct(lv.r5)}`);
            if(lv.r20!=null) rr.push(`D+20 ${pct(lv.r20)}`);
            if(rr.length) bits.push(rr.join(' '));
            const tg=(lv.tags||[]).filter(t=>!t.includes('접수'));
            if(tg.length) bits.push(esc(tg.join(' · ')));
            res=` <span class="note">— ${bits.join(' · ')}</span>`;
          }
          return `<div class="mc-pi" title="${esc(r.n)} (${esc(r.c)})"><span class="note">${i+1}.</span> ${lv?'✅':''}<b>${esc(mk==='kr'?r.n:r.c)}</b> ${mk==='us'&&r.kn?`<b class="uskn">${esc(r.kn)}</b> `:''}<span class="note">${esc(mk==='kr'?r.c:r.n)}</span>${res}</div>`;};
        /* (2026-08-05) 정렬 토글 — 시가총액순 / 서프라이즈순(발표분 우선, |값| 큰 순) */
        const sprLbl=mk==='us'?'EPS서프순':'실적서프순';
        const KEYF={spr:r=>{const lv=LIVEBY[r.c]||{}; return mk==='us'?lv.spr:(lv.spr!=null?lv.spr:lv.op_yoy);},
                    /* (2026-08-09) '비트인데 빠진 종목' 을 찾으려면 주가반응순이 필요하다 */
                    r1:r=>(LIVEBY[r.c]||{}).r1,
                    gap:r=>{const lv=LIVEBY[r.c]||{}; return lv.g_rev_gap!=null?lv.g_rev_gap:lv.g_eps_gap;}};
        const sorted=m=>{ const a=list.slice();
          if(KEYF[m]) a.sort((x,y)=>{const g=r=>{const v=KEYF[m](r); return v==null?-1e18:v;}; return g(y)-g(x);});
          else a.sort((x,y)=>((y.cap||(LIVEBY[y.c]||{}).cap||0)-(x.cap||(LIVEBY[x.c]||{}).cap||0)));
          return a; };
        let mode='cap';
        pop.innerHTML=`<div class="mc-pop-in"><div class="mc-pop-h">
            <b>📅 ${key} (${wdn}) 실적발표 — ${list.length}종</b>
            <span style="margin-left:auto;display:inline-flex;gap:4px">
              <button class="cp-x" id="mcp_scap">시가총액순</button>
              <button class="cp-x" id="mcp_sspr">${sprLbl}</button>
              <button class="cp-x" id="mcp_sr1">주가반응순</button>
              ${mk==='us'?'<button class="cp-x" id="mcp_sgap">가이던스갭순</button>':''}</span>
            <button class="cp-x" id="mcp_x">닫기 ✕</button></div>
          <div class="mc-pop-list"></div></div>`;
        const paint=()=>{ pop.querySelector('.mc-pop-list').innerHTML=sorted(mode).map(row).join('');
          [['mcp_scap','cap'],['mcp_sspr','spr'],['mcp_sr1','r1'],['mcp_sgap','gap']].forEach(([id,m])=>{
            const b=pop.querySelector('#'+id); if(!b) return;
            b.style.cssText=mode===m?'background:#1f6feb;color:#fff;border-color:#1f6feb':''; }); };
        [['mcp_scap','cap'],['mcp_sspr','spr'],['mcp_sr1','r1'],['mcp_sgap','gap']].forEach(([id,m])=>{
          const b=pop.querySelector('#'+id); if(b) b.onclick=()=>{ mode=m; paint(); }; });
        paint();
        pop.onclick=e=>{ if(e.target===pop) pop.remove(); };
        pop.querySelector('#mcp_x').onclick=()=>pop.remove();
        document.addEventListener('keydown',function esc0(e){ if(e.key==='Escape'){ pop.remove(); document.removeEventListener('keydown',esc0); } });
        document.body.appendChild(pop);
      });
      document.getElementById('mc_title').textContent=`${mcY}년 ${mcM+1}월`;
      document.getElementById('mc_note').textContent=
        (mk==='kr'?'네이버 IR 일정(대형주 위주)':'Yahoo earnings date')+` · 이 달 실적발표 ${cnt}건 · 셀당 최대 4종(시총순)`;
      };
      /* (2026-08-05) 실적 속보 로드 후 렌더(스트립 + 달력 ✅) — KR=DART · US=Yahoo 서프라이즈 */
      fetch(mk==='kr'?'/api/db/earnings_live':'/api/db/earnings_live_us').then(r=>r.ok?r.json():null)
        .then(lv=>build(_ernStrip(lv||{}, mk))).catch(()=>build(null));
    };
    if(window.nmrPool) window.nmrPool(done);
    else grid.innerHTML='<div class="note" style="grid-column:1/-1;padding:12px">풀 데이터 로드 중…</div>';
  }
  function calSwitch(v){
    calView=v;
    document.querySelectorAll('#p_cal .cvw').forEach(b=>b.classList.toggle('on',b.dataset.v===v));
    document.getElementById('cal_v_ev').style.display = v==='ev'?'':'none';
    document.getElementById('cal_v_stock').style.display = v==='ev'?'none':'';
    if(v!=='ev') renderMonthCal(v);
  }
  document.querySelectorAll('#p_cal .cvw').forEach(b=>b.addEventListener('click',()=>calSwitch(b.dataset.v)));
  {const p=document.getElementById('mc_prev'), n=document.getElementById('mc_next');
   if(p) p.onclick=()=>{ mcM--; if(mcM<0){mcM=11;mcY--;} renderMonthCal(calView); };
   if(n) n.onclick=()=>{ mcM++; if(mcM>11){mcM=0;mcY++;} renderMonthCal(calView); };}
  // (2026-07-26) ETF 스크리너 골격 — 필터 후보 미리보기
  {const ep=document.getElementById('etf_prev');
   if(ep) ep.innerHTML=[
     '<b>공통 후보</b>: 운용자산(AUM) · 거래대금 · 총보수(TER) · 상장기간 · 기간수익률(1M/3M/6M/1Y) · 변동성 · 200일선 · 고점比 · 배당(분배금)수익률',
     '<b>한국 전용 후보</b>: 괴리율(시장가−iNAV) · 추적오차 · 자산군(주식/채권/원자재/커버드콜…) · 운용사 · 레버리지/인버스 구분 · 분배금 주기(월배당 등)',
     '<b>미국 전용 후보</b>: expense ratio · AUM($) · 자산군/테마 · 옵션 유동성 · 레버리지 배수',
   ].map(x=>'· '+x).join('<br>');}
  // 탭 전환
  const panes=['p_welcome','p_daily','p_db','p_ai','p_ta','p_auto','p_fire','p_screener','p_vis','p_cal','p_etf','p_estate','p_global','p_trends','p_hobby','p_kpop','p_kcons','p_moat','p_share','p_debt','p_sub','p_pf','p_re','p_re3','p_eg'];  // p_eg: (2026-09-01) 이익성장 탭 (eg.js)  // p_sub: 청약 탭 (sub.js) · p_pf: (2026-08-23) Portfolio 탭 (pf.js) · p_re: (2026-08-23) RE 예측 탭 (re.js) — 여기 안 넣으면 탭 눌러도 빈 화면(실측)
  {const hb=document.getElementById('go_home');          // 제목 클릭 → 홈(인사 화면)
   if(hb) hb.addEventListener('click',()=>{
     document.querySelectorAll('.tab').forEach(x=>x.classList.remove('on'));
     const sb=document.getElementById('btn_screener'); if(sb) sb.classList.remove('on');
     panes.forEach(id=>{const el=document.getElementById(id); if(el) el.classList.toggle('on', id==='p_welcome');});
   });}
  {const wm=document.getElementById('wel_msg');          // 최초 진입 인사 (시간대별)
   if(wm){const h=new Date().getHours();
     wm.textContent = (h>=5&&h<11)?'좋은 아침입니다' : (h>=11&&h<17)?'좋은 점심입니다'
                    : (h>=17&&h<21)?'좋은 저녁입니다' : '좋은 밤입니다';}}
  document.querySelectorAll('.tab').forEach(b=>b.addEventListener('click',()=>{
    if(b.disabled||b.classList.contains('off')) return;   // 비활성 탭은 무시
    document.querySelectorAll('.tab').forEach(x=>x.classList.toggle('on',x===b));
    panes.forEach(id=>{const el=document.getElementById(id);
      if(el) el.classList.toggle('on', id===b.dataset.pane);});
    const sb=document.getElementById('btn_screener'); if(sb) sb.classList.remove('on');
    if(b.dataset.pane==='p_cal') renderCalPane();
    if(b.dataset.pane==='p_estate'&&window.renderEstate) window.renderEstate();
    if(b.dataset.pane==='p_global'&&window.renderGlobal) window.renderGlobal();
    if(b.dataset.pane==='p_db'&&window.renderVeps) window.renderVeps();
    if(b.dataset.pane==='p_trends'&&window.renderTrends) window.renderTrends();
    if(b.dataset.pane==='p_hobby'&&window.renderHobby) window.renderHobby();
    if(b.dataset.pane==='p_kpop'&&window.renderKpop) window.renderKpop();   // (2026-08-29) K-POP 선행지표
    if(b.dataset.pane==='p_kcons'&&window.renderKcons) window.renderKcons(); // (2026-08-29) K-소비재 선행지표
    if(b.dataset.pane==='p_moat'&&window.renderMoat) window.renderMoat();    // (2026-08-30) 해자 워치
    if(b.dataset.pane==='p_share'&&window.renderShare) window.renderShare();  // (2026-08-31) 점유율 추이
    if(b.dataset.pane==='p_debt'&&window.renderDebt) window.renderDebt();    // (2026-08-31) 빅테크 조달구조
    /* (2026-08-05) 숨김 상태에서 생성된 Chart.js 는 0×0 으로 남는다(실측: 3.1.10 3×3 그리드)
       → 탭을 열 때 크기 없는 차트만 골라 resize */
    if(window.Chart&&Chart.getChart) setTimeout(()=>{
      document.querySelectorAll('#'+b.dataset.pane+' canvas').forEach(c=>{
        const ch=Chart.getChart(c); if(ch&&(!c.width||!c.height)) ch.resize(); });},80);
  }));
  // 사이드바 SCREENER 버튼 → p_screener 페인 (상단 탭과 독립)
  const sbtn=document.getElementById('btn_screener');
  if(sbtn) sbtn.addEventListener('click',()=>{
    document.querySelectorAll('.tab').forEach(x=>x.classList.remove('on'));
    panes.forEach(id=>{const el=document.getElementById(id); if(el) el.classList.toggle('on', id==='p_screener');});
    sbtn.classList.add('on');
    if(window.renderScreener) window.renderScreener();
  });
})();

/* ── (2026-08-01) 🏠 부동산 탭 — ECOS 월간(전망CSI·매매/전세지수·주담대금리) ── */
(function(){
  let loaded=false;
  const $=id=>document.getElementById(id);
  function line(cvId, arr, opts){
    /* arr=[{t:[YYYYMM],v:[],label,color}] — 간단 멀티라인: y축 5눈금·연도 x축·기준선·최신값 배지 */
    const cv=$(cvId); if(!cv) return;
    const W=cv.clientWidth||700,H=cv.clientHeight||230; cv.width=W; cv.height=H;
    const x=cv.getContext('2d'); x.clearRect(0,0,W,H);
    // (2026-08-08) 계열이 비면 지우고 끝낸다 — 호출부마다 잔상 제거를 빠뜨리는 실수를 원천 차단
    if(!arr||!arr.length||!arr.some(a=>a&&a.v&&a.v.some(v=>v!=null))) return;
    /* (2026-08-10) opts.r2 = 보조축(좌측) 계열 — bars() 와 같은 규칙.
       단위가 다른 지표(예: 12개월 누적 증감 '조원' vs 주택 거래량 '건')를 겹쳐 본다. */
    const R2=(opts&&opts.r2&&opts.r2.length&&opts.r2.some(s=>s.v&&s.v.some(v=>v!=null)))?opts.r2:null;
    const P={l:R2?46:8,r:52,t:10,b:18};
    const N=Math.max(...arr.map(a=>a.v.length));
    const all=arr.flatMap(a=>a.v).filter(v=>v!=null);
    /* (2026-08-08) 로그 스케일 — 청약경쟁률처럼 0.02~35,000 같이 자릿수가 크게 벌어지는
       지표는 선형축에서 이상치 하나가 나머지를 전부 바닥에 눌러버린다. */
    const LG=!!(opts&&opts.log);
    const tf=v=>LG?Math.log10(Math.max(v,0.01)):v;
    const itf=y=>LG?Math.pow(10,y):y;
    let lo=Math.min(...all.map(tf)), hi=Math.max(...all.map(tf));
    if(opts&&opts.base!=null){ lo=Math.min(lo,tf(opts.base)); hi=Math.max(hi,tf(opts.base)); }
    const pad=(hi-lo)*0.06||(LG?0.2:1); lo-=pad; hi+=pad;
    const X=i=>P.l+(W-P.l-P.r)*i/Math.max(1,N-1), Y=v=>P.t+(H-P.t-P.b)*(1-(tf(v)-lo)/(hi-lo));
    const fmtA=v=>v>=1000?Math.round(v).toLocaleString():(v>=10?v.toFixed(0):v.toFixed(v<1?2:1));
    x.font='10px sans-serif'; x.strokeStyle='#eceff3'; x.fillStyle='#98a2ad';
    for(let g=0;g<=4;g++){ const yv=lo+(hi-lo)*g/4, y=P.t+(H-P.t-P.b)*(1-(yv-lo)/(hi-lo));
      x.beginPath();x.moveTo(P.l,y);x.lineTo(W-P.r,y);x.stroke();
      x.fillText(LG?fmtA(itf(yv)):yv.toFixed(hi-lo<10?1:0),W-P.r+4,y+3); }
    if(opts&&opts.base!=null){ x.setLineDash([4,3]); x.strokeStyle='#b7860b';
      x.beginPath();x.moveTo(P.l,Y(opts.base));x.lineTo(W-P.r,Y(opts.base));x.stroke(); x.setLineDash([]);
      x.fillStyle='#b7860b'; x.fillText(String(opts.base),P.l+2,Y(opts.base)-3); }
    /* (2026-08-02 → 2026-08-08 정밀화) 잠정 구간 표시.
       기존엔 경계선을 '첫 잠정 월' 위치에 그어 음영을 시작했는데, 그러면 첫 잠정 점이
       음영의 왼쪽 끝선 위에 정확히 얹혀 확정치처럼 보인다. 실제로 이 때문에
       "잠정 직전엔 은평구가 1등인데 순위는 4등"이라는 오해가 생겼다(그 값은 잠정 7월치였다).
       → 경계선을 마지막 확정 월과 첫 잠정 월의 **중간**으로 옮겨, 모든 잠정 점이
         음영 안쪽에 확실히 들어오게 한다. 잠정 점은 아래에서 선까지 점선으로 그린다. */
    const PI=(opts&&opts.provIdx!=null&&opts.provIdx>0&&opts.provIdx<N)?opts.provIdx:null;
    if(PI!=null){
      const x0=(X(PI)+X(PI-1))/2;
      x.fillStyle='rgba(230,140,0,0.10)'; x.fillRect(x0,P.t,(W-P.r)-x0,H-P.t-P.b);
      x.save(); x.setLineDash([3,3]); x.strokeStyle='#e08e3c'; x.lineWidth=1.4;
      x.beginPath(); x.moveTo(x0,P.t); x.lineTo(x0,H-P.b); x.stroke(); x.restore();
      const fm=s=>{s=String(s); return s.length===6?`${s.slice(0,4)}.${s.slice(4)}`:s;};
      x.fillStyle='#c47b1e'; x.fillText(`⚠ 여기부터 잠정(${fm(arr[0].t[PI])}~) — 신고 진행 중`,x0+4,P.t+10);
      x.fillStyle='#5b6673'; x.textAlign='right';
      x.fillText(`확정 최신 ${fm(arr[0].t[PI-1])} ▶`,x0-4,P.t+10); x.textAlign='left'; }
    /* 순위 기준월 — 몇 월로 줄 세웠는지 월까지 같이 적는다. */
    if(opts&&opts.refIdx!=null&&opts.refIdx>=0&&opts.refIdx<N){
      const xr=X(opts.refIdx), rs=String(arr[0].t[opts.refIdx]);
      x.save(); x.setLineDash([2,3]); x.strokeStyle='#1f2937'; x.globalAlpha=.5;
      x.beginPath(); x.moveTo(xr,P.t+14); x.lineTo(xr,H-P.b); x.stroke(); x.restore();
      x.fillStyle='#1f2937'; x.textAlign='center';
      x.fillText(`▲순위 기준 ${rs.length===6?rs.slice(0,4)+'.'+rs.slice(4):rs}`,xr,H-P.b-3); x.textAlign='left'; }
    const t0=arr[0].t;                                  // X축 눈금 — 연간(YYYY)·월간(YYYYMM) 모두 지원
    x.fillStyle='#98a2ad';
    for(let i=0;i<t0.length;i++){ const s=String(t0[i]);
      if(s.length===4){ if(+s%2===0) x.fillText(s,X(i)-12,H-4); }                                  // 연간: 짝수 해
      else if(s.slice(4)==='01'){ x.fillText(s.slice(0,4),X(i)-12,H-4); }                          // 월간: 매년 1월=연도
      else if(t0.length<=30&&+s.slice(4)%3===1){ x.fillText(s.slice(2,4)+'.'+s.slice(4),X(i)-10,H-4); } }  // 확대 시 분기 보조 눈금
    /* (2026-08-08) 계열이 많아지면(최대 30) ① 선이 구분 안 되고 ② 우측 라벨이 겹쳐 못 읽는다.
       → hi(강조 대상)가 있으면 나머지를 흐리게, 라벨은 세로 충돌을 밀어내 배치한다. */
    const HI=opts&&opts.hi;
    const ordered=HI?[...arr.filter(a=>a.label!==HI),...arr.filter(a=>a.label===HI)]:arr;
    ordered.forEach(a=>{ const on=!HI||a.label===HI;
      x.save(); x.globalAlpha=on?1:0.15;
      x.strokeStyle=a.color; x.lineWidth=on&&HI?2.6:1.6;
      /* 확정 구간은 실선, 잠정 구간은 점선 — 선 모양만 봐도 어느 점이 잠정인지 알 수 있게. */
      const seg=(a0,a1,dash)=>{ x.save(); if(dash) x.setLineDash([4,3]);
        x.beginPath(); let st=false;
        for(let i=a0;i<=a1&&i<a.v.length;i++){ if(a.v[i]==null) continue;
          st?x.lineTo(X(i),Y(a.v[i])):(x.moveTo(X(i),Y(a.v[i])),st=true); }
        x.stroke(); x.restore(); };
      if(PI!=null){ seg(0,PI-1,false); seg(PI-1,a.v.length-1,true);
        for(let i=PI;i<a.v.length;i++) if(a.v[i]!=null){      // 잠정 점은 속 빈 원으로
          x.beginPath(); x.arc(X(i),Y(a.v[i]),on&&HI?3:2.2,0,7);
          x.fillStyle='#fff'; x.fill(); x.stroke(); } }
      else seg(0,a.v.length-1,false);
      x.restore(); });
    x.lineWidth=1;
    if(R2){                                              // 보조축 — 눈금은 좌측에, 선은 약간 투명
      let l2=Infinity,h2=-Infinity;
      R2.forEach(s=>s.v.forEach(v=>{ if(v==null) return; if(v<l2)l2=v; if(v>h2)h2=v; }));
      if(h2===l2){ h2=l2+1; }
      const p2=(h2-l2)*0.10; l2-=p2; h2+=p2;
      const Y2=v=>P.t+(H-P.t-P.b)*(1-(v-l2)/(h2-l2));
      x.save(); x.font='10px sans-serif'; x.fillStyle='#98a2ad';
      for(let g=0;g<=4;g++){ const yv=l2+(h2-l2)*g/4;
        x.fillText(Math.round(yv).toLocaleString(), 2, Y2(yv)+3); }
      const lb2=[];
      R2.forEach(s=>{ x.strokeStyle=s.color; x.lineWidth=1.9; x.globalAlpha=.95;
        x.beginPath(); let st=false;
        for(let i=0;i<s.v.length;i++){ const v=s.v[i]; if(v==null) continue;
          st?x.lineTo(X(i),Y2(v)):(x.moveTo(X(i),Y2(v)),st=true); }
        x.stroke();
        let li=-1; for(let i=s.v.length-1;i>=0;i--) if(s.v[i]!=null){li=i;break;}
        if(li>=0) lb2.push({s, li, y:Y2(s.v[li])}); });
      /* (2026-08-16) 중복 선택으로 계열이 여러 개면 우측 끝 라벨이 겹쳐 못 읽는다 —
         본선 라벨과 같은 방식으로 위아래 최소 간격을 확보한다. */
      lb2.sort((p,q)=>p.y-q.y);
      const G2=11;
      for(let i=1;i<lb2.length;i++) if(lb2[i].y-lb2[i-1].y<G2) lb2[i].y=lb2[i-1].y+G2;
      x.globalAlpha=1;
      lb2.forEach(L=>{ x.fillStyle=L.s.color;
        const v=L.s.v[L.li];
        const tx=L.s.label+' '+(Math.abs(v)>=100?Math.round(v).toLocaleString():v.toFixed(1));
        x.fillText(tx, Math.max(P.l+2, X(L.li)-x.measureText(tx).width-4), L.y-4); });
      x.restore(); }
    /* 라벨 — 마지막 값 위치를 기준으로 잡되, 위아래로 겹치면 최소 간격만큼 밀어낸다 */
    const labs=[];
    arr.forEach(a=>{ let li=-1; for(let i=a.v.length-1;i>=0;i--) if(a.v[i]!=null){li=i;break;}
      if(li<0) return;
      labs.push({a, li, y:Y(a.v[li]), v:a.v[li]}); });
    labs.sort((p,q)=>p.y-q.y);
    const GAP=11;
    for(let i=1;i<labs.length;i++) if(labs[i].y-labs[i-1].y<GAP) labs[i].y=labs[i-1].y+GAP;
    for(let i=labs.length-1;i>0;i--) if(labs[i].y>H-P.b) labs[i].y=H-P.b, (labs[i-1].y=Math.min(labs[i-1].y,labs[i].y-GAP));
    labs.forEach(L=>{ const on=!HI||L.a.label===HI;
      x.save(); x.globalAlpha=on?1:0.25;
      x.fillStyle=L.a.color; x.font=(on&&hi?'bold ':'')+'10px sans-serif';
      const t=L.a.label+' '+(L.v>=1000?Math.round(L.v).toLocaleString():L.v.toFixed(L.v<1?2:1));
      x.fillText(t, Math.max(P.l+2, X(L.li)-x.measureText(t).width-4), L.y+3);
      x.restore(); });
    x.font='10px sans-serif';
  }
  const yoy=(t,v)=>{ const i=t.length-1, j=t.indexOf(String(+String(t[i]).slice(0,4)-1)+String(t[i]).slice(4));
    return (i>=0&&j>=0&&v[j])?((v[i]/v[j]-1)*100):null; };
  const fm=t=>t?`${String(t).slice(0,4)}.${String(t).slice(4)}`:'—';
  /* (2026-08-06) 🏃 취미(운동) 탭 — sports_events.json (LLM 조사 · 분기 갱신) 렌더.
     리스트(대회일 순·카테고리 뱃지) + 월 변경 가능한 달력(대회일 뱃지 표시) */
  let _hbLoaded=false, _hbEv=[], _hbY=0, _hbM=0;
  window.renderHobby=function(){
    if(_hbLoaded){ return; } _hbLoaded=true;
    const E3=s=>String(s??'').replace(/&/g,'&amp;').replace(/</g,'&lt;');
    const CATC={'마라톤(해외 메이저)':'#4338ca','마라톤(한국)':'#2f6fed','울트라(한국)':'#0e7490',
                '트레일(한국)':'#047857','트레일(해외)':'#65a30d','철인3종(한국)':'#b45309',
                '하이록스':'#be185d','스파르탄':'#7c2d12','쉬엄쉬엄3종':'#8b5cf6','기타':'#64748b'};
    fetch('/api/db/sports_events').then(x=>x.ok?x.json():null).then(d=>{
      if(!d||!d.events) return;
      _hbEv=d.events.slice().sort((a,b)=>a.date<b.date?-1:1);
      {const e=document.getElementById('hb_asof'); if(e) e.textContent=`조사 ${d.asof||''} · (추정)은 예년 패턴 — 공식 발표 시 갱신`;}
      const now=new Date(); _hbY=now.getFullYear(); _hbM=now.getMonth();
      const draw=()=>{
        const y=_hbY,m=_hbM;
        document.getElementById('hb_ym').textContent=`${y}년 ${m+1}월`;
        const first=new Date(y,m,1), start=first.getDay(), dim=new Date(y,m+1,0).getDate();
        const pre=`${y}-${String(m+1).padStart(2,'0')}-`;
        const evs={}, regs={};
        let mc=0, rc=0;
        for(const ev of _hbEv){
          if(ev.date.startsWith(pre)){ const dd=+ev.date.slice(8); (evs[dd]=evs[dd]||[]).push(ev); mc++; }
          if(ev.regStart&&ev.regStart.startsWith(pre)){ const dd=+ev.regStart.slice(8); (regs[dd]=regs[dd]||[]).push(ev); rc++; }
        }
        document.getElementById('hb_mcnt').textContent=`— 이 달 대회 ${mc}건 · 접수 시작 ${rc}건`;
        let html='<tr>'+['일','월','화','수','목','금','토'].map((w,i)=>`<th style="text-align:center;color:${i===0?'#e0442c':i===6?'#2f6fed':'inherit'}">${w}</th>`).join('')+'</tr><tr>';
        for(let i=0;i<start;i++) html+='<td></td>';
        for(let dd=1;dd<=dim;dd++){
          const dow=(start+dd-1)%7;
          const today=(y===now.getFullYear()&&m===now.getMonth()&&dd===now.getDate());
          html+=`<td style="vertical-align:top;height:74px;border:1px solid #eef1f5;padding:3px 4px${today?';background:#fffbe6':''}">
            <div class="note" style="color:${dow===0?'#e0442c':dow===6?'#2f6fed':'#8a94a3'}">${dd}</div>
            ${(evs[dd]||[]).map(ev=>`<a href="${E3(ev.url)}" target="_blank" title="🏁 대회일 — ${E3(ev.name)} · ${E3(ev.place)} · 신청: ${E3(ev.reg)}"
              style="display:block;font-size:10.5px;line-height:1.3;margin-top:2px;padding:1px 4px;border-radius:4px;background:${CATC[ev.cat]||'#64748b'};color:#fff;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${E3(ev.name.replace(/ 20\d\d.*$/,''))}${ev.est?' (추정)':''}</a>`).join('')}
            ${(regs[dd]||[]).map(ev=>`<a href="${E3(ev.url)}" target="_blank" title="📝 접수 시작 — ${E3(ev.name)} · ${E3(ev.reg)} · 대회일 ${E3(ev.date)}"
              style="display:block;font-size:10.5px;line-height:1.3;margin-top:2px;padding:0 3px;border-radius:4px;border:1.5px dashed ${CATC[ev.cat]||'#64748b'};color:${CATC[ev.cat]||'#64748b'};background:#fff;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">📝 ${E3(ev.name.replace(/ 20\d\d.*$/,''))}${ev.est?' (추정)':''}</a>`).join('')}
          </td>`;
          if(dow===6&&dd<dim) html+='</tr><tr>';
        }
        html+='</tr>';
        document.getElementById('hb_cal').innerHTML=html;
      };
      document.getElementById('hb_prev').onclick=()=>{ _hbM--; if(_hbM<0){_hbM=11;_hbY--;} draw(); };
      document.getElementById('hb_next').onclick=()=>{ _hbM++; if(_hbM>11){_hbM=0;_hbY++;} draw(); };
      draw();
      // 리스트 — 카테고리별 그룹 (좌: 한국 대회 · 우: 외국 대회 — 2026-08-07)
      //   표시 순서: 마라톤→트레일→철인3종→울트라→하이록스→스파르탄→기타 (쉬엄쉬엄3종은 기타에 포함)
      const mapC=c=>c==='쉬엄쉬엄3종'?'기타':c;
      const ord=c=>{ const K=['마라톤','트레일','철인','울트라','하이록스','스파르탄'];
        for(let i=0;i<K.length;i++) if(c.includes(K[i])) return i; return 9; };
      const cats=[...new Set(_hbEv.map(e=>mapC(e.cat)))].sort((a,b)=>ord(a)-ord(b));
      const isFg=c=>/해외|메이저/.test(c);
      // (2026-08-09) 접수 상태 자동 판별 — 마감/접수중/예정
      const regStat=r=>/(접수 마감|\(마감|마감\)|SOLD OUT|접수는 종료|추첨 종료)/i.test(r)?['마감','#94a3b8']
        :/(접수 중|접수중|진행 중|진행중|현재 접수|판매 중|접수 진행)/.test(r)?['접수중','#1a9850']
        :['예정','#f2a72e'];
      const stChip=r=>{const s=regStat(r);
        return `<span style="display:inline-block;font-size:10.5px;font-weight:700;padding:0 6px;border-radius:8px;background:${s[1]};color:#fff;margin-right:6px;vertical-align:1px">${s[0]}</span>`;};
      const catBox=c=>{
        const rows=_hbEv.filter(e=>mapC(e.cat)===c);
        return `<div class="box" style="margin-bottom:10px"><b style="font-size:13px"><span style="display:inline-block;width:10px;height:10px;border-radius:3px;background:${CATC[c]||'#64748b'};margin-right:6px"></span>${E3(c)} <span class="note">(${rows.length})</span></b>
          <table style="margin-top:4px"><tr><th style="width:110px">대회일</th><th>대회명</th><th>장소</th><th>신청 접수</th></tr>
          ${rows.map(ev=>{
            const past=ev.date<'2026-08-06'?' style="opacity:.55"':'';
            const hot=/⚠️/.test(ev.reg)?' <span style="color:#e0442c;font-weight:700">⚠️</span>':'';
            return `<tr${past}><td class="num" style="text-align:left"><b>${ev.date}</b>${ev.est?' <span class="note">(추정)</span>':''}</td>
              <td>${stChip(ev.reg)}<a href="${E3(ev.url)}" target="_blank"><b>${E3(ev.name)}</b></a>${hot}</td>
              <td class="note">${E3(ev.place)}</td><td class="note" style="font-size:12px">${E3(ev.reg)}</td></tr>`;
          }).join('')}</table></div>`;
      };
      document.getElementById('hb_list').innerHTML=
        `<div class="note" style="margin:4px 0 8px">접수 상태: ${stChip('접수 중')}지금 신청 가능 &nbsp;${stChip('예정')}접수 전(오픈 대기) &nbsp;${stChip('(마감)')}접수 종료</div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:0 12px;align-items:start">
          <div><div class="note" style="margin:2px 0 6px"><b>🇰🇷 한국 대회</b></div>${cats.filter(c=>!isFg(c)).map(catBox).join('')}</div>
          <div><div class="note" style="margin:2px 0 6px"><b>🌍 외국 대회</b></div>${cats.filter(isFg).map(catBox).join('')}</div>
        </div>`;
    }).catch(()=>{});
  };
  /* (2026-08-06) 📈 Trends 탭 — trends_collect.py(무토큰 일일 수집) 렌더.
     구글 RSS·네이버 쇼핑 XHR·유튜브 API(키 있을 때) + 주간 등장일수 자체 집계 */
  let _trLoaded=false;
  window.renderTrends=function(){
    if(_trLoaded) return; _trLoaded=true;
    const E2=s=>String(s??'').replace(/&/g,'&amp;').replace(/</g,'&lt;');
    fetch('/api/db/trends').then(r=>r.ok?r.json():null).then(d=>{
      if(!d){ const e=document.getElementById('tr_asof'); if(e) e.textContent='데이터 없음 — 첫 수집(05:50) 대기'; return; }
      {const e=document.getElementById('tr_asof'); if(e) e.textContent=`수집 ${d.asof||''} · 매일 05:50 무토큰 자동`;}
      // (2026-08-06) 글로벌 표엔 '한글' 열 — 서버 gtx 무토큰 번역(수집 시 생성)
      const gtbl=(id,rows,ko)=>{ const t=document.getElementById(id); if(!t) return;
        t.innerHTML=`<tr><th style="width:26px">#</th><th>검색어</th>${ko?'<th>한글</th>':''}<th style="width:64px">검색량</th><th>관련 뉴스${ko?' (한글 번역)':''}</th></tr>`+
          (rows||[]).slice(0,15).map((r,i)=>`<tr><td class="note">${i+1}</td>
            <td><b>${E2(r.kw)}</b></td>${ko?`<td>${E2(r.ko||'')}</td>`:''}<td class="note">${E2(r.tf)}</td>
            <td class="note" style="font-size:12px">${r.url?`<a href="${E2(r.url)}" target="_blank">${E2(ko&&r.news_ko?r.news_ko:r.news)}</a>`:E2(ko&&r.news_ko?r.news_ko:r.news)}</td></tr>`).join('')
          ||'<tr><td class="note">—</td></tr>'; };
      gtbl('tr_gkr',d.g_kr,false); gtbl('tr_gus',d.g_us,true);
      // 유튜브 — 키 미등록이면 안내만
      const off=document.getElementById('tr_yt_off'), grid=document.getElementById('tr_yt_grid');
      if(!d.yt_enabled){ if(off)off.style.display='block'; if(grid)grid.style.display='none'; }
      else{
        const ytbl=(id,rows,ko)=>{ const t=document.getElementById(id); if(!t) return;
          t.innerHTML=`<tr><th style="width:26px">#</th><th>영상</th>${ko?'<th>한글</th>':''}<th>채널</th><th style="width:70px;text-align:right">조회수</th></tr>`+
            (rows||[]).slice(0,15).map((r,i)=>`<tr><td class="note">${i+1}</td>
              <td style="font-size:12px"><a href="https://www.youtube.com/watch?v=${E2(r.id)}" target="_blank">${E2(r.t)}</a></td>
              ${ko?`<td class="note" style="font-size:12px">${E2(r.ko||'')}</td>`:''}
              <td class="note">${E2(r.ch)}</td><td class="num">${(r.v/1e4).toFixed(0)}만</td></tr>`).join(''); };
        ytbl('tr_ykr',d.y_kr,false); ytbl('tr_yus',d.y_us,true); }
      // 네이버 쇼핑 — 분야별 카드
      const nv=document.getElementById('tr_naver');
      if(nv) nv.innerHTML=Object.entries(d.naver_shop||{}).map(([cat,kws])=>`<div class="box">
        <b style="font-size:13px">${E2(cat)}</b><table>${(kws||[]).slice(0,10).map((k,i)=>
          `<tr><td class="note" style="width:24px">${i+1}</td><td>${E2(k)}</td></tr>`).join('')}</table></div>`).join('');
      // 주간 자체 집계
      const wkEl=document.getElementById('tr_weekly');
      const WKL={g_kr:'🔍 구글 주간 (한국)',g_us:'🔍 구글 주간 (글로벌)',y_kr:'▶️ 유튜브 주간 (한국)',y_us:'▶️ 유튜브 주간 (글로벌)'};
      if(wkEl) wkEl.innerHTML=Object.entries(d.weekly||{}).filter(([k,v])=>v&&v.length&&(d.yt_enabled||k.startsWith('g_'))).map(([k,v])=>`<div class="box">
        <b style="font-size:13px">${WKL[k]||k}</b><table><tr><th style="width:26px">#</th><th>키워드/채널</th><th style="width:70px;text-align:right">등장일수</th></tr>
        ${v.slice(0,10).map(([kw,n],i)=>`<tr><td class="note">${i+1}</td><td>${E2(kw)}</td><td class="num">${n}일</td></tr>`).join('')}</table></div>`).join('');
      {const e=document.getElementById('tr_wk_note'); if(e) e.textContent=`— 누적 ${d.hist_days||1}일차 (7일 차면 완전한 주간 랭킹)`;}
      // (2026-08-06) 데이터랩 장기 시계열 — 키 등록 시 자동 활성화
      const nvOff=document.getElementById('tr_nv_off'), nvBox=document.getElementById('tr_nv_box');
      if(!d.nv_enabled){ if(nvOff)nvOff.style.display='block'; }
      else if(nvBox&&d.nv_trend){
        nvBox.style.display='block';
        const NT=d.nv_trend, cols=['#e0442c','#2f6fed','#1a9850','#f2a72e','#8b5cf6','#0e7490','#be185d','#65a30d','#7c2d12','#64748b'];
        if(window.Chart) new Chart(document.getElementById('tr_nv_cv'),{type:'line',
          data:{labels:NT.labels,datasets:Object.entries(NT.series).map(([n,v],i)=>({label:n,data:v,borderColor:cols[i%10],borderWidth:1.6,pointRadius:0,tension:.2}))},
          options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{position:'bottom',labels:{boxWidth:14,font:{size:11}}}},scales:{x:{ticks:{maxTicksLimit:12}}}}}); }
      // (2026-08-06) 주간 LLM 리포트 (trends_weekly_llm.json — /namoobi-search-trends 주 1회)
      //   구글·유튜브 주간 해설 + 네이버 장기 해석 + 인스타 큐레이션 + 시즌·연간 발표 체크
      fetch('/api/db/trends_weekly_llm').then(x=>x.ok?x.json():null).then(w=>{
        if(!w) return;
        {const e=document.getElementById('tr_ig_asof'); if(e) e.textContent=`— ${w.week||''} · 작성 ${w.asof||''} · 주 1회 갱신 · /namoobi-search-trends`;}
        const itemTbl=(items)=>`<table style="margin-top:4px">${(items||[]).map(([t,d,u],i)=>
          `<tr><td class="note" style="width:24px">${i+1}</td><td><b>${u?`<a href="${E2(u)}" target="_blank">${E2(t)} ↗</a>`:E2(t)}</b><div class="note" style="font-size:12px">${E2(d)}</div></td></tr>`).join('')}</table>`;
        // ① 구글·유튜브 주간 해설(KR/US 4박스) + 네이버 장기 해석(1박스)
        const wkEl=document.getElementById('tr_wkllm');
        if(wkEl){
          const boxes=[];
          for(const [sec,flag] of [[w.google_wk,'구글'],[w.youtube_wk,'유튜브']]){
            if(!sec) continue;
            for(const [rk,lbl] of [['kr','🇰🇷 한국'],['us','🇺🇸 글로벌']]){
              const s=sec[rk]; if(!s) continue;
              boxes.push(`<div class="box"><b style="font-size:13px">${E2(sec.title)} — ${lbl}</b>
                <div class="note" style="margin:2px 0 2px"><b>${E2(s.head||'')}</b></div>${itemTbl(s.items)}</div>`);
            }
          }
          if(w.naver_long) boxes.push(`<div class="box" style="grid-column:1/-1"><b style="font-size:13px">${E2(w.naver_long.title)}</b>
            <div class="note" style="margin:2px 0 2px"><b>${E2(w.naver_long.head||'')}</b></div>${itemTbl(w.naver_long.items)}</div>`);
          wkEl.innerHTML=boxes.join('');
        }
        // ② 인스타 큐레이션
        const el=document.getElementById('tr_insta');
        if(el) el.innerHTML=[w.kr,w.global].filter(Boolean).map(s=>`<div class="box">
          <b style="font-size:13px">${E2(s.title)}</b>${itemTbl(s.items)}</div>`).join('')
          +`<div class="note" style="grid-column:1/-1">출처: ${(w.sources||[]).map(([n,u])=>`<a href="${E2(u)}" target="_blank">${E2(n)}</a>`).join(' · ')}</div>`;
        // ③ 시즌·연간 발표 체크 상태
        {const e=document.getElementById('tr_season');
         if(e&&w.season_check) e.textContent=`📚 시즌·연간 리포트 발표 체크 (${w.season_check.checked}): ${w.season_check.found}`;}
      }).catch(()=>{});
      // 연간·시즌 리포트 카드 (trends_annual.json — 연 1회 갱신)
      fetch('/api/db/trends_annual').then(x=>x.ok?x.json():null).then(an=>{
        const el=document.getElementById('tr_annual'); if(!el||!an) return;
        el.innerHTML=(an.cards||[]).map(c=>`<div class="box">
          <b style="font-size:13px">${E2(c.icon)} ${c.url?`<a href="${E2(c.url)}" target="_blank">${E2(c.title)} ↗</a>`:E2(c.title)}</b>
          <div class="note" style="margin:2px 0 6px">${c.url?`<a href="${E2(c.url)}" target="_blank" class="note">${E2(c.src)}</a>`:E2(c.src)}</div>
          <ul style="margin:0;padding-left:18px;font-size:12.5px;line-height:1.75">${(c.items||[]).map(x=>`<li>${E2(x)}</li>`).join('')}</ul></div>`).join('');
      }).catch(()=>{});
    }).catch(()=>{});
  };
  /* ── (2026-08-08) 공통 지역 선택기 —— '아파트 실거래 지역 비교' 방식을 전 카드에 통일.
     ① 검색으로 찾고 칩으로 담는 다중선택(최대 12) ② 시도는 ★ 로 위에 ③ 시군구는 시도명이
     이름에 없으면 앞에 붙여 '경기'·'강원' 같은 도 단위 검색이 걸리게 한다. ── */
  const RP_PAL=['#d9534f','#2f6fed','#27ae60','#e08e3c','#7c3aed','#0e7490','#be185d','#65a30d',
                '#5d4037','#455a64','#9e9d24','#00838f'];
  function regionPicker(o){
    /* o = {q,list,chips, all:()=>[names], isSido, count, sel:[], onChange,
            preset?:[[라벨,툴팁,()=>[names]]], presetEl?, sortVal?:(r)=>number|null, onHover?}
       (2026-08-08) 지역비교 카드에서 검증된 방식을 공통화 —
       최대 30개 · 값 내림차순 정렬 · 칩 hover 로 계열 강조 · 원클릭 프리셋. */
    const E=s=>String(s??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
    const q=$(o.q), list=$(o.list), chips=$(o.chips);
    if(!q||!list||!chips) return null;
    const MAX=o.max||30;
    const api={sel:o.sel.slice(), hi:null};
    api.sort=()=>{ if(!o.sortVal) return;
      api.sel=api.sel.map(r=>[r,o.sortVal(r)]).sort((a,b)=>(b[1]??-1e18)-(a[1]??-1e18)).map(x=>x[0]);};
    /* (2026-08-08) 강조는 **스타일만** 바꾼다.
       예전엔 hover 마다 drawChips() 로 innerHTML 을 통째로 다시 그렸는데, 그러면
       커서 아래에 있던 ✕ 노드가 교체돼 mousedown/mouseup 이 다른 노드에서 일어나
       클릭 자체가 성립하지 않았다("X 눌렀을때 제거 안됨"의 원인). */
    const paint=()=>chips.querySelectorAll('[data-hi]').forEach(el=>{
      const on=api.hi===el.dataset.hi;
      el.style.boxShadow=on?'0 0 0 2px #1f2937':''; el.style.fontWeight=on?'700':''; });
    let bound=false;
    const drawChips=()=>{chips.innerHTML=api.sel.map((r,i)=>{const c=RP_PAL[i%RP_PAL.length];
      return `<span data-hi="${E(r)}" style="display:inline-flex;align-items:center;gap:3px;padding:2px 7px;font-size:12px;border-radius:10px;background:${c}18;border:1px solid ${c};color:#333;cursor:pointer"><b style="color:${c}">●</b>${E(r)}<b data-rm="${E(r)}" style="cursor:pointer;color:#888;padding:0 2px">✕</b></span>`;}).join('');
      if(!bound){ bound=true;                       // 위임 리스너 — 재생성돼도 살아남는다
        chips.addEventListener('click',e=>{const b=e.target.closest('[data-rm]'); if(!b) return;
          e.stopPropagation(); e.preventDefault();
          api.sel=api.sel.filter(r=>r!==b.dataset.rm); api.hi=null;
          drawChips(); o.onChange(api.sel);});
        chips.addEventListener('mouseover',e=>{const s=e.target.closest('[data-hi]');
          const v=s?s.dataset.hi:null; if(api.hi===v) return;
          api.hi=v; paint(); o.onHover&&o.onHover(v);});
        chips.addEventListener('mouseleave',()=>{ if(api.hi==null) return;
          api.hi=null; paint(); o.onHover&&o.onHover(null);}); }
      paint();};
    api.setHi=(r)=>{ if(api.hi===r) return; api.hi=r; paint(); };
    api.redraw=()=>{api.sort(); drawChips();};
    const show=()=>{const kw=(q.value||'').trim().toLowerCase();
      const cand=o.all().filter(r=>!api.sel.includes(r)&&(!kw||String(r).toLowerCase().includes(kw)));
      const sd=cand.filter(o.isSido), sg=cand.filter(r=>!o.isSido(r)).sort();
      list.innerHTML=[...sd,...sg].slice(0,60).map(r=>{
        const n=o.count?o.count(r):null;
        return `<div data-add="${E(r)}" style="padding:5px 10px;font-size:12.5px;cursor:pointer;border-bottom:1px solid #f2f4f7">${o.isSido(r)?'★ ':''}${E(r)}${n?` <span class="note">${n}</span>`:''}</div>`;
      }).join('')||'<div style="padding:6px 10px" class="note">없음</div>';
      list.style.display='';
      list.querySelectorAll('[data-add]').forEach(x=>x.onclick=()=>{
        if(api.sel.length>=MAX){alert('최대 '+MAX+'개까지');return;}
        api.sel.push(x.dataset.add); q.value=''; list.style.display='none';
        api.sort(); drawChips(); o.onChange(api.sel);});};
    q.oninput=show; q.onfocus=show;
    document.addEventListener('click',e=>{
      if(!e.target.closest('#'+o.q)&&!e.target.closest('#'+o.list)) list.style.display='none';});
    /* 원클릭 프리셋 — 자주 쓰는 조합을 버튼으로 */
    /* (2026-08-08) preset 이 없는 화면(주택 공급 등)에도 '비우기' 는 필요하다 →
       presetEl 만 있으면 버튼 영역을 만든다. */
    if(o.presetEl&&$(o.presetEl)){
      const el=$(o.presetEl); const PS=o.preset||[];
      el.innerHTML=PS.map(([lab,tip],i)=>
        `<button data-p="${i}" title="${E(tip)}" style="padding:3px 9px;font-size:11.5px;border:1px solid #b45309;color:#b45309;background:#fff;border-radius:6px;cursor:pointer">${E(lab)}</button>`).join('')
        +`<button data-clr="1" title="선택 비우기" style="padding:3px 8px;font-size:11.5px;border:1px solid #d7dce3;border-radius:6px;cursor:pointer;background:#fff;color:#888">비우기</button>`;
      el.querySelectorAll('[data-p]').forEach(b=>b.onclick=()=>{
        api.sel=PS[+b.dataset.p][2]().slice(0,MAX); api.sort(); drawChips(); o.onChange(api.sel);});
      el.querySelector('[data-clr]').onclick=()=>{api.sel=[]; drawChips(); o.onChange(api.sel);};
    }
    api.refresh=()=>drawChips();
    api.sort(); drawChips();
    return api;
  }
  const RP_SIDO=new Set(['전국','수도권','서울','부산','대구','인천','광주','대전','울산','세종',
                         '경기','강원','충북','충남','전북','전남','경북','경남','제주']);

  /* ── (2026-08-08) 🏗 서울 재개발·재건축 — redev.json (클린업시스템 무인증)
     현황보다 '변화'가 신호다 — 매일 스냅샷을 비교해 단계 전환을 잡아낸다. ── */
  let _rdInit=false, _rdSd='전체';
  function initRedev(){
    if(_rdInit) return; _rdInit=true;
    fetch('/api/db/redev').then(r=>r.ok?r.json():null).then(d=>{
      if(!d||!d.gu){ const e=$('rd_head'); if(e) e.textContent='수집 대기 중 — 다음 수집(매일 08:05)부터 표시됩니다.'; return; }
      const sds=['전체',...Object.keys(d.sd||{})];
      const bar=()=>{$('rd_sd').innerHTML=sds.map(s=>`<button data-s="${s}" style="margin-right:3px;padding:2px 9px;font-size:11.5px;border:1px solid #d7dce3;border-radius:6px;cursor:pointer;background:${s===_rdSd?'#1f2937':'#fff'};color:${s===_rdSd?'#fff':'#333'}">${s}${s!=='전체'?` <span style="opacity:.7">${d.sd[s]}</span>`:''}</button>`).join('');
        $('rd_sd').querySelectorAll('button').forEach(b=>b.onclick=()=>{_rdSd=b.dataset.s; bar(); render();});};
      const render=()=>_rdRender(d);
      bar(); render();
    }).catch(()=>{});
  }
  function _rdRender(d){
    {
      const E6=s=>String(s??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
      const KEY=new Set(d.key_stages||[]);
      /* 시도 필터 — 자치구 키가 "서울 강남구" 형태라 접두어로 거른다 */
      const inSd=g=>_rdSd==='전체'||String(g).startsWith(_rdSd+' ');
      const GU=Object.fromEntries(Object.entries(d.gu).filter(([g])=>inSd(g)));
      const nSel=Object.values(GU).reduce((a,c)=>a+Object.values(c).reduce((x,y)=>x+y,0),0);
      $('rd_head').innerHTML=`<b>${E6(_rdSd)}</b> <b>${nSel.toLocaleString()}</b>개 사업장 · 자치구 ${Object.keys(GU).length}`
        +(_rdSd==='전체'?` · `+Object.entries(d.sd||{}).map(([k,v])=>`${E6(k)} ${v}`).join(' · '):'')
        +` <span style="margin-left:6px">수집 ${E6(d.asof||'')}</span>`
        +`<br><span class="note">지역마다 운영 시스템이 달라 단계 명칭이 제각각이라(46종) <b>표준 단계로 통일</b>했습니다. 경기는 사업일정·세대수까지, 인천은 컬럼이 가장 적습니다.</span>`;
      /* 단계별 막대 — canvas 대신 div 폭으로(가로 막대가 더 읽기 쉽다) */
      const tot={}; (d.stages||[]).forEach(s=>tot[s]=0);
      Object.values(GU).forEach(c=>Object.entries(c).forEach(([s,v])=>tot[s]=(tot[s]||0)+v));
      const gu=GU;
      const mx=Math.max(...Object.values(tot),1);
      $('rd_stages').innerHTML=(d.stages||[]).filter(s=>s&&tot[s]).map(s=>{
        const w=tot[s]/mx*100, hot=KEY.has(s);
        return `<div style="display:flex;align-items:center;gap:6px;margin-bottom:2px;font-size:11.5px">
          <span style="width:118px;text-align:right;${hot?'font-weight:700;color:#111':'color:#5b6672'}">${E6(s)}</span>
          <span style="flex:1;background:#f0f2f5;border-radius:3px;height:14px;position:relative">
            <span style="display:block;width:${w}%;height:100%;background:${hot?'#b45309':'#9fb0c4'};border-radius:3px"></span></span>
          <b style="width:34px;text-align:right">${tot[s]}</b></div>`;}).join('');
      /* 단계 전환 이력 */
      const C=d.changes||[];
      $('rd_chg').innerHTML=C.length?C.slice(0,60).map(c=>
        `<div style="padding:5px 7px;border-bottom:1px solid #f2f4f7;font-size:12px">
           <span class="note">${E6(c.de)}</span> <b>[${E6(c.gu)}]</b> ${E6(c.name)}
           <br><span style="color:${c.key?'#b45309':'#5b6672'};font-weight:${c.key?'700':'400'}">
             ${c.from?E6(c.from)+' → ':'신규 등재 → '}${E6(c.to)}</span>
             ${c.fwd===false?' <span style="color:#8a94a0">(단계 후퇴)</span>':''}</div>`).join('')
        : `<div class="note" style="padding:8px">아직 감지된 전환이 없습니다 — 매일 스냅샷을 비교해 <b>내일부터</b> 쌓입니다.
             (오늘이 첫 수집이라 비교 대상이 없습니다)</div>`;
      /* 자치구 × 주요단계 표 */
      const KS=(d.key_stages||[]).filter(s=>tot[s]);
      const gus=Object.keys(gu).sort((a,b)=>
        KS.reduce((s,k)=>s+(gu[b][k]||0),0)-KS.reduce((s,k)=>s+(gu[a][k]||0),0));
      $('rd_gu').innerHTML=`<table style="width:100%;border-collapse:collapse;font-size:12px">
        <thead><tr style="position:sticky;top:0;background:#f7f8fa">
          <th style="padding:4px 7px;text-align:left;border-bottom:1px solid #e3e7ec">자치구</th>
          ${KS.map(s=>`<th style="padding:4px 7px;text-align:right;border-bottom:1px solid #e3e7ec;white-space:nowrap">${E6(s)}</th>`).join('')}
          <th style="padding:4px 7px;text-align:right;border-bottom:1px solid #e3e7ec">전체</th></tr></thead>
        <tbody>${gus.map(g=>{const c=gu[g], all=Object.values(c).reduce((a,b)=>a+b,0);
          return `<tr style="border-bottom:1px solid #f2f4f7"><td style="padding:3px 7px">${E6(g)}</td>
            ${KS.map(s=>`<td style="padding:3px 7px;text-align:right;${c[s]?'font-weight:600':'color:#c3cad3'}">${c[s]||'·'}</td>`).join('')}
            <td style="padding:3px 7px;text-align:right" class="note">${all}</td></tr>`;}).join('')}</tbody></table>`;
    }
  }

  /* ── (2026-08-08) 🇺🇸 미국 주택 선행지표 — us_housing.json (FRED 무인증 CSV) ── */
  let _uhInit=false;
  function initUsHouse(){
    if(_uhInit) return; _uhInit=true;
    fetch('/api/db/us_housing').then(r=>r.ok?r.json():null).then(d=>{
      if(!d||!d.series) return;
      const S=d.series;
      {const e=$('uh_asof'); if(e) e.textContent=`수집 ${d.asof||''} · 출처 FRED (인증키 불필요)`;}
      const cut=(s,n)=>({t:s.t.slice(-n), v:s.v.slice(-n)});
      const F=t=>t?`${t.slice(0,4)}.${t.slice(4,6)}`:'—';
      const yoy=(s)=>{const n=s.v.length; if(n<13) return null;
        const a=s.v[n-1], b=s.v[n-13]; return b?((a/b-1)*100):null;};
      /* 허가·착공 — 최근 25년(300개월) */
      {const P=S.permit, H=S.start;
       if(P&&H){ const p=cut(P,300), h=cut(H,300);
         line('uh_start',[{...p,label:'건축허가',color:'#2f6fed'},{...h,label:'착공',color:'#d9534f'}]);
         const yp=yoy(P), yh=yoy(H);
         $('uh_start_n').innerHTML=
           `허가 <b>${P.v[P.v.length-1].toLocaleString()}</b>천호${yp!=null?` <span class="${yp>0?'up':'dn'}">(${yp>0?'+':''}${yp.toFixed(0)}% YoY)</span>`:''}`
           +` · 착공 <b>${H.v[H.v.length-1].toLocaleString()}</b>천호${yh!=null?` <span class="${yh>0?'up':'dn'}">(${yh>0?'+':''}${yh.toFixed(0)}% YoY)</span>`:''}`
           +` <span class="note">(${F(P.t[P.t.length-1])})</span>`
           +`<br><span class="note">${E7(P.note)}</span>`;
       }}
      /* 모기지 금리 — 최근 25년(주간 1300개) */
      {const M=S.mort;
       if(M){ const m=cut(M,1300);
         line('uh_mort',[{...m,label:'30년',color:'#7c3aed'}]);
         const n=M.v.length, cur=M.v[n-1], p52=n>52?M.v[n-53]:null;
         const lo=Math.min(...M.v.slice(-260)), hi=Math.max(...M.v.slice(-260));
         $('uh_mort_n').innerHTML=
           `현재 <b>${cur.toFixed(2)}%</b> (${F(M.t[M.t.length-1])})`
           +`${p52!=null?` · 1년 전 ${p52.toFixed(2)}% <span class="${cur>p52?'up':'dn'}">(${cur>p52?'+':''}${(cur-p52).toFixed(2)}%p)</span>`:''}`
           +` · 최근 5년 범위 ${lo.toFixed(2)}~${hi.toFixed(2)}%`
           +`<br><span class="note">${E7(M.note)}</span>`;
       }}
    }).catch(()=>{});
  }
  const E7=s=>String(s??'').replace(/[&<>]/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[m]));

  /* ── (2026-08-08) 🎯 청약경쟁률 — applyhome.json (청약홈)
     실거래는 계약 끝난 뒤에 잡히는 후행 지표지만, 청약은 지금 수요가 얼마나
     달려드는지를 보여주는 선행 지표. 지역 격차가 워낙 커서(서울 33:1 vs 지방 2:1)
     선택 지역 + 전국 기준선을 함께 그린다. ── */
  let _ahInit=false, _ahD=null, _ahSel=['전국','서울','경기'], _ahHi=null, _ahPick=null, _ahArr=null, _ahLog=true, _ahWin=12, _ahLastPre=null;
  const AHPAL=RP_PAL; const AHPAL_OLD=['#be185d','#2f6fed','#27ae60','#e08e3c','#7c3aed','#0e7490','#d9534f','#65a30d',
               '#5d4037','#455a64','#9e9d24','#00838f'];
  function initApply(){
    if(_ahInit) return; _ahInit=true;
    fetch('/api/db/applyhome').then(r=>r.ok?r.json():null).then(d=>{
      if(!d||!d.series){ const e=$('ah_main_n'); if(e) e.textContent='수집 대기 중 — 다음 수집(매일 07:55)부터 표시됩니다.'; return; }
      _ahD=d;
      {const e=$('ah_asof'); if(e) e.textContent=`수집 ${d.asof||''} · 청약홈 · 시도 ${(d.sido||[]).length} · 시군구 ${(d.sgg||[]).length}`;}
      _ahSel=_ahSel.filter(r=>d.series[r]);
      if(!_ahSel.length) _ahSel=(d.sido||[]).slice(0,3);
      /* 정렬·랭킹 기준 — 최근 12개월 중 값이 있는 달의 평균.
         청약은 단지 하나로 월값이 크게 튀어서 단월 기준으로 줄 세우면 순위가 매달 뒤집힌다. */
      /* 순위 기준 = 선택한 기간의 평균 경쟁률.
         기간에 따라 '요즘 뜨는 곳'(3M)과 '꾸준히 센 곳'(24M)이 갈린다. */
      const recentAvg=r=>{const v=d.series[r]; if(!v) return null;
        const s=(_ahWin>0?v.slice(-_ahWin):v).filter(x=>x!=null); if(!s.length) return null;
        return s.reduce((a,b)=>a+b,0)/s.length;};
      const topN=(f,n)=>(d.regions||[]).filter(r=>!RP_SIDO.has(r)&&f(r))
        .map(r=>[r,recentAvg(r)]).filter(x=>x[1]!=null)
        .sort((a,b)=>b[1]-a[1]).slice(0,n).map(x=>x[0]);
      _ahPick=regionPicker({q:'ah_q',list:'ah_list',chips:'ah_chips',presetEl:'ah_preset',sel:_ahSel,
        all:()=>d.regions||[], isSido:r=>RP_SIDO.has(r), sortVal:recentAvg, max:30,
        count:r=>{const n=(d.n_pblanc||{})[r]; return n?`공고 ${n}건`:null;},
        preset:[
          ['경쟁률 TOP30','선택한 순위기간의 평균 경쟁률 상위 시군구 30',()=>{_ahLastPre=0; return topN(()=>true,30);}],
          ['서울 전체',   '서울 시군구 전부',()=>{_ahLastPre=1; return topN(r=>r.startsWith('서울 '),30);}],
          ['부산 전체',   '부산 시군구 전부',()=>{_ahLastPre=2; return topN(r=>r.startsWith('부산 '),30);}],
          ['경기 TOP30',  '경기 시군구 상위 30',()=>{_ahLastPre=3; return topN(r=>r.startsWith('경기 '),30);}],
          ['시도 전체',   '전국·시도 단위만',()=>{_ahLastPre=4; return (d.sido||[]).slice(0,30);}],
        ],
        onHover:r=>{_ahHi=r; drawApply();},
        onChange:s=>{_ahSel=s; drawApply();}});
      /* 축 토글 — 경쟁률은 0.02~35,000 까지 벌어져 기본을 로그로 둔다.
         (선형이면 서초 35,076:1 같은 이상치 하나가 나머지 29개를 바닥에 눌러버린다) */
      const sbar=()=>{$('ah_scale').innerHTML=[[true,'로그축'],[false,'선형축']].map(([k,l])=>
          `<button data-l="${k}" style="padding:3px 9px;font-size:11.5px;border:1px solid #d7dce3;border-radius:6px;cursor:pointer;background:${k===_ahLog?'#1f2937':'#fff'};color:${k===_ahLog?'#fff':'#333'}">${l}</button>`).join('');
        $('ah_scale').querySelectorAll('button').forEach(b=>b.onclick=()=>{
          _ahLog=(b.dataset.l==='true'); sbar(); drawApply();});};
      const WINS=[[3,'3M'],[6,'6M'],[12,'12M'],[24,'24M'],[0,'전체']];
      const wbar=()=>{$('ah_win').innerHTML=WINS.map(([k,l])=>
          `<button data-w="${k}" style="padding:3px 8px;font-size:11.5px;border:1px solid #d7dce3;border-radius:6px;cursor:pointer;background:${k===_ahWin?'#1f2937':'#fff'};color:${k===_ahWin?'#fff':'#333'}">${l}</button>`).join('');
        $('ah_win').querySelectorAll('button').forEach(b=>b.onclick=()=>{
          _ahWin=+b.dataset.w; wbar();
          // 프리셋으로 뽑은 목록이면 새 기간으로 다시 뽑아준다(기간만 바꾸고 목록이 그대로면 헷갈린다)
          if(_ahLastPre!=null&&_ahPick){ const el=$('ah_preset');
            const btn=el&&el.querySelector(`[data-p="${_ahLastPre}"]`); if(btn){ btn.click(); return; } }
          _ahPick&&_ahPick.redraw(); drawApply();});};
      sbar(); wbar(); drawApply();
    }).catch(()=>{});
  }
  function drawApply(){
    if(!_ahD) return; const d=_ahD, t=d.t, S=d.series;
    const E5=s=>String(s??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
    const F=x=>x?`${x.slice(0,4)}.${x.slice(4)}`:'—';
    const arr=_ahSel.filter(r=>S[r]).map((r,i)=>({t,v:S[r],label:r,color:AHPAL[i%AHPAL.length]}));
    if(arr.length) line('ah_main',arr,{hi:_ahHi,log:_ahLog});
    else { const c=$('ah_main');                       // 비우기 후 잔상 제거
      if(c){const g=c.getContext('2d'); c.width=c.clientWidth||900; c.height=c.clientHeight||320; g.clearRect(0,0,c.width,c.height);}
      _ahArr=null; _ahHi=null;
      $('ah_main_n').innerHTML='<span class="note">지역을 선택하세요 — 위 버튼(경쟁률 TOP30 등)이나 검색으로 추가할 수 있습니다.</span>';
      $('ah_tbl').innerHTML=''; return; }
    /* 차트 위 마우스 → 근접 선 강조 + 해당 칩 활성 (지역비교와 동일 동작) */
    {const cv=$('ah_main');
     if(cv&&!cv._hiBound){ cv._hiBound=1;
       cv.addEventListener('mousemove',e=>{
         if(!_ahD) return; const A=_ahArr; if(!A||!A.length) return;
         const r=cv.getBoundingClientRect(), P={l:8,rr:52,t:10,b:18};
         const N0=Math.max(...A.map(a=>a.v.length));
         const fx=(e.clientX-r.left)/(cv.clientWidth||900)*cv.width;
         const fy=(e.clientY-r.top)/(cv.clientHeight||320)*cv.height;
         const iw=(cv.width-P.l-P.rr)/Math.max(1,N0-1);
         let idx=Math.max(0,Math.min(N0-1,Math.round((fx-P.l)/Math.max(1,iw))));
         const all=A.flatMap(a=>a.v).filter(v=>v!=null); if(!all.length) return;
         let lo=Math.min(...all), hi2=Math.max(...all);
         const pad=(hi2-lo)*0.06||1; lo-=pad; hi2+=pad;
         const Yv=v=>P.t+(cv.height-P.t-P.b)*(1-(v-lo)/(hi2-lo));
         let best=null, bd=1e9;
         A.forEach(a=>{ let v=a.v[idx];
           if(v==null){ for(let k=1;k<6&&v==null;k++) v=a.v[idx-k]??a.v[idx+k]; }
           if(v==null) return; const dd=Math.abs(Yv(v)-fy); if(dd<bd){bd=dd; best=a.label;} });
         const nl=(bd<26)?best:null;
         if(nl!==_ahHi){ _ahHi=nl; _ahPick&&_ahPick.setHi(nl); drawApply(); } });
       cv.addEventListener('mouseleave',()=>{ if(_ahHi){_ahHi=null; _ahPick&&_ahPick.setHi(null); drawApply();} });
     }}
    _ahArr=arr;
    const info=arr.map(a=>{
      const v=a.v; let li=-1; for(let i=v.length-1;i>=0;i--) if(v[i]!=null){li=i;break;}
      let pk=-1; for(let i=0;i<v.length;i++) if(v[i]!=null&&(pk<0||v[i]>v[pk])) pk=i;
      return {r:a.label,c:a.color,li,pk,v};});
    $('ah_main_n').innerHTML=
      `경쟁률 = <b>총 청약건수 ÷ 총 공급세대</b> · 월별 <b>가중평균</b> · 최대 30개 · 순위기간 <b>${_ahWin?_ahWin+'개월':'전체'}</b> · ${_ahLog?'<b>로그축</b>(자릿수 차이가 커서 기본값 — 선형은 이상치 하나에 눌린다)':'<b>선형축</b>'}`
      +`<br>`+info.map(x=>`<b style="color:${x.c}">${E5(x.r)}</b> 최신 <b>${x.li>=0?x.v[x.li].toFixed(2):'—'}</b>`
          +`${x.li>=0?`<span class="note">(${F(t[x.li])})</span>`:''}`
          +`${x.pk>=0?` · 최고 ${x.v[x.pk].toFixed(0)}<span class="note">(${F(t[x.pk])})</span>`:''}`).join(' &nbsp;·&nbsp; ')
      +`<br><span class="note">1:1 미만이면 <b>미달</b>(공급 &gt; 청약). 실거래·가격지수보다 먼저 움직여 <b>수요 심리의 선행 지표</b>로 쓰인다. 시군구는 공고 3건 이상인 곳만 제공되며, 분양가상한제·입지에 따라 단지 편차가 커서 월별 값이 크게 튄다.</span>`;
    /* 최근 공고 표 */
    const R=d.recent||[];
    $('ah_tbl').innerHTML=`<table style="width:100%;border-collapse:collapse;font-size:12px">
      <thead><tr style="position:sticky;top:0;background:#f7f8fa">
        ${['공고일','지역','단지명','유형','공급','경쟁률','최고'].map((h,i)=>`<th style="padding:5px 7px;text-align:${i>=4?'right':'left'};border-bottom:1px solid #e3e7ec;white-space:nowrap">${h}</th>`).join('')}
      </tr></thead><tbody>${R.map(a=>{
        const hot=a.rate>=10, cold=a.rate<1;
        return `<tr style="border-bottom:1px solid #f2f4f7">
          <td style="padding:4px 7px;white-space:nowrap">${E5(a.de)}</td>
          <td style="padding:4px 7px;white-space:nowrap">${E5(a.sgg||a.reg)}</td>
          <td style="padding:4px 7px">${a.url?`<a href="${E5(a.url)}" target="_blank" rel="noopener">${E5(a.name)}</a>`:E5(a.name)}</td>
          <td style="padding:4px 7px;white-space:nowrap" class="note">${E5(a.kind||'')}</td>
          <td style="padding:4px 7px;text-align:right">${Math.round(a.sup).toLocaleString()}</td>
          <td style="padding:4px 7px;text-align:right;font-weight:700;color:${hot?'#c0392b':cold?'#8a94a0':'#333'}">${a.rate.toFixed(2)}</td>
          <td style="padding:4px 7px;text-align:right" class="note">${a.top!=null?a.top.toFixed(1):'—'}</td></tr>`;}).join('')}
      </tbody></table>`;
  }

  /* ── (2026-08-08) 🏬 비아파트 실거래 5종 — rtms_etc.json
     아파트만 보면 시장의 절반을 놓친다. 오피스텔은 매매+전월세가 다 있어
     전월세전환율까지 직접 산출된다(단, 표본이 달라 근사치 — 추세로 읽을 것). ── */
  let _etInit=false, _etD=null, _etSel=['전국'], _etMet='n', _etKind='offi_s', _etPick=null, _etHi=null, _etRef=null;
  const ETC=[['offi_s','오피스텔'],['rh','연립다세대'],['sh','단독다가구'],['land','토지'],['nrg','상업업무용']];
  function initEtc(){
    if(_etInit) return; _etInit=true;
    fetch('/api/db/rtms_etc').then(r=>r.ok?r.json():null).then(d=>{
      if(!d||!d.types){ const e=$('et_main_n'); if(e) e.textContent='수집 대기 중 — 다음 수집(매일 07:50)부터 표시됩니다.'; return; }
      _etD=d;
      const T=d.types;
      const all=[...new Set(Object.values(T).flatMap(v=>Object.keys(v.n||{})))];
      {const e=$('et_asof'); if(e) e.textContent=`수집 ${d.asof||''} · 국토부 실거래가 · 지역 ${all.length}`;}
      _etSel=_etSel.filter(r=>all.includes(r)); if(!_etSel.length) _etSel=['전국'];
      /* 순위 기준 — **모든 지역 공통의 기준월**(잠정 직전 확정 최신월) 값.
         (2026-08-08) 지역별로 '각자의 마지막 확정월'을 쓰면 서로 다른 달을 비교하게 돼
         서초구(옛 고가 거래)가 양천구(최신 최고가)보다 위로 올라가는 문제가 있었다. */
      const refIdx=()=>{const S=T[_etKind]; if(!S) return -1;
        const d2=new Date(); d2.setMonth(d2.getMonth()-2);
        const cut=`${d2.getFullYear()}${String(d2.getMonth()+1).padStart(2,'0')}`;
        const V=S[_etMet]||{};
        for(let i=S.t.length-1;i>=0;i--)
          if(S.t[i]<=cut && Object.values(V).some(v=>v&&v[i]!=null)){ _etRef=S.t[i]; return i; }
        return -1;};
      const lastConf=r=>{const S=T[_etKind]; if(!S||!S[_etMet]||!S[_etMet][r]) return null;
        const i=refIdx(); return i<0?null:(S[_etMet][r][i]??null);};
      const topN=(f,n)=>all.filter(r=>!RP_SIDO.has(r)&&f(r))
        .map(r=>[r,lastConf(r)]).filter(x=>x[1]!=null)
        .sort((a,b)=>b[1]-a[1]).slice(0,n).map(x=>x[0]);
      _etPick=regionPicker({q:'et_q',list:'et_list',chips:'et_chips',presetEl:'et_preset',sel:_etSel,
        all:()=>all, isSido:r=>RP_SIDO.has(r), sortVal:lastConf, max:30,
        preset:[
          ['서울 전체구','서울 시군구 전부',()=>topN(r=>r.startsWith('서울 '),30)],
          ['부산 전체구','부산 시군구 전부',()=>topN(r=>r.startsWith('부산 '),30)],
          ['경기 TOP30','경기 시군구 상위 30',()=>topN(r=>r.startsWith('경기 ')||/^(수원|성남|고양|용인|안양|안산|화성|평택|부천)/.test(r),30)],
          ['전국 TOP30','전국 시군구 상위 30',()=>topN(()=>true,30)],
        ],
        onHover:r=>{_etHi=r; drawEtc();},
        onChange:s=>{_etSel=s; drawEtc();}});
      const bar=(id,items,cur,set)=>{$(id).innerHTML=items.map(([k,l])=>`<button data-k="${k}" style="margin-right:3px;padding:2px 8px;font-size:11.5px;border:1px solid #d7dce3;border-radius:6px;cursor:pointer;background:${k===cur()?'#1f2937':'#fff'};color:${k===cur()?'#fff':'#333'}">${l}</button>`).join('');
        $(id).querySelectorAll('button').forEach(b=>b.onclick=()=>{set(b.dataset.k); mb(); kb(); _etPick&&_etPick.redraw(); drawEtc();});};
      const mb=()=>bar('et_met',[['n','거래 건수'],['avg','평균 거래가(억)']],()=>_etMet,v=>_etMet=v);
      const kb=()=>bar('et_kind',ETC,()=>_etKind,v=>_etKind=v);
      mb(); kb(); drawEtc();
    }).catch(()=>{});
  }
  /* 실거래는 신고기한 30일 → 최근 2개월은 아직 덜 들어온 '잠정' 구간이다.
     line() 의 provIdx 로 주황 음영을 넣어 눈으로 구분되게 한다. */
  function _provRT(ts){
    const d=new Date(); d.setMonth(d.getMonth()-1);
    const cut=`${d.getFullYear()}${String(d.getMonth()+1).padStart(2,'0')}`;
    const i=ts.findIndex(t=>t>=cut);
    return i>0?i:null;
  }
  function refIdxOf(){                       // 순위 기준월의 인덱스(차트 표식용)
    const T=(_etD||{}).types||{}; const S=T[_etKind]; if(!S) return -1;
    const d2=new Date(); d2.setMonth(d2.getMonth()-2);
    const cut=`${d2.getFullYear()}${String(d2.getMonth()+1).padStart(2,'0')}`;
    const V=S[_etMet]||{};
    for(let i=S.t.length-1;i>=0;i--)
      if(S.t[i]<=cut && Object.values(V).some(v=>v&&v[i]!=null)){ _etRef=S.t[i]; return i; }
    return -1;}
  function drawEtc(){
    if(!_etD) return; const T=_etD.types||{};
    /* (2026-08-08) '비우기' 후 이전 그림이 남던 버그 — 선택이 비면 세 캔버스를 모두 지운다 */
    const wipe=id=>{const c=$(id); if(!c) return;
      const g=c.getContext('2d'); c.width=c.clientWidth||900; c.height=c.clientHeight||300;
      g.clearRect(0,0,c.width,c.height);};
    if(!_etSel.length){
      ['et_main','et_conv','et_jw'].forEach(wipe); _etHi=null;
      $('et_main_n').innerHTML='<span class="note">지역을 선택하세요 — 위 버튼(서울 전체구·전국 TOP30 등)이나 검색으로 추가할 수 있습니다.</span>';
      $('et_conv_n').innerHTML=''; $('et_jw_n').innerHTML='';
      return;
    }
    const K=n=>n==null?'—':(_etMet==='n'?Math.round(n).toLocaleString():n.toFixed(2)+'억');
    const F=t=>t?`${t.slice(0,4)}.${t.slice(4)}`:'—';
    const kindLab=(ETC.find(x=>x[0]===_etKind)||[,'?'])[1];
    /* ① 선택 유형을 지역별로 겹쳐보기 (유형 전환은 버튼으로) */
    {const s=T[_etKind];
     const L=s?_etSel.map((r,i)=>(s[_etMet]&&s[_etMet][r])?{t:s.t,v:s[_etMet][r],label:r,color:RP_PAL[i%RP_PAL.length]}:null).filter(Boolean):[];
     if(L.length){ line('et_main',L,{provIdx:_provRT(L[0].t),hi:_etHi,refIdx:refIdxOf()});
       const last=a=>{for(let i=a.v.length-1;i>=0;i--) if(a.v[i]!=null) return {ym:a.t[i],v:a.v[i]}; return null;};
       $('et_main_n').innerHTML=
         `<b>${kindLab}</b> · ${_etMet==='n'?'월별 <b>거래 건수</b>':'월별 <b>평균 거래가</b>(억원)'} · 지역 겹쳐보기(최대 30)`
         +`${_etRef?` · <b>순위 기준 ${_etRef.slice(0,4)}.${_etRef.slice(4)}</b>(잠정 직전 확정월 — 아래 표시값은 잠정 포함 최신치라 순위와 다를 수 있음)`:''}`
         +`<br>`+L.map(a=>{const l=last(a); return `<b style="color:${a.color}">${a.label}</b> ${l?K(l.v):'—'}<span class="note">${l?`(${F(l.ym)})`:''}</span>`;}).join(' &nbsp;·&nbsp; ')
         +`<br><span class="note">토지·상업업무용은 건당 금액 편차가 커서 평균이 크게 튄다 — 건수 추이가 더 안정적인 신호. 최근 1~2개월은 신고 진행 중이라 과소 집계. 단독다가구·토지·상업업무용은 국토부가 건물명을 제공하지 않아 단지별 조회는 불가.</span>`;
     } else { $('et_main_n').innerHTML='<span class="note">선택한 지역·유형에 데이터가 없습니다 — 백필이 진행 중이면 수집이 끝난 지역부터 나옵니다.</span>'; }}
    /* ② 오피스텔 전월세전환율 · ③ 전세 vs 월세 — 선택 지역 겹쳐보기 */
    {const s=T.offi_r; const R=_etSel;
     if(s&&s.conv){
       const L=R.map((r,i)=>s.conv[r]?{t:s.t,v:s.conv[r],label:r,color:RP_PAL[i%RP_PAL.length]}:null).filter(Boolean);
       if(L.length){ line('et_conv',L,{provIdx:_provRT(L[0].t)});
         const l=(a)=>{for(let i=a.v.length-1;i>=0;i--) if(a.v[i]!=null) return a.v[i]; return null;};
         $('et_conv_n').innerHTML=L.map(a=>`<b style="color:${a.color}">${a.label}</b> ${l(a)!=null?l(a).toFixed(2)+'%':'—'}`).join(' · ')
           +` — 전세를 월세로 바꿀 때 적용되는 이율. 높을수록 <b>월세가 비싸다</b>.`
           +`<br><span class="note">⚠ ${s.conv_note||'근사치'}</span>`;
       }}
     /* (2026-08-08) 전세·월세 '건수' 2선 → **월세 비중(%)** 1선으로 바꾸고 선택 지역 전부 그린다.
        건수는 지역 규모에 비례해 커서 지역 간 비교가 안 됐고(그래서 첫 지역만 그렸다),
        한 지역에 2선을 쓰니 다지역 겹쳐보기도 불가능했다. 비율로 정규화하면 둘 다 풀린다.
        월세 비중 = 월세건수 / (전세건수 + 월세건수) × 100. */
     if(s&&s.n&&s.wol_n){
       const L=R.map((r,i)=>{ const je=s.n[r], wo=s.wol_n[r]; if(!je||!wo) return null;
         const v=s.t.map((_,k)=>{ const a=je[k]||0, b=wo[k]||0; return (a+b)?+(b/(a+b)*100).toFixed(1):null; });
         return v.some(x=>x!=null)?{t:s.t,v,label:r,color:RP_PAL[i%RP_PAL.length]}:null; }).filter(Boolean);
       if(L.length){
         /* 표시·정렬은 **확정월** 기준. 잠정 달은 거래가 몇 건뿐이라
            "1건 중 1건이 월세 = 100%" 같은 값이 나와 비교가 무의미해진다. */
         const pi=_provRT(s.t); const ci=pi!=null?pi-1:s.t.length-1;
         line('et_jw',L,{provIdx:pi,hi:_etHi,refIdx:ci});
         const lastOf=a=>{for(let i=Math.min(ci,a.v.length-1);i>=0;i--) if(a.v[i]!=null) return {ym:a.t[i],v:a.v[i]}; return null;};
         const sorted=[...L].sort((a,b)=>((lastOf(b)||{}).v??-1)-((lastOf(a)||{}).v??-1));
         $('et_jw_n').innerHTML=
           `<b>월세 비중(%)</b> = 월세 ÷ (전세+월세) × 100 · 지역 겹쳐보기 · 높을수록 월세화가 진행된 시장`
           +`${ci>=0?` · <b>확정 ${F(s.t[ci])}</b> 기준`:''}`
           +`<br>`+sorted.map(a=>{const l=lastOf(a);
               return `<b style="color:${a.color}">${a.label}</b> ${l?l.v.toFixed(0)+'%':'—'}<span class="note">${l?`(${F(l.ym)})`:''}</span>`;}).join(' &nbsp;·&nbsp; ')
           +`<br><span class="note">월세 비중 상승 = 전세 기피(역전세·보증금 미반환 우려) 또는 고금리로 전세대출 부담↑. 거래가 적은 달은 비율이 크게 튀니 추세로 볼 것.</span>`;
       } else { wipe('et_jw'); $('et_jw_n').innerHTML=''; }
     }}
  }

  /* ── (2026-08-08) 🏗 주택 공급 — molit.json (통계누리 무인증)
     미분양=재고(수요 약세 신호) · 인허가/착공/준공=공급 파이프라인(1~3년 선행).
     월별 원자료는 계절성·노이즈가 커서 기본은 12개월 이동합으로 본다. ── */
  let _msInit=false, _msD=null, _msSel=['전국'], _msMode='12m';
  const _msReg0=()=>_msSel[0]||'전국';
  function initMolit(){
    if(_msInit) return; _msInit=true;
    fetch('/api/db/molit').then(r=>r.ok?r.json():null).then(d=>{
      if(!d||!d.series){ const e=$('ms_unsold_n'); if(e) e.textContent='수집 대기 중 — 다음 수집(매일 07:40)부터 표시됩니다.'; return; }
      _msD=d;
      const S=d.series;
      const all=[...new Set(Object.values(S).flatMap(v=>Object.keys(v.r||{})))];
      {const e=$('ms_asof'); if(e) e.textContent=`수집 ${d.asof||''} · 통계누리 · 지역 ${all.length}(미분양은 시군구까지)`;}
      _msSel=_msSel.filter(r=>all.includes(r)); if(!_msSel.length) _msSel=['전국'];
      const has=r=>all.includes(r);
      regionPicker({q:'ms_q',list:'ms_list',chips:'ms_chips',sel:_msSel,presetEl:'ms_preset',
        all:()=>all, isSido:r=>RP_SIDO.has(r), onChange:s=>{_msSel=s; drawMolit();},
        preset:[['전국','전국 한 줄만 보기',()=>['전국'].filter(has)],
                ['수도권','서울·경기·인천',()=>['서울','경기','인천'].filter(has)],
                ['5대 광역시','부산·대구·광주·대전·울산',()=>['부산','대구','광주','대전','울산'].filter(has)],
                ['전 시도','시도 전체 겹쳐보기',()=>all.filter(r=>RP_SIDO.has(r)&&r!=='전국')]]});
      const mbar=()=>{$('ms_mode').innerHTML=[['12m','12개월 누적'],['m','월별 원자료']].map(([k,l])=>`<button data-m="${k}" style="margin-right:3px;padding:2px 8px;font-size:11.5px;border:1px solid #d7dce3;border-radius:6px;cursor:pointer;background:${k===_msMode?'#1f2937':'#fff'};color:${k===_msMode?'#fff':'#333'}">${l}</button>`).join('');
        $('ms_mode').querySelectorAll('button').forEach(b=>b.onclick=()=>{_msMode=b.dataset.m; mbar(); drawMolit();});};
      mbar(); drawMolit();
    }).catch(()=>{});
  }
  function _msPick(key, reg){                  // 계열 1개를 지정 지역 기준으로 뽑기
    const r=reg||_msReg0();
    const s=(_msD.series||{})[key]; if(!s) return null;
    if(s.r[r]) return {t:s.t, v:s.r[r], label:s.label, unit:s.unit, note:s.note, reg:r};
    // 인허가·착공·준공은 통계누리가 시도까지만 공표한다 → 시군구를 고르면 그 시도로 대체
    const sd=String(r).split(' ')[0];
    if(s.r[sd]) return {t:s.t, v:s.r[sd], label:s.label, unit:s.unit, note:s.note, reg:sd, fb:r};
    return null;
  }
  /* 통계누리는 최근 몇 달을 "2026-06 p)" 처럼 잠정치로 낸다. 수집기가 그 시작월을
     series.prov 로 저장해 두었으니, 여러 계열 중 가장 이른 잠정 시작점을 음영 기준으로 쓴다. */
  function _msProv(ts, keys){
    const S=_msD.series||{};
    let p=null;
    keys.forEach(k=>{const v=S[k]&&S[k].prov; if(v&&(p===null||v<p)) p=v;});
    if(!p) return null;
    const i=ts.indexOf(p);
    return i>0?i:null;
  }
  function _ms12(t,v){                         // 12개월 이동합(직전 12개월 전부 있어야 값)
    return v.map((_,i)=>{ if(i<11) return null;
      let s=0; for(let j=i-11;j<=i;j++){ if(v[j]==null) return null; s+=v[j]; } return s; });
  }
  function _msAlign(list){                     // 서로 다른 t 를 공통 월축으로 정렬
    const all=[...new Set(list.flatMap(a=>a.t))].sort(); if(!all.length) return null;
    const ts=[]; let y=+all[0].slice(0,4), m=+all[0].slice(4);
    const ey=+all[all.length-1].slice(0,4), em=+all[all.length-1].slice(4);
    while(y<ey||(y===ey&&m<=em)){ ts.push(`${y}${String(m).padStart(2,'0')}`); if(++m>12){m=1;y++;} }
    return {ts, map:a=>{const mp={}; a.t.forEach((t,i)=>mp[t]=a.v[i]); return ts.map(t=>mp[t]??null);}};
  }
  function drawMolit(){
    if(!_msD) return;
    if(!_msSel.length){                       // '비우기'/전체 삭제 시 잔상 제거
      ['ms_unsold','ms_pipe','ms_move'].forEach(id=>{const c=$(id); if(!c) return;
        const g=c.getContext('2d'); c.width=c.clientWidth||900; c.height=c.clientHeight||300;
        g.clearRect(0,0,c.width,c.height);});
      $('ms_unsold_n').innerHTML='<span class="note">지역을 선택하세요 — 검색으로 추가할 수 있습니다.</span>';
      $('ms_pipe_n').innerHTML=''; $('ms_move_n').innerHTML=''; return;
    }
    const K=n=>Math.round(n).toLocaleString();
    const F=t=>t?`${t.slice(0,4)}.${t.slice(4)}`:'—';
    /* ① 미분양 — 재고 지표라 이동합이 무의미(이미 스톡) → 항상 원자료. 지역 겹쳐보기 */
    {const L=_msSel.map((r,i)=>{const a=_msPick('unsold',r); return a?{...a,label:r,color:RP_PAL[i%RP_PAL.length]}:null;}).filter(Boolean);
     const one=_msSel.length===1;
     const b=one?_msPick('unsold_done'):null;
     if(L.length){ const A=_msAlign(b?[...L,b]:L);
       const arr=L.map(a=>({t:A.ts,v:A.map(a),label:a.label,color:a.color}));
       if(b) arr.push({t:A.ts,v:A.map(b),label:'준공후',color:'#7c2d12'});
       line('ms_unsold',arr,{provIdx:_msProv(A.ts,['unsold','unsold_done'])});
       const lv=x=>{ if(!x) return null; for(let i=x.v.length-1;i>=0;i--) if(x.v[i]!=null) return {ym:x.t[i],v:x.v[i]}; return null; };
       const lb=lv(b);
       const a0=L[0], la=lv(a0);
       const pk=a0?a0.v.reduce((p,c,i)=>(c!=null&&(p==null||c>a0.v[p]))?i:p,null):null;
       $('ms_unsold_n').innerHTML=
         `단위 <b>호</b> · 재고 지표라 원자료 그대로 · <b>시군구까지</b> 선택 가능`
         +`<br>`+L.map(a=>{const l=lv(a); return `<b style="color:${a.color}">${a.label}</b> ${l?K(l.v)+'호':'—'}<span class="note">${l?`(${F(l.ym)})`:''}</span>`;}).join(' &nbsp;·&nbsp; ')
         +`${lb?` · 준공후 <b>${K(lb.v)}호</b>${la&&la.v?` (${(lb.v/la.v*100).toFixed(0)}%)`:''}`:''}`
         +`${pk!=null&&a0?` · ${a0.label} 역대 최다 <b>${K(a0.v[pk])}호</b>(${F(a0.t[pk])})`:''}`
         +`<br><span class="note">미분양↑ = 수요 약세·공급과잉. <b>준공후 미분양</b>은 다 짓고도 안 팔린 물량이라 건설사 자금압박·할인분양으로 이어지는 악성 신호(지역 1개만 고르면 함께 표시).</span>`;
     }}
    /* ② 공급 파이프라인 — 유량(flow) 지표라 12개월 누적이 기본 */
    /* (2026-08-08) `.map(_msPick)` 는 map 의 2번째 인자(인덱스)를 _msPick(key, reg) 의
       reg 로 넘긴다. 인허가는 index 0 이 falsy 라 '전국'으로 잘 떨어졌지만
       착공(1)·준공(2)은 존재하지 않는 지역 '1','2' 를 찾다 null 이 돼 사라졌다.
       → 인자를 명시적으로 넘긴다. */
    {const P=['permit','start','done'].map(k=>_msPick(k)).filter(Boolean);
     if(P.length){ const A=_msAlign(P);
       const CO={'주택 인허가':'#2f6fed','주택 착공':'#e08e3c','주택 준공':'#27ae60'};
       const arr=P.map(p=>{ const v=A.map(p); return {t:A.ts, v:_msMode==='12m'?_ms12(A.ts,v):v,
                                                     label:p.label.replace('주택 ',''), color:CO[p.label]||'#64748b'}; });
       line('ms_pipe',arr,{provIdx:_msProv(A.ts,['permit','start','done'])});
       const last=a=>{ for(let i=a.v.length-1;i>=0;i--) if(a.v[i]!=null) return {ym:a.t[i],v:a.v[i]}; return null; };
       const yoy=a=>{ const l=last(a); if(!l) return null; const i=a.t.indexOf(l.ym), j=i-12;
         return (j>=0&&a.v[j])?((l.v/a.v[j]-1)*100):null; };
       $('ms_pipe_n').innerHTML=
         `<b>${(P[0]&&P[0].reg)||_msReg0()}</b>${P[0]&&P[0].fb?` <span style="color:#a06010">(시군구 통계 없음 — 시도로 대체)</span>`:''} · 단위 <b>호</b> · ${_msMode==='12m'?'<b>12개월 누적</b>(계절성 제거 — 연간 물량으로 읽으면 됨)':'월별 원자료(노이즈 큼)'}`
         +`<br>`+arr.map(a=>{const l=last(a), y=yoy(a);
             return `${a.label} <b>${l?K(l.v):'—'}</b>${y!=null?` <span class="${y>0?'up':'dn'}">(${y>0?'+':''}${y.toFixed(0)}% YoY)</span>`:''}`;}).join(' · ')
         +`<br><span class="note">인허가 → 착공까지 6개월~1년, 착공 → 준공까지 2~3년. <b>인허가·착공 급감은 2~3년 뒤 공급절벽</b>(가격 상승 압력), <b>준공 급증은 입주물량 증가</b>(전세 약세) 신호.</span>`;
     }}
    /* ③ 입주물량 — 확정(준공 실적) + 추정(착공을 실측 시차만큼 이동) */
    {const m=(_msD.series||{}).movein;
     const _r0=_msReg0(); if(m&&m.r[_r0]){
       const A=m.r[_r0], P=(m.p||{})[_r0]||[];
       const a12=_ms12(m.t,A), p12=_ms12(m.t,P);
       // 추정 구간은 실적이 끊긴 뒤부터라 12개월 합이 경계에서 비므로, 두 계열을 이어 붙여 계산
       const join=m.t.map((_,i)=>A[i]!=null?A[i]:(P[i]!=null?P[i]:null));
       const j12=_ms12(m.t,join);
       let cutI=-1; for(let i=A.length-1;i>=0;i--) if(A[i]!=null){cutI=i;break;}
       const act=j12.map((v,i)=>i<=cutI?v:null), prj=j12.map((v,i)=>i>=cutI?v:null);
       line('ms_move',[{t:m.t,v:act,label:'확정',color:'#27ae60'},
                       {t:m.t,v:prj,label:'추정',color:'#e08e3c'}],{provIdx:cutI>0?cutI:null});
       const lastOf=v=>{for(let i=v.length-1;i>=0;i--) if(v[i]!=null) return {i,v:v[i]}; return null;};
       const la=lastOf(act), lp=lastOf(prj);
       const K=n=>Math.round(n).toLocaleString();
       const F2=t=>t?`${t.slice(0,4)}.${t.slice(4)}`:'—';
       const chg=(la&&lp&&la.v)?((lp.v/la.v-1)*100):null;
       $('ms_move_n').innerHTML=
         `<b>${_msReg0()}</b> · <b>12개월 누적</b>(연간 입주물량) · 단위 호`
         +`<br>확정 <b class="up">${la?K(la.v):'—'}</b>(${la?F2(m.t[la.i]):'—'})`
         +` → 추정 <b class="dn">${lp?K(lp.v):'—'}</b>(${lp?F2(m.t[lp.i]):'—'})`
         +`${chg!=null?` · <b class="${chg>0?'up':'dn'}">${chg>0?'+':''}${chg.toFixed(0)}%</b>`:''}`
         +`<br><span class="note">${m.note||''}</span>`
         +`<br><span style="color:#a06010">⚠ 추정치는 착공 물량이 예정대로 준공된다는 가정이다. 공사 지연·중단(PF 부실 등)이 있으면 실제 입주는 더 늦고 적을 수 있다. <b>입주물량↑ → 전세 약세</b>, <b>↓ → 전세 강세</b>가 일반적 관계.</span>`;
     }}
  }

  /* ── (2026-08-08) 🏢 아파트 단지별 실거래 — /api/apt/* (apt.sqlite)
     매매·전세·월세를 한 단지 기준으로 겹쳐 본다. 면적(전용 m²)별로 분리해야
     평균이 의미를 갖기 때문에 면적 선택을 필수로 두고, 거래 최다 면적을 기본값으로 잡는다. ── */
  let _apInit=false, _apAr=0, _apId=0, _apReg="", _apKind="apt";
  function initApt(){
    if(_apInit) return; _apInit=true;
    const E4=s=>String(s??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
    const q=$('ap_q'), list=$('ap_list'); if(!q) return;
    const SGG={'11':'서울','26':'부산','27':'대구','28':'인천','30':'대전','31':'울산','36':'세종','41':'경기',
               '51':'강원','43':'충북','44':'충남','52':'전북','46':'전남','47':'경북','48':'경남','50':'제주'};
    let tmr=null;
    const search=()=>{
      const kw=(q.value||'').trim();
      // 단지명 2자 이상 또는 지역이 지정돼 있으면 조회(둘 다 주면 AND 로 좁힌다)
      if(kw.length<2&&!_apReg){ list.style.display='none'; return; }
      fetch(`/api/apt/search?q=${encodeURIComponent(kw)}&region=${encodeURIComponent(_apReg)}&kind=${_apKind}&n=60`)
        .then(r=>r.ok?r.json():null).then(d=>{
        const rows=(d&&d.rows)||[];
        list.innerHTML=rows.length?rows.map(r=>
          `<div data-id="${r.id}" style="padding:6px 10px;font-size:12.5px;cursor:pointer;border-bottom:1px solid #f2f4f7">
             <b>${E4(r.name)}</b> <span class="note">${E4(SGG[String(r.sgg).slice(0,2)]||'')} ${E4(r.umd)}${r.build_year?' · '+r.build_year+'년':''} · 거래 ${r.ns}건</span></div>`).join('')
          : '<div style="padding:7px 10px" class="note">검색 결과 없음 — 수집이 끝난 지역만 조회됩니다</div>';
        list.style.display='';
        list.querySelectorAll('[data-id]').forEach(el=>el.onclick=()=>{
          list.style.display='none'; q.value=''; _apAr=0; loadApt(+el.dataset.id); });
      }).catch(()=>{});
    };
    q.oninput=()=>{ clearTimeout(tmr); tmr=setTimeout(search,220); };
    q.onfocus=search;
    document.addEventListener('click',e=>{ if(!e.target.closest('#ap_q')&&!e.target.closest('#ap_list')) list.style.display='none'; });

    /* (2026-08-08) 지역으로도 찾기 — 단지명을 몰라도 동네를 골라 훑을 수 있게.
       고른 지역은 칩으로 남고, 단지명 검색과 AND 로 함께 걸린다. */
    const rq=$('ap_rq'), rlist=$('ap_rlist'), rcur=$('ap_rcur');
    let REG={sido:[],dong:[]}, tmr2=null;
    const showReg=()=>{
      const kw=(rq.value||'').trim();
      const cand=[...REG.sido.filter(x=>!kw||x.r.includes(kw)),
                  ...REG.dong.filter(x=>!kw||x.r.includes(kw))].slice(0,60);
      rlist.innerHTML=cand.length?cand.map(x=>
        `<div data-r="${E4(x.r)}" style="padding:5px 10px;font-size:12.5px;cursor:pointer;border-bottom:1px solid #f2f4f7">${x.r.includes(' ')?'':'★ '}${E4(x.r)} <span class="note">${x.n}곳</span></div>`).join('')
        : '<div style="padding:6px 10px" class="note">없음 — 수집이 끝난 지역만 나옵니다</div>';
      rlist.style.display='';
      rlist.querySelectorAll('[data-r]').forEach(el=>el.onclick=()=>{
        _apReg=el.dataset.r; rq.value=''; rlist.style.display='none'; drawRcur(); search();});};
    const drawRcur=()=>{rcur.innerHTML=_apReg
      ? `<span style="display:inline-flex;align-items:center;gap:3px;padding:2px 8px;font-size:12px;border-radius:10px;background:#1f293718;border:1px solid #1f2937"><b>📍</b>${E4(_apReg)}<b data-clr="1" style="cursor:pointer;color:#888">✕</b></span>`
      : '';
      const x=rcur.querySelector('[data-clr]'); if(x) x.onclick=()=>{_apReg=''; drawRcur(); search();};};
    rq.oninput=()=>{ clearTimeout(tmr2); tmr2=setTimeout(showReg,200); };
    rq.onfocus=showReg;
    document.addEventListener('click',e=>{ if(!e.target.closest('#ap_rq')&&!e.target.closest('#ap_rlist')) rlist.style.display='none'; });
    fetch(`/api/apt/regions?kind=${_apKind}`).then(r=>r.ok?r.json():null).then(d=>{ if(d) REG=d; }).catch(()=>{});
    drawRcur();
    /* 유형 전환 — 국토부가 주는 식별정보가 달라 검색 단위가 유형마다 다르다 */
    const KINDS=[['apt','아파트','단지명'],['offi','오피스텔','건물명'],['rh','연립다세대','건물명'],
                 ['nrg','상업업무용','법정동+지번'],['sh','단독다가구','법정동'],['land','토지','법정동']];
    const kbar=()=>{$('ap_kind').innerHTML=KINDS.map(([k,l,u])=>
        `<button data-k="${k}" title="${u} 단위로 조회" style="margin-right:3px;padding:3px 9px;font-size:11.5px;border:1px solid #d7dce3;border-radius:6px;cursor:pointer;background:${k===_apKind?'#1f2937':'#fff'};color:${k===_apKind?'#fff':'#333'}">${l}</button>`).join('')
        +`<span class="note" style="margin-left:6px">${(KINDS.find(x=>x[0]===_apKind)||[])[2]||''} 단위</span>`;
      $('ap_kind').querySelectorAll('button').forEach(b=>b.onclick=()=>{
        _apKind=b.dataset.k; kbar(); q.value=''; list.style.display='none';
        $('ap_head').innerHTML=''; $('ap_ars').innerHTML='';
        ['ap_main','ap_rent','ap_vol'].forEach(id=>{const c=$(id); if(!c) return;
          const g=c.getContext('2d'); c.width=c.clientWidth||900; c.height=c.clientHeight||300;
          g.clearRect(0,0,c.width,c.height);});
        $('ap_main_n').innerHTML='<span class="note">유형을 바꿨습니다 — 단지명 또는 지역으로 검색하세요.</span>';
        // (2026-08-08) 아파트와 비아파트는 DB 파일이 달라 지역 목록도 유형마다 다시 받아야 한다.
        fetch(`/api/apt/regions?kind=${_apKind}`).then(r=>r.ok?r.json():null).then(d=>{ if(d) REG=d; }).catch(()=>{});
        search();});};
    kbar();

    function loadApt(id){
      _apId=id;
      fetch(`/api/apt/series?id=${id}&ar=${_apAr||0}&kind=${_apKind}`).then(r=>r.ok?r.json():null).then(d=>{
        if(!d){ $('ap_head').textContent='조회 실패'; return; }
        _apAr=d.ar;
        const a=d.apt;
        $('ap_head').innerHTML=`<b style="font-size:14px;color:#111">${E4(a.name)}</b> · ${E4(SGG[String(a.sgg).slice(0,2)]||'')} ${E4(a.umd)} ${E4(a.jibun||'')}`
          +`${a.build_year?` · <b>${a.build_year}년 준공</b>(${new Date().getFullYear()-a.build_year}년차)`:''}`
          +`${a.road?` · ${E4(a.road)}`:''}`;
        /* 면적 칩 — 거래 많은 순, 전용 m² + 대략 평 병기 */
        $('ap_ars').innerHTML=d.ars.map(r=>`<button data-ar="${r.ar}" style="padding:3px 9px;font-size:12px;border:1px solid #d7dce3;border-radius:6px;cursor:pointer;background:${r.ar===d.ar?'#1f2937':'#fff'};color:${r.ar===d.ar?'#fff':'#333'}">${r.ar}㎡<span style="opacity:.7">·${Math.round(r.ar/3.3058)}평 (${r.n})</span></button>`).join('');
        $('ap_ars').querySelectorAll('button').forEach(b=>b.onclick=()=>{ _apAr=+b.dataset.ar; loadApt(_apId); });
        drawApt(d);
      }).catch(()=>{});
    }

    function drawApt(d){
      /* 공통 월 축 — 세 계열의 최소~최대 월을 1개월 간격으로 채운다(중간 공백은 null → 선 연결) */
      const all=[...d.sale,...d.jeon,...d.wol].map(r=>r.ym).sort();
      if(!all.length){ $('ap_main_n').textContent='해당 면적의 거래 기록이 없습니다'; return; }
      const ts=[]; let y=+all[0].slice(0,4), m=+all[0].slice(4);
      const ey=+all[all.length-1].slice(0,4), em=+all[all.length-1].slice(4);
      while(y<ey||(y===ey&&m<=em)){ ts.push(`${y}${String(m).padStart(2,'0')}`); if(++m>12){m=1;y++;} }
      const pick=(rows,f)=>{ const mp={}; rows.forEach(r=>mp[r.ym]=f(r)); return ts.map(t=>mp[t]??null); };
      const S=pick(d.sale,r=>r.avg), J=pick(d.jeon,r=>r.avg), W=pick(d.wol,r=>r.dep);
      const arr=[];
      if(S.some(v=>v!=null)) arr.push({t:ts,v:S,label:'매매',color:'#d9534f'});
      if(J.some(v=>v!=null)) arr.push({t:ts,v:J,label:'전세',color:'#2f6fed'});
      if(W.some(v=>v!=null)) arr.push({t:ts,v:W,label:'월세보증금',color:'#27ae60'});
      if(arr.length) line('ap_main',arr);
      /* 월 임대료(만원) · 거래 건수 — 단위가 달라 별도 축 */
      const R=pick(d.wol,r=>r.rent);
      if(R.some(v=>v!=null)) line('ap_rent',[{t:ts,v:R,label:'월임대료',color:'#7c3aed'}]);
      else {const c=$('ap_rent'); if(c) c.getContext('2d').clearRect(0,0,c.width,c.height);}
      const VS=pick(d.sale,r=>r.n), VJ=pick(d.jeon,r=>r.n), VW=pick(d.wol,r=>r.n);
      const va=[]; if(VS.some(v=>v!=null)) va.push({t:ts,v:VS,label:'매매',color:'#d9534f'});
      if(VJ.some(v=>v!=null)) va.push({t:ts,v:VJ,label:'전세',color:'#2f6fed'});
      if(VW.some(v=>v!=null)) va.push({t:ts,v:VW,label:'월세',color:'#27ae60'});
      if(va.length) line('ap_vol',va);
      /* 요약 — 최신 실거래 + 전세가율(같은 달 전세/매매) */
      const lastOf=rows=>rows.length?rows[rows.length-1]:null;
      const ls=lastOf(d.sale), lj=lastOf(d.jeon), lw=lastOf(d.wol);
      let jr=null;
      for(let i=d.jeon.length-1;i>=0&&jr==null;i--){ const s=d.sale.find(x=>x.ym===d.jeon[i].ym);
        if(s&&s.avg) jr={ym:d.jeon[i].ym,v:d.jeon[i].avg/s.avg*100}; }
      const F=t=>t?`${t.slice(0,4)}.${t.slice(4)}`:'—';
      $('ap_main_n').innerHTML=
        `전용 <b>${d.ar}㎡</b>(약 ${Math.round(d.ar/3.3058)}평) · 단위 <b>억원</b> — 월별 <b>평균 실거래가</b>(거래가 없는 달은 선으로 이어 표시)`
        +`<br>최신 — 매매 <b class="up">${ls?ls.avg.toFixed(2)+'억 ('+F(ls.ym)+' · '+ls.n+'건)':'—'}</b>`
        +` · 전세 <b>${lj?lj.avg.toFixed(2)+'억 ('+F(lj.ym)+')':'—'}</b>`
        +` · 월세 <b>${lw?lw.dep.toFixed(2)+'억 / 월 '+Math.round(lw.rent)+'만원 ('+F(lw.ym)+')':'—'}</b>`
        +`${jr?` · <b>전세가율 ${jr.v.toFixed(0)}%</b>(${F(jr.ym)}) — 높을수록 갭 작아 매매 전환 압력↑`:''}`
        +`<br><span style="color:#a06010">⚠ 거래가 적은 달은 1~2건 평균이라 튈 수 있습니다. 같은 면적이라도 층·향·수리 상태 차이가 반영되지 않은 원본 신고가입니다.</span>`;
    }
    /* 적재 현황 안내 — 백필 진행 중이면 검색 범위가 제한적임을 알린다 */
    fetch('/api/apt/stat').then(r=>r.ok?r.json():null).then(s=>{
      if(!s) return;
      $('ap_head').innerHTML=s.apt
        ? `<span class="note">단지 <b>${s.apt.toLocaleString()}</b>곳 적재 · 시군구 ${s.sgg}곳 · ${s.ym0?String(s.ym0).slice(0,4)+'.'+String(s.ym0).slice(4):''}~${s.ym1?String(s.ym1).slice(0,4)+'.'+String(s.ym1).slice(4):''} — 전국 백필 진행 중이라 수집이 끝난 지역부터 검색됩니다. 단지명을 입력해 보세요.</span>`
        : `<span class="note">단지 DB 생성 대기 — 다음 수집(매일 07:20)부터 채워집니다.</span>`;
    }).catch(()=>{});
  }

  /* ══════════════════════════════════════════════════════════════════════════
     (2026-08-10) 💳 가계대출 + ⚠ 대출 연체율 — hcredit.json (ECOS · 매일 07:15)

     가계대출 잔액은 20년째 우상향이라 그림이 안 나온다. 신호는 **월별 증감액**에 있다.
     주택관련대출 순증이 꺾이면 몇 달 뒤 거래량이 따라 꺾이는 패턴이 반복된다.
     연체율은 그 반대편 — 가계·주택관련 연체율이 오르면 급매·경매 물량이 늘고,
     지역별로 보면 어느 지역이 먼저 무너지는지 총량보다 앞서 드러난다.
     ══════════════════════════════════════════════════════════════════════════ */

  /* 0선 기준 누적 막대. line() 은 선만 그린다 —
     증감액은 부호가 뒤집히는 지표라 0 기준선과 막대가 있어야
     '순증에서 순감으로 돌아선 달'이 한눈에 들어온다. */
  function bars(cvId, t, series, opts){
    opts=opts||{};
    const cv=$(cvId); if(!cv) return;
    const W=cv.clientWidth||700, H=cv.clientHeight||300; cv.width=W; cv.height=H;
    const x=cv.getContext('2d'); x.clearRect(0,0,W,H);
    if(!t||!t.length||!series||!series.length) return;
    /* (2026-08-10) opts.r2 = 보조축(좌측) 계열 — 단위가 전혀 다른 지표를 겹쳐 본다.
       예: 가계대출 증감액(조원, 막대) 위에 주택 매매거래량(건, 선).
       같은 축에 올리면 조원(±20)이 건수(수만)에 눌려 일직선이 된다. */
    const R2=(opts.r2&&opts.r2.length&&opts.r2.some(s=>s.v&&s.v.some(v=>v!=null)))?opts.r2:null;
    const P={l:R2?46:8,r:56,t:16,b:18}, N=t.length;
    let lo=0, hi=0;
    for(let i=0;i<N;i++){ let up=0,dn=0;
      series.forEach(s=>{const v=s.v[i]; if(v==null) return; v>=0?up+=v:dn+=v;});
      if(up>hi) hi=up; if(dn<lo) lo=dn; }
    (opts.extra||[]).forEach(s=>s.v.forEach(v=>{ if(v==null) return; if(v>hi)hi=v; if(v<lo)lo=v; }));
    if(hi===lo){ hi=1; lo=-1; }
    const pad=(hi-lo)*0.08; hi+=pad; lo-=pad;
    const X=i=>P.l+(W-P.l-P.r)*(i+0.5)/N, Y=v=>P.t+(H-P.t-P.b)*(1-(v-lo)/(hi-lo));
    const bw=Math.max(1,(W-P.l-P.r)/N*0.72), dec=(hi-lo)<10?1:0;
    x.font='10px sans-serif'; x.strokeStyle='#eceff3'; x.fillStyle='#98a2ad';
    for(let g=0;g<=4;g++){ const yv=lo+(hi-lo)*g/4, yy=Y(yv);
      x.beginPath(); x.moveTo(P.l,yy); x.lineTo(W-P.r,yy); x.stroke();
      x.fillText(yv.toFixed(dec), W-P.r+4, yy+3); }
    x.strokeStyle='#8f9aa6'; x.lineWidth=1.2;
    x.beginPath(); x.moveTo(P.l,Y(0)); x.lineTo(W-P.r,Y(0)); x.stroke(); x.lineWidth=1;
    for(let i=0;i<N;i++){ let up=0,dn=0;
      series.forEach(s=>{ const v=s.v[i]; if(v==null) return; x.fillStyle=s.color;
        if(v>=0){ x.fillRect(X(i)-bw/2, Y(up+v), bw, Math.max(0.6,Y(up)-Y(up+v))); up+=v; }
        else    { x.fillRect(X(i)-bw/2, Y(dn),    bw, Math.max(0.6,Y(dn+v)-Y(dn))); dn+=v; } }); }
    (opts.extra||[]).forEach(s=>{ x.strokeStyle=s.color; x.lineWidth=1.8;
      x.beginPath(); let st=false;
      for(let i=0;i<N;i++){ const v=s.v[i]; if(v==null) continue;
        st?x.lineTo(X(i),Y(v)):(x.moveTo(X(i),Y(v)),st=true); }
      x.stroke(); x.lineWidth=1; });
    if(R2){                                              // 보조축 — 눈금은 좌측에
      let l2=Infinity,h2=-Infinity;
      R2.forEach(s=>s.v.forEach(v=>{ if(v==null) return; if(v<l2)l2=v; if(v>h2)h2=v; }));
      if(h2===l2){ h2=l2+1; }
      const p2=(h2-l2)*0.10; l2-=p2; h2+=p2;
      const Y2=v=>P.t+(H-P.t-P.b)*(1-(v-l2)/(h2-l2));
      x.fillStyle='#98a2ad'; x.textAlign='left';
      for(let g=0;g<=4;g++){ const yv=l2+(h2-l2)*g/4;
        x.fillText(Math.round(yv).toLocaleString(), 2, Y2(yv)+3); }
      R2.forEach(s=>{ x.strokeStyle=s.color; x.lineWidth=1.9; x.globalAlpha=.95;
        x.beginPath(); let st=false;
        for(let i=0;i<N;i++){ const v=s.v[i]; if(v==null) continue;
          st?x.lineTo(X(i),Y2(v)):(x.moveTo(X(i),Y2(v)),st=true); }
        x.stroke(); x.globalAlpha=1; x.lineWidth=1; });
    }
    x.fillStyle='#98a2ad';
    for(let i=0;i<N;i++){ const s=String(t[i]);
      if(s.slice(4)==='01') x.fillText(s.slice(0,4), X(i)-12, H-4); }
    let lx=P.l+2;                                        // 범례 — 좌상단 가로 배치
    series.concat(opts.extra||[]).concat(R2||[]).forEach(s=>{ x.fillStyle=s.color; x.fillRect(lx,P.t-10,8,8);
      x.fillStyle='#5b6673'; x.fillText(s.label, lx+11, P.t-3);
      lx+=13+x.measureText(s.label).width+8; });
  }

  /* 세그먼트 버튼 한 줄 — 부동산 탭의 다른 카드(rd_sd·et_met)와 같은 모양 */
  function segbar(id, opts, cur, set, after){
    const el=$(id); if(!el) return;
    el.innerHTML=opts.map(([k,l])=>{ const on=String(k)===String(cur());
      return `<button data-k="${k}" style="padding:3px 9px;font-size:11.5px;border:1px solid #d7dce3;`
        +`border-radius:6px;cursor:pointer;background:${on?'#1f2937':'#fff'};color:${on?'#fff':'#333'}">${l}</button>`;}).join('');
    el.querySelectorAll('button').forEach(b=>b.onclick=()=>{ set(b.dataset.k); after&&after(); });
  }

  const _hcNum=v=>v==null?'—':(Math.abs(v)>=100?Math.round(v).toLocaleString():v.toFixed(1));
  const _hcSgn=v=>v==null?'—':(v>0?'+':'')+_hcNum(v);

  let _hcInit=false, _hcMode='chg', _hcSplit='use', _hcSpan='60', _hcVol='all', _hcVReg='전국';
  /* (2026-08-10) 주택 매매거래량 — htrade.json (KOSIS 국토부/부동산원 · 매일 07:20)
     RTMS 실거래 DB 는 아직 전국 일부 시군구만 채워져 있어 전국 총량으로 못 쓴다.
     총량은 국토부 공식 집계를 그대로 겹친다. ym 키로 맞춰야 해서 맵으로 들고 있는다. */
  let _htRaw=null, _htP=null;
  /* 두 카드(가계대출·아파트 실거래 지역비교)가 같이 쓰므로 한 번만 받아 공유한다 */
  const htrade=()=>{ if(!_htP) _htP=fetch('/api/db/htrade').then(r=>r.ok?r.json():null)
      .then(h=>{ if(h&&h.t&&h.t.length) _htRaw=h; return _htRaw; }).catch(()=>null);
    return _htP; };
  const _htMap=(kind,reg)=>{ if(!_htRaw||!_htRaw.t) return null;
    const a=(_htRaw[kind]||{})[reg]; if(!a) return null;
    const m={}; _htRaw.t.forEach((ym,i)=>{ if(a[i]!=null) m[ym]=a[i]; }); return m; };
  /* hcredit 의 t 배열(2004~)에 거래량(2006~)을 맞춘다. roll=true 면 12개월 합. */
  function _htAlign(t, kind, reg, roll){
    const m=_htMap(kind,reg); if(!m) return null;
    const T=_htRaw.t, idx={}; T.forEach((ym,i)=>idx[ym]=i);
    const arr=(_htRaw[kind]||{})[reg]||[];
    return t.map(ym=>{ const i=idx[ym]; if(i==null) return null;
      if(!roll) return arr[i]==null?null:arr[i];
      if(i<11) return null;
      let s=0; for(let k=i-11;k<=i;k++){ if(arr[k]==null) return null; s+=arr[k]; } return s; });
  }
  function initHCredit(){
    if(_hcInit) return; _hcInit=true;
    fetch('/api/db/hcredit').then(r=>r.ok?r.json():null).then(d=>{
      if(!d||!d.hh||!(d.hh.t||[]).length){
        const e=$('hc_main_n'); if(e) e.textContent='수집 대기 중 — 다음 수집(매일 07:15)부터 표시됩니다.'; return; }
      {const e=$('hc_asof'); if(e) e.textContent=`한국은행 ECOS · 말잔(조원) · 수집 ${d.asof||''}`;}

      const bar=()=>{
        segbar('hc_mode', [['chg','월별 증감액'],['bal','잔액']], ()=>_hcMode, v=>_hcMode=v, redraw);
        segbar('hc_split',[['use','용도별'],['ind','업권별']],   ()=>_hcSplit,v=>_hcSplit=v,redraw);
        segbar('hc_span', [['36','3년'],['60','5년'],['120','10년'],['999','전체']], ()=>_hcSpan, v=>_hcSpan=v, redraw);
        segbar('hc_vol',  [['off','끄기'],['all','주택 전체'],['apt','아파트']], ()=>_hcVol, v=>_hcVol=v, redraw);
        const regs=_htRaw?Object.keys(_htRaw.all||{}):['전국'];
        const ord=['전국','서울','경기','인천','부산','대구','광주','대전','울산','세종',
                   '강원','충북','충남','전북','전남','경북','경남','제주'].filter(r=>regs.includes(r));
        segbar('hc_vreg', ord.map(r=>[r,r]), ()=>_hcVReg, v=>_hcVReg=v, redraw);
      };
      const redraw=()=>{ bar(); draw(); };
      htrade().then(h=>{ if(h) redraw(); });

      function draw(){
        const B=(_hcSplit==='use')?d.hh:d.ind, T=B.t||[], S=B.s||{};
        const want=(_hcSpan==='999')?T.length:+_hcSpan;
        const st=Math.max(0, T.length-Math.min(want,T.length));
        const t=T.slice(st);
        const D=k=>{ const a=S[k]||[]; return a.map((v,i)=>(i===0||v==null||a[i-1]==null)?null:v-a[i-1]); };
        const cut=a=>(a||[]).slice(st);
        const last=a=>{ for(let i=a.length-1;i>=0;i--) if(a[i]!=null) return a[i]; return null; };

        if(_hcMode==='chg'){
          const defs=(_hcSplit==='use')
            ? [['주담대_전체','주택관련대출','#e08e3c'], ['기타_전체','기타대출','#5f9e5f']]
            : [['예금은행','예금은행','#2f6fed'], ['비은행','비은행권','#c2185b']];
          const ser=defs.map(([k,l,c])=>({v:cut(D(k)), label:l, color:c}));
          const tot={v:cut(D('전체')), label:'합계', color:'#1f2937'};
          const vol=(_hcVol==='off')?null:_htAlign(t,_hcVol,_hcVReg,false);
          bars('hc_main', t, ser, {extra:[tot], r2: vol?[{v:vol, color:'#0ea5e9',
            label:`${_hcVReg} ${_hcVol==='apt'?'아파트':'주택'} 거래량(건·좌축)`}]:null});
          const lt=t[t.length-1];
          const parts=ser.map(s=>`${s.label} <b class="${last(s.v)>0?'up':'dn'}">${_hcSgn(last(s.v))}조</b>`);
          const y12=(()=>{const a=S['전체']||[]; const n=a.length;
            return (n>13&&a[n-1]!=null&&a[n-13]!=null)?a[n-1]-a[n-13]:null;})();
          $('hc_main_n').innerHTML=`<b>${fm(lt)}</b> 전월 대비 — ${parts.join(' · ')}`
            +` · 합계 <b class="${last(tot.v)>0?'up':'dn'}">${_hcSgn(last(tot.v))}조</b>`
            +(y12!=null?` · 최근 12개월 순증 <b>${_hcSgn(y12)}조</b>`:'')
            +` <span class="note">— 0선 아래로 내려간 달은 가계대출이 줄어든 달. `
            +`주택관련대출 순증이 꺾이면 통상 몇 달 뒤 실거래 건수가 따라 꺾인다. ECOS 공표 ~1개월 지연.</span>`
            +(vol?`<br><span class="note">🔵 하늘색 선 = <b>${_hcVReg} ${_hcVol==='apt'?'아파트':'주택'} 매매거래량</b>`
              +`(좌축·건, ${(_htRaw&&_htRaw.src)||'KOSIS'}) — 막대(대출 증감)가 먼저 움직이고 선(거래량)이 따라오는지 보는 차트다. `
              +`거래량은 국토부 공표가 ~1개월 더 늦고 최근 1~2개월은 잠정치라 오른쪽 끝은 덜 채워져 보인다.</span>`:'');
        } else {
          const defs=(_hcSplit==='use')
            ? [['전체','전체','#1f2937'], ['주담대_전체','주택관련','#e08e3c'], ['기타_전체','기타','#5f9e5f'],
               ['주담대_은행','주택관련(은행)','#b45309']]
            : [['전체','전체','#1f2937'], ['예금은행','예금은행','#2f6fed'], ['비은행','비은행권','#c2185b'],
               ['저축은행','저축은행','#7c3aed'], ['상호금융','상호금융','#0e9aa7'], ['새마을금고','새마을금고','#9e9d24']];
          const bvol=(_hcVol==='off')?null:_htAlign(t,_hcVol,_hcVReg,false);
          line('hc_main', defs.filter(([k])=>S[k]).map(([k,l,c])=>({t, v:cut(S[k]), label:l, color:c})),
               {r2: bvol?[{v:bvol, color:'#0ea5e9', label:`${_hcVReg} 거래량`}]:null});
          const a=S['전체']||[], n=a.length, y1=yoy(T,a);
          $('hc_main_n').innerHTML=`<b>${fm(T[n-1])} 말잔 = ${_hcNum(a[n-1])}조원</b>`
            +(y1!=null?` · YoY <b class="${y1>0?'up':'dn'}">${(y1>0?'+':'')+y1.toFixed(1)}%</b>`:'')
            +` <span class="note">— 잔액은 늘 우상향이라 방향은 '월별 증감액' 탭에서 봐야 한다.</span>`;
        }

        /* 12개월 누적 증감 — 계절성(1월 감소·연말 증가)을 걷어낸 연간 순증 추세 */
        {const R=k=>{ const a=S[k]||[];
           return a.map((v,i)=>(i<12||v==null||a[i-12]==null)?null:v-a[i-12]); };
         const rdefs=(_hcSplit==='use')
           ? [['전체','전체','#1f2937'], ['주담대_전체','주택관련','#e08e3c'], ['기타_전체','기타','#5f9e5f']]
           : [['전체','전체','#1f2937'], ['예금은행','예금은행','#2f6fed'], ['비은행','비은행권','#c2185b']];
         const rvol=(_hcVol==='off')?null:_htAlign(t,_hcVol,_hcVReg,true);
         line('hc_roll', rdefs.filter(([k])=>S[k]).map(([k,l,c])=>({t, v:cut(R(k)), label:l, color:c})),
              {base:0, r2: rvol?[{v:rvol, color:'#0ea5e9',
                label:`${_hcVReg} 거래량 12M누적`}]:null});
         const rt=R('전체'), lv=last(rt);
         $('hc_roll_n').innerHTML=`최근 12개월 순증 <b class="${lv>0?'up':'dn'}">${_hcSgn(lv)}조</b>`
           +` <span class="note">— 0선을 뚫고 내려가면 가계 디레버리징(자금 이탈) 국면. 정책(DSR·대출총량) 효과가 여기에 가장 먼저 찍힌다.</span>`
           +(rvol?`<br><span class="note">🔵 ${_hcVReg} 매매거래량 12개월 누적(좌축·건) — 둘 다 계절성을 뺀 값이라 <b>선후 관계가 가장 또렷하게</b> 보인다.</span>`:'');}

        /* 전세자금·정책대출 — 용도별 블록에만 있다 */
        {const P=d.hh.s||{}, PT=d.hh.t||[];
         const pst=Math.max(0, PT.length-Math.min((_hcSpan==='999')?PT.length:+_hcSpan, PT.length));
         const pdefs=[['전세자금','예금은행 전세자금','#0e9aa7'], ['정책대출','정책대출(HF·주택기금)','#7c3aed']];
         const av=pdefs.filter(([k])=>P[k]);
         if(av.length){
           line('hc_pol', av.map(([k,l,c])=>({t:PT.slice(pst), v:(P[k]||[]).slice(pst), label:l, color:c})));
           const f=k=>{const a=P[k]||[]; for(let i=a.length-1;i>=0;i--) if(a[i]!=null) return a[i]; return null;};
           $('hc_pol_n').innerHTML=`전세자금 <b>${_hcNum(f('전세자금'))}조</b> · 정책대출 <b>${_hcNum(f('정책대출'))}조</b>`
             +` <span class="note">— 전세자금대출 잔액이 늘면 전세 수요가 살아있다는 뜻(전세가 지지). `
             +`정책대출은 금리와 무관하게 공급되는 자금이라 시장금리만 봐서는 안 되는 이유다. 2015년부터 제공.</span>`;
         } else { $('hc_pol_n').textContent='전세자금·정책대출 계열 없음 — hcredit.py --full 로 재수집하세요.'; }}
      }
      redraw();
    }).catch(()=>{});
  }

  /* ⚠ 대출 연체율 — 전국 장기(901Y054, 1일 이상)와 지역별(141Y005, 1개월 이상)은
     연체 인정 기준이 달라 숫자가 다르다. 같은 차트에 섞지 않고 탭으로 나눈다. */
  const DQPAL=['#d9534f','#2f6fed','#27ae60','#e08e3c','#7c3aed','#0e9aa7','#c2185b','#5d4037',
               '#455a64','#9e9d24','#00838f','#e91e63','#3f51b5','#ff9800','#8bc34a','#1976d2','#795548','#43a047'];
  let _dqInit=false, _dqView='reg', _dqKind='가계', _dqBank='은행전체',
      _dqRegs=['전국','서울','경기','인천'];
  /* (2026-08-16) 급매 압력 — firesale.json (실거래로 만든 대리지표 · 매일 07:30)
     '연체율이 오르면 급매가 늘어난다'는 카드 설명을 말로만 두지 않고 같은 차트에 겹친다.
     연체율은 0.1~1.2% 대, 급매 비중은 5~50% 대라 축을 나눠야 한다(line 의 r2). */
  /* (2026-08-16) 겹쳐볼 지표 정의 — 급매(실거래 자체계산, %)와 경매(등기정보광장, 건).
     단위가 섞이면 한 축에 그대로 못 올린다 → 섞였을 때만 '자기 최대=100' 지수로 환산한다.
     같은 단위끼리만 골랐으면 실제 값 그대로 그린다(눈금이 곧 값이 되게). */
  const OVDEF={
    deep:    {src:'fs', lab:'급매 체결',      unit:'%',  color:'#0ea5e9'},
    down:    {src:'fs', lab:'하락거래',       unit:'%',  color:'#0284c7'},
    open_all:{src:'au', lab:'경매 개시',      unit:'건', color:'#a855f7'},
    open_v:  {src:'au', lab:'임의경매 개시',  unit:'건', color:'#7c3aed'},
    open_f:  {src:'au', lab:'강제경매 개시',  unit:'건', color:'#c084fc'},
    sold_v:  {src:'au', lab:'임의경매 매각',  unit:'건', color:'#ea580c'},
    sold_f:  {src:'au', lab:'강제경매 매각',  unit:'건', color:'#fb923c'},
    /* (2026-08-22) 대법원 법원경매정보 매각통계 — 전국만 제공(지역 필터가 서버에서 안 먹는다).
       물량(등기정보광장·지역별)과 짝을 이루는 '가격' 쪽 지표다. */
    bid_apt_rate:   {src:'au', lab:'아파트 낙찰가율', unit:'%', color:'#16a34a'},
    bid_all_rate:   {src:'au', lab:'전체 낙찰가율',   unit:'%', color:'#65a30d'},
    bid_apt_sldrate:{src:'au', lab:'아파트 매각률',   unit:'%', color:'#0d9488'},
  };
  const OVMAX=6;                                   // 선이 너무 많으면 못 읽는다
  let _fsRaw=null, _fsP=null, _fsSel=[], _auRaw=null, _auP=null;
  const firesale=()=>{ if(!_fsP) _fsP=fetch('/api/db/firesale').then(r=>r.ok?r.json():null)
      .then(f=>{ if(f&&f.t&&f.t.length) _fsRaw=f; return _fsRaw; }).catch(()=>null);
    return _fsP; };
  /* (2026-08-16) 경매 물량 — auction.json (대법원 등기정보광장 · 매일 07:35)
     '연체율↑ → 급매↑ → 경매↑' 세 단계를 한 차트에서 잇는다. 경매 개시는 건수(수천~만),
     연체율은 %(0.1~1.2) 라 축을 나눠야 한다. */
  const auction=()=>{ if(!_auP) _auP=fetch('/api/db/auction').then(r=>r.ok?r.json():null)
      .then(a=>{ if(a&&a.t&&a.t.length) _auRaw=a; return _auRaw; }).catch(()=>null);
    return _auP; };
  /* 연체율 t 배열(YYYYMM)에 겹칠 시계열을 맞춘다. 없는 달은 null. */
  function _ovAlign(src, t, kind, reg){
    if(!src) return null;
    const a=(src[kind]||{})[reg]; if(!a) return null;
    const idx={}; src.t.forEach((ym,i)=>idx[ym]=i);
    return t.map(ym=>{ const i=idx[ym]; return i==null?null:(a[i]==null?null:a[i]); });
  }
  const _fsAlign=(t,kind,reg)=>_ovAlign(_fsRaw,t,kind,reg);
  function initDelq(){
    if(_dqInit) return; _dqInit=true;
    fetch('/api/db/hcredit').then(r=>r.ok?r.json():null).then(d=>{
      if(!d||!d.dreg||!(d.dreg.t||[]).length){
        const e=$('dq_main_n'); if(e) e.textContent='수집 대기 중 — 다음 수집(매일 07:15)부터 표시됩니다.'; return; }
      const REGS=d.dreg.regions||[];
      const KINDS=['가계','주택관련','대기업','중소기업','기업','전체'].filter(k=>d.dreg.s&&d.dreg.s[k]);
      if(KINDS.length && !KINDS.includes(_dqKind)) _dqKind=KINDS[0];
      _dqRegs=_dqRegs.filter(r=>REGS.includes(r));
      if(!_dqRegs.length) _dqRegs=REGS.slice(0,4);

      const bar=()=>{
        segbar('dq_view', [['reg','🗺 지역별 (1개월 이상 · 2019.12~)'],['nat','📉 전국 장기 (1일 이상 · 2005~)']],
               ()=>_dqView, v=>_dqView=v, redraw);
        const lab=$('dq_kindlab'); if(lab) lab.textContent=(_dqView==='reg')?'차주':'은행';
        if(_dqView==='reg'){
          segbar('dq_kind', KINDS.map(k=>[k,k]), ()=>_dqKind, v=>_dqKind=v, redraw);
          $('dq_regwrap').style.display='inline-flex';
          segbar('dq_preset', [['sudo','수도권'],['metro','5대광역시'],['all','전지역']], ()=>'', k=>{
            _dqRegs = k==='sudo' ? ['전국','서울','경기','인천']
                    : k==='metro'? ['전국','부산','대구','인천','광주','대전'].filter(r=>REGS.includes(r))
                    : REGS.slice();
          }, redraw);
          $('dq_reg').innerHTML=REGS.map(r=>{ const on=_dqRegs.includes(r);
            return `<button data-r="${r}" style="padding:2px 7px;font-size:11px;border:1px solid ${on?'#1f2937':'#d7dce3'};`
              +`border-radius:6px;cursor:pointer;background:${on?'#1f2937':'#fff'};color:${on?'#fff':'#5b6672'}">${r}</button>`;}).join('');
          $('dq_reg').querySelectorAll('button').forEach(b=>b.onclick=()=>{
            const r=b.dataset.r;
            _dqRegs = _dqRegs.includes(r) ? _dqRegs.filter(z=>z!==r) : _dqRegs.concat([r]);
            redraw(); });
        } else {
          const BANKS=Object.keys((d.delq&&d.delq.s)||{});
          if(BANKS.length && !BANKS.includes(_dqBank)) _dqBank=BANKS[0];
          segbar('dq_kind', BANKS.map(k=>[k,k]), ()=>_dqBank, v=>_dqBank=v, redraw);
          $('dq_regwrap').style.display='none';
        }
        /* 중복 선택 — 급매·경매를 함께 얹어 '연체율↑ → 급매↑ → 경매↑' 순서를 한 화면에서 본다 */
        const has=k=>_fsSel.includes(k), avail=k=>!!((OVDEF[k].src==='fs'?_fsRaw:_auRaw)||{})[k];
        $('dq_fs').innerHTML=`<button data-c="1" style="padding:2px 8px;font-size:11px;border:1px solid #d7dce3;border-radius:6px;cursor:pointer;background:${_fsSel.length?'#fff':'#1f2937'};color:${_fsSel.length?'#888':'#fff'}">끄기</button>`
          +Object.keys(OVDEF).map(k=>{ const on=has(k), ok=avail(k);
            return `<button data-k="${k}" ${ok?'':'disabled'} title="${OVDEF[k].unit}"`
              +` style="padding:2px 8px;font-size:11px;border:1px solid ${on?OVDEF[k].color:'#d7dce3'};border-radius:6px;`
              +`cursor:${ok?'pointer':'not-allowed'};background:${on?OVDEF[k].color:'#fff'};`
              +`color:${on?'#fff':(ok?'#5b6672':'#c3c9d1')}">${OVDEF[k].lab}</button>`;}).join('');
        $('dq_fs').querySelector('[data-c]').onclick=()=>{ _fsSel=[]; redraw(); };
        $('dq_fs').querySelectorAll('[data-k]').forEach(b=>b.onclick=()=>{
          const k=b.dataset.k;
          _fsSel = has(k) ? _fsSel.filter(z=>z!==k) : _fsSel.concat([k]);
          redraw(); });
      };
      const redraw=()=>{ bar(); draw(); };
      firesale().then(f=>{ if(f) redraw(); });
      auction().then(a=>{ if(a) redraw(); });

      /* 급매 지표 각주 — 자체 계산 지표라 '무엇을 어떻게 셌는지'를 반드시 같이 적는다.
         공식 통계가 아닌 값을 근거처럼 보이게 두면 안 된다. */
      const _ovSrc=k=>OVDEF[k].src==='fs'?_fsRaw:_auRaw;
      function _fsNote(){
        const sel=_fsSel.filter(k=>_ovSrc(k)); if(!sel.length) return '';
        const units=[...new Set(sel.map(k=>OVDEF[k].unit))];
        const P=(_fsRaw||{}).params||{};
        const bits=sel.map(k=>{
          const src=_ovSrc(k), t=src.t||[], a=(src[k]||{})['전국']||[];
          let li=-1; for(let i=a.length-1;i>=0;i--) if(a[i]!=null){li=i;break;}
          const v=li<0?'—':(OVDEF[k].unit==='%'?a[li]+'%':Math.round(a[li]).toLocaleString()+'건');
          return `<b style="color:${OVDEF[k].color}">${OVDEF[k].lab}</b> ${fm(t[li])} ${v}`;
        });
        let s=`<br><span class="note">겹쳐본 지표 — ${bits.join(' · ')}`;
        if(units.length>1) s+=`<br>⚠ <b>%와 건수를 함께 골라 좌축을 '자기 최대=100' 지수로 바꿨습니다</b> — 선의 <b>모양·시점</b>만 비교하세요. 실제 값은 위 요약 숫자입니다.`;
        if(sel.some(k=>OVDEF[k].src==='fs'))
          s+=`<br>급매·하락거래 = 같은 단지·면적의 직전 ${P.window||6}개월 중위가 대비 `
            +`최저체결가 ${Math.round((P.deep_cut||0.9)*100)}%·중위가 ${Math.round((P.down_cut||0.95)*100)}% 미만인 칸의 비중. `
            +`국토부 실거래로 서버가 계산한 <b>대리지표(공식 통계 아님)</b> · 2005년~. 최고는 2022-11 48.2%(금리인상 급락장).`;
        if(sel.some(k=>OVDEF[k].src==='au'))
          s+=`<br>경매 = 대법원 등기정보광장. <b>개시</b>는 경매가 시작된 물건 수(물량 유입), <b>매각</b>은 낙찰돼 소유권이 넘어간 건수. `
            +`임의경매는 담보권 실행이라 연체율과 직접 이어진다. <b>API 가 최근 3년치만</b> 제공하고 이번 달은 집계 중이라 낮게 보인다.`;
        return s+`</span>`;
      }
      /* 겹칠 계열 — (지표 × 지역) 조합. 단위가 섞이면 지수로 환산해 축을 하나로 쓴다. */
      function fsSeries(T){
        const sel=_fsSel.filter(k=>_ovSrc(k)); if(!sel.length) return null;
        const regs=(_dqView==='reg'?_dqRegs:['전국']);
        const out=[];
        for(const k of sel){
          const src=_ovSrc(k);
          for(const r of regs){
            if(out.length>=OVMAX) break;
            if(!((src[k]||{})[r])) continue;
            const v=_ovAlign(src,T,k,r);
            if(v&&v.some(x=>x!=null))
              out.push({v, key:k, color:OVDEF[k].color,
                        label:`${regs.length>1?r+' ':''}${OVDEF[k].lab}`});
          }
        }
        if(!out.length) return null;
        const units=[...new Set(sel.map(k=>OVDEF[k].unit))];
        if(units.length>1){                     // %와 건수 혼합 → 각자 최대=100 으로 환산
          out.forEach(s=>{ const mx=Math.max(...s.v.filter(x=>x!=null));
            if(mx>0){ s.v=s.v.map(x=>x==null?null:Math.round(x/mx*1000)/10); }
            s.label+=' (지수)'; });
        } else {
          out.forEach(s=>{ s.label+=`(${units[0]}·좌축)`; });
        }
        return out;
      }

      function draw(){
        if(_dqView==='reg'){
          const T=d.dreg.t||[], S=(d.dreg.s||{})[_dqKind]||{};
          const arr=_dqRegs.filter(r=>S[r]).map((r,i)=>({t:T, v:S[r], label:r,
            color:r==='전국'?'#1f2937':DQPAL[REGS.indexOf(r)%DQPAL.length]}));
          line('dq_main', arr, {r2:fsSeries(T)});
          {const e=$('dq_asof'); if(e) e.textContent=`예금은행 지역별 연체율(1개월 이상) · 수집 ${d.asof||''}`;}
          const nat=S['전국']||[], n=T.length, lv=nat[n-1], pv=nat[n-2], py=nat[n-13];
          // 최신월 기준 높은 지역 순 — 어디가 먼저 무너지는지가 이 카드의 핵심
          const rank=Object.entries(S).filter(([r,a])=>r!=='전국'&&a[n-1]!=null)
            .sort((a,b)=>b[1][n-1]-a[1][n-1]).slice(0,5)
            .map(([r,a])=>`${r} <b>${a[n-1].toFixed(2)}</b>`);
          $('dq_main_n').innerHTML=`<b>${_dqKind}</b> 연체율 ${fm(T[n-1])} — 전국 <b>${lv!=null?lv.toFixed(2)+'%':'—'}</b>`
            +(pv!=null&&lv!=null?` (전월 ${lv-pv>0?'+':''}${(lv-pv).toFixed(2)}p)`:'')
            +(py!=null&&lv!=null?` · 전년 <b class="${lv-py>0?'dn':'up'}">${lv-py>0?'+':''}${(lv-py).toFixed(2)}p</b>`:'')
            +(rank.length?`<br>높은 지역 — ${rank.join(' · ')}`:'')
            +` <span class="note">— 연체율이 오르는 지역은 급매·경매 물량이 먼저 늘어난다. `
            +`'주택관련'은 주담대만 뽑은 것이라 부동산 스트레스를 가장 직접적으로 보여준다. 1개월 이상 연체 기준.</span>`
            +_fsNote();
        } else {
          const T=d.delq.t||[], S=(d.delq.s||{})[_dqBank]||{};
          const defs=[['가계','가계대출','#d9534f'],['기업','기업대출','#2f6fed'],['신용카드','신용카드대출','#e08e3c']];
          line('dq_main', defs.filter(([k])=>S[k]).map(([k,l,c])=>({t:T, v:S[k], label:l, color:c})),
               {r2:fsSeries(T)});
          {const e=$('dq_asof'); if(e) e.textContent=`은행대출금 연체율(1일 이상) · ${_dqBank} · 수집 ${d.asof||''}`;}
          const a=S['가계']||[], n=T.length, lv=a[n-1], py=a[n-13];
          const mx=Math.max(...a.filter(v=>v!=null));
          $('dq_main_n').innerHTML=`<b>${_dqBank}</b> 가계대출 연체율 ${fm(T[n-1])} — <b>${lv!=null?lv.toFixed(2)+'%':'—'}</b>`
            +(py!=null&&lv!=null?` · 전년 <b class="${lv-py>0?'dn':'up'}">${lv-py>0?'+':''}${(lv-py).toFixed(2)}p</b>`:'')
            +(isFinite(mx)?` · 2005년 이후 최고 <b>${mx.toFixed(2)}%</b>`:'')
            +` <span class="note">— 1일 이상 연체 기준이라 아래 지역별(1개월 이상)보다 수치가 높다. `
            +`두 지표는 기준이 달라 섞어 읽지 말 것. 카드사 부실이 먼저 튀는 경향이 있어 신용카드 계열을 같이 본다.</span>`
            +_fsNote();
        }
      }
      redraw();
    }).catch(()=>{});
  }

  /* ══════════════════════════════════════════════════════════════════════════
     (2026-08-10) 🏆 많이 거래된 단지 — /api/apt/rank

     기존 카드들은 전부 '지역을 고른 뒤 추세를 본다'는 방향이라
     "이 기간에 뭐가 제일 많이 팔렸나"를 되물을 수가 없었다. 그 역방향 조회.
     원자료가 (단지·면적·월) 집계라 기간은 월 단위까지만 잘린다.
     ══════════════════════════════════════════════════════════════════════════ */
  let _arInit=false, _arKind='apt', _arDeal='sale', _arN='20';
  function initAptRank(){
    if(_arInit) return; _arInit=true;
    const e0=$('ar_ym0'), e1=$('ar_ym1'); if(!e0||!e1) return;
    const ymOf=d=>`${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}`;
    const now=new Date();
    e1.value=ymOf(now); {const p=new Date(now); p.setMonth(p.getMonth()-11); e0.value=ymOf(p);}
    const setSpan=m=>{ const b=new Date(), a=new Date(); a.setMonth(a.getMonth()-(m-1));
      e1.value=ymOf(b); e0.value=ymOf(a); run(); };
    const setYtd=y=>{ e0.value=`${y}-01`;
      e1.value=(y===now.getFullYear())?ymOf(now):`${y}-12`; run(); };
    $('ar_quick').innerHTML=[['최근 3개월',()=>setSpan(3)],['최근 6개월',()=>setSpan(6)],
        ['최근 1년',()=>setSpan(12)],[`${now.getFullYear()}년`,()=>setYtd(now.getFullYear())],
        [`${now.getFullYear()-1}년`,()=>setYtd(now.getFullYear()-1)]]
      .map(([l],i)=>`<button data-q="${i}" style="padding:3px 8px;font-size:11.5px;border:1px solid #d7dce3;border-radius:6px;cursor:pointer;background:#fff">${l}</button>`).join('');
    const QF=[()=>setSpan(3),()=>setSpan(6),()=>setSpan(12),()=>setYtd(now.getFullYear()),()=>setYtd(now.getFullYear()-1)];
    $('ar_quick').querySelectorAll('[data-q]').forEach(b=>b.onclick=()=>QF[+b.dataset.q]());
    const bar=()=>{
      segbar('ar_kind',[['apt','아파트'],['offi','오피스텔·기타']],()=>_arKind,v=>_arKind=v,run);
      segbar('ar_deal',[['sale','매매'],['jeon','전세'],['wol','월세']],()=>_arDeal,v=>_arDeal=v,run);
      segbar('ar_n',[['20','20'],['50','50'],['100','100']],()=>_arN,v=>_arN=v,run);
    };
    const E4=s=>String(s??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
    function run(){
      bar();
      const a=(e0.value||'').replace('-',''), b=(e1.value||'').replace('-','');
      const reg=($('ar_reg').value||'').trim();
      $('ar_n_note').textContent='조회 중…';
      const u=`/api/apt/rank?ym0=${a}&ym1=${b}&kind=${_arKind}&deal=${_arDeal}&n=${_arN}`
              +`&region=${encodeURIComponent(reg)}`;
      fetch(u).then(r=>r.ok?r.json():null).then(d=>{
        if(!d){ $('ar_tbl').innerHTML=''; $('ar_n_note').textContent='조회 실패 — 해당 유형의 DB가 아직 없을 수 있습니다.'; return; }
        const rows=d.rows||[];
        /* (2026-08-10) '부산이 왜 안 나오나' — 단지 DB 는 시군구를 하나씩 훑는 심층 백필이
           채우는 중이라 아직 전국이 아니다. 빈 결과일 때 어디까지 채워졌는지 그대로 보여준다. */
        const av=(d.avail||[]).filter(a=>a.apt>0);
        const avTxt=av.length?av.map(a=>`${E4(a.sido)}(${a.apt.toLocaleString()}단지)`).join(' · '):'없음';
        if(!rows.length){ $('ar_tbl').innerHTML='';
          $('ar_n_note').innerHTML=`<b>결과 없음</b> — 이 기간·지역엔 수집된 거래가 없습니다.<br>`
            +`<span class="note">단지 DB에 <b>지금 채워진 지역</b>: ${avTxt} `
            +`— 단지 단위 DB는 시군구를 하나씩 훑는 심층 백필(매일 01:30)이 채우는 중이라 아직 전국이 아닙니다. `
            +`전국 총량·시도 비교는 위 <b>'아파트 실거래 — 지역 비교'</b> 카드(246개 시군구 전부 수집)를 쓰세요. `
            +`수집 기간 ${d.db_ym0||'—'}~${d.db_ym1||'—'}</span>`; return; }
        const unit=_arDeal==='wol'?'보증금(억)':'평균가(억)';
        const mx=rows[0].cnt||1;
        $('ar_tbl').innerHTML=`<table style="width:100%;border-collapse:collapse;font-size:12.5px">`
          +`<thead><tr style="background:#f7f8fa">`
          +['순위','지역','단지명','준공','거래량',unit].map(h=>`<th style="padding:5px 8px;text-align:left;border-bottom:1px solid #e5e8ec;white-space:nowrap">${h}</th>`).join('')
          +`</tr></thead><tbody>`
          +rows.map((r,i)=>`<tr style="border-bottom:1px solid #f2f4f7">`
            +`<td style="padding:4px 8px;color:#8a93a0">${i+1}</td>`
            +`<td style="padding:4px 8px;white-space:nowrap">${E4(r.sido)} ${E4(r.umd||'')}</td>`
            +`<td style="padding:4px 8px"><b>${E4(r.name)}</b></td>`
            +`<td style="padding:4px 8px;color:#8a93a0">${r.build_year||'—'}</td>`
            +`<td style="padding:4px 8px;white-space:nowrap">`
              +`<span style="display:inline-block;height:9px;width:${Math.max(2,Math.round(70*r.cnt/mx))}px;background:#7c9bd1;border-radius:2px;vertical-align:middle;margin-right:6px"></span>`
              +`<b>${(r.cnt||0).toLocaleString()}</b>건</td>`
            +`<td style="padding:4px 8px">${r.px!=null?r.px.toFixed(r.px>=10?1:2):'—'}</td>`
          +`</tr>`).join('')+`</tbody></table>`;
        const f=s=>s?`${String(s).slice(0,4)}.${String(s).slice(4)}`:'—';
        $('ar_n_note').innerHTML=`<b>${f(d.ym0)} ~ ${f(d.ym1)}</b> · ${E4(d.region)} · `
          +`${_arDeal==='sale'?'매매':_arDeal==='jeon'?'전세':'월세'} 거래건수 상위 ${rows.length}개 단지 `
          +`<span class="note">— 국토부 실거래 신고 기준(RTMS). 기간 경계는 <b>월 단위</b>로만 잘립니다(원자료가 월별 집계). `
          +`최근 2개월은 신고가 진행 중이라 과소 집계됩니다. `
          +`실거래 DB 수집 범위 ${f(d.db_ym0)}~${f(d.db_ym1)} — <b>아직 전국 전체가 아니라 수집된 시군구만</b> 포함됩니다.</span>`;
      }).catch(()=>{ $('ar_n_note').textContent='조회 실패'; });
    }
    $('ar_go').onclick=run;
    $('ar_reg').addEventListener('keydown',e=>{ if(e.key==='Enter') run(); });
    run();
  }

  /* ── (2026-08-12) 🚗 공공데이터 API 예시 — 자동차 통계 4종 (autos.json · scripts/autos.py)
     같은 '자동차' 주제를 4가지 경로로 얻는 데모: ① KOSIS REST ② data.go.kr REST(활용신청)
     ③④ data.go.kr 파일CSV(키 불필요). 상용차 판매 급감 기사(한경 2026-08-10) 검증용. ── */
  let _auDone=false;
  function initAutos(){
    if(_auDone||!$('au_reg')) return; _auDone=true;
    fetch('/api/db/autos').then(r=>r.ok?r.json():null).then(d=>{
      if(!d){ $('au_reg_n').textContent='autos.json 없음 — 서버에서 scripts/autos.py 실행 필요'; return; }
      {const e=$('au_asof'); if(e) e.textContent=`(수집 ${d.asof||''} · 주 1회 자동 갱신 — 같은 주제를 4가지 공공 데이터 경로로 얻는 데모)`;}
      const pct=(y,dec=1)=>y!=null?`<b class="${y>0?'up':'dn'}">${y>0?'+':''}${y.toFixed(dec)}%</b>`:'—';
      /* ① KOSIS 등록대수 — 승용(우축) vs 화물·승합(좌축·만대). 누적이라 완만하지만
         화물이 2022년부터 사실상 멈춘 게 보인다(신규등록 부진 = 기사 내용의 재고 버전). */
      {const R=d.reg||{};
       if(R.t&&R.series){
         const M=a=>(a||[]).map(v=>v==null?null:v/10000);
         line('au_reg',[{t:R.t,v:M(R.series['승용']),label:'승용(만대)',color:'#2f6fed'}],
              {r2:[{t:R.t,v:M(R.series['화물']),label:'화물(만대·좌축)',color:'#d9534f'},
                   {t:R.t,v:M(R.series['승합']),label:'승합',color:'#27ae60'}]});
         const yc=yoy(R.t,R.series['화물']||[]), yp=yoy(R.t,R.series['승용']||[]), yb=yoy(R.t,R.series['승합']||[]);
         $('au_reg_n').innerHTML=`최신 <b>${fm(R.t[R.t.length-1])}</b> · YoY 승용 ${pct(yp)} · 화물 ${pct(yc)} · 승합 ${pct(yb)}`
           +` — 누적 등록대수(재고)라 변화가 완만하지만, <b>화물·승합 증가세가 꺾인 것</b>이 신차 수요 부진의 흔적.`
           +`<br><span class="note">KOSIS 공유서비스: <code>statisticsParameterData.do?orgId=116&tblId=DT_MLTM_5498</code> — 통계표ID·분류코드로 조회하는 정식 REST(JSON). 시도 17개 합=전국.</span>`;
       } else $('au_reg_n').textContent='KOSIS 수집 실패: '+(R.err||'');}
      /* ② 신규등록 — 활용신청 전이면 안내만 */
      {const N=d.newreg||{};
       if(N.t&&N.total){
         line('au_new',[{t:N.t,v:N.total,label:'신규등록(건)',color:'#7c3aed'}]);
         $('au_new_n').innerHTML=`최신 <b>${fm(N.t[N.t.length-1])} = ${(N.total[N.total.length-1]??0).toLocaleString()}건</b> · YoY ${pct(yoy(N.t,N.total))} — 월별 신규등록은 기사의 '판매량'과 가장 가까운 흐름(등록 기준이라 KAMA 출고 기준과 수치는 다름).`;
       } else {
         const cv=$('au_new'); if(cv){ const x=cv.getContext('2d'); const W=cv.clientWidth||700; cv.width=W; cv.height=cv.clientHeight||220;
           x.font='12px sans-serif'; x.fillStyle='#98a2ad'; x.textAlign='center';
           x.fillText('⏳ 아직 데이터 없음 — 아래 안내대로 활용신청하면 자동으로 채워집니다', W/2, 100); }
         $('au_new_n').innerHTML=`<b style="color:#b45309">${N.err||'데이터 없음'}</b><br><span class="note">이 API는 인증키만으론 안 되고 <a href="https://www.data.go.kr/data/15059401/openapi.do" target="_blank">data.go.kr 15059401</a> 페이지에서 <b>활용신청</b>(로그인 필요·자동승인)을 해야 호출된다 — 승인되면 다음 수집 때 자동 표시.</span>`;
       }}
      /* ③ KAMA 내수 vs 수출 — 기사(상용차 28년 최저)의 원본에 가장 가까운 집계 */
      {const K=d.kama||{};
       if(K.t&&K.t.length){
         line('au_kama',[{t:K.t,v:K.domestic,label:'내수판매(국산차)',color:'#2f6fed'},
                         {t:K.t,v:K.export,label:'수출량',color:'#d9534f'}]);
         const yd=yoy(K.t,K.domestic), yx=yoy(K.t,K.export);
         $('au_kama_n').innerHTML=`최신 <b>${fm(K.t[K.t.length-1])}</b> 내수 <b>${(K.domestic[K.domestic.length-1]??0).toLocaleString()}대</b>(YoY ${pct(yd)}) · 수출 <b>${(K.export[K.export.length-1]??0).toLocaleString()}대</b>(YoY ${pct(yx)})`
           +` — 내수(국산차)는 2020년 161만대 정점 이후 추세 하락(2025년 137만대), 수출이 실적을 지탱하는 구조가 그대로 보인다.`
           +`<br><span class="note">파일데이터는 API 아님 — CSV 직다운로드(<code>fileDownload.do?atchFileId=…</code>), 인증키 불필요, 연 1회 갱신(현재 ~2025.12).</span>`;
       } else $('au_kama_n').textContent='CSV 수집 실패';}
      /* ④ 국내 vs 세계 생산량 — 세계(우축) vs 한국(좌축), 백만대 */
      {const W=d.world||{};
       if(W.t&&W.t.length){
         const M=a=>(a||[]).map(v=>v==null?null:v/1000);
         line('au_world',[{t:W.t,v:M(W.world),label:'세계(백만대)',color:'#666'}],
              {r2:[{t:W.t,v:M(W.kr),label:'한국(백만대·좌축)',color:'#2f6fed'}]});
         const k0=W.kr[W.kr.length-1], w0=W.world[W.world.length-1];
         $('au_world_n').innerHTML=`최신 <b>${W.t[W.t.length-1]}년</b> 한국 <b>${(k0/1000).toFixed(2)}백만대</b> · 세계 <b>${(w0/1000).toFixed(1)}백만대</b> (점유율 ${(k0/w0*100).toFixed(1)}%)`
           +` — 한국 생산은 2011년 466만대 정점 이후 410만대 안팎 정체, 세계는 코로나 후 회복.`;
       } else $('au_world_n').textContent='CSV 수집 실패';}
    }).catch(()=>{ $('au_reg_n').textContent='autos 로드 실패'; });
  }

  /* ══════════════════════════════════════════════════════════════════════════
     (2026-08-16) 🏪 사업자 폐업률 — bizclose.json (KOSIS 국세청 · 매일 07:25)

     폐업률 = 폐업 ÷ (가동 + 폐업). '폐업 ÷ 가동'으로 계산하면 같은 해 값이
     1%p 가까이 커진다 — 신문 그래픽마다 숫자가 다른 이유가 대개 이 정의 차이다.
     '소상공인 밀집업종'은 임의로 고른 묶음이므로 어느 업태를 넣었는지 화면에 적는다.
     ══════════════════════════════════════════════════════════════════════════ */
  const BCPAL=['#1f2937','#d9534f','#2f6fed','#e08e3c','#27ae60','#7c3aed','#0e9aa7','#c2185b',
               '#5d4037','#9e9d24','#455a64','#00838f','#3f51b5','#8bc34a','#795548','#ad1457'];
  let _bcInit=false, _bcMode='rate', _bcSel=['전체','소상공인 밀집업종','음식업','소매업'];
  function initBizClose(){
    if(_bcInit) return; _bcInit=true;
    fetch('/api/db/bizclose').then(r=>r.ok?r.json():null).then(d=>{
      if(!d||!(d.t||[]).length){ const e=$('bc_main_n');
        if(e) e.textContent='수집 대기 중 — 다음 수집(매일 07:25)부터 표시됩니다.'; return; }
      const T=d.t, ALL=Object.keys(d.rate||{});
      const IND=['소매업','음식업','서비스업','숙박업','대리·중개·도급업','부동산임대업','도매업',
                 '제조업','건설업','운수·창고·통신업','부동산매매업','농·임·어업','광업','전기·가스·수도업'];
      const SIDO=['서울','인천','경기','강원','대전','충북','충남','세종','광주','전북','전남',
                  '대구','경북','부산','울산','경남','제주'];
      {const e=$('bc_asof'); if(e) e.textContent=`${d.src||''} · 수집 ${d.asof||''}`;}
      const E5=s=>String(s??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
      const PRESET=[
        ['전체 vs 소상공인', ()=>['전체','소상공인 밀집업종']],
        ['업태 전부',       ()=>['전체'].concat(IND)],
        ['자영업 4종',      ()=>['전체','음식업','소매업','숙박업','서비스업']],
        ['시도별',          ()=>['전체'].concat(SIDO)],
      ];
      const bar=()=>{
        segbar('bc_mode',[['rate','폐업률(%)'],['close','폐업자 수(명)'],['new','신규 사업자(명)'],
                          ['active','가동 사업자(명)']],()=>_bcMode,v=>_bcMode=v,redraw);
        $('bc_preset').innerHTML=PRESET.map(([l],i)=>
          `<button data-p="${i}" style="padding:3px 9px;font-size:11.5px;border:1px solid #b45309;color:#b45309;background:#fff;border-radius:6px;cursor:pointer">${l}</button>`).join('');
        $('bc_preset').querySelectorAll('[data-p]').forEach(b=>b.onclick=()=>{
          _bcSel=PRESET[+b.dataset.p][1]().filter(k=>ALL.includes(k)); redraw(); });
        $('bc_chips').innerHTML=_bcSel.map((k,i)=>
          `<span style="display:inline-flex;align-items:center;gap:3px;padding:2px 7px;font-size:12px;border-radius:10px;background:${BCPAL[i%BCPAL.length]}18;border:1px solid ${BCPAL[i%BCPAL.length]};color:#333">`
          +`<b style="color:${BCPAL[i%BCPAL.length]}">●</b>${E5(k)}<b data-rm="${E5(k)}" style="cursor:pointer;color:#888">✕</b></span>`).join('');
        $('bc_chips').querySelectorAll('[data-rm]').forEach(x=>x.onclick=()=>{
          _bcSel=_bcSel.filter(k=>k!==x.dataset.rm); redraw(); });
      };
      const redraw=()=>{ bar(); draw(); };
      function draw(){
        const S=d[_bcMode]||{};
        const arr=_bcSel.map((k,i)=>({t:T, v:(S[k]||[]).slice(), label:k, color:BCPAL[i%BCPAL.length]}))
                        .filter(a=>a.v.some(v=>v!=null));
        line('bc_main', arr);
        const last=a=>{ for(let i=a.length-1;i>=0;i--) if(a[i]!=null) return [a[i],T[i]]; return [null,null]; };
        const [rv,ry]=last(d.rate['전체']||[]), [sv]=last(d.rate['소상공인 밀집업종']||[]);
        const L=d.close_latest||{};
        const unit=_bcMode==='rate'?'%':'명';
        const rows=_bcSel.map(k=>{const [v]=last((d[_bcMode]||{})[k]||[]);
          return v==null?null:`${E5(k)} <b>${_bcMode==='rate'?v+'%':Math.round(v).toLocaleString()+'명'}</b>`;}).filter(Boolean);
        $('bc_main_n').innerHTML=`<b>${ry||''}년</b> — ${rows.join(' · ')}`
          +(rv!=null&&sv!=null?`<br>전체 <b>${rv}%</b> vs 소상공인 밀집업종 <b class="${sv>rv?'up':'dn'}">${sv}%</b>`
             +` — 격차 <b>${(sv-rv).toFixed(2)}%p</b>`:'')
          +`<br><span class="note"><b>폐업률 = 폐업 ÷ (가동 + 폐업)</b>. '폐업 ÷ 가동'으로 계산하면 같은 해 값이 1%p 가까이 커진다 — `
          +`신문·보고서마다 숫자가 다른 건 대개 이 정의 차이다.<br>`
          +`'소상공인 밀집업종'은 <b>${(d.soho||[]).map(E5).join(' · ')}</b> 를 합쳐 다시 폐업률로 환산한 값이다(공식 분류가 아니라 이 화면의 정의).<br>`
          +(L.year&&L.v&&L.v['전체']?`폐업자 수는 <b>${L.year}년 ${L.v['전체'].toLocaleString()}명</b>까지 공표됐지만 `
             +`가동 사업자가 아직 안 나와 폐업률은 ${T[T.length-1]}년까지만 계산된다.<br>`:'')
          +`${E5(d.note||'')}</span>`;
      }
      redraw();
    }).catch(()=>{});
  }

  /* ══════════════════════════════════════════════════════════════════════════
     (2026-08-16) 🧭 부동산 통합차트 — rehub.json (매일 07:45)

     지금까지 카드마다 소스가 달라 "가격이 먼저 꺾였나, 거래량이 먼저 꺾였나" 를
     눈으로 맞춰볼 수가 없었다. 16개 지표를 한 월(月) 축에 올려 아무거나 겹쳐본다.

     축 처리: 단위가 지수·만원/㎡·건·호·%로 제각각이라 **좌/우 두 축에 실제 값**으로
     그린다(지수화하지 않는다 — 눈금이 곧 값이 되게). 지표마다 기본 축이 정해져 있고
     칩의 L/R 배지를 눌러 반대 축으로 옮길 수 있다.
     line() 은 주 계열 눈금을 오른쪽에, opts.r2 눈금을 왼쪽에 그린다 → R=주계열, L=r2.
     ══════════════════════════════════════════════════════════════════════════ */
  const RHPAL=['#1f2937','#d9534f','#2f6fed','#e08e3c','#27ae60','#7c3aed','#0e9aa7','#c2185b',
               '#5d4037','#9e9d24','#455a64','#00838f','#3f51b5','#8bc34a','#795548','#ad1457'];
  /* ── 통합차트 전용 렌더러 (2026-08-16) ────────────────────────────────────
     공용 line() 은 축이 최대 둘(좌·우)이라 자릿수가 다른 계열 셋 이상을 못 담는다.
     여기서는 **선택한 순서대로 오른쪽에 축을 하나씩 쌓고** 각 축을 따로 확대·이동한다.
     왼쪽에는 눈금을 그리지 않는다(요청).
       · 플롯 영역에서 휠/드래그 = X축 확대·이동
       · 축 기둥 위에서 휠/드래그 = 그 계열만 Y 확대·상하 이동
       · 축 기둥 더블클릭 = 그 축 자동 범위로 복귀
     축별 상태는 {lo,hi} 로 들고 있고 null 이면 보이는 구간에서 자동 계산한다. */
  const RH_AXW=62;                                    // 축 기둥 하나의 폭(px)
  function rhDraw(cvId, t, ser, yst){
    const cv=$(cvId); if(!cv) return null;
    const W=cv.clientWidth||900, H=cv.clientHeight||520; cv.width=W; cv.height=H;
    const x=cv.getContext('2d'); x.clearRect(0,0,W,H);
    const N=t.length; if(!N||!ser.length) return null;
    const P={l:10,t:18,b:20}, RW=RH_AXW*ser.length, PW=Math.max(60,W-P.l-RW);
    const X=i=>P.l+PW*i/Math.max(1,N-1);
    const geo={W,H,P,RW,PW,axw:RH_AXW,plotR:P.l+PW};
    x.font='10px sans-serif';
    /* 각 계열의 세로 범위 — 저장된 값이 있으면 그걸 쓰고(사용자가 확대·이동한 상태) */
    const sc=ser.map(s=>{
      const st=yst[s.k];
      if(st&&st.lo!=null&&st.hi!=null&&st.hi>st.lo) return {lo:st.lo,hi:st.hi};
      const f=s.v.filter(v=>v!=null);
      if(!f.length) return {lo:0,hi:1};
      let lo=Math.min(...f), hi=Math.max(...f);
      if(hi===lo){ hi=lo+Math.abs(lo||1)*0.1; lo-=Math.abs(lo||1)*0.1; }
      const pad=(hi-lo)*0.08; return {lo:lo-pad,hi:hi+pad};
    });
    const Y=(i,v)=>P.t+(H-P.t-P.b)*(1-(v-sc[i].lo)/(sc[i].hi-sc[i].lo));
    /* 가로 격자 — 첫 계열 기준 5줄. 여러 축의 격자를 다 그리면 화면이 지저분해진다 */
    x.strokeStyle='#eef1f4';
    for(let g=0;g<=4;g++){ const yy=P.t+(H-P.t-P.b)*g/4;
      x.beginPath(); x.moveTo(P.l,yy); x.lineTo(P.l+PW,yy); x.stroke(); }
    /* X축 연도 */
    x.fillStyle='#98a2ad';
    for(let i=0;i<N;i++){ const s=String(t[i]);
      if(s.slice(4)==='01'&&(N<=140||+s.slice(0,4)%2===0)) x.fillText(s.slice(0,4),X(i)-12,H-5); }
    /* 100 기준선 — CSI·수급동향은 100 이 의미를 가르는 값이라 점선으로 깐다.
       (CSI 100 = 상승·하락 전망이 팽팽, 수급 100 = 사려는 쪽과 팔려는 쪽이 균형) */
    ser.forEach((s,i)=>{ if(s.base==null) return;
      const b=s.base; if(b<sc[i].lo||b>sc[i].hi) return;
      const yy=Y(i,b);
      x.save(); x.setLineDash([5,4]); x.strokeStyle=s.color; x.globalAlpha=.55; x.lineWidth=1.2;
      x.beginPath(); x.moveTo(P.l,yy); x.lineTo(P.l+PW,yy); x.stroke(); x.restore();
      x.fillStyle=s.color; x.globalAlpha=.8;
      x.fillText(String(b), P.l+2, yy-3); x.globalAlpha=1; });
    /* 계열 선 */
    ser.forEach((s,i)=>{ x.strokeStyle=s.color; x.lineWidth=1.7; x.beginPath(); let on=false;
      for(let j=0;j<N;j++){ const v=s.v[j]; if(v==null){ on=false; continue; }
        const px=X(j), py=Y(i,v);
        on?x.lineTo(px,py):(x.moveTo(px,py),on=true); }
      x.stroke(); x.lineWidth=1; });
    /* 오른쪽 축 기둥 — 선택 순서대로 */
    ser.forEach((s,i)=>{
      const x0=P.l+PW+RH_AXW*i;
      x.strokeStyle='#e5e8ec'; x.beginPath(); x.moveTo(x0,P.t-8); x.lineTo(x0,H-P.b); x.stroke();
      x.fillStyle=s.color; x.globalAlpha=.10; x.fillRect(x0,P.t-8,RH_AXW,H-P.t-P.b+8); x.globalAlpha=1;
      const dec=(sc[i].hi-sc[i].lo)<10?2:((sc[i].hi-sc[i].lo)<200?1:0);
      x.fillStyle=s.color;
      for(let g=0;g<=4;g++){ const vv=sc[i].lo+(sc[i].hi-sc[i].lo)*(1-g/4), yy=P.t+(H-P.t-P.b)*g/4;
        const tx=Math.abs(vv)>=10000?Math.round(vv).toLocaleString():vv.toFixed(dec);
        x.fillText(tx,x0+4,yy+3); }
      /* 기둥 머리에 계열 이름(짧게) — 어느 축이 누구 것인지 */
      const nm=s.short||s.label;
      x.save(); x.font='bold 10px sans-serif';
      x.fillText(nm.length>7?nm.slice(0,7):nm, x0+4, P.t-10); x.restore();
      /* 최신값 배지 */
      let li=-1; for(let j=s.v.length-1;j>=0;j--) if(s.v[j]!=null){li=j;break;}
      if(li>=0){ const py=Y(i,s.v[li]);
        x.fillStyle=s.color; x.globalAlpha=.9;
        x.fillRect(x0+1,Math.max(P.t,Math.min(H-P.b-11,py-6)),RH_AXW-3,12); x.globalAlpha=1;
        x.fillStyle='#fff';
        const tv=Math.abs(s.v[li])>=10000?Math.round(s.v[li]).toLocaleString():s.v[li].toFixed(dec);
        x.fillText(tv,x0+4,Math.max(P.t,Math.min(H-P.b-11,py-6))+9); }
    });
    return {geo,sc};
  }
  let _rhInit=false, _rhReg='전국', _rhSel=['rt_idx','trade'], _rhAxis={}, _rhSpan='999', _rhSm='raw', _rhMode={}, _rhY={};
  function initRehub(){
    if(_rhInit) return; _rhInit=true;
    fetch('/api/db/rehub').then(r=>r.ok?r.json():null).then(d=>{
      if(!d||!(d.t||[]).length){ const e=$('rh_main_n');
        if(e) e.textContent='수집 대기 중 — 다음 수집(매일 07:45)부터 표시됩니다.'; return; }
      const T=d.t, M=d.meta||{}, D=d.d||{};
      const E6=s=>String(s??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
      const SIDO=['전국','서울','부산','대구','인천','광주','대전','울산','세종','경기',
                  '강원','충북','충남','전북','전남','경북','경남','제주'];
      const regs=SIDO.filter(r=>Object.keys(M).some(k=>(D[k]||{})[r]));
      if(!regs.includes(_rhReg)) _rhReg=regs[0]||'전국';
      {const e=$('rh_asof'); if(e) e.textContent=`${d.src||''} · 수집 ${d.asof||''}`;}
      /* 지역 구분이 없는 거시 지표는 어느 지역을 골라도 '전국' 계열을 쓴다 */
      const GLOB=['rate_kr','rate_us','csi'];
      const pick=(k,r)=>(D[k]||{})[GLOB.includes(k)?'전국':r];
      const axOf=k=>_rhAxis[k]||(M[k]||{}).axis||'R';
      const MODES=[['val','값'],['idx','지수'],['yoy','전년비']];
      const modeOf=k=>_rhMode[k]||'val';
      const modeLab=k=>({val:'',idx:' 지수(구간시작=100)',yoy:' 전년비%'})[modeOf(k)];
      const modeUnit=k=>({val:(M[k]||{}).unit,idx:'100기준',yoy:'%'})[modeOf(k)];

      const bar=()=>{
        $('rh_reg').innerHTML=regs.map(r=>{const on=r===_rhReg;
          return `<button data-r="${E6(r)}" style="padding:2px 8px;font-size:11px;border:1px solid ${on?'#1f2937':'#d7dce3'};`
            +`border-radius:6px;cursor:pointer;background:${on?'#1f2937':'#fff'};color:${on?'#fff':'#5b6672'}">${E6(r)}</button>`;}).join('');
        $('rh_reg').querySelectorAll('[data-r]').forEach(b=>b.onclick=()=>{_rhReg=b.dataset.r; redraw();});
        $('rh_ind').innerHTML=Object.keys(M).map((k,i)=>{
          const on=_rhSel.includes(k), ok=!!pick(k,_rhReg), c=RHPAL[i%RHPAL.length];
          return `<button data-k="${k}" ${ok?'':'disabled'} title="${E6(M[k].note||'')} (${E6(M[k].src||'')})"`
            +` style="padding:2px 8px;font-size:11px;border:1px solid ${on?c:'#d7dce3'};border-radius:6px;`
            +`cursor:${ok?'pointer':'not-allowed'};background:${on?c:'#fff'};color:${on?'#fff':(ok?'#5b6672':'#c9cfd6')}">`
            +`${E6(M[k].label)}${M[k].cycle!=='M'?`<span style="opacity:.75">·${M[k].cycle==='Q'?'분기':'연'}</span>`:''}</button>`;}).join('');
        $('rh_ind').querySelectorAll('[data-k]').forEach(b=>b.onclick=()=>{
          const k=b.dataset.k;
          _rhSel=_rhSel.includes(k)?_rhSel.filter(z=>z!==k):_rhSel.concat([k]);
          redraw();});
        segbar('rh_span',[['60','5년'],['120','10년'],['240','20년'],['999','전체']],()=>_rhSpan,v=>{_rhSpan=v;_rhN=null;_rhOff=0;},redraw);
        segbar('rh_sm',[['raw','원본'],['ma12','12개월 평균'],['sum12','12개월 누적']],
               ()=>_rhSm,v=>_rhSm=v,redraw);
        /* 칩의 L/R 을 눌러 축을 옮긴다 — 값 차이가 큰 지표를 갈라놓는 유일한 수단 */
        $('rh_chips').innerHTML=_rhSel.map((k,i)=>{const c=RHPAL[Object.keys(M).indexOf(k)%RHPAL.length];
          return `<span style="display:inline-flex;align-items:center;gap:4px;padding:2px 7px;font-size:11.5px;border-radius:10px;background:${c}18;border:1px solid ${c}">`
            +`<b style="color:${c}">●</b>${E6(M[k].label)}<span class="note">${E6(modeUnit(k))}</span>`
            +`<b data-md="${k}" title="표시방식 바꾸기 — 값 → 지수 → 전년비" style="cursor:pointer;color:${c};border:1px solid ${c};border-radius:4px;padding:0 4px">${MODES.find(m=>m[0]===modeOf(k))[1]}</b>`
            +`<b data-rm="${k}" style="cursor:pointer;color:#888">✕</b></span>`;}).join('');
        $('rh_chips').querySelectorAll('[data-md]').forEach(x=>x.onclick=()=>{
          const k=x.dataset.md, i=MODES.findIndex(m=>m[0]===modeOf(k));
          _rhMode[k]=MODES[(i+1)%MODES.length][0]; redraw();});
        $('rh_chips').querySelectorAll('[data-rm]').forEach(x=>x.onclick=()=>{
          _rhSel=_rhSel.filter(z=>z!==x.dataset.rm); redraw();});
      };
      const redraw=()=>{ bar(); draw(); };

      /* (2026-08-16) 휠 확대/축소 · 드래그 좌우 이동 — 259개월을 한 화면에 다 그리면
         최근 구간이 뭉쳐 안 보인다. 지역비교 카드(re_rt_big)와 같은 조작 규칙을 쓴다.
         _rhN=null 이면 '기간' 버튼이 정한 구간 전체를 본다. */
      let _rhN=null, _rhOff=0, _rhLen=0, _rhGeo=null, _rhSer=[], _rhAuto=[];
      {const cv=$('rh_main');
       if(cv&&!cv._rhBound){ cv._rhBound=1;
         /* 커서가 어느 축 기둥 위인지 — 아니면 -1(플롯 영역) */
         const hit=e=>{ const g=_rhGeo; if(!g) return -1;
           const r=cv.getBoundingClientRect(), px=(e.clientX-r.left)*(cv.width/r.width);
           if(px<g.plotR) return -1;
           const i=Math.floor((px-g.plotR)/g.axw);
           return (i>=0&&i<_rhSer.length)?i:-1; };
         cv.addEventListener('wheel',e=>{ e.preventDefault();
           const ai=hit(e);
           if(ai>=0){                              // ── 그 계열의 Y 축만 확대/축소
             const k=_rhSer[ai].k, cur=_rhY[k]||_rhAuto[ai]; if(!cur) return;
             const r=cv.getBoundingClientRect(), g=_rhGeo;
             const fy=Math.max(0,Math.min(1,((e.clientY-r.top)*(cv.height/r.height)-g.P.t)/(g.H-g.P.t-g.P.b)));
             /* (2026-08-16 수정) lo/hi 배분이 뒤집혀 있어 커서가 가리키던 값이 매번 밀려났다
                (실측: 127.0 에서 굴리면 127→136→144 로 도망감 → 한쪽으로만 확대되는 느낌).
                화면 위에서 fy 만큼 내려온 지점의 값 = hi - span*fy 이므로
                hi = anchor + span*fy, lo = anchor - span*(1-fy) 이어야 한다. */
             const anchor=cur.hi-(cur.hi-cur.lo)*fy;         // 커서가 가리키는 값
             const f=e.deltaY<0?0.8:1.25, span=(cur.hi-cur.lo)*f;   // 위로=확대, 아래로=축소
             _rhY[k]={lo:anchor-span*(1-fy), hi:anchor+span*fy};
             draw(); return; }
           const L=_rhLen||T.length;               // ── X축 확대/축소
           const r=cv.getBoundingClientRect(), fr=Math.max(0,Math.min(1,(e.clientX-r.left)/r.width));
           const n0=_rhN?Math.min(_rhN,L):L, st=Math.max(0,L-n0-_rhOff), anchor=st+fr*(n0-1);
           const n1=Math.max(12,Math.min(L,Math.round(n0*(e.deltaY<0?0.8:1.25))));
           let s1=Math.round(anchor-fr*(n1-1)); s1=Math.max(0,Math.min(L-n1,s1));
           _rhN=n1; _rhOff=L-s1-n1; draw(); },{passive:false});
         let dr=null;
         cv.addEventListener('mousedown',e=>{ const ai=hit(e);
           if(ai>=0){ const k=_rhSer[ai].k, cur=_rhY[k]||_rhAuto[ai];
             dr={ax:ai,k,y:e.clientY,lo:cur.lo,hi:cur.hi}; }
           else dr={x:e.clientX,o:_rhOff}; });
         cv.addEventListener('mousemove',e=>{ if(!dr) return;
           if(dr.ax!=null){                        // ── 축 상하 이동
             const g=_rhGeo; if(!g) return;
             const r=cv.getBoundingClientRect();
             const dy=(e.clientY-dr.y)*(cv.height/r.height);
             const per=(dr.hi-dr.lo)/(g.H-g.P.t-g.P.b);
             _rhY[dr.k]={lo:dr.lo+dy*per, hi:dr.hi+dy*per}; draw(); return; }
           const L=_rhLen||T.length, n0=_rhN?Math.min(_rhN,L):L;
           const bw=(cv.clientWidth||900)/Math.max(1,n0);
           _rhOff=Math.max(0,Math.min(L-n0,dr.o+Math.round((e.clientX-dr.x)/bw))); draw(); });
         cv.addEventListener('mouseup',()=>{dr=null;});
         cv.addEventListener('mouseleave',()=>{dr=null;});
         cv.addEventListener('dblclick',e=>{ const ai=hit(e);
           if(ai>=0){ delete _rhY[_rhSer[ai].k]; draw(); }      // 그 축만 자동 범위로
           else { _rhN=null; _rhOff=0; _rhY={}; draw(); } });
         cv.style.cursor='crosshair';
       }}
      function draw(){
        const want=(_rhSpan==='999')?T.length:+_rhSpan;
        const base=Math.max(0,T.length-Math.min(want,T.length));
        const full=T.slice(base);
        _rhLen=full.length;
        const n=_rhN?Math.max(12,Math.min(_rhN,_rhLen)):_rhLen;
        const off=Math.max(0,Math.min(_rhOff,_rhLen-n));
        const st=base+Math.max(0,_rhLen-n-off);
        const t=T.slice(st,st+n);
        /* (2026-08-16) 12개월 평균·누적 — 거래량·인허가 같은 유량(flow) 지표는 계절성이 커서
           원본으로 보면 톱니만 보인다(1월 급감·3월 급증). 창을 12개월로 잡으면 계절성이 상쇄된다.
           누적(합계)은 유량 지표에만 뜻이 있다 — 지수·가격·%는 더해도 의미가 없으므로
           그 경우엔 평균으로 대신 계산하고 각주에 그 사실을 적는다.
           창이 채워지기 전(앞 11개월)은 값을 만들지 않고 null 로 둔다. */
        /* (2026-08-16) 계열별 표시방식 — 축이 둘뿐이라 값의 자릿수가 3종류를 넘으면
           어느 축에 놔도 하나는 바닥에 눌린다(실측: 평균가 1,707 만원/㎡ 가 거래건수 26,886
           옆에서 직선이 됐다). 그래서 계열마다 표현을 바꿀 수 있게 한다.
             값   원자료 그대로
             지수 보이는 구간의 첫 값 = 100 (확대하면 그 구간 기준으로 다시 잡힌다)
             전년비 12개월 전 대비 %  — 수준이 아니라 '얼마나 빨리 변하나'를 본다
           가격처럼 수준 차이가 큰 계열은 지수·전년비로 두면 지수·CSI 와 같은 축에서 읽힌다. */
        const FLOW=u=>u==='건'||u==='호';
        const roll=(a,k)=>{
          if(_rhSm==='raw') return a;
          const sum=(_rhSm==='sum12')&&FLOW((M[k]||{}).unit);
          const out=new Array(a.length).fill(null);
          for(let i=11;i<a.length;i++){
            let s=0,c=0;
            for(let j=i-11;j<=i;j++) if(a[j]!=null){ s+=a[j]; c++; }
            if(c===12) out[i]=sum?s:s/12;              // 한 달이라도 비면 계산하지 않는다
          }
          return out;
        };
        const mk=k=>{const a0=pick(k,_rhReg); if(!a0) return null;
          let a=roll(a0,k);
          if(modeOf(k)==='yoy'){                    // 12개월 전 대비 — 자르기 전 전체에서 계산
            const y=new Array(a.length).fill(null);
            for(let i=12;i<a.length;i++) if(a[i]!=null&&a[i-12]!=null&&a[i-12]!==0)
              y[i]=(a[i]/a[i-12]-1)*100;
            a=y;
          }
          let v=a.slice(st,st+n);
          if(modeOf(k)==='idx'){                    // 보이는 구간 첫 값 = 100
            const b=v.find(x=>x!=null);
            v=(b==null||b===0)?v:v.map(x=>x==null?null:x/b*100);
          }
          return v.some(x=>x!=null)?v:null;};
        /* (2026-08-16) 축을 선택 순서대로 오른쪽에 하나씩 쌓는다 — 좌축은 쓰지 않는다.
           계열마다 자릿수가 달라도 각자 축을 온전히 쓰므로 눌리는 계열이 없다. */
        const ser=[];
        _rhSel.forEach(k=>{ const v=mk(k); if(!v) return;
          const c=RHPAL[Object.keys(M).indexOf(k)%RHPAL.length];
          const sfx=_rhSm==='raw'?'':(_rhSm==='sum12'&&(M[k].unit==='건'||M[k].unit==='호')?' 12M누적':' 12M평균');
          /* 100 기준선을 그릴 지표 — 원값일 때만(지수·전년비로 바꾸면 100 의 뜻이 달라진다) */
          const base=(modeOf(k)==='val'&&(k==='csi'||k==='supply'))?100:null;
          ser.push({k, t, v, color:c, short:M[k].label, base,
                    label:M[k].label+sfx+modeLab(k)});});
        _rhSer=ser;
        const R=rhDraw('rh_main', t, ser, _rhY);
        _rhGeo=R?R.geo:null; _rhAuto=R?R.sc:[];
        const last=k=>{const a=roll(pick(k,_rhReg)||[],k); for(let i=a.length-1;i>=0;i--) if(a[i]!=null) return [T[i],a[i]]; return null;};
        const rows=_rhSel.map(k=>{const L=last(k); if(!L) return null;
          const v=Math.abs(L[1])>=1000?Math.round(L[1]).toLocaleString():L[1].toFixed(2);
          return `${E6(M[k].label)} <b>${v}</b>${E6(M[k].unit==='건'||M[k].unit==='호'?M[k].unit:'')} <span class="note">(${fm(L[0])})</span>`;}).filter(Boolean);
        const cyc=_rhSel.filter(k=>M[k].cycle!=='M');
        $('rh_main_n').innerHTML=(_rhSel.length?`<b>${E6(_rhReg)}</b> · ${rows.join(' · ')}`:'지표를 하나 이상 고르세요.')
          +`<br><span class="note">축이 둘이다 — <b>오른쪽 눈금</b>은 우축 지표, <b>왼쪽 눈금</b>은 좌축 지표. 칩의 좌/우 배지를 누르면 축을 옮긴다. `
          +`지수화하지 않고 실제 값 그대로라 눈금이 곧 값이다.`
          +(cyc.length?`<br>${cyc.map(k=>E6(M[k].label)).join(' · ')} 는 ${cyc.some(k=>M[k].cycle==='Q')?'분기':'연간'} 지표라 해당 기간 각 달에 같은 값이 들어가 <b>계단 모양</b>이 된다.`:'')
          +(_rhSel.some(k=>GLOB.includes(k))?`<br>금리·전망CSI 는 지역 구분이 없는 전국 값이라 어느 지역을 골라도 같은 선이 깔린다.`:'')
          +(_rhSm!=='raw'?`<br>📐 <b>${_rhSm==='sum12'?'12개월 누적':'12개월 이동평균'}</b> — 거래량·인허가처럼 계절성이 큰 지표(1월 급감·3월 급증)의 톱니를 걷어낸다. `
            +`창이 채워지기 전 앞 11개월은 값을 만들지 않고 비운다.`
            +(_rhSm==='sum12'&&_rhSel.some(k=>M[k].unit!=='건'&&M[k].unit!=='호')?` 지수·가격·%는 <b>더해도 뜻이 없어 평균으로 계산</b>했다(라벨에 12M평균으로 표시).`:'')
            :'')
          +(_rhSel.some(k=>modeOf(k)!=='val')?`<br>🔁 칩의 <b>값/지수/전년비</b> 배지로 표현을 바꿨다 — <b>지수</b>는 보이는 구간의 첫 값을 100으로 잡아 확대하면 다시 계산되고, <b>전년비</b>는 12개월 전 대비 %다. 자릿수가 크게 다른 계열(가격 vs 건수)을 같은 축에서 읽으려면 이쪽이 낫다.`:'')
          +`<br>🖱 <b>휠 = 확대/축소 · 드래그 = 좌우 이동</b> · '기간' 버튼을 누르면 확대가 풀린다.`
          +`<br>표시 구간 ${fm(t[0])}~${fm(t[t.length-1])} (${t.length}/${_rhLen}개월) · ${E6(d.note||'')}</span>`;
      }
      redraw();
    }).catch(()=>{});
  }

  /* ══════════════════════════════════════════════════════════════════════
     (2026-08-21) 🔮 선행지표·가격 예측 차트 — relead.json (매일 07:55)

     통합차트가 "지나온 길"이라면 이건 "앞길"이다. 세 가지를 한 화면에 둔다.
       ① 기준선: 아파트 매매 실거래 중위가격(3개월 평균) — 예측 대상
       ② 선행지표: 복수 선택. '시차' 버튼을 켜면 각 지표를 자기 선행 개월수만큼
          오른쪽으로 밀어 그린다 → 가격과 겹쳐지는 모양이 눈으로 확인된다.
       ③ 예측: 마지막 관측 뒤로 12개월. 점선 + 80% 밴드.
     예측을 곧이곧대로 믿지 않도록 백테스트 성적(과거 재현 오차·방향 적중률)을
     차트 아래 표로 항상 같이 보여준다. 성적이 나쁘면 나쁜 대로 보인다.
     ══════════════════════════════════════════════════════════════════════ */
  let _rlInit=false, _rlReg='서울', _rlSel=[], _rlSpan='120', _rlShift=true, _rlPred=true, _rlD=null;
  /* (2026-08-22) 시군구 확장 — 서울 25개 구 + 경기 주요시(거래량 기준 45곳).
     releadg.json 은 새벽 크론이 만든다(70지역 × 24지평이라 40분쯤 걸려 분리).
     기준계열이 시도(만원/㎡)와 달리 '자체 RTMS 실거래 중위가(억원)' 라 단위가 다르다. */
  let _rlGu='', _rlG=null;

  function rlDraw(t, hist, fut, ser, past){
    const cv=$('rl_main'); if(!cv) return;
    const W=cv.clientWidth||900, H=cv.clientHeight||520; cv.width=W; cv.height=H;
    const x=cv.getContext('2d'); x.clearRect(0,0,W,H);
    const N=t.length; if(!N) return;
    const P={l:10,t:18,b:20}, RW=RH_AXW*(ser.length+1), PW=Math.max(60,W-P.l-RW);
    const X=i=>P.l+PW*i/Math.max(1,N-1);
    x.font='10px sans-serif';
    /* 세로 범위 — 기준선은 예측·밴드까지 포함해 잡는다 */
    const rng=v=>{const f=v.filter(z=>z!=null); if(!f.length) return {lo:0,hi:1};
      let lo=Math.min(...f), hi=Math.max(...f);
      if(hi===lo){hi=lo+Math.abs(lo||1)*.1; lo-=Math.abs(lo||1)*.1;}
      const pad=(hi-lo)*.08; return {lo:lo-pad,hi:hi+pad};};
    const all=[...hist, ...fut.price, ...fut.lo, ...fut.hi];
    const sc=[rng(all), ...ser.map(s=>rng(s.v))];
    const Y=(i,v)=>P.t+(H-P.t-P.b)*(1-(v-sc[i].lo)/(sc[i].hi-sc[i].lo));
    /* 격자 + 연도 */
    x.strokeStyle='#eef1f4';
    for(let g=0;g<=4;g++){const yy=P.t+(H-P.t-P.b)*g/4; x.beginPath(); x.moveTo(P.l,yy); x.lineTo(P.l+PW,yy); x.stroke();}
    x.fillStyle='#98a2ad';
    for(let i=0;i<N;i++){const v=String(t[i]);
      if(v.slice(4)==='01'&&(N<=140||+v.slice(0,4)%2===0)) x.fillText(v.slice(0,4),X(i)-12,H-5);}
    /* 예측 시작 경계 */
    if(past<N-1){
      x.save(); x.setLineDash([4,4]); x.strokeStyle='#c8ced6';
      x.beginPath(); x.moveTo(X(past),P.t-8); x.lineTo(X(past),H-P.b); x.stroke(); x.restore();
      x.fillStyle='#98a2ad'; x.fillText('예측 →', X(past)+3, P.t-1);
      /* 80% 밴드 */
      x.beginPath(); let started=false;
      for(let j=past;j<N;j++){const v=fut.hi[j]; if(v==null) continue;
        started?x.lineTo(X(j),Y(0,v)):(x.moveTo(X(j),Y(0,v)),started=true);}
      for(let j=N-1;j>=past;j--){const v=fut.lo[j]; if(v==null) continue; x.lineTo(X(j),Y(0,v));}
      x.closePath(); x.fillStyle='rgba(31,41,55,.10)'; x.fill();
    }
    /* 선행지표 */
    ser.forEach((s,i)=>{x.strokeStyle=s.color; x.lineWidth=1.5; x.beginPath(); let on=false;
      for(let j=0;j<N;j++){const v=s.v[j]; if(v==null){on=false;continue;}
        const px=X(j),py=Y(i+1,v); on?x.lineTo(px,py):(x.moveTo(px,py),on=true);}
      x.stroke(); x.lineWidth=1;});
    /* 기준선(실측) */
    x.strokeStyle='#1f2937'; x.lineWidth=2.1; x.beginPath(); let on=false;
    for(let j=0;j<N;j++){const v=hist[j]; if(v==null){on=false;continue;}
      const px=X(j),py=Y(0,v); on?x.lineTo(px,py):(x.moveTo(px,py),on=true);}
    x.stroke();
    /* 예측선(점선) */
    x.save(); x.setLineDash([6,4]); x.strokeStyle='#d9534f'; x.lineWidth=2.1; x.beginPath(); on=false;
    for(let j=0;j<N;j++){const v=fut.price[j]; if(v==null){on=false;continue;}
      const px=X(j),py=Y(0,v); on?x.lineTo(px,py):(x.moveTo(px,py),on=true);}
    x.stroke(); x.restore(); x.lineWidth=1;
    /* 오른쪽 축 기둥 — 0번은 기준선(가격) */
    const cols=['#1f2937', ...ser.map(s=>s.color)];
    const names=['중위가격', ...ser.map(s=>s.short||s.label)];
    for(let i=0;i<sc.length;i++){
      const x0=P.l+PW+RH_AXW*i;
      x.strokeStyle='#e5e8ec'; x.beginPath(); x.moveTo(x0,P.t-8); x.lineTo(x0,H-P.b); x.stroke();
      x.fillStyle=cols[i]; x.globalAlpha=.10; x.fillRect(x0,P.t-8,RH_AXW,H-P.t-P.b+8); x.globalAlpha=1;
      const dec=(sc[i].hi-sc[i].lo)<10?2:((sc[i].hi-sc[i].lo)<200?1:0);
      x.fillStyle=cols[i];
      for(let g=0;g<=4;g++){const vv=sc[i].lo+(sc[i].hi-sc[i].lo)*(1-g/4), yy=P.t+(H-P.t-P.b)*g/4;
        x.fillText(Math.abs(vv)>=10000?Math.round(vv).toLocaleString():vv.toFixed(dec), x0+4, yy+3);}
      x.save(); x.font='bold 10px sans-serif';
      x.fillText(names[i].length>7?names[i].slice(0,7):names[i], x0+4, P.t-10); x.restore();
    }
  }

  function initRelead(){
    if(_rlInit) return; _rlInit=true;
    fetch('/api/db/relead').then(r=>r.ok?r.json():null).then(d=>{
      const n=$('rl_main_n');
      if(!d||!(d.t||[]).length){ if(n) n.textContent='수집 대기 중 — 다음 수집(매일 07:55)부터 표시됩니다.'; return; }
      _rlD=d;
      const E6=s=>String(s??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
      const M=d.meta||{}, regs=d.regions||[];
      if(!regs.includes(_rlReg)) _rlReg=regs[0];
      {const e=$('rl_asof'); if(e) e.textContent=`${d.src||''} · 수집 ${d.asof||''}`;}
      const btn=(on,txt,attr)=>`<button ${attr} style="padding:2px 8px;font-size:11px;border:1px solid ${on?'#1f2937':'#d7dce3'};`
        +`border-radius:6px;cursor:pointer;background:${on?'#1f2937':'#fff'};color:${on?'#fff':'#5b6672'}">${txt}</button>`;
      const LEAD=()=>((_rlGu&&_rlG?_rlG.lead[_rlGu]:d.lead[_rlReg])||{});
      const lagOf=k=>(LEAD()[k]||{}).lag||0;
      const corrOf=k=>(LEAD()[k]||{}).corr;
      const MM=k=>M[k]||(_rlG&&_rlG.meta&&_rlG.meta[k])||{label:k,unit:'',cycle:'M'};
      fetch('/api/db/releadg').then(r=>r.ok?r.json():null).then(g=>{ if(g&&g.pred){_rlG=g; draw();} }).catch(()=>{});
      const fm=t=>`${String(t).slice(0,4)}.${String(t).slice(4)}`;

      function bar(){
        /* 지역 */
        $('rl_reg').innerHTML=regs.map(r=>btn(r===_rlReg,E6(r),`data-r="${E6(r)}"`)).join('');
        $('rl_reg').querySelectorAll('[data-r]').forEach(b=>b.onclick=()=>{_rlReg=b.dataset.r; _rlGu=''; _rlSel=defSel(); draw();});
        /* 시군구 셀렉트 — 서울·경기에서만, releadg 도착 후 */
        {const gw=$('rl_gu');
         if(gw){ if(_rlG&&(_rlReg==='서울'||_rlReg==='경기')){
           const opts=Object.entries(_rlG.names||{}).filter(([c,n])=>(_rlG.pred[c]||{}).sido===_rlReg)
             .sort((a,b)=>a[1].localeCompare(b[1]));
           gw.innerHTML=`<select id="rl_gu_sel" style="font-size:11px;padding:2px 4px;border:1px solid #d7dce3;border-radius:6px">`
             +`<option value="">(${E6(_rlReg)} 전체)</option>`
             +opts.map(([c,n])=>`<option value="${c}"${c===_rlGu?' selected':''}>${E6(n)}</option>`).join('')+`</select>`;
           gw.querySelector('select').onchange=e=>{_rlGu=e.target.value; _rlSel=defSel(); draw();};
         } else gw.innerHTML='';}}
        /* 선행지표 — 그 지역에서 상관이 큰 순서로 나열하고 시차를 배지로 붙인다 */
        const ks=Object.keys(LEAD());
        //   순서 = |상관계수| 내림차순(= 그 지역 가격을 가장 잘 따라온 순). 번호와 r 값을 같이 보여준다.
        $('rl_ind').innerHTML=ks.map((k,i)=>{const on=_rlSel.includes(k), L=lagOf(k), r=corrOf(k);
          const rank=i<3?['①','②','③'][i]:`${i+1}.`;
          return btn(on,`${rank} ${E6(MM(k).label)}<span style="opacity:.75">·${L}개월·r=${(r>0?'+':'')}${r}</span>`,`data-k="${k}"`);}).join('');
        $('rl_ind').querySelectorAll('[data-k]').forEach(b=>b.onclick=()=>{
          const k=b.dataset.k, i=_rlSel.indexOf(k);
          // (2026-08-21) 상한 4 → 8. 지표마다 오른쪽에 축 기둥(62px)이 하나씩 붙어
          //   너무 많으면 그림 영역이 줄어든다. 8개면 축이 ~560px — 넓은 화면 기준 한계선.
          if(i>=0) _rlSel.splice(i,1); else { if(_rlSel.length>=8){alert('선행지표는 최대 8개까지 겹쳐볼 수 있습니다.');return;} _rlSel.push(k); }
          draw();});
        /* 기간·시차·예측 */
        $('rl_span').innerHTML=[['60','5년'],['120','10년'],['240','20년'],['999','전체']]
          .map(([v,t])=>btn(_rlSpan===v,t,`data-s="${v}"`)).join('');
        $('rl_span').querySelectorAll('[data-s]').forEach(b=>b.onclick=()=>{_rlSpan=b.dataset.s; draw();});
        $('rl_shift').innerHTML=btn(_rlShift,_rlShift?'적용':'해제','data-sh="1"');
        $('rl_shift').querySelector('[data-sh]').onclick=()=>{_rlShift=!_rlShift; draw();};
        $('rl_pred').innerHTML=btn(_rlPred,_rlPred?'표시':'숨김','data-p="1"');
        $('rl_pred').querySelector('[data-p]').onclick=()=>{_rlPred=!_rlPred; draw();};
        $('rl_chips').innerHTML=_rlSel.map((k,i)=>{const c=RHPAL[(i+1)%RHPAL.length];
          return `<span style="display:inline-flex;align-items:center;gap:4px;font-size:11px;border:1px solid ${c};`
            +`border-radius:6px;padding:1px 6px;color:${c}">${E6(MM(k).label)} <b>${lagOf(k)}개월</b> r=${corrOf(k)}</span>`;}).join('');
      }
      function defSel(){ return Object.keys(LEAD()).slice(0,2); }

      function draw(){
        bar();
        /* 시군구가 선택돼 있으면 releadg(자체 RTMS 실거래·억원) 를 쓴다 */
        const GU=_rlGu&&_rlG&&_rlG.pred[_rlGu]?_rlGu:'';
        const P= GU? _rlG.pred[GU] : (d.pred[_rlReg]||{});
        const price= GU? ((_rlG.price[GU]||{}).ma||[]) : ((d.price[_rlReg]||{}).ma||[]);
        const T0=d.t, ft=(_rlPred?(P.t||[]):[]);
        const t=[...T0, ...ft];
        /* 표시 구간 자르기 */
        const lim=_rlSpan==='999'?t.length:Math.min(t.length, +_rlSpan+ft.length);
        const s0=t.length-lim;
        const cut=a=>a.slice(s0);
        const hist=cut([...price, ...ft.map(()=>null)]);
        const fut={price:cut([...T0.map(()=>null), ...(P.price||[])]),
                   lo:cut([...T0.map(()=>null), ...(P.lo||[])]),
                   hi:cut([...T0.map(()=>null), ...(P.hi||[])])};
        /* 예측선을 마지막 실측점과 이어 붙인다(끊겨 보이지 않게) */
        const lastI=T0.length-1-s0;
        if(_rlPred&&lastI>=0&&price.length) {fut.price[lastI]=price[T0.length-1];
          fut.lo[lastI]=price[T0.length-1]; fut.hi[lastI]=price[T0.length-1];}
        const ser=_rlSel.map((k,i)=>{
          const sidoOf= GU? P.sido : _rlReg;
          const src= (GU&&((_rlG.d[GU]||{})[k]))
            || (GU&&k==='sido_p'? ((d.price[P.sido]||{}).ma||[]) : null)
            || (d.d[k]||{})[GLOBRL.includes(k)?'전국':sidoOf]||(d.d[k]||{})['전국']||[];
          let v=[...src, ...ft.map(()=>null)];
          if(_rlShift){const L=lagOf(k); v=[...Array(L).fill(null), ...v.slice(0,v.length-L)];}
          return {k, label:M[k].label, short:M[k].label, color:RHPAL[(i+1)%RHPAL.length], v:cut(v)};
        });
        rlDraw(cut(t), hist, fut, ser, T0.length-1-s0);

        /* ── (2026-08-23) 우측 지표 영향 패널 — 사용자 요청:
           "영향성 있는 지표명·r 리스트업, 유사 지표는 그룹화해 개별r + 통합r, r별 가중치".
           · 개별 r  : 그 지표의 최적 시차 상관(모델 산출값 그대로)
           · 통합 r  : 같은 그룹 지표들을 각자 시차로 민 뒤 표준화 평균한 '합성 계열' 과
                       가격 전년비의 상관 — 그룹이 한 몸처럼 움직일 때의 설명력
           · 가중치  : 릿지가 학습한 |β| 를 전체 합으로 나눈 비중(%) — 예측을 실제로 움직인 몫 */
        (function(){
          const el=$('rl_side'); if(!el) return;
          const U=(P.used||[]).filter(u=>u.beta!=null);
          if(!U.length){ el.innerHTML='<div class="note">모델 상세는 다음 재계산부터 표시됩니다.</div>'; return; }
          const LVL=['rate_kr','rate_us','mtg_rate','csi','supply','cli','khai','khoi','jr','supply_j',
                     'gap_am','bid_apt_rate','bid_apt_sldrate','bid_all_rate','gap_g'];
          /* 합성 r 계산 도구 */
          const yoy=a=>a.map((v,i)=> (i>=12&&v!=null&&a[i-12]!=null&&v>0&&a[i-12]>0)?Math.log(v/a[i-12]):null);
          const pear=(a,b)=>{const p=[];for(let i=0;i<Math.min(a.length,b.length);i++)if(a[i]!=null&&b[i]!=null)p.push([a[i],b[i]]);
            const n=p.length; if(n<48) return [null,n];
            const mx=p.reduce((s,x)=>s+x[0],0)/n, my=p.reduce((s,x)=>s+x[1],0)/n;
            let xy=0,xx=0,yy=0; p.forEach(([x,y])=>{xy+=(x-mx)*(y-my);xx+=(x-mx)**2;yy+=(y-my)**2;});
            return [(xx>0&&yy>0)?xy/Math.sqrt(xx*yy):null,n];};
          const priceMa=GU?((_rlG.price[GU]||{}).ma||[]):((d.price[_rlReg]||{}).ma||[]);
          const ytr=yoy(priceMa);
          const sidoOf=GU?P.sido:_rlReg;
          const rawOf=k=>{
            if(GU&&(_rlG.d[GU]||{})[k]) return _rlG.d[GU][k];
            if(GU&&k==='sido_p') return (d.price[P.sido]||{}).ma||[];
            return (d.d[k]||{})[GLOBRL.includes(k)?'전국':sidoOf]||(d.d[k]||{})['전국']||[];};
          const tf=(k,a)=>LVL.includes(k)?a.slice():yoy(a);
          const shift=(a,L)=>L?Array(L).fill(null).concat(a.slice(0,a.length-L)):a.slice();
          const z=a=>{const v=a.filter(x=>x!=null); if(v.length<24) return null;
            const mu=v.reduce((s,x)=>s+x,0)/v.length;
            const sd=Math.sqrt(v.reduce((s,x)=>s+(x-mu)**2,0)/v.length)||1;
            return a.map(x=>x!=null?(x-mu)/sd:null);};
          /* 그룹핑 */
          const G={}; U.forEach(u=>{(G[u.group]=G[u.group]||[]).push(u);});
          const sumAbsAll=U.reduce((s,u)=>s+Math.abs(u.beta),0)||1;
          const rows=Object.entries(G).map(([g,ms])=>{
            const sb=ms.reduce((s,u)=>s+Math.abs(u.beta),0);
            let gr=null, gn=0;
            if(ms.length===1){ gr=ms[0].corr; }
            else{
              const zs=ms.map(u=>{const a=rawOf(u.key); if(!a.length) return null;
                return z(shift(tf(u.key,a),u.lag||0));}).filter(Boolean);
              if(zs.length){
                const comp=ytr.map((_,i)=>{let s2=0,c=0; zs.forEach(zz=>{if(zz[i]!=null){s2+=zz[i];c++;}});
                  return c?s2/c:null;});
                const [r,n]=pear(comp,ytr); gr=r; gn=n;
              }
            }
            return {g,ms:ms.sort((a,b)=>Math.abs(b.beta)-Math.abs(a.beta)),sb,gr,gn};
          }).sort((a,b)=>b.sb-a.sb);
          const fmt=v=>v==null?'—':(v>0?'+':'')+v.toFixed(3);
          let html=`<div style="font-size:12px;font-weight:700;margin-bottom:4px">🧭 이번 예측의 지표 영향 <span class="note">(12개월 예측 기준 · 가중치=발언권 지분)</span></div>`
            +`<div style="font-size:11px;background:#f8f9fb;border:1px solid #e5e8ec;border-radius:4px;padding:5px 7px;margin-bottom:5px;line-height:1.65;color:#444">`
            +`<b>β(회귀계수)</b> = 회의에서 실제로 배정된 발언. 36개 지표를 표준화해 한 회귀에 넣고, 과거 20년을 매월 되돌아가 `
            +`"그때까지 자료만으로 12개월 뒤를 맞히는" 시험에서 <b>오차가 가장 작아지는 계수 조합</b>을 푼 결과다. `
            +`비슷한 지표끼리 발언을 부풀리지 못하게 벌점(릿지)을 주며, 벌점 강도(λ)도 사람이 아니라 백테스트 성적으로 자동 선택된다. `
            +`부호 = 이번 예측을 민 방향(<b style="color:#d9534f">+ 상승</b> / <b style="color:#2f6fed">− 하락</b>) — `
            +`동료가 이미 말한 중복분을 빼고 남는 몫이라, 혼자 볼 때의 r 과 부호가 다를 수 있다. `
            +`<b>가중치</b> = |β| ÷ Σ|β| — 발언 지분(%). `
            +`단 β 크기는 재학습 시점마다 다소 출렁이므로(부호·순위는 안정, 실측 2026-08-23) `
            +`가중치 %는 소수점보다 <b>순위와 상·하위 구분</b>으로 읽는 것이 안전하다.</div>`
            +`<table style="border-collapse:collapse;font-size:11px;width:100%">`
            +`<tr style="background:#f6f7f9"><th style="border:1px solid #e5e8ec;padding:2px 5px;text-align:left">그룹 / 지표</th>`
            +`<th style="border:1px solid #e5e8ec;padding:2px 5px">시차</th>`
            +`<th style="border:1px solid #e5e8ec;padding:2px 5px">r</th>`
            +`<th style="border:1px solid #e5e8ec;padding:2px 5px">β</th>`
            +`<th style="border:1px solid #e5e8ec;padding:2px 5px">가중치</th></tr>`;
          rows.forEach(({g,ms,sb,gr})=>{
            const gw=100*sb/sumAbsAll;
            html+=`<tr style="background:#eef1f6"><td style="border:1px solid #e5e8ec;padding:2px 5px;font-weight:700">${E6(g)} <span class="note">×${ms.length}</span></td>`
              +`<td style="border:1px solid #e5e8ec"></td>`
              +`<td style="border:1px solid #e5e8ec;padding:2px 5px;text-align:right;font-weight:700">${ms.length>1?fmt(gr):fmt(gr)}</td>`
              +(()=>{const nb=ms.reduce((s,u)=>s+u.beta,0),nc=nb>=0?'#d9534f':'#2f6fed';
                return `<td style="border:1px solid #e5e8ec;padding:2px 5px;text-align:right;font-weight:700;color:${nc}">${fmt(nb)}</td>`;})()
              +`<td style="border:1px solid #e5e8ec;padding:2px 5px;text-align:right;font-weight:700">${gw.toFixed(1)}%</td></tr>`;
            ms.forEach(u=>{
              const w=100*Math.abs(u.beta)/sumAbsAll, c=u.beta>=0?'#d9534f':'#2f6fed';
              html+=`<tr><td style="border:1px solid #e5e8ec;padding:2px 5px 2px 14px">${E6(u.label)}</td>`
                +`<td style="border:1px solid #e5e8ec;padding:2px 5px;text-align:right">${u.lag}M</td>`
                +`<td style="border:1px solid #e5e8ec;padding:2px 5px;text-align:right">${fmt(u.corr)}</td>`
                +`<td style="border:1px solid #e5e8ec;padding:2px 5px;text-align:right;color:${c}">${fmt(u.beta)}</td>`
                +`<td style="border:1px solid #e5e8ec;padding:2px 5px;text-align:right;color:${c}">${w.toFixed(1)}%`
                +`<span style="display:inline-block;height:7px;width:${Math.min(48,Math.round(w*3))}px;background:${c};opacity:.6;border-radius:2px;margin-left:4px;vertical-align:middle"></span></td></tr>`;
              /* 개별 지표별 β·가중치 배정 사유 (규칙 기반 자동 문장) */
              const flip=(u.corr!=null)&&((u.corr>=0)!==(u.beta>=0)), gN=ms.length;
              let ex;
              if(flip) ex=`혼자 보면 ${u.corr>=0?'상승':'하락'} 방향(r ${fmt(u.corr)})이지만 같은 얘기를 하는 동료가 많아, 회의에선 그 중복분을 깎는 반대쪽 조정 역할을 배정받음`;
              else if(w>=8) ex=`12개월 예측에 출전 가능한(시차≥12M) 지표 중 신호가 뚜렷하고 겹치는 동료가 적어 발언권을 크게 받음`;
              else if(gN>1&&w<3) ex=`같은 그룹 ${gN}개 지표와 정보가 겹쳐 발언을 나눠 가짐 — 신호는 그룹 합계(가중치 소계)로 볼 것`;
              else if(Math.abs(u.corr||0)>=0.4&&w<5) ex=`단독 신호는 강하지만(r ${fmt(u.corr)}) 다른 지표가 이미 말한 정보와 겹쳐, 새로 보태는 몫이 작음`;
              else ex=`r ${fmt(u.corr)} 신호 중 다른 지표와 겹치지 않는 몫만큼만 발언권을 받음`;
              html+=`<tr><td colspan="5" style="border:1px solid #e5e8ec;border-top:none;padding:1px 5px 3px 16px;font-size:10px;color:#8a92a0;line-height:1.5">↳ <b style="color:${c}">${u.beta>=0?'상승':'하락'} 쪽 기여</b> · ${ex}</td></tr>`;
            });
          });
          html+=`</table><div class="note" style="margin-top:4px;line-height:1.7">`
            +`💡 <b>읽는 법 — 회의에 비유하면:</b> <b>r</b> 은 그 지표를 <b>1:1 면접</b>했을 때의 점수(혼자 놓고 보면 가격과 얼마나 비슷하게 움직였나), `
            +`<b>가중치</b>는 36개 지표가 다 모인 <b>회의에서의 실제 발언 시간</b>이다. 발언권은 컴퓨터가 과거 20년치를 채점해 자동으로 나눈다 — `
            +`다른 지표가 이미 말한 정보를 빼고 <b>새로 보태는 만큼</b> 커진다. `
            +`그래서 같은 말을 하는 지표들(통합 r 이 높은 그룹)은 발언 시간을 나눠 갖고, `
            +`제각각 다른 관점을 말하는 그룹은 합창(통합 r)은 엉성해도 각자 솔로가 쓸모 있어 발언 시간 합계가 커진다. `
            +`<b>통합 r</b> = 그룹을 한목소리로 합쳤을 때의 면접 점수. `
            +`<b>시차 17M</b> = 그 지표를 17개월 뒤로 밀었을 때 가격과 가장 잘 겹쳤다 — "지표가 움직이면 약 17개월 뒤 가격에 반영되더라"는 과거 패턴. `
            +`r 이 0.3대인데 가중치가 큰 이유: 12개월 예측에는 <b>시차 12개월 이상 지표만 출전</b>할 수 있어서, r 높은 단기 지표(평균매매가 0.9대 등)는 이 경기에 못 나온다 — 출전 가능한 선수 중 1등이면 발언권이 크다. `
            +`※ 12개월 예측 기준 — 시차가 12개월보다 짧은 지표(낙찰가율·수급 등)는 이 표에 없어도 1~11개월 단기 예측에는 쓰인다. `
            +`※ <b>가중치 색</b>(<b style="color:#d9534f">빨강</b>=상승 쪽·<b style="color:#2f6fed">파랑</b>=하락 쪽)은 r 의 부호가 아니라 <b>회의에서 실제로 민 방향</b>이다 — `
            +`비슷한 말을 하는 동료가 많으면, 혼자 볼 땐 +r 인 지표가 회의에선 동료들의 과대반영을 깎는 <b>반대 방향 조정 역할</b>을 맡기도 한다(예: 미국 정책금리 r +0.3대인데 파랑).</div>`;
          el.innerHTML=html;
        })();
        /* 아래 설명 + 백테스트 표 */
        const bt=P.backtest||{}, last=P.last||{};
        const ch=(P.price&&P.price.length&&last.price)?((P.price[P.price.length-1]/last.price-1)*100):null;
        const regLbl= GU? _rlG.names[GU] : _rlReg;
        const unitLbl= GU? '억원' : d.target.unit;
        const tgtLbl= GU? 'RTMS 실거래 중위가' : d.target.label;
        $('rl_main_n').innerHTML=
          `<b>${E6(regLbl)}</b> · 기준 <b>${E6(tgtLbl)}</b> ${last.price?last.price.toLocaleString():'-'} ${E6(unitLbl)} (${fm(last.t||'')} · ${d.target.smooth}개월 평균)`
          +(ch!=null?` → 12개월 뒤 예측 <b style="color:${ch>=0?'#d9534f':'#2f6fed'}">${P.price[P.price.length-1].toLocaleString()} (${ch>=0?'+':''}${ch.toFixed(1)}%)</b>`:'')
          +`<br>📅 점선 경계 오른쪽은 <b>미래(예측 구간)</b>라 지표 관측값이 없다 — 지표선은 마지막 관측월에서 끝나고, '시차 적용'을 켠 지표만 자기 선행 개월수만큼 경계 너머로 밀려 그려진다.`
          +`<br>📐 r 은 <b>원값이 아니라 전년비 변동률끼리</b> 잰다 — 20년 우상향한 두 계열은 무관해도 원값 상관이 0.9를 넘기 때문(추세 공유 착시). 그래서 GRDP·소득처럼 꾸준히만 크는 지표는 차트로는 겹쳐 보여도 r 이 낮게 나오는 것이 정상이다(서울 1인당 GRDP 실측: 원값 +0.94 vs 변동률 +0.18).`
          +`<br>🥇 지표 버튼은 <b>맞힐 가능성이 높은 순</b>으로 정렬돼 있다 — 그 지역 가격과의 상관계수(r) 절대값 순서다. r 이 +면 같이 오르고, −면 반대로 움직인 지표다.`
          +`<br>🕐 <b>시차</b>는 그 지표가 가격보다 몇 개월 앞서 움직였는지를 <b>데이터로 찾은 값</b>이다(0~${d.maxlag}개월 중 상관이 가장 큰 지점). '시차 적용'을 켜면 그만큼 밀어 그려 가격과 겹쳐 보인다.`
          +`<br>📉 예측은 <b>수집한 ${Object.keys(M).length}개 지표를 전 지역 동일하게</b> 넣어 회귀한다(지역 차이는 값·시차·계수에서만 난다). 지표마다 <b>예측 기간보다 긴 시차</b>를 다시 골라 쓰므로 아직 관측되지 않은 값은 쓰지 않는다. 회색 띠는 80% 구간.`
          +`<br>🔬 지표 조합은 백테스트로 정했다 — 지역별 자동선택(6개)·핵심 7개·전 지표 세 방식을 겨뤄 <b>전 지표가 18개 시도 모두에서 가장 정확</b>했다.`
          +(P.guarded&&P.guarded.length?`<br>🛡 ${P.guarded.length}개 지점은 과거에 겪은 변화 범위(5~95%)를 벗어나 그 경계로 눌렀다.`:'')
          +`<br><span style="opacity:.8">${E6(d.note||'')}</span>`;
        /* (2026-08-22) 주간동아 김학렬 인터뷰 — "매입할 아파트를 고를 때 확인해야 하는 지표는 딱 2가지,
           전세가와 거래량" 을 지역 신호로 요약한다. 전세가: 최근 6개월 추세(꾸준히 오르는가),
           거래량: 최근 3개월 평균의 전년 동기 대비. 실측값만 쓰고 판정 기준을 그대로 적는다. */
        (function(){
          const el=$('rl_sig'); if(!el) return;
          const last=(a)=>{const i=a.map((v,j)=>v!=null?j:-1).filter(j=>j>=0); return i.length?i[i.length-1]:-1;};
          const GU2=_rlGu&&_rlG&&_rlG.pred[_rlGu]?_rlGu:'';
          const je= GU2? ((_rlG.d[GU2]||{}).rent_g||[]) : ((d.d['jeonse']||{})['전국']||[]);
          const tr= GU2? ((_rlG.d[GU2]||{}).trade_g||[]) : ((d.d['trade']||{})[_rlReg]||[]);
          const j2=(d.d['jr']||{})[_rlReg];               // 전세가율(지역별, 2020~)
          const ji=last(je), ti=last(tr);
          let s1='', s2='';
          if(ji>=6&&je[ji-6]!=null){const ch=(je[ji]/je[ji-6]-1)*100;
            s1=`전세지수 6개월 ${ch>=0?'+':''}${ch.toFixed(1)}% ${ch>0.5?'<b style="color:#d9534f">↑ 수요 탄탄</b>':(ch<-0.5?'<b style="color:#2f6fed">↓ 주의</b>':'→ 보합')}`;}
          if(ti>=14){const cur=(tr[ti]+tr[ti-1]+tr[ti-2])/3, prv=(tr[ti-12]+tr[ti-13]+tr[ti-14])/3;
            if(prv){const ch=(cur/prv-1)*100;
              s2=`거래량 3개월평균 전년비 ${ch>=0?'+':''}${ch.toFixed(0)}% ${ch>10?'<b style="color:#d9534f">↑ 활발</b>':(ch<-10?'<b style="color:#2f6fed">↓ 위축</b>':'→ 평년')}`;}}
          /* (2026-08-22) 월간중앙 전문가 10인 설문 — "시장이 규제로 지나치게 경직되면 가격이
             내려가기보다 거래량이 먼저 사라진다". 가격(3개월평균 6개월 변화) × 거래량(전년비)
             4분면으로 국면을 판정한다: 가격↑거래↓=매물잠김 · 가격↓거래↓=거래절벽(관망) ·
             가격↑거래↑=활황 · 가격↓거래↑=매물출회. */
          let s3='';
          const pm= GU2? ((_rlG.price[GU2]||{}).ma||[]) : ((d.price[_rlReg]||{}).ma||[]); const pi=last(pm);
          if(pi>=6&&pm[pi-6]!=null&&s2){
            const pch=(pm[pi]/pm[pi-6]-1)*100;
            const tUp=s2.includes('활발'), tDn=s2.includes('위축');
            const ph=pch>1, pl=pch<-1;
            const q= ph&&tDn?'<b style="color:#e08e3c">매물잠김형 상승</b> — 거래 없이 가격만 오름(호가 주도, 신뢰 낮음)'
                   : pl&&tDn?'<b style="color:#6b7280">거래절벽 관망</b> — 가격·거래 동반 위축(방향 탐색 국면)'
                   : ph&&!tDn&&!tUp?'가격 완만한 상승(거래 평년)'
                   : ph&&tUp?'<b style="color:#d9534f">활황</b> — 가격·거래 동반 상승(추세 신뢰 높음)'
                   : pl&&tUp?'<b style="color:#2f6fed">매물출회</b> — 가격 하락 속 거래 증가(하방 압력)'
                   : '보합권';
            s3=`국면: ${q}`;
          }
          el.innerHTML=(s1||s2)?`🏷 <b>${E6(GU2?_rlG.names[GU2]:_rlReg)}</b> 매수 판단 2지표 <span class="note">(주간동아·김학렬 — "전세가와 거래량")</span> : ${[s1,s2,s3].filter(Boolean).join(' · ')}`:'';
        })();
        /* (2026-08-22) 🧠 모델 사용 내역 표 — 사용자 질문("지표별 가중치·중복·λ가 어떻게 쓰이나")에
           화면으로 답한다. β 는 릿지가 학습한 표준화 가중치(12개월 지평 기준): 모든 지표를 평균0·표준편차1로
           맞춘 뒤의 계수라 단위와 무관하게 |β| 가 클수록 예측을 많이 움직인 지표다. r 은 참고용 단순 상관,
           실제 가중치는 β — 둘의 순위가 다른 것이 정상이다(중복 지표는 릿지가 가중치를 나눠 갖는다). */
        (function(){
          const el=$('rl_model'); if(!el) return;
          const U=(P.used||[]).filter(u=>u.beta!=null);
          if(!U.length){ el.innerHTML=''; return; }
          const lam=P.lam!=null?P.lam:'-';
          const srt=[...U].sort((a,b)=>Math.abs(b.beta)-Math.abs(a.beta));
          const bmax=Math.max(...srt.map(u=>Math.abs(u.beta)))||1;
          const grpCnt={}; U.forEach(u=>{grpCnt[u.group]=(grpCnt[u.group]||0)+1;});
          el.innerHTML=
            `<details style="margin-top:8px"><summary style="cursor:pointer;font-size:12px;font-weight:600">🧠 이번 예측이 지표를 쓴 방식 — 가중치(β)·시차·상관 전체 표 <span class="note">(릿지 강도 λ=${lam} · 12개월 지평 모델 · ${U.length}개 지표 사용)</span></summary>`
            +`<div class="note" style="margin:6px 0;line-height:1.7">`
            +`가중치는 사람이 정하지 않는다 — 모든 지표를 표준화한 뒤 <b>릿지 회귀가 β 를 학습</b>한다. |β| 가 클수록 이번 예측을 많이 움직인 지표. `
            +`r(단순 상관)와 β 순위가 다른 것이 정상이다: 비슷한 지표들(같은 <b>그룹</b>)은 릿지가 가중치를 <b>나눠 갖게</b> 눌러서, 한 주제가 여러 표를 행사하는 것을 막는다. `
            +`λ 는 그 누르는 강도이며 지역별 백테스트로 {0.3, 1, 3} 중 자동 선택된다(클수록 강하게 누름). `
            +`시차 열은 그 지표를 몇 개월 전 값으로 넣었는지다 — 12개월 예측이라 모든 지표가 12개월 이상 전 값만 쓴다(미래 참조 없음).</div>`
            +`<table style="border-collapse:collapse;font-size:11px"><tr style="background:#f6f7f9">`
            +`<th style="border:1px solid #e5e8ec;padding:3px 7px">#</th>`
            +`<th style="border:1px solid #e5e8ec;padding:3px 7px">지표</th>`
            +`<th style="border:1px solid #e5e8ec;padding:3px 7px">그룹(중복 가족)</th>`
            +`<th style="border:1px solid #e5e8ec;padding:3px 7px">시차</th>`
            +`<th style="border:1px solid #e5e8ec;padding:3px 7px">r(상관)</th>`
            +`<th style="border:1px solid #e5e8ec;padding:3px 7px">β(가중치)</th>`
            +`<th style="border:1px solid #e5e8ec;padding:3px 7px;min-width:130px">영향력</th></tr>`
            +srt.map((u,i)=>{
              const w=Math.round(100*Math.abs(u.beta)/bmax);
              const c=u.beta>=0?'#d9534f':'#2f6fed';
              const dup=grpCnt[u.group]>1?` <span style="opacity:.6">×${grpCnt[u.group]}</span>`:'';
              return `<tr><td style="border:1px solid #e5e8ec;padding:2px 7px;text-align:right">${i+1}</td>`
                +`<td style="border:1px solid #e5e8ec;padding:2px 7px">${E6(u.label)}</td>`
                +`<td style="border:1px solid #e5e8ec;padding:2px 7px">${E6(u.group||'')}${dup}</td>`
                +`<td style="border:1px solid #e5e8ec;padding:2px 7px;text-align:right">${u.lag}개월</td>`
                +`<td style="border:1px solid #e5e8ec;padding:2px 7px;text-align:right">${u.corr>0?'+':''}${u.corr}</td>`
                +`<td style="border:1px solid #e5e8ec;padding:2px 7px;text-align:right;color:${c};font-weight:600">${u.beta>0?'+':''}${u.beta}</td>`
                +`<td style="border:1px solid #e5e8ec;padding:2px 7px"><span style="display:inline-block;height:8px;width:${w}%;min-width:2px;background:${c};border-radius:2px;opacity:.75"></span></td></tr>`;
            }).join('')+`</table>`
            +`<div class="note" style="margin-top:4px">β 부호: <b style="color:#d9534f">+</b> 이 지표가 오르면 가격 상승 쪽으로, <b style="color:#2f6fed">−</b> 는 하락 쪽으로 기여. 그룹 ×N 표시는 같은 주제의 지표가 N개 있다는 뜻 — 릿지가 이들의 가중치를 나눠 과대반영을 막는다.</div>`
            +`</details>`;
        })();
        const rows=Object.keys(bt.by_h||{}).map(h=>+h).sort((a,b)=>a-b).filter(h=>[1,3,6,9,12,15,18,21,24].includes(h));
        $('rl_tbl').innerHTML=
          `<table style="border-collapse:collapse;font-size:11px"><tr style="background:#f6f7f9">`
          +`<th style="border:1px solid #e5e8ec;padding:3px 8px">과거 재현 성적</th>`
          +rows.map(h=>`<th style="border:1px solid #e5e8ec;padding:3px 8px">${h}개월 뒤</th>`).join('')+`</tr>`
          +`<tr><td style="border:1px solid #e5e8ec;padding:3px 8px">평균 오차(MAPE)</td>`
          +rows.map(h=>{const b=bt.by_h[h], worse=b.naive!=null&&b.mape>b.naive;
            return `<td style="border:1px solid #e5e8ec;padding:3px 8px;text-align:right;${worse?'color:#d9534f;font-weight:600':''}">${b.mape}%${worse?' ⚠':''}</td>`;}).join('')+`</tr>`
          +`<tr><td style="border:1px solid #e5e8ec;padding:3px 8px">그냥 '변동 없음' 이라 했을 때</td>`
          +rows.map(h=>`<td style="border:1px solid #e5e8ec;padding:3px 8px;text-align:right;opacity:.7">${bt.by_h[h].naive}%</td>`).join('')+`</tr>`
          +`<tr><td style="border:1px solid #e5e8ec;padding:3px 8px">방향(오를지 내릴지) 적중률</td>`
          +rows.map(h=>`<td style="border:1px solid #e5e8ec;padding:3px 8px;text-align:right">${bt.by_h[h].hit}%</td>`).join('')+`</tr></table>`
          +`<div class="note" style="margin-top:4px">과거 ${bt.origins||0}개 시점으로 되돌아가 그때 자료만으로 예측하고 실제와 비교한 결과다(표본 ${bt.n||0}건). `
          +`'변동 없음' 줄보다 오차가 작아야 예측에 의미가 있다 — <b style="color:#d9534f">⚠ 붉은 칸</b>은 단순 예측만 못한 지평이니 그 구간 예측선은 참고만 할 것. 방향 적중률 50%는 동전 던지기와 같다.</div>`;
      }
      const GLOBRL=['cli','m2','gdp','fx','rate_kr','mtg_bal','mtg_rate','kospi','hppci','jeonse','csi'];
      _rlSel=defSel();
      draw();
    }).catch(()=>{});
  }

  window.renderEstate=function(){
    initRehub(); initRelead(); initApt(); initMolit(); initEtc(); initApply(); initRedev(); initUsHouse(); initHCredit(); initDelq(); initAptRank(); initBizClose(); initAutos();
    if(loaded) return; loaded=true;
    fetch('/api/db/realestate').then(r=>r.json()).then(d=>{
      const S=d.series||{};
      {const e=$('re_asof'); if(e) e.textContent=`한국은행 ECOS · 월간 · 수집 ${d.asof||''} · 매일 07:10 자동 갱신`;}
      const cut=(a,n)=>({t:a.t.slice(-n),v:a.v.slice(-n)});
      /* ① 전망CSI — 최근 5년, 100 기준선 */
      {const a=cut(S.csi||{t:[],v:[]},60);
       line('re_csi',[{...a,label:'전망CSI',color:'#2f6fed'}],{base:100});
       const lv=a.v[a.v.length-1], pv=a.v[a.v.length-2];
       $('re_csi_n').innerHTML=`최신 <b>${fm(a.t[a.t.length-1])} = ${lv??'—'}</b>${pv!=null?` (전월 ${pv>lv?'−':'+'}${Math.abs(lv-pv)}p)`:''} — `+
         (lv>=100?`<b class="up">100 위 = 상승 예상 우세</b> (심리 회복 국면)`:`<b class="dn">100 아래 = 하락 예상 우세</b>`)+
         ` · 심리 선행지표라 실제 가격지수보다 몇 달 먼저 도는 경향`;}
      /* ② 주담대 금리 — 최근 5년 */
      {const a=cut(S.mtg||{t:[],v:[]},60);
       line('re_mtg',[{...a,label:'주담대',color:'#d9534f'}]);
       const lv=a.v[a.v.length-1];
       $('re_mtg_n').innerHTML=`최신 <b>${fm(a.t[a.t.length-1])} = ${lv!=null?lv.toFixed(2)+'%':'—'}</b> — 전망CSI와 대체로 역방향(금리 하락 → 매수심리 회복)`;}
      /* ③ 매매지수 — 3선, 최근 5년 */
      {const n=60, s1=cut(S.sale||{t:[],v:[]},n), s2=cut(S.sale_apt||{t:[],v:[]},n), s3=cut(S.sale_apt_s||{t:[],v:[]},n);
       line('re_sale',[{...s1,label:'전국',color:'#666'},{...s2,label:'아파트',color:'#2f6fed'},{...s3,label:'서울APT',color:'#d9534f'}]);
       const y1=yoy(S.sale_apt_s.t,S.sale_apt_s.v), y2=yoy(S.sale_apt.t,S.sale_apt.v);
       $('re_sale_n').innerHTML=`YoY — 서울아파트 <b class="${y1>0?'up':'dn'}">${y1!=null?(y1>0?'+':'')+y1.toFixed(1)+'%':'—'}</b> · 전국아파트 <b class="${y2>0?'up':'dn'}">${y2!=null?(y2>0?'+':'')+y2.toFixed(1)+'%':'—'}</b> · 서울이 전국보다 선행하는 경향`;}
      /* ④ 전세지수 */
      {const n=60, s1=cut(S.js||{t:[],v:[]},n), s2=cut(S.js_apt||{t:[],v:[]},n), s3=cut(S.js_apt_s||{t:[],v:[]},n);
       line('re_js',[{...s1,label:'전국',color:'#666'},{...s2,label:'아파트',color:'#2f6fed'},{...s3,label:'서울APT',color:'#27ae60'}]);
       const y1=yoy(S.js_apt_s.t,S.js_apt_s.v);
       $('re_js_n').innerHTML=`YoY — 서울아파트 전세 <b class="${y1>0?'up':'dn'}">${y1!=null?(y1>0?'+':'')+y1.toFixed(1)+'%':'—'}</b> · 전세↑+매매 횡보 = 갭 축소(매매 전환 압력) 참고`;}
      /* ⑦ 은행 정기예금 잔액 — 월별(조원) · 휠=X축 확대/축소·드래그=이동 (2026-08-02) */
      {const a0=S.tdep||{t:[],v:[]};
       if(a0.t.length){
         const T=a0.t, V=a0.v.map(v=>v!=null?v/1000:null), L=T.length;   // 십억원 → 조원
         let vn=Math.min(120,L), off=0;                                  // 기본 최근 10년
         const draw=()=>{const end=L-off, st=Math.max(0,end-vn);
           line('re_tdep',[{t:T.slice(st,end),v:V.slice(st,end),label:'정기예금(조원)',color:'#047857'}]);};
         draw();
         const cv=$('re_tdep');
         cv.addEventListener('wheel',e=>{e.preventDefault();
           const r=cv.getBoundingClientRect(), fr=Math.min(1,Math.max(0,(e.clientX-r.left)/r.width));
           const end=L-off, st=Math.max(0,end-vn), n0=end-st, anchor=st+fr*(n0-1);
           const n1=Math.max(12,Math.min(L,Math.round(n0*(e.deltaY<0?0.8:1.25))));
           let s1=Math.round(anchor-fr*(n1-1)); s1=Math.max(0,Math.min(L-n1,s1));
           vn=n1; off=L-s1-n1; draw();},{passive:false});
         let dr=null;
         cv.addEventListener('mousedown',e=>{dr={x:e.clientX,o:off};});
         cv.addEventListener('mousemove',e=>{if(!dr)return;
           const bw=(cv.clientWidth||700)/Math.max(1,vn);
           off=Math.max(0,Math.min(L-vn,dr.o+Math.round((e.clientX-dr.x)/bw))); draw();});
         cv.addEventListener('mouseup',()=>{dr=null;}); cv.addEventListener('mouseleave',()=>{dr=null;});
         const lv=V[L-1], pv=V[L-2], y1=yoy(T,a0.v);
         $('re_tdep_n').innerHTML=`최신 <b>${fm(T[L-1])} 월말 = ${lv!=null?Math.round(lv).toLocaleString()+'조원':'—'}</b>${pv!=null?` (전월 ${lv-pv>0?'+':''}${(lv-pv).toFixed(1)}조)`:''} · YoY <b class="${y1>0?'up':'dn'}">${y1!=null?(y1>0?'+':'')+y1.toFixed(1)+'%':'—'}</b> — 예금금리 매력이 높거나 위험회피 국면에서 증가. 증시 투자자예탁금·부동산 매수세와 반대로 움직이는 경향(12월 법인자금 유입 등 계절성 있음) · ECOS 공표 ~1개월+ 지연 · 🖱 휠=확대/축소(전체 2010~), 드래그=좌우 이동`;
       }}
      /* ⑧⑨ 아파트 실거래(국토부 rtms.py 매일 07:20) — 지역 드롭다운 + 거래량·가격 (2026-08-02) */
      fetch('/api/db/rtms').then(x=>x.ok?x.json():null).then(R=>{
        if(!R||!R.sale) return;
        /* (2026-08-06) 단일지역 드롭다운·거래량·가격 카드 삭제(지역 비교와 중복 — 사용자 요청).
           기존 `if(!re_rt_sel) return` 가드가 아래 지역 비교 초기화까지 스킵시키던 버그 함께 제거 */
        /* ── 지역 비교 대형 차트 — 다중 선택(검색+칩) · 지표 토글 (2026-08-02) ── */
        {const N=R.names||{}, MAXSEL=30;
         // 30개까지 겹쳐 그리므로 색상도 30개 — 인접 색이 붙지 않게 색상환을 넓게 돈다
         const PAL=['#d9534f','#2f6fed','#27ae60','#e08e3c','#7c3aed','#0e9aa7','#c2185b','#5d4037',
                    '#455a64','#9e9d24','#00838f','#6d4c41','#e91e63','#3f51b5','#009688','#ff9800',
                    '#673ab7','#00acc1','#8bc34a','#795548','#f44336','#1976d2','#43a047','#fb8c00',
                    '#512da8','#0097a7','#afb42b','#4e342e','#ad1457','#283593'];
         const E=z=>String(z??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));  // 부동산 IIFE엔 전역 E 없음(ReferenceError 수정)
         const METRICS=[['avg','평균가(억)'],['med','중위가(억)'],['n','매매 거래량'],['dep','전세 보증금(억)']];
         /* (2026-08-10) '전국 전체(공식)' — RTMS 실거래는 아직 전국 250여 시군구 중 일부만
            채워져 있어 시군구를 다 합쳐도 전국 총량이 안 된다(실측: 아파트 53개 시군구).
            그래서 **거래량 지표에 한해** 국토부 공식 집계(KOSIS htrade.json)를 계열로 끼워 넣는다.
            평균가·중위가·전세보증금은 공식 집계에 없으므로 그 지표에선 자동으로 빠진다. */
         const KRALL='KR_ALL', KRAPT='KR_APT';
         const injectKR=()=>{ if(!_htRaw||!_htRaw.t||N[KRALL]) return false;
           const put=(code,label,kind)=>{ const a=(_htRaw[kind]||{})['전국']; if(!a) return;
             const m={}; _htRaw.t.forEach((ym,i)=>{ if(a[i]!=null) m[ym]={n:a[i]}; });
             N[code]=label; (R.sale=R.sale||{})[code]={m}; };
           put(KRALL,'전국 전체(공식·주택)','all'); put(KRAPT,'전국 전체(공식·아파트)','apt');
           return true; };
         injectKR();
         let mset=['A11','A26','A41'].filter(c=>N[c]); if(!mset.length) mset=Object.keys(N).slice(0,3);
         let met='avg';
         const q=$('re_cmp_q'), list=$('re_cmp_list');
         const mbar=()=>{$('re_cmp_metric').innerHTML=METRICS.map(([k,l])=>`<button data-m="${k}" style="margin-right:4px;padding:3px 10px;font-size:12px;border:1px solid #d7dce3;border-radius:6px;cursor:pointer;background:${k===met?'#1f2937':'#fff'};color:${k===met?'#fff':'#333'}">${l}</button>`).join('');
           $("re_cmp_metric").querySelectorAll("button").forEach(b=>b.onclick=()=>{met=b.dataset.m; _refYm=null; mbar(); pbar(); drawBig(true);});};
         let hiLab=null;                     // 강조 중인 계열 라벨(칩 hover / 차트 hover)
         const chips=()=>{$('re_cmp_chips').innerHTML=mset.map((c,i)=>`<span data-hi="${E(N[c]||c)}" style="display:inline-flex;align-items:center;gap:3px;padding:2px 7px;font-size:12px;border-radius:10px;background:${PAL[i%PAL.length]}18;border:1px solid ${PAL[i%PAL.length]};color:#333;cursor:pointer"><b style="color:${PAL[i%PAL.length]}">●</b>${E(N[c]||c)}<b data-rm="${c}" style="cursor:pointer;color:#888">✕</b></span>`).join('');
           $('re_cmp_chips').querySelectorAll('[data-rm]').forEach(x=>x.onclick=e=>{
             e.stopPropagation(); mset=mset.filter(c=>c!==x.dataset.rm); chips(); drawBig(true);});
           /* 칩에 마우스를 올리면 그 지역만 진하게 — 30개가 겹쳐도 하나를 눈으로 따라갈 수 있다 */
           $('re_cmp_chips').querySelectorAll('[data-hi]').forEach(x=>{
             x.onmouseenter=()=>{hiLab=x.dataset.hi.replace(/\(.*\)/,''); drawBig();};
             x.onmouseleave=()=>{hiLab=null; drawBig();};});};
         /* (2026-08-08) 시도로 검색이 안 되던 문제 —
            광역시 시군구는 이름에 시도가 붙어 있지만("부산 중구") 도 단위는 안 붙어 있어서
            ("수원 장안구","춘천시") '경기'·'강원' 으로 검색하면 하나도 안 걸렸다.
            법정동코드 앞 2자리로 시도를 유추해 검색어와 표시에 함께 쓴다. */
         const SD={'11':'서울','12':'광주·전남','26':'부산','27':'대구','28':'인천','29':'광주','30':'대전','31':'울산',
                   '36':'세종','41':'경기','43':'충북','44':'충남','46':'전남','47':'경북','48':'경남',
                   '50':'제주','51':'강원','52':'전북'};
         const sdOf=c=>SD[String(c).replace(/^A/,'').slice(0,2)]||'';
         const showList=()=>{const kw=(q.value||'').trim().toLowerCase();
           const hay=c=>`${sdOf(c)} ${N[c]||c}`.toLowerCase();
           const cand=Object.keys(N).filter(c=>!mset.includes(c)&&(!kw||hay(c).includes(kw)));
           const aggs=cand.filter(c=>c.startsWith('A')), regs=cand.filter(c=>!c.startsWith('A'));
           regs.sort((a,b)=>hay(a)<hay(b)?-1:1);                    // 시도 → 시군구 순으로 묶어 보여준다
           list.innerHTML=[...aggs,...regs].slice(0,60).map(c=>{
             const sd=sdOf(c), nm=String(N[c]||c);
             const pre=(!c.startsWith('A')&&sd&&!nm.startsWith(sd))?`<span class="note">${E(sd)}</span> `:'';
             return `<div data-add="${c}" style="padding:5px 10px;font-size:12.5px;cursor:pointer;border-bottom:1px solid #f2f4f7">${c.startsWith('A')?'★ ':''}${pre}${E(nm)}</div>`;
           }).join('')||'<div style="padding:6px 10px" class="note">없음</div>';
           list.style.display='';
           list.querySelectorAll('[data-add]').forEach(x=>x.onclick=()=>{if(mset.length>=MAXSEL){alert('최대 '+MAXSEL+'개까지');return;}
             mset.push(x.dataset.add); q.value=''; list.style.display='none'; chips(); drawBig(true);});};
         /* (2026-08-08) 원클릭 프리셋 — 하나씩 고르기 번거로운 조합을 버튼으로.
            'TOP30' 은 현재 선택된 지표의 최신값 기준 상위 30(시군구만, 시도 합산 ★ 제외) */
         /* 합산 계열(시도 ★ · 전국 공식)은 TOP30 순위 대상에서 뺀다 — 총량이 시군구를 다 눌러버린다 */
         const isAgg=c=>String(c).startsWith('A')||String(c).startsWith('KR_');
         /* 정렬·TOP 선정 기준값 — **잠정 구간 직전의 확정 최신월**을 쓴다.
            최근 2개월은 실거래 신고가 덜 들어와 값이 과소·요동치므로 순위 기준으로 부적합하다. */
         const confCut=()=>{const d=new Date(); d.setMonth(d.getMonth()-2);
           return `${d.getFullYear()}${String(d.getMonth()+1).padStart(2,'0')}`;};
         /* (2026-08-08) 기준월을 지역마다 따로 잡으면 서로 다른 달을 비교하게 된다
            (옛 고가 거래가 남은 구가 최신 최고가 구보다 위로 올라가는 문제).
            → 전 지역 공통의 '잠정 직전 최신월'을 하나 정하고 그 달 값으로만 줄 세운다. */
         let _refYm=null;
         const refYm=()=>{ if(_refYm) return _refYm;
           const src=met==='dep'?(R.rent||{}):(R.sale||{}); const cut=confCut();
           const all=new Set();
           Object.keys(N).forEach(c=>Object.keys((src[c]||{}).m||{}).forEach(t=>{if(t<=cut) all.add(t);}));
           const ts=[...all].sort(); _refYm=ts.length?ts[ts.length-1]:null; return _refYm;};
         const latestOf=c=>{const src=met==='dep'?(R.rent||{}):(R.sale||{});
           const t=refYm(); if(!t) return null;
           const e=((src[c]||{}).m||{})[t]; return e?(e[met]??null):null;};
         const topN=(filter,n)=>Object.keys(N).filter(c=>!isAgg(c)&&filter(c))
           .map(c=>[c,latestOf(c)]).filter(x=>x[1]!=null)
           .sort((a,b)=>b[1]-a[1]).slice(0,n).map(x=>x[0]);
         const PRESET=[
           ['서울 전체구','서울 25개구 전부', ()=>Object.keys(N).filter(c=>!isAgg(c)&&c.startsWith('11'))],
           ['부산 전체구','부산 16개 구·군 전부', ()=>Object.keys(N).filter(c=>!isAgg(c)&&c.startsWith('26'))],
           ['경기 TOP30','경기 시군구 중 상위 30', ()=>topN(c=>c.startsWith('41'),30)],
           ['전국 TOP30','전국 시군구 중 상위 30', ()=>topN(()=>true,30)],
           /* (2026-08-10) 전국 합산 — 시도 합산(★)과 같은 방식으로 246개 시군구를 묶은 계열.
              rtms.py 가 만들어 주므로 4개 지표 모두 나온다. */
           ['★ 전국 전체','수집된 246개 시군구 합산 — 4개 지표 모두 표시', ()=>N['AKR']?['AKR']:[]],
           /* 공식 집계는 거래량밖에 없다 → 평균가 상태에서 누르면 빈 차트가 나온다.
              (실제로 그렇게 눌러 빈 화면을 봤다) → 지표를 거래량으로 함께 바꿔준다. */
           ['공식 집계(국토부)','국토부·부동산원 월별 집계 — 거래량 지표로 자동 전환',
             ()=>{ if(met!=='n'){ met='n'; _refYm=null; mbar(); } return [KRALL,KRAPT].filter(c=>N[c]); }],
         ];
         const pbar=()=>{$('re_cmp_preset').innerHTML=PRESET.map(([lab,tip],i)=>
             `<button data-p="${i}" title="${tip}" style="padding:3px 9px;font-size:11.5px;border:1px solid #b45309;color:#b45309;background:#fff;border-radius:6px;cursor:pointer">${lab}</button>`).join('')
             +`<button data-clr="1" title="선택 비우기" style="padding:3px 8px;font-size:11.5px;border:1px solid #d7dce3;border-radius:6px;cursor:pointer;background:#fff;color:#888">비우기</button>`;
           $('re_cmp_preset').querySelectorAll('[data-p]').forEach(b=>b.onclick=()=>{
             mset=PRESET[+b.dataset.p][2]().slice(0,MAXSEL); chips(); drawBig(true);});
           $('re_cmp_preset').querySelector('[data-clr]').onclick=()=>{mset=[]; chips(); drawBig(true);};};
         pbar();
         q.oninput=showList; q.onfocus=showList;
         document.addEventListener('click',e=>{ if(!e.target.closest('#re_cmp_q')&&!e.target.closest('#re_cmp_list')) list.style.display='none'; });
         let vN=null, vOff=0, curL=0, _bigArr=null;                       // 휠 확대/축소 상태 (null=전체)
         function drawBig(reset){
           if(reset){ vN=null; vOff=0; }
           /* (2026-08-08) 칩을 최신값 내림차순으로 정렬 — 칩 순서 = 차트에서 위→아래 순서가 되어
              30개를 겹쳐 놔도 "위에서 몇 번째 선이 어느 구인지" 눈으로 바로 맞출 수 있다.
              색도 이 순서를 따라가므로 지표를 바꾸면 순서·색이 함께 재배치된다. */
           {const ord=mset.map(c=>[c, latestOf(c)]).sort((a,b)=>(b[1]??-1e18)-(a[1]??-1e18)).map(x=>x[0]);
            if(ord.join('|')!==mset.join('|')){ mset=ord; chips(); }}
           const src=met==='dep'?(R.rent||{}):(R.sale||{});
           const tset=new Set(); mset.forEach(c=>Object.keys((src[c]||{}).m||{}).forEach(t=>tset.add(t)));
           /* (2026-08-08) '비우기' 후에도 이전 그림이 남던 버그 — 조기 return 전에 캔버스를 비운다 */
           const clearCv=()=>{const c=$('re_rt_big'); if(!c) return;
             const g=c.getContext('2d'); c.width=c.clientWidth||900; c.height=c.clientHeight||600;
             g.clearRect(0,0,c.width,c.height); _bigArr=null; hiLab=null;};
           const full=[...tset].sort();
           if(!mset.length){ clearCv(); $('re_rt_big_n').innerHTML='<span class="note">지역을 선택하세요 — 위 버튼(서울 전체구·전국 TOP30 등)이나 검색으로 추가할 수 있습니다.</span>'; return; }
           if(!full.length){ clearCv(); $('re_rt_big_n').textContent='선택된 지역의 데이터가 없습니다'; return;}
           curL=full.length;
           const n=vN?Math.max(6,Math.min(vN,curL)):curL, off=Math.max(0,Math.min(vOff,curL-n));
           const end=curL-off, st=Math.max(0,end-n);
           const ts=full.slice(st,end);
           const _d=new Date(); _d.setMonth(_d.getMonth()-2);
           const _cut=`${_d.getFullYear()}${String(_d.getMonth()+1).padStart(2,'0')}`;
           let provIdx=ts.findIndex(t=>t>_cut); if(provIdx<0) provIdx=null;
           const arr=mset.map((c,i)=>({t:ts,v:ts.map(t=>{const e=((src[c]||{}).m||{})[t]; return e?(e[met]??null):null;}),
                                       label:(N[c]||c).replace(/\(.*\)/,''),color:PAL[i%PAL.length]})).filter(a=>a.v.some(v=>v!=null));
           if(!arr.length){ const cvb=$('re_rt_big'); cvb.getContext('2d').clearRect(0,0,cvb.width,cvb.height);
             const onlyKR=mset.length&&mset.every(c=>String(c).startsWith('KR_'));
             $('re_rt_big_n').innerHTML=onlyKR
               ? `<b>공식 집계에는 '${E(METRICS.find(x=>x[0]===met)[1])}' 가 없습니다</b> — 국토부·부동산원 월별 집계는 <b>거래 건수만</b> 공표합니다.`
                 +` <span class="note">가격까지 보시려면 위 <b>매매 거래량</b> 으로 바꾸거나, <b>★ 전국 전체</b>(실거래 246개 시군구 합산)를 쓰세요.</span>`
               : '선택 지역엔 이 지표 데이터가 없습니다 — 다음 수집(매일 07:20) 후 시도 전체 중위가(근사)가 채워집니다';
             return; }
           _bigArr=arr;                       // 차트 hover 로 근접 계열을 찾기 위해 보관
           const rIdx=(()=>{const t=refYm(); return t?ts.indexOf(t):-1;})();
           line('re_rt_big',arr,{provIdx,hi:hiLab,refIdx:rIdx});
           /* 차트 hover ↔ 칩 강조를 양방향으로 — 선을 짚으면 그 지역 칩이 켜진다 */
           $('re_cmp_chips').querySelectorAll('[data-hi]').forEach(el=>{
             const on=hiLab&&el.dataset.hi.replace(/\(.*\)/,'')===hiLab;
             el.style.boxShadow=on?'0 0 0 2px #1f2937':'';
             el.style.fontWeight=on?'700':'400';});
           const ml=METRICS.find(x=>x[0]===met)[1];
           const hasKR=mset.some(c=>String(c).startsWith('KR_'));
           $('re_rt_big_n').innerHTML=(hasKR?`<b style="color:#b45309">전국 전체(공식)</b>는 국토부·한국부동산원 월별 집계(주택 매매거래 신고 건수)라 다른 계열(RTMS 아파트 실거래)과 <b>집계 대상이 다르다</b> — 총량 추세를 볼 때만 쓰세요.<br>`:'')
             +`<b>${ml}</b> · ${arr.length}개 지역 겹쳐보기 — 시도 전체(★)는 시군구 합산(거래건수 가중)${met==='med'?' · 시도 전체 중위가는 <b>거래량 가중 근사치</b>':''} · 주황 음영=신고 진행 중(잠정) · 🖱 휠=X축 확대/축소·드래그=좌우 이동(표시 ${ts.length}/${curL}개월) · 지역별 스케일 차이가 크면 거래량으로 비교 권장`;
         }
         {const cv2=$('re_rt_big');
          cv2.addEventListener('wheel',e=>{ e.preventDefault();
            const r2=cv2.getBoundingClientRect();
            const fr=Math.min(1,Math.max(0,(e.clientX-r2.left)/Math.max(1,r2.width)));
            const n0=vN?Math.min(vN,curL):curL, off0=Math.min(vOff,curL-n0);
            const st0=Math.max(0,curL-off0-n0), anchor=st0+fr*(n0-1);
            const n1=Math.max(6,Math.min(curL,Math.round(n0*(e.deltaY<0?0.8:1.25))));
            let s1=Math.round(anchor-fr*(n1-1)); s1=Math.max(0,Math.min(curL-n1,s1));
            vN=n1; vOff=curL-s1-n1; drawBig();
          },{passive:false});
          let dr2=null;
          cv2.addEventListener('mousedown',e=>{ dr2={x:e.clientX,o:vOff}; });
          cv2.addEventListener('mousemove',e=>{ if(!dr2){
            /* 드래그 중이 아니면 커서에 가장 가까운 선을 찾아 강조 —
               30개가 겹쳐도 마우스만 올리면 어느 구인지 바로 뜬다 */
            if(!_bigArr||!_bigArr.length) return;
            const r=cv2.getBoundingClientRect();
            const W=cv2.clientWidth||900, Hh=cv2.clientHeight||600;
            const P={l:8,r:52,t:10,b:18};
            const N0=Math.max(..._bigArr.map(a=>a.v.length));
            const fx=(e.clientX-r.left)/W*(cv2.width||W);   // 실제 캔버스 좌표계로
            const fy=(e.clientY-r.top)/Hh*(cv2.height||Hh);
            const iw=(cv2.width-P.l-P.r)/Math.max(1,N0-1);
            let idx=Math.round((fx-P.l)/Math.max(1,iw));
            idx=Math.max(0,Math.min(N0-1,idx));
            const all=_bigArr.flatMap(a=>a.v).filter(v=>v!=null);
            if(!all.length) return;
            let lo=Math.min(...all), hi2=Math.max(...all);
            const pad=(hi2-lo)*0.06||1; lo-=pad; hi2+=pad;
            const Yv=v=>P.t+(cv2.height-P.t-P.b)*(1-(v-lo)/(hi2-lo));
            let best=null, bd=1e9;
            _bigArr.forEach(a=>{ let v=a.v[idx];
              if(v==null){ for(let k=1;k<6&&v==null;k++) v=a.v[idx-k]??a.v[idx+k]; }
              if(v==null) return;
              const d=Math.abs(Yv(v)-fy); if(d<bd){bd=d; best=a.label;} });
            const nl=(bd<26)?best:null;
            if(nl!==hiLab){ hiLab=nl; drawBig(); }
            return; }
            const n0=vN?Math.min(vN,curL):curL;
            const bw=(cv2.clientWidth||900)/Math.max(1,n0);
            vOff=Math.max(0,Math.min(curL-n0,dr2.o+Math.round((e.clientX-dr2.x)/bw))); drawBig(); });
          cv2.addEventListener('mouseup',()=>{ dr2=null; });
          cv2.addEventListener("mouseleave",()=>{ dr2=null; if(hiLab){hiLab=null; drawBig();} });}
         mbar(); chips(); drawBig(true);
         /* htrade 가 아직 안 왔으면 도착한 뒤 '전국 전체(공식)'를 끼워 넣고 버튼만 다시 그린다 */
         htrade().then(()=>{ if(injectKR()){ pbar(); } });}
      }).catch(()=>{});
      /* ⑤ 주택 시가총액 — 수도권 비중 추이(연간) + 전국 규모 */
      try{
        const M=d.mcap||{};
        if(M['전국']&&M['서울']){
          const ts=M['전국'].t;
          const shr=ts.map((t,i)=>{ const g=r=>{const j=(M[r]||{}).t.indexOf(t); return j>=0?M[r].v[j]:null;};
            const su=g('서울'),gy=g('경기'),ic=g('인천'),na=M['전국'].v[i];
            return (su!=null&&gy!=null&&ic!=null&&na)?(su+gy+ic)/na*100:null; });
          line('re_mcap',[{t:ts,v:shr,label:'수도권 비중%',color:'#e08e3c'}]);
          const lv=shr[shr.length-1], nat=M['전국'].v[M['전국'].v.length-1];
          $('re_mcap_n').innerHTML=`최신 ${ts[ts.length-1]}년 — 전국 <b>${nat!=null?nat.toLocaleString():'—'}조원</b> · 수도권 비중 <b class="up">${lv!=null?lv.toFixed(1)+'%':'—'}</b> (2010년 집계 이후 추이) — 자산의 수도권 집중도`;
        }
        /* ⑥ 시도별 증가율 바차트 — 최신 연도 YoY 상위 8 */
        {const rows=[];
         for(const nm in M){ if(nm==='전국') continue; const a=M[nm];
           if(a.v.length>=2&&a.v[a.v.length-2]) rows.push([nm,(a.v[a.v.length-1]/a.v[a.v.length-2]-1)*100]); }
         rows.sort((x,y)=>y[1]-x[1]);
         const top=rows.slice(0,8);
         const cv=$('re_reg');
         if(cv&&top.length){ const W=cv.clientWidth||700,H=cv.clientHeight||230; cv.width=W;cv.height=H;
           const x=cv.getContext('2d'); x.clearRect(0,0,W,H);
           const mx=Math.max(...top.map(r=>Math.abs(r[1])))||1, bh=(H-16)/top.length;
           x.font='11px sans-serif';
           top.forEach((r,i)=>{ const y=8+i*bh, w=(W-140)*Math.abs(r[1])/mx;
             x.fillStyle=r[1]>=0?'#5cb85c':'#d9534f';
             x.fillRect(70,y+3,Math.max(2,w),bh-8);
             x.fillStyle='#555'; x.textAlign='right'; x.fillText(r[0],64,y+bh/2+3);
             x.textAlign='left'; x.fillText((r[1]>0?'+':'')+r[1].toFixed(1)+'%',74+w,y+bh/2+3); });
           x.textAlign='left';
           const yr=(M['전국']||{}).t.slice(-1)[0];
           $('re_reg_n').innerHTML=`${yr}년 전년 대비 증가율 상위 — 서울 독주 여부·지방 온기 확산을 한눈에`;}
        }
      }catch(e){}
    }).catch(e=>{ const el=$('re_asof'); if(el) el.textContent='데이터 로드 실패 — 수집 전이거나 서버 오류: '+e; loaded=false; });
  };
})();

/* ── (2026-08-01) 📐 선행 EPS·DDR5 vs KOSPI — 기사식 이중축 오버레이 (DB 탭) ── */
(function(){
  let loaded=false;
  const $=id=>document.getElementById(id);
  function dual(cvId, A, B){
    /* A(좌축)·B(우축) — {t:[YYYYMMDD|YYYY-MM-DD],v:[],label,color}. 날짜 문자열로 정렬·교집합 없이 A축 기준 배치 */
    const cv=$(cvId); if(!cv) return;
    const W=cv.clientWidth||700,H=cv.clientHeight||250; cv.width=W; cv.height=H;
    const x=cv.getContext('2d'); x.clearRect(0,0,W,H);
    const P={l:46,r:56,t:10,b:18};
    const norm=t=>String(t).replace(/-/g,'');
    const ts=[...new Set([...A.t.map(norm),...B.t.map(norm)])].sort();
    const N=ts.length; if(!N) return;
    const mapv=(S)=>{const m={}; S.t.forEach((t,i)=>m[norm(t)]=S.v[i]); return ts.map(t=>m[t]??null);};
    const av=mapv(A), bv=mapv(B);
    const rng=vs=>{const a=vs.filter(v=>v!=null); let lo=Math.min(...a),hi=Math.max(...a); const p=(hi-lo)*0.07||1; return [lo-p,hi+p];};
    const [al,ah]=rng(av),[bl,bh]=rng(bv);
    const X=i=>P.l+(W-P.l-P.r)*i/Math.max(1,N-1);
    const Ya=v=>P.t+(H-P.t-P.b)*(1-(v-al)/(ah-al)), Yb=v=>P.t+(H-P.t-P.b)*(1-(v-bl)/(bh-bl));
    x.font='10px sans-serif'; x.strokeStyle='#eceff3';
    for(let g=0;g<=4;g++){ const y=P.t+(H-P.t-P.b)*g/4;
      x.beginPath();x.moveTo(P.l,y);x.lineTo(W-P.r,y);x.stroke();
      x.fillStyle=A.color; x.textAlign='right'; x.fillText((ah-(ah-al)*g/4).toFixed(ah-al<10?1:0),P.l-4,y+3);
      x.fillStyle=B.color; x.textAlign='left'; x.fillText((bh-(bh-bl)*g/4).toFixed(0),W-P.r+4,y+3); }
    /* x축 눈금 — 구간 길이에 따라 연도/월 자동 (라벨 최소 46px 간격 보장) */
    x.textAlign='left'; x.fillStyle='#98a2ad';
    const spanY=(+ts[N-1].slice(0,4))-(+ts[0].slice(0,4));
    let lastK='', lastPx=-99;
    for(let i=0;i<N;i++){
      let key,lab;
      if(spanY>=4){ key=ts[i].slice(0,4); lab=key; }                                   // 연 단위: "1997"
      else { key=ts[i].slice(0,6); lab=`${ts[i].slice(2,4)}.${ts[i].slice(4,6)}`; }    // 월 단위: "26.08"
      if(key!==lastK){ lastK=key; const px=X(i);
        if(px-lastPx>=46){ lastPx=px;
          x.strokeStyle='#f0f2f5'; x.beginPath(); x.moveTo(px,P.t); x.lineTo(px,H-P.b); x.stroke();
          x.fillText(lab,px-(spanY>=4?12:10),H-4); } } }
    /* 수직 마커(옵션) — A.marks=[[YYYYMMDD,'라벨'],..] */
    (A.marks||[]).forEach(([d,lb])=>{ let i=ts.findIndex(t=>t>=String(d)); if(i<0) return;
      const px=X(i); x.strokeStyle='#c9ced6'; x.setLineDash([3,3]);
      x.beginPath(); x.moveTo(px,P.t); x.lineTo(px,H-P.b); x.stroke(); x.setLineDash([]);
      x.fillStyle='#98a2ad'; x.fillText(lb,px+3,P.t+18); x.fillStyle='#98a2ad'; });
    const draw=(vs,Y,col,w)=>{ x.strokeStyle=col; x.lineWidth=w; x.beginPath(); let st=false;
      for(let i=0;i<N;i++){ if(vs[i]==null) continue; st?x.lineTo(X(i),Y(vs[i])):(x.moveTo(X(i),Y(vs[i])),st=true); }
      x.stroke(); x.lineWidth=1; };
    draw(bv,Yb,B.color,1.4); draw(av,Ya,A.color,1.8);
    const leg=(t,c,dx)=>{ x.fillStyle=c; x.fillRect(P.l+dx,P.t+2,10,3); x.fillText(t,P.l+dx+13,P.t+7); };
    x.fillStyle='#555'; leg(A.label,A.color,4); leg(B.label,B.color,110);
  }
  window.renderVeps=function(){
    if(loaded) return; loaded=true;
    Promise.all([
      fetch('/api/db/fwd_eps').then(r=>r.ok?r.json():null).catch(()=>null),
      fetch('/api/db/series_mem_dram_spot').then(r=>r.ok?r.json():null).catch(()=>null),
      fetch('/api/db/margin_debt').then(r=>r.ok?r.json():null).catch(()=>null),
      fetch('/api/db/series_hy_oas').then(r=>r.ok?r.json():null).catch(()=>null)
    ]).then(([F,D,M,HY])=>{
      /* ⓪ 신용잔고 YoY vs S&P500 — FINRA 월간(1997~ 전기간), 기사 [표1] 재현 */
      if(M&&M.t&&M.t.length){
        const mt=M.t, my=M.yoy;
        dual('ve_mgn',{t:mt.map(x=>x+'-01'),v:my,label:'신용잔고 YoY%',color:'#c0392b',
                       marks:[['20000301','00.3'],['20071001','07.10'],['20211101','21.11']]},
                      {t:(M.spx.t||[]).map(x=>x+'-01'),v:(M.spx.v||[]).map(v=>Math.log(v)),label:'S&P500(로그)',color:'#888'});
        const i=M.t.length-1, cur=M.yoy[i], pk=Math.max(...M.yoy.slice(-24).filter(v=>v!=null));
        const turn=cur!=null&&pk!=null&&cur<pk-3;
        $('ve_mgn_n').innerHTML=`최신 <b>${M.t[i]}</b> — 잔고 <b>$${(M.debit[i]/1e6).toFixed(2)}조</b> · YoY <b class="${cur>=40?'dn':''}">${cur>0?'+':''}${cur}%</b> (최근 2년 고점 ${pk>0?'+':''}${pk}%)`+
          (turn?` → <b class="dn">고점 대비 꺾임 — 기사 로직상 과열 후 경계 구간(2000·2007·2021 패턴: 고점 후 0~9개월 선행)</b>`:` → 고점 경신·유지 중 — 과열 누적 관찰`)+
          ` · <span class="note">FINRA 월간(익월 하순 공표) · 1997~ 풀 히스토리 백필</span>`;
      }
      /* ⓪-2 하이일드 가산금리 vs S&P500(로그) — 기사 [표2] 재현 (1997~) */
      if(HY&&HY.data&&HY.data.length&&M&&M.spx){
        const hd=HY.data.filter((r,i)=>i%3===0||i===HY.data.length-1);   // 일별→3일 샘플(렌더 경량화)
        dual('ve_hy',{t:hd.map(r=>r[0]),v:hd.map(r=>r[1]),label:'HY 가산금리%',color:'#c0392b',
                      marks:[['20000301','00.3'],['20071001','07.10'],['20200201','20.2'],['20211201','21.12']]},
                     {t:(M.spx.t||[]).map(x=>x+'-01'),v:(M.spx.v||[]).map(v=>Math.log(v)),label:'S&P500(로그)',color:'#888'});
        const last=HY.data[HY.data.length-1], cur=last[1];
        const yr=HY.data.slice(-252).map(r=>r[1]), y_hi=Math.max(...yr);
        const lvl=cur<3.5?'<b class="up">낮은 수준에서 안정 — 완화적 금융환경(기사 결론과 동일)</b>'
                 :cur<5?'<b>보통 수준 — 중립</b>':'<b class="dn">급등 — 긴축적 금융환경, 신용 경계</b>';
        $('ve_hy_n').innerHTML=`최신 <b>${last[0]}</b> — 가산금리 <b>${cur}%p</b> (최근 1년 고점 ${y_hi}%p) → ${lvl}`+
          ` · <span class="note">과거 주가 고점(00.3·07.10·20.2·21.12) 전후 급등 동행 — 점선 마커 · FRED BAMLH0A0HYM2 일별 · 1997~ 풀 히스토리</span>`;
      }
      /* ① 선행이익 vs KOSPI — 누적 데이터 */
      if(F&&F.t&&F.t.length){
        dual('ve_eps',{t:F.t,v:F.e,label:'선행이익(조원)',color:'#c0392b'},
                      {t:F.t,v:F.kospi,label:'KOSPI',color:'#888'});
        const i=F.t.length-1;
        const dirE=F.e.length>=2?(F.e[i]>F.e[i-1]?'상향':F.e[i]<F.e[i-1]?'하향':'유지'):'—';
        const dirK=F.kospi.length>=2&&F.kospi[i]!=null&&F.kospi[i-1]!=null?(F.kospi[i]>F.kospi[i-1]?'상승':'하락'):'—';
        let verdict='';
        if(dirE==='상향'&&dirK==='하락') verdict=' → <b class="up">주가 조정 + 이익 상향 = 밸류 부담 해소 성격(기사 로직상 기회 신호)</b>';
        else if(dirE==='하향'&&dirK==='하락') verdict=' → <b class="dn">이익도 하향 = 실적 우려가 실체</b>';
        $('ve_eps_n').innerHTML=`최신 ${F.t[i]} — 선행이익 <b>${F.e[i]?.toLocaleString()}조</b>(${dirE}) · 선행PER <b>${F.fper[i]}</b> · KOSPI ${F.kospi[i]?.toLocaleString()??'—'}(${dirK}) · 표본 ${F.n[i]}종${verdict}`+
          `${F.t.length<15?` <span class="note">— 누적 ${F.t.length}일째(개시 2026-08-01) · 추세선은 수 주 축적 후 유의미</span>`:''}`;
      } else { $('ve_eps_n').textContent='수집 전 — 매일 16:20 누적 시작'; }
      /* ② DDR5 vs KOSPI — DDR5 시계열 + ECOS KOSPI 이력 */
      if(D&&D.data&&F&&F.kospi_hist){
        const key='DDR5 16Gb (2Gx8) 4800/5600';
        const dt=D.data.map(r=>r[0]), dv=D.data.map(r=>(r[1]||{})[key]??null);
        /* KOSPI 이력을 DDR5 수집 구간(-1주 여유)으로 잘라 오버레이 정합 — DDR5 이력이 쌓일수록 창이 자동 확장 */
        const d0=String(dt[0]||'').replace(/-/g,'');
        const ki=F.kospi_hist.t.findIndex(t=>t>=d0);
        const kh={t:F.kospi_hist.t.slice(Math.max(0,ki-5)), v:F.kospi_hist.v.slice(Math.max(0,ki-5))};
        dual('ve_ddr',{t:dt,v:dv,label:'DDR5 16Gb($)',color:'#c0392b'},
                      {t:kh.t,v:kh.v,label:'KOSPI',color:'#888'});
        const lv=dv.filter(v=>v!=null).slice(-1)[0], fv=dv.find(v=>v!=null);
        $('ve_ddr_n').innerHTML=`DDR5 16Gb 현물 <b>$${lv}</b> (수집 시작가 $${fv} 대비 ${fv?((lv/fv-1)*100).toFixed(1):'—'}%) — 반도체 실적의 최전선. KOSPI 조정에도 가격 강세 유지 여부가 기사 포인트`;
      }
    });
  };
})();


/* ══════════════════════════════════════════════════════════════════
   ① daily 조사 data (docx 1~8 · 부록B/C/D) · ③ AI 추론 (docx 9~12)
   /api/report 하나만 읽어 렌더 — LLM 호출 0회. 코인 차트만 /api/coin (Binance 프록시·1h 캐시).
   ══════════════════════════════════════════════════════════════════ */
fetch('/api/report').then(r=>r.json()).then(R=>{
  if(!R||!R.report_date) return;
  const E=t=>String(t??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
  const $$=i=>document.getElementById(i);
  const T=(id,head,rows)=>{const el=$$(id); if(!el)return;
    if(!rows||!rows.length){el.innerHTML=`<tr><td class="note">데이터 없음</td></tr>`;return;}
    el.innerHTML=`<tr>${head.map(h=>`<th>${h}</th>`).join('')}</tr>`+
      rows.map(r=>`<tr>${r.map(c=>`<td>${c}</td>`).join('')}</tr>`).join('');};
  const P=v=>(v==null||v==='')?'—':`<span class="${v>0?'up':(v<0?'dn':'note')}">${v>0?'+':''}${(+v).toFixed(2)}%</span>`;
  const N=v=>(v==null||v==='')?'—':(+v).toLocaleString(undefined,{maximumFractionDigits:2});
  const LK=(t,u)=>u?`<a href="${E(u)}" target="_blank" rel="noopener">${E(t)}</a>`:E(t);
  const M=R.markets||{}, C=R.commodities||{}, CR=R.crypto||{};
  // 추세 스파크라인 — docx 표의 '추세(1Y)' 열과 동일한 PNG (sync_server 가 /charts 로 업로드).
  // 아직 업로드 전이면 404 → onerror 로 조용히 숨긴다(레이아웃 안 깨짐).
  const SP=n=>n?`<img class="spk" src="/charts/spark_${n}.png" loading="lazy" alt=""
      onerror="this.style.display='none'">`:'';
  // (2026-07-17) 행에 chart 경로가 있으면 그걸 우선 사용 — 테마/반도체 표의 spark_etf_<빈값> 404 근본 수정
  const SPC=(r,fb)=>(r&&r.chart)?`<img class="spk" src="/${String(r.chart).replace(/^\//,'')}" loading="lazy" alt=""
      onerror="this.style.display='none'">`:SP(fb);
  // 비철금속(4.4) 행 심볼 추출 — 알려진 행은 스파크 파일명 직접 매핑, 그 외 선두 토큰/괄호 첫 티커
  const NF_MAP={'탄산리튬':'lithium','KODEX 2차전지산업':'kodex_batt','우라늄':'sruuf','HANARO 원자력iSelect':'hanaro_nuke','구리 선물':'copper','KODEX 구리선물':'kodex_copper'};
  const nfSym=x=>{ const nm=String((x&&x.name)||'');
    for(const k in NF_MAP) if(nm.startsWith(k)) return NF_MAP[k];
    let m=nm.match(/^([A-Za-z]{2,6})(?![A-Za-z])/); if(!m) m=nm.match(/\(([A-Za-z]{2,6})(?![A-Za-z])/);
    const s=(x&&(x.symbol||x.code))||(m&&m[1])||''; return s?String(s).toLowerCase():''; };

  $$('d_asof').innerHTML=`<b>기준 ${E(R.report_date)}</b> · ${E((R.metadata||{}).generated_at||'')}
    <span class="note">— 매 실행 새로 조사되는 값. DB로 누적하지 않는 그날의 스냅샷이다.</span>`;
  $$('nav_d').innerHTML=[['d1','1 뉴스'],['d317','3.1.7 M7'],['d3112','3.1.12 심리'],['d32','3.2 한국'],['d321','3.2.1 수급'],['d322','3.2.2 종목수급'],['d323','3.2.3 테마'],['d323s','반도체·AI 종목'],['d323e','반도체·AI ETF'],['s32','3.2.4·5 KRX브리프'],
    ['d33','3.3 미국'],['d331','3.3.1 美ETF'],['d34','3.4 아시아'],['d35','3.5 유럽'],['d36','3.6 북미·중남미'],['d37','3.7 호주·중동'],
    ['d41','4.1 에너지'],['d42','4.2 금속'],['d43','4.3 농산물'],['d44','4.4 비철금속'],['d5','5 환율'],['d7','7 증권사'],['d8','8 글로벌IB'],
    ['dB','부록B AI'],['dC','부록C 밸류체인'],['dD','부록D 관계도']]
    .map(([i,t])=>`<a href="#${i}" data-go2="${i}">${t}</a>`).join('');

  /* ── 1. Top News ── */
  $$('d_news').innerHTML=((R.news||{}).top_news||[]).map(n=>{
    const bad=/부정|▼/.test(n.impact||''), good=/긍정|강세|▲/.test(n.impact||'');
    return `<div class="nw"><div class="h"><span class="r">${n.rank}</span>${E(n.headline)}</div>
      <div class="s">${E(n.summary)}</div>
      <div class="f"><span class="${bad?'dn':(good?'up':'note')}" style="font-weight:600">${E(n.impact||'')}</span>
        <span class="note">·</span>${LK(n.source||'출처',n.source_url)}
        <span class="note">· ${E(n.published_date||'')}</span></div></div>`;}).join('');

  /* ── 2. 캘린더 ── */
  const EV=e=>[E(e.date),E(e.region||'—'),`<b>${E(e.event)}</b>`,
    `<span style="color:var(--warn)">${E(e.importance||'')}</span>`,
    `<span class="note">${E(e.expected_impact||'')}</span>`,LK(e.source||'—',e.source_url)];
  const EH=['날짜','지역','이벤트','중요도','예상 영향','출처'];
  // (2026-07-19) 2.1/2.2 = 서버 events_calendar DB 1순위(매일 05:45·16:05 자동), 실패 시 리포트분 폴백
  const _evFallback=()=>{ T('d_ev', EH, ((R.news||{}).events_calendar||[]).map(EV));
    T('d_evl',EH, ((R.news||{}).events_calendar_longterm||[]).map(EV)); };
  fetch('/api/db/events_calendar').then(r=>r.json()).then(ec=>{
    const today=new Date().toISOString().slice(0,10);
    // (2026-07-26) 빅테크는 2.3 전용 — 2.1 에서 제외(중복 표시 방지)
    const up=(ec.upcoming||[]).filter(e=>e.date>=today && e.region!=='빅테크'), lt=(ec.longterm||[]);
    if(up.length) T('d_ev', EH, up.map(EV)); else T('d_ev', EH, ((R.news||{}).events_calendar||[]).map(EV));
    if(lt.length) T('d_evl',EH, lt.map(EV)); else T('d_evl',EH, ((R.news||{}).events_calendar_longterm||[]).map(EV));
  }).catch(_evFallback);
  T('d_evb',['날짜','이벤트','중요도','예상 영향','출처'],((R.news||{}).bigtech_events||[]).map(e=>
    [E(e.date),`<b>${E(e.event)}</b>`,`<span style="color:var(--warn)">${E(e.importance||'')}</span>`,
     `<span class="note">${E(e.expected_impact||'')}</span>`,LK(e.source||'—',e.source_url)]));

  /* ── 3.1 주요지표 (DB 아닌 3종) ── */
  const FS=M.factset||{};
  const bullets=a=>Array.isArray(a)&&a.length?`<ul style="margin:6px 0 0 16px;padding:0">${a.map(x=>`<li style="margin:3px 0">${E(x)}</li>`).join('')}</ul>`:'';
  $$('d_fs').innerHTML = (FS.blog||FS.report) ? `
    ${FS.blog?`<div class="nw"><div class="h">${LK(FS.blog.title||'블로그',FS.blog.url)}</div>
      <div class="s">${E(FS.blog.summary||'')}${bullets(FS.blog.points)}</div>
      <div class="f note">${E(FS.blog.date||'')}</div></div>`:''}
    ${FS.report?`<div class="nw"><div class="h">${LK(FS.report.title||'Earnings Insight report',FS.report.url)}</div>
      <div class="s">${(function(fs){   // (2026-08-14) 스키마 드리프트 흡수 — 배열/{sections:[]}/문자열 모두 허용(.map 예외로 탭 전체가 죽던 버그)
        const arr = Array.isArray(fs) ? fs
          : (fs && Array.isArray(fs.sections)) ? fs.sections
          : (fs && typeof fs==='object') ? Object.entries(fs).map(([k,v])=>({section:k,points:Array.isArray(v)?v:[v]}))
          : (fs ? [{section:'',points:[String(fs)]}] : []);
        return arr.map(x=>`<div style="margin-top:8px"><b>${E(x.section||x.name||'')}</b>${bullets(x.points)}</div>`).join('');
      })(FS.report.full_summary)}</div>
      <div class="f note">${E(FS.report.date||'')} · 다음 발행 ${E(FS.report.next_date||'—')}</div></div>`:''}
    <div class="src">${LK('insight.factset.com/topic/earnings',FS.topic_url)} · 기준 ${E(FS.as_of||'—')}</div>`
    : '<div class="note">데이터 없음</div>';

  T('d_m7',['종목','현재가','52주','컨센서스','목표주가','상승여력','리비전','가이던스','신호'],
    ((M.m7_outlook||{}).rows||[]).map(r=>{
      const sg=String(r.signal||''), c=/긍정/.test(sg)?'up':(/위험|경계/.test(sg)?'dn':'note');
      return [`<b>${E(r.name||'')}</b> <span class="note">${E(r.ticker||'')}</span>`,
        `<span class="num">${N(r.price)}</span>`,
        `<span class="${String(r.chg52).startsWith('-')?'dn':'up'}">${E(r.chg52||'—')}</span>`,
        `${E(r.consensus||'—')}<br><span class="note">${E(r.consensus_detail||'')}</span>`,
        `<span class="num">${E(r.target||'—')}</span>`,
        `<span class="${String(r.upside).startsWith('-')?'dn':'up'}">${E(r.upside||'—')}</span>`,
        `${E(r.revision||'—')}<br><span class="note">${E(r.revision_detail||'')}</span>`,
        `<span class="note">${E(r.guidance||'')}</span>`,
        `<b class="${c}">${E(sg||'—')}</b>`];}));

  const SEN=((M.macro||{}).sentiment||{}).rows||[];
  const spkName=p=>String(p||'').replace(/^charts\/spark_/,'').replace(/\.png$/,'');
  T('d_sent',['지표','현재','1일','1주','1개월','3개월','6개월','1년','추세(1Y)','의미 · 활용'],SEN.map(r=>
    [`<b>${E(r.name||'')}</b>`,`<span class="num">${N(r.current??r.value)}</span>`,
     P(r['1d_pct']),P(r['1w_pct']),P(r['1mo_pct']),P(r['3mo_pct']),P(r['6mo_pct']),P(r['1y_pct']),
     SP(spkName(r.spark)),
     `<span class="note">${E(r.meaning||'')}${r.use?` — ${E(r.use)}`:''}</span>`]));

  /* ── 지수표 공통 ── */
  const NM={sp500:'S&P 500',nasdaq:'나스닥',dow:'다우',vix:'VIX',dxy:'달러인덱스',us10y:'미 10년물',
    nikkei:'닛케이225',shanghai:'상하이종합',hsi:'홍콩 항셍',taiwan:'대만 가권',sensex:'인도 센섹스',vietnam:'베트남(VNM)',
    stoxx50:'유로 스톡스 50',dax:'독일 DAX',ftse:'영국 FTSE100',kospi:'코스피',kosdaq:'코스닥'};
  const IH=['지수','현재','1일','1주','1개월','3개월','6개월','1년','추세(1Y)','추세 평가'];
  const idx=o=>Object.entries(o||{}).filter(([,v])=>v&&typeof v==='object'&&'current' in v)
    .map(([k,v])=>[`<b>${NM[k]||k}</b>`,`<span class="num">${N(v.current)}</span>`,
      P(v['1d_pct']??v.prev_pct),P(v['1w_pct']),P(v['1mo_pct']),
      P(v['3mo_pct']),P(v['6mo_pct']),P(v['1y_pct']),SP(k),`<span class="note">${E(v.trend||'')}</span>`]);
  T('d_kr',IH,idx(M.korea)); T('d_us',IH,idx(M.us_markets));
  T('d_as',IH,idx(M.asia_markets)); T('d_eu',IH,idx(M.europe_markets));

  /* ── 3.2 한국 상세 ── */
  { const _kc=document.getElementById('d_kinv');
    if(_kc && !document.getElementById('kr_candles')){
      const _div=document.createElement('div'); _div.id='kr_candles'; _div.style.cssText='grid-column:1/-1';
      _div.innerHTML=['kospi','kosdaq'].map(k=>`<a href="/charts/${k}_tech.png" target="_blank"><img src="/charts/${k}_tech.png" style="width:100%;max-width:860px;border:1px solid var(--line,#ddd);border-radius:6px;margin:6px 0" loading="lazy" alt="${k} 일봉 캔들·수급" onerror="this.parentElement.style.display='none'"></a>`).join('');
      _kc.parentElement.insertBefore(_div,_kc); } }
  const KI=M.korea_investors||{};
  $$('d_kinv').innerHTML=['kospi','kosdaq'].filter(k=>KI[k]).map(k=>{
    const v=KI[k];
    return `<div class="card"><div class="k" style="font-size:13px;color:var(--tx);font-weight:650">${k.toUpperCase()} <span class="note">${E(KI.asof||'')}</span></div>
      <div style="margin-top:8px;font-size:12.5px">
        <div class="fo"><span class="fl">지수</span><span class="fv">${N(v.level)}</span></div>
        <div class="fo"><span class="fl">외국인</span><span class="fv ${String(v.foreign).startsWith('-')?'dn':'up'}">${E(v.foreign)}</span></div>
        <div class="fo"><span class="fl">기관</span><span class="fv ${String(v.institution).startsWith('-')?'dn':'up'}">${E(v.institution)}</span></div>
        <div class="fo"><span class="fl">개인</span><span class="fv ${String(v.individual).startsWith('-')?'dn':'up'}">${E(v.individual)}</span></div>
        <div id="pg_${k}"></div>
      </div><div class="src">${E(v.comment||'')}</div></div>`;}).join('');
  renderProgram();                                     // 프로그램(차익·비차익)·등락종목 — 서버 실시간 (2026-08-02)
  async function renderProgram(){
    let P; try{ P=await (await fetch('/api/db/program_trading')).json(); }catch(e){ return; }
    const eok=v=>v==null?'—':`<span class="${v>0?'up':v<0?'dn':''}">${v>0?'+':''}${Math.round(v).toLocaleString()}억</span>`;
    ['kospi','kosdaq'].forEach(k=>{
      const el=document.getElementById('pg_'+k); if(!el||!P[k]||!(P[k].t||[]).length) return;
      const a=P[k], i=a.t.length-1, ud=(P.updown||{})[k];
      el.innerHTML=
        `<div class="fo"><span class="fl">프로그램 차익</span><span class="fv">${eok(a.arb[i])}</span></div>
         <div class="fo"><span class="fl">프로그램 비차익</span><span class="fv">${eok(a.nonarb[i])}</span></div>
         <div class="fo"><span class="fl">프로그램 전체</span><span class="fv">${eok(a.whole[i])}</span></div>`+
        (ud?`<div class="fo"><span class="fl">등락종목</span><span class="fv"><span class="up">상승 ${ud.up}</span> · 보합 ${ud.flat} · <span class="dn">하락 ${ud.down}</span>${ud.uplm?` · 상한 ${ud.uplm}`:''}${ud.lslm?` · 하한 ${ud.lslm}`:''}</span></div>`:'')+
        `<div class="note" style="margin-top:2px">프로그램 ${a.t[i].slice(4,6)}/${a.t[i].slice(6)} 종가(네이버·억원)${ud?` · 등락종목 ${E(P.updown_asof||'')} 기준(KIS)`:''} · <span style="color:#e08e3c;font-weight:700">차익</span>/<span style="color:#1f6feb;font-weight:700">비차익</span> 1년 추세는 위 캔들차트 하단 패널(같은 X축) 참조 — 차익=선물-현물 괴리 연계 기계적 수급(베이시스·외국인 선물과 함께), 비차익=기관 방향성 현물(규모·지속 시 지수 설명력↑)</div>`;
    });
  }

  const KS=M.korea_investor_stocks||{};
  const KSL={kospi_foreign_buy:'코스피 외국인 순매수',kospi_foreign_sell:'코스피 외국인 순매도',
    kospi_inst_buy:'코스피 기관 순매수',kospi_inst_sell:'코스피 기관 순매도',
    kosdaq_foreign_buy:'코스닥 외국인 순매수',kosdaq_foreign_sell:'코스닥 외국인 순매도',
    kosdaq_inst_buy:'코스닥 기관 순매수',kosdaq_inst_sell:'코스닥 기관 순매도'};
  $$('d_kstk').innerHTML=Object.entries(KSL).filter(([k])=>Array.isArray(KS[k])&&KS[k].length).map(([k,l])=>{
    const buy=/순매수/.test(l);
    return `<div class="card"><div class="k" style="font-size:12.5px;color:${buy?'var(--up)':'var(--dn)'};font-weight:650">${l}</div>
      <table style="border:none;margin-top:6px">${KS[k].map(x=>
        `<tr><td><b>${E(x.name)}</b></td><td class="note" style="text-align:right">${E(x.detail)}</td></tr>`).join('')}</table></div>`;}).join('');

  const TH=['테마','대표 ETF','현재','1일','1주','1개월','3개월','6개월','1년','추세(1Y)'];
  const TE=M.korea_theme_etfs||{};
  T('d_theme',TH,(M.korea_theme_rows||[]).map(r=>
    [`<b>${E(r.theme||'')}</b>`,`<span class="note">${E(TE[r.theme]||r.etf||'')}</span>`,
     `<span class="num">${N(r.current)}</span>`,P(r['1d_pct']),P(r['1w_pct']),P(r['1mo_pct']),P(r['3mo_pct']),
      P(r['6mo_pct']),P(r['1y_pct']),SPC(r,'etf_'+(r.code||r.symbol||''))]));
  $$('d_theme_c').innerHTML=E(M.korea_themes_comment||'');

  const SH=['종목','현재','1일','1주','1개월','3개월','6개월','1년','추세(1Y)','추세 평가'];
  const srow=r=>[`<b>${E(r.name||'')}</b> <span class="note">${E(r.code||r.symbol||'')}</span>`,
    `<span class="num">${N(r.current)}</span>`,P(r['1d_pct']),P(r['1w_pct']),P(r['1mo_pct']),P(r['3mo_pct']),
    P(r['6mo_pct']),P(r['1y_pct']),SPC(r,'etf_'+(r.code||r.symbol||'')),`<span class="note">${E(r.trend||'')}</span>`];
  T('d_semis',SH,(M.semi_ai_stocks||[]).map(srow));
  $$('d_semis_c').innerHTML=E(M.semi_ai_stocks_comment||'');
  T('d_semie',SH,(M.semi_ai_etfs||[]).map(srow));
  $$('d_semie_c').innerHTML=E(M.semi_ai_etfs_comment||'');

  /* ── ETF 그룹 렌더 (미국·아시아·유럽·북미·호주중동 공통) ── */
  const EGH=['종목','현재','1일','1주','1개월','3개월','6개월','1년','추세(1Y)','추세 평가'];
  const erow=(x,pfx='etf_')=>[`<b>${E(x.name||x.symbol)}</b> <span class="note">[${E(x.symbol||x.ticker||'-')}]</span>`+
      (x.desc?`<br><span class="note">${E(x.desc)}</span>`:''),
    `<span class="num">${N(x.current)}</span>`,P(x['1d_pct']),P(x['1w_pct']),P(x['1mo_pct']),
    P(x['3mo_pct']),P(x['6mo_pct']),P(x['1y_pct']),
    SP(pfx+(x.symbol||x.ticker||x.code||'')),`<span class="note">${E(x.trend||'')}</span>`];
  const etfGroups=(el,obj,labels)=>{
    const box=$$(el); if(!box||!obj){if(box)box.innerHTML='<div class="note">데이터 없음</div>';return;}
    let html='';
    Object.entries(obj).forEach(([k,v])=>{
      if(!Array.isArray(v)||!v.length) return;
      html+=`<div class="grp">${E(labels[k]||k)}</div><div class="box" style="overflow-x:auto"><table>
        <tr>${EGH.map(h=>`<th>${h}</th>`).join('')}</tr>
        ${v.map(x=>`<tr>${erow(x, el==='d_asetf'?'aetf_':'etf_').map(c=>`<td>${c}</td>`).join('')}</tr>`).join('')}</table></div>`;});
    if(obj.comment) html+=`<div class="lead" style="margin-top:12px">${E(obj.comment)}</div>`;
    if(obj.asof)    html+=`<div class="src">기준 ${E(obj.asof)}</div>`;
    box.innerHTML=html||'<div class="note">데이터 없음</div>';};

  etfGroups('d_usetf',M.us_etfs,{index:'지수',sector:'섹터',theme:'테마',defensive:'방어형',bond:'채권'});
  etfGroups('d_asetf',M.asia_etfs,{asia:'아시아',kr_listed:'한국 상장',us_listed:'미국 상장',country:'국가',theme:'테마'});
  etfGroups('d_euetf',M.europe_etfs,{items:'유럽 ETF',region:'지역',country:'국가',sector:'섹터',theme:'테마'});
  etfGroups('d_ametf',M.americas_etfs,{items:'북미·중남미 국가 ETF'});
  etfGroups('d_aumetf',M.aume_etfs,{items:'호주·중동 국가 ETF'});

  /* ── 3.3.2 리밸런싱 ── */
  const RB=(M.index_rebalance||{}).index_rebalance||M.index_rebalance||{};
  let rbh='';
  [['sp500','S&P 500'],['nasdaq100','나스닥 100']].forEach(([k,l])=>{
    const r=RB[k]; if(!r)return;
    rbh+=`<div class="grp">${l}</div>`;
    let ch=[...(r.additions||[]).map(x=>({...x,act:'편입'})),...(r.deletions||[]).map(x=>({...x,act:'편출'}))];
    (r.events||[]).forEach(ev=>{ if(ev&&typeof ev==='object'){
      (ev.add||ev.in||[]).forEach(x=>ch.push({...x,act:'편입',when:ev.title||ev.date||''}));
      (ev.remove||ev.out||[]).forEach(x=>ch.push({...x,act:'편출',when:ev.title||ev.date||''})); }});
    if(ch.length) rbh+=`<div class="box" style="overflow-x:auto"><table>
      <tr><th>구분</th><th>티커</th><th>회사명</th><th>사업 내용</th><th>사유</th><th>회차</th></tr>
      ${ch.map(x=>`<tr><td><b class="${x.act==='편입'?'up':'dn'}">${x.act}</b></td>
        <td><b>${E(x.ticker||x.symbol||'—')}</b></td><td>${E(x.name||'—')}</td>
        <td class="note">${E(x.biz||x.business||x.desc||'')}</td><td class="note">${E(x.reason||'')}</td><td class="note">${E(x.when||'')}</td></tr>`).join('')}</table></div>`;
    if(Array.isArray(r.schedule)&&r.schedule.length) rbh+=`<div class="lead" style="margin-top:10px">${r.schedule.map(x=>
      typeof x==='string'?`• ${E(x)}`:`• <b>${E(x.q||x.cycle||'-')}</b> — 발표 ${E(x.announce||'-')} · 적용 ${E(x.effective||'-')}${x.note?` <span class="note">(${E(x.note)})</span>`:''}`).join('<br>')}</div>`;});
  $$('d_rebal').innerHTML=rbh||'<div class="note">데이터 없음</div>';

  /* ── 4. 원자재 ── */
  // 명칭은 docx 와 동일한 정식 상품명·ETF명 (약칭 금지)
  const CN={wti:'WTI 원유',brent:'브렌트유',natgas:'천연가스',
    kodex_energy:'KODEX 미국S&P500에너지(합성)',kodex_aipower:'KODEX 미국AI전력핵심인프라',
    gold:'금',silver:'은',copper:'구리',platinum:'백금',
    corn:'옥수수',soybean:'대두',wheat:'소맥(밀)',sugar:'설탕',coffee:'커피',orange:'오렌지주스',
    crb:'CRB 상품지수 (프록시 ^TRCCRB)',bdi:'BDI 운임 (프록시 BDRY ETF)',
    dba:'Invesco DB Agriculture Fund (DBA)',de:'Deere & Company (DE)',ntr:'Nutrien Ltd. (NTR)'};
  const CD={wti:'NYMEX WTI 선물 최근월물 — 국제 유가 선도 지표',
    brent:'ICE 브렌트 선물 최근월물 — 유럽·아시아 기준 유종',
    natgas:'NYMEX 천연가스 선물 최근월물',
    kodex_energy:'전통 에너지(화석연료) · S&P500 에너지 섹터 합성 추종 (218420)',
    kodex_aipower:'넥스트 에너지(전력망·인프라) · 미국 AI 전력 핵심 인프라 (487230)'};
  const CH=['품목','현재','1일','1주','1개월','3개월','6개월','1년','추세(1Y)','추세 평가'];
  const crow=(o,skip=[])=>Object.entries(o||{})
    .filter(([k,v])=>v&&typeof v==='object'&&'current' in v&&!skip.includes(k))
    .map(([k,v])=>[`<b>${CN[k]||k}</b>${CD[k]?`<br><span class="note">${E(CD[k])}</span>`:''}`,
      `<span class="num">${N(v.current)}</span>`,P(v['1d_pct']??v.prev_pct),P(v['1w_pct']),P(v['1mo_pct']),
      P(v['3mo_pct']),P(v['6mo_pct']),P(v['1y_pct']),SP(k),`<span class="note">${E(v.trend||'')}</span>`]);
  T('d_c_en',CH,crow(C.energy));                    $$('d_c_en_c').innerHTML=E(C.energy_comment||'');
  T('d_c_me',CH,crow(C.metals,['rare_earth']));     $$('d_c_me_c').innerHTML=E(C.metals_comment||'');
  T('d_c_ag',CH,crow(C.agriculture));               $$('d_c_ag_c').innerHTML=E(C.agri_comment||'');
  /* (2026-08-14) FAO 세계 식량가격지수 — 종합+5개 구성. report_data 가 아니라 자체 수집분
     (fao_ffpi.json · 매월 첫째 주 갱신)이라 별도 fetch 로 그린다. */
  fetch('/api/db/fao_ffpi',{cache:'no-cache'}).then(r=>r.ok?r.json():null).then(f=>{
    if(!f||!f.snap) return;
    const el=$$('ffpi_asof'); if(el) el.textContent=`(${f.asof} 기준 · ${f.base})`;
    const PN=v=>v==null?'—':`<span class="${v>0?'up':(v<0?'dn':'note')}">${v>0?'+':''}${v}${'%'}</span>`;
    const t=$$('ffpi_t'); if(t) t.innerHTML='<tr><th>구성</th><th style="text-align:right">지수</th><th style="text-align:right">MoM(pt)</th><th style="text-align:right">YoY</th></tr>'+
      f.snap.map(x=>`<tr><td><b>${E(x.name)}</b></td><td class="num">${x.value}</td>
        <td class="num">${x.mom==null?'—':(x.mom>0?'+':'')+x.mom}</td><td class="num">${PN(x.yoy)}</td></tr>`).join('');
    /* 최근 10년 — 구성 6종 전부 + X(연도)·Y(지수) 눈금. 레전드는 SVG 밖(HTML)에 둔다
       (tspan 을 text 안에 넣었더니 렌더가 깨져 육류·유제품이 안 보이는 것처럼 보였다). */
    const ch=$$('ffpi_ch'); if(!ch) return;
    const sr=(f.series||[]).slice(-120), W=Math.max(560,(ch.clientWidth||620)-10), H=220, L=44, Bm=22;
    const picks=[[1,'종합','#16191d'],[2,'육류','#d64545'],[3,'유제품','#2f6fd0'],
                 [4,'곡물','#e08c1a'],[5,'유지류','#1e9e6a'],[6,'설탕','#8358c4']];
    const all=sr.flatMap(r=>picks.map(p=>r[p[0]])).filter(v=>v!=null);
    const lo=Math.floor(Math.min(...all)/20)*20, hi=Math.ceil(Math.max(...all)/20)*20;
    const X=i=>L+i/(sr.length-1)*(W-L-8), Y=v=>H-Bm-(v-lo)/(hi-lo)*(H-Bm-10);
    let g='';
    for(let v=lo;v<=hi;v+=20)                      /* Y 눈금 — 20pt 간격 */
      g+=`<line x1="${L}" y1="${Y(v)}" x2="${W-8}" y2="${Y(v)}" stroke="#eef0f3"/>`+
         `<text x="${L-5}" y="${Y(v)+3}" font-size="9.5" fill="#98a1ab" text-anchor="end">${v}</text>`;
    sr.forEach((r,i)=>{ if(/-01$/.test(r[0])&&+r[0].slice(0,4)%2===0)   /* X 눈금 — 짝수해 1월 */
      g+=`<line x1="${X(i)}" y1="${H-Bm}" x2="${X(i)}" y2="${H-Bm+3}" stroke="#c6ccd3"/>`+
         `<text x="${X(i)}" y="${H-6}" font-size="9.5" fill="#98a1ab" text-anchor="middle">${r[0].slice(0,4)}</text>`; });
    ch.innerHTML='<div style="font-size:11px;color:#667085;margin-bottom:3px">'+
      picks.map(p=>`<span style="color:${p[2]};font-weight:600">● ${p[1]}</span>`).join(' &nbsp;')+
      ` <span class="note">(${E(sr[0]?.[0]||'')} ~ ${E(sr[sr.length-1]?.[0]||'')} · 지수, 2014-2016=100)</span></div>`+
      `<svg width="${W}" height="${H}" style="display:block">${g}`+
      picks.map(p=>`<polyline fill="none" stroke="${p[2]}" stroke-width="${p[0]===1?2.2:1.4}" points="${sr.map((r,i)=>X(i).toFixed(1)+','+Y(r[p[0]]).toFixed(1)).join(' ')}"/>`).join('')+
      '</svg>';
  }).catch(()=>{});

  const NF=C.nonferrous||{};
  $$('d_c_nf').innerHTML=(NF.groups||[]).map(g=>`
    <div class="card" style="margin-bottom:12px">
      <div class="k" style="font-size:13px;color:var(--tx);font-weight:650">${E(g.title||'')}</div>
      <div class="s">${E(g.desc||'')}</div>
      ${g.core?`<div class="lead" style="margin:9px 0 0"><b>핵심 지표 — ${E(g.core)}</b><br>
        <span class="note">${E(g.core_desc||'')}</span></div>`:''}
      ${(()=>{const it=g.rows||g.items||[]; return it.length?`<div class="box" style="margin-top:9px;overflow-x:auto"><table>
        <tr>${['종목','현재','1일','1주','1개월','3개월','6개월','1년','추세(1Y)','추세 평가'].map(h=>`<th>${h}</th>`).join('')}</tr>
        ${it.map(x=>`<tr><td><b>${E(x.name||x.symbol||'')}</b> <span class="note">${E(x.symbol||x.code||'')}</span>
            ${x.desc?`<br><span class="note">${E(x.desc)}</span>`:''}</td>
          <td class="num">${N(x.current)}</td><td>${P(x['1d_pct']??x.prev_pct)}</td><td>${P(x['1w_pct'])}</td>
          <td>${P(x['1mo_pct'])}</td><td>${P(x['3mo_pct'])}</td><td>${P(x['6mo_pct'])}</td><td>${P(x['1y_pct'])}</td>
          <td>${SP(nfSym(x))}</td>
          <td class="note">${E(x.trend||'')}</td></tr>`).join('')}</table></div>`:'';})()}
    </div>`).join('') + (NF.comment?`<div class="lead">${E(NF.comment)}</div>`:'');

  /* ── 5. 환율 ── */
  const FN={usd_krw:'원/달러',eur_krw:'원/유로',jpy_krw:'원/엔(100)',cny_krw:'원/위안',hkd_krw:'원/홍콩달러',
    usd_eur:'달러/유로',usd_jpy:'달러/엔',usd_cny:'달러/위안'};
  const fxr=o=>Object.entries(o||{}).filter(([,v])=>v&&typeof v==='object'&&'current' in v)
    .map(([k,v])=>[`<b>${FN[k]||k}</b>`,`<span class="num">${N(v.current)}</span>`,
      P(v['1d_pct']??v.prev_pct),P(v['1w_pct']),P(v['1mo_pct']),
      P(v['3mo_pct']),P(v['6mo_pct']),P(v['1y_pct']),SP(k),`<span class="note">${E(v.trend||'')}</span>`]);
  const FH=['통화쌍','현재','1일','1주','1개월','3개월','6개월','1년','추세(1Y)','추세 평가'];
  T('d_fx',FH,fxr(M.fx_markets)); T('d_fxu',FH,fxr(M.fx_usd));

  /* ── 6. 크립토 ── (req9·10·11·19 2026-07-18)
     보고서 실행 시점 스냅샷 대신 서버 수집 DB 를 우선 사용 — '-' 가 생길 이유가 없다.
     crypto_overview(매시)·crypto_fng(1년 이력)·kimp_series(10분·1년 백필)·crypto_movers(각 10종목) */
  fetch('/api/db/crypto_overview').then(r=>r.json()).then(o=>{
    $$('d_cry').innerHTML=[
      ['총 시가총액',o.mcap_usd?('$'+(o.mcap_usd/1e12).toFixed(2)+'T'):'—',
        o.mcap_chg24!=null?`24h ${o.mcap_chg24>0?'+':''}${o.mcap_chg24.toFixed(2)}%`:''],
      ['24h 거래대금',o.vol24_usd?('$'+(o.vol24_usd/1e9).toFixed(0)+'B'):'—',`${N(o.coins||0)}개 코인`],
      ['BTC 도미넌스',o.btc_dom!=null?o.btc_dom.toFixed(1)+'%':'—',
        o.eth_dom!=null?('ETH '+o.eth_dom.toFixed(1)+'%'):''],
      ['갱신',E((o.as_of||'').slice(5)),'서버 매시 자동'],
    ].map(([k,v,s2])=>`<div class="card"><div class="k">${E(k)}</div><div class="v">${v}</div>
        <div class="s">${E(s2)}</div></div>`).join('');
  }).catch(()=>{});

  fetch('/api/db/crypto_fng').then(r=>r.json()).then(f=>{
    const now=f.now||{};
    // (req10) 설명이 없으면 '—' 꼬리를 붙이지 않는다
    $$('d_fg').innerHTML=`<b>${E(now.v??'—')} · ${E(now.label||'')}</b>`+
      `<span class="note"> (${E(now.date||'')} · alternative.me)</span>`;
    const h=f.hist||[];
    if(h.length&&window.Chart) new Chart($$('c_fng'),{type:'line',
      data:{labels:h.map(x=>x.date.slice(5)),datasets:[{data:h.map(x=>x.v),borderColor:'#e08c1a',
        borderWidth:1.6,pointRadius:0,tension:.15,fill:true,backgroundColor:'rgba(224,140,26,.08)'}]},
      options:{responsive:true,maintainAspectRatio:false,animation:false,plugins:{legend:{display:false}},
        scales:{x:{ticks:{maxTicksLimit:8,font:{size:9}},grid:{display:false}},
                y:{min:0,max:100,ticks:{stepSize:25,font:{size:9}}}}}});
  }).catch(()=>{});

  fetch('/api/db/kimp_series').then(r=>r.json()).then(km=>{
    const now=km.now||{}, S2=km.s||{}, order=['BTC','ETH','XRP','SOL'];
    T('d_kimchi',['코인','업비트 (원)','바이낸스 ($)','김프','판정'],order.filter(s2=>now[s2]).map(s2=>{
      const c=now[s2], p=c.pct;
      const st=p>2?'과열(한국 프리미엄 확대)':p>0.5?'소폭 프리미엄':p>-0.5?'중립':p>-2?'역프리미엄(해외가 더 비쌈)':'역프 과대';
      return [`<b>${s2}</b>`,`<span class="num">${N(c.krw)}</span>`,`<span class="num">${N(c.usd)}</span>`,
              P(p),`<span class="note">${st}</span>`];
    }));
    // (req19) 30D 김프 차트 — kimpwatda 30D 뷰와 같은 구간
    const cut=new Date(Date.now()-365*864e5).toISOString().slice(0,10);  // (2차 req31) 1년
    $$('d_kimp_charts').innerHTML=order.map(s2=>{
      const arr=(S2[s2]||[]).filter(x=>x[0]>=cut);
      const cur=arr.length?arr[arr.length-1][1]:null;
      return `<div class="cch"><div class="hd"><span class="sym">${s2} 김프 <span class="note">1Y</span></span>
        <span class="px ${cur>0?'up':'dn'}">${cur!=null?(cur>0?'+':'')+cur.toFixed(2)+'%':'—'}</span></div>
        <canvas id="kp_${s2}"></canvas>
        <div class="src">업비트÷(바이낸스×USD/KRW)−1 · 서버 10분 수집 (백필 구간은 일봉)</div></div>`;
    }).join('');
    if(window.Chart) order.forEach(s2=>{
      const arr=(S2[s2]||[]).filter(x=>x[0]>=cut); if(!arr.length) return;
      new Chart($$('kp_'+s2),{type:'line',
        data:{labels:arr.map(x=>x[0].slice(5,10)),datasets:[{data:arr.map(x=>x[1]),
          borderColor:'#d64545',borderWidth:1.5,pointRadius:0,tension:.1,fill:true,
          backgroundColor:'rgba(214,69,69,.07)'}]},
        options:{responsive:true,maintainAspectRatio:false,animation:false,plugins:{legend:{display:false}},
          scales:{x:{ticks:{maxTicksLimit:7,font:{size:9}},grid:{display:false}},
                  y:{ticks:{font:{size:9},callback:v=>Number(v).toFixed(2)+'%'}}}}});
    });
  }).catch(()=>{});

  fetch('/api/db/crypto_movers').then(r=>r.json()).then(mv=>{
    const gl=(arr,lab,cls)=>`<div class="card"><div class="k" style="font-size:12.5px;font-weight:650;color:var(--${cls})">${lab}</div>`+
      (Array.isArray(arr)&&arr.length?`<table style="border:none;margin-top:6px">
        <tr><th>코인</th><th style="text-align:right">가격($)</th><th style="text-align:right">24h</th><th style="text-align:right">거래대금</th></tr>${arr.map(x=>
        `<tr><td><b>${E(x.sym)}</b> <span class="note">${E((x.name||'').slice(0,14))}</span></td>
         <td class="num">${N(x.price)}</td><td class="num ${cls==='up'?'up':'dn'}">${P(x.chg24)}</td>
         <td class="num note">$${(x.vol/1e6).toFixed(0)}M</td></tr>`).join('')}</table>`
        :'<div class="note" style="margin-top:6px">수집 대기 중</div>')+'</div>';
    $$('d_gl').innerHTML=gl(mv.gainers,'24h Top Gainers (10)','up')+gl(mv.losers,'24h Top Losers (10)','dn');
  }).catch(()=>{});

  /* 6.2 코인 4종 1년 차트 (가격 + 거래량) — 서버 프록시가 Binance 를 1시간 캐시 */
  const SYMS=[['BTC','비트코인'],['ETH','이더리움'],['XRP','리플'],['SOL','솔라나']];
  $$('d_coins').innerHTML=SYMS.map(([s2,nm])=>
    `<div class="cch"><div class="hd"><span class="sym">${nm} <span class="note">${s2}/USDT</span></span>
      <span class="px" id="px_${s2}">…</span></div><canvas id="cc_${s2}"></canvas>
      <div class="src" id="sr_${s2}">Binance 일봉 1년 · 막대=거래대금</div></div>`).join('');
  SYMS.forEach(([s2])=>fetch('/api/coin/'+s2).then(r=>r.json()).then(d=>{
    const D=d.data||[]; if(!D.length||!window.Chart){$$('px_'+s2).textContent='—';return;}
    const last=D[D.length-1], first=D[0];
    const chg=(last.c/first.c-1)*100;
    $$('px_'+s2).innerHTML=`$${N(last.c)} <span class="${chg>0?'up':'dn'}" style="font-size:12px">${chg>0?'+':''}${chg.toFixed(1)}%</span>`;
    new Chart($$('cc_'+s2),{data:{labels:D.map(x=>new Date(x.t).toISOString().slice(5,10)),
      datasets:[
        {type:'bar',label:'거래대금',data:D.map(x=>x.v),yAxisID:'y2',backgroundColor:'rgba(148,163,184,.28)',borderWidth:0,order:2},
        {type:'line',label:'종가',data:D.map(x=>x.c),yAxisID:'y1',borderColor:'#e08c1a',borderWidth:1.8,
         pointRadius:0,tension:.1,fill:false,order:1}]},
      options:{responsive:true,maintainAspectRatio:false,animation:false,
        plugins:{legend:{display:false},tooltip:{mode:'index',intersect:false}},
        scales:{x:{ticks:{maxTicksLimit:6,font:{size:9}},grid:{display:false}},
                y1:{position:'left',ticks:{font:{size:9}}},
                y2:{position:'right',display:false,grid:{display:false}}}}});
  }).catch(()=>{$$('sr_'+s2).textContent='코인 시세 로드 실패 (네트워크 차단 가능)';}));

  /* ── 7·8. 리서치 ── */
  /* (2차 req8 2026-07-18) firms 가 securities.firm 아래 중첩 — 톱레벨만 뒤져 카드가 비던 버그.
     오늘의 메시지 + 하우스별 '시각'(strategy_view 등 *_view) + 대표리포트(제목·링크·날짜) 렌더 */
  const VIEWKO={strategy_view:'시황·투자전략 시각',global_strategy_view:'글로벌 전략 시각',asset_allocation_view:'자산배분 시각',
    etf_emerging_view:'ETF·신흥국 시각',derivatives_view:'파생·선물 시각',ib_china_view:'IB·중국 시각',
    global_etf_view:'글로벌 ETF 시각',sector_view:'섹터·반도체 시각',china_view:'중국·글로벌 시각',bond_view:'채권·매크로 시각',
    daily_view:'데일리 섹터 시각',industrial_view:'산업·방산 시각',house_view:'하우스 뷰'};
  const vtext=v=>typeof v==='string'?v:(v&&typeof v==='object'?(v.text||v.view||JSON.stringify(v)):String(v||''));
  /* (3차 2026-07-18) 본문 속 URL(https:// 또는 도메인/경로 꼴)을 클릭 가능한 링크로 — 이스케이프 후 치환이라 안전 */
  const LNK=t=>t.replace(/(https?:\/\/[^\s<)"']+|(?:[a-z0-9-]+\.)+(?:com|net|org|io)\/[^\s<,)"']+)/g,
    m2=>`<a href="${m2.startsWith('http')?m2:'https://'+m2}" target="_blank" rel="noopener">${m2}</a>`);
  const EL=v=>LNK(E(vtext(v)));
  /* (4차 2026-07-19) key_reports 링크 규칙 (사용자 지적 반영):
     ① rp.url(수집 시 저장한 텔레그램 퍼머링크·홈페이지 게시물 URL) 있으면 그대로 직행 링크
     ② 없으면 그 증권사의 '출처 채널'(텔레그램 채널 / NH·KB 공개 홈페이지)로 링크 — 웹에 없는
        내부 발간물이라도 최소한 출처로 연결. 검색해도 안 나오는 가짜 검색링크는 폐지. */
  const SRCCH={shinhan:'https://t.me/shinhanresearch',kiwoom:'https://t.me/KiwoomResearch',
    meritz:'https://t.me/meritz_research',hana:'https://t.me/HanaResearch',kyobo:'https://t.me/KyoboRSC',
    yuanta:'https://t.me/yuantaresearch',hyundai:'https://t.me/hmsecresearch',
    kb:'https://rc.kbsec.com/today/index.able',nh:'https://m.nhqv.com/research/boardList?rshPprDitCd=02',
    samsung:'https://www.samsungpop.com/mbw/research.do',miraeasset:'https://securities.miraeasset.com/bbs/board/message/list.do?categoryId=1521',
    korea_inv:'https://research.truefriend.com'};
  const houses=(obj,names,extras)=>{
    const src=(obj&&obj.firm&&typeof obj.firm==='object')?obj.firm:obj;
    return Object.entries(src||{}).filter(([k,v])=>names[k]&&v&&typeof v==='object')
    .map(([k,v])=>{
      const ch=SRCCH[k]||''; const tg=ch.includes('t.me');
      const views=Object.entries(v).filter(([kk,vv])=>VIEWKO[kk]&&vv)
        .map(([kk,vv])=>`<div class="s" style="margin-top:5px;color:#0f766e"><b>${VIEWKO[kk]}</b> — ${EL(vv)}</div>`).join('');
      const kr=(Array.isArray(v.key_reports)?v.key_reports:[]).slice(0,4)
        .map(rp=>{const u=rp.url||ch;
          return `<div class="s" style="margin-top:3px">📄 ${u?`<a href="${esc(u)}" target="_blank" rel="noopener">${E(rp.title||'')}</a>${rp.url?'':` <span class="note">${tg?'✈️채널':'↗출처'}</span>`}`:E(rp.title||'')}${rp.date?`<span class="note"> · ${E(rp.date)}</span>`:''}</div>`;}).join('');
      const reps=kr?`<div class="kr-fallback">${kr}</div>`:'';
      return `<div class="card"><div class="k" style="font-size:13px;color:var(--tx);font-weight:650">${E(names[k]||k)}</div>
      ${v.key_message?`<div class="s" style="margin-top:7px"><b>오늘의 메시지</b> — ${EL(v.key_message)}</div>`:''}
      ${views}${reps}
      ${(extras&&extras[k])||''}
      ${v.strength?`<div class="src">강점: ${E(v.strength)}</div>`:''}</div>`;}).join('');};
  /* (5차 2026-07-19 docx 신구조 미러) 7.1~7.6 핵심 6사만 풀 카드 — 기타 6사는 7.7 요약 표로 분리 */
  $$('d_sec').innerHTML=houses(R.securities,{kb:'KB증권',nh:'NH투자증권',samsung:'삼성증권',
    miraeasset:'미래에셋증권',korea_inv:'한국투자증권',meritz:'메리츠증권'});
  /* 7.7 기타 증권사 요약 (텔레그램 기반 6사) — 증권사명 아래 텔레그램 링크 */
  {const REST={shinhan:'신한투자증권',kiwoom:'키움증권',hana:'하나증권',kyobo:'교보증권',yuanta:'유안타증권',hyundai:'현대차증권'};
   const srcS=(R.securities&&R.securities.firm&&typeof R.securities.firm==='object')?R.securities.firm:(R.securities||{});
   const el=$$('d_sec_rest');
   if(el){ el.innerHTML=`<tr><th>증권사</th><th>핵심 메시지</th><th>시각 · 대표 리포트</th></tr>`+
     Object.entries(REST).map(([k,nm])=>{const v=srcS[k]||{}; const tg=SRCCH[k]||'';
       const vw=Object.entries(v).filter(([kk,vv])=>VIEWKO[kk]&&vv).map(([kk,vv])=>`<b>${VIEWKO[kk]}</b> — ${E(vtext(vv)).slice(0,140)}`).join('<br>');
       const rp=(Array.isArray(v.key_reports)&&v.key_reports[0])?('📄 '+E(String(v.key_reports[0].title||v.key_reports[0]||'').slice(0,50))):'';
       return `<tr><td style="white-space:nowrap"><b>${nm}</b><br><a href="${esc(tg)}" target="_blank" rel="noopener" class="note">✈️ ${E(tg.replace('https://',''))}</a></td>
         <td class="note">${E(vtext(v.key_message||'')).slice(0,220)||'—'}</td>
         <td class="note">${[vw,rp].filter(Boolean).join('<br>')||'—'}</td></tr>`;}).join(''); }}
  /* (4차 2026-07-18) 서버 수집 리포트를 위쪽 증권사 카드 스타일로 통합 —
     별도 '대표 리포트'·'네이버 모음' 섹션 폐지. 기존 카드(12사)엔 이어붙이고,
     보고서에 없는 증권사는 같은 스타일의 카드를 새로 만든다. */
  fetch('/api/db/broker_reports').then(r=>r.json()).then(br=>{
    const wrap=$$('d_sec'); if(!wrap||!Array.isArray(br.firms)) return;
    const byName={};
    wrap.querySelectorAll('.card > .k').forEach(k=>byName[k.textContent.trim()]=k.parentElement);
    const repHtml=f=>`<div class="s" style="margin-top:6px"><b>공식 리서치</b> — ${
        f.official?`<a href="${esc(f.official)}" target="_blank" rel="noopener">${E(f.broker)} 리서치 센터↗</a> · `:''}<a href="${esc(f.naver||'https://finance.naver.com/research/')}" target="_blank" rel="noopener">네이버 금융리서치↗</a></div>`+
      (f.reports||[]).slice(0,4).map(rp=>`<div class="s" style="margin-top:3px">📄 <a href="${esc(rp.url)}" target="_blank" rel="noopener">${E(rp.title)}</a>
        <span class="note">${E(rp.cat)}${rp.date?' · '+E(rp.date.slice(5)):''}</span>${
        rp.pdf?` <a href="${esc(rp.pdf)}" target="_blank" rel="noopener" class="note">[PDF]</a>`:''}</div>`).join('');
    /* (5차 2026-07-19) 핵심 6사 카드에만 서버 수집 리포트를 이어붙인다 —
       그 외 증권사 리포트는 7.8 네이버 금융리서치 모음 표에서 전부 보이므로 별도 카드 생성 폐지. */
    br.firms.forEach(f=>{
      const c=byName[f.broker];
      if(c){ c.insertAdjacentHTML('beforeend', repHtml(f)); }
    });
    /* (4차 2026-07-19) 링크 없는 리포트 제목 링크화 — 서버 수집분에서 제목 유사 매칭,
       못 찾으면 그 증권사 공식 리서치 페이지로 연결 */
    {const norm=t=>String(t||'').replace(/[\s\[\]()·\-–—:/,.]+/g,'').toLowerCase();
     const pool=[];
     br.firms.forEach(f=>(f.reports||[]).forEach(rp=>pool.push({b:f.broker,n:norm(rp.title),u:rp.url})));
     Object.entries(byName).forEach(([name,card])=>{
       const firm=br.firms.find(f=>f.broker===name);
       card.querySelectorAll('.rep-plain').forEach(sp=>{
         const n=norm(sp.textContent);
         if(!n) return;
         let hit=pool.find(x=>x.b===name&&(x.n.includes(n.slice(0,18))||n.includes(x.n.slice(0,18))));
         if(!hit) hit=pool.find(x=>x.n.includes(n.slice(0,14))||n.includes(x.n.slice(0,14)));
         const url=(hit&&hit.u)||(firm&&firm.official)||'';
         if(url){const a=document.createElement('a');a.href=url;a.target='_blank';a.rel='noopener';
           a.textContent=sp.textContent; sp.replaceWith(a);}
       });
     });}
    wrap.insertAdjacentHTML('beforeend',
      `<div class="note" style="grid-column:1/-1">🖥 ${E(br.desc||'')} · ${E(br.as_of||'')}</div>`);

    /* (5차 2026-07-19) 7.8 네이버 금융리서치 모음 — 최근 2일 · 테마별 표(제목·링크·작성사·작성일·요약) · 서버 자동 갱신 */
    const nv=$$('d_sec_nv');
    if(nv&&br.recent){
      nv.innerHTML=Object.entries(br.recent).filter(([,arr])=>arr&&arr.length).map(([cat,arr])=>
        `<h4 style="margin:14px 0 6px">${E(cat)} <span class="note">${arr.length}건</span></h4>
        <div class="box" style="overflow-x:auto"><table>
          <tr><th>작성일</th><th>작성사</th><th>제목${cat==='종목분석'||cat==='산업분석'?' · 대상':''}</th><th>간단요약</th><th></th></tr>
          ${arr.map(it=>`<tr><td class="note">${E((it.date||'').slice(5))}</td>
            <td>${E(it.broker)}</td>
            <td><a href="${esc(it.url)}" target="_blank" rel="noopener">${E(it.title)}</a>${it.stock?` <span class="note">${E(it.stock)}</span>`:''}</td>
            <td class="note">${E((it.summary||'').slice(0,80))}</td>
            <td style="width:40px;text-align:right">${it.pdf?`<a href="${esc(it.pdf)}" target="_blank" rel="noopener" class="note">PDF</a>`:''}</td></tr>`).join('')}
        </table></div>`).join('');
    }
  }).catch(()=>{});
  const CT=(R.securities||{}).common_themes;
  $$('d_sec_c').innerHTML=Array.isArray(CT)?CT.map(t=>`• ${E(typeof t==='string'?t:(t.theme||JSON.stringify(t)))}`).join('<br>'):E(CT||'');
  /* (3차) 리서치 센터 주소 — 각 IB 카드 안에 통합 (별도 '대표 발간물' 카드 폐지) */
  const IBP={ubs:[['House View · Investor Insights','https://www.ubs.com/global/en/wealthmanagement/insights.html']],
    goldman:[['Goldman Sachs Insights','https://www.goldmansachs.com/insights'],['GS Research (Briefings)','https://www.goldmansachs.com/insights/briefings']],
    jpmorgan:[['J.P. Morgan Global Research','https://www.jpmorgan.com/insights/global-research'],['Guide to the Markets','https://am.jpmorgan.com/us/en/asset-management/adv/insights/market-insights/guide-to-the-markets/']],
    morgan_stanley:[['Morgan Stanley Ideas & Insights','https://www.morganstanley.com/insights'],['Thoughts on the Market (팟캐스트)','https://www.morganstanley.com/ideas/thoughts-on-the-market']],
    blackrock:[['BlackRock Investment Institute','https://www.blackrock.com/corporate/insights/blackrock-investment-institute'],['Weekly Commentary','https://www.blackrock.com/us/individual/insights']]};
  const IBEX={};
  Object.entries(IBP).forEach(([k,ls])=>{
    const v=(R.global_securities||{})[k]||{};
    const pubs=(Array.isArray(v.rep_pubs)&&v.rep_pubs.length)?v.rep_pubs.map(pb=>[pb.title||pb.url,pb.url]):ls;
    IBEX[k]=`<div class="s" style="margin-top:7px"><b>리서치 센터 주소</b> — ${
      pubs.filter(([,u])=>u).map(([t,u])=>`<a href="${esc(u)}" target="_blank" rel="noopener">${E(t)}</a>`).join(' · ')}</div>`;});
  $$('d_gsec').innerHTML=houses(R.global_securities,{ubs:'UBS',goldman:'Goldman Sachs',jpmorgan:'J.P. Morgan',
    morgan_stanley:'Morgan Stanley',blackrock:'BlackRock'},IBEX);
  /* (req13 2026-07-18) IB 대표 발간물 + 링크 — 보고서 실행이 rep_pubs 를 채우면 표시.
     (IB 리서치는 로그인 장벽·비정형 포털이라 서버 자동수집 불가 — 보고서 조사 시 수집) */
  // (3차) d_gsec_pub 별도 카드 폐지 — 리서치 센터 주소를 각 IB 카드에 통합

  /* (2차 req14 2026-07-18) 8.6 과 8.7 을 docx처럼 분리 */
  const GC=(R.global_securities||{}).wall_street_consensus, GT=(R.global_securities||{}).common_themes;
  $$('d_gsec_c').innerHTML=Array.isArray(GT)?GT.map(t=>`• ${E(typeof t==='string'?t:JSON.stringify(t))}`).join('<br>'):E(GT||'—');
  {const w=$$('d_gsec_w');
   if(w) w.innerHTML=GC?(typeof GC==='string'?E(GC):Array.isArray(GC)?GC.map(t=>`• ${E(typeof t==='string'?t:JSON.stringify(t))}`).join('<br>'):Object.entries(GC).map(([k,v])=>`<b>${E(k)}</b> — ${E(typeof v==='string'?v:JSON.stringify(v))}`).join('<br>')):'—';}

  /* ── 부록B AI Trends ── */
  T('d_ai',['분류','내용'],((R.ai_trends||{}).items||[]).map(i=>
    typeof i==='string'?['—',E(i)]
    :[`<span class="pill p-ok">${E(i.tag||'—')}</span>`,
      `<b>${E(i.title||'')}</b><br><span class="note">${E(i.summary||'')}</span>`+
      (i.url?`<br><a href="${esc(i.url)}" target="_blank" rel="noopener" class="note">출처: ${E(i.source||i.url)}${i.date?' · '+E(i.date):''}</a>`:(i.source?`<br><span class="note">출처: ${E(i.source)}${i.date?' · '+E(i.date):''}</span>`:''))]));

  /* ── 부록C 밸류체인 개별종목 ── */
  const AC=M.appendix_c||{};
  $$('d_appc').innerHTML=(AC.groups||[]).map(g=>{
    const rows=(AC.rows||{})[g]||[]; if(!rows.length)return '';
    return `<div class="grp">${E(g)}</div><div class="box" style="overflow-x:auto"><table>
      <tr>${['종목','현재','1일','1주','1개월','3개월','1년','추세(1Y)','역할'].map(h=>`<th>${h}</th>`).join('')}</tr>
      ${rows.map(x=>`<tr>
        <td><b>${E(x.name||'')}</b> <span class="note">${E(x.symbol||x.code||'')}</span></td>
        <td class="num">${N(x.current)}</td><td>${P(x['1d_pct'])}</td><td>${P(x['1w_pct'])}</td>
        <td>${P(x['1mo_pct'])}</td><td>${P(x['3mo_pct'])}</td><td>${P(x['1y_pct'])}</td>
        <td>${SP('c_'+String(x.symbol||x.code||'').replace(/\./g,'_'))}</td>
        <td class="note">${E(x.desc||'')}</td></tr>`).join('')}</table></div>`;}).join('')
    + (AC.asof?`<div class="src">기준 ${E(AC.asof)}</div>`:'');

  /* ── 부록D 관계도 (정적 이미지 3장) ── */
  $$('d_appd').innerHTML=`<div class="appd">
    <img src="/img/appd_valuechain_1.png" alt="AI 반도체 밸류체인 관계도 1" loading="lazy">
    <img src="/img/appd_valuechain_2.png" alt="AI 반도체 밸류체인 관계도 2" loading="lazy">
    <img src="/img/appd_valuechain_3.png" alt="AI 반도체 밸류체인 관계도 3" loading="lazy">
    </div><div class="src">종목 구성이 바뀔 때만 갱신되는 정적 관계도 (부록C와 동일 46종).</div>`;

  /* ═══ ③ AI 추론 ═══ */
  const A=R.analysis||{};
  $$('a_asof').textContent=` — 기준 ${R.report_date}`;
  $$('nav_a').innerHTML=[['a9','9 종합분석'],['a10','10 자산별 견해'],['a11','11 포트폴리오'],['a12','12 액션']]
    .map(([i,t])=>`<a href="#${i}" data-go2="${i}">${t}</a>`).join('');
  $$('a_sum').innerHTML=E(A.summary||'—');
  $$('a_macro').innerHTML=E(A.macro_view||'—');
  T('a_theme',['테마','방향','코멘트'],(A.key_themes||[]).map(t=>{
    const up=/▲|상승|긍정/.test(t.direction||'');
    return [`<b>${E(t.theme)}</b>`,`<span class="${up?'up':'dn'}" style="font-weight:700">${E(t.direction||'')}</span>`,
      `<span class="note">${E(t.comment||'')}</span>`];}));
  T('a_risk',['#','리스크'],(A.key_risks||[]).map((r,i)=>[`<b>${i+1}</b>`,E(typeof r==='string'?r:JSON.stringify(r))]));
  const AN={us_equity:'미국 주식',kr_equity:'한국 주식',china_equity:'중국 주식',japan_equity:'일본 주식',
    em_equity:'신흥국 주식',europe_equity:'유럽 주식',kr_treasury:'한국 국채',us_treasury:'미국 국채',
    gold:'금',oil:'원유',btc:'비트코인'};
  T('a_asset',['자산','단·중·장기 견해'],Object.entries(A.asset_view||{}).map(([k,v])=>[`<b>${AN[k]||k}</b>`,E(v)]));
  const PC=['#2f6fd0','#1e9e6a','#e08c1a','#d64545','#8b5cf6','#0ea5e9','#94a3b8','#f472b6'];
  $$('a_pf').innerHTML=Object.entries(A.portfolios||{}).map(([k,p])=>{
    const al=p.allocation||[];
    return `<div class="pf"><div class="t">${E(p.label||k)}</div>
      <div class="bar">${al.map((x,i)=>`<div style="width:${x.weight_pct}%;background:${PC[i%PC.length]}" title="${E(x.asset)} ${x.weight_pct}%"></div>`).join('')}</div>
      <table style="border:none;margin-top:4px"><tr><th>자산</th><th style="text-align:right">비중</th><th>수단</th></tr>
      ${al.map((x,i)=>`<tr><td><span style="display:inline-block;width:8px;height:8px;border-radius:2px;background:${PC[i%PC.length]};margin-right:6px"></span>${E(x.asset)}</td>
        <td class="num">${x.weight_pct}%</td><td class="note">${E(x.vehicle||'')}</td></tr>`).join('')}</table>
      <div class="src" style="margin-top:9px">기대수익 <b>${E(p.expected_return||'—')}</b> · 최대낙폭 <b>${E(p.max_drawdown||'—')}</b> · 리밸런싱 ${E(p.rebalance||'—')}<br>${E(p.basis||'')}</div></div>`;}).join('');
  /* (req15·16 2026-07-18) action_items 는 {short_term:[],mid_term:[],long_term:[]} 사전 —
     리스트로 가정해 아무것도 안 그려지던 것을 고침. 13장 주의사항도 함께 렌더 */
  {const ai=A.action_items||{};
   const rows=Array.isArray(ai)
     ? ai.map(t=>{const m2=String(t).match(/^\[(.+?)\]\s*(.*)$/); return m2?[`<b>${E(m2[1])}</b>`,E(m2[2])]:['—',E(t)];})
     : [['<b>단기</b>','short_term'],['<b>중기</b>','mid_term'],['<b>장기</b>','long_term']]
        .flatMap(([lab,k])=>((ai[k]||[]).map((t,i)=>[i===0?lab:'',E(t)])));
   T('a_act',['구분','액션'],rows);}
  {const dc=(A.meta||{}).disclaimer, el=$$('a_disc');
   if(el) el.innerHTML=(dc?E(dc)+'<br><br>':'')+
     '<b>출처</b> — 시세·지표: 네이버증권 · Yahoo Finance · FRED · KRX · CoinGecko · Upbit/Binance · alternative.me / '+
     '리서치 요약: 각 증권사·IB 공개 발간물 / 자체 수집: 서버 DB (DB data 탭에서 원본 확인 가능)';}

  document.querySelectorAll('nav a[data-go2]').forEach(a=>a.addEventListener('click',e=>{
    const el=document.getElementById(a.dataset.go2);
    if(el){e.preventDefault(); el.scrollIntoView({behavior:'smooth',block:'start'});}}));
}).catch(e=>{const d=document.getElementById('d_asof'); if(d)d.textContent='report_data 로드 실패: '+e.message;});

/* ══════════════════════════════════════════════════════════════════
   SCREENER (2026-07-15) — 인터랙티브 필터.
   /api/db/screener_pool (전종목·필드) 를 지연로드 → 클라이언트가 6필터로 실시간 필터링.
   각 필터 = 프리셋 선택 + 직접 min/max 입력. 기본값 = 표준 1단계 하드컷.
   ══════════════════════════════════════════════════════════════════ */
(function(){
  const $=i=>document.getElementById(i);
  const E=t=>String(t??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
  const nowY=new Date().getFullYear();
  const wonF=v=>v==null?'—':(v>=1e12?(v/1e12).toFixed(v>=1e13?0:2)+'조':(v>=1e8?Math.round(v/1e8).toLocaleString()+'억':Math.round(v).toLocaleString()));
  const usdF=v=>v==null?'—':(v>=1e9?'$'+(v/1e9).toFixed(v>=1e10?0:1)+'B':(v>=1e6?'$'+(v/1e6).toFixed(0)+'M':'$'+Math.round(v).toLocaleString()));

  /* (2026-07-21) MACD 표기 명확화.
     저장값의 화살표는 '방향'이 아니라 MACD 가 0선 위(↑)냐 아래(↓)냐를 뜻한다.
       골든↑ = 골든크로스 + 0선 위 · 골든↓ = 골든크로스 + 0선 아래 …
     그런데 화살표가 방향으로 읽혀 '골든↓인데 상승 전환?' 이라는 혼동을 낳았다.
     서버 수집값(screener_pool·intraday_kr/us)은 그대로 두고 화면 표기만 풀어 쓴다. */
  const MACD_DISP={'골든↑':'골든(0선↑)','골든↓':'골든(0선↓)','데드↑':'데드(0선↑)','데드↓':'데드(0선↓)'};
  const dispOpt=(f,v)=>((f&&f.disp&&f.disp[v])||v);

  const DEF={
    kr:{
      mk:{label:'시장',cat:1},
      krx:{label:'KRX 업종',cat:1},
      wics2:{label:'WICS 세부',cat:1},
      wics:{label:'WICS 섹터',cat:1},
      chg:{label:'등락',fmt:v=>v.toFixed(1)+'%',presets:[['전체',null,null],['상승(0% ↑)',0,null],['+3% ↑',3,null],['하락(0% ↓)',null,0],['−3% ↓',null,-3]],def:[null,null]},
      cap:{label:'시가총액',fmt:wonF,presets:[['전체',null,null],['10조 ↑',1e13,null],['1~10조',1e12,1e13],['3,000억~1조',3e11,1e12],['1,000억~3,000억',1e11,3e11],['1,000억 ↓',null,1e11]],def:[3e11,null]},
      tv:{label:'거래대금',fmt:wonF,min:1,presets:[['전체',null],['100억 ↑',1e10],['30억 ↑',3e9],['10억 ↑',1e9],['1억 ↑',1e8]],def:[3e9,null]},
      px:{label:'가격',fmt:wonF,min:1,presets:[['전체',null],['1,000원 ↑',1000],['5,000원 ↑',5000],['1만원 ↑',10000]],def:[1000,null]},
      age:{label:'상장기간',fmt:v=>v+'년',min:1,presets:[['전체',null],['1년 ↑',1],['3년 ↑',3],['5년 ↑',5],['10년 ↑',10]],def:[1,null]},
      sec:{label:'증권 구분',fixed:'보통주만'},
      opLoss:{label:'영업적자',exclGE:1,maxOnly:1,fmt:v=>v.toFixed(0)+'년이상 제외',presets:[['전체',null,null],['1년이상 제외',null,1],['2년이상 제외',null,2],['3년이상 제외',null,3]],def:[null,3]},
      de:{label:'부채비율',fmt:v=>v.toFixed(0)+'%',fin:1,presets:[['전체',null,null],['100% ↓',null,100],['200% ↓',null,200],['300% ↓',null,300]],def:[null,300]},
      cr:{label:'유동비율',fmt:v=>v.toFixed(1),min:1,fin:1,presets:[['전체',null],['0.8 ↑',0.8],['1.0 ↑',1.0],['1.5 ↑',1.5]],def:[0.8,null]},
      upside:{label:'상승여력',fmt:v=>v.toFixed(0)+'%',min:1,reqData:1,presets:[['전체',null],['0% ↑',0],['10% ↑',10],['20% ↑',20],['50% ↑',50]],def:[null,null]},
      rec:{label:'투자의견',fmt:v=>'매수강도 '+v.toFixed(0),min:1,reqData:1,presets:[['전체',null],['매수 이상',65],['강력매수',85]],def:[null,null]},
      /* (2026-08-09 재편) 리비전 계열을 2쌍으로 통일 — ③영업익추정 30/90일 · ④목표주가 30/90일.
         기존 '리비전'(목표주가 90일)과 '목표주가' 토글은 ④와 중복이라 제거(사용자 요청). */
      rev:{label:'리비전(구)',fixed:'— 목표주가 리비전 90일로 통일'},
      nan:{label:'애널수',fixed:'— (KR 미제공)'},
      cov:{label:'목표주가(구)',fixed:'— 목표주가 리비전 30·90일로 통일'},
      per:{label:'PER',fmt:v=>v.toFixed(1)+'배',presets:[['전체',null,null],['10배 ↓',null,10],['15배 ↓',null,15],['20배 ↓',null,20]],def:[null,null]},
      pbr:{label:'PBR',fmt:v=>v.toFixed(1)+'배',presets:[['전체',null,null],['1배 ↓',null,1],['2배 ↓',null,2],['3배 ↓',null,3]],def:[null,null]},
      divy:{label:'배당',fmt:v=>v.toFixed(1)+'%',min:1,presets:[['전체',null],['1% ↑',1],['2% ↑',2],['3% ↑',3]],def:[null,null]},
      grw:{label:'성장',fmt:v=>v.toFixed(0)+'%',min:1,presets:[['전체',null],['0% ↑',0],['10% ↑',10],['20% ↑',20],['50% ↑',50]],def:[null,null]},
      mom:{label:'수익률 12M',fmt:v=>v.toFixed(0)+'%',presets:[['전체',null,null],['0% ↑',0,null],['50% ↑',50,null],['100% ↑',100,null],['0% ↓(하락)',null,0],['-30% ↓',null,-30]],def:[null,null]},
      r1m:{label:'수익률 1M',fmt:v=>(v>=0?'+':'')+v.toFixed(0)+'%',reqData:1,presets:[['전체',null,null],['0% ↑',0,null],['10% ↑',10,null],['20% ↑',20,null],['0% ↓(하락)',null,0],['-10% ↓',null,-10]],def:[null,null]},
      r3m:{label:'수익률 3M',fmt:v=>(v>=0?'+':'')+v.toFixed(0)+'%',reqData:1,presets:[['전체',null,null],['0% ↑',0,null],['20% ↑',20,null],['50% ↑',50,null],['0% ↓(하락)',null,0],['-20% ↓',null,-20]],def:[null,null]},
      r6m:{label:'수익률 6M',fmt:v=>(v>=0?'+':'')+v.toFixed(0)+'%',reqData:1,presets:[['전체',null,null],['0% ↑',0,null],['30% ↑',30,null],['100% ↑',100,null],['0% ↓(하락)',null,0],['-30% ↓',null,-30]],def:[null,null]},
      vol20:{label:'변동성(20일)',fmt:v=>v.toFixed(1)+'%',reqData:1,presets:[['전체',null,null],['2% ↓(안정)',null,2],['3% ↓',null,3],['5% ↑(고변동)',5,null]],def:[null,null]},
      hi:{label:'고점比',fmt:v=>'고점 '+v.toFixed(0)+'%',presets:[['전체',null,null],['-10% 이내',-10,null],['-20% 이내',-20,null],['-30% ↓(낙폭 큼)',null,-30],['-50% ↓',null,-50]],def:[null,null]},
      v200:{label:'200일선',fmt:v=>(v>=0?'+':'')+v.toFixed(0)+'%',min:1,presets:[['전체',null],['−30% ↑',-30],['−20% ↑',-20],['−10% ↑',-10],['위(0%) ↑',0],['+10% ↑',10],['+20% ↑',20]],def:[-30,null]},
      v20:{label:'20일선',fmt:v=>(v>=0?'+':'')+v.toFixed(0)+'%',min:1,reqData:1,presets:[['전체',null],['위(0%) ↑',0],['−5% ↑',-5],['+5% ↑',5]],def:[null,null]},
      v50:{label:'50일선',fmt:v=>(v>=0?'+':'')+v.toFixed(0)+'%',min:1,reqData:1,presets:[['전체',null],['위(0%) ↑',0],['−10% ↑',-10],['+10% ↑',10]],def:[null,null]},
      align:{label:'이평배열',cat:1,opts:['정배열','역배열','혼조'],hint:{'정배열':['up','상승 추세'],'역배열':['dn','하락 추세'],'혼조':['neu','전환 구간']}},
      rsi:{label:'RSI(14)',fmt:v=>'RSI '+v.toFixed(0),reqData:1,presets:[['전체',null,null],['과매도(≤30)',null,30],['30~50',30,50],['50 ↑(모멘텀)',50,null],['과매수 제외(≤70)',null,70],['과매수(≥70)',70,null]],def:[null,null]},
      /* (2026-07-21) ADX(14) — 추세의 '강도'. RSI(과열도)·MACD(방향)와 축이 달라 겹치지 않는다.
         25↑ 추세장 · 20↓ 횡보장. 이평 크로스·모멘텀 전략이 횡보장에서 깨지는 걸 걸러내는 용도.
         한국만 제공 — 미국은 Yahoo 일괄조회가 종가만 줘서 고가·저가가 없어 산출 불가. */
      adx:{label:'ADX(14)',fmt:v=>'ADX '+v.toFixed(0),min:1,reqData:1,presets:[['전체',null],['20 ↑(추세 시작)',20],['25 ↑(추세장)',25],['40 ↑(강한 추세)',40]],def:[null,null]},
      volx:{label:'거래량배수',fmt:v=>v.toFixed(1)+'배',min:1,reqData:1,presets:[['전체',null],['1.5배 ↑',1.5],['2배 ↑',2],['3배 ↑',3]],def:[null,null]},
      turn:{label:'회전율',fmt:v=>v.toFixed(2)+'%',min:1,reqData:1,presets:[['전체',null],['0.1% ↑',0.1],['0.5% ↑',0.5],['1% ↑',1]],def:[null,null]},
      macd:{label:'MACD',cat:1,opts:['골든↑','골든↓','데드↑','데드↓'],disp:MACD_DISP,hint:{'골든↑':['up','강한 상승'],'골든↓':['up','상승 전환'],'데드↑':['dn','하락 전환'],'데드↓':['dn','강한 하락']}},
      bb:{label:'볼린저밴드',fmt:v=>'%b '+v.toFixed(0),reqData:1,presets:[['전체',null,null],['하단권(≤20)',null,20],['중심 위(≥50)',50,null],['상단권(≥80)',80,null],['상단 돌파(≥100)',100,null]],def:[null,null]},
      roe:{label:'ROE',fmt:v=>v.toFixed(0)+'%',min:1,reqData:1,presets:[['전체',null],['5% ↑',5],['10% ↑',10],['15% ↑',15],['20% ↑',20]],def:[null,null]},
      mgrw:{label:'매출성장',fmt:v=>v.toFixed(0)+'%',reqData:1,presets:[['전체',null,null],['0% ↑',0,null],['10% ↑',10,null],['20% ↑',20,null],['부진(0% ↓)',null,0]],def:[null,null]},
      ogrw:{label:'이익성장',fmt:v=>v.toFixed(0)+'%',reqData:1,presets:[['전체',null,null],['0% ↑',0,null],['20% ↑',20,null],['100% ↑',100,null],['부진(0% ↓)',null,0],['-30% ↓',null,-30]],def:[null,null]},
      gacc:{label:'성장가속',fmt:v=>(v>=0?'+':'')+v.toFixed(0)+'%p',reqData:1,presets:[['전체',null,null],['가속 전환(0%p ↑)',0,null],['+10%p ↑',10,null],['+30%p ↑',30,null],['둔화(0%p ↓)',null,0]],def:[null,null]},
      qtoby:{label:'분기흑자YoY',tgl:1,def:false,tglLabel:'전년동기 적자→당분기 흑자 전환만 (계절성 안전)'},
      qtobq:{label:'분기흑자QoQ',tgl:1,def:false,tglLabel:'직전분기 적자→당분기 흑자 전환만 (가장 빠름·계절성 주의)'},
      opmch:{label:'마진변화',fmt:v=>(v>=0?'+':'')+v.toFixed(1)+'%p',reqData:1,presets:[['전체',null,null],['개선(0%p ↑)',0,null],['+3%p ↑',3,null],['+10%p ↑',10,null],['악화(0%p ↓)',null,0]],def:[null,null]},
      tob:{label:'흑자전환',tgl:1,def:false,tglLabel:'적자→흑자 전환 종목만'},
      opm:{label:'영업이익률',fmt:v=>v.toFixed(0)+'%',min:1,reqData:1,presets:[['전체',null],['0% ↑',0],['5% ↑',5],['10% ↑',10],['20% ↑',20]],def:[null,null]},
      peg:{label:'PEG',fmt:v=>v.toFixed(1),reqData:1,presets:[['전체',null,null],['1 ↓',null,1],['1.5 ↓',null,1.5],['2 ↓',null,2]],def:[null,null]},
      psr:{label:'PSR',fmt:v=>v.toFixed(1)+'배',reqData:1,presets:[['전체',null,null],['1배 ↓',null,1],['3배 ↓',null,3],['5배 ↓',null,5]],def:[null,null]},
      fnb20:{label:'외인수급(20일)',fmt:v=>(v>0?'+':'')+Math.round(v).toLocaleString()+'억',reqData:1,presets:[['전체',null,null],['순매수(0 ↑)',0,null],['100억 ↑',100,null],['500억 ↑',500,null],['순매도(0 ↓)',null,0]],def:[null,null]},
      onb20:{label:'기관수급(20일)',fmt:v=>(v>0?'+':'')+Math.round(v).toLocaleString()+'억',reqData:1,presets:[['전체',null,null],['순매수(0 ↑)',0,null],['100억 ↑',100,null],['500억 ↑',500,null],['순매도(0 ↓)',null,0]],def:[null,null]},
      fst:{label:'외인연속매수',fmt:v=>v.toFixed(0)+'일 ↑',min:1,reqData:1,presets:[['전체',null],['3일 ↑',3],['5일 ↑',5],['10일 ↑',10]],def:[null,null]},
      ost:{label:'기관연속매수',fmt:v=>v.toFixed(0)+'일 ↑',min:1,reqData:1,presets:[['전체',null],['3일 ↑',3],['5일 ↑',5],['10일 ↑',10]],def:[null,null]},
      sr:{label:'공매도비중',fmt:v=>v.toFixed(1)+'%',reqData:1,presets:[['전체',null,null],['1% ↓(약함)',null,1],['3% ↓',null,3],['5% ↑(과열)',5,null],['10% ↑',10,null]],def:[null,null]},
      lbr:{label:'대차잔고비율',fmt:v=>v.toFixed(1)+'%',reqData:1,presets:[['전체',null,null],['5% ↓',null,5],['10% ↓',null,10],['10% ↑(부담)',10,null],['20% ↑',20,null]],def:[null,null]},
      srf:{label:'공매도잔량비율',fixed:'— (US 전용 — KR은 공매도비중·대차잔고 사용)'},
      scov:{label:'커버일수',fixed:'— (US 전용)'},
      inst:{label:'기관보유비중',fixed:'— (US 전용 — KR은 외인보유비중 사용)'},
      drvj:{label:'파생·수급판정',fmt:v=>(v>0?'+':'')+parseFloat(v.toFixed(2))+'점',reqData:1,presets:[['전체',null,null],['강세(+1점 ↑)',1,null],['+0.5점 ↑',0.5,null],['약세(−1점 ↓)',null,-1],['−0.5점 ↓',null,-0.5]],def:[null,null]},
      ern:{label:'어닝일(D±)',fmt:v=>(v<0?'D+'+(-v).toFixed(0):'D-'+v.toFixed(0)),reqData:1,
        presets:[['전체',null,null],['D-7 이내',0,7],['D-14 이내',0,14],['D-30 이내',0,30],
                 ['발표 후 D+1~D+7',-7,-1],['발표 전후 ±7일',-7,7]],def:[null,null]},   // (2026-08-04) 음수=발표 지남(사후 추적)
      frgn:{label:'외인보유비중',fmt:v=>v.toFixed(0)+'%',min:1,reqData:1,presets:[['전체',null],['10% ↑',10],['30% ↑',30],['50% ↑',50]],def:[null,null]},
      frgn4w:{label:'외인지분율 4주변화',fmt:v=>(v>=0?'+':'')+v.toFixed(2)+'%p',reqData:1,presets:[['전체',null,null],['상승(0%p ↑)',0,null],['+0.3%p ↑',0.3,null],['+1%p ↑',1,null],['하락(0%p ↓)',null,0]],def:[null,null]},   // (2026-08-05) 네이버 일별 보유율 실측 Δ
      payout:{label:'배당성향',fmt:v=>v.toFixed(0)+'%',min:1,reqData:1,presets:[['전체',null],['10% ↑',10],['30% ↑',30],['50% ↑',50]],def:[null,null]},
      dinc:{label:'DPS 연속증가',fmt:v=>v.toFixed(0)+'년 연속↑',min:1,reqData:1,presets:[['전체',null],['1년 ↑',1],['2년 ↑',2],['3년 ↑',3]],def:[null,null]},   // (2026-08-06) DART 배당공시 5개년
      dgy:{label:'배당성장연수',fixed:'— (KR은 DPS 연속증가 사용)'},
      dcyc:{label:'배당주기',fixed:'— (US 전용 — KR은 연말 일괄 배당)'},
      mdd5:{label:'최대낙폭 5Y',fixed:'— (US 전용)'},
      /* (2026-08-09) 실적발표 이벤트 — 한국은 DART 잠정실적 vs 증권사 컨센서스 — "그런 일이 있었던 종목"을 전체에서 걸러내는 축 */
      spr:{label:'영업익 서프라이즈',fmt:v=>(v>0?'+':'')+v.toFixed(1)+'%',reqData:1,
        presets:[['전체',null,null],['비트(+0%↑)',0,null],['+10% ↑',10,null],['+30% ↑',30,null],['미스(−0%↓)',null,0],['−30% ↓',null,-30]],def:[null,null]},
      sspr:{label:'매출 서프라이즈',fmt:v=>(v>0?'+':'')+v.toFixed(1)+'%',reqData:1,
        presets:[['전체',null,null],['비트(+0%↑)',0,null],['+5% ↑',5,null],['+10% ↑',10,null],['미스(−0%↓)',null,0]],def:[null,null]},
      sprb:{label:'연속 비트(4Q중)',fixed:'— (KR 미제공 · 분기 서프 이력 무료 소스 없음)'},
      /* ③ 영업익 추정 리비전 — 컨센서스 스냅샷 차분. 30일=2026-09-08~ · 90일=2026-11-07~ 유효 */
      cr7:{label:'컨센 리비전 7일',fixed:'— (한국 미제공 — WISEreport 컨센은 주간 스냅샷)'},
      cr30:{label:'영업익추정 리비전 30일',fmt:v=>(v>0?'+':'')+v.toFixed(1)+'%',reqData:1,
        presets:[['전체',null,null],['상향 +2%↑',2,null],['상향 +5%↑',5,null],['하향 −2%↓',null,-2]],def:[null,null]},
      cr90:{label:'영업익추정 리비전 90일',fmt:v=>(v>0?'+':'')+v.toFixed(1)+'%',reqData:1,
        presets:[['전체',null,null],['상향 +5%↑',5,null],['상향 +10%↑',10,null],['하향 −5%↓',null,-5]],def:[null,null]},
      gap:{label:'매출 가이던스 갭',fixed:'— (한국은 기업 가이던스 공시 관행 없음 — 잠정 vs 컨센 서프라이즈가 대신)'},
      gapE:{label:'EPS 가이던스 갭',fixed:'— (한국은 기업 가이던스 공시 관행 없음)'},
      /* ④ 목표주가 리비전 — WISEreport 증권사별 변동표. 오늘 바로 유효 */
      tprv:{label:'목표주가 리비전 30일',fmt:v=>(v>0?'+':'')+v.toFixed(1)+'%',reqData:1,
        presets:[['전체',null,null],['상향 +3%↑',3,null],['상향 +10%↑',10,null],['하향 −3%↓',null,-3],['하향 −10%↓',null,-10]],def:[null,null]},
      tprv90:{label:'목표주가 리비전 90일',fmt:v=>(v>0?'+':'')+v.toFixed(1)+'%',reqData:1,
        presets:[['전체',null,null],['상향 +5%↑',5,null],['상향 +10%↑',10,null],['하향 −5%↓',null,-5]],def:[null,null]},
      edld:{label:'발표 후 경과일',fmt:v=>v===0?'오늘':`D+${v.toFixed(0)}`,reqData:1,
        presets:[['전체',null,null],['3일 이내',null,3],['7일 이내',null,7],['30일 이내',null,30]],def:[null,null]},
      r1:{label:'발표 후 1일',fmt:v=>(v>0?'+':'')+v.toFixed(1)+'%',reqData:1,
        presets:[['전체',null,null],['+5% ↑',5,null],['−5% ↓',null,-5]],def:[null,null]},
      r20:{label:'발표 후 20일(PEAD)',fmt:v=>(v>0?'+':'')+v.toFixed(1)+'%',reqData:1,
        presets:[['전체',null,null],['+10% ↑',10,null],['−10% ↓',null,-10]],def:[null,null]}
    },
    us:{
      sector:{label:'섹터',cat:1},
      usind:{label:'세부업종',cat:1},
      chg:{label:'등락',fmt:v=>v.toFixed(1)+'%',presets:[['전체',null,null],['상승(0% ↑)',0,null],['+3% ↑',3,null],['하락(0% ↓)',null,0],['−3% ↓',null,-3]],def:[null,null]},
      cap:{label:'시가총액',fmt:usdF,presets:[['전체',null,null],['$200B ↑',2e11,null],['$10~200B',1e10,2e11],['$2~10B',2e9,1e10],['$300M~2B',3e8,2e9],['$300M ↓',null,3e8]],def:[2e9,null]},
      tv:{label:'거래대금',fmt:usdF,min:1,presets:[['전체',null],['$50M ↑',5e7],['$20M ↑',2e7],['$5M ↑',5e6]],def:[2e7,null]},
      px:{label:'가격',fmt:usdF,min:1,presets:[['전체',null],['$5 ↑',5],['$10 ↑',10],['$50 ↑',50]],def:[5,null]},
      age:{label:'상장기간',fmt:v=>v+'년',min:1,presets:[['전체',null],['1년 ↑',1],['3년 ↑',3],['5년 ↑',5],['10년 ↑',10]],def:[1,null]},
      sec:{label:'증권 구분',fixed:'EQUITY만(ETF·워런트 제외)'},
      opLoss:{label:'영업적자',exclGE:1,maxOnly:1,fmt:v=>v.toFixed(0)+'년이상 제외',presets:[['전체',null,null],['1년이상 제외',null,1],['2년이상 제외',null,2],['3년이상 제외',null,3]],def:[null,3]},
      de:{label:'부채비율',fmt:v=>v.toFixed(0)+'%',fin:1,presets:[['전체',null,null],['100% ↓',null,100],['200% ↓',null,200],['300% ↓',null,300]],def:[null,300]},
      cr:{label:'유동비율',fmt:v=>v.toFixed(1),min:1,fin:1,presets:[['전체',null],['0.8 ↑',0.8],['1.0 ↑',1.0],['1.5 ↑',1.5]],def:[0.8,null]},
      /* (2026-08-10) 사용자 지정 명칭 — '목표주가 상승여력' */
      upside:{label:'목표주가 상승여력',fmt:v=>v.toFixed(0)+'%',min:1,reqData:1,presets:[['전체',null],['0% ↑',0],['10% ↑',10],['20% ↑',20],['50% ↑',50]],def:[null,null]},
      rec:{label:'투자의견',fmt:v=>'매수강도 '+v.toFixed(0),min:1,reqData:1,presets:[['전체',null],['매수 이상',65],['강력매수',85]],def:[null,null]},
      rev:{label:'리비전',fmt:v=>v.toFixed(0)+'%',min:1,reqData:1,presets:[['전체',null],['상향(0% ↑)',0],['5% ↑',5],['10% ↑',10]],def:[null,null]},
      nan:{label:'애널수',fmt:v=>v.toFixed(0)+'명',min:1,reqData:1,presets:[['전체',null],['1명 ↑',1],['3명 ↑',3],['10명 ↑',10]],def:[null,null]},
      cov:{label:'목표주가',tgl:1,def:false,tglLabel:'컨센서스 있는 종목만'},
      per:{label:'PER',fmt:v=>v.toFixed(1)+'배',presets:[['전체',null,null],['10배 ↓',null,10],['15배 ↓',null,15],['20배 ↓',null,20]],def:[null,null]},
      pbr:{label:'PBR',fmt:v=>v.toFixed(1)+'배',presets:[['전체',null,null],['1배 ↓',null,1],['2배 ↓',null,2],['3배 ↓',null,3]],def:[null,null]},
      divy:{label:'배당',fmt:v=>v.toFixed(1)+'%',min:1,presets:[['전체',null],['1% ↑',1],['2% ↑',2],['3% ↑',3]],def:[null,null]},
      grw:{label:'성장',fmt:v=>v.toFixed(0)+'%',min:1,presets:[['전체',null],['0% ↑',0],['10% ↑',10],['20% ↑',20],['50% ↑',50]],def:[null,null]},
      mom:{label:'수익률 12-1M',fmt:v=>v.toFixed(0)+'%',presets:[['전체',null,null],['0% ↑',0,null],['50% ↑',50,null],['100% ↑',100,null],['0% ↓(하락)',null,0],['-30% ↓',null,-30]],def:[null,null]},
      r1m:{label:'수익률 1M',fmt:v=>(v>=0?'+':'')+v.toFixed(0)+'%',reqData:1,presets:[['전체',null,null],['0% ↑',0,null],['10% ↑',10,null],['20% ↑',20,null],['0% ↓(하락)',null,0],['-10% ↓',null,-10]],def:[null,null]},
      r3m:{label:'수익률 3M',fmt:v=>(v>=0?'+':'')+v.toFixed(0)+'%',reqData:1,presets:[['전체',null,null],['0% ↑',0,null],['20% ↑',20,null],['50% ↑',50,null],['0% ↓(하락)',null,0],['-20% ↓',null,-20]],def:[null,null]},
      r6m:{label:'수익률 6M',fmt:v=>(v>=0?'+':'')+v.toFixed(0)+'%',reqData:1,presets:[['전체',null,null],['0% ↑',0,null],['30% ↑',30,null],['100% ↑',100,null],['0% ↓(하락)',null,0],['-30% ↓',null,-30]],def:[null,null]},
      vol20:{label:'변동성(20일)',fmt:v=>v.toFixed(1)+'%',reqData:1,presets:[['전체',null,null],['2% ↓(안정)',null,2],['3% ↓',null,3],['5% ↑(고변동)',5,null]],def:[null,null]},
      turn:{label:'회전율',fmt:v=>v.toFixed(2)+'%',min:1,reqData:1,presets:[['전체',null],['0.1% ↑',0.1],['0.5% ↑',0.5],['1% ↑',1]],def:[null,null]},
      tob:{label:'흑자전환',fixed:'— (US 미제공)'},
      opm:{label:'영업이익률',fmt:v=>v.toFixed(0)+'%',min:1,reqData:1,presets:[['전체',null],['0% ↑',0],['5% ↑',5],['10% ↑',10],['20% ↑',20]],def:[null,null]},
      peg:{label:'PEG',fmt:v=>v.toFixed(1),reqData:1,presets:[['전체',null,null],['1 ↓',null,1],['1.5 ↓',null,1.5],['2 ↓',null,2]],def:[null,null]},
      psr:{label:'PSR',fmt:v=>v.toFixed(1)+'배',reqData:1,presets:[['전체',null,null],['1배 ↓',null,1],['3배 ↓',null,3],['5배 ↓',null,5]],def:[null,null]},
      fnb20:{label:'외인수급(20일)',fixed:'— (US 미제공)'},
      onb20:{label:'기관수급(20일)',fixed:'— (US 미제공)'},
      fst:{label:'외인연속매수',fixed:'— (US 미제공)'},
      ost:{label:'기관연속매수',fixed:'— (US 미제공)'},
      sr:{label:'공매도비중',fixed:'— (US 미제공)'},
      lbr:{label:'대차잔고비율',fixed:'— (US 미제공)'},
      ern:{label:'어닝일(D±)',fmt:v=>(v<0?'D+'+(-v).toFixed(0):'D-'+v.toFixed(0)),reqData:1,
        presets:[['전체',null,null],['D-7 이내',0,7],['D-14 이내',0,14],['D-30 이내',0,30],
                 ['발표 후 D+1~D+7',-7,-1],['발표 전후 ±7일',-7,7]],def:[null,null]},   // (2026-08-04) 음수=발표 지남(사후 추적)
      hi:{label:'고점比',fmt:v=>'고점 '+v.toFixed(0)+'%',presets:[['전체',null,null],['-10% 이내',-10,null],['-20% 이내',-20,null],['-30% ↓(낙폭 큼)',null,-30],['-50% ↓',null,-50]],def:[null,null]},
      v200:{label:'200일선',fmt:v=>(v>=0?'+':'')+v.toFixed(0)+'%',min:1,presets:[['전체',null],['−30% ↑',-30],['−20% ↑',-20],['−10% ↑',-10],['위(0%) ↑',0],['+10% ↑',10],['+20% ↑',20]],def:[-30,null]},
      v20:{label:'20일선',fmt:v=>(v>=0?'+':'')+v.toFixed(0)+'%',min:1,reqData:1,presets:[['전체',null],['위(0%) ↑',0],['−5% ↑',-5],['+5% ↑',5]],def:[null,null]},
      v50:{label:'50일선',fmt:v=>(v>=0?'+':'')+v.toFixed(0)+'%',min:1,reqData:1,presets:[['전체',null],['위(0%) ↑',0],['−10% ↑',-10],['+10% ↑',10]],def:[null,null]},
      align:{label:'이평배열',cat:1,opts:['정배열','역배열','혼조'],hint:{'정배열':['up','상승 추세'],'역배열':['dn','하락 추세'],'혼조':['neu','전환 구간']}},
      rsi:{label:'RSI(14)',fmt:v=>'RSI '+v.toFixed(0),reqData:1,presets:[['전체',null,null],['과매도(≤30)',null,30],['30~50',30,50],['50 ↑(모멘텀)',50,null],['과매수 제외(≤70)',null,70],['과매수(≥70)',70,null]],def:[null,null]},
      volx:{label:'거래량배수',fmt:v=>v.toFixed(1)+'배',min:1,reqData:1,presets:[['전체',null],['1.5배 ↑',1.5],['2배 ↑',2],['3배 ↑',3]],def:[null,null]},
      macd:{label:'MACD',cat:1,opts:['골든↑','골든↓','데드↑','데드↓'],disp:MACD_DISP,hint:{'골든↑':['up','강한 상승'],'골든↓':['up','상승 전환'],'데드↑':['dn','하락 전환'],'데드↓':['dn','강한 하락']}},
      bb:{label:'볼린저밴드',fmt:v=>'%b '+v.toFixed(0),reqData:1,presets:[['전체',null,null],['하단권(≤20)',null,20],['중심 위(≥50)',50,null],['상단권(≥80)',80,null],['상단 돌파(≥100)',100,null]],def:[null,null]},
      roe:{label:'ROE',fmt:v=>v.toFixed(0)+'%',min:1,reqData:1,presets:[['전체',null],['5% ↑',5],['10% ↑',10],['15% ↑',15],['20% ↑',20]],def:[null,null]},
      mgrw:{label:'매출성장',fmt:v=>v.toFixed(0)+'%',reqData:1,presets:[['전체',null,null],['0% ↑',0,null],['10% ↑',10,null],['20% ↑',20,null],['부진(0% ↓)',null,0]],def:[null,null]},
      ogrw:{label:'이익성장',fmt:v=>v.toFixed(0)+'%',reqData:1,presets:[['전체',null,null],['0% ↑',0,null],['20% ↑',20,null],['100% ↑',100,null],['부진(0% ↓)',null,0],['-30% ↓',null,-30]],def:[null,null]},
      gacc:{label:'성장가속',fmt:v=>(v>=0?'+':'')+v.toFixed(0)+'%p',reqData:1,presets:[['전체',null,null],['가속 전환(0%p ↑)',0,null],['+10%p ↑',10,null],['+30%p ↑',30,null],['둔화(0%p ↓)',null,0]],def:[null,null]},
      qtoby:{label:'분기흑자YoY',tgl:1,def:false,tglLabel:'전년동기 적자→당분기 흑자 전환만 (계절성 안전)'},
      qtobq:{label:'분기흑자QoQ',tgl:1,def:false,tglLabel:'직전분기 적자→당분기 흑자 전환만 (가장 빠름·계절성 주의)'},
      opmch:{label:'마진변화',fmt:v=>(v>=0?'+':'')+v.toFixed(1)+'%p',reqData:1,presets:[['전체',null,null],['개선(0%p ↑)',0,null],['+3%p ↑',3,null],['+10%p ↑',10,null],['악화(0%p ↓)',null,0]],def:[null,null]},
      frgn:{label:'외인보유비중',fixed:'— (US 미제공)'},
      frgn4w:{label:'외인지분율 4주변화',fixed:'— (US 미제공)'},
      srf:{label:'공매도잔량비율',fmt:v=>v.toFixed(1)+'%',reqData:1,presets:[['전체',null,null],['2% ↓(약함)',null,2],['5% ↓',null,5],['10% ↑(과열)',10,null],['20% ↑',20,null]],def:[null,null]},
      scov:{label:'커버일수',fmt:v=>v.toFixed(1)+'일',reqData:1,presets:[['전체',null,null],['2일 ↓',null,2],['5일 ↑(부담)',5,null],['10일 ↑',10,null]],def:[null,null]},
      inst:{label:'기관보유비중',fmt:v=>v.toFixed(0)+'%',reqData:1,presets:[['전체',null,null],['70% ↑',70,null],['50% ↑',50,null],['30% ↓',null,30]],def:[null,null]},
      drvj:{label:'파생·수급판정',fmt:v=>(v>0?'+':'')+parseFloat(v.toFixed(2))+'점',reqData:1,presets:[['전체',null,null],['강세(+1점 ↑)',1,null],['+0.5점 ↑',0.5,null],['약세(−1점 ↓)',null,-1],['−0.5점 ↓',null,-0.5]],def:[null,null]},
      payout:{label:'배당성향',fmt:v=>v.toFixed(0)+'%',min:1,reqData:1,presets:[['전체',null],['10% ↑',10],['30% ↑',30],['50% ↑',50]],def:[null,null]},
      dinc:{label:'DPS 연속증가',fixed:'— (US 미제공)'},
      /* (2026-08-06) US 배당 이력(div_hist_us.py — 야후 30y 배당 이벤트 실측):
         dgy = '건당 평균 배당' 기준 연속 증가 연수 (연간 합계는 지급 밀림에 취약 — O 리얼티인컴 실측으로 확인).
               10년↑=Achievers · 20년↑=귀족급 · 30년+=Kings 급. 야후 이력 한계로 실제(KO 63년)보다 짧게 나올 수 있음(보수적).
         dcyc = 지급월 그룹 — 그룹별 1종목씩 3종목이면 매월 배당 수령(월배당 달력 조합).
         mdd5 = 최근 5년 월봉 최대낙폭 — '폭락 이력' 실측. */
      dgy:{label:'배당성장연수',fmt:v=>(v>=30?'30년+':v.toFixed(0)+'년')+' 연속↑',min:1,reqData:1,presets:[['전체',null],['10년 ↑',10],['20년 ↑',20],['30년+',30]],def:[null,null]},
      dcyc:{label:'배당주기',cat:1,opts:['월배당(연12회)','분기 1·4·7·10월','분기 2·5·8·11월','분기 3·6·9·12월'],
        hint:{'월배당(연12회)':['up','매월 지급'],'분기 1·4·7·10월':['neu','그룹1'],'분기 2·5·8·11월':['neu','그룹2'],'분기 3·6·9·12월':['neu','그룹3 — 세 그룹 1종목씩=매월 수령']}},
      mdd5:{label:'최대낙폭 5Y',fmt:v=>v.toFixed(0)+'%',reqData:1,presets:[['전체',null,null],['−20% 이내',-20,null],['−30% 이내',-30,null],['−40% 이내',-40,null]],def:[null,null]},
      /* (2026-08-10) 실적발표 이벤트 — 사용자 지정 명칭·구성으로 재편:
         직전실적 매출/EPS 서프 2종 + 가이던스 갭 매출/EPS 분리 + 리비전 7/30일 */
      spr:{label:'직전실적 EPS컨센 서프라이즈',fmt:v=>(v>0?'+':'')+v.toFixed(1)+'%',reqData:1,
        presets:[['전체',null,null],['비트(+0%↑)',0,null],['+10% ↑',10,null],['미스(−0%↓)',null,0]],def:[null,null]},
      /* (2026-08-10) 신규 — Zacks 발표 이력(상세 패널과 같은 소스·정의) 벌크 수집(zacks_spr.py) */
      sspr:{label:'직전실적 매출컨센 서프라이즈',fmt:v=>(v>0?'+':'')+v.toFixed(1)+'%',reqData:1,
        presets:[['전체',null,null],['비트(+0%↑)',0,null],['+3% ↑',3,null],['미스(−0%↓)',null,0]],def:[null,null]},
      sprb:{label:'연속 비트(4Q중)',fmt:v=>v.toFixed(0)+'/4회',reqData:1,
        presets:[['전체',null,null],['3회 ↑',3,null],['4회 전부',4,null]],def:[null,null]},
      cr7:{label:'EPS 컨센 리비전 변화율 (7일)',fmt:v=>(v>0?'+':'')+v.toFixed(1)+'%',reqData:1,
        presets:[['전체',null,null],['상향 +1%↑',1,null],['상향 +3%↑',3,null],['하향 −1%↓',null,-1]],def:[null,null]},
      cr30:{label:'EPS 컨센 리비전 변화율 (30일)',fmt:v=>(v>0?'+':'')+v.toFixed(1)+'%',reqData:1,
        presets:[['전체',null,null],['상향 +2%↑',2,null],['상향 +5%↑',5,null],['하향 −2%↓',null,-2]],def:[null,null]},
      /* (2026-08-14, 2차) cr90 이 필터 정의가 없어 컬럼 헤더가 CDEF 의 짧은 이름('추정90일')
         으로 남아있었다(자동 동기화는 DEF[mkt] 에 정의가 있어야 동작) — cr7/cr30 과 짝 맞춤. */
      cr90:{label:'EPS 컨센 리비전 변화율 (90일)',fmt:v=>(v>0?'+':'')+v.toFixed(1)+'%',reqData:1,
        presets:[['전체',null,null],['상향 +5%↑',5,null],['상향 +10%↑',10,null],['하향 −5%↓',null,-5]],def:[null,null]},
      /* (2026-08-14) 주가 대비 리비전 — cr7·cr30·cr90 과 같은 원자료지만 기저(EPS 추정치)가
         아니라 **주가**로 나눈다. 기저가 0 근처일 때 cr 이 폭주하는 문제(ZIM +1452% 사례)를
         측정 방식 자체에서 회피 — 종목간 비교·정렬은 이 값을 우선 참고. cr7/30/90 컬럼은
         이제 화면에 조건 없이 이 값(%p)으로 표시된다(위 셀 렌더링 참고). */
      pr7:{label:'EPS 리비전 (주가대비,7일)',fmt:v=>(v>0?'+':'')+v.toFixed(2)+'%p',reqData:1,
        presets:[['전체',null,null],['상향 +0.2%p↑',0.2,null],['상향 +0.5%p↑',0.5,null],['하향 −0.2%p↓',null,-0.2]],def:[null,null]},
      pr30:{label:'EPS 리비전 (주가대비,30일)',fmt:v=>(v>0?'+':'')+v.toFixed(2)+'%p',reqData:1,
        presets:[['전체',null,null],['상향 +0.3%p↑',0.3,null],['상향 +0.8%p↑',0.8,null],['하향 −0.3%p↓',null,-0.3]],def:[null,null]},
      pr90:{label:'EPS 리비전 (주가대비,90일)',fmt:v=>(v>0?'+':'')+v.toFixed(2)+'%p',reqData:1,
        presets:[['전체',null,null],['상향 +0.5%p↑',0.5,null],['상향 +1%p↑',1,null],['하향 −0.5%p↓',null,-0.5]],def:[null,null]},
      gap:{label:'매출 가이던스 갭',fmt:v=>(v>0?'+':'')+v.toFixed(1)+'%',reqData:1,
        presets:[['전체',null,null],['상회 +2%↑',2,null],['하회 −2%↓',null,-2],['크게 하회 −5%↓',null,-5]],def:[null,null]},
      gapE:{label:'EPS 가이던스 갭',fmt:v=>(v>0?'+':'')+v.toFixed(1)+'%',reqData:1,
        presets:[['전체',null,null],['상회 +2%↑',2,null],['하회 −2%↓',null,-2],['크게 하회 −5%↓',null,-5]],def:[null,null]},
      /* (2026-08-10) 포털 가이던스 갭 — **파싱 검증 전용**.
         우리가 8-K 보도자료에서 직접 파싱한 값(gap·gapE) 옆에 포털(Benzinga) 값을 나란히 두어
         "우리 파싱이 맞는지"를 눈으로 대조하기 위한 것이다.
         비트/미스 판정·전략 버튼·종합 점수에는 이 값을 절대 쓰지 않는다. */
      gapP:{label:'매출 가이던스 갭(포털)',fmt:v=>(v>0?'+':'')+v.toFixed(1)+'%',reqData:1,
        presets:[['전체',null,null],['상회 +2%↑',2,null],['하회 −2%↓',null,-2],['크게 하회 −5%↓',null,-5]],def:[null,null]},
      gapEP:{label:'EPS 가이던스 갭(포털)',fmt:v=>(v>0?'+':'')+v.toFixed(1)+'%',reqData:1,
        presets:[['전체',null,null],['상회 +2%↑',2,null],['하회 −2%↓',null,-2],['크게 하회 −5%↓',null,-5]],def:[null,null]},
      /* (2026-08-09) US 목표주가 리비전 — 미국 목표가는 '현재 유효한 목표가 평균'(기간 개념 없음 ·
         커버리지 중단 시에만 제외)이라 일별 스냅샷을 쌓아 차분한다(us_consensus.sqlite · 08-09 시작).
         30일 = 2026-09-08~ · 90일 = 2026-11-07~ 유효 — 그 전엔 값이 비어 있다. */
      tprv:{label:'목표주가 리비전 30일',fmt:v=>(v>0?'+':'')+v.toFixed(1)+'%',reqData:1,
        presets:[['전체',null,null],['상향 +3%↑',3,null],['상향 +10%↑',10,null],['하향 −3%↓',null,-3],['하향 −10%↓',null,-10]],def:[null,null]},
      tprv90:{label:'목표주가 리비전 90일',fmt:v=>(v>0?'+':'')+v.toFixed(1)+'%',reqData:1,
        presets:[['전체',null,null],['상향 +5%↑',5,null],['상향 +10%↑',10,null],['하향 −5%↓',null,-5]],def:[null,null]},
      edld:{label:'발표 후 경과일',fmt:v=>v===0?'오늘':`D+${v.toFixed(0)}`,reqData:1,
        presets:[['전체',null,null],['3일 이내',null,3],['7일 이내',null,7],['30일 이내',null,30]],def:[null,null]},
      r1:{label:'발표 후 1일',fmt:v=>(v>0?'+':'')+v.toFixed(1)+'%',reqData:1,
        presets:[['전체',null,null],['+5% ↑',5,null],['−5% ↓',null,-5]],def:[null,null]},
      r20:{label:'발표 후 20일(PEAD)',fmt:v=>(v>0?'+':'')+v.toFixed(1)+'%',reqData:1,
        presets:[['전체',null,null],['+10% ↑',10,null],['−10% ↓',null,-10]],def:[null,null]}
    }
  };
  /* 나열 순서 = 표시 컬럼 순서와 동일. 컬럼이 없는 필터(증권 구분)는 맨 뒤에 배치 */
  const KEYS=['mk','krx','wics2','wics','usind','sector','px','chg','cap','tv','de','cr','opLoss','age',
              /* (2026-07-21) 이동평균은 기간 오름차순으로 — 20일 → 50일 → 200일 */
              'v20','v50','v200','align','rsi','adx','volx','turn','macd','bb',
              /* (2026-07-21) 수익률 1Y 제거 — 미국은 mom(수익률 12-1M)이 52주 변화율로 산출돼
                 r1y 와 사실상 동일값이었다(실측 ALKS +98/+97.7 · AEHR +393/+392.7 · NAVN +30/+29.8).
                 중복 컬럼을 없애고 mom 을 1Y 가 있던 자리(6M 뒤)로 옮긴다. */
              'r1m','r3m','r6m','mom','vol20','hi','frgn','frgn4w','fnb20','onb20','fst','ost','sr','lbr','srf','scov','inst','drvj',
              'ern','cov','upside','rec','rev','nan',
              /* (2026-08-09) 실적발표 이벤트 — 실적(서프)·전망(리비전·가이던스)·주가(반응) 순
                 (2026-08-10) cr7 · gapE 추가 — 리비전 7일 / 가이던스 갭 매출·EPS 분리 */
              'edld','spr','sspr','sprb','cr7','cr30','cr90','pr7','pr30','pr90','tprv','tprv90','gap','gapP','gapE','gapEP','r1','r20',
              'grw','mgrw','ogrw','gacc','tob','qtoby','qtobq','opm','opmch','per','peg','pbr','psr','roe','payout','divy','dinc','dgy','dcyc','mdd5','sec'];
  /* ── (2026-07-24) 파생·수급판정 점수 (등급형 v2) ──────────────────────
     파생 z 3종(베이시스·풋콜(OI)·IV스큐 — 방향지표만, GEX·OI 제외):
       |z|≥1 → ±0.5점 · |z|≥2 → ±1점  (절벽 제거 — 1.49/1.51 이 갈리지 않게)
     현물 프록시(선행성이 약해 절반 이하 가중):
       외인·기관 20일 순매수 — 시총 대비 0.3%↑면 ±0.5 · 그 미만 ±0.25 (크기 반영)
       공매도비중 ≥5% −0.5 · <2% +0.25 (대칭화 — 음의 쏠림 방지) · 대차잔고비율 ≥10% −0.5
     파생 미수록 종목은 프록시만으로 계산(표에서 ≈ 표시). */
  let DRVSC=null, _drvscTried=false;
  function loadDrvSc(){
    if(_drvscTried) return; _drvscTried=true;
    fetch('/api/db/stock_deriv_score').then(r=>r.ok?r.json():null).then(d=>{
      if(d&&d.s){ DRVSC=d.s; refresh(); }
    }).catch(()=>{});
  }
  /* (2026-07-24) 부호 통일 — 인덱스 3.1.13처럼 카드·점수 모두 z(+)=강세·z(−)=약세.
     원지표가 약세 재료(풋콜=풋/콜, 스큐=풋−콜)인 것은 표시 전에 z 부호를 뒤집는다. */
  const _uz=z=>z==null?null:-z;
  /* 파생 점수 — 통일 z 3종(전부 z+=강세) 단순 등급 합산 */
  function _drvPts(b,p,s){
    const g=z=>{ if(z==null) return 0; const a=Math.abs(z); if(a<1) return 0;
      return (z>0?1:-1)*(a>=2?1:0.5); };
    return Math.round((g(b)+g(p)+g(s))*100)/100;
  }
  /* 프록시 점수 — KR 풀 행에서. 데이터 전무면 null */
  function _prxPts(r){
    let sc=0, any=false;
    const mg=v=>{ if(v==null||v===0) return 0;
      const pct=r.cap?Math.abs(v)*1e8/r.cap*100:null;          // 순매수(억원)→시총 대비 %
      const pt=(pct!=null&&pct>=0.3)?0.5:0.25;
      return v>0?pt:-pt; };
    if(r.fnb20!=null){ any=true; sc+=mg(r.fnb20); }
    if(r.onb20!=null){ any=true; sc+=mg(r.onb20); }
    if(r.sr!=null){ any=true; if(r.sr>=5) sc-=0.5; else if(r.sr<2) sc+=0.25; }
    if(r.lbr!=null&&r.lbr>=10) sc-=0.5;
    return any?Math.round(sc*100)/100:null;
  }
  /* (2026-07-24) US 수급 프록시 점수 — FINRA 공매도잔량(2주 주기)·커버일수
     잔량/유통 ≥10% −0.5 · ≤1% +0.5 · ≤2% +0.25 / 커버일수 ≥5일 −0.25 (기관보유는 정보만) */
  function _prxPtsUS(r){
    let sc=0, any=false;
    if(r.sr_f!=null){ any=true; const p=r.sr_f*100;
      if(p>=10) sc-=0.5; else if(p<=1) sc+=0.5; else if(p<=2) sc+=0.25; }
    if(r.scov!=null){ any=true; if(r.scov>=5) sc-=0.25; }
    return any?Math.round(sc*100)/100:null;
  }
  function _prxPartsUS(r){
    const R={};
    const p=r.sr_f!=null?r.sr_f*100:null;
    R.srf = p==null?'—': p>=10?'공매도 잔량 과다 — 하락 베팅 큼(급등 시 숏스퀴즈 연료이기도)':
            p>=2?'공매도 보통':'공매도 낮음 — 하락 베팅 적음';
    R.scov = r.scov==null?'—': r.scov>=5?'커버 부담 큼 — 되사는 데 5일 이상(스퀴즈 민감)':
             r.scov>=2?'커버 부담 보통':'커버 부담 적음';
    R.inst = r.inst==null?'—':'기관이 유통주식의 '+ (r.inst*100).toFixed(0) +'% 보유 (수준 정보 — 점수 미반영)';
    return R;
  }
  function _prxRowsUS(r,R){
    const row=(label,val,interp)=>`<div class="si" style="align-items:baseline"><span>${label}</span>`+
      `<b style="text-align:right">${val}<div class="note" style="font-weight:400;text-align:right">${interp}</div></b></div>`;
    return row('공매도잔량비율', cell(r,'srf'), R.srf)+
      row('커버일수(Days to Cover)', cell(r,'scov'), R.scov)+
      row('기관보유비중', cell(r,'inst'), R.inst);
  }
  /* (2026-08-14, 3차 수정) cr7/cr30/cr90(%변화율) 컬럼을 **항상 주가 대비 %p**로 표시한다.
     처음엔 "기저(현재 eq0·eq1)가 작을 때만" 조건부로 바꿨는데, 그 근사 조건이 정작 문제의
     원인 사례(ZIM: 그때 기저 0.09→현재 eq0 1.38 로 이미 커져서 조건에 안 걸림, +1214.4%
     그대로 노출)를 못 잡았다. 사용자 재지적("주가대비로 표시하라니깐") 반영 — 조건 없이
     pr7/pr30/pr90 값이 있으면 무조건 그걸 보여주고, 원래 %는 툴팁에서만 확인한다. */
  function _crDisplay(r,prKey,v){
    const pv=prKey?r[prKey]:null;
    if(pv==null) return null;
    const p=pv*100, z=Math.abs(p)<0.05;
    return {cls:z?'':(p>0?'up':'dn'), text:(p>0?'+':'')+p.toFixed(2)+'%p',
      title:`주가 대비 EPS 컨센 변화(=ΔEPS÷현재가) · 참고: 변화율(%) 원값 ${v>0?'+':''}${v.toFixed(1)}%`};
  }
  function _drvjVal(r){
    const d=DRVSC&&DRVSC[r.c];
    const dp=d?_drvPts(d.b,_uz(d.p),_uz(d.s)):null;   // slim은 원지표 z — 통일 부호로 변환
    const pp=mkt==='kr'?_prxPts(r):_prxPtsUS(r);
    if(dp==null&&pp==null) return null;
    return Math.round(((dp||0)+(pp||0))*100)/100;
  }
  const _fmtPt=v=>parseFloat(v.toFixed(2)).toString();
  const FK2CK={rec:'recn', mgrw:'revg', ogrw:'opg', cov:'tp', opLoss:'oploss'};   // 필터키 → 컬럼키(값 접근자 공통화)
  let POOL={kr:[],us:[]}, mkt='kr', F={}, sort={k:'cap',d:-1}, loaded=false;
  /* (2026-08-02) 업종 분류 맵 — sector_map.py(주1회): KR=KRX·WICS대·WICS세부 / US=세부업종(한글) */
  let SECMAP=null, F4W=null, DPSH=null, DIVUS=null;   // F4W=외인지분율 4주Δ · DPSH=DPS 연속증가 · DIVUS=US 배당이력(div_hist_us.py, 2026-08-06)
  function mergeSec(){
    if(SECMAP){
      for(const r of POOL.kr){ const e=(SECMAP.kr||{})[r.code]; if(e){ if(e.krx)r.krx=e.krx; if(e.wics)r.wics=e.wics; if(e.wics2)r.wics2=e.wics2; } }
      for(const r of POOL.us){ const e=(SECMAP.us||{})[r.sym]; if(e&&e.ind) r.usind=e.ind; } }
    if(F4W&&F4W.d) for(const r of POOL.kr){ const v=F4W.d[r.code]; if(v!=null) r.frgn4w=v; }
    if(DPSH&&DPSH.d) for(const r of POOL.kr){ const v=DPSH.d[r.code];
      if(v){ r.dinc=v.inc; r.dps_y=v.y; } }
    if(DIVUS&&DIVUS.d) for(const r of POOL.us){ const v=DIVUS.d[r.sym];
      if(v){ r.dgy=v.dgy; r.dfreq=v.freq; r.dmd=v.md; r.pmg=v.pmg; r.mdd5=v.mdd5; r.div_y=v.y;
        r.dcyc=v.md?'월배당(연12회)':(v.pmg?['','분기 1·4·7·10월','분기 2·5·8·11월','분기 3·6·9·12월'][v.pmg]:(v.freq?'기타(연'+v.freq+'회)':null)); } } }
  function loadSecMap(){
    if(!F4W) fetch('/api/db/frgn4w').then(x=>x.ok?x.json():null).then(d=>{ if(!d||!d.d) return;
      F4W=d; mergeSec(); if(loaded&&typeof refresh==='function') refresh(); }).catch(()=>{});
    if(!DPSH) fetch('/api/db/dps_hist').then(x=>x.ok?x.json():null).then(d=>{ if(!d||!d.d) return;
      DPSH=d; mergeSec(); if(loaded&&typeof refresh==='function') refresh(); }).catch(()=>{});
    if(!DIVUS) fetch('/api/db/div_hist_us').then(x=>x.ok?x.json():null).then(d=>{ if(!d||!d.d) return;
      DIVUS=d; mergeSec(); if(loaded&&typeof refresh==='function') refresh(); }).catch(()=>{});
    if(SECMAP){ mergeSec(); return; }
    fetch('/api/db/sector_map').then(x=>x.ok?x.json():null).then(d=>{ if(!d) return; SECMAP=d; mergeSec(); if(loaded&&typeof refresh==='function') refresh(); }).catch(()=>{}); }

  const F_ST={};   // 마켓별 1단계 필터 상태 유지
  function buildF(){ const o={}; const d=DEF[mkt];
    for(const k of KEYS){ const f=d[k]; if(!f || f.fixed!==undefined) continue;
      if(f.tgl){o[k]={on:f.def};}
      else if(f.cat){o[k]={v:null};}
      else {o[k]={min:f.def[0],max:f.def[1]};} } return o; }
  function resetF(){ F_ST[mkt]=buildF(); F=F_ST[mkt]; }          // 초기화 → 현재 마켓만 기본값
  /* 전부전체 = 모든 필터를 '전체'로 (buildF 와 같은 구조에 기본값 대신 빈 값) */
  function clearF(){ const o={}; const d=DEF[mkt];
    for(const k of KEYS){ const f=d[k]; if(!f || f.fixed!==undefined) continue;
      if(f.tgl){o[k]={on:false};}
      else if(f.cat){o[k]={v:null};}
      else {o[k]={min:null,max:null};} } return o; }
  function allF(){ F_ST[mkt]=clearF(); F=F_ST[mkt]; }
  /* (2026-08-10) 저장 상태 정규화 — sessionStorage 에 남은 옛 값에 **문자열**이 섞이면
     칩 표시(fmt: v=>v.toFixed(…))에서 'v.toFixed is not a function' 으로 화면 전체가 죽는다
     (실측: 미국 탭 '풀 로드 실패: TypeError: v.toFixed is not a function' — 표가 통째로 안 나옴).
     범위형 필터의 min/max 는 항상 숫자 또는 null 이어야 한다. */
  function normF(o){ const d=DEF[mkt]||{};
    for(const k in o){ const f=d[k], st=o[k]; if(!f||!st||f.tgl||f.cat||f.fixed!==undefined) continue;
      for(const s of ['min','max']){
        if(st[s]==null||st[s]==='') { st[s]=null; continue; }
        const n=+st[s]; st[s]=Number.isFinite(n)?n:null; } }
    return o; }
  function loadF(){ if(!F_ST[mkt]) F_ST[mkt]=buildF();           // 마켓 전환 → 저장분 로드(원복 안함)
    else { const df=buildF();
      for(const k in df) if(!(k in F_ST[mkt])) F_ST[mkt][k]=df[k];        // 신규 필터키 백필
      for(const k in F_ST[mkt]) if(!(k in df)) delete F_ST[mkt][k]; }     // 없어진 필터키 정리(구버전 세션 호환)
    F=normF(F_ST[mkt]); }
  const ageOf=r=>r.yr?nowY-r.yr:null;
  function pass(r){ const d=DEF[mkt];
    for(const k in F){ const f=d[k], st=F[k];
      /* (2026-07-21) 정의가 사라진 필터키는 건너뛴다.
         F_ST 는 sessionStorage('nmr_scr')에 저장돼 탭을 새로고침해도 남는다. 그래서 필터를
         제거·개편하면(예: 수익률 1Y 삭제) 옛 상태에 남은 키가 d[k]=undefined 가 되어
         '풀 로드 실패: Cannot read properties of undefined (reading tgl)' 로 화면 전체가 죽었다.
         앞으로 어떤 필터를 빼도 안전하도록 방어한다. */
      if(!f) continue;
      if(f.tgl){ if(!st.on) continue;
        if(k==='cov' && r.tp==null) return false;
        if(k==='tob' && !r.tob) return false;
        if(k==='qtoby' && !r.qtoby) return false;   // 분기 흑자전환(전년동기比)
        if(k==='qtobq' && !r.qtobq) return false;   // 분기 흑자전환(직전분기比)
        continue; }
      if(f.cat){ if(st.v!=null && String(r[k]||'')!==st.v) return false; continue; }
      /* (2026-07-24) 파생·수급판정 CASE 다중선택 — 값 조건과 별개로 케이스로도 거른다 (KR만) */
      if(k==='drvj' && Array.isArray(st.cs) && st.cs.length && st.cs.length<3 && mkt==='kr'){
        const _d=DRVSC&&DRVSC[r.c];
        const _kz=!_d?3:(_d.o?1:2);
        if(!st.cs.includes(_kz)) return false;
      }
      if(f.fin && r.isfin) continue;   // 금융업 면제
      let v=colVal(r, FK2CK[k]||k);   // 필터키 → 컬럼키 매핑 후 공통 접근자 사용
      if(v==null){ if(f.reqData && (st.min!=null||st.max!=null)) return false; continue; }
      if(f.exclGE){ if(st.max!=null && v>=st.max) return false; continue; }   // N년이상 제외  // 데이터 필수 필터: 값 없으면 제외
      if(st.min!=null && v<st.min) return false;
      if(st.max!=null && v>st.max) return false; }
    return true; }

  function catOpts(k){          // 범주형 옵션은 풀 데이터에서 수집
    const set=new Set();
    for(const r of (POOL[mkt]||[])){ const v=r[k]; if(v) set.add(String(v)); }
    return ['', ...[...set].sort()];
  }
  /* (2026-07-22) 이평선 컬럼/필터 라벨을 시장별로 — 한국 차트선 20/60/120, 미국 20/50/200. (차트에 있는 선만 노출) */
  const _MALBL = {v20:{kr:'20일선',us:'20일선'}, v50:{kr:'60일선',us:'50일선'}, v200:{kr:'120일선',us:'200일선'}};
  function chipLabel(k){ const f=DEF[mkt][k], st=F[k]||{};
    const L = _MALBL[k]?_MALBL[k][mkt]:f.label;
    if(f.fixed!==undefined) return `${L}: <span class="cv">${E(f.fixed)}</span>`;
    if(f.tgl) return `${L}: <span class="cv">${st.on?'ON':'OFF'}</span>`;
    if(f.cat) return `${L}: <span class="cv">${E(dispOpt(f,st.v)||'전체')}</span>`;
    if(f.exclGE) return `${L}: <span class="cv">${st.max==null?'전체':st.max+'년이상 제외'}</span>`;
    const lo=st.min, hi=st.max;
    /* (2026-08-10) fmt 는 숫자 전제(v.toFixed 등) — 방어적으로 감싼다. 칩 하나의 표시 실패가
       스크리너 전체 렌더를 중단시키면 안 된다(실측 사고). 실패 시 원값을 그대로 보여준다. */
    const FM=x=>{ try{ return f.fmt(x); }catch(e){ return String(x); } };
    let v = (lo==null&&hi==null)?'전체' : (hi==null?FM(lo)+' ↑' : (lo==null?FM(hi)+' ↓' : FM(lo)+'~'+FM(hi)));
    /* (2026-07-24) 파생·수급판정 — CASE 다중선택이 걸려 있으면 칩에 표기 */
    if(k==='drvj'&&Array.isArray(st.cs)&&st.cs.length&&st.cs.length<3)
      v=(v==='전체'?'':v+' · ')+'CASE'+st.cs.join('·');
    return `${L}: <span class="cv">${E(v)}</span>`; }

  /* (2026-07-22) 결과표 UI 옵션 — 종목 클릭 시 상세로 자동이동(기본 ON) · 스크롤 전 표시 행수(기본 8). localStorage 유지. */
  let autoScroll = localStorage.getItem('scr_autoscroll') === '1';   // 기본 OFF (명시적 '1'일 때만 ON)
  let visRows = Math.max(1, Math.min(60, +localStorage.getItem('scr_visrows') || 8));
  function applyTblHeight(){
    const w=document.getElementById('scr_tblwrap'); if(!w) return;
    const tbl=document.getElementById('scr_tbl');
    const hd=tbl&&tbl.querySelector('th'); const row=tbl&&tbl.querySelector('tr[data-c]');
    const hH = hd&&hd.parentElement ? hd.parentElement.offsetHeight : 34;
    const rH = row ? row.offsetHeight : 48;
    w.style.maxHeight = (hH + visRows*rH + 2) + 'px';
  }
  /* (2026-07-22) 툴바 버튼 7종(필터설명·초기화·전부전체·자동이동·표시·컬럼설정·START)을
     .scrtop 한 줄에 고정 — ETF 스크리너와 동일 배치. placeBtns 는 이동 없이 단계별 표시/숨김만. */
  const BTNS_GRP=document.getElementById('scr_btns_grp');
  function placeBtns(){
    const S1 = stage===1;
    const show=(id,on,dsp)=>{ const el=$(id); if(el) el.style.display = on?(dsp||''):'none'; };
    if(BTNS_GRP) BTNS_GRP.style.display='';           // 그룹은 항상 표시(개별 버튼만 제어)
    show('scr_glsbtn', stage<=2);                     // 필터설명: 1·2단계
    show('scr_rst', S1);                              // 초기화: 1단계
    show('scr_turn', S1);                             // 턴어라운드 프리셋: 1단계
    show('scr_surge', S1); show('scr_surge_hi', S1);  // 개장서지 + 변형 3종: 1단계
    show('scr_surge_sq', S1); show('scr_surge_ern', S1);
    show('scr_fmom', S1);                             // 외인모멘텀(KR 전용): 1단계
    show('scr_divp', S1);                             // 배당선취(KR 전용): 1단계
    show('scr_darist', S1); show('scr_dgrow', S1);    // US 배당 3종(US 전용): 1단계
    show('scr_dcal', S1);
    show('scr_lowpbr', S1);                           // 저PBR M&A 프리셋: 1단계
    show('scr_allf', S1);                             // 전부전체: 1단계
    show('scr_autoscroll', S1);
    show('scr_rowsbox', S1, 'inline-flex');
    show('scr_colbtn', S1);
    show('scr_start', S1);
    {const gp=$('scr_glspanel');
     if(gp){
       if(stage===2){ const s2=$('scr_s2');
         if(s2 && gp.parentElement!==s2) s2.insertBefore(gp, s2.firstChild); }
       else {         // (2026-07-26) 1단계: 필터설명 버튼과 필터 바 사이(= 필터 바 바로 위)
         const fb=$('scr_fltbar');
         if(fb && gp.nextElementSibling!==fb) fb.parentElement.insertBefore(gp, fb); }
       if(gp.style.display!=='none') renderLegend();   // 단계 전환 시 열린 설명 갱신
     }} }
  /* ── 종목 찾기 칩 (돋보기 → 입력창, 입력 즉시 필터) ── */
  let findQ='', findOpen=false, findCaret=null, findIME=false;
  function findHit(r){
    if(!findQ) return true;
    // (2026-07-20) "화장품|뷰티"=OR, "삼성&전자"=AND. | 로 그룹 분리(OR), 그룹 안 & 로 모두 요구(AND)
    const groups=findQ.toLowerCase().split('|').map(g=>g.split('&').map(s=>s.trim()).filter(Boolean)).filter(g=>g.length);
    if(!groups.length) return true;
    // (2026-07-23) 미국 종목은 한글명(kn)으로도 검색 — '테슬' → TSLA
    const n=String(r.n||'').toLowerCase(), c=String(r.c||'').toLowerCase(), k=String(r.kn||'').toLowerCase();
    return groups.some(g=>g.every(t=>n.includes(t)||c.includes(t)||k.includes(t)));
  }
  function findChipHTML(){
    return findOpen
      ? `<div class="fchip"><span class="findbox">🔎<input id="find_in" placeholder="${mkt==='us'?'종목명·코드  (예: apple|tesla, advanced&micro)':'종목명·코드  (예: 화장품|뷰티, 삼성&전자)'}" value="${E(findQ)}"
           autocomplete="off" spellcheck="false"><button id="find_x" title="찾기 해제">✕</button></span></div>`
      : `<div class="fchip"><button class="${findQ?'act':''}" id="find_btn" title="종목명·코드로 찾기">🔎 종목: <span class="cv">${findQ?E(findQ):'전체'}</span></button></div>`;
  }
  function renderChips(){
    /* 한글 조합 중엔 칩을 다시 그리지 않는다 — input 이 새로 만들어지면 조합이 끊겨 'ㅅㅏㅁ'이 된다 */
    if(findOpen && findIME) return;
    const d=DEF[mkt];
    const parts=KEYS.map(k=>{
      const f=d[k];
      if(!f) return '';
      if(f.fixed!==undefined) return `<div class="fchip"><button disabled style="opacity:.75;cursor:default">${chipLabel(k)}</button></div>`;
      const st=F[k]; const active = f.tgl? st.on : (f.cat? st.v!=null : (st.min!=null||st.max!=null
        || (k==='drvj'&&Array.isArray(st.cs)&&st.cs.length&&st.cs.length<3)));
      let pop;
      if(f.cat){
        const _opts=f.opts?['',...f.opts]:catOpts(k);   // (2026-07-18) 고정 옵션 지원 — 데이터 도착 전에도 선택지 표시
        /* (2026-07-21) 상태값 옵션에 주식 관점 방향(상승/하락)을 배지로 붙인다.
           '골든↓' 처럼 화살표만 봐서는 우호/비우호가 직관적이지 않다는 지적 반영.
           색은 화면 전체 규칙과 동일 — 빨강=주식 우호, 파랑=비우호, 회색=중립. */
        const _srch=_opts.length>8?`<input type="text" class="catq" data-catq="${k}" placeholder="🔎 검색" style="width:95%;margin:2px 0 4px;padding:3px 6px;font-size:12px;border:1px solid #d7dce3;border-radius:5px">`:'';
        pop=`<div class="pl">선택 ${_opts.length>8?`<span class="note">(${_opts.length-1}개)</span>`:''}</div>`+_srch+`<div class="catlist" style="max-height:300px;overflow:auto">`+_opts.map(o=>{
          const h=(f.hint||{})[o];
          const tag=h?`<span class="ohint ${h[0]}">${E(h[1])}</span>`:'';
          return `<button class="preset ohas ${st.v===(o||null)?'sel':''}" data-cat="${k}" data-v="${E(o)}">${E(dispOpt(f,o)||'전체')}${tag}</button>`;
        }).join('')+`</div>`;
      } else if(f.tgl){
        pop=`<label class="tgl"><input type="checkbox" data-tgl="${k}" ${st.on?'checked':''}> ${E(f.tglLabel)}</label>`;
      } else {
        /* (2026-07-24) 파생·수급판정 — 프리셋 라벨 오른쪽에 CASE1/2/3 다중선택(기본 전체) */
        const _csBtns = k==='drvj'
          ? `<span style="float:right;display:inline-flex;gap:4px">${[1,2,3].map(n=>{
              const on=!Array.isArray(st.cs)||st.cs.includes(n);
              return `<button class="preset" data-csk="${k}" data-csn="${n}" style="padding:2px 7px;font-size:11px;${on?'background:#2f6fed;color:#fff;border-color:#2f6fed':''}" title="CASE1 선물+옵션 · CASE2 선물만 · CASE3 파생 미상장(프록시) — 눌러서 켜고 끄기(다중선택)">C${n}</button>`;
            }).join('')}</span>`
          : '';
        pop=`<div class="pl">프리셋${_csBtns}</div>`+f.presets.map((p,pi)=>{
          const lo=p[1], hi=p.length>2?p[2]:null;
          const sel=(st.min===lo && (st.max===hi || (f.min&&hi==null)));
          return `<button class="preset ${sel?'sel':''}" data-k="${k}" data-lo="${lo==null?'':lo}" data-hi="${hi==null?'':hi}">${E(p[0])}</button>`;
        }).join('')+
        `<div class="man"><span>직접</span>`+
        (f.maxOnly?'':`<input type="number" placeholder="최소" data-man="${k}" data-mm="min" value="${st.min??''}">`)+
        (f.min?'':`${f.maxOnly?'':'<span>~</span>'}<input type="number" placeholder="${f.maxOnly?'N년이상':'최대'}" data-man="${k}" data-mm="max" value="${st.max??''}">`)+`</div>`;
      }
      return `<div class="fchip"><button class="${active?'act':''}" data-chip="${k}">${chipLabel(k)}</button><div class="fpop" id="pop_${k}">${pop}</div></div>`;
    });
    parts.unshift(findChipHTML());   // 종목 찾기 칩 = 필터 바 맨 앞(시장 왼쪽)
    $('scr_fltbar').innerHTML=parts.join('');
    /* (2026-07-26) innerHTML 로 BTNS_GRP(START·컬럼설정)가 분리된 직후 아래 배선에서
       예외가 나면 placeBtns 재부착을 못 해 START 가 사라진다 — finally 로 봉쇄 */
    try{
    // 이벤트
    $('scr_fltbar').querySelectorAll('[data-chip]').forEach(b=>b.onclick=e=>{
      e.stopPropagation(); const k=b.dataset.chip; const p=$('pop_'+k); const wasOpen=p.classList.contains('open');
      document.querySelectorAll('.fpop').forEach(x=>x.classList.remove('open')); if(!wasOpen)p.classList.add('open'); });
    /* CASE 다중선택 — 프리셋과 별개 상태(cs). 토글 후에도 팝업을 다시 열어 연속 선택 편의 */
    $('scr_fltbar').querySelectorAll('[data-csk]').forEach(b=>b.onclick=e=>{
      e.stopPropagation();
      const k=b.dataset.csk, n=+b.dataset.csn;
      const st=F[k]||(F[k]={min:null,max:null});
      let cs=Array.isArray(st.cs)?st.cs.slice():[1,2,3];
      cs=cs.includes(n)?cs.filter(x=>x!==n):cs.concat(n).sort();
      if(!cs.length) cs=[1,2,3];               // 전부 끄면 의미가 없어 전체로 복귀
      st.cs=cs.length===3?undefined:cs;
      apply();
      const p=$('pop_'+k); if(p) p.classList.add('open');
    });
    $('scr_fltbar').querySelectorAll('.preset:not([data-csk])').forEach(b=>b.onclick=()=>{
      const k=b.dataset.k; const _cs=(F[k]||{}).cs;   // CASE 선택은 프리셋 변경에도 유지
      F[k]={min:b.dataset.lo===''?null:+b.dataset.lo, max:b.dataset.hi===''?null:+b.dataset.hi, cs:_cs}; apply(); });
    $('scr_fltbar').querySelectorAll('[data-man]').forEach(inp=>inp.oninput=()=>{
      const k=inp.dataset.man; F[k][inp.dataset.mm]= inp.value===''?null:+inp.value;
      const btn=document.querySelector(`[data-chip="${k}"]`);
      if(btn){ btn.innerHTML=chipLabel(k); btn.classList.toggle('act', F[k].min!=null||F[k].max!=null); }
      applyTable(); });
    $('scr_fltbar').querySelectorAll('[data-catq]').forEach(inp=>{
      inp.onclick=e=>e.stopPropagation();
      inp.oninput=()=>{ const q=inp.value.trim().toLowerCase();
        inp.closest('.fpop').querySelectorAll('.catlist .preset').forEach(btn=>{
          btn.style.display=(!q||btn.textContent.toLowerCase().includes(q))?'':'none'; }); }; });
    $('scr_fltbar').querySelectorAll('[data-cat]').forEach(b=>b.onclick=()=>{
      F[b.dataset.cat].v = b.dataset.v||null; apply(); });
    $('scr_fltbar').querySelectorAll('[data-tgl]').forEach(t=>t.onchange=()=>{ F[t.dataset.tgl].on=t.checked; apply(); });
    /* 종목 찾기 — 돋보기 클릭 시 입력창으로 전환, 입력할 때마다 즉시 필터 */
    {const b=$('find_btn'); if(b) b.onclick=e=>{ e.stopPropagation();
      document.querySelectorAll('.fpop').forEach(x=>x.classList.remove('open'));
      findOpen=true; findCaret=null; renderChips(); };}
    {const x=$('find_x'); if(x) x.onclick=e=>{ e.stopPropagation(); findIME=false; findQ=''; findOpen=false; apply(); };}
    {const fi=$('find_in'); if(fi){
      fi.onclick=e=>e.stopPropagation();
      /* 입력 중엔 applyTable() 만 — apply()(=renderChips 포함)를 부르면 입력창이 새로 그려져 한글 조합이 깨진다 */
      fi.oncompositionstart=()=>{ findIME=true; };
      fi.oncompositionend=()=>{ findIME=false; findQ=fi.value.trim(); findCaret=fi.selectionStart; applyTable(); };
      fi.oninput=()=>{ findQ=fi.value.trim(); findCaret=fi.selectionStart; applyTable(); };
      fi.onkeydown=e=>{ e.stopPropagation();
        if(e.key==='Escape'){ findIME=false; findQ=''; findOpen=false; apply(); }
        if(e.key==='Enter'&&!findIME){ const t=$('scr_tbl').querySelector('tr[data-c]'); if(t) showDetail(t.dataset.c); } };
      /* 표 자동갱신으로 칩이 다시 그려져도 입력 위치를 유지 (다른 입력창 사용 중이면 양보) */
      const ae=document.activeElement;
      if(!(ae&&/^(INPUT|SELECT|TEXTAREA)$/.test(ae.tagName)&&ae.id!=='find_in')){
        fi.focus(); if(findCaret!=null) fi.setSelectionRange(findCaret,findCaret); }
    }}
    }catch(err){ console.error('[renderChips] 배선 오류:', err); }
    finally{ placeBtns(); }   // innerHTML 재작성 후 버튼 그룹 재부착 — 예외가 나도 반드시
  }

  /* ── 컬럼 레지스트리 (표시 On/OFF + 순서 변경) ── */
  /* l = 표 헤더 라벨(마켓별 객체 가능), pl = 컬럼 패널 라벨(생략 시 l)
     — 패널 라벨은 위 필터 바 이름과 정확히 일치시켜 매칭이 쉽도록 함 */
  /* 컬럼 정의 = 이 순서가 필터 나열 순서의 기준(KEYS도 동일 순서).
     라벨은 필터와 완전히 동일(짧게) — 부연 설명은 하단 '필터 설명'에 기재 */
  const CDEF={
    n:{l:'종목',n:0,m:'both'},
    mk:{l:'시장',n:0,m:'kr'}, sector:{l:'섹터',n:0,m:'us'},
    krx:{l:'KRX 업종',n:0,m:'kr'}, wics2:{l:'WICS 세부',n:0,m:'kr'}, wics:{l:'WICS 섹터',n:0,m:'kr'},
    usind:{l:'세부업종',n:0,m:'us'},
    px:{l:'가격',n:1,m:'both'}, chg:{l:'등락',n:1,m:'both'},
    cap:{l:'시가총액',n:1,m:'both'}, tv:{l:'거래대금',n:1,m:'both'},
    de:{l:'부채비율',n:1,m:'both'}, cr:{l:'유동비율',n:1,m:'both'},
    oploss:{l:'영업적자',n:1,m:'both'},
    age:{l:'상장기간',n:1,m:'both'}, v200:{l:'200일선',n:1,m:'both'},
    v20:{l:'20일선',n:1,m:'both'}, v50:{l:'50일선',n:1,m:'both'}, align:{l:'이평배열',n:0,m:'both'},
    rsi:{l:'RSI',n:1,m:'both'}, adx:{l:'ADX',n:1,m:'kr'}, volx:{l:'거래량배수',n:1,m:'both'}, turn:{l:'회전율',n:1,m:'both'},
    macd:{l:'MACD',n:0,m:'both'}, bb:{l:'볼린저밴드',n:1,m:'both'},
    /* 라벨을 시장별로 다르게 — 한국은 12M, 미국은 12−1M 이라 값의 의미가 다르다.
       getter 라 mkt 전환 시 헤더·컬럼패널·필터칩이 자동으로 따라간다. */
    mom:{get l(){return mkt==='kr'?'수익률 12M':'수익률 12-1M';},n:1,m:'both'},
    r1m:{l:'수익률 1M',n:1,m:'both'}, r3m:{l:'수익률 3M',n:1,m:'both'},
    r6m:{l:'수익률 6M',n:1,m:'both'},
    vol20:{l:'변동성(20일)',n:1,m:'both'},
    hi:{l:'고점比',n:1,m:'both'}, frgn:{l:'외인보유비중',n:1,m:'kr'}, frgn4w:{l:'외인지분율Δ4주',n:1,m:'kr'}, dinc:{l:'DPS연속증가',n:1,m:'kr'},
    dgy:{l:'배당성장연수',n:1,m:'us'}, dcyc:{l:'배당주기',n:0,m:'us'}, mdd5:{l:'최대낙폭5Y',n:1,m:'us'},
    fnb20:{l:'외인수급(20일)',n:1,m:'kr'}, onb20:{l:'기관수급(20일)',n:1,m:'kr'},
    fst:{l:'외인연속매수',n:1,m:'kr'}, ost:{l:'기관연속매수',n:1,m:'kr'},
    sr:{l:'공매도비중',n:1,m:'kr'}, lbr:{l:'대차잔고비율',n:1,m:'kr'},
    drvj:{l:'파생·수급판정',n:1,m:'both'},   // (2026-07-24) 파생 z(±1점) + 현물 프록시(±0.5점) 합산
    /* (2026-07-24) US 수급 프록시 — FINRA 공매도(2주 주기)·기관보유 (Yahoo defaultKeyStatistics) */
    srf:{l:'공매도잔량비율',n:1,m:'us'}, scov:{l:'커버일수',n:1,m:'us'}, inst:{l:'기관보유비중',n:1,m:'us'},
    ern:{l:'어닝일',n:1,m:'both'},
    tob:{l:'흑자전환',n:0,m:'kr'}, qtoby:{l:'분기흑자YoY',n:0,m:'both'}, qtobq:{l:'분기흑자QoQ',n:0,m:'both'}, opm:{l:'영업이익률',n:1,m:'both'}, opmch:{l:'마진변화',n:1,m:'both'},
    peg:{l:'PEG',n:1,m:'both'}, psr:{l:'PSR',n:1,m:'both'},
    tp:{l:'목표주가',n:1,m:'both'}, upside:{l:'상승여력',n:1,m:'both'},
    recn:{l:'투자의견',n:1,m:'both'}, rev:{l:'리비전',n:1,m:'both'}, nan:{l:'애널수',n:1,m:'us'},
    /* (2026-08-09) 실적발표 — 필터 6종과 1:1 대응. 필터가 있으면 컬럼도 있어야 표에서 값을 확인할 수 있다. */
    edld:{l:'실적발표일',n:1,m:'both'}, spr:{l:'실적서프%',n:1,m:'both'}, sspr:{l:'매출서프%',n:1,m:'both'}, sprb:{l:'비트4Q',n:1,m:'us'}, cr7:{l:'컨센7일',n:1,m:'us'}, cr30:{l:'컨센30일',n:1,m:'both'},
    cr90:{l:'추정90일',n:1,m:'both'},
    /* (2026-08-14) 주가 대비 리비전 컬럼 — cr7/30/90 은 화면에서 이미 이 값(%p)으로 표시되지만
       필터·컬럼 목록에도 독립적으로 노출해 정렬·필터링에 직접 쓸 수 있게 한다. */
    pr7:{l:'리비전 주가대비7일',n:1,m:'us'}, pr30:{l:'리비전 주가대비30일',n:1,m:'us'}, pr90:{l:'리비전 주가대비90일',n:1,m:'us'},
    tprv:{l:'목표가30일',n:1,m:'both'}, tprv90:{l:'목표가90일',n:1,m:'both'}, gap:{l:'매출 가이던스 갭',n:1,m:'us'}, gapP:{l:'매출 가이던스 갭(포털)',n:1,m:'us'},
    gapE:{l:'EPS 가이던스 갭',n:1,m:'us'}, gapEP:{l:'EPS 가이던스 갭(포털)',n:1,m:'us'},
    r1:{l:'발표D+1',n:1,m:'both'}, r20:{l:'발표D+20',n:1,m:'both'},
    grw:{l:'성장',n:1,m:'both'}, revg:{l:'매출성장',n:1,m:'both'}, opg:{l:'이익성장',n:1,m:'both'}, gacc:{l:'성장가속',n:1,m:'both'},
    per:{l:'PER',n:1,m:'both'}, pbr:{l:'PBR',n:1,m:'both'}, roe:{l:'ROE',n:1,m:'both'},
    payout:{l:'배당성향',n:1,m:'both'}, divy:{l:'배당',n:1,m:'both'}
  };
  /* (2026-08-10) 컬럼명 = 필터명 **자동 동기화** — 이름이 어긋나면 같은 값인지 알 수 없다
     (사용자 지시). 컬럼 라벨을 하드코딩하지 않고 현재 시장의 필터 정의(DEF[mkt].label)에서
     그대로 가져온다 → 필터명을 바꾸면 컬럼명이 저절로 따라오고, 시장 전환 시에도 맞는다.
     필터 키와 컬럼 키가 다른 4쌍은 명시 매핑. 필터가 없는 컬럼(목표주가 등)·fixed(미제공)
     필터는 기존 컬럼 라벨을 유지한다. */
  {const F2C={recn:'rec',revg:'mgrw',opg:'ogrw',oploss:'opLoss'};
   Object.keys(CDEF).forEach(k=>{
     const od=Object.getOwnPropertyDescriptor(CDEF[k],'l');
     const orig=()=>od&&(od.get?od.get.call(CDEF[k]):od.value);
     Object.defineProperty(CDEF[k],'l',{configurable:true,get(){
       /* (2026-08-10) 방어 — 라벨 조회가 실패해도 **표 렌더는 멈추면 안 된다**.
          이 getter 는 헤더·컬럼패널·필터칩이 매번 호출하므로 예외가 나면 화면이 통째로
          비어 버린다(전환 직후 DEF 미준비 등). 실패 시 원래 라벨로 조용히 되돌린다. */
       try{ const d=DEF[mkt]&&DEF[mkt][F2C[k]||k];
            return (d&&d.label&&d.fixed===undefined)?d.label:orig(); }
       catch(e){ return orig(); } }});
   });}
  const cl =k=>_MALBL[k]?_MALBL[k][mkt]:CDEF[k].l;   // 표 헤더 = 패널 = 필터 (이평선은 시장별 라벨)
  const cpl=cl;
  const CALL=Object.keys(CDEF);
  /* '추가 가능' 목록 정렬 = 필터가 없는 컬럼 먼저(종목·시장·섹터·등락·목표주가)
     → 그다음은 위 필터 바(KEYS)와 동일한 순서로 나열 */
  const CK2FK={}; for(const fk of KEYS){ const ck=FK2CK[fk]||fk; if(CDEF[ck]) CK2FK[ck]=fk; }
  /* (2026-07-23) Set 중복 제거 — qtoby·qtobq 두 필터가 같은 컬럼(qtob=분기흑자)에 매핑돼
     '분기흑자'가 표·컬럼설정에 2개 생기던 문제 */
  const CORDER=[...new Set(CALL.filter(k=>!CK2FK[k])
                   .concat(KEYS.map(fk=>FK2CK[fk]||fk).filter(ck=>CDEF[ck])))];
  const cAvail=k=>{const m=(CDEF[k]||{}).m; return m==='both'||m===mkt;};
  /* 기본 표시 컬럼 = 초기화 상태에서 '값이 걸린' 필터와 정확히 일치(구성·순서 동일)
     (시가총액·거래대금·저가주=가격·상장기간·부채비율·유동비율 + 종목/등락/컨센서스)
     ※ 증권 구분만 고정값이라 대응 컬럼 없음 */
  /* (2026-07-20) 확인 편의를 위해 기본값 = '전부 체크'. 시장별 미해당 컬럼은 cAvail 이 렌더 단계에서 거른다.
     (원래 기본값: kr ['n','mk','px','chg','cap','tv','de','cr','oploss','age','v200'] /
                   us ['n','sector','px','chg','cap','tv','de','cr','oploss','age','v200']) */
  const CDEFAULT={ kr:CORDER.slice(), us:CORDER.slice() };
  let COLST={kr:CDEFAULT.kr.slice(), us:CDEFAULT.us.slice()};
  /* 컬럼 구성은 '개인 PC'(localStorage)에 영구 저장 — 접속자마다 각자 설정 유지.
     (필터·정렬 등 나머지 상태는 세션 한정이라 sessionStorage 유지) */
  const COLKEY='nmr_cols_v5';   // v4: 1Y 제거·모멘텀 시장별 정의·이평 20→50→200 순서 (구 저장설정 무효화)
  let colsSaved=false;
  function saveCols(){ try{ localStorage.setItem(COLKEY,JSON.stringify(COLST)); colsSaved=true; }catch(e){} }
  function loadCols(){                       // 저장된 설정이 있는지 체크 → 있으면 사용, 없으면 기본값
    try{
      const raw=localStorage.getItem(COLKEY); if(!raw) return false;
      const d=JSON.parse(raw);
      if(!d||!Array.isArray(d.kr)||!Array.isArray(d.us)) return false;
      const kr=[...new Set(d.kr.filter(k=>CDEF[k]))], us=[...new Set(d.us.filter(k=>CDEF[k]))];   // 모르는/폐기된 키 제거 + 중복 제거(분기흑자 2개 버그 저장분 정화)
      if(!kr.length||!us.length) return false;
      COLST={kr,us}; colsSaved=true; return true;
    }catch(e){ return false; }
  }
  function clearCols(){ try{ localStorage.removeItem(COLKEY); }catch(e){} colsSaved=false; }
  loadCols();
  // 컬럼·정렬·필터 공통 값 (모두 '표시 단위'로 통일)
  function colVal(r,k){
    switch(k){
      case 'px': return r.px; case 'chg': return r.chg;
      case 'cap': return r.cap; case 'tv': return r.tv; case 'age': return ageOf(r);
      case 'tp': return r.tp;
      case 'upside': return r.upside!=null?r.upside*100:null;
      case 'recn': return r.recn; case 'nan': return r.nan;
      case 'rev': return r.rev!=null?r.rev*100:null;
      case 'per': return mkt==='kr'?r.fper:r.fpe;
      case 'pbr': return mkt==='kr'?r.pbr:r.pb;
      case 'divy': return r.divy;
      case 'grw': return r.g_new!=null?r.g_new*100:null;
      case 'roe': return r.roe!=null?(mkt==='kr'?r.roe:r.roe*100):null;
      case 'revg': return r.revg!=null?r.revg*100:null;
      case 'opg': {const v=mkt==='kr'?r.opg:r.epsg; return v!=null?v*100:null;}
      case 'gacc': return r.gacc!=null?r.gacc*100:null;   // 동분기 YoY 성장 가속(%p)
      /* (2026-07-21) 모멘텀 정의를 시장별로 분리 — 한국 12M · 미국 12−1M.
         미국은 풀의 mom 이 채워지기 전(직전 빌드 산출물)에도 화면이 비지 않도록
         항등식 (1+1Y)/(1+1M)−1 로 유도해 대체한다(수학적으로 동일값). */
      case 'mom': {
        if(mkt==='kr') return r.mom!=null?r.mom*100:null;          // 한국 12M
        if(r.mom!=null) return r.mom*100;                           // 미국 12−1M (풀 산출)
        return (r.r1y!=null&&r.r1m!=null&&(1+r.r1m)>0)?((1+r.r1y)/(1+r.r1m)-1)*100:null;
      }
      case 'hi': {const v=mkt==='kr'?r.near52:r.hi52; return v!=null?v*100:null;}
      case 'v200': return r.vs200!=null?r.vs200*100:null;
      case 'v20': return r.v20!=null?r.v20*100:null;
      case 'v50': return r.v50!=null?r.v50*100:null;
      case 'align': return r.align??null; case 'macd': return r.macd??null;
      case 'adx': return r.adx??null;
      case 'rsi': return r.rsi; case 'volx': return r.volx; case 'bb': return r.bb;
      case 'de': return r.de; case 'cr': return r.cr;
      case 'oploss': return r.oploss!=null?r.oploss:(r.op3neg?3:null);
      case 'frgn': return r.frgn;
      case 'frgn4w': return r.frgn4w;                              // 외인 지분율 4주 변화(%p)
      case 'dinc': return r.dinc;                                  // DPS 연속 증가 연수
      case 'dgy': return r.dgy;                                    // US 배당성장연수(건당 평균 기준)
      case 'dcyc': return r.dcyc;
      case 'mdd5': return r.mdd5;                                  // 5년 월봉 최대낙폭(%)
      case 'payout': return r.payout!=null?r.payout*100:null;
      // (2026-07-26) 1차 필터 추가분 — 서버는 소수(fraction)로 저장, 표시·필터는 %
      case 'r1m': return r.r1m!=null?r.r1m*100:null;
      case 'r3m': return r.r3m!=null?r.r3m*100:null;
      case 'r6m': return r.r6m!=null?r.r6m*100:null;
      case 'vol20': return r.vol20;                       // 이미 % 값
      case 'opm': return r.opm!=null?r.opm*100:null;
      case 'turn': return r.turn!=null?r.turn*100:null;
      case 'peg': return r.peg; case 'psr': return r.psr;
      case 'tob': return r.tob?1:0;
      case 'qtoby': return r.qtoby?1:0;   // 분기 흑자전환(전년동기比)
      case 'qtobq': return r.qtobq?1:0;   // 분기 흑자전환(직전분기比)
      case 'opmch': return r.opmch!=null?r.opmch*100:null;
      case 'fnb20': return r.fnb20; case 'onb20': return r.onb20;   // 억원
      case 'fst': return r.fst; case 'ost': return r.ost;           // 연속일
      case 'sr': return r.sr;                                       // 공매도 비중(%)
      case 'lb': return r.lb;                                        // 대차잔고 금액(억원)
      case 'lbr': return r.lbr;                                      // 대차잔고비율(%)
      case 'drvj': return _drvjVal(r);                               // 파생·수급판정 점수
      case 'srf': return r.sr_f!=null?r.sr_f*100:null;               // US 공매도잔량/유통주식(%)
      case 'scov': return r.scov;                                    // US 커버일수(일)
      case 'inst': return r.inst!=null?r.inst*100:null;              // US 기관보유(%)
      /* (2026-08-09) 실적 → 전망 → 주가 3종. '발표 때 무슨 일이 있었나'를 전체에서 필터하기 위한 축.
         cr30 은 비율(0.05)로 저장돼 있어 %로 환산한다. */
      case 'spr':  return r.spr;                                    // 최근 실적 서프라이즈%
      case 'sspr': return r.sspr;                                   // 매출 서프라이즈% (KR=WISEreport · US=Zacks)
      case 'cr7':  return r.cr7!=null?r.cr7*100:null;               // EPS 컨센 7일 리비전%(US)
      case 'cr90': return r.cr90!=null?r.cr90*100:null;             // 영업익추정 리비전 90일%
      /* 목표주가 90일 — cTB24 산출(tprv90)이 우선, 없으면 기존 백필값(rev=목표가 90일 변화율) */
      case 'tprv90': return r.tprv90!=null?r.tprv90:(mkt==='kr'&&r.rev!=null?r.rev*100:null);
      case 'sprb': return r.sprb;                                   // 최근 4분기 중 컨센 상회 횟수
      case 'cr30': return r.cr30!=null?r.cr30*100:null;             // 컨센서스 30일 리비전%
      /* (2026-08-14) 주가 대비 리비전 — 기저 EPS 대신 주가로 나눠 저기저 폭주를 피한 병행 지표 */
      case 'pr7':  return r.pr7!=null?r.pr7*100:null;
      case 'pr30': return r.pr30!=null?r.pr30*100:null;
      case 'pr90': return r.pr90!=null?r.pr90*100:null;
      case 'gap':  return r.gapR!=null?r.gapR:null;                 // 매출 가이던스 vs 컨센 갭%(US)
      case 'gapE': return r.gapE!=null?r.gapE:null;                 // EPS 가이던스 vs 컨센 갭%(US)
      /* 포털 갭 — 8-K 직접 파싱값 검증용 대조 값. 판정에는 쓰지 않는다(사용자 지시). */
      case 'gapP': return r.pgapR!=null?r.pgapR:null;
      case 'gapEP':return r.pgapE!=null?r.pgapE:null;
      case 'r1':   return r.r1;                                     // 발표 후 1거래일 등락%
      case 'r20':  return r.r20;                                    // 발표 후 20거래일 수익%(PEAD)
      case 'tprv': return r.tprv;                                   // 목표주가 30일 리비전%(KR)
      /* (2026-08-09) 실적발표일 — '어닝일(ern)'은 Yahoo·네이버 IR 의 **예정일**이라
         실제 발표를 감지한 날(edl)과 다를 수 있다. 서프·반응 값은 전부 edl 기준이므로
         "며칠 전에 발표했나"를 따로 둔다. */
      case 'edld': { if(!r.edl) return null;
        const y=+r.edl.slice(0,4), m=+r.edl.slice(4,6)-1, d=+r.edl.slice(6,8);
        const t=new Date(); t.setHours(0,0,0,0);
        return Math.round((t-new Date(y,m,d))/86400000); }
      case 'ern': {                                                 // 어닝 D-day — 음수=발표 지남(D+, 사후 추적용)
        if(!r.ed) return null;
        const t=new Date(); t.setHours(0,0,0,0);
        return Math.round((new Date(r.ed+'T00:00:00')-t)/86400000); }   // (2026-08-04) 과거도 반환 — US 풀은 지난 ed 유지(실측 2,159종)
    }
    return null;
  }
  /* (2026-07-19) 빈칸 3-구분 — 왜 '—' 인지 행 데이터로 판별.
     na  : 원래 존재하지 않음(구조적) — 회색 —
     wait: 아직 수집 전/집계 대기      — 주황 ⋯
     err : 수집 시도했으나 오류         — 빨강 ⚠  (수집기가 r._err 에 필드명을 담을 때만) */
  const COV=['tp','upside','tp_rev','tp_trend','rev','rec','recn','nan'];
  const TECH=['v20','v50','align','rsi','volx','macd','bb','near52','vs200','v200','z_val','z_mom','z_qual'];
  function missKind(r,key){
    if(Array.isArray(r._err)&&r._err.includes(key)) return 'err';
    if(COV.includes(key)) return (r.nan||r.recn!=null||r.tp!=null)?'wait':'na';  // 애널 커버리지 없음
    if(key==='divy'||key==='payout') return 'na';                    // 무배당
    if(key==='per'||key==='fper'||key==='pbr') return 'na';          // 적자·자본잠식
    if(key==='cr') return /은행|보험|증권|금융|지주|캐피탈|카드/.test(r.sector||'')?'na':'wait';
    if(TECH.includes(key)) return 'wait';                            // 장중 상태·이력 누적 대기
    if(['gr','rg','opg','og','mgrw','ogrw','revg'].includes(key)) return 'na'; // 성장률 계산 불가(전년 적자 등)
    return 'na';
  }
  const MISS={na:'<span class="note" title="원래 없음 — 구조적으로 존재하지 않는 값(예: 무배당·적자·애널 미커버)">—</span>',
    wait:'<span class="m-wait" title="집계 대기 — 아직 수집/누적 전(장중 상태·이력 축적 중)">⋯</span>',
    err:'<span class="m-err" title="수집 오류 — 조회를 시도했으나 실패">⚠</span>'};
  const dash=(r,key)=>MISS[missKind(r,key)];
  function cell(r,key){
    // (2026-07-20) 미국 종목은 한글명(kn, KIS 해외 마스터)을 티커 옆에 병기 — 없으면 영문명만
    if(key==='n') return mkt==='kr'?`<b>${E(r.n)}</b> <span class="note">${E(r.c)}</span>`
      :`<b>${E(r.c)}</b> ${r.kn?`<b class="uskn">${E(r.kn)}</b> `:''}<span class="note">${E(r.n)}</span>`;
    if(key==='mk') return E(r.mk||'');
    if(key==='sector') return `<span class="note">${E(r.sector||'—')}</span>`;
    if(key==='krx'||key==='wics'||key==='wics2'||key==='usind') return `<span class="note">${E(r[key]||'—')}</span>`;   // (2026-08-02) 업종 분류
    if(key==='px') return mkt==='kr'?(r.px?Math.round(r.px).toLocaleString()+'원':'—'):'$'+(r.px?(+r.px).toFixed(2):'—');
    if(key==='chg'){const v=r.chg; return v==null?'—':`<span class="${v>0?'up':(v<0?'dn':'note')}">${v>0?'+':''}${(+v).toFixed(2)}%</span>`;}
    if(key==='cap') return mkt==='kr'?wonF(r.cap):usdF(r.cap);
    if(key==='tv') return mkt==='kr'?wonF(r.tv):usdF(r.tv);
    if(key==='tp'){const v=r.tp; return v==null?dash(r,key):(mkt==='kr'?Math.round(v).toLocaleString()+'원':'$'+(+v).toFixed(2));}
    if(key==='upside'){const v=r.upside; return v==null?dash(r,key):`<span class="${v>0?'up':(v<0?'dn':'note')}">${v>0?'+':''}${(v*100).toFixed(0)}%</span>`;}
    if(key==='recn'){const v=r.recn; if(v==null)return dash(r,key); const lab=v>=85?'강력매수':v>=65?'매수':v>=45?'중립':'매도'; return `${v.toFixed(0)} <span class="note">${lab}</span>`;}
    if(key==='nan'){const v=r.nan; return v==null?dash(r,key):v.toFixed(0)+'명';}
    if(key==='rev'){const v=r.rev; if(v==null) return dash(r,key);
      const t=r.tp_trend, ar=t==='up_steady'?'⇈':t==='down_steady'?'⇊':(v>0?'↑':v<0?'↓':'→');
      const cls=v>0?'up':(v<0?'dn':'note'), tt=t==='up_steady'?'꾸준상승':t==='down_steady'?'꾸준하락':(mkt==='us'?'EPS 추정치 90일 변화':'목표주가 90일 변화');
      return `<span class="${cls}" title="${tt}">${ar} ${v>0?'+':''}${(v*100).toFixed(1)}%</span>`;}
    if(key==='age'){const a=ageOf(r); return a==null?dash(r,key):a+'년';}
    if(key==='ern'){const v=colVal(r,'ern'); if(v==null) return dash(r,key);
      const lab=v===0?'오늘':(v<0?'D+'+(-v):'D-'+v);                     // D+ = 발표 지남(사후 추적)
      return `<span class="${v<0?'dn':(v<=7?'up':'')}">${lab}</span> <span class="note">${E((r.ed||'').slice(5))}</span>`;}
    const v=colVal(r,key); if(v==null) return dash(r,key);
    const sgn=d=>`<span class="${v>0?'up':(v<0?'dn':'note')}">${v>0?'+':''}${v.toFixed(d)}%</span>`;
    switch(key){
      case 'per': case 'pbr': return v.toFixed(1)+'배';
      case 'divy': return v.toFixed(2)+'%';
      case 'de': return v.toFixed(0)+'%';
      case 'cr': return v.toFixed(1);
      case 'roe': case 'frgn': return v.toFixed(1)+'%';
      case 'frgn4w': return `<span class="${v>0?'up':(v<0?'dn':'note')}">${v>0?'+':''}${v.toFixed(2)}%p</span>`;
      case 'dinc': { const ys=r.dps_y||{}; const tip=Object.keys(ys).sort().map(y=>y+' '+Math.round(ys[y]).toLocaleString()+'원').join(' · ');
        return `<span class="${v>=3?'up':(v>=1?'':'note')}" title="${tip}">${v}년 연속↑</span>`; }
      case 'dgy': { const ys=r.div_y||{}; const tip='건당 평균 배당: '+Object.keys(ys).sort().map(y=>y+' $'+ys[y]).join(' · ');
        return `<span class="${v>=20?'up':(v>=10?'':'note')}" title="${tip}">${v>=30?'30년+':v+'년'} 연속↑</span>`; }
      case 'dcyc': return `<span class="${/월배당/.test(v)?'up':'note'}" title="지급월 그룹별 1종목씩 3종목 = 매월 배당 수령">${v}</span>`;
      case 'mdd5': return `<span class="${v<=-40?'dn':(v>=-20?'up':'note')}" title="최근 5년 월봉 최대낙폭">${v.toFixed(0)}%</span>`;
      case 'payout': return v.toFixed(0)+'%';
      case 'oploss': return v>0?`<span class="dn">${v.toFixed(0)}년</span>`:'<span class="note">—</span>';
      case 'hi': return `<span class="note">고점 ${v.toFixed(0)}%</span>`;
      case 'grw': case 'revg': case 'opg': case 'mom': case 'v200': case 'v20': case 'v50': return sgn(0);
      case 'r1m': case 'r3m': case 'r6m': case 'opm': return sgn(1);
      case 'vol20': return v.toFixed(1)+'%';
      case 'turn': return v.toFixed(2)+'%';
      case 'peg': case 'psr': return v.toFixed(2);
      case 'tob': return v?'<span class="up">전환</span>':'<span class="note">—</span>';
      case 'qtoby': return v?'<span class="up" title="전년동기 적자→당분기 흑자 (계절성 안전)">전환</span>':'<span class="note">—</span>';
      case 'qtobq': return v?'<span class="up" title="직전분기 적자→당분기 흑자 (가장 빠름·계절성 주의)">전환</span>':'<span class="note">—</span>';
      case 'opmch': return `<span class="${v>0?'up':(v<0?'dn':'note')}" title="당분기 영업이익률 − 전년동기 영업이익률 (%p)">${v>0?'+':''}${v.toFixed(1)}%p</span>`;
      case 'edld': return `<span class="${v<=7?'up':'note'}" title="실제 발표 감지일 ${r.edl?r.edl.slice(0,4)+'-'+r.edl.slice(4,6)+'-'+r.edl.slice(6):'—'} (어닝일 컬럼은 IR 예정일)">${v===0?'오늘':'D+'+v.toFixed(0)}</span>`;
      /* (2026-08-09) 실적발표 6종 — 부호가 곧 의미라 색으로 즉시 구분 */
      case 'spr': return `<span class="${v>0?'up':(v<0?'dn':'note')}" title="${mkt==='us'?'최근 분기 EPS':'잠정 영업이익'} 컨센서스 대비">${v>0?'+':''}${v.toFixed(1)}%</span>`;
      case 'sprb': return `<span class="${v>=3?'up':'note'}" title="최근 ${r.sprn||4}분기 중 컨센 상회 횟수">${v.toFixed(0)}/${r.sprn||4}</span>`;
      /* (2026-08-14, 2차) 기저가 작으면 %가 폭주해 의미가 없다(ZIM +1452% 사례) — 그 경우
         원래 %가 아니라 **주가 대비 %p**로 바꿔서 보여준다(_crDisplay). 기저가 정상이면
         평소대로 %. */
      case 'cr30': { const sw=_crDisplay(r,'pr30',v);
        if(sw) return `<span class="${sw.cls}" title="${sw.title}">${sw.text}</span>`;
        return `<span class="${v>0?'up':(v<0?'dn':'note')}" title="${mkt==='us'?'EPS':'영업이익'} 컨센서스 30일 변화 · 상향 ${r.cup??'—'}명 / 하향 ${r.cdn??'—'}명">${v>0?'+':''}${v.toFixed(1)}%</span>`; }
      case 'cr7': { const sw=_crDisplay(r,'pr7',v);
        if(sw) return `<span class="${sw.cls}" title="${sw.title}">${sw.text}</span>`;
        return `<span class="${v>0?'up':(v<0?'dn':'note')}" title="EPS 컨센서스 7일 변화">${v>0?'+':''}${v.toFixed(1)}%</span>`; }
      case 'cr90': { const sw=_crDisplay(r,'pr90',v);
        if(sw) return `<span class="${sw.cls}" title="${sw.title}">${sw.text}</span>`;
        return `<span class="${v>0?'up':(v<0?'dn':'note')}" title="${mkt==='us'?'EPS':'영업이익'} 컨센서스 90일 변화">${v>0?'+':''}${v.toFixed(1)}%</span>`; }
      case 'pr7': return `<span class="${v>0?'up':(v<0?'dn':'note')}" title="EPS 컨센서스 리비전을 주가로 나눈 값(%p) — 기저 EPS 크기와 무관해 종목간 비교 가능. cr7 이 저기저로 과장돼 보일 때 참고">${v>0?'+':''}${v.toFixed(2)}%p</span>`;
      case 'pr30': return `<span class="${v>0?'up':(v<0?'dn':'note')}" title="EPS 컨센서스 리비전을 주가로 나눈 값(%p, 30일) — 기저 EPS 크기와 무관해 종목간 비교 가능">${v>0?'+':''}${v.toFixed(2)}%p</span>`;
      case 'pr90': return `<span class="${v>0?'up':(v<0?'dn':'note')}" title="EPS 컨센서스 리비전을 주가로 나눈 값(%p, 90일) — 기저 EPS 크기와 무관해 종목간 비교 가능">${v>0?'+':''}${v.toFixed(2)}%p</span>`;
      case 'sspr': return `<span class="${v>0?'up':(v<0?'dn':'note')}" title="${mkt==='us'?'직전 발표 매출 vs 발표시점 컨센(Zacks)':'잠정 매출 vs 컨센서스'}">${v>0?'+':''}${v.toFixed(1)}%</span>`;
      case 'tprv90': return `<span class="${v>0?'up':(v<0?'dn':'note')}" title="목표주가 90일 변화(cTB24 우선 · 없으면 일별 백필)">${v>0?'+':''}${v.toFixed(1)}%</span>`;
      case 'tprv': return `<span class="${v>0?'up':(v<0?'dn':'note')}" title="최근 30일 증권사 목표주가 평균 변동률 · 리포트 ${r.tpn??'—'}건(상향 ${r.tpu??'—'}·하향 ${r.tpd??'—'})">${v>0?'+':''}${v.toFixed(1)}%</span>`;
      case 'gap': return `<span class="${v>0?'up':(v<0?'dn':'note')}" title="회사 매출 가이던스 중간값 vs 발표시점 컨센서스">${v>0?'+':''}${v.toFixed(1)}%</span>`;
      case 'gapE': return `<span class="${v>0?'up':(v<0?'dn':'note')}" title="회사 EPS 가이던스 중간값 vs 발표시점 컨센서스">${v>0?'+':''}${v.toFixed(1)}%</span>`;
      /* (2026-08-10) 포털 갭 — 검증 전용이라 색(up/dn)을 쓰지 않는다.
         색은 '판정에 쓰는 값'의 표시이므로, 포털 값까지 물들이면 두 값이 같은 지위로 보인다. */
      case 'gapP': case 'gapEP': {
        const mine=key==='gapP'?r.gapR:r.gapE, nm=key==='gapP'?'매출':'EPS';
        const d=(mine!=null)?(Math.abs(v-mine)<=1?' · 파싱값과 일치':` · 파싱값 ${mine>0?'+':''}${mine.toFixed(1)}% 와 차이 ${Math.abs(v-mine).toFixed(1)}%p`):' · 파싱값 없음';
        return `<span class="note" title="포털(Benzinga) ${nm} 가이던스 vs 컨센 — 우리 8-K 파싱값 검증용${d} · 비트/미스 판정에는 사용하지 않음">⤴${v>0?'+':''}${v.toFixed(1)}%</span>`; }
      case 'r1': case 'r20': return `<span class="${v>0?'up':(v<0?'dn':'note')}" title="발표 직전 종가 대비 ${key==='r1'?'다음 거래일':'20거래일 뒤'}${r.edl?' · 발표 '+r.edl.slice(4,6)+'/'+r.edl.slice(6):''}">${v>0?'+':''}${v.toFixed(1)}%</span>`;
      case 'fnb20': case 'onb20': return `<span class="${v>0?'up':(v<0?'dn':'note')}">${v>0?'+':''}${Math.round(v).toLocaleString()}억</span>`;
      case 'fst': case 'ost': return v>0?`<span class="up">${v.toFixed(0)}일</span>`:'<span class="note">0</span>';
      case 'sr': return `<span class="${v>=5?'dn':''}">${v.toFixed(1)}%</span>`;
      case 'lb': return v==null?'—':wonF(v*1e8);
      case 'lbr': return `<span class="${v>=10?'dn':''}">${v.toFixed(2)}%</span>`;
      case 'srf': return `<span class="${v>=10?'dn':''}">${v.toFixed(1)}%</span>`;
      case 'scov': return `<span class="${v>=5?'dn':''}">${v.toFixed(1)}일</span>`;
      case 'inst': return `${v.toFixed(0)}%`;
      case 'drvj': { const d=DRVSC&&DRVSC[r.c];
        /* 케이스별 문턱 — CASE1 ±1.5 · CASE2 ±1 · CASE3 ±0.75 · US(옵션) ±1 · US(프록시만) ±0.5 */
        const kz = mkt==='us'?(d?'us':'us3'):(!d?3:(d.o?1:2));
        const th=_CASE_TH[kz], prx=(kz===3||kz==='us3');
        const lb2=v>=th?'강세':v<=-th?'약세':'중립';
        return `<span class="${v>=th?'up':(v<=-th?'dn':'note')}" title="CASE${kz==='us'?' US(옵션만)':kz} · 문턱 ±${th} — 파생 z(베이시스·풋콜·IV스큐): |z|≥1 ±0.5점·|z|≥2 ±1점 + 수급 프록시: 외인·기관 20일(시총 0.3%↑ ±0.5·미만 ±0.25)·공매도 5%↑ −0.5/2%↓ +0.25·대차 10%↑ −0.5${prx?' — 파생 미상장이라 프록시만(≈)':''}">${prx?'≈':''}${v>0?'+':''}${_fmtPt(v)} ${lb2}</span>`; }
      case 'align': return `<span class="${v==='정배열'?'up':(v==='역배열'?'dn':'note')}">${E(v)}</span>`;
      case 'macd': return `<span class="${String(v).startsWith('골든')?'up':'dn'}">${E(MACD_DISP[v]||v)}</span>`;
      case 'rsi': return `<span class="${v>=70?'up':(v<=30?'dn':'')}">${(+v).toFixed(0)}</span>`;
      case 'adx': return `<span class="${v<20?'note':''}" title="ADX ≥25 추세장 · 20~25 추세 시작 · <20 횡보">${(+v).toFixed(0)}</span>`;
      case 'gacc': return `<span class="${v>0?'up':(v<0?'dn':'note')}" title="동분기 YoY 가속 = 이번 분기 YoY − 작년 동기 YoY (+면 성장 가속·−면 둔화)">${v>0?'+':''}${v.toFixed(0)}%p</span>`;
      case 'volx': return `<span class="${v>=1.5?'up':'note'}">${(+v).toFixed(1)}배</span>`;
      case 'bb': return (+v).toFixed(0);
    }
    return '';
  }
  function sortVal(r,k){
    if(k==='n') return String(r.n||'');
    if(k==='mk'||k==='sector'||k==='krx'||k==='wics'||k==='wics2'||k==='usind') return String(r[k]||'');
    return colVal(r,k)??-Infinity;
  }
  /* ── 컬럼 관리 패널 (표시 On/OFF · 순서 변경) ── */
  function toggleColPanel(force){
    const p=$('scr_colpanel'); if(!p) return;
    const open = force!=null ? force : (p.style.display==='none');
    p.style.display = open?'':'none';
    if(open) renderColPanel();
  }
  function mvCol(k,d){
    const a=COLST[mkt], i=a.indexOf(k); if(i<0) return;
    const j=i+d; if(j<0||j>=a.length) return;
    a.splice(j,0,a.splice(i,1)[0]); saveCols(); applyTable(); renderColPanel();
  }
  function renderColPanel(){
    const p=$('scr_colpanel'); if(!p) return;
    const cur=COLST[mkt].filter(cAvail);
    const rest=CORDER.filter(k=>cAvail(k)&&cur.indexOf(k)<0);
    p.innerHTML=
      `<div class="cp-h"><b>표시 컬럼</b><span class="note">체크로 표시/숨김 · ▲▼로 순서 변경</span>
         <span class="cp-badge">${colsSaved?'💾 이 PC에 저장됨':'기본값 사용 중'}</span>
         <button class="cp-x" id="cp_reset">컬럼 초기화(default)</button><button class="cp-x" id="cp_all">전부체크</button><button class="cp-x" id="cp_none">전부해제</button><button class="cp-x" id="cp_close">닫기</button></div>
       <div class="cp-sec">표시 중 (${cur.length})</div><div class="cp-list">`+
      cur.map((k,i)=>`<div class="cp-it"><label><input type="checkbox" data-coff="${k}" checked ${k==='n'?'disabled':''}>${E(cpl(k))}</label>
         <span class="cp-mvs"><button class="cp-mv" data-up="${k}" ${i===0?'disabled':''}>▲</button><button class="cp-mv" data-dn="${k}" ${i===cur.length-1?'disabled':''}>▼</button></span></div>`).join('')+
      `</div><div class="cp-sec">추가 가능 (${rest.length})</div><div class="cp-list">`+
      (rest.map(k=>`<div class="cp-it"><label><input type="checkbox" data-con="${k}">${E(cpl(k))}</label></div>`).join('')
        || '<div class="note" style="padding:4px 2px">모두 표시 중</div>')+`</div>`;
    p.querySelectorAll('[data-coff]').forEach(c=>c.onchange=()=>{
      COLST[mkt]=COLST[mkt].filter(x=>x!==c.dataset.coff); saveCols(); applyTable(); renderColPanel(); });
    p.querySelectorAll('[data-con]').forEach(c=>c.onchange=()=>{
      COLST[mkt]=COLST[mkt].concat([c.dataset.con]); saveCols(); applyTable(); renderColPanel(); });
    p.querySelectorAll('[data-up]').forEach(b=>b.onclick=()=>mvCol(b.dataset.up,-1));
    p.querySelectorAll('[data-dn]').forEach(b=>b.onclick=()=>mvCol(b.dataset.dn, 1));
    $('cp_reset').onclick=()=>{ COLST={kr:CDEFAULT.kr.slice(),us:CDEFAULT.us.slice()}; clearCols(); applyTable(); renderColPanel(); };
    /* 전부체크 — 현재 순서는 보존하고 '추가 가능' 전부를 뒤에 붙인다 */
    $('cp_all').onclick=()=>{ const c=COLST[mkt].filter(cAvail);
      COLST[mkt]=c.concat(CORDER.filter(k=>cAvail(k)&&c.indexOf(k)<0)); saveCols(); applyTable(); renderColPanel(); };
    /* 전부해제 — 종목(n)은 행 식별자라 남긴다(체크박스도 disabled) */
    $('cp_none').onclick=()=>{ COLST[mkt]=['n']; saveCols(); applyTable(); renderColPanel(); };
    $('cp_close').onclick=()=>toggleColPanel(false);
  }
  let popCloser=false;
  function applyTable(){
    if(!loaded){ waitScreen(); return; }      // START 전: 대기 화면 유지(빈 표로 덮어쓰지 않음)
    const base=POOL[mkt].filter(pass);            // 하드컷 통과 (2·3단계는 이 집합을 그대로 쓴다)
    const rows=findQ? base.filter(findHit) : base; // 종목 찾기는 1단계 표에만 적용
    rows.sort((a,b)=>{const x=sortVal(a,sort.k),y=sortVal(b,sort.k);
      if(typeof x==='string')return sort.d*x.localeCompare(y); return sort.d*(x-y);});
    $('scr_cnt').innerHTML=`<b>${base.length.toLocaleString()}</b>종 통과 <span style="opacity:.6">/ ${POOL[mkt].length.toLocaleString()} 전체</span>`
      +(findQ?` <span class="findtag">🔎 “${E(findQ)}” ${rows.length.toLocaleString()}종</span>`:'');
    const cols=COLST[mkt].filter(cAvail); const cap=rows.slice(0,400);
    $('scr_tbl').innerHTML='<tr><th id="scr_hashtop" title="클릭: 결과 표를 화면 맨 위로 · 다시 클릭: 필터로 복귀" style="cursor:pointer">#</th>'+cols.map(k=>`<th data-sort="${k}" class="${sort.k===k?(sort.d<0?'dn':'up'):''}">${E(cl(k))}</th>`).join('')
      +'<th class="colbtn" id="scr_colplus" title="표시 컬럼 추가·순서 변경">＋</th></tr>'+
      cap.map((r,i)=>`<tr data-c="${E(r.c)}"><td class="note">${i+1}</td>`+cols.map(k=>`<td class="${CDEF[k].n?'num':''}">${cell(r,k)}</td>`).join('')+'<td></td></tr>').join('')+
      (rows.length?'':`<tr><td colspan="${cols.length+2}" class="note" style="text-align:center;padding:16px">`+
        (findQ?`“${E(findQ)}” — 찾는 종목이 없습니다 <span style="opacity:.6">(하드컷을 통과한 ${base.length.toLocaleString()}종 안에서만 찾습니다)</span>`
             :'조건을 통과한 종목이 없습니다')+`</td></tr>`)+
      (rows.length>400?`<tr><td colspan="${cols.length+2}" class="note" style="text-align:center">상위 400종 표시 (전체 ${rows.length.toLocaleString()}종 — 필터를 좁히세요)</td></tr>`:'');
    $('scr_tbl').querySelectorAll('[data-sort]').forEach(th=>th.onclick=()=>{
      const k=th.dataset.sort; if(sort.k===k)sort.d*=-1; else {sort.k=k; sort.d=(k==='n')?1:-1;} applyTable(); });
    {const pl=$('scr_colplus'); if(pl) pl.onclick=()=>toggleColPanel();}
    {const hc=document.getElementById('scr_hashtop'); if(hc) hc.onclick=()=>{  // (2026-07-22) # 클릭 → 표를 맨 위로(토글)
       const w=document.getElementById('scr_tblwrap'); if(!w) return;
       if(w.getBoundingClientRect().top < 80) window.scrollTo({top:0,behavior:'smooth'});   // 이미 위 → 필터로 복귀
       else w.scrollIntoView({behavior:'smooth',block:'start'});                             // 표를 화면 맨 위로
    };}
    $('scr_tbl').querySelectorAll('tr[data-c]').forEach(tr=>tr.onclick=()=>showDetail(tr.dataset.c));
    applyTblHeight();   // (2026-07-22) 표시 행수 설정을 렌더마다 반영
    renderLegend();
  }
  /* (2026-07-26) 2단계 필터설명 = V·G·M·Q 축의 의미와 계산 방법 */
  function axisLegendHTML(){
    const KR=mkt==='kr';
    const G=[
      ['V — 밸류 (얼마나 싼가)',
       KR?'−forward PER · −PBR · +배당수익률':'−forward PE · −P/B · +배당수익률',
       'PER·PBR이 낮을수록, 배당이 높을수록 +점수. 부호를 뒤집어(−) "쌀수록 좋다"로 통일.'],
      ['G — 성장 (이익이 자라는가)',
       KR?'매출 YoY · 영업이익 YoY · 컨센서스 매출 증가율의 평균 (각 +300% 상한)':'매출성장 · EPS성장의 평균 (각 +300% 상한)',
       '최근 연간 실적 기준. 상한을 둬 일회성 폭증이 랭킹을 왜곡하지 않게 한다.'],
      ['M — 모멘텀 (주가·심리가 위로 향하는가)',
       KR?'수익률 12M · 52주고점比 · 200일선 이격 · 리비전(목표주가 90일 변화)':'수익률 12-1M(최근 1개월 제외) · 52주고점比 · 200일선 이격 · 리비전(EPS 추정 90일 변화)',
       '최근 1개월을 뺀 12개월 수익률(단기 반전 소음 제거) + 고점 근접·장기추세 위 여부 + 애널리스트 상향세.'],
      ['Q — 수익성 (돈을 잘 버는 체질인가)',
       KR?'ROE · −부채비율 (금융업은 부채비율 면제)':'ROE · FCF수익률 · −부채비율 (금융업 면제)',
       '자기자본 수익성이 높고 빚이 적을수록 +점수.']];
    return `<div class="note" style="margin-bottom:8px;line-height:1.6">
      1단계 하드컷을 통과한 전 종목을 4개 팩터 축으로 점수화해 랭킹한다.<br>
      <b>z-score</b> = (지표값 − 전종목 평균) ÷ 표준편차 — <b>0=평균, +1≈상위 16%, −1≈하위 16%</b>.
      축 점수 = 구성 지표들의 z 평균(없는 지표는 제외), <b>종합</b> = 켠 축들의 가중평균(슬라이더 가중치 · 유효 축 최소 3개).
      표의 지표 컬럼들이 각 축 계산에 실제 들어가는 원자료다.</div>`
      +G.map(([t,c,d])=>`<div style="margin-bottom:7px"><b style="font-size:12px">${t}</b><br>
        <span style="font-size:12px">구성: ${c}</span><br><span class="note">${d}</span></div>`).join('');
  }
  /* 필터 설명 — applyTable과 무관하게 단독 렌더 가능(START 전 '? 필터설명' 클릭 대응) */
  function renderLegend(){
    if(stage===2){ const rn=$('scr_revnote'); if(rn) rn.innerHTML=axisLegendHTML(); return; }
    {const rn=$('scr_revnote'); if(rn){
      const g = mkt==='us' ? [
        ['시장·섹터','거래소·업종 분류(Technology·Financial 등)'],
        ['가격','현재가. 기본값 $5↑ = 저가주 제외'],
        ['등락','전일 대비 등락률'],
        ['부채비율','D/E(부채÷자기자본). 금융업 면제'],
        ['유동비율','유동자산÷유동부채(current ratio). 금융업 면제'],
        ['영업적자','최근 연속 영업적자 연수. 기본 3년이상 제외'],
        ['목표주가(구)','→ 목표주가 리비전 30·90일로 통일(중복 제거)'],
        ['상승여력','목표주가 ÷ 현재가 − 1'],
        ['투자의견','컨센서스 등급을 0~100 매수강도로 환산(높을수록 매수)'],
        ['리비전','EPS 추정치 90일 변화율(FY1+FY2) — 애널리스트 상향세'],
        ['애널수','커버하는 애널리스트 수'],
        ['발표 후 경과일','<b>실제 실적발표를 감지한 날</b>로부터 며칠 지났나. 위쪽 <b>어닝일(D±)</b>은 Yahoo·네이버 IR 의 <b>예정일</b>이라 실제 발표일과 다를 수 있는데, 서프라이즈·발표 후 반응 값은 전부 이 실제 발표일 기준이다. 최근 45일치만 추적한다'],
        ['실적 서프라이즈','실제 실적이 증권사 컨센서스를 몇 % 웃돌았나. <b>미국=EPS · 한국=영업이익</b>(잠정공시 vs 컨센). <b>함정</b>: 발표 직전 컨센이 낮아졌다면 쉬운 허들을 넘은 것 — 반드시 <b>컨센30일</b>과 같이 볼 것'],
        ['연속 비트(4Q중)','최근 4분기 중 컨센 상회 횟수. 꾸준히 이기는 회사는 다음 분기도 이길 확률이 높다(서프라이즈 지속성). 평균 대신 중위값 사용 — 적자→흑자 분기 하나가 평균을 왜곡한다(실측 INTC 평균 +1,361%)'],
        ['컨센 7·30·90일 리비전','진행분기·다음분기 EPS 컨센서스 추정치의 그 시점 대비 변화율(평균). <b>가이던스가 시장에 어떻게 소화됐나</b>의 결과다. +5%↑=애널리스트가 전망 상향. 미국은 즉시 산출, <b>한국(컨센30일=영업이익 리비전)은 스냅샷 30일 누적 후(2026-09-08~)</b>. <b>주의</b>: 기저(그 시점 EPS 추정치)가 0 근처인 종목은 %가 크게 부풀 수 있어(예: 0.09→1.38 = +1452%, 실제 영향은 작음) 그런 경우 화면 값이 자동으로 <b>주가 대비 %p</b>로 바뀐다(아래 항목 참고) — 값은 정확하고, 표시 방식만 바뀌는 것'],
        ['리비전 주가대비 7·30·90일','위 컨센 리비전과 같은 원자료를 <b>주가로 나눈 값</b>(=ΔEPS÷현재가, %p) — 기저 EPS 크기와 무관해 종목간 비교·정렬에 더 적합하다. 컨센 리비전 컬럼이 기저가 작아 %가 과장될 때 화면에 자동으로 이 값이 대신 표시되며, 독립 필터·컬럼으로도 선택 가능'],
        ['가이던스 갭','회사가 제시한 다음 분기 전망 중간값 vs 애널리스트 컨센서스. <b>주가보다 빠른 유일한 신호</b>(SEC 8-K 보도자료 실시간 파싱). 실측 정확도 9/12 — 못 잡으면 빈칸(틀린 값보다 낫다). 애플처럼 숫자 가이던스를 안 주는 회사도 있다. <b>한국은 가이던스 공시 관행 없음</b>'],
        ['발표 후 1일','발표 <b>직전</b> 종가 대비 다음 거래일 등락률(장 마감 후 발표가 많아 당일 종가 기준이면 반응이 잘린다). <b>서프 + 인데 여기가 − 면 가이던스 쇼크</b> — 샌디스크 케이스'],
        ['발표 후 20일(PEAD)','발표 후 20거래일 수익률. PEAD(발표후 표류) = 서프라이즈 방향으로 주가가 수 주간 계속 흐르는 현상. 발표 다음 날 진입해도 남은 구간이 있다는 뜻'],
        ['목표주가 30일 리비전','US 미제공 — 미국은 이익추정 리비전(<b>컨센30일</b>)이 정식 지표라 그쪽을 쓴다'],
        ['PER','forward P/E(예상 순이익 대비 주가). 낮을수록 저평가'],
        ['PBR','P/B(순자산 대비 주가). 낮을수록 저평가'],
        ['배당','배당수익률'],
        ['성장','매출·EPS 성장률 평균'],
        ['매출성장','매출 전년동기比 성장률'],
        ['이익성장','EPS 전년동기比 성장률'],
        ['성장가속','이번 분기 YoY − 작년 동기 YoY(%p). +면 성장 가속·−면 둔화. 같은 분기끼리 비교라 계절성 제거된 모멘텀. US=SEC 실측(주1회)'],
        ['ROE','자기자본이익률(순이익÷자기자본)'],
        ['수익률 12-1M','12개월 전 → 1개월 전 구간의 주가 수익률 = (1+1Y수익률)÷(1+1M수익률)−1. 최근 1개월을 <b>일부러 제외</b>한 모멘텀 — 단기 급등 직후의 반전 위험을 걸러낸다. <b>한국은 12M(순수 12개월 수익률)</b>이라 정의가 다르다'],
        ['수익률 1M·3M·6M','해당 기간 주가 수익률'],
        ['변동성(20일)','최근 20일 일간수익률 표준편차 — 낮을수록 안정'],
        ['회전율','거래대금(3개월 평균) ÷ 시가총액 — 시총 대비 유동성'],
        ['영업이익률','operating margin(TTM, Yahoo)'],
        ['PEG','forward PE ÷ EPS 성장률 — 1 이하면 성장 대비 저평가'],
        ['PSR','P/S(TTM) — 적자 성장주 밸류에이션. 높으면 기본은 고평가 신호이나, 고성장이 뒷받침되면 "성장 프리미엄"으로 정당화됨 → 매출성장·성장가속과 반드시 교차 확인'],
        ['흑자전환·수급·공매도·대차잔고','미국 미제공 — 연간 영업이익 배열·투자자별 수급·공매도·대차잔고 데이터 없음'],
        ['어닝일(D±)','실적발표 D-day (Yahoo earnings date) — D-면 발표 전, D+면 발표 후(사후 추적: D+1~D+7 프리셋)'],
        ['고점比','52주 최고가 대비 현재가 위치 (−10% = 고점 근접)'],
        ['장기 이평선','<b>한국 120일·미국 200일</b> 이동평균 대비 현재가 — 장기 추세(차트선). 기본 −30%↑ = 심각한 하락추세 제외'],
        ['단기·중기 이평선','해당 이동평균 대비 현재가 위치 — 한국 20·60일 / 미국 20·50일(차트선)'],
        ['이평배열','정배열=단기선이 장기선 위(상승 구조) · 반대=역배열 — 한국 20>60>120 / 미국 50>100>200 (차트 이평선과 동일)'],
        ['RSI(14)','상대강도지수 — 30↓ 과매도 · 70↑ 과매수'],
        ['MACD','12-26 EMA 차이 vs 시그널(9). 앞의 <b>골든/데드</b>=시그널선 돌파 방향, 괄호의 <b>0선↑/↓</b>=MACD 가 0선 위인지 아래인지. 골든(0선↓)=하락 국면에서 막 돌아선 상승 전환 초기 · 데드(0선↑)=상승 국면에서 막 꺾인 하락 전환 초기'],
        ['볼린저밴드','볼린저(20,2) 밴드 내 위치 — 0=하단 · 100=상단'],
        ['거래량배수','당일 거래량 ÷ 3개월 평균(미국)/20일 평균(한국). <b>장중에는 하루치로 환산해 추정</b>(일중 거래량이 개장·마감에 몰리는 U자 곡선을 반영) → 차트의 진행 중인 마지막 봉과는 값이 다를 수 있다'],
        ['배당성향','배당금÷순이익(payout ratio)'],
        ['상장기간','상장 후 경과 연수'],
        ['증권 구분','EQUITY만(ETF·워런트 제외) — 고정']
      ] : [
        // (2026-07-18) 필터 바 나열 순서(KEYS)와 동일하게 정렬 + 기술 필터 7종 설명 추가
        ['시장','거래소 구분(KOSPI·KOSDAQ)'],
        ['가격','현재가. 기본값 1,000원↑ = 저가주 제외'],
        ['등락','전일 대비 등락률'],
        ['시가총액','보통주 시가총액. 기본 3,000억↑'],
        ['거래대금','최근 거래일 거래대금. 기본 30억↑ = 유동성 하한'],
        ['부채비율','부채÷자기자본. 금융업 면제'],
        ['유동비율','당좌자산÷유동부채(당좌비율) — 단기 지급능력. 금융업 면제'],
        ['영업적자','최근 연속 영업적자 연수. 기본 3년이상 제외'],
        ['상장기간','상장 후 경과 연수'],
        ['장기 이평선','<b>한국 120일·미국 200일</b> 이동평균 대비 현재가 — 장기 추세(차트선). 기본 −30%↑ = 심각한 하락추세 제외'],
        ['20일선','20일 이동평균 대비 현재가 — 단기 추세'],
        ['50일선','50일 이동평균 대비 현재가 — 중기 추세'],
        ['이평배열','차트 이평선 기준 — <b>한국 20>60>120</b> · <b>미국 50>100>200</b>. 정배열=단기선이 장기선 위(상승추세장), 역배열=아래(하락추세장), 혼조=교차(전환) 구간. 차트에 그려진 이평선과 동일 기준이라 눈으로 대조 가능'],
        ['RSI(14)','상대강도지수 — 30 이하 과매도(반등 후보), 50 상회 = 상승 모멘텀, 70 이상 과매수(조정 경계)'],
        ['ADX(14)','추세의 <b>강도</b>(방향 아님) — 25 이상이면 추세장, 20 이하면 횡보장. RSI(과열도)·MACD(방향)와 정보축이 달라 겹치지 않는다. 이평 크로스·모멘텀 전략은 횡보장에서 잘 깨지므로 그 구간을 걸러낼 때 쓴다. <b>한국 전용</b> — 미국은 일괄 시세조회가 종가만 줘서 고가·저가가 없어 산출 불가'],
        ['거래량배수','최근 거래일 거래량 ÷ 직전 20일 평균 — 1.5배↑ 급증 = 추세 전환/돌파 확인 신호'],
        ['MACD','(12,26,9) 상태. 앞의 <b>골든/데드</b>=시그널선 돌파 방향, 괄호의 <b>0선↑/↓</b>=MACD 의 0선 위/아래 위치. 골든(0선↑)=강한 상승 · 골든(0선↓)=상승 전환 초기(0선 아래 반등) · 데드(0선↑)=하락 전환 초기(고점권 꺾임) · 데드(0선↓)=강한 하락'],
        ['볼린저밴드','볼린저밴드(20,2) 내 위치(%b) — 0=하단(과매도권), 50=중심선, 100 이상=상단 돌파(거래량 동반 시 추세가속)'],
        ['수익률 12M','최근 12개월 주가 수익률(현재가 ÷ 12개월 전 종가). <b>미국은 12-1M</b>(최근 1개월 제외)이라 정의가 다르다'],
        ['수익률 1M·3M·6M','해당 기간 주가 수익률'],
        ['변동성(20일)','최근 20일 일간수익률 표준편차 — 낮을수록 안정'],
        ['회전율','거래대금 ÷ 시가총액 — 시총 대비 유동성'],
        ['영업이익률','영업이익 ÷ 매출액 (최근 연간 실적, 네이버)'],
        ['PEG','PER ÷ 영업이익 성장률 — 1 이하면 성장 대비 저평가 (미국은 EPS 성장률 기준)'],
        ['PSR','시가총액 ÷ 매출액(최근 연간) — 적자 성장주 밸류에이션. 높으면 기본은 고평가 신호이나, 고성장이 뒷받침되면 "성장 프리미엄"으로 정당화됨 → 매출성장·성장가속과 반드시 교차 확인'],
        ['흑자전환','직전 연도 영업적자 → 최근 연도 흑자로 전환 (연간 — 확정적이지만 느림)'],
        ['분기흑자YoY','전년 동분기 적자 → 당분기 흑자 전환 — 연간보다 최대 1년 빠르고 계절성 안전 (분기 실적, 주1회 갱신)'],
        ['분기흑자QoQ','직전 분기 적자 → 당분기 흑자 전환 — 가장 빠른 포착. 단 특정 분기만 흑자인 계절 패턴을 오인할 수 있음(계절성 주의)'],
        ['마진변화','당분기 영업이익률 − 전년동기 영업이익률(%p) — 마진 확대/축소 방향. 연간 영업이익률(수준)과 별개의 모멘텀 신호'],
        ['외인·기관수급(20일)','KIS 종목별 투자자 — 최근 20거래일 누적 순매수 금액(억원)'],
        ['외인·기관연속매수','최근 며칠 연속 순매수 중인가(일)'],
        ['공매도비중','최근 거래일 공매도 거래량 ÷ 전체 거래량(%) — 5%↑ 과열 경계 (KIS)'],
        ['파생·수급판정','<b>파생 z</b>(베이시스·풋콜·IV스큐): |z|≥1 ±0.5점 · |z|≥2 ±1점 + <b>수급 프록시</b>: 외인·기관 20일 순매수(시총 0.3%↑ ±0.5 · 미만 ±0.25), 공매도 5%↑ −0.5/2%↓ +0.25, 대차 10%↑ −0.5. <b>+1점↑ 강세 · −1점↓ 약세</b>. 파생 미수록 종목은 프록시만(≈)'],
        ['대차잔고비율','대차잔여주식수 ÷ 상장주식수(%) — 공매도 대기물량 프록시, 높을수록 하락배팅 부담 (금융위 주식대차정보 · 기준일 +1영업일 13시 갱신)'],
        ['어닝일(D±)','실적발표 D-day (네이버 IR 일정 — 대형주 위주) — D-면 발표 전, D+면 발표 후(사후 추적)'],
        ['고점比','52주 최고가 대비 현재가 위치 (−10% = 고점 근접)'],
        ['외인보유비중','외국인 보유 비중'],
        ['목표주가','애널리스트 컨센서스 목표주가. 필터는 \'있는 종목만\' 토글'],
        ['상승여력','목표주가 ÷ 현재가 − 1'],
        ['투자의견','컨센서스 등급을 0~100 매수강도로 환산(높을수록 매수)'],
        ['리비전','목표주가 90일 변화율(누적/백필) — 애널리스트 상향세'],
        ['애널수','KR 미제공'],
        ['발표 후 경과일','<b>실제 실적발표를 감지한 날</b>로부터 며칠 지났나. 위쪽 <b>어닝일(D±)</b>은 Yahoo·네이버 IR 의 <b>예정일</b>이라 실제 발표일과 다를 수 있는데, 서프라이즈·발표 후 반응 값은 전부 이 실제 발표일 기준이다. 최근 45일치만 추적한다'],
        ['영업익 서프라이즈','DART 잠정 영업이익 vs WISEreport 컨센서스(최근 3개월 증권사 추정 평균). <b>함정</b>: 발표 직전 컨센이 낮아졌다면 쉬운 허들을 넘은 것 — 리비전과 같이 볼 것'],
        ['매출 서프라이즈','DART 잠정 매출 vs 컨센서스 매출. 영업익보다 조작·일회성 여지가 적어 <b>수요의 방향</b>을 보는 데 적합. AI·수주 산업은 매출 서프가 더 중요한 경우가 많다'],
        ['영업익추정 리비전 30일·90일','영업이익 컨센서스 추정치의 30·90일 전 대비 변화율(일별 스냅샷 차분). <b>30일=2026-09-08~ · 90일=2026-11-07~ 유효</b>. 그 전까지는 목표주가 리비전을 대용으로 쓸 것'],
        ['목표주가 리비전 30일·90일','최근 30·90일 증권사 리포트의 목표주가 평균 변동률(WISEreport 증권사별 표 — 오늘 바로 유효). 90일은 표가 안 잡히는 종목이면 기존 일별 백필값으로 대체. <b>주의</b>: 목표가=이익추정×배수라 배수 조정만으로도 움직인다'],
        ['연속 비트(4Q중)','KR 미제공 — 분기별 서프라이즈 이력을 주는 무료 소스가 없다'],

        ['가이던스 갭','한국은 기업이 다음 분기 실적 전망을 공시하는 관행이 없다. 대신 <b>실적 서프라이즈</b>(잠정 vs 컨센)가 같은 역할을 한다'],
        ['발표 후 1일','발표 <b>직전</b> 종가 대비 다음 거래일 등락률. <b>서프 + 인데 여기가 − 면</b> 시장이 향후 전망을 나쁘게 봤다는 뜻'],
        ['발표 후 20일(PEAD)','발표 후 20거래일 수익률. PEAD(발표후 표류) = 서프라이즈 방향으로 주가가 수 주간 계속 흐르는 현상'],

        ['성장','매출·영업이익 성장률 평균'],
        ['매출성장','매출액 전년동기比 성장률'],
        ['이익성장','영업이익 전년동기比 성장률'],
        ['성장가속','이번 분기 YoY − 작년 동기 YoY(%p). +면 성장 가속·−면 둔화. 같은 분기끼리 비교라 계절성 제거된 모멘텀. KR=KIS 손익·US=SEC 실측(주1회 갱신)'],
        ['PER','추정 주가수익비율(순이익 대비 주가). 낮을수록 저평가'],
        ['PBR','주가순자산비율(순자산 대비 주가). 낮을수록 저평가'],
        ['ROE','자기자본이익률(순이익÷자기자본)'],
        ['배당성향','주당배당÷EPS'],
        ['배당','배당수익률'],
        ['증권 구분','보통주만 — 고정']
      ];
      // (2026-07-26) 항목이 많아 다단 배열로 — 폭에 따라 자동 2~3열, 항목 중간 끊김 방지.
      //   각 항목 라벨 옆에 소속 카테고리 배지([시세]·[기술적 지표] 등) 표시.
      rn.innerHTML=`<div class="lgcols">`+g.map(x=>{
        const cat=legendCat(x[0]);
        /* (2026-07-23) 설명 안의 <b> 강조만 안전하게 허용 — 나머지는 이스케이프 유지(주입 방지) */
        return `<div class="lgit"><b>${x[0]}</b>${cat?` <span class="lgcat">[${cat}]</span>`:''} = ${E(x[1]).replace(/&lt;(\/?)b&gt;/g,'<$1b>')}</div>`;
      }).join('')+`</div>`;
    }}
  }
  /* (2026-07-26) 필터 라벨 → 카테고리. 상세 요약 그룹(GCAT)을 라벨 기준으로 역참조 */
  const GCAT=[['시세',['px','chg','cap','tv','turn']],['기간수익률',['r1m','r3m','r6m','mom']],
    ['기술적 지표',['hi','v200','v50','v20','align','rsi','macd','bb','volx','vol20']],
    ['컨센서스',['ern','tp','upside','recn','rev','nan']],
      ['실적발표',['edld','spr','sspr','sprb','cr7','cr30','cr90','pr7','pr30','pr90','tprv','tprv90','gap','gapP','gapE','gapEP','r1','r20']],
    ['밸류·수익성',['per','peg','pbr','psr','divy','payout','dinc','dgy','dcyc','mdd5','roe','opm']],
    ['성장',['grw','revg','opg','tob']],['수급',['fnb20','onb20','fst','ost','sr','lbr','frgn','frgn4w','drvj']],
    ['건전성',['de','cr','oploss']],['기타',['age']]];
  const _catByLabel=(()=>{ const m={};
    for(const [cat,ks] of GCAT) for(const k of ks){ const c=CDEF[k]; if(c) m[c.l]=cat; }
    // 필터 전용/복합 라벨 보정 (컬럼 라벨과 다르게 표기되는 것들)
    Object.assign(m,{ '시장':'시세','섹터':'시세','가격':'시세','등락':'시세','시가총액':'시세','거래대금':'시세','회전율':'시세',
      '수익률 12-1M':'기간수익률','수익률 12M':'기간수익률','수익률 1M·3M·6M':'기간수익률','수익률 1M':'기간수익률','수익률 3M':'기간수익률','수익률 6M':'기간수익률','변동성(20일)':'기간수익률',
      'RSI(14)':'기술적 지표','거래량배수':'기술적 지표','MACD':'기술적 지표','볼린저밴드':'기술적 지표','이평배열':'기술적 지표','200일선':'기술적 지표','20일선':'기술적 지표','50일선':'기술적 지표','고점比':'기술적 지표',
      '목표주가':'컨센서스','상승여력':'컨센서스','투자의견':'컨센서스','리비전':'컨센서스','애널수':'컨센서스','어닝일(D±)':'컨센서스',
      'PER':'밸류·수익성','PEG':'밸류·수익성','PBR':'밸류·수익성','PSR':'밸류·수익성','ROE':'밸류·수익성','배당성향':'밸류·수익성','배당':'밸류·수익성','영업이익률':'밸류·수익성',
      '성장':'성장','매출성장':'성장','이익성장':'성장','성장가속':'성장','흑자전환':'성장','분기흑자YoY':'성장','분기흑자QoQ':'성장','마진변화':'밸류·수익성',
      '외인·기관수급(20일)':'수급','외인·기관연속매수':'수급','공매도비중':'수급','대차잔고비율':'수급','대차잔고':'수급','흑자전환·수급·공매도·대차잔고':'수급','외인보유비중':'수급',
      '부채비율':'건전성','유동비율':'건전성','영업적자':'건전성','상장기간':'기타','증권 구분':'기타' });
    return m; })();
  function legendCat(label){ return _catByLabel[label] || null; }
  function apply(){ applyTable(); renderChips(); }

  /* ── 종목 상세: 종가 기준 일봉 차트(기술지표) + 지표 요약 ── */
  let dcode=null;
  function hideDetail(){
    if(_EXT){ _extClose(); const ed=document.getElementById('etf_detail'); if(ed) ed.style.display='none'; return; }
    const d=$('scr_detail'); if(d) d.style.display='none'; dcode=null;
    /* (2026-08-09) 상세를 보는 동안 미룬 표 갱신을 닫을 때 반영 */
    try{ if(loaded && stage===1) refresh(); }catch(e){} }
  {const b=$('sd_close'); if(b) b.onclick=hideDetail;}
  /* 차트 소스: canvas(자체) / tv(TradingView 임베드). 네이버는 새창(임베드 시 시세 차단)
     종목을 열면 항상 자체차트로 시작한다 — TradingView 는 그 종목을 보는 동안만 유지(저장 안 함) */
  let chartSrc='canvas';
  document.querySelectorAll('.csrc').forEach(b=>b.onclick=()=>{
    chartSrc=b.dataset.s;
    if(dcode) showDetail(dcode);
  });
  {const nv=$('sd_nvopen'); if(nv) nv.onclick=()=>{ if(!dcode) return;
    const url = mkt==='kr' ? `https://finance.naver.com/item/fchart.naver?code=${encodeURIComponent(dcode)}`
                           : `https://search.naver.com/search.naver?query=${encodeURIComponent(dcode+' 주가')}`; // 해외는 네이버 증권 카드로
    window.open(url,'nmr_nv','width=1150,height=900'); };}
  {const tvp=$('sd_tvopen'); if(tvp) tvp.onclick=()=>{ if(!dcode) return;
    const sym = mkt==='kr' ? 'KRX:'+dcode : dcode;        // 사이트에서는 KRX 정상 제공
    window.open(`https://kr.tradingview.com/chart/?symbol=${encodeURIComponent(sym)}`,'nmr_tv','width=1300,height=900'); };}
  {const yh=$('sd_yhopen'); if(yh) yh.onclick=()=>{ if(!dcode) return;
    let sym=dcode;
    if(mkt==='kr'){ const r=POOL.kr.find(x=>x.c===dcode); sym=dcode+(r&&r.mk==='KOSDAQ'?'.KQ':'.KS'); } // 야후 한국 심볼
    window.open(`https://finance.yahoo.com/chart/${encodeURIComponent(sym)}`,'nmr_yh','width=1150,height=900'); };}

  /* ── (2026-07-29) ETF 차트 이식 모드 ─────────────────────────────────
     ETF 상세가 종목 차트 박스(#sd_chartbox)를 통째로 가져다 쓴다 — 분봉·주기·소스버튼·
     보조지표·장중 자동갱신을 종목과 동일하게 제공(코드 중복 없음).
     closure 의 mkt/dcode 를 잠시 ETF 것으로 바꾸며, 종목 상세를 다시 열거나 닫으면 원복. */
  let _EXT=null;
  function _extClose(){
    if(!_EXT) return;
    const box=$('sd_chartbox');
    if(box&&_EXT.ph&&_EXT.ph.parentNode) _EXT.ph.parentNode.replaceChild(box,_EXT.ph);
    mkt=_EXT.prevMkt; dcode=null;
    _EXT=null;
  }
  async function _extShow(m2, code, name, lastHTML){
    const box=$('sd_chartbox'), mount=document.getElementById('ed_chartmount');
    if(!box||!mount) return;
    if(!_EXT){
      _EXT={prevMkt:mkt, ph:document.createElement('div'), code};
      box.parentNode.insertBefore(_EXT.ph, box);
      mount.appendChild(box);
    }
    _EXT.code=code;
    mkt=m2; dcode=code; chartSrc='canvas';
    $('sd_name').textContent=name||code;
    $('sd_code').textContent=code;
    $('sd_last').innerHTML=lastHTML||'';
    {const sb=$('sd_srcbtns'); if(sb) sb.style.display='flex';}
    _bindTF(); _bindAuto(); _applyAuthTF();
    /* 이식 모드에선 TV 임베드 토글은 숨김(새창 버튼은 동작) — 자체차트 고정 */
    document.querySelectorAll('.csrc').forEach(b=>{
      b.style.display=(b.dataset.s==='tv')?'none':'';
      b.classList.toggle('on', b.dataset.s==='canvas');
    });
    $('sd_naver').style.display='none';
    _CVS_IDS.forEach(id=>{const e=$(id); if(e) e.style.display='block';});
    await _canvasFlow(code);
  }
  window.nmrEtfChart={open:_extShow, close:_extClose, active:()=>!!_EXT};
  /* (2026-07-29) 자체차트 플로우 추출 — 종목 상세와 ETF 상세(이식 모드)가 공유 */
  const _CVS_IDS=['sd_main','sd_vol','sd_rsi','sd_macd','sd_inv'];
  async function _canvasFlow(c){
    const cvs=_CVS_IDS;
      $('sd_naver').style.display='none';
      cvs.forEach(id=>{const e=$(id); if(e)e.style.display='block';});
      $('sd_src').textContent='차트 불러오는 중…';
      try{
        const D=await (await fetch(`/api/chart/${mkt}/${encodeURIComponent(c)}?tf=${_TF}${_ppq()}`)).json();
        if(dcode!==c) return;                     // 로드 중 다른 종목 클릭됨
        /* (2026-08-05) 분봉 401(세션 만료) — 조용히 실패하지 않고 안내 + 일봉 폴백 */
        if(D&&D.detail&&!(D.t||[]).length){
          _AUTH=false; _applyAuthTF(); _TF='d';
          $('sd_src').innerHTML='🔒 세션이 만료되어 분봉을 열 수 없습니다 — <b>다시 로그인하면 분봉 이용 가능</b> (일봉으로 전환합니다)';
          return _canvasFlow(c);
        }
        _LASTFETCH=Date.now();
        drawAll(D);
        const _src = mkt==='kr'?'네이버':'Yahoo';
        const _ma  = (_isMin()||_TF!=='d') ? '5/20/60/120' : (MASET[mkt]||MASET.us).map(m=>m[0]).join('/');
        /* (2026-07-21) 각주에 <b> 강조가 있어 textContent 로 넣으면 태그가 글자로 보인다.
           내용이 전부 우리 코드가 만든 정적 문자열이라 innerHTML 로 넣어도 안전하다. */
        $('sd_src').innerHTML =
          `${TFL[_TF]}봉 · ${_src} · 이동평균 ${_ma}`
          + (_TF==='d' ? (mkt==='kr' ? '일(한국식 — 60=수급선 · 120=경기선 · 240=1년선)'
                                     : '일(해외식 — 골든/데드 크로스는 50·200 교차 기준)')
                       : (_isMin()?'봉':'')) 
          + ` · 볼린저(20,2) 회색밴드 · 매물분석도 · RSI(14,9) · ADX(14) · MACD(12,26,9)`
          + (_TF==='d'&&mkt==='kr' ? ' · 누적순매수(외국인·기관·개인 — 1개월 이전 개인은 −(외인+기관) 추정 점선)'
                                   : ' · OBV(누적 거래량) — <b>OBV 는 거래량이 어느 방향에 실렸나</b>를 본다.'
                                     + ' 주가와 <b>같은 방향</b>이면 추세가 진짜(확인), <b>안 따라오면</b> 다이버전스로 경고:'
                                     + ' ①주가↑·OBV↑ = 상승 확인(매수에 물량) ②주가↑·OBV정체 = 분산 의심(상승이 비어 있음)'
                                     + ' ③주가↓·OBV↓ = 하락 확인(매도에 물량 실림 — 정상 하락) ④주가↓·OBV정체 = 매집 의심(하락에 물량 안 실림 → 매도세 소진·반등 가능).'
                                     + ' 단독 판단 말고 체결강도·수급과 같이 볼 것')
          + (_isMin() ? `  ⏱ 단타용 — 흐름은 5분, 진입·청산 순간만 1분으로 내려 보는 조합이 일반적입니다.`
              + ` 차트만으로는 체결 타이밍이 부족해 <b>아래에 호가·체결강도·투자자 가집계를 KIS 실전계정 실시간</b>으로 붙였습니다`
              + ` (네이버 호가·거래원은 20분 지연이라 쓰지 않습니다).`
              + ` 일봉으로 바꾸면 그 자리에 마감 후 확정치인 외국인·기관 순매매 표가 나옵니다.`
              + ` 차트는 '자리'(고점권인지, 매물대 위인지)를 보는 도구입니다.` : '')
          /* (2026-07-20) 일봉 장중엔 마지막 봉이 '아직 안 끝난 하루'라 평균선과 직접 비교하면 과소해 보인다.
             분봉은 봉 자체가 짧아 이 왜곡이 의미 없으므로 일봉일 때만 붙인다. */
          + ((()=>{ const g=window.__volProg;
             if(!g||_TF!=='d') return '';
             const u=n=>n>=1e8?(n/1e8).toFixed(1)+'억':n>=1e4?Math.round(n/1e4).toLocaleString()+'만':Math.round(n).toLocaleString();
             const x1=g.ma63?(g.now/g.ma63).toFixed(2):'—', x2=g.ma63?(g.proj/g.ma63).toFixed(2):'—';
             return ` · ⚠ 맨 오른쪽 봉은 아직 진행 중 — 장 ${Math.round(g.f*100)}% 경과 시점의 ${u(g.now)}주(빗금)이며 평균선과 비교하면 ${x1}배로 보입니다.`
                  + ` 점선은 이 페이스로 마감까지 갔을 때의 예상치 ${u(g.proj)}주(${x2}배)로, 표의 거래량배수가 이 값입니다.`; })());
        $('sd_tfbar').style.display='flex';
        /* (2026-08-04) 정규장/시간외 토글 노출 갱신 — KR↔US 전환·주기 변경 시에도 정확히 */
        {const pw=$('sd_ppwrap');
         if(pw){ pw.style.display=_isMin()?'inline-flex':'none';
           pw.querySelectorAll('.ppb').forEach(b=>b.classList.toggle('on', (b.dataset.pp==='1')===_PP)); }}
        $('sd_tfnote').textContent = (_isMin()
          ? `${D.t?D.t.length:0}봉 · 최근 ${new Set((D.t||[]).map(z=>z.slice(0,8))).size}거래일`
          : `${D.t?D.t.length:0}봉`)
          + (D.ppf?' · ⚠ 시간외 분봉 미제공 종목 — 정규장 표시':'')
          + (D.ppo?' · ⏰ 당일 시간외단일가(16:00~18:00) 포함 — ETF는 NXT 미상장이라 프리·애프터 없음':'');
        loadInv(c);                               // 수급 패널은 별도 로드(차트를 막지 않음)
        loadDisc(c);                              // 공시 마커도 별도 로드
        loadEarn(c);                              // 실적발표일 1년치(US=SEC 8-K · KR=DART)
        loadKrFin(c);                             // KR 분기 재무표·목표주가 변동·컨센 추이
        loadKrSeg(c);                             // KR 매출 구성·제품 정보 (DART·WISE·IR 비교)
        loadBottom(c);                            // 차트 하단 패널(호가/체결 또는 순매매 표)
      }catch(e){ $('sd_src').textContent='차트 로드 실패: '+e; }
  }
  async function showDetail(c){
    /* (2026-07-29) ETF 이식 모드 — 주기/소스 버튼이 showDetail(dcode)를 부르므로,
       같은 코드(=ETF 차트 재조회)면 이식 모드로 재실행하고, 다른 코드(종목 열기)면 원복 */
    if(_EXT){
      if(c===_EXT.code) return _extShow(mkt, c, $('sd_name').textContent, $('sd_last').innerHTML);
      _extClose();
    }
    const r=POOL[mkt].find(x=>x.c===c); if(!r) return;
    /* 새 종목을 열 때는 항상 자체차트부터. (같은 종목에서 소스 버튼을 누른 경우는 c===dcode 라 유지) */
    if(c!==dcode) chartSrc='canvas';
    dcode=c;
    $('scr_detail').style.display='';
    $('sd_name').textContent = mkt==='kr'? (r.n||'') : (r.kn? `${r.c} ${r.kn}` : r.c);
    $('sd_code').textContent = mkt==='kr'? r.c : (r.n||'');
    $('sd_last').innerHTML = cell(r,'px')+' '+cell(r,'chg');
    renderSum(r);
    loadDeriv(c);                                // (2026-07-24) 종목 파생 포지셔닝 — 파생 상장 종목만 표시
    const cvs=['sd_main','sd_vol','sd_rsi','sd_macd','sd_inv'];
    /* KRX 심볼은 TradingView 임베드 위젯에서 거래소 정책상 차단 → KR은 자체차트만 */
    const mode = mkt==='kr' ? 'canvas' : chartSrc;
    {const sb=$('sd_srcbtns'); if(sb) sb.style.display='flex';}
    _bindTF();                                   // 주기 선택(분봉·일·주·월) 배선 — 최초 1회
    _bindAuto();                                 // 장중 자동 갱신 타이머 — 최초 1회
    _applyAuthTF();                              // 분봉 잠금 상태 반영
    document.querySelectorAll('.csrc').forEach(b=>{
      b.style.display = (b.dataset.s==='tv' && mkt==='kr') ? 'none' : '';
      b.classList.toggle('on', b.dataset.s===mode);
    });
    if(mode==='tv'){
      cvs.forEach(id=>{const e=$(id); if(e)e.style.display='none';});
      $('sd_naver').style.display='';
      const wrap=$('sd_nwrap'), ifr=$('sd_nifr');
      ifr.style.width='100%'; ifr.style.marginTop='0'; ifr.style.transform='none'; ifr.style.height='620px';
      wrap.style.height='620px';
      const sym = mkt==='kr' ? 'KRX:'+c : c;
      const cfg={autosize:true,symbol:sym,interval:'D',theme:'light',style:'1',locale:'kr',
                 withdateranges:true,hide_side_toolbar:false,allow_symbol_change:false,save_image:false,
                 hide_volume:false,support_host:'https://www.tradingview.com'};
      /* 심볼을 쿼리에도 포함 — 해시만 바뀌면 iframe이 리로드되지 않는 문제 방지 */
      const src=`https://www.tradingview-widget.com/embed-widget/advanced-chart/?locale=kr&sym=${encodeURIComponent(sym)}#${encodeURIComponent(JSON.stringify(cfg))}`;
      if(ifr.getAttribute('src')!==src) ifr.setAttribute('src',src);
      $('sd_nlink').href = mkt==='kr' ? `https://finance.naver.com/item/main.naver?code=${encodeURIComponent(c)}`
                                      : `https://finance.yahoo.com/quote/${encodeURIComponent(c)}`;
      $('sd_src').textContent='TradingView 인터랙티브 차트 — 상단에서 1분~월봉 전환, 지표 버튼으로 보조지표 추가/삭제, 드래그·휠로 기간 조절.';
    } else {
await _canvasFlow(c);
    }
    if(autoScroll) $('scr_detail').scrollIntoView({block:'nearest',behavior:'smooth'});
  }
  function renderSum(r){
    // (2026-08-02) 기업개요 — 네이버 온디맨드(/api/overview, 서버 24h 캐시), 요약표 위에 표시
    { const ov=$('sd_ov');
      if(ov){ const oc=String(r.code||r.sym||r.symbol||''); ov.style.display='none'; ov.dataset.c=oc;   // KR=code · US=sym
        if(oc) fetch(`/api/overview?mkt=${mkt}&code=${encodeURIComponent(oc)}`).then(x=>x.ok?x.json():null).then(o=>{
          if(!o||!(o.lines||[]).length||ov.dataset.c!==oc) return;   // 응답 도착 전 다른 종목 선택 시 무시
          ov.style.display='';
          ov.innerHTML=`<div class="sgt">기업개요</div>
            <div style="font-size:12px;line-height:1.65;padding:2px 2px 0">${o.lines.slice(0,6).map(t=>'· '+E(t)).join('<br>')}</div>`;
          _ovHist();   // (2026-08-09) 최근연혁이 먼저 도착해 있었으면 다시 붙인다(innerHTML 덮임)
        }).catch(()=>{}); } }
    const G=[['시세',['px','chg','cap','tv','turn']],
             ['기간수익률',['r1m','r3m','r6m','mom']],
             ['기술적 지표',['hi','v200','v50','v20','align','rsi','macd','bb','volx','vol20']],
             ['컨센서스',['ern','tp','upside','recn','rev','nan']],
      ['실적발표',['edld','spr','sspr','sprb','cr7','cr30','cr90','pr7','pr30','pr90','tprv','tprv90','gap','gapP','gapE','gapEP','r1','r20']],
             ['밸류·수익성',['per','peg','pbr','psr','divy','payout','roe','opm']],
             ['성장',['grw','revg','opg','tob']],
             ['수급',['fnb20','onb20','fst','ost','sr','lbr','frgn','frgn4w','drvj']],
             ['건전성',['de','cr','oploss']],
             ['기타',['age']]];
    $('sd_sum').innerHTML=G.map(([t,ks])=>{
      const items=ks.filter(k=>CDEF[k]&&cAvail(k)).map(k=>`<div class="si"><span>${E(cl(k))}</span><b>${cell(r,k)}</b></div>`).join('');
      return items?`<div class="sg"><div class="sgt">${t}</div>${items}</div>`:'';
    }).join('');
  }

  /* ── (2026-07-24) 종목 파생 포지셔닝 — 파생 상장 종목만(파일럿 삼성전자·SK하이닉스)
     FSC T+1 확정치 5지표(값+60일 z) + 규칙 기반 자동 판독. 위치: 요약표(sd_sum) 위. ── */
  function _zBadge(z){
    if(z==null) return '<span class="note">z —</span>';
    const a=Math.abs(z), c=a>=2?'#c0392b':a>=1?'#e67e22':'#889';
    return `<span style="color:${c};font-weight:${a>=1?'700':'400'}">z ${z>0?'+':''}${z.toFixed(1)}</span>`;
  }
  /* (2026-07-24) KR 주식선물·옵션 만기 = 매월 두 번째 목요일. 기준일이 만기일 ±2영업일이면
     OI·베이시스는 롤오버 기계적 물량이라 방향 신호로 보지 않는다 — 카드가 자동 경고 */
  function _krExpiryGap(dstr){
    if(!dstr||dstr.length!==8) return null;
    const y=+dstr.slice(0,4), m=+dstr.slice(4,6), day=+dstr.slice(6,8);
    const secondThu=(yy,mm)=>{ let n=0; for(let i=1;i<=31;i++){ const dt=new Date(yy,mm-1,i); if(dt.getMonth()!==mm-1) break; if(dt.getDay()===4&&++n===2) return dt; } return null; };
    const cur=new Date(y,m-1,day);
    let ex=secondThu(y,m);
    if(ex&&cur>ex){ ex=secondThu(m===12?y+1:y, m===12?1:m+1); }   // 이달 만기 지났으면 다음달
    if(!ex) return null;
    return Math.round((ex-cur)/86400000);       // 만기까지 일수(음수 없음)
  }
  function _drvInterp(L,Z){
    /* 규칙 기반 자동 해석 — 각 행의 한줄 판독 + 종합 1줄. bull/bear 플래그 집계 */
    let bull=0, bear=0; const R={};
    const up = L.fut_chg_pct!=null ? L.fut_chg_pct>0 : null;
    const oiUp = L.fut_oi_chg!=null ? L.fut_oi_chg>0 : null;
    const gap=_krExpiryGap(L.d), roll=(gap!=null&&gap<=3);   // 만기 3일 이내 = 롤오버 구간
    // ① 베이시스
    const zb=Z.basis_pct;
    R.basis = zb==null?'누적 중':
      zb>=1.5?(bull++,'선물 주도 매수 — 강세 선행 신호'):
      zb<=-1.5?(bear++,'선물 매도 헤지 — 약세 전조'):'평소 범위';
    // ② 선물 OI × 선물가격 (정석: 선물가 기준) — 만기 3일 이내면 롤오버 물량이라 신호 무효
    if(roll){ R.oi=`⚠ 만기 주간(D-${gap}) — 롤오버 물량이라 방향 신호로 보지 말 것`; }
    else if(up==null||oiUp==null) R.oi='누적 중';
    else if(up&&oiUp){bull++;R.oi='선물↑+OI↑ 신규 매수 유입 — 상승 신뢰↑';}
    else if(up&&!oiUp) R.oi='선물↑+OI↓ 숏커버 반등 — 지속성 의심';
    else if(!up&&oiUp){bear++;R.oi='선물↓+OI↑ 신규 매도 — 하락 신뢰↑';}
    else R.oi='선물↓+OI↓ 롱 청산 — 하락 막바지 가능';
    if(roll&&R.basis&&!/누적/.test(R.basis)) R.basis+=' · ⚠ 만기 주간 — 월물 교체 왜곡 주의';
    // ③ PCR(OI) — Z는 부호 통일된 z(+=강세). 원지표 기준으로는 반대 방향
    const zp=Z.pcr_oi;
    R.pcr = zp==null?'표본 부족/누적 중':
      zp<=-2?(bear++,'헤지 급증 — 경계(극단이면 역발상 바닥 후보)'):
      zp<=-1?(bear++,'하방 경계 증가'):
      zp>=1?(bull++,'콜 우위 — 상방 베팅(쏠림 과열은 주의)'):'평소 범위';
    // ④ IV 스큐 — Z는 부호 통일된 z(+=강세)
    const zs=Z.iv_skew;
    R.skew = zs==null?'표본 부족/누적 중':
      zs<=-1.5?(bear++,'큰손이 폭락 보험 매집 — 겉이 강해도 경고'):
      zs>=1.5?(bull++,'하방 공포 완화 — 위험선호 회복'):'평소 범위';
    // ⑤ GEX (방향 아님 — 변동성 체제)
    R.gex = L.gex==null?'표본 부족/누적 중': L.gex<0?'변동성 증폭 구간 — 급등락 주의':'변동성 억제 구간 — 등락 완만';
    // 종합
    let head = bull>bear?`<b style="color:#c0392b">강세 우위</b> (${bull}:${bear}) — 파생이 상승을 지지`:
               bear>bull?`<b style="color:#2471c9">약세 우위</b> (${bear}:${bull}) — 파생이 하락을 경고`:
               `<b>중립·혼조</b> (${bull}:${bear})`;
    if(L.gex!=null&&L.gex<0) head+=' · <span style="color:#e67e22">변동성 증폭 주의</span>';
    return {rows:R, head};
  }
  /* (2026-07-24) 도움말 구조화 — 문단 나열 대신 무엇/왜 선행/읽는 법/주의 항목으로 분리 */
  const _DRV_HELP=[
   ['선물 베이시스',{
     '무엇':'최근월 선물가격 − 현물가격',
     '왜 선행':'선물은 증거금만 걸고 큰돈을 움직이는 시장 — 기관·외국인은 방향을 정하면 현물보다 선물부터 삽니다',
     '읽는 법':'<b class="up">z +1.5↑</b> 레버리지 자금이 상승 베팅(강세 선행) · <b class="dn">z −1.5↓</b> 선물로 미리 파는 중(헤지·약세 전조)',
     '주의':'배당락 전후엔 이론적으로 낮아짐 → 값이 아니라 z(평소 대비)로만 판단'}],
   ['선물 OI(미결제약정)',{
     '무엇':'아직 청산 안 된 선물 계약 수 = "판에 걸려 있는 돈"',
     '왜 선행':'OI 자체보다 가격과의 조합이 새 돈의 방향을 알려줍니다',
     '읽는 법':'<b class="up">선물↑+OI↑</b> 신규 매수(추세 진짜) · 선물↑+OI↓ 숏커버(반짝 가능성)<br><b class="dn">선물↓+OI↑</b> 신규 매도(하락 진짜) · 선물↓+OI↓ 롱 청산(하락 막바지 후보)',
     '주의':'만기(매월 두 번째 목요일) 주간엔 롤오버로 OI가 출렁임'}],
   ['풋콜비율 PCR(OI)',{
     '무엇':'풋(하락 보험) 미결제 ÷ 콜(상승 베팅) 미결제. 값이 높을수록 하락 대비가 많다는 뜻',
     '왜 선행':'하락 대비 수요의 증감이 현물보다 먼저 움직입니다',
     '읽는 법':'표시 z는 부호 통일(+=강세) — <b class="up">z +1↑</b> 콜 쏠림(상방 베팅 우위 — 과열은 주의) · <b class="dn">z −1↓</b> 하방 경계 증가 · <b class="dn">z −2↓</b> 헤지 급증(극단적 공포는 오히려 바닥 신호가 되기도)',
     '주의':'값(풋÷콜)은 원지표 그대로라 값↑=풋 증가. z만 방향 통일 · 개별주식옵션은 거래가 얇아 z(60일 대비)로 판단'}],
   ['IV 스큐 (콜−풋)',{
     '무엇':'"상승 복권(OTM 콜)" IV − "하락 보험(OTM 풋)" IV. 인덱스 3.1.13과 같은 콜−풋 표기 — 클수록 위험선호',
     '왜 선행':'큰손은 주가가 멀쩡할 때 조용히 보험부터 삽니다 → 주가보다 스큐가 먼저 움직이는 경우가 많음',
     '읽는 법':'<b class="up">z +1.5↑</b> 하방 공포 완화 — 위험선호 회복 · <b class="dn">z −1.5↓</b> 폭락 보험료 급등(하방 대비 수요 급증 — 겉이 강해도 경고)',
     '주의':'표본(호가) 부족한 날은 계산하지 않고 — 로 표시'}],
   ['딜러 감마 GEX',{
     '무엇':'옵션 팔아준 증권사(딜러)들이 헤지로 사고파는 방향의 총합 — 방향이 아니라 <b>변동성 체제</b> 지표',
     '읽는 법':'<b class="up">GEX +</b> 딜러가 "오르면 팔고 내리면 사는" 완충 → 등락 완만<br><b class="dn">GEX −</b> "오르면 더 사고 내리면 더 파는" 증폭 → 급등락 잘 나옴',
     '활용':'급락 후 GEX가 −에서 +로 돌아오면 바닥 다지기 신호로 참고'}],
   ['z-score',{
     '무엇':'오늘 값이 최근 60거래일 평균에서 몇 표준편차 떨어져 있나',
     '왜 쓰나':'종목마다 체급이 달라 절대값 비교 불가 → "자기 평소 대비 얼마나 이례적인가"로 표준화',
     '읽는 법':'<b>|z|≥2</b> 매우 이례적(강한 신호) · <b>|z|≥1</b> 평소보다 뚜렷함 · 그 외 평소 범위'}],
   ['데이터·갱신 (항목별 주기)',{
     '파생 5종':'한국거래소 확정치(금융위 FSC API) — <b>T+1 공표</b>(기준일 다음 영업일 13시) → 매일 <b>13:40</b> 적재. 헤더의 "MM/DD 확정"이 데이터 기준일, "획득"이 마지막 수집 시각',
     '장중(T+0)':'<b>베이시스·선물OI만</b> 카드 열 때 KIS 실시간 조회(⚡줄, 5분 캐시). 옵션 3종(풋콜·스큐·GEX)은 장중 호가 공백으로 왜곡이라 확정치만 사용',
     '수급 4종':'풀 빌드 <b>2회/일(06:52·15:52)</b>에 갱신 — 외인·기관 순매수는 당일 마감 후 확정(아침 빌드=전일치), 공매도 <b>T+1</b>·대차잔고 <b>T+1~2</b> 공표',
     'US':'Yahoo 옵션체인 마감 스냅샷 — 매일 06:50 KST(미 마감 후) 적재, 백필 불가라 z는 누적 중'}]];
  /* (2026-07-24) 판정점수 계산법 — 케이스별 상세 설명(ⓘ 맨 위에 표시) */
  function _scoreHelpHTML(kase){
    const th=_CASE_TH[kase]||1;
    const tbl=(rows)=>`<table style="width:100%;border-collapse:collapse;font-size:11.5px;margin:4px 0">${rows.map(r=>
      `<tr>${r.map((c,i)=>`<td style="border:1px solid var(--line,#e5e5e5);padding:3px 6px;${i===0?'white-space:nowrap;font-weight:600;background:var(--bg2,#f7f8f9)':''}">${c}</td>`).join('')}</tr>`).join('')}</table>`;
    /* (2026-07-24) 부호 통일 후 — 세 지표 모두 같은 규칙: z(+)=강세·z(−)=약세 */
    const _zrule='z <b>+1~+2</b> → <b class="up">+0.5</b> · z <b>+2↑</b> → <b class="up">+1</b> / z <b>−1~−2</b> → <b class="dn">−0.5</b> · z <b>−2↓</b> → <b class="dn">−1</b>';
    const drvRows=[
      ['선물 베이시스',`${_zrule} <span class="note">(z+ = 선물 매수 우위)</span>`],
      ['풋콜비율(OI)',`${_zrule} <span class="note">(z+ = 콜 쏠림 · 표시 z는 부호 통일 — 원지표 풋/콜과 반대)</span>`],
      ['IV 스큐 (콜−풋)',`${_zrule} <span class="note">(z+ = 하방 공포 완화 · 콜−풋으로 반전 표기)</span>`]];
    const prxRows=[
      ['외인 순매수(20일)','매수 +/매도 − · 크기 반영: 20일 순매수가 <b>시총의 0.3%↑면 ±0.5</b> · 미만이면 ±0.25'],
      ['기관 순매수(20일)','외인과 동일 (±0.25 ~ ±0.5)'],
      ['공매도비중','<b>5%↑ → −0.5</b> (하락 베팅 큼) · <b>2%↓ → +0.25</b> (베팅 적음) · 2~5%는 0'],
      ['대차잔고비율','<b>10%↑ → −0.5</b> (잠재 매도 실탄) · 그 외 0']];
    const exclRows=[['선물 OI','점수 제외 — 가격 방향과 같이 봐야만 의미(조건부)라 해석문만'],
      ['딜러 감마 GEX','점수 제외 — 상승/하락이 아니라 변동성 지표라 "변동성 증폭 주의" 경고만']];
    const CASES={
      1:['<b>CASE1 (선물+옵션 상장)</b> = 파생 3종 + 수급 4종 · 점수 범위 약 −5 ~ +4.25', drvRows.concat(prxRows)],
      2:['<b>CASE2 (선물만 상장)</b> = 베이시스 1종 + 수급 4종 (풋콜·스큐는 옵션 미상장이라 없음) · 범위 약 −3 ~ +2.25', [drvRows[0]].concat(prxRows)],
      3:['<b>CASE3 (파생 미상장)</b> = 수급 4종만 · 범위 약 −2 ~ +1.25', prxRows],
      us:['<b>US (옵션만 — 미국은 개별주식 선물 없음)</b> = 풋콜 + IV스큐 · 범위 ±2', [drvRows[1],drvRows[2]]]};
    const [title,rows]=CASES[kase]||CASES[1];
    const ex = kase===1?'예) 풋콜 z+1.3→−0.5 · 외인 −11조(시총 0.7%↑)→−0.5 · 기관 +1.4조(0.09%)→+0.25 · 공매도 7.7%→−0.5 ⇒ 합계 −1.25 → |−1.25| < 문턱 1.5 → <b>중립</b>':
      kase===2?'예) 베이시스 z+1.7→+0.5 · 외인 +0.4%→+0.5 · 기관 소액 매도→−0.25 · 공매도 3%→0 ⇒ 합계 +0.75 → 문턱 1 미달 → <b>중립</b>':
      kase===3?'예) 외인 +0.5%→+0.5 · 기관 +0.1%→+0.25 · 공매도 1.5%→+0.25 · 대차 3%→0 ⇒ 합계 +1.0 ≥ 문턱 0.75 → <b class="up">강세</b>':
      kase==='us'?'예) 풋콜 z(통일)+1.2→+0.5 · 스큐 z(통일)−2.1→−1 · 공매도잔량 1.5%→+0.25 ⇒ 합계 −0.25점 → 문턱 1 미달 → <b>중립</b>':
      '예) 공매도잔량 12%→−0.5 · 커버일수 6일→−0.25 ⇒ 합계 −0.75점 ≤ 문턱 −0.5 → <b class="dn">약세</b>';
    return `<div style="margin-bottom:12px;padding:8px 10px;border:1px solid #cde3cd;background:#f6faf6;border-radius:8px">`+
      `<b style="font-size:12px">📐 판정점수 계산법 — ${title}</b>`+
      tbl(rows)+
      (kase===1?`<div class="note" style="font-size:11px;margin:2px 0">점수에서 빠지는 항목:</div>`+tbl(exclRows):'')+
      `<div style="font-size:11.5px;line-height:1.6;margin-top:4px">각 항목 점수를 <b>단순 합산</b>합니다. 파생은 ±1점 만점(선행 베팅이라 크게), 수급은 ±0.25~0.5점(이미 실행된 매매라 절반 이하 가중).`+
      ` 케이스마다 항목 수가 달라 만점이 다르므로 <b>강세/약세 문턱도 케이스별</b>로: 이 종목은 <b>±${th}</b> (만점의 약 35% 지점).</div>`+
      `<div class="note" style="font-size:11px;margin-top:4px">${ex}</div></div>`;
  }
  /* 구조화 도움말 렌더러 — 지표 카드 + 항목 라벨 배지 */
  const _helpHTML=H=>H.map(h=>{
    const body=Object.entries(h[1]).map(([k,v])=>
      `<div style="display:flex;gap:7px;margin-top:3px;line-height:1.5"><span style="flex:0 0 52px;font-size:10.5px;font-weight:700;color:var(--tx2);background:var(--bg2,#f2f3f5);border-radius:4px;padding:1px 0;text-align:center;height:fit-content">${k}</span><span style="font-size:11.5px">${v}</span></div>`).join('');
    return `<div style="margin-bottom:10px;padding-bottom:8px;border-bottom:1px dashed var(--line,#e5e5e5)"><b style="font-size:12px">${h[0]}</b>${body}</div>`;
  }).join('');
  /* 파생 미상장 종목 폴백 — 이미 풀에 있는 공매도·대차·수급을 '포지셔닝 프록시'로 재구성 + 자동 해석 */
  const _PRX_HELP=[
   ['왜 프록시인가',{
     '무엇':'이 종목은 개별 주식선물·옵션이 미상장이라 파생 포지셔닝을 직접 잴 수 없음',
     '대신':'"누가 하락에 베팅 중인가"(공매도·대차잔고) + "큰손이 사는 중인가"(외국인·기관 순매수)로 근사'}],
   ['외인·기관 순매수(20일)',{
     '무엇':'최근 20거래일 누적 순매수 금액',
     '읽는 법':'<b class="up">둘 다 (+)</b> 큰손 양매수(수급 우호) · <b class="dn">둘 다 (−)</b> 양매도(비우호) · 엇갈리면 혼조',
     '참고':'연속매수 3일 이상이면 흐름이 이어지는 중'}],
   ['공매도비중',{
     '무엇':'최근 거래에서 공매도가 차지한 비율',
     '읽는 법':'<b class="dn">5%↑</b> 하락 베팅 압력 높음 · 2~5% 보통 · 2%↓ 낮음',
     '주의':'급등 종목의 공매도 급증은 과열 견제일 수도 → 수급과 같이 판단'}],
   ['대차잔고비율',{
     '무엇':'빌려간 주식(향후 공매도 실탄)의 시총 대비 비율',
     '읽는 법':'<b class="dn">10%↑</b> 잠재 매도 압력 큼 · 반대로 주가 상승 시 숏커버(되사기) 연료가 되기도'}],
   ['한계',{
     '주의':'파생 지표와 달리 "선행 베팅"이 아니라 "이미 실행된 매매"의 집계 → 선행성 한 단계 약함 · 확정치 T+1~T+2'}]];
  /* (2026-07-24) 3케이스 공용 — 수급 4행의 해석·행HTML을 CASE1·2 파생 카드에서도 재사용 */
  function _prxParts(r){
    let bull=0,bear=0; const R={};
    const f=r.fnb20, o=r.onb20;
    if(f!=null&&o!=null){
      if(f>0&&o>0){bull++;R.flow='외인·기관 양매수 — 수급 우호';}
      else if(f<0&&o<0){bear++;R.flow='외인·기관 양매도 — 수급 비우호';}
      else R.flow=f>0?'외인 매수·기관 매도 — 혼조':'기관 매수·외인 매도 — 혼조';
      if((r.fst||0)>=3||(r.ost||0)>=3) R.flow+=` (연속매수 ${Math.max(r.fst||0,r.ost||0)}일)`;
    } else R.flow='집계 대기';
    R.sr = r.sr==null?'—':
      r.sr>=5?(bear++,'공매도 압력 높음 — 하락 베팅 큰 편'):
      r.sr>=2?'공매도 보통':'공매도 낮음 — 하락 베팅 적음';
    R.lbr = r.lbr==null?'—':
      r.lbr>=10?(bear++,'대차잔고 과다 — 잠재 매도 압력(상승 시 숏커버 연료)'):
      r.lbr>=5?'대차잔고 다소 높음':'대차잔고 낮음';
    return {R,bull,bear};
  }
  function _prxRows(r,R){
    const row=(label,val,interp)=>`<div class="si" style="align-items:baseline"><span>${label}</span>`+
      `<b style="text-align:right">${val}<div class="note" style="font-weight:400;text-align:right">${interp}</div></b></div>`;
    return row('외인 순매수(20일)', cell(r,'fnb20')+(r.fst?` <span class="note">연속${r.fst}일</span>`:''), '')+
      row('기관 순매수(20일)', cell(r,'onb20')+(r.ost?` <span class="note">연속${r.ost}일</span>`:''), R.flow)+
      row('공매도비중', cell(r,'sr'), R.sr)+
      row('대차잔고비율', cell(r,'lbr')+(r.lb!=null?` <span class="note">(${cell(r,'lb')})</span>`:''), R.lbr);
  }
  /* 케이스별 강세/약세 문턱 — 항목 수가 달라 만점이 다르므로(만점의 ~35% 지점) */
  const _CASE_TH={1:1.5, 2:1, 3:0.75, us:1, us3:0.5};   // us3 = US 옵션 미수집(프록시만)
  const _caseBadge=k=>`<span style="font-size:10px;font-weight:700;background:${k===1?'#e8f2ff':k===2?'#eef7ee':k==='us'?'#f3ecff':'#f4f0e8'};border:1px solid var(--line,#ddd);border-radius:4px;padding:1px 5px;margin-right:5px" title="CASE1 선물+옵션(±1.5) · CASE2 선물만(±1) · CASE3 파생 미상장 프록시(±0.75) · US 옵션(±1) · US 프록시만(±0.5)">${k===1?'CASE1 선물+옵션':k===2?'CASE2 선물만':k===3?'CASE3 프록시':k==='us'?'US 옵션+프록시':'US 프록시'}</span>`;
  function _prxCard(r){
    const P=_prxParts(r), R=P.R;
    /* (2026-07-24) 판정 통일 — 우호/비우호 개수 대신 점수 기반 한 줄 */
    const pp=_prxPts(r), th=_CASE_TH[3];
    const vcol=pp!=null&&pp>=th?'#c0392b':pp!=null&&pp<=-th?'#2471c9':'inherit';
    const vlb=pp==null?'집계 대기':(pp>=th?'강세':pp<=-th?'약세':'중립');
    const scoreLine=`<div style="font-size:12.5px;margin:2px 0 6px"><b style="color:${vcol}">${vlb}</b>`+
      (pp!=null?` <b style="color:${vcol}">${pp>0?'+':''}${_fmtPt(pp)}점</b> <span class="note">(문턱 ±${th} — 프록시 4종뿐이라 낮게 · 스크리너 컬럼과 동일)</span>`:'')+`</div>`;
    return `<div class="sg"><div class="sgt" style="display:flex;justify-content:space-between;align-items:center">`+
      `<span>${_caseBadge(3)}포지셔닝 프록시 <span class="note">(파생 미상장 — 공매도·대차·수급으로 근사)</span></span>`+
      `<button class="cp-x" id="sd_drvhelp" title="설명">ⓘ 설명</button></div>`+
      scoreLine+
      _prxRows(r,R)+
      `<div id="sd_drvhelpbox" style="display:none;margin-top:8px;border-top:1px solid var(--line,#e5e5e5);padding-top:6px">`+
      _scoreHelpHTML(3)+_helpHTML(_PRX_HELP)+`</div></div>`;
  }
  async function loadDeriv(c){
    const box=$('sd_deriv'); if(!box) return;
    box.style.display='none';
    let D=null;
    try{ const r=await fetch(`/api/stock_deriv/${encodeURIComponent(c)}`); if(!r.ok) D=null; else D=await r.json(); }
    catch(e){ D=null; }
    if(dcode!==c) return;
    if(!D||!D.latest){
      /* 파생 미수록 → KR은 프록시 카드, US(옵션 미수집)는 공매도·기관 프록시 카드 */
      if(mkt==='us'){
        const r=POOL.us.find(x=>x.c===c); if(!r||(r.sr_f==null&&r.scov==null&&r.inst==null)) return;
        const R=_prxPartsUS(r), pp=_prxPtsUS(r), th=_CASE_TH.us3;
        const vcol=pp!=null&&pp>=th?'#c0392b':pp!=null&&pp<=-th?'#2471c9':'inherit';
        const vlb=pp==null?'집계 대기':(pp>=th?'강세':pp<=-th?'약세':'중립');
        box.innerHTML=`<div class="sg"><div class="sgt" style="display:flex;justify-content:space-between;align-items:center">`+
          `<span>${_caseBadge('us3')}포지셔닝 프록시 <span class="note">(옵션 미수집 종목 — 공매도·기관보유로 근사 · FINRA 2주 주기)</span></span>`+
          `<button class="cp-x" id="sd_drvhelp" title="설명">ⓘ 설명</button></div>`+
          `<div style="font-size:12.5px;margin:2px 0 6px"><b style="color:${vcol}">${vlb}</b>`+
          (pp!=null?` <b style="color:${vcol}">${pp>0?'+':''}${_fmtPt(pp)}점</b> <span class="note">(문턱 ±${th} · 스크리너 컬럼과 동일)</span>`:'')+`</div>`+
          _prxRowsUS(r,R)+
          `<div id="sd_drvhelpbox" style="display:none;margin-top:8px;border-top:1px solid var(--line,#e5e5e5);padding-top:6px">`+
          _scoreHelpHTML('us3')+`</div></div>`;
        box.style.display='';
        {const b=$('sd_drvhelp'); if(b) b.onclick=()=>{const e=$('sd_drvhelpbox'); if(e) e.style.display=e.style.display==='none'?'':'none';};}
        return;
      }
      const r=POOL.kr.find(x=>x.c===c); if(!r) return;
      box.innerHTML=_prxCard(r); box.style.display='';
      {const b=$('sd_drvhelp'); if(b) b.onclick=()=>{const e=$('sd_drvhelpbox'); if(e) e.style.display=e.style.display==='none'?'':'none';};}
      return;
    }
    const Zr=D.z||{};
    /* (2026-07-24) 인덱스식 부호 통일 — 풋콜·스큐 z를 뒤집어 전 지표 z(+)=강세.
       IV스큐는 값도 콜−풋으로 반전 표기(인덱스와 동일). 풋콜은 값(풋/콜)은 그대로 두고 z만 통일 */
    const Z={basis_pct:Zr.basis_pct, fut_oi_chg:Zr.fut_oi_chg,
             pcr_oi:_uz(Zr.pcr_oi), iv_skew:_uz(Zr.iv_skew), gex:Zr.gex};
    const L=D.latest, I=_drvInterp(L,Z), US=(mkt==='us');
    /* (2026-07-24) 3케이스 — CASE1 선물+옵션 / CASE2 선물만 / (CASE3=프록시 카드는 위 폴백) / US=옵션만 */
    const kase = US?'us':(D.has_opt===false?2:1);
    const pr = US?POOL.us.find(x=>x.c===c):POOL.kr.find(x=>x.c===c);
    const PX = pr?(US?_prxPartsUS(pr):_prxParts(pr)):null;
    /* 종합 판정점수(등급형) — 스크리너 '파생·수급판정' 컬럼과 동일 산식 */
    const dp=_drvPts(Z.basis_pct,Z.pcr_oi,Z.iv_skew);
    const pp=pr?(US?_prxPtsUS(pr):_prxPts(pr)):null;
    const tot=Math.round((dp+(pp||0))*100)/100;
    const th=_CASE_TH[kase];
    /* (2026-07-24) 판정 통일 — 예전 우호/비우호 개수 판정줄 삭제, 점수 기반 한 줄로.
       변동성 체제(GEX<0)는 점수와 별개의 경고라 뒤에 이어붙인다. */
    const _sgn=v=>`${v>0?'+':''}${_fmtPt(v)}`;
    const vcol=tot>=th?'#c0392b':tot<=-th?'#2471c9':'inherit';
    const vlb=tot>=th?'강세':tot<=-th?'약세':'중립';
    const scoreLine=`<div style="font-size:12.5px;margin:2px 0 6px"><b style="color:${vcol}">${vlb}</b> `+
      `<b style="color:${vcol}">${_sgn(tot)}점</b> <span class="note">(문턱 ±${th})</span>`+
      ` = 파생 ${_sgn(dp)}${pp!=null?` + 수급 ${_sgn(pp)} <span class="note" title="프록시는 선행성이 약해 축소 가중 — 수급은 시총 0.3%↑ ±0.5·미만 ±0.25, 공매도 5%↑ −0.5/2%↓ +0.25, 대차 10%↑ −0.5">(축소가중)</span>`:''}`+
      `${L.gex!=null&&L.gex<0?' · <span style="color:#e67e22">변동성 증폭 주의</span>':''}`+
      ` <span class="note">· 스크리너 컬럼과 동일</span></div>`;
    const fmt=(v,d,suf)=>v==null?'<span class="note">—</span>':`${(+v).toLocaleString(undefined,{maximumFractionDigits:d})}${suf||''}`;
    const row=(label,val,z,interp)=>`<div class="si" style="align-items:baseline"><span>${label}</span>`+
      `<b style="text-align:right">${val} <span style="margin-left:6px">${_zBadge(z)}</span>`+
      `<div class="note" style="font-weight:400;text-align:right">${interp}</div></b></div>`;
    const asofD = L.d?`${L.d.slice(4,6)}/${L.d.slice(6,8)}`:'';
    /* US: 개별주식 선물이 없어 베이시스·선물OI 행은 데이터 있을 때만. GEX 단위도 시장별(억원/M$) */
    box.innerHTML=
      `<div class="sg"><div class="sgt" style="display:flex;justify-content:space-between;align-items:center">`+
      `<span>${_caseBadge(kase)}파생 포지셔닝 <span class="note">(${asofD} ${US?'마감 스냅샷 · 매일 06:50 적재':'확정 · T+1 · 매일 13:40 적재'}${D.asof?` · 획득 ${E(String(D.asof).slice(5,16))}`:''})</span></span>`+
      `<button class="cp-x" id="sd_drvhelp" title="지표 설명">ⓘ 설명</button></div>`+
      scoreLine+
      `<div id="sd_drvlive" style="display:none;font-size:11.5px;background:#f1f7ff;border:1px solid #cfe3ff;border-radius:6px;padding:5px 8px;margin:2px 0 6px"></div>`+
      (L.basis!=null? row('선물 베이시스', `${fmt(L.basis,0,'원')} (${fmt(L.basis_pct,2,'%')})`, Z.basis_pct, I.rows.basis):'')+
      (L.fut_oi!=null? row('선물 OI', `${fmt(L.fut_oi,0,'계약')}${L.fut_oi_chg!=null?` (${L.fut_oi_chg>0?'+':''}${(+L.fut_oi_chg).toLocaleString()})`:''}`, Z.fut_oi_chg, I.rows.oi):'')+
      /* (2026-07-24) 옵션 미상장(주식선물만 상장) 종목 — '누적 중' 오안내 대신 행을 접고 사유 명시 */
      (D.has_opt===false
        ? `<div class="note" style="margin-top:4px;font-size:11px">이 종목은 <b>주식선물만 상장·주식옵션 미상장</b>이라 풋콜비율·IV스큐·GEX는 산출 대상이 아닙니다 (KRX 주식옵션은 약 40종목만 상장)</div>`
        : row('풋콜비율(OI)', fmt(L.pcr_oi,2), Z.pcr_oi, I.rows.pcr)+
          row('IV 스큐 (콜−풋)', fmt(L.iv_skew==null?null:(L.iv_skew===0?0:-L.iv_skew),1,'%p'), Z.iv_skew, I.rows.skew)+
          row('딜러 감마 GEX', fmt(L.gex,1,US?'M$':'억원'), Z.gex, I.rows.gex))+
      `<div class="note" style="margin-top:3px;font-size:10.5px">✅ 모든 z는 <b class="up">z(+)=강세</b>·<b class="dn">z(−)=약세</b>로 부호 통일(인덱스 3.1.13과 동일) — IV스큐는 콜−풋으로 반전 표기, 풋콜비율은 값(풋÷콜)은 원지표 그대로·z만 통일</div>`+
      (US?`<div class="note" style="margin-top:4px;font-size:11px">미국 개별주식은 선물이 없어 옵션 3종만 · 옵션체인은 과거 조회가 불가해 z는 수집 개시일부터 누적(20거래일 후 산출)</div>`:'')+
      /* (2026-07-24) CASE1·2도 수급 4행을 같은 카드에 — 파생 미상장 카드(CASE3)와 표시 항목 통일 */
      (PX?(US
        ?`<div class="note" style="margin:7px 0 2px;font-size:11px;font-weight:700">현물 수급 <span style="font-weight:400">(프록시 — 판정점수에 축소가중 반영 · 공매도잔량은 FINRA 2주 주기 공표 · 풀 빌드 시 갱신)</span></div>`+_prxRowsUS(pr,PX)
        :`<div class="note" style="margin:7px 0 2px;font-size:11px;font-weight:700">현물 수급 <span style="font-weight:400">(프록시 — 판정점수에 축소가중 반영 · 풀 빌드 2회/일 06:52·15:52 — 외인·기관 당일 마감 후 확정, 공매도 T+1·대차 T+1~2 공표)</span></div>`+_prxRows(pr,PX.R)):'')+
      `<div id="sd_drvhelpbox" style="display:none;margin-top:8px;border-top:1px solid var(--line,#e5e5e5);padding-top:6px">`+
      _scoreHelpHTML(kase)+_helpHTML(_DRV_HELP)+_helpHTML(_PRX_HELP.slice(1))+`</div></div>`;
    box.style.display='';
    {const b=$('sd_drvhelp'); if(b) b.onclick=()=>{const e=$('sd_drvhelpbox'); if(e) e.style.display=e.style.display==='none'?'':'none';};}
    /* (2026-07-24) 장중 온디맨드 — 베이시스·선물OI만 KIS T+0 (서버 5분 캐시).
       옵션 3종은 장중 호가 공백으로 왜곡이라 확정치 유지. z는 마감 확정 기준 그대로. */
    if(!US&&(kase===1||kase===2)){
      fetch(`/api/stock_deriv_live/${encodeURIComponent(c)}`).then(r2=>r2.ok?r2.json():null).then(q=>{
        if(!q||dcode!==c) return;
        const el=$('sd_drvlive'); if(!el) return;
        const s=(v,d)=>v==null?'—':(+v).toLocaleString(undefined,{maximumFractionDigits:d??0});
        /* (2026-07-24) OI 장중 판독 — 전일마감(기준점) → 장중(현재) → 증감 → 가격×OI 4분면 해석(잠정) */
        const prevOI=(q.oi!=null&&q.oi_chg!=null)?q.oi-q.oi_chg:null;
        const up=q.chg_pct>0, oiUp=(q.oi_chg||0)>0;
        const oisent= q.oi_chg==null?'' :
          up&&oiUp   ? '<b class="up">선물↑+OI↑</b> 장중 신규 매수 유입 중 — 상승 신뢰↑' :
          up&&!oiUp  ? '선물↑+OI↓ 장중 숏커버 성격 — 지속성 의심' :
          !up&&oiUp  ? '<b class="dn">선물↓+OI↑</b> 장중 신규 매도 진입 중 — 하락 신뢰↑' :
                       '선물↓+OI↓ 장중 롱 청산 성격 — 투매·포지션 정리(막바지 가능성)';
        /* 베이시스 — 직전 확정(FSC) → 장중, 변화 방향 해석. ±0.05%p 이내는 '비슷' */
        let bsent='';
        if(q.basis_pct!=null&&L.basis_pct!=null){
          const dfb=q.basis_pct-L.basis_pct;
          bsent = (q.basis_pct<0&&L.basis_pct>=0) ? '<b class="dn">백워데이션 전환</b> — 선물 매도 헤지 경계' :
                  dfb>0.05  ? '<b class="up">확정치보다 확대</b> — 장중 선물 매수세 강해지는 중' :
                  dfb<-0.05 ? '<b class="dn">확정치보다 축소</b> — 선물 쪽 힘 빠짐(헤지 매도 성격)' :
                              '직전 확정치와 비슷 — 특이 신호 없음';
        }
        /* (2026-07-24) 표 형태 — 항목/직전확정/장중/변화/z/해석 6열로 체계화 */
        const prevFut=(q.fut!=null&&q.chg_pct!=null)?Math.round(q.fut/(1+q.chg_pct/100)):null;
        const td=(c,extra)=>`<td style="border:1px solid #cfe3ff;padding:3px 7px;${extra||''}">${c}</td>`;
        const num='text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap';
        /* 현물가 — 풀(1분 갱신)의 현재가·등락으로 전일종가 역산 */
        const spotNow=pr&&pr.px!=null?pr.px:q.spot;
        const spotChg=pr&&pr.chg!=null?pr.chg:null;
        const prevSpot=(spotNow!=null&&spotChg!=null)?Math.round(spotNow/(1+spotChg/100)):null;
        const rows=[
          ['현물가(주가)', prevSpot!=null?s(prevSpot)+'원':'—', spotNow!=null?`<b>${s(spotNow)}원</b>`:'—',
           spotChg!=null?`<span class="${spotChg>=0?'up':'dn'}">${spotChg>0?'+':''}${s(spotChg,2)}%</span>`:'—', '', ''],
          ['선물가', prevFut!=null?s(prevFut)+'원':'—', `<b>${s(q.fut)}원</b>`,
           `<span class="${q.chg_pct>=0?'up':'dn'}">${q.chg_pct>0?'+':''}${s(q.chg_pct,2)}%</span>`, '',
           (spotChg!=null&&q.chg_pct!=null)?(q.chg_pct<spotChg-0.15?'현물보다 약함 — 선물 주도 하락':(q.chg_pct>spotChg+0.15?'현물보다 강함 — 선물 주도 상승':'현물과 동행')):''],
          ['베이시스', L.basis!=null?`${L.basis>0?'+':''}${s(L.basis)}원 (${L.basis_pct>0?'+':''}${s(L.basis_pct,2)}%) <span class="note">(${E(asofD)})</span>`:'—',
           `<b>${q.basis>0?'+':''}${s(q.basis)}원${q.basis_pct!=null?` (${q.basis_pct>0?'+':''}${s(q.basis_pct,2)}%)`:''}</b>`,
           (q.basis!=null&&L.basis!=null)?`${q.basis-L.basis>0?'+':''}${s(q.basis-L.basis)}원`:'—',
           _zBadge(q.z_basis_live), bsent||'—'],
          ['미결제약정(OI)', s(prevOI), `<b>${s(q.oi)}</b>`,
           q.oi_chg!=null?`<b class="${oiUp?'up':'dn'}">${q.oi_chg>0?'+':''}${s(q.oi_chg)}</b>`:'—',
           _zBadge(q.z_oi_live), oisent||'—']];
        /* (2026-07-24) 장중 잠정 판정 — 베이시스만 장중 z로 대체해 재계산(참고용).
           정본은 확정치 점수(스크리너 컬럼과 동일) — 장중은 노이즈·컬럼 불일치 때문에 참고 병기만 */
        let liveJdg='';
        if(q.z_basis_live!=null){
          const dpL=_drvPts(q.z_basis_live, Z.pcr_oi, Z.iv_skew);
          const totL=Math.round((dpL+(pp||0))*100)/100;
          if(totL!==tot){
            const lb=totL>=th?'<b class="up">강세</b>':totL<=-th?'<b class="dn">약세</b>':'중립';
            liveJdg=` · <b>장중 잠정 판정 ${totL>0?'+':''}${_fmtPt(totL)}점</b> ${lb} <span class="note">(베이시스만 장중 z 대체 — 정본은 위 확정 점수)</span>`;
          } else liveJdg=` · 장중 잠정 판정도 동일(${tot>0?'+':''}${_fmtPt(tot)}점)`;
        }
        el.innerHTML=`<div style="margin-bottom:4px">⚡ <b>장중 ${E(q.t||'')} 기준</b> <span class="note">(KIS T+0 · 5분 캐시 · z는 확정 60일 분포에 장중값 대입 · 잠정치 — 마감 때 달라질 수 있음, 확정 판독은 위 행들)</span>${liveJdg}</div>`+
          `<table style="width:100%;border-collapse:collapse;font-size:11.5px;background:#fff">`+
          `<tr>${['항목','직전 기준(전일마감·베이시스는 최근확정)','장중','변화','z(장중)','해석'].map(h=>`<th style="border:1px solid #cfe3ff;background:#e9f2ff;padding:3px 7px;font-weight:700;white-space:nowrap">${h}</th>`).join('')}</tr>`+
          rows.map(r=>`<tr>${td(`<b>${r[0]}</b>`,'white-space:nowrap')}${td(r[1],num)}${td(r[2],num)}${td(r[3],num)}${td(r[4],'white-space:nowrap')}${td(r[5])}</tr>`).join('')+
          `</table>`;
        el.style.display='';
      }).catch(()=>{});
    }
  }
  // 지표 계산
  const _sma=(a,n)=>a.map((_,i)=>{ if(i<n-1) return null; let s=0; for(let j=i-n+1;j<=i;j++){ const v=a[j]; if(v==null) return null; s+=v; } return s/n; });
  function _ema(a,n){ const k=2/(n+1); let e=null; return a.map(x=>{ if(x==null) return e; e = e==null? x : x*k + e*(1-k); return e; }); }
  function _rsiArr(c,n){ n=n||14; const out=Array(c.length).fill(null); let g=0,l=0,ag=0,al=0;
    for(let i=1;i<c.length;i++){ const d=(c[i]??c[i-1])-(c[i-1]??c[i]);
      if(i<=n){ g+=Math.max(d,0); l+=Math.max(-d,0);
        if(i===n){ ag=g/n; al=l/n; out[i]=100-100/(1+ag/(al||1e-9)); } }
      else { ag=(ag*(n-1)+Math.max(d,0))/n; al=(al*(n-1)+Math.max(-d,0))/n; out[i]=100-100/(1+ag/(al||1e-9)); } }
    return out; }
  function _cvs(id){ const cv=$(id); const w=cv.clientWidth||760, h=cv.clientHeight||80; cv.width=w; cv.height=h; const x=cv.getContext('2d'); x.clearRect(0,0,w,h); return [x,w,h]; }
  /* ── 자체차트 (2026-07-21 네이버식 정보 표시로 확장) ─────────────────────
     상단 범례(시·고·저·종/등락/거래량 + MA·볼린저 파라미터), 최고·최저 지점 라벨,
     우측 현재가 배지, 가격 y축 7눈금, 거래량·MACD y축, RSI 시그널(9),
     월 경계 x축, 그리고 마우스를 올리면 십자선이 따라오며 모든 범례가 그 봉 기준으로 바뀐다. */
  let _CD=null, _CHI=null, _CN=0, _CBOUND=false;
  let _INV=null, _CT=null, _CHD=null;   // 수급 패널 원본 · 메인 차트 날짜배열 · 호버 날짜
  /* (2026-07-21) 공시 마커 — 네이버처럼 A·B·C… 원형 배지를 캔들 위에 찍고 '클릭'하면 내용을 띄운다.
     호버가 아니라 클릭인 이유: 이미 십자선 호버가 걸려 있어 마우스만 올려도 뜨면 서로 방해된다.
     한국 전용(네이버 공시 API). 미국은 SEC EDGAR 가 코드→CIK 매핑을 따로 요구하고
     공시 성격도 달라 같은 UX 로 묶기 어렵다. */
  let _DISC=null, _DSEL=null, _DHIT=[];   // 공시목록 · 선택된 마커 · 마커 히트박스
  /* (2026-08-09) 실적발표 마커 — 공시 마커와 같은 UX(클릭하면 요약 상자).
     같은 급등락이라도 실적 발표 직후냐 아니냐에 따라 해석이 완전히 달라지므로
     캔들 위에 '실' 배지를 찍고, 누르면 캘린더 팝업과 같은 한 줄 요약을 띄운다. */
  let _ESEL=null, _EHIT=[];
  let _PLK=[], _ECIK=null;   // 팝업 안 '원본 열기' 링크 히트박스 · US 종목 CIK(SEC 링크용)
  /* (2026-08-09) 미국은 과거 1년치 발표일을 SEC 8-K(Item 2.02) 접수일로 받는다.
     Yahoo 는 '다음 예정일' 하나와 분기 말일만 줘서 과거 발표일을 알 수 없다. */
  let _EDATES=null;
  /* (2026-07-21) 줌·팬 — 휠로 기간 확대/축소, 드래그로 좌우 이동.
     구조상 어렵지 않다: 지표는 이미 전체 시계열(full)로 계산한 뒤 표시 구간만 잘라 쓰므로,
     보이는 봉수(_CZ)와 뒤로 밀린 봉수(_COFF)만 바꾸면 MA·RSI·MACD·ADX 가 전부 그대로 맞는다.
     이력도 이미 2년치(KR 505·US 501 거래일)를 받아두고 있다.
     휠은 sd_main 에서만 가로챈다 — 보조 패널까지 가로채면 차트 스택(880px)을 지나
     페이지를 스크롤할 방법이 없어진다. */
  /* (2026-07-21) 주기(timeframe) — 네이버와 동일 구성. 서버가 tf 파라미터로 만들어 준다.
     저장은 하지 않는다: 볼 때만 받아오는 온디맨드다. 분봉을 전 종목 저장하면 용량만 커지고
     쓰이지도 않는다(원본은 네이버·야후가 이미 보관). 서버는 30~60초 메모리 캐시만 둔다. */
  const TFL={'1m':'1분','3m':'3분','5m':'5분','10m':'10분','30m':'30분','60m':'1시간',
             'd':'일','w':'주','M':'월'};
  let _TF='d';
  const _isMin=()=>_TF.endsWith('m');
  /* (2026-08-04) 분봉 시간외(프리·애프터) 포함 토글 — 기본 정규장(false).
     US=Yahoo prepost(04:00~20:00 ET) · KR=KIS UN 통합(NXT 프리 08:00~·애프터 ~20:00, 최근 3거래일) */
  let _PP=false;
  const _ppq=()=>(_isMin()&&_PP)?'&pp=1':'';
  const CZ0=250;                          // 기본 표시 봉수
  let _CZ=CZ0, _COFF=0, _DRAG=null, _DMOVE=0;
  const _mk=n=>{ const a=Math.abs(n);
    return a>=1e6?(n/1e6).toFixed(2)+'m':a>=1e3?Math.round(n/1e3)+'k':String(Math.round(n)); };
  const _pf=p=>mkt==='kr'?Math.round(p).toLocaleString():(+p).toFixed(2);
  /* (2026-07-21) 이동평균은 시장별 관례가 다르다 — 일봉 기준.
       한국 5/20/60/120/240 : 20의 배수 체계로 1주·1개월·분기·반기·1년을 거래일 환산
                              (60=수급선, 120=경기선, 240=1년선. 네이버·국내 HTS 기본은 5/20/60/120)
       미국 20/50/100/200   : 50의 배수 관습. 골든/데드 크로스 정의가 50·200 교차.
                              ※ 미국 연 거래일은 252일이라 200일선은 실제로 1년이 아니다(9~10개월).
     장기선이 화면 전 구간에 그려지도록 /api/chart 이력을 KR 760일·US 2y 로 늘렸다. */
  /* (2026-07-21) 차트 범례의 '상태 배지' — 숫자만 보고 해석하지 않아도 되게 판정을 같이 띄운다.
     색은 화면 전체 규칙과 동일: 빨강=주식 우호 · 파랑=비우호 · 회색=중립.
     RSI 과매도를 빨강으로 두는 건 컨트라리안(반등 후보) 관점이며, 그 취지가 드러나도록
     배지 문구에 '반등 후보'를 함께 적는다. */
  function _badge(x,cx,y,txt,col,bg){ x.font='bold 10px sans-serif';
    const w=x.measureText(txt).width+10;
    x.fillStyle=bg;
    if(x.roundRect){ x.beginPath(); x.roundRect(cx,y-9.5,w,13,6); x.fill(); }
    else x.fillRect(cx,y-9.5,w,13);
    x.fillStyle=col; x.fillText(txt,cx+5,y); return w+6; }
  const R_UP=['#c0392b','#fdeaea'], R_DN=['#1e6fd6','#e8f1fd'], R_NE=['#6b7684','#eef0f3'];
  const _rsiState=v=> v==null?null
    : v>=70?['과매수 · 조정 경계',...R_DN]
    : v>=50?['상승 모멘텀',...R_UP]
    : v>30 ?['약세',...R_NE]
    :       ['과매도 · 반등 후보',...R_UP];
  /* ADX 는 '방향이 없는' 지표다(강한 하락에서도 값이 커진다).
     그래서 빨강(주식 우호)/파랑(비우호)을 쓰면 안 되고, ADX 선과 같은 보라 계열로 둔다.
     방향은 바로 옆 MACD 배지가 알려주므로 둘을 같이 읽으면 된다. */
  const R_AX=['#7d3c98','#f2e8f7'];
  const _adxState=v=> v==null?null
    : v>=40?['강한 추세(방향무관)',...R_AX]
    : v>=25?['추세(방향무관)',...R_AX]
    : v>=20?['추세 형성',...R_NE]
    :       ['횡보',...R_NE];
  const _macdState=(mv,sg)=> (mv==null||sg==null)?null
    : (mv>sg&&mv>0)?['골든(0선↑) 강한 상승',...R_UP]
    : (mv>sg)      ?['골든(0선↓) 상승 전환',...R_UP]
    : (mv<0)       ?['데드(0선↓) 강한 하락',...R_DN]
    :               ['데드(0선↑) 하락 전환',...R_DN];

  /* ADX(14) — Wilder 방식. RSI(과열도)·MACD(방향)와 달리 '추세의 강도'를 본다.
     보통 25 이상이면 추세장, 20 이하면 횡보장으로 보고, 이동평균 크로스 전략은
     횡보장에서 깨지므로 그 구간을 걸러내는 용도로 쓴다. 방향은 알려주지 않는다. */
  function _adx(h,l,c,p){ p=p||14; const n=h.length;
    if(n<p*2+2) return new Array(n).fill(null);
    const tr=[null],pdm=[null],ndm=[null];
    for(let i=1;i<n;i++){
      tr.push(Math.max(h[i]-l[i], Math.abs(h[i]-c[i-1]), Math.abs(l[i]-c[i-1])));
      const up=h[i]-h[i-1], dn=l[i-1]-l[i];
      pdm.push(up>dn&&up>0?up:0); ndm.push(dn>up&&dn>0?dn:0); }
    const sm=a=>{ const o=new Array(n).fill(null); let acc=0;
      for(let i=1;i<=p;i++) acc+=a[i]||0;
      o[p]=acc;
      for(let i=p+1;i<n;i++){ acc=acc-acc/p+(a[i]||0); o[i]=acc; }
      return o; };
    const TR=sm(tr),PD=sm(pdm),ND=sm(ndm);
    const dx=new Array(n).fill(null);
    for(let i=p;i<n;i++){ if(!TR[i]) continue;
      const pdi=100*PD[i]/TR[i], ndi=100*ND[i]/TR[i], t=pdi+ndi;
      if(t>0) dx[i]=100*Math.abs(pdi-ndi)/t; }
    const out=new Array(n).fill(null); let acc=0,cnt=0,prev=null;
    for(let i=p;i<n;i++){ if(dx[i]==null) continue;
      cnt++;
      if(cnt<=p){ acc+=dx[i]; if(cnt===p){ prev=acc/p; out[i]=prev; } }
      else { prev=(prev*(p-1)+dx[i])/p; out[i]=prev; } }
    return out; }

  const MASET={ kr:[[5,'#16a085'],[20,'#f39c12'],[60,'#27ae60'],[120,'#8e44ad'],[240,'#2c3e50']],
                us:[[20,'#f39c12'],[50,'#27ae60'],[100,'#16a085'],[200,'#8e44ad']] };
  /* (2026-07-21) 상세 차트 장중 자동 갱신.
     종전엔 종목을 열 때 한 번만 받아서, 5분봉을 띄워놓고 봐도 봉이 자라지 않았다(단타 용도에 치명적).
     주기는 서버 캐시와 맞춘다 — 분봉 30초 / 일·주·월 60초.
     지켜야 할 3가지:
       ① 줌·팬 상태 유지. 갱신마다 기본 250봉으로 돌아가면 못 쓴다.
          과거 구간을 보고 있으면(_COFF>0) 새로 생긴 봉 수만큼 오프셋을 밀어 같은 구간을 유지한다.
       ② 드래그 중에는 건너뛴다. 조작 중 다시 그리면 끊긴다.
       ③ 장중 + 브라우저 탭이 보일 때만. 장 끝나고도 계속 부르면 낭비다.
     공시 목록은 여기서 다시 받지 않는다(하루 몇 건이라 30초마다 부를 이유가 없다). */
  /* ── 차트 하단 패널 ────────────────────────────────────────────────────────
     분봉  : 호가 10단계 + 체결강도(KIS 실시간) + 시간별체결(네이버 분단위 + 공격성 판정)
     일·주·월: 외국인·기관 순매매 일별 표
     소스별 지연이 다르므로 각 상자에 그대로 적는다 —
       KIS(실전) = 실시간 / 네이버 호가·거래원 = 20분 지연 / 투자자별 순매매 = 마감 후 확정 */
  const _nf=v=>v==null?'—':Number(v).toLocaleString();
  const _sg=v=>v==null?'':(v>0?'+':'')+Number(v).toLocaleString();
  async function loadBottom(c){
    const bk=$('sd_book'), it=$('sd_invt');
    if(!bk||!it) return;
    bk.style.display='none'; it.style.display='none';
    if(mkt!=='kr') return;                       // 두 패널 모두 한국 전용
    if(_isMin()) await _drawBook(c, bk);         // 분봉 → KIS 실시간
    else         await _drawInvT(c, it);         // 일·주·월 → 네이버(마감 후 확정)
  }

  /* 분봉 하단 — 전부 KIS 실전계정 실시간. 네이버(20분 지연)는 여기 쓰지 않는다. */
  async function _drawBook(c, bk){
    try{
      const O=await (await fetch('/api/orderbook/kr/'+encodeURIComponent(c))).json();
      if(dcode!==c || !_isMin() || !O || O.err || !O.ask) return;
      const sc=O.score>=1?'buy':(O.score<=-1?'sell':'mid');
      const hh=String(O.at||'').replace(/(\d{2})(\d{2})(\d{2})/,'$1:$2:$3');
      let h='<div class="bkwrap">';

      // ① 호가창
      h+=`<div class="bkbox" style="flex:0 0 auto"><div class="bktit">① 호가 10단계 <small>${E(O.src||'')} · ${hh}</small></div><table class="bk">`;
      for(let i=9;i>=0;i--){ const a=O.ask[i]||{};
        h+=`<tr><td class="aq">${_nf(a.q)}</td><td class="ap">${_nf(a.p)}</td><td></td><td></td></tr>`; }
      for(let i=0;i<10;i++){ const b=O.bid[i]||{};
        h+=`<tr><td></td><td></td><td class="bp">${_nf(b.p)}</td><td class="bq">${_nf(b.q)}</td></tr>`; }
      h+=`<tr class="tot"><td class="aq">${_nf(O.ask_tot)}</td><td colspan="2" style="text-align:center;color:#98a2ad">잔량합계</td><td class="bq">${_nf(O.bid_tot)}</td></tr></table>
          <div class="note" style="font-size:11px;margin-top:5px;max-width:230px">
            잔량은 <b>벽</b>이다. 위(매도)가 두꺼우면 저항이지만 거래량 실어 뚫으면 오히려 돌파 신호.
            아래(매수)가 두꺼우면 지지. 정적인 숫자보다 <b>벽이 쌓이는지 걷히는지</b>가 중요하다.</div></div>`;

      // ② 체결강도 + 최근 체결
      const _st=parseFloat(O.strength);
      h+=`<div class="bkbox" style="width:300px;flex:0 0 auto"><div class="bktit">② 체결강도 · 장중 추이 <small>실시간</small></div>
          <div style="font-size:12.5px;margin-bottom:3px">체결강도
            <b style="font-size:15px">${O.strength??'—'}</b>
            <span class="sbadge ${_st>=100?'buy':'sell'}">당일 ${_st>=100?'매수 우위':'매도 우위'}</span></div>
          <div class="note" style="font-size:10px;margin-bottom:3px">당일 누적 · 100 초과=매수</div>
          <canvas id="sd_strcv" style="width:100%;height:72px;display:block"></canvas>
          <div class="note" id="sd_strnote" style="font-size:11px;margin-top:4px;max-width:290px">체결강도 추이 불러오는 중…</div>
          <details style="margin-top:6px"><summary style="font-size:11px;color:#98a2ad;cursor:pointer">직전 체결 30건 (수 초 · 참고용) ▾</summary>
          <div style="max-height:170px;overflow:auto;margin-top:4px"><table class="tk">
          <tr><th>시각</th><th>체결가</th><th>수량</th><th>구분</th></tr>`;
      for(const t of (O.ticks||[])){
        const up=(t.sg==='1'||t.sg==='2'); const sd=t.side||'mid';
        const lab= sd==='buy'?'매수':(sd==='sell'?'매도':'중립');
        h+=`<tr><td class="l">${E(String(t.t||'').replace(/(\d{2})(\d{2})(\d{2})/,'$1:$2:$3'))}</td>
             <td class="${up?'up':'dn'}">${_nf(t.p)}</td><td>${_nf(t.v)}</td>
             <td><span class="sbadge ${sd}">${lab}</span></td></tr>`; }
      h+=`</table></div><div class="note" style="font-size:10.5px;margin-top:4px">
          유동성 큰 종목은 30체결이 1~2초라 노이즈다. 방향은 위 <b>장중 추이</b>로 보는 게 맞다.
          구분은 직전 체결가 대비 오르며/내리며 체결로 판정(틱 규칙 추정).</div></details></div>`;

      // ③ 투자자 가집계 + 종합
      h+=`<div class="bkbox" style="flex:1;min-width:280px">
          <div class="bktit">③ 투자자 가집계 · 종합 <small><b style="color:#c0392b">오늘 장중</b> 잠정치 · 당일 누적(회차별)</small></div>
          <div style="font-size:12.5px;margin-bottom:6px">
            외국인 <b class="${(O.frg_est||0)>=0?'up':'dn'}">${_sg(O.frg_est)}</b> ·
            기관 <b class="${(O.org_est||0)>=0?'up':'dn'}">${_sg(O.org_est)}</b>
            <span class="note" style="font-size:10.5px">(당일 누적 · 최신 회차)</span></div>`;
      if(O.est_series && O.est_series.length>1){
        h+=`<table class="tk" style="margin-bottom:8px"><tr><th>회차</th><th>외국인(누적)</th><th>기관(누적)</th></tr>`;
        for(const e of O.est_series){
          h+=`<tr><td class="l">${e.gb}차</td>
               <td class="${(e.frg||0)>=0?'up':'dn'}">${_sg(e.frg)}</td>
               <td class="${(e.org||0)>=0?'up':'dn'}">${_sg(e.org)}</td></tr>`; }
        h+=`</table><div class="note" style="font-size:10.5px;margin-bottom:8px">
            KRX 가 장중 5회 발표하는 잠정 집계의 <b>당일 누적</b> 추이 — 회차가 갈수록 외인·기관이
            더 사들이면(값이 커지면) 매수세가 붙는 중, 줄면 빠지는 중.</div>`;
      }
      /* OBV 는 판정에 넣지 않는다 — '체결강도 추세(1시간)'와 같은 '최근 방향'이라 중복이다.
         OBV 의 고유 가치는 다이버전스(주가↑·OBV 정체=분산 의심)이고, 그건 점수화보다
         차트(⑤ OBV 패널)로 눈으로 보는 게 맞다(패널에 그 설명이 이미 있다). */
      h+=`
          <div style="font-size:14px;margin:8px 0">현재 압력
            <span class="sbadge ${sc}" style="font-size:13px;padding:3px 10px">${E(O.label)}</span>
            <span class="note" style="font-size:11px">(${O.score>=0?'+':''}${O.score}점)</span></div>
          <table class="tk"><tr><th>항목</th><th>값</th><th>점수</th></tr>`;
      for(const p of (O.parts||[])){
        h+=`<tr><td class="l">${E(p.k)}</td><td>${E(String(p.v))}</td>
             <td class="${p.s>0?'up':(p.s<0?'dn':'')}">${p.s>0?'+':''}${p.s}</td></tr>
            <tr><td class="l" colspan="3" style="color:#98a2ad;font-size:10.5px;padding-top:0">${E(p.d)}</td></tr>`; }
      h+=`</table>
          <div class="note" style="font-size:11px;margin-top:6px">
            ⚠ 이건 <b>지금 주문흐름에 나타난 매수·매도 압력의 요약</b>이지 매매 권유가 아닙니다.
            네 항목은 서로 어긋날 수 있고(예: 체결은 강한데 매도벽이 두꺼움), 그 경우 점수보다
            <b>왜 어긋나는지</b>를 보는 게 맞습니다. 진입·청산 기준과 손절선은 미리 정해 두세요.</div></div>`;
      h+='</div>';
      bk.innerHTML=h; bk.style.display='block';
      _loadStrengthCurve(c);                       // 체결강도 장중 추이(별도 요청·5분 캐시)
    }catch(e){}
  }

  /* 체결강도 장중 추이 — 09:30~현재 30분 간격. 30체결 노이즈 대신 '매수세가 붙는 중/빠지는 중'을 본다. */
  async function _loadStrengthCurve(c){
    const cv=$('sd_strcv'), nt=$('sd_strnote'); if(!cv) return;
    try{
      const D=await (await fetch('/api/strength/kr/'+encodeURIComponent(c))).json();
      if(dcode!==c || !_isMin()) return;
      const pts=(D&&D.pts)||[]; if(pts.length<2){ if(nt) nt.textContent=''; return; }
      /* (2026-07-21) 고해상도(레티나) 대응 — CSS px 로만 그리면 흐릿·깨져 보인다.
         내부 버퍼를 devicePixelRatio 배로 잡고 컨텍스트를 스케일한다. */
      const dpr=window.devicePixelRatio||1;
      const w=cv.clientWidth||280, hh=72;
      cv.width=Math.round(w*dpr); cv.height=Math.round(hh*dpr);
      const x=cv.getContext('2d'); x.setTransform(dpr,0,0,dpr,0,0); x.clearRect(0,0,w,hh);
      const P={l:6,r:34,t:10,b:14};
      /* (2026-07-21) y축 자동 스케일 + 여백. 100 이 범위 밖이면(전부 <100 등) 살짝 넓혀 항상 보이게. */
      const vs=pts.map(p=>p.cttr), dmn=Math.min(...vs), dmx=Math.max(...vs);
      let lo=Math.min(dmn,100)-2, hi=Math.max(dmx,100)+2;
      const li=pts.length-1, mid=Math.floor(li/2);
      const X=i=>P.l+(w-P.l-P.r)*i/(pts.length-1), Y=v=>P.t+(hh-P.t-P.b)*(1-(v-lo)/((hi-lo)||1));
      // 100 기준선(매수/매도 경계) — 점선, 라벨은 이것 하나만(겹침 방지)
      x.strokeStyle='#e6e9ee'; x.lineWidth=1; x.setLineDash([3,3]);
      x.beginPath(); x.moveTo(P.l,Y(100)); x.lineTo(w-P.r,Y(100)); x.stroke(); x.setLineDash([]);
      x.fillStyle='#c2c8d0'; x.font='9px sans-serif'; x.textAlign='left'; x.fillText('100', w-P.r+4, Y(100)+3);
      // 선 아래 옅은 면적 채움(마무리감)
      const last=vs[li];
      x.beginPath(); x.moveTo(X(0),Y(vs[0]));
      for(let i=1;i<pts.length;i++) x.lineTo(X(i),Y(vs[i]));
      x.lineTo(X(li),hh-P.b); x.lineTo(X(0),hh-P.b); x.closePath();
      x.fillStyle=last>=100?'rgba(221,51,51,.06)':'rgba(31,111,235,.06)'; x.fill();
      // 선 — 라운드 조인·캡, 100 위=빨강 / 아래=파랑 세그먼트
      x.lineWidth=1.8; x.lineJoin='round'; x.lineCap='round';
      for(let i=1;i<pts.length;i++){ const up=(vs[i-1]+vs[i])/2>=100;
        x.strokeStyle=up?'#d33':'#1f6feb'; x.beginPath();
        x.moveTo(X(i-1),Y(vs[i-1])); x.lineTo(X(i),Y(vs[i])); x.stroke(); }
      x.lineWidth=1;
      // 마지막 점 + 현재값 라벨
      x.fillStyle=last>=100?'#d33':'#1f6feb';
      x.beginPath(); x.arc(X(li),Y(last),3,0,Math.PI*2); x.fill();
      x.font='bold 9px sans-serif'; x.textAlign='left'; x.fillText(String(Math.round(last)), w-P.r+4, Y(last)+3);
      // x축 시각 — 첫점 왼쪽·끝점 오른쪽·가운데 중앙(잘림 방지)
      x.fillStyle='#98a2ad'; x.font='9px sans-serif';
      x.textAlign='left';   x.fillText(pts[0].t,   X(0),   hh-3);
      x.textAlign='center'; x.fillText(pts[mid].t, X(mid), hh-3);
      x.textAlign='right';  x.fillText(pts[li].t,  X(li),  hh-3);
      x.textAlign='left';
      // 해석 문구 — 최근 3점 기울기로 '붙는 중/빠지는 중'
      if(nt){
        const a=vs[Math.max(0,li-2)], b=vs[li], d=b-a;
        const cur=b>=100?'매수 우위':'매도 우위';
        const trend = Math.abs(d)<3 ? '횡보' : (d>0?'매수 쪽으로 강해지는 중':'매도 쪽으로 기우는 중');
        nt.innerHTML=`장중 저점 ${Math.round(Math.min(...vs))} · 고점 ${Math.round(Math.max(...vs))} · 현재 <b>${Math.round(b)}</b>(${cur}) · 최근 ${trend}. `
          +`<span style="color:#98a2ad">100 위=매수 체결 우위. 회차가 오르내리는 방향이 힘의 유입·이탈이다.</span>`;
      }
    }catch(e){ if(nt) nt.textContent=''; }
  }

  /* 일·주·월 하단 — 네이버 외국인·기관 순매매(장 마감 후 확정치) */
  async function _drawInvT(c, it){
    try{
      const J=await (await fetch('/api/invtable/kr/'+encodeURIComponent(c)+'?n=20')).json();
      if(dcode!==c || _isMin()) return;
      const rs=J.items||[]; if(!rs.length) return;
      let h=`<div class="bkbox"><div class="bktit">외국인 · 기관 순매매
               <small>네이버 · 장 마감 후 확정치(장중 잠정치는 분봉 화면에서 KIS 실시간으로 제공)</small></div>
             <div style="max-height:300px;overflow:auto"><table class="tk">
             <tr><th>날짜</th><th>종가</th><th>전일비</th><th>등락률</th><th>거래량</th>
                 <th>기관 순매매</th><th>외국인 순매매</th><th>개인 순매매</th><th>외인 보유율</th></tr>`;
      for(const r of rs){
        const pct=(r.px&&r.chg)?((r.chg/(r.px-r.chg))*100):null;
        const cc=r.chg>0?'up':(r.chg<0?'dn':'');
        const sc2=v=>v==null?'':(v>0?'up':(v<0?'dn':''));
        h+=`<tr><td class="l">${r.d.slice(0,4)}.${r.d.slice(4,6)}.${r.d.slice(6,8)}</td>
             <td>${_nf(r.px)}</td>
             <td class="${cc}">${r.chg>0?'▲':(r.chg<0?'▼':'')}${_nf(Math.abs(r.chg))}</td>
             <td class="${cc}">${pct==null?'—':(pct>0?'+':'')+pct.toFixed(2)+'%'}</td>
             <td>${_nf(r.vol)}</td>
             <td class="${sc2(r.org)}">${_sg(r.org)}</td>
             <td class="${sc2(r.frg)}">${_sg(r.frg)}</td>
             <td class="${sc2(r.ind)}">${_sg(r.ind)}</td>
             <td>${E(r.hold||'—')}</td></tr>`; }
      h+=`</table></div><div class="note" style="font-size:11px;margin-top:5px">
          기관·외국인이 <b>동시에 순매수</b>한 날이 상승의 수급 근거가 된다.
          외인 보유율이 며칠 연속 오르면 일회성 매수가 아니라는 뜻.</div></div>`;
      it.innerHTML=h; it.style.display='block';
    }catch(e){}
  }

  let _LASTFETCH=0, _AUTOBOUND=false;
  function _mktLive(){
    try{
      const tz = mkt==='kr' ? 'Asia/Seoul' : 'America/New_York';
      const pp={}; new Intl.DateTimeFormat('en-CA',{timeZone:tz,hour:'2-digit',minute:'2-digit',
        hour12:false, weekday:'short'}).formatToParts(new Date()).forEach(z=>pp[z.type]=z.value);
      if(pp.weekday==='Sat'||pp.weekday==='Sun') return false;
      const hm=+pp.hour*60 + +pp.minute;
      return mkt==='kr' ? (hm>=8*60+50 && hm<=15*60+45)    // 장전 동시호가~마감 직후
                        : (hm>=9*60+20 && hm<=16*60+5);
    }catch(e){ return false; }
  }
  async function _autoTick(){
    if(!dcode || chartSrc!=='canvas') return;
    if(document.visibilityState!=='visible') return;
    if(_EXT){ const ed=document.getElementById('etf_detail'); if(!ed||ed.style.display==='none') return; }
    else { const dv=$('scr_detail'); if(!dv || dv.style.display==='none') return; }
    if(_DRAG) return;                                   // 드래그 중이면 건너뛴다
    if(!_mktLive()) return;
    const need = _isMin() ? 30000 : 60000;
    if(Date.now()-_LASTFETCH < need) return;
    const c=dcode, tf=_TF;
    try{
      const D=await (await fetch(`/api/chart/${mkt}/${encodeURIComponent(c)}?tf=${tf}${_ppq()}`)).json();
      if(dcode!==c || _TF!==tf) return;                 // 그 사이 종목·주기가 바뀌었으면 버린다
      _LASTFETCH=Date.now();
      const prevTot=(_CD&&_CD.c)?_CD.c.length:0, tot=(D.c||[]).length;
      _CD=D;
      if(_COFF>0 && tot>prevTot) _COFF += (tot-prevTot);  // 과거를 보던 중이면 그 구간 고정
      _paint();
      const nt=$('sd_tfnote');
      if(nt) nt.textContent = (_isMin()
          ? `${tot}봉 · 최근 ${new Set((D.t||[]).map(z=>z.slice(0,8))).size}거래일`
          : `${tot}봉`) + (D.ppf?' · ⚠ 시간외 미제공(정규장 표시)':'') + (D.ppo?' · ⏰ 시간외단일가 포함':'')
          + ` · 🔴 LIVE ${new Date().toLocaleTimeString('ko-KR',{hour12:false})}`;
    }catch(e){}
  }
  function _bindAuto(){ if(_AUTOBOUND) return; _AUTOBOUND=true;
    setInterval(_autoTick, 15000);                      // 15초마다 확인, 실제 조회는 위 주기대로
  }

  let _TFBOUND=false;
  /* (2026-07-21) 분봉은 KIS 실계정을 쓰므로 로그인한 경우에만 허용한다.
     공개로 열어두면 유량제한에 걸려 파생·수급 수집 배치까지 같이 죽는다.
     화면에서 비활성화하는 건 안내용이고, 실제 차단은 서버(401)가 한다. */
  let _AUTH=null;
  function _applyAuthTF(){
    const sel=$('sd_tfmin'); if(!sel) return;
    const ok=!!_AUTH;
    sel.disabled=!ok;
    sel.style.opacity=ok?'':'0.45';
    sel.style.cursor=ok?'pointer':'not-allowed';
    sel.title=ok?'':'분봉은 로그인 후 이용 가능합니다 (KIS 부하 보호)';
    const nt=$('sd_tfnote');
    if(!ok && nt && !/로그인/.test(nt.textContent||''))
      nt.innerHTML=(nt.textContent||'')+' <span style="color:#c0392b">· 분봉은 로그인 필요</span>';
  }
  function _bindTF(){ if(_TFBOUND) return; _TFBOUND=true;
    fetch('/api/auth/me').then(r=>r.json())
      .then(d=>{ _AUTH=!!(d&&d.ok); _applyAuthTF();
        if(!_AUTH && _isMin()){ _TF='d'; if(dcode) showDetail(dcode); } })
      .catch(()=>{ _AUTH=false; _applyAuthTF(); });
    const sel=$('sd_tfmin');
    const sync=()=>{ document.querySelectorAll('#sd_tfbar .tfb')
        .forEach(b=>b.classList.toggle('on', b.dataset.tf===_TF));
      if(sel) sel.classList.toggle('on', _isMin());
      /* (2026-08-04) 정규장/시간외 토글 — 분봉일 때만 노출 (KR·US 공통, 기본 정규장) */
      const pw=$('sd_ppwrap');
      if(pw){ pw.style.display=_isMin()?'inline-flex':'none';
        pw.querySelectorAll('.ppb').forEach(b=>b.classList.toggle('on', (b.dataset.pp==='1')===_PP)); } };
    document.querySelectorAll('#sd_ppwrap .ppb').forEach(b=>{
      b.onclick=()=>{ const v=b.dataset.pp==='1'; if(v===_PP) return;
        _PP=v; sync(); if(dcode) showDetail(dcode); }; });
    /* (2026-07-21) 일/주/월 상태에서 드롭다운의 '현재 선택값'(예: 5분)을 다시 고르면
       select 의 value 가 안 바뀌어 change 이벤트가 안 난다 → 아무 반응이 없었다.
       (다른 값을 고르면 정상 동작해서 더 헷갈렸다)
       → 드롭다운을 '클릭'하는 순간 분봉이 아니면 현재 선택값으로 바로 전환한다.
         네이버도 분 드롭다운을 누르면 분봉으로 넘어간다. 이후 다른 값을 고르면 change 로 다시 전환. */
    if(sel){
      sel.onchange=()=>{ if(!_AUTH) return; _TF=sel.value; sync(); if(dcode) showDetail(dcode); };
      sel.addEventListener('mousedown',()=>{
        if(!_AUTH) return;
        if(!_isMin() && sel.value){ _TF=sel.value; sync(); if(dcode) showDetail(dcode); } });
    }
    document.querySelectorAll('#sd_tfbar .tfb').forEach(b=>{
      b.onclick=()=>{ _TF=b.dataset.tf; sync(); if(dcode) showDetail(dcode); }; });
    sync(); }

  /* (2026-08-09) 캔버스 히트테스트 클릭이 환경에 따라 안 먹어(팝업 차단·요소 겹침 추정)
     팝업의 링크 자리에 **실제 <a> 태그**를 절대배치로 겹친다. 네이티브 링크라 항상 열린다.
     캔버스는 CSS px = 그리기 px (1:1, _cvs) 이므로 좌표를 그대로 쓴다. */
  function _syncLinks(){
    const cv=$('sd_main'); if(!cv||!cv.parentElement) return;
    const host=cv.parentElement;
    let ov=host.querySelector(':scope > .plkov');
    if(!_PLK.length){ if(ov) ov.remove(); return; }
    if(getComputedStyle(host).position==='static') host.style.position='relative';
    if(!ov){ ov=document.createElement('div'); ov.className='plkov'; host.appendChild(ov); }
    const ox=cv.offsetLeft, oy=cv.offsetTop;
    ov.innerHTML=_PLK.map(L=>
      `<a href="${L.u}" target="_blank" rel="noopener" title="공시 원본 열기"
         onmouseover="this.style.background='rgba(31,111,235,.10)'" onmouseout="this.style.background='transparent'"
         style="position:absolute;left:${(ox+L.x).toFixed(0)}px;top:${(oy+L.y).toFixed(0)}px;width:${L.w.toFixed(0)}px;height:${L.h}px;z-index:30;border-radius:4px;cursor:pointer"></a>`).join('');
  }
  function _bindChart(){ if(_CBOUND) return; _CBOUND=true;
    /* (2026-08-09) 팝업 '원본 열기' 클릭 — 캔버스 위에 다른 요소가 겹쳐도 동작하도록
       문서 캡처 단계에서 sd_main 좌표로 환산해 판정하고, 팝업 차단을 피해
       window.open 대신 앵커 클릭으로 연다(사용자 제스처 내 링크 이동으로 취급). */
    document.addEventListener('click',ev=>{
      if(!_PLK.length) return;
      const e=$('sd_main'); if(!e) return;
      const r=e.getBoundingClientRect();
      if(ev.clientX<r.left||ev.clientX>r.right||ev.clientY<r.top||ev.clientY>r.bottom) return;
      const px=(ev.clientX-r.left)*(e.width/r.width), py=(ev.clientY-r.top)*(e.height/r.height);
      for(const L of _PLK){ if(px>=L.x&&px<=L.x+L.w&&py>=L.y&&py<=L.y+L.h){
        ev.preventDefault(); ev.stopPropagation();
        const a=document.createElement('a'); a.href=L.u; a.target='_blank'; a.rel='noopener';
        document.body.appendChild(a); a.click(); a.remove(); return; } }
    }, true);
    ['sd_main','sd_vol','sd_rsi','sd_macd'].forEach(id=>{ const e=$(id); if(!e) return;
      e.addEventListener('mousemove',ev=>{ if(!_CN) return;
        const r=e.getBoundingClientRect(), PL=6, PR=52;
        const step=(r.width-PL-PR)/_CN;
        if(_DRAG){                                   // 드래그 중엔 십자선 대신 구간 이동
          _DMOVE=Math.max(_DMOVE, Math.abs(ev.clientX-_DRAG.x));
          const TOT=(_CD&&_CD.c)?_CD.c.length:0; if(!TOT) return;
          const d=Math.round((ev.clientX-_DRAG.x)/step);   // 오른쪽으로 끌면 과거로
          const nv=Math.max(0, Math.min(TOT-_CZ, _DRAG.off+d));
          if(nv!==_COFF){ _COFF=nv; _paint(); }
          return; }
        let i=Math.round(((ev.clientX-r.left)-PL)/step-0.5);
        i=Math.max(0,Math.min(_CN-1,i));
        if(i!==_CHI){ _CHI=i; _paint(); } });
      e.addEventListener('mouseleave',()=>{ if(_CHI!=null){ _CHI=null; _paint(); } });

      /* 팬(좌우 이동) — 모든 패널에서 잡는다. 어느 패널을 끌든 전체가 같이 움직인다. */
      e.addEventListener('mousedown',ev=>{ if(ev.button!==0) return;
        _DRAG={x:ev.clientX, off:_COFF}; _DMOVE=0; e.style.cursor='grabbing'; });
      e.addEventListener('dblclick',()=>{ _CZ=CZ0; _COFF=0; _paint(); });   // 더블클릭 = 원래대로

      if(id==='sd_main'){
        /* 줌(휠) — sd_main 에서만. passive:false 라야 페이지 스크롤을 막을 수 있다.
           커서 위치의 봉을 기준으로 확대/축소해야 보고 있던 지점이 안 튄다. */
        e.addEventListener('wheel',ev=>{
          const TOT=(_CD&&_CD.c)?_CD.c.length:0; if(!TOT) return;
          ev.preventDefault();
          const r=e.getBoundingClientRect(), PL=6, PR=52;
          const frac=Math.max(0,Math.min(1,((ev.clientX-r.left)-PL)/(r.width-PL-PR)));
          const anchor=(TOT-_CZ-_COFF)+frac*_CZ;      // 커서가 가리키던 전체기준 인덱스
          const z0=_CZ;
          _CZ=Math.max(30, Math.min(TOT, Math.round(_CZ*(ev.deltaY>0?1.2:1/1.2))));
          if(_CZ===z0) return;
          const off=Math.round(anchor-frac*_CZ);       // 그 인덱스가 같은 위치에 오도록
          _COFF=Math.max(0, Math.min(TOT-_CZ, TOT-_CZ-off));
          _paint(); }, {passive:false});

        e.addEventListener('click',ev=>{
          if(_DMOVE>4) return;                        // 드래그였으면 클릭으로 치지 않는다
          if(!_DHIT.length && !_EHIT.length && !_PLK.length) return;
          const r=e.getBoundingClientRect();
          const px=(ev.clientX-r.left)*(e.width/r.width), py=(ev.clientY-r.top)*(e.height/r.height);
          // 팝업 안 '원본 열기' 링크가 최우선 — 팝업은 마커 위에 그려지므로
          for(const L of _PLK){ if(px>=L.x&&px<=L.x+L.w&&py>=L.y&&py<=L.y+L.h){
            window.open(L.u,'_blank'); return; } }
          // 실적 마커를 먼저 본다 — 공시 배지와 겹치는 날이면 실적 쪽이 정보량이 크다
          let eh=null;
          for(const m of _EHIT){ if((px-m.x)**2+(py-m.y)**2 <= (m.r+3)**2){ eh=m.d; break; } }
          if(eh){ _ESEL=(eh!==_ESEL)?eh:null; _DSEL=null; _paint(); return; }
          let hit=null;
          for(const m of _DHIT){ if((px-m.x)**2+(py-m.y)**2 <= (m.r+3)**2){ hit=m.d; break; } }
          _DSEL = (hit && hit!==_DSEL) ? hit : null;   // 같은 마커 재클릭·빈 곳 클릭 → 닫기
          _ESEL = null;
          _paint(); });
      }
      e.style.cursor='grab';
    });
    window.addEventListener('mouseup',()=>{ if(_DRAG){ _DRAG=null;
      ['sd_main','sd_vol','sd_rsi','sd_macd','sd_inv'].forEach(id=>{ const q=$(id); if(q) q.style.cursor='grab'; }); } });
    /* 수급 패널(sd_inv)은 네이버 1년+KIS 병합이라 메인 차트와 기간·봉수가 다르다.
       인덱스로 맞추면 다른 날짜를 가리키게 되므로 '날짜'를 공통키로 역매핑한다. */
    const ei=$('sd_inv');
    if(ei){
      ei.addEventListener('mousedown',ev=>{ if(ev.button!==0) return;
        _DRAG={x:ev.clientX, off:_COFF}; _DMOVE=0; ei.style.cursor='grabbing'; });
      ei.addEventListener('dblclick',()=>{ _CZ=CZ0; _COFF=0; _paint(); });
      ei.style.cursor='grab';
      ei.addEventListener('mousemove',ev=>{
        if(_DRAG){ _DMOVE=Math.max(_DMOVE, Math.abs(ev.clientX-_DRAG.x));
          const TOT=(_CD&&_CD.c)?_CD.c.length:0; if(!TOT) return;
          const r0=ei.getBoundingClientRect(), st0=(r0.width-58)/Math.max(_CN,1);
          const d=Math.round((ev.clientX-_DRAG.x)/st0);
          const nv=Math.max(0, Math.min(TOT-_CZ, _DRAG.off+d));
          if(nv!==_COFF){ _COFF=nv; _paint(); }
          return; }
        if(!_INV||!_CT) return; const jt=_INV.t||[]; if(!jt.length) return;
        const d0=String((_CT[0])||'').replace(/-/g,'');
        let j0=0; for(let k=0;k<jt.length;k++){ if(String(jt[k]||'').replace(/-/g,'')>=d0){ j0=k; break; } }
        const nv2=Math.max(jt.length-j0,1);
        const r=ei.getBoundingClientRect(), PL=6, PR=52, step=(r.width-PL-PR)/nv2;
        let j=j0+Math.round(((ev.clientX-r.left)-PL)/step-0.5);
        j=Math.max(j0,Math.min(jt.length-1,j));
        const d=String(jt[j]||'').replace(/-/g,'');
        let i=_CT.findIndex(z=>String(z||'').replace(/-/g,'')===d);
        if(i<0){ for(let k=_CT.length-1;k>=0;k--){ if(String(_CT[k]||'').replace(/-/g,'')<=d){ i=k; break; } } }
        if(i>=0&&i!==_CHI){ _CHI=i; _paint(); } });
      ei.addEventListener('mouseleave',()=>{ if(_CHI!=null){ _CHI=null; _paint(); } }); } }
  function drawAll(D){ _CD=D; _CHI=null; _DISC=null; _DSEL=null; _DHIT=[]; _ESEL=null; _EHIT=[];
    _CZ=CZ0; _COFF=0;                    // 종목이 바뀌면 기본 구간으로
    _bindChart(); _paint(); }
  /* ── (2026-08-09) KR 실적·전망 패널 — 차트 하단 ────────────────────────────
     ① 분기 재무표: 확정 5분기 + 컨센(E) 3분기 · 매출/영업익/순익 절대값과 YoY·QoQ 를
        한 표에. "지금이 개선 추세인가, 시장은 다음 분기를 어떻게 보나"가 한눈에 들어온다.
     ② 목표주가 90일 변동표 + 미니 추이: 증권사가 리포트마다 목표가를 어떻게 옮겼는지.
     ③ 컨센 영업이익 추정 추이: 일별 스냅샷 — 쌓일수록 리비전 곡선이 된다(2026-08-09 시작). */
  async function loadKrFin(c){
    const el=$('sd_fin'); if(!el) return;
    if(mkt!=='kr'){ return loadUsFin(c); }   // (2026-08-09) US 도 동일 컨셉 패널
    el.style.display=''; el.innerHTML='<span class="note">실적·전망 로드 중…</span>';
    let J=null;
    try{ J=await (await fetch('/api/kr_fin/'+encodeURIComponent(c))).json(); }catch(e){}
    if(dcode!==c) return;
    if(!J||!(J.q||[]).length){ el.innerHTML='<span class="note">분기 재무 데이터 없음 (컨센서스 미커버 종목)</span>'; return; }
    const q=J.q, F=v=>v==null?'—':Math.round(v).toLocaleString();
    /* (2026-08-09 수정) 변화율 = (현재−기저)÷|기저|. 예전 식은 적자 기저에서 부호가 뒤집혀
       적자(−0.55)→흑자(0.41) 가 −174.5% 로 나왔다(개선인데 마이너스). 지금은 +174.5%. */
    const pct=(a,b)=>(a!=null&&b!=null&&Math.abs(b)>1)?((a-b)/Math.abs(b)*100):null;
    const yoy=(i,k)=>i>=4?pct(q[i][k],q[i-4][k]):null;
    const qoq=(i,k)=>i>=1?pct(q[i][k],q[i-1][k]):null;
    const P=v=>v==null?'<span class="note">—</span>':`<span class="${v>0?'up':(v<0?'dn':'note')}">${v>0?'+':''}${v.toFixed(1)}%</span>`;
    const opm=i=>(q[i].s&&q[i].o!=null)?(q[i].o/q[i].s*100):null;
    /* ① 분기 재무표 */
    let t1=`<table style="width:100%;font-size:11.5px;border-collapse:collapse">
      <tr style="border-bottom:1px solid var(--line)"><th style="text-align:left;padding:3px 4px">분기</th>
      <th>매출<span class="note">(억)</span></th><th>YoY</th><th>QoQ</th>
      <th>영업익<span class="note">(억)</span></th><th>YoY</th><th>QoQ</th>
      <th>순익<span class="note">(억)</span></th><th>YoY</th><th>QoQ</th><th>영업이익률</th></tr>`;
    q.forEach((r,i)=>{ const m=opm(i);
      /* prov = DART 잠정공시로 덮은 분기 — WISEreport 가 (E) 로 두는 동안 실제(잠정)값 표시 */
      t1+=`<tr style="border-bottom:1px solid #f2f4f7;${r.prov?'background:#eefaf1':(r.e?'background:#fff7ea':'')}">
        <td style="padding:3px 4px"><b>${r.p}</b>${r.prov?' <span style="color:#1f9d55;font-size:10px">잠정</span>':(r.e?' <span style="color:#c47b1e;font-size:10px">E</span>':'')}</td>
        <td style="text-align:right">${F(r.s)}</td><td style="text-align:right">${P(yoy(i,'s'))}</td><td style="text-align:right">${P(qoq(i,'s'))}</td>
        <td style="text-align:right">${F(r.o)}</td><td style="text-align:right">${P(yoy(i,'o'))}</td><td style="text-align:right">${P(qoq(i,'o'))}</td>
        <td style="text-align:right">${F(r.n)}</td><td style="text-align:right">${P(yoy(i,'n'))}</td><td style="text-align:right">${P(qoq(i,'n'))}</td>
        <td style="text-align:right">${m==null?'—':m.toFixed(1)+'%'}</td></tr>`; });
    t1+='</table><div class="note" style="margin-top:3px">주황 배경 = 컨센서스 추정(E) · <span style="color:#1f9d55">초록 배경 = DART 잠정실적 반영(확정 전)</span> · YoY/QoQ 는 표 안 값으로 계산 · 음수 기저 구간의 비율은 부호 왜곡 가능</div>';
    /* ①-b 연간 재무 — 분기 컨센이 못 미치는 2027(E)·2028(E)까지 (2029는 WISEreport 미제공) */
    const Y=J.y||[];
    if(Y.length){
      const ypct=(i,k)=>i>=1?pct(Y[i][k],Y[i-1][k]):null;
      const yopm=i=>(Y[i].s&&Y[i].o!=null)?(Y[i].o/Y[i].s*100):null;
      /* 라벨은 고정 문구가 아니라 실제 제공분 기준 — FY2029 를 주는 종목이면 그대로 표시된다 */
      const lastE=[...Y].reverse().find(r=>r.e);
      let ty=`<div style="margin-top:8px"><b style="font-size:12px">연간</b> <span class="note">(확정 + 컨센 추정${lastE?` — ${lastE.p.slice(0,4)}년까지 제공분 전부`:''})</span>
        <table style="width:100%;font-size:11.5px;border-collapse:collapse;margin-top:2px">
        <tr style="border-bottom:1px solid var(--line)"><th style="text-align:left;padding:3px 4px">연도</th>
        <th>매출<span class="note">(억)</span></th><th>YoY</th><th>영업익<span class="note">(억)</span></th><th>YoY</th>
        <th>순익<span class="note">(억)</span></th><th>YoY</th><th>영업이익률</th></tr>`;
      Y.forEach((r,i)=>{ const m=yopm(i);
        ty+=`<tr style="border-bottom:1px solid #f2f4f7;${r.e?'background:#fff7ea':''}">
          <td style="padding:3px 4px"><b>${r.p}</b>${r.e?' <span style="color:#c47b1e;font-size:10px">E</span>':''}</td>
          <td style="text-align:right">${F(r.s)}</td><td style="text-align:right">${P(ypct(i,'s'))}</td>
          <td style="text-align:right">${F(r.o)}</td><td style="text-align:right">${P(ypct(i,'o'))}</td>
          <td style="text-align:right">${F(r.n)}</td><td style="text-align:right">${P(ypct(i,'n'))}</td>
          <td style="text-align:right">${m==null?'—':m.toFixed(1)+'%'}</td></tr>`; });
      ty+='</table></div>';
      t1+=ty;
    }
    /* ② 목표주가 90일 변동표 + 미니 그래프 */
    let t2='';
    const tp=(J.tp||[]).slice().sort((a,b)=>a.d<b.d?-1:1);
    if(tp.length){
      const pts=tp.filter(z=>z.tp!=null);
      const cur=(_CD&&_CD.c)?[..._CD.c].reverse().find(v=>v!=null):null;
      const pdate=s=>{const m=/^(\d\d)\/(\d\d)\/(\d\d)$/.exec(s||''); return m?new Date(2000+ +m[1], +m[2]-1, +m[3]):null;};
      /* (2026-08-09) 30·90일 평균 목표가 + 현재가 대비 상승여력 — 표 위 요약줄 */
      let avgLine='';
      {
        const now=new Date(), cut=n=>{const d=new Date(now); d.setDate(d.getDate()-n); return d;};
        const avg=n=>{const a=pts.filter(z=>{const d=pdate(z.d); return d&&d>=cut(n);});
          return a.length?{v:a.reduce((x,z)=>x+z.tp,0)/a.length,n:a.length,
            u:a.filter(z=>(z.chg||0)>0).length,d:a.filter(z=>(z.chg||0)<0).length}:null;};
        const fmt=o=>{ if(!o) return null;
          const gp=(cur&&cur>0)?((o.v/cur-1)*100):null;
          return `<b>${Math.round(o.v).toLocaleString()}</b><span class="note">(${o.n}건 · <span class="up">상향 ${o.u}</span>·<span class="dn">하향 ${o.d}</span>)</span>`+
            (gp==null?'':` <span class="${gp>0?'up':(gp<0?'dn':'note')}">${gp>0?'+':''}${gp.toFixed(1)}%</span>`); };
        const a30=fmt(avg(30)), a90=fmt(avg(90));
        if(a30||a90) avgLine=`<div style="font-size:11.5px;margin:4px 0 2px">`+
          (a30?`30일 평균 ${a30}`:'')+(a30&&a90?' · ':'')+(a90?`90일 평균 ${a90}`:'')+
          ` <span class="note">— % 는 현재가 대비 상승여력</span></div>`;
      }
      /* 차트(표 아래) — x=실제 발간일, 점=리포트 1건, 선=시간순 연결, 현재가는 점선 기준선.
         상승여력이 한눈에 보이도록 y 범위에 현재가를 포함한다. */
      let svg='';
      {
        const P2=pts.map(z=>({t:pdate(z.d),v:z.tp,d:z.d})).filter(z=>z.t).sort((a,b)=>a.t-b.t);
        if(P2.length){
          /* (2026-08-09) 차트 폭 = 표 폭(패널 실측), 높이 2배 */
          const w=Math.max(560,(el.clientWidth||620)-26),hh=240,L=64,R=10,T=8,B=18;
          let lo=Math.min(...P2.map(z=>z.v)), hi=Math.max(...P2.map(z=>z.v));
          if(cur&&cur>0){ lo=Math.min(lo,cur); hi=Math.max(hi,cur); }
          const pad=(hi-lo)*0.06||hi*0.02||1; lo-=pad; hi+=pad;
          const t0=P2[0].t.getTime(), t1=Math.max(P2[P2.length-1].t.getTime(), t0+864e5);
          const X=t=>L+(t-t0)/(t1-t0)*(w-L-R), Yc=v=>T+(1-(v-lo)/(hi-lo))*(hh-T-B);
          const fm=v=>Math.round(v).toLocaleString();
          const gridY=[hi-pad,(hi+lo)/2,lo+pad].map(v=>
            `<line x1="${L}" y1="${Yc(v).toFixed(1)}" x2="${w-R}" y2="${Yc(v).toFixed(1)}" stroke="#eef1f5"/>`+
            `<text x="${L-4}" y="${(Yc(v)+3).toFixed(1)}" font-size="9" fill="#8a94a3" text-anchor="end">${fm(v)}</text>`).join('');
          const curLn=(cur&&cur>0)?`<line x1="${L}" y1="${Yc(cur).toFixed(1)}" x2="${w-R}" y2="${Yc(cur).toFixed(1)}" stroke="#e05252" stroke-dasharray="4,3" stroke-width="1.2"/>`+
            `<text x="${w-R}" y="${(Yc(cur)-3).toFixed(1)}" font-size="9" fill="#e05252" text-anchor="end">현재가 ${fm(cur)}</text>`:'';
          const xy=P2.map(z=>`${X(z.t.getTime()).toFixed(1)},${Yc(z.v).toFixed(1)}`);
          const dots=P2.map(z=>`<circle cx="${X(z.t.getTime()).toFixed(1)}" cy="${Yc(z.v).toFixed(1)}" r="2.4" fill="#1f6feb"><title>${z.d} · ${fm(z.v)}</title></circle>`).join('');
          /* (2026-08-09) 30·90일 이동평균선 — 각 발간일 시점에서 직전 N일 리포트 목표가 평균.
             개별 점의 널뜀을 걸러 '눈높이가 실제로 어디로 움직이는가'가 추이로 보인다. */
          const roll=(days,tt)=>{const a=P2.filter(z=>z.t.getTime()<=tt&&z.t.getTime()>tt-days*864e5).map(z=>z.v);
            return a.length?a.reduce((s,v)=>s+v,0)/a.length:null;};
          const mline=(days,col)=>{const pt=P2.map(z=>({t:z.t.getTime(),v:roll(days,z.t.getTime())})).filter(z=>z.v!=null);
            return pt.length>=2?`<polyline points="${pt.map(z=>`${X(z.t).toFixed(1)},${Yc(z.v).toFixed(1)}`).join(' ')}" fill="none" stroke="${col}" stroke-width="1.8"/>`:'';};
          const m30=mline(30,'#e08e3c'), m90=mline(90,'#27ae60');
          const xlab=`<text x="${L}" y="${hh-4}" font-size="9" fill="#8a94a3">${P2[0].d}</text>`+
            `<text x="${w-R}" y="${hh-4}" font-size="9" fill="#8a94a3" text-anchor="end">${P2[P2.length-1].d}</text>`;
          svg=`<div style="margin-top:6px"><svg width="${w}" height="${hh}" style="max-width:100%">${gridY}${curLn}`+
            (xy.length>=2?`<polyline points="${xy.join(' ')}" fill="none" stroke="#9db8e8" stroke-width="1"/>`:'')+
            `${m30}${m90}${dots}${xlab}</svg><div class="note"><span style="color:#1f6feb">●</span> 리포트 목표가(발간일 기준) · <span style="color:#e08e3c">— 30일 평균</span> · <span style="color:#27ae60">— 90일 평균</span> · <span style="color:#e05252">- - 현재가</span></div></div>`;
        }
      }
      /* (2026-08-09 실측) cTB24 는 기간이 아니라 **최근 ~24건**만 보관한다
         (삼성전자 24건 6/1~7/31 · SK하이닉스 24건 · 현대차 25건). 커버리지 많은 종목은
         90일 전체가 안 담기므로 '90일'이라 쓰면 거짓말 — 보유분 기준으로 표기한다. */
      const span=tp.length?`${tp[0].d}~${tp[tp.length-1].d}`:'';
      t2=`<div style="margin-top:10px"><b style="font-size:12px">목표주가 변동 (증권사 리포트 최근 ${tp.length}건 · ${span})</b>
        <span class="note">소스가 최근 ~24건만 보관 — 리포트 많은 종목은 90일 전체가 아닐 수 있음</span> ${avgLine}
        <div style="max-height:230px;overflow:auto;margin-top:4px"><table style="width:100%;font-size:11px;border-collapse:collapse">
        <tr style="border-bottom:1px solid var(--line)"><th style="text-align:left;padding:2px 4px">일자</th><th style="text-align:left">증권사</th><th>목표가</th><th>직전</th><th>변동</th><th>의견</th></tr>`+
        tp.slice().reverse().map(z=>`<tr style="border-bottom:1px solid #f4f6f8"><td style="padding:2px 4px">${z.d}</td><td>${E(z.b)}</td>
          <td style="text-align:right">${F(z.tp)}</td><td style="text-align:right;color:var(--tx2)">${F(z.prev)}</td>
          <td style="text-align:right">${P(z.chg)}</td><td style="text-align:center;font-size:10px">${E(z.op||'')}</td></tr>`).join('')+'</table></div>'+svg+'</div>';
    }
    /* ③ 컨센 영업이익 추정 — 90일 스냅샷 표 + 추이 그래프
       (2026-08-09 수정) 표는 스냅샷 1일치부터 바로 보인다. 이전엔 2일 이상일 때만
       그래프를 그리고 표가 없어서, 수집 초기에 섹션이 통째로 비어 보였다. */
    let t3='';
    const sn=(J.snap||[]).filter(z=>z.o!=null);
    if(sn.length){
      const byP={}; sn.forEach(z=>{(byP[z.p]=byP[z.p]||{})[z.d]=z.o;});
      const ps=Object.keys(byP).sort();
      const days=[...new Set(sn.map(z=>z.d))].sort();
      const d90=days.slice(-90);                       // 표·그래프 모두 최근 90일치
      /* 그래프(표 아래): 절대값(억원)은 분기 60만억 vs 연간 400만억이라 한 차트에 못 섞는다
         → 각 추정치의 **첫 스냅샷 대비 누적 변화율(%)**로 정규화해 항목별 한 차트에.
         점을 항상 찍으므로 1일차에도 차트가 보인다(전부 0% 기준선 위). */
      let svg='';
      {
        const w=Math.max(560,(el.clientWidth||620)-26),hh=220;   // 폭=표 폭 · 높이 2배
        /* 무지개 순서(빨강→주황→노랑→초록→파랑→보라) — 기간 순서와 색 순서를 일치시킨다 */
        const COLS=['#e03131','#f08c00','#d9a406','#2f9e44','#1c7ed6','#7048e8'];
        const base={}; ps.forEach(pp=>{ const f=d90.find(d=>byP[pp][d]!=null); base[pp]=(f!=null)?byP[pp][f]:null; });
        const pcv=(pp,d)=>{ const v=byP[pp][d]; return (v!=null&&base[pp])?((v/base[pp]-1)*100):null; };
        let lo=0,hi=0;
        ps.forEach(pp=>d90.forEach(d=>{ const p=pcv(pp,d); if(p!=null){ if(p<lo)lo=p; if(p>hi)hi=p; } }));
        if(hi-lo<0.5){ hi+=0.5; lo-=0.5; }
        const rg=hi-lo, X=i=>((d90.length>1?i/(d90.length-1):0.5)*(w-64)+8), Yc=p=>(hh-16-(p-lo)/rg*(hh-30));
        const zero=`<line x1="8" y1="${Yc(0).toFixed(1)}" x2="${w-56}" y2="${Yc(0).toFixed(1)}" stroke="#d7dce3" stroke-dasharray="3,3"/>`
          +`<text x="${w-52}" y="${(Yc(0)+3).toFixed(1)}" font-size="9" fill="#8a94a3">0%</text>`;
        const parts=ps.map((pp,k)=>{ const col=COLS[k%COLS.length];
          const pt=d90.map((d,i)=>({i,p:pcv(pp,d)})).filter(z=>z.p!=null);
          const xy=pt.map(z=>`${X(z.i).toFixed(1)},${Yc(z.p).toFixed(1)}`);
          const dots=pt.map(z=>`<circle cx="${X(z.i).toFixed(1)}" cy="${Yc(z.p).toFixed(1)}" r="2.2" fill="${col}"/>`).join('');
          return (xy.length>=2?`<polyline points="${xy.join(' ')}" fill="none" stroke="${col}" stroke-width="1.6"/>`:'')+dots; }).join('');
        const leg=ps.map((pp,k)=>{ const last=[...d90].reverse().map(d=>pcv(pp,d)).find(p=>p!=null);
          return `<span style="color:${COLS[k%COLS.length]}">● ${pp}(E)${last!=null?` ${last>0?'+':''}${last.toFixed(1)}%`:''}</span>`; }).join(' ');
        svg=`<div style="margin-top:6px"><svg width="${w}" height="${hh}" style="max-width:100%">${zero}${parts}</svg>
          <div class="note">${leg} — 첫 스냅샷(${d90[0]||''}) 대비 누적 변화율</div></div>`;
      }
      /* 표: 최신이 위 — 분기별 추정치 + 직전 스냅샷 대비 % */
      const rows=d90.slice().reverse().map(d=>{
        const di=days.indexOf(d), pd=di>0?days[di-1]:null;
        return `<tr style="border-bottom:1px solid #f4f6f8"><td style="padding:2px 4px">${d}</td>`+ps.map(pp=>{
          const v=byP[pp][d], pv=pd!=null?byP[pp][pd]:null;
          const ch=(v!=null&&pv!=null&&Math.abs(pv)>1)?((v/pv-1)*100):null;
          return `<td style="text-align:right">${v==null?'<span class="note">—</span>':Math.round(v).toLocaleString()}`+
            (ch==null?'':` <span class="${ch>0?'up':(ch<0?'dn':'note')}" style="font-size:10px">${ch>0?'+':''}${ch.toFixed(1)}%</span>`)+'</td>';
        }).join('')+'</tr>'; }).join('');
      const tbl=`<div style="max-height:230px;overflow:auto;margin-top:4px"><table style="width:100%;font-size:11px;border-collapse:collapse">
        <tr style="border-bottom:1px solid var(--line)"><th style="text-align:left;padding:2px 4px">일자</th>${ps.map(pp=>`<th style="text-align:right">${pp}(E) 영업익</th>`).join('')}</tr>${rows}</table></div>`;
      t3=`<div style="margin-top:10px"><b style="font-size:12px">영업이익 컨센서스 리비전 (90일)</b> <span class="note">(일별 스냅샷 · 억원 · %는 직전 스냅샷 대비)</span>
        ${tbl}${svg}<div class="note" style="margin-top:2px">매일 07:20 적립(2026-08-09 시작)${d90.length<2?' · 아직 1일치 — 점만 표시, 내일부터 선이 이어집니다':''} · 30/90일 리비전 필터는 스냅샷이 그만큼 쌓인 뒤 유효</div></div>`;
    }
    el.innerHTML=`<div class="box" style="padding:10px 12px"><b style="font-size:12.5px">📊 실적·전망</b> <span class="note">(${E(J.src||'')} · 단위 억원)</span>
      <div style="overflow:auto;margin-top:6px">${t1}</div>${t2}${t3}</div>`;
  }
  /* ── (2026-08-09) US 실적·전망 패널 — KR 과 동일 컨셉.
     ① 분기 실적표(매출/영업익/순익 · YoY/QoQ · ⚡흑전/적전) — Yahoo timeseries 실적치
     ② 컨센 추정(0q/+1q 분기 + 0y/+1y 연간 — 매출·EPS) — earningsTrend
     ③ EPS 추정 리비전 90일 — Yahoo 가 90/30/7일 전 값을 직접 줘 **즉시 4점 곡선**
     ④ 목표주가 — US 는 '현재 유효 평균'만 제공(기간 개념 없음 · 커버리지 중단 시에만 제외)
        → 일별 스냅샷(08-09 시작)으로 30/90일 리비전을 만든다(9/8·11/7 유효) */
  let _USFIN=null;                        // 차트 팝업 YoY/QoQ 계산에도 쓴다
  async function loadUsFin(c){
    const el=$('sd_fin'); if(!el) return;
    _USFIN=null;
    el.style.display=''; el.innerHTML='<span class="note">실적·전망 로드 중…</span>';
    /* (2026-08-15) 가이던스 개정 습관 — Benzinga 캐시에서 뽑은 2022~ 이력 요약(guidance_history.py).
       184KB 1회 로드 후 전역 캐시. 판정에는 쓰지 않는 참고 지표. */
    if(!window._TENDJ){ try{ window._TENDJ=await (await fetch('/api/db/guidance_tendency')).json(); }catch(e){ window._TENDJ={}; } }
    let J=null;
    try{ J=await (await fetch('/api/us_fin/'+encodeURIComponent(c))).json(); }catch(e){}
    if(dcode!==c) return;
    if(!J||!(J.q||[]).length){ el.innerHTML='<span class="note">분기 재무 데이터 없음</span>'; el.style.display='none'; return; }
    _USFIN=J; _paint();                   // 팝업 YoY/QoQ 즉시 반영
    const q=J.q, F=v=>v==null?'—':Math.round(v).toLocaleString();
    /* (2026-08-09 수정) 변화율 = (현재−기저)÷|기저| — 적자 기저 부호 뒤집힘 수정
       (실측 ABNB 2024/03: EPS −0.55→0.41 이 −174.5% 로 나오던 것을 +174.5% 로) */
    const pct=(a,b)=>(a!=null&&b!=null&&Math.abs(b)>0.005)?((a-b)/Math.abs(b)*100):null;
    /* (2026-08-09 수정) YoY/QoQ 매칭 — 정확한 라벨(−12/−3개월)이 아니라 **±1개월 허용**.
       4-4-5 회계 달력 회사는 분기말이 다음 달로 밀린다(실측 AAPL: 2023 분기가
       2023/04·2023/07 로 기록 → 2024/03 의 1년 전을 2023/03 으로 찾으면 없어서
       YoY 가 통째로 '—'). 목표 시점에서 가장 가까운 분기(차이 ≤1개월)를 기저로 쓴다. */
    const mnum=p=>+p.slice(0,4)*12 + +p.slice(5,7);
    const base=(i,mm)=>{ const t=mnum(q[i].p)-mm; let best=null,bd=99;
      for(const z of q){ const d=Math.abs(mnum(z.p)-t); if(d<bd){bd=d;best=z;} }
      return bd<=1?best:null; };
    const yoy=(i,k)=>{ const b=base(i,12); return b?pct(q[i][k],b[k]):null; };
    const qoq=(i,k)=>{ const b=base(i,3);  return b?pct(q[i][k],b[k]):null; };
    const P=v=>v==null?'<span class="note">—</span>':`<span class="${v>0?'up':(v<0?'dn':'note')}">${v>0?'+':''}${v.toFixed(1)}%</span>`;
    const opm=i=>(q[i].s&&q[i].o!=null)?(q[i].o/q[i].s*100):null;
    /* 전환 배지 — QoQ 칸에 붙으며 **부호가 바뀐 그 분기에만** 표시한다.
       ⚡흑전 = 직전 분기 적자(−) → 이번 분기 흑자(+) · ⚡적전 = 흑자(+) → 적자(−)
       흑자를 계속 유지 중인 분기에는 붙지 않는다(전환이 아니라 유지이므로). */
    const turn=(i,k)=>{ const b=base(i,3), pv=b?b[k]:null, cv=q[i][k];
      if(pv==null||cv==null) return '';
      if(pv<0&&cv>0) return ` <b style="color:#1f9d55" title="직전 분기 ${pv.toFixed(2)} 적자 → 이번 분기 ${cv.toFixed(2)} 흑자">⚡흑전</b>`;
      if(pv>0&&cv<0) return ` <b style="color:#c0392b" title="직전 분기 ${pv.toFixed(2)} 흑자 → 이번 분기 ${cv.toFixed(2)} 적자">⚡적전</b>`; return ''; };
    /* ① 분기 실적표 — (2026-08-09) 미국식 보는 순서: 매출 → EPS → 서프라이즈 → 영업이익률.
       영업익·순익 열은 빼고(이익률 계산에만 사용) EPS 를 전면에 — 미국 시장의 정식 지표. */
    const eF=v=>v==null?'—':(+v).toFixed(2);
    /* 컨센 셀 = 발표시점 컨센값 + 실제 대비 서프(비트/미스) 한 칸에 */
    const cCell=(val,spr,isEps)=>{ if(val==null&&spr==null) return '<span class="note">—</span>';
      return (val==null?'—':(isEps?(+val).toFixed(2):Math.round(val).toLocaleString()))
        +(spr==null?'':`<br><span class="${spr>0?'up':'dn'}" style="font-size:10.5px"><b>${spr>0?'비트':'미스'}</b> ${spr>0?'+':''}${spr.toFixed(1)}%</span>`); };
    /* (2026-08-10) 영업이익률 미제공이면 열 자체를 뺀다 — 은행 등 금융주는
       stockanalysis 손익에 영업이익 항목이 없어(실측 BAC 전분기 null) 전부 '—' 였다. */
    const hasOPM=q.some((_,i)=>opm(i)!=null);
    /* (2026-08-10) 발표시점 매출·EPS 컨센+판정 = Zacks 단일 소스 (~17년치).
       판정(sSpr·sprE)은 Zacks 의 컨센·실제 쌍 안에서 서버가 계산해 온다 — 실적 열
       (stockanalysis · ADR 은 현지통화)과 비교하지 않으므로 통화 섞임 오판정이 없다.
       ADR 은 Zacks 값이 US$ ADR 기준이라 왼쪽 실적 열과 통화가 다름을 라벨로 명시. */
    const isADR=J.cur&&J.cur!=='USD';
    /* (2026-08-10) 매출컨센 열은 항상 표시 — 값이 없으면 숨기지 않고 '—'+사유 툴팁
       (사용자 지시: 마음대로 숨기지 말 것). hasSE 는 각주 문구 분기용. */
    const hasSE=q.some(r=>r.sE!=null);
    /* (2026-08-10) ADR 은 EPS 실적 열도 Zacks 조정 EPS(US$ ADR)로 표시 — EPS·EPS컨센·
       판정이 전부 같은 소스(Zacks)·같은 통화(US$ ADR)가 된다 (실측 MUFG: ¥ EPS 와
       $ 컨센이 나란히 있어 혼란). YoY/QoQ/흑전 도 같은 시리즈로 계산. */
    const epsK=isADR?'epsA':'eps';
    /* (2026-08-10) 매출도 가능하면 US$ 통일 — 서버가 일관성 검사(공시매출/Zacks 비율이
       환율처럼 일정한지)를 통과시킨 경우에만 sUS 가 온다 (실측: TSM·ASML 통과,
       MUFG·MFG 는 Zacks '매출' 정의가 달라 탈락 → 현지통화 유지가 정직). */
    const hasSUS=q.filter(r=>r.sUS!=null).length>=4;
    const sK=(isADR&&hasSUS)?'sUS':'s';
    /* (2026-08-10) 실적표 = 사용자 지정 구조(2행 헤더) — 분기·발표날짜·EPS 4열·Revenue 4열·
       Gross Margin 3열·Operating Margin 3열·FCF 5열(YTD 포함)·CapEx 5열.
       마진은 %p 차이, 금액은 변화율(%). */
    const gmv=i=>{const r=q[i]; return (r.gp!=null&&r[sK])?(r.gp/r[sK]*100):null;};
    const dpp=(i,f,mm)=>{const b=base(i,mm); if(!b) return null;
      const a=f(i), c2=f(q.indexOf(b)); return (a==null||c2==null)?null:(a-c2);};
    const PP=v=>v==null?'<span class="note">—</span>':`<span class="${v>0?'up':(v<0?'dn':'')}">${v>0?'+':''}${v.toFixed(1)}%p</span>`;
    const MG=v=>v==null?'—':v.toFixed(1)+'%';
    const F1=v=>v==null?'—':Math.round(v).toLocaleString();
    const HB='padding:3px 4px;border-bottom:1px solid var(--line);white-space:nowrap';
    let t1=`<table style="width:100%;font-size:11px;border-collapse:collapse">
      <tr style="background:#f8fafc"><th rowspan="2" style="${HB};text-align:left">분기</th><th rowspan="2" style="${HB}">발표날짜</th>
        <th colspan="4" style="${HB}">EPS <span class="note">(${isADR?'US$ ADR·조정':'$'})</span></th>
        <th colspan="6" style="${HB}">Revenue <span class="note">(백만${isADR?(sK==='sUS'?' US$ ADR':' '+J.cur):'$'})</span></th>
        <th colspan="3" style="${HB}">Gross Margin</th><th colspan="3" style="${HB}">Operating Margin</th>
        <th colspan="3" style="${HB}">FCF <span class="note">(백만$)</span></th><th colspan="4" style="${HB}">CapEx <span class="note">(백만$)</span></th></tr>
      <tr style="background:#f8fafc;font-size:10.5px;color:#667085">
        <th style="${HB}">Actual</th><th style="${HB}">YoY</th><th style="${HB}">QoQ</th><th style="${HB}">Consensus</th>
        <th style="${HB}">Actual</th><th style="${HB}">YoY</th><th style="${HB}">QoQ</th><th style="${HB}">Consensus</th><th style="${HB}">YTD</th><th style="${HB}">YoY</th>
        <th style="${HB}">%</th><th style="${HB}">YoY</th><th style="${HB}">QoQ</th>
        <th style="${HB}">%</th><th style="${HB}">YoY</th><th style="${HB}">QoQ</th>
        <th style="${HB}">분기</th><th style="${HB}">YTD</th><th style="${HB}">YoY</th>
        <th style="${HB}">분기</th><th style="${HB}">YTD</th><th style="${HB}">YoY</th><th style="${HB}" title="회계연도 누적 CapEx ÷ 누적 매출 — 매출 대비 설비투자 강도">CapEx/Revenue</th></tr>`;
    /* (2026-08-09) 계산은 전체(최대 20분기)로 하고 표시는 최근 분기만.
       앞쪽 행은 1년 전 분기가 화면 밖에 있을 뿐 YoY 는 정상 계산된다.
       (2026-08-10) 10→8분기 — 매출컨센(발표시점)이 MarketBeat 2년치(8분기)라
       앞의 2행이 늘 공란이었다. 컨센 있는 범위에 맞춘다. */
    const VIS=Math.max(0,q.length-8);
    q.forEach((r,i)=>{ if(i<VIS) return; const m=opm(i);
      /* 판정: 서버가 Zacks 쌍으로 계산한 sSpr 우선 — 없을 때만(스냅샷 폴백 등)
         실적(stockanalysis)과 비교. ADR 은 sSpr 만 유효(통화가 다르므로). */
      const ssp=r.sSpr!=null?r.sSpr:((!isADR&&r.s!=null&&r.sE)?((r.s/r.sE-1)*100):null);
      const TD='text-align:right;padding:2px 4px';
      /* (2026-08-10) **직전 실적발표 분기**는 한국 화면과 같이 연녹색으로 구분한다.
         표의 마지막 행이 방금 발표된 분기다 — 지금 판단에 쓰는 값이라 눈에 먼저 들어와야 한다. */
      const LST=(i===q.length-1)?';background:#f6faf6':'';
      t1+=`<tr style="border-bottom:1px solid #f2f4f7${LST}"><td style="padding:2px 4px"><b>${r.p}</b>${/4$/.test(String(r.fq||"").toUpperCase().replace("Q",""))?' <b style="color:#1c7ed6;font-size:9.5px" title="회계연도 4분기 — 연간보고서(10-K) 기준. 나머지 분기는 10-Q">연간</b>':''}</td>
        <td style="text-align:center;padding:2px 4px" class="note">${r.ed?E(String(r.ed).slice(2)):'—'}</td>
        <td style="${TD}"><b>${eF(r[epsK])}</b></td><td style="${TD}">${P(yoy(i,epsK))}</td><td style="${TD}">${P(qoq(i,epsK))}${turn(i,epsK)}</td>
        <td style="${TD}" title="${r.epsA!=null?`발표 조정EPS ${(+r.epsA).toFixed(2)} vs 컨센 ${r.epsE!=null?(+r.epsE).toFixed(2):'—'}`:''}">${cCell(r.epsE,r.sprE,true)}</td>
        <td style="${TD}">${F(r[sK])}</td><td style="${TD}">${P(yoy(i,sK))}</td><td style="${TD}">${P(qoq(i,sK))}</td>
        <td style="${TD}" title="${r.sE==null?'발표시점 매출컨센 없음 — Zacks 에 이 분기 추정치 없음':''}">${cCell(r.sE,ssp,false)}</td>
        <td style="${TD}">${F(r.sY)}</td><td style="${TD}">${P(yoy(i,'sY'))}</td>
        <td style="${TD}">${MG(gmv(i))}</td><td style="${TD}">${PP(dpp(i,gmv,12))}</td><td style="${TD}">${PP(dpp(i,gmv,3))}</td>
        <td style="${TD}">${MG(m)}</td><td style="${TD}">${PP(dpp(i,opm,12))}</td><td style="${TD}">${PP(dpp(i,opm,3))}</td>
        <td style="${TD}">${F1(r.fcf)}</td><td style="${TD}">${F1(r.fcfY)}</td><td style="${TD}">${P(yoy(i,'fcfY'))}</td>
        <td style="${TD}">${F1(r.capex)}</td><td style="${TD}">${F1(r.capexY)}</td><td style="${TD}">${P(yoy(i,'capexY'))}</td>
        <td style="${TD}" title="회계연도 누적 CapEx ÷ 누적 매출">${r.cxr==null?'<span class="note">—</span>':'<b>'+r.cxr.toFixed(1)+'%</b>'}</td></tr>`; });
    t1+='</table><div class="note" style="margin-top:3px"><b>출처</b> — 실적·마진·FCF·CapEx: stockanalysis(10-Q/K · 분기 옆 <b style="color:#1c7ed6">연간</b> 표시는 회계연도 4분기=10-K 기준) · 발표날짜·발표시점 컨센·판정: Zacks(조정 EPS 기준) · '
      +(isADR?`<b>현지통화(${J.cur}) 결산 ADR</b> — ${sK==='sUS'?`매출·EPS·컨센·판정 전부 Zacks <b>US$ ADR 기준으로 통일</b>(영업이익률만 현지 공시 재무의 비율 — 통화 무관)`:`EPS·EPS컨센·판정은 Zacks <b>US$ ADR·조정 EPS 통일</b> · 매출은 ${J.cur} 유지(Zacks 매출 실제가 공시 매출과 규모 불일치 — 정의가 달라 US$ 통일 시 틀린 값이 됨)`}`
             :'매출·EPS 컨센(발표시점)·판정은 Zacks 발표 이력(컨센·실제 쌍 · 조정 EPS 기준)')
      +'<br>변화율 = (이번−기저)÷|기저| · 마진은 <b>%p</b> 차이 · YTD = 회계연도 누적(Q1 리셋) · <b style="color:#1f9d55">⚡흑전</b> = 직전 분기 적자(−)에서 이번 분기 흑자(+)로 <b>바뀐 분기에만</b> 표시 · <b style="color:#c0392b">⚡적전</b> = 그 반대 · 흑자를 계속 유지 중인 분기에는 배지가 붙지 않는다(전환이 아니므로)</div>';
    /* (2026-08-09) 가이던스 vs 컨센 비교 표+막대 — 실전 우선순위 ①매출 ②EPS.
       자동 파싱 가능한 두 항목만 숫자로, 마진·EBITDA·FCF·CAPEX·가입자 등은 보도자료·어닝콜
       원문에만 있어(형식 자유) 링크로 안내한다. 비교 대상은 '회사 가이던스 vs 애널 컨센'
       — 회사가 EPS 가이던스를 안 주면 매출 가이던스+마진 전망으로 이익 방향을 추정할 것. */
    /* (2026-08-09) 위쪽 '가이던스 vs 컨센서스' 막대표는 아래 '직전 실적발표 가이던스' 표와
       내용이 겹쳐(같은 8-K 값·같은 갭) 제거했다 — 아래 표가 기간 4종을 모두 담는 상위 호환. */
    /* ①-b 컨센 추정 — 분기·연간 (회사가 공식으로 주는 미래치는 가이던스(매출·EPS), 여긴 애널 컨센) */
    const LBL={'0q':'진행분기','+1q':'다음분기','0y':'올해(FY)','+1y':'내년(FY)'};
    if((J.est||[]).length){
      /* (2026-08-09) 매출·EPS·애널수 3열. 영업이익률은 야후가 영업익 추정 자체를 안 줘서
         컨센 산출 불가 — 모든 행에 같은 TTM 값이 반복돼 오해만 주므로 열을 뺐다
         (실적 기준 영업이익률은 위 분기 실적표에 이미 있다). */
      /* (2026-08-09) 순서: 가이던스(회사 전망) → 컨센서스 추정(애널) — 실전 우선순위대로 */
      const gd2=J.gd;
      /* 8-K 접수 인덱스 → 보도자료(Exhibit 99) 원문. 진행분기·다음분기·연간 전망의
         실제 문장이 여기에 있다(우리 파서는 분기 매출·EPS만 자동 추출). */
      const gdU=(gd2&&gd2.acc&&_ECIK)?`https://www.sec.gov/Archives/edgar/data/${parseInt(_ECIK,10)}/${String(gd2.acc).replace(/-/g,'')}/${gd2.acc}-index.htm`:null;
      t1+=`<div style="margin-top:8px"><b style="font-size:12px">직전 실적발표 가이던스</b> <span class="note">${gd2?`(발표일 ${E(gd2.d)} · 8-K 보도자료 파싱)`:'(파싱된 값 없음)'}</span>
        ${gdU?`<a href="${gdU}" target="_blank" rel="noopener" style="font-size:11px">📄 실적발표 자료 원문↗</a>`:''}
        <table style="width:100%;font-size:11.5px;border-collapse:collapse;margin-top:2px">
        <tr style="border-bottom:1px solid var(--line)"><th style="text-align:left;padding:3px 4px">구분</th><th>기간</th>
        <th>매출 가이던스</th><th>매출 컨센</th><th>매출 가이던스 갭</th><th class="note">매출 가이던스 갭(포털)</th>
        <th>EPS 가이던스</th><th>EPS 컨센</th><th>EPS 가이던스 갭</th><th class="note">EPS 가이던스 갭(포털)</th><th title="회사가 제시한 설비투자 가이던스 — 애널리스트 CapEx 컨센서스는 존재하지 않는다">CapEx(E)</th><th>CapEx/Revenue(E)</th><th title="영업현금흐름(최근 4분기) × 매출 성장 − CapEx(E) · 추정">FCF(E)</th></tr>`+
        ['0q','+1q','0y','+1y'].map(per=>{
          const e3=(J.est||[]).find(z=>z.per===per)||{};
          /* (2026-08-09 수정) 가이던스를 **그 값이 실제로 가리키는 분기 행**에 놓는다.
             회사가 실적발표에서 주는 '다음 분기'는 그 시점 진행 중인 분기(0q)라
             예전처럼 +1q 행에 고정하면 컨센 열과 갭이 서로 다른 분기가 됐다
             (실측 ABNB: 가이던스 4,730 · 갭 0.0% 인데 옆 컨센은 +1q 3,154). */
          /* (2026-08-10) 매출·EPS 가 **각각 다른 기간**을 가리킬 수 있다 —
             매출은 분기만, EPS 는 연간만 주는 회사가 흔하다. 서버가 우선순위
             (진행분기→다음분기→올해FY→내년FY)로 고른 기간을 항목별로 받아 그 행에 놓는다. */
          const grp=(gd2&&(gd2.revPer||gd2.per))||'0q', gep=(gd2&&(gd2.epsPer||gd2.per))||'0q';
          const gr=(gd2&&per===grp)?gd2.rev:null, ge=(gd2&&per===gep)?gd2.eps:null;
          const jr=(gd2&&per===grp)?gd2.revGap:null, je=(gd2&&per===gep)?gd2.epsGap:null;
          const J2=v=>v==null?'<span class="note">—</span>':`<span class="${v>0?'up':'dn'}"><b>${v>0?'상회':'하회'}</b> ${v>0?'+':''}${(+v).toFixed(1)}%</span>`;
          /* (2026-08-10) 근거 문장 툴팁 — 파싱값이 보도자료 어디서 나왔는지 즉시 확인.
             "값이 맞나?"를 화면에서 바로 검증할 수 있어야 신뢰할 수 있다. */
          /* (2026-08-10) 교차검증 배지 — 포털 값과 대조한 결과만 표시한다.
             표시·판정에 쓰는 값은 언제나 우리 8-K 파싱값이며, 포털 값으로 교체하지 않는다
             (사용자 지시: "단, 판정에 사용은 하지 말것"). */
          const SB=(src,own)=>src==='verified'?' <b style="color:#1f9d55" title="포털(Benzinga) 값과 일치 — 교차검증 완료">✓</b>':'';
          /* 포털 갭 셀 — 색 없이(note) 표시해 '판정에 쓰는 값이 아님'을 시각적으로 구분 */
          const GP=(v,mine,nm)=>{
            if(v==null) return '<span class="note" title="포털에 같은 기간 가이던스가 없거나 컨센 역매칭 실패 — 대조 불가">—</span>';
            const d=(mine!=null)?(Math.abs(v-mine)<=1?'파싱값과 일치':`파싱값과 ${Math.abs(v-mine).toFixed(1)}%p 차이`):'파싱값 없음';
            return `<span class="note" title="포털(Benzinga) ${nm} 가이던스 갭 — 파싱 검증용 대조값 · ${d} · 판정에는 사용하지 않음">⤴${v>0?'+':''}${(+v).toFixed(1)}%</span>`; };
          /* (2026-08-10) 설비투자 3열 — 회사가 CapEx 가이던스를 준 기간 행에만 채운다.
             애널리스트 CapEx 컨센서스는 무료로 존재하지 않아 회사 발표가 유일한 근거다.
             FCF(E) 는 추정(≈) — 영업현금흐름(최근 4분기) × 매출성장 − CapEx(E)
             (시황 보고서 3.1.8 과 같은 산식). CapEx 가 없으면 FCF 도 만들지 않는다. */
          const CXC=(pp,e4)=>{
            const MI='<td style="text-align:right"><span class="note">미제시</span></td>';
            const gc=(gd2&&gd2.capex!=null&&(gd2.capexPer||'0y')===pp)?gd2.capex:null;
            if(gc==null) return MI+MI+MI;
            let ocf=0,rvT=0,ok=0;
            (J.q||[]).slice(-4).forEach(z=>{ if(z.fcf!=null&&z.capex!=null&&z.s!=null){ ocf+=z.fcf+Math.abs(z.capex); rvT+=z.s; ok++; } });
            const rv=e4&&e4.rev, fe=(ok===4&&rvT>0&&rv)?(ocf*(rv/rvT)-gc):null;
            return `<td style="text-align:right" title="${E(gd2.capexEv||'')}"><b>${Math.round(gc).toLocaleString()}</b></td>`
                 + `<td style="text-align:right">${rv?((gc/rv*100).toFixed(1)+'%'):'<span class="note">—</span>'}</td>`
                 + `<td style="text-align:right" title="추정 — 영업현금흐름(TTM) ${Math.round(ocf).toLocaleString()} 기준">${fe==null?'<span class="note">—</span>':'<span class="note">≈</span>'+Math.round(fe).toLocaleString()}</td>`; };
          const evR=(gd2&&per===grp&&gd2.revEv)?` title="근거: ${E(gd2.revEv)}"`:'';
          /* (2026-08-21) 리츠 FFO — 리츠는 컨센서스가 FFO 기준이라 EPS 갭을 만들지 않는다
             (만들면 FFO 컨센과 비교돼 +64~967% 왜곡). 그래서 EPS 칸이 늘 '미제시'였다.
             회사가 낸 FFO 가이던스 값 자체는 유효한 선행 정보이므로 그 칸에 대신 싣되,
             무료 FFO 컨센서스가 없어 갭은 계산하지 않는다(판정 열은 '—' 그대로). */
          const gf=(gd2&&gd2.ffo!=null&&(gd2.ffoPer||'0y')===per)?gd2.ffo:null;
          const evE=(gd2&&per===gep&&gd2.epsEv)?` title="근거: ${E(gd2.epsEv)}"`
                    :((gf!=null&&gd2.ffoEv)?` title="근거: ${E(gd2.ffoEv)}"`:'');
          /* (2026-08-21) 성장률 가이던스 — 금액을 아예 안 주고 성장률로만 말하는 회사가 있다
             (실측 47건: ADP '매출 +5~6% · EPS +9~11%' · GPC '총매출 +3~5.5%' 등).
             금액 환산은 도입하지 않는다(기준 차이로 오차가 커진다는 실측 결론) — 성장률
             그대로 보여주고, 컨센서스는 금액이라 갭은 만들지 않는다. */
          const GRC=(v,lo,hi,pp,ev)=>{
            if(v==null||pp!==per) return null;
            const rng=(lo!=null&&hi!=null&&lo!==hi)?`+${lo}~${hi}%`:`${v>0?'+':''}${v}%`;
            return `<b>${rng}</b> <span class="note" title="회사가 금액 대신 성장률로만 제시한 가이던스다. 컨센서스는 금액이라 상회/하회 갭은 계산하지 않는다.${ev?' · 근거: '+E(ev):''}">성장률</span>`; };
          const grR=(gd2&&per===grp)?null:(gd2?GRC(gd2.revGr,gd2.revGrLo,gd2.revGrHi,gd2.revGrPer||'0y',gd2.revGrEv):null);
          const grE=(gd2&&per===gep&&ge!=null)?null:(gd2?GRC(gd2.epsGr,gd2.epsGrLo,gd2.epsGrHi,gd2.epsGrPer||'0y',gd2.epsGrEv):null);
          const FFOC=gf!=null
            ?`<b>${(+gf).toFixed(2)}</b> <span class="note" title="리츠는 애널리스트 컨센서스가 순이익(EPS)이 아니라 FFO 기준이라 EPS 가이던스로는 비교가 성립하지 않는다. 회사가 제시한 FFO 가이던스 값을 대신 싣는다 — 무료 FFO 컨센서스가 없어 갭(상회/하회)은 계산하지 않는다.">${gd2.ffoBasis==='core'?'조정FFO':'FFO'}</span>`
            :(grE||'<span class="note">미제시</span>');
          return `<tr style="border-bottom:1px solid #f2f4f7;background:#f6faf6"><td style="padding:3px 4px"><b>${LBL[per]}</b></td><td style="text-align:center" class="note">${E(e3.end||'—')}</td>
            <td style="text-align:right"${evR}>${gr==null?(grR||'<span class="note">미제시</span>'):'<b>'+Math.round(gr).toLocaleString()+'</b>'+SB(gd2.revSrc,gd2.revOwn)}</td>
            <td style="text-align:right">${F(e3.rev)}</td><td style="text-align:right">${J2(jr)}</td>
            <td style="text-align:right">${(gd2&&per===((gd2.revPerP||grp)))?GP(gd2.revGapP,gd2.revGap,'매출'):'<span class="note">—</span>'}</td>
            <td style="text-align:right"${evE}>${ge==null?FFOC:'<b>'+(+ge).toFixed(2)+'</b>'+SB(gd2.epsSrc,gd2.epsOwn)}</td>
            <td style="text-align:right">${e3.eps==null?'—':(+e3.eps).toFixed(2)}</td><td style="text-align:right">${J2(je)}</td>
            <td style="text-align:right">${(gd2&&per===((gd2.epsPerP||gep)))?GP(gd2.epsGapP,gd2.epsGap,'EPS'):'<span class="note">—</span>'}</td>
            ${CXC(per,e3)}</tr>`; }).join('')+
        `</table>${(function(){          /* (2026-08-21) 이 회사의 가이던스 제시 습관 — 값이 비었을 때
             '원래 안 주는 회사'인지 '우리가 놓친 것'인지 구분하는 근거다(출처 Benzinga 이력). */
          const pf=gd2&&gd2.prof; if(!pf||!pf.n) return '';
          const pe=pf.per||{}, hs=pf.has||{}, bs=pf.basis||{};
          const per=[pe.FY?`연간 ${pe.FY}회`:'',pe.Q?`분기 ${pe.Q}회`:''].filter(Boolean).join(' · ');
          const met=[hs.rev?`매출 ${hs.rev}회`:'',hs.eps?`EPS ${hs.eps}회`:''].filter(Boolean).join(' · ');
          const ba=[bs.eps?`EPS ${bs.eps}`:'',bs.rev?`매출 ${bs.rev}`:''].filter(Boolean).join(' · ');
          /* 이력상 늘 제시하는데 이번엔 못 뽑은 지표 — 빈 칸이 '회사가 안 준 것'인지
             '우리가 놓친 것'인지 구분해 준다. 값을 지어내지 않고 한계를 드러낸다. */
          const MS={rev:'매출',eps:'EPS'};
          const ms=(gd2.miss||'').split(',').filter(Boolean).map(x=>MS[x]||x).join('·');
          const warn=ms?` <b class="dn">※ ${ms} 미확보</b> <span class="note">— 이 회사는 평소 제시하는 항목인데 이번 공시에서 뽑지 못했다(보조 첨부까지 확인). 표의 '미제시'는 회사가 안 준 것이 아니라 우리가 놓친 것일 수 있다.</span>`:'';
          return `<div class="note" style="margin-top:4px">이 회사의 가이던스 습관 <b>(${E(pf.first||'')}~${E(pf.last||'')} · 이력 ${pf.n}건)</b> — 제시 기간: ${per||'—'} · 제시 지표: ${met||'—'}${ba?' · 기준: '+ba:''}${warn} <span class="note">(출처 Benzinga 이력 — 위 표의 값이 이 습관과 어긋나면 파싱을 의심할 근거다)</span></div>`;})()}<div class="note" style="line-height:1.7"><b>구분 읽는 법</b> — <b>진행분기</b>: 진행 중인 다음 분기 또는 직후 분기 <b>(가장 중요)</b> · <b>다음분기</b>: 그다음 분기(회사가 제시하면 확인) · <b>올해(FY)</b>: 연간 전망 <b>(매우 중요)</b> · <b>내년(FY)</b>: 내년 연간 전망(회사가 제시할 때만 확인)<br>판정 = 가이던스 중간값 ÷ 같은 기간 컨센 − 1 · 회사가 숫자 가이던스를 안 주면 '미제시'(애플형) · <b>연간(FY) 가이던스도 연간 컨센과 비교해 표시</b>(2026-08-10 추가) · 매출·EPS 는 각각 우선순위(진행분기→다음분기→올해FY→내년FY)로 해당 행에 배치<br><b>성장률</b> 표기 — 금액을 아예 제시하지 않고 성장률로만 말하는 회사가 있다(예: '매출 +5~6% · EPS +9~11%'). 이때는 성장률을 그대로 싣는다. 전년 실적으로 금액을 역산하지 않는 이유는 회사가 쓰는 기준(환율 중립·조정 등)이 달라 오차가 커지기 때문이며, 같은 이유로 <b>갭(상회/하회)도 계산하지 않는다</b>.<br><b>FFO</b> 표기 — 리츠(부동산)는 애널리스트 컨센서스가 순이익(EPS)이 아니라 <b>FFO</b> 기준이라 EPS 가이던스로는 비교가 성립하지 않는다. 그래서 EPS 칸에 회사가 제시한 FFO 가이던스 값을 대신 싣고, 무료 FFO 컨센서스가 없어 <b>갭(상회/하회)은 계산하지 않는다</b>. '조정FFO' 는 회사가 주력으로 제시하는 Core/Normalized/Adjusted FFO 다.<br><b>CapEx(E)</b> = 회사가 제시한 설비투자 가이던스(8-K 파싱) — 애널리스트 CapEx 컨센서스는 무료로 존재하지 않아 회사 발표가 유일한 근거다. 제시하지 않으면 '미제시'. <b>FCF(E)</b> 는 추정(≈): 영업현금흐름(최근 4분기) × 매출성장 − CapEx(E) — 시황 보고서 3.1.8 과 같은 산식.<br><b>가이던스 갭(포털)</b> = 같은 항목을 포털(Benzinga)에서 받아 계산한 갭 — <b>우리 8-K 파싱이 맞는지 눈으로 대조하는 검증용</b>이다. 색을 칠하지 않은 것은 <b>상회/하회 판정에는 쓰지 않기 때문</b>이며, 판정은 언제나 왼쪽 파싱값 기준이다. '—' 는 포털에 같은 기간 값이 없거나 컨센 역매칭에 실패해 대조하지 못한 경우다.</div></div>`;
      /* (2026-08-15) 가이던스 개정 습관 한 줄 — Benzinga 이력(2022~) 기반 자체 파생 신호.
         상향/하향 습관은 다음 가이던스의 방향 기대치를 잡는 데 쓰인다(판정 미사용). */
      { const td=(window._TENDJ&&window._TENDJ.sym)?window._TENDJ.sym[c]:null;
        if(td&&td.n>=3){
          const cls=td.up>=td.dn*1.5+1?'up':(td.dn>=td.up*1.5+1?'dn':'note');
          const lab=cls==='up'?'상향 성향':(cls==='dn'?'하향 성향':'중립');
          t1+=`<div class="note" style="margin-top:4px">가이던스 개정 습관 <b>(${E(td.first)}~${E(td.last)} · 이력 ${td.n}건)</b> — 개정 시 상향 ${td.up} · 유지 ${td.same} · 하향 ${td.dn} → <b class="${cls==='note'?'':cls}">${lab}</b> · 제시 구성: 연간 ${td.fy}% / 분기 ${td.q}% <span class="note">(출처 Benzinga 이력 — 참고용, 판정 미사용)</span></div>`; } }
      t1+=`<div style="margin-top:8px"><b style="font-size:12px">컨센서스 추정</b> <span class="note">(애널리스트 · 매출 백만$ · EPS $ · 영업이익률은 컨센 미제공 — 실적 마진은 위 분기표 참조)</span>
        <table style="width:100%;font-size:11.5px;border-collapse:collapse;margin-top:2px">
        <tr style="border-bottom:1px solid var(--line)"><th style="text-align:left;padding:3px 4px">구분</th><th>기간</th>
        <th>매출(E)</th><th>EPS(E)</th><th>애널수</th></tr>`+
        J.est.map(e2=>`<tr style="border-bottom:1px solid #f2f4f7;background:#fff7ea">
            <td style="padding:3px 4px"><b>${LBL[e2.per]||e2.per}</b></td><td style="text-align:center">${E(e2.end||'')}</td>
            <td style="text-align:right">${F(e2.rev)}</td>
            <td style="text-align:right">${e2.eps==null?'—':e2.eps.toFixed(2)}</td>
            <td style="text-align:right">${e2.nan??'—'}</td></tr>`).join('')+'</table></div>';
    }
    /* ② EPS 추정 리비전 — 표 + 4점 곡선 (즉시) */
    let t3='';
    const RV=(J.rev||[]).filter(z=>z.cur!=null);
    /* (2026-08-14) 저기저 문제(ZIM 0.08→1.38 = +1452%처럼 기저가 작아 %가 과장되는 경우) 대응.
       현재가 — %가 폭주할 때 참고할 '주가 대비 %p'(=Δ÷주가)의 분모. 차트가 이미 그렸으면 최신 종가,
       아니면 스크리너 풀의 px(어제 종가)로 대체. */
    const _polRV=(POOL.us||[]).find(z=>z.c===c)||{};
    const _pxRV=(_CD&&_CD.c)?[..._CD.c].reverse().find(v=>v!=null):_polRV.px;
    if(RV.length){
      /* (2026-08-09 3차) 사용자 확정 사양:
         · 표 = 각 시점 실제 EPS + (현재값 대비 몇 % 수준인지)
         · 그래프 = %축 없이 4종 각각 **실제 EPS 값** — 축 크기가 달라(0.5 vs 9.6) 한 축에
           못 섞으므로 항목별 미니 패널 4개(각자 y축)로 그린다
         · 데이터 = 자체 일별 스냅샷(매일 08:00 적립)이 8일 이상이면 일별 곡선,
           그 전엔 야후 5개 시점(90/60/30/7/현재) — 쌓이는 대로 자동 전환 */
      const w=Math.max(560,(el.clientWidth||620)-26);
      const COLS={'0q':'#e03131','+1q':'#f08c00','0y':'#2f9e44','+1y':'#1c7ed6'};
      const SNKEY={'0q':'eq0','+1q':'eq1','0y':'ey0','+1y':'ey1'};
      const snAll=(J.snap||[]);
      const today=new Date();
      const series=z=>{                                   // → [{t(일 오프셋), v}] 시간 오름차순
        const sk=SNKEY[z.per];
        let sn=snAll.filter(s=>s[sk]!=null);
        /* (2026-08-27) **발표 롤오버 절단** — 분기 지표(진행분기·다음분기)는 실적 발표
           순간 다음 분기로 넘어간다. 자체 스냅샷은 '그날의 진행분기'를 적립하므로 발표
           이전 스냅은 **이전 분기의 컨센**이고, 이를 이어 그리면 표(현재 분기 기준 90일)와
           모순되는 가짜 급등이 생긴다. 실측 NVDA D+1: 표는 90일 내내 2.34(Q3 기준)인데
           그래프는 발표 전 Q2 컨센 2.08에서 발표 후 Q3 2.34 로 점프해 급등처럼 보였다.
           발표일 이후 스냅만 그리고, 남은 점이 적으면 야후 5시점(현재 분기 기준)으로
           자동 폴백해 표와 기준이 일치한다. 연간(FY)은 발표로 대상이 바뀌지 않아 그대로. */
        if((z.per==='0q'||z.per==='+1q')&&_polRV.edl){
          const ed=String(_polRV.edl).replace(/(\d{4})(\d{2})(\d{2})/,'$1-$2-$3');
          sn=sn.filter(s=>String(s.d)>ed);
        }
        const daily=sn.map(s=>({t:Math.round((new Date(s.d)-today)/864e5), v:s[sk]}));
        if(daily.length>=8) return {pts:daily, daily:true};
        return {pts:[['d90',-90],['d60',-60],['d30',-30],['d7',-7],['cur',0]]
          .map(([k,t])=>z[k]!=null?{t,v:z[k]}:null).filter(Boolean), daily:false};
      };
      let anyDaily=false;
      const pw=Math.floor((w-18)/4), ph=150;
      const panels=RV.slice(0,4).map((z,zi)=>{
        const col=COLS[z.per]||'#888', S=series(z); if(S.daily) anyDaily=true;
        const pt=S.pts; if(!pt.length) return '';
        let lo=Math.min(...pt.map(p=>p.v)), hi=Math.max(...pt.map(p=>p.v));
        const pad=(hi-lo)*0.18||Math.abs(hi)*0.02||0.05; lo-=pad; hi+=pad;
        const t0=pt[0].t, t1=pt[pt.length-1].t||0;
        const X=t=>8+(t-t0)/((t1-t0)||1)*(pw-16);
        const Y=v=>22+(1-(v-lo)/((hi-lo)||1))*(ph-46);
        const line=pt.length>=2?`<polyline points="${pt.map(p=>`${X(p.t).toFixed(1)},${Y(p.v).toFixed(1)}`).join(' ')}" fill="none" stroke="${col}" stroke-width="2"/>`:'';
        const dots=pt.map(p=>`<circle cx="${X(p.t).toFixed(1)}" cy="${Y(p.v).toFixed(1)}" r="${S.daily?1.8:3}" fill="${col}"><title>${p.t===0?'현재':(-p.t)+'일 전'} EPS ${p.v.toFixed(2)}</title></circle>`).join('');
        const v0=pt[0].v, v1=pt[pt.length-1].v;
        return `<svg width="${pw}" height="${ph}" style="max-width:100%">
          <text x="8" y="13" font-size="11" font-weight="bold" fill="${col}">${LBL[z.per]||z.per}</text>
          <text x="${pw-6}" y="13" font-size="10" fill="#5b6470" text-anchor="end">${v1.toFixed(2)}</text>
          ${line}${dots}
          <text x="8" y="${ph-4}" font-size="9" fill="#8a94a3">${-t0}일 전 ${v0.toFixed(2)}</text>
          <text x="${pw-6}" y="${ph-4}" font-size="9" fill="#8a94a3" text-anchor="end">현재</text></svg>`; }).join('');
      const leg=`<span class="note">항목별 개별 y축(실제 EPS $) — 값 크기가 달라 한 축에 못 섞음 · ${anyDaily?'자체 일별 스냅샷 곡선':'야후 5개 시점 — 일별 스냅샷이 8일 이상 쌓이면 자동으로 일별 곡선 전환'} (매일 08:00 적립 중${snAll.length?` · 현재 ${snAll.length}일치`:''})</span>`;
      /* (2026-08-09 재수정) 표와 그래프의 기준 통일 — 둘 다 **90일 전 대비 누적 변화율**.
         이전엔 표가 '현재 대비'라 왼쪽부터 읽으면 −16.4→−15.5→−1.9 로 줄어드는데
         그래프는 0→−16 으로 커져 서로 반대로 보였다. 이제 표를 왼쪽→오른쪽으로 읽으면
         그래프 궤적과 정확히 같다. 60일 전 열 추가(야후 제공 확인). */
      /* (2026-08-09 3차) 표 = 각 시점 값 + **현재값 대비 몇 % 수준**(현재=100%).
         100% 초과(파랑) = 그때 추정이 지금보다 높았다 = 이후 하향
         100% 미만(빨강) = 그때가 더 낮았다 = 이후 상향 */
      const f2=v=>v==null?'—':v.toFixed(2);
      /* (2026-08-14) 괄호 = **그 시점→현재 변화율** 로 통일 — 스크리너의
         'EPS 컨센 리비전 변화율' 필터와 같은 산식(현재÷그때−1)이라 두 화면 숫자가 맞아떨어진다.
         예전 '현재 대비 수준(%)' 표기는 ZIM 처럼 0.09→1.38 인 종목에서 필터 +1,214% 와
         표 6.4% 가 서로 다른 수치처럼 보이게 했다(실은 같은 데이터의 다른 표현).
         (2026-08-14 추가, 저기저 대응 1+2+3) 기저가 작아 %가 과장되는 문제(ZIM +1452%)를
         숨기지 않고 함께 보여준다: ① 절대변화(Δ) 병기 ② 기저<0.5 면 ⚠저기저 배지
         ③ 주가 대비 %p(=Δ÷현재가) — 기저 크기와 무관해 종목간 비교엔 이 값이 더 적절하다. */
      const lvl=(v,cur,px)=>{ if(v==null||cur==null) return '';
        const delta=cur-v, dS=(delta>0?'+':'')+delta.toFixed(2);
        let pctHtml;
        if(v>0){
          const p=(cur/v-1)*100, z=Math.abs(p)<0.05;
          pctHtml=`<span class="${z?'':(p>0?'up':'dn')}"${z?' style="color:#3d454f"':''}>${p>0?'+':''}${p.toFixed(1)}%</span>`;
        } else {
          pctHtml='<span class="note">기저≤0(%무의미)</span>';
        }
        const pxp=(px&&px>0)?(delta/px*100):null;
        const pxHtml=pxp!=null?`, <span class="note">주가대비${pxp>0?'+':''}${pxp.toFixed(2)}%p</span>`:'';
        const warnHtml=Math.abs(v)<0.5?` <span class="note" title="기저 EPS ${v.toFixed(2)} — 값이 작아 %가 과장돼 보일 수 있음. 주가대비%p 를 함께 참고">⚠저기저</span>`:'';
        return ` <span style="font-size:10.5px">(${pctHtml}, Δ${dS}${pxHtml})</span>${warnHtml}`; };
      t3=`<div style="margin-top:10px"><b style="font-size:12px">EPS 컨센서스 리비전 (90일)</b> <span class="note">(괄호 = 그 시점 → 현재 <b>변화율, Δ절대변화, 주가대비%p</b> — 변화율은 스크리너 'EPS 컨센 리비전 변화율' 필터와 같은 산식. ⚠저기저 = 기저 EPS&lt;0.5 로 %가 과장될 수 있음. 필터 값은 진행분기·다음분기 평균)</span>
        <table style="width:100%;font-size:11px;border-collapse:collapse;margin-top:3px">
        <tr style="border-bottom:1px solid var(--line)"><th style="text-align:left;padding:2px 4px">구분</th><th>90일 전</th><th>60일 전</th><th>30일 전</th><th>7일 전</th><th>현재<span class="note">(=100%)</span></th></tr>`+
        RV.map(z=>
          `<tr style="border-bottom:1px solid #f4f6f8"><td style="padding:2px 4px"><b style="color:${COLS[z.per]||'#888'}">${LBL[z.per]||z.per}</b></td>
            <td style="text-align:right">${f2(z.d90)}${lvl(z.d90,z.cur,_pxRV)}</td>
            <td style="text-align:right">${f2(z.d60)}${lvl(z.d60,z.cur,_pxRV)}</td>
            <td style="text-align:right">${f2(z.d30)}${lvl(z.d30,z.cur,_pxRV)}</td>
            <td style="text-align:right">${f2(z.d7)}${lvl(z.d7,z.cur,_pxRV)}</td>
            <td style="text-align:right"><b>${f2(z.cur)}</b></td></tr>`).join('')+'</table>'+
        /* (2026-08-14) 스크리너 필터·컬럼에 뜨는 cr7/cr30(→화면엔 pr7/pr30, %p) 값은
           위 표의 진행분기(0q)·다음분기(+1q) 두 행을 **평균**한 것이라, 표에 그 숫자 자체가
           별도 행으로 없으면 "필터값이 표랑 안 맞는 거 아니냐"는 오해가 생긴다(실측 확인됨).
           풀에 이미 저장된 값(_polRV)을 그대로 보여줘 같은 수치임을 눈으로 확인시킨다. */
        (()=>{ const parts=[];
          if(_polRV.pr7!=null) parts.push(`7일 <b>${_polRV.pr7>0?'+':''}${(_polRV.pr7*100).toFixed(2)}%p</b>${_polRV.cr7!=null?`(원래 ${_polRV.cr7>0?'+':''}${(_polRV.cr7*100).toFixed(1)}%)`:''}`);
          if(_polRV.pr30!=null) parts.push(`30일 <b>${_polRV.pr30>0?'+':''}${(_polRV.pr30*100).toFixed(2)}%p</b>${_polRV.cr30!=null?`(원래 ${_polRV.cr30>0?'+':''}${(_polRV.cr30*100).toFixed(1)}%)`:''}`);
          return parts.length?`<div class="note" style="margin-top:3px">스크리너 필터·컬럼 표시값(진행분기·다음분기 평균) = ${parts.join(' · ')} — 위 표의 진행분기·다음분기 두 행을 평균한 수치와 같습니다</div>`:''; })()+
        `<div style="margin-top:6px;display:flex;gap:6px;flex-wrap:wrap">${panels}</div>
          <div class="note" style="margin-top:2px">${leg}</div></div>`;
    }
    /* ③ 목표주가 — 현재 유효 평균 + 스냅샷 리비전 (누적 중) */
    let t2='';
    { const rw=(POOL.us||[]).find(z=>z.c===c)||{};
      const cur=(_CD&&_CD.c)?[..._CD.c].reverse().find(v=>v!=null):null;
      const gp=(rw.tp&&cur)?((rw.tp/cur-1)*100):null;
      const sn=(J.snap||[]).filter(z=>z.tp!=null);
      let ln=`<b>$${rw.tp?(+rw.tp).toLocaleString():'—'}</b>`+(gp!=null?` <span class="${gp>0?'up':'dn'}">상승여력 ${gp>0?'+':''}${gp.toFixed(1)}%</span>`:'');
      if(rw.tprv!=null) ln+=` · 30일 리비전 ${P(rw.tprv)}`;
      if(rw.tprv90!=null) ln+=` · 90일 ${P(rw.tprv90)}`;
      t2=`<div style="margin-top:10px"><b style="font-size:12px">목표주가</b> <span class="note">(미국은 '현재 유효한 목표가'의 평균 — 기간 개념 없음 · 커버리지 중단 시에만 제외 · 오래된 목표가가 섞일 수 있음)</span>
        <div style="font-size:12.5px;margin-top:3px">${ln}</div>`+
        (sn.length?`<div class="note">일별 스냅샷 ${sn.length}일치 적립 중(08-09 시작) — 30일 리비전은 9/8·90일은 11/7부터 필터에도 반영</div>`:
                   '<div class="note">일별 스냅샷 적립 시작(매일 08:00) — 30일 리비전 9/8·90일 11/7부터</div>')+'</div>';
    }
    /* (2026-08-09) 분기별 발표·공시 자료 링크(1년) — 전부 SEC 공식 접수 인덱스.
       8-K 인덱스에는 Earnings Release + 프레젠테이션·보충자료가 Exhibit 99.x 로 함께 있고,
       10-Q(분기)/10-K(4분기·연간)는 정기보고서 원문. 콘퍼런스콜 음성·원고는 SEC 에
       접수되지 않아 회사 IR 페이지에서만 제공(구조화 무료 소스 없음 — 정직하게 미지원). */
    let t5='';
    try{
      const ED=await (await fetch('/api/earn_dates/us/'+encodeURIComponent(c))).json();
      const cik=ED.cik;
      if(cik&&(ED.items||[]).length){
        const idxU=a=>`https://www.sec.gov/Archives/edgar/data/${parseInt(cik,10)}/${String(a).replace(/-/g,'')}/${a}-index.htm`;
        const dl=d=>`${d.slice(0,4)}.${d.slice(4,6)}.${d.slice(6,8)}`;
        const ers=(ED.items||[]).filter(z=>z.f!=='6-K').slice(-5).reverse();
        const tq=ED.tq||[];
        t5=`<div style="margin-top:10px"><b style="font-size:12px">분기별 발표·공시 자료 (1년)</b> <span class="note">— SEC 공식 접수분</span>
          <table style="width:100%;font-size:11.5px;border-collapse:collapse;margin-top:3px">
          <tr style="border-bottom:1px solid var(--line)"><th style="text-align:left;padding:3px 4px">발표일</th>
          <th style="text-align:left">실적발표 자료<span class="note"> (Earnings Release·프레젠테이션·보충자료)</span></th>
          <th style="text-align:left">정기보고서</th><th style="text-align:left">Earnings Call</th></tr>`+
          ers.map(er=>{
            /* 발표 후 0~50일 내 접수된 첫 10-Q/10-K 를 그 분기 보고서로 매칭 */
            const D8=s=>new Date(`${s.slice(0,4)}-${s.slice(4,6)}-${s.slice(6,8)}`);
            const m10=tq.find(z=>z.d>=er.d && (D8(z.d)-D8(er.d))/864e5<=50);
            return `<tr style="border-bottom:1px solid #f2f4f7"><td style="padding:3px 4px"><b>${dl(er.d)}</b></td>
              <td><a href="${idxU(er.acc)}" target="_blank" rel="noopener">📄 8-K 접수 인덱스↗</a></td>
              <td>${m10?`<a href="${idxU(m10.acc)}" target="_blank" rel="noopener">${m10.f==='10-K'?'📕 10-K (4분기·연간)':'📘 10-Q (분기)'}↗</a> <span class="note">${dl(m10.d)}</span>`:'<span class="note">제출 전 또는 45일 초과</span>'}</td>
              <td>${(()=>{ /* (2026-08-10) 어닝콜 — 그 발표에 해당하는 분기의 트랜스크립트(Zacks→Aiera) */
                const am=+er.d.slice(0,4)*12 + +er.d.slice(4,6);
                const hit=(q||[]).filter(z=>{const zm=+z.p.slice(0,4)*12 + +z.p.slice(5,7); return am-zm>=0 && am-zm<=3 && z.call;})
                                 .sort((x,y)=>(+y.p.slice(0,4)*12 + +y.p.slice(5,7))-(+x.p.slice(0,4)*12 + +x.p.slice(5,7)))[0];
                return hit?`<a href="${hit.call}" target="_blank" rel="noopener" title="${E(hit.callT||'')}">🎧 콜 원문·오디오↗</a>`:'<span class="note">링크 없음</span>'; })()}</td></tr>`; }).join('')+
          `</table><div class="note" style="margin-top:2px">8-K 인덱스의 Exhibit 99.1 = 보도자료 · 99.2 = 프레젠테이션(첨부한 회사만) · <b>Earnings Call</b> = 콜 원문·오디오(Zacks 제공 Aiera 링크) — 요약문을 주는 무료 소스가 없어 원문으로 연결(읽는 순서 6번 Q&amp;A)</div></div>`;
      }
    }catch(e){}
    /* (2026-08-10) 읽는 순서 가이드 — 위 표들이 왜 이 순서로 놓여 있는지, 발표를 어떤
       순서로 확인해야 하는지 (사용자 제공 체크리스트). 화면 맨 아래에 접이식으로 둔다. */
    const GUIDE=`<details style="margin-top:8px"><summary style="cursor:pointer;font-size:12px"><b>📖 실적 발표를 읽는 순서</b> <span class="note">(클릭하여 펼치기)</span></summary>
      <ol style="margin:6px 0 0 18px;padding:0;font-size:11.5px;line-height:1.75;color:#475467">
        <li><b>EPS Actual vs. Consensus</b> — 주당순이익이 예상치를 넘었는지 확인합니다.</li>
        <li><b>Revenue Actual vs. Consensus</b> — 매출이 예상치를 넘었는지 확인합니다.</li>
        <li><b>Gross Margin 및 Operating Margin</b> — 수익성이 개선됐는지 봅니다.</li>
        <li><b>Guidance</b> — 다음 분기와 연간 전망을 확인합니다.</li>
        <li><b>FCF 및 CapEx</b> — 이익이 실제 현금으로 연결되는지 확인합니다.</li>
        <li><b>Earnings Call Q&amp;A</b> — 경영진이 수요·경쟁·비용·재고·AI 투자 등을 어떻게 설명하는지 듣습니다.</li>
      </ol></details>`;
    el.innerHTML=`<div class="box" style="padding:10px 12px"><b style="font-size:12.5px">📊 실적·전망</b> <span class="note">(${E(J.src||'')} · ${E(J.unit||'')})</span>
      <div style="overflow:auto;margin-top:6px">${t1}</div>${t3}${t2}${t5}${GUIDE}</div>`;
  }
  /* ── (2026-08-09) 매출 구성·제품 정보 — 우측 열 하단. 소스 3종을 출처와 함께 비교.
     ① DART 정기보고서(사업/반기/분기) 「매출실적」 표 원문 그대로 — 기업마다 상세도가 다르다
        (실측: SK하이닉스는 'DRAM, NAND Flash 등' 단일 항목 + 부문별 기재 생략)
     ② WISEreport(FnGuide 계열) 주요제품 매출구성% 요약
     ③ 회사 IR 실적발표 — 분기 제품·응용처 비중의 유일한 정본(PDF·링크 제공) */
  /* (2026-08-09) 최근연혁 — 기업개요(sd_ov) 아래에 붙인다. 기업개요는 /api/overview 로
     따로 오므로, 어느 쪽이 먼저 도착하든 한 번만 붙도록 양쪽에서 _ovHist() 를 부른다. */
  let _HISTC=null, _HIST=null;
  function _ovHist(){
    const ov=$('sd_ov'); if(!ov||!_HIST||!_HIST.length) return;
    if(ov.dataset.c!==_HISTC || ov.querySelector('.ovh')) return;
    const d=document.createElement('div'); d.className='ovh';
    d.innerHTML=`<div class="sgt" style="margin-top:6px">최근연혁</div>
      <table style="width:100%;font-size:11.5px;border-collapse:collapse">`+
      _HIST.map(z=>`<tr style="border-bottom:1px solid #f2f4f7"><td style="padding:2px 4px;white-space:nowrap;color:var(--tx2)">${E(z.d)}</td><td style="padding:2px 4px">${E(z.t)}</td></tr>`).join('')+'</table>';
    ov.appendChild(d); ov.style.display='';
  }
  /* (2026-08-09) US 매출 구성 — KR 패널과 같은 자리·같은 느낌.
     소스는 실적표와 동일한 stockanalysis 한 곳(회사별 사업부/제품/지역 *_revenue 블록).
     실측: AAPL iPhone/Mac/iPad/웨어러블/서비스 · MSFT 3사업부 · ABNB 지역별. */
  async function loadUsSeg(c){
    const el=$('sd_seg'); if(!el) return;
    el.style.display=''; el.innerHTML='<span class="note">매출 구성 로드 중…</span>';
    let J=null;
    try{ J=await (await fetch('/api/us_fin/'+encodeURIComponent(c))).json(); }catch(e){}
    if(dcode!==c) return;
    const SEG=(J&&J.seg)||[];
    if(!SEG.length){ el.innerHTML='<span class="note">세그먼트 매출 미공시 종목 (단일 사업 또는 소스 미제공)</span>'; return; }
    const F=v=>v==null?'—':Math.round(v).toLocaleString();
    const srcU=`https://stockanalysis.com/stocks/${encodeURIComponent(c.toLowerCase())}/financials/?p=quarterly`;
    let hh=`<b style="font-size:12.5px">📦 매출 구성·제품 정보</b> <span class="note">(백만$ · 분기)</span>
      <a href="${srcU}" target="_blank" rel="noopener" style="font-size:11px">출처↗</a>`;
    SEG.forEach((sg,si)=>{
      /* 요약: 최신 분기 비중% — KR 의 FnGuide 요약과 같은 역할 */
      const r0=(sg.rows||[]).find(r=>(r.v||[]).some(v=>v!=null));
      if(r0){ const tot=r0.v.reduce((s,v)=>s+(v||0),0)||1;
        hh+=`<div style="font-size:12px;margin-top:${si?8:6}px"><b>${E(r0.p)}</b> `+
          sg.cols.map((cn,i)=>({cn,p:(r0.v[i]||0)/tot*100})).sort((a,b)=>b.p-a.p)
            .map(z=>`${E(z.cn)} <b>${z.p.toFixed(1)}%</b>`).join(' · ')+'</div>'; }
      hh+=`<div style="overflow:auto"><table style="width:100%;font-size:11px;border-collapse:collapse;margin-top:3px">
        <tr style="border-bottom:1px solid var(--line)"><th style="text-align:left;padding:2px 4px">분기</th>`+
        sg.cols.map(cn=>`<th style="text-align:right;padding:2px 4px">${E(cn)}</th>`).join('')+'</tr>'+
        (sg.rows||[]).map(r=>`<tr style="border-bottom:1px solid #f4f6f8"><td style="padding:2px 4px"><b>${E(r.p)}</b></td>`+
          r.v.map(v=>`<td style="text-align:right;padding:2px 4px">${F(v)}</td>`).join('')+'</tr>').join('')+'</table></div>'; });
    hh+=`<div class="note" style="margin-top:4px">회사가 10-Q/K 에 신고한 세그먼트 구분 그대로(사업부·제품·지역 등 회사마다 다름) · 12월 분기는 연간 신고에서 분리돼 지연될 수 있음</div>`;
    el.innerHTML=hh;
  }
  async function loadKrSeg(c){
    const el=$('sd_seg'); if(!el) return;
    _HISTC=c; _HIST=null;
    if(mkt!=='kr'){ if(mkt==='us') return loadUsSeg(c); el.style.display='none'; el.innerHTML=''; return; }
    el.style.display=''; el.innerHTML='<span class="note">매출 구성 로드 중… (첫 조회는 DART 보고서 3건 파싱 — 수십 초)</span>';
    let J=null;
    try{ J=await (await fetch('/api/kr_seg/'+encodeURIComponent(c))).json(); }catch(e){}
    if(dcode!==c) return;
    if(J&&(J.hist||[]).length){ _HIST=J.hist; _ovHist(); }   // 최근연혁 → 기업개요 아래
    if(!J||(!((J.reports||[]).length)&&!J.wise)){ el.innerHTML='<span class="note">매출 구성 정보 없음</span>'; return; }
    let hh='<b style="font-size:12.5px">📦 매출 구성·제품 정보</b> <span class="note">(소스 비교 · 24h 캐시 자동 갱신)</span>';
    /* (2026-08-09) 요약(구성비%)을 맨 위로 — 한눈 요약 먼저, 상세 표는 아래 */
    if(J.wise) hh+=`<div style="margin-top:6px"><b style="font-size:12px">FnGuide·WISEreport 요약</b>
      <span class="note">매출구성 ${E(J.wise.asof||'')}</span> <a href="${E(J.wise.url)}" target="_blank" rel="noopener" style="font-size:11px">출처↗</a>
      <div style="font-size:12px;margin-top:2px">`+J.wise.items.map(z=>`${E(z.n)} <b>${E(z.p)}%</b>`).join(' · ')+'</div></div>';
    (J.reports||[]).forEach(r=>{
      hh+=`<div style="margin-top:8px"><b style="font-size:12px">${E(r.nm)}</b> <span class="note">${E(r.dt)}</span>
        <a href="https://dart.fss.or.kr/dsaf001/main.do?rcpNo=${E(r.rno)}" target="_blank" rel="noopener" style="font-size:11px">원본↗</a>`;
      if((r.rows||[]).length){
        hh+=`<div style="overflow:auto"><table style="width:100%;font-size:11px;border-collapse:collapse;margin-top:3px">`+
          r.rows.map((cs,i)=>`<tr style="border-bottom:1px solid #f2f4f7;${i===0?'background:#f7f9fb;font-weight:600':''}">`+
            cs.map(cell=>`<td style="padding:2px 4px;white-space:nowrap;text-align:${/^[\d,.\-]+$/.test(cell)?'right':'left'}">${E(cell)}</td>`).join('')+'</tr>').join('')+
          '</table></div>'+(r.unit?`<div class="note">단위: ${E(r.unit)}</div>`:'');
      } else hh+='<div class="note">매출실적 표 없음(보고서 양식 상이)</div>';
      if(r.seg_skip) hh+=`<div class="note" style="color:#b7791f">※ 부문별 재무정보 기재 생략(지배적 단일 사업부문) — 제품별 분리는 회사 IR 자료에만 있음</div>`;
      hh+='</div>'; });
    if(J.ir) hh+=`<div style="margin-top:8px;border-top:1px solid var(--line);padding-top:6px"><b style="font-size:12px">IR 실적발표 자료</b>
      <a href="${E(J.ir)}" target="_blank" rel="noopener" style="font-size:11px">바로가기↗</a>
      <div class="note">분기별 제품(DRAM/NAND 등)·응용처별 비중은 <b>IR 자료가 유일한 정본</b> — PDF 형태라 표 자동 표시는 미지원, 원문 링크로 확인</div></div>`;
    el.innerHTML=hh;
  }
  async function loadEarn(c){
    /* (2026-08-09) 미국·한국 모두 과거 1년치 발표일을 받는다.
         미국 = SEC 8-K Item 2.02 접수일
         한국 = DART 영업(잠정)실적 공정공시 접수일
       둘 다 '실적이 세상에 처음 나온 날'이라 성격이 같다. */
    _EDATES=null;
    try{ const J=await (await fetch(`/api/earn_dates/${mkt}/`+encodeURIComponent(c))).json();
      if(dcode!==c) return;
      _EDATES=(J.items||[]); _ECIK=J.cik||null; _paint();
    }catch(e){ _EDATES=null; }
  }
  async function loadDisc(c){
    if(mkt!=='kr'){ _DISC=null; return; }
    try{ const J=await (await fetch('/api/disclosure/kr/'+encodeURIComponent(c))).json();
      if(dcode!==c) return;
      _DISC=(J.items||[]); _DSEL=null; _paint();
    }catch(e){ _DISC=null; }
  }
  function _paint(){ const D=_CD; if(!D) return;
    // 데이터 정리 (null 보간)
    const full=D.c.slice();
    for(let i=0;i<full.length;i++) if(full[i]==null) full[i]=full[i-1]??null;
    const TOT=full.length;
    _CZ=Math.max(30, Math.min(_CZ, TOT));            // 최소 30봉
    _COFF=Math.max(0, Math.min(_COFF, TOT-_CZ));     // 과거로 더 못 감 / 미래로 못 감
    const N=_CZ, off=TOT-N-_COFF;
    _CN=N;
    const HI=(_CHI!=null&&_CHI>=0&&_CHI<N)?_CHI:N-1;   // 범례 기준 봉(호버 없으면 최신)
    //  ※ drawMain 안에는 가격 표시범위용 lo/hi 가 따로 있어 이름을 HI 로 구분한다.
    const sl=a=>(a||[]).slice(off), pad=(a,d)=>a.map((x,i)=>x==null?(d[i]):x);
    const c=sl(full), o=pad(sl(D.o),c), hh=pad(sl(D.h),c), ll=pad(sl(D.l),c), v=sl(D.v).map(x=>x||0), t=sl(D.t);
    _CT=t; _CHD=String(t[HI]||'').replace(/-/g,'');   // 수급 패널과 '날짜'로 동기화(t 선언 이후여야 함)
    /* (2026-08-04) 분봉 등락 기준 = '전일 종가' — 직전 봉 대비가 아니라 일봉과 같은 당일 등락률.
       전일 종가 = 직전 거래일의 정규장 마감(KR 15:30 · US 16:00) 이전 마지막 봉 종가
       (시간외포함 모드에서 전일 애프터 체결을 기준 삼으면 일봉 % 와 어긋나므로 정규장 마감 기준). */
    const _pdc=fi=>{ if(!_isMin()) return null;
      const T=D.t||[], d=String(T[fi]||'').slice(0,8); if(d.length<8) return null;
      const cut = mkt==='kr' ? '1531' : '1601';
      let j=fi-1;
      while(j>=0 && String(T[j]||'').slice(0,8)===d) j--;
      if(j<0) return null;
      const pd=String(T[j]).slice(0,8), any=full[j];
      for(let k=j;k>=0;k--){ const z=String(T[k]||''); if(z.slice(0,8)!==pd) break;
        if(z.slice(8,12)<cut) return full[k]; }        // 정규장 마지막 봉
      return any; };                                   // 정규장 봉이 없으면 그 날 마지막 봉
    /* (2026-07-21) x축 라벨을 공통 함수로 — 메인 차트와 보조 패널(OBV 등)이 똑같은 라벨·위치를 쓴다.
       예전엔 OBV 패널이 분봉에서도 '년.월'(26.07)만 찍어 다 같아 보였다(정렬은 맞는데 라벨만 무의미).
       모든 패널이 P.l=6·P.r=52·N 동일이라 X(i) 픽셀이 일치 → 같은 함수를 쓰면 라벨도 세로로 딱 맞는다. */
    function _xlabels(cx2, Xf, Hc){
      cx2.fillStyle='#98a2ad'; cx2.font='10px sans-serif';
      if(_isMin()){
        /* 날짜 경계 x좌표 선계산 — 경계 ±44px 안의 시각 라벨은 생략(날짜와 겹침 방지) */
        const bx=[]; {let ld='';
          for(let i=0;i<N;i++){ const z=String(t[i]||''); if(z.length<12) continue;
            const d=z.slice(0,8); if(d!==ld){ if(ld) bx.push(Xf(i)); ld=d; } }}
        let lastD='', px=-99, firstBar=true;
        for(let i=0;i<N;i++){ const z=String(t[i]||''); if(z.length<12) continue;
          const d=z.slice(0,8), hm=z.slice(8,10)+':'+z.slice(10,12), xx=Xf(i);
          if(d!==lastD){ const isFirst=firstBar; firstBar=false; lastD=d;
            /* (2026-08-04) 날짜 경계 — 하루 시작 지점에 세로 점선(모든 패널 공통) + 아래 날짜.
               화면 맨 왼쪽에서 시작하는 날은 점선 생략(경계가 아니라 잘린 것). */
            if(!isFirst){ cx2.save(); cx2.strokeStyle='#c5beb2'; cx2.setLineDash([3,3]);
              cx2.beginPath(); cx2.moveTo(xx-0.5,2); cx2.lineTo(xx-0.5,Hc-13); cx2.stroke(); cx2.restore(); }
            /* 날짜 라벨은 항상 표시(시각 라벨보다 우선) — 시각 라벨의 간격 가드에 밀려 빠지지 않게 */
            px=xx; cx2.save(); cx2.fillStyle='#5b6470'; cx2.font='bold 10px sans-serif';
            cx2.fillText((+d.slice(4,6))+'/'+(+d.slice(6,8)), xx-9, Hc-4); cx2.restore();
            continue; }
          if(hm.endsWith(':00') && xx-px>=52 && bx.every(b=>Math.abs(xx-b)>=44)){ px=xx; cx2.fillText(hm, xx-12, Hc-4); } }
      } else {
        let lastM='',lastY='',px=-99;
        for(let i=0;i<N;i++){ const d=String(t[i]||'').replace(/-/g,''); if(d.length<6) continue;
          const yy=d.slice(0,4), mm=d.slice(4,6);
          if(mm===lastM) continue; const first=(lastM!=='');
          lastM=mm; if(!first){ lastY=yy; continue; }
          const lab=(yy!==lastY)?(lastY=yy,yy):(+mm)+'월';
          const xx=Xf(i); if(xx-px<42) continue; px=xx;
          cx2.fillText(lab, xx-10, Hc-4); } }
    }
    /* 일봉만 시장별 관례 세트를 쓴다. 분봉·주·월봉은 그 관례가 적용되는 단위가 아니므로
       네이버와 동일하게 5/20/60/120 을 쓴다(네이버도 분봉에서 같은 세트). */
    const _MASET = (_TF==='d') ? (MASET[mkt]||MASET.us)
                               : [[5,'#16a085'],[20,'#f39c12'],[60,'#27ae60'],[120,'#8e44ad']];
    const MAS=_MASET.map(([per,col])=>({per,col,a:sl(_sma(full,per))}));
    const bm=_sma(full,20), bsd=full.map((x,i)=>{ if(i<19||bm[i]==null) return null; let s=0; for(let j=i-19;j<=i;j++) s+=(full[j]-bm[i])**2; return Math.sqrt(s/20); });
    const bU=sl(bm.map((m,i)=>m==null?null:m+2*bsd[i])), bL=sl(bm.map((m,i)=>m==null?null:m-2*bsd[i]));
    const rsi=sl(_rsiArr(full,14));
    const e12=_ema(full,12), e26=_ema(full,26);
    const macdF=full.map((_,i)=>(e12[i]!=null&&e26[i]!=null)?e12[i]-e26[i]:null);
    const sigF=_ema(macdF,9);
    const macd=sl(macdF), sig=sl(sigF), hist=macd.map((x,i)=>(x!=null&&sig[i]!=null)?x-sig[i]:null);
    const UP='#d33', DN='#1f6feb';
    const last=c[c.length-1];
    let prev=c[c.length-2]??last;
    if(_isMin()){ const r=_pdc(off+c.length-1); if(r!=null) prev=r; }   // 분봉: 전일 종가 대비
    const chg=prev?(last/prev-1)*100:0;
    $('sd_last').innerHTML=`${mkt==='kr'?Math.round(last).toLocaleString()+'원':'$'+(+last).toFixed(2)} <span class="${chg>=0?'up':'dn'}">${chg>=0?'+':''}${chg.toFixed(2)}%</span>`;
    // ① 메인(캔들+MA+BB+52주고점) — 일반·로그 두 판 (useLog=가격을 log 공간에 매핑, 상승률 기준 균등)
    const drawMain=(id,useLog)=>{
     const [x,W,H]=_cvs(id); const P={l:6,r:52,t:32,b:16};   // t=32 : 상단 범례 2줄 자리
     const T=useLog?Math.log:(p=>p), IV=useLog?Math.exp:(p=>p);
     const lo=T(Math.min(...ll,...bL.filter(y=>y!=null))), hi=T(Math.max(...hh,...bU.filter(y=>y!=null)));
     const X=i=>P.l+(W-P.l-P.r)*(i+0.5)/N, Y=p=>P.t+(H-P.t-P.b)*(1-(T(p)-lo)/((hi-lo)||1));
     // BB 밴드
     x.beginPath(); let st=false;
     for(let i=0;i<N;i++){ if(bU[i]==null)continue; st?x.lineTo(X(i),Y(bU[i])):(x.moveTo(X(i),Y(bU[i])),st=true); }
     for(let i=N-1;i>=0;i--){ if(bL[i]==null)continue; x.lineTo(X(i),Y(bL[i])); }
     x.closePath(); x.fillStyle='rgba(130,150,170,.10)'; x.fill();
     /* 매물분석도(가격대별 거래량) — 일봉의 고가~저가 구간에 그날 거래량을 균등 배분해 근사한다.
        (일봉만으로는 체결가별 분포를 알 수 없으므로 표준적인 근사법)
        위쪽에 두꺼운 막대 = 그 가격대에 물린 물량이 많다 = 반등 시 저항.
        가장 두꺼운 구간(POC)은 주황으로 강조. 캔들보다 아래 레이어라 시야를 가리지 않는다. */
     {const VPB=30, vLo=Math.min(...ll), vHi=Math.max(...hh), rng=(vHi-vLo)||1;
      const bins=new Array(VPB).fill(0);
      for(let i=0;i<N;i++){
        const a=Math.min(ll[i],hh[i]), b=Math.max(ll[i],hh[i]);
        const k0=Math.max(0,Math.min(VPB-1,Math.floor((a-vLo)/rng*VPB)));
        const k1=Math.max(0,Math.min(VPB-1,Math.floor((b-vLo)/rng*VPB)));
        const span=k1-k0+1;
        for(let k=k0;k<=k1;k++) bins[k]+=(v[i]||0)/span; }
      const bmx=Math.max(...bins)||1, poc=bins.indexOf(bmx);
      const vpW=(W-P.l-P.r)*0.20;
      for(let k=0;k<VPB;k++){
        const y0=Y(vLo+rng*(k+1)/VPB), y1=Y(vLo+rng*k/VPB);
        const bh=Math.max(1,y1-y0-1), bwd=vpW*bins[k]/bmx;
        x.fillStyle=(k===poc)?'rgba(243,156,18,.42)':'rgba(120,140,165,.18)';
        x.fillRect(W-P.r-bwd, y0, bwd, bh); }
      // POC 가격 라벨
      x.font='9px sans-serif'; x.fillStyle='#c07a10';
      x.fillText('매물대 최대 '+_pf(vLo+rng*(poc+0.5)/VPB), W-P.r-vpW, Y(vLo+rng*(poc+0.5)/VPB)-3); }
     // y 그리드 — 네이버처럼 촘촘하게(7눈금). lo/hi 는 위에서 잡은 표시범위 변수라 이름 충돌 없음.
     x.font='10px sans-serif'; x.fillStyle='#98a2ad'; x.strokeStyle='#eceff3';
     const GT=6;
     for(let g=0;g<=GT;g++){ const p=IV(lo+(hi-lo)*g/GT), y=Y(p);
       x.beginPath(); x.moveTo(P.l,y); x.lineTo(W-P.r,y); x.stroke();
       x.fillText(_pf(p), W-P.r+4, y+3); }
     // 52주 최고 점선
     const mx=Math.max(...hh); x.setLineDash([4,3]); x.strokeStyle='#b7b0a6';
     x.beginPath(); x.moveTo(P.l,Y(mx)); x.lineTo(W-P.r,Y(mx)); x.stroke(); x.setLineDash([]);
     // 캔들
     const bw=Math.max(1,(W-P.l-P.r)/N*0.6);
     for(let i=0;i<N;i++){ const up=c[i]>=o[i]; x.strokeStyle=x.fillStyle=up?UP:DN;
       x.beginPath(); x.moveTo(X(i),Y(hh[i])); x.lineTo(X(i),Y(ll[i])); x.stroke();
       const y1=Y(Math.max(o[i],c[i])), y2=Y(Math.min(o[i],c[i]));
       x.fillRect(X(i)-bw/2, y1, bw, Math.max(1,y2-y1)); }
     // MA 라인
     const line=(a,col)=>{ x.strokeStyle=col; x.lineWidth=1.4; x.beginPath(); let s=false;
       for(let i=0;i<N;i++){ if(a[i]==null)continue; s?x.lineTo(X(i),Y(a[i])):(x.moveTo(X(i),Y(a[i])),s=true); } x.stroke(); x.lineWidth=1; };
     MAS.forEach(m=>line(m.a,m.col));
     // x축 — 분봉이면 날짜경계·정시, 그 외 월/연 (보조 패널과 동일 함수로 정렬)
     _xlabels(x, X, H);
     // 최고·최저 지점 라벨 (현재가 대비 등락률까지 — 네이버 '최고 83,200 (-45.67%)' 형식)
     {const iMax=hh.indexOf(Math.max(...hh)), iMin=ll.indexOf(Math.min(...ll));
      const cur=c[N-1];
      const mark=(i,val,isHi)=>{ const xx=X(i), yy=Y(val);
        const pct=cur&&val?((cur/val-1)*100):0;
        const txt=`${isHi?'▼최고':'▲최저'} ${_pf(val)} (${pct>=0?'+':''}${pct.toFixed(2)}%)`;
        x.font='10px sans-serif'; const w=x.measureText(txt).width;
        let tx=Math.min(Math.max(xx-w/2,P.l), W-P.r-w), ty=isHi?yy-6:yy+13;
        x.fillStyle='rgba(255,255,255,.82)'; x.fillRect(tx-2,ty-9,w+4,12);
        x.fillStyle='#5b6470'; x.fillText(txt,tx,ty); };
      mark(iMax,hh[iMax],true); mark(iMin,ll[iMin],false); }
     // 우측 축에 현재가 배지
     {const cur=c[N-1], yy=Y(cur), lab=_pf(cur);
      x.font='bold 10px sans-serif'; const w=x.measureText(lab).width;
      x.fillStyle='#2c3542'; x.fillRect(W-P.r+1, yy-7, w+7, 14);
      x.fillStyle='#fff'; x.fillText(lab, W-P.r+4, yy+3); }
     /* (2026-08-09) 실적발표 마커 — 공시 마커와 같은 방식(캔들 위 배지 + 클릭 시 요약 상자).
        🟩 '실' = 실제 발표를 감지한 날(edl · DART 잠정공시 / SEC 8-K Item 2.02)
        ⬜ '예' = IR 예정일(ed · Yahoo·네이버 IR) — 아직 발표 전이거나 감지 못한 경우
        클릭하면 캘린더 팝업과 같은 한 줄 요약(실적 → 전망 → 주가)이 뜬다. */
     _EHIT=[]; _PLK=[];        // _PLK: 팝업 안 클릭 가능한 링크(원본 열기) — 매 프레임 재계산
     let _epop=null;           // (2026-08-09) 실적팝업을 공시 마커 이후에 그리기 위한 지연 실행
     {const rw=(POOL[mkt]||[]).find(z=>z.c===dcode)||{};
      const idx2={}; for(let i=0;i<N;i++) idx2[String(t[i]||'').replace(/-/g,'').slice(0,8)]=i;
      const ed8=String(rw.ed||'').replace(/-/g,'').slice(0,8);
      const marks=[];
      /* (2026-08-09) 미국은 SEC 8-K(Item 2.02) 접수일로 **과거 1년치**를 전부 찍는다.
         한 종목의 급등락이 실적 때문인지 아닌지를 1년 흐름에서 한눈에 보기 위함이다.
         한국은 DART 잠정공시 최근 45일치(edl)만 있어 1건이다. */
      (_EDATES||[]).forEach(e=>{ if(idx2[e.d]!=null) marks.push({d:e.d, i:idx2[e.d], t:'실', col:'#1f9d55', acc:e.acc, rno:e.rno}); });
      if(rw.edl && idx2[rw.edl]!=null && !marks.some(m=>m.d===rw.edl))
        marks.push({d:rw.edl, i:idx2[rw.edl], t:'실', col:'#1f9d55'});
      if(ed8 && idx2[ed8]!=null && !marks.some(m=>m.d===ed8))
        marks.push({d:ed8, i:idx2[ed8], t:'예', col:'#7a869a'});
      /* 각 발표일의 주가 반응은 **차트에 이미 있는 종가로 직접 계산**한다.
         풀에는 최근 1건만 들어 있어서, 과거 발표분은 여기서 구해야 한다. */
      const reactAt=(i)=>{ if(i<1) return {};
        const base=c[i-1]; if(!base) return {};
        const g=(k)=>(i+k<N&&c[i+k]!=null)?((c[i+k]/base-1)*100):null;
        return {r1:g(0), r5:g(4), r20:g(19)}; };
      marks.forEach(m=>{ const mx=X(m.i), sel=(_ESEL===m.d);
        // 세로 가이드선 — 어느 봉이 발표일인지 한눈에
        x.save(); x.setLineDash(m.t==='예'?[3,3]:[]); x.strokeStyle=m.col; x.globalAlpha=sel?.55:.3;
        x.lineWidth=sel?2:1.2; x.beginPath(); x.moveTo(mx,P.t); x.lineTo(mx,H-P.b); x.stroke(); x.restore();
        const my=Math.max(Y(hh[m.i])-26, P.t+8);
        x.beginPath(); x.arc(mx, my, sel?8:6.5, 0, Math.PI*2);
        x.fillStyle=sel?m.col:(m.col+'d9'); x.fill();
        x.strokeStyle='#fff'; x.lineWidth=1.2; x.stroke(); x.lineWidth=1;
        x.fillStyle='#fff'; x.font='bold 9px sans-serif'; x.textAlign='center';
        x.fillText(m.t, mx, my+3); x.textAlign='left';
        _EHIT.push({d:m.d, x:mx, y:my, r:9}); });

      // 선택된 마커 → 요약 상자 (캘린더 팝업과 동일한 '실적 → 전망 → 주가' 순서)
      // ※ 팝업은 공시 마커(빨간 배지)까지 다 그린 뒤 마지막에 그린다 — 겹치면 팝업이 위
      const sm=marks.find(m=>m.d===_ESEL);
      if(sm){ _epop=()=>{
        const pc=(v,suf)=>v==null?null:`${v>0?'+':''}${(+v).toFixed(1)}${suf||'%'}`;
        const rows=[];
        if(sm.t==='예'){ rows.push(['다음 실적발표 예정일','IR 공시 기준 — 확정 아님']); }
        else{
          // 서프·전망은 '최근 발표분'에만 값이 있다(풀에 1건). 과거 분기는 주가 반응만 보여준다.
          const latest = (sm.d===rw.edl);
          if(latest && mkt==='kr'){
            /* (2026-08-09) KR 상세 — 컨센 대비 / YoY / QoQ(전환) / 마진을 전부 한 팝업에 */
            const l1=[]; if(rw.spr!=null) l1.push('영업익 컨센比 '+pc(rw.spr));
            if(rw.sspr!=null) l1.push('매출 컨센比 '+pc(rw.sspr));
            rows.push(['컨센', l1.length?l1.join('   '):'컨센서스 미커버']);
            const l2=[]; if(rw.syoy!=null) l2.push('매출 '+pc(rw.syoy));
            if(rw.oyoy!=null) l2.push('영업익 '+pc(rw.oyoy));
            if(rw.nyoy!=null) l2.push('순익 '+pc(rw.nyoy));
            if(l2.length) rows.push(['YoY', l2.join('   ')]);
            const l3=[]; if(rw.sqoq!=null) l3.push('매출 '+pc(rw.sqoq));
            if(rw.oqoq!=null) l3.push('영업익 '+pc(rw.oqoq));
            if(rw.nqoq!=null) l3.push('순익 '+pc(rw.nqoq));
            if(rw.oqt) l3.push('⚡'+rw.oqt);
            if(l3.length) rows.push(['QoQ', l3.join('   ')]);
            if(rw.opmn!=null) rows.push(['마진', `영업이익률 ${rw.opmn}%`+(rw.opmy!=null?`  (YoY ${rw.opmy>0?'+':''}${rw.opmy}%p)`:'')]);
            const cv = rw.tprv!=null?pc(rw.tprv):null;
            if(cv) rows.push(['전망', `목표가 30일 ${cv}`+(rw.tprv90!=null?`   90일 ${pc(rw.tprv90)}`:'')]);
          }
          /* (2026-08-09) US — 분기 실적 YoY/QoQ (컨센과 무관한 실적치라 과거 마커 전부 계산).
             발표일로부터 1~4개월 앞선 분기말을 해당 분기로 매칭한다. */
          if(mkt==='us'&&_USFIN&&(_USFIN.q||[]).length){
            const qq=_USFIN.q, am=+sm.d.slice(0,4)*12 + +sm.d.slice(4,6);
            let qi=-1;
            for(let i2=qq.length-1;i2>=0;i2--){ const qm2=+qq[i2].p.slice(0,4)*12 + +qq[i2].p.slice(5,7);
              const df=am-qm2; if(df>=1&&df<=4){ qi=i2; break; } }
            if(qi>=0){
              /* (2026-08-09) 미국식 보는 순서 — 매출 → EPS → 서프 판정 → 이익률 */
              const pctu=(a,b)=>(a!=null&&b!=null&&Math.abs(b)>0.005)?((a-b)/Math.abs(b)*100):null;
              /* ±1개월 허용 매칭 — 4-4-5 회계(AAPL 등)는 분기말이 다음 달로 밀린다 */
              const _mn=p=>+p.slice(0,4)*12 + +p.slice(5,7);
              const _bs=(mm)=>{ const t=_mn(qq[qi].p)-mm; let best=null,bd=99;
                for(const z of qq){ const d=Math.abs(_mn(z.p)-t); if(d<bd){bd=d;best=z;} }
                return bd<=1?best:null; };
              const gy=k=>{ const b=_bs(12); return b?pctu(qq[qi][k],b[k]):null; };
              const gq=k=>{ const b=_bs(3);  return b?pctu(qq[qi][k],b[k]):null; };
              const tn=k=>{ const b=_bs(3), pv=b?b[k]:null, cv=qq[qi][k];
                if(pv==null||cv==null) return '';
                if(pv<0&&cv>0) return ' ⚡흑전'; if(pv>0&&cv<0) return ' ⚡적전'; return ''; };
              /* (2026-08-10) **실적발표 요약 템플릿**(사용자 지정) — 캘린더와 같은 문구.
                 EPS / Revenue: YoY · QoQ · Consensus 대비 Beat|Miss
                 Gross / Operating Margin: 현재 % · YoY %p · QoQ %p */
              const _adr2=_USFIN&&_USFIN.cur&&_USFIN.cur!=='USD';
              const epsK2=_adr2?'epsA':'eps';
              const sK2=(_adr2&&qq.filter(z=>z.sUS!=null).length>=4)?'sUS':'s';
              const bm=v=>`Consensus 대비 ${v>0?'Beat':'Miss'} ${pc(v)}`;
              const _svv=qq[qi].sSpr!=null?qq[qi].sSpr
                :(_adr2?null:((qq[qi].sE&&qq[qi].s!=null)?((qq[qi].s/qq[qi].sE-1)*100):null));
              const L1=[]; if(gy(epsK2)!=null) L1.push('YoY '+pc(gy(epsK2)));
              if(gq(epsK2)!=null) L1.push('QoQ '+pc(gq(epsK2))+tn(epsK2));
              if(qq[qi].sprE!=null) L1.push(bm(qq[qi].sprE));
              if(L1.length) rows.push(['EPS', L1.join(',  ')]);
              const L2=[]; if(gy(sK2)!=null) L2.push('YoY '+pc(gy(sK2)));
              if(gq(sK2)!=null) L2.push('QoQ '+pc(gq(sK2)));
              if(_svv!=null) L2.push(bm(_svv));
              if(L2.length) rows.push(['Revenue', L2.join(',  ')]);
              const _gm2=k=>{const z=qq[k]; return (z&&z.gp!=null&&z[sK2])?(z.gp/z[sK2]*100):null;};
              const _om2=k=>{const z=qq[k]; return (z&&z.s&&z.o!=null)?(z.o/z.s*100):null;};
              const _pp2=(f,mm)=>{const bb=_bs(mm); if(!bb) return null;
                const x=f(qi), y=f(qq.indexOf(bb)); return (x==null||y==null)?null:(x-y);};
              const ppf=v=>v==null?null:`${v>0?'+':''}${v.toFixed(1)}%p`;
              [['Gross Margin',_gm2],['Operating Margin',_om2]].forEach(([lab,fn])=>{
                const cv=fn(qi); if(cv==null) return;
                const yv=ppf(_pp2(fn,12)), qv=ppf(_pp2(fn,3));
                rows.push([lab, `${cv.toFixed(1)}%`+(yv?`,  YoY ${yv}`:'')+(qv?`,  QoQ ${qv}`:'')]);
              });
            }
            /* 가이던스 → 컨센 리비전 (미국식 순서의 마지막 축) — 최근 발표분에만 값이 있다 */
            if(latest){
              const gl=[];
              /* (2026-08-10) 매출·EPS 가이던스를 각각, 비교 기간 라벨과 함께
                 (우선순위 진행분기→다음분기→올해FY→내년FY — 표·캘린더와 동일) */
              if(rw.gapR!=null) gl.push(`매출 가이던스 ${pc(rw.gapR)} vs ${_GPER(rw.gapRp)} 컨센`);
              else if(rw.gap!=null) gl.push(`가이던스 ${pc(rw.gap)} vs 컨센`);
              if(rw.gapE!=null) gl.push(`EPS 가이던스 ${pc(rw.gapE)} vs ${_GPER(rw.gapEp)} 컨센`);
              if(rw.sprb!=null) gl.push(`4분기 중 ${rw.sprb}회 상회`);
              if(rw.cr7!=null) gl.push(`컨센 7일 ${pc(rw.cr7*100)}`);
              if(rw.cr30!=null) gl.push(`컨센 30일 ${pc(rw.cr30*100)}`);
              if(gl.length) rows.push(['전망', gl.join('   ')]);
            }
          }
          const rc = latest ? {r1:rw.r1, r5:rw.r5, r20:rw.r20} : reactAt(sm.i);
          const rr=[]; if(rc.r1!=null) rr.push('D+1 '+pc(rc.r1));
          if(rc.r5!=null) rr.push('D+5 '+pc(rc.r5));
          if(rc.r20!=null) rr.push('D+20 '+pc(rc.r20));
          rows.push(['주가', rr.length?rr.join('   '):'집계 전']);
          if(!latest) rows.push(['비고','과거 분기 — 서프라이즈·전망 수치는 최근 발표분만 보관']);
        }
        /* (2026-08-09) 공시 원본 링크 — KR: DART 뷰어(rcpNo) · US: SEC EDGAR 접수 인덱스 */
        const url = (mkt==='kr'&&sm.rno) ? `https://dart.fss.or.kr/dsaf001/main.do?rcpNo=${sm.rno}`
                  : (mkt==='us'&&sm.acc&&_ECIK) ? `https://www.sec.gov/Archives/edgar/data/${parseInt(_ECIK,10)}/${String(sm.acc).replace(/-/g,'')}/${sm.acc}-index.htm`
                  : null;
        /* (2026-08-09 2차 확대) 15px 기준 — '더 크게' 피드백 반영 */
        x.font='15px sans-serif';
        const head=`${sm.d.slice(0,4)}.${sm.d.slice(4,6)}.${sm.d.slice(6,8)} ${sm.t==='예'?'실적발표 예정':'실적발표'}`;
        const lines=rows.map(z=>z[0]+'  '+z[1]);
        const wmax=Math.min(Math.max(x.measureText(head).width, ...lines.map(z=>x.measureText(z).width))+32, 640);
        const bh=32+lines.length*23+(url?27:0);
        let bx=Math.min(Math.max(X(sm.i)-wmax/2, P.l), W-P.r-wmax);
        let by=Math.min(Y(hh[sm.i])+16, H-P.b-bh-4); if(by<P.t+18) by=P.t+18;
        x.fillStyle='rgba(255,255,255,.97)'; x.strokeStyle='#d6dbe2';
        if(x.roundRect){ x.beginPath(); x.roundRect(bx,by,wmax,bh,8); x.fill(); x.stroke(); }
        else { x.fillRect(bx,by,wmax,bh); x.strokeRect(bx,by,wmax,bh); }
        x.fillStyle=sm.col; x.font='bold 15px sans-serif'; x.fillText(head, bx+11, by+22);
        rows.forEach((z,k)=>{ const yy=by+46+k*23;
          x.fillStyle='#98a2ad'; x.font='13px sans-serif'; x.fillText(z[0], bx+11, yy);
          x.fillStyle='#3d454f'; x.font='15px sans-serif'; x.fillText(z[1], bx+58, yy); });
        if(url){ const ly=by+46+rows.length*23;
          const lt=(mkt==='kr'?'📄 DART 공시 원본 열기 ↗':'📄 SEC 8-K 원본 열기 ↗');
          x.fillStyle='#1f6feb'; x.font='bold 15px sans-serif'; x.fillText(lt, bx+11, ly);
          _PLK.push({x:bx+7, y:ly-18, w:x.measureText(lt).width+14, h:24, u:url});
        }
      };}
     }
     /* 공시 마커 — 날짜별로 묶어 최신부터 A·B·C… 를 부여하고 캔들 고가 위에 원형 배지로 찍는다.
        클릭 판정을 위해 화면좌표를 _DHIT 에 쌓아 둔다(캔버스는 DOM 이 없어 직접 히트테스트). */
     _DHIT=[];
     if(_DISC&&_DISC.length){
       const byD={}; for(const it of _DISC){ (byD[it.d]=byD[it.d]||[]).push(it); }
       const idx={}; for(let i=0;i<N;i++) idx[String(t[i]||'').replace(/-/g,'')]=i;
       /* (2026-07-21 수정) 예전엔 '최근 26일'만 잘라 써서 마커가 최근 몇 달에만 몰렸다.
          공시가 잦은 종목(삼성전자)은 26일이 4개월치밖에 안 돼 1년 전체가 비어 보였다.
          → 창(표시 구간) 안의 공시일은 모두 쓰고, 라벨을 A~Z 다음 a~z 까지 늘린다(52일).
            그래도 넘치면 라벨 없이 점만 찍되 클릭은 그대로 된다. */
       const days=Object.keys(byD).filter(d=>idx[d]!=null).sort().reverse();
       const LT='ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz';
       days.forEach((d,k)=>{ const i=idx[d], cx0=X(i), cy0=Y(hh[i])-11;
         const sel=(_DSEL===d);
         x.beginPath(); x.arc(cx0, Math.max(cy0,P.t+8), sel?8:6.5, 0, Math.PI*2);
         x.fillStyle=sel?'#c0392b':'rgba(214,69,69,.85)'; x.fill();
         x.strokeStyle='#fff'; x.lineWidth=1.2; x.stroke(); x.lineWidth=1;
         x.fillStyle='#fff'; x.font='bold 9px sans-serif'; x.textAlign='center';
         if(LT[k]) x.fillText(LT[k], cx0, Math.max(cy0,P.t+8)+3);
         x.textAlign='left';
         _DHIT.push({d, x:cx0, y:Math.max(cy0,P.t+8), r:9}); });
       // 선택된 공시 내용 상자
       if(_DSEL&&byD[_DSEL]){
         const its=byD[_DSEL].slice(0,6), i=idx[_DSEL];
         /* (2026-08-09 2차 확대) 15px + 행 클릭 → 공시 원본(실제 <a> 오버레이) */
         x.font='15px sans-serif';
         const lines=its.map(z=>'· '+z.t);
         const head=`${_DSEL.slice(0,4)}.${_DSEL.slice(4,6)}.${_DSEL.slice(6,8)} 공시 ${byD[_DSEL].length}건`;
         const wmax=Math.min(Math.max(x.measureText(head).width, ...lines.map(z=>x.measureText(z).width))+26, 640);
         const bh=29+lines.length*22+(byD[_DSEL].length>6?22:0)+23;   // +23: 원본 안내줄
         let bx=Math.min(Math.max(X(i)-wmax/2, P.l), W-P.r-wmax), by=Math.min(Y(hh[i])+14, H-P.b-bh-4);
         if(by<P.t+18) by=P.t+18;
         x.fillStyle='rgba(255,255,255,.97)'; x.strokeStyle='#d6dbe2';
         if(x.roundRect){ x.beginPath(); x.roundRect(bx,by,wmax,bh,8); x.fill(); x.stroke(); }
         else { x.fillRect(bx,by,wmax,bh); x.strokeRect(bx,by,wmax,bh); }
         x.fillStyle='#c0392b'; x.font='bold 15px sans-serif'; x.fillText(head, bx+10, by+21);
         /* (2026-08-09) 실적팝업과 동일 구조 — 원본이 있는 행은 파란 링크 스타일로 그리고
            그 자리에 실제 <a> 오버레이를 겹친다(제목 자체가 링크). */
         lines.forEach((z,q)=>{ let tx=z;
           const link=(its[q]&&its[q].id!=null);
           x.fillStyle=link?'#1f6feb':'#3d454f'; x.font='15px sans-serif';
           while(x.measureText(tx).width>wmax-38 && tx.length>4) tx=tx.slice(0,-2);
           if(tx!==z) tx=tx.slice(0,-1)+'…';
           x.fillText(tx+(link?' ↗':''), bx+10, by+42+q*22); });
         its.forEach((z,q)=>{ if(z.id!=null)
           _PLK.push({x:bx+7, y:by+42+q*22-17, w:wmax-14, h:22, u:'/dv/'+dcode+'/'+z.id}); });
         if(byD[_DSEL].length>6){ x.fillStyle='#98a2ad'; x.font='15px sans-serif';
           x.fillText(`외 ${byD[_DSEL].length-6}건`, bx+10, by+42+lines.length*22); }
         x.fillStyle='#98a2ad'; x.font='12px sans-serif';
         x.fillText('파란 제목 클릭 = 공시 원본 새 탭', bx+10, by+bh-8);
       }
     }
     if(_epop) _epop();        // 실적팝업은 모든 마커 위에
     // 십자선 — 호버 중인 봉 위치
     if(_CHI!=null){ x.save(); x.setLineDash([3,3]); x.strokeStyle='#9aa4b0';
       x.beginPath(); x.moveTo(X(HI),P.t); x.lineTo(X(HI),H-P.b); x.stroke();
       x.beginPath(); x.moveTo(P.l,Y(c[HI])); x.lineTo(W-P.r,Y(c[HI])); x.stroke(); x.restore(); }
     // 상단 범례 2줄 — 호버 중이면 그 봉, 아니면 최신 봉 기준
     {const dd=String(t[HI]||'').replace(/-/g,'');
      let pv=(HI>0?c[HI-1]:c[HI]);
      if(_isMin()){ const r=_pdc(off+HI); if(r!=null) pv=r; }   // 분봉: 전일 종가 대비 (일봉과 동일한 등락률)
      const df=c[HI]-pv, dp=pv?(df/pv*100):0, upc=df>=0;
      x.font='10px sans-serif'; x.textAlign='left';
      let cx=P.l+4; const put=(txt,col,bold)=>{ x.font=(bold?'bold ':'')+'10px sans-serif';
        x.fillStyle=col; x.fillText(txt,cx,12); cx+=x.measureText(txt).width+5; };
      put(dd?(`${dd.slice(0,4)}.${dd.slice(4,6)}.${dd.slice(6,8)}`
              +(dd.length>=12?` ${dd.slice(8,10)}:${dd.slice(10,12)}`:'')):'', '#5b6470', true);
      put('시','#98a2ad'); put(_pf(o[HI]),'#5b6470');
      put('고','#98a2ad'); put(_pf(hh[HI]),'#5b6470');
      put('저','#98a2ad'); put(_pf(ll[HI]),'#5b6470');
      put('종','#98a2ad'); put(_pf(c[HI]),'#5b6470',true);
      put(`${upc?'▲':'▼'}${_pf(Math.abs(df))} ${dp>=0?'+':''}${dp.toFixed(2)}%`, upc?'#d33':'#1f6feb', true);
      put('거','#98a2ad'); put(Math.round(v[HI]).toLocaleString(),'#5b6470');
      cx=P.l+4;
      const put2=(txt,col)=>{ x.font='10px sans-serif'; x.fillStyle=col; x.fillText(txt,cx,25); cx+=x.measureText(txt).width+5; };
      put2('이동평균','#98a2ad');
      MAS.forEach(m=>put2(String(m.per), m.col));
      put2('볼린저밴드(20,2)','#8296aa');
      put2(`${N}봉`,'#5b6470');
      put2('휠=확대·축소 · 드래그=좌우이동 · 더블클릭=원래대로','#b0b8c2');
     }
     if(useLog){ x.font='bold 10px sans-serif'; x.fillStyle='#8e44ad'; x.fillText('로그 스케일 (상승률 기준 균등)', P.l+4, 38); }
     _syncLinks();   // (2026-08-09) 팝업 링크를 실제 <a> 오버레이로 — 캔버스 클릭 판정 불필요
    };
    drawMain('sd_main',false);   // 로그 판은 (2026-07-26) 제거 — drawMain 의 useLog 경로는 남겨둠
    // ② 거래량
    {const [x,W,H]=_cvs('sd_vol'); const P={l:6,r:52,t:16,b:2};   // t=16 : 상단 거래량 표기 자리
     /* (2026-07-20) 장중 '진행 중' 마지막 봉 처리 —
        반나절치 봉을 온종일 평균선과 비교하면 거래량이 안 터진 것처럼 보인다(실제 문의 사례).
        ① 진행 중 봉은 반투명+빗금으로 미완성임을 표시,
        ② 하루치로 환산한 '예상 높이'를 점선 테두리로 겹쳐 그려 표의 거래량배수와 눈으로 대조되게 한다.
        환산 곡선은 서버(intraday_us.py)와 동일한 U자형 누적거래량 프로필. */
     const _VPROF=[[0,0],[.05,.10],[.10,.16],[.15,.21],[.20,.26],[.30,.34],[.40,.42],[.50,.50],
                   [.60,.58],[.70,.66],[.80,.75],[.90,.86],[.95,.92],[1,1]];
     const _cumVol=t=>{ if(t<=0)return .05; if(t>=1)return 1;
       for(let i=1;i<_VPROF.length;i++){ const a=_VPROF[i-1],b=_VPROF[i];
         if(t<=b[0]) return Math.max(.05, a[1]+(b[1]-a[1])*((t-a[0])/(b[0]-a[0]))); } return 1; };
     const _sess=()=>{ try{
         const tz = mkt==='kr' ? 'Asia/Seoul' : 'America/New_York';
         const pp={}; new Intl.DateTimeFormat('en-CA',{timeZone:tz,year:'numeric',month:'2-digit',
           day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false,weekday:'short'})
           .formatToParts(new Date()).forEach(z=>pp[z.type]=z.value);
         if(pp.weekday==='Sat'||pp.weekday==='Sun') return null;
         const hm=+pp.hour*60 + +pp.minute;
         const op = mkt==='kr' ? 9*60 : 9*60+30, cl = mkt==='kr' ? 15*60+30 : 16*60;
         if(hm<=op||hm>=cl) return null;
         return {f:(hm-op)/(cl-op), d:pp.year+pp.month+pp.day};
       }catch(e){ return null; } };
     const _sf=_sess();
     const _inProg = !!(_sf && String(t[N-1]||'').replace(/-/g,'')===_sf.d && v[N-1]);
     const _projV = _inProg ? v[N-1]/_cumVol(_sf.f) : 0;
     const vm=Math.max(Math.max(...v), _projV)||1, X=i=>P.l+(W-P.l-P.r)*(i+0.5)/N, bw=Math.max(1,(W-P.l-P.r)/N*0.6);
     for(let i=0;i<N;i++){ const prog=_inProg&&i===N-1, up=c[i]>=o[i];
       x.fillStyle=up?`rgba(221,51,51,${prog?.20:.45})`:`rgba(31,111,235,${prog?.20:.45})`;
       const h2=(H-P.t-P.b)*v[i]/vm, bx=X(i)-bw/2; x.fillRect(bx, H-P.b-h2, bw, h2);
       if(prog){
         const col=up?'#dd3333':'#1f6feb';
         x.save(); x.beginPath(); x.rect(bx,H-P.b-h2,bw,h2); x.clip();   // 진행분에 빗금
         x.strokeStyle=col; x.globalAlpha=.55; x.lineWidth=1;
         for(let g=-h2;g<bw+h2;g+=3){ x.beginPath(); x.moveTo(bx+g,H-P.b); x.lineTo(bx+g+h2,H-P.b-h2); x.stroke(); }
         x.restore();
         /* 봉 폭이 4px 안팎이라 테두리만으론 잘 안 보인다 →
            ①현재 높이~예상 높이 구간을 옅은 고스트로 채우고 ②예상 높이에 점선 캡을 좌우로 길게 긋는다. */
         const hp=(H-P.t-P.b)*_projV/vm, yTop=H-P.b-hp;
         x.save();
         x.fillStyle=up?'rgba(221,51,51,.10)':'rgba(31,111,235,.10)';
         x.fillRect(bx, yTop, bw, (H-P.b-h2)-yTop);
         x.setLineDash([3,2]); x.strokeStyle=col; x.lineWidth=1.2; x.globalAlpha=.9;
         x.beginPath(); x.moveTo(bx-3, yTop); x.lineTo(bx+bw+3, yTop); x.stroke();   // 예상 높이 캡
         x.setLineDash([2,2]); x.globalAlpha=.45;
         x.beginPath(); x.moveTo(bx, yTop); x.lineTo(bx, H-P.b-h2);
         x.moveTo(bx+bw, yTop); x.lineTo(bx+bw, H-P.b-h2); x.stroke();
         x.restore();
       } }
     /* (2026-07-20) 거래량 평균선 2종.
        20일 = 최근 거래량 변화에 빠르게 반응(급증 포착용).
        63일(3개월) = 표의 '거래량배수' 분모(미국 quotes 의 3개월 평균)와 같은 기준 → 표·차트 정합성. */
     const vline=(arr,col,dash)=>{ x.strokeStyle=col; x.setLineDash(dash||[]); x.beginPath(); let s=false;
       for(let i=0;i<N;i++){ if(arr[i]==null)continue; const y=H-P.b-(H-P.t-P.b)*arr[i]/vm;
         s?x.lineTo(X(i),y):(x.moveTo(X(i),y),s=true); } x.stroke(); x.setLineDash([]); };
     vline(_sma(v,20),'#666');
     vline(_sma(v,63),'#d98c1a',[4,3]);
     x.font='10px sans-serif';
     /* 우측 여백(P.r=52)은 다른 패널과 x축을 맞추려 고정 — 라벨은 9px로 줄여 잘리지 않게 한다. */
     if(_CHI!=null){ x.save(); x.setLineDash([3,3]); x.strokeStyle='#9aa4b0';
       x.beginPath(); x.moveTo(X(HI),P.t); x.lineTo(X(HI),H-P.b); x.stroke(); x.restore(); }
     // 좌상단 현재(또는 호버) 거래량 · 우측 y축 눈금
     x.font='10px sans-serif'; x.fillStyle='#98a2ad'; x.fillText('거래량', P.l+4, 12);
     x.fillStyle='#5b6470'; x.font='bold 10px sans-serif';
     x.fillText(Math.round(v[HI]).toLocaleString(), P.l+42, 12);
     x.font='9px sans-serif'; x.fillStyle='#98a2ad';
     x.fillText(_mk(vm), W-P.r+4, 74); x.fillText(_mk(vm/2), W-P.r+4, 86);
     x.fillStyle='#98a2ad'; x.fillText('VOL·20일', W-P.r+4, 12);
     x.fillStyle='#d98c1a'; x.fillText('3개월평균', W-P.r+4, 24);
     if(_inProg){ x.fillStyle='#c0392b';
       x.fillText(`진행 ${Math.round(_sf.f*100)}%`, W-P.r+4, 38);
       x.fillText('▨=현재', W-P.r+4, 50);
       x.fillText('┈=예상', W-P.r+4, 62); }
     /* 상세 설명은 폭이 넉넉한 차트 하단 각주로 넘긴다(캔버스 우측은 52px뿐). */
     window.__volProg = _inProg ? {f:_sf.f, now:v[N-1], proj:_projV,
                                   ma63:(_sma(v,63)[N-1]||null)} : null; }
    // ③ RSI(14)
    {const [x,W,H]=_cvs('sd_rsi'); const P={l:6,r:52,t:18,b:4};   // t=18 : 상단 범례 자리
     const X=i=>P.l+(W-P.l-P.r)*(i+0.5)/N, Y=p=>P.t+(H-P.t-P.b)*(1-p/100);
     x.strokeStyle='#eceff3'; [30,50,70].forEach(g=>{ x.beginPath(); x.moveTo(P.l,Y(g)); x.lineTo(W-P.r,Y(g)); x.stroke(); });
     x.font='10px sans-serif';
     x.fillStyle='#d33'; x.fillText('70',W-P.r+4,Y(70)+3);
     x.fillStyle='#1f6feb'; x.fillText('30',W-P.r+4,Y(30)+3);
     const rsig=_sma(rsi,9);   // RSI 시그널 = RSI 의 9일 이동평균(네이버 RSI(14,9) 의 뒤 숫자)
     const rline=(a,col)=>{ x.strokeStyle=col; x.beginPath(); let st2=false;
       for(let i=0;i<N;i++){ if(a[i]==null)continue; st2?x.lineTo(X(i),Y(a[i])):(x.moveTo(X(i),Y(a[i])),st2=true); } x.stroke(); };
     rline(rsi,'#555'); rline(rsig,'#f39c12');
     /* ADX 를 같은 패널에 얹는다 — 0~100 스케일이 RSI 와 같아 축을 공유할 수 있고,
        패널을 하나 더 늘리지 않아 스크롤 부담이 없다. 25 기준선을 점선으로 표시. */
     const adxA=_adx(hh,ll,c,14);
     x.save(); x.setLineDash([2,2]); x.strokeStyle='#cfd6de';
     x.beginPath(); x.moveTo(P.l,Y(25)); x.lineTo(W-P.r,Y(25)); x.stroke(); x.restore();
     x.save(); x.setLineDash([5,3]); rline(adxA,'#8e44ad'); x.restore(); x.setLineDash([]);
     if(_CHI!=null){ x.save(); x.setLineDash([3,3]); x.strokeStyle='#9aa4b0';
       x.beginPath(); x.moveTo(X(HI),P.t); x.lineTo(X(HI),H-P.b); x.stroke(); x.restore(); }
     {let cx=P.l+4; const put=(txt,col,bold)=>{ x.font=(bold?'bold ':'')+'10px sans-serif';
        x.fillStyle=col; x.fillText(txt,cx,12); cx+=x.measureText(txt).width+5; };
      put('RSI (14,9)','#98a2ad'); put('RSI','#98a2ad');
      put(rsi[HI]!=null?rsi[HI].toFixed(2):'—','#5b6470',true);
      const rs=_rsiState(rsi[HI]); if(rs) cx+=_badge(x,cx,12,rs[0],rs[1],rs[2]);
      put('RSI-Signal','#f39c12'); put(rsig[HI]!=null?rsig[HI].toFixed(2):'—','#f39c12',true);
      put('ADX(14)','#8e44ad'); put(adxA[HI]!=null?adxA[HI].toFixed(1):'—','#8e44ad',true);
      const as=_adxState(adxA[HI]); if(as) cx+=_badge(x,cx,12,as[0],as[1],as[2]); } }
    // ④ MACD
    {const [x,W,H]=_cvs('sd_macd'); const P={l:6,r:52,t:18,b:4};  // t=18 : 상단 범례 자리
     const vals=[...macd,...sig,...hist].filter(y=>y!=null);
     const mx=Math.max(...vals.map(Math.abs))||1;
     const X=i=>P.l+(W-P.l-P.r)*(i+0.5)/N, Y=p=>P.t+(H-P.t-P.b)*(1-(p+mx)/(2*mx));
     x.strokeStyle='#eceff3'; x.beginPath(); x.moveTo(P.l,Y(0)); x.lineTo(W-P.r,Y(0)); x.stroke();
     const bw=Math.max(1,(W-P.l-P.r)/N*0.6);
     for(let i=0;i<N;i++){ if(hist[i]==null)continue; x.fillStyle=hist[i]>=0?'rgba(221,51,51,.5)':'rgba(31,111,235,.5)';
       const y0=Y(0), y1=Y(hist[i]); x.fillRect(X(i)-bw/2, Math.min(y0,y1), bw, Math.max(1,Math.abs(y1-y0))); }
     const line=(a,col)=>{ x.strokeStyle=col; x.beginPath(); let s=false;
       for(let i=0;i<N;i++){ if(a[i]==null)continue; s?x.lineTo(X(i),Y(a[i])):(x.moveTo(X(i),Y(a[i])),s=true); } x.stroke(); };
     line(macd,'#333'); line(sig,'#f39c12');
     if(_CHI!=null){ x.save(); x.setLineDash([3,3]); x.strokeStyle='#9aa4b0';
       x.beginPath(); x.moveTo(X(HI),P.t); x.lineTo(X(HI),H-P.b); x.stroke(); x.restore(); }
     x.font='9px sans-serif'; x.fillStyle='#98a2ad';
     x.fillText(_mk(mx), W-P.r+4, Y(mx)+9); x.fillText('0', W-P.r+4, Y(0)+3);
     {let cx=P.l+4; const put=(txt,col,bold)=>{ x.font=(bold?'bold ':'')+'10px sans-serif';
        x.fillStyle=col; x.fillText(txt,cx,12); cx+=x.measureText(txt).width+5; };
      const f2=z=>z==null?'—':(Math.abs(z)>=1000?Math.round(z).toLocaleString():z.toFixed(2));
      put('MACD (12,26,9)','#98a2ad'); put('MACD','#98a2ad'); put(f2(macd[HI]),'#333',true);
      put('Signal','#f39c12'); put(f2(sig[HI]),'#f39c12',true);
      const ms=_macdState(macd[HI],sig[HI]); if(ms) cx+=_badge(x,cx,12,ms[0],ms[1],ms[2]); } }
    // ⑤ 수급(한국 일봉) / OBV(그 외) — 같은 패널 자리를 공유한다.
    /* (2026-07-21 수정) 투자자별 순매매는 KRX가 '일 단위로만' 공표한다(분 단위 데이터 없음).
       그래서 분봉(하루 안 여러 봉)에 얹으면 하루 점 하나짜리 일일 누적선이라 x축과 안 맞았다.
       → 일별 수급선은 '일봉'에만 그린다. 분봉·주월봉에는 그 자리에 OBV(분봉 거래량 기반 매집/분산)를
         그린다. 분봉의 장중 외인·기관 흐름은 ③ 투자자 가집계(당일 5회차)가 담당한다. */
    const _useInv = (mkt==='kr' && _TF==='d');
    if(!_useInv){
      const el=$('sd_inv');
      if(el){ el.style.display='block';
        const [x,W,H]=_cvs('sd_inv'); const P={l:6,r:52,t:16,b:14};
        const ob=[]; let acc=0;
        for(let i=0;i<N;i++){ if(i>0) acc+=(c[i]>c[i-1]?(v[i]||0):c[i]<c[i-1]?-(v[i]||0):0); ob.push(acc); }
        let omx=Math.max(...ob), omn=Math.min(...ob); if(omx===omn){omx+=1;omn-=1;}
        const X=i=>P.l+(W-P.l-P.r)*(i+0.5)/N, Y=q=>P.t+(H-P.t-P.b)*(1-(q-omn)/(omx-omn));
        x.strokeStyle='#eceff3'; x.beginPath(); x.moveTo(P.l,Y(0)); x.lineTo(W-P.r,Y(0)); x.stroke();
        x.strokeStyle='#1f6feb'; x.lineWidth=1.5; x.beginPath();
        for(let i=0;i<N;i++) i?x.lineTo(X(i),Y(ob[i])):x.moveTo(X(i),Y(ob[i]));
        x.stroke(); x.lineWidth=1;
        if(_CHI!=null){ x.save(); x.setLineDash([3,3]); x.strokeStyle='#9aa4b0';
          x.beginPath(); x.moveTo(X(HI),P.t); x.lineTo(X(HI),H-P.b); x.stroke(); x.restore(); }
        x.font='9px sans-serif'; x.fillStyle='#98a2ad';
        x.fillText(_mk(omx),W-P.r+4,Y(omx)+9); x.fillText(_mk(omn),W-P.r+4,Y(omn)-2);
        // x축 — 메인 차트와 같은 라벨·위치(공통 함수). 분봉이면 M/D·정시, 그 외 월/연.
        _xlabels(x, X, H);
        let cx=P.l+4; const put=(txt,col,bold)=>{ x.font=(bold?'bold ':'')+'10px sans-serif';
          x.fillStyle=col; x.fillText(txt,cx,12); cx+=x.measureText(txt).width+5; };
        put('OBV (누적 거래량)','#98a2ad'); put(_mk(ob[HI]),'#1f6feb',true);
        put('· 주가와 같은 방향이면 추세 확인, 안 따라오면 다이버전스(주가↑OBV정체=분산 / 주가↓OBV정체=매집)','#98a2ad');
      }
    } else if(_INV) drawInv(_INV);   // 한국 일봉·분봉: 투자자별 누적순매수
  }
  // ⑤ 투자자별 누적순매수 (KR 전용 — 네이버 1년 + KIS 30일 병합)
  async function loadInv(c){
    const e=$('sd_inv'); if(!e) return;
    if(!(mkt==='kr' && _TF==='d')){ _INV=null; e.style.display='block'; _paint(); return; }  // 일봉 아니면 OBV(_paint 가 그림)
    e.style.display='block';
    try{
      const J=await (await fetch(`/api/investor/kr/${encodeURIComponent(c)}`)).json();
      if(dcode!==c) return;
      drawInv(J);
    }catch(err){ const [x]=_cvs('sd_inv'); x.font='11px sans-serif'; x.fillStyle='#98a2ad'; x.fillText('수급 데이터 로드 실패',10,22); }
  }
  function drawInv(J){
    _INV=J;                                   // 호버 재그리기용 원본 보관
    const n=(J.t||[]).length; if(!n) return;
    // 누적합 — 개인 미제공 구간(KIS 이전)은 −(외인+기관) 추정
    const cf=[],co=[],cp=[],est=[]; let sf=0,so=0,sp=0;
    for(let i=0;i<n;i++){ sf+=J.frgn[i]||0; so+=J.orgn[i]||0;
      const isEst=J.prsn[i]==null;
      sp+= isEst? -((J.frgn[i]||0)+(J.orgn[i]||0)) : J.prsn[i];
      cf.push(sf); co.push(so); cp.push(sp); est.push(isEst); }
    const [x,W,H]=_cvs('sd_inv'); const P={l:6,r:52,t:6,b:14};
    /* (2026-07-21) x축을 메인 차트와 정렬한다.
       수급 소스(네이버 1년+KIS)가 가격 차트(최근 250봉)보다 길어서, 그대로 그리면
       같은 날짜인데도 십자선 위치가 패널마다 어긋났다.
       → 표시 구간만 메인 차트 시작일 이후로 자른다. 누적 순매수 자체는 전 구간으로
         계산한 뒤 잘라내므로 '그 시점까지의 진짜 누적값'은 그대로 유지된다. */
    /* (2026-07-21 재작성) x 를 '메인 차트 인덱스'로 직접 매핑한다.
       종전엔 수급 패널이 자기 인덱스로 폭을 나눠 썼다. 일봉 250봉일 땐 얼추 맞았지만
         · 분봉으로 바꾸면 9거래일 = 수급 점 9개를 화면 전체에 늘려 그려 선이 평평해 보였고
         · 일봉을 10년으로 늘린 뒤엔 수급(1년)이 화면 일부 구간에만 해당하는데 전체 폭을 차지했다.
       → 수급 점의 '날짜'를 메인 차트의 봉 위치로 옮겨 찍는다. 화면 밖 날짜는 그리지 않는다.
         분봉이면 하루에 여러 봉이므로 그 날의 마지막 봉 위치에 찍는다(수급은 종가 기준 확정치). */
    const NN=Math.max(_CN||1,1);
    const posOf=new Map();
    if(_CT) for(let i=0;i<Math.min(NN,_CT.length);i++) posOf.set(String(_CT[i]||'').slice(0,8), i);
    const vis=[];                                  // [메인인덱스, 수급인덱스]
    for(let k=0;k<n;k++){ const q=posOf.get(String(J.t[k]||'').replace(/-/g,'').slice(0,8));
      if(q!=null) vis.push([q,k]); }
    if(!vis.length){                               // 겹치는 구간이 없다(줌아웃이 수급 이력보다 과거)
      x.font='11px sans-serif'; x.fillStyle='#98a2ad';
      x.fillText('이 구간에는 투자자별 수급 데이터가 없습니다(최근 1년만 제공)', P.l+6, H/2);
      return; }
    /* (2026-07-21) 표시 구간 시작점을 0 으로 맞춘다(리베이스).
       세 계열의 '절대 누적 수준'이 서로 크게 벌어져 있어(외인 −1.8억 · 기관 +0.7억 · 개인 +1.1억)
       그대로 그리면 계열 간 간격이 y축을 다 먹고, 구간 내 변화는 평평한 직선으로 보인다.
       실제로 알고 싶은 건 '이 구간 동안 누가 얼마나 샀나'이므로 구간 시작을 0 으로 놓는다.
       특히 분봉(9거래일)에서는 리베이스 없이는 사실상 아무 정보가 없다. */
    const i0=vis[0][1];
    /* (2026-07-21 수정) 리베이스 기준은 '첫 표시일'이 아니라 '그 직전일'이어야 한다.
       cf[i0] 를 빼면 첫날 자신의 순매수가 0 으로 지워져 구간 합계에서 빠진다.
       실측(005930 5분봉 9거래일): 첫날(7/8) 외국인 −301만이 누락돼
         표시 +367만 vs 실제 9일 합계 +65.7만 으로 크게 벌어졌다.
       → 직전일 누계를 기준으로 삼아 표시 구간의 모든 날이 합계에 들어가게 한다. */
    const bi=Math.max(i0-1,-1);
    const b0=bi>=0?cf[bi]:0, b1=bi>=0?co[bi]:0, b2=bi>=0?cp[bi]:0;
    const RF=k=>cf[k]-b0, RO=k=>co[k]-b1, RP=k=>cp[k]-b2;
    const all=vis.flatMap(([,k])=>[RF(k),RO(k),RP(k)]);
    let mx=Math.max(...all,0), mn=Math.min(...all,0);
    if(mx===mn){ mx+=1; mn-=1; }
    const X=i=>{ const q=posOf.get(String(J.t[i]||'').replace(/-/g,'').slice(0,8));
      return P.l+(W-P.l-P.r)*(((q==null?0:q))+0.5)/NN; };
    const Y=p=>P.t+(H-P.t-P.b)*(1-(p-mn)/(mx-mn));
    // 0선 + 상하한 라벨
    x.strokeStyle='#eceff3'; x.beginPath(); x.moveTo(P.l,Y(0)); x.lineTo(W-P.r,Y(0)); x.stroke();
    const fmt=v=>{const a=Math.abs(v);
      return (a>=1e8?(v/1e8).toFixed(1)+'억':a>=1e4?Math.round(v/1e4).toLocaleString()+'만':String(Math.round(v)))+'주';};
    x.font='10px sans-serif'; x.fillStyle='#98a2ad';
    x.fillText(fmt(mx),W-P.r+4,Y(mx)+8); x.fillText(fmt(mn),W-P.r+4,Y(mn)-2);
    // 선 그리기 (from~to 구간, 점선 여부)
    const inView=i=>posOf.has(String(J.t[i]||'').replace(/-/g,'').slice(0,8));
    const seg=(a,col,i0,i1,dash)=>{ if(i1<=i0) return;
      x.strokeStyle=col; x.lineWidth=1.5; x.setLineDash(dash?[3,3]:[]);
      x.beginPath(); let started=false;
      for(let i=i0;i<=i1;i++){ if(!inView(i)) continue;      // 화면 밖 날짜는 건너뛴다
        started?x.lineTo(X(i),Y(a[i])):(x.moveTo(X(i),Y(a[i])),started=true); }
      if(started) x.stroke();
      x.setLineDash([]); x.lineWidth=1; };
    const F='#d33', O='#1f6feb', PP='#27ae60';   // 외국인 빨강 · 기관 파랑 · 개인 초록 (3.2.1 배색)
    const _cf=cf.map((v,k)=>v-b0), _co=co.map((v,k)=>v-b1), _cp=cp.map((v,k)=>v-b2);
    seg(_cf,F,i0,n-1,false); seg(_co,O,i0,n-1,false);
    let cut=est.indexOf(false); if(cut<0) cut=n; cut=Math.max(cut,i0);   // 개인: 추정(점선) → 실측(실선)
    seg(_cp,PP,i0,Math.min(cut,n-1),true); if(cut<n) seg(_cp,PP,Math.max(cut-1,i0),n-1,false);
    // x축 날짜 3틱 + 범례
    x.fillStyle='#98a2ad';
    /* 표시 구간이 짧으면(분봉 등) 연.월 라벨이 전부 같아져 무의미하다 → 월.일로 바꾼다. */
    {const dFirst=String(J.t[vis[0][1]]||'').replace(/-/g,''),
           dLast =String(J.t[vis[vis.length-1][1]]||'').replace(/-/g,'');
     const sameMonth = dFirst.slice(0,6)===dLast.slice(0,6);
     for(let g=0;g<3;g++){ const [,k]=vis[Math.floor((vis.length-1)*g/3)]||vis[0];
       const d=String(J.t[k]||'').replace(/-/g,'');
       x.fillText(sameMonth ? (+d.slice(4,6))+'.'+(+d.slice(6,8))
                            : d.slice(2,4)+'.'+d.slice(4,6), X(k)-10, H-3); } }
    /* 십자선 — 메인 차트와 봉수가 달라 인덱스가 아니라 날짜로 맞춘다.
       정확히 같은 날짜가 없으면(휴장·데이터 갭) 그 이전 최근 거래일로 붙인다. */
    let hj=n-1;
    if(_CHI!=null&&_CHD){
      let f=J.t.findIndex(z=>String(z||'').replace(/-/g,'')===_CHD);
      if(f<0){ for(let k=n-1;k>=0;k--){ if(String(J.t[k]||'').replace(/-/g,'')<=_CHD){ f=k; break; } } }
      if(f>=0){ hj=f;
        x.save(); x.setLineDash([3,3]); x.strokeStyle='#9aa4b0';
        x.beginPath(); x.moveTo(X(hj),P.t); x.lineTo(X(hj),H-P.b); x.stroke(); x.restore(); } }
    // 범례 — 해당일(호버 없으면 최신) 누적 순매수까지 같이 표기
    {let cx=P.l+4; const put=(txt,col,bold)=>{ x.font=(bold?'bold ':'')+'10px sans-serif';
       x.fillStyle=col; x.fillText(txt,cx,14); cx+=x.measureText(txt).width+4; };
     put('구간 순매수','#98a2ad');
     put('외국인',F,true); put(fmt(cf[hj]-b0),F);
     put('기관',O,true);   put(fmt(co[hj]-b1),O);
     put('개인',PP,true);  put(fmt(cp[hj]-b2)+(est[hj]?'(추정)':''),PP);
     put('· 여러 날 누적(일 단위) · 표시 구간 합계','#b0b8c2'); }
  }

  // ── 2단계 z-score 랭킹 ──
  const AX=[['val','V 밸류','싼 종목 (−PER·−PBR·+배당)'],['grw','G 성장','이익 모멘텀 (EPS 성장)'],
            ['mom','M 모멘텀','주가·리비전 모멘텀 (12−1M·52주고점·200일선·추정 리비전)'],['qly','Q 수익성','ROE 근사 (PBR÷PER)']];
  let S2={kr:[],us:[]}, s2loaded=false, W={val:1,grw:1,mom:1,qly:1}, ON={val:1,grw:1,mom:1,qly:1},
      topN=0, sort2={k:'rscore',d:-1};
  function resetW(){ W={val:1,grw:1,mom:1,qly:1}; ON={val:1,grw:1,mom:1,qly:1}; topN=0; sort2={k:'rscore',d:-1}; resetF2(); }
  // z 원자료 하드컷 필터 (축 전부 해제 시 순수 필터로 사용 가능)
  const DEF2={
    kr:{
      per:{label:'PER',field:'fper',dir:'max',u:1,fmt:v=>v.toFixed(1)+'배',presets:[['전체',null],['10배 ↓',10],['15배 ↓',15],['20배 ↓',20]]},
      pbr:{label:'PBR',field:'pbr',dir:'max',u:1,fmt:v=>v.toFixed(1)+'배',presets:[['전체',null],['1배 ↓',1],['2배 ↓',2],['3배 ↓',3]]},
      divy:{label:'배당',field:'divy',dir:'min',u:1,fmt:v=>v.toFixed(1)+'%',presets:[['전체',null],['1% ↑',1],['2% ↑',2],['3% ↑',3]]},
      grw:{label:'성장',field:'g_new',dir:'min',u:0.01,fmt:v=>(v*100).toFixed(0)+'%',presets:[['전체',null],['0% ↑',0],['10% ↑',0.1],['20% ↑',0.2],['50% ↑',0.5]]},
      mom:{label:'추세',field:'mom',dir:'min',u:0.01,fmt:v=>(v*100).toFixed(0)+'%',presets:[['전체',null],['0% ↑',0],['50% ↑',0.5],['100% ↑',1],['200% ↑',2]]},
      hi:{label:'고점比',field:'near52',dir:'min',u:0.01,fmt:v=>'고점 '+(v*100).toFixed(0)+'%',presets:[['전체',null],['고점 -10% 이내',-0.10],['고점 -20% 이내',-0.20],['고점 -30% 이내',-0.30]]},
      v200:{label:'200일선',field:'vs200',dir:'min',u:0.01,fmt:v=>(v>=0?'+':'')+(v*100).toFixed(0)+'%',presets:[['전체',null],['200일선 위',0],['+10% 이상',0.10],['+20% 이상',0.20]]}
    },
    us:{
      per:{label:'P/E',field:'fpe',dir:'max',u:1,fmt:v=>v.toFixed(1)+'배',presets:[['전체',null],['10배 ↓',10],['15배 ↓',15],['20배 ↓',20]]},
      pbr:{label:'P/B',field:'pb',dir:'max',u:1,fmt:v=>v.toFixed(1)+'배',presets:[['전체',null],['1배 ↓',1],['2배 ↓',2],['3배 ↓',3]]},
      divy:{label:'배당',field:'divy',dir:'min',u:0.01,fmt:v=>(v*100).toFixed(1)+'%',presets:[['전체',null],['1% ↑',0.01],['2% ↑',0.02],['3% ↑',0.03]]},
      grw:{label:'성장',field:'g_new',dir:'min',u:0.01,fmt:v=>(v*100).toFixed(0)+'%',presets:[['전체',null],['0% ↑',0],['10% ↑',0.1],['20% ↑',0.2],['50% ↑',0.5]]},
      mom:{label:'추세',field:'w52',dir:'min',u:1,fmt:v=>v.toFixed(0)+'%',presets:[['전체',null],['0% ↑',0],['50% ↑',50],['100% ↑',100],['200% ↑',200]]},
      hi:{label:'고점比',field:'hi52',dir:'min',u:0.01,fmt:v=>'고점 '+(v*100).toFixed(0)+'%',presets:[['전체',null],['고점 -10% 이내',-0.10],['고점 -20% 이내',-0.20],['고점 -30% 이내',-0.30]]},
      v200:{label:'200일선',field:'vs200',dir:'min',u:0.01,fmt:v=>(v>=0?'+':'')+(v*100).toFixed(0)+'%',presets:[['전체',null],['200일선 위',0],['+10% 이상',0.10],['+20% 이상',0.20]]}
    }
  };
  const ALLK2=['per','pbr','divy','grw','mom','hi','v200'];
  const k2list=()=>Object.keys(DEF2[mkt]);
  let F2={};
  const F2_ST={};   // 마켓별 2단계 하드컷 상태 유지
  function resetF2(){ F2={}; for(const k of ALLK2) F2[k]={v:null}; F2_ST[mkt]=F2; }
  function loadF2(){ if(!F2_ST[mkt]){resetF2();} else F2=F2_ST[mkt]; }
  resetF2();
  function pass2(r){ const d=DEF2[mkt];
    for(const k of k2list()){ const st=F2[k]; if(st.v==null)continue; const f=d[k]; const fv=r[f.field];
      if(fv==null)continue; if(f.dir==='max'&&fv>st.v)return false; if(f.dir==='min'&&fv<st.v)return false; }
    return true; }
  function chipLabel2(k){ const f=DEF2[mkt][k], v=F2[k].v;
    return v==null?`${f.label}: <span class="cv">전체</span>`:`${f.label}: <span class="cv">${f.fmt(v)} ${f.dir==='max'?'↓':'↑'}</span>`; }
  function renderChips2(){ const d=DEF2[mkt];
    $('scr_fltbar2').innerHTML=`<span style="font-size:11.5px;color:var(--tx2);align-self:center;margin-right:2px">원자료 하드컷:</span>`+k2list().map(k=>{
      const f=d[k], v=F2[k].v, active=v!=null;
      const pop=`<div class="pl">프리셋 (${f.dir==='max'?'이하':'이상'})</div>`+
        f.presets.map(p=>{const pv=p[1]; const sel=(v===pv); return `<button class="preset ${sel?'sel':''}" data-k2="${k}" data-v="${pv==null?'':pv}">${E(p[0])}</button>`;}).join('')+
        `<div class="man"><span>직접</span><input type="number" placeholder="${f.dir==='max'?'최대':'최소'}" data-man2="${k}" value="${v==null?'':(+(v/f.u).toFixed(4))}"><span>${f.dir==='max'?'↓':'↑'}</span></div>`;
      return `<div class="fchip"><button class="${active?'act':''}" data-chip2="${k}">${chipLabel2(k)}</button><div class="fpop" id="pop2_${k}">${pop}</div></div>`;
    }).join('');
    $('scr_fltbar2').querySelectorAll('[data-chip2]').forEach(bt=>bt.onclick=e=>{e.stopPropagation();const k=bt.dataset.chip2;const p=$('pop2_'+k);const w=p.classList.contains('open');document.querySelectorAll('.fpop').forEach(x=>x.classList.remove('open'));if(!w)p.classList.add('open');});
    $('scr_fltbar2').querySelectorAll('[data-k2]').forEach(bt=>bt.onclick=()=>{F2[bt.dataset.k2].v=bt.dataset.v===''?null:+bt.dataset.v; rankTbl(); renderChips2();});
    $('scr_fltbar2').querySelectorAll('[data-man2]').forEach(inp=>inp.oninput=()=>{const k=inp.dataset.man2;const f=DEF2[mkt][k];F2[k].v=inp.value===''?null:(+inp.value)*f.u;
      const bt=$('scr_fltbar2').querySelector(`[data-chip2="${k}"]`); if(bt){bt.innerHTML=chipLabel2(k);bt.classList.toggle('act',F2[k].v!=null);} rankTbl();});
  }
  function renderS2(){ renderWPanel(); rankTbl(); renderLegend(); }   /* KR↔US 전환 시 VGMQ 설명도 갱신 */
  const zClass=z=>z==null?'':(z>=1.5?'zc2':z>=0.5?'zc1':z<=-1.5?'zn2':z<=-0.5?'zn1':'');
  const zFmt=z=>z==null?'—':(z>0?'+':'')+z.toFixed(2);
  function renderWPanel(){
    const nOn=AX.filter(a=>ON[a[0]]).length;
    $('scr_wpanel').innerHTML=AX.map(a=>{const k=a[0];
      return `<div class="wax ${ON[k]?'':'off'}"><div class="wh"><label><input type="checkbox" data-axon="${k}" ${ON[k]?'checked':''}> ${E(a[1])}</label><span class="wv">${(W[k]).toFixed(1)}x</span></div>
        <input type="range" min="0" max="3" step="0.1" value="${W[k]}" data-axw="${k}" ${ON[k]?'':'disabled'}>
        <div class="wd">${E(a[2])}</div></div>`;}).join('')+
      `<div class="wtop">상위 <input type="number" min="0" max="600" placeholder="전체" value="${topN||''}" id="scr_topn"> 위(0=전체) <span style="color:var(--tx2)">· 축 ${nOn}/4 (0=필터만)</span></div>`;
    $('scr_wpanel').querySelectorAll('[data-axw]').forEach(r=>r.oninput=()=>{
      const k=r.dataset.axw; W[k]=+r.value; r.closest('.wax').querySelector('.wv').textContent=W[k].toFixed(1)+'x'; rankTbl(); });
    $('scr_wpanel').querySelectorAll('[data-axon]').forEach(c=>c.onchange=()=>{
      ON[c.dataset.axon]=c.checked; renderWPanel(); rankTbl(); });
    const tn=$('scr_topn'); if(tn) tn.oninput=()=>{ topN=Math.max(0,Math.min(600,+tn.value||0)); rankTbl(); };
  }
  const COL2={
    /* (2026-07-26) 각 축 계산에 실제 쓰이는 지표를 전부 컬럼으로 노출
       V=PER·PBR·배당 / G=성장 / M=모멘텀(한국 12M·미국 12-1M)·고점比·200일선·리비전 / Q=ROE·부채비율(·FCF) */
    kr:[['n','종목',0],['rscore','종합',1,'z'],['z_val','V',1,'z'],['z_grw','G',1,'z'],['z_mom','M',1,'z'],['z_qly','Q',1,'z'],
        ['fper','PER',1],['pbr','PBR',1],['divy','배당%',1],['g_new','성장',1],
        ['mom',(mkt==='kr'?'12M':'12-1M'),1],['near52','고점比',1],['vs200','200일선',1],['rev','리비전',1],
        ['edld','발표일',1],['spr','영업익서프%',1],['sspr','매출서프%',1],['sprb','비트4Q',1],['cr30','추정30일',1],['cr90','추정90일',1],['tprv','목표가30일',1],['tprv90','목표가90일',1],['gap','가이던스갭',1],['r1','발표D+1',1],['r20','발표D+20',1],
        ['roe','ROE',1],['de','부채비율',1]],
    us:[['n','종목',0],['rscore','종합',1,'z'],['z_val','V',1,'z'],['z_grw','G',1,'z'],['z_mom','M',1,'z'],['z_qly','Q',1,'z'],
        ['fpe','PE',1],['pb','PB',1],['divy','배당%',1],['g_new','성장',1],
        ['w52','52주',1],['hi52','고점比',1],['vs200','200일선',1],['rev','리비전',1],
        ['edld','발표일',1],['spr','EPS서프%',1],['sspr','매출서프%',1],['sprb','비트4Q',1],['cr7','컨센7일',1],['cr30','컨센30일',1],['cr90','컨센90일',1],['tprv','목표가30일',1],['tprv90','목표가90일',1],['gap','매출 가이던스 갭',1],['gapP','매출 가이던스 갭(포털)',1],['gapE','EPS 가이던스 갭',1],['gapEP','EPS 가이던스 갭(포털)',1],['r1','발표D+1',1],['r20','발표D+20',1],
        ['roe','ROE',1],['fcfy','FCF%',1],['de','부채비율',1]]
  };
  function cell2(r,c){const k=c[0];
    if(k==='n') return mkt==='kr'?`<b>${E(r.name)}</b> <span class="note">${E(r.code)}</span>`:`<b>${E(r.sym)}</b> <span class="note">${E(r.name)}</span>`;
    if(k==='rscore') return `<span class="z ${zClass(r.rscore)}">${zFmt(r.rscore)}</span>`;
    if(k.startsWith('z_')) return `<span class="z ${zClass(r[k])}">${zFmt(r[k])}</span>`;
    if(k==='divy'){const v=r.divy; return v==null?'—':(mkt==='us'&&v<1?(v*100).toFixed(2):(+v).toFixed(2));}
    if(k==='g_new'||k==='mom'){const v=r[k]; return v==null?'—':(v*100).toFixed(0)+'%';}
    if(k==='w52'){const v=r.w52; return v==null?'—':(+v).toFixed(0)+'%';}
    if(k==='near52'||k==='hi52'){const v=r[k]; return v==null?'—':'고점 '+(v*100).toFixed(0)+'%';}
    if(k==='vs200'){const v=r.vs200; return v==null?'—':(v>=0?'+':'')+(v*100).toFixed(0)+'%';}
    if(k==='rev'){const v=r.rev; return v==null?'—':`<span class="${v>0?'up':(v<0?'dn':'note')}">${v>0?'+':''}${(v*100).toFixed(1)}%</span>`;}
    /* (2026-08-09) 실적발표 3종 — 부호가 곧 의미라 색으로 즉시 구분되게 한다 */
    if(k==='cr30'){const v=r.cr30; return v==null?'—':`<span class="${v>0?'up':(v<0?'dn':'note')}">${v>0?'+':''}${(v*100).toFixed(1)}%</span>`;}
    if(k==='spr'||k==='sspr'||k==='gap'||k==='r1'||k==='r20'||k==='tprv'){const v=r[k];
      return v==null?'—':`<span class="${v>0?'up':(v<0?'dn':'note')}">${v>0?'+':''}${(+v).toFixed(1)}%</span>`;}
    if(k==='sprb'){const v=r.sprb; return v==null?'—':`<span class="${v>=3?'up':'note'}">${v}/${r.sprn||4}</span>`;}
    if(k==='roe'){const v=r.roe; return v==null?'—':(mkt==='kr'?(+v).toFixed(1):(v*100).toFixed(1))+'%';}
    if(k==='de'){const v=r.de; return v==null?'—':(+v).toFixed(0)+'%';}
    if(k==='fcfy'){const v=r.fcfy; return v==null?'—':(v*100).toFixed(1)+'%';}
    const v=r[k]; return v==null?'—':(+v).toFixed(1);
  }
  function rankTbl(){
    const nOn=AX.filter(a=>ON[a[0]]).length;
    let rows=S2[mkt].filter(pass).map(r=>{let sw=0,sz=0,n=0;
      for(const[k]of AX){ if(!ON[k])continue; const z=r['z_'+k]; if(z==null)continue; sw+=W[k]; sz+=W[k]*z; n++; }
      return Object.assign({},r,{rscore:(nOn>0&&n>=Math.min(3,nOn))?sz/sw:null});  // 축 3개↑면 최소3 유효, 그 이하면 켠 축 전부 필요
    });
    if(nOn===0 && (sort2.k==='rscore'||sort2.k.startsWith('z_'))) sort2.k='mcap';
    const sk=sort2.k, gv=r=> sk==='mcap'?(r.mcap??-Infinity):(r[sk]??-Infinity);
    rows.sort((a,b)=>sort2.d*(gv(a)-gv(b)));
    const nRank=rows.filter(r=>r.rscore!=null).length;
    const lim = topN>0 ? topN : rows.length;   // topN 0/빈값 = 전체
    const shown = Math.min(lim, 600, rows.length);   // 표시 상한 600행(성능)
    $('scr_cnt').innerHTML = nOn>0
      ? `1단계 <b>${rows.length}</b>종 <span style="opacity:.6">· z랭킹 ${nRank}종 · 표시 ${shown}${shown<rows.length?' (상한600)':''}</span>`
      : `<b>${rows.length}</b>종 <span style="opacity:.6">/ 전종목 ${S2[mkt].length} (1단계 필터+하드컷)</span>`;
    const cols=COL2[mkt], top=rows.slice(0, shown);
    $('scr_tbl2').innerHTML='<tr><th>#</th>'+cols.map(c=>`<th data-s2="${c[0]}" class="${sort2.k===c[0]?(sort2.d<0?'dn':'up'):''}">${E(c[1])}</th>`).join('')+'</tr>'+
      top.map((r,i)=>`<tr><td class="note">${i+1}</td>`+cols.map(c=>`<td class="${c[2]?'num':''} ${c[3]||''}">${cell2(r,c)}</td>`).join('')+'</tr>').join('');
    $('scr_tbl2').querySelectorAll('[data-s2]').forEach(th=>th.onclick=()=>{
      const k=th.dataset.s2; if(sort2.k===k)sort2.d*=-1; else{sort2.k=k;sort2.d=-1;} rankTbl(); });
  }
  /* (2026-07-26) 캘린더(다른 IIFE)에서 풀 데이터 접근용 브리지 — 어닝 월간 달력 */
  window.nmrPool=cb=>loadS2(()=>cb(POOL));
  function loadS2(cb){
    if(s2loaded){cb&&cb();return;}
    // 2단계도 1단계와 같은 전종목 풀(z점수 포함)을 쓴다 — 1단계 필터를 거친 뒤 랭킹(퍼널).
    if(POOL.kr.length||POOL.us.length){ S2=POOL; s2loaded=true; cb&&cb(); return; }
    fetch('/api/db/screener_pool').then(r=>r.json()).then(d=>{
      d=d||{}; POOL={kr:d.kr||[],us:d.us||[]}; loadSecMap(); S2=POOL; s2loaded=true; cb&&cb();
    }).catch(()=>{ S2={kr:[],us:[]}; s2loaded=true; cb&&cb(); });
  }

  let stage=1;
  // ── 3단계 실측 팩터카드 + 분석요청 ──
  let topN3=30;
  function loadS3(cb){ if(POOL.kr.length||POOL.us.length){ S2=POOL; cb&&cb(); return; } loadS2(cb); }
  function rankCards3(){
    const nOn=AX.filter(a=>ON[a[0]]).length;
    let rows=POOL[mkt].filter(pass).filter(pass2).map(r=>{let sw=0,sz=0,n=0;
      for(const[k]of AX){ if(!ON[k])continue; const z=r['z_'+k]; if(z==null)continue; sw+=W[k];sz+=W[k]*z;n++; }
      return Object.assign({},r,{rscore:(nOn>0&&n>=Math.min(3,nOn))?sz/sw:null});
    }).filter(r=>r.rscore!=null);
    rows.sort((a,b)=>b.rscore-a.rscore);
    const top=rows.slice(0, Math.max(1,topN3||30));
    window.__scr_top3=top.map(r=>r.c);
    $('scr_cnt3').innerHTML=`1·2단계 통과 <b>${rows.length}</b>종 → TOP <b>${top.length}</b> 팩터카드`;
    const isk=mkt==='kr';
    const chip=(l,z)=> z==null?`<span>${l} —</span>`:`<span class="${zClass(z)}">${l} ${z>0?'+':''}${z.toFixed(2)}</span>`;
    const P=(v,d)=>v==null?'—':(v>0?'+':'')+(v*100).toFixed(d==null?0:d)+'%';
    $('scr_cards').innerHTML=top.map((r,i)=>{
      const roe=r.roe==null?'—':(isk?r.roe.toFixed(1):(r.roe*100).toFixed(1))+'%';
      const de=r.de==null?'—':r.de.toFixed(0)+'%';
      const cr=r.cr==null?'—':r.cr.toFixed(1);
      const per=isk?(r.fper==null?'—':(+r.fper).toFixed(1)):(r.fpe==null?'—':(+r.fpe).toFixed(1));
      const pbr=isk?(r.pbr==null?'—':(+r.pbr).toFixed(1)):(r.pb==null?'—':(+r.pb).toFixed(1));
      const div=r.divy==null?'—':(isk?(+r.divy).toFixed(1):(r.divy*100).toFixed(1))+'%';
      const lastLbl=isk?'영익YoY':'FCF수익', lastVal=isk?P(r.opg,0):P(r.fcfy,1);
      return `<div class="fcard"><div class="fh"><b>${E(isk?r.n:r.c)}</b> <span class="cd">${E(isk?r.c:r.n)}</span><span class="sc ${zClass(r.rscore)}">${r.rscore>0?'+':''}${r.rscore.toFixed(2)}</span></div>
        <div class="fz">${chip('V',r.z_val)}${chip('G',r.z_grw)}${chip('M',r.z_mom)}${chip('Q',r.z_qly)}</div>
        <div class="fm"><span>PER <b>${per}</b></span><span>PBR <b>${pbr}</b></span><span>배당 <b>${div}</b></span>
          <span>ROE <b>${roe}</b></span><span>부채 <b>${de}</b></span><span>유동 <b>${cr}</b></span>
          <span>매출YoY <b>${P(r.revg,0)}</b></span><span>${lastLbl} <b>${lastVal}</b></span><span>#${i+1}</span></div></div>`;
    }).join('') || '<div class="note" style="grid-column:1/-1">통과 종목 없음 — 1·2단계 필터를 완화하세요</div>';
  }
  function renderS3(){ rankCards3(); }

  function refresh(){ if(stage===1) apply(); else if(stage===2) renderS2(); else renderS3(); }

  // ── 스크리너 상태 저장·복원 (새로고침에도 필터 유지) ──
  function saveScr(){ try{
    sessionStorage.setItem('nmr_scr', JSON.stringify({mkt,stage,topN,topN3,sort,sort2,F_ST,F2_ST,W,ON}));
  }catch(e){} }
  function restoreScr(){ try{
    const d=JSON.parse(sessionStorage.getItem('nmr_scr')||'null'); if(!d) return false;
    if(d.mkt) mkt=d.mkt; if(d.stage) stage=d.stage;
    if(typeof d.topN==='number') topN=d.topN; if(typeof d.topN3==='number') topN3=d.topN3;
    if(d.sort) sort=d.sort; if(d.sort2) sort2=d.sort2;
    if(d.F_ST) Object.assign(F_ST,d.F_ST); if(d.F2_ST) Object.assign(F2_ST,d.F2_ST);
    if(d.W) W=d.W; if(d.ON) ON=d.ON;   // 컬럼 구성은 localStorage(loadCols)에서 별도 복원
    return true;
  }catch(e){ return false; } }
  function applyRestored(){
    document.querySelectorAll('#p_screener .mktseg:not(.stgseg) .mkt').forEach(x=>x.classList.toggle('on',x.dataset.mkt===mkt));
    document.querySelectorAll('.stgseg .stg').forEach(x=>x.classList.toggle('on',+x.dataset.stg===stage));
    $('scr_s1').style.display = stage===1?'':'none';
    $('scr_s2').style.display = stage===2?'':'none';
    $('scr_s3').style.display = stage===3?'':'none';
    placeBtns();
    loadF(); loadF2();
    if(stage===2) loadS2(()=>renderS2());
    else if(stage===3) loadS3(()=>renderS3());
    else apply();
  }
  window.addEventListener('beforeunload', saveScr);

  let prepped=false;
  /* 풀 머리말 — 장중이면 ⚡LIVE, 장외면 '왜 안 움직이는지'와 다음 갱신 시각을 밝힌다.
     (수집 시각만 덩그러니 있으면 갱신이 고장 난 것처럼 보인다) */
  function poolMeta(d){
    const E2=s=>E(s==null?'':s);
    /* (2026-08-09) live_at 신선도 검사 — 장마감 후 서버가 못 지운 값이 남으면
       주말에도 'LIVE' 로 보인다(실측: 금 장마감값이 일요일까지 표시). 15분 넘으면 장마감 취급. */
    let liveFresh=false;
    if(d.live_at){
      const m=/(\d\d)-(\d\d) (\d\d):(\d\d)( ET)?/.exec(d.live_at);
      if(m){
        try{
          const tz=m[5]?'America/New_York':'Asia/Seoul';
          const nowTz=new Date(new Date().toLocaleString('en-US',{timeZone:tz}));
          const tt=new Date(nowTz); tt.setMonth(+m[1]-1,+m[2]); tt.setHours(+m[3],+m[4],0,0);
          if(tt-nowTz>36e5) tt.setFullYear(tt.getFullYear()-1);   // 연초 경계
          const age=nowTz-tt;
          liveFresh=(age>-36e5 && age<15*60000);
        }catch(e){ liveFresh=true; }
      } else liveFresh=true;
    }
    let tail;
    if(d.live_at&&liveFresh){
      tail = ` · <b style="color:#1f6feb">⚡LIVE ${E2(d.live_at)}</b> <span class="note">· 장중 자동갱신 KR 1분·US 3분(시간외 포함)</span>`;
    }else if(d.live_at){
      tail = ` · <span style="color:var(--tx2)">장마감 (마지막 장중 갱신 ${E2(d.live_at)} · 장중에만 자동갱신)</span>`;
    }else{
      // 브라우저 시간대와 무관하게 KST 로 환산해 판단
      const k=new Date(Date.now()+(9*60+new Date().getTimezoneOffset())*60000);
      const wd=k.getDay(), hm=k.getHours()*60+k.getMinutes();
      const krOpen = wd>=1&&wd<=5 && hm>=540 && hm<=930;              // 09:00~15:30
      const usOpen = ((wd>=1&&wd<=5&&hm>=1350)||(wd>=2&&wd<=6&&hm<=360)); // 22:30~06:00
      let nxt;
      if(wd===6)      nxt='월 09:00 한국장';
      else if(wd===0) nxt='월 09:00 한국장';
      else if(hm<540) nxt='오늘 09:00 한국장';
      else if(hm<=930)nxt='';
      else if(hm<1350)nxt=(wd===5?'월 09:00 한국장':'오늘 22:30 미국장');
      else            nxt='';
      tail = (krOpen||usOpen)
        ? ' · <b style="color:#b7791f">장중인데 아직 갱신 전 — 5분 내 반영</b>'
        : ` · <span style="color:var(--tx2)">장마감 (장중에만 5분마다 갱신${nxt?' · 다음 '+nxt:''})</span>`;
    }
    return `기준일 <b>${E2(d.price_date||'—')}</b> · 전종목 풀 한국 ${POOL.kr.length.toLocaleString()}`
         + ` · 미국 ${POOL.us.length.toLocaleString()} · 수집 ${E2(d.asof||'')}${tail}`;
  }

  function loadPool(then){                    // 전종목 풀 로드 (START 눌렀을 때만)
    if(loaded){ then&&then(); return; }
    const gb=$('scr_start');
    if(gb){gb.disabled=true; gb.textContent='불러오는 중…';}
    $('scr_asof').textContent='전종목 풀 불러오는 중…';
    fetch('/api/db/screener_pool').then(r=>r.json()).then(d=>{
      d=d||{}; POOL={kr:d.kr||[],us:d.us||[]}; loaded=true; loadSecMap();
      loadDrvSc();                            // (2026-07-24) 파생·수급판정 점수 소스 (도착하면 refresh)
      $('scr_asof').innerHTML=poolMeta(d);
      {const _e=$('scr_src2'); if(_e) _e.innerHTML='출처: KRX OPEN API + 네이버 전종목 시세 · Yahoo v7(미국) · 하루 2회 갱신.';}
      if(gb){gb.disabled=false; gb.textContent='▶ START';}
      then&&then();
    }).catch(e=>{ $('scr_asof').textContent='풀 로드 실패: '+e;
      if(gb){gb.disabled=false; gb.textContent='▶ START';} });
  }
  function waitScreen(){                      // START 전 대기 화면 (필터는 미리 조정 가능)
    hideDetail();
    $('scr_asof').innerHTML='<b>START</b>를 누르면 전종목 풀을 불러와 필터를 적용합니다.';
    $('scr_cnt').innerHTML='<span style="opacity:.55">대기 중</span>';
    const msg='필터를 설정한 뒤 <b>▶ START</b> 버튼을 누르세요.';
    const row=`<tr><td class="note" style="text-align:center;padding:30px">${msg}</td></tr>`;
    for(const id of ['scr_tbl','scr_tbl2']){ const t=$(id); if(t) t.innerHTML=row; }
    const c=$('scr_cards'); if(c) c.innerHTML=`<div class="note" style="grid-column:1/-1;text-align:center;padding:30px">${msg}</div>`;
  }
  window.renderScreener=function(){
    if(loaded){ refresh(); return; }
    if(!prepped){ prepped=true;
      if(!restoreScr()) resetF();
      loadF(); loadF2();
      document.querySelectorAll('#p_screener .mktseg:not(.stgseg) .mkt').forEach(x=>x.classList.toggle('on',x.dataset.mkt===mkt));
      document.querySelectorAll('.stgseg .stg').forEach(x=>x.classList.toggle('on',+x.dataset.stg===stage));
      $('scr_s1').style.display = stage===1?'':'none';   // 복원된 단계 pane 표시
      $('scr_s2').style.display = stage===2?'':'none';
      $('scr_s3').style.display = stage===3?'':'none';
    }
    renderChips(); waitScreen();
  };
  /* (2026-07-20) 관리자 수동 즉시 갱신 — 로그인 상태에서 로드 후 START 재클릭 시 서버 강제 refresh */
  let scrAdmin=false, scrRefreshing=false;
  fetch('/api/auth/me').then(r=>r.json()).then(d=>{ scrAdmin=!!(d&&d.ok); }).catch(()=>{});
  async function scrForceRefresh(){
    if(scrRefreshing) return; scrRefreshing=true;
    const gb=$('scr_start');
    let prevLive=null; try{ const d0=await (await fetch('/api/db/screener_pool')).json(); prevLive=d0.live_at||null; }catch(e){}
    if(gb){ gb.disabled=true; gb.textContent='⏳ 갱신 요청…'; }
    let r; try{ r=await (await fetch('/api/admin/refresh/screener',{method:'POST'})).json(); }catch(e){ r=null; }
    if(!r || (!r.started && !r.busy)){ if(gb){gb.disabled=false; gb.textContent='▶ START';} scrRefreshing=false; return; }
    if(gb) gb.textContent='⏳ 갱신 중…';
    for(let i=0;i<20;i++){
      await new Promise(x=>setTimeout(x,2000));
      try{ const d=await (await fetch('/api/db/screener_pool')).json();
        if(d && d.live_at && d.live_at!==prevLive){
          POOL={kr:d.kr||[],us:d.us||[]}; mergeSec(); if(s2loaded) S2=POOL; $('scr_asof').innerHTML=poolMeta(d); refresh(); break; }
      }catch(e){}
    }
    if(gb){ gb.disabled=false; gb.textContent='▶ START'; }
    scrRefreshing=false;
  }
  {const gb=$('scr_start'); if(gb) gb.onclick=()=>{
     if(!loaded){ loadPool(()=>applyRestored()); return; }
     if(scrAdmin){ scrForceRefresh(); } else { refresh(); }   // 비관리자: 필터 재적용(기존 동작)
   };}
  /* (2026-07-20) 종목 스크리너 진입 시 START 자동 실행 — 매번 누를 필요 없이 바로 결과가 보이게. */
  {const sb=$('btn_screener');
   if(sb) sb.addEventListener('click',()=>{ if(!loaded) setTimeout(()=>{ if(!loaded) loadPool(()=>applyRestored()); },60); });}
  setTimeout(()=>{ const p=$('p_screener')||document.querySelector('.pane.scr');
    if(!loaded && p && p.classList.contains('on')) loadPool(()=>applyRestored()); }, 400);
  {const cb=$('scr_colbtn'); if(cb) cb.onclick=()=>toggleColPanel();}
  /* (2026-07-22) 자동이동 토글 */
  {const ab=$('scr_autoscroll'); if(ab){
    const paint=()=>{ ab.textContent='⤓ 자동이동: '+(autoScroll?'ON':'OFF');
      ab.style.color=autoScroll?'#1f6feb':'var(--tx2)'; ab.style.borderColor=autoScroll?'#1f6feb':'var(--line)'; ab.style.fontWeight=autoScroll?'600':'400'; };
    paint(); ab.onclick=()=>{ autoScroll=!autoScroll; localStorage.setItem('scr_autoscroll',autoScroll?'1':'0'); paint(); }; }}
  /* (2026-07-22) 결과표 표시 행수 */
  {const rn=$('scr_rows'); if(rn){ rn.value=visRows;
    const setRows=(v,writeInput)=>{ visRows=Math.max(1,Math.min(60,v)); if(writeInput) rn.value=visRows; localStorage.setItem('scr_visrows',visRows); applyTblHeight(); };
    rn.oninput=()=>setRows(+rn.value||8, false);   // 타이핑 중엔 input 을 덮어쓰지 않음(두 자리 입력 유지)
    const up=$('scr_rowsup'), dn=$('scr_rowsdn');
    if(up) up.onclick=()=>setRows(visRows+1, true);
    if(dn) dn.onclick=()=>setRows(visRows-1, true);
  }}
  {const gb=$('scr_glsbtn'), gp=$('scr_glspanel'), gx=$('gls_close');
   if(gb&&gp) gb.onclick=()=>{ const opening=gp.style.display==='none'; gp.style.display=opening?'':'none'; if(opening) renderLegend(); };  // START 전에도 설명 렌더
   if(gx&&gp) gx.onclick=()=>{ gp.style.display='none'; };}
  /* (2026-08-14) 서버 자가진단 배지 — health.json(2시간마다 갱신) 경보를 헤더에 노출 */
  (async function health(){
    try{
      const h=await (await fetch('/api/db/health',{cache:'no-cache'})).json();
      const hdr=document.querySelector('.hdr-r'); if(!hdr||!h) return;
      const el=document.createElement('button');
      el.className='hbtn'; el.style.cursor='help';
      el.style.color = h.ok ? '#1e9e6a' : '#d64545';
      el.style.borderColor = h.ok ? '#bfe6d4' : '#f0c2c2';
      el.textContent = h.ok ? '● 정상' : `▲ 경보 ${h.alerts.length}`;
      const c=h.checks||{}, r=c.resource||{};
      el.title = (h.ok?'서버 자가진단 정상':'경보:\n- '+h.alerts.join('\n- '))
        + `\n\n번들 ${c.bundle_mb}MB · 가용메모리 ${r.mem_avail_mb}MB · 디스크 ${r.disk_used_pct}%\n점검 ${h.as_of}`;
      hdr.insertBefore(el, hdr.firstChild);
    }catch(e){}
  })();
  /* 우측 자료 서랍(보고서·APK·DB 인벤토리) 토글 */
  {const t=document.getElementById('side_tgl'), sd=document.querySelector('aside.side'), x=document.getElementById('side_x');
   const sync=()=>document.body.classList.toggle('side-open', sd.classList.contains('open')); // 본문 동적 축소 연동
   if(t&&sd) t.onclick=()=>{ sd.classList.toggle('open'); sync(); };
   if(x&&sd) x.onclick=()=>{ sd.classList.remove('open'); sync(); };}
  /* 장중 LIVE: 서버 증분(KR 1분·US 3분) 갱신 풀을 1분마다 자동 재조회(ETag 304면 무비용) */
  setInterval(()=>{
    if(!loaded) return;
    const p=document.getElementById('p_screener');
    if(!p || !p.classList.contains('on') || document.visibilityState!=='visible') return;
    fetch('/api/db/screener_pool').then(r=>r.json()).then(d=>{
      if(!d||!d.kr||!d.kr.length) return;
      POOL={kr:d.kr||[],us:d.us||[]}; mergeSec(); if(s2loaded) S2=POOL;
      $('scr_asof').innerHTML=poolMeta(d);
      /* (2026-08-09) 종목 상세를 열어 아래쪽을 보고 있으면 표를 다시 그리지 않는다.
         재렌더 순간 표가 무너졌다 다시 커지며 스크롤이 클램프돼 위로 튀는데, 값 복원만으로는
         (차트·실적표가 비동기로 도착해 높이를 또 바꾸므로) 완전히 막지 못했다.
         데이터(POOL)는 이미 갱신했으므로 상세를 닫을 때 반영된다. */
      {const dv=$('scr_detail');
       if(dv && dv.style.display!=='none') return;}
      /* (2026-07-24) 자동 갱신이 표·칩을 다시 그리며 스크롤이 최상단으로 튀는 문제 —
         갱신 전 위치(페이지 + 표 내부)를 저장했다가 복원.
         (2026-08-09 보강) 2프레임 복원으로는 부족했다 — 종목 상세가 열려 있으면 기업개요·
         실적표·매출구성 등이 **비동기로 도착해 나중에 높이를 바꾸므로** 그 뒤에 다시 튄다.
         → 1.2초 동안 매 프레임 복원하되, 사용자가 직접 스크롤하면 즉시 중단한다. */
      const sy=window.scrollY, sx=window.scrollX, tw=$('scr_tblwrap'), ts=tw?tw.scrollTop:0;
      refresh();
      let last=sy, t0=performance.now(), stop=false;
      const onUser=()=>{ if(Math.abs(window.scrollY-last)>2) stop=true; };
      ['wheel','touchmove','keydown','mousedown'].forEach(ev=>window.addEventListener(ev,()=>{stop=true;},{once:true,passive:true}));
      const back=()=>{ if(stop) return;
        if(window.scrollY!==sy){ window.scrollTo(sx,sy); last=window.scrollY; }
        if(tw&&tw.scrollTop!==ts) tw.scrollTop=ts;
        if(performance.now()-t0<1200) requestAnimationFrame(back); };
      back(); onUser();
    }).catch(()=>{});
  }, 60000);
  document.addEventListener('click',e=>{ if(!e.target.closest('.fchip')) document.querySelectorAll('.fpop').forEach(x=>x.classList.remove('open')); });
  // 마켓 토글
  document.querySelectorAll('#p_screener .mktseg:not(.stgseg) .mkt').forEach(b=>b.onclick=()=>{
    document.querySelectorAll('#p_screener .mktseg:not(.stgseg) .mkt').forEach(x=>x.classList.toggle('on',x===b));
    mkt=b.dataset.mkt; loadF(); loadF2(); hideDetail();
    if(loaded) refresh(); else { renderChips(); waitScreen(); } renderLegend(); });   // 원복 안함 — 마켓별 선택 유지 · 설명도 시장 따라 갱신
  // 스테이지 토글 (1단계/2단계)
  document.querySelectorAll('.stgseg .stg').forEach(b=>b.onclick=()=>{
    document.querySelectorAll('.stgseg .stg').forEach(x=>x.classList.toggle('on',x===b));
    stage=+b.dataset.stg;
    $('scr_s1').style.display = stage===1?'':'none';
    $('scr_s2').style.display = stage===2?'':'none';
    $('scr_s3').style.display = stage===3?'':'none';
    placeBtns();
    if(!loaded){ renderChips(); waitScreen(); renderLegend(); return; }   // START 전에는 대기 화면 유지(설명은 갱신)
    if(stage===2) loadS2(()=>renderS2());
    else if(stage===3) loadS3(()=>renderS3());
    else apply();
  });
  {const rb=$('scr_rst'); if(rb) rb.onclick=()=>{ if(stage===1){sort={k:'cap',d:-1};resetF();apply();} else if(stage===2){resetW();renderS2();} else {resetW();renderS3();} };}
  /* (2026-08-04) 🔥 개장서지 프리셋 — "장 시작하며 거래량 터지며 급등" 실시간 포착.
     핵심: 등락 +5%↑ + 거래량배수 3배↑ (풀이 장중 KR 1분·US 3분 갱신이라 실시간 추적)
     잡음 배제: 거래대금(KR 100억/US $20M)↑ · 시총(KR 1,000억/US $300M)↑ · 상장 1년↑(신규상장 왜곡 제외)
     결과는 등락률 내림차순. 추가로 볼 만한 조합(수동): 고점比 -10% 이내=신고가 돌파형 ·
     공매도비중 ↑=숏스퀴즈 후보 · 어닝일 D+1~D+7=실적 서프라이즈 추격 */
  function _surgeBase(){                               // 서지 공통 조건 적용 후 set 함수 반환
    const d=DEF[mkt];
    for(const k in d){ const f=d[k]; if(!f||f.fixed!==undefined) continue;
      F[k]= f.tgl? {on:false} : f.cat? {v:null} : {min:null,max:null}; }   // 전부 '전체'로
    const set=(k,st)=>{ if(d[k]&&d[k].fixed===undefined) F[k]=st; };
    set('chg',{min:5,max:null});                       // 등락 +5% ↑
    set('volx',{min:3,max:null});                      // 거래량배수 3배 ↑
    set('tv',{min:mkt==='kr'?1e10:2e7,max:null});      // 거래대금 100억 / $20M ↑
    set('cap',{min:mkt==='kr'?1e11:3e8,max:null});     // 시총 1,000억 / $300M ↑
    set('age',{min:1,max:null});                       // 상장 1년 ↑
    sort={k:'chg',d:-1};                               // 등락률 높은 순
    return set;
  }
  {const sg=$('scr_surge'); if(sg) sg.onclick=()=>{ if(stage!==1) return; _surgeBase(); apply(); };}
  /* (2026-08-04) 서지 변형 3종 — 개장서지 + 추가 조건 하나씩 */
  {const b=$('scr_surge_hi'); if(b) b.onclick=()=>{ if(stage!==1) return;
    const set=_surgeBase();
    set('hi',{min:-10,max:null});                      // 고점比 -10% 이내 — 52주 신고가 돌파형
    apply(); };}
  {const b=$('scr_surge_sq'); if(b) b.onclick=()=>{ if(stage!==1) return;
    const set=_surgeBase();
    if(mkt==='kr') set('sr',{min:5,max:null});         // KR 공매도비중 5% ↑ (과열)
    else set('srf',{min:10,max:null});                 // US 공매도잔량/유통주식 10% ↑ (과열)
    apply(); };}
  {const b=$('scr_surge_ern'); if(b) b.onclick=()=>{ if(stage!==1) return;
    const set=_surgeBase();
    set('ern',{min:-7,max:-1});                        // 어닝 D+1~D+7 — 실적 발표 직후
    apply(); };}
  /* (2026-08-27) 📈 이익성장 상위 — '영업이익 성장률 상위 매수'가 매출·순이익 성장보다
     고수익이었다는 백테스트(2016~26 · KR +645% · US +466%, 토스 콘텐츠)를 실전형으로 보정.
     원문 방법(성장률 상위 10% 단순 매수)의 세 함정을 필터로 막는다:
       ① 저기저 왜곡 — 전년 이익 1억→10억이 +900%로 최상위에 온다
          → 영업이익률 5%↑(마진 있는 성장만) + [US] 정렬을 성장률이 아니라 **리비전순**으로
            (실측: 성장률 정렬 시 TWLO +4,671% 같은 저기저가 상위 독식)
       ② 일회성 반등 — 성장가속 0%p↑(직전 분기보다 성장률이 더 높아야)
       ③ 지속 확인 없음 — [US] 컨센 리비전 30일↑ + 직전 서프라이즈↑(애널·실적이 추인 중)
     (2026-08-27 2차 · 사용자 확정) 정렬은 KR·US 모두 **성장률순**으로 통일하고,
     저기저는 정렬 우회가 아니라 **PEG 하한(0.3↑)** 으로 정면 배제한다 — 성장이 진짜면
     시장이 PER 로 값을 매기므로, 성장 +4,671%에 PEG 0.01 이라는 건 시장이 그 성장률을
     믿지 않는다는 뜻이다(실측: PEG 0.3↑ 만으로 저기저 반등주 전멸, 상위가 PLTR +215% ·
     PWR +94% 같은 진짜 성장주로 교체 · 171→66종). KR 도 소수만 남아도 전 조건을 컷한다
     (사용자 확정 — 목표가 리비전 90일↑ + 서프↑ 복원, 실측 3종: 에이피알·고영·코스메카).
     분기 리밸런싱 전제. 실측 통과: KR 3종 · US 66종. */
  {const b=$('scr_opg'); if(b) b.onclick=()=>{ if(stage!==1) return;
    const d=DEF[mkt];
    for(const k in d){ const f=d[k]; if(!f||f.fixed!==undefined) continue;
      F[k]= f.tgl? {on:false} : f.cat? {v:null} : {min:null,max:null}; }
    const set=(k,st)=>{ if(d[k]&&d[k].fixed===undefined) F[k]=st; };
    set('ogrw',{min:30,max:null});                     // 이익성장 +30% ↑ (KR=영업익 · US=EPS)
    set('opm',{min:5,max:null});                       // 영업이익률 5% ↑ — 저기저 왜곡 차단
    set('gacc',{min:0,max:null});                      // 성장가속 0%p ↑ — 일회성 반등 배제
    if(mkt==='kr'){
      set('opLoss',{min:null,max:1});                  // 영업적자 1년이상 제외
      set('tprv90',{min:0,max:null});                  // 목표가 리비전 ↑ — 애널리스트 추인
      set('spr',{min:0,max:null});                     // 영업익 서프라이즈 ↑
      set('cap',{min:3e11,max:null});                  // 시총 3,000억 ↑
      set('tv',{min:1e9,max:null});                    // 거래대금 10억 ↑
    }else{
      set('peg',{min:0.3,max:null});                   // PEG 0.3 ↑ — 저기저 반등주 배제
      set('cr30',{min:0,max:null});                    // 컨센 리비전 30일 ↑ — 지속 확인
      set('spr',{min:0,max:null});                     // 직전 서프라이즈 ↑
      set('cap',{min:2e9,max:null});                   // 시총 $2B ↑
      set('tv',{min:2e7,max:null});                    // 거래대금 $20M ↑
    }
    sort={k:'opg',d:-1};                               // 성장률순 (2026-08-27 사용자 확정)
    apply(); };}
  /* (2026-08-05) 🎁 배당선취 (KR 전용) — 8~9월 연말 배당 선취 전략.
     고배당(4~12% — 12% 초과는 주가 폭락 역산/특별배당 '배당 함정' 배제)
     + 지속성(배당성향 20~60% — 상한이 핵심: 이익 일부만 배당해야 매년 지킬 체력)
     + 이익 방어력(영업이익성장 0%↑ · 영업적자 1년이상 제외 · ROE 5%↑ — 배당락 후 회복력)
     + 안정성(부채 150%↓ · 변동성 2.5%↓ · 시총 3,000억↑ · 거래대금 10억↑). 배당률 높은 순.
     ※ (2026-08-06) DPS 이력(DART 5개년) 확보 — 'DPS 1년 연속↑' 기본 포함, 더 엄격히는 칩에서 2·3년↑ 선택 */
  {const b=$('scr_divp'); if(b) b.onclick=()=>{ if(stage!==1) return;
    if(mkt!=='kr'){ alert('배당선취 프리셋은 한국 전용입니다 (연말 일괄 배당 구조 전제)'); return; }
    const d=DEF[mkt];
    for(const k in d){ const f=d[k]; if(!f||f.fixed!==undefined) continue;
      F[k]= f.tgl? {on:false} : f.cat? {v:null} : {min:null,max:null}; }
    const set=(k,st)=>{ if(d[k]&&d[k].fixed===undefined) F[k]=st; };
    set('divy',{min:4,max:12});        // 배당 4~12% (함정 상한)
    set('dinc',{min:1,max:null});      // (2026-08-06) DPS 1년 연속↑ 기본 포함 — '작년보다 배당 늘린 회사'만 (3년↑은 2종뿐이라 과속)
    set('payout',{min:20,max:60});     // 배당성향 20~60% (지속 가능 체력)
    set('opg',{min:0,max:null});       // 영업이익성장 + (배당락 후 회복력)
    set('opLoss',{min:null,max:1});    // 영업적자 1년이상 제외
    set('roe',{min:5,max:null});       // ROE 5% ↑
    set('de',{min:null,max:150});      // 부채비율 150% ↓
    set('vol20',{min:null,max:2.5});   // 변동성 낮음 (배당주 안정성)
    set('cap',{min:3e11,max:null});    // 시총 3,000억 ↑
    set('tv',{min:1e9,max:null});      // 거래대금 10억 ↑
    sort={k:'divy',d:-1};              // 배당률 높은 순
    apply(); };}
  /* (2026-08-06) US 배당 3종 프리셋 — div_hist_us(야후 30y 배당 이벤트) 기반.
     공통 사상: '사놓고 잊는' 배당 — 성장연수(감액 이력 없음)·성향 상한(증가 여력)·폭락 이력(MDD)·대형주. */
  const _usDivBase=(d)=>{ for(const k in d){ const f=d[k]; if(!f||f.fixed!==undefined) continue;
    F[k]= f.tgl? {on:false} : f.cat? {v:null} : {min:null,max:null}; } };
  // 🏛️ 배당귀족 — 20년↑ 연속 증가(귀족급) + 초대형 + 저변동. 가장 보수적.
  {const b=$('scr_darist'); if(b) b.onclick=()=>{ if(stage!==1) return;
    if(mkt!=='us'){ alert('배당귀족 프리셋은 미국 전용입니다 (KR은 배당선취 사용)'); return; }
    const d=DEF[mkt]; _usDivBase(d);
    const set=(k,st)=>{ if(d[k]&&d[k].fixed===undefined) F[k]=st; };
    set('dgy',{min:20,max:null});      // 20년 연속 증가 (야후 이력 한계 감안 — 귀족(25년)급)
    set('divy',{min:1.5,max:8});       // 배당 1.5~8% (극단 함정 배제)
    set('payout',{min:null,max:70});   // 성향 70% ↓ — 증가 여력
    set('cap',{min:1e10,max:null});    // 시총 $10B ↑
    set('mdd5',{min:-40,max:null});    // 5년 낙폭 -40% 이내
    set('vol20',{min:null,max:3});     // 저변동
    sort={k:'dgy',d:-1};               // 성장연수 긴 순
    apply(); };}
  // 📈 배당성장 — 10년↑(Achievers) + 이익성장 병행. 배당·성장 균형.
  {const b=$('scr_dgrow'); if(b) b.onclick=()=>{ if(stage!==1) return;
    if(mkt!=='us'){ alert('배당성장 프리셋은 미국 전용입니다'); return; }
    const d=DEF[mkt]; _usDivBase(d);
    const set=(k,st)=>{ if(d[k]&&d[k].fixed===undefined) F[k]=st; };
    set('dgy',{min:10,max:null});      // 10년 연속 증가 (Achievers)
    set('divy',{min:1.5,max:8});
    set('payout',{min:null,max:70});
    set('grw',{min:0,max:null});       // 이익성장 +
    set('cap',{min:2e9,max:null});     // $2B ↑
    set('mdd5',{min:-50,max:null});
    sort={k:'divy',d:-1};
    apply(); };}
  // 📅 월현금흐름 — 매월 배당 수령 설계: 월배당 종목 또는 지급월 그룹(1·4·7·10 / 2·5·8·11 / 3·6·9·12)별
  //    1종목씩 3종목 조합. 프리셋은 후보군(고배당·지속·저낙폭)을 깔고 '배당주기' 칩에서 그룹 선택.
  {const b=$('scr_dcal'); if(b) b.onclick=()=>{ if(stage!==1) return;
    if(mkt!=='us'){ alert('월현금흐름 프리셋은 미국 전용입니다'); return; }
    const d=DEF[mkt]; _usDivBase(d);
    const set=(k,st)=>{ if(d[k]&&d[k].fixed===undefined) F[k]=st; };
    set('divy',{min:3,max:12});        // 고배당 3~12%
    set('dgy',{min:1,max:null});       // 최소 작년보다 증가 (감액 함정 배제)
    set('payout',{min:null,max:80});
    set('cap',{min:2e9,max:null});
    set('mdd5',{min:-45,max:null});
    sort={k:'divy',d:-1};
    apply(); };}
  /* (2026-08-10) 한국 전망 축 자동 전환 — 지금은 영업익추정 리비전 스냅샷(kr_consensus)이
     30일치가 안 쌓여 목표주가 리비전 30일(tprv)로 대신한다. 2026-09-08 부터 30일 리비전이
     유효해지므로 그날부터 자동으로 cr30 을 쓴다(사용자 승인 · 수동 수정 불필요).
     실제 데이터가 비어 있으면 문턱을 걸어도 전부 탈락하므로 날짜와 값 존재를 함께 본다. */
  const _KRREV=()=>{
    const ok=new Date()>=new Date('2026-09-08T00:00:00');
    const has=(POOL&&POOL.kr||[]).some(r=>r.cr30!=null);
    return (ok&&has)?'cr30':'tprv';
  };
  /* (2026-08-09) 📈 어닝드리프트(PEAD) — 학계에서 반복 검증된 이례현상.
     컨센을 이긴 종목의 주가는 발표 당일에 다 반영되지 않고 수 주간 같은 방향으로 흐른다.
     그래서 '이겼고 + 추정치도 올라갔는데 + 아직 안 오른' 교집합을 초기 진입 후보로 본다. */
  {const b=$('scr_pead'); if(b) b.onclick=()=>{ if(stage!==1) return;
    /* (2026-08-09) '전부 전체'가 아니라 **기본 하드컷(default) 위에** 조건을 얹는다.
       전부 비우면 저가주·적자기업·초소형주까지 들어와 후보가 지저분해지고,
       직전에 손으로 만져둔 값이 남아 결과가 들쭉날쭉해진다(가이던스갭이 남아 3종만 나온 사례). */
    resetF(); F=F_ST[mkt];
    const d=DEF[mkt];
    const set=(k,st)=>{ if(d[k]&&d[k].fixed===undefined) F[k]=st; };
    /* (2026-08-09 사용자 세팅 반영) 실적·전망이 **모두** 좋은데 주가만 아직 안 오른 교집합.
       서프라이즈 하나만 보면 '이번에만 잘한' 종목과 가이던스가 나빠 이미 꺾인 종목이
       섞여 들어와 PEAD 후보로서 신뢰가 떨어진다. 가이던스쇼크와 같은 축을 쓰되
       주가 조건만 반대(아직 안 올랐다)로 둔다. */
    set('spr',{min:5,max:null});        // 실적: 컨센을 뚜렷하게 상회
    set('sprb',{min:4,max:null});       // 실적: 최근 4분기 전부 상회 = 꾸준히 이기는 회사
    /* (2026-08-10) 매출도 함께 이겼는지 — EPS 는 비용절감·자사주매입으로 만들 수 있지만
       매출은 못 꾸민다. '매출 미스인데 EPS 만 비트'인 가짜 비트를 제거한다. */
    set('sspr',{min:0,max:null});
    /* 전망 개선 확인 — 미국은 이익추정 리비전, 한국은 스냅샷 30일이 쌓이기 전까지
       증권사 목표주가 리비전으로 대신한다(같은 '전망이 올라갔나' 축). */
    /* (2026-08-10) 리비전은 **7일**을 쓴다 — 이 전략은 발표 후 7일 이내 종목만 보는데
       30일 리비전은 발표 전 변화까지 섞여 시간 축이 어긋난다. 7일 = '발표를 보고
       애널리스트가 실제로 올렸나'. gap = 매출 가이던스 갭(실전 우선순위 ①).
       ※ 가이던스는 보도자료에 숫자를 싣는 회사가 소수(실측 5%대)라 조건에 넣으면
         후보가 과하게 줄어든다 → 참고 컬럼으로만 두고 전략 조건에서는 뺀다. */
    if(mkt==='us'){ set('cr7',{min:1,max:null}); }
    else            set(_KRREV(),{min:3,max:null});
    /* (2026-08-09) **막 발표한 종목만** — PEAD 는 발표 직후 수 주간의 현상이라
       한 달 전 발표분까지 섞으면 신호가 희석된다.
       미국은 Yahoo 어닝일(ern)이 촘촘해 그걸 쓰고(D-day 라 지난 발표가 음수),
       한국은 IR 예정일 커버리지가 낮아 **실제 발표 감지일(edld)** 을 쓴다
       — 서프라이즈·주가반응 값도 전부 이 감지일 기준이라 축이 맞는다. */
    if(mkt==='us') set('ern',{min:-7,max:-1});
    else           set('edld',{min:null,max:7});
    set('r1',{min:null,max:5});         // 그런데 주가는 아직 크게 안 올랐다 = 남은 여지
    set('cap',{min:mkt==='kr'?3000:2e9,max:null});
    sort={k:'spr',d:-1}; apply(); };}
  /* (2026-08-09) ⚠️ 가이던스쇼크 — 샌디스크형. 실적은 좋은데 전망이 나빠 빠진 경우.
     반등 후보일 수도, 전망 악화가 진짜일 수도 있어 컨센 리비전을 반드시 함께 본다. */
  {const b=$('scr_gshock'); if(b) b.onclick=()=>{ if(stage!==1) return;
    resetF(); F=F_ST[mkt];                 // 기본 하드컷 위에 조건을 얹는다(위 어닝드리프트와 동일)
    const d=DEF[mkt];
    const set=(k,st)=>{ if(d[k]&&d[k].fixed===undefined) F[k]=st; };
    /* (2026-08-09 사용자 세팅 반영) '실적도 전망도 멀쩡한데 주가만 빠진' 교집합으로 좁힌다.
       서프만 보면 전망이 실제로 나빠진 종목까지 섞여 반등 후보와 함정이 구분되지 않는다.
       → 실적(서프·연속비트) + 전망(컨센 리비전·가이던스 갭)이 모두 마이너스가 아닌데
         주가만 −3% 이상 빠진 경우 = 과잉 반응 의심 구간. */
    set('spr',{min:0,max:null});         // 실적: 컨센 상회
    set('sprb',{min:4,max:null});        // 실적: 최근 4분기 전부 상회(꾸준히 이기는 회사)
    /* (2026-08-10) 매출도 이겼는지 — 펀더멘털이 멀쩡한데 주가만 빠졌다는 근거를 한 겹 더.
       실측 GOOGL 7/22: 매출·EPS 모두 비트인데 설비투자 상향 우려로 −6% → 이 전략의 원형. */
    set('sspr',{min:0,max:null});
    /* 전망이 꺾이지 않았는지 — 미국은 이익추정 리비전+가이던스, 한국은 목표주가 리비전.
       (한국은 cr30·gap 이 구조적으로 비어 있어 이 줄이 없으면 전망 축이 통째로 빠진다) */
    /* (2026-08-10) 발표 **후** 추정이 꺾이지 않았는지 = 7일 리비전(시간 축 일치).
       가이던스 갭은 조건에서 뺀다 — 보도자료에 숫자 가이던스를 싣는 회사가 소수(5%대)라
       조건에 넣으면 '가이던스를 준 회사'만 남아 정작 쇼크 종목이 사라진다(참고 컬럼으로 유지). */
    if(mkt==='us'){ set('cr7',{min:0,max:null}); }
    /* 한국은 '꺾이지 않음(0%)'이 아니라 **오히려 상향(+3%)** 을 요구한다.
       목표주가는 배수 조정만으로도 소폭 움직여 0% 문턱은 사실상 필터가 안 된다.
       +3% 면 증권사들이 실제로 전망을 올렸다는 뜻이라, 주가 하락이 과잉반응일 개연성이 커진다.
       (2026-08-10) 09-08 부터는 영업익추정 리비전 30일로 자동 전환 — _KRREV() */
    else            set(_KRREV(),{min:3,max:null});
    /* (2026-08-09) **막 발표한 종목만** — PEAD 는 발표 직후 수 주간의 현상이라
       한 달 전 발표분까지 섞으면 신호가 희석된다.
       미국은 Yahoo 어닝일(ern)이 촘촘해 그걸 쓰고(D-day 라 지난 발표가 음수),
       한국은 IR 예정일 커버리지가 낮아 **실제 발표 감지일(edld)** 을 쓴다
       — 서프라이즈·주가반응 값도 전부 이 감지일 기준이라 축이 맞는다. */
    if(mkt==='us') set('ern',{min:-7,max:-1});
    else           set('edld',{min:null,max:7});
    set('r1',{min:null,max:-3});         // 그런데 주가는 하락 → 과잉 반응 의심
    set('cap',{min:mkt==='kr'?3000:2e9,max:null});
    sort={k:'r1',d:1}; apply(); };}
  /* (2026-08-09) 🔀 상향미반영 — 사용자 아이디어: 실적발표와 무관하게
     추정치(컨센·목표가)는 좋아지는데 주가는 빠졌거나 아직 안 반영된 교집합.
     학계의 '리비전 모멘텀'(추정치 상향 종목이 초과수익)과 낙폭 결합형.
     보완 두 가지: ① 30일 상향 + 90일도 안 꺾임(단발 반등 배제) ② 상승여력 20%↑
     (주가가 빠져 목표가와의 갭이 벌어져 있어야 '미반영'이 성립).
     ⚠ 주가가 빠지는 데는 이유가 있을 수 있다 — 추정치가 아직 '안 내려온 것뿐'일 수도.
       그래서 낙폭 하한(-25%)을 둬 급락 진행형(악재 반영 중)은 제외한다. */
  {const b=$('scr_rvgap'); if(b) b.onclick=()=>{ if(stage!==1) return;
    resetF(); F=F_ST[mkt];
    const d=DEF[mkt];
    const set=(k,st)=>{ if(d[k]&&d[k].fixed===undefined) F[k]=st; };
    /* (2026-08-10) 7일 리비전 0% 이상 추가 — '30일로는 상향인데 최근 7일에 하향이
       시작된' 종목을 뺀다(90일 안 꺾임 조건의 단기판). */
    if(mkt==='us'){ set('cr30',{min:2,max:null}); set('cr90',{min:0,max:null}); set('cr7',{min:0,max:null}); }
    else{           set(_KRREV(),{min:3,max:null}); set('tprv90',{min:0,max:null}); }
    set('upside',{min:20,max:null});     // 목표가와의 갭 = 미반영 폭
    set('r1m',{min:-25,max:0});          // 한 달 주가 하락·횡보 — 급락 진행형(-25%↓)은 제외
    set('cap',{min:mkt==='kr'?3000:2e9,max:null});
    sort={k:(mkt==='us'?'cr30':_KRREV()),d:-1}; apply(); };}
  /* (2026-08-05) 🌏 외인모멘텀 — '외국인 지분율 개선 + 이익모멘텀 개선' (증권사 리서치 아이디어).
     지분율 일별 시계열이 없어 '꾸준한 개선'은 외인 20일 순매수(+)·연속매수일로 프록시(지분율 상승과 동치).
     이익모멘텀 = 리비전(추정 상향) + 성장가속(직전 분기 대비 성장률 개선). */
  {const b=$('scr_fmom'); if(b) b.onclick=()=>{ if(stage!==1) return;
    if(mkt!=='kr'){ alert('외인모멘텀 프리셋은 한국 전용입니다 (미국은 외인 수급 데이터 미제공)'); return; }
    const d=DEF[mkt];
    for(const k in d){ const f=d[k]; if(!f||f.fixed!==undefined) continue;
      F[k]= f.tgl? {on:false} : f.cat? {v:null} : {min:null,max:null}; }
    const set=(k,st)=>{ if(d[k]&&d[k].fixed===undefined) F[k]=st; };
    set('frgn4w',{min:0,max:null});    // 지분율 4주 변화 0%p ↑ — 실측(네이버 일별 보유율) 정식 지표
    set('fnb20',{min:0,max:null});     // 외인 20일 순매수 + (지분율 상승 중)
    set('fst',{min:3,max:null});       // 외인 연속매수 3일 ↑ (꾸준함)
    set('tprv90',{min:5,max:null});    // 목표주가 리비전 90일 +5%↑ (기존 '리비전' 필터 통일)
    set('gacc',{min:0,max:null});      // 성장가속 0%p ↑ (이익모멘텀 개선)
    set('cap',{min:3e11,max:null});    // 시총 3,000억 ↑
    set('tv',{min:3e9,max:null});      // 거래대금 30억 ↑
    sort={k:'fnb20',d:-1};             // 외인 순매수 많은 순
    apply(); };}
  /* (2026-08-01) 🔄 턴어라운드 프리셋 v2 — 사용자 검증 세팅(KR 21종 통과)으로 교체.
     "이미 하락(고점 -40%·3M 하락) + 실적 재가속(성장가속 +30%p) + 추정 상향(리비전 10%)
      + 밸류 여지(상승여력 50%) + 부실 배제(부채 200%↓·영업적자 1년이상 제외)".
     전부전체 상태에서 이 조합만 걸리도록 먼저 전체 초기화 후 적용. */
  {const tb=$('scr_turn'); if(tb) tb.onclick=()=>{
    if(stage!==1) return;
    const d=DEF[mkt];
    for(const k in d){ const f=d[k]; if(!f||f.fixed!==undefined) continue;
      F[k]= f.tgl? {on:false} : f.cat? {v:null} : {min:null,max:null}; }   // 전부 '전체'로
    const set=(k,st)=>{ if(d[k]&&d[k].fixed===undefined) F[k]=st; };
    set('gacc',{min:30,max:null});     // 성장가속 +30%p ↑ (실적 재가속 — 핵심)
    if(mkt==='kr') set('tprv90',{min:10,max:null});  // KR: 목표주가 리비전 90일로 통일
    else set('rev',{min:10,max:null});               // US: EPS 추정 리비전(기존 유지)
    set('upside',{min:50,max:null});   // 상승여력 50% ↑
    set('r3m',{min:null,max:0});       // 수익률 3M 하락 (아직 덜 반영)
    set('hi',{min:null,max:-40});      // 고점比 -40% ↓ (낙폭 충분)
    set('de',{min:null,max:200});      // 부채비율 200% ↓ (부실 배제)
    set('opLoss',{min:null,max:1});    // 영업적자 1년이상 제외
    apply();
  };}
  /* (2026-08-01) 🎯 저PBR M&A 표적 프리셋 — 기사(DS증권) 조건 그대로:
     PBR ≤0.4배 · 시총 ≥1,000억(US $300M) · 영업이익 흑자. 결과는 PBR 낮은 순 정렬 */
  {const pb=$('scr_lowpbr'); if(pb) pb.onclick=()=>{
    if(stage!==1) return;
    const d=DEF[mkt];
    for(const k in d){ const f=d[k]; if(!f||f.fixed!==undefined) continue;
      F[k]= f.tgl? {on:false} : f.cat? {v:null} : {min:null,max:null}; }
    const set=(k,st)=>{ if(d[k]&&d[k].fixed===undefined) F[k]=st; };
    set('pbr',{min:null,max:0.4});
    set('cap',{min:mkt==='kr'?1e11:3e8,max:null});   // 1,000억 / $300M
    set('opLoss',{min:null,max:1});                  // 흑자(최근 1년 적자 제외)
    /* (2026-08-01 v4 — 사용자 확정 '알짜 조합', KR 38종) 밸류트랩 3중 배제 + 외인 재평가 개시.
       상승여력·기관수급은 커버리지/후행 편향이라 제외 */
    set('de',{min:null,max:100});                    // 부채비율 100%↓ — 빚 없는 알짜 자산주(인수 매력)
    set('roe',{min:3,max:null});                     // ROE 3%↑ — 자산이 놀고 있지 않음
    set('divy',{min:3,max:null});                    // 배당 3%↑ — 주주환원 실적
    set('fnb20',{min:0,max:null});                   // 외인 20일 순매수 +
    sort={k:'pbr',d:1};                              // PBR 오름차순 — 가장 싼 순
    apply();
  };}
  /* 전부전체 — 하드컷 전부 해제 + 종목 찾기도 해제해 말 그대로 전종목을 띄운다 */
  {const ab=$('scr_allf'); if(ab) ab.onclick=()=>{ if(stage!==1) return;
    allF(); findQ=''; findOpen=false; findIME=false; apply(); };}
  // 3단계 상위 N · 분석요청 버튼
  {const tn=$('scr_topn3'); if(tn) tn.oninput=()=>{ topN3=Math.max(1,Math.min(100,+tn.value||30)); rankCards3(); };}
  {const pw=$('scr_pw'), ab0=$('scr_ask');
   if(pw&&ab0){ pw.oninput=()=>{ const ok=pw.value==='0070';
     ab0.disabled=!ok; ab0.style.opacity=ok?'1':'.45'; ab0.style.cursor=ok?'pointer':'not-allowed';
     ab0.textContent=(ok?'📋':'🔒')+' 분석요청 → TradingAgents'; }; } }
  {const ab=$('scr_ask'); if(ab) ab.onclick=()=>{ if(ab.disabled)return; const t=window.__scr_top3||[];
    if(!t.length){alert('선택된 종목이 없습니다 — 1·2단계 필터를 확인하세요');return;}
    try{navigator.clipboard.writeText(t.join(', '));}catch(e){}
    alert('분석요청 TOP '+t.length+'종 (클립보드 복사됨):\n'+t.join(', ')+'\n\n/namoobi-trading-agents 실행 시 이 종목으로 토론·리스크심사합니다.'); };}
})();

/* ── [부록E·F] 피지컬 AI 밸류체인 — /api/db/appe (서버 1일 2회 수집) ── */
(async function renderAppE(){
  const box=document.getElementById('d_appe'); if(!box) return;
  let A; try{ A=await (await fetch('/api/db/appe')).json(); }catch(e){ box.innerHTML='<div class="note">appe.json 없음 — 서버 수집 대기</div>'; return; }
  const P=v=>(v==null||v==='')?'<span class="note">-</span>':`<span class="${v>=0?'up':'dn'}">${v>=0?'+':''}${Number(v).toFixed(1)}%</span>`;
  const CCY={USD:'$',JPY:'¥',KRW:'₩',TWD:'NT$',CNY:'CN¥',HKD:'HK$',AUD:'A$'};
  const esc2=t=>String(t==null?'':t).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
  const num=v=>(v==null||v==='')?'-':Number(v).toLocaleString(undefined,{maximumFractionDigits:2});
  const GL='①②③④⑤⑥';
  box.innerHTML=(A.groups||[]).map((g,gi)=>{
    const rows=(A.rows||{})[g]||[]; if(!rows.length) return '';
    return `<h3>${GL[gi]||'■'} ${esc2(g)} <span class="note">${rows.length}종</span></h3>
      <div class="box" style="overflow-x:auto"><table>
      <tr>${['종목','현재가','1일','1주','1개월','3개월','6개월','1년','역할'].map(h=>`<th>${h}</th>`).join('')}</tr>
      ${rows.map(x=>`<tr>
        <td><b>${esc2(x.name||'')}</b> <span class="note">${esc2(x.code||'')}</span></td>
        <td class="num">${(CCY[x.ccy]||'$')}${num(x.current)}</td>
        <td class="num">${P(x['1d_pct'])}</td><td class="num">${P(x['1w_pct'])}</td><td class="num">${P(x['1mo_pct'])}</td>
        <td class="num">${P(x['3mo_pct'])}</td><td class="num">${P(x['6mo_pct'])}</td><td class="num">${P(x['1y_pct'])}</td>
        <td class="note">${esc2(x.desc||'')}</td></tr>`).join('')}</table></div>`;
  }).join('') + (A.asof?`<div class="src">기준 ${esc2(A.asof)}${A.as_of?' · 수집 '+esc2(A.as_of):''} · 구성 근거: 한경비즈니스 2026.08.05-11 커버스토리 '피지컬 AI 핵심 밸류체인' + 모건스탠리 2025 선정 핵심기업</div>`:'');
  const bf=document.getElementById('d_appf');
  if(bf) bf.innerHTML=`<div class="appd">
    <img src="/img/appf_physical_ai_1.png" alt="피지컬 AI 밸류체인 관계도 1" loading="lazy">
    <img src="/img/appf_physical_ai_2.png" alt="피지컬 AI 밸류체인 관계도 2" loading="lazy">
    <img src="/img/appf_physical_ai_3.png" alt="피지컬 AI 밸류체인 관계도 3" loading="lazy">
    </div><div class="src">구성이 바뀔 때만 갱신되는 정적 관계도 (부록E와 동일 54종 + 비상장 9곳).</div>`;
})();
/* ── 3.1.14 국내 유동성·레버리지 점검 — /api/krliq (서버 1일 3회 수집 · 보고서 renderKrLiquidity 와 동일 구성) ── */
(async()=>{
  const $=i=>document.getElementById(i);
  if(!$('kl_sum')) return;
  let D; try{ D=await (await fetch('/api/krliq?days=420')).json(); }catch(e){ return; }
  const rows=D.daily||[], M=D.monthly||[], V=D.verdict||{};
  // 일별: [0]date [1]예탁금 [2]미수금 [3]반대매매 [4]비중 [5]신용전체 [6]코스피분 [7]코스닥분 [8]코스피 [9]코스피대금 [10]코스닥 [11]코스닥대금
  const last=i=>{for(let k=rows.length-1;k>=0;k--) if(rows[k][i]!=null) return rows[k]; return null;};
  const fmtD=s=>String(s).replace(/(\d{4})(\d{2})(\d{2})/,'$2/$3');
  const nn=v=>(v==null?'—':v), sgn=v=>(v==null?'—':(v>0?'+':'')+(+v).toLocaleString());
  const ld=last(1), lt=rows.filter(r=>r[1]!=null&&r[9]!=null).pop(), lc=last(5), lo=last(3);
  const kl={as_of:ld?ld[0]:'', deposit_t:ld?+(ld[1]/1e12).toFixed(1):null,
    turnover:lt?+(lt[9]/lt[1]).toFixed(2):null,
    crd_t:lc?+(lc[5]/1e12).toFixed(1):null, crd_kosdaq_t:lc?+(lc[7]/1e12).toFixed(2):null,
    kosdaq_share:(lc&&lc[5]&&lc[7])?+(lc[7]/lc[5]*100).toFixed(1):null,
    opp_amt_e:lo?Math.round(lo[3]/1e8):null, opp_ratio:lo?lo[4]:null, opp_date:lo?lo[0]:''};
  const cq=rows.filter(r=>r[7]!=null);
  kl.kosdaq_chg5_e=cq.length>5?Math.round((cq[cq.length-1][7]-cq[cq.length-6][7])/1e8):null;
  const mi={}; M.forEach(r=>mi[r[0]]=r);
  const yoy=(t,i)=>{const p=mi[String(+t-100)];return (p&&p[i]&&mi[t]&&mi[t][i])?+((mi[t][i]/p[i]-1)*100).toFixed(1):null;};
  const ts=M.map(r=>r[0]).filter(t=>yoy(t,1)!=null&&yoy(t,2)!=null);
  const lm=ts[ts.length-1];
  if(lm){kl.m2_month=lm; kl.m2_yoy=yoy(lm,1); kl.kospi_yoy=yoy(lm,2); kl.kosdaq_yoy=yoy(lm,3);}
  const toneC={'강세':'#0a7d33','중립':'#8a6d00','경계':'#b45309','약세':'#b91c1c'}[V.tone]||'#334155';
  const vTxt=V.label?`자동 판정: ${V.label}(${V.tone}) — 예탁금 5일 ${V.dep_5d_pct>0?'+':''}${V.dep_5d_pct}% · 회전배수 5일 ${V.turn_5d_chg>0?'+':''}${V.turn_5d_chg}p`:'—';
  $('kl_verdict').innerHTML=`<b style="color:${toneC}">${vTxt}</b> · 기준 ${fmtD(V.as_of||kl.as_of)} (T+2)`;
  // 요약표 (보고서와 동일 4행)
  const gapTxt=(kl.kospi_yoy!=null&&kl.m2_yoy!=null)?((kl.kospi_yoy-kl.m2_yoy>20)?'유동성 증가율 대비 주가 상승률 괴리 — 과열 신호':'유동성 증가율과 주가 추세 동행'):'—';
  const T=(id,head,rws)=>{const el=$(id);el.innerHTML=`<tr>${head.map(h=>`<th>${h}</th>`).join('')}</tr>`+rws.map(r=>`<tr>${r.map(c=>`<td>${c}</td>`).join('')}</tr>`).join('');};
  T('kl_sum',['복합지표','최신 수치','기준일(지연)','판정/해석'],[
    ['① 예탁금+거래대금',`예탁금 ${nn(kl.deposit_t)}조 · 회전배수 ${nn(kl.turnover)}배`,`${fmtD(kl.as_of)} (T+2)`,vTxt],
    ['② M2+코스피/코스닥',`M2 YoY ${nn(kl.m2_yoy)}% · KOSPI ${nn(kl.kospi_yoy)}% · KOSDAQ ${nn(kl.kosdaq_yoy)}%`,`${kl.m2_month?String(kl.m2_month).replace(/(\d{4})(\d{2})/,'$1.$2'):'—'} (약 2개월)`,gapTxt],
    ['③ 신용융자+변동성+반대매매',`신용융자 ${nn(kl.crd_t)}조 · 반대매매 ${nn(kl.opp_amt_e)}억(비중 ${nn(kl.opp_ratio)}%)`,`${fmtD(kl.opp_date||kl.as_of)} (T+2)`,'레버리지 수준 + 급락 후 강제청산 압력 확인'],
    ['④ 코스닥 신용(마진콜 조기경보)',`코스닥 신용 ${nn(kl.crd_kosdaq_t)}조(비중 ${nn(kl.kosdaq_share)}%) · 5일 증감 ${sgn(kl.kosdaq_chg5_e)}억`,`${fmtD(kl.as_of)} (T+2)`,(kl.kosdaq_chg5_e!=null&&kl.kosdaq_chg5_e<0?'코스닥 잔고 순감 — 디레버리징(상환+강제청산 혼재) 진행':'코스닥 잔고 증가 — 레버리지 재축적')]]);
  // ① 판정 매트릭스 (현재 위치 강조)
  const mpos=({'유입·가동':[0,1],'유입·관망':[0,2],'이탈·소진성 회전':[1,1],'이탈·위축':[1,2]})[V.label]||null;
  const mrows=[['예탁금 증가','유입·가동 (강세)','유입·관망 (중립)'],['예탁금 감소','이탈 속 소진성 회전 (경계)','이탈·위축 (약세)']];
  if(mpos) mrows[mpos[0]][mpos[1]]=`<b style="color:${toneC}">${mrows[mpos[0]][mpos[1]]} ← 현재</b>`;
  T('kl_mx',['','회전배수 상승','회전배수 하락'],mrows);
  if(V.label) $('kl_cur1').innerHTML=`<b style="color:${toneC}">현재(${fmtD(V.as_of)} T+2): 예탁금 5일 ${V.dep_5d_pct>0?'+':''}${V.dep_5d_pct}% · 회전배수 5일 ${V.turn_5d_chg>0?'+':''}${V.turn_5d_chg}p → ${V.label}(${V.tone}).</b> 판정 결과는 차트 제목에 자동 표기.`;
  $('kl_txt2').textContent=`한국은행 ECOS 월별(M2 평잔·코스피/코스닥 월말 종가, 약 2개월 지연). 최근 KOSDAQ YoY ${nn(kl.kosdaq_yoy)}% vs KOSPI ${nn(kl.kospi_yoy)}% — M2 YoY(${nn(kl.m2_yoy)}%)를 크게 웃도는 주가 상승률은 유동성 초과 랠리, 하회하면 유동성 대비 저평가 신호.`;
  $('kl_txt3').textContent=`하단 반대매매 = 금융위 공공데이터 '미수금 대비 반대매매금액·비중'(일별 T+2, 금투협 원천) — 위탁매매 미수금(D+2 미납) 기반 강제청산의 공식 일별 통계. 급락 직후 반대매매 급증 + 비중 상승 = 강제청산 압력 확인. 최근 ${fmtD(kl.opp_date||kl.as_of)} ${nn(kl.opp_amt_e)}억원 · 비중 ${nn(kl.opp_ratio)}%.`;
  $('kl_txt4').textContent=`현재(${fmtD(kl.as_of)} T+2): 코스닥 신용 ${nn(kl.crd_kosdaq_t)}조(전체의 ${nn(kl.kosdaq_share)}%) · 5일 누적 ${sgn(kl.kosdaq_chg5_e)}억. 지수 하락률 대비 잔고 감소율이 비정상적으로 크면 강제청산(마진콜) 우세로 해석 — 단, 상환과 강제청산은 구분 불가(마진콜 직접 통계 부재).`;
})();

/* ══ 스크롤스파이 — 현재 섹션 네비 칩 실시간 하이라이트 (daily·DB data·AI 추론 3탭 공통) ══ */
(function(){
  let pin=null, prog=false;                            // pin: 클릭 고정 / prog: 프로그램 스크롤 중
  function activeNav(){
    const p=document.querySelector('.pane.on'); if(!p) return null;
    const n=p.querySelector('nav'); return (n && n.querySelector('a[data-go],a[data-go2]'))?n:null;
  }
  function mark(nav,a){ nav.querySelectorAll('a').forEach(x=>x.classList.toggle('spy',x===a)); }
  function scrollParent(el){                            // 섹션이 실제로 스크롤되는 조상 컨테이너 탐색
    let n=el&&el.parentElement;
    while(n){ const cs=getComputedStyle(n);
      if(/(auto|scroll)/.test(cs.overflowY) && n.scrollHeight>n.clientHeight+4) return n;
      n=n.parentElement; }
    return document.scrollingElement||document.documentElement;
  }
  function spy(){
    const nav=activeNav(); if(!nav) return;
    if(pin && nav.contains(pin)){ mark(nav,pin); return; }   // 클릭 고정 — 사용자가 스크롤할 때까지 유지
    const links=[...nav.querySelectorAll('a[data-go],a[data-go2]')]; if(!links.length) return;
    const ref=nav.getBoundingClientRect().bottom+16;  // 스티키 네비 바로 아래 기준선
    let cur=null;
    for(const a of links){
      const el=document.getElementById(a.dataset.go2||a.dataset.go); if(!el) continue;
      if(el.getBoundingClientRect().top<=ref) cur=a; else break;
    }
    mark(nav, cur||links[0]);
  }
  function go(a){                                      // 네비 클릭 → 섹션을 스티키 네비 바로 아래로
    const el=document.getElementById(a.dataset.go2||a.dataset.go); if(!el) return;
    const nav=a.closest('nav'); const scroller=scrollParent(el);   // 탭마다 스크롤 컨테이너 다름 → 동적 탐색
    const desired = () => nav.getBoundingClientRect().bottom + 6;  // 목표: 섹션 top = 네비 바로 아래
    prog=true;
    scroller.scrollBy({top: el.getBoundingClientRect().top - desired(), behavior:'auto'});
    requestAnimationFrame(()=>{                        // 스티키·리플로우 보정 1회
      const d2 = el.getBoundingClientRect().top - desired();
      if(Math.abs(d2)>2) scroller.scrollBy({top:d2, behavior:'auto'});
    });
    setTimeout(()=>{ prog=false; },150);               // rAF와 무관하게 항상 해제(백그라운드 탭 대비)
    pin=a; mark(nav, a);                               // 클릭 즉시 고정(짧은 pane에서도 유지)
  }
  document.addEventListener('click',e=>{               // 캡처 단계 — 기존 핸들러보다 먼저 처리
    const a=e.target.closest('nav a[data-go],nav a[data-go2]');
    if(a){ e.preventDefault(); e.stopPropagation(); go(a); }
  }, true);
  let lastSpy=0;
  const onScroll=()=>{ if(prog) return; pin=null;      // 사용자 스크롤 → 고정 해제
    const now=Date.now(); if(now-lastSpy<70) return; lastSpy=now; spy(); };  // rAF 대신 시간 스로틀(백그라운드 탭 대비)
  document.addEventListener('scroll',onScroll,{capture:true,passive:true});  // 모든 스크롤 컨테이너 포착(캡처)
  window.addEventListener('scroll',onScroll,{passive:true});
  window.addEventListener('resize',()=>{pin=null; spy();},{passive:true});
  document.querySelectorAll('.tab[data-pane]').forEach(t=>t.addEventListener('click',()=>{pin=null; setTimeout(spy,80);}));
  setInterval(spy,1200); setTimeout(spy,900);
})();


/* ── (2026-08-02) 🌐 글로벌시황 — 미래에셋 국내외 주요지수 재현 (10분 수집·global_market.py) ── */
(function(){
  let D=null, HIST=null, timer=null, openSym=null;
  const $=id=>document.getElementById(id);
  const fmt=(v,dec,mult)=>v==null?'—':(v*(mult||1)).toLocaleString(undefined,{minimumFractionDigits:dec??2,maximumFractionDigits:dec??2});
  const pc=v=>v==null?'<span class="note">—</span>':`<span class="${v>0?'up':v<0?'dn':''}">${v>0?'+':''}${v.toFixed(2)}%</span>`;
  function subCode(sym){
    if(sym.startsWith('KRW-')) return sym.split('-')[1]+'/KRW';
    if(sym==='KRW=X') return 'KRW/USD';
    if(/^[A-Z]{3}KRW=X$/.test(sym)) return 'KRW/'+sym.slice(0,3);
    if(sym==='EURUSD=X') return 'USD/EUR';
    if(sym==='GBPUSD=X') return 'USD/GBP';
    if(sym==='AUDUSD=X') return 'USD/AUD';
    if(/^[A-Z]{3}=X$/.test(sym)) return 'USD/'+sym.slice(0,3);
    if(sym==='ND.FX_USDGEL') return 'USD/GEL';
    if(sym.startsWith('ND.FX_')) return sym.slice(6,9)+'/'+sym.slice(9);
    if(sym.startsWith('NAV.')) return sym.slice(3);       // 네이버 월드지수 코드 (.TOPX 등)
    if(sym.startsWith('SN.')) return sym.slice(3);        // 시나 중국선물 코드 (LC0 등)
    if(sym.startsWith('NAVKR.')) return sym.slice(6);     // 네이버 국내지수 코드 (KVALUE 등)
    if(sym.startsWith('NF.')) return sym.slice(3);        // 네이버 선물 코드 (HSIc1 등)
    if(sym.startsWith('DV.')) return sym.slice(3);        // 내부 DB 소스 (VKOSPI)
    if(sym.startsWith('ND.')) return '';                  // 네이버 내부코드 — 생략
    return sym;                                           // 야후 심볼 그대로 (^GSPC·399001.SZ·CL=F 등)
  }
  function sparkSVG(a,w,h){
    if(!a||a.length<2) return '<span class="note">누적 중</span>';
    const lo=Math.min(...a),hi=Math.max(...a),rg=(hi-lo)||1;
    const pts=a.map((v,i)=>`${(i/(a.length-1)*w).toFixed(1)},${(h-2-(v-lo)/rg*(h-4)).toFixed(1)}`).join(' ');
    const up=a[a.length-1]>=a[0];
    return `<svg width="${w}" height="${h}" style="vertical-align:middle"><polyline points="${pts}" fill="none" stroke="${up?'#c0392b':'#1e6fd6'}" stroke-width="1.3"/></svg>`;
  }
  function table(){
    if(!D) return;
    $('gm_asof').textContent=`수집 ${D.asof} — 10분 자동 갱신 · 국내대표/크립토=실시간 · 해외지수=야후(~15분 지연) · KRX 세부=T+1 종가`;
    let h='<table style="width:100%;border-collapse:collapse;font-size:12px">';
    h+='<colgroup><col style="width:220px"><col style="width:104px">'+ '<col style="width:66px">'.repeat(6)+'<col style="width:140px"><col style="width:66px"><col style="width:140px"><col style="width:66px"></colgroup>';
    D.groups.forEach(g=>{
      if(!g.rows.length) return;
      if(g.key==='fx2'){
        h+=`<tr><td colspan="12" style="padding:10px 6px 4px;font-weight:700;font-size:13px;border-bottom:2px solid #dfe4ea;cursor:pointer" onclick="window.__gmFx2=!window.__gmFx2; window.__gmTblRe&&window.__gmTblRe()">${g.label} <span class="note">(${g.rows.length}종) ${window.__gmFx2?'▲ 접기':'▼ 더보기 — 전체 통화 표시'}</span></td></tr>`;
        if(!window.__gmFx2) return;
      } else {
        h+=`<tr><td colspan="12" style="padding:10px 6px 4px;font-weight:700;font-size:13px;border-bottom:2px solid #dfe4ea">${g.label}</td></tr>`;
      }
      h+='<tr style="color:#8a94a0">'+['지수/종목','현재가','1일','1주','1개월','3개월','6개월','1년','추세(1Y)','3년','추세(3Y)','10년'].map((c,i)=>`<td style="padding:2px 6px;text-align:${i==0?'left':'right'};border-bottom:1px solid #eceff3">${c}</td>`).join('')+'</tr>';
      g.rows.forEach(r=>{
        const R=r.ret||{}; const d1=R.d1!=null?R.d1:r.ret_d1_live;
        h+=`<tr class="gmrow" data-s="${r.s}" style="cursor:pointer;border-bottom:1px solid #f2f4f7">`
         +`<td style="padding:5px 6px"><b>${r.name}</b>${subCode(r.s)?` <span class="note" style="font-size:10px;font-weight:600">${subCode(r.s)}</span>`:''}${r.en?` <span class="note" style="font-size:10px">${r.en}</span>`:''} <span class="note" style="font-size:10px">${r.at||''}</span></td>`
         +`<td style="text-align:right;font-weight:600">${fmt(r.px,r.dec,r.mult)}</td>`
         +`<td style="text-align:right">${pc(d1)}</td><td style="text-align:right">${pc(R.w1)}</td>`
         +`<td style="text-align:right">${pc(R.m1)}</td><td style="text-align:right">${pc(R.m3)}</td>`
         +`<td style="text-align:right">${pc(R.m6)}</td><td style="text-align:right">${pc(R.y1)}</td>`
         +`<td style="text-align:right;padding:2px 6px">${sparkSVG(r.spark,120,26)}</td>`
         +`<td style="text-align:right">${pc(R.y3)}</td>`
         +`<td style="text-align:right;padding:2px 6px">${sparkSVG(r.spark3,120,26)}</td>`
         +`<td style="text-align:right">${pc(R.y10)}</td></tr>`;
      });
      if(g.key==='kr'){
        h+=`<tr><td colspan="12" style="padding:8px 6px 2px;font-weight:700;font-size:13px">🔥 인기 검색 종목 <span class="note" id="gm_pop_t">(네이버 · 3분 갱신)</span></td></tr>`
         +`<tr><td colspan="12" style="padding:0 6px 6px"><div id="gm_pop"><div class="note">불러오는 중…</div></div></td></tr>`;
      }
    });
    h+='</table>';
    const sc=document.querySelector('#p_global').scrollTop;
    $('gm_body').innerHTML=h;
    document.querySelectorAll('.gmrow').forEach(tr=>tr.addEventListener('click',()=>openDetail(tr.dataset.s)));
    document.querySelector('#p_global').scrollTop=sc;
    if(typeof loadPop==='function') loadPop();
    if(openSym) openDetail(openSym,true);
  }

  /* 외부 차트 링크 — 실측 검증된 코드만 버튼 노출(2026-08-02 전수 프로브). 팝업으로 표시 */
  const NAVER={'^KS11':'domestic/index/KOSPI/total','^KQ11':'domestic/index/KOSDAQ/total','^KS200':'domestic/index/KPI200/total',
    'NAVKR.KPI100':'domestic/index/KPI100/total','NAVKR.KVALUE':'domestic/index/KVALUE/total',
    '^DJI':'worldstock/index/.DJI/total','^DJT':'worldstock/index/.DJT/total','^IXIC':'worldstock/index/.IXIC/total',
    '^NDX':'worldstock/index/.NDX/total','^GSPC':'worldstock/index/.INX/total','^SOX':'worldstock/index/.SOX/total',
    '^VIX':'worldstock/index/.VIX/total','^HSI':'worldstock/index/.HSI/total','^HSCE':'worldstock/index/.HSCE/total',
    '000001.SS':'worldstock/index/.SSEC/total','399106.SZ':'worldstock/index/.SZSC/total','000300.SS':'worldstock/index/.CSI300/total',
    '^N225':'worldstock/index/.N225/total','NAV.TOPX':'worldstock/index/.TOPX/total','NAV.VNI':'worldstock/index/.VNI/total',
    'NAV.HNXI':'worldstock/index/.HNXI/total','NAV.SSEA':'worldstock/index/.SSEA/total','NAV.SSEB':'worldstock/index/.SSEB/total',
    'NAV.SZSA':'worldstock/index/.SZSA/total','NAV.SZSB':'worldstock/index/.SZSB/total','NAV.CSI100':'worldstock/index/.CSI100/total',
    'NAV.IBEX':'worldstock/index/.IBEX/total','NAV.OMXS30':'worldstock/index/.OMXS30/total','FTSEMIB.MI':'worldstock/index/.FTMIB/total',
    'NAV.OMXC20':'worldstock/index/.OMXC20/total','NAV.BUX':'worldstock/index/.BUX/total',
    '^ISEQ':'worldstock/index/.ISEQ/total','^AXJO':'worldstock/index/.AXJO/total','^MXX':'worldstock/index/.MXX/total','^MERV':'worldstock/index/.MERV/total',
    'NF.HSIc1':'worldstock/futures/HSIc1/total','NF.HCEIc1':'worldstock/futures/HCEIc1/total','NF.SFCc1':'worldstock/futures/SFCc1/total',
    'NF.SSIcm1':'worldstock/futures/SSIcm1/total','NF.STXEc1':'worldstock/futures/STXEc1/total','NF.FDXc1':'worldstock/futures/FDXc1/total',
    '^TWII':'worldstock/index/.TWII/total','^BSESN':'worldstock/index/.BSESN/total','^KLSE':'worldstock/index/.KLSE/total',
    '^JKSE':'worldstock/index/.JKSE/total','^STOXX50E':'worldstock/index/.STOXX50E/total','^FTSE':'worldstock/index/.FTSE/total',
    '^GDAXI':'worldstock/index/.GDAXI/total','^FCHI':'worldstock/index/.FCHI/total','^BFX':'worldstock/index/.BFX/total',
    '^AEX':'worldstock/index/.AEX/total','PSI20.LS':'worldstock/index/.PSI20/total','GD.AT':'worldstock/index/.ATG/total',
    '^BVSP':'worldstock/index/.BVSP/total',
    'CL=F':'marketindex/energy/CLcv1','BZ=F':'marketindex/energy/LCOcv1','NG=F':'marketindex/energy/NGcv1',
    'GC=F':'marketindex/metals/GCcv1','SI=F':'marketindex/metals/SIcv1','HG=F':'marketindex/metals/HGcv1',
    'ZC=F':'marketindex/agricultural/Ccv1','ZS=F':'marketindex/agricultural/Scv1','ZW=F':'marketindex/agricultural/Wcv1',
    'ZR=F':'marketindex/agricultural/RRcv1',
    'HO=F':'https://finance.naver.com/marketindex/materialDetail.naver?marketindexCd=CMDT_HO','PL=F':'https://finance.naver.com/marketindex/worldGoldDetail.naver?marketindexCd=CMDT_PL',
    'PA=F':'https://finance.naver.com/marketindex/worldGoldDetail.naver?marketindexCd=CMDT_PA','SB=F':'https://finance.naver.com/marketindex/materialDetail.naver?marketindexCd=CMDT_SB',
    'ZM=F':'https://finance.naver.com/marketindex/materialDetail.naver?marketindexCd=CMDT_SM','ZL=F':'https://finance.naver.com/marketindex/materialDetail.naver?marketindexCd=CMDT_BO',
    'CT=F':'https://finance.naver.com/marketindex/materialDetail.naver?marketindexCd=CMDT_CT','OJ=F':'https://finance.naver.com/marketindex/materialDetail.naver?marketindexCd=CMDT_OJ',
    'KC=F':'https://finance.naver.com/marketindex/materialDetail.naver?marketindexCd=CMDT_KC','CC=F':'https://finance.naver.com/marketindex/materialDetail.naver?marketindexCd=CMDT_CC',
    'ND.CMDT_GO':'https://finance.naver.com/marketindex/materialDetail.naver?marketindexCd=CMDT_GO','ND.OIL_DU':'https://finance.naver.com/marketindex/worldOilDetail.naver?marketindexCd=OIL_DU',
    'ND.CMDT_PDY':'https://finance.naver.com/marketindex/materialDetail.naver?marketindexCd=CMDT_PDY','ND.CMDT_ZDY':'https://finance.naver.com/marketindex/materialDetail.naver?marketindexCd=CMDT_ZDY',
    'ND.CMDT_NDY':'https://finance.naver.com/marketindex/materialDetail.naver?marketindexCd=CMDT_NDY','ND.CMDT_AAY':'https://finance.naver.com/marketindex/materialDetail.naver?marketindexCd=CMDT_AAY',
    'ND.CMDT_SDY':'https://finance.naver.com/marketindex/materialDetail.naver?marketindexCd=CMDT_SDY','ND.GOLD_KR':'https://finance.naver.com/marketindex/goldDetail.naver',
    'ND.OIL_GSL':'https://finance.naver.com/marketindex/oilDetail.naver?marketindexCd=OIL_GSL','ND.OIL_LO':'https://finance.naver.com/marketindex/oilDetail.naver?marketindexCd=OIL_LO',
    'KRW=X':'marketindex/exchange/FX_USDKRW','JPYKRW=X':'marketindex/exchange/FX_JPYKRW','CNYKRW=X':'marketindex/exchange/FX_CNYKRW',
    'EURKRW=X':'marketindex/exchange/FX_EURKRW','GBPKRW=X':'marketindex/exchange/FX_GBPKRW','HKDKRW=X':'marketindex/exchange/FX_HKDKRW',
    'AUDKRW=X':'marketindex/exchange/FX_AUDKRW','SGDKRW=X':'marketindex/exchange/FX_SGDKRW','CADKRW=X':'marketindex/exchange/FX_CADKRW',
    'INRKRW=X':'marketindex/exchange/FX_INRKRW','IDRKRW=X':'marketindex/exchange/FX_IDRKRW','BRLKRW=X':'marketindex/exchange/FX_BRLKRW',
    'TWDKRW=X':'marketindex/exchange/FX_TWDKRW','CHFKRW=X':'marketindex/exchange/FX_CHFKRW','NZDKRW=X':'marketindex/exchange/FX_NZDKRW','SEKKRW=X':'marketindex/exchange/FX_SEKKRW',
    'CZKKRW=X':'marketindex/exchange/FX_CZKKRW','CLPKRW=X':'marketindex/exchange/FX_CLPKRW','TRYKRW=X':'marketindex/exchange/FX_TRYKRW',
    'EURUSD=X':'https://finance.naver.com/marketindex/worldExchangeDetail.naver?marketindexCd=FX_USDEUR','GBPUSD=X':'https://finance.naver.com/marketindex/worldExchangeDetail.naver?marketindexCd=FX_USDGBP','AUDUSD=X':'https://finance.naver.com/marketindex/worldExchangeDetail.naver?marketindexCd=FX_USDAUD',
    'MXN=X':'https://finance.naver.com/marketindex/worldExchangeDetail.naver?marketindexCd=FX_USDMXN',
    'ZAR=X':'https://finance.naver.com/marketindex/worldExchangeDetail.naver?marketindexCd=FX_USDZAR',
    'NOK=X':'https://finance.naver.com/marketindex/worldExchangeDetail.naver?marketindexCd=FX_USDNOK',
    'DKK=X':'https://finance.naver.com/marketindex/worldExchangeDetail.naver?marketindexCd=FX_USDDKK',
    'PLN=X':'https://finance.naver.com/marketindex/worldExchangeDetail.naver?marketindexCd=FX_USDPLN',
    'THB=X':'https://finance.naver.com/marketindex/worldExchangeDetail.naver?marketindexCd=FX_USDTHB',
    'PHP=X':'https://finance.naver.com/marketindex/worldExchangeDetail.naver?marketindexCd=FX_USDPHP',
    'VND=X':'https://finance.naver.com/marketindex/worldExchangeDetail.naver?marketindexCd=FX_USDVND',
    'MYR=X':'https://finance.naver.com/marketindex/worldExchangeDetail.naver?marketindexCd=FX_USDMYR',
    'SAR=X':'https://finance.naver.com/marketindex/worldExchangeDetail.naver?marketindexCd=FX_USDSAR',
    'AED=X':'https://finance.naver.com/marketindex/worldExchangeDetail.naver?marketindexCd=FX_USDAED',
    'ILS=X':'https://finance.naver.com/marketindex/worldExchangeDetail.naver?marketindexCd=FX_USDILS',
    'ARS=X':'https://finance.naver.com/marketindex/worldExchangeDetail.naver?marketindexCd=FX_USDARS',
    'COP=X':'https://finance.naver.com/marketindex/worldExchangeDetail.naver?marketindexCd=FX_USDCOP',
    'HUF=X':'https://finance.naver.com/marketindex/worldExchangeDetail.naver?marketindexCd=FX_USDHUF',
    'RUB=X':'https://finance.naver.com/marketindex/worldExchangeDetail.naver?marketindexCd=FX_USDRUB',
    'CNY=X':'https://finance.naver.com/marketindex/worldExchangeDetail.naver?marketindexCd=FX_USDCNY',
    'HKD=X':'https://finance.naver.com/marketindex/worldExchangeDetail.naver?marketindexCd=FX_USDHKD',
    'TWD=X':'https://finance.naver.com/marketindex/worldExchangeDetail.naver?marketindexCd=FX_USDTWD',
    'SGD=X':'https://finance.naver.com/marketindex/worldExchangeDetail.naver?marketindexCd=FX_USDSGD',
    'CHF=X':'https://finance.naver.com/marketindex/worldExchangeDetail.naver?marketindexCd=FX_USDCHF',
    'CAD=X':'https://finance.naver.com/marketindex/worldExchangeDetail.naver?marketindexCd=FX_USDCAD',
    'BRL=X':'https://finance.naver.com/marketindex/worldExchangeDetail.naver?marketindexCd=FX_USDBRL',
    'TRY=X':'https://finance.naver.com/marketindex/worldExchangeDetail.naver?marketindexCd=FX_USDTRY',
    'UAH=X':'https://finance.naver.com/marketindex/worldExchangeDetail.naver?marketindexCd=FX_USDUAH'};
  const TV={'^KS11':'KRX:KOSPI','^KQ11':'KRX:KOSDAQ','^DJI':'DJ:DJI','^DJT':'DJ:DJT','^IXIC':'NASDAQ:IXIC','^NDX':'NASDAQ:NDX',
    '^GSPC':'SP:SPX','^SOX':'NASDAQ:SOX','^VIX':'TVC:VIX','ES=F':'CME_MINI:ES1!','NQ=F':'CME_MINI:NQ1!',
    'XLK':'AMEX:XLK','XLV':'AMEX:XLV','XLC':'AMEX:XLC','XLY':'AMEX:XLY','XLF':'AMEX:XLF','XLI':'AMEX:XLI','XLP':'AMEX:XLP','XLB':'AMEX:XLB','XLRE':'AMEX:XLRE','XLE':'AMEX:XLE','XLU':'AMEX:XLU','^RUT':'TVC:RUT','YM=F':'CBOT_MINI:YM1!','RTY=F':'CME_MINI:RTY1!',
    '000001.SS':'SSE:000001','399106.SZ':'SZSE:399106','399001.SZ':'SZSE:399001','000300.SS':'SSE:000300',
    '000688.SS':'SSE:000688','399006.SZ':'SZSE:399006','^HSI':'TVC:HSI','^HSCE':'HSI:HSCEI','HSTECH.HK':'HSI:HSTECH',
    '^N225':'TVC:NI225','^STOXX50E':'TVC:SX5E','^FTSE':'TVC:UKX','^GDAXI':'XETR:DAX','^FCHI':'TVC:CAC40',
    '^BSESN':'BSE:SENSEX','DX-Y.NYB':'TVC:DXY',
    'CL=F':'NYMEX:CL1!','BZ=F':'NYMEX:BZ1!','NG=F':'NYMEX:NG1!','GC=F':'COMEX:GC1!','SI=F':'COMEX:SI1!','HG=F':'COMEX:HG1!',
    'ZC=F':'CBOT:ZC1!','ZS=F':'CBOT:ZS1!','ZW=F':'CBOT:ZW1!','ZR=F':'CBOT:ZR1!','ZO=F':'CBOT:ZO1!',
    'HO=F':'NYMEX:HO1!','PL=F':'NYMEX:PL1!','PA=F':'NYMEX:PA1!','SB=F':'ICEUS:SB1!','ZM=F':'CBOT:ZM1!','ZL=F':'CBOT:ZL1!','CT=F':'ICEUS:CT1!','OJ=F':'ICEUS:OJ1!','KC=F':'ICEUS:KC1!','CC=F':'ICEUS:CC1!',
    'KRW=X':'FX_IDC:USDKRW','JPYKRW=X':'FX_IDC:JPYKRW','CNYKRW=X':'FX_IDC:CNYKRW','EURKRW=X':'FX_IDC:EURKRW',
    'GBPKRW=X':'FX_IDC:GBPKRW','HKDKRW=X':'FX_IDC:HKDKRW','AUDKRW=X':'FX_IDC:AUDKRW','SGDKRW=X':'FX_IDC:SGDKRW',
    'CADKRW=X':'FX_IDC:CADKRW','INRKRW=X':'FX_IDC:INRKRW','IDRKRW=X':'FX_IDC:IDRKRW','BRLKRW=X':'FX_IDC:BRLKRW',
    'TWDKRW=X':'FX_IDC:TWDKRW','CHFKRW=X':'FX_IDC:CHFKRW','NZDKRW=X':'FX_IDC:NZDKRW','SEKKRW=X':'FX_IDC:SEKKRW',
    'CZKKRW=X':'FX_IDC:CZKKRW','CLPKRW=X':'FX_IDC:CLPKRW','TRYKRW=X':'FX_IDC:TRYKRW',
    'EURUSD=X':'FX_IDC:USDEUR','GBPUSD=X':'FX_IDC:USDGBP','JPY=X':'FX:USDJPY','AUDUSD=X':'FX_IDC:USDAUD',
    'MXN=X':'FX_IDC:USDMXN',
    'ZAR=X':'FX_IDC:USDZAR',
    'NOK=X':'FX_IDC:USDNOK',
    'DKK=X':'FX_IDC:USDDKK',
    'PLN=X':'FX_IDC:USDPLN',
    'THB=X':'FX_IDC:USDTHB',
    'PHP=X':'FX_IDC:USDPHP',
    'VND=X':'FX_IDC:USDVND',
    'MYR=X':'FX_IDC:USDMYR',
    'SAR=X':'FX_IDC:USDSAR',
    'AED=X':'FX_IDC:USDAED',
    'ILS=X':'FX_IDC:USDILS',
    'ARS=X':'FX_IDC:USDARS',
    'COP=X':'FX_IDC:USDCOP',
    'HUF=X':'FX_IDC:USDHUF',
    'RUB=X':'FX_IDC:USDRUB',
    'CNY=X':'FX_IDC:USDCNY',
    'HKD=X':'FX_IDC:USDHKD',
    'TWD=X':'FX_IDC:USDTWD',
    'SGD=X':'FX_IDC:USDSGD',
    'CHF=X':'FX_IDC:USDCHF',
    'CAD=X':'FX_IDC:USDCAD',
    'BRL=X':'FX_IDC:USDBRL',
    'TRY=X':'FX_IDC:USDTRY',
    'UAH=X':'FX_IDC:USDUAH',
    'KRW-BTC':'UPBIT:BTCKRW','KRW-ETH':'UPBIT:ETHKRW','KRW-SOL':'UPBIT:SOLKRW','KRW-XRP':'UPBIT:XRPKRW',
    'KRW-ADA':'UPBIT:ADAKRW','KRW-DOGE':'UPBIT:DOGEKRW','KRW-TRX':'UPBIT:TRXKRW','KRW-LINK':'UPBIT:LINKKRW','KRW-AVAX':'UPBIT:AVAXKRW','KRW-SUI':'UPBIT:SUIKRW','KRW-USDT':'UPBIT:USDTKRW'};
  const TX={'399006.SZ':'https://gu.qq.com/sz399006/zs','000688.SS':'https://gu.qq.com/sh000688/zs','HSTECH.HK':'https://gu.qq.com/hkHSTECH/zs'};  // 야후 1년 이력 미제공 3종 — 텐센트로 대체
  const SINA={'SN.LC0':'https://finance.sina.com.cn/futures/quotes/LC0.shtml'};  // GFEX 탄산리튬 — 시나 차트
  function extLinks(r){
    const s=r.s, L=[];
    if(NAVER[s]) L.push(['네이버', NAVER[s].startsWith('http')?NAVER[s]:`https://m.stock.naver.com/${NAVER[s]}`]);
    const NOY=['CNYKRW=X','BRLKRW=X','SEKKRW=X','CZKKRW=X','CLPKRW=X','TRYKRW=X','EURUSD=X','GBPUSD=X','AUDUSD=X'];  // 네이버 고시환율 소스 — 야후 미상장
    if(!s.startsWith('KRX:')&&!s.startsWith('NAV')&&!s.startsWith('ND.')&&!s.startsWith('NF.')&&!s.startsWith('DV.')&&!s.startsWith('SN.')&&!NOY.includes(s)){
      const y=s.startsWith('KRW-')?s.split('-')[1]+'-KRW':s;
      L.push(['야후',`https://finance.yahoo.com/quote/${encodeURIComponent(y)}`]);
    }
    if(TX[s]) L.push(['텐센트',TX[s]]);
    if(SINA[s]) L.push(['시나',SINA[s]]);
    if(TV[s]) L.push(['TradingView',`https://www.tradingview.com/chart/?symbol=${encodeURIComponent(TV[s])}`]);
    if(s.startsWith('KRW-')) L.push(['업비트',`https://upbit.com/exchange?code=CRIX.UPBIT.${s}`]);
    return L;
  }
  window.__gmTblRe=table;
  function findRow(sym){ for(const g of D.groups){ const r=g.rows.find(x=>x.s===sym); if(r) return r; } return null; }
  async function openDetail(sym,keep){
    openSym=sym;
    const r=findRow(sym); if(!r) return;
    if(!HIST) HIST={};
    if(!HIST[sym]){ try{ HIST[sym]=await fetch('/api/global_hist_one?s='+encodeURIComponent(sym)).then(x=>x.ok?x.json():null); }catch(e){} }
    const box=$('gm_detail');
    const R=r.ret||{};
    box.innerHTML=`<div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap;padding:2px 4px">
      <b style="font-size:15px">${r.name}</b>${subCode(r.s)?`<span class="note" style="font-size:11px"> ${subCode(r.s)}</span>`:''}${r.en?`<span class="note" style="font-size:11px"> ${r.en}</span>`:''}<span style="font-size:15px;font-weight:600">${fmt(r.px,r.dec,r.mult)}</span>${pc(R.d1!=null?R.d1:r.ret_d1_live)}
      <span class="note">${r.at||''}</span>
      <span style="margin-left:auto">${extLinks(r).map(([lb,u])=>`<button class="gme" data-u="${u}" style="margin-left:4px;padding:2px 9px;font-size:11px;border:1px solid #d7dce3;background:#fff;color:#333;border-radius:5px;cursor:pointer">${lb} ↗</button>`).join('')}<span style="display:inline-block;width:10px"></span>${['1Y','3Y','10Y','MAX'].map(k=>`<button class="gmp" data-p="${k}" style="margin-left:4px;padding:2px 8px;font-size:11px;border:1px solid #d7dce3;background:${k===(box.dataset.p||'3Y')?'#1f2937':'#fff'};color:${k===(box.dataset.p||'3Y')?'#fff':'#333'};border-radius:5px;cursor:pointer">${k}</button>`).join('')}
      <button id="gm_x" style="margin-left:8px;padding:2px 8px;font-size:11px;border:1px solid #d7dce3;background:#fff;border-radius:5px;cursor:pointer">✕</button></span></div>
      <canvas id="gm_cv" style="width:100%;height:600px"></canvas>`;
    box.querySelectorAll('.gmp').forEach(b=>b.addEventListener('click',()=>{box.dataset.p=b.dataset.p; delete box._vn; delete box._vo; openDetail(sym,true);}));
    if(!keep){ delete box._vn; delete box._vo; }
    box.querySelectorAll('.gme').forEach(b=>b.addEventListener('click',e=>{e.stopPropagation(); window.open(b.dataset.u,'gm_pop','width=1280,height=860');}));
    box.querySelector('#gm_x').addEventListener('click',()=>{openSym=null; box.innerHTML='<div class="note" style="padding:40px 0;text-align:center">👈 왼쪽 표에서 지수/종목을 클릭하면<br>여기에 차트가 표시됩니다</div>';});
    let ov=null, prem=null;
    if(sym==='KRW-USDT'){
      if(!HIST['KRW=X']){ try{ HIST['KRW=X']=await fetch('/api/global_hist_one?s='+encodeURIComponent('KRW=X')).then(x=>x.ok?x.json():null); }catch(e){} }
      ov=HIST['KRW=X'];
      const kr=findRow('KRW=X');
      if(kr&&kr.px&&r.px!=null){ prem=(r.px/kr.px-1)*100;
        const hd=box.querySelector('div');
        if(hd) hd.insertAdjacentHTML('beforeend',`<span class="note" style="font-size:12px">원/달러 ${kr.px.toLocaleString()} 대비 프리미엄 <b class="${prem>1?'up':prem<-1?'dn':''}">${prem>0?'+':''}${prem.toFixed(2)}%</b></span>`);
      }
    }
    const hset=HIST[sym];
    const cv=$('gm_cv');
    if(!hset||!hset.t||hset.t.length<2){ cv.outerHTML='<div class="note" style="padding:14px">이력 없음 — KRX 세부지수는 일별 누적 개시(2026-08-02) 후 차오릅니다.</div>'; return; }
    const L=hset.t.length;
    const dl0=hset.t[L-1];                                   // 기간은 달력 기준(코인은 연 365봉이라 봉수 고정이면 어긋남)
    const nBack=y=>{ const d=new Date(+dl0.slice(0,4),+dl0.slice(4,6)-1,+dl0.slice(6)); d.setDate(d.getDate()-365*y);
      const key=`${d.getFullYear()}${String(d.getMonth()+1).padStart(2,'0')}${String(d.getDate()).padStart(2,'0')}`;
      let i=hset.t.findIndex(z=>z>=key); if(i<0) i=L-1; return Math.max(20,L-i); };
    const baseN={'1Y':nBack(1),'3Y':nBack(3),'10Y':nBack(10),'MAX':L}[box.dataset.p||'3Y'];  // 기본 3Y
    let viewN=Math.max(20,Math.min(box._vn||baseN,L));       // 표시 봉수(휠 확대/축소로 변경)
    let viewOff=Math.max(0,Math.min(box._vo||0,L-viewN));    // 오른쪽 끝에서 숨긴 봉수(드래그 이동)
    const W=cv.clientWidth||560,H=600; cv.width=W; cv.height=H;
    const x=cv.getContext('2d');
    const P={l:56,r:8,t:10,b:20};
    let om=null;
    if(ov&&ov.t){ om={}; ov.t.forEach((d,i)=>om[d]=ov.v[i]); }
    function draw(){
      const end=L-viewOff, start=Math.max(0,end-viewN);
      const t=hset.t.slice(start,end), v=hset.v.slice(start,end).map(z=>z*(r.mult||1));
      if(t.length<2) return;
      x.clearRect(0,0,W,H);
      const ovv=om?t.map(d=>om[d]??null):null;
      const allv=ovv?v.concat(ovv.filter(z=>z!=null)):v;
      const lo=Math.min(...allv),hi=Math.max(...allv),rg=(hi-lo)||1;
      const X=i=>P.l+(W-P.l-P.r)*i/(t.length-1), Y=val=>P.t+(H-P.t-P.b)*(1-(val-lo)/rg);
      x.font='10px sans-serif';
      for(let g2=0;g2<=4;g2++){ const y=P.t+(H-P.t-P.b)*g2/4;
        x.strokeStyle='#eceff3'; x.beginPath(); x.moveTo(P.l,y); x.lineTo(W-P.r,y); x.stroke();
        x.fillStyle='#8a94a0'; x.textAlign='right'; x.fillText((hi-rg*g2/4).toLocaleString(undefined,{maximumFractionDigits:r.dec}),P.l-5,y+3); }
      x.textAlign='left'; let lastM='';
      for(let i=0;i<t.length;i++){ const mk=t[i].slice(0,6); if(mk!==lastM){ lastM=mk;
        if(t.length<=140||(t.length<=600?+t[i].slice(4,6)%3===1:+t[i].slice(4,6)===1)){ x.fillStyle='#8a94a0'; x.fillText(`${t[i].slice(2,4)}.${t[i].slice(4,6)}`,X(i)-8,H-6); } } }
      // 표시 구간이 1년을 넘으면 — 지금(전체 이력 마지막 봉) 기준 1년 전·2년 전·… 점선 세로선
      const dl=hset.t[L-1], d0=new Date(+dl.slice(0,4),+dl.slice(4,6)-1,+dl.slice(6));
      for(let k=1;k<=20;k++){
        const tg=new Date(d0); tg.setDate(tg.getDate()-365*k);
        const key=`${tg.getFullYear()}${String(tg.getMonth()+1).padStart(2,'0')}${String(tg.getDate()).padStart(2,'0')}`;
        if(key<=t[0]||key>t[t.length-1]) continue;
        const idx=t.findIndex(z=>z>=key);
        if(idx>0){ x.save(); x.setLineDash([4,4]); x.strokeStyle='#9aa4b0'; x.beginPath(); x.moveTo(X(idx),P.t); x.lineTo(X(idx),H-P.b); x.stroke(); x.restore();
          x.fillStyle='#8a94a0'; x.textAlign='center'; x.fillText(`${k}년 전`,X(idx),P.t+10); x.textAlign='left'; }
      }
      if(ovv){ x.strokeStyle='#6b7280'; x.lineWidth=1.2; x.beginPath(); let st=false;
        ovv.forEach((val,i)=>{ if(val==null) return; st?x.lineTo(X(i),Y(val)):(x.moveTo(X(i),Y(val)),st=true); }); x.stroke();
        x.font='11px sans-serif'; x.fillStyle='#6b7280'; x.fillText('원/달러 환율',P.l+6,P.t+14);
        x.fillStyle='#c0392b'; x.fillText('테더 USDT/KRW',P.l+6,P.t+28); x.font='10px sans-serif'; }
      const up=v[v.length-1]>=v[0];
      x.strokeStyle=up?'#c0392b':'#1e6fd6'; x.lineWidth=1.6; x.beginPath();
      v.forEach((val,i)=>i?x.lineTo(X(i),Y(val)):x.moveTo(X(i),Y(val))); x.stroke(); x.lineWidth=1;
    }
    draw();
    cv.addEventListener('wheel',e=>{                          // 휠 = X축 확대/축소(마우스 위치 고정)
      e.preventDefault();
      const rect=cv.getBoundingClientRect();
      const fr=Math.min(1,Math.max(0,(e.clientX-rect.left-P.l)/(W-P.l-P.r)));
      const end=L-viewOff, start=Math.max(0,end-viewN), n0=end-start;
      const anchor=start+fr*(n0-1);
      const n1=Math.max(20,Math.min(L,Math.round(n0*(e.deltaY<0?0.8:1.25))));
      let s1=Math.round(anchor-fr*(n1-1));
      s1=Math.max(0,Math.min(L-n1,s1));
      viewN=n1; viewOff=L-s1-n1; box._vn=viewN; box._vo=viewOff;
      draw();
    },{passive:false});
    let drag=null;                                            // 드래그 = 좌우 이동
    cv.addEventListener('mousedown',e=>{ drag={x0:e.clientX,off0:viewOff}; });
    cv.addEventListener('mousemove',e=>{ if(!drag) return;
      const barw=(W-P.l-P.r)/Math.max(1,viewN);
      viewOff=Math.max(0,Math.min(L-viewN,drag.off0+Math.round((e.clientX-drag.x0)/barw)));
      box._vo=viewOff; draw(); });
    cv.addEventListener('mouseup',()=>{ drag=null; });
    cv.addEventListener('mouseleave',()=>{ drag=null; });
  }
  async function load(){
    try{ D=await fetch('/api/db/global_market').then(r=>r.json()); }catch(e){ $('gm_body').innerHTML='<div class="note">로드 실패 — 잠시 후 재시도</div>'; return; }
    table();  }
  window.__gmPopRe=null;
  async function loadPop(){
    window.__gmPopRe=loadPop;
    if(!$('gm_pop')) return;
    try{
      const P=await fetch('/api/popular').then(r=>r.json());
      if(!P.rows||!P.rows.length) return;
      const lim=window.__gmPopAll?30:10;
      $('gm_pop_t').textContent=`(네이버 · ${P.asof||''} 기준 · 3분 갱신)`;
      $('gm_pop').innerHTML='<table style="width:100%;border-collapse:collapse;font-size:12px">'+
        P.rows.slice(0,lim).map((r,i)=>`<tr style="cursor:pointer;border-bottom:1px solid #f2f4f7" onclick="window.open('https://m.stock.naver.com/domestic/stock/${r.code}/total','gm_pop_w','width=480,height=860')">
          <td style="padding:4px 4px;width:22px;color:#8a94a0">${i+1}</td>
          <td style="padding:4px 2px"><b>${r.name}</b></td>
          <td style="text-align:right;font-weight:600">${r.px!=null?r.px.toLocaleString():'—'}</td>
          <td style="text-align:right;width:76px"><span class="${r.pct>0?'up':r.pct<0?'dn':''}">${r.pct>0?'+':''}${r.pct??'—'}%</span></td></tr>`).join('')+'</table>'+(P.rows.length>10?`<div style="text-align:center;margin-top:4px"><button onclick="window.__gmPopAll=!window.__gmPopAll; window.__gmPopRe&&window.__gmPopRe()" id="gm_pop_more" style="padding:2px 12px;font-size:11px;border:1px solid #d7dce3;background:#fff;border-radius:5px;cursor:pointer">${window.__gmPopAll?'접기 ▲':'더보기(30위까지) ▼'}</button></div>`:'');
    }catch(e){}
  }
  window.renderGlobal=function(){
    load(); loadPop();
    if(timer) clearInterval(timer);
    timer=setInterval(()=>{ const p=document.getElementById('p_global');
      if(p&&p.style.display!=='none'&&p.offsetParent!==null){ HIST=null; load(); } },300000);
    setInterval(()=>{ const p=document.getElementById('p_global'); if(p&&p.offsetParent!==null) loadPop(); },180000);
  };
})();
