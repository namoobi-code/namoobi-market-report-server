#!/usr/bin/env python3
"""fetch_msci_val.py — MSCI 국가지수 월간 팩트시트에서 선행 PER 등 밸류 지표 누적 (2026-09-20 신설)

배경: 블룸버그 '국가별 12M 선행 PER 20년' 차트(한국 극단적 저평가)를 무료로 재현하려면
원본(I/B/E/S 집계 히스토리)은 유료뿐이다. 대신 **MSCI 공식 월간 팩트시트 PDF** 가 매월 말
기준 P/E Fwd·P/E·P/BV·배당수익률을 무료로 싣는다(실측 2026-09-20: MSCI Korea AUG 31 2026 —
P/E Fwd 5.06 · P/E 10.17 · P/BV 2.26 · DY 0.82). 히스토리는 안 주므로 **매월 파싱해 누적**한다.
같은 표의 두 번째 행(벤치마크 — Korea·China·India 는 EM, USA 는 World)도 함께 저장한다.

⚠ URL 은 MSCI 문서 경로 규칙이 국가마다 다르다(china 만 -index-usd-net). 404 면 그 국가만 건너뛰고
   경보를 출력한다 — 규칙이 바뀌면 여기만 고치면 된다.
cron: 매월 3일·10일 09:30 (팩트시트가 월초 며칠 지나 갱신되는 경우가 있어 2회)
"""
import json
import re
import subprocess
import tempfile
import urllib.request
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "data" / "db" / "msci_val.json"
UA = {"User-Agent": "Mozilla/5.0"}

SRC = [  # key, 표시명, 팩트시트 URL, 팩트시트 안의 지수 행 이름
    ("KR", "한국", "https://www.msci.com/documents/10199/255599/msci-korea-index-net.pdf", "MSCI Korea"),
    ("US", "미국", "https://www.msci.com/documents/10199/255599/msci-usa-index-net.pdf", "MSCI USA"),
    ("CN", "중국", "https://www.msci.com/documents/10199/255599/msci-china-index-usd-net.pdf", "MSCI China"),
    ("IN", "인도", "https://www.msci.com/documents/10199/255599/msci-india-index-net.pdf", "MSCI India"),
]
MON = {m: i + 1 for i, m in enumerate("JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC".split())}


def parse(txt, row_name):
    """FUNDAMENTALS (MON DD, YYYY) 날짜 + 'MSCI X ... DY P/E P/E-Fwd P/BV' 행의 끝 4개 숫자."""
    m = re.search(r"FUNDAMENTALS\s*\(([A-Z]{3})\s+(\d{1,2}),\s*(\d{4})\)", txt)
    if not m:
        return None, None, None
    d = f"{m.group(3)}-{MON[m.group(1)]:02d}-{int(m.group(2)):02d}"
    # 같은 페이지에 'MSCI Korea …' 로 시작하는 행이 여러 표(성과·리스크)에 있다 — 1차 실행에서
    # 엉뚱한 표(0.52·71.5 같은 값)를 집었다. FUNDAMENTALS 헤더 **이후** 첫 두 행만 본다.
    lines = txt.splitlines()
    start = next((i for i, l in enumerate(lines) if "FUNDAMENTALS" in l), 0)
    rows, seen = {}, 0
    for line in lines[start:]:
        s = line.strip()
        if not s.startswith("MSCI "):
            continue
        seen += 1
        if seen > 2:
            break
        nums = re.findall(r"-?\d+\.\d+", s)
        if len(nums) < 4:
            continue
        name = re.split(r"\s{2,}", s)[0].strip()
        dy, pe, pef, pb = (float(x) for x in nums[-4:])
        rows[name] = {"d": d, "dy": dy, "pe": pe, "pe_fwd": pef, "pb": pb}
    main_row = rows.get(row_name)
    bench = next(((k, v) for k, v in rows.items() if k != row_name), (None, None))
    return d, main_row, bench


def main():
    prev = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    series = prev.get("series") or {}
    bench = prev.get("bench") or {}
    names = prev.get("names") or {}
    for key, nm, url, row in SRC:
        names[key] = nm
        try:
            pdf = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40).read()
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
                f.write(pdf); p = f.name
            txt = subprocess.run(["pdftotext", "-layout", p, "-"], capture_output=True, text=True, timeout=60).stdout
            Path(p).unlink(missing_ok=True)
        except Exception as e:
            print(f"  ⚠ {key} 팩트시트 실패: {repr(e)[:80]}", flush=True); continue
        d, r, (bname, bv) = parse(txt, row)
        if not r:
            print(f"  ⚠ {key} 파싱 실패 — 팩트시트 레이아웃 변경 의심", flush=True); continue
        s = [x for x in (series.get(key) or []) if x["d"] != d] + [r]
        series[key] = sorted(s, key=lambda x: x["d"])[-240:]
        if bname and bv:
            b = [x for x in (bench.get(bname) or []) if x["d"] != d] + [bv]
            bench[bname] = sorted(b, key=lambda x: x["d"])[-240:]
        print(f"  {key} {nm}: {d} P/E Fwd {r['pe_fwd']} · P/E {r['pe']} · P/BV {r['pb']} · DY {r['dy']}"
              f"{' · 벤치 '+bname+' fwd '+str(bv['pe_fwd']) if bv else ''}", flush=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "asof": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "src": "MSCI 국가지수 월간 팩트시트(USD·Net) FUNDAMENTALS — P/E Fwd=12M 선행 컨센 기준. 히스토리 미제공이라 매월 파싱 누적(2026-08월말~)",
        "names": names, "series": series, "bench": bench}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[msci_val] ✅ {', '.join(f'{k} {len(v)}점' for k, v in series.items())}")


if __name__ == "__main__":
    main()
