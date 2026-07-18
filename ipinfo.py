#!/usr/bin/env python3
"""IP 신원조회 — 통신사(whois) + 도시(DB-IP City Lite, 로컬 mmdb).

방문자 IP 는 외부 API 로 나가지 않는다. 도시는 서버에 받아둔 파일에서 찾고,
통신사는 IP 등록정보(whois)를 조회한다. 결과는 영구 캐시한다 — IP 할당은
거의 바뀌지 않고, whois 서버에 같은 질문을 반복하지 않기 위해서다.

한계를 분명히 해둔다.
  · 도시 정확도는 유선 50~70%, 모바일(LTE/5G)은 교환국 위치라 사실상 무의미하다.
  · iCloud 사설 릴레이·VPN 은 실제 위치·통신사를 알 수 없다.
"""
import json, re, subprocess, threading, time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

BASE   = Path(__file__).parent
CACHE_F = BASE / "data" / "ipinfo.json"
MMDB_F  = BASE / "data" / "geo" / "dbip-city.mmdb"

_lock  = threading.Lock()
_cache = {}
_reader = None

try:
    import maxminddb
    if MMDB_F.exists():
        _reader = maxminddb.open_database(str(MMDB_F))
except Exception:
    _reader = None

def _load():
    global _cache
    try:
        _cache = json.loads(CACHE_F.read_text(encoding="utf-8"))
    except Exception:
        _cache = {}
_load()

def _save():
    try:
        CACHE_F.parent.mkdir(parents=True, exist_ok=True)
        tmp = CACHE_F.with_suffix(".tmp")
        tmp.write_text(json.dumps(_cache, ensure_ascii=False), encoding="utf-8")
        tmp.replace(CACHE_F)
    except Exception:
        pass

# ── 통신사 이름 정리 ────────────────────────────────────────
#   whois 원문은 법인명이라 알아보기 어렵다. 익숙한 이름으로 바꾸고,
#   유선/모바일 구분이 확실한 것만 표시한다.
ISP_MAP = [
    (r"sk\s*telecom|sktelecom",            "SKT",        "모바일"),
    (r"sk\s*broadband|broadnnet|hanaro",   "SK브로드밴드", "유선"),
    (r"kt\s*corp|kornet|korea\s*telecom",  "KT",         "유선"),
    (r"ktfwing|kt\s*mobile|kt\s*olleh",    "KT",         "모바일"),
    (r"lg\s*u\+?|lguplus|lgtelecom|dacom", "LG U+",      ""),
    (r"lg\s*powercomm|powercomm",          "LG U+",      "유선"),
    (r"sejong\s*telecom|세종",              "세종텔레콤",   "유선"),
    (r"drimnet|dreamline",                 "드림라인",     "유선"),
    (r"korea\s*cable|tbroad|dlive|hcn",    "케이블TV",    "유선"),
    (r"samsung",                           "삼성",        "사내망"),
    (r"amazon|aws",                        "AWS",        "데이터센터"),
    (r"google|gcp",                        "Google Cloud", "데이터센터"),
    (r"microsoft|azure",                   "Azure",      "데이터센터"),
    (r"oracle",                            "Oracle Cloud", "데이터센터"),
    (r"akamai",                            "Akamai",     "데이터센터"),
    (r"cloudflare",                        "Cloudflare", "데이터센터"),
    (r"digitalocean|linode|vultr|hetzner|ovh|contabo|scaleway",
                                           None,         "데이터센터"),
    (r"tencent|alibaba|huawei\s*cloud|baidu",
                                           None,         "데이터센터"),
]

def _norm_isp(raw: str):
    s = (raw or "").lower()
    for pat, name, kind in ISP_MAP:
        if re.search(pat, s):
            return (name or raw.strip()[:28]), kind
    return (raw or "").strip()[:28], ""

WHOIS_KEYS = re.compile(
    r"^(descr|netname|orgname|org-name|organization|owner|country)\s*:\s*(.+)$", re.I)
# KRNIC 은 한글 필드로 답한다. 게다가 넓은 대역 → 좁은 대역 순으로 여러 번 나오는데,
# 마지막(가장 좁은) 기관명이 실제 할당처다 — 회사·기관 전용망이면 여기서 드러난다.
KR_KEYS = re.compile(r"^(기관명|서비스명)\s*:\s*(.+)$")

# 한글 법인명 → 익숙한 이름
KR_ORG = [
    (r"에스케이텔레콤",              "SKT"),
    (r"에스케이브로드밴드|하나로",    "SK브로드밴드"),
    (r"케이티스카이라이프",          "KT스카이라이프"),
    (r"케이티|kt\b",                "KT"),
    (r"엘지유플러스|엘지데이콤|데이콤|파워콤", "LG U+"),
    (r"세종텔레콤",                 "세종텔레콤"),
]
# 서비스명 → 유선/모바일 (추측하지 않고 확실한 것만)
SVC_KIND = [
    (r"sk-?telecom-?net|sktelecom",  "모바일"),
    (r"kornet|broadnnet|hananet",     "유선"),
    (r"ktfwing|kt-?mobile",           "모바일"),
]

