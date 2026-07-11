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
  $('nav').innerHTML=[['s311','3.1.1 금리'],['s312','3.1.2 물가'],['s313','3.1.3 고용'],['s314','3.1.4 OECD CLI'],
    ['s315','3.1.5 경기선행'],['s318','3.1.8 CAPEX'],['s319','3.1.9 HBM'],['s3110','3.1.10 수출'],
    ['s3111','3.1.11 반도체'],['s3113','3.1.13 파생'],['s32','3.2 KRX'],['s333','3.3.3 HY'],
    ['sberk','버크셔'],['spoll','서버수집'],['sinv','DB'],['srpt','보고서']]
    .map(([i,t])=>`<a href="#${i}">${t}</a>`).join('');

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
    const asc=[...kl].reverse();
    mk($('c_lead'),asc.map(r=>r.period),[{n:'순환변동치',d:asc.map(r=>r.value),c:C.g,w:2.4,pt:3,fill:true,bg:'rgba(30,158,106,.08)'}]);
    $('lead_note').innerHTML=esc(M.korea_leading_comment||'기준 100 위는 경기 확장 국면, 아래는 수축 국면을 시사한다. 4개월 연속 상승 중.');
  }

  /* ── 3.1.8 CAPEX ── */
  const cx=M.bigtech_capex;
  if(cx?.capex_series){
    // 표는 차트와 동일한 capex_series 기준 (rows 배열엔 Meta가 누락돼 있어 불일치 방지)
    const yrs=cx.capex_series.years;
    const comp=Object.keys(cx.capex_series).filter(k=>k!=='years');
    const cap=cx.capex_series, rev=cx.rev_series||{}, fcf=cx.fcf_series||{};
    const fx=v=>(v===''||v==null)?'—':Number(v).toLocaleString(undefined,{maximumFractionDigits:0});
    $('capex_t').innerHTML=
      `<tr><th rowspan="2">기업</th><th colspan="${yrs.length}" style="text-align:center">CAPEX</th>
        <th colspan="${yrs.length}" style="text-align:center;border-left:2px solid #dfe3e7">매출</th></tr>
       <tr>${yrs.map(y=>`<th style="text-align:right">${y}${y>=2026?'E':''}</th>`).join('')}
        ${yrs.map((y,i)=>`<th style="text-align:right${i===0?';border-left:2px solid #dfe3e7':''}">${y}${y>=2026?'E':''}</th>`).join('')}</tr>`+
      comp.map((n,ci)=>`<tr><td><b style="color:${PAL[ci]}">${esc(n)}</b></td>
        ${(cap[n]||[]).map(v=>`<td class="num">${fx(v)}</td>`).join('')}
        ${(rev[n]||[]).map((v,i)=>`<td class="num note"${i===0?' style="border-left:2px solid #dfe3e7"':''}>${fx(v)}</td>`).join('')}
      </tr>`).join('')+
      `<tr><td colspan="${1+yrs.length*2}" class="note">단위: 십억 달러 · 2026 이후는 가이던스/컨센서스(E) · ${esc(cx.asof||'')}</td></tr>`;
    const S2=(o)=>{ if(!o) return null;
      const ys=o.years, names=Object.keys(o).filter(k=>k!=='years');
      return {ys, ds:names.map((n,i)=>({n,c:PAL[i],w:2,pt:2,d:o[n].map(v=>v===''?null:v)}))}; };
    const a=S2(cx.capex_series), r2=S2(cx.rev_series), f=S2(cx.fcf_series);
    if(a) mk($('c_capex'),a.ys,a.ds,{legend:true});
    if(r2) mk($('c_rev'),r2.ys,r2.ds,{legend:true});
    if(f) mk($('c_fcf'),f.ys,f.ds,{legend:true});
    $('capex_c').innerHTML=esc(cx.comment||'');
  }

  /* ── 3.1.9 메모리 + HBM ── */
  const hb=M.hbm;
  if(hb){
    const tiles=[['DDR5 16Gb 스팟','ddr5_16gb','USD'],['DDR4 8Gb 스팟','ddr4_8gb','USD'],
      ['NAND MLC 64Gb','nand_mlc_64gb','USD'],['HBM3E 가격','hbm3e_price',''],['HBM4 가격','hbm4_price',''],
      ['HBM 시장규모','hbm_market',''],['HBM 출하량','hbm_shipment',''],['DRAM 갭 비율','gap_ratio','']];
    $('hbm_tiles').innerHTML=tiles.map(([lab,key,u])=>{
      const o=hb[key]; if(!o) return '';
      const val=o.value!==''&&o.value!=null?o.value:'—';
      return `<div class="card"><div class="k">${lab}</div>
        <div class="v" style="font-size:17px">${esc(val)}${u&&val!=='—'?' '+u:''}</div>
        <div class="s">${esc((o.spec||o.note||'').slice(0,64))}</div></div>`;
    }).join('');
    const sh=hb.share;
    if(sh && typeof sh==='object'){
      const ent=Object.entries(sh).filter(([k,v])=>typeof v==='number'||(!isNaN(parseFloat(v))&&k!=='note'&&k!=='source'&&k!=='asof'));
      if(ent.length) mk($('c_hbm_share'),ent.map(e=>e[0]),
        [{n:'점유율',d:ent.map(e=>parseFloat(e[1])),c:C.b}],{bar:true,y0:true});
    }
    const mkt=hb.hbm_market, shp=hb.hbm_shipment;
    const rows=[];
    [['시장규모(십억$)',mkt],['출하량',shp]].forEach(([n,o])=>{
      if(o && typeof o==='object' && !isNaN(parseFloat(o.value))) rows.push([n,parseFloat(o.value)]);
    });
    if(rows.length) mk($('c_hbm_mkt'),rows.map(r=>r[0]),[{n:'값',d:rows.map(r=>r[1]),c:C.o}],{bar:true,y0:true});
  }
  const he=b.hbm_eps?.data;
  if(he){
    const yrs=['y2025','y2026','y2027','y2028'];
    const names=Object.keys(he).filter(k=>he[k]?.y2026_eps!=null);
    $('hbm_eps').innerHTML=`<tr><th>기업</th>${yrs.map(y=>`<th style="text-align:right">${y.slice(1)} EPS</th>`).join('')}
      ${yrs.map(y=>`<th style="text-align:right">${y.slice(1)} PER</th>`).join('')}</tr>`+
      names.map(n=>`<tr><td><b>${esc(n)}</b></td>
      ${yrs.map(y=>`<td class="num">${he[n][y+'_eps']?.toLocaleString()??'—'}</td>`).join('')}
      ${yrs.map(y=>`<td class="num dn">${he[n][y+'_per']??'—'}</td>`).join('')}</tr>`).join('')+
      `<tr><td colspan="9" class="note">한국기업 KRW · Micron USD</td></tr>`;
    mk($('c_per'),yrs.map(y=>y.slice(1)+'년'),
      names.map((n,i)=>({n,d:yrs.map(y=>he[n][y+'_per']),c:PAL[i]})),{legend:true,bar:true,y0:true});
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
    const sr=sc.series||{};
    const g=(el,key,col)=>{const o=sr[key]; if(o) mk($(el),o.labels,[{n:key,d:o.values,c:col}],{bar:true,y0:true});};
    g('c_inv','inventory',C.g); g('c_pq','price_qoq',C.r); g('c_cx','capex_yoy',C.b);
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

  /* ── HY 스프레드 ── */
  const hy=M.hy_spread;
  if(hy) $('hy').innerHTML=Object.entries(hy).filter(([k,v])=>typeof v!=='object').map(([k,v])=>
    `<div class="card"><div class="k">${esc(k)}</div><div class="v" style="font-size:17px">${esc(v)}</div></div>`).join('')
    || `<div class="card"><div class="s">${esc(JSON.stringify(hy).slice(0,200))}</div></div>`;

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

  /* ── DB 인벤토리 ── */
  const DUP={'series_emp_nfp_mom':'nfp 폴백 — NFP 차트 교차검증선','series_emp_retail_mom':'retail 폴백 — 소매 차트 교차검증선'};
  const inv=Object.keys(b).filter(k=>k!=='_poll').sort().map(k=>{
    const d=b[k],dat=d?.data; let n='—',kind='—';
    if(Array.isArray(dat)&&dat.length&&Array.isArray(dat[0])){kind='시계열';n=dat.length+'점';}
    else if(Array.isArray(dat)){kind='표';n=dat.length+'행';}
    else if(dat&&typeof dat==='object'){kind='복합';n=Object.keys(dat).length+'키';}
    return {k,kind,n,asof:d?.as_of||'',dup:DUP[k]||''};
  });
  $('inv').innerHTML=`<tr><th>항목</th><th>형태</th><th style="text-align:right">규모</th><th>기준일</th><th>비고</th></tr>`+
    inv.map(r=>`<tr><td><b>${esc(r.k)}</b></td><td class="note">${r.kind}</td><td class="num note">${r.n}</td>
    <td class="note">${esc(r.asof)}</td><td class="note">${esc(r.dup)}</td></tr>`).join('');
  $('inv_n').textContent=`${inv.length}종 전량`;

  /* ── 보고서 ── */
  $('reports').innerHTML=rs.map(r=>`<div class="rpt">
    <div><b>${esc(r.datetime)}</b> <span class="note">· ${r.size_mb}MB</span></div>
    <a class="dl" href="/reports/${encodeURIComponent(r.file)}">다운로드</a></div>`).join('');
})();
