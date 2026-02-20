"""
로일(LoIl) - 구글 시트 파싱 유틸
resolver.py를 통해 별명/서폿 판별 자동화
"""

import gspread
from oauth2client.service_account import ServiceAccountCredentials
from typing import Optional
from bot.config.settings import GOOGLE_CREDENTIALS_PATH
from bot.utils.resolver import normalize_character, is_support

SCOPE = [
    'https://spreadsheets.google.com/feeds',
    'https://www.googleapis.com/auth/drive'
]
CREDS_FILE = str(GOOGLE_CREDENTIALS_PATH)


def _get_client():
    creds = ServiceAccountCredentials.from_json_keyfile_name(CREDS_FILE, SCOPE)
    return gspread.authorize(creds)


def get_all_data(url: str) -> Optional[list]:
    """주간레이드 시트 전체 데이터"""
    try:
        client      = _get_client()
        spreadsheet = client.open_by_url(url)
        sheet       = spreadsheet.worksheet("주간레이드")
        return sheet.get_all_values()
    except Exception as e:
        print(f"[sheets] get_all_data 오류: {e}")
        return None


def get_sheet_info(url: str) -> Optional[dict]:
    """시트 기본 정보 (연동 테스트용)"""
    try:
        client      = _get_client()
        spreadsheet = client.open_by_url(url)
        sheet       = spreadsheet.worksheet("주간레이드")
        all_data    = sheet.get_all_values()
        return {
            'title':       spreadsheet.title,
            'worksheets':  [ws.title for ws in spreadsheet.worksheets()],
            'total_rows':  len(all_data),
            'total_cols':  len(all_data[0]) if all_data else 0
        }
    except Exception as e:
        print(f"[sheets] get_sheet_info 오류: {e}")
        return None


# ==================== 레이드 파싱 ====================

def parse_raids(data: list, guild_id: int = 0) -> list[dict]:
    """
    레이드 컬럼 파싱 (scheduled=TRUE인 것만)
    Row 1=요일, 2=시간, 3=분, 4=예정여부, 5=클리어, 6=레이드명, 7=예상시간
    """
    if not data or len(data) < 7:
        return []

    row_day      = data[0]
    row_hour     = data[1]
    row_min      = data[2]
    row_sched    = data[3]
    row_cleared  = data[4]
    row_name     = data[5]
    row_duration = data[6]

    raids = []
    for col in range(4, len(row_name)):
        name = (row_name[col] if col < len(row_name) else "").strip()
        if not name:
            continue

        scheduled = str(row_sched[col]).upper() == "TRUE" if col < len(row_sched) else False
        if not scheduled:
            continue

        day     = row_day[col]     if col < len(row_day)     else "미정"
        hr_raw  = row_hour[col]    if col < len(row_hour)    else "0"
        mn_raw  = row_min[col]     if col < len(row_min)     else ":00"
        cleared = str(row_cleared[col]).upper() == "TRUE" if col < len(row_cleared) else False
        dur_raw = row_duration[col] if col < len(row_duration) else "1"

        try:
            hour = int(hr_raw)
        except Exception:
            hour = 0
        minute = 30 if ":30" in str(mn_raw) else 0

        try:
            dur_min = int(dur_raw) * 30
        except Exception:
            dur_min = 30

        raids.append({
            'col':       col,
            'name':      name,
            'day':       day,
            'hour':      hour,
            'minute':    minute,
            'time_str':  f"{hour}:{minute:02d}",
            'scheduled': scheduled,
            'cleared':   cleared,
            'duration':  dur_min,
        })

    day_order = {'월':0,'화':1,'수':2,'목':3,'금':4,'토':5,'일':6,'미정':7}
    raids.sort(key=lambda r: (day_order.get(r['day'], 7), r['hour'], r['minute']))
    return raids


def parse_all_raids(data: list, guild_id: int = 0) -> list[dict]:
    """전체 레이드 파싱 (미정 포함)"""
    if not data or len(data) < 7:
        return []

    row_day      = data[0]
    row_hour     = data[1]
    row_min      = data[2]
    row_sched    = data[3]
    row_cleared  = data[4]
    row_name     = data[5]
    row_duration = data[6]

    raids = []
    for col in range(4, len(row_name)):
        name = (row_name[col] if col < len(row_name) else "").strip()
        if not name:
            continue

        day     = row_day[col]     if col < len(row_day)     else "미정"
        hr_raw  = row_hour[col]    if col < len(row_hour)    else "0"
        mn_raw  = row_min[col]     if col < len(row_min)     else ":00"
        scheduled = str(row_sched[col]).upper() == "TRUE" if col < len(row_sched) else False
        cleared = str(row_cleared[col]).upper() == "TRUE" if col < len(row_cleared) else False
        dur_raw = row_duration[col] if col < len(row_duration) else "1"

        try:
            hour = int(hr_raw)
        except Exception:
            hour = 0
        minute = 30 if ":30" in str(mn_raw) else 0

        try:
            dur_min = int(dur_raw) * 30
        except Exception:
            dur_min = 30

        raids.append({
            'col':       col,
            'name':      name,
            'day':       day,
            'hour':      hour,
            'minute':    minute,
            'time_str':  f"{hour}:{minute:02d}",
            'scheduled': scheduled,
            'cleared':   cleared,
            'duration':  dur_min,
        })

    day_order = {'월':0,'화':1,'수':2,'목':3,'금':4,'토':5,'일':6,'미정':7}
    raids.sort(key=lambda r: (day_order.get(r['day'], 7), r['hour'], r['minute']))
    return raids


# ==================== 길드원 파싱 ====================

