"""منابع قیمت: هر منبع یک آداپتور جدا پشت رابط PriceSource است (SPEC: منابع قیمت)."""

from app.adapters.prices.base import FetchedQuote, PriceSource, PriceSourceError

# منابع فعال؛ آداپتور alanchand پس از دسترسی به ساختار صفحه اضافه می‌شود
SOURCES: dict[str, type[PriceSource]] = {}

__all__ = ["SOURCES", "FetchedQuote", "PriceSource", "PriceSourceError"]
