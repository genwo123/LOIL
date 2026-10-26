"""
로일(LoIl) - 임시 길드(웹에서 먼저 생성) ↔ 실제 Discord 서버 연결 Modal

웹에서 봇 초대 전에 미리 만들어둔 길드 설정(레이드 카탈로그, 시간 정책 등)을
봇이 실제로 초대된 서버에 옮겨 붙인다. 설정 패널의 "길드 연결" 버튼에서 연다.
"""

import discord

from bot.utils.guild_link import find_guild_by_connect_code, merge_pending_into_real_guild
from bot.utils.permissions import require_admin


class GuildConnectModal(discord.ui.Modal, title="🔗 길드 연결"):
    code = discord.ui.TextInput(
        label="연결 코드",
        placeholder="웹에서 길드를 만들 때 발급된 코드",
        style=discord.TextStyle.short,
        min_length=1,
        max_length=50,
        required=True,
    )

    async def on_submit(self, interaction: discord.Interaction):
        if not await require_admin(interaction):
            return

        found = find_guild_by_connect_code(self.code.value.strip())
        if not found:
            await interaction.response.send_message(
                "❌ 유효하지 않은 연결 코드입니다. 웹에서 만든 길드 홈 화면의 코드를 다시 확인해주세요.",
                ephemeral=True,
            )
            return

        temp_id, _pending = found
        ok = merge_pending_into_real_guild(temp_id, interaction.guild_id)
        if ok:
            await interaction.response.send_message(
                "✅ 연결 완료! 웹에서 미리 설정한 레이드/시간 정책이 이 서버로 옮겨졌습니다.",
                ephemeral=True,
            )
        else:
            await interaction.response.send_message("❌ 연결에 실패했습니다. 다시 시도해주세요.", ephemeral=True)
