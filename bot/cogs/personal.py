"""
로일(LoIl) - 개인일정 Cog
🧾│개인일정 채널 상시 패널

기능:
- 내 시트 연결하기 (최초 1회)
- 내 일정 보기 (시트 개인 탭 이미지)
- 이번주 불참 신청 / 취소
"""

import discord
from discord.ext import commands
from discord import app_commands

from bot.utils.member_link import (
    get_sheet_name, set_sheet_name, is_linked,
    set_absence, remove_absence, is_absent, get_absences
)
from bot.config.channels import CH_PERSONAL, get_channel
from bot.cogs.setup import get_guild_setting


# ==================== 시트 연결 Modal ====================

class LinkSheetModal(discord.ui.Modal, title="내 시트 탭 연결"):
    sheet_name = discord.ui.TextInput(
        label="시트에서 본인 탭 이름",
        placeholder="예: 거니  (구글 시트 하단 탭 이름과 동일하게)",
        style=discord.TextStyle.short,
        min_length=1,
        max_length=30,
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        name = self.sheet_name.value.strip()
        set_sheet_name(interaction.guild_id, interaction.user.id, name)

        embed = discord.Embed(
            title="연결 완료!",
            description=(
                f"**{interaction.user.display_name}** 님의 시트 탭이 연결되었습니다.\n\n"
                f"시트 탭: **{name}**\n\n"
                "이제 일정 확인, 불참 신청 등을 바로 사용할 수 있어요!"
            ),
            color=0x57F287
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


# ==================== 개인일정 패널 View ====================

class PersonalPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="내 시트 연결하기",
        style=discord.ButtonStyle.primary,
        custom_id="personal_link",
        row=0
    )
    async def link_sheet(self, interaction: discord.Interaction, button: discord.ui.Button):
        current = get_sheet_name(interaction.guild_id, interaction.user.id)
        modal = LinkSheetModal()
        if current:
            modal.sheet_name.default = current
        await interaction.response.send_modal(modal)

    @discord.ui.button(
        label="내 일정 보기",
        style=discord.ButtonStyle.secondary,
        custom_id="personal_schedule",
        row=0
    )
    async def view_schedule(self, interaction: discord.Interaction, button: discord.ui.Button):
        sheet_name = get_sheet_name(interaction.guild_id, interaction.user.id)
        if not sheet_name:
            await interaction.response.send_message(
                "먼저 **내 시트 연결하기** 버튼으로 시트 탭을 연결해주세요!",
                ephemeral=True
            )
            return

        sheet_url = get_guild_setting(interaction.guild_id).get("sheet_url", "")
        if not sheet_url:
            await interaction.response.send_message(
                "시트가 연동되지 않았습니다. ⚙│봇설정 채널에서 먼저 설정해주세요.",
                ephemeral=True
            )
            return

        # 시트 개인 탭 직접 링크 생성
        # URL: .../spreadsheets/d/ID/edit#gid=... 형태지만
        # 탭 이름으로 바로 가는 링크는 불가 → 시트 링크 + 안내
        absence_status = "이번주 불참 신청됨" if is_absent(interaction.guild_id, sheet_name) else "참가 예정"

        embed = discord.Embed(
            title=f"{sheet_name} 님의 이번주 일정",
            description=f"상태: **{absence_status}**",
            color=0x5865F2
        )
        embed.add_field(
            name="시트에서 확인",
            value=f"[개인 일정 시트 열기]({sheet_url})\n탭 이름: **{sheet_name}**",
            inline=False
        )
        embed.set_footer(text="시트에서 직접 일정을 입력/수정할 수 있습니다")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(
        label="이번주 불참 신청",
        style=discord.ButtonStyle.danger,
        custom_id="personal_absence",
        row=1
    )
    async def absence_request(self, interaction: discord.Interaction, button: discord.ui.Button):
        sheet_name = get_sheet_name(interaction.guild_id, interaction.user.id)
        if not sheet_name:
            await interaction.response.send_message(
                "먼저 **내 시트 연결하기** 버튼으로 시트 탭을 연결해주세요!",
                ephemeral=True
            )
            return

        if is_absent(interaction.guild_id, sheet_name):
            await interaction.response.send_message(
                f"이미 이번주 불참 신청이 되어 있어요.\n취소하려면 **불참 취소** 버튼을 눌러주세요.",
                ephemeral=True
            )
            return

        set_absence(interaction.guild_id, sheet_name)

        embed = discord.Embed(
            title="이번주 불참 신청 완료",
            description=(
                f"**{sheet_name}** 님이 이번주 레이드에서 제외됩니다.\n"
                "파티 편성 시 자동으로 제외돼요!"
            ),
            color=0xED4245
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(
        label="불참 취소",
        style=discord.ButtonStyle.success,
        custom_id="personal_absence_cancel",
        row=1
    )
    async def absence_cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        sheet_name = get_sheet_name(interaction.guild_id, interaction.user.id)
        if not sheet_name:
            await interaction.response.send_message(
                "먼저 **내 시트 연결하기** 버튼으로 시트 탭을 연결해주세요!",
                ephemeral=True
            )
            return

        if not is_absent(interaction.guild_id, sheet_name):
            await interaction.response.send_message(
                "이번주 불참 신청 내역이 없어요!",
                ephemeral=True
            )
            return

        remove_absence(interaction.guild_id, sheet_name)
        await interaction.response.send_message(
            f"불참이 취소되었습니다. **{sheet_name}** 님이 이번주 레이드에 참가합니다!",
            ephemeral=True
        )


# ==================== 개인일정 패널 임베드 ====================

def build_personal_panel_embed() -> discord.Embed:
    embed = discord.Embed(
        title="🧾 개인 일정",
        description=(
            "처음 사용하시면 **내 시트 연결하기**를 먼저 눌러주세요!\n"
            "시트 탭 이름과 연결하면 일정 확인과 불참 신청을 바로 할 수 있어요."
        ),
        color=0x9B59B6
    )
    embed.add_field(
        name="사용 순서",
        value=(
            "1. **내 시트 연결하기** — 최초 1회 시트 탭 이름 입력\n"
            "2. **내 일정 보기** — 이번주 내 레이드 일정 확인\n"
            "3. **이번주 불참 신청** — 이번주 참가 불가 시 신청\n"
            "4. **불참 취소** — 다시 참가 가능해졌을 때"
        ),
        inline=False
    )
    embed.set_footer(text="불참 신청은 매주 수요일 초기화됩니다")
    return embed


# ==================== PersonalCog ====================

class PersonalCog(commands.Cog, name="PersonalCog"):

    def __init__(self, bot):
        self.bot = bot
        self.panel_messages: dict[int, int] = {}
        bot.add_view(PersonalPanelView())

    async def send_personal_panel(self, channel: discord.TextChannel):
        embed = build_personal_panel_embed()
        view  = PersonalPanelView()
        msg   = await channel.send(embed=embed, view=view)
        try:
            await msg.pin()
        except Exception:
            pass
        self.panel_messages[channel.guild.id] = msg.id

    async def refresh_personal_panel(self, guild: discord.Guild):
        ch = get_channel(guild, CH_PERSONAL)
        if not ch:
            return

        embed  = build_personal_panel_embed()
        view   = PersonalPanelView()
        msg_id = self.panel_messages.get(guild.id)

        if msg_id:
            try:
                msg = await ch.fetch_message(msg_id)
                await msg.edit(embed=embed, view=view)
                return
            except Exception:
                pass

        try:
            pins = await ch.pins()
            for pin in pins:
                if pin.author == guild.me:
                    await pin.edit(embed=embed, view=view)
                    self.panel_messages[guild.id] = pin.id
                    return
        except Exception:
            pass

        await self.send_personal_panel(ch)

    @app_commands.command(name="개인일정패널", description="개인일정 패널을 표시합니다 (관리자)")
    async def personal_panel_cmd(self, interaction: discord.Interaction):
        from bot.utils.permissions import require_admin
        if not await require_admin(interaction): return
        ch = get_channel(interaction.guild, CH_PERSONAL)
        if not ch:
            await interaction.response.send_message("❌ 개인일정 채널이 없습니다.", ephemeral=True)
            return
        await self.send_personal_panel(ch)
        await interaction.response.send_message(f"✅ {ch.mention} 에 패널을 표시했습니다!", ephemeral=True)

    @app_commands.command(name="불참현황", description="이번주 불참자 목록을 확인합니다")
    async def absence_status(self, interaction: discord.Interaction):
        absences = get_absences(interaction.guild_id)
        if not absences:
            await interaction.response.send_message("이번주 불참 신청자가 없습니다!", ephemeral=True)
            return
        embed = discord.Embed(
            title="이번주 불참 신청자",
            description="\n".join([f"• {name}" for name in absences]),
            color=0xED4245
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(PersonalCog(bot))