"""
로일(LoIl) - Discord 봇 메인
실행: python -m bot.main (프로젝트 루트에서)
"""

import discord
from discord.ext import commands, tasks
from datetime import datetime, timezone, timedelta
import asyncio

from bot.config.settings import (
    DISCORD_BOT_TOKEN,
    BOT_NAME,
    BOT_VERSION,
    validate_config,
    print_config,
)

# ==================== Intents ====================

intents = discord.Intents.default()
intents.message_content = True
intents.members         = True
intents.guilds          = True

# ==================== Bot ====================

bot = commands.Bot(command_prefix="!", intents=intents)

# ==================== 채널 구조 ====================

LOIL_CATEGORY = "로일(LoIl)"
LOIL_CHANNELS  = [
    ("로일-공지",    "로일 봇 공지 채널"),
    ("로일-설정",    "봇 설정 채널"),
    ("이번주-레이드", "이번 주 레이드 일정 자동 갱신"),
    ("일정-조회",    "개인 일정 조회 스레드"),
    ("파티-편성",    "AI 파티 편성 추천"),
    ("봇-관리",     "봇 관리 및 별명 승인"),
]

# ==================== Cog 목록 ====================

COGS = [
    "bot.cogs.setup",
    "bot.cogs.schedule",
    "bot.cogs.party",
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
    if discord.utils.get(guild.categories, name=LOIL_CATEGORY):
        print(f"[{guild.name}] 채널 이미 존재, 스킵")
        return

    try:
        if not guild.me.guild_permissions.manage_channels:
            print(f"[{guild.name}] 채널 관리 권한 없음")
            return

        category = await guild.create_category(LOIL_CATEGORY)

        for name, topic in LOIL_CHANNELS:
            await guild.create_text_channel(name=name, category=category, topic=topic)
            await asyncio.sleep(0.5)

        print(f"[{guild.name}] 채널 {len(LOIL_CHANNELS)}개 생성 완료!")

        # 환영 메시지
        notice_ch = discord.utils.get(guild.text_channels, name="로일-공지")
        if notice_ch:
            embed = discord.Embed(
                title=f"🎮 {BOT_NAME} v{BOT_VERSION} 입장!",
                description=(
                    "로스트아크 길드 레이드 자동화 봇입니다!\n\n"
                    "**⚙️ 시작하기**\n"
                    "1. **로일-설정** 채널에서 구글 시트 연동\n"
                    "2. **이번주-레이드** 채널에서 일정 확인\n"
                    "3. **파티-편성** 채널에서 AI 파티 추천\n\n"
                    "문의: `/도움말`"
                ),
                color=0x5865F2
            )
            embed.set_footer(text=f"로일(LoIl) v{BOT_VERSION}")
            await notice_ch.send(embed=embed)

        # 설정 패널
        setup_cog = bot.cogs.get("SetupCog")
        if setup_cog:
            setup_ch = discord.utils.get(guild.text_channels, name="로일-설정")
            if setup_ch:
                await setup_cog.send_setup_panel(setup_ch)

        # 파티 패널
        party_cog = bot.cogs.get("PartyCog")
        if party_cog:
            party_ch = discord.utils.get(guild.text_channels, name="파티-편성")
            if party_ch:
                await party_cog.send_party_panel(party_ch)

    except Exception as e:
        print(f"[{guild.name}] 채널 생성 실패: {e}")

# ==================== 이벤트 ====================

@bot.event
async def on_ready():
    print("=" * 50)
    print(f"🤖 {BOT_NAME} v{BOT_VERSION}")
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
    print(f"✅ 새 서버 입장: {guild.name}")
    await setup_guild_channels(guild)

# ==================== 수요일 자동 갱신 ====================

KST = timezone(timedelta(hours=9))

@tasks.loop(minutes=1)
async def weekly_update_scheduler():
    """매주 수요일 09:00 KST 자동 갱신 (로아 정기점검 이후)"""
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
                    notice_ch = discord.utils.get(guild.text_channels, name="로일-공지")
                    if notice_ch:
                        embed = discord.Embed(
                            title="📅 이번 주 레이드 일정 갱신!",
                            description=(
                                "수요일 정기점검 이후 이번 주 일정이 갱신됐습니다!\n"
                                "**이번주-레이드** 채널에서 확인해주세요 🎮"
                            ),
                            color=0x57F287
                        )
                        embed.set_footer(text="매주 수요일 09:00 자동 갱신")
                        await notice_ch.send(embed=embed)
            except Exception as e:
                print(f"[스케줄러] {guild.name} 갱신 실패: {e}")

        print(f"[스케줄러] {success}/{len(bot.guilds)}개 서버 갱신 완료")


@weekly_update_scheduler.before_loop
async def before_scheduler():
    await bot.wait_until_ready()

# ==================== 글로벌 에러 핸들러 ====================

@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error):
    if isinstance(error, discord.app_commands.MissingPermissions):
        await interaction.response.send_message("❌ 권한이 없습니다.", ephemeral=True)
    elif isinstance(error, discord.app_commands.CommandOnCooldown):
        await interaction.response.send_message(
            f"⏳ {error.retry_after:.1f}초 후 다시 시도해주세요.", ephemeral=True
        )
    else:
        print(f"[앱 명령어 오류] {error}")
        try:
            await interaction.response.send_message(
                "❌ 오류가 발생했습니다. 잠시 후 다시 시도해주세요.", ephemeral=True
            )
        except Exception:
            pass

# ==================== 실행 ====================

def main():
    print_config()
    errors = validate_config()
    if errors:
        print("⚠️ 설정 오류:")
        for e in errors:
            print(f"  - {e}")

    if not DISCORD_BOT_TOKEN:
        print("❌ DISCORD_BOT_TOKEN 없음. .env 확인해주세요.")
        return

    bot.run(DISCORD_BOT_TOKEN)


if __name__ == "__main__":
    main()