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

1차 실측 결과 (2026-09-05 · 가격 파생 팩터 8종 · 5년 · PIT 하한 ON)
------------------------------------------------------------
                       KR(996종목/기간)        US(2,457종목/기간)
  워크포워드 평균 IC     -0.0063 (t -0.27)      +0.0179 (t +0.50)
  상위-하위 4주 스프레드  -0.06%  승률 43%       +2.31%  승률 64%
    ±30% 윈저화          -0.37%                 +0.94%   ← 절반 이하로 축소
    종목중앙값 기준       -0.61%                 +0.23%   ← 사실상 소멸
  단일팩터 롱온리 최고    mom12_1 +0.74% t1.33   mom12_1 +0.69% t1.77
  ⇒ **채택 안 함**. US 원시 스프레드만 기준을 넘지만, 윈저화·중앙값에서 사실상
    사라지므로 소수 종목의 대박이 만든 착시다(IC t 0.50 과도 정합). 한·미 모두
    단일 팩터 어느 것도 t≥2 를 못 넘는다.

  부수 발견 — KR 저변동성(lowvol)은 IC +0.0920(t +3.15)로 유일하게 강했지만,
  롱온리로는 -0.48%(승률 38%)다. 즉 **고르는 팩터가 아니라 거르는 팩터**다
  (고변동성 하위군을 피하는 데서 정보가 나왔지, 저변동성 상위군이 오른 게 아니다).
  스크리너 하드컷 후보로는 의미가 있으나 스코어의 (+) 축으로 쓰면 안 된다.

  해석: 가격만으로 4주 횡단면을 맞히려는 시도는 실패했다 — 예상된 결과다(공개된
  가격 정보는 가장 빨리 소멸하는 알파다). 진짜 후보는 우리가 이미 매일 모으지만
  아직 과거가 없는 축 — 컨센 리비전·서프라이즈·수급·가이던스다. stock_panel 이
  6~12개월 쌓인 뒤 같은 하네스로 재검증할 것.

2차 재검증 (2026-09-07 · 예약 실행) — **판정 유보**
--------------------------------------------
  panel 축적 1일(2026-09-04 · KR 2,533 / US 5,205행)뿐. 예약(2027-03-08)보다 6개월 이른
  시점에 실행됐다. 워크포워드 최소 요건(학습 24 + 검증 12 = 36기간 ≈ 3년 월간관측,
  현실적으로는 축적 6개월 = 관측 6기간에 불과)에 턱없이 못 미쳐 판정하지 않는다.
  이번 회차에서 한 일: panel 테이블 조인(`--set panel|all`, 팩터 24종·부호 사전고정)과
  팩터군별 워크포워드·판정 유보 게이트(MIN_VALID)·착시검사(ok3) 를 하네스에 넣어
  다음 회차는 실행만 하면 되게 준비. 가격팩터 8종(`--set px`) 결과는 1차와 동일
  (px 패널 2026-09-04 까지 정상 적재 확인). 크론(09:00/17:00) 정상.

  ※ 주의 — 관측 간격 20거래일이라 panel 6개월 축적 = 관측 6기간이다. MIN_TRAIN 24 를
  panel 에 그대로 요구하면 2년 넘게 기다려야 한다. 다음 회차에 표본이 부족하면
  (a) 관측 간격을 5거래일로 줄이고 뉴이-웨스트 t 를 쓰거나 (b) 가격팩터 5년으로 사전
  학습한 뒤 panel 축을 증분 학습하는 식의 완화를 **결과를 보기 전에** 정해서 적용할 것.

사용:  python3 scripts/xs_backtest.py [--mk kr|us|both] [--nopit] [--set px|panel|all]
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
MIN_VALID = 12  # 워크포워드 검증 기간이 이보다 적으면 "판정 유보"(억지 판정 금지)

