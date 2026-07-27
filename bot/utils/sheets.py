"""
로일(LoIl) - 구글 시트 파싱 유틸
resolver.py를 통해 별명/서폿 판별 자동화
"""

import json
import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from typing import Optional
from datetime import datetime
from bot.config.settings import GOOGLE_CREDENTIALS_PATH
from bot.utils.resolver import normalize_character, is_support

SCOPE = [
    'https://spreadsheets.google.com/feeds',
    'https://www.googleapis.com/auth/drive'
]
CREDS_FILE = str(GOOGLE_CREDENTIALS_PATH)

# ==================== 레이드 데이터 로드 ====================

def _load_raid_data() -> dict:
    path = os.path.join(os.path.dirname(__file__), '..', 'data', 'raid_data.json')
    path = os.path.normpath(path)
    with open(path, encoding='utf-8') as f:
        return json.load(f)

_RAID_DATA     = _load_raid_data()
RAID_LEVEL_MAP = _RAID_DATA['raid_level_map']  # {"세르카": {"하드": {"ilvl":1730,"category":4,"size":4,"duration":60}, ...}}
DIFF_KEYWORDS  = _RAID_DATA['diff_keywords']   # ["하드", "노말", ...]
DIFF_ALIASES   = _RAID_DATA.get('diff_aliases', {})  # {"나메": "나이트메어", ...} 축약어 → 정식 난이도명
CATEGORIES     = _RAID_DATA['categories']      # {"0": "어비스 레이드", ...}


def _match_difficulty(diffs: dict, raid_name: str) -> dict:
    """레이드명 문자열에서 난이도를 찾아 해당 정보(dict) 반환.
    정식 난이도명 매칭을 우선하고, 축약어(나메→나이트메어 등)도 인식한다.
    매칭 실패 시 첫 번째 난이도로 폴백."""
    for diff, info in diffs.items():
        if diff in raid_name:
            return info
    for alias, canonical in DIFF_ALIASES.items():
        if alias in raid_name and canonical in diffs:
            return diffs[canonical]
    return next(iter(diffs.values()))


def get_raid_size(raid_name: str) -> int:
    """레이드명으로 인원수 반환 (4/8/16). 기본값 8."""
    for base, diffs in RAID_LEVEL_MAP.items():
        if base in raid_name:
            return _match_difficulty(diffs, raid_name).get('size', 8)
    return 8


def get_raid_default_duration(raid_name: str) -> int:
    """레이드명으로 기본 소요시간(분) 반환. 기본값 60."""
    for base, diffs in RAID_LEVEL_MAP.items():
        if base in raid_name:
            return _match_difficulty(diffs, raid_name).get('duration', 60)
    return 60


# ==================== 시트 구조 상수 ====================
SHEET_RAID    = "주간레이드"
SHEET_AI_RAID = "AI편성"

# 주간레이드 탭 행 인덱스 (0-based)
ROW_DAY      = 0   # 1행: 요일
ROW_HOUR     = 1   # 2행: 시간(시)
ROW_MIN      = 2   # 3행: 시간(분)
ROW_SCHED    = 3   # 4행: 예정여부 (체크박스)
ROW_FIXED    = 4   # 5행: 고정멤버여부
ROW_CLEARED  = 5   # 6행: 클리어여부
ROW_NAME     = 6   # 7행: 레이드명
ROW_DURATION = 7   # 8행: 예상시간
ROW_MEMBERS  = 8   # 9행~: 길드원


def _is_true(val: str) -> bool:
    """O / TRUE / 1 / Y / V / 참 / 체크 → True로 인식 (대소문자 무관)"""
    v = str(val).strip().upper()
    return v in ("TRUE", "O", "1", "Y", "YES", "참", "V", "✓", "CHECK")


def _get_client():
    creds = ServiceAccountCredentials.from_json_keyfile_name(CREDS_FILE, SCOPE)
    return gspread.authorize(creds)


def _get_spreadsheet(url: str):
    return _get_client().open_by_url(url)


# ==================== 데이터 읽기 ====================

