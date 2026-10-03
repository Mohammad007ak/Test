"""کارهای ثبت وزیر: مدل فقط «پیشنهاد» می‌دهد؛ ذخیره با ضربه کاربر روی کارت تأیید.

پیشنهاد با همان اعتبارسنجی فرم‌های اپ ساخته می‌شود (build_entity / apply_transaction)، پس
هر خطایی که فرم دستی می‌گیرد، این‌جا هم به مدل برمی‌گردد تا از کاربر بپرسد.
پیشنهادهای منتظر تأیید در user_settings («assistant_pending») نگه داشته می‌شوند.
"""

import json
import secrets
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app import services
from app.domain.money import format_toman, to_persian_digits
from app.models import Transaction
from app.web import categories, forms
from app.web import strings as s
from app.web.entities import ENTITIES, build_entity
from app.web.forms import Entity, FormError
from app.web.spending_routes import FLOWS, apply_transaction

PENDING_KEY = "assistant_pending"
MAX_PENDING = 10

# نوع کار → (موجودیت فرم، عنوان کارت)
_TITLES = {"add_asset": "دارایی", "add_liability": "بدهی", "add_income": "درآمد",
           "add_bill": "هزینه ثابت", "add_transaction": "تراکنش"}
_ENTITY_OF = {"add_asset": "assets", "add_liability": "liabilities", "add_income": "incomes",
              "add_bill": "bills"}
_FLOW_OF = {flow.direction: flow for flow in FLOWS}


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "on" if value else ""
    if isinstance(value, float):
        return format(Decimal(str(value)), "f")
    return str(value)


def _form_data(name: str, args: dict[str, Any]) -> dict[str, str]:
    data = {key: _text(value) for key, value in args.items()}
    if name == "add_liability" and "nominal_rate_percent" in data:
        data["nominal_rate"] = data.pop("nominal_rate_percent")
    if name in ("add_income", "add_bill"):
        data.setdefault("active", "on")
    if name == "add_asset" and data.get("kind") == "gold":
        data.setdefault("karat", "18")
    return data


def _entity(db: Session, name: str, data: dict[str, str]) -> Entity:
    if name == "add_transaction":
        direction = data.get("direction", "out")
        if direction not in _FLOW_OF:
            raise FormError({"direction": "out (خرج) یا in (واریز)"})
        options = categories.options(db, direction)
        label_to_key = {label: key for key, label in options.items()}
        category = data.get("category", "")
        data["category"] = category if category in options else label_to_key.get(category, "other")
        return categories.with_options(_FLOW_OF[direction].manual, db, direction)
    return ENTITIES[_ENTITY_OF[name]]


def _build(db: Session, name: str, data: dict[str, str]) -> Any:
    entity = _entity(db, name, data)
    if name == "add_transaction":
        tx = Transaction(direction=data["direction"] if data.get("direction") else "out",
                         account_id=None)
        apply_transaction(entity, data, tx)
        return tx, entity
    return build_entity(entity, data), entity


def _summary(entity: Entity, data: dict[str, str]) -> list[list[str]]:
    rows = []
    values = forms.parse_form(entity.fields, data)
    for field in entity.fields:
        value = values.get(field.name)
        if value in (None, "", False) or field.type == "bool":
            continue
        if field.type == "select":
            shown = field.options.get(value, value)
        elif field.type == "money":
            shown = format_toman(value)
        elif field.type == "percent":
            shown = forms.plain_decimal(value * 100) + "٪"
        else:
            shown = forms.display_value(field, value)
        rows.append([field.label, to_persian_digits(str(shown))])
    return rows


def _load(db: Session) -> dict[str, dict[str, Any]]:
    raw = services.get_user_setting(db, PENDING_KEY)
    return json.loads(raw) if raw else {}


def _store(db: Session, pending: dict[str, dict[str, Any]]) -> None:
    kept = dict(list(pending.items())[-MAX_PENDING:])
    services.set_user_setting(db, PENDING_KEY, json.dumps(kept, ensure_ascii=False))


def propose(db: Session, name: str, args: dict[str, Any]) -> dict[str, Any]:
    """اعتبارسنجی و نگه داشتن پیشنهاد؛ هیچ چیزی ذخیره نمی‌شود."""
    data = _form_data(name, args)
    try:
        _obj, entity = _build(db, name, data)
    except FormError as exc:
        labels = {f.name: f.label for f in _entity(db, name, dict(data)).fields}
        return {"error": "این موارد درست نیست یا کم است؛ از کاربر بپرس: " + "، ".join(
            f"{labels.get(k, k)} ({v})" for k, v in exc.errors.items())}
    action_id = secrets.token_hex(6)
    title = _TITLES[name]
    if name == "add_transaction":
        title = "واریز" if data.get("direction") == "in" else "خرج"
    pending = _load(db)
    pending[action_id] = {"name": name, "data": data, "title": title,
                          "summary": _summary(entity, data)}
    _store(db, pending)
    db.commit()
    return {"status": "pending_confirmation", "action_id": action_id,
            "note": "هنوز ثبت نشده؛ به کاربر بگو کارت تأیید زیر پیام را بزند."}


