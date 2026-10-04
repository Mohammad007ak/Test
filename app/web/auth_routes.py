"""ورود با موبایل و رمز؛ ثبت‌نام و بازیابی رمز با کد پیامکی.

تا وقتی پنل پیامک وصل نیست (sms_verification=False)، ثبت‌نام فقط با شماره و رمز است و
بازیابی رمز بسته است؛ شماره صاحب برنامه هم از این راه ثبت نمی‌شود تا داده قبلی‌اش امن بماند.
"""

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, Response
from sqlalchemy import select

from app.config import Settings
from app.domain.normalize import normalize_digits
from app.domain.phone import mask_phone, normalize_phone
from app.models import User
from app.otp import OtpError, OtpService
from app.web import auth
from app.web import strings as s
from app.web.common import Db, page, read_form, redirect

PURPOSES = ("signup", "reset")


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else ""


def _allowlist(settings: Settings) -> set[str]:
    phones = set()
    for raw in settings.signup_allowlist.split(","):
        try:
            phones.add(normalize_phone(raw))
        except ValueError:
            continue
    return phones


def register_auth_routes(app: FastAPI, settings: Settings, otp: OtpService,
                         sms_verification: bool = True) -> None:
    throttle = auth.LoginThrottle()
    signups = auth.LoginThrottle(max_failures=5, window_seconds=60 * 60)  # حساب تازه بر IP
    allowlist = _allowlist(settings)
    owner = settings.owner_phone and normalize_phone(settings.owner_phone)

    def may_sign_up(phone: str) -> bool:
        return not allowlist or phone in allowlist or phone == owner

    def phone_page(request: Request, purpose: str, error: str = "", phone: str = "",
                   status: int = 200) -> Response:
        return page(request, "phone_form.html", {
            "purpose": purpose, "error": error, "phone": phone, "auth_page": True,
            "direct": not sms_verification}, status)

    def verify_page(request: Request, error: str = "", status: int = 200) -> Response:
        if not sms_verification:
            return redirect("/signup")
        phone, purpose = request.session.get("otp_phone"), request.session.get("otp_purpose")
        if not phone or purpose not in PURPOSES:
            return redirect("/signup")
        return page(request, "verify.html", {
            "purpose": purpose, "masked": mask_phone(phone), "error": error,
            "auth_page": True}, status)

    # ---------- ورود ----------

    @app.get("/login", response_class=HTMLResponse)
    def login_form(request: Request) -> Response:
        return page(request, "login.html", {"auth_page": True})

    @app.post("/login", response_class=HTMLResponse)
    async def login(request: Request, db: Db) -> Response:
        data = await read_form(request)
        raw_phone = data.get("phone", "")
        try:
            phone = normalize_phone(raw_phone)
        except ValueError:
            return page(request, "login.html", {"error": s.T["phone_invalid"], "phone": raw_phone,
                                                "auth_page": True}, 400)
        keys = (f"ip:{_client_ip(request)}", f"phone:{phone}")
        if not all(throttle.allowed(key) for key in keys):
            return page(request, "login.html", {"error": s.T["login_locked"], "phone": phone,
                                                "auth_page": True}, 429)
        user = auth.authenticate(db, phone, data.get("password", ""))
        if user is None:
            for key in keys:
                throttle.failed(key)
            return page(request, "login.html", {"error": s.T["wrong_login"], "phone": phone,
                                                "auth_page": True}, 401)
        for key in keys:
            throttle.succeeded(key)
        auth.log_in(request, user)
        return redirect("/")

    @app.post("/logout")
    def logout(request: Request) -> Response:
        request.session.clear()
        return redirect("/login")

    # ---------- ثبت‌نام و فراموشی رمز: شماره ← کد ----------

    async def start(request: Request, db: Db, purpose: str) -> Response:
        data = await read_form(request)
        raw_phone = data.get("phone", "")
        try:
            phone = normalize_phone(raw_phone)
        except ValueError:
            return phone_page(request, purpose, s.T["phone_invalid"], raw_phone, 400)
        exists = auth.user_by_phone(db, phone) is not None
        if purpose == "signup":
            if exists:
                return phone_page(request, purpose, s.T["phone_taken"], phone, 409)
            if not may_sign_up(phone):
                return phone_page(request, purpose, s.T["signup_closed"], phone, 403)
        request.session["otp_phone"], request.session["otp_purpose"] = phone, purpose
        if purpose == "reset" and not exists:
            # برای شماره ناموجود پیامکی خرج نمی‌شود؛ پاسخ همان است تا عضویت کسی لو نرود
            return redirect("/verify")
        try:
            otp.issue(db, phone, purpose, _client_ip(request))
        except OtpError as exc:
            return phone_page(request, purpose, str(exc), phone, 429)
        return redirect("/verify")

    @app.get("/signup", response_class=HTMLResponse)
    def signup_form(request: Request) -> Response:
        return phone_page(request, "signup")

    @app.post("/signup", response_class=HTMLResponse)
    async def signup(request: Request, db: Db) -> Response:
        if not sms_verification:
            return await direct_signup(request, db)
        return await start(request, db, "signup")

    async def direct_signup(request: Request, db: Db) -> Response:
        """ثبت‌نام بدون پیامک: شماره + رمز، بلافاصله ورود."""
        data = await read_form(request)
        raw_phone = data.get("phone", "")
        try:
            phone = normalize_phone(raw_phone)
        except ValueError:
            return phone_page(request, "signup", s.T["phone_invalid"], raw_phone, 400)
        if auth.user_by_phone(db, phone) is not None:
            return phone_page(request, "signup", s.T["phone_taken"], phone, 409)
        if phone == owner or not may_sign_up(phone):
            return phone_page(request, "signup", s.T["signup_closed"], phone, 403)
        password = data.get("password", "")
        if len(password) < auth.MIN_PASSWORD_LENGTH:
            return phone_page(request, "signup", s.T["password_short"], phone, 400)
        if password != data.get("password_repeat"):
            return phone_page(request, "signup", s.T["password_mismatch"], phone, 400)
        ip_key = f"ip:{_client_ip(request)}"
        if not signups.allowed(ip_key):
            return phone_page(request, "signup", s.T["signup_throttled"], phone, 429)
        signups.failed(ip_key)
        user = User(phone=phone, password_hash=auth.hash_password(password), session_version=1)
        db.add(user)
        db.commit()
        auth.log_in(request, user)
        request.session["toast"] = s.T["welcome"]
        return redirect("/")

    @app.get("/forgot", response_class=HTMLResponse)
    def forgot_form(request: Request) -> Response:
        return phone_page(request, "reset")

    @app.post("/forgot", response_class=HTMLResponse)
    async def forgot(request: Request, db: Db) -> Response:
        if not sms_verification:
            return phone_page(request, "reset", status=404)
        return await start(request, db, "reset")

    # ---------- کد + رمز ----------

    @app.get("/verify", response_class=HTMLResponse)
    def verify_form(request: Request) -> Response:
        return verify_page(request)

    @app.post("/verify/resend", response_class=HTMLResponse)
    def resend(request: Request, db: Db) -> Response:
        if not sms_verification:
            return redirect("/signup")
        phone, purpose = request.session.get("otp_phone"), request.session.get("otp_purpose")
        if not phone or purpose not in PURPOSES:
            return redirect("/signup")
        if purpose == "signup" or auth.user_by_phone(db, phone) is not None:
            try:
                otp.issue(db, phone, purpose, _client_ip(request))
            except OtpError as exc:
                return verify_page(request, str(exc), 429)
        request.session["toast"] = s.T["code_resent"]
        return redirect("/verify")

    @app.post("/verify", response_class=HTMLResponse)
    async def verify(request: Request, db: Db) -> Response:
        if not sms_verification:
            return redirect("/signup")
        phone, purpose = request.session.get("otp_phone"), request.session.get("otp_purpose")
        if not phone or purpose not in PURPOSES:
            return redirect("/signup")
        data = await read_form(request)
        password = data.get("password", "")
        if len(password) < auth.MIN_PASSWORD_LENGTH:
            return verify_page(request, s.T["password_short"], 400)
        if password != data.get("password_repeat"):
            return verify_page(request, s.T["password_mismatch"], 400)
        if not otp.verify(db, phone, purpose, normalize_digits(data.get("code", ""))):
            return verify_page(request, s.T["code_wrong"], 400)

        user = auth.user_by_phone(db, phone)
        if purpose == "signup":
            if user is not None:
                return verify_page(request, s.T["phone_taken"], 409)
            legacy = (db.scalars(select(User).where(User.phone.is_(None))).first()
                      if phone == owner else None)
            user = legacy or User()
            user.phone = phone
            db.add(user)
        elif user is None:
            return verify_page(request, s.T["code_wrong"], 400)
        user.password_hash = auth.hash_password(password)
        user.session_version = (user.session_version or 0) + 1  # نشست‌های قبلی باطل
        db.commit()
        auth.log_in(request, user)
        request.session["toast"] = s.T["welcome" if purpose == "signup" else "password_changed"]
        return redirect("/")
