"""
Google Sheets 유틸리티
- 시트 연결 및 인증
- 일정 데이터 읽기
- 유저별 일정 검색
- 데이터 파싱
"""

import gspread
from google.oauth2.service_account import Credentials
from typing import Optional, List, Dict
from bot.config.settings import GOOGLE_CREDENTIALS_PATH, GOOGLE_SHEETS_SCOPE

# ==================== Google Sheets 연결 ====================

def get_sheets_client() -> Optional[gspread.Client]:
    """
    Google Sheets 클라이언트 생성
    
    Returns:
        gspread.Client 또는 None
    
    Example:
        >>> client = get_sheets_client()
        >>> sheet = client.open_by_url("https://...")
    """
    try:
        creds = Credentials.from_service_account_file(
            GOOGLE_CREDENTIALS_PATH,
            scopes=GOOGLE_SHEETS_SCOPE
        )
        client = gspread.authorize(creds)
        return client
    
    except FileNotFoundError:
        print(f"❌ credentials.json 파일을 찾을 수 없습니다: {GOOGLE_CREDENTIALS_PATH}")
        return None
    
    except Exception as e:
        print(f"❌ Google Sheets 인증 실패: {e}")
        return None


def open_sheet_by_url(url: str) -> Optional[gspread.Spreadsheet]:
    """
    URL로 시트 열기
    
    Args:
        url: Google Sheets URL
    
    Returns:
        Spreadsheet 객체 또는 None
    
    Example:
        >>> sheet = open_sheet_by_url("https://docs.google.com/spreadsheets/d/...")
        >>> print(sheet.title)
    """
    client = get_sheets_client()
    if not client:
        return None
    
    try:
        spreadsheet = client.open_by_url(url)
        return spreadsheet
    
    except gspread.exceptions.SpreadsheetNotFound:
        print(f"❌ 시트를 찾을 수 없습니다. 권한을 확인하세요.")
        return None
    
    except Exception as e:
        print(f"❌ 시트 열기 실패: {e}")
        return None


# ==================== 일정 데이터 읽기 ====================

def get_all_data(url: str, worksheet_index: int = 0) -> Optional[List[List[str]]]:
    """
    시트의 모든 데이터 가져오기
    
    Args:
        url: Google Sheets URL
        worksheet_index: 워크시트 인덱스 (기본: 0)
    
    Returns:
        2D 리스트 (행x열) 또는 None
    
    Example:
        >>> data = get_all_data("https://...")
        >>> print(data[0])  # 첫 번째 행 (헤더)
    """
    spreadsheet = open_sheet_by_url(url)
    if not spreadsheet:
        return None
    
    try:
        worksheet = spreadsheet.get_worksheet(worksheet_index)
        data = worksheet.get_all_values()
        return data
    
    except Exception as e:
        print(f"❌ 데이터 읽기 실패: {e}")
        return None


def get_worksheet_names(url: str) -> Optional[List[str]]:
    """
    시트의 모든 워크시트 이름 가져오기
    
    Args:
        url: Google Sheets URL
    
    Returns:
        워크시트 이름 리스트 또는 None
    
    Example:
        >>> names = get_worksheet_names("https://...")
        >>> print(names)
        ['주간레이드', '개인 숙제', '종합시트']
    """
    spreadsheet = open_sheet_by_url(url)
    if not spreadsheet:
        return None
    
    try:
        worksheets = spreadsheet.worksheets()
        return [ws.title for ws in worksheets]
    
    except Exception as e:
        print(f"❌ 워크시트 목록 가져오기 실패: {e}")
        return None


# ==================== 유저 일정 검색 ====================

def find_user_row(data: List[List[str]], username: str, name_col: int = 3) -> Optional[int]:
    """
    시트에서 유저 이름이 있는 행 찾기
    
    Args:
        data: 시트 데이터
        username: 찾을 유저 이름
        name_col: 유저 이름이 있는 열 (기본: 3)
    
    Returns:
        행 인덱스 또는 None
    """
    for i, row in enumerate(data):
        if len(row) > name_col:
            if username in str(row[name_col]):
                return i
    return None


