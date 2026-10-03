"""پارسر پیامک بانک سامان.

نمونه تأییدشده (۱۱ مهر ۱۴۰۵)، پس از پوشاندن شماره:
    بانک سامان
    برداشت مبلغ 127,100 انتقال وجه
    از *********5671
    مانده 46,294,698
    1405/7/11
    12:10:53
مبالغ ریالی‌اند. «واریز مبلغ … / به …» هم پذیرفته می‌شود ولی هنوز با نمونه واقعی تأیید نشده؛
هر قالب دیگری (مثلاً رمز پویا) به صف بررسی می‌رود، نه حدس.
"""

import re
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import jdatetime

from app.sms.parsers.base import ParsedSms

TEHRAN = ZoneInfo("Asia/Tehran")

_HEADER = "بانک سامان"
_AMOUNT = re.compile(r"^(برداشت|واریز) مبلغ ([\d,]+)\s*(.*)$", re.M)
_ACCOUNT = re.compile(r"^(?:از|به) \*+(\d{4})$", re.M)
_BALANCE = re.compile(r"^مانده (-?[\d,]+)$", re.M)
_DATE = re.compile(r"^(\d{4})/(\d{1,2})/(\d{1,2})$", re.M)
_TIME = re.compile(r"^(\d{1,2}):(\d{2})(?::(\d{2}))?$", re.M)


def _rial(text: str) -> int:
    return int(text.replace(",", ""))


class SamanParser:
    name = "saman"

    def can_parse(self, text: str) -> bool:
        return text.startswith(_HEADER)

    def parse(self, text: str) -> ParsedSms:
        amount = _AMOUNT.search(text)
        account = _ACCOUNT.search(text)
        if not (amount and account):
            raise ValueError("قالب پیامک سامان ناشناخته است")
        balance = _BALANCE.search(text)
        return ParsedSms(
            bank="saman",
            account_mask=account.group(1),
            direction="out" if amount.group(1) == "برداشت" else "in",
            amount_rial=_rial(amount.group(2)),
            balance_after_rial=_rial(balance.group(1)) if balance else None,
            occurred_at=_occurred(text),
            description=amount.group(3).strip(),
        )


def _occurred(text: str) -> datetime | None:
    date = _DATE.search(text)
    if not date:
        return None
    clock = _TIME.search(text)
    hour, minute, second = (int(clock.group(1)), int(clock.group(2)),
                            int(clock.group(3) or 0)) if clock else (0, 0, 0)
    local = jdatetime.datetime(int(date.group(1)), int(date.group(2)), int(date.group(3)),
                               hour, minute, second).togregorian()
    return local.replace(tzinfo=TEHRAN).astimezone(UTC)
