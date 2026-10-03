from datetime import date

from app.web.render import jalali_long, sparkline


def test_sparkline_latest_on_left_for_rtl() -> None:
    line, area = sparkline([10, 20, 30], width=100, height=50)
    # جدیدترین (۳۰) در x=0 و بالاترین نقطه (y کمینه)؛ قدیمی‌ترین در x=100 پایین
    assert line.startswith("M100.0,") and line.endswith("L0.0,4.0")
    assert area.endswith("L0.0,50 L100.0,50 Z")


def test_sparkline_flat_and_short() -> None:
    line, _ = sparkline([5, 5], width=100, height=50)
    assert line == "M100.0,25.0 L0.0,25.0"
    assert sparkline([5], width=100, height=50) == ("", "")


def test_jalali_long() -> None:
    assert jalali_long(date(2026, 10, 3)) == "شنبه ۱۱ مهر"
