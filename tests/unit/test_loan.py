"""موارد تست تحلیلگر وام.

مقادیر مورد انتظار با جریان نقدی مستقل محاسبه شده‌اند و باید با تابع IRR در اکسل
روی ستون «جریان نقدی» همان مورد یکی باشند (SPEC: سه مورد تطبیق با اکسل).
"""

from decimal import Decimal

import pytest

from app.domain.loan import (
    LoanInput,
    analyze_loan,
    annuity_installment_toman,
    build_cash_flows,
    irr,
    npv,
)

M = 10_000_000  # ده میلیون تومان


def test_annuity_installment_matches_textbook_value() -> None:
    # یک میلیارد تومان، ۱۲ ماه، ۱۸٪ → ۹۱٬۶۷۹٬۹۹۲٫۹ تومان
    assert annuity_installment_toman(100 * M, 12, Decimal("0.18")) == 91_679_993


def test_irr_of_known_flows() -> None:
    # Excel: =IRR({-100, 60, 60}) = 13.0662386%
    assert irr([-100, 60, 60]).quantize(Decimal("1e-9")) == Decimal("0.130662386")


def test_case1_simple_loan_effective_equals_compounded_nominal() -> None:
    result = analyze_loan(LoanInput(amount_toman=100 * M, months=12, nominal_rate=Decimal("0.18")))
    assert result.monthly_rate == pytest.approx(Decimal("0.015"), abs=Decimal("1e-8"))
    # (1.015)^12 - 1
    assert result.effective_rate == pytest.approx(Decimal("0.195618"), abs=Decimal("1e-6"))
    assert result.cash_flows[0] == 100 * M
    assert result.cash_flows[1:] == [-91_679_993] * 12
    assert result.total_cost_toman == 91_679_993 * 12 - 100 * M


def test_case2_blocked_deposit_raises_rate() -> None:
    loan = LoanInput(
        amount_toman=100 * M,
        months=12,
        nominal_rate=Decimal("0.18"),
        blocked_deposit_toman=20 * M,
        blocked_months=12,
        blocked_rate=Decimal(0),
    )
    flows = build_cash_flows(loan)
    assert flows[0] == 80 * M
    assert flows[12] == -91_679_993 + 20 * M
    result = analyze_loan(loan)
    assert npv(result.monthly_rate, flows) == pytest.approx(0, abs=Decimal("0.01"))
    # Excel: =IRR(B1:B13) ≈ 2.2921% ماهانه، نرخ مؤثر ≈ 31.25% (در برابر 18% اسمی)
    assert result.monthly_rate == pytest.approx(Decimal("0.0229213"), abs=Decimal("1e-7"))
    assert result.effective_rate == pytest.approx(Decimal("0.312522"), abs=Decimal("1e-6"))


def test_case3_averaging_shifts_loan_and_adds_negative_start() -> None:
    loan = LoanInput(
        amount_toman=100 * M,
        months=12,
        installment_toman=91_679_993,
        averaging_deposit_toman=50 * M,
        averaging_months=3,
        averaging_rate=Decimal(0),
        upfront_fee_toman=2 * M,
    )
    flows = build_cash_flows(loan)
    assert len(flows) == 16
    assert flows[0] == -50 * M
    assert flows[3] == 50 * M + 98 * M
    assert flows[4:] == [-91_679_993] * 12
    result = analyze_loan(loan)
    assert npv(result.monthly_rate, flows) == pytest.approx(0, abs=Decimal("0.01"))
    # Excel: =IRR(B1:B16) ≈ 2.4728% ماهانه، نرخ مؤثر ≈ 34.06%
    assert result.monthly_rate == pytest.approx(Decimal("0.0247278"), abs=Decimal("1e-7"))
    labels = [step.label for step in result.cost_steps]
    assert labels == ["قسط‌ها به‌تنهایی", "کارمزد، ضامن و بیمه", "معدل‌گیری"]
    assert all(step.added_rate > 0 for step in result.cost_steps)
    assert result.cost_steps[-1].effective_rate == result.effective_rate


def test_deposit_interest_lowers_rate() -> None:
    base = dict(amount_toman=100 * M, months=12, nominal_rate=Decimal("0.18"),
                blocked_deposit_toman=20 * M, blocked_months=12)
    without = analyze_loan(LoanInput(**base))
    with_interest = analyze_loan(LoanInput(**base, blocked_rate=Decimal("0.2")))
    assert with_interest.effective_rate < without.effective_rate


def test_real_rate_and_dti() -> None:
    result = analyze_loan(
        LoanInput(
            amount_toman=100 * M,
            months=12,
            nominal_rate=Decimal("0.18"),
            inflation=Decimal("0.40"),
            monthly_income_toman=300 * M,
            current_installments_toman=30 * M,
        )
    )
    tight = analyze_loan(
        LoanInput(amount_toman=100 * M, months=12, nominal_rate=Decimal("0.18"),
                  monthly_income_toman=30 * M, current_installments_toman=2 * M)
    )
    assert tight.dti_exceeds
    assert result.real_rate == pytest.approx(Decimal("1.195618") / Decimal("1.4") - 1,
                                              abs=Decimal("1e-6"))
    assert result.real_rate < 0
    assert result.dti_before == Decimal("0.1")
    assert result.dti_after == pytest.approx(Decimal("0.13056"), abs=Decimal("1e-5"))
    assert not result.dti_exceeds


def test_requires_installment_or_rate() -> None:
    with pytest.raises(ValueError):
        analyze_loan(LoanInput(amount_toman=100 * M, months=12))
