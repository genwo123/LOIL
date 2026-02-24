"""
로일(LoIl) - 공지 Cog
📡│공지 채널 메인

흐름:
1. 길드장 → 멘션 대상 선택 → 주차별 스레드 생성 + 알림
2. 길드원 → 스레드에서 "일정 입력 완료" 버튼
3. 24시간 미완료 → 자동 재호출
4. 재호출 후 2시간 무응답 → 자동 불참
5. 전원 완료 → 길드장 알림
"""

import discord
from discord.ext import commands, tasks
from discord import app_commands
import json, os
from datetime import datetime, timezone, timedelta

from bot.utils.member_link import (
    get_sheet_name, set_absence, remove_absence, get_absences
)
from bot.utils.permissions import require_admin
from bot.config.channels import CH_NOTICE, CH_PARTY, get_channel

SETTINGS_FILE  = "bot/data/guild_settings.json"
SCHEDULE_FILE  = "bot/data/schedule_state.json"  # 주차별 완료 상태 저장

KST = timezone(timedelta(hours=9))

# ==================== 설정 로드/저장 ====================

def load_settings() -> dict:
    if not os.path.exists(SETTINGS_FILE):
        return {}
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def get_sheet_url(guild_id: int) -> str:
    return load_settings().get(str(guild_id), {}).get("sheet_url", "")

