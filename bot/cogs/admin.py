"""
로일(LoIl) - 관리자 Cog
- /봇상태 : 봇 상태 확인
- /캐시초기화 : API 캐시 삭제
- /설정확인 : 현재 설정 현황
"""

import discord
from discord.ext import commands
from discord import app_commands
import json
import os
from bot.utils.lostark_api import get_api_stats, clear_cache
from bot.config.settings import BOT_VERSION

# ==================== 설정 불러오기 ====================

SETTINGS_FILE = "bot/data/guild_settings.json"

def get_guild_setting(guild_id: int) -> dict:
    if not os.path.exists(SETTINGS_FILE):
        return {}
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            settings = json.load(f)
        return settings.get(str(guild_id), {})
    except Exception:
        return {}


# ==================== AdminCog ====================

class AdminCog(commands.Cog, name="AdminCog"):

    def __init__(self, bot):
        self.bot = bot

    # ==================== /설정확인 ====================

    @app_commands.command(name="설정확인", description="현재 봇 설정을 확인합니다")
    async def check_settings(self, interaction: discord.Interaction):

        setting = get_guild_setting(interaction.guild_id)

        sheet_url    = setting.get("sheet_url", "")
        loa_keys_raw = setting.get("loa_api_keys", "")
        gemini_key   = setting.get("gemini_api_key", "")
        loa_keys     = [k for k in loa_keys_raw.split(",") if k] if loa_keys_raw else []

        api_stats = get_api_stats()
        latency   = round(self.bot.latency * 1000)

        # 상태 색상
        all_done = bool(sheet_url and loa_keys and gemini_key)
        color    = 0x57F287 if all_done else 0x5865F2

        embed = discord.Embed(
            title="⚙️ 로일 설정 현황",
            color=color
        )

        embed.add_field(name="🤖 봇 버전",    value=f"v{BOT_VERSION}",                   inline=True)
        embed.add_field(name="📡 응답속도",   value=f"{latency}ms",                       inline=True)
        embed.add_field(name="🌐 서버 수",    value=f"{len(self.bot.guilds)}개",           inline=True)
        embed.add_field(
            name="📊 구글 시트",
            value=f"[시트 열기]({sheet_url})" if sheet_url else "🔴 미연동",
            inline=True
        )
        embed.add_field(
            name="🔑 로아 API 키",
            value=f"🟢 {len(loa_keys)}개 등록" if loa_keys else "🔴 미등록",
            inline=True
        )
        embed.add_field(
            name="✨ Gemini API",
            value="🟢 등록됨" if gemini_key else "🔴 미등록",
            inline=True
        )
        embed.add_field(name="💾 캐시",       value=f"{api_stats['cache_size']}개 항목",  inline=True)
        embed.add_field(name="🔧 API 키 수",  value=f"{api_stats['total_keys']}개",        inline=True)

        embed.set_footer(text="설정 변경은 ⚙️ 로일-설정 채널에서 해주세요")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ==================== /봇상태 ====================

    @app_commands.command(name="봇상태", description="봇의 현재 상태를 확인합니다")
    async def check_status(self, interaction: discord.Interaction):

        api_stats = get_api_stats()
        latency   = round(self.bot.latency * 1000)

        if latency < 100:
            status_text = "🟢 매우 빠름"
            color       = 0x57F287
        elif latency < 300:
            status_text = "🟡 보통"
            color       = 0xFEE75C
        else:
            status_text = "🔴 느림"
            color       = 0xED4245

        embed = discord.Embed(title="🤖 로일 봇 상태", color=color)
        embed.add_field(name="상태",       value=status_text,                      inline=True)
        embed.add_field(name="응답속도",   value=f"{latency}ms",                   inline=True)
        embed.add_field(name="연결 서버",  value=f"{len(self.bot.guilds)}개",       inline=True)
        embed.add_field(name="API 키",     value=f"{api_stats['total_keys']}개",    inline=True)
        embed.add_field(name="캐시",       value=f"{api_stats['cache_size']}개",    inline=True)
        embed.add_field(name="버전",       value=f"v{BOT_VERSION}",                 inline=True)

        await interaction.response.send_message(embed=embed)

    # ==================== /캐시초기화 ====================

    @app_commands.command(name="캐시초기화", description="API 캐시를 초기화합니다 (관리자 전용)")
    @app_commands.checks.has_permissions(administrator=True)
    async def clear_api_cache(self, interaction: discord.Interaction):

        clear_cache()
        await interaction.response.send_message(
            "✅ API 캐시가 초기화되었습니다!\n"
            "다음 조회부터 최신 데이터로 업데이트됩니다.",
            ephemeral=True
        )

    @clear_api_cache.error
    async def cache_error(self, interaction: discord.Interaction, error):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                "❌ 관리자만 사용할 수 있습니다.", ephemeral=True
            )

    # ==================== /채널초기화 ====================

    @app_commands.command(name="채널초기화", description="로일 채널을 다시 생성합니다 (관리자 전용)")
    @app_commands.checks.has_permissions(administrator=True)
    async def reset_channels(self, interaction: discord.Interaction):
        """로일 카테고리가 없을 때 다시 생성"""
        await interaction.response.defer(ephemeral=True)

        existing = discord.utils.get(interaction.guild.categories, name="📋 로일(LoIl)")
        if existing:
            await interaction.followup.send(
                "⚠️ 이미 **📋 로일(LoIl)** 카테고리가 존재합니다!\n"
                "삭제 후 다시 시도하거나 `/설정패널` 로 설정 패널만 다시 올리세요.",
                ephemeral=True
            )
            return

        # main.py의 on_guild_join 로직 재실행
        from bot.main import LOIL_CHANNELS, send_onboarding_embed

        category = await interaction.guild.create_category("📋 로일(LoIl)")

        admin_overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True),
        }
        for role in interaction.guild.roles:
            if role.permissions.administrator:
                admin_overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True)

        created_channels = {}
        for ch_info in LOIL_CHANNELS:
            overwrites = admin_overwrites if ch_info.get("admin_only") else {}
            channel = await interaction.guild.create_text_channel(
                name=ch_info["name"],
                category=category,
                topic=ch_info["topic"],
                overwrites=overwrites
            )
            created_channels[ch_info["name"]] = channel

        notice_channel = created_channels.get("로일-공지")
        if notice_channel:
            await send_onboarding_embed(notice_channel, interaction.guild)

        await interaction.followup.send(
            "✅ 로일 채널이 새로 생성되었습니다!\n"
            "**📢 로일-공지** 채널에서 설정을 시작해주세요.",
            ephemeral=True
        )

    @reset_channels.error
    async def reset_channels_error(self, interaction: discord.Interaction, error):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                "❌ 관리자만 사용할 수 있습니다.", ephemeral=True
            )


# ==================== Cog 등록 ====================

async def setup(bot):
    await bot.add_cog(AdminCog(bot))