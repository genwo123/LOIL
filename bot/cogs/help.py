"""
로일(LoIl) - 도움말 Cog v4
변경사항:
- ⚔️│레이드설정 채널 안내 추가
- 일정 추가/수정/삭제 명령어 반영 (/일정추가, /일정수정, /일정삭제)
- 시작 가이드 업데이트
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
            description="로스트아크 길드 레이드 자동화 봇 · v" + BOT_VERSION,
            color=0x5865F2
        )

        # ── 설정 ──
        embed.add_field(
            name="⚙️ 설정 (관리자 전용)",
            value=(
                "`/설정패널` — 봇설정 패널 다시 표시\n"
                "`/레이드설정패널` — 레이드설정 패널 다시 표시\n"
                "`/캐시초기화` — API 캐시 삭제"
            ),
            inline=False
        )

        # ── 레이드 카탈로그 ──
        embed.add_field(
            name="⚔️ 레이드 카탈로그 (관리자 전용)",
            value=(
                "**⚔️│레이드설정 채널 버튼으로 사용:**\n"
                "　레이드 활성/비활성 · 슬롯 수 설정 · 소요시간 설정\n"
                "　변경사항은 구글 시트에 즉시 반영됩니다."
            ),
            inline=False
        )

        # ── 일정 관리 ──
        embed.add_field(
            name="📅 일정 관리 (관리자 전용)",
            value=(
                "**🛡│레이드편성 채널 버튼으로 사용:**\n"
                "　`일정 추가` — 이번 주 시트에 레이드 일정 추가\n"
                "　`일정 수정` — 등록된 일정 수정\n"
                "　`일정 삭제` — 등록된 일정 삭제\n\n"
                "**슬래시 명령어:**\n"
                "`/일정추가` · `/일정수정` · `/일정삭제`\n"
                "`/레이드클리어` · `/레이드토글` · `/레이드갱신`"
            ),
            inline=False
        )

        # ── 일정 조회 ──
        embed.add_field(
            name="🗒 일정 조회",
            value=(
                "**🗒│일정조회 채널 버튼으로 사용:**\n"
                "　`내 일정 보기` — 길드원 선택 → 개인 일정 이미지 스레드 생성\n"
                "　`전체 일정 보기` — 이번 주 전체 레이드 일정 이미지\n"
                "　스레드는 **24시간 후 자동 삭제**됩니다."
            ),
            inline=False
        )

        # ── 파티 편성 ──
        embed.add_field(
            name="🛡 파티 편성",
            value=(
                "**🛡│레이드편성 채널 버튼으로 사용:**\n"
                "　`주간 전체 편성` — 레이드 선택 → AI 자동 편성\n"
                "　`개별 레이드 편성` — 특정 레이드 하나만 AI 편성\n"
                "　`시너지 분석` — 직업 목록 입력 → 시너지 분석\n\n"
                "**슬래시 명령어:**\n"
                "`/시너지` — 시너지 분석\n"
                "`/파티패널` — 파티 편성 패널 다시 표시 (관리자)"
            ),
            inline=False
        )

        # ── 별명 ──
        embed.add_field(
            name="🏷️ 별명",
            value=(
                "`/별명추가` — 직업 / 각인 별명 추가 요청\n"
                "`/별명목록` — 등록된 별명 확인"
            ),
            inline=False
        )

        # ── 기타 ──
        embed.add_field(
            name="ℹ️ 기타",
            value=(
                "`/봇상태` — 응답속도 · API 키 · 연동 상태 확인\n"
                "`/핑` — 응답속도 확인\n"
                "`/정보` — 봇 상세 정보\n"
                "`/도움말` — 이 목록"
            ),
            inline=False
        )

        # ── 시작 가이드 ──
        embed.add_field(
            name="💡 처음 사용하신다면",
            value=(
                "1️⃣ **⚙│봇설정** 채널 → 시트 URL · API 키 등록\n"
                "2️⃣ **⚔️│레이드설정** 채널 → 운영할 레이드 활성화 · 슬롯 수 설정\n"
                "3️⃣ **🛡│레이드편성** 채널 → 일정 추가 후 AI 파티 편성\n"
                "4️⃣ **📡│공지** 채널 → 일정 입력 요청 시작 🎉"
            ),
            inline=False
        )

        embed.set_footer(text=f"로일 v{BOT_VERSION} · 문의는 관리자에게 · 설정은 ⚙️ 봇설정 채널에서")
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
            description=f"응답속도: **{latency}ms** · {status}",
            color=color
        )
        embed.set_footer(text=f"로일 v{BOT_VERSION}")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ==================== /정보 ====================

    @app_commands.command(name="정보", description="로일 봇 정보를 확인합니다")
    async def info(self, interaction: discord.Interaction):

        latency   = round(self.bot.latency * 1000)
        guild_cnt = len(self.bot.guilds)

        embed = discord.Embed(
            title="🤖 로일(LoIl) 봇 정보",
            description="로스트아크 길드 레이드 자동화 · AI 파티 편성 봇",
            color=0x9B59B6
        )

        embed.add_field(name="🔖 버전",    value=f"v{BOT_VERSION}",  inline=True)
        embed.add_field(name="📡 응답속도", value=f"{latency}ms",     inline=True)
        embed.add_field(name="🌐 서버 수",  value=f"{guild_cnt}개",   inline=True)

        embed.add_field(
            name="✨ 주요 기능",
            value=(
                "• 구글 시트 기반 레이드 일정 관리\n"
                "• AI(Gemini) 파티 자동 편성\n"
                "• 레이드 카탈로그 관리 (활성/슬롯/소요시간)\n"
                "• 시간 충돌 자동 감지 · 서폿 배치 자동화\n"
                "• 로아 API 키 풀링 (최대 3개)\n"
                "• 개인 일정 스레드 자동 생성"
            ),
            inline=False
        )

        embed.add_field(
            name="🔗 관련 링크",
            value=(
                "• [로아 API 키 발급](https://developer-lostark.game.onstove.com/)\n"
                "• [Gemini API 키 발급](https://aistudio.google.com/)\n"
                "• [구글 시트 템플릿](https://docs.google.com/spreadsheets)"
            ),
            inline=False
        )

        embed.set_footer(text="로일(LoIl) · Made for Lost Ark Guild Management")
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(HelpCog(bot))