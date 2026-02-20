"""
로일(LoIl) - 파티 Cog
버튼 + 드롭다운 중심 UI
- 파티-편성 채널 고정 메시지
- 레이드 선택 드롭다운 → AI 추천
- 확정 / 다시추천 / 삭제 버튼
"""

import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import json
import os
from bot.utils.gemini_ai import recommend_party, analyze_synergy
from bot.utils.sheets import get_all_data, get_weekly_summary, get_members, parse_raids
from bot.config.settings import GEMINI_API_KEY

# ==================== 설정 불러오기 ====================

SETTINGS_FILE = "bot/data/guild_settings.json"

def get_guild_setting(guild_id: int) -> dict:
    if not os.path.exists(SETTINGS_FILE):
        return {}
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f).get(str(guild_id), {})
    except Exception:
        return {}

def get_sheet_url(guild_id: int):
    return get_guild_setting(guild_id).get("sheet_url")

def get_gemini_key(guild_id: int) -> str:
    """길드 Gemini 키 → 없으면 .env 폴백"""
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


# ==================== 파티-편성 패널 임베드 ====================

def build_party_panel_embed() -> discord.Embed:
    embed = discord.Embed(
        title="⚔️ 파티 편성 센터",
        description=(
            "아래 버튼으로 레이드를 선택하면\n"
            "**AI가 최적의 파티 구성을 추천**해드립니다!\n\n"
            "시너지 · 서폿 배치 · 인원 구성을 자동으로 분석합니다."
        ),
        color=0x9B59B6
    )
    embed.add_field(
        name="💡 사용 방법",
        value=(
            "1️⃣ **레이드 선택** 버튼 클릭\n"
            "2️⃣ 원하는 레이드 선택\n"
            "3️⃣ AI 파티 추천 결과 확인\n"
            "4️⃣ **확정** 버튼으로 파티 확정"
        ),
        inline=False
    )
    embed.add_field(
        name="⚡ 시너지 분석",
        value="직업 목록 입력 → 시너지 조합 분석",
        inline=False
    )
    embed.set_footer(text="파티 확정 시 스레드 잠금 · 7일 후 자동 삭제")
    return embed


# ==================== 파티 패널 View ====================

class PartyPanelView(discord.ui.View):
    """파티-편성 채널 고정 버튼"""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="⚔️ 레이드 선택",
        style=discord.ButtonStyle.primary,
        custom_id="party_select_raid",
        row=0
    )
    async def select_raid(self, interaction: discord.Interaction, button: discord.ui.Button):
        """레이드 목록 드롭다운"""
        await interaction.response.defer(ephemeral=True)

        url = get_sheet_url(interaction.guild_id)
        if not url:
            await interaction.followup.send(
                "❌ 시트가 연동되지 않았습니다.\n⚙️ **로일-설정** 채널에서 설정해주세요.",
                ephemeral=True
            )
            return

        data  = get_all_data(url)
        raids = parse_raids(data)

        if not raids:
            await interaction.followup.send(
                "❌ 이번 주 예정된 레이드가 없습니다.", ephemeral=True
            )
            return

        # 드롭다운 옵션 생성 (최대 25개)
        options = []
        seen = set()
        for r in raids[:25]:
            label = f"{r['day']}요일 {r['time_str']} {r['name']}"
            if label not in seen:
                seen.add(label)
                options.append(
                    discord.SelectOption(
                        label=r['name'],
                        description=f"{r['day']}요일 {r['time_str']} · ~{r['duration']}분",
                        value=f"{r['col']}|{r['name']}"
                    )
                )

        view = RaidSelectView(options=options, data=data)
        await interaction.followup.send(
            "⚔️ 파티 편성할 레이드를 선택해주세요:",
            view=view,
            ephemeral=True
        )

    @discord.ui.button(
        label="⚡ 시너지 분석",
        style=discord.ButtonStyle.secondary,
        custom_id="party_synergy",
        row=0
    )
    async def synergy_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(SynergyModal())

    @discord.ui.button(
        label="👥 현재 파티 현황",
        style=discord.ButtonStyle.secondary,
        custom_id="party_status",
        row=1
    )
    async def party_status(self, interaction: discord.Interaction, button: discord.ui.Button):
        """레이드별 현재 참여 인원 현황"""
        await interaction.response.defer(ephemeral=True)

        url = get_sheet_url(interaction.guild_id)
        if not url:
            await interaction.followup.send("❌ 시트 연동 필요", ephemeral=True)
            return

        data    = get_all_data(url)
        summary = get_weekly_summary(data)

        embed = discord.Embed(
            title="👥 레이드별 참여 현황",
            color=0x5865F2
        )

        for raid in summary[:10]:
            members = raid.get('members', [])
            sup_cnt = sum(1 for m in members if m['is_support'])
            dps_cnt = len(members) - sup_cnt

            member_names = " · ".join([m['name'] for m in members]) if members else "없음"
            embed.add_field(
                name=f"⚔️ {raid['name']} ({raid.get('day','?')}요일 {raid.get('time_str','?')})",
                value=f"💚 서폿 {sup_cnt}명 · ⚔️ 딜러 {dps_cnt}명\n{member_names}",
                inline=False
            )

        await interaction.followup.send(embed=embed, ephemeral=True)


