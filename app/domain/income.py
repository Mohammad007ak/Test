"""نرمال‌سازی درآمد با دوره‌های مختلف به ماهانه."""

from decimal import Decimal

from app.domain.money import round_toman

MONTHS_PER_PERIOD: dict[str, int] = {"monthly": 1, "quarterly": 3, "yearly": 12}


def monthly_income_toman(amount_toman: int, frequency: str) -> int:
    try:
        months = MONTHS_PER_PERIOD[frequency]
    except KeyError as exc:
        raise ValueError(f"دوره نامعتبر: {frequency}") from exc
    return round_toman(Decimal(amount_toman) / months)
