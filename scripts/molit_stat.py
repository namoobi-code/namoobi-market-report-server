#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""molit_stat.py — 국토교통 통계누리 공급 지표 (2026-08-08 신설 · 매일 07:40 cron).

소스: stat.molit.go.kr `/portal/stat/data.do` — **무인증 JSON** (실측 2026-08-08).
      화면이 호출하는 엔드포인트를 그대로 쓴다. 공식 문서화된 OpenAPI 가 아니므로
      국토부가 화면 구조를 바꾸면 깨질 수 있다(그 경우 formId·styleNum 재확인 필요).

수집 통계 (formId / styleNum 은 실측 확인값)
  2082/128  시군구별 미분양현황            2001-12~   컬럼 0월 1시도 2시군구 3호
  5328/1    공사완료후 미분양(준공후)       2007-01~   컬럼 0월 1시도 2합계 3부문 4규모 5호
  1946/1    부문별 주택건설 인허가실적      2007-01~   컬럼 0월 1구분 2부문 3시도 4호
  5386/1    부문별 주택건설 착공실적        2011-01~   컬럼 동일
  5372/1    부문별 주택건설 준공(사용검사)  2010-07~   컬럼 동일

제약: **한 요청당 최대 60개월** (초과 시 빈 배열) → 5년 단위로 끊어 요청한다.
산출: data/db/molit.json
      {asof, series:{key:{label,unit,note,t:[YYYYMM],r:{지역:[값|null]}}}}
