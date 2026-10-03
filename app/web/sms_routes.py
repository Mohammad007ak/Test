"""مسیرهای پیامک بانکی: اندپوینت Shortcuts، واردکردن فایل و صف بررسی (SPEC: F6)."""

import hmac
import secrets
import socket
import time
from collections import deque
from datetime import datetime

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from starlette.datastructures import UploadFile

from app import services
from app.config import Settings
from app.models import SmsInbox, utcnow
from app.sms.importer import import_text, parse_time
from app.sms.parsers import ParsedSms
from app.sms.pipeline import complete_manually, ignore, ingest
from app.web import forms
from app.web import strings as s
from app.web.common import Db, LoggedIn, done, page, read_form, wants_fragment
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


def ingest_token(db: Session, settings: Settings) -> str:
    if settings.sms_token:
        return settings.sms_token
    token = services.get_setting(db, TOKEN_KEY)
    if token is None:
        token = secrets.token_urlsafe(24)
        services.set_setting(db, TOKEN_KEY, token)
        db.commit()
    return token


_LOCAL_HOSTS = {"127.0.0.1", "localhost", "0.0.0.0", "::1"}


def phone_endpoint(host: str, port: int | None, machine: str | None = None,
                   scheme: str = "http") -> str:
    """آدرسی که آیفون باید بزند؛ 127.0.0.1 از گوشی کار نمی‌کند، پس اسم ثابت مک (.local)."""
    if host in _LOCAL_HOSTS:
        name = (machine or socket.gethostname()).split(".")[0]
        host = f"{name}.local"
    return f"{scheme}://{host}{f':{port}' if port else ''}/api/sms"


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


def register_sms_routes(app: FastAPI, settings: Settings) -> None:
    limiter = _RateLimiter(RATE_LIMIT)

    @app.post("/api/sms")
    async def api_sms(request: Request, db: Db) -> Response:
        """Shortcuts آیفون: بدنه JSON {"text": "...", "received_at": "..."} و هدر توکن."""
        token = request.headers.get("X-Ingest-Token", "")
        if not hmac.compare_digest(token, ingest_token(db, settings)):
            return JSONResponse({"error": "invalid token"}, status_code=401)
        if not limiter.allow():
            return JSONResponse({"error": "rate limited"}, status_code=429)
        try:
            body = await request.json()
            text = str(body["text"]).strip()
        except (ValueError, KeyError, TypeError):
            return JSONResponse({"error": "expected JSON with text"}, status_code=400)
        if not text or len(text) > MAX_TEXT:
            return JSONResponse({"error": "empty or too long"}, status_code=400)
        received = _received_at(body.get("received_at"))
        result = ingest(db, text, received, llm=request.app.state.llm)
        return JSONResponse({"status": result.status, "id": result.sms.id})

    @app.get("/sms", response_class=HTMLResponse, dependencies=[LoggedIn])
    def sms_page(request: Request, db: Db) -> Response:
        queue = db.scalars(select(SmsInbox).where(SmsInbox.parse_status == "failed")
                           .order_by(SmsInbox.received_at.desc())).all()
        recent = db.scalars(select(SmsInbox).where(SmsInbox.parse_status != "failed")
                            .order_by(SmsInbox.id.desc()).limit(20)).all()
        return page(request, "sms.html", {
            "active": "sms", "queue": queue, "recent": recent,
            "token": ingest_token(db, settings),
            "endpoint": phone_endpoint(request.url.hostname or "", request.url.port,
                                       scheme=_public_scheme(request)),
            "watched_file": settings.sms_file,
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
        services.set_setting(db, TOKEN_KEY, secrets.token_urlsafe(24))
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