def get_all_data(url: str, ai: bool = False) -> Optional[list]:
    """주간레이드(또는 AI편성) 시트 전체 데이터"""
    try:
        name = SHEET_AI_RAID if ai else SHEET_RAID
        return _get_spreadsheet(url).worksheet(name).get_all_values()
    except Exception as e:
        print(f"[sheets] get_all_data 오류: {e}")
        return None


def get_sheet_info(url: str) -> Optional[dict]:
    """시트 기본 정보 (연동 테스트용)"""
    try:
        spreadsheet = _get_spreadsheet(url)
        sheet       = spreadsheet.worksheet("주간레이드")
        all_data    = sheet.get_all_values()
        return {
            'title':      spreadsheet.title,
            'worksheets': [ws.title for ws in spreadsheet.worksheets()],
            'total_rows': len(all_data),
            'total_cols': len(all_data[0]) if all_data else 0
        }
    except Exception as e:
        print(f"[sheets] get_sheet_info 오류: {e}")
        return None


# ==================== 개인탭 목록 ====================

def get_personal_sheet_names(url: str) -> list[str]:
    try:
        worksheets = _get_spreadsheet(url).worksheets()
        names = [ws.title for ws in worksheets]
        if "종합시트" not in names:
            return []
        start = names.index("종합시트") + 1
        return [n for n in names[start:] if n != "데이터베이스"]
    except Exception as e:
        print(f"[sheets] get_personal_sheet_names 오류: {e}")
        return []


# ==================== 개인탭 가능시간 파싱 ====================

DAY_COL_MAP = {'수': 3, '목': 4, '금': 5, '토': 6, '일': 7, '월': 8, '화': 9}

def get_personal_availability(url: str, nickname: str) -> dict:
    try:
        sheet = _get_spreadsheet(url).worksheet(nickname)
        data  = sheet.get_all_values()
    except Exception as e:
        print(f"[sheets] get_personal_availability 오류({nickname}): {e}")
        return {}

    availability = {}
    days      = ['수', '목', '금', '토', '일', '월', '화']
    last_hour = None

    for row in data:
        if len(row) < 5:
            continue
        hr_raw = row[0].strip()
        mn_raw = row[2].strip() if len(row) > 2 else ""

        if hr_raw:
            try:
                last_hour = int(hr_raw)
            except Exception:
                pass
        if last_hour is None:
            continue

        hour   = last_hour
        minute = 30 if ":30" in mn_raw else 0

        for i, day in enumerate(days):
            col_idx = i + 3
            if col_idx >= len(row):
                continue
            val = row[col_idx].strip()
            availability[(day, hour, minute)] = (val == "" or not _is_true(val))

    return availability


def get_all_availability(url: str) -> dict[str, dict]:
    try:
        spreadsheet = _get_spreadsheet(url)
        worksheets  = spreadsheet.worksheets()
        names_all   = [ws.title for ws in worksheets]
        if "종합시트" not in names_all:
            return {}
        start = names_all.index("종합시트") + 1
        names = [n for n in names_all[start:] if n != "데이터베이스"]
    except Exception as e:
        print(f"[sheets] get_all_availability 탭목록 오류: {e}")
        return {}

    days   = ['수', '목', '금', '토', '일', '월', '화']
    result = {}

    for name in names:
        try:
            sheet = spreadsheet.worksheet(name)
            data  = sheet.get_all_values()
        except Exception as e:
            print(f"[sheets] get_all_availability 오류({name}): {e}")
            continue

        availability = {}
        last_hour    = None

        for row in data:
            if len(row) < 5:
                continue
            hr_raw = row[0].strip()
            mn_raw = row[2].strip() if len(row) > 2 else ""

            if hr_raw:
                try:
                    last_hour = int(hr_raw)
                except Exception:
                    pass
            if last_hour is None:
                continue

            hour   = last_hour
            minute = 30 if ":30" in mn_raw else 0

            for i, day in enumerate(days):
                col_idx = i + 3
                if col_idx >= len(row):
                    continue
                val = row[col_idx].strip()
                availability[(day, hour, minute)] = (val == "" or not _is_true(val))

        result[name] = availability

    return result


