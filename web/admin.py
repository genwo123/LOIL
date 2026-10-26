"""
로일(LoIl) - 웹 대시보드 관리자 라우트

로그인(길드장/부길드장)한 사람만 접근 가능. 일정 조회/추가/수정/삭제.
레이드 일정은 guild_settings.json에 저장(raid_schedule.py) — 예전엔 구글 시트가
source of truth였지만 웹 대시보드로 옮기면서 대체됨.
"""

import asyncio
import json
import secrets
from pathlib import Path

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from bot.cogs.raid_config import (
    get_time_granularity, get_time_policy, get_trai_status,
    set_time_granularity, set_time_policy, set_trai_status,
)
from bot.config.settings import DEV_SKIP_LOGIN
from bot.utils import raid_schedule
from bot.utils.gemini_ai import recommend_party
from bot.utils.guild_banner import get_banner_url, remove_banner, set_banner
from bot.utils.lostark_api import get_character_item_level
from bot.utils.raid_icon import get_raid_color, get_raid_icon_url
from bot.utils.roster_import import parse_roster_workbook
from bot.utils.synergy_ui import CLASS_JOB_OPTIONS, CLASS_JOB_OPTIONS_PLAIN, get_optimization_suggestions, get_synergies_for_selection, guess_job_value, split_covered_overlaps, suggest_party_split
from bot.utils.guild_link import (
    approve_join_request, get_join_requests, get_pending_guilds_for_owner,
    is_pending, reject_join_request,
)
from bot.utils.member_link import (
    get_absences, get_all_availability, get_all_members, get_main_character,
    get_pending_members, get_role, remove_pending_member, week_label,
    add_pending_members,
)
from bot.utils.raid_signup import clear_signups, get_all_signups, suggest_time_candidates
from bot.utils.web_results import get_guild_name, get_guild_setting, list_registered_guild_ids
from web import auth

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))

DAYS       = ["수", "목", "금", "토", "일", "월", "화", "미정"]
DIFFS      = ["노말", "하드", "나이트메어"]  # 더퍼스트는 이벤트 종료로 현재 비활성 — raid_data.json엔 그대로 남겨둠(특별 기간 때 다시 여기에 추가)

_DEV_USER = {"id": "dev", "username": "개발모드(로그인 스킵)"}


def _current_user(request: Request) -> dict | None:
    if DEV_SKIP_LOGIN:
        return _DEV_USER
    return request.session.get("user")


def _guild_display_name(gid: str) -> str:
    """gid가 실제 Discord 길드 ID(숫자)면 get_guild_name, 웹에서 만든 임시 길드(web_ 접두사)면
    guild_settings.json에 저장된 guild_name을 직접 씀."""
    if gid.isdigit():
        return get_guild_name(int(gid), fallback=gid)
    return get_guild_setting(gid).get("guild_name", gid)


def _admin_guilds(request: Request) -> list[dict]:
    if DEV_SKIP_LOGIN:
        guilds = [
            {"id": gid, "name": _guild_display_name(gid)}
            for gid in list_registered_guild_ids()
        ]
    else:
        guilds = request.session.get("admin_guilds", [])

    user = _current_user(request)
    if user and str(user["id"]).isdigit():
        known_ids = {g["id"] for g in guilds}
        for g in get_pending_guilds_for_owner(int(user["id"])):
            if g["id"] not in known_ids:
                guilds.append(g)
                known_ids.add(g["id"])
        # 디스코드 서버 관리자 권한이 없어도, 로일 자체에 길드장/부길드장으로 등록된 경우 관리자로 인정
        for gid in list_registered_guild_ids():
            if gid in known_ids or not gid.isdigit():
                continue
            if get_role(int(gid), int(user["id"])) in ("길드장", "부길드장"):
                guilds.append({"id": gid, "name": _guild_display_name(gid)})
                known_ids.add(gid)
    return guilds


def _require_guild_access(request: Request, guild_id: str) -> dict | None:
    """로그인 안 했거나 이 길드 관리자가 아니면 None."""
    if not _current_user(request):
        return None
    return next((g for g in _admin_guilds(request) if g["id"] == guild_id), None)


