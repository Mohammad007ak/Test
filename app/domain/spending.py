"""خرج‌های واقعی: مرز ماه شمسی و جمع به تفکیک دسته."""

from collections import defaultdict
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import NamedTuple
from zoneinfo import ZoneInfo

import jdatetime

TEHRAN = ZoneInfo("Asia/Tehran")
UNCATEGORIZED = "uncategorized"
# انتقال بین حساب‌های خود آدم خرج نیست
NOT_SPENDING = frozenset({"transfer"})


class CategoryTotal(NamedTuple):
    category: str
    total_toman: int


def shift_month(year: int, month: int, delta: int) -> tuple[int, int]:
    index = year * 12 + (month - 1) + delta
    return index // 12, index % 12 + 1


def month_bounds_utc(year: int, month: int) -> tuple[datetime, datetime]:
    """آغاز ماه شمسی و آغاز ماه بعد به وقت تهران، به UTC (برای کوئری بازه‌ای)."""

    def start(y: int, m: int) -> datetime:
        day = jdatetime.date(y, m, 1).togregorian()
        return datetime(day.year, day.month, day.day, tzinfo=TEHRAN).astimezone(UTC)

    return start(year, month), start(*shift_month(year, month, 1))


def spending_by_category(items: Iterable[tuple[str | None, int]]) -> list[CategoryTotal]:
    """جمع مبلغ‌ها به تفکیک دسته، از بیشترین به کمترین؛ انتقال به خود حساب نمی‌شود."""
    totals: dict[str, int] = defaultdict(int)
    for category, amount_toman in items:
        if category in NOT_SPENDING:
            continue
        totals[category or UNCATEGORIZED] += amount_toman
    return sorted((CategoryTotal(c, t) for c, t in totals.items()),
                  key=lambda row: -row.total_toman)
