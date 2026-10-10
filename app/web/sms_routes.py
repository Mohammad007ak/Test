"""مسیرهای پیامک بانکی: اندپوینت Shortcuts، واردکردن فایل و صف بررسی (SPEC: F6)."""

import hashlib
import secrets
import time
from collections import deque
from collections.abc import Callable
from datetime import datetime, timedelta
from urllib.parse import quote, urlencode

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from starlette.datastructures import UploadFile

from app import services
from app.db import user_session
from app.domain.money import rial_to_toman
from app.domain.phone import mask_phone
from app.models import Account, SmsInbox, User, UserSetting, utcnow
from app.sms.importer import import_text, parse_time
from app.sms.parsers import ParsedSms
from app.sms.pipeline import (
    NEW_TEMPLATE,
    choose_account,
    complete_manually,
    held_reading,
    ignore,
    ingest,
)
from app.sms.text import is_secret
from app.web import forms
from app.web import strings as s
from app.web.common import Db, LoggedIn, done, page, read_form, site_url, wants_fragment
from app.web.forms import Field, FormError

TOKEN_KEY = "sms_ingest_token"
# کد اتصال اپ اندروید: جایگزین لینک intent که فقط در Chrome کار می‌کند
PAIR_CODE_KEY = "sms_pair_code"  # فقط هش کد
PAIR_EXPIRES_KEY = "sms_pair_expires"
PAIR_CODE_TTL = timedelta(minutes=10)
PAIR_RATE_LIMIT = 10  # تلاش در دقیقه برای هر IP
RATE_LIMIT = 60  # درخواست در دقیقه
MAX_TEXT = 2000

REVIEW_FIELDS = [
    Field("bank", "بانک", "select", required=True, options=s.BANKS),
    Field("account_mask", "۴ رقم آخر حساب یا کارت", "text", required=True),
    Field("account_prefix", "ابتدای شماره حساب", "text", hint="اختیاری، مثل 814"),
    Field("direction", "نوع", "select", required=True, options=s.DIRECTIONS, widget="chips"),
    Field("amount", "مبلغ", "rial", required=True, hint="همان عدد پیامک (ریال)"),
    Field("balance_after", "مانده پس از تراکنش", "rial", hint="اگر پیامک مانده دارد"),
    Field("description", "شرح", "text"),
]


def ingest_token(db: Session) -> str:
    """توکن اختصاصی کاربر جاری برای Shortcuts؛ بار اول ساخته می‌شود."""
    token = services.get_user_setting(db, TOKEN_KEY)
    if token is None:
        token = secrets.token_urlsafe(24)
        services.set_user_setting(db, TOKEN_KEY, token)
        db.commit()
    return token


def token_owner(factory: Callable[[], Session], token: str) -> int | None:
    """صاحب توکن (جست‌وجوی سیستمی، چون درخواست Shortcuts نشست ورود ندارد)."""
    if len(token) < 16:
        return None
    with factory() as system:
        row = system.scalars(select(UserSetting).where(
            UserSetting.key == TOKEN_KEY, UserSetting.value == token)).first()
        return row.user_id if row is not None else None


def _code_hash(code: str) -> str:
    return hashlib.sha256(f"pair:{code}".encode()).hexdigest()


def _active_pair_owner(system: Session, digest: str) -> int | None:
    row = system.scalars(select(UserSetting).where(
        UserSetting.key == PAIR_CODE_KEY, UserSetting.value == digest)).first()
    if row is None:
        return None
    expires = system.get(UserSetting, {"key": PAIR_EXPIRES_KEY, "user_id": row.user_id})
    if expires is None or datetime.fromisoformat(expires.value) < utcnow():
        return None
    return row.user_id


def new_pair_code(factory: Callable[[], Session], db: Session) -> str:
    """کد ۶ رقمی یک‌بارمصرف ۱۰ دقیقه‌ای برای کاربر جاری؛ کد قبلی او باطل می‌شود."""
    with factory() as system:
        while True:
            code = f"{secrets.randbelow(10**6):06d}"
            if _active_pair_owner(system, _code_hash(code)) is None:
                break
    services.set_user_setting(db, PAIR_CODE_KEY, _code_hash(code))
    services.set_user_setting(db, PAIR_EXPIRES_KEY, (utcnow() + PAIR_CODE_TTL).isoformat())
    db.commit()
    return code


