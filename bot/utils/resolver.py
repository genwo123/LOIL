"""
로일(LoIl) - 별명 리졸버
시트 셀값(홀나, 홀뚱이, 배마(폿) 등) → 표준 직업명/역할로 변환
"""

import json
import re
from pathlib import Path
from typing import Optional

BASE_ALIASES_FILE  = Path("bot/data/aliases.json")
GUILD_ALIASES_FILE = Path("bot/data/guild_aliases.json")
SUPPORTS_FILE      = Path("bot/data/supports.json")

# ==================== 데이터 로드 ====================

def _load_json(path: Path) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _build_lookup(guild_id: int) -> dict[str, str]:
    """
    별명 → 표준 직업명 역방향 맵 생성
    우선순위: 길드 커스텀 > 기본 aliases.json
    """
    lookup = {}

    base  = _load_json(BASE_ALIASES_FILE)
    guild_all = _load_json(GUILD_ALIASES_FILE)
    guild = guild_all.get(str(guild_id), {})

    # 기본 직업 별명
    for std_name, data in base.get("jobs", {}).items():
        aliases = data.get("aliases", []) if isinstance(data, dict) else []
        lookup[std_name.lower()] = std_name  # 표준명 자기자신
        for alias in aliases:
            lookup[alias.lower()] = std_name

    # 기본 각인 별명 (각인 → 직업명 매핑은 별도)
    for std_name, data in base.get("engravings", {}).items():
        aliases = data.get("aliases", []) if isinstance(data, dict) else []
        lookup[std_name.lower()] = std_name
        for alias in aliases:
            lookup[alias.lower()] = std_name

    # 길드 커스텀 직업 별명 (덮어쓰기)
    for std_name, aliases in guild.get("jobs", {}).items():
        for alias in aliases:
            lookup[alias.lower()] = std_name

    # 길드 커스텀 각인 별명
    for std_name, aliases in guild.get("engravings", {}).items():
        for alias in aliases:
            lookup[alias.lower()] = std_name

    return lookup


# ==================== 셀값 파싱 ====================

def parse_cell(cell_value: str) -> dict:
    """
    시트 셀값 파싱
    예: "홀나(폿)" → { raw, job, suffix, is_support, is_alt }
        "배마(부)"  → { raw, job, suffix, is_support, is_alt }
        "워로드"    → { raw, job, suffix=None, is_support=False, is_alt=False }
        "미참여"    → { raw, job=None, absent=True }

    Args:
        cell_value: 시트 셀 원본 값

    Returns:
        dict with keys: raw, job, suffix, is_support, is_alt, absent
    """
    raw = cell_value.strip()

    # 불참 처리
    if raw.lower() in ["미참여", "x", "", "none", "-"]:
        return {"raw": raw, "job": None, "suffix": None,
                "is_support": False, "is_alt": False, "absent": True}

    # 괄호 추출: 홀나(폿) → job=홀나, suffix=폿
    match = re.match(r"^(.+?)\((.+?)\)$", raw)
    if match:
        job_part    = match.group(1).strip()
        suffix_part = match.group(2).strip()
    else:
        job_part    = raw
        suffix_part = None

    # 서폿/딜/부캐 판별
    support_suffixes = {"폿", "서폿"}
    dps_suffixes     = {"딜"}
    alt_suffixes     = {"부"}

    is_support = suffix_part in support_suffixes if suffix_part else False
    is_dps_explicit = suffix_part in dps_suffixes if suffix_part else False
    is_alt     = suffix_part in alt_suffixes if suffix_part else False

    return {
        "raw":         raw,
        "job":         job_part,
        "suffix":      suffix_part,
        "is_support":  is_support,
        "is_alt":      is_alt,
        "absent":      False,
    }


# ==================== 직업명 정규화 ====================

def resolve_job(job_raw: str, guild_id: int = 0) -> Optional[str]:
    """
    별명/약자 → 표준 직업명
    예: "홀나" → "홀리나이트"
        "배마"  → "배틀마스터"
        "디트"  → "디스트로이어"

    Args:
        job_raw:  시트에서 읽은 직업명 (별명 포함)
        guild_id: 길드 ID (커스텀 별명 적용)

    Returns:
        표준 직업명 or None
    """
    if not job_raw:
        return None
    lookup = _build_lookup(guild_id)
    return lookup.get(job_raw.lower())


# ==================== 서폿 여부 판별 ====================

_SUPPORT_JOBS = {"홀리나이트", "바드", "도화가", "발키리", "기공사"}

def is_support(cell_value: str, guild_id: int = 0) -> bool:
    """
    시트 셀값으로 서폿 여부 판별
    규칙:
      1. (폿) suffix → 서폿
      2. (딜) suffix → 딜러
      3. suffix 없음 + 하이브리드 직업 → 기본 서폿으로 간주
      4. 순수 딜러 직업 → 딜러

    Args:
        cell_value: 시트 셀 원본값 (예: "홀나(폿)", "바드", "워로드")
        guild_id:   길드 ID

    Returns:
        True = 서폿, False = 딜러
    """
    parsed   = parse_cell(cell_value)
    if parsed["absent"]:
        return False

    # (폿) suffix → 무조건 서폿
    if parsed["is_support"]:
        return True

    # (딜) suffix → 무조건 딜러
    if parsed.get("suffix") in {"딜"}:
        return False

    # suffix 없음 → 직업명으로 판단
    std_job = resolve_job(parsed["job"], guild_id) or parsed["job"]

    # 하이브리드 직업은 기본 서폿
    supports_data = _load_json(SUPPORTS_FILE)
    hybrid_jobs   = set(supports_data.get("hybrid_support", {}).keys())

    return std_job in hybrid_jobs


# ==================== 전체 셀 정규화 ====================

def normalize_character(cell_value: str, guild_id: int = 0) -> dict:
    """
    시트 셀값 완전 정규화
    예: "홀나(폿)" → {
        raw: "홀나(폿)",
        job: "홀나",
        std_job: "홀리나이트",
        suffix: "폿",
        is_support: True,
        is_alt: False,
        absent: False,
        display: "홀리나이트 (서폿)"
    }

    Args:
        cell_value: 시트 셀 원본값
        guild_id:   길드 ID

    Returns:
        정규화된 캐릭터 정보 dict
    """
    parsed  = parse_cell(cell_value)
    if parsed["absent"]:
        return {**parsed, "std_job": None, "display": "미참여"}

    std_job    = resolve_job(parsed["job"], guild_id) or parsed["job"]
    support    = is_support(cell_value, guild_id)

    role_str   = "서폿" if support else "딜러"
    alt_str    = " (부캐)" if parsed["is_alt"] else ""
    display    = f"{std_job} ({role_str}){alt_str}"

    return {
        **parsed,
        "std_job":    std_job,
        "is_support": support,
        "display":    display,
    }


# ==================== 테스트 ====================

if __name__ == "__main__":
    test_cases = [
        "홀나(폿)", "홀나(딜)", "배마", "배마(부)",
        "워로드", "디트", "소서", "미참여", "바드",
        "발키리(폿)", "발키리(딜)", "기공사", "도화가"
    ]
    print("=" * 50)
    print("별명 리졸버 테스트")
    print("=" * 50)
    for val in test_cases:
        result = normalize_character(val, guild_id=0)
        print(f"{val:15} → {result['display']:20} | 서폿: {result['is_support']}")