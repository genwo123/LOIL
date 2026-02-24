"""
로일(LoIl) - 채널 구조 전면 개편 패치
옵션 C 이모지 스타일 적용

변경 사항:
  로일-공지      → 📜│패치노트   (봇 업데이트 자동 기록)
  없음           → 📡│공지      (새로 생성 - 길드장 일정 공지)
  이번주-레이드  → 🏹│이번주레이드
  일정-조회      → 🧾│개인일정
  파티-편성      → 🛡│레이드편성
  로일-설정      → ⚙│봇설정
  봇-관리        → 💌│건의함    (별명 요청, 건의사항)

실행: python patch_channels_v2.py
"""

import asyncio
import discord
from discord.ext import commands
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

TOKEN = os.getenv("DISCORD_BOT_TOKEN") or open("bot/data/.token").read().strip()

# ── 채널 이름 매핑 (구 → 신) ──
RENAME_MAP = {
    # 이전 이모지 버전 → 새 이름
    "📢│공지":        "📜│패치노트",
    "⚙️│봇설정":      "⚙│봇설정",
    "📅│이번주레이드": "🏹│이번주레이드",
    "🗒️│일정조회":    "🧾│개인일정",
    "⚔️│파티편성":    "🛡│레이드편성",
    "🔧│봇관리":      "💌│건의함",
    # 구버전 이름도 호환
    "로일-공지":      "📜│패치노트",
    "로일-설정":      "⚙│봇설정",
    "이번주-레이드":  "🏹│이번주레이드",
    "일정-조회":      "🧾│개인일정",
    "파티-편성":      "🛡│레이드편성",
    "봇-관리":        "💌│건의함",
}

# ── 채널 순서 (position 기준) ──
CHANNEL_ORDER = [
    "📜│패치노트",
    "📡│공지",
    "🏹│이번주레이드",
    "🧾│개인일정",
    "🛡│레이드편성",
    "⚙│봇설정",
    "💌│건의함",
]

# ── 채널 설명 (topic) ──
CHANNEL_TOPICS = {
    "📜│패치노트":    "로일 봇 업데이트 내역이 자동으로 기록됩니다",
    "📡│공지":        "길드장이 일정 공지를 올리는 채널",
    "🏹│이번주레이드": "이번 주 레이드 일정 자동 갱신",
    "🧾│개인일정":    "내 이번주 일정 확인 및 개인 조율",
    "🛡│레이드편성":  "레이드 파티 편성 및 AI 추천",
    "⚙│봇설정":      "봇 초기 설정 (관리자 전용)",
    "💌│건의함":      "별명 추가 요청, 건의사항",
}

intents = discord.Intents.default()
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"✅ 로그인: {bot.user}")

    for guild in bot.guilds:
        print(f"\n{'='*40}")
        print(f"서버: {guild.name}")
        print(f"{'='*40}")
        await patch_guild(guild)

    print("\n✅ 모든 서버 패치 완료!")
    await bot.close()


async def patch_guild(guild: discord.Guild):
    # ── 1. 로일 카테고리 찾기 ──
    category = None
    for cat in guild.categories:
        if "로일" in cat.name:
            category = cat
            break

    if not category:
        print(f"  ⚠️  로일 카테고리 없음 - 스킵")
        return

    print(f"  카테고리: {category.name}")

    # ── 2. 기존 채널 이름 변경 ──
    renamed = {}
    for ch in category.channels:
        new_name = RENAME_MAP.get(ch.name)
        if new_name and ch.name != new_name:
            try:
                topic = CHANNEL_TOPICS.get(new_name, "")
                await ch.edit(name=new_name, topic=topic)
                print(f"  ✅ 이름 변경: {ch.name} → {new_name}")
                renamed[new_name] = ch
                await asyncio.sleep(0.7)
            except Exception as e:
                print(f"  ❌ 변경 실패 ({ch.name}): {e}")
        else:
            renamed[ch.name] = ch

    # ── 3. 📡│공지 채널 없으면 새로 생성 ──
    notice_name = "📡│공지"
    existing_notice = discord.utils.get(category.channels, name=notice_name)
    if not existing_notice:
        try:
            new_ch = await guild.create_text_channel(
                name=notice_name,
                category=category,
                topic=CHANNEL_TOPICS[notice_name]
            )
            renamed[notice_name] = new_ch
            print(f"  ✅ 새 채널 생성: {notice_name}")
            await asyncio.sleep(0.7)
        except Exception as e:
            print(f"  ❌ 채널 생성 실패: {e}")

    # ── 4. 채널 순서 정렬 ──
    print(f"  채널 순서 정렬 중...")
    for idx, ch_name in enumerate(CHANNEL_ORDER):
        ch = discord.utils.get(category.channels, name=ch_name)
        if ch:
            try:
                await ch.edit(position=idx)
                await asyncio.sleep(0.5)
            except Exception as e:
                print(f"  ⚠️  순서 변경 실패 ({ch_name}): {e}")

    print(f"  ✅ 패치 완료!")

    # ── 5. 결과 출력 ──
    print(f"\n  최종 채널 목록:")
    for ch in sorted(category.channels, key=lambda c: c.position):
        print(f"    {ch.position+1}. {ch.name}")


bot.run(TOKEN)