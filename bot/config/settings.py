"""
LoIl Bot 설정 파일
모든 API 키와 설정을 중앙에서 관리
"""

import os
import json
from dotenv import load_dotenv
from pathlib import Path

# 환경변수 로드
load_dotenv()

# ==================== Bot 기본 설정 ====================
BOT_VERSION = "1.0.0"
BOT_NAME = "로일(LoIl)"
COMMAND_PREFIX = "/"

# ==================== 데이터 파일 경로 ====================

# 프로젝트 루트 경로 (LOIL/bot/)
BASE_DIR = Path(__file__).resolve().parent.parent  # config/ -> bot/

# 데이터 폴더 경로 (bot/data/)
DATA_DIR = BASE_DIR / 'data'

# JSON 파일 경로
JOBS_JSON = DATA_DIR / 'jobs.json'
ENGRAVINGS_JSON = DATA_DIR / 'engravings.json'
SYNERGIES_JSON = DATA_DIR / 'synergies.json'
RAIDS_JSON = DATA_DIR / 'raids.json'

# 캐시 폴더 (bot/cache/)
CACHE_DIR = BASE_DIR / 'cache'

# ==================== API Keys ====================

# Discord Bot Token
DISCORD_BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN')

# Gemini AI API Key
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

# 로스트아크 API Keys (쉼표로 구분된 여러 개)
LOSTARK_API_KEYS_RAW = os.getenv('LOSTARK_API_KEYS', '')
LOSTARK_API_KEYS = [key.strip() for key in LOSTARK_API_KEYS_RAW.split(',') if key.strip()]

# ==================== Google Sheets 설정 ====================

# credentials.json 파일 경로
GOOGLE_CREDENTIALS_PATH = BASE_DIR / 'credentials.json'

# Google Sheets API Scope
GOOGLE_SHEETS_SCOPE = [
    'https://spreadsheets.google.com/feeds',
    'https://www.googleapis.com/auth/drive'
]

# ==================== JSON 데이터 로드 ====================

def load_json_data(filepath):
    """JSON 파일 로드"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"⚠️ 파일을 찾을 수 없습니다: {filepath}")
        return {}
    except json.JSONDecodeError as e:
        print(f"⚠️ JSON 파싱 에러 ({filepath}): {e}")
        return {}

# 게임 데이터 로드
JOBS_DATA = load_json_data(JOBS_JSON)
ENGRAVINGS_DATA = load_json_data(ENGRAVINGS_JSON)
SYNERGIES_DATA = load_json_data(SYNERGIES_JSON)
RAIDS_DATA = load_json_data(RAIDS_JSON)

# ==================== API 설정 ====================

# 로스트아크 API
LOSTARK_API_BASE_URL = 'https://developer-lostark.game.onstove.com'
LOSTARK_API_RATE_LIMIT = 100  # 분당 100회
LOSTARK_API_CACHE_MINUTES = 5  # 5분 캐싱

# Gemini AI
GEMINI_MODEL = 'gemini-1.5-flash'  # 안정 버전
GEMINI_MAX_TOKENS = 1000

# ==================== 검증 함수 ====================

def validate_config():
    """설정 검증"""
    errors = []
    
    # Discord Bot Token 확인
    if not DISCORD_BOT_TOKEN:
        errors.append("DISCORD_BOT_TOKEN이 설정되지 않았습니다.")
    
    # Gemini API Key 확인
    if not GEMINI_API_KEY:
        errors.append("GEMINI_API_KEY가 설정되지 않았습니다.")
    
    # 로스트아크 API Keys 확인
    if not LOSTARK_API_KEYS:
        errors.append("LOSTARK_API_KEYS가 설정되지 않았습니다.")
    
    # credentials.json 확인
    if not GOOGLE_CREDENTIALS_PATH.exists():
        errors.append(f"{GOOGLE_CREDENTIALS_PATH} 파일이 없습니다.")
    
    # JSON 파일들 확인
    json_files = {
        'jobs.json': JOBS_DATA,
        'engravings.json': ENGRAVINGS_DATA,
        'synergies.json': SYNERGIES_DATA,
        'raids.json': RAIDS_DATA
    }
    
    for filename, data in json_files.items():
        if not data:
            errors.append(f"{filename} 로드 실패")
    
    return errors

# ==================== 설정 출력 ====================

def print_config():
    """현재 설정 출력 (디버깅용)"""
    print("=" * 50)
    print(f"🤖 {BOT_NAME} v{BOT_VERSION} 설정")
    print("=" * 50)
    
    print(f"\n📍 Bot Token: {'✅ 설정됨' if DISCORD_BOT_TOKEN else '❌ 없음'}")
    print(f"🤖 Gemini API: {'✅ 설정됨' if GEMINI_API_KEY else '❌ 없음'}")
    print(f"🎮 로스트아크 API: {len(LOSTARK_API_KEYS)}개")
    print(f"📊 Google Credentials: {'✅ 있음' if GOOGLE_CREDENTIALS_PATH.exists() else '❌ 없음'}")
    
    print(f"\n📂 데이터 파일:")
    print(f"  - jobs.json: {'✅' if JOBS_DATA else '❌'}")
    print(f"  - engravings.json: {'✅' if ENGRAVINGS_DATA else '❌'}")
    print(f"  - synergies.json: {'✅' if SYNERGIES_DATA else '❌'}")
    print(f"  - raids.json: {'✅' if RAIDS_DATA else '❌'}")
    
    # 검증
    errors = validate_config()
    if errors:
        print(f"\n⚠️ 설정 오류:")
        for error in errors:
            print(f"  - {error}")
    else:
        print(f"\n✅ 모든 설정 정상!")
    
    print("=" * 50)
    print()

# ==================== 초기화 시 검증 ====================

if __name__ == "__main__":
    # 테스트용
    print_config()