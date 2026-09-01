/* revd.js — 📋 리비전 데일리 탭 (2026-09-02 신설)
   데이터: /api/kr_rev_daily (tp_history.json + kr_consensus.sqlite 일별 diff · mtime 캐시)

   근거(사용자 관찰 · 코스메카코리아 실측 2026-08):
     8/10 실적발표(영업익 컨센比 +15.7%) → 8/11 증권사 6곳 목표가 일제 상향
     → 8/12 영업익 컨센서스 상향(+7.8~11.4%) → 주가 지속 상승(D+5 +32.6%).
   이 연쇄의 2단계(목표가 변동)·3단계(컨센 리비전)를 매일 전 종목 횡단 리스트로 제공
   → 확인·검토 후 매수 판단용. 개별 종목 심층은 종목 클릭(네이버 팝업) 또는 TICKER 차트로.

   주의: 평균 목표가는 리포트 ~24건 롤링 평균 — 액면병합·오래된 리포트 이탈로
   급변할 수 있다(실측 091810 +400%). 원자료 그대로 표시(가공 금지), 이 각주로 안내. */
(function(){
'use strict';
const $=id=>document.getElementById(id);
const E=s=>String(s??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
let D=null, MODE={tp:'all', op:'all'};   // all | up | dn

const WD=['일','월','화','수','목','금','토'];
const nf=n=>n==null?'—':Number(n).toLocaleString();
const capf=v=>v==null?'—':(v/1e12>=1?(v/1e12).toFixed(1)+'조':Math.round(v/1e8).toLocaleString()+'억');
const pctc=v=>v==null?'#64748b':(v>0?'#dc2626':v<0?'#2563eb':'#64748b');
const pf=(v,d)=>v==null?'—':`<span style="color:${pctc(v)}">${v>0?'+':''}${v.toFixed(d==null?1:d)}%</span>`;
const dstr=d=>{const t=new Date(d); return d.slice(5)+'('+WD[t.getDay()]+')';};

/* 직전 실적발표 D+n — 발표 연쇄(실적→목표가→리비전) 확인용. 14일 이내면 강조.
   edl 은 풀 원본이 8자리('20260811') — ISO 로 정규화 후 계산(실측). */
function edd(edl,d){
  if(!edl) return '—';
  const iso=String(edl).replace(/^(\d{4})(\d{2})(\d{2})$/,'$1-$2-$3');
  const n=Math.round((new Date(d)-new Date(iso))/864e5);
  if(isNaN(n)||n<0||n>90) return '—';
  const s=`D+${n}`;
  return n<=14?`<b style="color:#b45309">${E(iso.slice(5))} ${s}</b>`:`${E(iso.slice(5))} ${s}`;
}
/* 컨센 전→후 — 부호가 바뀌면 %가 왜곡되므로(실측 -23→25 = '-208%') 전환 뱃지로 표기 */
function opch(o,n,pct){
  if(o<0&&n>=0) return '<b style="color:#dc2626">흑자전환</b>';
  if(o>=0&&n<0) return '<b style="color:#2563eb">적자전환</b>';
  return pf(pct);
}
const openNv=c=>window.open(`https://m.stock.naver.com/domestic/stock/${c}/total`,'gm_pop_w','width=480,height=860');
window._revdNv=openNv;

function dayBlock(day,kind){
  let rows=day.rows;
  if(MODE[kind]==='up') rows=rows.filter(r=>(r.pct??0)>0||(kind==='op'&&r.old<0&&r.new>=0));
  if(MODE[kind]==='dn') rows=rows.filter(r=>(r.pct??0)<0||(kind==='op'&&r.old>=0&&r.new<0));
  const nu=day.rows.filter(r=>(r.pct??0)>0).length, nd=day.rows.filter(r=>(r.pct??0)<0).length;
  const head=`<div style="margin:14px 0 4px;font-weight:700">${dstr(day.d)} <span class="note">전영업일 ${E(day.prev.slice(5))} 대비 · <span style="color:#dc2626">상향 ${nu}</span> · <span style="color:#2563eb">하향 ${nd}</span></span></div>`;
  if(!rows.length) return head+'<div class="note">변동 없음</div>';
  const th=kind==='tp'
    ?'<tr><th style="text-align:left">종목</th><th>시총</th><th>현재가</th><th>평균목표가 전→후</th><th>변동률</th><th>상승여력</th><th>직전 실적발표</th></tr>'
    :'<tr><th style="text-align:left">종목</th><th>시총</th><th>현재가</th><th>기간</th><th>컨센 영업익 전→후(억)</th><th>변동률</th><th>변동기간</th><th>직전 실적발표</th></tr>';
  const tr=rows.map(r=>{
    const nm=`<td style="text-align:left;cursor:pointer;white-space:nowrap" onclick="_revdNv('${E(r.c)}')"><b>${E(r.n)}</b> <span class="note">${E(r.c)}</span></td>`;
    const px=`<td style="white-space:nowrap">${nf(r.px)} ${pf(r.chg)}</td>`;
    if(kind==='tp')
      return `<tr>${nm}<td>${capf(r.cap)}</td>${px}<td style="white-space:nowrap">${nf(r.old)} → <b>${nf(r.new)}</b></td><td>${pf(r.pct)}</td><td>${pf(r.up)}</td><td>${edd(r.edl,r.d||day.d)}</td></tr>`;
    return `<tr>${nm}<td>${capf(r.cap)}</td>${px}<td>${E(r.per)}</td><td style="white-space:nowrap">${nf(r.old)} → <b>${nf(r.new)}</b></td><td>${opch(r.old,r.new,r.pct)}</td><td>${r.nch}개</td><td>${edd(r.edl,day.d)}</td></tr>`;
  }).join('');
  return head+`<table class="mini" style="width:100%;font-size:12px;text-align:center">${th}${tr}</table>`;
}

function chips(kind){
  return `<span class="revd_chips" data-k="${kind}">
    ${['all','up','dn'].map(m=>`<button class="scrrst${MODE[kind]===m?' on':''}" data-m="${m}" style="font-size:11px${MODE[kind]===m?';background:#1e293b;color:#fff':''}">${m==='all'?'전체':m==='up'?'상향만':'하향만'}</button>`).join('')}</span>`;
}

function render(){
  if(!D) return;
  $('rv_asof').textContent='기준 '+(D.asof||'')+' · 스냅샷 갱신 시 자동 재계산';
  $('rv_tp').innerHTML=chips('tp')+(D.tp_days||[]).map(d=>dayBlock(d,'tp')).join('');
  $('rv_op').innerHTML=chips('op')+(D.op_days||[]).map(d=>dayBlock(d,'op')).join('');
  document.querySelectorAll('.revd_chips button').forEach(b=>b.onclick=()=>{
    MODE[b.parentElement.dataset.k]=b.dataset.m; render();});
}

function load(force){
  if(D&&!force){ render(); return; }
  $('rv_asof').textContent='불러오는 중…';
  fetch('/api/kr_rev_daily',{cache:'no-cache'}).then(r=>{
    if(!r.ok) throw new Error('HTTP '+r.status);
    return r.json();
  }).then(j=>{ D=j; render(); })
  .catch(e=>{ $('rv_asof').textContent='로드 실패: '+e.message; });
}

window.renderRevd=function(){ load(false); };
document.addEventListener('DOMContentLoaded',function(){
  const b=$('rv_reload'); if(b) b.onclick=()=>load(true);
});
})();