def _require_view_access(request: Request, guild_id: str) -> tuple[dict | None, bool]:
    """조회 권한 확인 — 관리자거나, 그 길드에 등록된 멤버면 통과.
    (길드 dict, is_admin) 반환. 접근 불가면 (None, False).
    관리자가 URL에 ?as=member를 붙이면 실제 권한은 그대로 두고 화면만 일반 길드원 시점으로 미리보기(다른 탭에서 진짜 관리자 화면과 동시에 비교 가능)."""
    admin_guild = _require_guild_access(request, guild_id)
    if admin_guild:
        return admin_guild, request.query_params.get("as") != "member"

    user = _current_user(request)
    if not user or not guild_id.isdigit() or not str(user["id"]).isdigit():
        return None, False

    from bot.utils.member_link import get_sheet_name
    if get_sheet_name(guild_id, int(user["id"])):
        return {"id": guild_id, "name": _guild_display_name(guild_id)}, False

    return None, False


@router.get("/login")
async def login(request: Request):
    state = secrets.token_urlsafe(16)
    request.session["oauth_state"] = state
    return RedirectResponse(auth.build_authorize_url(state))


@router.get("/callback")
async def callback(request: Request, code: str | None = None, state: str | None = None):
    if not code or state != request.session.get("oauth_state"):
        return RedirectResponse("/login")

    access_token = auth.exchange_code(code)
    user         = auth.fetch_user(access_token)
    admin_guilds = auth.fetch_admin_guilds(access_token)

    registered_ids = set(list_registered_guild_ids())
    admin_guilds   = [g for g in admin_guilds if g["id"] in registered_ids]

    request.session.pop("oauth_state", None)
    request.session["user"]         = {"id": user["id"], "username": user["username"]}
    request.session["admin_guilds"] = admin_guilds

    next_url = request.session.pop("login_next", None)
    return RedirectResponse(next_url or "/admin")


@router.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/")


@router.get("/admin", response_class=HTMLResponse)
async def admin_home(request: Request):
    user = _current_user(request)
    if not user:
        return templates.TemplateResponse("login.html", {"request": request})

    guilds = _admin_guilds(request)
    if len(guilds) == 1:
        return RedirectResponse(f"/admin/{guilds[0]['id']}")

    for g in guilds:
        g["banner_url"] = get_banner_url(g["id"])

    return templates.TemplateResponse("guild_select.html", {
        "request": request, "user": user, "guilds": guilds, "dev_mode": DEV_SKIP_LOGIN,
    })


@router.get("/admin/{guild_id}", response_class=HTMLResponse)
async def guild_home(request: Request, guild_id: str):
    guild, is_admin = _require_view_access(request, guild_id)
    if not guild:
        return RedirectResponse("/login")

    setting = get_guild_setting(guild_id)
    slug = setting.get("web_slug")
    pending = is_pending(guild_id)

    join_code = setting.get("join_code")
    if is_admin and not join_code and not pending and guild_id.isdigit():
        from bot.utils.guild_link import get_or_create_join_code
        join_code = get_or_create_join_code(guild_id)

    return templates.TemplateResponse("guild_home.html", {
        "request": request, "guild": guild, "user": _current_user(request),
        "public_url": f"/g/{slug}" if slug else None, "dev_mode": DEV_SKIP_LOGIN,
        "pending": pending, "is_admin": is_admin,
        "join_code": join_code,
        "connect_code": setting.get("connect_code") if pending else None,
        "join_request_count": len(get_join_requests(guild_id)) if is_admin else 0,
        "banner_url": get_banner_url(guild_id),
    })


@router.post("/admin/{guild_id}/banner")
async def upload_banner_route(request: Request, guild_id: str, file: UploadFile = File(...)):
    guild = _require_guild_access(request, guild_id)
    if not guild:
        return RedirectResponse("/login")
    content = await file.read()
    set_banner(guild_id, file.filename, content)
    return RedirectResponse(f"/admin/{guild_id}", status_code=303)


@router.post("/admin/{guild_id}/banner/remove")
async def remove_banner_route(request: Request, guild_id: str):
    guild = _require_guild_access(request, guild_id)
    if not guild:
        return RedirectResponse("/login")
    remove_banner(guild_id)
    return RedirectResponse(f"/admin/{guild_id}", status_code=303)


@router.get("/admin/{guild_id}/join-requests", response_class=HTMLResponse)
async def join_requests_page(request: Request, guild_id: str):
    guild = _require_guild_access(request, guild_id)
    if not guild:
        return RedirectResponse("/login")

    return templates.TemplateResponse("join_requests.html", {
        "request": request, "guild": guild, "dev_mode": DEV_SKIP_LOGIN,
        "requests": get_join_requests(guild_id),
    })


