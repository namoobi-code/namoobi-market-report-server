/* div.js — 💰 배당 탭 (2026-10-17 신설)
   데이터: /api/db/dividend (scripts/fetch_dividend.py 매일 08:10)
   구성: ① 배당 환경(국채 vs 배당, 배당 여력, 분리과세) ② 체크리스트 4가지 ③ KR 표 ④ US 표 ⑤ 월배당 달력 ⑥ 고배당 ETF
   표는 종목 클릭 없이 한 줄에 전부: 배당률·예상 DPS/배당률·주기·다음 배당락·배당락 폭·연속증가·3년 CAGR·안전/타이밍/위험 신호등·분리과세. 투자권유 아님. */
(function(){
'use strict';
const $=id=>document.getElementById(id);
const E=s=>String(s??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
const nf=(n,d)=>n==null?'—':Number(n).toLocaleString(undefined,{maximumFractionDigits:d==null?2:d});
const pf=(v,d=1)=>v==null?'—':`<span class="${v>0?'up':(v<0?'dn':'')}">${v>0?'+':''}${Number(v).toFixed(d)}%</span>`;
const TD='border:1px solid #e2e8f0;padding:4px 7px;', TH='border:1px solid #e2e8f0;padding:5px 7px;font-size:11px;background:#f8fafc;white-space:nowrap;';
let D=null,_init=false; const SORT={kr:'score',us:'score'};
function miniSpark(cv,vals,color){ if(!vals||vals.length<2) return; const W=90,H=26,dpr=window.devicePixelRatio||1; cv.width=W*dpr; cv.height=H*dpr; const x=cv.getContext('2d'); x.scale(dpr,dpr);
  const mn=Math.min(...vals),mx=Math.max(...vals),rg=(mx-mn)||1; x.beginPath(); vals.forEach((v,i)=>{const px=i/(vals.length-1)*(W-2)+1,py=H-2-(v-mn)/rg*(H-4); i?x.lineTo(px,py):x.moveTo(px,py);}); x.strokeStyle=color; x.lineWidth=1.3; x.stroke(); }
const dots=(n,max,col)=>Array.from({length:max},(_,i)=>`<span style="display:inline-block;width:8px;height:8px;border-radius:4px;margin-right:2px;background:${i<n?col:'#e2e8f0'}"></span>`).join('');
function lamp(r){ const s=r.safe+r.timing-r.risk; return s>=4?['🟢','유리']:s>=2?['🟡','보통']:['🔴','대기']; }
function tbl(mk){
  const R=[...(D[mk]||[])]; const k=SORT[mk];
  R.sort((a,b)=>((b[k]??-1e9)-(a[k]??-1e9)));
  const isKr=mk==='kr';
  const hd=[['score','종합'],['name','종목'],['px','현재가'],['divy','배당률'],['ydiv_est','예상 배당률'],['dps_est','예상 DPS'],['cyc','주기'],['next_ex','다음 배당락(추정)'],['drop','배당락 폭'],['inc','연속증가'],['cagr3','DPS 3Y CAGR'],['payout','배당성향'],['safe','① 여력·지속'],['timing','② 지금 유리?'],['risk','③ 하락 위험'],[isKr?'sep_tax':'mdd5',isKr?'분리과세':'5년 MDD'],['vs200','200일선比'],['rsi','RSI']];
  let h=`<table style="border-collapse:collapse;font-size:11.5px;background:#fff;width:100%"><thead><tr>${hd.map(([key,lb])=>`<th style="${TH}cursor:pointer;${SORT[mk]===key?'color:#1d4ed8':''}" data-k="${key}" data-mk="${mk}">${lb}${SORT[mk]===key?' ▼':''}</th>`).join('')}</tr></thead><tbody>`;
  R.forEach(r=>{ const [ic,lb]=lamp(r);
    h+=`<tr>
      <td style="${TD}white-space:nowrap"><b>${ic}</b> ${lb} <span class="note" style="font-size:10px">${r.score}</span></td>
      <td style="${TD}white-space:nowrap"><b>${E(r.name)}</b><span class="note" style="font-size:10px"> ${E(r.c)}</span>${r.special?' <span title="직전 DPS가 전년 2배↑ 또는 배당성향 100%↑ — 일회성 가능성" style="color:#b45309;font-size:10px">⚠특별</span>':''}</td>
      <td style="${TD}text-align:right">${isKr?nf(r.px,0):'$'+nf(r.px,2)}</td>
      <td style="${TD}text-align:right;font-weight:700">${r.divy==null?'—':r.divy.toFixed(2)+'%'}</td>
      <td style="${TD}text-align:right;color:#0f766e;font-weight:700" title="${E(r.est_note||'')}">${r.ydiv_est==null?'—':r.ydiv_est.toFixed(2)+'%'}</td>
      <td style="${TD}text-align:right" title="${E(r.est_note||'')}">${r.dps_est==null?'—':(isKr?nf(r.dps_est,0)+'원':'$'+nf(r.dps_est,3))}<span class="note" style="font-size:10px">${r.dps_last!=null?' (확정 '+(isKr?nf(r.dps_last,0):'$'+nf(r.dps_last,3))+' · '+r.dps_year+')':''}</span></td>
      <td style="${TD}">${E(r.cyc||'—')}${r.pay_months?`<span class="note" style="font-size:10px"> ${r.pay_months.join('·')}월</span>`:''}</td>
      <td style="${TD}white-space:nowrap">${r.next_ex?E(r.next_ex.slice(2))+(r.dday!=null?` <b style="color:${r.dday<=30?'#dc2626':'#475569'}">D-${r.dday}</b>`:''):'—'}<span class="note" style="font-size:10px">${r.last_ex?' (직전 '+r.last_ex.slice(2)+')':''}</span></td>
      <td style="${TD}text-align:right">${r.drop==null?'—':r.drop.toFixed(2)+'%'}</td>
      <td style="${TD}text-align:right">${r.inc==null?'—':(r.inc>=30?'30년+':r.inc+'년')}</td>
      <td style="${TD}text-align:right">${pf(r.cagr3)}</td>
      <td style="${TD}text-align:right">${r.payout==null?'—':r.payout+'%'}</td>
      <td style="${TD}" title="${E(r.safe_why||'')}">${dots(r.safe,3,'#16a34a')}</td>
      <td style="${TD}" title="${E(r.timing_why||'')}">${dots(r.timing,4,'#2563eb')}</td>
      <td style="${TD}" title="${E(r.risk_why||'')}">${dots(r.risk,4,'#dc2626')}</td>
      <td style="${TD}text-align:center">${isKr?(r.sep_tax===true?'<b style="color:#16a34a">적격</b>':r.sep_tax===false?'<span class="note">—</span>':'—'):(r.mdd5==null?'—':pf(r.mdd5,0))}</td>
      <td style="${TD}text-align:right">${pf(r.vs200)}</td>
      <td style="${TD}text-align:right">${r.rsi==null?'—':r.rsi.toFixed(0)}</td></tr>`;});
  h+=`</tbody></table>`;
  return h;
}
function calendar(){
  const U=D.us||[]; const g={};
  U.filter(r=>r.pay_months&&r.freq>=4&&r.safe>=2).forEach(r=>{ const key=r.pay_months.join('·'); (g[key]=g[key]||[]).push(r); });
  const order=Object.keys(g).sort((a,b)=>g[b].length-g[a].length).slice(0,4);
  return `<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:10px">${order.map(k=>`<div class="box" style="padding:10px 12px"><b style="font-size:12.5px">${k}월 배당락 그룹</b> <span class="note">${g[k].length}종목 · 여력 2점↑</span><div style="font-size:11.5px;margin-top:4px;line-height:1.7">${g[k].slice(0,8).map(r=>`${lamp(r)[0]} ${E(r.name)} <span class="note">${r.divy}%</span>`).join('<br>')}</div></div>`).join('')}</div>
    <div class="note" style="margin-top:5px">1·4·7·10 / 2·5·8·11 / 3·6·9·12 그룹에서 한 종목씩 고르면 매월 배당 수령 — 월배당 종목은 단독으로 12회. KR 분기배당(삼성전자·현대차·KT&G 등)은 위 KR 표의 '주기' 열에 지급월 표시.</div>`;
}
function render(){
  const y=D.y10||{};
  $('dv_asof').textContent='기준 '+(D.as_of||'')+' · 서버 매일 08:10';
  $('dv_env').innerHTML=`<div style="display:flex;gap:8px;flex-wrap:wrap">
    <div style="flex:1;min-width:220px;border:1px solid #e2e8f0;border-radius:8px;padding:8px 12px;background:#fff"><div class="note">배당 vs 국채 — 배당주의 허들</div><div style="font-size:16px;font-weight:800">韓 10년 ${y.KR!=null?y.KR.toFixed(2):'—'}% · 美 10년 ${y.US!=null?y.US.toFixed(2):'—'}%</div><div class="note" style="font-size:11px">배당률이 국채금리를 못 넘으면 '배당 때문에' 살 이유가 약하다 — 표의 ② 타이밍에 '배당률≥국채' 항목으로 반영. 금리 고점 통과(📜 채권 탭 체크리스트) 뒤엔 허들이 내려와 배당주에 순풍</div></div>
    <div style="flex:1;min-width:220px;border:1px solid #e2e8f0;border-radius:8px;padding:8px 12px;background:#fff"><div class="note">코스피 제조업 배당 여력 (리딩투자증권)</div><div style="font-size:16px;font-weight:800">순이익 169 → 751 → 973조 · FCF 99 → 522 → 778조</div><div class="note" style="font-size:11px">2025 → 2026E → 2027E. 잉여현금흐름이 1년 새 5배 — '배당 여력 4배' 기사 제목의 근거. 여력이 커진 만큼 실제로 늘리는 회사를 골라내는 게 아래 표</div></div>
    <div style="flex:1;min-width:220px;border:1px solid #e2e8f0;border-radius:8px;padding:8px 12px;background:#fff"><div class="note">배당소득 분리과세 (2026 지급분부터)</div><div style="font-size:13px;font-weight:700;line-height:1.5">배당 안 줄이고 (성향 40%↑) 또는 (성향 25%↑ & DPS 10%↑ 증액)</div><div class="note" style="font-size:11px">요건 충족 기업의 배당은 금융소득 2,000만원 초과해도 종합과세 대신 낮은 세율 선택 가능 — KR 표 '분리과세' 열에 DART 배당공시·배당성향으로 자동 판정(참고용, 최종은 공시 확인)</div></div>
  </div>
  <div class="note" style="margin-top:8px;line-height:1.7"><b>체크리스트 4가지(기사)</b> → 표의 신호등: <b>① 여력·지속</b>(🟢3점: 배당성향 70%↓(US 85%) · 이익 증가 · 3년↑ 연속증가) · <b>② 지금 유리?</b>(4점: 200일선 아래 · RSI 50↓ · 배당락 45일 내 · 배당률≥국채) · <b>③ 하락 위험</b>(4점 많을수록 위험: 변동성 · 5년 MDD −40%↓ · 52주 고점比 −25%↓ · 배당락 폭 3%↑). <b>종합</b>=①×1.5+②+min(배당률,6)÷2−③−(⚠특별 1.5). ⚠특별=직전 DPS 전년比 2배↑ 또는 성향 100%↑(일회성 의심, 증가율 미적용). 🟢유리=①+②−③≥4. 예상 DPS 는 KR=확정 DPS×3년 CAGR(연속증가 2년↑일 때, 상한 30%) · US=직전 건당 배당×연 횟수 — 추정이며 이사회 확정 전까지 불확실. 열 제목 클릭=정렬.</div>`;
  // (2026-10-17 한경MONEY 2026.10 '커버드콜이 다시 주목받는 이유') 커버드콜 국면 판정
  const CC=D.cc||{}; const RG=CC.regime||{};
  const phc=p=>p==null?'#94a3b8':/강한/.test(p)?'#dc2626':/하락/.test(p)?'#b45309':/완만/.test(p)?'#16a34a':'#ca8a04';
  if($('dv_cc')) $('dv_cc').innerHTML=`<div style="display:flex;gap:10px;flex-wrap:wrap">
    <div style="flex:2;min-width:300px"><div style="display:flex;gap:8px;flex-wrap:wrap">${['spx','ndx','ks200'].filter(k=>RG[k]).map(k=>{const r=RG[k];return `<div style="flex:1;min-width:200px;border:1px solid #e2e8f0;border-left:4px solid ${phc(r.phase)};border-radius:8px;padding:8px 12px;background:#fff"><div class="note">${E(r.label)} 12개월 예측 <span style="font-size:10px">(Portfolio 탭 릿지)</span></div><div style="font-size:18px;font-weight:800;color:${phc(r.phase)}">${r.g12>0?'+':''}${r.g12}% <span style="font-size:11px;font-weight:400;color:#64748b">3M ${r.g3>0?'+':''}${r.g3} · 6M ${r.g6>0?'+':''}${r.g6}</span></div><div style="font-size:12px;font-weight:700">${E(r.phase)}</div><div class="note" style="font-size:11px;line-height:1.4">${E(r.verdict)}</div></div>`;}).join('')}</div>
      <div class="note" style="margin-top:6px;line-height:1.6">기사 체크리스트: <b>강한 상승 예상</b>→콜옵션 매도 비중 낮추거나 OTM / <b>횡보·완만 상승</b>→등가격 전통 커버드콜 / <b>큰 폭 하락 우려</b>→커버드콜만으론 하락 방어 한계, 별도 헤지. 커버드콜은 주식 대체가 아니라 포트폴리오 보완 수단(SC제일은행 김종국).</div></div>
    <div style="flex:1;min-width:220px;border:1px solid #e2e8f0;border-radius:8px;padding:8px 12px;background:#fff"><div class="note">S&P500 대비 커버드콜(BXM) 상대성과 — 1990년 이후 실측</div>
      <table style="border-collapse:collapse;font-size:12px;margin-top:4px;width:100%">${(CC.table||[]).map(([k,v])=>`<tr><td style="padding:2px 6px;border-bottom:1px solid #f1f5f9">${E(k)}</td><td style="padding:2px 6px;border-bottom:1px solid #f1f5f9;text-align:right;font-weight:800;color:${v>0?'#16a34a':'#dc2626'}">${v>0?'+':''}${v}%p</td><td style="padding:2px 6px;border-bottom:1px solid #f1f5f9;width:40%"><div style="height:8px;border-radius:4px;background:${v>0?'#bbf7d0':'#fecaca'};width:${Math.abs(v)*10}%"></div></td></tr>`).join('')}</table>
      <div class="note" style="font-size:10.5px;margin-top:4px">블룸버그·SC제일은행. 지수가 10% 넘게 오르면 커버드콜이 뒤처진다 — 아래 ETF 표의 '지수比 1년' 열이 올해 실제 결과</div></div></div>`;
  $('dv_kr').innerHTML=tbl('kr'); $('dv_us').innerHTML=tbl('us');
  $('dv_cal').innerHTML=calendar();
  const etfLamp=t=>t==null?['⚪','—']:t>=3?['🟢','유리']:t>=2?['🟡','보통']:['🔴','대기'];
  const etfTbl=(L,isKr)=>`<table style="border-collapse:collapse;font-size:11.5px;background:#fff;width:100%"><thead><tr>${['ETF','구분·전략','현재가','분배율<br><span class="note" style="font-weight:400">최근 1년 실지급</span>','1년(가격)','총수익 1년≈','지수比 1년<br><span class="note" style="font-weight:400">커버드콜만</span>','200일선比','RSI','52주 고점比','지금 유리?','1년 추세'].map(x=>`<th style="${TH}">${x}</th>`).join('')}</tr></thead><tbody>${
    L.map(e=>{const [ic,lb]=etfLamp(e.timing); return `<tr><td style="${TD}white-space:nowrap"><b>${E(e.n)}</b><span class="note" style="font-size:10px"> ${E(e.c)}</span></td><td style="${TD}font-size:11px;color:#475569">${E(e.grp||'')}${e.strat?`<div style="color:#7c3aed;font-size:10.5px">${E(e.strat)}</div>`:''}</td><td style="${TD}text-align:right">${isKr?nf(e.px||e.px_y,0):'$'+nf(e.px_y,2)}</td><td style="${TD}text-align:right;font-weight:700;color:#0f766e">${e.dy==null?(e.divy!=null?e.divy.toFixed(2)+'%':'—'):e.dy.toFixed(2)+'%'}<span class="note" style="font-size:10px">${e.dyn?' '+e.dyn+'회':''}</span></td><td style="${TD}text-align:right">${pf(e.y1p!=null?e.y1p:e.r1y)}</td><td style="${TD}text-align:right;font-weight:700">${pf(e.tr1y)}</td><td style="${TD}text-align:right" title="${E(e.bench||'')} 총수익 대비">${e.rel1y==null?'<span class="note">—</span>':pf(e.rel1y)+'<span class="note" style="font-size:10px"> vs '+E((e.bench||'').replace('.KS','').replace('069500','K200'))+'</span>'}</td><td style="${TD}text-align:right">${pf(e.vs200)}</td><td style="${TD}text-align:right">${e.rsi==null?'—':e.rsi.toFixed(0)}</td><td style="${TD}text-align:right">${pf(e.hi52)}</td><td style="${TD}white-space:nowrap" title="${E(e.timing_why||'')}">${ic} ${lb}</td><td style="${TD}"><div style="width:90px;height:26px"><canvas id="dv_sp_${e.c}" width="90" height="26" style="display:block;width:90px;height:26px"></canvas></div></td></tr>`;}).join('')}</tbody></table>`;
  $('dv_etf').innerHTML=`<b style="font-size:12.5px">🇰🇷 국내 상장 배당·커버드콜·인컴 ETF <span class="note">시총 상위 25 (ETF 풀·다음금융 + 야후 1년)</span></b>${etfTbl(D.etfs||[],true)}
    <b style="font-size:12.5px;display:block;margin-top:14px">🇺🇸 미국 배당 ETF <span class="note">배당성장·고배당·귀족주·커버드콜·리츠 14종 (야후 1년 · 분배금 제외 가격 기준, 총수익=가격+분배)</span></b>${etfTbl(D.etfs_us||[],false)}
    <div class="note" style="margin-top:5px;line-height:1.6">지금 유리?=4점(200일선 아래 · RSI 50↓ · 분배율≥10년 국채 · 52주 고점比 −10%↓): 🟢3↑ 유리 / 🟡2 보통 / 🔴 대기. 커버드콜(JEPI·QYLD·커버드콜 OTM 등)은 분배율이 높지만 상승장 수익을 포기하는 구조 — 분배율만 보고 고르지 말 것(기사). 배당성장형(SCHD·DGRO·VIG)은 분배율은 낮아도 총수익이 길게 간다.</div>`;
  [...(D.etfs||[]),...(D.etfs_us||[])].forEach(e=>{const cv=$('dv_sp_'+e.c); if(cv&&e.spark) miniSpark(cv,e.spark,(e.y1p??e.r1y??0)>=0?'#dc2626':'#2563eb');});
  $('dv_counts').textContent=`KR ${D.n?.kr||0}종목(시총 3,000억↑·배당률 2%↑) 중 상위 80 · US ${D.n?.us||0}종목($5B↑·2%↑) 중 상위 80`;
  document.querySelectorAll('#p_dv th[data-k]').forEach(th=>th.onclick=()=>{ SORT[th.dataset.mk]=th.dataset.k; $('dv_'+th.dataset.mk).innerHTML=tbl(th.dataset.mk); bindSort(); });
}
function bindSort(){ document.querySelectorAll('#p_dv th[data-k]').forEach(th=>th.onclick=()=>{ SORT[th.dataset.mk]=th.dataset.k; $('dv_'+th.dataset.mk).innerHTML=tbl(th.dataset.mk); bindSort(); }); }
function init(){ if(_init) return; _init=true;
  fetch('/api/db/dividend',{cache:'no-cache'}).then(r=>{if(!r.ok) throw new Error('HTTP '+r.status); return r.json();})
    .then(d=>{D=d; try{render();}catch(err){$('dv_env').innerHTML=`<div style="color:#b91c1c;font-weight:700">렌더 오류: ${E(err&&err.message||err)}</div>`; throw err;}})
    .catch(e=>{$('dv_env').innerHTML=`<div class="note">dividend 로딩 실패: ${E(e.message||e)}</div>`;});
}
const tb=document.querySelector('.tab[data-pane="p_dv"]'); if(tb) tb.addEventListener('click',init);
})();
