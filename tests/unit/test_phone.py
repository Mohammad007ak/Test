import pytest

from app.domain.phone import mask_phone, normalize_phone


@pytest.mark.parametrize("raw", [
    "09121234567", "۰۹۱۲۱۲۳۴۵۶۷", "+989121234567", "989121234567", "9121234567",
    "0912 123 4567", "0912-123-4567", "٠٩١٢١٢٣٤٥٦٧", "00989121234567",
])
def test_normalizes_iranian_mobiles(raw: str) -> None:
    assert normalize_phone(raw) == "09121234567"


@pytest.mark.parametrize("raw", ["", "0212345678", "0812345678", "091212345", "abc",
                                 "091212345678", "+14155551234"])
def test_rejects_non_mobiles(raw: str) -> None:
    with pytest.raises(ValueError):
        normalize_phone(raw)


def test_mask() -> None:
    assert mask_phone("09121234567") == "0912***4567"
