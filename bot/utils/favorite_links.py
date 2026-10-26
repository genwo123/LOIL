"""
로일(LoIl) - 길드 즐겨찾기 링크 유틸
버튼을 계속 늘리는 대신, 길드장이 등록한 링크 목록을 하나의 명령어로 접근

저장 구조 (guild_settings.json):
{
  "guild_id": {
    "favorite_links": [
      {"label": "길드 공지 규칙", "url": "https://..."}
    ]
  }
}
"""

from bot.utils.storage import load_settings as _load, save_settings as _save

MAX_LINKS = 25  # discord.ui.View 한 메시지에 배치 가능한 버튼 최대 개수


def get_links(guild_id: int) -> list[dict]:
    """등록된 즐겨찾기 링크 목록 [{label, url}, ...]"""
    return _load().get(str(guild_id), {}).get("favorite_links", [])


def add_link(guild_id: int, label: str, url: str) -> bool:
    """
    링크 추가. 같은 이름이 있으면 URL을 덮어씀.
    Returns: 성공 여부 (최대 개수 초과 시 False)
    """
    settings = _load()
    gid = str(guild_id)
    if gid not in settings:
        settings[gid] = {}
    links = settings[gid].setdefault("favorite_links", [])

    for link in links:
        if link["label"] == label:
            link["url"] = url
            _save(settings)
            return True

    if len(links) >= MAX_LINKS:
        return False

    links.append({"label": label, "url": url})
    _save(settings)
    return True


def remove_link(guild_id: int, label: str) -> bool:
    """이름으로 링크 삭제. Returns: 실제로 삭제됐는지 여부"""
    settings = _load()
    gid = str(guild_id)
    links = settings.get(gid, {}).get("favorite_links", [])
    new_links = [l for l in links if l["label"] != label]
    if len(new_links) == len(links):
        return False
    settings[gid]["favorite_links"] = new_links
    _save(settings)
    return True