def pending(db: Session) -> dict[str, dict[str, Any]]:
    return _load(db)


def confirm(db: Session, action_id: str) -> dict[str, Any] | None:
    store = _load(db)
    action = store.pop(action_id, None)
    if action is None:
        return None
    obj, _entity_ = _build(db, action["name"], dict(action["data"]))
    db.add(obj)
    _store(db, store)
    db.commit()
    return action


def cancel(db: Session, action_id: str) -> dict[str, Any] | None:
    store = _load(db)
    action = store.pop(action_id, None)
    if action is not None:
        _store(db, store)
        db.commit()
    return action


# ---------- تعریف ابزارهای ثبت برای مدل ----------

def _tool(name: str, description: str, properties: dict[str, Any],
          required: list[str]) -> dict[str, Any]:
    return {"type": "function", "function": {
        "name": name, "description": description + " ثبت فقط بعد از تأیید کاربر انجام می‌شود.",
        "parameters": {"type": "object", "properties": properties, "required": required,
                       "additionalProperties": False}}}


_INT = {"type": "integer"}
_STR = {"type": "string"}
_FREQ = {"type": "string", "enum": list(s.FREQUENCIES)}

ACTION_TOOLS: list[dict[str, Any]] = [
    _tool("add_asset", "پیشنهاد ثبت دارایی تازه. برای طلا مقدار گرم و عیار، برای ارز کد ارز و "
                       "مقدار، برای سکه نوع سکه و تعداد، برای سهام و صندوق نماد و تعداد، برای "
                       "رمزارز کد و مقدار؛ برای خودرو، ملک، طلب، نقد و سایر ارزش فعلی به تومان.",
          {"kind": {"type": "string", "enum": list(s.ASSET_KINDS)}, "name": _STR,
           "quantity": {"type": "number"}, "karat": _INT,
           "currency": {"type": "string", "enum": list(s.CURRENCY_NAMES)},
           "coin_type": {"type": "string", "enum": list(s.COIN_KEYS)},
           "crypto_symbol": {"type": "string", "enum": list(s.CRYPTO_NAMES)},
           "symbol": {"type": "string", "description": "نماد سهم، مثل فملی"},
           "fund_symbol": {"type": "string", "description": "نماد صندوق، مثل عیار"},
           "manual_value_toman": _INT, "note": _STR},
          ["kind", "name"]),
    _tool("add_liability", "پیشنهاد ثبت بدهی یا وام تازه.",
          {"kind": {"type": "string", "enum": list(s.LIABILITY_KINDS)}, "lender": _STR,
           "principal_toman": _INT, "installment_toman": _INT, "installments_total": _INT,
           "installments_paid": _INT, "due_day": _INT,
           "nominal_rate_percent": {"type": "number", "description": "مثلاً 23 یعنی ۲۳٪"},
           "start_date": {"type": "string", "description": "شمسی YYYY/MM/DD"}, "note": _STR},
          ["kind", "lender", "principal_toman"]),
    _tool("add_transaction", "پیشنهاد ثبت یک خرج (out) یا واریز (in) نقدی یا دستی. دسته را از "
                             "دسته‌های کاربر انتخاب کن (نام فارسی یا کلید).",
          {"direction": {"type": "string", "enum": ["out", "in"]}, "amount_toman": _INT,
           "category": _STR, "description": _STR,
           "occurred_on": {"type": "string", "description": "شمسی YYYY/MM/DD؛ خالی = امروز"}},
          ["direction", "amount_toman", "category"]),
    _tool("add_income", "پیشنهاد ثبت درآمد تکراری (حقوق، اجاره، ...).",
          {"name": _STR, "amount_toman": _INT, "frequency": _FREQ},
          ["name", "amount_toman", "frequency"]),
    _tool("add_bill", "پیشنهاد ثبت هزینه ثابت تکراری (اجاره، قبض، شهریه، بیمه، ...).",
          {"name": _STR, "amount_toman": _INT, "frequency": _FREQ,
           "category": {"type": "string", "enum": list(s.EXPENSE_CATEGORIES)}},
          ["name", "amount_toman", "frequency"]),
]
