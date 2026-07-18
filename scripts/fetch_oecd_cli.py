# -*- coding: utf-8 -*-
# 3.1.4 OECD 경기선행지수(CLI) — OECD SDMX 공개 API 직접 수집 (v3.67 · 2026-07-17 req5)
# 종전 KOSIS 통계표 Chrome 스크래핑(iframe 불안정·자료갱신일 관측 실패 빈발)을 대체한다.
#   소스: sdmx.oecd.org OECD.SDD.STES,DSD_STES@DF_CLI (무키·무로그인, 진폭조정 AA)
#   산출: <WORK>/nmr_oecd_cli.json = {"data_updated","months":["YYYY.MM"..],"series":{"한글국가명":[..null허용..]}}
#   merge.py 가 _ndb.sync('oecd_cli', ...) 로 DB 갱신(변동 없으면 재사용) → gen_cli_chart.py
# 사용: python3 fetch_oecd_cli.py [WORK]   (Phase 1 bash 병렬 · 서버 cron 겸용, stdlib only)
import os, sys, json, urllib.request, datetime

WORK = sys.argv[1] if (len(sys.argv) > 1 and os.path.isdir(sys.argv[1])) else "."
CTY = {"AUS": "오스트레일리아", "CAN": "캐나다", "FRA": "프랑스", "DEU": "독일", "ITA": "이탈리아",
       "JPN": "일본", "KOR": "대한민국", "MEX": "멕시코", "ESP": "스페인", "TUR": "튀르키예",
       "GBR": "영국", "USA": "미국", "BRA": "브라질", "CHN": "중국", "IND": "인도",
       "IDN": "인도네시아", "ZAF": "남아프리카공화국"}
START = "2022-01"


def main():
    key = "+".join(CTY.keys())
    u = ("https://sdmx.oecd.org/public/rest/data/OECD.SDD.STES,DSD_STES@DF_CLI,/"
         + key + ".M.LI...AA...H?startPeriod=" + START
         + "&dimensionAtObservation=AllDimensions&format=jsondata")
    # OECD WAF 가 간헐 403 을 던진다(실측 2026-07-17: 같은 쿼리가 재시도에서 통과) → 3회 백오프 재시도
    import time
    d = None
    for _try in range(3):
        try:
            r = urllib.request.urlopen(urllib.request.Request(
                u, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/vnd.sdmx.data+json"}), timeout=40)
            d = json.loads(r.read())
            break
        except Exception as e:
            if _try == 2:
                raise
            print("[oecd_cli] 재시도 %d/3 (%s)" % (_try + 1, e))
            time.sleep(3 + _try * 3)
    ds = d.get("data", d)
    struct = ds.get("structures") or ds.get("structure")
    if isinstance(struct, list):
        struct = struct[0]
    dims = ((struct or {}).get("dimensions") or {}).get("observation") or []
    # 차원 인덱스 → 값 리스트
    idx_ref = {i: dm for i, dm in enumerate(dims)}
    pos_area = pos_time = None
    for i, dm in idx_ref.items():
        did = (dm.get("id") or "").upper()
        if did in ("REF_AREA", "LOCATION"):
            pos_area = i
        if did == "TIME_PERIOD":
            pos_time = i
    if pos_area is None or pos_time is None:
        raise SystemExit("[oecd_cli] 구조 파싱 실패: REF_AREA/TIME_PERIOD 차원 없음")
    area_vals = [v.get("id") for v in dims[pos_area].get("values") or []]
    time_vals = [v.get("id") for v in dims[pos_time].get("values") or []]
    obs = ((ds.get("dataSets") or [{}])[0].get("observations")) or {}
    grid = {}  # (iso, YYYY-MM) -> val
    for k, v in obs.items():
        parts = [int(x) for x in k.split(":")]
        iso = area_vals[parts[pos_area]]
        tm = time_vals[parts[pos_time]]
        val = v[0] if isinstance(v, list) and v else None
        if iso in CTY and val is not None:
            grid[(iso, tm)] = round(float(val), 2)
    months_iso = sorted({tm for (_, tm) in grid})
    if not months_iso:
        raise SystemExit("[oecd_cli] 관측치 0건")
    months = [m.replace("-", ".") for m in months_iso]
    series = {}
    for iso, name in CTY.items():
        series[name] = [grid.get((iso, m)) for m in months_iso]
    # data_updated = 응답 prepared(발행 시각) — KOSIS '자료갱신일'을 대체하는 변동 마커
    prepared = (d.get("meta") or {}).get("prepared") or (ds.get("meta") or {}).get("prepared") or ""
    upd = (prepared[:10] if prepared else datetime.date.today().isoformat())
    out = {"unit": "지수(진폭조정, 기준 100)", "source": "OECD SDMX API (DSD_STES@DF_CLI, 진폭조정 AA)",
           "source_url": "https://sdmx.oecd.org/public/rest/data/OECD.SDD.STES,DSD_STES@DF_CLI",
           "data_updated": upd + "|" + months[-1],  # 발행일+최신월 복합 마커(같은 날 재발행 대비)
           "months": months, "series": series}
    p = os.path.join(WORK, "nmr_oecd_cli.json")
    json.dump(out, open(p, "w", encoding="utf-8"), ensure_ascii=False)
    n_last = sum(1 for v in series.values() if v and v[-1] is not None)
    print("[oecd_cli] OK — %d개국 × %d개월 (%s~%s, 최신월 값 보유 %d개국) → %s"
          % (len(series), len(months), months[0], months[-1], n_last, p))


if __name__ == "__main__":
    main()
# EOF — namoobi-market-report fetch_oecd_cli.py
