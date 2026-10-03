"""خط پردازش با یک «بانک نمونه» ساختگی؛ پارسرهای واقعی پس از رسیدن نمونه پیامک‌ها."""

import re
from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import Base, make_engine, make_session_factory
from app.models import Account, SmsInbox, Transaction
from app.sms.parsers.base import ParsedSms
from app.sms.pipeline import complete_manually, ingest

T0 = datetime(2026, 10, 3, 6, 0, tzinfo=UTC)
SMS = "بانک نمونه\nکارت 6037991234561234\nبرداشت 250,000\nمانده 8,125,000"


class SampleBankParser:
    name = "sample"

    def can_parse(self, text: str) -> bool:
        return text.startswith("بانک نمونه")

    def parse(self, text: str, received_at: datetime) -> ParsedSms:
        amount = re.search(r"(برداشت|واریز) ([\d,]+)", text)
        balance = re.search(r"مانده ([\d,]+)", text)
        mask = re.search(r"\*+(\d{4})", text)
        assert amount and mask
        return ParsedSms(
            bank="mellat", account_mask=mask.group(1),
            direction="out" if amount.group(1) == "برداشت" else "in",
            amount_rial=int(amount.group(2).replace(",", "")),
            balance_after_rial=int(balance.group(1).replace(",", "")) if balance else None,
        )


class FakeLLM:
    name = "fake"

    def __init__(self) -> None:
        self.seen: list[str] = []

    def parse_sms(self, masked_text: str) -> ParsedSms | None:
        self.seen.append(masked_text)
        return ParsedSms("melli", "5678", "in", 1_000_000, 3_000_000)


@pytest.fixture
def session() -> Iterator[Session]:
    engine = make_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with make_session_factory(engine)() as s:
        yield s


def test_parsed_sms_creates_account_transaction_and_balance(session: Session) -> None:
    result = ingest(session, SMS, T0, parsers=[SampleBankParser()])
    assert result.status == "parsed"
    account = session.scalars(select(Account)).one()
    assert (account.bank, account.account_mask) == ("mellat", "1234")
    assert (account.balance_toman, account.balance_source) == (812_500, "sms")
    tx = session.scalars(select(Transaction)).one()
    assert (tx.direction, tx.amount_toman, tx.balance_after_toman) == ("out", 25_000, 812_500)
    assert tx.sms_id == result.sms.id


def test_raw_card_number_is_never_stored(session: Session) -> None:
    ingest(session, SMS, T0, parsers=[SampleBankParser()])
    stored = session.scalars(select(SmsInbox)).one().text_masked
    assert "6037991234561234" not in stored and "1234" in stored


def test_duplicate_is_recorded_as_ignored_and_not_applied_twice(session: Session) -> None:
    ingest(session, SMS, T0, parsers=[SampleBankParser()])
    again = ingest(session, SMS + "  ", T0, parsers=[SampleBankParser()])
    assert again.status == "duplicate"
    assert again.sms.parse_status == "ignored"
    assert len(session.scalars(select(Transaction)).all()) == 1


def test_unknown_sms_goes_to_review_queue(session: Session) -> None:
    result = ingest(session, "پیامک تبلیغاتی", T0, parsers=[SampleBankParser()])
    assert result.status == "failed"
    assert result.sms.parse_status == "failed" and result.sms.error


def test_llm_fallback_gets_only_masked_text(session: Session) -> None:
    llm = FakeLLM()
    result = ingest(session, "بانکی ناشناخته حساب 0123456789012 واریز", T0, parsers=[], llm=llm)
    assert result.status == "parsed" and result.sms.parser == "llm:fake"
    assert "0123456789012" not in llm.seen[0]


def test_older_sms_does_not_overwrite_newer_balance(session: Session) -> None:
    ingest(session, SMS, T0, parsers=[SampleBankParser()])
    older = SMS.replace("برداشت 250,000", "واریز 10,000").replace("8,125,000", "1,000")
    ingest(session, older, datetime(2026, 10, 2, tzinfo=UTC), parsers=[SampleBankParser()])
    assert session.scalars(select(Account)).one().balance_toman == 812_500
    assert len(session.scalars(select(Transaction)).all()) == 2  # تراکنش ثبت می‌شود


def test_existing_manual_account_is_reused(session: Session) -> None:
    session.add(Account(bank="mellat", account_mask="1234", label="حقوق", balance_toman=1))
    session.commit()
    ingest(session, SMS, T0, parsers=[SampleBankParser()])
    account = session.scalars(select(Account)).one()
    assert account.label == "حقوق" and account.balance_toman == 812_500


def test_failing_parser_falls_through_to_queue(session: Session) -> None:
    class Broken(SampleBankParser):
        def parse(self, text: str, received_at: datetime) -> ParsedSms:
            raise ValueError("قالب ناشناخته")

    result = ingest(session, SMS, T0, parsers=[Broken()])
    assert result.status == "failed" and "قالب ناشناخته" in (result.sms.error or "")


def test_manual_completion_from_queue(session: Session) -> None:
    sms = ingest(session, "پیامک ناشناخته", T0, parsers=[]).sms
    complete_manually(session, sms, ParsedSms("saman", "9876", "in", 50_000_000, 90_000_000))
    assert sms.parse_status == "parsed" and sms.parser == "manual"
    account = session.scalars(select(Account)).one()
    assert (account.bank, account.balance_toman) == ("saman", 9_000_000)


def test_invalid_parser_output_is_rejected(session: Session) -> None:
    class Bad(SampleBankParser):
        def parse(self, text: str, received_at: datetime) -> ParsedSms:
            return ParsedSms("mellat", "12", "sideways", -5)

    assert ingest(session, SMS, T0, parsers=[Bad()]).status == "failed"
