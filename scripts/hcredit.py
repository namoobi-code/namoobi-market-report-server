#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""hcredit.py — 가계대출·대출 연체율 (2026-08-10 신설 · 매일 07:15 cron).

소스: 한국은행 ECOS OpenAPI (기존 realestate.py 와 같은 인증키를 쓴다 — 신규 키 발급 불필요)

수집 통계표 (전부 실측 확인 2026-08-10 · 코드/항목명은 StatisticItemList 로 대조)
  901Y054  은행대출금 연체율(1일 이상)      M 2005.05~   기업·가계·신용카드 × 은행전체·일반·특수
  141Y005  예금은행 지역별 연체율(1개월 이상) M 2019.12~   전체·가계·주택관련·대기업·중소기업·기업 × 전국+16시도
  151Y005  예금취급기관 가계대출(용도별)      M 2003.10~   주택관련/기타 × 예금취급기관·예금은행·비은행 + 전세자금·정책대출
  151Y002  예금취급기관 가계대출(업권별)      M 2003.10~   예금은행·저축은행·신협·상호금융·새마을금고 등

왜 부동산 탭인가
  · 가계대출(특히 주택관련대출) **증감액**은 매수 자금의 크기 그 자체다.
    잔액이 아니라 전월 대비 증감이 신호 — 증가폭이 꺾이면 몇 달 뒤 거래량이 따라 꺾인다.
  · 연체율은 반대편 지표다. 가계·주택관련 연체율이 오르면 급매·경매 물량이 늘고,
    지역별로 보면 어느 지역이 먼저 무너지는지 1~2분기 앞서 드러난다.
  · 141Y005 는 **지역 × 차주 유형**이라 실거래·미분양과 같은 지역 축으로 겹쳐볼 수 있다.

호출량 관리 — ECOS 인증키는 일 10만건(행) 한도다.
  기본 실행은 최근 8개월만 받아 기존 JSON 에 머지(≈1,200행).
  --full 은 전 구간 재수집(≈15,000행) — 최초 1회, 또는 항목이 바뀌었을 때만.