def load_state() -> dict:
    if not os.path.exists(SCHEDULE_FILE):
        return {}
    try:
        with open(SCHEDULE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_state(data: dict):
    os.makedirs(os.path.dirname(SCHEDULE_FILE), exist_ok=True)
    with open(SCHEDULE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def week_key() -> str:
    """로아 주차 키 (수요일 기준)"""
    now = datetime.now(KST)
    days_since_wed = (now.weekday() - 2) % 7
    if now.weekday() == 2 and now.hour < 9:
        days_since_wed = 7
    ref = now - timedelta(days=days_since_wed)
    return ref.strftime("%Y-W%V")

def get_guild_state(guild_id: int) -> dict:
    return load_state().get(str(guild_id), {})

def update_guild_state(guild_id: int, key: str, value):
    state = load_state()
    gid   = str(guild_id)
    if gid not in state:
        state[gid] = {}
    state[gid][key] = value
    save_state(state)


# ==================== 멘션 대상 선택 ====================

class MentionSelectView(discord.ui.View):
    """길드장이 @멘션 대상 고르는 드롭다운"""

    def __init__(self, guild: discord.Guild, notice_cog):
        super().__init__(timeout=60)
        self.guild      = guild
        self.notice_cog = notice_cog

        # 옵션: everyone, here + 서버 역할들
        options = [
            discord.SelectOption(label="@everyone",  value="everyone",  description="서버 전체"),
            discord.SelectOption(label="@here",      value="here",      description="현재 온라인"),
        ]
        for role in guild.roles:
            if role.name != "@everyone" and not role.managed:
                options.append(
                    discord.SelectOption(label=f"@{role.name}", value=f"role:{role.id}")
                )

        select = discord.ui.Select(
            placeholder="알림 대상을 선택하세요",
            options=options[:25]
        )
        select.callback = self.on_select
        self.add_item(select)

    async def on_select(self, interaction: discord.Interaction):
        value = interaction.data["values"][0]

        if value == "everyone":
            mention = "@everyone"
        elif value == "here":
            mention = "@here"
        else:
            role_id = int(value.split(":")[1])
            role    = interaction.guild.get_role(role_id)
            mention = role.mention if role else "@everyone"

        await self.notice_cog.send_schedule_request(interaction, mention)


# ==================== 완료 버튼 View ====================

class ScheduleCompleteView(discord.ui.View):
    """스레드에서 길드원이 누르는 완료/불참 버튼"""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="일정 입력 완료",
        style=discord.ButtonStyle.success,
        custom_id="schedule_complete"
    )
    async def complete(self, interaction: discord.Interaction, button: discord.ui.Button):
        sheet_name = get_sheet_name(interaction.guild_id, interaction.user.id)
        if not sheet_name:
            await interaction.response.send_message(
                "먼저 시트 연결이 필요해요!\n`/내시트연결` 명령어로 연결해주세요.",
                ephemeral=True
            )
            return

        wk  = week_key()
        gid = str(interaction.guild_id)

        state = load_state()
        if gid not in state:
            state[gid] = {}
        if wk not in state[gid]:
            state[gid][wk] = {"completed": [], "absent": [], "thread_id": None, "notified": False}

        week_state = state[gid][wk]

        # 불참 해제
        if sheet_name in week_state.get("absent", []):
            week_state["absent"].remove(sheet_name)
            remove_absence(interaction.guild_id, sheet_name)

        # 완료 등록
        if sheet_name not in week_state.get("completed", []):
            week_state["completed"].append(sheet_name)

        week_state[f"time_{sheet_name}"] = datetime.now(KST).isoformat()
        save_state(state)

        # 스레드 메시지 업데이트
        await _update_thread_status(interaction.guild, wk, state[gid][wk])

        await interaction.response.send_message(
            f"✅ **{sheet_name}** 님 일정 입력 완료로 등록되었습니다!",
            ephemeral=True
        )

        # 전원 완료 체크
        await _check_all_complete(interaction.guild, wk, state[gid][wk])

    @discord.ui.button(
        label="이번주 불참",
        style=discord.ButtonStyle.danger,
        custom_id="schedule_absent"
    )
    async def absent(self, interaction: discord.Interaction, button: discord.ui.Button):
        sheet_name = get_sheet_name(interaction.guild_id, interaction.user.id)
        if not sheet_name:
            await interaction.response.send_message(
                "먼저 시트 연결이 필요해요!\n`/내시트연결` 명령어로 연결해주세요.",
                ephemeral=True
            )
            return

        wk  = week_key()
        gid = str(interaction.guild_id)

        state = load_state()
        if gid not in state:
            state[gid] = {}
        if wk not in state[gid]:
            state[gid][wk] = {"completed": [], "absent": [], "thread_id": None, "notified": False}

        week_state = state[gid][wk]

        # 완료 해제
        if sheet_name in week_state.get("completed", []):
            week_state["completed"].remove(sheet_name)

        # 불참 등록
        if sheet_name not in week_state.get("absent", []):
            week_state["absent"].append(sheet_name)
        set_absence(interaction.guild_id, sheet_name)

        week_state[f"time_{sheet_name}"] = datetime.now(KST).isoformat()
        save_state(state)

        await _update_thread_status(interaction.guild, wk, week_state)
        await interaction.response.send_message(
            f"**{sheet_name}** 님이 이번주 불참으로 등록되었습니다.",
            ephemeral=True
        )

        await _check_all_complete(interaction.guild, wk, week_state)


# ==================== 스레드 상태 업데이트 ====================

async def _update_thread_status(guild: discord.Guild, wk: str, week_state: dict):
    """스레드의 완료 현황 메시지 업데이트"""
    thread_id  = week_state.get("thread_id")
    status_mid = week_state.get("status_message_id")
    if not thread_id:
        return

    try:
        thread = guild.get_thread(thread_id) or await guild.fetch_channel(thread_id)
    except Exception:
        return

    completed = week_state.get("completed", [])
    absent    = week_state.get("absent", [])

    lines = []
    for name in completed:
        lines.append(f"✅ {name}")
    for name in absent:
        lines.append(f"❌ {name} (불참)")

    embed = discord.Embed(
        title=f"📋 {wk} 일정 입력 현황",
        description="\n".join(lines) if lines else "아직 응답자가 없습니다.",
        color=0x57F287 if lines else 0x5865F2
    )
    embed.set_footer(text=f"완료 {len(completed)}명 · 불참 {len(absent)}명")

    try:
        if status_mid:
            msg = await thread.fetch_message(status_mid)
            await msg.edit(embed=embed)
        else:
            msg = await thread.send(embed=embed)
            week_state["status_message_id"] = msg.id
            state = load_state()
            gid   = str(guild.id)
            if gid in state and wk in state[gid]:
                state[gid][wk]["status_message_id"] = msg.id
                save_state(state)
    except Exception as e:
        print(f"[notice] 상태 메시지 업데이트 실패: {e}")


async def _check_all_complete(guild: discord.Guild, wk: str, week_state: dict):
    """전원 완료 시 길드장(관리자)에게 DM 알림"""
    if week_state.get("notified"):
        return

    completed = week_state.get("completed", [])
    absent    = week_state.get("absent", [])
    total     = len(completed) + len(absent)

    # 전체 멤버 수 비교 (시트 연결된 멤버 기준)
    settings = load_settings().get(str(guild.id), {})
    members_map = settings.get("members", {})
    total_linked = len(members_map)

    if total_linked > 0 and total >= total_linked:
        # 관리자에게 DM
        for member in guild.members:
            if member.guild_permissions.administrator and not member.bot:
                try:
                    embed = discord.Embed(
                        title="모든 길드원이 일정을 완료했습니다!",
                        description=(
                            f"**{wk}** 주차\n\n"
                            f"✅ 완료: {len(completed)}명\n"
                            f"❌ 불참: {len(absent)}명\n\n"
                            "이제 레이드 편성을 진행해주세요!"
                        ),
                        color=0x57F287
                    )
                    await member.send(embed=embed)
                except Exception:
                    pass

        week_state["notified"] = True
        state = load_state()
        gid   = str(guild.id)
        if gid in state and wk in state[gid]:
            state[gid][wk]["notified"] = True
            save_state(state)


# ==================== NoticeCog ====================

class NoticeCog(commands.Cog, name="NoticeCog"):

    def __init__(self, bot):
        self.bot = bot
        bot.add_view(ScheduleCompleteView())
        self.auto_check.start()

    def cog_unload(self):
        self.auto_check.cancel()

    async def send_schedule_request(self, interaction: discord.Interaction, mention: str):
        """주차별 스레드 생성 + 일정 입력 요청"""
        notice_ch = get_channel(interaction.guild, CH_NOTICE)
        if not notice_ch:
            await interaction.response.send_message("❌ 공지 채널을 찾을 수 없습니다.", ephemeral=True)
            return

        wk      = week_key()
        gid     = str(interaction.guild_id)
        state   = load_state()
        sheet_url = get_sheet_url(interaction.guild_id)

        # 이미 이번주 스레드 있으면 재사용
        if gid in state and wk in state[gid] and state[gid][wk].get("thread_id"):
            existing_thread_id = state[gid][wk]["thread_id"]
            try:
                thread = interaction.guild.get_thread(existing_thread_id)
                if thread:
                    await interaction.response.send_message(
                        f"이번 주 스레드가 이미 있어요! {thread.mention}", ephemeral=True
                    )
                    return
            except Exception:
                pass

        await interaction.response.defer(ephemeral=True)

        # 공지 메시지 전송
        embed = discord.Embed(
            title=f"📋 {wk} 이번주 레이드 일정 입력 요청",
            description=(
                f"{mention}\n\n"
                f"이번 주 레이드 일정을 입력해주세요!\n\n"
                f"1. 아래 시트에서 가능한 시간 입력\n"
                f"2. 완료 후 스레드에서 **일정 입력 완료** 버튼 클릭\n"
                f"3. 이번주 참가 불가 시 **이번주 불참** 버튼 클릭\n\n"
                f"⏰ **24시간 내 미응답 시 재알림**\n"
                f"⏰ **재알림 후 2시간 내 무응답 시 자동 불참 처리**"
            ),
            color=0x5865F2
        )
        if sheet_url:
            embed.add_field(name="시트 링크", value=sheet_url, inline=False)
        embed.set_footer(text=f"요청자: {interaction.user.display_name}")

        msg = await notice_ch.send(embed=embed)

        # 스레드 생성
        thread = await msg.create_thread(
            name=f"{wk} 일정 입력",
            auto_archive_duration=10080  # 7일
        )

        # 스레드에 완료 버튼 전송
        await thread.send(
            "시트에 일정 입력 후 아래 버튼을 눌러주세요!",
            view=ScheduleCompleteView()
        )

        # 상태 저장
        if gid not in state:
            state[gid] = {}
        state[gid][wk] = {
            "completed":        [],
            "absent":           [],
            "thread_id":        thread.id,
            "message_id":       msg.id,
            "status_message_id": None,
            "notified":         False,
            "created_at":       datetime.now(KST).isoformat(),
            "reminded":         [],   # 재알림 보낸 사람 목록
        }
        save_state(state)

        await interaction.followup.send(
            f"✅ {thread.mention} 스레드를 생성했습니다!", ephemeral=True
        )

    # ==================== 네비게이션 패널 ====================

    async def send_notice_panel(self, channel: discord.TextChannel):
        embed = discord.Embed(
            title="📡 공지 센터",
            description="길드 공지 및 일정 관리 채널입니다.",
            color=0x5865F2
        )
        embed.add_field(
            name="길드원",
            value="• 일정 입력 요청이 오면 스레드에서 완료 버튼 클릭",
            inline=False
        )
        embed.add_field(
            name="관리자",
            value=(
                "• **일정 입력 요청** — 이번주 일정 입력 알림 발송\n"
                "• **편성 완료 공지** — 파티 편성 결과 공지\n"
                "• **불참 해제** — 자동 불참 처리된 멤버 해제"
            ),
            inline=False
        )
        view = NoticePanelView()
        msg  = await channel.send(embed=embed, view=view)
        try:
            await msg.pin()
        except Exception:
            pass
        return msg

    # ==================== 자동 재알림 + 자동 불참 ====================

    @tasks.loop(minutes=10)
    async def auto_check(self):
        """10분마다 미응답자 체크"""
        now   = datetime.now(KST)
        state = load_state()

        for gid, guild_state in state.items():
            guild = self.bot.get_guild(int(gid))
            if not guild:
                continue

            wk = week_key()
            if wk not in guild_state:
                continue

            week_state = guild_state[wk]
            thread_id  = week_state.get("thread_id")
            if not thread_id:
                continue

            try:
                thread = guild.get_thread(thread_id) or await guild.fetch_channel(thread_id)
            except Exception:
                continue

            created_at = datetime.fromisoformat(week_state.get("created_at", now.isoformat()))
            elapsed    = (now - created_at).total_seconds()

            # 시트 연결된 전체 멤버
            settings    = load_settings().get(gid, {})
            members_map = settings.get("members", {})  # {discord_id: sheet_name}

            completed = week_state.get("completed", [])
            absent    = week_state.get("absent", [])
            reminded  = week_state.get("reminded", [])
            done      = set(completed + absent)

            for discord_id, sheet_name in members_map.items():
                if sheet_name in done:
                    continue

                remind_time = week_state.get(f"remind_time_{sheet_name}")

                if elapsed >= 86400 and sheet_name not in reminded:
                    # 24시간 경과 → 재알림
                    try:
                        member = guild.get_member(int(discord_id))
                        if member:
                            await thread.send(
                                f"{member.mention} 아직 일정 입력을 하지 않으셨어요! "
                                f"2시간 내 미응답 시 자동 불참 처리됩니다."
                            )
                            week_state.setdefault("reminded", []).append(sheet_name)
                            week_state[f"remind_time_{sheet_name}"] = now.isoformat()
                    except Exception as e:
                        print(f"[notice] 재알림 실패 ({sheet_name}): {e}")

                elif remind_time:
                    remind_elapsed = (now - datetime.fromisoformat(remind_time)).total_seconds()
                    if remind_elapsed >= 7200 and sheet_name not in absent:
                        # 재알림 후 2시간 경과 → 자동 불참
                        week_state.setdefault("absent", []).append(sheet_name)
                        set_absence(int(gid), sheet_name)
                        try:
                            await thread.send(
                                f"⚠️ **{sheet_name}** 님이 미응답으로 자동 불참 처리되었습니다.\n"
                                f"관리자가 `/불참해제` 명령어로 해제할 수 있습니다."
                            )
                        except Exception:
                            pass
                        await _update_thread_status(guild, wk, week_state)
                        await _check_all_complete(guild, wk, week_state)

            # 변경사항 저장
            state[gid][wk] = week_state
            save_state(state)

    @auto_check.before_loop
    async def before_auto_check(self):
        await self.bot.wait_until_ready()

    # ==================== 슬래시 명령어 ====================

    @app_commands.command(name="일정요청", description="이번주 일정 입력을 요청합니다 (관리자)")
    async def request_schedule(self, interaction: discord.Interaction):
        if not await require_admin(interaction): return
        view = MentionSelectView(guild=interaction.guild, notice_cog=self)
        await interaction.response.send_message(
            "알림 대상을 선택하세요:", view=view, ephemeral=True
        )

    @app_commands.command(name="불참해제", description="자동 불참 처리된 멤버를 해제합니다 (관리자)")
    async def remove_absence_cmd(self, interaction: discord.Interaction):
        if not await require_admin(interaction): return

        wk         = week_key()
        gid        = str(interaction.guild_id)
        state      = load_state()
        week_state = state.get(gid, {}).get(wk, {})
        absent     = week_state.get("absent", [])

        if not absent:
            await interaction.response.send_message("이번주 불참자가 없습니다!", ephemeral=True)
            return

        options = [
            discord.SelectOption(label=name, value=name)
            for name in absent
        ]
        view = AbsenceRemoveView(options=options, gid=gid, wk=wk)
        await interaction.response.send_message(
            "불참 해제할 멤버를 선택하세요:", view=view, ephemeral=True
        )

    @app_commands.command(name="이번주현황", description="이번주 일정 입력 현황을 확인합니다")
    async def week_status(self, interaction: discord.Interaction):
        wk         = week_key()
        gid        = str(interaction.guild_id)
        week_state = load_state().get(gid, {}).get(wk, {})

        completed = week_state.get("completed", [])
        absent    = week_state.get("absent", [])

        lines = []
        for name in completed:
            lines.append(f"✅ {name}")
        for name in absent:
            lines.append(f"❌ {name} (불참)")

        embed = discord.Embed(
            title=f"📋 {wk} 일정 입력 현황",
            description="\n".join(lines) if lines else "아직 응답자가 없습니다.",
            color=0x5865F2
        )
        embed.set_footer(text=f"완료 {len(completed)}명 · 불참 {len(absent)}명")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="내시트연결", description="내 시트 탭을 연결합니다")
    async def link_sheet(self, interaction: discord.Interaction):
        url = get_sheet_url(interaction.guild_id)
        if not url:
            await interaction.response.send_message(
                "❌ 시트가 연동되지 않았습니다. 관리자에게 문의해주세요.", ephemeral=True
            )
            return
        view = LinkStep1View(guild=interaction.guild, url=url)
        await interaction.response.send_message(
            "**1단계** — 본인 Discord 닉네임을 선택해주세요:", view=view, ephemeral=True
        )


