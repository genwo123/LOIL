"""
로일(LoIl) - 설정 Cog v2
B+C+A 혼합형 패널:
- 상태 그리드 (C): 현재 연동 상태 카드 4개
- 스텝 가이드 (B): 순서별 완료/미완료 표시
- 스타일 선택 버튼 추가
- /설정확인 제거 (admin_v2에서도 제거됨)
"""

import discord
from discord.ext import commands
from discord import app_commands
import json
import os
from bot.config.settings import BOT_VERSION
from bot.config.channels import CH_SETUP, get_channel
from bot.utils.permissions import require_admin

# ==================== 설정 저장 ====================

SETTINGS_FILE = "bot/data/guild_settings.json"

def load_settings() -> dict:
    if not os.path.exists(SETTINGS_FILE):
        return {}
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_settings(data: dict):
    os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_guild_setting(guild_id: int) -> dict:
    return load_settings().get(str(guild_id), {})

def update_guild_setting(guild_id: int, key: str, value):
    settings = load_settings()
    guild_key = str(guild_id)
    if guild_key not in settings:
        settings[guild_key] = {}
    settings[guild_key][key] = value
    save_settings(settings)


# ==================== Modal 정의 ====================

class SheetUrlModal(discord.ui.Modal, title="📋 구글 시트 연동"):
    url = discord.ui.TextInput(
        label="구글 스프레드시트 URL",
        placeholder="https://docs.google.com/spreadsheets/d/...",
        style=discord.TextStyle.short,
        min_length=40,
        max_length=500,
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        url_value = self.url.value.strip()
        if "docs.google.com/spreadsheets" not in url_value:
            await interaction.response.send_message(
                "❌ 올바른 구글 시트 URL이 아닙니다!\n"
                "예시: `https://docs.google.com/spreadsheets/d/...`",
                ephemeral=True
            )
            return
        update_guild_setting(interaction.guild_id, "sheet_url", url_value)
        await interaction.response.send_message(
            "✅ 구글 시트 URL이 저장되었습니다!", ephemeral=True
        )
        setup_cog = interaction.client.cogs.get("SetupCog")
        if setup_cog:
            await setup_cog.refresh_setup_panel(interaction.guild)


class LoaApiKeyModal(discord.ui.Modal, title="🗝 로아 API 키 등록"):
    keys = discord.ui.TextInput(
        label="API 키 (최대 3개, 쉼표로 구분)",
        placeholder="key1,key2,key3",
        style=discord.TextStyle.paragraph,
        min_length=10,
        max_length=500,
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        raw      = self.keys.value.strip()
        key_list = [k.strip() for k in raw.split(",") if k.strip()]
        if not key_list:
            await interaction.response.send_message("❌ 유효한 키가 없습니다.", ephemeral=True)
            return
        if len(key_list) > 3:
            await interaction.response.send_message(
                "❌ API 키는 최대 3개까지 등록 가능합니다.", ephemeral=True
            )
            return
        update_guild_setting(interaction.guild_id, "loa_api_keys", ",".join(key_list))
        await interaction.response.send_message(
            f"✅ 로아 API 키 {len(key_list)}개가 저장되었습니다!", ephemeral=True
        )
        setup_cog = interaction.client.cogs.get("SetupCog")
        if setup_cog:
            await setup_cog.refresh_setup_panel(interaction.guild)


class GeminiApiKeyModal(discord.ui.Modal, title="🤖 Gemini API 키 등록"):
    key = discord.ui.TextInput(
        label="Gemini API 키",
        placeholder="AIza...",
        style=discord.TextStyle.short,
        min_length=10,
        max_length=200,
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        key_value = self.key.value.strip()
        if not key_value.startswith("AIza"):
            await interaction.response.send_message(
                "❌ 올바른 Gemini API 키가 아닙니다.\n"
                "Google AI Studio에서 발급한 키를 입력해주세요.",
                ephemeral=True
            )
            return
        update_guild_setting(interaction.guild_id, "gemini_api_key", key_value)
        await interaction.response.send_message(
            "✅ Gemini API 키가 저장되었습니다!", ephemeral=True
        )
        setup_cog = interaction.client.cogs.get("SetupCog")
        if setup_cog:
            await setup_cog.refresh_setup_panel(interaction.guild)


# ==================== 스타일 선택 View ====================

class StyleSelectView(discord.ui.View):
    """일정 스타일 선택 버튼"""

    def __init__(self):
        super().__init__(timeout=60)

    @discord.ui.button(label="B — 타임라인 (기본)", style=discord.ButtonStyle.primary, custom_id="style_b")
    async def style_b(self, interaction: discord.Interaction, button: discord.ui.Button):
        update_guild_setting(interaction.guild_id, "schedule_style", "B")
        await interaction.response.send_message(
            "✅ 일정 스타일이 **B — 타임라인**으로 설정되었습니다!", ephemeral=True
        )
        setup_cog = interaction.client.cogs.get("SetupCog")
        if setup_cog:
            await setup_cog.refresh_setup_panel(interaction.guild)

    @discord.ui.button(label="D — 다크카드", style=discord.ButtonStyle.secondary, custom_id="style_d")
    async def style_d(self, interaction: discord.Interaction, button: discord.ui.Button):
        update_guild_setting(interaction.guild_id, "schedule_style", "D")
        await interaction.response.send_message(
            "✅ 일정 스타일이 **D — 다크카드**로 설정되었습니다!", ephemeral=True
        )
        setup_cog = interaction.client.cogs.get("SetupCog")
        if setup_cog:
            await setup_cog.refresh_setup_panel(interaction.guild)


# ==================== 설정 패널 임베드 빌더 ====================

def build_setup_embed(guild_setting: dict) -> discord.Embed:
    """B+C+A 혼합형 설정 패널 임베드"""

    sheet_url    = guild_setting.get("sheet_url", "")
    loa_keys_raw = guild_setting.get("loa_api_keys", "")
    gemini_key   = guild_setting.get("gemini_api_key", "")
    style        = guild_setting.get("schedule_style", "B")

    loa_keys = [k for k in loa_keys_raw.split(",") if k.strip()] if loa_keys_raw else []

    sheet_ok  = bool(sheet_url)
    loa_ok    = bool(loa_keys)
    gemini_ok = bool(gemini_key)
    all_done  = sheet_ok and loa_ok

    color = 0x57F287 if all_done else 0x9B59B6

    embed = discord.Embed(
        title="⚙️ 로일 설정 패널",
        description=(
            "✅ **모든 설정 완료! 봇이 정상 운영 중입니다.**"
            if all_done else
            "아래 순서대로 설정하면 바로 사용할 수 있어요!\n"
            "*민감한 정보는 팝업창으로 안전하게 입력됩니다.*"
        ),
        color=color
    )

    # ── 상태 그리드 ──
    embed.add_field(
        name="📋 구글 시트",
        value=(f"✅ 연동됨\n[시트 열기]({sheet_url})" if sheet_ok else "❌ 미연동"),
        inline=True
    )
    embed.add_field(
        name="🗝 로아 API",
        value=(f"✅ {len(loa_keys)}개 등록" if loa_ok else "❌ 미등록"),
        inline=True
    )
    embed.add_field(
        name="🤖 Gemini API",
        value=("✅ 등록됨" if gemini_ok else "⚠️ 기본값 사용"),
        inline=True
    )
    embed.add_field(
        name="🎨 일정 스타일",
        value=f"{'B — 타임라인' if style == 'B' else 'D — 다크카드'}",
        inline=True
    )
    embed.add_field(name="\u200b", value="\u200b", inline=True)
    embed.add_field(name="\u200b", value="\u200b", inline=True)

    # ── 스텝 가이드 ──
    def step(done: bool, num: str, text: str, sub: str, optional: bool = False) -> str:
        if done:
            icon, status = "✅", "완료"
        elif optional:
            icon, status = "⚠️", "선택"
        else:
            icon, status = "⬜", "미완료"
        return f"{icon} **{num}. {text}** — {sub} `{status}`"

    guide = "\n".join([
        step(sheet_ok,  "1", "구글 시트 연동",      "시트 URL 등록"),
        step(loa_ok,    "2", "로아 API 키 등록",    "최대 3개 풀링"),
        step(gemini_ok, "3", "Gemini API 키 등록", "없으면 기본 키 사용", optional=True),
        step(True,      "4", "일정 스타일 선택",    f"현재: {'B — 타임라인' if style == 'B' else 'D — 다크카드'}"),
    ])
    embed.add_field(name="🚀 설정 가이드", value=guide, inline=False)

    if not all_done:
        embed.add_field(
            name="💡 도움말",
            value=(
                "• 로아 API 키 → [개발자 센터](https://developer-lostark.game.onstove.com/)\n"
                "• Gemini API 키 → [Google AI Studio](https://aistudio.google.com/)\n"
                "• 구글 시트 → `loli-sheet@loil-487100.iam.gserviceaccount.com` 편집자 공유 필요"
            ),
            inline=False
        )

    embed.set_footer(text=f"로일 v{BOT_VERSION} · 관리자만 설정 변경 가능 · 변경 즉시 반영")
    return embed


# ==================== 설정 패널 View ====================

class SetupPanelView(discord.ui.View):
    """설정 패널 버튼 (timeout=None → 영구)"""

    def __init__(self):
        super().__init__(timeout=None)

    # ── Row 0: 등록 버튼 ──

    @discord.ui.button(
        label="📋 시트 URL 등록",
        style=discord.ButtonStyle.primary,
        custom_id="setup_sheet_url",
        row=0
    )
    async def setup_sheet(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await require_admin(interaction): return
        await interaction.response.send_modal(SheetUrlModal())

    @discord.ui.button(
        label="🗝 API 키 등록",
        style=discord.ButtonStyle.primary,
        custom_id="setup_loa_key",
        row=0
    )
    async def setup_loa_key(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await require_admin(interaction): return
        await interaction.response.send_modal(LoaApiKeyModal())

    @discord.ui.button(
        label="🤖 Gemini 키 등록",
        style=discord.ButtonStyle.primary,
        custom_id="setup_gemini_key",
        row=0
    )
    async def setup_gemini_key(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await require_admin(interaction): return
        await interaction.response.send_modal(GeminiApiKeyModal())

    # ── Row 1: 스타일 + 유틸 버튼 ──

    @discord.ui.button(
        label="🎨 일정 스타일 선택",
        style=discord.ButtonStyle.secondary,
        custom_id="setup_style",
        row=1
    )
    async def select_style(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await require_admin(interaction): return
        await interaction.response.send_message(
            "🎨 **일정 스타일을 선택하세요**\n"
            "• **B — 타임라인**: 시간 흐름 직관적, 보기 편한 레이아웃\n"
            "• **D — 다크카드**: 고급스러운 느낌, 시간박스가 눈에 잘 띔",
            view=StyleSelectView(),
            ephemeral=True
        )

    @discord.ui.button(
        label="🔄 새로고침",
        style=discord.ButtonStyle.secondary,
        custom_id="setup_refresh",
        row=1
    )
    async def refresh(self, interaction: discord.Interaction, button: discord.ui.Button):
        setup_cog = interaction.client.cogs.get("SetupCog")
        if setup_cog:
            await setup_cog.refresh_setup_panel(interaction.guild)
        await interaction.response.send_message("🔄 설정 패널이 업데이트되었습니다!", ephemeral=True)

    @discord.ui.button(
        label="🗑 설정 초기화",
        style=discord.ButtonStyle.danger,
        custom_id="setup_reset",
        row=1
    )
    async def reset_settings(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await require_admin(interaction): return
        await interaction.response.send_message(
            "⚠️ 정말로 모든 설정을 초기화하시겠습니까?",
            view=ConfirmResetView(),
            ephemeral=True
        )


class ConfirmResetView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=30)

    @discord.ui.button(label="✅ 초기화 확인", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        settings  = load_settings()
        guild_key = str(interaction.guild_id)
        if guild_key in settings:
            del settings[guild_key]
            save_settings(settings)
        setup_cog = interaction.client.cogs.get("SetupCog")
        if setup_cog:
            await setup_cog.refresh_setup_panel(interaction.guild)
        await interaction.response.send_message("✅ 설정이 초기화되었습니다.", ephemeral=True)

    @discord.ui.button(label="❌ 취소", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("취소되었습니다.", ephemeral=True)


# ==================== SetupCog ====================

class SetupCog(commands.Cog, name="SetupCog"):

    def __init__(self, bot):
        self.bot = bot
        self.panel_messages: dict[int, int] = {}
        bot.add_view(SetupPanelView())

    async def send_setup_panel(self, channel: discord.TextChannel):
        guild_setting = get_guild_setting(channel.guild.id)
        embed = build_setup_embed(guild_setting)
        view  = SetupPanelView()
        msg   = await channel.send(embed=embed, view=view)
        try:
            await msg.pin()
        except Exception:
            pass
        self.panel_messages[channel.guild.id] = msg.id

    async def refresh_setup_panel(self, guild: discord.Guild):
        setup_channel = get_channel(guild, CH_SETUP)
        if not setup_channel:
            return

        guild_setting = get_guild_setting(guild.id)
        embed = build_setup_embed(guild_setting)
        view  = SetupPanelView()

        msg_id = self.panel_messages.get(guild.id)
        if msg_id:
            try:
                msg = await setup_channel.fetch_message(msg_id)
                await msg.edit(embed=embed, view=view)
                return
            except Exception:
                pass

        try:
            pins = await setup_channel.pins()
            for pin in pins:
                if pin.author == guild.me:
                    await pin.edit(embed=embed, view=view)
                    self.panel_messages[guild.id] = pin.id
                    return
        except Exception:
            pass

        await self.send_setup_panel(setup_channel)

    @app_commands.command(name="설정패널", description="설정 패널을 다시 표시합니다 (관리자)")
    async def setup_panel(self, interaction: discord.Interaction):
        if not await require_admin(interaction): return
        setup_ch = get_channel(interaction.guild, CH_SETUP)
        if not setup_ch:
            await interaction.response.send_message("❌ 설정 채널이 없습니다.", ephemeral=True)
            return
        await self.send_setup_panel(setup_ch)
        await interaction.response.send_message(
            f"✅ {setup_ch.mention} 에 설정 패널을 표시했습니다!", ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(SetupCog(bot))