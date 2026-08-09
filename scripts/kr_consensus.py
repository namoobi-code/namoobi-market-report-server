#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""kr_consensus.py — 한국 종목 분기 컨센서스 수집 (2026-08-09 신설 · 매일 07:20 cron).

왜 필요한가
-----------
미국은 실적발표 때 회사가 **가이던스**를 직접 주지만 한국은 그런 문화가 없다.
대신 한국은 DART '영업(잠정)실적' 공정공시가 최초 발표처이고(earnings_watch.py 가 5분마다 감시),
그 숫자가 **증권사 컨센서스 대비 얼마나 벗어났는가**가 곧 주가 충격의 크기다.
그동안 earnings_watch 는 전년동기比(YoY)만 계산했다 — 컨센 대비가 빠져 있었다.

소스 (무료 · 실측 2026-08-09)
------------------------------
navercomp.wisereport.co.kr 의 '주요재무정보' ajax 표(cF1001.aspx).
  · 분기 헤더에 (E) 가 붙은 열이 컨센서스 = 최근 3개월 증권사 추정치 평균
  · 실측 삼성전자: 2026/06(E) 매출 1,738,644 · 영업이익(발표기준) 850,494  (단위 억원)
  · encparam 은 c1010001.aspx 한 번만 받아 **전 종목에 재사용 가능**(실측 확인)
    → 종목당 호출 1회

리비전
------
미국(Yahoo)은 30·90일 전 추정치를 함께 주지만 한국은 **현재값만** 온다.
→ 매일 스냅샷을 SQLite 에 쌓아 직접 차분한다. 30일치가 모여야 op30 이 채워진다.

산출
----
  data/db/kr_consensus.sqlite  snap(code, d, period, sales, op, ni)   일별 스냅샷
  data/db/kr_consensus.json    {asof, r:{code:{p,sales,op,ni,op7,op30,rc7,rc30,tp}}}
    p    = 가장 가까운 미래 분기(E)
    op7  = 7일 전 대비 영업이익 컨센 변화율 · op30 = 30일 전 대비
    rc7  = 최근 7일 증권사 리포트 건수(네이버) · tp = 목표주가 평균

사용: kr_consensus.py [--limit N] [--workers N]
"""
import json, re, sqlite3, sys, time, urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
POOL = BASE / "data" / "db" / "screener_pool.json"
DB = BASE / "data" / "db" / "kr_consensus.sqlite"
OUT = BASE / "data" / "db" / "kr_consensus.json"
UA = {"User-Agent": "Mozilla/5.0", "Referer": "https://navercomp.wisereport.co.kr/"}
ARG = lambda k, d: (int(sys.argv[sys.argv.index(k) + 1]) if k in sys.argv else d)
LIMIT = ARG("--limit", 0)
WORKERS = ARG("--workers", 6)

SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS snap(
  code TEXT NOT NULL, d TEXT NOT NULL, period TEXT NOT NULL,
  sales REAL, op REAL, ni REAL,
  PRIMARY KEY(code, d, period)
) WITHOUT ROWID;
CREATE INDEX IF NOT EXISTS ix_snap_cd ON snap(code, d);
"""


def get(u, timeout=25):
    return urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=timeout).read().decode("utf-8", "replace")


def num(t):
    t = (t or "").replace(",", "").strip()
    if not t or t in ("-", "N/A"):
        return None
    try:
        return float(t)
    except Exception:
        return None


_CLEAN = lambda x: re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", x)).strip()


def encparam():
    """전 종목 공용 토큰 — 아무 종목 페이지에서 1회만 받으면 된다(실측 재사용 확인)."""
    b = get("https://navercomp.wisereport.co.kr/v2/company/c1010001.aspx?cmp_cd=005930")
    m = re.search(r"encparam\s*[:=]\s*['\"]([^'\"]+)", b)
    if not m:
        raise SystemExit("encparam 추출 실패 — WISEreport 페이지 구조 변경 의심")
    return m.group(1)


