#!/usr/bin/env bash
# 사용법: pull-backup.sh <서버IP> [저장폴더]
# 서버의 실데이터(guild_settings.json 등)를 이 PC로 내려받는다. 주 1회쯤 실행 권장.
set -euo pipefail
HOST="${1:?서버 IP를 인자로 주세요}"
DEST="${2:-$HOME/loil-backups}"
STAMP="$(date +%Y%m%d_%H%M%S)"
KEY="$HOME/.ssh/id_ed25519_loil"
OUT="$DEST/$STAMP"
mkdir -p "$OUT"
SSH_OPTS=(-i "$KEY" -o StrictHostKeyChecking=accept-new)

scp "${SSH_OPTS[@]}" "root@$HOST:/opt/loil/bot/data/guild_settings.json" "$OUT/"
for f in suggestions.json schedule_state.json; do
  scp "${SSH_OPTS[@]}" "root@$HOST:/opt/loil/bot/data/$f" "$OUT/" 2>/dev/null || true
done
scp -r "${SSH_OPTS[@]}" "root@$HOST:/opt/loil/web/static/guild_banners" "$OUT/" 2>/dev/null || true

echo "백업 완료: $OUT"
ls -la "$OUT"
