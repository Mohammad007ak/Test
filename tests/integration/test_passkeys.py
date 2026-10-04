"""ورود با چهره (WebAuthn): گزینه‌ها، ثبت کلید، ورود بی‌رمز، جداسازی کاربران و حذف.

امضای واقعی دستگاه این‌جا ساختنی نیست؛ تابع‌های بررسی کتابخانه با نتیجه ساختگی جایگزین
می‌شوند و بقیه مسیر (چالش در نشست، ذخیره کلید، ورود، شمارنده امضا) واقعی است.
"""

import base64
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.config import Settings
from app.main import create_app
from app.models import Passkey
from app.web import passkey_routes
from tests.integration.conftest import FakeSender, register

CRED = b"credential-123"
CRED_ID = base64.urlsafe_b64encode(CRED).decode().rstrip("=")


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    seen: dict[str, object] = {}

    def fake_register(**kw: object) -> SimpleNamespace:
        seen["reg"] = kw
        if kw["credential"] == {"bad": True}:
            raise passkey_routes.InvalidRegistrationResponse("bad")
        return SimpleNamespace(credential_id=CRED, credential_public_key=b"PUBKEY", sign_count=0)

    def fake_auth(**kw: object) -> SimpleNamespace:
        seen["auth"] = kw
        return SimpleNamespace(new_sign_count=5)

    monkeypatch.setattr(passkey_routes, "verify_registration_response", fake_register)
    monkeypatch.setattr(passkey_routes, "verify_authentication_response", fake_auth)
    settings = Settings(database_url=f"sqlite:///{tmp_path / 't.db'}", secret_key="t",
                        public_url="https://getvazir.ir")
    with TestClient(create_app(settings, price_sources=[], schedule=False,
                               otp_sender=FakeSender()), base_url="https://getvazir.ir") as c:
        c.seen = seen  # type: ignore[attr-defined]
        yield c


def add_key(client: TestClient) -> None:
    options = client.post("/passkeys/register/options").json()
    assert options["rp"]["id"] == "getvazir.ir"
    assert options["authenticatorSelection"]["residentKey"] == "required"
    assert options["authenticatorSelection"]["userVerification"] == "required"
    response = client.post("/passkeys/register/verify", json={"id": CRED_ID})
    assert response.json() == {"ok": True}


def test_register_then_login_without_password(client: TestClient) -> None:
    register(client)
    add_key(client)
    reg = client.seen["reg"]  # type: ignore[attr-defined]
    assert reg["expected_origin"] == "https://getvazir.ir" and reg["require_user_verification"]
    page = client.get("/passkeys").text
    assert "فعال از" in page
    client.post("/logout")
    assert client.get("/more", follow_redirects=False).status_code == 303

    options = client.post("/passkeys/login/options").json()
    assert options["rpId"] == "getvazir.ir" and options["userVerification"] == "required"
    result = client.post("/passkeys/login/verify", json={"id": CRED_ID})
    assert result.json() == {"ok": True, "next": "/"}
    assert client.get("/more", follow_redirects=False).status_code == 200
    auth = client.seen["auth"]  # type: ignore[attr-defined]
    assert auth["credential_public_key"] == b"PUBKEY" and auth["credential_current_sign_count"] == 0
    with client.app.state.session_factory() as s:  # type: ignore[attr-defined]
        key = s.scalars(select(Passkey)).one()
        assert key.sign_count == 5 and key.last_used_at is not None


def test_challenge_is_single_use_and_required(client: TestClient) -> None:
    assert client.post("/passkeys/login/verify", json={"id": CRED_ID}).status_code == 400
    client.post("/passkeys/login/options")
    assert client.post("/passkeys/login/verify", json={"id": "unknown"}).status_code == 404
    assert client.post("/passkeys/login/verify", json={"id": CRED_ID}).status_code == 400


def test_bad_registration_is_rejected(client: TestClient) -> None:
    register(client)
    client.post("/passkeys/register/options")
    response = client.post("/passkeys/register/verify", json={"bad": True})
    assert response.status_code == 400 and response.json()["ok"] is False


def test_registration_needs_login_and_keys_are_private(client: TestClient) -> None:
    assert client.post("/passkeys/register/options", follow_redirects=False).status_code == 303
    register(client)
    add_key(client)
    client.post("/logout")
    register(client, "09122222222")
    assert "فعال از" not in client.get("/passkeys").text
    with client.app.state.session_factory() as s:  # type: ignore[attr-defined]
        key_id = s.scalars(select(Passkey.id)).one()
    assert client.post(f"/passkeys/{key_id}/delete").status_code == 404


def test_delete_and_login_page_button(client: TestClient) -> None:
    assert "data-passkey-login" in client.get("/login").text
    register(client)
    add_key(client)
    with client.app.state.session_factory() as s:  # type: ignore[attr-defined]
        key_id = s.scalars(select(Passkey.id)).one()
    client.post(f"/passkeys/{key_id}/delete")
    with client.app.state.session_factory() as s:  # type: ignore[attr-defined]
        assert s.scalars(select(Passkey)).all() == []


def test_other_domain_uses_its_own_origin(client: TestClient) -> None:
    register(client)
    options = client.post("/passkeys/register/options",
                          headers={"host": "dppfm.darkube.ir", "x-forwarded-proto": "https"}).json()
    assert options["rp"]["id"] == "dppfm.darkube.ir"
    client.post("/passkeys/register/verify", json={"id": CRED_ID},
                headers={"host": "dppfm.darkube.ir", "x-forwarded-proto": "https"})
    assert client.seen["reg"]["expected_origin"] == "https://dppfm.darkube.ir"  # type: ignore[attr-defined]
