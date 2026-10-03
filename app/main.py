"""ساخت اپ FastAPI و مسیرهای وب."""

import asyncio
import json
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from dataclasses import asdict
from datetime import UTC, datetime
from decimal import Decimal
from functools import partial
from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy import inspect as sa_inspect
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware

from app import price_refresh, services
from app.adapters.prices import SOURCES, PriceSource
from app.config import Settings, get_settings
from app.db import Base, make_engine, make_session_factory
from app.domain.loan import LoanInput, analyze_loan
from app.domain.money import format_number
from app.models import Asset, LoanAnalysis, PriceQuote, utcnow
from app.scheduler import Activity, Pace, refresh_now, run_adaptive
from app.web import auth, forms
from app.web import strings as s
from app.web.entities import ENTITIES
from app.web.forms import Field, FormError
from app.web.render import jalali, tehran_today, templates

STATIC_DIR = Path(__file__).parent / "static"
Form = dict[str, str]


def run_migrations(database_url: str) -> None:
    from alembic import command
    from alembic.config import Config

    root = Path(__file__).resolve().parent.parent
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "migrations"))
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "head")


def default_price_sources() -> list[PriceSource]:
    return [source() for source in SOURCES.values()]


def create_app(settings: Settings | None = None, *, migrate: bool = True,
               price_sources: list[PriceSource] | None = None,
               schedule: bool = True) -> FastAPI:
    settings = settings or get_settings()
    engine = make_engine(settings.database_url)
    if migrate:
        run_migrations(settings.database_url)
    else:
        Base.metadata.create_all(engine)
    factory = make_session_factory(engine)

    with factory() as session:
        secret = auth.session_secret(session, settings.secret_key)

    sources = default_price_sources() if price_sources is None else price_sources

    activity = Activity(Pace(active_seconds=settings.price_refresh_seconds,
                             idle_seconds=settings.price_idle_minutes * 60))

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        task = None
        if schedule and sources and settings.price_refresh_seconds > 0:
            task = asyncio.create_task(run_adaptive(partial(refresh_now, factory, sources),
                                                    activity))
        yield
        if task:
            task.cancel()

    app = FastAPI(title=s.APP_NAME, docs_url=None, redoc_url=None, openapi_url=None,
                  lifespan=lifespan)
    app.state.session_factory = factory
    app.state.price_sources = sources
    app.state.poll_seconds = settings.price_refresh_seconds if sources else 0

    @app.middleware("http")
    async def _track_activity(request: Request, call_next: Any) -> Response:
        if not request.url.path.startswith("/static"):
            activity.touch()
        response: Response = await call_next(request)
        return response
    app.add_middleware(SessionMiddleware, secret_key=secret, session_cookie="finassist",
                       max_age=60 * 60 * 24 * 30, same_site="lax",
                       https_only=settings.secure_cookies)
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.exception_handler(auth.LoginRequired)
    async def _to_login(request: Request, _exc: auth.LoginRequired) -> Response:
        if request.headers.get("HX-Request"):
            return Response(status_code=401, headers={"HX-Redirect": "/login"})
        return RedirectResponse("/login", status_code=303)

    register_extra_routes(app)
    _register_routes(app)
    return app


def get_db(request: Request) -> Iterator[Session]:
    with request.app.state.session_factory() as session:
        yield session


Db = Annotated[Session, Depends(get_db)]
LoggedIn = Depends(auth.require_login)


async def read_form(request: Request) -> Form:
    form = await request.form()
    return {key: str(value) for key, value in form.items()}


def wants_fragment(request: Request) -> bool:
    """درخواست htmx برای تکه‌ای از صفحه (مثل برگه پایین)، نه ناوبری کامل."""
    return (request.headers.get("HX-Request") == "true"
            and request.headers.get("HX-Boosted") != "true")


def toast(request: Request, message: str) -> None:
    request.session["toast"] = message


def page(request: Request, name: str, context: dict[str, Any], status: int = 200) -> HTMLResponse:
    active = context.get("active")
    return templates.TemplateResponse(request, name, {
        "active": None,
        "tab": s.TAB_OF_PAGE.get(active, active) if active else None,
        "title": s.PAGE_TITLES.get(active or "", s.APP_NAME),
        "toast": request.session.pop("toast", None),
        **context,
    }, status_code=status)


