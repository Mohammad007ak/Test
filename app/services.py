"""لایه بین منطق مالی (domain) و دیتابیس: کوئری‌ها، خلاصه پرتفوی و اسنپ‌شات."""

import json
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import USER_KEY
from app.domain import persona as persona_domain
from app.domain.income import monthly_income_toman
from app.domain.liabilities import (
    LiabilityTerms,
    monthly_installment_toman,
    remaining_balance_toman,
)
from app.domain.normalize import normalize_chars
from app.domain.spending import CategoryTotal, month_bounds_utc, spending_by_category
from app.domain.valuation import AssetHolding, NetWorth, asset_value_toman, debt_to_income
from app.models import (
    Account,
    Asset,
    ExpenseStream,
    IncomeStream,
    Liability,
    NetworthSnapshot,
    PriceQuote,
    Setting,
    Transaction,
    UserSetting,
    utcnow,
)
from app.sms.text import mask_numbers

STALE_MANUAL_VALUE = timedelta(days=30)

DEFAULT_SETTINGS: dict[str, str] = {
    "dti_threshold": "0.35",
    "inflation": "0.35",
}


# ---------- تنظیمات ----------

def get_setting(session: Session, key: str) -> str | None:
    row = session.get(Setting, key)
    if row is not None:
        return row.value
    return DEFAULT_SETTINGS.get(key)


def set_setting(session: Session, key: str, value: str) -> None:
    row = session.get(Setting, key)
    if row is None:
        session.add(Setting(key=key, value=value))
    else:
        row.value = value


def get_user_setting(session: Session, key: str) -> str | None:
    """تنظیم کاربر جاری (نشست محدود به کاربر)؛ وگرنه مقدار پیش‌فرض."""
    row = session.scalars(select(UserSetting).where(UserSetting.key == key)).first()
    return row.value if row is not None else DEFAULT_SETTINGS.get(key)


def set_user_setting(session: Session, key: str, value: str) -> None:
    row = session.scalars(select(UserSetting).where(UserSetting.key == key)).first()
    if row is None:
        session.add(UserSetting(key=key, value=value))
    else:
        row.value = value


def get_decimal_setting(session: Session, key: str) -> Decimal:
    return Decimal(get_user_setting(session, key) or "0")


# ---------- قیمت‌ها ----------

def latest_quotes(session: Session) -> dict[str, PriceQuote]:
    """آخرین قیمت معتبر هر کلید (تاریخچه حفظ می‌شود)."""
    quotes: dict[str, PriceQuote] = {}
    query = select(PriceQuote).order_by(PriceQuote.fetched_at, PriceQuote.id)
    if USER_KEY not in session.info:  # نشست سیستمی: فقط قیمت منابع، نه قیمت دستی کاربران
        query = query.where(PriceQuote.user_id.is_(None))
    rows = session.scalars(query)
    for quote in rows:
        quotes[quote.key] = quote
    return quotes


def owned_market_keys(session: Session) -> list[str]:
    """کلیدهای قیمت سهام و صندوق‌هایی که کاربر به‌عنوان دارایی ثبت کرده."""
    keys = session.scalars(select(Asset.price_key).where(Asset.kind.in_(("stock", "fund")),
                                                         Asset.price_key.is_not(None)))
    return sorted({key for key in keys if key})


def add_quote(session: Session, key: str, price_toman: int, source: str = "manual") -> PriceQuote:
    quote = PriceQuote(key=key, price_toman=price_toman, fetched_at=utcnow(), source=source)
    session.add(quote)
    return quote


# ---------- خلاصه پرتفوی ----------

@dataclass(frozen=True)
class AssetLine:
    asset: Asset
    value_toman: int | None
    price: PriceQuote | None
    stale: bool


@dataclass(frozen=True)
class LiabilityLine:
    liability: Liability
    remaining_toman: int
    monthly_toman: int
    remaining_count: int


