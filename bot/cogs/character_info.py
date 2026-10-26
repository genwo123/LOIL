"""
로일(LoIl) - 캐릭터 정보 Cog
로스트아크 API를 실제로 써서 캐릭터 초상화/전투력/각인을 보여준다.

주의: 시트 "닉네임"이 실제 로스트아크 대표캐릭터명과 다른 길드원도 있을 수 있다.
API에서 못 찾으면 조용히 에러 안내만 하고, 다른 기능(편성 등)에는 영향 없게 한다.
"""

import asyncio
import discord
from discord.ext import commands
from discord import app_commands

from bot.config.settings import WEB_BASE_URL
from bot.utils.member_link import get_sheet_name, get_main_character
from bot.utils.guild_url import get_url_name, sync_guild_name
from bot.utils.lostark_api import get_character_info, get_character_engravings


class CharacterInfoCog(commands.Cog, name="CharacterInfoCog"):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="캐릭터조회", description="로스트아크 캐릭터 정보를 조회합니다")
    @app_commands.describe(캐릭터명="비워두면 내 등록된 닉네임으로 조회합니다")
    async def my_info(self, interaction: discord.Interaction, 캐릭터명: str = None):
        await interaction.response.defer(ephemeral=True)

        name = (
            (캐릭터명 or "").strip()
            or get_main_character(interaction.guild_id, interaction.user.id)
            or get_sheet_name(interaction.guild_id, interaction.user.id)
        )
        if not name:
            await interaction.followup.send(
                "❌ 등록된 캐릭터명이 없습니다. `/캐릭터조회 캐릭터명:홍길동` 처럼 직접 입력해주세요.",
                ephemeral=True
            )
            return

        info = await asyncio.to_thread(get_character_info, name, True, interaction.guild_id)
        if not info:
            await interaction.followup.send(
                f"❌ 로스트아크에서 '{name}' 캐릭터를 찾을 수 없습니다.\n"
                f"닉네임이 실제 캐릭터명과 다르면 `/캐릭터조회 캐릭터명:실제캐릭터명`으로 직접 입력해보세요.",
                ephemeral=True
            )
            return

        embed = discord.Embed(
            title=info.get("CharacterName", name),
            description=f"{info.get('ServerName', '')} · {info.get('CharacterClassName', '')}",
            color=0x9B59B6,
        )
        char_image = info.get("CharacterImage")
        if char_image:
            embed.set_image(url=char_image)

        embed.add_field(name="아이템 레벨", value=info.get("ItemAvgLevel", "?"), inline=True)
        embed.add_field(name="원정대 레벨", value=str(info.get("ExpeditionLevel", "?")), inline=True)
        embed.add_field(name="길드", value=info.get("GuildName") or "-", inline=True)

        try:
            engravings = await asyncio.to_thread(get_character_engravings, name, True, interaction.guild_id)
            effects = (engravings or {}).get("Effects") or []
            if effects:
                lines = [e.get("Name", "") for e in effects[:5] if e.get("Name")]
                if lines:
                    embed.add_field(name="각인", value="\n".join(lines), inline=False)
        except Exception as e:
            print(f"[character_info] 각인 조회 실패 ({name}): {e}")

        embed.set_footer(text="로일(LoIl) · 로스트아크 오픈 API")
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="주간일정설정", description="이번 주 가능한 시간을 제출할 개인 웹 링크를 받습니다")
    async def availability_link(self, interaction: discord.Interaction):
        sheet_name = get_sheet_name(interaction.guild_id, interaction.user.id)
        if not sheet_name:
            await interaction.response.send_message(
                "❌ 먼저 닉네임이 연결되어 있어야 합니다. 📡│공지 채널의 **내 닉네임 등록** 버튼으로 등록해주세요.",
                ephemeral=True,
            )
            return

        url_name = get_url_name(interaction.guild_id)
        if not url_name:
            sync_guild_name(interaction.guild_id, interaction.guild.name)
            url_name = get_url_name(interaction.guild_id)

        url = f"{WEB_BASE_URL.rstrip('/')}/{url_name}/일정/{sheet_name}"
        view = discord.ui.View()
        view.add_item(discord.ui.Button(label="🔗 주간 개인시간 설정하러 가기", style=discord.ButtonStyle.link, url=url))
        await interaction.response.send_message(
            "여는 화면에서 디스코드 로그인이 필요해요 (본인 계정으로 로그인해야 본인 페이지가 열립니다):",
            view=view,
            ephemeral=True,
        )


async def setup(bot):
    await bot.add_cog(CharacterInfoCog(bot))
