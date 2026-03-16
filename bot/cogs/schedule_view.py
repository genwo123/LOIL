"""
로일(LoIl) - 일정조회 Cog
"""

import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import json, os
from datetime import datetime, timezone, timedelta

from bot.utils.sheets import get_all_data, get_user_schedule, get_weekly_summary, copy_ai_to_manual, get_members
from bot.utils.image_renderer import render_my_schedule, render_weekly_raids, render_weekly_timeline
from bot.utils.member_link import get_sheet_name
from bot.config.channels import CH_SCHEDULE, CH_NOTICE, CH_PARTY, get_channel

def _get_week_label() -> str:
    now = datetime.now(KST)
    if now.weekday() < 2 or (now.weekday() == 2 and now.hour < 9):
        now = now - timedelta(weeks=1)
    month = now.month
    first_day = now.replace(day=1)
    first_wed = first_day + timedelta(days=(2 - first_day.weekday()) % 7)
    week_num  = (now - first_wed).days // 7 + 1
    return f"{month}월 {week_num}주차"

SETTINGS_FILE = "bot/data/guild_settings.json"
KST = timezone(timedelta(hours=9))

def get_guild_setting(guild_id: int) -> dict:
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f).get(str(guild_id), {})
    except Exception:
        return {}

def get_sheet_url(guild_id: int) -> str:
    return get_guild_setting(guild_id).get("sheet_url", "")

def get_guild_name(guild_id: int) -> str:
    return get_guild_setting(guild_id).get("guild_name", "로일길드")


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

        url = get_sheet_url(interaction.guild_id)
        if not url:
            await interaction.followup.send("❌ 시트가 연동되지 않았습니다.", ephemeral=True)
            return

        # 시트에서 길드원 목록 불러오기
        try:
            data    = get_all_data(url, ai=True) or get_all_data(url)
            members = get_members(data)
            names   = [m['name'] for m in members if not m.get('absent')]
        except Exception:
            names = []

        if not names:
            await interaction.followup.send("❌ 길드원 목록을 불러올 수 없습니다.", ephemeral=True)
            return

        # 본인 시트 이름으로 기본값 설정
        my_sheet = get_sheet_name(interaction.guild_id, interaction.user.id)

        view = MemberSelectView(
            names=names,
            default_name=my_sheet,
            guild=interaction.guild,
            guild_id=interaction.guild_id,
            user=interaction.user,
            url=url
        )
        await interaction.followup.send("누구의 일정을 볼까요?", view=view, ephemeral=True)

    @discord.ui.button(
        label="전체 일정 보기",
        style=discord.ButtonStyle.secondary,
        custom_id="sv_all_schedule",
        row=0
    )
    async def all_schedule(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = ScheduleSourceSelectView(mode="all", guild=interaction.guild,
                                        guild_id=interaction.guild_id, user=interaction.user)
        await interaction.response.send_message(
            "어떤 일정 기준으로 볼까요?", view=view, ephemeral=True
        )

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
        label="🤖 AI편성 → 주간레이드 복사",
        style=discord.ButtonStyle.danger,
        custom_id="sv_copy_ai",
        row=2
    )
    async def copy_ai(self, interaction: discord.Interaction, button: discord.ui.Button):
        from bot.utils.member_link import require_admin
        if not await require_admin(interaction): return
        await interaction.response.defer(ephemeral=True)
        url = get_sheet_url(interaction.guild_id)
        if not url:
            await interaction.followup.send("❌ 시트가 연동되지 않았습니다.", ephemeral=True)
            return
        ok = copy_ai_to_manual(url)
        if ok:
            await interaction.followup.send(
                "✅ AI편성 탭 복사 완료! 구글 시트에서 직접 수정 가능합니다.",
                ephemeral=True
            )
        else:
            await interaction.followup.send("❌ 복사 실패. AI편성 탭이 비어있거나 오류가 발생했습니다.", ephemeral=True)


# ==================== 길드원 선택 드롭다운 ====================

