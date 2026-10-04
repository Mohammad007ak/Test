"""دنگ: گروه، خرج، سهم من در خرج‌ها، تسویه، لینک دوستان و جداسازی کاربران."""

import re
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.config import Settings
from app.main import create_app
from app.models import SplitExpense, SplitGroup, SplitMember, Transaction
from tests.integration.conftest import FakeSender, register


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    settings = Settings(database_url=f"sqlite:///{tmp_path / 't.db'}", secret_key="t",
                        public_url="https://getvazir.ir")
    with TestClient(create_app(settings, price_sources=[], schedule=False,
                               otp_sender=FakeSender())) as c:
        register(c)
        yield c


def _db(client: TestClient):  # type: ignore[no-untyped-def]
    return client.app.state.session_factory()  # type: ignore[attr-defined]


def _group(client: TestClient) -> tuple[int, dict[str, int]]:
    response = client.post("/dong", data={"name": "سفر شمال", "me": "من",
                                          "members": "علی\nسارا\nرضا"}, follow_redirects=False)
    assert response.status_code == 303
    with _db(client) as db:
        group = db.scalars(select(SplitGroup)).one()
        members = {m.name: m.id for m in db.scalars(select(SplitMember))}
    return group.id, members


def test_create_group_validates_and_lists(client: TestClient) -> None:
    assert client.post("/dong", data={"name": "", "members": ""}).status_code == 400
    group_id, members = _group(client)
    assert set(members) == {"من", "علی", "سارا", "رضا"}
    page = client.get("/dong").text
    assert "سفر شمال" in page and f'href="/dong/{group_id}"' in page


def test_friend_pays_my_share_becomes_my_expense(client: TestClient) -> None:
    group_id, m = _group(client)
    response = client.post(f"/dong/{group_id}/expenses", data={
        "title": "شام", "amount": "۱٬۲۰۰٬۰۰۰", "payer": str(m["علی"]), "mode": "equal",
        "who": [str(x) for x in m.values()], "category": "food"}, follow_redirects=False)
    assert response.status_code == 303
    with _db(client) as db:
        tx = db.scalars(select(Transaction)).one()
        assert (tx.direction, tx.amount_toman, tx.category) == ("out", 300_000, "food")
        assert db.scalars(select(SplitExpense)).one().transaction_id == tx.id
    page = client.get(f"/dong/{group_id}").text
    assert "بدهی تو" in page and "من به علی" in page


def test_i_pay_no_double_counting_and_settle(client: TestClient) -> None:
    group_id, m = _group(client)
    client.post(f"/dong/{group_id}/expenses", data={
        "title": "ویلا", "amount": "۴٬۰۰۰٬۰۰۰", "payer": str(m["من"]), "mode": "equal",
        "who": [str(x) for x in m.values()]})
    with _db(client) as db:
        assert db.scalars(select(Transaction)).all() == []  # خرج کامل از پیامک بانک می‌آید
    assert "طلب تو" in client.get(f"/dong/{group_id}").text
    client.post(f"/dong/{group_id}/settle", data={"payer": m["علی"], "payee": m["من"],
                                                 "amount": "1000000"})
    page = client.get(f"/dong/{group_id}").text
    assert "علی به من" not in page and "سارا به من" in page


def test_exact_split_must_match_total(client: TestClient) -> None:
    group_id, m = _group(client)
    bad = client.post(f"/dong/{group_id}/expenses", data={
        "title": "خرید", "amount": "۱۰۰٬۰۰۰", "payer": str(m["علی"]), "mode": "exact",
        f"share_{m['من']}": "۷۰٬۰۰۰", f"share_{m['علی']}": "۲۰٬۰۰۰"})
    assert bad.status_code == 400 and "جمع سهم‌ها" in bad.text
    ok = client.post(f"/dong/{group_id}/expenses", data={
        "title": "خرید", "amount": "۱۰۰٬۰۰۰", "payer": str(m["علی"]), "mode": "exact",
        f"share_{m['من']}": "۷۰٬۰۰۰", f"share_{m['علی']}": "۳۰٬۰۰۰"}, follow_redirects=False)
    assert ok.status_code == 303
    with _db(client) as db:
        assert db.scalars(select(Transaction)).one().amount_toman == 70_000


def test_deleting_expense_and_group_removes_my_share_transaction(client: TestClient) -> None:
    group_id, m = _group(client)
    for _ in range(2):
        client.post(f"/dong/{group_id}/expenses", data={
            "title": "بنزین", "amount": "400000", "payer": str(m["رضا"]), "mode": "equal",
            "who": [str(m["من"]), str(m["رضا"])]})
    with _db(client) as db:
        first = db.scalars(select(SplitExpense)).first()
        assert len(db.scalars(select(Transaction)).all()) == 2
    client.post(f"/dong/{group_id}/expenses/{first.id}/delete")
    with _db(client) as db:
        assert len(db.scalars(select(Transaction)).all()) == 1
    client.post(f"/dong/{group_id}/delete")
    with _db(client) as db:
        assert db.scalars(select(Transaction)).all() == []
        assert db.scalars(select(SplitMember)).all() == []


def test_public_link_is_viewable_without_login_and_not_indexed(client: TestClient) -> None:
    group_id, m = _group(client)
    client.post(f"/dong/{group_id}/expenses", data={
        "title": "شام", "amount": "800000", "payer": str(m["سارا"]), "mode": "equal",
        "who": [str(x) for x in m.values()]})
    token = re.search(r"/dong/s/([\w-]+)", client.get(f"/dong/{group_id}").text).group(1)
    client.post("/logout")
    client.cookies.clear()
    public = client.get(f"/dong/s/{token}")
    assert public.status_code == 200 and "سفر شمال" in public.text and "شام" in public.text
    assert "noindex" in public.text and "پرداخت شد" not in public.text
    assert client.get("/dong/s/not-a-real-token-123").status_code == 404


def test_other_user_cannot_see_or_change_group(client: TestClient) -> None:
    group_id, m = _group(client)
    client.post("/logout")
    client.cookies.clear()
    register(client, phone="09122222222")
    assert client.get(f"/dong/{group_id}").status_code == 404
    response = client.post(f"/dong/{group_id}/expenses", data={
        "title": "x", "amount": "1000", "payer": str(m["علی"]), "who": [str(m["علی"])]})
    assert response.status_code == 404
    assert f"href=\"/dong/{group_id}\"" not in client.get("/dong").text


def test_dong_string_keys_do_not_shadow_dict_methods() -> None:
    """کلیدی مثل copy در Jinja به متد dict می‌رسد، نه به متن."""
    from app.web import strings as s

    assert not [k for k in s.DONG if k in dir(dict)]
