"""زمان‌بند درون‌پروسه‌ای: دریافت دوره‌ای قیمت‌ها (بدون وابستگی اضافه، با asyncio)."""

import asyncio
import logging
from collections.abc import Callable

from sqlalchemy.orm import Session, sessionmaker

from app.adapters.prices import PriceSource
from app.price_refresh import refresh_all

log = logging.getLogger("finassist.prices")


def refresh_now(factory: sessionmaker[Session], sources: list[PriceSource]) -> None:
    with factory() as session:
        for status in refresh_all(session, sources):
            if status.ok:
                log.info("%s: %d قیمت دریافت شد", status.name, status.count)
            else:
                log.warning("%s: %s", status.name, status.error)


async def run_periodically(job: Callable[[], None], minutes: int) -> None:
    """اجرای job در یک thread جدا، بلافاصله و سپس هر چند دقیقه یک‌بار."""
    while True:
        try:
            await asyncio.to_thread(job)
        except Exception:  # زمان‌بند نباید با یک خطا متوقف شود
            log.exception("دریافت قیمت شکست خورد")
        await asyncio.sleep(minutes * 60)
