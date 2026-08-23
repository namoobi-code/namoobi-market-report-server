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
import http.cookiejar, json, socket, sys, time, urllib.request, urllib.parse
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


def _keys():
    """인증키는 **데이터셋별로** 따로 발급된다(실측 2026-08-16).
    키 파일은 한 줄에 하나씩 `설명 데이터셋ID : 키` 형태.
        임의경매개시결정등기 신청 부동산 현황 0000000083 : xxxxxxxx…
    ID 가 없는 한 줄짜리 옛 형식이면 그 키를 모든 데이터셋에 공통으로 쓴다."""
    for p in [BASE / "keys" / "iros.txt", Path("D:/claudeCowork/SECURITY/data.iros.go.kr.txt")] + \
             sorted(Path("/sessions").glob("*/mnt/claudeCowork/SECURITY/data.iros.go.kr.txt")):
        try:
            txt = Path(p).read_text(encoding="utf-8")
        except Exception:
            continue
        out, fallback = {}, None
        for line in txt.splitlines():
            line = line.strip()
            if not line:
                continue
            if ":" in line:
                head, k = line.rsplit(":", 1)
                k = k.strip()
                ids = [w for w in head.replace(":", " ").split() if w.isdigit() and len(w) == 10]
                if k and ids:
                    out[ids[-1]] = k
                    continue
            if len(line.split()) == 1 and len(line) >= 20:
                fallback = line
        if out:
            return out, fallback
        if fallback:
            return {}, fallback
    raise SystemExit("등기정보광장 인증키 없음 — keys/iros.txt")


KEYS, KEY_ANY = _keys()


