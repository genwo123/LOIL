"""
로일(LoIl) Discord Bot
메인 실행 파일
"""

import discord
from discord.ext import commands
import os
from bot.config.settings import DISCORD_BOT_TOKEN, BOT_VERSION, COMMAND_PREFIX

# ==================== 봇 설정 ====================

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(
    command_prefix=COMMAND_PREFIX,
    intents=intents,
    help_command=None  # 기본 help 명령어 비활성화
)

# ==================== 이벤트 ====================

@bot.event
async def on_ready():
    """봇 시작 시"""
    print("=" * 50)
    print(f"🤖 {bot.user.name} v{BOT_VERSION} 시작!")
    print(f"📡 서버: {len(bot.guilds)}개")
    print(f"🔧 명령어 접두사: {COMMAND_PREFIX}")
    print("=" * 50)
    
    # Cogs 로드
    cogs = [
        'bot.cogs.schedule',
        'bot.cogs.party',
        'bot.cogs.admin',
        'bot.cogs.help',
    ]
    for cog in cogs:
        try:
            await bot.load_extension(cog)
            print(f"✅ {cog} 로드 완료!")
        except Exception as e:
            print(f"❌ {cog} 로드 실패: {e}")
    
    # 상태 메시지 설정
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="로스트아크 레이드 📋"
        )
    )
    
    # 슬래시 명령어 동기화
    try:
        synced = await bot.tree.sync()
        print(f"✅ 슬래시 명령어 {len(synced)}개 동기화 완료!")
    except Exception as e:
        print(f"❌ 슬래시 명령어 동기화 실패: {e}")


@bot.event
async def on_guild_join(guild):
    """새 서버 참가 시"""
    print(f"✅ 새 서버 참가: {guild.name} ({guild.member_count}명)")


@bot.event
async def on_command_error(ctx, error):
    """명령어 에러 처리"""
    if isinstance(error, commands.CommandNotFound):
        return  # 없는 명령어는 무시
    
    print(f"❌ 명령어 에러: {error}")


# ==================== 기본 명령어 ====================

@bot.tree.command(name="핑", description="봇 응답 속도 확인")
async def ping(interaction: discord.Interaction):
    """핑 테스트"""
    latency = round(bot.latency * 1000)
    await interaction.response.send_message(
        f"🏓 퐁! 응답속도: **{latency}ms**"
    )


@bot.tree.command(name="정보", description="로일 봇 정보")
async def info(interaction: discord.Interaction):
    """봇 정보"""
    embed = discord.Embed(
        title="🤖 로일(LoIl) 봇 정보",
        description="로스트아크 길드 레이드 자동화 봇",
        color=discord.Color.blue()
    )
    embed.add_field(name="버전", value=f"v{BOT_VERSION}", inline=True)
    embed.add_field(name="서버", value=f"{len(bot.guilds)}개", inline=True)
    embed.add_field(name="응답속도", value=f"{round(bot.latency * 1000)}ms", inline=True)
    embed.add_field(
        name="기능",
        value="• /일정 - 레이드 일정 조회\n• /파티추천 - AI 파티 편성\n• /설정 - 시트 연동",
        inline=False
    )
    embed.set_footer(text="Made for Lost Ark Guilds 🎮")
    
    await interaction.response.send_message(embed=embed)



# ==================== 실행 ====================

if __name__ == "__main__":
    if not DISCORD_BOT_TOKEN:
        print("❌ DISCORD_BOT_TOKEN이 설정되지 않았습니다!")
        print(".env 파일을 확인하세요.")
        exit(1)
    
    print("🚀 로일 봇 시작 중...")
    bot.run(DISCORD_BOT_TOKEN)