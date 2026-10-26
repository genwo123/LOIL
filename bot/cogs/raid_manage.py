"""
로일(LoIl) - 레이드 관리 Cog
🛡│레이드편성 채널 관리자 전용 기능

일정 추가/수정/삭제/클리어/토글은 웹 대시보드로 이전됨(2026-08-25) — 아래는
디스코드에 남겨둔 "시트 → 봇 새로고침"만 담당. 시트 자체 CRUD는 web/admin.py 참고.
"""

import discord
from discord.ext import commands
from discord import app_commands


class RaidManageCog(commands.Cog, name="RaidManageCog"):

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="레이드갱신", description="시트 변경사항을 봇에 반영합니다")
    async def refresh_raid_cmd(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        schedule_cog = interaction.client.cogs.get("ScheduleCog")
        if schedule_cog:
            ok = await schedule_cog.update_weekly_channel(interaction.guild)
            if ok:
                await interaction.followup.send("✅ 이번주레이드 채널이 갱신되었습니다!", ephemeral=True)
                return
        await interaction.followup.send("❌ 갱신에 실패했습니다.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(RaidManageCog(bot))
