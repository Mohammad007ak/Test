"""دخل و خرج واقعی: فهرست ماهانه به تفکیک دسته برای برداشت‌ها (خرج) و واریزها.

تراکنش دستی (نقدی) کامل ویرایش و حذف می‌شود؛ تراکنش پیامکی سابقه بانک است و فقط
دسته و شرحش عوض می‌شود.
"""

from dataclasses import dataclass
from datetime import date, datetime, time
from typing import Any

import jdatetime
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, Response

from app import services
from app.domain.spending import TEHRAN, shift_month
from app.models import Transaction
from app.web import forms
from app.web import strings as s
from app.web.common import Db, LoggedIn, done, page, read_form, wants_fragment
from app.web.forms import Entity, FormError


@dataclass(frozen=True)
class Flow:
    slug: str
    direction: str  # out: خرج، in: واریز
    manual: Entity
    from_sms: Entity
    total_label: str
    transfer_note: str
    show_fixed: bool


FLOWS = (
    Flow("spending", "out", Entity("spending", "خرج", forms.SPENDING_FIELDS, Transaction),
         Entity("spending", "خرج", forms.SPENDING_SMS_FIELDS, Transaction),
         s.T["spending_total"], s.T["transfer_note"], show_fixed=True),
    Flow("deposits", "in", Entity("deposits", "واریز", forms.DEPOSIT_FIELDS, Transaction),
         Entity("deposits", "واریز", forms.DEPOSIT_SMS_FIELDS, Transaction),
         s.T["deposit_total"], s.T["transfer_note_in"], show_fixed=False),
)


def parse_month(text: str | None) -> tuple[int, int]:
    """«1405-07» → (۱۴۰۵, ۷)؛ ورودی نامعتبر یا خالی = ماه جاری تهران."""
    try:
        year, month = (int(part) for part in forms.normalize_digits(text or "").split("-"))
        if 1 <= month <= 12 and 1300 <= year <= 1500:
            return year, month
    except ValueError:
        pass
    today = jdatetime.datetime.now(TEHRAN)
    return today.year, today.month


def _is_manual(tx: Transaction) -> bool:
    return tx.account_id is None and tx.sms_id is None


def _noon_tehran(day: date) -> datetime:
    return datetime.combine(day, time(12), tzinfo=TEHRAN)


def _form_values(entity: Entity, tx: Transaction) -> dict[str, str]:
    raw: dict[str, Any] = {
        "amount_toman": tx.amount_toman, "category": tx.category or "",
        "description": tx.description or "",
        "occurred_on": tx.occurred_at.astimezone(TEHRAN).date(),
    }
    return {f.name: forms.display_value(f, raw.get(f.name)) for f in entity.fields}


def register_spending_routes(app: FastAPI) -> None:
    for flow in FLOWS:
        _register_flow(app, flow)


def _register_flow(app: FastAPI, flow: Flow) -> None:
    base = f"/{flow.slug}"

    def entity_of(tx: Transaction) -> Entity:
        return flow.manual if _is_manual(tx) else flow.from_sms

    def _form(request: Request, entity: Entity, values: dict[str, str],
              errors: dict[str, str] | None = None, edit_id: int | None = None,
              status: int = 200) -> Response:
        fragment = wants_fragment(request)
        if fragment and status >= 400:
            status = 422
        return page(request, "sheet_form.html" if fragment else "form_page.html", {
            "active": flow.slug, "entity": entity, "fields": entity.fields,
            "values": values, "errors": errors or {}, "edit_id": edit_id,
            "no_delete": entity is flow.from_sms,
        }, status)

    def _tx(db: Db, tx_id: int) -> Transaction:
        tx = db.get(Transaction, tx_id)
        if tx is None or tx.direction != flow.direction:
            raise HTTPException(404)
        return tx

    def _apply(entity: Entity, data: dict[str, str], tx: Transaction) -> None:
        values = forms.parse_form(entity.fields, data)
        tx.category = values["category"]
        tx.description = values["description"] or None
        if entity is flow.manual:
            if values["amount_toman"] <= 0:
                raise FormError({"amount_toman": s.T["invalid_number"]})
            tx.amount_toman = values["amount_toman"]
            day = values["occurred_on"] or datetime.now(TEHRAN).date()
            tx.occurred_at = _noon_tehran(day)

    def listing(request: Request, db: Db) -> Response:
        year, month = parse_month(request.query_params.get("m"))
        result = services.month_spending(db, year, month, flow.direction)
        portfolio = services.build_portfolio(db)
        top = result.by_category[0].total_toman if result.by_category else 0
        prev, next_ = shift_month(year, month, -1), shift_month(year, month, 1)
        return page(request, "spending.html", {
            "active": flow.slug, "flow": flow, "result": result, "top": top,
            "month_label": f"{s.JALALI_MONTHS[month - 1]} {forms.to_persian_digits(str(year))}",
            "prev": f"{prev[0]}-{prev[1]:02d}", "next": f"{next_[0]}-{next_[1]:02d}",
            "fixed_toman": portfolio.monthly_fixed_expenses_toman if flow.show_fixed else 0,
            "accounts": {a.id: a for a in portfolio.accounts},
        })

    def new(request: Request) -> Response:
        return _form(request, flow.manual, {})

    async def create(request: Request, db: Db) -> Response:
        data = await read_form(request)
        tx = Transaction(direction=flow.direction, account_id=None)
        try:
            _apply(flow.manual, data, tx)
        except FormError as exc:
            return _form(request, flow.manual, data, exc.errors, status=400)
        db.add(tx)
        db.commit()
        return done(request, base, s.TOASTS["created"].format(title=flow.manual.title))

    def edit(request: Request, tx_id: int, db: Db) -> Response:
        tx = _tx(db, tx_id)
        entity = entity_of(tx)
        return _form(request, entity, _form_values(entity, tx), edit_id=tx_id)

    async def update(request: Request, tx_id: int, db: Db) -> Response:
        tx = _tx(db, tx_id)
        entity = entity_of(tx)
        data = await read_form(request)
        try:
            _apply(entity, data, tx)
        except FormError as exc:
            db.rollback()
            return _form(request, entity, data, exc.errors, edit_id=tx_id, status=400)
        db.commit()
        return done(request, base, s.TOASTS["updated"])

    def delete(request: Request, tx_id: int, db: Db) -> Response:
        tx = _tx(db, tx_id)
        if not _is_manual(tx):  # تراکنش پیامکی سابقه بانک است؛ فقط دسته‌اش عوض می‌شود
            raise HTTPException(404)
        db.delete(tx)
        db.commit()
        return done(request, base, s.TOASTS["deleted"].format(title=flow.manual.title))

    html = {"response_class": HTMLResponse, "dependencies": [LoggedIn]}
    app.add_api_route(base, listing, methods=["GET"], **html)
    app.add_api_route(f"{base}/new", new, methods=["GET"], **html)
    app.add_api_route(base, create, methods=["POST"], **html)
    app.add_api_route(f"{base}/{{tx_id}}/edit", edit, methods=["GET"], **html)
    app.add_api_route(f"{base}/{{tx_id}}", update, methods=["POST"], **html)
    app.add_api_route(f"{base}/{{tx_id}}/delete", delete, methods=["POST"],
                      dependencies=[LoggedIn])