def redirect(url: str) -> RedirectResponse:
    return RedirectResponse(url, status_code=303)


def done(request: Request, url: str, message: str) -> Response:
    """پایان موفق یک فرم: پیام کوتاه و بازگشت نرم به فهرست."""
    toast(request, message)
    if wants_fragment(request):
        location = json.dumps({"path": url, "target": "body"})
        return Response(status_code=200, headers={"HX-Location": location})
    return redirect(url)


def _register_routes(app: FastAPI) -> None:
    # ---------- ورود ----------

    @app.get("/setup", response_class=HTMLResponse)
    def setup_form(request: Request, db: Db) -> Response:
        if auth.has_password(db):
            return redirect("/login")
        return page(request, "setup.html", {})

    @app.post("/setup", response_class=HTMLResponse)
    async def setup(request: Request, db: Db) -> Response:
        if auth.has_password(db):
            return redirect("/login")
        data = await read_form(request)
        password = data.get("password", "")
        if len(password) < auth.MIN_PASSWORD_LENGTH:
            return page(request, "setup.html", {"error": s.T["password_short"]}, 400)
        if password != data.get("password_repeat"):
            return page(request, "setup.html", {"error": s.T["password_mismatch"]}, 400)
        auth.set_password(db, password)
        db.commit()
        request.session["authenticated"] = True
        return redirect("/")

    @app.get("/login", response_class=HTMLResponse)
    def login_form(request: Request, db: Db) -> Response:
        if not auth.has_password(db):
            return redirect("/setup")
        return page(request, "login.html", {})

    @app.post("/login", response_class=HTMLResponse)
    async def login(request: Request, db: Db) -> Response:
        data = await read_form(request)
        if not auth.check_password(db, data.get("password", "")):
            return page(request, "login.html", {"error": s.T["wrong_password"]}, 401)
        request.session.clear()
        request.session["authenticated"] = True
        return redirect("/")

    @app.post("/logout")
    def logout(request: Request) -> Response:
        request.session.clear()
        return redirect("/login")

    # ---------- داشبورد ----------

    @app.get("/", response_class=HTMLResponse, dependencies=[LoggedIn])
    def dashboard(request: Request, db: Db) -> Response:
        portfolio = services.build_portfolio(db)
        today = tehran_today()
        services.record_snapshot(db, portfolio, today)
        db.commit()
        history = services.snapshots(db)
        threshold = services.get_decimal_setting(db, "dti_threshold")
        networth = portfolio.networth
        previous = next((h for h in reversed(history) if h.date < today), None)
        change = None
        if previous is not None:
            delta = networth.networth_toman - previous.networth_toman
            base = abs(previous.networth_toman)
            change = {"delta": delta, "pct": Decimal(delta) / base if base else None,
                      "date": previous.date}
        trend = {"labels": [jalali(h.date) for h in history],
                 "values": [h.networth_toman for h in history]}
        empty = not (portfolio.assets or portfolio.accounts or portfolio.liabilities
                     or portfolio.incomes)
        return page(request, "dashboard.html", {
            "active": "dashboard",
            "p": portfolio,
            "networth": networth,
            "usd": portfolio.unit_price("usd"),
            "gold": portfolio.unit_price("gold18_gram"),
            "threshold": threshold,
            "dti_high": portfolio.dti is not None and portfolio.dti > threshold,
            "change": change,
            "composition": _composition(portfolio),
            "has_trend": len(history) > 1,
            "poll_seconds": request.app.state.poll_seconds,
            "prices_at": max((q.fetched_at for q in portfolio.quotes.values()), default=None),
            "trend_json": json.dumps(trend, ensure_ascii=False),
            "empty": empty,
        })

    @app.get("/more", response_class=HTMLResponse, dependencies=[LoggedIn])
    def more(request: Request) -> Response:
        return page(request, "more.html", {"active": "more"})

    # ---------- CRUD عمومی دارایی، حساب، بدهی، درآمد ----------

    def _entity(slug: str) -> forms.Entity:
        if slug not in ENTITIES:
            raise HTTPException(404)
        return ENTITIES[slug]

    def _form_values(entity: forms.Entity, obj: Any) -> dict[str, str]:
        raw = entity.from_model(obj) if entity.from_model else {
            f.name: getattr(obj, f.name) for f in entity.fields}
        return {f.name: forms.display_value(f, raw.get(f.name)) for f in entity.fields}

    def _form(request: Request, entity: forms.Entity, values: dict[str, str],
              errors: dict[str, str] | None = None, edit_id: int | None = None,
              status: int = 200) -> Response:
        """فرم در برگه پایین (htmx) یا به‌صورت صفحه کامل (بدون جاوااسکریپت)."""
        fragment = wants_fragment(request)
        if fragment and status >= 400:
            status = 422  # htmx این کد را جایگزین می‌کند تا خطاها در همان برگه دیده شوند
        suggestions = _symbol_suggestions(request) if entity.slug == "assets" else {}
        return page(request, "sheet_form.html" if fragment else "form_page.html", {
            "active": entity.slug, "entity": entity, "fields": entity.fields,
            "values": values, "errors": errors or {}, "edit_id": edit_id,
            "suggestions": suggestions,
        }, status)

    def _symbol_suggestions(request: Request) -> dict[str, list[str]]:
        """نمادهای سهام و نام صندوق‌هایی که منبع قیمت برایشان قیمت دارد."""
        with request.app.state.session_factory() as db:
            keys = services.latest_quotes(db)
        found: dict[str, list[str]] = {"stock": [], "fund": []}
        for key in keys:
            prefix, _, name = key.partition(":")
            if prefix in found:
                found[prefix].append(name)
        return {prefix: sorted(names) for prefix, names in found.items()}

    def _save(entity: forms.Entity, data: Form, obj: Any | None) -> Any:
        values = forms.parse_form(entity.fields, data)
        errors = entity.validate(values)
        if errors:
            raise FormError(errors)
        values = entity.to_model(values)
        obj = obj or entity.model()
        if isinstance(obj, Asset) and values.get("manual_value_toman") != obj.manual_value_toman:
            obj.manual_value_updated_at = utcnow() if values.get("manual_value_toman") else None
        if entity.slug == "accounts" and values["balance_toman"] != obj.balance_toman:
            obj.balance_updated_at = utcnow()
            obj.balance_source = "manual"
        for name, value in values.items():
            setattr(obj, name, value)
        return obj

    @app.get("/{slug}", response_class=HTMLResponse, dependencies=[LoggedIn])
    def entity_list(request: Request, slug: str, db: Db) -> Response:
        entity = _entity(slug)
        return page(request, f"{slug}.html", {
            "active": slug, "entity": entity, "p": services.build_portfolio(db)})

    @app.get("/{slug}/new", response_class=HTMLResponse, dependencies=[LoggedIn])
    def entity_new(request: Request, slug: str) -> Response:
        entity = _entity(slug)
        defaults = {"active": "on", "karat": "۱۸"}
        defaults.update({k: v for k, v in request.query_params.items() if k == "kind"})
        return _form(request, entity, defaults)

    @app.post("/{slug}", response_class=HTMLResponse, dependencies=[LoggedIn])
    async def entity_create(request: Request, slug: str, db: Db) -> Response:
        entity = _entity(slug)
        data = await read_form(request)
        try:
            db.add(_save(entity, data, None))
        except FormError as exc:
            return _form(request, entity, data, exc.errors, status=400)
        db.commit()
        return done(request, f"/{slug}", s.TOASTS["created"].format(title=entity.title))

    @app.get("/{slug}/{obj_id}/edit", response_class=HTMLResponse, dependencies=[LoggedIn])
    def entity_edit(request: Request, slug: str, obj_id: int, db: Db) -> Response:
        entity = _entity(slug)
        obj = db.get(entity.model, obj_id) or _not_found()
        return _form(request, entity, _form_values(entity, obj), edit_id=obj_id)

    @app.post("/{slug}/{obj_id}", response_class=HTMLResponse, dependencies=[LoggedIn])
    async def entity_update(request: Request, slug: str, obj_id: int, db: Db) -> Response:
        entity = _entity(slug)
        obj = db.get(entity.model, obj_id) or _not_found()
        data = await read_form(request)
        try:
            _save(entity, data, obj)
        except FormError as exc:
            db.rollback()
            return _form(request, entity, data, exc.errors, edit_id=obj_id, status=400)
        db.commit()
        return done(request, f"/{slug}", s.TOASTS["updated"])

    @app.post("/{slug}/{obj_id}/delete", dependencies=[LoggedIn])
    def entity_delete(request: Request, slug: str, obj_id: int, db: Db) -> Response:
        entity = _entity(slug)
        obj = db.get(entity.model, obj_id) or _not_found()
        db.delete(obj)
        db.commit()
        return done(request, f"/{slug}", s.TOASTS["deleted"].format(title=entity.title))


