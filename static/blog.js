/* blog.js — 📝 블로그 탭 (2026-11-17 신설 · 사용자 요청)
   구성: 왼쪽 카테고리 메뉴(글 목록) · 가운데 본문(마크다운 → 제목 앵커 '#'·코드블록 언어 라벨·복사) · 오른쪽 목차 · 검색(Ctrl+K) · 글쓰기(로그인 시).
   API: /api/blog/posts · /api/blog/post/{id} · /api/blog/search?q= (공개) · POST/DELETE /api/blog/post (로그인).
   마크다운은 marked 로 변환한 뒤 DOMPurify 로 소독해 넣는다(본문에 스크립트가 섞여도 실행되지 않게). */
(function(){
'use strict';
const $=id=>document.getElementById(id);
const E=s=>String(s??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
let POSTS=[], ADMIN=false, CUR=null, LOADED=false;

const api=(u,o)=>fetch(u,Object.assign({cache:'no-cache'},o||{})).then(async r=>{ if(!r.ok) throw new Error((await r.json().catch(()=>({}))).detail||('HTTP '+r.status)); return r.json(); });

function md2html(md){
  if(!window.marked) return '<pre>'+E(md)+'</pre>';
  const html=window.marked.parse(md,{gfm:true,breaks:true});
  return window.DOMPurify?window.DOMPurify.sanitize(html,{ADD_ATTR:['target']}):html;
}

/* 본문 후처리 — 제목에 id·'#' 앵커, 코드블록에 언어 라벨·복사 버튼, 표 래핑, 외부 링크 새 창 */
function decorate(root){
  const toc=[]; const used={};
  root.querySelectorAll('h2,h3').forEach(h=>{
    let id=(h.tagName.toLowerCase()+'_'+h.textContent.trim().replace(/\s+/g,'_')).slice(0,60); if(used[id]) id+='_'+(++used[id]); else used[id]=1;
    h.id=id; toc.push({id,t:h.textContent.trim(),lv:h.tagName==='H2'?2:3});
    const a=document.createElement('a'); a.href='#'+id; a.textContent='#'; a.className='bl_anchor';
    a.onclick=e=>{e.preventDefault(); h.scrollIntoView({behavior:'smooth',block:'start'});}; h.prepend(a);
  });
  root.querySelectorAll('pre').forEach(pre=>{
    const code=pre.querySelector('code'); const lang=((code&&code.className.match(/language-(\S+)/))||[])[1]||'';
    const bar=document.createElement('div'); bar.className='bl_codebar';
    bar.innerHTML=`<span>${E(lang.toUpperCase())}</span><button type="button">복사</button>`;
    bar.querySelector('button').onclick=function(){ navigator.clipboard.writeText(code?code.textContent:pre.textContent).then(()=>{this.textContent='복사됨'; setTimeout(()=>this.textContent='복사',1200);}); };
    const wrap=document.createElement('div'); wrap.className='bl_code'; pre.parentNode.insertBefore(wrap,pre); wrap.appendChild(bar); wrap.appendChild(pre);
  });
  root.querySelectorAll('table').forEach(t=>{ const w=document.createElement('div'); w.style.cssText='overflow:auto;margin:12px 0'; t.parentNode.insertBefore(w,t); w.appendChild(t); });
  root.querySelectorAll('a[href^="http"]').forEach(a=>{a.target='_blank'; a.rel='noopener';});
  return toc;
}

function renderMenu(){
  const cats={}; POSTS.forEach(p=>(cats[p.cat||'기타']=cats[p.cat||'기타']||[]).push(p));
  $('bl_menu').innerHTML=Object.keys(cats).sort().map(c=>`<div class="bl_cat">${E(c)}</div>`+
    cats[c].map(p=>`<a href="#" data-id="${E(p.id)}" class="bl_item${CUR&&CUR.id===p.id?' on':''}">${E(p.title)}</a>`).join('')).join('')||'<div class="note">글이 없습니다</div>';
  $('bl_menu').querySelectorAll('a').forEach(a=>a.onclick=e=>{e.preventDefault(); openPost(a.dataset.id);});
}

function card(p,snip){
  return `<a href="#" class="bl_card" data-id="${E(p.id)}"><div class="bl_ct">${E(p.title)}</div>
    <div class="bl_cd">${E(snip||p.desc||'')}</div>
    <div class="bl_cm">${E(p.cat||'')} · ${E((p.created||'').slice(0,10))}${(p.tags||[]).length?' · '+(p.tags||[]).map(t=>'#'+E(t)).join(' '):''}</div></a>`;
}
function bindCards(root){ root.querySelectorAll('.bl_card').forEach(a=>a.onclick=e=>{e.preventDefault(); openPost(a.dataset.id);}); }

function showHome(){
  CUR=null; renderMenu(); $('bl_toc').innerHTML='';
  $('bl_main').innerHTML=`<h1 class="bl_h1">블로그</h1><div class="note" style="margin-bottom:14px">글 ${POSTS.length}개 · 왼쪽 메뉴에서 고르거나 위 검색창(Ctrl+K)으로 찾으세요.</div>`+
    (POSTS.map(p=>card(p)).join('')||'<div class="note">아직 글이 없습니다.</div>');
  bindCards($('bl_main')); $('bl_main').scrollTop=0;
}

async function openPost(id){
  let p; try{ p=await api('/api/blog/post/'+encodeURIComponent(id)); }catch(e){ $('bl_main').innerHTML='<div class="note">글을 불러오지 못했습니다: '+E(e.message)+'</div>'; return; }
  CUR=p; renderMenu();
  $('bl_main').innerHTML=`<h1 class="bl_h1">${E(p.title)}</h1>
    <div class="bl_cm" style="margin-bottom:14px">${E(p.cat||'')} · 작성 ${E(p.created||'')}${p.updated&&p.updated!==p.created?' · 수정 '+E(p.updated):''}
      ${(p.tags||[]).map(t=>`<a href="#" class="bl_tag" data-t="${E(t)}">#${E(t)}</a>`).join(' ')}
      ${ADMIN?`<span style="float:right"><button class="scrrst" id="bl_edit" style="font-size:11px">✏ 수정</button> <button class="scrrst" id="bl_del" style="font-size:11px;color:#b91c1c">🗑 삭제</button></span>`:''}</div>
    <div class="bl_body" id="bl_body">${md2html(p.md||'')}</div>`;
  const toc=decorate($('bl_body'));
  $('bl_toc').innerHTML=toc.length?'<div class="bl_cat">목차</div>'+toc.map(t=>`<a href="#" data-h="${E(t.id)}" style="padding-left:${t.lv===3?14:0}px">${E(t.t)}</a>`).join(''):'';
  $('bl_toc').querySelectorAll('a').forEach(a=>a.onclick=e=>{e.preventDefault(); const h=document.getElementById(a.dataset.h); if(h) h.scrollIntoView({behavior:'smooth',block:'start'});});
  $('bl_main').querySelectorAll('.bl_tag').forEach(a=>a.onclick=e=>{e.preventDefault(); $('bl_q').value=a.dataset.t; search();});
  if(ADMIN){ $('bl_edit').onclick=()=>editor(p);
    $('bl_del').onclick=async()=>{ if(!confirm('이 글을 삭제할까요? 되돌릴 수 없습니다.')) return;
      try{ await api('/api/blog/post/'+encodeURIComponent(p.id),{method:'DELETE'}); await reload(); showHome(); }catch(e){ alert('삭제 실패: '+e.message); } }; }
  $('bl_main').scrollTop=0;
}

let stimer=null;
async function search(){
  const q=$('bl_q').value.trim(); if(!q){ showHome(); return; }
  let r; try{ r=await api('/api/blog/search?q='+encodeURIComponent(q)); }catch(e){ return; }
  if($('bl_q').value.trim()!==q) return;
  CUR=null; renderMenu(); $('bl_toc').innerHTML='';
  const hl=s=>{ let h=E(s); q.split(/\s+/).filter(Boolean).forEach(w=>{ h=h.replace(new RegExp(w.replace(/[.*+?^${}()|[\]\\]/g,'\\$&'),'gi'),m=>'<mark>'+m+'</mark>'); }); return h; };
  $('bl_main').innerHTML=`<h1 class="bl_h1">검색</h1><div class="note" style="margin-bottom:14px">“${E(q)}” — ${r.hits.length}건 (제목·태그·설명·본문, 여러 단어는 모두 포함된 글)</div>`+
    (r.hits.map(h=>`<a href="#" class="bl_card" data-id="${E(h.id)}"><div class="bl_ct">${hl(h.title)}</div><div class="bl_cd">${hl(h.snip||'')}</div>
      <div class="bl_cm">${E(h.cat||'')} · ${E((h.created||'').slice(0,10))}</div></a>`).join('')||'<div class="note">찾는 글이 없습니다. 다른 단어로 찾아보세요.</div>');
  bindCards($('bl_main'));
}

function editor(p){
  p=p||{}; CUR=null; renderMenu(); $('bl_toc').innerHTML='';
  $('bl_main').innerHTML=`<h1 class="bl_h1">${p.id?'글 수정':'새 글'}</h1>
    <div style="display:grid;grid-template-columns:1fr 180px;gap:8px;margin-bottom:8px">
      <input id="be_title" class="bl_in" placeholder="제목" value="${E(p.title||'')}">
      <input id="be_cat" class="bl_in" placeholder="카테고리 (예: AI)" value="${E(p.cat||'')}" list="be_cats"><datalist id="be_cats">${[...new Set(POSTS.map(x=>x.cat))].map(c=>`<option value="${E(c)}">`).join('')}</datalist></div>
    <input id="be_desc" class="bl_in" placeholder="한 줄 설명 (목록·검색 결과에 표시)" value="${E(p.desc||'')}" style="margin-bottom:8px">
    <input id="be_tags" class="bl_in" placeholder="태그 — 쉼표로 구분" value="${E((p.tags||[]).join(', '))}" style="margin-bottom:8px">
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px">
      <textarea id="be_md" class="bl_in" style="height:60vh;font-family:ui-monospace,Consolas,monospace;font-size:12.5px;line-height:1.55;resize:vertical" placeholder="마크다운으로 작성 — ## 제목, \`\`\`js 코드, | 표 |, ![그림](주소)">${E(p.md||'')}</textarea>
      <div id="be_prev" class="bl_body" style="height:60vh;overflow:auto;border:1px solid #e2e8f0;border-radius:8px;padding:4px 14px;background:#fff"></div></div>
    <div style="margin-top:10px;display:flex;gap:8px;align-items:center"><button id="be_save" class="scrrst" style="background:#e96900;color:#fff;border-color:#e96900;font-size:13px;padding:6px 16px">저장</button>
      <button id="be_cancel" class="scrrst" style="font-size:13px;padding:6px 14px">취소</button><span id="be_msg" class="note"></span></div>`;
  const prev=()=>{ $('be_prev').innerHTML=md2html($('be_md').value); decorate($('be_prev')); };
  let t=null; $('be_md').addEventListener('input',()=>{ clearTimeout(t); t=setTimeout(prev,250); }); prev();
  $('be_cancel').onclick=()=>p.id?openPost(p.id):showHome();
  $('be_save').onclick=async()=>{
    const body={id:p.id||'',title:$('be_title').value,cat:$('be_cat').value,desc:$('be_desc').value,md:$('be_md').value,
      tags:$('be_tags').value.split(',').map(s=>s.trim()).filter(Boolean)};
    $('be_msg').textContent='저장 중…';
    try{ const r=await api('/api/blog/post',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}); await reload(); openPost(r.id); }
    catch(e){ $('be_msg').textContent='저장 실패: '+e.message; }
  };
}

async function reload(){ const d=await api('/api/blog/posts'); POSTS=d.posts||[]; }

window.renderBlog=async function(){
  if(LOADED){ return; } LOADED=true;
  try{ const me=await fetch('/api/auth/me').then(r=>r.json()); ADMIN=!!(me&&me.ok); }catch(e){}
  $('bl_new').style.display=ADMIN?'':'none'; $('bl_new').onclick=()=>editor();
  $('bl_home').onclick=e=>{e.preventDefault(); $('bl_q').value=''; showHome();};
  $('bl_q').addEventListener('input',()=>{ clearTimeout(stimer); stimer=setTimeout(search,220); });
  try{ await reload(); }catch(e){ $('bl_main').innerHTML='<div class="note">목록을 불러오지 못했습니다: '+E(e.message)+'</div>'; return; }
  showHome();
};
document.addEventListener('keydown',e=>{ if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='k'){ const p=$('p_blog'); if(p&&p.classList.contains('on')){ e.preventDefault(); $('bl_q').focus(); $('bl_q').select(); } } });
})();
