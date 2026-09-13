#!/usr/bin/env python3
"""고용·경기 지표(3.1.3) 서버 자동 최신화 — FRED 무키 CSV.

employment.json 의 '최신 수치·기준·예상영향'을 매일 갱신한다.
의미·시장영향 설명문과 발표일자(release, FRED release/dates 실측)는 보고서가 관리하므로 건드리지 않는다.
예상영향 문구·임계값은 보고서 merge.py `_emp_interp` 와 동일하게 유지한다(리포트=홈피 일치).
ISM 제조업·서비스업 PMI 는 FRED 무키로 못 받아 보고서 실행 때만 갱신된다.

시계열 파일(series_emp_*)도 같은 값으로 이어붙여 차트가 함께 최신화된다.
"""
import json, csv, io, urllib.request
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DB   = BASE / "data" / "db"

def _key():
    """FRED API 키 — ~/namoobi/fred.key (600). fredgraph.csv 는 서버망에서 멈춰서 API 필수."""
    try:
        return (BASE / "fred.key").read_text().strip()
    except Exception:
        return ""

def fred(series_id, n=420):
    k = _key()
    if k:
        url = ("https://api.stlouisfed.org/fred/series/observations"
               f"?series_id={series_id}&api_key={k}&file_type=json")
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=25) as r:
            obs = json.loads(r.read().decode()).get("observations", [])
        out = [(o["date"], float(o["value"])) for o in obs if o.get("value") not in (".", "", None)]
        return out[-n:]
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=25) as r:
        rows = list(csv.reader(io.StringIO(r.read().decode())))
    return [(d, float(v)) for d, v in rows[1:] if v not in (".", "")][-n:]

def save_series(name, pts):
    p = DB / f"{name}.json"
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        d = {}
    d["data"] = [[a, b] for a, b in pts]
    d["as_of"] = d["marker"] = datetime.now().strftime("%Y-%m-%d")
    p.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")

def interp(name, s0):
    """(2026-09-13 리포트=홈피 일치) 보고서 merge.py `_emp_interp` 와 **동일 문구·임계값**.
    종전엔 이 스크립트가 독자 문구(예: NFP '완만한 증가', 소매 '위축, 소비둔화 신호')와 다른 임계값으로
    07:40 에 DB 를 덮어써 06시 보고서의 예상영향과 홈피가 매일 어긋났다(9/12 실측). merge.py 를 고치면 여기도 같이 고친다."""
    import re
    m = re.search(r'-?\d+\.?\d*', str(s0).replace(',', ''))
    if not m:
        return ''
    v = float(m.group())
    if '실업수당' in name or '청구' in name:
        return (f"청구 {s0} — 낮은 수준, 노동시장 견조·증시 우호" if v < 23 else
                f"청구 {s0} — 증가세, 고용둔화·경기우려로 증시 부담" if v >= 25 else
                f"청구 {s0} — 보합권, 고용 완만 둔화 관망")
    if 'NFP' in name or '비농업' in name:
        return f"신규고용 {s0} — 견조, 과열 시 금리인상 우려" if v >= 150 else f"신규고용 {s0} — 둔화, 금리인하 명분·증시 양면"
    if '실업' in name:
        return f"실업률 {s0} — 상승 압력, 인하 기대로 증시 양면" if v >= 4.4 else f"실업률 {s0} — 낮음, 노동시장 타이트·인하 지연"
    if '소매' in name:
        return f"소비 {s0} — 견조하나 인플레·금리 자극" if v >= 0 else f"소비 {s0} — 둔화, 경기 우려·인하 기대"
    if 'ISM' in name:
        return f"{s0} — 50 상회 확장, 경기민감·반도체 우호" if v >= 50 else f"{s0} — 50 하회 위축, 경기둔화 우려"
    if 'GDP' in name:
        return f"성장 {s0} — 견조, 실적 우호" if v >= 2 else f"성장 {s0} — 둔화, 경기 우려"
    return ''

def quarter(ym):
    """'2026-04-01' → '2026 Q2' (보고서 nmr_reasons 의 GDP 기준 표기와 동일)."""
    q = {"01": "Q1", "04": "Q2", "07": "Q3", "10": "Q4"}.get(str(ym)[5:7])
    return f"{str(ym)[:4]} {q}" if q else str(ym)[:7]

