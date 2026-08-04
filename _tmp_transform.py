import json, copy

BASE_HBM = 'data/nmr_hbm.json'
BASE_SEMI = 'db/semi_cycle.json'
OUT_HBM = '/sessions/tender-clever-hawking/mnt/outputs/nmr_build_0606/nmr_hbm.json'
OUT_SEMI = '/sessions/tender-clever-hawking/mnt/outputs/nmr_build_0606/nmr_semi_cycle.json'

with open(BASE_HBM, encoding='utf-8') as f:
    hbm = json.load(f)
with open(BASE_SEMI, encoding='utf-8') as f:
    semi = json.load(f)

TODAY = "2026-07-30"

# ============ nmr_hbm.json updates ============
hbm['asof'] = TODAY
hbm['source'] += ("; [2026-07-30 갱신] SK hynix Newsroom(2Q26 실적발표, 2026-07-29) + PRNewswire/StockTitan/BigGo Finance/한국경제/헤럴드경제/아주경제/한국일보 교차검증; "
                   "Yahoo Finance(UsStockInfo MCP) 2026-07-29 정규장 종가 재조회(SK하이닉스·삼성전자·Micron·KOSPI지수); "
                   "TrendForce DRAM/NAND Spot Price 2026-07-29 18:10(GMT+8) 세션 직접 재조회(web_fetch)")

def add_note(obj, text):
    obj['note'] = obj.get('note', '') + ' ' + text

# DDR5 16Gb spot
prev_ddr5 = hbm['ddr5_16gb']['value_usd']
hbm['ddr5_16gb']['value_usd'] = 50.933
hbm['ddr5_16gb']['change_pct_session'] = 0.0
hbm['ddr5_16gb']['asof'] = "2026-07-29 18:10 GMT+8"
add_note(hbm['ddr5_16gb'], f"[2026-07-30 점검] TrendForce DRAM Spot Price 페이지 직접 재조회(web_fetch) 결과 Last Update가 2026-07-29 18:10(GMT+8)로 갱신됨을 확인, 세션평균 $50.933(TrendForce 자체표시 Session Change 0.00%, 직전 스냅샷 ${prev_ddr5}/07-27 대비 자체계산 시 약 +0.20%)로 소폭 상향.")

# DDR4 8Gb spot
prev_ddr4 = hbm['ddr4_8gb']['value_usd']
hbm['ddr4_8gb']['value_usd'] = 42.041
hbm['ddr4_8gb']['change_pct_session'] = -0.09
hbm['ddr4_8gb']['asof'] = "2026-07-29 18:10 GMT+8"
add_note(hbm['ddr4_8gb'], f"[2026-07-30 점검] TrendForce DRAM Spot Price 페이지 직접 재조회(web_fetch) 결과 Last Update 2026-07-29 18:10(GMT+8) 갱신 확인, 세션평균 $42.041(TrendForce 자체표시 Session Change ▼-0.09%, 직전 스냅샷 ${prev_ddr4}/07-27 대비 소폭 하락).")

# NAND MLC 64Gb spot - unchanged
add_note(hbm['nand_mlc_64gb'], "[2026-07-30 점검] TrendForce NAND Flash Spot Price 페이지 직접 재조회(web_fetch) 결과 Last Update 2026-07-20 14:40(GMT+8)로 동일(갱신 없음), 세션평균 $32.565 변동 없음.")

# gap_ratio recompute
new_ddr5 = hbm['ddr5_16gb']['value_usd']
new_ddr4 = hbm['ddr4_8gb']['value_usd']
new_ratio = round(new_ddr5 / new_ddr4, 2)
new_prem = round((new_ddr5/new_ddr4 - 1) * 100, 1)
hbm['gap_ratio']['value'] = new_ratio
hbm['gap_ratio']['value_pct_premium'] = f"+{new_prem}%"
hbm['gap_ratio']['asof'] = TODAY
add_note(hbm['gap_ratio'], f"[2026-07-30 재계산] ddr5_16gb(${new_ddr5}, 07-29 18:10 GMT+8 세션)·ddr4_8gb(${new_ddr4}, 동일세션) 갱신값 기준 재산출, {new_ratio}(+{new_prem}%).")

