#!/bin/sh
# guidance_chain.sh — 가이던스 갭 전체 재구축 (2026-08-10)
#
# 순서가 중요하다. 컨센서스가 없으면 갭도 포털 대조도 계산 자체가 불가능하다.
#   1) us_consensus  — ry0/ry1/eq0/rq0(연간·진행분기 컨센). 이게 비어 있어서
#                      우선순위 3·4번(올해FY·내년FY) 비교가 통째로 죽어 있었다.
#   2) zacks_spr     — 발표시점 매출·EPS 컨센(서프라이즈)
#   3) 가이던스 재파싱(--force) — 파서 수정분을 이미 채워진 값에도 반영
#   4) earnings_join — 풀에 gapR/gapE/pgapR/pgapE 반영
#   5) guidance_portal — 포털 대조값(검증 전용) 수집 후 다시 join
cd /home/ubuntu/namoobi || exit 1
# 단계가 겹치면 서로의 결과를 덮어쓴다(실측: 갭 479건 소실). 한 번에 하나만 돈다.
exec 9>/tmp/gchain.lock
flock -n 9 || { echo "[chain] 이미 실행 중 — 종료" >> /tmp/gchain.log; exit 0; }
LOG=/tmp/gchain.log
say() { echo "[chain $(date +%H:%M)] $*" >> $LOG; }

# 실행 중인 재파싱이 있으면 끝날 때까지 대기.
# 패턴을 'python3 scripts/...' 로 좁힌다 — 'guidance_backfill.py' 만 쓰면 이 문자열을
# 명령줄에 담고 있는 다른 쉘(예: 이 스크립트를 띄운 ssh 명령)까지 잡혀 영원히 기다린다.
while pgrep -f "python3 scripts/guidance_backfill.py" >/dev/null; do sleep 20; done

say "1/6 us_consensus 시작"
# (재실행) 컨센은 이미 채워져 있어 건너뛴다
#nice -n 15 ionice -c3 python3 scripts/us_consensus.py >> logs/us_consensus.log 2>&1
say "1/6 us_consensus 완료 rc=$?"

say "2/6 zacks_spr 시작"
#nice -n 15 ionice -c3 python3 scripts/zacks_spr.py >> logs/zacks_spr.log 2>&1
say "2/6 zacks_spr 완료 rc=$?"

say "3/6 가이던스 재파싱(--force) 시작"
nice -n 15 ionice -c3 python3 scripts/guidance_backfill.py --days 400 --workers 4 --force >> $LOG 2>&1
say "3/6 재파싱 완료 rc=$?"

say "4/6 join"
flock /tmp/intra_kr.lock python3 scripts/earnings_join.py >> $LOG 2>&1

say "5/6 포털 대조값 수집"
nice -n 15 ionice -c3 python3 scripts/guidance_portal.py --days 60 >> $LOG 2>&1

say "6/6 join"
flock /tmp/intra_kr.lock python3 scripts/earnings_join.py >> $LOG 2>&1
say "전체 완료"