@dataclass
class Portfolio:
    assets: list[AssetLine]
    accounts: list[Account]
    liabilities: list[LiabilityLine]
    incomes: list[tuple[IncomeStream, int]]
    quotes: dict[str, PriceQuote]
    composition: dict[str, int] = field(default_factory=dict)
    expenses: list[tuple[ExpenseStream, int]] = field(default_factory=list)

    @property
    def assets_toman(self) -> int:
        valued = sum(line.value_toman or 0 for line in self.assets)
        return valued + sum(account.balance_toman for account in self.accounts)

    @property
    def liabilities_toman(self) -> int:
        return sum(line.remaining_toman for line in self.liabilities)

    @property
    def networth(self) -> NetWorth:
        return NetWorth(self.assets_toman, self.liabilities_toman)

    @property
    def monthly_income_toman(self) -> int:
        return sum(monthly for income, monthly in self.incomes if income.active)

    @property
    def monthly_installments_toman(self) -> int:
        return sum(line.monthly_toman for line in self.liabilities)

    @property
    def monthly_fixed_expenses_toman(self) -> int:
        return sum(monthly for expense, monthly in self.expenses if expense.active)

    @property
    def monthly_free_cash_toman(self) -> int:
        """درآمد ماهانه منهای اقساط و هزینه‌های ثابت."""
        return (self.monthly_income_toman - self.monthly_installments_toman
                - self.monthly_fixed_expenses_toman)

    @property
    def dti(self) -> Decimal | None:
        return debt_to_income(self.monthly_installments_toman, self.monthly_income_toman)

    @property
    def unvalued_assets(self) -> list[AssetLine]:
        return [line for line in self.assets if line.value_toman is None]

    @property
    def stale_assets(self) -> list[AssetLine]:
        return [line for line in self.assets if line.stale]

    def unit_price(self, key: str) -> int | None:
        quote = self.quotes.get(key)
        return quote.price_toman if quote else None


def _holding(asset: Asset) -> AssetHolding:
    return AssetHolding(asset.kind, asset.quantity, asset.karat, asset.price_key,
                        asset.manual_value_toman)


def _is_stale(asset: Asset, now: datetime) -> bool:
    if asset.price_key or asset.manual_value_updated_at is None:
        return False
    return now - asset.manual_value_updated_at > STALE_MANUAL_VALUE


def _terms(liability: Liability) -> LiabilityTerms:
    return LiabilityTerms(liability.principal_toman, liability.installment_toman,
                          liability.installments_total, liability.installments_paid)


def build_portfolio(session: Session, now: datetime | None = None) -> Portfolio:
    now = now or utcnow()
    quotes = latest_quotes(session)
    prices = {key: quote.per_unit for key, quote in quotes.items()}

    asset_lines = [
        AssetLine(asset, asset_value_toman(_holding(asset), prices),
                  quotes.get(asset.price_key) if asset.price_key else None,
                  _is_stale(asset, now))
        for asset in session.scalars(select(Asset).order_by(Asset.kind, Asset.id))
    ]
    liability_lines = []
    for liability in session.scalars(select(Liability).order_by(Liability.id)):
        terms = _terms(liability)
        liability_lines.append(
            LiabilityLine(liability, remaining_balance_toman(terms),
                          monthly_installment_toman(terms),
                          max(terms.installments_total - terms.installments_paid, 0))
        )
    incomes = [
        (income, monthly_income_toman(income.amount_toman, income.frequency))
        for income in session.scalars(select(IncomeStream).order_by(IncomeStream.id))
    ]
    expenses = [
        (expense, monthly_income_toman(expense.amount_toman, expense.frequency))
        for expense in session.scalars(select(ExpenseStream).order_by(ExpenseStream.id))
    ]
    accounts = list(session.scalars(select(Account).order_by(Account.id)))

    composition: dict[str, int] = defaultdict(int)
    for line in asset_lines:
        if line.value_toman:
            composition[line.asset.kind] += line.value_toman
    account_total = sum(account.balance_toman for account in accounts)
    if account_total:
        composition["bank"] += account_total

    return Portfolio(asset_lines, accounts, liability_lines, incomes, quotes, dict(composition),
                     expenses)


# ---------- اسنپ‌شات ----------

def record_snapshot(session: Session, portfolio: Portfolio, day: date) -> NetworthSnapshot:
    """یک ردیف در روز؛ اجرای دوباره در همان روز ردیف را به‌روز می‌کند."""
    snapshot = (session.scalars(select(NetworthSnapshot).where(NetworthSnapshot.date == day))
                .first() or NetworthSnapshot(date=day))
    snapshot.assets_toman = portfolio.assets_toman
    snapshot.liabilities_toman = portfolio.liabilities_toman
    snapshot.networth_toman = portfolio.networth.networth_toman
    snapshot.usd_rate = portfolio.unit_price("usd")
    snapshot.gold18_rate = portfolio.unit_price("gold18_gram")
    session.add(snapshot)
    return snapshot


def snapshots(session: Session) -> list[NetworthSnapshot]:
    return list(session.scalars(select(NetworthSnapshot).order_by(NetworthSnapshot.date)))


# ---------- خرج‌های واقعی ----------

@dataclass
class MonthSpending:
    transactions: list[Transaction]
    by_category: list[CategoryTotal]

    @property
    def total_toman(self) -> int:
        return sum(row.total_toman for row in self.by_category)


