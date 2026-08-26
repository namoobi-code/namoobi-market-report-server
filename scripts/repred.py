#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""repred.py — 부동산 r-가중 합성 예측 (2026-08-23 신설 · RE 예측 탭 데이터)

방법 (사용자 지정: 릿지 회귀계수 β 는 쓰지 않는다)
  Portfolio 탭과 같은 사고방식 — 지표를 그룹으로 묶어 보여주되, **가중치는 지표별
  시차(M)와 r 로 개별 결정**한다. 지평 h 개월 예측은:

    1) 지표별로 시차 L ∈ [h, MAXLAG] 을 옮기며 목표(마지막 관측 대비 h개월 누적
       로그변화율)와의 상관 r 이 최대인 시차를 고른다 — 관측된 값만 쓰는 규칙.
    2) 가중치 w_k = |r_k| / Σ|r| (그 지평에 출전한 지표들끼리 비례 배분).
    3) 예측 ŷ_h = ȳ_h + sd_y·Σ_k w_k·r_k·z_k
       (z_k = 그 지표의 현재 표준화 값, ±3σ 클램프 — 단일지표 OLS 예측의 가중평균)
    4) 워크포워드 백테스트(그 시점 자료만, 시차 탐색부터 다시)로 보정계수·오차밴드,
       relead 와 같은 3점 평활 + 역사범위(5~95%) 가드.

  릿지와의 차이: 중복 지표의 발언을 자동으로 깎지 않는다. 같은 얘기를 하는 지표가
  많은 그룹은 그만큼 합산 발언이 커진다 — 대신 계산이 투명하고(r 만 보면 됨),
  화면에서 지표별 가중치 배수·시나리오(±1σ) 조절이 정확히 재현된다.

지표: relead.json 의 36종 상속 + 신규 2종
  subs  청약 경쟁률   applyhome.json series (2020.02~, 시도별 가중평균) — 기사 심리 그룹
  cons  건설수주액    ECOS 901Y020/I42A (1990~, 월, 전국 공통) — 공급 파이프라인 최상류
  ※ 전월세전환율(KOSIS DT_KAB_11671_N06)은 objL 조합 전부 빈 응답 — 제외(실측 2026-08-23).
  ※ 급매물 비율(직방·다방)·KB 매수우위는 공개 API 없음 — 매매수급동향(보유)이 후자를 대체.