def find_user_column(data: List[List[str]], username: str, max_header_rows: int = 10) -> Optional[int]:
    """
    헤더에서 유저 이름 찾기 (여러 행 검색)
    
    Args:
        data: 시트 데이터 (2D 리스트)
        username: 찾을 유저 이름
        max_header_rows: 검색할 헤더 행 수 (기본: 10)
    
    Returns:
        열 인덱스 또는 None
    """
    if not data or len(data) < 1:
        return None
    
    # 전체 행에서 검색
    for row in data[:max_header_rows]:
        for i, cell in enumerate(row):
            if username in str(cell):
                return i
    
    return None


def get_user_schedule(data: List[List[str]], username: str, name_col: int = 3, start_raid_col: int = 4) -> List[Dict]:
    """
    특정 유저의 레이드별 참여 정보 가져오기
    
    Args:
        data: 시트 데이터
        username: 유저 이름
        name_col: 유저 이름 열 (기본: 3)
        start_raid_col: 레이드 시작 열 (기본: 4)
    
    Returns:
        레이드별 참여 정보 리스트
    """
    user_row = find_user_row(data, username, name_col)
    
    if user_row is None:
        return []
    
    row = data[user_row]
    schedules = []
    
    # 레이드별 참여 정보 수집
    for col_idx in range(start_raid_col, len(row)):
        character = row[col_idx]
        
        # 참여하는 경우만
        if character and character.strip() and character != "미참여":
            # 레이드명 찾기 (Row 6의 같은 열)
            raid_name = ''
            date = ''
            time = ''
            
            # 헤더 행들에서 레이드 정보 찾기
            for header_row in data[:10]:
                if len(header_row) > col_idx:
                    val = header_row[col_idx]
                    if val and val not in ['미정', 'FALSE', 'TRUE', '']:
                        raid_name = val
                        break
            
            schedules.append({
                'raid': raid_name,
                'character': character,
                'col': col_idx,
                'row': user_row
            })
    
    return schedules


# ==================== 데이터 파싱 ====================

def parse_raid_schedule(data: List[List[str]]) -> List[Dict]:
    """
    전체 레이드 일정 파싱
    
    Args:
        data: 시트 데이터
    
    Returns:
        일정 리스트
        [
            {
                'raid': str,
                'date': str,
                'time': str,
                'members': List[str],
                'row': int
            },
            ...
        ]
    
    Example:
        >>> schedules = parse_raid_schedule(data)
        >>> for s in schedules:
        ...     print(f"{s['raid']}: {len(s['members'])}명")
    """
    if not data or len(data) < 2:
        return []
    
    headers = data[0]
    schedules = []
    
    for i, row in enumerate(data[1:], start=2):
        if len(row) < 3:
            continue
        
        # 멤버 수집 (3번째 열부터)
        members = []
        for cell in row[3:]:
            if cell and cell.strip() and cell != "미참여":
                members.append(cell.strip())
        
        schedule = {
            'raid': row[0] if len(row) > 0 else '',
            'date': row[1] if len(row) > 1 else '',
            'time': row[2] if len(row) > 2 else '',
            'members': members,
            'row': i
        }
        
        # 레이드명이 있는 경우만
        if schedule['raid']:
            schedules.append(schedule)
    
    return schedules


def get_weekly_schedule(data: List[List[str]], day_filter: Optional[str] = None) -> List[Dict]:
    """
    주간 일정 가져오기 (요일 필터링 가능)
    
    Args:
        data: 시트 데이터
        day_filter: 요일 필터 (예: "월", "화", None=전체)
    
    Returns:
        필터링된 일정 리스트
    
    Example:
        >>> today = get_weekly_schedule(data, "수")
        >>> for s in today:
        ...     print(f"{s['time']} - {s['raid']}")
    """
    schedules = parse_raid_schedule(data)
    
    if not day_filter:
        return schedules
    
    # 요일 필터링
    filtered = []
    for schedule in schedules:
        if day_filter in schedule['date']:
            filtered.append(schedule)
    
    return filtered


