"""پارسرهای پاسارگاد و پارسیان؛ نمونه‌ها از پیامک واقعی (شماره حساب پارسیان ساختگی).

هیچ‌کدام اسم بانک ندارند؛ از روی ساختار شناخته می‌شوند. سال در تاریخ نیست.
"""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.sms.parsers import PARSERS
from app.sms.parsers.dates import month_day_to_utc
from app.sms.parsers.parsian import ParsianParser
from app.sms.parsers.pasargad import PasargadParser
from app.sms.text import mask_numbers, prepare

FIXTURES = Path(__file__).parent.parent / "fixtures" / "sms"
PASARGAD = mask_numbers(prepare((FIXTURES / "pasargad" / "withdrawal.txt").read_text("utf-8")))
PARSIAN = mask_numbers(prepare((FIXTURES / "parsian" / "withdrawal.txt").read_text("utf-8")))
RECEIVED = datetime(2026, 9, 28, 15, 0, tzinfo=UTC)  # ۶ مهر ۱۴۰۵


def test_pasargad_withdrawal() -> None:
    parser = PasargadParser()
    assert parser.can_parse(PASARGAD) and not parser.can_parse(PARSIAN)
    p = parser.parse(PASARGAD, RECEIVED)
    assert (p.bank, p.account_prefix, p.account_mask) == ("pasargad", "777", "4541")
    assert (p.direction, p.amount_rial, p.balance_after_rial) == ("out", 911_000, 181_715_262)
    assert p.occurred_at == datetime(2026, 9, 28, 8, 15, tzinfo=UTC)  # ۶ مهر ۱۱:۴۵ تهران


def test_pasargad_deposit_real_sample() -> None:
    deposit = mask_numbers(prepare((FIXTURES / "pasargad" / "deposit.txt").read_text("utf-8")))
    p = PasargadParser().parse(deposit, RECEIVED)
    assert (p.direction, p.amount_rial, p.balance_after_rial) == ("in", 550_000_000, 736_818_262)
    assert (p.account_prefix, p.account_mask) == ("777", "4541")
    assert p.occurred_at == datetime(2026, 9, 25, 10, 47, tzinfo=UTC)  # ۳ مهر ۱۴:۱۷ تهران


def test_parsian_withdrawal() -> None:
    parser = ParsianParser()
    assert parser.can_parse(PARSIAN) and not parser.can_parse(PASARGAD)
    p = parser.parse(PARSIAN, RECEIVED)
    assert (p.bank, p.account_prefix, p.account_mask) == ("parsian", "301", "5678")
    assert (p.direction, p.amount_rial, p.balance_after_rial) == ("out", 2_000_000, 4_417_721)
    assert p.occurred_at == datetime(2026, 9, 28, 14, 31, tzinfo=UTC)  # ۶ مهر ۱۸:۰۱ تهران


def test_parsian_deposit_real_sample() -> None:
    deposit = mask_numbers(prepare((FIXTURES / "parsian" / "deposit.txt").read_text("utf-8")))
    p = ParsianParser().parse(deposit, RECEIVED)
    assert (p.direction, p.amount_rial, p.balance_after_rial) == ("in", 2_400_000, 6_417_721)
    assert p.occurred_at == datetime(2026, 9, 28, 10, 18, tzinfo=UTC)  # ۶ مهر ۱۳:۴۸ تهران


def test_parsian_day_in_order() -> None:
    """واریز ۱۳:۴۸ و برداشت ۱۸:۰۱ همان روز: مانده نهایی مال برداشت است، به هر ترتیبی برسند."""
    from sqlalchemy import select

    from app.db import Base, make_engine, make_session_factory
    from app.models import Account
    from app.sms.pipeline import ingest

    deposit = (FIXTURES / "parsian" / "deposit.txt").read_text("utf-8")
    withdrawal = (FIXTURES / "parsian" / "withdrawal.txt").read_text("utf-8")
    engine = make_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with make_session_factory(engine)() as session:
        ingest(session, withdrawal, RECEIVED)
        ingest(session, deposit, RECEIVED)  # دیرتر رسید ولی قدیمی‌تر است
        account = session.scalars(select(Account)).one()
        assert account.balance_toman == 441_772  # ۴٬۴۱۷٬۷۲۱ ریال پس از برداشت


def test_registered() -> None:
    kinds = {type(p) for p in PARSERS}
    assert {PasargadParser, ParsianParser} <= kinds


def test_other_banks_not_claimed() -> None:
    saman = mask_numbers(prepare("بانک سامان\nبرداشت مبلغ 1,000 خرید\nاز 814-20-1234567-1"))
    assert not PasargadParser().can_parse(saman) and not ParsianParser().can_parse(saman)


@pytest.mark.parametrize(
    "received,expected_year",
    [
        (datetime(2026, 10, 3, tzinfo=UTC), 2026),   # ۱۱ مهر ۱۴۰۵ → ۶ مهر همان سال
        (datetime(2027, 3, 22, tzinfo=UTC), 2026),   # ۱ فروردین ۱۴۰۶ → ۶ مهر سال قبل
    ],
)
def test_year_inferred_from_receive_time(received: datetime, expected_year: int) -> None:
    assert month_day_to_utc(7, 6, 11, 45, received).year == expected_year
