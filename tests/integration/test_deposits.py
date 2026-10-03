from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import jdatetime
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.config import Settings
from app.db import user_session
from app.main import create_app
from app.models import Account, Transaction
from tests.integration.conftest import FakeSender, register


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    settings = Settings(database_url=f"sqlite:///{tmp_path / 't.db'}", secret_key="t")
    app = create_app(settings, price_sources=[], schedule=False, otp_sender=FakeSender())
    with TestClient(app) as c:
        register(c)
        yield c


def db(client: TestClient):  # type: ignore[no-untyped-def]
    return user_session(client.app.state.session_factory(), 1)  # type: ignore[attr-defined]


def this_month() -> str:
    today = jdatetime.date.today()
    return f"{today.year}-{today.month:02d}"


def sms_tx(client: TestClient, direction: str, amount: int) -> int:
    with db(client) as s:
        account = s.scalars(select(Account)).first() or Account(
            bank="saman", account_mask="1234", balance_toman=0)
        s.add(account)
        s.flush()
        tx = Transaction(account_id=account.id, direction=direction, amount_toman=amount,
                         occurred_at=datetime.now(UTC), description="واریز پایا")
        s.add(tx)
        s.commit()
        return tx.id


def test_deposits_page_lists_incoming_only_with_category_totals(client: TestClient) -> None:
    sms_tx(client, "in", 60_000_000)
    sms_tx(client, "out", 999_000)
    client.post("/deposits", data={"amount_toman": "5,000,000", "category": "gift",
                                   "description": "عیدی"})
    client.post("/deposits", data={"amount_toman": "20,000,000", "category": "transfer"})
    page = client.get(f"/deposits?m={this_month()}").text
    assert "عیدی" in page and "واریز پایا" in page
    assert "۹۹۹" not in page  # برداشت این‌جا نیست
    assert "۶۵" in page  # ۶۰ + ۵ میلیون؛ انتقال به خود حساب نمی‌شود
    assert "عیدی" not in client.get(f"/spending?m={this_month()}").text


def test_sms_deposit_is_categorized_not_edited(client: TestClient) -> None:
    tx_id = sms_tx(client, "in", 60_000_000)
    form = client.get(f"/deposits/{tx_id}/edit").text
    assert 'name="amount_toman"' not in form and "حقوق" in form
    client.post(f"/deposits/{tx_id}", data={"category": "salary", "amount_toman": "1"})
    with db(client) as s:
        tx = s.get(Transaction, tx_id)
        assert (tx.category, tx.amount_toman) == ("salary", 60_000_000)
    assert client.post(f"/deposits/{tx_id}/delete").status_code == 404


def test_routes_do_not_cross_directions(client: TestClient) -> None:
    out_id = sms_tx(client, "out", 100)
    in_id = sms_tx(client, "in", 100)
    assert client.get(f"/deposits/{out_id}/edit").status_code == 404
    assert client.get(f"/spending/{in_id}/edit").status_code == 404


def test_manual_deposit_crud(client: TestClient) -> None:
    client.post("/deposits", data={"amount_toman": "100", "category": "other"})
    with db(client) as s:
        tx = s.scalars(select(Transaction)).one()
        assert (tx.direction, tx.account_id) == ("in", None)
    client.post(f"/deposits/{tx.id}/delete")
    with db(client) as s:
        assert s.scalars(select(Transaction)).first() is None


def test_tab_and_home_show_deposits(client: TestClient) -> None:
    client.post("/incomes", data={"name": "حقوق", "amount_toman": "1000",
                                  "frequency": "monthly", "active": "on"})
    client.post("/deposits", data={"amount_toman": "7,000,000", "category": "salary"})
    assert 'href="/deposits"' in client.get("/spending").text
    home = client.get("/").text
    assert "واریز این ماه" in home
