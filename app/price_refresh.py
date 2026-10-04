"""دریافت قیمت از منابع، ذخیره تاریخچه و ثبت وضعیت هر منبع.

شکست یک منبع بقیه را متوقف نمی‌کند و آخرین قیمت معتبر همچنان نمایش داده می‌شود.
ردیف تازه فقط وقتی ثبت می‌شود که قیمت عوض شده باشد؛ وگرنه fetched_at آخرین ردیف
(زمان آخرین مشاهده) جلو می‌رود تا تاریخچه با دریافت‌های پرتکرار پر نشود.
"""

import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.adapters.prices import FetchedQuote, PriceSource, PriceSourceError
from app.models import PriceQuote, utcnow
from app.price_history import _tehran_day
from app.services import get_setting, latest_quotes, set_setting

STATUS_KEY = "price_source_status:{name}"
# قیمت‌های چند روز اخیر با همه جزئیات (تغییر ۲۴ ساعته)؛ قدیمی‌ترها فقط پایانی هر روز
KEEP_DETAIL = timedelta(days=3)
COMPACT_EVERY = timedelta(hours=6)
_COMPACT_STAMP = "quotes_compacted_at"
_DELETE_BATCH = 500


@dataclass(frozen=True)
class SourceStatus:
    name: str
    at: datetime
    ok: bool
    count: int
    error: str = ""
    # برای منبعی که نمادهای کاربران را می‌گیرد (شاخص‌بان)؛ جدا نگه داشته می‌شوند تا
    # به هر کاربر فقط نمادهای خودش نشان داده شود
    missing: tuple[str, ...] = ()
    stale: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class SourceView:
    """وضعیت منبع از دید یک کاربر."""

    name: str
    at: datetime
    ok: bool
    count: int
    note: str = ""
    idle: bool = False  # کاربر نمادی ندارد که این منبع برایش قیمت بگیرد


def view_for_user(status: SourceStatus, user_keys: set[str], per_user: bool) -> SourceView:
    if not per_user:
        return SourceView(status.name, status.at, status.ok, status.count, status.error)
    symbols = {key.partition(":")[2] for key in user_keys}
    if not symbols:
        return SourceView(status.name, status.at, True, 0, idle=True)
    missing = [m for m in status.missing if m in symbols]
    stale = [f"{sym} (آخرین معامله {day})" for sym, day in status.stale if sym in symbols]
    parts = []
    if missing:
        parts.append("پیدا نشد: " + "، ".join(missing))
    if stale:
        parts.append("قیمت قدیمی: " + "، ".join(stale))
    connection_failed = not status.ok and not status.missing
    if connection_failed:
        parts.append(status.error)
    count = len(symbols) - len(missing)
    return SourceView(status.name, status.at, not missing and not connection_failed,
                      max(count, 0), " · ".join(p for p in parts if p))


def _valid(quote: FetchedQuote) -> bool:
    return bool(quote.key) and quote.price_toman > 0 and quote.units > 0


def refresh_source(session: Session, source: PriceSource) -> SourceStatus:
    now = utcnow()
    try:
        quotes = [q for q in source.fetch() if _valid(q)]
    except Exception as exc:  # هر خطای منبع فقط همان منبع را از کار می‌اندازد
        message = str(exc) if isinstance(exc, PriceSourceError) else f"{type(exc).__name__}: {exc}"
        status = SourceStatus(source.name, now, False, 0, message[:300],
                              tuple(getattr(source, "missing", ())),
                              tuple(getattr(source, "stale", ())))
    else:
        latest = latest_quotes(session)
        for quote in quotes:
            previous = latest.get(quote.key)
            if (previous is not None and previous.source == source.name
                    and previous.price_toman == quote.price_toman
                    and previous.units == quote.units):
                previous.fetched_at = now  # قیمت عوض نشده؛ فقط زمان آخرین مشاهده به‌روز می‌شود
            else:
                session.add(PriceQuote(key=quote.key, price_toman=quote.price_toman,
                                       units=quote.units, fetched_at=now, source=source.name))
        warning = getattr(source, "warning", "")  # مثلاً نماد پیدانشده یا قیمت قدیمی
        status = SourceStatus(source.name, now, bool(quotes), len(quotes),
                              warning if quotes else warning or "هیچ قیمتی دریافت نشد",
                              tuple(getattr(source, "missing", ())),
                              tuple(getattr(source, "stale", ())))
    _save_status(session, status)
    session.commit()
    return status


