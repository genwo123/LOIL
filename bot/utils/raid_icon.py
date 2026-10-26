"""
로일(LoIl) - 레이드 아이콘/색상
실제 레이드 이미지가 아직 없어서 우선 레이드명 기반 고정 색상 + 이니셜 원으로 구분.
나중에 실제 이미지를 web/static/raid_icons/{레이드명}.png 로 넣으면 자동으로 그걸 씀.
"""

import hashlib
from pathlib import Path

STATIC_DIR = Path(__file__).resolve().parent.parent.parent / "web" / "static"
ICON_DIR = STATIC_DIR / "raid_icons"
ICON_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXT = ["png", "jpg", "jpeg", "webp"]
PALETTE = ["#7C5CFC", "#43B581", "#FAA61A", "#F04747", "#5865F2", "#00BFA6", "#E91E8C", "#8BC34A", "#FF7043", "#26A69A"]


def _slug(raid_name: str) -> str:
    return raid_name.strip().replace(" ", "_")


def get_raid_icon_url(raid_name: str) -> str | None:
    slug = _slug(raid_name)
    for ext in ALLOWED_EXT:
        f = ICON_DIR / f"{slug}.{ext}"
        if f.exists():
            return f"/static/raid_icons/{slug}.{ext}"
    return None


def get_raid_color(raid_name: str) -> str:
    h = int(hashlib.md5(raid_name.strip().encode("utf-8")).hexdigest(), 16)
    return PALETTE[h % len(PALETTE)]
