"""
로일(LoIl) - 개인별 가능시간 + 레이드 관심/캐릭터 제출

경로: /{길드 URL이름}/일정/{닉네임} — 디스코드 로그인 필요, 본인 것만 접근 가능
(로그인한 디스코드 계정이 그 길드에서 그 닉네임으로 등록돼 있어야 함).
겹치는 시간대를 골라 후보를 추천하는 로직은 raid_signup.suggest_time_candidates가 담당.
가능시간은 When2meet 스타일 드래그 그리드로 입력받는다(요일 하나에 여러 블록 가능).
"""

import asyncio
import json
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from bot.cogs.notice import mark_schedule_complete
from bot.cogs.raid_config import get_active_raids, get_time_granularity, get_time_policy
from bot.config.settings import DEV_SKIP_LOGIN
from bot.utils.guild_url import get_guild_id_by_url_name
from bot.utils.lostark_api import get_account_characters
from bot.utils.member_link import (
    get_all_availability, get_last_saved, get_main_character, get_sheet_name,
    get_previous_week_availability, save_availability, set_last_saved, week_label,
)
from bot.utils.raid_signup import get_all_interest, set_member_interests

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))

DAYS = ["수", "목", "금", "토", "일", "월", "화"]

_DEV_USER = {"id": "dev", "username": "개발모드(로그인 스킵)"}


def _parse_ilvl(raw) -> float:
    try:
        return float(str(raw).replace(",", ""))
    except (TypeError, ValueError):
        return 0.0


def _current_user(request: Request) -> dict | None:
    if DEV_SKIP_LOGIN:
        return _DEV_USER
    return request.session.get("user")


def _resolve_identity(request: Request, guild_url_name: str, member_name: str):
    """접근 가능하면 (guild_id, user_id, sheet_name), 아니면 None."""
    guild_id = get_guild_id_by_url_name(guild_url_name)
    if not guild_id or not guild_id.isdigit():
        return None

    user = _current_user(request)
    if not user:
        return None

    if str(user["id"]) == "dev":
        return int(guild_id), 0, member_name

    my_name = get_sheet_name(int(guild_id), int(user["id"]))
    if my_name != member_name:
        return None

    return int(guild_id), int(user["id"]), member_name


@router.get("/{guild_url_name}/일정/{member_name}", response_class=HTMLResponse)
async def my_availability(request: Request, guild_url_name: str, member_name: str, saved: str | None = None):
    identity = _resolve_identity(request, guild_url_name, member_name)
    if identity is None:
        if not _current_user(request):
            request.session["login_next"] = f"/{guild_url_name}/일정/{member_name}"
            return RedirectResponse("/login")
        return HTMLResponse("❌ 본인 페이지만 볼 수 있습니다.", status_code=403)

    guild_id, user_id, sheet_name = identity
    existing_blocks = get_all_availability(guild_id).get(sheet_name, [])
    prev_week_blocks = get_previous_week_availability(guild_id, sheet_name)

    active_raids = get_active_raids(guild_id)
    interest = get_all_interest(guild_id)

    lookup_name = get_main_character(guild_id, user_id) or sheet_name
    char_error = None
    try:
        my_chars_raw = await asyncio.to_thread(get_account_characters, lookup_name, 0, guild_id)
    except Exception:
        my_chars_raw = []
        char_error = None

    if not my_chars_raw:
        char_error = (
            "로스트아크에서 캐릭터 정보를 불러오지 못했습니다. "
            "디스코드 '내 닉네임 등록'에서 대표 캐릭터명을 등록했는지, 실제 캐릭터명과 맞는지 확인해주세요."
        )

    my_chars = sorted(
        (
            {"name": c.get("CharacterName", ""), "ilvl": _parse_ilvl(c.get("ItemAvgLevel", 0))}
            for c in (my_chars_raw or [])
        ),
        key=lambda c: -c["ilvl"],
    )[:6]

    my_checked = set()  # {(raid_key, character)}
    for raid in active_raids:
        entries = interest.get(raid["key"], [])
        raid["interest_count"] = len({e["member"] for e in entries})
        for e in entries:
            if e["member"] == sheet_name and e.get("character"):
                my_checked.add((raid["key"], e["character"]))

    return templates.TemplateResponse("availability.html", {
        "request": request, "guild_url_name": guild_url_name, "member_name": member_name,
        "sheet_name": sheet_name,
        "days": DAYS, "saved": bool(saved), "week_label": week_label(),
        "last_saved": get_last_saved(guild_id, sheet_name),
        "existing_blocks_json": json.dumps(existing_blocks, ensure_ascii=False),
        "prev_week_blocks_json": json.dumps(prev_week_blocks, ensure_ascii=False),
        "has_prev_week": bool(prev_week_blocks),
        "policy": get_time_policy(guild_id),
        "policy_json": json.dumps(get_time_policy(guild_id), ensure_ascii=False),
        "granularity": get_time_granularity(guild_id), "active_raids": active_raids,
        "my_chars": my_chars, "my_checked_count": len(my_checked),
        "my_checked_json": json.dumps(sorted(my_checked), ensure_ascii=False),
        "char_error": char_error, "has_chars": bool(my_chars),
    })


@router.post("/{guild_url_name}/일정/{member_name}/interest")
async def submit_interest(request: Request, guild_url_name: str, member_name: str):
    identity = _resolve_identity(request, guild_url_name, member_name)
    if identity is None:
        return HTMLResponse("❌ 접근할 수 없습니다.", status_code=403)

    guild_id, user_id, sheet_name = identity
    form = await request.form()

    selections = []
    try:
        raw = json.loads(form.get("interest_json", "[]"))
        for item in raw:
            raid_key = item.get("raid_key")
            character = item.get("character")
            if raid_key and character:
                selections.append({
                    "raid_key": raid_key,
                    "character": character,
                    "item_level": _parse_ilvl(item.get("item_level")),
                })
    except (ValueError, TypeError, AttributeError, json.JSONDecodeError):
        selections = []

    set_member_interests(guild_id, sheet_name, selections)
    set_last_saved(guild_id, sheet_name)
    return RedirectResponse(f"/{guild_url_name}/일정/{member_name}?saved=1", status_code=303)


@router.post("/{guild_url_name}/일정/{member_name}")
async def submit_availability(request: Request, guild_url_name: str, member_name: str):
    identity = _resolve_identity(request, guild_url_name, member_name)
    if identity is None:
        return HTMLResponse("❌ 접근할 수 없습니다.", status_code=403)

    guild_id, user_id, sheet_name = identity
    form = await request.form()

    entries = []
    try:
        raw_blocks = json.loads(form.get("blocks", "[]"))
        for b in raw_blocks:
            day = b.get("day")
            start = float(b.get("start"))
            end = float(b.get("end"))
            if day in DAYS and 0 <= start < end <= 24:
                entries.append({"day": day, "start": start, "end": end})
    except (ValueError, TypeError, AttributeError, json.JSONDecodeError):
        entries = []

    save_availability(guild_id, sheet_name, entries)
    set_last_saved(guild_id, sheet_name)
    mark_schedule_complete(guild_id, sheet_name)
    return RedirectResponse(f"/{guild_url_name}/일정/{member_name}?saved=1", status_code=303)
