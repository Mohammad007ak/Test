from decimal import Decimal
from pathlib import Path

import pytest

from app.adapters.prices import PriceSourceError
from app.adapters.prices.alanchand import (
    AlanchandSource,
    parse_crypto,
    parse_currencies,
    parse_gold,
)

FIXTURES = Path(__file__).parent.parent / "fixtures" / "prices" / "alanchand"
CURRENCIES = (FIXTURES / "currencies.html").read_text(encoding="utf-8")
GOLD = (FIXTURES / "gold.html").read_text(encoding="utf-8")
CRYPTO = (FIXTURES / "crypto.html").read_text(encoding="utf-8")


def as_dict(quotes):  # type: ignore[no-untyped-def]
    return {q.key: q.price_toman for q in quotes}


def test_currencies_use_sell_price_in_toman() -> None:
    prices = as_dict(parse_currencies(CURRENCIES))
    assert prices["usd"] == 269_500
    assert prices["eur"] == 303_300
    assert prices["aed"] == 73_370
    assert len(prices) == 38  # ردیف‌های حواله و دلار استانبول/هرات قیمت اصلی را عوض نمی‌کنند


def test_per_hundred_units_are_divided() -> None:
    prices = as_dict(parse_currencies(CURRENCIES))
    # «صد ین ژاپن»، «صد دینار عراق» و ... به ازای ۱۰۰ واحد قیمت‌گذاری شده‌اند
    assert prices["jpy"] == 1_707  # ۱۷۰٬۷۰۰ برای صد ین
    assert prices["iqd"] == 171
    assert prices["gbp"] == 353_300  # ارز معمولی دست نمی‌خورد


def test_gold_and_coins() -> None:
    prices = as_dict(parse_gold(GOLD))
    assert prices == {
        "gold_mesghal": 114_680_000,
        "gold18_gram": 26_473_980,
        "coin_emami": 274_000_000,
        "coin_bahar": 260_000_000,
        "coin_half": 142_000_000,
        "coin_quarter": 78_000_000,
        "coin_gram": 38_000_000,
    }  # اونس‌ها به دلارند و کنار گذاشته می‌شوند


def test_source_fetches_both_pages() -> None:
    pages = {"https://alanchand.com/currencies-price": CURRENCIES,
             "https://alanchand.com/gold-price": GOLD,
             "https://alanchand.com/crypto-price": CRYPTO}
    quotes = as_dict(AlanchandSource(fetch_html=pages.__getitem__).fetch())
    assert quotes["usd"] == 269_500 and quotes["gold18_gram"] == 26_473_980
    assert quotes["crypto:btc"] == 22_762_553_884


def test_changed_layout_is_reported() -> None:
    source = AlanchandSource(fetch_html=lambda url: "<html><body>maintenance</body></html>")
    with pytest.raises(PriceSourceError):
        source.fetch()


def test_network_error_is_reported() -> None:
    def broken(url: str) -> str:
        raise PriceSourceError("timeout")

    with pytest.raises(PriceSourceError):
        AlanchandSource(fetch_html=broken).fetch()



class TestCrypto:
    def quotes(self):  # type: ignore[no-untyped-def]
        return {q.key: q for q in parse_crypto(CRYPTO)}

    def test_large_coins_use_site_toman_price(self) -> None:
        q = self.quotes()
        assert (q["crypto:btc"].price_toman, q["crypto:btc"].units) == (22_762_553_884, 1)
        assert (q["crypto:usdt"].price_toman, q["crypto:usdt"].units) == (268_680, 1)

    def test_tiny_coins_keep_precision_via_usd_and_tether(self) -> None:
        shib = self.quotes()["crypto:shib"]  # سایت «۲ تومان» نشان می‌دهد
        # ۰٫۰۰۰۰۰۵۷ دلار × ۲۶۸٬۶۸۰ تومان = ۱٫۵۳۱۴۷۶ تومان برای هر شیبا
        assert shib.units == 1_000_000
        assert shib.price_toman == 1_531_476

    def test_broken_zero_toman_price_is_derived_from_usd(self) -> None:
        ton = self.quotes()["crypto:ton"]  # سایت «۰ تومان» نشان می‌دهد ولی ۱٫۶ دلار
        assert Decimal(ton.price_toman) / ton.units == Decimal("429888")

    def test_all_coins_present(self) -> None:
        assert len(self.quotes()) == 40
