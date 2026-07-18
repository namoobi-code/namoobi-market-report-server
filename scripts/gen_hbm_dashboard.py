# -*- coding: utf-8 -*-
# 3.1.9 반도체 주가 체크용 메모리+HBM 지표 대시보드 생성기 (v3.10.0 신규)
# 출력(cwd 상대): charts/hbm_dashboard.png
#   - 빌더(build_report.js renderKoreaExtras)가 ③그룹 첫 항목(3.1.9)에 imagePara 로 임베드.
#   - 파일이 없으면 빌더가 조용히 생략(imagePara→null) → 본 스크립트 실패해도 보고서는 깨지지 않음(비차단).
# 스타일: gen_capex_chart.py / gen_rest_charts.py 와 동일(NanumBarunGothic·슬레이트 팔레트, dpi150).
#
# ⚠️ 모든 수치는 '추정치'다. HBM 스팟가격·ASP·점유율은 무료 실시간 API 가 없어
#    HBMAgent 가 WebSearch+뉴스(TrendForce·각사 실적 컨센서스·언론)로 분기 추정치를 수집한다.
#    확인 불가 항목은 미표기(빈값)로 두며, 차트 상단·표 제목에 '추정' 을 명시한다.
# 데이터 우선순위: (1) nmr_hbm.json (HBMAgent 가 Phase 1 에 저장) → (2) report_data.markets.hbm
#    → (3) 내장 기본(예시) 값. 라이브 데이터가 있으면 해당 키만 오버라이드, 없으면 내장값.
import os, sys, glob, json, textwrap
from datetime import datetime
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import matplotlib.dates as mdates

# ---- 폰트(한글) ----
_cands=[os.path.join(os.path.dirname(__file__),"fonts","nmr_kr.ttf"),
        os.path.join(os.getcwd(),"fonts","nmr_kr.ttf"), os.environ.get("NMR_FONT","")]
_f=[p for p in _cands if p and os.path.exists(p)]
if not _f:
    _g=glob.glob("/sessions/*/mnt/**/namoobi-market-report/scripts/fonts/nmr_kr.ttf", recursive=True)
    _f=_g[:1]
if _f:
    fm.fontManager.addfont(_f[0]); matplotlib.rcParams["font.family"]="NanumBarunGothic"
matplotlib.rcParams["axes.unicode_minus"]=False
matplotlib.rcParams.update({"font.size":14,"axes.titlesize":20,"axes.labelsize":15,"xtick.labelsize":13.5,"ytick.labelsize":13.5,"legend.fontsize":12.5})

C_SPOT="#7C4DFF"; C_DDR5="#F5A623"; C_DDR4="#4A90E2"; C_NAND="#2E9E5B"
C_SHIP="#4A90E2"; C_MKT="#2E9E5B"; C_HBM3E="#F5A623"; C_HBM4="#7C4DFF"
C_SAMS="#4A90E2"; C_SK="#F5A623"; C_MICRON="#2E9E5B"; C_ETC="#9CA3AF"; C_GAP="#E2342E"
GRID=dict(alpha=0.18, linewidth=0.8)
LEG=dict(fontsize=12.5, frameon=True, framealpha=0.85, edgecolor="#E5E7EB", handletextpad=0.5, borderpad=0.4)

# ================= 내장 기본(예시·추정) =================
def _outdir():
    for a in sys.argv[1:]:
        if os.path.isdir(a): return a
    return os.environ.get("NMR_OUT") or "."

def _memdb():
    """(v3.59) 데이터 소스: ① db/memory.json (통합 DB — merge/서버 cron 이 매일 갱신)
                          ② WORK/nmr_memory.json (이번 회차 수집분)
    둘 다 없으면 차트 생략(비차단)."""
    O=_outdir()
    cands=[]
    for pat in (O+"/namoobi-market-report-server/db/memory.json",
                O+"/../namoobi-market-report-server/db/memory.json",
                "/sessions/*/mnt/claudeCowork/namoobi-market-report-server/db/memory.json"):
        cands += sorted(glob.glob(pat))
    for c in cands:
        try:
            d=json.load(open(c,encoding="utf-8"))
            return (d.get("data") or d), c
        except Exception: pass
    for c in sorted(glob.glob(O+"/nmr_memory.json")) + sorted(glob.glob("nmr_memory.json")):
        try: return json.load(open(c,encoding="utf-8")), c
        except Exception: pass
    return None, None

def _series(key):
    """db/series_mem_<key>.json 누적 시계열 → [(date, {item: val}), ...]"""
    O=_outdir()
    for pat in (O+"/namoobi-market-report-server/db/series_mem_%s.json"%key,
                O+"/../namoobi-market-report-server/db/series_mem_%s.json"%key,
                "/sessions/*/mnt/claudeCowork/namoobi-market-report-server/db/series_mem_%s.json"%key):
        for c in sorted(glob.glob(pat)):
            try:
                d=(json.load(open(c,encoding="utf-8")) or {}).get("data") or []
                return sorted(d, key=lambda r: r[0])
            except Exception: pass
    return []

# (req7 2026-07-17) 변동주기 라벨 — 그래프마다 명시(수집 주기가 아니라 값이 실제 바뀌는 주기)
CAD = {"dram_spot": "변동주기: 매일(영업일 18:10 GMT+8)", "dram_contract": "변동주기: 월 1회(매월 말)",
       "nand_spot": "변동주기: 주 1회 내외", "nand_contract": "변동주기: 월 1회(매월 말)",
       "gap": "변동주기: 매일(현물 분자)", "share": "변동주기: 분기 1회 내외(벤더 집계 발표 시)",
       "asp": "변동주기: 분기 1회 내외(신제품·계약 갱신 시)", "market": "변동주기: 연 1~2회(조사기관 전망 갱신)",
       "ddr5gap": "변동주기: 매일(DDR5 현물 분모)", "lead": "변동주기: 매일", "rs": "변동주기: 매일(주가) · EPS 컨센서스=수시"}

