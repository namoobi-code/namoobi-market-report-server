#!/usr/bin/env python3
# lend_borrow.py — KR 전종목 대차잔고 수집 + screener_pool 증분 패치. (2026-07-20)
# 소스: 금융위원회_주식대차정보 getStLendAndBorrItemRank_V2 (기준일자별 전종목 순위)
#   실측: numOfRows=3000 이면 전종목(≈2,769)이 1페이지·1콜에 다 온다 (0.7s).
#   isinCd 필드가 ISIN 이 아니라 '단축코드'(예: 000020) — 풀 행 r["c"] 와 직접 매칭.
# 저장 필드(프론트 표시 규약과 일치):
#   lb  = 대차잔고 '금액'(억원) = lnbBal ÷ 1e8   → 표는 wonF(조/억)로 표시
#   lbs = 대차잔여 '주식수'(주) = lnbRmanStckCnt  → 검증·향후 확장용 원값
#   lbr = 대차잔고비율(%) = lbs ÷ 상장주식수 × 100. 상장주식수 = KRX base LIST_SHRS, 폴백 cap/px.
# 갱신 주기: 기준일 +1영업일 13시 이후 반영 → basDt 를 오늘부터 역순 탐색(totalCount>0).
# 유의: data.go.kr 첫 콜은 SSL 핸드셰이크가 매우 느릴 수 있다 → timeout 40s·재시도 5회.
# 사용:
#   screener_pool.build() 에서 enrich(kr) 호출 (풀 재빌드 시 포함)
#   단독 실행 = 기존 screener_pool DB 증분 패치 (cron 일 1회 16:20, screener_pool 15:52 이후.
#   intraday_kr 가 장중 5분마다 풀을 재저장하므로, 패치는 '수집 완료 후 load→save 즉시'로 레이스 최소화)
import os, sys, json, time, glob, urllib.request, urllib.parse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from datetime import date, timedelta
import ta_screen as T

SVC = "https://apis.data.go.kr/1160100/GetStocLendBorrInfoService_V2/getStLendAndBorrItemRank_V2"

def _key():
    k = os.environ.get("DATA_GO_KR_KEY", "").strip()
    if k: return k
    try:
        for ln in open(os.path.join(T.BASE, "secrets", ".env")):
            ln = ln.strip()
            if ln.startswith("DATA_GO_KR_KEY=") and not ln.startswith("#"):
                return ln.split("=", 1)[1].strip()
    except Exception: pass
    for p in glob.glob("/sessions/*/mnt/*/SECURITY/data.go.kr.txt"):
        try: return open(p).read().strip()
        except Exception: pass
    raise RuntimeError("DATA_GO_KR_KEY 없음 (env 또는 secrets/.env)")

def _call(key, basdt, rows, page, tries=5, timeout=40):
    u = (f"{SVC}?serviceKey={urllib.parse.quote(key)}&resultType=json"
         f"&basDt={basdt}&numOfRows={rows}&pageNo={page}")
    for att in range(tries):
        try:
            j = json.loads(urllib.request.urlopen(u, timeout=timeout).read())
            return ((j.get("response", {}) or {}).get("body", {}) or {})
        except Exception:
            if att == tries - 1: raise
            time.sleep(2 * (att + 1))

def fetch_rank(max_back=10):
    """최신 영업일 대차 전종목 → (basdt, {단축코드: (금액억원, 주식수)})."""
    key = _key(); t = date.today()
    for i in range(max_back):
        d = (t - timedelta(days=i)).strftime("%Y%m%d")
        try: b = _call(key, d, 5, 1)
        except Exception as e:
            print(f"[lend] {d} 조회실패 {repr(e)[:60]}"); continue
        tc = int(b.get("totalCount") or 0)
        if tc <= 0: continue
        out = {}; page = 1
        while len(out) < tc and page <= 10:          # 안전 페이지네이션(실측은 1페이지면 충분)
            bb = _call(key, d, 3000, page)
            items = ((bb.get("items") or {}).get("item")) or []
            if not items: break
            for x in items:
                c = (x.get("isinCd") or "").strip()   # 실측: 단축코드(6자리)
                if len(c) == 12 and c.startswith("KR"): c = c[3:9]   # 혹시 ISIN 이면 변환
                shrs = T.num(x.get("lnbRmanStckCnt"))
                bal = T.num(x.get("lnbBal"))
                if c and shrs is not None:
                    out[c] = (round(bal / 1e8, 1) if bal else None, int(shrs))
            page += 1
        print(f"[lend] basDt {d} totalCount {tc} 수집 {len(out)}")
        return d, out
    return None, {}

def _shr_map():
    """KRX base 캐시(최신 파일) → {단축코드: 상장주식수}."""
    m = {}
    for mkt in ("stk", "ksq"):
        fs = sorted(glob.glob(f"{T.CACHE}/krxbase_{mkt}_*.json"))
        if not fs: continue
        try:
            for b in json.load(open(fs[-1])):
                srt = b.get("ISU_SRT_CD"); shrs = T.num(b.get("LIST_SHRS"))
                if srt and shrs: m[srt] = shrs
        except Exception: pass
    return m

def enrich(kr, rank=None, basdt=None):
    """풀 KR 행에 lb(금액 억원)·lbs(주식수)·lbr(상장주식수 대비 %) 채움 → (basdt, 채운 종목수)."""
    if rank is None: basdt, rank = fetch_rank()
    if not rank:
        print("[lend] 대차 데이터 없음 — skip"); return None, 0
    shr = _shr_map(); n = 0
    for r in kr:
        v = rank.get(r.get("c"))
        if v is None: continue
        bal, lbs = v
        if bal is not None: r["lb"] = bal
        r["lbs"] = lbs
        shrs = shr.get(r["c"])
        if not shrs and r.get("cap") and r.get("px"): shrs = r["cap"] / r["px"]
        if shrs: r["lbr"] = round(lbs / shrs * 100, 2)
        n += 1
    print(f"[lend] lb/lbs/lbr 채움 {n}/{len(kr)} (basDt {basdt})")
    return basdt, n

def main():
    """단독 실행 — 느린 수집을 먼저 끝낸 뒤 DB load→patch→save 를 즉시(레이스 최소화)."""
    basdt, rank = fetch_rank()
    if not rank:
        print("[lend] 수집 실패 — DB 미변경"); return
    db = T.load_db("screener_pool")
    if not db or not db.get("kr"):
        print("[lend] screener_pool DB 없음"); return
    _, n = enrich(db["kr"], rank=rank, basdt=basdt)
    if n:
        db["lend_basdt"] = basdt
        T.save_db("screener_pool", db)
        print(f"[lend] screener_pool 패치 저장 (KR {n}종, basDt {basdt})")

if __name__ == "__main__":
    main()
