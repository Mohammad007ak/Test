"""خط پردازش مشترک پیامک (SPEC: «دریافت و پارس پیامک بانکی»).

یکسان‌سازی ← پوشاندن شماره‌ها ← حذف تکراری ← پارسرهای بانکی ← قالب‌های یادگرفته ←
بازگشت به LLM (که قالب تازه می‌سازد) ← اعتبارسنجی ← حساب ← ثبت.

پیامکی که خوانده شد ولی حسابش معلوم نیست، یا قالبش تازه است و هنوز تأیید نشده، در صف
می‌ماند تا کاربر فقط حساب را انتخاب کند (choose_account). پیامکی که خوانده نشد، دستی
تکمیل می‌شود (complete_manually).
"""

import hashlib
import json
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import services
from app.domain.money import rial_to_toman
from app.models import Account, AccountAlias, SmsInbox, SmsTemplate, Transaction, utcnow
from app.sms.llm import DisabledLLM, LLMClient
from app.sms.parsers import PARSERS, BankParser, ParsedSms
from app.sms.templates import LearnedTemplate, TemplateError, learn, read_with
from app.sms.text import content_hash, mask_numbers, prepare

NO_PARSER = "هیچ پارسری این پیامک را نشناخت"
NEEDS_ACCOUNT = "این پیامک مال کدام حساب است؟"
NEW_TEMPLATE = "قالب تازه: خوانده را ببین و حساب را انتخاب کن"
LLM_DAILY_LIMIT = 20  # پیامک ناشناخته در روز برای هر کاربر (هزینه مدل زبانی)
LLM_COUNTER_KEY = "sms_llm_day"


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
    if parsed.account_mask and not (len(parsed.account_mask) == 4
                                    and parsed.account_mask.isdigit()):
        return "۴ رقم آخر حساب نامعتبر"
    if parsed.account_prefix and not (len(parsed.account_prefix) <= 4
                                      and parsed.account_prefix.isdigit()):
        return "ابتدای شماره حساب نامعتبر"
    if not parsed.bank:
        return "بانک مشخص نیست"
    return None


class AmbiguousAccount(ValueError):
    pass


def find_account(session: Session, bank: str, mask: str, prefix: str = "") -> Account | None:
    """حساب پیامک؛ None اگر هنوز معلوم نیست (کاربر انتخاب می‌کند)."""
    if not mask:  # پیامک بدون شماره حساب (مثل بلو): تنها حساب همان بانک
        accounts = session.scalars(select(Account).where(Account.bank == bank)).all()
        if len(accounts) > 1:
            raise AmbiguousAccount("این بانک چند حساب دارد و پیامک شماره حساب ندارد")
        return accounts[0] if accounts else _alias(session, bank, "", "")
    same_end = session.scalars(select(Account).where(Account.bank == bank,
                                                     Account.account_mask == mask)).all()
    account = next((a for a in same_end if a.account_prefix == prefix), None)
    if account is None and prefix:
        # حسابی که دستی و بدون ابتدای شماره ثبت شده، اگر یکتاست همان است
        unprefixed = [a for a in same_end if not a.account_prefix]
        if len(unprefixed) == 1:
            account = unprefixed[0]
            account.account_prefix = prefix
    return account or _alias(session, bank, mask, prefix)


def _alias(session: Session, bank: str, mask: str, prefix: str) -> Account | None:
    alias = session.scalars(select(AccountAlias).where(
        AccountAlias.bank == bank, AccountAlias.account_mask == mask,
        AccountAlias.account_prefix == prefix)).first()
    return session.get(Account, alias.account_id) if alias is not None else None


def _new_account(session: Session, parsed: ParsedSms) -> Account:
    account = Account(bank=parsed.bank, account_mask=parsed.account_mask,
                      account_prefix=parsed.account_prefix, balance_toman=0,
                      balance_source="sms")
    session.add(account)
    session.flush()
    return account


def _apply(session: Session, sms: SmsInbox, parsed: ParsedSms, parser: str,
           account: Account) -> Transaction:
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
    sms.parsed_json = None
    return transaction


