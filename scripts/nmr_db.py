#!/usr/bin/env python3
# nmr_db.py - 범용 비매일 지표 DB (Big-Arch v1.0). 섹션 무관 저장/변동체크/재사용.
# 정책: 발표주기가 매일이 아닌 모든 지표는 DB(파일)에 저장하고, 매 실행 '변동 여부만' 관측해
#       변동(marker 변경)이 있을 때만 재조사·갱신, 없으면 DB값을 그대로 재사용한다.
# DB: <connected>/namoobi-market-report-server/db/<item>.json = {"marker":..,"as_of":"YYYY-MM-DD","data":..}
#     (2026-07-12 이전: _market_report_data/db — 서버 코드 저장소로 이전해 git 버전관리·백업까지 함께 된다.
#      구 경로는 읽기 폴백으로만 남긴다.)
# Usage:
#   nmr_db.py check  <item> <observed_marker> [dbdir]   -> {status:reuse|due, reason, as_of}
#   nmr_db.py get    <item> [dbdir]                       -> data JSON (stdout)
#   nmr_db.py set    <item> <as_of> <marker> [dbdir]      (data JSON on stdin)
#   nmr_db.py upsert <item> <as_of> <marker> <keyfield> [dbdir]  (list[dict] on stdin; merge by keyfield - 누적형)
#   nmr_db.py list   [dbdir]                              -> 각 item marker/as_of 요약
import sys, json, os, glob

# DB 정본 = 서버코드 저장소 안의 db/  (D:\claudeCowork\namoobi-market-report-server\db)
DBROOT_NAME = 'namoobi-market-report-server'
LEGACY_NAME = '_market_report_data'          # 구 위치 — 읽기 폴백 전용

def _dbdir(arg=None):
    if arg:
        os.makedirs(arg, exist_ok=True); return arg
    # 1) 정본
    for pat in ('/sessions/*/mnt/claudeCowork/%s' % DBROOT_NAME,
                '/sessions/*/mnt/outputs/%s' % DBROOT_NAME):
        for base in sorted(glob.glob(pat)):
            d = os.path.join(base, 'db')
            try: os.makedirs(d, exist_ok=True)
            except Exception: pass
            return d
    # 2) 레거시 폴백 (구 DB 가 아직 남아 있는 환경)
    for pat in ('/sessions/*/mnt/claudeCowork/%s/db' % LEGACY_NAME,
                '/sessions/*/mnt/outputs/%s/db' % LEGACY_NAME):
        for d in sorted(glob.glob(pat)):
            sys.stderr.write('nmr_db: ⚠️ 레거시 DB 경로 사용 중 (%s) — 이전 필요\n' % d)
            return d
    # 3) 최후 — 로컬
    d = os.path.join('.', 'db')
    try: os.makedirs(d, exist_ok=True)
    except Exception: pass
    return d

def dbdir(arg=None):
    """공개 API — 다른 스크립트는 이걸 써서 DB 위치를 얻는다."""
    return _dbdir(arg)

def _path(item, dbdir): return os.path.join(dbdir, str(item) + '.json')

def _load(item, dbdir):
    try: return json.load(open(_path(item, dbdir), encoding='utf-8'))
    except Exception: return {}

def _empty(v): return v is None or v == {} or v == [] or v == ''

def check(item, observed, dbdir):
    e = _load(item, dbdir)
    if not e or _empty(e.get('data')): return {'status': 'due', 'reason': 'no DB data'}
    obs = str(observed if observed is not None else '').strip()
    if obs.lower() in ('', 'none', 'unknown', 'null', 'error', '-'):
        return {'status': 'due', 'reason': '관측 불가 -> 재조사(stale 방지)'}
    if str(e.get('marker')) != obs:
        return {'status': 'due', 'reason': 'marker 변경: %s -> %s' % (e.get('marker'), obs)}
    return {'status': 'reuse', 'reason': 'marker 불변: ' + obs, 'as_of': e.get('as_of')}

def get(item, dbdir): return _load(item, dbdir).get('data')

