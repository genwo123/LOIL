"""
로일(LoIl) - 채널명 상수
"""

# ==================== 채널명 ====================

CH_NOTICE   = "📡│공지"
CH_SCHEDULE = "🗒│일정조회"
CH_PARTY    = "🛡│레이드편성"
CH_SUGGEST  = "💌│건의함"
CH_SETUP    = "⚙│봇설정"

# ==================== 카테고리 ====================

CATEGORY_NAME = "로일(LoIl)"

# ==================== 채널 생성 정보 ====================

LOIL_CHANNELS = [
    {"name": CH_NOTICE,   "topic": "길드 공지 및 일정 관리",      "admin_only": False},
    {"name": CH_SCHEDULE, "topic": "개인 일정 조회 (24시간 자동 삭제)", "admin_only": False},
    {"name": CH_PARTY,    "topic": "레이드 파티 편성 및 AI 추천",  "admin_only": False},
    {"name": CH_SUGGEST,  "topic": "길드 문의 / 개발 문의",        "admin_only": False},
    {"name": CH_SETUP,    "topic": "봇 초기 설정 (관리자 전용)",   "admin_only": True},
]

# ==================== 구버전 채널명 호환 ====================

LEGACY_NAMES = {
    CH_NOTICE:   ["로일-공지", "📢│공지", "📜│패치노트", "📡│공지"],
    CH_SCHEDULE: ["일정-조회", "🗒️│일정조회", "🧾│개인일정"],
    CH_PARTY:    ["파티-편성", "⚔️│파티편성", "🛡│레이드편성"],
    CH_SUGGEST:  ["봇-관리", "💌│건의함"],
    CH_SETUP:    ["로일-설정", "⚙│봇설정", "⚙️│봇설정"],
}


def get_channel(guild, ch_const: str):
    """채널 찾기 - 신규 이름 → 구버전 폴백"""
    import discord
    ch = discord.utils.get(guild.text_channels, name=ch_const)
    if ch:
        return ch
    for legacy in LEGACY_NAMES.get(ch_const, []):
        ch = discord.utils.get(guild.text_channels, name=legacy)
        if ch:
            return ch
    return None