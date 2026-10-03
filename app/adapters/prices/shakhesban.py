"""آداپتور shakhesban.com: قیمت پایانی سهام و صندوق‌های بورسی.

- robots.txt صفحه‌ها را مجاز و /api/ را ممنوع کرده؛ پس فقط صفحه جستجوی عمومی
  /markets/all?search=<نماد> خوانده می‌شود (جدول در خود HTML است).
- هر صفحه فهرست فقط ۱۰۰ ردیف دارد؛ برای همین فقط نمادهایی که کاربر دارد، یکی‌یکی
  جستجو می‌شوند (چند درخواست کوچک، هر ۱۰ دقیقه).
- قیمت «قیمت پایانی» ریالی است و به‌عنوان قیمت ۱۰ واحد به تومان ذخیره می‌شود (units=10).
- نماد پیدانشده یا معامله‌نشده در چند روز اخیر (نماد متوقف) به‌صورت هشدار گزارش می‌شود.
"""

import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from html import unescape
from urllib.parse import quote

import jdatetime

from app.adapters.prices.base import FetchedQuote, PriceSourceError
from app.adapters.prices.http import http_get
from app.domain.money import RIAL_PER_TOMAN
from app.domain.normalize import normalize_chars, normalize_digits

SEARCH_URL = "https://www.shakhesban.com/markets/all?search={query}"
STALE_DAYS = 7
FINAL_PRICE_COLUMN = 7  # نماد، نام، نوع بازار، بازار، آخرین قیمت (۳ خانه)، قیمت پایانی
DATE_COLUMN = 10

_ROW = re.compile(r'<tr data-symbol="([^"]*)">(.*?)</tr>', re.S)
_CELL = re.compile(r"<td[^>]*>(.*?)</td>", re.S)
_TAG = re.compile(r"<[^>]+>")


@dataclass(frozen=True)
class Row:
    symbol: str
    name: str
    market: str
    final_rial: int | None
    trade_date: date | None


def _clean(text: str) -> str:
    return " ".join(normalize_chars(unescape(_TAG.sub("", text))).split())


def _rial(text: str) -> int | None:
    digits = normalize_digits(_clean(text)).replace(",", "")
    return int(digits) if digits.isdigit() and int(digits) > 0 else None


def _date(text: str) -> date | None:
    try:
        year, month, day = (int(p) for p in normalize_digits(_clean(text)).split("/"))
        return jdatetime.date(year, month, day).togregorian()
    except ValueError:
        return None


def parse_search(page: str) -> list[Row]:
    rows = []
    for symbol, body in _ROW.findall(page):
        cells = _CELL.findall(body)
        if len(cells) <= DATE_COLUMN:
            continue
        rows.append(Row(_clean(symbol), _clean(cells[1]), _clean(cells[2]),
                        _rial(cells[FINAL_PRICE_COLUMN]), _date(cells[DATE_COLUMN])))
    return rows


class ShakhesbanSource:
    name = "shakhesban"
    min_interval = 600  # ثانیه

    def __init__(self, wanted: Callable[[], list[str]],
                 fetch_html: Callable[[str], str] | None = None,
                 today: Callable[[], date] = date.today, pause: float = 0.5) -> None:
        self._wanted = wanted  # کلیدهای stock:<نماد> و fund:<نماد> دارایی‌های کاربر
        self._get = fetch_html or http_get
        self._today = today
        self._pause = pause
        self.warning = ""

    def wanted_keys(self) -> list[str]:
        return self._wanted()

    def has_work(self) -> bool:
        return bool(self.wanted_keys())

    def fetch(self) -> list[FetchedQuote]:
        quotes: list[FetchedQuote] = []
        missing: list[str] = []
        stale: list[str] = []
        for index, key in enumerate(self._wanted()):
            if index and self._pause:
                time.sleep(self._pause)  # فشار کم روی سایت
            symbol = _clean(key.partition(":")[2])
            page = self._get(SEARCH_URL.format(query=quote(symbol)))
            row = next((r for r in parse_search(page) if r.symbol == symbol), None)
            if row is None or row.final_rial is None:
                missing.append(symbol)
                continue
            if row.trade_date and (self._today() - row.trade_date).days > STALE_DAYS:
                shamsi = jdatetime.date.fromgregorian(date=row.trade_date).strftime("%Y/%m/%d")
                stale.append(f"{symbol} (آخرین معامله {shamsi})")
            quotes.append(FetchedQuote(key, row.final_rial, units=RIAL_PER_TOMAN))
        parts = []
        if missing:
            parts.append("پیدا نشد: " + "، ".join(missing))
        if stale:
            parts.append("قیمت قدیمی: " + "، ".join(stale))
        self.warning = " · ".join(parts)
        if missing and not quotes:
            raise PriceSourceError(self.warning)
        return quotes
