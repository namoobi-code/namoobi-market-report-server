#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fetch_share.py — 📊 점유율 추이(Share Watch) 정본 생성 (2026-08-31 신설)

'점유율만 잘 추적하면 주가 예상이 가능한 대결'(릴리 vs 노보 사례)을 시계열로 축적한다.
데이터 3원천:
  ① 시드 시계열(이 파일에 내장) — 실적 발표·기관 보도 실측치 위주, (E)=기관 추정.
  ② 자동 병합 — 서버가 이미 매일 수집 중인 DB 재활용:
     hbm  = series_mem_hbm_share.json (HBM 3사, 3.1.9 파이프라인)
     amzn = kcons_hist.json 아마존 뷰티 베스트셀러 브랜드별 최고 랭크(K-소비재 파이프라인)
  ③ LLM 갱신 — share_llm.json(/namoobi-market-report Phase 3.7 산출)을 upsert.
     신선도 기준(주간>10일·월간>40일·분기>100일)을 넘긴 배틀만 보고서 실행 시 웹서치로 갱신.
선별 B2의 점유 '구도'는 moat.json(SHARES)이 정본 — 탭에서 함께 표시(Phase 3.6이 점검).

산출: data/db/share.json
cron: 35 6 * * *
"""
import json, time
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DB   = BASE / "data" / "db"
OUT  = DB / "share.json"
KST  = timezone(timedelta(hours=9))

# freq → 신선도 한도(일) — Phase 3.7 이 이 기준으로 갱신 대상을 고른다
FRESH = {"주간": 10, "월간": 40, "분기": 100, "반기": 200, "연간": 400}

# (id, 등급, 이름, 단위, 갱신주기, 주가 연결 논리, 플레이어[(표시명, 관련종목)], 시드 시계열, auto, 출처)
BATTLES = [
    ("glp1", "A", "美 비만약(GLP-1) 처방 점유", "%", "분기",
     "점유 역전(2023 2:8 → 2026 6:4)이 릴리·노보 주가를 완전히 갈랐다 — 본 탭의 원형 사례",
     [("릴리", "LLY"), ("노보", "NVO")],
     [("2023-12", {"릴리": 20, "노보": 80}, "출시 초기(E)"),
      ("2025-06", {"릴리": 57, "노보": 43}, "신규처방 역전 실측"),
      ("2026-06", {"릴리": 60, "노보": 40}, "처방 10건 중 6건 릴리 실측")],
     None, "IQVIA 처방 집계 보도·양사 실적"),
    ("ess", "A", "ESS 배터리 셀 출하 점유", "%", "월간",
     "LFP 전환의 승자 판별 — CATL 고착 vs 신흥 중국사 난립 속 한국 2사 위치가 LG엔솔·삼성SDI 밸류 결정",
     [("CATL", "300750.SZ"), ("EVE", "300014.SZ"), ("하이시움", "비상장"), ("BYD", "002594.SZ"), ("LG엔솔", "373220.KS"), ("삼성SDI", "006400.KS")],
     [("2025-06", {"CATL": 25.6, "LG엔솔": 1.0, "삼성SDI": 2.0}, "실측(CnEVPost 전년동기 비교치)"),
      ("2025-12", {"CATL": 30.0}, "SNE 연간 실측 — 한국 2사 합 4%"),
      ("2026-06", {"CATL": 27.1, "EVE": 10.4, "하이시움": 10.0, "BYD": 7.7, "LG엔솔": 2.6, "삼성SDI": 1.4}, "1H26 실측 풀세트(461GWh·+71%)")],
     None, "SNE리서치·InfoLink·CnEVPost — 북미 한정은 한국 2사 19.7%로 구조 상이"),
    ("cn_ev", "A", "중국 NEV 소매 점유", "%", "월간",
     "월간 인도량이 가장 고빈도 점유 데이터 — BYD 2년 연속 급락(34→27→21%) vs 지리 약진이 관전점, 테슬라는 톱10 이탈",
     [("BYD", "002594.SZ"), ("지리", "0175.HK"), ("창안", "000625.SZ"), ("립모터", "9863.HK"), ("테슬라", "TSLA")],
     [("2024-12", {"BYD": 34.1, "테슬라": 6.0}, "연간 실측(테슬라 E)"),
      ("2025-12", {"BYD": 27.2, "지리": 12.2, "창안": 6.2, "테슬라": 4.9}, "연간 실측 — 우링 6.0%"),
      ("2026-07", {"BYD": 23.5, "지리": 11.1, "립모터": 8.8}, "월간 실측 — 테슬라 톱10 이탈(1~7월 누적 4.7%)")],
     None, "중국승용차협회(CPCA) 월간 공시·CnEVPost"),
    ("amzn_kb", "A", "아마존 US 뷰티 톱60 내 K뷰티 최고 랭크", "위", "일간",
     "온라인 점유의 일간 프록시 — 메디큐브(에이피알) 랭크 상승이 실적 컨센 상향으로 이어지는 경로",
     [], [], "amzn", "아마존 베스트셀러(K-소비재 탭 파이프라인 재활용)"),
    ("hbm", "B", "HBM 점유 (SK하이닉스·삼성·마이크론)", "%", "분기",
     "엔비디아 퀄·배분 뉴스가 3사 주가 즉발 변수 — 삼성 반격 폭이 SK하이닉스 프리미엄을 결정",
     [("SK하이닉스", "000660.KS"), ("삼성전자", "005930.KS"), ("마이크론", "MU")],
     [], "hbm", "트렌드포스·업계 집계(서버 3.1.9 일일 수집 재활용)"),
    ("ai_chip", "B", "AI 서버 출하 비중 (GPU vs 커스텀 ASIC)", "%", "분기",
     "ASIC 성장률이 GPU의 3배(+44.6% vs +16.1%) — 2030년 ASIC 40% 전망, 엔비디아 멀티플 압박·브로드컴 수혜의 제로섬. 매출 기준으론 엔비디아 ~86%(2025)로 여전히 압도",
     [("GPU(엔비디아)", "NVDA"), ("커스텀 ASIC", "AVGO")],
     [("2026-12", {"GPU(엔비디아)": 69.7, "커스텀 ASIC": 27.8}, "트렌드포스 2026 전망(출하 대수 기준) — ASIC 2023년 이후 최고치")],
     None, "트렌드포스 AI 서버 전망 — 출하 대수 기준(매출 기준 아님) 주의"),
    ("foundry", "B", "파운드리 매출 점유", "%", "분기",
     "선단공정 수주 배분 — TSMC 점유가 오히려 확대(67→72%) 중, 고착이 유지되는 한 TSM 멀티플의 바닥 논리",
     [("TSMC", "TSM"), ("삼성 파운드리", "005930.KS"), ("SMIC", "0981.HK")],
     [("2024-12", {"TSMC": 67.1, "삼성 파운드리": 8.1}, "트렌드포스 실측"),
      ("2025-12", {"TSMC": 70.4, "삼성 파운드리": 7.1, "SMIC": 5.4}, "4Q25 실측(SMIC 역산 E)"),
      ("2026-03", {"TSMC": 72.3, "삼성 파운드리": 6.5, "SMIC": 5.1}, "1Q26 실측 — 톱10 합계 사상 최대")],
     None, "트렌드포스 분기 보도"),
    ("tester", "B", "SoC 테스터 점유 (어드밴테스트)", "%", "반기",
     "HBM·AI 테스터 승부 — 어드밴 56→66%로 확대 중(⚪⚠ 판정의 반증 데이터), 매출 기준 테라다인의 2배",
     [("어드밴테스트", "6857.T"), ("테라다인", "TER")],
     [("2024-12", {"어드밴테스트": 56}, "사측 실측 — 양사 합산 전체 테스터 ~80%"),
      ("2025-12", {"어드밴테스트": 66}, "사측 실측(테라다인 개별 % 미공표)")],
     None, "어드밴테스트 실적설명 자료·업계 리서치"),
    ("cloud", "B", "클라우드 인프라 점유", "%", "분기",
     "3강 성장률 격차가 리레이팅 결정 — GCP 점유 상승(12→15%)이 알파벳 카드의 핵심 변수, 3사 합 63%는 정체(오라클·네오클라우드 잠식)",
     [("AWS", "AMZN"), ("Azure", "MSFT"), ("GCP", "GOOGL")],
     [("2024-12", {"AWS": 30, "Azure": 21, "GCP": 12}, "시너지리서치 실측"),
      ("2025-12", {"AWS": 28, "Azure": 21, "GCP": 14}, "4Q25 실측"),
      ("2026-06", {"AWS": 28, "Azure": 20, "GCP": 15}, "2Q26 실측 — 시장 +43% 8년래 최고 성장")],
     None, "시너지리서치 분기 발표"),
    ("mlcc", "B", "MLCC 점유 (무라타·삼성전기)", "%", "반기",
     "AI 서버용 세그먼트는 무라타 45 vs 삼성전기 40(E)으로 사실상 양분 — 4Q26 OEM 가격 인상(삼성전기 주도) = 업사이클 개시",
     [("무라타", "6981.T"), ("삼성전기", "009150.KS")],
     [("2024-06", {"무라타": 40, "삼성전기": 24}, "(E) 전체 시장 기준 — AI 서버용은 45 vs 40(E)")],
     None, "업계·코트라 인용(전체 시장) — 야교·타이요유덴 실측 공표 없음, 트렌드포스 유료 리포트 영역"),
    ("cdmo", "B", "CDMO 생산 캐파 (만L)", "만L", "반기",
     "캐파가 곧 해자 — 삼바 격차 확대 vs 우시 계획(58만L) 실행 여부가 삼바 프리미엄 결정",
     [("삼성바이오", "207940.KS"), ("베링거", "비상장"), ("론자", "LONN"), ("우시바이오", "2269.HK")],
     [("2018-12", {"삼성바이오": 36.2}, "1~3공장"),
      ("2020-12", {"베링거": 29}, "실측"),
      ("2023-12", {"삼성바이오": 60.4, "베링거": 43}, "4공장·비엔나"),
      ("2025-12", {"삼성바이오": 78.4, "론자": 40, "우시바이오": 26}, "5공장/바카빌(E)/실측"),
      ("2026-06", {"삼성바이오": 84.5}, "美 록빌 인수 — 팩트시트 실측")],
     None, "각사 팩트시트·실적 발표"),
]


def load(p):
    try:
        return json.loads((DB / p).read_text(encoding="utf-8"))
    except Exception:
        return None


def auto_hbm():
    """series_mem_hbm_share.json(일별) → 주 1회 샘플 시계열"""
    d = load("series_mem_hbm_share.json")
    if not d or not d.get("data"):
        return []
    out, last_wk = [], None
    for dt_, m in d["data"]:
        wk = dt_[:7] + "-" + str(int(dt_[8:10]) // 7)
        if wk == last_wk:
            continue
        last_wk = wk
        out.append((dt_, {"SK하이닉스": m.get("SK Hynix"), "삼성전자": m.get("Samsung"),
                          "마이크론": m.get("Micron")}, "실측(주간 샘플)"))
    return out[-26:]


def auto_amzn():
    """kcons_hist.json → 브랜드별 아마존 최고 랭크 일별 시계열(낮을수록 좋음)"""
    h = load("kcons_hist.json")
    if not h:
        return [], []
    days = [d for d in h.get("days", []) if d.get("az")]
    brands = []
    for d in days:
        for b in d["az"]:
            if b not in brands:
                brands.append(b)
    ser = [(d["d"], {b: d["az"].get(b) for b in brands if d["az"].get(b)}, "실측") for d in days]
    return ser[-60:], [(b, "") for b in brands]


def main():
    print("[share] 생성 시작", flush=True)
    llm = load("share_llm.json") or {}
    ups = {}
    for u in llm.get("updates", []):
        ups.setdefault(u.get("id"), []).append(u)
    battles = []
    for bid, grade, name, unit, freq, why, players, seed, auto, src in BATTLES:
        series = [{"d": d, "v": v, "note": n} for d, v, n in seed]
        if auto == "hbm":
            series = [{"d": d, "v": v, "note": n} for d, v, n in auto_hbm()]
        elif auto == "amzn":
            ser, players = auto_amzn()
            series = [{"d": d, "v": v, "note": n} for d, v, n in ser]
        for u in ups.get(bid, []):   # Phase 3.7 LLM 갱신 upsert (같은 날짜면 교체)
            series = [s for s in series if s["d"] != u["d"]]
            series.append({"d": u["d"], "v": u["v"], "note": "🧠 " + (u.get("note") or "보고서 갱신"),
                           "src": u.get("src")})
        series.sort(key=lambda s: s["d"])
        last = series[-1]["d"] if series else None
        stale = None
        if last and auto is None:
            days_old = (datetime.now(KST).date() - datetime.strptime(last[:10] if len(last) > 7 else last + "-28", "%Y-%m-%d").date()).days
            stale = days_old > FRESH.get(freq, 100)
        battles.append({"id": bid, "grade": grade, "name": name, "unit": unit, "freq": freq,
                        "why": why, "players": [{"k": k, "stock": st} for k, st in players],
                        "series": series, "auto": auto, "src": src, "stale": stale})
        print(f"  {grade} {name}: {len(series)}점" + (" · 자동" if auto else (" · ⏳갱신 필요" if stale else "")), flush=True)
    OUT.write_text(json.dumps({
        "as_of": datetime.now(KST).strftime("%Y-%m-%d %H:%M"),
        "battles": battles,
        "llm_asof": llm.get("as_of"),
    }, ensure_ascii=False), encoding="utf-8")
    print(f"[share] ✅ {len(battles)}개 대결 → {OUT}", flush=True)


if __name__ == "__main__":
    main()
