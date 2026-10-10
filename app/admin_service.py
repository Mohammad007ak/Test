"""پنل مدیریت کاربران: آمار و فهرست کاربران برای صاحب برنامه.

همه کوئری‌ها با نشست سیستمی‌اند (همه کاربران)، ولی فقط شمارش برمی‌گردد؛ هیچ مبلغ، نام دارایی،
متن پیامک یا شماره کامل از این ماژول بیرون نمی‌رود (اعتماد کاربر، SPEC بخش امنیت).
"""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.phone import mask_phone
from app.domain.spending import TEHRAN
from app.models import (
    Account,
    Asset,
    OtpCode,
    Passkey,
    SmsInbox,
    Transaction,
    User,
    utcnow,
)

PAGE_SIZE = 50
CHART_DAYS = 30


@dataclass(frozen=True)
class Stats:
    total: int
    new_today: int
    new_7d: int
    new_30d: int
    active_1d: int
    active_7d: int
    disabled: int
    sms_7d: int  # کاربرانی که در ۷ روز اخیر پیامک بانکی فرستاده‌اند
    signups: list[tuple[date, int]]  # ثبت‌نام هر روز، ۳۰ روز اخیر (تهران)


@dataclass(frozen=True)
class UserRow:
    id: int
    phone_masked: str
    created_at: datetime
    last_seen_at: datetime | None
    disabled: bool
    is_owner: bool
    assets: int
    accounts: int
    transactions: int
    sms: int
    passkey: bool
    premium_until: datetime | None = None  # وزیر ویژه (جان بی‌نهایت مدرسه)


def _day_start(day: date) -> datetime:
    return datetime.combine(day, time(0), tzinfo=TEHRAN)


def _count(db: Session, *where: object) -> int:
    return db.scalar(select(func.count()).select_from(User)
                     .where(User.phone.is_not(None), *where)) or 0


def stats(db: Session, today: date) -> Stats:
    now = utcnow()
    since = {n: _day_start(today - timedelta(days=n - 1)) for n in (1, 7, 30)}
    sms_users = db.scalar(select(func.count(func.distinct(SmsInbox.user_id)))
                          .where(SmsInbox.received_at >= now - timedelta(days=7))) or 0
    created = db.scalars(select(User.created_at).where(
        User.phone.is_not(None), User.created_at >= _day_start(today - timedelta(CHART_DAYS - 1))))
    per_day: dict[date, int] = {}
    for moment in created:
        per_day[moment.astimezone(TEHRAN).date()] = per_day.get(
            moment.astimezone(TEHRAN).date(), 0) + 1
    days = [today - timedelta(days=i) for i in range(CHART_DAYS - 1, -1, -1)]
    return Stats(
        total=_count(db),
        new_today=_count(db, User.created_at >= since[1]),
        new_7d=_count(db, User.created_at >= since[7]),
        new_30d=_count(db, User.created_at >= since[30]),
        active_1d=_count(db, User.last_seen_at >= now - timedelta(days=1)),
        active_7d=_count(db, User.last_seen_at >= now - timedelta(days=7)),
        disabled=_count(db, User.disabled_at.is_not(None)),
        sms_7d=sms_users,
        signups=[(d, per_day.get(d, 0)) for d in days],
    )


def _counts(db: Session, model: type, ids: list[int]) -> dict[int, int]:
    rows = db.execute(select(model.user_id, func.count()).where(  # type: ignore[attr-defined]
        model.user_id.in_(ids)).group_by(model.user_id))  # type: ignore[attr-defined]
    return {uid: n for uid, n in rows}


def users(db: Session, owner_phone: str, query: str = "",
          page: int = 1) -> tuple[list[UserRow], int]:
    """کاربران، تازه‌ترین اول؛ جستجو با بخشی از شماره. (ردیف‌ها، تعداد کل یافته‌ها)."""
    where = [User.phone.is_not(None)]
    if query:
        where.append(User.phone.contains(query))
    total = db.scalar(select(func.count()).select_from(User).where(*where)) or 0
    found = list(db.scalars(select(User).where(*where)
                            .order_by(User.created_at.desc(), User.id.desc())
                            .offset((max(page, 1) - 1) * PAGE_SIZE).limit(PAGE_SIZE)))
    ids = [u.id for u in found]
    counts = {m: _counts(db, m, ids) for m in (Asset, Account, Transaction, SmsInbox, Passkey)}
    return [UserRow(
        id=u.id, phone_masked=mask_phone(u.phone or ""), created_at=u.created_at,
        last_seen_at=u.last_seen_at, disabled=u.disabled_at is not None,
        is_owner=u.phone == owner_phone,
        assets=counts[Asset].get(u.id, 0), accounts=counts[Account].get(u.id, 0),
        transactions=counts[Transaction].get(u.id, 0), sms=counts[SmsInbox].get(u.id, 0),
        passkey=counts[Passkey].get(u.id, 0) > 0,
        premium_until=u.premium_until if u.premium_until and u.premium_until > utcnow() else None)
        for u in found], total


PREMIUM_GRANT = timedelta(days=90)  # «۳ ماه وزیر ویژه» (مثلاً جایزه اینستاگرام)


def grant_premium(db: Session, user: User, now: datetime | None = None) -> None:
    """سه ماه وزیر ویژه؛ اگر هنوز فعال است، از پایان فعلی تمدید می‌شود."""
    now = now or utcnow()
    start = user.premium_until if user.premium_until and user.premium_until > now else now
    user.premium_until = start + PREMIUM_GRANT
    db.commit()


def revoke_premium(db: Session, user: User) -> None:
    user.premium_until = None
    db.commit()


def set_disabled(db: Session, user: User, disabled: bool) -> None:
    """غیرفعال: ورود بسته و همه نشست‌های باز همان لحظه باطل می‌شوند."""
    user.disabled_at = utcnow() if disabled else None
    if disabled:
        user.session_version = (user.session_version or 0) + 1
    db.commit()


def delete_user(db: Session, user: User) -> None:
    """حذف کامل: همه داده‌های کاربر با CASCADE پایگاه‌داده پاک می‌شود."""
    if user.phone:
        for code in db.scalars(select(OtpCode).where(OtpCode.phone == user.phone)):
            db.delete(code)
    db.delete(user)
    db.commit()
