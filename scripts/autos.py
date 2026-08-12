#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""autos.py — 🚗 자동차 통계 4종 (공공 API 예시 · 부동산 탭 하단 데모)

기사(한경 2026081051041, 상용차 판매 28년 만의 최저) 검증용으로
"같은 주제를 4가지 공공 데이터 경로로 얻는" 예시를 만든다.

  ① KOSIS 공유서비스(REST·인증키)     — 자동차등록대수 시도별·차종별 (국토부 보고, 월간)
       orgId=116 tblId=DT_MLTM_5498 · 17개 시도 합 = 전국 (실측: 시군구 '계'=0001)
  ② data.go.kr 15059401(REST·인증키)  — 교통안전공단 신규등록 통계 (월간, 익월 2일)
       ※ 활용신청이 안 돼 있으면 SERVICE_KEY_IS_NOT_REGISTERED — err 로 기록만 한다
  ③ data.go.kr 15051118(파일·키 불필요) — 산업통상부 전체 자동차 산업 현황
       월간 내수판매(국산차)·수출량·수출금액, 2009.01~ (연 1회 갱신)
  ④ data.go.kr 15051116(파일·키 불필요) — 국내 및 세계 자동차 생산량(KAMA), 연간 2005~

산출: data/db/autos.json
  {asof, reg:{t,series:{승용|승합|화물|특수|총계:[대]}},
   newreg:{t,total:[건]} | {err},
   kama:{t,domestic:[대],export:[대],export_usd:[천달러]},
   world:{t,kr:[천대],world:[천대]}}