def _composition(portfolio: services.Portfolio) -> list[dict[str, Any]]:
    """سهم هر گروه دارایی، با شماره رنگ ثابت برای هر گروه."""
    total = sum(v for v in portfolio.composition.values() if v > 0)
    rows = []
    for key, label, kinds, slot in s.COMPOSITION_GROUPS:
        value = sum(portfolio.composition.get(kind, 0) for kind in kinds)
        if value > 0 and total:
            rows.append({"key": key, "label": label, "value": value, "slot": slot,
                         "pct": Decimal(value) / total})
    return sorted(rows, key=lambda row: -row["value"])


def _not_found() -> Any:
    raise HTTPException(404)


def register_extra_routes(app: FastAPI) -> None:
    """قیمت‌ها، تحلیل وام، تنظیمات و خروجی — قبل از مسیرهای عمومی /{slug} ثبت می‌شوند."""

    @app.get("/prices", response_class=HTMLResponse, dependencies=[LoggedIn])
    def prices_page(request: Request, db: Db) -> Response:
        return _prices_page(request, db)

    @app.post("/prices", response_class=HTMLResponse, dependencies=[LoggedIn])
    async def prices_save(request: Request, db: Db) -> Response:
        data = await read_form(request)
        errors: dict[str, str] = {}
        for key in _price_keys(db):
            raw = data.get(f"price:{key}", "").strip()
            if raw:
                try:
                    db.add(PriceQuote(key=key, price_toman=_toman_field(raw), fetched_at=utcnow(),
                                      source="manual"))
                except ValueError:
                    errors[key] = s.T["invalid_number"]
        if errors:
            db.rollback()
            return _prices_page(request, db, errors, 400)
        db.commit()
        return done(request, "/prices", s.TOASTS["prices"])

    @app.post("/prices/refresh", dependencies=[LoggedIn])
    def prices_refresh(request: Request, db: Db) -> Response:
        statuses = price_refresh.refresh_all(db, request.app.state.price_sources)
        fetched = sum(status.count for status in statuses)
        failed = [status.name for status in statuses if not status.ok]
        message = s.TOASTS["refreshed"].format(count=format_number(fetched))
        if failed:
            message = s.TOASTS["refresh_failed"].format(names="، ".join(failed))
        return done(request, "/prices", message)

    @app.get("/loan", response_class=HTMLResponse, dependencies=[LoggedIn])
    def loan_page(request: Request, db: Db) -> Response:
        portfolio = services.build_portfolio(db)
        defaults = {
            "monthly_income": forms.display_value(_MONEY, portfolio.monthly_income_toman),
            "current_installments": forms.display_value(_MONEY,
                                                        portfolio.monthly_installments_toman),
        }
        return _loan_page(request, db, defaults)

    @app.post("/loan", response_class=HTMLResponse, dependencies=[LoggedIn])
    async def loan_analyze(request: Request, db: Db) -> Response:
        data = await read_form(request)
        try:
            values = forms.parse_form(LOAN_FIELDS, data)
            if values["installment"] is None and values["nominal_rate"] is None:
                raise FormError({"installment": "قسط یا نرخ اسمی را وارد کن."})
            loan = _loan_input(db, values)
            result = analyze_loan(loan)
        except FormError as exc:
            return _loan_page(request, db, data, exc.errors, status=400)
        except ValueError as exc:
            return _loan_page(request, db, data, {"amount": str(exc)}, status=400)
        db.add(LoanAnalysis(inputs_json=_to_json(asdict(loan)), result_json=_to_json(
            {k: v for k, v in asdict(result).items() if k != "cash_flows"})))
        db.commit()
        return _loan_page(request, db, data, result=result, loan=loan)

    @app.get("/settings", response_class=HTMLResponse, dependencies=[LoggedIn])
    def settings_page(request: Request, db: Db) -> Response:
        return _settings_page(request, db)

    @app.post("/settings", response_class=HTMLResponse, dependencies=[LoggedIn])
    async def settings_save(request: Request, db: Db) -> Response:
        data = await read_form(request)
        try:
            values = forms.parse_form(SETTINGS_FIELDS, data)
        except FormError as exc:
            return _settings_page(request, db, data, exc.errors, status=400)
        for key, value in values.items():
            if value is not None:
                services.set_setting(db, key, str(value))
        db.commit()
        return done(request, "/settings", s.TOASTS["settings"])

    @app.get("/export.json", dependencies=[LoggedIn])
    def export(db: Db) -> Response:
        payload: dict[str, list[dict[str, Any]]] = {}
        for mapper in Base.registry.mappers:
            model = mapper.class_
            if model.__tablename__ == "settings":
                continue
            payload[model.__tablename__] = [
                {c.key: getattr(row, c.key) for c in sa_inspect(model).column_attrs}
                for row in db.scalars(select(model))
            ]
        stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M")
        return Response(_to_json(payload), media_type="application/json", headers={
            "Content-Disposition": f'attachment; filename="finassist-{stamp}.json"'})


