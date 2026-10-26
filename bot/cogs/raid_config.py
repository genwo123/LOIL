"""
로일(LoIl) - 레이드 설정 Cog
⚔️│레이드설정 채널 전용

기능:
- 레이드 카탈로그 활성/비활성 토글
- 소요시간 조정
- 변경사항 guild_settings.json 저장

파티(공대) 수는 더 이상 여기서 미리 정하지 않는다 — 🛡│레이드편성에서 레이드를
등록하면 일단 공대 1개가 "미정" 상태로 생기고, 실제로 갈 사람이 모이면(웹 개인
가능시간 페이지의 참가 신청 수 기준) 공대를 늘리는 방식으로 바뀜.

UI 구조 (단일 ephemeral 메시지, edit_message):
  Row 0: [그림자] [카제로스] [군단장] [어비스] [에픽]  ← 카테고리 탭
  Row 1: [드롭다운: 레이드 선택 ▼]                    ← 선택한 카테고리 레이드
  Row 2: [활성/비활성] [소요시간 ▼]                   ← 선택한 레이드 설정
  Row 3: [✅ 저장·시트반영] [닫기]
"""

import discord
from discord.ext import commands
from discord import app_commands
import json
import os

from bot.utils.permissions import require_admin
from bot.utils.sheets import RAID_LEVEL_MAP, CATEGORIES, get_raid_size, get_raid_default_duration
from bot.utils.storage import load_settings, save_settings
from bot.config.channels import CH_RAID_CONFIG, get_channel

# ==================== 카테고리 정의 ====================

CAT_INFO = {
    "0": {"name": "어비스",   "emoji": "🟢", "label": "어비스"},
    "1": {"name": "군단장",   "emoji": "🟣", "label": "군단장"},
    "2": {"name": "에픽",     "emoji": "🔵", "label": "에픽"},
    "3": {"name": "카제로스", "emoji": "🟠", "label": "카제로스"},
    "4": {"name": "그림자",   "emoji": "🔴", "label": "그림자"},
}

DUR_OPTIONS = [
    discord.SelectOption(label="30분",      value="30"),
    discord.SelectOption(label="1시간",     value="60"),
    discord.SelectOption(label="1시간 30분", value="90"),
    discord.SelectOption(label="2시간",     value="120"),
]

def _dur_label(minutes: int) -> str:
    if minutes >= 60:
        h, m = minutes // 60, minutes % 60
        return f"{h}시간" if m == 0 else f"{h}시간 {m}분"
    return f"{minutes}분"


# ==================== 설정 로드/저장 ====================

def get_raid_config(guild_id: int) -> dict:
    """
    길드별 레이드 설정 반환
    구조: {"세르카_나이트메어": {"active": True, "slots": 5, "duration": 60}, ...}
    """
    return load_settings().get(str(guild_id), {}).get("raid_config", {})

def save_raid_config(guild_id: int, config: dict):
    settings = load_settings()
    gid = str(guild_id)
    if gid not in settings:
        settings[gid] = {}
    settings[gid]["raid_config"] = config
    save_settings(settings)


def get_trai_status(guild_id: int) -> dict:
    """이번 주 '트라이(진행 중/미클리어)' 표시된 레이드 목록.
    구조: {"카멘 하드": {"priority": "high"}, ...} — 키는 시트에 실제 적히는 '레이드명 난이도' 문자열.
    Google Sheets 스키마는 건드리지 않고 guild_settings.json에만 저장한다."""
    return load_settings().get(str(guild_id), {}).get("trai_status", {})


def set_trai_status(guild_id: int, raid_full_name: str, trai: bool, priority: str = "high"):
    settings = load_settings()
    gid = str(guild_id)
    if gid not in settings:
        settings[gid] = {}
    status = settings[gid].get("trai_status", {})
    if trai:
        status[raid_full_name] = {"priority": priority}
    else:
        status.pop(raid_full_name, None)
    settings[gid]["trai_status"] = status
    save_settings(settings)


TIME_POLICY_DAYS = ['수', '목', '금', '토', '일', '월', '화']


def get_time_policy(guild_id: int) -> dict:
    """길드 단위 요일별 허용 시간대(0~24시). 길드장/총무가 설정, 설정 안 한 요일은 기본 0~24(제한 없음).
    구조: {"수": {"start": 20, "end": 24}, ...} — 야행성 파티가 있는 길드는 특정 요일만 늦게 열어둘 수 있음."""
    saved = load_settings().get(str(guild_id), {}).get("time_policy", {})
    return {day: saved.get(day, {"start": 0, "end": 24}) for day in TIME_POLICY_DAYS}


