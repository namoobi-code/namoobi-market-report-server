#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""night_ws.py — KOSPI200 야간선물 실시간(웹소켓) 수집 데몬. (2026-07-20 신설)

정규장 REST(inquire-price)는 15:45 종가로 고정돼 야간(18:00~06:00) 체결가를 못 준다.
KIS 실시간 웹소켓(H0IFCNT0 선물체결 · H0IFASP0 선물호가)은 야간 세션도 push 하므로
그걸 받아 data/night_fut.json 에 최신가를 기록한다. deriv_intraday 가 야간엔 이 파일로
'야간 선물가 → 베이시스(야간선물 ÷ 직전 현물종가)'를 계산한다.

  · 체결(H0IFCNT0) 오면 실거래가(futs_prpr) 사용.
  · 체결이 얇을 때를 대비해 호가(H0IFASP0)도 구독 → 최우선 매수·매도 중간값(mid) 보조.
  · PINGPONG 하트비트 응답, 끊기면 5초 후 재접속, 야간 아닌 시간이면 정상 종료.
  · 비밀번호·주문 없음(시세 구독만). 승인키는 REST 앱키/시크릿으로 발급.
"""
import os
import sys
import io
import json
import time
import zipfile
import urllib.request
import asyncio
import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kis_api                      # noqa: E402
import websockets                   # noqa: E402

BASE = os.path.expanduser("~/namoobi")
OUT = os.path.join(BASE, "data", "night_fut.json")
DBG = os.path.join(BASE, "data", "night_ws_debug.txt")
KST = datetime.timezone(datetime.timedelta(hours=9))
WS_URL = "ws://ops.koreainvestment.com:21000"


def _near_code():
    """근월물 선물 tr_key(마스터코드) + 만기(YYYYMM)."""
    with urllib.request.urlopen(kis_api.MASTER, timeout=40) as f:
        z = zipfile.ZipFile(io.BytesIO(f.read()))
    raw = z.read(z.namelist()[0]).decode("cp949", "ignore").splitlines()
    fut = sorted([p for l in raw for p in [l.split("|")]
                  if len(p) >= 9 and p[8] == "KOSPI200" and p[0] == "1" and p[3].startswith("F 2")],
                 key=lambda p: p[3])
    return (fut[0][1], fut[0][3][2:]) if fut else (None, None)


def _approval():
    c = kis_api._creds()
    body = {"grant_type": "client_credentials", "appkey": c["appkey"], "secretkey": c["appsecret"]}
    r = urllib.request.Request(c["host"] + "/oauth2/Approval", data=json.dumps(body).encode(),
                               headers={"content-type": "application/json"})
    return json.loads(urllib.request.urlopen(r, timeout=15).read())["approval_key"]


def _night(now):
    """KRX 야간선물 세션(18:00~다음날 06:05). 월~금 저녁~새벽 + 토 새벽(금 야간)."""
    hm = now.hour * 60 + now.minute
    wd = now.weekday()
    if wd == 5:                     # 토: 금 야간의 새벽 연장만
        return hm <= 6 * 60 + 5
    if wd == 6:                     # 일: 없음
        return False
    return hm >= 18 * 60 or hm <= 6 * 60 + 5


def _write(code, ym, px, chg=None, mkt_time=None):
    """야간 최신가 기록. chg=전일(주간종가) 대비 등락률(%), mkt_time=거래소 영업시간 HHMMSS."""
    tmp = OUT + ".tmp"
    json.dump({"code": code, "expiry": ym, "px": round(px, 2),
               "chg_pct": chg, "mkt_time": mkt_time, "tr": "H0MFCNT0",
               "ts": datetime.datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")},
              open(tmp, "w"))
    os.replace(tmp, OUT)


def _sub(ak, tr_id, key):
    return json.dumps({"header": {"approval_key": ak, "custtype": "P", "tr_type": "1",
                                  "content-type": "utf-8"},
                       "body": {"input": {"tr_id": tr_id, "tr_key": key}}})


async def _stream(code, ym, ak):
    async with websockets.connect(WS_URL, ping_interval=None, max_size=None) as ws:
        # (2026-07-20 실측) 주간용 H0IFCNT0/H0IFASP0 은 구독은 되나 야간엔 데이터를 안 보낸다.
        #   야간세션 체결은 H0MFCNT0 로만 흐른다 → 야간 전용 TR 사용.
        await ws.send(_sub(ak, "H0MFCNT0", code))       # 야간 선물 체결
        dbg_done = set()
        while True:
            if not _night(datetime.datetime.now(KST)):
                print("[night_ws] 야간 종료 — 정상 종료"); return "done"
            m = await asyncio.wait_for(ws.recv(), timeout=40)
            if not m:
                continue
            if m[0] == "{":                              # 제어 프레임(구독확인/PINGPONG)
                if "PINGPONG" in m:
                    await ws.send(m)
                continue
            parts = m.split("|")
            if len(parts) < 4:
                continue
            tr = parts[1]
            pay = parts[3].split("^")
            if tr not in dbg_done:                        # 최초 1회 필드 덤프(검증용)
                try:
                    with open(DBG, "a") as f:
                        f.write(tr + " → " + " ".join(f"{i}:{v}" for i, v in enumerate(pay[:24])) + "\n")
                except Exception:
                    pass
                dbg_done.add(tr)
            try:
                # H0MFCNT0 payload(실측): [0]종목 [1]영업시간 [2]전일대비 [3]부호 [4]등락률
                #                          [5]현재가 [6]시가 [7]고가 [8]저가 ...
                if tr == "H0MFCNT0":
                    px = float(pay[5])
                    if 500 < px < 2000:
                        _write(code, ym, px, float(pay[4]), pay[1])
            except Exception:
                continue


def main():
    code, ym = _near_code()
    if not code:
        print("[night_ws] 근월물 없음 — 종료"); return
    print(f"[night_ws] start tr_key={code} 만기={ym}")
    while _night(datetime.datetime.now(KST)):
        try:
            ak = _approval()
            r = asyncio.run(_stream(code, ym, ak))
            if r == "done":
                break
        except Exception as e:
            print(f"[night_ws] {datetime.datetime.now(KST):%H:%M} 재접속: {repr(e)[:90]}")
            time.sleep(5)
    print("[night_ws] 종료")


if __name__ == "__main__":
    main()
