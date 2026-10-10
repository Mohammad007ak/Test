"""قالب یادگرفته پیامک (CLAUDE.md: قالب ناشناخته یک بار با LLM).

قالب همان متن پوشانده‌شده پیامک است که جای عددهای متغیر با جاهای خالی پر شده، مثل
«کاربر عزیز، {amount} ریال از حساب شما پرید.». LLM آن را یک بار می‌سازد؛ قالب فقط وقتی
پذیرفته می‌شود که روی همان پیامک دقیقاً همان مبلغ و مانده‌ای را بدهد که LLM گفته، و متن
ثابتش هیچ عددی نداشته باشد (قالب بین کاربران مشترک است). از آن به بعد پیامک‌های هم‌قالب
بدون LLM خوانده می‌شوند.
"""

import re
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache

from app.sms.parsers.base import ParsedSms
from app.sms.parsers.dates import jalali_to_utc, month_day_to_utc
from app.web.strings import BANKS

_NUMBER = r"-?\d[\d,]*"
PLACEHOLDERS: dict[str, str] = {
    "amount": _NUMBER,
    "balance": _NUMBER,
    "date": r"\d{1,4}[/.-]\d{1,2}(?:[/.-]\d{1,2})?",
    "time": r"\d{1,2}:\d{2}(?::\d{2})?",
    "account": r"(?:[\d*]+[-.])*[\d*]*\d{4}",
}
ANY = "any"  # متن متغیر بی‌اهمیت، مثل نام مشتری یا فروشگاه؛ چند بار مجاز
_ANY_PATTERN = r"[^\n]+?"
_TOKEN = re.compile(r"\{(\w+)\}")
UNITS = {"rial": 1, "toman": 10}
MAX_TEMPLATE = 2000
CARD_LENGTH = 16
PREFIX_MAX = 4


class TemplateError(ValueError):
    pass


@dataclass(frozen=True)
class SmsReading:
    """خواندهٔ LLM از یک پیامک؛ مبالغ به همان واحدی که در متن آمده (unit)."""

    bank: str
    direction: str  # in یا out
    amount: int
    balance: int | None
    unit: str  # rial یا toman
    template: str
    label: str = ""  # شرح ثابت قالب، مثل «برداشت پول»


@dataclass(frozen=True)
class LearnedTemplate:
    pattern: str
    bank: str
    direction: str
    unit: str
    label: str = ""


def check_template(template: str) -> None:
    """قالب معتبر: دقیقاً یک {amount}، باقی جاهای خالی حداکثر یک بار، متن ثابت بی‌عدد."""
    if not template.strip() or len(template) > MAX_TEMPLATE:
        raise TemplateError("قالب خالی یا خیلی بلند است")
    names = _TOKEN.findall(template)
    for name in names:
        if name not in PLACEHOLDERS and name != ANY:
            raise TemplateError(f"جای خالی ناشناخته: {name}")
    if names.count("amount") != 1:
        raise TemplateError("قالب باید دقیقاً یک {amount} داشته باشد")
    for name in PLACEHOLDERS:
        if names.count(name) > 1:
            raise TemplateError(f"{{{name}}} بیش از یک بار آمده")
    literal = _TOKEN.sub("", template)
    if re.search(r"\d", literal):
        raise TemplateError("متن ثابت قالب نباید عدد داشته باشد")
    if "{" in literal or "}" in literal:
        raise TemplateError("آکولاد نامعتبر در قالب")


def _literal(text: str) -> str:
    return "".join(r"\s+" if part.isspace() else re.escape(part)
                   for part in re.split(r"(\s+)", text) if part)


@lru_cache(maxsize=512)
def compile_template(template: str) -> re.Pattern[str]:
    check_template(template)
    out: list[str] = []
    position = 0
    for match in _TOKEN.finditer(template):
        out.append(_literal(template[position:match.start()]))
        name = match.group(1)
        out.append(f"({_ANY_PATTERN})" if name == ANY
                   else f"(?P<{name}>{PLACEHOLDERS[name]})")
        position = match.end()
    out.append(_literal(template[position:]))
    return re.compile(r"\s*" + "".join(out) + r"\s*")


def _number(text: str | None) -> int | None:
    return None if text is None else int(text.replace(",", ""))


def _account(text: str | None) -> tuple[str, str]:
    """(ابتدای شماره، ۴ رقم آخر) از شماره پوشانده‌شده؛ کارت ابتدای شماره ندارد."""
    if not text:
        return "", ""
    mask = text[-4:]
    if sum(c.isdigit() or c == "*" for c in text) >= CARD_LENGTH:
        return "", mask
    lead = re.match(r"\d+", text)
    prefix = lead.group(0) if lead and lead.end() < len(text) - 4 else ""
    return (prefix if len(prefix) <= PREFIX_MAX else ""), mask


def _occurred(date: str | None, clock: str | None, received_at: datetime) -> datetime | None:
    if not date:
        return None
    hour, minute = (int(clock.split(":")[0]), int(clock.split(":")[1])) if clock else (0, 0)
    parts = re.split(r"[/.-]", date)
    try:
        if len(parts) == 2:
            return month_day_to_utc(int(parts[0]), int(parts[1]), hour, minute, received_at)
        year = int(parts[0])
        if len(parts[0]) == 2:
            year += 1400
        if not 1300 <= year <= 1500:  # فقط تاریخ شمسی
            return None
        return jalali_to_utc(year, int(parts[1]), int(parts[2]), hour, minute)
    except ValueError:
        return None


def read_with(template: LearnedTemplate, text: str, received_at: datetime) -> ParsedSms | None:
    match = compile_template(template.pattern).fullmatch(text)
    if match is None:
        return None
    groups = match.groupdict()
    factor = UNITS[template.unit]
    amount = _number(groups.get("amount"))
    balance = _number(groups.get("balance"))
    prefix, mask = _account(groups.get("account"))
    return ParsedSms(
        bank=template.bank, account_mask=mask, account_prefix=prefix,
        direction=template.direction,
        amount_rial=(amount or 0) * factor,
        balance_after_rial=None if balance is None else balance * factor,
        occurred_at=_occurred(groups.get("date"), groups.get("time"), received_at),
        description=template.label,
    )


def learn(text: str, reading: SmsReading) -> LearnedTemplate:
    """قالب LLM را می‌پذیرد فقط اگر روی همین پیامک همان خوانده را بازتولید کند."""
    if reading.bank not in BANKS:
        raise TemplateError(f"بانک ناشناخته: {reading.bank}")
    if reading.direction not in ("in", "out"):
        raise TemplateError(f"جهت نامعتبر: {reading.direction}")
    if reading.unit not in UNITS:
        raise TemplateError(f"واحد نامعتبر: {reading.unit}")
    template = LearnedTemplate(pattern=reading.template.strip(), bank=reading.bank,
                               direction=reading.direction, unit=reading.unit,
                               label=reading.label.strip()[:100])
    check_template(template.pattern)
    match = compile_template(template.pattern).fullmatch(text)
    if match is None:
        raise TemplateError("قالب با متن پیامک جور نیست")
    if _number(match.group("amount")) != reading.amount:
        raise TemplateError("مبلغ قالب با خواندهٔ LLM یکی نیست")
    if _number(match.groupdict().get("balance")) != reading.balance:
        raise TemplateError("مانده قالب با خواندهٔ LLM یکی نیست")
    return template
