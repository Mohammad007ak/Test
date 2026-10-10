import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import Base, user_session
from app.models import Asset, PriceQuote, User, utcnow


@pytest.fixture
def engine():  # type: ignore[no-untyped-def]
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        s.add_all([User(id=1, phone="09120000001"), User(id=2, phone="09120000002")])
        s.commit()
    return engine


def test_new_rows_get_user_and_reads_are_scoped(engine) -> None:  # type: ignore[no-untyped-def]
    with user_session(Session(engine), 1) as s:
        s.add(Asset(kind="car", name="ماشین یک"))
        s.commit()
    with user_session(Session(engine), 2) as s:
        s.add(Asset(kind="car", name="ماشین دو"))
        s.commit()
        assert [a.name for a in s.scalars(select(Asset))] == ["ماشین دو"]
        assert s.get(Asset, 1) is None  # شناسه کاربر دیگر پیدا نمی‌شود
    with Session(engine) as system:  # پردازش‌های سیستمی (قیمت) همه را می‌بینند
        assert len(system.scalars(select(Asset)).all()) == 2


def test_anonymous_session_sees_nothing(engine) -> None:  # type: ignore[no-untyped-def]
    with user_session(Session(engine), 1) as s:
        s.add(Asset(kind="car", name="x"))
        s.commit()
    with user_session(Session(engine), None) as s:
        assert s.scalars(select(Asset)).all() == []


def test_system_session_cannot_insert_without_owner(engine) -> None:  # type: ignore[no-untyped-def]
    with Session(engine) as s:
        s.add(Asset(kind="car", name="بی‌صاحب"))
        with pytest.raises(IntegrityError):
            s.commit()


def test_manual_prices_are_private_source_prices_shared(engine) -> None:  # type: ignore[no-untyped-def]
    with Session(engine) as system:
        system.add(PriceQuote(key="usd", price_toman=100, fetched_at=utcnow(), source="alanchand"))
        system.commit()
    with user_session(Session(engine), 1) as s:
        s.add(PriceQuote(key="usd", price_toman=999, fetched_at=utcnow(), source="manual"))
        s.commit()
        assert sorted(q.price_toman for q in s.scalars(select(PriceQuote))) == [100, 999]
    with user_session(Session(engine), 2) as s:
        assert [q.price_toman for q in s.scalars(select(PriceQuote))] == [100]


def test_background_refresh_ignores_private_manual_prices(engine) -> None:  # type: ignore[no-untyped-def]
    from app.services import latest_quotes

    with Session(engine) as system:
        system.add(PriceQuote(key="usd", price_toman=100, fetched_at=utcnow(), source="alanchand"))
        system.commit()
    with user_session(Session(engine), 1) as s:
        s.add(PriceQuote(key="usd", price_toman=999, fetched_at=utcnow(), source="manual"))
        s.commit()
        assert latest_quotes(s)["usd"].price_toman == 999  # کاربر قیمت دستی خودش را می‌بیند
    with Session(engine) as system:
        assert latest_quotes(system)["usd"].price_toman == 100


def test_school_progress_is_per_user(engine) -> None:  # type: ignore[no-untyped-def]
    from app.models import LessonProgress, SchoolStats

    for user in (1, 2):
        with user_session(Session(engine), user) as s:
            s.add(SchoolStats(xp=user * 10, knowledge=0, streak=0, best_streak=0))
            s.add(LessonProgress(lesson_slug="money", course="basics", best_correct=user,
                                 attempts=1))
            s.commit()
    with user_session(Session(engine), 2) as s:
        assert [x.xp for x in s.scalars(select(SchoolStats))] == [20]
        assert [p.best_correct for p in s.scalars(select(LessonProgress))] == [2]
