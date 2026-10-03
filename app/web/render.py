"""Jinja2 با فیلترهای فارسی (تومان، درصد، تاریخ شمسی)."""

import hashlib
from datetime import date, datetime
from decimal import Decimal
from functools import cache
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import jdatetime
from fastapi.templating import Jinja2Templates
from markupsafe import Markup

from app.domain.money import (
    format_number,
    format_percent,
    format_toman,
    format_toman_short,
    to_persian_digits,
    toman_short_parts,
)
from app.web import strings
from app.web.forms import plain_decimal

TEHRAN = ZoneInfo("Asia/Tehran")
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


@cache
def static_url(path: str) -> str:
    """آدرس فایل استاتیک با نشانه نسخه؛ پس از هر تغییر، مرورگر نسخه کش‌شده قدیمی را کنار می‌گذارد."""
    digest = hashlib.sha256((STATIC_DIR / path).read_bytes()).hexdigest()[:10]
    return f"/static/{path}?v={digest}"


def jalali(value: datetime | date | None, with_time: bool = True) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        local = jdatetime.datetime.fromgregorian(datetime=value.astimezone(TEHRAN))
        text = local.strftime("%Y/%m/%d %H:%M" if with_time else "%Y/%m/%d")
    else:
        text = jdatetime.date.fromgregorian(date=value).strftime("%Y/%m/%d")
    return to_persian_digits(text)


def tehran_today() -> date:
    return datetime.now(TEHRAN).date()


def _amount(toman: int) -> Markup:
    number, unit = toman_short_parts(toman)
    return Markup('<span class="amt">{}<small>{}</small></span>').format(number, unit)


def _unit_price(quote: Any) -> str:
    """قیمت یک واحد؛ برای رمزارزهای خیلی ارزان با رقم اعشار («۱٫۵۳۱۴۷۶ تومان»)."""
    if quote.units == 1:
        return format_toman(quote.price_toman)
    places = len(str(quote.units)) - 1
    text = format_number(quote.per_unit, places).rstrip("۰").rstrip("٫")
    return f"{text} تومان"


def _number(value: Decimal | int | None, places: int = 0) -> str:
    return "" if value is None else format_number(value, places)


def _percent(value: Decimal | None, places: int = 1) -> str:
    return "—" if value is None else format_percent(value, places)


templates = Jinja2Templates(directory=Path(__file__).parent / "templates")
templates.env.filters.update(
    toman=format_toman,
    toman_short=format_toman_short,
    amt=_amount,
    unit_price=_unit_price,
    num=_number,
    percent=_percent,
    jalali=jalali,
    fa=lambda v: to_persian_digits(str(v)),
    dec=plain_decimal,
)
templates.env.globals.update(s=strings, T=strings.T, static=static_url)
