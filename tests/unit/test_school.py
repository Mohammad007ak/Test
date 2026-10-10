from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.domain.school import (
    CHEST_XP,
    MAX_LEVEL,
    CardLevel,
    Slider,
    Streak,
    card_level,
    check_choice,
    check_slider,
    current_streak,
    grow,
    knowledge_bonus,
    lesson_inflation,
    lesson_xp,
    price_on,
    purchasing_power,
    real_rate,
    record_day,
    week_marks,
    week_start,
    years_before,
)

# شنبه ۱۹ مهر ۱۴۰۵
SAT = date(2026, 10, 10)


class TestXp:
    def test_first_time_is_base_plus_four_per_correct(self) -> None:
        assert lesson_xp(correct=0, first_time=True) == 40
        assert lesson_xp(correct=3, first_time=True) == 52

    def test_replay_gives_half(self) -> None:
        assert lesson_xp(correct=3, first_time=False) == 26
        assert lesson_xp(correct=1, first_time=False) == 22  # ۴۴ ÷ ۲

    def test_negative_correct_is_rejected(self) -> None:
        with pytest.raises(ValueError):
            lesson_xp(correct=-1, first_time=True)

    def test_chest_is_extra(self) -> None:
        assert CHEST_XP > 0


class TestWeek:
    def test_iranian_week_starts_on_saturday(self) -> None:
        assert week_start(SAT) == SAT
        assert week_start(SAT + timedelta(days=6)) == SAT  # جمعه
        assert week_start(SAT - timedelta(days=1)) == SAT - timedelta(days=7)


class TestStreak:
    def test_first_day_starts_at_one(self) -> None:
        s = record_day(Streak(), SAT)
        assert (s.count, s.best, s.last_day) == (1, 1, SAT)

    def test_same_day_twice_counts_once(self) -> None:
        s = record_day(record_day(Streak(), SAT), SAT)
        assert s.count == 1

    def test_next_day_continues(self) -> None:
        s = Streak()
        for i in range(3):
            s = record_day(s, SAT + timedelta(days=i))
        assert s.count == 3 and s.best == 3

    def test_one_missed_day_is_frozen_once_a_week(self) -> None:
        s = record_day(record_day(Streak(), SAT), SAT + timedelta(days=1))
        s = record_day(s, SAT + timedelta(days=3))  # دوشنبه جا افتاد
        assert s.count == 3 and s.freeze_day == SAT + timedelta(days=2)

    def test_second_freeze_in_same_week_breaks(self) -> None:
        s = Streak(count=3, best=3, last_day=SAT + timedelta(days=3),
                   freeze_day=SAT + timedelta(days=2))
        s = record_day(s, SAT + timedelta(days=5))  # چهارشنبه هم جا افتاد
        assert s.count == 1 and s.best == 3

    def test_freeze_available_again_next_week(self) -> None:
        s = Streak(count=5, best=5, last_day=SAT + timedelta(days=6),
                   freeze_day=SAT + timedelta(days=2))
        s = record_day(s, SAT + timedelta(days=8))  # یکشنبه هفته بعد؛ شنبه جا افتاد
        assert s.count == 6 and s.freeze_day == SAT + timedelta(days=7)

    def test_two_missed_days_break(self) -> None:
        s = Streak(count=4, best=4, last_day=SAT)
        s = record_day(s, SAT + timedelta(days=3))
        assert s.count == 1 and s.best == 4

    def test_current_streak_survives_until_tomorrow(self) -> None:
        s = Streak(count=4, best=4, last_day=SAT)
        assert current_streak(s, SAT) == 4
        assert current_streak(s, SAT + timedelta(days=1)) == 4
        assert current_streak(s, SAT + timedelta(days=2)) == 4  # یخ‌زدن هنوز مانده
        assert current_streak(s, SAT + timedelta(days=3)) == 0

    def test_current_streak_without_freeze(self) -> None:
        s = Streak(count=4, best=4, last_day=SAT + timedelta(days=3),
                   freeze_day=SAT + timedelta(days=1))
        assert current_streak(s, SAT + timedelta(days=5)) == 0

    def test_empty_streak(self) -> None:
        assert current_streak(Streak(), SAT) == 0