# eps_per updates: price refresh with data-vendor-confirmed closes (Yahoo Finance via UsStockInfo MCP), EPS consensus carried forward (no verified vendor change)
for entry in hbm['eps_per']:
    if entry['name'] == 'SK하이닉스':
        entry['price'] = 1401000
        entry['asof'] = TODAY
        new_per = round(1401000/entry['eps_2026E'], 2)
        add_note(entry, (
            "[2026-07-30 점검] SK하이닉스 2026년 2분기(2Q26) 실적이 2026-07-29 확정 발표됨(SK hynix Newsroom 공식 발표, PRNewswire/StockTitan/한국경제/헤럴드경제/아주경제/한국일보 교차검증): "
            "연결기준 매출 79조3187억원(YoY +256.8%)·영업이익 60조5426억원(YoY +557.2%, 상반기 누적 98조1529억원)·순이익 93조9226억원(YoY +1242.5%) - 매출·영업이익·순이익 모두 분기 사상 최고치, 영업이익률 76%(1분기 72%에서 확대). "
            "다만 사전 컨센서스(14개 국내 증권사 평균 매출 84.1조원·영업이익 64.1조원) 대비로는 매출 -5.7%·영업이익 -5.6% 미달(시장 기대치 하회, 한국일보 등 보도 제목 '예상치 밑돌아'); 반면 한국투자증권이 7/13 발표한 보수적 자체 추정치(영업이익 60.4조원, 컨센서스 대비 8% 낮춰 잡음)와는 거의 일치. "
            "매우 중요: 2026년 연간 CAPEX(설비투자) 공식 가이던스를 최초로 공개 - '40조원대 후반' 수준으로 예상한다고 컨퍼런스콜(7/29)에서 밝힘(머니투데이·아시아경제·뉴스핌·ZDNet코리아·파이낸셜뉴스·한국경제 등 교차확인); 전년(2025년) 설비투자 30조1730억원 대비 최소 15조원 이상 증가(YoY 약 +50~62%, 40조원대 후반을 47~49조원 구간으로 볼 때). M15X 팹 양산 일정 조기화, 2027년초 오픈 예정인 용인팹 1기 클린룸 이후 생산능력 신속 확대를 위한 선제 투자 포함. 약 10개 고객사(NVIDIA 포함)와 5년 장기공급계약(LTA) 체결도 공개 - 수요 가시성 근거. HBM4는 양산을 개시했으며 수율이 기존 HBM3E 성숙 수준에 근접했다고 밝힘; HBM4E 샘플은 주요 고객사에 이미 출하 완료. 3Q26 가이던스로 DRAM ASP QoQ 약 +30%·NAND ASP QoQ 약 +50%대 중반·DRAM 비트성장 약 +10%QoQ를 제시(Wall St Engine/BigGo Finance 인용, 1차 컨퍼런스콜 원문 교차검증 필요 항목으로 참고용 병기). "
            "주가는 실적 발표를 전후로 이틀 연속 급락: 2026-07-28(화) 1,550,000원(-14.65%, 전일 1,816,000원 대비) → 2026-07-29(수, 실적발표 당일) 1,401,000원(-9.61%) - Yahoo Finance(UsStockInfo MCP) regularMarketPrice/regularMarketPreviousClose 직접조회로 확정. 이틀간 누적 -22.85%. 사상 최대 실적과 사상 최대 CAPEX 증액(공급부족 지속 시사)에도 불구하고 주가가 급락한 것은 (1)이미 높아진 컨센서스 눈높이 대비 미달, (2)AI 밸류에이션 재평가 심리가 겹친 결과로 해석되며, 실물 계약가·공급 지표(TrendForce DRAM 현물가 등)는 이번 세션에도 소폭 변동에 그쳐 반전 신호는 없음(상세는 nmr_semi_cycle.json 참조). "
            f"EPS 컨센서스(2026E~2028E)는 이번 분기실적이 연간 EPS 데이터벤더 컨센서스로 아직 반영되지 않아(FnGuide JS렌더링 문제 지속, 영업이익 등 원화총액 지표만으로는 EPS 환산 근거 불충분, 추정 금지 원칙) 기존값(317,929/442,984/431,572) 유지. PER(2026E)은 1,401,000/317,929={new_per}배로 재계산(직전 5.71배 대비 valuation 크게 낮아짐, 주가 급락 반영)."
        ))
    elif entry['name'] == '삼성전자':
        entry['price'] = 208500
        entry['asof'] = TODAY
        new_per = round(208500/entry['eps_2026E'], 2)
        add_note(entry, (
            "[2026-07-30 점검] 삼성전자 주가는 SK하이닉스와 동반 이틀 연속 급락: 2026-07-28(화) 220,000원(-13.4%, 전일 254,000원 대비) → 2026-07-29(수) 208,500원(-5.23%) - Yahoo Finance(UsStockInfo MCP) regularMarketPrice/regularMarketPreviousClose 직접조회로 확정. 이틀간 누적 -17.9%. "
            "삼성전자는 2026년 2분기 잠정실적(매출 171조원·영업이익 89.4조원, 사업부별 미공개)을 이미 7/7 발표했으며, 사업부별(반도체 DS·모바일·디스플레이) 확정 실적은 2026-07-30(오늘) 발표 예정이었으나 본 점검 시점 기준 확정 수치는 확인되지 않음(빈값 처리, 다음 점검에서 갱신). "
            f"EPS 컨센서스는 데이터벤더 갱신 근거 불충분으로 기존값(46,664/65,802/65,907) 유지. PER(2026E)은 208,500/46,664={new_per}배로 재계산(직전 5.44배 대비 하락)."
        ))
    elif entry['name'] == 'Micron':
        entry['price'] = 739.00
        entry['asof'] = TODAY
        new_per = round(739.00/entry['eps_2026E'], 2)
        add_note(entry, (
            "[2026-07-30 점검] Micron도 SK하이닉스 실적 발표를 전후로 동반 급락: 2026-07-28(화, 미국시장) $820.53(-8.85%, 전일 $900.20 대비) → 2026-07-29(수) $739.00(-9.94%) → 시간외(postmarket) $710.65(-3.84% 추가) - Yahoo Finance(UsStockInfo MCP) regularMarketPrice/regularMarketPreviousClose/postMarketPrice 직접조회로 확정(정규장 기준 이틀간 누적 -17.9%, 시간외 반영 시 약 -21.1%). "
            "StockAnalysis.com 기준 EPS 컨센서스(FY2026E 73.44/FY2027E 153.74)는 재조회 결과 변동 없음(데이터벤더 갱신 근거 불충분, 기존값 유지). "
            f"PER(FY2026E, 정규장 종가 기준)은 739.00/73.44={new_per}배로 재계산(직전 12.26배 대비 크게 하락, 시간외가 기준이면 710.65/73.44=9.68배)."
        ))

