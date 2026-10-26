"""
로일(LoIl) - 구글 시트 연동 유틸

레이드 일정(요일/시간/예정/클리어)과 파티-캐릭터 배정은 더 이상 시트에 저장하지 않고
guild_settings.json(raid_schedule.py, raid_signup.py)에 저장한다. 이 파일엔 이제
- 레이드 카탈로그(raid_data.json) 조회 헬퍼 — 순수 JSON, 시트와 무관
- 실제 구글 시트 연결 헬퍼 — "내 닉네임 등록" 흐름(notice.py)이 개인 탭 목록을 가져올 때만 씀
만 남아있다.
"""

import json
import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from typing import Optional
from bot.config.settings import GOOGLE_CREDENTIALS_PATH

SCOPE = [
    'https://spreadsheets.google.com/feeds',
    'https://www.googleapis.com/auth/drive'
]
CREDS_FILE = str(GOOGLE_CREDENTIALS_PATH)

# ==================== 레이드 카탈로그 (raid_data.json) ====================

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


def match_raid_catalog(raid_name: str) -> tuple[str, str] | None:
    """레이드명 문자열(예: '세르카 나이트메어')에서
    raid_config.py의 raid_key(f"{레이드명}_{난이도}") 조립에 쓸 (기준 레이드명, 난이도)를 찾는다.
    매칭 실패(카탈로그에 없는 레이드) 시 None — 관심 레이드 명단 조회 등에서 이 raid는 건너뛴다."""
    for base, diffs in RAID_LEVEL_MAP.items():
        if base in raid_name:
            for diff in diffs:
                if diff in raid_name:
                    return base, diff
            for alias, canonical in DIFF_ALIASES.items():
                if alias in raid_name and canonical in diffs:
                    return base, canonical
            return base, next(iter(diffs.keys()))
    return None


# ==================== 구글 시트 연결 (닉네임 등록용) ====================

def _get_client():
    creds = ServiceAccountCredentials.from_json_keyfile_name(CREDS_FILE, SCOPE)
    return gspread.authorize(creds)


def _get_spreadsheet(url: str):
    return _get_client().open_by_url(url)


def get_sheet_info(url: str) -> Optional[dict]:
    """시트 탭 목록 조회 (닉네임 등록 시 개인 탭 선택지 구성용).
    레이드 일정은 이제 JSON에 저장하므로 "주간레이드" 탭 존재 여부와 무관하게 동작한다."""
    try:
        spreadsheet = _get_spreadsheet(url)
        return {
            'title':      spreadsheet.title,
            'worksheets': [ws.title for ws in spreadsheet.worksheets()],
        }
    except Exception as e:
        print(f"[sheets] get_sheet_info 오류: {e}")
        return None
