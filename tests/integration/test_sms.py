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

    def test_secret_messages_are_dropped_unstored(self, client: TestClient) -> None:
        h = {"X-Ingest-Token": TOKEN}
        response = client.post("/api/sms", json={"text": "بانک ملت\nرمز پویا: 482913"}, headers=h)
        assert response.status_code == 200 and response.json() == {"status": "ignored"}
        with db(client) as s:
            assert s.scalars(select(SmsInbox)).first() is None

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


def test_sms_endpoint_prefers_public_url() -> None:
    from app.web.sms_routes import sms_endpoint

    assert sms_endpoint("https://getvazir.ir/", "http", "internal", 8000) == \
        "https://getvazir.ir/api/sms"
    assert sms_endpoint("", "https", "example.ir", None) == "https://example.ir/api/sms"


IPHONE = "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15"
ANDROID = "Mozilla/5.0 (Linux; Android 14; SM-A546E) AppleWebKit/537.36 Chrome/129 Mobile"


def test_iphone_sees_open_shortcuts_guide_with_copy_buttons(client: TestClient) -> None:
    page = client.get("/sms", headers={"User-Agent": IPHONE}).text
    assert '<details class="card disclosure sms-ios" open' in page
    assert 'data-copy="#sms-endpoint"' in page and 'data-copy="#sms-token"' in page
    assert TOKEN in page and '<bdi class="ios-label">Get Contents of URL</bdi>' in page
    assert "&lt;bdi" not in page
    assert "sms-android" not in page and "uvicorn" not in page and "وای‌فای" not in page


def test_android_sees_android_card_only(client: TestClient) -> None:
    page = client.get("/sms", headers={"User-Agent": ANDROID}).text
    assert "sms-android" in page and "sms-ios" not in page


def test_desktop_sees_both_guides_closed(client: TestClient) -> None:
    page = client.get("/sms").text
    assert "sms-android" in page and '<details class="card disclosure sms-ios">' in page


def test_sms_page_shows_https_endpoint_behind_proxy(client: TestClient) -> None:
    page = client.get("/sms", headers={"X-Forwarded-Proto": "https",
                                       "Host": "finassist.example.ir"}).text
    assert "https://finassist.example.ir/api/sms" in page


def test_ui_labels_escapes_text() -> None:
    from app.web.render import ui_labels

    assert str(ui_labels("<b>x</b> [[Run]]")) == \
        '&lt;b&gt;x&lt;/b&gt; <bdi class="ios-label">Run</bdi>'


SHORTCUT = "https://www.icloud.com/shortcuts/cf3ee163cae046d0b4df7c3c97a0ff52"


def _client_with(tmp_path: Path, shortcut: str) -> TestClient:
    settings = Settings(database_url=f"sqlite:///{tmp_path / 's.db'}", secret_key="t",
                        ios_shortcut_url=shortcut)
    return TestClient(create_app(settings, price_sources=[], schedule=False,
                                 otp_sender=FakeSender()))


def test_ready_shortcut_gives_short_guide_with_manual_fallback(tmp_path: Path) -> None:
    with _client_with(tmp_path, SHORTCUT) as c:
        register(c)
        page = c.get("/sms", headers={"User-Agent": IPHONE}).text
    assert f'href="{SHORTCUT}"' in page and 'data-copy="#sms-token"' in page
    assert '<details class="sms-manual">' in page  # راه دستی بسته، زیر راه کوتاه
    assert page.index(SHORTCUT) < page.index("sms-manual")
    assert 'data-copy-first="#sms-token"' in page  # دکمه شورتکات کلید را خودش کپی می‌کند
    assert "video/ios-sms-setup.mp4" in page and "video/ios-sms-setup.jpg" in page


def test_without_shortcut_only_manual_steps(tmp_path: Path) -> None:
    with _client_with(tmp_path, "") as c:
        register(c)
        page = c.get("/sms", headers={"User-Agent": IPHONE}).text
    assert "icloud.com" not in page and "sms-manual" not in page
    assert "Get Contents of URL" in page