def get_members(data: list, guild_id: int = 0) -> list[dict]:
    """
    길드원 파싱 (Row 8~)
    resolver.normalize_character()로 별명/서폿 자동 처리
    """
    if not data or len(data) < 8:
        return []

    members = []
    for row_idx in range(7, len(data)):
        row = data[row_idx]
        if len(row) < 4:
            continue

        name   = row[3].strip() if row[3] else ""
        absent = str(row[2]).upper() == "TRUE"

        if not name or name in ["인원수", "특이사항", ""]:
            break

        # Col E~ 캐릭터 파싱 (resolver 통해 정규화)
        characters = {}
        for col in range(4, len(row)):
            raw = row[col].strip() if col < len(row) else ""
            if not raw:
                continue
            parsed = normalize_character(raw, guild_id)
            if not parsed["absent"]:
                characters[col] = {
                    "raw":        raw,
                    "job":        parsed["job"],
                    "std_job":    parsed["std_job"],
                    "is_support": parsed["is_support"],
                    "is_alt":     parsed["is_alt"],
                    "display":    parsed["display"],
                }

        members.append({
            'name':       name,
            'absent':     absent,
            'row_idx':    row_idx,
            'characters': characters,
        })

    return members


def find_user_row(data: list, nickname: str, guild_id: int = 0) -> Optional[int]:
    """닉네임으로 행 인덱스 찾기"""
    for m in get_members(data, guild_id):
        if m['name'] == nickname or nickname in m['name']:
            return m['row_idx']
    return None


# ==================== 개인 일정 ====================

def get_user_schedule(data: list, nickname: str, guild_id: int = 0) -> list[dict]:
    """
    특정 길드원의 이번 주 일정
    (scheduled=TRUE 레이드 기준)
    """
    members = get_members(data, guild_id)
    raids   = parse_raids(data, guild_id)

    member = None
    for m in members:
        if m['name'] == nickname or nickname in m['name']:
            member = m
            break
    if not member:
        return []

    raid_map = {r['col']: r for r in raids}
    schedule = []

    for col, char_info in member['characters'].items():
        raid = raid_map.get(col)
        if not raid:
            continue
        schedule.append({
            'raid_name':  raid['name'],
            'day':        raid['day'],
            'hour':       raid['hour'],
            'minute':     raid['minute'],
            'time_str':   raid['time_str'],
            'character':  char_info['raw'],
            'std_job':    char_info['std_job'],
            'is_support': char_info['is_support'],
            'is_alt':     char_info['is_alt'],
            'duration':   raid['duration'],
            'cleared':    raid['cleared'],
            'scheduled':  raid['scheduled'],
        })

    day_order = {'월':0,'화':1,'수':2,'목':3,'금':4,'토':5,'일':6,'미정':7}
    schedule.sort(key=lambda s: (day_order.get(s['day'], 7), s['hour'], s['minute']))
    return schedule


def get_all_user_schedule(data: list, nickname: str, guild_id: int = 0) -> list[dict]:
    """
    특정 길드원의 전체 일정 (미정 포함)
    """
    members  = get_members(data, guild_id)
    all_raids = parse_all_raids(data, guild_id)

    member = None
    for m in members:
        if m['name'] == nickname or nickname in m['name']:
            member = m
            break
    if not member:
        return []

    raid_map = {r['col']: r for r in all_raids}
    schedule = []

    for col, char_info in member['characters'].items():
        raid = raid_map.get(col)
        if not raid:
            continue
        schedule.append({
            'raid_name':  raid['name'],
            'day':        raid['day'],
            'hour':       raid['hour'],
            'minute':     raid['minute'],
            'time_str':   raid['time_str'],
            'character':  char_info['raw'],
            'std_job':    char_info['std_job'],
            'is_support': char_info['is_support'],
            'is_alt':     char_info['is_alt'],
            'duration':   raid['duration'],
            'cleared':    raid['cleared'],
            'scheduled':  raid['scheduled'],
        })

    day_order = {'월':0,'화':1,'수':2,'목':3,'금':4,'토':5,'일':6,'미정':7}
    schedule.sort(key=lambda s: (day_order.get(s['day'], 7), s['hour'], s['minute']))
    return schedule


# ==================== 전체 레이드 요약 ====================

def get_weekly_summary(data: list, guild_id: int = 0) -> list[dict]:
    """
    이번 주 전체 레이드 요약 (scheduled=TRUE)
    레이드별 참여 인원 포함
    """
    raids   = parse_raids(data, guild_id)
    members = get_members(data, guild_id)

    result = []
    for raid in raids:
        col = raid['col']
        participating = []
        for m in members:
            if m['absent']:
                continue
            char = m['characters'].get(col)
            if char:
                participating.append({
                    'name':       m['name'],
                    'character':  char['raw'],
                    'std_job':    char['std_job'],
                    'is_support': char['is_support'],
                    'is_alt':     char['is_alt'],
                })

        result.append({
            **raid,
            'members':      participating,
            'member_count': len(participating),
        })

    return result


def get_all_weekly_summary(data: list, guild_id: int = 0) -> list[dict]:
    """전체 레이드 요약 (미정 포함)"""
    raids   = parse_all_raids(data, guild_id)
    members = get_members(data, guild_id)

    result = []
    for raid in raids:
        col = raid['col']
        participating = []
        for m in members:
            if m['absent']:
                continue
            char = m['characters'].get(col)
            if char:
                participating.append({
                    'name':       m['name'],
                    'character':  char['raw'],
                    'std_job':    char['std_job'],
                    'is_support': char['is_support'],
                    'is_alt':     char['is_alt'],
                })

        result.append({
            **raid,
            'members':      participating,
            'member_count': len(participating),
        })

    return result