#!/usr/bin/env python3
"""xs_backtest.py — 횡단면(cross-sectional) 4주 예측 백테스트 (2026-09-05 신설)

목적
----
"이 종목이 앞으로 4주간 **같은 시장의 다른 종목 대비** 더 오를까"를 점수화할 수
있는지 실측으로 판정한다. AEFS(LG·코스콤) 류 상품의 핵심이 이 횡단면 스코어인데,
그쪽은 성과를 공개하지 않으므로 우리는 **채택 전에 우리 데이터로 직접 검증**한다.
성과가 안 나오면 채택하지 않는다(하우스 규칙 — 백테스트 실측 후 채택).

방법론 — 흔한 함정을 피하려고 잡아둔 것들
--------------------------------------
1) **정답지 = 시장초과 수익률**. 원시 수익률을 쓰면 지수가 오른 구간에서 모든 종목이
   플러스라 '예측이 맞는 것처럼' 보인다. 매 시점 같은 시장 종목의 평균을 빼서
   순수 종목선택력만 남긴다(KR·US 각각).
2) **워크포워드**. t 시점 예측은 t 이전 데이터로만 학습한다(확장창, 최소 24기간).
   전 구간 회귀 후 그 계수로 과거를 맞히면 당연히 잘 맞는다 — 그건 검증이 아니다.
3) **윈저화 + 횡단면 z**. 팩터를 매 시점 시장 내에서 표준화하고 ±3σ 로 자른다.
   극단치 몇 종목이 회귀계수를 통째로 끌고 가는 것을 막는다.
4) **유동성 하한**(stock_px 유니버스: KR 1,000억↑·US $500M↑). 초소형주는 실제로
   못 사는 가격에 체결됐다고 가정하게 만들어 백테스트에만 존재하는 알파를 만든다.
5) **중첩 제거**. 20거래일 지평인데 매일 리밸런싱하면 표본이 중복돼 t값이 부풀려진다.
   20거래일 간격(월 1회)으로만 관측한다.
6) **시점별 시총 하한(PIT)** — 1차 실행(2026-09-05)에서 US 스프레드가 4주 +4.23%
   (연환산 +55%)로 비현실적으로 나왔다. 원인은 유니버스를 '**오늘** 시총 $500M↑'로
   잡은 것: 당시 초소형주였다가 지금 대형주가 된 종목만 남아 "앞으로 크게 오를 종목"이
   유니버스 자체에 미리 심겨 있었다(모멘텀 계열이 특히 부풀려진다). 그래서 시점 t 의
   시총을 `오늘시총 × (P_t / P_최근)` 로 역산해 **그 시점에 이미 하한을 넘던 종목만**
   남긴다(주식수 변동은 무시하는 근사지만, 미래참조의 대부분을 제거한다).
   `--nopit` 로 끄면 1차와 같은 편향된 결과가 재현된다 — 비교용.

판정 기준(사전 고정 — 결과 보고 바꾸지 않는다)
------------------------------------------
- 평균 IC ≥ 0.02 **그리고** IC t값 ≥ 2.0  → 신호 있음
- 상위20%−하위20% 스프레드가 4주 평균 > 0 이고 승률 > 50%  → 실전 유의
- 둘 다 미달이면 **채택하지 않는다**(가격팩터만으론 부족 → 팩터 패널 축적을 기다린다)

사용:  python3 scripts/xs_backtest.py [--mk kr|us|both] [--h 20]
"""
import json
import sqlite3
import sys
from pathlib import Path

import numpy as np

BASE = Path(__file__).resolve().parent.parent
DB = BASE / "data" / "db" / "stock_panel.sqlite"
POOL = BASE / "data" / "db" / "screener_pool.json"
CAP_MIN = {"kr": 1e11, "us": 5e8}   # stock_px.py 와 동일 하한

H = 20          # 예측 지평(거래일) ≈ 4주
STEP = 20       # 관측 간격 — 지평과 같게 두어 표본 중첩 제거
MIN_HIST = 260  # 팩터 계산에 필요한 최소 과거 길이(12개월 모멘텀)
MIN_TRAIN = 24  # 최소 학습 기간 수
LAM = 10.0      # 릿지 — 팩터 8개·표본 수만 개라 약한 정규화로 충분


def load(mk):
    cx = sqlite3.connect(DB)
    rows = cx.execute("SELECT c, d, close FROM px WHERE mk=? ORDER BY c, d", (mk,)).fetchall()
    cx.close()
    if not rows:
        return None, None, None
    codes, dates = sorted({r[0] for r in rows}), sorted({r[1] for r in rows})
    ci = {c: i for i, c in enumerate(codes)}
    di = {d: i for i, d in enumerate(dates)}
    P = np.full((len(codes), len(dates)), np.nan)
    for c, d, v in rows:
        P[ci[c], di[d]] = v
    return P, codes, dates


