"""
로일(LoIl) - 일정 Cog
버튼 중심 UI + 2가지 모드 (예정된 일정 / 전체 일정)
"""

import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import json
import os
from typing import Optional
from bot.utils.sheets import (
    get_all_data,
    get_user_schedule,
    get_weekly_summary,
    parse_raids,
    find_user_row
)

# ==================== 설정 불러오기 ====================

SETTINGS_FILE = "bot/data/guild_settings.json"

def get_sheet_url(guild_id: int) -> Optional[str]:
    if not os.path.exists(SETTINGS_FILE):
        return None
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f).get(str(guild_id), {}).get("sheet_url")
    except Exception:
        return None


async def delete_thread_after(thread: discord.Thread, seconds: int):
    await asyncio.sleep(seconds)
    try:
        await thread.delete()
    except Exception:
        pass


# ==================== 서폿 판별 ====================

SUPPORT_JOBS = {'홀리나이트', '홀나', '바드', '도화가', '발키리'}

def is_support(char_name: str) -> bool:
    if not char_name:
        return False
    base = char_name.split('(')[0].strip()
    return base in SUPPORT_JOBS or '폿' in char_name


# ==================== 임베드 빌더 ====================

def build_weekly_embed(summary: list, mode: str = "scheduled") -> discord.Embed:
    """
    이번주 전체 레이드 임베드
    mode: "scheduled" = 예정된 것만 / "all" = 전체
    """
    if mode == "all":
        title  = "📋 전체 레이드 일정 (미정 포함)"
        color  = 0xFEE75C
        target = summary  # 전체
    else:
        title  = "📅 이번 주 레이드 일정"
        color  = 0x5865F2
        target = [r for r in summary if r.get('scheduled')]

    embed = discord.Embed(title=title, color=color)

    if not target:
        embed.description = "📭 이번 주 등록된 레이드가 없습니다."
        embed.set_footer(text="매주 수요일 자동 갱신")
        return embed

    # 요일별 그룹
    day_order  = {'월': 0, '화': 1, '수': 2, '목': 3, '금': 4, '토': 5, '일': 6, '미정': 7}
    day_groups = {}
    for raid in target:
        day = raid.get('day', '미정')
        if day not in day_groups:
            day_groups[day] = []
        day_groups[day].append(raid)

    day_emoji = {'월': '🗓', '화': '🗓', '수': '🗓', '목': '🗓', '금': '🗓', '토': '🗓', '일': '🗓', '미정': '❓'}

    for day in sorted(day_groups, key=lambda d: day_order.get(d, 7)):
        raids = day_groups[day]
        lines = []
        for r in raids:
            count    = r.get('member_count', 0)
            dur      = r.get('duration', 30)
            dur_str  = f"~{dur//60}h" if dur >= 60 else f"~{dur}m"
            cleared  = "✅ " if r.get('cleared') else ""
            time_str = r.get('time_str', '?:??')
            lines.append(f"`{time_str}` {cleared}**{r['name']}** · {count}명 · {dur_str}")

        embed.add_field(
            name=f"{day_emoji.get(day, '🗓')} {day}요일",
            value="\n".join(lines),
            inline=False
        )

    embed.set_footer(text="📋 내 일정 보기 버튼으로 개인 일정 확인 · 매주 수요일 자동 갱신")
    return embed


def build_my_schedule_embed(nickname: str, schedule: list, mode: str = "scheduled") -> discord.Embed:
    """
    개인 일정 임베드
    mode: "scheduled" = 예정된 것만 / "all" = 전체
    """
    if mode == "all":
        title  = f"📋 {nickname}의 전체 일정 (미정 포함)"
        color  = 0xFEE75C
        target = schedule
    else:
        title  = f"📅 {nickname}의 이번 주 일정"
        color  = 0x57F287
        target = [s for s in schedule if s.get('scheduled', True)]

    embed = discord.Embed(title=title, color=color)

    if not target:
        embed.description = "이번 주 예정된 레이드가 없습니다."
        return embed

    # 요일별 그룹
    day_order  = {'월': 0, '화': 1, '수': 2, '목': 3, '금': 4, '토': 5, '일': 6, '미정': 7}
    day_groups = {}
    for s in target:
        day = s.get('day', '미정')
        if day not in day_groups:
            day_groups[day] = []
        day_groups[day].append(s)

    for day in sorted(day_groups, key=lambda d: day_order.get(d, 7)):
        raids  = day_groups[day]
        lines  = []
        for s in raids:
            char     = s.get('character', '')
            role_ico = "💚" if s.get('is_support') else "⚔️"
            dur      = s.get('duration', 30)
            dur_str  = f"~{dur//60}h" if dur >= 60 else f"~{dur}m"
            time_str = s.get('time_str', '?:??')
            lines.append(
                f"`{time_str}` {role_ico} **{s['raid_name']}** · {char} · {dur_str}"
            )

        embed.add_field(
            name=f"🗓 {day}요일",
            value="\n".join(lines),
            inline=False
        )

    total = len(target)
    sup   = sum(1 for s in target if s.get('is_support'))
    dps   = total - sup
    embed.set_footer(text=f"총 {total}개 · ⚔️ 딜러 {dps}개 · 💚 서폿 {sup}개 · 24시간 후 자동 삭제")
    return embed


