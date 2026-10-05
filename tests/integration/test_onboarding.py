"""راه‌اندازی اولیه بعد از ثبت‌نام: چی داری ← چقدر ← ماه به ماه ← پیامک ← کارت شخصیت."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.config import Settings
from app.main import create_app
from app.models import Account, Asset, ExpenseStream, IncomeStream
from tests.integration.conftest import PASSWORD, PHONE, FakeSender, last_code


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    settings = Settings(database_url=f"sqlite:///{tmp_path / 't.db'}", secret_key="t")
    with TestClient(create_app(settings, price_sources=[], schedule=False,
                               otp_sender=FakeSender())) as c:
        c.post("/signup", data={"phone": PHONE})
        response = c.post("/verify", data={"code": last_code(c, PHONE), "password": PASSWORD,
                                           "password_repeat": PASSWORD}, follow_redirects=False)
        assert response.headers["location"] == "/start"  # کاربر تازه مستقیم به راه‌اندازی
        yield c


def rows(client: TestClient, model: type) -> list:  # type: ignore[type-arg]
    from app.db import user_session

    with user_session(client.app.state.session_factory(), 1) as s:  # type: ignore[attr-defined]
        return list(s.scalars(select(model)))


def test_full_setup_records_data_and_personalizes_persona(client: TestClient) -> None:
    page = client.get("/start", follow_redirects=True).text
    assert "چی داری" in page and 'value="gold"' in page

    step = client.post("/start/have", data={"kinds": ["gold", "bank", "coin"]},
                       follow_redirects=False)
    assert step.headers["location"] == "/start/amounts"
    page = client.get("/start/amounts").text
    assert 'name="gold_grams"' in page and 'name="bank_balance"' in page
    assert 'name="coin_coin_half"' in page and 'name="fx_amount"' not in page

    step = client.post("/start/amounts", data={
        "gold_grams": "۱۰", "coin_coin_half": "2", "bank_name": "saman",
        "bank_balance": "50,000,000"}, follow_redirects=False)
    assert step.headers["location"] == "/start/monthly"
    gold = [a for a in rows(client, Asset) if a.kind == "gold"][0]
    assert str(gold.quantity) == "10" and gold.karat == 18 and gold.price_key == "gold18_gram"
    coin = [a for a in rows(client, Asset) if a.kind == "coin"][0]
    assert coin.price_key == "coin_half" and str(coin.quantity) == "2"
    assert rows(client, Account)[0].balance_toman == 50_000_000

    step = client.post("/start/monthly", data={"income": "30,000,000", "fixed_rent": "10,000,000"},
                       follow_redirects=False)
    assert step.headers["location"] == "/start/sms"
    assert rows(client, IncomeStream)[0].amount_toman == 30_000_000
    rent = rows(client, ExpenseStream)[0]
    assert rent.amount_toman == 10_000_000 and rent.category == "housing"

    page = client.get("/start/sms").text
    assert "۲۰٬۰۰۰٬۰۰۰" in page  # ماهی ۲۰ میلیون می‌ماند
    assert "/sms" in page

    page = client.get("/start/card").text
    assert 'href="/persona"' in page

    quiz = client.get("/persona/quick").text  # جواب‌های پیش‌فرض از داده‌های ثبت‌شده
    assert 'name="housing" value="renter" checked' in quiz
    assert 'name="interests" value="gold" checked' in quiz
    assert 'name="experience" value="safe" checked' in quiz
    assert 'name="emergency" value="3_6" checked' in quiz  # ۵۰ میلیون نقد ÷ ۱۰ میلیون ثابت
    assert "data-inferred" in quiz


def test_nothing_chosen_skips_amounts(client: TestClient) -> None:
    step = client.post("/start/have", data={}, follow_redirects=False)
    assert step.headers["location"] == "/start/monthly"


def test_no_income_choice_is_remembered_for_persona(client: TestClient) -> None:
    client.post("/start/monthly", data={"no_income": "1"})
    assert rows(client, IncomeStream) == []
    assert 'name="income" value="none" checked' in client.get("/persona/quick").text


def test_bad_amount_shows_error_and_saves_nothing(client: TestClient) -> None:
    client.post("/start/have", data={"kinds": ["gold", "cash"]})
    response = client.post("/start/amounts", data={"gold_grams": "abc", "cash_value": "5,000,000"})
    assert response.status_code == 400 and 'name="gold_grams"' in response.text
    assert rows(client, Asset) == []


def test_skip_finishes_and_dashboard_stops_pointing_to_setup(client: TestClient) -> None:
    assert 'href="/start"' in client.get("/").text  # داشبورد خالی: ادامه راه‌اندازی
    assert client.get("/start/skip", follow_redirects=False).headers["location"] == "/"
    assert 'href="/start"' not in client.get("/").text
    assert client.get("/start", follow_redirects=False).headers["location"] == "/start/have"
