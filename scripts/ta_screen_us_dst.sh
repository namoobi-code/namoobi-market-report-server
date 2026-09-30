#!/bin/sh
# ta_screen 미국장 마감 후 회차 — 서머타임 인식 래퍼 (2026-09-30)
# cron 은 DST 를 모른다. 미국장 마감 = EDT 05:00 / EST 06:00 KST.
#   edt      : 05:40 cron — 서머타임(EDT)일 때만 실행 (마감+40분)
#   est      : 06:50 cron — 표준시(EST)일 때만 실행 (마감+50분)
#   edt-retry: 06:20 cron — EDT 이고 오늘자 완료 flag 가 없을 때만 재시도
cd /home/ubuntu/namoobi || exit 1
Z=$(TZ=America/New_York date +%Z)
TODAY=$(date +%y%m%d)
case "$1" in
  edt)       [ "$Z" = "EDT" ] || exit 0 ;;
  est)       [ "$Z" = "EST" ] || exit 0 ;;
  edt-retry) [ "$Z" = "EDT" ] || exit 0
             ls screening_completed_${TODAY}_*.txt >/dev/null 2>&1 && exit 0 ;;
  *) echo "usage: $0 edt|est|edt-retry"; exit 2 ;;
esac
echo "[$(date '+%F %T')] ta_screen_us_dst $1 (NY=$Z)" >> ta_screen.log
python3 scripts/ta_screen.py all >> ta_screen.log 2>&1
