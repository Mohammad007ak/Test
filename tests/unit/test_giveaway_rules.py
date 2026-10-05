"""جایزه اینستاگرام: پاک‌سازی آیدی و بازه زمانی."""

from datetime import date

import pytest

from app.domain.giveaway import END, is_open, parse_handle


@pytest.mark.parametrize(("raw", "handle"), [
    ("getvazir", "getvazir"),
    ("@GetVazir", "getvazir"),
    ("  @ali.reza_79 ", "ali.reza_79"),
    ("https://www.instagram.com/ali.reza/", "ali.reza"),
    ("instagram.com/ali_reza?igsh=abc", "ali_reza"),
    ("ali۱۳۷۹", "ali1379"),
])
def test_parse_handle_accepts_common_forms(raw: str, handle: str) -> None:
    assert parse_handle(raw) == handle


@pytest.mark.parametrize("raw", ["", "@", "علی", "a b", "x" * 31, "ali..reza", ".ali", "ali."])
def test_parse_handle_rejects_invalid(raw: str) -> None:
    assert parse_handle(raw) is None


def test_open_until_end_of_25_mehr() -> None:
    assert END == date(2026, 10, 17)  # ۲۵ مهر ۱۴۰۵
    assert is_open(date(2026, 10, 5)) and is_open(END)
    assert not is_open(date(2026, 10, 18))
