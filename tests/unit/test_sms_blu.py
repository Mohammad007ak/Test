"""پارسر بانک بلو؛ نمونه از پیامک واقعی (نام کاربر عوض شده). پیامک بلو شماره حساب ندارد."""

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Account, Transaction
from app.sms.parsers import PARSERS
from app.sms.parsers.blu import BluParser
from app.sms.pipeline import NEEDS_ACCOUNT, choose_account, ingest
from app.sms.text import mask_numbers, prepare
from tests.unit.conftest import memory_session

NOW = datetime(2026, 10, 3, 9, 0, tzinfo=UTC)

WITHDRAWAL = (Path(__file__).parent.parent / "fixtures" / "sms" / "blu" / "withdrawal.txt"
              ).read_text(encoding="utf-8")
DEPOSIT = (Path(__file__).parent.parent / "fixtures" / "sms" / "blu" / "deposit.txt"
           ).read_text(encoding="utf-8")
T0 = datetime(2026, 10, 1, 12, 43, tzinfo=UTC)


def test_withdrawal() -> None:
    text = mask_numbers(prepare(WITHDRAWAL))
    parser = BluParser()
    assert parser.can_parse(text)
    parsed = parser.parse(text, NOW)
    assert (parsed.bank, parsed.account_mask, parsed.direction) == ("blu", "", "out")
    assert parsed.amount_rial == 30_000_000
    assert parsed.balance_after_rial == 86_552_338
    assert parsed.description == "برداشت پول"
    assert parsed.occurred_at == datetime(2026, 10, 1, 12, 42, tzinfo=UTC)  # ۹ مهر ۱۶:۱۲ تهران


def test_deposit_real_sample() -> None:
    deposit = (Path(__file__).parent.parent / "fixtures" / "sms" / "blu" / "deposit.txt"
               ).read_text(encoding="utf-8")
    parsed = BluParser().parse(mask_numbers(prepare(deposit)), NOW)
    assert (parsed.direction, parsed.amount_rial) == ("in", 15_000_000)
    assert parsed.balance_after_rial == 16_570_338
    assert parsed.description == "واریز پول"
    assert parsed.occurred_at == datetime(2026, 9, 28, 10, 17, tzinfo=UTC)  # ۶ مهر ۱۳:۴۷ تهران


def test_unknown_blu_message_is_not_guessed() -> None:
    with pytest.raises(ValueError):
        BluParser().parse(prepare("بلو\nکد ورود شما 12345"), NOW)


def test_not_other_banks() -> None:
    assert not BluParser().can_parse(prepare("بانک سامان\nبرداشت مبلغ 1,000"))


@pytest.fixture
def session() -> Iterator[Session]:
    with memory_session() as s:
        yield s


def test_first_blu_sms_asks_for_account_then_creates_it(session: Session) -> None:
    assert any(isinstance(p, BluParser) for p in PARSERS)
    result = ingest(session, WITHDRAWAL, T0)
    assert result.status == "failed" and result.sms.error == NEEDS_ACCOUNT
    choose_account(session, result.sms, None)
    account = session.scalars(select(Account)).one()
    assert (account.bank, account.account_mask, account.balance_toman) == ("blu", "", 8_655_234)


def test_uses_existing_blu_account_even_if_it_has_digits(session: Session) -> None:
    session.add(Account(bank="blu", account_mask="9999", label="بلو اصلی", balance_toman=1))
    session.commit()
    ingest(session, WITHDRAWAL, T0)
    account = session.scalars(select(Account)).one()
    assert account.label == "بلو اصلی" and account.balance_toman == 8_655_234
    assert session.scalars(select(Transaction)).one().amount_toman == 3_000_000


def test_ambiguous_when_several_blu_accounts(session: Session) -> None:
    session.add_all([Account(bank="blu", account_mask="1111", balance_toman=1),
                     Account(bank="blu", account_mask="2222", balance_toman=1)])
    session.commit()
    result = ingest(session, WITHDRAWAL, T0)
    assert result.status == "failed" and result.sms.error == NEEDS_ACCOUNT
    choose_account(session, result.sms, session.scalars(select(Account)).all()[1].id)
    assert session.scalars(select(Account)).all()[1].balance_toman == 8_655_234
    # بلو شماره ندارد: با چند حساب هر بار پرسیده می‌شود، چیزی به خاطر سپرده نمی‌شود
    assert ingest(session, DEPOSIT, T0).sms.error == NEEDS_ACCOUNT