def main():
    p = DB / "employment.json"
    d = json.loads(p.read_text(encoding="utf-8"))
    rows = {r["name"]: r for r in d["data"]}
    today = datetime.now().strftime("%Y-%m-%d")

    def setv(name, value, asof, _interp=None):
        # release(발표일자)는 건드리지 않는다 — 보고서(nmr_reasons, FRED release/dates 실측)가 관리.
        r = rows.get(name)
        if not r:
            return
        r["value"], r["asof"], r["interp"] = value, asof, (_interp or interp(name, value))

    # 초기 실업수당 청구 (주간)
    icsa = fred("ICSA")
    dt, v = icsa[-1]
    setv("초기 실업수당 청구건수", f"{v/1e4:.1f}만 건".replace(".0만", "만"), dt)
    save_series("series_emp_jobless", icsa[-260:])

    # NFP = PAYEMS 전월차 (천명)
    pay = fred("PAYEMS")
    chg = round(pay[-1][1] - pay[-2][1])
    setv("NFP (비농업취업자 변화)", f"{chg}천명", pay[-1][0][:7])
    save_series("series_emp_nfp", pay[-120:])
    save_series("series_emp_nfp_mom",
                [(pay[i][0], round(pay[i][1]-pay[i-1][1])) for i in range(len(pay)-60, len(pay))])

    # 실업률
    un = fred("UNRATE")
    setv("실업률", f"{un[-1][1]:.1f}", un[-1][0][:7])
    save_series("series_emp_unemp", un[-120:])

    # 소매판매 MoM
    rs = fred("RSAFS")
    mom = round((rs[-1][1]/rs[-2][1]-1)*100, 2)
    setv("소매판매 (MoM)", f"{mom}", rs[-1][0][:7])
    save_series("series_emp_retail", rs[-120:])
    save_series("series_emp_retail_mom",
                [(rs[i][0], round((rs[i][1]/rs[i-1][1]-1)*100, 2)) for i in range(len(rs)-60, len(rs))])

    # (2차 req30) ISM 제조업·서비스업 — FRED 미제공(라이선스 종료).
    # tradingeconomics 공개 페이지 meta description 에 최신값·기준월이 문장으로 들어있어 파싱한다.
    # 예: "decreased to 53.30 points in June from 54 points in May of 2026"
    def ism(page, row_name, series_name):
        try:
            req2 = urllib.request.Request(f"https://tradingeconomics.com/united-states/{page}",
                                          headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
            with urllib.request.urlopen(req2, timeout=20) as r:
                h = r.read().decode(errors="replace")
            import re as _re
            m = _re.search(r'content="[^"]*?(?:increased|decreased|rose|fell|edged \w+|was unchanged at|came in at|stood at)'
                           r' t?o? ?([0-9]{2}(?:\.[0-9]+)?) points in (\w+)[^"]*?of (\d{4})', h)
            if not m:
                return
            v = float(m.group(1))
            mon = datetime.strptime(m.group(2)[:3], "%b").month
            asof = f"{m.group(3)}-{mon:02d}"
            setv(row_name, f"{v:.1f}", asof)
            # 시계열도 이어붙임
            sp = DB / f"{series_name}.json"
            try:
                sd = json.loads(sp.read_text(encoding="utf-8"))
                arr = sd.get("data") or []
                if not arr or arr[-1][0][:7] != asof:
                    arr.append([asof + "-01", v])
                sd["data"] = arr[-160:]
                sd["as_of"] = sd["marker"] = today
                sp.write_text(json.dumps(sd, ensure_ascii=False), encoding="utf-8")
            except Exception:
                pass
        except Exception as e:
            print(f"ISM {page} 실패: {type(e).__name__}")
    ism("business-confidence", "ISM 제조업 PMI", "series_emp_ism_mfg")
    ism("non-manufacturing-pmi", "ISM 서비스업 PMI", "series_emp_ism_svc")

    # GDP 성장률 (연율, 분기)
    g = fred("A191RL1Q225SBEA")
    setv("GDP 성장률 (연율)", f"{g[-1][1]:.1f}", quarter(g[-1][0]))   # 기준 = '2026 Q2' (보고서 표기와 동일)
    save_series("series_emp_gdp", g[-60:])

    d["as_of"] = d["marker"] = today
    d["auto_note"] = "FRED 무키 CSV 매일 자동 갱신 (ISM 2종은 보고서 실행 시 갱신)"
    p.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    print("employment 갱신:", ", ".join(f'{r["name"]}={r["value"]}' for r in d["data"]))

if __name__ == "__main__":
    main()
