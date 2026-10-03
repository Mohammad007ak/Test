"""ارزش‌گذاری دارایی و ثروت خالص."""

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal

from app.domain.money import round_toman

MARKET_KINDS = frozenset({"fx", "gold", "coin", "stock", "fund", "crypto"})
MANUAL_KINDS = frozenset({"car", "real_estate", "receivable", "cash", "other"})
GOLD_BASE_KARAT = 18


@dataclass(frozen=True)
class AssetHolding:
    kind: str
    quantity: Decimal | None
    karat: int | None
    price_key: str | None
    manual_value_toman: int | None


def asset_value_toman(asset: AssetHolding, prices: Mapping[str, Decimal | int]) -> int | None:
    """ارزش تومانی دارایی؛ None اگر قیمت بازار هنوز موجود نیست."""
    if asset.kind not in MARKET_KINDS:
        return asset.manual_value_toman
    if not asset.price_key or asset.price_key not in prices or asset.quantity is None:
        return None
    value = asset.quantity * prices[asset.price_key]
    if asset.kind == "gold":
        value = value * (asset.karat or GOLD_BASE_KARAT) / GOLD_BASE_KARAT
    return round_toman(value)


@dataclass(frozen=True)
class NetWorth:
    assets_toman: int
    liabilities_toman: int

    @property
    def networth_toman(self) -> int:
        return self.assets_toman - self.liabilities_toman

    def in_unit(self, unit_price_toman: int | None) -> Decimal | None:
        """ثروت بر حسب دلار یا گرم طلای ۱۸ (تقسیم بر قیمت واحد)."""
        if not unit_price_toman:
            return None
        return Decimal(self.networth_toman) / unit_price_toman


def debt_to_income(monthly_installments_toman: int, monthly_income_toman: int) -> Decimal | None:
    if monthly_income_toman <= 0:
        return None
    return Decimal(monthly_installments_toman) / monthly_income_toman
