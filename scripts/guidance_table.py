#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""guidance_table.py — 8-K 보도자료 **원문 HTML의 표**에서 가이던스를 읽는다 (2026-08-10 신설).

왜 필요한가
-----------
지금까지는 첨부를 평문으로 바꿔 문장에서 값을 찾았다. 그런데 가이던스는 상당수가 **표**로
제시된다. 평문화하면 열 머리글과 값의 대응이 사라져, 어느 기간의 값인지 문장 규칙으로
추측해야 했다. 실측 PTC:

    Reconciliation of EPS Guidance to Non-GAAP EPS Guidance
                              FY’26 Guidance    Q4’26 Guidance
    Earnings per share        $8.46 to $9.18    $0.94 to $1.17

평문에서는 "FY’26 Guidance Q4’26 Guidance Earnings per share $8.46 to $9.18 $0.94 to $1.17"
가 되어, 값 바로 앞의 'Q4’26' 이 이겨 연간 8.46 이 분기로 분류됐다(+300%대 갭).
표를 표로 읽으면 **첫 번째 값 열의 머리글이 FY’26** 이라는 사실이 그대로 남는다.

읽는 규칙
---------
  ① 가이던스 표만 본다 — 표 안이나 바로 앞 문구에 guidance/outlook 이 있어야 한다.
  ② 머리글 행에서 **열별 기간**을 확정한다(FY26 · Q4’26 · Full Year 2026 · Three Months Ending…).
  ③ 행 이름이 매출/EPS 인 행만 읽는다. 다른 항목(EBITDA·현금흐름 등)은 건너뛴다.
  ④ 셀에서 범위를 읽는다. 한 셀에 "8.46 to 9.18" 이 있거나, 인접 두 셀에 lo·hi 가 나뉘어 있다.
  ⑤ 기간을 확정하지 못한 열은 버린다(추측하지 않는다).

문장 파서(guidance_parse)를 대체하지 않고 **먼저 시도**한다 — 표에서 확정되면 그 값이
가장 믿을 만하고, 표가 없으면 종전대로 문장에서 찾는다.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"[\s ]+")

# 열 머리글 → 기간. 분기 표시가 있으면 분기, 없고 연도·연간 표시만 있으면 연간.
_H_Q = re.compile(r"\bQ[1-4]\b|first|second|third|fourth\s+quarter|quarter|three\s+months", re.I)
_H_Y = re.compile(r"\bFY\b|fiscal\s*year|full\s*year|twelve\s+months|year\s+end|annual|\b20\d\d\b", re.I)
# 행 이름
_R_REV = re.compile(r"^(?:total\s+|net\s+|consolidated\s+)?(?:revenue|revenues|net sales|sales)\b", re.I)
_R_EPS = re.compile(r"(?:earnings|income|eps)\s*(?:\(loss\)\s*)?per\s+(?:diluted\s+)?share|"
                    r"\bdiluted\s+eps\b|\beps\b", re.I)
# 읽으면 안 되는 행(다른 항목)
_R_SKIP = re.compile(r"ebitda|ebit\b|margin|cash\s*flow|capital|capex|expense|tax|interest|"
                     r"share\s*count|shares|dividend|debt|amortization|depreciation|"
                     # 조정 명세 행 — "Less diluted EPS attributable to share-based compensation"
                     # 같은 항목을 EPS 로 읽으면 0.72 짜리 가짜 값이 나온다(실측 QCOM).
                     r"^\s*(?:less|plus|add|adjust|reconcil)|attributable to|"
                     r"stock[-\s]?based|share[-\s]?based|acquisition[-\s]related|restructur", re.I)
_NUM = re.compile(r"\(?\$?\s*([\d,]+(?:\.\d+)?)\s*\)?\s*(billion|million|bn|mm|b|m)?", re.I)
_MULT = {"billion": 1e9, "bn": 1e9, "b": 1e9, "million": 1e6, "mm": 1e6, "m": 1e6}


def _txt(s):
    return _WS.sub(" ", _TAG.sub(" ", s)).replace("&nbsp;", " ").replace("&amp;", "&").strip()


def _cells(row_html):
    return [_txt(c) for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row_html, re.S | re.I)]


def _period(head):
    """열 머리글 문자열 → 'Q' · 'Y' · None"""
    if not head:
        return None
    q, y = _H_Q.search(head), _H_Y.search(head)
    if q and not y:
        return "Q"
    if y and not q:
        return "Y"
    if q and y:
        # "Q4’26" 처럼 분기 표시가 연도에 붙어 있으면 분기다.
        return "Q"
    return None


