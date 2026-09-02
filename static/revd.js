/* revd.js — 📋 리비전 데일리 탭 (2026-09-02 신설)
   데이터: /api/kr_rev_daily (tp_history.json + kr_consensus.sqlite 일별 diff · mtime 캐시)

   근거(사용자 관찰 · 코스메카코리아 실측 2026-08):
     8/10 실적발표(영업익 컨센대비 +15.7%) → 8/11 증권사 6곳 목표가 일제 상향
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
  const head=`<div style="margin:12px 0 4px;font-weight:700;font-size:12.5px">${dstr(day.d)} <span class="note">전영업일 ${E(day.prev.slice(5))} 대비 · <span style="color:#dc2626">상향 ${nu}</span> · <span style="color:#2563eb">하향 ${nd}</span></span></div>`;
  if(!rows.length) return head+'<div class="note">변동 없음</div>';
  /* (2026-09-02 피드백) 좌우 병렬 배치용 가로 압축 — 시총은 종목 셀 둘째 줄, 변동기간 수는 변동률 옆 첨자 */
  const th=kind==='tp'
    ?'<tr><th style="text-align:left">종목</th><th>현재가</th><th>목표가 전→후</th><th>변동률</th><th>여력</th><th>실적발표</th></tr>'
    :'<tr><th style="text-align:left">종목</th><th>현재가</th><th>기간</th><th>영업익 전→후(억)</th><th>변동률</th><th>실적발표</th></tr>';
  const tr=rows.map(r=>{
    const nm=`<td style="text-align:left;cursor:pointer;white-space:nowrap" onclick="_revdNv('${E(r.c)}')"><b>${E(r.n)}</b><br><span class="note">${E(r.c)} · ${capf(r.cap)}</span></td>`;
    const px=`<td style="white-space:nowrap">${nf(r.px)}<br>${pf(r.chg)}</td>`;
    if(kind==='tp')
      return `<tr>${nm}${px}<td style="white-space:nowrap">${nf(r.old)} → <b>${nf(r.new)}</b></td><td>${pf(r.pct)}</td><td>${pf(r.up)}</td><td style="white-space:nowrap">${edd(r.edl,day.d)}</td></tr>`;
    return `<tr>${nm}${px}<td>${E(r.per)}</td><td style="white-space:nowrap">${nf(r.old)} → <b>${nf(r.new)}</b></td><td style="white-space:nowrap">${opch(r.old,r.new,r.pct)}<span class="note"> ${r.nch>1?'외'+(r.nch-1):''}</span></td><td style="white-space:nowrap">${edd(r.edl,day.d)}</td></tr>`;
  }).join('');
  return head+`<table class="mini" style="width:100%;font-size:11px;text-align:center">${th}${tr}</table>`;
}

function chips(kind){
  return `<span class="revd_chips" data-k="${kind}">
    ${['all','up','dn'].map(m=>`<button class="scrrst${MODE[kind]===m?' on':''}" data-m="${m}" style="font-size:11px${MODE[kind]===m?';background:#1e293b;color:#fff':''}">${m==='all'?'전체':m==='up'?'상향만':'하향만'}</button>`).join('')}</span>`;
}