def set_time_policy(guild_id: int, policy: dict):
    settings = load_settings()
    gid = str(guild_id)
    if gid not in settings:
        settings[gid] = {}
    settings[gid]["time_policy"] = policy
    save_settings(settings)


def get_time_granularity(guild_id: int) -> int:
    """개인 가능시간 그리드 기본 단위(분) — 길드장이 지정, 기본값 60분(1시간 단위).
    30을 지정하면 길드원이 페이지를 열 때부터 30분 단위 그리드로 시작(그래도 개인이 그때그때 토글 가능)."""
    return load_settings().get(str(guild_id), {}).get("time_granularity", 60)


def set_time_granularity(guild_id: int, minutes: int):
    settings = load_settings()
    gid = str(guild_id)
    if gid not in settings:
        settings[gid] = {}
    settings[gid]["time_granularity"] = 30 if minutes == 30 else 60
    save_settings(settings)


def _raid_key(raid_name: str, diff: str) -> str:
    """저장 키 생성: "세르카_나이트메어" """
    return f"{raid_name}_{diff}"

def get_raids_by_category(cat_id: str) -> list[dict]:
    """카테고리 ID로 레이드 목록 반환 (레벨 내림차순)"""
    raids = []
    for raid_name, diffs in RAID_LEVEL_MAP.items():
        for diff, info in diffs.items():
            if str(info.get("category", -1)) == cat_id:
                raids.append({
                    "raid_name": raid_name,
                    "diff":      diff,
                    "key":       _raid_key(raid_name, diff),
                    "ilvl":      info["ilvl"],
                    "size":      info["size"],
                    "duration":  info["duration"],
                })
    raids.sort(key=lambda r: r["ilvl"], reverse=True)
    return raids


def get_active_raids(guild_id: int) -> list[dict]:
    """활성화된 레이드 목록 반환 (레벨 내림차순) — 🛡│레이드편성 /일정추가 드롭다운에서 사용
    각 항목: {key, raid_name, diff, ilvl, size, duration, slots}
    duration은 관리자가 ⚔️│레이드설정에서 조정한 값을 우선 사용, 없으면 raid_data.json 기본값."""
    config = get_raid_config(guild_id)
    raids = []
    for raid_name, diffs in RAID_LEVEL_MAP.items():
        for diff, info in diffs.items():
            key = _raid_key(raid_name, diff)
            cfg = config.get(key)
            if not cfg or not cfg.get("active"):
                continue
            raids.append({
                "key":       key,
                "raid_name": raid_name,
                "diff":      diff,
                "ilvl":      info["ilvl"],
                "size":      info["size"],
                "duration":  cfg.get("duration", info["duration"]),
                "slots":     cfg.get("slots", 1),
            })
    raids.sort(key=lambda r: r["ilvl"], reverse=True)
    return raids


# ==================== 메인 View ====================