def get_available_members_for_raid(url: str, day: str, hour: int, minute: int,
                                    all_availability: dict = None) -> list[str]:
    if all_availability is None:
        all_availability = get_all_availability(url)
    return [nick for nick, avail in all_availability.items()
            if avail.get((day, hour, minute), True)]


# ==================== 레이드 파싱 ====================

def parse_raids(data: list, guild_id: int = 0) -> list[dict]:
    """레이드 파싱 - ROW_SCHED가 O/TRUE인 것만"""
    if not data or len(data) <= ROW_DURATION:
        return []

    row_day      = data[ROW_DAY]
    row_hour     = data[ROW_HOUR]
    row_min      = data[ROW_MIN]
    row_fixed    = data[ROW_FIXED]
    row_sched    = data[ROW_SCHED]
    row_cleared  = data[ROW_CLEARED]
    row_name     = data[ROW_NAME]
    row_duration = data[ROW_DURATION]

    raids = []
    for col in range(4, len(row_name)):
        name = (row_name[col] if col < len(row_name) else "").strip()
        if not name:
            continue

        scheduled = _is_true(row_sched[col]) if col < len(row_sched) else False
        if not scheduled:
            continue

        day     = row_day[col]  if col < len(row_day)  else "미정"
        hr_raw  = row_hour[col] if col < len(row_hour) else "0"
        mn_raw  = row_min[col]  if col < len(row_min)  else ":00"
        fixed   = _is_true(row_fixed[col])   if col < len(row_fixed)   else False
        cleared = _is_true(row_cleared[col]) if col < len(row_cleared) else False
        dur_raw = row_duration[col] if col < len(row_duration) else "2"

        try:
            hour = int(hr_raw)
        except Exception:
            hour = 0
        minute = 30 if ":30" in str(mn_raw) else 0

        try:
            dur_min = int(dur_raw) * 30
        except Exception:
            dur_min = 60

        raids.append({
            'col':       col,
            'name':      name,
            'day':       day,
            'hour':      hour,
            'minute':    minute,
            'time_str':  f"{hour}:{minute:02d}",
            'scheduled': scheduled,
            'fixed':     fixed,
            'cleared':   cleared,
            'duration':  dur_min,
            'size':      get_raid_size(name),
        })

    day_order = {'수':0,'목':1,'금':2,'토':3,'일':4,'월':5,'화':6,'미정':7}
    raids.sort(key=lambda r: (day_order.get(r['day'], 7), r['hour'], r['minute']))
    return raids


def parse_all_raids(data: list, guild_id: int = 0) -> list[dict]:
    """전체 레이드 파싱 (미정 포함, scheduled 무관)"""
    if not data or len(data) <= ROW_DURATION:
        return []

    row_day      = data[ROW_DAY]
    row_hour     = data[ROW_HOUR]
    row_min      = data[ROW_MIN]
    row_fixed    = data[ROW_FIXED]
    row_sched    = data[ROW_SCHED]
    row_cleared  = data[ROW_CLEARED]
    row_name     = data[ROW_NAME]
    row_duration = data[ROW_DURATION]

    raids = []
    for col in range(4, len(row_name)):
        name = (row_name[col] if col < len(row_name) else "").strip()
        if not name:
            continue

        day       = row_day[col]  if col < len(row_day)  else "미정"
        hr_raw    = row_hour[col] if col < len(row_hour) else "0"
        mn_raw    = row_min[col]  if col < len(row_min)  else ":00"
        fixed     = _is_true(row_fixed[col])   if col < len(row_fixed)   else False
        scheduled = _is_true(row_sched[col])   if col < len(row_sched)   else False
        cleared   = _is_true(row_cleared[col]) if col < len(row_cleared) else False
        dur_raw   = row_duration[col] if col < len(row_duration) else "2"

        try:
            hour = int(hr_raw)
        except Exception:
            hour = 0
        minute = 30 if ":30" in str(mn_raw) else 0

        try:
            dur_min = int(dur_raw) * 30
        except Exception:
            dur_min = 60

        raids.append({
            'col':       col,
            'name':      name,
            'day':       day,
            'hour':      hour,
            'minute':    minute,
            'time_str':  f"{hour}:{minute:02d}",
            'scheduled': scheduled,
            'fixed':     fixed,
            'cleared':   cleared,
            'duration':  dur_min,
            'size':      get_raid_size(name),
        })

    day_order = {'수':0,'목':1,'금':2,'토':3,'일':4,'월':5,'화':6,'미정':7}
    raids.sort(key=lambda r: (day_order.get(r['day'], 7), r['hour'], r['minute']))
    return raids


