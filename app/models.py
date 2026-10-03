"""جدول‌های دیتابیس (SPEC بخش «مدل داده»). مبالغ BIGINT تومانی، زمان‌ها UTC."""

from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.engine import Dialect
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import TypeDecorator

from app.db import Base


class DecimalText(TypeDecorator[Decimal]):
    """Decimal دقیق در SQLite (به‌صورت متن ذخیره می‌شود، نه float)."""

    impl = String(40)
    cache_ok = True

    def process_bind_param(self, value: Decimal | None, dialect: Dialect) -> str | None:
        return None if value is None else str(value)

    def process_result_value(self, value: str | None, dialect: Dialect) -> Decimal | None:
        return None if value is None else Decimal(value)


class UTCDateTime(TypeDecorator[datetime]):
    """SQLite منطقه زمانی را نگه نمی‌دارد؛ همیشه UTC آگاه برمی‌گردانیم."""

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("زمان بدون منطقه زمانی ذخیره نمی‌شود")
        return value.astimezone(UTC).replace(tzinfo=None)

    def process_result_value(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        return None if value is None else value.replace(tzinfo=UTC)


def utcnow() -> datetime:
    return datetime.now(UTC)


class Asset(Base):
    __tablename__ = "assets"

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(200))
    quantity: Mapped[Decimal | None] = mapped_column(DecimalText)
    unit: Mapped[str | None] = mapped_column(String(20))
    karat: Mapped[int | None] = mapped_column(Integer)
    price_key: Mapped[str | None] = mapped_column(String(100))
    manual_value_toman: Mapped[int | None] = mapped_column(BigInteger)
    manual_value_updated_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    note: Mapped[str | None] = mapped_column(Text)


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    bank: Mapped[str] = mapped_column(String(50))
    account_mask: Mapped[str] = mapped_column(String(4))
    # ابتدای شماره حساب (کد شعبه/نوع)؛ حساب‌های یک نفر با ۴ رقم آخر یکسان را جدا می‌کند
    account_prefix: Mapped[str] = mapped_column(String(4), default="", server_default="")
    label: Mapped[str | None] = mapped_column(String(200))
    balance_toman: Mapped[int] = mapped_column(BigInteger, default=0)
    balance_updated_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    balance_source: Mapped[str] = mapped_column(String(10), default="manual")


class SmsInbox(Base):
    __tablename__ = "sms_inbox"

    id: Mapped[int] = mapped_column(primary_key=True)
    text_masked: Mapped[str] = mapped_column(Text)
    received_at: Mapped[datetime] = mapped_column(UTCDateTime)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    parse_status: Mapped[str] = mapped_column(String(10))
    parser: Mapped[str | None] = mapped_column(String(50))
    error: Mapped[str | None] = mapped_column(Text)


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    # خالی برای خرجی که دستی ثبت شده (نقدی یا بدون حساب)
    account_id: Mapped[int | None] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"))
    direction: Mapped[str] = mapped_column(String(3))
    amount_toman: Mapped[int] = mapped_column(BigInteger)
    balance_after_toman: Mapped[int | None] = mapped_column(BigInteger)
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime)
    category: Mapped[str | None] = mapped_column(String(50))
    description: Mapped[str | None] = mapped_column(Text)
    sms_id: Mapped[int | None] = mapped_column(ForeignKey("sms_inbox.id", ondelete="SET NULL"))


class Liability(Base):
    __tablename__ = "liabilities"

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(20))
    lender: Mapped[str] = mapped_column(String(200))
    principal_toman: Mapped[int] = mapped_column(BigInteger, default=0)
    installment_toman: Mapped[int] = mapped_column(BigInteger, default=0)
    installments_total: Mapped[int] = mapped_column(Integer, default=0)
    installments_paid: Mapped[int] = mapped_column(Integer, default=0)
    due_day: Mapped[int | None] = mapped_column(Integer)
    nominal_rate: Mapped[Decimal | None] = mapped_column(DecimalText)
    start_date: Mapped[date | None] = mapped_column(Date)
    note: Mapped[str | None] = mapped_column(Text)


class IncomeStream(Base):
    __tablename__ = "income_streams"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    amount_toman: Mapped[int] = mapped_column(BigInteger)
    frequency: Mapped[str] = mapped_column(String(10))
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class ExpenseStream(Base):
    """هزینه ثابت تکراری (اجاره، قبض، شهریه)؛ از باقی‌مانده ماهانه کم می‌شود."""

    __tablename__ = "expense_streams"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    amount_toman: Mapped[int] = mapped_column(BigInteger)
    frequency: Mapped[str] = mapped_column(String(10))
    category: Mapped[str | None] = mapped_column(String(50))
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class PriceQuote(Base):
    __tablename__ = "price_quotes"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(100), index=True)
    price_toman: Mapped[int] = mapped_column(BigInteger)  # قیمت units واحد
    units: Mapped[int] = mapped_column(BigInteger, default=1, server_default="1")
    fetched_at: Mapped[datetime] = mapped_column(UTCDateTime, index=True)
    source: Mapped[str] = mapped_column(String(50))

    @property
    def per_unit(self) -> Decimal:
        """قیمت یک واحد (برای رمزارزهای خیلی ارزان کسری از تومان)."""
        return Decimal(self.price_toman) / (self.units or 1)


class NetworthSnapshot(Base):
    __tablename__ = "networth_snapshots"

    date: Mapped[date] = mapped_column(Date, primary_key=True)
    assets_toman: Mapped[int] = mapped_column(BigInteger)
    liabilities_toman: Mapped[int] = mapped_column(BigInteger)
    networth_toman: Mapped[int] = mapped_column(BigInteger)
    usd_rate: Mapped[int | None] = mapped_column(BigInteger)
    gold18_rate: Mapped[int | None] = mapped_column(BigInteger)


class LoanAnalysis(Base):
    __tablename__ = "loan_analyses"

    id: Mapped[int] = mapped_column(primary_key=True)
    inputs_json: Mapped[str] = mapped_column(Text)
    result_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text)
