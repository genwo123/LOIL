"""
Google Sheets 테스트
- 시트 읽기 테스트
- 일정 데이터 파싱 테스트
"""

import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
from config.settings import GOOGLE_CREDENTIALS_PATH, GOOGLE_SHEETS_SCOPE

def test_sheets_connection():
    """Google Sheets 연결 테스트"""
    print("=" * 50)
    print("🔗 Google Sheets 연결 테스트")
    print("=" * 50)
    
    try:
        # 인증 설정 (settings.py에서 가져옴)
        creds = Credentials.from_service_account_file(
            GOOGLE_CREDENTIALS_PATH,
            scopes=GOOGLE_SHEETS_SCOPE
        )
        
        client = gspread.authorize(creds)
        
        print("✅ Google Sheets 인증 성공!\n")
        return client
        
    except FileNotFoundError:
        print(f"❌ {GOOGLE_CREDENTIALS_PATH} 파일이 없습니다!")
        print("Google Cloud Console에서 Service Account 키를 발급받아주세요.\n")
        return None
        
    except Exception as e:
        print(f"❌ 에러 발생: {e}\n")
        return None


def test_read_sheet(client, sheet_url):
    """시트 읽기 테스트"""
    print("=" * 50)
    print("📖 시트 읽기 테스트")
    print("=" * 50)
    
    try:
        # 시트 열기
        spreadsheet = client.open_by_url(sheet_url)
        print(f"✅ 시트 열기 성공: {spreadsheet.title}\n")
        
        # 워크시트 목록
        worksheets = spreadsheet.worksheets()
        print(f"📋 워크시트 목록 ({len(worksheets)}개):")
        for ws in worksheets:
            print(f"  - {ws.title}")
        print()
        
        # 첫 번째 시트 읽기
        sheet = spreadsheet.get_worksheet(0)
        print(f"📄 읽는 시트: {sheet.title}")
        
        # 전체 데이터 가져오기
        data = sheet.get_all_values()
        print(f"✅ 데이터 읽기 성공: {len(data)}행\n")
        
        # 처음 5행 출력
        print("처음 5행 미리보기:")
        print("-" * 50)
        for i, row in enumerate(data[:5]):
            print(f"Row {i+1}: {row[:5]}...")  # 처음 5열만
        print("-" * 50)
        print()
        
        return data
        
    except Exception as e:
        print(f"❌ 에러 발생: {e}\n")
        return None


def test_parse_schedule(data):
    """일정 데이터 파싱 테스트"""
    print("=" * 50)
    print("🔍 일정 데이터 파싱 테스트")
    print("=" * 50)
    
    try:
        if not data or len(data) < 2:
            print("❌ 데이터가 충분하지 않습니다.\n")
            return False
        
        # 헤더 확인 (첫 번째 행)
        headers = data[0]
        print(f"📌 헤더: {headers[:10]}...")  # 처음 10개만
        print()
        
        # 데이터 파싱 예시
        print("📊 일정 데이터 파싱:")
        print("-" * 50)
        
        # 간단한 파싱 (실제로는 더 복잡함)
        schedules = []
        for i, row in enumerate(data[1:11], start=2):  # 2-11행
            if len(row) > 3:
                schedule = {
                    'row': i,
                    'raid': row[0] if len(row) > 0 else '',
                    'date': row[1] if len(row) > 1 else '',
                    'time': row[2] if len(row) > 2 else '',
                    'members': row[3] if len(row) > 3 else ''
                }
                schedules.append(schedule)
                print(f"Row {i}: {schedule['raid']} | {schedule['date']} {schedule['time']}")
        
        print("-" * 50)
        print(f"\n✅ {len(schedules)}개 일정 파싱 완료!\n")
        
        return schedules
        
    except Exception as e:
        print(f"❌ 에러 발생: {e}\n")
        return None


def test_find_user_schedule(data, username):
    """특정 유저 일정 찾기 테스트"""
    print("=" * 50)
    print(f"👤 '{username}' 유저 일정 찾기")
    print("=" * 50)
    
    try:
        user_schedules = []
        
        # 헤더에서 유저 열 찾기
        headers = data[0]
        user_col = -1
        
        for i, header in enumerate(headers):
            if username in header:
                user_col = i
                break
        
        if user_col == -1:
            print(f"❌ '{username}' 유저를 찾을 수 없습니다.\n")
            return None
        
        print(f"✅ '{username}' 찾음! (열: {user_col})\n")
        
        # 유저 일정 수집
        print("📅 유저 일정:")
        print("-" * 50)
        
        for i, row in enumerate(data[1:11], start=2):
            if len(row) > user_col:
                character = row[user_col]
                if character and character != "미참여":
                    raid = row[0] if len(row) > 0 else ''
                    date = row[1] if len(row) > 1 else ''
                    time = row[2] if len(row) > 2 else ''
                    
                    user_schedules.append({
                        'raid': raid,
                        'date': date,
                        'time': time,
                        'character': character
                    })
                    
                    print(f"{date} {time} - {raid} ({character})")
        
        print("-" * 50)
        print(f"\n✅ {len(user_schedules)}개 일정 발견!\n")
        
        return user_schedules
        
    except Exception as e:
        print(f"❌ 에러 발생: {e}\n")
        return None


if __name__ == "__main__":
    print("\n🧪 Google Sheets 테스트 시작\n")
    
    # 시트 URL 입력 (테스트용)
    # 실제 사용 시 .env에서 가져오거나 직접 입력
    SHEET_URL = input("📝 테스트할 구글 시트 URL을 입력하세요: ").strip()
    
    if not SHEET_URL:
        print("❌ URL이 입력되지 않았습니다.")
        print("\n테스트 종료")
        exit()
    
    print()
    
    # 테스트 실행
    client = test_sheets_connection()
    
    if client:
        data = test_read_sheet(client, SHEET_URL)
        
        if data:
            schedules = test_parse_schedule(data)
            
            # 특정 유저 찾기 테스트
            test_username = input("\n👤 찾을 유저 이름을 입력하세요 (Enter로 건너뛰기): ").strip()
            if test_username:
                print()
                user_schedules = test_find_user_schedule(data, test_username)
    
    # 결과 요약
    print("=" * 50)
    print("📊 테스트 완료")
    print("=" * 50)
    
    if client and data:
        print("🎉 Google Sheets 연동 성공!")
    else:
        print("⚠️ 테스트 실패 - credentials.json 또는 시트 URL 확인 필요")
    
    print()