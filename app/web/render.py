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


def jalali_long(day: date) -> str:
    """۳ اکتبر ۲۰۲۶ → «شنبه ۱۱ مهر»."""
    j = jdatetime.date.fromgregorian(date=day)
    weekday = strings.WEEKDAYS[j.weekday()]
    return f"{weekday} {to_persian_digits(str(j.day))} {strings.JALALI_MONTHS[j.month - 1]}"


def sparkline(values: list[int], width: int = 300, height: int = 56) -> tuple[str, str]:
    """مسیر SVG خط و سطح زیر آن؛ راست‌به‌چپ: قدیمی‌ترین راست، جدیدترین چپ."""
    if len(values) < 2:
        return "", ""
    low, high = min(values), max(values)
    pad = height * 0.08
    span = high - low

    def y(v: int) -> float:
        if not span:
            return height / 2
        return round(pad + (high - v) / span * (height - 2 * pad), 1)

    step = width / (len(values) - 1)
    points = [(round(width - i * step, 1), y(v)) for i, v in enumerate(values)]
    line = " ".join(f"{'M' if i == 0 else 'L'}{x},{yy}" for i, (x, yy) in enumerate(points))
    area = f"{line} L{points[-1][0]},{height} L{points[0][0]},{height} Z"
    return line, area


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
    jalali_long=jalali_long,
)
templates.env.globals.update(s=strings, T=strings.T, static=static_url)