# hbm.share / hbm_market / hbm_shipment / hbm3e_price / hbm4_price + top-level mirrors: no new data found, add re-check note (both nested and top-level, since they mirror)
def recheck_note(obj, extra=""):
    add_note(obj, f"[2026-07-30 재확인] TrendForce Press Center·Counterpoint 공식페이지·Silicon Analysts 재점검 결과 신규 발표 없음. 기존값 유지.{extra}")
    obj['asof'] = TODAY

for path in [hbm['share'], hbm['hbm']['share']]:
    recheck_note(path)
for path in [hbm['hbm_market'], hbm['hbm']['hbm_market']]:
    recheck_note(path)
for path in [hbm['hbm_shipment'], hbm['hbm']['hbm_shipment']]:
    recheck_note(path)
for path in [hbm['hbm3e_price'], hbm['hbm']['hbm3e_price']]:
    recheck_note(path)
for path in [hbm['hbm4_price'], hbm['hbm']['hbm4_price']]:
    recheck_note(path, " 다만 SK하이닉스는 2026-07-29 2Q26 컨퍼런스콜에서 HBM4 양산 개시(수율 HBM3E 근접) 및 HBM4E 샘플 주요고객 출하완료를 공식 확인(정성적 정보, ASP 레인지 자체 변경 근거는 아님).")

# spot_index snapshot refresh
hbm['spot_index']['ddr5_16gb_usd'] = new_ddr5
hbm['spot_index']['ddr4_8gb_usd'] = new_ddr4
hbm['spot_index']['nand_mlc_64gb_usd'] = hbm['nand_mlc_64gb']['value_usd']
hbm['spot_index']['asof'] = "2026-07-29 18:10 GMT+8"
add_note(hbm['spot_index'], "[2026-07-30 갱신] ddr5_16gb/ddr4_8gb 최신 세션값(07-29 18:10 GMT+8)으로 스냅샷 갱신, nand_mlc_64gb는 변동없음(07-20 14:40 GMT+8 세션 유지).")

