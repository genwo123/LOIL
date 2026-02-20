"""
로일(LoIl) - 도움말 Cog
- /도움말 : 전체 명령어 목록
- /핑 : 응답속도 확인
- /정보 : 봇 정보
"""

import discord
from discord.ext import commands
from discord import app_commands
from bot.config.settings import BOT_VERSION


class HelpCog(commands.Cog, name="HelpCog"):

    def __init__(self, bot):
        self.bot = bot

    # ==================== /도움말 ====================

    @app_commands.command(name="도움말", description="로일 봇 명령어 목록을 확인합니다")
    async def help_command(self, interaction: discord.Interaction):

        embed = discord.Embed(
            title="📋 로일(LoIl) 명령어 목록",
            description="로스트아크 길드 레이드 자동화 봇",
            color=0x5865F2
        )

        embed.add_field(
            name="⚙️ 설정 (관리자 전용)",
            value=(
                "`/설정패널` — 설정 상태판 다시 표시\n"
                "`/채널초기화` — 로일 채널 다시 생성\n"
                "`/이번주갱신` — 이번주-레이드 채널 수동 갱신"
            ),
            inline=False
        )
        embed.add_field(
            name="📅 일정",
            value=(
                "`/일정` — 이번 주 레이드 일정 갱신\n"
                "`/내일정 [닉네임]` — 개인 일정 조회 (스레드)"
            ),
            inline=False
        )
        embed.add_field(
            name="⚔️ 파티",
            value=(
                "`/파티추천 [레이드명]` — AI 파티 편성 추천\n"
                "`/시너지 [직업1,직업2,...]` — 시너지 분석"
            ),
            inline=False
        )
        embed.add_field(
            name="🔧 관리",
            value=(
                "`/설정확인` — 현재 설정 현황\n"
                "`/봇상태` — 봇 상태 확인\n"
                "`/캐시초기화` — API 캐시 초기화 (관리자)"
            ),
            inline=False
        )
        embed.add_field(
            name="ℹ️ 기타",
            value=(
                "`/핑` — 응답속도 확인\n"
                "`/정보` — 봇 정보\n"
                "`/도움말` — 명령어 목록"
            ),
            inline=False
        )

        embed.add_field(
            name="💡 처음 사용하신다면",
            value=(
                "1️⃣ **📢 로일-공지** 채널에서 '설정 시작하기' 버튼 클릭\n"
                "2️⃣ 구글 시트 URL 등록\n"
                "3️⃣ 로아 API 키 등록\n"
                "4️⃣ Gemini API 키 등록\n"
                "5️⃣ 완료! `/일정` 으로 바로 사용 가능"
            ),
            inline=False
        )

        embed.set_footer(text=f"로일 v{BOT_VERSION} · 문제가 있으면 관리자에게 문의하세요!")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ==================== /핑 ====================

    @app_commands.command(name="핑", description="봇 응답속도를 확인합니다")
    async def ping(self, interaction: discord.Interaction):

        latency = round(self.bot.latency * 1000)

        if latency < 100:
            status = "🟢 매우 빠름"
            color  = 0x57F287
        elif latency < 300:
            status = "🟡 보통"
            color  = 0xFEE75C
        else:
            status = "🔴 느림"
            color  = 0xED4245

        embed = discord.Embed(
            title="🏓 퐁!",
            description=f"응답속도: **{latency}ms** {status}",
            color=color
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ==================== /정보 ====================

    @app_commands.command(name="정보", description="로일 봇 정보를 확인합니다")
    async def show_info(self, interaction: discord.Interaction):

        embed = discord.Embed(
            title="🤖 로일(LoIl) 봇 정보",
            description="로스트아크 길드 레이드 자동화 봇",
            color=0x5865F2
        )
        embed.add_field(name="버전",      value=f"v{BOT_VERSION}",               inline=True)
        embed.add_field(name="서버",      value=f"{len(self.bot.guilds)}개",      inline=True)
        embed.add_field(name="응답속도",  value=f"{round(self.bot.latency * 1000)}ms", inline=True)
        embed.add_field(
            name="주요 기능",
            value=(
                "📊 구글 시트 연동\n"
                "🤖 AI 파티 편성 추천\n"
                "⚡ 시너지 분석\n"
                "📅 레이드 일정 자동 관리\n"
                "🧵 스레드 방식 개인 조회"
            ),
            inline=False
        )
        embed.set_footer(text="Made for Lost Ark Guilds 🎮")
        await interaction.response.send_message(embed=embed, ephemeral=True)


# ==================== Cog 등록 ====================

async def setup(bot):
    await bot.add_cog(HelpCog(bot))