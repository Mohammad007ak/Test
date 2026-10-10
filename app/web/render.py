"""Jinja2 با فیلترهای فارسی (تومان، درصد، تاریخ شمسی)."""

import hashlib
import re
from datetime import date, datetime
from decimal import Decimal
from functools import cache
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import jdatetime
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from markupsafe import Markup, escape
from starlette.responses import Response
from starlette.types import Scope

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
from app.web.mascot import bird_svg

TEHRAN = ZoneInfo("Asia/Tehran")
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


_VERSIONED = re.compile(r"v-[0-9a-f]{10}[/\\](.+)")


@cache
def static_url(path: str) -> str:
    """آدرس فایل استاتیک با نشانه نسخه در خود مسیر (نه ?v=)؛ CDNهایی مثل آروان که کوئری را
    نادیده می‌گیرند هم بعد از هر تغییر نسخه تازه را می‌دهند."""
    digest = hashlib.sha256((STATIC_DIR / path).read_bytes()).hexdigest()[:10]
    return f"/static/v-{digest}/{path}"


class VersionedStatic(StaticFiles):
    """/static/v-<نسخه>/... همان فایل /static/... است و چون نسخه‌دار است، تا ابد کش می‌شود."""

    async def get_response(self, path: str, scope: Scope) -> Response:
        match = _VERSIONED.fullmatch(path)
        response = await super().get_response(match.group(1) if match else path, scope)
        if match and response.status_code == 200:
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return response


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
    """مسیر SVG خط و سطح زیر آن؛ زمان مثل همه نمودارهای مالی از چپ به راست (جدیدترین راست)."""
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
    points = [(round(i * step, 1), y(v)) for i, v in enumerate(values)]
    line = " ".join(f"{'M' if i == 0 else 'L'}{x},{yy}" for i, (x, yy) in enumerate(points))
    area = f"{line} L{points[-1][0]},{height} L{points[0][0]},{height} Z"
    return line, area


_BOLD = re.compile(r"\*\*(.+?)\*\*")
_BULLET = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+")
_GROUPED = re.compile(r"(?<=\d),(?=\d{3})")


def _inline(text: str) -> str:
    text = str(escape(text))
    text = _GROUPED.sub("٬", text)
    text = _BOLD.sub(r"<strong>\1</strong>", text)
    return to_persian_digits(text)


def chat_markdown(text: str) -> Markup:
    """جواب مدل (مارک‌داون ساده) → HTML امن: پاراگراف، فهرست، پررنگ و ارقام فارسی.

    اول همه چیز escape می‌شود، پس هیچ تگی از مدل اجرا نمی‌شود.
    """
    parts: list[str] = []
    items: list[str] = []
    ordered = False

    def flush() -> None:
        nonlocal items
        if items:
            tag = "ol" if ordered else "ul"
            parts.append(f"<{tag}>" + "".join(f"<li>{i}</li>" for i in items) + f"</{tag}>")
            items = []

    for line in text.strip().splitlines():
        stripped = line.strip()
        if not stripped:
            flush()
            continue
        if _BULLET.match(stripped):
            is_ordered = stripped[0].isdigit()
            if items and is_ordered != ordered:
                flush()
            ordered = is_ordered
            items.append(_inline(_BULLET.sub("", stripped)))
            continue
        flush()
        if stripped.startswith("#"):
            parts.append(f"<p><strong>{_inline(stripped.lstrip('#').strip())}</strong></p>")
        else:
            parts.append(f"<p>{_inline(stripped)}</p>")
    flush()
    return Markup("".join(parts))


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


def price_short(value: Decimal | int | None) -> str:
    """قیمت خلاصه: بزرگ «۲۷۲ هزار تومان»، خیلی کوچک (رمزارز ارزان) با اعشار."""
    if value is None:
        return "—"
    if value >= 1000:
        return format_toman_short(int(round(value)))
    return f"{format_number(Decimal(value), 4).rstrip('۰').rstrip('٫')} تومان"


def _percent(value: Decimal | None, places: int = 1) -> str:
    return "—" if value is None else format_percent(value, places)


templates = Jinja2Templates(directory=Path(__file__).parent / "templates")
templates.env.filters.update(
    toman=format_toman,
    toman_short=format_toman_short,
    price_short=price_short,
    amt=_amount,
    unit_price=_unit_price,
    num=_number,
    percent=_percent,
    jalali=jalali,
    fa=lambda v: to_persian_digits(str(v)),
    dec=plain_decimal,
    jalali_long=jalali_long,
    chat_md=chat_markdown,
)
_UI_LABEL = re.compile(r"\[\[(.+?)\]\]")


def ui_labels(text: str) -> Markup:
    """«[[Label]]» در راهنما ← اسم دکمه آیفون، چپ‌به‌راست و پررنگ؛ بقیه متن escape می‌شود."""
    return Markup(_UI_LABEL.sub(r'<bdi class="ios-label">\1</bdi>', str(escape(text))))


templates.env.filters["ui_labels"] = ui_labels
templates.env.filters["by_value"] = lambda lines: sorted(
    lines, key=lambda line: -(line.value_toman if line.value_toman is not None else -1))
templates.env.filters["faq_item"] = lambda qa: {
    "@type": "Question", "name": qa[0], "acceptedAnswer": {"@type": "Answer", "text": qa[1]}}
_EMPHASIS = re.compile(r"\*(.+?)\*")


def emphasis(text: str) -> Markup:
    """«*واژه*» در متن درس‌های مدرسه ← <em>؛ بقیه متن escape می‌شود."""
    return Markup(_EMPHASIS.sub(r"<em>\1</em>", str(escape(text))))


templates.env.filters["em"] = emphasis
templates.env.globals.update(s=strings, T=strings.T, static=static_url, bird_svg=bird_svg)