# ==================== 시트 연결 2단계 드롭다운 ====================

SYSTEM_TABS = ["주간레이드", "AI편성결과", "공지", "Sheet1"]

class LinkStep1View(discord.ui.View):
    """1단계: 서버 멤버 목록에서 본인 선택"""

    def __init__(self, guild: discord.Guild, url: str):
        super().__init__(timeout=60)
        self.url = url

        # 로일 역할 있으면 해당 멤버만, 없으면 전체
        loil_role = discord.utils.get(guild.roles, name="로일")
        if loil_role:
            members = [m for m in guild.members if loil_role in m.roles and not m.bot]
        else:
            members = [m for m in guild.members if not m.bot]

        options = [
            discord.SelectOption(
                label=m.display_name,
                value=str(m.id),
                description=f"@{m.name}"
            )
            for m in members[:25]
        ]

        select = discord.ui.Select(placeholder="본인 닉네임을 선택하세요", options=options)
        select.callback = self.on_select
        self.add_item(select)

    async def on_select(self, interaction: discord.Interaction):
        selected_id = int(interaction.data["values"][0])
        # 본인인지 확인
        if selected_id != interaction.user.id:
            await interaction.response.send_message(
                "❌ 본인 닉네임만 선택할 수 있습니다!", ephemeral=True
            )
            return
        # 2단계: 시트 탭 선택
        view = LinkStep2View(user_id=interaction.user.id, url=self.url, guild_id=interaction.guild_id)
        if view.has_tabs:
            await interaction.response.send_message(
                "**2단계** — 시트에서 본인 탭을 선택해주세요:", view=view, ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "❌ 시트 탭을 불러오지 못했습니다. 시트 연동을 확인해주세요.", ephemeral=True
            )


