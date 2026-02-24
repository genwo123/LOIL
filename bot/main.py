"""
로일(LoIl) - Discord 봇 메인
실행: python -m bot.main (프로젝트 루트에서)
"""

import discord
from discord.ext import commands, tasks
from datetime import datetime, timezone, timedelta
import asyncio
import json
import os

from bot.config.settings import (
    DISCORD_BOT_TOKEN,
    BOT_NAME,
    BOT_VERSION,
    validate_config,
    print_config,
)
from bot.config.channels import (
    LOIL_CHANNELS,
    CATEGORY_NAME,
    CH_NOTICE,
    CH_SCHEDULE,
    CH_SETUP,
    CH_PARTY,
    CH_SUGGEST,
    get_channel,
)

# ==================== Intents ====================

intents = discord.Intents.default()
intents.message_content = True
intents.members         = True
intents.guilds          = True

# ==================== Bot ====================

bot = commands.Bot(command_prefix="!", intents=intents)

# ==================== Cog 목록 ====================

COGS = [
    "bot.cogs.setup",
    "bot.cogs.schedule",
    "bot.cogs.schedule_view",
    "bot.cogs.party",
    "bot.cogs.notice",
    "bot.cogs.suggest",
    "bot.cogs.raid_manage",
    "bot.cogs.admin",
    "bot.cogs.help",
    "bot.cogs.alias",
]

async def load_cogs():
    for cog in COGS:
        try:
            await bot.load_extension(cog)
            print(f"✅ {cog} 로드 완료!")
        except Exception as e:
            print(f"❌ {cog} 로드 실패: {e}")


# ==================== 채널 자동 생성 ====================

async def setup_guild_channels(guild: discord.Guild):
    """봇 입장 시 로일 카테고리 + 채널 자동 생성"""

    if discord.utils.get(guild.categories, name=CATEGORY_NAME):
        print(f"[{guild.name}] 채널 이미 존재, 스킵")
        return

    try:
        if not guild.me.guild_permissions.manage_channels:
            print(f"[{guild.name}] 채널 관리 권한 없음")
            return

        category = await guild.create_category(CATEGORY_NAME)

        # 봇설정 채널 관리자 전용 권한
        admin_overwrite = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True),
        }
        for role in guild.roles:
            if role.permissions.administrator:
                admin_overwrite[role] = discord.PermissionOverwrite(
                    view_channel=True, send_messages=True
                )

        for ch_info in LOIL_CHANNELS:
            ow = admin_overwrite if ch_info.get("admin_only") else {}
            await guild.create_text_channel(
                name=ch_info["name"],
                category=category,
                topic=ch_info["topic"],
                overwrites=ow
            )
            await asyncio.sleep(0.5)

        print(f"[{guild.name}] 채널 {len(LOIL_CHANNELS)}개 생성 완료!")

        # 패치노트 채널에 환영 메시지
        patchnote_ch = get_channel(guild, CH_PATCHNOTE)
        if patchnote_ch:
            embed = discord.Embed(
                title=f"로일(LoIl) v{BOT_VERSION} 입장!",
                description=(
                    "로스트아크 길드 레이드 자동화 봇입니다!\n\n"
                    "**시작하기**\n"
                    "1. **⚙│봇설정** 채널에서 구글 시트 연동\n"
                    "2. **🏹│이번주레이드** 채널에서 일정 확인\n"
                    "3. **🛡│레이드편성** 채널에서 AI 파티 추천\n\n"
                    "문의: `/도움말`"
                ),
                color=0x5865F2
            )
            embed.set_footer(text=f"로일(LoIl) v{BOT_VERSION}")
            await patchnote_ch.send(embed=embed)

        # 공지 패널
        notice_cog = bot.cogs.get("NoticeCog")
        if notice_cog:
            notice_ch = get_channel(guild, CH_NOTICE)
            if notice_ch:
                await notice_cog.send_notice_panel(notice_ch)

        # 일정조회 패널
        sv_cog = bot.cogs.get("ScheduleViewCog")
        if sv_cog:
            sv_ch = get_channel(guild, CH_SCHEDULE)
            if sv_ch:
                await sv_cog.send_schedule_panel(sv_ch)

        # 파티 패널
        party_cog = bot.cogs.get("PartyCog")
        if party_cog:
            party_ch = get_channel(guild, CH_PARTY)
            if party_ch:
                await party_cog.send_party_panel(party_ch)

        # 건의함 패널
        suggest_cog = bot.cogs.get("SuggestCog")
        if suggest_cog:
            suggest_ch = get_channel(guild, CH_SUGGEST)
            if suggest_ch:
                await suggest_cog.send_suggest_panel(suggest_ch)

        # 설정 패널
        setup_cog = bot.cogs.get("SetupCog")
        if setup_cog:
            setup_ch = get_channel(guild, CH_SETUP)
            if setup_ch:
                await setup_cog.send_setup_panel(setup_ch)

    except Exception as e:
        print(f"[{guild.name}] 채널 생성 실패: {e}")