# sources[] append new entries
new_sources = [
    {"item": "SK하이닉스 2Q26 매출(확정 실적)", "value": "79조3187억원(YoY +256.8%)", "source": "SK hynix Newsroom(2026-07-29 공식 발표), 한국경제/헤럴드경제 교차검증", "url": "https://news.skhynix.co.kr/q2-2026-business-results/", "asof": "2026-07-29", "type": "actual"},
    {"item": "SK하이닉스 2Q26 영업이익(확정 실적)", "value": "60조5426억원(YoY +557.2%, 컨센서스 64.1조원 대비 -5.6% 미달)", "source": "SK hynix Newsroom(2026-07-29 공식 발표), 한국일보/아주경제 교차검증", "url": "https://news.skhynix.co.kr/q2-2026-business-results/", "asof": "2026-07-29", "type": "actual"},
    {"item": "SK하이닉스 2Q26 순이익(확정 실적)", "value": "93조9226억원(YoY +1242.5%)", "source": "SK hynix Newsroom(2026-07-29 공식 발표), 헤럴드경제 교차검증", "url": "https://biz.heraldcorp.com/article/10823557", "asof": "2026-07-29", "type": "actual"},
    {"item": "SK하이닉스 2026년 연간 CAPEX 공식 가이던스(신규 공개)", "value": "40조원대 후반(전년 30조1730억원 대비 최소 +15조원, YoY 약 +50~62%)", "source": "SK하이닉스 2Q26 컨퍼런스콜(2026-07-29), 머니투데이/아시아경제/뉴스핌/ZDNet코리아/파이낸셜뉴스 교차검증", "url": "https://www.mt.co.kr/industry/2026/07/29/2026072909115447110", "asof": "2026-07-29", "type": "guidance"},
    {"item": "SK하이닉스 주가(종가)", "value": 1401000, "source": "Yahoo Finance(UsStockInfo MCP) 직접조회, 2026-07-29 정규장 종가(전일종가 1,550,000원 대비 -9.61%)", "url": "https://stockanalysis.com/quote/krx/000660/", "asof": "2026-07-29", "type": "quote"},
    {"item": "SK하이닉스 주가(종가, 7/28)", "value": 1550000, "source": "Yahoo Finance(UsStockInfo MCP) 직접조회, 2026-07-28 정규장 종가(전일종가 1,816,000원 대비 -14.65%)", "url": "https://stockanalysis.com/quote/krx/000660/", "asof": "2026-07-28", "type": "quote"},
    {"item": "삼성전자 주가(종가)", "value": 208500, "source": "Yahoo Finance(UsStockInfo MCP) 직접조회, 2026-07-29 정규장 종가(전일종가 220,000원 대비 -5.23%)", "url": "https://stockanalysis.com/quote/krx/005930/", "asof": "2026-07-29", "type": "quote"},
    {"item": "삼성전자 주가(종가, 7/28)", "value": 220000, "source": "Yahoo Finance(UsStockInfo MCP) 직접조회, 2026-07-28 정규장 종가(전일종가 254,000원 대비 -13.4%)", "url": "https://stockanalysis.com/quote/krx/005930/", "asof": "2026-07-28", "type": "quote"},
    {"item": "Micron 주가(종가)", "value": 739.00, "source": "Yahoo Finance(UsStockInfo MCP) 직접조회, 2026-07-29 정규장 종가(전일종가 $820.53 대비 -9.94%, 시간외 $710.65 추가하락)", "url": "https://stockanalysis.com/stocks/mu/", "asof": "2026-07-29", "type": "quote"},
    {"item": "KOSPI 지수(종가)", "value": 5663.24, "source": "Yahoo Finance(UsStockInfo MCP) 직접조회(^KS11), 2026-07-29 종가(전일종가 6,023.66 대비 -5.98%, 장중 매도사이드카 발동)", "url": "https://finance.yahoo.com/quote/%5EKS11/", "asof": "2026-07-29", "type": "quote"},
    {"item": "DRAM DDR5 16Gb 현물가(세션평균)", "value": 50.933, "source": "TrendForce DRAM Spot Price (DRAMeXchange)", "url": "https://www.trendforce.com/price/dram/dram_spot", "asof": "2026-07-29 18:10 GMT+8", "type": "actual"},
    {"item": "DRAM DDR4 8Gb 현물가(세션평균)", "value": 42.041, "source": "TrendForce DRAM Spot Price (DRAMeXchange)", "url": "https://www.trendforce.com/price/dram/dram_spot", "asof": "2026-07-29 18:10 GMT+8", "type": "actual"},
]
hbm['sources'].extend(new_sources)

