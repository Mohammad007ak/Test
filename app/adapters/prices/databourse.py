"""آداپتور databourse.ir: قیمت سهام (دیده‌بان بازار) و صندوق‌های سرمایه‌گذاری.

- جدول‌ها در خود HTML صفحه‌اند (بدون API جداگانه).
- سهام: ستون «قیمت پایانی» (خانه‌ای با class=lastPrice؛ سرستون‌ها با خانه‌ها هم‌تعداد نیستند
  چون درصد تغییر در خانه جدا آمده)؛ کلید stock:<نماد>.
- صندوق: ستون «قیمت ابطال» (مبلغی که هنگام فروش واحد گرفته می‌شود)؛ کلید fund:<نام صندوق>،
  چون این صفحه نماد صندوق‌ها را ندارد. صندوق‌های بدون قیمت کنار گذاشته می‌شوند.
- قیمت‌ها ریالی‌اند؛ برای از دست نرفتن دقت، عدد ریالی به‌عنوان قیمت ۱۰ واحد به تومان
  ذخیره می‌شود (units=10).
- این صفحه‌ها کند تغییر می‌کنند و حجیم‌اند؛ هر ۱۰ دقیقه یک‌بار کافی است (min_interval).
"""

from collections.abc import Callable
from html.parser import HTMLParser

from app.adapters.prices.base import FetchedQuote, PriceSourceError
from app.adapters.prices.http import http_get
from app.domain.money import RIAL_PER_TOMAN
from app.domain.normalize import normalize_chars, normalize_digits

BASE_URL = "https://databourse.ir"
MARKETWATCH_URL = f"{BASE_URL}/marketwatch"
FUNDS_URL = f"{BASE_URL}/funds"
STOCK_PRICE_HEADER = "قیمت پایانی"
FUND_PRICE_HEADER = "قیمت ابطال"


class _Table(HTMLParser):
    """سرستون‌ها و متن خانه‌های اولین جدول صفحه."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.headers: list[str] = []
        self.rows: list[list[tuple[str, str]]] = []  # هر خانه: (class، متن)
        self._tables = 0
        self._text: list[str] | None = None
        self._row: list[tuple[str, str]] | None = None
        self._cls = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "table":
            self._tables += 1
        if self._tables != 1:
            return
        if tag == "tr":
            self._row = []
        elif tag in ("th", "td"):
            self._text = []
            self._cls = dict(attrs).get("class") or ""

    def handle_endtag(self, tag: str) -> None:
        if self._tables != 1:
            return
        if tag in ("th", "td") and self._text is not None:
            text = " ".join("".join(self._text).split())
            if tag == "th":
                self.headers.append(text)
            elif self._row is not None:
                self._row.append((self._cls, text))
            self._text = None
        elif tag == "tr" and self._row:
            self.rows.append(self._row)
            self._row = None
        elif tag == "table":
            self._tables += 1  # فقط جدول اول

    def handle_data(self, data: str) -> None:
        if self._text is not None:
            self._text.append(data)


def _name(text: str) -> str:
    return " ".join(normalize_chars(text).split())


def _rial(text: str) -> int | None:
    digits = normalize_digits(text).replace(",", "").strip()
    return int(digits) if digits.isdigit() and int(digits) > 0 else None


def _table(page: str, price_header: str) -> _Table:
    table = _Table()
    table.feed(page)
    if not any(h.startswith(price_header) for h in table.headers):
        raise PriceSourceError(f"ستون «{price_header}» پیدا نشد؛ قالب صفحه عوض شده")
    return table


def _quote(prefix: str, name: str, price_text: str) -> FetchedQuote | None:
    name, price = _name(name), _rial(price_text)
    if not (name and price):
        return None
    # عدد ریالی = قیمت RIAL_PER_TOMAN واحد به تومان؛ بدون گرد کردن
    return FetchedQuote(f"{prefix}:{name}", price, units=RIAL_PER_TOMAN)


def parse_marketwatch(page: str) -> list[FetchedQuote]:
    quotes = []
    for row in _table(page, STOCK_PRICE_HEADER).rows:
        symbol = next((text for cls, text in row if "symbol" in cls.split()), "")
        price = next((text for cls, text in row if "lastPrice" in cls.split()), "")
        if quote := _quote("stock", symbol, price):
            quotes.append(quote)
    return quotes


def parse_funds(page: str) -> list[FetchedQuote]:
    table = _table(page, FUND_PRICE_HEADER)
    column = next(i for i, h in enumerate(table.headers) if h.startswith(FUND_PRICE_HEADER))
    quotes = []
    for row in table.rows:
        if len(row) > column and (quote := _quote("fund", row[0][1], row[column][1])):
            quotes.append(quote)
    return quotes


class DatabourseSource:
    name = "databourse"
    min_interval = 600  # ثانیه

    def __init__(self, fetch_html: Callable[[str], str] | None = None) -> None:
        self._get = fetch_html or http_get

    def fetch(self) -> list[FetchedQuote]:
        quotes = parse_marketwatch(self._get(MARKETWATCH_URL)) + parse_funds(self._get(FUNDS_URL))
        if not quotes:
            raise PriceSourceError("هیچ قیمتی در صفحه‌ها پیدا نشد")
        return quotes
