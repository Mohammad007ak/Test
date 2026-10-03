from decimal import Decimal
from pathlib import Path

import pytest

from app.adapters.prices import PriceSourceError
from app.adapters.prices.databourse import DatabourseSource, parse_funds, parse_marketwatch

FIXTURES = Path(__file__).parent.parent / "fixtures" / "prices" / "databourse"
MARKETWATCH = (FIXTURES / "marketwatch.html").read_text(encoding="utf-8")
FUNDS = (FIXTURES / "funds.html").read_text(encoding="utf-8")


def per_unit(quotes):  # type: ignore[no-untyped-def]
    return {q.key: Decimal(q.price_toman) / q.units for q in quotes}


def test_stocks_use_closing_price_in_toman() -> None:
    prices = per_unit(parse_marketwatch(MARKETWATCH))
    # ستون «قیمت پایانی» (نه «آخرین قیمت»)، ریالی → تومان بدون گرد کردن
    assert prices["stock:تابان"] == Decimal("2295")
    assert prices["stock:فملی"] == Decimal("2812")
    assert prices["stock:شبریز"] == Decimal("5639")
    assert len(prices) == 25


def test_rial_prices_keep_full_precision() -> None:
    quote = next(q for q in parse_marketwatch(MARKETWATCH) if q.key == "stock:شپدیس")
    assert (quote.price_toman, quote.units) == (12_310, 10)  # ۱۲٬۳۱۰ ریال = قیمت ۱۰ سهم به تومان


def test_funds_use_redemption_price() -> None:
    prices = per_unit(parse_funds(FUNDS))
    assert prices["fund:اختصاصی بازارگردانی تاک دانا"] == Decimal("155307.1")
    assert prices["fund:اختصاصی بازارگردانی کوشا الگوریتم"] == Decimal("3446936.5")


def test_funds_without_price_are_skipped() -> None:
    keys = {q.key for q in parse_funds(FUNDS)}
    assert "fund:مشترک توسعه بازار سرمایه" not in keys
    assert "fund:زمین و ساختمان نسیم" not in keys
    assert len(keys) == 25


def test_source_fetches_both_pages() -> None:
    pages = {"https://databourse.ir/marketwatch": MARKETWATCH,
             "https://databourse.ir/funds": FUNDS}
    keys = {q.key for q in DatabourseSource(fetch_html=pages.__getitem__).fetch()}
    assert "stock:فملی" in keys and "fund:طلای عیار مفید" in keys


def test_changed_layout_is_reported() -> None:
    source = DatabourseSource(fetch_html=lambda url: "<html><body>maintenance</body></html>")
    with pytest.raises(PriceSourceError):
        source.fetch()


def test_symbols_are_normalised() -> None:
    page = MARKETWATCH.replace(">فملی<", ">فملي<")  # «ي» عربی
    assert "stock:فملی" in {q.key for q in parse_marketwatch(page)}