def pair_code_owner(factory: Callable[[], Session], code: str) -> int | None:
    """صاحب کد (جست‌وجوی سیستمی، چون اپ نشست ورود ندارد)؛ کد مصرف و پاک می‌شود."""
    if not (len(code) == 6 and code.isdigit()):
        return None
    with factory() as system:
        owner = _active_pair_owner(system, _code_hash(code))
        if owner is None:
            return None
        for key in (PAIR_CODE_KEY, PAIR_EXPIRES_KEY):
            row = system.get(UserSetting, {"key": key, "user_id": owner})
            if row is not None:
                system.delete(row)
        system.commit()
        return owner


def sms_endpoint(public_url: str, scheme: str, host: str, port: int | None) -> str:
    """آدرسی که Shortcuts آیفون می‌زند؛ آدرس عمومی سایت اگر تنظیم شده."""
    if public_url:
        return public_url.rstrip("/") + "/api/sms"
    return f"{scheme}://{host}{f':{port}' if port else ''}/api/sms"


def phone_platform(user_agent: str) -> str | None:
    """«ios»، «android» یا None (رایانه و ناشناخته: هر دو راهنما)."""
    agent = user_agent.lower()
    if "iphone" in agent or "ipad" in agent:
        return "ios"
    return "android" if "android" in agent else None


def _public_scheme(request: Request) -> str:
    """پشت پروکسی سرور (HTTPS) آدرس واقعی از هدر X-Forwarded-Proto می‌آید."""
    forwarded = request.headers.get("x-forwarded-proto", "").split(",")[0].strip()
    return forwarded if forwarded in ("http", "https") else request.url.scheme


def queue_count(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(SmsInbox)
                     .where(SmsInbox.parse_status == "failed")) or 0


class _RateLimiter:
    def __init__(self, per_minute: int) -> None:
        self.per_minute = per_minute
        self.hits: deque[float] = deque()

    def allow(self) -> bool:
        now = time.monotonic()
        while self.hits and now - self.hits[0] > 60:
            self.hits.popleft()
        if len(self.hits) >= self.per_minute:
            return False
        self.hits.append(now)
        return True


ANDROID_PACKAGE = "ir.getvazir.app"
ANDROID_UNPAIR = f"intent://unpair#Intent;scheme=vazir;package={ANDROID_PACKAGE};end"


def android_pair_url(token: str, account: str, site: str) -> str:
    """لینک اتصال اپ اندروید (PairActivity)؛ بدون اپ، Chrome به صفحه نصب می‌رود."""
    query = urlencode({"token": token, "account": account})
    # Chrome به این آدرس می‌رود اگر اپ نیست یا قدیمی است (صفحه اتصال از ۱.۱.۰ آمده)
    fallback = quote(f"{site}/install?update=sms", safe="")
    return (f"intent://pair?{query}#Intent;scheme=vazir;package={ANDROID_PACKAGE};"
            f"S.browser_fallback_url={fallback};end")