편입 판정: --judge 로 서울·전국·경기에서 기본 vs +subs vs +cons vs +둘다 백테스트 비교.
산출: data/db/repred.json    사용: repred.py [--judge]    cron: 10 8 * * * (relead 07:55 뒤)
"""
import json, math, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import relead as R

DB = R.DB
OUT = DB / "repred.json"
# (2026-08-23) 부동산은 사이클이 길다(사용자): 지평 24→30개월, 시차 상한 30→36
#   (h개월 예측에는 시차≥h 지표만 출전 — 30개월 예측이 성립하려면 상한이 그 위여야 한다).
#   표시 지평은 1M 유지 + 30M 추가 (사용자 확정 2026-08-23).
HZ = 30
MAXLAG = 36
DISP_H = (1, 3, 6, 12, 18, 24, 30)      # 화면 표에 보여줄 지평
BT_ORIGINS = 48
JUDGE = "--judge" in sys.argv

# 신규 지표 변환 방식
R.TRANS["subs"] = "lvl"                  # 경쟁률(배) — 수준 그대로
R.TRANS["j2m"] = "lvl"                   # 전월세전환율(%) — 수준 그대로
# cons(금액)는 기본 yoy — TRANS 미등록이면 전년비

# (2026-08-23) 보정계수(calib)는 **적용하지 않는다** — 선택/평가 분리 실측:
#   앞 24시점에서 calib을 추정해 뒤 24시점을 채점한 결과, 보정 없음(raw)이 전 지역 최선.
#     서울 raw 6.87%/방향 81% vs calib≥0 9.00% vs 음수허용 14.69% (전국·경기도 동일 순위)
#   합성 신호의 기울기가 구간(급등→급락→반등)에 따라 뒤집혀, 과거 기울기를 곱하는 것
#   자체가 해가 된다. 예측선은 원신호 + 3점 평활 + 역사범위(5~95%) 가드만 쓴다.
#   calib 값은 참고용으로 계속 산출·표시한다(적용만 안 함).

# ── 기사(2026-08 리서치) 프레임: 표시그룹 · 통설 선행기간 · 해석 한 줄 ──
#    실측 시차와 나란히 보여주기 위한 메타 — 계산에는 쓰지 않는다(계산은 실측만).
ART = {
    # key: (표시그룹, 통설 선행, 해석)
    "permit":   ("공급", "6~18M", "인허가 감소 → 몇 년 뒤 공급 부족 → 상승 압력"),
    "start":    ("공급", "3~12M", "착공 증가 → 향후 입주물량 증가 → 하락 압력"),
    "presale":  ("공급", "2~6M",  "분양 증가 → 공급 증가·청약 경쟁률 변화"),
    "unsold":   ("공급", "1~3M",  "미분양 증가 → 공급 과잉 → 하락 압력"),
    "unsold_done": ("공급", "—",  "악성 미분양 — 다 짓고도 안 팔린 물량"),
    # (2026-08-26 통설 재검토) 문헌 보강 — 근거 있는 것만 추가:
    #   기준금리 6~12M(한은 통화정책 파급 2~4분기+코픽스 시차) · M2/주담대잔액 6~12M
    #   (국토연구원: 과잉유동성 6개월 후 영향 시작·12개월 최대·18개월 소멸) ·
    #   KOSPI 6~12M(주가→부동산 자금 전이 통설·SF연은 실증) ·
    #   준공·전세가율은 기사 분류상 **후행지표**(3~6M) — 통설 열에 그대로 표기.
    "comp":     ("공급", "후행 3~6M", "준공(입주물량) — 기사 분류상 후행지표: 다 지어진 뒤 가격에 반영"),
    "cons":     ("공급", "3~6M",  "수주 증가 → 착공·인허가로 이어지는 최상류"),
    "trade":    ("수요·금융", "1~3M", "거래량 증가 → 시장 활성화, 상승 신호"),
    "jeonse":   ("수요·금융", "1~2M", "전세 상승 → 매매 수요 증가 선행(전세→매매 순서)"),
    "jr":       ("수요·금융", "후행 3~6M", "전세가율 — 기사 분류상 후행지표(입주물량이 전세를 거쳐 반영)"),
    "wolse":    ("수요·금융", "—",    "보유세 전가가 월세로 먼저 나타남"),
    "j2m":      ("수요·금융", "—",    "전세→월세 전환 이자율 — 높을수록 월세 부담 커 전세·매매 선호"),
    "mtg_rate": ("수요·금융", "1~3M", "금리 하락 → 구매력 증가 → 상승 압력"),
    "mtg_bal":  ("수요·금융", "6~12M", "주담대 잔액 — 유동성 계열 통설(국토연구원 6~12M)"),
    "rate_kr":  ("수요·금융", "6~12M", "기준금리 — 통화정책 파급 2~4분기 통설(한은) + 코픽스 반영 시차"),
    "supply":   ("심리", "2~3M",  "매수우위(수급) — KB 매수우위지수 대응 지표"),
    "supply_j": ("심리", "—",     "전세수급 — 전세난은 매매 전환 압력"),
    "csi":      ("심리", "—",     "1년 후 가격 전망 설문 — 100 위면 상승 우세"),
    "subs":     ("심리", "1~3M",  "청약 경쟁률 상승 → 심리 회복, 상승 선행"),
    "bid_apt_rate": ("심리", "1~3M", "낙찰가율 80%↑ 안정 · 70%↓ 침체 신호"),
    "bid_apt_sldrate": ("심리", "—", "경매 물건 중 낙찰 비중"),
    "bid_apt_auctn": ("심리", "—",  "경매 유입 물량 — 침체가 길수록 쌓임"),
    "bid_all_rate": ("심리", "—",   "전체 용도 낙찰가율"),
    "hppci":    ("가격", "—", "전국 매매지수 — 가격 자신의 전국 흐름"),
    "rt_idx":   ("가격", "—", "실거래지수 — 자기 과거 흐름(자기회귀)"),
    "rt_avg":   ("가격", "—", "평균가 — 중위가와의 괴리가 고가 쏠림"),
    "gap_am":   ("가격", "—", "평균/중위 괴리배율 — 고가거래 쏠림"),
    "seoul_p":  ("가격", "—", "서울 가격의 지방 파급(순차 확산)"),
    "cli":      ("거시", "—", "경기선행지수 — 실물 경기의 방향"),
    "m2":       ("거시", "6~12M", "유동성 → 6개월 후 영향 시작·12개월 최대(국토연구원)"),
    "gdp":      ("거시", "—", "명목 성장 — 자산가격의 장기 닻"),
    "fx":       ("거시", "—", "원화 약세 → 자산가격 상승 압력"),
    "rate_us":  ("거시", "—", "글로벌 긴축/완화 사이클"),
    "kospi":    ("거시", "6~12M", "주가→부동산 자금 전이 통설 6개월~1년(SF연은 실증 ~2년)"),
    "hdi_pc":   ("소득", "—", "가계가 실제 쓸 수 있는 돈"),
    "grdp":     ("소득", "—", "지역 경제 규모"),
    "grdp_pc":  ("소득", "—", "1인당 지역 소득"),
    "khai":     ("수요·금융", "—", "구입부담 — 높을수록 수요 위축"),
    "khoi":     ("수요·금융", "—", "중위소득이 살 수 있는 주택 비중"),
}
GROUP_ORDER = ["공급", "수요·금융", "심리", "가격", "거시", "소득"]


def mstd(xs):
    n = len(xs)
    mu = sum(xs) / n
    return mu, math.sqrt(sum((x - mu) ** 2 for x in xs) / n)


def mask_y(Y, h, upto):
    """백테스트 정직성: i+h 가 upto 를 넘는 목표값은 그 시점엔 관측 불가 — None 처리."""
    if upto is None:
        return Y
    return [Y[i] if (Y[i] is not None and i + h <= upto) else None for i in range(len(Y))]


def scan(feat, Ymasks, keys, t_last, upto, h):
    """지평 h 의 출전표: [(k, lag, r, z, mu, sd)] — 시차·r·현재 z 값.
    r 은 h개월 누적 로그변화율(목표 그 자체)과의 상관 — 시차는 [h, MAXLAG]."""
    cut = (upto if upto is not None else t_last) + 1
    Y = Ymasks[h]
    rows = []
    for k in keys:
        x = feat[k]
        bl, bc = h, 0.0
        for L in range(h, MAXLAG + 1):
            xs = [None] * L + x[:cut - L] if L else x[:cut]
            c, _ = R.corr(xs, Y[:cut])
            if abs(c) > abs(bc):
                bl, bc = L, c
        if bc == 0.0:
            continue
        j = t_last - (bl - h)
        v = x[j] if 0 <= j < len(x) else None
        if v is None:
            continue
        xv = [q for q in x[:cut] if q is not None]
        if len(xv) < 48:
            continue
        mu, sd = mstd(xv)
        sd = sd or 1.0
        z = max(-3.0, min(3.0, (v - mu) / sd))
        rows.append((k, bl, bc, z))
    return rows


def shift_arr(a, L, cut):
    return ([None] * L + a[:cut - L]) if L else a[:cut]


def group_budgets(gz, Y, cut, h):
    """(2026-08-26 · V2 그룹예산) 그룹 합성계열의 지평별 최적시차 상관 = 그룹 발언 예산.

    지표별 |r| 비례만 쓰면 같은 얘기를 하는 지표가 많은 그룹이 머릿수만큼 발언권을
    가져간다(사용자 지적). 4파전 백테스트(서울·전국·경기)에서 성적은 사실상 동률
    (V2 서울 11.62→11.51% 소폭 우세)이라, 구조적 정당성으로 V2 를 채택:
    그룹 총 발언권 = |그룹 합성 r_h| 비례 (머릿수 아닌 정보량 기준),
    그룹 안에서는 |r_h| 비례로 나눈다. 시차는 그룹 합성계열로 [h, MAXLAG] 재탐색."""
    out = {}
    for g, a in gz.items():
        best = 0.0
        for L in range(h, MAXLAG + 1):
            c, _ = R.corr(shift_arr(a, L, cut), Y[:cut])
            if abs(c) > abs(best):
                best = c
        if best:
            out[g] = abs(best)
    return out


def comp_pred(rows, ym, ysd, keyset=None, grp=None, bud=None):
    """합성 예측: ŷ = ȳ + sd_y·Σ w·r·z.
    grp·bud 가 있으면 V2 그룹예산(그룹 합성 r 비례 × 그룹 내 |r| 비례),
    없으면 순수 |r| 비례. 반환: (ŷ, cont{k}, unit{k}=w·r·sd_y — 시나리오 ±1σ 용)."""
    rr = [r for r in rows if keyset is None or r[0] in keyset]
    if not rr:
        return None, {}, {}
    w = {}
    if grp and bud is not None:
        from collections import defaultdict
        G = defaultdict(list)
        for r0 in rr:
            G[grp.get(r0[0], "기타")].append(r0)
        bud2 = {g: (bud.get(g) or max(abs(c) for _, _, c, _ in mem)) for g, mem in G.items()}
        tb = sum(bud2.values()) or 1.0
        for g, mem in G.items():
            wg = sum(abs(c) for _, _, c, _ in mem) or 1.0
            for k, L, c, z in mem:
                w[k] = (abs(c) / wg) * (bud2[g] / tb)
    else:
        wsum = sum(abs(c) for _, _, c, _ in rr) or 1.0
        for k, L, c, z in rr:
            w[k] = abs(c) / wsum
    cont = {k: w[k] * c * z * ysd for k, L, c, z in rr}
    unit = {k: w[k] * c * ysd for k, L, c, z in rr}
    return ym + sum(cont.values()), cont, unit


# ══════════ (2026-08-26) 릿지 엔진 — 사용자 확정 ══════════
# 3파전 실측(V2 그룹예산 vs 데이터 클러스터 vs 릿지 · 39지표·48시점·지평 7개):
#   릿지가 전 지역·전 지평 압승 — 서울 2.34%/91.7% vs V2 10.12%/69.6% vs C50 9.51%/70.2%.
#   V2·클러스터는 오차 기준으로 단순예측을 거의 못 이겼다(방향만 우위).
#   → 예측 엔진을 릿지로 전환. 시차 탐색은 relead 와 같이 전년비(ytr) 기준 —
#     표의 시차·r 열(scan, 목표 기준)은 진단용으로 유지하되 엔진과 기준이 다름을 문서화.
#     기여도 분해(cont=β·z, unit=β)로 화면의 가중치 배수·±1σ 시나리오 조절을 그대로 지원한다.
def ridge_h(feat, prices, ytr, keys, h, t_last, lam, upto=None):
    """지평 h 릿지 예측 — 3파전에서 검증된 구성 그대로(시차 탐색은 relead 와 같이
    전년비(ytr) 기준. 처음에 표와 맞추려 목표(step) 기준 시차를 썼더니 장지평에서
    시차 재선택이 널뛰며 26M -40% ↔ 27M +49% 점프가 났다 — 실측 2026-08-26).
    반환: {g, ym, cont{k}=β·z(현재 기여), beta{k}(±1σ 시나리오용)} 또는 None."""
    cut = (upto if upto is not None else t_last) + 1
    lags = {}
    for k in keys:
        L, c = R.best_lag_ge(feat[k][:cut], ytr[:cut], h)
        lags[k] = {"lag": L, "corr": c}
    sel = [k for k in keys
           if 0 <= t_last - (lags[k]["lag"] - h) < len(feat[k])
           and feat[k][t_last - (lags[k]["lag"] - h)] is not None]
    if not sel:
        return None
    X, Y, use = R.build_xy(feat, R.step_log(prices, h), h, lags, sel,
                           upto=(upto if upto is not None else t_last), force=sel)
    while len(X) < 60 and len(sel) > 3:
        sel.remove(min(sel, key=lambda k: sum(1 for v in feat[k] if v is not None)))
        X, Y, use = R.build_xy(feat, R.step_log(prices, h), h, lags, sel,
                               upto=(upto if upto is not None else t_last), force=sel)
    if len(X) < 36:
        return None
    m = R.ridge_fit(X, Y, lam=lam)
    if not m:
        return None
    row = [feat[k][t_last - (lags[k]["lag"] - h)] for k in use]
    g = R.ridge_pred(m, row)
    cont = {k: m["beta"][j] * (row[j] - m["mu"][j]) / m["sd"][j] for j, k in enumerate(use)}
    beta = {k: m["beta"][j] for j, k in enumerate(use)}
    return {"g": g, "ym": m["ym"], "cont": cont, "beta": beta}


def bt_ridge(feat, prices, ytr, keys, lam, origins=BT_ORIGINS):
    """릿지 워크포워드 백테스트 — backtest_multi 와 같은 통계(mape·sd·naive·calib·hit)."""
    n = len(prices)
    res = {h: {"e": [], "ne": [], "pr": [], "hit": [0, 0]} for h in range(1, HZ + 1)}
    for o in range(n - HZ - origins, n - HZ):
        if o < 60 or prices[o] is None:
            continue
        for h in range(1, HZ + 1):
            act = prices[o + h] if o + h < n else None
            if act is None or act <= 0:
                continue
            r2 = ridge_h(feat, prices, ytr, keys, h, o, lam, upto=o)
            if not r2:
                continue
            p = prices[o] * math.exp(max(-1.2, min(1.2, r2["g"])))
            b = res[h]
            b["e"].append(abs(p - act) / act)
            b["ne"].append(abs(prices[o] - act) / act)
            b["pr"].append((math.log(p / prices[o]), math.log(act / prices[o])))
            b["hit"][0] += 1
            b["hit"][1] += 1 if (p > prices[o]) == (act > prices[o]) else 0
    by_h = {}
    for h in range(1, HZ + 1):
        b = res[h]
        if not b["e"]:
            continue
        mape = sum(b["e"]) / len(b["e"])
        sd = math.sqrt(sum((x - mape) ** 2 for x in b["e"]) / len(b["e"])) if len(b["e"]) > 1 else 0.0
        nv = sum(b["ne"]) / len(b["ne"]) if b["ne"] else None
        calib = 0.0
        pr = b["pr"]
        if len(pr) >= 12:
            mx = sum(a for a, _ in pr) / len(pr)
            my = sum(y for _, y in pr) / len(pr)
            vxx = sum((a - mx) ** 2 for a, _ in pr)
            cxy = sum((a - mx) * (y - my) for a, y in pr)
            if vxx > 1e-12:
                calib = max(0.0, min(1.5, cxy / vxx))
        by_h[h] = {"mape": round(mape * 100, 2), "sd": round(sd * 100, 2),
                   "naive": round(nv * 100, 2) if nv else None,
                   "skill": round(max(0.0, min(1.0, 1 - mape / nv)), 3) if nv else 0.0,
                   "calib": round(calib, 3), "n": len(b["e"]),
                   "hit": round(100 * b["hit"][1] / b["hit"][0], 1) if b["hit"][0] else None}
    alle = [x for h in res for x in res[h]["e"]]
    allh = [res[h]["hit"] for h in res if res[h]["hit"][0]]
    return {"by_h": by_h,
            "mape": round(100 * sum(alle) / len(alle), 2) if alle else None,
            "hit": round(100 * sum(a[1] for a in allh) / sum(a[0] for a in allh), 1) if allh else None,
            "n": len(alle), "origins": origins}


def ystats(prices, h, upto):
    Y = R.step_log(prices, h)
    lim = (upto + 1 - h) if upto is not None else len(Y)
    yv = [Y[i] for i in range(max(0, lim)) if Y[i] is not None]
    if len(yv) < 60:
        return None, None, None
    ym, ysd = mstd(yv)
    return Y, ym, ysd


def backtest_multi(feat, prices, keys, keysets, origins=BT_ORIGINS, grp=None, gz=None):
    """여러 지표집합을 한 번의 워크포워드로 채점 — 시차 탐색(scan)은 합집합에 1회.
    grp·gz 를 주면 V2 그룹예산 가중(본 모델과 동일 규칙으로 채점)."""
    n = len(prices)
    res = {name: {h: {"e": [], "ne": [], "pr": [], "hit": [0, 0]} for h in range(1, HZ + 1)}
           for name in keysets}
    for o in range(n - HZ - origins, n - HZ):
        if o < 60 or prices[o] is None:
            continue
        Ymasks, yms, ysds = {}, {}, {}
        ok = True
        for h in range(1, HZ + 1):
            Y, ym, ysd = ystats(prices, h, o)
            if Y is None:
                ok = False
                break
            Ymasks[h], yms[h], ysds[h] = mask_y(Y, h, o), ym, ysd
        if not ok:
            continue
        for h in range(1, HZ + 1):
            act = prices[o + h] if o + h < n else None
            if act is None or act <= 0:
                continue
            rows = scan(feat, Ymasks, keys, o, o, h)
            bud = group_budgets(gz, Ymasks[h], o + 1, h) if (grp and gz) else None
            for name, ks in keysets.items():
                g, _, _ = comp_pred(rows, yms[h], ysds[h], ks, grp=grp, bud=bud)
                if g is None:
                    continue
                p = prices[o] * math.exp(g)
                b = res[name][h]
                b["e"].append(abs(p - act) / act)
                b["ne"].append(abs(prices[o] - act) / act)
                b["pr"].append((math.log(p / prices[o]), math.log(act / prices[o])))
                b["hit"][0] += 1
                b["hit"][1] += 1 if (p > prices[o]) == (act > prices[o]) else 0
    out = {}
    for name in keysets:
        by_h = {}
        for h in range(1, HZ + 1):
            b = res[name][h]
            if not b["e"]:
                continue
            mape = sum(b["e"]) / len(b["e"])
            sd = math.sqrt(sum((x - mape) ** 2 for x in b["e"]) / len(b["e"])) if len(b["e"]) > 1 else 0.0
            nv = sum(b["ne"]) / len(b["ne"]) if b["ne"] else None
            calib = 0.0
            pr = b["pr"]
            if len(pr) >= 12:
                mx = sum(a for a, _ in pr) / len(pr)
                my = sum(y for _, y in pr) / len(pr)
                vxx = sum((a - mx) ** 2 for a, _ in pr)
                cxy = sum((a - mx) * (y - my) for a, y in pr)
                if vxx > 1e-12:
                    calib = max(0.0, min(1.5, cxy / vxx))
            by_h[h] = {"mape": round(mape * 100, 2), "sd": round(sd * 100, 2),
                       "naive": round(nv * 100, 2) if nv else None,
                       "skill": round(max(0.0, min(1.0, 1 - mape / nv)), 3) if nv else 0.0,
                       "calib": round(calib, 3), "n": len(b["e"]),
                       "hit": round(100 * b["hit"][1] / b["hit"][0], 1) if b["hit"][0] else None}
        alle = [x for h in res[name] for x in res[name][h]["e"]]
        allh = [res[name][h]["hit"] for h in res[name] if res[name][h]["hit"][0]]
        out[name] = {"by_h": by_h,
                     "mape": round(100 * sum(alle) / len(alle), 2) if alle else None,
                     "hit": round(100 * sum(a[1] for a in allh) / sum(a[0] for a in allh), 1) if allh else None,
                     "n": len(alle), "origins": origins}
    return out


def zscore(seq):
    v = [x for x in seq if x is not None]
    if len(v) < 24:
        return [None] * len(seq)
    mu, sd = mstd(v)
    sd = sd or 1.0
    return [None if x is None else (x - mu) / sd for x in seq]


def group_z(feat, keys, meta):
    """그룹별 합성계열 — 멤버(변환 후)의 z-점수 평균. 그룹예산의 재료."""
    from collections import defaultdict
    G = defaultdict(list)
    for k in keys:
        G[meta[k]["group"]].append(k)
    gz = {}
    for g, mem in G.items():
        zs_ = [z for z in (zscore(feat[k]) for k in mem) if z and any(v is not None for v in z)]
        if not zs_:
            continue
        n = len(zs_[0])
        gz[g] = [(sum(z[i] for z in zs_ if z[i] is not None) /
                  max(1, sum(1 for z in zs_ if z[i] is not None)))
                 if any(z[i] is not None for z in zs_) else None for i in range(n)]
    return gz


def main():
    rl = json.loads((DB / "relead.json").read_text(encoding="utf-8"))
    T = rl["t"]
    GL = set(R.GLOBAL_KEYS) | {"cons"}

    # ── 신규 지표 수집·합류 ──
    extra = {}
    try:
        ah = json.loads((DB / "applyhome.json").read_text(encoding="utf-8"))
        at, ser = ah["t"], ah.get("series") or {}
        extra["subs"] = {reg: {at[i]: v for i, v in enumerate(arr) if v is not None}
                         for reg, arr in ser.items() if isinstance(arr, list)}
        print(f"  subs 청약경쟁률: 지역 {len(extra['subs'])} · {at[0]}~{at[-1]}")
    except Exception as e:
        print("  ⚠ applyhome 합류 실패:", str(e)[:80])
    try:
        mp = R.ecos("901Y020", "I42A", s="199001", scale=1e-6)   # 백만원→조원
        extra["cons"] = {"전국": mp}
        ks = sorted(mp)
        print(f"  cons 건설수주액: {len(mp)}개월 {ks[0]}~{ks[-1]}")
    except Exception as e:
        print("  ⚠ 건설수주액 실패:", str(e)[:80])
    try:
        # 전월세전환율 — 신표 DT_30404_N0010 (구표 DT_KAB_11671_N06 은 폐기·빈 응답, 실측 2026-08-23)
        #   아파트 유형(C1_NM 필터) · 2011.01~ · err31(40,000셀) 회피 위해 4년 조각
        mp = R.kosis_monthly("408", "DT_30404_N0010", "ALL",
                             fixed={"objL1": "ALL", "objL2": "ALL"},
                             flt={"C1_NM": "아파트"}, y0="201101", chunk=4)
        if mp:
            extra["j2m"] = mp
            print(f"  j2m 전월세전환율: 지역 {len(mp)} · 전국 {len(mp.get('전국') or {})}개월")
    except Exception as e:
        print("  ⚠ 전월세전환율 실패:", str(e)[:80])

    def series(k, reg):
        if k in extra:
            src = extra[k]
            mp = src.get("전국" if k == "cons" else reg) or src.get("전국") or {}
            return [mp.get(t) for t in T]
        src = rl["d"].get(k) or {}
        return src.get("전국" if k in GL else reg) or src.get("전국")

    base_keys = [k for k in rl["meta"]]
    new_keys = [k for k in ("subs", "cons", "j2m") if k in extra]
    meta = {}
    for k in base_keys:
        m = dict(rl["meta"][k])
        g, folk, hint = ART.get(k, (m.get("group") or "기타", "—", m.get("note") or ""))
        m.update({"group": g, "folk": folk, "hint": hint})
        meta[k] = m
    if "subs" in new_keys:
        meta["subs"] = {"label": "청약 경쟁률", "unit": "배", "group": "심리", "folk": "1~3M",
                        "hint": ART["subs"][2], "src": "청약홈(자체 집계)", "cycle": "M"}
    if "cons" in new_keys:
        meta["cons"] = {"label": "건설수주액", "unit": "조원", "group": "공급", "folk": "3~6M",
                        "hint": ART["cons"][2], "src": "한국은행 ECOS 901Y020", "cycle": "M"}
    if "j2m" in new_keys:
        meta["j2m"] = {"label": "전월세전환율", "unit": "%", "group": "수요·금융", "folk": "—",
                       "hint": ART["j2m"][2], "src": "한국부동산원 KOSIS DT_30404_N0010 (아파트)",
                       "cycle": "M"}

    # ── --judge: 신규 지표 편입 판정 ──
    if JUDGE:
        for reg in ("서울", "전국", "경기"):
            prices = rl["price"][reg]["ma"]
            feat = {}
            for k in base_keys + new_keys:
                a = series(k, reg)
                if not a:
                    continue
                f = R.transform(k, a)
                if sum(1 for v in f if v is not None) >= 36:
                    feat[k] = f
            ks_all = list(feat)
            sets = {"기본": set(k for k in ks_all if k not in ("subs", "cons")),
                    "+청약": set(k for k in ks_all if k != "cons"),
                    "+수주": set(k for k in ks_all if k != "subs"),
                    "+둘다": set(ks_all)}
            bt = backtest_multi(feat, prices, ks_all, sets)
            line = " | ".join(f"{nm} {v['mape']}%/{v['hit']}%" for nm, v in bt.items())
            print(f"  [{reg}] {line}", flush=True)
        return 0

    # ── 본 계산: 18개 시도 ──
    out_pred, out_price, out_lead = {}, {}, {}
    for reg in R.SIDO:
        prices = (rl["price"].get(reg) or {}).get("ma")
        if not prices:
            continue
        feat, keys = {}, []
        for k in base_keys + new_keys:
            a = series(k, reg)
            if not a:
                continue
            f = R.transform(k, a)
            if sum(1 for v in f if v is not None) < 36:
                continue
            feat[k] = f
            keys.append(k)
        t_last = max(i for i, v in enumerate(prices) if v is not None)
        ytr = R.yoy_log(prices)

        # 표시용 lead: 전구간 최적(진단) + 지평별 시차·r
        lead = {}
        for k in keys:
            L, c, n = R.best_lag(feat[k], ytr)
            lead[k] = {"lag": L, "corr": round(c, 3), "n": n}
        Ymasks, yms, ysds = {}, {}, {}
        for h in range(1, HZ + 1):
            Y, ym, ysd = ystats(prices, h, None)
            if Y is None:
                continue
            Ymasks[h], yms[h], ysds[h] = Y, ym, ysd
        rows_h = {h: scan(feat, Ymasks, keys, t_last, None, h) for h in Ymasks}
        for h in DISP_H:
            for (k, L, c, z) in rows_h.get(h, []):
                lead[k][f"lag{h}"], lead[k][f"r{h}"] = L, round(c, 3)
        # (2026-08-26 · 릿지 전환) 표시용 w12 = |12M r|/Σ|12M r| (pf 와 동일 — 진단용 표시).
        #   실제 예측 영향은 릿지 β·기여도(cont)가 담당한다.
        r12map = {k: c for k, L, c, z in rows_h.get(12, [])}
        r12s = sum(abs(c) for c in r12map.values()) or 1.0
        for k in keys:
            lead[k]["w12"] = round(abs(r12map.get(k, 0.0)) / r12s, 4)
        lam = (rl["pred"].get(reg) or {}).get("lam") or 1.0   # relead 지역별 λ 재사용

        # 그룹 합성 r (표시용)
        groups = []
        for g in GROUP_ORDER:
            mem = [k for k in keys if meta[k]["group"] == g]
            if len(mem) < 2:
                continue
            zs = [zscore(feat[k]) for k in mem]
            compz = [None] * len(T)
            for i in range(len(T)):
                vv = [zz[i] for zz in zs if zz[i] is not None]
                if len(vv) >= max(2, len(mem) // 2):
                    compz[i] = sum(vv) / len(vv)
            L, c, n = R.best_lag(compz, ytr)
            if n:
                groups.append({"name": g, "members": mem, "lag": L, "corr": round(c, 3), "n": n})

        # (2026-08-26) 백테스트·예측 모두 릿지 — 3파전 압승으로 사용자 확정
        bt = bt_ridge(feat, prices, ytr, keys, lam)
        pred, g_raw = {}, {}
        for h in sorted(Ymasks):
            r2 = ridge_h(feat, prices, ytr, keys, h, t_last, lam)
            if not r2:
                continue
            calib = (bt["by_h"].get(h) or {}).get("calib", 0.0) or 0.0
            g_raw[h] = (max(-1.2, min(1.2, r2["g"])), r2["cont"], calib, r2["beta"], r2["ym"])
        gs, guard = {}, {}
        for h in sorted(g_raw):
            # (2026-08-23) calib 곱하지 않음 — 선택/평가 분리 실측에서 raw 가 전 지역 최선
            nb = [g_raw[x][0] for x in (h - 1, h, h + 1) if x in g_raw]
            v = sum(nb) / len(nb)
            hist = sorted(math.log(prices[j + h] / prices[j]) for j in range(len(prices) - h)
                          if prices[j] and prices[j + h])
            glo = ghi = None
            if len(hist) >= 40:
                glo, ghi = hist[int(len(hist) * 0.05)], hist[int(len(hist) * 0.95)]
                if v < glo or v > ghi:
                    guard[h] = True
                v = max(glo, min(ghi, v))
            gs[h] = (v, glo, ghi)
        z128 = 1.2816
        ext = [R.add_months(T[t_last], i + 1) for i in range(HZ)]
        fut = {"price": [None] * HZ, "lo": [None] * HZ, "hi": [None] * HZ}
        base_p = prices[t_last]
        for h in sorted(gs):
            v, glo, ghi = gs[h]
            b = bt["by_h"].get(h) or {}
            sd = (b.get("sd") or b.get("mape") or 0) / 100
            p = base_p * math.exp(v)
            fut["price"][h - 1] = round(p, 1)
            fut["lo"][h - 1] = round(p * math.exp(-z128 * sd), 1)
            fut["hi"][h - 1] = round(p * math.exp(z128 * sd), 1)
            g, cont, calib, beta, ymh = g_raw[h]
            pred[h] = {"g": round(v, 5), "price": round(p, 1),
                       "base": round(ymh, 5), "calib": round(calib, 3),
                       "bsd": round(sd, 4),
                       "gb": [round(glo, 4), round(ghi, 4)] if glo is not None else None,
                       "cont": {k: round(c2, 5) for k, c2 in cont.items() if abs(c2) > 5e-6},
                       "unit": {k: round(u2, 5) for k, u2 in beta.items()}}
        out_pred[reg] = {"past": t_last, "ext": ext, "fut": fut, "pred": pred,
                         "groups": groups, "bt": bt,
                         "last": {"t": T[t_last], "price": round(base_p, 1)}}
        out_lead[reg] = lead
        out_price[reg] = rl["price"][reg]
        print(f"  {reg:<3} 지표 {len(keys)} · MAPE {bt['mape']}% · 방향 {bt['hit']}%", flush=True)

    OUT.write_text(json.dumps({
        "asof": R.NOW.strftime("%Y-%m-%d %H:%M"),
        "src": "한국부동산원 실거래 중위가 + 선행지표 38종 — r-가중 합성(릿지 미사용)",
        "note": ("지평별로 시차≥h 에서 r 최대 시차를 찾고(표와 동일 기준), 표준화 릿지 회귀로 예측 "
                 "(2026-08-26 사용자 확정 — 3파전 실측: 릿지 서울 2.34%/91.7% vs V2 10.12% vs 클러스터 9.51%). "
                 "가중치(12M) 열은 |r| 비례 진단용 표시이고, 실제 영향·조절은 릿지 기여도(β·z) 기준. "
                 "참고용이며 투자권유가 아님."),
        "method": "표준화 릿지: ŷ_h = ȳ + Σ β_k·z_k (시차≥h, λ=relead 지역별) · cont=β·z · unit=β",
        "t": T, "horizon": HZ, "regions": [r for r in R.SIDO if r in out_pred],
        "meta": meta, "group_order": GROUP_ORDER,
        "price": out_price, "pred": out_pred, "lead": out_lead,
        # (2026-08-24) 차트 오버레이용 — 신규 3종만 원계열 동봉(상속 36종은 relead.json 지연 로드)
        "d": {k: {reg: [mp.get(t) for t in T] for reg, mp in extra[k].items()
                  if reg in R.SIDO or reg == "전국"}
              for k in new_keys},
    }, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"  → {OUT} ({OUT.stat().st_size // 1024}KB) · 지역 {len(out_pred)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
