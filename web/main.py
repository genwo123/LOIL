"""
로일(LoIl) - 웹 대시보드

Discord 봇(bot/)과는 별도 프로세스로 로컬에서 실행한다.

- /g/{slug}: 편성 결과 조회 전용 (로그인 불필요, 누구나 링크만 있으면 봄)
- /login, /admin/...: 길드장/부길드장 전용 일정 관리 (Discord OAuth2 로그인 필요)

로컬 실행: uvicorn web.main:app --reload
"""

import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

from bot.utils.app_logging import setup_logging
setup_logging("web")

import json
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.sessions import SessionMiddleware

from fastapi.responses import RedirectResponse

from bot.config.settings import SESSION_SECRET_KEY, WEB_BASE_URL
from bot.utils.guild_banner import get_banner_url
from bot.utils.guild_url import get_guild_id_by_url_name
from web.admin import router as admin_router, _current_user, _guild_display_name
from web.availability import router as availability_router
from web.onboarding import router as onboarding_router

BASE_DIR    = Path(__file__).resolve().parent
RESULTS_DIR = BASE_DIR.parent / "bot" / "data" / "web_results"
STATIC_DIR  = BASE_DIR / "static"
STATIC_DIR.mkdir(exist_ok=True)
GUIDE_DIR   = BASE_DIR.parent / "docs"

DAY_ORDER = {'수': 0, '목': 1, '금': 2, '토': 3, '일': 4, '월': 5, '화': 6, '미정': 7}

app = FastAPI(title="로일(LoIl) 웹 대시보드")
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET_KEY)
app.include_router(admin_router)
app.include_router(availability_router)
app.include_router(onboarding_router)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/guide", include_in_schema=False)
@app.get("/guide/", include_in_schema=False)
@app.get("/guide/index.html", include_in_schema=False)
async def guide_home_redirect():
    # docs/index.html은 실제 홈(web/templates/index.html)과 내용이 겹치는 옛 사본이라
    # 계속 손으로 동기화하는 대신 실제 홈으로 보낸다. 가이드 하위 페이지(guide.html 등)는
    # 아래 /guide StaticFiles 마운트로 그대로 서빙됨.
    return RedirectResponse("/")


if GUIDE_DIR.exists():
    app.mount("/guide", StaticFiles(directory=str(GUIDE_DIR), html=True), name="guide")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    # 길드 목록/링크는 여기서 노출하지 않음 — 길드별 링크는 각자 Discord에서만 받음
    return templates.TemplateResponse("index.html", {
        "request": request,
        "user": _current_user(request),
        "base_url": WEB_BASE_URL.rstrip("/"),
    })


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return FileResponse(STATIC_DIR / "loil" / "favicon.ico")


@app.get("/privacy", include_in_schema=False)
async def privacy_redirect():
    return RedirectResponse("/guide/privacy.html")


_ERROR_TEXT = {
    403: ("접근 권한이 없어요", "이 페이지를 볼 수 있는 권한이 없습니다. 길드 관리자에게 문의해 주세요."),
    404: ("페이지를 찾을 수 없어요", "주소가 잘못됐거나 사라진 페이지예요. 아래 버튼으로 돌아가 주세요."),
    405: ("지원하지 않는 요청이에요", "이 주소는 요청하신 방식으로는 쓸 수 없어요."),
}


def _error_page(request: Request, code: int):
    title, message = _ERROR_TEXT.get(code, ("문제가 생겼어요", "잠시 후 다시 시도해 주세요. 계속되면 문의 페이지로 알려주세요."))
    return templates.TemplateResponse(
        "error.html",
        {"request": request, "code": code, "title": title, "message": message},
        status_code=code,
    )


def _wants_html(request: Request) -> bool:
    return "text/html" in request.headers.get("accept", "")


@app.exception_handler(StarletteHTTPException)
async def http_exception_page(request: Request, exc: StarletteHTTPException):
    if _wants_html(request):
        return _error_page(request, exc.status_code)
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code, headers=getattr(exc, "headers", None))


@app.exception_handler(Exception)
async def unhandled_exception_page(request: Request, exc: Exception):
    if _wants_html(request):
        return _error_page(request, 500)
    return JSONResponse({"detail": "Internal Server Error"}, status_code=500)


def _load_snapshot(slug: str) -> dict | None:
    path = RESULTS_DIR / f"{slug}.json"
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


@app.get("/{guild_url_name}/홈", response_class=HTMLResponse)
async def pretty_guild_home(request: Request, guild_url_name: str):
    guild_id = get_guild_id_by_url_name(guild_url_name)
    if not guild_id:
        return templates.TemplateResponse("empty.html", {"request": request}, status_code=404)
    banner_url = get_banner_url(guild_id)
    return templates.TemplateResponse("guild_public_home.html", {
        "request": request,
        "guild_url_name": guild_url_name,
        "guild_name": _guild_display_name(guild_id),
        "banner_url": banner_url,
        "banner_url_abs": f"{WEB_BASE_URL}{banner_url}" if banner_url else None,
    })


@app.get("/{guild_url_name}/홈/관리자")
async def pretty_guild_admin(guild_url_name: str):
    guild_id = get_guild_id_by_url_name(guild_url_name)
    if not guild_id:
        return RedirectResponse("/")
    return RedirectResponse(f"/admin/{guild_id}")


@app.get("/g/{slug}", response_class=HTMLResponse)
async def guild_result(request: Request, slug: str):
    snapshot = _load_snapshot(slug)
    if not snapshot:
        return templates.TemplateResponse(
            "empty.html", {"request": request}, status_code=404
        )

    raids = []
    for name, info in snapshot.get("raids", {}).items():
        members = [m for party in info.get("parties", []) for m in party]
        raids.append({
            "name":      name,
            "day":       info.get("day", "미정"),
            "time_str":  info.get("time_str", ""),
            "parties":   info.get("parties", []),
            "conflicts": info.get("conflicts", []),
            "total":     len(members),
            "sup":       sum(1 for m in members if m.get("is_support")),
        })
    raids.sort(key=lambda r: (DAY_ORDER.get(r["day"], 7), r["time_str"]))

    weekly_schedule = sorted(
        snapshot.get("weekly_schedule", []),
        key=lambda r: (DAY_ORDER.get(r.get("day", "미정"), 7), r.get("time_str", ""))
    )
    members = dict(sorted(snapshot.get("members", {}).items()))

    return templates.TemplateResponse("result.html", {
        "request":         request,
        "guild_name":      snapshot.get("guild_name") or "로일 길드",
        "week_label":      snapshot.get("week_label", ""),
        "updated_at":      snapshot.get("updated_at", ""),
        "raids":           raids,
        "weekly_schedule": weekly_schedule,
        "members":         members,
        "admin_url":       f"/g/{slug}/admin",
    })


@app.get("/g/{slug}/admin")
async def guild_result_admin(request: Request, slug: str):
    """공개 결과 페이지의 '관리자이신가요?' 링크 — 이 길드로 바로 이어지는 Discord OAuth2 로그인.
    로그인 안 되어 있으면 로그인 후 이 길드 관리 화면으로 바로 돌아오고, 되어 있으면 바로 이동.
    관리자 여부 자체는 /admin/{guild_id}에서 기존 로직(_require_view_access)이 이미 검증한다."""
    snapshot = _load_snapshot(slug)
    guild_id = snapshot.get("guild_id") if snapshot else None
    if not guild_id:
        return RedirectResponse("/admin")

    if not request.session.get("user"):
        request.session["login_next"] = f"/admin/{guild_id}"
        return RedirectResponse("/login")
    return RedirectResponse(f"/admin/{guild_id}")
