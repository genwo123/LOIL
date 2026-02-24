"""
로일(LoIl) - 건의함 Cog
💌│건의함 채널

길드 문의 → 서버 관리자 확인
개발 문의 → 봇에 모아두고 /개발문의조회 로 확인
"""

import discord
from discord.ext import commands
from discord import app_commands
import json, os
from datetime import datetime, timezone, timedelta

from bot.utils.permissions import require_admin

SUGGEST_FILE = "bot/data/suggestions.json"
KST = timezone(timedelta(hours=9))

# ==================== 저장/로드 ====================

def load_suggestions() -> dict:
    if not os.path.exists(SUGGEST_FILE):
        return {"guild": [], "dev": []}
    try:
        with open(SUGGEST_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"guild": [], "dev": []}

def save_suggestions(data: dict):
    os.makedirs(os.path.dirname(SUGGEST_FILE), exist_ok=True)
    with open(SUGGEST_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ==================== 건의 Modal ====================

class GuildSuggestModal(discord.ui.Modal, title="길드 문의"):
    content = discord.ui.TextInput(
        label="문의 내용",
        placeholder="길드 운영, 레이드, 기타 건의사항을 입력해주세요",
        style=discord.TextStyle.paragraph,
        max_length=500,
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        from bot.config.channels import CH_SUGGEST, get_channel

        embed = discord.Embed(
            title="💌 길드 문의",
            description=self.content.value,
            color=0x5865F2
        )
        embed.set_footer(
            text=f"{interaction.user.display_name} · {datetime.now(KST).strftime('%Y-%m-%d %H:%M')}"
        )

        # 건의함 채널에 전송
        suggest_ch = get_channel(interaction.guild, CH_SUGGEST)
        if suggest_ch:
            await suggest_ch.send(embed=embed)

        await interaction.response.send_message(
            "✅ 길드 문의가 등록되었습니다! 관리자가 확인 후 답변드릴게요.", ephemeral=True
        )


class DevSuggestModal(discord.ui.Modal, title="개발 문의"):
    content = discord.ui.TextInput(
        label="개발 문의 내용",
        placeholder="봇 버그, 기능 요청, 개선 사항 등을 입력해주세요",
        style=discord.TextStyle.paragraph,
        max_length=500,
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        data = load_suggestions()
        data["dev"].append({
            "guild_id":   interaction.guild_id,
            "guild_name": interaction.guild.name,
            "user":       interaction.user.display_name,
            "content":    self.content.value,
            "created_at": datetime.now(KST).isoformat(),
            "read":       False,
        })
        save_suggestions(data)

        await interaction.response.send_message(
            "✅ 개발 문의가 접수되었습니다! 분기마다 검토 후 반영됩니다.", ephemeral=True
        )


# ==================== 건의함 패널 View ====================

class SuggestPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="길드 문의",
        style=discord.ButtonStyle.primary,
        custom_id="suggest_guild",
        row=0
    )
    async def guild_suggest(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(GuildSuggestModal())

    @discord.ui.button(
        label="개발 문의",
        style=discord.ButtonStyle.secondary,
        custom_id="suggest_dev",
        row=0
    )
    async def dev_suggest(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(DevSuggestModal())


def build_suggest_panel_embed() -> discord.Embed:
    embed = discord.Embed(
        title="💌 건의함",
        description=(
            "**길드 문의** — 길드 운영, 레이드, 기타 건의사항\n"
            "**개발 문의** — 봇 버그 신고, 기능 요청, 개선 사항"
        ),
        color=0x9B59B6
    )
    embed.set_footer(text="개발 문의는 분기마다 검토됩니다")
    return embed


# ==================== SuggestCog ====================

class SuggestCog(commands.Cog, name="SuggestCog"):

    def __init__(self, bot):
        self.bot = bot
        bot.add_view(SuggestPanelView())

    async def send_suggest_panel(self, channel: discord.TextChannel):
        embed = build_suggest_panel_embed()
        view  = SuggestPanelView()
        msg   = await channel.send(embed=embed, view=view)
        try:
            await msg.pin()
        except Exception:
            pass

    @app_commands.command(name="개발문의조회", description="접수된 개발 문의를 조회합니다 (개발자 전용)")
    async def view_dev_suggestions(self, interaction: discord.Interaction):
        # 서버 소유자만 가능
        if interaction.user.id != interaction.guild.owner_id:
            # 또는 특정 개발자 ID 체크
            if not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message("❌ 권한이 없습니다.", ephemeral=True)
                return

        data = load_suggestions()
        dev  = [d for d in data["dev"] if not d.get("read")]

        if not dev:
            await interaction.response.send_message("새 개발 문의가 없습니다!", ephemeral=True)
            return

        # 최대 10개씩 표시
        embed = discord.Embed(
            title=f"개발 문의 ({len(dev)}건 미확인)",
            color=0x9B59B6
        )
        for i, s in enumerate(dev[:10], 1):
            embed.add_field(
                name=f"{i}. {s['guild_name']} · {s['user']} · {s['created_at'][:10]}",
                value=s["content"][:200],
                inline=False
            )

        # 읽음 처리
        for s in data["dev"]:
            s["read"] = True
        save_suggestions(data)

        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(SuggestCog(bot))