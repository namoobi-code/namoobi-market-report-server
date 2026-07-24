import json, time, urllib.request, os, re, sqlite3, zlib, sys
from pathlib import Path
from datetime import datetime
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

BASE = Path(__file__).parent
DB   = BASE / "data" / "db"
RPT  = BASE / "data" / "reports"
POLL = BASE / "data" / "poll.db"
RPTD = BASE / "data" / "report"

app = FastAPI(title="namoobi market", docs_url="/api/docs")

def load(name: str):
    p = DB / f"{name}.json"
    if not p.exists():
        raise HTTPException(404, f"{name} not found")
    return json.loads(p.read_text(encoding="utf-8"))

_domains_cache = {"sig": None, "out": None}

@app.get("/api/domains")
def domains():
    files = sorted(DB.glob("*.json"))
    sig = _db_sig(files)
    if _domains_cache["sig"] != sig:
        out = []
        for p in files:
            try:
                d = json.loads(p.read_text(encoding="utf-8"))
                out.append({"name": p.stem, "as_of": d.get("as_of",""), "marker": d.get("marker","")})
            except Exception:
                pass
        _domains_cache.update(sig=sig, out=out)
    return _domains_cache["out"]

@app.get("/api/db/{name}")
def get_db(name: str, request: Request):
    """원본 JSON 바이트를 그대로 전송(파싱/재직렬화 생략) + ETag 재검증 캐시."""
    if not re.fullmatch(r"[a-zA-Z0-9_]+", name):
        raise HTTPException(400, "bad name")
    p = DB / f"{name}.json"
    if not p.exists():
        raise HTTPException(404, f"{name} not found")
    st = p.stat()
    etag = 'W/"%x-%x"' % (int(st.st_mtime), st.st_size)
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers={"ETag": etag, "Cache-Control": "no-cache"})
    return Response(content=p.read_bytes(), media_type="application/json",
                    headers={"ETag": etag, "Cache-Control": "no-cache"})

@app.get("/api/summary")
def summary():
    """대시보드 상단 카드용 — 정책금리·물가·고용·경기선행 한 번에"""
    out = {}
    for k in ("policy_rates", "inflation", "employment", "leading", "semi_cycle"):
        try:
            out[k] = load(k)
        except HTTPException:
            out[k] = None
    return out

@app.get("/api/series/{name}")
def series(name: str, days: int = 0):
    """[[date, value], ...] 형식 시계열"""
    d = load(name)
    data = d.get("data", [])
    if days and isinstance(data, list) and len(data) > days:
        data = data[-days:]
    return {"as_of": d.get("as_of",""), "marker": d.get("marker",""), "data": data}

@app.get("/api/report")
def report_data():
    """보고서가 렌더링하는 전체 데이터 — CAPEX·HBM·파생포지셔닝 등"""
    p = RPTD / "report_data.json"
    if not p.exists():
        raise HTTPException(404, "report_data 없음")
    return json.loads(p.read_text(encoding="utf-8"))

@app.get("/api/deriv")
def deriv_live():
    """3.1.13 파생 포지셔닝 — 서버가 장중·마감 갱신하는 deriv_snapshot.json 라이브 제공.
       report_data(하루 1회 병합)와 분리해 프론트가 장중 폴링으로 최신값을 본다.
       built_at = 스냅샷 파일 갱신시각(KST) — 실제 마지막 취득 시각."""
    p = BASE / "data" / "deriv_snapshot.json"
    if not p.exists():
        raise HTTPException(404, "deriv_snapshot 없음")
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        raise HTTPException(500, f"deriv_snapshot 파싱 실패: {e}")
    from datetime import timezone, timedelta
    kst = timezone(timedelta(hours=9))
    d["built_at"] = datetime.fromtimestamp(p.stat().st_mtime, kst).strftime("%Y-%m-%d %H:%M:%S")
    d["cadence"] = ("장중 5분 자동취득(정규장·장전·시간외·야간 中 데이터 제공 구간) · "
                    "옵션 PCR·IV스큐·GEX는 장중 1시간+장마감 캡처 · 매일 새벽 정산치로 z 재계산")
    # (2026-07-20) 야간선물(KRX 18:00~06:00) — night_ws 웹소켓 데몬(H0MFCNT0)이 기록한 실시간가.
    #   현물은 야간에 멈춰 있어 베이시스로 쓰면 왜곡 → 별도 '야간선물' 정보로만 노출한다.
    nfp = BASE / "data" / "night_fut.json"
    if nfp.exists():
        try:
            nf = json.loads(nfp.read_text(encoding="utf-8"))
            age = time.time() - nfp.stat().st_mtime
            if age < 900 and nf.get("px"):
                nf["age_sec"] = int(age)
                d["night"] = nf
        except Exception:
            pass
    return Response(content=json.dumps(d, ensure_ascii=False),
                    media_type="application/json", headers={"Cache-Control": "no-store"})

@app.get("/api/policyrates")
def policyrates():
    """주요 6개국 정책금리 월별 시계열"""
    p = RPTD / "policyrates_monthly.json"
    if not p.exists():
        raise HTTPException(404, "policyrates 없음")
    return json.loads(p.read_text(encoding="utf-8"))

# 대시보드가 참조하지 않는 대용량 DB — 번들 제외(필요 시 /api/db/<name> 로 개별 조회)
BUNDLE_SKIP = {"screener_pool", "tp_history", "us_krname", "etf_holdings"}
_bundle_cache = {"sig": None, "body": None, "etag": None}

def _db_sig(files):
    parts = []
    for p in files:
        st = p.stat()
        parts.append("%s:%d:%d" % (p.name, st.st_mtime, st.st_size))
    if POLL.exists():
        st = POLL.stat()
        parts.append("poll:%d:%d" % (st.st_mtime, st.st_size))
    return "|".join(parts)

@app.get("/api/bundle")
def bundle(request: Request):
    """db/ 전체를 한 번에 — 변경 없으면 메모리 캐시/304로 즉시 응답."""
    files = sorted(p for p in DB.glob("*.json") if p.stem not in BUNDLE_SKIP)
    sig = _db_sig(files)
    if _bundle_cache["sig"] != sig:
        out = {}
        for p in files:
            try:
                out[p.stem] = json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                pass
        poll = {}
        if POLL.exists():
            try:
                c = sqlite3.connect(POLL)
                for m, sym, ts, v in c.execute(
                    "SELECT metric,symbol,ts,value FROM ticks ORDER BY ts"):
                    poll.setdefault(m, {}).setdefault(sym or "_", []).append([ts, v])
                c.close()
            except Exception:
                pass
        out["_poll"] = poll
        body = json.dumps(out, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        _bundle_cache.update(sig=sig, body=body,
                             etag='W/"b%x-%x"' % (zlib.crc32(sig.encode()), len(body)))
    etag = _bundle_cache["etag"]
    hdr = {"ETag": etag, "Cache-Control": "no-cache"}
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=hdr)
    return Response(content=_bundle_cache["body"], media_type="application/json", headers=hdr)

_disc_cache = {}


