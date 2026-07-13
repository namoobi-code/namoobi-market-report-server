#!/usr/bin/env python3
"""[5단계] 성과 추적 — 무-LLM. 서버 cron 이 매일 돌린다.

ta_calls.json(판정 이력) 의 각 회차에 대해:
  · 판정 시점 가격(px_snapshot) 대비 현재가 수익률
  · 같은 기간 벤치마크(KOSPI ^KS11 / SPY) 수익률
  · α = 종목수익률 − 벤치마크수익률
을 계산하고, 판정군(채택/관망/탈락)·심사결과(승인/반려)별로 집계한다.

★ 탈락 종목도 반드시 추적한다 — 채택만 보면 생존편향에 빠져
  "우리 필터가 좋다"는 착각을 검증할 수 없다. 채택군 α 가 탈락군 α 보다
  유의하게 높아야 비로소 스크리닝이 작동한다는 증거가 된다.

출력: data/db/ta_perf.json
"""
import json, os, re, sys, ssl, time, urllib.request
from datetime import datetime, timezone, timedelta

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB   = os.path.join(BASE, "data", "db")
KST  = timezone(timedelta(hours=9))
CTX  = ssl.create_default_context()
UA   = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120 Safari/537.36"}
CHART = "https://query1.finance.yahoo.com/v8/finance/chart/%s?interval=1d&range=6mo"

BENCH = {"KR": "^KS11", "US": "SPY"}
HORIZONS = [("1주", 7), ("1개월", 30), ("3개월", 91)]


def fetch(sym):
    """[(YYYY-MM-DD, close), ...] · 실패 시 [] · (series, 회사명) 은 fetch2 로."""
    return fetch2(sym)[0]


def fetch2(sym):
    """(series, 회사명) — 회사명은 티커 검증용.

    ⚠️ Yahoo 는 한국 종목에 잘못된 접미사를 줘도 에러 대신 '엉뚱한 데이터'를 반환한다.
       006910.KS → 3,475원 (딴 종목) · 000660.KQ → 딴 종목
       그런데 **잘못된 접미사는 회사명 자리에 '코드,코드,코드' 쓰레기 문자열**을 넣는다:
         000660.KS → "SK hynix Inc."                      ← 정상
         000660.KQ → "000660.KQ,0P0000AZ1B,4519170"        ← 쓰레기 = 틀린 티커
       이걸 판별자로 쓴다. 가격 일치만으로는 우연히 통과할 수 있어 불충분하다.
    """
    for attempt in range(3):
        try:
            u = CHART % urllib.request.quote(sym, safe="")
            r = json.loads(urllib.request.urlopen(
                urllib.request.Request(u, headers=UA), timeout=20, context=CTX).read())
            res = r["chart"]["result"][0]
            m = res.get("meta") or {}
            nm = m.get("longName") or m.get("shortName") or ""
            ts = res["timestamp"]
            cl = res["indicators"]["quote"][0]["close"]
            ser = [(datetime.fromtimestamp(t, KST).strftime("%Y-%m-%d"), c)
                   for t, c in zip(ts, cl) if c is not None]
            return ser, nm
        except Exception:
            if attempt == 2:
                return [], ""
            time.sleep(2)
    return [], ""


def _valid_name(nm, sym):
    """회사명이 진짜인가? (틀린 접미사면 '코드,코드,코드' 형태가 온다)"""
    if not nm:
        return False
    return not re.match(r"^\d{6}\.K[SQ],", nm)


def ticker(name, snap):
    code, mkt = snap.get("code"), snap.get("시장")
    if mkt == "US":
        return [code]
    if snap.get("ysym"):                  # 번들이 정확한 심볼을 남겼으면 그대로
        return [snap["ysym"]]
    return [f"{code}.KS", f"{code}.KQ"]   # 둘 다 시도 → 회사명으로 진짜를 고른다


def series(name, snap, cache):
    """티커 검증 2중: ① 회사명이 진짜인가 ② 기준가가 시리즈에 실재하는가."""
    if name in cache:
        return cache[name]
    p0 = snap.get("close")
    for tk in ticker(name, snap):
        ser, nm = fetch2(tk)
        if not ser or not _valid_name(nm, tk):
            continue                       # 쓰레기 회사명 = 틀린 접미사 → 버린다
        if p0 and not any(abs(c - p0) / max(abs(p0), 1e-9) < 0.005 for _, c in ser):
            print(f"[perf] ⚠️ {name}({tk}, {nm}): 기준가 {p0} 가 시리즈에 없다 — 확인 필요")
        cache[name] = ser
        return ser
    print(f"[perf] ⚠️ {name}: 유효한 티커를 찾지 못했다 — 성과 계산 제외")
    cache[name] = []
    return []


