/* moat.js — 🏰 해자 워치 탭 (2026-08-30 신설)
   데이터: /api/db/moat (scripts/fetch_moat.py · 매일 06:30 cron · LLM 토큰 0)
   목적: 해자지도(부록D·F·H)의 독점·준독점(파란 배지) 상장 종목에서
        "일시적 빠짐(기회 후보)"과 "이유 있는 하락(구조 의심)"을 구분해 보여준다.
   판정은 '검토 후보 알림'이지 매수 신호가 아니다 — 가치함정은 가격 신호로 안 걸러진다. */
(function(){
'use strict';
let D=null, FILT='all';
const $=id=>document.getElementById(id);
const pf=v=>v==null?'—':(v>0?'+':'')+v.toFixed(1)+'%';
const pc=v=>v==null?'#64748b':(v>0?'#dc2626':v<0?'#2563eb':'#64748b');
// (2026-08-30) 심볼 접미사 → 국가·거래소 (사용자 요청)
function mkt(sym){
  if(/\.KS$/.test(sym)) return ['🇰🇷','한국 KRX'];
  if(/\.KQ$/.test(sym)) return ['🇰🇷','한국 코스닥'];
  if(/\.T$/.test(sym))  return ['🇯🇵','일본 도쿄'];
  if(/\.SS$/.test(sym)) return ['🇨🇳','중국 상하이'];
  if(/\.SZ$/.test(sym)) return ['🇨🇳','중국 선전'];
  if(/\.HK$/.test(sym)) return ['🇭🇰','홍콩'];
  if(/\.L$/.test(sym))  return ['🇬🇧','영국 런던'];
  if(/\.AX$/.test(sym)) return ['🇦🇺','호주 ASX'];
  if(/\.DE$/.test(sym)) return ['🇩🇪','독일'];
  return ['🇺🇸','미국'];
}
const V={buy:  ['🟢','일시적 빠짐 후보','#166534','#dcfce7','해자 유지 신호 속 큰 낙폭 — 검토 후보'],
        buy_m:['🟢','빠짐 후보 ※수동확인','#166534','#dcfce7','큰 낙폭이나 선행지표 미연결 — 해자 훼손 뉴스 직접 확인 필요'],
        risk: ['🔴','선행지표 동반 악화','#b91c1c','#fee2e2','낙폭 + 연결 지표도 하락 — 구조적 이유 의심'],
        watch:['🟡','관찰','#a16207','#fef9c3','중간 지대 — 신호 대기'],
        top:  ['⚪','고점권','#475569','#f1f5f9','52주 고점 부근 — 빠짐 신호 없음']};
const ORDER={buy:0,buy_m:1,risk:2,watch:3,top:4};

function spark(sv,color){
  if(!sv||sv.length<2) return '';
  const mn=Math.min(...sv),mx=Math.max(...sv),h=34,w=150;
  const pts=sv.map((v,i)=>`${(i/(sv.length-1)*w).toFixed(1)},${(h-3-(v-mn)/(mx-mn||1)*(h-6)).toFixed(1)}`).join(' ');
  return `<svg width="${w}" height="${h}" style="display:block"><polyline points="${pts}" fill="none" stroke="${color}" stroke-width="1.5"/></svg>`;
}

function render(){
  if(!D) return;
  $('mw_asof').textContent='기준 '+(D.as_of||'')+' · 서버 매일 06:30 자동 갱신';
  const rows=D.rows||[], c=D.counts||{};
  // 필터 칩 + 신호등 요약
  const FL=[['all','전체 '+rows.length],['buy','🟢 빠짐 후보 '+((c.buy||0)+(c.buy_m||0))],['risk','🔴 악화 '+(c.risk||0)],['watch','🟡 관찰 '+(c.watch||0)],['top','⚪ 고점권 '+(c.top||0)]];
  $('mw_filt').innerHTML=FL.map(f=>
    `<button data-f="${f[0]}" style="margin-right:6px;padding:3px 12px;border-radius:14px;border:1px solid ${FILT===f[0]?'#334155':'#d6d9de'};background:${FILT===f[0]?'#334155':'#fff'};color:${FILT===f[0]?'#fff':'#333'};cursor:pointer;font-size:12.5px">${f[1]}</button>`).join('');
  $('mw_filt').querySelectorAll('button').forEach(b=>b.onclick=()=>{FILT=b.dataset.f;render();});

  // (Phase3) 오늘의 판정 전환 배너
  const chg=rows.filter(r=>r.vd_prev);
  const VE={buy:'🟢',buy_m:'🟢※',risk:'🔴',watch:'🟡',top:'⚪'};
  const bn=$('mw_chg');
  if(bn) bn.innerHTML=chg.length?`<b>⚡ 오늘의 전환</b> — ${chg.map(r=>`${r.name} ${VE[r.vd_prev]||r.vd_prev}→${VE[r.verdict]}`).join(' · ')}`
                               :'오늘 판정 전환 없음 — 신호등은 매일 06:30 재산출';
  let list=[...rows];
  if(FILT==='buy') list=list.filter(r=>r.verdict==='buy'||r.verdict==='buy_m');
  else if(FILT!=='all') list=list.filter(r=>r.verdict===FILT);
  // 정렬: 🟢 우선 → 낙폭 큰 순 (기회 후보가 맨 위)
  list.sort((a,b)=>(ORDER[a.verdict]-ORDER[b.verdict])||((a.dd??0)-(b.dd??0)));

  $('mw_grid').innerHTML=list.map(r=>{
    const v=V[r.verdict]||V.watch;
    const dcol=r.dd==null?'#64748b':(r.dd<=-20?'#2563eb':r.dd<=-10?'#a16207':'#64748b');
    return `<div style="flex:1 1 340px;max-width:430px;border:1px solid #e2e8f0;border-top:3px solid ${v[2]};border-radius:10px;background:#fff;padding:10px 12px">
      <div style="display:flex;justify-content:space-between;align-items:center">
        <b style="font-size:14px">${r.name} <span style="font-size:10.5px;color:#94a3b8">${r.sym}</span>
          <span style="font-size:10.5px;background:#f1f5f9;color:#475569;border-radius:8px;padding:1px 7px;margin-left:3px">${mkt(r.sym)[0]} ${mkt(r.sym)[1]}</span></b>
        <span title="${v[4]}" style="background:${v[3]};color:${v[2]};border-radius:10px;padding:2px 9px;font-size:11.5px;font-weight:700">${v[0]} ${v[1]}${r.vd_days>1?` <span style="font-weight:400;opacity:.8">D+${r.vd_days}</span>`:r.vd_prev?' <span style="font-weight:400">⚡오늘 전환</span>':''}</span></div>
      <div style="font-size:11px;color:#64748b;margin:3px 0 6px"><span style="background:#eef2ff;color:#4338ca;border-radius:8px;padding:1px 7px;margin-right:5px">${r.sec}</span>${r.tier==='B2+'?'<span title="관계도 배지는 황색(복점·양강)이나 해자 실질이 독점급이라 선별 편입" style="background:#fef3c7;color:#b45309;border-radius:8px;padding:1px 7px;margin-right:5px">선별 B2</span>':''}${r.moat}</div>
      <div style="display:flex;gap:10px;align-items:center">
        ${spark(r.spark,v[2])}
        <table style="font-size:11.5px;border-collapse:collapse;flex:1;white-space:nowrap">
          <tr><td style="color:#94a3b8;padding:1px 6px 1px 0">52주고점比</td><td style="text-align:right;font-weight:800;color:${dcol}">${pf(r.dd)}</td>
              <td style="color:#94a3b8;padding:1px 6px 1px 12px">RSI</td><td style="text-align:right;font-weight:700;color:${r.rsi==null?'#64748b':r.rsi<30?'#2563eb':r.rsi>70?'#dc2626':'#334155'}">${r.rsi==null?'—':r.rsi}</td></tr>
          <tr><td style="color:#94a3b8;padding:1px 6px 1px 0">200일선比</td><td style="text-align:right;color:${pc(r.gap200)}">${pf(r.gap200)}</td>
              <td style="color:#94a3b8;padding:1px 6px 1px 12px">3개월</td><td style="text-align:right;color:${pc(r.m3)}">${pf(r.m3)}</td></tr>
          <tr><td style="color:#94a3b8;padding:1px 6px 1px 0">1년</td><td style="text-align:right;color:${pc(r.y1)}">${pf(r.y1)}</td>
              <td style="color:#94a3b8;padding:1px 6px 1px 12px">현재가</td><td style="text-align:right">${(r.cur??0).toLocaleString()}</td></tr>
          <tr><td style="color:#94a3b8;padding:1px 6px 1px 0">PER(${r.val?r.val.src:'-'})</td><td style="text-align:right;font-weight:700">${r.val?r.val.per:'—'}</td>
              <td style="color:#94a3b8;padding:1px 6px 1px 12px">밴드</td><td style="text-align:right;font-size:10.5px">${r.val?(r.val.pct!=null?`<b style="color:${r.val.pct<=25?'#166534':r.val.pct>=75?'#b91c1c':'#334155'}">하위 ${r.val.pct}%</b>(${r.val.n}일)`:`누적 ${r.val.n}일`):'—'}</td></tr>
        </table></div>
      <div style="font-size:11px;margin-top:6px;padding-top:6px;border-top:1px dashed #e2e8f0">
        ${r.lead?`🔗 선행지표 <b>${r.lead.name}</b> — 1개월 <span style="color:${pc(r.lead.m1)}">${pf(r.lead.m1)}</span> · 3개월 <b style="color:${pc(r.lead.m3)}">${pf(r.lead.m3)}</b> · 6개월 <span style="color:${pc(r.lead.m6)}">${pf(r.lead.m6)}</span> · 1년 <span style="color:${pc(r.lead.y1)}">${pf(r.lead.y1)}</span>`
                :'🔗 선행지표 미연결 — 해자 훼손 뉴스 수동 확인 대상'}
        ${r.risk?`<div style="color:#b45309;margin-top:3px">⚠ ${r.risk}</div>`:''}
        ${(function(){const a=(window.__moatLLM&&window.__moatLLM.map[r.sym]);if(!a)return '';
          const c=a.verdict_llm==='유지'?'#166534':a.verdict_llm==='훼손 의심'?'#b91c1c':'#a16207';
          return `<div style="margin-top:3px">🧠 AI 점검(${(window.__moatLLM.as_of||'').slice(5,10)}) <b style="color:${c}">${a.verdict_llm}</b> — ${a.note||''}${a.src?` <a href="${a.src}" target="_blank" rel="noopener" style="color:#94a3b8">[근거]</a>`:''}</div>`;})()}</div>
    </div>`;}).join('');
}

function load(force){
  if(D&&!force){ render(); return; }
  $('mw_asof').textContent='불러오는 중…';
  // (v3.93) 보고서 실행이 남기는 AI 점검 결과 — 없으면 조용히 생략(404 무해)
  fetch('/api/db/moat_llm',{cache:'no-cache'}).then(r=>r.ok?r.json():null).then(j=>{
    if(j&&j.checks){ window.__moatLLM={as_of:j.as_of,map:Object.fromEntries(j.checks.map(c=>[c.sym,c]))}; if(D) render(); }
  }).catch(()=>{});
  fetch('/api/db/moat',{cache:'no-cache'}).then(r=>{
    if(!r.ok) throw new Error('HTTP '+r.status);
    return r.json();
  }).then(j=>{ D=j; render(); })
  .catch(e=>{ $('mw_asof').textContent='로드 실패: '+e.message+' (서버 수집 전이면 다음 06:30 이후 표시)'; });
}

window.renderMoat=function(){ load(false); };
document.addEventListener('DOMContentLoaded',function(){
  const b=$('mw_reload'); if(b) b.onclick=()=>load(true);
});
})();