def register_sms_routes(app: FastAPI) -> None:
    limiters: dict[int, _RateLimiter] = {}

    @app.post("/api/sms")
    async def api_sms(request: Request, db: Db) -> Response:
        """Shortcuts آیفون: بدنه JSON {"text": "...", "received_at": "..."} و هدر توکن."""
        owner = token_owner(request.app.state.session_factory,
                            request.headers.get("X-Ingest-Token", ""))
        if owner is None:
            return JSONResponse({"error": "invalid token"}, status_code=401)
        user_session(db, owner)
        if not limiters.setdefault(owner, _RateLimiter(RATE_LIMIT)).allow():
            return JSONResponse({"error": "rate limited"}, status_code=429)
        try:
            body = await request.json()
            text = str(body["text"]).strip()
        except (ValueError, KeyError, TypeError):
            return JSONResponse({"error": "expected JSON with text"}, status_code=400)
        if not text or len(text) > MAX_TEXT:
            return JSONResponse({"error": "empty or too long"}, status_code=400)
        if is_secret(text):  # رمز پویا و کد تأیید: بدون ذخیره دور ریخته می‌شود
            return JSONResponse({"status": "ignored"})
        received = _received_at(body.get("received_at"))
        result = ingest(db, text, received, llm=request.app.state.llm)
        return JSONResponse({"status": result.status, "id": result.sms.id})

    pair_limiters: dict[str, _RateLimiter] = {}

    @app.post("/api/sms/pair")
    async def api_sms_pair(request: Request, db: Db) -> Response:
        """اپ اندروید با کد ۶ رقمی صفحه پیامک، توکن کاربر را می‌گیرد (بدون مرورگر)."""
        ip = request.client.host if request.client else ""
        if not pair_limiters.setdefault(ip, _RateLimiter(PAIR_RATE_LIMIT)).allow():
            return JSONResponse({"error": "rate limited"}, status_code=429)
        try:
            code = forms.normalize_digits(str((await request.json())["code"])).strip()
        except (ValueError, KeyError, TypeError):
            code = ""
        owner = pair_code_owner(request.app.state.session_factory, code) if code else None
        if owner is None:
            return JSONResponse({"error": "invalid code"}, status_code=400)
        user_session(db, owner)
        token = ingest_token(db)
        user = db.get(User, owner)
        return JSONResponse({"token": token,
                             "account": mask_phone(user.phone) if user and user.phone else ""})

    def _sms_page(request: Request, db: Session, pair_code: str = "") -> Response:
        queue = db.scalars(select(SmsInbox).where(SmsInbox.parse_status == "failed")
                           .order_by(SmsInbox.received_at.desc())).all()
        recent = db.scalars(select(SmsInbox).where(SmsInbox.parse_status != "failed")
                            .order_by(SmsInbox.id.desc()).limit(20)).all()
        token = ingest_token(db)
        user = db.get(User, request.state.user_id)
        return page(request, "sms.html", {
            "active": "sms", "queue": queue, "recent": recent, "token": token,
            "android_pair": android_pair_url(token, mask_phone(user.phone) if user and user.phone
                                             else "", site_url(request)),
            "android_unpair": ANDROID_UNPAIR, "pair_code": pair_code,
            "shortcut_url": getattr(request.app.state, "ios_shortcut_url", ""),
            "platform": phone_platform(request.headers.get("user-agent", "")),
            "endpoint": sms_endpoint(getattr(request.app.state, "public_url", ""),
                                     _public_scheme(request), request.url.hostname or "",
                                     request.url.port),
        })

    @app.get("/sms", response_class=HTMLResponse, dependencies=[LoggedIn])
    def sms_page(request: Request, db: Db) -> Response:
        return _sms_page(request, db)

    @app.post("/sms/pair-code", response_class=HTMLResponse, dependencies=[LoggedIn])
    def sms_pair_code(request: Request, db: Db) -> Response:
        code = new_pair_code(request.app.state.session_factory, db)
        return _sms_page(request, db, pair_code=code)

    @app.post("/sms/upload", dependencies=[LoggedIn])
    async def sms_upload(request: Request, db: Db) -> Response:
        form = await request.form()
        upload = form.get("file")
        if not isinstance(upload, UploadFile):
            raise HTTPException(400)
        content = (await upload.read()).decode("utf-8", errors="replace")
        counts = import_text(db, content, llm=request.app.state.llm)
        return done(request, "/sms", s.TOASTS["sms_imported"].format(
            **{k: forms.to_persian_digits(str(v)) for k, v in counts.items()}))

    @app.post("/sms/token", dependencies=[LoggedIn])
    def sms_rotate_token(request: Request, db: Db) -> Response:
        services.set_user_setting(db, TOKEN_KEY, secrets.token_urlsafe(24))
        db.commit()
        return done(request, "/sms", s.TOASTS["sms_token"])

    def _sms(db: Session, sms_id: int) -> SmsInbox:
        sms = db.get(SmsInbox, sms_id)
        if sms is None:
            raise HTTPException(404)
        return sms

    def _review(request: Request, sms: SmsInbox, values: dict[str, str],
                errors: dict[str, str] | None = None, status: int = 200) -> Response:
        fragment = wants_fragment(request)
        if fragment and status >= 400:
            status = 422
        return page(request, "sms_review_sheet.html" if fragment else "sms_review_page.html", {
            "active": "sms", "sms": sms, "fields": REVIEW_FIELDS, "values": values,
            "errors": errors or {}, "body": None}, status)

    def _pick(request: Request, db: Session, sms: SmsInbox, reading: ParsedSms,
              error: str = "", status: int = 200) -> Response:
        """پیامک خوانده‌شده: کاربر فقط حساب را انتخاب می‌کند (حساب‌های همان بانک اول)."""
        accounts = sorted(db.scalars(select(Account)).all(),
                          key=lambda a: (a.bank != reading.bank, a.id))
        fragment = wants_fragment(request)
        if fragment and status >= 400:
            status = 422
        return page(request, "sms_review_sheet.html" if fragment else "sms_review_page.html", {
            "active": "sms", "sms": sms, "reading": reading, "accounts": accounts,
            "amount_toman": rial_to_toman(reading.amount_rial),
            "balance_toman": (None if reading.balance_after_rial is None
                              else rial_to_toman(reading.balance_after_rial)),
            "new_template": sms.error == NEW_TEMPLATE, "error": error,
            "body": "_sms_account_body.html"}, status)

    @app.get("/sms/{sms_id}/review", response_class=HTMLResponse, dependencies=[LoggedIn])
    def sms_review(request: Request, sms_id: int, db: Db, manual: int = 0) -> Response:
        sms = _sms(db, sms_id)
        reading = held_reading(sms) if not manual else None
        if reading is not None:
            return _pick(request, db, sms, reading)
        return _review(request, sms, {"direction": "out"})

    @app.post("/sms/{sms_id}/account", response_class=HTMLResponse, dependencies=[LoggedIn])
    async def sms_choose_account(request: Request, sms_id: int, db: Db) -> Response:
        sms = _sms(db, sms_id)
        reading = held_reading(sms)
        if reading is None:
            raise HTTPException(404)
        choice = (await read_form(request)).get("account", "")
        if choice != "new" and not choice.isdigit():
            return _pick(request, db, sms, reading, s.T["sms_pick_title"], status=400)
        try:
            choose_account(db, sms, None if choice == "new" else int(choice))
        except ValueError as exc:
            return _pick(request, db, sms, reading, str(exc), status=400)
        return done(request, "/sms", s.TOASTS["sms_account_chosen"])

    @app.post("/sms/{sms_id}/review", response_class=HTMLResponse, dependencies=[LoggedIn])
    async def sms_complete(request: Request, sms_id: int, db: Db) -> Response:
        sms = _sms(db, sms_id)
        data = await read_form(request)
        try:
            v = forms.parse_form(REVIEW_FIELDS, data)
            mask = forms.normalize_digits(v["account_mask"])
            if not (len(mask) == 4 and mask.isdigit()):
                raise FormError({"account_mask": s.T["mask_hint"]})
            prefix = forms.normalize_digits(v["account_prefix"] or "")
            if prefix and not (len(prefix) <= 4 and prefix.isdigit()):
                raise FormError({"account_prefix": "حداکثر ۴ رقم"})
            complete_manually(db, sms, ParsedSms(
                bank=v["bank"], account_mask=mask, account_prefix=prefix,
                direction=v["direction"],
                amount_rial=v["amount"], balance_after_rial=v["balance_after"],
                description=v["description"] or ""))
        except FormError as exc:
            return _review(request, sms, data, exc.errors, status=400)
        return done(request, "/sms", s.TOASTS["sms_completed"])

    @app.post("/sms/{sms_id}/ignore", dependencies=[LoggedIn])
    def sms_ignore(request: Request, sms_id: int, db: Db) -> Response:
        ignore(db, _sms(db, sms_id))
        return done(request, "/sms", s.TOASTS["sms_ignored"])


def _received_at(value: object) -> datetime:
    if isinstance(value, str) and value.strip():
        try:
            return parse_time(value)
        except (ValueError, TypeError):
            pass
    return utcnow()