def caps_today(mk, codes):
    """오늘 시총(원/달러). 시점별 시총 역산의 기준값."""
    d = json.loads(POOL.read_text(encoding="utf-8"))
    m = {}
    for r in d.get(mk) or []:
        c = r.get("c") or r.get("sym")
        if c and isinstance(r.get("cap"), (int, float)):
            m[str(c)] = float(r["cap"])
    return np.array([m.get(c, np.nan) for c in codes])


def factors(P, t):
    """t 시점에 **관측 가능한** 가격 파생 팩터만. 미래 정보 사용 없음."""
    def ret(a, b):
        with np.errstate(invalid="ignore", divide="ignore"):
            return P[:, t - a] / P[:, t - b] - 1.0
    px = P[:, t]
    f = {}
    f["mom12_1"] = ret(20, 252)                     # 12개월 모멘텀 제외 최근 1개월(표준형)
    f["mom6"] = ret(0, 126)
    f["rev1m"] = -ret(0, 20)                        # 단기 반전 — 부호 뒤집어 '많이 빠진 게 +'
    win = P[:, t - 60:t + 1]
    with np.errstate(invalid="ignore", divide="ignore"):
        lr = np.diff(np.log(win), axis=1)
    f["lowvol"] = -np.nanstd(lr, axis=1)            # 저변동성 이상현상 — 변동성 낮을수록 +
    peak = np.nanmax(win, axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        f["mdd60"] = px / peak - 1.0                # 60일 고점 대비(0에 가까울수록 신고가권)
        f["ma200"] = px / np.nanmean(P[:, t - 200:t + 1], axis=1) - 1.0
        f["ma20"] = px / np.nanmean(P[:, t - 20:t + 1], axis=1) - 1.0
    d = np.diff(P[:, t - 15:t + 1], axis=1)
    up, dn = np.nansum(np.clip(d, 0, None), axis=1), -np.nansum(np.clip(d, None, 0), axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        f["rsi14"] = 100 - 100 / (1 + up / np.where(dn == 0, np.nan, dn))
    return f


def zs(v):
    """횡단면 z + ±3σ 윈저화. 결측은 0(= 그 시점 평균)으로 둔다."""
    m, s = np.nanmean(v), np.nanstd(v)
    if not np.isfinite(s) or s == 0:
        return np.zeros_like(v)
    z = np.clip((v - m) / s, -3, 3)
    return np.nan_to_num(z, nan=0.0)


def spearman(a, b):
    if len(a) < 20:
        return np.nan
    ra = np.argsort(np.argsort(a)).astype(float)
    rb = np.argsort(np.argsort(b)).astype(float)
    ra -= ra.mean(); rb -= rb.mean()
    dn = np.sqrt((ra ** 2).sum() * (rb ** 2).sum())
    return float((ra * rb).sum() / dn) if dn else np.nan


def run(mk, pit=True):
    P, codes, dates = load(mk)
    if P is None:
        print(f"[{mk}] 데이터 없음"); return
    T = len(dates)
    # 시점별 시총 근사 = 오늘시총 × (P_t / P_최근관측) — 미래참조 제거용
    capT = caps_today(mk, codes)
    last = np.array([np.nan if np.all(np.isnan(P[i])) else P[i][~np.isnan(P[i])][-1]
                     for i in range(len(codes))])
    ts = list(range(MIN_HIST, T - H, STEP))
    print(f"\n══ {mk.upper()} · {len(codes)}종목 · {dates[0]}~{dates[-1]} · 관측 {len(ts)}기간 "
          f"(지평 {H}거래일·간격 {STEP}) · 시점별 시총하한 {'ON' if pit else 'OFF(편향 재현)'}")

    FN, snaps = None, []
    for t in ts:
        f = factors(P, t)
        if FN is None:
            FN = list(f)
        with np.errstate(invalid="ignore", divide="ignore"):
            fwd = P[:, t + H] / P[:, t] - 1.0
        ok = np.isfinite(fwd) & np.isfinite(P[:, t]) & np.isfinite(P[:, t - 252])
        if pit:
            with np.errstate(invalid="ignore", divide="ignore"):
                cap_t = capT * (P[:, t] / last)      # 그 시점 시총 근사
            ok &= np.isfinite(cap_t) & (cap_t >= CAP_MIN[mk])
        if ok.sum() < 100:
            continue
        exc = fwd[ok] - np.nanmean(fwd[ok])          # ← 시장초과(핵심)
        X = np.column_stack([zs(f[k][ok]) for k in FN])
        snaps.append((dates[t], X, exc, ok.sum()))

    # ── 단일 팩터 IC (진단용) — 어떤 팩터가 실제로 정보를 갖는지
    nn = [s[3] for s in snaps]
    print(f"  단일 팩터 IC(평균 · t값) — 표본 {len(snaps)}기간 · 기간당 종목 중앙 {int(np.median(nn)) if nn else 0}")
    keep = []
    for j, k in enumerate(FN):
        ics = np.array([spearman(X[:, j], y) for _, X, y, _ in snaps])
        ics = ics[np.isfinite(ics)]
        tv = ics.mean() / ics.std(ddof=1) * np.sqrt(len(ics)) if len(ics) > 2 and ics.std(ddof=1) else np.nan
        flag = "◀ 유의" if abs(tv) >= 2 else ""
        print(f"    {k:9s} IC {ics.mean():+.4f}  t {tv:+.2f}  {flag}")
        if abs(tv) >= 2:
            keep.append(k)

    # ── 워크포워드 릿지 (전 팩터 결합)
    ic_wf, q_spread, q_hit, n_used = [], [], 0, 0
    q_wins, q_med, q_long = [], [], []
    for i in range(MIN_TRAIN, len(snaps)):
        Xtr = np.vstack([s[1] for s in snaps[:i]])
        ytr = np.concatenate([s[2] for s in snaps[:i]])
        A = Xtr.T @ Xtr + LAM * np.eye(Xtr.shape[1])
        beta = np.linalg.solve(A, Xtr.T @ ytr)
        d_, X, y, _ = snaps[i]
        pred = X @ beta
        ic = spearman(pred, y)
        if np.isfinite(ic):
            ic_wf.append(ic)
        k = max(1, len(y) // 5)
        o = np.argsort(-pred)
        sp = y[o[:k]].mean() - y[o[-k:]].mean()
        # (2026-09-05 2차 검증) 극단치 지배 여부 — 4주 수익률은 우측꼬리가 매우 두꺼워
        # 몇 종목의 +200% 가 평균 스프레드를 통째로 만들 수 있다. ±30% 윈저화한 값과
        # 중앙값 스프레드를 함께 보면, 신호가 '전체 분포의 이동'인지 '몇 종목 대박'인지 갈린다.
        yw = np.clip(y, -0.30, 0.30)
        q_wins.append(yw[o[:k]].mean() - yw[o[-k:]].mean())
        q_med.append(np.median(y[o[:k]]) - np.median(y[o[-k:]]))
        q_long.append(y[o[:k]].mean())          # 롱온리 상위20% 시장초과(실전에 더 가까움)
        q_spread.append(sp); q_hit += (sp > 0); n_used += 1

    if not ic_wf:
        print("  ⚠️ 워크포워드 표본 부족 — 판정 불가"); return
    ic_wf = np.array(ic_wf); q_spread = np.array(q_spread)
    ict = ic_wf.mean() / ic_wf.std(ddof=1) * np.sqrt(len(ic_wf)) if ic_wf.std(ddof=1) else np.nan
    print(f"  워크포워드(학습 {MIN_TRAIN}기간↑ · 검증 {n_used}기간)")
    print(f"    평균 IC        {ic_wf.mean():+.4f}   t값 {ict:+.2f}")
    qw, qm, ql = np.array(q_wins), np.array(q_med), np.array(q_long)
    print(f"    상위20%-하위20% 4주 평균 {q_spread.mean()*100:+.2f}%  "
          f"기간중앙 {np.median(q_spread)*100:+.2f}%  승률 {q_hit/n_used*100:.0f}%")
    print(f"      └ ±30% 윈저화 {qw.mean()*100:+.2f}%  ·  종목중앙값 기준 {qm.mean()*100:+.2f}%"
          f"  ← 원값과 크게 벌어지면 소수 종목이 만든 착시")
    print(f"    롱온리 상위20% 시장초과 4주 {ql.mean()*100:+.2f}%  승률 "
          f"{(ql>0).mean()*100:.0f}%  (연환산 참고 {ql.mean()*13*100:+.1f}%p)")
    ok1 = ic_wf.mean() >= 0.02 and ict >= 2.0
    ok2 = q_spread.mean() > 0 and q_hit / n_used > 0.5
    print(f"  판정 → IC기준 {'통과' if ok1 else '미달'} · 스프레드기준 {'통과' if ok2 else '미달'}"
          f"  ⇒ {'채택 검토' if (ok1 and ok2) else ('부분' if (ok1 or ok2) else '채택 안 함')}")
    if keep:
        print(f"  유의 팩터: {', '.join(keep)}")


if __name__ == "__main__":
    mks = ["kr", "us"]
    if "--mk" in sys.argv:
        v = sys.argv[sys.argv.index("--mk") + 1]
        if v != "both":
            mks = [v]
    pit = "--nopit" not in sys.argv
    for m in mks:
        run(m, pit=pit)