@router.post("/admin/{guild_id}/join-requests/{request_id}/approve")
async def approve_join_request_route(request: Request, guild_id: str, request_id: str, message: str = Form("")):
    guild = _require_guild_access(request, guild_id)
    if not guild:
        return RedirectResponse("/login")
    req = approve_join_request(guild_id, request_id)
    if req and req.get("discord_user_id"):
        from bot.utils.dm_queue import queue_dm
        text = f"**{guild['name']}** 가입 신청이 승인되었습니다!"
        if message.strip():
            text += f"\n{message.strip()}"
        queue_dm(guild_id, req["discord_user_id"], text)
    return RedirectResponse(f"/admin/{guild_id}/join-requests", status_code=303)


@router.post("/admin/{guild_id}/join-requests/{request_id}/reject")
async def reject_join_request_route(request: Request, guild_id: str, request_id: str, reason: str = Form("")):
    guild = _require_guild_access(request, guild_id)
    if not guild:
        return RedirectResponse("/login")
    req = reject_join_request(guild_id, request_id)
    if req and req.get("discord_user_id"):
        from bot.utils.dm_queue import queue_dm
        text = f"❌ **{guild['name']}** 가입 신청이 거절되었습니다."
        if reason.strip():
            text += f"\n사유: {reason.strip()}"
        queue_dm(guild_id, req["discord_user_id"], text)
    return RedirectResponse(f"/admin/{guild_id}/join-requests", status_code=303)


@router.get("/admin/{guild_id}/members", response_class=HTMLResponse)
async def members_page(request: Request, guild_id: str):
    guild, is_admin = _require_view_access(request, guild_id)
    if not guild:
        return RedirectResponse("/login")

    members = get_all_members(guild_id)
    role_order = {"길드장": 0, "부길드장": 1, "": 2}
    claimed = [
        {
            "nickname": nickname,
            "character": get_main_character(guild_id, int(uid)) if uid.isdigit() else None,
            "role": get_role(guild_id, int(uid)) if uid.isdigit() else "",
        }
        for uid, nickname in members.items()
    ]
    claimed.sort(key=lambda m: (role_order.get(m["role"], 2), m["nickname"]))
    pending = sorted(get_pending_members(guild_id), key=lambda p: (role_order.get(p.get("role", ""), 2), p["nickname"]))

    return templates.TemplateResponse("members.html", {
        "request": request, "guild": guild, "dev_mode": DEV_SKIP_LOGIN, "is_admin": is_admin,
        "claimed": claimed, "pending": pending,
    })


@router.post("/admin/{guild_id}/members/remove-pending")
async def remove_pending_member_route(request: Request, guild_id: str, nickname: str = Form(...)):
    guild = _require_guild_access(request, guild_id)
    if not guild:
        return RedirectResponse("/login")
    remove_pending_member(guild_id, nickname)
    return RedirectResponse(f"/admin/{guild_id}/members", status_code=303)


@router.get("/admin/{guild_id}/import", response_class=HTMLResponse)
async def import_page(request: Request, guild_id: str):
    guild = _require_guild_access(request, guild_id)
    if not guild:
        return RedirectResponse("/login")
    return templates.TemplateResponse("import_upload.html", {
        "request": request, "guild": guild, "dev_mode": DEV_SKIP_LOGIN,
    })


@router.post("/admin/{guild_id}/import/preview", response_class=HTMLResponse)
async def import_preview_route(request: Request, guild_id: str, file: UploadFile = File(...)):
    guild = _require_guild_access(request, guild_id)
    if not guild:
        return RedirectResponse("/login")

    content = await file.read()
    parsed = parse_roster_workbook(content)

    return templates.TemplateResponse("import_preview.html", {
        "request": request, "guild": guild, "dev_mode": DEV_SKIP_LOGIN,
        "raids": parsed["raids"], "members": parsed["members"], "errors": parsed["errors"],
        "payload": json.dumps({"raids": parsed["raids"], "members": parsed["members"]}, ensure_ascii=False),
    })


