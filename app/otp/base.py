"""رابط فرستنده کد."""

from typing import Protocol


class OtpError(Exception):
    """پیام قابل نمایش به کاربر (محدودیت ارسال، خطای سرویس پیامک)."""


class OtpSender(Protocol):
    name: str

    def send(self, phone: str, code: str) -> None:
        """کد را به شماره بفرستد یا OtpError بدهد."""
        ...
