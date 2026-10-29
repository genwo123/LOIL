#!/usr/bin/env bash
# 내 SSH 키로 접속이 확인된 뒤에만 실행(root): 비밀번호 로그인을 끄고 키 로그인만 허용한다.
set -euo pipefail
if ! [ -s /root/.ssh/authorized_keys ]; then
  echo "root의 authorized_keys가 비어 있어 중단합니다(잠기지 않도록)"; exit 1
fi
CONF=/etc/ssh/sshd_config.d/99-loil-hardening.conf
mkdir -p /etc/ssh/sshd_config.d
cat > "$CONF" <<'CONF_EOF'
PasswordAuthentication no
PermitRootLogin prohibit-password
CONF_EOF
sshd -t
systemctl reload ssh || systemctl reload sshd
echo "harden-ssh 완료: 비밀번호 로그인 비활성화"
