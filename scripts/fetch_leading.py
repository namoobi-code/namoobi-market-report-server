#!/usr/bin/env python3
# fetch_leading.py (v3.13.0) -- 경기선행지수 순환변동치 월별 실측 수집 (sandbox, Chrome 불필요).
# 소스: e-나라지표 통계표 AJAX 엔드포인트 showStblGams3.do (stts_cd=105701, idx_cd=1057, freq=M)
#       = 국가데이터처 「산업활동동향」 선행종합지수 순환변동치(2020=100). curl/web_fetch 와 달리
#       UA+Referer+X-Requested-With 헤더를 주면 sandbox 에서 200 으로 응답(Chrome 불필요).
# 출력(WORK): nmr_leading_series.json [["YYYY-MM",val]..] (공개 전월, 보통 ~29개월),
#             nmr_leading.json {"korea_leading":[{period,value,mom,note}]} (최신 4개월, 내림차순).
# 사용: python3 fetch_leading.py [WORK_DIR]   (WORK 없으면 cwd)
# 실패해도 비차단: 파일 미생성 → merge.py 가 캐시/직전 report_data 로 폴백.
import sys, os, json, re, ssl, urllib.request, datetime as dt
from html.parser import HTMLParser

WORK = sys.argv[1] if (len(sys.argv) > 1 and os.path.isdir(sys.argv[1])) else "."

def period_str(back=30):
    end = dt.date.today().replace(day=1)
    y, m = end.year, end.month - back
    while m <= 0:
        m += 12; y -= 1
    start = dt.date(y, m, 1)
    return f"{start.year}{start.month:02d}:{end.year}{end.month:02d}"

URL = ("https://www.index.go.kr/unity/potal/eNara/sub/showStblGams3.do"
       "?stts_cd=105701&idx_cd=1057&freq=M&period=" + period_str())

class TableParser(HTMLParser):
    def __init__(self):
        super().__init__(); self.rows = []; self.cur = None; self.cell = False; self.buf = ""
    def handle_starttag(self, t, a):
        if t == "tr": self.cur = []
        elif t in ("td", "th") and self.cur is not None: self.cell = True; self.buf = ""
    def handle_data(self, d):
        if self.cell: self.buf += d
    def handle_endtag(self, t):
        if t in ("td", "th") and self.cell: self.cur.append(self.buf.strip()); self.cell = False
        elif t == "tr" and self.cur is not None: self.rows.append(self.cur); self.cur = None

def fetch():
    ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
    req = urllib.request.Request(URL, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Referer": "https://www.index.go.kr/unity/potal/main/EachDtlPageDetail.do?idx_cd=1057",
        "X-Requested-With": "XMLHttpRequest"})
    return urllib.request.urlopen(req, timeout=20, context=ctx).read().decode("utf-8", "replace")

def parse(html):
    P = TableParser(); P.feed(html)
    months, vals = [], []
    for r in P.rows:
        # (req6 2026-07-17) 잠정치 월 헤더 '202605월p'/'2026.05(p)' 대응 — p 접미 허용(종전 정규식이 최근 3개월을 탈락시켜 시계열이 2~5개월 뒤처졌다)
        ms = [c for c in r if re.match(r"^\d{6}(\uc6d4)?[ ()pP]*$", c.replace("\xa0", " ").strip())]
        if len(ms) > len(months):
            months = [re.sub(r"[^0-9]", "", c)[:6] for c in ms]
        lbl = r[0] if r else ""
        if "선행" in lbl and "순환변동" in lbl:
            vals = list(r[1:])
    series = []
    # (req6) 우측 정렬 페어링 — 헤더/값 셀 수가 달라도 최신월 기준으로 맞춘다(좌측 zip 은 어긋나면 최근월이 밀린다)
    n = min(len(months), len(vals))
    for mo, v in zip(months[-n:], vals[-n:]):
        try: fv = float(re.sub(r"[, ]", "", v))
        except Exception: continue
        series.append([f"{mo[:4]}-{mo[4:6]}", fv])
    return series

def main():
    try:
        series = parse(fetch())
    except Exception as e:
        print("fetch_leading 실패(비차단):", type(e).__name__, e); return
    if len(series) < 12:
        print(f"fetch_leading: 시계열 부족({len(series)}<12) -- 미생성(비차단)"); return
    json.dump(series, open(os.path.join(WORK, "nmr_leading_series.json"), "w"), ensure_ascii=False)
    tail = series[-5:] if len(series) >= 5 else series
    kl = []
    for i in range(len(tail) - 1, 0, -1):
        mom = round(tail[i][1] - tail[i - 1][1], 1)
        kl.append({"period": tail[i][0].replace("-", "."), "value": tail[i][1],
                   "mom": ("+%.1f" % mom if mom >= 0 else "%.1f" % mom) + "p", "note": ""})
        if len(kl) >= 4: break
    json.dump({"korea_leading": kl}, open(os.path.join(WORK, "nmr_leading.json"), "w"), ensure_ascii=False)
    print(f"fetch_leading OK -- series {len(series)}pts (last {series[-1]}), korea_leading {len(kl)}mo desc")

if __name__ == "__main__":
    main()
# EOF -- namoobi-market-report fetch_leading.py
