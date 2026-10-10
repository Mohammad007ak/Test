"""جدول‌های دیتابیس (SPEC بخش «مدل داده»). مبالغ BIGINT تومانی، زمان‌ها UTC."""

from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
)
from sqlalchemy.engine import Dialect
from sqlalchemy.orm import Mapped, declared_attr, mapped_column
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


class User(Base):
    """کاربر؛ نام کاربری همان شماره موبایل (۰۹xxxxxxxxx) است."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    # خالی فقط برای حساب قدیمی تک‌کاربره تا صاحبش با شماره خودش ثبت‌نام کند
    phone: Mapped[str | None] = mapped_column(String(11), unique=True)
    password_hash: Mapped[str | None] = mapped_column(String(200))
    # با تغییر رمز بالا می‌رود تا نشست‌های قبلی همه دستگاه‌ها باطل شوند
    session_version: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    # آخرین بازدید (با فاصله حداقل چند دقیقه به‌روز می‌شود) و غیرفعال‌شده از پنل مدیریت
    last_seen_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    disabled_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    # اشتراک «وزیر ویژه» (فعلاً از پنل مدیریت داده می‌شود): جان بی‌نهایت در مدرسه
    premium_until: Mapped[datetime | None] = mapped_column(UTCDateTime)


class UserOwned:
    """داده شخصی: هر کوئری خودکار به کاربر جاری محدود می‌شود (app.db.scope_to_user)."""

    @declared_attr
    def user_id(cls) -> Mapped[int]:
        return mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)


class UserSetting(UserOwned, Base):
    __tablename__ = "user_settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"),
                                         primary_key=True, index=True)


class OtpCode(Base):
    """کد یک‌بارمصرف پیامکی برای ثبت‌نام یا بازیابی رمز؛ فقط هش کد نگه داشته می‌شود."""

    __tablename__ = "otp_codes"

    id: Mapped[int] = mapped_column(primary_key=True)
    phone: Mapped[str] = mapped_column(String(11), index=True)
    purpose: Mapped[str] = mapped_column(String(10))
    code_hash: Mapped[str] = mapped_column(String(64))
    ip: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, index=True)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    used: Mapped[bool] = mapped_column(Boolean, default=False)


class Asset(UserOwned, Base):
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


class Account(UserOwned, Base):
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


class SmsInbox(UserOwned, Base):
    __tablename__ = "sms_inbox"

    id: Mapped[int] = mapped_column(primary_key=True)
    text_masked: Mapped[str] = mapped_column(Text)
    received_at: Mapped[datetime] = mapped_column(UTCDateTime)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    parse_status: Mapped[str] = mapped_column(String(10))
    parser: Mapped[str | None] = mapped_column(String(50))
    error: Mapped[str | None] = mapped_column(Text)
    # پیامک خوانده‌شده‌ای که منتظر انتخاب حساب (یا تأیید قالب تازه) است: خوانده به JSON
    parsed_json: Mapped[str | None] = mapped_column(Text)
    template_id: Mapped[int | None] = mapped_column(
        ForeignKey("sms_templates.id", ondelete="SET NULL"))


class SmsTemplate(Base):
    """قالب یادگرفته پیامک، مشترک بین همه کاربران (app.sms.templates).

    pending تا تأیید اولین کاربر، active پس از آن، rejected اگر کاربر خوانده را اشتباه دانست.
    متن ثابت قالب هیچ عددی ندارد و نام‌ها با {any} پوشانده شده‌اند.
    """

    __tablename__ = "sms_templates"

    id: Mapped[int] = mapped_column(primary_key=True)
    pattern: Mapped[str] = mapped_column(Text)
    pattern_hash: Mapped[str] = mapped_column(String(64), unique=True)
    bank: Mapped[str] = mapped_column(String(50))
    direction: Mapped[str] = mapped_column(String(3))
    unit: Mapped[str] = mapped_column(String(5))
    label: Mapped[str] = mapped_column(String(100), default="")
    status: Mapped[str] = mapped_column(String(10), default="pending")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    activated_at: Mapped[datetime | None] = mapped_column(UTCDateTime)


class AccountAlias(UserOwned, Base):
    """انتخاب کاربر: پیامک این بانک و شماره مال این حساب است (مثلاً کارتِ حساب ثبت‌شده)."""

    __tablename__ = "account_aliases"

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"))
    bank: Mapped[str] = mapped_column(String(50))
    account_mask: Mapped[str] = mapped_column(String(4), default="")
    account_prefix: Mapped[str] = mapped_column(String(4), default="")


class Transaction(UserOwned, Base):
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


class Liability(UserOwned, Base):
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


class IncomeStream(UserOwned, Base):
    __tablename__ = "income_streams"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    amount_toman: Mapped[int] = mapped_column(BigInteger)
    frequency: Mapped[str] = mapped_column(String(10))
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class ExpenseStream(UserOwned, Base):
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
    # «آخرین قیمت هر کلید» (latest_quotes) و «قیمت در لحظه X» (price_at) در هر صفحه اجرا می‌شوند
    __table_args__ = (
        Index("ix_price_quotes_key_fetched_user", "key", "fetched_at", "user_id"),
        Index("ix_price_quotes_key_first_seen", "key", "first_seen_at", "id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(100), index=True)
    price_toman: Mapped[int] = mapped_column(BigInteger)  # قیمت units واحد
    units: Mapped[int] = mapped_column(BigInteger, default=1, server_default="1")
    fetched_at: Mapped[datetime] = mapped_column(UTCDateTime, index=True)  # آخرین بار دیده‌شده
    # اولین بار که این قیمت دیده شد (ردیف تازه فقط با تغییر قیمت ساخته می‌شود)
    first_seen_at: Mapped[datetime | None] = mapped_column(UTCDateTime, default=utcnow)
    source: Mapped[str] = mapped_column(String(50))
    # قیمت دستی فقط برای همان کاربر؛ قیمت منابع (خالی) برای همه
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))

    @property
    def per_unit(self) -> Decimal:
        """قیمت یک واحد (برای رمزارزهای خیلی ارزان کسری از تومان)."""
        return Decimal(self.price_toman) / (self.units or 1)


class NetworthSnapshot(UserOwned, Base):
    __tablename__ = "networth_snapshots"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"),
                                         primary_key=True, index=True)
    date: Mapped[date] = mapped_column(Date, primary_key=True)
    assets_toman: Mapped[int] = mapped_column(BigInteger)
    liabilities_toman: Mapped[int] = mapped_column(BigInteger)
    networth_toman: Mapped[int] = mapped_column(BigInteger)
    usd_rate: Mapped[int | None] = mapped_column(BigInteger)
    gold18_rate: Mapped[int | None] = mapped_column(BigInteger)


class LoanAnalysis(UserOwned, Base):
    __tablename__ = "loan_analyses"

    id: Mapped[int] = mapped_column(primary_key=True)
    inputs_json: Mapped[str] = mapped_column(Text)
    result_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text)


class PriceHistory(Base):
    """قیمت پایانی روزانه از آرشیو منابع (برای نمودار و تحلیل)؛ سراسری، نه مال یک کاربر.

    روزهایی که آرشیو ندارد از قیمت‌های خود اپ (price_quotes) پر می‌شود.
    """

    __tablename__ = "price_history"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    day: Mapped[date] = mapped_column(Date, primary_key=True)  # روز تهران
    price_toman: Mapped[int] = mapped_column(BigInteger)  # قیمت یک واحد
    real_price_toman: Mapped[int | None] = mapped_column(BigInteger)  # ارزش ذاتی سکه (حباب)
    source: Mapped[str] = mapped_column(String(50))


class Passkey(UserOwned, Base):
    """ورود با چهره یا اثر انگشت (WebAuthn): فقط کلید عمومی دستگاه ذخیره می‌شود، نه داده زیستی."""

    __tablename__ = "passkeys"

    id: Mapped[int] = mapped_column(primary_key=True)
    credential_id: Mapped[str] = mapped_column(String(512), unique=True, index=True)  # base64url
    public_key: Mapped[bytes] = mapped_column(LargeBinary)
    sign_count: Mapped[int] = mapped_column(BigInteger, default=0)
    name: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    last_used_at: Mapped[datetime | None] = mapped_column(UTCDateTime)


# ---------- دنگ (تقسیم خرج گروهی) ----------
# همه جدول‌ها UserOwned: گروه و هر چه در آن است فقط مال سازنده است؛ دوستان با لینک
# اشتراک (share_token) فقط می‌بینند.

class SplitGroup(UserOwned, Base):
    __tablename__ = "split_groups"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    share_token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class SplitMember(UserOwned, Base):
    __tablename__ = "split_members"

    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("split_groups.id", ondelete="CASCADE"),
                                          index=True)
    name: Mapped[str] = mapped_column(String(60))
    is_me: Mapped[bool] = mapped_column(Boolean, default=False)


class SplitExpense(UserOwned, Base):
    __tablename__ = "split_expenses"

    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("split_groups.id", ondelete="CASCADE"),
                                          index=True)
    title: Mapped[str] = mapped_column(String(100))
    amount_toman: Mapped[int] = mapped_column(BigInteger)
    payer_id: Mapped[int] = mapped_column(ForeignKey("split_members.id", ondelete="CASCADE"))
    category: Mapped[str | None] = mapped_column(String(50))
    spent_on: Mapped[date] = mapped_column(Date)
    # سهم خود کاربر وقتی دیگری حساب کرده، به‌عنوان خرج او ثبت می‌شود
    transaction_id: Mapped[int | None] = mapped_column(
        ForeignKey("transactions.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class SplitShare(UserOwned, Base):
    __tablename__ = "split_shares"

    expense_id: Mapped[int] = mapped_column(
        ForeignKey("split_expenses.id", ondelete="CASCADE"), primary_key=True)
    member_id: Mapped[int] = mapped_column(
        ForeignKey("split_members.id", ondelete="CASCADE"), primary_key=True)
    amount_toman: Mapped[int] = mapped_column(BigInteger)


class SplitSettlement(UserOwned, Base):
    __tablename__ = "split_settlements"

    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("split_groups.id", ondelete="CASCADE"),
                                          index=True)
    payer_id: Mapped[int] = mapped_column(ForeignKey("split_members.id", ondelete="CASCADE"))
    payee_id: Mapped[int] = mapped_column(ForeignKey("split_members.id", ondelete="CASCADE"))
    amount_toman: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


# ---------- مدرسه وزیر ----------

class LessonProgress(UserOwned, Base):
    """پیشرفت هر درس؛ امتیاز و زنجیره در school_stats جمع می‌شود."""

    __tablename__ = "lesson_progress"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"),
                                         primary_key=True, index=True)
    lesson_slug: Mapped[str] = mapped_column(String(60), primary_key=True)
    course: Mapped[str] = mapped_column(String(40))
    best_correct: Mapped[int] = mapped_column(Integer, default=0)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    completed_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)  # اولین بار


class SchoolStats(UserOwned, Base):
    __tablename__ = "school_stats"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"),
                                         primary_key=True, index=True)
    xp: Mapped[int] = mapped_column(BigInteger, default=0)
    # افزوده مدرسه به آمار «دانش» کارت؛ جدا از پرسونا تا گرفتن دوباره کارت صفرش نکند
    knowledge: Mapped[int] = mapped_column(Integer, default=0)
    streak: Mapped[int] = mapped_column(Integer, default=0)
    best_streak: Mapped[int] = mapped_column(Integer, default=0)
    last_day: Mapped[date | None] = mapped_column(Date)  # روز تهران
    freeze_day: Mapped[date | None] = mapped_column(Date)  # آخرین روز جاافتاده‌ای که یخ زد
    hearts: Mapped[int] = mapped_column(Integer, default=5, server_default="5")
    hearts_since: Mapped[datetime | None] = mapped_column(UTCDateTime)  # شروع شمارش جان بعدی
    # سطح شروع هر تاپیک از آزمون تعیین سطح: «basics=2,loans=1»؛ خالی یعنی آزمون نداده
    levels: Mapped[str] = mapped_column(String(200), default="", server_default="")
