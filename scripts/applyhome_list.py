#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""applyhome_list.py — 청약(분양) 공고 리스트 + 추첨제 추정 (2026-08-16 신설 · 매일 07:58 cron).

applyhome.py(시계열 경쟁률 차트용)와 별도로, **공고 단위 리스트**를 만든다.
용도: 홈피 '청약' 탭(namoobi 로그인 시 노출) — 신혼특공 추첨제·일반공급 추첨제
세대수를 공고·주택형별로 추정해 보여주고, 경쟁률·당첨가점·원본링크를 붙인다.

소스: data.go.kr 한국부동산원 청약홈 (odcloud) — 2026-08-16 실측 확인
  ApplyhomeInfoDetailSvc/v1/getAPTLttotPblancDetail   공고 마스터(일정·규제플래그·URL)
  ApplyhomeInfoDetailSvc/v1/getAPTLttotPblancMdl      주택형별 공급세대(일반/특공 유형별)·분양최고가
  ApplyhomeInfoCmpetRtSvc/v1/getAPTLttotPblancCmpet   주택형·순위·거주지역별 접수건수
  ApplyhomeInfoCmpetRtSvc/v1/getAPTSpsplyReqstStus    특별공급 유형별 신청건수 (신혼·신생아·생초…)
  ApplyhomeInfoCmpetRtSvc/v1/getAptLttotPblancScore   주택형별 당첨가점(최저/평균/최고)
  ※ cond[HOUSE_MANAGE_NO::GTE] 서버측 필터 동작 실측 확인(전량 페이징 불필요)

추첨제 추정 규칙 (2023.4 청약제도 개편 이후 현행 — 규제지역 여부는 공고의
SPECLT_RDN_EARTH_AT(투기과열)·MDAT_TRGET_AREA_SECD(조정대상) 플래그로 공고별 자동 반영):
  · 민영 일반공급 추첨 비율
      투기과열지구: 전용 ≤60㎡ 60% · 60~85㎡ 30% · >85㎡ 20%
      조정대상지역: ≤60㎡ 60% · 60~85㎡ 30% · >85㎡ 50%
      비규제:       ≤85㎡ 60%(지자체 재량으로 가점 0~40%) · >85㎡ 100%
  · 국민(공공) 일반공급: 80% 순차제 + 20% 추첨
  · 신혼부부 특별공급: 배정물량의 30% 추첨(소득 상관없이 자산요건만) — 민영·공공 공통
  ⚠ 어디까지나 **규칙 기반 추정**이다. 확정 배정은 입주자모집공고 원문(PBLANC_URL) 확인.

