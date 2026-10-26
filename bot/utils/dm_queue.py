"""
로일(LoIl) - 웹 → 디스코드 DM 큐
웹 프로세스는 디스코드 연결이 없어서 직접 DM을 못 보낸다. 웹에서 큐에 쌓아두면
봇 프로세스가 주기적으로 비우면서 실제로 보낸다(성공/실패 상관없이 한 번만 시도).
"""

from bot.utils.storage import load_settings, save_settings


def queue_dm(guild_id, user_id, message: str):
    settings = load_settings()
    gid = str(guild_id)
    if gid not in settings:
        settings[gid] = {}
    settings[gid].setdefault("pending_dms", []).append({
        "user_id": str(user_id),
        "message": message,
    })
    save_settings(settings)
