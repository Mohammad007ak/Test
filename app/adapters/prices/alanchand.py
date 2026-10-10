"""آداپتور alanchand.com: خواندن جدول‌های صفحه‌های عمومی ارز و طلا.

- فقط صفحه‌های عمومی خوانده می‌شوند؛ مسیر /get-all-data در robots.txt ممنوع است و استفاده نمی‌شود.
- قیمت‌های هر دو صفحه تومانی‌اند. برای ارز «قیمت فروش» برداشته می‌شود.
- هر ارز یک ردیف اصلی (بازار آزاد) دارد و ردیف‌های حواله و بازارهای دیگر نادیده گرفته می‌شوند.
- ارزهایی که به ازای صد واحد قیمت دارند («صد ین ژاپن») به یک واحد تبدیل می‌شوند.
- اونس‌ها دلاری‌اند و کنار گذاشته می‌شوند.
- رمزارز: قیمت تومانی سایت برای کوین‌های ارزان گرد شده یا گاهی صفر است؛ در آن حالت
  قیمت دلاری × قیمت تتر حساب و برای «units» واحد ذخیره می‌شود تا دقت از دست نرود.
- از مهر ۱۴۰۵ ردیف دلار از صفحه ارزها برداشته شده؛ تا پیدا شدن منبع زنده، دلار از آخرین
  روز آرشیو (معمولاً یک روز عقب) برداشته و در هشدار منبع اعلام می‌شود.
- شکست یک صفحه بقیه را از کار نمی‌اندازد؛ فقط اگر هیچ قیمتی نیاید خطا داده می‌شود.
"""

import re
from collections.abc import Callable
from datetime import date, datetime
from decimal import Decimal
from html.parser import HTMLParser
from zoneinfo import ZoneInfo

import jdatetime

from app.adapters.prices.base import FetchedQuote, PriceSourceError
from app.adapters.prices.http import http_get
from app.domain.money import round_toman, to_persian_digits
from app.domain.normalize import normalize_digits

BASE_URL = "https://alanchand.com"
CURRENCIES_URL = f"{BASE_URL}/currencies-price"
GOLD_URL = f"{BASE_URL}/gold-price"
CRYPTO_URL = f"{BASE_URL}/crypto-price"

GOLD_KEYS: dict[str, str] = {
    "abshodeh": "gold_mesghal",
    "18ayar": "gold18_gram",
    "sekkeh": "coin_emami",
    "bahar": "coin_bahar",
    "nim": "coin_half",
    "rob": "coin_quarter",
    "sek": "coin_gram",
}

_ROW_URL = re.compile(r"/(currencies-price|gold-price|crypto-price)/([a-z0-9_]+)")
SITE_TOMAN_MIN = 100_000  # کمتر از این، قیمت تومانی سایت دقت کافی ندارد
SIGNIFICANT_TOMAN = 1_000_000  # قیمت ذخیره‌شده دست‌کم این‌قدر باشد (۶ رقم معنادار)
_PRICE = re.compile(r"[\d,]+")
USD_ARCHIVE_MAX_AGE_DAYS = 3  # آرشیو قدیمی‌تر از این جای قیمت لحظه‌ای را نمی‌گیرد
TEHRAN = ZoneInfo("Asia/Tehran")


class _Row:
    def __init__(self, section: str, slug: str, title: str) -> None:
        self.section, self.slug, self.title = section, slug, title
        self.cells: list[tuple[str, str]] = []  # (class، متن خود خانه بدون span درونی)
        self.spans: dict[str, str] = {}  # متن spanها بر اساس اولین class (tmn، dlr، ...)


