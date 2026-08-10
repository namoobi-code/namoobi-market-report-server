#!/bin/sh
# guidance_recover.sh — SEC 속도 제한이 풀리면 가이던스를 다시 채운다 (2026-08-10).
#
# 사고 경위: --force 재파싱 중 SEC 가 차단해 본문이 0자로 왔고, 옛 값을 이미 지운 뒤라
# 화면의 가이던스 갭이 0건이 됐다. 파서에는 재발 방지(FETCH_FAIL)를 넣었고, 이 스크립트는
# **본문이 실제로 내려올 때까지 기다렸다가** 한 번만 재파싱한다.
cd /home/ubuntu/namoobi || exit 1
exec 9>/tmp/grec.lock
flock -n 9 || exit 0
LOG=/tmp/grecover.log
say() { echo "[recover $(date +%H:%M)] $*" >> $LOG; }

i=0
while [ $i -lt 48 ]; do                     # 최대 4시간(5분 간격)
  n=$(python3 - <<'PY'
import sys; sys.path.insert(0,'scripts')
try:
    from earnings_8k_watch import cik_map, exhibit_text
    from guidance_check import latest_earn_8k
    c = cik_map().get('ABT'); a = latest_earn_8k(c) if c else None
    print(len(exhibit_text(c, a) or '') if a else 0)
except Exception:
    print(0)
PY
)
  if [ "$n" -gt 5000 ]; then
    say "SEC 응답 정상(본문 ${n}자) — 재파싱 시작"
    nice -n 15 ionice -c3 python3 scripts/guidance_backfill.py --days 400 --workers 3 --force >> $LOG 2>&1
    flock /tmp/intra_kr.lock python3 scripts/earnings_join.py >> $LOG 2>&1
    say "복구 완료"
    exit 0
  fi
  say "SEC 아직 차단(본문 ${n}자) — 5분 뒤 재시도"
  sleep 300
  i=$((i + 1))
done
say "4시간 동안 회복되지 않아 중단"