/* ⓪ 발표 당일 서프라이즈 — 연쇄 1단계 (2026-09-02 추가). spr=영업익 컨센대비 · spr_s=매출 컨센대비 */
function spBlock(day){
  const head=`<div style="margin:12px 0 4px;font-weight:700;font-size:12.5px">${dstr(day.d)} <span class="note">발표 ${day.rows.length}건 (수치 파싱분)</span></div>`;
  /* (2026-09-02 피드백4·5) 컬럼 확장 + 기준 명시 — 컨센대비는 YoY/QoQ 가 아니라
     '발표한 분기의 실제치 vs 같은 분기의 증권사 컨센서스 추정치'다. 헤더에 (당분기 추정대비)
     를 병기하고 툴팁으로 풀어쓴다. */
  const _tt='발표 분기 실제치 vs 같은 분기 증권사 컨센서스 추정치 — 전년동기(YoY)·전분기(QoQ) 비교가 아님';
  const th=`<tr><th style="text-align:left">종목</th><th>현재가</th><th title="${_tt}">영업익 컨센대비<br><span style="font-weight:400;font-size:9.5px">(당분기 추정대비)</span></th><th>영업익<br>YoY</th><th>영업익<br>QoQ</th><th title="${_tt}">매출 컨센대비<br><span style="font-weight:400;font-size:9.5px">(당분기 추정대비)</span></th><th>매출<br>YoY</th><th>매출<br>QoQ</th><th>주가반응</th></tr>`;
  const tr=day.rows.map(r=>{
    const nm=`<td style="text-align:left;cursor:pointer;white-space:nowrap" onclick="_revdNv('${E(r.c)}')"><b>${E(r.n)}</b><br><span class="note">${E(r.c)} · ${capf(r.cap)}</span></td>`;
    const rr=[]; if(r.r1!=null) rr.push('D+1 '+pf(r.r1)); if(r.r5!=null) rr.push('D+5 '+pf(r.r5));
    return `<tr>${nm}<td style="white-space:nowrap">${nf(r.px)}<br>${pf(r.chg)}</td><td><b>${pf(r.spr)}</b></td><td>${pf(r.op_yoy)}</td><td>${pf(r.op_qoq)}</td><td><b>${pf(r.spr_s)}</b></td><td>${pf(r.sales_yoy)}</td><td>${pf(r.sales_qoq)}</td><td style="white-space:nowrap">${rr.join('<br>')||'—'}</td></tr>`;
  }).join('');
  return head+`<table class="mini" style="width:100%;font-size:11px;text-align:center">${th}${tr}</table>`;
}

/* ㉠ 발표 예정 + 선행 신호 — 캘린더 팝업 _leadBits 와 동일 신호를 리스트로 (2026-09-02) */
function upBlock(day){
  const head=`<div style="margin:12px 0 4px;font-weight:700;font-size:12.5px">${dstr(day.d)} 발표 예정 <span class="note">${day.rows.length}종 · 시총순</span></div>`;
  const th='<tr><th style="text-align:left">종목</th><th>현재가</th><th>영업익컨센 30일</th><th>목표가 90일</th><th>직전 서프</th><th>연속순매수</th><th>수출 YoY</th></tr>';
  const tr=day.rows.map(r=>{
    /* 확정(IR 공시) vs 추정(직전 발표일+91일 — 전종목 확대, 2026-09-02) 뱃지 */
    const sb=r.src==='추정'?'<span style="color:#b45309;font-size:9.5px;border:1px solid #fcd34d;border-radius:4px;padding:0 3px;margin-left:3px">추정</span>':'';
    const nm=`<td style="text-align:left;cursor:pointer;white-space:nowrap" onclick="_revdNv('${E(r.c)}')"><b>${E(r.n)}</b>${sb}<br><span class="note">${E(r.c)} · ${capf(r.cap)}</span></td>`;
    const sup=[]; if((r.fst||0)>0) sup.push('외인 '+r.fst+'일'); if((r.ost||0)>0) sup.push('기관 '+r.ost+'일');
    const kx=r.kx&&r.kx.yoy!=null?`${pf(r.kx.yoy)}<br><span class="note">${E(r.kx.th)} ${E(r.kx.m||'')}</span>`:'—';
    return `<tr>${nm}<td style="white-space:nowrap">${nf(r.px)}<br>${pf(r.chg)}</td><td>${pf(r.cr30)}</td><td>${pf(r.tprv90)}</td><td>${pf(r.spr)}</td><td style="white-space:nowrap">${sup.join(' ')||'—'}</td><td>${kx}</td></tr>`;
  }).join('');
  return head+`<table class="mini" style="width:100%;font-size:11px;text-align:center">${th}${tr}</table>`;
}

function render(){
  if(!D) return;
  $('rv_asof').textContent='기준 '+(D.asof||'')+' · 스냅샷 갱신 시 자동 재계산';
  $('rv_up').innerHTML=(D.up_days||[]).map(upBlock).join('')||'<div class="note">향후 7일 발표 예정 없음 (예정일은 IR 공시·컨센 커버 종목만 수집됨)</div>';
  $('rv_sp').innerHTML=(D.sp_days||[]).map(spBlock).join('')||'<div class="note">최근 발표 없음</div>';
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
