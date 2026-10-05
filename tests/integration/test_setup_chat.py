"""راه‌اندازی با گفتگوی وزیر: کاربر تازه به‌جای فرم با خود هوش مصنوعی حرف می‌زند."""

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.config import Settings
from app.db import user_session
from app.main import create_app
from app.models import Account
from tests.integration.conftest import FakeSender, register

IPHONE = "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15"


def call(name: str, args: dict[str, Any], cid: str) -> dict[str, Any]:
    return {"id": cid, "type": "function",
            "function": {"name": name, "arguments": json.dumps(args, ensure_ascii=False)}}


def last_turn(model: "Script", index: int = -1) -> tuple[str, set[str]]:
    messages, tools = model.seen[index]
    return messages[0]["content"], {t["function"]["name"] for t in tools}


class Script:
    """هر سؤال: یک دور صدا زدن ابزارهای تعیین‌شده، بعد جواب متنی."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.answer = "عالی!"
        self.seen: list[tuple[list[dict[str, Any]], list[dict[str, Any]]]] = []

    def complete(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> dict:
        self.seen.append((list(messages), tools))
        if messages[-1]["role"] != "tool" and self.calls:
            calls, self.calls = self.calls, []
            return {"role": "assistant", "content": None, "tool_calls": calls}
        return {"role": "assistant", "content": self.answer}


@pytest.fixture
def model() -> Script:
    return Script()


@pytest.fixture
def client(tmp_path: Path, model: Script) -> Iterator[TestClient]:
    settings = Settings(database_url=f"sqlite:///{tmp_path / 't.db'}", secret_key="t")
    app = create_app(settings, price_sources=[], schedule=False, otp_sender=FakeSender(),
                     chat_model=model)
    with TestClient(app) as c:
        register(c)
        yield c


PERSONA = {"age": "25_34", "job": "employee", "income": "fixed", "household": "single",
           "housing": "renter", "goal": "home", "horizon": "3_7", "drop": "wait",
           "choice": "coin", "experience": "safe", "style": "balanced", "emergency": "lt3",
           "tone": "simple", "interests": ["gold"]}


def to_money_chat(client: TestClient) -> None:
    """آشنایی (کارت) ← پیامک ← گفتگوی مالی با وزیر."""
    client.post("/persona", data=PERSONA)
    client.get("/start/sms")
    assert client.get("/start/money", follow_redirects=False).headers["location"] == "/assistant"
    client.post("/assistant/consent")


def test_order_is_get_to_know_then_card_then_sms_then_money(client: TestClient) -> None:
    assert client.get("/start", follow_redirects=False).headers["location"] == "/persona"
    client.post("/persona", data=PERSONA)
    card = client.get("/persona?new=1").text
    assert 'href="/start/sms"' in card  # بعد از کارت، ادامه راه‌اندازی
    assert client.get("/start", follow_redirects=False).headers["location"] == "/start/sms"
    page = client.get("/start/sms").text
    assert 'href="/start/money"' in page
    assert client.get("/start", follow_redirects=False).headers["location"] == "/start/money"
    assert client.get("/start/money", follow_redirects=False).headers["location"] == "/assistant"
    page = client.get("/assistant").text
    assert "/assistant/consent" in page and 'href="/start/have"' in page  # بدون رضایت: فرم
    client.post("/assistant/consent")
    page = client.get("/assistant").text
    assert "حالا که" in page and 'data-ask="طلا و سکه"' in page
    assert 'href="/start/skip"' in page


def test_setup_turn_uses_setup_prompt_records_and_suggests(client: TestClient,
                                                           model: Script) -> None:
    to_money_chat(client)
    model.calls = [
        call("add_account", {"bank": "saman", "balance_toman": 45_000_000}, "a"),
        call("suggest_replies", {"options": ["دلار هم دارم", "همین بود"]}, "b"),
    ]
    html = client.post("/assistant", data={"question": "یه حساب سامان دارم ۴۵ میلیون"}).text
    system, tools = last_turn(model, 0)
    assert "حالت راه‌اندازی" in system and {"show_setup_card", "suggest_replies"} <= tools
    assert "پرسونای این کاربر" in system  # وزیر او را از مصاحبه می‌شناسد
    assert "data-action=" in html and 'data-ask="دلار هم دارم"' in html
    action_id = html.split('data-action="')[1].split('"')[0]
    client.post(f"/assistant/actions/{action_id}/confirm")
    with user_session(client.app.state.session_factory(), 1) as s:  # type: ignore[attr-defined]
        account = s.scalars(select(Account)).one()
        assert account.bank == "saman" and account.balance_toman == 45_000_000
    model.calls = []
    client.post("/assistant", data={"question": "همین بود"})
    assert "حساب بانکی سامان" in model.seen[-1][0][0]["content"]  # آنچه تا حالا ثبت شده


def test_done_card_finishes_setup(client: TestClient, model: Script) -> None:
    to_money_chat(client)
    model.calls = [call("show_setup_card", {"card": "sms"}, "a")]
    html = client.post("/assistant", data={"question": "خب"}, headers={"User-Agent": IPHONE}).text
    assert 'href="/sms"' in html  # اگر پیامک را رد کرده بود، دوباره یادآوری
    model.calls = [call("show_setup_card", {"card": "done"}, "b")]
    html = client.post("/assistant", data={"question": "همین‌ها بود"}).text
    assert 'href="/"' in html
    model.calls = []
    client.post("/assistant", data={"question": "قیمت دلار؟"})
    system, tools = last_turn(model)
    assert "حالت راه‌اندازی" not in system and "show_setup_card" not in tools  # تمام شد
    assert 'href="/start"' not in client.get("/").text


def test_regular_chat_has_no_setup_tools(client: TestClient, model: Script) -> None:
    client.get("/start/skip")
    client.post("/assistant/consent")
    client.post("/assistant", data={"question": "سلام"})
    assert "show_setup_card" not in {t["function"]["name"] for t in model.seen[-1][1]}