with open(OUT_HBM, 'w', encoding='utf-8') as f:
    json.dump(hbm, f, ensure_ascii=False, indent=1)

print("HBM OK, sources len:", len(hbm['sources']))

# ============ nmr_semi_cycle.json updates ============
d = semi['data']
d['asof'] = TODAY
semi['marker'] = TODAY
semi['as_of'] = TODAY

d['stages']['current'] = (
    "고점 통과(진행형) — SK하이닉스 2Q26 실적(2026-07-29 발표)이 매출·영업이익·순이익 모두 분기 사상 최고치를 기록하고 "
    "2026년 CAPEX를 40조원대 후반으로 오히려 확대(전년대비 +50~62%)하는 등 실물 펀더멘털은 여전히 확장 국면이나, "
    "실적이 이미 높아진 컨센서스(매출 84.1조원·영업이익 64.1조원)에 미달하고 AI 밸류에이션 재평가 심리가 겹치며 "
    "코스피가 7/28~29 이틀간 -16.16%(6,755.75→5,663.24) 급락, 6,000선이 붕괴되고 매도사이드카가 발동됐다 — "
    "그간 이어진 '고점 통과' 논쟁이 실제 대형 조정으로 전이된 국면"
)
d['stages']['note'] += (
    " [2026-07-30 갱신] 2026-07-28(화) 코스피는 전일(7/27, 6,755.75) 대비 -10.84%(-732.09P) 급락한 6,023.66에 마감했다(Yahoo Finance/UsStockInfo MCP 확인). "
    "삼성전자(-13.4%, 254,000→220,000원)·SK하이닉스(-14.65%, 1,816,000→1,550,000원)가 동반 급락했다. 이날 급락의 개별 촉매는 명확히 특정되지 않는다(추정 금지 원칙) — "
    "다음날(7/29) 예정된 SK하이닉스 2분기 실적발표를 앞둔 경계매물, 미국 빅테크·반도체주 동반 조정 가능성 등이 배경으로 거론되나 확정된 인과관계 보도는 확인되지 않았다. "
    "2026-07-29(수) SK하이닉스는 2분기(2Q26) 실적을 발표했다: 연결기준 매출 79조3187억원(YoY +256.8%)·영업이익 60조5426억원(YoY +557.2%, 상반기 누적 98조1529억원)·순이익 93조9226억원(YoY +1242.5%) - 매출·영업이익·순이익 모두 분기 사상 최고치, 영업이익률 76%(1분기 72%에서 확대). "
    "다만 사전 컨센서스(14개 국내 증권사 평균 매출 84.1조원·영업이익 64.1조원) 대비로는 매출 -5.7%·영업이익 -5.6% 미달했다(한국일보 등 '예상치 밑돌아' 보도); 반면 한국투자증권의 7/13 보수적 추정치(영업이익 60.4조원)와는 거의 일치했다. "
    "매우 중요한 신규 확인: SK하이닉스는 이날 컨퍼런스콜에서 2026년 연간 CAPEX를 최초로 공식 공개했다 — '40조원대 후반' 수준(전년 2025년 30조1730억원 대비 최소 15조원 이상 증가, YoY 약 +50~62%)이며, M15X 팹 양산 조기화·2027년초 오픈 예정 용인팹 1기 클린룸 대응 투자를 포함한다고 밝혔다. 또한 NVIDIA 등 약 10개 고객사와 5년 장기공급계약(LTA)을 체결했다고 공개했으며, HBM4는 이미 양산을 개시(수율 HBM3E 근접 수준)했고 HBM4E 샘플은 주요 고객사 출하를 완료했다고 밝혔다. 3Q26 가이던스로 DRAM ASP QoQ 약 +30%·NAND ASP QoQ 약 +50%대 중반을 제시했다(Wall St Engine/BigGo Finance 인용). "
    "그러나 주가는 실적발표 당일에도 추가 급락했다: 코스피는 장중 6,000선이 붕괴(장중 5,746.28)되며 매도사이드카가 발동됐고(코스닥도 매도사이드카 발동, 5분간 프로그램 매도호가 효력정지), 종가는 -5.98%(6,023.66→5,663.24)를 기록했다. SK하이닉스는 -9.61%(1,550,000→1,401,000원), 삼성전자는 -5.23%(220,000→208,500원)로 마감했다(Yahoo Finance/UsStockInfo MCP 확인). 코스피는 7/27 종가(6,755.75) 대비 이틀간 누적 -16.16% 급락했다. "
    "미국 Micron도 동반 급락했다: 7/28 -8.85%($900.20→$820.53)에 이어 7/29 -9.94%($820.53→$739.00), 시간외 추가 -3.84%($710.65)를 기록해 정규장 기준 이틀간 -17.9%(시간외 반영 시 약 -21.1%) 하락했다(Yahoo Finance/UsStockInfo MCP). "
    "실적·CAPEX 등 실물 펀더멘털은 사상 최고 수준으로 오히려 강화됐음에도 주가가 급락한 것은 (1)이미 높아진 컨센서스 눈높이 대비 미달, (2)장기간 이어진 AI/메모리 밸류에이션에 대한 재평가 심리가 겹친 결과로 해석된다. TrendForce DRAM 현물가(DDR5 $50.933·DDR4 $42.041, 07-29 18:10 GMT+8 세션)는 이번에도 소폭 변동에 그쳐 실물 계약가 지표 자체의 반전 신호는 없다 — 즉 '고점 통과'는 밸류에이션·주가 측면에서 사실상 진행되고 있으나, 계약가·공급부족 등 실물 사이클 지표는 아직 명확한 하강 전환 신호를 보이지 않고 있어 완전한 '하강' 단계로의 진입 여부는 다음 관찰 포인트(삼성전자 2026-07-30 확정실적/사업부별 세부, 미국 빅테크 실적, 7월 FOMC)에서 추가 확인이 필요하다. "
    "삼성전자의 2분기 확정실적(사업부별, DS/모바일/디스플레이 세부)은 2026-07-30(오늘) 발표될 예정이었으나 본 점검 시점 기준 확정 수치는 확인되지 않아 빈값으로 남겨둔다."
)

