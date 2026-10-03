import json

import pytest

from app.assistant.agent import AssistantError, ask
from app.assistant.client import OpenAICompatClient


class ScriptedModel:
    """مدل ساختگی: پاسخ‌های از پیش تعیین‌شده را به ترتیب برمی‌گرداند و درخواست‌ها را نگه می‌دارد."""

    def __init__(self, *replies: dict) -> None:
        self.replies = list(replies)
        self.calls: list[list[dict]] = []

    def complete(self, messages: list[dict], tools: list[dict]) -> dict:
        self.calls.append([dict(m) for m in messages])
        return self.replies.pop(0)


def tool_call(name: str, args: dict, call_id: str = "c1") -> dict:
    return {"role": "assistant", "content": None, "tool_calls": [
        {"id": call_id, "type": "function",
         "function": {"name": name, "arguments": json.dumps(args)}}]}


def fake_runner(log: list):  # type: ignore[no-untyped-def]
    def run(name: str, arguments: str) -> str:
        log.append((name, json.loads(arguments)))
        return json.dumps({"networth_toman": 30_000_000})
    return run


def test_tool_result_flows_back_and_answer_returned() -> None:
    model = ScriptedModel(tool_call("overview", {}),
                          {"role": "assistant", "content": "ثروت خالصت ۳۰ میلیون تومان است."})
    log: list = []
    answer = ask(model, fake_runner(log), "ثروت خالصم چقدره؟", history=[])
    assert answer.text == "ثروت خالصت ۳۰ میلیون تومان است."
    assert answer.tools_used == ["overview"] and log == [("overview", {})]
    second = model.calls[1]
    assert second[0]["role"] == "system" and "وزیر" in second[0]["content"]
    assert second[-1] == {"role": "tool", "tool_call_id": "c1",
                          "content": json.dumps({"networth_toman": 30_000_000})}


def test_history_is_sent_before_question() -> None:
    model = ScriptedModel({"role": "assistant", "content": "باشه"})
    ask(model, fake_runner([]), "و ماه قبل؟",
        history=[{"role": "user", "content": "خرج این ماه؟"},
                 {"role": "assistant", "content": "۵ میلیون"}])
    roles = [m["role"] for m in model.calls[0]]
    assert roles == ["system", "user", "assistant", "user"]


def test_endless_tool_calls_are_cut_off() -> None:
    model = ScriptedModel(*[tool_call("overview", {}, f"c{i}") for i in range(10)])
    with pytest.raises(AssistantError):
        ask(model, fake_runner([]), "؟", history=[])


def test_openai_compatible_request_and_response_shape() -> None:
    sent = {}

    def post(url: str, body: bytes, headers: dict) -> tuple[int, str]:
        sent.update(url=url, body=json.loads(body), headers=headers)
        return 200, json.dumps({"choices": [{"message": {"role": "assistant", "content": "سلام"}}]})

    client = OpenAICompatClient("https://api.example.ir/v1/", "KEY", "gpt-luna", post=post)
    reply = client.complete([{"role": "user", "content": "سلام"}], [{"type": "function"}])
    assert reply["content"] == "سلام"
    assert sent["url"] == "https://api.example.ir/v1/chat/completions"
    assert sent["headers"]["Authorization"] == "Bearer KEY"
    assert sent["body"]["model"] == "gpt-luna" and sent["body"]["tool_choice"] == "auto"


def test_provider_error_becomes_friendly_error() -> None:
    def post(url: str, body: bytes, headers: dict) -> tuple[int, str]:
        return 429, json.dumps({"error": {"message": "quota"}})

    with pytest.raises(AssistantError):
        OpenAICompatClient("https://x/v1", "K", "m", post=post).complete([], [])