# ==================== 레이드 선택 드롭다운 ====================

class RaidSelectView(discord.ui.View):
    """레이드 선택 드롭다운"""

    def __init__(self, options: list, data: list):
        super().__init__(timeout=60)
        self.data = data
        select = RaidSelect(options=options, data=data)
        self.add_item(select)


class RaidSelect(discord.ui.Select):
    def __init__(self, options: list, data: list):
        super().__init__(
            placeholder="레이드를 선택하세요...",
            min_values=1,
            max_values=1,
            options=options
        )
        self.data = data

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        value      = self.values[0]
        col_str, raid_name = value.split("|", 1)
        col        = int(col_str)

        # 해당 레이드 참여자 수집
        members_data = get_members(self.data)
        members = []
        for m in members_data:
            if m['absent']:
                continue
            char = m['characters'].get(col)
            if char:
                members.append({
                    'name':       m['name'],
                    'character':  char,
                    'job':        char.split('(')[0].strip(),
                    'is_support': is_support(char),
                    'level':      0
                })

        if not members:
            await interaction.followup.send(
                f"❌ **{raid_name}** 에 참여 예정인 길드원이 없습니다.",
                ephemeral=True
            )
            return

        # 파티-편성 채널에 스레드 생성
        party_channel = discord.utils.get(
            interaction.guild.text_channels, name="파티-편성"
        )
        if not party_channel:
            await interaction.followup.send("❌ 파티-편성 채널이 없습니다.", ephemeral=True)
            return

        # 로딩 메시지
        loading_embed = discord.Embed(
            title="🤖 AI 파티 편성 중...",
            description=f"**{raid_name}** 레이드 파티를 분석하고 있습니다!\n잠시만 기다려주세요...",
            color=0xFEE75C
        )
        thread = await party_channel.create_thread(
            name=f"⚔️ {raid_name} 파티 편성",
            auto_archive_duration=10080,
            type=discord.ChannelType.public_thread
        )
        loading_msg = await thread.send(embed=loading_embed)

        await interaction.followup.send(
            f"✅ {thread.mention} 에서 확인하세요!",
            ephemeral=True
        )

        # Gemini 키 폴백 적용
        gemini_key = get_gemini_key(interaction.guild_id)

        # AI 추천
        try:
            result = recommend_party(members, raid_name)
        except Exception as e:
            result = f"AI 추천 중 오류: {e}"

        # 결과 임베드
        sup_cnt = sum(1 for m in members if m['is_support'])
        dps_cnt = len(members) - sup_cnt

        result_embed = discord.Embed(
            title=f"⚔️ {raid_name} 파티 편성 추천",
            description=result[:2000] if len(result) > 2000 else result,
            color=0xFFD700
        )
        result_embed.add_field(name="👥 총 인원", value=f"{len(members)}명", inline=True)
        result_embed.add_field(name="💚 서폿",    value=f"{sup_cnt}명",      inline=True)
        result_embed.add_field(name="⚔️ 딜러",   value=f"{dps_cnt}명",      inline=True)

        # 참여자 목록
        member_list = "\n".join([
            f"{'💚' if m['is_support'] else '⚔️'} **{m['name']}** · {m['character']}"
            for m in members
        ])
        result_embed.add_field(name="📋 참여 인원", value=member_list[:1024], inline=False)
        result_embed.set_footer(text="✅ 확정 버튼으로 파티를 확정하세요 · 7일 후 자동 삭제")

        confirm_view = PartyConfirmView(thread=thread, raid_name=raid_name)
        await loading_msg.edit(embed=result_embed, view=confirm_view)

        asyncio.create_task(delete_thread_after(thread, 604800))