_MONEY = Field("x", "", "money")

LOAN_FIELDS = [
    Field("amount", "مبلغ وام", "money", required=True, group="main"),
    Field("months", "تعداد اقساط (ماه)", "int", required=True, min=1, max=600, group="main"),
    Field("installment", "مبلغ قسط", "money", group="main",
          hint="اگر نمی‌دانی خالی بگذار و نرخ اسمی را بده"),
    Field("nominal_rate", "نرخ اسمی سالانه", "percent", group="main"),
    Field("upfront_fee", "کارمزد و هزینه‌های ابتدایی", "money", group="fees"),
    Field("guarantor_cost", "هزینه ضامن", "money", group="fees"),
    Field("insurance", "بیمه", "money", group="fees"),
    Field("blocked_deposit", "سپرده بلوکه‌شده", "money", group="blocked"),
    Field("blocked_months", "مدت بلوکه (ماه)", "int", min=0, max=600, group="blocked"),
    Field("blocked_rate", "سود سالانه سپرده بلوکه", "percent", group="blocked"),
    Field("averaging_deposit", "مبلغ سپرده معدل‌گیری", "money", group="averaging"),
    Field("averaging_months", "چند ماه قبل از وام", "int", min=0, max=120, group="averaging"),
    Field("averaging_rate", "سود سالانه سپرده معدل‌گیری", "percent", group="averaging"),
    Field("monthly_income", "درآمد ماهانه", "money", group="budget"),
    Field("current_installments", "اقساط فعلی ماهانه", "money", group="budget"),
]

