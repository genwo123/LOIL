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
from bot.utils.member_link import get_absences, get_all_availability_slots
from bot.utils.permissions import require_admin, is_admin
from bot.utils.channel_cleanup import purge_channel as _purge_channel
from bot.utils.raid_schedule import (
    get_scheduled_raids, get_raid_candidates, assign_raid_times, save_assigned_times,
)
from bot.utils.raid_signup import get_raid_party
from bot.utils.gemini_ai import recommend_party as ai_recommend_party
from bot.utils.lostark_api import get_character_item_level
from bot.utils.web_results import save_result_snapshot, remove_raid_from_snapshot, build_web_url, get_guild_name
from bot.config.settings import RAIDS_DATA
from bot.config.channels import CH_PARTY, get_channel

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


# ==================== AI(Gemini) 편성 코멘트 ====================

async def _send_ai_commentary(thread, raid_name: str, members: list, guild_id: int):
    """편성 결과에 대한 Gemini 코멘트를 추가로 보내준다.
    파티 배정 자체는 이미 끝난 뒤라 실패해도 편성 결과에는 영향 없음 — 조용히 스킵."""
    try:
        comment = await asyncio.to_thread(ai_recommend_party, members, raid_name, guild_id)
    except Exception as e:
        print(f"[party] AI 코멘트 생성 실패 ({raid_name}): {e}")
        return
    if not comment or comment.startswith("❌"):
        return
    embed = discord.Embed(
        title=f"🤖 AI 시너지 추천 — {raid_name}",
        description=comment[:4000],
        color=0x9B59B6,
    )
    try:
        await thread.send(embed=embed)
    except Exception:
        pass


async def _send_avg_level(thread, raid_name: str, members: list, guild_id: int):
    """편성된 파티원들의 로스트아크 평균 아이템 레벨을 알려준다.
    시트 닉네임이 실제 캐릭터명과 다른 길드원이 있을 수 있어 조회 실패는 조용히 건너뜀."""
    levels = []
    for m in members:
        try:
            level = await asyncio.to_thread(get_character_item_level, m.get('name', ''), guild_id)
        except Exception as e:
            print(f"[party] 전투력 조회 실패 ({m.get('name')}): {e}")
            level = None
        if level is not None:
            levels.append(level)
    if not levels:
        return
    avg = sum(levels) / len(levels)
    try:
        await thread.send(f"⚔️ **{raid_name}** 평균 전투력: **{avg:,.2f}** ({len(levels)}/{len(members)}명 조회)")
    except Exception:
        pass


async def _save_party_results(guild_id: int, results: list) -> list:
    """편성 결과 저장 공통 로직 — 확정된 시간을 레이드 인스턴스에 반영. 실패한 레이드 이름 리스트를 반환.
    파티 구성 자체(누가 몇 번 파티인지)는 디스코드 스레드 + 웹 편성 결과 링크로만 보여주고
    별도 로그로 저장하지 않는다(예전엔 시트에 로그를 남겼지만 아무도 다시 읽지 않아서 폐기)."""
    def _parse_time_str(time_str):
        try:
            h, m = time_str.split(':')
            return int(h), int(m)
        except Exception:
            return 0, 0

    time_assignments = []
    for r in results:
        if not r.get('day') or r['day'] == '미정':
            continue
        hour, minute = _parse_time_str(r.get('time_str', '0:00'))
        time_assignments.append({
            'raid':            r['raid'],
            'assigned_day':    r['day'],
            'assigned_hour':   hour,
            'assigned_minute': minute,
        })

    failed = []
    if time_assignments:
        try:
            save_assigned_times(guild_id, time_assignments)
        except Exception as e:
            print(f"[party] save_assigned_times 오류: {e}")
            failed = [r['name'] for r in results]

    return failed


# ==================== 레이드 카테고리 묶기 ====================
# 예전엔 레이드명에 "카멘(하)2"처럼 공대 번호가 붙어있어서 정규식으로 잘라냈는데,
# 이제 raid_schedule.py가 이름/난이도/공대를 처음부터 분리해서 주므로 그냥 name을 쓰면 된다.

