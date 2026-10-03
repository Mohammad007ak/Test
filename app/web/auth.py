"""ورود تک‌کاربره: رمز با argon2 در جدول settings، نشست امضاشده در کوکی."""

import secrets
import time
from collections.abc import Callable

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from fastapi import Request
from sqlalchemy.orm import Session

from app.services import get_setting, set_setting

PASSWORD_KEY = "password_hash"
SECRET_KEY = "session_secret"
MIN_PASSWORD_LENGTH = 8

_hasher = PasswordHasher()


class LoginRequired(Exception):
    """کاربر وارد نشده؛ به صفحه ورود هدایت می‌شود."""


def has_password(session: Session) -> bool:
    return get_setting(session, PASSWORD_KEY) is not None


def set_password(session: Session, password: str) -> None:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError("password too short")
    set_setting(session, PASSWORD_KEY, _hasher.hash(password))


def check_password(session: Session, password: str) -> bool:
    stored = get_setting(session, PASSWORD_KEY)
    if stored is None:
        return False
    try:
        return _hasher.verify(stored, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


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
    """بعد از max_failures رمز اشتباه از یک آدرس، ورود از آن آدرس تا پایان پنجره بسته است."""

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


def require_login(request: Request) -> None:
    if not request.session.get("authenticated"):
        raise LoginRequired
