#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""us_options_capture.py — 미국장 마감 직후(cron 06:40 KST 화~토) SPX·NDX 옵션 스냅샷. (2026-07-17 신설)

배경: yfinance 옵션체인(PCR·IV·GEX)은 **백필 불가**(포인트인타임) — PC 리포트를 안 돌린 날은
options_daily 에 구멍이 나 60거래일 z-score 누적이 늦어진다. 서버가 미국장 마감 직후 매일
떠 두면 공백이 사라진다. (06:40 KST = EDT 마감 +1h40m / EST 마감 +40m — 연중 커버)

- PC 파이프라인(deriv_signals/ingest_krx.py ingest_server_close)이 us_options_close.json 을
  내려받아 로컬 DB에 INSERT OR IGNORE 병합한다(PC 자체 실측이 있으면 그대로 둠).
- 의존: ~/namoobi/deriv_signals/{ingest,config,db}.py + venv(numpy·pandas·yfinance)
- cron: 40 6 * * 2-6  (화~토 = 미국 거래일 다음날 아침 KST)
"""
import os, sys, json, sqlite3

sys.path.insert(0, os.path.expanduser("~/namoobi/deriv_signals"))
from ingest import ingest_options  # noqa: E402

BASE = os.path.expanduser("~/namoobi")
DB = os.path.join(BASE, "data", "deriv_signals.db")
OUT = os.path.join(BASE, "data", "us_options_close.json")


def main():
    con = sqlite3.connect(DB, timeout=30)
    n = ingest_options(con)
    rows = [
        dict(zip(("id", "date", "expiry_used", "dte", "pcr_oi", "pcr_vol", "iv_atm",
                  "iv_skew_25d", "delta_imbalance", "gex"), r))
        for r in con.execute(
            "SELECT id,date,expiry_used,dte,pcr_oi,pcr_vol,iv_atm,iv_skew_25d,delta_imbalance,gex "
            "FROM options_daily ORDER BY date DESC LIMIT 20")
    ]
    con.close()
    if "--dry" in sys.argv:
        print(f"[us_options] --dry ingest {n} · rows {len(rows)}")
        return 0
    with open(OUT, "w") as f:
        json.dump({"rows": rows}, f)
    print(f"[us_options] ✅ ingest {n}종목 · export 최근 {len(rows)}행 → us_options_close.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