class LinkStep2View(discord.ui.View):
    """2단계: 시트 탭 목록에서 본인 탭 선택"""

    def __init__(self, user_id: int, url: str, guild_id: int):
        super().__init__(timeout=60)
        self.user_id  = user_id
        self.guild_id = guild_id
        self.has_tabs = False

        try:
            from bot.utils.sheets import get_sheet_info
            info = get_sheet_info(url)
            if info:
                tabs = [t for t in info.get("worksheets", []) if t not in SYSTEM_TABS]
                if tabs:
                    options = [
                        discord.SelectOption(label=tab, value=tab)
                        for tab in tabs[:25]
                    ]
                    select = discord.ui.Select(placeholder="본인 시트 탭을 선택하세요", options=options)
                    select.callback = self.on_select
                    self.add_item(select)
                    self.has_tabs = True
        except Exception as e:
            print(f"[notice] 시트 탭 로드 실패: {e}")

    async def on_select(self, interaction: discord.Interaction):
        from bot.utils.member_link import set_sheet_name
        tab_name = interaction.data["values"][0]
        set_sheet_name(self.guild_id, self.user_id, tab_name)
        await interaction.response.send_message(
            f"✅ **{interaction.user.display_name}** → **{tab_name}** 탭으로 연결되었습니다!",
            ephemeral=True
        )


