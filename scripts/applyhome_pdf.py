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


def parse_pdf(pdf_bytes, unit_hint=1):
    """PDF → {타입: (mn, av, mx)} (원 단위). 타입 못 찾은 행은 '_' 에 귀속."""
    with tempfile.NamedTemporaryFile(suffix=".pdf") as f:
        f.write(pdf_bytes)
        f.flush()
        r = subprocess.run(["pdftotext", "-layout", f.name, "-"],
                           capture_output=True, timeout=120)
    txt = r.stdout.decode("utf-8", "ignore")
    if "공급금액" not in txt:
        return {}
    unit = unit_hint
    m = re.search(r"공급금액[^\n]{0,80}단위\s*[:：][^\n]*?(천원|만원|원)", txt)
    if m:
        unit = {"원": 1, "천원": 1000, "만원": 10000}[m.group(1)]
    acc = {}                                  # ty → [wsum, n, mn, mx]
    cur = None
    for ln in txt.splitlines():
        t = re.match(r"\s{0,4}(\d{2,3}[A-Z]{0,2})\b", ln)
        if t and not re.match(r"\s*\d+층", ln):
            cur = t.group(1)                  # 타입 컨텍스트 (병합셀 → 이후 행에 계속 적용)
        if "층" not in ln:
            continue
        amts = [int(a.replace(",", "")) * unit
                for a in re.findall(r"\d{1,3}(?:,\d{3}){2,}", ln)]
        amts = [a for a in amts if a >= 5e7]
        if len(amts) < 2:
            continue
        pr = max(amts)                        # 행 최대 = 분양가 '계'
        n = 1
        mn_ = re.search(r"층\s+(\d{1,3})\s+\d{1,3},", ln)
        if mn_:
            n = int(mn_.group(1))
        k = cur or "_"
        a = acc.setdefault(k, [0, 0, None, None])
        a[0] += pr * n
        a[1] += n
        a[2] = pr if a[2] is None else min(a[2], pr)
        a[3] = pr if a[3] is None else max(a[3], pr)
    return {k: (v[2], v[0] / v[1], v[3]) for k, v in acc.items() if v[1]}


def main():
    import sys
    all_mode = "--all" in sys.argv
    d = json.loads(SUB.read_text(encoding="utf-8"))
    cache = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    since = (date.today() - timedelta(days=120)).isoformat()
    todo = [i for i in d["items"]
            if i.get("url") and i["no"] not in cache
            and (all_mode or (i.get("r1_bg") or "") >= since)][:LIMIT]
    print(f"[pdf] 대상 {len(todo)}건 (캐시 {len(cache)}건)")
    ok = 0
    for i in todo:
        no = i["no"]
        try:
            html = get(i["url"])
            m = re.search(r'href="(https://static\.applyhome\.co\.kr/ai/aia/getAtchmnfl\.do[^"]+)"[^>]*>\s*모집공고문', html) \
                or re.search(r'href="(https://static\.applyhome\.co\.kr/ai/aia/getAtchmnfl\.do[^"]+)"', html)
            if not m:
                cache[no] = {"_src": "링크없음"}
                continue
            parsed = parse_pdf(get(m.group(1).replace("&amp;", "&"), binary=True))
            # ── 검증: API 최고공급금액과 대조 (±3%) ──
            ent = {}
            tys = i.get("ty") or []
            for t in tys:
                if not t.get("pr"):
                    continue
                st = short_ty(t["t"])
                p = parsed.get(st) or (parsed.get("_") if len(tys) == 1 else None)
                if not p:
                    continue
                top_api = t["pr"] * 1e8
                if abs(p[2] - top_api) / top_api <= 0.03:
                    ent[st] = {"mn": round(p[0] / 1e8, 2), "av": round(p[1] / 1e8, 2),
                               "mx": round(p[2] / 1e8, 2)}
            cache[no] = ent or {"_src": "검증실패"}
            if ent:
                ok += 1
                print(f"  ✓ {i['name'][:28]} {list(ent.items())[0]}")
        except Exception as e:
            cache[no] = {"_src": f"오류:{type(e).__name__}"}
        time.sleep(1.5)
    OUT.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    print(f"[pdf] ✅ 신규 파싱 {ok}/{len(todo)} · 캐시 {len(cache)}건 → {OUT}")


if __name__ == "__main__":
    main()