SETTINGS_FIELDS = [
    Field("dti_threshold", s.T["dti_threshold"], "percent", required=True),
    Field("inflation", s.T["inflation"], "percent", required=True),
]


def _loan_input(db: Session, v: dict[str, Any]) -> LoanInput:
    blocked = v["blocked_deposit"] or 0
    averaging = v["averaging_deposit"] or 0
    if blocked and not v["blocked_months"]:
        raise FormError({"blocked_months": s.T["required"]})
    if averaging and not v["averaging_months"]:
        raise FormError({"averaging_months": s.T["required"]})
    return LoanInput(
        amount_toman=v["amount"],
        months=v["months"],
        installment_toman=v["installment"],
        nominal_rate=v["nominal_rate"],
        upfront_fee_toman=v["upfront_fee"] or 0,
        guarantor_cost_toman=v["guarantor_cost"] or 0,
        insurance_toman=v["insurance"] or 0,
        blocked_deposit_toman=blocked,
        blocked_months=v["blocked_months"] or 0,
        blocked_rate=v["blocked_rate"] or Decimal(0),
        averaging_deposit_toman=averaging,
        averaging_months=v["averaging_months"] or 0,
        averaging_rate=v["averaging_rate"] or Decimal(0),
        inflation=services.get_decimal_setting(db, "inflation"),
        monthly_income_toman=v["monthly_income"] or 0,
        current_installments_toman=v["current_installments"] or 0,
        dti_threshold=services.get_decimal_setting(db, "dti_threshold"),
    )


