#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""sports_watch.py — 취미(운동) 대회 신규 감지 (2026-08-06 신설 · 주 1회).

무토큰 서버 감시 — 실측 확인된 두 소스에서 '대회일'을 수집해 sports_events.json(LLM 조사 정본)과
대조, 목록에 없는 신규 대회를 sports_detect.json 에 기록한다. 접수일은 게시글 텍스트라 자동 불가
→ 월 1회 /namoobi-run-search(LLM)가 감지분을 정밀조사해 정본에 편입한다.

소스(실측 ✓): ① 로드런 roadrun.co.kr/schedule/list.php?syear_key&smonth_key&take_key=풀 (EUC-KR)
             ② KTF triathlon.or.kr 대회일정 (tourcd 블록 — 장소·날짜·접수상태 포함)
cron: 0 9 * * 0  (일요일 09:00)
"""
import json, re, time, urllib.request, urllib.parse
from datetime import datetime, timedelta
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
EV = BASE / "data" / "db" / "sports_events.json"
OUT = BASE / "data" / "db" / "sports_detect.json"
UA = {"User-Agent": "Mozilla/5.0"}

def get(u, to=20):
    return urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=to).read()

def roadrun_full(months=6):
    """향후 N개월 풀코스(+100km) 대회 [(date,name,place)] — 로드런"""
    out = []
    now = datetime.now()
    for k in range(months):
        y = now.year + (now.month - 1 + k) // 12
        m = (now.month - 1 + k) % 12 + 1
        for take in ("풀", "100km"):
            try:
                q = urllib.parse.urlencode({"syear_key": y, "smonth_key": m, "take_key": take}, encoding="euc-kr")
                t = get(f"http://www.roadrun.co.kr/schedule/list.php?{q}").decode("euc-kr", "ignore")
            except Exception:
                continue
            # 실측 구조(태그 제거·파이프 압축 후): |10/3|(토)|대회명|종목|장소|주최|
            plain = re.sub(r"[\s|]+", "|", re.sub(r"<[^>]+>", "|", t))
            for mm in re.finditer(r"\|(\d{1,2})/(\d{1,2})\|\(([일월화수목금토])\)\|([^|]{4,50})\|([^|]{1,40})\|([^|]{2,40})\|", plain):
                mo, dd, _, nm, kinds, pl = mm.groups()
                nm = re.sub(r"\s+", " ", nm).strip()
                if int(mo) != m or not re.search(r"[가-힣A-Za-z]", nm):
                    continue
                out.append((f"{y}-{int(mo):02d}-{int(dd):02d}", nm, pl.strip(), f"로드런({take}·{kinds.strip()[:14]})"))
            time.sleep(0.4)
    return out

def ktf_events():
    """KTF 대회일정 [(date,name,place,status)]"""
    out = []
    try:
        t = get("https://triathlon.or.kr/events/tour/?mode=list&syear=2026").decode("utf-8", "ignore")
        t += get("https://triathlon.or.kr/events/tour/?mode=list&syear=2027").decode("utf-8", "ignore")
    except Exception:
        return out
    plain = re.sub(r"<[^>]+>", "|", t)
    for mm in re.finditer(r"\|([^|]{6,60}(?:대회|트라이애슬론|아이언맨|철인)[^|]{0,20})\|[^|]*\|?장소:\s*([^|]{2,40})\|.{0,200}?\|(20\d\d)\.(\d{2})\.(\d{2})\|.{0,120}?\|(접수[^|]{0,6}|마감[^|]{0,4})\|", plain, re.S):
        nm, pl, y, mo, dd, st = mm.groups()
        nm = re.sub(r"\s+", " ", nm).strip()
        if "교육" in nm or "심판" in nm or "세미나" in nm:
            continue
        out.append((f"{y}-{mo}-{dd}", nm, pl.strip(), f"KTF·{st.strip()}"))
    return out

def norm(s):
    """대회명 정규화 — 연도·회차·공백·특수문자 제거 후 비교"""
    s = re.sub(r"(제?\d+회|20\d\d|by UTMB|\(.*?\))", "", s)
    return re.sub(r"[^가-힣a-zA-Z0-9]", "", s).lower()

def main():
    ev = json.loads(EV.read_text(encoding="utf-8"))
    known = [norm(e["name"]) for e in ev.get("events") or []]
    today = datetime.now().strftime("%Y-%m-%d")
    cand = roadrun_full() + ktf_events()
    print(f"[sw] 수집 — 로드런+KTF {len(cand)}건")
    found, seen = [], set()
    for date, nm, pl, src in cand:
        if date < today:
            continue
        n = norm(nm)
        if not n or len(n) < 4 or n in seen:
            continue
        if any(n in k or k in n for k in known):
            continue                                    # 이미 정본에 있음
        seen.add(n)
        found.append({"date": date, "name": nm, "place": pl, "src": src})
    found.sort(key=lambda x: x["date"])
    OUT.write_text(json.dumps({"asof": datetime.now().strftime("%Y-%m-%d %H:%M"),
                               "found": found[:40]}, ensure_ascii=False), encoding="utf-8")
    print(f"[sw] ✅ 신규 감지 {len(found)}건 → {OUT}")

if __name__ == "__main__":
    main()
