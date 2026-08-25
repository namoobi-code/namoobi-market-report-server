#!/usr/bin/env python3
"""stlead_score.py — 실전 예측 채점 (매월 1일 06:40 cron)

stlead.py가 매일 적재하는 예측 스냅샷(stlead_pred_hist.json)에서 만기가 도래한
예측("N개월 전에 한 N개월 예측")을 실제 수익률과 비교해 채점한다.
백테스트(표본 내 재현)와 달리 이것이 진짜 실전 성적표다.

이탈 판정(사전 고정 기준 — 판단이 아니라 규칙):
  F1  실전 MAE가 백테스트 MAPE의 2배 초과 (표본 3회 이상일 때만)
  F2  최근 3회 채점 중 방향 오답 2회 이상 (표본 3회 이상)
  F3  실제가 예측 밴드(±1.5σ, 로그) 밖 이탈이 최근 3회 중 1회 이상
걸린 자산은 flag=1 + 사유 기록 → 화면 ⚠ 배지 + 월간 LLM 원인검토 대상.

급락확률 채점(브라이어 점수)은 12개월 만기라 스냅샷 1년치 축적 후 자동 활성화.
"""
import json
import math
import sys
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DB = BASE / "data" / "db"
PRED_HIST = DB / "stlead_pred_hist.json"
STLEAD = DB / "stlead.json"
OUT = DB / "stlead_score.json"
HORIZONS = [1, 3, 6, 12, 18, 24]
CRASH_HZ = 12
CRASH_DD = 0.80


def add_months(ym, n):
    y, m = int(ym[:4]), int(ym[4:6])
    m += n
    y += (m - 1) // 12
    m = (m - 1) % 12 + 1
    return f"{y:04d}{m:02d}"


def main():
    try:
        hist = json.loads(PRED_HIST.read_text(encoding="utf-8"))
    except Exception:
        print("[score] pred_hist 없음 — stlead.py가 먼저 스냅샷을 적재해야 한다")
        sys.exit(0)
    d = json.loads(STLEAD.read_text(encoding="utf-8"))
    targets = d["targets"]

    # 실측 월별 종가: stlead.json 의 t/hist (past 이하가 실측)
    px = {}
    for tk, t in targets.items():
        px[tk] = {str(t["t"][i]): t["hist"][i]
                  for i in range(t["past"] + 1) if t["hist"][i] is not None}

    # 스냅샷 정리 — 같은 기준월(m0)은 마지막 스냅샷만 사용(월말 상태 = 그 달의 확정 예측)
    by_issue = {}                                   # {tk: {m0: (date, row)}}
    for date in sorted(hist):
        for tk, row in hist[date].items():
            by_issue.setdefault(tk, {})[row["m0"]] = (date, row)

    out_t, n_scored = {}, 0
    for tk, issues in by_issue.items():
        if tk not in targets:
            continue
        bt_by_h = (targets[tk].get("bt") or {}).get("by_h") or {}
        hs, recs = {}, []                           # recs: 시간순 개별 채점(최근 판정용)
        for m0 in sorted(issues):
            date, row = issues[m0]
            for h in HORIZONS:
                gp = (row.get("g") or {}).get(str(h))
                if gp is None or not row.get("p0"):
                    continue
                due = add_months(m0, h)
                act_p = px.get(tk, {}).get(due)
                if act_p is None:
                    continue                        # 아직 만기 미도래
                act = (act_p / row["p0"] - 1) * 100
                sd = (row.get("sd") or {}).get(str(h)) or 0.05
                breach = abs(math.log(act_p / (row["p0"] * (1 + gp / 100)))) > 1.5 * sd
                rec = {"m0": m0, "h": h, "pred": round(gp, 2), "act": round(act, 2),
                       "err": round(abs(act - gp), 2),
                       "hit": 1 if (gp >= 0) == (act >= 0) else 0,
                       "breach": 1 if breach else 0}
                hs.setdefault(h, []).append(rec)
                recs.append(rec)
                n_scored += 1
        if not recs:
            out_t[tk] = {"n": 0}
            continue
        by_h = {}
        for h, rr in hs.items():
            mape_bt = (bt_by_h.get(str(h)) or bt_by_h.get(h) or {}).get("mape")
            mae = sum(r["err"] for r in rr) / len(rr)
            by_h[h] = {"n": len(rr), "mae": round(mae, 2),
                       "hit": round(100 * sum(r["hit"] for r in rr) / len(rr)),
                       "breach": sum(r["breach"] for r in rr),
                       "mape_bt": mape_bt,
                       "ratio": round(mae / mape_bt, 2) if mape_bt else None,
                       "recent": rr[-3:]}
        # ── 이탈 판정 (고정 기준)
        reasons = []
        for h, s in by_h.items():
            if s["n"] >= 3 and s["ratio"] is not None and s["ratio"] > 2:
                reasons.append(f"{h}M 실전오차 {s['mae']}% = 백테스트 {s['mape_bt']}%의 {s['ratio']}배")
        last3 = recs[-3:]
        if len(last3) >= 3 and sum(r["hit"] for r in last3) <= 1:
            reasons.append(f"최근 3회 방향 오답 {3 - sum(r['hit'] for r in last3)}회")
        if len(last3) >= 1 and sum(r["breach"] for r in last3) >= 1:
            reasons.append("최근 채점에서 ±1.5σ 밴드 이탈")
        out_t[tk] = {"n": len(recs), "by_h": by_h,
                     "flag": 1 if reasons else 0, "reasons": reasons}

    # ── 급락확률 채점(브라이어) — 12M 만기 도래분만
    crash = {}
    for tk, issues in by_issue.items():
        rows = []
        for m0 in sorted(issues):
            date, row = issues[m0]
            if "cr" not in row or not row.get("p0"):
                continue
            fut = [px.get(tk, {}).get(add_months(m0, i + 1)) for i in range(CRASH_HZ)]
            if any(v is None for v in fut):
                continue
            label = 1 if min(fut) / row["p0"] <= CRASH_DD else 0
            rows.append((row["cr"] / 100, label))
        if rows:
            crash[tk] = {"n": len(rows),
                         "brier": round(sum((p - y) ** 2 for p, y in rows) / len(rows), 4),
                         "ev": sum(y for _, y in rows)}

    flagged = [tk for tk, v in out_t.items() if v.get("flag")]
    OUT.write_text(json.dumps({
        "asof": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "since": min(hist) if hist else "", "snapshots": len(hist),
        "scored": n_scored, "targets": out_t, "crash": crash, "flagged": flagged,
        "note": ("실전 채점 — 스냅샷(매일 05:20 적재)의 만기 도래 예측 vs 실제. "
                 "기준: F1 오차>백테스트×2, F2 최근3회 방향오답≥2, F3 ±1.5σ 이탈. "
                 "표본은 천천히 쌓인다(1M 예측 첫 채점 = 적재 시작 한 달 뒤).")},
        ensure_ascii=False), encoding="utf-8")
    print(f"[score] 스냅샷 {len(hist)}일 · 채점 {n_scored}건 · ⚠ {flagged or '없음'}"
          f" → {OUT.name}")


if __name__ == "__main__":
    main()