@app.get("/api/disclosure/kr/{code}")
def disclosure_api(code: str):
    """종목 공시 목록 — 네이버 m.stock 프록시. 차트에 마커로 찍고 클릭하면 내용을 보여준다.

    (2026-07-21) 한국 전용. 미국은 SEC EDGAR 가 종목코드→CIK 매핑을 따로 요구하고
    공시 성격도 달라(8-K 등) 같은 UX 로 묶기 어려워 제외한다.
    30분 캐시 — 공시는 실시간성이 낮고 같은 종목을 반복 조회하는 화면이라 충분하다.
    """
    if not re.fullmatch(r"[0-9A-Za-z]{6}", code):
        raise HTTPException(400, "bad code")
    now = time.time()
    hit = _disc_cache.get(code)
    if hit and now - hit[0] < 1800:
        return hit[1]
    try:
        url = ("https://m.stock.naver.com/api/stock/%s/disclosure?pageSize=200&page=1" % code)
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0",
                                                   "Referer": "https://m.stock.naver.com/"})
        rows = json.loads(urllib.request.urlopen(req, timeout=10).read())
        # (2026-07-21) 거래소 시장조치 공지는 뺀다.
        #   '주식선물·옵션 가격제한폭 확대요건 도달' 류는 주가가 크게 움직였다는 사실의 '결과'로
        #   자동 발생하는 공지다. 이걸 주가 차트에 사건으로 찍으면 순환논리이고,
        #   실측(005930 1년): 80건 중 20건이 이 유형이라 정작 실적·자사주 같은 실제 공시를 밀어냈다.
        NOISE = re.compile(r"가격제한폭|매매거래정지|매매거래재개|시장조치|투자유의")
        out = {"items": [{"d": str(r.get("datetime") or "")[:10].replace("-", ""),
                          "t": r.get("title") or "",
                          "at": str(r.get("datetime") or "")[11:16],
                          "src": r.get("author") or "",
                          "id": r.get("disclosureId")}
                         for r in (rows or [])
                         if r.get("datetime") and not NOISE.search(r.get("title") or "")]}
        _disc_cache[code] = (now, out)
        if len(_disc_cache) > 300:
            _disc_cache.clear()
        return out
    except Exception as e:
        return {"items": [], "err": repr(e)[:80]}


def _logged_in(request) -> bool:
    """namoobi 로그인 세션 여부. KIS 를 쓰는 엔드포인트는 이걸로 막는다.

    (2026-07-21) 분봉·호가·체결은 KIS 실계정을 호출한다. 공개로 열어두면
    유량제한에 걸려 파생·수급 수집 배치까지 같이 죽는다.
    클라이언트에서 버튼만 비활성화하면 URL 직접 호출로 뚫리므로 서버에서 막는다.
    """
    try:
        from auth_visitors import current_user
        return bool(current_user(request))
    except Exception:
        return False


_invt_cache = {}


@app.get("/api/invtable/kr/{code}")
def invtable_api(code: str, n: int = 20):
    """외국인·기관 순매매 일별 표 — 네이버 trend API.

    (2026-07-21) 일봉 차트 하단에 붙인다. 차트의 수급 '선'은 추세를 보고,
    이 표는 '어느 날 누가 얼마나' 를 숫자로 확인하는 용도다.
    제공: 종가·전일비·등락률·거래량·기관 순매수·외국인 순매수·개인 순매수·외국인 보유율
    (보유주수는 이 API 에 없다 — 보유율로 대체)
    ※ 투자자별 순매매는 장 마감 후 확정치다. 장중 값은 잠정치조차 공개 API 로는 안 나온다.
    """
    if not re.fullmatch(r"[0-9A-Za-z]{6}", code):
        raise HTTPException(400, "bad code")
    n = max(5, min(int(n or 20), 60))
    now = time.time()
    key = f"{code}:{n}"
    hit = _invt_cache.get(key)
    if hit and now - hit[0] < 600:
        return hit[1]
    try:
        url = ("https://m.stock.naver.com/api/stock/%s/trend?pageSize=%d&page=1" % (code, n))
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0",
                                                   "Referer": "https://m.stock.naver.com/"})
        rows = json.loads(urllib.request.urlopen(req, timeout=10).read())

        def _i(z):
            try:
                return int(str(z).replace(",", "").replace("+", "").strip())
            except Exception:
                return None
        out = [{"d": r.get("bizdate"),
                "px": _i(r.get("closePrice")),
                "chg": _i(r.get("compareToPreviousClosePrice")),
                "up": ((r.get("compareToPreviousPrice") or {}).get("code") in ("1", "2")),
                "vol": _i(r.get("accumulatedTradingVolume")),
                "org": _i(r.get("organPureBuyQuant")),
                "frg": _i(r.get("foreignerPureBuyQuant")),
                "ind": _i(r.get("individualPureBuyQuant")),
                "hold": r.get("foreignerHoldRatio")} for r in (rows or [])]
        res = {"items": out}
        _invt_cache[key] = (now, res)
        if len(_invt_cache) > 200:
            _invt_cache.clear()
        return res
    except Exception as e:
        return {"items": [], "err": repr(e)[:80]}


_ob_cache = {}


