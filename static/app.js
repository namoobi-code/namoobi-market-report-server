const $=id=>document.getElementById(id);
const esc=s=>String(s??'').replace(/[<>&]/g,c=>({'<':'&lt;','>':'&gt;','&':'&amp;'}[c]));
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

  $('meta').innerHTML=`최신 리포트 <b>${esc(rs[0]?.datetime||'—')}</b><br>지표 ${h.db_files}종 · 보고서 ${h.reports}건`;
  // (2026-07-12) 앱셸 — 헤더·좌측(아카이브·APK·DB인벤토리)·nav 는 고정, 본문(.mainc)만 스크롤.
  //   좌측 항목(보고서·DB)은 항상 보이므로 nav 에서 뺀다 — nav 는 본문 섹션 점프 전용.
  $('nav').innerHTML=[['slive','실시간 시세'],
    ['s311','3.1.1 금리'],['s333','3.1.1 HY'],['s312','3.1.2 물가'],['s313','3.1.3 고용'],['s314','3.1.4 OECD CLI'],
    ['s315','3.1.5 경기선행'],['s318','3.1.8 CAPEX'],['s319','3.1.9 HBM'],['s3110','3.1.10 수출'],
    ['s3111','3.1.11 반도체'],['s3113','3.1.13 파생'],['s32','3.2 KRX'],
    ['sberk','버크셔'],['spoll','서버수집']]
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

  const dp=b.dot_plot?.data;
  if(dp?.rows) $('dot').innerHTML=`<tr><th>시점</th><th style="text-align:right">6월</th><th style="text-align:right">3월</th><th>비고</th></tr>`+
    dp.rows.map(r=>`<tr><td><b>${esc(r.year)}</b></td><td class="num">${esc(r.jun)}</td>
    <td class="num note">${esc(r.mar)}</td><td class="note">${esc((r.note||'').slice(0,58))}</td></tr>`).join('');
  const fm=b.fomc_meetings?.data;
  if(fm) $('fomc').innerHTML=`<tr><th>일자</th><th>상태</th><th>비고</th></tr>`+
    fm.map(r=>`<tr><td><b>${esc(r.date)}</b></td><td>${esc(r.stance)}</td><td class="note">${esc(r.note)}</td></tr>`).join('');

  const t10=S(b,'series_us10y_daily'), t2=S(b,'series_us2y_daily'), sp=S(b,'series_curve_10_2');
  mk($('c_ust'),L(t10),[{n:'10년물',d:V(t10),c:C.r},{n:'2년물',d:V(t2),c:C.b}],{legend:true});
  mk($('c_spread'),L(sp),[{n:'10Y−2Y',d:V(sp),c:C.p,fill:true,bg:'rgba(131,88,196,.08)'}]);

  /* ── 3.1.2 물가 ── */
  $('infl').innerHTML=`<tr><th>지표</th><th style="text-align:right">전년비</th><th style="text-align:right">전월비</th>
    <th>기준</th><th>발표</th><th>해석</th></tr>`+(b.inflation?.data||[]).map(r=>`<tr>
    <td><b>${esc(r.name)}</b></td><td class="num up">${r.yoy!=null?r.yoy+'%':'—'}</td>
    <td class="num ${r.mom>0?'up':'dn'}">${r.mom!=null?r.mom+'%':'—'}</td>
    <td class="note">${esc(r.asof)}</td><td class="note">${esc(r.release||'')}</td>
    <td class="note">${esc(r.interp)}</td></tr>`).join('');
  const ic=S(b,'series_infl_CPI'),icc=S(b,'series_infl_Core_CPI'),ip=S(b,'series_infl_PCE'),
        ipc=S(b,'series_infl_Core_PCE'),ippi=S(b,'series_infl_PPI');
  mk($('c_infl'),L(ic),[{n:'CPI',d:V(ic),c:C.r},{n:'Core CPI',d:V(icc),c:C.o},{n:'PCE',d:V(ip),c:C.b},
    {n:'Core PCE',d:V(ipc),c:C.g},{n:'PPI',d:V(ippi),c:C.gy}],{legend:true});
  const bei=S(b,'series_infl_exp');
  mk($('c_bei'),L(bei),[{n:'BEI',d:V(bei),c:C.p}]);

  /* ── 3.1.3 고용 ── */
  $('emp').innerHTML=`<tr><th>지표</th><th style="text-align:right">값</th><th>기준</th><th>주기</th><th>해석</th></tr>`+
    (b.employment?.data||[]).map(r=>`<tr><td><b>${esc(r.name)}</b></td><td class="num">${esc(r.value)}</td>
    <td class="note">${esc(r.asof)}</td><td class="note">${esc(r.freq||'')}</td><td class="note">${esc(r.interp)}</td></tr>`).join('');
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
    const YS=cxd.years, NM=cxd.companies;
    const fx=v=>(v===''||v==null)?'—':Number(v).toLocaleString(undefined,{maximumFractionDigits:0});
    $('capex_t').innerHTML=
      `<tr><th rowspan="2">기업</th><th colspan="${YS.length}" style="text-align:center">CAPEX</th>
        <th colspan="${YS.length}" style="text-align:center;border-left:2px solid #dfe3e7">매출</th></tr>
       <tr>${YS.map(y=>`<th style="text-align:right">${y}${y>=2026?'E':''}</th>`).join('')}
        ${YS.map((y,i)=>`<th style="text-align:right${i===0?';border-left:2px solid #dfe3e7':''}">${y}${y>=2026?'E':''}</th>`).join('')}</tr>`+
      NM.map((n,ci)=>`<tr><td><b style="color:${PAL[ci]}">${esc(n)}</b></td>
        ${cxd.capex[n].map(v=>`<td class="num">${fx(v)}</td>`).join('')}
        ${cxd.revenue[n].map((v,i)=>`<td class="num note"${i===0?' style="border-left:2px solid #dfe3e7"':''}>${fx(v)}</td>`).join('')}
      </tr>`).join('')+
      `<tr><td colspan="${1+YS.length*2}" class="note">단위: 십억 달러 · 2026 이후는 가이던스/컨센서스</td></tr>`;
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
    const t=md?.tables?.[tkey]; if(!t) return;
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
        $('hbm_mkt_src').textContent='[추정] Yole Group·TrendForce 연간 전망 — 연 1~2회 갱신(조사기관 발표 시)';
      } else if(H.market){
        const yr=H.market.revenue_bn.map(r=>r[0]);
        const dy=Object.fromEntries(H.market.demand_yoy||[]);
        mk($('c_hbm_mkt'),yr,[{n:'시장규모($B)',d:H.market.revenue_bn.map(r=>r[1]),c:C.g},
          {n:'수요 증가율(%)',d:yr.map(y=>dy[y]??null),c:C.p,dash:[5,3],w:2.2}],{bar:true,legend:true,y0:true});
        $('hbm_mkt_src').textContent=H.market.revenue_src;
      } }
    // ② HBM ASP
    if(H.asp){
      $('asp_t').innerHTML=`<tr><th>제품</th><th style="text-align:right">가격(USD)</th><th style="text-align:right">변동</th><th>동인</th></tr>`+
        H.asp.map(a=>`<tr><td><b>${esc(a.product)}</b></td><td class="num">${esc(a.price)}</td>
        <td class="num ${a.trend==='up'?'up':'note'}">${esc(a.change||'—')}</td>
        <td class="note">${esc((a.driver||'').slice(0,40))}</td></tr>`).join('');
    }
    memTrend('c_asp','hbm_asp');
    // ③ 점유율
    if(H.share){
      const sr=Object.fromEntries((H.supplier_revenue||[]).map(r=>[r.vendor,r]));
      $('share_t').innerHTML=`<tr><th>업체</th><th style="text-align:right">HBM 점유율</th><th style="text-align:right">매출 기준</th><th>비고</th></tr>`+
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
      $('spgap_src').textContent='현물가가 계약가를 상회하는 폭. 갭이 클수록 다음 계약 협상에서 계약가 인상 압력이 커진다 — 메모리 3사 실적의 선행지표. DDR4 8Gb 갭 +89%, NAND 64Gb 갭 +55%로 인상 압력이 지속되고 있다.';
    }

    // ⑨ HBM:DDR5 격차 — (req12 2026-07-12) 매일 환산 시계열(series_mem_hbm_ddr5_gap) 우선
    { const gs=[...SR('hbm_ddr5_gap')].sort((a,b2)=>a[0]<b2[0]?-1:1);
      if(gs.length){
        const last=gs[gs.length-1][1]||{};
        mk($('c_gap'),gs.map(r=>r[0].slice(5)),
          [{n:'배율(HBM÷DDR5)',d:gs.map(r=>r[1]['배율']??null),c:C.p,w:2.4},
           {n:'HBM $/GB',d:gs.map(r=>r[1]['HBM $/GB']??null),c:C.o,dash:[4,3]},
           {n:'DDR5 $/GB',d:gs.map(r=>r[1]['DDR5 $/GB']??null),c:C.b,dash:[4,3]}],{legend:true,y0:true});
        $('gap_src').textContent=`[환산 추정] HBM3E 스택 ASP÷용량 vs DDR5 계약가 $/GB — 최신 ${last['배율']}배 (HBM $${last['HBM $/GB']}/GB vs DDR5 $${last['DDR5 $/GB']}/GB). 통상 5~6배 · 배율 급락=범용 DRAM 급등(삼성 상대 유리) 신호 · 매일 계산·누적.`;
      } else if(H.per_gb){
        const p=H.per_gb;
        mk($('c_gap'),['DDR5 현물','HBM3','HBM3E','HBM4E'],
          [{n:'USD/GB',d:[p.ddr5_spot_usd_per_gb,p.hbm3_usd_per_gb,p.hbm3e_usd_per_gb,p.hbm4_usd_per_gb],c:C.r}],
          {bar:true,y0:true});
        $('gap_src').textContent=`DDR5 현물이 HBM3E의 ${p.premium_x}배 — 통상 HBM이 5~6배 프리미엄인데 역전됨. ${p.note}`;
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
      $('meta_t').innerHTML=`<tr><th>지표</th><th>변동 주기</th><th>의미</th><th>해석 방법</th></tr>`+
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
      $('val_t').innerHTML=`<tr><th>기업</th><th style="text-align:right">현재가</th>
        <th style="text-align:right">TTM EPS</th><th style="text-align:right">PER</th>
        <th style="text-align:right">2026E EPS</th><th style="text-align:right">PER</th>
        <th style="text-align:right">2027E EPS</th><th style="text-align:right">PER</th></tr>`+
        V.map(r=>{const K=r.currency==='KRW';
        return `<tr><td><b>${esc(r.name)}</b></td><td class="num">${f(r.price,K)}</td>
        <td class="num note">${f(r.eps_ttm,K)}</td><td class="num">${r.per_ttm}x</td>
        <td class="num note">${f(r.eps_2026E,K)}</td><td class="num dn"><b>${r.per_2026E}x</b></td>
        <td class="num note">${f(r.eps_2027E,K)}</td><td class="num" style="color:var(--ok)"><b>${r.per_2027E}x</b></td></tr>`;}).join('')+
        `<tr><td colspan="8" class="note">단일 소스 db/hbm_eps.json — PER = 최신 종가 ÷ EPS 매일 재계산 (docx 3.1.9 표와 동일값) · ${esc((b.hbm_eps&&b.hbm_eps.price_note)||md.asof_valuation||'')}</td></tr>`;
      mk($('c_per'),V.map(r=>r.name),
        [{n:'TTM',d:V.map(r=>r.per_ttm),c:C.gy},{n:'2026E',d:V.map(r=>r.per_2026E),c:C.b},
         {n:'2027E',d:V.map(r=>r.per_2027E),c:C.g}],{bar:true,legend:true,y0:true});
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

  /* ── 3.1.13 파생 포지셔닝 ── */
  const dv=M.deriv_positioning;
  if(dv){
    $('deriv_idx').innerHTML=(dv.index||[]).map(x=>`<div class="card">
      <div class="k">${esc(x.name)}</div><div class="v" style="font-size:18px">${esc(x.close)}</div>
      <div class="s"><span class="${String(x.ret1).startsWith('+')?'up':'dn'}">1일 ${esc(x.ret1)}</span> ·
        <span class="${String(x.ret5).startsWith('+')?'up':'dn'}">5일 ${esc(x.ret5)}</span></div></div>`).join('');
    const names=(dv.index||[]).map(x=>x.name);
    $('deriv_t').innerHTML=`<tr><th>지표</th>${names.map(n=>`<th colspan="2" style="text-align:center">${esc(n)}</th>`).join('')}</tr>
      <tr><th></th>${names.map(()=>`<th style="text-align:right">값</th><th style="text-align:right">z</th>`).join('')}</tr>`+
      (dv.rows||[]).map(r=>`<tr><td><b>${esc(r.label)}</b></td>${(r.cells||[]).map(c=>{
        const z=c.z, hot=z!=null&&Math.abs(z)>=1.5;
        return `<td class="num">${esc(c.v)}</td><td class="num ${hot?(z>0?'up':'dn'):'note'}" ${hot?'style="font-weight:800"':''}>${z!=null?z.toFixed(2):'—'}</td>`;
      }).join('')}</tr>`).join('')+
      `<tr><td colspan="${1+names.length*2}" class="note">${esc(dv.asof||'')}</td></tr>`;
    $('dv_us').textContent=dv.market_us||'—';
    $('dv_kr').textContent=dv.market_kr||'—';
    $('dv_syn').textContent=dv.synthesis||'';
  }

  /* ── KRX ── */
  const kx=b.krx_brief?.data;
  if(kx) $('krx').innerHTML=Object.entries(kx).map(([k,v])=>`<div class="card">
    <div class="k">${k==='krx'?'KRX 증시 Brief':'공매도 데일리 브리프'}</div>
    <div class="v" style="font-size:14px">${esc(v.title)}</div>
    <div class="s">등록 ${esc(v.date)} · ${esc(v.pages)}p</div></div>`).join('');

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
    if($('hy_cur')) $('hy_cur').innerHTML=`현재 OAS: <b>${cur==null?'-':Number(cur).toFixed(2)+'%'}</b> · 기준 ${esc(hs.length?hs[hs.length-1][0]:(hy.asof||''))}${hy.comment?('<br><span class="note">'+esc(hy.comment)+'</span>'):''}`;
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
  }

  /* ── 서버 폴링 ── */
  const pl=b._poll||{}, kim=pl.kimchi_premium||{}, syms=Object.keys(kim);
  const fg=(pl.fear_greed||{})._||[];
  const last=o=>o?.length?o[o.length-1][1]:null;
  $('poll_now').innerHTML=[['공포탐욕지수',last(fg)??'—',''],['원/달러',last((pl.usdkrw||{})._)?.toLocaleString()??'—','KRW'],
    ...syms.map(s=>[`김프 ${s}`,(last(kim[s])??0).toFixed(2)+'%',''])]
    .map(([k,v,u])=>`<div class="card"><div class="k">${k}</div><div class="v" style="font-size:18px">${v}${u?' '+u:''}</div></div>`).join('');
  if(syms.length) mk($('c_kim'),(kim[syms[0]]||[]).map(x=>x[0].slice(5,16).replace('T',' ')),
    syms.map((s,i)=>({n:s,d:(kim[s]||[]).map(x=>x[1]),c:PAL[i]})),{legend:true});
  if(fg.length) mk($('c_fg'),fg.map(x=>x[0].slice(5,16).replace('T',' ')),
    [{n:'F&G',d:fg.map(x=>x[1]),c:C.r,fill:true,bg:'rgba(214,69,69,.08)'}],{y0:true});

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
    oecd_cli:'OECD 경기선행지수(CLI) 주요국 월별 (3.1.4)',
    policy_rates:'주요 6개국 정책금리 현재값·비고 (3.1.1 카드)',
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
    series_us2y_daily:'미국 2년물 국채금리 일별 시계열 (3.1.1 차트)'};
  const inv=Object.keys(b).filter(k=>k!=='_poll').sort().map(k=>{
    const d=b[k],dat=d?.data; let n='—',kind='—';
    if(Array.isArray(dat)&&dat.length&&Array.isArray(dat[0])){kind='시계열';n=dat.length+'점';}
    else if(Array.isArray(dat)){kind='표';n=dat.length+'행';}
    else if(dat&&typeof dat==='object'){kind='복합';n=Object.keys(dat).length+'키';}
    // (2026-07-12) 기준일 자동 폴백 — as_of 공란이면 marker(날짜꼴) → 시계열 최신일 → '—'
    let ao=d?.as_of;
    if(!ao){ const mk2=String(d?.marker||'').slice(0,10);
      if(/^\d{4}-\d{2}-\d{2}$/.test(mk2)) ao=mk2;
      else if(Array.isArray(dat)&&dat.length&&Array.isArray(dat[0])){ const l=String(dat[dat.length-1][0]).slice(0,10); if(/^\d{4}-\d{2}-\d{2}$/.test(l)) ao=l; } }
    return {k,kind,n,asof:ao||'—',desc:DESC[k]||''};
  });
  // (2026-07-12) 좌측 사이드바 컴팩트 — 항목당 2줄(1줄: 이름+형태·규모·기준일 / 2줄: 설명)
  $('inv').innerHTML=inv.map(r=>`<div class="it">
    <div class="l1"><b>${esc(r.k)}</b><span class="m">${r.kind} ${r.n} · ${esc(r.asof)}</span></div>
    <div class="l2">${esc(r.desc)}</div></div>`).join('');
  $('inv_n').textContent=`${inv.length}종 전량`;

  /* ── 보고서 ── */
  $('reports').innerHTML=rs.map(r=>`<div class="rpt">
    <div><b>${esc(r.datetime)}</b> <span class="note">· ${r.size_mb}MB</span></div>
    <a class="dl" href="/reports/${encodeURIComponent(r.file)}">다운로드</a></div>`).join('');
})();


/* ── 안드로이드 APK 릴리스 (GitHub Releases 캐시 · sync_apk.py) ── */
fetch('/api/apk').then(r=>r.json()).then(rs=>{
  const el=document.getElementById('apkbox');
  if(!el) return;
  if(!Array.isArray(rs)||!rs.length){el.innerHTML='<div class="rpt">릴리스 없음</div>';return;}
  el.innerHTML=rs.map(r=>`<div class="rpt">
    <div><b>${r.tag}</b> · ${r.published}${r.notes?`<br><span style="opacity:.75;font-size:11px">${r.notes}</span>`:''}<br><span style="opacity:.55;font-size:11px">${r.file} · ${r.size_mb}MB</span></div>
    <a class="dl" href="/apk/${encodeURIComponent(r.file)}">다운로드</a></div>`).join('');
}).catch(()=>{});
