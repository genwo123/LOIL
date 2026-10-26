#!/usr/bin/env bash
# 새 서버(Ubuntu 24.04)에서 root로 한 번 실행: 기본 패키지, 방화벽, 서비스 유저, Caddy 설치
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive

apt-get update -y
apt-get upgrade -y
apt-get install -y python3-venv python3-pip ufw curl gnupg debian-keyring debian-archive-keyring apt-transport-https

ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

id loil >/dev/null 2>&1 || adduser --system --group --home /opt/loil --shell /usr/sbin/nologin loil
mkdir -p /opt/loil/logs
chown -R loil:loil /opt/loil

if ! command -v caddy >/dev/null 2>&1; then
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | tee /etc/apt/sources.list.d/caddy-stable.list >/dev/null
  apt-get update -y
  apt-get install -y caddy
fi

python3 --version
caddy version
echo "setup-server 완료"
