#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""kis_close_capture.py — 장 마감 직후(cron 15:48 KST) KIS T+0 파생 지표 캡처. (2026-07-17 신설)

배경: PC 의 06시 예약 리포트 실행은 장전이라 거래량·IV 기반 지표(PCR(Vol)·IV스큐·GEX)가
구조적으로 왜곡된다(당일 거래량≈0, 이론가 IV — 실측 2026-07-17: PCR(Vol) 4,199 퇴화).
그래서 PC 쪽 ingest_kis_t0 에는 장전 가드(09:15 이전 미기록)가 있고, 이 스크립트가
서버에서 매 거래일 마감 직후 값을 떠 둔다. 다음날 아침 PC 파이프라인(ingest_server_close)이
ssh 로 kis_close.json 을 내려받아 NULL 셀만 병합한다.

- PCR(OI) 는 기록하지 않는다: 여기의 ±25% 창 스캔은 전체체인 PCR(OI) 로 부정확하며,
  아침 PC 실행이 KRX 전체체인 + KIS T+0 로 정확히 채운다. 거래량·IV·감마는 ATM 근처에
  집중되므로 창 스캔으로 충분하다.
- 자격증명: ~/namoobi/secrets/.env (KIS_ENV=real + REAL_APP_KEY/SECRET) — kis_api._seczone().
- cron: 48 15 * * *  (서버 TZ=Asia/Seoul, 옵션 정규장 15:45 마감 직후)
- 옵션: --force(시간 가드 무시) --dry(DB·JSON 기록 없이 계산만)
"""
import os, sys, json, sqlite3, datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kis_api

BASE = os.path.expanduser("~/namoobi")
DB = os.path.join(BASE, "data", "deriv_signals.db")
OUT = os.path.join(BASE, "data", "kis_close.json")
KID = "KOSPI200"


def main():
    now = datetime.datetime.now()  # 서버 TZ=Asia/Seoul
    force, dry = "--force" in sys.argv, "--dry" in sys.argv
    if (now.hour, now.minute) < (15, 45) and not force:
        print(f"[kis_close] {now:%m-%d %H:%M} 장 마감(15:45) 전 — skip (--force 로 무시 가능)")
        return 0
    # 주말 가드 (KRX 휴장일은 KIS 응답의 asof 로 걸러짐 — 값이 전 거래일이면 그 날짜로 기록)
    if now.weekday() >= 5 and not force:
        print(f"[kis_close] 주말({now:%a}) — skip")
        return 0
    if not kis_api._creds():
        print("[kis_close] KIS 키 없음(~/namoobi/secrets/.env) — skip")
        return 0

    fo = kis_api.futures_oi()
    if not fo:
        print("[kis_close] 선물 응답 없음(KIS 장애/키 차단) — skip")
        return 0

    # VKOSPI 당일 종가 (CNBC .KSVKOSPI — 무인증 T+0). KRX 공표는 T+1 이라 PC 미실행일에
    # 갭이 생긴다(실측: 7/13·7/15 None). 마감 직후 여기서 떠 두면 갭이 안 생긴다. 실패 비차단.
    vkospi = None
    try:
        import urllib.request as _ur
        u = ("https://quote.cnbc.com/quote-html-webservice/restQuote/symbolType/symbol"
             "?symbols=.KSVKOSPI&requestMethod=itv&noform=1&partnerId=2&fund=1&exthrs=1&output=json")
        q = json.loads(_ur.urlopen(_ur.Request(u, headers={"User-Agent": "Mozilla/5.0"}), timeout=12).read())
        q = q["FormattedQuoteResult"]["FormattedQuote"][0]
        v = float(str(q.get("last", "")).replace(",", ""))
        d = str(q.get("last_time", ""))[:10]
        if v > 0 and d == now.date().isoformat():
            vkospi = v
    except Exception as e:
        print("[kis_close] VKOSPI(CNBC) skip:", repr(e)[:60])
    oc = kis_api.option_chain(spot=fo["price"], krx_base=None, max_calls=240, time_budget=150)
    if not oc:
        print("[kis_close] 옵션 체인 실패 — skip")
        return 0

    date = oc.get("asof") or now.date().isoformat()
    rec = {
        "date": date,
        "captured_at": now.isoformat(timespec="seconds"),
        "spot": oc.get("spot"),
        "expiry": oc.get("expiry"),
        "oi": fo.get("oi"),
        "pcr_vol": oc.get("pcr_vol"),
        "iv_skew": oc.get("iv_skew"),
        "iv_call_25d": oc.get("iv_call_25d"),
        "iv_put_25d": oc.get("iv_put_25d"),
        "gex": oc.get("gex"),
        "vkospi": vkospi,
        "call_vol": oc.get("call_vol"),
        "put_vol": oc.get("put_vol"),
        "scanned": oc.get("scanned"),
        "note": "server close capture (±25% 창 스캔 — PCR(OI) 미산출, 아침 PC 실행이 전체체인으로 채움)",
    }
    print("[kis_close]", json.dumps(rec, ensure_ascii=False))
    if dry:
        print("[kis_close] --dry — 기록 생략")
        return 0

    with open(OUT, "w") as f:
        json.dump(rec, f, ensure_ascii=False, indent=1)
    con = sqlite3.connect(DB, timeout=20)
    con.execute(
        """INSERT INTO kr_derivatives_daily(id,date,pcr_vol,iv_skew_25d,gex,oi,vkospi)
           VALUES(?,?,?,?,?,?,?)
           ON CONFLICT(id,date) DO UPDATE SET
             pcr_vol     = COALESCE(excluded.pcr_vol,     kr_derivatives_daily.pcr_vol),
             iv_skew_25d = COALESCE(excluded.iv_skew_25d, kr_derivatives_daily.iv_skew_25d),
             gex         = COALESCE(excluded.gex,         kr_derivatives_daily.gex),
             oi          = COALESCE(excluded.oi,          kr_derivatives_daily.oi),
             vkospi      = COALESCE(excluded.vkospi,      kr_derivatives_daily.vkospi)""",
        (KID, date, rec["pcr_vol"], rec["iv_skew"], rec["gex"], rec["oi"], rec["vkospi"]),
    )
    con.commit()
    con.close()
    print(f"[kis_close] ✅ {date} 기록 — PCR(Vol) {rec['pcr_vol']} · IV스큐 {rec['iv_skew']} · GEX {rec['gex']} → DB + kis_close.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
