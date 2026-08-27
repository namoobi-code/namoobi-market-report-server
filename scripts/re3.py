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

    # ── ② 매매 vs 전세·월세 판단기용 부가 데이터 ──
    out["jsr"] = {k: [round(x,2) if x is not None else None for x in v] for k, v in jsr.items()}
    mtg_v = [x for x in s["mtg"]["v"] if x is not None]
    out["mtg"] = mtg_v[-1] if mtg_v else None                     # 최신 주담대 금리(%)
    out["pred12"] = {}
    try:
        rp = load("repred.json")
        for reg, pv in rp.get("pred", {}).items():
            p12 = pv.get("pred", {}).get("12")
            if p12 and p12.get("g") is not None:
                cal = p12.get("calib", 1) or 1
                out["pred12"][reg] = {"g": round(p12["g"]*cal*100, 1),
                                      "lo": round(p12["gb"][0]*100,1) if p12.get("gb") else None,
                                      "hi": round(p12["gb"][1]*100,1) if p12.get("gb") else None,
                                      "m": (pv.get("last") or {}).get("t")}
    except Exception as e:
        print("pred12 skip:", e)

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

    # ── 시군구(서울 25구·경기 45시군구) 확장 (2026-08-27) ──
    # 가격: releadg.json(시군구 예측용 3M평활 중위가, 억원) · 거래량: apt.sqlite 집계 · 미분양: rehub 시군구
    # 전세가율은 서울 구=서울 프록시, 경기=전국 프록시 상속. 금리·경매·연체율은 전국 공통.
    def build_unit(name, med, trade, unsold, jsr_s):
        """시도 루프와 동일한 규칙으로 cur/hist/bt[name] 을 채운다"""
        score_hist = [None]*N
        for i in range(N):
            items = {
                "trade": sig_of(None if not trade or sum3(trade,i) is None or sum3(trade,i-12) in (None,0)
                                 else (sum3(trade,i)/sum3(trade,i-12)-1)*100, 10, -10),
                "jsr":   sig_of(chg(jsr_s,i,6), 0.5, -0.5) if jsr_s else None,
                "unsold":sig_of(pct(unsold,i,6), 10, -10, invert=True) if unsold else None,
                "rate":  sig_of(chg(rate,i,6), 0.3, -0.3, invert=True),
                "bid":   sig_of(None if avgn(bidr,i,3) is None or avgn(bidr,i,12) is None
                                 else avgn(bidr,i,3)-avgn(bidr,i,12), 2, -2),
                "delq":  sig_of(chg(delq_all,i,6), 0.10, -0.10, invert=True),
            }
            avail = {k:v for k,v in items.items() if v is not None}
            if len(avail) >= 4: score_hist[i] = round(sum(avail.values())/len(avail), 3)
        score_s = [None]*N
        for i in range(2, N):
            vs = [x for x in score_hist[i-2:i+1] if x is not None]
            if len(vs) == 3: score_s[i] = round(sum(vs)/3, 3)
        out["hist"][name] = {"score": score_hist, "score_s": score_s, "med": med}
        i = next((j for j in range(N-1, -1, -1) if score_s[j] is not None), N-1)
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
        sig_now = {
            "trade": sig_of(raw["trade"], 10, -10), "jsr": sig_of(raw["jsr"], 0.5, -0.5),
            "unsold": sig_of(raw["unsold"], 10, -10, invert=True),
            "rate": sig_of(raw["rate"], 0.3, -0.3, invert=True),
            "bid": sig_of(raw["bid"], 2, -2), "delq": sig_of(raw["delq"], 0.10, -0.10, invert=True)}
        cur_items = [{"k":k, "sig":sig_now[k], "val":raw[k], "unit":UNITS[k]} for k in LABELS]
        sbar = score_s[i]
        verdict = None if sbar is None else ("up" if sbar >= 0.25 else ("down" if sbar <= -0.25 else "mid"))
        out["cur"][name] = {"score": sbar, "verdict": verdict, "month": T[i], "items": cur_items}
        out["bt"][name] = {}
        if med:
            for hor in (6, 12, 24):
                bt = {"up":[], "mid":[], "down":[]}
                for j in range(N-hor):
                    sc = score_s[j]
                    if sc is None or med[j] in (None,0) or med[j+hor] is None: continue
                    r = (med[j+hor]/med[j]-1)*100
                    bt["up" if sc >= 0.25 else ("down" if sc <= -0.25 else "mid")].append(r)
                out["bt"][name]["h%d"%hor] = {k: {"n": len(v),
                    "avg": round(sum(v)/len(v),1) if v else None,
                    "win": round(sum(1 for x in v if x>0)/len(v)*100) if v else None}
                    for k,v in bt.items()}

    gu_units = {}
    try:
        import sqlite3
        rg = load("releadg.json"); gt = rg["t"]
        cx = sqlite3.connect("file:%s?mode=ro" % os.path.join(BASE, "apt.sqlite"), uri=True)
        q = cx.execute("SELECT a.sgg, s.ym, SUM(s.n) FROM sale s JOIN apt a ON a.id=s.apt_id "
                       "WHERE substr(a.sgg,1,2) IN ('11','41') GROUP BY a.sgg, s.ym").fetchall()
        cx.close()
        tr_map = {}
        for sgg, ym, n_ in q: tr_map.setdefault(sgg, {})[ym] = n_
        tidx = {m: i for i, m in enumerate(T)}
        def unsold_key(nm):
            if nm.startswith("서울"): return nm                    # '서울 강남구' 그대로
            city = nm.replace("(경기)", "").split()[0]             # '수원 장안구' → '수원'
            if not city.endswith(("시", "군")): city += "시"
            return "경기 " + city
        gu_list = []
        for sgg, nm in sorted(rg["names"].items(), key=lambda x: x[1]):
            pv = rg["price"].get(sgg) or {}
            ma = pv.get("ma") or pv.get("raw")
            if not ma: continue
            med = align(T, gt, ma)
            tr = [None]*N
            for ym, n_ in tr_map.get(sgg, {}).items():
                if ym in tidx: tr[tidx[ym]] = n_
            un = d["unsold"].get(unsold_key(nm))
            jsr_s = jsr["서울"] if nm.startswith("서울") else jsr["전국"]
            name = nm if nm.startswith("서울") else "경기 " + nm.replace("(경기)", "")
            build_unit(name, med, tr, un, jsr_s)
            gu_units[name] = (tr, un)
            gu_list.append(name)
        out["gu_list"] = gu_list
        print("gu:", len(gu_list), "시군구")
    except Exception as e:
        print("gu skip:", e)

    # ── ④ 조정 확률 모델 (2026-08-27) — "12개월 내 실거래 중위가(3M평활) −8% 이상 하락" 로지스틱 ──
    # 순수 파이썬 IRLS(릿지 λ=1) — 서버 시스템 python3 에 numpy 없음(기존 스크립트 관례 유지).
    # 특징 6개(시점 i 정보만): 금리6M·거래량YoY·미분양6M·CSI(전국)·낙찰가율3-12M·전세가율6M(전국)
    # 한계(정직 명시): 표본 내 적합·월별 자기상관·지역 풀링 — 참고치이며 급락 예언이 아님.
    def smooth3(v):
        return [None if i<2 or any(x is None for x in v[i-2:i+1]) else sum(v[i-2:i+1])/3
                for i in range(len(v))]
    def feats_at(reg, i, trade, unsold):
        f = []
        f.append(chg(rate, i, 6))
        f.append(None if not trade or sum3(trade,i) is None or sum3(trade,i-12) in (None,0)
                 else (sum3(trade,i)/sum3(trade,i-12)-1)*100)
        f.append(pct(unsold, i, 6) if unsold else None)
        csi_n = d["csi"]["전국"]; f.append(csi_n[i] if csi_n and i < len(csi_n) else None)
        f.append(None if avgn(bidr,i,3) is None or avgn(bidr,i,12) is None
                 else avgn(bidr,i,3)-avgn(bidr,i,12))
        f.append(chg(jsr.get("전국"), i, 6))
        return f
    FN = ["주담대6M", "거래량YoY", "미분양6M", "CSI", "낙찰가율3-12M", "전세가율6M"]
    rows, tags = [], []          # tags: (reg, i) — hist 재구성용
    med_s_map = {}
    for reg in regions:
        med = d["rt_med"].get(reg)
        if not med: continue
        ms = smooth3(med); med_s_map[reg] = ms
        trade = d["trade"].get(reg) or d["trade"].get("전국")
        unsold = d["unsold"].get(reg) or d["unsold"].get("전국")
        for i in range(N):
            f = feats_at(reg, i, trade, unsold)
            if any(x is None for x in f) or ms[i] in (None, 0): continue
            fut = [ms[i+k] for k in range(1, 13) if i+k < N and ms[i+k] is not None]
            y = None
            if len(fut) >= 10:
                y = 1 if min(x/ms[i]-1 for x in fut) <= -0.08 else 0
            rows.append((f, y)); tags.append((reg, i))
    train = [(f, y) for f, y in rows if y is not None]
    crash = {"note": "타깃: 12M 내 3M평활 중위가 −8% 이상 하락 · 풀링 로지스틱(표본 내) · 참고치",
             "feat": FN, "n": len(train), "events": sum(y for _, y in train)}
    if crash["events"] >= 30:
        K = len(FN)
        mu = [sum(f[k] for f, _ in train)/len(train) for k in range(K)]
        sd = [max((sum((f[k]-mu[k])**2 for f, _ in train)/len(train))**.5, 1e-9) for k in range(K)]
        Z = [[1.0]+[(f[k]-mu[k])/sd[k] for k in range(K)] for f, _ in train]
        Y = [y for _, y in train]
        import math as _m
        b = [0.0]*(K+1)
        def sigm(z): return 1/(1+_m.exp(-max(-30, min(30, z))))
        for _ in range(30):                       # IRLS + 릿지 λ=1(절편 제외)
            P = [sigm(sum(b[j]*z[j] for j in range(K+1))) for z in Z]
            W = [max(p*(1-p), 1e-6) for p in P]
            A = [[sum(W[n_]*Z[n_][a]*Z[n_][c] for n_ in range(len(Z))) + (1.0 if a == c and a > 0 else 0)
                  for c in range(K+1)] for a in range(K+1)]
            g = [sum((Y[n_]-P[n_])*Z[n_][a] for n_ in range(len(Z))) - (b[a] if a > 0 else 0)
                 for a in range(K+1)]
            # 가우스 소거로 A·db = g
            M = [Ar[:]+[g[a]] for a, Ar in enumerate(A)]
            for c in range(K+1):
                piv = max(range(c, K+1), key=lambda r_: abs(M[r_][c])); M[c], M[piv] = M[piv], M[c]
                if abs(M[c][c]) < 1e-12: break
                for r_ in range(K+1):
                    if r_ != c and M[r_][c]:
                        f2 = M[r_][c]/M[c][c]
                        M[r_] = [M[r_][x]-f2*M[c][x] for x in range(K+2)]
            db = [M[a][K+1]/M[a][a] if abs(M[a][a]) > 1e-12 else 0 for a in range(K+1)]
            b = [b[a]+db[a] for a in range(K+1)]
            if max(abs(x) for x in db) < 1e-6: break
        def prob_of(f):
            # (2026-08-27) 결측 1개까지 평균 대체(z=0) 허용 — 낙찰가율 등 늦게 시작하는
            # 지표가 확률 시계열 앞부분을 통째로 잘라먹던 것을 완화 (x축 연장, 사용자 요청)
            miss = sum(1 for x in f if x is None)
            if miss > 1: return None
            z = [1.0]+[0.0 if f[k] is None else (f[k]-mu[k])/sd[k] for k in range(K)]
            return sigm(sum(b[j]*z[j] for j in range(K+1)))
        # 지역별 확률 시계열 + 현재값
        crash["hist"], crash["cur"] = {}, {}
        for reg in regions:
            if reg not in med_s_map: continue
            trade = d["trade"].get(reg) or d["trade"].get("전국")
            unsold = d["unsold"].get(reg) or d["unsold"].get("전국")
            hs = [None]*N
            for i in range(N):
                p = prob_of(feats_at(reg, i, trade, unsold))
                if p is not None: hs[i] = round(p*100, 1)
            crash["hist"][reg] = hs
            li = next((j for j in range(N-1, -1, -1) if hs[j] is not None), None)
            nn = [x for x in hs if x is not None]
            crash["cur"][reg] = {"p": hs[li] if li is not None else None,
                                 "m": T[li] if li is not None else None,
                                 "avg": round(sum(nn)/len(nn), 1) if nn else None}
        # 시군구(서울·경기)도 같은 풀링 모델로 확률 산출 (2026-08-27)
        for name, (tr, un) in gu_units.items():
            hs = [None]*N
            for i in range(N):
                p = prob_of(feats_at(name, i, tr, un))
                if p is not None: hs[i] = round(p*100, 1)
            crash["hist"][name] = hs
            li = next((j for j in range(N-1, -1, -1) if hs[j] is not None), None)
            nn = [x for x in hs if x is not None]
            crash["cur"][name] = {"p": hs[li] if li is not None else None,
                                  "m": T[li] if li is not None else None,
                                  "avg": round(sum(nn)/len(nn), 1) if nn else None}
        # 5분위 리프트(표본 내 정직성 점검): 확률 상위 구간에서 실제 조정이 잦았는가
        pv = sorted(((prob_of(f), y) for f, y in train), key=lambda x: x[0])
        q = len(pv)//5
        crash["lift"] = [{"q": qi+1,
                          "rate": round(sum(y for _, y in pv[qi*q:(qi+1)*q if qi < 4 else len(pv)])
                                        /max(len(pv[qi*q:(qi+1)*q if qi < 4 else len(pv)]), 1)*100)}
                         for qi in range(5)]
        crash["base"] = round(crash["events"]/crash["n"]*100)
    out["crash"] = crash

    dst = os.path.join(BASE, "re3.json")
    with open(dst, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",",":"))
    print("re3.json written:", len(regions), "regions,", N, "months")

if __name__ == "__main__":
    main()
