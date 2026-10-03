"""رجیستری پارسرهای بانکی.

هر بانک یک فایل جدا در همین پوشه دارد و این‌جا ثبت می‌شود. پارسرها فقط از روی نمونه
پیامک واقعی (با شماره‌های پوشانده) نوشته می‌شوند؛ نمونه‌ها در tests/fixtures/sms/<bank>/.
پیامک بانکی که پارسر ندارد به صف بررسی می‌رود.
"""

from app.sms.parsers.base import BankParser, ParsedSms
from app.sms.parsers.blu import BluParser
from app.sms.parsers.saman import SamanParser

PARSERS: list[BankParser] = [SamanParser(), BluParser()]

__all__ = ["PARSERS", "BankParser", "ParsedSms"]
