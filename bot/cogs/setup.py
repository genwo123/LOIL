"""
로일(LoIl) - 설정 Cog
/설정 명령어 제거 → Modal + 버튼 UI로 교체

채널: ⚙️ 로일-설정
- 설정 상태판 고정 메시지
- 시트 URL / 로아 API 키 / Gemini API 키 Modal 입력
- 민감한 정보 채팅창 노출 없음
"""

import discord
from discord.ext import commands
from discord import app_commands
import json
import os
from bot.config.settings import BOT_VERSION

# ==================== 설정 저장 (JSON 임시 / 나중에 DB 교체) ====================

SETTINGS_FILE = "bot/data/guild_settings.json"

def load_settings() -> dict:
    """길드 설정 불러오기"""
    if not os.path.exists(SETTINGS_FILE):
        return {}
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_settings(data: dict):
    """길드 설정 저장"""
    os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_guild_setting(guild_id: int) -> dict:
    """특정 길드 설정 가져오기"""
    settings = load_settings()
    return settings.get(str(guild_id), {})

def update_guild_setting(guild_id: int, key: str, value: str):
    """특정 길드 설정 업데이트"""
    settings = load_settings()
    guild_key = str(guild_id)
    if guild_key not in settings:
        settings[guild_key] = {}
    settings[guild_key][key] = value
    save_settings(settings)


# ==================== Modal 정의 ====================

class SheetUrlModal(discord.ui.Modal, title="📊 구글 시트 연동"):
    """시트 URL 입력 Modal"""

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

        # URL 유효성 검사
        if "docs.google.com/spreadsheets" not in url_value:
            await interaction.response.send_message(
                "❌ 올바른 구글 시트 URL이 아닙니다!\n"
                "예시: `https://docs.google.com/spreadsheets/d/...`",
                ephemeral=True
            )
            return

        # 저장
        update_guild_setting(interaction.guild_id, "sheet_url", url_value)

        await interaction.response.send_message(
            "✅ 구글 시트 URL이 저장되었습니다!\n"
            "설정 상태판이 자동으로 업데이트됩니다.",
            ephemeral=True
        )

        # 설정 패널 갱신
        setup_cog = interaction.client.cogs.get("SetupCog")
        if setup_cog:
            await setup_cog.refresh_setup_panel(interaction.guild)


class LoaApiKeyModal(discord.ui.Modal, title="🔑 로아 API 키 등록"):
    """로아 API 키 입력 Modal"""

    key1 = discord.ui.TextInput(
        label="API 키 1 (필수)",
        placeholder="eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9...",
        style=discord.TextStyle.short,
        required=True,
        max_length=500
    )
    key2 = discord.ui.TextInput(
        label="API 키 2 (선택)",
        placeholder="두 번째 API 키 (없으면 비워두세요)",
        style=discord.TextStyle.short,
        required=False,
        max_length=500
    )
    key3 = discord.ui.TextInput(
        label="API 키 3 (선택)",
        placeholder="세 번째 API 키 (없으면 비워두세요)",
        style=discord.TextStyle.short,
        required=False,
        max_length=500
    )

    async def on_submit(self, interaction: discord.Interaction):
        keys = []
        for k in [self.key1.value, self.key2.value, self.key3.value]:
            k = k.strip()
            if k:
                keys.append(k)

        if not keys:
            await interaction.response.send_message(
                "❌ API 키를 최소 1개 이상 입력해주세요.",
                ephemeral=True
            )
            return

        # 저장 (쉼표로 구분)
        update_guild_setting(interaction.guild_id, "loa_api_keys", ",".join(keys))

        await interaction.response.send_message(
            f"✅ 로아 API 키 **{len(keys)}개**가 저장되었습니다!\n"
            "설정 상태판이 자동으로 업데이트됩니다.",
            ephemeral=True
        )

        # 설정 패널 갱신
        setup_cog = interaction.client.cogs.get("SetupCog")
        if setup_cog:
            await setup_cog.refresh_setup_panel(interaction.guild)


class GeminiApiKeyModal(discord.ui.Modal, title="✨ Gemini API 키 등록"):
    """Gemini API 키 입력 Modal"""

    key = discord.ui.TextInput(
        label="Gemini API 키",
        placeholder="AIzaSy...",
        style=discord.TextStyle.short,
        required=True,
        max_length=200
    )

    async def on_submit(self, interaction: discord.Interaction):
        key_value = self.key.value.strip()

        if not key_value.startswith("AIza"):
            await interaction.response.send_message(
                "❌ 올바른 Gemini API 키가 아닌 것 같습니다.\n"
                "`AIzaSy...` 형태의 키를 입력해주세요.",
                ephemeral=True
            )
            return

        # 저장
        update_guild_setting(interaction.guild_id, "gemini_api_key", key_value)

        await interaction.response.send_message(
            "✅ Gemini API 키가 저장되었습니다!\n"
            "설정 상태판이 자동으로 업데이트됩니다.",
            ephemeral=True
        )

        # 설정 패널 갱신
        setup_cog = interaction.client.cogs.get("SetupCog")
        if setup_cog:
            await setup_cog.refresh_setup_panel(interaction.guild)


