"""جایزه اینستاگرام: ثبت آیدی هر کاربر (تنظیم کاربر) و فهرست برای پنل مدیریت."""

import json
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import services
from app.domain.phone import mask_phone
from app.models import User, UserSetting, utcnow

KEY = "giveaway_1405_mehr"


@dataclass(frozen=True)
class Claim:
    phone_masked: str
    instagram: str
    at: datetime


def _parse(raw: str | None) -> dict[str, str]:
    try:
        data = json.loads(raw or "")
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def handle(db: Session) -> str | None:
    """آیدی ثبت‌شده کاربر جاری (نشست کاربر)."""
    return _parse(services.get_user_setting(db, KEY)).get("instagram")


def save(db: Session, instagram: str) -> None:
    services.set_user_setting(db, KEY, json.dumps(
        {"instagram": instagram, "at": utcnow().isoformat()}))


def taken_by_other(system: Session, instagram: str, user_id: int) -> bool:
    """همین آیدی را کاربر دیگری ثبت کرده؟ (نشست سیستمی)"""
    rows = system.scalars(select(UserSetting).where(
        UserSetting.key == KEY, UserSetting.user_id != user_id))
    return any(_parse(r.value).get("instagram") == instagram for r in rows)


def claims(system: Session) -> list[Claim]:
    """همه شرکت‌کننده‌ها، تازه‌ترین اول؛ فقط شماره پوشانده و آیدی."""
    rows = system.execute(select(UserSetting.value, User.phone).join(
        User, User.id == UserSetting.user_id).where(UserSetting.key == KEY))
    found = []
    for value, phone in rows:
        data = _parse(value)
        if data.get("instagram") and data.get("at"):
            found.append(Claim(mask_phone(phone or ""), data["instagram"],
                               datetime.fromisoformat(data["at"])))
    return sorted(found, key=lambda c: c.at, reverse=True)