@router.post("/admin/{guild_id}/import/confirm")
async def import_confirm_route(request: Request, guild_id: str, payload: str = Form(...)):
    guild = _require_guild_access(request, guild_id)
    if not guild:
        return RedirectResponse("/login")

    data = json.loads(payload)
    for r in data.get("raids", []):
        raid_schedule.add_raid(
            guild_id, r["name"], r["diff"],
            r.get("day", "미정"), r.get("hour", 0),
            r.get("minute", 0), r.get("duration", 60),
        )
    add_pending_members(guild_id, data.get("members", []))

    return RedirectResponse(f"/admin/{guild_id}/members", status_code=303)


@router.get("/admin/{guild_id}/schedule", response_class=HTMLResponse)
async def schedule_page(request: Request, guild_id: str):
    guild, is_admin = _require_view_access(request, guild_id)
    if not guild:
        return RedirectResponse("/login")

    raids = raid_schedule.get_raids(guild_id)
    trai_status = get_trai_status(guild_id)

    signups  = get_all_signups(guild_id)
    for r in raids:
        r["signup_names"] = signups.get(str(r["col"]), [])
        r["signup_count"] = len(r["signup_names"]) + r["guest_count"]
        r["candidates"] = suggest_time_candidates(guild_id, r["col"], r["duration"]) if r["day"] == "미정" else []
        r["icon_url"] = get_raid_icon_url(r["name"])
        r["color"] = get_raid_color(r["name"])

    # 참고용 힌트일 뿐 파티 수를 자동으로 정하는 데는 안 씀 — 시트 전체 인원이 아니라
    # "이번 주 개인일정에서 불참 표시 안 한 사람" 기준(member_link.py 불참 관리)이 더 정확한 신호.
    all_members  = get_all_members(guild_id)
    absent_names = set(get_absences(guild_id))
    going_hint   = sum(1 for name in all_members.values() if name not in absent_names)

    def _group(raid_list):
        result, by_name = [], {}
        for r in raid_list:
            g = by_name.get(r["name"])
            if g is None:
                g = {"name": r["name"], "color": r["color"], "icon_url": r["icon_url"], "scheduled": [], "pending": []}
                by_name[r["name"]] = g
                result.append(g)
            (g["pending"] if r["day"] == "미정" else g["scheduled"]).append(r)
        return result

    groups = _group([r for r in raids if r["active"]])
    inactive_groups = _group([r for r in raids if not r["active"]])

    return templates.TemplateResponse("admin_schedule.html", {
        "request": request, "user": _current_user(request),
        "guild": guild, "groups": groups, "inactive_groups": inactive_groups,
        "days": DAYS, "dev_mode": DEV_SKIP_LOGIN,
        "diffs": DIFFS, "trai_status": trai_status,
        "going_hint": going_hint, "is_admin": is_admin,
    })


@router.post("/admin/{guild_id}/schedule/group/{name}/toggle-active")
async def toggle_group_active_route(request: Request, guild_id: str, name: str, active: str = Form(...)):
    guild = _require_guild_access(request, guild_id)
    if not guild:
        return RedirectResponse("/login")
    raid_schedule.set_active_by_name(guild_id, name, active == "true")
    return RedirectResponse(f"/admin/{guild_id}/schedule", status_code=303)


@router.get("/admin/{guild_id}/suggestions", response_class=HTMLResponse)
async def suggestions_page(request: Request, guild_id: str):
    guild, is_admin = _require_view_access(request, guild_id)
    if not guild:
        return RedirectResponse("/login")

    from bot.cogs.suggest import load_suggestions
    all_suggestions = load_suggestions().get("guild", [])
    mine = [s for s in all_suggestions if str(s.get("guild_id")) == guild_id]
    mine.sort(key=lambda s: s.get("created_at", ""), reverse=True)

    return templates.TemplateResponse("suggestions.html", {
        "request": request, "guild": guild, "dev_mode": DEV_SKIP_LOGIN,
        "suggestions": mine, "is_admin": is_admin,
    })


@router.post("/admin/{guild_id}/suggestions/{suggestion_id}/resolve")
async def resolve_suggestion_route(request: Request, guild_id: str, suggestion_id: str, reply: str = Form("")):
    guild = _require_guild_access(request, guild_id)
    if not guild:
        return RedirectResponse("/login")

    from bot.cogs.suggest import load_suggestions, save_suggestions
    data = load_suggestions()
    for s in data.get("guild", []):
        if s.get("id") == suggestion_id and str(s.get("guild_id")) == guild_id:
            s["resolved"] = True
            if s.get("user_id"):
                from bot.utils.dm_queue import queue_dm
                text = (
                    f"**{s.get('user', '길드원')}**님이 **{guild['name']}**에 남기신 건의가 처리되었습니다.\n\n"
                    f"**Q.** {s.get('content', '')}\n"
                    f"**A.** {reply.strip() or '(답변 없음)'}"
                )
                queue_dm(guild_id, s["user_id"], text)
            break
    save_suggestions(data)
    return RedirectResponse(f"/admin/{guild_id}/suggestions", status_code=303)