# ==================== 길드원 파싱 ====================

def get_members(data: list, guild_id: int = 0) -> list[dict]:
    if not data or len(data) <= ROW_MEMBERS:
        return []

    members = []
    for row_idx in range(ROW_MEMBERS, len(data)):
        row = data[row_idx]
        if len(row) < 4:
            continue

        name   = row[3].strip() if row[3] else ""
        absent = _is_true(row[2])

        if not name or name in ["인원수", "특이사항", ""]:
            break

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
    for m in get_members(data, guild_id):
        if m['name'] == nickname or nickname in m['name']:
            return m['row_idx']
    return None


# ==================== 개인 일정 ====================

def get_user_schedule(data: list, nickname: str, guild_id: int = 0) -> list[dict]:
    members  = get_members(data, guild_id)
    raids    = parse_raids(data, guild_id)
    raid_map = {r['col']: r for r in raids}

    member = next((m for m in members if m['name'] == nickname or nickname in m['name']), None)
    if not member:
        return []

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
            'size':       raid['size'],
        })

    day_order = {'수':0,'목':1,'금':2,'토':3,'일':4,'월':5,'화':6,'미정':7}
    schedule.sort(key=lambda s: (day_order.get(s['day'], 7), s['hour'], s['minute']))
    return schedule


def get_all_user_schedule(data: list, nickname: str, guild_id: int = 0) -> list[dict]:
    members   = get_members(data, guild_id)
    all_raids = parse_all_raids(data, guild_id)
    raid_map  = {r['col']: r for r in all_raids}

    member = next((m for m in members if m['name'] == nickname or nickname in m['name']), None)
    if not member:
        return []

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
            'size':       raid['size'],
        })

    day_order = {'수':0,'목':1,'금':2,'토':3,'일':4,'월':5,'화':6,'미정':7}
    schedule.sort(key=lambda s: (day_order.get(s['day'], 7), s['hour'], s['minute']))
    return schedule


# ==================== 전체 레이드 요약 ====================

def get_weekly_summary(data: list, guild_id: int = 0) -> list[dict]:
    return _build_summary(parse_raids(data, guild_id), get_members(data, guild_id))


def get_remaining_summary(data: list, guild_id: int = 0) -> list[dict]:
    raids = [r for r in parse_raids(data, guild_id) if not r['cleared']]
    return _build_summary(raids, get_members(data, guild_id))


def get_all_weekly_summary(data: list, guild_id: int = 0) -> list[dict]:
    return _build_summary(parse_all_raids(data, guild_id), get_members(data, guild_id))


def _build_summary(raids: list, members: list) -> list[dict]:
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


# ==================== AI 편성 (가능시간 기반) ====================

def get_raid_members_by_availability(url: str, data: list,
                                      raid: dict, guild_id: int = 0,
                                      all_availability: dict = None) -> list[dict]:
    members   = get_members(data, guild_id)
    all_avail = all_availability if all_availability is not None else get_all_availability(url)
    day, hour, minute = raid['day'], raid['hour'], raid['minute']
    col       = raid['col']

    result = []
    for m in members:
        if m['absent']:
            continue
        char_info = m['characters'].get(col)
        if not char_info:
            continue
        name = m['name']
        if not raid.get('fixed', False):
            avail = all_avail.get(name, {})
            if not avail.get((day, hour, minute), True):
                continue
        result.append({
            'name':       name,
            'character':  char_info['raw'],
            'std_job':    char_info['std_job'],
            'is_support': char_info['is_support'],
            'is_alt':     char_info['is_alt'],
        })
    return result


# ==================== AI 편성 결과 저장 ====================

