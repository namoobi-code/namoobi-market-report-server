const $=id=>document.getElementById(id);
const esc=s=>String(s??'').replace(/[<>&]/g,c=>({'<':'&lt;','>':'&gt;','&':'&amp;'}[c]));

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
    fetch('/api/bundle').then(r=>r.json()),
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
    ['s3111','3.1.11 반도체'],['s3113','3.1.13 파생'],['s3114','3.1.14 유동성'],['d332','3.3.2 리밸런싱'],['s32','3.2 KRX'],['d6','6 크립토'],['s78','7.8 네이버'],
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
    const m=cs.months.slice(-24), n=cs.months.length;
    const cut=a=>(a||[]).slice(n-24).map(v=>v!=null?v/1000:null);
    mk($('c_cus_t'),m,[{n:'1~10일',d:cut(cs.series.total.p10),c:C.b},{n:'1~20일',d:cut(cs.series.total.p20),c:C.o},
      {n:'월전체',d:cut(cs.series.total.pm),c:C.r}],{legend:true,bar:true});
    mk($('c_cus_s'),m,[{n:'1~10일',d:cut(cs.series.semiconductor.p10),c:C.b},{n:'1~20일',d:cut(cs.series.semiconductor.p20),c:C.o},
      {n:'월전체',d:cut(cs.series.semiconductor.pm),c:C.r}],{legend:true,bar:true});
    const it=[['total','전체'],['semiconductor','반도체'],['steel','철강'],['car','승용차'],['petroleum','석유'],
      ['wireless','무선통신'],['ship','선박'],['autoparts','자동차부품'],['computer','컴퓨터주변기기']];
    const P=['p10','p20','pm'],PN=['1~10일','1~20일','월전체'];
    $('cus_tbl').innerHTML=`<tr><th>품목</th>${PN.map(x=>`<th style="text-align:right">${x}</th>`).join('')}</tr>`+
      it.map(([k,lab])=>`<tr><td><b>${lab}</b></td>${P.map(p=>{const v=cs.latest[p]?.[k];
        return `<td class="num">${v!=null?(v/1000).toLocaleString(undefined,{maximumFractionDigits:0}):'—'}</td>`;}).join('')}</tr>`).join('')+
      `<tr><td colspan="4" class="note">${esc(cs.latest.yyyymm)} 기준 · 백만 달러</td></tr>`;
  }

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
    $('deriv_t').innerHTML=`<tr><th>지표</th>${names.map(n=>`<th colspan="2" style="text-align:center">${esc(n)}</th>`).join('')}</tr>
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
    $('berk_sum').innerHTML=`<b>${esc(bk.quarter)}</b> · 공시 ${esc(bk.filing_date)}<br>${esc(bk.summary)}<br><br><b>현금:</b> ${esc(bk.cash)}`;
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
    berkshire:'버크셔 해서웨이 13F 보유지분 변동 — 신규매수/확대/축소/청산·현금 (분기)',
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
    ta_flag:'TradingAgents 스크리닝 완료 플래그 — 거래일·완료 여부'};
  // (2026-07-17) 수집 주체 — 🖥 서버 cron 자체 수집(리포트 실행과 무관하게 최신) vs 📄 리포트 실행 시 수집
  const SRV={customs:'06:35·15:35',leading:'06:35·15:35',series_leading:'06:35·15:35',krx_brief:'06:35·15:35',
    series_hy_oas:'06:35·15:35',memory:'06:45·15:45',kr_liquidity:'06:35·14:10·16:10',
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
  function renderMonthCal(mk){
    const grid=document.getElementById('mc_grid'); if(!grid) return;
    const done=pool=>{
      const evs={};
      for(const r of (pool[mk]||[])) if(r.ed) (evs[r.ed]=evs[r.ed]||[]).push(r);
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
        const chips=list.slice(0,4).map(r=>`<span class="mc-chip" title="${esc(mk==='kr'?r.n:((r.kn?r.kn+' · ':'')+r.n))} (${esc(r.c)}) 실적발표">${esc(mk==='kr'?r.n:(r.kn||r.c))}</span>`).join('')
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
        pop.innerHTML=`<div class="mc-pop-in"><div class="mc-pop-h">
            <b>📅 ${key} (${wdn}) 실적발표 — ${list.length}종</b>
            <span class="note" style="margin-left:auto">시가총액순</span>
            <button class="cp-x" id="mcp_x">닫기 ✕</button></div>
          <div class="mc-pop-list">${list.map((r,i)=>
            `<div class="mc-pi" title="${esc(r.n)} (${esc(r.c)})"><span class="note">${i+1}.</span> <b>${esc(mk==='kr'?r.n:r.c)}</b> ${mk==='us'&&r.kn?`<b class="uskn">${esc(r.kn)}</b> `:''}<span class="note">${esc(mk==='kr'?r.c:r.n)}</span></div>`).join('')}
          </div></div>`;
        pop.onclick=e=>{ if(e.target===pop) pop.remove(); };
        pop.querySelector('#mcp_x').onclick=()=>pop.remove();
        document.addEventListener('keydown',function esc0(e){ if(e.key==='Escape'){ pop.remove(); document.removeEventListener('keydown',esc0); } });
        document.body.appendChild(pop);
      });
      document.getElementById('mc_title').textContent=`${mcY}년 ${mcM+1}월`;
      document.getElementById('mc_note').textContent=
        (mk==='kr'?'네이버 IR 일정(대형주 위주)':'Yahoo earnings date')+` · 이 달 실적발표 ${cnt}건 · 셀당 최대 4종(시총순)`;
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
  const panes=['p_welcome','p_daily','p_db','p_ai','p_ta','p_auto','p_fire','p_screener','p_vis','p_cal','p_etf'];
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
      <div class="s">${(FS.report.full_summary||[]).map(x=>
        `<div style="margin-top:8px"><b>${E(x.section||'')}</b>${bullets(x.points)}</div>`).join('')}</div>
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
      </div><div class="src">${E(v.comment||'')}</div></div>`;}).join('');

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
      rev:{label:'리비전',fmt:v=>v.toFixed(0)+'%',min:1,reqData:1,presets:[['전체',null],['상향(0% ↑)',0],['5% ↑',5],['10% ↑',10]],def:[null,null]},
      nan:{label:'애널수',fixed:'— (KR 미제공)'},
      cov:{label:'목표주가',tgl:1,def:false,tglLabel:'컨센서스 있는 종목만'},
      per:{label:'PER',fmt:v=>v.toFixed(1)+'배',presets:[['전체',null,null],['10배 ↓',null,10],['15배 ↓',null,15],['20배 ↓',null,20]],def:[null,null]},
      pbr:{label:'PBR',fmt:v=>v.toFixed(1)+'배',presets:[['전체',null,null],['1배 ↓',null,1],['2배 ↓',null,2],['3배 ↓',null,3]],def:[null,null]},
      divy:{label:'배당',fmt:v=>v.toFixed(1)+'%',min:1,presets:[['전체',null],['1% ↑',1],['2% ↑',2],['3% ↑',3]],def:[null,null]},
      grw:{label:'성장',fmt:v=>v.toFixed(0)+'%',min:1,presets:[['전체',null],['0% ↑',0],['10% ↑',10],['20% ↑',20],['50% ↑',50]],def:[null,null]},
      mom:{label:'수익률 12M',fmt:v=>v.toFixed(0)+'%',min:1,presets:[['전체',null],['0% ↑',0],['50% ↑',50],['100% ↑',100],['200% ↑',200]],def:[null,null]},
      r1m:{label:'수익률 1M',fmt:v=>(v>=0?'+':'')+v.toFixed(0)+'%',min:1,reqData:1,presets:[['전체',null],['0% ↑',0],['10% ↑',10],['20% ↑',20]],def:[null,null]},
      r3m:{label:'수익률 3M',fmt:v=>(v>=0?'+':'')+v.toFixed(0)+'%',min:1,reqData:1,presets:[['전체',null],['0% ↑',0],['20% ↑',20],['50% ↑',50]],def:[null,null]},
      r6m:{label:'수익률 6M',fmt:v=>(v>=0?'+':'')+v.toFixed(0)+'%',min:1,reqData:1,presets:[['전체',null],['0% ↑',0],['30% ↑',30],['50% ↑',50],['100% ↑',100]],def:[null,null]},
      vol20:{label:'변동성(20일)',fmt:v=>v.toFixed(1)+'%',reqData:1,presets:[['전체',null,null],['2% ↓(안정)',null,2],['3% ↓',null,3],['5% ↑(고변동)',5,null]],def:[null,null]},
      hi:{label:'고점比',fmt:v=>'고점 '+v.toFixed(0)+'%',min:1,presets:[['전체',null],['-10% 이내',-10],['-20% 이내',-20],['-30% 이내',-30]],def:[null,null]},
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
      mgrw:{label:'매출성장',fmt:v=>v.toFixed(0)+'%',min:1,reqData:1,presets:[['전체',null],['0% ↑',0],['10% ↑',10],['20% ↑',20],['50% ↑',50]],def:[null,null]},
      ogrw:{label:'이익성장',fmt:v=>v.toFixed(0)+'%',min:1,reqData:1,presets:[['전체',null],['0% ↑',0],['20% ↑',20],['50% ↑',50],['100% ↑',100]],def:[null,null]},
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
      ern:{label:'어닝임박',fmt:v=>'D-'+v.toFixed(0)+' 이내',reqData:1,presets:[['전체',null,null],['D-7 이내',0,7],['D-14 이내',0,14],['D-30 이내',0,30]],def:[null,null]},
      frgn:{label:'외인보유비중',fmt:v=>v.toFixed(0)+'%',min:1,reqData:1,presets:[['전체',null],['10% ↑',10],['30% ↑',30],['50% ↑',50]],def:[null,null]},
      payout:{label:'배당성향',fmt:v=>v.toFixed(0)+'%',min:1,reqData:1,presets:[['전체',null],['10% ↑',10],['30% ↑',30],['50% ↑',50]],def:[null,null]}
    },
    us:{
      sector:{label:'섹터',cat:1},
      chg:{label:'등락',fmt:v=>v.toFixed(1)+'%',presets:[['전체',null,null],['상승(0% ↑)',0,null],['+3% ↑',3,null],['하락(0% ↓)',null,0],['−3% ↓',null,-3]],def:[null,null]},
      cap:{label:'시가총액',fmt:usdF,presets:[['전체',null,null],['$200B ↑',2e11,null],['$10~200B',1e10,2e11],['$2~10B',2e9,1e10],['$300M~2B',3e8,2e9],['$300M ↓',null,3e8]],def:[2e9,null]},
      tv:{label:'거래대금',fmt:usdF,min:1,presets:[['전체',null],['$50M ↑',5e7],['$20M ↑',2e7],['$5M ↑',5e6]],def:[2e7,null]},
      px:{label:'가격',fmt:usdF,min:1,presets:[['전체',null],['$5 ↑',5],['$10 ↑',10],['$50 ↑',50]],def:[5,null]},
      age:{label:'상장기간',fmt:v=>v+'년',min:1,presets:[['전체',null],['1년 ↑',1],['3년 ↑',3],['5년 ↑',5],['10년 ↑',10]],def:[1,null]},
      sec:{label:'증권 구분',fixed:'EQUITY만(ETF·워런트 제외)'},
      opLoss:{label:'영업적자',exclGE:1,maxOnly:1,fmt:v=>v.toFixed(0)+'년이상 제외',presets:[['전체',null,null],['1년이상 제외',null,1],['2년이상 제외',null,2],['3년이상 제외',null,3]],def:[null,3]},
      de:{label:'부채비율',fmt:v=>v.toFixed(0)+'%',fin:1,presets:[['전체',null,null],['100% ↓',null,100],['200% ↓',null,200],['300% ↓',null,300]],def:[null,300]},
      cr:{label:'유동비율',fmt:v=>v.toFixed(1),min:1,fin:1,presets:[['전체',null],['0.8 ↑',0.8],['1.0 ↑',1.0],['1.5 ↑',1.5]],def:[0.8,null]},
      upside:{label:'상승여력',fmt:v=>v.toFixed(0)+'%',min:1,reqData:1,presets:[['전체',null],['0% ↑',0],['10% ↑',10],['20% ↑',20],['50% ↑',50]],def:[null,null]},
      rec:{label:'투자의견',fmt:v=>'매수강도 '+v.toFixed(0),min:1,reqData:1,presets:[['전체',null],['매수 이상',65],['강력매수',85]],def:[null,null]},
      rev:{label:'리비전',fmt:v=>v.toFixed(0)+'%',min:1,reqData:1,presets:[['전체',null],['상향(0% ↑)',0],['5% ↑',5],['10% ↑',10]],def:[null,null]},
      nan:{label:'애널수',fmt:v=>v.toFixed(0)+'명',min:1,reqData:1,presets:[['전체',null],['1명 ↑',1],['3명 ↑',3],['10명 ↑',10]],def:[null,null]},
      cov:{label:'목표주가',tgl:1,def:false,tglLabel:'컨센서스 있는 종목만'},
      per:{label:'PER',fmt:v=>v.toFixed(1)+'배',presets:[['전체',null,null],['10배 ↓',null,10],['15배 ↓',null,15],['20배 ↓',null,20]],def:[null,null]},
      pbr:{label:'PBR',fmt:v=>v.toFixed(1)+'배',presets:[['전체',null,null],['1배 ↓',null,1],['2배 ↓',null,2],['3배 ↓',null,3]],def:[null,null]},
      divy:{label:'배당',fmt:v=>v.toFixed(1)+'%',min:1,presets:[['전체',null],['1% ↑',1],['2% ↑',2],['3% ↑',3]],def:[null,null]},
      grw:{label:'성장',fmt:v=>v.toFixed(0)+'%',min:1,presets:[['전체',null],['0% ↑',0],['10% ↑',10],['20% ↑',20],['50% ↑',50]],def:[null,null]},
      mom:{label:'수익률 12-1M',fmt:v=>v.toFixed(0)+'%',min:1,presets:[['전체',null],['0% ↑',0],['50% ↑',50],['100% ↑',100],['200% ↑',200]],def:[null,null]},
      r1m:{label:'수익률 1M',fmt:v=>(v>=0?'+':'')+v.toFixed(0)+'%',min:1,reqData:1,presets:[['전체',null],['0% ↑',0],['10% ↑',10],['20% ↑',20]],def:[null,null]},
      r3m:{label:'수익률 3M',fmt:v=>(v>=0?'+':'')+v.toFixed(0)+'%',min:1,reqData:1,presets:[['전체',null],['0% ↑',0],['20% ↑',20],['50% ↑',50]],def:[null,null]},
      r6m:{label:'수익률 6M',fmt:v=>(v>=0?'+':'')+v.toFixed(0)+'%',min:1,reqData:1,presets:[['전체',null],['0% ↑',0],['30% ↑',30],['50% ↑',50],['100% ↑',100]],def:[null,null]},
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
      ern:{label:'어닝임박',fmt:v=>'D-'+v.toFixed(0)+' 이내',reqData:1,presets:[['전체',null,null],['D-7 이내',0,7],['D-14 이내',0,14],['D-30 이내',0,30]],def:[null,null]},
      hi:{label:'고점比',fmt:v=>'고점 '+v.toFixed(0)+'%',min:1,presets:[['전체',null],['-10% 이내',-10],['-20% 이내',-20],['-30% 이내',-30]],def:[null,null]},
      v200:{label:'200일선',fmt:v=>(v>=0?'+':'')+v.toFixed(0)+'%',min:1,presets:[['전체',null],['−30% ↑',-30],['−20% ↑',-20],['−10% ↑',-10],['위(0%) ↑',0],['+10% ↑',10],['+20% ↑',20]],def:[-30,null]},
      v20:{label:'20일선',fmt:v=>(v>=0?'+':'')+v.toFixed(0)+'%',min:1,reqData:1,presets:[['전체',null],['위(0%) ↑',0],['−5% ↑',-5],['+5% ↑',5]],def:[null,null]},
      v50:{label:'50일선',fmt:v=>(v>=0?'+':'')+v.toFixed(0)+'%',min:1,reqData:1,presets:[['전체',null],['위(0%) ↑',0],['−10% ↑',-10],['+10% ↑',10]],def:[null,null]},
      align:{label:'이평배열',cat:1,opts:['정배열','역배열','혼조'],hint:{'정배열':['up','상승 추세'],'역배열':['dn','하락 추세'],'혼조':['neu','전환 구간']}},
      rsi:{label:'RSI(14)',fmt:v=>'RSI '+v.toFixed(0),reqData:1,presets:[['전체',null,null],['과매도(≤30)',null,30],['30~50',30,50],['50 ↑(모멘텀)',50,null],['과매수 제외(≤70)',null,70],['과매수(≥70)',70,null]],def:[null,null]},
      volx:{label:'거래량배수',fmt:v=>v.toFixed(1)+'배',min:1,reqData:1,presets:[['전체',null],['1.5배 ↑',1.5],['2배 ↑',2],['3배 ↑',3]],def:[null,null]},
      macd:{label:'MACD',cat:1,opts:['골든↑','골든↓','데드↑','데드↓'],disp:MACD_DISP,hint:{'골든↑':['up','강한 상승'],'골든↓':['up','상승 전환'],'데드↑':['dn','하락 전환'],'데드↓':['dn','강한 하락']}},
      bb:{label:'볼린저밴드',fmt:v=>'%b '+v.toFixed(0),reqData:1,presets:[['전체',null,null],['하단권(≤20)',null,20],['중심 위(≥50)',50,null],['상단권(≥80)',80,null],['상단 돌파(≥100)',100,null]],def:[null,null]},
      roe:{label:'ROE',fmt:v=>v.toFixed(0)+'%',min:1,reqData:1,presets:[['전체',null],['5% ↑',5],['10% ↑',10],['15% ↑',15],['20% ↑',20]],def:[null,null]},
      mgrw:{label:'매출성장',fmt:v=>v.toFixed(0)+'%',min:1,reqData:1,presets:[['전체',null],['0% ↑',0],['10% ↑',10],['20% ↑',20],['50% ↑',50]],def:[null,null]},
      ogrw:{label:'이익성장',fmt:v=>v.toFixed(0)+'%',min:1,reqData:1,presets:[['전체',null],['0% ↑',0],['20% ↑',20],['50% ↑',50],['100% ↑',100]],def:[null,null]},
      frgn:{label:'외인보유비중',fixed:'— (US 미제공)'},
      payout:{label:'배당성향',fmt:v=>v.toFixed(0)+'%',min:1,reqData:1,presets:[['전체',null],['10% ↑',10],['30% ↑',30],['50% ↑',50]],def:[null,null]}
    }
  };
  /* 나열 순서 = 표시 컬럼 순서와 동일. 컬럼이 없는 필터(증권 구분)는 맨 뒤에 배치 */
  const KEYS=['mk','sector','px','chg','cap','tv','de','cr','opLoss','age',
              /* (2026-07-21) 이동평균은 기간 오름차순으로 — 20일 → 50일 → 200일 */
              'v20','v50','v200','align','rsi','adx','volx','turn','macd','bb',
              /* (2026-07-21) 수익률 1Y 제거 — 미국은 mom(수익률 12-1M)이 52주 변화율로 산출돼
                 r1y 와 사실상 동일값이었다(실측 ALKS +98/+97.7 · AEHR +393/+392.7 · NAVN +30/+29.8).
                 중복 컬럼을 없애고 mom 을 1Y 가 있던 자리(6M 뒤)로 옮긴다. */
              'r1m','r3m','r6m','mom','vol20','hi','frgn','fnb20','onb20','fst','ost','sr','lbr',
              'ern','cov','upside','rec','rev','nan',
              'grw','mgrw','ogrw','tob','opm','per','peg','pbr','psr','roe','payout','divy','sec'];
  const FK2CK={rec:'recn', mgrw:'revg', ogrw:'opg', cov:'tp', opLoss:'oploss'};   // 필터키 → 컬럼키(값 접근자 공통화)
  let POOL={kr:[],us:[]}, mkt='kr', F={}, sort={k:'cap',d:-1}, loaded=false;

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
  function loadF(){ if(!F_ST[mkt]) F_ST[mkt]=buildF();           // 마켓 전환 → 저장분 로드(원복 안함)
    else { const df=buildF();
      for(const k in df) if(!(k in F_ST[mkt])) F_ST[mkt][k]=df[k];        // 신규 필터키 백필
      for(const k in F_ST[mkt]) if(!(k in df)) delete F_ST[mkt][k]; }     // 없어진 필터키 정리(구버전 세션 호환)
    F=F_ST[mkt]; }
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
        continue; }
      if(f.cat){ if(st.v!=null && String(r[k]||'')!==st.v) return false; continue; }
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
  function chipLabel(k){ const f=DEF[mkt][k], st=F[k]||{};
    if(f.fixed!==undefined) return `${f.label}: <span class="cv">${E(f.fixed)}</span>`;
    if(f.tgl) return `${f.label}: <span class="cv">${st.on?'ON':'OFF'}</span>`;
    if(f.cat) return `${f.label}: <span class="cv">${E(dispOpt(f,st.v)||'전체')}</span>`;
    if(f.exclGE) return `${f.label}: <span class="cv">${st.max==null?'전체':st.max+'년이상 제외'}</span>`;
    const lo=st.min, hi=st.max;
    let v = (lo==null&&hi==null)?'전체' : (hi==null?f.fmt(lo)+' ↑' : (lo==null?f.fmt(hi)+' ↓' : f.fmt(lo)+'~'+f.fmt(hi)));
    return `${f.label}: <span class="cv">${E(v)}</span>`; }

  /* (2026-07-22) 결과표 UI 옵션 — 종목 클릭 시 상세로 자동이동(기본 ON) · 스크롤 전 표시 행수(기본 8). localStorage 유지. */
  let autoScroll = localStorage.getItem('scr_autoscroll') !== '0';
  let visRows = Math.max(1, Math.min(60, +localStorage.getItem('scr_visrows') || 8));
  function applyTblHeight(){
    const w=document.getElementById('scr_tblwrap'); if(!w) return;
    const tbl=document.getElementById('scr_tbl');
    const hd=tbl&&tbl.querySelector('th'); const row=tbl&&tbl.querySelector('tr[data-c]');
    const hH = hd&&hd.parentElement ? hd.parentElement.offsetHeight : 34;
    const rH = row ? row.offsetHeight : 48;
    w.style.maxHeight = (hH + visRows*rH + 2) + 'px';
  }
  /* (2026-07-18) START·컬럼설정·필터설명·초기화 그룹 위치 — 1단계=필터 바 우측 끝, 2·3단계=상단 원위치 */
  const BTNS_GRP=document.getElementById('scr_btns_grp');
  function placeBtns(){ if(!BTNS_GRP) return;
    const tgt = stage===1 ? $('scr_fltbar') : document.querySelector('.scrtop');
    if(tgt && BTNS_GRP.parentElement!==tgt) tgt.appendChild(BTNS_GRP);
    /* (2026-07-26) 컬럼설정·START·초기화·전부전체 = 1단계 전용.
       ? 필터설명은 2단계에서도 필요(V·G·M·Q 설명) — 패널을 현재 단계 pane 으로 옮긴다 */
    BTNS_GRP.style.display = stage===1?'':'none';
    /* (2026-07-26) START 소실 근본 원인 수정 — .scrbtns-r 이 문서에 2개(필터설명 행 + START 래퍼).
       3단계에서 BTNS_GRP 가 .scrtop 으로 이동하면 문서 순서가 바뀌어 querySelector 가
       START 래퍼를 잡아 none 처리했었다 → 필터설명 행은 id(scr_glsrow)로 정확히 지정,
       START 래퍼는 항상 표시로 복구 */
    {const inner=BTNS_GRP.querySelector('.scrbtns-r'); if(inner) inner.style.display='';}
    {const rb=document.getElementById('scr_glsrow'); if(rb) rb.style.display = stage<=2?'':'none';}
    {const gb=$('scr_glsbtn'); if(gb) gb.style.display = stage<=2?'':'none';}   // 3단계: 필터설명도 제거
    {const rs=$('scr_rst');  if(rs) rs.style.display = stage===1?'':'none';}
    {const ab=$('scr_allf'); if(ab) ab.style.display = stage===1?'':'none';}
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
    const n=String(r.n||'').toLowerCase(), c=String(r.c||'').toLowerCase();
    return groups.some(g=>g.every(t=>n.includes(t)||c.includes(t)));
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
      const st=F[k]; const active = f.tgl? st.on : (f.cat? st.v!=null : (st.min!=null||st.max!=null));
      let pop;
      if(f.cat){
        const _opts=f.opts?['',...f.opts]:catOpts(k);   // (2026-07-18) 고정 옵션 지원 — 데이터 도착 전에도 선택지 표시
        /* (2026-07-21) 상태값 옵션에 주식 관점 방향(상승/하락)을 배지로 붙인다.
           '골든↓' 처럼 화살표만 봐서는 우호/비우호가 직관적이지 않다는 지적 반영.
           색은 화면 전체 규칙과 동일 — 빨강=주식 우호, 파랑=비우호, 회색=중립. */
        pop=`<div class="pl">선택</div>`+_opts.map(o=>{
          const h=(f.hint||{})[o];
          const tag=h?`<span class="ohint ${h[0]}">${E(h[1])}</span>`:'';
          return `<button class="preset ohas ${st.v===(o||null)?'sel':''}" data-cat="${k}" data-v="${E(o)}">${E(dispOpt(f,o)||'전체')}${tag}</button>`;
        }).join('');
      } else if(f.tgl){
        pop=`<label class="tgl"><input type="checkbox" data-tgl="${k}" ${st.on?'checked':''}> ${E(f.tglLabel)}</label>`;
      } else {
        pop=`<div class="pl">프리셋</div>`+f.presets.map((p,pi)=>{
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
    $('scr_fltbar').querySelectorAll('.preset').forEach(b=>b.onclick=()=>{
      const k=b.dataset.k; F[k]={min:b.dataset.lo===''?null:+b.dataset.lo, max:b.dataset.hi===''?null:+b.dataset.hi}; apply(); });
    $('scr_fltbar').querySelectorAll('[data-man]').forEach(inp=>inp.oninput=()=>{
      const k=inp.dataset.man; F[k][inp.dataset.mm]= inp.value===''?null:+inp.value;
      const btn=document.querySelector(`[data-chip="${k}"]`);
      if(btn){ btn.innerHTML=chipLabel(k); btn.classList.toggle('act', F[k].min!=null||F[k].max!=null); }
      applyTable(); });
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
    hi:{l:'고점比',n:1,m:'both'}, frgn:{l:'외인보유비중',n:1,m:'kr'},
    fnb20:{l:'외인수급(20일)',n:1,m:'kr'}, onb20:{l:'기관수급(20일)',n:1,m:'kr'},
    fst:{l:'외인연속매수',n:1,m:'kr'}, ost:{l:'기관연속매수',n:1,m:'kr'},
    sr:{l:'공매도비중',n:1,m:'kr'}, lb:{l:'대차잔고',n:1,m:'kr'}, lbr:{l:'대차잔고비율',n:1,m:'kr'},
    ern:{l:'어닝일',n:1,m:'both'},
    tob:{l:'흑자전환',n:0,m:'kr'}, opm:{l:'영업이익률',n:1,m:'both'},
    peg:{l:'PEG',n:1,m:'both'}, psr:{l:'PSR',n:1,m:'both'},
    tp:{l:'목표주가',n:1,m:'both'}, upside:{l:'상승여력',n:1,m:'both'},
    recn:{l:'투자의견',n:1,m:'both'}, rev:{l:'리비전',n:1,m:'both'}, nan:{l:'애널수',n:1,m:'us'},
    grw:{l:'성장',n:1,m:'both'}, revg:{l:'매출성장',n:1,m:'both'}, opg:{l:'이익성장',n:1,m:'both'},
    per:{l:'PER',n:1,m:'both'}, pbr:{l:'PBR',n:1,m:'both'}, roe:{l:'ROE',n:1,m:'both'},
    payout:{l:'배당성향',n:1,m:'both'}, divy:{l:'배당',n:1,m:'both'}
  };
  const cl =k=>CDEF[k].l;   // 표 헤더 = 패널 = 필터, 모두 동일 라벨
  const cpl=cl;
  const CALL=Object.keys(CDEF);
  /* '추가 가능' 목록 정렬 = 필터가 없는 컬럼 먼저(종목·시장·섹터·등락·목표주가)
     → 그다음은 위 필터 바(KEYS)와 동일한 순서로 나열 */
  const CK2FK={}; for(const fk of KEYS){ const ck=FK2CK[fk]||fk; if(CDEF[ck]) CK2FK[ck]=fk; }
  const CORDER=CALL.filter(k=>!CK2FK[k])
                   .concat(KEYS.map(fk=>FK2CK[fk]||fk).filter(ck=>CDEF[ck]));
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
      const kr=d.kr.filter(k=>CDEF[k]), us=d.us.filter(k=>CDEF[k]);   // 모르는/폐기된 키 제거
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
      case 'fnb20': return r.fnb20; case 'onb20': return r.onb20;   // 억원
      case 'fst': return r.fst; case 'ost': return r.ost;           // 연속일
      case 'sr': return r.sr;                                       // 공매도 비중(%)
      case 'lb': return r.lb;                                        // 대차잔고 금액(억원)
      case 'lbr': return r.lbr;                                      // 대차잔고비율(%)
      case 'ern': {                                                 // 어닝까지 D-day (지난 발표는 제외)
        if(!r.ed) return null;
        const t=new Date(); t.setHours(0,0,0,0);
        const d=Math.round((new Date(r.ed+'T00:00:00')-t)/86400000);
        return d>=0?d:null; }
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
      return `<span class="${v<=7?'up':''}">${v===0?'오늘':'D-'+v}</span> <span class="note">${E((r.ed||'').slice(5))}</span>`;}
    const v=colVal(r,key); if(v==null) return dash(r,key);
    const sgn=d=>`<span class="${v>0?'up':(v<0?'dn':'note')}">${v>0?'+':''}${v.toFixed(d)}%</span>`;
    switch(key){
      case 'per': case 'pbr': return v.toFixed(1)+'배';
      case 'divy': return v.toFixed(2)+'%';
      case 'de': return v.toFixed(0)+'%';
      case 'cr': return v.toFixed(1);
      case 'roe': case 'frgn': return v.toFixed(1)+'%';
      case 'payout': return v.toFixed(0)+'%';
      case 'oploss': return v>0?`<span class="dn">${v.toFixed(0)}년</span>`:'<span class="note">—</span>';
      case 'hi': return `<span class="note">고점 ${v.toFixed(0)}%</span>`;
      case 'grw': case 'revg': case 'opg': case 'mom': case 'v200': case 'v20': case 'v50': return sgn(0);
      case 'r1m': case 'r3m': case 'r6m': case 'opm': return sgn(1);
      case 'vol20': return v.toFixed(1)+'%';
      case 'turn': return v.toFixed(2)+'%';
      case 'peg': case 'psr': return v.toFixed(2);
      case 'tob': return v?'<span class="up">전환</span>':'<span class="note">—</span>';
      case 'fnb20': case 'onb20': return `<span class="${v>0?'up':(v<0?'dn':'note')}">${v>0?'+':''}${Math.round(v).toLocaleString()}억</span>`;
      case 'fst': case 'ost': return v>0?`<span class="up">${v.toFixed(0)}일</span>`:'<span class="note">0</span>';
      case 'sr': return `<span class="${v>=5?'dn':''}">${v.toFixed(1)}%</span>`;
      case 'lb': return v==null?'—':wonF(v*1e8);
      case 'lbr': return `<span class="${v>=10?'dn':''}">${v.toFixed(2)}%</span>`;
      case 'align': return `<span class="${v==='정배열'?'up':(v==='역배열'?'dn':'note')}">${E(v)}</span>`;
      case 'macd': return `<span class="${String(v).startsWith('골든')?'up':'dn'}">${E(MACD_DISP[v]||v)}</span>`;
      case 'rsi': return `<span class="${v>=70?'up':(v<=30?'dn':'')}">${(+v).toFixed(0)}</span>`;
      case 'volx': return `<span class="${v>=1.5?'up':'note'}">${(+v).toFixed(1)}배</span>`;
      case 'bb': return (+v).toFixed(0);
    }
    return '';
  }
  function sortVal(r,k){
    if(k==='n') return String(r.n||'');
    if(k==='mk'||k==='sector') return String(r[k]||'');
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
        ['목표주가','애널리스트 컨센서스 목표주가. 필터는 \'있는 종목만\' 토글'],
        ['상승여력','목표주가 ÷ 현재가 − 1'],
        ['투자의견','컨센서스 등급을 0~100 매수강도로 환산(높을수록 매수)'],
        ['리비전','EPS 추정치 90일 변화율(FY1+FY2) — 애널리스트 상향세'],
        ['애널수','커버하는 애널리스트 수'],
        ['PER','forward P/E(예상 순이익 대비 주가). 낮을수록 저평가'],
        ['PBR','P/B(순자산 대비 주가). 낮을수록 저평가'],
        ['배당','배당수익률'],
        ['성장','매출·EPS 성장률 평균'],
        ['매출성장','매출 전년동기比 성장률'],
        ['이익성장','EPS 전년동기比 성장률'],
        ['ROE','자기자본이익률(순이익÷자기자본)'],
        ['수익률 12-1M','12개월 전 → 1개월 전 구간의 주가 수익률 = (1+1Y수익률)÷(1+1M수익률)−1. 최근 1개월을 <b>일부러 제외</b>한 모멘텀 — 단기 급등 직후의 반전 위험을 걸러낸다. <b>한국은 12M(순수 12개월 수익률)</b>이라 정의가 다르다'],
        ['수익률 1M·3M·6M','해당 기간 주가 수익률'],
        ['변동성(20일)','최근 20일 일간수익률 표준편차 — 낮을수록 안정'],
        ['회전율','거래대금(3개월 평균) ÷ 시가총액 — 시총 대비 유동성'],
        ['영업이익률','operating margin(TTM, Yahoo)'],
        ['PEG','forward PE ÷ EPS 성장률 — 1 이하면 성장 대비 저평가'],
        ['PSR','P/S(TTM) — 적자 성장주 밸류에이션'],
        ['흑자전환·수급·공매도·대차잔고','미국 미제공 — 연간 영업이익 배열·투자자별 수급·공매도·대차잔고 데이터 없음'],
        ['어닝임박','다음 실적발표일까지 D-day (Yahoo earnings date)'],
        ['고점比','52주 최고가 대비 현재가 위치 (−10% = 고점 근접)'],
        ['200일선','200일 이동평균 대비 현재가. 기본 −30%↑ = 심각한 하락추세 제외(구 건전성 신호)'],
        ['20일선·50일선','해당 이동평균 대비 현재가 위치'],
        ['이평배열','MA20>MA50>MA200=정배열(상승 구조) · 반대=역배열'],
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
        ['200일선','200일 이동평균 대비 현재가 — 장기 추세. 기본 −30%↑ = 심각한 하락추세 제외'],
        ['20일선','20일 이동평균 대비 현재가 — 단기 추세'],
        ['50일선','50일 이동평균 대비 현재가 — 중기 추세'],
        ['이평배열','20·50·200일선 배열 — 정배열(20>50>200)=상승추세장, 역배열=하락추세장, 혼조=전환 구간'],
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
        ['PSR','시가총액 ÷ 매출액(최근 연간) — 적자 성장주 밸류에이션'],
        ['흑자전환','직전 연도 영업적자 → 최근 연도 흑자로 전환'],
        ['외인·기관수급(20일)','KIS 종목별 투자자 — 최근 20거래일 누적 순매수 금액(억원)'],
        ['외인·기관연속매수','최근 며칠 연속 순매수 중인가(일)'],
        ['공매도비중','최근 거래일 공매도 거래량 ÷ 전체 거래량(%) — 5%↑ 과열 경계 (KIS)'],
        ['대차잔고비율','대차잔여주식수 ÷ 상장주식수(%) — 공매도 대기물량 프록시, 높을수록 하락배팅 부담 (금융위 주식대차정보 · 기준일 +1영업일 13시 갱신)'],
        ['어닝임박','다음 실적발표일까지 D-day (네이버 IR 일정 — 대형주 위주 제공)'],
        ['고점比','52주 최고가 대비 현재가 위치 (−10% = 고점 근접)'],
        ['외인보유비중','외국인 보유 비중'],
        ['목표주가','애널리스트 컨센서스 목표주가. 필터는 \'있는 종목만\' 토글'],
        ['상승여력','목표주가 ÷ 현재가 − 1'],
        ['투자의견','컨센서스 등급을 0~100 매수강도로 환산(높을수록 매수)'],
        ['리비전','목표주가 90일 변화율(누적/백필) — 애널리스트 상향세'],
        ['애널수','KR 미제공'],
        ['성장','매출·영업이익 성장률 평균'],
        ['매출성장','매출액 전년동기比 성장률'],
        ['이익성장','영업이익 전년동기比 성장률'],
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
        return `<div class="lgit"><b>${x[0]}</b>${cat?` <span class="lgcat">[${cat}]</span>`:''} = ${E(x[1])}</div>`;
      }).join('')+`</div>`;
    }}
  }
  /* (2026-07-26) 필터 라벨 → 카테고리. 상세 요약 그룹(GCAT)을 라벨 기준으로 역참조 */
  const GCAT=[['시세',['px','chg','cap','tv','turn']],['기간수익률',['r1m','r3m','r6m','mom']],
    ['기술적 지표',['hi','v200','v50','v20','align','rsi','macd','bb','volx','vol20']],
    ['컨센서스',['ern','tp','upside','recn','rev','nan']],
    ['밸류·수익성',['per','peg','pbr','psr','divy','payout','roe','opm']],
    ['성장',['grw','revg','opg','tob']],['수급',['fnb20','onb20','fst','ost','sr','lb','lbr','frgn']],
    ['건전성',['de','cr','oploss']],['기타',['age']]];
  const _catByLabel=(()=>{ const m={};
    for(const [cat,ks] of GCAT) for(const k of ks){ const c=CDEF[k]; if(c) m[c.l]=cat; }
    // 필터 전용/복합 라벨 보정 (컬럼 라벨과 다르게 표기되는 것들)
    Object.assign(m,{ '시장':'시세','섹터':'시세','가격':'시세','등락':'시세','시가총액':'시세','거래대금':'시세','회전율':'시세',
      '수익률 12-1M':'기간수익률','수익률 12M':'기간수익률','수익률 1M·3M·6M':'기간수익률','수익률 1M':'기간수익률','수익률 3M':'기간수익률','수익률 6M':'기간수익률','변동성(20일)':'기간수익률',
      'RSI(14)':'기술적 지표','거래량배수':'기술적 지표','MACD':'기술적 지표','볼린저밴드':'기술적 지표','이평배열':'기술적 지표','200일선':'기술적 지표','20일선':'기술적 지표','50일선':'기술적 지표','고점比':'기술적 지표',
      '목표주가':'컨센서스','상승여력':'컨센서스','투자의견':'컨센서스','리비전':'컨센서스','애널수':'컨센서스','어닝임박':'컨센서스',
      'PER':'밸류·수익성','PEG':'밸류·수익성','PBR':'밸류·수익성','PSR':'밸류·수익성','ROE':'밸류·수익성','배당성향':'밸류·수익성','배당':'밸류·수익성','영업이익률':'밸류·수익성',
      '성장':'성장','매출성장':'성장','이익성장':'성장','흑자전환':'성장',
      '외인·기관수급(20일)':'수급','외인·기관연속매수':'수급','공매도비중':'수급','대차잔고비율':'수급','대차잔고':'수급','흑자전환·수급·공매도·대차잔고':'수급','외인보유비중':'수급',
      '부채비율':'건전성','유동비율':'건전성','영업적자':'건전성','상장기간':'기타','증권 구분':'기타' });
    return m; })();
  function legendCat(label){ return _catByLabel[label] || null; }
  function apply(){ applyTable(); renderChips(); }

  /* ── 종목 상세: 종가 기준 일봉 차트(기술지표) + 지표 요약 ── */
  let dcode=null;
  function hideDetail(){ const d=$('scr_detail'); if(d) d.style.display='none'; dcode=null; }
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
  async function showDetail(c){
    const r=POOL[mkt].find(x=>x.c===c); if(!r) return;
    /* 새 종목을 열 때는 항상 자체차트부터. (같은 종목에서 소스 버튼을 누른 경우는 c===dcode 라 유지) */
    if(c!==dcode) chartSrc='canvas';
    dcode=c;
    $('scr_detail').style.display='';
    $('sd_name').textContent = mkt==='kr'? (r.n||'') : (r.kn? `${r.c} ${r.kn}` : r.c);
    $('sd_code').textContent = mkt==='kr'? r.c : (r.n||'');
    $('sd_last').innerHTML = cell(r,'px')+' '+cell(r,'chg');
    renderSum(r);
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
      $('sd_naver').style.display='none';
      cvs.forEach(id=>{const e=$(id); if(e)e.style.display='block';});
      $('sd_src').textContent='차트 불러오는 중…';
      try{
        const D=await (await fetch(`/api/chart/${mkt}/${encodeURIComponent(c)}?tf=${_TF}`)).json();
        if(dcode!==c) return;                     // 로드 중 다른 종목 클릭됨
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
        $('sd_tfnote').textContent = _isMin()
          ? `${D.t?D.t.length:0}봉 · 최근 ${new Set((D.t||[]).map(z=>z.slice(0,8))).size}거래일`
          : `${D.t?D.t.length:0}봉`;
        loadInv(c);                               // 수급 패널은 별도 로드(차트를 막지 않음)
        loadDisc(c);                              // 공시 마커도 별도 로드
        loadBottom(c);                            // 차트 하단 패널(호가/체결 또는 순매매 표)
      }catch(e){ $('sd_src').textContent='차트 로드 실패: '+e; }
    }
    if(autoScroll) $('scr_detail').scrollIntoView({block:'nearest',behavior:'smooth'});
  }
  function renderSum(r){
    const G=[['시세',['px','chg','cap','tv','turn']],
             ['기간수익률',['r1m','r3m','r6m','mom']],
             ['기술적 지표',['hi','v200','v50','v20','align','rsi','macd','bb','volx','vol20']],
             ['컨센서스',['ern','tp','upside','recn','rev','nan']],
             ['밸류·수익성',['per','peg','pbr','psr','divy','payout','roe','opm']],
             ['성장',['grw','revg','opg','tob']],
             ['수급',['fnb20','onb20','fst','ost','sr','lb','lbr','frgn']],
             ['건전성',['de','cr','oploss']],
             ['기타',['age']]];
    $('sd_sum').innerHTML=G.map(([t,ks])=>{
      const items=ks.filter(k=>CDEF[k]&&cAvail(k)).map(k=>`<div class="si"><span>${E(cl(k))}</span><b>${cell(r,k)}</b></div>`).join('');
      return items?`<div class="sg"><div class="sgt">${t}</div>${items}</div>`:'';
    }).join('');
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
    const dv=$('scr_detail'); if(!dv || dv.style.display==='none') return;
    if(_DRAG) return;                                   // 드래그 중이면 건너뛴다
    if(!_mktLive()) return;
    const need = _isMin() ? 30000 : 60000;
    if(Date.now()-_LASTFETCH < need) return;
    const c=dcode, tf=_TF;
    try{
      const D=await (await fetch(`/api/chart/${mkt}/${encodeURIComponent(c)}?tf=${tf}`)).json();
      if(dcode!==c || _TF!==tf) return;                 // 그 사이 종목·주기가 바뀌었으면 버린다
      _LASTFETCH=Date.now();
      const prevTot=(_CD&&_CD.c)?_CD.c.length:0, tot=(D.c||[]).length;
      _CD=D;
      if(_COFF>0 && tot>prevTot) _COFF += (tot-prevTot);  // 과거를 보던 중이면 그 구간 고정
      _paint();
      const nt=$('sd_tfnote');
      if(nt) nt.textContent = (_isMin()
          ? `${tot}봉 · 최근 ${new Set((D.t||[]).map(z=>z.slice(0,8))).size}거래일`
          : `${tot}봉`) + ` · 🔴 LIVE ${new Date().toLocaleTimeString('ko-KR',{hour12:false})}`;
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
      if(sel) sel.classList.toggle('on', _isMin()); };
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

  function _bindChart(){ if(_CBOUND) return; _CBOUND=true;
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
          if(!_DHIT.length) return;
          const r=e.getBoundingClientRect();
          const px=(ev.clientX-r.left)*(e.width/r.width), py=(ev.clientY-r.top)*(e.height/r.height);
          let hit=null;
          for(const m of _DHIT){ if((px-m.x)**2+(py-m.y)**2 <= (m.r+3)**2){ hit=m.d; break; } }
          _DSEL = (hit && hit!==_DSEL) ? hit : null;   // 같은 마커 재클릭·빈 곳 클릭 → 닫기
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
  function drawAll(D){ _CD=D; _CHI=null; _DISC=null; _DSEL=null; _DHIT=[];
    _CZ=CZ0; _COFF=0;                    // 종목이 바뀌면 기본 구간으로
    _bindChart(); _paint(); }
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
    /* (2026-07-21) x축 라벨을 공통 함수로 — 메인 차트와 보조 패널(OBV 등)이 똑같은 라벨·위치를 쓴다.
       예전엔 OBV 패널이 분봉에서도 '년.월'(26.07)만 찍어 다 같아 보였다(정렬은 맞는데 라벨만 무의미).
       모든 패널이 P.l=6·P.r=52·N 동일이라 X(i) 픽셀이 일치 → 같은 함수를 쓰면 라벨도 세로로 딱 맞는다. */
    function _xlabels(cx2, Xf, Hc){
      cx2.fillStyle='#98a2ad'; cx2.font='10px sans-serif';
      if(_isMin()){
        let lastD='', px=-99;
        for(let i=0;i<N;i++){ const z=String(t[i]||''); if(z.length<12) continue;
          const d=z.slice(0,8), hm=z.slice(8,10)+':'+z.slice(10,12), xx=Xf(i);
          if(d!==lastD){ lastD=d;
            if(xx-px>=46){ px=xx; cx2.save(); cx2.fillStyle='#5b6470'; cx2.font='bold 10px sans-serif';
              cx2.fillText((+d.slice(4,6))+'/'+(+d.slice(6,8)), xx-10, Hc-4); cx2.restore(); }
            continue; }
          if(hm.endsWith(':00') && xx-px>=52){ px=xx; cx2.fillText(hm, xx-12, Hc-4); } }
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
    const last=c[c.length-1], prev=c[c.length-2]??last, chg=prev?(last/prev-1)*100:0;
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
         x.font='11px sans-serif';
         const lines=its.map(z=>'· '+z.t);
         const head=`${_DSEL.slice(0,4)}.${_DSEL.slice(4,6)}.${_DSEL.slice(6,8)} 공시 ${byD[_DSEL].length}건`;
         const wmax=Math.min(Math.max(x.measureText(head).width, ...lines.map(z=>x.measureText(z).width))+16, 420);
         const bh=20+lines.length*14+(byD[_DSEL].length>6?14:0);
         let bx=Math.min(Math.max(X(i)-wmax/2, P.l), W-P.r-wmax), by=Math.min(Y(hh[i])+14, H-P.b-bh-4);
         if(by<P.t+18) by=P.t+18;
         x.fillStyle='rgba(255,255,255,.97)'; x.strokeStyle='#d6dbe2';
         if(x.roundRect){ x.beginPath(); x.roundRect(bx,by,wmax,bh,7); x.fill(); x.stroke(); }
         else { x.fillRect(bx,by,wmax,bh); x.strokeRect(bx,by,wmax,bh); }
         x.fillStyle='#c0392b'; x.font='bold 11px sans-serif'; x.fillText(head, bx+8, by+15);
         x.fillStyle='#3d454f'; x.font='11px sans-serif';
         lines.forEach((z,q)=>{ let tx=z;
           while(x.measureText(tx).width>wmax-16 && tx.length>4) tx=tx.slice(0,-2);
           if(tx!==z) tx=tx.slice(0,-1)+'…';
           x.fillText(tx, bx+8, by+29+q*14); });
         if(byD[_DSEL].length>6){ x.fillStyle='#98a2ad';
           x.fillText(`외 ${byD[_DSEL].length-6}건`, bx+8, by+29+lines.length*14); }
       }
     }
     // 십자선 — 호버 중인 봉 위치
     if(_CHI!=null){ x.save(); x.setLineDash([3,3]); x.strokeStyle='#9aa4b0';
       x.beginPath(); x.moveTo(X(HI),P.t); x.lineTo(X(HI),H-P.b); x.stroke();
       x.beginPath(); x.moveTo(P.l,Y(c[HI])); x.lineTo(W-P.r,Y(c[HI])); x.stroke(); x.restore(); }
     // 상단 범례 2줄 — 호버 중이면 그 봉, 아니면 최신 봉 기준
     {const dd=String(t[HI]||'').replace(/-/g,''), pv=(HI>0?c[HI-1]:c[HI]);
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
        ['roe','ROE',1],['de','부채비율',1]],
    us:[['n','종목',0],['rscore','종합',1,'z'],['z_val','V',1,'z'],['z_grw','G',1,'z'],['z_mom','M',1,'z'],['z_qly','Q',1,'z'],
        ['fpe','PE',1],['pb','PB',1],['divy','배당%',1],['g_new','성장',1],
        ['w52','52주',1],['hi52','고점比',1],['vs200','200일선',1],['rev','리비전',1],
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
      d=d||{}; POOL={kr:d.kr||[],us:d.us||[]}; S2=POOL; s2loaded=true; cb&&cb();
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
    let tail;
    if(d.live_at){
      tail = ` · <b style="color:#1f6feb">⚡LIVE ${E2(d.live_at)}</b> <span class="note">· 장중 자동갱신 KR 1분·US 3분(시간외 포함)</span>`;
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
      d=d||{}; POOL={kr:d.kr||[],us:d.us||[]}; loaded=true;
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
          POOL={kr:d.kr||[],us:d.us||[]}; if(s2loaded) S2=POOL; $('scr_asof').innerHTML=poolMeta(d); refresh(); break; }
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
      POOL={kr:d.kr||[],us:d.us||[]}; if(s2loaded) S2=POOL;
      $('scr_asof').innerHTML=poolMeta(d);
      refresh();
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