@router.get("/admin/{guild_id}/time-policy", response_class=HTMLResponse)
async def time_policy_page(request: Request, guild_id: str, saved: str | None = None):
    guild, is_admin = _require_view_access(request, guild_id)
    if not guild:
        return RedirectResponse("/login")

    return templates.TemplateResponse("time_policy.html", {
        "request": request, "guild": guild, "days": DAYS[:-1],
        "policy": get_time_policy(guild_id), "granularity": get_time_granularity(guild_id),
        "dev_mode": DEV_SKIP_LOGIN, "saved": bool(saved), "is_admin": is_admin,
    })


@router.get("/admin/{guild_id}/group-availability", response_class=HTMLResponse)
async def group_availability_page(request: Request, guild_id: str):
    """길드장이 보는 전체 취합 가능시간(When2meet의 'Group's Availability' 방식) — 개인별 그리드를
    겹쳐서 시간대별로 몇 명이 가능한지 히트맵으로 보여준다. 개인 입력 화면(web/availability.py)과
    달리 여긴 편집 불가, 조회 전용."""
    guild, is_admin = _require_view_access(request, guild_id)
    if not guild:
        return RedirectResponse("/login")

    days = DAYS[:-1]  # "미정" 제외
    avail = get_all_availability(guild_id)

    policy         = get_time_policy(guild_id)
    granularity    = get_time_granularity(guild_id)
    slots_per_hour = 2 if granularity == 30 else 1
    total_slots    = 24 * slots_per_hour

    # 요일마다 정책 범위가 다를 수 있어서(예: 평일 18~24, 주말 0~24), 전부 열어놓은 범위의
    # 합집합만 보여주면 어느 요일도 안 쓰는 시간대(예: 새벽)를 그리드에서 아예 잘라낼 수 있다.
    global_start = min((policy[d]["start"] for d in days), default=0)
    global_end   = max((policy[d]["end"] for d in days), default=24)
    start_slot_offset = int(global_start * slots_per_hour)
    end_slot_offset    = int(global_end * slots_per_hour)
    visible_slots = max(0, end_slot_offset - start_slot_offset)

    grid = [[[] for _ in range(visible_slots)] for _ in range(len(days))]
    for sheet_name, entries in avail.items():
        for e in entries:
            if e.get("day") not in days:
                continue
            di = days.index(e["day"])
            start_slot = max(0, round(float(e.get("start", 0)) * slots_per_hour) - start_slot_offset)
            end_slot   = min(visible_slots, round(float(e.get("end", 0)) * slots_per_hour) - start_slot_offset)
            for s in range(start_slot, end_slot):
                grid[di][s].append(sheet_name)

    max_count = max((len(cell) for row in grid for cell in row), default=0)

    policy_ranges = {
        d: [
            max(0, round(policy[d]["start"] * slots_per_hour) - start_slot_offset),
            max(0, round(policy[d]["end"] * slots_per_hour) - start_slot_offset),
        ]
        for d in days
    }

    return templates.TemplateResponse("group_availability.html", {
        "request": request, "guild": guild, "days": days, "dev_mode": DEV_SKIP_LOGIN,
        "grid_json": json.dumps(grid, ensure_ascii=False),
        "max_count": max_count, "submitted_count": len(avail),
        "week_label": week_label(), "slots_per_hour": slots_per_hour, "is_admin": is_admin,
        "start_slot_offset": start_slot_offset,
        "policy_ranges_json": json.dumps(policy_ranges, ensure_ascii=False),
    })


@router.post("/admin/{guild_id}/time-policy")
async def save_time_policy_route(request: Request, guild_id: str):
    guild = _require_guild_access(request, guild_id)
    if not guild:
        return RedirectResponse("/login")

    form = await request.form()
    policy = {}
    for day in DAYS[:-1]:
        try:
            start = int(form.get(f"start_{day}", 0))
            end   = int(form.get(f"end_{day}", 24))
        except (TypeError, ValueError):
            start, end = 0, 24
        policy[day] = {"start": max(0, min(24, start)), "end": max(0, min(24, end))}

    set_time_policy(guild_id, policy)

    try:
        granularity = int(form.get("granularity", 60))
    except (TypeError, ValueError):
        granularity = 60
    set_time_granularity(guild_id, granularity)

    return RedirectResponse(f"/admin/{guild_id}/time-policy?saved=1", status_code=303)


