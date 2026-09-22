/* ── (2026-08-16) 🏗️ 청약 탭 — applyhome_sub.json (scripts/applyhome_list.py · 매일 07:58)
   namoobi 로그인 시에만 탭 노출(공공데이터라 서버 차단은 안 하고 UI만 가림 — visitors.js 패턴).
   신혼특공 추첨제·일반공급 추첨제 세대수(규칙 기반 추정) + 경쟁률·당첨가점·원본링크.
   app.js 와 파일을 분리한 이유: 부동산 카드 작업과 동시 수정 충돌을 피하기 위해. ── */
(function(){
  const $=id=>document.getElementById(id);
  const E=s=>String(s??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
  const tab=$('tab_sub'); if(!tab) return;
  /* (2026-09-04) 로그인 게이트 해제 — 누구나 보이게.
     원래 visitors.js 패턴을 따라 로그인 시에만 노출했는데, 세션이 풀리면 탭이 사라져
     '없어졌다'고 보였다. 청약홈(data.go.kr) 공공데이터라 가릴 이유가 없어 상시 공개로 바꾼다.
     (KIS 실계정을 쓰는 분봉·호가와 달리 서버 자원·유량 문제도 없다) */
  tab.style.display='';

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

  /* ── (2026-09-05) 🔭 분양예정 — applyhome_plan.json (주 1회 웹 리서치 · /namoobi-sub-plan)
     청약홈 API 는 '공고가 난 것'만 준다. 성남·판교처럼 공고가 뜸한 지역은 목록이 비어
     보여서, 공고 전 단계(재개발·재건축·공공택지 계획)를 따로 조사해 붙인다.
     보도·계획 기반이라 확정 공고와 성격이 다르므로 표·색을 분리하고 출처를 행마다 남긴다. ── */
  let _pd=null, _pband='전체';
  /* (2026-09-05) 📍 네이버지도 검색 링크 — 위치를 바로 확인하려는 용도.
     공급위치·사업지 주소는 '…355번지 외 13필지', '…686 일대 38만6364㎡' 처럼
     꼬리가 붙어 그대로 넣으면 검색이 안 잡힌다 → 지번까지만 남기고 자른다.
     주소가 너무 짧거나 없으면(구역명만 있는 계획 단계) 단지명으로 검색한다. */
  const mapQ=(addr,name)=>{
    let q=String(addr||'').replace(/\s*(일원|일대|외\s*\d+\s*필지|번지).*$/,'')
                          .replace(/\s*[\d,]+만?\s*[\d,]*㎡.*$/,'').trim();
    if(q.length<6) q=String(name||'').trim();
    return q?`https://map.naver.com/p/search/${encodeURIComponent(q)}`:null;
  };
  const mapLink=(addr,name)=>{const u=mapQ(addr,name);
    return u?` <a href="${E(u)}" target="_blank" rel="noopener" title="네이버지도에서 위치 보기" onclick="event.stopPropagation()">📍</a>`:'';};
  function renderPlan(){
    const root=$('sub_tbl'); if(!root) return;
    if(!_pd){ root.innerHTML='<div class="note">분양예정 자료를 불러오는 중…</div>'; return; }
    const rows=(_pd.items||[]).filter(i=>{
      if(_reg!=='전체'&&i.reg!==_reg) return false;
      if(_sgg!=='전체'&&(i.sgg||'')!==_sgg) return false;
      if(_pband!=='전체'&&i.band!==_pband) return false;
      if(_q&&!((i.name||'')+(i.addr||'')+(i.kind||'')+(i.note||'')).toLowerCase().includes(_q)) return false;
      return true;
    });
    const F=v=>v==null?'—':(typeof v==='number'?v.toLocaleString():E(v));
    const BC={'임박':'#b91c1c','2027':'#b45309','2028+':'#0e7490','미정':'#6b7280'};
    root.innerHTML=`<div class="note" style="margin-bottom:6px;line-height:1.6;background:#fffbeb;border:1px solid #fde68a;border-radius:6px;padding:7px 10px">
        ⚠ <b>공고 전 단계</b>입니다 — 언론 보도·지자체 계획 기반이라 <b>일정이 밀리는 일이 잦습니다</b>(서울 정비사업 336곳 중 실제 공사 중 32곳).
        일반분양 세대수·시기는 확정치가 아니며, 확정 정보는 입주자모집공고로 확인하세요. 행마다 <b>출처·보도일</b>을 달았습니다.</div>
      <table><thead><tr>
      <th>분양시기</th><th>사업명 <span class="note">(🔗=출처 기사 · 📍=네이버지도)</span></th><th>지역</th><th>구분</th>
      <th style="text-align:right">총세대</th><th style="text-align:right" title="일반분양 예상 세대 — 조합원분을 뺀 물량">일반분양</th>
      <th>사업단계</th><th>비고</th><th>출처</th></tr></thead><tbody>${
      rows.map(i=>`<tr>
        <td><b style="color:${BC[i.band]||'#333'}">${F(i.when)}</b></td>
        <td><b>${E(i.name)}</b>${i.src?` <a href="${E(i.src)}" target="_blank" rel="noopener" title="출처 기사 열기">🔗</a>`:''}${mapLink(i.addr,i.name)}
            ${i.addr?`<br><span class="note">${E(i.addr)}</span>`:''}</td>
        <td>${E(i.reg)} ${E(i.sgg||'')}</td><td>${F(i.kind)}</td>
        <td class="num">${F(i.total)}</td>
        <td class="num" style="color:#0f766e;font-weight:700">${F(i.gen)}</td>
        <td>${F(i.stage)}</td>
        <td class="note" style="max-width:420px;white-space:normal">${E(i.note||'')}${i.price?`<br><b>예상가:</b> ${E(i.price)}`:''}</td>
        <td class="note" style="white-space:nowrap">${E(i.srcname||'')}${i.asof?`<br>${E(i.asof)}`:''}</td></tr>`).join('')}</tbody></table>`;
    $('sub_cnt').textContent=`${rows.length}건`;
  }

  function render(){
    if(_st==='예정'){ renderPlan(); return; }
    if(_st==='줍줍'){ renderRem(); return; }
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
      <th>상태</th><th>단지명 <span class="note">(클릭=주택형 상세 · 🔗=청약홈 원문 · 📍=네이버지도)</span></th><th>지역</th>
      <th>유형</th><th style="text-align:right">총공급</th>
      <th style="text-align:right" title="일반공급 중 추첨제 추정 세대 (민영: 규제·면적별 20~100% · 국민: 20%)">일반추첨*</th>
      <th style="text-align:right" title="신혼부부 특공 배정 (괄호=30% 추첨 추정)">신혼특공*</th>
      <th style="text-align:right">분양가(억)</th>
      <th style="text-align:right" title="당첨 시 예상차익* = 같은 시군구 최근 6개월 실거래 ㎡당가(준공 15년 이내·유사면적 ±5㎡ 우선) × 전용 − 분양가(PDF 파싱 평균가 우선, 없으면 최고가 기준·보수적). 일반공급 세대수 가중평균 · 옵션비·층향 미반영 추정 · 실거래DB 수집 지역만 표시">예상차익*</th>
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
          <td><b>${E(i.name)}</b> <a href="${E(i.url||'#')}" target="_blank" rel="noopener" title="청약홈 공고 원문" onclick="event.stopPropagation()">🔗</a>${mapLink(i.addr,i.name)}</td>
          <td>${E(i.reg)}${i.sgg?' '+E(i.sgg):''}${reg}</td><td>${E(i.typ||'—')}</td>
          <td class="num">${F(i.sup)}</td>
          <td class="num" style="color:#0f766e;font-weight:700">${F(a.lot)}</td>
          <td class="num">${F(a.nw)}${a.nwlot?` <span class="note">(추첨 ${a.nwlot})</span>`:''}</td>
          <td class="num">${i.pr?(i.pr[0]===i.pr[1]?i.pr[0]:i.pr[0]+'~'+i.pr[1]):'—'}</td>
          <td class="num">${i.gain!=null?`<b style="color:${i.gain>=0?'#0f766e':'#b91c1c'}">${i.gain>0?'+':''}${i.gain}억</b>${i.gpct!=null?` <span class="note">(${i.gpct>0?'+':''}${i.gpct}%)</span>`:''}`:'—'}</td>
          <td>${F(i.sp_bg)}</td><td><b>${F(i.r1_bg)}</b></td><td>${F(i.prz)}</td>
          <td class="num">${r1!=null?fr1(r1):(s==='완료'?'<span class="note" style="cursor:help" title="청약홈 오픈API가 이 유형(신혼희망타운·공공 사전청약 등)의 경쟁률을 공표하지 않거나, 일반공급이 없는 공고 — 원문(🔗)에서 확인">미제공</span>':'—')}</td>
          <td class="num">${sc?sc[0]+'~'+sc[1]:'—'}</td><td>${i.mvn?String(i.mvn).slice(0,4)+'.'+String(i.mvn).slice(4):'—'}</td></tr>`;
        if(!_open[i.no]) return main;
        const det=`<tr><td colspan="15" style="background:#f8fafc;padding:8px 14px">
          <div class="note" style="margin-bottom:5px">${E(i.addr||'')} · 시행 ${E(i.biz||'—')} · 시공 ${E(i.cons||'—')} · 접수 ${E(i.r1_bg||'')}~${E(i.rc_ed||'')} · 계약해당 발표 ${E(i.prz||'—')}
            ${i.hmpg?` · <a href="${E(i.hmpg)}" target="_blank" rel="noopener">분양 홈페이지</a>`:''} · <a href="${E(i.url||'#')}" target="_blank" rel="noopener">청약홈 공고 원문 ↗</a></div>
          <table style="font-size:11.5px"><thead><tr><th>주택형</th><th style="text-align:right">전용㎡</th>
            <th style="text-align:right" title="최저~최고 (평균) — 최저·평균은 공고문 PDF의 층별 가격표를 자동 파싱한 값(파싱 최고가가 API 최고공급금액과 ±3% 일치할 때만 표시 · 병합표 특성상 근사치). 최고가만 있으면 PDF 미파싱(형식 상이·스캔본 등) — 원문(🔗) 확인">분양가(억)<br><span style="font-weight:400">최저~최고 (평균)</span></th>
            <th style="text-align:right" title="같은 시군구 최근 6개월 실거래 ㎡당가의 거래건수 가중 평균 × 전용 (최고값·중간값 아닌 평균값) — 준공 15년 이내·유사면적(±5㎡) 우선, † = 신축 표본 부족으로 전 연식 사용(보수적)">예상시세*(억)</th>
            <th style="text-align:right" title="예상시세 − 분양가. 기준: PDF 파싱 평균분양가가 있으면 평균(동·호수 추첨이라 기대값), 없으면 최고분양가(보수적 — 실제 차익은 이보다 클 수 있음). 옵션비·층향 미반영">차익*</th>
            <th style="text-align:right">일반</th><th style="text-align:right" title="일반공급 추첨 비율(추정) — 규제지역·수도권은 추첨물량의 75% 무주택 우선, 25%에 1주택자 참여">추첨*</th>
            <th style="text-align:right" title="1순위 경쟁률(가점제 낙첨자 포함)">1순위경쟁률</th>
            <th style="text-align:right" title="1순위 접수건수 ÷ 추첨제 추정물량 — 가점 낙첨자도 추첨에 들어가므로 추첨제 체감 경쟁률에 가까움 (1주택자 참고)">추첨환산*</th>
            <th style="text-align:right">특공계</th>
            <th style="text-align:right" title="각 특공 유형: 배정세대 (경쟁률 = 신청건수÷배정세대) · 특공은 전부 무주택세대 요건">신혼 <span class="note">(경쟁률)</span></th>
            <th style="text-align:right">신생아</th><th style="text-align:right">생애최초</th><th style="text-align:right">다자녀</th><th style="text-align:right">청년</th><th style="text-align:right">노부모</th>
            <th style="text-align:right" title="기관추천 — 국가유공자·장애인·중소기업 근로자 등, 해당 기관 추천을 받아야 신청 가능(일반 청약자는 대상 아님)">기관추천</th>
            <th style="text-align:right" title="이전기관 종사자 — 혁신도시 등 이전 공공기관 직원 대상">이전기관</th>
            <th style="text-align:right" title="위 유형에 잡히지 않은 잔여 특공 물량(합계를 특공계와 맞춘 값)">기타</th>
            <th style="text-align:right">가점(최저/평균/최고)</th></tr></thead><tbody>${
          (i.ty||[]).map(t=>{
            const sp=(n,r)=>n?`${n}${r!=null?` <span class="note">(${fr1(r)})</span>`:''}`:'—';
            const conv=(t.r1!=null&&t.lot)?t.r1*t.gen/t.lot:null;   // 추첨환산 = 1순위 접수 ÷ 추첨물량 (무주택·1주택 전체 평균)
            /* 1주택 환산 — 수도권·광역시·규제지역은 추첨물량 75%가 무주택 우선이라
               1주택자는 25%몫을 '75% 낙첨 무주택자 전원'과 함께 추첨:
               확률 ≈ 0.25L ÷ (접수 − 0.75L)  (무주택 신청 ≥ 75%물량 가정 — 통상 참) */
            const has75=i.spec==='Y'||i.mdat==='Y'||['서울','경기','인천','부산','대구','광주','대전','울산'].includes(i.reg);
            const conv1=(has75&&conv!=null&&t.r1*t.gen>0.75*t.lot)?(t.r1*t.gen-0.75*t.lot)/(0.25*t.lot):null;
            const bp=t.prav!=null?t.prav:t.pr;   // 차익 기준: 평균 분양가(파싱 시) > 최고가
            const gv=(t.est!=null&&bp!=null)?+(t.est-bp).toFixed(2):null;
            return `<tr><td>${E(t.t)}</td><td class="num">${F(t.ar)}</td>
            <td class="num">${t.prmn!=null?`${t.prmn}~${F(t.pr)}<br><span class="note">평균 ${t.prav}</span>`:F(t.pr)}</td>
            <td class="num">${t.est!=null?F(t.est)+(t.act?' <b style="color:#0f766e" title="추정이 아니라 이 단지 자체의 입주 후 실거래(최근 12개월) ㎡당가 기반 실측 시세 — 단지명·준공년 매칭">실측</b>':'')+(t.slv?' <b style="color:#7c3aed" title="이 단지 분양권 전매 실거래(최근 6개월, 프리미엄 반영) 가중평균 — 단지명·전용 ±3㎡ 매칭 실측">분양권</b>':'')+(t.cmp?` <span class="note" title="${t.dg?'같은 법정동':'같은 시군구'} 준공 10년 이내 신축 ${t.cmp}개 단지의 실거래만으로 계산(구축 평균 왜곡 제거)">신축${t.cmp}${t.dg?'·동':''}</span>`:'')+(t.estb?'<span title="신축 표본 부족 — 전 연식 실거래 ㎡당가 사용(보수적 추정)">†</span>':''):'—'}</td>
            <td class="num" style="font-weight:700;color:${gv>=0?'#0f766e':'#b91c1c'}">${gv!=null?(gv>0?'+':'')+gv+` <span class="note">(${Math.round(gv/bp*100)>0?'+':''}${Math.round(gv/bp*100)}%${t.prav!=null?' 평균가 기준':''})</span>`:'—'}</td>
            <td class="num">${F(t.gen)}</td><td class="num" style="color:#0f766e;font-weight:700">${t.lot?`${t.lot} <span class="note">(${t.pct}%)</span>`:'—'}</td>
            <td class="num">${t.r1!=null?fr1(t.r1)+(t.short?' <span title="1순위 미달" style="color:#b91c1c">미달</span>':''):'—'}</td>
            <td class="num" style="font-weight:700">${conv!=null?fr1(conv):'—'}${conv1!=null?`<br><span class="note" title="1주택자 체감 환산 = 25%물량 ÷ (1순위 접수 − 75%물량). 무주택자는 75% 우선 + 25% 재도전이라 평균(추첨환산)보다 유리, 1주택자는 이 값에 가깝다">1주택 ${fr1(conv1)}</span>`:''}</td>
            <td class="num">${F(t.spc)}</td>
            <td class="num">${sp(t.nw,t.nwr)}${t.nwlot?` <span class="note">추첨${t.nwlot}</span>`:''}</td>
            <td class="num">${sp(t.nb,t.nbr)}</td><td class="num">${sp(t.lf,t.lfr)}</td>
            <td class="num">${sp(t.my,t.myr)}</td><td class="num">${sp(t.yg,t.ygr)}</td><td class="num">${sp(t.op,t.opr)}</td>
            <td class="num">${sp(t.ir,t.irr)}</td><td class="num">${sp(t.tr,t.trr)}</td><td class="num">${t.ec?t.ec:'—'}</td>
            <td class="num">${t.sc?t.sc.join(' / '):'—'}</td></tr>`;}).join('')}</tbody></table>
          <div class="note" style="margin-top:4px">💡 <b>예상시세*</b>는 같은 시군구 최근 6개월 국토부 실거래 ㎡당가의 <b>거래건수 가중 평균</b>(최고값·중간값 아님 · 준공 15년 이내·유사면적 ±5㎡ 우선, †=전 연식) × 전용면적.
          <b>분양가 최저~최고(평균)</b>의 최저·평균은 공고문 PDF 층별 가격표를 자동 파싱한 값(API 최고가와 ±3% 일치 시에만 표시·근사치) — <b>차익*은 평균 분양가 기준</b>(동·호수 추첨이라 기대값, '평균가 기준' 표기), 평균이 없으면 최고가 기준(보수적). 최고가만 표시되면 PDF 형식이 달라 미파싱, 원문(🔗) 확인. <b>차익*</b> = 예상시세 − 최고분양가 — 분양가가 최고가(최상층) 기준이라 실제 차익은 이보다 클 수 있고, 옵션비·발코니 확장비·층향 차이는 미반영. 신축 프리미엄으로 실제 신축 시세는 주변 평균보다 높게 형성되는 경향도 참고. 실거래DB 수집 지역(서울·경기·광역시 등)만 표시.
          1순위 경쟁률 분모는 <b>일반공급 전체</b>(가점+추첨)다. 접수는 하나로 받고 가점제 배정 → 낙첨자 포함 추첨 순서라 '추첨제만의 공식 경쟁률'은 없다.
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
    const plan=(_st==='예정'), rem=(_st==='줍줍');
    // 예정 모드에선 시도 칩도 예정 자료 기준으로(서울·경기만 조사 대상)
    bar($('sub_reg'),['전체'].concat(plan?(_pd&&_pd.regions||[]):rem?(_rd&&_rd.sido||[]):(_d&&_d.sido||[])),_reg,
        v=>{_reg=v;_sgg='전체';_n=60;bars();render();});
    bar($('sub_st'),['모집중','발표대기','완료','전체','예정','줍줍'],_st,v=>{
      _st=v; _sgg='전체'; _n=60;
      if(v==='예정'&&!_pd){ initPlan(); return; }     // 첫 진입 시 로드 후 bars/render
      if(v==='줍줍'&&!_rd){ initRem(); return; }      // (2026-09-22) 무순위·잔여세대
      bars(); render();});
    // 유형(민영/국민) 대신 예정 모드에선 시기 구간 칩, 줍줍 모드에선 상태·종류 칩
    if(plan) bar($('sub_typ'),['전체'].concat(_pd&&_pd.bands||[]),_pband,v=>{_pband=v;_n=60;bars();render();});
    else if(rem) bar($('sub_typ'),['모집중','완료','전체','무순위','재공급','규제지역','비규제'],_rf,v=>{_rf=v;_n=60;bars();render();});
    else bar($('sub_typ'),['전체','민영','국민'],_typ,v=>{_typ=v;_n=60;bars();render();});
    // 2단계: 시도를 고르면 그 안의 구(광역시)·시군(도) 칩 — 건수 많은 순
    const el=$('sub_sgg');
    if(_reg==='전체'){ el.innerHTML=''; el.style.display='none'; }
    else{
      const cnt={};
      ((plan?_pd&&_pd.items:rem?_rd&&_rd.items:_d&&_d.items)||[]).forEach(i=>{ if(i.reg===_reg){ const g=i.sgg||'기타'; cnt[g]=(cnt[g]||0)+1; }});
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
  /* ── (2026-09-22) 🎯 줍줍 — applyhome_rem.json (scripts/applyhome_rem.py · 매일 08:02)
     청약홈 API 는 무순위/잔여세대를 별도 엔드포인트(getRemndrLttotPblancDetail)로 줘서
     일반 공고 목록엔 안 잡혔다(철산자이 더 헤리티지·브리에르 사례). 무순위·불법행위 재공급을
     따로 받아 분양가·예상시세·차익·자격(규칙)·접수일을 한 표로 보여준다. ── */
  let _rd=null, _rf='모집중';
  const rstat=i=>{
    const bg=i.sp_bg&&i.sp_bg<i.rc_bg?i.sp_bg:(i.rc_bg||i.sp_bg||'');
    if(bg&&bg>TODAY) return '접수예정';
    if(i.rc_ed&&i.rc_ed>=TODAY) return '접수중';
    if(i.prz&&i.prz>=TODAY) return '발표대기';
    return '완료';
  };
  function renderRem(){
    const root=$('sub_tbl'); if(!root) return;
    if(!_rd){ root.innerHTML='<div class="note">무순위·잔여세대 자료를 불러오는 중…</div>'; return; }
    const rows=(_rd.items||[]).filter(i=>{
      if(_reg!=='전체'&&i.reg!==_reg) return false;
      if(_sgg!=='전체'&&(i.sgg||'기타')!==_sgg) return false;
      const s=rstat(i);
      if(_rf==='모집중'&&s!=='접수예정'&&s!=='접수중'&&s!=='발표대기') return false;
      if(_rf==='완료'&&s!=='완료') return false;
      if(_rf==='무순위'&&i.secd!=='04') return false;
      if(_rf==='재공급'&&i.secd!=='06') return false;
      if(_rf==='규제지역'&&!i.regd) return false;
      if(_rf==='비규제'&&i.regd) return false;
      if(_q&&!((i.name||'')+(i.addr||'')).toLowerCase().includes(_q)) return false;
      return true;
    });
    rows.sort((a,b)=>(_rf==='모집중')
      ?String(a.rc_bg||a.de).localeCompare(String(b.rc_bg||b.de))
      :String(b.rc_bg||b.de).localeCompare(String(a.rc_bg||a.de)));
    const show=rows.slice(0,_n);
    const F=v=>v==null?'—':(typeof v==='number'?v.toLocaleString():E(v));
    const fr=v=>v==null?'—':(v>=100?Math.round(v).toLocaleString():v.toFixed(v>=10?1:2))+':1';
    root.innerHTML=`<div class="note" style="margin-bottom:6px;line-height:1.6;background:#fff7ed;border:1px solid #fed7aa;border-radius:6px;padding:7px 10px">
        🎯 <b>줍줍(무순위·잔여세대)</b> — 청약통장·가점 없이 추첨. <b>규제지역(서울 전역+경기 12곳, 10·15 대책)</b>은 <b>해당 지역 거주 무주택세대구성원</b>만(거주 범위가 시·군인지 시·도인지는 공고마다 다름 — 헤리티지는 경기도, 브리에르는 광명시),
        <b>비규제</b>는 성년이면 거주지·주택 소유 무관(2023.2.28~). <b>불법행위 재공급</b>은 최초 공고 자격 준용(해당 시·군 무주택). 당첨 시 규제지역 <b>재당첨 제한 10년</b>, 준공 단지는 계약 후 곧바로 <b>잔금 90%</b>(중도금 없음·LTV 50%·DSR).
        '차수'가 붙은 단지(3차·8차)는 여러 번 돌려도 안 팔린 곳 — 예상차익이 음수인 게 많다. 자격·실거주 의무는 반드시 원문(🔗) 확인.</div>
      <table><thead><tr>
      <th>상태</th><th>단지명 <span class="note">(클릭=주택형 상세 · 🔗=청약홈 원문 · 📍=네이버지도)</span></th><th>지역</th><th>종류</th>
      <th style="text-align:right">세대</th><th style="text-align:right">분양가(억)</th>
      <th style="text-align:right" title="예상시세 − 최고분양가 (세대수 가중). 시세 우선순위: 단지 자체 매매 실측 > 분양권 전매 실측 > 같은 동·시군구 준공 10년 이내 신축 실거래 ㎡당가 × 전용. 옵션·층향 미반영">예상차익*</th>
      <th title="규칙 기반 표시 — 확정은 공고 원문">자격(규칙)</th>
      <th>접수</th><th>발표</th><th>계약</th><th style="text-align:right" title="접수건수 ÷ 공급세대 (형별 가중) — 접수 마감 후">경쟁률</th><th>입주</th></tr></thead><tbody>${
      show.map(i=>{
        const s=rstat(i);
        let a=0,b=0;(i.ty||[]).forEach(t=>{if(t.rt!=null){const w=(t.gen||0)+(t.spc||0)||1;a+=t.rt*w;b+=w;}});
        const rt=b?a/b:null;
        const kind=i.secd==='06'?`<span style="color:#7c3aed;font-weight:700" title="불법전매·공급질서 교란 등으로 계약 취소된 세대를 사업주체가 재공급">재공급</span>`:'무순위';
        const main=`<tr data-no="${E(i.no)}" style="cursor:pointer" title="${E(i.addr||'')}">
          <td><b style="color:${SCOL[s]}">${s}</b></td>
          <td><b>${E(i.name)}</b> <a href="${E(i.url||'#')}" target="_blank" rel="noopener" title="청약홈 공고 원문" onclick="event.stopPropagation()">🔗</a>${mapLink(i.addr,i.name)}</td>
          <td>${E(i.reg)}${i.sgg?' '+E(i.sgg):''}${i.regd?'<span title="규제지역(투기과열·조정대상) — 해당 지역 거주 무주택만" style="color:#b91c1c;font-weight:700"> 규</span>':''}</td>
          <td>${kind}</td><td class="num">${F(i.sup)}</td>
          <td class="num">${i.pr?(i.pr[0]===i.pr[1]?i.pr[0]:i.pr[0]+'~'+i.pr[1]):'—'}</td>
          <td class="num">${i.gain!=null?`<b style="color:${i.gain>=0?'#0f766e':'#b91c1c'}">${i.gain>0?'+':''}${i.gain}억</b>${i.gpct!=null?` <span class="note">(${i.gpct>0?'+':''}${i.gpct}%)</span>`:''}`:'—'}</td>
          <td class="note" style="white-space:normal;max-width:260px;color:${i.regd||i.secd==='06'?'#b91c1c':'#0f766e'}">${E(i.elig||'')}</td>
          <td><b>${F(i.rc_bg)}</b>${i.rc_ed&&i.rc_ed!==i.rc_bg?`<br><span class="note">~${E(i.rc_ed)}</span>`:''}</td>
          <td>${F(i.prz)}</td><td>${F(i.ctr)}</td>
          <td class="num">${rt!=null?fr(rt):'—'}</td>
          <td>${i.mvn?String(i.mvn).slice(0,4)+'.'+String(i.mvn).slice(4):'—'}</td></tr>`;
        if(!_open[i.no]) return main;
        const det=`<tr><td colspan="13" style="background:#f8fafc;padding:8px 14px">
          <div class="note" style="margin-bottom:5px">${E(i.addr||'')} · 시행 ${E(i.biz||'—')} · 접수 ${E(i.rc_bg||'')}~${E(i.rc_ed||'')} · 발표 ${E(i.prz||'—')} · 계약 ${E(i.ctr||'—')}
            ${i.hmpg?` · <a href="${E(i.hmpg)}" target="_blank" rel="noopener">분양 홈페이지</a>`:''} · <a href="${E(i.url||'#')}" target="_blank" rel="noopener">청약홈 공고 원문 ↗</a></div>
          <table style="font-size:11.5px"><thead><tr><th>주택형</th><th style="text-align:right">전용㎡</th><th style="text-align:right">세대</th>
            <th style="text-align:right">최고분양가(억)</th><th style="text-align:right">예상시세*(억)</th><th style="text-align:right">차익*</th>
            <th style="text-align:right">접수</th><th style="text-align:right">경쟁률</th></tr></thead><tbody>${
          (i.ty||[]).map(t=>{const gv=(t.est!=null&&t.pr!=null)?+(t.est-t.pr).toFixed(2):null;
            return `<tr><td>${E(t.t)}</td><td class="num">${F(t.ar)}</td><td class="num">${F((t.gen||0)+(t.spc||0))}</td>
            <td class="num">${F(t.pr)}</td>
            <td class="num">${t.est!=null?F(t.est)+(t.act?' <b style="color:#0f766e" title="이 단지 자체의 최근 12개월 매매 실거래 ㎡당가 기반">실측</b>':'')+(t.slv?' <b style="color:#7c3aed" title="이 단지 분양권 전매 실거래(최근 6개월) 가중평균">분양권</b>':'')+(t.cmp?` <span class="note" title="${t.dg?'같은 법정동':'같은 시군구'} 준공 10년 이내 신축 ${t.cmp}개 단지 실거래">신축${t.cmp}${t.dg?'·동':''}</span>`:'')+(t.estb?'<span title="신축 표본 부족 — 전 연식 사용">†</span>':''):'—'}</td>
            <td class="num" style="font-weight:700;color:${gv>=0?'#0f766e':'#b91c1c'}">${gv!=null?(gv>0?'+':'')+gv+` <span class="note">(${Math.round(gv/t.pr*100)>0?'+':''}${Math.round(gv/t.pr*100)}%)</span>`:'—'}</td>
            <td class="num">${F(t.req)}</td><td class="num">${t.rt!=null?fr(t.rt)+(t.short?' <span style="color:#b91c1c">미달</span>':''):'—'}</td></tr>`;}).join('')}</tbody></table>
          <div class="note" style="margin-top:4px">💡 예상시세*는 단지 자체 매매 실측 → 분양권 전매 실측 → 같은 동·시군구 신축 실거래 순으로 잡는다. 최근 6~12개월에 그 단지 거래가 없으면 인근 신축 평균이라 실제와 차이가 날 수 있다(철산자이 더 헤리티지 59㎡는 2025.10·2026.02 전매 14억대가 있었으나 창 밖). 분양가는 최고가 기준(보수적).</div></td></tr>`;
        return main+det;
      }).join('')}</tbody></table>${
      rows.length>_n?`<div style="text-align:center;margin:8px 0"><button id="sub_more" style="padding:5px 16px;font-size:12px;border:1px solid #d7dce3;border-radius:6px;cursor:pointer;background:#fff">더 보기 (${_n}/${rows.length}건)</button></div>`:''}`;
    $('sub_cnt').textContent=`${rows.length}건`;
    root.querySelectorAll('tr[data-no]').forEach(tr=>tr.addEventListener('click',()=>{
      _open[tr.dataset.no]=!_open[tr.dataset.no]; render();}));
    const mb=$('sub_more'); if(mb) mb.onclick=()=>{_n+=60; render();};
  }
  function initRem(){
    $('sub_tbl').innerHTML='<div class="note">무순위·잔여세대 자료를 불러오는 중…</div>';
    fetch('/api/db/applyhome_rem').then(r=>r.ok?r.json():null).then(d=>{
      if(!d||!d.items){ $('sub_tbl').innerHTML='<div class="note">줍줍 자료 준비 중 — 다음 수집(매일 08:02)부터 표시됩니다.</div>'; return; }
      _rd=d; bars(); render();
    }).catch(()=>{ $('sub_tbl').innerHTML='<div class="note">줍줍 자료 불러오기 실패.</div>'; });
  }
  // 분양예정 자료는 '예정' 칩을 처음 누를 때만 받는다(평소엔 트래픽 0)
  function initPlan(){
    $('sub_tbl').innerHTML='<div class="note">분양예정 자료를 불러오는 중…</div>';
    fetch('/api/db/applyhome_plan').then(r=>r.ok?r.json():null).then(d=>{
      if(!d||!d.items){ $('sub_tbl').innerHTML='<div class="note">분양예정 자료 준비 중 — 주 1회(월요일) 갱신됩니다.</div>'; return; }
      _pd=d; bars(); render();
    }).catch(()=>{ $('sub_tbl').innerHTML='<div class="note">분양예정 자료 불러오기 실패.</div>'; });
  }
  tab.addEventListener('click',()=>{ init(); render(); });
})();
