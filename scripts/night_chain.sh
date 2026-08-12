#!/bin/sh
# night_chain.sh — 밤사이 무인 실행 (2026-08-10).
#
#   1) Benzinga 전 종목 수집 (저속 5초 · 약 3.6시간 · 429 나면 그 지점에서 중단)
#   2) join — 포털 갭을 풀에 반영
#   3) 대조 리포트 저장 — 어긋난 종목이 곧 파서 개선 큐
#   4) 표 파서 감사 저장 — 캐시 원문 기준(SEC 미호출)
#
# 결과는 /tmp/night_*.log 에 남는다. 아침에 그것만 보면 된다.
cd /home/ubuntu/namoobi || exit 1
exec 9>/tmp/night.lock
flock -n 9 || exit 0
L=/tmp/night_main.log
say() { echo "[night $(date '+%m-%d %H:%M')] $*" >> $L; }

say "1/4 Benzinga 수집 시작"
python3 scripts/guidance_bz.py --days 60 --gap 5 >> /tmp/night_bz.log 2>&1
say "1/4 완료 rc=$?"

say "2/4 join"
flock /tmp/intra_kr.lock python3 scripts/earnings_join.py >> $L 2>&1

say "3/4 대조 리포트"
python3 scripts/bz_diff.py --limit 120 > /tmp/night_diff.log 2>&1
say "3/4 완료 — $(head -2 /tmp/night_diff.log | tr '\n' ' ')"

say "4/4 표 파서 감사"
python3 scripts/gt_audit.py --limit 300 > /tmp/night_gt.log 2>&1
say "4/4 완료 — $(tail -2 /tmp/night_gt.log | head -1)"
say "전체 완료"
