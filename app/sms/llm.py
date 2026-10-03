"""بازگشت به LLM برای پیامکی که هیچ پارسری نشناخت (SPEC: LLMClient قابل تعویض).

فقط متن پوشانده‌شده فرستاده می‌شود. ارائه‌دهنده هنوز انتخاب نشده؛ پیش‌فرض خاموش است.
"""

from typing import Protocol

from app.sms.parsers.base import ParsedSms


class LLMClient(Protocol):
    name: str

    def parse_sms(self, masked_text: str) -> ParsedSms | None:
        """خروجی JSON سختگیرانه طبق ParsedSms؛ اگر مطمئن نیست None."""
        ...


class DisabledLLM:
    name = "disabled"

    def parse_sms(self, masked_text: str) -> ParsedSms | None:
        return None
