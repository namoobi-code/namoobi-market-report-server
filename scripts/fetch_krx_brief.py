#!/usr/bin/env python3
# fetch_krx_brief.py — 3.2.4 KRX 증시 Brief / 3.2.5 공매도 데일리 브리프 (v3.54 신설 — DB화)
# open.krx.co.kr 시장동향>종합시황(MKD01010000) 게시판에서 최신 'KRX 증시 Brief'와
# '공매도 데일리 브리프' PDF를 내려받아 페이지별 PNG 캡쳐를 만든다 (sandbox·stdlib·Chrome 불필요).
#
# [DB화 — Big-Arch] 회차 마커 = 게시글 att_seq.
#   - 영구 저장소: <connected>/namoobi-market-report-server/data/krx_brief/<key>_<att_seq>/ (원본 pdf + 페이지 PNG)
#   - DB:          <connected>/namoobi-market-report-server/db/krx_brief.json (marker="krx:<seq>|short:<seq>")
#   - 마커 불변(기존꺼랑 같음) → 다운로드·캡쳐 생략, 저장본 PNG 를 charts/ 로 복사(재사용).
#   - 마커 변경(신규 회차)   → PDF 다운로드 → pdftocairo(폴백 pdftoppm) PNG 캡쳐 → 영구 저장 + charts/ 복사.
#
# API 체인 (2026-07-09 실측 — 쿠키·로그인 불필요):
#   1) 목록:   GET  /contents/COM/GenerateOTP.jspx?bld=MKD/01/0101/01010000/mkd01010000_01&name=list → OTP
#              POST /contents/OPN/99/OPN99000001.jspx?code=<OTP>  body: market=ALL&word=ALL&sch_word=&
#                   fromdate=YYYYMMDD&todate=YYYYMMDD&cycle=ALL&pagePath=<jsp>&curPage=1&pageSize=20
#              → {"block1":[{ttl,att_seq,fst_opdt,market,cycl,...}]} (최신순)
#   2) 첨부:   GET  GenerateOTP.jspx?bld=.../mkd01010000_03&name=attach → OTP
#              POST OPN99000001.jspx?code=<OTP>  body: seq=<att_seq>
#              → {"block1":[{file_seq,file_nm,file_path,save_file_nm}]}
#   3) 다운로드: GET GenerateOTP.jspx?name=fileDown&filetype=att&url=MKD/01/0101/01010000/mkd01010000_03&seq=<att_seq>&file_seq=<n> → OTP
#              POST https://file.krx.co.kr/download.jspx  body: code=<OTP> → PDF bytes
#
# Usage: python3 fetch_krx_brief.py [$WORK]
# 산출: $WORK/nmr_krx_brief.json + $WORK/charts/krx_brief_p*.png / short_brief_p*.png
# 실패 시 비차단: 항목별 독립 — 실패 항목은 DB 폴백(있으면), 둘 다 없으면 산출 생략(빌더 섹션 자동 생략).
import sys, os, glob, json, re, shutil, subprocess, datetime
import urllib.request, urllib.parse

BASE = 'https://open.krx.co.kr'
JSP  = '/contents/MKD/01/0101/01010000/MKD01010000.jsp'
BLD  = 'MKD/01/0101/01010000/mkd01010000_%s'
HDRS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)', 'Referer': BASE + JSP}
ITEMS = [  # (key, 제목 매칭 정규식, charts/ 파일 접두어, 보고서 섹션)
    ('krx',   re.compile(r'KRX\s*증시\s*Brief', re.I), 'krx_brief',   '3.2.4'),
    ('short', re.compile(r'공매도\s*데일리\s*브리프'), 'short_brief', '3.2.5'),
]

def http(url, data=None, binary=False, timeout=25):
    req = urllib.request.Request(url, data=(urllib.parse.urlencode(data).encode() if data is not None else None), headers=HDRS)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        b = r.read()
    return b if binary else b.decode('utf-8', 'replace')

def otp(params):
    return http(BASE + '/contents/COM/GenerateOTP.jspx?' + urllib.parse.urlencode(params))

