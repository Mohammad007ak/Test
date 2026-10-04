from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.domain.indicators import (
    bollinger,
    change_since,
    ema,
    macd,
    max_drawdown,
    rsi,
    sma,
    summarize,
    volatility,
)

D = Decimal


def prices(*values: float) -> list[Decimal]:
    return [D(str(v)) for v in values]


def series(values: list[Decimal], end: date = date(2026, 10, 1)) -> list[tuple[date, Decimal]]:
    start = end - timedelta(days=len(values) - 1)
    return [(start + timedelta(days=i), v) for i, v in enumerate(values)]


class TestAverages:
    def test_sma_last_window(self) -> None:
        assert sma(prices(1, 2, 3, 4, 5), 3) == D(4)
        assert sma(prices(1, 2), 3) is None

    def test_ema_seeds_with_sma_and_weights_recent(self) -> None:
        # k = 2/(3+1) = 0.5؛ بذر = میانگین ۱،۲،۳ = ۲؛ بعد: ۴→۳، ۵→۴
        assert ema(prices(1, 2, 3, 4, 5), 3) == D(4)
        assert ema(prices(1, 2), 3) is None


class TestOscillators:
    def test_rsi_all_gains_is_100_and_losses_0(self) -> None:
        assert rsi(prices(*range(1, 20)), 14) == D(100)
        assert rsi(prices(*range(20, 1, -1)), 14) == D(0)

    def test_rsi_known_value(self) -> None:
        # بالا و پایین برابر و یکی‌درمیان → حدود ۵۰
        values = prices(*([10, 11] * 15))
        value = rsi(values, 14)
        assert value is not None and D(45) < value < D(55)

    def test_rsi_needs_enough_data(self) -> None:
        assert rsi(prices(1, 2, 3), 14) is None

    def test_macd_positive_in_uptrend(self) -> None:
        result = macd(prices(*range(1, 60)))
        assert result is not None
        line, signal, hist = result
        assert line > 0 and signal > 0 and hist == line - signal

    def test_macd_needs_35_points(self) -> None:
        assert macd(prices(*range(1, 30))) is None

    def test_bollinger_flat_series_has_zero_width(self) -> None:
        mid, upper, lower = bollinger(prices(*([5] * 25)))
        assert mid == upper == lower == D(5)

    def test_bollinger_bands_symmetric(self) -> None:
        result = bollinger(prices(*range(1, 21)))
        assert result is not None
        mid, upper, lower = result
        assert mid == D("10.5") and upper - mid == mid - lower > 0


class TestRisk:
    def test_volatility_zero_for_constant_growth_ratio(self) -> None:
        values = [D(100) * D("1.01") ** i for i in range(30)]
        value = volatility(values)
        assert value is not None and value < D("1e-20")

    def test_volatility_positive_and_annualized(self) -> None:
        value = volatility(prices(*([100, 110] * 20)))
        assert value is not None and value > D(1)  # نوسان شدید روزانه، سالانه بیش از ۱۰۰٪

    def test_max_drawdown(self) -> None:
        # اوج ۲۰۰، کف بعدی ۱۰۰ → افت ۵۰٪
        assert max_drawdown(prices(100, 200, 150, 100, 180)) == D("0.5")
        assert max_drawdown(prices(1, 2, 3)) == D(0)


class TestChange:
    def test_change_since_uses_last_price_on_or_before(self) -> None:
        data = series(prices(100, 110, 120, 150))
        assert change_since(data, timedelta(days=2)) == D(40) / D(110)
        assert change_since(data, timedelta(days=3)) == D("0.5")

    def test_change_since_missing_history(self) -> None:
        assert change_since(series(prices(1, 2)), timedelta(days=30)) is None


def test_summarize_reports_signals() -> None:
    values = [D(100 + i) for i in range(260)]
    s = summarize(series(values))
    assert s["last"] == D(359)
    assert s["trend"] == "up"
    assert s["above_sma200"] is True and s["golden_cross"] is True
    assert s["rsi14"] == D(100) and s["rsi_state"] == "overbought"
    assert s["changes"]["1w"] is not None and s["changes"]["5y"] is None
    assert s["high_1y"] == D(359) and s["distance_from_high_1y"] == D(0)


@pytest.mark.parametrize("n", [0, 1])
def test_summarize_tiny_series(n: int) -> None:
    s = summarize(series([D(5)] * n))
    assert s["points"] == n