def price_date(ser, close):
    """번들 기준가(close)가 실제로 어느 날 종가인지 역추적.
    ⚠️ trade_date 라벨은 KRX 기준일(1영업일 지연)이라 가격일과 다르다 —
       2026-07-13 실행 번들이 trade_date=20260710 인데 가격은 07-13 종가였다.
       라벨을 믿고 시리즈를 조회하면 엉뚱한 기준가로 α 가 통째로 틀어진다."""
    if not ser or close is None:
        return None
    best, bd = None, None
    for d, c in ser:
        e = abs(c - close) / max(abs(close), 1e-9)
        if best is None or e < best:
            best, bd = e, d
    return bd if best is not None and best < 0.005 else None   # 0.5% 이내면 그 날로 확정


def ret_from(ser, d0, days, p0):
    """d0(실제 가격일) + days 경과 시점 수익률. 기준가 p0 는 판정 시 실제로 본 가격."""
    if not ser or not d0 or not p0:
        return None
    base = datetime.strptime(d0, "%Y-%m-%d").date()
    tgt = base + timedelta(days=days)
    if datetime.now(KST).date() < tgt:
        return None                          # 아직 도래 안 함 — 억지로 계산하지 않는다
    p1 = None
    for d, c in ser:
        if d <= tgt.strftime("%Y-%m-%d"):
            p1 = c
    if not p1:
        return None
    return round((p1 / p0 - 1) * 100, 2)


