from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import jdatetime
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.config import Settings
from app.main import create_app
from app.models import Account, ExpenseStream, Transaction

PASSWORD = "very-secret-1"


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    settings = Settings(database_url=f"sqlite:///{tmp_path / 't.db'}", secret_key="t")
    with TestClient(create_app(settings, price_sources=[], schedule=False)) as c:
        c.post("/setup", data={"password": PASSWORD, "password_repeat": PASSWORD})
        yield c


def db(client: TestClient):  # type: ignore[no-untyped-def]
    return client.app.state.session_factory()  # type: ignore[attr-defined]


def this_month() -> str:
    today = jdatetime.date.today()
    return f"{today.year}-{today.month:02d}"


class TestBills:
    def test_fixed_costs_reduce_free_cash(self, client: TestClient) -> None:
        client.post("/incomes", data={"name": "حقوق", "amount_toman": "60,000,000",
                                      "frequency": "monthly", "active": "on"})
        response = client.post("/bills", data={"name": "اجاره", "amount_toman": "15,000,000",
                                               "frequency": "monthly", "category": "housing",
                                               "active": "on"}, follow_redirects=False)
        assert response.status_code == 303
        client.post("/bills", data={"name": "بیمه", "amount_toman": "12,000,000",
                                    "frequency": "yearly", "active": "on"})
        with db(client) as s:
            assert len(s.scalars(select(ExpenseStream)).all()) == 2
        page = client.get("/").text
        assert "هزینه ثابت" in page
        assert "۴۴" in page  # ۶۰ - ۱۵ - ۱ میلیون

    def test_bills_page_lists_monthly_amount(self, client: TestClient) -> None:
        client.post("/bills", data={"name": "شهریه", "amount_toman": "30,000,000",
                                    "frequency": "quarterly", "active": "on"})
        page = client.get("/bills").text
        assert "شهریه" in page and "۱۰" in page


class TestSpending:
    def test_manual_expense_shows_in_month_with_category_total(self, client: TestClient) -> None:
        today = jdatetime.date.today().strftime("%Y/%m/%d")
        for amount, category in (("250,000", "food"), ("150,000", "food"),
                                 ("1,000,000", "transport"), ("9,000,000", "transfer")):
            response = client.post("/spending", data={
                "amount_toman": amount, "category": category, "description": "تست",
                "occurred_on": today}, follow_redirects=False)
            assert response.status_code == 303
        page = client.get(f"/spending?m={this_month()}").text
        assert "خوراک" in page and "رفت‌وآمد" in page
        assert "۱٫۴" in page  # جمع خرج ۱٫۴ میلیون؛ انتقال به خود حساب نمی‌شود
        with db(client) as s:
            manual = s.scalars(select(Transaction)).all()
            assert all(t.account_id is None and t.direction == "out" for t in manual)

    def test_requires_amount_and_category(self, client: TestClient) -> None:
        response = client.post("/spending", data={"amount_toman": "", "category": ""})
        assert response.status_code == 400

    def test_other_month_is_empty(self, client: TestClient) -> None:
        client.post("/spending", data={"amount_toman": "100", "category": "food"})
        assert "تست" not in client.get("/spending?m=1390-01").text
        assert client.get("/spending?m=bad").status_code == 200

    def test_sms_transaction_only_category_is_editable(self, client: TestClient) -> None:
        with db(client) as s:
            account = Account(bank="saman", account_mask="1234", balance_toman=0)
            s.add(account)
            s.flush()
            tx = Transaction(account_id=account.id, direction="out", amount_toman=700_000,
                             occurred_at=datetime.now(UTC), description="خرید")
            s.add(tx)
            s.commit()
            tx_id = tx.id
        form = client.get(f"/spending/{tx_id}/edit").text
        assert 'name="amount_toman"' not in form and 'name="category"' in form
        assert "/delete" not in form
        client.post(f"/spending/{tx_id}", data={"category": "shopping", "amount_toman": "1"})
        with db(client) as s:
            tx = s.get(Transaction, tx_id)
            assert tx.category == "shopping" and tx.amount_toman == 700_000
        assert client.post(f"/spending/{tx_id}/delete").status_code == 404

    def test_manual_expense_can_be_edited_and_deleted(self, client: TestClient) -> None:
        client.post("/spending", data={"amount_toman": "100", "category": "food"})
        with db(client) as s:
            tx_id = s.scalars(select(Transaction.id)).one()
        client.post(f"/spending/{tx_id}", data={"amount_toman": "300", "category": "fun"})
        with db(client) as s:
            tx = s.get(Transaction, tx_id)
            assert (tx.amount_toman, tx.category) == (300, "fun")
        client.post(f"/spending/{tx_id}/delete")
        with db(client) as s:
            assert s.get(Transaction, tx_id) is None

    def test_home_shows_month_spending(self, client: TestClient) -> None:
        client.post("/incomes", data={"name": "حقوق", "amount_toman": "1000",
                                      "frequency": "monthly", "active": "on"})
        client.post("/spending", data={"amount_toman": "2,500,000", "category": "food"})
        page = client.get("/").text
        assert "خرج این ماه" in page and 'href="/spending"' in page

    def test_pages_need_login(self, client: TestClient) -> None:
        client.post("/logout")
        for url in ("/spending", "/spending/new", "/bills"):
            assert client.get(url, follow_redirects=False).status_code == 303


def test_more_page_offers_light_dark_and_system_theme(client: TestClient) -> None:
    page = client.get("/more").text
    for key in ("system", "light", "dark"):
        assert f'data-set-theme="{key}"' in page
    assert 'localStorage.getItem("theme")' in client.get("/").text  # پیش از نمایش صفحه
