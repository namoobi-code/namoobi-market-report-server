#!/usr/bin/env python3
"""[3.1.9] 지표 메타데이터 — 의미 / 해석방법 / 갱신주기.

모든 지표에 "이게 뭔지 · 어떻게 읽는지 · 언제 바뀌는지" 를 붙인다.
매일 바뀌지 않는 값은 실제 변동 주기를 명시한다 (예: 계약가=월 1회).
보고서·대시보드·docx 가 이 한 곳을 참조한다.
"""

# cadence: 실제 값이 바뀌는 주기 (수집 주기가 아님)
META = {
 # ── 가격 (TrendForce 공개 가격표) ─────────────────────────────
 "dram_spot": {
   "label": "DRAM 현물(스팟) 가격",
   "meaning": "브로커·유통 시장에서 즉시 거래되는 DRAM 칩 가격. 계약가와 달리 수급이 실시간 반영된다.",
   "howto": "계약가보다 먼저 움직이는 선행지표. 스팟이 오르면 다음 달 계약가 인상 압력이 커진다. 반대로 스팟이 꺾이면 사이클 고점 신호.",
   "cadence": "매일 (영업일 18:10 GMT+8 갱신)",
   "source": "TrendForce / DRAMeXchange 공개 가격표",
 },
 "dram_contract": {
   "label": "DRAM 고정거래(계약) 가격",
   "meaning": "제조사↔대형 고객 간 장기 공급 계약 단가. 메모리 3사 실적에 직접 반영되는 가격.",
   "howto": "실적의 실체. 스팟이 아니라 이 가격이 올라야 영업이익이 오른다. 스팟-계약 갭이 클수록 다음 협상에서 오를 가능성이 크다.",
   "cadence": "월 1회 (매월 말 갱신 — 일별로는 안 변한다)",
   "source": "TrendForce",
 },
 "nand_spot": {
   "label": "NAND 현물(스팟) 가격",
   "meaning": "NAND 플래시 칩의 즉시 거래 가격.",
   "howto": "DRAM 현물과 동일한 논리. AI 서버향 SSD 수요가 NAND 사이클을 견인하는지 확인.",
   "cadence": "주 1회 내외 (세션 갱신)",
   "source": "TrendForce",
 },
 "nand_contract": {
   "label": "NAND 고정거래(계약) 가격",
   "meaning": "NAND 장기 공급 계약 단가.",
   "howto": "삼성·SK하이닉스·마이크론의 NAND 부문 실적에 직결. DRAM 대비 회복이 늦으면 NAND가 사이클 후행임을 뜻한다.",
   "cadence": "월 1회 (매월 말 갱신)",
   "source": "TrendForce",
 },
 "spot_contract_gap": {
   "label": "스팟-계약 갭  ★핵심 선행지표",
   "meaning": "현물가 ÷ 계약가 − 1. 즉시 시장이 장기 계약가보다 얼마나 높은 값을 매기는지.",
   "howto": "갭이 크게 벌어지면 → 제조사가 다음 계약 협상에서 가격을 올릴 명분이 생긴다. 즉 '실적 개선이 예약된 상태'. 갭이 좁혀지거나 음수로 가면 인상 사이클 종료 신호.",
   "cadence": "매일 (현물이 매일 변하므로)",
   "source": "계산값 (TrendForce 현물 ÷ 계약)",
 },

 # ── HBM (Silicon Analysts 공개 API) ───────────────────────────
 "hbm_share": {
   "label": "HBM 업체별 점유율",
   "meaning": "HBM 시장에서 SK하이닉스·삼성·마이크론이 차지하는 비중.",
   "howto": "HBM은 마진이 범용 DRAM의 수 배. 점유율 = 이익 점유율에 가깝다. 삼성 점유율이 오르면 삼성 주가 재평가 트리거.",
   "cadence": "분기 1회 내외 (벤더 집계 발표 시)",
   "source": "Silicon Analysts 공개 API · IDC(SK하이닉스 SEC 제출서류 인용)",
 },
 "hbm_asp": {
   "label": "HBM ASP (가속기당 HBM 총액)",
   "meaning": "NVIDIA H100/H200/B200 등 AI 가속기 1대에 탑재되는 HBM의 총 가격.",
   "howto": "세대가 올라갈수록(HBM3→3E→4) 스택당 가격과 탑재량이 함께 늘어 ASP가 계단식 상승. 메모리 3사 매출의 승수 효과.",
   "cadence": "분기 1회 내외 (신제품 출시·계약 갱신 시)",
   "source": "Silicon Analysts 공개 API",
 },
 "hbm_market": {
   "label": "HBM 시장규모 · 수요 증가율",
   "meaning": "HBM 전체 시장의 연간 매출 규모와 수요 증가율(YoY).",
   "howto": "메모리 3사 성장의 천장. 시장 자체가 커지는 속도가 개별 기업 실적의 상한선.",
   "cadence": "연 1~2회 (조사기관 전망 갱신 시)",
   "source": "Yole Group · TrendForce · SK하이닉스 IR",
 },
 "hbm_qual": {
   "label": "HBM 공급 인증 진행상황  ★점유율 선행",
   "meaning": "각 업체가 NVIDIA/AMD 등에 어느 세대 HBM을 어느 단계(qualified → volume_shipping)까지 공급하는지.",
   "howto": "인증 통과 → 양산 출하까지 보통 1~2분기. 즉 지금의 인증 상태가 다음 분기 점유율을 미리 알려준다. 삼성이 신규 qualified 되면 점유율 반등 신호.",
   "cadence": "비정기 (인증·양산 발표 시)",
   "source": "Silicon Analysts 공개 API",
 },
 "hbm_ddr5_gap": {
   "label": "HBM : DDR5 GB당 단가 격차",
   "meaning": "HBM과 범용 DDR5의 GB당 가격 비율.",
   "howto": "통상 HBM이 DDR5의 5~6배. 이 배율이 무너지면(=DDR5가 급등) 공급부족이 HBM보다 범용 DRAM에서 더 극심하다는 뜻 → 범용 DRAM 비중이 큰 삼성에 상대적으로 유리.",
   "cadence": "매일 (DDR5 현물이 매일 변함)",
   "source": "계산값 (TrendForce 현물 ÷ Silicon Analysts HBM 스택가)",
 },

 # ── 선행지표 (Yahoo · 일별) ───────────────────────────────────
 "sox": {
   "label": "필라델피아 반도체지수 (SOX)",
   "meaning": "미국 상장 반도체 30종목 지수. 반도체 업황의 종합 체온계.",
   "howto": "메모리 주가는 SOX와 동행하되 사이클 후반에 더 크게 움직인다. SOX가 꺾이는데 메모리만 오르면 고점 경계.",
   "cadence": "매일 (미국장)",
   "source": "Yahoo Finance ^SOX",
 },
 "hbm_demand_proxy": {
   "label": "HBM 수요처 주가 (NVDA·AMD·TSM)  ★수요 선행",
   "meaning": "HBM을 사가는 쪽(엔비디아·AMD)과 패키징 병목(TSMC CoWoS)의 주가.",
   "howto": "수요처가 먼저 오르고 메모리가 따라가는 게 정상. TSMC CoWoS 증설은 HBM 출하의 물리적 상한 → TSM 강세는 HBM 물량 확대 신호.",
   "cadence": "매일",
   "source": "Yahoo Finance NVDA · AMD · TSM",
 },
 "mem_vs_gpu": {
   "label": "메모리 / GPU 상대강도  ★가치 이동",
   "meaning": "마이크론 주가 상승률 ÷ 엔비디아 주가 상승률 (1년).",
   "howto": "1 초과 = 가치가 수요처(GPU)에서 공급자(메모리)로 이동 중 = 공급부족이 심화되어 메모리가 협상력을 쥐었다는 뜻. 이 비율이 꺾이면 공급부족 완화 신호.",
   "cadence": "매일",
   "source": "계산값 (Yahoo MU ÷ NVDA)",
 },
 "kospi_concentration": {
   "label": "코스피 (삼성+SK 시총 55~60%)",
   "meaning": "코스피 지수. 삼성전자+SK하이닉스가 시총의 절반 이상.",
   "howto": "메모리 사이클이 곧 코스피. 역으로 코스피 급락은 메모리 고점 논쟁의 신호.",
   "cadence": "매일 (한국장)",
   "source": "Yahoo Finance ^KS11",
 },
 "kr_semi_export": {
   "label": "한국 반도체 수출액  ★실물 확증",
   "meaning": "관세청 10일 단위 잠정치. 실제로 배에 실려 나간 금액.",
   "howto": "가격·주가는 기대를 반영하지만 이건 실물. 가격이 오르는데 수출액이 안 따라오면 '가격만 오르고 물량은 안 나가는' 위험 신호. 현재 YoY +196.9% 로 가격·물량이 동반 확장 중.",
   "cadence": "월 3회 (1~10일분=11일 · 1~20일분=21일 · 월전체=익월 1일)",
   "source": "관세청 오픈API (db/customs)",
 },

 # ── 밸류에이션 (Yahoo) ────────────────────────────────────────
 "valuation": {
   "label": "메모리 3사 EPS · PER",
   "meaning": "SK하이닉스·삼성전자·마이크론의 현재가와 연도별 컨센서스 EPS로 계산한 PER.",
   "howto": "메모리는 사이클 산업이라 이익 정점에서 PER이 가장 낮게 보인다(PER 함정). PER이 낮다고 싸다고 보면 안 되고, EPS 컨센서스의 방향(상향/하향)을 함께 봐야 한다.",
   "cadence": "주가=매일 · EPS 컨센서스=수시 (실적 발표 전후 집중)",
   "source": "Yahoo Finance (PER = 현재가 ÷ EPS 직접 계산)",
 },
}

def get(key):
    return META.get(key, {})

def cadence(key):
    return (META.get(key) or {}).get("cadence", "")

if __name__ == "__main__":
    for k, v in META.items():
        print(f"\n【{v['label']}】  ({k})")
        print(f"  주기 : {v['cadence']}")
        print(f"  의미 : {v['meaning']}")
        print(f"  해석 : {v['howto']}")
        print(f"  출처 : {v['source']}")