def main():
    p = os.path.join(DB, "ta_calls.json")
    if not os.path.exists(p):
        print("[perf] ta_calls.json 없음 — 판정 이력이 아직 없다"); return 0
    hist = json.load(open(p, encoding="utf-8"))
    calls = hist.get("calls") or []
    if not calls:
        print("[perf] 판정 이력 0건"); return 0

    cache = {}
    bench = {m: fetch(t) for m, t in BENCH.items()}
    for m, s in bench.items():
        print(f"[perf] 벤치마크 {BENCH[m]}: {len(s)}일")

    rows, runs = [], []
    for call in calls:
        d0 = str(call.get("trade_date"))
        px = call.get("px_snapshot") or {}
        appr = {re.sub(r"\s*\(.*?\)\s*$", "", a["종목"]).strip() for a in (call.get("approved") or [])}
        # 리스크 심사에서 반려된 종목
        rej = {re.sub(r"\s*\(.*?\)\s*$", "", a["종목"]).strip()
               for a in ((call.get("risk_review") or {}).get("심사대상") or []) if not a.get("승인")}
        # 토론 에이전트가 종목명 뒤에 티커를 붙이는 경우가 있다("Micron Technology, Inc. (MU)").
        # px_snapshot 키와 어긋나 조용히 누락되므로, 괄호를 떼고 재매칭한다.
        def _norm(x): return re.sub(r"\s*\(.*?\)\s*$", "", str(x or "")).strip()
        px_norm = {_norm(k): v2 for k, v2 in px.items()}
        for v in (call.get("verdicts") or []):
            nm, mkt = v.get("종목"), v.get("시장")
            snap = px.get(nm) or px_norm.get(_norm(nm))
            if not snap:
                print(f"[perf] ⚠️ px_snapshot 매칭 실패: {nm}")
                continue
            nm = _norm(nm)
            ser = series(nm, snap, cache)
            p0 = snap.get("close")
            # 번들이 기록한 price_date 우선(정확). 없으면 기준가로 역추적.
            pd0 = snap.get("price_date") or price_date(ser, p0)
            bser = bench.get(mkt, [])
            b0 = next((c for d, c in bser if d >= (pd0 or "9999")), None)
            cur = ser[-1][1] if ser else None
            r = {"trade_date": d0, "price_date": pd0, "종목": nm, "시장": mkt,
                 "코드": snap.get("code"), "판정": v.get("판정"), "확신도": v.get("확신도"),
                 "심사": "승인" if nm in appr else ("반려" if nm in rej else "미심사"),
                 "기준가": p0, "현재가": cur,
                 "현재수익률": (None if not (cur and p0) else round((cur / p0 - 1) * 100, 2))}
            for lab, dd in HORIZONS:
                sr = ret_from(ser, pd0, dd, p0)
                br = ret_from(bser, pd0, dd, b0)
                r[f"{lab}_수익률"] = sr
                r[f"{lab}_벤치"] = br
                r[f"{lab}_알파"] = (None if sr is None or br is None else round(sr - br, 2))
            rows.append(r)
        runs.append({"trade_date": d0, "as_of": call.get("as_of"),
                     "종목수": len([v for v in (call.get("verdicts") or []) if px.get(v.get("종목"))]),
                     "승인": sorted(appr)})

    # ══════════════════════════════════════════════════════════════════
    #  집계 — 중복 가중 문제를 2단 평균으로 처리한다.
    #
    #  같은 종목이 매일 채택되면 콜(call) 단위 평균은 그 한 종목이 표본을 지배해
    #  "채택군 성적"이 아니라 "그 종목 성적"이 되어버린다. 또 같은 종목의 연속
    #  판정은 서로 독립이 아니므로(어제 오른 종목은 오늘도 오를 확률이 높다)
    #  n=30 을 독립 표본 30개처럼 읽으면 안 된다 — 실질 독립 표본은 종목 수에 가깝다.
    #
    #  그래서 두 가지를 나란히 낸다:
    #    · 콜 단위  = 판정 1건 = 표본 1개 (신호를 낼 때마다의 기대 성과)
    #    · 종목 단위 = 종목별로 먼저 평균 → 종목 간 평균 (중복 가중 제거)
    #  둘이 크게 벌어지면 "소수 종목이 반복 등장해 성적을 끌고 있다"는 진단이 된다.
    # ══════════════════════════════════════════════════════════════════
    def agg(sel, label):
        g = [r for r in rows if sel(r)]
        uniq = sorted({r["종목"] for r in g})
        out = {"구분": label, "콜수": len(g), "고유종목수": len(uniq)}
        for lab, _ in HORIZONS:
            a = [r[f"{lab}_알파"] for r in g if r[f"{lab}_알파"] is not None]
            # ── 콜 단위 (평평한 평균) ──
            out[f"{lab}_평균알파"] = round(sum(a) / len(a), 2) if a else None
            out[f"{lab}_적중률"] = (round(100 * sum(1 for x in a if x > 0) / len(a), 1) if a else None)
            out[f"{lab}_n"] = len(a)
            # ── 종목 단위 (종목별 평균 → 종목 간 평균) ──
            per = {}
            for r in g:
                v = r[f"{lab}_알파"]
                if v is not None:
                    per.setdefault(r["종목"], []).append(v)
            pm = [sum(v) / len(v) for v in per.values()]
            out[f"{lab}_종목평균알파"] = round(sum(pm) / len(pm), 2) if pm else None
            out[f"{lab}_종목적중률"] = (round(100 * sum(1 for x in pm if x > 0) / len(pm), 1) if pm else None)
            out[f"{lab}_종목n"] = len(pm)
        return out

    # 같은 종목이 몇 번 등장했는지 (반복 판정 카운트) — 행에 표시해 중복을 눈에 보이게 한다
    from collections import Counter
    cnt = Counter(r["종목"] for r in rows)
    for r in rows:
        r["반복판정"] = cnt[r["종목"]]

    summary = [
        agg(lambda r: r["심사"] == "승인", "★ 최종 승인"),
        agg(lambda r: r["판정"] == "채택", "채택"),
        agg(lambda r: r["판정"] == "관망", "관망"),
        agg(lambda r: r["판정"] == "탈락", "탈락 (대조군)"),
        agg(lambda r: True, "전체 후보"),
    ]

    # 중복 진단 — 반복 등장 상위 종목 (표본을 지배하고 있는지 확인)
    dup = [{"종목": k, "등장횟수": v} for k, v in cnt.most_common(10) if v > 1]

    out = {"as_of": datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S"),
           "benchmark": BENCH, "horizons": [h[0] for h in HORIZONS],
           "runs": runs, "rows": rows, "summary": summary,
           "중복진단": {"총콜수": len(rows), "고유종목수": len(cnt), "반복등장": dup},
           "note": ("α = 종목수익률 − 벤치마크수익률(KOSPI/SPY). 경과일이 안 된 구간은 null. "
                    "탈락군을 대조군으로 함께 추적한다 — 채택군 α 가 탈락군 α 보다 유의하게 "
                    "높아야 스크리닝이 작동한다는 증거가 된다(생존편향 방지)."),
           "note_dup": ("같은 종목이 여러 날 판정되면 콜 단위 평균은 그 종목이 표본을 지배한다. "
                        "'종목 단위'는 종목별로 먼저 평균을 낸 뒤 종목 간 평균을 내 중복 가중을 제거한 값이다. "
                        "콜 단위와 종목 단위가 크게 벌어지면 소수 종목이 성적을 끌고 있다는 뜻이다. "
                        "또 같은 종목의 연속 판정은 서로 독립이 아니므로 n 을 독립 표본 수로 읽지 말 것 — "
                        "실질 독립 표본은 고유종목수에 가깝다.")}
    # ta_stage*.json 과 동일하게 raw 로 저장한다 (/api/db 가 파일을 그대로 서빙 —
    # nmr_db 래퍼({marker,as_of,data})로 감싸면 대시보드가 한 겹 더 벗겨야 한다)
    tmp = os.path.join(DB, "ta_perf.json.tmp")
    json.dump(out, open(tmp, "w", encoding="utf-8"), ensure_ascii=False)
    os.replace(tmp, os.path.join(DB, "ta_perf.json"))
    done = sum(1 for r in rows if r["1주_알파"] is not None)
    print(f"[perf] ok: {len(runs)}회차 · 콜 {len(rows)}건 / 고유 {len(cnt)}종목 · "
          f"1주 경과 {done}건 · 반복등장 {len(dup)}종목 → db/ta_perf.json")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"[perf] ⚠️ 예외(비차단): {e}"); sys.exit(0)
