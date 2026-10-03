"""ورود چندکاربره: نام کاربری = موبایل، رمز با argon2، نشست امضاشده در کوکی.

نشست شناسه کاربر و «نسخه نشست» او را نگه می‌دارد؛ با تغییر رمز نسخه بالا می‌رود و همه
نشست‌های قبلی (دستگاه‌های دیگر) باطل می‌شوند.
"""

import secrets
import time
from collections.abc import Callable

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import User
from app.services import get_setting, set_setting

SECRET_KEY = "session_secret"
MIN_PASSWORD_LENGTH = 8

_hasher = PasswordHasher()
_DUMMY_HASH = _hasher.hash("dummy-password-for-timing")


class LoginRequired(Exception):
    """کاربر وارد نشده؛ به صفحه ورود هدایت می‌شود."""


def hash_password(password: str) -> str:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError("password too short")
    return _hasher.hash(password)


def user_by_phone(session: Session, phone: str) -> User | None:
    return session.scalars(select(User).where(User.phone == phone)).first()


def authenticate(session: Session, phone: str, password: str) -> User | None:
    user = user_by_phone(session, phone)
    try:  # برای شماره ناموجود هم یک بار هش بررسی می‌شود تا زمان پاسخ چیزی لو ندهد
        _hasher.verify(user.password_hash if user and user.password_hash else _DUMMY_HASH,
                       password)
    except (VerificationError, InvalidHashError):
        return None
    return user if user and user.password_hash else None


def log_in(request: Request, user: User) -> None:
    request.session.clear()
    request.session["uid"] = user.id
    request.session["sv"] = user.session_version


def session_user_id(request: Request, session: Session) -> int | None:
    uid = request.session.get("uid")
    if not isinstance(uid, int):
        return None
    user = session.get(User, uid)
    if user is None or user.phone is None or user.session_version != request.session.get("sv"):
        request.session.pop("uid", None)
        return None
    return uid


def session_secret(session: Session, configured: str) -> str:
    """کلید .env اگر هست؛ وگرنه یک کلید تصادفی که یک‌بار ساخته و نگه داشته می‌شود."""
    if configured:
        return configured
    stored = get_setting(session, SECRET_KEY)
    if stored is None:
        stored = secrets.token_urlsafe(48)
        set_setting(session, SECRET_KEY, stored)
        session.commit()
    return stored


class LoginThrottle:
    """بعد از max_failures رمز اشتباه برای یک کلید (IP یا شماره)، ورود تا پایان پنجره بسته است."""

    def __init__(self, max_failures: int = 5, window_seconds: float = 15 * 60,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self.max_failures = max_failures
        self.window = window_seconds
        self.clock = clock
        self._failures: dict[str, list[float]] = {}

    def _recent(self, client: str) -> list[float]:
        cutoff = self.clock() - self.window
        recent = [t for t in self._failures.get(client, []) if t > cutoff]
        if recent:
            self._failures[client] = recent
        else:
            self._failures.pop(client, None)
        return recent

    def allowed(self, client: str) -> bool:
        return len(self._recent(client)) < self.max_failures

    def failed(self, client: str) -> None:
        self._failures[client] = [*self._recent(client), self.clock()]

    def succeeded(self, client: str) -> None:
        self._failures.pop(client, None)


def ensure_owner(session: Session, phone: str, password: str) -> User | None:
    """حساب صاحب برنامه از متغیر محیطی: ساخته می‌شود، داده تک‌کاربره قبلی را تحویل می‌گیرد
    و اگر رمز محیطی عوض شده باشد، رمز به‌روز و نشست‌های قبلی باطل می‌شوند."""
    if len(password) < MIN_PASSWORD_LENGTH:
        return None
    user = user_by_phone(session, phone)
    if user is None:
        user = session.scalars(select(User).where(User.phone.is_(None))).first() or User()
        user.phone = phone
        session.add(user)
    try:
        if user.password_hash and _hasher.verify(user.password_hash, password):
            session.commit()
            return user
    except (VerificationError, InvalidHashError):
        pass
    user.password_hash = hash_password(password)
    user.session_version = (user.session_version or 0) + 1
    session.commit()
    return user
