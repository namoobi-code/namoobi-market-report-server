#!/usr/bin/env python3
"""암호화폐 서버 수집 — 보고서 실행 때 조사하던 것을 서버가 미리 DB화한다.

수집 항목 (req9·10·11·19)
  ① 김치 프리미엄 시계열 (BTC·ETH·XRP·SOL)
       업비트 KRW 시세 ÷ (바이낸스 USDT 시세 × USD/KRW 환율) − 1
       kimpwatda 와 같은 산식. 10분 간격 누적, 90일 보관 → 차트는 30D 표시.
  ② 공포·탐욕 지수 이력 (alternative.me 공개 API, 1년)
  ③ 시장 개요 (총시총·거래량·BTC 도미넌스 — CoinGecko global)
  ④ 24h Top Gainers/Losers (CoinGecko markets, 시총 상위 250 중)

사용법
  python3 scripts/crypto_intel.py            # 정기 수집 (cron */10분)
  python3 scripts/crypto_intel.py --backfill # 김프 1년 일봉 백필 (1회)
"""
import json, sys, time, os
import urllib.request, urllib.parse
from datetime import datetime, timedelta
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DB   = BASE / "data" / "db"
SYMS = ["BTC", "ETH", "XRP", "SOL"]
UA   = {"User-Agent": "Mozilla/5.0"}

def jget(url, timeout=15, headers=None):
    req = urllib.request.Request(url, headers=headers or UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())

def load(name):
    p = DB / f"{name}.json"
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}