# ==================== 채널 자동 삭제 ====================

async def cleanup_guild_channels(guild: discord.Guild):
    """봇 강퇴/탈퇴 시 로일 카테고리 + 채널 + 설정 삭제"""

    print(f"[{guild.name}] 봇 제거 → 채널 정리 시작")

    category = discord.utils.get(guild.categories, name=CATEGORY_NAME)
    if not category:
        print(f"[{guild.name}] 로일 카테고리 없음 - 스킵")
        _cleanup_guild_settings(guild.id)
        return

    try:
        deleted = 0
        for channel in list(category.channels):
            try:
                await channel.delete(reason="로일 봇 제거")
                deleted += 1
                await asyncio.sleep(0.3)
            except Exception as e:
                print(f"  채널 삭제 실패 ({channel.name}): {e}")

        await category.delete(reason="로일 봇 제거")
        print(f"[{guild.name}] 채널 {deleted}개 + 카테고리 삭제 완료")

    except Exception as e:
        print(f"[{guild.name}] 채널 정리 실패: {e}")

    _cleanup_guild_settings(guild.id)


def _cleanup_guild_settings(guild_id: int):
    """guild_settings.json 에서 해당 길드 설정 제거"""
    settings_file = "bot/data/guild_settings.json"
    if not os.path.exists(settings_file):
        return
    try:
        with open(settings_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        if str(guild_id) in data:
            del data[str(guild_id)]
            with open(settings_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"  길드 설정 삭제 완료 (ID: {guild_id})")
    except Exception as e:
        print(f"  설정 삭제 실패: {e}")


# ==================== 이벤트 ====================

@bot.event
async def on_ready():
    print("=" * 50)
    print(f"로일(LoIl) v{BOT_VERSION}")
    print(f"   로그인: {bot.user} (ID: {bot.user.id})")
    print(f"   서버: {len(bot.guilds)}개")
    print("=" * 50)

    await load_cogs()

    try:
        synced = await bot.tree.sync()
        print(f"✅ 슬래시 명령어 {len(synced)}개 동기화 완료!")
    except Exception as e:
        print(f"❌ 명령어 동기화 실패: {e}")

    if not weekly_update_scheduler.is_running():
        weekly_update_scheduler.start()
        print("✅ 수요일 자동 갱신 스케줄러 시작!")

    await bot.change_presence(
        activity=discord.Game(name="로스트아크 길드 관리 | /도움말")
    )
    print("✅ 봇 준비 완료!")


@bot.event
async def on_guild_join(guild: discord.Guild):
    """봇 서버 입장 시 채널 자동 생성"""
    print(f"✅ 새 서버 입장: {guild.name}")
    await setup_guild_channels(guild)


@bot.event
async def on_guild_remove(guild: discord.Guild):
    """봇 강퇴/탈퇴 시 채널 + 설정 자동 삭제"""
    print(f"봇 제거됨: {guild.name}")
    await cleanup_guild_channels(guild)


# ==================== 수요일 자동 갱신 ====================

KST = timezone(timedelta(hours=9))

@tasks.loop(minutes=1)
async def weekly_update_scheduler():
    """매주 수요일 09:00 KST 자동 갱신"""
    now = datetime.now(KST)

    if now.weekday() == 2 and now.hour == 9 and now.minute == 0:
        print(f"[스케줄러] 수요일 자동 갱신 시작! {now.strftime('%Y-%m-%d %H:%M')}")

        schedule_cog = bot.cogs.get("ScheduleCog")
        if not schedule_cog:
            return

        success = 0
        for guild in bot.guilds:
            try:
                ok = await schedule_cog.update_weekly_channel(guild)
                if ok:
                    success += 1
                    patchnote_ch = get_channel(guild, CH_PATCHNOTE)
                    if patchnote_ch:
                        embed = discord.Embed(
                            title="이번 주 레이드 일정 갱신!",
                            description="🏹│이번주레이드 채널에서 확인하세요!",
                            color=0x57F287
                        )
                        await patchnote_ch.send(embed=embed)
            except Exception as e:
                print(f"  [{guild.name}] 갱신 실패: {e}")

        print(f"[스케줄러] 완료! {success}/{len(bot.guilds)}개 서버 갱신")


@weekly_update_scheduler.before_loop
async def before_scheduler():
    await bot.wait_until_ready()


# ==================== 실행 ====================

if __name__ == "__main__":
    validate_config()
    print_config()
    bot.run(DISCORD_BOT_TOKEN)