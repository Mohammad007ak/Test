"""اتصال SQLAlchemy به SQLite."""

from collections.abc import Iterator
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, event, or_
from sqlalchemy.engine import Engine
from sqlalchemy.orm import (
    DeclarativeBase,
    ORMExecuteState,
    Session,
    sessionmaker,
    with_loader_criteria,
)


class Base(DeclarativeBase):
    pass


USER_KEY = "user_id"
NOBODY = -1  # نشست بدون کاربر وارد شده: هیچ داده شخصی‌ای پیدا نمی‌شود


def user_session(session: Session, user_id: int | None) -> Session:
    """نشست محدود به یک کاربر: خواندن فقط داده او، ردیف تازه به نام او.

    نشست بدون این برچسب «سیستمی» است (به‌روزرسانی قیمت‌ها) و همه را می‌بیند.
    """
    session.info[USER_KEY] = NOBODY if user_id is None else user_id
    return session


@event.listens_for(Session, "do_orm_execute")
def _scope_reads(state: ORMExecuteState) -> None:
    user_id = state.session.info.get(USER_KEY)
    if user_id is None or not state.is_select or state.is_column_load or state.is_relationship_load:
        return
    from app.models import PriceQuote, UserOwned

    state.statement = state.statement.options(
        with_loader_criteria(UserOwned, lambda cls: cls.user_id == user_id, include_aliases=True),
        with_loader_criteria(PriceQuote, lambda cls: or_(cls.user_id.is_(None),
                                                         cls.user_id == user_id)),
    )


@event.listens_for(Session, "before_flush")
def _stamp_owner(session: Session, _context: Any, _instances: Any) -> None:
    user_id = session.info.get(USER_KEY)
    if user_id is None or user_id == NOBODY:
        return
    from app.models import PriceQuote, UserOwned

    for obj in session.new:
        owned = isinstance(obj, UserOwned) or (isinstance(obj, PriceQuote)
                                               and obj.source == "manual")
        if owned and getattr(obj, "user_id", None) is None:
            obj.user_id = user_id


def make_engine(url: str) -> Engine:
    if url.startswith("sqlite:///") and not url.startswith("sqlite:///:memory:"):
        Path(url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(url, connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection, _record) -> None:  # type: ignore[no-untyped-def]
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    return engine


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)


def session_scope(factory: sessionmaker[Session]) -> Iterator[Session]:
    with factory() as session:
        yield session
