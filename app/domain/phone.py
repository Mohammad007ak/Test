"""شماره موبایل ایران: یکسان‌سازی به قالب ۰۹xxxxxxxxx (نام کاربری)."""

import re

from app.domain.normalize import normalize_digits

_MOBILE = re.compile(r"9\d{9}")


def normalize_phone(raw: str) -> str:
    digits = re.sub(r"[\s\-()]", "", normalize_digits(raw or ""))
    for prefix in ("+98", "0098", "98", "0"):
        if digits.startswith(prefix) and len(digits) - len(prefix) == 10:
            digits = digits[len(prefix):]
            break
    if not _MOBILE.fullmatch(digits):
        raise ValueError("شماره موبایل نامعتبر")
    return "0" + digits


def mask_phone(phone: str) -> str:
    return f"{phone[:4]}***{phone[-4:]}"
