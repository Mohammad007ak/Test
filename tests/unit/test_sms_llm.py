"""خواندن پیامک ناشناخته با مدل زبانی (فقط متن پوشانده‌شده)."""

import json
from typing import Any

from app.sms.llm import ChatSmsReader
from app.sms.templates import SmsReading


class FakeChat:
    def __init__(self, arguments: object = None, fail: bool = False) -> None:
        self.arguments = arguments
        self.fail = fail
        self.messages: list[dict[str, Any]] = []
        self.tools: list[dict[str, Any]] = []

    def complete(self, messages: list[dict[str, Any]],
                 tools: list[dict[str, Any]]) -> dict[str, Any]:
        if self.fail:
            raise RuntimeError("down")
        self.messages, self.tools = messages, tools
        if self.arguments is None:
            return {"role": "assistant", "content": "نمی‌دانم"}
        return {"role": "assistant", "tool_calls": [{"function": {
            "name": "report_bank_sms", "arguments": json.dumps(self.arguments)}}]}


ANSWER = {"is_bank_transaction": True, "bank": "blu", "direction": "out",
          "amount": 30_000_000, "balance": 86_552_338, "unit": "rial",
          "template": "{amount} ریال پرید. موجودی: {balance}", "label": "برداشت پول"}


def test_reader_returns_reading_from_tool_call() -> None:
    chat = FakeChat(ANSWER)
    reading = ChatSmsReader(chat).read_sms("30,000,000 ریال پرید. موجودی: 86,552,338")
    assert reading == SmsReading("blu", "out", 30_000_000, 86_552_338, "rial",
                                 ANSWER["template"], "برداشت پول")
    assert "30,000,000 ریال پرید" in chat.messages[-1]["content"]
    assert chat.tools[0]["function"]["name"] == "report_bank_sms"


def test_not_a_transaction_or_bad_answer_is_none() -> None:
    assert ChatSmsReader(FakeChat({**ANSWER, "is_bank_transaction": False})).read_sms("x") is None
    assert ChatSmsReader(FakeChat(None)).read_sms("x") is None
    assert ChatSmsReader(FakeChat({"bank": "blu"})).read_sms("x") is None
    assert ChatSmsReader(FakeChat({**ANSWER, "amount": "سی"})).read_sms("x") is None


def test_service_failure_is_none() -> None:
    assert ChatSmsReader(FakeChat(fail=True)).read_sms("x") is None