def _whois(ip: str) -> dict:
    try:
        out = subprocess.run(["whois", ip], capture_output=True, text=True,
                             timeout=12).stdout
    except Exception:
        return {}
    descr = netname = org = cc = svc = ""
    kr_orgs = []
    for ln in out.splitlines():
        s = ln.strip()
        m = WHOIS_KEYS.match(s)
        if m:
            k, v = m.group(1).lower(), m.group(2).strip()
            if   k == "descr"   and not descr:   descr = v
            elif k == "netname" and not netname: netname = v
            elif k in ("orgname", "org-name", "organization", "owner") and not org: org = v
            elif k == "country" and not cc:      cc = v.upper()[:2]
            continue
        m = KR_KEYS.match(s)
        if m:
            if m.group(1) == "기관명":
                kr_orgs.append(m.group(2).strip())
            elif not svc:
                svc = m.group(2).strip()
    return {"descr": descr, "netname": netname, "org": org, "cc": cc,
            "svc": svc, "kr_top": kr_orgs[0] if kr_orgs else "",
            "kr_last": kr_orgs[-1] if kr_orgs else ""}

def _kr_name(s: str) -> str:
    t = (s or "").lower().replace(" ", "")
    for pat, name in KR_ORG:
        if re.search(pat, t):
            return name
    return re.sub(r"^\(?주\)?식?회?사?\s*|\s*\(?주\)?$", "", (s or "").strip())[:24]

def _geo(ip: str) -> dict:
    if not _reader:
        return {}
    try:
        d = _reader.get(ip) or {}
    except Exception:
        return {}
    def nm(node):
        n = (node or {}).get("names") or {}
        return n.get("ko") or n.get("en") or ""
    sub = (d.get("subdivisions") or [{}])[0]
    city = re.sub(r"\s*\(.*\)$", "", nm(d.get("city")))       # "Seoul (Toegye-ro)" → "Seoul"
    return {"country": nm(d.get("country")),
            "cc": (d.get("country") or {}).get("iso_code", ""),
            "region": nm(sub), "city": city}

# iCloud 사설 릴레이는 애플이 Akamai/Cloudflare/Fastly 를 빌려 쓴다.
RELAY_HINT = re.compile(r"akamai|cloudflare|fastly", re.I)

def lookup(ip: str) -> dict:
    with _lock:
        hit = _cache.get(ip)
    if hit:
        return hit

    w, g = _whois(ip), _geo(ip)

    if w.get("kr_top"):                       # 국내 IP — KRNIC 한글 응답
        isp = _kr_name(w["kr_top"])
        kind = ""
        for pat, k in SVC_KIND:
            if re.search(pat, (w.get("svc") or "") + " " + (w.get("netname") or ""), re.I):
                kind = k
                break
        last = _kr_name(w.get("kr_last") or "")
        org  = last if (last and last != isp) else ""      # 회사·기관 전용망이면 여기 남는다
    else:
        raw = w.get("descr") or w.get("org") or w.get("netname") or ""
        isp, kind = _norm_isp(raw)
        org = ""
        if not kind and RELAY_HINT.search(raw):
            kind = "데이터센터"

    info = {
        "isp":     isp or "?",
        "org":     org,
        "kind":    kind,
        "netname": w.get("netname", "") or w.get("svc", ""),
        "country": g.get("country") or ("대한민국" if w.get("cc") == "KR" or w.get("kr_top") else ""),
        "cc":      g.get("cc") or w.get("cc") or ("KR" if w.get("kr_top") else ""),
        "region":  g.get("region", ""),
        "city":    g.get("city", ""),
        "ts":      int(time.time()),
    }
    with _lock:
        _cache[ip] = info
        if len(_cache) % 20 == 0:
            _save()
    return info

def lookup_many(ips, budget: int = 60) -> dict:
    """캐시에 없는 IP 만 조회한다. whois 는 느려서(IP당 1~3초) 한 번에 budget 개까지만.

    나머지는 다음 새로고침 때 채워진다 — 화면이 통째로 멎는 것보다 낫다.
    """
    ips  = list(dict.fromkeys(ips))
    with _lock:
        need = [ip for ip in ips if ip not in _cache][:budget]
    if need:
        with ThreadPoolExecutor(max_workers=10) as ex:
            list(ex.map(lookup, need))
        _save()
    with _lock:
        return {ip: _cache.get(ip) for ip in ips}

def pending(ips) -> int:
    with _lock:
        return sum(1 for ip in set(ips) if ip not in _cache)
