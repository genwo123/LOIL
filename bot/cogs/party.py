"""
로일(LoIl) - 파티 Cog
이미지 렌더러(image_renderer.py) 적용
"""

import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import json
import os
import random

from bot.utils.gemini_ai import recommend_party
from bot.utils.synergy_ui import SynergyClassSelectView
from bot.utils.permissions import require_admin, is_admin
from bot.utils.sheets import get_all_data, get_members, parse_raids, parse_all_raids, save_party_result
from bot.utils.image_renderer import render_party_result
from bot.config.settings import GEMINI_API_KEY, RAIDS_DATA
from bot.config.channels import CH_PARTY, CH_NOTICE, CH_SCHEDULE, CH_SUGGEST, get_channel

SETTINGS_FILE = "bot/data/guild_settings.json"

def get_guild_setting(guild_id: int) -> dict:
    if not os.path.exists(SETTINGS_FILE):
        return {}
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f).get(str(guild_id), {})
    except Exception:
        return {}

def get_sheet_url(guild_id: int) -> str:
    return get_guild_setting(guild_id).get("sheet_url", "")

def get_gemini_key(guild_id: int) -> str:
    key = get_guild_setting(guild_id).get("gemini_api_key", "")
    return key if key else GEMINI_API_KEY

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


# ==================== 레이드 정렬 ====================

CATEGORY_ORDER = {
    "shadow_raids":  0,
    "kazeros_raids": 1,
    "legion_raids":  2,
    "abyss_raids":   3,
    "epic_raids":    4,
}
KAZEROS_ORDER    = ['종막', '4막', '3막', '2막', '1막', '서막']
LEGION_ORDER     = ['카멘', '일리아칸', '아브렐슈드', '쿠크세이튼', '비아키스', '발탄']
DIFFICULTY_ORDER = {'nightmare':0,'나이트메어':0,'나메':0,'hard':1,'하드':1,'normal':2,'노말':2}

def get_raid_sort_key(raid: dict) -> tuple:
    cat        = raid.get('category', '')
    name       = raid.get('name', '')
    diff       = raid.get('difficulty', '').lower()
    cat_order  = CATEGORY_ORDER.get(cat, 99)
    diff_order = DIFFICULTY_ORDER.get(diff, 99)
    if cat == 'kazeros_raids':
        raid_order = next((i for i, n in enumerate(KAZEROS_ORDER) if n in name), 99)
    elif cat == 'legion_raids':
        raid_order = next((i for i, n in enumerate(LEGION_ORDER) if n in name), 99)
    else:
        raid_order = 0
    return (cat_order, raid_order, diff_order)

def get_sorted_raids(raids: list) -> list:
    return sorted(raids, key=get_raid_sort_key)


# ==================== 파티 편성 로직 ====================

def build_party_groups(members: list, party_size: int = 4) -> list[list]:
    supports = [m for m in members if m.get('is_support')]
    dps      = [m for m in members if not m.get('is_support')]
    parties  = []
    dps_idx  = 0
    for supp in supports:
        party = []
        while dps_idx < len(dps) and len(party) < party_size - 1:
            party.append(dps[dps_idx])
            dps_idx += 1
        party.append(supp)
        parties.append(party)
    remaining = dps[dps_idx:]
    while remaining:
        parties.append(remaining[:party_size])
        remaining = remaining[party_size:]
    return parties


# ==================== 고정 패널 임베드 ====================

def build_party_panel_embed() -> discord.Embed:
    embed = discord.Embed(
        title="🛡 레이드 편성 센터",
        description=(
            "구글 시트의 이번 주 참가자를 불러와\n"
            "**AI가 최적의 파티를 자동 구성**합니다.\n\n"
            "시간 충돌 자동 감지 · 서폿 자동 배치 · 시너지 고려"
        ),
        color=0x5865F2
    )
    embed.add_field(
        name="편성",
        value=(
            "주간 전체 편성 — 레이드 선택 후 AI가 한번에 편성\n"
            "개별 레이드 편성 — 레이드 하나만 선택해 편성\n"
            "시너지 분석 — 직업 목록 입력 → 시너지 분석"
        ),
        inline=True
    )
    embed.add_field(
        name="레이드 관리 (관리자)",
        value=(
            "레이드 추가 / 수정 / 삭제\n"
            "클리어 처리 / 예정 토글"
        ),
        inline=True
    )
    embed.set_footer(text="결과는 이미지로 스레드에 표시됩니다 · 확정 후 시트 자동 저장")
    return embed


