#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""releadg.py — 시군구 단위 가격 예측 (2026-08-22 신설 · relead 엔진 재사용)

배경
  시도 예측(relead)을 보던 사용자가 "시군구 단위도 되나" 물었다. 기사들(한강벨트·
  판교·분당 이동)도 구·시 단위 논의라 시도 평균으로는 안 보이는 것이 많다.

범위 (사용자 선택: 서울 25개 구 + 경기 주요시)
  · 서울(11)  25개 구 전부
  · 경기(41)  최근 24개월 월평균 거래 MIN_N건 이상인 시·구 (거래가 너무 적으면
              중위가가 그 달 표본에 휘둘려 예측이 무의미하다)

기준계열
  자체 RTMS 실거래 DB(rtms.json) 의 시군구 월별 매매 중위가(억원) — 2006.01~.
  시도 모델과 같은 3개월 평균으로 평활한다. 월 표본이 적은 달은 그대로 두되
  ma() 가 인접 달과 섞어 잡음을 누른다.

지표 (재수집 없음 — 전부 이미 있는 파일에서)
  · 상속: relead.json 의 32종 — 전국 공통은 그대로, 시도별은 소속 시도 값
  · 자체: trade_g 거래건수 · rent_g 전월세 중위가 · gap_g 평균/중위 괴리(고가 쏠림)
  · sido_p: 소속 시도 중위가(시도→시군구 파급 — 기사들의 '순차 확산' 시군구판)

엔진: relead 의 ma/yoy/시차탐색/릿지/보정/가드/백테스트를 그대로 import 해 쓴다.
      백테스트 시점 수만 48→36 으로 줄인다(지역이 3배라 계산 시간 절충).

