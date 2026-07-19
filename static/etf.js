/* etf.js — ETF 스크리너 (2026-07-26 신설. 종목 스크리너 1단계의 컴팩트 독립판)
   데이터: /api/db/etf_pool (etf_pool.py 가 일 갱신)
   필터: 종목찾기·자산군(KR)/거래소(US)·가격·등락·AUM·거래대금·총보수·상장기간
         ·수익률 1M/3M/6M/1Y·변동성·200일선·고점比·분배율·괴리율(KR)·레버리지 제외·월배당(KR) */
(function(){
  const $=i=>document.getElementById(i);
  if(!$('p_etf')) return;
  const E=t=>String(t??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
  const wonF=v=>v==null?'—':(v>=1e12?(v/1e12).toFixed(v>=1e13?0:1)+'조':(v>=1e8?Math.round(v/1e8).toLocaleString()+'억':Math.round(v).toLocaleString()));
  const usdF=v=>v==null?'—':(v>=1e9?'$'+(v/1e9).toFixed(v>=1e10?0:1)+'B':(v>=1e6?'$'+(v/1e6).toFixed(0)+'M':'$'+Math.round(v).toLocaleString()));

  let POOL={kr:[],us:[]}, loaded=false, mkt='kr', sort={k:'cap',d:-1};
  let findQ='', findOpen=false, findCaret=null, findIME=false;

  /* ── 필터 정의 (min/max 는 표시 단위) ── */
  const pct0=v=>(v>=0?'+':'')+v.toFixed(0)+'%';
  const DEF={
    kr:{
      asset:{label:'자산군',cat:1,opts:['국내지수','업종·테마','파생','해외주식','원자재','채권','기타']},
      px:{label:'가격',fmt:v=>Math.round(v).toLocaleString()+'원',min:1,presets:[['전체',null],['1,000원 ↑',1000],['5,000원 ↑',5000],['1만원 ↑',10000]],def:[null,null]},
      chg:{label:'등락',fmt:v=>v.toFixed(1)+'%',presets:[['전체',null,null],['상승(0% ↑)',0,null],['+2% ↑',2,null],['하락(0% ↓)',null,0],['−2% ↓',null,-2]],def:[null,null]},
      cap:{label:'AUM',fmt:wonF,min:1,presets:[['전체',null],['1조 ↑',1e12],['3,000억 ↑',3e11],['500억 ↑',5e10],['100억 ↑',1e10]],def:[5e10,null]},
      tv:{label:'거래대금',fmt:wonF,min:1,presets:[['전체',null],['100억 ↑',1e10],['10억 ↑',1e9],['1억 ↑',1e8]],def:[1e8,null]},
      fee:{label:'총보수',fmt:v=>v.toFixed(2)+'%',reqData:1,presets:[['전체',null,null],['0.1% ↓',null,0.1],['0.3% ↓',null,0.3],['0.5% ↓',null,0.5]],def:[null,null]},
      yr:{label:'상장기간',fmt:v=>v+'년',min:1,presets:[['전체',null],['1년 ↑',1],['3년 ↑',3],['5년 ↑',5]],def:[null,null]},
      r1m:{label:'수익률 1M',fmt:pct0,min:1,reqData:1,presets:[['전체',null],['0% ↑',0],['5% ↑',5],['10% ↑',10]],def:[null,null]},
      r3m:{label:'수익률 3M',fmt:pct0,min:1,reqData:1,presets:[['전체',null],['0% ↑',0],['10% ↑',10],['20% ↑',20]],def:[null,null]},
      r6m:{label:'수익률 6M',fmt:pct0,min:1,reqData:1,presets:[['전체',null],['0% ↑',0],['15% ↑',15],['30% ↑',30]],def:[null,null]},
      r1y:{label:'수익률 1Y',fmt:pct0,min:1,reqData:1,presets:[['전체',null],['0% ↑',0],['20% ↑',20],['50% ↑',50]],def:[null,null]},
      vol20:{label:'변동성(20일)',fmt:v=>v.toFixed(1)+'%',reqData:1,presets:[['전체',null,null],['1% ↓(안정)',null,1],['2% ↓',null,2],['3% ↑(고변동)',3,null]],def:[null,null]},
      v200:{label:'200일선',fmt:pct0,min:1,reqData:1,presets:[['전체',null],['위(0%) ↑',0],['−10% ↑',-10],['+10% ↑',10]],def:[null,null]},
      hi:{label:'고점比',fmt:v=>'고점 '+v.toFixed(0)+'%',min:1,reqData:1,presets:[['전체',null],['-5% 이내',-5],['-10% 이내',-10],['-20% 이내',-20]],def:[null,null]},
      divy:{label:'분배율',fmt:v=>v.toFixed(1)+'%',min:1,reqData:1,presets:[['전체',null],['1% ↑',1],['3% ↑',3],['5% ↑',5],['8% ↑',8]],def:[null,null]},
      dev:{label:'괴리율',fmt:v=>(v>=0?'+':'')+v.toFixed(2)+'%',reqData:1,presets:[['전체',null,null],['±0.5% 이내',-0.5,0.5],['±1% 이내',-1,1],['저평가(0% ↓)',null,0]],def:[null,null]},
      lev:{label:'레버리지·인버스',tgl:1,def:false,tglLabel:'레버리지·인버스 제외'},
      md:{label:'월배당',tgl:1,def:false,tglLabel:'월배당(월분배)만'}
    },
    us:{
      asset:{label:'거래소',cat:1},
      px:{label:'가격',fmt:v=>'$'+v.toFixed(2),min:1,presets:[['전체',null],['$5 ↑',5],['$20 ↑',20],['$50 ↑',50]],def:[null,null]},
      chg:{label:'등락',fmt:v=>v.toFixed(1)+'%',presets:[['전체',null,null],['상승(0% ↑)',0,null],['+2% ↑',2,null],['하락(0% ↓)',null,0],['−2% ↓',null,-2]],def:[null,null]},
      cap:{label:'AUM',fmt:usdF,min:1,presets:[['전체',null],['$10B ↑',1e10],['$1B ↑',1e9],['$100M ↑',1e8]],def:[1e8,null]},
      tv:{label:'거래대금',fmt:usdF,min:1,presets:[['전체',null],['$50M ↑',5e7],['$5M ↑',5e6],['$1M ↑',1e6]],def:[1e6,null]},
      fee:{label:'총보수',fmt:v=>v.toFixed(2)+'%',reqData:1,presets:[['전체',null,null],['0.1% ↓',null,0.1],['0.3% ↓',null,0.3],['0.75% ↓',null,0.75]],def:[null,null]},
      yr:{label:'상장기간',fmt:v=>v+'년',min:1,presets:[['전체',null],['1년 ↑',1],['3년 ↑',3],['5년 ↑',5]],def:[null,null]},
      r1m:{label:'수익률 1M',fmt:pct0,min:1,reqData:1,presets:[['전체',null],['0% ↑',0],['5% ↑',5],['10% ↑',10]],def:[null,null]},
      r3m:{label:'수익률 3M',fmt:pct0,min:1,reqData:1,presets:[['전체',null],['0% ↑',0],['10% ↑',10],['20% ↑',20]],def:[null,null]},
      r6m:{label:'수익률 6M',fmt:pct0,min:1,reqData:1,presets:[['전체',null],['0% ↑',0],['15% ↑',15],['30% ↑',30]],def:[null,null]},
      r1y:{label:'수익률 1Y',fmt:pct0,min:1,reqData:1,presets:[['전체',null],['0% ↑',0],['20% ↑',20],['50% ↑',50]],def:[null,null]},
      vol20:{label:'변동성(20일)',fmt:v=>v.toFixed(1)+'%',reqData:1,presets:[['전체',null,null],['1% ↓(안정)',null,1],['2% ↓',null,2],['3% ↑(고변동)',3,null]],def:[null,null]},
      v200:{label:'200일선',fmt:pct0,min:1,reqData:1,presets:[['전체',null],['위(0%) ↑',0],['−10% ↑',-10],['+10% ↑',10]],def:[null,null]},
      hi:{label:'고점比',fmt:v=>'고점 '+v.toFixed(0)+'%',min:1,reqData:1,presets:[['전체',null],['-5% 이내',-5],['-10% 이내',-10],['-20% 이내',-20]],def:[null,null]},
      divy:{label:'분배율',fmt:v=>v.toFixed(1)+'%',min:1,reqData:1,presets:[['전체',null],['1% ↑',1],['3% ↑',3],['5% ↑',5],['8% ↑',8]],def:[null,null]},
      dev:{label:'괴리율',fixed:'— (US 미제공)'},
      lev:{label:'레버리지·인버스',tgl:1,def:false,tglLabel:'레버리지·인버스 제외'},
      md:{label:'월배당',fixed:'— (US 미제공)'}
    }
  };
  const KEYS=['asset','px','chg','cap','tv','fee','yr','r1m','r3m','r6m','r1y','vol20','v200','hi','divy','dev','lev','md'];
  let F_ST={};
  const buildF=()=>{const o={},d=DEF[mkt];
    for(const k of KEYS){const f=d[k]; if(!f||f.fixed!==undefined)continue;
      if(f.tgl)o[k]={on:f.def}; else if(f.cat)o[k]={v:null}; else o[k]={min:f.def[0],max:f.def[1]};}
    return o;};
  let F=null;
  const loadF=()=>{ if(!F_ST[mkt]) F_ST[mkt]=buildF(); F=F_ST[mkt]; };

  /* 값 접근 (표시 단위로) — fraction 저장 필드는 ×100 */
  function val(r,k){
    switch(k){
      case 'px': return r.px; case 'chg': return r.chg;
      case 'cap': return r.cap; case 'tv': return r.tv;
      case 'fee': return r.fee; case 'divy': return r.divy; case 'dev': return r.dev;
      case 'yr': return r.yr?new Date().getFullYear()-r.yr:null;
      case 'r1m': case 'r3m': case 'r6m': case 'r1y': case 'v200': case 'hi':
        return r[k]!=null?r[k]*100:null;
      case 'vol20': return r.vol20;
      case 'asset': return mkt==='kr'?r.asset:r.exch;
    }
    return r[k];
  }
  function pass(r){ const d=DEF[mkt];
    if(findQ){ const q=findQ.toLowerCase();
      if(!String(r.n||'').toLowerCase().includes(q)&&!String(r.c||'').toLowerCase().includes(q)) return false; }
    for(const k in F){ const f=d[k], st=F[k]; if(!f) continue;
      if(f.tgl){ if(!st.on) continue;
        if(k==='lev' && r.lev) return false;
        if(k==='md' && !r.md) return false;
        continue; }
      if(f.cat){ if(st.v!=null && String(val(r,k)||'')!==st.v) return false; continue; }
      const v=val(r,k);
      if(v==null){ if(f.reqData&&(st.min!=null||st.max!=null)) return false; continue; }
      if(st.min!=null&&v<st.min) return false;
      if(st.max!=null&&v>st.max) return false; }
    return true;
  }

  /* ── 전부전체 (모든 필터를 '전체'로) ── */
  function clearF(){ const o={},d=DEF[mkt];
    for(const k of KEYS){const f=d[k]; if(!f||f.fixed!==undefined)continue;
      if(f.tgl)o[k]={on:false}; else if(f.cat)o[k]={v:null}; else o[k]={min:null,max:null};}
    return o;}

  /* ── 컬럼 관리 (종목 스크리너와 동일 UX, localStorage 저장) ── */
  const CDEF={  // 표 컬럼 정의 (라벨·숫자여부·시장) — 모든 필터가 컬럼이 되도록 전체 수록
    n:{l:'종목',n:0,m:'both'}, asset:{l:'자산군',n:0,m:'kr'}, exch:{l:'거래소',n:0,m:'us'},
    px:{l:'가격',n:1,m:'both'}, chg:{l:'등락',n:1,m:'both'}, cap:{l:'AUM',n:1,m:'both'},
    tv:{l:'거래대금',n:1,m:'both'}, fee:{l:'총보수',n:1,m:'both'}, dev:{l:'괴리율',n:1,m:'kr'},
    divy:{l:'분배율',n:1,m:'both'}, r1m:{l:'수익률 1M',n:1,m:'both'}, r3m:{l:'수익률 3M',n:1,m:'both'},
    r6m:{l:'수익률 6M',n:1,m:'both'}, r1y:{l:'수익률 1Y',n:1,m:'both'}, vol20:{l:'변동성(20일)',n:1,m:'both'},
    v200:{l:'200일선',n:1,m:'both'}, hi:{l:'고점比',n:1,m:'both'}, yr:{l:'상장기간',n:1,m:'both'},
    lev:{l:'레버리지',n:0,m:'both'}, md:{l:'월배당',n:0,m:'kr'}
  };
  const CORDER=['n','asset','exch','px','chg','cap','tv','fee','dev','divy','r1m','r3m','r6m','r1y','vol20','v200','hi','yr','lev','md'];
  const cAvail=k=>{const m=(CDEF[k]||{}).m; return m==='both'||m===mkt;};
  const CDEFAULT={
    kr:['n','asset','px','chg','cap','tv','fee','dev','divy','r1m','r3m','r6m','r1y','vol20','v200','hi','yr'],
    us:['n','exch','px','chg','cap','tv','fee','divy','r1m','r3m','r6m','r1y','vol20','v200','hi','yr']
  };
  let COLST={kr:CDEFAULT.kr.slice(),us:CDEFAULT.us.slice()};
  const CKEY='nmr_etfcols_v1'; let colsSaved=false;
  const saveCols=()=>{try{localStorage.setItem(CKEY,JSON.stringify(COLST));colsSaved=true;}catch(e){}};
  const clearCols=()=>{try{localStorage.removeItem(CKEY);}catch(e){}colsSaved=false;};
  (function loadCols(){try{const raw=localStorage.getItem(CKEY); if(!raw)return;
    const d=JSON.parse(raw); if(!d||!Array.isArray(d.kr)||!Array.isArray(d.us))return;
    const kr=d.kr.filter(k=>CDEF[k]),us=d.us.filter(k=>CDEF[k]);
    if(kr.length&&us.length){COLST={kr,us};colsSaved=true;}}catch(e){}})();
  let colOpen=false;
  function toggleColPanel(f){ colOpen = f!=null?f:!colOpen;
    const p=$('etf_colpanel'); if(p) p.style.display=colOpen?'':'none'; if(colOpen) renderColPanel(); }
  function mvCol(k,d){const a=COLST[mkt],i=a.indexOf(k),j=i+d; if(i<0||j<0||j>=a.length)return;
    a.splice(j,0,a.splice(i,1)[0]); saveCols(); applyTable(); renderColPanel();}
  function renderColPanel(){
    const p=$('etf_colpanel'); if(!p) return;
    const cur=COLST[mkt].filter(cAvail);
    const rest=CORDER.filter(k=>cAvail(k)&&cur.indexOf(k)<0);
    p.innerHTML=`<div class="cp-h"><b>표시 컬럼</b><span class="note">체크로 표시/숨김 · ▲▼로 순서</span>
        <span class="cp-badge">${colsSaved?'💾 저장됨':'기본값'}</span>
        <button class="cp-x" id="ecp_reset">컬럼 초기화(default)</button><button class="cp-x" id="ecp_all">전부체크</button><button class="cp-x" id="ecp_none">전부해제</button><button class="cp-x" id="ecp_close">닫기</button></div>
      <div class="cp-sec">표시 중 (${cur.length})</div><div class="cp-list">`+
      cur.map((k,i)=>`<div class="cp-it"><label><input type="checkbox" data-ecoff="${k}" checked ${k==='n'?'disabled':''}>${E(CDEF[k].l)}</label>
        <span class="cp-mvs"><button class="cp-mv" data-eup="${k}" ${i===0?'disabled':''}>▲</button><button class="cp-mv" data-edn="${k}" ${i===cur.length-1?'disabled':''}>▼</button></span></div>`).join('')+
      `</div><div class="cp-sec">추가 가능 (${rest.length})</div><div class="cp-list">`+
      (rest.map(k=>`<div class="cp-it"><label><input type="checkbox" data-econ="${k}">${E(CDEF[k].l)}</label></div>`).join('')||'<div class="note" style="padding:4px 2px">모두 표시 중</div>')+`</div>`;
    p.querySelectorAll('[data-ecoff]').forEach(c=>c.onchange=()=>{COLST[mkt]=COLST[mkt].filter(x=>x!==c.dataset.ecoff);saveCols();applyTable();renderColPanel();});
    p.querySelectorAll('[data-econ]').forEach(c=>c.onchange=()=>{COLST[mkt]=COLST[mkt].concat([c.dataset.econ]);saveCols();applyTable();renderColPanel();});
    p.querySelectorAll('[data-eup]').forEach(b=>b.onclick=()=>mvCol(b.dataset.eup,-1));
    p.querySelectorAll('[data-edn]').forEach(b=>b.onclick=()=>mvCol(b.dataset.edn,1));
    $('ecp_reset').onclick=()=>{COLST={kr:CDEFAULT.kr.slice(),us:CDEFAULT.us.slice()};clearCols();applyTable();renderColPanel();};
    $('ecp_all').onclick=()=>{const c=COLST[mkt].filter(cAvail);COLST[mkt]=c.concat(CORDER.filter(k=>cAvail(k)&&c.indexOf(k)<0));saveCols();applyTable();renderColPanel();};
    $('ecp_none').onclick=()=>{COLST[mkt]=['n'];saveCols();applyTable();renderColPanel();};
    $('ecp_close').onclick=()=>toggleColPanel(false);
  }

  /* ── 필터 설명 ── */
  function legendHTML(){
    const KR=mkt==='kr';
    const g=[
      ['종목찾기','종목명·코드 부분일치 (표 안에서 특정 ETF 찾기)'],
      [KR?'자산군':'거래소', KR?'국내지수·업종테마·파생·해외주식·원자재·채권·기타(네이버 탭 분류)':'상장 거래소(NYSE Arca·Nasdaq 등)'],
      ['가격','현재가'], ['등락','전일 대비 등락률'],
      ['AUM','순자산총액(운용 규모) — 클수록 유동성·안정성'],
      ['거래대금',KR?'최근 거래대금(백만원 환산)':'3개월 평균 거래대금'],
      ['총보수','연 운용보수(TER) — 낮을수록 장기 유리'],
      ['상장기간','상장 후 경과 연수'],
      ['수익률 1M·3M·6M·1Y','해당 기간 가격 수익률'],
      ['변동성(20일)','최근 20일 일간수익률 표준편차 — 낮을수록 안정'],
      ['200일선','200일 이동평균 대비 현재가'],
      ['고점比','52주 최고가 대비 현재가 (−5% = 고점 근접)'],
      ['분배율','분배금(배당) 수익률 TTM'],
    ];
    if(KR) g.push(
      ['괴리율','시장가 vs 실시간 NAV(iNAV) — +면 비싸게(고평가) 사는 것. ±0.5% 이내가 정상'],
      ['레버리지·인버스','2X·인버스 등 파생 ETF (토글로 제외 가능)'],
      ['월배당','월분배(월배당) ETF 만 필터']);
    else g.push(['괴리율·월배당','미국 미제공 (Yahoo 데이터에 iNAV·분배주기 없음)'],
      ['레버리지·인버스','이름 기반 판별 (3X·Inverse 등, 토글로 제외)']);
    return `<div class="note" style="margin-bottom:8px">ETF 전종목(${KR?'네이버':'Yahoo'})을 필터로 실시간 압축한다. 1단계 하드컷 방식(2·3단계 없음).</div>`
      +`<div class="lgcols">`+g.map(x=>`<div class="lgit"><b>${x[0]}</b> = ${E(x[1])}</div>`).join('')+`</div>`;
  }
  let legOpen=false;
  function toggleLegend(f){ legOpen=f!=null?f:!legOpen;
    const p=$('etf_glspanel'); if(p){ p.style.display=legOpen?'':'none'; if(legOpen) p.querySelector('.lgbody').innerHTML=legendHTML(); } }

  /* ── 칩 렌더 ── */
  const chipLabel=k=>{const f=DEF[mkt][k],st=F[k]||{};
    if(f.fixed!==undefined) return `${f.label}: <span class="cv">${E(f.fixed)}</span>`;
    if(f.tgl) return `${f.label}: <span class="cv">${st.on?'ON':'OFF'}</span>`;
    if(f.cat) return `${f.label}: <span class="cv">${E(st.v||'전체')}</span>`;
    const a=st.min!=null?f.fmt(st.min):null,b=st.max!=null?f.fmt(st.max):null;
    let t='전체'; if(a&&b)t=`${a}~${b}`; else if(a)t=`${a} ↑`; else if(b)t=`${b} ↓`;
    return `${f.label}: <span class="cv">${t}</span>`;};
  const catOpts=k=>{const f=DEF[mkt][k]; if(f.opts) return ['',...f.opts];
    const s=new Set(); for(const r of POOL[mkt]) {const v=val(r,k); if(v)s.add(String(v));}
    return ['',...[...s].sort()];};
  function findChipHTML(){
    return findOpen
      ? `<div class="fchip"><span class="findbox">🔎<input id="efind_in" placeholder="종목명 · 코드" value="${E(findQ)}" autocomplete="off" spellcheck="false"><button id="efind_x">✕</button></span></div>`
      : `<div class="fchip"><button class="${findQ?'act':''}" id="efind_btn">🔎 종목: <span class="cv">${findQ?E(findQ):'전체'}</span></button></div>`;
  }
  function renderChips(){
    if(findOpen&&findIME) return;
    const d=DEF[mkt];
    const parts=KEYS.map(k=>{const f=d[k]; if(!f) return '';
      if(f.fixed!==undefined) return `<div class="fchip"><button disabled style="opacity:.75;cursor:default">${chipLabel(k)}</button></div>`;
      const st=F[k]; const active=f.tgl?st.on:(f.cat?st.v!=null:(st.min!=null||st.max!=null));
      let pop;
      if(f.cat){ pop=`<div class="pl">선택</div>`+catOpts(k).map(o=>
          `<button class="preset ${st.v===(o||null)?'sel':''}" data-ecat="${k}" data-v="${E(o)}">${E(o||'전체')}</button>`).join(''); }
      else if(f.tgl){ pop=`<label class="tgl"><input type="checkbox" data-etgl="${k}" ${st.on?'checked':''}> ${E(f.tglLabel)}</label>`; }
      else { pop=`<div class="pl">프리셋</div>`+f.presets.map(p=>{
          const lo=p[1],hi=p.length>2?p[2]:null;
          const sel=(st.min===lo&&(st.max===hi||(f.min&&hi==null)));
          return `<button class="preset ${sel?'sel':''}" data-ek="${k}" data-lo="${lo==null?'':lo}" data-hi="${hi==null?'':hi}">${E(p[0])}</button>`;}).join('')+
        `<div class="man"><span>직접</span><input type="number" placeholder="최소" data-eman="${k}" data-mm="min" value="${st.min??''}">`+
        `<span>~</span><input type="number" placeholder="최대" data-eman="${k}" data-mm="max" value="${st.max??''}"></div>`; }
      return `<div class="fchip"><button class="${active?'act':''}" data-echip="${k}">${chipLabel(k)}</button><div class="fpop" id="epop_${k}">${pop}</div></div>`;});
    parts.unshift(findChipHTML());
    const bar=$('etf_fltbar'); if(!bar) return;
    bar.innerHTML=parts.join('');
    try{
      bar.querySelectorAll('[data-echip]').forEach(b=>b.onclick=e=>{e.stopPropagation();
        const p=$('epop_'+b.dataset.echip); const was=p.classList.contains('open');
        document.querySelectorAll('#p_etf .fpop').forEach(x=>x.classList.remove('open')); if(!was)p.classList.add('open');});
      bar.querySelectorAll('.preset[data-ek]').forEach(b=>b.onclick=()=>{const k=b.dataset.ek;
        F[k]={min:b.dataset.lo===''?null:+b.dataset.lo,max:b.dataset.hi===''?null:+b.dataset.hi}; apply();});
      bar.querySelectorAll('[data-eman]').forEach(inp=>inp.oninput=()=>{const k=inp.dataset.eman;
        F[k][inp.dataset.mm]=inp.value===''?null:+inp.value;
        const btn=bar.querySelector(`[data-echip="${k}"]`);
        if(btn){btn.innerHTML=chipLabel(k);btn.classList.toggle('act',F[k].min!=null||F[k].max!=null);}
        applyTable();});
      bar.querySelectorAll('[data-ecat]').forEach(b=>b.onclick=()=>{F[b.dataset.ecat].v=b.dataset.v||null; apply();});
      bar.querySelectorAll('[data-etgl]').forEach(t=>t.onchange=()=>{F[t.dataset.etgl].on=t.checked; apply();});
      {const b=$('efind_btn'); if(b) b.onclick=e=>{e.stopPropagation();
        document.querySelectorAll('#p_etf .fpop').forEach(x=>x.classList.remove('open'));
        findOpen=true; findCaret=null; renderChips();};}
      {const x=$('efind_x'); if(x) x.onclick=e=>{e.stopPropagation(); findIME=false; findQ=''; findOpen=false; apply();};}
      {const fi=$('efind_in'); if(fi){
        fi.onclick=e=>e.stopPropagation();
        fi.oncompositionstart=()=>{findIME=true;};
        fi.oncompositionend=()=>{findIME=false; findQ=fi.value.trim(); findCaret=fi.selectionStart; applyTable();};
        fi.oninput=()=>{findQ=fi.value.trim(); findCaret=fi.selectionStart; applyTable();};
        fi.onkeydown=e=>{e.stopPropagation(); if(e.key==='Escape'){findIME=false;findQ='';findOpen=false;apply();}};
        const ae=document.activeElement;
        if(!(ae&&/^(INPUT|SELECT|TEXTAREA)$/.test(ae.tagName)&&ae.id!=='efind_in')){
          fi.focus(); if(findCaret!=null) fi.setSelectionRange(findCaret,findCaret);} }}
    }catch(err){ console.error('[etf] 칩 배선 오류:',err); }
  }
  document.addEventListener('click',()=>document.querySelectorAll('#p_etf .fpop').forEach(x=>x.classList.remove('open')));

  /* ── 표 (컬럼 = COLST 사용자 설정) ── */
  const sgn=(v,d)=>v==null?'—':`<span class="${v>0?'up':(v<0?'dn':'note')}">${v>0?'+':''}${v.toFixed(d)}%</span>`;
  function cell(r,k){
    const v=val(r,k);
    switch(k){
      case 'n': return `<b>${E(mkt==='kr'?r.n:r.c)}</b> <span class="note">${E(mkt==='kr'?r.c:(r.n||'').slice(0,26))}</span>`
        +(r.lev?' <span class="etflev">L</span>':'')+(r.md?' <span class="etfmd">월</span>':'');
      case 'lev': return r.lev?'<span class="etflev">레버·인버스</span>':'<span class="note">—</span>';
      case 'md': return r.md?'<span class="etfmd">월배당</span>':'<span class="note">—</span>';
      case 'asset': case 'exch': return `<span class="note">${E(v||'—')}</span>`;
      case 'px': return v==null?'—':(mkt==='kr'?Math.round(v).toLocaleString()+'원':'$'+(+v).toFixed(2));
      case 'chg': return sgn(v,2);
      case 'cap': return mkt==='kr'?wonF(v):usdF(v);
      case 'tv': return mkt==='kr'?wonF(v):usdF(v);
      case 'fee': return v==null?'—':v.toFixed(2)+'%';
      case 'dev': return v==null?'—':`<span class="${Math.abs(v)>=1?'dn':''}">${(v>0?'+':'')+v.toFixed(2)}%</span>`;
      case 'divy': return v==null?'—':v.toFixed(2)+'%';
      case 'r1m': case 'r3m': case 'r6m': case 'r1y': case 'v200': return sgn(v,1);
      case 'vol20': return v==null?'—':v.toFixed(1)+'%';
      case 'hi': return v==null?'—':`<span class="note">고점 ${v.toFixed(0)}%</span>`;
      case 'yr': return v==null?'—':v+'년';
    }
    return v==null?'—':String(v);
  }
  function applyTable(){
    if(!loaded){ return; }
    const rows=POOL[mkt].filter(pass);
    const gv=r=>{const v=val(r,sort.k); return v==null?-Infinity:(typeof v==='string'?v:v);};
    rows.sort((a,b)=>{const x=gv(a),y=gv(b);
      if(typeof x==='string'||typeof y==='string') return sort.d*String(x).localeCompare(String(y));
      return sort.d*(x-y);});
    $('etf_cnt').innerHTML=`<b>${rows.length.toLocaleString()}</b>종 통과 <span style="opacity:.6">/ ${POOL[mkt].length.toLocaleString()} 전체</span>`
      +(findQ?` <span class="findtag">🔎 "${E(findQ)}"</span>`:'');
    const cols=COLST[mkt].filter(cAvail), cap=rows.slice(0,400);
    $('etf_tbl').innerHTML='<tr><th>#</th>'+cols.map(k=>`<th data-es="${k}" class="${sort.k===k?(sort.d<0?'dn':'up'):''}">${E(CDEF[k].l)}</th>`).join('')
      +'<th class="colbtn" id="etf_colplus" title="표시 컬럼 추가·순서 변경">＋</th></tr>'+
      cap.map((r,i)=>`<tr><td class="note">${i+1}</td>`+cols.map(k=>`<td class="${CDEF[k].n?'num':''}">${cell(r,k)}</td>`).join('')+'<td></td></tr>').join('')+
      (rows.length?'':`<tr><td colspan="${cols.length+2}" class="note" style="text-align:center;padding:16px">조건을 통과한 ETF 가 없습니다</td></tr>`)+
      (rows.length>400?`<tr><td colspan="${cols.length+2}" class="note" style="text-align:center">상위 400종 표시 (전체 ${rows.length.toLocaleString()}종)</td></tr>`:'');
    // (2026-07-26) 행에 data-c(코드) 부여 + 클릭 → 상세
    $('etf_tbl').querySelectorAll('tr').forEach((tr,i)=>{ if(i===0) return;
      const r=cap[i-1]; if(!r) return; tr.setAttribute('data-c',r.c); tr.onclick=()=>showDetail(r); });
    $('etf_tbl').querySelectorAll('[data-es]').forEach(th=>th.onclick=e=>{ e.stopPropagation();
      const k=th.dataset.es; if(sort.k===k)sort.d*=-1; else{sort.k=k;sort.d=(CDEF[k].n)?-1:1;} applyTable();});
    {const pl=$('etf_colplus'); if(pl) pl.onclick=e=>{e.stopPropagation(); toggleColPanel();};}
  }

  /* ── 종목 상세 (좌 차트 · 우 정보) ── */
  let dcode=null;
  const _sma=(a,n)=>a.map((_,i)=>{ if(i<n-1) return null; let s=0; for(let j=i-n+1;j<=i;j++){ if(a[j]==null) return null; s+=a[j]; } return s/n; });
  function _cvs(id){ const cv=$(id); const w=cv.clientWidth||760,h=cv.clientHeight||80; cv.width=w; cv.height=h; const x=cv.getContext('2d'); x.clearRect(0,0,w,h); return [x,w,h]; }
  function drawChart(D){
    const c=(D.c||[]).map((v,i)=>v==null?(D.c[i-1]??null):v);
    const N=Math.min(260,c.length), off=c.length-N;
    const cl=c.slice(off), o=(D.o||[]).slice(off), hh=(D.h||[]).slice(off), ll=(D.l||[]).slice(off), v=(D.v||[]).slice(off).map(x=>x||0), t=(D.t||[]).slice(off);
    const ma20=_sma(c,20).slice(off), ma60=_sma(c,60).slice(off);
    const UP='#d33',DN='#1f6feb';
    // ① 캔들 + MA20/60
    {const [x,W,H]=_cvs('ed_main'); const P={l:6,r:54,t:8,b:16};
     const lo=Math.min(...ll.filter(y=>y!=null)), hi=Math.max(...hh.filter(y=>y!=null));
     const X=i=>P.l+(W-P.l-P.r)*(i+0.5)/N, Y=p=>P.t+(H-P.t-P.b)*(1-(p-lo)/((hi-lo)||1));
     x.font='10px sans-serif'; x.fillStyle='#98a2ad'; x.strokeStyle='#eceff3';
     for(let g=0;g<=3;g++){ const p=lo+(hi-lo)*g/3,y=Y(p); x.beginPath();x.moveTo(P.l,y);x.lineTo(W-P.r,y);x.stroke();
       x.fillText(mkt==='kr'?Math.round(p).toLocaleString():(+p).toFixed(2),W-P.r+4,y+3); }
     const bw=Math.max(1,(W-P.l-P.r)/N*0.6);
     for(let i=0;i<N;i++){ if(cl[i]==null)continue; const up=cl[i]>=(o[i]??cl[i]); x.strokeStyle=x.fillStyle=up?UP:DN;
       x.beginPath(); x.moveTo(X(i),Y(hh[i]??cl[i])); x.lineTo(X(i),Y(ll[i]??cl[i])); x.stroke();
       const y1=Y(Math.max(o[i]??cl[i],cl[i])),y2=Y(Math.min(o[i]??cl[i],cl[i])); x.fillRect(X(i)-bw/2,y1,bw,Math.max(1,y2-y1)); }
     const line=(a,col)=>{ x.strokeStyle=col;x.lineWidth=1.4;x.beginPath();let s=false;
       for(let i=0;i<N;i++){ if(a[i]==null)continue; s?x.lineTo(X(i),Y(a[i])):(x.moveTo(X(i),Y(a[i])),s=true);} x.stroke();x.lineWidth=1; };
     line(ma20,'#f39c12'); line(ma60,'#27ae60');
     x.fillStyle='#98a2ad'; for(let g=0;g<5;g++){ const i=Math.floor(N*g/5),d=String(t[i]||'').replace(/-/g,''); x.fillText(d.slice(2,4)+'.'+d.slice(4,6),X(i)-10,H-4); } }
    // ② 거래량
    {const [x,W,H]=_cvs('ed_vol'); const P={l:6,r:54,t:2,b:2};
     const vm=Math.max(...v)||1, X=i=>P.l+(W-P.l-P.r)*(i+0.5)/N, bw=Math.max(1,(W-P.l-P.r)/N*0.6);
     for(let i=0;i<N;i++){ x.fillStyle=(cl[i]>=(o[i]??cl[i]))?'rgba(221,51,51,.45)':'rgba(31,111,235,.45)'; const h2=(H-P.t-P.b)*v[i]/vm; x.fillRect(X(i)-bw/2,H-P.b-h2,bw,h2); }
     x.font='10px sans-serif'; x.fillStyle='#98a2ad'; x.fillText('VOL',W-P.r+4,12); }
  }
  function infoRows(r){
    const pctS=v=>v==null?'—':`<b class="${v>0?'up':(v<0?'dn':'')}">${v>0?'+':''}${(v*100).toFixed(1)}%</b>`;
    const G=[['시세',[['가격',cell(r,'px')],['등락',cell(r,'chg')],['AUM',cell(r,'cap')],['거래대금',cell(r,'tv')]]],
      ['기간수익률',[['1M',pctS(r.r1m)],['3M',pctS(r.r3m)],['6M',pctS(r.r6m)],['1Y',pctS(r.r1y)]]],
      ['기술',[['변동성(20일)',r.vol20!=null?r.vol20.toFixed(1)+'%':'—'],['200일선',pctS(r.v200)],['고점比',r.hi!=null?(r.hi*100).toFixed(0)+'%':'—']]],
      ['ETF 정보',[[(mkt==='kr'?'자산군':'거래소'),cell(r,'asset')],['총보수',cell(r,'fee')],['분배율',cell(r,'divy')]
        ].concat(mkt==='kr'?[['괴리율',cell(r,'dev')],['운용사',r.issuer?`<b>${E(r.issuer)}</b>`:'—'],['월배당',r.md?'<b class="up">월배당</b>':'—']]:[])
        .concat([['레버리지·인버스',r.lev?'<b class="dn">예</b>':'아니오'],['상장기간',cell(r,'yr')]]) ]];
    return G.map(([t,its])=>`<div class="sgt">${t}</div>`+its.map(it=>`<div class="si"><span class="note">${it[0]}</span>${it[1]}</div>`).join('')).join('');
  }
  function showDetail(r){
    dcode=r.c;
    $('etf_detail').style.display='';
    $('ed_name').textContent = mkt==='kr'?r.n:r.c;
    $('ed_code').textContent = mkt==='kr'?r.c:(r.n||'');
    $('ed_last').innerHTML = cell(r,'px')+' '+cell(r,'chg');
    $('ed_sum').innerHTML = infoRows(r);
    $('ed_src').textContent='종가 기준 일봉(최근 1년) · '+(mkt==='kr'?'네이버':'Yahoo')+' · MA20 주황 · MA60 초록';
    fetch(`/api/chart/${mkt}/${encodeURIComponent(r.c)}`).then(x=>x.json()).then(D=>{
      if(dcode!==r.c) return; drawChart(D);
    }).catch(()=>{ $('ed_src').textContent='차트 로드 실패'; });
    $('etf_detail').scrollIntoView({block:'nearest',behavior:'smooth'});
  }
  {const cb=$('ed_close'); if(cb) cb.onclick=()=>{ $('etf_detail').style.display='none'; dcode=null; };}
  {const nv=$('ed_nvopen'); if(nv) nv.onclick=()=>{ if(!dcode) return;
    const url = mkt==='kr' ? `https://finance.naver.com/item/main.naver?code=${encodeURIComponent(dcode)}`
                           : `https://finance.yahoo.com/quote/${encodeURIComponent(dcode)}`;
    window.open(url,'etf_ext','width=1150,height=900'); };}
  function apply(){ applyTable(); renderChips(); }

  function statusText(d){ return `기준 ${d.asof||''}${d.live_at?' · 🟢 '+d.live_at:''} · KR ${(d.kr||[]).length}종 · US ${(d.us||[]).length}종 <span class="note">· 장중 자동갱신 KR 1분·US 3분(시간외 포함)</span>`; }
  function start(){
    const st=$('etf_status'); if(st) st.textContent='ETF 풀 불러오는 중…';
    fetch('/api/db/etf_pool').then(r=>r.json()).then(d=>{
      POOL={kr:d.kr||[],us:d.us||[]}; loaded=true;
      if(st) st.innerHTML=statusText(d);
      apply();
    }).catch(e=>{ if(st) st.textContent='ETF 풀 로드 실패 — 수집이 아직 안 됐을 수 있습니다: '+e; });
  }
  /* (2026-07-26) 장중 LIVE: 서버 증분(KR 1분·US 3분) 갱신 풀을 1분마다 자동 재조회 (탭 열림·화면 보일 때만) */
  setInterval(()=>{
    if(!loaded) return;
    const p=document.getElementById('p_etf');
    if(!p||!p.classList.contains('on')||document.visibilityState!=='visible') return;
    fetch('/api/db/etf_pool').then(r=>r.json()).then(d=>{
      if(!d||!d.kr) return;
      POOL={kr:d.kr||[],us:d.us||[]};
      const st=$('etf_status'); if(st) st.innerHTML=statusText(d);
      apply();
    }).catch(()=>{});
  }, 60000);
  /* 시장 토글 */
  document.querySelectorAll('#p_etf .mkt[data-emkt]').forEach(b=>b.onclick=()=>{
    document.querySelectorAll('#p_etf .mkt[data-emkt]').forEach(x=>x.classList.toggle('on',x===b));
    mkt=b.dataset.emkt; loadF(); findQ=''; findOpen=false; sort={k:'cap',d:-1};
    if(loaded) apply(); else renderChips();
  });
  {const gb=$('etf_start'); if(gb) gb.onclick=()=>{ if(!loaded) start(); else apply(); };}
  {const rb=$('etf_rst'); if(rb) rb.onclick=()=>{ F_ST[mkt]=buildF(); F=F_ST[mkt]; findQ=''; findOpen=false; apply(); };}
  {const ab=$('etf_allf'); if(ab) ab.onclick=()=>{ F_ST[mkt]=clearF(); F=F_ST[mkt]; findQ=''; findOpen=false; apply(); };}
  {const cb=$('etf_colbtn'); if(cb) cb.onclick=()=>toggleColPanel();}
  {const lb=$('etf_glsbtn'); if(lb) lb.onclick=()=>toggleLegend();}
  {const lx=$('etf_glsx'); if(lx) lx.onclick=()=>toggleLegend(false);}
  loadF(); renderChips();
})();
