#!/usr/bin/env python3
"""로그인 인증 + 방문자 통계 (개발자 전용).

설계 원칙
  · UI만 숨기지 않는다 — /api/visitors 는 엔드포인트 자체가 세션을 검사한다.
  · 비밀번호는 평문으로 어디에도 저장하지 않는다 (PBKDF2-SHA256 200k회).
  · 무차별 대입은 IP 단위로 차단한다 (15분 내 5회 실패 → 15분 잠금).
  · 방문자 IP는 남의 개인정보이므로 로그인 없이는 단 한 줄도 나가지 않는다.
"""
import json, re, gzip, time, hmac, secrets, hashlib
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict
from fastapi import APIRouter, HTTPException, Request, Response

BASE     = Path(__file__).parent
AUTH_F   = BASE / "data" / "auth.json"        # {user, salt, hash, iter}
SESS_F   = BASE / "data" / "sessions.json"    # 재시작해도 로그인 유지
SETUP_F  = BASE / "data" / "setup_token.json" # 최초 1회 계정 등록용 (단발·만료)
LOG_DIR  = Path("/var/log/nginx")

SESS_TTL  = 14 * 24 * 3600      # 로그인 유지 14일
LOCK_N    = 5                   # 실패 허용 횟수
LOCK_WIN  = 900                 # 집계 구간 15분
LOCK_DUR  = 900                 # 잠금 시간 15분
PBKDF_IT  = 200_000

router = APIRouter()

# ── 세션 저장소 ────────────────────────────────────────────
def _load_sess() -> dict:
    try:
        d = json.loads(SESS_F.read_text())
        now = time.time()
        return {k: v for k, v in d.items() if v.get("exp", 0) > now}
    except Exception:
        return {}

def _save_sess(d: dict):
    try:
        SESS_F.parent.mkdir(parents=True, exist_ok=True)
        SESS_F.write_text(json.dumps(d))
        SESS_F.chmod(0o600)
    except Exception:
        pass

SESS  = _load_sess()
FAILS = defaultdict(list)       # ip -> [실패시각,...]

# ── 내 회선 목록 ───────────────────────────────────────────
#   로그인할 때마다 그 IP 를 자동 기록한다. 집·휴대폰·회사가 각각 다른 IP 이므로
#   여러 개가 쌓이는 게 정상이다. 통신사가 IP 를 바꿔도 다시 로그인하면 갱신된다.
MYIP_F = BASE / "data" / "my_ips.json"

def load_my_ips() -> dict:
    try:
        return json.loads(MYIP_F.read_text(encoding="utf-8"))
    except Exception:
        return {}

def save_my_ips(d: dict):
    try:
        MYIP_F.parent.mkdir(parents=True, exist_ok=True)
        MYIP_F.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass

def _auto_label(ip: str) -> str:
    """통신사 정보로 회선 성격을 추정해 이름을 붙여둔다 (수정 가능)."""
    try:
        import ipinfo
        g = ipinfo.lookup(ip)
    except Exception:
        return ""
    if g.get("kind") == "모바일":
        return f'휴대폰 ({g.get("isp","")})'
    if g.get("org"):
        return f'회사 ({g["org"]})'
    if g.get("kind") == "유선":
        return f'유선 ({g.get("isp","")})'
    return g.get("isp", "")

def remember_my_ip(ip: str):
    if not ip or ip in ("?", "127.0.0.1"):
        return
    d = load_my_ips()
    if ip not in d:
        d[ip] = {"label": _auto_label(ip), "since": datetime.now().strftime("%Y-%m-%d"),
                 "auto": True}
        save_my_ips(d)

def _geo_pending(ips) -> int:
    try:
        import ipinfo
        return ipinfo.pending(ips)
    except Exception:
        return 0

def _hash(pw: str, salt: str, it: int = PBKDF_IT) -> str:
    return hashlib.pbkdf2_hmac("sha256", pw.encode(), bytes.fromhex(salt), it).hex()

