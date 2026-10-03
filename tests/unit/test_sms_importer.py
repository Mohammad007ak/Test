from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import Base, make_engine, make_session_factory
from app.models import SmsInbox
from app.sms.importer import import_new_from_file, import_text, split_messages

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
        yield s


def test_import_text_counts(session: Session) -> None:
    counts = import_text(session, FILE)
    assert counts == {"parsed": 0, "failed": 2, "duplicate": 0}
    assert import_text(session, FILE)["duplicate"] == 2


def test_watched_file_imports_only_new_messages(session: Session, tmp_path: Path) -> None:
    path = tmp_path / "bank_sms.txt"
    path.write_text(FILE, encoding="utf-8")
    assert import_new_from_file(session, path)["failed"] == 2
    assert import_new_from_file(session, path) == {"parsed": 0, "failed": 0, "duplicate": 0}
    with path.open("a", encoding="utf-8") as f:
        f.write("--- 2026-10-03 12:00\nپیامک سوم\n")
    assert import_new_from_file(session, path)["failed"] == 1
    assert len(session.scalars(select(SmsInbox)).all()) == 3  # تکراری ساخته نشد


def test_rotated_file_starts_over(session: Session, tmp_path: Path) -> None:
    path = tmp_path / "bank_sms.txt"
    path.write_text(FILE, encoding="utf-8")
    import_new_from_file(session, path)
    path.write_text("--- 2026-10-04 08:00\nپیامک تازه\n", encoding="utf-8")  # فایل خالی و از نو
    assert import_new_from_file(session, path)["failed"] == 1


def test_missing_file_is_not_an_error(session: Session, tmp_path: Path) -> None:
    assert import_new_from_file(session, tmp_path / "none.txt") is None
