from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.config import Settings
from app.main import create_app
from app.models import Account, Asset, Liability, LoanAnalysis, NetworthSnapshot, PriceQuote

PASSWORD = "very-secret-1"


@pytest.fixture
def app_client(tmp_path: Path) -> Iterator[TestClient]:
    settings = Settings(database_url=f"sqlite:///{tmp_path / 'test.db'}", secret_key="test")
    app = create_app(settings, migrate=True)
    with TestClient(app) as client:
        yield client


@pytest.fixture
def client(app_client: TestClient) -> TestClient:
    response = app_client.post("/setup", data={"password": PASSWORD, "password_repeat": PASSWORD},
                               follow_redirects=False)
    assert response.status_code == 303
    return app_client


def db(client: TestClient):  # type: ignore[no-untyped-def]
    return client.app.state.session_factory()  # type: ignore[attr-defined]


class TestAuth:
    def test_first_run_redirects_to_setup(self, app_client: TestClient) -> None:
        assert app_client.get("/", follow_redirects=False).headers["location"] == "/login"
        assert app_client.get("/login", follow_redirects=False).headers["location"] == "/setup"

    def test_setup_rejects_short_password(self, app_client: TestClient) -> None:
        response = app_client.post("/setup", data={"password": "short", "password_repeat": "short"})
        assert response.status_code == 400

    def test_setup_only_once(self, client: TestClient) -> None:
        response = client.post("/setup", data={"password": "other-pass-1",
                                               "password_repeat": "other-pass-1"},
                               follow_redirects=False)
        assert response.headers["location"] == "/login"

    def test_logout_then_login(self, client: TestClient) -> None:
        client.post("/logout")
        assert client.get("/assets", follow_redirects=False).status_code == 303
        assert client.post("/login", data={"password": "wrong-pass"}).status_code == 401
        client.post("/login", data={"password": PASSWORD})
        assert client.get("/assets").status_code == 200

    def test_htmx_request_gets_redirect_header(self, app_client: TestClient) -> None:
        response = app_client.post("/assets/1/delete", headers={"HX-Request": "true"})
        assert response.status_code == 401
        assert response.headers["HX-Redirect"] == "/login"


class TestDataEntry:
    def test_gold_asset_valued_after_price_entry(self, client: TestClient) -> None:
        response = client.post("/assets", data={
            "kind": "gold", "name": "النگو", "quantity": "۱۲٫۵", "karat": "۱۸", "note": ""})
        assert response.status_code == 200
        with db(client) as s:
            asset = s.scalars(select(Asset)).one()
            assert asset.price_key == "gold18_gram"
            assert str(asset.quantity) == "12.5"

        client.post("/prices", data={"price:gold18_gram": "۸٬۰۰۰٬۰۰۰"})
        with db(client) as s:
            quote = s.scalars(select(PriceQuote)).one()
            assert quote.price_toman == 8_000_000
        assert "۱۰۰٬۰۰۰٬۰۰۰ تومان" in client.get("/assets").text

    def test_stock_symbol_builds_price_key(self, client: TestClient) -> None:
        client.post("/assets", data={"kind": "stock", "name": "فولاد", "symbol": "فولاد",
                                     "quantity": "1000"})
        assert "۱۰۰۰" in client.get("/assets").text
        with db(client) as s:
            assert s.scalars(select(Asset)).one().price_key == "stock:فولاد"
        assert "stock:فولاد" in client.get("/prices").text

    def test_manual_asset_sets_updated_at(self, client: TestClient) -> None:
        client.post("/assets", data={"kind": "car", "name": "۲۰۷",
                                     "manual_value_toman": "1,500,000,000"})
        with db(client) as s:
            asset = s.scalars(select(Asset)).one()
            assert asset.manual_value_toman == 1_500_000_000
            assert asset.manual_value_updated_at is not None

    def test_invalid_number_shows_error(self, client: TestClient) -> None:
        response = client.post("/assets", data={"kind": "car", "name": "x",
                                                "manual_value_toman": "abc"})
        assert response.status_code == 400
        assert "عدد نامعتبر" in response.text

    def test_account_mask_must_be_four_digits(self, client: TestClient) -> None:
        bad = client.post("/accounts", data={"bank": "mellat", "account_mask": "12345",
                                             "balance_toman": "100"})
        assert bad.status_code == 400
        client.post("/accounts", data={"bank": "mellat", "account_mask": "۱۲۳۴",
                                       "balance_toman": "81,250,000"})
        with db(client) as s:
            account = s.scalars(select(Account)).one()
            assert (account.account_mask, account.balance_toman) == ("1234", 81_250_000)

    def test_edit_and_delete_liability(self, client: TestClient) -> None:
        client.post("/liabilities", data={
            "kind": "bank_loan", "lender": "ملت", "principal_toman": "100000000",
            "installment_toman": "5000000", "installments_total": "24",
            "installments_paid": "4", "nominal_rate": "۱۸", "start_date": "۱۴۰۴/۰۱/۱۵"})
        with db(client) as s:
            loan = s.scalars(select(Liability)).one()
            assert str(loan.nominal_rate) == "0.18"
            assert loan.start_date.isoformat() == "2025-04-04"
        edit = client.get(f"/liabilities/{loan.id}/edit")
        assert "۱۴۰۴/۰۱/۱۵" in edit.text
        client.post(f"/liabilities/{loan.id}", data={
            "kind": "bank_loan", "lender": "ملت", "principal_toman": "100000000",
            "installment_toman": "5000000", "installments_total": "24",
            "installments_paid": "10"})
        assert "۷۰٬۰۰۰٬۰۰۰ تومان" in client.get("/liabilities").text  # 14 × 5M
        response = client.post(f"/liabilities/{loan.id}/delete", headers={"HX-Request": "true"})
        assert response.status_code == 200
        with db(client) as s:
            assert s.scalars(select(Liability)).all() == []

    def test_paid_cannot_exceed_total(self, client: TestClient) -> None:
        response = client.post("/liabilities", data={
            "kind": "bank_loan", "lender": "x", "principal_toman": "1",
            "installment_toman": "1", "installments_total": "2", "installments_paid": "3"})
        assert response.status_code == 400


