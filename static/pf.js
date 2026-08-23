/* ── (2026-08-22) 💼 Portfolio 탭 — stlead.json (매일 05:20)
   지수 12종의 최장 히스토리 차트(휠 줌·드래그 팬·로그축) + 선행지표 r값 표(개별·그룹) +
   시차 릿지회귀 예측(24개월, 백테스트 보정) + 비중 제안(맨 위).
   엔진은 부동산 relead 와 동일 — 산출물만 다르다. app.js 와 파일 분리(충돌 회피). ── */
(function(){
  const $=id=>document.getElementById(id);
  const E=s=>String(s??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
  let D=null,_init=false,cur='spx',logY=true,showPred=true,sel=[],view=null,drag=null;
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
    const W=cv.clientWidth||1000,H=cv.clientHeight||520; cv.width=W; cv.height=H;
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
    /* ── ① 비중 제안 (맨 위) ── */
    $('pf_alloc').innerHTML=`<table><thead><tr><th>자산</th><th>매수 상품</th>
      <th style="text-align:right">기본 비중</th>
      <th style="text-align:right" title="선행지표 릿지회귀 · 백테스트 보정계수 적용 후">12M 예측</th>
      <th style="text-align:right">24M 예측</th>
      <th style="text-align:right" title="기본비중 ± 12개월 상대예측 (코어 ±5%p · 위성 +3%p 한도)">제안 비중</th></tr></thead><tbody>${
      (D.alloc||[]).map(a=>{
        const tilt=(a.sug!=null&&a.base!=null)?a.sug-a.base:null;
        /* (2026-08-23) 백테스트 MAPE 50% 초과 자산(BTC 등)은 예측을 흐리게+⚠ — 표본이
           짧아 통계적으로 무의미(실측: BTC 24M -47%는 반감기 사이클 그림자 학습 의심) */
        const tgb=(D.targets[a.key]||{}).bt||{};
        const bad=a.g12!=null&&(tgb.mape==null||tgb.mape>50);
        const pv=v=>v==null?'—':`<span style="${bad?'opacity:.35':''}" ${bad?'title="백테스트 오차가 커 신뢰 불가 — 참고하지 말 것"':''}>${bad?'⚠ ':''}${v>0?'+':''}${v}%</span>`;
        return `<tr${D.targets[a.key]?` style="cursor:pointer" data-tk="${a.key}"`:''}>
        <td><b>${E(a.asset)}</b></td><td>${E(a.etf)}</td>
        <td class="num">${a.base==null?'—':a.base+'%'}</td>
        <td class="num" style="color:${a.g12>0?'#0f766e':(a.g12<0?'#b91c1c':'#666')}">${pv(a.g12)}</td>
        <td class="num">${pv(a.g24)}</td>
        <td class="num"><b>${a.sug==null?'현금군':a.sug+'%'}</b>${tilt?` <span class="note">(${tilt>0?'+':''}${tilt})</span>`:''}</td></tr>`;}).join('')}</tbody></table>
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
    const rc=v=>`<span style="color:${Math.abs(v)>=.5?(v>0?'#0f766e':'#b91c1c'):'#666'};font-weight:${Math.abs(v)>=.5?700:400}">${(+v).toFixed(3)}</span>`;
    /* (2026-08-23) 통합 행 바로 아래에 그 그룹의 개별 지표를 들여쓰기로 붙인다 */
    const indRow=(k,ind)=>{const l=lead[k],m=D.meta[k]||{};const on=sel.includes(k);
      return `<tr data-i="${k}" style="cursor:pointer${on?';background:#fffbe6':''}">
      <td style="padding-left:${ind?22:8}px">${ind?'└ ':''}${on?'✔ ':''}${E(m.label||k)} <span class="note">${E(m.src||'')}</span></td>
      <td>${E(m.group||'')}</td><td class="num">${l.lag}개월</td>
      <td class="num">${rc(l.corr)}</td><td class="num">${(l.w*100).toFixed(1)}%</td></tr>`;};
    const gArr=(tg.groups||[]).slice().sort((a,b)=>Math.abs(b.corr)-Math.abs(a.corr));
    const used=new Set();
    let body=gArr.map(g=>{
      const mem=g.members.filter(k=>lead[k]).sort((a,b)=>Math.abs(lead[b].corr)-Math.abs(lead[a].corr));
      mem.forEach(k=>used.add(k));
      return `<tr style="background:#f4f6f8"><td><b>▣ ${E(g.name)} 통합</b> <span class="note">${mem.length}개 합성 — 아래 개별</span></td>
        <td>${E(g.name)}</td><td class="num">${g.lag}개월</td><td class="num">${rc(g.corr)}</td><td class="num">—</td></tr>`
        +mem.map(k=>indRow(k,true)).join('');
    }).join('');
    const rest=Object.keys(lead).filter(k=>!used.has(k))
      .sort((a,b)=>Math.abs(lead[b].corr)-Math.abs(lead[a].corr));
    if(rest.length)
      body+=`<tr style="background:#f4f6f8"><td colspan="5"><b>▣ 단독 지표</b> <span class="note">그룹 미구성(2개 미만)</span></td></tr>`
        +rest.map(k=>indRow(k,true)).join('');
    $('pf_ind').innerHTML=`<table><thead><tr><th>지표 <span class="note">(클릭=차트 겹쳐보기)</span></th><th>그룹</th>
      <th style="text-align:right" title="지표가 몇 개월 선행하는지 — 전 구간 상관 최대 시차">시차</th>
      <th style="text-align:right" title="시차 적용 후 지수 전년비 성장률과의 상관계수">r</th>
      <th style="text-align:right" title="|r| 정규화 — 예측 회귀에서의 상대 영향력 표시용(실제 계수는 지평별 릿지가 산출)">가중치</th></tr></thead><tbody>${body}</tbody></table>
      <div class="note" style="margin-top:4px;line-height:1.6">💡 <b>시차 0개월 = 동행지표</b>다(선행 아님). 실물·심리 지표가 0인 이유:
      <b>주가 자체가 경기 선행지표</b>라 실물이 주가를 앞서지 못하고 같이 움직인다. 표의 시차·r 은 전 구간 최적값이고,
      실제 h개월 예측에는 시차 h개월 이상 구간에서 재탐색한 값만 출전한다 — 동행지표는 그만큼 영향력이 줄고,
      M2·금리처럼 진짜 선행하는 지표가 먼 지평을 주도한다.</div>`;
    $('pf_ind').querySelectorAll('[data-i]').forEach(tr=>tr.onclick=()=>{
      const k=tr.dataset.i;
      sel=sel.includes(k)?sel.filter(x=>x!==k):(sel.length>=6?sel:[...sel,k]);
      render();});
    /* ── ④ 백테스트 표 ── */
    const bh=(tg.bt||{}).by_h||{};
    $('pf_bt').innerHTML=`<table><thead><tr><th>지평</th><th style="text-align:right">평균 오차(MAPE)</th>
      <th style="text-align:right" title="'변동 없음'이라고 찍었을 때의 오차 — 이보다 작아야 의미">단순예측 오차</th>
      <th style="text-align:right">방향 적중률</th><th style="text-align:right" title="예측 변화율 대비 실제 실현 비율 — 예측선에 곱해져 있음">보정계수</th></tr></thead><tbody>${
      [1,3,6,12,18,24].filter(h=>bh[h]).map(h=>{const b=bh[h];
        return `<tr><td>${h}개월 뒤</td><td class="num">${fmt(b.mape,2)}%</td>
        <td class="num">${fmt(b.naive,2)}%</td><td class="num"><b>${fmt(b.hit,1)}%</b></td>
        <td class="num">${fmt(b.calib,2)}</td></tr>`;}).join('')}</tbody></table>
      <div class="note" style="margin-top:4px">워크포워드 백테스트 ${((tg.bt||{}).origins)||''}시점 — 그 시점까지 자료만으로 시차 탐색부터 다시 수행. 성적이 나쁘면 나쁜 대로 표시(포장 없음). 예측·비중 제안은 리서치 참고용이며 투자권유가 아님.</div>`;
    bindChart(); draw();
  }

  function init(){
    if(_init) return; _init=true;
    fetch('/api/db/stlead').then(r=>r.ok?r.json():null).then(d=>{
      if(!d||!d.targets||!Object.keys(d.targets).length){
        $('pf_alloc').innerHTML='<div class="note">수집 대기 중 — stlead.py 첫 실행이 끝나면 표시됩니다(매일 05:20 자동 갱신).</div>'; return;}
      D=d; if(!D.targets[cur]) cur=Object.keys(D.targets)[0];
      {const e=$('pf_asof'); if(e) e.textContent=`${d.src||''} · 수집 ${d.asof||''}`;}
      render();
    }).catch(()=>{$('pf_alloc').innerHTML='<div class="note">불러오기 실패 — 새로고침 해주세요.</div>';});
  }
  const tb=document.querySelector('.tab[data-pane="p_pf"]');
  if(tb) tb.addEventListener('click',()=>{init(); setTimeout(draw,50);});
  window.addEventListener('resize',()=>{if(D)draw();});
})();
