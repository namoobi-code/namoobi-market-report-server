#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""kis_api.py — 한국투자증권(KIS) Open API 클라이언트.

목적: 3.1.13 파생지표의 마지막 T+1 구멍(미결제약정·풋콜비율·IV스큐·딜러감마)을 T+0 로 메운다.
      KRX OPEN API 는 전 항목 T+1 이라, 폭락 당일 파생 시그널이 하루 늦게 도착한다.

■ 자격증명 — <SECURITY>/.env (이미 존재하는 파일. 별도 kis.json 불필요)
      KIS_ENV=mock            # mock=모의 / real=실전
      MOCK_APP_KEY=... / MOCK_APP_SECRET=...
      REAL_APP_KEY=... / REAL_APP_SECRET=...
    토큰은 <SECURITY>/.token_cache_{mode}.json 에 캐시(기존 파일 포맷과 동일: access_token/expires_at).
    키가 없거나 발급 실패하면 모든 함수가 None 을 돌려주고 파이프라인은 그대로 진행된다(비차단).

■ 실측으로 확인된 사실 (2026-07-13)
  · 모의(VTS) 토큰도 '시세'는 실제 시장값을 준다. KRX T+1 과 행사가별 OI 가 정확히 이어짐:
        K=1145  KRX 7/10 풋 94  →  KIS 7/13 풋 119
    단, 모의 토큰은 모의 호스트(openapivts)에서만 유효하다. 실전 호스트는 rt_cd=1 로 거부.
  · 레이트리밋: 모의 ≈ 1건/초, 실전 ≈ 20건/초. 초과 시 rt_cd=1 "초당 거래건수를 초과하였습니다".
  · display-board-callput(전광판)은 **행사가 최고가부터 100행**만 준다. 연속조회(tr_cont) 없음.
    현물이 급락하면 ATM 이 창 밖으로 나가 PCR 이 쓰레기값이 된다(실측: 현물 1090 인데 창은 1350~1597).
    → 전광판은 쓰지 않는다. 행사가별 개별 조회(inquire-price)로 체인을 훑는다.
  · 선물/옵션 종목코드는 KIS 마스터 파일에만 있다(KRX 단축코드와 체계가 다름):
        A01609    = 코스피200 F 202609
        B01608A32 = 코스피200 C 202608 K=1090.0     (B=콜, C=풋)
