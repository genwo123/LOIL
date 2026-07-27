"""
로일(LoIl) - 파티 Cog
"""

import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import json
import os
import re

from bot.utils.synergy_ui import SynergyClassSelectView
from bot.utils.member_link import get_absences
from bot.utils.permissions import require_admin, is_admin
from bot.utils.sheets import (
    get_all_data, get_members, parse_raids, parse_all_raids,
    save_party_result, save_all_party_results, get_raid_members_by_availability, get_all_availability,
    assign_raid_times, save_assigned_times
)
from bot.utils.image_renderer import render_party_result
from bot.config.settings import GEMINI_API_KEY, RAIDS_DATA
from bot.config.channels import CH_PARTY, CH_NOTICE, CH_SCHEDULE, CH_SUGGEST, CH_RAID_CONFIG, get_channel

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

def _get_week_label() -> str:
    from datetime import datetime, timezone, timedelta
    KST = timezone(timedelta(hours=9))
    now = datetime.now(KST)
    days_back = (now.weekday() - 2) % 7
    if now.weekday() == 2 and now.hour < 9:
        days_back = 7
    ref = now - timedelta(days=days_back)
    first_day = ref.replace(day=1)
    first_wed_offset = (2 - first_day.weekday()) % 7
    first_wed = first_day + timedelta(days=first_wed_offset)
    week_num = (ref - first_wed).days // 7 + 1
    return f"{ref.month}월 {week_num}주차"


_composition_counter: dict[str, int] = {}

def _get_next_count(guild_id: int) -> int:
    key = str(guild_id)
    _composition_counter[key] = _composition_counter.get(key, 0) + 1
    return _composition_counter[key]


async def delete_thread_after(thread: discord.Thread, seconds: int):
    await asyncio.sleep(seconds)
    try:
        await thread.delete()
    except Exception:
        pass


# ==================== 시트 데이터 로드 (폴백 포함) ====================

def _get_data(url: str, ai: bool = True) -> list:
    """AI편성 탭 우선, 없으면 주간레이드 탭으로 폴백"""
    if ai:
        data = get_all_data(url, ai=True)
        if data:
            return data
        print("[party] AI편성 탭 없음 → 주간레이드 탭으로 폴백")
    return get_all_data(url, ai=False) or []


# ==================== 파티 편성 로직 ====================

def _split_parties(members: list, party_size: int = 4) -> list[list]:
    supports = [m for m in members if m.get('is_support')]
    dps      = [m for m in members if not m.get('is_support')]
    total = len(members)
    if total <= party_size:
        return [dps + supports] if members else []
    num_parties = (total + party_size - 1) // party_size
    parties = [[] for _ in range(num_parties)]
    for i, s in enumerate(supports[:num_parties]):
        parties[i].append(s)
    extra_supps = supports[num_parties:]
    dps_pool = dps + extra_supps
    dps_idx = 0
    for party in parties:
        while len(party) < party_size and dps_idx < len(dps_pool):
            party.insert(0, dps_pool[dps_idx])
            dps_idx += 1
    while dps_idx < len(dps_pool):
        parties[-1].append(dps_pool[dps_idx])
        dps_idx += 1
    return [p for p in parties if p]


def _make_parties_simple(supports: list, dps_list: list, size: int = 4) -> list[list]:
    if not supports:
        return []
    sup_needed = 1 if size == 4 else 2
    if len(supports) < sup_needed:
        return []
    n_parties = len(supports) // sup_needed
    max_dps   = (size - 1) * n_parties
    dps       = dps_list[:max_dps]
    if len(supports + dps) <= size:
        return [dps + supports]
    p1_sup = supports[:1]; p2_sup = supports[1:2]
    extra  = supports[2:]
    all_dps = dps + extra
    half = len(all_dps) // 2
    p1 = all_dps[:half + len(all_dps)%2] + p1_sup
    p2 = all_dps[half + len(all_dps)%2:] + p2_sup
    return [p for p in [p1, p2] if p]