@router.post("/admin/{guild_id}/schedule/add")
async def add_raid_route(
    request: Request, guild_id: str,
    name: str = Form(...), diff: str = Form(...),
    size: str = Form(""), duration_minutes: int = Form(...),
    trai: bool = Form(False), trai_priority: str = Form("high"),
):
    guild = _require_guild_access(request, guild_id)
    if not guild:
        return RedirectResponse("/login")

    name = name.strip()
    full_name = f"{name} {diff}"
    size_override = int(size) if size.strip().isdigit() else None

    # 실제로 이 레이드에 갈 인원이 몇 명인지는 아직 아무도 신청 안 한 시점이라 알 수 없음
    # (전체 길드원 수로 어림잡던 이전 방식은 부정확해서 폐기) — 공대 1개만 만들고,
    # 사람이 더 모이면 아래 "+공대 추가"로 늘리는 방식으로 변경. 인원수를 직접 정하면(예: 8인
    # 레이드를 4명이서만 갈 계획) 그 값을 이 공대의 목표 정원으로 씀 — 안 정하면 카탈로그 기준.
    raid_schedule.add_raid(guild_id, name, diff, "미정", 0, 0, duration_minutes, size_override=size_override)

    set_trai_status(guild_id, full_name, trai, trai_priority)
    return RedirectResponse(f"/admin/{guild_id}/schedule", status_code=303)


@router.post("/admin/{guild_id}/schedule/add-squad")
async def add_squad_route(
    request: Request, guild_id: str,
    name: str = Form(...), diff: str = Form(...), duration_minutes: int = Form(...),
):
    """이미 등록된 레이드에 공대(컬럼)를 하나 더 추가 — 사람이 더 모였을 때 사용."""
    guild = _require_guild_access(request, guild_id)
    if not guild:
        return RedirectResponse("/login")

    raid_schedule.add_raid(guild_id, name, diff, "미정", 0, 0, duration_minutes)
    return RedirectResponse(f"/admin/{guild_id}/schedule", status_code=303)


@router.post("/admin/{guild_id}/schedule/{col}/update")
async def update_raid_route(
    request: Request, guild_id: str, col: int,
    name: str = Form(...), diff: str = Form(...), day: str = Form(...),
    hour: int = Form(...), minute: int = Form(0),
    duration_minutes: int = Form(60), size: str = Form(""), force: str = Form(None),
):
    guild = _require_guild_access(request, guild_id)
    if not guild:
        return RedirectResponse("/login")

    name = name.strip()
    full_name = f"{name} {diff}"

    # 트라이(우선)로 표시된 레이드가 이미 확정된 다른 일정과 시간이 겹치면
    # 조용히 저장하지 않고 관리자에게 물어본다.
    trai_status = get_trai_status(guild_id)
    if not force and full_name in trai_status:
        raids = raid_schedule.get_raids(guild_id)
        conflicts = raid_schedule.find_time_conflicts(raids, day, hour, minute, duration_minutes, exclude_col=col)
        if conflicts:
            return templates.TemplateResponse("confirm_conflict.html", {
                "request": request, "guild": guild, "conflicts": conflicts,
                "col": col, "name": name, "diff": diff, "day": day, "hour": hour, "minute": minute,
                "duration_minutes": duration_minutes, "size": size, "dev_mode": DEV_SKIP_LOGIN,
            })

    size_override = int(size) if size.strip().isdigit() else None
    raid_schedule.update_raid(
        guild_id, col, name=name, diff=diff, day=day, hour=hour,
        minute=minute, duration=duration_minutes, size_override=size_override,
    )
    return RedirectResponse(f"/admin/{guild_id}/schedule", status_code=303)


@router.post("/admin/{guild_id}/schedule/{col}/delete")
async def delete_raid_route(request: Request, guild_id: str, col: int):
    guild = _require_guild_access(request, guild_id)
    if not guild:
        return RedirectResponse("/login")

    raid_schedule.delete_raid(guild_id, col)
    clear_signups(guild_id, col)
    return RedirectResponse(f"/admin/{guild_id}/schedule", status_code=303)


