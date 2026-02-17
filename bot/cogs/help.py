"""
도움말 명령어
- /도움말 - 전체 명령어 목록
- /명령어 - 특정 명령어 상세 설명
"""

import discord
from discord.ext import commands
from discord import app_commands
from bot.config.settings import BOT_VERSION


class HelpCog(commands.Cog):
    """도움말 명령어 모음"""
    
    def __init__(self, bot):
        self.bot = bot
    
    # ==================== /도움말 ====================
    
    @app_commands.command(name="도움말", description="로일 봇 명령어 목록을 확인합니다")
    async def help_command(self, interaction: discord.Interaction):
        """전체 명령어 목록"""
        
        embed = discord.Embed(
            title="📋 로일(LoIl) 봇 명령어",
            description="로스트아크 길드 레이드 자동화 봇",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="⚙️ 설정",
            value=(
                "`/설정 [시트URL]` - 구글 시트 연동\n"
                "`/설정확인` - 현재 설정 보기"
            ),
            inline=False
        )
        embed.add_field(
            name="📅 일정",
            value=(
                "`/일정` - 이번 주 레이드 일정\n"
                "`/내일정 [닉네임]` - 내 일정 조회"
            ),
            inline=False
        )
        embed.add_field(
            name="⚔️ 파티",
            value=(
                "`/파티추천 [레이드명]` - AI 파티 편성 추천\n"
                "`/시너지 [직업1,직업2,...]` - 시너지 분석"
            ),
            inline=False
        )
        embed.add_field(
            name="🔧 관리",
            value=(
                "`/봇상태` - 봇 상태 확인\n"
                "`/캐시초기화` - API 캐시 초기화 (관리자)"
            ),
            inline=False
        )
        embed.add_field(
            name="ℹ️ 기타",
            value=(
                "`/핑` - 응답속도 확인\n"
                "`/정보` - 봇 정보\n"
                "`/도움말` - 명령어 목록"
            ),
            inline=False
        )
        
        embed.set_footer(text=f"로일 v{BOT_VERSION} | 문제가 있으면 관리자에게 문의하세요!")
        
        await interaction.response.send_message(embed=embed)
    
    
    # ==================== /정보 ====================
    
    @app_commands.command(name="정보", description="로일 봇 정보를 확인합니다")
    async def show_info(self, interaction: discord.Interaction):
        """봇 정보"""
        
        embed = discord.Embed(
            title="🤖 로일(LoIl) 봇 정보",
            description="로스트아크 길드 레이드 자동화 봇",
            color=discord.Color.blue()
        )
        embed.add_field(name="버전", value=f"v{BOT_VERSION}", inline=True)
        embed.add_field(name="서버", value=f"{len(self.bot.guilds)}개", inline=True)
        embed.add_field(name="응답속도", value=f"{round(self.bot.latency * 1000)}ms", inline=True)
        embed.add_field(
            name="주요 기능",
            value=(
                "📊 구글 시트 연동\n"
                "🤖 AI 파티 편성 추천\n"
                "⚡ 시너지 분석\n"
                "📅 레이드 일정 관리"
            ),
            inline=False
        )
        embed.set_footer(text="Made for Lost Ark Guilds 🎮")
        
        await interaction.response.send_message(embed=embed)


# ==================== Cog 등록 ====================

async def setup(bot):
    await bot.add_cog(HelpCog(bot))