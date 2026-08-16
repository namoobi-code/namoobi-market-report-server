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

(2026-08-16 추가) 당첨 시 예상시세·차익 — apt.sqlite(rtms.py 매일 수집)의 같은 시군구
최근 6개월 실거래 ㎡당가(준공 15년 이내·유사면적 ±5㎡ 우선)로 주택형별 예상시세를 추정.
분양가는 '최고공급금액' 기준이라 차익은 보수적(실제는 이보다 클 수 있음). DB 미수집
지역(rtms REGIONS 밖)은 표시 안 함.

산출: data/db/applyhome_sub.json {asof, note, sido, items[공고]}
"""
import json, re, sqlite3, time, urllib.request
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "data" / "db" / "applyhome_sub.json"
APT_DB = BASE / "data" / "db" / "apt.sqlite"
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


def parse_lvl2(addr):
    """공급위치 주소 → 2단계 행정구역. 광역시·서울은 구/군('노원구'),
    도는 시·군('진주시','가평군' — 특례시 일반구는 시 단위로 묶음)."""
    t = (addr or "").split()
    if len(t) < 2:
        return None
    g = t[1]
    return g if g.endswith(("시", "군", "구")) else None


def sane_pr(pr, ar):
    """(2026-08-16) 분양가 단위 오류 보정 — 청약홈 LTTOT_TOP_AMOUNT 가 일부 공고
    (신혼희망타운 잔여·추가모집 등)에서 만원이 아니라 천원 단위로 등록돼 10배로 나온다.
    실측: 의왕월암 A-3 55㎡ 46.19억(A-1 동일면적은 4.6억) · 성남복정1 A2 55.97㎡ 69.38억.
    평당가 2.0억(국내 최고 분양가 ~1.8억/평 상회) 초과면 10으로 나누고,
    그래도 비정상(>2.0억 또는 <100만/평)이면 표시하지 않는다."""
    if not pr or not ar:
        return pr
    py = lambda p: p * 10000 / (ar * 0.3025)      # 만원/평
    if py(pr) > 20000:
        pr = round(pr / 10, 2)
    if py(pr) > 20000 or py(pr) < 100:
        return None
    return pr


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


def load_ppsm():
    """(2026-08-16) 시군구별 ㎡당 실거래가 집계 — 당첨 시 예상시세 계산용.
    한 번의 GROUP BY 로 (시군구, 전용㎡, 신축여부)별 가중치를 만들어 두고
    공고·주택형 루프에서는 메모리 조회만 한다(공고 수천 건 × 쿼리 방지)."""
    if not APT_DB.exists():
        print("[sub] apt.sqlite 없음 — 예상시세 생략")
        return None, {}, {}, {}
    try:
        from rtms import REGIONS                  # 지역코드→이름 (단일 출처 유지)
    except Exception as e:
        print(f"[sub] rtms REGIONS 로드 실패({e}) — 예상시세 생략")
        return None, {}, {}, {}
    ym6 = (date.today().replace(day=1) - timedelta(days=183)).strftime("%Y%m")
    ym12 = (date.today().replace(day=1) - timedelta(days=366)).strftime("%Y%m")
    cut = date.today().year - 15                  # '신축급' = 준공 15년 이내
    cx = sqlite3.connect(APT_DB)
    rows = cx.execute(
        "SELECT a.sgg, s.ar, a.build_year>=?, SUM(s.avg/s.ar*s.n), SUM(s.n) "
        "FROM sale s JOIN apt a ON a.id=s.apt_id "
        "WHERE s.ym>=? AND s.ar>=20 AND s.avg>0 "
        "GROUP BY a.sgg, s.ar, a.build_year>=?", (cut, ym6, cut)).fetchall()
    db = defaultdict(list)
    for sgg, ar, nf, wp, n in rows:
        db[sgg].append((ar, nf, wp, n))
    # (2026-08-16) 단지 자체 실거래 — 입주 시작된 완료 공고의 '실측' 시세용
    apts = defaultdict(list)                      # sgg → [(apt_id, 정규화명, 준공년)]
    for i2, sgg, nm, by, umd in cx.execute(
            "SELECT id, sgg, name, build_year, umd FROM apt WHERE build_year>=?",
            (date.today().year - 10,)):
        apts[sgg].append((i2, re.sub(r"[^0-9A-Za-z가-힣]", "", str(nm or "").lower()),
                          by, str(umd or "")))
    asale = defaultdict(list)                     # apt_id → [(ar, ㎡당가가중, n)]
    for aid, ar, wp, n in cx.execute(
            "SELECT s.apt_id, s.ar, SUM(s.avg/s.ar*s.n), SUM(s.n) FROM sale s "
            "JOIN apt a ON a.id=s.apt_id WHERE s.ym>=? AND a.build_year>=? "
            "AND s.ar>=20 AND s.avg>0 GROUP BY s.apt_id, s.ar",
            (ym12, date.today().year - 10)):
        asale[aid].append((ar, wp, n))
    cx.close()
    print(f"[sub] 예상시세 기준: {ym6}~ 실거래 · {len(db)}개 시군구 · "
          f"신축단지 {sum(len(v) for v in apts.values())}곳(실측 매칭용)")
    return REGIONS, db, apts, asale


def act_price(apts, asale, codes, name, mvn, ar):
    """(2026-08-16) 입주 시작(mvn 경과)된 완료 공고 → 같은 시군구 신축 단지명 매칭으로
    그 단지 자체의 최근 12개월 실거래 ㎡당가 × 전용 = '실측' 시세. 매칭 규칙:
    정규화명 포함관계(4자 이상) + 준공년이 입주예정년 ±1. 표본 2건 이상일 때만."""
    if not codes or not ar or not mvn:
        return None
    ym_now = date.today().strftime("%Y%m")
    if str(mvn)[:6] > ym_now:
        return None                               # 아직 미입주
    nn = re.sub(r"[^0-9A-Za-z가-힣]", "", str(name or "").lower())
    yr = int(str(mvn)[:4])
    best = None
    for c in codes:
        for aid, anm, by, _umd in apts.get(c, ()):
            if len(anm) < 4 or not (anm in nn or nn in anm):
                continue
            if by and abs(by - yr) > 1:
                continue
            wp = n = 0
            for a2, w, k in asale.get(aid, ()):
                if abs(a2 - ar) <= 5:
                    wp += w
                    n += k
            if n >= 2 and (best is None or n > best[1]):
                best = (round(wp / n * ar, 2), n)
    return best[0] if best else None


def sgg_codes(regions, reg, sgg):
    """공고의 (시도, 시군구명) → rtms 지역코드 목록.
    REGIONS 이름 형식이 '서울 종로구'(광역) · '수원 장안구'(특례시 일반구) ·
    '부천시'(단일시) · '광주시(경기)'(동명 구분) 로 섞여 있어 순서대로 매칭."""
    if reg == "세종":
        return ["36110"]
    if not sgg:
        return []
    out = [c for c, nm in regions.items()
           if nm in (f"{reg} {sgg}", sgg, f"{sgg}({reg})")]
    if not out and sgg.endswith("시"):            # '수원시' → '수원 *' · '화성시' → '화성 *권'
        p = sgg[:-1] + " "
        out = [c for c, nm in regions.items() if nm.startswith(p)]
    return out


def est_price(db, codes, ar, apts=None, asale=None, dong=None):
    """유사 면적 ㎡당가 가중평균 × 전용 = 예상시세(억). 4단계 폴백:
    ⓪ (2026-08-16 v4) 같은 '법정동' 준공 10년 이내 신축 단지별 — 급지 반영(뉴타운 vs
       구도심 왜곡 축소). 2개 단지·5건 이상.
    ① 같은 시군구 준공 10년 이내 신축 단지별(±8㎡·3단지·8건 이상)
    ② 시군구 집계(준공 15년 이내) 5건 이상  ③ 전 연식 3건 이상(† 표기).
    반환 (시세, 전연식플래그, 비교단지수, 동단위플래그)"""
    if not codes or not ar:
        return None, 0, 0, 0
    if apts and asale:
        for use_dong in ((1, 0) if dong else (0,)):   # ⓪ 동 단위 → ① 구 단위
            wp = n = 0
            nb = set()
            for c in codes:
                for aid, _nm, _by, umd in apts.get(c, ()):
                    if use_dong and umd != dong:
                        continue
                    for a2, w, k in asale.get(aid, ()):
                        if abs(a2 - ar) <= 8:     # 신축은 59·84 위주라 밴드 ±8(52↔59 매칭)
                            wp += w
                            n += k
                            nb.add(aid)
            if use_dong and len(nb) >= 2 and n >= 5:
                return round(wp / n * ar, 2), 0, len(nb), 1
            if not use_dong and len(nb) >= 3 and n >= 8:
                return round(wp / n * ar, 2), 0, len(nb), 0
    for new_only in (1, 0):                       # ②③ 시군구 집계 폴백
        wp = n = 0
        for c in codes:
            for a2, nf, w, k in db.get(c, ()):
                if abs(a2 - ar) <= 5 and (nf == 1 or not new_only):
                    wp += w
                    n += k
        if new_only and n >= 5:
            return round(wp / n * ar, 2), 0, 0, 0
        if not new_only and n >= 3:
            return round(wp / n * ar, 2), 1, 0, 0
    return None, 0, 0, 0


def parse_dong(addr):
    """공급위치 주소 → 법정동('신길동'·'복정동'·'문래동3가'…) — apt.umd 와 대조용"""
    for t in (addr or "").split()[2:]:
        if re.search(r"(동|가|읍|면)\d*$", t) and not t.endswith("빌딩"):
            return t
    return None


def silv_price(silv, codes, name, ar):
    """(2026-08-16) 분양권 전매 실거래(silv_trade.py) — 미입주 단지의 '분양권 실측'.
    같은 시군구에서 정규화 단지명 포함관계(4자+) + 전용 ±3㎡ 매칭, 거래건수 가중평균(억)."""
    if not silv or not codes or not ar or not name:
        return None
    nn = re.sub(r"[^0-9A-Za-z가-힣]", "", str(name).lower())
    s = n = 0
    for c in codes:
        for anm, ar2, avg, k in silv.get(c, ()):
            if abs(ar2 - ar) <= 3 and len(anm) >= 4 and (anm in nn or nn in anm):
                s += avg * k
                n += k
    return round(s / n, 2) if n >= 2 else None


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
        # 기관추천·이전기관은 거주지역 구분이 없는 단일 필드다(청약홈 화면도 지역행이 비어 있다).
        # 이 둘을 빼면 유형별 배정 합이 특공계와 안 맞는다(실측: 쌍용 서대문 84A 25 vs 특공계 30 = 기관추천 5).
        x["ir"] += ival(r.get("INSTT_RECOMEND_DCSN_CNT"))    # 기관추천 확정
        x["tr"] += ival(r.get("TRANSR_INSTT_ENFSN_CNT"))     # 이전기관 종사자
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

    REG, PPSM, APTS, ASALE = load_ppsm()          # (2026-08-16) 예상시세용 실거래 ㎡당가
    # (2026-08-16) 공고문 PDF 층별 가격 캐시(applyhome_pdf.py) — 주택형별 최저·평균 분양가
    PDFP = {}
    pdf_f = BASE / "data" / "db" / "applyhome_pdf.json"
    if pdf_f.exists():
        PDFP = json.loads(pdf_f.read_text(encoding="utf-8"))
    from applyhome_pdf import short_ty
    # (2026-08-16) 분양권 전매 실거래(silv_trade.py 매일 07:40) — 미입주 단지 실측용
    SILV = {}
    silv_f = BASE / "data" / "db" / "silv.json"
    if silv_f.exists():
        SILV = json.loads(silv_f.read_text(encoding="utf-8")).get("data", {})

    # ── 공고 단위 조립 ──
    items, sido = [], set()
    for r in pb:
        no = str(r.get("HOUSE_MANAGE_NO") or "").strip()
        if not no or no not in mdl:
            continue
        miny = (r.get("HOUSE_DTL_SECD_NM") or "") == "민영"
        spec, mdat = r.get("SPECLT_RDN_EARTH_AT") or "N", r.get("MDAT_TRGET_AREA_SECD") or "N"
        reg = r.get("SUBSCRPT_AREA_CODE_NM") or ""
        sgg = parse_lvl2(r.get("HSSPLY_ADRES"))
        codes = sgg_codes(REG, reg, sgg) if REG else []
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
            pr = sane_pr(pr, ar)                          # 10배 단위오류 보정
            if pr:
                prs.append(pr)
            # ⚠ 비교단지수 키는 "cmp" — "nb"는 신생아 특공 세대수로 이미 사용 중(충돌 주의)
            # 시세 우선순위: 입주 후 매매 실측(act) > 분양권 전매 실측(slv) > 주변 신축 추정
            est, estb, cmpn, dg = (est_price(PPSM, codes, ar, APTS, ASALE,
                                             parse_dong(r.get("HSSPLY_ADRES")))
                                   if pr else (None, 0, 0, 0))
            act = (act_price(APTS, ASALE, codes, r.get("HOUSE_NM"),
                             r.get("MVN_PREARNGE_YM"), ar) if pr else None)
            slv = (silv_price(SILV, codes, r.get("HOUSE_NM"), ar)
                   if pr and not act else None)
            if act:
                est, estb, cmpn, dg = act, 0, 0, 0
            elif slv:
                est, estb, cmpn, dg = slv, 0, 0, 0
            pp = PDFP.get(no, {}).get(short_ty(ht)) if pr else None
            t = {"t": ht, "ar": ar, "pr": pr, "pct": pct,
                 "act": 1 if act else 0, "slv": 1 if slv else 0,
                 "cmp": cmpn, "dg": dg,
                 "prmn": (pp or {}).get("mn"), "prav": (pp or {}).get("av"),
                 "est": est, "estb": estb,
                 "gen": gen, "spc": ival(m.get("SPSPLY_HSHLDCO")),
                 "nw": nw, "nb": ival(m.get("NWBB_HSHLDCO")),
                 "lf": ival(m.get("LFE_FRST_HSHLDCO")), "my": ival(m.get("MNYCH_HSHLDCO")),
                 "yg": ival(m.get("YGMN_HSHLDCO")),
                 "op": ival(m.get("OLD_PARNTS_SUPORT_HSHLDCO")),
                 # (2026-08-16) 특공계 합계를 맞추는 나머지 3종 — 기관추천·이전기관·기타
                 "ir": ival(m.get("INSTT_RECOMEND_HSHLDCO")),
                 "tr": ival(m.get("TRANSR_INSTT_ENFSN_HSHLDCO")),
                 "ec": ival(m.get("ETC_HSHLDCO")),
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
                              ("my", "myr"), ("yg", "ygr"), ("op", "opr"),
                              ("ir", "irr"), ("tr", "trr")):
                    if t[f] and q[f]:
                        t[rk] = round(q[f] / t[f], 2)
            if k in score:
                t["sc"] = score[k]
            # 유형 합이 특공계(spc)와 어긋나면 '기타'로 흡수 — 화면 합계가 항상 맞게 한다
            _sum = sum(t[f] for f in ("nw", "nb", "lf", "my", "yg", "op", "ir", "tr", "ec"))
            if t["spc"] and t["spc"] != _sum:
                t["ec"] += t["spc"] - _sum
            for f in ("gen", "spc", "nw", "nb", "lf", "my", "yg", "op",
                      "ir", "tr", "ec", "lot", "nwlot"):
                ag[f] += t[f]
            tys.append({k2: v for k2, v in t.items() if v not in (None, 0, [])})
        sido.add(reg)
        # (2026-08-16) 공고 대표 예상차익 = 일반공급 세대수 가중평균 (est·pr 둘 다 있는 형만)
        # 기준 분양가: PDF 파싱 평균(prav)이 있으면 평균 — 동·호수는 추첨이라 기대값은 평균가.
        # 없으면 최고가(pr) — 보수적.
        gv = [(t["est"] - (t.get("prav") or t["pr"]), t.get("gen") or 1,
               t.get("prav") or t["pr"])
              for t in tys if t.get("est") and t.get("pr")]
        gain = gpct = None
        if gv:
            W = sum(x[1] for x in gv)
            gain = sum(x[0] * x[1] for x in gv) / W
            base = sum(x[2] * x[1] for x in gv) / W
            gain, gpct = round(gain, 1), (round(gain / base * 100) if base else None)
        it = {"no": no, "name": r.get("HOUSE_NM"), "reg": reg,
              "sgg": sgg, "gain": gain, "gpct": gpct,
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