# ==================== 유틸리티 함수 ====================

def get_sheet_info(url: str) -> Optional[Dict]:
    """
    시트 정보 가져오기
    
    Args:
        url: Google Sheets URL
    
    Returns:
        시트 정보 딕셔너리
        {
            'title': str,
            'worksheets': List[str],
            'total_rows': int,
            'total_cols': int
        }
    
    Example:
        >>> info = get_sheet_info("https://...")
        >>> print(f"시트명: {info['title']}")
    """
    spreadsheet = open_sheet_by_url(url)
    if not spreadsheet:
        return None
    
    try:
        worksheet = spreadsheet.get_worksheet(0)
        data = worksheet.get_all_values()
        
        return {
            'title': spreadsheet.title,
            'worksheets': [ws.title for ws in spreadsheet.worksheets()],
            'total_rows': len(data),
            'total_cols': len(data[0]) if data else 0
        }
    
    except Exception as e:
        print(f"❌ 시트 정보 가져오기 실패: {e}")
        return None


def search_in_sheet(data: List[List[str]], keyword: str) -> List[Dict]:
    """
    시트에서 키워드 검색
    
    Args:
        data: 시트 데이터
        keyword: 검색 키워드
    
    Returns:
        검색 결과 리스트
        [
            {
                'row': int,
                'col': int,
                'value': str
            },
            ...
        ]
    
    Example:
        >>> results = search_in_sheet(data, "에기르")
        >>> for r in results:
        ...     print(f"({r['row']}, {r['col']}): {r['value']}")
    """
    results = []
    
    for row_idx, row in enumerate(data):
        for col_idx, cell in enumerate(row):
            if keyword in str(cell):
                results.append({
                    'row': row_idx + 1,  # 1-indexed
                    'col': col_idx + 1,
                    'value': cell
                })
    
    return results


# ==================== 테스트 코드 ====================

if __name__ == "__main__":
    print("=" * 50)
    print("🧪 Google Sheets 유틸리티 테스트")
    print("=" * 50)
    
    # URL 하드코딩 (테스트 편의용)
    DEFAULT_URL = "https://docs.google.com/spreadsheets/d/1GIHnWAE8gJggDeFVCGSFJgVml7DEAItmoe0TIBfLxS4/edit"
    
    test_url = input(f"\n시트 URL (Enter로 기본값 사용): ").strip()
    if not test_url:
        test_url = DEFAULT_URL
        print(f"기본 URL 사용: {test_url[:60]}...\n")
    
    print()
    
    # 시트 정보
    info = get_sheet_info(test_url)
    if info:
        print(f"✅ 시트 정보:")
        print(f"  - 제목: {info['title']}")
        print(f"  - 워크시트: {len(info['worksheets'])}개")
        print(f"  - 크기: {info['total_rows']}행 x {info['total_cols']}열\n")
    
    # 데이터 읽기
    data = get_all_data(test_url)
    if data:
        print(f"✅ 데이터 읽기 성공: {len(data)}행\n")
        
        # 유저 검색
        username = input("찾을 유저 이름 (Enter로 건너뛰기): ").strip()
        if username:
            print()
            
            print(f"🔍 '{username}' 검색 중...")
            user_row = find_user_row(data, username)
            print(f"  - 찾은 행: {user_row}")
            if user_row is not None:
                print(f"  - 해당 행 데이터: {data[user_row][:6]}")
            print()
            
            schedules = get_user_schedule(data, username)
            
            if schedules:
                print(f"✅ '{username}' 참여 레이드: {len(schedules)}개\n")
                for s in schedules[:10]:
                    print(f"  - {s['raid']} → {s['character']}")
            else:
                print(f"❌ '{username}' 일정을 찾을 수 없습니다.")
    
    print("\n✅ 테스트 완료!\n")