# -*- coding: utf-8 -*-
"""
export_snapshot.py — deriv_signals.db → nmr_deriv_positioning.json
3.1.21 파생 포지셔닝 섹션 렌더러(build_report.js renderDerivPositioning)가 읽는 스키마로
현재 스냅샷(지수현황·z매트릭스·활성신호·간이 해석)을 내보낸다.

사용:  python export_snapshot.py [출력경로]     # 기본 ./nmr_deriv_positioning.json
전제:  같은 폴더의 deriv_signals.db (daily_update.py 실행으로 최신화). 없으면 아무 것도 안 함(비차단).
"""
import sqlite3, json, math, os, sys

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.environ.get("DERIV_DB") or os.path.join(BASE, "deriv_signals.db")  # 안정 경로 우선(config와 동일)
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.getcwd(), "nmr_deriv_positioning.json")

if not os.path.exists(DB):
    print("export_snapshot: DB 없음 → skip:", DB); sys.exit(0)

# (req4 fix v3.50) 마운트(D:) sqlite 직접 읽기는 disk I/O error(random access) → db.connect() 의
#   마운트-세이프 폴백(로컬 작업 DB 재사용: backfill/daily_update 가 채운 동일 경로)을 사용한다.
try:
    import db as _dbmod
    con = _dbmod.connect()
except Exception:
    con = sqlite3.connect(DB)

def one(q, a=()):
    r = con.execute(q, a).fetchone()
    return r


def _last(tbl, iid, order="date"):
    cur = con.execute(f"SELECT * FROM {tbl} WHERE id=? ORDER BY {order} DESC LIMIT 1", (iid,))
    r = cur.fetchone()
    if not r:
        return {}
    return dict(zip([d[0] for d in cur.description], r))


def num(v):
    try:
        return None if v is None else float(v)
    except Exception:
        return None


def fmt_comma(v, suffix=""):
    v = num(v)
    return "-" if v is None else (f"{v:+,.0f}{suffix}")


def zval(v):
    v = num(v)
    return None if v is None or math.isnan(v) else round(v, 2)


IDS = [("SPX", "S&P 500"), ("NDX", "Nasdaq 100"), ("KOSPI200", "KOSPI200")]

# 지수 현황
index = []
for iid, name in IDS:
    ind = _last("indicators_daily", iid)
    if not ind:
        continue
    g = con.execute("SELECT spot_close FROM indicators_daily WHERE id=? ORDER BY date", (iid,)).fetchall()
    closes = [x[0] for x in g if x[0] is not None]
    ret5 = ((closes[-1] / closes[-6] - 1) * 100) if len(closes) > 6 else None
    r1 = num(ind.get("spot_ret"))
    index.append({
        "name": name,
        "close": ("-" if ind.get("spot_close") is None else f"{ind['spot_close']:,.2f}"),
        "ret1": ("-" if r1 is None else f"{r1*100:+.2f}%"),
        "ret5": ("-" if ret5 is None else f"{ret5:+.2f}%"),
    })

# 옵션 스냅샷(미국) / KR 파생 최신
usopt = {r[0]: dict(zip(["id", "pcr_oi", "iv_skew_25d", "gex"], r)) for r in
         con.execute("SELECT id,pcr_oi,iv_skew_25d,gex FROM options_daily").fetchall()}