class MemberSelectView(discord.ui.View):
    def __init__(self, names: list, default_name: str, guild, guild_id, user, url):
        super().__init__(timeout=60)
        self.guild      = guild
        self.guild_id   = guild_id
        self.user       = user
        self.url        = url
        self.selected   = default_name or (names[0] if names else None)

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
            min_values=1,
            max_values=1,
            custom_id="member_select",
            row=0
        )
        select.callback = self._on_select
        self.add_item(select)

    async def _on_select(self, interaction: discord.Interaction):
        select = discord.utils.get(self.children, custom_id="member_select")
        self.selected = select.values[0]
        await interaction.response.defer()

    @discord.ui.button(label="📋 주간레이드 탭", style=discord.ButtonStyle.secondary, row=1)
    async def use_manual(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        await self._send(interaction, ai=False)

    @discord.ui.button(label="🤖 AI편성 탭", style=discord.ButtonStyle.primary, row=1)
    async def use_ai(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        await self._send(interaction, ai=True)

    async def _send(self, interaction, ai: bool):
        if not self.selected:
            await interaction.followup.send("❌ 길드원을 선택해주세요.", ephemeral=True)
            return

        data       = get_all_data(self.url, ai=ai) or get_all_data(self.url)
        guild_name = get_guild_name(self.guild_id)
        week_label = _get_week_label()
        schedule_ch = get_channel(self.guild, CH_SCHEDULE)
        if not schedule_ch:
            await interaction.followup.send("❌ 일정조회 채널을 찾을 수 없습니다.", ephemeral=True)
            return

        schedule = get_user_schedule(data, self.selected)
        if not schedule:
            await interaction.followup.send(
                f"**{self.selected}** 님의 이번주 예정 레이드가 없습니다!", ephemeral=True
            )
            return

        buf     = render_my_schedule(self.selected, schedule, guild_name=guild_name)
        src_tag = "AI편성" if ai else "수동"
        thread  = await schedule_ch.create_thread(
            name=f"📅 {week_label} {self.selected} 개인 일정 ({src_tag})",
            auto_archive_duration=1440,
            type=discord.ChannelType.public_thread
        )
        await thread.send(
            content=self.user.mention,
            file=discord.File(fp=buf, filename="my_schedule.png")
        )
        await interaction.followup.send(f"{thread.mention} 에서 확인하세요! (24시간 후 자동 삭제)", ephemeral=True)
        asyncio.create_task(_delete_thread_after(thread, 86400))


# ==================== 데이터 소스 선택 (전체 일정용) ====================

class ScheduleSourceSelectView(discord.ui.View):
    def __init__(self, mode, guild, guild_id, user, sheet_name=None, url=None):
        super().__init__(timeout=60)
        self.mode       = mode
        self.guild      = guild
        self.guild_id   = guild_id
        self.user       = user
        self.sheet_name = sheet_name
        self.url        = url or get_sheet_url(guild_id)

    @discord.ui.button(label="📋 주간레이드 탭", style=discord.ButtonStyle.secondary)
    async def use_manual(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        await self._send_schedule(interaction, ai=False)

    @discord.ui.button(label="🤖 AI편성 탭", style=discord.ButtonStyle.primary)
    async def use_ai(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        await self._send_schedule(interaction, ai=True)

    async def _send_schedule(self, interaction, ai: bool):
        guild_name  = get_guild_name(self.guild_id)
        week_label  = _get_week_label()
        schedule_ch = get_channel(self.guild, CH_SCHEDULE)
        if not schedule_ch:
            await interaction.followup.send("❌ 일정조회 채널을 찾을 수 없습니다.", ephemeral=True)
            return

        data = get_all_data(self.url, ai=ai) or get_all_data(self.url)

        summary = get_weekly_summary(data)
        if not summary:
            await interaction.followup.send("이번주 예정된 레이드가 없습니다!", ephemeral=True)
            return
        src_tag = "AI편성" if ai else "수동"
        thread  = await schedule_ch.create_thread(
            name=f"📋 {week_label} 전체 레이드 일정 ({src_tag})",
            auto_archive_duration=1440,
            type=discord.ChannelType.public_thread
        )
        buf_card     = render_weekly_raids(summary, guild_name=guild_name)
        buf_timeline = render_weekly_timeline(summary, guild_name=guild_name)
        await thread.send(
            content=self.user.mention,
            files=[discord.File(fp=buf_card,     filename="weekly_card.png"),
                   discord.File(fp=buf_timeline, filename="weekly_timeline.png")]
        )
        await interaction.followup.send(f"{thread.mention} 에서 확인하세요! (24시간 후 자동 삭제)", ephemeral=True)
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
        # 봇 실행 시 버튼이 상시 작동하도록 뷰 등록
        self.bot.add_view(ScheduleViewPanel())

    @app_commands.command(name="일정패널", description="일정 조회 패널을 생성합니다.")
    async def spawn_panel(self, interaction: discord.Interaction):
        """이 명령어가 있어야 네비게이션에 뜹니다."""
        await interaction.response.defer(ephemeral=True)
        await self.send_schedule_panel(interaction.channel)
        await interaction.followup.send("✅ 패널이 생성되었습니다.", ephemeral=True)

    async def send_schedule_panel(self, channel: discord.TextChannel):
        embed = discord.Embed(
            title="🗒 일정 조회",
            description=(
                "**내 일정 보기** — 길드원 선택 후 개인 레이드 일정 이미지\n"
                "**전체 일정 보기** — 이번주 전체 레이드 현황 이미지\n\n"
                "스레드는 **24시간 후 자동 삭제**됩니다."
            ),
            color=0x5865F2
        )
        view = ScheduleViewPanel()
        msg = await channel.send(embed=embed, view=view)
        try:
            await msg.pin()
        except:
            pass
        return msg

async def setup(bot):
    await bot.add_cog(ScheduleViewCog(bot))