def key_for(did):
    return KEYS.get(did) or KEY_ANY
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
    k = key_for(did)
    if not k:
        return []
    q = {"key": k, "id": did, "reqtype": "json", "search_type_api": "02",
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



# ══════════════════ 대법원 법원경매정보 — 매각통계(낙찰가율) ══════════════════
# 화면(PGJ164M01)이 쓰는 내부 엔드포인트다. 공식 Open API 가 아니라 인증키가 없고,
# 법원이 화면을 바꾸면 깨질 수 있다 → 실패해도 조용히 넘어가고 이전 값을 유지한다.
#
# 지역 필터는 못 쓴다(실측 2026-08-22): adongSdCd·cortOfcCd 에 서울중앙/서울동부/부산/대구
# 어느 값을 넣어도 전국과 동일한 숫자가 돌아온다. 서버가 세션에 담긴 조건을 보는 구조로 보인다.
# → **전국 기준**으로만 수집한다. 지역별 물량은 등기정보광장(위)이 담당한다.
CA_BASE = "https://www.courtauction.go.kr"
CA_STAT = CA_BASE + "/pgj/pgj164/selectRletCortDspslStats.on"
CA_UA = "Mozilla/5.0 (namoobi market terminal)"
# 화면이 돌려주는 용도 19종 중 대시보드에서 쓸 것만 고른다(소계·겸용은 중복이라 뺀다)
CA_USG = ["아파트", "연립주택,다세대", "오피스텔", "단독주택", "다가구주택", "전체"]


def num(v):
    """'1,234' · '' · '-' 같은 값을 숫자로. 못 바꾸면 None(빈칸으로 남긴다)."""
    t = str(v if v is not None else "").replace(",", "").strip()
    if t in ("", "-", "X", "x", "None", "null"):
        return None
    try:
        f = float(t)
        return int(f) if f == int(f) else round(f, 2)
    except Exception:
        return None


def _ca_opener():
    """세션 쿠키를 받아야 조회가 된다 — 메인 페이지를 한 번 열고 그 쿠키를 재사용."""
    cj = http.cookiejar.CookieJar()
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    op.addheaders = [("User-Agent", CA_UA),
                     ("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"),
                     ("Accept-Language", "ko-KR,ko;q=0.9,en;q=0.8"),
                     ("Connection", "keep-alive")]
    try:
        op.open(CA_BASE + "/pgj/index.on", timeout=30).read()
    except Exception as e:
        print(f"    ⚠ 법원경매 세션 실패: {e}")
        return None
    return op


def court_stats(months):
    """{용도: {ym: {...}}} — 월별 전국 매각통계."""
    op = _ca_opener()
    if not op:
        return {}
    acc, miss = {}, 0
    for ym in months:
        body = json.dumps({"dma_search": {"searchType": "1", "cortOfcCd": "", "adongSdCd": "",
                                          "adongSggCd": "", "startDate": ym, "endDate": ym}}).encode()
        req = urllib.request.Request(CA_STAT, data=body, method="POST", headers={
            "Content-Type": "application/json;charset=UTF-8", "User-Agent": CA_UA,
            "Referer": CA_BASE + "/pgj/index.on", "SC-Pgmid": "PGJ164M01", "SC-Userid": "NONUSER"})
        try:
            d = json.loads(op.open(req, timeout=30).read())
            rows = (d.get("data") or {}).get("rletCortDspslStats") or []
        except Exception:
            rows = []
        if not rows:
            miss += 1
        for r in rows:
            nm = str(r.get("lclDspslGdsLstUsgNm") or "").strip()
            if nm not in CA_USG:
                continue
            acc.setdefault(nm, {})[ym] = {
                "auctn": num(r.get("auctnNum")), "sold": num(r.get("dspslNum")),
                "rate": num(r.get("dspslAmtRate")), "sold_rate": num(r.get("dspslRate")),
                "appr": num(r.get("aeeEvlGrsAmt")), "amt": num(r.get("dspslGrsAmt"))}
        time.sleep(0.35)
    print(f"    용도 {len(acc)}종 · 빈 응답 {miss}/{len(months)}개월")
    return acc


def month_range(y0):
    out = []
    for y in range(y0, NOW.year + 1):
        for m in range(1, 13):
            if y == NOW.year and m > NOW.month:
                break
            out.append(f"{y}{m:02d}")
    return out


def main():
    print(f"인증키 {len(KEYS)}개 등록" + (" (+공통키)" if KEY_ANY else ""))
    acc = {k: {} for k, _, _ in SETS}          # {key: {(지역, ym): 건수}}
    for key, did, label in SETS:
        if not key_for(did):
            print(f"  {label:<12} 건너뜀 — {did} 인증키 없음")
            continue
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

    print("법원경매정보 매각통계(전국) 수집")
    Y0 = 2010 if "--full" in sys.argv else NOW.year - 4
    court = court_stats(month_range(Y0))

    ts = sorted({ym for k in acc for (_, ym) in acc[k]} |
                {ym for u in court.values() for ym in u})
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
    # ── 낙찰가율 등 법원 매각통계 — 전국만 있으므로 {'전국': [...]} 모양으로 맞춘다 ──
    USG_KEY = {"아파트": "apt", "연립주택,다세대": "rh", "오피스텔": "offi",
               "단독주택": "sh", "다가구주택": "mh", "전체": "all"}
    for nm, short in USG_KEY.items():
        mp = court.get(nm) or {}
        if not mp:
            continue
        for fld, suffix, lab in [("rate", "rate", "낙찰가율"), ("sold_rate", "sldrate", "매각률"),
                                 ("auctn", "auctn", "경매 진행건수"), ("sold", "sold", "매각건수")]:
            out[f"bid_{short}_{suffix}"] = {"전국": [(mp.get(t) or {}).get(fld) for t in ts]}
            out["labels"][f"bid_{short}_{suffix}"] = f"{nm} {lab}"
    out["court_src"] = "대법원 법원경매정보 매각통계 — 전국 기준(지역 필터 미지원)"

    # 개시 합계(임의+강제) — '경매 물량' 한 줄로 볼 때 쓰는 계열
    out["open_all"] = {r: [(None if (acc["open_v"].get((r, t)) is None and acc["open_f"].get((r, t)) is None)
                            else (acc["open_v"].get((r, t)) or 0) + (acc["open_f"].get((r, t)) or 0))
                           for t in ts] for r in regs}
    out["labels"]["open_all"] = "경매 개시(임의+강제)"

    # ── (2026-08-23) 기존 파일 병합 — 일일 실행이 백필을 덮어쓰는 사고 방지 ──
    #   등기 API 는 최근 3년, 법원 매각통계 일일 모드는 4년치만 받는다. 겹치는 달은
    #   새 값을 쓰고, 이번에 못 받은 과거 달은 기존 파일 값을 보존한다.
    #   실측 사고(2026-08-23): 크론이 --full 백필(2010~, 106KB)을 2022~ 30KB 로 덮어써
    #   낙찰가율 시차 탐색이 표본 부족(53개월·최소겹침 48)으로 0~5개월에 갇혔다
    #   → 시차 5M·r -0.39 오염(원래 2010~ 전체로는 r +0.613).
    old = {}
    if OUT.exists():
        try:
            old = json.loads(OUT.read_text(encoding="utf-8"))
        except Exception:
            old = {}
    oldt = old.get("t") or []
    if oldt and ts:
        mts = sorted(set(oldt) | set(ts))
        oidx = {t: i for i, t in enumerate(oldt)}
        nidx = {t: i for i, t in enumerate(ts)}
        is_series = lambda v: isinstance(v, dict) and any(isinstance(x, list) for x in v.values())
        for k in {k for k, v in old.items() if is_series(v)} | {k for k, v in out.items() if is_series(v)}:
            ov, nv = old.get(k) or {}, out.get(k) or {}
            merged = {}
            for r in set(ov) | set(nv):
                oa, na = ov.get(r) or [], nv.get(r) or []
                merged[r] = [na[nidx[t]] if (t in nidx and nidx[t] < len(na) and na[nidx[t]] is not None)
                             else (oa[oidx[t]] if (t in oidx and oidx[t] < len(oa)) else None)
                             for t in mts]
            out[k] = merged
        lb = dict(old.get("labels") or {})
        lb.update(out.get("labels") or {})
        out["labels"] = lb
        out["t"] = ts = mts

    DB.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    a = out["open_all"]["전국"]
    tail = [(ts[i], a[i]) for i in range(len(ts)) if a[i] is not None][-4:]
    print(f"  → {OUT} ({OUT.stat().st_size // 1024}KB) · {ts[0]}~{ts[-1]} · 지역 {len(regs)}")
    for t, v in tail:
        print(f"    {t} 경매 개시 {v:,}건")
    br = (out.get("bid_apt_rate") or {}).get("전국") or []
    bt = [(ts[i], br[i]) for i in range(min(len(ts), len(br))) if br[i] is not None][-4:]
    for t, v in bt:
        print(f"    {t} 아파트 낙찰가율 {v}%")


if __name__ == "__main__":
    main()