def save_party_result(url: str, raid_name: str, parties: list) -> bool:
    return save_all_party_results(url, [(raid_name, parties)])


def save_all_party_results(url: str, raid_parties: list) -> bool:
    try:
        spreadsheet = _get_spreadsheet(url)
        try:
            sheet = spreadsheet.worksheet("AI편성결과")
        except Exception:
            sheet = spreadsheet.add_worksheet(title="AI편성결과", rows=1000, cols=20)

        all_values = sheet.get_all_values()
        now_str    = datetime.now().strftime("%m/%d %H:%M")
        raid_names = {name for name, _ in raid_parties}

        cleaned = []
        skip = False
        for row in all_values:
            val = row[0] if row else ""
            if val.startswith("["):
                raid_in_row = val.split("]")[0][1:] if "]" in val else ""
                skip = raid_in_row in raid_names
            if not skip:
                cleaned.append(row)

        new_blocks = []
        for raid_name, parties in raid_parties:
            new_blocks.append([f"[{raid_name}] — {now_str} 편성"])
            for i, party in enumerate(parties, 1):
                members_str = " / ".join(m.get('character', m.get('name', '')) for m in party)
                new_blocks.append([f"파티{i}: {members_str}"])
            new_blocks.append([""])

        final = cleaned + new_blocks
        sheet.clear()
        if final:
            sheet.update("A1", final)

        print(f"[sheets] save_all_party_results 완료: {len(raid_parties)}개")
        return True
    except Exception as e:
        print(f"[sheets] save_all_party_results 오류: {e}")
        return False


# ==================== 레이드 쓰기 ====================

def _get_raid_sheet(url: str, ai: bool = False):
    name = SHEET_AI_RAID if ai else SHEET_RAID
    return _get_spreadsheet(url).worksheet(name)


def add_raid(url: str, name: str, day: str, hour: int, minute: int,
             duration_blocks: int = 2) -> bool:
    try:
        sheet = _get_raid_sheet(url)
        data  = sheet.get_all_values()
        if not data or len(data) <= ROW_NAME:
            return False

        row_name = data[ROW_NAME]
        last_col = 4
        for col in range(4, len(row_name)):
            if row_name[col].strip():
                last_col = col
        new_col = last_col + 1
        min_str = ":30" if minute == 30 else ":00"

        updates = [
            (ROW_DAY+1,      day),
            (ROW_HOUR+1,     str(hour)),
            (ROW_MIN+1,      min_str),
            (ROW_FIXED+1,    ""),
            (ROW_SCHED+1,    "O"),
            (ROW_CLEARED+1,  ""),
            (ROW_NAME+1,     name),
            (ROW_DURATION+1, str(duration_blocks)),
        ]
        for row_num, value in updates:
            sheet.update_cell(row_num, new_col + 1, value)

        print(f"[sheets] add_raid 완료: {name}")
        return True
    except Exception as e:
        print(f"[sheets] add_raid 오류: {e}")
        return False


def update_raid(url: str, col: int, name: str = None, day: str = None,
                hour: int = None, minute: int = None, duration_blocks: int = None) -> bool:
    try:
        sheet     = _get_raid_sheet(url)
        sheet_col = col + 1
        if day is not None:             sheet.update_cell(ROW_DAY+1,      sheet_col, day)
        if hour is not None:            sheet.update_cell(ROW_HOUR+1,     sheet_col, str(hour))
        if minute is not None:          sheet.update_cell(ROW_MIN+1,      sheet_col, ":30" if minute==30 else ":00")
        if name is not None:            sheet.update_cell(ROW_NAME+1,     sheet_col, name)
        if duration_blocks is not None: sheet.update_cell(ROW_DURATION+1, sheet_col, str(duration_blocks))
        return True
    except Exception as e:
        print(f"[sheets] update_raid 오류: {e}")
        return False


def delete_raid(url: str, col: int) -> bool:
    try:
        sheet     = _get_raid_sheet(url)
        data      = sheet.get_all_values()
        sheet_col = col + 1
        for row_num in range(1, ROW_MEMBERS + 1):
            sheet.update_cell(row_num, sheet_col, "")
        if len(data) > ROW_MEMBERS:
            for row_num in range(ROW_MEMBERS + 1, len(data) + 1):
                sheet.update_cell(row_num, sheet_col, "")
        return True
    except Exception as e:
        print(f"[sheets] delete_raid 오류: {e}")
        return False


