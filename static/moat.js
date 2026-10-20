/* moat.js — 🏰 해자 워치 탭 (2026-08-30 신설 · 2026-10-21 3층 판정으로 개정)
   데이터: /api/db/moat (scripts/fetch_moat.py · 매일 06:30 cron · LLM 토큰 0)
   판정 3층 = ① 해자 유지 게이트(TTM EPS 전년比 + 영업이익 교차검증) → ② 안전마진(자기역사 3년 낙폭 하위 10%)
             → ③ 멈춤 확인(종가>20일선). 근거 백테스트는 fetch_moat.py 하단 주석.
   🔴 alert 는 '해자 해지 의심 — 사람이 확인'이지 매도 신호가 아니고, 🟢 buy 도 '검토 후보'다. */
(function(){
'use strict';
let D=null, FILT='all', MT='all';
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
const V={buy:  ['🟢','매수 후보','#166534','#dcfce7','이익 증가(게이트 통과) + 자기역사 낙폭 하위 10%(안전마진) + 종가>20일선(멈춤) — 세 조건 동시 충족. 백테스트 12M 승률 83%·최악10% -3%'],
        wait: ['🟡','싸졌지만 하락 중','#a16207','#fef9c3','게이트 통과 + 안전마진이나 종가가 아직 20일선 아래 — 떨어지는 칼날. 20일선 회복 시 🟢 전환'],
        alert:['🔴','해자 경보','#b91c1c','#fee2e2','TTM EPS 전년 대비 2분기 연속 감소 + 영업이익도 감소 — 해자 해지 의심. 사람이 확인할 것(매도 신호 아님)'],
        nogate:['🚫','이익 미확정','#6b21a8','#f3e8ff','안전마진은 있으나 TTM EPS 적자·비교 불가 — 잴 해자가 없어 매수 규칙 비적용(백테스트 승률 57%·최악10% -44%)'],
        watch:['🟡','관찰','#64748b','#f1f5f9','낙폭이 자기 역사상 특별하지 않음 — 신호 대기'],
        top:  ['⚪','고점권','#475569','#f1f5f9','52주 고점 부근 — 빠짐 신호 없음'],
        top_hot: ['⚪🔥','추세 건강','#0f766e','#ccfbf1','고점 질 점수 70+ — 신고가 최근·선행지표 동행·밴드 중하위 = 오를 이유가 살아있는 고점'],
        top_warn:['⚪⚠','과열·소진 주의','#b45309','#ffedd5','고점 질 점수 40미만 — 경신 끊김·다이버전스·이격 과대 = 멀티플 의존 고점'],
        // 구 판정(2026-10-21 이전 이력 표시용)
        buy_z:['🟢~','(구)빠짐 후보','#15803d','#dcfce7','구 규칙'], buy_m:['🟢※','(구)빠짐 후보','#166534','#dcfce7','구 규칙'], risk:['🔴','(구)선행지표 악화','#b91c1c','#fee2e2','구 규칙']};
const ORDER={alert:0,buy:1,wait:2,nogate:3,top_warn:4,watch:5,top_hot:6,top:7,buy_z:2,buy_m:2,risk:0};

function spark(sv,color){
  if(!sv||sv.length<2) return '';
  const mn=Math.min(...sv),mx=Math.max(...sv),h=34,w=150;
  const pts=sv.map((v,i)=>`${(i/(sv.length-1)*w).toFixed(1)},${(h-3-(v-mn)/(mx-mn||1)*(h-6)).toFixed(1)}`).join(' ');
  return `<div style="position:relative"><svg width="${w}" height="${h}" style="display:block"><polyline points="${pts}" fill="none" stroke="${color}" stroke-width="1.5"/></svg><span style="position:absolute;left:0;top:0;font-size:9px;color:#94a3b8">1년</span></div>`;
}

// (2026-09-04) 해자 '유형' 배지 — 모닝스타 5분류.
//   tier(B1/B2)는 해자의 '강도'만 본다. 유형은 '어떻게 무너지는가'를 알려주므로 감시 대상이 정해진다.
//   (노보노디스크 제거 사례 = 무형자산형이 대체 기술에 뚫린 경우)
function mtBadges(r){
  const T=(D&&D.moat_types)||{};
  return (r.mtype||[]).map((k,i)=>{const t=T[k]; if(!t) return '';
    return `<span title="${t.name} — ${t.risk}" style="background:${t.bg};color:${t.fg};border-radius:8px;padding:1px 7px;margin-right:4px;font-weight:${i===0?700:400}">${t.name}</span>`;
  }).join('');
}

function render(){
  if(!D) return;
  $('mw_asof').textContent='기준 '+(D.as_of||'')+' · 서버 매일 06:30 자동 갱신';
  const rows=D.rows||[], c=D.counts||{};
  // 필터 칩 + 신호등 요약
  const FL=[['all','전체 '+rows.length],['alert','🔴 해자 경보 '+(c.alert||0)],['buy','🟢 매수 후보 '+(c.buy||0)],['wait','🟡 싸졌지만 하락 중 '+(c.wait||0)],['nogate','🚫 이익 미확정 '+(c.nogate||0)],['watch','관찰 '+(c.watch||0)],['top','⚪ 고점권 '+((c.top||0)+(c.top_hot||0)+(c.top_warn||0))]];
  $('mw_filt').innerHTML=FL.map(f=>
    `<button data-f="${f[0]}" style="margin-right:6px;padding:3px 12px;border-radius:14px;border:1px solid ${FILT===f[0]?'#334155':'#d6d9de'};background:${FILT===f[0]?'#334155':'#fff'};color:${FILT===f[0]?'#fff':'#333'};cursor:pointer;font-size:12.5px">${f[1]}</button>`).join('');
  $('mw_filt').querySelectorAll('button').forEach(b=>b.onclick=()=>{FILT=b.dataset.f;render();});
  // 유형 필터 — 해자가 '어떻게 무너지는지'로 골라 보기
  const T=D.moat_types||{}, mc={};
  rows.forEach(r=>(r.mtype||[]).forEach(k=>mc[k]=(mc[k]||0)+1));
  const nreg=rows.filter(r=>r.reg).length;
  const MF=[['all','유형 전체']].concat(Object.keys(T).map(k=>[k,T[k].name+' '+(mc[k]||0)])).concat([['reg','⚖️ 규제 '+nreg]]);
  const mf=$('mw_mtype');
  if(mf){
    mf.innerHTML=MF.map(f=>{const t=T[f[0]];
      return `<button data-m="${f[0]}" title="${t?t.risk:''}" style="margin-right:5px;padding:2px 10px;border-radius:12px;border:1px solid ${MT===f[0]?(t?t.fg:'#334155'):'#d6d9de'};background:${MT===f[0]?(t?t.bg:'#334155'):'#fff'};color:${MT===f[0]?(t?t.fg:'#fff'):'#333'};cursor:pointer;font-size:11.5px">${f[1]}</button>`;}).join('');
    mf.querySelectorAll('button').forEach(b=>b.onclick=()=>{MT=b.dataset.m;render();});
  }

  // (Phase3) 오늘의 판정 전환 배너
  const chg=rows.filter(r=>r.vd_prev);
  const VE={buy:'🟢',wait:'🟡대기',alert:'🔴',nogate:'🚫',buy_z:'🟢~',buy_m:'🟢※',risk:'🔴(구)',watch:'관찰',top:'⚪',top_hot:'⚪🔥',top_warn:'⚪⚠'};
  // (2026-10-21) 🔴 해자 경보 상단 고정 배너 — 사용자 결정: 메일 없이 홈피 표시만. 사유(EPS·영업이익·OPM)를 함께 적는다.
  const al=D.alerts||[], lone=D.lone||[], ab=$('mw_alert');
  if(ab){
    const alH=al.length?`<b>🔴 해자 경보 ${al.length}종</b> — TTM EPS 전년比 2분기 연속 감소 + 영업이익 감소. <i>해자 해지 의심이지 매도 신호가 아니다 — 계약 인식 시점이 울퉁불퉁한 종목(센트러스류)은 오탐 가능, 사람이 확인할 것.</i><br>`+
      al.map(a=>`<span style="display:inline-block;margin:3px 10px 0 0;padding:2px 8px;background:#fff;border:1px solid #fecaca;border-radius:8px"><b>${a.name}</b> EPS ${pf(a.eps_yoy)}(${a.down_q}분기 연속) · 영업이익 ${pf(a.oi_yoy)}${a.opm!=null?` · OPM ${a.opm}%(${a.opm_chg!=null?(a.opm_chg>0?'+':'')+a.opm_chg+'%p':'—'})`:''}${a.since>1?` · D+${a.since}`:' · ⚡오늘'}</span>`).join('')
      :'<b>🔴 해자 경보 없음</b> — 51종 모두 이익 게이트 통과 또는 미확정';
    const loH=lone.length?`<div style="margin-top:5px"><b>⚠ 혼자 빠짐 ${lone.length}종</b> — 섹터 대리지표는 오르는데(3개월 ≥+5%) 자기역사 낙폭 하위 10%. 백테스트상 '섹터 동반 하락'보다 성적이 나빴던 유형 = 고유 사유 점검: `+
      lone.map(x=>`<b>${x.name}</b>(지표 ${pf(x.lead_m3)} vs 낙폭 하위 ${x.ddp3y}%)`).join(' · ')+'</div>':'';
    ab.innerHTML=alH+loH;
    ab.style.cssText=`margin-bottom:8px;padding:7px 10px;border-radius:8px;background:${al.length?'#fef2f2':'#f0fdf4'};border-left:4px solid ${al.length?'#b91c1c':'#16a34a'};font-size:12px`;
  }
  const bn=$('mw_chg');
  if(bn) bn.innerHTML=chg.length?`<b>⚡ 오늘의 전환</b> — ${chg.map(r=>`${r.name} ${VE[r.vd_prev]||r.vd_prev}→${VE[r.verdict]}`).join(' · ')}`
                               :'오늘 판정 전환 없음 — 신호등은 매일 06:30 재산출';
  let list=[...rows];
  if(MT==='reg') list=list.filter(r=>r.reg);
  else if(MT!=='all') list=list.filter(r=>(r.mtype||[]).indexOf(MT)>=0);
  if(FILT==='top') list=list.filter(r=>r.verdict.startsWith('top'));
  else if(FILT!=='all') list=list.filter(r=>r.verdict===FILT);
  // 정렬: 🟢 우선 → 낙폭 큰 순 (기회 후보가 맨 위)
  list.sort((a,b)=>((ORDER[a.verdict]??5)-(ORDER[b.verdict]??5))||((a.ddp3y??100)-(b.ddp3y??100)));

  $('mw_grid').innerHTML=list.map(r=>{
    const v=V[r.verdict]||V.watch;
    const dcol=r.dd==null?'#64748b':(r.dd<=-20?'#2563eb':r.dd<=-10?'#a16207':'#64748b');
    return `<div style="flex:1 1 340px;max-width:430px;border:1px solid #e2e8f0;border-top:3px solid ${v[2]};border-radius:10px;background:#fff;padding:10px 12px">
      <div style="display:flex;justify-content:space-between;align-items:center">
        <b style="font-size:14px">${r.name} <span style="font-size:10.5px;color:#94a3b8">${r.sym}</span>
          <span style="font-size:10.5px;background:#f1f5f9;color:#475569;border-radius:8px;padding:1px 7px;margin-left:3px">${mkt(r.sym)[0]} ${mkt(r.sym)[1]}</span></b>
        <span title="${v[4]}" style="background:${v[3]};color:${v[2]};border-radius:10px;padding:2px 9px;font-size:11.5px;font-weight:700">${v[0]} ${v[1]}${r.qh!=null?` <span style=\"font-weight:400;opacity:.85\">${r.qh}점</span>`:''}${r.vd_days>1?` <span style="font-weight:400;opacity:.8">D+${r.vd_days}</span>`:r.vd_prev?' <span style="font-weight:400">⚡오늘 전환</span>':''}</span></div>
      <div style="font-size:11px;color:#64748b;margin:3px 0 6px"><span style="background:#eef2ff;color:#4338ca;border-radius:8px;padding:1px 7px;margin-right:5px">${r.sec}</span>${r.tier==='B2+'?'<span title="관계도 배지는 황색(복점·양강)이나 해자 실질이 독점급이라 선별 편입" style="background:#fef3c7;color:#b45309;border-radius:8px;padding:1px 7px;margin-right:5px">선별 B2</span>':''}${mtBadges(r)}${r.moat}</div>
      ${r.reg?`<div style="font-size:10.5px;color:#b91c1c;background:#fef2f2;border-left:3px solid #b91c1c;padding:3px 7px;margin:0 0 5px">⚖️ 규제 리스크 — ${r.reg}</div>`:''}
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
      ${(function(){const f=r.fund||{}, g=f.gate||'na';
        const gc=g==='alert'?'#b91c1c':g==='down'?'#b45309':g==='ok'?'#166534':'#6b21a8';
        const gl=g==='alert'?'🔴 2분기 연속 감소+영업이익↓':g==='down'?(f.note?'⚠ '+f.note:'⚠ 1분기 감소'):g==='ok'?(f.note?'✓ 통과 ('+f.note+')':'✓ 이익 증가'):'🚫 적자·미확정';
        const mg=r.ddp3y!=null?`<b style="color:${r.ddp3y<=10?'#166534':'#334155'}">하위 ${r.ddp3y}%</b>`:'<span style="color:#94a3b8">이력 부족</span>';
        return `<div style="font-size:11px;margin-top:5px;display:flex;gap:6px;flex-wrap:wrap">
          <span title="① 해자 유지 게이트 — TTM EPS 전년 대비(영업이익으로 교차검증)" style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:6px;padding:1px 6px">① 이익 <b style="color:${gc}">${gl}</b>${f.eps_yoy!=null?` <span style="color:#64748b">EPS ${pf(f.eps_yoy)}${f.oi_yoy!=null?' · 영업이익 '+pf(f.oi_yoy):''}${f.opm!=null?' · OPM '+f.opm+'%':''}</span>`:''}</span>
          <span title="② 안전마진 — 오늘 낙폭이 이 종목의 최근 3년 낙폭 분포에서 어디인가(하위 10% 이하 = 자기 역사상 이례적)" style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:6px;padding:1px 6px">② 자기역사 낙폭 ${mg}</span>
          <span title="③ 멈춤 확인 — 종가 > 20일선" style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:6px;padding:1px 6px">③ 20일선比 <b style="color:${r.stop?'#166534':'#b45309'}">${pf(r.gap20)}</b>${r.stop?' 회복':' 하락중'}</span>
          ${r.lone?'<span style="background:#fff7ed;border:1px solid #fdba74;color:#9a3412;border-radius:6px;padding:1px 6px">⚠ 혼자 빠짐 — 고유 사유 점검</span>':''}</div>`;})()}
      <div style="font-size:11px;margin-top:6px;padding-top:6px;border-top:1px dashed #e2e8f0">
        ${r.lead?`🔗 섹터 대리지표 <b>${r.lead.name}</b> — 1개월 <span style="color:${pc(r.lead.m1)}">${pf(r.lead.m1)}</span> · 3개월 <b style="color:${pc(r.lead.m3)}">${pf(r.lead.m3)}</b> · 6개월 <span style="color:${pc(r.lead.m6)}">${pf(r.lead.m6)}</span> · 1년 <span style="color:${pc(r.lead.y1)}">${pf(r.lead.y1)}</span>`
                :'🔗 섹터 대리지표 미연결'}
        ${r.share?`<div style="color:#4338ca;margin-top:3px">📊 점유 추이 — ${r.share}</div>`:''}
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
