from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from sqlalchemy.orm import Session

from app.db import Base, make_engine, make_session_factory, user_session
from app.models import User
from app.sms.importer import import_text, split_messages

FILE = """--- 2026-10-03T09:42:00+03:30
بانک ملت
برداشت 250,000
--- ۱۴۰۵/۰۷/۱۱ ۱۰:۱۵
پیامک دوم
--- 2026-10-03 11:00
"""


def test_split_messages_with_iso_and_jalali_dates() -> None:
    messages = split_messages(FILE)
    assert [m.text for m in messages] == ["بانک ملت\nبرداشت 250,000", "پیامک دوم"]
    assert messages[0].received_at == datetime(2026, 10, 3, 6, 12, tzinfo=UTC)
    assert messages[1].received_at == datetime(2026, 10, 3, 6, 45, tzinfo=UTC)  # تهران


def test_text_before_first_marker_is_ignored() -> None:
    assert [m.text for m in split_messages("زباله\n--- 2026-10-03 09:00\nپیام")] == ["پیام"]


@pytest.fixture
def session() -> Iterator[Session]:
    engine = make_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with make_session_factory(engine)() as s:
        s.add(User(id=1, phone="09120000001"))
        s.commit()
        yield user_session(s, 1)


def test_import_text_counts(session: Session) -> None:
    counts = import_text(session, FILE)
    assert counts == {"parsed": 0, "failed": 2, "duplicate": 0, "ignored": 0}
    assert import_text(session, FILE)["duplicate"] == 2


def test_import_skips_secret_messages_without_storing(session: Session) -> None:
    from sqlalchemy import select

    from app.models import SmsInbox

    counts = import_text(session, "--- 2026-10-03 09:00\nرمز پویا شما 482913\n")
    assert counts["ignored"] == 1
    assert session.scalars(select(SmsInbox)).first() is None
