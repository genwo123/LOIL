"""
로일(LoIl) - 길드 시작하기 (생성 / 가입 코드)

- /guild/new: 로그인(Discord OAuth2 또는 DEV_SKIP_LOGIN) 필요. 봇 초대 전에 웹에서 먼저 길드 그룹을 만든다.
- /guild/join: 로그인(Discord OAuth2) 필요 — 누가 신청했는지 실제 디스코드 계정으로 확인해서
  관리자가 승인/거절 여부를 판단하고, 결과를 DM으로 알려줄 수 있게 한다.
"""

from pathlib import Path

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from bot.utils.guild_link import create_pending_guild, find_guild_by_join_code, submit_join_request
from web.admin import DEV_SKIP_LOGIN, _current_user

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))


@router.get("/guild/new", response_class=HTMLResponse)
async def new_guild_form(request: Request):
    user = _current_user(request)
    if not user:
        return RedirectResponse("/login")
    return templates.TemplateResponse("guild_new.html", {
        "request": request, "user": user, "dev_mode": DEV_SKIP_LOGIN,
    })


@router.post("/guild/new")
async def create_guild(request: Request, guild_name: str = Form(...)):
    user = _current_user(request)
    if not user:
        return RedirectResponse("/login")
    if not str(user["id"]).isdigit():
        return HTMLResponse("개발 모드 계정으로는 길드를 생성할 수 없습니다 (Discord ID 필요).", status_code=400)

    result = create_pending_guild(int(user["id"]), guild_name)
    return RedirectResponse(f"/admin/{result['guild_id']}", status_code=303)


@router.get("/guild/join", response_class=HTMLResponse)
async def join_form(request: Request, error: str | None = None, done: str | None = None):
    user = _current_user(request)
    if not user:
        request.session["login_next"] = "/guild/join"
        return RedirectResponse("/login")
    return templates.TemplateResponse("guild_join.html", {
        "request": request, "user": user, "dev_mode": DEV_SKIP_LOGIN,
        "error": error, "done": bool(done),
    })


@router.post("/guild/join")
async def submit_join(request: Request, code: str = Form(...), display_name: str = Form(...), note: str = Form("")):
    user = _current_user(request)
    if not user:
        return RedirectResponse("/login")

    found = find_guild_by_join_code(code)
    if not found:
        return RedirectResponse("/guild/join?error=1", status_code=303)

    guild_id, _guild = found
    discord_user_id = str(user["id"]) if str(user["id"]).isdigit() else None
    submit_join_request(guild_id, display_name, note, discord_user_id=discord_user_id)
    return RedirectResponse("/guild/join?done=1", status_code=303)
