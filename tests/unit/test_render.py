from datetime import date

from app.web.render import jalali_long, sparkline


def test_sparkline_time_runs_left_to_right() -> None:
    line, area = sparkline([10, 20, 30], width=100, height=50)
    # قدیمی‌ترین (۱۰) در x=0 پایین؛ جدیدترین (۳۰) در x=100 و بالاترین نقطه (y کمینه)
    assert line.startswith("M0.0,") and line.endswith("L100.0,4.0")
    assert area.endswith("L100.0,50 L0.0,50 Z")


def test_sparkline_flat_and_short() -> None:
    line, _ = sparkline([5, 5], width=100, height=50)
    assert line == "M0.0,25.0 L100.0,25.0"
    assert sparkline([5], width=100, height=50) == ("", "")


def test_jalali_long() -> None:
    assert jalali_long(date(2026, 10, 3)) == "شنبه ۱۱ مهر"