def client_ip(req: Request) -> str:
    return (req.headers.get("x-real-ip")
            or (req.headers.get("x-forwarded-for", "").split(",")[0].strip())
            or (req.client.host if req.client else "?"))

def current_user(req: Request):
    tok = req.cookies.get("nmr_sess")
    if not tok:
        return None
    s = SESS.get(tok)
    if not s or s.get("exp", 0) <= time.time():
        SESS.pop(tok, None)
        return None
    return s.get("u")

def require_login(req: Request) -> str:
    u = current_user(req)
    if not u:
        raise HTTPException(401, "로그인이 필요합니다")
    return u

# ── 인증 API ──────────────────────────────────────────────
@router.get("/api/auth/me")
def auth_me(request: Request):
    u = current_user(request)
    setup = False
    if not AUTH_F.exists() and SETUP_F.exists():
        try:
            setup = json.loads(SETUP_F.read_text()).get("exp", 0) > time.time()
        except Exception:
            setup = False
    return {"ok": bool(u), "user": u,
            "configured": AUTH_F.exists(), "setup": setup}

@router.post("/api/auth/login")
async def auth_login(request: Request, response: Response):
    ip  = client_ip(request)
    now = time.time()

    FAILS[ip] = [t for t in FAILS[ip] if now - t < LOCK_WIN]
    if len(FAILS[ip]) >= LOCK_N:
        wait = int((LOCK_DUR - (now - FAILS[ip][-1])) / 60) + 1
        raise HTTPException(429, f"로그인 시도가 너무 많습니다. {wait}분 후 다시 시도하세요.")

    if not AUTH_F.exists():
        raise HTTPException(503, "계정이 설정되지 않았습니다 (set_password.py 실행 필요)")
    try:
        body = await request.json()
    except Exception:
        body = {}
    user = str(body.get("user", ""))
    pw   = str(body.get("pw", ""))

    cfg = json.loads(AUTH_F.read_text())
    ok  = hmac.compare_digest(user, cfg["user"]) and hmac.compare_digest(
        _hash(pw, cfg["salt"], cfg.get("iter", PBKDF_IT)), cfg["hash"])

    if not ok:
        FAILS[ip].append(now)
        left = LOCK_N - len(FAILS[ip])
        raise HTTPException(401, f"아이디 또는 비밀번호가 올바르지 않습니다 (남은 시도 {max(left,0)}회)")

    FAILS.pop(ip, None)
    tok = secrets.token_urlsafe(32)
    SESS[tok] = {"u": user, "exp": now + SESS_TTL, "ip": ip}
    _save_sess(SESS)
    remember_my_ip(ip)                          # 이 회선은 '나'로 기억한다
    https = (request.headers.get("x-forwarded-proto") == "https"
             or request.url.scheme == "https")
    response.set_cookie("nmr_sess", tok, max_age=SESS_TTL, httponly=True,
                        samesite="lax", secure=https, path="/")
    return {"ok": True, "user": user, "secure": https}