# ── panel 테이블 팩터 (2026-09-07 추가) — 가격으로 소급 불가능했던 축.
#    부호는 **사전에** 고정한다(데이터 보고 뒤집지 않는다): 값이 클수록 4주 초과수익에
#    (+)일 것으로 가설하는 방향으로 맞춰 둔다. 밸류 배수는 낮을수록 싸므로 −, 공매도·
#    대차잔고는 높을수록 하방 압력으로 −. 결측은 zs() 에서 그 시점 평균(0)으로 둔다.
PANEL_FACTORS = {
    # 리비전
    "cr30": +1, "cr90": +1, "cr7": +1, "tprv": +1, "tprv90": +1, "eps_rev": +1,
    # 서프라이즈
    "spr": +1, "sspr": +1, "sprb": +1,
    # 성장·전망
    "opg": +1, "opg_f": +1, "gacc": +1, "epsg": +1, "qup": +1, "yup": +1,
    # 밸류 (배수 낮을수록 +)
    "per": -1, "pbr": -1, "psr": -1, "fper": -1, "upside": +1,
    # 수급
    "frgn": +1, "inst": +1, "sr": -1, "lbr": -1,
}
PANEL_GROUP = {
    "리비전": ["cr30", "cr90", "cr7", "tprv", "tprv90", "eps_rev"],
    "서프라이즈": ["spr", "sspr", "sprb"],
    "성장전망": ["opg", "opg_f", "gacc", "epsg", "qup", "yup"],
    "밸류": ["per", "pbr", "psr", "fper", "upside"],
    "수급": ["frgn", "inst", "sr", "lbr"],
}


def load_panel(mk, codes):
    """panel 테이블 → {d: ndarray(len(codes), len(PANEL_FACTORS))}. 조인 키 (d, mk, c).
    밸류 배수는 0 이하(적자)를 결측 처리 — PER −5 가 '아주 싸다'로 읽히는 오류 방지."""
    cx = sqlite3.connect(DB)
    try:
        cols = list(PANEL_FACTORS)
        have = {r[1] for r in cx.execute("PRAGMA table_info(panel)")}
        cols = [k for k in cols if k in have]
        if not cols:
            return {}, []
        # US 풀은 pbr→pb · fper→fpe 이름을 쓴다(실측 2026-09-07: US pbr/fper 0건, pb/fpe 는 있음)
        alias = {"pbr": "COALESCE(pbr,pb)", "fper": "COALESCE(fper,fpe)"}
        sel = ",".join(alias.get(k, k) if k in have else "NULL" for k in cols)
        rows = cx.execute(f"SELECT d, c, {sel} FROM panel WHERE mk=?", (mk,)).fetchall()
    except sqlite3.OperationalError:
        return {}, []
    finally:
        cx.close()
    ci = {c: i for i, c in enumerate(codes)}
    out = {}
    for r in rows:
        d, c = r[0], str(r[1])
        if c not in ci:
            continue
        M = out.setdefault(d, np.full((len(codes), len(cols)), np.nan))
        M[ci[c]] = [np.nan if v is None else float(v) for v in r[2:]]
    for d, M in out.items():
        for j, k in enumerate(cols):
            if k in ("per", "pbr", "psr", "fper"):
                M[np.where(M[:, j] <= 0)[0], j] = np.nan
            M[:, j] *= PANEL_FACTORS[k]
    return out, cols


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


