"""خط پردازش با یک «بانک نمونه» ساختگی؛ پارسرهای واقعی پس از رسیدن نمونه پیامک‌ها."""

import re
from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Account, AccountAlias, SmsInbox, SmsTemplate, Transaction
from app.sms.parsers.base import ParsedSms
from app.sms.pipeline import (
    LLM_DAILY_LIMIT,
    NEEDS_ACCOUNT,
    NEW_TEMPLATE,
    choose_account,
    complete_manually,
    held_reading,
    ingest,
)
from app.sms.templates import SmsReading
from tests.unit.conftest import memory_session

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


UNKNOWN = "بانکی ناشناخته حساب 0123456789012\nواریز 1,000,000 ریال\nمانده 3,000,000"
UNKNOWN_TEMPLATE = "بانکی ناشناخته حساب {account}\nواریز {amount} ریال\nمانده {balance}"


class FakeLLM:
    name = "fake"

    def __init__(self, template: str = UNKNOWN_TEMPLATE) -> None:
        self.seen: list[str] = []
        self.template = template

    def read_sms(self, masked_text: str) -> SmsReading | None:
        self.seen.append(masked_text)
        return SmsReading("melli", "in", 1_000_000, 3_000_000, "rial", self.template, "واریز")


@pytest.fixture
def session() -> Iterator[Session]:
    with memory_session() as s:
        yield s


def seed(session: Session, bank: str = "mellat", mask: str = "1234", label: str = "") -> Account:
    account = Account(bank=bank, account_mask=mask, label=label or None, balance_toman=1)
    session.add(account)
    session.commit()
    return account


def test_parsed_sms_updates_known_account(session: Session) -> None:
    seed(session)
    result = ingest(session, SMS, T0, parsers=[SampleBankParser()])
    assert result.status == "parsed"
    account = session.scalars(select(Account)).one()
    assert (account.bank, account.account_mask) == ("mellat", "1234")
    assert (account.balance_toman, account.balance_source) == (812_500, "sms")
    tx = session.scalars(select(Transaction)).one()
    assert (tx.direction, tx.amount_toman, tx.balance_after_toman) == ("out", 25_000, 812_500)
    assert tx.sms_id == result.sms.id


def test_first_sms_of_unknown_account_asks_only_for_account(session: Session) -> None:
    result = ingest(session, SMS, T0, parsers=[SampleBankParser()])
    assert result.status == "failed" and result.sms.error == NEEDS_ACCOUNT
    assert session.scalars(select(Account)).all() == []  # حساب خودسرانه ساخته نمی‌شود
    reading = held_reading(result.sms)
    assert reading is not None and (reading.amount_rial, reading.account_mask) == (250_000, "1234")
    choose_account(session, result.sms, None)  # «حساب تازه بساز»
    account = session.scalars(select(Account)).one()
    assert (account.bank, account.account_mask) == ("mellat", "1234")
    assert account.balance_toman == 812_500
    assert result.sms.parse_status == "parsed" and result.sms.parsed_json is None
    # پیامک بعدی همین حساب بی‌سؤال ثبت می‌شود
    again = ingest(session, SMS.replace("250,000", "1,000"), T0, parsers=[SampleBankParser()])
    assert again.status == "parsed"


def test_chosen_account_is_remembered_for_that_card(session: Session) -> None:
    salary = seed(session, mask="9999", label="حقوق")
    result = ingest(session, SMS, T0, parsers=[SampleBankParser()])
    choose_account(session, result.sms, salary.id)
    assert session.scalars(select(AccountAlias)).one().account_mask == "1234"
    assert salary.balance_toman == 812_500
    again = ingest(session, SMS.replace("250,000", "1,000"), T0, parsers=[SampleBankParser()])
    assert again.status == "parsed" and again.transaction is not None
    assert again.transaction.account_id == salary.id
    assert len(session.scalars(select(Account)).all()) == 1


