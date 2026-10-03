"""حلقه گفتگوی وزیر: پرسش ← (صدا زدن ابزارها) ← پاسخ فارسی."""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from app.assistant.client import AssistantError, ChatModel
from app.assistant.prompt import system_prompt
from app.assistant.tools import TOOLS

MAX_ROUNDS = 5

__all__ = ["Answer", "AssistantError", "ask"]


@dataclass
class Answer:
    text: str
    tools_used: list[str] = field(default_factory=list)


def ask(model: ChatModel, run_tool: Callable[[str, str], str], question: str,
        history: list[dict[str, Any]]) -> Answer:
    messages: list[dict[str, Any]] = [{"role": "system", "content": system_prompt()},
                                      *history, {"role": "user", "content": question}]
    used: list[str] = []
    for _ in range(MAX_ROUNDS):
        reply = model.complete(messages, TOOLS)
        calls = reply.get("tool_calls") or []
        if not calls:
            text = (reply.get("content") or "").strip()
            if not text:
                raise AssistantError("جوابی نگرفتم؛ سؤال را کمی واضح‌تر بپرس.")
            return Answer(text, used)
        messages.append({"role": "assistant", "content": reply.get("content"),
                         "tool_calls": calls})
        for call in calls:
            function = call.get("function", {})
            name = str(function.get("name", ""))
            used.append(name)
            messages.append({"role": "tool", "tool_call_id": call.get("id", ""),
                             "content": run_tool(name, function.get("arguments") or "{}")})
    raise AssistantError("این سؤال بیش از حد پیچیده شد؛ آن را ساده‌تر یا تکه‌تکه بپرس.")