class TestDashboard:
    def test_totals_add_up_and_snapshot_recorded(self, client: TestClient) -> None:
        client.post("/prices", data={"price:usd": "100000", "price:gold18_gram": "8000000"})
        client.post("/assets", data={"kind": "fx", "name": "دلار", "market": "usd",
                                     "quantity": "1000"})                   # 100M
        client.post("/accounts", data={"bank": "melli", "account_mask": "5678",
                                       "balance_toman": "50000000"})       # 50M
        client.post("/liabilities", data={"kind": "personal", "lender": "علی",
                                          "principal_toman": "30000000"})  # 30M
        client.post("/incomes", data={"name": "حقوق", "amount_toman": "60000000",
                                      "frequency": "monthly", "active": "on"})
        client.post("/liabilities", data={"kind": "bnpl", "lender": "اسنپ‌پی",
                                          "principal_toman": "12000000",
                                          "installment_toman": "3000000",
                                          "installments_total": "4"})      # 12M, 3M/month

        page = client.get("/").text
        assert "۱۰۸ میلیون تومان" in page   # 150M − 42M
        assert "۱٬۰۸۰ $" in page
        assert "۱۳٫۵ گرم" in page
        assert "۵٫۰٪" in page               # 3M / 60M
        with db(client) as s:
            snap = s.scalars(select(NetworthSnapshot)).one()
            assert (snap.assets_toman, snap.liabilities_toman, snap.networth_toman) == (
                150_000_000, 42_000_000, 108_000_000)

    def test_missing_price_warning(self, client: TestClient) -> None:
        client.post("/assets", data={"kind": "coin", "name": "سکه", "market": "coin_emami",
                                     "quantity": "2"})
        assert "قیمت بازار ندارد" in client.get("/").text


class TestLoanAndSettings:
    def test_loan_analysis_saved(self, client: TestClient) -> None:
        response = client.post("/loan", data={
            "amount": "1,000,000,000", "months": "12", "nominal_rate": "18",
            "blocked_deposit": "200000000", "blocked_months": "12",
            "monthly_income": "300000000", "current_installments": "0"})
        assert response.status_code == 200
        assert "۳۱٫۲۵٪" in response.text
        with db(client) as s:
            assert len(s.scalars(select(LoanAnalysis)).all()) == 1

    def test_loan_requires_rate_or_installment(self, client: TestClient) -> None:
        response = client.post("/loan", data={"amount": "1000", "months": "12"})
        assert response.status_code == 400

    def test_settings_change_threshold(self, client: TestClient) -> None:
        client.post("/settings", data={"dti_threshold": "40", "inflation": "30"})
        page = client.get("/settings").text
        assert 'value="۴۰"' in page and 'value="۳۰"' in page

    def test_export_json(self, client: TestClient) -> None:
        client.post("/accounts", data={"bank": "mellat", "account_mask": "1234",
                                       "balance_toman": "1"})
        data = client.get("/export.json").json()
        assert data["accounts"][0]["account_mask"] == "1234"
        assert "settings" not in data  # هش رمز و کلید نشست بیرون نمی‌رود
