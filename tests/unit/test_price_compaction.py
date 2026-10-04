"""فشرده‌سازی قیمت‌های قدیمی: جزئیات روزهای گذشته حذف، پایانی هر روز و همه چیز اخیر حفظ."""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import Base, make_engine, make_session_factory
from app.models import PriceQuote, User
from app.price_history import _own_closes
from app.price_refresh import KEEP_DETAIL, compact_quotes
from app.services import latest_quotes, price_at

NOW = datetime(2026, 10, 5, 12, 0, tzinfo=UTC)


@pytest.fixture
def session() -> Iterator[Session]:
    engine = make_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with make_session_factory(engine)() as s:
        yield s


def _seed(session: Session) -> None:
    """هر ۳ ساعت یک قیمت تازه برای دلار در ۱۰ روز گذشته، و یک قیمت دستی قدیمی."""
    session.add(User(id=1, phone="09120000000"))
    session.flush()
    moment, price = NOW - timedelta(days=10), 100_000
    while moment <= NOW:
        session.add(PriceQuote(key="usd", price_toman=price, fetched_at=moment,
                               first_seen_at=moment, source="alanchand"))
        moment += timedelta(hours=3)
        price += 50
    session.add(PriceQuote(key="usd", price_toman=1, fetched_at=NOW - timedelta(days=9),
                           first_seen_at=NOW - timedelta(days=9), source="manual", user_id=1))
    session.commit()


def test_compaction_keeps_daily_closes_recent_detail_and_latest(session: Session) -> None:
    _seed(session)
    closes, latest = _own_closes(session, "usd"), latest_quotes(session)["usd"].price_toman
    yesterday = price_at(session, "usd", NOW - timedelta(hours=24)).price_toman
    before = len(session.scalars(select(PriceQuote)).all())

    removed = compact_quotes(session, NOW)

    after = session.scalars(select(PriceQuote)).all()
    assert removed > 0 and len(after) == before - removed
    assert _own_closes(session, "usd") == closes  # نمودار روزانه تغییر نمی‌کند
    assert latest_quotes(session)["usd"].price_toman == latest
    assert price_at(session, "usd", NOW - timedelta(hours=24)).price_toman == yesterday
    recent = [r for r in after if r.fetched_at >= NOW - KEEP_DETAIL and r.user_id is None]
    assert len(recent) == len([r for r in range(0, 10 * 8 + 1)
                               if timedelta(hours=3 * r) >= timedelta(days=10) - KEEP_DETAIL])
    assert any(r.source == "manual" for r in after)  # قیمت دستی کاربر هرگز حذف نمی‌شود


def test_compaction_is_idempotent(session: Session) -> None:
    _seed(session)
    compact_quotes(session, NOW)
    assert compact_quotes(session, NOW) == 0
