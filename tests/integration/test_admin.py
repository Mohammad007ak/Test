"""پنل مدیریت کاربران: فقط صاحب برنامه؛ آمار و فهرست بدون هیچ مبلغی؛ غیرفعال‌سازی و حذف کامل."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.config import Settings
from app.main import create_app
from app.models import Account, User
from tests.integration.conftest import PASSWORD, PHONE, FakeSender, register

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
        bob.post("/accounts", data={"bank": "saman", "account_mask": "1234",
                                    "balance_toman": "987,654,321"})
        yield owner, bob


def _count(client: TestClient, model: type) -> int:
    with client.app.state.session_factory() as s:  # type: ignore[attr-defined]
        return s.scalar(select(func.count()).select_from(model)) or 0


def _bob_id(client: TestClient) -> int:
    with client.app.state.session_factory() as s:  # type: ignore[attr-defined]
        return s.scalars(select(User.id).where(User.phone == OTHER)).one()


def test_only_owner_can_open_admin(clients: tuple[TestClient, TestClient]) -> None:
    owner, bob = clients
    assert bob.get("/admin").status_code == 404
    assert bob.post(f"/admin/users/{_bob_id(bob)}/disable").status_code == 404
    page = owner.get("/admin")
    assert page.status_code == 200 and 'name="robots" content="noindex' in page.text


def test_owner_sees_counts_but_never_amounts_or_full_phone(
        clients: tuple[TestClient, TestClient]) -> None:
    owner, _bob = clients
    page = owner.get("/admin").text
    assert "0912***2222" in page and OTHER not in page
    assert "۹۸۷" not in page and "987" not in page  # مبلغ دارایی بزرگ هرگز نمایش داده نمی‌شود
    found = owner.get("/admin", params={"q": "2222"}).text
    assert "0912***2222" in found and "0912***1111" not in found


def test_disable_logs_user_out_and_blocks_login(clients: tuple[TestClient, TestClient]) -> None:
    owner, bob = clients
    bob_id = _bob_id(owner)
    assert owner.post(f"/admin/users/{bob_id}/disable", follow_redirects=False).status_code == 303
    assert bob.get("/sms", follow_redirects=False).status_code == 303  # نشست قبلی باطل شد
    login = bob.post("/login", data={"phone": OTHER, "password": PASSWORD}, follow_redirects=False)
    assert login.status_code == 400 and "غیرفعال" in login.text
    owner.post(f"/admin/users/{bob_id}/enable")
    login = bob.post("/login", data={"phone": OTHER, "password": PASSWORD}, follow_redirects=False)
    assert login.status_code == 303


def test_delete_needs_phone_confirmation_and_removes_all_data(
        clients: tuple[TestClient, TestClient]) -> None:
    owner, _bob = clients
    bob_id = _bob_id(owner)
    assert _count(owner, Account) == 1
    wrong = owner.post(f"/admin/users/{bob_id}/delete", data={"confirm": "0912"})
    assert wrong.status_code == 400 and _count(owner, User) == 2
    owner.post(f"/admin/users/{bob_id}/delete", data={"confirm": OTHER})
    assert _count(owner, User) == 1 and _count(owner, Account) == 0


def test_owner_cannot_disable_or_delete_self(clients: tuple[TestClient, TestClient]) -> None:
    owner, _bob = clients
    with owner.app.state.session_factory() as s:  # type: ignore[attr-defined]
        me = s.scalars(select(User.id).where(User.phone == PHONE)).one()
    assert owner.post(f"/admin/users/{me}/disable").status_code == 400
    assert owner.post(f"/admin/users/{me}/delete", data={"confirm": PHONE}).status_code == 400


def test_last_seen_is_recorded(clients: tuple[TestClient, TestClient]) -> None:
    owner, bob = clients
    bob.get("/")
    with owner.app.state.session_factory() as s:  # type: ignore[attr-defined]
        user = s.get(User, _bob_id(owner))
        assert user is not None and user.last_seen_at is not None
