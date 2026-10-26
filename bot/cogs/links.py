"""
로일(LoIl) - 즐겨찾기 링크 Cog
길드장이 자주 쓰는 링크(공략 사이트, 길드 규칙, 디스코드 초대 등)를 등록해두면
길드원은 채널에 고정된 링크 보드에서 버튼 하나로 바로 이동할 수 있다.
"""

import discord
from discord.ext import commands
from discord import app_commands

from bot.utils.permissions import require_admin
from bot.utils.favorite_links import get_links, add_link, remove_link, MAX_LINKS
from bot.utils.storage import load_settings, save_settings


class LinksView(discord.ui.View):
    def __init__(self, links: list[dict]):
        super().__init__(timeout=None)
        for link in links:
            self.add_item(discord.ui.Button(
                style=discord.ButtonStyle.link,
                label=link["label"][:80],
                url=link["url"],
            ))


def _panel_state(guild_id: int) -> dict:
    settings = load_settings()
    return settings.get(str(guild_id), {}).get("links_panel", {})


def _save_panel_state(guild_id: int, channel_id: int, message_id: int):
    settings = load_settings()
    gid = str(guild_id)
    if gid not in settings:
        settings[gid] = {}
    settings[gid]["links_panel"] = {"channel_id": channel_id, "message_id": message_id}
    save_settings(settings)


class LinksCog(commands.Cog, name="LinksCog"):
    def __init__(self, bot):
        self.bot = bot

    async def refresh_links_panel(self, guild: discord.Guild):
        """이미 고정해둔 링크 보드가 있으면 최신 목록으로 갱신."""
        state = _panel_state(guild.id)
        channel_id = state.get("channel_id")
        message_id = state.get("message_id")
        if not channel_id or not message_id:
            return

        channel = guild.get_channel(channel_id)
        if not channel:
            return

        links = get_links(guild.id)
        try:
            msg = await channel.fetch_message(message_id)
            await msg.edit(content=f"🔗 **즐겨찾기 링크** ({len(links)}개)", view=LinksView(links))
        except Exception:
            pass

    @app_commands.command(name="링크", description="길드에 등록된 즐겨찾기 링크를 봅니다")
    async def show_links(self, interaction: discord.Interaction):
        links = get_links(interaction.guild_id)
        if not links:
            await interaction.response.send_message(
                "아직 등록된 링크가 없습니다. 관리자가 `/링크추가`로 등록할 수 있어요.",
                ephemeral=True
            )
            return
        await interaction.response.send_message(
            f"🔗 등록된 링크 {len(links)}개",
            view=LinksView(links),
            ephemeral=True
        )

    @app_commands.command(name="링크고정", description="이 채널에 즐겨찾기 링크 보드를 고정합니다 (관리자 전용)")
    async def pin_links(self, interaction: discord.Interaction):
        if not await require_admin(interaction): return

        links = get_links(interaction.guild_id)
        if not links:
            await interaction.response.send_message(
                "아직 등록된 링크가 없습니다. `/링크추가`로 먼저 등록해주세요.", ephemeral=True
            )
            return

        msg = await interaction.channel.send(
            content=f"🔗 **즐겨찾기 링크** ({len(links)}개)", view=LinksView(links)
        )
        try:
            await msg.pin()
        except Exception:
            pass
        _save_panel_state(interaction.guild_id, interaction.channel_id, msg.id)
        await interaction.response.send_message("✅ 이 채널에 링크 보드를 고정했습니다!", ephemeral=True)

    @app_commands.command(name="링크추가", description="즐겨찾기 링크를 등록합니다 (관리자 전용)")
    @app_commands.describe(이름="버튼에 표시될 이름", url="https:// 로 시작하는 주소")
    async def add_link_cmd(self, interaction: discord.Interaction, 이름: str, url: str):
        if not await require_admin(interaction): return

        if not url.startswith(("http://", "https://")):
            await interaction.response.send_message(
                "❌ URL은 `http://` 또는 `https://` 로 시작해야 합니다.", ephemeral=True
            )
            return

        ok = add_link(interaction.guild_id, 이름.strip(), url.strip())
        if not ok:
            await interaction.response.send_message(
                f"❌ 링크는 최대 {MAX_LINKS}개까지만 등록할 수 있습니다. `/링크삭제`로 먼저 정리해주세요.",
                ephemeral=True
            )
            return

        await self.refresh_links_panel(interaction.guild)
        await interaction.response.send_message(f"✅ 링크 **{이름}** 등록 완료!", ephemeral=True)

    @app_commands.command(name="링크삭제", description="등록된 즐겨찾기 링크를 삭제합니다 (관리자 전용)")
    @app_commands.describe(이름="삭제할 링크의 이름")
    async def remove_link_cmd(self, interaction: discord.Interaction, 이름: str):
        if not await require_admin(interaction): return

        ok = remove_link(interaction.guild_id, 이름.strip())
        if not ok:
            await interaction.response.send_message(f"❌ '{이름}' 링크를 찾을 수 없습니다.", ephemeral=True)
            return

        await self.refresh_links_panel(interaction.guild)
        await interaction.response.send_message(f"🗑 링크 **{이름}** 삭제 완료!", ephemeral=True)

    @remove_link_cmd.autocomplete("이름")
    async def remove_link_autocomplete(self, interaction: discord.Interaction, current: str):
        links = get_links(interaction.guild_id)
        return [
            app_commands.Choice(name=l["label"], value=l["label"])
            for l in links if current.lower() in l["label"].lower()
        ][:25]


async def setup(bot):
    await bot.add_cog(LinksCog(bot))
