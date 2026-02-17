"""
관리자 명령어
- /설정확인 - 현재 설정 보기
- /캐시초기화 - 캐시 삭제
- /봇상태 - 봇 상태 확인
"""

import discord
from discord.ext import commands
from discord import app_commands
from bot.utils.lostark_api import get_api_stats, clear_cache
from bot.cogs.schedule import guild_sheets
from bot.config.settings import BOT_VERSION, GEMINI_API_KEY, LOSTARK_API_KEYS


class AdminCog(commands.Cog):
    """관리자 명령어 모음"""
    
    def __init__(self, bot):
        self.bot = bot
    
    # ==================== /설정확인 ====================
    
    @app_commands.command(name="설정확인", description="현재 봇 설정을 확인합니다")
    async def check_settings(self, interaction: discord.Interaction):
        """설정 확인"""
        
        # 시트 연동 여부
        sheet_url = guild_sheets.get(interaction.guild_id)
        sheet_status = "✅ 연동됨" if sheet_url else "❌ 미연동"
        
        # API 통계
        api_stats = get_api_stats()
        
        embed = discord.Embed(
            title="⚙️ 로일 봇 설정 확인",
            color=discord.Color.blue()
        )
        embed.add_field(name="봇 버전", value=f"v{BOT_VERSION}", inline=True)
        embed.add_field(name="응답속도", value=f"{round(self.bot.latency * 1000)}ms", inline=True)
        embed.add_field(name="서버 수", value=f"{len(self.bot.guilds)}개", inline=True)
        embed.add_field(name="구글 시트", value=sheet_status, inline=True)
        embed.add_field(name="Gemini AI", value="✅ 설정됨" if GEMINI_API_KEY else "❌ 없음", inline=True)
        embed.add_field(name="로스트아크 API", value=f"✅ {len(LOSTARK_API_KEYS)}개", inline=True)
        embed.add_field(name="캐시 크기", value=f"{api_stats['cache_size']}개", inline=True)
        
        if sheet_url:
            embed.add_field(
                name="연동된 시트",
                value=f"[시트 열기]({sheet_url})",
                inline=False
            )
        
        await interaction.response.send_message(embed=embed)
    
    
    # ==================== /캐시초기화 ====================
    
    @app_commands.command(name="캐시초기화", description="API 캐시를 초기화합니다 (관리자 전용)")
    async def clear_api_cache(self, interaction: discord.Interaction):
        """캐시 초기화"""
        
        # 관리자 권한 확인
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ 관리자만 사용 가능한 명령어입니다!",
                ephemeral=True
            )
            return
        
        clear_cache()
        
        await interaction.response.send_message(
            "✅ API 캐시가 초기화되었습니다!\n"
            "다음 조회부터 최신 데이터로 업데이트됩니다."
        )
    
    
    # ==================== /봇상태 ====================
    
    @app_commands.command(name="봇상태", description="봇의 현재 상태를 확인합니다")
    async def check_status(self, interaction: discord.Interaction):
        """봇 상태 확인"""
        
        api_stats = get_api_stats()
        latency = round(self.bot.latency * 1000)
        
        # 상태 판단
        if latency < 100:
            status = "🟢 매우 빠름"
            color = discord.Color.green()
        elif latency < 300:
            status = "🟡 보통"
            color = discord.Color.yellow()
        else:
            status = "🔴 느림"
            color = discord.Color.red()
        
        embed = discord.Embed(
            title="🤖 로일 봇 상태",
            color=color
        )
        embed.add_field(name="상태", value=status, inline=True)
        embed.add_field(name="응답속도", value=f"{latency}ms", inline=True)
        embed.add_field(name="연결된 서버", value=f"{len(self.bot.guilds)}개", inline=True)
        embed.add_field(name="API 키", value=f"{api_stats['total_keys']}개", inline=True)
        embed.add_field(name="캐시", value=f"{api_stats['cache_size']}개 항목", inline=True)
        embed.add_field(name="버전", value=f"v{BOT_VERSION}", inline=True)
        
        await interaction.response.send_message(embed=embed)


# ==================== Cog 등록 ====================

async def setup(bot):
    await bot.add_cog(AdminCog(bot))