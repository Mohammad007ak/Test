import pytest

from app.sms.text import content_hash, mask_numbers, prepare


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("کارت 6037991234561234 برداشت", "کارت ************1234 برداشت"),
        ("کارت 6037-9912-3456-1234", "کارت ************1234"),
        ("حساب 0123.4567.8901", "حساب ********8901"),
        ("حساب ۰۱۲۳۴۵۶۷۸۹۰۱", "حساب ********8901"),
        ("شبا IR120170000000123456789012", "شبا IR" + "*" * 20 + "9012"),
    ],
)
def test_long_numbers_keep_only_last_four(raw: str, expected: str) -> None:
    assert mask_numbers(prepare(raw)) == expected


@pytest.mark.parametrize(
    "text",
    [
        "مبلغ 25,000,000 ریال",   # مبلغ با جداکننده دست نمی‌خورد
        "مانده 812,500,000",
        "ساعت 09:42 تاریخ 1405/07/11",
        "رمز پویا 123456",          # کوتاه‌تر از ۱۰ رقم
    ],
)
def test_amounts_dates_and_short_codes_are_kept(text: str) -> None:
    assert mask_numbers(prepare(text)) == text


def test_prepare_normalises_digits_and_letters() -> None:
    assert prepare("بانك ملي\r\nمبلغ ۲۵٬۰۰۰ ") == "بانک ملی\nمبلغ 25٬000"


def test_hash_ignores_whitespace_differences() -> None:
    assert content_hash("برداشت  25,000\n") == content_hash("برداشت 25,000")
    assert content_hash("برداشت 25,000") != content_hash("برداشت 26,000")