def _get_raid_base_name(name: str) -> str:
    return name.strip()

def _group_raids_by_category(raids: list) -> dict[str, list]:
    groups = {}
    for raid in raids:
        base = raid['name']
        groups.setdefault(base, []).append(raid)
    return groups


# ==================== 레이드 정렬 ====================

KAZEROS_ORDER    = ['종막', '4막', '3막', '2막', '1막', '서막']
LEGION_ORDER     = ['카멘', '일리아칸', '아브렐슈드', '쿠크세이튼', '비아키스', '발탄']
DIFFICULTY_ORDER = {'더퍼스트': 0, '나이트메어': 1, '나메': 1, '하드': 2, '노말': 3}

def _raid_sort_key(raid: dict) -> tuple:
    name = raid.get('name', '')
    kaz  = next((i for i, n in enumerate(KAZEROS_ORDER) if n in name), 99)
    leg  = next((i for i, n in enumerate(LEGION_ORDER)  if n in name), 99)
    diff = DIFFICULTY_ORDER.get(raid.get('diff', ''), 99)
    day_order = {'수':0,'목':1,'금':2,'토':3,'일':4,'월':5,'화':6,'미정':7}
    return (day_order.get(raid.get('day','미정'), 7), min(kaz, leg), diff, raid.get('hour', 0), raid.get('minute', 0))

def get_sorted_raids(raids: list) -> list:
    return sorted(raids, key=_raid_sort_key)


# ==================== 고정 패널 임베드 ====================