@router.post("/admin/{guild_id}/schedule/{col}/toggle-scheduled")
async def toggle_scheduled_route(request: Request, guild_id: str, col: int, scheduled: str = Form(...)):
    """예정/미예정 전환. scheduled 폼값은 전환 후 상태("true"/"false")."""
    guild = _require_guild_access(request, guild_id)
    if not guild:
        return RedirectResponse("/login")

    raid_schedule.set_scheduled(guild_id, col, scheduled == "true")
    return RedirectResponse(f"/admin/{guild_id}/schedule", status_code=303)


@router.post("/admin/{guild_id}/schedule/{col}/guest")
async def set_guest_count_route(request: Request, guild_id: str, col: int, delta: int = Form(...)):
    """길드원이 아닌 지인 등을 데려와서 정원 채운 인원 +1/-1 — 이름은 안 받고 숫자만."""
    guild = _require_guild_access(request, guild_id)
    if not guild:
        return RedirectResponse("/login")

    raids = raid_schedule.get_raids(guild_id)
    current = next((r["guest_count"] for r in raids if r["col"] == col), 0)
    raid_schedule.set_guest_count(guild_id, col, current + delta)
    return RedirectResponse(f"/admin/{guild_id}/schedule", status_code=303)


@router.post("/admin/{guild_id}/schedule/{col}/clear")
async def clear_raid_route(request: Request, guild_id: str, col: int):
    guild = _require_guild_access(request, guild_id)
    if not guild:
        return RedirectResponse("/login")

    raid_schedule.set_cleared(guild_id, col, True)
    return RedirectResponse(f"/admin/{guild_id}/schedule", status_code=303)


@router.get("/admin/{guild_id}/synergy", response_class=HTMLResponse)
async def synergy_page(request: Request, guild_id: str):
    """시너지 분석 — 디스코드 /시너지와 같은 계산 로직(synergy_ui.py)을 그대로 재사용."""
    guild, is_admin = _require_view_access(request, guild_id)
    if not guild:
        return RedirectResponse("/login")

    selected = request.query_params.getlist("jobs")
    load_col = request.query_params.get("load_col", "")

    all_raids = raid_schedule.get_raids(guild_id)
    signups = get_all_signups(guild_id)
    loadable_raids = [r for r in all_raids if signups.get(str(r["col"]))]

    loaded_note = None
    if load_col:
        loaded_raid = next((r for r in all_raids if str(r["col"]) == load_col), None)
        if loaded_raid:
            from bot.utils.raid_signup import get_raid_party
            party = get_raid_party(guild_id, int(load_col))
            if not selected:
                guessed = [guess_job_value(m["std_job"], m["is_support"]) for m in party]
                selected = [v for v in guessed if v]
            loaded_note = (
                f"{loaded_raid['full_name']}의 실제 편성 {len(party)}명을 불러왔습니다 — "
                "직업/역할까지는 자동 매칭했고, 정확한 각인은 다를 수 있어요(체크박스에서 직접 조정 가능). "
                "부족한 자리는 체크박스를 더 눌러서 게스트(길드원 아닌 인원)로 채워보세요."
            )

    label_map = {}
    for class_data in CLASS_JOB_OPTIONS.values():
        for label, val in class_data["jobs"]:
            label_map[val] = label

    synergy_map = get_synergies_for_selection(selected) if selected else {}
    selected_labels = [label_map.get(v, v) for v in selected]

    covered, overlaps = split_covered_overlaps(synergy_map) if synergy_map else ([], [])
    covered_list = [{**synergy_map[k], "key": k, "overlap": k in overlaps} for k in covered]
    suggestions = get_optimization_suggestions(synergy_map, selected) if selected else []
    party_split = suggest_party_split(selected) if selected else None

    return templates.TemplateResponse("synergy.html", {
        "request": request, "guild": guild, "dev_mode": DEV_SKIP_LOGIN,
        "class_options": CLASS_JOB_OPTIONS_PLAIN, "selected": set(selected),
        "selected_labels": selected_labels, "covered": covered_list, "suggestions": suggestions,
        "party_split": party_split,
        "has_selection": bool(selected), "has_any_synergy": bool(synergy_map),
        "loadable_raids": loadable_raids, "load_col": load_col, "loaded_note": loaded_note,
    })