산출: data/db/applyhome_sub.json {asof, note, sido, items[공고]}
"""
import json, re, time, urllib.request
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "data" / "db" / "applyhome_sub.json"
API = "https://api.odcloud.kr/api"
PER = 1000
BACK_DAYS = 600                       # 공고일 기준 ~20개월 (과거분은 경쟁률 참고용)


def _key():
    for p in (BASE / "keys" / "data.go.kr.txt",
              BASE.parent / "SECURITY" / "data.go.kr.txt"):
        if p.exists():
            return p.read_text().strip()
    raise SystemExit("data.go.kr 키 없음")


KEY = _key()
SINCE_DE = (date.today() - timedelta(days=BACK_DAYS)).isoformat()
SINCE_NO = SINCE_DE[:4] + "000000"    # HOUSE_MANAGE_NO 는 연도 프리픽스


def fetch_all(path, label, cond=""):
    rows, page = [], 1
    while True:
        u = f"{API}/{path}?page={page}&perPage={PER}&serviceKey={KEY}{cond}"
        for k in range(4):
            try:
                d = json.loads(urllib.request.urlopen(u, timeout=60).read())
                break
            except Exception as e:
                if k == 3:
                    print(f"  ⚠ {label} p{page} 실패: {e}")
                    return rows
                time.sleep(4 * (k + 1))
        cur = d.get("data") or []
        rows += cur
        tot = d.get("matchCount") or d.get("totalCount") or 0
        print(f"    {label} {len(rows):,}/{tot:,}", flush=True)
        if not cur or len(rows) >= tot:
            break
        page += 1
        time.sleep(0.4)
    return rows


def num(x):
    try:
        return float(str(x).replace(",", "").strip())
    except Exception:
        return None


def ival(x):
    v = num(x)
    return int(v) if v else 0


def ty_area(house_ty):
    """HOUSE_TY '084.5605B' → 전용 84.56"""
    m = re.match(r"(\d+\.?\d*)", str(house_ty or "").strip())
    return round(float(m.group(1)), 2) if m else None


def gen_lot_pct(minyoung, spec, mdat, ar):
    """일반공급 추첨 비율(%) — 규칙은 파일 상단 docstring 참고"""
    if not minyoung:
        return 20
    if ar is None:
        ar = 84.9
    if spec == "Y":
        return 60 if ar <= 60 else (30 if ar <= 85 else 20)
    if mdat == "Y":
        return 60 if ar <= 60 else (30 if ar <= 85 else 50)
    return 60 if ar <= 85 else 100


def main():
    c_no = f"&cond%5BHOUSE_MANAGE_NO%3A%3AGTE%5D={SINCE_NO}"
    c_de = f"&cond%5BRCRIT_PBLANC_DE%3A%3AGTE%5D={SINCE_DE}"
    print(f"[sub] 수집 시작 — 공고일 {SINCE_DE} 이후")
    pb = fetch_all("ApplyhomeInfoDetailSvc/v1/getAPTLttotPblancDetail", "공고", c_de)
    md = fetch_all("ApplyhomeInfoDetailSvc/v1/getAPTLttotPblancMdl", "주택형", c_no)
    cp = fetch_all("ApplyhomeInfoCmpetRtSvc/v1/getAPTLttotPblancCmpet", "경쟁률", c_no)
    sp = fetch_all("ApplyhomeInfoCmpetRtSvc/v1/getAPTSpsplyReqstStus", "특공신청", c_no)
    sc = fetch_all("ApplyhomeInfoCmpetRtSvc/v1/getAptLttotPblancScore", "당첨가점", c_no)
    if not pb or not md:
        print("[sub] ❌ 수집 실패 — 저장 생략")
        return

    # ── 주택형별 보조 테이블 (키: 공고번호 + 주택형) ──
    K = lambda r: (str(r.get("HOUSE_MANAGE_NO") or "").strip(),
                   str(r.get("HOUSE_TY") or "").strip())
    cmpet = defaultdict(lambda: {"r1": 0, "tot": 0, "short": False})
    for r in cp:
        x = cmpet[K(r)]
        q = ival(r.get("REQ_CNT"))
        x["tot"] += q
        if str(r.get("SUBSCRPT_RANK_CODE") or "") == "1":
            x["r1"] += q
            if "△" in str(r.get("CMPET_RATE") or ""):
                x["short"] = True                 # 1순위 미달 표기 (△n = 부족분)
    spq = defaultdict(lambda: defaultdict(int))
    for r in sp:
        x = spq[K(r)]
        for pre in ("CRSPAREA", "CTPRVN", "ETC_AREA"):
            x["nw"] += ival(r.get(f"{pre}_NWWDS_NMTW_CNT"))
            x["nb"] += ival(r.get(f"{pre}_NWBB_NWBBSHR_CNT"))
            x["lf"] += ival(r.get(f"{pre}_LFE_FRST_CNT"))
            x["my"] += ival(r.get(f"{pre}_MNYCH_CNT"))       # 다자녀
            x["yg"] += ival(r.get(f"{pre}_YGMN_CNT"))        # 청년
            x["op"] += ival(r.get(f"{pre}_OPS_CNT"))         # 노부모부양
    score = {}
    for r in sc:
        if str(r.get("RESIDE_SECD") or "") != "01":      # 해당지역 1순위 기준
            continue
        v = [num(r.get("LWET_SCORE")), num(r.get("AVRG_SCORE")), num(r.get("TOP_SCORE"))]
        if any(v) and v[2]:
            score[K(r)] = [round(x or 0, 1) for x in v]

    mdl = defaultdict(list)
    for r in md:
        mdl[str(r.get("HOUSE_MANAGE_NO") or "").strip()].append(r)

    # ── 공고 단위 조립 ──
    items, sido = [], set()
    for r in pb:
        no = str(r.get("HOUSE_MANAGE_NO") or "").strip()
        if not no or no not in mdl:
            continue
        miny = (r.get("HOUSE_DTL_SECD_NM") or "") == "민영"
        spec, mdat = r.get("SPECLT_RDN_EARTH_AT") or "N", r.get("MDAT_TRGET_AREA_SECD") or "N"
        tys, ag = [], defaultdict(int)
        prs = []
        for m in sorted(mdl[no], key=lambda x: str(x.get("HOUSE_TY") or "")):
            ht = str(m.get("HOUSE_TY") or "").strip()
            ar = ty_area(ht)
            gen, nw = ival(m.get("SUPLY_HSHLDCO")), ival(m.get("NWWDS_HSHLDCO"))
            pct = gen_lot_pct(miny, spec, mdat, ar)
            lot, nwlot = round(gen * pct / 100), round(nw * 0.3)
            pr = num(m.get("LTTOT_TOP_AMOUNT"))
            pr = round(pr / 10000, 2) if pr else None     # 만원 → 억
            if pr:
                prs.append(pr)
            t = {"t": ht, "ar": ar, "pr": pr, "pct": pct,
                 "gen": gen, "spc": ival(m.get("SPSPLY_HSHLDCO")),
                 "nw": nw, "nb": ival(m.get("NWBB_HSHLDCO")),
                 "lf": ival(m.get("LFE_FRST_HSHLDCO")), "my": ival(m.get("MNYCH_HSHLDCO")),
                 "yg": ival(m.get("YGMN_HSHLDCO")),
                 "op": ival(m.get("OLD_PARNTS_SUPORT_HSHLDCO")),
                 "lot": lot, "nwlot": nwlot}
            k = (no, ht)
            c = cmpet.get(k)
            if c and c["tot"]:
                t["r1"] = round(c["r1"] / gen, 2) if gen else None
                t["rt"] = round(c["tot"] / gen, 2) if gen else None
                if c["short"]:
                    t["short"] = 1
            q = spq.get(k)
            if q:  # 특공 유형별 경쟁률 = 유형 신청건수 ÷ 유형 배정세대 (해당+기타지역 합)
                for f, rk in (("nw", "nwr"), ("nb", "nbr"), ("lf", "lfr"),
                              ("my", "myr"), ("yg", "ygr"), ("op", "opr")):
                    if t[f] and q[f]:
                        t[rk] = round(q[f] / t[f], 2)
            if k in score:
                t["sc"] = score[k]
            for f in ("gen", "spc", "nw", "nb", "lf", "my", "yg", "op", "lot", "nwlot"):
                ag[f] += t[f]
            tys.append({k2: v for k2, v in t.items() if v not in (None, 0, [])})
        reg = r.get("SUBSCRPT_AREA_CODE_NM") or ""
        sido.add(reg)
        it = {"no": no, "name": r.get("HOUSE_NM"), "reg": reg,
              "addr": r.get("HSSPLY_ADRES"), "url": r.get("PBLANC_URL"),
              "hmpg": r.get("HMPG_ADRES"), "typ": r.get("HOUSE_DTL_SECD_NM"),
              "rent": r.get("RENT_SECD_NM"),
              "spec": spec, "mdat": mdat,
              "cap": r.get("PARCPRC_ULS_AT") or "N",       # 분양가상한제
              "de": str(r.get("RCRIT_PBLANC_DE") or "")[:10],
              "sp_bg": str(r.get("SPSPLY_RCEPT_BGNDE") or "")[:10],
              "r1_bg": str(r.get("RCEPT_BGNDE") or "")[:10],
              "rc_ed": str(r.get("RCEPT_ENDDE") or "")[:10],
              "prz": str(r.get("PRZWNER_PRESNATN_DE") or "")[:10],
              "mvn": r.get("MVN_PREARNGE_YM"),
              "biz": r.get("BSNS_MBY_NM"), "cons": r.get("CNSTRCT_ENTRPS_NM"),
              "sup": ival(r.get("TOT_SUPLY_HSHLDCO")),
              "pr": [min(prs), max(prs)] if prs else None,
              "agg": dict(ag), "ty": tys}
        items.append({k: v for k, v in it.items() if v not in (None, "", [])})

    items.sort(key=lambda x: x.get("r1_bg") or x.get("de") or "", reverse=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "asof": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "src": "한국부동산원 청약홈 (data.go.kr) · 매일 07:58 갱신",
        "note": ("추첨제 세대수는 규칙 기반 추정(민영 일반: 규제지역·전용면적별 20~100%, "
                 "국민 일반: 20%, 신혼특공: 30%). 확정 배정·자격요건은 모집공고 원문 확인."),
        "since": SINCE_DE,
        "sido": [s for s in ["서울", "경기", "인천", "부산", "대구", "광주", "대전", "울산",
                             "세종", "강원", "충북", "충남", "전북", "전남", "경북", "경남",
                             "제주"] if s in sido],
        "items": items}, ensure_ascii=False), encoding="utf-8")
    up = sum(1 for i in items if (i.get("r1_bg") or "") >= date.today().isoformat())
    print(f"[sub] ✅ 공고 {len(items):,}건 (접수예정·접수중 {up}건) → {OUT} "
          f"({OUT.stat().st_size//1024}KB)")


if __name__ == "__main__":
    main()
