#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""htrade.py — 주택 매매거래량 (KOSIS · 국토교통부/한국부동산원, 월별 2006.01~)

왜 KOSIS 인가
  서버가 매일 받는 RTMS 실거래(apt.sqlite)는 시군구를 하나씩 훑어 모으는 구조라
  아직 전국 250여 시군구 중 일부만 채워져 있다. 그걸 합치면 '전국'이 실제의
  1/3로 나온다. 전국 총량은 국토부 공식 집계(KOSIS)를 그대로 쓰는 게 맞다.
  (단지 단위 분석은 계속 RTMS 를 쓴다 — 둘은 용도가 다르다.)

수집 통계 (실측 확인 2026-08-10)
  408 / DT_408_2006_S0057  행정구역별 주택매매거래현황   → all  (주택 전체)
  408 / DT_408_2006_S0061  주택유형별 주택매매거래현황   → apt  (아파트만)
  둘 다 월간 · 2006.01 ~ · 단위 '동(호)수' = 거래 건수

산출: data/db/htrade.json
  {asof, src, t:[YYYYMM], all:{지역:[건수|null]}, apt:{지역:[건수|null]}}

사용: htrade.py            최근 36개월만 갱신(매일 cron)
      htrade.py --full     2006.01 부터 전체 재수집

