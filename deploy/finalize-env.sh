#!/usr/bin/env bash
# 사용법: finalize-env.sh <도메인>   (예: loil-bot.duckdns.org)
# bot/.env의 서버용 값 4개를 설정하고, SESSION_SECRET_KEY가 없으면 무작위로 생성한다. 비밀값은 출력하지 않는다.
set -euo pipefail
DOMAIN="${1:?도메인을 인자로 주세요}"
ENV_FILE=/opt/loil/bot/.env

python3 - "$DOMAIN" "$ENV_FILE" <<'PY'
import sys, secrets
domain, path = sys.argv[1], sys.argv[2]
lines = open(path, encoding="utf-8").read().splitlines()
wanted = {
    "WEB_BASE_URL": f"https://{domain}",
    "DISCORD_REDIRECT_URI": f"https://{domain}/callback",
    "DEV_SKIP_LOGIN": "false",
}
have = {}
out = []
for l in lines:
    key = l.split("=", 1)[0].strip() if "=" in l and not l.lstrip().startswith("#") else None
    if key in wanted:
        out.append(f"{key}={wanted[key]}"); have[key] = True
    elif key == "SESSION_SECRET_KEY" and l.split("=", 1)[1].strip():
        out.append(l); have[key] = True
    else:
        out.append(l)
for k, v in wanted.items():
    if k not in have:
        out.append(f"{k}={v}")
if "SESSION_SECRET_KEY" not in have:
    out.append("SESSION_SECRET_KEY=" + secrets.token_urlsafe(48))
open(path, "w", encoding="utf-8").write("\n".join(out) + "\n")
print("설정된 항목:", ", ".join(list(wanted) + ["SESSION_SECRET_KEY"]))
PY
chown loil:loil "$ENV_FILE"
chmod 600 "$ENV_FILE"