산출: data/db/hcredit.json
사용: hcredit.py [--full] [--months N]
"""
import json, sys, time, urllib.request
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
OUT  = BASE / "data" / "db" / "hcredit.json"
API  = "https://ecos.bok.or.kr/api/StatisticSearch"

FULL   = "--full" in sys.argv
MONTHS = 8
if "--months" in sys.argv:
    MONTHS = int(sys.argv[sys.argv.index("--months") + 1])


def _key():
    """realestate.py 와 동일한 탐색 순서 — 서버는 keys/ecos.txt, PC 는 SECURITY 폴더."""
    cands = [BASE / "keys" / "ecos.txt",
             Path("D:/claudeCowork/SECURITY") / "한국은행OPENAPI인증키.txt"]
    cands += sorted(Path("/sessions").glob("*/mnt/claudeCowork/SECURITY/한국은행OPENAPI인증키.txt"))
    cands += sorted(Path("/sessions").glob("*/mnt/SECURITY/한국은행OPENAPI인증키.txt"))
    for p in cands:
        try:
            k = Path(p).read_text(encoding="utf-8").strip()
            if k:
                return k
        except Exception:
            pass
    raise SystemExit("ECOS 키 없음 (keys/ecos.txt)")


KEY = _key()
NOW = datetime.now()
END = NOW.strftime("%Y%m")


def _ym_back(n):
    y, m = NOW.year, NOW.month - n
    while m <= 0:
        m += 12
        y -= 1
    return f"{y}{m:02d}"


def fetch(stat, start, end, rows=100000, tries=3):
    """항목코드를 지정하지 않으면 해당 통계표의 전 항목 조합을 한 번에 준다(실측)."""
    url = f"{API}/{KEY}/json/kr/1/{rows}/{stat}/M/{start}/{end}/"
    for k in range(tries):
        try:
            raw = urllib.request.urlopen(url, timeout=180).read().decode("utf-8")
            d = json.loads(raw)
            if "RESULT" in d:                      # ERROR-2xx/3xx — 조회결과 없음 포함
                code = d["RESULT"].get("CODE", "")
                if code in ("INFO-200", "INFO-100"):
                    return []
                print(f"  ! {stat} {code} {d['RESULT'].get('MESSAGE','')[:80]}")
                return []
            return d.get("StatisticSearch", {}).get("row", []) or []
        except Exception as e:
            print(f"  ! {stat} 재시도 {k+1}/{tries}: {e}")
            time.sleep(2 + 2 * k)
    return []


def num(v):
    try:
        return float(v)
    except Exception:
        return None


# ── 표시용 이름 정리 ────────────────────────────────────────────────
# ECOS 항목명은 각주 기호("은행전체 1)")·괄호("가계대출 연체율(전체1M)")가 붙어 있어
# 그대로 범례에 쓰면 지저분하다. 차트에서 쓸 짧은 이름으로 미리 접는다.
DELQ_KIND = {"기업대출": "기업", "가계대출": "가계", "신용카드대출 2)": "신용카드"}
DELQ_BANK = {"은행전체 1)": "은행전체", "일반은행": "일반은행", "특수은행": "특수은행"}
REG_KIND = {
    "원화대출금연체율(전체1M)": "전체",
    "가계대출 연체율(전체1M)": "가계",
    "주택관련대출 연체율(전체1M)": "주택관련",
    "대기업대출 연체율(전체1M)": "대기업",
    "중소기업대출 연체율(전체1M)": "중소기업",
    "기업대출 연체율(전체1M)": "기업",
}
HH_USE = {
    "예금취급기관": "전체",
    "주택관련대출-예금취급기관": "주담대_전체",
    "기타대출-예금취급기관": "기타_전체",
    "주택관련대출-예금은행": "주담대_은행",
    "기타대출-예금은행": "기타_은행",
    "주택관련대출-비은행예금취급기관": "주담대_비은행",
    "기타대출-비은행예금취급기관": "기타_비은행",
    "[참고] 예금은행 전세자금대출": "전세자금",
    "[참고] 주택금융공사 및 주택도시기금의 정책대출": "정책대출",
}
HH_IND = {
    "예금취급기관": "전체", "예금은행": "예금은행", "비은행예금취급기관": "비은행",
    "상호저축은행": "저축은행", "신용협동조합": "신협", "상호금융": "상호금융",
    "새마을금고": "새마을금고", "우체국예금 등": "우체국",
}
# 시도 표시 순서 — 전국을 맨 앞에, 수도권을 그 다음에 두면 범례가 읽힌다
SIDO = ["전국", "서울", "경기", "인천", "부산", "대구", "광주", "대전", "울산",
        "세종", "강원", "충북", "충남", "전북", "전남", "경북", "경남", "제주"]


def to_flat(rows, keyfn, scale=1.0):
    """rows → {키: {YYYYMM: 값}}  (키는 keyfn 이 None 을 주면 버린다)"""
    out = {}
    for r in rows:
        k = keyfn(r)
        if k is None:
            continue
        v = num(r.get("DATA_VALUE"))
        if v is None:
            continue
        out.setdefault(k, {})[r.get("TIME")] = v * scale
    return out


def merge(old, new):
    """{키:{YYYYMM:값}} 를 병합 — 새 값이 이긴다(잠정 → 확정 갱신 반영)."""
    for k, m in new.items():
        old.setdefault(k, {}).update(m)
    return old


def densify(flat):
    """{키:{YYYYMM:값}} → 공통 t 축 + 키별 배열(빠진 달은 null)."""
    ts = sorted({t for m in flat.values() for t in m})
    return ts, {k: [m.get(t) for t in ts] for k, m in flat.items()}


def load_prev():
    """기존 산출물을 되풀어 {키:{YYYYMM:값}} 로 복원한다.

    원자료를 `_raw` 로 따로 저장해 두면 파일이 두 배가 된다(같은 숫자를 두 번 쓴다).
    화면용 구조만으로 손실 없이 되돌릴 수 있으므로 그렇게 하지 않는다."""
    try:
        d = json.loads(OUT.read_text(encoding="utf-8"))
    except Exception:
        return {}

    def two(block):                       # {상위:{하위:[...]}} → {"상위|하위":{ym:v}}
        t = block.get("t") or []
        out = {}
        for a, sub in (block.get("s") or {}).items():
            for b, arr in sub.items():
                out[f"{a}|{b}"] = {t[i]: v for i, v in enumerate(arr) if v is not None and i < len(t)}
        return out

    def one(block):                       # {키:[...]} → {키:{ym:v}}
        t = block.get("t") or []
        return {k: {t[i]: v for i, v in enumerate(arr) if v is not None and i < len(t)}
                for k, arr in (block.get("s") or {}).items()}

    return {"delq": two(d.get("delq", {})), "dreg": two(d.get("dreg", {})),
            "hh": one(d.get("hh", {})),     "ind": one(d.get("ind", {}))}


def main():
    start = "200501" if FULL else _ym_back(MONTHS)
    print(f"hcredit: {start} ~ {END} {'(전체 재수집)' if FULL else '(증분)'}")
    prev = load_prev()

    # ① 은행대출금 연체율 — 장기 시계열(은행전체 기준만 화면에 쓰지만 원자료는 전부 보관)
    r = fetch("901Y054", "200505" if FULL else start, END)
    delq = to_flat(r, lambda x: (f"{DELQ_BANK.get(x.get('ITEM_NAME2'), x.get('ITEM_NAME2'))}"
                                 f"|{DELQ_KIND.get(x.get('ITEM_NAME1'), x.get('ITEM_NAME1'))}"))
    print(f"  901Y054 연체율(장기) {len(r):,}행 · 계열 {len(delq)}")

    # ② 지역별 연체율 — 2019.12 부터만 존재
    r = fetch("141Y005", "201912" if FULL else start, END)
    dreg = to_flat(r, lambda x: (f"{REG_KIND.get(x.get('ITEM_NAME1'))}|{x.get('ITEM_NAME2')}"
                                 if REG_KIND.get(x.get('ITEM_NAME1')) else None))
    print(f"  141Y005 지역별 연체율 {len(r):,}행 · 계열 {len(dreg)}")

    # ③ 가계대출 용도별 — 십억원 → 조원
    r = fetch("151Y005", "200310" if FULL else start, END)
    hh = to_flat(r, lambda x: HH_USE.get(x.get("ITEM_NAME1")), scale=0.001)
    print(f"  151Y005 가계대출(용도별) {len(r):,}행 · 계열 {len(hh)}")

    # ④ 가계대출 업권별 — 십억원 → 조원
    r = fetch("151Y002", "200310" if FULL else start, END)
    ind = to_flat(r, lambda x: HH_IND.get(x.get("ITEM_NAME1")), scale=0.001)
    print(f"  151Y002 가계대출(업권별) {len(r):,}행 · 계열 {len(ind)}")

    raw = {
        "delq": merge(prev.get("delq", {}), delq),
        "dreg": merge(prev.get("dreg", {}), dreg),
        "hh":   merge(prev.get("hh", {}),   hh),
        "ind":  merge(prev.get("ind", {}),  ind),
    }
    if not any(raw.values()):
        print("  ! 수집 0건 — 기존 파일 유지"); return

    # ── 화면용 구조로 접기 ────────────────────────────────────────
    t_d, s_d = densify(raw["delq"])
    t_r, s_r = densify(raw["dreg"])
    t_h, s_h = densify(raw["hh"])
    t_i, s_i = densify(raw["ind"])

    # 지역별은 {종류:{지역:[...]}} 2단으로 — 프론트에서 종류 토글 + 지역 칩 선택
    dreg_out, regions = {}, []
    for k, arr in s_r.items():
        kind, reg = k.split("|", 1)
        dreg_out.setdefault(kind, {})[reg] = arr
        if reg not in regions:
            regions.append(reg)
    regions.sort(key=lambda x: SIDO.index(x) if x in SIDO else 99)

    # 전국 연체율은 141Y005 에 '전국'이 있으나 2019.12 부터다.
    # 그보다 긴 그림은 901Y054(은행전체)로 보여준다 — 두 지표는 기준이 달라(1일 vs 1개월)
    # 같은 차트에 섞지 않고 화면에서 탭으로 나눈다.
    delq_out = {}
    for k, arr in s_d.items():
        bank, kind = k.split("|", 1)
        delq_out.setdefault(bank, {})[kind] = arr

    doc = {
        "asof": NOW.strftime("%Y-%m-%d %H:%M"),
        "src": "한국은행 ECOS (901Y054·141Y005·151Y005·151Y002)",
        "delq":  {"t": t_d, "s": delq_out,
                  "note": "은행대출금 연체율(1일 이상) · 은행전체/일반/특수 × 기업·가계·신용카드"},
        "dreg":  {"t": t_r, "regions": regions, "s": dreg_out,
                  "note": "예금은행 지역별 연체율(1개월 이상) · 2019.12~"},
        "hh":    {"t": t_h, "s": s_h, "unit": "조원",
                  "note": "예금취급기관 가계대출(용도별) · 말잔"},
        "ind":   {"t": t_i, "s": s_i, "unit": "조원",
                  "note": "예금취급기관 가계대출(업권별) · 말잔"},
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    sz = OUT.stat().st_size / 1024
    print(f"  → {OUT} ({sz:,.0f}KB) · 연체율 {t_d[-1] if t_d else '—'} · 가계대출 {t_h[-1] if t_h else '—'}")


if __name__ == "__main__":
    main()
