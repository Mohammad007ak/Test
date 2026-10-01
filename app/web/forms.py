"""تعریف فرم‌ها و تبدیل ورودی کاربر به مقادیر مدل (مبالغ: int تومانی)."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any

import jdatetime

from app.domain.money import format_number, round_toman, to_persian_digits
from app.domain.normalize import normalize_digits, normalize_text, parse_decimal, parse_int
from app.web import strings as s


class FormError(Exception):
    def __init__(self, errors: dict[str, str]) -> None:
        super().__init__(errors)
        self.errors = errors


@dataclass(frozen=True)
class Field:
    name: str
    label: str
    type: str  # text | money | decimal | int | percent | select | date | textarea | bool
    required: bool = False
    options: Mapping[str, str] = field(default_factory=dict)
    kinds: tuple[str, ...] = ()  # فقط برای این kindها نمایش داده می‌شود
    hint: str = ""
    min: int | None = None
    max: int | None = None

    @property
    def unit(self) -> str:
        return {"money": "تومان", "percent": "٪"}.get(self.type, "")


def _parse_jalali(text: str) -> date:
    parts = normalize_digits(text).replace("-", "/").split("/")
    if len(parts) != 3:
        raise ValueError(text)
    year, month, day = (int(p) for p in parts)
    return jdatetime.date(year, month, day).togregorian()


def _parse_value(spec: Field, raw: str) -> Any:
    if spec.type == "text" or spec.type == "textarea":
        return normalize_text(raw)
    if spec.type == "money":
        return round_toman(parse_decimal(raw))
    if spec.type == "decimal":
        return parse_decimal(raw)
    if spec.type == "percent":
        return parse_decimal(raw) / 100
    if spec.type == "int":
        value = parse_int(raw)
        if (spec.min is not None and value < spec.min) or (
            spec.max is not None and value > spec.max
        ):
            raise OverflowError
        return value
    if spec.type == "select":
        if raw not in spec.options:
            raise LookupError
        return raw
    if spec.type == "date":
        return _parse_jalali(raw)
    raise AssertionError(spec.type)


def parse_form(fields: list[Field], data: Mapping[str, str]) -> dict[str, Any]:
    """مقادیر معتبر برای فیلدهای مرتبط با kind انتخاب‌شده؛ فیلدهای نامرتبط None می‌شوند."""
    kind = data.get("kind", "")
    values: dict[str, Any] = {}
    errors: dict[str, str] = {}
    for spec in fields:
        if spec.kinds and kind not in spec.kinds:
            values[spec.name] = None
            continue
        if spec.type == "bool":
            values[spec.name] = data.get(spec.name) in ("on", "true", "1")
            continue
        raw = (data.get(spec.name) or "").strip()
        if not raw:
            if spec.required:
                errors[spec.name] = s.T["required"]
            values[spec.name] = None
            continue
        try:
            values[spec.name] = _parse_value(spec, raw)
        except OverflowError:
            errors[spec.name] = s.T["out_of_range"]
        except LookupError:
            errors[spec.name] = s.T["invalid_choice"]
        except ValueError:
            errors[spec.name] = s.T["invalid_date" if spec.type == "date" else "invalid_number"]
    if errors:
        raise FormError(errors)
    return values


def plain_decimal(value: Decimal) -> str:
    """Decimal('1000.00') → «۱۰۰۰»، بدون نماد علمی (normalize به تنهایی 1E+3 می‌دهد)."""
    return to_persian_digits(f"{value.normalize():f}")


def display_value(spec: Field, value: Any) -> str:
    """مقدار مدل → متن داخل فیلد فرم برای ویرایش."""
    if value is None:
        return ""
    if spec.type == "money":
        return format_number(value)
    if spec.type == "percent":
        return plain_decimal(value * 100)
    if spec.type == "decimal":
        return plain_decimal(value)
    if spec.type == "int":
        return to_persian_digits(str(value))
    if spec.type == "date":
        return to_persian_digits(jdatetime.date.fromgregorian(date=value).strftime("%Y/%m/%d"))
    return str(value)


MARKET_OPTIONS = {k: s.PRICE_KEYS[k] for k in (*s.FX_KEYS, *s.COIN_KEYS)}

ASSET_FIELDS = [
    Field("kind", "نوع", "select", required=True, options=s.ASSET_KINDS),
    Field("name", "نام", "text", required=True, hint="مثلاً «دلار کیف پول» یا «پژو ۲۰۷ مدل ۱۴۰۰»"),
    Field("market", "کدام", "select", required=True, options=MARKET_OPTIONS,
          kinds=("fx", "coin")),
    Field("symbol", "نماد", "text", required=True, kinds=("stock", "fund"), hint="مثلاً فولاد"),
    Field("quantity", "مقدار", "decimal", required=True,
          kinds=("fx", "gold", "coin", "stock", "fund"),
          hint="گرم، عدد سکه، تعداد سهم یا واحد ارز"),
    Field("karat", "عیار", "int", required=True, kinds=("gold",), min=1, max=24),
    Field("manual_value_toman", "ارزش فعلی", "money", required=True,
          kinds=("car", "real_estate", "receivable", "cash", "other")),
    Field("note", "یادداشت", "textarea"),
]

ACCOUNT_FIELDS = [
    Field("bank", "بانک", "select", required=True, options=s.BANKS),
    Field("account_mask", "۴ رقم آخر", "text", required=True, hint=s.T["mask_hint"]),
    Field("label", "عنوان", "text"),
    Field("balance_toman", "موجودی", "money", required=True),
]

LIABILITY_FIELDS = [
    Field("kind", "نوع", "select", required=True, options=s.LIABILITY_KINDS),
    Field("lender", "وام‌دهنده یا طرف حساب", "text", required=True),
    Field("principal_toman", "اصل مبلغ", "money", required=True),
    Field("installment_toman", "مبلغ هر قسط", "money", hint="برای بدهی بدون قسط خالی بگذار"),
    Field("installments_total", "تعداد کل اقساط", "int", min=0, max=600),
    Field("installments_paid", "اقساط پرداخت‌شده", "int", min=0, max=600),
    Field("due_day", "روز سررسید در ماه", "int", min=1, max=31),
    Field("nominal_rate", "نرخ اسمی سالانه", "percent"),
    Field("start_date", "تاریخ شروع", "date", hint="شمسی، مثل ۱۴۰۴/۰۱/۱۵"),
    Field("note", "یادداشت", "textarea"),
]

INCOME_FIELDS = [
    Field("name", "عنوان", "text", required=True, hint="حقوق، اجاره، ..."),
    Field("amount_toman", "مبلغ هر دوره", "money", required=True),
    Field("frequency", "دوره پرداخت", "select", required=True, options=s.FREQUENCIES),
    Field("active", "فعال", "bool"),
]


@dataclass(frozen=True)
class Entity:
    """پیکربندی CRUD عمومی برای یک جدول."""

    slug: str
    title: str
    fields: list[Field]
    model: type
    to_model: Callable[[dict[str, Any]], dict[str, Any]] = lambda v: v
    from_model: Callable[[Any], dict[str, Any]] | None = None
    validate: Callable[[dict[str, Any]], dict[str, str]] = lambda v: {}