def _try_parsers(text: str, received_at: datetime, parsers: Sequence[BankParser],
                 ) -> tuple[ParsedSms | None, str, list[str]]:
    errors: list[str] = []
    for parser in parsers:
        if not parser.can_parse(text):
            continue
        try:
            parsed = parser.parse(text, received_at)
        except Exception as exc:  # یک پارسر خراب نباید خط پردازش را بشکند
            errors.append(f"{parser.name}: {exc}")
            continue
        if problem := _validate(parsed):
            errors.append(f"{parser.name}: {problem}")
            continue
        return parsed, parser.name, errors
    return None, "", errors


def _learned(row: SmsTemplate) -> LearnedTemplate:
    return LearnedTemplate(pattern=row.pattern, bank=row.bank, direction=row.direction,
                           unit=row.unit, label=row.label)


def _try_templates(session: Session, text: str,
                   received_at: datetime) -> tuple[ParsedSms, SmsTemplate] | None:
    """قالب‌های فعال اول، بعد قالب‌های منتظر تأیید (تا همان قالب دوباره به LLM نرود)."""
    rows = session.scalars(select(SmsTemplate).where(SmsTemplate.status != "rejected")
                           .order_by(SmsTemplate.status, SmsTemplate.id)).all()
    for row in rows:
        try:
            parsed = read_with(_learned(row), text, received_at)
        except (TemplateError, ValueError):
            continue
        if parsed is not None and _validate(parsed) is None:
            return parsed, row
    return None


def _llm_allowed(session: Session) -> bool:
    """سقف روزانه خواندن با مدل زبانی برای هر کاربر."""
    today = utcnow().date().isoformat()
    day, _, count = (services.get_user_setting(session, LLM_COUNTER_KEY) or "").partition(":")
    used = int(count) if day == today and count.isdigit() else 0
    if used >= LLM_DAILY_LIMIT:
        return False
    services.set_user_setting(session, LLM_COUNTER_KEY, f"{today}:{used + 1}")
    return True


def _try_llm(session: Session, text: str, received_at: datetime, llm: LLMClient,
             errors: list[str]) -> tuple[ParsedSms, SmsTemplate] | None:
    if isinstance(llm, DisabledLLM) or not _llm_allowed(session):
        return None
    reading = llm.read_sms(text)
    if reading is None:
        errors.append("llm: تراکنش بانکی نیست یا خوانده نشد")
        return None
    try:
        template = learn(text, reading)
    except TemplateError as exc:  # خوانده بدون قالبِ بازتولیدکننده پذیرفته نمی‌شود
        errors.append(f"llm: {exc}")
        return None
    digest = hashlib.sha256(template.pattern.encode("utf-8")).hexdigest()
    row = session.scalars(select(SmsTemplate).where(SmsTemplate.pattern_hash == digest)).first()
    if row is None:
        row = SmsTemplate(pattern=template.pattern, pattern_hash=digest, bank=template.bank,
                          direction=template.direction, unit=template.unit,
                          label=template.label, status="pending")
        session.add(row)
        session.flush()
    elif row.status == "rejected":
        errors.append("llm: این قالب قبلاً اشتباه شناخته شده")
        return None
    parsed = read_with(_learned(row), text, received_at)
    problem = _validate(parsed) if parsed is not None else "قالب با متن جور نیست"
    if parsed is None or problem:
        errors.append(f"llm: {problem}")
        return None
    return parsed, row


def _hold(sms: SmsInbox, parsed: ParsedSms, parser: str, template: SmsTemplate | None,
          reason: str) -> None:
    """خوانده نگه داشته می‌شود تا کاربر فقط حساب را انتخاب کند."""
    data = asdict(parsed)
    data["occurred_at"] = parsed.occurred_at.isoformat() if parsed.occurred_at else None
    sms.parse_status, sms.parser, sms.error = "failed", parser, reason
    sms.parsed_json = json.dumps(data, ensure_ascii=False)
    sms.template_id = template.id if template is not None else None


