#!/usr/bin/env bash
# 코드가 /opt/loil에 풀려 있는 상태에서 root로 실행: venv 설치, systemd 서비스 등록·시작
set -euo pipefail
cd /opt/loil

python3 -m venv venv
venv/bin/pip install --upgrade pip
venv/bin/pip install -r requirements-server.txt

mkdir -p logs
chown -R loil:loil /opt/loil
chmod 600 bot/.env

cp deploy/loil-bot.service deploy/loil-web.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now loil-web
systemctl enable --now loil-bot
sleep 4
systemctl --no-pager --lines=0 status loil-web loil-bot || true
echo "install-app 완료"