주의: 국토부 공표는 통상 1개월 지연이고 최근 1~2개월은 잠정치다.
"""
import json, sys, time, urllib.request, urllib.parse
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DB   = BASE / "data" / "db"
OUT  = DB / "htrade.json"
FULL = "--full" in sys.argv

API  = "https://kosis.kr/openapi/Param/statisticsParameterData.do"
ORG  = "408"
T_ALL, T_APT = "DT_408_2006_S0057", "DT_408_2006_S0061"
ITM_ALL, ITM_APT = "13103114441T1", "13103114445T1"     # 동(호)수
PRE_ALL, PRE_APT = "13102114441A", "13102114445A"       # 행정구역별 코드 접두
APT_TYPE = "13102114445B.00010005"                      # 유형별 = 아파트

# 코드 끝 4자리 → 표시명. 두 통계표가 같은 순서를 쓴다(실측 확인).
SIDO = [("0001", "전국"), ("0002", "서울"), ("0003", "부산"), ("0004", "대구"),
        ("0005", "인천"), ("0006", "광주"), ("0007", "대전"), ("0008", "울산"),
        ("0009", "세종"), ("0010", "경기"), ("0011", "강원"), ("0012", "충북"),
        ("0013", "충남"), ("0014", "전북"), ("0015", "전남"), ("0016", "경북"),
        ("0017", "경남"), ("0018", "제주"), ("0019", "제주")]   # (구)제주 + 제주특자도 → 제주


def _key():
    """KOSIS 인증키 — 서버는 keys/, PC 는 SECURITY 폴더."""
    cands = [BASE / "keys" / "kosis.txt",
             Path("D:/claudeCowork/SECURITY/kosis.kr.txt")]
    cands += sorted(Path("/sessions").glob("*/mnt/claudeCowork/SECURITY/kosis.kr.txt"))
    for p in cands:
        try:
            k = Path(p).read_text(encoding="utf-8").strip()
            if k:
                return k
        except Exception:
            pass
    raise SystemExit("KOSIS 키 없음 — keys/kosis.txt 를 만들어 주세요")


KEY = _key()
NOW = datetime.now()
END = NOW.strftime("%Y%m")
START = "200601" if FULL else f"{NOW.year - 3}{NOW.month:02d}"


def fetch(tbl, itm, obj1, obj2=None, tries=3):
    q = {"method": "getList", "apiKey": KEY, "itmId": itm, "objL1": obj1,
         "format": "json", "jsonVD": "Y", "prdSe": "M",
         "startPrdDe": START, "endPrdDe": END, "orgId": ORG, "tblId": tbl}
    if obj2:
        q["objL2"] = obj2
    url = API + "?" + urllib.parse.urlencode(q)
    for k in range(tries):
        try:
            raw = urllib.request.urlopen(url, timeout=90).read()
            d = json.loads(raw)
            if isinstance(d, dict):                      # {"err":..,"errMsg":..}
                raise RuntimeError(d.get("errMsg") or str(d))
            return d
        except Exception as e:
            if k == tries - 1:
                print(f"    ⚠ {tbl} {obj1} 실패: {e}")
                return []
            time.sleep(2 * (k + 1))
    return []


def num(v):
    s = str(v if v is not None else "").replace(",", "").strip()
    if s in ("", "-", "X", "x", "null", "None"):
        return None
    try:
        return int(round(float(s)))
    except Exception:
        return None


def collect(tbl, itm, pre, obj2=None):
    """{지역: {ym: 건수}} — (구)제주처럼 코드가 갈린 지역은 합치지 않고 덮어쓴다.
    (구)제주는 2006.06 까지, 제주특별자치도는 2006.07 부터라 기간이 겹치지 않는다.)"""
    acc = {}
    for code, name in SIDO:
        rows = fetch(tbl, itm, f"{pre}.{code}", obj2)
        got = 0
        for r in rows:
            ym = str(r.get("PRD_DE") or "")
            v = num(r.get("DT"))
            if len(ym) != 6 or v is None:
                continue
            cur = acc.setdefault(name, {})
            # 같은 이름(제주)에 두 코드가 들어오면 값이 있는 쪽을 남긴다
            if cur.get(ym) is None:
                cur[ym] = v
            got += 1
        print(f"    {name:<4} {got:>4}행")
        time.sleep(0.4)                                  # KOSIS 배려
    return acc


def main():
    print(f"htrade: {START} ~ {END} ({'전체 재수집' if FULL else '최근 3년 갱신'})")
    print("  [1/2] 행정구역별 주택매매거래현황 (주택 전체)")
    a_all = collect(T_ALL, ITM_ALL, PRE_ALL)
    print("  [2/2] 주택유형별 주택매매거래현황 (아파트)")
    a_apt = collect(T_APT, ITM_APT, PRE_APT, APT_TYPE)
    if not a_all:
        raise SystemExit("✗ 수집 0건 — 키 또는 통계표 ID 확인")

    old = {}
    if OUT.exists() and not FULL:
        try:
            old = json.loads(OUT.read_text(encoding="utf-8"))
        except Exception:
            old = {}

    def merge(key, new):
        """기존 시계열 위에 새로 받은 달만 덮어쓴다(부분 갱신 모드용)."""
        ot, ob = old.get("t") or [], old.get(key) or {}
        base = {}
        for reg, arr in ob.items():
            base[reg] = {ot[i]: arr[i] for i in range(min(len(ot), len(arr))) if arr[i] is not None}
        for reg, mp in new.items():
            base.setdefault(reg, {}).update(mp)
        return base

    m_all, m_apt = merge("all", a_all), merge("apt", a_apt)
    ts = sorted({ym for mp in m_all.values() for ym in mp} |
                {ym for mp in m_apt.values() for ym in mp})
    out = {
        "asof": NOW.strftime("%Y-%m-%d %H:%M"),
        "src": "KOSIS · 국토교통부/한국부동산원 주택매매거래현황 (월별, 단위 건)",
        "note": "국토부 공표는 통상 1개월 지연 · 최근 1~2개월은 잠정치",
        "t": ts,
        "all": {r: [mp.get(ym) for ym in ts] for r, mp in sorted(m_all.items())},
        "apt": {r: [mp.get(ym) for ym in ts] for r, mp in sorted(m_apt.items())},
    }
    DB.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    n = out["all"].get("전국") or []
    lastv = next((v for v in reversed(n) if v is not None), None)
    print(f"  → {OUT} ({OUT.stat().st_size // 1024}KB) · {ts[0]}~{ts[-1]} "
          f"· 지역 {len(out['all'])} · 전국 최신 {lastv:,}건" if lastv else "")


if __name__ == "__main__":
    main()
