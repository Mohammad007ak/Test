"""ورود با چهره یا اثر انگشت (Passkey / WebAuthn).

گوشی یا کامپیوتر یک جفت کلید می‌سازد؛ کلید خصوصی و داده زیستی (چهره، اثر انگشت) هرگز از
دستگاه بیرون نمی‌آید و سرور فقط کلید عمومی را نگه می‌دارد و امضای هر ورود را با آن چک می‌کند.
Passkeyها «قابل کشف» (discoverable) ساخته می‌شوند تا ورود بدون تایپ شماره ممکن باشد.
"""

import json
from typing import Any
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from sqlalchemy import select
from webauthn import (
    generate_authentication_options,
    generate_registration_options,
    options_to_json,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers import base64url_to_bytes, bytes_to_base64url
from webauthn.helpers.exceptions import InvalidAuthenticationResponse, InvalidRegistrationResponse
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from app.models import Passkey, User, utcnow
from app.web import auth
from app.web import strings as s
from app.web.common import Db, LoggedIn, done, page, site_url

REG_CHALLENGE = "pk_reg_challenge"
AUTH_CHALLENGE = "pk_auth_challenge"
MAX_NAME = 60


def _rp(request: Request) -> tuple[str, str]:
    """(rp_id، origin): دامنه‌ای که کاربر با آن آمده؛ passkey به همین دامنه بسته است.

    اگر همان FINASSIST_PUBLIC_URL باشد آدرس دقیقش استفاده می‌شود؛ وگرنه (مثلاً آدرس قدیمی
    darkube) از سرآیندهای درخواست، با https پشت پراکسی.
    """
    public = site_url(request)
    host = request.url.hostname or "localhost"
    if urlsplit(public).hostname == host:
        return host, public
    scheme = request.headers.get("x-forwarded-proto", request.url.scheme).split(",")[0].strip()
    port = request.url.port
    netloc = host if port in (None, 80, 443) else f"{host}:{port}"
    return host, f"{scheme}://{netloc}"


def _device_name(request: Request) -> str:
    agent = request.headers.get("user-agent", "")
    for marker, name in (("iPhone", "آیفون"), ("iPad", "آی‌پد"), ("Android", "اندروید"),
                         ("Macintosh", "مک"), ("Windows", "ویندوز")):
        if marker in agent:
            return name
    return s.T["passkey_device"]


def register_passkey_routes(app: FastAPI) -> None:
    def failed(message: str, status: int = 400) -> JSONResponse:
        return JSONResponse({"ok": False, "error": message}, status_code=status)

    @app.get("/passkeys", response_class=HTMLResponse, dependencies=[LoggedIn])
    def passkeys_page(request: Request, db: Db) -> Response:
        keys = db.scalars(select(Passkey).order_by(Passkey.created_at)).all()
        return page(request, "passkeys.html", {"active": "passkeys", "keys": keys})

    @app.post("/passkeys/register/options", dependencies=[LoggedIn])
    def register_options(request: Request, db: Db) -> Response:
        user = db.get(User, request.state.user_id)
        if user is None or not user.phone:
            raise HTTPException(403)
        rp_id, _origin = _rp(request)
        existing = db.scalars(select(Passkey.credential_id)).all()
        options = generate_registration_options(
            rp_id=rp_id, rp_name=s.APP_NAME, user_id=str(user.id).encode(),
            user_name=user.phone, user_display_name=f"{s.APP_NAME} · {user.phone}",
            authenticator_selection=AuthenticatorSelectionCriteria(
                resident_key=ResidentKeyRequirement.REQUIRED,
                user_verification=UserVerificationRequirement.REQUIRED),
            exclude_credentials=[PublicKeyCredentialDescriptor(id=base64url_to_bytes(c))
                                 for c in existing])
        request.session[REG_CHALLENGE] = bytes_to_base64url(options.challenge)
        return Response(options_to_json(options), media_type="application/json")

    @app.post("/passkeys/register/verify", dependencies=[LoggedIn])
    async def register_verify(request: Request, db: Db) -> Response:
        challenge = request.session.pop(REG_CHALLENGE, None)
        if not challenge:
            return failed(s.T["passkey_expired"])
        rp_id, origin = _rp(request)
        try:
            body: dict[str, Any] = json.loads(await request.body())
            verified = verify_registration_response(
                credential=body, expected_challenge=base64url_to_bytes(challenge),
                expected_rp_id=rp_id, expected_origin=origin, require_user_verification=True)
        except (InvalidRegistrationResponse, ValueError, TypeError):
            return failed(s.T["passkey_failed"])
        db.add(Passkey(credential_id=bytes_to_base64url(verified.credential_id),
                       public_key=verified.credential_public_key,
                       sign_count=verified.sign_count,
                       name=_device_name(request)[:MAX_NAME]))
        db.commit()
        request.session["toast"] = s.T["passkey_added"]
        return JSONResponse({"ok": True})

    @app.post("/passkeys/login/options")
    def login_options(request: Request) -> Response:
        rp_id, _origin = _rp(request)
        options = generate_authentication_options(
            rp_id=rp_id, user_verification=UserVerificationRequirement.REQUIRED)
        request.session[AUTH_CHALLENGE] = bytes_to_base64url(options.challenge)
        return Response(options_to_json(options), media_type="application/json")

    @app.post("/passkeys/login/verify")
    async def login_verify(request: Request) -> Response:
        challenge = request.session.pop(AUTH_CHALLENGE, None)
        if not challenge:
            return failed(s.T["passkey_expired"])
        rp_id, origin = _rp(request)
        try:
            body: dict[str, Any] = json.loads(await request.body())
            credential_id = str(body.get("id", ""))
        except (ValueError, AttributeError):
            return failed(s.T["passkey_failed"])
        # هنوز کسی وارد نشده: جست‌وجوی سیستمی بر اساس شناسه همان کلید
        with request.app.state.session_factory() as system:
            key = system.scalars(select(Passkey).where(
                Passkey.credential_id == credential_id)).first()
            if key is None:
                return failed(s.T["passkey_unknown"], 404)
            try:
                verified = verify_authentication_response(
                    credential=body, expected_challenge=base64url_to_bytes(challenge),
                    expected_rp_id=rp_id, expected_origin=origin,
                    credential_public_key=key.public_key,
                    credential_current_sign_count=key.sign_count,
                    require_user_verification=True)
            except (InvalidAuthenticationResponse, ValueError, TypeError):
                return failed(s.T["passkey_failed"])
            user = system.get(User, key.user_id)
            if user is None or not user.phone:
                return failed(s.T["passkey_unknown"], 404)
            key.sign_count = verified.new_sign_count
            key.last_used_at = utcnow()
            system.commit()
            auth.log_in(request, user)
        return JSONResponse({"ok": True, "next": "/"})

    @app.post("/passkeys/{key_id}/delete", dependencies=[LoggedIn])
    def delete(request: Request, key_id: int, db: Db) -> Response:
        key = db.get(Passkey, key_id)
        if key is None:
            raise HTTPException(404)
        db.delete(key)
        db.commit()
        return done(request, "/passkeys", s.T["passkey_removed"])
