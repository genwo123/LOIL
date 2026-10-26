"""
로일(LoIl) - 공지 Cog
📡│공지 채널 메인

흐름:
1. 길드장 → 멘션 대상 선택 → 주차별 스레드 생성 + 알림
2. 길드원 → `/주간일정설정`으로 개인 링크 받아 웹에서 제출 (완료 처리 자동)
3. 24시간 미완료 → 자동 재호출
4. 재호출 후 2시간 무응답 → 자동 불참
5. 전원 완료 → 길드장 알림
"""

import asyncio
import discord
from discord.ext import commands, tasks
from discord import app_commands
import json, os
from datetime import datetime, timezone, timedelta

from bot.utils.member_link import (
    set_absence, remove_absence, get_absences, get_pending_members, claim_pending_member
)
from bot.utils.permissions import require_admin
from bot.utils.storage import load_settings
from bot.config.channels import CH_NOTICE, CH_PARTY, CH_SCHEDULE, get_channel
from bot.utils.channel_cleanup import purge_channel as _purge_channel

SCHEDULE_FILE  = "bot/data/schedule_state.json"  # 주차별 완료 상태 저장

KST = timezone(timedelta(hours=9))

# ==================== 설정 로드/저장 ====================

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


# ==================== 완료/불참 상태 변경 (공통) ====================
# Discord 버튼과 웹 가능시간 제출(web/availability.py) 둘 다 여기로 모아서 같은 로직을 쓴다.
# 스레드 임베드 갱신·전원완료 DM은 discord.Guild 객체가 있어야 해서(별도 프로세스인 웹에선 불가능)
# 여기선 안 하고, 다음 auto_check 주기(최대 10분)에서 모든 길드에 대해 자동으로 갱신한다.

def mark_schedule_complete(guild_id: int, sheet_name: str) -> dict:
    """일정 입력 완료로 등록. 반환값: 갱신된 week_state."""
    wk  = week_key()
    gid = str(guild_id)

    state = load_state()
    if gid not in state:
        state[gid] = {}
    if wk not in state[gid]:
        state[gid][wk] = {"completed": [], "absent": [], "thread_id": None, "notified": False}

    week_state = state[gid][wk]

    if sheet_name in week_state.get("absent", []):
        week_state["absent"].remove(sheet_name)
        remove_absence(guild_id, sheet_name)

    if sheet_name not in week_state.get("completed", []):
        week_state["completed"].append(sheet_name)

    week_state[f"time_{sheet_name}"] = datetime.now(KST).isoformat()
    save_state(state)
    return week_state


def mark_schedule_absent(guild_id: int, sheet_name: str) -> dict:
    """이번주 불참으로 등록. 반환값: 갱신된 week_state."""
    wk  = week_key()
    gid = str(guild_id)

    state = load_state()
    if gid not in state:
        state[gid] = {}
    if wk not in state[gid]:
        state[gid][wk] = {"completed": [], "absent": [], "thread_id": None, "notified": False}

    week_state = state[gid][wk]

    if sheet_name in week_state.get("completed", []):
        week_state["completed"].remove(sheet_name)
    if sheet_name not in week_state.get("absent", []):
        week_state["absent"].append(sheet_name)
    set_absence(guild_id, sheet_name)

    week_state[f"time_{sheet_name}"] = datetime.now(KST).isoformat()
    save_state(state)
    return week_state




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


async def _weekly_channel_cleanup(bot: commands.Bot, guild: discord.Guild):
    """주차가 바뀔 때마다 공지/레이드편성/일정조회 채널을 자동으로 청소하고 패널을 새로 표시."""
    targets = [
        (CH_NOTICE, "NoticeCog", "send_notice_panel"),
        (CH_PARTY, "PartyCog", "send_party_panel"),
        (CH_SCHEDULE, "ScheduleViewCog", "send_schedule_panel"),
    ]
    for channel_key, cog_name, repost_method in targets:
        channel = get_channel(guild, channel_key)
        if not channel:
            continue
        try:
            await _purge_channel(channel)
            cog = bot.cogs.get(cog_name)
            if cog:
                await getattr(cog, repost_method)(channel)
        except Exception as e:
            print(f"[notice] 주간 자동 청소 실패 ({channel_key}): {e}")