def run(mk, pit=True, fset="px"):
    """fset: px = 가격 파생 8종(1차와 동일) · panel = panel 팩터만 · all = 둘 다.
    panel/all 은 관측 시점이 panel 스냅샷이 있는 날로 제한된다(가격은 5년, 패널은 축적분만)."""
    P, codes, dates = load(mk)
    if P is None:
        print(f"[{mk}] 데이터 없음"); return
    T = len(dates)
    # 시점별 시총 근사 = 오늘시총 × (P_t / P_최근관측) — 미래참조 제거용
    capT = caps_today(mk, codes)
    last = np.array([np.nan if np.all(np.isnan(P[i])) else P[i][~np.isnan(P[i])][-1]
                     for i in range(len(codes))])
    panel, pcols = ({}, [])
    if fset == "px":
        ts = list(range(MIN_HIST, T - H, STEP))
    else:
        panel, pcols = load_panel(mk, codes)
        di = {d: i for i, d in enumerate(dates)}
        # panel 날짜 중 px 에도 있고(조인), 팩터 이력·정답지가 갖춰진 날만, STEP 간격으로 솎는다
        cand = sorted(di[d] for d in panel if d in di and MIN_HIST <= di[d] < T - H)
        ts, prev = [], -10**9
        for t in cand:
            if t - prev >= STEP:
                ts.append(t); prev = t
        pd_all = sorted(panel)
        print(f"\n   panel 축적: {len(pd_all)}일 ({pd_all[0] if pd_all else '-'}~{pd_all[-1] if pd_all else '-'})"
              f" · 정답지(+{H}거래일) 확보된 관측일 {len(cand)} → {STEP}거래일 간격 {len(ts)}기간"
              f" · 팩터 {len(pcols)}종")
    print(f"\n══ {mk.upper()} · {len(codes)}종목 · {dates[0]}~{dates[-1]} · 관측 {len(ts)}기간 "
          f"(지평 {H}거래일·간격 {STEP}) · 팩터셋 {fset} · 시점별 시총하한 {'ON' if pit else 'OFF(편향 재현)'}")
    if len(ts) < MIN_TRAIN + MIN_VALID:
        print(f"  ⏸ 판정 유보 — 관측 {len(ts)}기간 < 최소 {MIN_TRAIN}(학습)+{MIN_VALID}(검증)."
              f" 표본이 모일 때까지 기다린다(억지 판정 금지).")
        if fset != "px":
            return
    if not ts:
        return

    FN, snaps = None, []
    for t in ts:
        f = factors(P, t) if fset != "panel" else {}
        if fset != "px":
            M = panel[dates[t]]
            for j, k in enumerate(pcols):
                f[k] = M[:, j]
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

    # ── 단일 팩터 롱온리 (학습 없음 = 과적합 여지 없음)
    #    부호를 데이터로 고르지 않고 factors() 에서 **사전에** 고정해 뒀으므로
    #    (저변동성 +, 단기반전 +, 모멘텀 +) 전 기간을 그대로 평가해도 정직하다.
    #    릿지 결합이 실패해도 개별 팩터에 신호가 살아있는지 여기서 갈린다.
    print("  단일 팩터 롱온리 상위20% 시장초과(4주 평균 · 승률) — 학습 없음")
    for j, k in enumerate(FN):
        r = []
        for _, X, y, _ in snaps:
            kk = max(1, len(y) // 5)
            r.append(y[np.argsort(-X[:, j])[:kk]].mean())
        r = np.array(r)
        tv = r.mean() / r.std(ddof=1) * np.sqrt(len(r)) if len(r) > 2 and r.std(ddof=1) else np.nan
        print(f"    {k:9s} {r.mean()*100:+.2f}%  승률 {(r>0).mean()*100:3.0f}%  t {tv:+.2f}"
              f"  {'◀' if tv >= 2 else ''}")

    # ── 워크포워드 릿지 (전 팩터 결합)
    res = walk_forward(snaps, list(range(len(FN))))
    if res is None:
        print("  ⚠️ 워크포워드 표본 부족 — 판정 불가"); return
    report_wf(res, keep)
    # ── 팩터군별 워크포워드 (panel/all) — 어떤 축이 실제로 기여하는지 기록용
    if fset != "px":
        print("  팩터군별 워크포워드(같은 하네스 · 해당 군만 학습)")
        groups = dict(PANEL_GROUP)
        if fset == "all":
            groups = {"가격8종": [k for k in FN if k not in PANEL_FACTORS], **groups}
        for g, ks in groups.items():
            idx = [FN.index(k) for k in ks if k in FN]
            if not idx:
                continue
            r = walk_forward(snaps, idx)
            if r is None:
                continue
            print(f"    {g:6s} IC {r['ic'].mean():+.4f} t {r['ict']:+.2f} · 스프레드 {r['sp'].mean()*100:+.2f}%"
                  f" 승률 {r['hit']*100:.0f}% · 윈저 {r['qw'].mean()*100:+.2f}% 중앙 {r['qm'].mean()*100:+.2f}%")


def walk_forward(snaps, idx):
    """확장창 워크포워드 릿지. idx = 사용할 팩터 열 인덱스. 검증 기간 < MIN_VALID 면 None."""
    ic_wf, q_spread, q_hit, n_used = [], [], 0, 0
    q_wins, q_med, q_long = [], [], []
    for i in range(MIN_TRAIN, len(snaps)):
        Xtr = np.vstack([s[1][:, idx] for s in snaps[:i]])
        ytr = np.concatenate([s[2] for s in snaps[:i]])
        A = Xtr.T @ Xtr + LAM * np.eye(Xtr.shape[1])
        beta = np.linalg.solve(A, Xtr.T @ ytr)
        d_, X, y, _ = snaps[i]
        pred = X[:, idx] @ beta
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

    if len(ic_wf) < MIN_VALID:
        return None
    ic_wf = np.array(ic_wf); q_spread = np.array(q_spread)
    ict = ic_wf.mean() / ic_wf.std(ddof=1) * np.sqrt(len(ic_wf)) if ic_wf.std(ddof=1) else np.nan
    return dict(ic=ic_wf, ict=ict, sp=q_spread, hit=q_hit / n_used, n=n_used,
                qw=np.array(q_wins), qm=np.array(q_med), ql=np.array(q_long))


def report_wf(r, keep):
    ic_wf, ict, q_spread = r["ic"], r["ict"], r["sp"]
    qw, qm, ql = r["qw"], r["qm"], r["ql"]
    print(f"  워크포워드(학습 {MIN_TRAIN}기간↑ · 검증 {r['n']}기간)")
    print(f"    평균 IC        {ic_wf.mean():+.4f}   t값 {ict:+.2f}")
    print(f"    상위20%-하위20% 4주 평균 {q_spread.mean()*100:+.2f}%  "
          f"기간중앙 {np.median(q_spread)*100:+.2f}%  승률 {r['hit']*100:.0f}%")
    print(f"      └ ±30% 윈저화 {qw.mean()*100:+.2f}%  ·  종목중앙값 기준 {qm.mean()*100:+.2f}%"
          f"  ← 원값과 크게 벌어지면 소수 종목이 만든 착시")
    print(f"    롱온리 상위20% 시장초과 4주 {ql.mean()*100:+.2f}%  승률 "
          f"{(ql>0).mean()*100:.0f}%  (연환산 참고 {ql.mean()*13*100:+.1f}%p)")
    ok1 = ic_wf.mean() >= 0.02 and ict >= 2.0
    ok2 = q_spread.mean() > 0 and r["hit"] > 0.5
    # (2026-09-05 경험) 필수 조건 3: 윈저화·중앙값 스프레드가 원값의 절반 밑으로 무너지면
    # 소수 종목 착시 → 통과로 치지 않는다
    ok3 = q_spread.mean() > 0 and qw.mean() >= 0.5 * q_spread.mean() and qm.mean() >= 0.5 * q_spread.mean()
    print(f"  판정 → IC기준 {'통과' if ok1 else '미달'} · 스프레드기준 {'통과' if ok2 else '미달'}"
          f" · 착시검사 {'통과' if ok3 else '미달'}"
          f"  ⇒ {'채택 검토' if (ok1 and ok2 and ok3) else ('부분' if (ok1 or ok2) else '채택 안 함')}")
    if keep:
        print(f"  유의 팩터: {', '.join(keep)}")


if __name__ == "__main__":
    mks = ["kr", "us"]
    if "--mk" in sys.argv:
        v = sys.argv[sys.argv.index("--mk") + 1]
        if v != "both":
            mks = [v]
    pit = "--nopit" not in sys.argv
    fset = sys.argv[sys.argv.index("--set") + 1] if "--set" in sys.argv else "px"
    for m in mks:
        run(m, pit=pit, fset=fset)
