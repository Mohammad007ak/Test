from datetime import date
from pathlib import Path

import pytest

from app.adapters.prices.base import PriceSourceError
from app.adapters.prices.history import AlanchandHistory, parse_history

FIXTURES = Path(__file__).parent.parent / "fixtures" / "prices" / "alanchand"


def read(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_currency_archive_goes_back_to_1386() -> None:
    points = parse_history(read("archive_usd.html"))
    assert points[0].day == date(2008, 1, 21) and points[0].price_toman == 940
    assert points[-1].price_toman == 269_500 and points[-1].real_price_toman is None
    days = [p.day for p in points]
    assert days == sorted(days) and len(days) == len(set(days))


def test_coin_page_has_price_and_intrinsic_value() -> None:
    points = parse_history(read("gold_sekkeh.html"))
    last = points[-1]
    assert last.price_toman > 100_000_000 and last.real_price_toman is not None
    assert points[0].real_price_toman == 23_529_932  # کسری گرد می‌شود


def test_timestamps_become_tehran_days() -> None:
    # 1790973000 = 20:30 UTC = نیمه‌شب تهران → همان روز تهران
    page = '<script>const fullPriceData = [{"timestamp":1790973000,"price":269500}];</script>'
    assert parse_history(page)[0].day == date(2026, 10, 3)


def test_bad_rows_skipped_and_missing_data_raises() -> None:
    page = ('<script>let fullPriceData = [{"timestamp":1,"price":0},{"price":5},'
            '{"timestamp":1790973000,"price":"7"}];</script>')
    assert [p.price_toman for p in parse_history(page)] == [7]
    with pytest.raises(PriceSourceError):
        parse_history("<html>نمودار نیست</html>")


def test_urls_per_key() -> None:
    source = AlanchandHistory(fetch_html=lambda url: read("archive_usd.html"))
    assert source.url("usd") == "https://alanchand.com/currencies-price/archive/usd"
    assert source.url("coin_emami") == "https://alanchand.com/gold-price/sekkeh"
    assert source.url("gold18_gram") == "https://alanchand.com/gold-price/18ayar"
    assert not source.supports("crypto:btc") and not source.supports("stock:فملی")
    assert source.fetch_history("usd")[0].price_toman == 940
