"""زمان‌بند درون‌پروسه‌ای دریافت قیمت (asyncio، بدون وابستگی اضافه).

- وقتی اپ باز است (بازدیدی در چند دقیقه اخیر): هر چند ثانیه یک‌بار (پیش‌فرض ۳۰).
- وقتی کسی اپ را نگاه نمی‌کند: هر یک ساعت؛ با اولین بازدید بعدی فوراً بیدار می‌شود.
- پس از هر شکست، فاصله دو برابر می‌شود (تا سقف) تا منبع زیر بار نرود.
"""

import asyncio
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy.orm import Session, sessionmaker

from app.adapters.prices import PriceSource
from app.price_refresh import due_sources, refresh_all
from app.sms.importer import import_new_from_file

log = logging.getLogger("finassist.prices")


@dataclass(frozen=True)
class Pace:
    active_seconds: float = 30
    idle_seconds: float = 3600
    active_window: float = 300  # تا چند ثانیه پس از آخرین بازدید «فعال» حساب می‌شود
    max_backoff: float = 600


def next_delay(pace: Pace, idle_for: float, failures: int) -> float:
    """فاصله تا دریافت بعدی بر اساس فعال بودن کاربر و تعداد شکست‌های پیاپی."""
    base = pace.active_seconds if idle_for <= pace.active_window else pace.idle_seconds
    if failures <= 0:
        return base
    return min(base * 2 ** failures, max(pace.max_backoff, base))


@dataclass
class Activity:
    """زمان آخرین بازدید؛ برگشتن پس از بیکاری زمان‌بند را بیدار می‌کند."""

    pace: Pace
    last: float = float("-inf")
    wake: asyncio.Event = field(default_factory=asyncio.Event)

    def idle_for(self, now: float | None = None) -> float:
        return (time.monotonic() if now is None else now) - self.last

    def touch(self) -> None:
        was_idle = self.idle_for() > self.pace.active_window
        self.last = time.monotonic()
        if was_idle:
            self.wake.set()


def refresh_now(factory: sessionmaker[Session], sources: list[PriceSource]) -> bool:
    with factory() as session:
        statuses = refresh_all(session, due_sources(session, sources))
    for status in statuses:
        if status.ok:
            log.info("%s: %d قیمت دریافت شد", status.name, status.count)
        else:
            log.warning("%s: %s", status.name, status.error)
    return all(status.ok for status in statuses)


async def run_adaptive(job: Callable[[], bool], activity: Activity) -> None:
    failures = 0
    while True:
        try:
            ok = await asyncio.to_thread(job)
        except Exception:  # زمان‌بند نباید با یک خطا متوقف شود
            log.exception("دریافت قیمت شکست خورد")
            ok = False
        failures = 0 if ok else failures + 1
        last_run = time.monotonic()
        while True:
            elapsed = time.monotonic() - last_run
            remaining = next_delay(activity.pace, activity.idle_for(), failures) - elapsed
            if remaining <= 0:
                break
            activity.wake.clear()
            try:
                await asyncio.wait_for(activity.wake.wait(), timeout=remaining)
            except TimeoutError:
                pass


SMS_FILE_SECONDS = 60
sms_log = logging.getLogger("finassist.sms")


def import_sms_file(factory: sessionmaker[Session], path: Path) -> None:
    """بخش تازه فایل پیامک‌ها (Shortcuts → iCloud Drive) را وارد می‌کند."""
    with factory() as session:
        counts = import_new_from_file(session, path)
    if counts and any(counts.values()):
        sms_log.info("پیامک: %s", counts)


async def run_every(job: Callable[[], None], seconds: float) -> None:
    while True:
        try:
            await asyncio.to_thread(job)
        except Exception:
            log.exception("کار زمان‌بندی‌شده شکست خورد")
        await asyncio.sleep(seconds)