class RaidConfigView(discord.ui.View):
    """레이드 설정 메인 View — 단일 ephemeral 메시지에서 edit_message로 업데이트"""

    def __init__(self, guild_id: int, cat_id: str = "4", selected_key: str = None):
        super().__init__(timeout=180)
        self.guild_id     = guild_id
        self.cat_id       = cat_id       # 현재 선택된 카테고리
        self.selected_key = selected_key # 현재 선택된 레이드 키
        self.config       = get_raid_config(guild_id)
        self._build()

    def _build(self):
        """버튼/셀렉트 구성"""
        self.clear_items()

        # ── Row 0: 카테고리 탭 ──
        for cat_id, info in CAT_INFO.items():
            is_active = (cat_id == self.cat_id)
            btn = discord.ui.Button(
                label=info["label"],
                style=discord.ButtonStyle.primary if is_active else discord.ButtonStyle.secondary,
                custom_id=f"rc_cat_{cat_id}",
                row=0,
            )
            btn.callback = self._make_cat_callback(cat_id)
            self.add_item(btn)

        # ── Row 1: 레이드 드롭다운 ──
        raids = get_raids_by_category(self.cat_id)
        if raids:
            options = []
            for r in raids[:25]:
                cfg     = self.config.get(r["key"], {})
                active  = cfg.get("active", False)
                dur     = cfg.get("duration", r["duration"])
                icon    = "✅" if active else "○"
                options.append(discord.SelectOption(
                    label=f"{icon}  {r['raid_name']} {r['diff']}  ·  {r['size']}인  ·  {_dur_label(dur)}",
                    value=r["key"],
                    default=(r["key"] == self.selected_key),
                ))
            select = discord.ui.Select(
                placeholder="레이드를 선택하세요",
                options=options,
                custom_id="rc_raid_select",
                row=1,
            )
            select.callback = self._on_raid_select
            self.add_item(select)

        # ── Row 2: 선택된 레이드 컨트롤 ──
        if self.selected_key:
            cfg    = self.config.get(self.selected_key, {})
            active = cfg.get("active", False)
            dur    = cfg.get("duration", 60)

            # 활성/비활성 토글
            toggle_btn = discord.ui.Button(
                label="✅ 활성" if active else "○ 비활성",
                style=discord.ButtonStyle.success if active else discord.ButtonStyle.secondary,
                custom_id="rc_toggle",
                row=2,
            )
            toggle_btn.callback = self._on_toggle
            self.add_item(toggle_btn)

            # 소요시간 셀렉트
            dur_options = []
            for opt in DUR_OPTIONS:
                new_opt = discord.SelectOption(
                    label=opt.label,
                    value=opt.value,
                    default=(int(opt.value) == dur),
                )
                dur_options.append(new_opt)
            dur_select = discord.ui.Select(
                placeholder="소요시간",
                options=dur_options,
                custom_id="rc_dur_select",
                row=3,
            )
            dur_select.callback = self._on_dur
            self.add_item(dur_select)

            # ── Row 4: 저장/닫기 ──
            save_btn = discord.ui.Button(
                label="✅ 저장 · 시트 반영",
                style=discord.ButtonStyle.success,
                custom_id="rc_save",
                row=4,
            )
            save_btn.callback = self._on_save
            self.add_item(save_btn)

            close_btn = discord.ui.Button(
                label="닫기",
                style=discord.ButtonStyle.secondary,
                custom_id="rc_close",
                row=4,
            )
            close_btn.callback = self._on_close
            self.add_item(close_btn)
        else:
            # 레이드 미선택 시 저장/닫기만
            close_btn = discord.ui.Button(
                label="닫기",
                style=discord.ButtonStyle.secondary,
                custom_id="rc_close",
                row=4,
            )
            close_btn.callback = self._on_close
            self.add_item(close_btn)

    def _make_cat_callback(self, cat_id: str):
        async def callback(interaction: discord.Interaction):
            self.cat_id       = cat_id
            self.selected_key = None
            self._build()
            await interaction.response.edit_message(
                embed=self._build_embed(),
                view=self,
            )
        return callback

    async def _on_raid_select(self, interaction: discord.Interaction):
        self.selected_key = interaction.data["values"][0]
        # 선택된 레이드의 기본 소요시간 초기화 (처음 선택 시)
        if self.selected_key not in self.config:
            raids = get_raids_by_category(self.cat_id)
            raid  = next((r for r in raids if r["key"] == self.selected_key), None)
            if raid:
                self.config[self.selected_key] = {
                    "active":   False,
                    "slots":    1,
                    "duration": raid["duration"],
                }
        self._build()
        await interaction.response.edit_message(
            embed=self._build_embed(),
            view=self,
        )

    async def _on_toggle(self, interaction: discord.Interaction):
        if not self.selected_key:
            return
        cfg = self.config.setdefault(self.selected_key, {"active": False, "slots": 1, "duration": 60})
        cfg["active"] = not cfg.get("active", False)
        self._build()
        await interaction.response.edit_message(
            embed=self._build_embed(),
            view=self,
        )

    async def _on_dur(self, interaction: discord.Interaction):
        if not self.selected_key:
            return
        dur = int(interaction.data["values"][0])
        cfg = self.config.setdefault(self.selected_key, {"active": False, "slots": 1, "duration": 60})
        cfg["duration"] = dur
        self._build()
        await interaction.response.edit_message(
            embed=self._build_embed(),
            view=self,
        )

    async def _on_save(self, interaction: discord.Interaction):
        save_raid_config(self.guild_id, self.config)
        await interaction.response.edit_message(
            embed=self._build_embed(saved=True),
            view=self,
        )

    async def _on_close(self, interaction: discord.Interaction):
        await interaction.response.edit_message(
            content="✅ 레이드 설정 창을 닫았습니다.",
            embed=None,
            view=None,
        )

    def _build_embed(self, saved: bool = False) -> discord.Embed:
        cat_name = CAT_INFO[self.cat_id]["name"]

        if saved:
            embed = discord.Embed(
                title="⚔️ 레이드 설정",
                description="✅ 저장 완료! 다음 **/일정추가**부터 이 설정이 반영됩니다.",
                color=0x57f287,
            )
        else:
            embed = discord.Embed(
                title="⚔️ 레이드 카탈로그 설정",
                description=(
                    f"**{cat_name}** 카테고리 · 레이드를 선택해 활성/슬롯/소요시간을 설정하세요.\n"
                    "활성화된 레이드만 🛡│레이드편성 일정 추가에 표시됩니다."
                ),
                color=0x5865f2,
            )

        # 선택된 레이드 정보 표시
        if self.selected_key:
            cfg    = self.config.get(self.selected_key, {})
            active = cfg.get("active", False)
            slots  = cfg.get("slots", 1)
            dur    = cfg.get("duration", 60)

            raids = get_raids_by_category(self.cat_id)
            raid  = next((r for r in raids if r["key"] == self.selected_key), None)
            if raid:
                embed.add_field(
                    name="선택된 레이드",
                    value=(
                        f"**{raid['raid_name']} {raid['diff']}**\n"
                        f"{raid['size']}인 · 최소 {raid['ilvl']}\n"
                        f"상태: {'✅ 활성' if active else '○ 비활성'} · {slots}슬롯 · {_dur_label(dur)}"
                    ),
                    inline=False,
                )

        # 현재 카테고리 활성 레이드 요약
        raids_in_cat = get_raids_by_category(self.cat_id)
        active_list  = [
            f"• {r['raid_name']} {r['diff']} × {self.config.get(r['key'], {}).get('slots', 1)}슬롯"
            for r in raids_in_cat
            if self.config.get(r["key"], {}).get("active", False)
        ]
        if active_list:
            embed.add_field(
                name=f"✅ {cat_name} 활성 레이드",
                value="\n".join(active_list),
                inline=False,
            )
        else:
            embed.add_field(
                name=f"{cat_name} 활성 레이드",
                value="없음 (아래에서 활성화하세요)",
                inline=False,
            )

        embed.set_footer(text="저장 버튼을 누르면 다음 /일정추가부터 이 설정(활성/슬롯/소요시간)이 반영됩니다")
        return embed