def _has_work(source: PriceSource) -> bool:
    """منبعی که فقط برای دارایی‌های کاربر قیمت می‌گیرد، بدون دارایی کاری ندارد."""
    check = getattr(source, "has_work", None)
    return check() if check else True


def refresh_all(session: Session, sources: list[PriceSource]) -> list[SourceStatus]:
    statuses = [refresh_source(session, source) for source in sources if _has_work(source)]
    maybe_compact(session)
    return statuses


def compact_quotes(session: Session, now: datetime | None = None) -> int:
    """ردیف‌های قیمت منابع قدیمی‌تر از KEEP_DETAIL: فقط آخرین ردیف هر کلید در هر روز تهران
    می‌ماند (پایانی روز برای نمودار)؛ قیمت دستی کاربران دست نمی‌خورد. تعداد حذف‌شده را برمی‌گرداند.

    بدون این، جدول با هر دریافت (هر ۳۰ ثانیه) بزرگ‌تر و همه صفحه‌ها کندتر می‌شوند.
    """
    now = now or utcnow()
    rows = session.execute(
        select(PriceQuote.id, PriceQuote.key, PriceQuote.first_seen_at, PriceQuote.fetched_at)
        .where(PriceQuote.user_id.is_(None), PriceQuote.fetched_at < now - KEEP_DETAIL)
        .order_by(PriceQuote.key, PriceQuote.first_seen_at, PriceQuote.id)).all()
    closing: dict[tuple[str, date], int] = {}
    for row in rows:
        closing[(row.key, _tehran_day(row.first_seen_at or row.fetched_at))] = row.id
    keep = set(closing.values())
    doomed = [row.id for row in rows if row.id not in keep]
    for start in range(0, len(doomed), _DELETE_BATCH):
        session.execute(delete(PriceQuote).where(
            PriceQuote.id.in_(doomed[start:start + _DELETE_BATCH])))
    session.commit()
    return len(doomed)


def maybe_compact(session: Session, now: datetime | None = None) -> int:
    """حداکثر هر COMPACT_EVERY یک بار."""
    now = now or utcnow()
    stamp = get_setting(session, _COMPACT_STAMP)
    if stamp and now - datetime.fromisoformat(stamp) < COMPACT_EVERY:
        return 0
    removed = compact_quotes(session, now)
    set_setting(session, _COMPACT_STAMP, now.isoformat())
    session.commit()
    return removed


def due_sources(session: Session, sources: list[PriceSource],
                now: datetime | None = None) -> list[PriceSource]:
    """منابعی که از آخرین دریافتشان دست‌کم min_interval ثانیه گذشته (منبع کند مثل بورس)."""
    now = now or utcnow()
    due = []
    for source in sources:
        interval = getattr(source, "min_interval", 0)
        status = load_status(session, source.name) if interval else None
        if status is None or (now - status.at).total_seconds() >= interval:
            due.append(source)
        elif _has_unpriced(session, source):  # نماد تازه ثبت‌شده منتظر ۱۰ دقیقه نماند
            due.append(source)
    return due


def _has_unpriced(session: Session, source: PriceSource) -> bool:
    wanted = getattr(source, "wanted_keys", None)
    if wanted is None:
        return False
    known = latest_quotes(session)
    return any(key not in known for key in wanted())


def _save_status(session: Session, status: SourceStatus) -> None:
    set_setting(session, STATUS_KEY.format(name=status.name), json.dumps({
        "at": status.at.isoformat(), "ok": status.ok, "count": status.count,
        "error": status.error, "missing": list(status.missing),
        "stale": [list(pair) for pair in status.stale]}, ensure_ascii=False))


def load_status(session: Session, name: str) -> SourceStatus | None:
    raw = get_setting(session, STATUS_KEY.format(name=name))
    if raw is None:
        return None
    data = json.loads(raw)
    return SourceStatus(name, datetime.fromisoformat(data["at"]), data["ok"], data["count"],
                        data["error"], tuple(data.get("missing", ())),
                        tuple((sym, day) for sym, day in data.get("stale", ())))
