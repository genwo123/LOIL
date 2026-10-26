"""
로일(LoIl) - 레이드 참가 신청

지금까지는 "공대(시트 컬럼)를 몇 개 만들지"를 관리자가 감으로 정했음.
이 모듈은 "이 레이드에 실제로 갈 사람"을 신청받아, 모집 진행바(N/8)와
파티 수 판단의 근거 데이터를 만든다.

주의: 컬럼(col)이 삭제된 뒤 같은 위치에 다른 레이드가 새로 생기면 신청 데이터가
꼬일 수 있음(알려진 한계) — 레이드를 삭제할 때는 반드시 clear_signups도 같이 호출.
"""

from bot.utils.storage import load_settings as _load, save_settings as _save


def get_signups(guild_id: int, col: int) -> list[str]:
    settings = _load()
    return settings.get(str(guild_id), {}).get("raid_signups", {}).get(str(col), [])


def get_all_signups(guild_id: int) -> dict:
    """{col(str): [시트이름, ...]}"""
    return _load().get(str(guild_id), {}).get("raid_signups", {})


def toggle_signup(guild_id: int, col: int, sheet_name: str, character: str | None = None) -> bool:
    """참가/취소 토글. 반환값: 토글 후 참가 중이면 True.
    character를 같이 주면 이 사람이 이 레이드에 어떤 캐릭터로 가는지도 같이 저장
    (raid_signup_characters) — AI 자동편성/이미지 렌더링이 여기서 직업/서폿 여부를 읽는다."""
    settings = _load()
    gid = str(guild_id)
    if gid not in settings:
        settings[gid] = {}
    signups = settings[gid].setdefault("raid_signups", {})
    col_key = str(col)
    names = signups.setdefault(col_key, [])

    if sheet_name in names:
        names.remove(sheet_name)
        joined = False
        settings[gid].get("raid_signup_characters", {}).get(col_key, {}).pop(sheet_name, None)
    else:
        names.append(sheet_name)
        joined = True
        if character:
            chars = settings[gid].setdefault("raid_signup_characters", {})
            chars.setdefault(col_key, {})[sheet_name] = character

    _save(settings)
    return joined


def get_signup_character(guild_id: int, col: int, sheet_name: str) -> str | None:
    settings = _load()
    return settings.get(str(guild_id), {}).get("raid_signup_characters", {}).get(str(col), {}).get(sheet_name)


def get_raid_party(guild_id: int, col: int) -> list[dict]:
    """이 레이드(컬럼)에 배정된 사람들을 캐릭터 정보(직업/서폿 여부)까지 포함해서 반환.
    구글시트의 사람행×레이드열 매트릭스를 대체 — 캐릭터가 등록 안 된 사람은 건너뜀
    (배정은 됐지만 어떤 캐릭터로 갈지 아직 안 정한 경우)."""
    from bot.utils.resolver import normalize_character

    names = get_signups(guild_id, col)
    party = []
    for name in names:
        character = get_signup_character(guild_id, col, name)
        if not character:
            continue
        parsed = normalize_character(character, guild_id)
        if parsed["absent"]:
            continue
        party.append({
            "name": name,
            "character": character,
            "std_job": parsed["std_job"],
            "is_support": parsed["is_support"],
            "is_alt": parsed["is_alt"],
        })
    return party


def clear_signups(guild_id: int, col: int):
    """레이드(컬럼) 삭제 시 같이 호출 — 신청 데이터 잔존 방지."""
    settings = _load()
    gid = str(guild_id)
    signups = settings.get(gid, {}).get("raid_signups", {})
    signups.pop(str(col), None)
    settings.get(gid, {}).get("raid_signup_characters", {}).pop(str(col), None)
    _save(settings)


