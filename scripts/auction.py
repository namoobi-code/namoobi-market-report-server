#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""auction.py — 부동산 경매 물량 (대법원 등기정보광장 Open API · 월별)

왜 등기정보광장인가
  법원경매정보(courtauction.go.kr)는 사건 단위 조회만 되고 통계 API 가 없다.
  지지옥션 같은 민간 데이터는 유료다. 반면 등기정보광장은 **경매개시결정등기**와
  **경매로 인한 소유권이전(=낙찰 후 소유권 이전)** 신청 건수를 월별·시도별로 공개한다.
  경매개시결정등기는 경매가 '시작'된 물건 수라 경매 물량의 유입을 가장 앞에서 보여준다.

수집 데이터셋 (실측 확인 2026-08-16)
  0000000083  임의경매개시결정등기 신청 부동산 현황   → open_v  (담보권 실행 · 대출 연체가 원인)
  0000000087  강제경매개시결정등기 신청 부동산 현황   → open_f  (판결 등 집행권원)
  0000000050  소유권이전등기(임의경매로 인한 매각)    → sold_v  (낙찰돼 실제 넘어간 건수)
  0000000045  소유권이전등기(강제경매로 인한 매각)    → sold_f

API 제약 (실측)
  · key 파라미터 이름은 `key` (authKey·serviceKey 아님 — HTML 로그인 페이지가 돌아온다)
  · 한 번에 12개월까지. 그 이상은 APIERROR-0011
  · **최근 3년치만** 제공 — 그 이전은 아예 못 받는다
  · 하루 1,000회 · 3개월 미사용 시 인증키 자동 삭제

산출: data/db/auction.json
  {asof, src, note, t:[YYYYMM], open_v/open_f/sold_v/sold_f: {지역:[건수]}, open_all:{지역:[건수]}}

