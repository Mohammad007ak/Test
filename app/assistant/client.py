"""اتصال به مدل زبانی با API سازگار با OpenAI (chat/completions + function calling).

ارائه‌دهنده با سه متغیر محیطی عوض می‌شود: FINASSIST_LLM_URL، FINASSIST_LLM_KEY و
FINASSIST_LLM_MODEL. کتابخانه اضافه لازم نیست؛ درخواست با کتابخانه استاندارد فرستاده می‌شود.
"""

import json
import logging
import ssl
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Any, Protocol

log = logging.getLogger("finassist.assistant")
TIMEOUT_SECONDS = 60

Post = Callable[[str, bytes, dict[str, str]], tuple[int, str]]


class AssistantError(Exception):
    """پیام قابل نمایش به کاربر."""


class ChatModel(Protocol):
    def complete(self, messages: list[dict[str, Any]],
                 tools: list[dict[str, Any]]) -> dict[str, Any]:
        """پیام دستیار (role=assistant، content و شاید tool_calls) را برمی‌گرداند."""
        ...


def _http_post(url: str, body: bytes, headers: dict[str, str]) -> tuple[int, str]:
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS,
                                    context=ssl.create_default_context()) as response:
            return response.status, response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", errors="replace")
    except OSError as exc:
        raise AssistantError("به سرویس هوش مصنوعی وصل نشدم؛ کمی بعد دوباره بپرس.") from exc


class OpenAICompatClient:
    def __init__(self, base_url: str, api_key: str, model: str, post: Post = _http_post) -> None:
        self.url = base_url.rstrip("/") + "/chat/completions"
        self.api_key = api_key
        self.model = model
        self.post = post

    def complete(self, messages: list[dict[str, Any]],
                 tools: list[dict[str, Any]]) -> dict[str, Any]:
        body = json.dumps({"model": self.model, "messages": messages, "tools": tools,
                           "tool_choice": "auto"}, ensure_ascii=False).encode()
        status, text = self.post(self.url, body, {
            "Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"})
        try:
            data = json.loads(text)
            message = data["choices"][0]["message"]
        except (ValueError, KeyError, IndexError, TypeError):
            data, message = {}, None
        if status != 200 or not isinstance(message, dict):
            log.warning("مدل زبانی خطا داد: %s %s", status, str(data.get("error", text))[:300])
            raise AssistantError("سرویس هوش مصنوعی الان جواب نداد؛ کمی بعد دوباره بپرس.")
        return message
