#!/usr/bin/env python3
"""stock_px.py — 종목 일별 종가 패널 (2026-09-05 신설)

왜 별도인가
-----------
stock_panel.py 가 쌓는 팩터 스냅샷은 **오늘부터**만 존재한다(컨센·리비전은 소급 불가).
반면 **가격 파생 팩터**(모멘텀·RSI·이평·변동성)와 **정답지인 forward return** 은
과거 종가만 있으면 전부 소급 계산된다. 즉 이 테이블 하나로 횡단면 백테스트를
'오늘 당장' 시작할 수 있고, 6개월 뒤 팩터 패널이 쌓이면 거기에 합류시키면 된다.

수집 방식 — Yahoo spark 배치
---------------------------
종목당 1회 호출(chart API)이 아니라 **spark 엔드포인트에 20심볼씩 묶어** 던진다.
실측(2026-09-05): 20심볼 5y = 0.4초 → 4,302종목 전량이 216콜 ≈ 수십 초(스레드 6).
종가만 오지만 백테스트엔 종가면 충분하다(OHLC 는 필요해지면 그때 확장).
⚠️ crumb/cookie 가 붙은 opener 가 없으면 400 이 뜬다 — ta_screen.yahoo_opener() 재사용.

유니버스 (유동성 하한)
--------------------
KR 시총 1,000억↑(1,292종목) · US $500M↑(3,010종목) = 4,302.
전 종목을 넣지 않는 이유: 초소형주는 호가 스프레드·거래 불가로 **백테스트에서만
존재하는 가짜 알파**를 만든다. 하한을 두는 게 결과를 보수적으로 만든다.
⚠️ cap 단위는 원(KR)·달러(US) 원본값이다(억원 아님 — 삼성전자 1.49e15).

사용:
  python3 scripts/stock_px.py --full     5년치 최초 백필(수십 초~수 분)
  python3 scripts/stock_px.py            일일 증분(range=1mo, 결측 자동 메움)
  python3 scripts/stock_px.py --stat     적재 현황
"""
import json
import sqlite3
import sys
import time
import urllib.parse as _up
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE / "scripts"))
import ta_screen as T  # noqa: E402  (yahoo_opener·jget 재사용)

POOL = BASE / "data" / "db" / "screener_pool.json"
DB = BASE / "data" / "db" / "stock_panel.sqlite"

CAP_KR = 1e11   # 1,000억원
CAP_US = 5e8    # $500M
CHUNK = 20      # spark 심볼/콜 (screener_pool 실측 안정값)
WORKERS = 6

SCHEMA = """
CREATE TABLE IF NOT EXISTS px(
  mk TEXT NOT NULL, c TEXT NOT NULL, d TEXT NOT NULL, close REAL,
  PRIMARY KEY(mk, c, d)
) WITHOUT ROWID;
CREATE INDEX IF NOT EXISTS ix_px_d ON px(d);
"""


def universe():
    """(야후심볼, mk, code) 리스트 — 유동성 하한 적용."""
    d = json.loads(POOL.read_text(encoding="utf-8"))
    out = []
    for r in d.get("kr") or []:
        if (r.get("cap") or 0) < CAP_KR:
            continue
        c = r.get("c")
        if not c:
            continue
        sfx = ".KQ" if (r.get("mkt") or "").upper().startswith("KOSDAQ") else ".KS"
        out.append((f"{c}{sfx}", "kr", c))
    for r in d.get("us") or []:
        if (r.get("cap") or 0) < CAP_US:
            continue
        c = r.get("c") or r.get("sym")
        if c:
            out.append((c, "us", c))
    return out


def main():
    full = "--full" in sys.argv
    rng = "5y" if full else "1mo"
    uni = universe()
    n_kr = sum(1 for _, mk, _ in uni if mk == "kr")
    print(f"[px] 유니버스 {len(uni)}종목 (KR {n_kr} · US {len(uni)-n_kr}) · range={rng}", flush=True)

    op, _ = T.yahoo_opener()
    bysym = {s: (mk, c) for s, mk, c in uni}
    syms = list(bysym)
    chunks = [syms[i:i + CHUNK] for i in range(0, len(syms), CHUNK)]

    def one(ch):
        u = ("https://query1.finance.yahoo.com/v7/finance/spark?symbols=%s&range=%s&interval=1d"
             % (_up.quote(",".join(ch)), rng))
        try:
            j = T.jget(u, opener=op, timeout=25)
        except Exception:
            return []
        rows = []
        for r0 in (j.get("spark", {}) or {}).get("result") or []:
            sym = r0.get("symbol")
            mkc = bysym.get(sym)
            if not mkc:
                continue
            resp = (r0.get("response") or [{}])[0]
            ts = resp.get("timestamp") or []
            cl = ((resp.get("indicators", {}) or {}).get("quote") or [{}])[0].get("close") or []
            for t, v in zip(ts, cl):
                if v is None:
                    continue
                d8 = datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%d")
                rows.append((mkc[0], mkc[1], d8, float(v)))
        return rows

    DB.parent.mkdir(parents=True, exist_ok=True)
    cx = sqlite3.connect(DB, timeout=180)
    cx.execute("PRAGMA journal_mode=WAL")
    cx.executescript(SCHEMA)

    t0, done, total = time.time(), 0, 0
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        for rows in ex.map(one, chunks):
            if rows:
                cx.executemany("INSERT OR REPLACE INTO px VALUES(?,?,?,?)", rows)
                total += len(rows)
            done += 1
            if done % 40 == 0:
                cx.commit()
                print(f"    [{done}/{len(chunks)}] {total}행 · {time.time()-t0:.0f}초", flush=True)
    cx.commit()

    nsym, nrow = cx.execute("SELECT COUNT(DISTINCT mk||c), COUNT(*) FROM px").fetchone()
    rngd = cx.execute("SELECT MIN(d), MAX(d) FROM px").fetchone()
    cx.close()
    print(f"[px] 완료 {total}행 적재 · 누적 {nsym}종목 {nrow}행 ({rngd[0]}~{rngd[1]}) "
          f"· {DB.stat().st_size/1024/1024:.0f}MB · {time.time()-t0:.0f}초", flush=True)


def stat():
    cx = sqlite3.connect(DB)
    try:
        nsym, nrow = cx.execute("SELECT COUNT(DISTINCT mk||c), COUNT(*) FROM px").fetchone()
        rngd = cx.execute("SELECT MIN(d), MAX(d) FROM px").fetchone()
        print(f"px: {nsym}종목 · {nrow}행 · {rngd[0]}~{rngd[1]}")
        for row in cx.execute("SELECT mk, COUNT(DISTINCT c), COUNT(*) FROM px GROUP BY mk"):
            print("  ", row)
    except Exception as e:
        print("px 없음:", e)
    cx.close()


if __name__ == "__main__":
    stat() if "--stat" in sys.argv else main()
