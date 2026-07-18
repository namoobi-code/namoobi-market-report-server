#!/usr/bin/env python3
# 3.1.10 관세청_수출 주요품목별 10일 단위 잠정치 통계 (data.go.kr 15157908)
# 정책(Big-Arch): 매일 '저렴한 변경체크'만 수행 → 변경(신규 순보 또는 최근월 현행화) 시에만 전체 백필.
#   변경 없으면 아무 것도 쓰지 않음(merge 가 DB값 재사용, 기존 차트 유지).
# 출력(변경 시): <WORK>/nmr_customs.json  (merge.py 가 db/customs.json 으로 동기화)
# stdlib 전용(urllib, ElementTree) — 리포트 Phase 1 bash 병렬 실행용.
import sys, os, json, glob, hashlib
import urllib.request, urllib.parse
import datetime as dt
import xml.etree.ElementTree as ET

ENDPOINT = "https://apis.data.go.kr/1220000/prlstMmUtPrviExpAcrs/getPrlstMmUtPrviExpAcrs"
DATA_START = "201601"
ITEMS = [("itemUsdAmt00","total"),("itemUsdAmt01","semiconductor"),("itemUsdAmt02","steel"),
         ("itemUsdAmt03","car"),("itemUsdAmt04","petroleum"),("itemUsdAmt05","wireless"),
         ("itemUsdAmt06","ship"),("itemUsdAmt07","autoparts"),("itemUsdAmt08","computer"),
         ("itemUsdAmt09","precision"),("itemUsdAmt10","appliance")]

def find_key():
    for p in (glob.glob("/sessions/*/mnt/claudeCowork/SECURITY/data.go.kr.txt") +
              glob.glob("/sessions/*/mnt/*/SECURITY/data.go.kr.txt")):
        try:
            k=open(p,encoding="utf-8").read().strip()
            if k: return k
        except Exception: pass
    k=os.environ.get("DATA_GO_KR_KEY","").strip()
    if k: return k
    raise SystemExit("[customs] 인증키 없음: SECURITY/data.go.kr.txt")

def work_dir():
    a=[x for x in sys.argv[1:] if not x.startswith("-")]
    if a and os.path.isdir(a[0]): return a[0]
    if os.environ.get("NMR_OUT"): return os.environ["NMR_OUT"]
    g=sorted(glob.glob("/sessions/*/mnt/outputs"))
    return g[-1] if g else "."

def db_dir():
    for b in (glob.glob("/sessions/*/mnt/claudeCowork/namoobi-market-report-server") or
              glob.glob("/sessions/*/mnt/outputs/namoobi-market-report-server") or
              glob.glob("/sessions/*/mnt/claudeCowork/namoobi-market-report-server/data") or
              glob.glob("/sessions/*/mnt/outputs/_market_report_data")):
        d=os.path.join(b,"db"); 
        if os.path.isdir(d): return d
    return None

def _int(v):
    if v is None: return None
    s=v.replace(",","").replace(" ","").strip()
    return int(s) if s.lstrip("-").isdigit() else None
def _seq(pd):
    try: e=int(str(pd).split("~")[1])
    except Exception: return 3
    return 1 if e<=10 else (2 if e<=20 else 3)
def ym_add(ym,n):
    y,m=int(ym[:4]),int(ym[4:6]); i=y*12+(m-1)+n; return f"{i//12:04d}{i%12+1:02d}"
def cur_ym():
    t=dt.date.today(); return f"{t.year:04d}{t.month:02d}"