# ==================== 레이드 관심/참가 (카탈로그 단위, 캐릭터 포함) ====================
# "공대(시트 컬럼) 하나에 신청 버튼 하나"보다, 활성화된 레이드 전체를 그리드로 놓고
# 여러 개 체크 + 어느 캐릭터로 갈지까지 정하는 방식이 낫다는 사용자 피드백으로 추가.
# 위 raid_signups(컬럼 단위)와는 별개로, raid_key(레이드명+난이도 카탈로그 키) 단위로 저장한다.
# 한 사람은 캐릭터를 최대 6개까지 가질 수 있어서, 레이드마다 다른 캐릭터를 낼 수도 있다.

def get_interest(guild_id: int, raid_key: str) -> list[dict]:
    """이 레이드(카탈로그 키)에 관심 표시한 사람들. [{"member", "character", "item_level"}, ...]"""
    settings = _load()
    return settings.get(str(guild_id), {}).get("raid_interest", {}).get(raid_key, [])


def get_all_interest(guild_id: int) -> dict:
    """{raid_key: [{"member","character","item_level"}, ...]}"""
    return _load().get(str(guild_id), {}).get("raid_interest", {})


def set_member_interests(guild_id: int, sheet_name: str, selections: list[dict]):
    """이 사람의 관심 레이드 전체를 한 번에 통째로 교체.
    selections: [{"raid_key","character","item_level"}, ...] — 한 레이드에 캐릭터를 여러 개 넣어도 됨
    (메인/부캐 둘 다 갈 의향이 있는 경우, 최종 배정은 관리자가 조율).
    """
    settings = _load()
    gid = str(guild_id)
    if gid not in settings:
        settings[gid] = {}
    interest = settings[gid].setdefault("raid_interest", {})

    for raid_key, entries in list(interest.items()):
        interest[raid_key] = [e for e in entries if e["member"] != sheet_name]

    for sel in selections:
        raid_key = sel["raid_key"]
        interest.setdefault(raid_key, []).append({
            "member": sheet_name,
            "character": sel.get("character"),
            "item_level": sel.get("item_level"),
        })

    settings[gid]["raid_interest"] = interest
    _save(settings)


# ==================== 시간 후보 추천 ====================
# "겹치는 시간이 하나로 안 맞을 때, 후보 2~3개를 관리자에게 제시 → 관리자가 최종 선택"
# 결정된 방식. 이 레이드에 참가 신청한 사람들의 개인 가능시간(member_link.save_availability)을
# 길드 시간 정책(raid_config.get_time_policy) 범위 안에서 30분 단위로 훑어서,
# 가장 많은 인원이 동시에 가능한 시간대 상위 N개를 뽑는다.

def suggest_time_candidates(guild_id: int, col: int, duration_minutes: int, top_n: int = 3) -> list[dict]:
    from bot.cogs.raid_config import TIME_POLICY_DAYS, get_time_policy
    from bot.utils.member_link import get_all_availability

    signed_up = get_signups(guild_id, col)
    total = len(signed_up)
    if not signed_up:
        return []

    availability = get_all_availability(guild_id)
    policy = get_time_policy(guild_id)
    duration_hours = duration_minutes / 60

    candidates = []
    for day in TIME_POLICY_DAYS:
        pol = policy.get(day, {"start": 0, "end": 24})
        slot = float(pol["start"])
        while slot + duration_hours <= pol["end"]:
            available_members = []
            for name in signed_up:
                entry = next((e for e in availability.get(name, []) if e["day"] == day), None)
                if entry and entry["start"] <= slot and slot + duration_hours <= entry["end"]:
                    available_members.append(name)
            if available_members:
                candidates.append({
                    "day": day,
                    "hour": int(slot),
                    "minute": 30 if slot % 1 else 0,
                    "available_count": len(available_members),
                    "available_members": available_members,
                    "total_signups": total,
                })
            slot += 0.5

    day_order = {d: i for i, d in enumerate(TIME_POLICY_DAYS)}
    candidates.sort(key=lambda c: (-c["available_count"], day_order[c["day"]], c["hour"], c["minute"]))
    return candidates[:top_n]