def set_scheduled(url: str, col: int, scheduled: bool) -> bool:
    try:
        _get_raid_sheet(url).update_cell(ROW_SCHED+1, col+1, "O" if scheduled else "")
        return True
    except Exception as e:
        print(f"[sheets] set_scheduled 오류: {e}")
        return False


def set_cleared(url: str, col: int, cleared: bool) -> bool:
    try:
        _get_raid_sheet(url).update_cell(ROW_CLEARED+1, col+1, "O" if cleared else "")
        return True
    except Exception as e:
        print(f"[sheets] set_cleared 오류: {e}")
        return False


def set_fixed(url: str, col: int, fixed: bool) -> bool:
    try:
        _get_raid_sheet(url).update_cell(ROW_FIXED+1, col+1, "O" if fixed else "")
        return True
    except Exception as e:
        print(f"[sheets] set_fixed 오류: {e}")
        return False


def _col_to_letter(col: int) -> str:
    result = ""
    while col > 0:
        col, remainder = divmod(col - 1, 26)
        result = chr(65 + remainder) + result
    return result


# ==================== 레이드 우선순위 ====================

def _parse_raid_level(raid_name: str) -> tuple:
    """레이드명으로 (ilvl, category) 반환"""
    for base, diffs in RAID_LEVEL_MAP.items():
        if base in raid_name:
            info = _match_difficulty(diffs, raid_name)
            return (info['ilvl'], info['category'])
    return (0, 9)


def get_raid_priority_key(raid: dict) -> tuple:
    level, cat = _parse_raid_level(raid.get('name', ''))
    return (-level, cat)


# ==================== 시간 배정 ====================

