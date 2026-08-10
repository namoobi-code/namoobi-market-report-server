#!/bin/sh
# gitsync.sh — 두 저장소를 한 번에 커밋·푸시 (2026-08-10 신설)
#
# 왜 필요한가: 수정은 서버(scp)와 로컬 양쪽에 흩어지는데, 커밋을 나중에 몰아서 하면
# "어제 한 것 중 뭐가 안 올라갔는지" 를 매번 찾아야 한다. 수정할 때마다 이 스크립트로
# 즉시 반영한다.
#
# 사용:  sh gitsync.sh "커밋 메시지"
#        (메시지 없으면 날짜·시각으로 자동 생성)
#
# 대상 저장소
#   /sessions/*/mnt/claudeCowork/namoobi-market-report-server  (서버 코드·프론트)
#   /sessions/*/mnt/namoobi-market-report                      (플러그인·스킬·문서)
MSG=${1:-"작업 반영 $(date '+%Y-%m-%d %H:%M')"}
ROOT=$(cd "$(dirname "$0")" && pwd)
TOKF="$ROOT/SECURITY/githubtoken.txt"
TOK=$(tr -d '\r\n' < "$TOKF" | grep -o '[A-Za-z0-9_]\{20,\}' | head -1)

sync_one() {
  DIR=$1; REPO=$2
  [ -d "$DIR/.git" ] || { echo "[skip] $REPO — 저장소 아님"; return; }
  cd "$DIR" || return
  rm -f .git/index.lock .git/HEAD.lock          # 이전 실행이 죽었을 때 남는 잠금 해제
  if [ -n "$(git status --porcelain)" ]; then
    git add -A
    git -c user.email=namoobi@gmail.com -c user.name=namoobi commit -q -m "$MSG"
    echo "[commit] $REPO — $(git log --oneline -1)"
  else
    echo "[clean ] $REPO — 변경 없음"
  fi
  OUT=$(git push "https://namoobi-code:$TOK@github.com/namoobi-code/$REPO.git" main 2>&1 | tail -1)
  echo "[push  ] $REPO — $OUT"
}

sync_one "$ROOT/namoobi-market-report-server" namoobi-market-report-server
sync_one "$(dirname "$ROOT")/namoobi-market-report" namoobi-market-report
