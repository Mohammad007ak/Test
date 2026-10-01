"""یکسان‌سازی متن و عدد ورودی (ارقام فارسی/عربی، «ي» و «ك»، جداکننده هزارگان)."""

from decimal import Decimal, InvalidOperation

_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
_CHARS = str.maketrans({"ي": "ی", "ك": "ک", "ى": "ی"})
_THOUSANDS_SEPARATORS = (",", "٬", "،", " ", "‌", "_", "'")
_DECIMAL_POINTS = ("٫", "/")


def normalize_digits(text: str) -> str:
    return text.translate(_DIGITS)


def normalize_chars(text: str) -> str:
    return text.translate(_CHARS)


def normalize_text(text: str) -> str:
    return normalize_chars(normalize_digits(text)).strip()


def _strip_separators(text: str) -> str:
    text = normalize_digits(text).strip()
    for sep in _THOUSANDS_SEPARATORS:
        text = text.replace(sep, "")
    return text


def parse_int(text: str) -> int:
    """«۱۲٬۵۰۰٬۰۰۰» → 12500000. خطا برای ورودی غیرعددی یا اعشاری."""
    cleaned = _strip_separators(text)
    if not cleaned or not cleaned.lstrip("-").isdigit():
        raise ValueError(f"عدد صحیح نامعتبر: {text!r}")
    return int(cleaned)


def parse_decimal(text: str) -> Decimal:
    """«۲٫۵» یا «2.5» → Decimal('2.5')."""
    cleaned = _strip_separators(text)
    for point in _DECIMAL_POINTS:
        cleaned = cleaned.replace(point, ".")
    try:
        value = Decimal(cleaned)
    except InvalidOperation as exc:
        raise ValueError(f"عدد نامعتبر: {text!r}") from exc
    if not value.is_finite():
        raise ValueError(f"عدد نامعتبر: {text!r}")
    return value