class TestWeekMarks:
    def test_marks_done_frozen_and_today(self) -> None:
        s = Streak(count=3, best=3, last_day=SAT + timedelta(days=3),
                   freeze_day=SAT + timedelta(days=2))
        marks = week_marks(s, SAT + timedelta(days=4))
        assert marks == ["done", "done", "frozen", "done", "today", "", ""]

    def test_today_done(self) -> None:
        s = Streak(count=2, best=2, last_day=SAT + timedelta(days=1))
        assert week_marks(s, SAT + timedelta(days=1))[:3] == ["done", "done", ""]

    def test_broken_streak_marks_nothing(self) -> None:
        s = Streak(count=2, best=2, last_day=SAT)
        assert week_marks(s, SAT + timedelta(days=4)) == ["", "", "", "", "today", "", ""]


class TestCardLevel:
    @pytest.mark.parametrize(("base", "bonus", "expected"), [
        (10, 0, CardLevel(1, 10, 10)),
        (95, 4, CardLevel(1, 99, 99)),
        (95, 6, CardLevel(2, 1, 101)),
        (60, 40, CardLevel(2, 0, 100)),
        (90, 120, CardLevel(3, 10, 210)),
        (95, 400, CardLevel(3, 100, 300)),
    ])
    def test_three_levels_of_hundred(self, base: int, bonus: int, expected: CardLevel) -> None:
        assert card_level(base, bonus) == expected
        assert card_level(base, bonus).level <= MAX_LEVEL

    def test_knowledge_is_two_per_lesson(self) -> None:
        assert knowledge_bonus(0) == 0
        assert knowledge_bonus(6) == 12


class TestChecks:
    def test_choice(self) -> None:
        assert check_choice(1, 4, "1") is True
        assert check_choice(1, 4, "۰") is False  # ارقام فارسی
        assert check_choice(1, 4, "4") is None  # خارج از گزینه‌ها
        assert check_choice(1, 4, "x") is None

    def test_slider(self) -> None:
        months = Slider(low=1, high=12, right_low=3, right_high=6)
        assert check_slider(months, "3") is True
        assert check_slider(months, "6") is True
        assert check_slider(months, "2") is False
        assert check_slider(months, "7") is False
        assert check_slider(months, "13") is None
        assert check_slider(months, "") is None


class TestMoneyMath:
    def test_purchasing_power(self) -> None:
        assert purchasing_power(100_000_000, Decimal("0.35"), 1) == 74_074_074
        assert purchasing_power(100_000_000, Decimal("0.35"), 3) == 40_644_211

    def test_real_rate(self) -> None:
        assert round(real_rate(Decimal("0.30"), Decimal("0.35")), 4) == Decimal("-0.0370")

    def test_grow(self) -> None:
        assert grow(100_000_000, Decimal(2), Decimal(5)) == 250_000_000

    def test_lesson_inflation_uses_setting_in_sane_range(self) -> None:
        assert lesson_inflation(Decimal("0.4")) == Decimal("0.4")
        assert lesson_inflation(Decimal("0.02")) == Decimal("0.35")
        assert lesson_inflation(Decimal("3")) == Decimal("0.35")


class TestPrices:
    SERIES = [(date(2023, 10, 1), Decimal(100)), (date(2023, 10, 5), Decimal(110)),
              (date(2026, 10, 1), Decimal(500))]

    def test_price_on_takes_last_known_day(self) -> None:
        assert price_on(self.SERIES, date(2023, 10, 4)) == Decimal(100)
        assert price_on(self.SERIES, date(2023, 10, 5)) == Decimal(110)
        assert price_on(self.SERIES, date(2026, 12, 1)) == Decimal(500)

    def test_price_on_before_series_is_none(self) -> None:
        assert price_on(self.SERIES, date(2023, 9, 1)) is None
        assert price_on([], date(2023, 9, 1)) is None

    def test_years_before(self) -> None:
        assert years_before(date(2026, 10, 10), 3) == date(2023, 10, 10)
        assert years_before(date(2028, 2, 29), 3) == date(2025, 2, 28)