# ==================== 파티 확정 버튼 ====================

class PartyConfirmView(discord.ui.View):
    def __init__(self, thread: discord.Thread, raid_name: str):
        super().__init__(timeout=None)
        self.thread    = thread
        self.raid_name = raid_name

    @discord.ui.button(
        label="✅ 파티 확정",
        style=discord.ButtonStyle.success,
        custom_id="party_confirm"
    )
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ 관리자 또는 레이드장만 확정할 수 있습니다.", ephemeral=True
            )
            return

        for item in self.children:
            item.disabled = True
        await interaction.message.edit(view=self)

        await interaction.response.send_message(
            f"✅ **{interaction.user.display_name}** 님이 **{self.raid_name}** 파티를 확정했습니다!\n"
            "🔒 스레드가 잠깁니다."
        )
        try:
            await self.thread.edit(locked=True, archived=False)
        except Exception:
            pass

    @discord.ui.button(
        label="🔄 다시 추천",
        style=discord.ButtonStyle.primary,
        custom_id="party_retry"
    )
    async def retry(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "🔄 파티-편성 채널의 **레이드 선택** 버튼을 다시 눌러주세요!",
            ephemeral=True
        )

    @discord.ui.button(
        label="🗑️ 삭제",
        style=discord.ButtonStyle.danger,
        custom_id="party_delete"
    )
    async def delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ 관리자만 삭제 가능합니다.", ephemeral=True)
            return
        await interaction.response.send_message("🗑️ 스레드를 삭제합니다...")
        try:
            await self.thread.delete()
        except Exception:
            pass


# ==================== 시너지 Modal ====================

class SynergyModal(discord.ui.Modal, title="⚡ 시너지 분석"):
    jobs = discord.ui.TextInput(
        label="직업 목록 (쉼표로 구분)",
        placeholder="예: 홀리나이트, 소서리스, 리퍼, 블레이드",
        style=discord.TextStyle.short,
        required=True,
        max_length=200
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)

        job_list = [j.strip() for j in self.jobs.value.split(',') if j.strip()]

        if len(job_list) < 2:
            await interaction.followup.send(
                "❌ 직업을 2개 이상 입력해주세요!", ephemeral=True
            )
            return
        if len(job_list) > 8:
            await interaction.followup.send(
                "❌ 최대 8개까지 입력 가능합니다!", ephemeral=True
            )
            return

        try:
            result = analyze_synergy(job_list)
        except Exception as e:
            result = f"분석 중 오류: {e}"

        embed = discord.Embed(
            title="⚡ 시너지 분석 결과",
            description=result[:2000] if len(result) > 2000 else result,
            color=0x9B59B6
        )
        embed.add_field(
            name="분석 직업",
            value=" · ".join(job_list),
            inline=False
        )
        embed.set_footer(text="AI 분석 결과입니다")
        await interaction.followup.send(embed=embed)


# ==================== PartyCog ====================

