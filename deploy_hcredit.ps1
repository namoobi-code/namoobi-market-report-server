# deploy_hcredit.ps1 — 가계대출·대출 연체율 카드 배포 (2026-08-10)
#
# 실행:  powershell -ExecutionPolicy Bypass -File D:\claudeCowork\namoobi-market-report-server\deploy_hcredit.ps1
#
# 하는 일
#   1) static/app.js · static/index.html  → 서버 static/
#   2) scripts/hcredit.py                 → 서버 scripts/
#   3) hcredit.py --full  (최초 1회 전 구간 백필 · 2~3분)
#   4) cron 07:15 등록 (이미 있으면 건너뜀)
#   5) 서비스 재시작 + API 응답 확인
#
# 이미 배포한 뒤 코드만 고쳤다면 -SkipFull 로 3번을 건너뛸 수 있다.

param([switch]$SkipFull)

$ErrorActionPreference = "Stop"
$ROOT = "D:\claudeCowork\namoobi-market-report-server"
$KEY  = "D:\claudeCowork\SECURITY\nmr_deploy_key"
$SRV  = "ubuntu@141.147.160.13"

function Step($n, $msg) { Write-Host "`n[$n] $msg" -ForegroundColor Cyan }
function Die($msg)      { Write-Host "`n✗ $msg" -ForegroundColor Red; exit 1 }

if (-not (Test-Path $ROOT)) { Die "저장소 없음: $ROOT" }
if (-not (Test-Path $KEY))  { Die "배포키 없음: $KEY" }
Set-Location $ROOT

foreach ($f in @("static\app.js", "static\index.html", "scripts\hcredit.py")) {
    if (-not (Test-Path $f)) { Die "파일 없음: $f" }
}

Step "1/5" "static 전송 — app.js · index.html"
scp -i $KEY static/app.js static/index.html "${SRV}:namoobi/static/"
if ($LASTEXITCODE -ne 0) { Die "static 전송 실패" }

Step "2/5" "scripts 전송 — hcredit.py"
scp -i $KEY scripts/hcredit.py "${SRV}:namoobi/scripts/"
if ($LASTEXITCODE -ne 0) { Die "scripts 전송 실패" }

if ($SkipFull) {
    Step "3/5" "백필 건너뜀 (-SkipFull)"
} else {
    Step "3/5" "ECOS 전 구간 백필 — 2~3분 걸립니다 (약 15,000행)"
    ssh -i $KEY $SRV "cd namoobi && python3 scripts/hcredit.py --full"
    if ($LASTEXITCODE -ne 0) { Die "hcredit.py --full 실패 — 위 메시지 확인 (서버 keys/ecos.txt 경로일 가능성이 큼)" }
}

Step "4/5" "cron 등록 (07:15 · 중복 방지)"
$cronLine = "15 7 * * * cd /home/ubuntu/namoobi && python3 scripts/hcredit.py >> /home/ubuntu/namoobi/hcredit.log 2>&1"
ssh -i $KEY $SRV "crontab -l 2>/dev/null | grep -q 'hcredit.py' || ( (crontab -l 2>/dev/null; echo '$cronLine') | crontab - ); echo '--- 등록된 항목 ---'; crontab -l | grep hcredit.py"
if ($LASTEXITCODE -ne 0) { Die "cron 등록 실패" }

Step "5/5" "서비스 재시작 + 확인"
ssh -i $KEY $SRV "sudo systemctl restart namoobi; sleep 3; ls -lh namoobi/data/db/hcredit.json; curl -s -o /dev/null -w '  /api/db/hcredit -> HTTP %{http_code}\n' http://127.0.0.1/api/db/hcredit"
if ($LASTEXITCODE -ne 0) { Die "재시작/확인 실패" }

Write-Host "`n✓ 배포 완료 — 브라우저에서 Ctrl+Shift+R 로 새로고침하세요." -ForegroundColor Green
Write-Host "  Real Estate 탭 → '은행 정기예금 잔액' 카드 바로 아래에 카드 2개가 추가됩니다.`n"
