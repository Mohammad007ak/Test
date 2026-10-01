"""تحلیلگر وام: ساخت جریان نقدی ماهانه از دید وام‌گیرنده و محاسبه نرخ مؤثر با IRR.

سود سپرده‌ها (بلوکه و معدل‌گیری) ساده و بر پایه نرخ سالانه محاسبه می‌شود:
مبلغ × نرخ × ماه ÷ ۱۲، و همراه اصل سپرده در پایان مدت برمی‌گردد.
"""

from dataclasses import dataclass, replace
from decimal import Decimal, localcontext

from app.domain.money import round_toman

MONTHS_PER_YEAR = 12


@dataclass(frozen=True)
class LoanInput:
    amount_toman: int
    months: int
    installment_toman: int | None = None
    nominal_rate: Decimal | None = None  # نرخ اسمی سالانه، مثلاً 0.18
    upfront_fee_toman: int = 0
    guarantor_cost_toman: int = 0
    insurance_toman: int = 0
    blocked_deposit_toman: int = 0
    blocked_months: int = 0
    blocked_rate: Decimal = Decimal(0)
    averaging_deposit_toman: int = 0
    averaging_months: int = 0
    averaging_rate: Decimal = Decimal(0)
    inflation: Decimal = Decimal(0)
    monthly_income_toman: int = 0
    current_installments_toman: int = 0
    dti_threshold: Decimal = Decimal("0.35")


@dataclass(frozen=True)
class CostStep:
    label: str
    effective_rate: Decimal
    added_rate: Decimal


@dataclass(frozen=True)
class LoanResult:
    installment_toman: int
    cash_flows: list[int]
    monthly_rate: Decimal
    effective_rate: Decimal
    real_rate: Decimal
    net_received_toman: int
    total_paid_toman: int
    total_cost_toman: int
    dti_before: Decimal | None
    dti_after: Decimal | None
    dti_exceeds: bool
    cost_steps: list[CostStep]


def annuity_installment_toman(amount_toman: int, months: int, annual_rate: Decimal) -> int:
    """قسط ثابت (فرمول اقساطی رایج بانک‌ها) با نرخ ماهانه = نرخ سالانه ÷ ۱۲."""
    if months <= 0:
        raise ValueError("تعداد اقساط باید مثبت باشد")
    r = annual_rate / MONTHS_PER_YEAR
    if r == 0:
        return round_toman(Decimal(amount_toman) / months)
    growth = (1 + r) ** months
    return round_toman(Decimal(amount_toman) * r * growth / (growth - 1))


def simple_interest_toman(principal_toman: int, annual_rate: Decimal, months: int) -> int:
    return round_toman(Decimal(principal_toman) * annual_rate * months / MONTHS_PER_YEAR)


def resolve_installment(loan: LoanInput) -> int:
    if loan.installment_toman is not None:
        return loan.installment_toman
    if loan.nominal_rate is None:
        raise ValueError("مبلغ قسط یا نرخ اسمی لازم است")
    return annuity_installment_toman(loan.amount_toman, loan.months, loan.nominal_rate)


def build_cash_flows(loan: LoanInput) -> list[int]:
    """جریان نقدی ماهانه؛ اندیس صفر اولین ماه (شروع معدل‌گیری یا دریافت وام)."""
    installment = resolve_installment(loan)
    start = loan.averaging_months if loan.averaging_deposit_toman else 0
    horizon = start + max(loan.months, loan.blocked_months if loan.blocked_deposit_toman else 0)
    flows = [0] * (horizon + 1)

    if loan.averaging_deposit_toman:
        flows[0] -= loan.averaging_deposit_toman
        flows[start] += loan.averaging_deposit_toman + simple_interest_toman(
            loan.averaging_deposit_toman, loan.averaging_rate, loan.averaging_months
        )

    flows[start] += (
        loan.amount_toman
        - loan.upfront_fee_toman
        - loan.guarantor_cost_toman
        - loan.insurance_toman
        - loan.blocked_deposit_toman
    )
    for month in range(1, loan.months + 1):
        flows[start + month] -= installment

    if loan.blocked_deposit_toman:
        flows[start + loan.blocked_months] += loan.blocked_deposit_toman + simple_interest_toman(
            loan.blocked_deposit_toman, loan.blocked_rate, loan.blocked_months
        )
    return flows


def npv(rate: Decimal, flows: list[int]) -> Decimal:
    total = Decimal(0)
    discount = Decimal(1)
    factor = 1 + rate
    for flow in flows:
        total += flow / discount
        discount *= factor
    return total


_SCAN_START = Decimal("-0.5")
_SCAN_END = Decimal(1)
_SCAN_STEP = Decimal("0.0025")


