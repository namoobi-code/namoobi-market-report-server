#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""applyhome_pdf.py — 모집공고문 PDF 층별 공급금액 파싱 (2026-08-16 신설 · 매일 08:10 cron).

왜: 청약홈 API 는 주택형별 '최고공급금액(최상층)' 하나만 준다 → 공고문 PDF 의
층별 가격표를 파싱해 주택형별 **최저·평균 분양가**를 보탠다.

방법 (실측: 쌍용 더 플래티넘 서대문 2026000372, 2026-08-16):
  1. 상세페이지(PBLANC_URL) HTML 에서 '모집공고문 보기' 링크(getAtchmnfl) 추출
  2. PDF 다운로드 → pdftotext -layout
  3. '층' 토큰 + 1억 이상 콤마 금액 2개 이상인 행 = 가격 행.
     행 내 최대 금액 = 분양가 '계' (대지비+건축비 합계 — 계약금·중도금·잔금은 그보다 작다)
     '층 N 금액' 패턴의 N = 해당 층 세대수(가중평균용, 없으면 1)
     타입 컨텍스트 = 행 머리의 약식표기(59A·84B·119 등), 단일 타입 공고는 전체 귀속
  4. 검증: 파싱 최고가가 API 최고공급금액 ±3% 이내일 때만 채택
     → 표 형식이 다른 건설사·스캔본 PDF 는 자동 탈락(오파싱 게시 방지)

