#!/usr/bin/env python3
# nmr_fred.py — FRED 공용 헬퍼 (v3.16): API 키 직접 호출 우선 → fredgraph.csv 폴백. stdlib only.
# 키 위치: 환경변수 FRED_API_KEY 또는 연결폴더 SECURITY/secrets.env 의 FRED_API_KEY= 행.
# 실측(2026-07-07): sandbox curl 로 api.stlouisfed.org 도달 확인, 단건 ~0.4s(CSV ~0.6s).
# 주의: BAMLH0A0HYM2 등 ICE BofA 시리즈는 키가 있어도 FRED 가 최근 약 3년만 제공(라이선스 — 시리즈 자체 상한).
#       API 전환 목적은 구간 확대가 아니라 속도·안정성(브라우저/미러 불필요·JSON 구조화·서버측 월별 집계).
import os, json, subprocess, glob as _g, time as _t

def fred_key():
    k = os.environ.get('FRED_API_KEY')
    if k: return k.strip()
    for p in _g.glob('/sessions/*/mnt/claudeCowork/SECURITY/secrets.env') + _g.glob('/sessions/*/mnt/*/SECURITY/secrets.env'):
        try:
            for ln in open(p, encoding='utf-8'):
                ln = ln.strip()
                if ln.startswith('FRED_API_KEY=') and ln.split('=', 1)[1].strip():
                    return ln.split('=', 1)[1].strip()
        except Exception: pass
    return None

def _curl(u, timeout=10):
    r = subprocess.run(['curl', '-s', '--max-time', str(timeout), '-H', 'User-Agent: Mozilla/5.0', u],
                       capture_output=True, text=True, timeout=timeout + 2)
    return r.stdout or ''

def fred_series(sid, start=None, freq=None, tries=2, timeout=10):
    """반환: [[YYYY-MM-DD, float], ...] 오름차순(결측 '.' 제외). 실패 시 [].
    키 있으면 API JSON(freq='m' 이면 서버측 월별 eop 집계), 없거나 실패하면 fredgraph.csv(일별) 폴백."""
    key = fred_key()
    for _i in range(tries):
        try:
            if key:
                u = ('https://api.stlouisfed.org/fred/series/observations?series_id=%s&api_key=%s&file_type=json'
                     % (sid, key))
                if start: u += '&observation_start=' + start
                if freq: u += '&frequency=%s&aggregation_method=eop' % freq
                j = json.loads(_curl(u, timeout))
                out = []
                for o in j.get('observations', []):
                    v = o.get('value')
                    if v not in ('.', '', None):
                        try: out.append([o['date'], float(v)])
                        except Exception: pass
                if out: return out
            u = 'https://fred.stlouisfed.org/graph/fredgraph.csv?id=' + sid
            if start: u += '&cosd=' + start
            txt = _curl(u, timeout)
            if txt and ',' in txt:
                out = []
                for ln in txt.strip().split('\n')[1:]:
                    p = ln.split(',')
                    if len(p) >= 2 and p[1] not in ('.', ''):
                        try: out.append([p[0], float(p[1])])
                        except Exception: pass
                if out: return out
        except Exception: pass
        _t.sleep(1.5)
    return []

if __name__ == '__main__':
    import sys
    sid = sys.argv[1] if len(sys.argv) > 1 else 'DGS10'
    s = fred_series(sid, start=sys.argv[2] if len(sys.argv) > 2 else None)
    print('key:', 'yes' if fred_key() else 'no', '|', sid, len(s), 'obs', s[:1], s[-1:] if s else '')
