#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fetch_infl_fcst.py — 3.1.2 물가 '앞으로의 경로' 공식 전망 3종 (2026-10-24 신설 · 한경MONEY 2026-10 이은택 'CPI와 장기금리의 암울한 예언')

왜: 기사 차트(블룸버그 50여 기관 CPI 전망 중앙값)는 유료라 못 가져온다. 같은 성격의 공식·무료 소스로 대체:
  ① 필라델피아 연준 SPF(Survey of Professional Forecasters) — 40여 기관 중앙값, CPI·코어CPI·PCE·코어PCE **향후 5개 분기**.
     분기 1회(2·5·8·11월 중순) 갱신. 값은 '전분기 대비 연율'이라 홈피 차트(YoY)에 얹으려면 **실제 지수(FRED)에 전망 경로를
     이어붙여 분기평균 지수 → YoY 로 환산**한다(아래 _spf_yoy). 전망치는 전부 (E).
  ② FOMC SEP(경제전망 요약) — 연준 위원 중앙값, 연말(Q4/Q4) PCE·코어PCE. FRED PCECTPICTM·JCXFECTM. **CPI 는 없다.**
  ③ 클리블랜드 연준 Inflation Nowcasting — 당월·익월 CPI·코어CPI·PCE·코어PCE 일별 나우캐스트(MoM·YoY). 발표 전 1~2개월.
     실측(2026-10-23): 9월 CPI 나우캐스트 MoM 0.53 vs 실제 0.65 — 나우캐스트도 틀린다. actual 이 있으면 같이 저장해 오차를 보여준다.
  + 클리블랜드 연준 기대인플레 모델(FRED EXPINF1YR·2YR·5YR·10YR, 월간) — 경로가 아닌 수평 기대치, 표에만.
산출: data/db/infl_fcst.json
  { as_of, spf:{survey, vars:{CPI:{qq:[[q,v]], yoy:[[YYYY-MM, v, src]], annual:{yr:v}}, ...}},
    sep:{updated, PCE:[[yr,v]], COREPCE:[[yr,v]]}, nowcast:{as_of, months:[{m, CPI:{mom,yoy,act_mom}, ...}]},
    expinf:{as_of, y1,y2,y5,y10}, ext:{CPI:[[YYYY-MM, v, src]], ...} }   ← ext = 차트용(나우캐스트 월 + SPF 분기말 월, 전부 E)
