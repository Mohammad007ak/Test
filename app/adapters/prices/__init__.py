"""منابع قیمت: هر منبع یک آداپتور جدا پشت رابط PriceSource است (SPEC: منابع قیمت)."""

from app.adapters.prices.alanchand import AlanchandSource
from app.adapters.prices.base import FetchedQuote, PriceSource, PriceSourceError
from app.adapters.prices.databourse import DatabourseSource

# منابع فعال
SOURCES: dict[str, type[PriceSource]] = {
    "alanchand": AlanchandSource,
    "databourse": DatabourseSource,
}

__all__ = ["SOURCES", "AlanchandSource", "DatabourseSource", "FetchedQuote", "PriceSource",
           "PriceSourceError"]
