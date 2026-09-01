/* ── (2026-09-01) 📈 이익성장 모니터링 탭 — screener_pool + stlead (신규 수집 없음)
   컨셉(사용자): **과거 이익성장(실적) + 미래 이익성장 예측(컨센) + 선행지표(시장) → 주가 오름**.
   두 조건을 동시에 충족하는 종목만 리스트업(KR·US 각 상위 30)하고,
   종목별 '지금 사기 좋은 시점인가'를 6항목 신호등(🟢🟡🔴)으로 판별한다.
   과거성장: KR opg(재무제표 영업익 YoY) · US epsg(실적 EPS 성장)
   미래성장: KR opg_f(컨센 영업익_E/최근 실적−1, 2026-09-01 신설 — 첫 풀 갱신 전엔 revg_f·g_new 폴백)
             US (ey1/ey0−1) — 내년/올해 컨센 EPS
   신호등 6항목: ①시장 선행지표(지수 12M 릿지 예측+) ②전망 리비전 ③밸류(PEG<1.5/상승여력)
   ④추세(장기이평 위+정배열) ⑤과열 아님(RSI<70) ⑥성장 가속(gacc>0). 5~6=🟢 3~4=🟡 0~2=🔴 */
(function(){
  const $=id=>document.getElementById(id);
  const E=s=>String(s??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
  let _init=false,P=null,ST=null,mkt='kr',minCapKR=3000,minCapUS=2;   // 억원 / $B

  const pct=(v,d)=>v==null?'—':`<span class="${v>0?'up':(v<0?'dn':'')}">${v>0?'+':''}${(v*100).toFixed(d==null?0:d)}%</span>`;
  const capf=(r,m)=>m==='kr'?(r.mcap?(r.mcap/1e12>=1?(r.mcap/1e12).toFixed(1)+'조':Math.round(r.mcap/1e8).toLocaleString()+'억'):'—')
                            :(r.mcap?'$'+(r.mcap/1e9).toFixed(0)+'B':'—');

  /* 과거·미래 성장 추출 */
  function grow(r,m){
    if(m==='kr'){
      const past=r.opg;                                   // 재무제표 영업익 YoY(실적)
      // 컨센 영업익(2026-09-01 신설) → 매출 전망 → 혼합성장 g_new(첫 풀 갱신 전 임시 대용) 순 폴백
      const fut=(r.opg_f!=null)?r.opg_f:(r.revg_f!=null?r.revg_f:(r.g_new!=null?r.g_new:null));
      return {past,fut,futSrc:r.opg_f!=null?'컨센 영업익':(r.revg_f!=null?'매출 전망(대용)':'혼합 성장(임시 대용 — 내일부터 컨센 영업익)')};
    }
    const past=(r.epsg!=null)?r.epsg:r.revg;              // 실적 EPS 성장 → 매출 폴백
    const fut=(r.ey0&&r.ey1&&r.ey0>0)?(r.ey1/r.ey0-1):null; // 내년/올해 컨센 EPS
    return {past,fut,futSrc:'컨센 EPS(내년/올해)'};
  }

  /* (2026-09-02) PEG 재정의 — 기존 peg(분모=직전 1년 실적 성장률)는 이 탭 상위군(성장 400~600%)에서
     0.0x 로 붕괴해 의미 없음(실측: 상위30 PEG 중앙값 0.04). 표시·판정용 PEG 는
     **fPER ÷ 미래 성장예측%** 로 재계산하고, 성장률 15~100% 구간에서만 값 인정
     (100%↑ = 기저효과 왜곡 · 15%↓ = PEG 부적합). 그 외는 '—' + 상승여력으로만 밸류 판정. */
  function fpeg(r,g,m){
    const pe=m==='kr'?r.fper:r.fpe;
    if(pe==null||pe<=0||g.fut==null) return null;
    const gp=g.fut*100;
    if(gp<15||gp>100) return null;
    return pe/gp;
  }
  /* (2026-09-01) 컨셉 확장: 과거이익성장 + 미래이익성장예측 + **선행지표** → 주가 오름.
     선행지표 축 = 소속 시장 지수(코스피200/S&P500)의 12개월 릿지 예측(Portfolio stlead 엔진 —
     금리·유동성·신용잔고 등 20여 선행지표 기반). 종목 레벨 선행은 ②리비전이 담당. */
  function mktLead(m){
    if(!ST) return null;
    const p=((ST.targets[m==='kr'?'ks200':'spx']||{}).pred||{})[12];
    return p?p.g:null;
  }
  /* 신호등 6항목 — 각 항목 {ok, txt} */
  function signals(r,m,g){
    const s=[];
    const ml=mktLead(m);
    s.push({ok:ml!=null&&ml>0, na:ml==null,
      txt:`시장 선행지표 12M ${ml!=null?(ml>0?'+':'')+((Math.exp(ml)-1)*100).toFixed(1)+'%':'—'}`});
    // (2026-09-02) KR tprv 는 원본이 이미 % 단위(kr_consensus tp30), US cr30 은 fraction — 단위 분리
    const rev=m==='kr'?r.tprv:r.cr30;
    const revPct=rev==null?null:(m==='kr'?rev:rev*100);
    s.push({ok:rev!=null&&rev>0, na:rev==null,
      txt:`${m==='kr'?'목표가30일':'컨센30일'} ${revPct!=null?(revPct>0?'+':'')+revPct.toFixed(1)+'%':'—'}`});
    const pg=fpeg(r,g,m);
    const val=(pg!=null&&pg<1.5)||(r.upside!=null&&r.upside>0);
    s.push({ok:val, na:pg==null&&r.upside==null,
      txt:`PEG ${pg!=null?pg.toFixed(2):'—'}·여력 ${r.upside!=null?(r.upside>0?'+':'')+(r.upside*100).toFixed(0)+'%':'—'}`});
    // (2026-09-02) align 은 문자열("정배열/혼조/역배열") — 숫자 비교 버그로 전종목 역배열 표시됐었다.
    //   판정 = 장기선(120일/200일) 위 AND 역배열 아님(혼조 허용 — 정배열만 요구하면 KR 145종뿐).
    const tr=(r.vs200!=null&&r.vs200>0)&&(r.align!=='역배열');
    s.push({ok:tr, na:r.vs200==null,
      txt:`장기선 ${r.vs200!=null?(r.vs200>0?'위':'아래'):'—'}${typeof r.align==='string'?'·'+r.align:''}`});
    s.push({ok:r.rsi!=null&&r.rsi<70, na:r.rsi==null, txt:`RSI ${r.rsi!=null?Math.round(r.rsi):'—'}`});
    s.push({ok:r.gacc!=null&&r.gacc>0, na:r.gacc==null,
      txt:`가속 ${r.gacc!=null?((r.gacc>0?'+':'-')+Math.min(Math.abs(r.gacc)*100,999).toFixed(0)+'%p'+(Math.abs(r.gacc)>9.99?'↑':'')):'—'}`});
    return s;
  }
  const lamp=n=>n>=5?'🟢':(n>=3?'🟡':'🔴');
  const lampTxt=n=>n>=5?'매수 우호':(n>=3?'관망':'대기');

  function rows(m){
    const list=(P&&P[m])||[];
    const out=[];
    for(const r of list){
      if(r.isfin) continue;                               // 금융 제외(성장률 왜곡)
      if(m==='kr'&&(!r.mcap||r.mcap<minCapKR*1e8)) continue;
      if(m==='us'&&(!r.mcap||r.mcap<minCapUS*1e9)) continue;
      if(r.oploss) continue;                              // 적자 지속 제외
      const g=grow(r,m);
      if(g.past==null||g.fut==null) continue;
      if(g.past<=0||g.fut<=0) continue;                   // 컨셉: 과거·미래 모두 +
      const sg=signals(r,m,g);
      const sc=sg.filter(x=>x.ok).length;
      out.push({r,g,sg,sc,pg:fpeg(r,g,m),rank:Math.min(g.past,3)+Math.min(g.fut,3)});  // 극단 캡 후 합산
    }
    out.sort((a,b)=>b.rank-a.rank);
    return out.slice(0,30);
  }

  function marketBanner(){
    if(!ST) return '';
    const g=(tk,h)=>{const p=((ST.targets[tk]||{}).pred||{})[h];return p?(Math.exp(p.g)*100-100):null;};
    const s12=g('spx',12),k12=g('ks200',12);
    let mg=null;
    const ser=(ST.series||{}).margin;
    if(ser&&ser.v){const v=ser.v.filter(x=>x!=null);
      if(v.length>13){const a=v[v.length-1],b=v[v.length-13]; if(a&&b) mg=(a/b-1)*100;}}
    const warn=mg!=null&&mg>50;
    return `<div style="padding:6px 10px;background:#f6f7f9;border:1px solid #e5e8ec;border-radius:8px;margin-bottom:8px;font-size:12.5px">
      🌡 <b>시장 온도</b> — S&P500 12M 예측 <b class="${s12>0?'up':'dn'}">${s12!=null?(s12>0?'+':'')+s12.toFixed(1)+'%':'—'}</b>
      · 코스피200 12M <b class="${k12>0?'up':'dn'}">${k12!=null?(k12>0?'+':'')+k12.toFixed(1)+'%':'—'}</b>
      · 미 신용잔고 YoY <b style="color:${warn?'#dc2626':'#333'}">${mg!=null?(mg>0?'+':'')+mg.toFixed(1)+'%':'—'}</b>${warn?' <span style="color:#dc2626">⚠ 레버리지 과열권(2000·2007·2021 고점 58~72%)</span>':''}
      <span class="note">— 개별 신호등이 🟢여도 시장 전체가 꺾이면 같이 빠진다. 참고용·투자권유 아님</span></div>`;
  }

  function render(){
    if(!P) return;
    const m=mkt, data=rows(m);
    const asof=P.price_date||P.asof||'';
    const futNote=m==='kr'&&data.length&&data[0].g.futSrc.includes('대용')
      ?' <span class="note" style="color:#b45309">(미래성장=매출 전망 대용 — 다음 풀 갱신부터 컨센 영업익)</span>':'';
    const btn=(on,txt,attr)=>`<button ${attr||''} style="padding:3px 10px;font-size:11.5px;border:1px solid ${on?'#1f2937':'#d7dce3'};border-radius:6px;cursor:pointer;background:${on?'#1f2937':'#fff'};color:${on?'#fff':'#444'}">${txt}</button>`;
    $('eg_top').innerHTML=marketBanner()
      +`<div style="margin-bottom:6px">${btn(m==='kr','🇰🇷 한국','data-m="kr"')} ${btn(m==='us','🇺🇸 미국','data-m="us"')}
      <span class="note" style="margin-left:8px">조건: 과거 이익성장 + AND 미래 이익성장 예측 + · 시총 ${m==='kr'?minCapKR.toLocaleString()+'억↑':'$'+minCapUS+'B↑'} · 금융·적자지속 제외 · 상위 30 (성장 합산순) · 기준 ${E(asof)}${futNote}</span></div>`;
    $('eg_top').querySelectorAll('[data-m]').forEach(b=>b.onclick=()=>{mkt=b.dataset.m;render();});
    const th=t=>`<th style="text-align:right">${t}</th>`;
    $('eg_tbl').innerHTML=`<table style="font-size:12px"><thead><tr>
      <th>#</th><th>종목</th>${th('시총')}${th('과거 이익성장')}${th('미래 성장예측')}<th style="text-align:right" title="PEG = fPER ÷ 미래 성장예측(%). 1 근처 적정·1미만 저평가·2이상 고평가(피터 린치). 성장률 15~100% 구간만 표시 — 그 밖은 왜곡이라 '—'">PEG</th>${th(m==='kr'?'fPER':'fPE')}
      <th style="text-align:center" title="6항목 중 충족 수 — 5~6 🟢 매수우호 · 3~4 🟡 관망 · 0~2 🔴 대기">타이밍</th>
      <th title="①시장 선행지표 ②전망 리비전 ③밸류 ④추세 ⑤과열아님 ⑥성장가속 — ✓충족 ✗미충족 ·자료없음">판별 근거 6항목</th></tr></thead><tbody>${
      data.map((x,i)=>{const r=x.r;
        const nm=m==='kr'?`${E(r.name)} <span class="note">${r.code}</span>`:`<b>${E(r.sym)}</b> <span class="note">${E((r.name||'').slice(0,18))}</span>`;
        const pe=m==='kr'?r.fper:r.fpe;
        return `<tr>
        <td>${i+1}</td><td style="white-space:nowrap">${nm}</td>
        <td class="num">${capf(r,m)}</td>
        <td class="num"><b>${pct(x.g.past,0)}</b></td>
        <td class="num"><b>${pct(x.g.fut,0)}</b> <span class="note" title="${E(x.g.futSrc)}">ⓘ</span></td>
        <td class="num" title="fPER ÷ 미래 성장예측% — 성장 15~100% 구간만 표시(그 밖은 기저효과 왜곡/부적합)">${(x.pg!=null)?x.pg.toFixed(2):'—'}</td>
        <td class="num">${pe!=null?pe.toFixed(1):'—'}</td>
        <td style="text-align:center;font-size:14px" title="${lampTxt(x.sc)} (${x.sc}/6)">${lamp(x.sc)} <span class="note">${x.sc}/6</span></td>
        <td style="font-size:10.5px;color:#555">${x.sg.map(s=>`<span style="margin-right:7px;white-space:nowrap;${s.na?'opacity:.4':''}">${s.na?'·':(s.ok?'<b style="color:#16a34a">✓</b>':'<b style="color:#dc2626">✗</b>')} ${E(s.txt)}</span>`).join('')}</td></tr>`;
      }).join('')||'<tr><td colspan="9" class="note">조건 충족 종목 없음</td></tr>'}</tbody></table>
      <div class="note" style="margin-top:6px;line-height:1.7">💡 <b>컨셉</b>: 이익이 <b>실적으로 이미 성장했고</b>(과거) <b>앞으로도 성장할 것으로 전망되는</b>(컨센서스) 종목이 주가가 오른다 —
      두 조건을 동시에 충족한 종목만 올린다. <b>타이밍 신호등</b>은 '지금 진입해도 되는가'를 6항목으로 판별:
      ①<b>시장 선행지표</b>(소속 지수의 12개월 릿지 예측 — 금리·유동성·신용잔고 등 20여 선행지표가 +인가)
      ②전망 리비전(애널리스트가 최근 30일 상향 중인가) ③밸류(PEG&lt;1.5 또는 목표가 상승여력) ④추세(장기이평 위·정배열)
      ⑤과열 아님(RSI&lt;70) ⑥성장 가속(이번 분기 YoY가 작년 동기보다 빠른가). 🟢=성장+선행지표+타이밍 모두 우호,
      🟡=성장은 확인되나 타이밍 신호 일부 미충족, 🔴=지금은 대기. 매일 스크리너 풀 갱신 시 자동 반영. 참고용이며 투자권유가 아님.</div>`;
  }

  function init(){
    if(_init) return; _init=true;
    Promise.all([
      fetch('/api/db/screener_pool',{cache:'no-cache'}).then(r=>r.ok?r.json():null),
      fetch('/api/db/stlead').then(r=>r.ok?r.json():null).catch(()=>null),
    ]).then(([p,st])=>{
      if(!p||!p.kr){$('eg_top').innerHTML='<div class="note">스크리너 풀 로딩 실패 — 새로고침 해주세요.</div>';return;}
      P=p; ST=st;
      try{render();}catch(err){
        $('eg_top').innerHTML=`<div style="color:#b91c1c;font-weight:700">렌더 오류: ${E(err&&err.message||err)}</div>`;throw err;}
    });
  }
  const tb=document.querySelector('.tab[data-pane="p_eg"]');
  if(tb) tb.addEventListener('click',init);
})();