def api(bld_suffix, name, body):
    code = otp({'bld': BLD % bld_suffix, 'name': name})
    return json.loads(http(BASE + '/contents/OPN/99/OPN99000001.jspx?code=' + urllib.parse.quote(code), data=body))

def work_dir():
    if len(sys.argv) > 1 and sys.argv[1].strip():
        return sys.argv[1].rstrip('/')
    return (glob.glob('/sessions/*/mnt/outputs') or ['.'])[0] + '/nmr_build'

def store_base():
    for pat in ('/sessions/*/mnt/claudeCowork/namoobi-market-report-server/data', '/sessions/*/mnt/outputs/_market_report_data'):
        g = glob.glob(pat)
        if g: return g[0]
    d = (glob.glob('/sessions/*/mnt/outputs') or ['.'])[0] + '/_market_report_data'
    os.makedirs(d, exist_ok=True); return d

def pdf_to_pngs(pdf, outdir, prefix):
    """pdftocairo(폴백 pdftoppm) -r 110 → [outdir/<prefix>_p1.png, ...]"""
    tmp = os.path.join(outdir, '_cap')
    for f in glob.glob(os.path.join(outdir, prefix + '_p*.png')): os.remove(f)
    for tool in (['pdftocairo', '-png', '-r', '110', pdf, tmp], ['pdftoppm', '-png', '-r', '110', pdf, tmp]):
        try:
            if subprocess.run(tool, capture_output=True, timeout=120).returncode == 0:
                pages = sorted(glob.glob(tmp + '*.png'))
                if pages: break
        except Exception: pages = []
    else: pages = sorted(glob.glob(tmp + '*.png'))
    out = []
    for i, p in enumerate(pages, 1):
        dst = os.path.join(outdir, '%s_p%d.png' % (prefix, i)); shutil.move(p, dst); out.append(dst)
    return out