# ==================== 설정 패널 버튼 View ====================

class SetupPanelView(discord.ui.View):
    """설정 패널 버튼들"""

    def __init__(self):
        super().__init__(timeout=None)

    async def _check_admin(self, interaction: discord.Interaction) -> bool:
        """관리자 권한 체크"""
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ 관리자만 설정을 변경할 수 있습니다.",
                ephemeral=True
            )
            return False
        return True

    @discord.ui.button(
        label="📊 시트 URL 등록",
        style=discord.ButtonStyle.primary,
        custom_id="setup_sheet_url",
        row=0
    )
    async def setup_sheet(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check_admin(interaction):
            return
        await interaction.response.send_modal(SheetUrlModal())

    @discord.ui.button(
        label="🔑 로아 API 키 등록",
        style=discord.ButtonStyle.primary,
        custom_id="setup_loa_key",
        row=0
    )
    async def setup_loa_key(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check_admin(interaction):
            return
        await interaction.response.send_modal(LoaApiKeyModal())

    @discord.ui.button(
        label="✨ Gemini 키 등록",
        style=discord.ButtonStyle.primary,
        custom_id="setup_gemini_key",
        row=0
    )
    async def setup_gemini_key(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check_admin(interaction):
            return
        await interaction.response.send_modal(GeminiApiKeyModal())

    @discord.ui.button(
        label="🔄 상태 새로고침",
        style=discord.ButtonStyle.secondary,
        custom_id="setup_refresh",
        row=1
    )
    async def refresh(self, interaction: discord.Interaction, button: discord.ui.Button):
        setup_cog = interaction.client.cogs.get("SetupCog")
        if setup_cog:
            await setup_cog.refresh_setup_panel(interaction.guild)
        await interaction.response.send_message(
            "🔄 상태판이 업데이트되었습니다!",
            ephemeral=True
        )

    @discord.ui.button(
        label="🗑️ 설정 초기화",
        style=discord.ButtonStyle.danger,
        custom_id="setup_reset",
        row=1
    )
    async def reset_settings(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check_admin(interaction):
            return
        await interaction.response.send_message(
            "⚠️ 정말로 모든 설정을 초기화하시겠습니까?\n"
            "확인하려면 아래 버튼을 눌러주세요.",
            view=ConfirmResetView(),
            ephemeral=True
        )


class ConfirmResetView(discord.ui.View):
    """설정 초기화 확인 버튼"""

    def __init__(self):
        super().__init__(timeout=30)

    @discord.ui.button(label="✅ 초기화 확인", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        settings = load_settings()
        guild_key = str(interaction.guild_id)
        if guild_key in settings:
            del settings[guild_key]
            save_settings(settings)

        setup_cog = interaction.client.cogs.get("SetupCog")
        if setup_cog:
            await setup_cog.refresh_setup_panel(interaction.guild)

        await interaction.response.send_message(
            "✅ 설정이 초기화되었습니다.",
            ephemeral=True
        )

    @discord.ui.button(label="❌ 취소", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("취소되었습니다.", ephemeral=True)


# ==================== 설정 임베드 빌더 ====================

def build_setup_embed(guild_setting: dict) -> discord.Embed:
    """설정 현황 임베드 생성"""

    sheet_url    = guild_setting.get("sheet_url", "")
    loa_keys_raw = guild_setting.get("loa_api_keys", "")
    gemini_key   = guild_setting.get("gemini_api_key", "")

    loa_keys = [k for k in loa_keys_raw.split(",") if k] if loa_keys_raw else []

    # 연동 상태
    sheet_status  = "🟢 연동됨" if sheet_url else "🔴 미연동"
    loa_status    = f"🟢 {len(loa_keys)}개 등록" if loa_keys else "🔴 미등록"
    gemini_status = "🟢 등록됨" if gemini_key else "🔴 미등록"

    # 전체 완료 여부
    all_done = bool(sheet_url and loa_keys and gemini_key)
    color = 0x57F287 if all_done else 0x5865F2

    embed = discord.Embed(
        title="⚙️ 로일 설정 센터",
        description=(
            "✅ **설정 완료! 봇이 정상 운영 중입니다.**" if all_done
            else "아래 버튼을 눌러 각 항목을 설정해주세요.\n*민감한 정보는 팝업창으로 안전하게 입력됩니다.*"
        ),
        color=color
    )

    # 시트 URL (일부만 표시)
    if sheet_url:
        short_url = sheet_url[:60] + "..." if len(sheet_url) > 60 else sheet_url
        embed.add_field(
            name="📊 구글 시트",
            value=f"{sheet_status}\n[시트 바로가기]({sheet_url})",
            inline=True
        )
    else:
        embed.add_field(name="📊 구글 시트", value=sheet_status, inline=True)

    # 로아 API 키
    embed.add_field(name="🔑 로아 API 키", value=loa_status, inline=True)

    # Gemini 키
    embed.add_field(name="✨ Gemini API", value=gemini_status, inline=True)

    # 체크리스트
    checklist = (
        f"{'✅' if sheet_url  else '⬜'} 구글 시트 연동\n"
        f"{'✅' if loa_keys   else '⬜'} 로아 API 키 등록\n"
        f"{'✅' if gemini_key else '⬜'} Gemini API 키 등록"
    )
    embed.add_field(name="📋 설정 체크리스트", value=checklist, inline=False)

    if not all_done:
        embed.add_field(
            name="💡 도움말",
            value=(
                "• 로아 API 키는 [개발자 센터](https://developer-lostark.game.onstove.com/)에서 발급\n"
                "• Gemini API 키는 [Google AI Studio](https://aistudio.google.com/)에서 발급\n"
                "• 구글 시트는 `loli-sheet@loil-487100.iam.gserviceaccount.com` 에 편집자 공유 필요"
            ),
            inline=False
        )

    embed.set_footer(text=f"로일(LoIl) v{BOT_VERSION} · 설정은 서버별로 독립 저장됩니다")
    return embed


# ==================== SetupCog ====================

class SetupCog(commands.Cog, name="SetupCog"):

    def __init__(self, bot):
        self.bot = bot
        # 설정 패널 메시지 ID 저장 {guild_id: message_id}
        self.panel_messages: dict[int, int] = {}
        # 버튼 View 영구 등록
        bot.add_view(SetupPanelView())

    # ── 설정 패널 전송 ──

    async def send_setup_panel(self, channel: discord.TextChannel):
        """설정 채널에 상태판 전송 (최초 1회)"""
        guild_setting = get_guild_setting(channel.guild.id)
        embed = build_setup_embed(guild_setting)
        view  = SetupPanelView()
        msg   = await channel.send(embed=embed, view=view)

        # 메시지 고정
        try:
            await msg.pin()
        except Exception:
            pass

        self.panel_messages[channel.guild.id] = msg.id

    # ── 설정 패널 갱신 ──

    async def refresh_setup_panel(self, guild: discord.Guild):
        """설정 변경 시 상태판 메시지 Edit으로 갱신"""
        setup_channel = discord.utils.get(guild.text_channels, name="로일-설정")
        if not setup_channel:
            return

        guild_setting = get_guild_setting(guild.id)
        embed = build_setup_embed(guild_setting)
        view  = SetupPanelView()

        # 저장된 메시지 ID로 Edit
        msg_id = self.panel_messages.get(guild.id)
        if msg_id:
            try:
                msg = await setup_channel.fetch_message(msg_id)
                await msg.edit(embed=embed, view=view)
                return
            except Exception:
                pass

        # 저장된 메시지가 없으면 고정 메시지에서 찾기
        try:
            pins = await setup_channel.pins()
            for pin in pins:
                if pin.author == guild.me:
                    await pin.edit(embed=embed, view=view)
                    self.panel_messages[guild.id] = pin.id
                    return
        except Exception:
            pass

        # 아예 없으면 새로 전송
        await self.send_setup_panel(setup_channel)

    # ── /설정패널 명령어 (수동으로 패널 다시 올리기) ──

    @app_commands.command(name="설정패널", description="설정 상태판을 다시 표시합니다 (관리자 전용)")
    @app_commands.checks.has_permissions(administrator=True)
    async def show_setup_panel(self, interaction: discord.Interaction):
        setup_channel = discord.utils.get(
            interaction.guild.text_channels, name="로일-설정"
        )
        if not setup_channel:
            await interaction.response.send_message(
                "❌ 로일-설정 채널이 없습니다. 봇을 다시 초대하거나 채널을 수동으로 만들어주세요.",
                ephemeral=True
            )
            return

        await self.send_setup_panel(setup_channel)
        await interaction.response.send_message(
            f"✅ {setup_channel.mention} 채널에 설정 패널을 표시했습니다!",
            ephemeral=True
        )

    @show_setup_panel.error
    async def setup_panel_error(self, interaction: discord.Interaction, error):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                "❌ 관리자만 사용할 수 있습니다.",
                ephemeral=True
            )


# ==================== Cog 등록 ====================

async def setup(bot):
    await bot.add_cog(SetupCog(bot))