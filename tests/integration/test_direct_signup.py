"""ثبت‌نام بدون پنل پیامک: شماره + رمز، بازیابی رمز بسته."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

PASSWORD = "very-secret-1"


def make(tmp_path: Path, **extra: str) -> TestClient:
    settings = Settings(database_url=f"sqlite:///{tmp_path / 't.db'}", secret_key="t", **extra)
    return TestClient(create_app(settings, price_sources=[], schedule=False))


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    with make(tmp_path) as c:
        yield c


def signup(client: TestClient, phone: str = "09121234567", password: str = PASSWORD,
           repeat: str | None = None):  # type: ignore[no-untyped-def]
    return client.post("/signup", data={"phone": phone, "password": password,
                                        "password_repeat": repeat or password},
                       follow_redirects=False)


def test_signup_form_asks_for_password_not_code(client: TestClient) -> None:
    page = client.get("/signup").text
    assert 'name="password"' in page and 'name="password_repeat"' in page
    assert "ارسال کد" not in page


def test_signup_logs_in_and_password_works_later(client: TestClient) -> None:
    response = signup(client, "۰۹۱۲۱۲۳۴۵۶۷")
    assert response.status_code == 303 and response.headers["location"] == "/"
    assert client.get("/more", follow_redirects=False).status_code == 200
    client.post("/logout")
    assert client.get("/more", follow_redirects=False).status_code == 303
    login = client.post("/login", data={"phone": "09121234567", "password": PASSWORD},
                        follow_redirects=False)
    assert login.headers["location"] == "/"


def test_signup_validation(client: TestClient) -> None:
    assert signup(client, "123").status_code == 400
    assert signup(client, password="short").status_code == 400
    assert signup(client, repeat="different-pass").status_code == 400
    assert signup(client).status_code == 303
    client.post("/logout")
    assert signup(client).status_code == 409  # شماره تکراری


def test_signups_per_ip_are_limited(client: TestClient) -> None:
    for i in range(5):
        assert signup(client, f"0912000000{i}").status_code == 303
        client.post("/logout")
    assert signup(client, "09120000009").status_code == 429


def test_owner_phone_cannot_be_claimed_without_sms(tmp_path: Path) -> None:
    with make(tmp_path, owner_phone="09129999999") as client:
        assert signup(client, "09129999999").status_code == 403


def test_reset_and_verify_are_closed(client: TestClient) -> None:
    assert "پشتیبانی" in client.get("/forgot").text
    assert client.post("/forgot", data={"phone": "09121234567"}).status_code == 404
    assert client.get("/verify", follow_redirects=False).headers["location"] == "/signup"
    assert client.post("/verify", data={"code": "1"},
                       follow_redirects=False).headers["location"] == "/signup"


def test_sms_panel_configured_keeps_code_flow(tmp_path: Path) -> None:
    with make(tmp_path, smsir_api_key="k", smsir_template_id="1") as client:
        assert "ارسال کد" in client.get("/signup").text