@router.post("/api/auth/setup")
async def auth_setup(request: Request, response: Response):
    """최초 1회 계정 등록.

    서버에서 발급한 일회용 토큰이 있어야만 열린다. 토큰은 30분 뒤 만료되고
    성공하면 즉시 폐기된다. 덕분에 비밀번호는 브라우저 → 서버로만 흐르고,
    설정을 도와주는 사람(나)을 포함해 누구도 거치지 않는다.
    """
    ip, now = client_ip(request), time.time()
    FAILS[ip] = [t for t in FAILS[ip] if now - t < LOCK_WIN]
    if len(FAILS[ip]) >= LOCK_N:
        raise HTTPException(429, "시도가 너무 많습니다. 15분 후 다시 시도하세요.")
    if AUTH_F.exists():
        raise HTTPException(409, "이미 계정이 등록돼 있습니다.")
    if not SETUP_F.exists():
        raise HTTPException(403, "설정 토큰이 없습니다. 서버에서 발급이 필요합니다.")

    tk = json.loads(SETUP_F.read_text())
    if tk.get("exp", 0) < now:
        SETUP_F.unlink(missing_ok=True)
        raise HTTPException(403, "설정 토큰이 만료됐습니다. 새로 발급받으세요.")

    try:
        body = await request.json()
    except Exception:
        body = {}
    token = str(body.get("token", "")).strip()
    user  = str(body.get("user", "")).strip()
    pw    = str(body.get("pw", ""))

    if not hmac.compare_digest(token, tk.get("token", "")):
        FAILS[ip].append(now)
        raise HTTPException(403, "설정 토큰이 올바르지 않습니다.")
    if not user:
        raise HTTPException(400, "아이디를 입력하세요.")
    if len(pw) < 8:
        raise HTTPException(400, "비밀번호는 8자 이상이어야 합니다.")

    salt = secrets.token_hex(16)
    AUTH_F.write_text(json.dumps({"user": user, "salt": salt,
                                  "hash": _hash(pw, salt), "iter": PBKDF_IT}))
    AUTH_F.chmod(0o600)
    SETUP_F.unlink(missing_ok=True)             # 토큰 즉시 폐기

    tok = secrets.token_urlsafe(32)
    SESS[tok] = {"u": user, "exp": now + SESS_TTL, "ip": ip}
    _save_sess(SESS)
    remember_my_ip(ip)                          # 이 회선은 '나'로 기억한다
    https = (request.headers.get("x-forwarded-proto") == "https"
             or request.url.scheme == "https")
    response.set_cookie("nmr_sess", tok, max_age=SESS_TTL, httponly=True,
                        samesite="lax", secure=https, path="/")
    return {"ok": True, "user": user}

@router.post("/api/auth/logout")
def auth_logout(request: Request, response: Response):
    tok = request.cookies.get("nmr_sess")
    if tok:
        SESS.pop(tok, None)
        _save_sess(SESS)
    response.delete_cookie("nmr_sess", path="/")
    return {"ok": True}

# ── nginx 접근로그 파싱 ────────────────────────────────────
LOG_RE = re.compile(
    r'^(\S+) \S+ \S+ \[([^\]]+)\] "([A-Z]+) ([^ "]*)[^"]*" (\d{3}) (\S+) "([^"]*)" "([^"]*)"')

BOT_UA   = re.compile(r"bot|crawl|spider|slurp|scan|curl|wget|python|go-http|libwww|"
                      r"okhttp|java/|masscan|zgrab|nmap|httpx|censys|expanse|inspect|"
                      r"probe|fetch|monitor|uptime|headless|phantom|selenium", re.I)
PROBE    = re.compile(r"\.env|\.git|wp-|wordpress|phpmyadmin|/admin|\.php|/vendor/|"
                      r"/config|/actuator|/solr|/cgi-bin|\.aws|credential|/owa/|"
                      r"/telescope|/_ignition|/api/v1/pods|\.ssh|/registry/", re.I)
SESSION_GAP = 30 * 60          # 30분 이상 공백이면 별도 방문으로 센다

# 인앱 브라우저 — 어느 앱에서 링크를 눌러 들어왔는지가 여기서 드러난다.
INAPP = [
    (r"KAKAOTALK",                     "카카오톡"),
    (r"KAKAOSTORY",                    "카카오스토리"),
    (r"NAVER\(inapp",                  "네이버앱"),
    (r"NAVER",                         "네이버앱"),
    (r"whale",                         ""),               # 웨일은 정식 브라우저
    (r"Instagram",                     "인스타그램"),
    (r"FBAN|FBAV|FB_IAB",              "페이스북"),
    (r"Line/",                         "라인"),
    (r"BAND/",                         "밴드"),
    (r"Daum",                          "다음앱"),
    (r"Telegram",                      "텔레그램"),
    (r"KAKAO",                         "카카오"),
]

