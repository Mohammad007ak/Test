"""پارسر پیامک بانک پارسیان (بدون اسم بانک؛ از روی ساختار).

نمونه تأییدشده (۶ مهر ۱۴۰۵)، پس از پوشاندن شماره:
    301*******5678
    مبلغ:2,000,000-
    مانده:4,417,721
    07/06
    18:01
علامت بعد از مبلغ می‌آید؛ «+» واریز (هنوز با نمونه واقعی تأیید نشده). سال در تاریخ نیست.
"""

import re
from datetime import datetime

from app.sms.parsers.base import ParsedSms
from app.sms.parsers.dates import month_day_to_utc

_PATTERN = re.compile(
    r"^(\d{0,4})\*+(\d{4})\n"
    r"مبلغ: ?([\d,]+)([+-])\n"
    r"مانده: ?(-?[\d,]+)\n"
    r"(\d{1,2})/(\d{1,2})\n"
    r"(\d{1,2}):(\d{2})$"
)


def _rial(text: str) -> int:
    return int(text.replace(",", ""))


class ParsianParser:
    name = "parsian"

    def can_parse(self, text: str) -> bool:
        return _PATTERN.match(text) is not None

    def parse(self, text: str, received_at: datetime) -> ParsedSms:
        m = _PATTERN.match(text)
        if m is None:
            raise ValueError("قالب پیامک پارسیان ناشناخته است")
        return ParsedSms(
            bank="parsian",
            account_prefix=m.group(1),
            account_mask=m.group(2),
            direction="out" if m.group(4) == "-" else "in",
            amount_rial=_rial(m.group(3)),
            balance_after_rial=_rial(m.group(5)),
            occurred_at=month_day_to_utc(int(m.group(6)), int(m.group(7)), int(m.group(8)),
                                         int(m.group(9)), received_at),
        )