캐시: data/db/applyhome_pdf.json {공고번호: {약식타입: {mn,av,mx}(억), _src}}
대상: 접수시작 오늘-120일 이후(예정 포함) 공고 중 캐시 미보유분 — 회당 최대 40건.
사용: applyhome_pdf.py [--all]  (--all 은 기간 제한 없이 캐시 미보유 전부)
"""
import json, re, subprocess, tempfile, time, urllib.request
from datetime import date, timedelta
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
SUB = BASE / "data" / "db" / "applyhome_sub.json"
OUT = BASE / "data" / "db" / "applyhome_pdf.json"
UA = {"User-Agent": "Mozilla/5.0"}
LIMIT = 40                                   # 회당 다운로드 상한 (PDF ~1MB)


def short_ty(house_ty):
    """'084.9458A' → '84A' (PDF 약식표기와 매칭)"""
    m = re.match(r"0*(\d+)(?:\.\d+)?([A-Z]*)", str(house_ty or "").strip())
    return (m.group(1) + m.group(2)) if m else None


def get(url, binary=False, tries=3):
    for k in range(tries):
        try:
            r = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60).read()
            return r if binary else r.decode("utf-8", "ignore")
        except Exception:
            if k == tries - 1:
                raise
            time.sleep(3 * (k + 1))


def parse_pdf(pdf_bytes):
    """PDF → {타입: [(가격원시값, 세대수)…]} — 스케일(원/천원/만원) 미적용 원시값.

    (2026-08-16 고도화) v1 은 '라벨 등장 이후 행'을 그 타입에 귀속했는데, 표의 타입
    라벨은 세로 병합셀 **중앙**에 인쇄되므로 블록 앞쪽 절반이 직전 타입에 오귀속됐다
    (실측: 쌍용 서대문 84A 의 13-14층 행이 59A 로 → 59A 검증 탈락·84A 최고층 누락).
    → 행 자체에 라벨이 있으면 그것, 없으면 **줄 번호 최근접 라벨**로 귀속(중앙 병합
    구조에서 중점 분할과 동치). 스케일은 여기서 정하지 않고 검증 단계에서 API 최고가에
    맞는 배수(1/1000/10000)를 자동 선택 — '단위: 천원' 표기 누락 PDF 도 살린다."""
    with tempfile.NamedTemporaryFile(suffix=".pdf") as f:
        f.write(pdf_bytes)
        f.flush()
        r = subprocess.run(["pdftotext", "-layout", f.name, "-"],
                           capture_output=True, timeout=120)
    txt = r.stdout.decode("utf-8", "ignore")
    if "공급금액" not in txt:
        return {}
    labels, rows = [], []
    for i, ln in enumerate(txt.splitlines()):
        amts = [int(a.replace(",", ""))
                for a in re.findall(r"\d{1,3}(?:,\d{3})+", ln)]
        big = [a for a in amts if a >= 3e4]    # 천원 단위 표(계≈1e6)도 후보로
        t = re.match(r"\s{0,10}(\d{2,3}[A-Z]{0,2})\b", ln)
        if "층" in ln and len(big) >= 2:
            n = 1
            mn_ = re.search(r"층\s+(\d{1,3})\s+\d", ln)
            if mn_:
                n = int(mn_.group(1))
            rows.append((i, max(big), n, t.group(1) if t else None))
        elif t and not amts and len(ln.strip()) <= 12:
            labels.append((i, t.group(1)))     # 단독 라벨 줄 (병합셀 중앙)
    out = {}
    for i, pr, n, own in rows:
        ty = own or (min(labels, key=lambda l: abs(l[0] - i))[1] if labels else "_")
        out.setdefault(ty, []).append((pr, n))
    return out


def pick_type(parsed, st, top_api, single):
    """타입 st 의 원시 행들에 스케일(1/천/만원)을 대입해 API 최고가 ±3% 에 맞는
    배수를 찾으면 (mn, av, mx) 원 단위 반환 — 못 찾으면 None(검증 탈락)."""
    cand = parsed.get(st) or (parsed.get("_") if single else None)
    if not cand:
        return None
    for sc in (1, 1000, 10000):
        vals = [(p * sc, n) for p, n in cand if p * sc >= 5e7]
        if not vals:
            continue
        mx = max(v for v, _ in vals)
        if abs(mx - top_api) / top_api <= 0.03:
            mn = min(v for v, _ in vals)
            av = sum(v * n for v, n in vals) / sum(n for _, n in vals)
            return mn, av, mx
    return None


def main():
    import sys
    all_mode = "--all" in sys.argv
    retry = "--retry" in sys.argv
    d = json.loads(SUB.read_text(encoding="utf-8"))
    cache = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    if retry:                                 # 파서 개선 후 실패분(가격 데이터 없는 캐시) 재시도
        cache = {k: v for k, v in cache.items()
                 if any(not kk.startswith("_") for kk in v)}
    since = (date.today() - timedelta(days=120)).isoformat()
    todo = [i for i in d["items"]
            if i.get("url") and i["no"] not in cache
            and (all_mode or (i.get("r1_bg") or "") >= since)][:LIMIT]
    print(f"[pdf] 대상 {len(todo)}건 (캐시 {len(cache)}건{' · retry' if retry else ''})")
    ok = 0
    for i in todo:
        no = i["no"]
        try:
            html = get(i["url"])
            # 공고문 앵커 우선 + 나머지 첨부 순 — 최대 2개까지 시도 (정정공고·형식 상이 대비)
            pri = re.findall(r'href="(https://static\.applyhome\.co\.kr/ai/aia/getAtchmnfl\.do[^"]+)"[^>]*>\s*모집공고문', html)
            allm = re.findall(r'href="(https://static\.applyhome\.co\.kr/ai/aia/getAtchmnfl\.do[^"]+)"', html)
            links = list(dict.fromkeys(pri + allm))[:2]
            if not links:
                cache[no] = {"_src": "링크없음"}
                continue
            ent, tys = {}, i.get("ty") or []
            for url in links:
                parsed = parse_pdf(get(url.replace("&amp;", "&"), binary=True))
                for t in tys:
                    if not t.get("pr"):
                        continue
                    st = short_ty(t["t"])
                    if st in ent:
                        continue
                    p = pick_type(parsed, st, t["pr"] * 1e8, len(tys) == 1)
                    if p:
                        ent[st] = {"mn": round(p[0] / 1e8, 2), "av": round(p[1] / 1e8, 2),
                                   "mx": round(p[2] / 1e8, 2)}
                if len(ent) >= sum(1 for t in tys if t.get("pr")):
                    break                     # 전 타입 확보 시 다음 첨부 생략
            cache[no] = ent or {"_src": "검증실패"}
            if ent:
                ok += 1
                print(f"  ✓ {i['name'][:28]} {len(ent)}타입 {list(ent.items())[0]}")
        except Exception as e:
            cache[no] = {"_src": f"오류:{type(e).__name__}"}
        time.sleep(1.5)
    OUT.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    print(f"[pdf] ✅ 신규 파싱 {ok}/{len(todo)} · 캐시 {len(cache)}건 → {OUT}")


if __name__ == "__main__":
    main()
