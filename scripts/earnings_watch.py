#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""earnings_watch.py — DART 영업(잠정)실적 실시간 감지 (2026-08-05 신설).

한국 실적의 공식 최초 발표처 = DART '영업(잠정)실적(공정공시)' (회사 홈피·기사보다 먼저).
  · list.json(거래소공시 I) 을 폴링 → 새 잠정실적 공시의 document.xml(zip) 표를 파싱
  · 실측(20260804800585 HDC): 태그 제거 후 "매출액 당해실적 1,519,714 1,257,391 20.9 - 1,818,814 -16.4 -"
    → 숫자열 [당해, 직전, 직전比%, 전년동기, 전년동기比%] (전환여부 칸은 '-' 또는 '흑자전환' 텍스트)
판정: 전년동기比 매출/영업이익/순이익 %, 흑자·적자전환, ±30% 급증/급감 태그
산출: data/db/earnings_live.json {asof, days:{YYYYMMDD:[{c,n,rno,t,cons,u,sales,sales_yoy,op,op_yoy,ni,ni_yoy,tags}]}}
사용: earnings_watch.py [--date YYYYMMDD]   (기본 오늘 · 최근 45일 유지)
cron: */5 07-18 * * 1-5 (공시는 보통 08~18시, 마감 후 15:30~18시 집중)
"""
import io, json, re, sys, time, urllib.request, zipfile
from datetime import datetime, timedelta
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "data" / "db" / "earnings_live.json"
KEY = (BASE / "keys" / "opendart.txt").read_text().strip()
DATE = None
if "--date" in sys.argv:
    DATE = sys.argv[sys.argv.index("--date") + 1]
D8 = DATE or datetime.now().strftime("%Y%m%d")

def jget(u):
    return json.loads(urllib.request.urlopen(u, timeout=20).read())

def num(tok):
    """DART 숫자 토큰 → float. '-'·빈칸·텍스트는 None. △·(괄호)=음수."""
    t = tok.strip().replace(",", "").replace("△", "-")
    if t.startswith("(") and t.endswith(")"):
        t = "-" + t[1:-1]
    if not re.fullmatch(r"-?\d+(\.\d+)?", t):
        return None
    return float(t)

def parse_doc(rno):
    """공시 원문 → {u단위(억 환산계수), 지표별 (당해, 전년동기, 전년比%, 전환텍스트)}"""
    raw = urllib.request.urlopen(
        f"https://opendart.fss.or.kr/api/document.xml?crtfc_key={KEY}&rcept_no={rno}", timeout=25).read()
    z = zipfile.ZipFile(io.BytesIO(raw))
    d = z.read(z.namelist()[0])
    try:
        t = d.decode("utf-8")
    except UnicodeDecodeError:
        t = d.decode("cp949", "ignore")
    flat = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", t))
    # 단위 — 표 머리에 '(단위: 백만원)' 식. 억원 환산 계수
    unit = 1 / 100          # 백만원 → 억원 (기본)
    mu = re.search(r"단위\s*[::]?\s*(백만원|천원|억원|원)", flat)
    if mu:
        unit = {"백만원": 1/100, "천원": 1/100000, "억원": 1.0, "원": 1/1e8}[mu.group(1)]
    toks = flat.split(" ")
    METS = {"sales": ("매출액", "영업수익"), "op": ("영업이익",), "ni": ("당기순이익", "분기순이익", "반기순이익")}
    out = {"unit": unit}
    for k, labels in METS.items():
        idx = None
        for i, tk in enumerate(toks):
            if any(tk == lb for lb in labels):
                # 그 다음 '당해실적' 행을 찾는다
                for j in range(i + 1, min(i + 4, len(toks))):
                    if "당해실적" in toks[j]:
                        idx = j
                        break
                if idx:
                    break
        if idx is None:
            continue
        seg = toks[idx + 1: idx + 12]
        nums, turn = [], None
        for tk in seg:
            if "누계실적" in tk or any(lb in tk for mm in METS.values() for lb in mm):
                break
            v = num(tk)
            if v is not None:
                nums.append(v)
            if "흑자전환" in tk or "흑자로전환" in tk:
                turn = "흑자전환"
            elif "적자전환" in tk:
                turn = "적자전환"
        if not nums:
            continue
        now = nums[0]
        # 실측 구조: [당해, 직전, 직전比, 전년동기, 전년比] — 전년 쌍 = 마지막 두 숫자
        yoy_v = nums[-2] if len(nums) >= 4 else None
        yoy_p = nums[-1] if len(nums) >= 5 else None
        if yoy_p is not None and abs(yoy_p) > 5000:      # % 자리로 보기 어려운 값 방어
            yoy_p = None
        if turn is None and yoy_v is not None:           # 텍스트가 없어도 부호로 판정
            if yoy_v < 0 <= now: turn = "흑자전환"
            elif now < 0 <= yoy_v: turn = "적자전환"
        out[k] = (now, yoy_v, yoy_p, turn)
    return out

def tags_of(p):
    tg = []
    def g(k): return p.get(k) or (None, None, None, None)
    s, o, n = g("sales"), g("op"), g("ni")
    if o[3]: tg.append("영업익 " + o[3])
    elif o[2] is not None:
        if o[2] >= 30: tg.append(f"영업익 급증 +{o[2]:.0f}%")
        elif o[2] <= -30: tg.append(f"영업익 급감 {o[2]:.0f}%")
    if s[2] is not None:
        if s[2] >= 30: tg.append(f"매출 급증 +{s[2]:.0f}%")
        elif s[2] <= -30: tg.append(f"매출 급감 {s[2]:.0f}%")
    if n[3] and not o[3]: tg.append("순이익 " + n[3])
    return tg

def main():
    old = {}
    try:
        old = json.loads(OUT.read_text(encoding="utf-8"))
    except Exception:
        pass
    days = old.get("days") or {}
    seen = {it["rno"] for v in days.values() for it in v}
    # 오늘 거래소공시 전 페이지에서 잠정실적만
    items, page = [], 1
    while page <= 6:
        j = jget(f"https://opendart.fss.or.kr/api/list.json?crtfc_key={KEY}"
                 f"&bgn_de={D8}&end_de={D8}&pblntf_ty=I&page_count=100&page_no={page}")
        if j.get("status") != "000":
            break
        lst = j.get("list") or []
        items += [x for x in lst if "영업(잠정)실적" in x.get("report_nm", "") and x.get("stock_code")]
        if page * 100 >= int(j.get("total_count") or 0):
            break
        page += 1
        time.sleep(0.2)
    # 정정 포함 종목별 최신 rcept 만
    by = {}
    for x in sorted(items, key=lambda z: z["rcept_no"]):
        by[x["stock_code"]] = x
    new = 0
    for code, x in by.items():
        rno = x["rcept_no"]
        if rno in seen:
            continue
        try:
            p = parse_doc(rno)
        except Exception as e:
            print("  파싱실패", x["corp_name"], rno, repr(e))
            continue
        u = p.get("unit", 1/100)
        def val(k, i):
            v = (p.get(k) or (None,)*4)[i]
            return round(v * u, 1) if (i in (0, 1) and v is not None) else v
        it = {"c": code, "n": x["corp_name"], "rno": rno,
              "t": datetime.now().strftime("%H:%M"),
              "cons": "연결" if "연결" in x.get("report_nm", "") else "별도",
              "sales": val("sales", 0), "sales_yoy": val("sales", 2),
              "op": val("op", 0), "op_yoy": val("op", 2),
              "ni": val("ni", 0), "ni_yoy": val("ni", 2)}
        it["tags"] = tags_of(p)
        days.setdefault(D8, [])
        days[D8] = [z for z in days[D8] if z["c"] != code] + [it]   # 정정 시 교체
        new += 1
        print(f"  🔔 {x['corp_name']}({code}) 매출YoY {it['sales_yoy']}% · 영업익YoY {it['op_yoy']}% {it['tags']}")
        time.sleep(0.15)
    # 45일 초과 제거
    cut = (datetime.now() - timedelta(days=45)).strftime("%Y%m%d")
    days = {d: v for d, v in days.items() if d >= cut}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"asof": datetime.now().strftime("%Y-%m-%d %H:%M"), "days": days},
                              ensure_ascii=False), encoding="utf-8")
    tot = sum(len(v) for v in days.values())
    print(f"[earnings] ✅ {D8} 신규 {new}건 · 누적 {tot}건({len(days)}일) → {OUT}")

if __name__ == "__main__":
    main()
