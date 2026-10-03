from datetime import UTC, datetime

import pytest

from app.domain.spending import (
    CategoryTotal,
    month_bounds_utc,
    shift_month,
    spending_by_category,
)


class TestMonthBounds:
    def test_mehr_1405_in_tehran(self) -> None:
        # ۱ مهر ۱۴۰۵ = ۲۳ سپتامبر ۲۰۲۶؛ تهران UTC+3:30 (بدون ساعت تابستانی)
        start, end = month_bounds_utc(1405, 7)
        assert start == datetime(2026, 9, 22, 20, 30, tzinfo=UTC)
        assert end == datetime(2026, 10, 22, 20, 30, tzinfo=UTC)  # ۱ آبان

    def test_esfand_rolls_to_next_year(self) -> None:
        start, end = month_bounds_utc(1404, 12)
        assert end == month_bounds_utc(1405, 1)[0]
        assert start < end


class TestShiftMonth:
    @pytest.mark.parametrize(("year", "month", "delta", "expected"), [
        (1405, 7, 1, (1405, 8)),
        (1405, 12, 1, (1406, 1)),
        (1405, 1, -1, (1404, 12)),
        (1405, 7, -13, (1404, 6)),
    ])
    def test_shift(self, year: int, month: int, delta: int, expected: tuple[int, int]) -> None:
        assert shift_month(year, month, delta) == expected


class TestSpendingByCategory:
    def test_groups_sorts_and_totals(self) -> None:
        rows = spending_by_category([("food", 300), ("bills", 500), ("food", 400), (None, 50)])
        assert rows == [CategoryTotal("food", 700), CategoryTotal("bills", 500),
                        CategoryTotal("uncategorized", 50)]

    def test_transfers_to_self_are_not_spending(self) -> None:
        rows = spending_by_category([("transfer", 9_000), ("food", 100)])
        assert rows == [CategoryTotal("food", 100)]

    def test_empty(self) -> None:
        assert spending_by_category([]) == []