def _loan_page(request: Request, db: Session, values: dict[str, str],
               errors: dict[str, str] | None = None, status: int = 200, **extra: Any) -> Response:
    history = db.scalars(select(LoanAnalysis).order_by(LoanAnalysis.id.desc()).limit(10))
    past = []
    for row in history:
        inputs, result = json.loads(row.inputs_json), json.loads(row.result_json)
        past.append({"at": row.created_at, "amount": int(inputs["amount_toman"]),
                     "months": inputs["months"], "rate": Decimal(result["effective_rate"])})
    return page(request, "loan.html", {
        "active": "loan", "fields": LOAN_FIELDS, "values": values, "errors": errors or {},
        "inflation": services.get_decimal_setting(db, "inflation"),
        "threshold": services.get_decimal_setting(db, "dti_threshold"),
        "history": past, **extra,
    }, status)


def _settings_page(request: Request, db: Session, values: dict[str, str] | None = None,
                   errors: dict[str, str] | None = None, status: int = 200,
                   message: str = "") -> Response:
    if values is None:
        values = {f.name: forms.display_value(f, services.get_decimal_setting(db, f.name))
                  for f in SETTINGS_FIELDS}
    return page(request, "settings.html", {
        "active": "settings", "fields": SETTINGS_FIELDS, "values": values,
        "errors": errors or {}, "message": message}, status)


def _price_keys(db: Session) -> list[str]:
    """سهام و صندوق‌ها فقط وقتی نمایش داده می‌شوند که دارایی‌ای با آن نماد ثبت شده باشد."""
    keys = list(s.MAIN_PRICE_KEYS) + [k for k in s.PRICE_KEYS if k not in s.MAIN_PRICE_KEYS]
    for key in db.scalars(select(Asset.price_key).where(Asset.price_key.is_not(None))):
        if key not in keys:
            keys.append(key)
    for key in services.latest_quotes(db):
        if key not in keys and not key.startswith(("stock:", "fund:")):
            keys.append(key)
    return keys


def _prices_page(request: Request, db: Session, errors: dict[str, str] | None = None,
                 status: int = 200) -> Response:
    quotes = services.latest_quotes(db)
    used = set(db.scalars(select(Asset.price_key).where(Asset.price_key.is_not(None))))
    rows = [{"key": key, "label": _price_label(key), "quote": quotes.get(key),
             "group": _price_group(key, used)}
            for key in _price_keys(db)]
    sources = [price_refresh.load_status(db, source.name) or source.name
               for source in request.app.state.price_sources]
    return page(request, "prices.html", {"active": "prices", "rows": rows, "sources": sources,
                                         "errors": errors or {}}, status)


def _price_group(key: str, used: set[str | None]) -> str:
    """main: همیشه بالای صفحه؛ fx و crypto: در بخش‌های تاشو."""
    if key in s.MAIN_PRICE_KEYS or key in used or key not in s.PRICE_KEYS:
        return "main"
    return "crypto" if key.startswith("crypto:") else "fx"


def _price_label(key: str) -> str:
    if key in s.PRICE_KEYS:
        return s.PRICE_KEYS[key]
    kind, _, symbol = key.partition(":")
    return f"{symbol} · {s.ASSET_KINDS.get(kind, kind)}" if symbol else key


def _toman_field(raw: str) -> int:
    from app.domain.money import round_toman
    from app.domain.normalize import parse_decimal

    value = round_toman(parse_decimal(raw))
    if value <= 0:
        raise ValueError(raw)
    return value


def _to_json(value: Any) -> str:
    def default(obj: Any) -> Any:
        if isinstance(obj, Decimal):
            return str(obj)
        if hasattr(obj, "isoformat"):
            return obj.isoformat()
        raise TypeError(type(obj))

    return json.dumps(value, default=default, ensure_ascii=False, indent=1)
