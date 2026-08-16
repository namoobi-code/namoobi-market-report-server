/* ── (2026-08-16) 🏗️ 청약 탭 — applyhome_sub.json (scripts/applyhome_list.py · 매일 07:58)
   namoobi 로그인 시에만 탭 노출(공공데이터라 서버 차단은 안 하고 UI만 가림 — visitors.js 패턴).
   신혼특공 추첨제·일반공급 추첨제 세대수(규칙 기반 추정) + 경쟁률·당첨가점·원본링크.
   app.js 와 파일을 분리한 이유: 부동산 카드 작업과 동시 수정 충돌을 피하기 위해. ── */
(function(){
  const $=id=>document.getElementById(id);
  const E=s=>String(s??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
  const tab=$('tab_sub'); if(!tab) return;
  // 로그인 시에만 탭 노출 (재로그인 반영 위해 visitors.js 와 동일하게 포커스 시 재확인)
  const chk=()=>fetch('/api/auth/me').then(r=>r.json())
    .then(d=>{ tab.style.display=(d&&d.ok)?'':'none'; }).catch(()=>{});
  chk(); window.addEventListener('focus',chk);

  let _d=null,_reg='전체',_sgg='전체',_st='모집중',_typ='전체',_q='',_open={},_n=60;
  const TODAY=new Date(Date.now()-new Date().getTimezoneOffset()*60000).toISOString().slice(0,10);
  const stat=i=>{
    const bg=i.sp_bg&&i.sp_bg<i.r1_bg?i.sp_bg:(i.r1_bg||i.sp_bg||'');
    if(bg&&bg>TODAY) return '접수예정';
    if(i.rc_ed&&i.rc_ed>=TODAY) return '접수중';
    if(i.prz&&i.prz>=TODAY) return '발표대기';
    return '완료';
  };
  const SCOL={'접수예정':'#0e7490','접수중':'#b91c1c','발표대기':'#b45309','완료':'#6b7280'};
  // 공고 대표 1순위 경쟁률 = Σ(형별 경쟁률×일반세대)/Σ일반세대 (가중평균)
  const aggR1=i=>{let a=0,b=0;(i.ty||[]).forEach(t=>{if(t.r1!=null&&t.gen){a+=t.r1*t.gen;b+=t.gen;}});
    return b?a/b:null;};
  const scRange=i=>{const v=(i.ty||[]).filter(t=>t.sc).map(t=>t.sc);
    if(!v.length) return null; return [Math.min(...v.map(x=>x[0])),Math.max(...v.map(x=>x[2]))];};

  function render(){
    if(!_d){ init(); return; }
    const d=_d, root=$('sub_tbl'); if(!root) return;
    const rows=(d.items||[]).filter(i=>{
      if(_reg!=='전체'&&i.reg!==_reg) return false;
      if(_sgg!=='전체'&&(i.sgg||'기타')!==_sgg) return false;
      if(_typ!=='전체'&&(i.typ||'')!==_typ) return false;
      const s=stat(i);
      if(_st==='모집중'&&s!=='접수예정'&&s!=='접수중') return false;
      if(_st==='발표대기'&&s!=='발표대기') return false;
      if(_st==='완료'&&s!=='완료') return false;
      if(_q&&!((i.name||'')+(i.addr||'')+(i.cons||'')).toLowerCase().includes(_q)) return false;
      return true;
    });
    // 접수예정·접수중은 접수일 오름차순(임박 순), 나머지는 최신순
    rows.sort((a,b)=>(_st==='모집중')
      ?String(a.r1_bg||a.de).localeCompare(String(b.r1_bg||b.de))
      :String(b.r1_bg||b.de).localeCompare(String(a.r1_bg||a.de)));
    const show=rows.slice(0,_n);
    const F=v=>v==null?'—':(typeof v==='number'?v.toLocaleString():v);
    const fr1=v=>v==null?'—':(v>=100?Math.round(v).toLocaleString():v.toFixed(v>=10?1:2))+':1';
    root.innerHTML=`<table><thead><tr>
      <th>상태</th><th>단지명 <span class="note">(클릭=주택형 상세 · 🔗=청약홈 원문)</span></th><th>지역</th>
      <th>유형</th><th style="text-align:right">총공급</th>
      <th style="text-align:right" title="일반공급 중 추첨제 추정 세대 (민영: 규제·면적별 20~100% · 국민: 20%)">일반추첨*</th>
      <th style="text-align:right" title="신혼부부 특공 배정 (괄호=30% 추첨 추정)">신혼특공*</th>
      <th style="text-align:right">분양가(억)</th>
      <th>특공접수</th><th>1순위</th><th>발표</th>
      <th style="text-align:right" title="1순위 경쟁률 (형별 가중평균) — 접수 마감 후 표시">경쟁률</th>
      <th style="text-align:right" title="당첨가점 최저~최고 (해당지역 1순위)">가점</th><th>입주</th></tr></thead><tbody>${
      show.map(i=>{
        const s=stat(i), r1=aggR1(i), sc=scRange(i), a=i.agg||{};
        const reg=(i.spec==='Y'?'<span title="투기과열지구" style="color:#b91c1c;font-weight:700"> 투</span>':'')
                 +(i.mdat==='Y'?'<span title="조정대상지역" style="color:#b45309;font-weight:700"> 조</span>':'')
                 +(i.cap==='Y'?'<span title="분양가상한제" style="color:#0e7490;font-weight:700"> 상</span>':'');
        const main=`<tr data-no="${E(i.no)}" style="cursor:pointer" title="${E(i.addr||'')} · ${E(i.cons||'')}">
          <td><b style="color:${SCOL[s]}">${s}</b></td>
          <td><b>${E(i.name)}</b> <a href="${E(i.url||'#')}" target="_blank" rel="noopener" title="청약홈 공고 원문" onclick="event.stopPropagation()">🔗</a></td>
          <td>${E(i.reg)}${i.sgg?' '+E(i.sgg):''}${reg}</td><td>${E(i.typ||'—')}</td>
          <td class="num">${F(i.sup)}</td>
          <td class="num" style="color:#0f766e;font-weight:700">${F(a.lot)}</td>
          <td class="num">${F(a.nw)}${a.nwlot?` <span class="note">(추첨 ${a.nwlot})</span>`:''}</td>
          <td class="num">${i.pr?(i.pr[0]===i.pr[1]?i.pr[0]:i.pr[0]+'~'+i.pr[1]):'—'}</td>
          <td>${F(i.sp_bg)}</td><td><b>${F(i.r1_bg)}</b></td><td>${F(i.prz)}</td>
          <td class="num">${fr1(r1)}</td>
          <td class="num">${sc?sc[0]+'~'+sc[1]:'—'}</td><td>${i.mvn?String(i.mvn).slice(0,4)+'.'+String(i.mvn).slice(4):'—'}</td></tr>`;
        if(!_open[i.no]) return main;
        const det=`<tr><td colspan="14" style="background:#f8fafc;padding:8px 14px">
          <div class="note" style="margin-bottom:5px">${E(i.addr||'')} · 시행 ${E(i.biz||'—')} · 시공 ${E(i.cons||'—')} · 접수 ${E(i.r1_bg||'')}~${E(i.rc_ed||'')} · 계약해당 발표 ${E(i.prz||'—')}
            ${i.hmpg?` · <a href="${E(i.hmpg)}" target="_blank" rel="noopener">분양 홈페이지</a>`:''} · <a href="${E(i.url||'#')}" target="_blank" rel="noopener">청약홈 공고 원문 ↗</a></div>
          <table style="font-size:11.5px"><thead><tr><th>주택형</th><th style="text-align:right">전용㎡</th><th style="text-align:right">최고분양가(억)</th>
            <th style="text-align:right">일반</th><th style="text-align:right" title="일반공급 추첨 비율(추정) — 규제지역·수도권은 추첨물량의 75% 무주택 우선, 25%에 1주택자 참여">추첨*</th>
            <th style="text-align:right" title="1순위 경쟁률(가점제 낙첨자 포함)">1순위경쟁률</th>
            <th style="text-align:right" title="1순위 접수건수 ÷ 추첨제 추정물량 — 가점 낙첨자도 추첨에 들어가므로 추첨제 체감 경쟁률에 가까움 (1주택자 참고)">추첨환산*</th>
            <th style="text-align:right">특공계</th>
            <th style="text-align:right" title="각 특공 유형: 배정세대 (경쟁률 = 신청건수÷배정세대) · 특공은 전부 무주택세대 요건">신혼 <span class="note">(경쟁률)</span></th>
            <th style="text-align:right">신생아</th><th style="text-align:right">생애최초</th><th style="text-align:right">다자녀</th><th style="text-align:right">청년</th><th style="text-align:right">노부모</th>
            <th style="text-align:right">가점(최저/평균/최고)</th></tr></thead><tbody>${
          (i.ty||[]).map(t=>{
            const sp=(n,r)=>n?`${n}${r!=null?` <span class="note">(${fr1(r)})</span>`:''}`:'—';
            const conv=(t.r1!=null&&t.lot)?t.r1*t.gen/t.lot:null;   // 추첨환산 = 1순위 접수 ÷ 추첨물량 (무주택·1주택 전체 평균)
            /* 1주택 환산 — 수도권·광역시·규제지역은 추첨물량 75%가 무주택 우선이라
               1주택자는 25%몫을 '75% 낙첨 무주택자 전원'과 함께 추첨:
               확률 ≈ 0.25L ÷ (접수 − 0.75L)  (무주택 신청 ≥ 75%물량 가정 — 통상 참) */
            const has75=i.spec==='Y'||i.mdat==='Y'||['서울','경기','인천','부산','대구','광주','대전','울산'].includes(i.reg);
            const conv1=(has75&&conv!=null&&t.r1*t.gen>0.75*t.lot)?(t.r1*t.gen-0.75*t.lot)/(0.25*t.lot):null;
            return `<tr><td>${E(t.t)}</td><td class="num">${F(t.ar)}</td><td class="num">${F(t.pr)}</td>
            <td class="num">${F(t.gen)}</td><td class="num" style="color:#0f766e;font-weight:700">${t.lot?`${t.lot} <span class="note">(${t.pct}%)</span>`:'—'}</td>
            <td class="num">${t.r1!=null?fr1(t.r1)+(t.short?' <span title="1순위 미달" style="color:#b91c1c">미달</span>':''):'—'}</td>
            <td class="num" style="font-weight:700">${conv!=null?fr1(conv):'—'}${conv1!=null?`<br><span class="note" title="1주택자 체감 환산 = 25%물량 ÷ (1순위 접수 − 75%물량). 무주택자는 75% 우선 + 25% 재도전이라 평균(추첨환산)보다 유리, 1주택자는 이 값에 가깝다">1주택 ${fr1(conv1)}</span>`:''}</td>
            <td class="num">${F(t.spc)}</td>
            <td class="num">${sp(t.nw,t.nwr)}${t.nwlot?` <span class="note">추첨${t.nwlot}</span>`:''}</td>
            <td class="num">${sp(t.nb,t.nbr)}</td><td class="num">${sp(t.lf,t.lfr)}</td>
            <td class="num">${sp(t.my,t.myr)}</td><td class="num">${sp(t.yg,t.ygr)}</td><td class="num">${sp(t.op,t.opr)}</td>
            <td class="num">${t.sc?t.sc.join(' / '):'—'}</td></tr>`;}).join('')}</tbody></table>
          <div class="note" style="margin-top:4px">💡 1순위 경쟁률 분모는 <b>일반공급 전체</b>(가점+추첨)다. 접수는 하나로 받고 가점제 배정 → 낙첨자 포함 추첨 순서라 '추첨제만의 공식 경쟁률'은 없다.
          <b>추첨환산*</b>(접수÷추첨물량)은 무주택·1주택 구분 없는 <b>전체 평균</b> — 무주택자는 75% 우선+25% 재도전이라 이보다 유리, <b>1주택자는 아래 '1주택' 환산</b>(25%물량÷(접수−75%물량))이 체감에 가깝다.
          특공 경쟁률은 유형별 신청건수÷배정세대(청약홈 신청현황). 특공·무주택우선 75%는 무주택세대 전용 — 1주택자는 일반 추첨 25% 몫에만 참여.</div></td></tr>`;
        return main+det;
      }).join('')}</tbody></table>${
      rows.length>_n?`<div style="text-align:center;margin:8px 0"><button id="sub_more" style="padding:5px 16px;font-size:12px;border:1px solid #d7dce3;border-radius:6px;cursor:pointer;background:#fff">더 보기 (${_n}/${rows.length}건)</button></div>`:''}`;
    $('sub_cnt').textContent=`${rows.length}건`;
    root.querySelectorAll('tr[data-no]').forEach(tr=>tr.addEventListener('click',()=>{
      _open[tr.dataset.no]=!_open[tr.dataset.no]; render();}));
    const mb=$('sub_more'); if(mb) mb.onclick=()=>{_n+=60; render();};
  }

  function bar(el,list,cur,fn){
    el.innerHTML=list.map(v=>`<button data-v="${E(v)}" style="padding:3px 9px;font-size:11.5px;border:1px solid #d7dce3;border-radius:6px;cursor:pointer;background:${v===cur?'#1f2937':'#fff'};color:${v===cur?'#fff':'#333'}">${E(v)}</button>`).join('');
    el.querySelectorAll('button').forEach(b=>b.onclick=()=>fn(b.dataset.v));
  }
  function bars(){
    bar($('sub_reg'),['전체'].concat(_d.sido||[]),_reg,v=>{_reg=v;_sgg='전체';_n=60;bars();render();});
    bar($('sub_st'),['모집중','발표대기','완료','전체'],_st,v=>{_st=v;_n=60;bars();render();});
    bar($('sub_typ'),['전체','민영','국민'],_typ,v=>{_typ=v;_n=60;bars();render();});
    // 2단계: 시도를 고르면 그 안의 구(광역시)·시군(도) 칩 — 공고 수 많은 순
    const el=$('sub_sgg');
    if(_reg==='전체'){ el.innerHTML=''; el.style.display='none'; }
    else{
      const cnt={};
      (_d.items||[]).forEach(i=>{ if(i.reg===_reg){ const g=i.sgg||'기타'; cnt[g]=(cnt[g]||0)+1; }});
      const list=Object.keys(cnt).sort((a,b)=>cnt[b]-cnt[a]);
      el.style.display='flex';
      el.innerHTML=['전체'].concat(list).map(v=>`<button data-v="${E(v)}" style="padding:3px 9px;font-size:11.5px;border:1px solid #d7dce3;border-radius:6px;cursor:pointer;background:${v===_sgg?'#0f766e':'#fff'};color:${v===_sgg?'#fff':'#333'}">${E(v)}${v!=='전체'?` <span style="opacity:.65">${cnt[v]}</span>`:''}</button>`).join('');
      el.querySelectorAll('button').forEach(b=>b.onclick=()=>{_sgg=b.dataset.v;_n=60;bars();render();});
    }
  }
  let _init=false;
  function init(){
    if(_init) return; _init=true;
    fetch('/api/db/applyhome_sub').then(r=>r.ok?r.json():null).then(d=>{
      if(!d||!d.items){ $('sub_tbl').innerHTML='<div class="note">수집 대기 중 — 다음 수집(매일 07:58)부터 표시됩니다.</div>'; return; }
      _d=d;
      $('sub_asof').textContent=`수집 ${d.asof||''} · ${d.src||''} · 공고 ${d.items.length}건 (${d.since||''}~)`;
      const q=$('sub_q'); if(q) q.oninput=()=>{_q=q.value.trim().toLowerCase();_n=60;render();};
      bars(); render();
    }).catch(()=>{ $('sub_tbl').innerHTML='<div class="note">불러오기 실패 — 새로고침 해주세요.</div>'; });
  }
  tab.addEventListener('click',()=>{ init(); render(); });
})();