kr = _last("kr_derivatives_daily", "KOSPI200")
_r = one("SELECT date, pcr_oi FROM kr_derivatives_daily WHERE id='KOSPI200' AND pcr_oi IS NOT NULL ORDER BY date DESC LIMIT 1")
kr_pcr_date, kr_pcr = (_r[0], _r[1]) if _r else (None, None)
# VKOSPI: 당일 행이 결측(KRX T+1 공표)일 수 있으므로 '최신 비NULL 값+날짜'를 쓴다(stale-guard).
_r = one("SELECT date, vkospi FROM kr_derivatives_daily WHERE id='KOSPI200' AND vkospi IS NOT NULL ORDER BY date DESC LIMIT 1")
kr_vk_date, kr_vk = (_r[0], _r[1]) if _r else (None, None)
_r = one("SELECT z_vkospi FROM zscores_daily WHERE id='KOSPI200' AND date=?", (kr_vk_date,)) if kr_vk_date else None
kr_vk_z = _r[0] if _r else None
# (2026-07-17) IV스큐·GEX 도 stale-guard — 당일 KIS 스캔이 pcr 만 성공한 날 최신 비NULL(백필/전일)로 폴백, 날짜 병기.
_r = one("SELECT date, iv_skew_25d FROM kr_derivatives_daily WHERE id='KOSPI200' AND iv_skew_25d IS NOT NULL ORDER BY date DESC LIMIT 1")
kr_sk_date, kr_sk = (_r[0], _r[1]) if _r else (None, None)
_r = one("SELECT z_iv_skew_25d FROM zscores_daily WHERE id='KOSPI200' AND date=?", (kr_sk_date,)) if kr_sk_date else None
kr_sk_z = _r[0] if _r else None
_r = one("SELECT date, gex FROM kr_derivatives_daily WHERE id='KOSPI200' AND gex IS NOT NULL ORDER BY date DESC LIMIT 1")
kr_gx_date, kr_gx = (_r[0], _r[1]) if _r else (None, None)
_r = one("SELECT z_gex FROM zscores_daily WHERE id='KOSPI200' AND date=?", (kr_gx_date,)) if kr_gx_date else None
kr_gx_z = _r[0] if _r else None

I = {iid: _last("indicators_daily", iid) for iid, _ in IDS}
Z = {iid: _last("zscores_daily", iid) for iid, _ in IDS}

# (2026-07-20) IV 스큐 부호 정규화 — 이 지표만 'z(+)=주식 비우호'라 방향이 반대였다.
#   전 지표를 'z(+)=주식 우호'로 통일하려고 표시·신호 단계에서 콜−풋(=기존 풋−콜의 −1배)으로 뒤집는다.
#   z 는 선형변환이라 z(−x) = −z(x) 로 부호만 정확히 반전된다. 원본 DB(풋−콜, 시장관행)는 손대지 않는다.
for _iid in Z:
    _v = Z[_iid].get("z_iv_skew_25d")
    if _v is not None:
        Z[_iid]["z_iv_skew_25d"] = -_v
for _k in usopt:
    _v = usopt[_k].get("iv_skew_25d")
    if _v is not None:
        usopt[_k]["iv_skew_25d"] = -_v
if kr_sk is not None:
    kr_sk = -kr_sk
if kr_sk_z is not None:
    kr_sk_z = -kr_sk_z


def cellv(v_str, zscore):
    return {"v": v_str, "z": zval(zscore)}


def gbn(iid):
    g = usopt.get(iid, {}).get("gex")
    return "n/a" if g is None else f"{g/1e9:+.2f}bn"