# ==================== NoticeCog ====================

class NoticeCog(commands.Cog, name="NoticeCog"):

    def __init__(self, bot):
        self.bot = bot
        bot.add_view(NoticePanelView())
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
                f"1. `/주간일정설정`으로 개인 링크 받기\n"
                f"2. 웹에서 가능한 시간 입력하고 저장 (완료 처리 자동)\n\n"
                f"⏰ **24시간 내 미응답 시 재알림**\n"
                f"⏰ **재알림 후 2시간 내 무응답 시 자동 불참 처리**"
            ),
            color=0x5865F2
        )
        embed.set_footer(text=f"요청자: {interaction.user.display_name}")

        msg = await notice_ch.send(embed=embed)

        # 스레드 생성
        thread = await msg.create_thread(
            name=f"{wk} 일정 입력",
            auto_archive_duration=10080  # 7일
        )

        await thread.send("`/주간일정설정`으로 개인 링크를 받아서 이번 주 가능시간을 입력해주세요!")

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
            value="• 일정 입력 요청이 오면 `/주간일정설정`으로 개인 링크 받아서 제출",
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

            if guild_state.get("_last_cleanup_week") != wk:
                await _weekly_channel_cleanup(self.bot, guild)
                guild_state["_last_cleanup_week"] = wk
                state[gid] = guild_state
                save_state(state)

            suggest_cog = self.bot.cogs.get("SuggestCog")
            if suggest_cog:
                await suggest_cog.monthly_cleanup_if_needed(guild)

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

            # 웹(가능시간 제출 페이지)에서 완료 처리됐을 수도 있으니, 리마인드 여부와 무관하게
            # 매 주기(최대 10분)마다 스레드 현황을 최신화하고 전원완료 체크도 같이 해준다.
            await _update_thread_status(guild, wk, week_state)
            await _check_all_complete(guild, wk, week_state)

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

    @app_commands.command(name="닉네임등록", description="내 닉네임을 등록합니다")
    async def link_sheet(self, interaction: discord.Interaction):
        await _start_nickname_registration(interaction)


# ==================== 닉네임 등록 ====================

async def _start_nickname_registration(interaction: discord.Interaction):
    """관리자가 엑셀로 미리 올려둔 미청구 명단이 있으면 거기서 고르게 하고,
    없으면 바로 직접 입력 모달을 띄운다."""
    pending = get_pending_members(interaction.guild_id)
    if pending:
        view = ClaimNicknameView(
            guild_id=interaction.guild_id, user_id=interaction.user.id,
            display_name=interaction.user.display_name, pending=pending,
        )
        await interaction.response.send_message(
            "**명단에서 본인 이름을 선택**하거나, 목록에 없으면 아래 버튼으로 직접 입력해주세요:",
            view=view, ephemeral=True,
        )
    else:
        modal = NicknameModal(guild_id=interaction.guild_id, user_id=interaction.user.id, display_name=interaction.user.display_name)
        await interaction.response.send_modal(modal)


class ClaimNicknameView(discord.ui.View):
    """관리자가 엑셀로 올려둔 미청구 명단에서 본인 이름을 골라 연결."""

    def __init__(self, guild_id: int, user_id: int, display_name: str, pending: list[dict]):
        super().__init__(timeout=60)
        self.guild_id = guild_id
        self.user_id = user_id
        self.display_name = display_name

        options = [discord.SelectOption(label=p["nickname"], value=p["nickname"]) for p in pending[:25]]
        select = discord.ui.Select(placeholder="명단에서 본인 이름 선택", options=options)
        select.callback = self.on_select
        self.add_item(select)

        manual_btn = discord.ui.Button(label="📝 목록에 없어요 (직접 입력)", style=discord.ButtonStyle.secondary)
        manual_btn.callback = self.on_manual
        self.add_item(manual_btn)

    async def on_select(self, interaction: discord.Interaction):
        nickname = interaction.data["values"][0]
        ok = claim_pending_member(self.guild_id, self.user_id, nickname)
        if ok:
            await interaction.response.edit_message(
                content=f"✅ **{self.display_name}** → **{nickname}**(으)로 연결되었습니다!", view=None
            )
        else:
            await interaction.response.edit_message(
                content="❌ 이미 다른 사람이 선택했거나 목록에서 사라졌습니다. `/닉네임등록`을 다시 실행해주세요.", view=None
            )

    async def on_manual(self, interaction: discord.Interaction):
        modal = NicknameModal(guild_id=self.guild_id, user_id=self.user_id, display_name=self.display_name)
        await interaction.response.send_modal(modal)


