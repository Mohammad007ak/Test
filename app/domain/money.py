"""مبنای مبالغ و قالب‌بندی فارسی اعداد.

همه مبالغ به‌صورت int تومانی ذخیره و محاسبه می‌شوند. ریال فقط در مرز ورودی
(پیامک بانکی، منابع قیمت ریالی) با rial_to_toman تبدیل می‌شود.
"""

from decimal import ROUND_HALF_UP, Decimal

RIAL_PER_TOMAN = 10

_TO_PERSIAN = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def round_toman(value: Decimal) -> int:
    return int(value.quantize(Decimal(1), rounding=ROUND_HALF_UP))


def rial_to_toman(rial: int) -> int:
    """تبدیل مبلغ ریالی ورودی به تومان صحیح (گرد به نزدیک‌ترین تومان)."""
    return round_toman(Decimal(rial) / RIAL_PER_TOMAN)


def to_persian_digits(text: str) -> str:
    return text.translate(_TO_PERSIAN)


def format_number(value: Decimal | int, places: int = 0) -> str:
    """۱۲۳۴۵۶۷٫۸ → «۱٬۲۳۴٬۵۶۷٫۸»."""
    quantum = Decimal(1).scaleb(-places)
    rounded = Decimal(value).quantize(quantum, rounding=ROUND_HALF_UP)
    text = f"{rounded:,.{places}f}".replace(",", "٬").replace(".", "٫")
    return to_persian_digits(text)


def format_toman(toman: int) -> str:
    return f"{format_number(toman)} تومان"


_SCALES = ((Decimal(10) ** 12, "هزار میلیارد"), (Decimal(10) ** 9, "میلیارد"),
           (Decimal(10) ** 6, "میلیون"))


def format_toman_short(toman: int) -> str:
    """۸۱٬۲۰۰٬۰۰۰ تومان → «۸۱٫۲ میلیون تومان»."""
    for scale, name in _SCALES:
        if abs(toman) >= scale:
            text = format_number(Decimal(toman) / scale, 1).removesuffix("٫۰")
            return f"{text} {name} تومان"
    return format_toman(toman)


def format_percent(rate: Decimal, places: int = 1) -> str:
    """Decimal('0.1956') → «۱۹٫۶٪»."""
    return f"{format_number(rate * 100, places)}٪"
