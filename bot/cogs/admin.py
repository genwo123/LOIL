"""
로일(LoIl) - 관리자 Cog v2
- /봇상태 : 봇 상태 + API 통계
- /캐시초기화 : API 캐시 삭제
※ /설정확인은 setup.py의 패널 버튼으로 통합 (중복 제거)
"""

import discord
from discord.ext import commands
from discord import app_commands
from bot.utils.lostark_api import get_api_stats, clear_cache
from bot.config.settings import BOT_VERSION


class AdminCog(commands.Cog, name="AdminCog"):

    def __init__(self, bot):
        self.bot = bot

    # ==================== /봇상태 ====================

    @app_commands.command(name="봇상태", description="봇의 현재 상태를 확인합니다")
    async def check_status(self, interaction: discord.Interaction):

        latency   = round(self.bot.latency * 1000)
        api_stats = get_api_stats()

        if latency < 100:
            status_icon = "🟢"
            status_text = "매우 빠름"
            color       = 0x57F287
        elif latency < 300:
            status_icon = "🟡"
            status_text = "보통"
            color       = 0xFEE75C
        else:
            status_icon = "🔴"
            status_text = "느림"
            color       = 0xED4245

        from bot.utils.raid_schedule import get_raids
        raid_count = len(get_raids(interaction.guild_id))

        embed = discord.Embed(
            title="🤖 로일봇 상태",
            color=color
        )
        embed.add_field(
            name="📡 응답속도",
            value=f"{status_icon} {latency}ms ({status_text})",
            inline=True
        )
        embed.add_field(
            name="🌐 연결 서버",
            value=f"{len(self.bot.guilds)}개",
            inline=True
        )
        embed.add_field(
            name="🔖 버전",
            value=f"v{BOT_VERSION}",
            inline=True
        )
        embed.add_field(
            name="🔑 API 키",
            value=f"{api_stats['total_keys']}개 등록",
            inline=True
        )
        embed.add_field(
            name="💾 캐시",
            value=f"{api_stats['cache_size']}개 항목",
            inline=True
        )
        embed.add_field(
            name="📋 등록 레이드",
            value=f"{raid_count}개",
            inline=True
        )
        embed.set_footer(text="설정 변경은 ⚙️ 로일-설정 채널에서 해주세요")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ==================== /캐시초기화 ====================

    @app_commands.command(name="캐시초기화", description="API 캐시를 초기화합니다 (관리자 전용)")
    @app_commands.checks.has_permissions(administrator=True)
    async def clear_api_cache(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            cleared = clear_cache()
            embed = discord.Embed(
                title="✅ 캐시 초기화 완료",
                description=f"API 캐시 **{cleared}개** 항목이 삭제되었습니다.",
                color=0x57F287
            )
            embed.set_footer(text="다음 조회부터 최신 데이터가 사용됩니다")
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            print(f"[admin] 캐시 초기화 실패: {e}")
            await interaction.followup.send("❌ 캐시 초기화에 실패했습니다. 잠시 후 다시 시도해주세요.", ephemeral=True)

    @clear_api_cache.error
    async def cache_error(self, interaction: discord.Interaction, error):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message("❌ 관리자만 사용 가능합니다.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(AdminCog(bot))