@app.get("/api/orderbook/kr/{code}")
def orderbook_api(request: Request, code: str):
    """호가 10단계 · 체결강도 · 최근 체결 — KIS 실전계정 REST(실시간).

    (2026-07-21) 네이버 호가·거래원은 20분 지연이라 단타 판단에 못 쓴다.
    KIS 는 실전 계정이면 지연이 없어 그대로 쓸 수 있다(mode=real 확인).
      · 호가   FHKST01010200 → askp1~10 / bidp1~10 + 잔량 + 총잔량
      · 체결강도 FHKST01010300 의 tday_rltv (당일 누적, 100 초과면 매수 우위)
      · 체결   같은 응답의 output 30건(초 단위)
    검증: 2026-07-21 마감값이 네이버 호가창과 완전 일치
          (매도 183,629@259,000 · 매수 38,824@258,500 · 총잔량 1,220,989 / 337,861)
    """
    if not re.fullmatch(r"[0-9]{6}", code):
        raise HTTPException(400, "bad code")
    if not _logged_in(request):
        raise HTTPException(401, "로그인 후 이용 가능합니다(KIS 부하 보호)")
    now = time.time()
    hit = _ob_cache.get(code)
    if hit and now - hit[0] < 5:          # 실시간이라 5초만 캐시(연타 방어)
        return hit[1]
    try:
        sys.path.insert(0, str(BASE / "scripts"))
        import kis_api as _K
        c = _K._creds()
        if not c:
            return {"err": "KIS 키 없음"}
        tok = _K._token(c)
        a = _K._get(c, tok, "/uapi/domestic-stock/v1/quotations/inquire-asking-price-exp-ccn",
                    "FHKST01010200", {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": code})
        o1 = a.get("output1") or {}
        o2 = a.get("output2") or {}

        def _i(z):
            try:
                return int(str(z).replace(",", "").strip())
            except Exception:
                return None
        ask = [{"p": _i(o1.get("askp%d" % i)), "q": _i(o1.get("askp_rsqn%d" % i))} for i in range(1, 11)]
        bid = [{"p": _i(o1.get("bidp%d" % i)), "q": _i(o1.get("bidp_rsqn%d" % i))} for i in range(1, 11)]
        # (2026-07-21) 체결 소스를 inquire-ccnl → inquire-time-itemconclusion 으로 교체.
        #   후자는 각 체결에 '그 시점의 매도/매수호가(askp/bidp)'를 준다 → 체결가를 호가와 비교해
        #   매수(매도호가 이상)·매도(매수호가 이하)를 실측 판정할 수 있다.
        #   틱 규칙(직전가 대비)은 삼성전자처럼 같은 가격 연속 체결이면 전부 '중립(—)'이 돼 무의미했다.
        from datetime import timezone as _tz0, timedelta as _td0
        _kn = datetime.now(_tz0(_td0(hours=9)))
        _hh0 = "%02d%02d00" % (min(_kn.hour, 15) if _kn.hour != 15 or _kn.minute <= 30 else 15,
                               _kn.minute if not (_kn.hour == 15 and _kn.minute > 30) else 30)
        t = _K._get(c, tok, "/uapi/domestic-stock/v1/quotations/inquire-time-itemconclusion",
                    "FHPST01060000", {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": code,
                                      "FID_INPUT_HOUR_1": _hh0})
        tk = t.get("output2") or []
        if not tk:      # 장 시작 전 등 — 마감 스냅으로 폴백
            t = _K._get(c, tok, "/uapi/domestic-stock/v1/quotations/inquire-time-itemconclusion",
                        "FHPST01060000", {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": code,
                                          "FID_INPUT_HOUR_1": "153000"})
            tk = t.get("output2") or []
        # 장중 투자자 가집계(잠정) — 거래소가 장중 몇 차례 발표하는 외인·기관 추정 순매수.
        #   확정치는 마감 후에 나오므로, 장중에 방향을 보려면 이 잠정치뿐이다.
        frg = org = None; est_series = []
        try:
            iv = _K._get(c, tok, "/uapi/domestic-stock/v1/quotations/investor-trend-estimate",
                         "HHPTJ04160200", {"MKSC_SHRN_ISCD": code})
            rows = iv.get("output2") or []
            # 회차(bsop_hour_gb 1~5)별 '당일 누적' 추정 순매수 — 오름차순 = 시간 진행.
            series = sorted(rows, key=lambda z: str(z.get("bsop_hour_gb") or ""))
            est_series = [{"gb": _i(z.get("bsop_hour_gb")),
                           "frg": _i(z.get("frgn_fake_ntby_qty")),
                           "org": _i(z.get("orgn_fake_ntby_qty"))} for z in series]
            if series:
                last = series[-1]
                frg, org = _i(last.get("frgn_fake_ntby_qty")), _i(last.get("orgn_fake_ntby_qty"))
        except Exception:
            est_series = []

        # ── 체결·호가에 나타난 '압력' 요약 (매매 권유가 아니라 현재 주문흐름의 서술)
        st = None
        try:
            st = float(tk[0].get("tday_rltv")) if tk else None
        except Exception:
            st = None
        at_, bt_ = _i(o1.get("total_askp_rsqn")), _i(o1.get("total_bidp_rsqn"))
        ratio = (bt_ / at_) if (at_ and bt_) else None          # 매수잔량 ÷ 매도잔량
        # (2026-07-21) '최근 30체결 중 상승'(수 초 노이즈·거의 항상 100%)을 빼고
        #   체결강도 '추세'(1시간 전 대비)로 대체 — 힘이 붙는 중인지 빠지는 중인지가 진짜 정보다.
        st_prev = None
        try:
            from datetime import timezone as _tz, timedelta as _td3
            _kst = _tz(_td3(hours=9))
            _nm = datetime.now(_kst); _m = _nm.hour * 60 + _nm.minute - 60
            _m = min(max(_m, 9 * 60 + 30), 15 * 60 + 30)
            _hh = "%02d%02d00" % (_m // 60, _m % 60)
            _r = _K._get(c, tok, "/uapi/domestic-stock/v1/quotations/inquire-time-itemconclusion",
                         "FHPST01060000", {"FID_COND_MRKT_DIV_CODE": "J",
                                          "FID_INPUT_ISCD": code, "FID_INPUT_HOUR_1": _hh})
            _o = (_r.get("output2") or [])
            if _o:
                st_prev = float(_o[0].get("tday_rltv") or 0)
        except Exception:
            st_prev = None
        parts, sc = [], 0
        if st is not None:
            v = 2 if st >= 120 else (1 if st >= 105 else (0 if st > 95 else (-1 if st > 80 else -2)))
            sc += v; parts.append({"k": "체결강도(당일 누적)", "v": round(st, 1), "s": v,
                                   "d": "100 초과 = 매수 체결 우위"})
        if st is not None and st_prev is not None:
            d1 = st - st_prev
            v = 1 if d1 >= 3 else (-1 if d1 <= -3 else 0)
            sc += v; parts.append({"k": "체결강도 추세(1시간)", "v": "%+.1f" % d1, "s": v,
                                   "d": "1시간 전 대비 — 오르면 매수세 유입, 내리면 이탈. 방금 30체결(수 초)보다 이 추세가 신뢰도 높다"})
        if ratio is not None:
            v = 1 if ratio >= 1.2 else (-1 if ratio <= 0.83 else 0)
            sc += v; parts.append({"k": "호가 잔량비(매수÷매도)", "v": round(ratio, 2), "s": v,
                                   "d": "1 초과 = 아래 받치는 물량이 두꺼움. 단 위쪽 매도벽은 저항이자 돌파 시 신호라 해석이 갈린다"})
        if frg is not None and org is not None:
            tot = frg + org
            v = 1 if tot > 0 else (-1 if tot < 0 else 0)
            sc += v; parts.append({"k": "외인+기관 가집계", "v": tot, "s": v,
                                   "d": "장중 추정 순매수(잠정) — 확정치는 마감 후"})
        lab = ("매수 우위" if sc >= 3 else "약한 매수 우위" if sc >= 1 else
               "중립" if sc == 0 else "약한 매도 우위" if sc >= -2 else "매도 우위")
        res = {"ask": ask, "bid": bid,
               "ask_tot": at_, "bid_tot": bt_,
               "at": o1.get("aspr_acpt_hour"),
               "px": _i(o2.get("stck_prpr")),
               "strength": (tk[0].get("tday_rltv") if tk else None),
               "frg_est": frg, "org_est": org, "est_series": est_series,
               "score": sc, "label": lab, "parts": parts,
               "ticks": [{"t": x.get("stck_cntg_hour"), "p": _i(x.get("stck_prpr")),
                          "v": _i(x.get("cnqn")), "sg": x.get("prdy_vrss_sign"),
                          "ask": _i(x.get("askp")), "bid": _i(x.get("bidp"))}
                         for x in tk[:30]],
               "src": "KIS(%s) 실시간" % c.get("mode")}
        # (2026-07-21) 체결별 매수/매도 판정 — 호가 우선 + 틱 규칙 보조(혼합).
        #   1차: 체결가 >= 매도호가 → 매수 주도 / <= 매수호가 → 매도 주도
        #   2차(중간가 체결): 직전 체결가 대비 오르면 매수·내리면 매도로 보조 판정
        #   그래도 안 갈리면 중립(중간가 매칭 — NXT 중간가·종가 단일가에서 흔함, 매수·매도 균형).
        _tks = res["ticks"]
        _prev = None
        for i in range(len(_tks) - 1, -1, -1):
            p_, a_, b_ = _tks[i]["p"], _tks[i].get("ask"), _tks[i].get("bid")
            older = _tks[i + 1]["p"] if i + 1 < len(_tks) else None
            d = None
            if p_ is not None and a_ and b_:
                if p_ >= a_:
                    d = "buy"
                elif p_ <= b_:
                    d = "sell"
            if d is None and p_ is not None and older is not None:   # 중간가 → 틱 규칙 보조
                d = "buy" if p_ > older else ("sell" if p_ < older else None)
            if d is None:
                d = "mid"
            _tks[i]["side"] = d
            if d in ("buy", "sell"):
                _prev = d
        bq = sum(t["v"] or 0 for t in _tks if t["side"] == "buy")
        sq = sum(t["v"] or 0 for t in _tks if t["side"] == "sell")
        res["tick_buy"] = bq
        res["tick_sell"] = sq
        _ob_cache[code] = (now, res)
        if len(_ob_cache) > 200:
            _ob_cache.clear()
        return res
    except Exception as e:
        return {"err": repr(e)[:100]}


_str_cache = {}


@app.get("/api/strength/kr/{code}")
def strength_curve_api(request: Request, code: str):
    """체결강도 '장중 추이' — 09:30부터 30분 간격으로 스냅샷.

    (2026-07-21) '최근 30체결'은 삼성전자처럼 유동성 큰 종목에선 1~2초라 노이즈다.
    체결강도(tday_rltv)는 당일 누적이라 값 하나론 흐름을 못 본다.
    → inquire-time-itemconclusion 의 FID_INPUT_HOUR_1 로 특정 시각의 체결강도를 조회할 수 있어
      하루를 30분 간격으로 훑어 곡선을 만든다. '매수세가 붙는 중인지 빠지는 중인지'가 보인다.
    실측(005930): 10시 68.7 → 11:30 90.0 → 13시 86.8 → 14:30 81.1 → 15시 82.9
    과거 시각 값은 고정이라 캐시를 길게 잡는다(5분).
    """
    if not re.fullmatch(r"[0-9]{6}", code):
        raise HTTPException(400, "bad code")
    if not _logged_in(request):
        raise HTTPException(401, "로그인 후 이용 가능합니다")
    now = time.time()
    hit = _str_cache.get(code)
    if hit and now - hit[0] < 300:
        return hit[1]
    try:
        from concurrent.futures import ThreadPoolExecutor
        sys.path.insert(0, str(BASE / "scripts"))
        import kis_api as _K
        c = _K._creds()
        if not c:
            return {"err": "KIS 키 없음"}
        tok = _K._token(c)
        # KST 현재 분 — 장중이면 지금까지, 마감 후면 15:30 까지
        from datetime import timezone, timedelta
        kst = timezone(timedelta(hours=9))
        nm = datetime.now(kst)
        cur = nm.hour * 60 + nm.minute
        cur = min(max(cur, 9 * 60 + 30), 15 * 60 + 30)
        slots = list(range(9 * 60 + 30, cur + 1, 30))
        if slots and slots[-1] != cur:
            slots.append(cur)

        def _one(m):
            hh = "%02d%02d00" % (m // 60, m % 60)
            try:
                r = _K._get(c, tok, "/uapi/domestic-stock/v1/quotations/inquire-time-itemconclusion",
                            "FHPST01060000", {"FID_COND_MRKT_DIV_CODE": "J",
                                              "FID_INPUT_ISCD": code, "FID_INPUT_HOUR_1": hh})
                o = (r.get("output2") or [])
                if not o:
                    return None
                x = o[0]
                return {"t": "%02d:%02d" % (m // 60, m % 60),
                        "cttr": float(x.get("tday_rltv") or 0),
                        "vol": int(x.get("acml_vol") or 0)}
            except Exception:
                return None

        with ThreadPoolExecutor(max_workers=8) as ex:
            pts = [p for p in ex.map(_one, slots) if p]
        # 구간 거래량(그 30분에 실제로 붙은 양) = 누적 차분
        for i in range(len(pts) - 1, 0, -1):
            pts[i]["dvol"] = pts[i]["vol"] - pts[i - 1]["vol"]
        if pts:
            pts[0]["dvol"] = pts[0]["vol"]
        res = {"pts": pts, "src": "KIS 실시간"}
        _str_cache[code] = (now, res)
        if len(_str_cache) > 200:
            _str_cache.clear()
        return res
    except Exception as e:
        return {"err": repr(e)[:100]}


_tick_cache = {}


@app.get("/api/ticks/kr/{code}")
def ticks_api(request: Request, code: str, pages: int = 6):
    """시간별 시세(체결가 + 그 시점 매도/매수 호가) — 네이버 sise_time 파싱.

    (2026-07-21) 분봉 차트 아래에 붙여 '공격성'을 같이 본다.
      체결가 >= 매도호가 → 공격적 매수(사는 쪽이 값을 올려 가져감)
      체결가 <= 매수호가 → 공격적 매도(파는 쪽이 값을 내려 던짐)
      그 사이            → 중립
    호가 스냅샷이 체결 직후 값이라 정확히 일치하지 않는 경우가 있어 '=' 가 아니라 부등호로 판정한다.
    한 페이지 10행(1분 단위) — 기본 6페이지 ≈ 60분.

    ※ 네이버 고지대로 이 데이터는 20분 지연이다. 실시간 진입 판단용이 아니라
      '방금까지 매수·매도 중 어느 쪽이 공격적이었나'를 사후 확인하는 용도다.
    """
    if not re.fullmatch(r"[0-9A-Za-z]{6}", code):
        raise HTTPException(400, "bad code")
    if not _logged_in(request):
        raise HTTPException(401, "로그인 후 이용 가능합니다")
    pages = max(1, min(int(pages or 6), 12))
    now = time.time()
    key = f"{code}:{pages}"
    hit = _tick_cache.get(key)
    if hit and now - hit[0] < 30:
        return hit[1]
    out, seen = [], set()

    def _parse(html):
        rows = []
        for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S):
            tds = [re.sub(r"<[^>]+>", "", x).replace("&nbsp;", " ").strip()
                   for x in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
            tds = [t for t in tds if t.strip()]
            if len(tds) >= 7 and re.match(r"^\d{2}:\d{2}", tds[0]):
                rows.append(tds)
        return rows

    def _get(tt, pg):
        url = ("https://finance.naver.com/item/sise_time.naver"
               "?code=%s&thistime=%s&page=%d" % (code, tt, pg))
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0",
                                                   "Referer": "https://finance.naver.com/"})
        return urllib.request.urlopen(req, timeout=10).read().decode("euc-kr", "ignore")

    try:
        # thistime 은 '거래일'이어야 한다. 휴장일·장 시작 전이면 빈 표가 온다(실측).
        # → 오늘(현재시각)부터 시작해 하루씩 거슬러 올라가며 데이터가 있는 날을 찾는다.
        from datetime import timedelta as _td2
        cands = [datetime.now().strftime("%Y%m%d%H%M%S")] + [
            (datetime.now() - _td2(days=k)).strftime("%Y%m%d") + "160000" for k in range(0, 8)]
        thistime, first = None, []
        for tt in cands:
            r0 = _parse(_get(tt, 1))
            if r0:
                thistime, first = tt, r0
                break
        if not thistime:
            return {"items": [], "err": "최근 8일 내 시간별시세 없음"}
        for pg in range(1, pages + 1):
            url = None
            n0 = len(out)
            for tds in (first if pg == 1 else _parse(_get(thistime, pg))):
                if tds[0] in seen:
                    continue
                seen.add(tds[0])

                def _n(z):
                    try:
                        return int(str(z).replace(",", "").strip())
                    except Exception:
                        return None
                px, ask, bid = _n(tds[1]), _n(tds[3]), _n(tds[4])
                side = None
                if px is not None and ask is not None and bid is not None:
                    side = "buy" if px >= ask else ("sell" if px <= bid else "mid")
                out.append({"t": tds[0], "px": px, "ask": ask, "bid": bid,
                            "cum": _n(tds[5]), "vol": _n(tds[6]), "side": side})
            if len(out) == n0:       # 더 이상 안 나오면 중단(장 시작 전 구간 등)
                break
        # 체결강도 = 공격적 매수 거래량 / 공격적 매도 거래량 × 100 (100 초과면 매수 우위)
        bv = sum(r["vol"] or 0 for r in out if r["side"] == "buy")
        sv = sum(r["vol"] or 0 for r in out if r["side"] == "sell")
        res = {"items": out, "buy_vol": bv, "sell_vol": sv,
               "date": thistime[:8],
               "strength": round(bv / sv * 100, 1) if sv else None,
               "delay": "20분 지연(네이버 고지)"}
        _tick_cache[key] = (now, res)
        if len(_tick_cache) > 200:
            _tick_cache.clear()
        return res
    except Exception as e:
        return {"items": [], "err": repr(e)[:80]}


_chart_cache = {}

def _agg(t, o, h, l, c, v, keyfn):
    """봉 합치기 — keyfn(시각문자열)이 같은 것끼리 시가=처음·고가=max·저가=min·종가=마지막·거래량=합.
    분봉→N분봉, 일봉→주봉·월봉 모두 이 하나로 처리한다."""
    T, O, H, L, C, V = [], [], [], [], [], []
    prev = None
    for i in range(len(t)):
        if c[i] is None:
            continue
        k = keyfn(t[i])
        if k != prev:
            T.append(t[i]); O.append(o[i]); H.append(h[i]); L.append(l[i]); C.append(c[i]); V.append(v[i] or 0)
            prev = k
        else:
            if H[-1] is None or (h[i] is not None and h[i] > H[-1]): H[-1] = h[i]
            if L[-1] is None or (l[i] is not None and l[i] < L[-1]): L[-1] = l[i]
            C[-1] = c[i]; V[-1] = (V[-1] or 0) + (v[i] or 0)
    return {"t": T, "o": O, "h": H, "l": L, "c": C, "v": V}


# 지원 주기 — 네이버 차트와 동일 구성(분봉 드롭다운 + 일/주/월)
TF_MIN = {"1m": 1, "3m": 3, "5m": 5, "10m": 10, "30m": 30, "60m": 60}


@app.get("/api/chart/{mkt}/{code}")
def chart_api(request: Request, mkt: str, code: str, tf: str = "d"):
    """종목 차트 프록시 — KR: 네이버 / US: Yahoo v8.

    tf: 1m·3m·5m·10m·30m·60m(분봉) · d(일) · w(주) · M(월)
      · KR 분봉은 네이버가 1분봉만 준다(interval 파라미터 무시) → 서버에서 N분으로 합친다.
        실측: 1분봉 3,400개 = 최근 9거래일. 5분 집계 시 약 680봉.
      · US 분봉은 Yahoo 가 1m(최근 5일)·5m(최근 1개월)을 준다. 3분은 1m 에서, 10·30·60분은 5m 에서 합친다.
      · 주·월봉은 일봉을 합쳐서 만든다(추가 호출 없음).
    캐시: 분봉 30초 / 그 외 60초.
    """
    if mkt not in ("kr", "us") or not re.fullmatch(r"[A-Za-z0-9.\-]{1,12}", code):
        raise HTTPException(400, "bad params")
    if tf not in TF_MIN and tf not in ("d", "w", "M"):
        raise HTTPException(400, "bad tf")
    if tf in TF_MIN and not _logged_in(request):
        raise HTTPException(401, "분봉은 로그인 후 이용 가능합니다(KIS·외부 API 부하 보호)")
    key = f"{mkt}:{code}:{tf}"; now = time.time()
    hit = _chart_cache.get(key)
    if hit and now - hit[0] < (30 if tf in TF_MIN else 60):
        return hit[1]
    try:
        from datetime import date as _d, timedelta as _td, datetime as _dt
        if tf in TF_MIN:
            n = TF_MIN[tf]
            if mkt == "kr":
                E = _d.today().strftime("%Y%m%d") + "1600"
                S = (_d.today() - _td(days=20)).strftime("%Y%m%d") + "0900"
                url = (f"https://api.stock.naver.com/chart/domestic/item/{code}"
                       f"/minute?startDateTime={S}&endDateTime={E}")
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0",
                                                           "Referer": "https://m.stock.naver.com/"})
                rows = json.loads(urllib.request.urlopen(req, timeout=15).read())
                t = [str(r.get("localDateTime") or "")[:12] for r in rows]
                base = {"t": t,
                        "o": [r.get("openPrice") for r in rows], "h": [r.get("highPrice") for r in rows],
                        "l": [r.get("lowPrice") for r in rows], "c": [r.get("currentPrice") for r in rows],
                        "v": [r.get("accumulatedTradingVolume") for r in rows]}
            else:
                iv, rg = ("1m", "5d") if n <= 3 else ("5m", "1mo")
                url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(code)}"
                       f"?range={rg}&interval={iv}")
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                j = json.loads(urllib.request.urlopen(req, timeout=15).read())
                res = j["chart"]["result"][0]; q = res["indicators"]["quote"][0]
                off = (res.get("meta") or {}).get("gmtoffset") or 0     # 현지 거래시각으로 표시
                ts = res.get("timestamp") or []
                base = {"t": [_dt.utcfromtimestamp(x + off).strftime("%Y%m%d%H%M") for x in ts],
                        "o": q.get("open"), "h": q.get("high"), "l": q.get("low"),
                        "c": q.get("close"), "v": q.get("volume")}
            # 분 단위 버킷 — 같은 날짜 안에서 (시*60+분)//n
            def _kf(s):
                return s[:8] + str((int(s[8:10]) * 60 + int(s[10:12])) // n)
            out = _agg(base["t"], base["o"], base["h"], base["l"], base["c"], base["v"], _kf) \
                if n > 1 else base
            out["tf"] = tf
        else:
            # 필요한 이력 = 표시 250봉 + 최장 이동평균(240) + 줌아웃 여유.
            #   일 10년(≈2,500봉) · 주 15년(≈780주) · 월 30년(≈360개월)
            #   실측: 네이버 일봉은 1990년까지, Yahoo 는 상장 이후 전부 준다.
            YRS = {"d": 10, "w": 15, "M": 30}[tf]
            if mkt == "kr":
                E = _d.today().strftime("%Y%m%d")
                S = (_d.today() - _td(days=int(YRS * 366))).strftime("%Y%m%d")
                url = f"https://api.stock.naver.com/chart/domestic/item/{code}/day?startDateTime={S}&endDateTime={E}"
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                rows = json.loads(urllib.request.urlopen(req, timeout=20).read())
                out = {"t": [str(r.get("localDate") or "") for r in rows],
                       "o": [r.get("openPrice") for r in rows], "h": [r.get("highPrice") for r in rows],
                       "l": [r.get("lowPrice") for r in rows], "c": [r.get("closePrice") for r in rows],
                       "v": [r.get("accumulatedTradingVolume") for r in rows]}
            else:
                # range=max 는 Yahoo 가 자동으로 주/월로 다운샘플해 버린다(실측: 27년치가 331봉).
                # 반드시 period1/period2 로 기간을 지정해야 진짜 일봉이 온다.
                _p2 = int(time.time()); _p1 = _p2 - int(YRS * 366 * 86400)
                url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(code)}"
                       f"?period1={_p1}&period2={_p2}&interval=1d")
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                j = json.loads(urllib.request.urlopen(req, timeout=20).read())
                res = j["chart"]["result"][0]; q = res["indicators"]["quote"][0]
                ts = res.get("timestamp") or []
                out = {"t": [_dt.utcfromtimestamp(x).strftime("%Y%m%d") for x in ts],
                       "o": q.get("open"), "h": q.get("high"), "l": q.get("low"),
                       "c": q.get("close"), "v": q.get("volume")}
            if tf == "w":
                out = _agg(out["t"], out["o"], out["h"], out["l"], out["c"], out["v"],
                           lambda s: _dt.strptime(s, "%Y%m%d").strftime("%G%V"))   # ISO 주
            elif tf == "M":
                out = _agg(out["t"], out["o"], out["h"], out["l"], out["c"], out["v"], lambda s: s[:6])
            out["tf"] = tf
        _chart_cache[key] = (now, out)
        if len(_chart_cache) > 300:
            _chart_cache.clear()
        return out
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(502, f"chart fetch failed: {e}")

