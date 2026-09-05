/* exports.js — 📦 K-수출 탭 (2026-09-05 신설 · 사용자 요청)
   3.1.10(daily 탭 내부)의 세 블록을 전용 페이지로 승격 — 기존 3.1.10 은 그대로 둔다.
   데이터(신규 수집 없음 · 기존 DB 재사용):
     ① /api/db/customs   — 관세청 10일 단위 잠정치 (전체+10품목 · 1~10일/1~20일/월전체)
     ② /api/db/hs_invest — 투자 관점 품목별 월간 수출 (HS코드 · 3년 · 수주 이벤트 메모 포함)
   구성: ①요약 표 + 품목 칩 → 선택 품목 24개월 차트  ②테마 필터 칩 + HS 표(관련종목·수주 메모) */
(function(){
'use strict';
const $=id=>document.getElementById(id);
const E=s=>String(s??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
let CUS=null, HSI=null, CK='total', TH='전체', ch1=null, chH={};

const CUS_IT=[['total','전체'],['semiconductor','반도체'],['steel','철강'],['car','승용차'],['petroleum','석유'],
  ['wireless','무선통신'],['ship','선박'],['autoparts','자동차부품'],['computer','컴퓨터주변기기'],
  ['precision','정밀기기'],['appliance','가전제품']];
/* 품목→관련 종목 (app.js 3.1.10 HSI_REL 사본 — 관세청은 기업별 비공개라 수동 큐레이션) */
const REL={'3304':[['아모레퍼시픽','090430'],['LG생활건강','051900'],['코스맥스','192820'],['한국콜마','161890'],['실리콘투','257720']],
 '3305':[['LG생활건강','051900'],['아모레퍼시픽','090430']],'3303':[['신세계인터내셔날','031430'],['코스맥스','192820']],
 '8542':[['삼성전자','005930'],['SK하이닉스','000660']],'8541':[['서울반도체','046890'],['HD현대에너지솔루션','322000']],
 '8486':[['한미반도체','042700'],['주성엔지니어링','036930'],['원익IPS','240810']],
 '8507':[['LG에너지솔루션','373220'],['삼성SDI','006400'],['SK이노베이션','096770']],
 '2841+2825':[['에코프로머티','450080'],['포스코퓨처엠','003670']],'8703':[['현대차','005380'],['기아','000270']],
 '8708':[['현대모비스','012330'],['한온시스템','018880'],['HL만도','204320']],
 '3004':[['셀트리온','068270'],['한미약품','128940'],['유한양행','000100']],
 '3002':[['삼성바이오로직스','207940'],['셀트리온','068270'],['SK바이오사이언스','302440']],
 '9018':[['바텍','043150'],['아이센스','099190'],['인바디','041830']],'9021':[['덴티움','145720'],['디오','039840']],
 '8517':[['삼성전자','005930']],'8471':[['삼성전자','005930']],'8524':[['LG디스플레이','034220'],['삼성전자','005930']],
 '89':[['HD한국조선해양','009540'],['삼성중공업','010140'],['한화오션','042660']],
 '72':[['POSCO홀딩스','005490'],['현대제철','004020']],'2710':[['SK이노베이션','096770'],['S-Oil','010950'],['GS','078930']],
 '1902':[['농심','004370'],['삼양식품','003230'],['오뚜기','007310']],
 '2103':[['CJ제일제당','097950'],['대상','001680'],['삼양식품','003230']],
 '121221':[['CJ씨푸드','011150'],['사조씨푸드','014710']],'2202':[['롯데칠성','005300'],['LG생활건강','051900']],
 '2208':[['하이트진로','000080'],['롯데칠성','005300']],
 '88':[['한국항공우주','047810'],['한화에어로스페이스','012450'],['대한항공','003490']],
 '854232':[['SK하이닉스','000660'],['삼성전자','005930']],'870380':[['현대차','005380'],['기아','000270']],
 '300241':[['SK바이오사이언스','302440']],'300215':[['셀트리온','068270'],['삼성바이오로직스','207940']],
 '902129':[['덴티움','145720'],['디오','039840']],'9022':[['바텍','043150'],['뷰웍스','100120'],['레이','228670']],
 '330510':[['LG생활건강','051900'],['아모레퍼시픽','090430']],
 '8504':[['HD현대일렉트릭','267260'],['효성중공업','298040'],['LS일렉트릭','010120']],
 '8544':[['대한전선','001440'],['LS','006260']],'854142+854143':[['한화솔루션','009830'],['HD현대에너지솔루션','322000']],
 '8710':[['현대로템','064350'],['한화에어로스페이스','012450']],
 '93':[['한화에어로스페이스','012450'],['LIG넥스원','079550'],['풍산','103140']],
 '8543':[['에이피알','278470'],['클래시스','214150'],['원텍','336570']],'92':[['삼익악기','002450']]};
const _rel=hs=>((REL[hs]||[]).map(([n,c])=>
  `<a href="https://finance.naver.com/item/main.naver?code=${c}" target="_blank" style="white-space:nowrap">${E(n)}</a>`).join(' · '))||'—';
const fM=v=>v!=null?('$'+(v/1000).toLocaleString(undefined,{maximumFractionDigits:0})+'M'):'—';
const fY=y=>`<td class="num ${y>0?'up':(y<0?'dn':'')}">${y!=null?((y>0?'+':'')+y.toFixed(1)+'%'):'—'}</td>`;

/* ── ① 관세청 10일 잠정치 ─────────────────────────────────────────────── */
function renderCus(){
  const cs=CUS; if(!cs) return;
  const m=cs.months.slice(-24);
  const rmap={}; (cs.rows||[]).forEach(r=>{ rmap[r.yyyymm+'_'+r.seq]=r; });
  // 품목 칩
  $('ex_chips').innerHTML=CUS_IT.map(([k,lab])=>
    `<button data-k="${k}" class="scrrst" style="font-size:11.5px${k===CK?';background:#1e293b;color:#fff':''}">${lab}</button>`).join(' ');
  $('ex_chips').querySelectorAll('button').forEach(b=>b.onclick=()=>{CK=b.dataset.k;renderCus();});
  // 선택 품목 차트 (1~10/1~20/월전체)
  const seq=[1,2,3].map(sq=>m.map(mo=>{ const r=rmap[mo.replace('-','')+'_'+sq];
    const v=r?r[CK]:null; return v!=null?v/1000:null; }));
  if(ch1) ch1.destroy();
  ch1=new Chart($('ex_cv1'),{type:'bar',data:{labels:m,datasets:[
    {label:'1~10일',data:seq[0],backgroundColor:'#3b82f6'},
    {label:'1~20일',data:seq[1],backgroundColor:'#f59e0b'},
    {label:'월전체',data:seq[2],backgroundColor:'#dc2626'}]},
    options:{responsive:true,maintainAspectRatio:false,
      plugins:{legend:{labels:{boxWidth:12,font:{size:11}}}},
      scales:{x:{ticks:{maxTicksLimit:12,font:{size:10}}},y:{ticks:{font:{size:10},callback:v=>'$'+v.toLocaleString()+'M'}}}}});
  // 요약 표
  const P=['p10','p20','pm'],PN=['1~10일','1~20일','월전체'];
  $('ex_cus_tbl').innerHTML=`<tr><th style="text-align:left">품목</th>${PN.map(x=>`<th style="text-align:right">${x}</th>`).join('')}</tr>`+
    CUS_IT.map(([k,lab])=>`<tr style="${k===CK?'background:#eff6ff':''}"><td style="text-align:left;cursor:pointer" onclick="_exPick('${k}')"><b>${lab}</b></td>${P.map(p=>{const v=cs.latest[p]?.[k];
      return `<td class="num">${v!=null?(v/1000).toLocaleString(undefined,{maximumFractionDigits:0}):'—'}</td>`;}).join('')}</tr>`).join('')+
    `<tr><td colspan="4" class="note">${E(cs.latest.yyyymm)} 기준 · 백만 달러 · 행 클릭=차트 전환</td></tr>`;
}
window._exPick=k=>{CK=k;renderCus();};

/* ── ② 투자 관점 품목별 (HS코드 · 3년 · 수주 메모) ────────────────────── */
function renderHsi(){
  const hv=HSI; if(!hv||!hv.items) return;
  const ms=(hv.months||[]).slice(-36), off=hv.months.length-ms.length;
  const ths=['전체',...[...new Set(hv.items.map(r=>r.th))]];
  $('ex_th_chips').innerHTML=ths.map(t=>
    `<button data-t="${t}" class="scrrst" style="font-size:11.5px${t===TH?';background:#1e293b;color:#fff':''}">${E(t)}</button>`).join(' ');
  $('ex_th_chips').querySelectorAll('button').forEach(b=>b.onclick=()=>{TH=b.dataset.t;renderHsi();});
  Object.values(chH).forEach(c=>{try{c.destroy();}catch(e){}}); chH={};
  const _sum=(e,a,b)=>{ if(a<0) return null; const s=e.slice(a,b+1); return s.some(v=>v==null)?null:s.reduce((x,y)=>x+y,0); };
  const rows=hv.items.map((r,i)=>({r,i})).filter(x=>TH==='전체'||x.r.th===TH);
  $('ex_hsi_tbl').innerHTML=`<tr><th>테마</th><th>품목</th><th>HS</th><th>비고</th><th>관련 종목</th>
    <th style="text-align:right">최신월</th><th style="text-align:right">YoY</th>
    <th style="text-align:right">3개월</th><th style="text-align:right">3M YoY</th>
    <th style="text-align:right">1년</th><th style="text-align:right">1Y YoY</th>
    <th style="min-width:340px">월간 수출 (3년)</th></tr>`+
    rows.map(({r,i})=>{
      const e=(r.exp||[]).slice(off);
      let li=e.length-1; while(li>=0&&e[li]==null) li--;
      const last=li>=0?e[li]:null, yoy=(li>=12&&e[li-12])?(last/e[li-12]-1)*100:null;
      const s3=_sum(e,li-2,li), p3=_sum(e,li-14,li-12), y3=(s3!=null&&p3)?(s3/p3-1)*100:null;
      const s12=_sum(e,li-11,li), p12=_sum(e,li-23,li-12), y12=(s12!=null&&p12)?(s12/p12-1)*100:null;
      const evs=(hv.events||[]).filter(ev=>ev.hs===r.hs).map(ev=>
        `<tr style="background:#fffbeb"><td colspan="12" style="font-size:12px;padding:6px 10px;border-left:3px solid #f59e0b">
          📌 <b>${E(ev.d)}</b> ${E(ev.txt)}<br><span class="note" style="margin-left:20px">${E(ev.est||'')}</span></td></tr>`).join('');
      return `<tr><td><b>${E(r.th)}</b></td><td>${E(r.nm)}</td><td class="note">${E(r.hs)}</td>
        <td class="note" style="max-width:170px">${E(r.note||'')}</td>
        <td style="font-size:12px;max-width:190px">${_rel(r.hs)}</td>
        <td class="num">${fM(last)}</td>${fY(yoy)}
        <td class="num">${fM(s3)}</td>${fY(y3)}
        <td class="num">${fM(s12)}</td>${fY(y12)}
        <td><canvas id="ex_hsi_${i}" style="max-height:52px"></canvas></td></tr>`+evs;
    }).join('');
  rows.forEach(({r,i})=>{ const cv=$('ex_hsi_'+i); if(!cv) return;
    const e=(r.exp||[]).slice(off).map(v=>v!=null?v/1000:null);
    chH[i]=new Chart(cv,{type:'bar',data:{labels:ms,datasets:[{data:e,backgroundColor:'#dc2626'}]},
      options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}},
        scales:{x:{ticks:{maxTicksLimit:7,font:{size:9}}},y:{ticks:{font:{size:9}}}}}}); });
}