def _resample(ser, mode):
    """일별 [(date,{item:val})..] → 주별/월별 마지막 관측값."""
    if mode not in ("weekly", "monthly"): return ser
    from datetime import datetime as _dt
    out = {}
    for d, row in ser:
        t = _dt.strptime(d, "%Y-%m-%d")
        k = ("%d-W%02d" % t.isocalendar()[:2]) if mode == "weekly" else t.strftime("%Y-%m")
        out[k] = (d, row)  # 같은 버킷은 마지막 관측으로 덮음
    return [out[k] for k in sorted(out)]

def _backfill():
    """(req7 2026-07-17) 공개 보도치 백필 — db/mem_backfill.json (에이전트 리서치 시드)."""
    O = _outdir()
    for pat in (O + "/nmr_mem_backfill.json",
                O + "/namoobi-market-report-server/db/mem_backfill.json",
                "/sessions/*/mnt/claudeCowork/namoobi-market-report-server/db/mem_backfill.json"):
        for c in sorted(glob.glob(pat)):
            try:
                d = json.load(open(c, encoding="utf-8"))
                return d.get("data") or d
            except Exception:
                pass
    return {}

BF = _backfill()

D, SRC = _memdb()
if not D or not D.get("tables"):
    print("memory: 데이터 없음 — hbm_dashboard 차트 생략(비차단)")
