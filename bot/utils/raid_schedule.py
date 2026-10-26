"""
로일(LoIl) - 레이드 일정(이번 주 편성) 저장소
구글 시트 "주간레이드" 탭의 컬럼 구조를 대체 — guild_settings.json에 레이드 인스턴스
리스트로 저장한다. "col"은 더 이상 실제 시트 컬럼이 아니라 그냥 안정적인 식별자.

이름/난이도를 하나의 문자열로 합쳐서 저장하던 예전 방식과 달리 name/diff를 분리해서
저장 — 수정 화면에서 뭐가 이름이고 뭐가 난이도인지 구분 안 되던 문제를 없앤다.
"""

from bot.utils.storage import load_settings, save_settings
from bot.utils.sheets import get_raid_size, get_raid_default_duration, match_raid_catalog

DAY_ORDER = {'수': 0, '목': 1, '금': 2, '토': 3, '일': 4, '월': 5, '화': 6, '미정': 7}


def _full_name(name: str, diff: str) -> str:
    return f"{name} {diff}".strip()


def _enrich(raid: dict) -> dict:
    full_name = _full_name(raid["name"], raid["diff"])
    size_override = raid.get("size_override")
    return {
        **raid,
        "full_name": full_name,
        "time_str": f"{raid['hour']}:{raid['minute']:02d}",
        "size": size_override or get_raid_size(full_name),
        "size_override": size_override,
        "guest_count": raid.get("guest_count", 0),
        "active": raid.get("active", True),
    }


def get_raids(guild_id) -> list[dict]:
    """전체 레이드 인스턴스(미정/예정 다 포함), 요일·시간순 정렬, size/full_name 등 계산필드 포함."""
    raw = load_settings().get(str(guild_id), {}).get("raids", [])
    raids = [_enrich(r) for r in raw]
    raids.sort(key=lambda r: (DAY_ORDER.get(r["day"], 7), r["hour"], r["minute"]))
    return raids


def get_scheduled_raids(guild_id) -> list[dict]:
    return [r for r in get_raids(guild_id) if r["scheduled"]]


def _raw_raids(guild_id) -> list[dict]:
    return load_settings().get(str(guild_id), {}).get("raids", [])


def _save_raids(guild_id, raids: list[dict]):
    settings = load_settings()
    gid = str(guild_id)
    if gid not in settings:
        settings[gid] = {}
    settings[gid]["raids"] = raids
    save_settings(settings)


def _next_col(raids: list[dict]) -> int:
    return max((r["col"] for r in raids), default=4) + 1


def add_raid(guild_id, name: str, diff: str, day: str = "미정", hour: int = 0,
             minute: int = 0, duration: int = 60, size_override: int | None = None) -> dict:
    raids = _raw_raids(guild_id)
    raid = {
        "col": _next_col(raids),
        "name": name.strip(),
        "diff": diff.strip(),
        "day": day,
        "hour": hour,
        "minute": minute,
        "duration": duration,
        "scheduled": day != "미정",
        "fixed": False,
        "cleared": False,
        "active": True,
    }
    if size_override:
        raid["size_override"] = size_override
    raids.append(raid)
    _save_raids(guild_id, raids)
    return _enrich(raid)


def update_raid(guild_id, col: int, **fields) -> bool:
    raids = _raw_raids(guild_id)
    for r in raids:
        if r["col"] == col:
            r.update(fields)
            _save_raids(guild_id, raids)
            return True
    return False


def delete_raid(guild_id, col: int) -> bool:
    raids = _raw_raids(guild_id)
    new_raids = [r for r in raids if r["col"] != col]
    if len(new_raids) == len(raids):
        return False
    _save_raids(guild_id, new_raids)
    return True


def set_scheduled(guild_id, col: int, scheduled: bool) -> bool:
    return update_raid(guild_id, col, scheduled=scheduled)


def set_cleared(guild_id, col: int, cleared: bool) -> bool:
    return update_raid(guild_id, col, cleared=cleared)


def set_fixed(guild_id, col: int, fixed: bool) -> bool:
    return update_raid(guild_id, col, fixed=fixed)


def set_guest_count(guild_id, col: int, count: int) -> bool:
    """길드원이 아닌 지인 등을 데려와서 정원을 채운 인원 수 — 이름/캐릭터 등록 없이 숫자만 카운트.
    AI 자동편성(가능시간·직업 기반 파티 구성)에는 안 들어가고, "N/정원" 표시에만 반영됨."""
    return update_raid(guild_id, col, guest_count=max(0, count))


def set_active_by_name(guild_id, name: str, active: bool) -> int:
    """레이드명이 같은 모든 공대(난이도 불문)를 한번에 활성화/비활성화. 바뀐 개수 반환."""
    raids = _raw_raids(guild_id)
    count = 0
    for r in raids:
        if r["name"] == name:
            r["active"] = active
            count += 1
    if count:
        _save_raids(guild_id, raids)
    return count


