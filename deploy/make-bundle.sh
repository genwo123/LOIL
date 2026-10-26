#!/usr/bin/env bash
# 프로젝트 루트에서 실행: 서버로 올릴 압축 파일 생성. 비밀(.env)과 불필요한 파일은 제외한다.
set -euo pipefail
OUT="${1:-loil-bundle.tar.gz}"
tar --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' --exclude='logs' --exclude='.claude' \
    --exclude='bot/data/backups' --exclude='bot/.env' --exclude='.env' --exclude='cache' \
    --exclude='docs/sample/screenshots' --exclude='venv' --exclude='*.tar.gz' \
    -czf "$OUT" .
ls -la "$OUT"