# ==================== 레이드 카테고리 묶기 ====================

def _get_raid_base_name(name: str) -> str:
    return re.sub(r'\d+$', '', name).strip()

def _group_raids_by_category(raids: list) -> dict[str, list]:
    groups = {}
    for raid in raids:
        base = _get_raid_base_name(raid['name'])
        groups.setdefault(base, []).append(raid)
    return groups


# ==================== 레이드 정렬 ====================

KAZEROS_ORDER    = ['종막', '4막', '3막', '2막', '1막', '서막']
LEGION_ORDER     = ['카멘', '일리아칸', '아브렐슈드', '쿠크세이튼', '비아키스', '발탄']
DIFFICULTY_ORDER = {'나이트메어':0,'나메':0,'하드':1,'노말':2,'normal':2,'hard':1}

def _raid_sort_key(raid: dict) -> tuple:
    name = raid.get('name', '')
    kaz  = next((i for i, n in enumerate(KAZEROS_ORDER) if n in name), 99)
    leg  = next((i for i, n in enumerate(LEGION_ORDER)  if n in name), 99)
    diff = next((v for k, v in DIFFICULTY_ORDER.items() if k in name.lower()), 99)
    day_order = {'수':0,'목':1,'금':2,'토':3,'일':4,'월':5,'화':6,'미정':7}
    return (day_order.get(raid.get('day','미정'), 7), min(kaz, leg), diff, raid.get('hour', 0), raid.get('minute', 0))

def get_sorted_raids(raids: list) -> list:
    return sorted(raids, key=_raid_sort_key)


# ==================== 고정 패널 임베드 ====================