cron: 20 6 * * *   (나우캐스트는 매일 바뀜 · SPF/SEP 는 분기 1회지만 호출이 싸서 같이)
리포트(gen_macro_charts.py _ch_infl · build_report.js 3.1.2)도 /api/db/infl_fcst 를 읽어 같은 점선·표를 넣는다 — 리포트=홈피 동일.
"""
import io, json, sys, urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE / "scripts"))
from nmr_fred import fred_series, fred_key  # noqa: E402

OUT = BASE / "data" / "db" / "infl_fcst.json"
KST = timezone(timedelta(hours=9))
UA = {"User-Agent": "Mozilla/5.0"}
SPF_URL = ("https://www.philadelphiafed.org/-/media/frbp/assets/surveys-and-data/"
           "survey-of-professional-forecasters/historical-data/medianlevel.xlsx")
NOW_URL = "https://www.clevelandfed.org/-/media/files/webcharts/inflationnowcasting/nowcast_%s.json"
VARS = ["CPI", "CORECPI", "PCE", "COREPCE"]
IDX = {"CPI": "CPIAUCSL", "CORECPI": "CPILFESL", "PCE": "PCEPI", "COREPCE": "PCEPILFE"}   # FRED 지수(레벨)
NOW_NAME = {"CPI Inflation": "CPI", "Core CPI Inflation": "CORECPI", "PCE Inflation": "PCE", "Core PCE Inflation": "COREPCE"}


def get(url, timeout=40):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout).read()


def qlab(y, q):
    return f"{y}Q{q}"


def qend(y, q):
    return f"{y}-{q*3:02d}"


def qnext(y, q):
    return (y + 1, 1) if q == 4 else (y, q + 1)


# ───────── ① SPF ─────────
def fetch_spf(idx):
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(get(SPF_URL)), read_only=True)
    out = {"vars": {}}
    for v in VARS:
        rows = [r for r in wb[v].iter_rows(values_only=True) if r and isinstance(r[0], (int, float))]
        last = rows[-1]
        y, q = int(last[0]), int(last[1])
        out["survey"] = qlab(y, q)
        qq = []
        yy, qq_ = y, q
        for k in range(6):
            val = last[2 + k]
            if isinstance(val, (int, float)):
                qq.append([qlab(yy, qq_), round(float(val), 2)])
            yy, qq_ = qnext(yy, qq_)
        annual = {}
        for k, off in enumerate((0, 1, 2)):
            val = last[8 + k]
            if isinstance(val, (int, float)):
                annual[str(y + off)] = round(float(val), 2)
        out["vars"][v] = {"qq": qq, "annual": annual, "yoy": _spf_yoy(qq, idx.get(v) or {})}
    return out


def _mprev(ym):
    y, m = int(ym[:4]), int(ym[5:7])
    return f"{y-1}-12" if m == 1 else f"{y}-{m-1:02d}"


def _spf_yoy(qq, idx):
    """전분기비 연율 전망 → 월별 지수 경로 → 분기평균 → YoY. 월 단위로 잇는다:
    실제가 있는 월은 실제 지수, 없는 월은 직전 월 × (1+r/100)^(1/12) (r = 그 분기의 SPF 전망).
    → 일부만 발표된 분기(예: PCE 9월 미발표)도 실제 7·8월 + 전망 9월로 평균해, 전망을 분기 전체에 덮어쓰지 않는다.
    YoY 분모 = 전년 동분기 실제 평균(2025-10 CPI 미발표(셧다운) 같은 결측은 있는 달만 평균, 1개월뿐이면 제외).
    실제 3개월이 다 있는 분기는 건너뛴다(차트에 이미 있음)."""
    lvl = dict(idx)
    out = []
    for lab, r in qq:
        y, q = int(lab[:4]), int(lab[5])
        ms = [f"{y}-{m:02d}" for m in range(q * 3 - 2, q * 3 + 1)]
        if all(m in idx for m in ms):
            continue
        ok = True
        for m in ms:
            if m in lvl:
                continue
            p = _mprev(m)
            if p not in lvl:
                ok = False; break
            lvl[m] = lvl[p] * (1 + r / 100) ** (1 / 12)
        if not ok:
            break
        # 분모 = 전년 동분기 평균. 실제 우선, 실제가 없는 달(아직 미발표·앞 분기 전망)은 같은 경로(lvl)의 전망값 — 2027Q4 는 2026Q4 전망이 분모
        base = [lvl[f"{y-1}-{m:02d}"] for m in range(q * 3 - 2, q * 3 + 1) if f"{y-1}-{m:02d}" in lvl]
        if len(base) >= 2:
            cur = sum(lvl[m] for m in ms) / 3
            out.append([qend(y, q), round((cur / (sum(base) / len(base)) - 1) * 100, 2), "spf"])
    return out


# ───────── ② FOMC SEP ─────────
def fetch_sep():
    out = {}
    for k, sid in (("PCE", "PCECTPICTM"), ("COREPCE", "JCXFECTM")):
        s = fred_series(sid, start="2024-01-01")
        out[k] = [[int(d[:4]), round(v, 2)] for d, v in s if d[:4] >= str(datetime.now().year)]
    # 갱신일(=최근 SEP 회의 뒤 FRED 반영일) — 키 있을 때만
    key = fred_key()
    if key:
        try:
            j = json.loads(get(f"https://api.stlouisfed.org/fred/series?series_id=PCECTPICTM&api_key={key}&file_type=json", 15))
            out["updated"] = (j.get("seriess") or [{}])[0].get("last_updated", "")[:10]
        except Exception:
            pass
    return out


# ───────── ③ 클리블랜드 나우캐스트 ─────────
def _now_file(kind):
    a = json.loads(get(NOW_URL % kind))
    res = {}
    for ch in a[-3:]:
        sub = ch["chart"].get("subcaption", "")       # '2026-10'
        try:
            y, m = sub.split("-"); mk = f"{int(y)}-{int(m):02d}"
        except Exception:
            continue
        cats = [c["label"] for c in ch["categories"][0]["category"]]
        d = {"_asof": ch["chart"].get("_comment", "")[:10]}
        for ds in ch["dataset"]:
            nm = ds["seriesname"]; act = nm.startswith("Actual ")
            key = NOW_NAME.get(nm.replace("Actual ", ""))
            if not key:
                continue
            vals = [(cats[i], d_["value"]) for i, d_ in enumerate(ds["data"]) if d_.get("value") not in ("", None)]
            if not vals:
                continue
            d.setdefault(key, {})["act" if act else "now"] = round(float(vals[-1][1]), 2)
            if not act:
                d["_last"] = vals[-1][0]
        res[mk] = d
    return res


def fetch_nowcast():
    mo, yr = _now_file("month"), _now_file("year")
    months = []
    for mk in sorted(set(mo) | set(yr)):
        a, b = mo.get(mk, {}), yr.get(mk, {})
        row = {"m": mk, "last": a.get("_last") or b.get("_last")}
        for v in VARS:
            row[v] = {"mom": a.get(v, {}).get("now"), "yoy": b.get(v, {}).get("now"),
                      "act_mom": a.get(v, {}).get("act"), "act_yoy": b.get(v, {}).get("act")}
        months.append(row)
    asof = (list(mo.values()) or [{}])[-1].get("_asof", "")
    return {"as_of": asof, "months": months}


# ───────── 기대인플레 ─────────
def fetch_expinf():
    out = {}
    for k, sid in (("y1", "EXPINF1YR"), ("y2", "EXPINF2YR"), ("y5", "EXPINF5YR"), ("y10", "EXPINF10YR")):
        s = fred_series(sid, start="2025-01-01")
        if s:
            out[k] = round(s[-1][1], 2); out["as_of"] = s[-1][0][:7]
    return out


def main():
    now = datetime.now(KST)
    idx = {}
    for v, sid in IDX.items():
        s = fred_series(sid, start=(now - timedelta(days=4 * 365)).isoformat()[:10])
        idx[v] = {d[:7]: val for d, val in s}
    res = {"as_of": now.strftime("%Y-%m-%d %H:%M"), "src": {
        "spf": "필라델피아 연준 SPF 중앙값(분기 1회) — 전분기비 연율을 FRED 지수에 이어붙여 YoY 환산(E)",
        "sep": "FOMC SEP 중앙값(FRED PCECTPICTM·JCXFECTM) — Q4/Q4, CPI 없음",
        "nowcast": "클리블랜드 연준 Inflation Nowcasting(일별) — 당월·익월 MoM·YoY",
        "expinf": "클리블랜드 연준 기대인플레 모델(FRED EXPINF*, 월간)"}}
    for name, fn, args in (("spf", fetch_spf, (idx,)), ("sep", fetch_sep, ()), ("nowcast", fetch_nowcast, ()), ("expinf", fetch_expinf, ())):
        try:
            res[name] = fn(*args)
        except Exception as e:
            res[name] = None; res.setdefault("err", {})[name] = repr(e)[:160]
            print(f"  ⚠ {name} 실패: {repr(e)[:120]}", flush=True)
    # 차트용 확장 경로 — 실제 마지막 월 이후: 나우캐스트 월(YoY) → SPF 분기말(YoY). 전부 (E)
    ext = {}
    for v in VARS:
        pts = []
        last_act = max(idx[v]) if idx.get(v) else ""
        for row in (res.get("nowcast") or {}).get("months") or []:
            if row["m"] > last_act and row[v].get("yoy") is not None:
                pts.append([row["m"], row[v]["yoy"], "nowcast"])
        used = {p[0] for p in pts}
        for p in ((res.get("spf") or {}).get("vars") or {}).get(v, {}).get("yoy") or []:
            if p[0] > last_act and p[0] not in used:
                pts.append(p)
        ext[v] = sorted(pts)
    res["ext"] = ext
    res["last_actual"] = {v: (max(idx[v]) if idx.get(v) else None) for v in VARS}
    OUT.write_text(json.dumps(res, ensure_ascii=False), encoding="utf-8")
    sp = (res.get("spf") or {}).get("survey"); nc = (res.get("nowcast") or {}).get("months") or []
    print(f"[inflf] ✅ SPF {sp} · SEP {len((res.get('sep') or {}).get('PCE') or [])}yr · 나우캐스트 {[m['m'] for m in nc]} · "
          f"ext CPI {ext['CPI'][:3]} → {OUT}", flush=True)


if __name__ == "__main__":
    main()
