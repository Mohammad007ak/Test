from decimal import Decimal

import pytest

from app.domain.money import (
    format_number,
    format_percent,
    format_toman,
    format_toman_short,
    rial_to_toman,
)
from app.domain.normalize import normalize_text, parse_decimal, parse_int


@pytest.mark.parametrize(
    "text,expected",
    [
        ("۱۲٬۵۰۰٬۰۰۰", 12_500_000),
        ("١٢,٥٠٠", 12_500),
        ("12 500 000", 12_500_000),
        ("  ۷ ", 7),
    ],
)
def test_parse_int_accepts_all_digit_systems(text: str, expected: int) -> None:
    assert parse_int(text) == expected


@pytest.mark.parametrize("text", ["", "abc", "۱۲٫۵", "1.5"])
def test_parse_int_rejects_invalid(text: str) -> None:
    with pytest.raises(ValueError):
        parse_int(text)


@pytest.mark.parametrize(
    "text,expected",
    [("۲٫۵", Decimal("2.5")), ("2.75", Decimal("2.75")), ("۱٬۰۰۰", Decimal(1000))],
)
def test_parse_decimal(text: str, expected: Decimal) -> None:
    assert parse_decimal(text) == expected


def test_parse_decimal_rejects_nan() -> None:
    with pytest.raises(ValueError):
        parse_decimal("nan")


def test_normalize_text_fixes_arabic_letters_and_digits() -> None:
    assert normalize_text(" بانك ملي ۱۲۳ ") == "بانک ملی 123"


def test_rial_input_converts_to_whole_toman() -> None:
    assert rial_to_toman(812_000_000) == 81_200_000
    assert rial_to_toman(12_345) == 1_235  # ROUND_HALF_UP


def test_format_number_uses_persian_digits_and_separators() -> None:
    assert format_number(1234567) == "۱٬۲۳۴٬۵۶۷"
    assert format_number(Decimal("2.345"), 2) == "۲٫۳۵"


def test_format_toman() -> None:
    assert format_toman(81_200_000) == "۸۱٬۲۰۰٬۰۰۰ تومان"


@pytest.mark.parametrize(
    "toman,expected",
    [
        (81_200_000, "۸۱٫۲ میلیون تومان"),
        (5_000_000, "۵ میلیون تومان"),
        (1_234_000_000, "۱٫۲ میلیارد تومان"),
        (9_500, "۹٬۵۰۰ تومان"),
        (-81_200_000, "-۸۱٫۲ میلیون تومان"),
    ],
)
def test_format_toman_short(toman: int, expected: str) -> None:
    assert format_toman_short(toman) == expected


def test_format_percent() -> None:
    assert format_percent(Decimal("0.195618")) == "۱۹٫۶٪"