사용: auction.py            최근 3년 전체 재수집(호출 16회 남짓이라 매번 다 받아도 된다)
cron: 35 7 * * *
"""
import json, socket, sys, time, urllib.request, urllib.parse
from datetime import datetime
from pathlib import Path

socket.setdefaulttimeout(45)

BASE = Path(__file__).resolve().parent.parent
DB   = BASE / "data" / "db"
OUT  = DB / "auction.json"
API  = "https://data.iros.go.kr/openapi/cr/rs/selectCrRsRgsCsOpenApi.rest"

SETS = [("open_v", "0000000083", "임의경매 개시"),
        ("open_f", "0000000087", "강제경매 개시"),
        ("sold_v", "0000000050", "임의경매 매각"),
        ("sold_f", "0000000045", "강제경매 매각")]

# 등기정보광장 지역명 → 대시보드 표기. 행정구역 개편으로 이름이 바뀌어도
# 여기만 고치면 되도록 한곳에 모은다(실측 2026-08: '전남광주통합특별시' 등장).
REG = {"서울특별시": "서울", "부산광역시": "부산", "대구광역시": "대구", "인천광역시": "인천",
       "광주광역시": "광주", "전남광주통합특별시": "광주·전남", "대전광역시": "대전",
       "울산광역시": "울산", "세종특별자치시": "세종", "경기도": "경기",
       "강원특별자치도": "강원", "강원도": "강원", "충청북도": "충북", "충청남도": "충남",
       "전북특별자치도": "전북", "전라북도": "전북", "전라남도": "전남",
       "경상북도": "경북", "경상남도": "경남", "제주특별자치도": "제주"}


def _key():
    for p in [BASE / "keys" / "iros.txt", Path("D:/claudeCowork/SECURITY/data.iros.go.kr.txt")] + \
             sorted(Path("/sessions").glob("*/mnt/claudeCowork/SECURITY/data.iros.go.kr.txt")):
        try:
            k = Path(p).read_text(encoding="utf-8").strip()
            if k:
                return k
        except Exception:
            pass
    raise SystemExit("등기정보광장 인증키 없음 — keys/iros.txt")


KEY = _key()
NOW = datetime.now()


def windows():
    """최근 3년을 연 단위(최대 12개월)로 끊는다 — API 가 12개월 초과를 거부한다."""
    out, y = [], NOW.year - 2
    while y <= NOW.year:
        s, e = f"{y}01", (f"{y}{NOW.month:02d}" if y == NOW.year else f"{y}12")
        out.append((s, e))
        y += 1
    return out


def fetch(did, s, e, tries=3):
    q = {"key": KEY, "id": did, "reqtype": "json", "search_type_api": "02",
         "search_start_date_api": s, "search_end_date_api": e}
    url = API + "?" + urllib.parse.urlencode(q)
    for k in range(tries):
        try:
            raw = urllib.request.urlopen(url, timeout=40).read()
            d = json.loads(raw)
            head = (d.get("result") or {}).get("head") or {}
            if head.get("returnCode") != "APIINFO-0001":
                # 최근 3년 밖이면 APIERROR-0013 — 조용히 건너뛴다(정상 흐름)
                print(f"    · {s}~{e} {head.get('returnMessage','응답 이상')}")
                return []
            it = ((d.get("result") or {}).get("items") or {}).get("item") or []
            return it if isinstance(it, list) else [it]
        except Exception as ex:
            if k == tries - 1:
                print(f"    ⚠ {did} {s}~{e} 실패: {ex}")
                return []
            time.sleep(3 * (k + 1))
    return []


def main():
    acc = {k: {} for k, _, _ in SETS}          # {key: {(지역, ym): 건수}}
    for key, did, label in SETS:
        n = 0
        for s, e in windows():
            for r in fetch(did, s, e):
                ym = str(r.get("resDate") or "").replace("-", "")
                reg = REG.get(str(r.get("adminRegn1Name") or "").strip())
                try:
                    v = int(str(r.get("tot") or "0").replace(",", ""))
                except Exception:
                    continue
                if len(ym) != 6 or not reg:
                    continue
                acc[key][(reg, ym)] = acc[key].get((reg, ym), 0) + v
                acc[key][("전국", ym)] = acc[key].get(("전국", ym), 0) + v
                n += 1
            time.sleep(1.0)                    # 하루 1,000회 한도 — 여유 있게
        print(f"  {label:<12} {n:>5}행")

    ts = sorted({ym for k in acc for (_, ym) in acc[k]})
    regs = sorted({r for k in acc for (r, _) in acc[k]}, key=lambda x: (x != "전국", x))
    if not ts:
        raise SystemExit("✗ 수집 0건 — 인증키·API 제한 확인")

    out = {
        "asof": NOW.strftime("%Y-%m-%d %H:%M"),
        "src": "대법원 등기정보광장 Open API · 경매개시결정등기/경매로 인한 소유권이전 신청 건수",
        "note": ("개시 = 경매가 시작된 물건 수(물량 유입) · 매각 = 낙찰돼 소유권이 넘어간 건수. "
                 "임의경매는 담보권 실행(대출 연체가 원인)이라 부동산 스트레스를 더 직접적으로 보여준다. "
                 "API 가 최근 3년치만 제공한다."),
        "t": ts,
        "labels": {k: l for k, _, l in SETS},
    }
    for key, _, _ in SETS:
        out[key] = {r: [acc[key].get((r, t)) for t in ts] for r in regs}
    # 개시 합계(임의+강제) — '경매 물량' 한 줄로 볼 때 쓰는 계열
    out["open_all"] = {r: [(None if (acc["open_v"].get((r, t)) is None and acc["open_f"].get((r, t)) is None)
                            else (acc["open_v"].get((r, t)) or 0) + (acc["open_f"].get((r, t)) or 0))
                           for t in ts] for r in regs}
    out["labels"]["open_all"] = "경매 개시(임의+강제)"

    DB.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    a = out["open_all"]["전국"]
    tail = [(ts[i], a[i]) for i in range(len(ts)) if a[i] is not None][-4:]
    print(f"  → {OUT} ({OUT.stat().st_size // 1024}KB) · {ts[0]}~{ts[-1]} · 지역 {len(regs)}")
    for t, v in tail:
        print(f"    {t} 경매 개시 {v:,}건")


if __name__ == "__main__":
    main()
