"""آماده‌سازی متن پیامک: یکسان‌سازی، پوشاندن شماره‌ها و هش برای حذف تکراری.

متن خام هرگز ذخیره نمی‌شود؛ فقط خروجی mask_numbers.
"""

import hashlib
import re

from app.domain.normalize import normalize_chars, normalize_digits

# نویسه‌های نامرئی جهت متن (LRM، RLM، LRE...PDF، isolateها) که بانک‌ها دور شماره‌ها می‌گذارند؛
# نیم‌فاصله (U+200C) جزو متن فارسی است و می‌ماند
_BIDI_CONTROLS = dict.fromkeys(map(ord, "\u200e\u200f\u202a\u202b\u202c\u202d\u202e"
                                       "\u2066\u2067\u2068\u2069\ufeff"))
MIN_MASKED_DIGITS = 10  # شماره کارت (۱۶)، حساب (۱۰ تا ۱۳) و شبا؛ مبلغ‌ها جداکننده دارند
_NUMBER_RUN = re.compile(r"\d(?:[\d]|[-. ](?=\d))*\d")


def prepare(raw: str) -> str:
    """ارقام فارسی/عربی به لاتین، «ي/ك» به «ی/ک»، خط‌شکن یکسان، بدون فاصله اضافه دو سر."""
    text = normalize_chars(normalize_digits(raw)).translate(_BIDI_CONTROLS)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return "\n".join(line.strip() for line in text.strip().split("\n"))


CARD_DIGITS = 16  # کارت و شبا: فقط ۴ رقم آخر
PREFIX_MAX = 4


def account_prefix(raw: str) -> str:
    """ابتدای شماره حساب: گروه اول اگر جداکننده دارد (۴ رقم یا کمتر)، وگرنه ۳ رقم اول."""
    first = re.split(r"[-. ]", raw, maxsplit=1)[0]
    return first if len(first) <= PREFIX_MAX and first != raw else re.sub(r"\D", "", raw)[:3]


def _mask(match: re.Match[str]) -> str:
    raw = match.group(0)
    digits = re.sub(r"\D", "", raw)
    if len(digits) < MIN_MASKED_DIGITS:
        return raw
    prefix = "" if len(digits) >= CARD_DIGITS else account_prefix(raw)
    return prefix + "*" * (len(digits) - len(prefix) - 4) + digits[-4:]


def mask_numbers(text: str) -> str:
    """کارت و شبا → فقط ۴ رقم آخر؛ حساب (۱۰ تا ۱۵ رقم) → ابتدای شماره + ۴ رقم آخر.

    ابتدای شماره (کد شعبه یا نوع حساب) دو حساب یک نفر را که ۴ رقم آخرشان یکی است از هم
    جدا می‌کند (تصمیم کاربر، ۱۱ مهر ۱۴۰۵؛ استثنای قاعده «فقط ۴ رقم آخر» در SPEC).
    """
    return _NUMBER_RUN.sub(_mask, text)


# پیامک رمز و کد (رمز پویا، کد تأیید) حتی از طرف بانک هرگز ذخیره یا پردازش نمی‌شود؛
# همان فهرست اپ اندروید (SmsText.SECRETS)، برای Shortcuts آیفون و فایل که فیلتر گوشی ندارند
SECRETS = ("رمز", "پویا", "کد تایید", "کد تأیید", "کد ورود", "کد امنیتی", "کد یکبار", "کد یک‌بار",
           "کد فعال", "otp", "password", "verification", "cvv")


def is_secret(raw: str) -> bool:
    text = normalize_chars(raw).casefold()
    return any(word in text for word in SECRETS)


def content_hash(text: str) -> str:
    return hashlib.sha256(" ".join(text.split()).encode("utf-8")).hexdigest()