@router.get("/admin/{guild_id}/compose", response_class=HTMLResponse)
async def compose_page(request: Request, guild_id: str):
    """AI 자동편성 — 예정된 레이드 중 고를 레이드를 선택하는 화면 (디스코드의 '주간 전체 편성'과 동일)."""
    guild = _require_guild_access(request, guild_id)
    if not guild:
        return RedirectResponse("/login")

    raids = raid_schedule.get_scheduled_raids(guild_id)
    for r in raids:
        r["icon_url"] = get_raid_icon_url(r["name"])
        r["color"] = get_raid_color(r["name"])

    groups, by_name = [], {}
    for r in raids:
        g = by_name.get(r["name"])
        if g is None:
            g = {"name": r["name"], "color": r["color"], "icon_url": r["icon_url"], "raids": []}
            by_name[r["name"]] = g
            groups.append(g)
        g["raids"].append(r)

    return templates.TemplateResponse("compose_select.html", {
        "request": request, "guild": guild, "groups": groups, "dev_mode": DEV_SKIP_LOGIN,
    })


async def _fetch_ai_extras(a: dict, guild_id: int) -> tuple[str | None, float | None, int]:
    """편성 결과 카드에 붙일 부가 정보 — Gemini 시너지 코멘트 + 파티원 평균 전투력.
    파티 구성이 안 된 레이드(1명뿐이거나 서폿 부족 등)는 건너뜀. 실패해도 편성 결과 자체엔 영향 없음."""
    if not a['parties']:
        return None, None, 0
    comment_task = asyncio.to_thread(recommend_party, a['members'], a['raid']['full_name'], guild_id)
    level_tasks = [asyncio.to_thread(get_character_item_level, m['character'], guild_id) for m in a['members']]
    comment, *levels = await asyncio.gather(comment_task, *level_tasks, return_exceptions=True)
    if isinstance(comment, Exception) or (isinstance(comment, str) and comment.startswith("❌")):
        comment = None
    valid_levels = [l for l in levels if isinstance(l, (int, float))]
    avg_level = sum(valid_levels) / len(valid_levels) if valid_levels else None
    return comment, avg_level, len(valid_levels)


@router.post("/admin/{guild_id}/compose/run", response_class=HTMLResponse)
async def compose_run_route(request: Request, guild_id: str):
    """선택된 레이드만 골라서 AI 자동편성 실행 — 결과는 아직 저장 안 하고 미리보기만."""
    guild = _require_guild_access(request, guild_id)
    if not guild:
        return RedirectResponse("/login")

    form = await request.form()
    selected_cols = {int(c) for c in form.getlist("cols")}
    if not selected_cols:
        return RedirectResponse(f"/admin/{guild_id}/compose", status_code=303)

    from bot.utils.member_link import get_absences
    absences = set(get_absences(guild_id))

    assignments = raid_schedule.assign_raid_times(guild_id)
    assignments = [a for a in assignments if a['raid']['col'] in selected_cols]
    for a in assignments:
        a['members'] = [m for m in a['members'] if m['name'] not in absences]

    extras = await asyncio.gather(*[_fetch_ai_extras(a, guild_id) for a in assignments])
    for a, (comment, avg_level, level_count) in zip(assignments, extras):
        a['ai_comment'] = comment
        a['avg_level'] = avg_level
        a['level_count'] = level_count

    return templates.TemplateResponse("compose_results.html", {
        "request": request, "guild": guild, "assignments": assignments, "dev_mode": DEV_SKIP_LOGIN,
    })


@router.post("/admin/{guild_id}/compose/save")
async def compose_save_route(request: Request, guild_id: str):
    """미리보기에서 체크된 레이드들의 시간을 실제로 저장(예정으로 전환)."""
    guild = _require_guild_access(request, guild_id)
    if not guild:
        return RedirectResponse("/login")

    form = await request.form()
    included_cols = form.getlist("include")

    assignments = []
    for col in included_cols:
        day = form.get(f"day_{col}")
        if not day or day == "미정":
            continue
        assignments.append({
            "raid": {"col": int(col)},
            "assigned_day": day,
            "assigned_hour": int(form.get(f"hour_{col}", 0)),
            "assigned_minute": int(form.get(f"minute_{col}", 0)),
        })

    if assignments:
        raid_schedule.save_assigned_times(guild_id, assignments)

    return RedirectResponse(f"/admin/{guild_id}/schedule?composed={len(assignments)}", status_code=303)