def api(key,s,e):
    qs=urllib.parse.urlencode({"serviceKey":key,"strtYymm":s,"endYymm":e,"pageNo":1,"numOfRows":2000})
    req=urllib.request.Request(ENDPOINT+"?"+qs, headers={"User-Agent":"nmr-customs/1.0"})
    with urllib.request.urlopen(req, timeout=40) as r:
        txt=r.read().decode("utf-8","replace")
    if txt.strip().lower().startswith("unauthorized"):
        raise SystemExit("[customs] 401 Unauthorized: 인증키 미활성/승인전")
    root=ET.fromstring(txt)
    code=root.findtext(".//resultCode")
    if code not in (None,"00"):
        raise SystemExit(f"[customs] API 오류 {code}: {root.findtext('.//resultMsg')}")
    out=[]
    for it in root.iter("item"):
        pd=(it.findtext("priodDt") or "").strip()
        rec={"yyyymm":(it.findtext("priodMon") or "").strip(),"seq":_seq(pd),"period":pd}
        for f,c in ITEMS: rec[c]=_int(it.findtext(f))
        out.append(rec)
    return out

def collect(key,start,end):
    rows=[]; s=start
    while s<=end:
        e=ym_add(s,9*12-1); e=end if e>end else e
        rows+=api(key,s,e); s=ym_add(e,1)
    # 중복 제거(청크 경계) + 정렬
    seen={}; 
    for r in rows: seen[(r["yyyymm"],r["seq"])]=r
    return [seen[k] for k in sorted(seen)]

def marker_of(rows, months=4):
    """최근 N개월(모든 순보) 레코드 해시 — 신규 순보/최근월 현행화 감지."""
    if not rows: return "empty"
    yms=sorted({r["yyyymm"] for r in rows})[-months:]
    recent=[r for r in rows if r["yyyymm"] in yms]
    recent.sort(key=lambda r:(r["yyyymm"],r["seq"]))
    blob=json.dumps(recent, ensure_ascii=False, sort_keys=True)
    return sorted(yms)[-1]+"|"+hashlib.sha1(blob.encode("utf-8")).hexdigest()[:12]

def build(rows):
    months=sorted({r["yyyymm"] for r in rows})
    idx={(r["yyyymm"],r["seq"]):r for r in rows}
    def series(col):
        out={"p10":[],"p20":[],"pm":[]}
        for ym in months:
            out["p10"].append((idx.get((ym,1)) or {}).get(col))
            out["p20"].append((idx.get((ym,2)) or {}).get(col))
            out["pm"].append((idx.get((ym,3)) or {}).get(col))
        return out
    latest_ym=months[-1]
    lat={s:idx.get((latest_ym,s)) for s in (1,2,3)}
    return {
        "months":[f"{m[:4]}-{m[4:6]}" for m in months],
        "series":{"total":series("total"),"semiconductor":series("semiconductor")},
        "rows":rows,
        "latest":{"yyyymm":latest_ym,
                  "p10":lat.get(1),"p20":lat.get(2),"pm":lat.get(3)},
        "unit":"천 달러","source":"관세청 · data.go.kr(15157908)",
    }

def main():
    key=find_key(); WORK=work_dir(); DD=db_dir()
    # 1) 저렴한 변경체크: 최근 4개월만 조회
    recent=collect(key, ym_add(cur_ym(),-4), cur_ym())
    new_marker=marker_of(recent)
    prior=None
    if DD and os.path.exists(os.path.join(DD,"customs.json")):
        try: prior=json.load(open(os.path.join(DD,"customs.json"),encoding="utf-8")).get("marker")
        except Exception: prior=None
    if prior and prior==new_marker:
        print(f"[customs] reuse — 변경없음(marker {new_marker}) · 기존 DB·차트 유지")
        return
    # 2) 변경 감지 → 전체 백필
    rows=collect(key, DATA_START, cur_ym())
    data=build(rows); data["marker"]=marker_of(rows); data["as_of"]=dt.date.today().isoformat()
    outp=os.path.join(WORK,"nmr_customs.json")
    json.dump(data, open(outp,"w",encoding="utf-8"), ensure_ascii=False)
    print(f"[customs] due{'(신규 DB)' if not prior else ''} → 백필 {len(rows)}건 "
          f"({data['months'][0]}~{data['months'][-1]}), 최신 {data['latest']['yyyymm']} → {outp}")

if __name__=="__main__":
    main()
