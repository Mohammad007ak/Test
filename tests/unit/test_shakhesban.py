from datetime import date
from decimal import Decimal
from pathlib import Path
from urllib.parse import unquote

import pytest

from app.adapters.prices import PriceSourceError
from app.adapters.prices.shakhesban import ShakhesbanSource, parse_search

FIXTURES = Path(__file__).parent.parent / "fixtures" / "prices" / "shakhesban"
FAMELI = (FIXTURES / "search_fameli.html").read_text(encoding="utf-8")
AYAR = (FIXTURES / "search_ayar.html").read_text(encoding="utf-8")
TODAY = date(2026, 10, 3)  # ۱۱ مهر ۱۴۰۵


def test_parse_rows() -> None:
    rows = {r.symbol: r for r in parse_search(AYAR)}
    ayar = rows["عیار"]
    assert ayar.market == "صندوق ها"
    assert ayar.final_rial == 739_824  # «قیمت پایانی»، نه «آخرین قیمت» (۷۴۶٬۴۸۷)
    assert ayar.trade_date == date(2026, 10, 3)
    assert "معیار" in rows  # فاصله اضافه آخر نماد حذف می‌شود


def fake_site(url: str) -> str:
    query = unquote(url.rsplit("search=", 1)[-1])
    return {"فملی": FAMELI, "عیار": AYAR}.get(query, "<table></table>")


def source(*keys: str) -> ShakhesbanSource:
    return ShakhesbanSource(wanted=lambda: list(keys), fetch_html=fake_site, today=lambda: TODAY,
                            pause=0)


def test_fetches_only_owned_symbols_exactly() -> None:
    quotes = {q.key: q for q in source("stock:فملی", "fund:عیار").fetch()}
    assert set(quotes) == {"stock:فملی", "fund:عیار"}  # اختیار معامله‌های «ضملی...» نه
    fameli = quotes["stock:فملی"]
    assert (fameli.price_toman, fameli.units) == (28_120, 10)  # ریال = قیمت ۱۰ سهم به تومان
    assert Decimal(quotes["fund:عیار"].price_toman) / 10 == Decimal("73982.4")


def test_missing_symbol_becomes_warning() -> None:
    src = source("stock:فملی", "stock:ناموجود")
    assert [q.key for q in src.fetch()] == ["stock:فملی"]
    assert "ناموجود" in src.warning


def test_stale_trade_date_becomes_warning() -> None:
    old = FAMELI.replace("1405/07/11", "1405/04/26")
    src = ShakhesbanSource(wanted=lambda: ["stock:فملی"], fetch_html=lambda url: old,
                           today=lambda: TODAY, pause=0)
    assert [q.key for q in src.fetch()] == ["stock:فملی"]  # قیمت می‌ماند ولی هشدار دارد
    assert "فملی" in src.warning and "1405/04/26" in src.warning


def test_nothing_found_is_an_error() -> None:
    with pytest.raises(PriceSourceError):
        source("stock:ناموجود").fetch()


def test_has_work_only_with_owned_symbols() -> None:
    assert not source().has_work()
    assert source("stock:فملی").has_work()


def test_symbols_are_url_encoded() -> None:
    seen: list[str] = []
    src = ShakhesbanSource(wanted=lambda: ["stock:فملی"], today=lambda: TODAY, pause=0,
                           fetch_html=lambda url: seen.append(url) or FAMELI)
    src.fetch()
    assert seen == ["https://www.shakhesban.com/markets/all?search=%D9%81%D9%85%D9%84%DB%8C"]


def test_old_fund_saved_by_full_name_is_found_by_name() -> None:
    src = ShakhesbanSource(wanted=lambda: ["fund:طلای عیار مفید"], fetch_html=lambda url: AYAR,
                           today=lambda: TODAY, pause=0)
    quotes = src.fetch()
    assert [(q.key, q.price_toman) for q in quotes] == [("fund:طلای عیار مفید", 739_824)]


def test_ambiguous_name_is_not_guessed() -> None:
    src = ShakhesbanSource(wanted=lambda: ["fund:دیبای معیار"], fetch_html=lambda url: AYAR,
                           today=lambda: TODAY, pause=0)
    with pytest.raises(PriceSourceError):  # «دیبای معیار» در دو صندوق آمده
        src.fetch()
