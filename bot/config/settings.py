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

BASE_DIR  = Path(__file__).resolve().parent.parent  # config/ -> bot/
DATA_DIR  = BASE_DIR / 'data'
CACHE_DIR = BASE_DIR / 'cache'

# ── 게임 데이터 JSON ──
JOBS_JSON             = DATA_DIR / 'jobs.json'
ENGRAVINGS_JSON       = DATA_DIR / 'engravings.json'
SYNERGIES_JSON        = DATA_DIR / 'synergies.json'
RAIDS_JSON            = DATA_DIR / 'raids.json'

# ── 로일 신규 데이터 JSON ──
DPS_TYPES_JSON        = DATA_DIR / 'dps_types.json'
ALIASES_JSON          = DATA_DIR / 'aliases.json'
SUPPORTS_JSON         = DATA_DIR / 'supports.json'
SYNERGY_BENEFITS_JSON = DATA_DIR / 'synergy_benefits.json'
GUILD_ALIASES_JSON    = DATA_DIR / 'guild_aliases.json'  # 봇이 자동 생성

# ── 런타임 데이터 ──
GUILD_SETTINGS_JSON   = DATA_DIR / 'guild_settings.json'

# ==================== API Keys ====================

DISCORD_BOT_TOKEN      = os.getenv('DISCORD_BOT_TOKEN')
GEMINI_API_KEY         = os.getenv('GEMINI_API_KEY')

LOSTARK_API_KEYS_RAW   = os.getenv('LOSTARK_API_KEYS', '')
LOSTARK_API_KEYS       = [k.strip() for k in LOSTARK_API_KEYS_RAW.split(',') if k.strip()]

# ==================== Google Sheets 설정 ====================

GOOGLE_CREDENTIALS_PATH = BASE_DIR / 'credentials.json'
GOOGLE_SHEETS_SCOPE     = [
    'https://spreadsheets.google.com/feeds',
    'https://www.googleapis.com/auth/drive'
]

# ==================== JSON 데이터 로드 ====================

def load_json_data(filepath: Path) -> dict:
    """JSON 파일 로드. 없으면 빈 dict 반환."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"⚠️ 파일 없음: {filepath.name}")
        return {}
    except json.JSONDecodeError as e:
        print(f"⚠️ JSON 파싱 오류 ({filepath.name}): {e}")
        return {}

# ── 기존 게임 데이터 ──
JOBS_DATA       = load_json_data(JOBS_JSON)
ENGRAVINGS_DATA = load_json_data(ENGRAVINGS_JSON)
SYNERGIES_DATA  = load_json_data(SYNERGIES_JSON)
RAIDS_DATA      = load_json_data(RAIDS_JSON)

# ── 신규 로일 데이터 ──
DPS_TYPES_DATA        = load_json_data(DPS_TYPES_JSON)
ALIASES_DATA          = load_json_data(ALIASES_JSON)
SUPPORTS_DATA         = load_json_data(SUPPORTS_JSON)
SYNERGY_BENEFITS_DATA = load_json_data(SYNERGY_BENEFITS_JSON)
# GUILD_ALIASES_DATA: 길드별 런타임 데이터라 resolver.py에서 직접 읽음

# ==================== API 설정 ====================

LOSTARK_API_BASE_URL    = 'https://developer-lostark.game.onstove.com'
LOSTARK_API_RATE_LIMIT  = 100
LOSTARK_API_CACHE_MINUTES = 5

GEMINI_MODEL      = 'gemini-2.0-flash'
GEMINI_MAX_TOKENS = 1000

# ==================== 검증 ====================

def validate_config() -> list[str]:
    errors = []
    if not DISCORD_BOT_TOKEN:
        errors.append("DISCORD_BOT_TOKEN 미설정")
    if not GEMINI_API_KEY:
        errors.append("GEMINI_API_KEY 미설정")
    if not LOSTARK_API_KEYS:
        errors.append("LOSTARK_API_KEYS 미설정")
    if not GOOGLE_CREDENTIALS_PATH.exists():
        errors.append(f"credentials.json 없음: {GOOGLE_CREDENTIALS_PATH}")

    # 필수 JSON 확인
    required = {
        'jobs.json':             JOBS_DATA,
        'dps_types.json':        DPS_TYPES_DATA,
        'aliases.json':          ALIASES_DATA,
        'supports.json':         SUPPORTS_DATA,
        'synergy_benefits.json': SYNERGY_BENEFITS_DATA,
    }
    for name, data in required.items():
        if not data:
            errors.append(f"{name} 로드 실패 또는 비어있음")

    return errors


def print_config():
    print("=" * 50)
    print(f"🤖 {BOT_NAME} v{BOT_VERSION}")
    print("=" * 50)
    print(f"Discord Token : {'✅' if DISCORD_BOT_TOKEN else '❌'}")
    print(f"Gemini API    : {'✅' if GEMINI_API_KEY else '❌'}")
    print(f"로아 API Keys : {len(LOSTARK_API_KEYS)}개")
    print(f"credentials   : {'✅' if GOOGLE_CREDENTIALS_PATH.exists() else '❌'}")
    print()
    print("📂 데이터 파일:")
    files = {
        'jobs.json':             JOBS_DATA,
        'synergies.json':        SYNERGIES_DATA,
        'dps_types.json':        DPS_TYPES_DATA,
        'aliases.json':          ALIASES_DATA,
        'supports.json':         SUPPORTS_DATA,
        'synergy_benefits.json': SYNERGY_BENEFITS_DATA,
    }
    for name, data in files.items():
        print(f"  {name:25} {'✅' if data else '❌'}")

    errors = validate_config()
    if errors:
        print(f"\n⚠️ 오류:")
        for e in errors:
            print(f"  - {e}")
    else:
        print(f"\n✅ 모든 설정 정상!")
    print("=" * 50)


if __name__ == "__main__":
    print_config()