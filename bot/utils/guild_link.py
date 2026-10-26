"""
로일(LoIl) - 길드 생성/가입 코드 관리

세 가지 코드가 서로 다른 역할을 한다:
- join_code:    일반 길드원이 웹에서 이 길드에 가입 신청할 때 쓰는 코드 (관리자 승인 필요)
- connect_code: 웹에서 먼저 만든 임시 길드를, 나중에 봇이 실제 서버에 들어갔을 때
                그 서버와 연결(병합)하는 1회용 코드
- web_slug:     편성 결과 공개 조회 URL용 랜덤 문자열 (web_results.py에서 별도 관리, 여기선 안 다룸)
"""

import secrets
import string
from datetime import datetime, timezone, timedelta

from bot.utils.storage import load_settings as _load, save_settings as _save

KST = timezone(timedelta(hours=9))


def _gen_code(length: int = 6) -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


# ==================== 임시 길드 생성 (봇 초대 전, 웹에서 먼저) ====================

def create_pending_guild(owner_discord_id: int, guild_name: str) -> dict:
    """웹에서 먼저 길드 그룹을 만든다. 실제 디스코드 서버가 아직 없으므로 임시 ID를 발급."""
    settings = _load()
    temp_id = "web_" + secrets.token_hex(6)
    join_code = _gen_code()
    connect_code = _gen_code()
    settings[temp_id] = {
        "pending": True,
        "guild_name": guild_name.strip(),
        "owner_discord_id": str(owner_discord_id),
        "join_code": join_code,
        "connect_code": connect_code,
        "created_at": datetime.now(KST).isoformat(),
        "join_requests": {},
        "raid_config": {},
        "time_policy": {},
    }
    _save(settings)
    return {"guild_id": temp_id, "join_code": join_code, "connect_code": connect_code}


def get_pending_guilds_for_owner(owner_discord_id: int) -> list[dict]:
    """이 디스코드 유저가 웹에서 만든(아직 봇 연결 안 된) 길드 목록."""
    settings = _load()
    return [
        {"id": gid, "name": g.get("guild_name", gid)}
        for gid, g in settings.items()
        if g.get("pending") and g.get("owner_discord_id") == str(owner_discord_id)
    ]


def is_pending(guild_id: str) -> bool:
    return bool(_load().get(str(guild_id), {}).get("pending"))


def get_or_create_join_code(guild_id) -> str:
    """실제(이미 연결된) 길드용 가입 코드. 없으면 새로 만들어 저장.
    create_pending_guild는 웹에서 먼저 만든 임시 길드에만 코드를 주므로, 봇을 바로 초대해서
    시작한 길드는 이걸로 최초 접근(관리자 홈) 시점에 코드를 발급받는다."""
    settings = _load()
    gid = str(guild_id)
    if gid not in settings:
        settings[gid] = {}
    code = settings[gid].get("join_code")
    if code:
        return code
    code = _gen_code()
    settings[gid]["join_code"] = code
    _save(settings)
    return code


# ==================== 가입 코드로 신청 (일반 길드원용) ====================

def find_guild_by_join_code(code: str) -> tuple[str, dict] | None:
    settings = _load()
    code = code.strip().upper()
    for gid, g in settings.items():
        if g.get("join_code") == code:
            return gid, g
    return None


def submit_join_request(guild_id: str, display_name: str, note: str = "", discord_user_id: str | None = None) -> bool:
    """디스코드 로그인으로 신원을 확인한 신청 — 표시 이름(닉네임)은 따로 받아서 관리자가
    알아보기 쉽게 하고, discord_user_id는 승인/거절 결과를 DM으로 보낼 때 쓴다."""
    settings = _load()
    if guild_id not in settings:
        return False
    req_id = secrets.token_hex(4)
    settings[guild_id].setdefault("join_requests", {})[req_id] = {
        "display_name": display_name.strip()[:50],
        "note": note.strip()[:200],
        "discord_user_id": discord_user_id,
        "requested_at": datetime.now(KST).isoformat(),
    }
    _save(settings)
    return True


def get_join_requests(guild_id: str) -> dict:
    return _load().get(str(guild_id), {}).get("join_requests", {})


def approve_join_request(guild_id: str, request_id: str, message: str = "") -> dict | None:
    """승인 처리. 반환값은 지워진 요청(dict, DM 발송용) — 없으면 None."""
    settings = _load()
    gdata = settings.get(str(guild_id), {})
    req = gdata.get("join_requests", {}).pop(request_id, None)
    if not req:
        return None
    gdata.setdefault("approved_members", []).append(req["display_name"])
    _save(settings)
    return req


def reject_join_request(guild_id: str, request_id: str, reason: str = "") -> dict | None:
    """거절 처리. 반환값은 지워진 요청(dict, DM 발송용) — 없으면 None."""
    settings = _load()
    gdata = settings.get(str(guild_id), {})
    req = gdata.get("join_requests", {}).pop(request_id, None)
    if not req:
        return None
    _save(settings)
    return req


# ==================== 봇 연결 (임시 길드 → 실제 디스코드 서버) ====================

def find_guild_by_connect_code(code: str) -> tuple[str, dict] | None:
    settings = _load()
    code = code.strip().upper()
    for gid, g in settings.items():
        if g.get("pending") and g.get("connect_code") == code:
            return gid, g
    return None


def merge_pending_into_real_guild(temp_id: str, real_guild_id: int) -> bool:
    """연결 코드 확인 후 호출. 임시 길드에 저장해둔 설정(레이드 카탈로그, 시간 정책 등)을
    실제 디스코드 길드 ID로 옮겨 붙인다. 실제 길드에 이미 값이 있으면(예: 봇 재초대) 그쪽을 우선한다."""
    settings = _load()
    pending = settings.pop(temp_id, None)
    if not pending:
        return False

    real_id = str(real_guild_id)
    existing = settings.get(real_id, {})
    merged = {**pending, **existing}
    merged.pop("pending", None)
    merged.pop("connect_code", None)
    settings[real_id] = merged
    _save(settings)
    return True