def _ua_parse(ua: str) -> dict:
    """기기·OS·브라우저·인앱 여부를 뽑는다. UA 는 위장 가능하므로 참고용이다."""
    if not ua or ua == "-":
        return {"os": "", "dev": "", "br": "", "app": "", "mob": False, "s": "?"}

    if   "iPhone" in ua:     os_, dev = "iOS", "아이폰"
    elif "iPad" in ua:       os_, dev = "iPadOS", "아이패드"
    elif "Android" in ua:    os_, dev = "Android", "안드로이드"
    elif "Windows" in ua:    os_, dev = "Windows", "PC"
    elif "Macintosh" in ua:  os_, dev = "macOS", "맥"
    elif "Linux" in ua:      os_, dev = "Linux", "PC"
    else:                    os_, dev = "", ""

    m = re.search(r"(?:iPhone )?OS (\d+)[_.](\d+)", ua)
    if m and os_ in ("iOS", "iPadOS"):
        os_ += f" {m.group(1)}.{m.group(2)}"
    m = re.search(r"Android (\d+)", ua)
    if m:
        os_ = f"Android {m.group(1)}"
    m = re.search(r"Windows NT 10\.0", ua)
    if m:
        os_ = "Windows 10/11"

    app = ""
    for pat, name in INAPP:
        if re.search(pat, ua, re.I):
            app = name
            break

    br = ""
    for pat, name in (("Whale", "웨일"), ("Edg/", "Edge"), ("OPR/", "Opera"),
                      ("SamsungBrowser", "삼성인터넷"), ("Firefox/", "Firefox"),
                      ("CriOS", "Chrome"), ("Chrome/", "Chrome"), ("Safari/", "Safari")):
        if pat in ua:
            br = name
            break
    m = re.search(r"(?:Whale|Edg|OPR|Chrome|CriOS|Firefox|Version)/(\d+)", ua)
    if br and m:
        br += " " + m.group(1)

    mob = bool(re.search(r"Mobile|Android|iPhone|iPad", ua))
    label = " · ".join(x for x in (dev, os_, br) if x) or ua[:40]
    if app:
        label = f"{app} 인앱 · {label}"
    return {"os": os_, "dev": dev, "br": br, "app": app, "mob": mob, "s": label}

def _ua_short(ua: str) -> str:
    return _ua_parse(ua)["s"]

def _iter_lines(days: int):
    files = [LOG_DIR / "access.log"]
    if days > 1:
        files.append(LOG_DIR / "access.log.1")
        files += sorted(LOG_DIR.glob("access.log.*.gz"))[: max(0, days - 2)]
    for f in files:
        if not f.exists():
            continue
        try:
            op = gzip.open if f.suffix == ".gz" else open
            with op(f, "rt", errors="replace") as fh:
                for ln in fh:
                    yield ln
        except PermissionError:
            continue

