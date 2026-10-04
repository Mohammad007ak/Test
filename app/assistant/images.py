"""عکسی که کاربر برای وزیر می‌فرستد (مثلاً اسکرین‌شات پرتفوی بورس).

عکس فقط در حافظه همین درخواست است: نه در دیتابیس ذخیره می‌شود نه روی دیسک. مرورگر
پیش از ارسال آن را کوچک و دوباره JPEG می‌کند (اطلاعات EXIF مثل مکان حذف می‌شود).
استثنای آگاهانه قاعده «فقط متن پوشانده‌شده به LLM» با هشدار پیش از ارسال (تصمیم کاربر، SPEC).
"""

import base64

MAX_BYTES = 4 * 1024 * 1024
_SIGNATURES = {b"\xff\xd8\xff": "image/jpeg", b"\x89PNG\r\n\x1a\n": "image/png"}


class ImageError(ValueError):
    pass


def _kind(data: bytes) -> str | None:
    for magic, mime in _SIGNATURES.items():
        if data.startswith(magic):
            return mime
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def data_url(data: bytes) -> str:
    """بایت‌های عکس → data URL برای پیام مدل؛ نوع از امضای خود فایل، نه از نام یا هدر."""
    if not data:
        raise ImageError("عکس خالی است.")
    if len(data) > MAX_BYTES:
        raise ImageError("عکس خیلی بزرگ است (حداکثر ۴ مگابایت).")
    mime = _kind(data)
    if mime is None:
        raise ImageError("فقط عکس JPG، PNG یا WebP.")
    return f"data:{mime};base64,{base64.b64encode(data).decode()}"