def set_(item, as_of, marker, dbdir, data):
    # (기준일 자동화) as_of 미지정 시: marker 가 날짜꼴이면 그 날짜(=데이터 최신 시점), 아니면 오늘.
    if not as_of:
        import re as _re, datetime as _dt
        _m = str(marker or '')[:10]
        as_of = _m if _re.fullmatch(r'\d{4}-\d{2}-\d{2}', _m) else _dt.date.today().isoformat()
    try:
        json.dump({'marker': marker, 'as_of': as_of, 'data': data},
                  open(_path(item, dbdir), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        return True
    except Exception as ex:
        sys.stderr.write('nmr_db set fail %s: %s\n' % (item, ex)); return False

def upsert(item, as_of, marker, keyfield, dbdir, rows):
    cur = _load(item, dbdir).get('data') or []
    if not isinstance(cur, list): cur = []
    idx = {str(r.get(keyfield)): i for i, r in enumerate(cur) if isinstance(r, dict)}
    for r in (rows or []):
        if not isinstance(r, dict): continue
        k = str(r.get(keyfield))
        if k in idx: cur[idx[k]] = r
        else: cur.append(r); idx[k] = len(cur) - 1
    cur.sort(key=lambda r: str(r.get(keyfield)))
    return set_(item, as_of, marker, dbdir, cur)

# (편의) 신규조사분이 있으면 DB 저장, 없으면 DB값 재사용 — merge 등 파이프라인용
def sync(item, value, as_of, marker, dbdir, nonempty=None):
    ne = nonempty or (lambda v: not _empty(v))
    if ne(value):
        set_(item, as_of, marker, dbdir, value); return value
    cached = get(item, dbdir)
    return cached if (cached is not None and ne(cached)) else value

# ─────────────────────────────────────────────────────────────
# [DB화 v2] 차트용 '시계열' 누적 DB — 표(rows)뿐 아니라 차트 series 도 DB에 저장·누적·재사용.
def _pairs(s):
    return isinstance(s, list) and len(s) > 0 and isinstance(s[0], (list, tuple)) and len(s[0]) >= 2

def merge_series(old, new):
    def _m(s):
        d = {}
        for p in (s or []):
            if isinstance(p, (list, tuple)) and len(p) >= 2 and p[0] is not None:
                d[str(p[0])[:10]] = p[1]
        return d
    if _pairs(old) or _pairs(new):
        d = _m(old); d.update(_m(new))
        return [[k, d[k]] for k in sorted(d)]
    no = new if isinstance(new, list) else []
    oo = old if isinstance(old, list) else []
    return no if len(no) >= len(oo) else oo

def _latest_marker(s):
    if _pairs(s):
        ds=[str(p[0])[:10] for p in s if p and p[0] is not None]
        return max(ds) if ds else None
    return ('n=%d'%len(s)) if isinstance(s,list) else None

def dbseries(item, fresh, dbdir, prefer_fresh=False):
    # [변경감지 마커] 조사 실패(null)와 변경없음을 구분: null→unverified(플래그), fresh→마커비교 updated/reused
    e=_load('series_'+item, dbdir); cur=e.get('data'); cur_marker=e.get('marker')
    if _empty(fresh):
        return {'data': cur, 'status':'unverified', 'marker': cur_marker}
    merged=merge_series(cur, fresh); new_marker=_latest_marker(merged); fm=_latest_marker(fresh)
    status='updated' if (fm is not None and str(fm)!=str(cur_marker)) else 'reused'
    # (기준일 자동화) 변경됐을 때만 저장 → set_ 이 as_of 를 데이터 최신일(marker)로 자동 기록.
    if merged and (status=='updated' or merged!=cur or not e.get('as_of')): set_('series_'+item, '', new_marker, dbdir, merged)
    out = fresh if (prefer_fresh and fresh) else merged
    return {'data': out, 'status': status, 'marker': new_marker}

def merge_rows(old, new, key='name'):
    # 셀 단위 병합: fresh 셀이 값 있으면 fresh, 없으면(null/-) DB 셀 백필. DB는 null로 덮지 않음.
    om={str(r.get(key)): r for r in (old or []) if isinstance(r,dict)}
    out=[]; back=[]
    for r in (new or []):
        if not isinstance(r,dict): out.append(r); continue
        k=str(r.get(key)); base=dict(om.get(k) or {}); merged=dict(base)
        for f,v in r.items():
            if v not in (None,'','-'): merged[f]=v
        for f,bv in base.items():
            if (r.get(f) in (None,'','-')) and (bv not in (None,'','-')): back.append(k+'.'+f)
        out.append(merged)
    seen={str(r.get(key)) for r in out if isinstance(r,dict)}
    for k,r in om.items():
        if k not in seen: out.append(r)
    return out, back

def dbrows(item, fresh, dbdir, key='name'):
    cur=_load(item, dbdir).get('data') or []
    if _empty(fresh):
        return {'data': cur, 'backfilled':[], 'status':'unverified'}
    merged, back = merge_rows(cur, fresh, key)
    # (기준일 자동화) 내용이 변했을 때만 저장 → as_of=저장일(변경일) 자동 기록.
    if merged and merged!=cur: set_(item, '', '', dbdir, merged)
    return {'data': merged, 'backfilled': back, 'status': ('partial' if back else 'ok')}


def main():
    a = sys.argv; cmd = a[1] if len(a) > 1 else ''
    if cmd == 'check':
        print(json.dumps(check(a[2], a[3], _dbdir(a[4] if len(a) > 4 else None)), ensure_ascii=False))
    elif cmd == 'get':
        print(json.dumps(get(a[2], _dbdir(a[3] if len(a) > 3 else None)), ensure_ascii=False))
    elif cmd == 'set':
        print(set_(a[2], a[3], a[4], _dbdir(a[5] if len(a) > 5 else None), json.load(sys.stdin)))
    elif cmd == 'upsert':
        print(upsert(a[2], a[3], a[4], a[5], _dbdir(a[6] if len(a) > 6 else None), json.load(sys.stdin)))
    elif cmd == 'list':
        d = _dbdir(a[2] if len(a) > 2 else None)
        for f in sorted(glob.glob(os.path.join(d, '*.json'))):
            e = json.load(open(f, encoding='utf-8'))
            print(os.path.basename(f)[:-5], '| marker=', e.get('marker'), '| as_of=', e.get('as_of'))
    else:
        print('usage: nmr_db.py check|get|set|upsert|list ...'); sys.exit(1)

if __name__ == '__main__': main()
# EOF -- namoobi-market-report nmr_db.py
