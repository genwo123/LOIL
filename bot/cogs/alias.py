"""
로일(LoIl) - 별명 관리 Cog
- /별명추가: 직업/각인 별명 추가 요청
- 관리자 승인/거절 버튼
- guild_aliases.json 저장 (길드별 커스텀, 배포 시 유지)
- aliases.json (공식 기본값, 배포 시 업데이트)
"""

import discord
from discord.ext import commands
from discord import app_commands
import json
import os
from pathlib import Path

# ==================== 경로 ====================

BASE_ALIASES_FILE  = Path("bot/data/aliases.json")        # 공식 기본 (배포 관리)
GUILD_ALIASES_FILE = Path("bot/data/guild_aliases.json")  # 길드별 커스텀 (배포 시 유지)
SETTINGS_FILE      = Path("bot/data/guild_settings.json")

# ==================== 데이터 로드/저장 ====================

def load_base_aliases() -> dict:
    try:
        with open(BASE_ALIASES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"jobs": {}, "engravings": {}}


def load_guild_aliases(guild_id: int) -> dict:
    """길드별 커스텀 별명 로드"""
    try:
        with open(GUILD_ALIASES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get(str(guild_id), {"jobs": {}, "engravings": {}})
    except Exception:
        return {"jobs": {}, "engravings": {}}


def save_guild_alias(guild_id: int, target_type: str, target_name: str, alias: str) -> bool:
    """길드별 커스텀 별명 저장"""
    try:
        all_data = {}
        if GUILD_ALIASES_FILE.exists():
            with open(GUILD_ALIASES_FILE, "r", encoding="utf-8") as f:
                all_data = json.load(f)

        gid = str(guild_id)
        if gid not in all_data:
            all_data[gid] = {"jobs": {}, "engravings": {}}

        category = "jobs" if target_type == "직업" else "engravings"
        if target_name not in all_data[gid][category]:
            all_data[gid][category][target_name] = []

        if alias not in all_data[gid][category][target_name]:
            all_data[gid][category][target_name].append(alias)

        with open(GUILD_ALIASES_FILE, "w", encoding="utf-8") as f:
            json.dump(all_data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"[alias] 저장 오류: {e}")
        return False


def get_all_targets(target_type: str) -> list[str]:
    """직업 또는 각인 전체 목록"""
    data = load_base_aliases()
    if target_type == "직업":
        return sorted(data.get("jobs", {}).keys())
    else:
        return sorted(data.get("engravings", {}).keys())


def get_existing_aliases(guild_id: int, target_type: str, target_name: str) -> list[str]:
    """기본 + 길드 커스텀 별명 합쳐서 반환"""
    base  = load_base_aliases()
    guild = load_guild_aliases(guild_id)

    category = "jobs" if target_type == "직업" else "engravings"

    base_list  = base.get(category, {}).get(target_name, {})
    if isinstance(base_list, dict):
        base_list = base_list.get("aliases", [])

    guild_list = guild.get(category, {}).get(target_name, [])
    return list(set(base_list + guild_list))


# ==================== 승인 요청 View ====================

class AliasApproveView(discord.ui.View):
    """관리자 승인/거절 버튼"""

    def __init__(self, requester_id: int, guild_id: int,
                 target_type: str, target_name: str, alias: str):
        super().__init__(timeout=None)
        self.requester_id = requester_id
        self.guild_id     = guild_id
        self.target_type  = target_type
        self.target_name  = target_name
        self.alias        = alias

    def _build_result_embed(self, approved: bool, admin_name: str) -> discord.Embed:
        if approved:
            embed = discord.Embed(
                title="✅ 별명 추가 승인됨",
                color=0x57F287
            )
        else:
            embed = discord.Embed(
                title="❌ 별명 추가 거절됨",
                color=0xED4245
            )
        embed.add_field(name="대상",   value=f"{self.target_type} · **{self.target_name}**", inline=True)
        embed.add_field(name="별명",   value=f"`{self.alias}`",                               inline=True)
        embed.add_field(name="처리자", value=admin_name,                                      inline=True)
        return embed

    @discord.ui.button(
        label="✅ 승인",
        style=discord.ButtonStyle.success,
        custom_id="alias_approve"
    )
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ 관리자만 승인할 수 있습니다.", ephemeral=True)
            return

        ok = save_guild_alias(self.guild_id, self.target_type, self.target_name, self.alias)

        for item in self.children:
            item.disabled = True
        embed = self._build_result_embed(True, interaction.user.display_name)
        await interaction.message.edit(embed=embed, view=self)

        if ok:
            await interaction.response.send_message(
                f"✅ **{self.target_name}** → `{self.alias}` 별명이 추가됐습니다!", ephemeral=True
            )
        else:
            await interaction.response.send_message("❌ 저장 중 오류가 발생했습니다.", ephemeral=True)
            return

        # 요청자 DM 알림
        try:
            requester = await interaction.guild.fetch_member(self.requester_id)
            dm_embed = discord.Embed(
                title="✅ 별명 추가 승인!",
                description=f"**{self.target_name}** 의 별명 `{self.alias}` 가 추가됐습니다!",
                color=0x57F287
            )
            await requester.send(embed=dm_embed)
        except Exception:
            pass

    @discord.ui.button(
        label="❌ 거절",
        style=discord.ButtonStyle.danger,
        custom_id="alias_reject"
    )
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ 관리자만 거절할 수 있습니다.", ephemeral=True)
            return

        for item in self.children:
            item.disabled = True
        embed = self._build_result_embed(False, interaction.user.display_name)
        await interaction.message.edit(embed=embed, view=self)
        await interaction.response.send_message("거절 처리됐습니다.", ephemeral=True)

        # 요청자 DM 알림
        try:
            requester = await interaction.guild.fetch_member(self.requester_id)
            dm_embed = discord.Embed(
                title="❌ 별명 추가 거절",
                description=(
                    f"**{self.target_name}** 의 별명 `{self.alias}` 요청이 거절됐습니다.\n"
                    "다른 별명으로 다시 요청해보세요!"
                ),
                color=0xED4245
            )
            await requester.send(embed=dm_embed)
        except Exception:
            pass


# ==================== 별명 추가 Modal ====================

class AliasAddModal(discord.ui.Modal):
    """별명 입력 Modal"""

    alias_input = discord.ui.TextInput(
        label="추가할 별명",
        placeholder="예: 홀뚱이, 워붕붕, 디붕이...",
        min_length=1,
        max_length=20,
        required=True
    )

    def __init__(self, target_type: str, target_name: str):
        super().__init__(title=f"📝 별명 추가 — {target_name}")
        self.target_type = target_type
        self.target_name = target_name

    async def on_submit(self, interaction: discord.Interaction):
        alias = self.alias_input.value.strip()

        # 중복 체크
        existing = get_existing_aliases(interaction.guild_id, self.target_type, self.target_name)
        if alias in existing:
            await interaction.response.send_message(
                f"⚠️ `{alias}` 는 이미 등록된 별명입니다!", ephemeral=True
            )
            return

        # 봇-관리 채널에 승인 요청
        mgmt_channel = discord.utils.get(interaction.guild.text_channels, name="봇-관리")
        if not mgmt_channel:
            await interaction.response.send_message(
                "❌ 봇-관리 채널이 없습니다. 관리자에게 문의해주세요.", ephemeral=True
            )
            return

        # 요청 임베드
        embed = discord.Embed(
            title="📝 별명 추가 요청",
            color=0xFEE75C
        )
        embed.add_field(
            name="요청자",
            value=f"{interaction.user.mention} ({interaction.user.display_name})",
            inline=False
        )
        embed.add_field(name="타입", value=self.target_type, inline=True)
        embed.add_field(name="대상", value=f"**{self.target_name}**", inline=True)
        embed.add_field(name="추가 별명", value=f"`{alias}`", inline=True)

        # 기존 별명 목록
        if existing:
            existing_str = " · ".join([f"`{a}`" for a in existing[:10]])
            embed.add_field(name="현재 등록된 별명", value=existing_str, inline=False)
        else:
            embed.add_field(name="현재 등록된 별명", value="없음", inline=False)

        embed.set_footer(text="관리자가 승인 또는 거절해주세요")

        view = AliasApproveView(
            requester_id=interaction.user.id,
            guild_id=interaction.guild_id,
            target_type=self.target_type,
            target_name=self.target_name,
            alias=alias
        )
        await mgmt_channel.send(embed=embed, view=view)

        await interaction.response.send_message(
            f"✅ **{self.target_name}** 의 별명 `{alias}` 추가 요청을 보냈습니다!\n"
            f"관리자 승인 후 적용됩니다.",
            ephemeral=True
        )


# ==================== 타입 선택 View ====================

class AliasTypeView(discord.ui.View):
    """직업 / 각인 선택"""

    def __init__(self):
        super().__init__(timeout=60)

    @discord.ui.button(
        label="🎮 직업 별명 추가",
        style=discord.ButtonStyle.primary,
        custom_id="alias_type_job"
    )
    async def select_job(self, interaction: discord.Interaction, button: discord.ui.Button):
        targets = get_all_targets("직업")
        options = [
            discord.SelectOption(label=t, value=t)
            for t in targets[:25]
        ]
        view = AliasTargetView(target_type="직업", options=options)
        await interaction.response.edit_message(
            content="🎮 **직업을 선택해주세요:**",
            view=view
        )

    @discord.ui.button(
        label="📜 각인 별명 추가",
        style=discord.ButtonStyle.secondary,
        custom_id="alias_type_engraving"
    )
    async def select_engraving(self, interaction: discord.Interaction, button: discord.ui.Button):
        targets = get_all_targets("각인")
        # 각인은 많으니까 2개 View로 나눔
        options = [
            discord.SelectOption(label=t, value=t)
            for t in targets[:25]
        ]
        view = AliasTargetView(target_type="각인", options=options)
        await interaction.response.edit_message(
            content="📜 **각인을 선택해주세요:**",
            view=view
        )

    @discord.ui.button(
        label="📋 등록된 별명 보기",
        style=discord.ButtonStyle.secondary,
        custom_id="alias_type_list"
    )
    async def show_list(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild_aliases = load_guild_aliases(interaction.guild_id)
        base_aliases  = load_base_aliases()

        embed = discord.Embed(
            title="📋 등록된 별명 목록",
            color=0x5865F2
        )

        # 길드 커스텀 별명만 표시
        job_lines = []
        for job, aliases in guild_aliases.get("jobs", {}).items():
            if aliases:
                job_lines.append(f"**{job}**: {' · '.join([f'`{a}`' for a in aliases])}")

        eng_lines = []
        for eng, aliases in guild_aliases.get("engravings", {}).items():
            if aliases:
                eng_lines.append(f"**{eng}**: {' · '.join([f'`{a}`' for a in aliases])}")

        if job_lines:
            embed.add_field(
                name="🎮 직업 별명 (우리 길드)",
                value="\n".join(job_lines[:10]),
                inline=False
            )
        if eng_lines:
            embed.add_field(
                name="📜 각인 별명 (우리 길드)",
                value="\n".join(eng_lines[:10]),
                inline=False
            )

        if not job_lines and not eng_lines:
            embed.description = "아직 등록된 길드 별명이 없습니다!\n별명 추가 요청을 해보세요 😊"

        embed.set_footer(text="기본 별명 외 길드에서 추가한 별명만 표시됩니다")
        await interaction.response.send_message(embed=embed, ephemeral=True)


# ==================== 대상 선택 드롭다운 ====================

class AliasTargetView(discord.ui.View):
    def __init__(self, target_type: str, options: list):
        super().__init__(timeout=60)
        self.add_item(AliasTargetSelect(target_type=target_type, options=options))


class AliasTargetSelect(discord.ui.Select):
    def __init__(self, target_type: str, options: list):
        super().__init__(
            placeholder=f"{target_type}을 선택하세요...",
            min_values=1,
            max_values=1,
            options=options
        )
        self.target_type = target_type

    async def callback(self, interaction: discord.Interaction):
        target_name = self.values[0]
        await interaction.response.send_modal(
            AliasAddModal(target_type=self.target_type, target_name=target_name)
        )


# ==================== AliasCog ====================

class AliasCog(commands.Cog, name="AliasCog"):

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="별명추가", description="직업 또는 각인 별명을 추가 요청합니다")
    @app_commands.checks.cooldown(1, 86400.0, key=lambda i: i.user.id)
    async def alias_add(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="📝 별명 추가 요청",
            description=(
                "직업이나 각인에 **별명을 추가**할 수 있어요!\n\n"
                "예: `홀리나이트` → `홀뚱이`\n"
                "예: `고독한 기사` → `고기각인`\n\n"
                "요청 후 관리자 승인 시 적용됩니다."
            ),
            color=0x5865F2
        )
        embed.set_footer(text="길드별로 별명이 관리됩니다 · 업데이트 시에도 유지됩니다")

        await interaction.response.send_message(
            embed=embed,
            view=AliasTypeView(),
            ephemeral=True
        )

    @app_commands.command(name="별명목록", description="등록된 별명 목록을 확인합니다")
    async def alias_list(self, interaction: discord.Interaction):
        guild_aliases = load_guild_aliases(interaction.guild_id)
        base_aliases  = load_base_aliases()

        embed = discord.Embed(
            title="📋 별명 목록",
            color=0x5865F2
        )

        # 기본 별명 샘플
        base_jobs = base_aliases.get("jobs", {})
        sample_lines = []
        for job, data in list(base_jobs.items())[:8]:
            aliases = data.get("aliases", []) if isinstance(data, dict) else data
            if aliases:
                sample_lines.append(f"**{job}**: {' · '.join([f'`{a}`' for a in aliases[:4]])}")
        if sample_lines:
            embed.add_field(
                name="🎮 기본 직업 별명",
                value="\n".join(sample_lines),
                inline=False
            )

        # 길드 커스텀
        job_lines = []
        for job, aliases in guild_aliases.get("jobs", {}).items():
            if aliases:
                job_lines.append(f"**{job}**: {' · '.join([f'`{a}`' for a in aliases])}")
        eng_lines = []
        for eng, aliases in guild_aliases.get("engravings", {}).items():
            if aliases:
                eng_lines.append(f"**{eng}**: {' · '.join([f'`{a}`' for a in aliases])}")

        if job_lines:
            embed.add_field(
                name="🎮 우리 길드 직업 별명",
                value="\n".join(job_lines[:10]),
                inline=False
            )
        if eng_lines:
            embed.add_field(
                name="📜 우리 길드 각인 별명",
                value="\n".join(eng_lines[:10]),
                inline=False
            )

        if not job_lines and not eng_lines:
            embed.add_field(
                name="우리 길드 별명",
                value="아직 없어요! `/별명추가` 로 추가해보세요.",
                inline=False
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @alias_add.error
    async def alias_add_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CommandOnCooldown):
            hours   = int(error.retry_after // 3600)
            minutes = int((error.retry_after % 3600) // 60)
            await interaction.response.send_message(
                f"⏳ 별명 추가 요청은 하루에 한 번만 가능해요. {hours}시간 {minutes}분 후 다시 시도해주세요.",
                ephemeral=True
            )
        else:
            raise error


# ==================== Cog 등록 ====================

async def setup(bot):
    await bot.add_cog(AliasCog(bot))