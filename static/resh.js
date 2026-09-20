/* resh.js — 🏘 부동산시황 탭 (2026-09-20 신설)
   데이터: /api/db/rerank (scripts/rerank.py · 매일 07:50 cron) — 한국부동산원 R-ONE
           (월) 매매가격지수_아파트, 전국 236개 지역(시도·권역·시군구 혼재) 2003.11~
   구성: ① 기간·개수·범위를 고르면 그 기간 상승률 순위(가로 막대 + 표)
         ② 순위표의 지역을 누르면 아래에 지수 추이 선(여러 개 겹치기)
   설계 의도: 동아일보 '수도권 상승률 TOP10' 같은 그래픽을 아무 기간·아무 개수로
             바로 만들어 본다. 신문은 한 장이지만 여기선 기간을 옮겨가며 누가 먼저
             올랐고 누가 뒤따랐는지가 보인다.
   순위 대상은 **말단 지역(leaf)** 만 — '성남시'와 '분당구'를 같이 세우면 중복이라
   위쪽 집계(시·권역)는 빼고, 필요하면 '범위' 에서 시도 단위로 따로 본다. */
(function(){
'use strict';
let D=null, chBar=null, chLine=null;
let S={from:'202506', to:null, n:10, order:'desc', scope:'leaf', sido:'', picked:[]};
const $=id=>document.getElementById(id);
const fm=t=>t?`${String(t).slice(0,4)}.${String(t).slice(4)}`:'—';
const E=s=>String(s??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
const nm=r=>r.sido===r.short||!r.sido?r.short:r.sido+' '+r.short;
const PAL=['#d9534f','#2f6fed','#27ae60','#e08e3c','#7c3aed','#0e9aa7','#c2185b','#5d4037','#9e9d24','#455a64',
           '#00838f','#e91e63','#3f51b5','#ff9800','#8bc34a','#1976d2','#795548','#43a047','#ad1457','#283593'];

/* 시도명은 R-ONE 표기 그대로(서울·경기·전남광주 …). 화면 필터 버튼 순서 */
const isAgg=fn=>fn==='전국'||/^(수도권|지방권|\d+대광역시|\d+개도)$/.test(fn);
const SIDO_ORDER=['서울','경기','인천','부산','대구','대전','울산','세종','전남광주','강원','충북','충남','전북','경북','경남','제주'];

function rows(){
  if(!D) return [];
  const T=D.t, i0=T.indexOf(S.from), i1=T.indexOf(S.to);
  if(i0<0||i1<0||i1<=i0) return [];
  const out=[];
  for(const [fn,r] of Object.entries(D.regions)){
    if(!fn||isAgg(fn)) continue;                          // 빈 이름·전국·권역(수도권·4대광역시·8개도…) 제외
    if(S.scope==='leaf'&&(!r.leaf||r.depth<2)) continue;  // 시군구 말단만 (자식 없는 시도(세종)는 시도 범위에서)
    if(S.scope==='sido'&&r.depth!==1) continue;
    if(S.sido&&r.sido!==S.sido) continue;
    const a=D.idx[fn]||[], v0=a[i0], v1=a[i1];
    if(v0==null||v1==null||!v0) continue;
    out.push({fn, short:r.short, sido:r.sido, path:fn.split('>').slice(1).join(' › '),
              chg:(v1/v0-1)*100, v0, v1});
  }
  out.sort((a,b)=>S.order==='desc'?b.chg-a.chg:a.chg-b.chg);
  return out;
}

function bar(){
  const R=rows().slice(0,S.n);
  const ctx=$('rs_bar'); if(!ctx) return;
  ctx.parentElement.style.height=Math.max(220, 26*R.length+60)+'px';
  if(chBar) chBar.destroy();
  chBar=new Chart(ctx,{type:'bar',data:{labels:R.map(nm),
    datasets:[{data:R.map(r=>+r.chg.toFixed(2)),
      backgroundColor:R.map(r=>r.chg>=0?'#e08e3c':'#2f6fed'),borderWidth:0,barThickness:16}]},
    options:{indexAxis:'y',responsive:true,maintainAspectRatio:false,
      plugins:{legend:{display:false},
        tooltip:{callbacks:{label:c=>{const r=R[c.dataIndex];return ` ${r.chg.toFixed(2)}% (${r.v0.toFixed(1)} → ${r.v1.toFixed(1)})`;}}},
        datalabels:undefined},
      scales:{x:{ticks:{font:{size:10},callback:v=>v+'%'},grid:{color:'#eef1f4'}},
              y:{ticks:{font:{size:11}},grid:{display:false}}},
      onClick:(e,els)=>{ if(!els.length) return; const r=R[els[0].index]; toggle(r.fn); }}});
  // 막대 끝 숫자 — Chart.js 기본엔 없어 표에서 보게 두고, 상단 요약만 적는다
  const T=D.t;
  $('rs_sum').innerHTML=R.length
    ? `<b>${fm(S.from)} → ${fm(S.to)}</b> · ${S.scope==='sido'?'시도':'시군구'} ${S.sido?E(S.sido)+' ':''}`
      +`${S.order==='desc'?'상승률 상위':'하락률 상위'} <b>${R.length}</b>곳 (대상 ${rows().length}곳) · `
      +`1위 <b style="color:${R[0].chg>=0?'#c2410c':'#1d4ed8'}">${E(nm(R[0]))} ${R[0].chg>=0?'+':''}${R[0].chg.toFixed(2)}%</b>`
      +` · 막대를 누르면 아래에 추이가 겹쳐집니다`
    : '이 기간에는 계산할 수 있는 지역이 없습니다 — 기간을 넓혀 보세요.';
}

function table(){
  const R=rows().slice(0,S.n);
  $('rs_tbl').innerHTML=`<table style="width:100%;border-collapse:collapse;font-size:12.5px">
    <thead><tr style="background:#f7f8fa">${['순위','지역','경로','상승률',fm(S.from),fm(S.to)].map(h=>`<th style="padding:5px 8px;text-align:left;border-bottom:1px solid #e5e8ec;white-space:nowrap">${h}</th>`).join('')}</tr></thead>
    <tbody>${R.map((r,i)=>`<tr data-fn="${E(r.fn)}" style="border-bottom:1px solid #f2f4f7;cursor:pointer;${S.picked.includes(r.fn)?'background:#fff7ed':''}">
      <td style="padding:4px 8px;color:#8a93a0">${i+1}</td>
      <td style="padding:4px 8px;white-space:nowrap"><b>${E(nm(r))}</b></td>
      <td style="padding:4px 8px;color:#8a93a0;font-size:11.5px">${E(r.path)}</td>
      <td style="padding:4px 8px;white-space:nowrap"><b style="color:${r.chg>=0?'#c2410c':'#1d4ed8'}">${r.chg>=0?'+':''}${r.chg.toFixed(2)}%</b></td>
      <td style="padding:4px 8px;color:#5b6672">${r.v0.toFixed(2)}</td>
      <td style="padding:4px 8px;color:#5b6672">${r.v1.toFixed(2)}</td></tr>`).join('')}</tbody></table>`;
  $('rs_tbl').querySelectorAll('tr[data-fn]').forEach(tr=>tr.onclick=()=>toggle(tr.dataset.fn));
}

function toggle(fn){
  S.picked = S.picked.includes(fn) ? S.picked.filter(x=>x!==fn) : S.picked.concat([fn]).slice(-8);
  table(); lines();
}

function lines(){
  const ctx=$('rs_line'); if(!ctx) return;
  const T=D.t, i0=Math.max(0,T.indexOf(S.from)-24), i1=T.indexOf(S.to);   // 기간 앞 2년부터 보여 맥락을 준다
  const L=T.slice(i0,i1+1);
  if(chLine) chLine.destroy();
  if(!S.picked.length){ $('rs_line_n').textContent='순위표나 막대에서 지역을 누르면 여기에 지수 추이가 겹쳐집니다(최대 8개).'; return; }
  const ds=S.picked.map((fn,k)=>{const r=D.regions[fn]||{};
    return {label:r.short?nm(r):fn, data:(D.idx[fn]||[]).slice(i0,i1+1),
            borderColor:PAL[k%PAL.length],borderWidth:1.8,pointRadius:0,tension:.15,spanGaps:true};});
  chLine=new Chart(ctx,{type:'line',data:{labels:L.map(fm),datasets:ds},
    options:{responsive:true,maintainAspectRatio:false,interaction:{mode:'index',intersect:false},
      plugins:{legend:{labels:{boxWidth:12,font:{size:11}}},
        tooltip:{callbacks:{label:c=>` ${c.dataset.label} ${c.raw==null?'—':c.raw.toFixed(2)}`}}},
      scales:{x:{ticks:{font:{size:10},maxTicksLimit:14}},y:{ticks:{font:{size:10}},title:{display:true,text:'매매가격지수',font:{size:10}}}}}});
  const s0=T.indexOf(S.from);
  $('rs_line_n').innerHTML=`선택 ${S.picked.length}곳 · 표시 ${fm(L[0])}~${fm(L[L.length-1])} (순위 기간 앞 2년을 더 보여줍니다) · `
    +S.picked.map((fn,k)=>{const a=D.idx[fn]||[]; const v0=a[s0],v1=a[i1];
      return `<span style="color:${PAL[k%PAL.length]}">●</span>${E((D.regions[fn]||{}).short||fn)} ${v0&&v1?((v1/v0-1)*100).toFixed(2)+'%':'—'}`;}).join(' · ')
    +` <button id="rs_clear" style="margin-left:6px;font-size:11px;padding:1px 6px">비우기</button>`;
  $('rs_clear').onclick=()=>{S.picked=[];table();lines();};
}

function controls(){
  const T=D.t;
  const opt=(sel,def)=>{sel.innerHTML=T.slice().reverse().map(t=>`<option value="${t}"${t===def?' selected':''}>${fm(t)}</option>`).join('');};
  opt($('rs_from'),S.from); opt($('rs_to'),S.to);
  $('rs_from').onchange=e=>{S.from=e.target.value; draw();};
  $('rs_to').onchange=e=>{S.to=e.target.value; draw();};
  $('rs_n').value=S.n;
  $('rs_n').onchange=e=>{S.n=Math.max(1,Math.min(236,+e.target.value||10)); e.target.value=S.n; draw();};
  $('rs_npre').querySelectorAll('button').forEach(b=>b.onclick=()=>{S.n=+b.dataset.n;$('rs_n').value=S.n;draw();});
  const seg=(id,cur,set)=>{$(id).querySelectorAll('button').forEach(b=>{b.classList.toggle('on',b.dataset.v===cur);
    b.onclick=()=>{set(b.dataset.v);draw();};});};
  seg('rs_order',S.order,v=>S.order=v);
  seg('rs_scope',S.scope,v=>S.scope=v);
  // 시도 필터 — 데이터에 있는 것만
  const sidos=[...new Set(Object.values(D.regions).map(r=>r.sido))].filter(s=>s&&!isAgg(s));
  sidos.sort((a,b)=>(SIDO_ORDER.indexOf(a)+99)%99-(SIDO_ORDER.indexOf(b)+99)%99);
  $('rs_sido').innerHTML=`<button data-v="" class="${S.sido?'':'on'}">전국</button>`+sidos.map(s=>`<button data-v="${E(s)}" class="${S.sido===s?'on':''}">${E(s)}</button>`).join('');
  seg('rs_sido',S.sido,v=>S.sido=v);
  // 기간 프리셋
  $('rs_span').querySelectorAll('button').forEach(b=>b.onclick=()=>{const m=+b.dataset.m; const i1=T.indexOf(S.to); S.from=T[Math.max(0,i1-m)]; $('rs_from').value=S.from; draw();});
}

function draw(){ controls(); bar(); table(); lines(); }

window.renderResh=async function(){
  if(D){ setTimeout(()=>{[chBar,chLine].forEach(c=>c&&c.resize());},60); return; }
  try{
    const r=await fetch('/api/db/rerank'); if(!r.ok) throw new Error('HTTP '+r.status);
    D=await r.json();
    if(!D.t||!D.t.length) throw new Error('데이터 없음');
    S.to=D.t[D.t.length-1];
    if(!D.t.includes(S.from)) S.from=D.t[Math.max(0,D.t.length-15)];
    $('rs_asof').textContent=`${D.src} · 수집 ${D.asof} · 지역 ${Object.keys(D.regions).length}`;
    draw();
  }catch(e){ $('rs_sum').textContent='데이터를 불러오지 못했습니다 — 다음 수집(매일 07:50) 후 다시 열어 주세요. ('+e.message+')'; }
};
})();