산출: data/db/releadg.json   사용: releadg.py   cron: 30 3 * * * (새벽 — 40분쯤 걸린다)
"""
import json, math, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import relead as R

DB = R.DB
OUT = DB / "releadg.json"
SIDO_OF = {"11": "서울", "41": "경기"}
MIN_N = 15          # 경기 편입 기준: 최근 24개월 월평균 거래건수
BT_ORIGINS = 36     # 시군구 백테스트 시점 수 (시도 48 → 36, 계산 시간 절충)

OWN_META = {
    "trade_g": ("거래건수(구)", "건", "부동산", "M", "RTMS", "그 시군구의 월 매매 신고 건수"),
    "rent_g":  ("전월세 중위가(구)", "억원", "부동산", "M", "RTMS", "전월세 실거래 중위 보증금"),
    "gap_g":   ("평균/중위 괴리(구)", "배", "가격", "M", "RTMS", "평균가÷중위가 — 고가거래 쏠림"),
    "sido_p":  ("소속 시도 중위가(파급)", "만원/㎡", "가격", "M", "한국부동산원(파생)",
                "시도 가격이 몇 달 뒤 이 시군구로 번지는가"),
}
R.TRANS["gap_g"] = "lvl"     # 배율은 수준 그대로


def main():
    print(f"releadg — 시군구 예측 ({R.NOW:%Y-%m-%d %H:%M})")
    rt = json.loads((DB / "rtms.json").read_text(encoding="utf-8"))
    rl = json.loads((DB / "relead.json").read_text(encoding="utf-8"))
    T = rl["t"]
    names, sale, rent = rt["names"], rt["sale"], rt["rent"]

    # ── 대상 선정
    codes = []
    for code, nm in sorted(names.items()):
        if code[:2] not in SIDO_OF:
            continue
        m = (sale.get(code) or {}).get("m") or {}
        if not m:
            continue
        rec = [m[k].get("n") or 0 for k in sorted(m)[-24:]]
        if code[:2] == "11" or (rec and sum(rec) / len(rec) >= MIN_N):
            codes.append(code)
    print(f"  대상 {len(codes)}개 (서울 {sum(1 for c in codes if c[:2]=='11')} · "
          f"경기 {sum(1 for c in codes if c[:2]=='41')})")

    GL = set(R.GLOBAL_KEYS)

    def inherit(k, sido):
        src = (rl["d"].get(k) or {})
        return src.get("전국" if k in GL else sido) or src.get("전국")

    out_pred, out_price, out_lead, out_d = {}, {}, {}, {}
    for i, code in enumerate(codes):
        nm, sido = names[code], SIDO_OF[code[:2]]
        m = (sale.get(code) or {}).get("m") or {}
        rm = (rent.get(code) or {}).get("m") or {}
        prices_raw = [ (m.get(t) or {}).get("med") for t in T ]
        if sum(1 for v in prices_raw if v is not None) < 120:
            continue
        prices = R.ma(prices_raw)
        ytr = R.yoy_log(prices)

        feat, keys = {}, []
        for k in rl["meta"]:                       # 상속 32종
            a = inherit(k, sido)
            if not a:
                continue
            f = R.transform(k, a)
            need = 36 if k in R.FIXED_KEYS else 60
            if sum(1 for v in f if v is not None) < need:
                continue
            feat[k] = f; keys.append(k)
        own = {
            "trade_g": [ (m.get(t) or {}).get("n") for t in T ],
            "rent_g":  R.ma([ (rm.get(t) or {}).get("med") for t in T ]),
            "gap_g":   [ ((m.get(t) or {}).get("avg") / (m.get(t) or {}).get("med"))
                         if (m.get(t) or {}).get("med") and (m.get(t) or {}).get("avg") else None
                         for t in T ],
            "sido_p":  (rl["price"].get(sido) or {}).get("ma"),
        }
        for k, a in own.items():
            if not a:
                continue
            f = R.transform(k, a)
            if sum(1 for v in f if v is not None) < 36:
                continue
            feat[k] = f; keys.append(k)
        if len(keys) < 5:
            continue

        t_last = max(j for j, v in enumerate(prices) if v is not None)
        fc = R.forecast(feat, ytr, prices, keys, t_last)
        bt = R.backtest(feat, ytr, prices, keys, origins=BT_ORIGINS)

        base = prices[t_last]
        g = {h: fc[h]["growth"] * (bt["by_h"].get(h, {}).get("calib", 0.0)) for h in fc}
        gs, guard = {}, {}
        for h in sorted(g):
            nb = [g[x] for x in (h - 1, h, h + 1) if x in g]
            v = sum(nb) / len(nb)
            hist = sorted(math.log(prices[j + h] / prices[j]) for j in range(len(prices) - h)
                          if prices[j] and prices[j + h])
            if len(hist) >= 40:
                lo_, hi_ = hist[int(len(hist) * 0.05)], hist[int(len(hist) * 0.95)]
                if v < lo_ or v > hi_:
                    guard[h] = True
                v = max(lo_, min(hi_, v))
            gs[h] = v
        z = 1.2816
        ft, fp, flo, fhi = [], [], [], []
        for h in sorted(gs):
            sd = (bt["by_h"].get(h) or {}).get("sd") or (bt["by_h"].get(h) or {}).get("mape") or 0
            band = sd / 100 * z
            p = base * math.exp(gs[h])
            ft.append(R.add_months(T[t_last], h))
            fp.append(round(p, 3)); flo.append(round(p * (1 - band), 3)); fhi.append(round(p * (1 + band), 3))

        lg_all = R.lags_for(feat, ytr, keys)
        out_lead[code] = dict(sorted(lg_all.items(), key=lambda kv: -abs(kv[1]["corr"]))[:12])
        meta_all = dict(rl["meta"]); meta_all.update(
            {k: {"label": v[0], "unit": v[1], "group": v[2], "cycle": v[3], "src": v[4], "note": v[5]}
             for k, v in OWN_META.items()})
        out_pred[code] = {
            "name": nm, "sido": sido,
            "t": ft, "price": fp, "lo": flo, "hi": fhi, "guarded": sorted(guard),
            "last": {"t": T[t_last], "price": round(prices[t_last], 3), "raw": prices_raw[t_last]},
            "used": [{"key": k, "label": meta_all[k]["label"],
                      "lag": (fc.get(12, {}).get("lags") or {}).get(k),
                      "corr": (fc.get(12, {}).get("corrs") or {}).get(k)}
                     for k in keys if k in (fc.get(12, {}).get("lags") or {})][:12],
            "backtest": bt,
        }
        out_price[code] = {"raw": prices_raw, "ma": [round(v, 3) if v else None for v in prices]}
        out_d[code] = {k: own[k] for k in ("trade_g", "rent_g", "gap_g") if own.get(k)}
        print(f"  [{i+1}/{len(codes)}] {nm:<10} 지표 {len(keys)} · MAPE {bt['mape']}% · 방향 {bt['hit']}%")

    out = {
        "asof": R.NOW.strftime("%Y-%m-%d %H:%M"),
        "src": "RTMS 실거래(자체 집계) + relead 상속 지표",
        "note": ("시군구 기준계열은 자체 RTMS 실거래 중위가(억원·3개월 평균). "
                 "시군구는 월 표본이 적어 시도보다 잡음이 크다 — 백테스트 성적을 반드시 함께 볼 것."),
        "unit": "억원",
        "t": T, "horizon": R.HZ,
        "meta": {k: {"label": v[0], "unit": v[1], "group": v[2], "cycle": v[3], "src": v[4], "note": v[5]}
                 for k, v in OWN_META.items()},
        "names": {c: names[c] for c in out_pred},
        "pred": out_pred, "price": out_price, "lead": out_lead, "d": out_d,
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"  → {OUT} ({OUT.stat().st_size // 1024}KB) · 지역 {len(out_pred)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
