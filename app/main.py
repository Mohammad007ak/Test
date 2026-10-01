"""ساخت اپ FastAPI و مسیرهای وب."""

import json
from collections.abc import Iterator
from dataclasses import asdict
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy import inspect as sa_inspect
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware

from app import services
from app.config import Settings, get_settings
from app.db import Base, make_engine, make_session_factory
from app.domain.loan import LoanInput, analyze_loan
from app.models import Asset, LoanAnalysis, PriceQuote, utcnow
from app.web import auth, forms
from app.web import strings as s
from app.web.entities import ENTITIES
from app.web.forms import Field, FormError
from app.web.render import tehran_today, templates

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


def create_app(settings: Settings | None = None, *, migrate: bool = True) -> FastAPI:
    settings = settings or get_settings()
    engine = make_engine(settings.database_url)
    if migrate:
        run_migrations(settings.database_url)
    else:
        Base.metadata.create_all(engine)
    factory = make_session_factory(engine)

    with factory() as session:
        secret = auth.session_secret(session, settings.secret_key)

    app = FastAPI(title=s.APP_NAME, docs_url=None, redoc_url=None, openapi_url=None)
    app.state.session_factory = factory
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


def page(request: Request, name: str, context: dict[str, Any], status: int = 200) -> HTMLResponse:
    return templates.TemplateResponse(request, name, {"active": None, **context},
                                      status_code=status)


def redirect(url: str) -> RedirectResponse:
    return RedirectResponse(url, status_code=303)


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
        services.record_snapshot(db, portfolio, tehran_today())
        db.commit()
        history = services.snapshots(db)
        threshold = services.get_decimal_setting(db, "dti_threshold")
        networth = portfolio.networth
        composition = sorted(portfolio.composition.items(), key=lambda kv: -kv[1])
        chart = {
            "composition": {
                "labels": [s.COMPOSITION_LABELS[k] for k, _ in composition],
                "values": [v for _, v in composition],
            },
            "trend": {
                "labels": [_jalali_day(h.date) for h in history],
                "values": [h.networth_toman for h in history],
            },
        }
        return page(request, "dashboard.html", {
            "active": "dashboard",
            "p": portfolio,
            "networth": networth,
            "usd": portfolio.unit_price("usd"),
            "gold": portfolio.unit_price("gold18_gram"),
            "threshold": threshold,
            "dti_high": portfolio.dti is not None and portfolio.dti > threshold,
            "has_trend": len(history) > 1,
            "chart_json": json.dumps(chart, ensure_ascii=False),
        })

    # ---------- CRUD عمومی دارایی، حساب، بدهی، درآمد ----------

    def _entity(slug: str) -> forms.Entity:
        if slug not in ENTITIES:
            raise HTTPException(404)
        return ENTITIES[slug]

    def _form_values(entity: forms.Entity, obj: Any) -> dict[str, str]:
        raw = entity.from_model(obj) if entity.from_model else {
            f.name: getattr(obj, f.name) for f in entity.fields}
        return {f.name: forms.display_value(f, raw.get(f.name)) for f in entity.fields}

    def _list_page(request: Request, db: Session, entity: forms.Entity,
                   form_values: dict[str, str] | None = None, errors: dict[str, str] | None = None,
                   edit_id: int | None = None, status: int = 200) -> Response:
        portfolio = services.build_portfolio(db)
        defaults = {"active": "on", "karat": "۱۸"}
        return page(request, f"{entity.slug}.html", {
            "active": entity.slug,
            "entity": entity,
            "p": portfolio,
            "fields": entity.fields,
            "values": form_values if form_values is not None else defaults,
            "errors": errors or {},
            "edit_id": edit_id,
        }, status)

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
        return _list_page(request, db, _entity(slug))

    @app.post("/{slug}", response_class=HTMLResponse, dependencies=[LoggedIn])
    async def entity_create(request: Request, slug: str, db: Db) -> Response:
        entity = _entity(slug)
        data = await read_form(request)
        try:
            db.add(_save(entity, data, None))
        except FormError as exc:
            return _list_page(request, db, entity, data, exc.errors, status=400)
        db.commit()
        return redirect(f"/{slug}")

    @app.get("/{slug}/{obj_id}/edit", response_class=HTMLResponse, dependencies=[LoggedIn])
    def entity_edit(request: Request, slug: str, obj_id: int, db: Db) -> Response:
        entity = _entity(slug)
        obj = db.get(entity.model, obj_id) or _not_found()
        return _list_page(request, db, entity, _form_values(entity, obj), edit_id=obj_id)

    @app.post("/{slug}/{obj_id}", response_class=HTMLResponse, dependencies=[LoggedIn])
    async def entity_update(request: Request, slug: str, obj_id: int, db: Db) -> Response:
        entity = _entity(slug)
        obj = db.get(entity.model, obj_id) or _not_found()
        data = await read_form(request)
        try:
            _save(entity, data, obj)
        except FormError as exc:
            db.rollback()
            return _list_page(request, db, entity, data, exc.errors, edit_id=obj_id, status=400)
        db.commit()
        return redirect(f"/{slug}")

    @app.post("/{slug}/{obj_id}/delete", dependencies=[LoggedIn])
    def entity_delete(request: Request, slug: str, obj_id: int, db: Db) -> Response:
        entity = _entity(slug)
        obj = db.get(entity.model, obj_id) or _not_found()
        db.delete(obj)
        db.commit()
        if request.headers.get("HX-Request"):
            return HTMLResponse("")
        return redirect(f"/{slug}")


