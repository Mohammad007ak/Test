"""منابع قیمت: هر منبع یک آداپتور جدا پشت رابط PriceSource است (SPEC: منابع قیمت)."""

from app.adapters.prices.alanchand import AlanchandSource
from app.adapters.prices.base import FetchedQuote, PriceSource, PriceSourceError

# منابع فعال
SOURCES: dict[str, type[PriceSource]] = {"alanchand": AlanchandSource}

__all__ = ["SOURCES", "AlanchandSource", "FetchedQuote", "PriceSource", "PriceSourceError"]