# ── ETF 주요 구성종목·비중 (상세 열 때 온디맨드) ──
#   KR: 네이버 모바일 etfAnalysis → etfTop10MajorConstituentAssets (Top10 종목·비중)
#   US: Yahoo quoteSummary topHoldings (crumb 인증 필요 → ta_screen.yahoo_opener 재사용)
#   6시간 메모리 캐시. 실패해도 200 + 빈 holdings (프론트가 '정보 없음' 표기).
_hold_cache = {}
_hold_qcache = {}   # ETF 구성종목 시세(현재가·전일비·등락률) 45초 캐시
_yop = {"op": None, "crumb": None, "ts": 0.0}

def _pctnum(s):
    if s is None:
        return None
    if isinstance(s, (int, float)):
        return float(s)
    m = re.search(r"-?[\d.]+", str(s).replace(",", ""))
    return float(m.group(0)) if m else None

def _yahoo_oc():
    import sys as _sys
    if _yop["op"] and time.time() - _yop["ts"] < 1800:
        return _yop["op"], _yop["crumb"]
    _sys.path.insert(0, str(BASE / "scripts"))
    import ta_screen as _T
    op, crumb = _T.yahoo_opener()
    _yop.update(op=op, crumb=crumb, ts=time.time())
    return op, crumb

