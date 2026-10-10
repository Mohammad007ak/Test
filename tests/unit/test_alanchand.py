from datetime import date
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
# صفحه واقعی ۱۸ مهر ۱۴۰۵: الان‌چند ردیف دلار را برداشته
CURRENCIES_NO_USD = (FIXTURES / "currencies_no_usd.html").read_text(encoding="utf-8")
ARCHIVE_USD = (FIXTURES / "archive_usd.html").read_text(encoding="utf-8")  # آخرین روز: ۲۰۲۶-۱۰-۰۳
CURRENCIES_URL = "https://alanchand.com/currencies-price"
GOLD_URL = "https://alanchand.com/gold-price"
CRYPTO_URL = "https://alanchand.com/crypto-price"
ARCHIVE_URL = "https://alanchand.com/currencies-price/archive/usd"


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


def site(**overrides: str | None):  # type: ignore[no-untyped-def]
    """صفحه‌های سایت؛ None یعنی آن صفحه در دسترس نیست."""
    pages: dict[str, str | None] = {CURRENCIES_URL: CURRENCIES_NO_USD, GOLD_URL: GOLD,
                                    CRYPTO_URL: CRYPTO, ARCHIVE_URL: ARCHIVE_USD}
    pages.update({{"currencies": CURRENCIES_URL, "gold": GOLD_URL, "crypto": CRYPTO_URL,
                   "archive": ARCHIVE_URL}[name]: page for name, page in overrides.items()})
    fetched: list[str] = []

    def fetch(url: str) -> str:
        fetched.append(url)
        page = pages.get(url)
        if page is None:
            raise PriceSourceError(f"{url}: timeout")
        return page

    return fetch, fetched


def source(fetch, today: date = date(2026, 10, 4)) -> AlanchandSource:  # type: ignore[no-untyped-def]
    return AlanchandSource(fetch_html=fetch, today=lambda: today)


class TestUsdMissingFromLivePage:
    def test_usd_comes_from_daily_archive(self) -> None:
        fetch, _ = site()
        src = source(fetch)
        quotes = as_dict(src.fetch())
        assert quotes["usd"] == 269_500  # آخرین روز آرشیو
        assert quotes["eur"] == 301_200 and quotes["gold18_gram"] == 26_473_980
        assert "crypto:btc" in quotes
        assert "آرشیو" in src.warning and "۱۴۰۵/۰۷/۱۱" in src.warning

    def test_archive_not_fetched_when_live_usd_exists(self) -> None:
        fetch, fetched = site(currencies=CURRENCIES)
        src = source(fetch)
        assert as_dict(src.fetch())["usd"] == 269_500
        assert ARCHIVE_URL not in fetched and src.warning == ""

    def test_old_archive_is_not_used(self) -> None:
        fetch, _ = site()
        src = source(fetch, today=date(2026, 10, 20))
        quotes = as_dict(src.fetch())
        assert "usd" not in quotes and quotes["gold18_gram"] == 26_473_980
        assert "دلار" in src.warning

    def test_archive_failure_keeps_other_prices(self) -> None:
        fetch, _ = site(archive=None)
        src = source(fetch)
        quotes = as_dict(src.fetch())
        assert "usd" not in quotes and quotes["coin_emami"] == 274_000_000
        assert "دلار" in src.warning


class TestOnePageFailing:
    def test_gold_page_down_keeps_currencies_and_crypto(self) -> None:
        fetch, _ = site(currencies=CURRENCIES, gold=None)
        src = source(fetch)
        quotes = as_dict(src.fetch())
        assert quotes["usd"] == 269_500 and "crypto:btc" in quotes
        assert "gold18_gram" not in quotes and "طلا" in src.warning

    def test_changed_gold_layout_is_a_warning(self) -> None:
        fetch, _ = site(currencies=CURRENCIES, gold="<html></html>")
        src = source(fetch)
        assert "gold18_gram" not in as_dict(src.fetch()) and "طلا" in src.warning

    def test_currencies_page_down_keeps_gold(self) -> None:
        fetch, _ = site(currencies=None)
        src = source(fetch)
        quotes = as_dict(src.fetch())
        assert quotes["usd"] == 269_500 and quotes["gold18_gram"] == 26_473_980
        assert "eur" not in quotes and "ارز" in src.warning


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
