"""ابزار عمومی محاسبه سود واقعی وام: بدون ورود، بدون ذخیره، با پیش‌فرض‌های عمومی."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.config import Settings
from app.main import create_app
from app.models import LoanAnalysis
from tests.integration.conftest import FakeSender, register

LOAN = {"amount": "۳۰۰٬۰۰۰٬۰۰۰", "months": "۳۶", "nominal_rate": "۲۳",
        "upfront_fee": "۵٬۰۰۰٬۰۰۰", "blocked_deposit": "۵۰٬۰۰۰٬۰۰۰", "blocked_months": "۳۶"}


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    settings = Settings(database_url=f"sqlite:///{tmp_path / 't.db'}", secret_key="t",
                        public_url="https://getvazir.ir")
    with TestClient(create_app(settings, price_sources=[], schedule=False,
                               otp_sender=FakeSender())) as c:
        yield c


def test_tool_page_is_public_and_indexable(client: TestClient) -> None:
    page = client.get("/tools/loan").text
    assert "<title>محاسبه سود واقعی وام | وزیر</title>" in page and "noindex" not in page
    assert 'action="/tools/loan#result"' in page and '"FAQPage"' in page
    assert "<loc>https://getvazir.ir/tools/loan</loc>" in client.get("/sitemap.xml").text


def test_anonymous_analysis_shows_result_and_stores_nothing(client: TestClient) -> None:
    response = client.post("/tools/loan", data=LOAN)
    assert response.status_code == 200 and "نتیجه محاسبه" in response.text
    assert "نرخ مؤثر" in response.text or "مؤثر" in response.text
    with client.app.state.session_factory() as db:  # type: ignore[attr-defined]
        assert db.scalar(select(func.count()).select_from(LoanAnalysis)) == 0


def test_public_tool_ignores_other_users_settings(client: TestClient) -> None:
    register(client)
    client.post("/settings", data={"dti_threshold": "۹۰", "inflation": "۹۹"})
    client.post("/logout")
    client.cookies.clear()
    page = client.post("/tools/loan", data=LOAN).text
    assert "تورم فرضی ۳۵٪" in page and "۹۹٪" not in page


def test_bad_input_returns_form_errors(client: TestClient) -> None:
    response = client.post("/tools/loan", data={"amount": "", "months": "۱۲"})
    assert response.status_code == 400 and "نتیجه محاسبه" not in response.text
