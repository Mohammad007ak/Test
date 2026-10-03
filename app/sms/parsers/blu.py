"""پارسر پیامک بلو (بانک دیجیتال سامان).

نمونه تأییدشده (۹ مهر ۱۴۰۵؛ نام کاربر عوض شده):
    بلو
    برداشت پول
    کاربر عزیز، 30,000,000 ریال از حساب شما پرید.
    موجودی: 86,552,338 ریال
    16:12
    1405.07.09
پیامک بلو شماره حساب ندارد؛ account_mask خالی است و تنها حساب بلو استفاده می‌شود.
«واریز …» پذیرفته می‌شود ولی هنوز با نمونه واقعی تأیید نشده؛ قالب دیگر به صف بررسی می‌رود.
"""

import re
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import jdatetime

from app.sms.parsers.base import ParsedSms

TEHRAN = ZoneInfo("Asia/Tehran")

_HEADER = "بلو"
_KIND = re.compile(r"^(برداشت|واریز)[^\n]*$", re.M)
_AMOUNT = re.compile(r"([\d,]+) ریال (?:از|به) حساب شما")
_BALANCE = re.compile(r"^موجودی: (-?[\d,]+) ریال$", re.M)
_TIME = re.compile(r"^(\d{1,2}):(\d{2})$", re.M)
_DATE = re.compile(r"^(\d{4})[./](\d{1,2})[./](\d{1,2})$", re.M)


def _rial(text: str) -> int:
    return int(text.replace(",", ""))


class BluParser:
    name = "blu"

    def can_parse(self, text: str) -> bool:
        return text.split("\n", 1)[0].strip() == _HEADER

    def parse(self, text: str, received_at: datetime) -> ParsedSms:
        kind = _KIND.search(text)
        amount = _AMOUNT.search(text)
        if not (kind and amount):
            raise ValueError("قالب پیامک بلو ناشناخته است")
        balance = _BALANCE.search(text)
        return ParsedSms(
            bank="blu",
            account_mask="",
            direction="out" if kind.group(1) == "برداشت" else "in",
            amount_rial=_rial(amount.group(1)),
            balance_after_rial=_rial(balance.group(1)) if balance else None,
            occurred_at=_occurred(text),
            description=kind.group(0).strip(),
        )


def _occurred(text: str) -> datetime | None:
    date = _DATE.search(text)
    if not date:
        return None
    clock = _TIME.search(text)
    hour, minute = (int(clock.group(1)), int(clock.group(2))) if clock else (0, 0)
    local = jdatetime.datetime(int(date.group(1)), int(date.group(2)), int(date.group(3)),
                               hour, minute).togregorian()
    return local.replace(tzinfo=TEHRAN).astimezone(UTC)