def _bracket_root(flows: list[int]) -> tuple[Decimal, Decimal]:
    """نزدیک‌ترین بازه به صفر (نرخ ماهانه −۵۰٪ تا ۱۰۰٪) که NPV در آن تغییر علامت می‌دهد.

    جریان نقدی با سپرده برگشتی ممکن است چند ریشه داشته باشد؛ ریشه نزدیک صفر معنادار است.
    """
    up = down = Decimal(0)
    f_up = f_down = npv(Decimal(0), flows)
    if f_up == 0:
        return up, up
    while up < _SCAN_END or down > _SCAN_START:
        if up < _SCAN_END:
            nxt = up + _SCAN_STEP
            f_nxt = npv(nxt, flows)
            if f_up * f_nxt <= 0:
                return up, nxt
            up, f_up = nxt, f_nxt
        if down > _SCAN_START:
            nxt = down - _SCAN_STEP
            f_nxt = npv(nxt, flows)
            if f_down * f_nxt <= 0:
                return nxt, down
            down, f_down = nxt, f_nxt
    raise ValueError("برای این جریان نقدی نرخ بازده معقولی پیدا نشد")


def irr(flows: list[int]) -> Decimal:
    """نرخ دوره‌ای که NPV را صفر می‌کند؛ پیمایش برای یافتن بازه، سپس دوبخشی (بدون float)."""
    with localcontext() as ctx:
        ctx.prec = 40
        low, high = _bracket_root(flows)
        f_low = npv(low, flows)
        if f_low == 0:
            return low
        for _ in range(200):
            mid = (low + high) / 2
            f_mid = npv(mid, flows)
            if f_mid == 0 or high - low < Decimal("1e-20"):
                break
            if (f_mid > 0) == (f_low > 0):
                low, f_low = mid, f_mid
            else:
                high = mid
        return +((low + high) / 2)


def effective_annual_rate(monthly_rate: Decimal) -> Decimal:
    return (1 + monthly_rate) ** MONTHS_PER_YEAR - 1


def real_rate(effective_rate: Decimal, inflation: Decimal) -> Decimal:
    return (1 + effective_rate) / (1 + inflation) - 1


def _effective_rate_of(loan: LoanInput) -> Decimal:
    return effective_annual_rate(irr(build_cash_flows(loan)))


def cost_breakdown(loan: LoanInput) -> list[CostStep]:
    """اثر تجمعی هر هزینه پنهان روی نرخ مؤثر، به ترتیب اضافه شدن."""
    base = replace(
        loan,
        installment_toman=resolve_installment(loan),
        upfront_fee_toman=0,
        guarantor_cost_toman=0,
        insurance_toman=0,
        blocked_deposit_toman=0,
        averaging_deposit_toman=0,
    )
    stages: list[tuple[str, LoanInput]] = [("قسط‌ها به‌تنهایی", base)]
    if loan.upfront_fee_toman or loan.guarantor_cost_toman or loan.insurance_toman:
        base = replace(
            base,
            upfront_fee_toman=loan.upfront_fee_toman,
            guarantor_cost_toman=loan.guarantor_cost_toman,
            insurance_toman=loan.insurance_toman,
        )
        stages.append(("کارمزد، ضامن و بیمه", base))
    if loan.blocked_deposit_toman:
        base = replace(base, blocked_deposit_toman=loan.blocked_deposit_toman)
        stages.append(("سپرده بلوکه", base))
    if loan.averaging_deposit_toman:
        base = replace(base, averaging_deposit_toman=loan.averaging_deposit_toman)
        stages.append(("معدل‌گیری", base))

    steps: list[CostStep] = []
    previous = Decimal(0)
    for label, stage in stages:
        rate = _effective_rate_of(stage)
        steps.append(CostStep(label, rate, rate - previous if steps else rate))
        previous = rate
    return steps


def analyze_loan(loan: LoanInput) -> LoanResult:
    installment = resolve_installment(loan)
    flows = build_cash_flows(loan)
    monthly = irr(flows)
    effective = effective_annual_rate(monthly)
    received = sum(f for f in flows if f > 0)
    paid = -sum(f for f in flows if f < 0)

    dti_before = dti_after = None
    if loan.monthly_income_toman > 0:
        dti_before = Decimal(loan.current_installments_toman) / loan.monthly_income_toman
        after = loan.current_installments_toman + installment
        dti_after = Decimal(after) / loan.monthly_income_toman

    return LoanResult(
        installment_toman=installment,
        cash_flows=flows,
        monthly_rate=monthly,
        effective_rate=effective,
        real_rate=real_rate(effective, loan.inflation),
        net_received_toman=received,
        total_paid_toman=paid,
        total_cost_toman=paid - received,
        dti_before=dti_before,
        dti_after=dti_after,
        dti_exceeds=dti_after is not None and dti_after > loan.dti_threshold,
        cost_steps=cost_breakdown(loan),
    )