def assign_raid_times(url: str, data: list, guild_id: int = 0) -> list[dict]:
    from collections import Counter

    all_raids = parse_all_raids(data, guild_id)
    members   = get_members(data, guild_id)
    all_avail = get_all_availability(url)

    fixed_raids  = sorted([r for r in all_raids if r.get('fixed')],     key=get_raid_priority_key)
    normal_raids = sorted([r for r in all_raids if not r.get('fixed')], key=get_raid_priority_key)
    sorted_raids = fixed_raids + normal_raids

    assigned_times: dict[str, list] = {}
    DAY_ORDER = {'수':0,'목':1,'금':2,'토':3,'일':4,'월':5,'화':6}

    def _best_slot(raid_members):
        member_avail = {}
        for m in raid_members:
            name    = m['name']
            avail   = all_avail.get(name, {})
            blocked = {(d, h, mi) for d, h, mi, _ in assigned_times.get(name, [])}
            possible = {slot for slot, ok in avail.items() if ok and slot not in blocked}
            member_avail[name] = possible

        slot_count: Counter = Counter()
        for possible in member_avail.values():
            for slot in possible:
                slot_count[slot] += 1

        if not slot_count:
            return None, member_avail

        max_count  = max(slot_count.values())
        candidates = [s for s, c in slot_count.items() if c == max_count]
        candidates.sort(key=lambda s: (DAY_ORDER.get(s[0], 7), s[1], s[2]))
        return candidates[0], member_avail

    def _make_parties(sups, dps, size=8):
        if size == 4:
            return [dps + sups] if (dps or sups) else []
        elif size == 16:
            # 16인: 서폿 없이 단일 파티
            return [dps + sups] if (dps or sups) else []
        else:  # 8인
            if sups:
                p1_sup  = sups[:1]
                p2_sup  = sups[1:2]
                extra   = sups[2:]
                all_dps = dps + extra
            else:
                p1_sup  = []
                p2_sup  = []
                all_dps = dps
            half = len(all_dps) // 2
            p1 = all_dps[:half + len(all_dps) % 2] + p1_sup
            p2 = all_dps[half + len(all_dps) % 2:] + p2_sup
            return [p for p in [p1, p2] if p]

    results = []

    for raid in sorted_raids:
        col       = raid['col']
        raid_name = raid['name']
        raid_size = raid.get('size', get_raid_size(raid_name))  # 파싱된 size 우선

        raid_members = []
        for m in members:
            if m.get('absent'):
                continue
            char_info = m['characters'].get(col)
            if not char_info:
                continue
            raid_members.append({
                'name':       m['name'],
                'character':  char_info['raw'],
                'std_job':    char_info['std_job'],
                'is_support': char_info['is_support'],
                'is_alt':     char_info['is_alt'],
            })

        if len(raid_members) == 0:
            continue

        if len(raid_members) == 1:
            results.append({
                'raid':            raid,
                'assigned_day':    '미정',
                'assigned_hour':   0,
                'assigned_minute': 0,
                'time_str':        '미정',
                'members':         raid_members,
                'parties':         [],
                'conflicts':       [],
            })
            continue

        best_slot, member_avail = _best_slot(raid_members)

        if best_slot:
            bday, bhour, bminute = best_slot
            btime_str = f"{bhour}:{bminute:02d}"
            final_members = [
                m for m in raid_members
                if best_slot in member_avail.get(m['name'], set())
            ]
            conflicts = []
            for m in final_members:
                name = m['name']
                for d, h, mi, other_raid in assigned_times.get(name, []):
                    if (d, h, mi) == best_slot:
                        conflicts.append({'name': name, 'other_raid': other_raid})
            for m in final_members:
                assigned_times.setdefault(m['name'], []).append(
                    (bday, bhour, bminute, raid_name)
                )
        else:
            bday, bhour, bminute, btime_str = '미정', 0, 0, '미정'
            final_members = raid_members
            conflicts     = []

        supports = [m for m in final_members if m.get('is_support')]
        dps_list = [m for m in final_members if not m.get('is_support')]
        sup_needed = 1 if raid_size == 4 else (0 if raid_size == 16 else 2)
        max_dps    = (raid_size - sup_needed) * max(len(supports), 1)
        parties    = _make_parties(supports, dps_list[:max_dps], raid_size)

        results.append({
            'raid':            raid,
            'assigned_day':    bday,
            'assigned_hour':   bhour,
            'assigned_minute': bminute,
            'time_str':        btime_str,
            'members':         final_members,
            'parties':         parties,
            'conflicts':       conflicts,
        })

    return results


def save_assigned_times(url: str, assignments: list) -> bool:
    try:
        sheet   = _get_raid_sheet(url, ai=True)
        updates = []
        for a in assignments:
            col    = a['raid']['col']
            day    = a['assigned_day']
            hour   = a['assigned_hour']
            minute = a['assigned_minute']
            if day == '미정':
                continue
            col_letter = _col_to_letter(col + 1)
            updates += [
                {'range': f"{col_letter}{ROW_DAY+1}",   'values': [[day]]},
                {'range': f"{col_letter}{ROW_HOUR+1}",  'values': [[str(hour)]]},
                {'range': f"{col_letter}{ROW_MIN+1}",   'values': [[f":{minute:02d}"]]},
                {'range': f"{col_letter}{ROW_SCHED+1}", 'values': [["O"]]},
            ]
        if updates:
            sheet.batch_update(updates)
        print(f"[sheets] save_assigned_times 완료: {len(assignments)}개")
        return True
    except Exception as e:
        print(f"[sheets] save_assigned_times 오류: {e}")
        return False


def copy_ai_to_manual(url: str) -> bool:
    try:
        ss     = _get_spreadsheet(url)
        src    = ss.worksheet(SHEET_AI_RAID)
        dst    = ss.worksheet(SHEET_RAID)
        values = src.get_all_values()
        if not values:
            print("[sheets] AI편성 탭이 비어있음")
            return False
        dst.clear()
        dst.update(values, value_input_option="USER_ENTERED")
        print(f"[sheets] AI편성 → 주간레이드 복사 완료 ({len(values)}행)")
        return True
    except Exception as e:
        print(f"[sheets] copy_ai_to_manual 오류: {e}")
        return False