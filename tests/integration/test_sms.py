from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.config import Settings
from app.main import create_app
from app.models import Account, SmsInbox, Transaction
from tests.integration.conftest import FakeSender, register

TOKEN = "test-token-1234567890"
SMS = "بانک ملت\nکارت 6037991234561234\nبرداشت 2,500,000 ریال\nمانده 81,250,000"


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    settings = Settings(database_url=f"sqlite:///{tmp_path / 't.db'}", secret_key="t")
    app = create_app(settings, price_sources=[], schedule=False, otp_sender=FakeSender())
    with TestClient(app) as c:
        register(c)
        with db(c) as s:
            from app.services import set_user_setting
            from app.web.sms_routes import TOKEN_KEY

            set_user_setting(s, TOKEN_KEY, TOKEN)
            s.commit()
        yield c


def db(client: TestClient):  # type: ignore[no-untyped-def]
    from app.db import user_session

    return user_session(client.app.state.session_factory(), 1)  # type: ignore[attr-defined]


class TestApi:
    def test_requires_token(self, client: TestClient) -> None:
        assert client.post("/api/sms", json={"text": SMS}).status_code == 401
        bad = client.post("/api/sms", json={"text": SMS}, headers={"X-Ingest-Token": "x"})
        assert bad.status_code == 401

    def test_works_without_login_session(self, client: TestClient) -> None:
        client.post("/logout")
        response = client.post("/api/sms", json={"text": SMS, "received_at": "2026-10-03T09:42"},
                               headers={"X-Ingest-Token": TOKEN})
        assert response.status_code == 200
        assert response.json()["status"] == "failed"  # هنوز پارسر بانکی نداریم → صف بررسی
        with db(client) as s:
            stored = s.scalars(select(SmsInbox)).one()
            assert "6037991234561234" not in stored.text_masked

    def test_duplicate(self, client: TestClient) -> None:
        h = {"X-Ingest-Token": TOKEN}
        client.post("/api/sms", json={"text": SMS}, headers=h)
        again = client.post("/api/sms", json={"text": SMS}, headers=h)
        assert again.json()["status"] == "duplicate"

    def test_rejects_bad_body(self, client: TestClient) -> None:
        h = {"X-Ingest-Token": TOKEN}
        assert client.post("/api/sms", content=b"not json", headers=h).status_code == 400
        assert client.post("/api/sms", json={"text": ""}, headers=h).status_code == 400
        assert client.post("/api/sms", json={"text": "x" * 3000}, headers=h).status_code == 400

    def test_rate_limit(self, client: TestClient) -> None:
        h = {"X-Ingest-Token": TOKEN}
        codes = [client.post("/api/sms", json={"text": f"پیام {i}"}, headers=h).status_code
                 for i in range(65)]
        assert codes.count(429) == 5


class TestReviewQueue:
    def test_queue_complete_updates_account(self, client: TestClient) -> None:
        client.post("/api/sms", json={"text": SMS}, headers={"X-Ingest-Token": TOKEN})
        page = client.get("/sms").text
        assert "نیاز به بررسی" in page and "************1234" in page
        assert "۱ پیامک بانکی نیاز به بررسی دارد" in client.get("/").text
        with db(client) as s:
            sms_id = s.scalars(select(SmsInbox)).one().id
        form = client.get(f"/sms/{sms_id}/review", headers={"HX-Request": "true"}).text
        assert "<html" not in form and "ریال" in form
        response = client.post(f"/sms/{sms_id}/review", data={
            "bank": "mellat", "account_mask": "۱۲۳۴", "direction": "out",
            "amount": "2,500,000", "balance_after": "81,250,000", "description": "خرید"})
        assert response.status_code == 200 and "تراکنش ثبت شد" in response.text
        with db(client) as s:
            account = s.scalars(select(Account)).one()
            assert (account.account_mask, account.balance_toman) == ("1234", 8_125_000)
            tx = s.scalars(select(Transaction)).one()
            assert (tx.amount_toman, tx.direction, tx.description) == (250_000, "out", "خرید")

    def test_review_validation(self, client: TestClient) -> None:
        client.post("/api/sms", json={"text": SMS}, headers={"X-Ingest-Token": TOKEN})
        with db(client) as s:
            sms_id = s.scalars(select(SmsInbox)).one().id
        response = client.post(f"/sms/{sms_id}/review", headers={"HX-Request": "true"},
                               data={"bank": "mellat", "account_mask": "12",
                                     "direction": "out", "amount": "abc"})
        assert response.status_code == 422

    def test_ignore(self, client: TestClient) -> None:
        client.post("/api/sms", json={"text": "تبلیغ"}, headers={"X-Ingest-Token": TOKEN})
        with db(client) as s:
            sms_id = s.scalars(select(SmsInbox)).one().id
        client.post(f"/sms/{sms_id}/ignore")
        with db(client) as s:
            assert s.get(SmsInbox, sms_id).parse_status == "ignored"  # type: ignore[union-attr]


def test_upload_file(client: TestClient) -> None:
    content = "--- 2026-10-03T09:42\nپیام یک\n--- 2026-10-03T10:00\nپیام دو\n".encode()
    response = client.post("/sms/upload", files={"file": ("bank_sms.txt", content)})
    assert "۲ نیاز به بررسی" in response.text


def test_sms_pages_need_login(client: TestClient) -> None:
    client.post("/logout")
    assert client.get("/sms", follow_redirects=False).status_code == 303


def test_phone_endpoint_uses_mac_name_for_local_hosts() -> None:
    from app.web.sms_routes import phone_endpoint

    assert phone_endpoint("127.0.0.1", 8000, "MY-MAC.local") == "http://MY-MAC.local:8000/api/sms"
    assert phone_endpoint("0.0.0.0", 8000, "MY-MAC") == "http://MY-MAC.local:8000/api/sms"
    assert phone_endpoint("192.168.1.5", 8000, "x") == "http://192.168.1.5:8000/api/sms"


def test_sms_page_shows_https_endpoint_behind_proxy(client: TestClient) -> None:
    page = client.get("/sms", headers={"X-Forwarded-Proto": "https",
                                       "Host": "finassist.example.ir"}).text
    assert "https://finassist.example.ir/api/sms" in page