else:
    T=D["tables"]; H=D.get("hbm") or {}
    PAL=[C_DDR5,C_DDR4,C_NAND,C_SPOT,C_SAMS,C_MICRON,C_ETC]

    def _style(ax):
        for sp in ("top","right"): ax.spines[sp].set_visible(False)
        ax.grid(**GRID)
    def _cap(ax, t, y=-0.27):
        ax.text(0,y,t,transform=ax.transAxes,fontsize=9,color="#666",va="top")

    def _trend(ax, key, title, ylab, mode="daily"):
        """(req7 v3.67) mode: daily=USD 라인 / index=지수화(첫날=100, 일직선 방지·최신 USD는 범례에)
        / weekly·monthly=버킷 마지막 관측 + monthly 는 보도치 백필 라인 병행."""
        ser=_series(key)
        t=T.get(key) or {}
        # 월별/주별 리샘플 + (monthly) 보도치 백필 오버레이
        if mode in ("weekly","monthly") and ser:
            rs=_resample(ser, mode)
            items=sorted({k for _,r in rs for k in r})
            bfmap = (BF.get("dram_contract_monthly") if key=="dram_contract" else
                     BF.get("nand_contract_monthly") if key=="nand_contract" else {}) or {}
            drew=False
            # ① 보도치 월별 라인 (계약가 이력 — TrendForce/DRAMeXchange 월말 보도)
            for j,(bfn,bfser) in enumerate(sorted(bfmap.items())):
                if not bfser: continue
                bx=[datetime.strptime(m+"-15","%Y-%m-%d") for m,_ in bfser]
                by=[v for _,v in bfser]
                ax.plot(bx,by,marker="s",ms=4,lw=1.6,ls="--",color=PAL[j%len(PAL)],label="%s (보도치)"%bfn)
                for xx,yy in [(bx[-1],by[-1])]:
                    ax.annotate("$%.2f"%yy,(xx,yy),textcoords="offset points",xytext=(4,4),fontsize=7)
                drew=True
            # ② 자체 누적(월/주 버킷 마지막 관측)
            for i,it in enumerate(items):
                pts=[(d,row.get(it)) for d,row in rs if row.get(it) is not None]
                if not pts: continue
                xs=[datetime.strptime(p[0],"%Y-%m-%d") for p in pts]
                ax.plot(xs,[p[1] for p in pts],marker="o",ms=5,lw=1.8,color=PAL[i%len(PAL)],
                        label=it if len(items)<=8 else None)
                drew=True
            if drew:
                ax.xaxis.set_major_formatter(mdates.DateFormatter("%y-%m" if mode=="monthly" else "%m-%d")); ax.margins(x=0.05)
                ax.legend(fontsize=6.2,frameon=False,ncol=2)
                ax.set_title("%s  (%s 축%s)"%(title, "월별" if mode=="monthly" else "주별",
                             " · 점선=보도치 백필" if (mode=="monthly" and bfmap) else ""),fontsize=13,fontweight="bold")
                ax.set_ylabel(ylab,fontsize=9); _style(ax)
                _cap(ax,"[실측] TrendForce 공개 가격표 · 갱신 %s · %s%s"%(t.get("last_update") or "", CAD.get(key,""),
                     "\n     점선=공개 보도치 백필(월말 고정가 보도) · 실선/점=자체 누적(2026-07-11~)" if (mode=="monthly" and bfmap) else ""))
                return
        if len(ser)>=2 and mode=="index":
            xs=[datetime.strptime(r[0],"%Y-%m-%d") for r in ser]
            items=sorted({k for r in ser for k in r[1]})
            for i,it in enumerate(items):
                v=[r[1].get(it) for r in ser]
                base=next((x for x in v if x),None)
                if not base: continue
                idx=[(x/base*100.0 if x else None) for x in v]
                last=next((x for x in reversed(v) if x),None)
                ax.plot(xs,idx,marker="o",ms=3.5,lw=1.7,color=PAL[i%len(PAL)],
                        label="%s  $%.2f"%(it,last) if last else it)
            ax.axhline(100,color="#888",lw=0.8,ls="--")
            ax.set_xticks(xs if len(xs)<=8 else xs[::max(1,len(xs)//7)])
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d")); ax.margins(x=0.06)
            ax.legend(fontsize=6.2,frameon=False,ncol=2)
            ax.set_title("%s  (지수화 100 · 누적 %d일)"%(title,len(ser)),fontsize=13,fontweight="bold")
            ax.set_ylabel("첫날=100",fontsize=9); _style(ax)
            _cap(ax,"[실측] TrendForce 공개 가격표 · 갱신 %s · %s\n     규격별 가격대(3~80달러)가 달라 USD 축에선 일직선처럼 보임 → 첫날=100 지수화(최신 달러값은 범례)"%(t.get("last_update") or "", CAD.get(key,"")))
            return
        if len(ser)>=2:
            xs=[datetime.strptime(r[0],"%Y-%m-%d") for r in ser]
            items=sorted({k for r in ser for k in r[1]})
            for i,it in enumerate(items):
                v=[r[1].get(it) for r in ser]
                ax.plot(xs,v,marker="o",ms=4,lw=1.8,color=PAL[i%len(PAL)],label=it)
            ax.set_xticks(xs if len(xs)<=8 else xs[::max(1,len(xs)//7)])
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
            ax.margins(x=0.06)
            ax.legend(fontsize=6.5,frameon=False,ncol=2)
            ax.set_title("%s  (누적 %d일)"%(title,len(ser)),fontsize=13,fontweight="bold")
        else:
            rows=t.get("rows") or []
            if not rows: ax.set_visible(False); return
            xs=range(len(rows)); vs=[r["avg"] for r in rows]
            ax.bar(xs,vs,width=0.55,color=[PAL[i%len(PAL)] for i in xs])
            for i,r in enumerate(rows):
                ax.text(i,r["avg"]*1.02,"%.1f"%r["avg"],ha="center",fontsize=8,fontweight="bold")
            ax.set_xticks(list(xs))
            ax.set_xticklabels([r["item"].replace(" (","\n(") for r in rows],fontsize=6.5)
            ax.set_ylim(top=max(vs)*1.2)
            ax.set_title("%s  (누적 1일 — 내일부터 추세선)"%title,fontsize=13,fontweight="bold")
        ax.set_ylabel(ylab,fontsize=9); _style(ax)
        _cap(ax,"[실측] TrendForce 공개 가격표 · 갱신 %s · %s"%(t.get("last_update") or "", CAD.get(key,"")))

    fig=plt.figure(figsize=(16.0,21.8), dpi=150)
    fig.suptitle("반도체 주가 체크용 메모리·HBM 지표 (가격·주가 실측 + ⑦⑧⑨ 공개 추정 환산)",
                 fontsize=21, fontweight="bold", y=0.988)
    fig.text(0.5, 0.966, "기준 %s · TrendForce 공개 가격표 + Silicon Analysts 공개 API + Yole(시장규모) + Yahoo Finance(선행지표)"%(D.get("asof") or ""),
             ha="center", fontsize=11, color="#666")
    gs=fig.add_gridspec(6,2, top=0.935, bottom=0.045, left=0.055, right=0.985,
                        hspace=0.95, wspace=0.22)

    _trend(fig.add_subplot(gs[0,0]),"dram_spot",    "① DRAM 현물(스팟)",   "USD", mode="index")
    _trend(fig.add_subplot(gs[0,1]),"dram_contract","② DRAM 고정거래(계약)","USD", mode="monthly")
    _trend(fig.add_subplot(gs[1,0]),"nand_spot",    "③ NAND 현물(스팟)",   "USD", mode="weekly")
    _trend(fig.add_subplot(gs[1,1]),"nand_contract","④ NAND 고정거래(계약)","USD", mode="monthly")

    # ⑤ 스팟 − 계약 갭 (핵심 선행지표 — 2026-07-13 req: 매일 변하는 지표이므로 일별 추세선)
    ax5=fig.add_subplot(gs[2,0])
    PAIRS5=[("DDR4 8Gb","DDR4 8Gb (1Gx8) 3200","DDR4 8Gb 1Gx8","dram_spot","dram_contract"),
           ("DDR4 16Gb","DDR4 16Gb (2Gx8) 3200","DDR4 16Gb 2Gx8","dram_spot","dram_contract"),
           ("NAND 64Gb","MLC 64Gb 8GBx8","NAND 64Gb 8Gx8 MLC","nand_spot","nand_contract"),
           ("NAND 32Gb","MLC 32Gb 4GBx8","NAND 32Gb 4Gx8 MLC","nand_spot","nand_contract")]
    SER5={k:_series(k) for k in ("dram_spot","dram_contract","nand_spot","nand_contract")}
    def _gap_series(si,ci,sk,ck):
        smap={r[0]:(r[1] or {}).get(si) for r in SER5[sk]}
        cmap={r[0]:(r[1] or {}).get(ci) for r in SER5[ck]}
        out=[]; last_c=None
        for d in sorted(set(list(smap))|set(list(cmap))):
            if cmap.get(d): last_c=cmap[d]
            sv=smap.get(d)
            if sv and last_c: out.append((d,(sv/last_c-1)*100.0))
        return out
    _drawn5=False; COLS5=[C_SK,C_SAMS,C_MICRON,C_ETC]
    for _i5,(l5,si,ci,sk,ck) in enumerate(PAIRS5):
        g5=_gap_series(si,ci,sk,ck)
        if len(g5)>=2:
            xs5=[datetime.strptime(d,"%Y-%m-%d") for d,_ in g5]; ys5=[v for _,v in g5]
            ax5.plot(xs5,ys5,marker="o",ms=3.2,lw=1.7,color=COLS5[_i5%4],label="%s %+.0f%%"%(l5,ys5[-1]))
            _drawn5=True
    if _drawn5:
        ax5.axhline(0,color="#888",lw=0.9)
        ax5.legend(fontsize=8.5,ncol=2,frameon=False,loc="center right")
        for lb in ax5.get_xticklabels(): lb.set_fontsize(8)
    else:
        g=lambda k: {r["item"]: r["avg"] for r in (T.get(k) or {}).get("rows",[])}
        ds,dc,ns,nc=g("dram_spot"),g("dram_contract"),g("nand_spot"),g("nand_contract")
        lab,val=[],[]
        for l5,si,ci,sk,ck in PAIRS5:
            S=ds if sk=="dram_spot" else ns; K=dc if ck=="dram_contract" else nc
            if si in S and ci in K and K[ci]: lab.append(l5); val.append((S[si]/K[ci]-1)*100)
        if val:
            ax5.bar(lab,val,width=0.5,color=[C_GAP if v>0 else C_DDR4 for v in val])
            for i,v in enumerate(val):
                ax5.text(i, v+(3 if v>0 else -7), "%+.0f%%"%v, ha="center", fontsize=11, fontweight="bold")
            ax5.axhline(0,color="#888",lw=0.9)
            ax5.set_ylim(min(val)*1.5 if min(val)<0 else 0, max(val)*1.28)
    ax5.set_title("⑤ 스팟-계약 갭 일별 추세 (계약가 인상 압력 선행지표)",fontsize=13,fontweight="bold")
    ax5.set_ylabel("%",fontsize=9); _style(ax5)
    _cap(ax5,"[계산] 현물÷계약-1 일별 추세(계약가는 월 1회 갱신 — 직전 갱신값 carry). 갭 확대=다음 계약 협상 인상 압력. %s\n     ※ NAND 32Gb 갭 0%% 부근은 정상 — 구형 저용량 규격은 현물 수요가 없어 현물≈계약. 시계열 누적 시작 2026-07-11"%CAD.get("gap",""))

    # ⑥ HBM 업체별 점유율 (실측)
    ax6=fig.add_subplot(gs[2,1])
    sh=H.get("share") or []
    bfq=BF.get("hbm_share_quarterly") or []
    _V6={"SK Hynix":C_SK,"SK hynix":C_SK,"Samsung":C_SAMS,"Micron":C_MICRON}
    if bfq:
        # (req7-⑥) 분기 추이 — 보도치 분기 시계열 + 최신 실측 포인트
        qs=[q for q,_ in bfq]
        for vd,cc in _V6.items():
            ys=[(row.get(vd) if isinstance(row,dict) else None) for _,row in bfq]
            if not any(y is not None for y in ys): continue
            ax6.plot(range(len(qs)),ys,marker="o",ms=5,lw=1.8,color=cc,label=vd)
        # 최신 실측(오늘) 포인트 추가
        for r in sh:
            vd=str(r.get("vendor") or ""); cc=_V6.get(vd)
            if cc and r.get("share_pct") is not None:
                ax6.scatter([len(qs)-0.7+1],[r["share_pct"]],color=cc,marker="D",s=42,zorder=5)
                ax6.annotate("%.0f%%"%r["share_pct"],(len(qs)+0.3,r["share_pct"]),fontsize=8,fontweight="bold",color=cc)
        ax6.set_xticks(list(range(len(qs)))+[len(qs)+0.3]); ax6.set_xticklabels(qs+["최신\n실측"],fontsize=7.5)
        ax6.legend(fontsize=7.5,frameon=False)
        ax6.set_title("⑥ HBM 업체별 점유율 — 분기 추이 (보도치+최신 실측)",fontsize=13,fontweight="bold")
    elif sh:
        nm=[r["vendor"] for r in sh]; vv=[r.get("share_pct") or 0 for r in sh]
        ax6.bar(nm,vv,width=0.5,color=[C_SAMS,C_SK,C_MICRON,C_ETC][:len(nm)])
        for i,v in enumerate(vv):
            ax6.text(i,v+1.2,"%.0f%%"%v,ha="center",fontsize=12,fontweight="bold")
        ax6.set_ylim(0,max(vv)*1.25)
        ax6.set_title("⑥ HBM 업체별 점유율 (최신 실측)",fontsize=13,fontweight="bold")
    else:
        ax6.set_visible(False)
    ax6.set_ylabel("%",fontsize=9); _style(ax6)
    _cap(ax6,"[실측+보도치] Silicon Analysts 공개 API(최신) · Counterpoint/TrendForce 분기 보도(추이) · %s · %s"%(D.get("asof") or "", CAD.get("share","")))

    # ⑦ HBM ASP 추이 (req10 2026-07-12 — docx에도 표시)
    ax7a=fig.add_subplot(gs[3,0])
    aser=_series("hbm_asp")
    # (req7-⑦) 오염 가드 — HBM 스택가($100 미만 값·비 HBM 항목은 단위붕괴/프록시 오염) 제거
    aser=[[d,{k:v for k,v in (row or {}).items() if str(k).startswith("HBM") and (v or 0)>=100}] for d,row in aser]
    aser=[r for r in aser if r[1]]
    # (2026-07-17 사용자 req) 분기 축 — ASP 는 분기 1회 내외 변동이라 일별 축은 일직선. 분기 마지막 관측만 표시.
    def _q(dstr):
        y,m=int(dstr[:4]),int(dstr[5:7]); return "%dQ%d"%(y,(m-1)//3+1)
    _qb={}
    for d,row in aser: _qb[_q(d)]=row   # 분기 내 마지막 관측
    qs=sorted(_qb)
    # (2026-07-17 사용자 req) 과거 추이 — 계약 ASP '보도치'(2024~2025) 병행. ⚠️ 현재 지표는 2026-06 시작
    #   '스팟가'라 기준이 다름(계약 대비 4~9배) → 하나의 선으로 잇지 않고 구분선·라벨로 분리 표기.
    bfa={q:row for q,row in (BF.get("hbm_asp_quarterly") or [])}
    bqs=sorted(bfa)
    if qs or bqs:
        cats=bqs+qs
        _pos={c:i for i,c in enumerate(cats)}
        _bfc=["#9CA3AF","#EF9F27","#8B5CF6","#64748B"]
        bitems=sorted({k for q in bqs for k in bfa[q]})
        for i,it in enumerate(bitems):
            pts=[(q,bfa[q][it]) for q in bqs if bfa[q].get(it)]
            if not pts: continue
            ax7a.plot([_pos[p[0]] for p in pts],[p[1] for p in pts],marker="s",ms=6,lw=1.4,ls="--",
                      mfc="white",color=_bfc[i%len(_bfc)],label="%s (계약 ASP·보도치)"%it)
            for q,v in pts:
                ax7a.annotate("$%s"%format(int(v),","),(_pos[q],v),textcoords="offset points",xytext=(0,-13),fontsize=7,color=_bfc[i%len(_bfc)])
        items=sorted({k for q in qs for k in _qb[q]})
        for i,it in enumerate(items):
            pts=[(q,_qb[q][it]) for q in qs if _qb[q].get(it)]
            if not pts: continue
            ax7a.plot([_pos[p[0]] for p in pts],[p[1] for p in pts],marker="o",ms=7,lw=1.8,color=PAL[i%len(PAL)],label="%s (스팟 지표)"%it)
            for q,v in pts:
                ax7a.annotate("$%s"%format(int(v),","),(_pos[q],v),textcoords="offset points",xytext=(6,5),fontsize=8,fontweight="bold")
        if bqs and qs:
            _dv=(_pos[qs[0]]+_pos[bqs[-1]])/2.0
            ax7a.axvline(_dv,color="#CBD5E1",lw=1.2,ls=":")
            ax7a.text(_dv-0.06,0.98,"계약 ASP 보도치(참고) ◀",transform=ax7a.get_xaxis_transform(),ha="right",va="top",fontsize=7.5,color="#94A3B8")
            ax7a.text(_dv+0.06,0.98,"▶ 스팟가 지표(2026-06 시작 · 기준 다름)",transform=ax7a.get_xaxis_transform(),ha="left",va="top",fontsize=7.5,color="#94A3B8")
        ax7a.set_xticks(range(len(cats))); ax7a.set_xticklabels(cats,fontsize=8)
        ax7a.margins(x=0.08,y=0.18); ax7a.legend(fontsize=6.8,frameon=False,loc="center left")
        ax7a.set_title("⑦ HBM ASP 추이 (USD/스택 · 분기 축) — 변동주기: 분기 1회 내외",fontsize=13,fontweight="bold")
    elif aser:
        it=aser[-1][1]; nm=list(it.keys()); vv=[it[k] for k in nm]
        ax7a.bar(nm,vv,width=0.5,color=[C_HBM3E,C_HBM4,C_SPOT][:len(nm)])
        for i,v in enumerate(vv): ax7a.text(i,v*1.02,"$%s"%format(int(v),","),ha="center",fontsize=9,fontweight="bold")
        ax7a.set_xticklabels(nm,fontsize=7.5); ax7a.set_ylim(top=max(vv)*1.2)
        ax7a.set_title("⑦ HBM ASP (USD/스택)  (누적 1일 — 매일 08:30 자동 누적)",fontsize=13,fontweight="bold")
    else: ax7a.set_visible(False)
    if aser or (BF.get("hbm_asp_quarterly") or []): ax7a.set_ylabel("USD",fontsize=9); _style(ax7a); _cap(ax7a,"[추정] 점선=계약 ASP 보도치(TrendForce·Silicon Analysts $/GB 표 환산 등 — 출처별 용량 가정 상이) · 실선=Silicon Analysts 스팟가 지표(2026-06-06 시작, 소급 불가) · %s\n     ⚠️ 두 구간은 서로 다른 가격 기준(계약 vs 스팟, 4~9배 레벨차)이라 연결하지 않음 — 점프는 가격 급등이 아니라 지표 교체"%CAD.get("asp",""))

    # ⑧ HBM 시장규모·수요 증가율 (req9 2026-07-12 — 연간, Yole 추정)
    ax8a=fig.add_subplot(gs[3,1])
    mser=_series("hbm_market")
    if mser:
        yrs=[r[0] for r in mser]; mv=[list(r[1].values())[0] for r in mser]
        ax8a.bar(yrs,mv,width=0.5,color=C_MKT)
        for i,v in enumerate(mv):
            ax8a.text(i,v*1.02,"$%dB"%v,ha="center",fontsize=11,fontweight="bold")
            if i>0 and mv[i-1]:
                ax8a.text(i,v*0.5,"+%.0f%% YoY"%((v/mv[i-1]-1)*100),ha="center",fontsize=9,color="white",fontweight="bold")
        # (req7-⑧) 이전 전망 빈티지 병행 — 전망치가 어떻게 상향/하향돼 왔는지 추세 비교
        vint=BF.get("hbm_market_vintage") or []
        _vc=["#9CA3AF","#F5A623","#7C4DFF","#E2342E"]
        def _yri(y): 
            import re as _re8
            m=_re8.search(r"\d{4}",str(y)); return int(m.group(0)) if m else 0
        _cats=sorted({str(y) for y in yrs} | {str(k) for _v in vint for k in (_v.get("forecast") or {})}, key=_yri)
        _pos={c:i for i,c in enumerate(_cats)}
        # 막대를 통합 카테고리 위치로 다시 그린다(정렬 어긋남 방지)
        ax8a.clear()
        ax8a.bar([_pos[str(y)] for y in yrs],mv,width=0.5,color=C_MKT)
        for _bi,(_y,_v0) in enumerate(zip(yrs,mv)):
            ax8a.text(_pos[str(_y)],_v0*1.02,"$%dB"%_v0,ha="center",fontsize=11,fontweight="bold")
            if _bi>0 and mv[_bi-1]:
                ax8a.text(_pos[str(_y)],_v0*0.5,"+%.0f%% YoY"%((_v0/mv[_bi-1]-1)*100),ha="center",fontsize=9,color="white",fontweight="bold")
        for _vi,_v in enumerate(vint):
            fc=_v.get("forecast") or {}
            ky=sorted(fc.keys(),key=_yri)
            if not ky: continue
            ax8a.plot([_pos[str(k)] for k in ky],[fc[k] for k in ky],marker="s",ms=5,lw=1.4,ls="--",color=_vc[_vi%len(_vc)],
                      label="%s %s 전망"%(_v.get("by",""),_v.get("published","")))
        ax8a.set_xticks(range(len(_cats))); ax8a.set_xticklabels(_cats)
        if vint: ax8a.legend(fontsize=7,frameon=False,loc="upper left")
        ax8a.set_ylim(top=max(mv)*1.22)
        ax8a.set_title("⑧ HBM 시장규모 · 수요 증가율 (연간 · 전망 빈티지 비교)",fontsize=13,fontweight="bold")
        ax8a.set_ylabel("십억 달러",fontsize=9); _style(ax8a)
        _cap(ax8a,"[추정] 막대=최신 전망(Yole·TrendForce) · 점선=과거 발표 시점별 전망(빈티지) — 상향 반복=수요 서프라이즈 지속. %s"%CAD.get("market",""))
    else: ax8a.set_visible(False)

    # ⑨ HBM:DDR5 GB당 단가 격차 (req12 2026-07-12 — 환산 추정, 매일 계산)
    ax9a=fig.add_subplot(gs[4,0])
    gser=_series("hbm_ddr5_gap")
    if len(gser)>=2:
        xs=[datetime.strptime(r[0],"%Y-%m-%d") for r in gser]
        ysS=[r[1].get("배율(현물)") for r in gser]
        ysC=[(r[1].get("배율(계약)") if r[1].get("배율(계약)") is not None else r[1].get("배율")) for r in gser]
        if any(v is not None for v in ysS):
            _lS=[v for v in ysS if v is not None]
            ax9a.plot(xs,ysS,marker="o",ms=5,lw=2.2,color=C_SPOT,label="vs DDR5 현물 %.1f배 (매일)"%_lS[-1])
        _lC=[v for v in ysC if v is not None]
        ax9a.plot(xs,ysC,marker="o",ms=4,lw=1.6,color=C_DDR4,ls="--",label=("vs DDR5 계약 %.1f배 (월1회 계단)"%_lC[-1]) if _lC else "vs 계약")
        ax9a.legend(fontsize=9,frameon=False)
        ax9a.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d")); ax9a.margins(x=0.06)
        ax9a.set_title("⑨ HBM : DDR5 GB당 단가 격차 (배) — 변동주기: 매일(DDR5 현물 분모)",fontsize=13,fontweight="bold")
    elif gser:
        g1=gser[-1][1]
        ax9a.bar(["HBM $/GB","DDR5 $/GB"],[g1.get("HBM $/GB") or 0,g1.get("DDR5 $/GB") or 0],width=0.45,color=[C_HBM3E,C_DDR4])
        for i,v in enumerate([g1.get("HBM $/GB") or 0,g1.get("DDR5 $/GB") or 0]):
            ax9a.text(i,v*1.02,"$%.1f"%v,ha="center",fontsize=11,fontweight="bold")
        ax9a.set_title("⑨ HBM : DDR5 GB당 단가 = %s배  (누적 1일 — 내일부터 추세선)"%(g1.get("배율") or "-"),fontsize=13,fontweight="bold")
    else: ax9a.set_visible(False)
    if gser: ax9a.set_ylabel("USD/GB · 배",fontsize=9); _style(ax9a)
    _cap(ax9a,"[환산 추정] HBM3E 스택 ASP÷용량 vs DDR5 $/GB. 실선=현물 분모(매일 변동)·점선=계약 분모(월1회 계단 — 일직선이 정상). %s\n     통상 5~6배 — 배율 급락 = 범용 DRAM 급등(삼성 상대 유리) 신호"%CAD.get("ddr5gap",""))

    # ─── (v3.60) 선행지표 2패널 ────────────────────────────────────────
    LD=D.get("leading") or {}

    # ⑩ 선행지표 1년 성과 — 수요처(NVDA) vs 공급자(MU) 괴리
    ax7=fig.add_subplot(gs[4,1])
    ORD=["SOX","NVDA","AMD","TSM","KOSPI","MU"]
    _c10={"SOX":C_ETC,"NVDA":C_DDR4,"AMD":C_HBM4,"TSM":C_NAND,"KOSPI":"#0EA5E9","MU":C_SK}
    _drew10=False
    for k in ORD:
        e=LD.get(k) or {}
        ser=e.get("series_1y") or []
        if len(ser)>=30:
            base=ser[0][1]
            if not base: continue
            xs=[datetime.strptime(d,"%Y-%m-%d") for d,_ in ser]
            ys=[v/base*100.0 for _,v in ser]
            _lw=2.4 if k in ("NVDA","MU") else 1.3
            ax7.plot(xs,ys,lw=_lw,color=_c10.get(k,"#999"),
                     label="%s %+.0f%%"%(e.get("label",k), e.get("chg_1y_pct") or (ys[-1]-100)))
            _drew10=True
    if _drew10:
        ax7.axhline(100,color="#888",lw=0.8,ls="--")
        ax7.xaxis.set_major_formatter(mdates.DateFormatter("%y-%m"))
        ax7.legend(fontsize=7,frameon=False,ncol=2,loc="upper left")
        ax7.set_title("⑩ 선행지표 1년 추이 — 수요처(NVDA) vs 공급자(MU) · 지수화 100",fontsize=13,fontweight="bold")
        ax7.set_ylabel("1년 전=100",fontsize=9); _style(ax7)
    else:
        # (폴백) 1년 시계열 미확보 회차 — 기존 1년 성과 막대
        ln=[LD[k]["label"] for k in ORD if LD.get(k) and LD[k].get("chg_1y_pct") is not None]
        lv=[LD[k]["chg_1y_pct"] for k in ORD if LD.get(k) and LD[k].get("chg_1y_pct") is not None]
        if lv:
            cols=[C_SPOT,C_DDR4,C_DDR5,C_NAND,C_ETC,C_SK][:len(lv)]
            ax7.bar(ln,lv,width=0.55,color=cols)
            for i,v in enumerate(lv):
                ax7.text(i, v+(max(lv)*0.02 if v>=0 else max(lv)*-0.05), "%+.0f%%"%v,
                         ha="center", fontsize=10, fontweight="bold")
            ax7.axhline(0,color="#888",lw=0.9)
            ax7.set_ylim(min(0,min(lv)*1.2), max(lv)*1.22)
            ax7.set_xticks(range(len(ln))); ax7.set_xticklabels(ln,fontsize=7.5)
            ax7.set_title("⑩ 선행지표 1년 성과 — 수요처(엔비디아) vs 공급자(마이크론)",fontsize=13,fontweight="bold")
            ax7.set_ylabel("%",fontsize=9); _style(ax7)
        else:
            ax7.set_visible(False)
    _cap(ax7,"[실측] Yahoo Finance 1년 일별(지수화 100) · SOX=업황 · NVDA·AMD=수요처 · TSM=CoWoS 병목 · MU=공급자 · %s\n     공급자(MU, 굵은 주황)가 수요처(NVDA, 굵은 파랑)를 크게 앞서면 = 메모리가 협상력을 쥔 공급부족 국면"%CAD.get("lead",""))

    # ⑪ 메모리/GPU 상대강도 — 가치 이동 신호 (누적 2일↑이면 추세선)
    ax8=fig.add_subplot(gs[5,0])
    fig.add_subplot(gs[5,1]).set_visible(False)
    rser=_series("mem_vs_gpu")
    rs=(LD.get("MEM_VS_GPU") or {}).get("value")
    if len(rser)>=2:
        xs=[datetime.strptime(r[0],"%Y-%m-%d") for r in rser]
        vs=[list(r[1].values())[0] for r in rser]
        ax8.plot(xs,vs,marker="o",ms=5,lw=2.2,color=C_GAP)
        ax8.axhline(1.0,color="#888",lw=1.0,ls="--")
        ax8.set_xticks(xs if len(xs)<=8 else xs[::max(1,len(xs)//7)])
        ax8.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
        ax8.margins(x=0.06)
        ax8.set_title("⑪ 메모리/GPU 상대강도 (MU÷NVDA)  (누적 %d일)"%len(rser),fontsize=13,fontweight="bold")
    elif rs is not None:
        ax8.barh([0],[rs],height=0.38,color=C_GAP if rs>1 else C_DDR4)
        ax8.axvline(1.0,color="#888",lw=1.2,ls="--")
        ax8.text(rs*1.03, 0, "%.2f배 → %s"%(rs,(LD.get("MEM_VS_GPU") or {}).get("signal","")),
                 va="center", fontsize=12, fontweight="bold", color=C_GAP if rs>1 else C_DDR4)
        ax8.set_xlim(0, max(1.4, rs*1.42))
        ax8.set_ylim(-0.62, 0.62)
        ax8.set_yticks([0]); ax8.set_yticklabels(["MU ÷ NVDA (1년)"], fontsize=9)
        ax8.text(1.0, 0.44, "균형선(1.0)", ha="center", fontsize=8, color="#888")
        ax8.set_xlabel("배", fontsize=9)
        ax8.set_title("⑪ 메모리/GPU 상대강도 (MU÷NVDA)  (누적 1일 — 내일부터 추세선)",fontsize=13,fontweight="bold")
    else:
        ax8.set_visible(False)
    if len(rser)>=2: ax8.set_ylabel("배",fontsize=9)
    _style(ax8)
    _cap(ax8,"[계산] 1년 상승률 비율. 1 초과 = 가치가 수요처(GPU)→공급자(메모리)로 이동 = 공급부족 심화 · %s\n     꺾이기 시작하면 공급부족 완화 = 사이클 고점 경계 신호"%CAD.get("rs",""))

    OUT="charts/hbm_dashboard.png"
    os.makedirs("charts",exist_ok=True)
    plt.savefig(OUT, dpi=150, facecolor="white"); plt.close()
    print("hbm dashboard -> %s (%d bytes) | src=%s"%(OUT, os.path.getsize(OUT), SRC))


def _semi_cycle_signals():
    """(req7 2026-07-12) 재설계 — 정량 미공개 신호(재고주수·CAPEX YoY)는 빈 그래프 대신
    '판정상태(안전/주의/경보) 타임라인'(db/series_semi_status.json, 매일 누적)으로 표시하고,
    정량이 있는 DRAM 계약가 QoQ 만 수치 그래프로 남긴다."""
    import json as _j, glob as _g, os as _os
    sc=None
    for _p in [_os.path.join(_outdir(),"nmr_semi_cycle.json")]+_g.glob("/sessions/*/mnt/claudeCowork/namoobi-market-report-server/db/semi_cycle.json"):
        try:
            _d=_j.load(open(_p,encoding="utf-8")); _d=_d.get("data",_d)
            if isinstance(_d,dict) and isinstance(_d.get("series"),dict): sc=_d; break
        except Exception: pass
    st=[]
    for _p in _g.glob("/sessions/*/mnt/claudeCowork/namoobi-market-report-server/db/series_semi_status.json")+[_os.path.join(_outdir(),"namoobi-market-report-server","db","series_semi_status.json")]:
        try:
            _d=_j.load(open(_p,encoding="utf-8")); st=(_d.get("data") or []); break
        except Exception: pass
    if not sc and not st: print("semi_cycle_signals: 데이터 없음 → 스킵"); return
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(13.2,3.6))
    # ① DRAM 계약가 QoQ (정량 실측·전망)
    pq=(sc or {}).get("series",{}).get("price_qoq") or {}
    ax=axes[0]; xs0=pq.get("labels",[]); ys=pq.get("values",[])
    xs=[str(l).split(" ")[0].split("(")[0] for l in xs0]   # 긴 라벨 → 분기 토큰만
    if xs and ys:
        cols=["#EF9F27" if "E" in x.upper().replace("Q","") else "#1D9E75" for x in xs]
        ax.bar(xs,ys,color=cols)
        for x,y in zip(xs,ys): ax.annotate(f"+{y}%",(x,y),textcoords="offset points",xytext=(0,3),fontsize=9,ha="center")
        ax.set_title("① DRAM 계약가 상승률 QoQ (%) — 초록=실측·주황=전망(E)",fontsize=10)
    else:
        ax.text(0.5,0.5,"데이터 미확보",ha="center",va="center",fontsize=9,color="#94A3B8"); ax.set_xticks([])
        ax.set_title("① DRAM 계약가 상승률 QoQ",fontsize=10)
    ax.grid(alpha=.25,axis="y")
    # ② 3신호 판정상태 타임라인 (안전=0/주의=1/경보=2 · 매일 누적)
    ax=axes[1]
    if st:
        from datetime import datetime as _dt2
        xs=[_dt2.strptime(r[0],"%Y-%m-%d") for r in st]
        KEYS=[("inventory","재고주수","#1D9E75"),("price_qoq","DRAM 계약가 QoQ","#EF9F27"),("capex_yoy","SK하이닉스 CAPEX YoY","#378ADD")]
        off={"inventory":0.06,"price_qoq":0.0,"capex_yoy":-0.06}
        for k,lab,c in KEYS:
            vs=[(r[1] or {}).get(k) for r in st]
            pts=[(x,v+off[k]) for x,v in zip(xs,vs) if v is not None]
            if pts: ax.step([p[0] for p in pts],[p[1] for p in pts],where="post",lw=2.0,color=c,label=lab,marker="o",ms=5)
        ax.set_yticks([0,1,2]); ax.set_yticklabels(["안전","주의","경보"]); ax.set_ylim(-0.4,2.4)
        ax.axhspan(1.5,2.4,color="#FEE2E2",alpha=0.5)
        ax.legend(fontsize=7.5,frameon=False,loc="upper left",ncol=1)
        import matplotlib.dates as _md2
        ax.xaxis.set_major_formatter(_md2.DateFormatter("%m-%d"))
        ax.set_title("② 3대 조기경보 판정상태 타임라인 (매일 관측·DB 누적 %d일)"%len(st),fontsize=10)
        ax.grid(alpha=.2,axis="x")
    else:
        ax.text(0.5,0.5,"판정 누적 시작 전",ha="center",va="center",fontsize=9,color="#94A3B8"); ax.set_xticks([])
        ax.set_title("② 3대 조기경보 판정상태 타임라인",fontsize=10)
    for ax in axes:
        for sp in ["top","right"]: ax.spines[sp].set_visible(False)
    fig.text(0.01,-0.04,"판정 근거: 재고주수=TrendForce·공급사 코멘트(정량 비공개→정성 판정) · QoQ=TrendForce 계약가 전망 · CAPEX=회사 가이던스/실적 — 2개 이상 '경보'면 고점·하강 신호",fontsize=7.5,color="#666")
    plt.tight_layout(); plt.savefig("charts/semi_cycle_signals.png",dpi=110,bbox_inches="tight"); plt.close()
    print("semi_cycle_signals OK (QoQ+판정 타임라인)")
try: _semi_cycle_signals()
except Exception as _e: print("semi_cycle_signals 실패(비차단):",_e)
