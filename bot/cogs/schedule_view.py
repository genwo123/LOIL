"""
로일(LoIl) - 일정조회 Cog
"""

import discord
from discord.ext import commands
from discord import app_commands
import asyncio
from datetime import datetime, timezone, timedelta
from urllib.parse import quote

from bot.utils.raid_schedule import get_user_schedule, get_weekly_summary
from bot.utils.member_link import get_all_members, get_absences, get_sheet_name
from bot.utils.web_results import save_member_schedule_snapshot, save_weekly_schedule_snapshot, build_web_url, get_guild_name
from bot.utils.permissions import require_admin
from bot.utils.channel_cleanup import purge_channel as _purge_channel
from bot.config.channels import CH_SCHEDULE, CH_SCHEDULE_THREAD, CH_NOTICE, CH_PARTY, get_channel

KST = timezone(timedelta(hours=9))

def _get_week_label() -> str:
    now = datetime.now(KST)
    if now.weekday() < 2 or (now.weekday() == 2 and now.hour < 9):
        now = now - timedelta(weeks=1)
    month = now.month
    first_day = now.replace(day=1)
    first_wed = first_day + timedelta(days=(2 - first_day.weekday()) % 7)
    week_num  = (now - first_wed).days // 7 + 1
    return f"{month}월 {week_num}주차"


# ==================== 일정조회 패널 임베드 ====================

def build_schedule_panel_embed() -> discord.Embed:
    embed = discord.Embed(
        title="🗒 일정 조회",
        description=(
            "**내 일정 보기** — 길드원 선택 후 개인 레이드 일정 이미지\n"
            "**전체 일정 보기** — 이번주 전체 레이드 현황 이미지\n\n"
            "결과는 📋│일정확인 채널 스레드에 표시됩니다.\n"
            "스레드는 **24시간 후 자동 삭제**됩니다."
        ),
        color=0x5865F2
    )
    return embed


# ==================== 일정조회 패널 View ====================

class ScheduleViewPanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="내 일정 보기",
        style=discord.ButtonStyle.primary,
        custom_id="sv_my_schedule",
        row=0
    )
    async def my_schedule(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)

        absent_names = set(get_absences(interaction.guild_id))
        names = [n for n in get_all_members(interaction.guild_id).values() if n not in absent_names]

        if not names:
            await interaction.followup.send("❌ 등록된 길드원이 없습니다.", ephemeral=True)
            return

        my_sheet = get_sheet_name(interaction.guild_id, interaction.user.id)
        view = MemberSelectView(
            names=names,
            default_name=my_sheet,
            guild=interaction.guild,
            guild_id=interaction.guild_id,
            user=interaction.user,
        )
        await interaction.followup.send("누구의 일정을 볼까요?", view=view, ephemeral=True)

    @discord.ui.button(
        label="전체 일정 보기",
        style=discord.ButtonStyle.secondary,
        custom_id="sv_all_schedule",
        row=0
    )
    async def all_schedule(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        await _send_weekly_schedule(interaction, interaction.guild, interaction.guild_id, interaction.user)

    @discord.ui.button(
        label="공지 →",
        style=discord.ButtonStyle.secondary,
        custom_id="sv_to_notice",
        row=1
    )
    async def to_notice(self, interaction: discord.Interaction, button: discord.ui.Button):
        ch = get_channel(interaction.guild, CH_NOTICE)
        await interaction.response.send_message(
            f"{ch.mention} 으로 이동하세요!" if ch else "채널을 찾을 수 없습니다.",
            ephemeral=True
        )

    @discord.ui.button(
        label="레이드 편성 →",
        style=discord.ButtonStyle.secondary,
        custom_id="sv_to_party",
        row=1
    )
    async def to_party(self, interaction: discord.Interaction, button: discord.ui.Button):
        ch = get_channel(interaction.guild, CH_PARTY)
        await interaction.response.send_message(
            f"{ch.mention} 으로 이동하세요!" if ch else "채널을 찾을 수 없습니다.",
            ephemeral=True
        )

    @discord.ui.button(
        label="🧹 채널 청소",
        style=discord.ButtonStyle.danger,
        custom_id="sv_purge",
        row=1
    )
    async def purge_channel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await require_admin(interaction): return
        await interaction.response.defer(ephemeral=True)
        channel = interaction.channel
        try:
            deleted = await _purge_channel(channel)

            sv_cog = interaction.client.cogs.get("ScheduleViewCog")
            if sv_cog:
                await sv_cog.send_schedule_panel(channel)

            await interaction.followup.send(
                f"🧹 **{deleted}개** 메시지 삭제 후 패널을 새로 표시했습니다.",
                ephemeral=True
            )
        except Exception as e:
            print(f"[schedule_view] 청소 실패: {e}")
            await interaction.followup.send("❌ 채널 청소에 실패했습니다. 잠시 후 다시 시도해주세요.", ephemeral=True)


# ==================== 길드원 선택 드롭다운 ====================

class MemberSelectView(discord.ui.View):
    def __init__(self, names: list, default_name: str, guild, guild_id, user):
        super().__init__(timeout=60)
        self.guild    = guild
        self.guild_id = guild_id
        self.user     = user
        self.selected = default_name or (names[0] if names else None)

        options = [
            discord.SelectOption(
                label=name[:100],
                value=name[:100],
                default=(name == default_name)
            )
            for name in names[:25]
        ]
        select = discord.ui.Select(
            placeholder="길드원 선택",
            options=options,
            min_values=1, max_values=1,
            custom_id="member_select",
            row=0
        )
        select.callback = self._on_select
        self.add_item(select)

    async def _on_select(self, interaction: discord.Interaction):
        select = discord.utils.get(self.children, custom_id="member_select")
        self.selected = select.values[0]
        await interaction.response.defer()

    @discord.ui.button(label="일정 보기", style=discord.ButtonStyle.primary, row=1)
    async def send(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)

        if not self.selected:
            await interaction.followup.send("❌ 길드원을 선택해주세요.", ephemeral=True)
            return

        guild_name = get_guild_name(self.guild_id)
        week_label = _get_week_label()

        thread_ch = get_channel(self.guild, CH_SCHEDULE_THREAD)
        if not thread_ch:
            await interaction.followup.send("❌ 일정확인 채널을 찾을 수 없습니다.", ephemeral=True)
            return

        schedule = get_user_schedule(self.guild_id, self.selected)
        if not schedule:
            await interaction.followup.send(
                f"**{self.selected}** 님의 이번주 예정 레이드가 없습니다!", ephemeral=True
            )
            return

        # 웹 조회 페이지에서 전체 길드원을 바로 골라볼 수 있도록, 이 시점에 전체 멤버 일정을 함께 저장
        absent_names = set(get_absences(self.guild_id))
        members_schedule = {
            name: get_user_schedule(self.guild_id, name)
            for name in get_all_members(self.guild_id).values() if name not in absent_names
        }
        slug = save_member_schedule_snapshot(self.guild_id, week_label, members_schedule, guild_name=guild_name)

        thread = await thread_ch.create_thread(
            name=f"📅 {week_label} {self.selected} 개인 일정",
            auto_archive_duration=1440,
            type=discord.ChannelType.public_thread
        )
        await thread.send(
            content=f"{self.user.mention}\n🔗 일정 보기: {build_web_url(slug)}?tab=member&member={quote(self.selected)}"
        )
        await interaction.followup.send(
            f"{thread.mention} 에서 확인하세요! (24시간 후 자동 삭제)", ephemeral=True
        )
        asyncio.create_task(_delete_thread_after(thread, 86400))


# ==================== 전체 일정 ====================

async def _send_weekly_schedule(interaction, guild, guild_id, user):
    guild_name = get_guild_name(guild_id)
    week_label = _get_week_label()

    thread_ch = get_channel(guild, CH_SCHEDULE_THREAD)
    if not thread_ch:
        await interaction.followup.send("❌ 일정확인 채널을 찾을 수 없습니다.", ephemeral=True)
        return

    summary = get_weekly_summary(guild_id)
    if not summary:
        await interaction.followup.send("이번주 예정된 레이드가 없습니다!", ephemeral=True)
        return

    slug = save_weekly_schedule_snapshot(guild_id, week_label, summary, guild_name=guild_name)

    thread = await thread_ch.create_thread(
        name=f"📋 {week_label} 전체 레이드 일정",
        auto_archive_duration=1440,
        type=discord.ChannelType.public_thread
    )
    await thread.send(
        content=f"{user.mention}\n🔗 전체 일정 보기: {build_web_url(slug)}?tab=weekly"
    )
    await interaction.followup.send(
        f"{thread.mention} 에서 확인하세요! (24시간 후 자동 삭제)", ephemeral=True
    )
    asyncio.create_task(_delete_thread_after(thread, 86400))


async def _delete_thread_after(thread: discord.Thread, seconds: int):
    await asyncio.sleep(seconds)
    try:
        await thread.delete()
    except Exception:
        pass


# ==================== ScheduleViewCog ====================

class ScheduleViewCog(commands.Cog, name="ScheduleViewCog"):
    def __init__(self, bot):
        self.bot = bot
        self.bot.add_view(ScheduleViewPanel())

    @app_commands.command(name="일정패널", description="일정 조회 패널을 생성합니다.")
    async def spawn_panel(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        await self.send_schedule_panel(interaction.channel)
        await interaction.followup.send("✅ 패널이 생성되었습니다.", ephemeral=True)

    async def send_schedule_panel(self, channel: discord.TextChannel):
        embed = build_schedule_panel_embed()
        view  = ScheduleViewPanel()
        msg   = await channel.send(embed=embed, view=view)
        try:
            await msg.pin()
        except Exception:
            pass
        return msg


async def setup(bot):
    await bot.add_cog(ScheduleViewCog(bot))
