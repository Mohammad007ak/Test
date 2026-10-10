"""مدرسه وزیر: امتیاز، زنجیره روزانه، سطح کارت و بررسی جواب (منطق خالص، بدون دیتابیس و وب).

روزها همه «روز تهران» هستند و هفته ایرانی از شنبه شروع می‌شود. کارت شخصیت سه سطح دارد: دانش کل
(دانش پایه پرسونا + دانش مدرسه) هر ۱۰۰ واحد یک سطح بالا می‌رود، تا سقف سطح ۳.
"""

import bisect
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from app.domain.money import round_toman
from app.domain.normalize import normalize_digits

XP_BASE = 40
XP_PER_CORRECT = 4
REPLAY_DIVISOR = 2  # دوباره خواندن درس تمام‌شده: نصف امتیاز
CHEST_XP = 50  # صندوقچه پایان ایستگاه، یک بار
KNOWLEDGE_PER_LESSON = 2
LEVEL_SPAN = 100
MAX_LEVEL = 3

# تورم درس‌ها همان تنظیم کاربر است؛ عدد غیرعادی (که گزینه‌ها را یکی می‌کند) با پیش‌فرض عوض می‌شود
DEFAULT_INFLATION = Decimal("0.35")
INFLATION_RANGE = (Decimal("0.10"), Decimal("1.00"))

_SATURDAY = 5  # date.weekday()


def lesson_xp(correct: int, first_time: bool) -> int:
    if correct < 0:
        raise ValueError("تعداد جواب درست منفی نیست")
    xp = XP_BASE + XP_PER_CORRECT * correct
    return xp if first_time else xp // REPLAY_DIVISOR


# ---------- زنجیره روزانه ----------

def week_start(day: date) -> date:
    """شنبه همان هفته."""
    return day - timedelta(days=(day.weekday() - _SATURDAY) % 7)


@dataclass(frozen=True)
class Streak:
    count: int = 0
    best: int = 0
    last_day: date | None = None  # آخرین روزی که درسی تمام شد
    freeze_day: date | None = None  # آخرین روز جاافتاده‌ای که یخ زد (هفته‌ای یک بار)


def _can_freeze(streak: Streak, missed: date) -> bool:
    return streak.freeze_day is None or week_start(streak.freeze_day) != week_start(missed)


def record_day(streak: Streak, today: date) -> Streak:
    """یک درس امروز تمام شد؛ یک روز جاافتاده، اگر یخ‌زدن این هفته مانده، زنجیره را نمی‌شکند."""
    last = streak.last_day
    if last == today:
        return streak
    freeze_day = streak.freeze_day
    if last is not None and today - last == timedelta(days=1):
        count = streak.count + 1
    elif (last is not None and today - last == timedelta(days=2) and streak.count
          and _can_freeze(streak, today - timedelta(days=1))):
        count, freeze_day = streak.count + 1, today - timedelta(days=1)
    else:
        count = 1
    return Streak(count, max(streak.best, count), today, freeze_day)


def current_streak(streak: Streak, today: date) -> int:
    """زنجیره‌ای که هنوز زنده است (امروز یا دیروز درس خوانده، یا یخ‌زدن جای دیروز را می‌گیرد)."""
    last = streak.last_day
    if last is None:
        return 0
    gap = (today - last).days
    if gap <= 1 or (gap == 2 and _can_freeze(streak, today - timedelta(days=1))):
        return streak.count
    return 0


def week_marks(streak: Streak, today: date) -> list[str]:
    """هفت روز این هفته (شنبه تا جمعه): done، frozen، today یا خالی."""
    start = week_start(today)
    marks = ["today" if start + timedelta(days=i) == today else "" for i in range(7)]
    if not current_streak(streak, today) or streak.last_day is None:
        return marks
    day, left = streak.last_day, streak.count
    while left > 0 and day >= start:
        if day == streak.freeze_day:
            marks[(day - start).days] = "frozen"
        else:
            marks[(day - start).days] = "done"
            left -= 1
        day -= timedelta(days=1)
    return marks


# ---------- سطح کارت شخصیت ----------

@dataclass(frozen=True)
class CardLevel:
    level: int  # ۱ تا ۳
    progress: int  # پیشرفت در همین سطح، ۰ تا ۱۰۰
    total: int  # دانش کل، ۰ تا ۳۰۰


def knowledge_bonus(lessons_completed: int) -> int:
    return KNOWLEDGE_PER_LESSON * lessons_completed


def card_level(base: int, bonus: int) -> CardLevel:
    total = min(max(base + bonus, 0), LEVEL_SPAN * MAX_LEVEL)
    level = min(total // LEVEL_SPAN + 1, MAX_LEVEL)
    return CardLevel(level, total - (level - 1) * LEVEL_SPAN, total)


# ---------- بررسی جواب ----------

@dataclass(frozen=True)
class Slider:
    low: int
    high: int
    right_low: int
    right_high: int
    step: int = 1


def _parse_int(answer: str) -> int | None:
    text = normalize_digits(answer.strip())
    return int(text) if text.isdecimal() else None


def check_choice(correct: int, count: int, answer: str) -> bool | None:
    """None یعنی جواب نامعتبر (نه غلط)."""
    pick = _parse_int(answer)
    if pick is None or not 0 <= pick < count:
        return None
    return pick == correct


def check_slider(slider: Slider, answer: str) -> bool | None:
    value = _parse_int(answer)
    if value is None or not slider.low <= value <= slider.high:
        return None
    return slider.right_low <= value <= slider.right_high


# ---------- حساب‌های درس‌ها ----------

def lesson_inflation(setting: Decimal) -> Decimal:
    low, high = INFLATION_RANGE
    return setting if low <= setting <= high else DEFAULT_INFLATION


def purchasing_power(amount_toman: int, inflation: Decimal, years: int) -> int:
    """ارزش مبلغ پس از چند سال، به پول امروز."""
    return round_toman(Decimal(amount_toman) / (1 + inflation) ** years)


def real_rate(nominal: Decimal, inflation: Decimal) -> Decimal:
    return (1 + nominal) / (1 + inflation) - 1


def grow(amount_toman: int, start_price: Decimal, end_price: Decimal) -> int:
    """مبلغی که با قیمت شروع خرج شده، با قیمت پایان چقدر می‌ارزد."""
    return round_toman(Decimal(amount_toman) * end_price / start_price)


def price_on(series: Sequence[tuple[date, Decimal]], day: date) -> Decimal | None:
    """قیمت آخرین روزِ تا این روز (سری مرتب قدیم به جدید)."""
    i = bisect.bisect_right([d for d, _ in series], day)
    return series[i - 1][1] if i else None


def years_before(day: date, years: int) -> date:
    try:
        return day.replace(year=day.year - years)
    except ValueError:  # ۲۹ فوریه
        return day.replace(year=day.year - years, day=28)
