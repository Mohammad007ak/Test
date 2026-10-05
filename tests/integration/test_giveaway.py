"""صفحه جایزه (/gift): ثبت آیدی اینستاگرام برای ۳ ماه وزیر ویژه، و فهرستش در پنل مدیریت."""

from collections.abc import Iterator
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.web import giveaway_routes
from tests.integration.conftest import PASSWORD, PHONE, FakeSender, last_code, register

OTHER = "09122222222"


@pytest.fixture
def app(tmp_path: Path):  # type: ignore[no-untyped-def]
    settings = Settings(database_url=f"sqlite:///{tmp_path / 't.db'}", secret_key="t",
                        owner_phone=PHONE)
    return create_app(settings, price_sources=[], schedule=False, otp_sender=FakeSender())


@pytest.fixture
def clients(app) -> Iterator[tuple[TestClient, TestClient]]:  # type: ignore[no-untyped-def]
    with TestClient(app) as owner, TestClient(app) as bob:
        register(owner, PHONE)
        register(bob, OTHER)
        yield owner, bob


@pytest.fixture(autouse=True)
def during_giveaway(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(giveaway_routes, "tehran_today", lambda: date(2026, 10, 5))


def test_visitor_sees_rules_and_signup_returns_to_gift(app) -> None:  # type: ignore[no-untyped-def]
    with TestClient(app) as visitor:
        page = visitor.get("/gift")
        assert page.status_code == 200 and "۲۵ مهر" in page.text
        assert 'href="/gift/join"' in page.text
        go = visitor.get("/gift/join", follow_redirects=False)
        assert go.headers["location"] == "/signup"
        visitor.post("/signup", data={"phone": OTHER}, follow_redirects=False)
        response = visitor.post("/verify", data={"code": last_code(visitor, OTHER),
                                                 "password": PASSWORD,
                                                 "password_repeat": PASSWORD},
                                follow_redirects=False)
        assert response.headers["location"] == "/gift"


def test_claim_is_saved_once_per_user_and_shown_to_owner(
        clients: tuple[TestClient, TestClient]) -> None:
    owner, bob = clients
    assert 'name="instagram"' in bob.get("/gift").text
    bad = bob.post("/gift", data={"instagram": "علی رضا"})
    assert bad.status_code == 400
    bob.post("/gift", data={"instagram": "@Bob.Saver"})
    page = bob.get("/gift").text
    assert "bob.saver" in page and 'name="instagram"' in page  # می‌تواند آیدی را اصلاح کند
    bob.post("/gift", data={"instagram": "bob.saver2"})
    admin = owner.get("/admin").text
    assert "bob.saver2" in admin and "0912***2222" in admin


def test_same_instagram_cannot_be_claimed_by_two_users(
        clients: tuple[TestClient, TestClient]) -> None:
    owner, bob = clients
    bob.post("/gift", data={"instagram": "bob.saver"})
    taken = owner.post("/gift", data={"instagram": "@BOB.saver"})
    assert taken.status_code == 409


def test_closed_after_deadline(clients: tuple[TestClient, TestClient],
                               monkeypatch: pytest.MonkeyPatch) -> None:
    _owner, bob = clients
    monkeypatch.setattr(giveaway_routes, "tehran_today", lambda: date(2026, 10, 18))
    page = bob.get("/gift").text
    assert 'name="instagram"' not in page
    assert bob.post("/gift", data={"instagram": "bob"}).status_code == 403