# ==================== 버튼 View ====================

class WeeklyView(discord.ui.View):
    """이번주-레이드 채널 고정 버튼"""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="📋 내 일정 보기",
        style=discord.ButtonStyle.primary,
        custom_id="weekly_my_schedule",
        row=0
    )
    async def my_schedule(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(MyScheduleModal(mode="scheduled"))

    @discord.ui.button(
        label="📋 전체 일정 보기",
        style=discord.ButtonStyle.secondary,
        custom_id="weekly_my_schedule_all",
        row=0
    )
    async def my_schedule_all(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(MyScheduleModal(mode="all"))

    @discord.ui.button(
        label="🔄 새로고침",
        style=discord.ButtonStyle.secondary,
        custom_id="weekly_refresh",
        row=1
    )
    async def refresh(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        url = get_sheet_url(interaction.guild_id)
        if not url:
            await interaction.followup.send("❌ 시트가 연동되지 않았습니다.", ephemeral=True)
            return
        data    = get_all_data(url)
        summary = get_weekly_summary(data)
        embed   = build_weekly_embed(summary, mode="scheduled")
        await interaction.message.edit(embed=embed, view=WeeklyView())
        await interaction.followup.send("✅ 새로고침 완료!", ephemeral=True)

    @discord.ui.button(
        label="📊 전체 레이드 현황",
        style=discord.ButtonStyle.secondary,
        custom_id="weekly_all_raids",
        row=1
    )
    async def all_raids(self, interaction: discord.Interaction, button: discord.ui.Button):
        """미정 포함 전체 레이드 현황"""
        await interaction.response.defer(ephemeral=True)
        url = get_sheet_url(interaction.guild_id)
        if not url:
            await interaction.followup.send("❌ 시트가 연동되지 않았습니다.", ephemeral=True)
            return
        data    = get_all_data(url)
        summary = get_weekly_summary(data)
        embed   = build_weekly_embed(summary, mode="all")
        await interaction.followup.send(embed=embed, ephemeral=True)


class MyScheduleModal(discord.ui.Modal):
    """닉네임 입력 Modal"""

    nickname = discord.ui.TextInput(
        label="길드원 닉네임",
        placeholder="예: 거니",
        min_length=1,
        max_length=30,
        required=True
    )

    def __init__(self, mode: str = "scheduled"):
        title = "📅 내 일정 조회" if mode == "scheduled" else "📋 전체 일정 조회"
        super().__init__(title=title)
        self.mode = mode

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        name = self.nickname.value.strip()
        url  = get_sheet_url(interaction.guild_id)

        if not url:
            await interaction.followup.send("❌ 시트가 연동되지 않았습니다.", ephemeral=True)
            return

        data = get_all_data(url)
        if not data:
            await interaction.followup.send("❌ 시트를 읽을 수 없습니다.", ephemeral=True)
            return

        if find_user_row(data, name) is None:
            await interaction.followup.send(
                f"❌ `{name}` 을 찾을 수 없습니다!\n닉네임을 정확히 입력해주세요.",
                ephemeral=True
            )
            return

        schedule = get_user_schedule(data, name)
        embed    = build_my_schedule_embed(name, schedule, mode=self.mode)

        # 일정-조회 채널에 스레드 생성
        query_channel = discord.utils.get(
            interaction.guild.text_channels, name="일정-조회"
        )
        if query_channel:
            thread = await query_channel.create_thread(
                name=f"📅 {name}의 일정",
                auto_archive_duration=1440,
                type=discord.ChannelType.public_thread
            )
            view = ScheduleThreadView(name=name)
            await thread.send(embed=embed, view=view)
            await interaction.followup.send(
                f"✅ {thread.mention} 에서 확인하세요! (24시간 후 자동 삭제)",
                ephemeral=True
            )
            asyncio.create_task(delete_thread_after(thread, 86400))
        else:
            await interaction.followup.send(embed=embed, ephemeral=True)


class ScheduleThreadView(discord.ui.View):
    """스레드 안 버튼 (모드 전환)"""

    def __init__(self, name: str):
        super().__init__(timeout=86400)
        self.name = name

    @discord.ui.button(
        label="📋 전체 일정 보기 (미정 포함)",
        style=discord.ButtonStyle.secondary,
        custom_id="thread_show_all"
    )
    async def show_all(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        url = get_sheet_url(interaction.guild_id)
        if not url:
            await interaction.followup.send("❌ 시트 연동 필요", ephemeral=True)
            return
        data     = get_all_data(url)
        schedule = get_user_schedule(data, self.name)
        embed    = build_my_schedule_embed(self.name, schedule, mode="all")
        await interaction.message.edit(embed=embed, view=self)

    @discord.ui.button(
        label="📅 예정된 일정만",
        style=discord.ButtonStyle.primary,
        custom_id="thread_show_scheduled"
    )
    async def show_scheduled(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        url = get_sheet_url(interaction.guild_id)
        if not url:
            await interaction.followup.send("❌ 시트 연동 필요", ephemeral=True)
            return
        data     = get_all_data(url)
        schedule = get_user_schedule(data, self.name)
        embed    = build_my_schedule_embed(self.name, schedule, mode="scheduled")
        await interaction.message.edit(embed=embed, view=self)


# ==================== ScheduleCog ====================

class ScheduleCog(commands.Cog, name="ScheduleCog"):

    def __init__(self, bot):
        self.bot = bot
        self.weekly_messages: dict[int, int] = {}

    # ── 이번주-레이드 채널 갱신 ──

    async def update_weekly_channel(self, guild: discord.Guild):
        """이번주-레이드 채널 메시지 Edit 또는 새로 전송"""
        url = get_sheet_url(guild.id)
        if not url:
            return False

        data    = get_all_data(url)
        if not data:
            return False

        summary = get_weekly_summary(data)
        embed   = build_weekly_embed(summary, mode="scheduled")
        view    = WeeklyView()

        channel = discord.utils.get(guild.text_channels, name="이번주-레이드")
        if not channel:
            return False

        # 저장된 메시지 Edit 시도
        msg_id = self.weekly_messages.get(guild.id)
        if msg_id:
            try:
                msg = await channel.fetch_message(msg_id)
                await msg.edit(embed=embed, view=view)
                return True
            except Exception:
                pass

        # 고정 메시지에서 찾기
        try:
            pins = await channel.pins()
            for pin in pins:
                if pin.author == guild.me:
                    await pin.edit(embed=embed, view=view)
                    self.weekly_messages[guild.id] = pin.id
                    return True
        except Exception:
            pass

        # 없으면 새로 전송 + 고정
        msg = await channel.send(embed=embed, view=view)
        try:
            await msg.pin()
        except Exception:
            pass
        self.weekly_messages[guild.id] = msg.id
        return True

    # ── /일정 (수동 갱신) ──

    @app_commands.command(name="일정", description="이번주-레이드 채널을 갱신합니다")
    async def show_schedule(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True, ephemeral=True)
        ok = await self.update_weekly_channel(interaction.guild)
        if ok:
            channel = discord.utils.get(interaction.guild.text_channels, name="이번주-레이드")
            await interaction.followup.send(
                f"✅ {channel.mention} 채널이 갱신됐습니다!", ephemeral=True
            )
        else:
            await interaction.followup.send(
                "❌ 시트가 연동되지 않았습니다.\n⚙️ **로일-설정** 채널에서 먼저 설정해주세요.",
                ephemeral=True
            )

    # ── /이번주갱신 (관리자) ──

    @app_commands.command(name="이번주갱신", description="이번주-레이드 채널을 수동 갱신합니다 (관리자)")
    @app_commands.checks.has_permissions(administrator=True)
    async def refresh_weekly(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True, ephemeral=True)
        ok = await self.update_weekly_channel(interaction.guild)
        if ok:
            await interaction.followup.send("✅ 갱신 완료!", ephemeral=True)
        else:
            await interaction.followup.send("❌ 시트 연동 필요", ephemeral=True)

    @refresh_weekly.error
    async def refresh_error(self, interaction, error):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message("❌ 관리자만 사용 가능합니다.", ephemeral=True)


# ==================== Cog 등록 ====================

async def setup(bot):
    cog = ScheduleCog(bot)
    await bot.add_cog(cog)
    bot.add_view(WeeklyView())