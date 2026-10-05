"""کارهای ثبت وزیر: مدل فقط «پیشنهاد» می‌دهد؛ ذخیره با ضربه کاربر روی کارت تأیید.

پیشنهاد با همان اعتبارسنجی فرم‌های اپ ساخته می‌شود (build_entity / apply_transaction)، پس
هر خطایی که فرم دستی می‌گیرد، این‌جا هم به مدل برمی‌گردد تا از کاربر بپرسد.
پیشنهادهای منتظر تأیید در user_settings («assistant_pending») نگه داشته می‌شوند.
"""

import json
import secrets
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app import services
from app import split_service as dong
from app.domain import split
from app.domain.money import format_toman, to_persian_digits
from app.models import Transaction
from app.web import categories, forms
from app.web import strings as s
from app.web.entities import ENTITIES, build_entity
from app.web.forms import Entity, FormError
from app.web.spending_routes import FLOWS, apply_transaction

PENDING_KEY = "assistant_pending"
MAX_PENDING = 40  # یک اسکرین‌شات پرتفوی ممکن است ده‌ها سهم داشته باشد

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


# ---------- دنگ: خرج گروهی (گروه موجود، یا گروه تازه با همان کارت) ----------

def _split_plan(db: Session, args: dict[str, Any]) -> dict[str, Any]:
    """آرگومان‌های مدل ← برنامه دقیق خرج (اسم‌ها و سهم‌ها)؛ هیچ چیزی ذخیره نمی‌شود."""
    ref = dong.clean(str(args.get("group") or ""), dong.MAX_GROUP_NAME)
    groups = dong.all_groups(db)
    view = next((v for v in groups if dong.clean(v.group.name).casefold() == ref.casefold()),
                None)
    new_members = [str(n) for n in args.get("new_group_members") or []]
    if view is not None:
        members = [m.name for m in view.members]
        me = view.names[view.me] if view.me is not None else members[0]
    elif new_members:
        ref, me, others = dong.validate_group(ref, s.DONG["me"], new_members)
        members = [me, *others]
    else:
        existing = "، ".join(v.group.name for v in groups) or "هیچ گروهی"
        raise dong.SplitInputError({"group": f"گروه «{ref}» نیست (گروه‌ها: {existing}). یا اسم "
                                             "درست را بپرس، یا new_group_members بده تا ساخته شود"})

    def resolve(raw: Any) -> str:
        wanted = dong.clean(str(raw or ""))
        if wanted.casefold() in dong.SELF_NAMES:
            return me
        for member in members:
            if member.casefold() == wanted.casefold():
                return member
        raise dong.SplitInputError({"member": f"«{wanted}» عضو گروه نیست؛ اعضا: "
                                              + "، ".join(members)})

    try:
        amount = int(args.get("amount_toman") or 0)
    except (TypeError, ValueError):
        amount = 0
    index = {name: i for i, name in enumerate(members)}
    exact = args.get("exact_shares") or {}
    try:
        if exact:
            by_index = split.split_exact(amount, {index[resolve(k)]: int(v)
                                                  for k, v in dict(exact).items()})
        else:
            chosen = [index[resolve(n)] for n in args.get("participants") or []] or list(
                index.values())
            by_index = split.split_equal(amount, list(dict.fromkeys(chosen)))
    except split.SplitError as exc:
        raise dong.SplitInputError({"amount": str(exc)}) from exc
    options = categories.options(db, "out")
    label_to_key = {label: key for key, label in options.items()}
    category = str(args.get("category") or "")
    spent_on = None
    if args.get("spent_on"):
        spent_on = forms.parse_form([forms.Field("spent_on", "تاریخ", "date")],
                                    {"spent_on": str(args["spent_on"])})["spent_on"]
    return {
        "group": ref, "new_members": [] if view else members[1:], "me": me,
        "title": dong.clean(str(args.get("title") or s.DONG["title"]), dong.MAX_TITLE),
        "amount": amount, "payer": resolve(args.get("payer") or "من"),
        "shares": {members[i]: v for i, v in by_index.items()},
        "category": category if category in options else label_to_key.get(category, "other"),
        "spent_on": spent_on.isoformat() if spent_on else None,
    }


