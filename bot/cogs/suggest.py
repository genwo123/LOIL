"""
로일(LoIl) - 길드 건의함 Cog
💌│건의함 채널

길드 건의 → 긴급/일반 태그 선택 후 구조화된 내용으로 접수, 채널에 색상 구분해서 공지
개발 문의 → 봇에 모아두고 /개발문의조회 로 확인
제출된 건의는 suggestions.json에 영구 저장(추후 웹 대시보드에서 조회할 데이터 소스),
채널 자체는 한 달 주기로 자동 청소.
"""

import discord
from discord.ext import commands
from discord import app_commands
import json, os, secrets
from datetime import datetime, timezone, timedelta

from bot.utils.permissions import require_admin
from bot.utils.channel_cleanup import purge_channel
from bot.config.channels import CH_NOTICE, CH_PARTY, get_channel

SUGGEST_FILE = "bot/data/suggestions.json"
KST = timezone(timedelta(hours=9))

URGENCY_STYLE = {
    "긴급": {"emoji": "🚨", "color": 0xED4245},
    "일반": {"emoji": "💬", "color": 0x5865F2},
}

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


def _month_key(dt: datetime) -> str:
    return dt.strftime("%Y-%m")


# ==================== 건의 Modal ====================

class GuildSuggestModal(discord.ui.Modal):
    content = discord.ui.TextInput(
        label="내용",
        placeholder="무슨 일 때문인지 적어주세요",
        style=discord.TextStyle.paragraph,
        max_length=500,
        required=True
    )

    def __init__(self, urgency: str):
        style = URGENCY_STYLE[urgency]
        super().__init__(title=f"{style['emoji']} {urgency} 건의")
        self.urgency = urgency

    async def on_submit(self, interaction: discord.Interaction):
        style = URGENCY_STYLE[self.urgency]
        now = datetime.now(KST)

        data = load_suggestions()
        data["guild"].append({
            "id":         secrets.token_hex(4),
            "guild_id":   interaction.guild_id,
            "guild_name": interaction.guild.name,
            "user":       interaction.user.display_name,
            "user_id":    interaction.user.id,
            "urgency":    self.urgency,
            "content":    self.content.value,
            "created_at": now.isoformat(),
            "resolved":   False,
        })
        save_suggestions(data)

        embed = discord.Embed(
            title=f"{style['emoji']} {self.urgency} 건의",
            description=self.content.value,
            color=style["color"]
        )
        embed.set_footer(text=f"{interaction.user.display_name} · {now.strftime('%Y-%m-%d %H:%M')}")

        from bot.config.channels import CH_SUGGEST
        suggest_ch = get_channel(interaction.guild, CH_SUGGEST)
        if suggest_ch:
            await suggest_ch.send(embed=embed)

        await interaction.response.send_message(
            "✅ 건의가 등록되었습니다! 관리자가 확인 후 답변드릴게요.", ephemeral=True
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


# ==================== 긴급도 선택 View ====================

class UrgencySelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)

    @discord.ui.button(label="🚨 긴급", style=discord.ButtonStyle.danger, custom_id="suggest_urgency_high")
    async def urgent(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(GuildSuggestModal(urgency="긴급"))

    @discord.ui.button(label="💬 일반", style=discord.ButtonStyle.secondary, custom_id="suggest_urgency_normal")
    async def normal(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(GuildSuggestModal(urgency="일반"))


# ==================== 건의함 패널 View ====================

class SuggestPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    # ── Row 0: 기능 버튼 ──

    @discord.ui.button(
        label="길드 건의",
        style=discord.ButtonStyle.primary,
        custom_id="suggest_guild",
        row=0
    )
    async def guild_suggest(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "긴급도를 선택해주세요:", view=UrgencySelectView(), ephemeral=True
        )

    @discord.ui.button(
        label="개발 문의",
        style=discord.ButtonStyle.secondary,
        custom_id="suggest_dev",
        row=0
    )
    async def dev_suggest(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(DevSuggestModal())

    # ── Row 1: 네비게이션 ──

    @discord.ui.button(
        label="📡 공지",
        style=discord.ButtonStyle.secondary,
        custom_id="suggest_nav_notice",
        row=1
    )
    async def nav_notice(self, interaction: discord.Interaction, button: discord.ui.Button):
        ch = get_channel(interaction.guild, CH_NOTICE)
        if ch:
            await interaction.response.send_message(f"📡 {ch.mention}", ephemeral=True)
        else:
            await interaction.response.send_message("❌ 공지 채널을 찾을 수 없습니다.", ephemeral=True)

    @discord.ui.button(
        label="🛡 레이드편성",
        style=discord.ButtonStyle.secondary,
        custom_id="suggest_nav_party",
        row=1
    )
    async def nav_party(self, interaction: discord.Interaction, button: discord.ui.Button):
        ch = get_channel(interaction.guild, CH_PARTY)
        if ch:
            await interaction.response.send_message(f"🛡 {ch.mention}", ephemeral=True)
        else:
            await interaction.response.send_message("❌ 레이드편성 채널을 찾을 수 없습니다.", ephemeral=True)


def build_suggest_panel_embed() -> discord.Embed:
    embed = discord.Embed(
        title="💌 길드 건의함",
        description=(
            "**길드 건의** — 긴급/일반으로 나눠서 접수, 길드 운영·레이드·기타 건의사항\n"
            "**개발 문의** — 봇 버그 신고, 기능 요청, 개선 사항"
        ),
        color=0x9B59B6
    )
    embed.set_footer(text="채널은 한 달마다 자동 정리됩니다 · 내용은 계속 보관됩니다")
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

    async def monthly_cleanup_if_needed(self, guild: discord.Guild):
        from bot.config.channels import CH_SUGGEST
        from bot.utils.storage import load_settings, save_settings

        gid = str(guild.id)
        settings = load_settings()
        this_month = _month_key(datetime.now(KST))
        if settings.get(gid, {}).get("_suggest_last_cleanup_month") == this_month:
            return

        channel = get_channel(guild, CH_SUGGEST)
        if channel:
            try:
                await purge_channel(channel)
                await self.send_suggest_panel(channel)
            except Exception as e:
                print(f"[suggest] 월간 자동 청소 실패: {e}")

        if gid not in settings:
            settings[gid] = {}
        settings[gid]["_suggest_last_cleanup_month"] = this_month
        save_settings(settings)

    @app_commands.command(name="개발문의조회", description="접수된 개발 문의를 조회합니다 (개발자 전용)")
    async def view_dev_suggestions(self, interaction: discord.Interaction):
        if interaction.user.id != interaction.guild.owner_id:
            if not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message("❌ 권한이 없습니다.", ephemeral=True)
                return

        data = load_suggestions()
        dev  = [d for d in data["dev"] if not d.get("read")]

        if not dev:
            await interaction.response.send_message("새 개발 문의가 없습니다!", ephemeral=True)
            return

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
