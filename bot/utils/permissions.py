"""
로일(LoIl) - 권한 체계
Discord 기본 권한 기반 3단계

서버 소유자  → OWNER   (모든 권한)
관리자 권한  → ADMIN   (레이드 관리, 파티 확정, 봇 설정)
일반 유저    → MEMBER  (일정 보기, 불참 체크)
"""

import discord


# ==================== 권한 레벨 ====================

class PermLevel:
    MEMBER = 0   # 길드원
    ADMIN  = 1   # 길드장 / 부길드장 (Discord 관리자 권한)
    OWNER  = 2   # 서버 소유자 (개발자 = 우건)


def get_perm_level(interaction: discord.Interaction) -> int:
    """유저 권한 레벨 반환"""
    user = interaction.user
    guild = interaction.guild

    if guild and guild.owner_id == user.id:
        return PermLevel.OWNER

    if isinstance(user, discord.Member) and user.guild_permissions.administrator:
        return PermLevel.ADMIN

    return PermLevel.MEMBER


def is_owner(interaction: discord.Interaction) -> bool:
    return get_perm_level(interaction) >= PermLevel.OWNER

def is_admin(interaction: discord.Interaction) -> bool:
    """관리자 이상 (길드장, 부길드장, 소유자)"""
    return get_perm_level(interaction) >= PermLevel.ADMIN

def is_member(interaction: discord.Interaction) -> bool:
    """모든 길드원 (누구나)"""
    return get_perm_level(interaction) >= PermLevel.MEMBER


# ==================== 권한 거부 응답 ====================

async def deny(interaction: discord.Interaction, level: str = "admin"):
    """권한 없을 때 ephemeral 메시지"""
    messages = {
        "admin": "❌ 길드장 / 부길드장만 사용할 수 있습니다.\n*(Discord 관리자 권한 필요)*",
        "owner": "❌ 서버 소유자만 사용할 수 있습니다.",
    }
    msg = messages.get(level, "❌ 권한이 없습니다.")

    if interaction.response.is_done():
        await interaction.followup.send(msg, ephemeral=True)
    else:
        await interaction.response.send_message(msg, ephemeral=True)


# ==================== 권한 체크 데코레이터 스타일 헬퍼 ====================

async def require_admin(interaction: discord.Interaction) -> bool:
    """
    관리자 권한 체크 헬퍼
    사용법:
        if not await require_admin(interaction): return
    """
    if not is_admin(interaction):
        await deny(interaction, "admin")
        return False
    return True

async def require_owner(interaction: discord.Interaction) -> bool:
    """
    소유자 권한 체크 헬퍼
    사용법:
        if not await require_owner(interaction): return
    """
    if not is_owner(interaction):
        await deny(interaction, "owner")
        return False
    return True


# ==================== 권한 레벨 텍스트 ====================

def perm_label(interaction: discord.Interaction) -> str:
    level = get_perm_level(interaction)
    if level == PermLevel.OWNER:
        return "👑 서버 소유자"
    if level == PermLevel.ADMIN:
        return "🛡️ 관리자"
    return "👤 길드원"