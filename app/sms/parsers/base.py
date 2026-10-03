"""قرارداد پارسرهای بانکی (SPEC: «قرارداد خروجی پارسر»)."""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class ParsedSms:
    bank: str  # کلید BANKS، مثل mellat
    account_mask: str  # ۴ رقم آخر (خالی اگر پیامک شماره ندارد، مثل بلو)
    direction: str  # in یا out
    amount_rial: int  # پیامک‌ها ریالی‌اند؛ تبدیل به تومان در خط پردازش
    balance_after_rial: int | None = None
    occurred_at: datetime | None = None  # اگر پیامک زمان دارد؛ وگرنه زمان دریافت
    description: str = ""
    confidence: float = 1.0
    account_prefix: str = ""  # ابتدای شماره حساب، اگر در متن پوشانده‌شده آمده


class BankParser(Protocol):
    name: str

    def can_parse(self, text: str) -> bool: ...

    def parse(self, text: str, received_at: datetime) -> ParsedSms:
        """received_at برای پیامک‌هایی که سال را در تاریخ نمی‌نویسند."""
        ...
