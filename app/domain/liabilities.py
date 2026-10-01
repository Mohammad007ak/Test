"""مانده و قسط ماهانه بدهی‌ها."""

from dataclasses import dataclass


@dataclass(frozen=True)
class LiabilityTerms:
    principal_toman: int
    installment_toman: int
    installments_total: int
    installments_paid: int


def remaining_installments(terms: LiabilityTerms) -> int:
    return max(terms.installments_total - terms.installments_paid, 0)


def remaining_balance_toman(terms: LiabilityTerms) -> int:
    """بدهی قسطی: قسط × اقساط باقی‌مانده؛ بدهی بدون قسط (کارت، شخصی): اصل مبلغ."""
    if terms.installments_total <= 0:
        return terms.principal_toman
    return terms.installment_toman * remaining_installments(terms)


def monthly_installment_toman(terms: LiabilityTerms) -> int:
    if terms.installments_total <= 0 or remaining_installments(terms) == 0:
        return 0
    return terms.installment_toman