def main():
    W = work_dir(); charts = os.path.join(W, 'charts')
    os.makedirs(charts, exist_ok=True)
    sb = store_base(); store = os.path.join(sb, 'krx_brief')
    # DB 정본은 서버코드 저장소 db/ (원본 PDF·PNG 는 계속 _market_report_data/krx_brief/)
    _sv = glob.glob('/sessions/*/mnt/claudeCowork/namoobi-market-report-server')
    dbp = os.path.join((_sv[0] if _sv else sb), 'db', 'krx_brief.json')
    os.makedirs(store, exist_ok=True); os.makedirs(os.path.dirname(dbp), exist_ok=True)
    try: db = json.load(open(dbp, encoding='utf-8'))
    except Exception: db = {}
    old = (db.get('data') or {}) if isinstance(db, dict) else {}

    today = datetime.date.today(); frm = (today - datetime.timedelta(days=14)).strftime('%Y%m%d')
    rows = []
    try:
        rows = api('01', 'list', {'market': 'ALL', 'word': 'ALL', 'sch_word': '', 'fromdate': frm,
                                  'todate': today.strftime('%Y%m%d'), 'cycle': 'ALL', 'pagePath': JSP,
                                  'curPage': '1', 'pageSize': '20'}).get('block1') or []
    except Exception as e:
        sys.stderr.write('krx_brief: 목록 조회 실패(%s) — DB 폴백 시도\n' % e)

    result = {}
    for key, pat, prefix, sec in ITEMS:
        prev = old.get(key) or {}
        row = next((r for r in rows if pat.search(str(r.get('ttl') or ''))), None)
        seq = str(row.get('att_seq') or '') if row else ''
        item_dir = os.path.join(store, '%s_%s' % (key, seq)) if seq else ''
        try:
            if row and seq and seq == str(prev.get('att_seq') or '') and glob.glob(os.path.join(store, '%s_%s' % (key, seq), prefix + '_p*.png')):
                # 기존꺼랑 같음 → 재사용 (다운로드·캡쳐 생략)
                pages = sorted(glob.glob(os.path.join(store, '%s_%s' % (key, seq), prefix + '_p*.png')))
                result[key] = dict(prev, reused=True)
                print('%s %s: 회차 불변(att_seq=%s) → 저장본 재사용 (%d쪽)' % (sec, key, seq, len(pages)))
            elif row and seq:
                # 신규 회차 → 다운로드 + 캡쳐
                att = api('03', 'attach', {'seq': seq}).get('block1') or []
                if not att: raise RuntimeError('첨부파일 목록 없음(seq=%s)' % seq)
                fseq = str(att[0].get('file_seq') or '1')
                code = otp({'name': 'fileDown', 'filetype': 'att', 'url': BLD % '03', 'seq': seq, 'file_seq': fseq})
                pdf_bytes = http('https://file.krx.co.kr/download.jspx', data={'code': code}, binary=True)
                if not pdf_bytes.startswith(b'%PDF'): raise RuntimeError('PDF 아님(%dB)' % len(pdf_bytes))
                os.makedirs(item_dir, exist_ok=True)
                pdfp = os.path.join(item_dir, prefix + '.pdf'); open(pdfp, 'wb').write(pdf_bytes)
                pages = pdf_to_pngs(pdfp, item_dir, prefix)
                if not pages: raise RuntimeError('PNG 캡쳐 실패')
                result[key] = {'title': str(row.get('ttl') or ''), 'date': str(row.get('fst_opdt') or ''),
                               'att_seq': seq, 'pages': len(pages), 'file_nm': str(att[0].get('file_nm') or ''), 'reused': False}
                # 이전 회차 저장소 정리(항목별 최근 5개 유지)
                dirs = sorted(glob.glob(os.path.join(store, key + '_*')), key=os.path.getmtime)
                for d in dirs[:-5]: shutil.rmtree(d, ignore_errors=True)
                print('%s %s: 신규 회차(att_seq=%s) 다운로드·캡쳐 완료 (%d쪽)' % (sec, key, seq, len(pages)))
            else:
                raise RuntimeError('최근 14일 목록에서 미발견')
        except Exception as e:
            sys.stderr.write('krx_brief %s: %s\n' % (key, e))
            if prev.get('att_seq') and glob.glob(os.path.join(store, '%s_%s' % (key, prev['att_seq']), prefix + '_p*.png')):
                result[key] = dict(prev, reused=True, stale_note='이번 실행 수집 실패 — 직전 회차(DB) 유지')
                print('%s %s: 수집 실패 → DB 직전 회차 폴백(att_seq=%s)' % (sec, key, prev['att_seq']))
            else:
                result[key] = None
        # charts/ 복사 (재사용·신규 공통 — 빌더는 charts/<prefix>_p*.png 만 본다)
        it = result.get(key)
        if it and it.get('att_seq'):
            src = sorted(glob.glob(os.path.join(store, '%s_%s' % (key, it['att_seq']), prefix + '_p*.png')))
            for s in src: shutil.copy2(s, os.path.join(charts, os.path.basename(s)))
            it['pages'] = len(src)

    ok = {k: v for k, v in result.items() if v}
    if not ok:
        sys.stderr.write('krx_brief: 두 항목 모두 실패 — 산출 생략(섹션 자동 생략)\n'); return 0
    out = {'asof': today.isoformat(),
           'source': '한국거래소 KRX 시장 > 시장동향 > 종합시황',
           'source_url': BASE + JSP}
    out.update({k: v for k, v in result.items()})
    json.dump(out, open(os.path.join(W, 'nmr_krx_brief.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    marker = 'krx:%s|short:%s' % (((result.get('krx') or {}).get('att_seq') or ''), ((result.get('short') or {}).get('att_seq') or ''))
    json.dump({'marker': marker, 'as_of': today.isoformat(), 'data': {k: v for k, v in result.items() if v}},
              open(dbp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('nmr_krx_brief.json 저장 완료 (marker=%s)' % marker)
    return 0

if __name__ == '__main__':
    sys.exit(main())
# EOF — fetch_krx_brief.py
