/* llm.js — 🤖 AI 챗봇 탭 (2026-09-10 신설 · 실험용)
   서버 로컬 LLM(Ollama · qwen3.5:4b · CPU 전용, 1.2코어 격리)을 /api/llm/chat 으로 호출해 스트리밍 표시.
   로그인 세션만 허용(서버가 401 반환). 대화 이력은 메모리(새로고침 시 초기화). */
(function(){
'use strict';
const $=id=>document.getElementById(id);
const E=s=>String(s??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
let HIST=[], BUSY=false, ctrl=null;
// (2026-09-10 사용자 요청) 대화 백업 — 브라우저 localStorage 에 저장, 새로고침·강제중단 후에도 복원(최근 60턴). 초기화 버튼이 지운다.
const LS='namoobi_llm_hist';
function save(){ try{ localStorage.setItem(LS, JSON.stringify(HIST.slice(-60))); }catch(e){} }
function loadHist(){ try{ const h=JSON.parse(localStorage.getItem(LS)||'[]'); return Array.isArray(h)?h:[]; }catch(e){ return []; } }

function bubble(role, text, id){
  const me=role==='user';
  return `<div id="${id||''}" style="display:flex;justify-content:${me?'flex-end':'flex-start'};margin:6px 0">
    <div style="max-width:78%;padding:9px 13px;border-radius:14px;font-size:13.5px;line-height:1.55;white-space:pre-wrap;word-break:break-word;
      background:${me?'#4c1d95':'#fff'};color:${me?'#fff':'#1e293b'};border:1px solid ${me?'#4c1d95':'#e2e8f0'}">${E(text)}</div></div>`;
}
function scrollBottom(){ const b=$('llm_box'); if(b) b.scrollTop=b.scrollHeight; }

async function status(){
  try{
    const r=await fetch('/api/llm/status',{cache:'no-cache'}); const d=await r.json();
    $('llm_stat').innerHTML=d.ok?`<span style="color:#166534">● ${E(d.model)} ${d.loaded?'준비':'모델 미설치'}</span>`:`<span style="color:#b91c1c">● Ollama 응답 없음 ${E(d.err||'')}</span>`;
  }catch(e){ $('llm_stat').textContent='상태 확인 실패'; }
}

async function send(){
  if(BUSY) return;
  const ta=$('llm_in'); const q=ta.value.trim(); if(!q) return;
  ta.value=''; HIST.push({role:'user',content:q}); save();
  $('llm_box').insertAdjacentHTML('beforeend', bubble('user',q));
  const aid='llm_a_'+Date.now();
  $('llm_box').insertAdjacentHTML('beforeend', bubble('assistant','…',aid));
  scrollBottom();
  BUSY=true; $('llm_send').disabled=true; $('llm_stop').style.display='';
  const t0=performance.now(); let out='', ntok=0;
  const el=$(aid).firstElementChild;
  ctrl=new AbortController();
  try{
    const r=await fetch('/api/llm/chat',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({messages:HIST.slice(-12)}),signal:ctrl.signal});
    if(r.status===401){ el.textContent='로그인 후 이용 가능합니다(서버 CPU 보호).'; HIST.pop(); save(); return; }
    if(!r.ok){ el.textContent='오류 HTTP '+r.status; HIST.pop(); save(); return; }
    const rd=r.body.getReader(), dec=new TextDecoder(); let buf='';
    el.textContent='';
    while(true){
      const {value,done}=await rd.read(); if(done) break;
      buf+=dec.decode(value,{stream:true});
      let i;
      while((i=buf.indexOf('\n'))>=0){
        const line=buf.slice(0,i).trim(); buf=buf.slice(i+1); if(!line) continue;
        let j; try{ j=JSON.parse(line); }catch(e){ continue; }
        if(j.error){ el.textContent+='\n[오류] '+j.error; continue; }
        const c=(j.message&&j.message.content)||''; if(c){ out+=c; ntok++; el.textContent=out; scrollBottom(); }
        if(j.done){ const s=(performance.now()-t0)/1000;
          $('llm_meta').textContent=`마지막 응답: ${ntok}토큰 · ${s.toFixed(1)}초 · ${(ntok/s).toFixed(1)} tok/s`; }
      }
    }
    if(out) HIST.push({role:'assistant',content:out}); save();
  }catch(e){
    if(e.name==='AbortError'){ el.textContent=out+' [중단]'; if(out) HIST.push({role:'assistant',content:out+' [중단]'}); save(); }
    else el.textContent='오류: '+e.message;
  }finally{ BUSY=false; $('llm_send').disabled=false; $('llm_stop').style.display='none'; ctrl=null; scrollBottom(); }
}

const HELLO='실험용 로컬 모델(qwen3.5 4B · CPU)입니다. 첫 질문은 모델 로딩으로 20~30초, 이후 약 3 토큰/초로 느리게 답합니다. 수치·사실은 검증 없이 믿지 마세요. 대화는 이 브라우저에 자동 저장됩니다.';
window.renderLlm=function(){ status(); if(!$('llm_box').children.length){
  HIST=loadHist();
  $('llm_box').innerHTML=bubble('assistant',HELLO)+HIST.map(m=>bubble(m.role,m.content)).join('');
  if(HIST.length) $('llm_meta').textContent=`저장된 대화 ${HIST.length}개 복원`;
  scrollBottom(); } };
// (2026-09-10 사용자 요청) 화면을 보고 있지 않으면 강제 중단 — 서버 CPU 보호.
//   ① 다른 탭 버튼 클릭 ② 브라우저 탭 숨김(visibilitychange) ③ 창 닫기/새로고침(pagehide) → 진행 중 fetch abort.
//   abort 되면 서버 스트리밍 제너레이터가 닫히고 urllib 연결이 끊겨 Ollama 도 생성을 멈춘다(app.py 주석 참조).
function abortIfBusy(reason){ if(ctrl){ ctrl.abort(); const m=$('llm_meta'); if(m) m.textContent='화면 이탈로 중단됨('+reason+')'; } }
document.addEventListener('visibilitychange',()=>{ if(document.hidden) abortIfBusy('탭 숨김'); });
window.addEventListener('pagehide',()=>abortIfBusy('페이지 종료'));
document.addEventListener('click',e=>{ const b=e.target.closest('button.tab[data-pane]'); if(b&&b.dataset.pane!=='p_llm') abortIfBusy('다른 탭'); },true);
document.addEventListener('DOMContentLoaded',function(){
  const s=$('llm_send'); if(s) s.onclick=send;
  const st=$('llm_stop'); if(st) st.onclick=()=>{ if(ctrl) ctrl.abort(); };
  const c=$('llm_clear'); if(c) c.onclick=()=>{ if(ctrl) ctrl.abort(); HIST=[]; try{localStorage.removeItem(LS);}catch(e){} $('llm_box').innerHTML=''; $('llm_meta').textContent=''; window.renderLlm(); };
  const ta=$('llm_in'); if(ta) ta.addEventListener('keydown',e=>{ if(e.key==='Enter'&&!e.shiftKey){ e.preventDefault(); send(); } });
});
})();