def _range(cells, i, metric):
    """i 번째 셀(필요하면 다음 셀까지)에서 (lo, hi) 를 읽는다."""
    def one(s):
        vals = []
        for m in _NUM.finditer(s or ""):
            try:
                v = float(m.group(1).replace(",", ""))
            except Exception:
                continue
            u = (m.group(2) or "").lower()
            if u in _MULT:
                v *= _MULT[u]
            elif metric == "rev" and v < 1e5:
                v *= 1e6                       # 표 단위가 백만인 경우가 대부분
            vals.append(v)
        return vals
    v = one(cells[i] if i < len(cells) else "")
    if len(v) >= 2:
        return min(v[:2]), max(v[:2])
    if len(v) == 1:
        nxt = one(cells[i + 1]) if i + 1 < len(cells) else []
        if len(nxt) == 1:                       # lo·hi 가 인접 두 셀로 나뉜 형태
            return min(v[0], nxt[0]), max(v[0], nxt[0])
        return v[0], v[0]
    return None, None


def parse_tables(html):
    """원문 HTML → {rev_lo,rev_hi,eps_lo,eps_hi,fy_*} + _ev(근거 표 머리글)"""
    out, ev = {}, {}
    if not html:
        return out
    for tm in re.finditer(r"<table[^>]*>(.*?)</table>", html, re.S | re.I):
        tb = tm.group(1)
        lead = _txt(html[max(0, tm.start() - 400):tm.start()])[-200:]
        flat = _txt(tb)
        if not re.search(r"guidance|outlook", flat + " " + lead, re.I):
            continue                                    # 가이던스 표가 아니면 보지 않는다
        rows = [_cells(r) for r in re.findall(r"<tr[^>]*>(.*?)</tr>", tb, re.S | re.I)]
        rows = [r for r in rows if any(c for c in r)]
        if len(rows) < 2:
            continue
        # 머리글 행 = 기간을 담은 셀이 가장 많은 행(위쪽 3행 안에서)
        hdr, hi_ = None, -1
        for r in rows[:3]:
            n = sum(1 for c in r if _period(c))
            if n > hi_:
                hdr, hi_ = r, n
        if not hdr or hi_ == 0:
            continue
        # '이전 가이던스' 열은 버린다 — 실측 PTC 표에는 현재와 직전 가이던스가 나란히 있어
        # 왼쪽부터 읽으면 옛 값을 채택한다.
        cols = {i: _period(c) for i, c in enumerate(hdr)
                if _period(c) and not re.search(r"prior|previous|last\s|as\s+of\s+\w+\s+\d", c, re.I)}
        for r in rows:
            if r is hdr or not r:
                continue
            name = next((c for c in r if c), "")
            if _R_SKIP.search(name):
                continue
            metric = "rev" if _R_REV.search(name) else ("eps" if _R_EPS.search(name) else None)
            if not metric:
                continue
            # EPS 는 컨센서스가 조정(non-GAAP) 기준이므로 GAAP 전용 행은 읽지 않는다.
            # 실측 QCOM 표에는 'GAAP diluted EPS'(1.22~1.42) 와 'Non-GAAP diluted EPS'
            # (2.05~2.25) 가 나란히 있어, 앞줄을 읽으면 −40% 짜리 가짜 갭이 나온다.
            if metric == "eps" and re.search(r"(?<!non-)(?<!non )\bgaap\b", name, re.I):
                continue
            for i, per in cols.items():
                lo, hi = _range(r, i, metric)
                if lo is None or lo <= 0:
                    continue
                if metric == "eps" and not (-100 < lo <= hi < 1000):
                    continue
                if metric == "rev" and not (lo > 1e5 and hi / lo < 1.6):
                    continue
                pre = "" if per == "Q" else "fy_"
                if pre + metric + "_lo" in out:
                    continue
                out[pre + metric + "_lo"], out[pre + metric + "_hi"] = lo, hi
                ev[pre + metric] = f"[표] {hdr[i]} · {name}"
    if ev:
        out["_ev"] = ev
    return out


if __name__ == "__main__":
    from earnings_8k_watch import cik_map, get
    from guidance_check import latest_earn_8k
    import json as _json
    mp = cik_map()
    for sym in sys.argv[1:] or ["PTC"]:
        cik = mp.get(sym.upper())
        acc = latest_earn_8k(cik) if cik else None
        if not acc:
            print(f"{sym}: 8-K 없음"); continue
        an = acc.replace("-", "")
        idx = _json.loads(get(f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{an}/index.json"))
        htm = [i for i in idx["directory"]["item"] if str(i.get("name", "")).lower().endswith((".htm", ".html"))]
        name = None
        for pat in (r"ex-?99", r"press.?release", r"(^|[^a-z])pr\.htm", r"earnings"):
            c = [i for i in htm if re.search(pat, i["name"], re.I)]
            if c:
                name = max(c, key=lambda i: int(i.get("size") or 0))["name"]; break
        if not name:
            print(f"{sym}: 첨부 못 찾음"); continue
        raw = get(f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{an}/{name}", timeout=30)
        g = parse_tables(raw if isinstance(raw, str) else raw.decode("utf-8", "ignore"))
        print(sym, {k: v for k, v in g.items() if not k.startswith("_")}, g.get("_ev"))
