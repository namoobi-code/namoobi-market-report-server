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
import json, time, subprocess
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
     # (2026-09-04) 월간 시계열 확보 — CnEVPost 가 매월 중순 CPCA 기준 업체별 점유를 공표한다.
     #   2026년 월별 전 플레이어 실측으로 교체(종전 3점 → 9점).
     [("2024-12", {"BYD": 34.1, "테슬라": 6.0}, "2024 연간 실측(테슬라 E)"),
      ("2025-12", {"BYD": 27.2, "지리": 12.2, "창안": 6.2, "테슬라": 4.9}, "2025 연간 실측 — 우링 6.0%"),
      ("2026-02", {"BYD": 19.1, "지리": 16.5, "창안": 6.1, "립모터": 3.9, "테슬라": 8.2},
       "2월 — BYD 연중 최저(19.1%), 지리 16.5%로 최대 접근(격차 2.6%p)"),
      ("2026-03", {"BYD": 22.8, "지리": 11.4, "창안": 8.0, "립모터": 3.9}, "3월 실측"),
      ("2026-04", {"BYD": 21.4, "지리": 11.3, "창안": 7.6, "립모터": 6.7}, "4월 — 립모터 3.9→6.7% 급등"),
      ("2026-05", {"BYD": 21.8, "지리": 11.5, "창안": 6.6, "립모터": 6.5}, "5월 실측"),
      ("2026-06", {"BYD": 22.3, "지리": 10.7, "창안": 6.6, "립모터": 7.2}, "6월 — 테슬라 2개월 연속 5위"),
      ("2026-07", {"BYD": 23.5, "지리": 11.1, "창안": 6.3, "립모터": 8.8},
       "7월 — 립모터 8.8%로 창안 추월해 3위, 테슬라 톱10 이탈(1~7월 누적 4.7%)")],
     None, "중국승용차협회(CPCA) 월간 공시 · CnEVPost 월별 업체별 점유 집계"),
    ("us_ev", "A", "美 EV 판매 점유", "%", "분기",
     "테슬라 점유 하락(49→46→45%) 속 2위 경쟁 — 현대·기아는 그룹 합산 3~4위권, 보조금 종료 후 재편이 관전점",
     [("테슬라", "TSLA"), ("GM", "GM"), ("포드", "F"), ("현대차그룹", "005380.KS·000270.KS")],
     [("2024-12", {"테슬라": 49}, "Cox 연간 실측"),
      ("2025-12", {"테슬라": 46, "GM": 13, "포드": 7, "현대차그룹": 6}, "연간 실측(CleanTechnica·Cox) — 4Q25 테슬라 59% 반등 후 재하락"),
      ("2026-06", {"테슬라": 45}, "1H26 실측 — 브랜드 기준 쉐보레 6.0·현대 5.8(기아 별도, 그룹 합산 미공표)")],
     None, "Cox Automotive 분기 리포트·CleanTechnica"),
    ("amzn_kb", "A", "아마존 US 뷰티 톱60 내 K뷰티 최고 랭크", "위", "일간",
     "온라인 점유의 일간 프록시 — 메디큐브(에이피알) 랭크 상승이 실적 컨센 상향으로 이어지는 경로",
     [], [], "amzn", "아마존 베스트셀러(K-소비재 탭 파이프라인 재활용)"),
    ("ai_accel", "A", "AI 가속기 분기 매출 (엔비디아·AMD·브로드컴)", "십억$", "분기",
     "★ 점유율(%)이 아니라 매출액으로 재는 이유 — 기관마다 'AI 반도체'의 정의가 달라 엔비디아 점유가 "
     "75~86% 로 11%p 나 벌어진다(엔비디아 데이터센터엔 네트워킹 포함, 브로드컴 AI 매출도 마찬가지). "
     "그래서 각사 공시 분기 매출을 그대로 쌓아 정의를 우리가 고정한다 — 매 분기 SEC 에서 자동 검증. "
     "엔비디아·AMD 는 SEC 공시 부문 매출 실측(자동), 브로드컴 AI 반도체 매출은 비GAAP 구두 공시라 "
     "세그먼트 태그가 없어 실적발표 실측을 시드로 넣는다(분기 결산일도 회사마다 다르다 — 같은 달로 묶어 표시). "
     "고객 구성도 갈린다: 엔비디아 데이터센터 안에서 하이퍼스케일(2Q26 487억$·+102% YoY)보다 "
     "AI클라우드·기업·소버린(403억$·+138%)이 더 빨리 큰다 — 고객 저변이 빅테크 밖으로 넓어지는 중. "
     "시장 전망은 2030년 2,860억$(Omdia)~2033년 6,000억$+(블룸버그인텔리전스)로 출처 간 2배 차이라 "
     "단일 시계열로 그리지 않는다(거짓 정밀도 방지).",
     [("엔비디아 데이터센터", "NVDA"), ("AMD 데이터센터", "AMD"), ("브로드컴 AI반도체", "AVGO")],
     [], "ai_accel", "SEC EDGAR 공시 부문 매출(엔비디아·AMD) + 브로드컴 실적발표 AI 반도체 매출"),
    ("nvda_cust", "B", "엔비디아 고객 집중도 (익명 상위 고객, SEC 실측)", "%", "분기",
     "★ 'AI 반도체를 누가 사는가' — 엔비디아 10-Q/10-K 의 XBRL 을 직접 파싱한다(매 분기 자동 갱신). "
     "개별 10% 이상 고객만 익명으로 공시되며 라벨(Customer A/1/One)은 공시마다 재할당돼 "
     "같은 고객 추적은 불가 — 순위별 비중만 읽는다. ⚠ 미공시는 0% 가 아니라 '10% 미만'이라 "
     "합계 비교는 공시 문턱 탓에 무의미하고, 항상 공시되는 1위 고객 비중이 진짜 비교 대상이다. "
     "매출채권 기준은 더 극단적이다 — 2026 상반기 상위 5곳이 70%(2025 상반기 3곳 56%, 2024 상반기 3곳 49%). "
     "엔비디아 스스로 '투자등급 대형 고객과의 다분기 계약에 결제조건을 늘려줘' DSO 가 45→60일로 늘었다고 밝혔다. "
     "조달구조 탭의 하이퍼스케일러 5사와 같은 얼굴들이다 — 그들이 빚내서 사고, 엔비디아가 외상을 준다. "
     "AMD·브로드컴은 이 항목을 XBRL 로 태깅하지 않아 자동 수집 불가(엔비디아 단독).",
     [], [], "nvda_cust", "SEC EDGAR 10-Q/10-K XBRL (us-gaap:ConcentrationRiskPercentage1)"),
    ("dram", "B", "D램 전체 매출 점유 (HBM 포함 — 범용 D램이 승부처)", "%", "분기",
     "★ HBM 점유만 보면 놓치는 판 — SK하이닉스는 매출이 YoY +214% 인데도 D램 전체 점유가 39%→26% 로 밀렸다. "
     "HBM 비중이 가장 높아 HBM3E 가격 하락·HBM4 지연을 직격당했고, 일찍 맺은 장기계약(LTA)의 가격 상한에 묶인 사이 "
     "범용 D램 가격이 QoQ 급등하며 삼성이 1위를 탈환했다. "
     "마이크론은 D램 매출이 1년 새 5배로 늘어 SK 2위 자리를 위협(격차 1%p)하고, "
     "CXMT 는 +716% YoY 로 전체 1위 성장률 — 처음 두 자릿수 점유 진입(2023년 <1% → 3년 만에 10배). "
     "즉 한국 2사가 HBM 에 캐파를 몰아준 사이 비워진 범용 D램을 중국이 파고들었다는 것이 이 대결의 핵심.",
     [("삼성전자", "005930.KS"), ("SK하이닉스", "000660.KS"), ("마이크론", "MU"),
      ("CXMT", "중국 上證(2026-07 상장)"), ("난야", "2408.TW")],
     # 정본: Counterpoint 'Global DRAM and HBM Market Share: Quarterly'(2026-09-01 갱신) 공개 표 전재.
     #   ※ 같은 기관 보도자료(2026-08-03)는 2Q26 을 삼성 39·SK 26·MU 25 로 적었으나(반올림·개정 차),
     #     분기 트래커 표를 정본으로 채택한다. 기타(Others) 1~2% 는 생략.
     [("2025-06", {"삼성전자": 33, "SK하이닉스": 39, "마이크론": 22, "CXMT": 4, "난야": 1},
       "2Q25 — SK하이닉스 1위(39%)"),
      ("2025-09", {"삼성전자": 33, "SK하이닉스": 33, "마이크론": 26, "CXMT": 5, "난야": 1},
       "3Q25 — 삼성·SK 공동 1위(33%), 마이크론 26% 로 최고치"),
      ("2025-12", {"삼성전자": 36, "SK하이닉스": 32, "마이크론": 22, "CXMT": 8, "난야": 2},
       "4Q25 — ★ 삼성 1위 탈환, CXMT 5→8% 급증"),
      ("2026-03", {"삼성전자": 38, "SK하이닉스": 29, "마이크론": 22, "CXMT": 8, "난야": 2},
       "1Q26 — 삼성 38%, SK 29% 로 격차 9%p"),
      ("2026-06", {"삼성전자": 38, "SK하이닉스": 25, "마이크론": 24, "CXMT": 10, "난야": 2},
       "2Q26 — 격차 13%p 로 확대 · CXMT 첫 두 자릿수(+716% YoY) · 마이크론 SK 와 1%p 차 · 시장 자체는 QoQ +57%/YoY +385%")],
     None, "Counterpoint 'Global DRAM and HBM Market Share: Quarterly'(2026-09-01판) — 매출 기준 분기 집계"),
    ("hbm", "B", "HBM 점유 (SK하이닉스·삼성·마이크론·CXMT)", "%", "분기",
     "엔비디아 퀄·배분 뉴스가 3사 주가 즉발 변수 — 삼성 반격 폭이 SK하이닉스 프리미엄을 결정. "
     "교차검증 경로: SK하이닉스 실적발표(DRAM 내 HBM 매출 비중)·마이크론 실적발표(HBM 매출액 공시)로 "
     "매출 기준 점유를 재계산 가능(삼성은 미공시 — 3사 완결은 기관 집계 필요). "
     "중국 CXMT 는 HBM3E 소량 생산 개시(2026-08) — 웨이퍼 공급 기준 ~1%(2025)→12%(2028E, SemiAnalysis)",
     [("SK하이닉스", "000660.KS"), ("삼성전자", "005930.KS"), ("마이크론", "MU"), ("CXMT", "중국 上證(2026-07 상장)")],
     # (2026-09-02 정본 교체) 옛 자동 시계열(Silicon Analysts)은 API 스스로 editorial estimate 라
     # 명시한 추정치였고 마이크론 8%가 기관 집계(~21%)와 크게 어긋나 폐기(auto 해제).
     # 정본: Counterpoint Research 'Global DRAM and HBM Market Share: Quarterly' —
     # 매출 기준 분기 집계(공개 페이지 실측 전재 2026-06-08판). CXMT 는 HBM 표 미등재(점유 미미).
     [("2025-03", {"SK하이닉스": 69, "삼성전자": 13, "마이크론": 18}, "Counterpoint 매출 기준 분기 집계"),
      ("2025-06", {"SK하이닉스": 64, "삼성전자": 15, "마이크론": 21}, "Counterpoint 매출 기준 분기 집계"),
      ("2025-09", {"SK하이닉스": 56, "삼성전자": 23, "마이크론": 21}, "Counterpoint 매출 기준 분기 집계"),
      ("2025-12", {"SK하이닉스": 57, "삼성전자": 22, "마이크론": 21}, "Counterpoint 매출 기준 분기 집계"),
      ("2026-06", {"SK하이닉스": 50, "삼성전자": 33, "마이크론": 18},
       "2Q26 실측 — ★ 삼성 21→33%(+12%p) 급반격, SK 리드 37%p→17%p 로 반토막. "
       "HBM3E 가격 하락·HBM4 출시 지연이 SK 를 직격(HBM 비중 최대 + LTA 가격상한에 묶임)"),
      ("2026-03", {"SK하이닉스": 58, "삼성전자": 21, "마이크론": 21, "CXMT": 1},
       "Counterpoint 분기 집계 — CXMT 는 HBM 표 미등재, 웨이퍼 공급 ~1%(E)로 병기")],
     None, "Counterpoint Research 분기 실측(매출 기준) — counterpointresearch.com/insights/global-dram-and-hbm-market-share"),
    ("ai_chip", "B", "AI 서버 출하 비중 (GPU vs 커스텀 ASIC)", "%", "분기",
     "ASIC 성장률이 GPU의 3배(+44.6% vs +16.1%) — 2030년 ASIC 40% 전망, 엔비디아 멀티플 압박·브로드컴 수혜의 제로섬. 매출 기준으론 엔비디아 ~86%(2025)로 여전히 압도",
     [("GPU(엔비디아)", "NVDA"), ("커스텀 ASIC", "AVGO")],
     # (2026-09-04) 연도 시계열 확보 — 트렌드포스 AI 서버 연간 전망·실측(출하 '대수' 기준)
     [("2024-12", {"GPU(엔비디아)": 71.0, "커스텀 ASIC": 26.0}, "2024 실측 — ASIC 26%"),
      ("2026-12", {"GPU(엔비디아)": 69.7, "커스텀 ASIC": 27.8},
       "2026 전망 — ASIC 성장률 +44.6% vs GPU +16.1%(성장률은 3배지만 절대 점유는 아직 GPU 압도). "
       "※ 2025는 트렌드포스가 GPU/ASIC 분해치를 공표하지 않아 비움(추정 기입 안 함)")],
     None, "트렌드포스 AI 서버 전망 — 출하 대수 기준(매출 기준 아님) 주의"),
    ("foundry", "B", "파운드리 매출 점유", "%", "분기",
     "선단공정 수주 배분 — TSMC 점유가 오히려 확대(67→72%) 중, 고착이 유지되는 한 TSM 멀티플의 바닥 논리",
     [("TSMC", "TSM"), ("삼성 파운드리", "005930.KS"), ("SMIC", "0981.HK")],
     # (2026-09-04) 분기 시계열 확보 — 트렌드포스가 매 분기 톱10 파운드리 매출·점유를 공표한다.
     [("2024-12", {"TSMC": 67.1, "삼성 파운드리": 8.1}, "4Q24 실측"),
      ("2025-03", {"TSMC": 67.6, "삼성 파운드리": 7.7}, "1Q25 실측 — TSMC 255억$·삼성 28.9억$"),
      ("2025-06", {"TSMC": 70.2, "삼성 파운드리": 7.3, "SMIC": 5.1},
       "2Q25 실측 — 업계 매출 QoQ +14.6% 사상 최대(TSMC 302.4억$)"),
      ("2025-09", {"TSMC": 71.0, "삼성 파운드리": 6.8, "SMIC": 5.1}, "3Q25 실측 — 톱10 합계 451억$"),
      ("2025-12", {"TSMC": 72.0, "삼성 파운드리": 6.5, "SMIC": 5.0}, "4Q25 실측 — TSMC 359억$"),
      ("2026-03", {"TSMC": 72.3, "삼성 파운드리": 6.5, "SMIC": 5.1}, "1Q26 실측 — 톱10 합계 사상 최대")],
     None, "트렌드포스 분기 보도"),
    ("tester", "B", "SoC 테스터 점유 (어드밴테스트)", "%", "반기",
     "HBM·AI 테스터 승부 — 어드밴 56→66%로 확대 중(⚪⚠ 판정의 반증 데이터), 매출 기준 테라다인의 2배",
     [("어드밴테스트", "6857.T"), ("테라다인", "TER")],
     # (2026-09-04) 시계열 확보 — 어드밴테스트 IR 자료의 연도별 SoC 테스터 점유 실측.
     #   ⚠ 테라다인은 개별 %를 공표하지 않는다(양사 합산 ~80%만 공개) → 단일 선으로 그린다.
     [("2023-12", {"어드밴테스트": 59}, "CY23 — 사측 실측(전체 테스터 기준 58%)"),
      ("2024-12", {"어드밴테스트": 56}, "CY24 — 사측 실측, 양사 합산 전체 테스터 ~80%"),
      ("2025-12", {"어드밴테스트": 66}, "CY25 — 사측 실측, 1년 새 +10%p (AI·HBM 테스터 수요)")],
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
    ("orexin", "B", "오렉신(OX2R) 수면장애 개발 단계 경쟁", "단계", "분기",
     "'비만약 다음 먹거리'의 최전선 — 릴리가 Centessa를 78억$에 산 이유. 릴리vs노보의 2023년(출시 직전) 국면과 같은 구도라, "
     "점유율이 아직 없는 지금은 개발 단계로 추적한다. "
     "단계 척도: 1=Ph1 · 2=Ph2 진행 · 3=Ph2 성공 · 4=Ph3/등록임상 진행 · 5=Ph3 성공 · 6=NDA 접수 · 7=FDA 승인 · 8=다국가 승인. "
     "다케다가 first-in-class 선점(2026-08 FDA), 릴리는 NT2·특발성과다수면까지 노린 적응증 확장으로 추격",
     [("다케다", "4502.T"), ("릴리(Centessa)", "LLY"), ("알케르메스", "ALKS")],
     [("2025-09", {"다케다": 5, "릴리(Centessa)": 3, "알케르메스": 3},
       "World Sleep 2025 — 릴리(ORX750)·알케르메스(Vibrance-1) Ph2 성공 / 다케다는 Ph3 FirstLight·RadiantLight 전 지표 충족"),
      ("2026-02", {"다케다": 6, "알케르메스": 4},
       "다케다 NDA 접수·우선심사(PDUFA 3Q26) / 알케르메스 BTD 획득(1월)·Ph3 Brilliance 개시(1Q26, NT1 302·304·NT2 303)"),
      ("2026-06", {"다케다": 6, "릴리(Centessa)": 4, "알케르메스": 4},
       "릴리 등록 Ph2/3 개시(5.29 · NCT07598708 · 222명) — Centessa 인수 완료(6.24)"),
      ("2026-08", {"다케다": 8, "릴리(Centessa)": 4, "알케르메스": 4},
       "다케다 Orzeyful FDA 승인(8.5) — 中 NMPA 7월 승인에 이은 2번째 시장. 세계 최초 오렉신 작용제")],
     None, "각사 공시·FDA/NMPA 승인 발표·ClinicalTrials.gov — 알케르메스 Vibrance-3(특발성과다수면 Ph2)·다케다 TAK-360(2세대)은 별도 진행"),
    ("cowos", "C", "TSMC CoWoS 패키징 캐파 (천 장/월)", "천장/월", "분기",
     "엔비디아 출하량의 물리적 상한 — 13→35→75→130천장으로 매년 배증, 수급갭 20%→10% 축소 중(공급 부족 완화가 곧 출하 성장)",
     [("TSMC", "TSM"), ("Amkor", "AMKR")],
     [("2023-12", {"TSMC": 13, "Amkor": 5}, "(E) 시장조사 정리치"),
      ("2024-12", {"TSMC": 35}, "실측 — 트렌드포스"),
      ("2025-12", {"TSMC": 75}, "실측 — 계획 달성(75~80천장)"),
      ("2026-12", {"TSMC": 130}, "계획(E) 120~140천장 — OSAT 합산 시 업계 ~200천장")],
     None, "트렌드포스·노마드세미 — 2026은 계획치"),
    ("hbm_capa", "C", "HBM(TSV) 웨이퍼 캐파 (천 장/월)", "천장/월", "반기",
     "캐파 배분 발표가 곧 내년 매출 — 삼성 250천장 계획(+47%)이 실행되면 HBM 점유 배틀의 선행 신호",
     [("삼성전자", "005930.KS"), ("SK하이닉스", "000660.KS")],
     [("2024-12", {"삼성전자": 130, "SK하이닉스": 120}, "트렌드포스 집계 실측"),
      ("2025-12", {"삼성전자": 170, "SK하이닉스": 150}, "삼성 실측·SK 역산(E)"),
      ("2026-12", {"삼성전자": 250}, "계획(E) — SK는 미공표(2H26 D램 캐파 2배 보도만)")],
     None, "트렌드포스 — 캐파≠수율·양산승인 주의"),
    ("transformer", "C", "초고압 변압기 수주잔고 (조원)", "조원", "분기",
     "수년치 백로그라 캐파·수주 증가분 = 확정 매출 — 두 회사 모두 매 분기 잔고 신기록 경신 중",
     [("HD현대일렉트릭", "267260.KS"), ("효성중공업", "298040.KS")],
     [("2023-12", {"HD현대일렉트릭": 7.2, "효성중공업": 5.8}, "실측(효성=중공업 부문 기준)"),
      ("2024-12", {"효성중공업": 11.2}, "실측"),
      ("2025-09", {"HD현대일렉트릭": 9.8}, "3Q25 실측"),
      ("2026-03", {"HD현대일렉트릭": 11.5, "효성중공업": 15.1}, "1Q26 실측 — 효성 분기 최대 신규수주 4.17조")],
     None, "각사 실적 발표·보도 — 효성은 부문/전사 기준 혼재 주의"),
    ("haleu", "C", "센트러스 HALEU 누적 생산 (kg)", "kg", "반기",
     "캐파가 곧 계약 — 美 유일 HALEU 농축, DOE 지원 증설 실행이 SMR 연료 병목 해소·LEU 실적의 선행",
     [("센트러스", "LEU")],
     [("2023-11", {"센트러스": 20}, "美 최초 생산 실측"),
      ("2025-06", {"센트러스": 920}, "Phase II 900kg 인도 완료 실측"),
      ("2026-06", {"센트러스": 1900}, "추가 900kg 2주 조기 완료 실측")],
     None, "DOE·사측 발표 — 2029년 상업 규모 설비 목표"),
    ("launch", "C", "궤도 발사 횟수 (연간)", "회", "반기",
     "발사 캐던스 = 스타링크·위성 매출의 물리량 — 스페이스X 연 165회(전세계 절반), 로켓랩 뉴트론 가세가 관전점",
     [("스페이스X", "SPCX"), ("로켓랩", "RKLB")],
     # (2026-09-04) 시계열 확보 — 양사 연간 발사 실적(스페이스X 궤도발사·로켓랩 일렉트론).
     [("2022-12", {"스페이스X": 61, "로켓랩": 9}, "2022 실측"),
      ("2023-12", {"스페이스X": 96, "로켓랩": 9}, "2023 실측"),
      ("2024-12", {"스페이스X": 134, "로켓랩": 14}, "2024 실측"),
      ("2025-12", {"스페이스X": 165, "로켓랩": 21},
       "2025 실측 — 스페이스X 전세계 궤도발사의 52%, 로켓랩 연간 최다·성공률 100%")],
     None, "각사 발표·연간 발사 집계 — 두산 SMR 연 20기·GEV 터빈 슬롯은 공표 시계열 생기면 추가 예정"),
    ("cdmo", "C", "CDMO 생산 캐파 (만L)", "만L", "반기",
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


def _edgar_seg(cik, keyword, tagpat, n=9):
    """SEC 공시 원문에서 '부문(세그먼트)별 분기 매출'을 파싱해 {기말: 십억$}.

    ⚠ XBRL companyfacts/companyconcept API 는 차원(세그먼트) 없는 연결 수치만 준다 —
      부문 값은 공시 HTML 의 컨텍스트를 직접 읽어야 한다.
    ⚠ 같은 분기에 여러 사실이 잡히면(제품·시점 축이 겹친 하위 항목) 최댓값을 부문 총매출로 본다.
      단일 차원만 허용하면 AMD 처럼 축이 2개인 회사가 하위 항목을 물어 3.5 → 0.5 로 깨진다(실측 확인).
    """
    import re as _re, datetime as _d
    UA = "namoobi-market-report namoobi@gmail.com"

    def _get(u, to=150):
        try:
            return subprocess.run(["curl", "-s", "--compressed", "--max-time", str(to),
                                   "-H", "User-Agent: " + UA, u],
                                  capture_output=True, text=True, timeout=to + 10).stdout or ""
        except Exception:
            return ""
    try:
        j = json.loads(_get("https://data.sec.gov/submissions/CIK%s.json" % cik, 30))
    except Exception:
        return {}
    r = j.get("filings", {}).get("recent", {})
    fils = [(f, a.replace("-", ""), p) for f, a, p in
            zip(r.get("form", []), r.get("accessionNumber", []), r.get("primaryDocument", []))
            if f in ("10-Q", "10-K")][:n]
    out = {}
    for f, a, p in fils:
        h = _get("https://www.sec.gov/Archives/edgar/data/%d/%s/%s" % (int(cik), a, p))
        if len(h) < 50000:
            continue
        ctx = {}
        for m in _re.finditer(r'<xbrli:context id="([^"]+)"[^>]*>(.*?)</xbrli:context>', h, _re.S):
            mem = [x.split(":")[-1].replace("Member", "") for x in
                   _re.findall(r'explicitMember dimension="[^"]*">([^<]+)<', m.group(2))]
            sd = _re.search(r"<xbrli:startDate>([^<]+)", m.group(2))
            ed = _re.search(r"<xbrli:endDate>([^<]+)", m.group(2))
            ctx[m.group(1)] = {"mem": mem, "s": sd.group(1) if sd else "", "e": ed.group(1) if ed else ""}
        for m in _re.finditer(r"<ix:nonFraction\b([^>]*)>([^<]*)</ix:nonFraction>", h):
            at, val = m.group(1), m.group(2).strip().replace(",", "")
            if not _re.search(tagpat, at):
                continue
            cr = _re.search(r'contextRef="([^"]+)"', at)
            c = ctx.get(cr.group(1), {}) if cr else {}
            if not any(keyword in x for x in c.get("mem", [])):
                continue
            sc = _re.search(r'scale="(-?\d+)"', at)
            sc = int(sc.group(1)) if sc else 0
            try:
                v = float(val) * (10 ** sc)
            except Exception:
                continue
            s, e = c.get("s", ""), c.get("e", "")
            if not s or not e:
                continue
            try:
                days = (_d.date.fromisoformat(e) - _d.date.fromisoformat(s)).days
            except Exception:
                continue
            if not (80 <= days <= 100):        # 분기 단독만
                continue
            out[e] = max(out.get(e, 0), round(v / 1e9, 1))
        time.sleep(0.3)
    return out


# 브로드컴 'AI 반도체 매출'은 비GAAP 구두 공시라 세그먼트 태그가 없다 → 실적발표 실측 시드.
#   키는 이미 '달력 분기'로 환산해 둔다(브로드컴 회계분기는 11·2·5·8월 종료라 한 분기씩 앞선다).
AVGO_AI = {"2025-Q3": 6.5, "2025-Q4": 8.4, "2026-Q1": 10.8, "2026-Q2": 16.7}


def _cal_q(end, days=91):
    """회계 기말일 → 달력 분기 라벨. 기간의 '중간점'이 속한 분기로 매긴다.

    엔비디아(7/10/1/4월 종료)·AMD(6/9/12/3월)·브로드컴(8/11/2/5월)이 제각각이라
    기말일 그대로 쓰면 같은 실적 분기가 다른 시점에 찍혀 차트가 톱니처럼 흩어진다(실측 확인).
    """
    import datetime as _d
    try:
        mid = _d.date.fromisoformat(end) - _d.timedelta(days=days // 2)
    except Exception:
        return None
    return "%d-Q%d" % (mid.year, (mid.month - 1) // 3 + 1)


def auto_ai_accel():
    """엔비디아·AMD 부문 매출은 SEC 실측 자동, 브로드컴 AI 매출은 실적발표 시드.
    셋 다 달력 분기로 정규화해 같은 시점에 겹쳐 그린다."""
    nv = _edgar_seg("0001045810", "DataCenter", r'name="us-gaap:Revenues"')
    am = _edgar_seg("0000002488", "DataCenter", r"RevenueFromContractWithCustomer")
    q = {}
    for src, lab in ((nv, "엔비디아 데이터센터"), (am, "AMD 데이터센터")):
        for e, v in src.items():
            k = _cal_q(e)
            if k: q.setdefault(k, {})[lab] = v
    for k, v in AVGO_AI.items():
        q.setdefault(k, {})["브로드컴 AI반도체"] = v
    out = []
    for k in sorted(q):
        v = q[k]
        n = "SEC 공시 부문 매출 실측"
        if "브로드컴 AI반도체" in v:
            n += " · 브로드컴은 실적발표 AI 매출(비GAAP)"
        out.append((k, v, n))
    return out


def auto_nvda_cust():
    """엔비디아 고객 집중도 — SEC EDGAR 10-Q/10-K 의 XBRL 을 직접 파싱해 분기 시계열화.

    엔비디아는 개별 10% 이상 고객만 익명(Customer A/1/One…)으로 공시한다.
    ⚠ 라벨은 공시마다 재할당돼 '같은 고객'을 추적할 수 없다 — 순위별 비중만 의미 있다.
    ⚠ 미공시 = 0% 가 아니라 '10% 미만'이다. 그래서 합계 비교는 무의미하고(공시 문턱 때문),
      1위 고객 비중처럼 항상 공시되는 값만 시계열로 비교한다.
    태그명이 공시마다 CustomerA / CustomerOne / RevenueCustomer1 로 달라 정규식으로 흡수한다.
    """
    import re as _re
    UA = "namoobi-market-report namoobi@gmail.com"
    CUST = _re.compile(r"^(?:Revenue)?(?:AccountsReceivable)?Customer"
                       r"(?:[A-H]|\d+|One|Two|Three|Four|Five|Six|Seven|Eight)$")
    BAD = {"NonUs", "SG", "UnitedStatesBasedEndCustomers", "ControlledDataCenterComputeProducts"}

    def _get(u, to=150):
        try:
            return subprocess.run(["curl", "-s", "--compressed", "--max-time", str(to),
                                   "-H", "User-Agent: " + UA, u],
                                  capture_output=True, text=True, timeout=to + 10).stdout or ""
        except Exception:
            return ""
    try:
        j = json.loads(_get("https://data.sec.gov/submissions/CIK0001045810.json", 30))
    except Exception:
        return []
    r = j.get("filings", {}).get("recent", {})
    fils = [(f, a.replace("-", ""), p) for f, a, p in
            zip(r.get("form", []), r.get("accessionNumber", []), r.get("primaryDocument", []))
            if f in ("10-Q", "10-K")][:9]
    q = {}
    for f, acc, doc in fils:
        h = _get("https://www.sec.gov/Archives/edgar/data/1045810/%s/%s" % (acc, doc))
        if len(h) < 50000:
            continue
        ctx = {}
        for m in _re.finditer(r'<xbrli:context id="([^"]+)"[^>]*>(.*?)</xbrli:context>', h, _re.S):
            mem = [x.split(":")[-1].replace("Member", "") for x in
                   _re.findall(r'explicitMember dimension="[^"]*">([^<]+)<', m.group(2))]
            sd = _re.search(r"<xbrli:startDate>([^<]+)", m.group(2))
            ed = _re.search(r"<xbrli:endDate>([^<]+)", m.group(2))
            ctx[m.group(1)] = {"mem": mem, "s": sd.group(1) if sd else "", "e": ed.group(1) if ed else ""}
        for m in _re.finditer(r"<ix:nonFraction\b([^>]*)>([^<]*)</ix:nonFraction>", h):
            at, val = m.group(1), m.group(2).strip()
            if "ConcentrationRiskPercentage1" not in at:
                continue
            cr = _re.search(r'contextRef="([^"]+)"', at)
            c = ctx.get(cr.group(1), {}) if cr else {}
            mem = c.get("mem", [])
            if "CustomerConcentrationRisk" not in mem or (set(mem) & BAD):
                continue
            if "SalesRevenueNet" not in mem or not any(CUST.match(x) for x in mem):
                continue
            try:
                v = int(val)
            except Exception:
                continue
            s, e = c.get("s", ""), c.get("e", "")
            if not s or not e:
                continue
            try:
                days = (datetime.strptime(e, "%Y-%m-%d") - datetime.strptime(s, "%Y-%m-%d")).days
            except Exception:
                continue
            if not (80 <= days <= 100):        # 분기 단독만 (누적 구간은 서로 비교 불가)
                continue
            q.setdefault(e, set()).add(v)
        time.sleep(0.35)
    out = []
    for e in sorted(q):
        vs = sorted(q[e], reverse=True)
        v = {}
        for i, x in enumerate(vs[:4]):
            v["%d위 고객" % (i + 1)] = x
        out.append((e[:7], v, "%d곳이 10%% 이상 (미공시=10%% 미만, 0 아님)" % len(vs)))
    return out


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
        # (2026-09-02 감사) '실측' 라벨 정정 — 원천 API 가 editorial estimate 라고 자체 명시
        out.append((dt_, {"SK하이닉스": m.get("SK Hynix"), "삼성전자": m.get("Samsung"),
                          "마이크론": m.get("Micron")}, "SA 추정(주간 샘플·실측 아님)"))
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
            # (2026-09-02) 시드(트렌드포스 참조점) 유지 + 자동(SA 추정) 병합 — 시드를 버리지 않는다
            series += [{"d": d, "v": v, "note": n} for d, v, n in auto_hbm()]
        elif auto == "amzn":
            ser, players = auto_amzn()
            series = [{"d": d, "v": v, "note": n} for d, v, n in ser]
        elif auto == "ai_accel":
            ser = auto_ai_accel()
            series = [{"d": d, "v": v, "note": n} for d, v, n in ser]
        elif auto == "nvda_cust":
            ser = auto_nvda_cust()
            series = [{"d": d, "v": v, "note": n} for d, v, n in ser]
            players = [(k, "NVDA") for k in ("1위 고객", "2위 고객", "3위 고객", "4위 고객")]
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
