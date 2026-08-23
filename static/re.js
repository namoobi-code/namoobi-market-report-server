/* ── (2026-08-23) 🔮 RE 예측 탭 — repred.json (매일 08:10)
   부동산 실거래 중위가 장기차트 + r-가중 합성 예측(릿지 미사용 — 사용자 지정 방식).
   지평 h 예측 = ȳ_h + sd_y·Σ w_k·r_k·z_k (w=|r|비례, 시차≥h) × 백테스트 보정.
   지표는 그룹(공급/수요·금융/심리/가격/거시/소득)으로 묶어 보여주되 가중치는 지표별
   시차·r 로 개별 결정. 기사(2026-08) 통설 선행기간을 실측 시차와 나란히 표시.
   가중치 배수(−/＋)·시나리오(▲/▼ ±1σ) 조절 시 예측선 즉시 재계산. pf.js 와 구조 동일. ── */
(function(){
  const $=id=>document.getElementById(id);
  const E=s=>String(s??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
  let D=null,_init=false,cur='서울',logY=false,showPred=true,view=null,drag=null;
  let mulAll={},scAll={};                       // 조절은 지표 키 기준 전역(모든 지역 동시)
  const mulOf=k=>mulAll[k]??1, scOf=k=>scAll[k]??0;
  const HZS=[1,3,6,12,18,24,30];   // (2026-08-23) 부동산 장주기: 1M 유지 + 30M 추가 (사용자 확정)
  const fm=t=>`${String(t).slice(0,4)}.${String(t).slice(4)}`;

  /* ── 지역별 차트 배열 캐시: TT=t+ext, hist, fut(전장) ── */
  function axis(reg){
    const P=D.pred[reg]; if(!P) return null;
    if(!P._ax){
      const TT=D.t.concat(P.ext), N=TT.length, past=P.past;
      const ma=(D.price[reg]||{}).ma||[];
      const hist=ma.concat(new Array(P.ext.length).fill(null));
      const mk=a=>{const o=new Array(N).fill(null);
        for(let i=0;i<a.length;i++) if(a[i]!=null) o[past+1+i]=a[i];
        return o;};
      P._ax={TT,N,past,hist};
      P._f0={price:mk(P.fut.price),lo:mk(P.fut.lo),hi:mk(P.fut.hi)};
      P._f0.price[past]=P.last.price;
      P.futX=JSON.parse(JSON.stringify(P._f0));
    }
    return P._ax;
  }

  /* ── 조절 재계산 — 서버 후처리(보정→3점 평활→역사범위 가드→밴드)를 그대로 재현 ── */
  const isAdj=()=>Object.keys(mulAll).some(k=>mulAll[k]!==1)||Object.keys(scAll).some(k=>scAll[k]!==0);
  function applyAdjust(reg){
    const P=D.pred[reg]; if(!P||!P.pred) return; axis(reg);
    const g1={};
    for(const h in P.pred){const p=P.pred[h];
      if(!p.cont){g1[h]=p.g;continue;}
      let raw=p.base;
      for(const k in p.cont) raw+=mulOf(k)*p.cont[k];
      for(const k in (p.unit||{})){const s=scOf(k);
        if(s) raw+=mulOf(k)*s*(p.unit[k]||0);}
      g1[h]=raw;}   // calib 미적용 — 선택/평가 분리 실측에서 raw 가 전 지역 최선(서버와 동일 규칙)
    const F=P.futX, base=P.last.price, z=1.2816;
    for(const h0 in P.pred){const h=+h0, p=P.pred[h];
      const nb=[h-1,h,h+1].filter(x=>g1[x]!=null).map(x=>g1[x]);
      let v=nb.reduce((a,c)=>a+c,0)/nb.length;
      if(p.gb) v=Math.max(p.gb[0],Math.min(p.gb[1],v));
      const pr=base*Math.exp(v), j=P._ax.past+h, sd=p.bsd||0;
      p._gx=v;
      F.price[j]=+pr.toFixed(1);
      F.lo[j]=+(pr*Math.exp(-z*sd)).toFixed(1);
      F.hi[j]=+(pr*Math.exp(z*sd)).toFixed(1);}
  }
  function applyAdjustAll(){for(const r of D.regions) applyAdjust(r);}
  function resetAdjust(){mulAll={};scAll={};
    for(const r of D.regions){const P=D.pred[r];
      if(P&&P._f0){P.futX=JSON.parse(JSON.stringify(P._f0));
        for(const h in P.pred) delete P.pred[h]._gx;}}}

  function draw(){
    const cv=$('re_cv'); if(!cv||!D) return;
    const P=D.pred[cur]; if(!P) return;
    const ax=axis(cur);
    const H=Math.max(520,(window.innerHeight||900)-200);
    cv.style.height=H+'px';
    {const box=$('re_ind')&&$('re_ind').parentElement; if(box) box.style.height=H+'px';}
    const W=cv.clientWidth||1000; cv.width=W; cv.height=H;
    const x=cv.getContext('2d'); x.clearRect(0,0,W,H);
    const N=ax.N;
    if(!view) view=[0,N-1];
    const [v0,v1]=view, M=v1-v0+1;
    const Pd={l:8,t:18,b:20}, AXW=56, PW=Math.max(80,W-Pd.l-AXW);
    const X=i=>Pd.l+PW*(i-v0)/Math.max(1,M-1);
    x.font='10px sans-serif';
    const tf=v=>logY?Math.log10(Math.max(v,1e-9)):v;
    const seg=a=>a.slice(v0,v1+1);
    const F=P.futX||P._f0;
    const vals=[...seg(ax.hist),...(showPred?[...seg(F.price),...seg(F.lo),...seg(F.hi)]:[])].map(v=>v==null?null:tf(v));
    const f2=vals.filter(z=>z!=null);
    let lo=f2.length?Math.min(...f2):0, hi=f2.length?Math.max(...f2):1;
    if(hi===lo){hi=lo+1;} const pad=(hi-lo)*.07; lo-=pad; hi+=pad;
    const Y=v=>Pd.t+(H-Pd.t-Pd.b)*(1-(v-lo)/(hi-lo));
    x.strokeStyle='#eef1f4';
    for(let g=0;g<=4;g++){const yy=Pd.t+(H-Pd.t-Pd.b)*g/4;x.beginPath();x.moveTo(Pd.l,yy);x.lineTo(Pd.l+PW,yy);x.stroke();}
    x.fillStyle='#98a2ad';
    const yrStep=M>180?2:1;
    for(let i=v0;i<=v1;i++){const s=String(ax.TT[i]);
      if(s.slice(4)==='01'&&(+s.slice(0,4))%yrStep===0) x.fillText(s.slice(0,4),X(i)-12,H-5);}
    const past=ax.past;
    if(showPred&&past>=v0&&past<=v1){
      x.save();x.setLineDash([4,4]);x.strokeStyle='#c8ced6';
      x.beginPath();x.moveTo(X(past),Pd.t-8);x.lineTo(X(past),H-Pd.b);x.stroke();x.restore();
      x.fillStyle='#98a2ad';x.fillText('예측 →',X(past)+3,Pd.t-1);
      x.beginPath();let st=false;
      for(let j=Math.max(past,v0);j<=v1;j++){const v=F.hi[j];if(v==null)continue;
        const px=X(j),py=Y(tf(v)); st?x.lineTo(px,py):(x.moveTo(px,py),st=true);}
      for(let j=v1;j>=Math.max(past,v0);j--){const v=F.lo[j];if(v==null)continue;x.lineTo(X(j),Y(tf(v)));}
      x.closePath();x.fillStyle='rgba(31,41,55,.10)';x.fill();
    }
    x.strokeStyle='#1f2937';x.lineWidth=2;x.beginPath();let on=false;
    for(let j=v0;j<=v1;j++){const v=ax.hist[j];if(v==null){on=false;continue;}
      const px=X(j),py=Y(tf(v)); on?x.lineTo(px,py):(x.moveTo(px,py),on=true);}
    x.stroke();
    if(showPred){x.save();x.setLineDash([6,4]);x.strokeStyle='#d9534f';x.lineWidth=2;x.beginPath();on=false;
      for(let j=v0;j<=v1;j++){const v=F.price[j];if(v==null){on=false;continue;}
        const px=X(j),py=Y(tf(v)); on?x.lineTo(px,py):(x.moveTo(px,py),on=true);}
      x.stroke();x.restore();x.lineWidth=1;}
    /* 우측 축 */
    const x0=Pd.l+PW;
    x.strokeStyle='#e5e8ec';x.beginPath();x.moveTo(x0,Pd.t-8);x.lineTo(x0,H-Pd.b);x.stroke();
    x.fillStyle='#1f2937';
    for(let g=0;g<=4;g++){let vv=lo+(hi-lo)*(1-g/4);
      if(logY)vv=Math.pow(10,vv);
      const yy=Pd.t+(H-Pd.t-Pd.b)*g/4;
      x.fillText(vv>=1e4?Math.round(vv).toLocaleString():vv.toFixed(0),x0+3,yy+3);}
    x.save();x.font='bold 10px sans-serif';x.fillText(cur,x0+3,Pd.t-10);x.restore();
  }

  function setView(a,b){const N=axis(cur).N;
    a=Math.max(0,Math.round(a)); b=Math.min(N-1,Math.round(b));
    if(b-a<12){const c=(a+b)/2;a=Math.max(0,c-6);b=Math.min(N-1,c+6);}
    view=[Math.round(a),Math.round(b)]; draw();}

  function bindChart(){
    const cv=$('re_cv'); if(!cv||cv._re) return; cv._re=1;
    if(window.ResizeObserver){const ro=new ResizeObserver(()=>{if(D)draw();});ro.observe(cv);}
    cv.addEventListener('wheel',e=>{e.preventDefault();
      const r=cv.getBoundingClientRect(), fx=(e.clientX-r.left)/r.width;
      const [a,b]=view, M=b-a, c=a+M*fx, f=e.deltaY>0?1.2:1/1.2;
      setView(c-(c-a)*f, c+(b-c)*f);},{passive:false});
    cv.addEventListener('mousedown',e=>{drag={x:e.clientX,v:[...view]};});
    window.addEventListener('mousemove',e=>{if(!drag)return;
      const r=cv.getBoundingClientRect(), M=drag.v[1]-drag.v[0];
      const dx=(e.clientX-drag.x)/r.width*M, N=axis(cur).N;
      let a=drag.v[0]-dx,b=drag.v[1]-dx;
      if(a<0){b-=a;a=0;} if(b>N-1){a-=b-(N-1);b=N-1;}
      view=[Math.round(a),Math.round(b)]; draw();});
    window.addEventListener('mouseup',()=>{drag=null;});
    cv.addEventListener('dblclick',()=>{view=null;draw();});
  }

  const fmt=(v,d)=>v==null?'—':(+v).toFixed(d==null?1:d);

  function render(){
    const P=D.pred[cur]; if(!P) return;
    axis(cur);
    const btn=(on,txt,attr)=>`<button ${attr||''} style="padding:3px 9px;font-size:11.5px;border:1px solid ${on?'#1f2937':'#d7dce3'};border-radius:6px;cursor:pointer;background:${on?'#1f2937':'#fff'};color:${on?'#fff':'#444'}">${txt}</button>`;
    /* ① 지역 요약 줄 — 현재가 + 지평별 예측 % */
    const gh=h=>{const p=(P.pred||{})[h]; if(!p) return null;
      const g=p._gx!=null?p._gx:p.g; return +(Math.exp(g)*100-100).toFixed(1);};
    const adj=isAdj();
    const pv=v=>v==null?'—':`<span${adj?' style="text-decoration:underline dotted" title="조절 반영값"':''}>${adj?'✎ ':''}${v>0?'+':''}${v}%</span>`;
    $('re_sum').innerHTML=`<b style="font-size:15px">${E(cur)}</b>
      <span style="margin-left:8px">현재 중위가 <b>${P.last.price.toLocaleString()}</b> <span class="note">만원/㎡ · ${fm(P.last.t)}</span></span>${
      HZS.map(h=>` <span style="margin-left:10px">${h}M ${pv(gh(h))}</span>`).join('')}
      <span class="note" style="margin-left:10px">백테스트 MAPE ${fmt((P.bt||{}).mape,2)}% · 방향 ${fmt((P.bt||{}).hit,1)}%</span>`;
    /* ② 지역 칩 + 컨트롤 */
    $('re_tg').innerHTML=D.regions.map(r=>btn(r===cur,E(r),`data-k="${E(r)}"`)).join(' ');
    $('re_tg').querySelectorAll('[data-k]').forEach(b=>b.onclick=()=>{cur=b.dataset.k;view=null;render();});
    const N=axis(cur).N;
    const spans={'전체':N,'10년':144,'5년':84};
    $('re_ctl').innerHTML=Object.keys(spans).map(s=>btn(false,s,`data-s="${s}"`)).join(' ')
      +' '+btn(logY,'로그축','id="re_log"')+' '+btn(showPred,'예측','id="re_pred"')
      +` <span class="note">휠=확대축소 · 드래그=이동 · 더블클릭=전체 · ${fm(D.t[0])}~${fm(D.t[P.past])} 실측 ${P.past+1}개월 · 3개월 평균 계열</span>`;
    $('re_ctl').querySelectorAll('[data-s]').forEach(b=>b.onclick=()=>{
      const n=Math.min(spans[b.dataset.s],N); setView(N-n,N-1);});
    $('re_log').onclick=()=>{logY=!logY;render();};
    $('re_pred').onclick=()=>{showPred=!showPred;render();};
    /* ③ 지표 표 — 그룹(통합 r) + 개별(통설 vs 실측·지평별 r·가중치·조절) */
    const lead=D.lead[cur]||{};
    const rc=v=>{const a=Math.abs(v);
      return `<span style="color:${v>0?'#d9534f':(v<0?'#2f6fed':'#666')};opacity:${a<.2?.45:1};font-weight:${a>=.5?700:400}">${(+v).toFixed(3)}</span>`;};
    const bsty='padding:0 3px;font-size:10.5px;border:1px solid #d7dce3;border-radius:4px;cursor:pointer;background:#fff';
    const NC=4+HZS.length*2+2;
    const indRow=k=>{const l=lead[k]; if(!l) return '';
      const m=D.meta[k]||{}, mv=mulOf(k), sv=scOf(k);
      const hz=HZS.map(h=>`<td class="num">${l['lag'+h]!=null?l['lag'+h]+'M':'—'}</td><td class="num">${l['r'+h]!=null?rc(l['r'+h]):'—'}</td>`).join('');
      return `<tr title="${E((m.hint||'')+(m.src?' · '+m.src:''))}">
      <td style="padding-left:16px;white-space:nowrap">└ ${E(m.label||k)}</td>
      <td class="num" style="color:#98a2ad">${E(m.folk||'—')}</td>
      <td class="num">${l.lag}M</td><td class="num">${rc(l.corr)}</td>${hz}
      <td class="num"><b style="color:${mv!==1?'#b45309':''}">${l.w12!=null?(l.w12*mv*100).toFixed(1)+'%':'—'}</b></td>
      <td class="num" style="white-space:nowrap">
        <button data-mm="${k}" data-d="-1" style="${bsty}" title="가중치 -0.1배">−</button><b style="color:${mv!==1?'#b45309':'#333'}">${mv.toFixed(1)}</b><button data-mm="${k}" data-d="1" style="${bsty}" title="가중치 +0.1배">＋</button>
        <button data-ms="${k}" data-s="1" style="${bsty};${sv===1?'background:#d9534f;color:#fff;border-color:#d9534f':''}" title="이 지표가 1σ 오른다고 가정">▲</button><button data-ms="${k}" data-s="-1" style="${bsty};${sv===-1?'background:#2f6fed;color:#fff;border-color:#2f6fed':''}" title="이 지표가 1σ 내린다고 가정">▼</button></td></tr>`;};
    const gArr=(P.groups||[]);
    const order=D.group_order||gArr.map(g=>g.name);
    const used=new Set();
    let body='';
    order.forEach(gn=>{
      const g=gArr.find(x=>x.name===gn);
      const mem=(g?g.members:Object.keys(lead).filter(k=>(D.meta[k]||{}).group===gn))
        .filter(k=>lead[k])
        .sort((a,b)=>Math.abs(lead[b].r12||0)-Math.abs(lead[a].r12||0));
      if(!mem.length) return;
      mem.forEach(k=>used.add(k));
      body+=`<tr style="background:#f4f6f8"><td style="white-space:nowrap"><b>▣ ${E(gn)}</b> <span class="note">×${mem.length}</span></td>
        <td class="num">—</td><td class="num">${g?g.lag+'M':'—'}</td><td class="num">${g?rc(g.corr):'—'}</td>${('<td class="num">—</td>').repeat(HZS.length*2)}
        <td class="num"><b>${(mem.reduce((s,k)=>s+(lead[k].w12||0)*mulOf(k),0)*100).toFixed(1)}%</b></td><td></td></tr>`
        +mem.map(indRow).join('');
    });
    const rest=Object.keys(lead).filter(k=>!used.has(k))
      .sort((a,b)=>Math.abs(lead[b].r12||0)-Math.abs(lead[a].r12||0));
    if(rest.length)
      body+=`<tr style="background:#f4f6f8"><td colspan="${NC}"><b>▣ 기타</b></td></tr>`+rest.map(indRow).join('');
    const wSum=Object.keys(lead).reduce((s,k)=>s+(lead[k].w12||0)*mulOf(k),0);
    $('re_ind').innerHTML=`<div style="text-align:right;margin:1px 0"><button id="re_rst" style="${bsty}" title="가중치 배수·시나리오 전부 초기화(전 지역 반영)">⟲ 조절 전체 초기화</button></div>
      <table style="font-size:11px"><thead><tr><th title="마우스 올리면 해석·출처">지표</th>
      <th style="text-align:right" title="기사·통계기관이 말하는 통설 선행기간 — 실측 시차와 비교해 볼 것">통설</th>
      <th style="text-align:right" title="전 구간 상관 최대 시차 — 0M이면 동행지표(현재 확인용)">시차</th>
      <th style="text-align:right" title="그 시차에서 전년비와의 상관(진단용)">r</th>${
      HZS.map(h=>`<th style="text-align:right">${h}M</th><th style="text-align:right" title="${h}개월 누적 변화율을 시차≥${h}개월 지표로 잰 상관 — 예측에 실제 쓰는 값">${h}M r</th>`).join('')}
      <th style="text-align:right" title="|12M r| ÷ Σ|12M r| — 12개월 예측 발언 지분. 조절 배수 반영">가중치</th>
      <th style="text-align:right;white-space:nowrap" title="−/＋=가중치 배수 ±0.1 · ▲/▼=그 지표가 1σ 오름/내림 가정. 바꾸면 예측선 즉시 재계산(저장 안 됨)">가중치조절 | 지표값조절</th></tr></thead>
      <tbody>${body}</tbody></table>
      <div class="note" style="margin:5px 0">실효 Σ가중치 <b style="color:${Math.abs(wSum-1)>.001?'#b45309':'#333'}">${(wSum*100).toFixed(0)}%</b> (기본 100%) — 예측선에 즉시 반영(저장 안 됨·새로고침 시 초기화)</div>
      <div class="note" style="line-height:1.6">💡 <b>이 탭의 예측은 릿지 회귀를 쓰지 않는다</b> — 지평 h 예측 = 그 지평에 출전 가능한(시차≥h) 지표들의
      "r × 현재 표준화값"을 <b>|r| 비례 가중치</b>로 합성한 원신호(+3점 평활·역사범위 가드). 보정계수는 곱하지 않는다 —
      선택/평가 분리 실측에서 보정이 오히려 성적을 해쳤다(서울 6.87%→9.00%). 계산이 투명한 대신 비슷한 지표가 많은 그룹의 발언이
      그대로 합산된다(중복 자동 차감 없음) — 그룹 소계로 쏠림을 확인할 것. <b>통설 vs 실측 시차</b>가 크게 다르면 통설이 이 지역
      데이터에선 안 맞았다는 뜻. 기사 프레임: 전세→매매(1~2M) · 인허가→입주(6~18M) · 낙찰가율 80%↑ 안정/70%↓ 침체.</div>`;
    $('re_ind').querySelectorAll('[data-mm]').forEach(b=>b.onclick=e=>{e.stopPropagation();
      const k=b.dataset.mm, d=+b.dataset.d;
      mulAll[k]=Math.max(0,Math.min(3,+((mulOf(k)+d*0.1).toFixed(1))));
      applyAdjustAll(); render();});
    $('re_ind').querySelectorAll('[data-ms]').forEach(b=>b.onclick=e=>{e.stopPropagation();
      const k=b.dataset.ms, s=+b.dataset.s;
      scAll[k]=(scOf(k)===s)?0:s;
      applyAdjustAll(); render();});
    {const rb=$('re_rst'); if(rb) rb.onclick=()=>{resetAdjust();render();};}
    /* ④ 백테스트 표 */
    const bh=(P.bt||{}).by_h||{};
    const avgH=h=>{const sk=[],hi=[];
      for(const r of D.regions){const b2=((D.pred[r]||{}).bt||{}).by_h?.[h];
        if(!b2) continue;
        if(b2.skill!=null) sk.push(b2.skill);
        if(b2.hit!=null) hi.push(b2.hit);}
      return {sk:sk.length?sk.reduce((a,c)=>a+c,0)/sk.length:null,
              hi:hi.length?hi.reduce((a,c)=>a+c,0)/hi.length:null};};
    $('re_bt').innerHTML=`<div class="note" style="margin-bottom:3px">MAPE·단순예측 오차·보정계수·방향적중 = <b>${E(cur)}</b> 기준 · '전지역' 두 열은 ${D.regions.length}개 시도 평균</div>
      <table><thead><tr><th>지평</th><th style="text-align:right">평균 오차(MAPE)</th>
      <th style="text-align:right" title="'변동 없음' 예측의 오차 — 이보다 작아야 의미">단순예측 오차</th>
      <th style="text-align:right" title="예측 변화율 대비 실제 실현 비율(참고) — 이 탭은 곱하지 않는다(선택/평가 분리 실측에서 보정이 성적을 해침)">보정계수(참고)</th>
      <th style="text-align:right">${E(cur)} 방향적중</th>
      <th style="text-align:right" title="1 − MAPE/단순예측오차">${E(cur)} 스킬</th>
      <th style="text-align:right">전지역 방향</th><th style="text-align:right">전지역 스킬</th></tr></thead><tbody>${
      HZS.filter(h=>bh[h]).map(h=>{const b=bh[h],a=avgH(h);
        return `<tr><td>${h}개월 뒤</td><td class="num">${fmt(b.mape,2)}%</td>
        <td class="num">${fmt(b.naive,2)}%</td><td class="num">${fmt(b.calib,2)}</td>
        <td class="num"><b>${fmt(b.hit,1)}%</b></td>
        <td class="num"><b>${b.skill!=null?(+b.skill).toFixed(2):'—'}</b></td>
        <td class="num">${a.hi!=null?a.hi.toFixed(1)+'%':'—'}</td>
        <td class="num">${a.sk!=null?a.sk.toFixed(2):'—'}</td></tr>`;}).join('')}</tbody></table>
      <div class="note" style="margin-top:4px">워크포워드 백테스트 ${(P.bt||{}).origins||''}시점 — 그 시점까지 자료만으로 시차 탐색부터 다시 수행. 성적은 있는 그대로 표시.
      같은 지역을 릿지 회귀로 푸는 부동산 탭 예측(참고: 서울 MAPE ~2.7%)보다 오차가 큰 것이 정상이다 — 이 탭은 계산 투명성·수동 조절을 우선한 모델이다. 참고용이며 투자권유가 아님.</div>`;
    bindChart(); draw();
  }

  function init(){
    if(_init) return; _init=true;
    fetch('/api/db/repred',{cache:'reload'}).then(r=>r.ok?r.json():null).then(d=>{
      if(!d||!d.pred||!Object.keys(d.pred).length){
        $('re_sum').innerHTML='<div class="note">수집 대기 중 — repred.py 첫 실행이 끝나면 표시됩니다(매일 08:10 자동 갱신).</div>'; return;}
      D=d; if(!D.pred[cur]) cur=D.regions[0];
      {const e=$('re_asof'); if(e) e.textContent=`${d.src||''} · 수집 ${d.asof||''}`;}
      try{render();}catch(err){
        $('re_sum').innerHTML=`<div style="color:#b91c1c;font-weight:700">렌더 오류: ${E(err&&err.message||err)}</div>`;
        throw err;}
    }).catch(()=>{$('re_sum').innerHTML='<div class="note">불러오기 실패 — 새로고침 해주세요.</div>';});
  }
  const tb=document.querySelector('.tab[data-pane="p_re"]');
  if(tb) tb.addEventListener('click',()=>{init(); setTimeout(draw,50);});
  window.addEventListener('resize',()=>{if(D)draw();});
})();
