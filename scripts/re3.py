#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""re3.py — RE3 시장 국면 신호등 (2026-08-27 신설 · RE3 탭 데이터)

목적
  rehub(통합지표)·realestate(ECOS)·hcredit(연체율)에 이미 있는 데이터를 조합해
  "지금 상승/하락 국면인가"를 규칙 기반으로 판정한다. 새 수집은 없다(무토큰).
  사용자 제공 스터디 자료(부동산 시세 예측 방법)의 "시장 사이클 읽기" 구현:
    상승 국면 = 거래량 증가 + 전세가율 상승 + 매물(미분양) 감소 + 금리 안정/하락
    하락 국면 = 거래량 급감 + 미분양 증가 + 금리 급등 (+ 경매 증가·연체율 상승)

6개 신호 (각 +1 상승 / 0 중립 / −1 하락 — 임계값은 코드에 고정, 판정은 그 시점 정보만 사용)
  trade   거래량        : 최근 3M 합 vs 전년동기 3M 합 YoY   ±10%      (지역별)
  jsr     전세가율 방향  : ECOS 전세지수/매매지수 비율 6M 변화 ±0.5%p   (전국·서울만)
  unsold  미분양        : 6M 변화율 ∓10% (감소=상승신호)               (지역별)
  rate    주담대 금리    : 6M 변화 ∓0.3%p (하락=상승신호)              (전국 공통)
  bid     경매 낙찰가율  : 3M 평균 vs 12M 평균 ±2%p                    (전국 공통)
  delq    가계대출 연체율: 은행전체 6M 변화 ∓0.10%p (상승=하락신호)     (전국 공통)

종합: 가용 신호 평균 s̄ (−1..+1). s̄≥+0.25 상승 / s̄≤−0.25 하락 / 그 외 중립.
  가용 신호 4개 미만인 달은 판정 보류(None).

백테스트(정직성 장치): 매월 위 규칙을 소급 적용해 판정하고, 판정 후 12개월
  실거래 중위가(rt_med) 수익률을 국면별로 집계한다. 상승판정>중립>하락판정
  순서가 실제로 나오는지 화면에 그대로 보여준다(안 나오면 규칙이 틀린 것).