def save(name, obj):
    obj["as_of"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    obj["marker"] = datetime.now().strftime("%Y-%m-%d")
    p = DB / f"{name}.json"
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")
    tmp.replace(p)

def usdkrw():
    """네이버 환율 (당일 실시간). 실패 시 er-api 폴백."""
    try:
        d = jget("https://m.stock.naver.com/front-api/marketIndex/prices"
                 "?category=exchange&reutersCode=FX_USDKRW&page=1&pageSize=1")
        v = float(str(d["result"][0]["closePrice"]).replace(",", ""))
        if 900 < v < 3000:
            return v
    except Exception:
        pass
    d = jget("https://open.er-api.com/v6/latest/USD")
    return float(d["rates"]["KRW"])

# ── ① 김치 프리미엄 ────────────────────────────────────────
def collect_kimp():
    mk = ",".join(f"KRW-{s}" for s in SYMS)
    up = {r["market"].split("-")[1]: r["trade_price"]
          for r in jget(f"https://api.upbit.com/v1/ticker?markets={mk}")}
    # binance 는 symbols JSON 에 공백이 있으면 400 을 낸다
    syms_q = urllib.parse.quote(json.dumps([f"{s}USDT" for s in SYMS], separators=(",", ":")))
    bn = {r["symbol"][:-4]: float(r["price"])
          for r in jget(f"https://api.binance.com/api/v3/ticker/price?symbols={syms_q}")}
    fx = usdkrw()
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")

    d = load("kimp_series")
    st = d.get("s") or {}
    cutoff = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")
    cur = {}
    for s in SYMS:
        if s not in up or s not in bn:
            continue
        pct = round((up[s] / (bn[s] * fx) - 1) * 100, 3)
        cur[s] = {"pct": pct, "krw": up[s], "usd": bn[s]}
        arr = [x for x in (st.get(s) or []) if x[0] >= cutoff]
        arr.append([ts, pct])
        st[s] = arr
    save("kimp_series", {"s": st, "fx": fx, "now": cur,
                         "desc": "업비트KRW ÷ (바이낸스USDT × USD/KRW) − 1 · 10분 간격 · 90일 보관"})
    line = ", ".join("%s %+.2f%%" % (s, cur[s]["pct"]) for s in cur)
    print(f"kimp: {line} · fx {fx:,.1f}")

def backfill_kimp():
    """일봉 1년 백필 — 이후 10분 수집이 그 위에 쌓인다."""
    # 환율 일별 이력 (네이버, 페이지당 10개)
    fxh = {}
    for pg in range(1, 40):
        try:
            d = jget("https://m.stock.naver.com/front-api/marketIndex/prices"
                     f"?category=exchange&reutersCode=FX_USDKRW&page={pg}&pageSize=10")
            rows = d.get("result") or []
        except Exception:
            break
        if not rows:
            break
        for r in rows:
            dt = str(r.get("localTradedAt", ""))[:10]
            try:
                fxh[dt] = float(str(r["closePrice"]).replace(",", ""))
            except Exception:
                pass
        if len(fxh) >= 370:
            break
        time.sleep(0.15)
    print(f"환율 이력 {len(fxh)}일")

    def fx_at(dt):
        for back in range(7):                      # 주말·휴일은 직전 영업일 환율
            k = (datetime.strptime(dt, "%Y-%m-%d") - timedelta(days=back)).strftime("%Y-%m-%d")
            if k in fxh:
                return fxh[k]
        return None

    st = {}
    for s in SYMS:
        upd = {}
        to = ""
        for _ in range(2):                          # 업비트 일봉 200개 × 2 = 400일
            u = (f"https://api.upbit.com/v1/candles/days?market=KRW-{s}&count=200"
                 + (f"&to={urllib.parse.quote(to)}" if to else ""))
            rows = jget(u)
            if not rows:
                break
            for r in rows:
                upd[r["candle_date_time_kst"][:10]] = r["trade_price"]
            to = rows[-1]["candle_date_time_utc"] + "Z"
            time.sleep(0.25)
        bnd = {}
        kl = jget(f"https://api.binance.com/api/v3/klines?symbol={s}USDT&interval=1d&limit=400")
        for k in kl:
            dt = datetime.utcfromtimestamp(k[0] / 1000).strftime("%Y-%m-%d")
            bnd[dt] = float(k[4])                   # 종가
        arr = []
        for dt in sorted(set(upd) & set(bnd)):
            fx = fx_at(dt)
            if not fx:
                continue
            arr.append([dt + " 09:00", round((upd[dt] / (bnd[dt] * fx) - 1) * 100, 3)])
        st[s] = arr[-370:]
        print(f"  {s}: {len(st[s])}일 백필 ({st[s][0][0][:10]} ~ {st[s][-1][0][:10]})")

    d = load("kimp_series")
    old = d.get("s") or {}
    for s in SYMS:                                  # 백필 뒤에 기존 10분 수집분을 잇는다
        cut = st[s][-1][0][:10] if st.get(s) else ""
        tail = [x for x in (old.get(s) or []) if x[0][:10] > cut]
        st[s] = (st.get(s) or []) + tail
    save("kimp_series", {"s": st, "fx": d.get("fx"), "now": d.get("now") or {},
                         "desc": "일봉 1년 백필 + 10분 간격 누적"})

# ── ② 공포·탐욕 이력 ──────────────────────────────────────
def collect_fng():
    d = jget("https://api.alternative.me/fng/?limit=365")
    rows = [{"date": datetime.utcfromtimestamp(int(r["timestamp"])).strftime("%Y-%m-%d"),
             "v": int(r["value"]), "label": r["value_classification"]}
            for r in d.get("data") or []]
    rows.sort(key=lambda r: r["date"])
    if rows:
        save("crypto_fng", {"hist": rows, "now": rows[-1]})
        print(f"fng: {rows[-1]['v']} ({rows[-1]['label']}) · {len(rows)}일")

# ── ③ 시장 개요 ───────────────────────────────────────────
def collect_overview():
    g = jget("https://api.coingecko.com/api/v3/global").get("data") or {}
    save("crypto_overview", {
        "mcap_usd": g.get("total_market_cap", {}).get("usd"),
        "vol24_usd": g.get("total_volume", {}).get("usd"),
        "mcap_chg24": g.get("market_cap_change_percentage_24h_usd"),
        "btc_dom": g.get("market_cap_percentage", {}).get("btc"),
        "eth_dom": g.get("market_cap_percentage", {}).get("eth"),
        "coins": g.get("active_cryptocurrencies"),
    })
    print(f"overview: mcap {g.get('total_market_cap', {}).get('usd', 0)/1e12:.2f}T "
          f"· BTC {g.get('market_cap_percentage', {}).get('btc', 0):.1f}%")

# ── ④ Top Gainers / Losers ────────────────────────────────
def collect_movers():
    rows = jget("https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd"
                "&order=market_cap_desc&per_page=250&page=1&price_change_percentage=24h")
    ok = [r for r in rows
          if r.get("price_change_percentage_24h") is not None
          and r.get("current_price") and (r.get("total_volume") or 0) > 1e6]
    ok.sort(key=lambda r: r["price_change_percentage_24h"], reverse=True)
    def pack(r):
        return {"sym": (r.get("symbol") or "").upper(), "name": r.get("name"),
                "price": r.get("current_price"),
                "chg24": round(r["price_change_percentage_24h"], 2),
                "vol": r.get("total_volume"), "mcap": r.get("market_cap"),
                "rank": r.get("market_cap_rank")}
    save("crypto_movers", {"gainers": [pack(r) for r in ok[:10]],
                           "losers":  [pack(r) for r in ok[-10:][::-1]],
                           "universe": "CoinGecko 시총 상위 250 · 거래량 $1M+"})
    print(f"movers: top {ok[0]['symbol'].upper()} {ok[0]['price_change_percentage_24h']:+.1f}% "
          f"· bottom {ok[-1]['symbol'].upper()} {ok[-1]['price_change_percentage_24h']:+.1f}%")

def main():
    if "--backfill" in sys.argv:
        backfill_kimp()
        return
    jobs = [("kimp", collect_kimp)]
    # 무거운 것들은 매시 정각 무렵에만 (cron 10분 간격 가정)
    if datetime.now().minute < 10 or "--all" in sys.argv:
        jobs += [("fng", collect_fng), ("overview", collect_overview),
                 ("movers", collect_movers)]
    for name, fn in jobs:
        try:
            fn()
        except Exception as e:
            print(f"{name} 실패: {type(e).__name__} {e}")

if __name__ == "__main__":
    main()