사용: molit_stat.py [--full]   (기본=최근 5년 갱신 · --full=2001년부터 전체 재수집)
"""
import json, sys, time, urllib.request, urllib.error
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "data" / "db" / "molit.json"
URL = "https://stat.molit.go.kr/portal/stat/data.do"
UA = {"User-Agent": "Mozilla/5.0 (namoobi market terminal)"}
FULL = "--full" in sys.argv

# 시도 표준 순서 — 그래프 범례 정렬용(전국을 맨 앞)
SIDO = ["전국", "서울", "부산", "대구", "인천", "광주", "대전", "울산", "세종",
        "경기", "강원", "충북", "충남", "전북", "전남", "경북", "경남", "제주"]
KWON = {"수도권": ["서울", "인천", "경기"]}


def fetch(form_id, style, start, end, tries=3):
    u = (f"{URL}?formId={form_id}&styleNum={style}&apprYn=Y"
         f"&startDate={start}&endDate={end}")
    for k in range(tries):
        try:
            req = urllib.request.Request(u, headers=UA)
            raw = urllib.request.urlopen(req, timeout=120).read()
            return json.loads(raw).get("data") or []
        except Exception as e:
            if k == tries - 1:
                print(f"    ⚠ {form_id} {start}~{end} 실패: {e}")
                return []
            time.sleep(3 * (k + 1))
    return []


def chunks(y0):
    """(start,end) YYYYMM 5년 단위 — 통계누리 60개월 제한 대응."""
    now = datetime.now()
    y = y0
    while y <= now.year:
        e = min(y + 4, now.year)
        yield f"{y}01", f"{e}12" if e < now.year else f"{now.year}{now.month:02d}"
        y = e + 1


def num(s):
    s = str(s or "").replace(",", "").strip()
    if s in ("", "-", "‐", "X", "x", "null", "None"):
        return None
    try:
        return float(s)
    except Exception:
        return None


def decum(ts, vs):
    """연초 누계(YTD) → 당월 값. 1월은 그대로, 그 외는 전월 대비 차분.
    (실측 2026-08-08: 인허가 1946 은 1월 16,531 → 12월 379,834 → 1월 리셋되는 누계였다.
     이걸 월별로 착각하면 12개월 합이 실제의 4~5배로 부풀어 오른다.)"""
    out = []
    for i, t in enumerate(ts):
        v = vs[i]
        if v is None:
            out.append(None); continue
        if t[4:] == "01":
            out.append(v); continue
        pt = f"{t[:4]}{int(t[4:]) - 1:02d}"          # 직전 월(같은 해)
        j = ts.index(pt) if pt in ts else -1
        pv = vs[j] if j >= 0 else None
        out.append(None if pv is None else max(0.0, v - pv))
    return out


def collect(form_id, style, y0, keep, region_col, value_col, label, unit, note,
            cumulative=False):
    """keep(row)->bool 로 총계 행만 남기고, region_col 을 지역명·value_col 을 값으로 뽑는다."""
    acc, prov = {}, set()                               # {ym: {region: v}}, 잠정치 월 집합
    for s, e in chunks(y0):
        rows = fetch(form_id, style, s, e)
        print(f"    {s}~{e}: {len(rows):,}행")
        for r in rows:
            if not keep(r):
                continue
            # (2026-08-08) 최근 월은 "2026-06 p)" 처럼 잠정치 표식이 붙는다.
            # 예전엔 이 행들을 전부 버려서 최신 11개월이 통째로 비었었다.
            raw = str(r.get("0", "")).strip()
            isp = "p)" in raw
            ym = raw.replace("-", "").split()[0][:6] if raw else ""
            if len(ym) != 6 or not ym.isdigit():
                continue
            if isp:
                prov.add(ym)
            reg = str(r.get(region_col, "")).replace(" ", "")
            v = num(r.get(value_col))
            if not reg or v is None:
                continue
            acc.setdefault(ym, {})[reg] = v
        time.sleep(1.2)                                 # 서버 배려
    if not acc:
        return None
    ts = sorted(acc)
    regs = [x for x in SIDO if any(x in acc[t] for t in ts)]
    for x in sorted({k for t in ts for k in acc[t]}):    # 표준목록 밖 지역도 뒤에 붙임
        if x not in regs:
            regs.append(x)
    out = {r: [acc[t].get(r) for t in ts] for r in regs}
    if cumulative:                                   # 누계 통계는 당월 값으로 환산
        out = {r: decum(ts, v) for r, v in out.items()}
    # (2026-08-08) '전국' 행을 안 주는 통계가 있다 — 미분양(2082)은 2007년부터 시도만 제공.
    # 비어 있는 달은 17개 시도 합으로 채운다(시도가 모두 있는 달만).
    sido = [x for x in SIDO if x != "전국" and x in out]
    if len(sido) >= 15:
        nat = out.get("전국") or [None] * len(ts)
        out["전국"] = [nat[i] if nat[i] is not None else
                      (None if any(out[m][i] is None for m in sido)
                       else sum(out[m][i] for m in sido)) for i in range(len(ts))]
    # 수도권 파생 — 서울+인천+경기 합
    for k, mem in KWON.items():
        if all(m in out for m in mem):
            out[k] = [None if any(out[m][i] is None for m in mem)
                      else sum(out[m][i] for m in mem) for i in range(len(ts))]
    pi = next((i for i, t in enumerate(ts) if t in prov), None)   # 잠정치 시작 위치
    return {"label": label, "unit": unit, "note": note, "t": ts, "r": out,
            "prov": ts[pi] if pi is not None else None}


LAG = 27          # 착공 → 준공 실측 시차(개월). 2026-08-08 전국 12개월이동합 기준
                  # 상관계수 최대점: 27개월에서 +0.833 (표본 148). 아파트 표준 공사기간과 일치.
                  # ※ 인허가→준공은 23개월에서 상관이 더 높게(+0.869) 나오지만 인허가가
                  #   착공보다 앞서는 순서와 모순되므로, 사이클 동조를 잡은 것으로 보고 채택하지 않음.


def derive_movein(S):
    """향후 입주물량 추정 — 공식 통계가 없어 착공을 LAG 만큼 밀어 만든다.

    입주물량(준공)은 전세가격의 가장 강한 선행 변수인데 '예정' 통계가 공표되지 않는다.
    이미 확정된 착공 실적을 공사기간만큼 이동시키면 향후 약 2년치가 보인다.
    확정(준공 실적)과 추정(착공 이동)을 **다른 계열로 분리**해 섞이지 않게 한다.
    """
    st, dn = S.get("start"), S.get("done")
    if not st or not dn:
        return None
    def shift(t):
        y, m = int(t[:4]), int(t[4:]) + LAG
        y += (m - 1) // 12; m = (m - 1) % 12 + 1
        return f"{y}{m:02d}"
    ts = sorted(set(dn["t"]) | {shift(t) for t in st["t"]})
    regs = [r for r in dn["r"] if r in st["r"]]
    act, prj = {}, {}
    for r in regs:
        a = dict(zip(dn["t"], dn["r"][r]))
        p = {shift(t): v for t, v in zip(st["t"], st["r"][r])}
        last = max((t for t in dn["t"] if a.get(t) is not None), default=None)
        act[r] = [a.get(t) for t in ts]
        # 실적이 있는 구간은 추정을 그리지 않는다(겹쳐 보이면 혼동)
        prj[r] = [p.get(t) if (last is None or t > last) else None for t in ts]
    return {"label": "입주물량(준공)", "unit": "호", "t": ts, "r": act, "p": prj,
            "lag": LAG,
            "note": (f"확정=준공 실적 · 추정=착공을 <b>{LAG}개월</b> 뒤로 민 값"
                     f"(착공→준공 실측 시차, 상관 +0.83). 공식 '입주예정' 통계가 없어 자체 산출한 값이다.")}


def main():
    y0 = 2001 if FULL else datetime.now().year - 4
    print(f"[molit] 수집 시작 (from {y0}) — 통계누리 무인증 JSON")
    S = {}
    tot = lambda r: "총" in str(r.get("1", "")) and "총" in str(r.get("2", ""))

    print("  ① 미분양(시군구별 → 시도 계)")
    S["unsold"] = collect(2082, 128, max(y0, 2001),
                          lambda r: str(r.get("2", "")).strip() == "계",
                          "1", "3", "미분양", "호",
                          "시도별 미분양 재고 — 공급과잉·침체 국면의 정석 지표")

    print("  ② 준공후 미분양 (악성 미분양)")
    S["unsold_done"] = collect(5328, 1, max(y0, 2007),
                               lambda r: str(r.get("3", "")).strip() == "계"
                               and str(r.get("4", "")).strip() == "계",
                               "1", "5", "준공후 미분양", "호",
                               "다 짓고도 안 팔린 물량 — 미분양 중에서도 질이 나쁜 신호")

    # cum=True : 원자료가 연초부터의 누계인 통계 (실측으로 확인 — 인허가만 해당)
    for key, fid, yy, cum, lab, nt in (
            ("permit", 1946, 2007, True, "주택 인허가",
             "인허가 → 착공 → 준공까지 1~3년 — 향후 공급량 선행지표"),
            ("start", 5386, 2011, False, "주택 착공",
             "인허가보다 확정적인 공급 신호 — 착공 급감은 2~3년 뒤 공급절벽"),
            ("done", 5372, 2010, False, "주택 준공",
             "입주물량 — 늘면 전세 약세, 줄면 전세 강세 압력")):
        print(f"  ③ {lab}{' (누계→월별 환산)' if cum else ''}")
        S[key] = collect(fid, 1, max(y0, yy), tot, "3", "4", lab, "호", nt,
                         cumulative=cum)

    S = {k: v for k, v in S.items() if v}
    mv = derive_movein(S)                    # 착공 → 향후 입주물량 추정(파생 · 추가 수집 없음)
    if mv:
        S["movein"] = mv
        print(f"  ④ 입주물량 추정 (착공 +{LAG}개월)")
    if not S:
        print("[molit] ❌ 수집 실패 — 저장 생략(기존 파일 보존)")
        return
    # 부분 실패 시 기존 계열 보존
    old = {}
    try:
        old = (json.loads(OUT.read_text(encoding="utf-8")) or {}).get("series") or {}
    except Exception:
        pass
    merged = {**old, **S}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "asof": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "src": "국토교통 통계누리(stat.molit.go.kr) · 무인증 공개 JSON",
        "series": merged}, ensure_ascii=False), encoding="utf-8")
    for k, v in merged.items():
        print(f"[molit] ✅ {k:12s} {v['label']:12s} {len(v['t'])}개월 "
              f"{v['t'][0]}~{v['t'][-1]} · 지역 {len(v['r'])}")
    print(f"[molit] → {OUT}")


if __name__ == "__main__":
    main()
