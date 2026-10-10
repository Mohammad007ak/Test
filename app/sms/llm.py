"""خواندن پیامکی که هیچ پارسر و قالبی نشناخت، با مدل زبانی (SPEC: LLMClient قابل تعویض).

فقط متن پوشانده‌شده فرستاده می‌شود. مدل علاوه بر مبلغ و جهت، قالب پیامک را برمی‌گرداند
تا این قالب یک بار یاد گرفته شود (app.sms.templates). بدون تنظیم مدل زبانی، خاموش است.
"""

import json
import logging
from typing import Any, Protocol

from app.sms.templates import SmsReading
from app.web.strings import BANKS

log = logging.getLogger("finassist.sms")


class LLMClient(Protocol):
    name: str

    def read_sms(self, masked_text: str) -> SmsReading | None:
        """خواندهٔ پیامک و قالبش؛ اگر تراکنش بانکی نیست یا مطمئن نیست None."""
        ...


class DisabledLLM:
    name = "disabled"

    def read_sms(self, masked_text: str) -> SmsReading | None:
        return None


class ChatModel(Protocol):
    def complete(self, messages: list[dict[str, Any]],
                 tools: list[dict[str, Any]]) -> dict[str, Any]: ...


PROMPT = """You read Iranian bank SMS messages. Card and account numbers are already masked.
Call report_bank_sms exactly once.

If the message is not a single money transaction (an ad, a login code, a loan notice
without a transfer), set is_bank_transaction to false.

Otherwise report:
- bank: one of {banks}
- direction: "out" for money leaving the account (برداشت، خرید، انتقال از، پرید), "in" for money
  arriving (واریز، انتقال به، نشست، سود)
- amount and balance as integers exactly as written in the text (no unit conversion), balance null
  if absent; unit: "rial" or "toman", as written (no unit written means rial)
- label: the short fixed transaction title from the text, e.g. "برداشت پول"
- template: the message text copied EXACTLY character by character, with these variable parts
  replaced: {{amount}}, {{balance}}, {{date}}, {{time}}, {{account}} (masked card/account number),
  and {{any}} for any other changing text such as a person's or merchant's name. The template
  must contain no digits at all; every number must be replaced by a placeholder.

Example: "30,000,000 ریال از حساب شما پرید.\\nموجودی: 86,552,338 ریال\\n16:12\\n1405.07.09"
→ template "{{amount}} ریال از حساب شما پرید.\\nموجودی: {{balance}} ریال\\n{{time}}\\n{{date}}"
"""

TOOL: dict[str, Any] = {"type": "function", "function": {
    "name": "report_bank_sms",
    "description": "Report the reading and the reusable template of one bank SMS.",
    "parameters": {"type": "object", "properties": {
        "is_bank_transaction": {"type": "boolean"},
        "bank": {"type": "string", "enum": list(BANKS)},
        "direction": {"type": "string", "enum": ["in", "out"]},
        "amount": {"type": "integer"},
        "balance": {"type": ["integer", "null"]},
        "unit": {"type": "string", "enum": ["rial", "toman"]},
        "label": {"type": "string"},
        "template": {"type": "string"},
    }, "required": ["is_bank_transaction"]},
}}


class ChatSmsReader:
    name = "chat"

    def __init__(self, chat: ChatModel) -> None:
        self.chat = chat

    def read_sms(self, masked_text: str) -> SmsReading | None:
        messages = [{"role": "system", "content": PROMPT.format(banks=", ".join(BANKS))},
                    {"role": "user", "content": masked_text}]
        try:
            message = self.chat.complete(messages, [TOOL])
            call = message["tool_calls"][0]["function"]
            return _reading(json.loads(call["arguments"]))
        except Exception as exc:  # مدل خراب یا قطع: پیامک به صف بررسی می‌رود
            log.warning("خواندن پیامک با مدل زبانی نشد: %s", type(exc).__name__)
            return None


def _reading(answer: dict[str, Any]) -> SmsReading | None:
    if answer.get("is_bank_transaction") is not True:
        return None
    balance = answer.get("balance")
    if not isinstance(answer["amount"], int) or not (balance is None or isinstance(balance, int)):
        return None
    return SmsReading(bank=str(answer["bank"]), direction=str(answer["direction"]),
                      amount=answer["amount"], balance=balance, unit=str(answer["unit"]),
                      template=str(answer["template"]), label=str(answer.get("label") or ""))
