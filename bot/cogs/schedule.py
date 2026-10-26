"""
로일(LoIl) - 일정 Cog
역할: 수요일 자동 갱신용 update_weekly_channel() 제공
      개인 일정 조회는 schedule_view.py (🗒│일정조회) 가 담당
"""

import discord
from discord.ext import commands
from discord import app_commands

from bot.utils.raid_schedule import get_weekly_summary
from bot.utils.image_renderer import render_weekly_raids
from bot.config.channels import CH_SCHEDULE, get_channel


# ==================== ScheduleCog ====================

class ScheduleCog(commands.Cog, name="ScheduleCog"):

    def __init__(self, bot):
        self.bot = bot

    async def update_weekly_channel(self, guild: discord.Guild) -> bool:
        """
        🗒│일정조회 채널에 이번주 전체 레이드 이미지 갱신
        main.py 수요일 스케줄러 또는 /이번주갱신에서 호출
        """
        summary = get_weekly_summary(guild.id)
        if not summary:
            return False

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
                "❌ 이번주 예정된 레이드가 없습니다.",
                ephemeral=True
            )

    @refresh_weekly.error
    async def refresh_error(self, interaction, error):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message("❌ 관리자만 사용 가능합니다.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(ScheduleCog(bot))