class _TableParser(HTMLParser):
    """ردیف‌هایی از جدول که با کلیک به صفحه یک نماد می‌روند."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[_Row] = []
        self._row: _Row | None = None
        self._cell: list[str] | None = None
        self._cell_class = ""
        self._span_depth = 0
        self._span_classes: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = {k: v or "" for k, v in attrs}
        if tag == "tr":
            match = _ROW_URL.search(attr.get("onclick", ""))
            title = attr.get("title", "")
            self._row = _Row(match.group(1), match.group(2), title) if match else None
        elif tag == "td" and self._row is not None:
            self._cell, self._cell_class, self._span_depth = [], attr.get("class", ""), 0
        elif tag == "span" and self._cell is not None:
            self._span_depth += 1
            self._span_classes.append((attr.get("class", "").split() or [""])[0])

    def handle_endtag(self, tag: str) -> None:
        if tag == "span" and self._span_depth:
            self._span_depth -= 1
            self._span_classes.pop()
        elif tag == "td" and self._row is not None and self._cell is not None:
            self._row.cells.append((self._cell_class, " ".join("".join(self._cell).split())))
            self._cell = None
        elif tag == "tr" and self._row is not None:
            self.rows.append(self._row)
            self._row = None

    def handle_data(self, data: str) -> None:
        if self._cell is None or self._row is None:
            return
        if not self._span_depth:
            self._cell.append(data)
        elif self._span_classes[-1]:
            key = self._span_classes[-1]
            self._row.spans[key] = (self._row.spans.get(key, "") + data).strip()


def _rows(page: str, section: str) -> list[_Row]:
    parser = _TableParser()
    parser.feed(page)
    return [row for row in parser.rows if row.section == section]


def _toman(text: str) -> int | None:
    """«۲۶۹,۵۰۰» یا «۱۱۴,۶۸۰,۰۰۰ تومان» → عدد؛ مقدار دلاری یا خالی → None."""
    text = normalize_digits(text)
    if "$" in text:
        return None
    match = _PRICE.search(text)
    if not match:
        return None
    digits = match.group(0).replace(",", "")
    return int(digits) if digits else None


def parse_currencies(page: str) -> list[FetchedQuote]:
    """قیمت فروش بازار آزاد؛ ردیف‌های بعدی همان ارز (حواله، استانبول، هرات...) کنار می‌روند."""
    quotes: list[FetchedQuote] = []
    seen: set[str] = set()
    for row in _rows(page, "currencies-price"):
        if row.slug in seen:
            continue
        seen.add(row.slug)
        sell = next((text for cls, text in row.cells if "sellPrice" in cls), "")
        price = _toman(sell)
        if not price:
            continue
        if "صد " in row.title:
            price = round_toman(Decimal(price) / 100)
        quotes.append(FetchedQuote(row.slug, price))
    return quotes


def parse_gold(page: str) -> list[FetchedQuote]:
    quotes = []
    for row in _rows(page, "gold-price"):
        key = GOLD_KEYS.get(row.slug)
        price_cell = next((text for cls, text in row.cells if "priceTd" in cls), "")
        price = _toman(price_cell)
        if key and price:
            quotes.append(FetchedQuote(key, price))
    return quotes


def _usd(text: str) -> Decimal | None:
    cleaned = normalize_digits(text).replace(",", "").strip()
    try:
        value = Decimal(cleaned)
    except ArithmeticError:
        return None
    return value if value.is_finite() and value > 0 else None


def _scaled(per_unit: Decimal) -> tuple[int, int]:
    """قیمت یک واحد → (قیمت units واحد، units) با دست‌کم شش رقم معنادار."""
    units = 1
    while per_unit * units < SIGNIFICANT_TOMAN:
        units *= 10
    return round_toman(per_unit * units), units


def parse_crypto(page: str) -> list[FetchedQuote]:
    rows = _rows(page, "crypto-price")
    tether = next((_toman(r.spans.get("tmn", "")) for r in rows if r.slug == "usdt"), None)
    quotes = []
    for row in rows:
        site = _toman(row.spans.get("tmn", "")) or 0
        if site >= SITE_TOMAN_MIN:
            quotes.append(FetchedQuote(f"crypto:{row.slug}", site))
            continue
        usd = _usd(row.spans.get("dlr", ""))
        if usd is None or not tether:
            continue
        price, units = _scaled(usd * tether)
        quotes.append(FetchedQuote(f"crypto:{row.slug}", price, units))
    return quotes


def _tehran_today() -> date:
    return datetime.now(TEHRAN).date()


class AlanchandSource:
    name = "alanchand"

    def __init__(self, fetch_html: Callable[[str], str] | None = None,
                 today: Callable[[], date] = _tehran_today) -> None:
        # history ثابت‌هایش را از همین ماژول می‌گیرد؛ وارد کردن در سطح ماژول چرخه می‌سازد
        from app.adapters.prices.history import AlanchandHistory

        self._get = fetch_html or http_get
        self._history = AlanchandHistory(fetch_html=self._get)
        self._today = today
        self.warning = ""

    def _page(self, label: str, url: str, parse: Callable[[str], list[FetchedQuote]],
              problems: list[str]) -> list[FetchedQuote]:
        try:
            quotes = parse(self._get(url))
        except PriceSourceError as exc:
            problems.append(f"{label}: {exc}")
            return []
        if not quotes:
            problems.append(f"{label}: قالب صفحه عوض شده")
        return quotes

    def _usd_from_archive(self, problems: list[str]) -> list[FetchedQuote]:
        try:
            points = self._history.fetch_history("usd")
        except PriceSourceError as exc:
            problems.append(f"دلار در صفحه و آرشیو پیدا نشد ({exc})")
            return []
        if not points:
            problems.append("دلار در صفحه و آرشیو پیدا نشد")
            return []
        last = points[-1]
        shamsi = to_persian_digits(jdatetime.date.fromgregorian(date=last.day).strftime("%Y/%m/%d"))
        if (self._today() - last.day).days > USD_ARCHIVE_MAX_AGE_DAYS:
            problems.append(f"دلار در صفحه نیست و آرشیو قدیمی است ({shamsi})")
            return []
        problems.append(f"دلار از آرشیو روزانه ({shamsi})")
        return [FetchedQuote("usd", last.price_toman)]

    def fetch(self) -> list[FetchedQuote]:
        problems: list[str] = []
        currencies = self._page("ارز", CURRENCIES_URL, parse_currencies, problems)
        if not any(q.key == "usd" for q in currencies):
            currencies += self._usd_from_archive(problems)
        gold = self._page("طلا", GOLD_URL, parse_gold, problems)
        crypto = self._page("رمزارز", CRYPTO_URL, parse_crypto, problems)
        self.warning = " · ".join(problems)
        quotes = currencies + gold + crypto
        if not quotes:
            raise PriceSourceError(self.warning or "هیچ قیمتی دریافت نشد")
        return quotes
