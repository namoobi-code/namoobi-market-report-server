#!/usr/bin/env bash
# (2026-08-08 재작성) 실거래 심층 백필 감시 루프.
#
#  이전 구조는 아파트 → 비아파트를 **순차** 실행했다. 둘 다 apt.sqlite 에 단지별 시계열을
#  쓰는데 SQLite 는 파일당 쓰기가 1개뿐이라 병렬로 돌리면 "database is locked" 로 죽었기 때문이다.
#  그 탓에 아파트 심층 백필(지역당 252개월)이 몇 시간 도는 동안 비아파트는 멈춰 있었다.
#  → apt_db 를 apt.sqlite / apt_etc.sqlite 두 파일로 분리해 **동시 실행**한다.
#
#  data.go.kr 은 활용신청 건(=API)마다 일일 한도가 있다. 한도가 차면 각 수집기가
#  해당 유형만 건너뛰고 계속 진행하며, 자정(KST) 리셋 후 다음 사이클에서 이어받는다.
cd /home/ubuntu/namoobi || exit 1
exec 9>/tmp/nmr_backfill.lock
flock -n 9 || { echo "이미 실행 중 — 중복 기동 중단"; exit 0; }
# flock 을 잡은 시점엔 정상 자식이 있을 수 없으므로, 남아 있다면 전부 고아다.
pkill -f "scripts/rtms.py --backfill" 2>/dev/null
pkill -f "scripts/rtms_etc.py"        2>/dev/null
sleep 3

LOG=logs/apt_backfill.log
LOG2=logs/rtms_etc.log

for i in $(seq 1 400); do
  echo "=== [loop $i] $(date '+%F %T') 아파트+비아파트 동시 시작 ===" | tee -a "$LOG" >> "$LOG2"

  python3 -u scripts/rtms.py --backfill --months 250 --extend --budget 40000 >> "$LOG" 2>&1 &
  PA=$!
  # 비아파트도 아파트와 같은 깊이(250개월)로 최대치 백필. done 표식이 (kind,sgg,ym) 단위라
  # 이미 받은 12개월은 건너뛰고 빠진 과거만 채운다.
  python3 -u scripts/rtms_etc.py --months 250 --sleep 0.35 --budget 40000 >> "$LOG2" 2>&1 &
  PE=$!
  wait $PA $PE

  N=$(python3 - <<'PY'
import sqlite3
try:
    cx = sqlite3.connect("data/db/apt.sqlite", timeout=30)
    print(cx.execute("SELECT COUNT(DISTINCT sgg) FROM done WHERE kind='apt_sale'").fetchone()[0])
except Exception:
    print(0)
PY
)
  echo "    → 아파트 완료 시군구 $N/246" >> "$LOG"
  [ "$N" -ge 246 ] && { echo "=== 아파트 전국 완료 $(date '+%F %T') ===" >> "$LOG"; }
  sleep 600          # 일일 한도·레이트리밋 해제 대기
done
