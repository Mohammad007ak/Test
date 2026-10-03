"""آماده‌سازی متن پیامک: یکسان‌سازی، پوشاندن شماره‌ها و هش برای حذف تکراری.

متن خام هرگز ذخیره نمی‌شود؛ فقط خروجی mask_numbers.
"""

import hashlib
import re

from app.domain.normalize import normalize_chars, normalize_digits

MIN_MASKED_DIGITS = 10  # شماره کارت (۱۶)، حساب (۱۰ تا ۱۳) و شبا؛ مبلغ‌ها جداکننده دارند
_NUMBER_RUN = re.compile(r"\d(?:[\d]|[-. ](?=\d))*\d")


def prepare(raw: str) -> str:
    """ارقام فارسی/عربی به لاتین، «ي/ك» به «ی/ک»، خط‌شکن یکسان، بدون فاصله اضافه دو سر."""
    text = normalize_chars(normalize_digits(raw)).replace("\r\n", "\n").replace("\r", "\n")
    return "\n".join(line.strip() for line in text.strip().split("\n"))


def _mask(match: re.Match[str]) -> str:
    digits = re.sub(r"\D", "", match.group(0))
    if len(digits) < MIN_MASKED_DIGITS:
        return match.group(0)
    return "*" * (len(digits) - 4) + digits[-4:]


def mask_numbers(text: str) -> str:
    """هر رشته ارقام (با - . یا فاصله) با دست‌کم ۱۰ رقم → فقط ۴ رقم آخر دیده می‌شود."""
    return _NUMBER_RUN.sub(_mask, text)


def content_hash(text: str) -> str:
    return hashlib.sha256(" ".join(text.split()).encode("utf-8")).hexdigest()
