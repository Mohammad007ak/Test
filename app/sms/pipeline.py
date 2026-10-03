"""خط پردازش مشترک پیامک (SPEC: «دریافت و پارس پیامک بانکی»).

یکسان‌سازی ← پوشاندن شماره‌ها ← حذف تکراری ← پارسرهای بانکی ← بازگشت به LLM ←
اعتبارسنجی و ثبت ← صف بررسی برای پیامک نامفهوم.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.money import rial_to_toman
from app.models import Account, SmsInbox, Transaction
from app.sms.llm import DisabledLLM, LLMClient
from app.sms.parsers import PARSERS, BankParser, ParsedSms
from app.sms.text import content_hash, mask_numbers, prepare

NO_PARSER = "هیچ پارسری این پیامک را نشناخت"


@dataclass(frozen=True)
class IngestResult:
    status: str  # parsed، failed یا duplicate
    sms: SmsInbox
    transaction: Transaction | None = None


def _validate(parsed: ParsedSms) -> str | None:
    if parsed.direction not in ("in", "out"):
        return f"جهت نامعتبر: {parsed.direction}"
    if parsed.amount_rial <= 0:
        return "مبلغ نامعتبر"
    if not (len(parsed.account_mask) == 4 and parsed.account_mask.isdigit()):
        return "۴ رقم آخر حساب نامعتبر"
    if not parsed.bank:
        return "بانک مشخص نیست"
    return None


def _account(session: Session, bank: str, mask: str) -> Account:
    account = session.scalars(select(Account).where(Account.bank == bank,
                                                    Account.account_mask == mask)).first()
    if account is None:
        account = Account(bank=bank, account_mask=mask, balance_toman=0, balance_source="sms")
        session.add(account)
        session.flush()
    return account


def _apply(session: Session, sms: SmsInbox, parsed: ParsedSms, parser: str) -> Transaction:
    account = _account(session, parsed.bank, parsed.account_mask)
    occurred = parsed.occurred_at or sms.received_at
    balance = rial_to_toman(parsed.balance_after_rial) if parsed.balance_after_rial else None
    transaction = Transaction(
        account_id=account.id, direction=parsed.direction,
        amount_toman=rial_to_toman(parsed.amount_rial), balance_after_toman=balance,
        occurred_at=occurred, description=parsed.description or None, sms_id=sms.id)
    session.add(transaction)
    # پیامک دیرتر رسیده‌ی قدیمی، مانده تازه‌تر را بازنویسی نمی‌کند
    if balance is not None and (account.balance_updated_at is None
                                or occurred >= account.balance_updated_at):
        account.balance_toman = balance
        account.balance_updated_at = occurred
        account.balance_source = "sms"
    sms.parse_status, sms.parser, sms.error = "parsed", parser, None
    return transaction


def _try_parsers(text: str, parsers: Sequence[BankParser],
                 llm: LLMClient) -> tuple[ParsedSms | None, str, list[str]]:
    errors: list[str] = []
    for parser in parsers:
        if not parser.can_parse(text):
            continue
        try:
            parsed = parser.parse(text)
        except Exception as exc:  # یک پارسر خراب نباید خط پردازش را بشکند
            errors.append(f"{parser.name}: {exc}")
            continue
        if problem := _validate(parsed):
            errors.append(f"{parser.name}: {problem}")
            continue
        return parsed, parser.name, errors
    parsed = llm.parse_sms(text)
    if parsed is not None:
        if problem := _validate(parsed):
            errors.append(f"llm: {problem}")
        else:
            return parsed, f"llm:{llm.name}", errors
    return None, "", errors


def ingest(session: Session, raw_text: str, received_at: datetime,
           parsers: Sequence[BankParser] = PARSERS,
           llm: LLMClient | None = None) -> IngestResult:
    text = mask_numbers(prepare(raw_text))
    digest = content_hash(text)
    sms = SmsInbox(text_masked=text, received_at=received_at, content_hash=digest,
                   parse_status="failed")
    duplicate = session.scalars(select(SmsInbox.id).where(
        SmsInbox.content_hash == digest, SmsInbox.parse_status != "ignored")).first()
    if duplicate is not None:
        sms.parse_status, sms.error = "ignored", f"تکراری (پیامک #{duplicate})"
        session.add(sms)
        session.commit()
        return IngestResult("duplicate", sms)

    session.add(sms)
    session.flush()
    parsed, parser_name, errors = _try_parsers(text, parsers, llm or DisabledLLM())
    if parsed is None:
        sms.error = " · ".join(errors) or NO_PARSER
        session.commit()
        return IngestResult("failed", sms)
    transaction = _apply(session, sms, parsed, parser_name)
    session.commit()
    return IngestResult("parsed", sms, transaction)


def complete_manually(session: Session, sms: SmsInbox, parsed: ParsedSms) -> Transaction:
    """تکمیل دستی پیامکی که در صف بررسی مانده."""
    if problem := _validate(parsed):
        raise ValueError(problem)
    transaction = _apply(session, sms, parsed, "manual")
    session.commit()
    return transaction


def ignore(session: Session, sms: SmsInbox) -> None:
    sms.parse_status, sms.error = "ignored", "نادیده گرفته شد"
    session.commit()