def find_time_conflicts(raids: list[dict], day: str, hour: int, minute: int,
                         duration: int, exclude_col: int | None = None) -> list[dict]:
    """day/hour/minute/duration(분)이 다른 확정된(미정 아닌) 레이드와 겹치는지 확인."""
    if not day or day == '미정':
        return []

    start = hour * 60 + minute
    end = start + duration
    conflicts = []
    for r in raids:
        if exclude_col is not None and r['col'] == exclude_col:
            continue
        if r['day'] != day or r['day'] == '미정':
            continue
        r_start = r['hour'] * 60 + r['minute']
        r_end = r_start + r['duration']
        if start < r_end and r_start < end:
            conflicts.append(r)
    return conflicts


def get_raid_priority_key(raid: dict) -> tuple:
    match = match_raid_catalog(raid.get("full_name") or _full_name(raid["name"], raid["diff"]))
    if not match:
        return (0, 9)
    from bot.utils.sheets import RAID_LEVEL_MAP
    info = RAID_LEVEL_MAP.get(match[0], {}).get(match[1], {})
    return (-info.get("ilvl", 0), info.get("category", 9))


# ==================== 참가 후보 (배정 + 가능시간 필터) ====================

def get_raid_candidates(guild_id, raid: dict, all_availability: dict | None = None) -> list[dict]:
    """이 레이드(공대)에 배정된 사람들 중, fixed가 아니면 그 시간에 가능한 사람만.
    가능시간을 아예 제출 안 한 사람은 그 이유로 자동 배제되면 안 되므로 후보에 그대로 포함."""
    from bot.utils.raid_signup import get_raid_party
    from bot.utils.member_link import get_all_availability_slots, get_all_availability as _raw_availability

    party = get_raid_party(guild_id, raid["col"])
    if raid.get("fixed"):
        return party

    all_avail = all_availability if all_availability is not None else get_all_availability_slots(guild_id)
    submitted = set(_raw_availability(guild_id).keys())
    day, hour, minute = raid["day"], raid["hour"], raid["minute"]

    result = []
    for m in party:
        name = m["name"]
        if name in submitted and (day, hour, minute) not in all_avail.get(name, set()):
            continue
        result.append(m)
    return result


# ==================== AI 시간 배정 ====================