def _etf_quotes(mkt, codes):
    """구성종목 코드 → {code: {px 현재가, chg 전일비(부호), chgp 등락률%(부호)}}.
       KR: 네이버 폴링 배치(1회 호출, delayTime=0 실시간). US: Yahoo v7 quote(crumb). 실패 비차단."""
    codes = [c for c in dict.fromkeys(codes) if c]
    if not codes:
        return {}
    qm = {}
    try:
        if mkt == "kr":
            qu = "https://polling.finance.naver.com/api/realtime/domestic/stock/" + ",".join(codes)
            qreq = urllib.request.Request(qu, headers={
                "User-Agent": "Mozilla/5.0", "Referer": "https://finance.naver.com/"})
            qd = json.loads(urllib.request.urlopen(qreq, timeout=10).read().decode("utf-8", "ignore"))
            for it in (qd.get("datas") or []):
                # compareToPreviousClosePrice·fluctuationsRatio 는 이미 부호 포함(하락 = 음수).
                qm[it.get("itemCode")] = {"px": _pctnum(it.get("closePrice")),
                                          "chg": _pctnum(it.get("compareToPreviousClosePrice")),
                                          "chgp": _pctnum(it.get("fluctuationsRatio"))}
        else:
            import sys as _sys
            _sys.path.insert(0, str(BASE / "scripts"))
            import ta_screen as _T
            op, crumb = _yahoo_oc()
            qu = ("https://query1.finance.yahoo.com/v7/finance/quote?symbols=%s&crumb=%s"
                  % (urllib.parse.quote(",".join(codes)), urllib.parse.quote(crumb)))
            qj = _T.jget(qu, opener=op, timeout=12)
            for it in ((qj.get("quoteResponse", {}) or {}).get("result") or []):
                rnd = lambda v: round(v, 2) if isinstance(v, (int, float)) else None
                qm[it.get("symbol")] = {"px": rnd(it.get("regularMarketPrice")),
                                        "chg": rnd(it.get("regularMarketChange")),
                                        "chgp": rnd(it.get("regularMarketChangePercent"))}
    except Exception:
        pass
    return qm