# tiles: keep values, append reconfirmation notes
for tile in d['tiles']:
    tile['sub'] += "; 7/30 재확인 변동없음(TrendForce 신규 계약가 발표 없음, DDR5/DDR4 현물가는 07-29 18:10 GMT+8 세션에서 소폭 변동 - 상세는 nmr_hbm.json 참조)"

# signals update
for sig in d['signals']:
    if sig['name'] == 'DRAM 재고주수/리드타임':
        sig['note'] += (
            " [2026-07-30 재확인] SK하이닉스 2Q26 컨퍼런스콜(7/29)에서 하반기 HBM4 양산 본격화 및 1c DRAM 출하 증가로 '하반기 성장이 상반기보다 높을 것'이라 언급했고, "
            "NVIDIA 등 약 10개 고객사와 5년 장기공급계약(LTA) 체결을 공개했다 - 공급부족 지속을 시사하는 신규 정성적 근거로 추가한다. 정량 재고주수 자체는 여전히 미발표(Inventec 7/16 경고, 40주 이상 리드타임이 최신 근거). 상태 '안전'(공급부족 지속) 유지."
        )
    elif sig['name'] == 'DRAM 계약가 상승률 QoQ':
        sig['note'] += (
            " [2026-07-30 재확인] TrendForce DRAM Spot Price 페이지(web_fetch 직접조회) 결과 Last Update 2026-07-29 18:10(GMT+8) 갱신 확인, DDR5 16Gb $50.933(전 세션 대비 자체계산 +0.20%, TrendForce 표시 Session Change 0.00%)·DDR4 8Gb $42.041(▼-0.09%)로 소폭 등락. 3분기 계약가 전망(서버 +13~18%·PC +15~20%)은 신규 발표 없이 유지. "
            "한편 SK하이닉스는 2Q26 컨퍼런스콜(7/29)에서 3Q26 자체 가이던스로 'DRAM ASP QoQ 약 +30%, NAND ASP QoQ 약 +50%대 중반, DRAM 비트성장 약 +10%QoQ'를 제시(Wall St Engine/BigGo Finance 인용) - TrendForce 서버 D램 블렌디드 전망(13~18%)보다 낙관적인 개별기업 가이던스로, 계약가 상승 기조 자체를 재확인시키는 신규 근거다. 상태 '주의' 유지."
        )
    elif sig['name'] == 'SK하이닉스 CAPEX 증가율 YoY':
        sig['value'] = "2026년 연간 40조원대 후반(회사 공식 가이던스, 2026-07-29 2Q26 컨퍼런스콜 공개) - 전년(2025년) 30조1730억원 대비 최소 15조원 이상 증가(YoY 약 +50~62%)"
        sig['note'] += (
            " [2026-07-30 매우 중요한 갱신] SK하이닉스가 2026-07-29 2분기 컨퍼런스콜에서 2026년 연간 CAPEX를 최초로 공식 공개했다(머니투데이·아시아경제·뉴스핌·ZDNet코리아·파이낸셜뉴스·한국경제 교차확인) — '40조원대 후반' 수준으로 예상하며, 전년(2025년) 실제 투자규모 30조1730억원 대비 최소 15조원 이상 증가하는 것으로 이는 YoY 약 +50~62%(40조원대 후반을 47~49조원 구간으로 볼 때)에 해당한다. M15X 팹 양산 일정 조기화, 2027년초 오픈 예정인 용인팹 1기 클린룸 이후 생산능력 신속 확대를 위한 투자를 포함한다고 설명했으며, 약 10개 고객사(NVIDIA 포함)와 5년 장기공급계약(LTA)을 체결했다고도 밝혔다. "
            "이는 본 신호의 threshold 조건 중 후자('과도한 증액이 지속되면 2027년 이후 공급과잉 위험 신호')에 해당할 수 있는 대규모 증액이나, 회사측은 이를 AI 메모리 수요 확대에 대응한 공급부족 해소 차원의 투자로 설명하고 있고(수요 위축이 아닌 공급확대 목적), 곽노정 CEO가 앞서(7/10) '2027년은 공급측면에서 업계 역사상 최악의 해가 될 것'이라 언급한 공급부족 전망과도 궤를 같이한다. 따라서 즉각적인 '경보'(수요위축) 전환 근거는 아니라고 판단하되, 향후 2027~2028년 신규 캐파 온라인 시점에 공급과잉으로 전환될 위험은 모니터링을 강화해야 할 요인으로 신규 반영한다. 상태는 '주의' 유지(단, 종전 '미공개'에서 '수치 확인'으로 근본적 진전)."
        )

