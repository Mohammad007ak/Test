"""دریافت قیمت از منابع، ذخیره تاریخچه و ثبت وضعیت هر منبع.

شکست یک منبع بقیه را متوقف نمی‌کند و آخرین قیمت معتبر همچنان نمایش داده می‌شود.
ردیف تازه فقط وقتی ثبت می‌شود که قیمت عوض شده باشد؛ وگرنه fetched_at آخرین ردیف
(زمان آخرین مشاهده) جلو می‌رود تا تاریخچه با دریافت‌های پرتکرار پر نشود.
"""

import json
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from app.adapters.prices import FetchedQuote, PriceSource
from app.models import PriceQuote, utcnow
from app.services import get_setting, latest_quotes, set_setting

STATUS_KEY = "price_source_status:{name}"


@dataclass(frozen=True)
class SourceStatus:
    name: str
    at: datetime
    ok: bool
    count: int
    error: str = ""


def _valid(quote: FetchedQuote) -> bool:
    return bool(quote.key) and quote.price_toman > 0


def refresh_source(session: Session, source: PriceSource) -> SourceStatus:
    now = utcnow()
    try:
        quotes = [q for q in source.fetch() if _valid(q)]
    except Exception as exc:  # هر خطای منبع فقط همان منبع را از کار می‌اندازد
        status = SourceStatus(source.name, now, False, 0, f"{type(exc).__name__}: {exc}"[:300])
    else:
        latest = latest_quotes(session)
        for quote in quotes:
            previous = latest.get(quote.key)
            if (previous is not None and previous.source == source.name
                    and previous.price_toman == quote.price_toman):
                previous.fetched_at = now  # قیمت عوض نشده؛ فقط زمان آخرین مشاهده به‌روز می‌شود
            else:
                session.add(PriceQuote(key=quote.key, price_toman=quote.price_toman,
                                       fetched_at=now, source=source.name))
        status = SourceStatus(source.name, now, bool(quotes), len(quotes),
                              "" if quotes else "هیچ قیمتی دریافت نشد")
    _save_status(session, status)
    session.commit()
    return status


def refresh_all(session: Session, sources: list[PriceSource]) -> list[SourceStatus]:
    return [refresh_source(session, source) for source in sources]


def _save_status(session: Session, status: SourceStatus) -> None:
    set_setting(session, STATUS_KEY.format(name=status.name), json.dumps({
        "at": status.at.isoformat(), "ok": status.ok, "count": status.count,
        "error": status.error}, ensure_ascii=False))


def load_status(session: Session, name: str) -> SourceStatus | None:
    raw = get_setting(session, STATUS_KEY.format(name=name))
    if raw is None:
        return None
    data = json.loads(raw)
    return SourceStatus(name, datetime.fromisoformat(data["at"]), data["ok"], data["count"],
                        data["error"])