rows = [
    {"label": "선물 베이시스 (bp)", "cells": [
        cellv(("-" if I['SPX'].get('basis_bp') is None else f"{I['SPX']['basis_bp']:+.0f}"), Z['SPX'].get('z_basis_bp')),
        cellv(("-" if I['NDX'].get('basis_bp') is None else f"{I['NDX']['basis_bp']:+.0f}"), Z['NDX'].get('z_basis_bp')),
        cellv(("-" if I['KOSPI200'].get('basis_bp') is None else f"{I['KOSPI200']['basis_bp']:+.0f}"), Z['KOSPI200'].get('z_basis_bp'))]},
    {"label": "레버리지(美)/외국인(韓) 순", "cells": [
        cellv(fmt_comma(I['SPX'].get('lev_net'), " 계약"), Z['SPX'].get('z_lev_net')),
        cellv(fmt_comma(I['NDX'].get('lev_net'), " 계약"), Z['NDX'].get('z_lev_net')),
        cellv(fmt_comma(I['KOSPI200'].get('lev_net'), " 억원"), Z['KOSPI200'].get('z_lev_net'))]},
    {"label": "자산운용(美)/기관(韓) 순", "cells": [
        cellv(fmt_comma(I['SPX'].get('asset_mgr_net'), " 계약"), Z['SPX'].get('z_asset_mgr_net')),
        cellv(fmt_comma(I['NDX'].get('asset_mgr_net'), " 계약"), Z['NDX'].get('z_asset_mgr_net')),
        cellv(fmt_comma(I['KOSPI200'].get('asset_mgr_net'), " 억원"), Z['KOSPI200'].get('z_asset_mgr_net'))]},
    {"label": "선물 OI 변화", "cells": [
        cellv(fmt_comma(I['SPX'].get('oi_chg_w'), " (주)"), Z['SPX'].get('z_oi_chg_w')),
        cellv(fmt_comma(I['NDX'].get('oi_chg_w'), " (주)"), Z['NDX'].get('z_oi_chg_w')),
        cellv(fmt_comma(I['KOSPI200'].get('oi_chg_w'), " (5일)"), Z['KOSPI200'].get('z_oi_chg_w'))]},
    # (2026-07-17) 美 옵션 3종 z: 종전 하드코딩 None → zscores 배선. Z_MINP=30 이라 30거래일
    #   (수집개시 7/11 기준 ≈ 2026-08-21 전후) 도달 시 'z making' 이 자동으로 실제 z 로 전환된다.
    {"label": "풋콜비율 (OI)", "cells": [
        cellv(("-" if usopt.get('SPX', {}).get('pcr_oi') is None else f"{usopt['SPX']['pcr_oi']:.2f}"), Z['SPX'].get('z_pcr_oi')),
        cellv(("-" if usopt.get('NDX', {}).get('pcr_oi') is None else f"{usopt['NDX']['pcr_oi']:.2f}"), Z['NDX'].get('z_pcr_oi')),
        cellv(("-" if kr_pcr is None else f"{kr_pcr:.2f}"), Z['KOSPI200'].get('z_pcr_oi'))]},
    {"label": "IV 스큐 (콜−풋)", "cells": [
        cellv(("-" if usopt.get('SPX', {}).get('iv_skew_25d') is None else f"{usopt['SPX']['iv_skew_25d']:+.3f}"), Z['SPX'].get('z_iv_skew_25d')),
        cellv(("-" if usopt.get('NDX', {}).get('iv_skew_25d') is None else f"{usopt['NDX']['iv_skew_25d']:+.3f}"), Z['NDX'].get('z_iv_skew_25d')),
        cellv(("-" if kr_sk is None else
               (f"{kr_sk:+.1f}" if kr_sk_date == I['KOSPI200'].get('date')
                else f"{kr_sk:+.1f} ({(kr_sk_date or '')[5:]})")), kr_sk_z)]},
    {"label": "딜러 감마 (GEX)", "cells": [
        # (2026-07-15) KOSPI200 GEX 종전 하드코딩 "—" → KIS 옵션체인 T+0 값(억원) 배선.
        # (2026-07-17) 당일 결측 시 최신 비NULL(백필/전일) 폴백 + 날짜 병기 — IV스큐 동일.
        cellv(gbn('SPX'), Z['SPX'].get('z_gex')), cellv(gbn('NDX'), Z['NDX'].get('z_gex')),
        cellv(("—" if kr_gx is None else
               (f"{kr_gx:+,.0f}억" if kr_gx_date == I['KOSPI200'].get('date')
                else f"{kr_gx:+,.0f}억 ({(kr_gx_date or '')[5:]})")), kr_gx_z)]},
    # VKOSPI(韓 공식 변동성지수) — 옵션체인 붕괴로 못 쓰는 PCR/IV스큐를 대체하는 변동성·공포 축.
    #   미국은 VIX 가 별도 축이라 여기서는 KOSPI200 열만 채운다.
    {"label": "VKOSPI (변동성지수)", "cells": [
        cellv("—", None), cellv("—", None),
        # 당일 결측 시 최신 비NULL 값에 날짜를 병기(예: "45.20 (07-10)") — 지연분임을 표에서 즉시 인지.
        cellv(("-" if kr_vk is None else
               (f"{kr_vk:.2f}" if kr_vk_date == I['KOSPI200'].get('date')
                else f"{kr_vk:.2f} ({(kr_vk_date or '')[5:]})")),
              (Z['KOSPI200'].get('z_vkospi') if kr_vk_date == I['KOSPI200'].get('date') else kr_vk_z))]},
]

# 활성 신호 (|z|>=1.5)
TAG = {("basis_bp", 1): "선물 프리미엄 확대(과매도 반등/위험선호)", ("basis_bp", -1): "선물 디스카운트(하락 압력)",
       ("lev_net", 1): "매수 쏠림(추세 동조)", ("lev_net", -1): "매도·이탈",
       ("asset_mgr_net", 1): "리얼머니 매수 확대", ("asset_mgr_net", -1): "리얼머니 축소(하방 경계)",
       ("oi_chg_w", 1): "신규 유입(추세 강화)", ("oi_chg_w", -1): "디레버리징(청산)",
       ("pcr_oi", 1): "공포·헤지(컨트라리안 반등)", ("pcr_oi", -1): "안주·탐욕",
       ("iv_skew_25d", 1): "위험선호 회복(헤지 수요 완화)", ("iv_skew_25d", -1): "하방 헤지 급증(방어·하락 경계)",
       ("gex", 1): "롱감마(변동성 억제)", ("gex", -1): "숏감마(변동성 확대)",
       ("vkospi", 1): "공포 극단(컨트라리안 반등 소지)", ("vkospi", -1): "변동성 진정(위험선호)"}
