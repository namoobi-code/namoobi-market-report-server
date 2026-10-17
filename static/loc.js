/* loc.js — 📍 입지점수 탭 (2026-10-17 신설) · 데이터 /api/db/locscore (scripts/locscore.py · 월 1회)
   고준석(연세대) 입지 5요소를 서울 25구·성남 3구·용인 수지의 K-apt 등록 단지(~3,900)에 점수화.
     교육 = 600m 내 입시·외국어 학원 수(백분위) · 편의 = 최근접 종합병원 거리 · 자연 = 대규모 공원 거리
     교통 = 600m 내 환승역/역 · 규모 = 세대수 1,500~2,500 만점
   총점은 여기서 가중치 슬라이더로 즉시 재계산(서버는 요소 점수만 준다). 가격은 실거래 12개월 ㎡당가 → 84㎡ 환산.
   '점수 대비 싼 단지'를 찾는 게 목적이라 산점도(총점 vs 84㎡가)와 가성비 열을 둔다. */
(function(){
'use strict';
const $=id=>document.getElementById(id);
const E=s=>String(s??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
let D=null, ch=null;
let S={reg:'전체', q:'', minhh:0, sort:'tot', dir:-1, n:80, w:{edu:20,hosp:20,park:20,tr:20,size:20}, pick:null};
const F=['edu','hosp','park','tr','size'];
const FN={edu:'교육',hosp:'편의',park:'자연',tr:'교통',size:'규모'};
const FC={edu:'#7c3aed',hosp:'#0e9aa7',park:'#27ae60',tr:'#2f6fed',size:'#e08e3c'};

function tot(a){ let s=0,w=0; F.forEach(f=>{const v=a['s_'+f]; if(v!=null&&S.w[f]>0){s+=v*S.w[f]; w+=S.w[f];}}); return w?s/w:null; }
function rows(){
  if(!D) return [];
  const out=[];
  for(const a of D.apts){
    if(S.reg!=='전체'&&!(a.sgg===S.reg||(S.reg==='서울'&&a.sgg.startsWith('서울'))||(S.reg==='성남'&&a.sgg.startsWith('성남')))) continue;
    if(S.minhh&&(a.hh||0)<S.minhh) continue;
    if(S.q&&!((a.nm||'')+(a.umd||'')+(a.sgg||'')).toLowerCase().includes(S.q)) continue;
    const t=tot(a); if(t==null) continue;
    out.push(Object.assign({tot:t, vfm:a.p84e?t/a.p84e:null}, a));
  }
  const k=S.sort;
  out.sort((a,b)=>{const x=a[k],y=b[k]; if(x==null&&y==null) return 0; if(x==null) return 1; if(y==null) return -1; return typeof x==='string'?S.dir*x.localeCompare(y,'ko'):S.dir*(x-y);});
  return out;
}
const bar=(v,c)=>v==null?'—':`<span style="display:inline-block;width:${Math.round(v*0.5)}px;height:8px;background:${c};border-radius:2px;vertical-align:middle"></span> <span style="font-size:11px">${Math.round(v)}</span>`;
const km=d=>d==null||d>=99?'—':d<1?Math.round(d*1000)+'m':d.toFixed(1)+'km';
function draw(){
  const R=rows(); const show=R.slice(0,S.n);
  // 요약
  const byG={}; R.forEach(a=>{(byG[a.sgg]=byG[a.sgg]||[]).push(a.tot);});
  const top=Object.entries(byG).map(([g,v])=>[g,v.reduce((x,y)=>x+y,0)/v.length,v.length]).sort((a,b)=>b[1]-a[1]).slice(0,6);
  $('lc_sum').innerHTML=`<b>${S.reg}</b> 단지 <b>${R.length}</b>곳 · 가중치 ${F.map(f=>`<span style="color:${FC[f]}">${FN[f]} ${S.w[f]}</span>`).join(' · ')}`
    +(top.length>1?` · 구별 평균 상위: ${top.map(t=>`${E(t[0].replace('서울 ','').replace('성남 ',''))} <b>${t[1].toFixed(0)}</b>`).join(' · ')}`:'')
    +` · 행 클릭=상세 · 열 머리글 클릭=정렬`;
  // 산점도
  const ctx=$('lc_sc'); if(ctx){ if(ch) ch.destroy();
    const pts=R.filter(a=>a.p84e).map(a=>({x:a.tot,y:a.p84e,a}));
    ch=new Chart(ctx,{type:'scatter',data:{datasets:[{data:pts,pointRadius:pts.length>1500?2:3,backgroundColor:pts.map(p=>p.a.k===S.pick?'#d9534f':(p.a.sgg.startsWith('성남')||p.a.sgg.startsWith('용인')?'rgba(224,142,60,.55)':'rgba(47,111,237,.35)'))}]},
      options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false},tooltip:{callbacks:{label:c=>{const a=c.raw.a;return ` ${a.nm} (${a.sgg} ${a.umd||''}) 총점 ${a.tot.toFixed(0)} · 84㎡ ${a.p84e}억 · ${a.hh}세대`;}}}},
        scales:{x:{title:{display:true,text:'입지 총점',font:{size:10}},min:0,max:100,ticks:{font:{size:10}}},y:{title:{display:true,text:'84㎡ 환산가(억, 최근 12개월 ㎡당가)',font:{size:10}},ticks:{font:{size:10}}}},
        onClick:(e,els)=>{ if(!els.length) return; S.pick=pts[els[0].index].a.k; draw(); const tr=document.querySelector(`#lc_tbl tr[data-k="${S.pick}"]`); tr&&tr.scrollIntoView({block:'center'}); }}});
  }
  // 표
  const H=[['tot','총점'],['nm','단지'],['sgg','지역'],['hh','세대'],['use','준공'],['s_edu','교육'],['s_hosp','편의'],['s_park','자연'],['s_tr','교통'],['s_size','규모'],['p84e','84㎡가(억)'],['ppsm','㎡당(만원)'],['vfm','가성비']];
  $('lc_tbl').innerHTML=`<table style="width:100%;border-collapse:collapse;font-size:12px"><thead><tr style="background:#f7f8fa">${H.map(([k,l])=>`<th data-k="${k}" style="padding:5px 7px;text-align:left;border-bottom:1px solid #e5e8ec;white-space:nowrap;cursor:pointer">${l}${S.sort===k?(S.dir<0?' ▼':' ▲'):''}</th>`).join('')}</tr></thead><tbody>${
    show.map((a,i)=>{
      const st=(a.st||[]).map(s=>`${E(s.nm)}${s.ln>=2?'<b style="color:#2f6fed">(환승)</b>':''} ${Math.round(s.d*1000)}m`).join(', ');
      const main=`<tr data-k="${E(a.k)}" style="border-bottom:1px solid #f2f4f7;cursor:pointer;${a.k===S.pick?'background:#fff7ed':''}">
        <td style="padding:4px 7px;white-space:nowrap"><b style="font-size:13px">${a.tot.toFixed(0)}</b> <span class="note">#${i+1}</span></td>
        <td style="padding:4px 7px"><b>${E(a.nm)}</b> <a href="https://map.naver.com/p/search/${encodeURIComponent((a.sgg||'')+' '+(a.nm||''))}" target="_blank" rel="noopener" title="네이버지도" onclick="event.stopPropagation()">📍</a>${a.typ&&a.typ!=='아파트'?` <span class="note">${E(a.typ)}</span>`:''}</td>
        <td style="padding:4px 7px;white-space:nowrap">${E(a.sgg)} ${E(a.umd||'')}</td>
        <td style="padding:4px 7px;text-align:right">${a.hh?a.hh.toLocaleString():'—'}</td>
        <td style="padding:4px 7px">${a.use?a.use.slice(0,4):'—'}</td>
        <td style="padding:4px 7px;white-space:nowrap" title="600m 내 입시·외국어 학원 ${a.edu_n}개">${bar(a.s_edu,FC.edu)} <span class="note">${a.edu_n}</span></td>
        <td style="padding:4px 7px;white-space:nowrap" title="${E(a.hosp||'')}">${bar(a.s_hosp,FC.hosp)} <span class="note">${km(a.hosp_d)}</span></td>
        <td style="padding:4px 7px;white-space:nowrap" title="${E(a.park||'')}${a.park_s?' · 근린공원 300m 내':''}">${bar(a.s_park,FC.park)} <span class="note">${km(a.park_d)}</span></td>
        <td style="padding:4px 7px;white-space:nowrap" title="${st}">${bar(a.s_tr,FC.tr)} <span class="note">${a.st&&a.st.length?E(a.st[0].nm)+(a.st[0].ln>=2?'⇄':''):'—'}</span></td>
        <td style="padding:4px 7px;white-space:nowrap">${bar(a.s_size,FC.size)}</td>
        <td style="padding:4px 7px;text-align:right;font-weight:700">${a.p84e!=null?a.p84e.toFixed(1):'—'}${a.p84?`<br><span class="note" title="80~90㎡ 실거래 평균 (${a.n84}건)">실 ${a.p84.toFixed(1)}</span>`:''}</td>
        <td style="padding:4px 7px;text-align:right">${a.ppsm!=null?Math.round(a.ppsm*10000/10000*10000).toLocaleString():'—'}${a.ntr?`<br><span class="note">${a.ntr}건</span>`:''}</td>
        <td style="padding:4px 7px;text-align:right" title="총점 ÷ 84㎡ 환산가 — 높을수록 점수 대비 싸다">${a.vfm!=null?a.vfm.toFixed(1):'—'}</td></tr>`;
      if(a.k!==S.pick) return main;
      return main+`<tr><td colspan="13" style="background:#f8fafc;padding:8px 14px;font-size:12px;line-height:1.7">
        <b>${E(a.nm)}</b> · ${E(a.sgg)} ${E(a.umd||'')} · ${a.hh?a.hh.toLocaleString()+'세대':''} ${a.dg?a.dg+'개동':''} · 준공 ${a.use?a.use.slice(0,4)+'.'+a.use.slice(4):'—'}${a.pkr?` · 주차 ${a.pkr}대/세대`:''}<br>
        🚇 <b>교통 ${a.s_tr}</b> — ${st||'1km 내 역 없음'}<br>
        📚 <b>교육 ${a.s_edu}</b> — 600m 내 입시·교과·외국어 학원 <b>${a.edu_n}</b>개 (전체 단지 백분위)<br>
        🏥 <b>편의 ${a.s_hosp}</b> — 최근접 종합병원 ${E(a.hosp||'—')} ${km(a.hosp_d)}<br>
        🌳 <b>자연 ${a.s_park}</b> — 대규모 공원 ${E(a.park||'—')} ${km(a.park_d)}${a.park_s?' · 근린공원 300m 내 있음(+10)':''}<br>
        🏢 <b>규모 ${a.s_size}</b> — ${a.hh?a.hh.toLocaleString():'—'}세대 (1,500~2,500 만점)<br>
        💰 ${a.ppsm?`㎡당 ${Math.round(a.ppsm*10000).toLocaleString()}만원 (최근 12개월 ${a.ntr}건) → 84㎡ 환산 <b>${a.p84e}억</b>${a.p84?` · 80~90㎡ 실거래 평균 ${a.p84}억(${a.n84}건)`:''}`:'최근 12개월 실거래 매칭 없음'}
      </td></tr>`;
    }).join('')}</tbody></table>${R.length>S.n?`<div style="text-align:center;margin:8px 0"><button id="lc_more" style="padding:5px 16px;font-size:12px;border:1px solid #d7dce3;border-radius:6px;cursor:pointer;background:#fff">더 보기 (${S.n}/${R.length})</button></div>`:''}`;
  $('lc_tbl').querySelectorAll('th[data-k]').forEach(th=>th.onclick=()=>{const k=th.dataset.k; if(S.sort===k) S.dir=-S.dir; else {S.sort=k; S.dir=(k==='nm'||k==='sgg'||k==='use')?1:-1;} draw();});
  $('lc_tbl').querySelectorAll('tr[data-k]').forEach(tr=>tr.onclick=()=>{S.pick=S.pick===tr.dataset.k?null:tr.dataset.k; draw();});
  const mb=$('lc_more'); if(mb) mb.onclick=()=>{S.n+=80; draw();};
}
function controls(){
  const regs=['전체','서울','성남'].concat(D.regions);
  $('lc_reg').innerHTML=regs.map(r=>`<button data-v="${E(r)}" class="${r===S.reg?'on':''}">${E(r.replace('서울 ','').replace('성남 ','성남·').replace('용인 ','용인·'))}</button>`).join('');
  $('lc_reg').querySelectorAll('button').forEach(b=>b.onclick=()=>{S.reg=b.dataset.v; S.n=80; $('lc_reg').querySelectorAll('button').forEach(x=>x.classList.toggle('on',x===b)); draw();});
  $('lc_q').oninput=e=>{S.q=e.target.value.trim().toLowerCase(); S.n=80; draw();};
  $('lc_minhh').onchange=e=>{S.minhh=+e.target.value||0; draw();};
  F.forEach(f=>{const el=$('lc_w_'+f); el.value=S.w[f]; el.oninput=()=>{S.w[f]=+el.value; $('lc_wv_'+f).textContent=el.value; draw();}; $('lc_wv_'+f).textContent=S.w[f];});
  $('lc_wpre').querySelectorAll('button').forEach(b=>b.onclick=()=>{const w=JSON.parse(b.dataset.w); F.forEach(f=>{S.w[f]=w[f]; $('lc_w_'+f).value=w[f]; $('lc_wv_'+f).textContent=w[f];}); draw();});
}
window.renderLoc=async function(){
  if(D){ setTimeout(()=>ch&&ch.resize(),60); return; }
  try{
    const r=await fetch('/api/db/locscore'); if(!r.ok) throw new Error('HTTP '+r.status);
    D=await r.json(); if(!D.apts) throw new Error('데이터 없음');
    $('lc_asof').textContent=`${D.src} · 수집 ${D.asof} · 단지 ${D.apts.length} · POI 역 ${D.poi_n.st}·학원 ${D.poi_n.hk}·종합병원 ${D.poi_n.hp}`;
    controls(); draw();
  }catch(e){ $('lc_sum').textContent='입지점수 데이터가 아직 없습니다 — 수집 완료 후 표시됩니다. ('+e.message+')'; }
};
})();