def _party_count(size: int) -> int:
    """파티 하나는 최대 4명 — 로스트아크 파티 구성 규칙. 16인은 예외(서폿 없이 통짜 한 그룹)."""
    if size == 16:
        return 1
    return max(1, -(-size // 4))  # ceil(size/4)


def _make_parties(sups: list, dps: list, size: int = 8) -> list[list]:
    """파티마다 최대 4명, 서폿 1명씩 우선 배치 — 8인이면 2파티, 목표 인원수를 6명으로
    직접 지정했으면 2파티(4+2)로 자동 계산되는 식으로 인원수에 맞춰 몇 명이든 정확히 나눔."""
    num_parties = _party_count(size)
    if num_parties == 1:
        return [dps + sups] if (dps or sups) else []
    party_sups = sups[:num_parties]
    leftover_sups = sups[num_parties:]
    all_dps = leftover_sups + dps
    parties: list[list] = [[s] for s in party_sups]
    while len(parties) < num_parties:
        parties.append([])
    for i, m in enumerate(all_dps):
        parties[i % num_parties].append(m)
    return [p for p in parties if p]


def assign_raid_times(guild_id) -> list[dict]:
    """예정 여부와 무관하게 전체 레이드에 대해, 배정된 사람들의 가능시간을 기준으로
    가장 많이 겹치는 시간대를 찾아 파티까지 구성한다. 구글시트 없이 완전히 JSON 기반."""
    from collections import Counter
    from bot.utils.raid_signup import get_raid_party
    from bot.utils.member_link import get_all_availability_slots

    all_raids = get_raids(guild_id)
    all_avail = get_all_availability_slots(guild_id)

    fixed_raids  = sorted([r for r in all_raids if r.get('fixed')],     key=get_raid_priority_key)
    normal_raids = sorted([r for r in all_raids if not r.get('fixed')], key=get_raid_priority_key)
    sorted_raids = fixed_raids + normal_raids

    assigned_times: dict[str, list] = {}
    _DAY_ORDER = {'수': 0, '목': 1, '금': 2, '토': 3, '일': 4, '월': 5, '화': 6}

    def _best_slot(raid_members):
        member_avail = {}
        for m in raid_members:
            name = m['name']
            avail = all_avail.get(name, set())
            blocked = {(d, h, mi) for d, h, mi, _ in assigned_times.get(name, [])}
            member_avail[name] = avail - blocked

        slot_count: Counter = Counter()
        for possible in member_avail.values():
            for slot in possible:
                slot_count[slot] += 1

        if not slot_count:
            return None, member_avail

        max_count = max(slot_count.values())
        candidates = [s for s, c in slot_count.items() if c == max_count]
        candidates.sort(key=lambda s: (_DAY_ORDER.get(s[0], 7), s[1], s[2]))
        return candidates[0], member_avail

    results = []

    for raid in sorted_raids:
        col = raid['col']
        raid_size = raid['size']
        raid_members = get_raid_party(guild_id, col)

        if len(raid_members) == 0:
            continue

        if len(raid_members) == 1:
            results.append({
                'raid': raid, 'assigned_day': '미정', 'assigned_hour': 0, 'assigned_minute': 0,
                'time_str': '미정', 'members': raid_members, 'parties': [], 'conflicts': [],
            })
            continue

        best_slot, member_avail = _best_slot(raid_members)

        if best_slot:
            bday, bhour, bminute = best_slot
            btime_str = f"{bhour}:{bminute:02d}"
            final_members = [m for m in raid_members if best_slot in member_avail.get(m['name'], set())]
            conflicts = []
            for m in final_members:
                name = m['name']
                for d, h, mi, other_raid in assigned_times.get(name, []):
                    if (d, h, mi) == best_slot:
                        conflicts.append({'name': name, 'other_raid': other_raid})
            for m in final_members:
                assigned_times.setdefault(m['name'], []).append((bday, bhour, bminute, raid.get('full_name', raid['name'])))
        else:
            bday, bhour, bminute, btime_str = '미정', 0, 0, '미정'
            final_members = raid_members
            conflicts = []

        supports = [m for m in final_members if m.get('is_support')]
        dps_list = [m for m in final_members if not m.get('is_support')]
        num_parties = _party_count(raid_size)
        sup_slots = 0 if raid_size == 16 else min(num_parties, len(supports))
        max_dps = raid_size - sup_slots
        parties = _make_parties(supports, dps_list[:max_dps], raid_size)

        results.append({
            'raid': raid, 'assigned_day': bday, 'assigned_hour': bhour, 'assigned_minute': bminute,
            'time_str': btime_str, 'members': final_members, 'parties': parties, 'conflicts': conflicts,
        })

    return results


# ==================== 개인/전체 일정 요약 (이미지 렌더링용) ====================

def get_user_schedule(guild_id, sheet_name: str) -> list[dict]:
    """이 사람이 배정된 예정 레이드 전부 — image_renderer.render_my_schedule에 그대로 넣는 형식."""
    from bot.utils.raid_signup import get_signups, get_signup_character
    from bot.utils.resolver import normalize_character

    schedule = []
    for raid in get_scheduled_raids(guild_id):
        if sheet_name not in get_signups(guild_id, raid['col']):
            continue
        character = get_signup_character(guild_id, raid['col'], sheet_name)
        if not character:
            continue
        parsed = normalize_character(character, guild_id)
        if parsed["absent"]:
            continue
        schedule.append({
            'raid_name':  raid['full_name'],
            'day':        raid['day'],
            'hour':       raid['hour'],
            'minute':     raid['minute'],
            'time_str':   raid['time_str'],
            'character':  character,
            'std_job':    parsed['std_job'],
            'is_support': parsed['is_support'],
            'is_alt':     parsed['is_alt'],
            'duration':   raid['duration'],
            'cleared':    raid['cleared'],
            'scheduled':  raid['scheduled'],
            'size':       raid['size'],
        })

    schedule.sort(key=lambda s: (DAY_ORDER.get(s['day'], 7), s['hour'], s['minute']))
    return schedule


def get_weekly_summary(guild_id) -> list[dict]:
    """예정된 레이드 전부 + 배정된 인원 — image_renderer.render_weekly_raids/timeline에 그대로 넣는 형식."""
    from bot.utils.member_link import get_absences
    from bot.utils.raid_signup import get_raid_party

    absent_names = set(get_absences(guild_id))
    result = []
    for raid in get_scheduled_raids(guild_id):
        party = [m for m in get_raid_party(guild_id, raid['col']) if m['name'] not in absent_names]
        result.append({
            **raid,
            'name':         raid['full_name'],
            'members':      party,
            'member_count': len(party),
        })
    return result


def save_assigned_times(guild_id, assignments: list) -> bool:
    """AI가 정한 시간을 실제 레이드 인스턴스에 반영(예정으로 전환)."""
    for a in assignments:
        if a['assigned_day'] == '미정':
            continue
        update_raid(
            guild_id, a['raid']['col'],
            day=a['assigned_day'], hour=a['assigned_hour'], minute=a['assigned_minute'],
            scheduled=True,
        )
    return True
