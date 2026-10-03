"""تاریخ و ساعت پیامک‌ها (شمسی، وقت تهران) → UTC."""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import jdatetime

TEHRAN = ZoneInfo("Asia/Tehran")


def jalali_to_utc(year: int, month: int, day: int, hour: int = 0, minute: int = 0,
                  second: int = 0) -> datetime:
    local = jdatetime.datetime(year, month, day, hour, minute, second).togregorian()
    return local.replace(tzinfo=TEHRAN).astimezone(UTC)


def month_day_to_utc(month: int, day: int, hour: int, minute: int,
                     received_at: datetime) -> datetime:
    """پیامکی که سال ندارد (مثل «07/06_11:45»): سال شمسی زمان دریافت؛
    اگر تاریخ بعد از زمان دریافت بیفتد (پیامک اسفند که فروردین رسیده)، سال قبل."""
    year = jdatetime.datetime.fromgregorian(datetime=received_at.astimezone(TEHRAN)).year
    moment = jalali_to_utc(year, month, day, hour, minute)
    if moment > received_at.astimezone(UTC) and (moment - received_at).days >= 1:
        moment = jalali_to_utc(year - 1, month, day, hour, minute)
    return moment
