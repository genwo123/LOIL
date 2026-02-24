"""
로일(LoIl) - 일정 Cog
이미지 렌더러(image_renderer.py) 적용
- 이번주-레이드: 이미지 전송
- 개인 일정: 이미지 전송 (스타일 D 다크카드)
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
    find_user_row,
)
from bot.utils.image_renderer import render_my_schedule, render_weekly_raids

# ==================== 설정 ====================

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


# ==================== 이번주-레이드 고정 버튼 ====================

class WeeklyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="📋 내 일정 보기",
        style=discord.ButtonStyle.primary,
        custom_id="weekly_my_schedule",
        row=0
    )
    async def my_schedule(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(MyScheduleModal())

    @discord.ui.button(
        label="🔄 새로고침",
        style=discord.ButtonStyle.secondary,
        custom_id="weekly_refresh",
        row=0
    )
    async def refresh(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        url = get_sheet_url(interaction.guild_id)
        if not url:
            await interaction.followup.send("❌ 시트가 연동되지 않았습니다.", ephemeral=True)
            return

        data    = get_all_data(url)
        summary = get_weekly_summary(data)

        # 이미지 생성
        buf = render_weekly_raids(summary)
        img_file = discord.File(fp=buf, filename="weekly.png")

        # 기존 메시지 이미지 교체 (새 메시지로 전송 후 기존 삭제)
        await interaction.message.delete()
        channel = interaction.channel
        new_msg = await channel.send(file=img_file, view=WeeklyView())
        try:
            await new_msg.pin()
        except Exception:
            pass

        await interaction.followup.send("✅ 새로고침 완료!", ephemeral=True)


# ==================== 개인 일정 Modal ====================

class MyScheduleModal(discord.ui.Modal, title="📅 내 일정 조회"):
    nickname = discord.ui.TextInput(
        label="길드원 닉네임",
        placeholder="예: 거니",
        min_length=1,
        max_length=30,
        required=True
    )

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

        # 이미지 생성
        buf      = render_my_schedule(name, schedule)
        img_file = discord.File(fp=buf, filename="schedule.png")

        # 일정-조회 채널에 스레드 생성
        query_ch = discord.utils.get(interaction.guild.text_channels, name="일정-조회")
        if query_ch:
            thread = await query_ch.create_thread(
                name=f"📅 {name}의 일정",
                auto_archive_duration=1440,
                type=discord.ChannelType.public_thread
            )
            await thread.send(file=img_file)
            await interaction.followup.send(
                f"✅ {thread.mention} 에서 확인하세요!\n24시간 후 자동 삭제됩니다.",
                ephemeral=True
            )
            asyncio.create_task(delete_thread_after(thread, 86400))
        else:
            await interaction.followup.send(file=img_file, ephemeral=True)



# ==================== ScheduleCog ====================

class ScheduleCog(commands.Cog, name="ScheduleCog"):

    def __init__(self, bot):
        self.bot = bot
        self.weekly_messages: dict[int, int] = {}

    async def update_weekly_channel(self, guild: discord.Guild) -> bool:
        """이번주-레이드 채널 이미지 갱신"""
        url = get_sheet_url(guild.id)
        if not url:
            return False

        data = get_all_data(url)
        if not data:
            return False

        summary  = get_weekly_summary(data)
        buf      = render_weekly_raids(summary)
        img_file = discord.File(fp=buf, filename="weekly.png")
        view     = WeeklyView()

        channel = discord.utils.get(guild.text_channels, name="이번주-레이드")
        if not channel:
            return False

        # 기존 핀 메시지 삭제 후 새로 전송
        # (이미지는 edit으로 교체 불가 → 삭제 후 재전송)
        msg_id = self.weekly_messages.get(guild.id)
        if msg_id:
            try:
                old_msg = await channel.fetch_message(msg_id)
                await old_msg.delete()
            except Exception:
                pass

        # 핀 메시지에서 봇 메시지 찾아 삭제
        try:
            pins = await channel.pins()
            for pin in pins:
                if pin.author == guild.me:
                    await pin.delete()
        except Exception:
            pass

        # 새 이미지 전송 + 핀
        msg = await channel.send(file=img_file, view=view)
        try:
            await msg.pin()
        except Exception:
            pass
        self.weekly_messages[guild.id] = msg.id
        return True

    # ── /일정 ──

    @app_commands.command(name="일정", description="이번주-레이드 채널을 갱신합니다")
    async def show_schedule(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True, ephemeral=True)
        ok = await self.update_weekly_channel(interaction.guild)
        if ok:
            ch = discord.utils.get(interaction.guild.text_channels, name="이번주-레이드")
            await interaction.followup.send(f"✅ {ch.mention} 채널이 갱신됐습니다!", ephemeral=True)
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


async def setup(bot):
    cog = ScheduleCog(bot)
    await bot.add_cog(cog)
    bot.add_view(WeeklyView())