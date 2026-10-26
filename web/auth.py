"""
로일(LoIl) - 웹 대시보드 로그인 (Discord OAuth2)

길드장/부길드장(= Discord 서버 관리자 권한 보유자)만 로그인한다.
일반 길드원 로그인은 없음 — 조회는 계속 /g/{slug} 링크로.
"""

from urllib.parse import urlencode

import requests

from bot.config.settings import DISCORD_CLIENT_ID, DISCORD_CLIENT_SECRET, DISCORD_REDIRECT_URI

DISCORD_API   = "https://discord.com/api"
OAUTH_SCOPE   = "identify guilds"
ADMINISTRATOR = 0x8  # Discord 권한 비트필드 - 관리자


def build_authorize_url(state: str) -> str:
    params = {
        "client_id":     DISCORD_CLIENT_ID,
        "redirect_uri":  DISCORD_REDIRECT_URI,
        "response_type": "code",
        "scope":         OAUTH_SCOPE,
        "state":         state,
        "prompt":        "consent",
    }
    return f"{DISCORD_API}/oauth2/authorize?{urlencode(params)}"


def exchange_code(code: str) -> str:
    """OAuth authorization code를 access token으로 교환."""
    data = {
        "client_id":     DISCORD_CLIENT_ID,
        "client_secret": DISCORD_CLIENT_SECRET,
        "grant_type":    "authorization_code",
        "code":          code,
        "redirect_uri":  DISCORD_REDIRECT_URI,
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    res = requests.post(f"{DISCORD_API}/oauth2/token", data=data, headers=headers, timeout=10)
    res.raise_for_status()
    return res.json()["access_token"]


def fetch_user(access_token: str) -> dict:
    headers = {"Authorization": f"Bearer {access_token}"}
    res = requests.get(f"{DISCORD_API}/users/@me", headers=headers, timeout=10)
    res.raise_for_status()
    return res.json()


def fetch_admin_guilds(access_token: str) -> list[dict]:
    """이 유저가 서버 소유자이거나 관리자 권한을 가진 길드 목록 (id, name)."""
    headers = {"Authorization": f"Bearer {access_token}"}
    res = requests.get(f"{DISCORD_API}/users/@me/guilds", headers=headers, timeout=10)
    res.raise_for_status()

    admin_guilds = []
    for g in res.json():
        is_owner = g.get("owner", False)
        perms    = int(g.get("permissions", 0))
        if is_owner or (perms & ADMINISTRATOR):
            admin_guilds.append({"id": g["id"], "name": g["name"]})
    return admin_guilds
