"""
로일(LoIl) - 채널 청소 공통 유틸
공지/레이드편성/일정조회 채널에서 핀 제외 메시지를 정리할 때 공통으로 쓴다.
"""

import discord


async def purge_channel(channel: discord.TextChannel, limit: int = 200, skip_ids: set[int] | None = None) -> int:
    pinned = await channel.pins()
    keep_ids = {m.id for m in pinned} | (skip_ids or set())
    deleted = 0
    async for msg in channel.history(limit=limit):
        if msg.id not in keep_ids:
            try:
                await msg.delete()
                deleted += 1
            except Exception:
                pass
    return deleted