@app.get("/api/etf/holdings/{mkt}/{code}")
def etf_holdings(mkt: str, code: str):
    if mkt not in ("kr", "us") or not re.fullmatch(r"[A-Za-z0-9.\-]{1,12}", code):
        raise HTTPException(400, "bad params")
    key = f"{mkt}:{code}"; now = time.time()
    # ── 구성종목(이름·비중·코드): 6시간 캐시 ──
    hit = _hold_cache.get(key)
    if hit and now - hit[0] < 6 * 3600:
        base = hit[1]
    else:
        base = {"mkt": mkt, "code": code, "holdings": []}
        try:
            if mkt == "kr":
                url = f"https://m.stock.naver.com/api/stock/{code}/etfAnalysis"
                req = urllib.request.Request(url, headers={
                    "User-Agent": "Mozilla/5.0", "Referer": "https://m.stock.naver.com/"})
                d = json.loads(urllib.request.urlopen(req, timeout=12).read().decode("utf-8", "ignore"))
                for x in (d.get("etfTop10MajorConstituentAssets") or []):
                    nm = x.get("itemName")
                    if not nm:
                        continue
                    base["holdings"].append({"n": nm, "c": x.get("itemCode") or "",
                                             "w": _pctnum(x.get("etfWeight"))})
            else:
                import sys as _sys
                _sys.path.insert(0, str(BASE / "scripts"))
                import ta_screen as _T
                op, crumb = _yahoo_oc()
                url = ("https://query1.finance.yahoo.com/v10/finance/quoteSummary/%s"
                       "?modules=topHoldings&crumb=%s"
                       % (urllib.parse.quote(code), urllib.parse.quote(crumb)))
                j = _T.jget(url, opener=op, timeout=15)
                th = ((j.get("quoteSummary", {}).get("result") or [{}])[0] or {}).get("topHoldings", {}) or {}
                for h in (th.get("holdings") or []):
                    nm = h.get("holdingName") or h.get("symbol")
                    if not nm:
                        continue
                    hp = h.get("holdingPercent") or {}
                    w = hp.get("raw")
                    w = round(w * 100, 2) if isinstance(w, (int, float)) else _pctnum(hp.get("fmt"))
                    base["holdings"].append({"n": nm, "c": h.get("symbol") or "", "w": w})
        except Exception as e:
            base["err"] = str(e)[:120]
        _hold_cache[key] = (now, base)
        if len(_hold_cache) > 600:
            _hold_cache.clear()
    # ── 시세·전일비·등락률 조인: 45초 캐시(장중 변동 반영, 네이버처럼) ──
    out = {"mkt": mkt, "code": code, "holdings": [dict(h) for h in base["holdings"]]}
    if base.get("err"):
        out["err"] = base["err"]
    qhit = _hold_qcache.get(key)
    if qhit and now - qhit[0] < 45:
        qm = qhit[1]
    else:
        qm = _etf_quotes(mkt, [h.get("c") for h in out["holdings"]])
        _hold_qcache[key] = (now, qm)
        if len(_hold_qcache) > 800:
            _hold_qcache.clear()
    for h in out["holdings"]:
        q = qm.get(h.get("c"))
        if q:
            h.update(q)
    out["quoted"] = bool(qm)
    return out

# ── 종목별 투자자 수급 (외국인·기관·개인 누적순매수) ──
#   1년치: 네이버 frgn.naver 13페이지 (외국인·기관 순매매량만 제공)
#   최근 30거래일: KIS FHKST01010900 (개인 포함 3주체 실측 — 네이버 값과 일치 검증됨)
#   병합: KIS 구간은 KIS 우선(개인 실측), 그 이전 개인은 null → 프론트가 −(외인+기관) 추정 점선
_inv_cache = {}

