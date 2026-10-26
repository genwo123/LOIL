"""
로일(LoIl) - 길드 이름 기반 예쁜 URL 슬러그
"/{길드이름}/홈", "/{길드이름}/일정/{닉네임}" 같은 경로에서 쓰는 길드 식별자.
guild_settings.json에 "guild_name"(원래 이름) + "url_name"(경로용, 중복 시 뒤에 숫자 붙음)으로 저장.
"""

import re

from bot.utils.storage import load_settings, save_settings

_STRIP_PATTERN = re.compile(r"[^0-9A-Za-z가-힣]+")


def slugify_guild_name(name: str) -> str:
    cleaned = _STRIP_PATTERN.sub("", name or "")
    return cleaned or "길드"


def sync_guild_name(guild_id: int, guild_name: str):
    """봇이 실제로 아는 길드 이름을 settings에 반영하고, url_name이 없으면 새로 만든다."""
    settings = load_settings()
    gid = str(guild_id)
    if gid not in settings:
        settings[gid] = {}

    changed = False
    if settings[gid].get("guild_name") != guild_name:
        settings[gid]["guild_name"] = guild_name
        changed = True

    if not settings[gid].get("url_name"):
        base = slugify_guild_name(guild_name)
        candidate = base
        suffix = 1
        taken = {
            v.get("url_name")
            for k, v in settings.items()
            if k != gid and isinstance(v, dict)
        }
        while candidate in taken:
            suffix += 1
            candidate = f"{base}{suffix}"
        settings[gid]["url_name"] = candidate
        changed = True

    if changed:
        save_settings(settings)


def get_guild_id_by_url_name(url_name: str) -> str | None:
    settings = load_settings()
    for gid, data in settings.items():
        if isinstance(data, dict) and data.get("url_name") == url_name:
            return gid
    return None


def get_url_name(guild_id) -> str | None:
    return load_settings().get(str(guild_id), {}).get("url_name")
