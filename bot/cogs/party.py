"""
파티 관련 명령어
- /파티추천 - AI 파티 편성 추천
- /시너지 - 시너지 분석
"""

import discord
from discord.ext import commands
from discord import app_commands
from bot.utils.gemini_ai import recommend_party, analyze_synergy
from bot.utils.sheets import get_all_data, get_user_schedule, find_user_row
from bot.cogs.schedule import guild_sheets


class PartyCog(commands.Cog):
    """파티 관련 명령어 모음"""
    
    def __init__(self, bot):
        self.bot = bot
    
    # ==================== /파티추천 ====================
    
    @app_commands.command(name="파티추천", description="AI가 최적의 파티 편성을 추천해드립니다")
    @app_commands.describe(레이드="레이드 이름 (예: 에기르 하드)")
    async def party_recommend(self, interaction: discord.Interaction, 레이드: str):
        """AI 파티 편성 추천"""
        await interaction.response.defer(thinking=True)
        
        # 시트 URL 확인
        url = guild_sheets.get(interaction.guild_id)
        if not url:
            await interaction.followup.send(
                "❌ 구글 시트가 연동되지 않았습니다!\n"
                "`/설정 [시트URL]` 로 먼저 설정해주세요."
            )
            return
        
        # 시트에서 길드원 정보 읽기
        data = get_all_data(url)
        if not data:
            await interaction.followup.send("❌ 시트 데이터를 읽을 수 없습니다!")
            return
        
        # 길드원 멤버 정보 수집 (Row 8~부터)
        members = []
        
        # 서폿 직업 목록
        support_jobs = ['홀리나이트', '홀나', '바드', '발키리', '도화가']
        
        for row in data[7:]:  # Row 8~
            if len(row) < 4:
                continue
            
            name = row[3]  # 닉네임
            if not name or name in ['미정', '']:
                continue
            
            # 해당 레이드 참여 여부 확인
            # 일단 전체 멤버를 수집
            # 나중에 레이드별 필터링 추가 예정
            
            # 대표 캐릭터 찾기 (처음 참여하는 캐릭터)
            main_char = ''
            main_job = ''
            for col_idx in range(4, min(len(row), 61)):
                char = row[col_idx]
                if char and char != '미참여':
                    main_char = char
                    break
            
            if not main_char:
                continue
            
            # 직업 파싱 (예: "홀나", "홀나(폿)", "발키리(폿)")
            job = main_char.split('(')[0].strip()
            is_support = any(s in main_char for s in support_jobs)
            
            members.append({
                'name': name,
                'character': main_char,
                'job': job,
                'level': 0,  # 나중에 API로 조회 예정
                'is_support': is_support
            })
        
        if not members:
            await interaction.followup.send("❌ 참여 가능한 길드원이 없습니다!")
            return
        
        # 로딩 메시지
        loading_embed = discord.Embed(
            title="🤖 AI 파티 편성 중...",
            description=f"**{레이드}** 레이드 파티를 분석하고 있습니다!\n잠시만 기다려주세요...",
            color=discord.Color.yellow()
        )
        await interaction.followup.send(embed=loading_embed)
        
        # AI 추천 요청
        result = recommend_party(members, 레이드)
        
        # 결과 출력 (텍스트가 길면 여러 메시지로 분할)
        embed = discord.Embed(
            title=f"⚔️ {레이드} 파티 편성 추천",
            description=result[:2000] if len(result) > 2000 else result,
            color=discord.Color.gold()
        )
        embed.set_footer(text=f"참여 가능 인원: {len(members)}명 | AI 추천 결과입니다")
        
        await interaction.edit_original_response(embed=embed)
    
    
    # ==================== /시너지 ====================
    
    @app_commands.command(name="시너지", description="파티 구성의 시너지를 분석합니다")
    @app_commands.describe(직업들="직업 목록 (쉼표로 구분, 예: 홀리나이트,소서리스,리퍼,블레이드)")
    async def synergy_check(self, interaction: discord.Interaction, 직업들: str):
        """시너지 분석"""
        await interaction.response.defer(thinking=True)
        
        # 직업 파싱
        jobs = [j.strip() for j in 직업들.split(',') if j.strip()]
        
        if len(jobs) < 2:
            await interaction.followup.send(
                "❌ 직업을 2개 이상 입력해주세요!\n"
                "예시: `/시너지 홀리나이트,소서리스,리퍼,블레이드`"
            )
            return
        
        if len(jobs) > 8:
            await interaction.followup.send("❌ 최대 8개까지 입력 가능합니다!")
            return
        
        # AI 시너지 분석
        result = analyze_synergy(jobs)
        
        embed = discord.Embed(
            title="⚡ 시너지 분석 결과",
            description=result[:2000] if len(result) > 2000 else result,
            color=discord.Color.purple()
        )
        embed.add_field(
            name="분석한 직업",
            value=', '.join(jobs),
            inline=False
        )
        embed.set_footer(text="AI 분석 결과입니다")
        
        await interaction.followup.send(embed=embed)


# ==================== Cog 등록 ====================

async def setup(bot):
    await bot.add_cog(PartyCog(bot))