def _frgn_naver(code: str, pages: int = 80):
    # (2026-07-21) 13페이지(≈1년) → 80페이지(≈6.5년).
    #   일봉 이력을 10년으로 늘린 뒤 수급 패널만 1년이라 화면 오른쪽 끝에만 그려졌다.
    #   실측: frgn.naver 는 2005년까지 제공하고, 10워커 병렬로 80페이지 3.7초.
    #   확정치라 하루 1번만 바뀌므로 캐시를 길게 잡아 반복 호출을 없앤다.
    """finance.naver.com/item/frgn.naver 표 파싱 → [(YYYYMMDD, 기관, 외인)]"""
    from concurrent.futures import ThreadPoolExecutor
    def one(p):
        url = f"https://finance.naver.com/item/frgn.naver?code={code}&page={p}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        html = urllib.request.urlopen(req, timeout=12).read().decode("euc-kr", "ignore")
        out = []
        for m in re.finditer(r"<tr[^>]*>(.*?)</tr>", html, re.S):
            cells = [re.sub(r"<[^>]+>", "", c).strip().replace(",", "")
                     for c in re.findall(r"<td[^>]*>(.*?)</td>", m.group(1), re.S)]
            # 일별 표만: 날짜·종가·전일비·등락률·거래량·기관·외인·보유주수·보유율(%) = 9칸
            if len(cells) < 9 or "%" not in cells[8]:
                continue
            dm = re.match(r"(\d{4})\.(\d{2})\.(\d{2})", cells[0])
            if not dm:
                continue
            try:
                org, frg = int(cells[5]), int(cells[6])
            except ValueError:
                continue
            out.append((dm.group(1) + dm.group(2) + dm.group(3), org, frg))
        return out
    rows = []
    with ThreadPoolExecutor(max_workers=6) as ex:
        for part in ex.map(one, range(1, pages + 1)):
            rows.extend(part)
    return rows

