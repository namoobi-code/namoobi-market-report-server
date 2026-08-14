#!/bin/sh
# bz_wait.sh — Benzinga 429 가 풀릴 때까지 기다렸다가 재수집 (2026-08-14).
#
# 오늘 오프라인 재판정 시도(--gap 0)로 20건을 연속 요청해 다시 429 에 걸렸다.
# 창(window)이 시간 단위라 곧바로 재시도해도 소용없다 — 10분 간격으로 1건씩 찔러보고,
# 성공하면 그때 본 수집(5초 간격)을 시작한다. 수집 후 join·대조 리포트까지 이어서 돈다.
cd /home/ubuntu/namoobi || exit 1
exec 9>/tmp/bzw.lock
flock -n 9 || exit 0
L=/tmp/bz_wait.log
say() { echo "[bzw $(date '+%m-%d %H:%M')] $*" >> $L; }

i=0
while [ $i -lt 72 ]; do                       # 최대 12시간(10분 간격)
  ok=$(python3 - <<'PY'
import urllib.request
UA={'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36'}
try:
    r=urllib.request.urlopen(urllib.request.Request(
        'https://www.benzinga.com/quote/AAPL/earnings-forecasts',headers=UA),timeout=20)
    print(1 if r.status==200 else 0)
except Exception:
    print(0)
PY
)
  if [ "$ok" = "1" ]; then
    say "429 해제 확인 — 본 수집 시작"
    flock -n /tmp/bz.lock python3 scripts/guidance_bz.py --days 60 --gap 5 >> $L 2>&1
    flock /tmp/intra_kr.lock python3 scripts/earnings_join.py >> $L 2>&1
    python3 scripts/bz_diff.py --limit 150 > /tmp/bz_final_diff.log 2>&1
    say "완료 — $(head -2 /tmp/bz_final_diff.log | tr '\n' ' ')"
    exit 0
  fi
  say "아직 429 — 10분 뒤 재시도"
  sleep 600
  i=$((i + 1))
done
say "12시간 내 해제되지 않아 중단"
