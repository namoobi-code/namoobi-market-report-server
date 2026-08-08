#!/usr/bin/env bash
# (2026-08-08) 실거래 백필 감시 루프 — 아파트 + 비아파트를 **순차** 실행.
#   둘 다 apt.sqlite 에 단지별 시계열을 쓰는데 SQLite 는 동시 쓰기가 1개뿐이라
#   병렬로 돌리면 서로 "database is locked" 로 죽는다. 한 루프에서 차례로 돌린다.
#   각 스크립트는 --extend + done 표식으로 완전 재개 가능하므로 중단돼도 이어서 진행된다.
cd /home/ubuntu/namoobi || exit 1
# (2026-08-08) 중복 실행 방지 — 루프가 여러 개 뜨면 rtms_etc 가 서로 SQLite 를 물고
# "database is locked" 로 죽는다(실제로 4개까지 떠서 비아파트 수집이 계속 실패했다).
exec 9>/tmp/nmr_backfill.lock
flock -n 9 || { echo "이미 실행 중 — 중복 기동 중단"; exit 0; }
LOG=logs/apt_backfill.log
LOG2=logs/rtms_etc.log
for i in $(seq 1 400); do
  echo "=== [loop $i] $(date '+%F %T') 아파트 ===" >> "$LOG"
  python3 -u scripts/rtms.py --backfill --months 250 --extend --budget 40000 >> "$LOG" 2>&1

  echo "=== [loop $i] $(date '+%F %T') 비아파트 ===" >> "$LOG2"
  python3 -u scripts/rtms_etc.py --months 36 --sleep 0.5 --budget 20000 >> "$LOG2" 2>&1

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
  [ "$N" -ge 246 ] && { echo "=== 전국 완료 $(date '+%F %T') ===" >> "$LOG"; break; }
  sleep 900          # 레이트리밋 해제 대기(15분)
done
