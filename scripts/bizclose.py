#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bizclose.py — 사업자 폐업률 (KOSIS 국세청 국세통계, 연간 2005~)

배경: "소상공인 폐업률이 전체 폐업률을 웃돈다"는 그림을 재현·검증하려면
      분자(폐업자)와 분모(가동사업자)를 같은 표에서 같은 기준으로 뽑아야 한다.
      두 표를 섞으면 과세기간·집계시점이 어긋나 폐업률이 1~2%p씩 틀어진다.

통계표 (실측 확인 2026-08-15)
  133 / TX_13301_A161  9.8.2 사업자 현황Ⅱ(지역,업태) 2005~2024
      한 표 안에 '총계(=가동사업자)·신규·폐업'이 다 있고 지역·업태로 쪼갤 수 있다.
  133 / TX_13301_A169  9.8.13 폐업자 현황Ⅳ           2005~2025
      가동사업자가 없어 폐업률은 못 내지만 **폐업자 수는 1년 더 최신**이라 함께 받는다.

폐업률 정의 = 폐업 ÷ (가동 + 폐업)
  국세청·언론이 쓰는 정의다. '폐업 ÷ 가동'으로 하면 같은 해 값이 1%p 가까이 커진다.
  실측 2024 전체: 1,008,282 ÷ (10,145,150 + 1,008,282) = 9.04%

산출: data/db/bizclose.json
  {asof, src, note, t:[YYYY], rate:{구분:[%]}, close:{구분:[명]},
   active:{구분:[명]}, new:{구분:[명]}, close_latest:{연도, 구분:[명]}}

