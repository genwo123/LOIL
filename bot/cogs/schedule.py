"""
일정 관련 명령어
- /설정 - 구글 시트 연동
- /일정 - 이번 주 레이드 일정
- /내일정 - 내 일정 조회
"""

import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional
from bot.utils.sheets import (
    get_sheet_info,
    get_all_data,
    get_user_schedule,
    find_user_row
)

# ==================== 서버별 시트 URL 저장 (임시) ====================
# 나중에 DB로 교체 예정
guild_sheets = {}  # {guild_id: sheet_url}


class ScheduleCog(commands.Cog):
    """일정 관련 명령어 모음"""
    
    def __init__(self, bot):
        self.bot = bot
    
    # ==================== /설정 ====================
    
    @app_commands.command(name="설정", description="구글 시트를 연동합니다")
    @app_commands.describe(url="구글 스프레드시트 URL")
    async def setup_sheet(self, interaction: discord.Interaction, url: str):
        """구글 시트 연동"""
        await interaction.response.defer(thinking=True)
        
        # URL 유효성 검사
        if "docs.google.com/spreadsheets" not in url:
            await interaction.followup.send(
                "❌ 올바른 구글 시트 URL이 아닙니다!\n"
                "예시: `https://docs.google.com/spreadsheets/d/...`"
            )
            return
        
        # 시트 접근 테스트
        info = get_sheet_info(url)
        
        if not info:
            await interaction.followup.send(
                "❌ 시트에 접근할 수 없습니다!\n"
                "시트 공유 설정을 확인하세요:\n"
                "`loli-sheet@loil-487100.iam.gserviceaccount.com` 에 편집자 권한 필요"
            )
            return
        
        # 서버에 시트 URL 저장
        guild_sheets[interaction.guild_id] = url
        
        embed = discord.Embed(
            title="✅ 구글 시트 연동 완료!",
            color=discord.Color.green()
        )
        embed.add_field(name="시트 제목", value=info['title'], inline=False)
        embed.add_field(name="워크시트", value=f"{len(info['worksheets'])}개", inline=True)
        embed.add_field(name="데이터", value=f"{info['total_rows']}행 x {info['total_cols']}열", inline=True)
        embed.add_field(
            name="사용 가능한 명령어",
            value="`/일정` - 전체 일정 조회\n`/내일정 [닉네임]` - 개인 일정 조회",
            inline=False
        )
        embed.set_footer(text="시트가 수정되면 자동으로 반영됩니다!")
        
        await interaction.followup.send(embed=embed)
    
    
    # ==================== /일정 ====================
    
    @app_commands.command(name="일정", description="이번 주 레이드 일정을 확인합니다")
    async def show_schedule(self, interaction: discord.Interaction):
        """전체 일정 조회"""
        await interaction.response.defer(thinking=True)
        
        # 시트 URL 확인
        url = guild_sheets.get(interaction.guild_id)
        if not url:
            await interaction.followup.send(
                "❌ 구글 시트가 연동되지 않았습니다!\n"
                "`/설정 [시트URL]` 로 먼저 설정해주세요."
            )
            return
        
        # 데이터 읽기
        data = get_all_data(url)
        if not data:
            await interaction.followup.send("❌ 시트 데이터를 읽을 수 없습니다!")
            return
        
        # Row 6이 레이드 헤더 (인덱스 5)
        # Row 8~부터 길드원 데이터 (인덱스 7~)
        
        embed = discord.Embed(
            title="📅 이번 주 레이드 일정",
            color=discord.Color.blue()
        )
        
        # 날짜 정보 (Row 1~3)
        try:
            days = data[0]     # 요일
            dates = data[1]    # 날짜
            times = data[2]    # 시간
            raids = data[5]    # 레이드명 (Row 6)
            
            # 레이드별 정리
            raid_summary = {}
            
            for col_idx in range(4, min(len(raids), 61)):
                raid_name = raids[col_idx] if col_idx < len(raids) else ''
                day = days[col_idx] if col_idx < len(days) else '미정'
                date = dates[col_idx] if col_idx < len(dates) else ''
                time = times[col_idx] if col_idx < len(times) else ''
                
                if not raid_name or raid_name in ['미정', '']:
                    continue
                
                # 레이드별 참여자 수집
                members = []
                for row in data[7:]:  # Row 8부터
                    if len(row) > col_idx:
                        char = row[col_idx]
                        if char and char != '미참여':
                            # 길드원 이름 찾기
                            name = row[3] if len(row) > 3 else '?'
                            members.append(f"{name}({char})")
                
                key = f"{day} {date}{time} - {raid_name}"
                raid_summary[key] = members
            
            if not raid_summary:
                await interaction.followup.send("📭 이번 주 등록된 레이드가 없습니다!")
                return
            
            # 임베드에 추가 (최대 5개)
            for i, (raid_info, members) in enumerate(list(raid_summary.items())[:5]):
                member_text = '\n'.join(members) if members else '참여자 없음'
                embed.add_field(
                    name=f"🗡️ {raid_info} ({len(members)}명)",
                    value=member_text[:200] if member_text else '참여자 없음',
                    inline=False
                )
            
            if len(raid_summary) > 5:
                embed.set_footer(text=f"총 {len(raid_summary)}개 레이드 중 5개만 표시")
        
        except Exception as e:
            await interaction.followup.send(f"❌ 일정 파싱 중 오류: {e}")
            return
        
        await interaction.followup.send(embed=embed)
    
    
    # ==================== /내일정 ====================
    
    @app_commands.command(name="내일정", description="내 레이드 일정을 확인합니다")
    @app_commands.describe(닉네임="길드원 닉네임 (예: 거니)")
    async def my_schedule(self, interaction: discord.Interaction, 닉네임: str):
        """개인 일정 조회"""
        await interaction.response.defer(thinking=True)
        
        # 시트 URL 확인
        url = guild_sheets.get(interaction.guild_id)
        if not url:
            await interaction.followup.send(
                "❌ 구글 시트가 연동되지 않았습니다!\n"
                "`/설정 [시트URL]` 로 먼저 설정해주세요."
            )
            return
        
        # 데이터 읽기
        data = get_all_data(url)
        if not data:
            await interaction.followup.send("❌ 시트 데이터를 읽을 수 없습니다!")
            return
        
        # 유저 찾기
        user_row = find_user_row(data, 닉네임)
        
        if user_row is None:
            await interaction.followup.send(
                f"❌ `{닉네임}` 를 시트에서 찾을 수 없습니다!\n"
                "닉네임을 정확히 입력해주세요."
            )
            return
        
        # 일정 가져오기
        schedules = get_user_schedule(data, 닉네임)
        
        if not schedules:
            await interaction.followup.send(f"📭 `{닉네임}` 의 이번 주 일정이 없습니다!")
            return
        
        # 날짜/시간 정보 추가
        days = data[0]
        dates = data[1]
        times = data[2]
        
        embed = discord.Embed(
            title=f"📅 {닉네임}의 이번 주 일정",
            color=discord.Color.green()
        )
        
        for s in schedules[:10]:  # 최대 10개
            col = s['col']
            day = days[col] if col < len(days) else '?'
            date = dates[col] if col < len(dates) else '?'
            time = times[col] if col < len(times) else '?'
            
            embed.add_field(
                name=f"🗡️ {s['raid']}",
                value=f"📆 {day} {date}{time}\n⚔️ {s['character']}",
                inline=True
            )
        
        embed.set_footer(text=f"총 {len(schedules)}개 레이드 참여")
        
        await interaction.followup.send(embed=embed)


# ==================== Cog 등록 ====================

async def setup(bot):
    await bot.add_cog(ScheduleCog(bot))