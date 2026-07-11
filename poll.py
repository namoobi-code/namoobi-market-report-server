#!/usr/bin/env python3
"""1일 2회 실행 — 김치프리미엄·공포탐욕지수를 SQLite에 누적.
표준 라이브러리만 사용. 외부 호출 최소화(하루 2회)."""
import json, sqlite3, urllib.request, ssl
from datetime import datetime, timezone
from pathlib import Path

DB = Path(__file__).parent / "data" / "poll.db"
UA = {"User-Agent": "Mozilla/5.0 (namoobi-dashboard)"}
CTX = ssl.create_default_context()
COINS = {"BTC": "KRW-BTC", "ETH": "KRW-ETH", "XRP": "KRW-XRP", "SOL": "KRW-SOL"}
BINANCE = {"BTC": "BTCUSDT", "ETH": "ETHUSDT", "XRP": "XRPUSDT", "SOL": "SOLUSDT"}

def get(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=15, context=CTX) as r:
        return json.loads(r.read().decode())

def init():
    DB.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB)
    c.execute("""CREATE TABLE IF NOT EXISTS ticks(
        ts TEXT NOT NULL, metric TEXT NOT NULL, symbol TEXT,
        value REAL, unit TEXT, UNIQUE(ts, metric, symbol))""")
    c.execute("CREATE INDEX IF NOT EXISTS ix ON ticks(metric, symbol, ts)")
    c.commit()
    return c

def main():
    c = init()
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    rows = []

    # 1) 환율 (USD/KRW)
    fx = None
    try:
        d = get("https://query1.finance.yahoo.com/v8/finance/chart/KRW=X?interval=1d&range=1d")
        fx = d["chart"]["result"][0]["meta"]["regularMarketPrice"]
        rows.append((ts, "usdkrw", None, float(fx), "KRW"))
    except Exception as e:
        print("환율 실패:", e)

    # 2) 김치프리미엄 (업비트 KRW vs 바이낸스 USD × 환율)
    if fx:
        try:
            up = {x["market"]: x["trade_price"] for x in
                  get("https://api.upbit.com/v1/ticker?markets=" + ",".join(COINS.values()))}
            for sym, mkt in COINS.items():
                try:
                    b = get(f"https://api.binance.com/api/v3/ticker/price?symbol={BINANCE[sym]}")
                    krw, usd = float(up[mkt]), float(b["price"])
                    prem = (krw / (usd * fx) - 1) * 100
                    rows.append((ts, "kimchi_premium", sym, round(prem, 4), "%"))
                    rows.append((ts, "upbit_krw", sym, krw, "KRW"))
                except Exception as e:
                    print(f"김프 {sym} 실패:", e)
        except Exception as e:
            print("업비트 실패:", e)

    # 3) 공포탐욕지수 (하루 1회만 갱신되는 지표)
    try:
        d = get("https://api.alternative.me/fng/?limit=1")
        v = d["data"][0]
        rows.append((ts, "fear_greed", None, float(v["value"]), v["value_classification"]))
    except Exception as e:
        print("공포탐욕 실패:", e)

    c.executemany("INSERT OR IGNORE INTO ticks(ts,metric,symbol,value,unit) VALUES(?,?,?,?,?)", rows)
    c.commit()
    n = c.execute("SELECT COUNT(*) FROM ticks").fetchone()[0]
    c.close()
    print(f"[{ts}] {len(rows)}건 적재 · 누적 {n}건")

if __name__ == "__main__":
    main()