def build_stats(days: int = 1) -> dict:
    since = datetime.now() - timedelta(days=days)
    by_ip = defaultdict(list)
    total = 0

    for ln in _iter_lines(days):
        m = LOG_RE.match(ln)
        if not m:
            continue
        ip, ts, mth, path, st, sz, ref, ua = m.groups()
        if ip.startswith("127.") or ip == "::1":
            continue
        try:
            t = datetime.strptime(ts.split()[0], "%d/%b/%Y:%H:%M:%S")
        except ValueError:
            continue
        if t < since:
            continue
        total += 1
        by_ip[ip].append((t, path, int(st), ua, ref,
                          int(sz) if sz.isdigit() else 0))

    sessions, bots = [], []
    hourly = defaultdict(lambda: {"h": 0, "b": 0})

    for ip, evs in by_ip.items():
        evs.sort()
        uas    = {e[3] for e in evs}
        probes = sum(1 for e in evs if PROBE.search(e[1]))
        errs   = sum(1 for e in evs if e[2] >= 400)
        # 진짜 브라우저는 화면을 한 번 열면 app.js 와 /api/ 를 반드시 줄줄이 부른다.
        # 그 흔적이 아예 없으면, UA 가 크롬이라고 우겨도 브라우저가 아니다.
        # (UA 는 얼마든지 위장되므로 UA 만으로 판정하지 않는다)
        real = sum(1 for e in evs
                   if e[1].startswith("/api/") or e[1].endswith(".js"))
        if probes > 0:
            why = "침투시도"
        elif all(BOT_UA.search(u or "") for u in uas):
            why = "봇 UA"
        elif len(evs) >= 5 and errs / len(evs) > 0.9:
            why = "오류만 발생"
        elif real == 0:
            why = "화면 안 열고 찔러봄"
        else:
            why = ""
        is_bot = bool(why)

        for e in evs:
            hourly[e[0].hour]["b" if is_bot else "h"] += 1

        if is_bot:
            bots.append({
                "ip": ip, "n": len(evs), "why": why,
                "first": evs[0][0].strftime("%m-%d %H:%M"),
                "last":  evs[-1][0].strftime("%m-%d %H:%M"),
                "probe": probes,
                "ua": _ua_short(next(iter(uas))),
                "paths": sorted({e[1][:48] for e in evs if PROBE.search(e[1])})[:5]
                         or sorted({e[1][:48] for e in evs})[:3],
            })
            continue

        # 30분 이상 끊기면 별도 방문으로 분리
        chunk = [evs[0]]
        for prev, cur in zip(evs, evs[1:]):
            if (cur[0] - prev[0]).total_seconds() > SESSION_GAP:
                sessions.append((ip, chunk))
                chunk = []
            chunk.append(cur)
        sessions.append((ip, chunk))

    # 통신사·도시 조회 (캐시 우선, 새 IP 는 건수 제한)
    geo = {}
    try:
        import ipinfo
        geo = ipinfo.lookup_many([ip for ip, _ in sessions], budget=60)
    except Exception:
        pass
    mine = load_my_ips()

    out = []
    for ip, ch in sessions:
        pages = [e[1] for e in ch if not e[1].startswith(("/api/", "/charts/"))
                 and not e[1].endswith((".js", ".css", ".png", ".ico", ".map"))]
        u  = _ua_parse(ch[-1][3])
        g  = geo.get(ip) or {}
        # iCloud 사설 릴레이 — 애플이 Akamai·Cloudflare·Fastly 를 빌려 쓰므로
        # '데이터센터인데 사파리로 들어옴' 조합이면 릴레이로 본다. 실제 위치는 알 수 없다.
        relay = bool(g.get("kind") == "데이터센터"
                     and re.search(r"akamai|cloudflare|fastly", g.get("isp", ""), re.I)
                     and u["br"].startswith("Safari"))
        out.append({
            "ip": ip,
            "start": ch[0][0].strftime("%m-%d %H:%M:%S"),
            "end":   ch[-1][0].strftime("%m-%d %H:%M:%S"),
            "dur":   round((ch[-1][0] - ch[0][0]).total_seconds() / 60, 1),
            "reqs":  len(ch),
            "kb":    round(sum(e[5] for e in ch) / 1024, 1),
            "ua":    u["s"], "dev": u["dev"], "os": u["os"], "br": u["br"],
            "app":   u["app"], "mob": u["mob"],
            "isp":   g.get("isp", ""), "line": g.get("kind", ""),
            "org":   g.get("org", ""),
            "loc":   " ".join(x for x in (g.get("region", ""), g.get("city", "")) if x),
            "cc":    g.get("cc", ""), "country": g.get("country", ""),
            "relay": relay,
            "me":    ip in mine,
            "label": mine.get(ip, {}).get("label", ""),
            "ref":   next((e[4] for e in ch if e[4] and e[4] != "-"
                           and "141.147.160.13" not in e[4]
                           and "namoobi" not in e[4]), ""),
            "last":  ch[-1][1][:52],
            "pages": len(pages),
        })
    out.sort(key=lambda r: r["start"], reverse=True)

    # 동일인 추정 — IP 가 달라도 기기·브라우저·통신사가 같으면 같은 사람일 가능성이 높다.
    # 어디까지나 추정이다. 통신사 IP 는 수시로 바뀌고, 같은 기종을 쓰는 남일 수도 있다.
    fps = defaultdict(list)
    for r in out:
        if r["me"]:
            continue
        fp = f'{r["dev"]}|{r["os"]}|{r["br"]}|{r["isp"]}'
        if r["dev"] or r["br"]:
            fps[fp].append(r)
    gid = 0
    groups = []
    for fp, rows in fps.items():
        ips = {r["ip"] for r in rows}
        if len(ips) < 2:
            continue
        gid += 1
        for r in rows:
            r["grp"] = gid
        groups.append({
            "id": gid, "who": rows[0]["ua"], "isp": rows[0]["isp"],
            "ips": sorted(ips), "visits": len(rows),
            "reqs": sum(r["reqs"] for r in rows),
            "first": min(r["start"] for r in rows),
            "last":  max(r["end"] for r in rows),
            "locs":  sorted({r["loc"] for r in rows if r["loc"]})[:4],
            "apps":  sorted({r["app"] for r in rows if r["app"]}),
        })
    groups.sort(key=lambda g: -g["reqs"])

    paths = defaultdict(int)
    for ip, ch in sessions:
        for e in ch:
            if e[1].startswith("/api/"):
                paths[e[1].split("?")[0][:44]] += 1
    bots.sort(key=lambda r: -r["n"])

    others = [r for r in out if not r["me"]]
    return {
        "as_of": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "days": days,
        "summary": {
            "visitors":  len({s["ip"] for s in out}),
            "visits":    len(out),
            "requests":  total,
            "bot_ips":   len(bots),
            "bot_reqs":  sum(b["n"] for b in bots),
            "probes":    sum(b["probe"] for b in bots),
            "me_visits": len(out) - len(others),
            "others":    len({r["ip"] for r in others}),
            "inapp":     len({r["ip"] for r in others if r["app"]}),
            "geo_wait":  _geo_pending([ip for ip, _ in sessions]),
        },
        "groups":   groups[:20],
        "sessions": out[:300],
        "bots":     bots[:60],
        "hourly":   [{"hour": h, "human": hourly[h]["h"], "bot": hourly[h]["b"]}
                     for h in range(24)],
        "paths":    sorted([{"path": k, "n": v} for k, v in paths.items()],
                           key=lambda r: -r["n"])[:25],
    }

