"""جایزه اینستاگرام (/gift): فالو + شیر برای دوست ← ثبت آیدی ← ۳ ماه وزیر ویژه رایگان.

صفحه برای همه باز است؛ بازدیدکننده با «ثبت‌نام» می‌رود و بعد از ثبت‌نام به همین‌جا برمی‌گردد.
"""

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, Response

from app import giveaway_service as giveaway
from app.domain.giveaway import is_open, parse_handle
from app.web import strings as s
from app.web.common import Db, LoggedIn, done, page, read_form, redirect
from app.web.render import tehran_today


def _gift_page(request: Request, db: Db, value: str = "", error: str = "",
               status: int = 200) -> Response:
    logged_in = request.state.user_id is not None
    claimed = giveaway.handle(db) if logged_in else None
    return page(request, "gift.html", {
        "title": s.GIFT["page_title"], "logged_in": logged_in, "open": is_open(tehran_today()),
        "claimed": claimed, "value": value or (f"@{claimed}" if claimed else ""),
        "error": error}, status)


def register_giveaway_routes(app: FastAPI) -> None:
    @app.get("/gift", response_class=HTMLResponse)
    def gift(request: Request, db: Db) -> Response:
        return _gift_page(request, db)

    @app.get("/gift/join")
    def join(request: Request, login: bool = False) -> Response:
        request.session["after_auth"] = "/gift"
        return redirect("/login" if login else "/signup")

    @app.post("/gift", response_class=HTMLResponse, dependencies=[LoggedIn])
    async def claim(request: Request, db: Db) -> Response:
        raw = (await read_form(request)).get("instagram", "")
        if not is_open(tehran_today()):
            return _gift_page(request, db, status=403)
        handle = parse_handle(raw)
        if handle is None:
            return _gift_page(request, db, raw, s.GIFT["invalid"], 400)
        with request.app.state.session_factory() as system:
            if giveaway.taken_by_other(system, handle, request.state.user_id):
                return _gift_page(request, db, raw, s.GIFT["taken"], 409)
        giveaway.save(db, handle)
        db.commit()
        return done(request, "/gift", s.GIFT["saved"])
