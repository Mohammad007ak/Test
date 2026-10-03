from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.config import Settings
from app.db import user_session
from app.main import create_app
from app.models import Asset, User, utcnow
from tests.integration.conftest import PASSWORD, PHONE, FakeSender, last_code, register

OTHER = "09122222222"


def make_app(tmp_path: Path, **settings: object):  # type: ignore[no-untyped-def]
    config = Settings(database_url=f"sqlite:///{tmp_path / 't.db'}", secret_key="t",
                      **settings)  # type: ignore[arg-type]
    return create_app(config, price_sources=[], schedule=False, otp_sender=FakeSender())


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    with TestClient(make_app(tmp_path)) as c:
        yield c


class TestSignup:
    def test_signup_logs_in_and_phone_is_username(self, client: TestClient) -> None:
        assert client.get("/", follow_redirects=False).headers["location"] == "/login"
        register(client, "۰۹۱۲ ۱۱۱ ۱۱۱۱")  # ارقام فارسی و فاصله
        assert client.get("/").status_code == 200
        with client.app.state.session_factory() as s:  # type: ignore[attr-defined]
            assert s.scalars(select(User.phone)).all() == [PHONE]

    def test_invalid_phone(self, client: TestClient) -> None:
        assert client.post("/signup", data={"phone": "021234"}).status_code == 400

    def test_existing_phone_is_told_to_log_in(self, client: TestClient) -> None:
        register(client)
        client.post("/logout")
        response = client.post("/signup", data={"phone": PHONE})
        assert response.status_code == 409 and "/login" in response.text

    def test_wrong_code_and_password_rules(self, client: TestClient) -> None:
        client.post("/signup", data={"phone": PHONE})
        code = last_code(client, PHONE)
        short = client.post("/verify", data={"code": code, "password": "short",
                                             "password_repeat": "short"})
        assert short.status_code == 400
        wrong = "000000" if code != "000000" else "111111"
        bad = client.post("/verify", data={"code": wrong, "password": PASSWORD,
                                           "password_repeat": PASSWORD})
        assert bad.status_code == 400
        assert client.get("/", follow_redirects=False).status_code == 303  # هنوز وارد نشده

    def test_verify_without_pending_phone_goes_back(self, client: TestClient) -> None:
        assert client.get("/verify", follow_redirects=False).headers["location"] == "/signup"

    def test_resend_respects_cooldown(self, client: TestClient) -> None:
        client.post("/signup", data={"phone": PHONE})
        assert client.post("/verify/resend").status_code == 429

    def test_allowlist(self, tmp_path: Path) -> None:
        with TestClient(make_app(tmp_path, signup_allowlist="09121111111")) as c:
            assert c.post("/signup", data={"phone": OTHER}).status_code == 403
            register(c, PHONE)


class TestLogin:
    def test_login_with_phone_and_password(self, client: TestClient) -> None:
        register(client)
        client.post("/logout")
        assert client.post("/login", data={"phone": PHONE, "password": "nope-nope"}
                           ).status_code == 401
        assert client.post("/login", data={"phone": OTHER, "password": PASSWORD}
                           ).status_code == 401
        ok = client.post("/login", data={"phone": "+989121111111", "password": PASSWORD},
                         follow_redirects=False)
        assert ok.headers["location"] == "/"

    def test_locked_after_repeated_failures(self, client: TestClient) -> None:
        register(client)
        client.post("/logout")
        for _ in range(5):
            client.post("/login", data={"phone": PHONE, "password": "nope-nope"})
        locked = client.post("/login", data={"phone": PHONE, "password": PASSWORD})
        assert locked.status_code == 429