@router.get("/api/visitors/myips")
def my_ips_get(request: Request):
    require_login(request)
    d = load_my_ips()
    try:
        import ipinfo
        for ip, v in d.items():
            g = ipinfo.lookup(ip) if ip in (ipinfo._cache or {}) else {}
            v["isp"] = g.get("isp", "")
            v["loc"] = " ".join(x for x in (g.get("region", ""), g.get("city", "")) if x)
    except Exception:
        pass
    return {"ips": d, "you": client_ip(request)}

@router.post("/api/visitors/myips")
async def my_ips_set(request: Request):
    """방문자 표에서 '나로 표시 / 해제'."""
    require_login(request)
    try:
        body = await request.json()
    except Exception:
        body = {}
    ip = str(body.get("ip", "")).strip()
    if not re.fullmatch(r"[0-9a-fA-F.:]{3,45}", ip):
        raise HTTPException(400, "IP 형식이 올바르지 않습니다")
    d = load_my_ips()
    if body.get("remove"):
        d.pop(ip, None)
    else:
        lb = str(body.get("label", "")).strip()[:40]
        d[ip] = {"label": lb or _auto_label(ip),
                 "since": d.get(ip, {}).get("since", datetime.now().strftime("%Y-%m-%d")),
                 "auto": False}
    save_my_ips(d)
    _cache["out"] = None                        # 표시가 바로 반영되게 캐시 비움
    return {"ok": True, "count": len(d)}

_cache = {"t": 0, "d": 0, "out": None}

@router.get("/api/visitors")
def visitors(request: Request, days: int = 1):
    require_login(request)                      # ← UI가 아니라 여기서 막는다
    days = max(1, min(int(days), 14))
    now = time.time()
    if _cache["out"] and _cache["d"] == days and now - _cache["t"] < 60:
        out = dict(_cache["out"])
    else:
        out = build_stats(days)
        _cache.update(t=now, d=days, out=out)
        out = dict(out)
    out["you"] = client_ip(request)             # 내 접속을 표에서 구분해 준다
    return out