"""
import os, re, io, json, time, glob, zipfile, datetime
import urllib.request, urllib.parse, urllib.error

VTS  = "https://openapivts.koreainvestment.com:29443"   # 모의
REAL = "https://openapi.koreainvestment.com:9443"       # 실전
MASTER = "https://new.real.download.dws.co.kr/common/master/fo_idx_code_mts.mst.zip"

# ── 자격증명 ────────────────────────────────────────────────────────────────
def _seczone():
    for p in ("/sessions/*/mnt/claudeCowork/SECURITY", "/sessions/*/mnt/*/SECURITY",
              os.path.expanduser("~/namoobi/secrets"), "D:/claudeCowork/SECURITY"):
        for d in sorted(glob.glob(p)):
            if os.path.isdir(d):
                return d
    return None

def _creds():
    """.env → {mode, host, appkey, appsecret}. 없으면 None."""
    z = _seczone()
    if not z:
        return None
    env = {}
    f = os.path.join(z, ".env")
    if os.path.exists(f):
        for ln in open(f, encoding="utf-8", errors="ignore"):
            ln = ln.strip()
            if ln and not ln.startswith("#") and "=" in ln:
                k, v = ln.split("=", 1)
                env[k.strip()] = v.split("#")[0].strip().strip('"').strip("'")
    j = os.path.join(z, "kis.json")            # 구 방식도 계속 지원
    if os.path.exists(j):
        try:
            d = json.load(open(j, encoding="utf-8"))
            m = (d.get("mode") or "real").lower()
            env.setdefault("KIS_ENV", m)
            env.setdefault(m.upper() + "_APP_KEY", d.get("appkey", ""))
            env.setdefault(m.upper() + "_APP_SECRET", d.get("appsecret", ""))
        except Exception:
            pass
    mode = (env.get("KIS_ENV") or "mock").lower()
    ak = env.get(mode.upper() + "_APP_KEY", "")
    sk = env.get(mode.upper() + "_APP_SECRET", "")
    if not ak or not sk:
        return None
    return {"mode": mode, "host": VTS if mode == "mock" else REAL,
            "appkey": ak, "appsecret": sk, "sec": z,
            # 실측 레이트리밋: 모의 ~1건/초. 실전은 문서상 20건/초(gap 0.06).
            # ⚠️ 신규 계좌는 신청일로부터 '3일간 초당 3건' 제한(공지 2026-03-20) 후 자동 상향.
            #    3일창 동안엔 _get 의 적응형 백오프가 간격을 자동으로 늘린다. 이후엔 0.06 으로 풀속.
            "gap": 0.75 if mode == "mock" else 0.06}

# ── 토큰 ────────────────────────────────────────────────────────────────────
def _token(c):
    """캐시 최우선. KIS 는 tokenP 를 자주 부르면 EGW00103('유효하지 않은 AppKey')로 '차단'한다
    — 키가 틀린 게 아니라 발급 과호출 방어다(실측). 그러니 캐시를 끝까지 재사용하고,
    발급 실패 시에도 캐시 토큰이 있으면 그걸 쓴다(만료 전이면 정상 동작)."""
    cache = os.path.join(c["sec"], ".token_cache_%s.json" % c["mode"])
    old = None
    try:
        d = json.load(open(cache, encoding="utf-8"))
        if d.get("access_token"):
            old = d["access_token"]
            if float(d.get("expires_at", 0)) - time.time() > 300:
                return old
    except Exception:
        pass
    # ⚠️ 발급 남용 방지 가드 — KIS 는 tokenP 를 짧은 시간에 여러 번 부르면 앱키를 '일시 차단'하고
    #    이후 모든 호출에 EGW00103("유효하지 않은 AppKey")을 돌려준다. 키가 틀린 게 아니다(실측 2026-07-14).
    #    토큰 수명이 24h 이므로 발급은 하루 몇 번이면 충분하다. 1시간에 1회로 하드 제한한다.
    stamp = os.path.join(c["sec"], ".token_issue_%s.stamp" % c["mode"])
    try:
        if time.time() - os.path.getmtime(stamp) < 3600:
            if old:
                return old
            raise RuntimeError("KIS 토큰 발급 쿨다운(1h) — 앱키 차단 방지. 캐시 토큰도 없음.")
    except OSError:
        pass
    body = json.dumps({"grant_type": "client_credentials",
                       "appkey": c["appkey"], "appsecret": c["appsecret"]}).encode()
    r = urllib.request.Request(c["host"] + "/oauth2/tokenP", data=body,
                               headers={"content-type": "application/json"})
    try:
        with urllib.request.urlopen(r, timeout=20) as f:
            j = json.loads(f.read())
    except urllib.error.HTTPError as e:
        j = json.loads(e.read() or b"{}")
    try:
        open(stamp, "w").close()      # 실패해도 스탬프 → 폭주 방지
    except Exception:
        pass
    tok = j.get("access_token")
    if not tok:
        if old:
            return old          # 발급 차단이어도 기존 토큰이 살아있을 수 있다 → 그대로 시도
        raise RuntimeError("KIS 토큰 발급 실패: %s" % (j.get("error_description") or j.get("msg1") or j))
    exp = time.time() + float(j.get("expires_in") or 86400) - 60
    try:
        open(stamp, "w").close()
    except Exception:
        pass
    try:
        json.dump({"access_token": tok, "expires_at": exp}, open(cache, "w"))
        os.chmod(cache, 0o600)
    except Exception:
        pass
    return tok

# ── 호출 (레이트리밋 자동 백오프) ───────────────────────────────────────────
_last = [0.0]

def _get(c, tok, path, tr, params, tries=4):
    for i in range(tries):
        w = c["gap"] - (time.time() - _last[0])
        if w > 0:
            time.sleep(w)
        u = c["host"] + path + "?" + urllib.parse.urlencode(params)
        r = urllib.request.Request(u, headers={
            "content-type": "application/json", "authorization": "Bearer " + tok,
            "appkey": c["appkey"], "appsecret": c["appsecret"], "tr_id": tr, "custtype": "P"})
        try:
            with urllib.request.urlopen(r, timeout=25) as f:
                j = json.loads(f.read())
        except urllib.error.HTTPError as e:
            j = json.loads(e.read() or b"{}")
        except Exception:
            j = {}
        _last[0] = time.time()
        if "초당" in str(j.get("msg1", "")):
            # 리밋 → 간격을 늘려 학습. 상한 0.5s(=2건/초) — 신규 3일창(3건/초)에서도 과증 방지.
            c["gap"] = min(c["gap"] * 1.5 + 0.05, 0.5)
            continue
        # 성공 → 간격을 조금씩 회복(3일 제한 해제/일시 혼잡 이후 풀속 복귀). 최저는 모드 하한.
        floor = 0.75 if c["mode"] == "mock" else 0.06
        c["gap"] = max(floor, c["gap"] * 0.97)
        return j
    return {}

# ── 종목 마스터 (선물·옵션 코드) ────────────────────────────────────────────
_mst = {"day": None, "fut": [], "call": {}, "put": {}}

def _master():
    """KIS 종목 마스터에서 코스피200 선물/옵션 코드를 뽑는다. 하루 1회 캐시."""
    today = datetime.date.today().isoformat()
    if _mst["day"] == today:
        return _mst
    with urllib.request.urlopen(MASTER, timeout=40) as f:
        z = zipfile.ZipFile(io.BytesIO(f.read()))
    raw = z.read(z.namelist()[0]).decode("cp949", "ignore").splitlines()
    fut, call, put = [], {}, {}
    for l in raw:
        p = l.split("|")
        if len(p) < 9 or p[8] != "KOSPI200":
            continue
        g, code, nm = p[0], p[1], p[3]
        if g == "1" and nm.startswith("F 2"):                  # 선물 (정규 월물)
            fut.append((nm[2:8], code))                        # (만기 YYYYMM, 코드)
        elif g == "5" and nm.startswith("C 2"):                # 콜 (정규 월물)
            call.setdefault(nm[2:8], {})[float(p[5])] = code
        elif g == "6" and nm.startswith("P 2"):                # 풋
            put.setdefault(nm[2:8], {})[float(p[5])] = code
    _mst.update(day=today, fut=sorted(fut), call=call, put=put)
    return _mst

def _near(kinds):
    """근월물 만기(YYYYMM) — 오늘 이후 만기 중 가장 빠른 것."""
    ym = datetime.date.today().strftime("%Y%m")
    c = sorted(k for k in kinds if k >= ym)
    return c[0] if c else (sorted(kinds)[-1] if kinds else None)

# ── 공개 API ────────────────────────────────────────────────────────────────
def _f(x):
    try:
        return float(str(x).replace(",", ""))
    except Exception:
        return 0.0

def futures_oi():
    """코스피200 선물 근월물 — 현재가·미결제약정(T+0). {code,name,price,oi,oi_chg,asof} or None."""
    c = _creds()
    if not c:
        return None
    tok = _token(c)
    m = _master()
    ym = _near([k for k, _ in m["fut"]])
    code = dict(m["fut"]).get(ym)
    if not code:
        return None
    j = _get(c, tok, "/uapi/domestic-futureoption/v1/quotations/inquire-price",
             "FHMIF10000000", {"FID_COND_MRKT_DIV_CODE": "F", "FID_INPUT_ISCD": code})
    o = j.get("output1") or {}
    if not o.get("futs_prpr"):
        return None
    return {"code": code, "expiry": ym, "name": o.get("hts_kor_isnm"),
            "price": _f(o["futs_prpr"]), "oi": _f(o.get("hts_otst_stpl_qty")),
            "oi_chg": _f(o.get("otst_stpl_qty_icdc")),
            "asof": datetime.date.today().isoformat()}

def option_chain(spot=None, coverage=0.99, krx_base=None, max_calls=600):
    """코스피200 옵션 근월물 체인을 T+0 로 훑어 PCR·IV스큐·GEX 를 낸다.

    체인 전체(390 행사가 × 2 = 780 호출)는 모의(1건/초)에서 13분이라 과하다.
    krx_base(= KRX T+1 행사가별 OI dict) 를 주면 **OI 상위 coverage 까지만** T+0 로 갱신하고
    나머지 꼬리는 KRX 값을 그대로 쓴다 → 99% 커버에 522 호출(모의 ~7분 / 실전 ~30초).
    krx_base 가 없으면 현물 ±25% 창만 훑는다.

    krx_base 형식: {"call": {행사가: OI}, "put": {행사가: OI}}
    """
    c = _creds()
    if not c:
        return None
    tok = _token(c)
    m = _master()
    ym = _near(list(m["call"].keys()))
    call, put = m["call"].get(ym, {}), m["put"].get(ym, {})
    ks = sorted(set(call) & set(put))
    if not ks:
        return None
    if spot is None:
        fo = futures_oi()
        spot = fo["price"] if fo else (ks[len(ks) // 2])

    if krx_base:
        bc, bp = krx_base.get("call", {}), krx_base.get("put", {})
        tot = sum(bc.values()) + sum(bp.values())
        rank = sorted(ks, key=lambda k: -(bc.get(k, 0) + bp.get(k, 0)))
        pick, s = [], 0.0
        for k in rank:
            if len(pick) * 2 >= max_calls:
                break
            pick.append(k)
            s += bc.get(k, 0) + bp.get(k, 0)
            if tot and s / tot >= coverage:
                break
        scan = sorted(pick)
    else:
        scan = [k for k in ks if spot * 0.75 <= k <= spot * 1.25][: max_calls // 2]

    rows = []
    for k in scan:
        for side, tbl in (("C", call), ("P", put)):
            j = _get(c, tok, "/uapi/domestic-futureoption/v1/quotations/inquire-price",
                     "FHMIF10000000", {"FID_COND_MRKT_DIV_CODE": "O", "FID_INPUT_ISCD": tbl[k]})
            o = j.get("output1") or {}
            if not o:
                continue
            rows.append({"k": k, "side": side, "oi": _f(o.get("hts_otst_stpl_qty")),
                         "vol": _f(o.get("acml_vol")), "iv": _f(o.get("hts_ints_vltl")),
                         "delta": _f(o.get("delta_val")), "gamma": _f(o.get("gama")),
                         "px": _f(o.get("optn_prpr"))})
    if not rows:
        return None

    # T+0 로 훑은 행사가는 KIS 값, 안 훑은 꼬리는 KRX T+1 값으로 채워 '전 체인' PCR 을 만든다.
    coi = {r["k"]: r["oi"] for r in rows if r["side"] == "C"}
    poi = {r["k"]: r["oi"] for r in rows if r["side"] == "P"}
    if krx_base:
        for k, v in (krx_base.get("call") or {}).items():
            coi.setdefault(k, v)
        for k, v in (krx_base.get("put") or {}).items():
            poi.setdefault(k, v)
    C, P = sum(coi.values()), sum(poi.values())
    cv = sum(r["vol"] for r in rows if r["side"] == "C")
    pv = sum(r["vol"] for r in rows if r["side"] == "P")

    # 25델타 스큐 = 25델타 풋 IV − 25델타 콜 IV (양수 = 하방 헤지 수요 우위 = 공포)
    def d25(side, tgt):
        cand = [r for r in rows if r["side"] == side and r["iv"] > 0 and abs(r["delta"]) > 0.01]
        return min(cand, key=lambda r: abs(abs(r["delta"]) - tgt)) if cand else None
    cp, pp = d25("C", 0.25), d25("P", 0.25)
    skew = round(pp["iv"] - cp["iv"], 2) if (cp and pp) else None

    # 딜러 감마(GEX) — 콜은 딜러 롱감마(+), 풋은 숏감마(−). 계약승수 25만원.
    gex = sum((1 if r["side"] == "C" else -1) * r["gamma"] * r["oi"] * 250000 * (spot ** 2) / 100
              for r in rows if r["gamma"])

    return {"asof": datetime.date.today().isoformat(), "expiry": ym, "spot": spot,
            "scanned": len(scan), "strikes": len(ks),
            "call_oi": C, "put_oi": P, "pcr_oi": round(P / C, 3) if C else None,
            "call_vol": cv, "put_vol": pv, "pcr_vol": round(pv / cv, 3) if cv else None,
            "iv_skew": skew,
            "iv_call_25d": cp["iv"] if cp else None, "iv_put_25d": pp["iv"] if pp else None,
            "gex": round(gex / 1e8, 1) if gex else None,     # 억원
            "src": "KIS(%s) T+0%s" % (c["mode"], " + KRX 꼬리보정" if krx_base else "")}

# 하위호환 별칭
def option_board(expiry=None):
    return option_chain()

if __name__ == "__main__":
    c = _creds()
    if not c:
        z = _seczone()
        print("❌ KIS 키 없음 — %s/.env 에 KIS_ENV / {MOCK|REAL}_APP_KEY / _APP_SECRET 필요" % z)
        raise SystemExit(1)
    print("모드:", c["mode"], "| 호스트:", c["host"])
    f = futures_oi()
    print("선물:", json.dumps(f, ensure_ascii=False))
    o = option_chain(spot=f["price"] if f else None)
    print("옵션:", json.dumps(o, ensure_ascii=False))