class TestReset:
    def test_forgot_password_sets_new_one_and_logs_out_other_devices(
            self, tmp_path: Path) -> None:
        app = make_app(tmp_path)
        with TestClient(app) as phone_a, TestClient(app) as phone_b:
            register(phone_a)
            phone_b.post("/login", data={"phone": PHONE, "password": PASSWORD})
            assert phone_b.get("/", follow_redirects=False).status_code == 200
            phone_b.post("/logout")
            later = utcnow() + timedelta(minutes=2)  # فاصله لازم بین دو پیامک به یک شماره
            app.state.otp.clock = lambda: later
            phone_b.post("/forgot", data={"phone": PHONE})
            new = "brand-new-pass"
            response = phone_b.post("/verify", data={
                "code": last_code(phone_b, PHONE), "password": new, "password_repeat": new},
                follow_redirects=False)
            assert response.headers["location"] == "/"
            # دستگاه اول با رمز قدیم وارد شده بود؛ نشستش باطل شد
            assert phone_a.get("/", follow_redirects=False).status_code == 303
            assert phone_a.post("/login", data={"phone": PHONE, "password": new},
                                follow_redirects=False).status_code == 303

    def test_unknown_phone_gets_same_page_but_no_sms(self, client: TestClient) -> None:
        response = client.post("/forgot", data={"phone": OTHER}, follow_redirects=False)
        assert response.headers["location"] == "/verify"
        assert OTHER not in client.app.state.otp_sender.codes  # type: ignore[attr-defined]


class TestIsolation:
    def test_users_never_see_each_other(self, tmp_path: Path) -> None:
        app = make_app(tmp_path)
        with TestClient(app) as alice, TestClient(app) as bob:
            register(alice, PHONE)
            register(bob, OTHER)
            alice.post("/assets", data={"kind": "car", "name": "ماشین آلیس",
                                        "manual_value_toman": "900,000,000"})
            alice.post("/spending", data={"amount_toman": "100", "category": "food",
                                          "description": "قهوه آلیس"})
            alice.post("/prices", data={"price:usd": "999,999"})
            with app.state.session_factory() as s:
                asset_id = s.scalars(select(Asset.id)).one()
            for url in ("/", "/assets", "/spending", "/prices", "/export.json"):
                page = bob.get(url).text
                assert "آلیس" not in page and "۹۹۹٬۹۹۹" not in page, url
            assert bob.get(f"/assets/{asset_id}/edit").status_code == 404
            bob.post(f"/assets/{asset_id}/delete")
            assert bob.post(f"/assets/{asset_id}", data={
                "kind": "car", "name": "دزد", "manual_value_toman": "1"}).status_code == 404
            with user_session(app.state.session_factory(), 1) as s:
                assert s.get(Asset, asset_id).name == "ماشین آلیس"
            assert "ماشین آلیس" in alice.get("/assets").text

    def test_sms_token_is_per_user(self, tmp_path: Path) -> None:
        app = make_app(tmp_path)
        with TestClient(app) as alice, TestClient(app) as bob:
            register(alice, PHONE)
            register(bob, OTHER)
            import re
            token = re.search(r'class="token">([^<]+)<', alice.get("/sms").text).group(1)
            assert token not in bob.get("/sms").text
            sms = "بانک ملت\nبرداشت 2,500,000 ریال"
            ok = bob.post("/api/sms", json={"text": sms}, headers={"X-Ingest-Token": token})
            assert ok.status_code == 200
            assert "برداشت" in alice.get("/sms").text and "برداشت" not in bob.get("/sms").text


class TestOwnerClaim:
    def test_owner_phone_takes_over_single_user_data(self, tmp_path: Path) -> None:
        app = make_app(tmp_path, owner_phone="09121111111")
        with app.state.session_factory() as s:
            s.add(User(id=7, phone=None, password_hash="old"))
            s.flush()
            s.add(Asset(kind="car", name="ماشین قدیمی", manual_value_toman=5, user_id=7))
            s.commit()
        with TestClient(app) as stranger, TestClient(app) as owner:
            register(stranger, OTHER)
            assert "ماشین قدیمی" not in stranger.get("/assets").text
            register(owner, PHONE)
            assert "ماشین قدیمی" in owner.get("/assets").text
