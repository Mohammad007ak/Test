import pytest

from app.sms.text import content_hash, is_secret, mask_numbers, prepare


@pytest.mark.parametrize(
    "raw,expected",
    [
        # کارت و شبا (۱۶ رقم و بیشتر): فقط ۴ رقم آخر
        ("کارت 6037991234561234 برداشت", "کارت ************1234 برداشت"),
        ("کارت 6037-9912-3456-1234", "کارت ************1234"),
        ("شبا IR120170000000123456789012", "شبا IR" + "*" * 20 + "9012"),
        # حساب (۱۰ تا ۱۵ رقم): ابتدای شماره + ۴ رقم آخر تا حساب‌های هم‌انتها جدا شوند
        ("از 814-20-1234567-1", "از 814******5671"),
        ("از 2137-800-1234567-1", "از 2137*******5671"),
        ("777.888.11425454.1", "777********4541"),
        ("حساب 0123.4567.8901", "حساب 0123****8901"),
        ("حساب ۰۱۲۳۴۵۶۷۸۹۰۱", "حساب 012*****8901"),
        ("30100758026608", "301*******6608"),
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


@pytest.mark.parametrize("text", [
    "بانک ملت\nرمز پویا: 482913",
    "کد تأیید ورود شما: 5521",
    "كد تاييد شما ۱۲۳۴",           # «ك/ي» عربی و ارقام فارسی
    "Your OTP is 9911",
    "رمز دوم یکبار مصرف 771122",
])
def test_secret_messages_are_detected(text: str) -> None:
    assert is_secret(text)


@pytest.mark.parametrize("text", [
    "بانک سامان\nبرداشت 1,200,000\nمانده 5,000,000",
    "واریز 500,000 ریال به حساب 814**1234\nکد پیگیری 3321",
])
def test_transaction_messages_are_not_secret(text: str) -> None:
    assert not is_secret(text)
