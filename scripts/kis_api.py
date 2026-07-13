#!/usr/bin/env python3
"""한국투자증권(KIS) Open API 클라이언트 — 국내 파생 T+0 (미결제약정·PCR·IV스큐).

왜 필요한가
-----------
KRX OPEN API 는 T+1 공표라 미결제약정(OI)·풋콜비율(PCR)이 하루 늦는다.
네이버는 선물 '가격'은 주지만 OI 는 주지 않는다. KIS 는 HTS 와 동일한 실시간 데이터를 준다:

  display-board-callput (FHPIF05030100) → 콜/풋 행사가별
      hts_otst_stpl_qty  미결제약정        → PCR = 풋 OI 합 / 콜 OI 합
      hts_ints_vltl      내재변동성(IV)    → IV 스큐 (OTM 풋 IV − OTM 콜 IV)
      delta_val/gama     델타·감마         → 딜러 감마(GEX) 실측
  inquire-price (FHMIF10000000)          → 선물 미결제약정

인증
----
appkey + appsecret 은 매 요청 헤더에 '필수'다. access_token 만으로는 안 된다
(실측: EGW00104 "AppSecret은 필수입니다").

  키 파일: <SECURITY>/kis.json
    {"appkey": "...", "appsecret": "...", "mode": "real"}   # mode: real | mock
  토큰 캐시: <SECURITY>/.token_cache_{mode}.json  (자동 발급·갱신, 24h 유효)

키가 없으면 조용히 skip 한다 — 파이프라인을 막지 않는다.

⚠️ 호출 제한: 공식 문서가 display-board-callput 을 "조회시간이 긴 API · 1초당 최대 1건 권장"
   이라 명시한다. 하루 2회 배치 용도로만 쓴다. 실시간 폴링 금지.
"""
import json, os, glob, time, ssl
import urllib.request, urllib.error
from datetime import datetime, timezone, timedelta

KST = timezone(timedelta(hours=9))
CTX = ssl.create_default_context()
HOST = {"real": "https://openapi.koreainvestment.com:9443",
        "mock": "https://openapivts.koreainvestment.com:29443"}


def _seczone():
    for p in (glob.glob("/sessions/*/mnt/claudeCowork/SECURITY"),
              glob.glob("/sessions/*/mnt/outputs/SECURITY"),
              [os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "secrets")]):
        for d in p:
            if os.path.isdir(d):
                return d
    return None


def _creds():
    z = _seczone()
    if not z:
        return None
    p = os.path.join(z, "kis.json")
    if not os.path.isfile(p):
        return None
    try:
        c = json.load(open(p, encoding="utf-8"))
    except Exception:
        return None
    if not (c.get("appkey") and c.get("appsecret")):
        return None
    c.setdefault("mode", "real")
    c["_zone"] = z
    return c


def _token(c):
    """캐시된 토큰 재사용, 만료 60초 전이면 재발급."""
    cache = os.path.join(c["_zone"], f".token_cache_{c['mode']}.json")
    try:
        t = json.load(open(cache, encoding="utf-8"))
        if t.get("access_token") and float(t.get("expires_at", 0)) - 60 > time.time():
            return t["access_token"]
    except Exception:
        pass
    body = json.dumps({"grant_type": "client_credentials",
                       "appkey": c["appkey"], "appsecret": c["appsecret"]}).encode()
    req = urllib.request.Request(HOST[c["mode"]] + "/oauth2/tokenP", data=body,
                                 headers={"content-type": "application/json"})
    try:
        d = json.loads(urllib.request.urlopen(req, timeout=15, context=CTX).read())
    except urllib.error.HTTPError as e:
        print("  [KIS] 토큰 발급 실패:", e.code, e.read().decode("utf-8", "ignore")[:120])
        return None
    except Exception as e:
        print("  [KIS] 토큰 발급 실패:", type(e).__name__)
        return None
    tok = d.get("access_token")
    if not tok:
        print("  [KIS] 토큰 응답 이상:", str(d)[:120]); return None
    exp = time.time() + float(d.get("expires_in", 86400))
    try:
        json.dump({"access_token": tok, "expires_at": exp},
                  open(cache, "w", encoding="utf-8"))
        os.chmod(cache, 0o600)
    except Exception:
        pass
    print(f"  [KIS] 토큰 발급 ✓ (만료 {datetime.fromtimestamp(exp, KST):%m-%d %H:%M})")
    return tok


