#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""deriv_intraday.py — 3.1.13 파생 패널 장중/시간외 경량 갱신 (서버 cron, 2026-07-20 신설).

  --light (기본): 네이버 m.stock T+0(KR 현물·선물·베이시스, 라이브) + VKOSPI(CNBC T+0)
                  + US 지수(Yahoo, ingest_prices) → run_analysis(z 재계산) → publish
                  → export_snapshot.  (KIS 무겁지 않은 3~4콜)
  --heavy       : + KIS 옵션체인 캡처(scripts/kis_close_capture.py --force: PCR/IV스큐/GEX/OI)
                  후 동일 재계산·재출력.  (수백 콜 → 장중 1시간·마감에만)

세션 게이트(KST): KR 파생 08:20~다음날 06:10(정규 09~15:45 + 시간외 16~18 + 야간 18~06)
  또는 US 22:20~05:10.  게이트 밖이면 skip.  --force 로 무시.
값이 소스에서 안 바뀌면 그냥 재출력 → 스냅샷 built_at(파일시각)만 갱신,
per-축 날짜(asof)는 실제 데이터 날짜 그대로라 지연분은 표에서 즉시 식별된다.

정본 원칙: 네이버 T+0 는 '당일(=KRX 최신일 이후)' 만 덮어쓰고, 다음날 아침 daily_update
파이프라인이 KRX 공식 정산치로 재적재하므로 하루짜리 라이브 브리지로만 작동한다.
"""
import os
import sys
import json
import subprocess
import datetime
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(HERE)                       # ~/namoobi
sys.path.insert(0, HERE)
os.environ.setdefault("DERIV_DB", os.path.join(BASE, "data", "deriv_signals.db"))

KST = datetime.timezone(datetime.timedelta(hours=9))
KID = "KOSPI200"
SNAP = os.path.join(BASE, "data", "deriv_snapshot.json")
UA = {"User-Agent": "Mozilla/5.0"}


def _kr_live(now):
    """KRX 파생 거래창(정규+시간외+야간). 야간세션은 18:00~익일 06:00 → 새벽까지 열림."""
    wd = now.weekday()                 # 0=월 … 5=토 6=일
    hm = now.hour * 60 + now.minute
    day = 8 * 60 + 20 <= hm <= 18 * 60 + 5          # 08:20~18:05 (정규+장전+시간외)
    night_eve = hm >= 18 * 60                        # 18:00~24:00 (야간 전반)
    night_dawn = hm <= 6 * 60 + 10                   # 00:00~06:10 (야간 후반)
    if wd <= 3:                        # 월~목: 주간 + 야간(저녁~다음날 새벽)
        return day or night_eve or night_dawn
    if wd == 4:                        # 금: 주간 + 금 저녁 야간
        return day or night_eve
    if wd == 5:                        # 토: 금 야간의 새벽 연장만
        return night_dawn
    return False                       # 일: 없음


def _us_live(now):
    hm = now.hour * 60 + now.minute
    return hm >= 22 * 60 + 20 or hm <= 5 * 60 + 10


def _naver_series(code, size=10):
    url = "https://m.stock.naver.com/api/index/%s/price?pageSize=%d&page=1" % (code, size)
    try:
        rows = json.loads(urllib.request.urlopen(
            urllib.request.Request(url, headers=UA), timeout=15).read().decode("utf-8", "ignore"))
    except Exception as e:
        print("[deriv-live] naver %s 실패: %s" % (code, repr(e)[:60]))
        return {}
    out = {}
    for r in (rows or []):
        try:
            out[str(r["localTradedAt"])[:10]] = float(str(r["closePrice"]).replace(",", ""))
        except Exception:
            pass
    return out


def _vkospi_cnbc():
    try:
        u = ("https://quote.cnbc.com/quote-html-webservice/restQuote/symbolType/symbol"
             "?symbols=.KSVKOSPI&requestMethod=itv&noform=1&partnerId=2&fund=1&exthrs=1&output=json")
        q = json.loads(urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=12).read())
        q = q["FormattedQuoteResult"]["FormattedQuote"][0]
        v = float(str(q.get("last", "")).replace(",", ""))
        return v if v > 0 else None
    except Exception:
        return None


def light(con, now, us_on=True):
    """KR 현물·선물·베이시스(네이버 T+0) + VKOSPI(CNBC) + US 지수(Yahoo) 를 당일행에 force-upsert."""
    n = 0
    fut, idx = _naver_series("FUT"), _naver_series("KPI200")
    common = sorted(set(fut) & set(idx))
    if common:
        d = common[-1]                 # 최신 거래일(장중이면 오늘)
        if idx[d] and idx[d] > 0:
            basis = round((fut[d] / idx[d] - 1.0) * 1e4, 1)
            con.execute("INSERT OR REPLACE INTO prices_daily(id,date,spot_close,future_close,vix_close) "
                        "VALUES(?,?,?,?,NULL)", (KID, d, idx[d], fut[d]))
            con.execute("INSERT INTO kr_derivatives_daily(id,date,basis_bp) VALUES(?,?,?) "
                        "ON CONFLICT(id,date) DO UPDATE SET basis_bp=excluded.basis_bp", (KID, d, basis))
            con.commit()
            n += 1
            vk = _vkospi_cnbc()
            if vk:
                con.execute("INSERT INTO kr_derivatives_daily(id,date,vkospi) VALUES(?,?,?) "
                            "ON CONFLICT(id,date) DO UPDATE SET vkospi=excluded.vkospi", (KID, d, vk))
                con.commit()
            print("[deriv-live] KR T+0 %s 현물 %.2f · 선물 %.2f · 베이시스 %+.1fbp%s"
                  % (d, idx[d], fut[d], basis, (" · VKOSPI %.2f" % vk) if vk else ""))
    # US 지수(Yahoo) — 미국장 세션일 때만(그 외엔 최근 종가 유지, 헛호출·로그노이즈 방지)
    if us_on:
        try:
            from ingest import ingest_prices
            today = now.date().isoformat()
            ingest_prices(con, today, today)
        except Exception as e:
            print("[deriv-live] US prices skip:", repr(e)[:70])
    return n


def osample(con, now):
    """장중 5분 — 좁은창(ATM±8%) KIS 옵션 샘플 스캔으로 IV스큐·GEX만 T+0 갱신.
       PCR 은 좁은창에서 외가격 꼬리를 빼먹어 편향되므로 갱신하지 않는다(장중 1H 전체스캔이 담당).
       IV스큐(25델타)·GEX(ATM 집중)는 좁은창으로도 정확 → 5분 라이브에 적합."""
    try:
        import kis_api
        oc = kis_api.option_chain(window=0.08, max_calls=80, time_budget=45)
    except Exception as e:
        print("[deriv-live] osample 실패:", repr(e)[:70]); return
    if not oc:
        print("[deriv-live] osample: 옵션 응답 없음(장 종료?)"); return
    d = oc.get("asof") or now.date().isoformat()
    sk, gx = oc.get("iv_skew"), oc.get("gex")
    if sk is not None:
        con.execute("INSERT INTO kr_derivatives_daily(id,date,iv_skew_25d) VALUES(?,?,?) "
                    "ON CONFLICT(id,date) DO UPDATE SET iv_skew_25d=excluded.iv_skew_25d", (KID, d, sk))
    if gx is not None:
        con.execute("INSERT INTO kr_derivatives_daily(id,date,gex) VALUES(?,?,?) "
                    "ON CONFLICT(id,date) DO UPDATE SET gex=excluded.gex", (KID, d, gx))
    con.commit()
    print(f"[deriv-live] osample {d} · IV스큐 {sk} · GEX {gx} (ATM±8% 샘플, {oc.get('scanned')}행사가)")


def heavy(now):
    """KIS 옵션체인(PCR/IV스큐/GEX/OI) 캡처 — kis_close_capture 재사용(시간가드 --force)."""
    cap = os.path.join(BASE, "scripts", "kis_close_capture.py")
    if not os.path.exists(cap):
        print("[deriv-live] kis_close_capture.py 없음 — heavy skip")
        return
    try:
        subprocess.run([sys.executable, cap, "--force"], cwd=os.path.join(BASE, "scripts"),
                       timeout=220)
    except Exception as e:
        print("[deriv-live] heavy(KIS) skip:", repr(e)[:80])


def main():
    force = "--force" in sys.argv
    mode_heavy = "--heavy" in sys.argv
    mode_osample = "--osample" in sys.argv
    now = datetime.datetime.now(KST)
    if not force and not (_kr_live(now) or _us_live(now)):
        print("[deriv-live] %s 장외 — skip" % now.strftime("%m-%d %H:%M"))
        return

    if mode_heavy:
        heavy(now)                     # 자체 커넥션으로 DB 기록(전체 스캔)

    import db
    from analyze import run_analysis
    con = db.connect()
    if mode_osample and not mode_heavy:
        osample(con, now)              # 좁은창 샘플 → IV스큐·GEX 만
    light(con, now, us_on=(force or _us_live(now)))
    run_analysis(con)
    con.close()
    db.publish_db()

    try:
        subprocess.run([sys.executable, os.path.join(HERE, "export_snapshot.py"), SNAP],
                       cwd=HERE, env={**os.environ}, timeout=60)
    except Exception as e:
        print("[deriv-live] export skip:", repr(e)[:80])
    _mode = "heavy" if mode_heavy else ("osample" if mode_osample else "light")
    print("[deriv-live] ✓ %s (%s)" % (now.strftime("%m-%d %H:%M"), _mode))


if __name__ == "__main__":
    main()