def build_party_panel_embed() -> discord.Embed:
    embed = discord.Embed(
        title="🛡 레이드 편성 센터",
        description=(
            "이번 주 배정된 인원을 불러와\n"
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
    embed.set_footer(text="결과는 이미지로 스레드에 표시됩니다 · 확정 후 자동 저장")
    return embed


# ==================== 파티 고정 패널 View ====================

class PartyPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="📅 주간 전체 편성", style=discord.ButtonStyle.primary, custom_id="party_weekly", row=0)
    async def weekly_party(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        raids = get_sorted_raids(get_scheduled_raids(interaction.guild_id))
        if not raids:
            await interaction.followup.send("❌ 이번 주 예정된 레이드가 없습니다.", ephemeral=True)
            return
        view  = RaidChecklistView(raids=raids, guild_id=interaction.guild_id)
        embed = discord.Embed(
            title="📅 주간 전체 편성",
            description=f"편성할 레이드를 선택하세요 · 총 **{len(raids)}개**",
            color=0x5865F2
        )
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)

    @discord.ui.button(label="🛡 개별 레이드 편성", style=discord.ButtonStyle.secondary, custom_id="party_individual", row=0)
    async def individual_party(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        raids = get_sorted_raids(get_scheduled_raids(interaction.guild_id))
        if not raids:
            await interaction.followup.send("❌ 이번 주 예정된 레이드가 없습니다.", ephemeral=True)
            return
        view  = IndividualRaidSelectView(raids=raids, guild_id=interaction.guild_id)
        embed = discord.Embed(title="🛡 개별 레이드 편성", description="편성할 레이드를 선택하세요", color=0x5865F2)
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)

    @discord.ui.button(label="⚡ 시너지 분석", style=discord.ButtonStyle.secondary, custom_id="party_synergy", row=0)
    async def synergy(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(title="⚡ 시너지 분석 — 클래스 선택", description="분석할 직업의 클래스를 선택하세요", color=0x9B59B6)
        await interaction.response.send_message(embed=embed, view=SynergyClassSelectView(), ephemeral=True)

    @discord.ui.button(label="🧹 채널 청소", style=discord.ButtonStyle.danger, custom_id="party_purge", row=1)
    async def purge_channel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await require_admin(interaction): return
        await interaction.response.defer(ephemeral=True)
        channel = interaction.channel
        try:
            deleted = await _purge_channel(channel)

            party_cog = interaction.client.cogs.get("PartyCog")
            if party_cog:
                await party_cog.send_party_panel(channel)

            await interaction.followup.send(
                f"🧹 **{deleted}개** 메시지 삭제 후 패널을 새로 표시했습니다.",
                ephemeral=True
            )
        except Exception as e:
            print(f"[party] 청소 실패: {e}")
            await interaction.followup.send("❌ 채널 청소에 실패했습니다. 잠시 후 다시 시도해주세요.", ephemeral=True)



# ==================== 주간 체크리스트 ====================

class RaidChecklistView(discord.ui.View):
    def __init__(self, raids: list, guild_id: int):
        super().__init__(timeout=180)
        self.raids    = raids
        self.guild_id = guild_id
        self.selected: set[int] = set(range(len(raids)))
        self._build_select()

    def _build_select(self):
        for item in self.children.copy():
            if isinstance(item, discord.ui.Select):
                self.remove_item(item)
        options = [
            discord.SelectOption(
                label=f"{r.get('name', '')} {r.get('diff', '')}"[:100],
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

    @discord.ui.button(label="🤖 자동 편성", style=discord.ButtonStyle.primary, custom_id="weekly_ai_compose", row=1)
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
        await thread.send("🤖 자동 편성 중... 시간 배정 포함 잠시 기다려주세요!")
        await interaction.followup.send(f"✅ {thread.mention} 에서 확인하세요!", ephemeral=True)

        absences    = get_absences(self.guild_id)
        assignments = assign_raid_times(interaction.guild_id)

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
            base = a['raid']['full_name']
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

        weekly_sent = [False]

        async def _send_weekly():
            if weekly_sent[0]:
                return
            weekly_sent[0] = True
            try:
                await thread.send("🎉 편성이 저장됐어요! 주간 일정표를 드릴게요 잠시만요...")
                from bot.utils.image_renderer import render_weekly_raids, render_weekly_timeline
                weekly_raids = get_scheduled_raids(interaction.guild_id)
                col_to_assign = {a['raid']['col']: a for a in assignments}
                for r in weekly_raids:
                    r['name'] = r['full_name']
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

        # ---- 그룹별로 흩어져 있던 결과를 하나로 모은다 (웹 조회용, 이미지는 더 이상 안 만듦) ----
        pending_results: dict[str, dict] = {}
        conflict_msgs: list[str]         = []

        for base_name, group, group_results in valid_groups:
            undecided_in_group = [a['raid']['full_name'] for a in group if a['members'] and not a['parties']]
            if undecided_in_group:
                await thread.send("⚠️ 미정 (인원 부족): " + ", ".join(undecided_in_group))

            # 한 레이드+난이도에 공대가 여러 개(예: 세르카 노말 1, 2, 3)일 수 있어서 표시 이름에 번호를 붙여 구분.
            squad_no = 1
            for result in group_results:
                display_name = base_name if len(group_results) == 1 else f"{base_name} {squad_no}"
                squad_no += 1
                result['display_name'] = display_name

                for c in result.get('conflicts', []):
                    conflict_msgs.append(
                        f"⚠️ **{c['name']}** — {display_name} · {c['other_raid']} 동시간 중복"
                    )
                pending_results[display_name] = {
                    'raid':      result['raid'],
                    'name':      display_name,
                    'members':   result['members'],
                    'parties':   result['parties'],
                    'time_str':  result['time_str'],
                    'day':       result['assigned_day'],
                    'conflicts': result.get('conflicts', []),
                }
                asyncio.create_task(
                    _send_ai_commentary(thread, display_name, result['members'], interaction.guild_id)
                )
                asyncio.create_task(
                    _send_avg_level(thread, display_name, result['members'], interaction.guild_id)
                )

        if pending_results:
            web_raids = {
                name: {
                    'day':       r['day'],
                    'time_str':  r['time_str'],
                    'parties':   r['parties'],
                    'conflicts': r.get('conflicts', []),
                }
                for name, r in pending_results.items()
            }
            guild_name = get_guild_name(interaction.guild_id, interaction.guild.name if interaction.guild else '')
            slug = save_result_snapshot(interaction.guild_id, _get_week_label(), web_raids, guild_name)
            await thread.send(f"🔗 편성 결과 보기: {build_web_url(slug)}")

        if conflict_msgs:
            await thread.send("\n".join(conflict_msgs))

        undecided = [a['raid']['full_name'] for a in assignments if a['assigned_day'] == '미정']
        if undecided:
            await thread.send(f"⚠️ 시간 배정 불가 (미정): {', '.join(undecided)}")

        if pending_results:
            control_view = UnifiedConfirmView(
                thread=thread,
                results=pending_results,
                guild_id=interaction.guild_id,
                weekly_callback=_send_weekly,
            )
            control_view.control_message = await thread.send(
                content=f"📦 총 **{len(pending_results)}개** 레이드 편성 완료 — 검토 후 저장해주세요.",
                view=control_view
            )

        asyncio.create_task(delete_thread_after(thread, 604800))


# ==================== 개별 레이드 선택 ====================

class IndividualRaidSelectView(discord.ui.View):
    def __init__(self, raids: list, guild_id: int):
        super().__init__(timeout=180)
        self.raids        = raids
        self.guild_id     = guild_id
        self.selected_idx = None

        options = [
            discord.SelectOption(
                label=f"{r.get('name', '')} {r.get('diff', '')}"[:100],
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

    @discord.ui.button(label="🤖 자동 편성", style=discord.ButtonStyle.primary, custom_id="individual_ai", row=1)
    async def ai_compose(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.selected_idx is None:
            await interaction.response.send_message("❌ 레이드를 먼저 선택해주세요!", ephemeral=True)
            return

        raid      = self.raids[self.selected_idx]
        raid_name = raid.get('full_name', raid.get('name', ''))

        await interaction.response.defer(ephemeral=True)

        all_avail = get_all_availability_slots(interaction.guild_id)
        members   = get_raid_candidates(interaction.guild_id, raid, all_availability=all_avail)
        absences = get_absences(interaction.guild_id)
        if absences:
            members = [m for m in members if m['name'] not in absences]

        if not members:
            await interaction.followup.send(f"❌ **{raid_name}** 참가 가능한 길드원이 없습니다.", ephemeral=True)
            return

        parties  = _split_parties(members, raid.get('size', 4))

        party_ch = get_channel(interaction.guild, CH_PARTY)
        if not party_ch:
            await interaction.followup.send("❌ 레이드편성 채널이 없습니다.", ephemeral=True)
            return

        guild_name = get_guild_name(interaction.guild_id, interaction.guild.name if interaction.guild else '')
        slug = save_result_snapshot(
            interaction.guild_id, _get_week_label(),
            {raid_name: {'day': raid.get('day', ''), 'time_str': raid.get('time_str', ''), 'parties': parties, 'conflicts': []}},
            guild_name
        )

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
            all_avail=all_avail,
        )
        await thread.send(content=f"🔗 편성 결과 보기: {build_web_url(slug)}", view=view)
        await interaction.followup.send(f"✅ {thread.mention} 에서 확인하세요!", ephemeral=True)
        asyncio.create_task(_send_ai_commentary(thread, raid_name, members, interaction.guild_id))
        asyncio.create_task(_send_avg_level(thread, raid_name, members, interaction.guild_id))
        asyncio.create_task(delete_thread_after(thread, 604800))


# ==================== 파티 그룹 확정 View ====================

class PartyGroupConfirmView(discord.ui.View):
    def __init__(self, thread, group_results, guild_id, url, data, all_avail,
                 total_groups=1, confirmed_counter=None, weekly_callback=None):
        super().__init__(timeout=None)
        self.thread            = thread
        self.group_results     = group_results
        self.guild_id          = guild_id
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
            failed = await _save_party_results(self.guild_id, self.group_results)

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
        for r in self.group_results:
            remove_raid_from_snapshot(self.guild_id, r['name'])
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
        await self.thread.send("🔄 재편성 중...")
        try:
            new_assignments = assign_raid_times(self.guild_id)
            target_cols = {r['raid']['col'] for r in self.group_results}
            new_group = [a for a in new_assignments if a['raid']['col'] in target_cols and a['parties']]
            if not new_group:
                await interaction.followup.send("⚠️ 재편성 결과가 없습니다.", ephemeral=True)
                return
            new_results = [{
                'raid':      a['raid'],
                'name':      a['raid']['full_name'],
                'members':   a['members'],
                'parties':   a['parties'],
                'time_str':  a['time_str'],
                'day':       a['assigned_day'],
                'conflicts': a.get('conflicts', []),
            } for a in new_group]
            self.group_results = new_results
            web_raids = {
                r['name']: {'day': r['day'], 'time_str': r['time_str'], 'parties': r['parties'], 'conflicts': r.get('conflicts', [])}
                for r in new_results
            }
            guild_name = get_guild_name(self.guild_id, interaction.guild.name if interaction.guild else '')
            slug = save_result_snapshot(self.guild_id, _get_week_label(), web_raids, guild_name)
            await interaction.message.delete()
            await self.thread.send(content=f"🔗 재편성 결과 보기: {build_web_url(slug)}", view=self)
        except Exception as e:
            print(f"[party] 재편성 오류: {e}")
            await interaction.followup.send("❌ 재편성에 실패했습니다. 잠시 후 다시 시도해주세요.", ephemeral=True)


# ==================== 통합 확정 View (주간 전체 편성) ====================
# 레이드가 여러 개면 그룹마다 저장/미정/재편성을 따로 눌러야 했던 걸,
# "전체 저장" 하나 + 손봐야 할 레이드만 드롭다운으로 고르는 구조로 통합.

class SingleRaidActionView(discord.ui.View):
    """드롭다운에서 레이드 하나를 골랐을 때 뜨는 미정 처리 / 재편성 선택지."""

    def __init__(self, parent: "UnifiedConfirmView", raid_name: str):
        super().__init__(timeout=120)
        self.parent    = parent
        self.raid_name = raid_name

    @discord.ui.button(label="⏸ 이 레이드만 미정 처리", style=discord.ButtonStyle.secondary)
    async def exclude(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await require_admin(interaction): return
        self.parent.results.pop(self.raid_name, None)
        remove_raid_from_snapshot(self.parent.guild_id, self.raid_name)
        await self.parent._refresh_control_message()
        await interaction.response.edit_message(
            content=f"⏸ **{self.raid_name}** 미정 처리로 제외했습니다 (전체 저장 대상에서 빠짐).",
            view=None
        )

    @discord.ui.button(label="🔄 이 레이드만 재편성", style=discord.ButtonStyle.primary)
    async def recompose(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await require_admin(interaction): return
        await interaction.response.defer(ephemeral=True)
        try:
            target_col = self.parent.results.get(self.raid_name, {}).get('raid', {}).get('col')
            new_assignments = assign_raid_times(self.parent.guild_id)
            match = next((a for a in new_assignments if a['raid']['col'] == target_col and a['parties']), None)
            if not match:
                await interaction.followup.send("⚠️ 재편성 결과가 없습니다.", ephemeral=True)
                return
            new_result = {
                'raid':      match['raid'],
                'name':      self.raid_name,
                'members':   match['members'],
                'parties':   match['parties'],
                'time_str':  match['time_str'],
                'day':       match['assigned_day'],
                'conflicts': match.get('conflicts', []),
            }
            self.parent.results[self.raid_name] = new_result
            await self.parent._refresh_control_message()
            guild_name = get_guild_name(self.parent.guild_id, interaction.guild.name if interaction.guild else '')
            slug = save_result_snapshot(
                self.parent.guild_id, _get_week_label(),
                {self.raid_name: {'day': new_result['day'], 'time_str': new_result['time_str'], 'parties': new_result['parties'], 'conflicts': new_result.get('conflicts', [])}},
                guild_name
            )
            await self.parent.thread.send(
                content=f"🔄 **{self.raid_name}** 재편성 결과 (전체 저장에 반영됨) — 🔗 {build_web_url(slug)}"
            )
            await interaction.followup.send(f"✅ **{self.raid_name}** 재편성 완료!", ephemeral=True)
        except Exception as e:
            print(f"[party] 통합뷰 재편성 오류: {e}")
            await interaction.followup.send("❌ 재편성에 실패했습니다. 잠시 후 다시 시도해주세요.", ephemeral=True)


class UnifiedConfirmView(discord.ui.View):
    """레이드 여러 개를 한 번에 검토하는 통합 확정 화면. control_message는 전송 직후 채워준다."""

    def __init__(self, thread, results: dict, guild_id: int, weekly_callback=None):
        super().__init__(timeout=None)
        self.thread          = thread
        self.results         = results  # {raid_name: formatted_result}
        self.guild_id        = guild_id
        self.weekly_callback = weekly_callback
        self.control_message = None
        self._build_select()

    def _build_select(self):
        for item in list(self.children):
            if isinstance(item, discord.ui.Select):
                self.remove_item(item)
        if not self.results:
            return
        options = [
            discord.SelectOption(label=name[:100], value=name)
            for name in list(self.results.keys())[:25]
        ]
        select = discord.ui.Select(
            placeholder="개별로 손볼 레이드가 있으면 선택 (없으면 바로 전체 저장)",
            options=options,
            custom_id="unified_select",
            row=1
        )
        select.callback = self._on_select
        self.add_item(select)

    async def _refresh_control_message(self):
        self._build_select()
        if self.control_message:
            try:
                await self.control_message.edit(
                    content=f"📦 총 **{len(self.results)}개** 레이드 편성 완료 — 검토 후 저장해주세요.",
                    view=self
                )
            except Exception:
                pass

    async def _on_select(self, interaction: discord.Interaction):
        if not await require_admin(interaction): return
        raid_name = interaction.data["values"][0]
        view = SingleRaidActionView(self, raid_name)
        await interaction.response.send_message(
            f"**{raid_name}** 를 어떻게 할까요?", view=view, ephemeral=True
        )

    @discord.ui.button(label="✅ 전체 저장", style=discord.ButtonStyle.success, custom_id="unified_confirm", row=0)
    async def confirm_all(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await require_admin(interaction): return
        if not self.results:
            await interaction.response.send_message("저장할 편성이 없습니다 (전부 미정 처리됨).", ephemeral=True)
            return

        button.disabled = True
        button.label    = "저장 중..."
        await interaction.response.edit_message(view=self)

        confirmed_by = interaction.user.display_name
        results = list(self.results.values())
        failed  = await _save_party_results(self.guild_id, results)

        summary = " · ".join(
            f"{r['name']} {r['day']}{'요일 ' if r['day'] != '미정' else ' '}{r['time_str']}"
            for r in results
        )
        if len(summary) > 1500:
            summary = summary[:1500] + f" 외 더 있음"
        fail_txt = " | ⚠️ 저장 실패: " + ", ".join(failed) if failed else ""

        try:
            await interaction.message.edit(
                content=f"✅ 전체 {len(results)}개 레이드 — **{confirmed_by}** 확정\n{summary}{fail_txt}",
                view=None
            )
        except Exception:
            pass

        if self.weekly_callback:
            await self.weekly_callback()

        try:
            await self.thread.edit(locked=True, archived=False)
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
        embed = discord.Embed(title="⚡ 시너지 분석 — 클래스 선택", description="분석할 직업의 클래스를 선택하세요", color=0x9B59B6)
        await interaction.response.send_message(embed=embed, view=SynergyClassSelectView(), ephemeral=True)


async def setup(bot):
    cog = PartyCog(bot)
    await bot.add_cog(cog)
    bot.add_view(PartyPanelView())