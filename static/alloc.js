/* alloc.js — 💼 자산배분(포트폴리오 제안) 탭 (2026-10-18 신설 · 사용자 요청)
   데이터: /api/db/alloc (scripts/fetch_alloc.py · 매일 07:55) + /api/db/alloc_hist
   총자산은 입력(기본 10억, localStorage 보존) → 비중×총자산 = 금액. 부동산은 비율 권고만.
   구성: ① 한 줄 요약·신뢰도 ② 자산군 카드(비중·금액·실행수단·근거) ③ 신호 대시보드 ④ 주식 바스켓(KR/US, 종목별 금액) ⑤ 부동산 비율 ⑥ 비중 이력 차트 */
(function(){
'use strict';
const $=id=>document.getElementById(id);
const E=s=>String(s??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
let D=null, H=null, ch=null;
const LS='namoobi_alloc_total';
const COL={kr_eq:'#0f766e',us_eq:'#1d4ed8',bond_s:'#64748b',bond_l:'#334155',gold:'#ca8a04',cash:'#94a3b8',crypto:'#7c3aed'};
function total(){ const v=parseFloat(($('al_total')||{}).value); return (v>0?v:10)*1e8; }
function won(v){ if(v==null) return '—'; const a=Math.abs(v); if(a>=1e8) return (v/1e8).toFixed(a>=1e9?1:2)+'억'; if(a>=1e4) return Math.round(v/1e4).toLocaleString()+'만'; return Math.round(v).toLocaleString()+'원'; }
const pf=v=>v==null?'—':(v>0?'+':'')+Number(v).toFixed(1)+'%';
const pc=v=>v==null?'#64748b':(v>0?'#dc2626':v<0?'#2563eb':'#64748b');

function render(){
  if(!D) return;
  const T=total(); try{ localStorage.setItem(LS,String(T/1e8)); }catch(e){}
  $('al_asof').textContent='기준 '+D.as_of+' · 매일 07:55 갱신 · 신뢰도 '+D.confidence;
  $('al_sum').innerHTML=`<b>${E(D.summary)}</b><div class="note" style="margin-top:4px">${E(D.disclaimer)}</div>`;
  // ② 자산군 카드
  const W=D.weights, keys=Object.keys(W);
  $('al_cards').innerHTML=keys.map(k=>{const w=W[k], d=(D.diff7||{})[k]||0, base=D.base[k];
    return `<div style="flex:1 1 260px;border:1px solid #e2e8f0;border-top:4px solid ${COL[k]};border-radius:10px;background:#fff;padding:10px 12px">
      <div style="display:flex;justify-content:space-between;align-items:baseline"><b style="font-size:13px">${E(D.label[k])}</b>
        <span style="font-size:20px;font-weight:800;color:${COL[k]}">${w.toFixed(0)}%</span></div>
      <div style="font-size:15px;font-weight:700;margin:2px 0">${won(T*w/100)}</div>
      <div class="note">기본 ${base}% · 7일 전 대비 <span style="color:${d>0?'#dc2626':d<0?'#2563eb':'#64748b'}">${d>0?'+':''}${d}p</span> · ${E(D.vehicle[k])}</div>
      <div style="font-size:11.5px;color:#334155;margin-top:6px;line-height:1.55">${(D.why[k]||[]).map(x=>'• '+E(x)).join('<br>')||'<span class="note">• 조정 없음(기본 비중)</span>'}</div></div>`;}).join('');
  // ③ 신호 대시보드
  $('al_sig').innerHTML=`<table style="border-collapse:collapse;font-size:12px;background:#fff;width:100%"><thead><tr style="background:#f8fafc">
    ${['신호','현재값','출처 탭','읽는 법'].map(h=>`<th style="border:1px solid #e2e8f0;padding:4px 7px">${h}</th>`).join('')}</tr></thead><tbody>
    ${(D.signals||[]).map(s=>`<tr><td style="border:1px solid #e2e8f0;padding:3px 7px;font-weight:700;white-space:nowrap">${E(s.k)}</td>
      <td style="border:1px solid #e2e8f0;padding:3px 7px">${E(s.v)}</td><td style="border:1px solid #e2e8f0;padding:3px 7px;white-space:nowrap;color:#64748b">${E(s.src)}</td>
      <td style="border:1px solid #e2e8f0;padding:3px 7px;color:#475569;font-size:11.5px">${E(s.detail||'')}</td></tr>`).join('')}</tbody></table>`;
  // ④ 바스켓
  const bk=(mkt,sleeve)=>{ const B=D.baskets[mkt], amt=T*W[sleeve]/100; const isus=mkt==='us';
    return Object.entries(B.weights).map(([name,wp])=>{ const lst=B.lists[name]||[]; const a=amt*wp/100, per=lst.length?a/lst.length:0;
      return `<div style="flex:1 1 420px;border:1px solid #e2e8f0;border-radius:8px;background:#fff;padding:8px 10px">
        <div style="display:flex;justify-content:space-between"><b style="font-size:12.5px">${E(name)}</b><span style="font-size:12px"><b>${wp}%</b> · ${won(a)}${lst.length?` · 종목당 ${won(per)}`:''}</span></div>
        ${lst.length?`<table style="border-collapse:collapse;font-size:11.5px;width:100%;margin-top:5px"><thead><tr style="background:#f8fafc">${['종목','가격','배당','ICR','영현/영익','1M','상승여력','금액'].map(h=>`<th style="border:1px solid #e2e8f0;padding:2px 5px">${h}</th>`).join('')}</tr></thead>
        <tbody>${lst.map(x=>`<tr><td style="border:1px solid #e2e8f0;padding:2px 5px;white-space:nowrap"><a href="${isus?`https://finance.yahoo.com/quote/${x.c}`:`https://finance.naver.com/item/main.naver?code=${x.c}`}" target="_blank">${E(x.n||x.c)}</a> <span class="note">${E(x.c)}</span></td>
          <td style="border:1px solid #e2e8f0;padding:2px 5px;text-align:right">${x.px!=null?(isus?'$'+Number(x.px).toFixed(2):Math.round(x.px).toLocaleString()):'—'}</td>
          <td style="border:1px solid #e2e8f0;padding:2px 5px;text-align:right">${x.divy!=null?Number(x.divy).toFixed(1)+'%':'—'}</td>
          <td style="border:1px solid #e2e8f0;padding:2px 5px;text-align:right;color:${x.icr!=null&&x.icr<1?'#dc2626':'inherit'}">${x.icr!=null?Number(x.icr).toFixed(1):'—'}</td>
          <td style="border:1px solid #e2e8f0;padding:2px 5px;text-align:right">${x.ocfop!=null?Number(x.ocfop).toFixed(2):'—'}</td>
          <td style="border:1px solid #e2e8f0;padding:2px 5px;text-align:right;color:${pc(x.r1m!=null?x.r1m*100:null)}">${x.r1m!=null?pf(x.r1m*100):'—'}</td>
          <td style="border:1px solid #e2e8f0;padding:2px 5px;text-align:right">${x.upside!=null?pf(x.upside*100):'—'}</td>
          <td style="border:1px solid #e2e8f0;padding:2px 5px;text-align:right;font-weight:700">${won(per)}</td></tr>`).join('')}</tbody></table>`:'<div class="note" style="margin-top:4px">현재 조건을 통과하는 종목 없음 — 비중은 ETF 로 대체</div>'}</div>`; }).join(''); };
  $('al_kr').innerHTML=bk('kr','kr_eq'); $('al_us').innerHTML=bk('us','us_eq');
  $('al_bk_note').textContent=D.baskets.note||'';
  // ⑤ 부동산
  const R=D.realestate||{};
  $('al_re').innerHTML=`<div style="font-size:13px"><b>권고 비율: ${E(R.band||'—')}</b></div>
    <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:6px">${(R.rows||[]).map(r=>`<span style="border:1px solid #e2e8f0;border-radius:8px;padding:3px 9px;font-size:12px;background:#fff">${E(r.r)} 12M <b style="color:${pc(r.g)}">${pf(r.g)}</b> · ${E(r.verdict||'')}</span>`).join('')}</div>
    <div class="note" style="margin-top:4px">${E(R.note||'')}</div>`;
  // ⑥ 이력
  if(ch){try{ch.destroy();}catch(e){}}
  if(H&&H.length>1){ const labels=H.map(x=>x.d);
    ch=new Chart($('al_cv'),{type:'line',data:{labels,datasets:keys.map(k=>({label:D.label[k].split('(')[0],data:H.map(x=>x.w[k]),borderColor:COL[k],backgroundColor:COL[k]+'22',fill:true,pointRadius:0,borderWidth:1.5,stack:'s'}))},
      options:{responsive:true,maintainAspectRatio:false,interaction:{mode:'index',intersect:false},plugins:{legend:{labels:{boxWidth:12,font:{size:10.5}}}},
        scales:{x:{ticks:{maxTicksLimit:10,font:{size:10}}},y:{stacked:true,min:0,max:100,ticks:{font:{size:10},callback:v=>v+'%'}}}}});
    $('al_hist_note').textContent=`${H.length}일 누적 · 비중 변화를 쌓아 본다(100% 스택)`; }
  else $('al_hist_note').textContent='이력은 내일부터 쌓입니다(매일 1행).';
}

function load(force){
  if(D&&!force){ render(); return; }
  $('al_asof').textContent='불러오는 중…';
  Promise.all([fetch('/api/db/alloc',{cache:'no-cache'}).then(r=>{if(!r.ok)throw new Error('HTTP '+r.status);return r.json();}),
               fetch('/api/db/alloc_hist',{cache:'no-cache'}).then(r=>r.ok?r.json():[]).catch(()=>[])])
  .then(([a,h])=>{ D=a; H=h; render(); })
  .catch(e=>{ $('al_asof').textContent='로드 실패: '+e.message+' (07:55 수집 전이면 다음날 표시)'; });
}
window.renderAlloc=function(){ load(false); };
const tb=document.querySelector('.tab[data-pane="p_al"]'); if(tb) tb.addEventListener('click',()=>load(false));
document.addEventListener('DOMContentLoaded',function(){
  const t=$('al_total'); if(t){ try{ const v=localStorage.getItem(LS); if(v) t.value=v; }catch(e){} t.addEventListener('change',()=>render()); t.addEventListener('keyup',e=>{ if(e.key==='Enter') render(); }); }
  const b=$('al_reload'); if(b) b.onclick=()=>load(true);
});
})();
