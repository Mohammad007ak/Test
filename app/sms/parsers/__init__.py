"""رجیستری پارسرهای بانکی.

هر بانک یک فایل جدا در همین پوشه دارد و این‌جا ثبت می‌شود. پارسرها فقط از روی نمونه
پیامک واقعی (با شماره‌های پوشانده) نوشته می‌شوند؛ نمونه‌ها در tests/fixtures/sms/<bank>/.
تا رسیدن نمونه‌ها رجیستری خالی است و همه پیامک‌ها به صف بررسی می‌روند.
"""

from app.sms.parsers.base import BankParser, ParsedSms

PARSERS: list[BankParser] = []

__all__ = ["PARSERS", "BankParser", "ParsedSms"]