def _get(c, tok, path, tr_id, params):
    q = "&".join(f"{k}={v}" for k, v in params.items())
    req = urllib.request.Request(f"{HOST[c['mode']]}{path}?{q}", headers={
        "content-type": "application/json; charset=utf-8",
        "authorization": f"Bearer {tok}",
        "appkey": c["appkey"], "appsecret": c["appsecret"],
        "tr_id": tr_id, "custtype": "P"})
    try:
        d = json.loads(urllib.request.urlopen(req, timeout=25, context=CTX).read())
    except urllib.error.HTTPError as e:
        print(f"  [KIS] {tr_id} HTTP {e.code}: {e.read().decode('utf-8','ignore')[:120]}")
        return None
    except Exception as e:
        print(f"  [KIS] {tr_id} 실패: {type(e).__name__}")
        return None
    if str(d.get("rt_cd")) != "0":
        print(f"  [KIS] {tr_id} rt_cd={d.get('rt_cd')} {d.get('msg1')}")
        return None
    return d


def _n(v):
    try: return float(str(v).replace(",", ""))
    except Exception: return None


def option_board(expiry=None):
    """콜/풋 전광판 → PCR·IV스큐·OI 합계. 키 없으면 None(비차단)."""
    c = _creds()
    if not c:
        return None                       # 키 없음 → 조용히 skip
    tok = _token(c)
    if not tok:
        return None
    if not expiry:                        # 최근월물 (당월, 만기 지났으면 익월은 호출자가 조정)
        n = datetime.now(KST)
        expiry = f"{n.year}{n.month:02d}"
    d = _get(c, tok, "/uapi/domestic-futureoption/v1/quotations/display-board-callput",
             "FHPIF05030100",
             {"FID_COND_MRKT_DIV_CODE": "O", "FID_COND_SCR_DIV_CODE": "20503",
              "FID_MRKT_CLS_CODE": "CO", "FID_MTRT_CNT": expiry,
              "FID_MRKT_CLS_CODE1": "PO", "FID_COND_MRKT_CLS_CODE": ""})
    if not d:
        return None
    calls = d.get("output1") or []        # 콜
    puts  = d.get("output2") or []        # 풋

    def oi(rows):
        return sum(_n(r.get("hts_otst_stpl_qty")) or 0 for r in rows)

    coi, poi = oi(calls), oi(puts)
    out = {"expiry": expiry, "asof": datetime.now(KST).strftime("%Y-%m-%d"),
           "call_oi": coi, "put_oi": poi,
           "pcr_oi": (round(poi / coi, 3) if coi else None),
           "n_call": len(calls), "n_put": len(puts)}

    # IV 스큐 = OTM 풋 IV 평균 − OTM 콜 IV 평균 (ATM 대비 ±3~7 행사가)
    def iv_of(rows):
        return [(_n(r.get("acpr")) or _n(r.get("optn_prpr")), _n(r.get("hts_ints_vltl")))
                for r in rows if _n(r.get("hts_ints_vltl"))]
    ivc, ivp = [v for _, v in iv_of(calls)], [v for _, v in iv_of(puts)]
    if ivc and ivp:
        out["iv_call_avg"] = round(sum(ivc) / len(ivc), 2)
        out["iv_put_avg"] = round(sum(ivp) / len(ivp), 2)
        out["iv_skew"] = round(out["iv_put_avg"] - out["iv_call_avg"], 2)
    return out


def futures_oi(code="101W09"):
    """코스피200 선물 미결제약정. 키 없으면 None."""
    c = _creds()
    if not c: return None
    tok = _token(c)
    if not tok: return None
    d = _get(c, tok, "/uapi/domestic-futureoption/v1/quotations/inquire-price",
             "FHMIF10000000",
             {"FID_COND_MRKT_DIV_CODE": "F", "FID_INPUT_ISCD": code})
    if not d: return None
    o = d.get("output1") or d.get("output") or {}
    return {"code": code, "asof": datetime.now(KST).strftime("%Y-%m-%d"),
            "price": _n(o.get("futs_prpr")),
            "oi": _n(o.get("hts_otst_stpl_qty")),
            "oi_chg": _n(o.get("otst_stpl_qty_icdc"))}


if __name__ == "__main__":
    c = _creds()
    if not c:
        z = _seczone() or "(SECURITY 폴더 없음)"
        print("❌ KIS 키 없음 — 아래 파일을 만들면 즉시 활성화된다:")
        print(f"   {os.path.join(z, 'kis.json')}")
        print('   {"appkey": "...", "appsecret": "...", "mode": "real"}')
        print("\n   발급: https://apiportal.koreainvestment.com → 로그인 → 앱 등록")
        print("   (모의투자 계좌로도 시세 조회 가능 — mode: \"mock\")")
        raise SystemExit(0)
    print(f"✅ KIS 키 확인 (mode={c['mode']})")
    print("\n── 선물 미결제약정")
    print("  ", futures_oi())
    print("\n── 옵션 전광판 (PCR·IV스큐)")
    print("  ", option_board())
