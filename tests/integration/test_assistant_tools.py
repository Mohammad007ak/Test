"""ابزارهای وزیر: عدد دقیق از کد خود اپ، فقط داده همان کاربر، بدون اطلاعات حساس."""

import json
from collections.abc import Iterator
from pathlib import Path

import jdatetime
import pytest
from fastapi.testclient import TestClient

from app.assistant.tools import TOOLS, run_tool
from app.config import Settings
from app.db import user_session
from app.main import create_app
from app.models import PriceQuote, utcnow
from tests.integration.conftest import FakeSender, register


@pytest.fixture
def app(tmp_path: Path):  # type: ignore[no-untyped-def]
    settings = Settings(database_url=f"sqlite:///{tmp_path / 't.db'}", secret_key="t")
    app = create_app(settings, price_sources=[], schedule=False, otp_sender=FakeSender())
    with app.state.session_factory() as s:
        s.add(PriceQuote(key="usd", price_toman=100_000, fetched_at=utcnow(), source="alanchand"))
        s.commit()
    return app


@pytest.fixture
def client(app) -> Iterator[TestClient]:  # type: ignore[no-untyped-def]
    with TestClient(app) as c:
        register(c)
        c.post("/assets", data={"kind": "fx", "name": "دلار", "currency": "usd",
                                "quantity": "1000"})
        c.post("/accounts", data={"bank": "saman", "account_mask": "1234",
                                  "balance_toman": "50,000,000"})
        c.post("/incomes", data={"name": "حقوق", "amount_toman": "60,000,000",
                                 "frequency": "monthly", "active": "on"})
        c.post("/liabilities", data={"kind": "bank_loan", "lender": "بانک ملت",
                                     "principal_toman": "100,000,000",
                                     "installment_toman": "6,000,000",
                                     "installments_total": "20", "installments_paid": "0"})
        c.post("/spending", data={"amount_toman": "300,000", "category": "food",
                                  "description": "رستوران"})
        c.post("/spending", data={"amount_toman": "200,000", "category": "food"})
        yield c


def call(app, name: str, user_id: int = 1, **args: object) -> dict:  # type: ignore[no-untyped-def]
    with user_session(app.state.session_factory(), user_id) as db:
        return json.loads(run_tool(db, name, json.dumps(args)))


def month() -> str:
    today = jdatetime.date.today()
    return f"{today.year}-{today.month:02d}"


def test_tool_schemas_are_openai_function_format() -> None:
    names = {t["function"]["name"] for t in TOOLS}
    assert {"overview", "spending", "compare_months", "assets", "liabilities", "prices",
            "analyze_loan"} <= names
    for tool in TOOLS:
        assert tool["type"] == "function" and tool["function"]["parameters"]["type"] == "object"


def test_overview_numbers(app, client) -> None:  # type: ignore[no-untyped-def]
    data = call(app, "overview")
    assert data["assets_toman"] == 150_000_000  # ۱۰۰ میلیون دلار + ۵۰ میلیون حساب
    assert data["liabilities_toman"] == 120_000_000  # ۲۰ قسط × ۶ میلیون باقی‌مانده
    assert data["monthly_income_toman"] == 60_000_000
    assert data["monthly_installments_toman"] == 6_000_000
    assert data["networth_toman"] == 30_000_000


def test_spending_by_category(app, client) -> None:  # type: ignore[no-untyped-def]
    data = call(app, "spending", month=month())
    assert data["total_toman"] == 500_000
    assert data["by_category"][0] == {"category": "خوراک و رستوران", "total_toman": 500_000}


def test_compare_months(app, client) -> None:  # type: ignore[no-untyped-def]
    data = call(app, "compare_months", month_a="1390-01", month_b=month())
    assert data["b"]["total_toman"] == 500_000 and data["a"]["total_toman"] == 0


def test_loan_analysis_uses_users_income(app, client) -> None:  # type: ignore[no-untyped-def]
    data = call(app, "analyze_loan", amount_toman=100_000_000, months=12,
                nominal_rate_percent=23)
    assert 0.2 < data["effective_rate"] < 0.3
    assert data["dti_after"] > data["dti_before"]


def test_no_sensitive_fields_leak(app, client) -> None:  # type: ignore[no-untyped-def]
    text = json.dumps([call(app, name) for name in ("overview", "assets", "liabilities")],
                      ensure_ascii=False)
    assert "1234" not in text and "0912" not in text


def test_other_user_sees_nothing(app, client) -> None:  # type: ignore[no-untyped-def]
    with TestClient(app) as bob:
        register(bob, "09122222222")
    assert call(app, "overview", user_id=2)["assets_toman"] == 0
    assert call(app, "spending", user_id=2, month=month())["total_toman"] == 0


def test_bad_arguments_return_error_not_crash(app, client) -> None:  # type: ignore[no-untyped-def]
    assert "error" in call(app, "spending", month="بد")
    assert "error" in call(app, "nope")
    with user_session(app.state.session_factory(), 1) as db:
        assert "error" in json.loads(run_tool(db, "overview", "{not json"))
