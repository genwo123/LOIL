"""
로일(LoIl) - 길드 대표 배너 이미지
파일 자체는 web/static/guild_banners/에 저장하고, guild_settings.json엔 상대 경로만 기록.
(이미지를 JSON에 base64로 박으면 매 저장/로드마다 무거워져서 분리)
"""

from pathlib import Path

from bot.utils.storage import load_settings, save_settings

STATIC_DIR = Path(__file__).resolve().parent.parent.parent / "web" / "static"
BANNER_DIR = STATIC_DIR / "guild_banners"
BANNER_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXT = {"jpg", "jpeg", "png", "webp", "gif"}
MAX_SIZE = 5 * 1024 * 1024


def get_banner_url(guild_id) -> str | None:
    path = load_settings().get(str(guild_id), {}).get("banner")
    return f"/static/{path}" if path else None


def set_banner(guild_id, filename: str, content: bytes) -> str | None:
    """성공하면 새 배너 URL, 형식/크기가 안 맞으면 None."""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_EXT or not content or len(content) > MAX_SIZE:
        return None

    remove_banner(guild_id)
    dest = BANNER_DIR / f"{guild_id}.{ext}"
    dest.write_bytes(content)

    settings = load_settings()
    gid = str(guild_id)
    if gid not in settings:
        settings[gid] = {}
    rel = f"guild_banners/{guild_id}.{ext}"
    settings[gid]["banner"] = rel
    save_settings(settings)
    return f"/static/{rel}"


def remove_banner(guild_id):
    settings = load_settings()
    gid = str(guild_id)
    rel = settings.get(gid, {}).get("banner")
    if rel:
        f = STATIC_DIR / rel
        if f.exists():
            f.unlink()
        settings[gid].pop("banner", None)
        save_settings(settings)
