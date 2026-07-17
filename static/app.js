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

  $('meta').innerHTML=`최신 리포트 <b>${esc(rs[0]?.datetime||'—')}</b>`;
  // (2026-07-12) 앱셸 — 헤더·좌측(아카이브·APK·DB인벤토리)·nav 는 고정, 본문(.mainc)만 스크롤.
  //   좌측 항목(보고서·DB)은 항상 보이므로 nav 에서 뺀다 — nav 는 본문 섹션 점프 전용.
  $('nav').innerHTML=[['slive','실시간 시세'],
    ['s311','3.1.1 금리'],['s333','3.1.1 HY'],['s312','3.1.2 물가'],['s313','3.1.3 고용'],['s314','3.1.4 OECD CLI'],
    ['s315','3.1.5 경기선행'],['s318','3.1.8 CAPEX'],['s319','3.1.9 HBM'],['s3110','3.1.10 수출'],
    ['s3111','3.1.11 반도체'],['s3113','3.1.13 파생'],['s3114','3.1.14 유동성'],['s32','3.2 KRX'],
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
        const hasV=c.v!=null&&!['-','—',''].includes(String(c.v).trim());
        if(!hasV) return `<td class="num note" colspan="2" style="text-align:center">N/A</td>`;
        return `<td class="num">${esc(c.v)}</td><td class="num ${hot?(z>0?'up':'dn'):'note'}" ${hot?'style="font-weight:800"':''}>${z!=null?z.toFixed(2):'<span class="note" style="font-style:italic">making</span>'}</td>`;
      }).join('')}</tr>`).join('')+
      `<tr><td colspan="${1+names.length*2}" class="note">${esc(dv.asof||'')}</td></tr>`+
      `<tr><td colspan="${1+names.length*2}" class="note">※ z 공란(—) 안내 — 풋콜비율·IV 스큐·딜러 감마(GEX)는 옵션 체인 과거 스냅샷이 공개 소스에 없어 2026-07-11 수집 개시분부터 자체 누적 중이며, 롤링 60거래일이 쌓이는 2026년 10월경부터 z가 자동 산출됩니다(그때까지 현재값 + 'making'(누적 진행 중) 표시). 한국 외국인·기관 수급 z도 주간 이력 누적 후 순차 산출. N/A = 해당 지수에서 조사 불가 항목(KOSPI200 옵션 지표는 VKOSPI로 대체, VKOSPI는 한국 전용 — 미국은 VIX).</td></tr>`;
    $('dv_us').textContent=dv.market_us||'—';
    $('dv_kr').textContent=dv.market_kr||'—';
    $('dv_syn').textContent=dv.synthesis||'';
  }

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
    kr_liquidity:'국내 유동성·레버리지 — 예탁금·미수금·반대매매·신용잔고(코스피/코스닥)·M2 (3.1.14, 원본=data/kr_liquidity.db)',
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

  // 탭 전환
  const panes=['p_daily','p_db','p_ai','p_ta','p_auto','p_fire','p_screener'];
  document.querySelectorAll('.tab').forEach(b=>b.addEventListener('click',()=>{
    if(b.disabled||b.classList.contains('off')) return;   // 비활성 탭은 무시
    document.querySelectorAll('.tab').forEach(x=>x.classList.toggle('on',x===b));
    panes.forEach(id=>{const el=document.getElementById(id);
      if(el) el.classList.toggle('on', id===b.dataset.pane);});
    const sb=document.getElementById('btn_screener'); if(sb) sb.classList.remove('on');
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
  $$('nav_d').innerHTML=[['d1','1 뉴스'],['d2','2 캘린더'],['d316','3.1.6 FactSet'],['d317','3.1.7 M7'],['d3112','3.1.12 심리'],['d32','3.2 한국'],['d321','3.2.1 수급'],['d322','3.2.2 종목수급'],['d323','3.2.3 테마'],['d323s','반도체·AI 종목'],['d323e','반도체·AI ETF'],['s32','3.2.4·5 KRX브리프'],
    ['d33','3.3 미국'],['d331','3.3.1 美ETF'],['d332','3.3.2 리밸런싱'],['d34','3.4 아시아'],['d35','3.5 유럽'],['d36','3.6 북미·중남미'],['d37','3.7 호주·중동'],
    ['d41','4.1 에너지'],['d42','4.2 금속'],['d43','4.3 농산물'],['d44','4.4 비철금속'],['d5','5 환율'],['d6','6 크립토'],['d7','7 증권사'],['d8','8 글로벌IB'],
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
  T('d_ev', EH, ((R.news||{}).events_calendar||[]).map(EV));
  T('d_evl',EH, ((R.news||{}).events_calendar_longterm||[]).map(EV));
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

  /* ── 6. 크립토 ── */
  const mo=(CR.market_overview||{}).market_summary||{}, fg=(CR.fear_greed||{}).current||{};
  $$('d_cry').innerHTML=[
    ['24h 거래대금',mo.total_volume_24h?('$'+(mo.total_volume_24h/1e9).toFixed(1)+'B'):'—',`${mo.total_coins||0}개 코인`],
    ['24h 평균 등락',mo.avg_change_24h!=null?`${mo.avg_change_24h>0?'+':''}${mo.avg_change_24h}%`:'—',
      `상승 ${mo.coins_up||0} · 하락 ${mo.coins_down||0}`],
    ['상승/하락',`${mo.coins_up||0} / ${mo.coins_down||0}`,'24시간 기준'],
  ].map(([k,v,s2])=>`<div class="card"><div class="k">${E(k)}</div><div class="v">${E(v)}</div>
      <div class="s">${E(s2)}</div></div>`).join('');
  $$('d_fg').innerHTML=`<b>${E(fg.value??'—')} · ${E(fg.classification||'')}</b> — ${E(fg.description||'')}<br>
    <span class="note">${E((CR.fear_greed||{}).trend_analysis||'')}</span>`;

  T('d_kimchi',['코인','업비트 (원)','바이낸스 ($)','김프','판정'],((CR.kimchi_premium||{}).coins||[]).map(c=>
    [`<b>${E(c.symbol)}</b>`,`<span class="num">${N(c.upbit_krw)}</span>`,`<span class="num">${N(c.binance_usd)}</span>`,
     P(c.premium_pct),`<span class="note">${E(c.status||'')}</span>`]));

  const gl=(arr,lab,cls)=>`<div class="card"><div class="k" style="font-size:12.5px;font-weight:650;color:var(--${cls})">${lab}</div>`+
    (Array.isArray(arr)&&arr.length?`<table style="border:none;margin-top:6px">${arr.map(x=>
      `<tr><td><b>${E(x.symbol||x.name)}</b></td><td class="num ${cls==='up'?'up':'dn'}">${P(x.change_24h??x.change)}</td></tr>`).join('')}</table>`
      :'<div class="note" style="margin-top:6px">데이터 없음 (수집 실패 시 빈 배열)</div>')+'</div>';
  $$('d_gl').innerHTML=gl(CR.top_gainers,'24h Top Gainers','up')+gl(CR.top_losers,'24h Top Losers','dn');

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
  const houses=(obj,names)=>Object.entries(obj||{}).filter(([,v])=>v&&typeof v==='object'&&v.key_message)
    .map(([k,v])=>`<div class="card"><div class="k" style="font-size:13px;color:var(--tx);font-weight:650">${E(names[k]||k)}</div>
      <div class="s" style="margin-top:7px">${E(v.key_message)}</div>
      <div class="src">강점: ${E(v.strength||'')}</div></div>`).join('');
  $$('d_sec').innerHTML=houses(R.securities,{kb:'KB증권',nh:'NH투자증권',samsung:'삼성증권',miraeasset:'미래에셋증권',korea_inv:'한국투자증권',
    shinhan:'신한투자증권',kiwoom:'키움증권',meritz:'메리츠증권',hana:'하나증권',kyobo:'교보증권',
    yuanta:'유안타증권',hyundai:'현대차증권'});
  const CT=(R.securities||{}).common_themes;
  $$('d_sec_c').innerHTML=Array.isArray(CT)?CT.map(t=>`• ${E(typeof t==='string'?t:(t.theme||JSON.stringify(t)))}`).join('<br>'):E(CT||'');
  $$('d_gsec').innerHTML=houses(R.global_securities,{ubs:'UBS',goldman:'Goldman Sachs',jpmorgan:'J.P. Morgan',
    morgan_stanley:'Morgan Stanley',blackrock:'BlackRock'});
  const GC=(R.global_securities||{}).wall_street_consensus, GT=(R.global_securities||{}).common_themes;
  $$('d_gsec_c').innerHTML=(Array.isArray(GT)?GT.map(t=>`• ${E(typeof t==='string'?t:JSON.stringify(t))}`).join('<br>'):'')+
    (GC?`<div style="margin-top:8px"><b>월가 컨센서스</b> — ${E(typeof GC==='string'?GC:JSON.stringify(GC))}</div>`:'');

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
  T('a_act',['구분','액션'],(A.action_items||[]).map(a=>{
    const t=String(a), m2=t.match(/^\[(.+?)\]\s*(.*)$/);
    return m2?[`<b>${E(m2[1])}</b>`,E(m2[2])]:['—',E(t)];}));

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

  const DEF={
    kr:{
      cap:{label:'시가총액',fmt:wonF,presets:[['전체',null,null],['10조 ↑',1e13,null],['1~10조',1e12,1e13],['3,000억~1조',3e11,1e12],['1,000억~3,000억',1e11,3e11],['1,000억 ↓',null,1e11]],def:[3e11,null]},
      tv:{label:'거래대금',fmt:wonF,min:1,presets:[['전체',null],['100억 ↑',1e10],['30억 ↑',3e9],['10억 ↑',1e9],['1억 ↑',1e8]],def:[3e9,null]},
      px:{label:'저가주',fmt:wonF,min:1,presets:[['전체',null],['1,000원 ↑',1000],['5,000원 ↑',5000],['1만원 ↑',10000]],def:[1000,null]},
      age:{label:'상장기간',fmt:v=>v+'년',min:1,presets:[['전체',null],['1년 ↑',1],['3년 ↑',3],['5년 ↑',5],['10년 ↑',10]],def:[1,null]},
      sec:{label:'증권 구분',fixed:'보통주만'},
      health:{label:'건전성 신호',tgl:1,def:true,tglLabel:'200일선 −30%↓ 제외'},
      opLoss:{label:'3년 영업적자',tgl:1,def:true,tglLabel:'3년 연속 영업적자 제외'},
      de:{label:'부채비율',fmt:v=>v.toFixed(0)+'%',fin:1,presets:[['전체',null,null],['100% ↓',null,100],['200% ↓',null,200],['300% ↓',null,300]],def:[null,300]},
      cr:{label:'유동비율(당좌)',fmt:v=>v.toFixed(1),min:1,fin:1,presets:[['전체',null],['0.8 ↑',0.8],['1.0 ↑',1.0],['1.5 ↑',1.5]],def:[0.8,null]},
      upside:{label:'목표주가 대비 상승여력',fmt:v=>v.toFixed(0)+'%',min:1,reqData:1,presets:[['전체',null],['0% ↑',0],['10% ↑',10],['20% ↑',20],['50% ↑',50]],def:[null,null]},
      rec:{label:'투자의견',fmt:v=>'매수강도 '+v.toFixed(0),min:1,reqData:1,presets:[['전체',null],['매수 이상',65],['강력매수',85]],def:[null,null]},
      rev:{label:'리비전',fmt:v=>v.toFixed(0)+'%',min:1,reqData:1,presets:[['전체',null],['상향(0% ↑)',0],['5% ↑',5],['10% ↑',10]],def:[null,null]},
      nan:{label:'애널리스트수',fixed:'— (KR 미제공)'},
      cov:{label:'목표주가',tgl:1,def:false,tglLabel:'컨센서스 있는 종목만'},
      per:{label:'PER',fmt:v=>v.toFixed(1)+'배',presets:[['전체',null,null],['10배 ↓',null,10],['15배 ↓',null,15],['20배 ↓',null,20]],def:[null,null]},
      pbr:{label:'PBR',fmt:v=>v.toFixed(1)+'배',presets:[['전체',null,null],['1배 ↓',null,1],['2배 ↓',null,2],['3배 ↓',null,3]],def:[null,null]},
      divy:{label:'배당',fmt:v=>v.toFixed(1)+'%',min:1,presets:[['전체',null],['1% ↑',1],['2% ↑',2],['3% ↑',3]],def:[null,null]},
      grw:{label:'성장',fmt:v=>v.toFixed(0)+'%',min:1,presets:[['전체',null],['0% ↑',0],['10% ↑',10],['20% ↑',20],['50% ↑',50]],def:[null,null]},
      mom:{label:'추세',fmt:v=>v.toFixed(0)+'%',min:1,presets:[['전체',null],['0% ↑',0],['50% ↑',50],['100% ↑',100],['200% ↑',200]],def:[null,null]},
      hi:{label:'고점比',fmt:v=>'고점 '+v.toFixed(0)+'%',min:1,presets:[['전체',null],['-10% 이내',-10],['-20% 이내',-20],['-30% 이내',-30]],def:[null,null]},
      v200:{label:'200일선',fmt:v=>(v>=0?'+':'')+v.toFixed(0)+'%',min:1,presets:[['전체',null],['위(0%)',0],['+10% ↑',10],['+20% ↑',20]],def:[null,null]}
    },
    us:{
      cap:{label:'시가총액',fmt:usdF,presets:[['전체',null,null],['$200B ↑',2e11,null],['$10~200B',1e10,2e11],['$2~10B',2e9,1e10],['$300M~2B',3e8,2e9],['$300M ↓',null,3e8]],def:[2e9,null]},
      tv:{label:'거래대금',fmt:usdF,min:1,presets:[['전체',null],['$50M ↑',5e7],['$20M ↑',2e7],['$5M ↑',5e6]],def:[2e7,null]},
      px:{label:'저가주',fmt:usdF,min:1,presets:[['전체',null],['$5 ↑',5],['$10 ↑',10],['$50 ↑',50]],def:[5,null]},
      age:{label:'상장기간',fmt:v=>v+'년',min:1,presets:[['전체',null],['1년 ↑',1],['3년 ↑',3],['5년 ↑',5],['10년 ↑',10]],def:[1,null]},
      sec:{label:'증권 구분',fixed:'EQUITY만(ETF·워런트 제외)'},
      health:{label:'건전성 신호',tgl:1,def:true,tglLabel:'200일선 −30%↓ 제외'},
      opLoss:{label:'3년 영업적자',tgl:1,def:true,tglLabel:'3년 연속 영업적자 제외'},
      de:{label:'D/E',fmt:v=>v.toFixed(0)+'%',fin:1,presets:[['전체',null,null],['100% ↓',null,100],['200% ↓',null,200],['300% ↓',null,300]],def:[null,300]},
      cr:{label:'유동비율',fmt:v=>v.toFixed(1),min:1,fin:1,presets:[['전체',null],['0.8 ↑',0.8],['1.0 ↑',1.0],['1.5 ↑',1.5]],def:[0.8,null]},
      upside:{label:'목표주가 대비 상승여력',fmt:v=>v.toFixed(0)+'%',min:1,reqData:1,presets:[['전체',null],['0% ↑',0],['10% ↑',10],['20% ↑',20],['50% ↑',50]],def:[null,null]},
      rec:{label:'투자의견',fmt:v=>'매수강도 '+v.toFixed(0),min:1,reqData:1,presets:[['전체',null],['매수 이상',65],['강력매수',85]],def:[null,null]},
      rev:{label:'리비전',fmt:v=>v.toFixed(0)+'%',min:1,reqData:1,presets:[['전체',null],['상향(0% ↑)',0],['5% ↑',5],['10% ↑',10]],def:[null,null]},
      nan:{label:'애널리스트수',fmt:v=>v.toFixed(0)+'명',min:1,reqData:1,presets:[['전체',null],['1명 ↑',1],['3명 ↑',3],['10명 ↑',10]],def:[null,null]},
      cov:{label:'목표주가',tgl:1,def:false,tglLabel:'컨센서스 있는 종목만'},
      per:{label:'PER',fmt:v=>v.toFixed(1)+'배',presets:[['전체',null,null],['10배 ↓',null,10],['15배 ↓',null,15],['20배 ↓',null,20]],def:[null,null]},
      pbr:{label:'PBR',fmt:v=>v.toFixed(1)+'배',presets:[['전체',null,null],['1배 ↓',null,1],['2배 ↓',null,2],['3배 ↓',null,3]],def:[null,null]},
      divy:{label:'배당',fmt:v=>v.toFixed(1)+'%',min:1,presets:[['전체',null],['1% ↑',1],['2% ↑',2],['3% ↑',3]],def:[null,null]},
      grw:{label:'성장',fmt:v=>v.toFixed(0)+'%',min:1,presets:[['전체',null],['0% ↑',0],['10% ↑',10],['20% ↑',20],['50% ↑',50]],def:[null,null]},
      mom:{label:'추세',fmt:v=>v.toFixed(0)+'%',min:1,presets:[['전체',null],['0% ↑',0],['50% ↑',50],['100% ↑',100],['200% ↑',200]],def:[null,null]},
      hi:{label:'고점比',fmt:v=>'고점 '+v.toFixed(0)+'%',min:1,presets:[['전체',null],['-10% 이내',-10],['-20% 이내',-20],['-30% 이내',-30]],def:[null,null]},
      v200:{label:'200일선',fmt:v=>(v>=0?'+':'')+v.toFixed(0)+'%',min:1,presets:[['전체',null],['위(0%)',0],['+10% ↑',10],['+20% ↑',20]],def:[null,null]}
    }
  };
  const KEYS=['cap','tv','px','age','sec','health','opLoss','de','cr','upside','rec','rev','nan','cov','per','pbr','divy','grw','mom','hi','v200'];
  let POOL={kr:[],us:[]}, mkt='kr', F={}, sort={k:'cap',d:-1}, loaded=false;

  const F_ST={};   // 마켓별 1단계 필터 상태 유지
  function buildF(){ const o={}; const d=DEF[mkt];
    for(const k of KEYS){ const f=d[k]; if(!f || f.fixed!==undefined) continue;
      if(f.tgl){o[k]={on:f.def};} else {o[k]={min:f.def[0],max:f.def[1]};} } return o; }
  function resetF(){ F_ST[mkt]=buildF(); F=F_ST[mkt]; }          // 초기화 → 현재 마켓만 기본값
  function loadF(){ if(!F_ST[mkt]) F_ST[mkt]=buildF();           // 마켓 전환 → 저장분 로드(원복 안함)
    else { const df=buildF(); for(const k in df) if(!(k in F_ST[mkt])) F_ST[mkt][k]=df[k]; } // 신규 필터키 백필(구버전 저장상태 호환)
    F=F_ST[mkt]; }
  const ageOf=r=>r.yr?nowY-r.yr:null;
  function pass(r){ const d=DEF[mkt];
    for(const k in F){ const f=d[k], st=F[k];
      if(f.tgl){ if(!st.on) continue;
        if(k==='health'){ const h = mkt==='kr'? r.vs200 : r.d200; if(h!=null && h<-0.30) return false; }
        if(k==='opLoss' && r.op3neg) return false;
        if(k==='cov' && r.tp==null) return false;
        continue; }
      if(f.fin && r.isfin) continue;   // 금융업 면제
      const _hi=(mkt==='kr'?r.near52:r.hi52);
      let v=k==='cap'?r.cap:k==='tv'?r.tv:k==='px'?r.px:k==='age'?ageOf(r):k==='de'?r.de:k==='cr'?r.cr:
            k==='upside'?(r.upside!=null?r.upside*100:null):k==='rec'?r.recn:k==='nan'?r.nan:
            k==='rev'?(r.rev!=null?r.rev*100:null):
            k==='per'?(mkt==='kr'?r.fper:r.fpe):k==='pbr'?(mkt==='kr'?r.pbr:r.pb):k==='divy'?r.divy:
            k==='grw'?(r.g_new!=null?r.g_new*100:null):
            k==='mom'?(mkt==='kr'?(r.mom!=null?r.mom*100:null):r.w52):
            k==='hi'?(_hi!=null?_hi*100:null):k==='v200'?(r.vs200!=null?r.vs200*100:null):null;
      if(v==null){ if(f.reqData && (st.min!=null||st.max!=null)) return false; continue; }  // 데이터 필수 필터: 값 없으면 제외
      if(st.min!=null && v<st.min) return false;
      if(st.max!=null && v>st.max) return false; }
    return true; }

  function chipLabel(k){ const f=DEF[mkt][k], st=F[k]||{};
    if(f.fixed!==undefined) return `${f.label}: <span class="cv">${E(f.fixed)}</span>`;
    if(f.tgl) return `${f.label}: <span class="cv">${st.on?'ON':'OFF'}</span>`;
    const lo=st.min, hi=st.max;
    let v = (lo==null&&hi==null)?'전체' : (hi==null?f.fmt(lo)+' ↑' : (lo==null?f.fmt(hi)+' ↓' : f.fmt(lo)+'~'+f.fmt(hi)));
    return `${f.label}: <span class="cv">${E(v)}</span>`; }

  function renderChips(){
    const d=DEF[mkt];
    $('scr_fltbar').innerHTML=KEYS.map(k=>{
      const f=d[k];
      if(!f) return '';
      if(f.fixed!==undefined) return `<div class="fchip"><button disabled style="opacity:.75;cursor:default">${chipLabel(k)}</button></div>`;
      const st=F[k]; const active = f.tgl? st.on : (st.min!=null||st.max!=null);
      let pop;
      if(f.tgl){
        pop=`<label class="tgl"><input type="checkbox" data-tgl="${k}" ${st.on?'checked':''}> ${E(f.tglLabel)}</label>`;
      } else {
        pop=`<div class="pl">프리셋</div>`+f.presets.map((p,pi)=>{
          const lo=p[1], hi=p.length>2?p[2]:null;
          const sel=(st.min===lo && (st.max===hi || (f.min&&hi==null)));
          return `<button class="preset ${sel?'sel':''}" data-k="${k}" data-lo="${lo==null?'':lo}" data-hi="${hi==null?'':hi}">${E(p[0])}</button>`;
        }).join('')+
        `<div class="man"><span>직접</span><input type="number" placeholder="최소" data-man="${k}" data-mm="min" value="${st.min??''}">`+
        (f.min?'':`<span>~</span><input type="number" placeholder="최대" data-man="${k}" data-mm="max" value="${st.max??''}">`)+`</div>`;
      }
      return `<div class="fchip"><button class="${active?'act':''}" data-chip="${k}">${chipLabel(k)}</button><div class="fpop" id="pop_${k}">${pop}</div></div>`;
    }).join('');
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
    $('scr_fltbar').querySelectorAll('[data-tgl]').forEach(t=>t.onchange=()=>{ F[t.dataset.tgl].on=t.checked; apply(); });
  }

  const COLS={
    kr:[['n','종목',0],['mk','시장',0],['px','가격',1],['chg','등락',1],['cap','시가총액',1],['tv','거래대금',1],['tp','목표주가',1],['upside','상승여력',1],['recn','투자의견',1],['rev','리비전',1],['age','상장',1]],
    us:[['n','종목명',0],['px','가격',1],['chg','등락',1],['cap','시가총액',1],['tv','거래대금',1],['tp','목표주가',1],['upside','상승여력',1],['recn','투자의견',1],['nan','애널',1],['rev','리비전',1],['age','상장',1]]
  };
  function cell(r,key){
    if(key==='n') return mkt==='kr'?`<b>${E(r.n)}</b> <span class="note">${E(r.c)}</span>`:`<b>${E(r.c)}</b> <span class="note">${E(r.n)}</span>`;
    if(key==='mk') return E(r.mk||'');
    if(key==='px') return mkt==='kr'?(r.px?Math.round(r.px).toLocaleString()+'원':'—'):'$'+(r.px?(+r.px).toFixed(2):'—');
    if(key==='chg'){const v=r.chg; return v==null?'—':`<span class="${v>0?'up':(v<0?'dn':'note')}">${v>0?'+':''}${(+v).toFixed(2)}%</span>`;}
    if(key==='cap') return mkt==='kr'?wonF(r.cap):usdF(r.cap);
    if(key==='tv') return mkt==='kr'?wonF(r.tv):usdF(r.tv);
    if(key==='d200'){const v=r.d200; return v==null?'—':`<span class="${v>0?'up':(v<0?'dn':'note')}">${v>0?'+':''}${(v*100).toFixed(0)}%</span>`;}
    if(key==='tp'){const v=r.tp; return v==null?'<span class="note">—</span>':(mkt==='kr'?Math.round(v).toLocaleString()+'원':'$'+(+v).toFixed(2));}
    if(key==='upside'){const v=r.upside; return v==null?'<span class="note">—</span>':`<span class="${v>0?'up':(v<0?'dn':'note')}">${v>0?'+':''}${(v*100).toFixed(0)}%</span>`;}
    if(key==='recn'){const v=r.recn; if(v==null)return '<span class="note">—</span>'; const lab=v>=85?'강력매수':v>=65?'매수':v>=45?'중립':'매도'; return `${v.toFixed(0)} <span class="note">${lab}</span>`;}
    if(key==='nan'){const v=r.nan; return v==null?'<span class="note">—</span>':v.toFixed(0)+'명';}
    if(key==='rev'){const v=r.rev; if(v==null) return mkt==='kr'?'<span class="note">누적중</span>':'<span class="note">—</span>';
      const t=r.tp_trend, ar=t==='up_steady'?'⇈':t==='down_steady'?'⇊':(v>0?'↑':v<0?'↓':'→');
      const cls=v>0?'up':(v<0?'dn':'note'), tt=t==='up_steady'?'꾸준상승':t==='down_steady'?'꾸준하락':(mkt==='us'?'EPS 추정치 90일 변화':'목표주가 90일 변화');
      return `<span class="${cls}" title="${tt}">${ar} ${v>0?'+':''}${(v*100).toFixed(1)}%</span>`;}
    if(key==='age'){const a=ageOf(r); return a==null?'—':a+'년';}
    return '';
  }
  function sortVal(r,k){ return k==='age'?(ageOf(r)??-1):k==='n'?String(r.n||''):(r[k]??-Infinity); }
  let popCloser=false;
  function applyTable(){
    const rows=POOL[mkt].filter(pass);
    rows.sort((a,b)=>{const x=sortVal(a,sort.k),y=sortVal(b,sort.k);
      if(typeof x==='string')return sort.d*x.localeCompare(y); return sort.d*(x-y);});
    $('scr_cnt').innerHTML=`<b>${rows.length.toLocaleString()}</b>종 통과 <span style="opacity:.6">/ ${POOL[mkt].length.toLocaleString()} 전체</span>`;
    const cols=COLS[mkt]; const cap=rows.slice(0,400);
    $('scr_tbl').innerHTML='<tr><th>#</th>'+cols.map(c=>`<th data-sort="${c[0]}" class="${sort.k===c[0]?(sort.d<0?'dn':'up'):''}">${E(c[1])}</th>`).join('')+'</tr>'+
      cap.map((r,i)=>`<tr><td class="note">${i+1}</td>`+cols.map(c=>`<td class="${c[2]?'num':''}">${cell(r,c[0])}</td>`).join('')+'</tr>').join('')+
      (rows.length>400?`<tr><td colspan="${cols.length+1}" class="note" style="text-align:center">상위 400종 표시 (전체 ${rows.length.toLocaleString()}종 — 필터를 좁히세요)</td></tr>`:'');
    $('scr_tbl').querySelectorAll('[data-sort]').forEach(th=>th.onclick=()=>{
      const k=th.dataset.sort; if(sort.k===k)sort.d*=-1; else {sort.k=k; sort.d=(k==='n')?1:-1;} applyTable(); });
    {const rn=$('scr_revnote'); if(rn){
      const g = mkt==='us' ? [
        ['건전성 신호','200일 이동평균 대비 −30% 미만(심각한 하락추세) 종목 제외'],
        ['유동비율','유동자산÷유동부채(current ratio) — 단기 지급능력. 금융업 면제'],
        ['리비전','EPS 추정치 90일 변화율(FY1+FY2), Yahoo에서 즉시 — 애널리스트 상향세 (예: NVDA ↑+11%)'],
        ['PER','forward P/E(예상 순이익 대비 주가). 낮을수록 저평가'],
        ['PBR','P/B(순자산 대비 주가). 낮을수록 저평가'],
        ['성장','매출·EPS 전년동기比 성장률(Yahoo)'],
        ['추세','52주 주가 변화율(가격 모멘텀)'],
        ['고점比','52주 최고가 대비 현재가 위치 (−10% = 고점 근접)'],
        ['200일선','200일 이동평균 대비 현재가(장기 추세 위치)']
      ] : [
        ['건전성 신호','200일 이동평균 대비 −30% 미만(심각한 하락추세) 종목 제외'],
        ['유동비율(당좌)','당좌자산÷유동부채 — 단기 지급능력. 금융업 면제'],
        ['리비전','목표주가 90일 변화율(누적/백필) — 애널리스트 상향세 (예: 삼성전자 ⇈+72%, 메모리 슈퍼사이클 실제 상향)'],
        ['PER','추정 주가수익비율(순이익 대비 주가). 낮을수록 저평가'],
        ['PBR','주가순자산비율(순자산 대비 주가). 낮을수록 저평가'],
        ['성장','매출·영업이익 전년동기比 실측 성장률 평균'],
        ['추세','12−1개월 주가 모멘텀(장기 상승 강도)'],
        ['고점比','52주 최고가 대비 현재가 위치 (−10% = 고점 근접)'],
        ['200일선','200일 이동평균 대비 현재가(장기 추세 위치)']
      ];
      rn.innerHTML='<b style="color:var(--tx)">필터 설명</b><br>'+g.map(x=>`<b>${x[0]}</b> = ${E(x[1])}`).join('<br>');
    }}
  }
  function apply(){ applyTable(); renderChips(); }

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
  function renderS2(){ renderWPanel(); rankTbl(); }   /* 원자료 하드컷은 1단계로 이동 */
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
    kr:[['n','종목',0],['rscore','종합',1,'z'],['z_val','V',1,'z'],['z_grw','G',1,'z'],['z_mom','M',1,'z'],['z_qly','Q',1,'z'],['fper','PER',1],['pbr','PBR',1],['divy','배당%',1],['g_new','성장',1],['mom','추세',1],['near52','고점比',1]],
    us:[['n','종목',0],['rscore','종합',1,'z'],['z_val','V',1,'z'],['z_grw','G',1,'z'],['z_mom','M',1,'z'],['z_qly','Q',1,'z'],['fpe','PE',1],['pb','PB',1],['divy','배당%',1],['g_new','성장',1],['w52','52주',1],['hi52','고점比',1],['vs200','200일선',1]]
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
    if(d.W) W=d.W; if(d.ON) ON=d.ON;
    return true;
  }catch(e){ return false; } }
  function applyRestored(){
    document.querySelectorAll('.mktseg:not(.stgseg) .mkt').forEach(x=>x.classList.toggle('on',x.dataset.mkt===mkt));
    document.querySelectorAll('.stgseg .stg').forEach(x=>x.classList.toggle('on',+x.dataset.stg===stage));
    $('scr_s1').style.display = stage===1?'':'none';
    $('scr_s2').style.display = stage===2?'':'none';
    $('scr_s3').style.display = stage===3?'':'none';
    loadF(); loadF2();
    if(stage===2) loadS2(()=>renderS2());
    else if(stage===3) loadS3(()=>renderS3());
    else apply();
  }
  window.addEventListener('beforeunload', saveScr);

  window.renderScreener=function(){
    if(!loaded){
      loaded=true;
      $('scr_asof').textContent='전종목 풀 불러오는 중…';
      fetch('/api/db/screener_pool').then(r=>r.json()).then(d=>{
        d=d||{}; POOL={kr:d.kr||[],us:d.us||[]};
        $('scr_asof').innerHTML=`기준일 <b>${E(d.price_date||'—')}</b> · 전종목 풀 한국 ${POOL.kr.length.toLocaleString()} · 미국 ${POOL.us.length.toLocaleString()} · 수집 ${E(d.asof||'')}`;
        {const _e=$('scr_src2'); if(_e) _e.innerHTML='출처: KRX OPEN API + 네이버 전종목 시세 · Yahoo v7(미국) · 하루 2회 갱신.';}
        if(restoreScr()) applyRestored(); else { resetF(); apply(); }
      }).catch(e=>{ $('scr_asof').textContent='풀 로드 실패: '+e; });
    } else { refresh(); }
  };
  document.addEventListener('click',e=>{ if(!e.target.closest('.fchip')) document.querySelectorAll('.fpop').forEach(x=>x.classList.remove('open')); });
  // 마켓 토글
  document.querySelectorAll('.mktseg:not(.stgseg) .mkt').forEach(b=>b.onclick=()=>{
    document.querySelectorAll('.mktseg:not(.stgseg) .mkt').forEach(x=>x.classList.toggle('on',x===b));
    mkt=b.dataset.mkt; loadF(); loadF2(); refresh(); });   // 원복 안함 — 마켓별 선택 유지
  // 스테이지 토글 (1단계/2단계)
  document.querySelectorAll('.stgseg .stg').forEach(b=>b.onclick=()=>{
    document.querySelectorAll('.stgseg .stg').forEach(x=>x.classList.toggle('on',x===b));
    stage=+b.dataset.stg;
    $('scr_s1').style.display = stage===1?'':'none';
    $('scr_s2').style.display = stage===2?'':'none';
    $('scr_s3').style.display = stage===3?'':'none';
    if(stage===2) loadS2(()=>renderS2());
    else if(stage===3) loadS3(()=>renderS3());
    else apply();
  });
  {const rb=$('scr_rst'); if(rb) rb.onclick=()=>{ if(stage===1){sort={k:'cap',d:-1};resetF();apply();} else if(stage===2){resetW();renderS2();} else {resetW();renderS3();} };}
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
