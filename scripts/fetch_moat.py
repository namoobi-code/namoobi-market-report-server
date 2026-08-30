#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fetch_moat.py — 해자 워치(Moat Watch) 수집 (2026-08-30 신설)

부록 해자지도(D·F·H)의 파란 배지(독점·준독점) 상장 종목에 대해
"일시적 빠짐 vs 이유 있는 하락"을 구분하는 3층 신호를 매일 산출한다.
  ① 가격 신호: 52주 고점 대비 낙폭 · 200일선 이격도 · RSI(14) · 기간 수익률
  ② 해자 선행지표: 종목별 연결 지표(우라늄 실물신탁·은 선물·SOX·XBI·MU 등, 야후)의 3개월 방향
  ③ 판정 신호등:
     ⚪ top   낙폭 > -10%              — 고점권(빠짐 신호 없음)
     🟢 buy   낙폭 ≤ -20% & RSI<50 & 선행지표 3개월 ≥0 — '일시적 빠짐 후보'
     🔴 risk  낙폭 ≤ -20% & 선행지표 3개월 <0          — 선행지표 동반 악화(구조 의심)
     🟡 watch 그 외                                    — 관찰
     선행지표 미연결 종목이 낙폭 조건 충족 시 buy_m(🟢※ 수동 확인 필요).
※ 가격·판정은 '검토 후보 알림'이지 매수 신호가 아니다 — 가치함정은 걸러지지 않는다.
유니버스는 gen_appd/appf/apph 관계도의 B1 카드 기준 수동 동기화(관계도 갱신 시 여기도 갱신).

