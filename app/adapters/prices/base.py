"""رابط مشترک منابع قیمت."""

from dataclasses import dataclass
from typing import Protocol


class PriceSourceError(Exception):
    """منبع در دسترس نیست یا قالب پاسخش عوض شده."""


@dataclass(frozen=True)
class FetchedQuote:
    key: str  # usd، gold18_gram، coin_emami، stock:<نماد>، ...
    price_toman: int


class PriceSource(Protocol):
    name: str

    def fetch(self) -> list[FetchedQuote]:
        """قیمت‌های فعلی؛ در صورت شکست PriceSourceError."""
        ...
