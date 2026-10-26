"""
로일(LoIl) - 멤버 연결 유틸
Discord 유저 ID ↔ 시트 탭 이름 매핑 관리

저장 구조 (guild_settings.json):
{
  "guild_id": {
    "members": {
      "discord_user_id": "시트탭이름"  (예: "123456789": "거니")
    },
    "absences": {
      "2026-W08": ["거니", "자두"]     (이번주 불참자)
    }
  }
}
"""

from datetime import datetime, timezone, timedelta

from bot.utils.storage import load_settings, save_settings

# ==================== 설정 로드/저장 ====================

def _guild_data(guild_id: int) -> dict:
    return load_settings().get(str(guild_id), {})

def _update(guild_id: int, key: str, value):
    settings = load_settings()
    gid = str(guild_id)
    if gid not in settings:
        settings[gid] = {}
    settings[gid][key] = value
    save_settings(settings)


# ==================== 멤버 연결 ====================

def get_sheet_name(guild_id: int, user_id: int) -> str | None:
    """Discord 유저 ID → 시트 탭 이름 반환 (없으면 None)"""
    members = _guild_data(guild_id).get("members", {})
    return members.get(str(user_id))

def set_sheet_name(guild_id: int, user_id: int, sheet_name: str):
    """Discord 유저 ID ↔ 시트 탭 이름 저장"""
    settings = load_settings()
    gid = str(guild_id)
    if gid not in settings:
        settings[gid] = {}
    if "members" not in settings[gid]:
        settings[gid]["members"] = {}
    settings[gid]["members"][str(user_id)] = sheet_name
    save_settings(settings)

def is_linked(guild_id: int, user_id: int) -> bool:
    """멤버 연결 여부"""
    return get_sheet_name(guild_id, user_id) is not None

def get_all_members(guild_id: int) -> dict[str, str]:
    """등록된 전체 멤버 {discord_user_id: 시트탭이름}"""
    return _guild_data(guild_id).get("members", {})


def set_main_character(guild_id: int, user_id: int, name: str):
    """대표 캐릭터명(실제 로스트아크 캐릭터명) 저장 — 원정대 조회 시 시트 닉네임 대신 이걸 우선 사용."""
    settings = load_settings()
    gid = str(guild_id)
    if gid not in settings:
        settings[gid] = {}
    settings[gid].setdefault("characters", {})[str(user_id)] = name
    save_settings(settings)


def get_main_character(guild_id: int, user_id: int) -> str | None:
    """등록된 대표 캐릭터명 (없으면 None — 호출부에서 시트 닉네임으로 폴백)"""
    return _guild_data(guild_id).get("characters", {}).get(str(user_id))


# ==================== 미청구 명단 (엑셀 일괄 등록 → 각자 본인 이름 클릭해서 연결) ====================

def add_pending_members(guild_id: int, entries: list[dict]):
    """entries: [{"nickname": "거니", "character": "빛쟁이거니", "role": "길드장"|""}, ...].
    이미 청구(연결)된 닉네임이나 이미 대기 중인 닉네임은 건너뛴다."""
    settings = load_settings()
    gid = str(guild_id)
    if gid not in settings:
        settings[gid] = {}
    pending = settings[gid].setdefault("pending_members", [])
    existing_pending = {e["nickname"] for e in pending}
    claimed = set(settings[gid].get("members", {}).values())
    for e in entries:
        nickname = (e.get("nickname") or "").strip()
        if not nickname or nickname in existing_pending or nickname in claimed:
            continue
        pending.append({
            "nickname": nickname,
            "character": (e.get("character") or "").strip(),
            "role": (e.get("role") or "").strip(),
        })
        existing_pending.add(nickname)
    save_settings(settings)


def get_pending_members(guild_id: int) -> list[dict]:
    """아직 아무도 청구하지 않은 명단 [{"nickname":..., "character":..., "role":...}, ...]"""
    return _guild_data(guild_id).get("pending_members", [])


def claim_pending_member(guild_id: int, user_id: int, nickname: str) -> bool:
    """미청구 명단에서 nickname을 찾아 이 Discord 유저에게 연결. 성공하면 True."""
    settings = load_settings()
    gid = str(guild_id)
    pending = settings.get(gid, {}).get("pending_members", [])
    entry = next((e for e in pending if e["nickname"] == nickname), None)
    if entry is None:
        return False
    pending.remove(entry)
    settings[gid].setdefault("members", {})[str(user_id)] = nickname
    if entry.get("character"):
        settings[gid].setdefault("characters", {})[str(user_id)] = entry["character"]
    if entry.get("role"):
        settings[gid].setdefault("roles", {})[str(user_id)] = entry["role"]
    save_settings(settings)
    return True


def get_role(guild_id: int, user_id: int) -> str:
    """길드 내 역할("길드장"/"부길드장", 없으면 빈 문자열 = 일반 길드원)."""
    return _guild_data(guild_id).get("roles", {}).get(str(user_id), "")


def remove_pending_member(guild_id: int, nickname: str):
    """관리자가 오타/중복 등으로 미청구 명단 항목 삭제."""
    settings = load_settings()
    gid = str(guild_id)
    pending = settings.get(gid, {}).get("pending_members", [])
    settings.setdefault(gid, {})["pending_members"] = [e for e in pending if e["nickname"] != nickname]
    save_settings(settings)


# ==================== 개인별 가능시간 (1차: 원시 데이터만 저장) ====================
# 겹치는 시간 후보 추천 알고리즘, 길드별 요일 정책 등은 아직 미설계 — 여기선 제출/저장만 담당.

