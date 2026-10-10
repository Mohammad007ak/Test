"""قالب یادگرفته: متن پیامک با جاهای خالی که یک بار از پاسخ LLM ساخته می‌شود."""

from datetime import UTC, datetime

import pytest

from app.sms.templates import (
    SmsReading,
    TemplateError,
    check_template,
    learn,
    read_with,
)

T0 = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)
BLU = ("بلو\nبرداشت پول\nکاربر عزیز، 30,000,000 ریال از حساب شما پرید.\n"
       "موجودی: 86,552,338 ریال\n16:12\n1405.07.09")
BLU_TEMPLATE = ("بلو\nبرداشت پول\nکاربر عزیز، {amount} ریال از حساب شما پرید.\n"
                "موجودی: {balance} ریال\n{time}\n{date}")
CARD = "بانک نمونه\nکارت ************1234\nخرید 250,000 تومان\nمانده 8,125,000\n07/06_11:45"
CARD_TEMPLATE = "بانک نمونه\nکارت {account}\nخرید {amount} تومان\nمانده {balance}\n{date}_{time}"


def reading(template: str, **kw: object) -> SmsReading:
    values: dict[object, object] = {"bank": "blu", "direction": "out",
                                     "amount": 30_000_000, "balance": 86_552_338,
                                     "unit": "rial", "template": template}
    values.update(kw)
    return SmsReading(**values)  # type: ignore[arg-type]


def test_template_reads_amount_balance_and_jalali_datetime() -> None:
    parsed = read_with(learn(BLU, reading(BLU_TEMPLATE)), BLU, T0)
    assert parsed is not None
    assert (parsed.bank, parsed.direction, parsed.account_mask) == ("blu", "out", "")
    assert (parsed.amount_rial, parsed.balance_after_rial) == (30_000_000, 86_552_338)
    # ۹ مهر ۱۴۰۵ ساعت ۱۶:۱۲ تهران = ۱۲:۴۲ UTC
    assert parsed.occurred_at == datetime(2026, 10, 1, 12, 42, tzinfo=UTC)


def test_same_format_with_other_numbers_matches_without_llm() -> None:
    template = learn(BLU, reading(BLU_TEMPLATE))
    other = BLU.replace("30,000,000", "1,250,000").replace("86,552,338", "5,000")
    parsed = read_with(template, other, T0)
    assert parsed is not None
    assert (parsed.amount_rial, parsed.balance_after_rial) == (1_250_000, 5_000)


def test_other_format_does_not_match() -> None:
    template = learn(BLU, reading(BLU_TEMPLATE))
    assert read_with(template, BLU.replace("پرید", "رفت"), T0) is None


def test_toman_amounts_become_rial_and_account_mask_is_read() -> None:
    template = learn(CARD, reading(CARD_TEMPLATE, bank="mellat", amount=250_000,
                                   balance=8_125_000, unit="toman"))
    parsed = read_with(template, CARD, T0)
    assert parsed is not None
    assert (parsed.amount_rial, parsed.balance_after_rial) == (2_500_000, 81_250_000)
    assert (parsed.account_mask, parsed.account_prefix) == ("1234", "")
    assert parsed.occurred_at is not None and parsed.occurred_at.month == 9  # ۶ مهر


def test_account_prefix_is_kept() -> None:
    text = "حساب 814***5678\nواریز 10,000"
    template = learn(text, reading("حساب {account}\nواریز {amount}", bank="saman",
                                   direction="in", amount=10_000, balance=None))
    parsed = read_with(template, text, T0)
    assert parsed is not None and (parsed.account_prefix, parsed.account_mask) == ("814", "5678")


def test_any_placeholder_hides_names() -> None:
    text = "آقای رضایی عزیز\nبرداشت 5,000"
    template = learn(text, reading("{any} عزیز\nبرداشت {amount}", amount=5_000, balance=None))
    assert "رضایی" not in template.pattern
    assert read_with(template, "خانم احمدی عزیز\nبرداشت 7,000", T0) is not None


def test_template_that_does_not_reproduce_llm_values_is_rejected() -> None:
    with pytest.raises(TemplateError):
        learn(BLU, reading(BLU_TEMPLATE, amount=3_000_000))
    with pytest.raises(TemplateError):
        learn(BLU, reading(BLU_TEMPLATE, balance=1))
    with pytest.raises(TemplateError):  # قالب با متن جور نیست
        learn(BLU, reading(BLU_TEMPLATE.replace("پرید", "رفت")))


@pytest.mark.parametrize("template", [
    "برداشت",  # بدون مبلغ
    "{amount} {amount}",  # مبلغ دو بار
    "{amount} {foo}",  # جای خالی ناشناخته
    "حساب 1234 {amount}",  # عدد در متن ثابت (به اشتراک گذاشته نمی‌شود)
])
def test_invalid_templates(template: str) -> None:
    with pytest.raises(TemplateError):
        check_template(template)


def test_unknown_bank_or_direction_is_rejected() -> None:
    with pytest.raises(TemplateError):
        learn(BLU, reading(BLU_TEMPLATE, bank="nowhere"))
    with pytest.raises(TemplateError):
        learn(BLU, reading(BLU_TEMPLATE, direction="sideways"))
