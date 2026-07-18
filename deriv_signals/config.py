# -*- coding: utf-8 -*-
"""
파생시장 포지셔닝 → 현물 선행신호 파이프라인 설정.
모든 데이터는 무료 소스(yfinance, CFTC COT 직접 다운로드)에서 수집 → API 키 불필요.
"""
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
# 게시본(사용자 폴더). 일반 PC에서는 여기서 바로 SQLite가 동작한다.
# 마운트/네트워크 파일시스템에서는 SQLite 락이 불가 → db.connect()가 로컬 임시
# 디스크에서 작업 후 이 경로로 복사(게시)한다.
import os as _os
# DB 위치: 환경변수 DERIV_DB(안정 경로, 예: ..\namoobi-market-report-server\data\deriv_signals.db) 우선 → 없으면 로컬.
# 플러그인은 매 실행 git 추출본($RUN)에서 코드를 돌리므로, 재백필 방지를 위해 DB는 안정 경로 권장(run_for_report.py가 지정).
PUBLISH_DB = Path(_os.environ["DERIV_DB"]) if _os.environ.get("DERIV_DB") else (BASE_DIR / "deriv_signals.db")
DB_PATH = PUBLISH_DB                      # 표시용(실제 작업 경로는 db.active_db())
OUT_DIR = BASE_DIR / "outputs"
OUT_DIR.mkdir(exist_ok=True)

# ── data.go.kr(공공데이터포털) 파생상품시세정보 API 키 ──
# 우선순위: 환경변수(DATA_GO_KR_KEY 또는 SECRETS_ENV 경로) → 로컬 secrets.env →
#           상위 디렉터리들의 secrets.env / SECURITY/secrets.env (예: 저장소 상위 SECURITY 폴더).
# 없으면 KOSPI200 선물/옵션(data.go.kr) 수집만 skip(나머지는 정상).
def _find_secrets():
    import os
    exp = os.environ.get("SECRETS_ENV") or os.environ.get("DATA_GO_KR_SECRETS")
    if exp and Path(exp).is_file():
        return Path(exp)
    for anc in [BASE_DIR, *BASE_DIR.parents]:
        for c in (anc / "secrets.env", anc / "SECURITY" / "secrets.env"):
            try:
                if c.is_file():
                    return c
            except Exception:
                pass
    return None


def _load_datago_key():
    import os
    k = os.environ.get("DATA_GO_KR_KEY")
    if k:
        return k.strip()
    f = _find_secrets()
    if f:
        try:
            for line in f.read_text(encoding="utf-8").splitlines():
                t = line.strip()
                if t.startswith("DATA_GO_KR_KEY") and "=" in t:
                    return t.split("=", 1)[1].strip()
        except Exception:
            pass
    return None

SECRETS_PATH = _find_secrets()          # 해석된 secrets.env 경로(없으면 None) — 디버그용
DATA_GO_KR_KEY = _load_datago_key()

# ── 백필/윈도우 파라미터 ───────────────────────────────
BACKFILL_DAYS = 420          # 약 1년치 거래일 확보(캘린더 여유분 포함)
Z_WINDOW = 60                # 롤링 z-score 윈도우(거래일). 데이터가 쌓이면 120/252 권장
Z_MINP = 30                  # z 계산 최소 표본
Z_THRESHOLD = 1.5            # |z| >= 임계값 → 신호 이벤트
FWD_HORIZONS = [1, 3, 5]     # 신호일 이후 현물수익률 검증 구간(거래일)

# 옵션(스냅샷) 파라미터
OPT_TARGET_DTE = 30          # IV 스큐 계산 목표 만기(일). 가장 가까운 만기 선택
RISK_FREE = 0.043            # BS 델타 계산용 무위험금리(근사)

# ── 대상 지수 정의 ─────────────────────────────────────
INSTRUMENTS = [
    {
        "id": "SPX", "name": "S&P 500", "region": "US",
        "spot": "^GSPC", "future": "ES=F", "option": "SPY",
        "cot": "E-MINI S&P 500 - CHICAGO MERCANTILE EXCHANGE",
        "proxy_spot": False,
    },
    {
        "id": "NDX", "name": "Nasdaq 100", "region": "US",
        "spot": "^NDX", "future": "NQ=F", "option": "QQQ",
        "cot": "NASDAQ MINI - CHICAGO MERCANTILE EXCHANGE",
        "proxy_spot": False,
    },
    {
        # KOSPI200: Yahoo ^KS200 지수는 결측(NaN) → KODEX 200 ETF로 현물 대용.
        # 선물/옵션 포지셔닝(KRX)은 무료 소스 확보 불가 → KRX 자격증명 필요(README 참고).
        "id": "KOSPI200", "name": "KOSPI 200", "region": "KR",
        "spot": "069500.KS", "future": None, "option": None,
        "cot": None,
        "proxy_spot": True,
    },
]

# 지표 메타: 신호 방향 해석용(expected=현물수익률과의 통상 기대부호). 실제부호는 검증표로 확인.
INDICATOR_META = {
    "basis_bp":        {"label": "선물 베이시스(bp)",     "expected": +1, "cat": "futures"},
    "oi_chg_w":        {"label": "선물 OI 주간변화",       "expected": +1, "cat": "positioning"},
    "lev_net":         {"label": "레버리지펀드(美)/외국인(韓) 순매수", "expected": +1, "cat": "positioning"},
    "asset_mgr_net":   {"label": "자산운용사(美)/기관(韓) 순매수",     "expected": +1, "cat": "positioning"},
    "pcr_oi":          {"label": "풋콜비율(미결제)",       "expected": -1, "cat": "options"},
    "pcr_vol":         {"label": "풋콜비율(거래량)",       "expected": -1, "cat": "options"},
    "iv_skew_25d":     {"label": "25델타 IV 스큐(풋-콜)",  "expected": -1, "cat": "options"},
    "delta_imbalance": {"label": "델타가중 풋/콜 불균형",  "expected": -1, "cat": "options"},
    "gex":             {"label": "딜러 감마(GEX)",         "expected": +1, "cat": "options"},
    # VKOSPI(韓): KRX 공식 변동성지수. 옵션체인 붕괴(행사가 사다리가 현물 미커버)로 쓸 수 없는
    #   PCR/IV스큐를 대체하는 KOSPI200 변동성·공포 축. 컨트라리안(공포 극단 → 반등) → expected=-1.
    "vkospi":          {"label": "VKOSPI(변동성지수)",     "expected": -1, "cat": "volatility"},
}
