"""
로일(LoIl) - 일정조회 Cog
🗒│일정조회 채널

기능:
- 내 일정 보기 → 개인 스레드에 이미지 전송 → 24시간 후 자동 삭제
- 전체 일정 보기 → 이번주 전체 레이드 현황
- 스레드는 24시간 후 자동 삭제
"""

import discord
from discord.ext import commands, tasks
from discord import app_commands
import asyncio
import json, os
from datetime import datetime, timezone, timedelta

from bot.utils.sheets import get_all_data, get_user_schedule, get_weekly_summary
from bot.utils.member_link import get_sheet_name
from bot.config.channels import CH_SCHEDULE, CH_NOTICE, CH_PARTY, get_channel

SETTINGS_FILE = "bot/data/guild_settings.json"
KST = timezone(timedelta(hours=9))

def get_sheet_url(guild_id: int) -> str:
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f).get(str(guild_id), {}).get("sheet_url", "")
    except Exception:
        return ""


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

        sheet_name = get_sheet_name(interaction.guild_id, interaction.user.id)
        if not sheet_name:
            await interaction.followup.send(
                "먼저 시트 연결이 필요해요!\n📡│공지 채널에서 **내 시트 연결** 버튼을 눌러주세요.",
                ephemeral=True
            )
            return

        url = get_sheet_url(interaction.guild_id)
        if not url:
            await interaction.followup.send("❌ 시트가 연동되지 않았습니다.", ephemeral=True)
            return

        data     = get_all_data(url)
        schedule = get_user_schedule(data, sheet_name)

        if not schedule:
            await interaction.followup.send(
                f"**{sheet_name}** 님의 이번주 예정된 레이드가 없습니다!", ephemeral=True
            )
            return

        # 스레드 생성
        schedule_ch = get_channel(interaction.guild, CH_SCHEDULE)
        if not schedule_ch:
            await interaction.followup.send("❌ 일정조회 채널을 찾을 수 없습니다.", ephemeral=True)
            return

        thread_name = f"{sheet_name}의 이번주 일정"
        thread = await schedule_ch.create_thread(
            name=thread_name,
            auto_archive_duration=1440,  # 24시간
            type=discord.ChannelType.public_thread
        )

        # 일정 임베드 생성
        embed = _build_my_schedule_embed(sheet_name, schedule)
        await thread.send(
            content=f"{interaction.user.mention}",
            embed=embed
        )

        await interaction.followup.send(
            f"{thread.mention} 에서 확인하세요! (24시간 후 자동 삭제)",
            ephemeral=True
        )

        # 24시간 후 스레드 삭제
        asyncio.create_task(_delete_thread_after(thread, 86400))

    @discord.ui.button(
        label="전체 일정 보기",
        style=discord.ButtonStyle.secondary,
        custom_id="sv_all_schedule",
        row=0
    )
    async def all_schedule(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)

        url = get_sheet_url(interaction.guild_id)
        if not url:
            await interaction.followup.send("❌ 시트가 연동되지 않았습니다.", ephemeral=True)
            return

        data    = get_all_data(url)
        summary = get_weekly_summary(data)

        if not summary:
            await interaction.followup.send("이번주 예정된 레이드가 없습니다!", ephemeral=True)
            return

        schedule_ch = get_channel(interaction.guild, CH_SCHEDULE)
        if not schedule_ch:
            await interaction.followup.send("❌ 일정조회 채널을 찾을 수 없습니다.", ephemeral=True)
            return

        thread = await schedule_ch.create_thread(
            name="이번주 전체 레이드 일정",
            auto_archive_duration=1440,
            type=discord.ChannelType.public_thread
        )

        embed = _build_weekly_embed(summary)
        await thread.send(
            content=f"{interaction.user.mention}",
            embed=embed
        )

        await interaction.followup.send(
            f"{thread.mention} 에서 확인하세요! (24시간 후 자동 삭제)",
            ephemeral=True
        )

        asyncio.create_task(_delete_thread_after(thread, 86400))

    # ==================== 네비게이션 ====================

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


# ==================== 임베드 빌더 ====================

DAY_ORDER = {'수':0,'목':1,'금':2,'토':3,'일':4,'월':5,'화':6,'미정':7}

def _build_my_schedule_embed(sheet_name: str, schedule: list) -> discord.Embed:
    embed = discord.Embed(
        title=f"📅 {sheet_name}의 이번주 일정",
        color=0x57F287
    )

    day_groups = {}
    for s in schedule:
        day = s.get('day', '미정')
        day_groups.setdefault(day, []).append(s)

    for day in sorted(day_groups, key=lambda d: DAY_ORDER.get(d, 7)):
        raids = day_groups[day]
        lines = []
        for s in raids:
            role_ico = "💚" if s.get('is_support') else "⚔️"
            dur      = s.get('duration', 30)
            dur_str  = f"~{dur//60}h" if dur >= 60 else f"~{dur}m"
            lines.append(f"`{s['time_str']}` {role_ico} **{s['raid_name']}** · {s['character']} · {dur_str}")
        embed.add_field(
            name=f"🗓 {day}요일",
            value="\n".join(lines),
            inline=False
        )

    embed.set_footer(text="24시간 후 자동 삭제")
    return embed


def _build_weekly_embed(summary: list) -> discord.Embed:
    embed = discord.Embed(
        title="📋 이번주 전체 레이드 일정",
        color=0x5865F2
    )

    day_groups = {}
    for raid in summary:
        day = raid.get('day', '미정')
        day_groups.setdefault(day, []).append(raid)

    for day in sorted(day_groups, key=lambda d: DAY_ORDER.get(d, 7)):
        raids = day_groups[day]
        lines = []
        for r in raids:
            count   = r.get('member_count', 0)
            dur     = r.get('duration', 30)
            dur_str = f"~{dur//60}h" if dur >= 60 else f"~{dur}m"
            cleared = "✅" if r.get('cleared') else "⚔️"
            lines.append(f"`{r['time_str']}` {cleared} **{r['name']}** · {count}명 · {dur_str}")
        embed.add_field(
            name=f"🗓 {day}요일",
            value="\n".join(lines),
            inline=False
        )

    embed.set_footer(text="24시간 후 자동 삭제")
    return embed


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
        bot.add_view(ScheduleViewPanel())

    async def send_schedule_panel(self, channel: discord.TextChannel):
        embed = discord.Embed(
            title="🗒 일정 조회",
            description=(
                "**내 일정 보기** — 이번주 내 레이드 일정을 스레드로 확인\n"
                "**전체 일정 보기** — 이번주 전체 레이드 현황 확인\n\n"
                "스레드는 **24시간 후 자동 삭제**됩니다."
            ),
            color=0x5865F2
        )
        view = ScheduleViewPanel()
        msg  = await channel.send(embed=embed, view=view)
        try:
            await msg.pin()
        except Exception:
            pass
        return msg


async def setup(bot):
    await bot.add_cog(ScheduleViewCog(bot))