def build_party_panel_embed() -> discord.Embed:
    embed = discord.Embed(
        title="🛡 레이드 편성 센터",
        description=(
            "구글 시트의 이번 주 참가자를 불러와\n"
            "**AI가 최적의 파티를 자동 구성**합니다.\n\n"
            "가능 시간 자동 감지 · 서폿 자동 배치 · 시너지 고려"
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
        name="일정 관리 (관리자)",
        value=(
            "일정 추가 / 수정 / 삭제\n"
            "클리어 처리 / 예정 토글\n"
            "레이드 카탈로그 → ⚔️│레이드설정"
        ),
        inline=True
    )
    embed.set_footer(text="결과는 이미지로 스레드에 표시됩니다 · 확정 후 시트 자동 저장")
    return embed


# ==================== 파티 고정 패널 View ====================

class PartyPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="주간 전체 편성", style=discord.ButtonStyle.primary, custom_id="party_weekly", row=0)
    async def weekly_party(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        url = get_sheet_url(interaction.guild_id)
        if not url:
            await interaction.followup.send("❌ 시트가 연동되지 않았습니다.", ephemeral=True)
            return
        data  = _get_data(url, ai=True)
        raids = get_sorted_raids(parse_raids(data))
        if not raids:
            await interaction.followup.send("❌ 이번 주 예정된 레이드가 없습니다.", ephemeral=True)
            return
        view  = RaidChecklistView(raids=raids, guild_id=interaction.guild_id, data=data, url=url)
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
        data  = _get_data(url, ai=True)
        raids = get_sorted_raids(parse_raids(data))
        if not raids:
            await interaction.followup.send("❌ 이번 주 예정된 레이드가 없습니다.", ephemeral=True)
            return
        view  = IndividualRaidSelectView(raids=raids, guild_id=interaction.guild_id, data=data, url=url)
        embed = discord.Embed(title="개별 레이드 편성", description="편성할 레이드를 선택하세요", color=0x5865F2)
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)

    @discord.ui.button(label="시너지 분석", style=discord.ButtonStyle.secondary, custom_id="party_synergy", row=0)
    async def synergy(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(title="시너지 분석 — 클래스 선택", description="분석할 직업의 클래스를 선택하세요", color=0x9B59B6)
        await interaction.response.send_message(embed=embed, view=SynergyClassSelectView(), ephemeral=True)

    @discord.ui.button(label="일정 추가", style=discord.ButtonStyle.success, custom_id="party_raid_add", row=1)
    async def raid_add(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await require_admin(interaction): return
        from bot.cogs.raid_manage import RaidSelectForAddView
        from bot.cogs.raid_config import get_active_raids
        url = get_sheet_url(interaction.guild_id)
        if not url:
            await interaction.response.send_message("❌ 시트가 연동되지 않았습니다.", ephemeral=True)
            return
        active_raids = get_active_raids(interaction.guild_id)
        if not active_raids:
            await interaction.response.send_message(
                "❌ 활성화된 레이드가 없습니다.\n⚔️│레이드설정 채널에서 먼저 운영할 레이드를 켜주세요.",
                ephemeral=True
            )
            return
        view = RaidSelectForAddView(raids=active_raids, url=url, guild=interaction.guild)
        await interaction.response.send_message("추가할 레이드를 선택하세요:", view=view, ephemeral=True)

    @discord.ui.button(label="🧹 채널 청소", style=discord.ButtonStyle.danger, custom_id="party_purge", row=1)
    async def purge_channel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await require_admin(interaction): return
        await interaction.response.defer(ephemeral=True)
        channel = interaction.channel
        try:
            # 핀 제외 메시지 삭제
            pinned = await channel.pins()
            pinned_ids = {m.id for m in pinned}
            deleted = 0
            async for msg in channel.history(limit=200):
                if msg.id not in pinned_ids:
                    try:
                        await msg.delete()
                        deleted += 1
                    except Exception:
                        pass

            # 패널 맨 아래 재전송
            party_cog = interaction.client.cogs.get("PartyCog")
            if party_cog:
                await party_cog.send_party_panel(channel)

            await interaction.followup.send(
                f"🧹 **{deleted}개** 메시지 삭제 후 패널을 새로 표시했습니다.",
                ephemeral=True
            )
        except Exception as e:
            await interaction.followup.send(f"❌ 청소 실패: {e}", ephemeral=True)

    @discord.ui.button(label="일정 수정", style=discord.ButtonStyle.secondary, custom_id="party_raid_edit", row=1)
    async def raid_edit(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await require_admin(interaction): return
        from bot.cogs.raid_manage import RaidActionView
        url = get_sheet_url(interaction.guild_id)
        if not url:
            await interaction.response.send_message("❌ 시트가 연동되지 않았습니다.", ephemeral=True)
            return
        data  = _get_data(url, ai=True)
        raids = parse_all_raids(data)
        if not raids:
            await interaction.response.send_message("❌ 등록된 일정이 없습니다.", ephemeral=True)
            return
        await interaction.response.send_message("수정할 일정을 선택하세요:", view=RaidActionView(raids=raids, action="edit", url=url), ephemeral=True)

    @discord.ui.button(label="일정 삭제", style=discord.ButtonStyle.danger, custom_id="party_raid_delete", row=1)
    async def raid_delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await require_admin(interaction): return
        from bot.cogs.raid_manage import RaidActionView
        url = get_sheet_url(interaction.guild_id)
        if not url:
            await interaction.response.send_message("❌ 시트가 연동되지 않았습니다.", ephemeral=True)
            return
        data  = _get_data(url, ai=True)
        raids = parse_all_raids(data)
        if not raids:
            await interaction.response.send_message("❌ 등록된 일정이 없습니다.", ephemeral=True)
            return
        await interaction.response.send_message("삭제할 일정을 선택하세요:", view=RaidActionView(raids=raids, action="delete", url=url), ephemeral=True)

    @discord.ui.button(label="공지 →", style=discord.ButtonStyle.secondary, custom_id="party_to_notice", row=2)
    async def to_notice(self, interaction: discord.Interaction, button: discord.ui.Button):
        ch = get_channel(interaction.guild, CH_NOTICE)
        await interaction.response.send_message(f"{ch.mention} 으로 이동하세요!" if ch else "채널을 찾을 수 없습니다.", ephemeral=True)

    @discord.ui.button(label="일정 조회 →", style=discord.ButtonStyle.secondary, custom_id="party_to_schedule", row=2)
    async def to_schedule(self, interaction: discord.Interaction, button: discord.ui.Button):
        ch = get_channel(interaction.guild, CH_SCHEDULE)
        await interaction.response.send_message(f"{ch.mention} 으로 이동하세요!" if ch else "채널을 찾을 수 없습니다.", ephemeral=True)

    @discord.ui.button(label="레이드 설정 →", style=discord.ButtonStyle.secondary, custom_id="party_to_raid_config", row=2)
    async def to_raid_config(self, interaction: discord.Interaction, button: discord.ui.Button):
        ch = get_channel(interaction.guild, CH_RAID_CONFIG)
        await interaction.response.send_message(f"{ch.mention} 으로 이동하세요!" if ch else "채널을 찾을 수 없습니다.", ephemeral=True)

    @discord.ui.button(label="건의함 →", style=discord.ButtonStyle.secondary, custom_id="party_to_suggest", row=2)
    async def to_suggest(self, interaction: discord.Interaction, button: discord.ui.Button):
        ch = get_channel(interaction.guild, CH_SUGGEST)
        await interaction.response.send_message(f"{ch.mention} 으로 이동하세요!" if ch else "채널을 찾을 수 없습니다.", ephemeral=True)

    @discord.ui.button(label="새로고침", style=discord.ButtonStyle.secondary, custom_id="party_refresh", row=2)
    async def refresh(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        party_cog = interaction.client.cogs.get("PartyCog")
        if party_cog:
            await party_cog.refresh_party_panel(interaction.guild)
        await interaction.followup.send("패널이 갱신되었습니다!", ephemeral=True)


# ==================== 주간 체크리스트 ====================

class RaidChecklistView(discord.ui.View):
    def __init__(self, raids: list, guild_id: int, data: list, url: str):
        super().__init__(timeout=180)
        self.raids    = raids
        self.guild_id = guild_id
        self.data     = data
        self.url      = url
        self.selected: set[int] = set(range(len(raids)))
        self._build_select()

    def _build_select(self):
        for item in self.children.copy():
            if isinstance(item, discord.ui.Select):
                self.remove_item(item)
        options = [
            discord.SelectOption(
                label=r.get('name', '')[:100],
                description=f"{r.get('day','')} {r.get('time_str','')}",
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

        await interaction.response.defer(ephemeral=True)

        party_ch = get_channel(interaction.guild, CH_PARTY)
        if not party_ch:
            await interaction.followup.send("❌ 레이드편성 채널이 없습니다.", ephemeral=True)
            return

        thread = await party_ch.create_thread(
            name=f"📅 {_get_week_label()} AI편성 {_get_next_count(interaction.guild_id)}회차",
            auto_archive_duration=10080,
            type=discord.ChannelType.public_thread
        )
        await thread.send("🤖 AI 파티 편성 중... 시간 배정 포함 잠시 기다려주세요!")
        await interaction.followup.send(f"✅ {thread.mention} 에서 확인하세요!", ephemeral=True)

        absences    = get_absences(self.guild_id)
        ai_data     = _get_data(self.url, ai=True)
        assignments = assign_raid_times(self.url, ai_data, interaction.guild_id)

        selected_cols = {self.raids[i]['col'] for i in self.selected}
        assignments   = [a for a in assignments if a['raid']['col'] in selected_cols]

        if absences:
            for a in assignments:
                a['members'] = [m for m in a['members'] if m['name'] not in absences]
                supports = [m for m in a['members'] if m.get('is_support')]
                dps_list = [m for m in a['members'] if not m.get('is_support')]
                a['parties'] = _make_parties_simple(supports, dps_list)

        if not assignments:
            await thread.send("❌ 편성 가능한 레이드가 없습니다.")
            return

        groups = {}
        for a in assignments:
            base = _get_raid_base_name(a['raid']['name'])
            groups.setdefault(base, []).append(a)

        DAY_ORDER = {'수':0,'목':1,'금':2,'토':3,'일':4,'월':5,'화':6,'미정':7}

        valid_groups = []
        for base_name, group in groups.items():
            group.sort(key=lambda a: (
                DAY_ORDER.get(a['assigned_day'], 7),
                a['assigned_hour'],
                a['assigned_minute']
            ))
            gr = [a for a in group if a['members'] and a['parties']]
            if gr:
                valid_groups.append((base_name, group, gr))

        total_groups      = len(valid_groups)
        confirmed_counter = [0]
        weekly_sent       = [False]

        async def _send_weekly():
            if weekly_sent[0]:
                return
            weekly_sent[0] = True
            try:
                await thread.send("🎉 모든 편성이 완료됐어요! 주간 일정표를 드릴게요 잠시만요...")
                from bot.utils.image_renderer import render_weekly_raids, render_weekly_timeline
                from bot.utils.sheets import parse_raids
                weekly_data  = _get_data(self.url, ai=True)
                weekly_raids = parse_raids(weekly_data)
                col_to_assign = {a['raid']['col']: a for a in assignments}
                for r in weekly_raids:
                    a = col_to_assign.get(r['col'])
                    if a:
                        r['members']  = a.get('members', [])
                        r['day']      = a.get('assigned_day', '미정')
                        r['time_str'] = a.get('time_str', '미정')
                        r['hour']     = a.get('assigned_hour', 0)
                        r['minute']   = a.get('assigned_minute', 0)
                _day_ord = {'수':0,'목':1,'금':2,'토':3,'일':4,'월':5,'화':6,'미정':7}
                weekly_raids = [r for r in weekly_raids if r.get('members')]
                weekly_raids.sort(key=lambda r: (
                    _day_ord.get(r.get('day','미정'), 7),
                    r.get('hour', 0),
                    r.get('minute', 0)
                ))
                buf_card     = render_weekly_raids(weekly_raids)
                buf_timeline = render_weekly_timeline(weekly_raids)
                week_label   = _get_week_label()
                await thread.send(
                    content=f"📋 **{week_label} 전체 일정**",
                    files=[discord.File(fp=buf_card,     filename="weekly_card.png"),
                           discord.File(fp=buf_timeline, filename="weekly_timeline.png")]
                )
                await thread.send("📌 주간 일정표는 **일정조회** 탭에서도 확인 가능합니다.")
            except Exception as e:
                print(f"[party] 전체 일정 출력 오류: {e}")

        for base_name, group, group_results in valid_groups:
            undecided_in_group = [a['raid']['name'] for a in group if a['members'] and not a['parties']]
            if undecided_in_group:
                await thread.send("⚠️ 미정 (인원 부족): " + ", ".join(undecided_in_group))

            files = []
            conflict_msgs = []
            for result in group_results:
                buf = render_party_result(
                    result['raid']['name'], result['parties'],
                    time_str=result['time_str'], day=result['assigned_day']
                )
                files.append(discord.File(fp=buf, filename=f"party_{result['raid']['name']}.png"))
                for c in result.get('conflicts', []):
                    conflict_msgs.append(
                        f"⚠️ **{c['name']}** — {result['raid']['name']} · {c['other_raid']} 동시간 중복"
                    )

            formatted_results = [{
                'raid':      a['raid'],
                'name':      a['raid']['name'],
                'members':   a['members'],
                'parties':   a['parties'],
                'time_str':  a['time_str'],
                'day':       a['assigned_day'],
                'conflicts': a.get('conflicts', []),
            } for a in group_results]

            group_view = PartyGroupConfirmView(
                thread=thread,
                group_results=formatted_results,
                guild_id=interaction.guild_id,
                url=self.url,
                data=self.data,
                all_avail={},
                total_groups=total_groups,
                confirmed_counter=confirmed_counter,
                weekly_callback=_send_weekly,
            )
            await thread.send(files=files, view=group_view)
            if conflict_msgs:
                await thread.send("\n".join(conflict_msgs))

        undecided = [a['raid']['name'] for a in assignments if a['assigned_day'] == '미정']
        if undecided:
            await thread.send(f"⚠️ 시간 배정 불가 (미정): {', '.join(undecided)}")

        asyncio.create_task(delete_thread_after(thread, 604800))


# ==================== 개별 레이드 선택 ====================

class IndividualRaidSelectView(discord.ui.View):
    def __init__(self, raids: list, guild_id: int, data: list, url: str):
        super().__init__(timeout=180)
        self.raids        = raids
        self.guild_id     = guild_id
        self.data         = data
        self.url          = url
        self.selected_idx = None

        options = [
            discord.SelectOption(
                label=r.get('name', '')[:100],
                description=f"{r.get('day','')} {r.get('time_str','')}",
                value=str(i),
            )
            for i, r in enumerate(raids)
        ]
        select = discord.ui.Select(
            placeholder="⚔️ 레이드 선택",
            options=options[:25],
            min_values=1, max_values=1,
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

        raid      = self.raids[self.selected_idx]
        raid_name = raid.get('name', '')

        await interaction.response.defer(ephemeral=True)

        all_avail = get_all_availability(self.url)
        members   = get_raid_members_by_availability(self.url, self.data, raid, all_availability=all_avail)

        from bot.utils.member_link import get_absences
        absences = get_absences(interaction.guild_id)
        if absences:
            members = [m for m in members if m['name'] not in absences]

        if not members:
            await interaction.followup.send(f"❌ **{raid_name}** 참가 가능한 길드원이 없습니다.", ephemeral=True)
            return

        parties  = _split_parties(members, raid.get('party_size', 4))
        buf      = render_party_result(
            raid_name, parties,
            time_str=raid.get('time_str',''), day=raid.get('day','')
        )
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
        view = PartyGroupConfirmView(
            thread=thread,
            group_results=[{
                'raid': raid, 'name': raid_name,
                'parties': parties, 'members': members,
                'time_str': raid.get('time_str',''), 'day': raid.get('day',''),
            }],
            guild_id=interaction.guild_id,
            url=self.url,
            data=self.data,
            all_avail=all_avail,
        )
        await thread.send(file=img_file, view=view)
        await interaction.followup.send(f"✅ {thread.mention} 에서 확인하세요!", ephemeral=True)
        asyncio.create_task(delete_thread_after(thread, 604800))


# ==================== 파티 그룹 확정 View ====================

class PartyGroupConfirmView(discord.ui.View):
    def __init__(self, thread, group_results, guild_id, url, data, all_avail,
                 total_groups=1, confirmed_counter=None, weekly_callback=None):
        super().__init__(timeout=None)
        self.thread            = thread
        self.group_results     = group_results
        self.guild_id          = guild_id
        self.url               = url
        self.data              = data
        self.all_avail         = all_avail
        self.total_groups      = total_groups
        self.confirmed_counter = confirmed_counter
        self.weekly_callback   = weekly_callback

    @discord.ui.button(label="✅ 저장하기", style=discord.ButtonStyle.success, custom_id="pgroup_confirm")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await require_admin(interaction): return

        # 버튼 즉시 비활성화 — 중복 클릭 및 404 타임아웃 방지
        button.disabled = True
        button.label    = "저장 중..."
        await interaction.response.edit_message(view=self)

        confirmed_by = interaction.user.display_name

        async def _save():
            failed = []
            try:
                raid_parties = [(r['name'], r['parties']) for r in self.group_results]
                save_all_party_results(self.url, raid_parties)
            except Exception as e:
                print(f"[party] save_all_party_results 오류: {e}")
                failed = [r['name'] for r in self.group_results]

            def _parse_time_str(time_str):
                try:
                    h, m = time_str.split(':')
                    return int(h), int(m)
                except Exception:
                    return 0, 0

            time_assignments = []
            for r in self.group_results:
                if not r.get('day') or r['day'] == '미정':
                    continue
                hour, minute = _parse_time_str(r.get('time_str', '0:00'))
                time_assignments.append({
                    'raid':            r['raid'],
                    'assigned_day':    r['day'],
                    'assigned_hour':   hour,
                    'assigned_minute': minute,
                })
            if time_assignments:
                try:
                    save_assigned_times(self.url, time_assignments)
                except Exception as e:
                    print(f"[party] save_assigned_times 오류: {e}")

            if self.confirmed_counter is not None:
                self.confirmed_counter[0] += 1
                current = self.confirmed_counter[0]
                total   = self.total_groups
            else:
                current = total = 1

            summary  = " · ".join(
                f"{r['name']} {r['day']}{'요일 ' if r['day'] != '미정' else ' '}{r['time_str']}"
                for r in self.group_results
            )
            fail_txt = " | ⚠️ 저장 실패: " + ", ".join(failed) if failed else ""
            try:
                await interaction.message.edit(
                    content=f"✅ [{current}/{total}] {summary} — **{confirmed_by}** 확정{fail_txt}",
                    attachments=[],
                    view=None
                )
            except Exception:
                pass

            if current >= total and self.weekly_callback:
                await self.weekly_callback()

            try:
                await self.thread.edit(locked=True, archived=False)
            except Exception:
                pass

        asyncio.create_task(_save())

    @discord.ui.button(label="⏸ 미정 처리", style=discord.ButtonStyle.secondary, custom_id="pgroup_exclude")
    async def exclude(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await require_admin(interaction): return
        names = ", ".join(r['name'] for r in self.group_results)
        if self.confirmed_counter is not None:
            self.confirmed_counter[0] += 1
            current = self.confirmed_counter[0]
            total   = self.total_groups
        else:
            current = total = 1
        try:
            await interaction.response.edit_message(
                content=f"⏸ [{current}/{total}] {names} — 미정 처리",
                attachments=[],
                view=None
            )
        except Exception:
            await interaction.response.send_message(f"⏸ **{names}** 미정 처리", ephemeral=True)
        if current >= total and self.weekly_callback:
            await self.weekly_callback()

    @discord.ui.button(label="🔄 재편성", style=discord.ButtonStyle.primary, custom_id="pgroup_recompose")
    async def recompose(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await require_admin(interaction): return
        await interaction.response.defer()
        try:
            data      = _get_data(self.url, ai=True)
            all_avail = get_all_availability(self.url)
            new_assignments = assign_raid_times(self.url, data, self.guild_id)
            target_names = {r['name'] for r in self.group_results}
            new_group = [a for a in new_assignments if a['raid']['name'] in target_names and a['parties']]
            if not new_group:
                await interaction.followup.send("⚠️ 재편성 결과가 없습니다.", ephemeral=True)
                return
            new_results = [{
                'raid':      a['raid'],
                'name':      a['raid']['name'],
                'members':   a['members'],
                'parties':   a['parties'],
                'time_str':  a['time_str'],
                'day':       a['assigned_day'],
                'conflicts': a.get('conflicts', []),
            } for a in new_group]
            self.group_results = new_results
            files = []
            for r in new_results:
                buf = render_party_result(r['name'], r['parties'], time_str=r['time_str'], day=r['day'])
                files.append(discord.File(fp=buf, filename=f"party_{r['name']}.png"))
            await interaction.message.delete()
            await self.thread.send(files=files, view=self)
        except Exception as e:
            await interaction.followup.send(f"❌ 재편성 오류: {e}", ephemeral=True)


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
        embed = discord.Embed(title="⚡ 시너지 분석 — 클래스 선택", description="분석할 직업의 클래스를 선택하세요", color=0x9B59B6)
        await interaction.response.send_message(embed=embed, view=SynergyClassSelectView(), ephemeral=True)


async def setup(bot):
    cog = PartyCog(bot)
    await bot.add_cog(cog)
    bot.add_view(PartyPanelView())