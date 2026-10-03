"""وزیر ثبت را پیشنهاد می‌دهد؛ ذخیره فقط با تأیید کاربر و با همان اعتبارسنجی فرم‌ها."""

import json
import re
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.assistant.tools import TOOLS, run_tool
from app.config import Settings
from app.db import user_session
from app.main import create_app
from app.models import Asset, IncomeStream, Liability, Transaction
from tests.integration.conftest import FakeSender, register


class Model:
    """اولین درخواست هر سؤال: ابزاری که تست تعیین کرده؛ بعد جواب کوتاه."""

    def __init__(self) -> None:
        self.next_call: tuple[str, dict] | None = None

    def complete(self, messages: list[dict], tools: list[dict]) -> dict:
        if messages[-1]["role"] == "tool" or self.next_call is None:
            return {"role": "assistant", "content": "برای ثبت، تأیید کن."}
        name, args = self.next_call
        self.next_call = None
        return {"role": "assistant", "content": None, "tool_calls": [
            {"id": "c1", "type": "function",
             "function": {"name": name, "arguments": json.dumps(args, ensure_ascii=False)}}]}


@pytest.fixture
def model() -> Model:
    return Model()


@pytest.fixture
def app(tmp_path: Path, model: Model):  # type: ignore[no-untyped-def]
    settings = Settings(database_url=f"sqlite:///{tmp_path / 't.db'}", secret_key="t")
    return create_app(settings, price_sources=[], schedule=False, otp_sender=FakeSender(),
                      chat_model=model)


@pytest.fixture
def client(app) -> Iterator[TestClient]:  # type: ignore[no-untyped-def]
    with TestClient(app) as c:
        register(c)
        c.post("/assistant/consent")
        yield c


def db(app):  # type: ignore[no-untyped-def]
    return user_session(app.state.session_factory(), 1)


def say(client: TestClient, model: Model, tool: str, **args: object) -> str:
    model.next_call = (tool, args)
    return client.post("/assistant", data={"question": "ثبت کن"}).text


def action_id(html: str) -> str:
    return re.search(r'data-action="([^"]+)"', html).group(1)


def test_write_tools_are_offered() -> None:
    names = {t["function"]["name"] for t in TOOLS}
    assert {"add_asset", "add_liability", "add_transaction", "add_income", "add_bill"} <= names


def test_asset_is_proposed_then_saved_only_on_confirm(app, client, model) -> None:  # type: ignore[no-untyped-def]
    html = say(client, model, "add_asset", kind="gold", name="النگو", quantity=10, karat=18)
    assert "النگو" in html and "ثبت کن" in html
    with db(app) as s:
        assert s.scalars(select(Asset)).first() is None  # هنوز چیزی ثبت نشده
    confirmed = client.post(f"/assistant/actions/{action_id(html)}/confirm")
    assert confirmed.status_code == 200 and "ثبت شد" in confirmed.text
    with db(app) as s:
        asset = s.scalars(select(Asset)).one()
        assert (asset.name, asset.price_key, str(asset.quantity)) == ("النگو", "gold18_gram", "10")
    # تأیید دوباره چیزی را تکرار نمی‌کند
    assert client.post(f"/assistant/actions/{action_id(html)}/confirm").status_code == 404


def test_cancel_discards(app, client, model) -> None:  # type: ignore[no-untyped-def]
    html = say(client, model, "add_income", name="حقوق", amount_toman=60_000_000,
               frequency="monthly")
    assert client.post(f"/assistant/actions/{action_id(html)}/cancel").status_code == 200
    assert client.post(f"/assistant/actions/{action_id(html)}/confirm").status_code == 404
    with db(app) as s:
        assert s.scalars(select(IncomeStream)).first() is None


def test_liability_and_transactions(app, client, model) -> None:  # type: ignore[no-untyped-def]
    for html in (
        say(client, model, "add_liability", kind="bank_loan", lender="بانک ملت",
            principal_toman=200_000_000, installment_toman=8_000_000, installments_total=36),
        say(client, model, "add_transaction", direction="out", amount_toman=350_000,
            category="خوراک و رستوران", description="ناهار"),
        say(client, model, "add_transaction", direction="in", amount_toman=5_000_000,
            category="gift", description="عیدی"),
    ):
        client.post(f"/assistant/actions/{action_id(html)}/confirm")
    with db(app) as s:
        assert s.scalars(select(Liability)).one().lender == "بانک ملت"
        txs = {t.description: (t.direction, t.category, t.amount_toman)
               for t in s.scalars(select(Transaction))}
    assert txs == {"ناهار": ("out", "food", 350_000), "عیدی": ("in", "gift", 5_000_000)}


def test_invalid_proposal_returns_errors_to_model(app, client) -> None:  # type: ignore[no-untyped-def]
    with db(app) as s:
        result = json.loads(run_tool(s, "add_asset", json.dumps({"kind": "gold", "name": "x"})))
    assert "error" in result  # مقدار و عیار لازم است؛ مدل باید بپرسد


def test_actions_are_private(app, client, model) -> None:  # type: ignore[no-untyped-def]
    html = say(client, model, "add_income", name="حقوق", amount_toman=1000, frequency="monthly")
    with TestClient(app) as bob:
        register(bob, "09122222222")
        assert bob.post(f"/assistant/actions/{action_id(html)}/confirm").status_code == 404