def held_reading(sms: SmsInbox) -> ParsedSms | None:
    """خواندهٔ پیامکی که منتظر انتخاب حساب است."""
    if not sms.parsed_json:
        return None
    data = json.loads(sms.parsed_json)
    if data.get("occurred_at"):
        data["occurred_at"] = datetime.fromisoformat(data["occurred_at"])
    return ParsedSms(**data)


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
    template: SmsTemplate | None = None
    parsed, parser_name, errors = _try_parsers(text, received_at, parsers)
    if parsed is None:
        llm = llm or DisabledLLM()
        found = (_try_templates(session, text, received_at)
                 or _try_llm(session, text, received_at, llm, errors))
        if found is not None:
            parsed, template = found
            parser_name = (f"template:{template.id}" if template.status == "active"
                           else f"llm:{llm.name}")
    if parsed is None:
        sms.error = " · ".join(errors) or NO_PARSER
        session.commit()
        return IngestResult("failed", sms)
    try:
        account = find_account(session, parsed.bank, parsed.account_mask,
                               parsed.account_prefix)
    except AmbiguousAccount:
        account = None
    if template is not None and template.status != "active":
        _hold(sms, parsed, parser_name, template, NEW_TEMPLATE)
    elif account is None:
        _hold(sms, parsed, parser_name, template, NEEDS_ACCOUNT)
    else:
        transaction = _apply(session, sms, parsed, parser_name, account)
        session.commit()
        return IngestResult("parsed", sms, transaction)
    session.commit()
    return IngestResult("failed", sms)


def choose_account(session: Session, sms: SmsInbox, account_id: int | None) -> Transaction:
    """کاربر حساب پیامک خوانده‌شده را انتخاب کرد (None یعنی حساب تازه بساز).

    انتخاب به خاطر سپرده می‌شود و قالب تازه با همین تأیید فعال می‌شود.
    """
    parsed = held_reading(sms)
    if parsed is None:
        raise ValueError("این پیامک خوانده نشده؛ دستی تکمیلش کن")
    if account_id is None:
        account = _new_account(session, parsed)
    else:
        chosen = session.get(Account, account_id)
        if chosen is None:
            raise ValueError("حساب پیدا نشد")
        account = chosen
        _remember(session, parsed, account)
    template = session.get(SmsTemplate, sms.template_id) if sms.template_id else None
    if template is not None and template.status == "pending":
        template.status, template.activated_at = "active", utcnow()
    transaction = _apply(session, sms, parsed, sms.parser or "manual", account)
    session.commit()
    return transaction


def _remember(session: Session, parsed: ParsedSms, account: Account) -> None:
    try:
        found = find_account(session, parsed.bank, parsed.account_mask, parsed.account_prefix)
    except AmbiguousAccount:  # بلو با چند حساب: هر بار پرسیده می‌شود
        return
    if found is None:
        session.add(AccountAlias(account_id=account.id, bank=parsed.bank,
                                 account_mask=parsed.account_mask,
                                 account_prefix=parsed.account_prefix))


def complete_manually(session: Session, sms: SmsInbox, parsed: ParsedSms) -> Transaction:
    """تکمیل دستی پیامکی که در صف بررسی مانده؛ قالب تازه‌ای که اشتباه خواند کنار می‌رود."""
    if problem := _validate(parsed):
        raise ValueError(problem)
    template = session.get(SmsTemplate, sms.template_id) if sms.template_id else None
    if template is not None and template.status == "pending":
        template.status = "rejected"
    try:
        account = find_account(session, parsed.bank, parsed.account_mask, parsed.account_prefix)
    except AmbiguousAccount:
        account = None
    transaction = _apply(session, sms, parsed, "manual",
                         account or _new_account(session, parsed))
    session.commit()
    return transaction


def ignore(session: Session, sms: SmsInbox) -> None:
    sms.parse_status, sms.error = "ignored", "نادیده گرفته شد"
    sms.parsed_json = None
    session.commit()
