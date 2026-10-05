"""جایزه اینستاگرام مهر ۱۴۰۵: فالو + شیر پست برای یک دوست ← ۳ ماه وزیر ویژه رایگان.

فقط آیدی اینستاگرام ثبت می‌شود تا صاحب پیج فالو را دستی بررسی کند؛ شیر در دایرکت قابل دیدن
نیست و به صداقت کاربر سپرده شده.
"""

import re
from datetime import date

from app.domain.normalize import normalize_digits

END = date(2026, 10, 17)  # ۲۵ مهر ۱۴۰۵، خودِ روز هم حساب است (تهران)
_URL = re.compile(r"^(?:https?://)?(?:www\.)?instagram\.com/", re.IGNORECASE)
_HANDLE = re.compile(r"^(?!\.)(?!.*\.\.)(?!.*\.$)[a-z0-9._]{1,30}$")


def parse_handle(raw: str) -> str | None:
    """آیدی تمیز (کوچک، بدون @ و لینک)، یا None اگر آیدی معتبر اینستاگرام نیست."""
    text = _URL.sub("", normalize_digits(raw).strip())
    text = text.split("?")[0].strip("/").removeprefix("@").lower()
    return text if _HANDLE.match(text) else None


def is_open(today: date) -> bool:
    return today <= END
