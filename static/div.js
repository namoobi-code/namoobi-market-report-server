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
  $('dv_kr').innerHTML=tbl('kr'); $('dv_us').innerHTML=tbl('us');
  $('dv_cal').innerHTML=calendar();
  $('dv_etf').innerHTML=`<table style="border-collapse:collapse;font-size:11.5px;background:#fff"><thead><tr>${['ETF','현재가','분배율','1년 수익','보수'].map(x=>`<th style="${TH}">${x}</th>`).join('')}</tr></thead><tbody>${(D.etfs||[]).map(e=>`<tr><td style="${TD}"><b>${E(e.n)}</b><span class="note" style="font-size:10px"> ${E(e.c)}</span></td><td style="${TD}text-align:right">${nf(e.px,0)}</td><td style="${TD}text-align:right;font-weight:700">${e.divy==null?'—':e.divy.toFixed(2)+'%'}</td><td style="${TD}text-align:right">${pf(e.r1y)}</td><td style="${TD}text-align:right">${e.fee==null?'—':e.fee+'%'}</td></tr>`).join('')}</tbody></table><div class="note" style="margin-top:4px">국내 상장 배당·커버드콜·인컴 ETF 시총 상위 25 (ETF 풀 · 다음금융). 커버드콜은 분배율이 높지만 상승장 수익을 포기하는 구조 — 분배율만 보고 고르지 말 것(기사)</div>`;
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