NM = {"SPX": "S&P500", "NDX": "나스닥", "KOSPI200": "KOSPI200"}
LB = {"basis_bp": "선물 베이시스", "lev_net": "레버리지/외국인 순", "asset_mgr_net": "자산운용/기관 순",
      "oi_chg_w": "선물 OI 변화", "pcr_oi": "풋콜비율", "iv_skew_25d": "IV 스큐(콜−풋)", "gex": "딜러 감마",
      "vkospi": "VKOSPI"}
signals = []
for iid, _ in IDS:
    z = Z[iid]
    for col in ["basis_bp", "lev_net", "asset_mgr_net", "oi_chg_w", "pcr_oi", "iv_skew_25d", "gex", "vkospi"]:
        zv = zval(z.get("z_" + col))
        if zv is not None and abs(zv) >= 1.5:
            d = 1 if zv > 0 else -1
            signals.append(f"{NM[iid]} {LB[col]} z={zv:+.2f} → {TAG[(col, d)]}")

asof_price = one("SELECT max(date) FROM prices_daily WHERE id='SPX'")[0]
asof_cot = one("SELECT max(report_date) FROM positioning_weekly WHERE id='SPX'")[0]
asof_flow = one("SELECT max(report_date) FROM positioning_weekly WHERE id='KOSPI200'")[0]
asof_usopt = one("SELECT max(date) FROM options_daily")[0]
asof_krx = kr_vk_date
_r = one("SELECT max(date) FROM kr_derivatives_daily WHERE id='KOSPI200' AND basis_bp IS NOT NULL")
asof_basis = _r[0] if _r else None
asof_kr_spot = I['KOSPI200'].get('date')

# ── stale-guard: 당일 급변동(|spot_ret|≥3%)인데 일부 축이 T+1 지연분이면 경고를 신호 목록 맨 앞에 삽입.
#    signals 배열은 빌더가 그대로 리스트 렌더 → build_report.js 수정 없이 보고서에 노출된다.
_ret = num(I['KOSPI200'].get('spot_ret'))
if asof_kr_spot and _ret is not None and abs(_ret) >= 0.03:
    _stale = [f"{lbl} {d}" for lbl, d in (("VKOSPI", kr_vk_date), ("풋콜비율", kr_pcr_date))
              if d and d < asof_kr_spot]
    if _stale:
        signals.insert(0, (f"⚠ 당일 KOSPI200 {_ret*100:+.1f}% 급변동 — {' · '.join(_stale)} 값은 "
                           f"KRX T+1 공표 지연분(당일 미반영). 해당 축 z-신호는 참고만 할 것."))

out = {
    "asof": (f"가격 {asof_price} · 미국 COT {asof_cot}(주간) · KOSPI200 수급 {asof_flow} · "
             f"미국 옵션 {asof_usopt} · KOSPI200 현물·베이시스 {asof_basis or 'n/a'}"
             f"{'(T+0 네이버 브리지)' if asof_basis and asof_krx and asof_basis > asof_krx else ''}"
             f" · KRX 공표(VKOSPI 등) {asof_krx or 'n/a'}"),
    "index": index, "rows": rows, "signals": signals,
    "market_us": "베이시스 프리미엄이나 포지셔닝은 방어적(선물 OI 감소·리얼머니 축소·딜러 감마 확인).",
    "market_kr": "현물·수급과 선물 베이시스 신호가 엇갈리면 방향 미확정 — 외국인 순매수 전환이 핵심 트리거.",
    "synthesis": "지표들이 같은 방향으로 극단(|z|≥1.5)일 때 신뢰도↑. 옵션 지표(PCR·IV스큐·미국 GEX)는 표본 축적 후 신뢰. 리서치용·투자권유 아님.",
}
con.close()
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=2)
print("export_snapshot: wrote", OUT, "| signals:", len(signals))
