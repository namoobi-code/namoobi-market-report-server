/* TradingAgents 탭 — 6버튼(Architecture/1~5 Step) + 일일 자동 스크리닝 결과 렌더 (2026-07-12) */
(function(){
const root=document.getElementById('ta_root'); if(!root) return;
const st=document.createElement('style'); st.textContent=`
.ta-btns{display:flex;gap:8px;flex-wrap:wrap;margin:12px 0 16px}
.ta-btn{border:1px solid var(--line);background:var(--card,#fff);border-radius:20px;padding:7px 14px;font-size:12.5px;cursor:pointer;font-weight:600;color:var(--tx2)}
.ta-btn small{display:block;font-weight:400;font-size:10px;color:var(--tx2)}
.ta-btn.on{background:#1a2b4a;color:#fff;border-color:#1a2b4a}
.ta-btn.on small{color:#cdd6e4}
.ta-pane{display:none}.ta-pane.on{display:block}
.ta-h{font-size:14px;font-weight:700;margin:18px 0 8px;color:var(--tx)}
.ta-tbl{width:100%;border-collapse:collapse;font-size:11.5px;background:#fff}
.ta-tbl th{background:#f2f4f8;border:1px solid var(--line);padding:5px 7px;text-align:left;white-space:nowrap}
.ta-tbl td{border:1px solid var(--line);padding:4px 7px;vertical-align:top}
.ta-scroll{max-height:420px;overflow-y:auto;border:1px solid var(--line);border-radius:6px}
.ta-note{font-size:11px;color:var(--tx2);margin:6px 0 14px;line-height:1.6}
.ta-flag{display:inline-block;background:#fff3e6;border:1px solid #e8c9a0;color:#9a5b00;border-radius:4px;padding:1px 6px;font-size:10.5px;margin:1px 2px}
.ta-pos{color:#0a7a3d;font-weight:600}.ta-neg{color:#c0392b;font-weight:600}
.ta-chip{display:inline-block;border-radius:14px;padding:3px 11px;font-size:11.5px;font-weight:700;margin-right:6px}
.ta-chip.g{background:#e6f6ec;color:#0a7a3d;border:1px solid #bfe5cc}.ta-chip.y{background:#fff7e0;color:#9a6b00;border:1px solid #ecd9a0}.ta-chip.r{background:#fdeaea;color:#c0392b;border:1px solid #f0c2c2}
.ta-card{border:1px solid var(--line);border-radius:8px;background:#fff;margin-bottom:8px}
.ta-card summary{cursor:pointer;padding:9px 12px;font-size:12.5px;font-weight:650;list-style:none;display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.ta-card summary::-webkit-details-marker{display:none}
.ta-card[open] summary{border-bottom:1px solid var(--line)}
.ta-card .bd{padding:10px 14px;font-size:12px;line-height:1.65}
.ta-quote{border-left:3px solid #ccc;padding:6px 10px;margin:6px 0;background:#fafbfd;border-radius:0 6px 6px 0}
.ta-quote.bull{border-color:#0a7a3d}.ta-quote.bear{border-color:#c0392b}
.ta-appr{border:1px solid #bfe5cc;background:#f4fbf6;border-radius:8px;padding:12px 14px;margin:8px 0}
.ta-pre{background:#0f1a2e;color:#d7e0ef;border-radius:8px;padding:14px;font-size:11.5px;line-height:1.7;overflow-x:auto;white-space:pre}
`;document.head.appendChild(st);
const esc=t=>String(t??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const fx=(v,p=1)=>(v===null||v===undefined||isNaN(v))?'-':Number(v).toFixed(p);
const pc=(v,p=0)=>(v===null||v===undefined||isNaN(v))?'-':`<span class="${v>=0?'ta-pos':'ta-neg'}">${(v*100).toFixed(p)}%</span>`;
const tbl=(head,rows)=>`<table class="ta-tbl"><tr>${head.map(h=>`<th>${h}</th>`).join('')}</tr>${rows.map(r=>`<tr>${r.map(c=>`<td>${c}</td>`).join('')}</tr>`).join('')}</table>`;
const box=h=>`<div class="box" style="padding:10px">${h}</div>`;

const ARCH=`
<div class="ta-h">전체 구조 — 스크리너(서버 자동·무-LLM) + 스킬(LLM 판단)의 분업</div>
<div class="ta-pre">┌──────── 서버 자동 (매일 06·15시 KST cron · LLM 없음 · 전부 무료 소스) ────────┐
│ 데이터    전종목 실측 재무를 미리 수집 → screener_pool.json                        │
│           KR: 네이버 벌크시세 + integration(PER·PBR·배당·외국인)                    │
│               + finance/annual(ROE·부채비율·당좌·매출·영업이익) + 차트(200일선)     │
│           US: NASDAQ Trader + Yahoo v7 배치 + quoteSummary(ROE·D/E·유동·매출·FCF)   │
│      ↓                                                                              │
│ 1단계     하드컷 — 거래가능성(시총·거래대금·저가주·상장·증권구분·건전성)            │
│ 유니버스   + 실측(3년 영업적자·부채비율 ≤300%·유동비율 ≥0.8) → 통과 종목            │
│      ↓                                                                              │
│ 2단계     실측 z랭킹 — V(−PER·−PBR·+배당)·G(실측 매출·영익 YoY)                     │
│ 정량필터   ·M(12−1M·52주고점·200일선)·Q(실측 ROE·저부채·FCF) 4축 가중 z-score        │
│      ↓     (전종목 실측 — 프록시 폐기)                                              │
│ 3단계     팩터카드 — 상위 종목 실측 재무 상세 + 4축 z + 사전플래그(기술·뉴스·심리)   │
└────────────────────────────────────────────────────────────────────────────────────┘
        ↓  스크리너 페이지에서 [분석요청](비번) 또는 자동 상위 N
┌──────── 스킬 /namoobi-trading-agents 실행 시 (LLM 판단) ─────────────────────────────┐
│ 3-C 토론  번들 주입 → 4분석가 의견 → Bull 논거 → Bear 반박 → 판정(채택/관망/탈락)     │
│ 4단계     리스크심사 — 섹터 집중도·상관·변동성(ATR) → 최종 채택/반려                 │
└────────────────────────────────────────────────────────────────────────────────────┘
  5단계     성과추적 — 판정 스냅샷 → 1주/1개월 후 실현 수익률 vs 벤치마크(탈락군 대조)</div>
<div class="ta-h">설계 원칙</div>
${box(tbl(['원칙','내용'],[
['단계별 비용 배분','1·2단계는 전종목에 경량 실측 z랭킹, 무거운 토론(LLM)은 상위 후보에만 — 싸게 넓게 거르고 비싸게 좁게 판단'],
['프록시 → 실측 (2026-07)','네이버 finance/annual·Yahoo quoteSummary 가 전종목 실측 재무를 싸게 주므로, 종전 프록시(EPS비율·PBR÷PER)를 폐기하고 처음부터 실측 G(매출·영익 YoY)·Q(실측 ROE·FCF)로 z랭킹'],
['배제는 하드컷, 선호는 랭킹','유동성·건전성은 탈락 조건, 밸류·성장·모멘텀·수익성은 시장 내 z-score 상대평가'],
['사전 수집 → 주입','LLM이 도구로 데이터를 찾게 하지 않고 스크립트가 먼저 수집해 프롬프트에 주입 — 툴 압박 환각 차단'],
['결측은 결측으로','수집 실패 시 명시적 결측(가짜 0·추정 금지), 실측 재무 없는 종목은 해당 z축 결측 처리'],
['성과 검증','판정을 DB에 남겨 사후 수익률로 파이프라인 자체를 평가 (5단계·탈락군 대조)']]))}
<div class="ta-h">산출물 API</div>
${box(tbl(['파일','내용','조회'],[
['screener_pool.json','전종목 실측 재무 + 4축 z (스크리너 1·2·3단계 엔진)','<a href="/api/db/screener_pool" target="_blank">/api/db/screener_pool</a>'],
['ta_stage1~3.json','자동 파이프라인(ta_screen)의 유니버스·랭킹·번들','<a href="/api/db/ta_stage1" target="_blank">stage1</a> · <a href="/api/db/ta_stage2" target="_blank">2</a> · <a href="/api/db/ta_stage3" target="_blank">3</a>'],
['ta_verdict.json','스킬 실행 시 토론·심사 최종 판정','<a href="/api/db/ta_verdict" target="_blank">/api/db/ta_verdict</a>'],
['ta_perf.json','판정군별 성과추적(탈락군 대조)','<a href="/api/db/ta_perf" target="_blank">/api/db/ta_perf</a>']]))}
<div class="ta-note">스크리너 페이지(좌측 SCREENER 버튼)에서 1·2·3단계를 <b>직접 조작·필터</b>할 수 있고, 자동 파이프라인(ta_screen)은 같은 원리로 매일 상위 후보를 미리 뽑아 둔다.</div>
<div class="src">⚠️ 투자 자문이 아니며 결과는 참고용. 매매 판단·책임은 사용자에게 있다.</div>`;

const S1A=`
<div class="ta-h">A. 사용 가능한 전체 지표 후보 (중요도 ★★★=스크리닝 성패 좌우 · ✅=전종목 일괄 · △=후보군만 · ❌=불가)</div>
<div class="ta-note">기본 = TradingAgents 28필드 계열 / 기술 = 12지표 카탈로그 계열 / 심리·수급 / 뉴스·이벤트</div>
${box('<b style="font-size:12px">기본적 분석</b>'+tbl(['지표','중요도','한국','미국','비고'],[
['시가총액·거래대금','★★★','✅ KRX 1콜','✅ Yahoo 배치','배제용(유동성) — 모든 필터의 대전제'],
['fwd EPS 성장','★★★','✅ 네이버 cnsEps/eps','✅ epsForward/epsTTM','컨센서스 기반 선행 성장'],
['PER(TTM·Fwd)','★★★','✅ 네이버','✅ Yahoo','적자기업=결측 처리(최하점 금지)'],
['PBR','★★☆','✅ 네이버','✅ priceToBook','금융·지주는 섹터 내 상대평가'],
['ROE·이익률','★★★','✅ 네이버 연간재무','✅ quoteSummary','밸류 함정 방어 — 1·2단계에서 전종목 실측(프록시 폐기)'],
['D/E·유동비율','★★☆','✅ 연간재무','✅ quoteSummary','배제용 — 1단계 실측 하드컷'],
['FCF','★★☆','—','✅ quoteSummary','이익의 질 — Q축(미국)'],
['배당수익률','★★','✅','✅','랭킹 가점'],
['Beta·EBITDA 등','★','△','✅/△','스크리닝 판별력 낮음 — 미사용']]))}
${box('<b style="font-size:12px">기술적 분석</b>'+tbl(['지표','중요도','한국','미국','비고'],[
['12−1 모멘텀','★★★','✅ KRX 과거시점','✅ 52주수익률 근사','팩터 문헌에서 가장 강건'],
['52주 고점 대비','★★★','✅ 네이버','✅ Yahoo','모멘텀 확인'],
['200일선 대비','★★☆','✅ 네이버 차트','✅ Yahoo','장기추세 — M축(한·미 대칭)'],
['거래량 활성화(10d/3m)','★★','✅','✅','수급 관심 프록시'],
['RSI','★★','✅ 계산','✅ 계산','1차에선 극단 과열 배제·3단계 번들에 포함'],
['ATR(변동성)','★★','✅ 계산','✅ 계산','4단계 포지션 사이징 재사용'],
['MACD·볼린저·VWMA','★','✅','✅','시점(타이밍) 지표 — 랭킹 부적합, 3단계 번들만']]))}
${box('<b style="font-size:12px">심리·수급</b>'+tbl(['지표','중요도','한국','미국','비고'],[
['외국인 소진율·변화','★★★(KR)','✅ 네이버 foreignRate','—','한국 축 최강 수급'],
['StockTwits Bull/Bear','★★','❌ 미커버','△ 후보군만','3단계 번들에 포함 (무키)'],
['공매도 잔고','★★','△ KRX','△ quoteSummary','향후'],
['네이버 데이터랩·Reddit','★★','△','△','종목 필터 부적합 — 시장 국면용'],
['VIX·CNN F&G·AAII','★★','시장 단위','시장 단위','필터가 아닌 가중치 틸트 후보']]))}
${box('<b style="font-size:12px">뉴스·이벤트</b>'+tbl(['지표','중요도','비고'],[
['종목 뉴스 헤드라인','★★','전종목 필터 불가 — 3단계 번들(상위 10×2)에만 포함'],
['FRED 매크로·Polymarket 예측시장','★★','종목이 아닌 시장/이벤트 단위 — 국면 판단용'],
['실적 발표 일정','★★','향후: 번들에 D-day 추가 검토']]))}`;

const S1B=`
<div class="ta-h">B. 1단계 하드컷 — 거래가능성 + 실측 건전성 (전부 스크리너에서 조절 가능)</div>
${box('<b style="font-size:12px">거래가능성 (경량)</b>'+tbl(['필터','한국 (KRX)','미국 (Yahoo 배치)','이유'],[
['시가총액','≥ 3,000억원','≥ $2B','초소형주 제외 — 유동성·정보 신뢰도'],
['거래대금','3거래일 평균 ≥ 30억원','3개월 평균거래량×주가 ≥ $20M','실제 매매 가능성'],
['저가주','종가 ≥ 1,000원','≥ $5','저가주 변동성·작전 리스크'],
['상장기간','상장 ≥ 1년','IPO ≥ 1년','이력 부족 종목의 지표 왜곡'],
['증권 구분','보통주만(우선주/스팩 제외)','ETF·워런트·유닛·우선주 제외','중복·비종목 제거'],
['건전성 신호','—','200일선 −30%↓ 제외','추락 나이프 회피']]))}
${box('<b style="font-size:12px">실측 건전성 (2026-07 · 종전 2단계 Layer2 → 1단계로 이동)</b>'+tbl(['필터','기준','금융업','이유'],[
['3년 영업적자','3년 연속 영업적자 제외','—','구조적 부실 — 네이버 연간재무 영업이익 3년'],
['부채비율(D/E)','≤ 300%','면제','레버리지 리스크 — 금융업은 구조적 고부채'],
['유동비율(당좌)','≥ 0.8','면제','단기 지급능력']]))}
<div class="ta-note">종전엔 실측 건전성 컷을 상위 150에만(2단계 Layer2) 적용했으나, 전종목 실측 재무 확보 후 <b>1단계 하드컷으로 이동</b>했다 — 하드컷의 제자리는 1단계다.</div>`;

const S3A=`
<div class="ta-h">A. 3단계 — 실측 팩터카드 + 분석요청</div>
${box(tbl(['블록','내용','이유'],[
['팩터카드','1·2단계 통과 상위 종목의 4축 z + 실측 원값(PER·PBR·배당·ROE·부채·유동·매출YoY·영익YoY/FCF)','토론의 정량 뼈대 — 에이전트가 수치 인용 의무'],
['기술·사전플래그','RSI≥75 과열 / RSI≤35 조정 / 1M −10%↓ / 52주고점比 −30%↓ / 거래량급증 / 소셜 쏠림','규칙으로 미리 계산해 LLM 판단 보조 — 서버 무-LLM 파트'],
['뉴스·심리','최근 헤드라인(KR 네이버·US Yahoo) · US StockTwits 강세/약세 · KR 외국인 소진율','촉매·리스크·개미 쏠림 — 해석은 LLM'],
['분석요청','스크리너 3단계에서 상위 N을 [분석요청] 버튼(비번)으로 확정 → 토론 입력으로 전달','오조작 방지 소프트 게이트']]))}
<div class="ta-h">C. 에이전트 토론 — /namoobi-trading-agents 스킬 실행 시</div>
${box(tbl(['순서','내용'],[
['입력','확정된 상위 종목 번들 — 스킬이 서버에서 내려받아 프롬프트에 주입(툴콜 없음 → 환각 차단)'],
['토론','종목별: 4분석가(기본·기술·심리·뉴스) 의견 → Bull 최선 논거 → Bear 반박 → 판정(채택/관망/탈락 + 확신도 1~10)'],
['규칙','번들 수치만 인용(지어내기 금지) · 결측은 "자료 없음" · 전부 채택 금지(차별화 강제)'],
['출력','판정 JSON → 4단계 리스크 심사의 입력']]))}
<div class="ta-note">서버는 LLM을 쓰지 않는다 — 팩터카드는 "토론 대기 후보"이며, 판정은 스킬 실행 시에만 생성된다.</div>`;

const S4=`
<div class="ta-h">4단계 — 리스크 심사 (/namoobi-trading-agents 스킬 실행 시)</div>
${box(tbl(['심사 항목','내용','서버 사전 계산'],[
['섹터 집중도','채택 종목의 섹터 분포 — 특정 섹터(예: 반도체) 쏠림 시 편입 수 제한','번들에 섹터 포함'],
['상관·중복','같은 밸류체인 종목 동시 채택 여부(예: SK하이닉스+SK스퀘어는 사실상 동일 베팅)','—'],
['변동성·사이징','ATR% 기반 포지션 상한 — 변동성 큰 종목일수록 작게','번들에 ATR% 포함'],
['최종 판정','토론 채택 종목별 승인/반려 + 편입 비중 제안','—']]))}
<div class="ta-note">입력 = 3단계 토론 판정(C) 결과. 포트폴리오 매니저 역할 — TradingAgents의 Risk Management & Portfolio Manager 구조를 단일 심사 패스로 번안.</div>`;

const S5=`
<div class="ta-h">5단계 — 성과 추적 <span style="font-size:11px;font-weight:400;color:var(--ok)">· 가동 중 (ta_perf.py · 무-LLM)</span></div>
${box(tbl(['항목','구현'],[
['기록','판정 시점의 종목·가격·판정·확신도를 <code>ta_calls.json</code>에 스냅샷 — <b>탈락 종목도 기록</b>'],
['검증','1주/1개월/3개월 경과 수익률을 벤치마크(KOSPI·SPY) 대비 α로 계산'],
['대조군','<b>탈락군을 함께 추적</b> — 채택군만 보면 생존편향에 빠져 필터가 실제로 작동하는지 검증할 수 없다'],
['환류','채택 α − 탈락 α 가 유의하게 양(+)이어야 스크리닝이 작동한다는 증거가 된다']]))}
<div class="ta-h" style="margin-top:18px">A. 판정군별 성적표</div>
<div id="ta_perf_sum">불러오는 중…</div>
<div class="ta-h" style="margin-top:18px">B. 종목별 추적</div>
<div id="ta_perf_rows">불러오는 중…</div>
<div class="ta-note" id="ta_perf_note"></div>`;

const S2A=`
<div class="ta-h">2단계 — 4축 z-score 실측 랭킹 <span style="font-size:11px;font-weight:400;color:var(--ok)">· 프록시 폐기, 전종목 실측 (2026-07)</span></div>
${box(tbl(['축','구성 (KR / US)','이유'],[
['V 밸류','−fPER(컨센서스 우선)·−PBR·+배당수익률','싸게 사기 — 적자기업은 결측 처리(최하점 금지)'],
['G 성장','실측 매출·영업이익 YoY + 매출 컨센서스 / 실측 매출성장·EPS성장','<b>실측</b> — 종전 프록시(컨센EPS÷실적EPS)의 저베이스 착시 제거'],
['M 모멘텀','12−1개월 수익률·52주고점 근접·<b>200일선比</b> / 52주수익률·고점비·200일선比','최근 1개월 제외(단기 반전 노이즈)·200일선(장기추세) — 한·미 대칭 3지표'],
['Q 수익성','실측 ROE + 저부채 가점 / 실측 ROE + FCF수익률 + 저부채','<b>실측</b> — 종전 PBR÷PER 프록시의 극단값 지배 차단']]))}
<div class="ta-note">동일가중이 기본, 스크리너에서 <b>축별 가중치 슬라이더</b>로 관점을 조절해 실시간 재랭킹한다(서버 재실행 없음, 최소 3축). z=시장 내 표준화 점수(0=평균, +1=상위).</div>
<div class="ta-h" style="margin-top:16px">실측 재무 소스 (전종목 · 종전 상위 150 한정 → 전종목 확대)</div>
${box(tbl(['시장','소스','커버리지·속도'],[
['한국','네이버 finance/annual(ROE·부채비율·당좌비율·매출·영업이익) + 차트(200일 이동평균)','전종목 ~99% · ~15초'],
['미국','Yahoo quoteSummary(ROE·D/E·유동비율·매출성장·FCF)','전종목 ~67%(레이트리밋 재시도) · ~4분']]))}
<div class="ta-note">종전엔 프록시로 전종목 랭킹 → 상위 150만 실측(Layer2)했으나, 네이버·야후가 실측 재무를 싸게 주므로 <b>처음부터 전종목 실측</b>으로 통합했다. 재무 없는 종목은 해당 z축만 결측(하단 정렬).</div>`;

// ---------- skeleton ----------
root.innerHTML=`
<div class="hero"><span class="badge">서버 자동화 · 하루 2회(06·15시 KST) + 스크리너 실시간</span>
<h3>TradingAgents — 종목 스크리닝</h3>
<p><a href="https://github.com/TauricResearch/TradingAgents" target="_blank" rel="noopener">TauricResearch/TradingAgents</a>의 멀티 에이전트 토론 구조를 번안.
1~3단계(전종목 실측 z랭킹)는 <b>서버가 하루 2회(06·15시) LLM 없이 자동 실행</b>하고 <b>좌측 SCREENER 페이지에서 직접 조작</b>할 수 있다. 토론(3-C)·리스크 심사(4)는 <b>/namoobi-trading-agents</b> 스킬 실행 시 LLM이 수행한다.</p></div>
<div class="ta-btns">
<button class="ta-btn on" data-ta="0">0. Architecture<small>전반 구조</small></button>
<button class="ta-btn" data-ta="1">1 Step<small>유니버스</small></button>
<button class="ta-btn" data-ta="2">2 Step<small>정량필터</small></button>
<button class="ta-btn" data-ta="3">3 Step<small>에이전트토론</small></button>
<button class="ta-btn" data-ta="4">4 Step<small>리스크심사</small></button>
<button class="ta-btn" data-ta="R">SKILL RESULT<small>토론·심사 판정</small></button>
<button class="ta-btn" data-ta="5">5 Step<small>성과추적</small></button>
</div>
<div class="ta-pane on" id="ta_p0">${ARCH}<div class="ta-h">최근 실행 로그</div><div id="ta_status">불러오는 중…</div></div>
<div class="ta-pane" id="ta_p1">${S1A}${S1B}<div class="ta-h">C. 오늘의 1차 스크리닝 리스트 (매일 06:00 자동)</div><div id="ta_s1">불러오는 중…</div></div>
<div class="ta-pane" id="ta_p2">${S2A}<div class="ta-h">B. 오늘의 2차 스크리닝 TOP 30 (1단계 후 순차 실행)</div><div id="ta_s2">불러오는 중…</div></div>
<div class="ta-pane" id="ta_p3">${S3A}<div class="ta-h">B. 오늘의 토론 대기 후보 10×2 + 번들 (2단계 후 순차 실행)</div><div id="ta_s3">불러오는 중…</div></div>
<div class="ta-pane" id="ta_p4">${S4}</div>
<div class="ta-pane" id="ta_pR"><div class="ta-h">스킬 실행 결과 — /namoobi-trading-agents 토론·리스크 심사 판정</div><div id="ta_sr">불러오는 중…</div></div>
<div class="ta-pane" id="ta_p5">${S5}</div>
<div class="src" style="margin-top:16px">⚠️ 투자 자문이 아니며, 스크리닝 결과는 참고용이다. 매매 판단과 책임은 사용자에게 있다.</div>`;
root.querySelectorAll('.ta-btn').forEach(b=>b.onclick=()=>{
  root.querySelectorAll('.ta-btn').forEach(x=>x.classList.toggle('on',x===b));
  root.querySelectorAll('.ta-pane').forEach(p=>p.classList.toggle('on',p.id==='ta_p'+b.dataset.ta));
});
// ---------- live data ----------
const J=async n=>{try{const r=await fetch('/api/db/'+n);return r.ok?await r.json():null}catch(e){return null}};
(async()=>{
  const s0=await J('ta_status');
  if(s0&&s0.runs&&s0.runs.length){
    const runs=s0.runs.slice(-5).reverse();
    document.getElementById('ta_status').innerHTML=box(tbl(['실행 시각','stage1','stage2','stage3'],
      runs.map(r=>[esc(r.start),...['stage1','stage2','stage3'].map(k=>{const s=(r.stages||{})[k];
        return s?(s.ok?`✅ ${s.sec}s`:`❌ ${esc(s.err||'').slice(0,60)}`):'—'})])));
  } else document.getElementById('ta_status').innerHTML='<div class="ta-note">아직 실행 기록 없음</div>';
  // ── 5단계 성과추적 (ta_perf.py 산출) ──
  // ⚠️ 이 블록은 stage1/2/3·SKILL RESULT 보다 먼저 실행된다 — 여기서 예외가 나면
  //    아래 렌더가 전부 중단돼 모든 패널이 "불러오는 중…" 에 멈춘다(2026-07-14 장애).
  //    그래서 (a) summary 가 배열인지 실제로 확인하고 (b) try/catch 로 격리한다.
  const pf=await J('ta_perf');
  try{
  if(pf&&Array.isArray(pf.summary)&&pf.summary.length){
    const P=v=>v==null?'—':`<span class="${v>0?'up':(v<0?'dn':'note')}">${v>0?'+':''}${v}%</span>`;
    const R=v=>v==null?'<span class="note">경과 전</span>':`<b class="${v>0?'up':'dn'}">${v>0?'+':''}${v}%</b>`;
    const H=pf.horizons||['1주','1개월','3개월'];
    const NM=x=>(x.구분.startsWith('★')?`<b>${esc(x.구분)}</b>`:(x.구분.startsWith('탈락')?`<span class="note">${esc(x.구분)}</span>`:esc(x.구분)));
    const cell=(v,n)=>v==null?'<span class="note">경과 전</span>':`${R(v)} <span class="note">(n=${n})</span>`;
    document.getElementById('ta_perf_sum').innerHTML=
      `<b style="font-size:12px">① 콜 단위</b> <span class="note">— 판정 1건 = 표본 1개. 같은 종목이 반복 등장하면 그 종목이 표본을 지배한다.</span>`
      +box(tbl(['구분','콜수','고유종목',...H.flatMap(h=>[h+' 평균α',h+' 적중률'])],
        pf.summary.map(x=>[NM(x),String(x.콜수),String(x.고유종목수),
          ...H.flatMap(h=>[cell(x[h+'_평균알파'],x[h+'_n']),
            (x[h+'_적중률']==null?'—':`${x[h+'_적중률']}%`)])])))
      +`<b style="font-size:12px;display:block;margin-top:14px">② 종목 단위 <span style="color:var(--ok)">★ 중복 가중 제거</span></b>
        <span class="note">— 종목별로 먼저 평균 → 종목 간 평균. ①과 크게 벌어지면 소수 종목이 성적을 끌고 있다는 뜻이다.</span>`
      +box(tbl(['구분','고유종목',...H.flatMap(h=>[h+' 평균α',h+' 적중률'])],
        pf.summary.map(x=>[NM(x),String(x.고유종목수),
          ...H.flatMap(h=>[cell(x[h+'_종목평균알파'],x[h+'_종목n']),
            (x[h+'_종목적중률']==null?'—':`${x[h+'_종목적중률']}%`)])])))
      +`<div class="ta-note">α = 종목수익률 − 벤치마크(KOSPI·SPY). <b>탈락 = 대조군</b> — 채택 α 가 탈락 α 를 유의하게 앞서야 필터가 작동한다는 증거다.<br>
        ⚠️ 같은 종목의 연속 판정은 서로 독립이 아니다(어제 오른 종목은 오늘도 오를 확률이 높다). <b>n 을 독립 표본 수로 읽지 말 것</b> — 실질 독립 표본은 고유종목수에 가깝다.<br>
        경과일이 안 된 구간은 계산하지 않는다(억지로 채우지 않음).</div>`
      + ((pf.중복진단&&(pf.중복진단.반복등장||[]).length)
          ? `<div class="ta-h" style="margin-top:14px">반복 등장 종목 <span style="font-size:11px;font-weight:400;color:var(--tx2)">— 표본을 지배하고 있는지 확인</span></div>`
            + box(tbl(['종목','등장 횟수'], pf.중복진단.반복등장.map(d=>[esc(d.종목),`<b>${d.등장횟수}회</b>`])))
          : `<div class="ta-note">반복 등장 종목 없음 — 현재 ${pf.중복진단?pf.중복진단.고유종목수:'—'}종목 모두 1회씩 판정됐다.</div>`);
    const rows=(pf.rows||[]).slice().sort((a,b)=>
      String(b.price_date||b.trade_date||'').localeCompare(String(a.price_date||a.trade_date||''))
      || (b.현재수익률??-999)-(a.현재수익률??-999));
    document.getElementById('ta_perf_rows').innerHTML=`<div class="ta-scroll">`+
      tbl(['종목','반복','시장','판정','확신도','심사','<b>기준일</b>','기준가','현재가','현재 수익률',...H.map(h=>h+' α')],
        rows.map(r=>[
          esc(r.종목),
          (r.반복판정>1?`<b class="dn">${r.반복판정}회</b>`:'<span class="note">1</span>'),
          r.시장,
          (r.판정==='채택'?`<b class="up">채택</b>`:(r.판정==='탈락'?`<span class="note">탈락</span>`:'관망')),
          String(r.확신도??'—'),
          (r.심사==='승인'?`<b style="color:var(--ok)">승인</b>`:(r.심사==='반려'?`<span class="dn">반려</span>`:'<span class="note">—</span>')),
          (r.price_date?`<b>${esc(r.price_date)}</b>`:'<span class="note">—</span>'),
          (r.기준가==null?'—':Number(r.기준가).toLocaleString()),
          (r.현재가==null?'—':Number(r.현재가).toLocaleString()),
          R(r.현재수익률),
          ...H.map(h=>r[h+'_알파']==null?'<span class="note">·</span>':P(r[h+'_알파']))
        ]))+`</div>`;
    document.getElementById('ta_perf_rows').insertAdjacentHTML('beforebegin',
      `<div class="ta-note" style="margin-bottom:8px">
        <b>같은 종목이 여러 날 선정되면?</b> — <b>회차마다 별도 행</b>으로 남긴다. 7/13의 SK하이닉스(@1,845,000)와
        7/20의 SK하이닉스(@2,000,000)는 <b>다른 가격·다른 정보에서 나온 다른 콜</b>이므로, 각각의 판정이 옳았는지를
        따로 채점해야 한다. 하나로 합치면 '언제 낸 신호가 좋았는가'를 잃는다.<br>
        <b>기준가 = 그 회차 판정 시점에 실제로 본 종가</b>이고, <b>기준일</b>이 그 날짜다.
        집계할 때만 종목 단위로 묶어 평균을 낸다(위 ② 표).</div>`);
    document.getElementById('ta_perf_note').innerHTML=
      `갱신 ${esc(pf.as_of||'')} · 벤치마크 KR=^KS11 · US=SPY
       <br>※ <b>기준일</b> = 기준가가 실제로 형성된 날(종가일). 번들의 <code>trade_date</code>(KRX 기본정보 기준일)는
       1영업일 지연돼 실제 가격일과 다르므로 성과 계산에 쓰지 않는다.
       <br>${esc(pf.note||'')}`;
  } else {
    document.getElementById('ta_perf_sum').innerHTML='<div class="ta-note">아직 판정 이력이 없다 — /namoobi-trading-agents 를 1회 이상 실행해야 추적이 시작된다.</div>';
    document.getElementById('ta_perf_rows').innerHTML='';
  }
  }catch(e){
    console.error('[ta] 5단계 성과추적 렌더 실패 — 다른 단계는 계속 그린다:',e);
    document.getElementById('ta_perf_sum').innerHTML=
      '<div class="ta-note">성과추적 표를 그리지 못했다 (ta_perf.json 형식 오류: '+esc(String(e&&e.message||e))+'). 원본: <a href="/api/db/ta_perf" target="_blank">/api/db/ta_perf</a></div>';
    document.getElementById('ta_perf_rows').innerHTML='';
  }

  const s1=await J('ta_stage1');
  try{
  if(s1){
    const mk=(rows,kr)=>`<div class="ta-scroll">${tbl(kr?['종목','시장','종가','시총(조)','거래대금(억)']:['티커','종목명','주가','시총($B)'],
      rows.map(r=>kr?[esc(r.name),r.mkt,Number(r.close).toLocaleString(),(r.mcap/1e12).toFixed(2),(r.trdval/1e8).toFixed(0)]
                   :[r.sym,esc(r.name),fx(r.px,2),(r.mcap/1e9).toFixed(1)]))}</div>`;
    document.getElementById('ta_s1').innerHTML=
      `<div class="ta-note"><b>기준일 ${esc(s1.price_date||s1.trade_date||'—')}</b> (종가 기준) · 갱신 ${esc(s1.as_of)} <span class="note">· 시세(종가·시총·거래대금)는 네이버 당일값. 종목 기본정보(주권·보통주·상장일)만 KRX ${esc(s1.krx_base_date||'—')} 기준 — 정적 정보라 무해하다.</span> — 한국 ${s1.kr.universe}종목 → <b>${s1.kr.pass}</b> 통과 · 미국 ${s1.us.universe}종목 → <b>${s1.us.pass}</b> 통과</div>`
      +`<div class="ta-h" style="margin-top:8px">한국 통과 ${s1.kr.pass}종목 (시총순)</div>`+mk(s1.kr.rows,true)
      +`<div class="ta-h">미국 통과 ${s1.us.pass}종목 (시총순)</div>`+mk(s1.us.rows,false);
  } else document.getElementById('ta_s1').innerHTML='<div class="ta-note">데이터 없음 — 다음 06:00 실행 대기</div>';
  }catch(e){console.error('[ta] 1단계 렌더 실패:',e);document.getElementById('ta_s1').innerHTML='<div class="ta-note">1단계 렌더 실패: '+esc(String(e&&e.message||e))+'</div>';}
  const s2=await J('ta_stage2');
  try{
  if(s2){
    const zrow=r=>[fx(r.z_val),fx(r.z_grw),fx(r.z_mom),fx(r.z_qly),`<b>${fx(r.score,2)}</b>`];
    const krT=tbl(['#','종목','fPER','PBR','ROE%','부채%','매출성장','영업이익성장','V','G','M','Q','종합'],
      s2.kr.top.map((r,i)=>[i+1,esc(r.name),fx(r.fper),fx(r.pbr),fx(r.roe,0),fx(r.de,0),pc(r.revg),pc(r.opg),...zrow(r)]));
    const usT=tbl(['#','티커','종목명','섹터','fPE','ROE','D/E%','매출성장','FCF수익률','V','G','M','Q','종합'],
      s2.us.top.map((r,i)=>[i+1,r.sym,esc(r.name).slice(0,26),esc(r.sector||'-').slice(0,12),fx(r.fpe),pc(r.roe),fx(r.de,0),pc(r.revg),pc(r.fcfy,1),...zrow(r)]));
    const drops=(s2.kr.drops||[]).map(d=>esc(d[0])+'('+esc(d[1])+')').join(', ');
    const dropsU=(s2.us.drops||[]).slice(0,14).map(d=>esc(d[0])+'('+esc(d[1])+')').join(', ');
    document.getElementById('ta_s2').innerHTML=
      `<div class="ta-note"><b>기준일 ${esc(s2.price_date||s2.trade_date||'—')}</b> (종가 기준) · 갱신 ${esc(s2.as_of)} <span class="note">· 시세(종가·시총·거래대금)는 네이버 당일값. 종목 기본정보(주권·보통주·상장일)만 KRX ${esc(s2.krx_base_date||'—')} 기준 — 정적 정보라 무해하다.</span></div>`
      +`<div class="ta-h" style="margin-top:8px">한국 TOP 30</div><div class="ta-scroll">${krT}</div>`
      +`<div class="ta-h">미국 TOP 30</div><div class="ta-scroll">${usT}</div>`
      +`<div class="ta-note"><b>재무 하드컷 탈락</b> — KR: ${drops||'없음'}<br>US(일부): ${dropsU||'없음'}</div>`;
  } else document.getElementById('ta_s2').innerHTML='<div class="ta-note">데이터 없음</div>';
  }catch(e){console.error('[ta] 2단계 렌더 실패:',e);document.getElementById('ta_s2').innerHTML='<div class="ta-note">2단계 렌더 실패: '+esc(String(e&&e.message||e))+'</div>';}
  const s3=await J('ta_stage3');
  try{
  if(s3){
    const mk=(bs,kr)=>tbl(['종목','종합','fPER/fPE','ROE','RSI','1개월','1년','52주고점比','심리','플래그'],
      bs.map(b=>{const f=b['팩터카드']||{},t=b['기술지표']||{},sn=b['심리']||{};
        let sent=kr?('외인 '+fx(sn['외국인소진율%'],0)+'%'):(typeof sn.StockTwits==='object'?`강세${sn.StockTwits.bullish}/약세${sn.StockTwits.bearish}`:'결측');
        return [`<b>${esc(b['종목'])}</b>${kr?'':' ('+esc(b['티커'])+')'}`,fx(f.score,2),fx(kr?f.fper:f.fpe),
          kr?fx(f.roe,0)+'%':pc(f.roe),fx(t.rsi14,0),pc(t.ret_1m),pc(t.ret_1y),pc(t.hi52_dist),sent,
          (b['사전플래그']||[]).map(x=>`<span class="ta-flag">${esc(x)}</span>`).join('')||'—'];}));
    document.getElementById('ta_s3').innerHTML=
      `<div class="ta-note"><b>기준일 ${esc(s3.price_date||s3.trade_date||'—')}</b> (종가 기준) · 갱신 ${esc(s3.as_of)} <span class="note">· 시세(종가·시총·거래대금)는 네이버 당일값. 종목 기본정보(주권·보통주·상장일)만 KRX ${esc(s3.krx_base_date||'—')} 기준 — 정적 정보라 무해하다.</span> — 뉴스 헤드라인 6건·StockTwits 원문은 <a href="/api/db/ta_stage3" target="_blank">JSON</a> 참조</div>`
      +`<div class="ta-h" style="margin-top:8px">한국 후보 10</div><div class="ta-scroll">${mk(s3.kr,true)}</div>`
      +`<div class="ta-h">미국 후보 10</div><div class="ta-scroll">${mk(s3.us,false)}</div>`;
  } else document.getElementById('ta_s3').innerHTML='<div class="ta-note">데이터 없음</div>';
  }catch(e){console.error('[ta] 3단계 렌더 실패:',e);document.getElementById('ta_s3').innerHTML='<div class="ta-note">3단계 렌더 실패: '+esc(String(e&&e.message||e))+'</div>';}

  // ---- SKILL RESULT (ta_verdict) ----
  try{
  const sv=await J('ta_verdict'); const calls=await J('ta_calls');
  const el=document.getElementById('ta_sr');
  if(!sv||!sv.verdicts){ el.innerHTML='<div class="ta-note">아직 스킬 실행 기록이 없다 — <b>/namoobi-trading-agents</b> 를 실행하면 판정이 여기에 표시된다.</div>'; }
  else{
    const V=sv.verdicts, rr=sv.risk_review||{}, ap=sv.approved||[];
    const cnt=k=>V.filter(v=>v['판정']===k).length;
    const ord={'채택':0,'관망':1,'탈락':2};
    const vs=[...V].sort((a,b)=>(ord[a['판정']]??3)-(ord[b['판정']]??3)||(b['확신도']||0)-(a['확신도']||0));
    // 기준가의 실제 날짜 = px_snapshot 의 price_date (KRX trade_date 와 다르다)
    const _pds=[...new Set(Object.values(sv.px_snapshot||{}).map(x=>x&&x.price_date).filter(Boolean))].sort();
    const _pd=_pds.length?_pds[_pds.length-1]:null;
    let h=`<div class="ta-note"><b>기준일 ${esc(_pd||sv.trade_date||'—')}</b> (판정에 쓰인 종가일)`
      + (_pds.length>1?` <span class="note">· 한국 ${esc(_pds[_pds.length-1])} / 미국 ${esc(_pds[0])} (시차)</span>`:'')
      + ` · 판정 생성 ${esc(sv.as_of)} · 실행 이력 ${calls&&calls.calls?calls.calls.length:1}회`
      + `<br><span class="note">시세·기술지표는 네이버/Yahoo 당일 종가 기준. 종목 기본정보(주권·상장일)만 KRX T+1 이지만 정적 정보라 무해하다.</span></div>`;
    h+=`<div style="margin:6px 0 14px"><span class="ta-chip g">채택 ${cnt('채택')}</span><span class="ta-chip y">관망 ${cnt('관망')}</span><span class="ta-chip r">탈락 ${cnt('탈락')}</span></div>`;
    if(ap.length){
      h+=`<div class="ta-appr"><b style="font-size:13px">✅ 최종 승인 ${ap.length}종목 (리스크 심사 통과)</b><div style="margin-top:8px">`+
        tbl(['종목','시장','토론 확신도','비중 가이드','사유'],ap.map(r=>[`<b>${esc(r['종목'])}</b>`,esc(r['시장']||''),(r['확신도']??'-')+'/10',esc(r['비중가이드']||''),esc(r['사유']||'')]))+'</div></div>';
    } else h+='<div class="ta-appr"><b>최종 승인 없음</b> — 리스크 심사에서 전원 반려</div>';
    const rej=(rr['심사대상']||[]).filter(r=>!r['승인']);
    if(rej.length) h+=`<div class="ta-note"><b>리스크 심사 반려</b>: ${rej.map(r=>esc(r['종목'])+' — '+esc(r['사유']||'')).join(' · ')}</div>`;
    if(rr['총평']) h+=`<div class="lead">${esc(rr['총평'])}</div>`;
    h+='<div class="ta-h">종목별 토론 카드 (클릭해서 펼치기)</div>';
    for(const v of vs){
      const ic={'채택':'🟢','관망':'🟡','탈락':'🔴'}[v['판정']]||'⚪';
      const a=v['분석가']||{};
      h+=`<details class="ta-card"><summary>${ic} <b>${esc(v['종목'])}</b> <span style="color:var(--tx2);font-weight:400">[${esc(v['시장']||'')}]</span>`+
         `<span class="ta-chip ${v['판정']==='채택'?'g':v['판정']==='관망'?'y':'r'}">${esc(v['판정'])} ${v['확신도']??'?'}/10</span>`+
         `<span style="font-weight:400;color:var(--tx2);font-size:11px">${esc((v['근거']||'').slice(0,60))}</span></summary><div class="bd">`+
         tbl(['분석가','의견'],['기본','기술','심리','뉴스'].filter(k=>a[k]).map(k=>[`<b>${k}</b>`,esc(a[k])]))+
         (v.bull?`<div class="ta-quote bull"><b>Bull</b><br>${v.bull.map(b=>'· '+esc(b)).join('<br>')}</div>`:'')+
         (v.bear?`<div class="ta-quote bear"><b>Bear 반박</b><br>${esc(v.bear)}</div>`:'')+
         `<div class="ta-note" style="margin:8px 0 0"><b>촉매</b> ${esc(v['촉매']||'-')} · <b>리스크</b> ${esc(v['리스크']||'-')}</div></div></details>`;
    }
    h+='<div class="src" style="margin-top:10px">⚠️ 투자 자문이 아니며 판정은 참고용. 매매 판단과 책임은 사용자에게 있다. 원본 JSON: <a href="/api/db/ta_verdict" target="_blank">/api/db/ta_verdict</a></div>';
    el.innerHTML=h;
  }
  }catch(e){console.error('[ta] SKILL RESULT 렌더 실패:',e);document.getElementById('ta_sr').innerHTML='<div class="ta-note">판정 카드 렌더 실패: '+esc(String(e&&e.message||e))+' · 원본 <a href="/api/db/ta_verdict" target="_blank">JSON</a></div>';}

})();
})();