/* ── ③ K방산 수출 공식 (2026-09-05 · 이코노믹리뷰 커버스토리 실측 전재 · 분기 갱신) ──
   층 구분: 통관 통계(선적) ≠ 수출 실적(계약·방사청) ≠ 수주잔고(계약 누적) — 셋을 한 탭에.
   핵심 논점: 수출 공식이 '완제품 납품'에서 '현지생산×기술이전×정부원팀'으로 바뀌는 중 —
   대형 수주전 4연속 고배가 그 신호(성장 스토리의 반증 데이터로 병기). */
let DF_DONE=false;
function renderDefense(){
  if(DF_DONE||!$('ex_df_cv1')) return; DF_DONE=true;
  new Chart($('ex_df_cv1'),{type:'bar',data:{labels:['2021','2022','2023','2024','2025'],
    datasets:[{data:[47.7,69.6,79.1,96,120.5],backgroundColor:'#1e3a5f'}]},
    options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false},
      tooltip:{callbacks:{label:c=>c.raw+'조원'}}},scales:{x:{ticks:{font:{size:10}}},y:{ticks:{font:{size:10},callback:v=>v+'조'}}}}});
  new Chart($('ex_df_cv2'),{type:'bar',data:{labels:['2019','2020','2021','2022','2023','2024','2025'],
    datasets:[{data:[25,30,73,173,135,96,154],backgroundColor:'#b91c1c'}]},
    options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false},
      tooltip:{callbacks:{label:c=>'$'+c.raw+'억'}}},scales:{x:{ticks:{font:{size:10}}},y:{ticks:{font:{size:10},callback:v=>'$'+v+'억'}}}}});
  const card=(t,rows,bd)=>`<div style="flex:1;min-width:280px;border:1px solid #e2e8f0;border-left:4px solid ${bd};border-radius:8px;padding:10px 12px;background:#fff">
    <div style="font-size:12.5px;font-weight:700;margin-bottom:6px">${t}</div>
    <div style="font-size:12px;line-height:1.8">${rows.join('<br>')}</div></div>`;
  $('ex_df_cards').innerHTML=`<div style="display:flex;gap:10px;flex-wrap:wrap">
    ${card('📈 2Q26 — 역대 최대 분기',[
      '4사 합산 영업익 <b>1조 7,000억+</b> · 수주잔고 <b>120.5조</b>(4년 만에 2.5배)',
      '한화에어로 분기 영업익 <b>첫 1조 돌파</b>(1.37조) · 잔고 38.3조',
      '현대로템 잔고 30.4조 역대최대 · LIG 잔고 57% 수출 · KAI 매출 +41%',
      '<span class="note">수출 체질 전환: 한화 지상방산 잔고 수출비중 33%(22)→66%(23)→<b>75%</b>(2Q26)</span>'],'#1e3a5f')}
    ${card('📜 대형 계약 이력 (계약 기준)',[
      '한화: 폴란드 K9 364문 <b>6.6조</b> · 천무 288대 <b>12.6조</b>(3회) + 핀란드·에스토니아·이집트',
      '로템: 폴란드 K2 1차 4.5조 + 2차 <b>9조(단일 역대최대 · 현지생산 포함)</b>',
      'LIG: 천궁-II 중동 3연타 — UAE 4.1조(22)·사우디 4.25조(24)·이라크 3.7조(25)',
      'KAI: FA-50 폴란드 48대 4조 · 말레이시아 18대 1.2조 · 필리핀 12대 1조',
      '<span class="note">📌 미국 첫 진출(K9MH)은 위 93류 행 수주 메모 참조</span>'],'#0f766e')}
    ${card('⚠ 공식 변화 신호 — 대형 수주전 4연속 고배',[
      '캐나다 잠수함 <b>20조</b> → 獨 TKMS(26.7) · 폴란드 잠수함 8조 → 瑞 SAAB(25.11)',
      '루마니아 장갑차 6조 → 獨 라인메탈(26.5) · 프랑스 로켓 1조 → MBDA·사프란(26.6)',
      '유럽 방산 블록화 공식화 — NATO SYNC(산업계 협력 전략) · EU Readiness 2030 <b>1,290조</b> · GDP 5%(2035)',
      '<span class="note">새 공식: 패키지형 수출 × 현지 방산 생태계 구축 × 정부·기업 원팀 — 빠른 납기·가격만으론 부족. '
      +'현지거점: 한화 호주 H-ACE·폴란드 JV·UAE / 로템 폴란드 K2PL / LIG 인니·라인메탈 / KAI 폴란드 MRO</span>'],'#b45309')}
  </div>
  <div class="note" style="margin-top:8px">SIPRI 무기 수출 점유(한국 0.9→2.2%)는 📊 점유율 추이 탭 '글로벌 무기 수출' 배틀 · 실제 선적 흐름은 위 93류·8710 통관 행 참조. 출처: 이코노믹리뷰 2026-09 커버스토리·각사 IR·방위사업청 — 분기 갱신.</div>`;
}

function load(force){
  if(CUS&&HSI&&!force){ renderCus(); renderHsi(); renderDefense(); return; }
  $('ex_asof').textContent='불러오는 중…';
  Promise.all([
    fetch('/api/db/customs',{cache:'no-cache'}).then(r=>r.ok?r.json():null),
    fetch('/api/db/hs_invest',{cache:'no-cache'}).then(r=>r.ok?r.json():null)
  ]).then(([c,h])=>{
    CUS=(c&&c.data)||c; HSI=h;
    $('ex_asof').textContent='잠정치 '+((CUS&&CUS.latest&&CUS.latest.yyyymm)||'')+' · 품목별 수집 '+((h&&h.asof)||'');
    renderCus(); renderHsi(); renderDefense();
  }).catch(e=>{ $('ex_asof').textContent='로드 실패: '+e.message; });
}

window.renderExports=function(){ load(false); };
document.addEventListener('DOMContentLoaded',function(){
  const b=$('ex_reload'); if(b) b.onclick=()=>load(true);
});
})();
