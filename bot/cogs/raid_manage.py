"""
로일(LoIl) - 레이드 관리 Cog
🛡│레이드편성 채널 관리자 전용 기능

기능:
- 레이드 추가 (Modal)
- 레이드 수정 (Select → Modal)
- 레이드 삭제 (Select → 확인)
- 클리어 처리 (Select)
- 시트 → 봇 새로고침
"""

import discord
from discord.ext import commands
from discord import app_commands
import json, os

from bot.utils.sheets import (
    get_all_data, parse_all_raids,
    add_raid, update_raid, delete_raid,
    set_scheduled, set_cleared
)
from bot.utils.permissions import require_admin
from bot.config.channels import CH_PARTY, get_channel

SETTINGS_FILE = "bot/data/guild_settings.json"

def get_sheet_url(guild_id: int) -> str:
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f).get(str(guild_id), {}).get("sheet_url", "")
    except Exception:
        return ""


# ==================== 요일 선택 ====================

DAYS = ['수', '목', '금', '토', '일', '월', '화']

DAY_OPTIONS = [
    discord.SelectOption(label=f"{d}요일", value=d)
    for d in DAYS
]

DURATION_OPTIONS = [
    discord.SelectOption(label="30분",    value="1"),
    discord.SelectOption(label="1시간",   value="2"),
    discord.SelectOption(label="1시간30분", value="3"),
    discord.SelectOption(label="2시간",   value="4"),
]


# ==================== 레이드 추가 Modal ====================

class AddRaidModal(discord.ui.Modal, title="레이드 추가"):
    raid_name = discord.ui.TextInput(
        label="레이드 이름",
        placeholder="예: 종막(노)1, 세르카(하)2",
        max_length=30,
        required=True
    )
    day = discord.ui.TextInput(
        label="요일 (수목금토일월화 중 하나)",
        placeholder="예: 수",
        max_length=1,
        required=True
    )
    time = discord.ui.TextInput(
        label="시작 시간",
        placeholder="예: 20:00 또는 21:30",
        max_length=5,
        required=True
    )
    duration = discord.ui.TextInput(
        label="예상 소요 (30분 단위, 숫자만)",
        placeholder="예: 1=30분, 2=1시간, 3=1시간30분",
        max_length=1,
        required=True,
        default="2"
    )

    async def on_submit(self, interaction: discord.Interaction):
        url = get_sheet_url(interaction.guild_id)
        if not url:
            await interaction.response.send_message("❌ 시트가 연동되지 않았습니다.", ephemeral=True)
            return

        # 입력값 파싱
        day_val = self.day.value.strip()
        if day_val not in DAYS:
            await interaction.response.send_message(
                f"❌ 요일은 수목금토일월화 중 하나를 입력해주세요. (입력값: {day_val})", ephemeral=True
            )
            return

        time_str = self.time.value.strip()
        try:
            parts  = time_str.split(":")
            hour   = int(parts[0])
            minute = 30 if len(parts) > 1 and parts[1] == "30" else 0
        except Exception:
            await interaction.response.send_message("❌ 시간 형식이 올바르지 않습니다. (예: 20:00)", ephemeral=True)
            return

        try:
            dur = int(self.duration.value.strip())
        except Exception:
            dur = 2

        await interaction.response.defer(ephemeral=True)

        ok = add_raid(
            url=url,
            name=self.raid_name.value.strip(),
            day=day_val,
            hour=hour,
            minute=minute,
            duration_blocks=dur
        )

        if ok:
            # 이번주레이드 채널 갱신
            schedule_cog = interaction.client.cogs.get("ScheduleCog")
            if schedule_cog:
                await schedule_cog.update_weekly_channel(interaction.guild)

            await interaction.followup.send(
                f"✅ **{self.raid_name.value.strip()}** 레이드가 추가되었습니다!\n"
                f"{day_val}요일 {time_str}",
                ephemeral=True
            )
        else:
            await interaction.followup.send("❌ 레이드 추가에 실패했습니다.", ephemeral=True)


# ==================== 레이드 수정 Modal ====================

