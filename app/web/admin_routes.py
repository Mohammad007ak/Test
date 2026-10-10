"""پنل مدیریت کاربران (/admin): فقط صاحب برنامه (FINASSIST_OWNER_PHONE).

برای بقیه ۴۰۴ است تا وجود پنل هم لو نرود. داده مالی کسی دیده نمی‌شود؛ فقط شمارش.
"""

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from sqlalchemy.orm import Session

from app import admin_service, giveaway_service
from app.domain.normalize import normalize_digits
from app.models import User
from app.web import strings as s
from app.web.common import Db, LoggedIn, done, page, read_form
from app.web.render import tehran_today


def require_owner(request: Request, _db: Db) -> None:
    if not getattr(request.state, "is_owner", False):
        raise HTTPException(404)


Owner = Depends(require_owner)


def _target(system: Session, request: Request, user_id: int) -> User:
    """کاربر هدف؛ صاحب برنامه نمی‌تواند خودش را غیرفعال یا حذف کند."""
    user = system.get(User, user_id)
    if user is None or user.phone is None:
        raise HTTPException(404)
    if user.id == request.state.user_id:
        raise HTTPException(400)
    return user


def _digits(raw: str) -> str:
    return "".join(ch for ch in normalize_digits(raw) if ch.isdigit())


def admin_page(request: Request, q: str = "", p: int = 1, error: str = "",
               status: int = 200) -> Response:
    query = _digits(q)[:11]
    with request.app.state.session_factory() as system:
        stats = admin_service.stats(system, tehran_today())
        rows, found = admin_service.users(system, request.app.state.owner_phone, query, p)
        claims = giveaway_service.claims(system)
    top = max((n for _d, n in stats.signups), default=0)
    pages = (found + admin_service.PAGE_SIZE - 1) // admin_service.PAGE_SIZE
    return page(request, "admin.html", {
        "active": "admin", "stats": stats, "rows": rows, "found": found, "q": query,
        "p": max(p, 1), "pages": pages, "top": top, "peak": top or 1,
        "claims": claims, "error": error}, status)


def register_admin_routes(app: FastAPI) -> None:
    @app.get("/admin", response_class=HTMLResponse, dependencies=[LoggedIn, Owner])
    def admin(request: Request, q: str = "", p: int = 1) -> Response:
        return admin_page(request, q, p)

    @app.post("/admin/users/{user_id}/disable", dependencies=[LoggedIn, Owner])
    def disable(request: Request, user_id: int) -> Response:
        with request.app.state.session_factory() as system:
            admin_service.set_disabled(system, _target(system, request, user_id), True)
        return done(request, "/admin", s.ADMIN["disabled_done"])

    @app.post("/admin/users/{user_id}/enable", dependencies=[LoggedIn, Owner])
    def enable(request: Request, user_id: int) -> Response:
        with request.app.state.session_factory() as system:
            admin_service.set_disabled(system, _target(system, request, user_id), False)
        return done(request, "/admin", s.ADMIN["enabled_done"])

    @app.post("/admin/users/{user_id}/premium", dependencies=[LoggedIn, Owner])
    def premium(request: Request, user_id: int) -> Response:
        with request.app.state.session_factory() as system:
            user = system.get(User, user_id)
            if user is None:
                raise HTTPException(404)
            admin_service.grant_premium(system, user)
        return done(request, "/admin", s.ADMIN["premium_done"])

    @app.post("/admin/users/{user_id}/premium/revoke", dependencies=[LoggedIn, Owner])
    def premium_revoke(request: Request, user_id: int) -> Response:
        with request.app.state.session_factory() as system:
            user = system.get(User, user_id)
            if user is None:
                raise HTTPException(404)
            admin_service.revoke_premium(system, user)
        return done(request, "/admin", s.ADMIN["premium_revoked"])

    @app.post("/admin/users/{user_id}/delete", dependencies=[LoggedIn, Owner])
    async def delete(request: Request, user_id: int) -> Response:
        confirm = _digits((await read_form(request)).get("confirm", ""))
        with request.app.state.session_factory() as system:
            user = _target(system, request, user_id)
            if confirm != user.phone:
                return admin_page(request, error=s.ADMIN["confirm_wrong"], status=400)
            admin_service.delete_user(system, user)
        return done(request, "/admin", s.ADMIN["deleted_done"])
