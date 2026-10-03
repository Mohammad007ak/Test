"""پارسر بانک سامان؛ نمونه‌ها از پیامک واقعی با شماره حساب ساختگی هم‌قالب."""

from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import select

from app.db import Base, make_engine, make_session_factory
from app.models import Account, SmsInbox, Transaction
from app.sms.parsers import PARSERS
from app.sms.parsers.saman import SamanParser
from app.sms.pipeline import ingest
from app.sms.text import mask_numbers, prepare

NOW = datetime(2026, 10, 3, 9, 0, tzinfo=UTC)

FIXTURES = Path(__file__).parent.parent / "fixtures" / "sms" / "saman"
WITHDRAWAL = (FIXTURES / "withdrawal_transfer.txt").read_text(encoding="utf-8")


def masked(raw: str) -> str:
    return mask_numbers(prepare(raw))


def test_invisible_direction_marks_are_removed() -> None:
    assert "‪" not in prepare(WITHDRAWAL) and "‬" not in prepare(WITHDRAWAL)
    assert "‌" in prepare("حساب‌ها")  # نیم‌فاصله فارسی می‌ماند


def test_withdrawal_transfer() -> None:
    parser = SamanParser()
    text = masked(WITHDRAWAL)
    assert parser.can_parse(text)
    parsed = parser.parse(text, NOW)
    assert parsed.bank == "saman"
    assert (parsed.account_prefix, parsed.account_mask) == ("814", "5671")
    assert parsed.direction == "out"
    assert parsed.amount_rial == 127_100
    assert parsed.balance_after_rial == 46_294_698
    assert parsed.description == "انتقال وجه"
    assert parsed.occurred_at == datetime(2026, 10, 3, 8, 40, 53, tzinfo=UTC)  # ۱۲:۱۰:۵۳ تهران


def test_other_banks_are_not_claimed() -> None:
    assert not SamanParser().can_parse(masked("بانک ملت\nبرداشت 1,000"))


def test_unexpected_saman_format_goes_to_queue_instead_of_guessing() -> None:
    with pytest.raises(ValueError):
        SamanParser().parse(masked("بانک سامان\nرمز پویا شما 123456"), NOW)


def test_registered_and_applied_end_to_end() -> None:
    assert any(isinstance(p, SamanParser) for p in PARSERS)
    engine = make_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with make_session_factory(engine)() as session:
        result = ingest(session, WITHDRAWAL, datetime(2026, 10, 3, 8, 41, tzinfo=UTC))
        assert result.status == "parsed" and result.sms.parser == "saman"
        account = session.scalars(select(Account)).one()
        assert (account.bank, account.account_prefix, account.account_mask) == (
            "saman", "814", "5671")
        assert account.balance_toman == 4_629_470  # ۴۶٬۲۹۴٬۶۹۸ ریال
        tx = session.scalars(select(Transaction)).one()
        assert (tx.direction, tx.amount_toman) == ("out", 12_710)
        assert "1234567" not in session.scalars(select(SmsInbox)).one().text_masked


def test_two_saman_accounts_with_same_last_four_stay_separate() -> None:
    engine = make_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    second = WITHDRAWAL.replace("814-20-", "2137-800-").replace("46,294,698", "16,225,026")
    with make_session_factory(engine)() as session:
        ingest(session, WITHDRAWAL, datetime(2026, 10, 3, 8, 41, tzinfo=UTC))
        ingest(session, second, datetime(2026, 10, 3, 8, 42, tzinfo=UTC))
        accounts = {a.account_prefix: a.balance_toman for a in session.scalars(select(Account))}
        assert accounts == {"814": 4_629_470, "2137": 1_622_503}


def test_manual_account_without_prefix_is_adopted() -> None:
    engine = make_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with make_session_factory(engine)() as session:
        session.add(Account(bank="saman", account_mask="5671", label="جاری", balance_toman=1))
        session.commit()
        ingest(session, WITHDRAWAL, datetime(2026, 10, 3, 8, 41, tzinfo=UTC))
        account = session.scalars(select(Account)).one()
        assert (account.label, account.account_prefix) == ("جاری", "814")
