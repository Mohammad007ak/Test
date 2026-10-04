"""آرشیو قیمت روزانه از الان‌چند (فقط برای نمودار و تحلیل؛ قیمت لحظه‌ای جای دیگری است).

- ارزها: صفحه آرشیو /currencies-price/archive/<ارز> همه تاریخچه از ۱۳۸۶ را دارد.
- طلا و سکه: صفحه خود هر مورد حدود سه سال تاریخچه دارد؛ سکه‌ها «ارزش ذاتی» هم دارند.
- رمزارز و بورس: الان‌چند آرشیو ندارد؛ تاریخچه این‌ها از قیمت‌های خود اپ ساخته می‌شود.
داده در متغیر fullPriceData داخل صفحه است (نمونه واقعی در tests/fixtures).
"""

import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from typing import Protocol
from zoneinfo import ZoneInfo

from app.adapters.prices.alanchand import BASE_URL, GOLD_KEYS
from app.adapters.prices.base import PriceSourceError
from app.adapters.prices.http import http_get
from app.domain.money import round_toman

TEHRAN = ZoneInfo("Asia/Tehran")
_DATA = re.compile(r"(?:let|const|var)\s+fullPriceData\s*=\s*(\[.*?\]);", re.S)
_CURRENCY = re.compile(r"[a-z]{3}")
_SLUG_OF = {key: slug for slug, key in GOLD_KEYS.items()}


@dataclass(frozen=True)
class HistoryPoint:
    day: date  # روز تهران
    price_toman: int
    real_price_toman: int | None = None


class HistorySource(Protocol):
    name: str

    def supports(self, key: str) -> bool: ...

    def fetch_history(self, key: str) -> list[HistoryPoint]:
        """قیمت پایانی روزانه، قدیم به جدید؛ در صورت شکست PriceSourceError."""
        ...


def _toman(value: object) -> int | None:
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    return round_toman(amount) if amount.is_finite() and amount > 0 else None


def parse_history(page: str) -> list[HistoryPoint]:
    match = _DATA.search(page)
    if not match:
        raise PriceSourceError("آرشیو قیمت در صفحه پیدا نشد")
    try:
        rows = json.loads(match.group(1))
    except ValueError as exc:
        raise PriceSourceError("قالب آرشیو قیمت عوض شده") from exc
    by_day: dict[date, HistoryPoint] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        price = _toman(row.get("price"))
        stamp = row.get("timestamp")
        if price is None or not isinstance(stamp, int):
            continue
        day = datetime.fromtimestamp(stamp, UTC).astimezone(TEHRAN).date()
        by_day[day] = HistoryPoint(day, price, _toman(row.get("real_price")))  # آخرین قیمت هر روز
    return [by_day[d] for d in sorted(by_day)]


class AlanchandHistory:
    name = "alanchand"

    def __init__(self, fetch_html: Callable[[str], str] | None = None) -> None:
        self._get = fetch_html or http_get

    def url(self, key: str) -> str | None:
        if key in _SLUG_OF:
            return f"{BASE_URL}/gold-price/{_SLUG_OF[key]}"
        if _CURRENCY.fullmatch(key):
            return f"{BASE_URL}/currencies-price/archive/{key}"
        return None

    def supports(self, key: str) -> bool:
        return self.url(key) is not None

    def fetch_history(self, key: str) -> list[HistoryPoint]:
        url = self.url(key)
        if url is None:
            raise PriceSourceError(f"آرشیوی برای {key} نیست")
        return parse_history(self._get(url))
