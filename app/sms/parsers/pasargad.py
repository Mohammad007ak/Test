"""پارسر پیامک بانک پاسارگاد (بدون اسم بانک؛ از روی ساختار).

نمونه تأییدشده (۶ مهر ۱۴۰۵)، پس از پوشاندن شماره:
    777********4541
    -911,000
    07/06_11:45
    مانده: 181,715,262
مبالغ ریالی؛ «+» واریز (هنوز با نمونه واقعی تأیید نشده). تاریخ ماه/روز بدون سال است.
"""

import re
from datetime import datetime

from app.sms.parsers.base import ParsedSms
from app.sms.parsers.dates import month_day_to_utc

_PATTERN = re.compile(
    r"^(\d{0,4})\*+(\d{4})\n"
    r"([+-])([\d,]+)\n"
    r"(\d{1,2})/(\d{1,2})_(\d{1,2}):(\d{2})\n"
    r"مانده: ?(-?[\d,]+)$"
)


def _rial(text: str) -> int:
    return int(text.replace(",", ""))


class PasargadParser:
    name = "pasargad"

    def can_parse(self, text: str) -> bool:
        return _PATTERN.match(text) is not None

    def parse(self, text: str, received_at: datetime) -> ParsedSms:
        m = _PATTERN.match(text)
        if m is None:
            raise ValueError("قالب پیامک پاسارگاد ناشناخته است")
        return ParsedSms(
            bank="pasargad",
            account_prefix=m.group(1),
            account_mask=m.group(2),
            direction="out" if m.group(3) == "-" else "in",
            amount_rial=_rial(m.group(4)),
            balance_after_rial=_rial(m.group(9)),
            occurred_at=month_day_to_utc(int(m.group(5)), int(m.group(6)), int(m.group(7)),
                                         int(m.group(8)), received_at),
        )