# ==================== 닉네임 등록 모달 ====================

class NicknameModal(discord.ui.Modal, title="닉네임 등록"):
    """길드 내 식별에 쓰이는 닉네임(sheet_name)과, 원정대 API 조회용 실제 캐릭터명을 등록."""

    nickname = discord.ui.TextInput(
        label="본인 닉네임 (길드에서 쓰는 이름)",
        placeholder="예: 거니",
        required=True,
        max_length=30,
    )
    character_name = discord.ui.TextInput(
        label="실제 로스트아크 캐릭터명 (선택)",
        placeholder="비워두면 닉네임을 그대로 사용합니다",
        required=False,
        max_length=30,
    )

    def __init__(self, guild_id: int, user_id: int, display_name: str):
        super().__init__()
        self.guild_id = guild_id
        self.user_id = user_id
        self.display_name = display_name
        self.nickname.default = display_name

    async def on_submit(self, interaction: discord.Interaction):
        from bot.utils.member_link import set_sheet_name, set_main_character
        nick = self.nickname.value.strip()
        if not nick:
            await interaction.response.send_message("❌ 닉네임을 입력해주세요.", ephemeral=True)
            return
        set_sheet_name(self.guild_id, self.user_id, nick)

        char = (self.character_name.value or "").strip()
        if char:
            set_main_character(self.guild_id, self.user_id, char)

        msg = f"✅ **{self.display_name}** → **{nick}**(으)로 등록되었습니다!"
        if char:
            msg += f"\n대표 캐릭터: **{char}** (원정대 캐릭터 조회에 사용됩니다)"
        await interaction.response.send_message(msg, ephemeral=True)


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
        label="이번주 일정 현황",
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
        label="내 닉네임 등록",
        style=discord.ButtonStyle.primary,
        custom_id="notice_link_sheet",
        row=1
    )
    async def link_sheet(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _start_nickname_registration(interaction)

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
        label="🌐 웹 대시보드",
        style=discord.ButtonStyle.secondary,
        custom_id="notice_dashboard_home",
        row=1
    )
    async def dashboard_home(self, interaction: discord.Interaction, button: discord.ui.Button):
        from bot.config.settings import WEB_BASE_URL
        from bot.utils.guild_url import get_url_name, sync_guild_name
        url_name = get_url_name(interaction.guild_id)
        if not url_name:
            sync_guild_name(interaction.guild_id, interaction.guild.name)
            url_name = get_url_name(interaction.guild_id)
        url = f"{WEB_BASE_URL.rstrip('/')}/{url_name}/홈"
        view = discord.ui.View()
        view.add_item(discord.ui.Button(label="🌐 대시보드 열기", style=discord.ButtonStyle.link, url=url))
        await interaction.response.send_message(view=view, ephemeral=True)

    @discord.ui.button(
        label="🧹 채널 청소",
        style=discord.ButtonStyle.danger,
        custom_id="notice_purge",
        row=1
    )
    async def purge_channel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await require_admin(interaction): return
        await interaction.response.defer(ephemeral=True)
        channel = interaction.channel
        try:
            wk = week_key()
            gid = str(interaction.guild_id)
            active_msg_id = load_state().get(gid, {}).get(wk, {}).get("message_id")
            deleted = await _purge_channel(channel, skip_ids={active_msg_id} if active_msg_id else None)

            notice_cog = interaction.client.cogs.get("NoticeCog")
            if notice_cog:
                await notice_cog.send_notice_panel(channel)

            await interaction.followup.send(
                f"🧹 **{deleted}개** 메시지 삭제 후 패널을 새로 표시했습니다.",
                ephemeral=True
            )
        except Exception as e:
            print(f"[notice] 청소 실패: {e}")
            await interaction.followup.send("❌ 채널 청소에 실패했습니다. 잠시 후 다시 시도해주세요.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(NoticeCog(bot))