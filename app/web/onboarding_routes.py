"""راه‌اندازی اولیه (/start): کاربر تازه با اپ خالی تنها نمی‌ماند.

چی داری ← حدوداً چقدر ← ماه به ماه ← پیامک بانک ← کارت شخصیت. هر قدم قابل رد شدن است و
داده‌ها همان ردیف‌های معمولی اپ‌اند.
"""

from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, Response

from app import onboarding_service as onboarding
from app import services
from app.domain.money import to_persian_digits
from app.domain.onboarding import ASSET_CHOICES, monthly_left
from app.domain.phone import mask_phone
from app.models import User
from app.web import strings as s
from app.web.common import Db, LoggedIn, page, read_form, redirect, site_url
from app.web.forms import FormError
from app.web.sms_routes import android_pair_url, ingest_token, phone_platform


def _page(request: Request, step: str, context: dict[str, Any], status: int = 200) -> Response:
    index = onboarding.STEPS.index(step)
    return page(request, "onboarding.html", {
        "active": "start", "step": step, "n": index + 1, "total": len(onboarding.STEPS),
        "values": {}, "errors": {}, **context}, status)


def register_onboarding_routes(app: FastAPI) -> None:
    @app.get("/start", dependencies=[LoggedIn])
    def start() -> Response:
        return redirect("/start/have")

    @app.get("/start/skip", dependencies=[LoggedIn])
    def skip(request: Request, db: Db) -> Response:
        state = onboarding.load_state(db)
        state.done = True
        onboarding.save_state(db, state)
        db.commit()
        return redirect("/")

    @app.get("/start/have", response_class=HTMLResponse, dependencies=[LoggedIn])
    def have(request: Request, db: Db) -> Response:
        return _page(request, "have", {"choices": ASSET_CHOICES,
                                       "chosen": onboarding.load_state(db).kinds})

    @app.post("/start/have", dependencies=[LoggedIn])
    async def have_save(request: Request, db: Db) -> Response:
        form = await request.form()
        state = onboarding.load_state(db)
        state.kinds = [k for k in ASSET_CHOICES if k in {str(v) for v in form.getlist("kinds")}]
        onboarding.save_state(db, state)
        db.commit()
        return redirect("/start/amounts" if state.kinds else "/start/monthly")

    def amounts_page(request: Request, kinds: list[str], values: dict[str, str] | None = None,
                     errors: dict[str, str] | None = None, status: int = 200) -> Response:
        return _page(request, "amounts", {"groups": onboarding.amount_fields(kinds),
                                          "values": values or {}, "errors": errors or {}},
                     status)

    @app.get("/start/amounts", response_class=HTMLResponse, dependencies=[LoggedIn])
    def amounts(request: Request, db: Db) -> Response:
        kinds = onboarding.load_state(db).kinds
        return amounts_page(request, kinds) if kinds else redirect("/start/have")

    @app.post("/start/amounts", response_class=HTMLResponse, dependencies=[LoggedIn])
    async def amounts_save(request: Request, db: Db) -> Response:
        data = await read_form(request)
        kinds = onboarding.load_state(db).kinds
        try:
            count = onboarding.save_amounts(db, kinds, data)
        except FormError as exc:
            return amounts_page(request, kinds, data, exc.errors, status=400)
        db.commit()
        if count:
            request.session["toast"] = s.ONBOARDING["amounts_saved"].format(
                n=to_persian_digits(str(count)))
        return redirect("/start/monthly")

    @app.get("/start/monthly", response_class=HTMLResponse, dependencies=[LoggedIn])
    def monthly(request: Request) -> Response:
        return _page(request, "monthly", {"fields": onboarding.monthly_fields()})

    @app.post("/start/monthly", response_class=HTMLResponse, dependencies=[LoggedIn])
    async def monthly_save(request: Request, db: Db) -> Response:
        data = await read_form(request)
        try:
            no_income = onboarding.save_monthly(db, data)
        except FormError as exc:
            return _page(request, "monthly", {"fields": onboarding.monthly_fields(),
                                              "values": data, "errors": exc.errors}, 400)
        state = onboarding.load_state(db)
        state.no_income = no_income
        onboarding.save_state(db, state)
        db.commit()
        return redirect("/start/sms")

    @app.get("/start/sms", response_class=HTMLResponse, dependencies=[LoggedIn])
    def sms(request: Request, db: Db) -> Response:
        snap = onboarding.snapshot(db, onboarding.load_state(db))
        user = db.get(User, request.state.user_id)
        token = ingest_token(db)
        return _page(request, "sms", {
            "networth": services.build_portfolio(db).networth, "left": monthly_left(snap),
            "platform": phone_platform(request.headers.get("user-agent", "")),
            "android_pair": android_pair_url(
                token, mask_phone(user.phone) if user and user.phone else "", site_url(request)),
        })

    @app.get("/start/card", response_class=HTMLResponse, dependencies=[LoggedIn])
    def card(request: Request, db: Db) -> Response:
        state = onboarding.load_state(db)
        if not state.done:
            state.done = True  # به قدم آخر رسید؛ داشبورد دیگر دعوت به راه‌اندازی نمی‌کند
            onboarding.save_state(db, state)
            db.commit()
        return _page(request, "card", {})

