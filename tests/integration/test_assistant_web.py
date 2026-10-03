import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from tests.integration.conftest import FakeSender, register


class Model:
    """هر سؤال: یک بار ابزار overview، بعد جواب با عددی که ابزار داد."""

    def __init__(self) -> None:
        self.seen: list[list[dict]] = []

    def complete(self, messages: list[dict], tools: list[dict]) -> dict:
        self.seen.append(messages)
        if messages[-1]["role"] == "tool":
            networth = json.loads(messages[-1]["content"])["networth_toman"]
            return {"role": "assistant", "content": f"ثروت خالصت {networth} تومان است."}
        return {"role": "assistant", "content": None, "tool_calls": [
            {"id": "c1", "type": "function", "function": {"name": "overview", "arguments": "{}"}}]}


def make(tmp_path: Path, model: Model | None, **kw: object):  # type: ignore[no-untyped-def]
    settings = Settings(database_url=f"sqlite:///{tmp_path / 't.db'}", secret_key="t",
                        **kw)  # type: ignore[arg-type]
    return create_app(settings, price_sources=[], schedule=False, otp_sender=FakeSender(),
                      chat_model=model)


@pytest.fixture
def model() -> Model:
    return Model()


@pytest.fixture
def client(tmp_path: Path, model: Model) -> Iterator[TestClient]:
    with TestClient(make(tmp_path, model, llm_daily_limit=3)) as c:
        register(c)
        c.post("/accounts", data={"bank": "saman", "account_mask": "1234",
                                  "balance_toman": "7,000,000"})
        yield c


def test_needs_consent_first(client: TestClient) -> None:
    page = client.get("/assistant").text
    assert 'action="/assistant/consent"' in page
    assert client.post("/assistant", data={"question": "ثروتم؟"}).status_code == 403
    client.post("/assistant/consent")
    assert 'name="question"' in client.get("/assistant").text


def test_answer_uses_real_numbers_and_history_persists(client: TestClient, model: Model) -> None:
    client.post("/assistant/consent")
    reply = client.post("/assistant", data={"question": "ثروت خالصم چقدره؟"})
    assert reply.status_code == 200 and "۷۰۰۰۰۰۰" in reply.text  # ارقام فارسی
    assert "ثروت خالصم چقدره؟" in client.get("/assistant").text  # تاریخچه ماند
    client.post("/assistant", data={"question": "و دارایی‌هام؟"})
    roles = [m["role"] for m in model.seen[-2]]
    assert roles[:4] == ["system", "user", "assistant", "user"]  # سؤال قبلی در تاریخچه
    client.post("/assistant/clear")
    assert "ثروت خالصم چقدره؟" not in client.get("/assistant").text


def test_daily_limit(client: TestClient) -> None:
    client.post("/assistant/consent")
    for _ in range(3):
        assert client.post("/assistant", data={"question": "؟"}).status_code == 200
    limited = client.post("/assistant", data={"question": "؟"})
    assert limited.status_code == 429 and "۳" in limited.text


def test_empty_and_long_questions_rejected(client: TestClient) -> None:
    client.post("/assistant/consent")
    assert client.post("/assistant", data={"question": "  "}).status_code == 400
    assert client.post("/assistant", data={"question": "x" * 1001}).status_code == 400


def test_not_configured_message(tmp_path: Path) -> None:
    with TestClient(make(tmp_path, None)) as c:
        register(c)
        page = c.get("/assistant").text
        assert "فعال نشده" in page and 'name="question"' not in page


def test_entry_point_on_home(client: TestClient) -> None:
    assert 'href="/assistant"' in client.get("/").text