class PartyCog(commands.Cog, name="PartyCog"):

    def __init__(self, bot):
        self.bot = bot
        self.panel_messages: dict[int, int] = {}

    async def send_party_panel(self, channel: discord.TextChannel):
        """파티-편성 채널에 패널 전송"""
        embed = build_party_panel_embed()
        view  = PartyPanelView()
        msg   = await channel.send(embed=embed, view=view)
        try:
            await msg.pin()
        except Exception:
            pass
        self.panel_messages[channel.guild.id] = msg.id

    # ── /파티패널 (수동 패널 올리기) ──

    @app_commands.command(name="파티패널", description="파티 편성 패널을 표시합니다 (관리자)")
    @app_commands.checks.has_permissions(administrator=True)
    async def party_panel(self, interaction: discord.Interaction):
        party_channel = discord.utils.get(
            interaction.guild.text_channels, name="파티-편성"
        )
        if not party_channel:
            await interaction.response.send_message(
                "❌ 파티-편성 채널이 없습니다.", ephemeral=True
            )
            return

        await self.send_party_panel(party_channel)
        await interaction.response.send_message(
            f"✅ {party_channel.mention} 에 파티 편성 패널을 표시했습니다!",
            ephemeral=True
        )

    @party_panel.error
    async def party_panel_error(self, interaction, error):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message("❌ 관리자만 사용 가능합니다.", ephemeral=True)

    # ── /파티추천 (기존 명령어 유지) ──

    @app_commands.command(name="파티추천", description="AI 파티 편성 추천")
    @app_commands.describe(레이드="레이드 이름 (예: 에기르 하드)")
    async def party_recommend(self, interaction: discord.Interaction, 레이드: str):
        await interaction.response.defer(thinking=True, ephemeral=True)

        url = get_sheet_url(interaction.guild_id)
        if not url:
            await interaction.followup.send(
                "❌ 시트가 연동되지 않았습니다.\n⚙️ **로일-설정** 채널에서 설정해주세요.",
                ephemeral=True
            )
            return

        data         = get_all_data(url)
        members_data = get_members(data)
        members = []
        for m in members_data:
            if m['absent'] or not m['characters']:
                continue
            first_char = next(iter(m['characters'].values()))
            members.append({
                'name':       m['name'],
                'character':  first_char,
                'job':        first_char.split('(')[0].strip(),
                'is_support': is_support(first_char),
                'level':      0
            })

        if not members:
            await interaction.followup.send("❌ 참여 가능한 길드원이 없습니다.", ephemeral=True)
            return

        try:
            result = recommend_party(members, 레이드)
        except Exception as e:
            result = f"오류: {e}"

        embed = discord.Embed(
            title=f"⚔️ {레이드} 파티 편성 추천",
            description=result[:2000],
            color=0xFFD700
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    # ── /시너지 (기존 명령어 유지) ──

    @app_commands.command(name="시너지", description="파티 시너지를 분석합니다")
    @app_commands.describe(직업들="직업 목록 (쉼표로 구분)")
    async def synergy_check(self, interaction: discord.Interaction, 직업들: str):
        await interaction.response.defer(thinking=True)

        jobs = [j.strip() for j in 직업들.split(',') if j.strip()]
        if not 2 <= len(jobs) <= 8:
            await interaction.followup.send("❌ 2~8개 직업을 입력해주세요!", ephemeral=True)
            return

        try:
            result = analyze_synergy(jobs)
        except Exception as e:
            result = f"오류: {e}"

        embed = discord.Embed(
            title="⚡ 시너지 분석 결과",
            description=result[:2000],
            color=0x9B59B6
        )
        embed.add_field(name="분석 직업", value=" · ".join(jobs), inline=False)
        await interaction.followup.send(embed=embed)


# ==================== Cog 등록 ====================

async def setup(bot):
    cog = PartyCog(bot)
    await bot.add_cog(cog)
    bot.add_view(PartyPanelView())