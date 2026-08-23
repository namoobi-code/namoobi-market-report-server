/* ── (2026-08-22) 💼 Portfolio 탭 — stlead.json (매일 05:20)
   지수 12종의 최장 히스토리 차트(휠 줌·드래그 팬·로그축) + 선행지표 r값 표(개별·그룹) +
   시차 릿지회귀 예측(24개월, 백테스트 보정) + 비중 제안(맨 위).
   엔진은 부동산 relead 와 동일 — 산출물만 다르다. app.js 와 파일 분리(충돌 회피). ── */
(function(){
  const $=id=>document.getElementById(id);
  const E=s=>String(s??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
  let D=null,_init=false,cur='spx',logY=true,showPred=true,sel=[],view=null,drag=null;
  /* (2026-08-23) 가중치 조절·시나리오 — 서버가 저장한 지표별 기여도(cont)·β 로
     g' = calib × (base + Σ m_k·(cont_k + s_k·β_k)) 를 클라이언트에서 정확히 재계산.
     m_k = 가중치 배수(기본 1, ±0.1), s_k = 시나리오(+1 지표 1σ 오름 / -1 내림 / 0 기본) */
  /* (2026-08-23) 조절은 지표 키 기준 **전역** — 같은 지표를 쓰는 모든 지수에 동시 적용
     (예: CPI ▲ 를 켜면 S&P500·나스닥·금·채권 등 CPI 가 들어가는 모든 예측이 재계산) */
  let mulAll={}, scAll={};
  const mulOf=k=>mulAll[k]??1;
  const scOf=k=>scAll[k]??0;
  const isAdj=tk=>{const tg=D.targets[tk]||{};
    const p=((tg._p0||tg.pred||{})[12]||{}).cont;
    return !!p&&Object.keys(p).some(k=>mulOf(k)!==1||scOf(k)!==0);};

  function applyAdjust(tk){
    const tg=D.targets[tk]; if(!tg||!tg.pred) return;
    if(!tg._p0){tg._p0=JSON.parse(JSON.stringify(tg.pred));tg._f0=JSON.parse(JSON.stringify(tg.fut));}
    const basePx=tg.hist[tg.past];
    for(const h in tg._p0){const p0=tg._p0[h];
      if(!p0.cont){tg.pred[h]=p0;continue;}
      let raw=p0.base;
      for(const k in p0.cont) raw+=mulOf(k)*(p0.cont[k]+(scOf(k)*(p0.beta?.[k]??0)));
      const g=Math.max(-1.2,Math.min(1.2,raw*(p0.calib??1)));
      const pr=basePx*Math.exp(g), sd=p0.bsd??0.05, j=tg.past+ +h;
      tg.pred[h]={...p0,g:+g.toFixed(4),price:+pr.toFixed(2)};
      tg.fut.price[j]=+pr.toFixed(2);
      tg.fut.lo[j]=+(pr*Math.exp(-1.28*sd)).toFixed(2);
      tg.fut.hi[j]=+(pr*Math.exp(1.28*sd)).toFixed(2);
    }
  }
  function applyAdjustAll(){for(const tk in D.targets) applyAdjust(tk);}
  function resetAdjust(){mulAll={};scAll={};
    for(const tk in D.targets){const tg=D.targets[tk];
      if(tg&&tg._p0){tg.pred=JSON.parse(JSON.stringify(tg._p0));tg.fut=JSON.parse(JSON.stringify(tg._f0));}}}
  const COLS=['#b45309','#0e7490','#7c3aed','#be185d','#166534','#4338ca','#dc2626'];
  const AXW=58;

  const fm=t=>`${String(t).slice(0,4)}.${String(t).slice(4)}`;
  const addM=(ym,k)=>{let y=+String(ym).slice(0,4),m=+String(ym).slice(4)+k;
    y+=Math.floor((m-1)/12); m=(m-1)%12+1; return `${y}${String(m).padStart(2,'0')}`;};

  function serOn(tk, key){                 // 전역 지표 계열 → 타깃 t축 매핑
    const s=(D.series||{})[key]; if(!s) return null;
    const T=D.targets[tk].t, out=new Array(T.length).fill(null);
    for(let i=0;i<T.length;i++){
      // idx = (T[i] - t0) 개월차
      const a=T[i], b=s.t0;
      const d=(+a.slice(0,4)-+b.slice(0,4))*12+(+a.slice(4)-+b.slice(4));
      if(d>=0&&d<s.v.length) out[i]=s.v[d];
    }
    return out;
  }

  function draw(){
    const cv=$('pf_cv'); if(!cv||!D) return;
    const tg=D.targets[cur]; if(!tg) return;
    /* (2026-08-23) CSS(calc·100%·flex) 조합이 브라우저에서 계속 어긋남(실측 3회) —
       뷰포트 높이에서 직접 계산해 캔버스와 지표표 박스에 픽셀로 강제한다 */
    const H=Math.max(520, (window.innerHeight||900)-200);
    cv.style.height=H+'px';
    {const box=$('pf_ind')&&$('pf_ind').parentElement; if(box) box.style.height=H+'px';}
    const W=cv.clientWidth||1000; cv.width=W; cv.height=H;
    const x=cv.getContext('2d'); x.clearRect(0,0,W,H);
    const t=tg.t,N=t.length;
    if(!view) view=[0,N-1];
    const [v0,v1]=view, M=v1-v0+1;
    const P={l:8,t:18,b:20}, RW=AXW*(sel.length+1), PW=Math.max(80,W-P.l-RW);
    const X=i=>P.l+PW*(i-v0)/Math.max(1,M-1);
    x.font='10px sans-serif';
    const tf=v=>logY?Math.log10(Math.max(v,1e-9)):v;
    const rng=vs=>{const f=vs.filter(z=>z!=null); if(!f.length)return{lo:0,hi:1};
      let lo=Math.min(...f),hi=Math.max(...f);
      if(hi===lo){hi=lo+Math.abs(lo||1)*.1;lo-=Math.abs(lo||1)*.1;}
      const p=(hi-lo)*.07; return{lo:lo-p,hi:hi+p};};
    const seg=a=>a.slice(v0,v1+1);
    const priceVals=[...seg(tg.hist),...(showPred?[...seg(tg.fut.price),...seg(tg.fut.lo),...seg(tg.fut.hi)]:[])]
      .map(v=>v==null?null:tf(v));
    const scP=rng(priceVals);
    const overlays=sel.map((k,i)=>({k,color:COLS[i%COLS.length],v:serOn(cur,k)}));
    const scO=overlays.map(o=>rng(seg(o.v||[])));
    const Y=(sc,v)=>P.t+(H-P.t-P.b)*(1-(v-sc.lo)/(sc.hi-sc.lo));
    /* 격자·연도 */
    x.strokeStyle='#eef1f4';
    for(let g=0;g<=4;g++){const yy=P.t+(H-P.t-P.b)*g/4;x.beginPath();x.moveTo(P.l,yy);x.lineTo(P.l+PW,yy);x.stroke();}
    x.fillStyle='#98a2ad';
    const yrStep=M>720?10:(M>360?5:(M>140?2:1));
    for(let i=v0;i<=v1;i++){const s=String(t[i]);
      if(s.slice(4)==='01'&&(+s.slice(0,4))%yrStep===0) x.fillText(s.slice(0,4),X(i)-12,H-5);}
    /* 예측 경계·밴드 */
    const past=tg.past;
    if(showPred&&past>=v0&&past<=v1){
      x.save();x.setLineDash([4,4]);x.strokeStyle='#c8ced6';
      x.beginPath();x.moveTo(X(past),P.t-8);x.lineTo(X(past),H-P.b);x.stroke();x.restore();
      x.fillStyle='#98a2ad';x.fillText('예측 →',X(past)+3,P.t-1);
      x.beginPath();let st=false;
      for(let j=Math.max(past,v0);j<=v1;j++){const v=tg.fut.hi[j];if(v==null)continue;
        const px=X(j),py=Y(scP,tf(v)); st?x.lineTo(px,py):(x.moveTo(px,py),st=true);}
      for(let j=v1;j>=Math.max(past,v0);j--){const v=tg.fut.lo[j];if(v==null)continue;x.lineTo(X(j),Y(scP,tf(v)));}
      x.closePath();x.fillStyle='rgba(31,41,55,.10)';x.fill();
    }
    /* 오버레이 지표 */
    overlays.forEach((o,i)=>{ if(!o.v) return;
      x.strokeStyle=o.color;x.lineWidth=1.4;x.beginPath();let on=false;
      for(let j=v0;j<=v1;j++){const v=o.v[j];if(v==null){on=false;continue;}
        const px=X(j),py=Y(scO[i],v); on?x.lineTo(px,py):(x.moveTo(px,py),on=true);}
      x.stroke();x.lineWidth=1;});
    /* 실측 */
    x.strokeStyle='#1f2937';x.lineWidth=2;x.beginPath();let on=false;
    for(let j=v0;j<=v1;j++){const v=tg.hist[j];if(v==null){on=false;continue;}
      const px=X(j),py=Y(scP,tf(v)); on?x.lineTo(px,py):(x.moveTo(px,py),on=true);}
    x.stroke();
    /* 예측선 */
    if(showPred){x.save();x.setLineDash([6,4]);x.strokeStyle='#d9534f';x.lineWidth=2;x.beginPath();on=false;
      for(let j=v0;j<=v1;j++){const v=tg.fut.price[j];if(v==null){on=false;continue;}
        const px=X(j),py=Y(scP,tf(v)); on?x.lineTo(px,py):(x.moveTo(px,py),on=true);}
      x.stroke();x.restore();x.lineWidth=1;}
    /* 우측 축 — 0번 기준선 + 오버레이 */
    const axes=[{sc:scP,color:'#1f2937',name:tg.label,log:logY},
                ...overlays.map((o,i)=>({sc:scO[i],color:o.color,
                  name:(D.meta[o.k]||{}).label||o.k,log:false}))];
    axes.forEach((a,i)=>{
      const x0=P.l+PW+AXW*i;
      x.strokeStyle='#e5e8ec';x.beginPath();x.moveTo(x0,P.t-8);x.lineTo(x0,H-P.b);x.stroke();
      x.fillStyle=a.color;x.globalAlpha=.08;x.fillRect(x0,P.t-8,AXW,H-P.t-P.b+8);x.globalAlpha=1;
      x.fillStyle=a.color;
      for(let g=0;g<=4;g++){let vv=a.sc.lo+(a.sc.hi-a.sc.lo)*(1-g/4);
        if(a.log)vv=Math.pow(10,vv);
        const yy=P.t+(H-P.t-P.b)*g/4;
        x.fillText(Math.abs(vv)>=1e4?Math.round(vv).toLocaleString():(Math.abs(vv)>=100?vv.toFixed(0):vv.toFixed(2)),x0+3,yy+3);}
      x.save();x.font='bold 10px sans-serif';
      x.fillText(a.name.length>6?a.name.slice(0,6):a.name,x0+3,P.t-10);x.restore();
    });
  }

  function setView(a,b){const N=D.targets[cur].t.length;
    a=Math.max(0,Math.round(a)); b=Math.min(N-1,Math.round(b));
    if(b-a<12){const c=(a+b)/2; a=c-6; b=c+6; a=Math.max(0,a); b=Math.min(N-1,b);}
    view=[Math.round(a),Math.round(b)]; draw();}

  function bindChart(){
    const cv=$('pf_cv'); if(!cv||cv._pf) return; cv._pf=1;
    /* (2026-08-23) 레이아웃 확정 전에 그려져 차트가 작게 남는 문제 — 크기 변화를 감지해 재드로우 */
    if(window.ResizeObserver){const ro=new ResizeObserver(()=>{if(D)draw();});ro.observe(cv);}
    cv.addEventListener('wheel',e=>{e.preventDefault();
      const r=cv.getBoundingClientRect(), fx=(e.clientX-r.left)/r.width;
      const [a,b]=view, M=b-a, c=a+M*fx, f=e.deltaY>0?1.2:1/1.2;
      setView(c-(c-a)*f, c+(b-c)*f);},{passive:false});
    cv.addEventListener('mousedown',e=>{drag={x:e.clientX,v:[...view]};});
    window.addEventListener('mousemove',e=>{if(!drag)return;
      const r=cv.getBoundingClientRect(), M=drag.v[1]-drag.v[0];
      const dx=(e.clientX-drag.x)/r.width*M;
      const N=D.targets[cur].t.length;
      let a=drag.v[0]-dx,b=drag.v[1]-dx;
      if(a<0){b-=a;a=0;} if(b>N-1){a-=b-(N-1);b=N-1;}
      view=[Math.round(a),Math.round(b)]; draw();});
    window.addEventListener('mouseup',()=>{drag=null;});
    cv.addEventListener('dblclick',()=>{view=null;draw();});
  }

  function fmt(v,d){if(v==null)return '—';
    if(+v>=999)return '<span title="고변동 자산 — 백테스트 오차가 커 신뢰 불가">999+</span>';
    return (+v).toFixed(d==null?1:d);}

  function render(){
    const tg=D.targets[cur]; if(!tg) return;
    /* ── ① 비중 제안 (맨 위) — 조절이 반영되도록 targets.pred 에서 매번 재계산 ── */
    const rowsA=(D.alloc||[]).filter(a=>a.key!=='cash');
    const gL=a=>{const p=((D.targets[a.key]||{}).pred||{})[12];
      return p?p.g:(a.g12!=null?Math.log(1+a.g12/100):null);};
    const tiltable=rowsA.filter(a=>a.sug!=null&&gL(a)!=null);
    const avg=tiltable.length?tiltable.reduce((s,a)=>s+gL(a),0)/tiltable.length:0;
    let tot=0;
    const gh=(tg2,h)=>{const p=(tg2.pred||{})[h];return p?+(Math.exp(p.g)*100-100).toFixed(1):null;};
    const html=rowsA.map(a=>{
      const tg=D.targets[a.key]||{};
      const p12=(tg.pred||{})[12], p24=(tg.pred||{})[24];
      const g1=gh(tg,1), g3=gh(tg,3), g6=gh(tg,6);
      const g12=p12?+(Math.exp(p12.g)*100-100).toFixed(1):a.g12;
      const g24=p24?+(Math.exp(p24.g)*100-100).toFixed(1):a.g24;
      let sug=null,tilt=null;
      if(a.sug!=null&&gL(a)!=null){
        const cap=a.base>0?5:3, lo=a.base>0?-5:0;
        tilt=Math.max(lo,Math.min(cap,Math.round((gL(a)-avg)*40)));
        sug=Math.max(0,a.base+tilt); tot+=sug;
      }
      const bad=g12!=null&&((tg.bt||{}).mape==null||(tg.bt||{}).mape>50);
      const adj=isAdj(a.key);
      const pv=v=>v==null?'—':`<span style="${bad?'opacity:.35':''}${adj?';text-decoration:underline dotted':''}" ${bad?'title="백테스트 오차가 커 신뢰 불가 — 참고하지 말 것"':(adj?'title="가중치·시나리오 조절 반영값"':'')}>${bad?'⚠ ':''}${adj?'✎ ':''}${v>0?'+':''}${v}%</span>`;
      return `<tr${D.targets[a.key]?` style="cursor:pointer" data-tk="${a.key}"`:''}>
      <td><b>${E(a.asset)}</b></td><td>${E(a.etf)}</td>
      <td class="num">${a.base==null?'—':a.base+'%'}</td>
      <td class="num">${pv(g1)}</td><td class="num">${pv(g3)}</td><td class="num">${pv(g6)}</td>
      <td class="num" style="color:${g12>0?'#0f766e':(g12<0?'#b91c1c':'#666')}">${pv(g12)}</td>
      <td class="num">${pv(gh(tg,18))}</td>
      <td class="num">${pv(g24)}</td>
      <td class="num"><b>${sug==null?'현금군':sug+'%'}</b>${tilt?` <span class="note">(${tilt>0?'+':''}${tilt})</span>`:''}</td></tr>`;}).join('');
    const cashBase=((D.alloc||[]).find(a=>a.key==='cash')||{}).base??15;
    $('pf_alloc').innerHTML=`<table><thead><tr><th>자산</th><th>매수 상품</th>
      <th style="text-align:right">기본 비중</th>
      <th style="text-align:right">1M 예측</th><th style="text-align:right">3M 예측</th><th style="text-align:right">6M 예측</th>
      <th style="text-align:right" title="선행지표 릿지회귀 · 백테스트 보정계수 적용 후 (✎=조절 반영)">12M 예측</th>
      <th style="text-align:right">18M 예측</th>
      <th style="text-align:right">24M 예측</th>
      <th style="text-align:right" title="기본비중 ± 12개월 상대예측 (코어 ±5%p · 위성 +3%p 한도)">제안 비중</th></tr></thead><tbody>${html}
      <tr><td><b>현금·단기채</b></td><td>파킹/머니마켓</td><td class="num">${cashBase}%</td>
      <td class="num">—</td><td class="num">—</td><td class="num">—</td>
      <td class="num">—</td><td class="num">—</td><td class="num">—</td><td class="num"><b>${Math.max(0,100-tot)}%</b></td></tr></tbody></table>
      <div class="note" style="margin-top:5px">${E(D.note||'')}</div>`;
    $('pf_alloc').querySelectorAll('[data-tk]').forEach(tr=>tr.onclick=()=>{cur=tr.dataset.tk;sel=[];view=null;render();});
    /* ── ② 지수 칩 + 컨트롤 ── */
    const btn=(on,txt,attr)=>`<button ${attr||''} style="padding:3px 9px;font-size:11.5px;border:1px solid ${on?'#1f2937':'#d7dce3'};border-radius:6px;cursor:pointer;background:${on?'#1f2937':'#fff'};color:${on?'#fff':'#444'}">${txt}</button>`;
    $('pf_tg').innerHTML=Object.entries(D.targets).map(([k,v])=>btn(k===cur,E(v.label),`data-k="${k}"`)).join(' ');
    $('pf_tg').querySelectorAll('[data-k]').forEach(b=>b.onclick=()=>{cur=b.dataset.k;sel=[];view=null;render();});
    const N=tg.t.length;
    const spans={'전체':N,'30년':384,'10년':144,'5년':84};
    $('pf_ctl').innerHTML=Object.keys(spans).map(s=>btn(false,s,`data-s="${s}"`)).join(' ')
      +' '+btn(logY,'로그축','id="pf_log"')+' '+btn(showPred,'예측','id="pf_pred"')
      +` <span class="note">휠=확대축소 · 드래그=이동 · 더블클릭=전체 · ${fm(tg.t[0])}~${fm(tg.t[tg.past])} 실측 ${tg.past+1}개월</span>`;
    $('pf_ctl').querySelectorAll('[data-s]').forEach(b=>b.onclick=()=>{
      const n=Math.min(spans[b.dataset.s],N); setView(N-n,N-1);});
    $('pf_log').onclick=()=>{logY=!logY;render();};
    $('pf_pred').onclick=()=>{showPred=!showPred;render();};
    /* ── ③ 지표 표 (그룹 통합 r + 개별 r·가중치) ── */
    const lead=tg.lead||{};
    /* (2026-08-23) r 색 = 미국식 주가 색 — 양수(지표↑=주가↑) 초록, 음수(지표↑=주가↓) 빨강.
       |r|<0.2 는 옅게(사실상 무상관), ≥0.5 는 굵게 */
    const rc=v=>{const a=Math.abs(v);
      return `<span style="color:${v>0?'#16a34a':(v<0?'#dc2626':'#666')};opacity:${a<.2?.45:1};font-weight:${a>=.5?700:400}">${(+v).toFixed(3)}</span>`;};
    /* (2026-08-23) 통합 행 바로 아래에 그 그룹의 개별 지표를 들여쓰기로 붙인다 */
    const has12=Object.values(lead).some(l=>l.r12!=null);   // 구 JSON 호환
    const hasH=Object.values(lead).some(l=>l.r1!=null);     // 1·3·6M 열 있는 JSON
    const HZS=[1,3,6,12,18,24].filter(h=>Object.values(lead).some(l=>l['r'+h]!=null));
    const hasAdj=!!(((tg.pred||{})[12]||{}).cont);          // 기여도 있는 JSON 만 조절 가능
    const bsty='padding:0 3px;font-size:10.5px;border:1px solid #d7dce3;border-radius:4px;cursor:pointer;background:#fff';
    /* (2026-08-23) 사이드 배치용 압축 — 출처는 툴팁으로, 그룹 열 제거(들여쓰기로 구분), 폰트 11px */
    const indRow=(k,ind)=>{const l=lead[k],m=D.meta[k]||{};const on=sel.includes(k);
      const mv=mulOf(k), sv=scOf(k);
      const hzCells=HZS.map(h=>`<td class="num">${l['lag'+h]!=null?l['lag'+h]+'M':'—'}</td>
        <td class="num">${l['r'+h]!=null?rc(l['r'+h]):'—'}</td>`).join('');
      const adjCell=hasAdj?`<td class="num" style="white-space:nowrap">
        <button data-mm="${k}" data-d="-1" style="${bsty}" title="가중치 -0.1">−</button><b style="color:${mv!==1?'#b45309':'#333'}">${mv.toFixed(1)}</b><button data-mm="${k}" data-d="1" style="${bsty}" title="가중치 +0.1">＋</button>
        <button data-ms="${k}" data-s="1" style="${bsty};${sv===1?'background:#16a34a;color:#fff;border-color:#16a34a':''}" title="이 지표가 1σ 오른다고 가정">▲</button><button data-ms="${k}" data-s="-1" style="${bsty};${sv===-1?'background:#dc2626;color:#fff;border-color:#dc2626':''}" title="이 지표가 1σ 내린다고 가정">▼</button></td>`:'';
      return `<tr data-i="${k}" style="cursor:pointer${on?';background:#fffbe6':''}" title="${E(m.src||'')}">
      <td style="padding-left:${ind?16:4}px;white-space:nowrap">${ind?'└ ':''}${on?'✔ ':''}${E(m.label||k)}</td>
      <td class="num">${l.lag}M</td>
      <td class="num">${rc(l.corr)}</td>${hzCells}${HZS.length?`
      <td class="num"><b style="color:${mv!==1?'#b45309':''}">${l.w12!=null?(l.w12*mv*100).toFixed(1)+'%':'—'}</b></td>`:`<td class="num">${(l.w*100).toFixed(1)}%</td>`}${adjCell}</tr>`;};
    const gArr=(tg.groups||[]).slice().sort((a,b)=>Math.abs(b.corr)-Math.abs(a.corr));
    const used=new Set();
    let body=gArr.map(g=>{
      const mem=g.members.filter(k=>lead[k]).sort((a,b)=>Math.abs(lead[b].corr)-Math.abs(lead[a].corr));
      mem.forEach(k=>used.add(k));
      const NC=3+HZS.length*2+1+(hasAdj?1:0);
      const pad=('<td class="num">—</td>').repeat(NC-3);
      return `<tr style="background:#f4f6f8"><td style="white-space:nowrap"><b>▣ ${E(g.name)} 통합</b> <span class="note">${mem.length}개</span></td>
        <td class="num">${g.lag}M</td><td class="num">${rc(g.corr)}</td>${pad}</tr>`
        +mem.map(k=>indRow(k,true)).join('');
    }).join('');
    const rest=Object.keys(lead).filter(k=>!used.has(k))
      .sort((a,b)=>Math.abs(lead[b].corr)-Math.abs(lead[a].corr));
    if(rest.length)
      body+=`<tr style="background:#f4f6f8"><td colspan="${3+HZS.length*2+1+(hasAdj?1:0)}"><b>▣ 단독 지표</b> <span class="note">그룹 미구성</span></td></tr>`
        +rest.map(k=>indRow(k,true)).join('');
    const wSum=has12?Object.keys(lead).reduce((s,k)=>s+(lead[k].w12||0)*mulOf(k),0):1;
    $('pf_ind').innerHTML=`${hasAdj?`<div style="text-align:right;margin:1px 0"><button id="pf_rst2" style="${bsty}" title="가중치 배수·지표값 시나리오를 모두 원상복구 (전 지수 반영)">⟲ 조절 전체 초기화</button></div>`:''}
      <table style="font-size:11px"><thead><tr><th title="클릭=차트 겹쳐보기 · 마우스 올리면 출처">지표</th>
      <th style="text-align:right" title="전 구간 상관 최대 시차 — 0M이면 동행지표(현재 확인용, 선행 아님)">시차</th>
      <th style="text-align:right" title="그 시차에서의 상관 — '얼마나 닮았나'이지 예측 기여가 아님">r</th>${
      HZS.map(h=>`<th style="text-align:right" title="${h}개월 예측에 출전 가능한 시차(≥${h}개월) 중 상관 최대 지점">${h}M</th>
      <th style="text-align:right" title="${h}개월 이상 선행 구간에서의 상관 — 동행지표는 먼 지평에서 뚝 떨어진다">${h}M r</th>`).join('')}${has12?`
      <th style="text-align:right" title="|12M r| 정규화 — 12개월 예측에서의 실제 상대 영향력. 조절 배수 반영">가중치</th>`:`
      <th style="text-align:right">가중치</th>`}${hasAdj?`
      <th style="text-align:right;white-space:nowrap" title="가중치조절(−/＋) = 배수 ±0.1, 예측 기여를 그 배수만큼 · 지표값조절(▲/▼) = 이 지표가 1σ 오름/내림 가정 시나리오. 바꾸면 차트 예측선·비중 제안이 즉시 재계산">가중치조절 | 지표값조절</th>`:''}</tr></thead><tbody>${body}</tbody></table>${
      hasAdj?`<div class="note" style="margin:5px 0">실효 Σ가중치 <b style="color:${Math.abs(wSum-1)>.001?'#b45309':'#333'}">${(wSum*100).toFixed(0)}%</b> (기본 100%)
      · <button id="pf_rst" style="${bsty}">조절 초기화</button> — 예측선·비중 제안에 즉시 반영됨(저장 안 됨·새로고침 시 초기화)</div>`:''}
      <div class="note" style="margin-top:4px;line-height:1.6">💡 <b>시차·r</b> 은 "몇 개월 밀면 가장 닮나"(진단용) — 시차 0이면 <b>동행지표</b>라 지금 상황 확인엔 좋지만
      미래 예측엔 못 쓴다(주가 자체가 경기 선행지표라 실물·심리가 주가를 못 앞선다).
      <b>12M시차·12M r·예측 가중치</b>가 실제 12개월 예측 기준이다: 12개월 이상 선행 구간에서만 다시 잰 상관이라,
      동행지표는 여기서 값이 뚝 떨어지고 M2·금리처럼 진짜 선행하는 지표가 커진다 — 두 열을 비교해 보면 차이가 보인다.</div>`;
    $('pf_ind').querySelectorAll('[data-i]').forEach(tr=>tr.onclick=()=>{
      const k=tr.dataset.i;
      sel=sel.includes(k)?sel.filter(x=>x!==k):(sel.length>=6?sel:[...sel,k]);
      render();});
    /* 조절 버튼 — 행 클릭(오버레이 토글)과 분리 */
    $('pf_ind').querySelectorAll('[data-mm]').forEach(b=>b.onclick=e=>{e.stopPropagation();
      const k=b.dataset.mm, d=+b.dataset.d;
      mulAll[k]=Math.max(0,Math.min(3,+((mulOf(k)+d*0.1).toFixed(1))));
      applyAdjustAll(); render();});               // 전 지수 동시 재계산
    $('pf_ind').querySelectorAll('[data-ms]').forEach(b=>b.onclick=e=>{e.stopPropagation();
      const k=b.dataset.ms, s=+b.dataset.s;
      scAll[k]=(scOf(k)===s)?0:s;                  // 같은 버튼 다시 누르면 해제
      applyAdjustAll(); render();});
    {const rb=$('pf_rst'); if(rb) rb.onclick=()=>{resetAdjust();render();};}
    {const rb=$('pf_rst2'); if(rb) rb.onclick=()=>{resetAdjust();render();};}
    /* ── ④ 백테스트 표 ── */
    const bh=(tg.bt||{}).by_h||{};
    /* (2026-08-23) 전 지수 평균 스킬·방향 — 신뢰불가 자산(MAPE>50%, BTC 등)은 평균에서 제외 */
    const avgH=h=>{const sk=[],hi=[];
      for(const t2 of Object.values(D.targets)){
        const bt2=t2.bt||{}, b2=(bt2.by_h||{})[h];
        if(!b2||bt2.mape==null||bt2.mape>50) continue;
        if(b2.skill!=null) sk.push(b2.skill);
        if(b2.hit!=null) hi.push(b2.hit);}
      return {sk:sk.length?sk.reduce((a,c)=>a+c,0)/sk.length:null,
              hi:hi.length?hi.reduce((a,c)=>a+c,0)/hi.length:null};};
    $('pf_bt').innerHTML=`<div class="note" style="margin-bottom:3px">MAPE·단순예측 오차·방향적중·스킬·보정계수 = <b>${E(tg.label)}</b> 기준 · '전지수' 두 열만 12개 자산 평균(신뢰불가 제외)</div>
      <table><thead><tr><th>지평</th><th style="text-align:right" title="선택한 지수의 예측가격이 실제와 평균 몇 % 어긋났나">평균 오차(MAPE)</th>
      <th style="text-align:right" title="'변동 없음'이라고 찍었을 때의 오차 — 이보다 작아야 의미">단순예측 오차</th>
      <th style="text-align:right" title="예측 변화율 대비 실제 실현 비율 — 예측선에 곱해져 있음">보정계수</th>
      <th style="text-align:right" title="선택한 지수의 오를지/내릴지 방향 적중">${E(tg.label)} 방향적중</th>
      <th style="text-align:right" title="스킬 = 1 − MAPE/단순예측오차. 0=게으른 예측과 동일, 0.5=오차 절반 감소">${E(tg.label)} 스킬</th>
      <th style="text-align:right" title="신뢰 가능한 전 지수(MAPE 50% 이하)의 평균 방향 적중">전지수 방향</th>
      <th style="text-align:right" title="전 지수 평균 스킬 — 이 지평의 모델 전반 신뢰도">전지수 스킬</th></tr></thead><tbody>${
      [1,3,6,12,18,24].filter(h=>bh[h]).map(h=>{const b=bh[h],a=avgH(h);
        return `<tr><td>${h}개월 뒤</td><td class="num">${fmt(b.mape,2)}%</td>
        <td class="num">${fmt(b.naive,2)}%</td>
        <td class="num">${fmt(b.calib,2)}</td>
        <td class="num"><b>${fmt(b.hit,1)}%</b></td>
        <td class="num"><b>${b.skill!=null?(+b.skill).toFixed(2):'—'}</b></td>
        <td class="num">${a.hi!=null?a.hi.toFixed(1)+'%':'—'}</td>
        <td class="num">${a.sk!=null?a.sk.toFixed(2):'—'}</td></tr>`;}).join('')}</tbody></table>
      <div class="note" style="margin-top:4px">워크포워드 백테스트 ${((tg.bt||{}).origins)||''}시점 — 그 시점까지 자료만으로 시차 탐색부터 다시 수행. 성적이 나쁘면 나쁜 대로 표시(포장 없음). 예측·비중 제안은 리서치 참고용이며 투자권유가 아님.</div>`;
    bindChart(); draw();
  }

  const PFV='i';                                  // 진단 배지용 버전
  function init(){
    if(_init) return; _init=true;
    fetch('/api/db/stlead',{cache:'reload'}).then(r=>r.ok?r.json():null).then(d=>{
      if(!d||!d.targets||!Object.keys(d.targets).length){
        $('pf_alloc').innerHTML='<div class="note">수집 대기 중 — stlead.py 첫 실행이 끝나면 표시됩니다(매일 05:20 자동 갱신).</div>'; return;}
      D=d; if(!D.targets[cur]) cur=Object.keys(D.targets)[0];
      {const e=$('pf_asof');
       const hasC=!!(((D.targets.spx||{}).pred||{})[12]||{}).cont;
       if(e) e.textContent=`${d.src||''} · 수집 ${d.asof||''} · pf v=${PFV} · 조절데이터 ${hasC?'O':'X'}`;}
      try{render();}catch(err){
        $('pf_alloc').innerHTML=`<div style="color:#b91c1c;font-weight:700">렌더 오류: ${E(err&&err.message||err)}<br><span class="note">${E((err&&err.stack||'').slice(0,300))}</span></div>`;
        throw err;}
    }).catch(()=>{$('pf_alloc').innerHTML='<div class="note">불러오기 실패 — 새로고침 해주세요.</div>';});
  }
  const tb=document.querySelector('.tab[data-pane="p_pf"]');
  if(tb) tb.addEventListener('click',()=>{init(); setTimeout(draw,50);});
  window.addEventListener('resize',()=>{if(D)draw();});
})();