class EditRaidModal(discord.ui.Modal, title="레이드 수정"):

    def __init__(self, raid: dict, url: str):
        super().__init__()
        self.raid = raid
        self.url  = url

        self.raid_name = discord.ui.TextInput(
            label="레이드 이름",
            default=raid['name'],
            max_length=30,
            required=True
        )
        self.day = discord.ui.TextInput(
            label="요일",
            default=raid['day'],
            max_length=1,
            required=True
        )
        self.time = discord.ui.TextInput(
            label="시작 시간 (예: 20:00)",
            default=raid['time_str'],
            max_length=5,
            required=True
        )
        self.duration = discord.ui.TextInput(
            label="예상 소요 블록 (1=30분)",
            default=str(raid['duration'] // 30),
            max_length=1,
            required=True
        )
        self.add_item(self.raid_name)
        self.add_item(self.day)
        self.add_item(self.time)
        self.add_item(self.duration)

    async def on_submit(self, interaction: discord.Interaction):
        day_val = self.day.value.strip()
        if day_val not in DAYS:
            await interaction.response.send_message("❌ 요일은 수목금토일월화 중 하나를 입력해주세요.", ephemeral=True)
            return

        time_str = self.time.value.strip()
        try:
            parts  = time_str.split(":")
            hour   = int(parts[0])
            minute = 30 if len(parts) > 1 and parts[1] == "30" else 0
        except Exception:
            await interaction.response.send_message("❌ 시간 형식이 올바르지 않습니다.", ephemeral=True)
            return

        try:
            dur = int(self.duration.value.strip())
        except Exception:
            dur = 2

        await interaction.response.defer(ephemeral=True)

        ok = update_raid(
            url=self.url,
            col=self.raid['col'],
            name=self.raid_name.value.strip(),
            day=day_val,
            hour=hour,
            minute=minute,
            duration_blocks=dur
        )

        if ok:
            schedule_cog = interaction.client.cogs.get("ScheduleCog")
            if schedule_cog:
                await schedule_cog.update_weekly_channel(interaction.guild)
            await interaction.followup.send(
                f"✅ **{self.raid_name.value.strip()}** 레이드가 수정되었습니다!", ephemeral=True
            )
        else:
            await interaction.followup.send("❌ 수정에 실패했습니다.", ephemeral=True)


# ==================== 레이드 선택 드롭다운 ====================

class RaidSelectForAction(discord.ui.Select):
    def __init__(self, raids: list, action: str, url: str):
        self.raids  = raids
        self.action = action  # "edit" | "delete" | "clear" | "toggle"
        self.url    = url

        options = [
            discord.SelectOption(
                label=r['name'],
                description=f"{r['day']}요일 {r['time_str']} · {'예정' if r['scheduled'] else '미예정'}",
                value=str(i)
            )
            for i, r in enumerate(raids[:25])
        ]
        super().__init__(placeholder="레이드를 선택하세요", options=options)

    async def callback(self, interaction: discord.Interaction):
        idx  = int(self.values[0])
        raid = self.raids[idx]

        if self.action == "edit":
            await interaction.response.send_modal(EditRaidModal(raid=raid, url=self.url))

        elif self.action == "delete":
            view = ConfirmDeleteView(raid=raid, url=self.url)
            await interaction.response.send_message(
                f"**{raid['name']}** ({raid['day']}요일 {raid['time_str']}) 을 삭제할까요?",
                view=view,
                ephemeral=True
            )

        elif self.action == "clear":
            await interaction.response.defer(ephemeral=True)
            ok = set_cleared(self.url, raid['col'], True)
            if ok:
                schedule_cog = interaction.client.cogs.get("ScheduleCog")
                if schedule_cog:
                    await schedule_cog.update_weekly_channel(interaction.guild)
                await interaction.followup.send(
                    f"✅ **{raid['name']}** 클리어 처리되었습니다!", ephemeral=True
                )
            else:
                await interaction.followup.send("❌ 처리에 실패했습니다.", ephemeral=True)

        elif self.action == "toggle":
            await interaction.response.defer(ephemeral=True)
            new_state = not raid['scheduled']
            ok = set_scheduled(self.url, raid['col'], new_state)
            if ok:
                schedule_cog = interaction.client.cogs.get("ScheduleCog")
                if schedule_cog:
                    await schedule_cog.update_weekly_channel(interaction.guild)
                state_str = "예정" if new_state else "미예정"
                await interaction.followup.send(
                    f"✅ **{raid['name']}** → **{state_str}** 으로 변경되었습니다!", ephemeral=True
                )
            else:
                await interaction.followup.send("❌ 처리에 실패했습니다.", ephemeral=True)


class RaidActionView(discord.ui.View):
    def __init__(self, raids: list, action: str, url: str):
        super().__init__(timeout=60)
        self.add_item(RaidSelectForAction(raids=raids, action=action, url=url))


# ==================== 삭제 확인 View ====================

class ConfirmDeleteView(discord.ui.View):
    def __init__(self, raid: dict, url: str):
        super().__init__(timeout=30)
        self.raid = raid
        self.url  = url

    @discord.ui.button(label="삭제 확인", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        ok = delete_raid(self.url, self.raid['col'])
        if ok:
            schedule_cog = interaction.client.cogs.get("ScheduleCog")
            if schedule_cog:
                await schedule_cog.update_weekly_channel(interaction.guild)
            await interaction.followup.send(
                f"✅ **{self.raid['name']}** 레이드가 삭제되었습니다!", ephemeral=True
            )
        else:
            await interaction.followup.send("❌ 삭제에 실패했습니다.", ephemeral=True)
        self.stop()

    @discord.ui.button(label="취소", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("취소되었습니다.", ephemeral=True)
        self.stop()


# ==================== RaidManageCog ====================

class RaidManageCog(commands.Cog, name="RaidManageCog"):

    def __init__(self, bot):
        self.bot = bot

    async def _get_raids_or_error(self, interaction) -> tuple:
        """url, raids 반환. 실패 시 None, None"""
        url = get_sheet_url(interaction.guild_id)
        if not url:
            await interaction.response.send_message(
                "❌ 시트가 연동되지 않았습니다. ⚙│봇설정 채널에서 먼저 설정해주세요.", ephemeral=True
            )
            return None, None

        data  = get_all_data(url)
        raids = parse_all_raids(data)
        if not raids:
            await interaction.response.send_message("❌ 레이드가 없습니다.", ephemeral=True)
            return None, None

        return url, raids

    @app_commands.command(name="레이드추가", description="레이드를 추가합니다 (관리자)")
    async def add_raid_cmd(self, interaction: discord.Interaction):
        if not await require_admin(interaction): return
        url = get_sheet_url(interaction.guild_id)
        if not url:
            await interaction.response.send_message("❌ 시트가 연동되지 않았습니다.", ephemeral=True)
            return
        await interaction.response.send_modal(AddRaidModal())

    @app_commands.command(name="레이드수정", description="레이드를 수정합니다 (관리자)")
    async def edit_raid_cmd(self, interaction: discord.Interaction):
        if not await require_admin(interaction): return
        url, raids = await self._get_raids_or_error(interaction)
        if not raids: return
        view = RaidActionView(raids=raids, action="edit", url=url)
        await interaction.response.send_message("수정할 레이드를 선택하세요:", view=view, ephemeral=True)

    @app_commands.command(name="레이드삭제", description="레이드를 삭제합니다 (관리자)")
    async def delete_raid_cmd(self, interaction: discord.Interaction):
        if not await require_admin(interaction): return
        url, raids = await self._get_raids_or_error(interaction)
        if not raids: return
        view = RaidActionView(raids=raids, action="delete", url=url)
        await interaction.response.send_message("삭제할 레이드를 선택하세요:", view=view, ephemeral=True)

    @app_commands.command(name="레이드클리어", description="레이드 클리어 처리합니다 (관리자)")
    async def clear_raid_cmd(self, interaction: discord.Interaction):
        if not await require_admin(interaction): return
        url, raids = await self._get_raids_or_error(interaction)
        if not raids: return
        view = RaidActionView(raids=raids, action="clear", url=url)
        await interaction.response.send_message("클리어할 레이드를 선택하세요:", view=view, ephemeral=True)

    @app_commands.command(name="레이드토글", description="레이드 예정/미예정 전환 (관리자)")
    async def toggle_raid_cmd(self, interaction: discord.Interaction):
        if not await require_admin(interaction): return
        url, raids = await self._get_raids_or_error(interaction)
        if not raids: return
        view = RaidActionView(raids=raids, action="toggle", url=url)
        await interaction.response.send_message("전환할 레이드를 선택하세요:", view=view, ephemeral=True)

    @app_commands.command(name="레이드갱신", description="시트 변경사항을 봇에 반영합니다")
    async def refresh_raid_cmd(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        schedule_cog = interaction.client.cogs.get("ScheduleCog")
        if schedule_cog:
            ok = await schedule_cog.update_weekly_channel(interaction.guild)
            if ok:
                await interaction.followup.send("✅ 이번주레이드 채널이 갱신되었습니다!", ephemeral=True)
                return
        await interaction.followup.send("❌ 갱신에 실패했습니다.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(RaidManageCog(bot))