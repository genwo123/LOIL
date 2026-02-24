"""
로일(LoIl) - 멤버 연결 유틸
Discord 유저 ID ↔ 시트 탭 이름 매핑 관리

저장 구조 (guild_settings.json):
{
  "guild_id": {
    "members": {
      "discord_user_id": "시트탭이름"  (예: "123456789": "거니")
    },
    "absences": {
      "2026-W08": ["거니", "자두"]     (이번주 불참자)
    }
  }
}
"""

import json
import os
from datetime import datetime, timezone, timedelta

SETTINGS_FILE = "bot/data/guild_settings.json"

# ==================== 설정 로드/저장 ====================

def load_settings() -> dict:
    if not os.path.exists(SETTINGS_FILE):
        return {}
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_settings(data: dict):
    os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def _guild_data(guild_id: int) -> dict:
    return load_settings().get(str(guild_id), {})

def _update(guild_id: int, key: str, value):
    settings = load_settings()
    gid = str(guild_id)
    if gid not in settings:
        settings[gid] = {}
    settings[gid][key] = value
    save_settings(settings)


# ==================== 멤버 연결 ====================

def get_sheet_name(guild_id: int, user_id: int) -> str | None:
    """Discord 유저 ID → 시트 탭 이름 반환 (없으면 None)"""
    members = _guild_data(guild_id).get("members", {})
    return members.get(str(user_id))

def set_sheet_name(guild_id: int, user_id: int, sheet_name: str):
    """Discord 유저 ID ↔ 시트 탭 이름 저장"""
    settings = load_settings()
    gid = str(guild_id)
    if gid not in settings:
        settings[gid] = {}
    if "members" not in settings[gid]:
        settings[gid]["members"] = {}
    settings[gid]["members"][str(user_id)] = sheet_name
    save_settings(settings)

def is_linked(guild_id: int, user_id: int) -> bool:
    """멤버 연결 여부"""
    return get_sheet_name(guild_id, user_id) is not None


# ==================== 불참 관리 ====================

def _week_key() -> str:
    """
    로아 주차 키 - 수요일 초기화 기준
    수요일 09:00 KST 이후 → 이번 주
    수요일 09:00 KST 이전 → 저번 주
    예: 2026-W08-WED
    """
    now = datetime.now(timezone(timedelta(hours=9)))
    # 수요일=2, 09:00 이전이면 전날 기준으로 계산
    if now.weekday() < 2 or (now.weekday() == 2 and now.hour < 9):
        # 아직 이번 로아 주차 시작 전 → 지난 수요일 기준
        days_since_wed = (now.weekday() - 2) % 7
        ref = now - timedelta(days=days_since_wed)
    else:
        # 이번 수요일 09:00 이후
        days_since_wed = (now.weekday() - 2) % 7
        ref = now - timedelta(days=days_since_wed)
    return ref.strftime("%Y-W%V-WED")

def set_absence(guild_id: int, sheet_name: str):
    """이번주 불참 등록"""
    settings = load_settings()
    gid = str(guild_id)
    week = _week_key()
    if gid not in settings:
        settings[gid] = {}
    if "absences" not in settings[gid]:
        settings[gid]["absences"] = {}
    if week not in settings[gid]["absences"]:
        settings[gid]["absences"][week] = []
    if sheet_name not in settings[gid]["absences"][week]:
        settings[gid]["absences"][week].append(sheet_name)
    save_settings(settings)

def remove_absence(guild_id: int, sheet_name: str):
    """불참 취소"""
    settings = load_settings()
    gid = str(guild_id)
    week = _week_key()
    try:
        absences = settings[gid]["absences"][week]
        if sheet_name in absences:
            absences.remove(sheet_name)
        save_settings(settings)
    except (KeyError, TypeError):
        pass

def get_absences(guild_id: int) -> list[str]:
    """이번주 불참자 목록"""
    week = _week_key()
    return _guild_data(guild_id).get("absences", {}).get(week, [])

def is_absent(guild_id: int, sheet_name: str) -> bool:
    """이번주 불참 여부"""
    return sheet_name in get_absences(guild_id)