사용: bizclose.py            (연 1회 갱신이면 충분 — cron 은 매일 07:25)
cron: 25 7 * * *
"""
import json, socket, sys, time, urllib.request, urllib.parse
from datetime import datetime
from pathlib import Path

# (2026-08-16) urlopen(timeout=) 은 소켓이 조금씩이라도 데이터를 흘리면 안 끊긴다.
# 실측: 32개 코드×3측정을 빠르게 던지자 KOSIS 가 한 요청을 15분 넘게 붙잡고 놔주지 않았다.
# → 전역 기본 타임아웃을 걸어 확실히 끊고, 호출 간격도 넉넉히 준다.
socket.setdefaulttimeout(35)

BASE = Path(__file__).resolve().parent.parent
DB   = BASE / "data" / "db"
OUT  = DB / "bizclose.json"
API  = "https://kosis.kr/openapi/Param/statisticsParameterData.do"
ORG  = "133"

# ── TX_13301_A161 (가동·신규·폐업) ──
T_MAIN = "TX_13301_A161"
ITM    = "T01"
PERIOD = "13301A"          # 과세기간 합계
BIZ    = "15133SEJ08"      # 총사업자(법인+개인)
MEA    = {"active": "16133T2008_0245", "new": "16133B0", "close": "16133B1"}

# 시도·업태 코드 → 표시명. 업태는 소상공인이 몰린 순으로 앞에 둔다.
DIMS = [
    ("15133GBB00",   "전체"),
    # 업태 14종
    ("15133GBB0807", "소매업"),   ("15133GBB080G", "음식업"),   ("15133GBB080C", "서비스업"),
    ("15133GBB080H", "숙박업"),   ("15133GBB0810", "대리·중개·도급업"),
    ("15133GBB080I", "부동산임대업"), ("15133GBB0806", "도매업"), ("15133GBB0803", "제조업"),
    ("15133GBB0805", "건설업"),   ("15133GBB080N", "운수·창고·통신업"),
    ("15133GBB080F", "부동산매매업"), ("15133GBB080K", "농·임·어업"),
    ("15133GBB0802", "광업"),     ("15133GBB080L", "전기·가스·수도업"),
    # 시도 17
    ("15133GBB0201", "서울"), ("15133GBB0202", "인천"), ("15133GBB0203", "경기"),
    ("15133GBB0204", "강원"), ("15133GBB0205", "대전"), ("15133GBB0206", "충북"),
    ("15133GBB0207", "충남"), ("15133GBB0207A", "세종"), ("15133GBB0208", "광주"),
    ("15133GBB0209", "전북"), ("15133GBB020A", "전남"), ("15133GBB020B", "대구"),
    ("15133GBB020C", "경북"), ("15133GBB020D", "부산"), ("15133GBB020E", "울산"),
    ("15133GBB020F", "경남"), ("15133GBB020G", "제주"),
]
# 소상공인이 밀집한 업태 — '전체'와 대비해 보여주는 묶음. 어떤 업태를 넣었는지
# 화면에 그대로 적어 둔다(임의로 고른 값을 근거처럼 보이게 하지 않기 위해).
SOHO = ["소매업", "음식업", "서비스업", "숙박업", "대리·중개·도급업", "부동산임대업"]

# ── TX_13301_A169 (폐업자만 · 1년 더 최신) ──
T_LATE = "TX_13301_A169"
LATE_ITM, LATE_TAX, LATE_RSN = "T01", "15133SEJ00", "16133T2008_0245"
LATE_DIMS = [("B01", "전체"), ("B03", "서울"), ("B04", "인천"), ("B05", "경기"),
             ("B06", "강원"), ("B07", "대전"), ("B08", "충북"), ("B09", "충남"),
             ("B10", "세종"), ("B11", "광주"), ("B12", "전북"), ("B13", "전남"),
             ("B14", "대구"), ("B15", "경북"), ("B16", "부산"), ("B17", "울산"),
             ("B18", "경남"), ("B19", "제주")]

Y0, Y1 = "2005", str(datetime.now().year)


def _key():
    for p in [BASE / "keys" / "kosis.txt", Path("D:/claudeCowork/SECURITY/kosis.kr.txt")] + \
             sorted(Path("/sessions").glob("*/mnt/claudeCowork/SECURITY/kosis.kr.txt")):
        try:
            k = Path(p).read_text(encoding="utf-8").strip()
            if k:
                return k
        except Exception:
            pass
    raise SystemExit("KOSIS 키 없음 — keys/kosis.txt")


KEY = _key()


def get(**q):
    q.update({"method": "getList", "apiKey": KEY, "format": "json", "jsonVD": "Y",
              "prdSe": "Y", "startPrdDe": Y0, "endPrdDe": Y1, "orgId": ORG})
    url = API + "?" + urllib.parse.urlencode(q)
    for k in range(3):
        try:
            d = json.loads(urllib.request.urlopen(url, timeout=30).read())
            if isinstance(d, dict):
                return []                      # err 30 = 해당 조합 없음 — 정상 흐름
            return d
        except Exception as e:
            if k == 2:
                print(f"    ⚠ 실패: {e}")
                return []
            time.sleep(3 * (k + 1))
    return []


def num(v):
    s = str(v if v is not None else "").replace(",", "").strip()
    if s in ("", "-", "X", "x", "None", "null"):
        return None
    try:
        return int(round(float(s)))
    except Exception:
        return None


def main():
    print(f"bizclose: {Y0}~{Y1}")
    data = {m: {} for m in MEA}                       # {measure: {name: {year: v}}}
    for code, name in DIMS:
        got = []
        for m, mc in MEA.items():
            rows = get(tblId=T_MAIN, itmId=ITM, objL1=code, objL2=PERIOD, objL3=BIZ, objL4=mc)
            d = {r["PRD_DE"]: num(r.get("DT")) for r in rows if r.get("PRD_DE")}
            data[m][name] = d
            got.append(len(d))
            time.sleep(0.6)
        print(f"    {name:<14} 가동 {got[0]:>2} · 신규 {got[1]:>2} · 폐업 {got[2]:>2}개년")

    years = sorted({y for m in data for n in data[m] for y in data[m][n]})
    if not years:
        raise SystemExit("✗ 수집 0건")

    def arr(m, n):
        return [data[m].get(n, {}).get(y) for y in years]

    rate = {}
    for _, n in DIMS:
        out = []
        for y in years:
            a, c = data["active"].get(n, {}).get(y), data["close"].get(n, {}).get(y)
            out.append(round(100 * c / (a + c), 2) if (a and c) else None)
        rate[n] = out

    # 소상공인 밀집 업태 묶음 — 업태별 합을 다시 폐업률로 환산(가중평균과 동일)
    for lbl, keys in [("소상공인 밀집업종", SOHO)]:
        ra = []
        for y in years:
            A = [data["active"].get(k, {}).get(y) for k in keys]
            C = [data["close"].get(k, {}).get(y) for k in keys]
            if all(v is not None for v in A + C) and (sum(A) + sum(C)):
                ra.append(round(100 * sum(C) / (sum(A) + sum(C)), 2))
            else:
                ra.append(None)
        rate[lbl] = ra
        data["close"][lbl] = {y: sum(v for v in [data["close"].get(k, {}).get(y) for k in keys]
                                     if v is not None) or None for y in years}
        data["active"][lbl] = {y: sum(v for v in [data["active"].get(k, {}).get(y) for k in keys]
                                      if v is not None) or None for y in years}

    print("  [2/2] 폐업자 최신연도 보강 (TX_13301_A169)")
    late, late_y = {}, None
    for code, name in LATE_DIMS:
        rows = get(tblId=T_LATE, itmId=LATE_ITM, objL1=LATE_TAX, objL2=code, objL3=LATE_RSN)
        d = {r["PRD_DE"]: num(r.get("DT")) for r in rows if r.get("PRD_DE")}
        if d:
            y = max(d)
            if late_y is None or y > late_y:
                late_y = y
            late[name] = d.get(y)
        time.sleep(0.6)

    names = [n for _, n in DIMS] + ["소상공인 밀집업종"]
    out = {
        "asof": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "src": "KOSIS · 국세청 국세통계 9.8.2 사업자 현황Ⅱ(지역,업태) · 9.8.13 폐업자 현황Ⅳ",
        "note": "폐업률 = 폐업 ÷ (가동 + 폐업). 연간 통계이며 국세청 확정 공표 기준.",
        "soho": SOHO,
        "t": years,
        "rate":   {n: rate.get(n) for n in names},
        "close":  {n: [data["close"].get(n, {}).get(y) for y in years] for n in names},
        "active": {n: [data["active"].get(n, {}).get(y) for y in years] for n in names},
        "new":    {n: [data["new"].get(n, {}).get(y) for y in years] for n in names},
        "close_latest": {"year": late_y, "v": late},
    }
    DB.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    i = -1
    print(f"  → {OUT} ({OUT.stat().st_size // 1024}KB) · {years[0]}~{years[-1]}")
    print(f"    {years[i]} 폐업률 — 전체 {out['rate']['전체'][i]}% · "
          f"소상공인 밀집업종 {out['rate']['소상공인 밀집업종'][i]}%")
    if late_y:
        print(f"    폐업자 최신 {late_y}년 전체 {late.get('전체'):,}명 (가동사업자 미공표로 폐업률은 {years[-1]}년까지)")


if __name__ == "__main__":
    main()
