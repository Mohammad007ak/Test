from decimal import Decimal

import pytest

from app.domain.income import monthly_income_toman
from app.domain.liabilities import (
    LiabilityTerms,
    monthly_installment_toman,
    remaining_balance_toman,
)
from app.domain.valuation import AssetHolding, NetWorth, asset_value_toman, debt_to_income


class TestLiabilities:
    def test_installment_loan_balance(self) -> None:
        terms = LiabilityTerms(1_000_000_000, 50_000_000, 24, 10)
        assert remaining_balance_toman(terms) == 700_000_000
        assert monthly_installment_toman(terms) == 50_000_000

    def test_fully_paid_loan(self) -> None:
        terms = LiabilityTerms(1_000_000_000, 50_000_000, 24, 24)
        assert remaining_balance_toman(terms) == 0
        assert monthly_installment_toman(terms) == 0

    def test_overpaid_counter_never_goes_negative(self) -> None:
        terms = LiabilityTerms(0, 50_000_000, 12, 15)
        assert remaining_balance_toman(terms) == 0

    def test_non_installment_debt_uses_principal(self) -> None:
        terms = LiabilityTerms(30_000_000, 0, 0, 0)
        assert remaining_balance_toman(terms) == 30_000_000
        assert monthly_installment_toman(terms) == 0


class TestIncome:
    @pytest.mark.parametrize(
        "amount,frequency,expected",
        [
            (400_000_000, "monthly", 400_000_000),
            (300_000_000, "quarterly", 100_000_000),
            (1_200_000_000, "yearly", 100_000_000),
            (100, "quarterly", 33),
            (200, "quarterly", 67),  # ROUND_HALF_UP
        ],
    )
    def test_normalizes_to_monthly(self, amount: int, frequency: str, expected: int) -> None:
        assert monthly_income_toman(amount, frequency) == expected

    def test_rejects_unknown_frequency(self) -> None:
        with pytest.raises(ValueError):
            monthly_income_toman(1, "weekly")


PRICES = {"usd": 1_000_000, "gold18_gram": 80_000_000, "coin_emami": 900_000_000}


class TestValuation:
    def test_fx(self) -> None:
        asset = AssetHolding("fx", Decimal(500), None, "usd", None)
        assert asset_value_toman(asset, PRICES) == 500_000_000

    def test_gold_scales_by_karat(self) -> None:
        asset = AssetHolding("gold", Decimal(10), 24, "gold18_gram", None)
        assert asset_value_toman(asset, PRICES) == 1_066_666_667

    def test_gold_18_karat(self) -> None:
        asset = AssetHolding("gold", Decimal("2.5"), 18, "gold18_gram", None)
        assert asset_value_toman(asset, PRICES) == 200_000_000

    def test_coin(self) -> None:
        asset = AssetHolding("coin", Decimal(2), None, "coin_emami", None)
        assert asset_value_toman(asset, PRICES) == 1_800_000_000

    def test_missing_price_returns_none(self) -> None:
        asset = AssetHolding("stock", Decimal(100), None, "stock:فولاد", None)
        assert asset_value_toman(asset, PRICES) is None

    def test_manual_kind(self) -> None:
        asset = AssetHolding("car", None, None, None, 15_000_000_000)
        assert asset_value_toman(asset, PRICES) == 15_000_000_000

    def test_networth_in_units(self) -> None:
        worth = NetWorth(assets_toman=3_000_000_000, liabilities_toman=1_000_000_000)
        assert worth.networth_toman == 2_000_000_000
        assert worth.in_unit(PRICES["usd"]) == Decimal(2000)
        assert worth.in_unit(PRICES["gold18_gram"]) == Decimal(25)
        assert worth.in_unit(None) is None

    def test_dti(self) -> None:
        assert debt_to_income(35, 100) == Decimal("0.35")
        assert debt_to_income(35, 0) is None
