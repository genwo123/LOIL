"""
로일(LoIl) - 일정 Cog
역할: 수요일 자동 갱신용 update_weekly_channel() 제공
      개인 일정 조회는 schedule_view.py (🗒│일정조회) 가 담당
"""

import discord
from discord.ext import commands
from discord import app_commands
import json
import os
from typing import Optional

from bot.utils.sheets import get_all_data, get_weekly_summary
from bot.utils.image_renderer import render_weekly_raids
from bot.config.channels import CH_SCHEDULE, get_channel

# ==================== 설정 ====================

SETTINGS_FILE = "bot/data/guild_settings.json"

def get_sheet_url(guild_id: int) -> Optional[str]:
    if not os.path.exists(SETTINGS_FILE):
        return None
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f).get(str(guild_id), {}).get("sheet_url")
    except Exception:
        return None


# ==================== ScheduleCog ====================

class ScheduleCog(commands.Cog, name="ScheduleCog"):

    def __init__(self, bot):
        self.bot = bot

    async def update_weekly_channel(self, guild: discord.Guild) -> bool:
        """
        🗒│일정조회 채널에 이번주 전체 레이드 이미지 갱신
        main.py 수요일 스케줄러에서 호출
        """
        url = get_sheet_url(guild.id)
        if not url:
            return False

        data = get_all_data(url)
        if not data:
            return False

        summary  = get_weekly_summary(data)
        buf      = render_weekly_raids(summary)
        img_file = discord.File(fp=buf, filename="weekly.png")

        # 🗒│일정조회 채널 (구버전 채널명 폴백 포함)
        channel = get_channel(guild, CH_SCHEDULE)
        if not channel:
            return False

        # 기존 핀 봇 메시지 삭제 후 재전송 (이미지는 edit 불가)
        try:
            pins = await channel.pins()
            for pin in pins:
                if pin.author == guild.me:
                    await pin.delete()
        except Exception:
            pass

        msg = await channel.send(file=img_file)
        try:
            await msg.pin()
        except Exception:
            pass

        return True

    # ── /이번주갱신 (관리자) ──

    @app_commands.command(name="이번주갱신", description="일정조회 채널을 수동 갱신합니다 (관리자)")
    @app_commands.checks.has_permissions(administrator=True)
    async def refresh_weekly(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True, ephemeral=True)
        ok = await self.update_weekly_channel(interaction.guild)
        if ok:
            ch = get_channel(interaction.guild, CH_SCHEDULE)
            await interaction.followup.send(
                f"✅ {ch.mention} 채널이 갱신됐습니다!", ephemeral=True
            )
        else:
            await interaction.followup.send(
                "❌ 시트가 연동되지 않았습니다.\n⚙│봇설정 채널에서 먼저 설정해주세요.",
                ephemeral=True
            )

    @refresh_weekly.error
    async def refresh_error(self, interaction, error):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message("❌ 관리자만 사용 가능합니다.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(ScheduleCog(bot))