def _not_found() -> Any:
    raise HTTPException(404)


def _jalali_day(day: Any) -> str:
    from app.web.render import jalali

    return jalali(day)


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
        return redirect("/prices")

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
        return _settings_page(request, db, message=s.T["saved"])

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
    Field("amount", "مبلغ وام", "money", required=True),
    Field("months", "تعداد اقساط (ماه)", "int", required=True, min=1, max=600),
    Field("installment", "مبلغ قسط", "money", hint="اگر نمی‌دانی خالی بگذار و نرخ اسمی را بده"),
    Field("nominal_rate", "نرخ اسمی سالانه", "percent"),
    Field("upfront_fee", "کارمزد و هزینه‌های ابتدایی", "money"),
    Field("guarantor_cost", "هزینه ضامن", "money"),
    Field("insurance", "بیمه", "money"),
    Field("blocked_deposit", "سپرده بلوکه‌شده", "money"),
    Field("blocked_months", "مدت بلوکه (ماه)", "int", min=0, max=600),
    Field("blocked_rate", "سود سالانه سپرده بلوکه", "percent"),
    Field("averaging_deposit", "مبلغ سپرده معدل‌گیری", "money"),
    Field("averaging_months", "چند ماه قبل از وام", "int", min=0, max=120),
    Field("averaging_rate", "سود سالانه سپرده معدل‌گیری", "percent"),
    Field("monthly_income", "درآمد ماهانه", "money"),
    Field("current_installments", "اقساط فعلی ماهانه", "money"),
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
    keys = list(s.PRICE_KEYS)
    for key in db.scalars(select(Asset.price_key).where(Asset.price_key.is_not(None))):
        if key not in keys:
            keys.append(key)
    for key in services.latest_quotes(db):
        if key not in keys:
            keys.append(key)
    return keys


def _prices_page(request: Request, db: Session, errors: dict[str, str] | None = None,
                 status: int = 200) -> Response:
    quotes = services.latest_quotes(db)
    rows = [{"key": key, "label": s.PRICE_KEYS.get(key, key), "quote": quotes.get(key)}
            for key in _price_keys(db)]
    return page(request, "prices.html", {"active": "prices", "rows": rows,
                                         "errors": errors or {}}, status)


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