출력: data/db/re3.json → /api/db/re3
cron: 매일 08:05 (rehub 07:45 이후)
"""
import json, os, datetime

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "db")

def load(name):
    with open(os.path.join(BASE, name), encoding="utf-8") as f:
        return json.load(f)

def chg(series, i, back):
    """i시점 값 − (i−back)시점 값. 결측이면 None"""
    if i - back < 0: return None
    a, b = series[i], series[i - back]
    if a is None or b is None: return None
    return a - b

def pct(series, i, back):
    if i - back < 0: return None
    a, b = series[i], series[i - back]
    if a is None or b is None or b == 0: return None
    return (a / b - 1) * 100

def sig_of(v, up, dn, invert=False):
    """v가 up 이상 +1, dn 이하 −1 (invert면 부호 반전)"""
    if v is None: return None
    s = 1 if v >= up else (-1 if v <= dn else 0)
    return -s if invert else s

def align(t_master, t_src, v_src):
    """src 시계열(YYYYMM)을 master 시간축으로 재배열"""
    idx = {m: i for i, m in enumerate(t_src)}
    return [v_src[idx[m]] if m in idx else None for m in t_master]

def sum3(series, i):
    """i 포함 직전 3개 합 (하나라도 결측이면 None)"""
    if i < 2: return None
    vs = series[i-2:i+1]
    if any(x is None for x in vs): return None
    return sum(vs)

def avgn(series, i, n):
    if i - n + 1 < 0: return None
    vs = [x for x in series[i-n+1:i+1] if x is not None]
    return sum(vs)/len(vs) if len(vs) >= max(2, n//2) else None

def main():
    hub = load("rehub.json"); re_ = load("realestate.json"); hc = load("hcredit.json")
    T = hub["t"]; N = len(T); d = hub["d"]
    s = re_["series"]

    # ── 전국 공통 신호 시계열 ──
    rate = d["rate_kr"]["전국"]                    # 주담대(rehub이 이미 월간 정렬)
    bidr = d["bid_rate"]["전국"]                   # 낙찰가율
    delq_all = align(T, hc["delq"]["t"], hc["delq"]["s"]["은행전체"]["가계"])  # 가계 연체율(주택 관련성)
    # 전세가율 프록시: ECOS 전세지수/매매지수 (전국·서울)
    jsr = {}
    for reg, sale_k, js_k in [("전국", "sale_apt", "js_apt"), ("서울", "sale_apt_s", "js_apt_s")]:
        sa = align(T, s[sale_k]["t"], s[sale_k]["v"]); jj = align(T, s[js_k]["t"], s[js_k]["v"])
        jsr[reg] = [ (jj[i]/sa[i]*100) if (sa[i] and jj[i]) else None for i in range(N) ]

    # 대상 지역: rt_med·trade 가 있는 시도 단위
    sido = [r for r in hub["regions"] if " " not in r or r == "수도권"]
    regions = [r for r in sido if r in d.get("rt_med", {}) and (r in d.get("trade", {}) or r == "전국")]
    if "전국" in d.get("rt_med", {}) and "전국" not in regions: regions.insert(0, "전국")

    LABELS = {"trade":"거래량 (3M vs 전년동기)", "jsr":"전세가율 방향 (6M)",
              "unsold":"미분양 (6M 변화)", "rate":"주담대 금리 (6M)",
              "bid":"경매 낙찰가율 (3M vs 12M)", "delq":"가계대출 연체율 (6M)"}
    SCOPE  = {"trade":"지역", "jsr":"전국·서울만", "unsold":"지역", "rate":"전국 공통",
              "bid":"전국 공통", "delq":"전국 공통"}

    out = {"asof": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
           "src": "rehub(RTMS·KOSIS·등기광장)+ECOS+hcredit 조합 — 신규 수집 없음",
           "note": "규칙 기반 국면 판정. 참고용이며 투자권유 아님. 임계값은 re3.py에 고정.",
           "t": T, "labels": LABELS, "scope": SCOPE, "regions": regions,
           "cur": {}, "hist": {}, "bt": {}}

    for reg in regions:
        trade = d["trade"].get(reg) or d["trade"].get("전국")
        unsold = d["unsold"].get(reg) or d["unsold"].get("전국")
        med = d["rt_med"].get(reg)
        jsr_s = jsr.get(reg)  # 전국·서울 외 None
        score_hist, sigs_last = [None]*N, None
        for i in range(N):
            items = {
                "trade": sig_of(None if sum3(trade,i) is None or sum3(trade,i-12) in (None,0)
                                 else (sum3(trade,i)/sum3(trade,i-12)-1)*100, 10, -10) if trade else None,
                "jsr":   sig_of(chg(jsr_s,i,6), 0.5, -0.5) if jsr_s else None,
                "unsold":sig_of(pct(unsold,i,6), 10, -10, invert=True) if unsold else None,
                "rate":  sig_of(chg(rate,i,6), 0.3, -0.3, invert=True),
                "bid":   sig_of(None if avgn(bidr,i,3) is None or avgn(bidr,i,12) is None
                                 else avgn(bidr,i,3)-avgn(bidr,i,12), 2, -2),
                "delq":  sig_of(chg(delq_all,i,6), 0.10, -0.10, invert=True),
            }
            avail = {k:v for k,v in items.items() if v is not None}
            if len(avail) >= 4:
                sbar = sum(avail.values())/len(avail)
                score_hist[i] = round(sbar, 3)
        # 3M 평활 (실측: 원지수보다 국면 분리가 깨끗 — 2026-08-27 백테스트)
        score_s = [None]*N
        for i in range(2, N):
            vs = [x for x in score_hist[i-2:i+1] if x is not None]
            if len(vs) == 3: score_s[i] = round(sum(vs)/3, 3)
        out["hist"][reg] = {"score": score_hist, "score_s": score_s, "med": med}

        # 현재 판정 — 발표 시차로 최신월은 결측이 많아, 평활 점수가 있는 마지막 달 기준
        i = next((j for j in range(N-1, -1, -1) if score_s[j] is not None), N-1)
        cur_month = T[i]
        sigs_last = None
        # 해당 시점의 신호 재계산 (위 루프의 i시점 items 재현)
        def items_at(i):
            return {
                "trade": sig_of(None if not trade or sum3(trade,i) is None or sum3(trade,i-12) in (None,0)
                                 else (sum3(trade,i)/sum3(trade,i-12)-1)*100, 10, -10),
                "jsr":   sig_of(chg(jsr_s,i,6), 0.5, -0.5) if jsr_s else None,
                "unsold":sig_of(pct(unsold,i,6), 10, -10, invert=True) if unsold else None,
                "rate":  sig_of(chg(rate,i,6), 0.3, -0.3, invert=True),
                "bid":   sig_of(None if avgn(bidr,i,3) is None or avgn(bidr,i,12) is None
                                 else avgn(bidr,i,3)-avgn(bidr,i,12), 2, -2),
                "delq":  sig_of(chg(delq_all,i,6), 0.10, -0.10, invert=True),
            }
        sigs_last = items_at(i)
        cur_items = []
        raw = {
            "trade": None if not trade or sum3(trade,i) is None or sum3(trade,i-12) in (None,0)
                     else round((sum3(trade,i)/sum3(trade,i-12)-1)*100,1),
            "jsr":   round(chg(jsr_s,i,6),2) if jsr_s and chg(jsr_s,i,6) is not None else None,
            "unsold":round(pct(unsold,i,6),1) if unsold and pct(unsold,i,6) is not None else None,
            "rate":  round(chg(rate,i,6),2) if chg(rate,i,6) is not None else None,
            "bid":   None if avgn(bidr,i,3) is None or avgn(bidr,i,12) is None
                     else round(avgn(bidr,i,3)-avgn(bidr,i,12),1),
            "delq":  round(chg(delq_all,i,6),3) if chg(delq_all,i,6) is not None else None,
        }
        UNITS = {"trade":"%","jsr":"%p","unsold":"%","rate":"%p","bid":"%p","delq":"%p"}
        for k in LABELS:
            cur_items.append({"k":k, "sig":sigs_last.get(k), "val":raw[k], "unit":UNITS[k]})
        sbar = score_s[i]
        verdict = None if sbar is None else ("up" if sbar >= 0.25 else ("down" if sbar <= -0.25 else "mid"))
        out["cur"][reg] = {"score": sbar, "verdict": verdict, "month": cur_month, "items": cur_items}

        # 백테스트: 평활 점수 판정 → 6/12/24M 뒤 중위가 수익률 (지평별로 성격이 다름 — 실측:
        #   6M은 국면 순서대로 갈리고, 24M은 하락판정 뒤가 최고 = 바닥 신호)
        out["bt"][reg] = {}
        if med:
            for hor in (6, 12, 24):
                bt = {"up":[], "mid":[], "down":[]}
                for j in range(N-hor):
                    sc = score_s[j]
                    if sc is None or med[j] in (None,0) or med[j+hor] is None: continue
                    r = (med[j+hor]/med[j]-1)*100
                    bt["up" if sc >= 0.25 else ("down" if sc <= -0.25 else "mid")].append(r)
                out["bt"][reg]["h%d"%hor] = {k: {"n": len(v),
                    "avg": round(sum(v)/len(v),1) if v else None,
                    "win": round(sum(1 for x in v if x>0)/len(v)*100) if v else None}
                    for k,v in bt.items()}

    dst = os.path.join(BASE, "re3.json")
    with open(dst, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",",":"))
    print("re3.json written:", len(regions), "regions,", N, "months")

if __name__ == "__main__":
    main()