def _kis_investor(code: str):
    """KIS 종목별 투자자매매동향(일별 30행) → {YYYYMMDD: (기관, 외인, 개인)}"""
    import sys as _s
    sp = str(BASE / "scripts")
    if sp not in _s.path:
        _s.path.insert(0, sp)
    import kis_api as K
    c = K._creds(); tok = K._token(c)
    j = K._get(c, tok, "/uapi/domestic-stock/v1/quotations/inquire-investor", "FHKST01010900",
               {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": code})
    out = {}
    for r in (j.get("output") or []):
        try:
            out[r["stck_bsop_date"]] = (int(r["orgn_ntby_qty"]), int(r["frgn_ntby_qty"]), int(r["prsn_ntby_qty"]))
        except (KeyError, ValueError, TypeError):
            continue
    return out

@app.get("/api/investor/kr/{code}")
def investor_api(code: str):
    if not re.fullmatch(r"\d{6}", code):
        raise HTTPException(400, "bad code")
    now = time.time(); hit = _inv_cache.get(code)
    if hit and now - hit[0] < 21600:     # 6시간 캐시 — 투자자별 순매매는 마감 후 확정이라 하루 1번만 바뀐다
        return hit[1]
    data = {}
    try:
        for d, org, frg in _frgn_naver(code):
            data[d] = {"o": org, "f": frg, "p": None}
    except Exception:
        pass
    kis_from = None
    try:
        k = _kis_investor(code)
        for d, (o_, f_, p_) in k.items():
            data[d] = {"o": o_, "f": f_, "p": p_}
        if k:
            kis_from = min(k)
    except Exception:
        pass
    if not data:
        raise HTTPException(502, "investor fetch failed")
    ts = sorted(data)
    out = {"t": ts,
           "orgn": [data[d]["o"] for d in ts],
           "frgn": [data[d]["f"] for d in ts],
           "prsn": [data[d]["p"] for d in ts],
           "kis_from": kis_from}
    _inv_cache[code] = (now, out)
    if len(_inv_cache) > 200:
        _inv_cache.clear()
    return out

@app.get("/api/stock_deriv/{code}")
def stock_deriv_api(code: str):
    """종목별 파생 포지셔닝 — KR 파생상장 전 종목(FSC T+1) + US 옵션 종목(Yahoo, 티커).
       5지표(베이시스·선물OI·PCR(OI)·IV스큐·GEX — US는 옵션 3종만) 시계열 + 60일 z.
       미수록 종목은 404 → 프론트가 프록시 카드로 대체."""
    if not re.fullmatch(r"[A-Za-z0-9.\-]{1,12}", code):
        raise HTTPException(400, "bad code")
    p = DB / "stock_deriv.json"
    if not p.exists():
        raise HTTPException(404, "stock_deriv 없음")
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        raise HTTPException(500, f"stock_deriv 파싱 실패: {e}")
    s = (d.get("stocks") or {}).get(code)
    if not s or not s.get("days"):
        raise HTTPException(404, "파생 미상장 종목")
    # (2026-07-24) 주식선물만 상장·옵션 미상장 종목 구분 — 프론트가 '누적 중'이 아니라
    #   '옵션 미상장'으로 안내하도록 이력 전체에서 옵션값 존재 여부를 내려준다
    has_opt = any((x.get("pcr_oi") is not None) or (x.get("gex") is not None)
                  for x in s["days"])
    out = {"asof": d.get("asof"), "src": d.get("src"), "name": s.get("name"),
           "z": s.get("z"), "latest": s.get("latest"), "has_opt": has_opt,
           # 스파크라인용 최근 60일만 (전송량 절약)
           "days": s["days"][-60:]}
    return Response(content=json.dumps(out, ensure_ascii=False),
                    media_type="application/json", headers={"Cache-Control": "no-cache"})

@app.get("/api/reports")
def reports():
    out = []
    for p in sorted(RPT.glob("*.docx"), reverse=True):
        m = re.search(r"(\d{8})_(\d{4})", p.name)
        dt = ""
        if m:
            dt = f"{m.group(1)[:4]}-{m.group(1)[4:6]}-{m.group(1)[6:]} {m.group(2)[:2]}:{m.group(2)[2:]}"
        out.append({"file": p.name, "datetime": dt, "size_mb": round(p.stat().st_size/1024/1024, 1)})
    return out

@app.get("/reports/{fname}")
def download(fname: str):
    if not re.fullmatch(r"[\w\-\.]+\.docx", fname):
        raise HTTPException(400, "bad filename")
    p = RPT / fname
    if not p.exists():
        raise HTTPException(404, "not found")
    return FileResponse(p, filename=fname,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")

@app.get("/krxbrief/{sub}/{fname}")
def krxbrief_img(sub: str, fname: str):
    if not (re.fullmatch(r"[\w\-]+", sub) and re.fullmatch(r"[\w\-]+\.png", fname)):
        raise HTTPException(400, "bad path")
    p = BASE / "data" / "krx_brief" / sub / fname
    if not p.exists():
        raise HTTPException(404, "not found")
    return FileResponse(p, media_type="image/png")

@app.get("/api/poll/{metric}")
def poll(metric: str, limit: int = 200):
    """서버가 1일 2회 수집한 김치프리미엄·공포탐욕 시계열"""
    if not POLL.exists():
        return []
    c = sqlite3.connect(POLL)
    try:
        rows = c.execute(
            "SELECT ts, symbol, value FROM ticks WHERE metric=? ORDER BY ts DESC LIMIT ?",
            (metric, limit)).fetchall()
    except sqlite3.OperationalError:
        return []
    finally:
        c.close()
    return [{"ts": r[0], "symbol": r[1], "value": r[2]} for r in reversed(rows)]

KRLIQ = BASE / "data" / "kr_liquidity.db"

@app.get("/api/krliq")
def krliq(days: int = 420):
    """3.1.14 국내 유동성·레버리지 — 서버가 1일 3회 수집 (scripts/fetch_kr_liquidity.py).
    daily: [date, 예탁금, 미수금, 반대매매금액, 반대매매비중%, 신용전체, 신용코스피, 신용코스닥,
            코스피, 코스피거래대금, 코스닥, 코스닥거래대금]  (금액 원 단위)
    monthly: [month, M2(십억원), 코스피종가, 코스닥종가]
    verdict: ① 예탁금 5일 증감 × 회전배수 5일 방향 2×2 자동 판정"""
    if not KRLIQ.exists():
        raise HTTPException(404, "kr_liquidity.db not found")
    c = sqlite3.connect(KRLIQ)
    try:
        daily = c.execute(
            "SELECT date,deposit,ucol,opp_amt,opp_ratio,crd_whl,crd_kospi,crd_kosdaq,"
            "kospi,kospi_trdval,kosdaq,kosdaq_trdval FROM kr_liq_daily "
            "ORDER BY date DESC LIMIT ?", (days,)).fetchall()[::-1]
        monthly = c.execute(
            "SELECT month,m2,kospi,kosdaq FROM kr_liq_monthly ORDER BY month").fetchall()
        vrows = c.execute(         # 판정은 days 파라미터와 무관하게 최근 40행에서 계산
            "SELECT date,deposit,kospi_trdval FROM kr_liq_daily "
            "WHERE deposit IS NOT NULL AND kospi_trdval IS NOT NULL "
            "ORDER BY date DESC LIMIT 40").fetchall()[::-1]
    finally:
        c.close()
    verdict = None
    dep = vrows
    if len(dep) >= 6:
        d5 = (dep[-1][1] / dep[-6][1] - 1) * 100
        t_now, t_prev = dep[-1][2] / dep[-1][1], dep[-6][2] / dep[-6][1]
        t5 = (t_now - t_prev)
        lab = (("유입·가동", "강세") if d5 > 0 and t5 > 0 else
               ("유입·관망", "중립") if d5 > 0 else
               ("이탈·소진성 회전", "경계") if t5 > 0 else ("이탈·위축", "약세"))
        verdict = {"label": lab[0], "tone": lab[1], "dep_5d_pct": round(d5, 2),
                   "turn_5d_chg": round(t5, 4), "as_of": dep[-1][0]}
    return {"daily": daily, "monthly": monthly, "verdict": verdict}

@app.get("/api/health")
def health():
    return {"ok": True,
            "db_files": len(list(DB.glob("*.json"))),
            "reports": len(list(RPT.glob("*.docx"))),
            "now": datetime.now().isoformat(timespec="seconds")}

APK = BASE / "data" / "apk"

@app.get("/api/apk")
def apk_releases():
    """GitHub 릴리스 캐시 (scripts/sync_apk.py가 갱신)"""
    p = APK / "releases.json"
    if not p.exists():
        return []
    return json.loads(p.read_text(encoding="utf-8"))

@app.get("/apk/{fname}")
def apk_download(fname: str):
    if not re.fullmatch(r"[\w\-\.]+\.apk", fname):
        raise HTTPException(400, "bad filename")
    p = APK / fname
    if not p.exists():
        raise HTTPException(404, "not found")
    return FileResponse(p, filename=fname,
        media_type="application/vnd.android.package-archive")

# ── (2026-07-12) 6.2 코인 4종 1년 차트 (가격·거래량) ──
#   Binance 공개 klines 를 서버가 대신 받아 1시간 캐시한다. 인증·과금 없음.
#   클라이언트가 직접 부르면 CORS·사내망 차단에 걸리므로 서버 프록시로 우회한다.
COINS = {"BTC": "BTCUSDT", "ETH": "ETHUSDT", "XRP": "XRPUSDT", "SOL": "SOLUSDT"}
_coin_cache: dict = {}

@app.get("/api/coin/{sym}")
def coin_series(sym: str):
    sym = sym.upper()
    if sym not in COINS:
        raise HTTPException(404, "unknown symbol")
    now = time.time()
    hit = _coin_cache.get(sym)
    if hit and now - hit[0] < 3600:          # 1시간 캐시
        return hit[1]
    url = ("https://api.binance.com/api/v3/klines"
           f"?symbol={COINS[sym]}&interval=1d&limit=365")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "namoobi-dashboard"})
        with urllib.request.urlopen(req, timeout=15) as r:
            raw = json.loads(r.read().decode())
        out = {"symbol": sym, "pair": COINS[sym],
               "data": [{"t": k[0], "c": float(k[4]), "v": float(k[7])} for k in raw]}
        _coin_cache[sym] = (now, out)
        return out
    except Exception as e:
        if hit:                               # 실패 시 만료 캐시라도 준다
            return hit[1]
        return {"symbol": sym, "data": [], "error": str(e)}

# ── 로그인 + 방문자 통계 (개발자 전용) ──
#   반드시 아래 StaticFiles 마운트보다 먼저 등록해야 한다.
#   mount("/") 가 모든 경로를 가로채므로, 뒤에 붙이면 라우트가 죽는다.
try:
    from auth_visitors import router as _av_router
    app.include_router(_av_router)
except Exception as _e:
    print(f"[app] auth_visitors 로드 실패: {_e}")

# ── (2026-07-20) 관리자 수동 즉시 갱신 — 로그인 사용자만. START 재클릭 시 1분/3분 안 기다리고 강제 refresh ──
#   단일 워커라 동기 실행은 사이트를 멈춘다 → 백그라운드 subprocess + flock 로 중복 방지. 프론트가 풀 live_at 변화를 재폴링.
import subprocess as _sp
_REFRESH_MODS = {"screener": ("intraday_kr", "intraday_us"), "etf": ("etf_intraday",)}

@app.post("/api/admin/refresh/{which}")
def admin_refresh(which: str, request: Request):
    from auth_visitors import current_user
    if not current_user(request):
        raise HTTPException(401, "관리자 로그인이 필요합니다")
    mods = _REFRESH_MODS.get(which)
    if not mods:
        raise HTTPException(400, "대상이 올바르지 않습니다")
    lock = f"/tmp/refresh_{which}.lock"
    # 이미 실행 중이면(락 점유) 스킵 안내 — 그 실행이 곧 풀을 갱신한다
    import fcntl
    try:
        _lf = open(lock, "w")
        fcntl.flock(_lf, fcntl.LOCK_EX | fcntl.LOCK_NB)
        fcntl.flock(_lf, fcntl.LOCK_UN); _lf.close()
    except BlockingIOError:
        return {"busy": True, "which": which}
    code = "import sys; sys.path.insert(0,'scripts'); " + \
           "; ".join(f"import {m}; {m}.main(force=True)" for m in mods)
    try:
        _sp.Popen(["/usr/bin/flock", "-n", lock, "python3", "-c", code],
                  cwd=str(BASE), stdout=_sp.DEVNULL, stderr=_sp.DEVNULL,
                  start_new_session=True)
    except Exception as e:
        raise HTTPException(500, f"갱신 실행 실패: {e}")
    return {"started": True, "which": which}

# ── 추세 스파크라인 (docx 표의 '추세(1Y)' 열과 동일한 PNG) ──
#   리포트 실행 때 생성된 charts/spark_*.png 를 sync_server.py 가 올린다.
CHARTS = BASE / "data" / "charts"
CHARTS.mkdir(parents=True, exist_ok=True)
app.mount("/charts", StaticFiles(directory=CHARTS), name="charts")

app.mount("/", StaticFiles(directory=BASE / "static", html=True), name="static")
