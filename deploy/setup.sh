#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
# namoobi 시황 대시보드 — 서버 완전 복구 스크립트
# 새 서버(Ubuntu 24.04)에서 이 파일 하나만 실행하면 전부 재구축된다.
#   bash setup.sh
# ─────────────────────────────────────────────────────────────
set -e
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
APP=/home/ubuntu/namoobi

echo "▸ 1/7 시스템 준비"
sudo apt-get update -qq
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq python3-venv python3-pip nginx curl

echo "▸ 2/7 스왑 2GB (1GB 인스턴스 대응)"
if ! swapon --show | grep -q swapfile; then
  sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile
  sudo mkswap /swapfile && sudo swapon /swapfile
  echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab >/dev/null
fi

echo "▸ 3/7 방화벽 (⚠️ ACCEPT를 REJECT보다 앞에 — INPUT 1)"
sudo iptables -I INPUT 1 -p tcp --dport 80 -j ACCEPT
sudo iptables -I INPUT 1 -p tcp --dport 443 -j ACCEPT
sudo netfilter-persistent save
echo "   ※ Oracle 콘솔 Security List 에도 80/443 Ingress 규칙 필요"

echo "▸ 4/7 앱 배치"
mkdir -p $APP/data/{db,reports,report} $APP/static
cp "$REPO_DIR/app.py" "$REPO_DIR/poll.py" $APP/
cp "$REPO_DIR/static/"* $APP/static/
cd $APP && python3 -m venv venv
./venv/bin/pip install -q --upgrade pip
./venv/bin/pip install -q -r "$REPO_DIR/requirements.txt"

echo "▸ 5/7 systemd 서비스"
sudo cp "$REPO_DIR/deploy/namoobi.service" /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now namoobi

echo "▸ 6/7 nginx"
sudo cp "$REPO_DIR/deploy/nginx.conf" /etc/nginx/sites-available/default
sudo nginx -t && sudo systemctl reload nginx

echo "▸ 7/7 cron (폴링 1일 2회 + DuckDNS IP 갱신 5분)"
echo "   ※ DuckDNS 토큰은 수동 설정: ~/duckdns/duck.sh"
(crontab -l 2>/dev/null | grep -v 'namoobi/poll.py'; \
 echo "0 9,21 * * * cd $APP && ./venv/bin/python poll.py >> $APP/poll.log 2>&1") | crontab -

echo ""
echo "✅ 복구 완료 → http://<서버IP>/api/health 확인"
echo "   데이터는 PC에서 'python3 scripts/sync_server.py' 실행 시 채워진다."