# ==================== 고정 패널 View ====================

class RaidConfigPanelView(discord.ui.View):
    """채널에 고정되는 패널"""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="⚙️ 레이드 설정",
        style=discord.ButtonStyle.primary,
        custom_id="rcp_open",
        row=0,
    )
    async def open_config(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await require_admin(interaction):
            return
        view  = RaidConfigView(guild_id=interaction.guild_id)
        embed = view._build_embed()
        await interaction.response.send_message(
            embed=embed,
            view=view,
            ephemeral=True,
        )


# ==================== RaidConfigCog ====================

class RaidConfigCog(commands.Cog, name="RaidConfigCog"):

    def __init__(self, bot):
        self.bot = bot
        self.bot.add_view(RaidConfigPanelView())

    async def send_raid_config_panel(self, channel: discord.TextChannel):
        """채널에 고정 패널 전송"""
        await channel.purge(limit=50, check=lambda m: m.author == channel.guild.me)

        embed = discord.Embed(
            title="⚔️ 레이드 카탈로그 관리",
            description=(
                "길드가 운영할 레이드와 슬롯 수를 설정합니다.\n"
                "활성화된 레이드만 **🛡│레이드편성 /일정추가**의 선택 목록에 표시됩니다.\n\n"
                "슬롯 수만큼 파티를 한 번에 등록할 수 있어요 (예: 3슬롯 → 세르카(나이트메어)1·2·3)."
            ),
            color=0x5865f2,
        )
        embed.add_field(
            name="카테고리",
            value="🟢 어비스 · 🟣 군단장 · 🔵 에픽 · 🟠 카제로스 · 🔴 그림자",
            inline=False,
        )
        embed.set_footer(text="관리자 전용 채널")

        view = RaidConfigPanelView()
        msg  = await channel.send(embed=embed, view=view)
        try:
            await msg.pin()
        except Exception:
            pass
        return msg

    @app_commands.command(name="레이드설정패널", description="레이드 설정 패널을 생성합니다 (관리자)")
    async def spawn_panel(self, interaction: discord.Interaction):
        if not await require_admin(interaction):
            return
        ch = get_channel(interaction.guild, CH_RAID_CONFIG)
        if not ch:
            await interaction.response.send_message(
                "❌ ⚔️│레이드설정 채널을 찾을 수 없습니다.", ephemeral=True
            )
            return
        await interaction.response.defer(ephemeral=True)
        await self.send_raid_config_panel(ch)
        await interaction.followup.send("✅ 레이드 설정 패널이 생성되었습니다.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(RaidConfigCog(bot))