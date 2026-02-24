"""
로일(LoIl) - 구글 시트 파싱 유틸
resolver.py를 통해 별명/서폿 판별 자동화
"""

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

    day_order = {'수':0,'목':1,'금':2,'토':3,'일':4,'월':5,'화':6,'미정':7}
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

    day_order = {'수':0,'목':1,'금':2,'토':3,'일':4,'월':5,'화':6,'미정':7}
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

    day_order = {'수':0,'목':1,'금':2,'토':3,'일':4,'월':5,'화':6,'미정':7}
    schedule.sort(key=lambda s: (day_order.get(s['day'], 7), s['hour'], s['minute']))
    return schedule


def get_all_user_schedule(data: list, nickname: str, guild_id: int = 0) -> list[dict]:
    """
    특정 길드원의 전체 일정 (미정 포함)
    """
    members   = get_members(data, guild_id)
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

    day_order = {'수':0,'목':1,'금':2,'토':3,'일':4,'월':5,'화':6,'미정':7}
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


# ==================== AI 편성 결과 저장 ====================

def save_party_result(url: str, raid_name: str, parties: list) -> bool:
    """
    AI 편성 결과를 구글 시트 'AI편성결과' 탭에 저장
    탭 없으면 자동 생성
    저장 형식:
    [종막(노)1] — 02/20 21:30 편성
    파티1: 워로드 / 홀나 / 스커 / 디트
    파티2: 블레이드 / 바드 / 소서
    """
    try:
        client      = _get_client()
        spreadsheet = client.open_by_url(url)

        # AI편성결과 탭 찾기 or 자동 생성
        try:
            sheet = spreadsheet.worksheet("AI편성결과")
        except Exception:
            sheet = spreadsheet.add_worksheet(title="AI편성결과", rows=500, cols=20)

        all_values = sheet.get_all_values()
        now_str    = datetime.now().strftime("%m/%d %H:%M")

        # 새 블록 생성
        block = [[f"[{raid_name}] — {now_str} 편성"]]
        for i, party in enumerate(parties, 1):
            members_str = " / ".join([
                m.get('character', m.get('name', ''))
                for m in party
            ])
            block.append([f"파티{i}: {members_str}"])
        block.append([""])  # 빈 줄 구분

        # 기존 같은 레이드 블록 위치 찾기
        target_row = None
        for i, row in enumerate(all_values):
            if row and row[0].startswith(f"[{raid_name}]"):
                target_row = i + 1  # 1-indexed
                break

        if target_row:
            # 기존 블록 끝 찾기
            end_row = target_row
            for i in range(target_row, len(all_values)):
                val = all_values[i][0] if all_values[i] else ""
                if i > target_row - 1 and val.startswith("["):
                    break
                end_row = i + 1
            sheet.batch_clear([f"A{target_row}:A{end_row}"])
            sheet.update(f"A{target_row}", block)
        else:
            # 맨 아래에 추가
            next_row = len(all_values) + 2
            sheet.update(f"A{next_row}", block)

        print(f"[sheets] save_party_result 완료: {raid_name}")
        return True

    except Exception as e:
        print(f"[sheets] save_party_result 오류: {e}")
        return False
    


    """
로일(LoIl) - sheets.py 추가 함수
기존 sheets.py 맨 아래에 붙여넣기

레이드 쓰기 함수:
- add_raid()    : 레이드 추가 (새 컬럼)
- update_raid() : 레이드 수정
- delete_raid() : 레이드 삭제 (컬럼 클리어)
- set_scheduled(): scheduled TRUE/FALSE 토글
"""

# ==================== 레이드 쓰기 ====================

def _get_raid_sheet(url: str):
    """주간레이드 시트 객체 반환"""
    client      = _get_client()
    spreadsheet = client.open_by_url(url)
    return spreadsheet.worksheet("주간레이드")