# ==================== 불참 해제 View ====================

class AbsenceRemoveView(discord.ui.View):
    def __init__(self, options, gid, wk):
        super().__init__(timeout=60)
        self.gid = gid
        self.wk  = wk

        select = discord.ui.Select(placeholder="해제할 멤버 선택", options=options)
        select.callback = self.on_select
        self.add_item(select)

    async def on_select(self, interaction: discord.Interaction):
        sheet_name = interaction.data["values"][0]
        state      = load_state()

        if self.gid in state and self.wk in state[self.gid]:
            week_state = state[self.gid][self.wk]
            if sheet_name in week_state.get("absent", []):
                week_state["absent"].remove(sheet_name)
            # remind 기록도 초기화
            week_state.get("reminded", [])
            if sheet_name in week_state.get("reminded", []):
                week_state["reminded"].remove(sheet_name)
            week_state.pop(f"remind_time_{sheet_name}", None)
            save_state(state)

        remove_absence(interaction.guild_id, sheet_name)
        await _update_thread_status(
            interaction.guild, self.wk,
            state.get(self.gid, {}).get(self.wk, {})
        )
        await interaction.response.send_message(
            f"✅ **{sheet_name}** 님의 불참이 해제되었습니다!", ephemeral=True
        )


# ==================== 공지 패널 View ====================

class NoticePanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="일정 입력 요청",
        style=discord.ButtonStyle.primary,
        custom_id="notice_request_schedule",
        row=0
    )
    async def request_schedule(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await require_admin(interaction): return
        notice_cog = interaction.client.cogs.get("NoticeCog")
        view = MentionSelectView(guild=interaction.guild, notice_cog=notice_cog)
        await interaction.response.send_message("알림 대상을 선택하세요:", view=view, ephemeral=True)

    @discord.ui.button(
        label="이번주 현황",
        style=discord.ButtonStyle.secondary,
        custom_id="notice_week_status",
        row=0
    )
    async def week_status(self, interaction: discord.Interaction, button: discord.ui.Button):
        wk         = week_key()
        gid        = str(interaction.guild_id)
        week_state = load_state().get(gid, {}).get(wk, {})
        completed  = week_state.get("completed", [])
        absent     = week_state.get("absent", [])

        lines = []
        for name in completed:
            lines.append(f"✅ {name}")
        for name in absent:
            lines.append(f"❌ {name} (불참)")

        embed = discord.Embed(
            title=f"📋 {wk} 현황",
            description="\n".join(lines) if lines else "아직 응답자가 없습니다.",
            color=0x5865F2
        )
        embed.set_footer(text=f"완료 {len(completed)}명 · 불참 {len(absent)}명")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(
        label="불참 해제",
        style=discord.ButtonStyle.danger,
        custom_id="notice_remove_absence",
        row=0
    )
    async def remove_absence(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await require_admin(interaction): return
        wk         = week_key()
        gid        = str(interaction.guild_id)
        week_state = load_state().get(gid, {}).get(wk, {})
        absent     = week_state.get("absent", [])

        if not absent:
            await interaction.response.send_message("이번주 불참자가 없습니다!", ephemeral=True)
            return

        options = [discord.SelectOption(label=name, value=name) for name in absent]
        view    = AbsenceRemoveView(options=options, gid=gid, wk=wk)
        await interaction.response.send_message("불참 해제할 멤버를 선택하세요:", view=view, ephemeral=True)

    @discord.ui.button(
        label="내 시트 연결",
        style=discord.ButtonStyle.primary,
        custom_id="notice_link_sheet",
        row=1
    )
    async def link_sheet(self, interaction: discord.Interaction, button: discord.ui.Button):
        url = get_sheet_url(interaction.guild_id)
        if not url:
            await interaction.response.send_message(
                "❌ 시트가 연동되지 않았습니다. 관리자에게 문의해주세요.", ephemeral=True
            )
            return
        view = LinkStep1View(guild=interaction.guild, url=url)
        await interaction.response.send_message(
            "**1단계** — 본인 Discord 닉네임을 선택해주세요:", view=view, ephemeral=True
        )

    @discord.ui.button(
        label="일정 조회 →",
        style=discord.ButtonStyle.secondary,
        custom_id="notice_to_schedule",
        row=1
    )
    async def to_schedule(self, interaction: discord.Interaction, button: discord.ui.Button):
        from bot.config.channels import CH_SCHEDULE
        ch = get_channel(interaction.guild, CH_SCHEDULE)
        await interaction.response.send_message(
            f"{ch.mention} 에서 일정을 확인하세요!" if ch else "채널을 찾을 수 없습니다.",
            ephemeral=True
        )

    @discord.ui.button(
        label="레이드 편성 →",
        style=discord.ButtonStyle.secondary,
        custom_id="notice_to_party",
        row=1
    )
    async def to_party(self, interaction: discord.Interaction, button: discord.ui.Button):
        party_ch = get_channel(interaction.guild, CH_PARTY)
        if party_ch:
            await interaction.response.send_message(
                f"레이드 편성은 {party_ch.mention} 채널에서 진행해주세요!", ephemeral=True
            )
        else:
            await interaction.response.send_message("레이드편성 채널을 찾을 수 없습니다.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(NoticeCog(bot))