def _split_summary(plan: dict[str, Any]) -> list[list[str]]:
    group = plan["group"] + (" (" + s.DONG["new_group"] + ")" if plan["new_members"] else "")
    shares = "، ".join(f"{name} {format_toman(v)}" for name, v in plan["shares"].items())
    rows = [[s.DONG["group_name"], group], [s.DONG["expense_title"], plan["title"]],
            [s.DONG["amount"], format_toman(plan["amount"])], [s.DONG["payer"], plan["payer"]],
            [s.DONG["who"], shares]]
    mine = plan["shares"].get(plan["me"], 0)
    if mine and plan["payer"] != plan["me"]:
        rows.append([s.DONG["my_share"].format(amount=format_toman(mine)),
                     s.DONG["my_share_note"]])
    return [[label, to_persian_digits(value)] for label, value in rows]


def _split_execute(db: Session, plan: dict[str, Any]) -> None:
    if plan["new_members"]:
        group = dong.create_group(db, plan["group"], plan["me"], plan["new_members"])
    else:
        group = next(v.group for v in dong.all_groups(db)
                     if dong.clean(v.group.name).casefold() == plan["group"].casefold())
    view = dong.load_group(db, group)
    ids = {view.names[i]: i for i in view.names}
    dong.record_expense(db, view, plan["title"], plan["amount"], ids[plan["payer"]],
                        {ids[n]: v for n, v in plan["shares"].items()}, plan["category"],
                        date.fromisoformat(plan["spent_on"]) if plan["spent_on"] else None)


def _propose_split(db: Session, args: dict[str, Any]) -> dict[str, Any]:
    try:
        plan = _split_plan(db, args)
    except (dong.SplitInputError, FormError) as exc:
        return {"error": "این موارد درست نیست یا کم است؛ از کاربر بپرس: " + "، ".join(
            exc.errors.values())}
    action_id = secrets.token_hex(6)
    pending = _load(db)
    pending[action_id] = {"name": "add_split_expense", "data": args, "title": s.DONG["title"],
                          "summary": _split_summary(plan)}
    _store(db, pending)
    db.commit()
    return {"status": "pending_confirmation", "action_id": action_id, "plan": plan,
            "note": "هنوز ثبت نشده؛ به کاربر بگو کارت تأیید زیر پیام را بزند."}


def propose(db: Session, name: str, args: dict[str, Any]) -> dict[str, Any]:
    """اعتبارسنجی و نگه داشتن پیشنهاد؛ هیچ چیزی ذخیره نمی‌شود."""
    if name == "add_split_expense":
        return _propose_split(db, args)
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
    if action["name"] == "add_split_expense":
        # دوباره با داده امروز اعتبارسنجی؛ اگر گروه یا عضوی حذف شده باشد FormError می‌دهد
        try:
            _split_execute(db, _split_plan(db, dict(action["data"])))
        except dong.SplitInputError as exc:
            raise FormError(exc.errors) from exc
    else:
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
    _tool("add_split_expense",
          "پیشنهاد ثبت خرج گروهی در دنگ (شام، سفر، خرید مشترک). اول dong_groups را صدا بزن. "
          "payer کسی است که حساب کرد («من» یعنی خود کاربر). participants خالی یعنی تقسیم "
          "مساوی بین همه اعضا؛ برای سهم نامساوی exact_shares (اسم ← تومان) که جمعش دقیقاً "
          "مبلغ باشد. اگر گروه وجود ندارد، new_group_members (اسم دوستان، بدون خود کاربر) "
          "بده تا با همین کارت ساخته شود.",
          {"group": {"type": "string", "description": "اسم گروه، مثل «سفر شمال»"},
           "title": _STR, "amount_toman": _INT,
           "payer": {"type": "string", "description": "اسم عضو یا «من»"},
           "participants": {"type": "array", "items": _STR},
           "exact_shares": {"type": "object", "additionalProperties": _INT},
           "category": _STR,
           "spent_on": {"type": "string", "description": "شمسی YYYY/MM/DD؛ خالی = امروز"},
           "new_group_members": {"type": "array", "items": _STR}},
          ["group", "title", "amount_toman", "payer"]),
    _tool("add_bill", "پیشنهاد ثبت هزینه ثابت تکراری (اجاره، قبض، شهریه، بیمه، ...).",
          {"name": _STR, "amount_toman": _INT, "frequency": _FREQ,
           "category": {"type": "string", "enum": list(s.EXPENSE_CATEGORIES)}},
          ["name", "amount_toman", "frequency"]),
]