def add_raid(url: str, name: str, day: str, hour: int, minute: int, duration_blocks: int = 1) -> bool:
    """
    레이드 추가 - 맨 끝 컬럼에 추가
    duration_blocks: 1=30분, 2=1시간, 3=1시간30분...
    """
    try:
        sheet = _get_raid_sheet(url)
        data  = sheet.get_all_values()

        if not data or len(data) < 7:
            print("[sheets] add_raid: 시트 데이터 부족")
            return False

        # 마지막 레이드 컬럼 찾기 (Row 6 = 레이드명 행)
        row_name = data[5]  # 0-indexed
        last_col = 4  # E열부터 시작
        for col in range(4, len(row_name)):
            if row_name[col].strip():
                last_col = col

        new_col = last_col + 1  # 새 컬럼 위치 (0-indexed)
        col_letter = _col_to_letter(new_col + 1)  # gspread는 1-indexed

        # 분 표기 (:00 or :30)
        min_str = ":30" if minute == 30 else ":00"

        # Row 1~7 업데이트
        updates = [
            (1, day),               # 요일
            (2, str(hour)),         # 시간
            (3, min_str),           # 분
            (4, "TRUE"),            # scheduled
            (5, "FALSE"),           # cleared
            (6, name),              # 레이드명
            (7, str(duration_blocks)),  # 예상시간 (블록수)
        ]

        for row_num, value in updates:
            sheet.update_cell(row_num, new_col + 1, value)

        print(f"[sheets] add_raid 완료: {name} ({day} {hour}:{minute:02d})")
        return True

    except Exception as e:
        print(f"[sheets] add_raid 오류: {e}")
        return False


def update_raid(url: str, col: int, name: str = None, day: str = None,
                hour: int = None, minute: int = None, duration_blocks: int = None) -> bool:
    """
    레이드 수정 - col은 0-indexed
    None인 항목은 변경하지 않음
    """
    try:
        sheet    = _get_raid_sheet(url)
        sheet_col = col + 1  # gspread 1-indexed

        if day is not None:
            sheet.update_cell(1, sheet_col, day)
        if hour is not None:
            sheet.update_cell(2, sheet_col, str(hour))
        if minute is not None:
            min_str = ":30" if minute == 30 else ":00"
            sheet.update_cell(3, sheet_col, min_str)
        if name is not None:
            sheet.update_cell(6, sheet_col, name)
        if duration_blocks is not None:
            sheet.update_cell(7, sheet_col, str(duration_blocks))

        print(f"[sheets] update_raid 완료: col={col}")
        return True

    except Exception as e:
        print(f"[sheets] update_raid 오류: {e}")
        return False


def delete_raid(url: str, col: int) -> bool:
    """
    레이드 삭제 - 해당 컬럼 Row 1~7 클리어 + scheduled=FALSE
    col은 0-indexed
    """
    try:
        sheet     = _get_raid_sheet(url)
        data      = sheet.get_all_values()
        sheet_col = col + 1  # gspread 1-indexed

        # Row 1~7 클리어
        for row_num in range(1, 8):
            sheet.update_cell(row_num, sheet_col, "")

        # 길드원 행도 해당 컬럼 클리어
        if len(data) > 7:
            for row_num in range(8, len(data) + 1):
                sheet.update_cell(row_num, sheet_col, "")

        print(f"[sheets] delete_raid 완료: col={col}")
        return True

    except Exception as e:
        print(f"[sheets] delete_raid 오류: {e}")
        return False


def set_scheduled(url: str, col: int, scheduled: bool) -> bool:
    """
    레이드 예정 여부 토글
    col은 0-indexed
    """
    try:
        sheet     = _get_raid_sheet(url)
        sheet_col = col + 1
        sheet.update_cell(4, sheet_col, "TRUE" if scheduled else "FALSE")
        print(f"[sheets] set_scheduled: col={col} → {scheduled}")
        return True
    except Exception as e:
        print(f"[sheets] set_scheduled 오류: {e}")
        return False


def set_cleared(url: str, col: int, cleared: bool) -> bool:
    """
    레이드 클리어 여부 업데이트
    col은 0-indexed
    """
    try:
        sheet     = _get_raid_sheet(url)
        sheet_col = col + 1
        sheet.update_cell(5, sheet_col, "TRUE" if cleared else "FALSE")
        print(f"[sheets] set_cleared: col={col} → {cleared}")
        return True
    except Exception as e:
        print(f"[sheets] set_cleared 오류: {e}")
        return False


def _col_to_letter(col: int) -> str:
    """컬럼 번호 → 알파벳 (1=A, 27=AA...)"""
    result = ""
    while col > 0:
        col, remainder = divmod(col - 1, 26)
        result = chr(65 + remainder) + result
    return result