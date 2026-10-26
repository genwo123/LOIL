#!/usr/bin/env bash
# 사용법: setup-caddy.sh <도메인>   Caddy가 HTTPS 인증서를 자동 발급하고 웹 앱(127.0.0.1:8000)으로 전달한다.
set -euo pipefail
DOMAIN="${1:?도메인을 인자로 주세요}"
cat > /etc/caddy/Caddyfile <<CADDY
${DOMAIN} {
    reverse_proxy 127.0.0.1:8000
}
CADDY
systemctl reload caddy || systemctl restart caddy
sleep 2
systemctl --no-pager --lines=0 status caddy || true
echo "setup-caddy 완료: https://${DOMAIN}"
