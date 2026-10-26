"""
로일(LoIl) - 웹 대시보드용 편성 결과 스냅샷

파티 편성이 끝나면 이 모듈이 결과를 JSON으로 저장하고,
길드별 고유 링크(슬러그)를 발급/조회한다.
실제 렌더링은 web/ 앱이 이 JSON을 읽어서 처리한다.
"""

import json
import os
import secrets
from datetime import datetime, timezone, timedelta

from bot.config.settings import WEB_BASE_URL
from bot.utils.storage import load_settings as _load_settings, save_settings as _save_settings

RESULTS_DIR   = "bot/data/web_results"
KST           = timezone(timedelta(hours=9))


def get_guild_name(guild_id: int, fallback: str = "") -> str:
    settings = _load_settings()
    return settings.get(str(guild_id), {}).get("guild_name", fallback)


def get_guild_setting(guild_id) -> dict:
    """길드 하나의 설정 전체(시트 URL, API 키 등)를 반환. 없으면 빈 dict."""
    return _load_settings().get(str(guild_id), {})


def list_registered_guild_ids() -> list[str]:
    """봇 설정이 등록된(= guild_settings.json에 존재하는) 길드 ID 목록."""
    return list(_load_settings().keys())


def get_or_create_web_slug(guild_id: int) -> str:
    """길드별 웹 조회용 고유 슬러그. 없으면 새로 만들어 guild_settings.json에 저장."""
    settings      = _load_settings()
    guild_key     = str(guild_id)
    guild_setting = settings.get(guild_key, {})
    slug = guild_setting.get("web_slug")
    if slug:
        return slug
    slug = secrets.token_urlsafe(9)
    guild_setting["web_slug"] = slug
    settings[guild_key] = guild_setting
    _save_settings(settings)
    return slug


def _snapshot_path(slug: str) -> str:
    return os.path.join(RESULTS_DIR, f"{slug}.json")


def save_result_snapshot(guild_id: int, week_label: str, raids: dict, guild_name: str = "") -> str:
    """편성 결과를 웹 조회용 JSON으로 저장 (레이드 단위로 기존 스냅샷에 병합).
    반환값은 이 길드의 슬러그 — 호출부에서 웹 링크를 만들 때 사용."""
    slug = get_or_create_web_slug(guild_id)
    os.makedirs(RESULTS_DIR, exist_ok=True)
    path = _snapshot_path(slug)

    snapshot = {}
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                snapshot = json.load(f)
        except Exception:
            snapshot = {}

    existing_raids = snapshot.get("raids", {})
    existing_raids.update(raids)

    snapshot.update({
        "guild_id":   guild_id,
        "guild_name": guild_name or snapshot.get("guild_name", ""),
        "week_label": week_label,
        "updated_at": datetime.now(KST).isoformat(),
        "raids":      existing_raids,
    })

    with open(path, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2)

    return slug


def save_weekly_schedule_snapshot(guild_id: int, week_label: str, summary: list, guild_name: str = "") -> str:
    """전체 일정(요일별 레이드 현황)을 웹 조회용 JSON에 저장."""
    slug = get_or_create_web_slug(guild_id)
    os.makedirs(RESULTS_DIR, exist_ok=True)
    path = _snapshot_path(slug)

    snapshot = {}
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                snapshot = json.load(f)
        except Exception:
            snapshot = {}

    snapshot.update({
        "guild_id":        guild_id,
        "guild_name":      guild_name or snapshot.get("guild_name", ""),
        "week_label":      week_label,
        "updated_at":      datetime.now(KST).isoformat(),
        "weekly_schedule": summary,
    })

    with open(path, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2)

    return slug


def save_member_schedule_snapshot(guild_id: int, week_label: str, members_schedule: dict, guild_name: str = "") -> str:
    """길드원별 개인 일정을 웹 조회용 JSON에 저장 (멤버 단위로 기존 스냅샷에 병합).
    members_schedule: {닉네임: [get_user_schedule 결과 리스트]}"""
    slug = get_or_create_web_slug(guild_id)
    os.makedirs(RESULTS_DIR, exist_ok=True)
    path = _snapshot_path(slug)

    snapshot = {}
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                snapshot = json.load(f)
        except Exception:
            snapshot = {}

    existing_members = snapshot.get("members", {})
    existing_members.update(members_schedule)

    snapshot.update({
        "guild_id":   guild_id,
        "guild_name": guild_name or snapshot.get("guild_name", ""),
        "week_label": week_label,
        "updated_at": datetime.now(KST).isoformat(),
        "members":    existing_members,
    })

    with open(path, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2)

    return slug


def remove_raid_from_snapshot(guild_id: int, raid_name: str):
    """미정 처리 등으로 레이드 하나를 스냅샷에서 제거."""
    slug = get_or_create_web_slug(guild_id)
    path = _snapshot_path(slug)
    if not os.path.exists(path):
        return
    try:
        with open(path, "r", encoding="utf-8") as f:
            snapshot = json.load(f)
    except Exception:
        return
    snapshot.get("raids", {}).pop(raid_name, None)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2)


def build_web_url(slug: str) -> str:
    return f"{WEB_BASE_URL.rstrip('/')}/g/{slug}"