# ==================== 파티 고정 패널 View ====================

class PartyPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    # ── Row 0: 편성 ──

    @discord.ui.button(label="주간 전체 편성", style=discord.ButtonStyle.primary, custom_id="party_weekly", row=0)
    async def weekly_party(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        url = get_sheet_url(interaction.guild_id)
        if not url:
            await interaction.followup.send("❌ 시트가 연동되지 않았습니다.", ephemeral=True)
            return
        data  = get_all_data(url)
        raids = get_sorted_raids(parse_raids(data))
        if not raids:
            await interaction.followup.send("❌ 이번 주 예정된 레이드가 없습니다.", ephemeral=True)
            return
        view  = RaidChecklistView(raids=raids, guild_id=interaction.guild_id, data=data)
        embed = discord.Embed(
            title="주간 전체 편성",
            description=f"편성할 레이드를 선택하세요 · 총 **{len(raids)}개**",
            color=0x5865F2
        )
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)

    @discord.ui.button(label="개별 레이드 편성", style=discord.ButtonStyle.secondary, custom_id="party_individual", row=0)
    async def individual_party(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        url = get_sheet_url(interaction.guild_id)
        if not url:
            await interaction.followup.send("❌ 시트가 연동되지 않았습니다.", ephemeral=True)
            return
        data  = get_all_data(url)
        raids = get_sorted_raids(parse_raids(data))
        if not raids:
            await interaction.followup.send("❌ 이번 주 예정된 레이드가 없습니다.", ephemeral=True)
            return
        view  = IndividualRaidSelectView(raids=raids, guild_id=interaction.guild_id, data=data)
        embed = discord.Embed(title="개별 레이드 편성", description="편성할 레이드를 선택하세요", color=0x5865F2)
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)

    @discord.ui.button(label="시너지 분석", style=discord.ButtonStyle.secondary, custom_id="party_synergy", row=0)
    async def synergy(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="시너지 분석 — 클래스 선택",
            description="분석할 직업의 클래스를 선택하세요",
            color=0x9B59B6
        )
        await interaction.response.send_message(embed=embed, view=SynergyClassSelectView(), ephemeral=True)

    # ── Row 1: 레이드 관리 (관리자) ──

    @discord.ui.button(label="레이드 추가", style=discord.ButtonStyle.success, custom_id="party_raid_add", row=1)
    async def raid_add(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await require_admin(interaction): return
        from bot.cogs.raid_manage import AddRaidModal
        url = get_sheet_url(interaction.guild_id)
        if not url:
            await interaction.response.send_message("❌ 시트가 연동되지 않았습니다.", ephemeral=True)
            return
        await interaction.response.send_modal(AddRaidModal())

    @discord.ui.button(label="레이드 수정", style=discord.ButtonStyle.secondary, custom_id="party_raid_edit", row=1)
    async def raid_edit(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await require_admin(interaction): return
        from bot.cogs.raid_manage import RaidActionView
        url = get_sheet_url(interaction.guild_id)
        if not url:
            await interaction.response.send_message("❌ 시트가 연동되지 않았습니다.", ephemeral=True)
            return
        data  = get_all_data(url)
        raids = parse_all_raids(data)
        if not raids:
            await interaction.response.send_message("❌ 레이드가 없습니다.", ephemeral=True)
            return
        await interaction.response.send_message(
            "수정할 레이드를 선택하세요:",
            view=RaidActionView(raids=raids, action="edit", url=url),
            ephemeral=True
        )

    @discord.ui.button(label="레이드 삭제", style=discord.ButtonStyle.danger, custom_id="party_raid_delete", row=1)
    async def raid_delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await require_admin(interaction): return
        from bot.cogs.raid_manage import RaidActionView
        url = get_sheet_url(interaction.guild_id)
        if not url:
            await interaction.response.send_message("❌ 시트가 연동되지 않았습니다.", ephemeral=True)
            return
        data  = get_all_data(url)
        raids = parse_all_raids(data)
        if not raids:
            await interaction.response.send_message("❌ 레이드가 없습니다.", ephemeral=True)
            return
        await interaction.response.send_message(
            "삭제할 레이드를 선택하세요:",
            view=RaidActionView(raids=raids, action="delete", url=url),
            ephemeral=True
        )

    # ── Row 2: 네비게이션 ──

    @discord.ui.button(label="공지 →", style=discord.ButtonStyle.secondary, custom_id="party_to_notice", row=2)
    async def to_notice(self, interaction: discord.Interaction, button: discord.ui.Button):
        ch = get_channel(interaction.guild, CH_NOTICE)
        await interaction.response.send_message(
            f"{ch.mention} 으로 이동하세요!" if ch else "채널을 찾을 수 없습니다.", ephemeral=True
        )

    @discord.ui.button(label="일정 조회 →", style=discord.ButtonStyle.secondary, custom_id="party_to_schedule", row=2)
    async def to_schedule(self, interaction: discord.Interaction, button: discord.ui.Button):
        ch = get_channel(interaction.guild, CH_SCHEDULE)
        await interaction.response.send_message(
            f"{ch.mention} 으로 이동하세요!" if ch else "채널을 찾을 수 없습니다.", ephemeral=True
        )

    @discord.ui.button(label="건의함 →", style=discord.ButtonStyle.secondary, custom_id="party_to_suggest", row=2)
    async def to_suggest(self, interaction: discord.Interaction, button: discord.ui.Button):
        ch = get_channel(interaction.guild, CH_SUGGEST)
        await interaction.response.send_message(
            f"{ch.mention} 으로 이동하세요!" if ch else "채널을 찾을 수 없습니다.", ephemeral=True
        )

    @discord.ui.button(label="새로고침", style=discord.ButtonStyle.secondary, custom_id="party_refresh", row=2)
    async def refresh(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        party_cog = interaction.client.cogs.get("PartyCog")
        if party_cog:
            await party_cog.refresh_party_panel(interaction.guild)
        await interaction.followup.send("패널이 갱신되었습니다!", ephemeral=True)


# ==================== 주간 체크리스트 ====================

class RaidChecklistView(discord.ui.View):
    def __init__(self, raids: list, guild_id: int, data: list):
        super().__init__(timeout=180)
        self.raids    = raids
        self.guild_id = guild_id
        self.data     = data
        self.selected: set[int] = set(range(len(raids)))
        self._build_select()

    def _build_select(self):
        for item in self.children.copy():
            if isinstance(item, discord.ui.Select):
                self.remove_item(item)
        options = [
            discord.SelectOption(
                label=r.get('name', '')[:100],
                description=f"{r.get('day','')} {r.get('time_str','')} · {r.get('member_count', 0)}명",
                value=str(i),
                default=(i in self.selected)
            )
            for i, r in enumerate(self.raids)
        ]
        select = discord.ui.Select(
            placeholder="레이드 선택 (여러 개 가능)",
            options=options[:25],
            min_values=1,
            max_values=min(len(options), 25),
            custom_id="raid_checklist_select",
            row=0
        )
        select.callback = self._on_select
        self.add_item(select)

    async def _on_select(self, interaction: discord.Interaction):
        select = discord.utils.get(self.children, custom_id="raid_checklist_select")
        if select:
            self.selected = {int(v) for v in select.values}
        await interaction.response.defer()

    @discord.ui.button(label="🤖 AI 편성", style=discord.ButtonStyle.primary, custom_id="weekly_ai_compose", row=1)
    async def ai_compose(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.selected:
            await interaction.response.send_message("❌ 레이드를 하나 이상 선택해주세요!", ephemeral=True)
            return

        selected_raids = [self.raids[i] for i in sorted(self.selected)]
        await interaction.response.defer(ephemeral=True)

        party_ch = get_channel(interaction.guild, CH_PARTY)
        if not party_ch:
            await interaction.followup.send("❌ 레이드편성 채널이 없습니다.", ephemeral=True)
            return

        thread = await party_ch.create_thread(
            name="📅 주간 파티 편성",
            auto_archive_duration=10080,
            type=discord.ChannelType.public_thread
        )
        await thread.send("🤖 AI 파티 편성 중... 잠시만 기다려주세요!")
        await interaction.followup.send(f"✅ {thread.mention} 에서 확인하세요!", ephemeral=True)

        all_results = {}
        members_raw = get_members(self.data)

        from bot.utils.member_link import get_absences
        absences = get_absences(self.guild_id)
        if absences:
            members_raw = [m for m in members_raw if m.get('name') not in absences]

        for raid in selected_raids:
            raid_name = raid.get('name', '')
            col       = raid.get('col')
            members   = []
            for m in members_raw:
                if m.get('absent'):
                    continue
                char_info = m['characters'].get(col)
                if not char_info:
                    continue
                members.append({
                    'name':       m['name'],
                    'character':  char_info['raw'],
                    'is_support': char_info['is_support'],
                })
            if not members:
                continue
            parties = build_party_groups(members, raid.get('party_size', 4))
            all_results[raid_name] = {'raid': raid, 'members': members, 'parties': parties}

        for raid_name, result in all_results.items():
            buf      = render_party_result(raid_name, result['parties'])
            img_file = discord.File(fp=buf, filename=f"party_{raid_name}.png")
            confirm_view = PartyConfirmView(
                thread=thread,
                raid_name=raid_name,
                parties=result['parties'],
                members=result['members'],
                guild_id=interaction.guild_id,
            )
            await thread.send(file=img_file, view=confirm_view)

        asyncio.create_task(delete_thread_after(thread, 604800))


# ==================== 개별 레이드 선택 ====================

class IndividualRaidSelectView(discord.ui.View):
    def __init__(self, raids: list, guild_id: int, data: list):
        super().__init__(timeout=180)
        self.raids        = raids
        self.guild_id     = guild_id
        self.data         = data
        self.selected_idx = None

        options = [
            discord.SelectOption(
                label=r.get('name', '')[:100],
                description=f"{r.get('day','')} {r.get('time_str','')} · {r.get('member_count',0)}명",
                value=str(i),
            )
            for i, r in enumerate(raids)
        ]
        select = discord.ui.Select(
            placeholder="⚔️ 레이드 선택",
            options=options[:25],
            min_values=1,
            max_values=1,
            custom_id="individual_raid_select",
            row=0
        )
        select.callback = self._on_select
        self.add_item(select)

    async def _on_select(self, interaction: discord.Interaction):
        select = discord.utils.get(self.children, custom_id="individual_raid_select")
        self.selected_idx = int(select.values[0])
        await interaction.response.defer()

    @discord.ui.button(label="🤖 AI 편성", style=discord.ButtonStyle.primary, custom_id="individual_ai", row=1)
    async def ai_compose(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.selected_idx is None:
            await interaction.response.send_message("❌ 레이드를 먼저 선택해주세요!", ephemeral=True)
            return
        raid       = self.raids[self.selected_idx]
        raid_name  = raid.get('name', '')
        col        = raid.get('col')

        members_raw = get_members(self.data)

        from bot.utils.member_link import get_absences
        absences = get_absences(interaction.guild_id)
        if absences:
            members_raw = [m for m in members_raw if m.get('name') not in absences]

        members = []
        for m in members_raw:
            if m.get('absent'):
                continue
            char_info = m['characters'].get(col)
            if not char_info:
                continue
            members.append({
                'name':       m['name'],
                'character':  char_info['raw'],
                'is_support': char_info['is_support'],
            })

        if not members:
            await interaction.response.send_message(
                f"❌ **{raid_name}** 참가 예정 길드원이 없습니다.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        parties  = build_party_groups(members, raid.get('party_size', 4))
        buf      = render_party_result(raid_name, parties)
        img_file = discord.File(fp=buf, filename=f"party_{raid_name}.png")

        party_ch = get_channel(interaction.guild, CH_PARTY)
        if not party_ch:
            await interaction.followup.send("❌ 레이드편성 채널이 없습니다.", ephemeral=True)
            return

        thread = await party_ch.create_thread(
            name=f"⚔️ {raid_name} 파티 편성",
            auto_archive_duration=10080,
            type=discord.ChannelType.public_thread
        )
        confirm_view = PartyConfirmView(
            thread=thread,
            raid_name=raid_name,
            parties=parties,
            members=members,
            guild_id=interaction.guild_id,
        )
        await thread.send(file=img_file, view=confirm_view)
        await interaction.followup.send(f"✅ {thread.mention} 에서 확인하세요!", ephemeral=True)
        asyncio.create_task(delete_thread_after(thread, 604800))


# ==================== 파티 확정 View ====================

class PartyConfirmView(discord.ui.View):
    def __init__(self, thread, raid_name, parties, members, guild_id):
        super().__init__(timeout=None)
        self.thread    = thread
        self.raid_name = raid_name
        self.parties   = parties
        self.members   = members
        self.guild_id  = guild_id

    @discord.ui.button(label="✅ 확정 + 시트 저장", style=discord.ButtonStyle.success, custom_id="party_confirm")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await require_admin(interaction): return
        await interaction.response.defer()
        url = get_sheet_url(self.guild_id)
        if url:
            try:
                save_party_result(url, self.raid_name, self.parties)
            except Exception as e:
                await interaction.followup.send(f"⚠️ 시트 저장 오류: {e}", ephemeral=True)
        for item in self.children:
            item.disabled = True
        await interaction.message.edit(view=self)
        await interaction.followup.send(
            f"✅ **{interaction.user.display_name}** 님이 **{self.raid_name}** 파티를 확정했습니다!\n🔒 스레드가 잠깁니다."
        )
        try:
            await self.thread.edit(locked=True, archived=False)
        except Exception:
            pass

    @discord.ui.button(label="🔄 재편성", style=discord.ButtonStyle.primary, custom_id="party_retry")
    async def retry(self, interaction: discord.Interaction, button: discord.ui.Button):
        dps          = [m for m in self.members if not m.get('is_support')]
        supps        = [m for m in self.members if m.get('is_support')]
        random.shuffle(dps)
        party_size   = max(len(self.parties[0]), 4) if self.parties else 4
        self.parties = build_party_groups(dps + supps, party_size)
        buf          = render_party_result(self.raid_name, self.parties)
        img_file     = discord.File(fp=buf, filename=f"party_{self.raid_name}.png")
        await interaction.response.defer()
        await interaction.message.delete()
        await interaction.channel.send(file=img_file, view=self)

    @discord.ui.button(label="🗑 삭제", style=discord.ButtonStyle.danger, custom_id="party_delete")
    async def delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await require_admin(interaction): return
        await interaction.response.send_message("🗑 삭제합니다...")
        try:
            await self.thread.delete()
        except Exception:
            pass


# ==================== PartyCog ====================

class PartyCog(commands.Cog, name="PartyCog"):

    def __init__(self, bot):
        self.bot = bot
        self.panel_messages: dict[int, int] = {}

    async def send_party_panel(self, channel: discord.TextChannel):
        embed = build_party_panel_embed()
        view  = PartyPanelView()
        msg   = await channel.send(embed=embed, view=view)
        try:
            await msg.pin()
        except Exception:
            pass
        self.panel_messages[channel.guild.id] = msg.id

    async def refresh_party_panel(self, guild: discord.Guild):
        party_ch = get_channel(guild, CH_PARTY)
        if not party_ch:
            return
        embed  = build_party_panel_embed()
        view   = PartyPanelView()
        msg_id = self.panel_messages.get(guild.id)
        if msg_id:
            try:
                msg = await party_ch.fetch_message(msg_id)
                await msg.edit(embed=embed, view=view)
                return
            except Exception:
                pass
        try:
            pins = await party_ch.pins()
            for pin in pins:
                if pin.author == guild.me:
                    await pin.edit(embed=embed, view=view)
                    self.panel_messages[guild.id] = pin.id
                    return
        except Exception:
            pass
        await self.send_party_panel(party_ch)

    @app_commands.command(name="파티패널", description="파티 편성 패널을 표시합니다 (관리자)")
    async def party_panel_cmd(self, interaction: discord.Interaction):
        if not await require_admin(interaction): return
        party_ch = get_channel(interaction.guild, CH_PARTY)
        if not party_ch:
            await interaction.response.send_message("❌ 레이드편성 채널이 없습니다.", ephemeral=True)
            return
        await self.send_party_panel(party_ch)
        await interaction.response.send_message(f"✅ {party_ch.mention} 에 패널을 표시했습니다!", ephemeral=True)

    @app_commands.command(name="시너지", description="파티 시너지를 분석합니다")
    async def synergy_check(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="⚡ 시너지 분석 — 클래스 선택",
            description="분석할 직업의 클래스를 선택하세요",
            color=0x9B59B6
        )
        await interaction.response.send_message(embed=embed, view=SynergyClassSelectView(), ephemeral=True)


async def setup(bot):
    cog = PartyCog(bot)
    await bot.add_cog(cog)
    bot.add_view(PartyPanelView())