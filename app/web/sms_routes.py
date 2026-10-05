"""مسیرهای پیامک بانکی: اندپوینت Shortcuts، واردکردن فایل و صف بررسی (SPEC: F6)."""

import secrets
import time
from collections import deque
from collections.abc import Callable
from datetime import datetime
from urllib.parse import quote, urlencode

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from starlette.datastructures import UploadFile

from app import services
from app.db import user_session
from app.domain.phone import mask_phone
from app.models import SmsInbox, User, UserSetting, utcnow
from app.sms.importer import import_text, parse_time
from app.sms.parsers import ParsedSms
from app.sms.pipeline import complete_manually, ignore, ingest
from app.sms.text import is_secret
from app.web import forms
from app.web import strings as s
from app.web.common import Db, LoggedIn, done, page, read_form, site_url, wants_fragment
from app.web.forms import Field, FormError

TOKEN_KEY = "sms_ingest_token"
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

    @app.get("/sms", response_class=HTMLResponse, dependencies=[LoggedIn])
    def sms_page(request: Request, db: Db) -> Response:
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
            "android_unpair": ANDROID_UNPAIR,
            "shortcut_url": getattr(request.app.state, "ios_shortcut_url", ""),
            "platform": phone_platform(request.headers.get("user-agent", "")),
            "endpoint": sms_endpoint(getattr(request.app.state, "public_url", ""),
                                     _public_scheme(request), request.url.hostname or "",
                                     request.url.port),
        })

    @app.post("/sms/upload", dependencies=[LoggedIn])
    async def sms_upload(request: Request, db: Db) -> Response:
        form = await request.form()
        upload = form.get("file")
        if not isinstance(upload, UploadFile):
            raise HTTPException(400)
        content = (await upload.read()).decode("utf-8", errors="replace")
        counts = import_text(db, content)
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
            "errors": errors or {}}, status)

    @app.get("/sms/{sms_id}/review", response_class=HTMLResponse, dependencies=[LoggedIn])
    def sms_review(request: Request, sms_id: int, db: Db) -> Response:
        return _review(request, _sms(db, sms_id), {"direction": "out"})

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