def test_raw_card_number_is_never_stored(session: Session) -> None:
    ingest(session, SMS, T0, parsers=[SampleBankParser()])
    stored = session.scalars(select(SmsInbox)).one().text_masked
    assert "6037991234561234" not in stored and "1234" in stored


def test_duplicate_is_recorded_as_ignored_and_not_applied_twice(session: Session) -> None:
    seed(session)
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
    ingest(session, UNKNOWN, T0, parsers=[], llm=llm)
    assert "0123456789012" not in llm.seen[0]


def test_new_format_is_learned_once_and_confirmed_by_choosing_account(session: Session) -> None:
    llm = FakeLLM()
    first = ingest(session, UNKNOWN, T0, parsers=[], llm=llm)
    assert first.status == "failed" and first.sms.error == NEW_TEMPLATE
    template = session.scalars(select(SmsTemplate)).one()
    assert template.status == "pending" and "0123" not in template.pattern
    # همان قالب پیش از تأیید دوباره به LLM نمی‌رود
    second = ingest(session, UNKNOWN.replace("1,000,000", "2,000"), T0, parsers=[], llm=llm)
    assert len(llm.seen) == 1 and second.sms.error == NEW_TEMPLATE
    choose_account(session, first.sms, None)
    assert template.status == "active"
    choose_account(session, second.sms, session.scalars(select(Account)).one().id)
    # پس از تأیید: بدون LLM و بدون سؤال
    third = ingest(session, UNKNOWN.replace("1,000,000", "5,000"), T0, parsers=[], llm=llm)
    assert third.status == "parsed" and third.sms.parser == f"template:{template.id}"
    assert len(llm.seen) == 1
    assert third.transaction is not None and third.transaction.amount_toman == 500


def test_learned_template_is_shared_between_users(session: Session) -> None:
    from app.db import user_session
    from app.models import User

    llm = FakeLLM()
    choose_account(session, ingest(session, UNKNOWN, T0, parsers=[], llm=llm).sms, None)
    session.add(User(id=2, phone="09120000002"))
    session.commit()
    user_session(session, 2)
    other = ingest(session, UNKNOWN.replace("1,000,000", "7,000"), T0, parsers=[], llm=llm)
    assert len(llm.seen) == 1  # کاربر دوم LLM لازم ندارد
    assert other.sms.error == NEEDS_ACCOUNT  # فقط حسابش را می‌پرسد
    assert held_reading(other.sms) is not None


def test_template_that_does_not_reproduce_reading_goes_to_queue(session: Session) -> None:
    llm = FakeLLM(template="بانکی ناشناخته حساب {account}\nواریز {amount} ریال\nمانده 3,000,000")
    result = ingest(session, UNKNOWN, T0, parsers=[], llm=llm)
    assert result.status == "failed" and result.sms.parsed_json is None
    assert "عدد" in (result.sms.error or "")
    assert session.scalars(select(SmsTemplate)).all() == []


def test_wrong_reading_rejects_the_new_template(session: Session) -> None:
    llm = FakeLLM()
    sms = ingest(session, UNKNOWN, T0, parsers=[], llm=llm).sms
    complete_manually(session, sms, ParsedSms("melli", "9012", "out", 1_000_000))
    assert session.scalars(select(SmsTemplate)).one().status == "rejected"
    ingest(session, UNKNOWN.replace("1,000,000", "9,000"), T0, parsers=[], llm=llm)
    assert len(llm.seen) == 2  # قالب کنارگذاشته دیگر استفاده نمی‌شود


def test_llm_daily_limit(session: Session) -> None:
    llm = FakeLLM(template="{amount}")  # قالب بی‌فایده: هر بار به LLM می‌رود
    for i in range(LLM_DAILY_LIMIT + 3):
        ingest(session, f"پیامک {'ا' * i} {i + 1},000", T0, parsers=[], llm=llm)
    assert len(llm.seen) == LLM_DAILY_LIMIT


def test_older_sms_does_not_overwrite_newer_balance(session: Session) -> None:
    seed(session)
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