def month_spending(session: Session, year: int, month: int,
                   direction: str = "out") -> MonthSpending:
    """تراکنش‌های یک جهت (out: خرج، in: واریز) در یک ماه شمسی، جدیدترین اول."""
    start, end = month_bounds_utc(year, month)
    rows = list(session.scalars(
        select(Transaction)
        .where(Transaction.direction == direction, Transaction.occurred_at >= start,
               Transaction.occurred_at < end)
        .order_by(Transaction.occurred_at.desc(), Transaction.id.desc())))
    return MonthSpending(rows, spending_by_category((t.category, t.amount_toman) for t in rows))


# ---------- قیمت‌های دلخواه صفحه اصلی ----------

WATCHLIST_KEY = "watchlist"
DEFAULT_WATCHLIST = ("usd", "eur", "gold18_gram", "coin_emami")
MAX_WATCHLIST = 12
CHANGE_WINDOW = timedelta(hours=24)


@dataclass(frozen=True)
class WatchItem:
    key: str
    quote: PriceQuote | None
    change: Decimal | None  # نسبت به ۲۴ ساعت قبل


def watchlist_keys(session: Session) -> list[str]:
    raw = get_user_setting(session, WATCHLIST_KEY)
    return [k for k in raw.split(",") if k] if raw is not None else list(DEFAULT_WATCHLIST)


def set_watchlist(session: Session, keys: list[str]) -> None:
    unique = list(dict.fromkeys(keys))[:MAX_WATCHLIST]
    set_user_setting(session, WATCHLIST_KEY, ",".join(unique))


def _price_at(session: Session, key: str, moment: datetime) -> PriceQuote | None:
    """قیمتی که در آن لحظه معتبر بود: آخرین ردیفی که پیش از آن دیده شده بود."""
    return session.scalars(
        select(PriceQuote).where(PriceQuote.key == key, PriceQuote.first_seen_at <= moment)
        .order_by(PriceQuote.first_seen_at.desc(), PriceQuote.id.desc())).first()


def watchlist(session: Session, now: datetime | None = None) -> list[WatchItem]:
    now = now or utcnow()
    quotes = latest_quotes(session)
    items = []
    for key in watchlist_keys(session):
        quote = quotes.get(key)
        change = None
        if quote is not None:
            before = _price_at(session, key, now - CHANGE_WINDOW)
            if before is not None and before.id != quote.id and before.per_unit:
                change = (quote.per_unit - before.per_unit) / before.per_unit
        items.append(WatchItem(key, quote, change))
    return items


# ---------- پرسونای مالی ----------

PERSONA_KEY = "persona"
AVATAR_KEY = "avatar"
MAX_PERSONA_NOTE = 300
_WATCH_OF_INTEREST = {"fx": ("usd", "eur"), "gold": ("gold18_gram", "coin_emami"),
                      "crypto": ("crypto:btc", "crypto:usdt")}


@dataclass(frozen=True)
class StoredPersona:
    persona: persona_domain.Persona
    card: str
    note: str


def load_persona(session: Session) -> StoredPersona | None:
    raw = get_user_setting(session, PERSONA_KEY)
    if not raw:
        return None
    try:
        data = json.loads(raw)
        return _stored(data["answers"], str(data.get("note", "")))
    except (ValueError, KeyError, TypeError, AttributeError):
        return None


def save_persona(session: Session, answers: dict[str, object], note: str) -> StoredPersona:
    """جواب‌ها ذخیره می‌شوند و امتیاز هر بار از نو حساب می‌شود؛ یادداشت بدون شماره حساب و کارت.

    اگر کاربر قیمت‌های صفحه اصلی را هنوز دستی انتخاب نکرده، از روی علاقه‌هایش چیده می‌شود.
    """
    clean_note = mask_numbers(normalize_chars(" ".join(note.split())))[:MAX_PERSONA_NOTE]
    set_user_setting(session, PERSONA_KEY, json.dumps(
        {"answers": answers, "note": clean_note, "at": utcnow().isoformat()},
        ensure_ascii=False))
    stored = _stored(answers, clean_note)
    if get_user_setting(session, WATCHLIST_KEY) is None:
        interests = stored.persona.interests
        keys = [k for i in interests for k in _WATCH_OF_INTEREST.get(i, ())]
        if keys:
            set_watchlist(session, keys)
    if get_user_setting(session, AVATAR_KEY) is None:
        set_user_setting(session, AVATAR_KEY, stored.card)
    return stored


def _stored(answers: dict[str, object], note: str) -> StoredPersona:
    persona = persona_domain.build_persona(answers)
    return StoredPersona(persona, persona_domain.card_for(persona), note)


def avatar(session: Session) -> str | None:
    value = get_user_setting(session, AVATAR_KEY)
    return value if value in persona_domain.CARDS else None


def set_avatar(session: Session, card: str) -> None:
    if card not in persona_domain.CARDS:
        raise ValueError(card)
    set_user_setting(session, AVATAR_KEY, card)
