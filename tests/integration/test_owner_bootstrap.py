from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.config import Settings
from app.main import create_app
from app.models import Asset, User
from tests.integration.conftest import FakeSender

PHONE = "09121111111"


def make(tmp_path: Path, **kw: str):  # type: ignore[no-untyped-def]
    settings = Settings(database_url=f"sqlite:///{tmp_path / 't.db'}", secret_key="t",
                        owner_phone=PHONE, **kw)  # type: ignore[arg-type]
    return create_app(settings, price_sources=[], schedule=False, otp_sender=FakeSender())


def login(client: TestClient, password: str) -> int:
    return client.post("/login", data={"phone": PHONE, "password": password},
                       follow_redirects=False).status_code


def test_owner_account_created_from_env(tmp_path: Path) -> None:
    with TestClient(make(tmp_path, owner_password="owner-pass-1")) as c:
        assert login(c, "owner-pass-1") == 303
        assert c.get("/").status_code == 200


def test_env_password_claims_single_user_data(tmp_path: Path) -> None:
    app = make(tmp_path)
    with app.state.session_factory() as s:
        s.add(User(id=5, phone=None, password_hash="old"))
        s.flush()
        s.add(Asset(kind="car", name="ماشین قدیمی", manual_value_toman=5, user_id=5))
        s.commit()
    with TestClient(make(tmp_path, owner_password="owner-pass-1")) as c:
        assert login(c, "owner-pass-1") == 303
        assert "ماشین قدیمی" in c.get("/assets").text


def test_changing_env_password_takes_effect_on_restart(tmp_path: Path) -> None:
    with TestClient(make(tmp_path, owner_password="first-pass-1")) as c:
        assert login(c, "first-pass-1") == 303
    with TestClient(make(tmp_path, owner_password="second-pass-2")) as c:
        assert login(c, "first-pass-1") == 401
        assert login(c, "second-pass-2") == 303
    app = make(tmp_path, owner_password="second-pass-2")
    with app.state.session_factory() as s:
        assert len(s.scalars(select(User)).all()) == 1


def test_short_env_password_is_ignored(tmp_path: Path) -> None:
    with TestClient(make(tmp_path, owner_password="short")) as c:
        assert login(c, "short") == 401