# panels update
for panel in d['panels']:
    if panel['title'] == '반도체 업황':
        panel['rows'].append(["SK하이닉스 2Q26 실적(확정, 2026-07-29 발표)",
            "매출 79조3187억원(YoY+256.8%)·영업이익 60조5426억원(YoY+557.2%, 상반기누적 98조1529억원)·순이익 93조9226억원(YoY+1242.5%) - 모두 분기 사상 최고치, 영업이익률 76%(1Q 72%에서 확대); 다만 사전 컨센서스(매출 84.1조원·영업이익 64.1조원) 대비 매출 -5.7%·영업이익 -5.6% 미달"])
        panel['rows'].append(["SK하이닉스 2026년 CAPEX 공식 가이던스(신규, 7/29 컨콜)",
            "40조원대 후반(전년 30조1730억원 대비 최소 +15조원, YoY 약 +50~62%) - M15X·용인팹1기 조기화 투자; NVIDIA 등 약 10개 고객사와 5년 장기공급계약(LTA) 체결 공개"])
        panel['rows'].append(["SK하이닉스 3Q26 가이던스(신규, 7/29 컨콜)",
            "DRAM ASP QoQ 약 +30%, NAND ASP QoQ 약 +50%대 중반, DRAM 비트성장 약 +10%QoQ(Wall St Engine/BigGo Finance 인용)"])
        panel['rows'].append(["HBM4 양산 개시 공식화(신규)",
            "SK하이닉스 HBM4 양산 개시, 수율은 기존 HBM3E 성숙 수준에 근접; HBM4E 샘플은 주요 고객사 출하 완료(2026-07-29 컨콜)"])
        panel['rows'].append(["삼성전자 2Q26 확정실적(사업부별)",
            "2026-07-30 발표 예정 - 본 점검 시점 기준 확정 수치 미확인(빈값)"])
    elif panel['title'] == '업종 사이클':
        panel['rows'].append(["2026-07-28(화) 코스피 급락(신규, 확정종가)",
            "코스피 6,023.66(-10.84%, -732.09P, 전일 6,755.75 대비); 삼성전자 220,000원(-13.4%)·SK하이닉스 1,550,000원(-14.65%) 동반 급락(Yahoo Finance/UsStockInfo MCP) - 개별 촉매 불명확(SK하이닉스 실적발표 전야 경계매물 가능성 거론되나 확정 인과관계 보도 없음, 추정 금지)"])
        panel['rows'].append(["2026-07-29(수) SK하이닉스 실적발표 및 코스피 추가급락(신규, 확정종가)",
            "코스피 5,663.24(-5.98%, 장중 5,746.28서 매도사이드카 발동·6,000선 붕괴); 코스닥도 매도사이드카 발동(5분간 프로그램 매도호가 효력정지); SK하이닉스 1,401,000원(-9.61%)·삼성전자 208,500원(-5.23%) - 실적은 사상 최고치이나 컨센서스 하회·밸류에이션 재평가로 급락. 7/27 대비 이틀간 코스피 누적 -16.16%"])
        panel['rows'].append(["Micron(참고, 나스닥) 동반 급락(신규)",
            "7/28 $820.53(-8.85%, 전일 $900.20)→7/29 $739.00(-9.94%)→시간외 $710.65(-3.84% 추가) - 정규장 기준 이틀간 -17.9%(시간외 반영시 약 -21.1%), Yahoo Finance/UsStockInfo MCP"])
        panel['rows'].append(["실물지표 vs 주가 괴리(재확인, 신규)",
            "SK하이닉스 CAPEX 확대(+50~62%YoY 공식화)·LTA 10개사 체결·HBM4 양산개시 등 공급측 강세 시그널이 오히려 늘었음에도 주가는 이틀간 -22.85%(SK하이닉스)·-17.9%(삼성전자) 급락 - 실적 미스(컨센서스 대비)와 밸류에이션 재평가가 실물 지표 강세를 압도한 사례"])
    elif panel['title'] == '코스피 대형주 압박':
        panel['rows'].append(["2026-07-28·29 이틀간 삼성전자·SK하이닉스 낙폭(신규, 확정종가)",
            "삼성전자 -17.9%(254,000→208,500원), SK하이닉스 -22.85%(1,816,000→1,401,000원) - 6월 고점 대비 낙폭이 기존(30%대) 대비 추가 확대(정확한 갱신 낙폭%는 6월 고점 정확치 미확인으로 산출하지 않음, 추정 금지)"])
        panel['rows'].append(["코스피 이틀간 낙폭 및 시장안정화조치(신규)",
            "코스피 7/27(6,755.75)→7/29(5,663.24) 이틀간 -16.16%; 7/29 매도사이드카(코스피·코스닥 동시), 5분간 프로그램 매도호가 효력정지 - 2026년 누적 시장안정화조치 발동 빈도 추가 갱신 필요(정확한 누적 횟수는 본 점검에서 미확인, 다음 점검에서 갱신)"])
    elif panel['title'] == '확인 방법':
        for row in panel['rows']:
            if row[0] in ("DRAM/NAND 계약가·재고", "기업 실적·CAPEX"):
                row[1] = "삼성전자·SK하이닉스 분기 컨퍼런스콜 (SK하이닉스 2Q26 실적발표 2026-07-29 완료 확인; 삼성전자 2Q26 확정실적 2026-07-30 발표 예정; 차차기 SK하이닉스 3Q26 실적발표는 통상 10월경, 일자 미확정)"

# series: unchanged values, append note
d['series']['price_qoq']['cap'] += (
    " [2026-07-30 재확인] 3Q26 서버 D램 중간값(15.5%) 변동 없음(TrendForce 신규 계약가 발표 없음, DDR5/DDR4 현물가는 07-29 18:10 GMT+8 세션 기준 소폭 변동 - 상세는 nmr_hbm.json 참조). "
    "SK하이닉스 2Q26 컨퍼런스콜(7/29)의 3Q26 자체 가이던스(DRAM ASP QoQ 약 +30%)는 개별기업 가이던스로 TrendForce 서버 D램 블렌디드 전망과는 별개 지표이므로 본 시리즈(TrendForce 기준) 자체는 변경하지 않는다."
)

# chart field required by schema
d['chart'] = "charts/semi_cycle_signals.png"

with open(OUT_SEMI, 'w', encoding='utf-8') as f:
    json.dump(semi, f, ensure_ascii=False, indent=1)

print("SEMI OK")
