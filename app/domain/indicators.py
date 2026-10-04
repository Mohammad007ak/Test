"""اندیکاتورهای تحلیل تکنیکال روی سری قیمت پایانی روزانه (Decimal، بدون float).

فقط قیمت پایانی داریم (نه سقف و کف روز)، پس اندیکاتورهایی مثل ATR یا استوکاستیک کامل
این‌جا نیستند. همه تابع‌ها اگر داده کافی نباشد None برمی‌گردانند.
"""

from collections.abc import Sequence
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

TRADING_DAYS = 365  # بازار ارز و طلای ایران هر روز قیمت دارد
RSI_OVERBOUGHT = Decimal(70)
RSI_OVERSOLD = Decimal(30)
PERIODS: dict[str, timedelta] = {
    "1d": timedelta(days=1), "1w": timedelta(days=7), "1m": timedelta(days=30),
    "3m": timedelta(days=91), "1y": timedelta(days=365), "5y": timedelta(days=5 * 365),
}

Series = Sequence[tuple[date, Decimal]]


def sma(values: Sequence[Decimal], window: int) -> Decimal | None:
    if len(values) < window or window <= 0:
        return None
    return sum(values[-window:], Decimal(0)) / window


def _ema_series(values: Sequence[Decimal], window: int) -> list[Decimal]:
    if len(values) < window:
        return []
    k = Decimal(2) / (window + 1)
    current = sum(values[:window], Decimal(0)) / window
    out = [current]
    for value in values[window:]:
        current = value * k + current * (1 - k)
        out.append(current)
    return out


def ema(values: Sequence[Decimal], window: int) -> Decimal | None:
    out = _ema_series(values, window)
    return out[-1] if out else None


def rsi(values: Sequence[Decimal], window: int = 14) -> Decimal | None:
    """RSI وایلدر."""
    if len(values) <= window:
        return None
    moves = [b - a for a, b in zip(values, values[1:], strict=False)]
    gain = sum((m for m in moves[:window] if m > 0), Decimal(0)) / window
    loss = sum((-m for m in moves[:window] if m < 0), Decimal(0)) / window
    for m in moves[window:]:
        gain = (gain * (window - 1) + max(m, Decimal(0))) / window
        loss = (loss * (window - 1) + max(-m, Decimal(0))) / window
    if loss == 0:
        return Decimal(100) if gain > 0 else Decimal(50)
    return Decimal(100) - Decimal(100) / (1 + gain / loss)


def macd(values: Sequence[Decimal], fast: int = 12, slow: int = 26,
         signal: int = 9) -> tuple[Decimal, Decimal, Decimal] | None:
    """(خط MACD، خط سیگنال، هیستوگرام)."""
    if len(values) < slow + signal:
        return None
    fast_series = _ema_series(values, fast)[slow - fast:]
    slow_series = _ema_series(values, slow)
    line = [f - s for f, s in zip(fast_series, slow_series, strict=True)]
    signal_line = _ema_series(line, signal)
    return line[-1], signal_line[-1], line[-1] - signal_line[-1]


def _std(values: Sequence[Decimal]) -> Decimal:
    mean = sum(values, Decimal(0)) / len(values)
    return (sum(((v - mean) ** 2 for v in values), Decimal(0)) / len(values)).sqrt()


def bollinger(values: Sequence[Decimal], window: int = 20,
              width: int = 2) -> tuple[Decimal, Decimal, Decimal] | None:
    """(میانه، باند بالا، باند پایین)."""
    if len(values) < window:
        return None
    recent = values[-window:]
    mid = sum(recent, Decimal(0)) / window
    band = _std(recent) * width
    return mid, mid + band, mid - band


def _returns(values: Sequence[Decimal]) -> list[Decimal]:
    return [(b - a) / a for a, b in zip(values, values[1:], strict=False) if a]


def volatility(values: Sequence[Decimal], window: int = 90) -> Decimal | None:
    """نوسان سالانه‌شده (انحراف معیار بازده روزانه × √۳۶۵) روی window روز آخر."""
    returns = _returns(values[-(window + 1):])
    if len(returns) < 10:
        return None
    return _std(returns) * Decimal(TRADING_DAYS).sqrt()


def max_drawdown(values: Sequence[Decimal]) -> Decimal | None:
    """بیشترین افت از یک اوج تا کف بعدی، به نسبت اوج."""
    if not values:
        return None
    peak, worst = values[0], Decimal(0)
    for value in values:
        peak = max(peak, value)
        if peak:
            worst = max(worst, (peak - value) / peak)
    return worst


def _price_on_or_before(data: Series, day: date) -> Decimal | None:
    found = None
    for d, value in data:
        if d > day:
            break
        found = value
    return found


def change_since(data: Series, period: timedelta) -> Decimal | None:
    if not data:
        return None
    last_day, last = data[-1]
    if data[0][0] > last_day - period:
        return None
    base = _price_on_or_before(data, last_day - period)
    return (last - base) / base if base else None


def _round(value: Decimal | None, places: int = 4) -> Decimal | None:
    return None if value is None else round(value, places)


def summarize(data: Series) -> dict[str, Any]:
    """خلاصه تکنیکال برای نمایش و برای وزیر؛ عددها Decimal یا None."""
    values = [v for _d, v in data]
    out: dict[str, Any] = {"points": len(values), "last": values[-1] if values else None,
                           "from": data[0][0] if data else None,
                           "to": data[-1][0] if data else None}
    out["changes"] = {name: _round(change_since(data, p)) for name, p in PERIODS.items()}
    if not values:
        return out
    year = [v for d, v in data if d > data[-1][0] - PERIODS["1y"]]
    high, low = max(year), min(year)
    s20, s50, s200 = sma(values, 20), sma(values, 50), sma(values, 200)
    r = rsi(values)
    m = macd(values)
    b = bollinger(values)
    last = values[-1]
    out.update({
        "high_1y": high, "low_1y": low,
        "distance_from_high_1y": _round((last - high) / high) if high else None,
        "sma20": _round(s20, 2), "sma50": _round(s50, 2), "sma200": _round(s200, 2),
        "ema20": _round(ema(values, 20), 2),
        "above_sma50": None if s50 is None else last > s50,
        "above_sma200": None if s200 is None else last > s200,
        "golden_cross": None if s50 is None or s200 is None else s50 > s200,
        "rsi14": _round(r, 1),
        "rsi_state": None if r is None else ("overbought" if r >= RSI_OVERBOUGHT else
                                             "oversold" if r <= RSI_OVERSOLD else "neutral"),
        "macd": None if m is None else {"line": _round(m[0], 2), "signal": _round(m[1], 2),
                                        "histogram": _round(m[2], 2)},
        "bollinger20": None if b is None else {"mid": _round(b[0], 2), "upper": _round(b[1], 2),
                                               "lower": _round(b[2], 2)},
        "volatility_90d": _round(volatility(values)),
        "max_drawdown_1y": _round(max_drawdown(year)),
        "trend": _trend(last, s20, s50),
    })
    return out


def _trend(last: Decimal, s20: Decimal | None, s50: Decimal | None) -> str | None:
    if s20 is None or s50 is None:
        return None
    if last > s20 > s50:
        return "up"
    if last < s20 < s50:
        return "down"
    return "sideways"