def quarters(code, enc, freq="Q"):
    """→ [(period, is_est, sales, op, ni)]  기간 오름차순. 억원 단위(DART 파서와 동일).
    freq='Y' 면 연간 표 — 같은 구조라 파서를 공유한다(실측: 2028/12(E)까지 제공)."""
    h = get(f"https://navercomp.wisereport.co.kr/v2/company/ajax/cF1001.aspx"
            f"?cmp_cd={code}&fin_typ=0&freq_typ={freq}&encparam={enc}")
    heads = [_CLEAN(t) for t in re.findall(r"<th[^>]*>(.*?)</th>", h, re.S)]
    pers = [x for x in heads if re.search(r"\d{4}/\d{2}", x)]
    if not pers:
        return []
    rows = {}
    for r in re.findall(r"<tr[^>]*>(.*?)</tr>", h, re.S):
        c = [_CLEAN(x) for x in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", r, re.S)]
        if not c:
            continue
        # '영업이익'은 컨센 열이 비어 있고 '영업이익(발표기준)'에만 채워진다(실측) → 후자 우선
        key = {"매출액": "sales", "영업이익(발표기준)": "op", "당기순이익": "ni"}.get(c[0])
        if key and (key != "op" or "op" not in rows):
            rows[key] = c[1:1 + len(pers)]
    out = []
    for i, p in enumerate(pers):
        m = re.match(r"(\d{4}/\d{2})(\(E\))?", p)
        if not m:
            continue
        gv = lambda k: num(rows.get(k, [None] * len(pers))[i]) if rows.get(k) and i < len(rows[k]) else None
        out.append((m.group(1), bool(m.group(2)), gv("sales"), gv("op"), gv("ni")))
    return out


_TPRV_RE = re.compile(r'id="cTB24".*?</table>', re.S)

def tp_revision(html):
    """증권사별 목표주가 변동표(#cTB24) → 최근 30일 리포트의 평균 목표가 변동률.

    한국은 이익 추정치 리비전 과거값을 주는 무료 소스가 없어(미국 Yahoo 와 달리)
    스냅샷이 30일 쌓여야 op30 이 나온다. 그런데 이 표는 **각 증권사가 직전 목표가를 얼마나
    바꿨는지**를 리포트 발간일과 함께 이미 갖고 있다 → 기다리지 않고 오늘 바로 쓸 수 있는
    전망 변화 지표다(실측 SK하이닉스 2026-07-30: 신한 −35.7%·한화 −26.7%·한투 +23.7% …).

    목표주가는 이익 추정과 목표 배수를 곱해 만든 값이라 이익 전망 변화를 반영한다.
    다만 배수(멀티플) 조정만으로도 움직이므로 **이익 리비전과 동일하지는 않다**.
    """
    m = _TPRV_RE.search(html)
    if not m:
        return {}
    now = datetime.now()
    cut30 = (now - timedelta(days=30)).strftime("%y/%m/%d")
    cut90 = (now - timedelta(days=90)).strftime("%y/%m/%d")
    rows = []
    for r in re.findall(r"<tr[^>]*>(.*?)</tr>", m.group(0), re.S):
        c = [_CLEAN(x) for x in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", r, re.S)]
        if len(c) < 5 or not re.match(r"\d\d/\d\d/\d\d", c[1] or ""):
            continue
        v = num(c[4])
        if v is None:
            continue
        rows.append((c[1], v))
    out = {}
    for lab, cut in (("tp30", cut30), ("tp90", cut90)):
        vals = [v for d, v in rows if d >= cut]
        if vals:
            out[lab] = round(sum(vals) / len(vals), 2)
            if lab == "tp30":
                out["tpn"] = len(vals)
                out["tpu"] = sum(1 for v in vals if v > 0)
                out["tpd"] = sum(1 for v in vals if v < 0)
    return out


def naver_extra(code):
    """증권사 리포트 발간 흐름 + 목표주가 — 컨센 재조정의 조기 신호.

    실적발표 다음날 리포트가 몰리는 것 자체가 '전망이 바뀌고 있다'는 뜻이다.
    """
    try:
        j = json.loads(urllib.request.urlopen(urllib.request.Request(
            f"https://m.stock.naver.com/api/stock/{code}/integration",
            headers={"User-Agent": "Mozilla/5.0"}), timeout=15).read())
    except Exception:
        return {}
    now = datetime.now()
    d7 = (now - timedelta(days=7)).strftime("%Y%m%d")
    d30 = (now - timedelta(days=30)).strftime("%Y%m%d")
    rs = j.get("researches") or []
    ci = j.get("consensusInfo") or {}
    return {"rc7": sum(1 for r in rs if (r.get("wdt") or "") >= d7),
            "rc30": sum(1 for r in rs if (r.get("wdt") or "") >= d30),
            "tp": num(ci.get("priceTargetMean")), "rec": num(ci.get("recommMean"))}


def main():
    DB.parent.mkdir(parents=True, exist_ok=True)
    cx = sqlite3.connect(DB, timeout=120)
    cx.execute("PRAGMA busy_timeout=120000")
    cx.executescript(SCHEMA)
    try:
        pool = json.loads(POOL.read_text(encoding="utf-8"))
        codes = [r["c"] for r in (pool.get("kr") or []) if re.fullmatch(r"\d{6}", str(r.get("c") or ""))]
    except Exception:
        codes = []
    if not codes:
        raise SystemExit("screener_pool.json 에서 KR 종목을 못 읽음 — 풀 빌드 후 실행할 것")
    if LIMIT:
        codes = codes[:LIMIT]
    enc = encparam()
    today = datetime.now().strftime("%Y-%m-%d")
    print(f"[cons] 대상 {len(codes)}종목 · encparam {enc[:12]}…", flush=True)

    def one(code):
        """분기 + 연간(2026-08-09 추가). 연간은 분기 컨센이 못 미치는 2027(E)·2028(E)까지
        주므로, 장기 전망 리비전은 연간 스냅샷으로만 쌓을 수 있다. period 키는 'FY2027'
        형식으로 저장해 분기('2027/03')와 구분한다. 종목당 호출이 1→2회가 되는 비용."""
        try:
            qs = quarters(code, enc)
        except Exception:
            qs = []
        try:
            ys = [(f"FY{p[:4]}", est, s, o, ni) for p, est, s, o, ni in quarters(code, enc, "Y")]
        except Exception:
            ys = []
        return code, qs + ys

    got = {}
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        for i, (code, qs) in enumerate(ex.map(one, codes)):
            if qs:
                got[code] = qs
            if (i + 1) % 200 == 0:
                print(f"    [{i+1}/{len(codes)}] 수집 {len(got)}", flush=True)
    print(f"[cons] 컨센 확보 {len(got)}/{len(codes)}", flush=True)

    # ── 스냅샷 적재 (미래 분기 = 컨센만)
    n = 0
    for code, qs in got.items():
        for p, est, s, o, ni in qs:
            if not est:
                continue
            cx.execute("INSERT OR REPLACE INTO snap(code,d,period,sales,op,ni) VALUES(?,?,?,?,?,?)",
                       (code, today, p, s, o, ni))
            n += 1
    cx.commit()
    print(f"[cons] 스냅샷 {n}행 적재 ({today})", flush=True)

    # ── 리비전 = 과거 스냅샷 대비 변화율
    def rev(code, period, days):
        d0 = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        r = cx.execute("SELECT op FROM snap WHERE code=? AND period=? AND d<=? ORDER BY d DESC LIMIT 1",
                       (code, period, d0)).fetchone()
        return r[0] if r else None

    out = {}
    for code, qs in got.items():
        est = [q for q in qs if q[1]]
        if not est:
            continue
        p, _, s, o, ni = est[0]                      # 가장 가까운 미래 분기
        rec = {"p": p, "sales": s, "op": o, "ni": ni}
        for lab, dd in (("op7", 7), ("op30", 30), ("op90", 90)):
            prev = rev(code, p, dd)
            rec[lab] = round(o / prev - 1.0, 4) if (o and prev and prev > 0) else None
        out[code] = rec

    # ── 리포트 발간 흐름·목표주가 (상위 종목만 — 호출 절약)
    top = list(out.keys())[:400]
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        for code, ex_ in zip(top, ex.map(naver_extra, top)):
            out[code].update(ex_)

    # ── 목표주가 리비전 — 컨센 페이지를 한 번 더 열어 #cTB24 를 읽는다(종목당 1콜)
    def tprv(code):
        try:
            return code, tp_revision(get(f"https://navercomp.wisereport.co.kr/v2/company/c1010001.aspx?cmp_cd={code}"))
        except Exception:
            return code, {}
    codes2 = list(out.keys())
    got2 = 0
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        for code, d in ex.map(tprv, codes2):
            if d:
                out[code].update(d); got2 += 1
    print(f"[cons] 목표주가 리비전 {got2}/{len(codes2)}종목", flush=True)

    OUT.write_text(json.dumps({"asof": datetime.now().strftime("%Y-%m-%d %H:%M"),
                               "src": "WISEreport 분기 컨센서스(증권사 추정 평균) + 네이버 리포트·목표주가",
                               "unit": "억원", "r": out}, ensure_ascii=False), encoding="utf-8")
    have30 = sum(1 for v in out.values() if v.get("op30") is not None)
    print(f"[cons] 완료 {len(out)}종목 · 30일 리비전 산출 {have30}종목 → {OUT.name}", flush=True)


if __name__ == "__main__":
    main()