사용: autos.py            (cron 주 1회면 충분 — ①은 월간, ③④는 연간 갱신)
"""
import json, ssl, sys, time, urllib.parse, urllib.request
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
OUT  = BASE / "data" / "db" / "autos.json"
UA   = {"User-Agent": "Mozilla/5.0"}
CTX  = ssl.create_default_context()


def _key(name):
    """인증키 — 서버는 keys/, PC(코워크)는 SECURITY 폴더."""
    cands = [BASE / "keys" / name]
    cands += [Path("D:/claudeCowork/SECURITY") / name]
    cands += sorted(Path("/sessions").glob(f"*/mnt/claudeCowork/SECURITY/{name}"))
    for p in cands:
        try:
            k = Path(p).read_text(encoding="utf-8").strip()
            if k:
                return k
        except Exception:
            pass
    return None


def get(url, tries=3, timeout=90):
    for k in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            return urllib.request.urlopen(req, timeout=timeout, context=CTX).read()
        except urllib.error.HTTPError as e:
            body = b""
            try:
                body = e.read()
            except Exception:
                pass
            if body:                              # data.go.kr 는 에러 사유를 본문(XML)에 준다
                return body
            if k == tries - 1:
                raise
            time.sleep(2 * (k + 1))
        except Exception:
            if k == tries - 1:
                raise
            time.sleep(2 * (k + 1))


def num(v):
    s = str(v if v is not None else "").replace(",", "").strip()
    if s in ("", "-", "X", "x", "null", "None"):
        return None
    try:
        return int(round(float(s)))
    except Exception:
        return None


# ── ① KOSIS 자동차등록대수 (DT_MLTM_5498) ──────────────────────────────
def kosis_reg():
    key = _key("kosis.txt") or _key("kosis.kr.txt")
    if not key:
        return {"err": "KOSIS 키 없음"}
    API = "https://kosis.kr/openapi/Param/statisticsParameterData.do"
    KIND = [("0001", "승용"), ("0002", "승합"), ("0003", "화물"),
            ("0004", "특수"), ("0005", "총계")]
    start = "201101"
    end = datetime.now().strftime("%Y%m")
    series, months = {}, set()
    for code, name in KIND:                      # 차종별 5회 호출(호출당 17시도×월)
        q = {"method": "getList", "apiKey": key, "orgId": "116",
             "tblId": "DT_MLTM_5498", "itmId": "13103873443T4",   # 항목=계(관용+자가+영업)
             "objL1": "ALL",                                       # 시도 17개 전부
             "objL2": "13102873443B.0001",                         # 시군구=계
             "objL3": f"13102873443C.{code}",                      # 차종
             "format": "json", "jsonVD": "Y", "prdSe": "M",
             "startPrdDe": start, "endPrdDe": end}
        try:
            rows = json.loads(get(API + "?" + urllib.parse.urlencode(q)))
        except Exception as e:
            print(f"  ⚠ KOSIS {name} 실패: {e}")
            continue
        if isinstance(rows, dict):               # {"err":..}
            print(f"  ⚠ KOSIS {name}: {rows.get('errMsg')}")
            continue
        acc = {}                                  # ym → 17개 시도 합
        for r in rows:
            ym, v = str(r.get("PRD_DE") or ""), num(r.get("DT"))
            if ym and v is not None:
                acc[ym] = acc.get(ym, 0) + v
        series[name] = acc
        months |= set(acc)
        print(f"  KOSIS {name}: {len(acc)}개월")
        time.sleep(0.4)
    if not series:
        return {"err": "KOSIS 수집 실패"}
    t = sorted(months)
    return {"t": t, "series": {k: [v.get(m) for m in t] for k, v in series.items()}}


# ── ② 교통안전공단 신규등록 (15059401 — 활용신청 필요) ────────────────
def newreg():
    import xml.etree.ElementTree as ET
    key = _key("data.go.kr.txt")
    if not key:
        return {"err": "data.go.kr 키 없음"}
    EP = ("https://apis.data.go.kr/B553881/newRegistlnfoService_02/"
          "getnewRegistlnfoService02")
    now = datetime.now()
    t, total = [], []
    for back in range(36, 0, -1):                 # 최근 36개월
        y, m = divmod((now.year * 12 + now.month - 1) - back, 12)
        ym = f"{y}{m+1:02d}"
        url = f"{EP}?serviceKey={key}&registYy={y}&registMt={m+1:02d}&numOfRows=999&pageNo=1"
        try:
            raw = get(url, tries=2, timeout=60)
        except Exception as e:
            return {"t": t, "total": total} if t else {"err": f"호출 실패: {e}"}
        txt = raw.decode("utf-8", "replace")
        if "SERVICE_KEY_IS_NOT_REGISTERED" in txt:
            return {"err": "활용신청 필요 — data.go.kr 15059401 에서 이 API 활용신청 후 자동 수집됩니다"}
        if "SERVICETIMEOUT" in txt:               # 제공기관(교통안전공단) 응답 없음 — 흔한 야간 장애
            return ({"t": t, "total": total} if t else
                    {"err": "제공기관 응답 없음(SERVICETIMEOUT) — 활용신청은 완료됨, 매일 07:35 자동 재시도"})
        if "SERVICE ERROR" in txt or "LIMITED_NUMBER" in txt:
            return {"t": t, "total": total} if t else {"err": txt[:160]}
        try:
            root = ET.fromstring(txt)
        except Exception:
            return {"err": "XML 파싱 실패: " + txt[:120]}
        s = 0
        for it in root.iter():                    # 건수형 필드 합산(스키마 미공개 → 방어적)
            tag = it.tag.lower()
            if tag.endswith(("co", "cnt", "count")) and it.text and it.text.strip().isdigit():
                s += int(it.text)
        t.append(ym)
        total.append(s or None)
        time.sleep(0.2)
    return {"t": t, "total": total}


# ── ③ 산업통상부 전체 자동차 산업 현황 (월간 CSV — 키 불필요) ─────────
def kama_csv():
    url = ("https://www.data.go.kr/cmm/cmm/fileDownload.do"
           "?atchFileId=FILE_000000003636716&fileDetailSn=1")
    raw = get(url)
    txt = raw.decode("utf-8-sig", "replace")
    t, dom, exp, usd = [], [], [], []
    for ln in txt.splitlines()[1:]:
        c = [x.strip() for x in ln.split(",")]
        if len(c) < 4 or "-" not in c[0]:
            continue
        t.append(c[0].replace("-", ""))          # YYYYMM (프론트 fm() 규격)
        dom.append(num(c[1])); exp.append(num(c[2])); usd.append(num(c[3]))
    print(f"  KAMA 월간: {len(t)}개월 ({t[0]}~{t[-1]})" if t else "  ⚠ KAMA CSV 비어있음")
    return {"t": t, "domestic": dom, "export": exp, "export_usd": usd}


# ── ④ 국내 및 세계 자동차 생산량 (연간 CSV — 키 불필요) ───────────────
def world_csv():
    url = ("https://www.data.go.kr/cmm/cmm/fileDownload.do"
           "?atchFileId=FILE_000000003635464&fileDetailSn=1")
    raw = get(url)
    try:
        txt = raw.decode("cp949")
    except UnicodeDecodeError:
        txt = raw.decode("utf-8-sig", "replace")
    t, kr, wd = [], [], []
    for ln in txt.splitlines()[1:]:
        c = [x.strip() for x in ln.split(",")]
        if len(c) < 3 or not c[0][:4].isdigit():
            continue
        t.append(c[0][:4]); kr.append(num(c[1])); wd.append(num(c[2]))
    print(f"  세계생산 연간: {len(t)}년 ({t[0]}~{t[-1]})" if t else "  ⚠ 세계생산 CSV 비어있음")
    return {"t": t, "kr": kr, "world": wd}


def main():
    out = {"asof": datetime.now().strftime("%Y-%m-%d %H:%M"),
           "src": {"reg": "KOSIS DT_MLTM_5498(국토부 자동차등록현황보고, 월간)",
                   "newreg": "data.go.kr 15059401(교통안전공단 신규등록, 월간)",
                   "kama": "data.go.kr 15051118(산업통상부, 월간 CSV)",
                   "world": "data.go.kr 15051116(산업통상부·KAMA, 연간 CSV)"}}
    print("[autos] ① KOSIS 등록대수")
    out["reg"] = kosis_reg()
    print("[autos] ② 신규등록(15059401)")
    out["newreg"] = newreg()
    if "err" in out["newreg"]:
        print("  ⚠", out["newreg"]["err"])
    else:
        print(f"  신규등록: {len(out['newreg']['t'])}개월")
    print("[autos] ③ KAMA 월간 내수·수출")
    out["kama"] = kama_csv()
    print("[autos] ④ 세계 생산량(연간)")
    out["world"] = world_csv()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")),
                   encoding="utf-8")
    print(f"[autos] ✅ → {OUT}")


if __name__ == "__main__":
    main()
