/* ══════════════════════════════════════════════════════════════════
   개발자 로그인 + 방문자 통계 탭
   화면을 숨기는 것은 편의일 뿐 보안이 아니다 — 실제 차단은 서버(/api/visitors)가 한다.
   ══════════════════════════════════════════════════════════════════ */
(function(){
  const $  = id => document.getElementById(id);
  const ov = $('lg_ov'), tab = $('tab_vis'), lock = $('auth_btn');
  if(!ov || !tab || !lock) return;
  let me = null, mode = 'login';       // 'login' | 'setup'(최초 계정 등록)

  const esc = s => String(s==null?'':s).replace(/[&<>"]/g,
                c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));

  // ── 로그인 상태 반영 ────────────────────────────────────
  function paint(){
    tab.style.display = me ? '' : 'none';
    lock.classList.toggle('on', !!me);
    lock.title = me ? (me + ' 로그인됨 — 방문자 탭 열기') : '개발자 로그인';
    lock.textContent = me ? ('🔓 ' + me) : '🔒';
    $('auth_out').classList.toggle('on', !!me);
    const w = $('vs_who'); if(w) w.textContent = me ? (me + ' · 관리자 전용') : '관리자 전용';
  }

  async function logout(){
    await fetch('/api/auth/logout', {method:'POST'}).catch(()=>{});
    me = null; paint();
    const h = $('go_home'); if(h) h.click();
  }

  fetch('/api/auth/me').then(r=>r.json()).then(d=>{
    me = d.ok ? d.user : null;
    mode = (!d.configured && d.setup) ? 'setup' : 'login';
    paint();
  }).catch(()=>{});

  // ── 로그인 창 ───────────────────────────────────────────
  function open(){
    const setup = (mode === 'setup');
    $('lg_ttl').textContent = setup ? '최초 계정 설정' : '개발자 로그인';
    $('lg_sub').innerHTML   = setup
      ? '서버에서 발급한 <b>일회용 토큰</b>과 함께 쓸 아이디·비밀번호를 정한다. 비밀번호는 이 브라우저에서 서버로만 전달되고, 해시로만 저장된다.'
      : '방문자 통계에는 다른 방문자의 IP가 담긴다. 본인만 열람한다.';
    $('lg_go').textContent  = setup ? '계정 만들기' : '로그인';
    $('lg_tk').style.display  = setup ? '' : 'none';
    $('lg_pw2').style.display = setup ? '' : 'none';
    $('lg_pw').placeholder    = setup ? '비밀번호 (8자 이상)' : '비밀번호';
    $('lg_err').textContent = '';
    $('lg_pw').value = ''; $('lg_pw2').value = '';
    $('lg_warn').style.display = (location.protocol === 'https:') ? 'none' : 'block';
    ov.classList.add('on');
    setTimeout(()=>{ (setup ? $('lg_tk') : ($('lg_id').value ? $('lg_pw') : $('lg_id'))).focus(); }, 40);
  }
  const close = () => ov.classList.remove('on');

  lock.addEventListener('click', ()=>{ me ? tab.click() : open(); });
  $('lg_x').addEventListener('click', close);
  ov.addEventListener('click', e => { if(e.target === ov) close(); });
  document.addEventListener('keydown', e => { if(e.key === 'Escape' && ov.classList.contains('on')) close(); });

  async function login(){
    const btn = $('lg_go'), err = $('lg_err'), setup = (mode === 'setup');
    const user = $('lg_id').value.trim(), pw = $('lg_pw').value;
    if(!user || !pw){ err.textContent = '아이디와 비밀번호를 모두 입력하세요.'; return; }
    if(setup){
      if(!$('lg_tk').value.trim()){ err.textContent = '설정 토큰을 입력하세요.'; return; }
      if(pw.length < 8){ err.textContent = '비밀번호는 8자 이상이어야 합니다.'; return; }
      if(pw !== $('lg_pw2').value){ err.textContent = '두 번 입력한 비밀번호가 다릅니다.'; return; }
    }
    btn.disabled = true; err.textContent = '';
    try{
      const body = setup ? {token:$('lg_tk').value.trim(), user, pw} : {user, pw};
      const r = await fetch(setup ? '/api/auth/setup' : '/api/auth/login', {
        method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify(body)
      });
      const d = await r.json().catch(()=>({}));
      if(!r.ok){ err.textContent = d.detail || '실패했습니다.'; return; }
      me = d.user; mode = 'login'; paint(); close(); tab.click();
    }catch(e){ err.textContent = '서버에 연결하지 못했습니다.'; }
    finally{ btn.disabled = false; }
  }
  $('lg_go').addEventListener('click', login);
  ['lg_tk','lg_id','lg_pw','lg_pw2'].forEach(id => $(id).addEventListener('keydown',
    e => { if(e.key === 'Enter') login(); }));

  $('vs_out').addEventListener('click', logout);
  $('auth_out').addEventListener('click', logout);

  // ── 방문자 통계 렌더 ────────────────────────────────────
  function render(s){
    const q = s.summary, body = $('vs_body');
    $('vs_as').textContent = '집계 ' + s.as_of;

    const mx = Math.max(1, ...s.hourly.map(h => h.human + h.bot));
    const bars = s.hourly.map(h =>
      `<i style="height:${Math.round((h.human/mx)*100)}%" title="${h.hour}시 · 사람 ${h.human} · 봇 ${h.bot}"></i>`).join('');
    const bbar = s.hourly.map(h =>
      `<i class="b" style="height:${Math.round((h.bot/mx)*100)}%" title="${h.hour}시 봇 ${h.bot}"></i>`).join('');

    const dur = d => d >= 60 ? (d/60).toFixed(1)+'시간' : d+'분';
    const line = r => {
      if(r.relay) return '<span title="애플 iCloud 사설 릴레이 — 실제 통신사·위치를 알 수 없다">🍎 릴레이</span>';
      const t = [esc(r.isp)];
      if(r.line) t.push('<span style="color:var(--tx2)">'+esc(r.line)+'</span>');
      if(r.org)  t.push('<b style="color:#7c3aed" title="회사·기관 전용망">'+esc(r.org)+'</b>');
      return t.join(' ') || '<span style="color:var(--tx2)">조회 중</span>';
    };
    const dev = r => {
      let t = '';
      if(r.app) t += '<b style="color:#d97706">'+esc(r.app)+'</b> ';
      t += esc([r.dev, r.os, r.br].filter(Boolean).join(' · ')) || esc(r.ua);
      return t;
    };
    const mkRows = list => list.map(r=>`<tr class="${r.me?'vs-me':''}">
        <td>${esc(r.ip)}${r.me?' <b style="color:#2b57d0">(나)</b>':''}
            ${r.grp?'<span class="vs-g" title="같은 사람으로 추정되는 묶음">#'+r.grp+'</span>':''}</td>
        <td>${line(r)}</td>
        <td>${esc(r.relay ? '—' : (r.loc || r.country || ''))}</td>
        <td>${dev(r)}</td>
        <td>${esc(r.start)}</td><td>${esc(r.end)}</td><td>${dur(r.dur)}</td>
        <td>${r.reqs}</td>
        <td style="color:var(--tx2)">${esc(r.last)}</td>
        <td><button class="vs-mk" data-ip="${esc(r.ip)}" data-me="${r.me?1:0}">${
            r.me ? '나 해제' : '나로 표시'}</button></td></tr>`).join('');

    const meRows = mkRows(s.sessions.filter(r=>r.me))
      || '<tr><td colspan="10" style="color:var(--tx2);padding:14px">아직 없다 — 로그인하면 그 회선이 자동으로 등록된다.</td></tr>';
    const otRows = mkRows(s.sessions.filter(r=>!r.me))
      || '<tr><td colspan="10" style="color:var(--tx2);padding:14px">기록 없음</td></tr>';

    const grows = (s.groups||[]).map(g=>`<tr>
        <td><span class="vs-g">#${g.id}</span></td>
        <td>${esc(g.who)}${g.apps.length?' <b style="color:#d97706">'+esc(g.apps.join(','))+'</b>':''}</td>
        <td>${esc(g.isp)}</td><td>${g.ips.length}개</td><td>${g.visits}</td><td>${g.reqs}</td>
        <td>${esc(g.locs.join(' / '))}</td>
        <td style="color:var(--tx2)">${esc(g.first)} ~ ${esc(g.last)}</td></tr>`).join('')
      || '<tr><td colspan="8" style="color:var(--tx2);padding:14px">묶인 그룹 없음</td></tr>';

    const brows = s.bots.map(b=>`<tr>
        <td>${esc(b.ip)}</td><td>${b.n}</td><td>${esc(b.why)}</td>
        <td>${esc(b.first)} ~ ${esc(b.last)}</td><td>${esc(b.ua)}</td>
        <td style="color:var(--tx2)">${esc(b.paths.join(' , ')).slice(0,90)}</td></tr>`).join('')
      || '<tr><td colspan="6" style="color:var(--tx2);padding:14px">없음</td></tr>';

    const prows = s.paths.map(p=>`<tr><td>${esc(p.path)}</td><td>${p.n}</td></tr>`).join('');

    body.innerHTML = `
      <div class="vs-k">
        <div><b style="color:#2b57d0">${q.others}</b><span>나 아닌 방문자</span></div>
        <div><b>${q.me_visits}</b><span>내 방문</span></div>
        <div><b style="color:#d97706">${q.inapp}</b><span>카톡·앱에서 유입</span></div>
        <div><b>${q.requests.toLocaleString()}</b><span>총 요청</span></div>
        <div><b style="color:#b7791f">${q.bot_ips}</b><span>봇 IP</span></div>
        <div><b style="color:#c0392b">${q.probes}</b><span>침투 시도 (차단됨)</span></div>
      </div>
      ${q.geo_wait ? '<p class="note" style="margin:-6px 0 12px">통신사·위치 조회가 '
        + q.geo_wait + '건 남았다. 새로고침하면 이어서 채워진다.</p>' : ''}

      <div class="grid g2">
        <div class="card"><div class="k">시간대별 접속 — 사람</div>
          <div class="vs-bar">${bars}</div>
          <div class="vs-hx">${[0,6,12,18].map(h=>`<span style="flex:6">${h}시</span>`).join('')}</div></div>
        <div class="card"><div class="k">시간대별 접속 — 봇</div>
          <div class="vs-bar">${bbar}</div>
          <div class="vs-hx">${[0,6,12,18].map(h=>`<span style="flex:6">${h}시</span>`).join('')}</div></div>
      </div>

      <h2 style="margin-top:18px">나 아닌 방문자<em>30분 이상 끊기면 별도 방문</em></h2>
      <div class="box" style="overflow:auto;max-height:460px"><table>
        <thead><tr><th>IP</th><th>통신사 · 회선</th><th>위치</th><th>기기 · 앱</th>
          <th>들어온 시각</th><th>마지막 요청</th><th>체류</th><th>요청</th>
          <th>마지막 화면</th><th></th></tr></thead>
        <tbody>${otRows}</tbody></table></div>

      <h2 style="margin-top:18px">동일인 추정 묶음<em>IP가 달라도 기기·브라우저·통신사가 같은 경우</em></h2>
      <div class="box" style="overflow:auto;max-height:300px"><table>
        <thead><tr><th>묶음</th><th>기기 · 브라우저</th><th>통신사</th><th>IP</th>
          <th>방문</th><th>요청</th><th>위치</th><th>기간</th></tr></thead>
        <tbody>${grows}</tbody></table></div>

      <h2 style="margin-top:18px">내 접속<em>로그인한 회선은 자동 등록된다</em></h2>
      <div class="box" style="overflow:auto;max-height:260px"><table>
        <thead><tr><th>IP</th><th>통신사 · 회선</th><th>위치</th><th>기기 · 앱</th>
          <th>들어온 시각</th><th>마지막 요청</th><th>체류</th><th>요청</th>
          <th>마지막 화면</th><th></th></tr></thead>
        <tbody>${meRows}</tbody></table></div>

      <h2 style="margin-top:18px">봇 · 스캐너<em>사람과 분리해 집계 — 전부 차단됨</em></h2>
      <div class="box" style="overflow:auto;max-height:340px"><table>
        <thead><tr><th>IP</th><th>요청</th><th>판정 근거</th><th>기간</th>
          <th>자칭 브라우저</th><th>노린 경로</th></tr></thead>
        <tbody>${brows}</tbody></table></div>

      <h2 style="margin-top:18px">많이 불린 API<em>사람 요청만</em></h2>
      <div class="box" style="overflow:auto;max-height:280px"><table>
        <thead><tr><th>경로</th><th>호출</th></tr></thead><tbody>${prows}</tbody></table></div>

      <p class="note" style="margin-top:12px">
        <b>봇 판정</b> — 진짜 브라우저는 화면을 열면 app.js 와 /api/ 를 반드시 함께 부른다.
        그 흔적 없이 한두 번 찔러보고 사라지면 스캐너로 본다. 자칭 브라우저(User-Agent)는
        얼마든지 위장할 수 있어 판정에 쓰지 않는다.<br>
        <b>믿을 만한 것 / 아닌 것</b> — 통신사와 회사망은 IP 등록정보라 정확하다.
        도시는 유선도 절반 남짓만 맞고, <b>모바일은 교환국 위치라 실제 있는 곳이 아니다</b>.
        기기·앱은 위장 가능한 자기 신고값이다. 동일인 묶음은 어디까지나 추정으로,
        같은 기종을 쓰는 다른 사람일 수 있다.</p>`;

    body.querySelectorAll('.vs-mk').forEach(b => b.addEventListener('click', async ()=>{
      b.disabled = true;
      await fetch('/api/visitors/myips', {
        method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({ip: b.dataset.ip, remove: b.dataset.me === '1'})
      }).catch(()=>{});
      load();
    }));
  }

  async function load(){
    const body = $('vs_body');
    body.innerHTML = '<div class="soon">불러오는 중…</div>';
    try{
      const r = await fetch('/api/visitors?days=' + $('vs_days').value);
      if(r.status === 401){
        me = null; paint();
        body.innerHTML = '<div class="soon">세션이 만료됐다. 다시 로그인하세요.</div>';
        open(); return;
      }
      if(!r.ok) throw new Error(r.status);
      render(await r.json());
    }catch(e){
      body.innerHTML = '<div class="soon">불러오지 못했습니다 (' + esc(e.message) + ')</div>';
    }
  }

  tab.addEventListener('click', load);
  $('vs_rf').addEventListener('click', load);
  $('vs_days').addEventListener('change', load);
})();
