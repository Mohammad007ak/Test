"""تاریخچه قیمت روزانه: آرشیو منبع (الان‌چند) + قیمت‌های خود اپ، و تغییر روزانه.

آرشیو هر کلید حداکثر هر ۱۲ ساعت یک بار گرفته می‌شود (موقع باز شدن نمودار یا سؤال وزیر).
اگر واحد آرشیو با قیمت فعلی نخواند (مثلاً قیمت صد واحد)، فقط حالت روشن «صد برابر» اصلاح
می‌شود؛ ناهمخوانی دیگر ذخیره نمی‌شود، نه حدس.
"""

import logging
from collections.abc import Sequence
from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app import services
from app.adapters.prices.base import PriceSourceError
from app.adapters.prices.history import HistoryPoint, HistorySource
from app.domain.spending import TEHRAN
from app.models import PriceHistory, PriceQuote, utcnow

log = logging.getLogger("finassist.history")
FRESH_FOR = timedelta(hours=12)
RETRY_AFTER_FAILURE = timedelta(hours=1)
CHANGE_WINDOW = timedelta(hours=24)
_STAMP = "history_at:"

Series = list[tuple[date, Decimal]]


def _tehran_day(moment: datetime) -> date:
    return moment.astimezone(TEHRAN).date()


def _scaled(points: Sequence[HistoryPoint], current: Decimal | None) -> list[HistoryPoint] | None:
    """واحد آرشیو با قیمت فعلی؛ None یعنی ناهمخوان (ذخیره نکن)."""
    if not points or current is None:
        return list(points)
    ratio = current / points[-1].price_toman
    if Decimal("0.67") < ratio < Decimal("1.5"):
        return list(points)
    if Decimal("0.0067") < ratio < Decimal("0.015"):  # آرشیو قیمت صد واحد است
        return [HistoryPoint(p.day, max(round(p.price_toman / 100), 1),
                             None if p.real_price_toman is None
                             else round(p.real_price_toman / 100)) for p in points]
    return None


def refresh(session: Session, key: str, sources: Sequence[HistorySource],
            now: datetime | None = None) -> bool:
    """آرشیو کلید را اگر کهنه است تازه می‌کند؛ True اگر چیزی ذخیره شد."""
    now = now or utcnow()
    source = next((src for src in sources if src.supports(key)), None)
    if source is None:
        return False
    stamp = services.get_setting(session, _STAMP + key)
    if stamp:
        last, _, outcome = stamp.partition("|")
        wait = FRESH_FOR if outcome == "ok" else RETRY_AFTER_FAILURE
        if now - datetime.fromisoformat(last) < wait:
            return False
    try:
        points = source.fetch_history(key)
    except PriceSourceError as exc:
        log.warning("آرشیو %s گرفته نشد: %s", key, exc)
        services.set_setting(session, _STAMP + key, f"{now.isoformat()}|failed")
        session.commit()
        return False
    quote = services.latest_quotes(session).get(key)
    points_ok = _scaled(points, quote.per_unit if quote else None)
    if points_ok is None:
        log.warning("واحد آرشیو %s با قیمت فعلی نمی‌خواند؛ ذخیره نشد", key)
        services.set_setting(session, _STAMP + key, f"{now.isoformat()}|failed")
        session.commit()
        return False
    session.execute(delete(PriceHistory).where(PriceHistory.key == key))
    session.add_all(PriceHistory(key=key, day=p.day, price_toman=p.price_toman,
                                 real_price_toman=p.real_price_toman, source=source.name)
                    for p in points_ok)
    services.set_setting(session, _STAMP + key, f"{now.isoformat()}|ok")
    session.commit()
    return True


def _own_closes(session: Session, key: str) -> dict[date, Decimal]:
    """قیمت پایانی هر روز از قیمت‌های خود اپ (هر ردیف تا ردیف بعدی معتبر است)."""
    rows = session.scalars(select(PriceQuote).where(PriceQuote.key == key)
                           .order_by(PriceQuote.first_seen_at, PriceQuote.id)).all()
    closes: dict[date, Decimal] = {}
    for i, row in enumerate(rows):
        start = _tehran_day(row.first_seen_at or row.fetched_at)
        until = rows[i + 1].first_seen_at if i + 1 < len(rows) else row.fetched_at
        end = _tehran_day(until or row.fetched_at)
        day = start
        while day <= end:
            closes[day] = row.per_unit
            day += timedelta(days=1)
    return closes


def series(session: Session, key: str) -> Series:
    """قیمت پایانی روزانه، قدیم به جدید؛ آرشیو منبع مقدم، روزهای بی‌آرشیو از خود اپ."""
    merged = {row.day: Decimal(row.price_toman) for row in session.scalars(
        select(PriceHistory).where(PriceHistory.key == key))}
    for day, price in _own_closes(session, key).items():
        merged.setdefault(day, price)
    return sorted(merged.items())


def intrinsic(session: Session, key: str) -> tuple[date, int, int] | None:
    """(روز، قیمت، ارزش ذاتی) آخرین روزی که آرشیو ارزش ذاتی دارد (سکه‌ها)."""
    row = session.scalars(select(PriceHistory).where(
        PriceHistory.key == key, PriceHistory.real_price_toman.is_not(None))
        .order_by(PriceHistory.day.desc())).first()
    return (row.day, row.price_toman, row.real_price_toman) if row and row.real_price_toman \
        else None


def change_24h(session: Session, key: str, quote: PriceQuote | None,
               now: datetime | None = None) -> Decimal | None:
    """تغییر نسبت به ۲۴ ساعت پیش؛ اگر قیمت آن موقع را نداریم، نسبت به پایانی دیروز آرشیو."""
    if quote is None or not quote.per_unit:
        return None
    now = now or utcnow()
    before = services.price_at(session, key, now - CHANGE_WINDOW)
    if before is not None:  # اپ قیمت ۲۴ ساعت پیش را دارد
        same = before.id == quote.id or not before.per_unit
        return None if same else _ratio(quote.per_unit, before.per_unit)
    row = session.scalars(select(PriceHistory).where(
        PriceHistory.key == key, PriceHistory.day < _tehran_day(now))
        .order_by(PriceHistory.day.desc())).first()
    return None if row is None else _ratio(quote.per_unit, Decimal(row.price_toman))


def _ratio(now_price: Decimal, then: Decimal) -> Decimal | None:
    return (now_price - then) / then if then else None