산출: data/db/moat.json
cron: 30 6 * * *
"""
import json, time, urllib.request, urllib.parse
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
OUT  = BASE / "data" / "db" / "moat.json"
HIST = BASE / "data" / "db" / "moat_hist.json"   # (Phase2) PER 일일 스냅샷 누적 — 자기 역사 대비 percentile
UA   = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120"}
KST  = timezone(timedelta(hours=9))

# (심볼, 이름, 분야, 해자 한 줄, 선행지표 심볼|None, 선행지표 이름)
UNIV = [
    ("ASML",      "ASML",          "AI반도체", "EUV 노광 유일 — 선단공정의 문지기, 대체재 없음",              "^SOX", "필라델피아 반도체지수"),
    ("TSM",       "TSMC",          "AI반도체", "선단공정 파운드리 압도 — AI 칩 전량이 거쳐가는 관문",          "^SOX", "필라델피아 반도체지수"),
    ("NVDA",      "엔비디아",       "AI반도체", "CUDA 생태계 락인 — GPU를 넘어선 소프트웨어 해자",             "^SOX", "필라델피아 반도체지수"),
    ("ARM",       "Arm",           "AI반도체", "저전력 설계 IP 사실상 표준 — 로열티 수취 구조",               "^SOX", "필라델피아 반도체지수"),
    ("4062.T",    "이비덴",         "AI반도체", "AI 서버용 FC-BGA 70~80% 과점 — 칩 설계 단계부터 공동개발",    "^SOX", "필라델피아 반도체지수"),
    ("VRT",       "버티브",         "AI반도체", "데이터센터 전력·액체냉각 토탈 — '칩보다 전기' 병목의 수혜",     "^SOX", "필라델피아 반도체지수"),
    ("000660.KS", "SK하이닉스",     "AI반도체", "HBM 점유 1위 — 엔비디아 최우선 공급사",                     "MU",   "마이크론(메모리 업황 대리)"),
    ("042700.KS", "한미반도체",     "AI반도체", "HBM TC본더 선두 — SK하이닉스와 동반 성장",                  "MU",   "마이크론(메모리 업황 대리)"),
    # (2026-08-30) 해자 강도 선별 B2 13종 — 1군(사실상 독점급) + 2군(병목 지배·사이클 공존)
    ("SNPS",      "시놉시스",       "AI반도체", "EDA 복점 — 이 툴 없인 칩 설계 불가, 스위칭 비용 극단",         "^SOX", "필라델피아 반도체지수"),
    ("CDNS",      "케이던스",       "AI반도체", "설계·검증 EDA 복점의 다른 축",                              "^SOX", "필라델피아 반도체지수"),
    ("AVGO",      "브로드컴",       "AI반도체", "빅테크 ASIC 설계 대행 + 네트워크칩 지배",                    "^SOX", "필라델피아 반도체지수"),
    ("6857.T",    "어드밴테스트",    "AI반도체", "AI 가속기·HBM 테스터 양강 — 검사 없인 출하 불가",             "MU",   "마이크론(메모리 업황 대리)"),
    ("6981.T",    "무라타",         "AI반도체", "AI 서버용 MLCC 삼성전기와 양분 — 가동률 90%+ 공급자 우위",     "^SOX", "필라델피아 반도체지수"),
    ("4063.T",    "신에쓰화학",      "AI반도체", "실리콘 웨이퍼 양강 — 신규진입 사실상 불가",                   "^SOX", "필라델피아 반도체지수"),
    ("6268.T",    "나브테스코",      "피지컬AI", "산업로봇 RV 감속기 ~60% — 하모닉과 관절 실질 복점",           "6954.T", "화낙(산업로봇 업황 대리)"),
    ("207940.KS", "삼성바이오로직스", "첨단바이오", "CDMO 캐파 세계 최대(78.4만L) + FDA 트랙레코드·장기계약 락인",  "XBI",  "미 바이오테크 ETF"),
    ("LLY",       "일라이릴리",      "첨단바이오", "비만약 듀오폴리 선두 — 젭바운드 점유 57%",                   "XBI",  "미 바이오테크 ETF"),
    ("NVO",       "노보노디스크",    "첨단바이오", "비만약 듀오폴리 — 경구 위고비 세계 최초 출시",                "XBI",  "미 바이오테크 ETF"),
    ("GEV",       "GE버노바",       "SMR·원전", "가스터빈 3사 과점 + 백로그 116GW — 전력 병목의 지배자",       "GRID", "스마트그리드 ETF(전력기기 업황 대리)"),
    ("267260.KS", "HD현대일렉트릭",  "재생에너지", "초고압 변압기 과점 — 수년치 수주잔고 공급부족",               "GRID", "스마트그리드 ETF(전력기기 업황 대리)"),
    ("298040.KS", "효성중공업",      "재생에너지", "초고압 변압기 과점 — 수주잔고 13.85조·멤피스 증설",           "GRID", "스마트그리드 ETF(전력기기 업황 대리)"),
    # (2026-08-30 전수 보정) 최신 해자지도 B1 대조에서 빠져 있던 상장 종목 편입 — 사용자 지적
    ("KLAC",      "KLA",           "AI반도체", "공정 검사·계측 사실상 독점 — 수율의 문지기",                  "^SOX", "필라델피아 반도체지수"),
    ("8035.T",    "도쿄일렉트론",    "AI반도체", "코터·디벨로퍼 등 전공정 장비 준독점군",                      "^SOX", "필라델피아 반도체지수"),
    ("6146.T",    "디스코",         "AI반도체", "HBM 적층 필수 그라인더·다이서 사실상 독점",                   "MU",   "마이크론(메모리 업황 대리)"),
    ("GOOGL",     "알파벳",         "AI반도체", "제미나이·TPU·딥마인드 — AI 풀스택 수직통합",                 None,   None),
    ("CEG",       "컨스텔레이션",    "SMR·원전", "미국 최대 원전 운영 — AI 무탄소 기저전력 장기 PPA 프리미엄",    None,   None),
    ("600111.SS", "중국북방희토",    "핵심광물", "희토류 채굴·분리 세계 최대 — 자석 원가의 지배 변수",           "REMX", "희토류·전략금속 ETF"),
    ("300748.SZ", "JL마그",         "핵심광물", "NdFeB 영구자석 세계 최대 — 중국 자석 90% 장악의 상징",        "REMX", "희토류·전략금속 ETF"),
    ("300750.SZ", "CATL",          "재생에너지", "ESS 셀 점유율 약 39% — 5년 연속 1위",                      "LIT",  "리튬·배터리 ETF"),
    ("600438.SS", "통위",           "재생에너지", "폴리실리콘 캐파 세계 1위 — 중국이 전 세계 93.5% 장악",       "TAN",  "태양광 ETF"),
    ("WCH.DE",    "바커케미",       "재생에너지", "폴리실리콘 톱10 내 유일한 비중국 생산자",                    "TAN",  "태양광 ETF"),
    ("SPCX",      "스페이스X",      "우주·방산", "궤도발사 점유 50%+ · 스타링크 LEO 통신 독주",                "ARKX", "우주·방산 혁신 ETF(테마 대리)"),
    ("6324.T",    "하모닉드라이브",  "피지컬AI", "로봇 관절 감속기 세계 표준 — 수십 년 내구성 데이터가 해자",     "6954.T", "화낙(산업로봇 업황 대리)"),
    ("6758.T",    "소니그룹",       "피지컬AI", "이미지센서 1위 — 로봇·스마트폰 '눈'의 기본 공급자",           None,   None),
    ("3402.T",    "도레이",         "피지컬AI", "탄소섬유(CFRP) 세계 1위 — 경량화의 소재 관문",               None,   None),
    ("034020.KS", "두산에너빌리티", "SMR·원전", "SMR 파운드리 — 테라파워·뉴스케일·엑스에너지 주기기 계약",       "U-UN.TO", "스프로트 실물 우라늄"),
    ("LEU",       "센트러스",       "SMR·원전", "美 HALEU 농축 유일 — DOE가 직접 돈을 대는 병목",             "U-UN.TO", "스프로트 실물 우라늄"),
    ("KAP.L",     "카자톰프롬",     "SMR·원전", "우라늄 채굴 세계 1위(점유 23%)",                            "U-UN.TO", "스프로트 실물 우라늄"),
    ("MP",        "MP머티리얼즈",   "핵심광물", "미국 유일 희토류 일관 — 국방부 지분 15%·가격 하한 보장",       "REMX", "희토류·전략금속 ETF"),
    ("LYC.AX",    "라이너스",       "핵심광물", "중국 밖 유일 중희토류 분리 — 디스프로슘 상업생산",             "REMX", "희토류·전략금속 ETF"),
    ("010130.KS", "고려아연",       "핵심광물", "아연 제련 세계 1위 + 美 테네시 74억$ 제련소 — 비철 13종 회수", "SI=F", "은 선물(부산물 가격)"),
    ("196170.KQ", "알테오젠",       "첨단바이오", "SC 제형 변환 독점 — 키트루다SC 머크 독점계약 로열티",         "MRK",  "머크(키트루다 주인)"),
    ("VRTX",      "버텍스",         "첨단바이오", "낭포성섬유증 치료제 사실상 독점 + CRISPR 상업화 선두",        "XBI",  "미 바이오테크 ETF"),
    ("ILMN",      "일루미나",       "첨단바이오", "유전자 시퀀싱 준독점 — 장비 설치기반 락인",                  "XBI",  "미 바이오테크 ETF"),
    ("CRSP",      "크리스퍼 Tx",    "첨단바이오", "유전자편집 치료제 최초 상업화(카스게비)",                    "XBI",  "미 바이오테크 ETF"),
    ("047810.KS", "한국항공우주",   "우주·방산", "국내 완제기 체계종합 유일 — FA-50 수출 축",                  "hs:88",      "항공기 수출(관세청 88류·12M누적)"),
    ("012450.KS", "한화에어로",     "우주·방산", "누리호 체계종합 독점 + K-방산 수주잔고",                     "hs:93+8710", "무기·전차 수출(관세청·12M누적)"),
    ("IRDM",      "이리듐",         "우주·방산", "극지 포함 L밴드 전지구망 보유 유일 사업자",                   "ARKX",       "우주·방산 혁신 ETF(테마 대리)"),
    ("QBTS",      "디웨이브",       "양자",     "양자 어닐링 상용화 유일",                                   "QTUM",       "양자 테마 ETF(테마 조정 vs 고유 문제 구분)"),
    ("294630.KQ", "서남",          "핵융합",   "2세대 고온초전도 선재 양산 국내 유일 — 英 STEP 공급사",        None,   None),
]

# (2026-08-30) 해자 강도 선별 B2 — 관계도 배지는 황색(복점·양강)이 정확하지만 해자 실질은 B1급인 종목
#   기준: 스위칭 비용 극단(EDA)·출하 병목(테스터·MLCC·감속기)·규모 락인(CDMO)·수년 백로그(터빈·변압기)·듀오폴리(비만약)
SEL_B2 = {"SNPS","CDNS","6857.T","6981.T","6268.T","207940.KS","GEV","4063.T","267260.KS","298040.KS","LLY","NVO","AVGO"}

# 해자 위협 워치포인트 (구조 훼손 후보 — 뉴스 기반 수동 갱신)
RISKS = {
    "ASML": "中 역설계 EUV 프로토타입(2025.12)·화웨이 LDP 광원 실험 — 단 국산 DUV는 4세대 격차, 양산칩은 2030년 전망(현재 위협 아님)",
    "ILMN": "중국 수입금지 — 2026 성장률 1%p 역풍(구조 훼손 진행형 리스크)",
    "010130.KS": "경영권 분쟁 2라운드 진행 중 — 지배구조 리스크 잔존",
}

def get(u, to=25):
    return urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=to).read()

# ── (Phase2) 야후 PER — crumb 인증 플로우 (2026-08-30 실측 확인) ─────────────
_OPENER = urllib.request.build_opener(urllib.request.HTTPCookieProcessor())
_CRUMB = None

def _crumb():
    global _CRUMB
    if _CRUMB is None:
        try:
            try:
                _OPENER.open(urllib.request.Request("https://fc.yahoo.com", headers=UA), timeout=15).read()
            except Exception:
                pass  # fc.yahoo.com 은 404 여도 쿠키는 심어진다
            _CRUMB = _OPENER.open(urllib.request.Request(
                "https://query1.finance.yahoo.com/v1/test/getcrumb", headers=UA), timeout=15).read().decode()
        except Exception as e:
            print(f"  ⚠ crumb 실패: {repr(e)[:50]}", flush=True)
            _CRUMB = ""
    return _CRUMB

def fetch_per(sym):
    """forward PER 우선, 없으면 trailing. 통화 불일치 쓰레기값(KAP.L 0.0096 실측) 필터: 1<PE<500 만 유효."""
    c = _crumb()
    if not c:
        return None, None
    try:
        u = (f"https://query1.finance.yahoo.com/v10/finance/quoteSummary/{urllib.parse.quote(sym)}"
             f"?modules=summaryDetail,defaultKeyStatistics&crumb={urllib.parse.quote(c)}")
        d = json.loads(_OPENER.open(urllib.request.Request(u, headers=UA), timeout=20).read())
        r = d["quoteSummary"]["result"][0]
        sd, ks = r.get("summaryDetail", {}), r.get("defaultKeyStatistics", {})
        for v, src in (((ks.get("forwardPE") or sd.get("forwardPE") or {}).get("raw"), "fwd"),
                       ((sd.get("trailingPE") or {}).get("raw"), "ttm")):
            if v is not None and 1 < v < 500:
                return round(v, 1), src
    except Exception:
        pass
    return None, None

def per_band(per_map):
    """이력 누적 후 종목별 percentile(하위 x% = 자기 역사상 저평가) — 관측 20일 미만이면 percentile 없이 일수만."""
    try:
        h = json.loads(HIST.read_text(encoding="utf-8"))
    except Exception:
        h = {"days": []}
    today = datetime.now(KST).strftime("%Y-%m-%d")
    h["days"] = [d for d in h.get("days", []) if d.get("d") != today]
    h["days"].append({"d": today, "per": {k: v for k, (v, s) in per_map.items() if v is not None}})
    h["days"] = sorted(h["days"], key=lambda x: x["d"])[-1500:]
    HIST.write_text(json.dumps(h, ensure_ascii=False), encoding="utf-8")
    out = {}
    for sym, (v, src) in per_map.items():
        if v is None:
            continue
        hist_vals = [d["per"][sym] for d in h["days"] if sym in d.get("per", {})]
        n = len(hist_vals)
        pct = round(sum(1 for x in hist_vals if x <= v) / n * 100) if n >= 20 else None
        out[sym] = {"per": v, "src": src, "pct": pct, "n": n}
    return out

def hist(sym, rng="2y"):
    u = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(sym)}?range={rng}&interval=1d"
    j = json.loads(get(u))
    r = (j.get("chart") or {}).get("result") or []
    if not r:
        return None
    r = r[0]
    ts = r.get("timestamp") or []
    cl = ((r.get("indicators") or {}).get("quote") or [{}])[0].get("close") or []
    pts = [(t, c) for t, c in zip(ts, cl) if c is not None]
    return pts or None

def rsi14(closes):
    if len(closes) < 15:
        return None
    g = l = 0.0
    for i in range(1, 15):
        d = closes[i] - closes[i-1]
        g += max(d, 0); l += max(-d, 0)
    ag, al = g/14, l/14
    for i in range(15, len(closes)):
        d = closes[i] - closes[i-1]
        ag = (ag*13 + max(d, 0)) / 14
        al = (al*13 + max(-d, 0)) / 14
    return 100.0 if al == 0 else round(100 - 100/(1 + ag/al), 1)

def pct(a, b):
    return round((b/a - 1) * 100, 1) if a else None

# ── (Phase3) 관세청 HS 수출을 선행지표로 — "hs:88" / "hs:93+8710" 형식 ──────
#    K-소비재 탭에서 검증된 tradedata 패턴 재사용. 12M 누적의 3개월/12개월 변화율로 방향 판정.
TRADE_URL = "https://tradedata.go.kr/cts/hmpg/retrieveTrade.do"
TRADE_H = dict(UA); TRADE_H.update({"Content-Type": "application/x-www-form-urlencoded",
                                    "Referer": "https://tradedata.go.kr/cts/index.do"})

def hs_lead(codes):
    import re as _re
    now = datetime.now(KST)
    fr, to = f"{now.year-3}{now.month:02d}", f"{now.year}{now.month:02d}"
    acc = {}
    for hs in codes.split("+"):
        col = {2: "HS2_SGN", 4: "HS4_SGN", 6: "HS6_SGN"}[len(hs)]
        body = urllib.parse.urlencode({"tradeKind": "ETS_MNK_1020000A", "priodKind": "MON",
            "priodFr": fr, "priodTo": to, "statsBase": "acptDd", "ttwgTpcd": "1000",
            "showPagingLine": "100", "hsSgnGrpCol": col, "hsSgnWhrCol": col, "hsSgn": hs}).encode()
        j = json.loads(urllib.request.urlopen(urllib.request.Request(TRADE_URL, data=body, headers=TRADE_H), timeout=30).read())
        for x in j.get("items") or []:
            p = (x.get("priodTitle") or "").strip()
            if _re.match(r"^\d{4}\.\d{2}$", p):
                v = (x.get("expUsdAmt") or "").replace(",", "").strip()
                acc[p] = acc.get(p, 0) + (int(v) if v else 0)
        time.sleep(0.4)
    ms = sorted(acc)
    vals = [acc[m] for m in ms]
    roll = [sum(vals[i-11:i+1]) if i >= 11 else None for i in range(len(vals))]
    rv = [r for r in roll if r is not None]
    if len(rv) < 4:
        return None
    return {"m3": pct(rv[-4], rv[-1]), "y1": pct(rv[-13], rv[-1]) if len(rv) >= 13 else None, "cur": rv[-1]}

def main():
    print("[moat] 수집 시작", flush=True)
    # (Phase2) PER 스냅샷 → 이력 누적 → 밴드 percentile
    per_map = {}
    for sym, *_ in UNIV:
        per_map[sym] = fetch_per(sym)
        time.sleep(0.3)
    band = per_band(per_map)
    ok = sum(1 for v in band.values())
    print(f"  PER: {ok}/{len(UNIV)}종 수집 · 밴드 누적 {max((b['n'] for b in band.values()), default=0)}일", flush=True)
    leads = {}
    for sym in sorted({x[4] for x in UNIV if x[4]}):
        try:
            if sym.startswith("hs:"):
                leads[sym] = hs_lead(sym[3:])
            else:
                pts = hist(sym, "1y")
                cl = [c for _, c in pts]
                leads[sym] = {"m3": pct(cl[-64], cl[-1]) if len(cl) > 64 else None,
                              "y1": pct(cl[0], cl[-1]), "cur": round(cl[-1], 2)}
        except Exception as e:
            print(f"  ⚠ lead {sym}: {repr(e)[:50]}", flush=True)
            leads[sym] = None
        time.sleep(0.3)
    rows = []
    for sym, nm, sec, moat, lsym, lnm in UNIV:
        try:
            pts = hist(sym)
        except Exception as e:
            print(f"  ⚠ {nm}({sym}) 실패: {repr(e)[:50]}", flush=True)
            continue
        if not pts:
            continue
        cl = [c for _, c in pts]
        cur = cl[-1]
        yr = cl[-252:] if len(cl) >= 252 else cl
        hi52 = max(yr)
        dd = pct(hi52, cur)                       # 52주 고점 대비(음수)
        ma200 = sum(cl[-200:])/min(200, len(cl))
        gap200 = pct(ma200, cur)
        rsi = rsi14(cl[-120:])
        m1 = pct(cl[-22], cur) if len(cl) > 22 else None
        m3 = pct(cl[-64], cur) if len(cl) > 64 else None
        y1 = pct(cl[-253], cur) if len(cl) > 253 else pct(cl[0], cur)
        L = leads.get(lsym) if lsym else None
        lead_m3 = L.get("m3") if L else None
        if dd is None:
            v = "watch"
        elif dd > -10:
            v = "top"
        elif dd <= -20 and (rsi is None or rsi < 50):
            if lsym is None or lead_m3 is None:
                v = "buy_m"                        # 🟢※ 선행지표 미연결 — 수동 확인
            elif lead_m3 >= 0:
                v = "buy"
            else:
                v = "risk"
        else:
            v = "watch"
        step = max(1, len(pts)//60)
        samp = pts[::step][-60:]
        rows.append({"sym": sym, "name": nm, "sec": sec, "moat": moat, "risk": RISKS.get(sym),
                     "tier": ("B2+" if sym in SEL_B2 else "B1"),
                     "val": band.get(sym),
                     "cur": round(cur, 1), "dd": dd, "gap200": gap200, "rsi": rsi,
                     "m1": m1, "m3": m3, "y1": y1, "verdict": v,
                     "lead": ({"sym": lsym, "name": lnm, "m3": lead_m3,
                               "y1": (L or {}).get("y1")} if lsym else None),
                     "spark": [round(c, 1) for _, c in samp],
                     "spark_d": [datetime.fromtimestamp(t, KST).strftime("%y.%m.%d") for t, _ in samp]})
        time.sleep(0.3)
    # (Phase3) 판정 이력 누적 → 전환 감지(어제와 다르면 vd_prev)·유지일수(vd_days)
    try:
        h = json.loads(HIST.read_text(encoding="utf-8"))
    except Exception:
        h = {"days": []}
    today = datetime.now(KST).strftime("%Y-%m-%d")
    vd_today = {r["sym"]: r["verdict"] for r in rows}
    prev_days = [d for d in h.get("days", []) if d.get("d") != today and d.get("vd")]
    prev = prev_days[-1]["vd"] if prev_days else {}
    for d in h.get("days", []):
        if d.get("d") == today:
            d["vd"] = vd_today
            break
    else:
        h.setdefault("days", []).append({"d": today, "vd": vd_today})
    h["days"] = sorted(h["days"], key=lambda x: x["d"])[-1500:]
    HIST.write_text(json.dumps(h, ensure_ascii=False), encoding="utf-8")
    for r in rows:
        p = prev.get(r["sym"])
        r["vd_prev"] = p if (p and p != r["verdict"]) else None   # 오늘 전환됐으면 직전 판정
        n = 0
        for d in reversed(h["days"]):
            if (d.get("vd") or {}).get(r["sym"]) == r["verdict"]:
                n += 1
            else:
                break
        r["vd_days"] = n
    chg = [f"{r['name']} {r['vd_prev']}→{r['verdict']}" for r in rows if r["vd_prev"]]
    if chg:
        print("  전환:", chg, flush=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "as_of": datetime.now(KST).strftime("%Y-%m-%d %H:%M"),
        "rows": rows,
        "counts": {k: sum(1 for r in rows if r["verdict"] == k) for k in ("buy", "buy_m", "risk", "watch", "top")},
    }, ensure_ascii=False), encoding="utf-8")
    vc = {r['name']: r['verdict'] for r in rows if r['verdict'] in ('buy', 'buy_m', 'risk')}
    print(f"[moat] ✅ {len(rows)}/{len(UNIV)}종 → {OUT} · 신호: {vc}", flush=True)

if __name__ == "__main__":
    main()
