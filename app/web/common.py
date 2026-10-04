"""ابزارهای مشترک مسیرهای وب: دیتابیس، رندر صفحه، پیام کوتاه و بازگشت پس از فرم."""

import json
from collections.abc import Iterator
from typing import Annotated, Any
from urllib.parse import urlsplit

from fastapi import Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy.orm import Session

from app.db import user_session
from app.web import auth
from app.web import strings as s
from app.web.render import templates

Form = dict[str, str]


def get_db(request: Request) -> Iterator[Session]:
    """نشست دیتابیس محدود به کاربر واردشده (یا هیچ‌کس)."""
    with request.app.state.session_factory() as session:
        user_id = auth.session_user_id(request, session)
        request.state.user_id = user_id
        yield user_session(session, user_id)


Db = Annotated[Session, Depends(get_db)]


def require_login(request: Request, _db: Db) -> None:
    if request.state.user_id is None:
        raise auth.LoginRequired


LoggedIn = Depends(require_login)


async def read_form(request: Request) -> Form:
    form = await request.form()
    return {key: str(value) for key, value in form.items()}


def wants_fragment(request: Request) -> bool:
    """درخواست htmx برای تکه‌ای از صفحه (مثل برگه پایین)، نه ناوبری کامل."""
    return (request.headers.get("HX-Request") == "true"
            and request.headers.get("HX-Boosted") != "true")


def toast(request: Request, message: str) -> None:
    request.session["toast"] = message


def site_url(request: Request) -> str:
    """آدرس اصلی سایت: FINASSIST_PUBLIC_URL، وگرنه همان آدرسی که درخواست با آن آمده."""
    configured = getattr(request.app.state, "public_url", "")
    return (configured or str(request.base_url)).rstrip("/")


def page(request: Request, name: str, context: dict[str, Any], status: int = 200) -> HTMLResponse:
    """indexable=True فقط برای صفحه‌های عمومی (معرفی، ورود، ثبت‌نام)؛ بقیه noindex."""
    active = context.get("active")
    if context.get("indexable"):
        base = site_url(request)
        context = {"site_url": base, "canonical": base + request.url.path, **context}
    return templates.TemplateResponse(request, name, {
        "active": None,
        "tab": s.TAB_OF_PAGE.get(active, active) if active else None,
        "title": s.PAGE_TITLES.get(active or "", s.APP_NAME),
        "toast": request.session.pop("toast", None),
        **context,
    }, status_code=status)


def redirect(url: str) -> RedirectResponse:
    return RedirectResponse(url, status_code=303)


def done(request: Request, url: str, message: str) -> Response:
    """پایان موفق یک فرم: پیام کوتاه و بازگشت نرم به فهرست."""
    toast(request, message)
    if wants_fragment(request):
        # برگه از هر صفحه‌ای باز شده باشد (مثلاً خانه)، همان صفحه تازه می‌شود
        current = urlsplit(request.headers.get("HX-Current-URL", "")).path
        location = json.dumps({"path": current or url, "target": "body"})
        return Response(status_code=200, headers={"HX-Location": location})
    return redirect(url)