def _week_ref_date(offset_weeks: int = 0):
    """이번(또는 offset_weeks만큼 전/후) 로아 주차의 기준일(수요일)."""
    now = datetime.now(timezone(timedelta(hours=9)))
    days_since_wed = (now.weekday() - 2) % 7
    ref = now - timedelta(days=days_since_wed)
    return ref + timedelta(weeks=offset_weeks)


def week_key_for(offset_weeks: int = 0) -> str:
    """offset_weeks=0이면 이번 주, -1이면 저번 주 키."""
    return _week_ref_date(offset_weeks).strftime("%Y-W%V-WED")


def week_label(offset_weeks: int = 0) -> str:
    """사람이 읽기 좋은 주차 표기. 예: '8월 2주차' (CHANGELOG 표기 방식과 동일)."""
    ref = _week_ref_date(offset_weeks)
    week_of_month = ((ref.day - 1) // 7) + 1
    return f"{ref.month}월 {week_of_month}주차"


def save_availability(guild_id: int, sheet_name: str, entries: list[dict], week: str | None = None):
    """entries: [{"day": "수", "start": 18, "end": 24}, ...] — 한 요일에 여러 블록도 가능(리스트에 같은 day 여러 개)."""
    week = week or week_key_for()
    settings = load_settings()
    gid = str(guild_id)
    if gid not in settings:
        settings[gid] = {}
    avail = settings[gid].setdefault("availability", {})
    avail.setdefault(week, {})[sheet_name] = entries
    save_settings(settings)


def get_all_availability(guild_id: int, week: str | None = None) -> dict[str, list]:
    """이 주차(기본: 이번 주) 전체 {시트탭이름: [가능시간 항목, ...]}"""
    week = week or week_key_for()
    return _guild_data(guild_id).get("availability", {}).get(week, {})


def get_all_availability_slots(guild_id: int, week: str | None = None) -> dict[str, set]:
    """웹 개인 가능시간(요일별 시작~끝 블록)을 AI 자동편성이 쓰던 예전 형식
    {시트탭이름: {(day, hour, minute), ...}} (30분 단위)으로 변환.
    구글시트 개인탭 방식은 더 이상 안 쓰고, 이제 이게 유일한 가능시간 소스."""
    result = {}
    for sheet_name, entries in get_all_availability(guild_id, week).items():
        slots = set()
        for e in entries:
            day = e.get("day")
            if not day:
                continue
            start = float(e.get("start", 0))
            end = float(e.get("end", 0))
            slot = start
            while slot < end:
                hour = int(slot)
                minute = 30 if slot - hour >= 0.5 else 0
                slots.add((day, hour, minute))
                slot += 0.5
        result[sheet_name] = slots
    return result


def get_previous_week_availability(guild_id: int, sheet_name: str) -> list[dict]:
    """직전 로아 주차에 이 사람이 제출했던 가능시간 ("저번주 불러오기"용). 없으면 빈 리스트."""
    prev_week = week_key_for(offset_weeks=-1)
    return _guild_data(guild_id).get("availability", {}).get(prev_week, {}).get(sheet_name, [])


def set_last_saved(guild_id: int, sheet_name: str):
    """개인 페이지에서 뭔가(가능시간/관심 레이드) 저장할 때마다 호출 — "이게 방금 저장된 게 맞는지"
    화면에서 바로 확인할 수 있게 사람이 읽을 수 있는 시각을 남긴다."""
    settings = load_settings()
    gid = str(guild_id)
    if gid not in settings:
        settings[gid] = {}
    now = datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d %H:%M")
    settings[gid].setdefault("last_saved", {})[sheet_name] = now
    save_settings(settings)


def get_last_saved(guild_id: int, sheet_name: str) -> str | None:
    return _guild_data(guild_id).get("last_saved", {}).get(sheet_name)


# ==================== 불참 관리 ====================

def _week_key() -> str:
    """
    로아 주차 키 - 수요일 초기화 기준
    수요일 09:00 KST 이후 → 이번 주
    수요일 09:00 KST 이전 → 저번 주
    예: 2026-W08-WED
    """
    now = datetime.now(timezone(timedelta(hours=9)))
    # 수요일=2, 09:00 이전이면 전날 기준으로 계산
    if now.weekday() < 2 or (now.weekday() == 2 and now.hour < 9):
        # 아직 이번 로아 주차 시작 전 → 지난 수요일 기준
        days_since_wed = (now.weekday() - 2) % 7
        ref = now - timedelta(days=days_since_wed)
    else:
        # 이번 수요일 09:00 이후
        days_since_wed = (now.weekday() - 2) % 7
        ref = now - timedelta(days=days_since_wed)
    return ref.strftime("%Y-W%V-WED")

def set_absence(guild_id: int, sheet_name: str):
    """이번주 불참 등록"""
    settings = load_settings()
    gid = str(guild_id)
    week = _week_key()
    if gid not in settings:
        settings[gid] = {}
    if "absences" not in settings[gid]:
        settings[gid]["absences"] = {}
    if week not in settings[gid]["absences"]:
        settings[gid]["absences"][week] = []
    if sheet_name not in settings[gid]["absences"][week]:
        settings[gid]["absences"][week].append(sheet_name)
    save_settings(settings)

def remove_absence(guild_id: int, sheet_name: str):
    """불참 취소"""
    settings = load_settings()
    gid = str(guild_id)
    week = _week_key()
    try:
        absences = settings[gid]["absences"][week]
        if sheet_name in absences:
            absences.remove(sheet_name)
        save_settings(settings)
    except (KeyError, TypeError):
        pass

def get_absences(guild_id: int) -> list[str]:
    """이번주 불참자 목록"""
    week = _week_key()
    return _guild_data(guild_id).get("absences", {}).get(week, [])

def is_absent(guild_id: int, sheet_name: str) -> bool:
    """이번주 불참 여부"""
    return sheet_name in get_absences(guild_id)