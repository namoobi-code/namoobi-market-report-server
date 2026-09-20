/* ct.js — 🧬 셀트리온 탭 (2026-09-20 신설)
   데이터: /api/db/celltrion (data/db/celltrion.json)
     큐레이션 층(분기실적·제품별 매출·점유율 시계열·출처) = 주 1회 LLM 갱신(Cowork 예약)
     live 층(시세·컨센·리비전·수급) = fetch_celltrion.py 매일
   원칙: 회사가 제품별 매출을 공표하지 않는다 → 공시/IR/증권사 추정을 출처와 함께 구분 표시, 추정으로 빈칸 안 메움. */
(function(){
  const $=id=>document.getElementById(id);
  const E=s=>String(s??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
  const nf=v=>v==null?'—':Math.round(v).toLocaleString();
  const pf=(v,d=1)=>v==null?'—':`<span class="${v>0?'up':(v<0?'dn':'')}">${v>0?'+':''}${v.toFixed(d)}%</span>`;
  const TD='border:1px solid #e2e8f0;padding:4px 8px;';
  const TH='border:1px solid #e2e8f0;padding:5px 8px;font-size:11.5px;background:#f8fafc;';
  let _init=false, D=null, chQ=null, chS=null;

  function liveBox(){
    const L=D.live||{}, p=L.pool||{}, c=L.cons||{};
    if(!p.px) return '<div class="note">라이브 데이터 없음(fetch_celltrion 크론 확인)</div>';
    const pctv=(v,d=1)=>v==null?'—':pf(v*100,d);
    const cell=(k,v)=>`<div style="background:#fff;border:1px solid #e2e8f0;border-radius:8px;padding:6px 10px;min-width:96px"><div class="note" style="font-size:10.5px">${k}</div><div style="font-size:14px;font-weight:700">${v}</div></div>`;
    return `<div style="display:flex;flex-wrap:wrap;gap:6px">
      ${cell('현재가',nf(p.px)+'<span class="note" style="font-size:10.5px"> '+(p.chg==null?'':pf(p.chg))+'</span>')}
      ${cell('시총',p.mcap?(p.mcap/1e12).toFixed(1)+'조':'—')}
      ${cell('목표가(컨센)',nf(p.tp)+(p.upside!=null?' <span class="note">'+pf(p.upside)+'</span>':''))}
      ${cell('PER / 선행PER',(p.per==null?'—':p.per.toFixed(1))+' / '+(p.fper==null?'—':p.fper.toFixed(1)))}
      ${cell('영업익 리비전 30·90일',pctv(p.cr30)+' · '+pctv(p.cr90))}
      ${cell('목표가 리비전 30일',pf(p.tprv)+(p.tpn?` <span class="note">(${p.tpn}건 ↑${p.tpu??0}/↓${p.tpd??0})</span>`:''))}
      ${cell('영업익 성장 실적 / 컨센',pctv(p.opg,0)+' / '+pctv(p.opg_f,0))}
      ${cell('전망 전구간↑ 분기/연간',(p.qup?'✓':'✗')+' / '+(p.yup?'✓':'✗'))}
      ${cell('RSI · 120일선',(p.rsi==null?'—':p.rsi.toFixed(0))+' · '+pctv(p.vs200)+(p.align?' <span class="note">'+E(p.align)+'</span>':''))}
      ${cell('수익률 1M/3M/6M/1Y',[p.r1m,p.r3m,p.r6m,p.r1y].map(v=>v==null?'—':(v*100).toFixed(0)+'%').join(' / '))}
      ${cell('외인·기관 20일 순매수(시총比)',pctv(p.fnb20,2)+' · '+pctv(p.onb20,2))}
    </div><div class="note" style="margin-top:4px">시세 기준 ${E(L.price_date||'')} · 컨센 ${E(L.cons_asof||'')} · 스크리너 풀·컨센 스냅샷과 동일 데이터</div>`;
  }

  function quarterTbl(){
    const Q=D.quarters||[], A=D.annual||[];
    let h=`<table style="border-collapse:collapse;font-size:12.5px;background:#fff">
      <thead><tr>${['분기','매출(억)','YoY','영업이익(억)','YoY','OPM','신제품 비중','근거'].map(x=>`<th style="${TH}">${x}</th>`).join('')}</tr></thead><tbody>`;
    Q.forEach((q,i)=>{
      const prev=Q.find(x=>x.q===(parseInt(q.q)-1)+q.q.slice(4));
      const yr=prev&&prev.rev?(q.rev/prev.rev-1)*100:null, yo=prev&&prev.op?(q.op/prev.op-1)*100:null;
      h+=`<tr><td style="${TD}"><b>${E(q.q)}</b></td><td style="${TD}text-align:right">${nf(q.rev)}</td><td style="${TD}text-align:right">${pf(yr)}</td>
        <td style="${TD}text-align:right">${nf(q.op)}</td><td style="${TD}text-align:right">${pf(yo)}</td>
        <td style="${TD}text-align:right">${q.rev&&q.op?(q.op/q.rev*100).toFixed(1)+'%':'—'}</td>
        <td style="${TD}text-align:right">${q.new_share!=null?'<b>'+q.new_share+'%</b>'+(q.new_rev?' <span class="note">('+nf(q.new_rev)+'억)</span>':''):'—'}</td>
        <td style="${TD}color:#64748b;font-size:11px">${E(q.src||'')}</td></tr>`;});
    h+=`</tbody></table>`;
    let a=`<table style="border-collapse:collapse;font-size:12.5px;background:#fff;margin-top:8px">
      <thead><tr>${['연도','매출(억)','YoY','영업이익(억)','YoY','OPM','바이오(억)','신제품 비중','근거'].map(x=>`<th style="${TH}">${x}</th>`).join('')}</tr></thead><tbody>`;
    A.forEach((y,i)=>{const p=A[i-1];
      a+=`<tr style="${y.est?'background:#fff7ea':''}"><td style="${TD}"><b>${y.y}${y.est?' <span style="color:#c47b1e;font-size:10px">E</span>':''}</b></td>
        <td style="${TD}text-align:right">${nf(y.rev)}</td><td style="${TD}text-align:right">${pf(p&&p.rev?(y.rev/p.rev-1)*100:null)}</td>
        <td style="${TD}text-align:right">${nf(y.op)}</td><td style="${TD}text-align:right">${pf(p&&p.op?(y.op/p.op-1)*100:null)}</td>
        <td style="${TD}text-align:right">${y.rev&&y.op?(y.op/y.rev*100).toFixed(1)+'%':'—'}</td>
        <td style="${TD}text-align:right">${nf(y.bio)}</td><td style="${TD}text-align:right">${y.new_share!=null?y.new_share+'%':'—'}</td>
        <td style="${TD}color:#64748b;font-size:11px">${E(y.src||'')}</td></tr>`;});
    a+=`</tbody></table><div class="note" style="margin-top:3px">주황=증권사 추정(E) · '역산'=공표된 YoY·연간 합계로 계산한 값(회사 미공표 분기)</div>`;
    return h+a;
  }

  function quarterChart(){
    const Q=D.quarters||[]; if(chQ) chQ.destroy(); if(!Q.length||!window.Chart) return;
    chQ=new Chart($('ct_cv1'),{type:'bar',data:{labels:Q.map(q=>q.q),datasets:[
      {label:'매출(억)',data:Q.map(q=>q.rev),backgroundColor:'#93c5fd',yAxisID:'y'},
      {label:'영업이익(억)',data:Q.map(q=>q.op),backgroundColor:'#1d4ed8',yAxisID:'y'},
      {label:'신제품 비중(%)',type:'line',data:Q.map(q=>q.new_share),borderColor:'#dc2626',backgroundColor:'#dc2626',yAxisID:'y2',spanGaps:true,tension:.2}]},
      options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{labels:{font:{size:11}}}},
        scales:{y:{ticks:{font:{size:10}}},y2:{position:'right',min:0,max:100,grid:{drawOnChartArea:false},ticks:{font:{size:10},callback:v=>v+'%'}}}}});
  }

  function productTbl(){
    const P=D.products||[], S=D.shares||[], ST=D.shares_text||[];
    const latestShare=k=>{ const rows=S.filter(s=>s.product===k); const by={};
      rows.forEach(s=>{ if(!by[s.region]||by[s.region].d<s.d) by[s.region]=s; });
      const num=Object.values(by).sort((a,b)=>b.v-a.v).map(s=>`<b>${E(s.region)} ${s.v}%</b><span class="note" style="font-size:10px"> ${E(s.d)}</span>`);
      const txt=ST.filter(s=>s.product===k).map(s=>`${E(s.region)} ${E(s.text)}<span class="note" style="font-size:10px"> ${E(s.d)}</span>`);
      return num.concat(txt).join(' · ')||'—'; };
    const revCell=p=>(p.rev||[]).map(r=>`<div style="${r.est?'color:#c47b1e':''}">${E(r.period)} <b>${nf(r.v)}억</b>${r.est?' <span style="font-size:10px">E</span>':''}${r.detail?` <span class="note" style="font-size:10.5px">${E(r.detail)}</span>`:''}<span class="note" style="font-size:10px"> — ${E(r.src||'')}</span></div>`).join('')||'<span class="note">비공표</span>';
    let h=`<table style="border-collapse:collapse;font-size:12.5px;background:#fff;width:100%">
      <thead><tr>${['구분','제품 (오리지널)','시장 위치 · 최신 점유율','매출(억)','현황'].map(x=>`<th style="${TH}">${x}</th>`).join('')}</tr></thead><tbody>`;
    P.forEach(p=>{ h+=`<tr><td style="${TD}white-space:nowrap"><span style="padding:1px 7px;border-radius:9px;font-size:11px;background:${p.cls==='신제품'?'#dcfce7':'#e2e8f0'};color:${p.cls==='신제품'?'#166534':'#475569'}">${E(p.cls)}</span></td>
      <td style="${TD}white-space:nowrap"><b>${E(p.name)}</b>${p.us_name?` <span class="note" style="font-size:10.5px">美 ${E(p.us_name)}</span>`:''}<br><span class="note" style="font-size:11px">${E(p.orig||'')}</span></td>
      <td style="${TD}font-size:12px">${latestShare(p.key)}</td>
      <td style="${TD}font-size:12px">${revCell(p)}</td>
      <td style="${TD}font-size:11.5px;color:#334155">${E(p.status||'')}${p.note?`<div class="note" style="font-size:10.5px">${E(p.note)}</div>`:''}</td></tr>`;});
    h+=`</tbody></table>`;
    return h;
  }

  function shareChart(){
    const S=D.shares||[], P=D.products||[]; if(chS) chS.destroy();
    const nm=k=>(P.find(p=>p.key===k)||{}).name||k;
    const series={}; S.forEach(s=>{ const key=nm(s.product)+' · '+s.region; (series[key]=series[key]||[]).push({x:s.d,y:s.v}); });
    const dates=[...new Set(S.map(s=>s.d))].sort();
    const multi=Object.values(series).some(v=>v.length>=2);
    $('ct_sh_note').innerHTML=multi?'':'<div class="note">아직 시점이 1개뿐인 시리즈만 있어 추이선은 시점이 2개 이상 쌓이면 자동으로 그려진다(주간 갱신 누적). 아래 표가 현재 정본.</div>';
    if(!window.Chart||!dates.length) return;
    const cols=['#1d4ed8','#dc2626','#059669','#d97706','#7c3aed','#0891b2','#be185d','#4b5563','#65a30d','#ea580c'];
    chS=new Chart($('ct_cv2'),{type:'line',data:{labels:dates,datasets:Object.entries(series).map(([k,v],i)=>({label:k,
      data:dates.map(d=>{const p=v.find(x=>x.x===d);return p?p.y:null;}),borderColor:cols[i%cols.length],backgroundColor:cols[i%cols.length],spanGaps:true,tension:.15,pointRadius:4}))},
      options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{labels:{font:{size:10.5}}}},scales:{y:{min:0,max:100,ticks:{callback:v=>v+'%',font:{size:10}}}}}});
  }

  function shareTbl(){
    const S=[...(D.shares||[])].sort((a,b)=>b.d.localeCompare(a.d)), P=D.products||[];
    const nm=k=>(P.find(p=>p.key===k)||{}).name||k;
    return `<table style="border-collapse:collapse;font-size:12px;background:#fff"><thead><tr>${['시점','제품','지역','점유율','출처'].map(x=>`<th style="${TH}">${x}</th>`).join('')}</tr></thead><tbody>${
      S.map(s=>`<tr><td style="${TD}">${E(s.d)}</td><td style="${TD}"><b>${E(nm(s.product))}</b></td><td style="${TD}">${E(s.region)}</td><td style="${TD}text-align:right"><b>${s.v}%</b></td><td style="${TD}color:#64748b;font-size:11px">${E(s.src||'')}</td></tr>`).join('')}</tbody></table>`;
  }

  function render(){
    $('ct_live').innerHTML=liveBox();
    $('ct_q').innerHTML=quarterTbl(); quarterChart();
    $('ct_p').innerHTML=productTbl();
    shareChart(); $('ct_sh').innerHTML=shareTbl();
    $('ct_watch').innerHTML='<ul style="margin:4px 0 0 18px;line-height:1.8">'+(D.watch||[]).map(w=>`<li>${E(w)}</li>`).join('')+'</ul>';
    $('ct_log').innerHTML=(D.log||[]).slice().reverse().map(l=>`<div class="note">${E(l.d)} · ${E(l.who||'')} — ${E(l.note)}</div>`).join('');
    $('ct_asof').textContent='큐레이션 기준 '+(D.as_of||'')+' · 주 1회 자동 갱신(공시·IR·증권사 리포트 웹 조사) · 추정치는 E 표기, 빈칸은 미공표';
  }

  function init(){
    if(_init) return; _init=true;
    fetch('/api/db/celltrion',{cache:'no-cache'}).then(r=>r.ok?r.json():null).then(d=>{
      if(!d||!d.products){$('ct_live').innerHTML='<div class="note">celltrion.json 로딩 실패</div>';return;}
      D=d; try{render();}catch(err){$('ct_live').innerHTML=`<div style="color:#b91c1c;font-weight:700">렌더 오류: ${E(err&&err.message||err)}</div>`;throw err;}
    });
  }
  const tb=document.querySelector('.tab[data-pane="p_ct"]');
  if(tb) tb.addEventListener('click',init);
})();
