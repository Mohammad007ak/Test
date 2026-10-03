from collections.abc import Iterator

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.prices import FetchedQuote, PriceSourceError
from app.db import Base, make_engine, make_session_factory
from app.models import PriceQuote, utcnow
from app.price_refresh import load_status, refresh_all
from app.services import latest_quotes


class FakeSource:
    def __init__(self, name: str, quotes: list[FetchedQuote] | None = None,
                 error: Exception | None = None) -> None:
        self.name, self.quotes, self.error = name, quotes or [], error

    def fetch(self) -> list[FetchedQuote]:
        if self.error:
            raise self.error
        return self.quotes


@pytest.fixture
def session() -> Iterator[Session]:
    engine = make_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with make_session_factory(engine)() as s:
        yield s


def test_quotes_saved_with_source_and_history(session: Session) -> None:
    source = FakeSource("fake", [FetchedQuote("usd", 102_500)])
    refresh_all(session, [source])
    source.quotes = [FetchedQuote("usd", 103_000)]
    refresh_all(session, [source])
    rows = session.scalars(select(PriceQuote)).all()
    assert [r.price_toman for r in rows] == [102_500, 103_000]
    assert latest_quotes(session)["usd"].source == "fake"
    assert latest_quotes(session)["usd"].price_toman == 103_000


def test_failing_source_does_not_stop_others_and_keeps_last_price(session: Session) -> None:
    good = FakeSource("good", [FetchedQuote("gold18_gram", 8_200_000)])
    session.add(PriceQuote(key="usd", price_toman=100_000, fetched_at=utcnow(), source="manual"))
    session.commit()
    statuses = refresh_all(session, [FakeSource("bad", error=PriceSourceError("قطع")), good])
    assert [s.ok for s in statuses] == [False, True]
    quotes = latest_quotes(session)
    assert quotes["usd"].price_toman == 100_000  # آخرین قیمت معتبر می‌ماند
    assert quotes["gold18_gram"].price_toman == 8_200_000
    bad = load_status(session, "bad")
    assert bad is not None and not bad.ok and "قطع" in bad.error


def test_invalid_quotes_are_dropped(session: Session) -> None:
    status = refresh_all(session, [FakeSource("x", [FetchedQuote("usd", 0),
                                                    FetchedQuote("", 5)])])[0]
    assert not status.ok and status.count == 0
    assert session.scalars(select(PriceQuote)).all() == []


def test_unexpected_exception_is_contained(session: Session) -> None:
    status = refresh_all(session, [FakeSource("x", error=ValueError("قالب عوض شد"))])[0]
    assert not status.ok and "ValueError" in status.error


def test_unchanged_price_updates_last_seen_without_new_row(session: Session) -> None:
    source = FakeSource("fake", [FetchedQuote("usd", 102_500)])
    refresh_all(session, [source])
    first_seen = latest_quotes(session)["usd"].fetched_at
    refresh_all(session, [source])
    rows = session.scalars(select(PriceQuote)).all()
    assert len(rows) == 1
    assert rows[0].fetched_at >= first_seen


def test_manual_price_is_not_overwritten_in_place(session: Session) -> None:
    session.add(PriceQuote(key="usd", price_toman=102_500, fetched_at=utcnow(), source="manual"))
    session.commit()
    refresh_all(session, [FakeSource("fake", [FetchedQuote("usd", 102_500)])])
    sources = [r.source for r in session.scalars(select(PriceQuote))]
    assert sources == ["manual", "fake"]


def test_slow_source_is_skipped_until_its_interval_passes(session: Session) -> None:
    from datetime import timedelta

    from app.price_refresh import due_sources

    fast = FakeSource("fast", [FetchedQuote("usd", 1)])
    slow = FakeSource("slow", [FetchedQuote("stock:فملی", 28_120, units=10)])
    slow.min_interval = 600  # type: ignore[attr-defined]
    assert due_sources(session, [fast, slow]) == [fast, slow]  # هنوز دریافت نشده
    refresh_all(session, [fast, slow])
    now = utcnow()
    assert due_sources(session, [fast, slow], now + timedelta(seconds=30)) == [fast]
    assert due_sources(session, [fast, slow], now + timedelta(seconds=601)) == [fast, slow]
