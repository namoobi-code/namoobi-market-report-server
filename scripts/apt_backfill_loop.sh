#!/usr/bin/env bash
# (2026-08-08) 아파트 단지별 백필 감시 루프.
#   rtms.py 는 --extend + 단지DB done 테이블로 완전 재개 가능하므로,
#   국토부 레이트리밋(429)으로 중단돼도 잠시 뒤 다시 띄우면 이어서 진행된다.
#   전국 246지역 × 최대 250개월 = 12만여 호출이라 며칠에 걸쳐 돌아간다.
cd /home/ubuntu/namoobi || exit 1
LOG=logs/apt_backfill.log
for i in $(seq 1 400); do
  echo "=== [loop $i] $(date '+%F %T') 재개 ===" >> "$LOG"
  python3 -u scripts/rtms.py --backfill --months 250 --extend --budget 400000 >> "$LOG" 2>&1
  # 남은 작업이 있는지 판정: done 표식이 (246지역 × 2종) 에 도달하면 종료
  N=$(python3 - <<'PY'
import sqlite3
try:
    cx = sqlite3.connect("data/db/apt.sqlite")
    print(cx.execute("SELECT COUNT(DISTINCT sgg) FROM done").fetchone()[0])
except Exception:
    print(0)
PY
)
  echo "    → 완료 시군구 $N/246" >> "$LOG"
  [ "$N" -ge 246 ] && { echo "=== 전국 완료 $(date '+%F %T') ===" >> "$LOG"; break; }
  sleep 1200          # 레이트리밋 해제 대기(20분)
done
