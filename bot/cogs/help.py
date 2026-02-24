"""
로일(LoIl) - 도움말 Cog v3
변경사항:
- /설정확인 제거 (admin_v2에서 삭제됨)
- 파티 편성 명령어 구조 반영 (주간/개별/시너지)
- 스타일 선택 안내 추가
- /정보 명령어 개선
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
                "`/설정패널` — 설정 패널 다시 표시\n"
                "`/이번주갱신` — 이번주-레이드 채널 수동 갱신\n"
                "`/캐시초기화` — API 캐시 삭제"
            ),
            inline=False
        )

        # ── 일정 ──
        embed.add_field(
            name="📅 일정",
            value=(
                "`/일정` — 이번주-레이드 채널 갱신\n"
                "**내 일정 보기** — 이번주-레이드 채널 버튼 클릭 → 닉네임 입력 → 스레드 생성\n"
                "　스레드 안에서 스타일 B(타임라인) ↔ D(다크카드) 전환 가능"
            ),
            inline=False
        )

        # ── 파티 편성 ──
        embed.add_field(
            name="⚔️ 파티 편성",
            value=(
                "**파티-편성 채널 버튼으로 사용:**\n"
                "　`📅 주간 전체 편성` — 레이드 체크박스 선택 → AI 자동 편성\n"
                "　`⚔️ 개별 레이드 편성` — 특정 레이드 하나만 AI 편성\n"
                "　`⚡ 시너지 분석` — 직업 목록 입력 → 시너지 분석\n"
                "　`🔄 새로고침` — 패널 갱신\n\n"
                "**슬래시 명령어:**\n"
                "`/파티추천 [레이드명]` — AI 파티 편성 추천\n"
                "`/시너지 [직업1,직업2,...]` — 시너지 분석"
            ),
            inline=False
        )

        # ── 별명 ──
        embed.add_field(
            name="🏷️ 별명",
            value=(
                "`/별명추가 [대상] [별명]` — 닉네임 / 직업 별명 추가 요청\n"
                "　관리자 승인 후 적용 · 봇-관리 채널에서 확인"
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
                "1️⃣ **로일-설정** 채널 → 시트 URL 등록\n"
                "2️⃣ **로일-설정** 채널 → 로아 API 키 등록\n"
                "3️⃣ (선택) Gemini API 키 등록\n"
                "4️⃣ `/일정` 으로 이번주-레이드 채널 갱신\n"
                "5️⃣ **파티-편성** 채널에서 AI 파티 편성 시작! 🎉"
            ),
            inline=False
        )

        embed.set_footer(text=f"로일 v{BOT_VERSION} · 문의는 관리자에게 · 설정은 ⚙️ 로일-설정 채널에서")
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

        embed.add_field(name="🔖 버전",    value=f"v{BOT_VERSION}",        inline=True)
        embed.add_field(name="📡 응답속도", value=f"{latency}ms",           inline=True)
        embed.add_field(name="🌐 서버 수",  value=f"{guild_cnt}개",         inline=True)

        embed.add_field(
            name="✨ 주요 기능",
            value=(
                "• 구글 시트 기반 레이드 일정 관리\n"
                "• AI(Gemini) 파티 자동 편성\n"
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