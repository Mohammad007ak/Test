from app.domain.onboarding import Snapshot, infer_persona, monthly_left


def snap(**kw: object) -> Snapshot:
    base: dict[str, object] = {"kinds": frozenset(), "liquid_toman": 0, "monthly_fixed_toman": 0,
                               "monthly_income_toman": None, "pays_rent": False,
                               "owns_home": False}
    return Snapshot(**{**base, **kw})  # type: ignore[arg-type]


def test_nothing_known_infers_nothing() -> None:
    assert infer_persona(snap()) == {}


def test_interests_and_experience_follow_assets() -> None:
    got = infer_persona(snap(kinds=frozenset({"gold", "coin", "fx"})))
    assert got["interests"] == ["gold", "fx"]
    assert got["experience"] == "safe"
    assert infer_persona(snap(kinds=frozenset({"gold", "market"})))["experience"] == "market"
    assert infer_persona(snap(kinds=frozenset({"market", "crypto"})))["experience"] == "advanced"


def test_bank_or_cash_alone_says_nothing_about_experience() -> None:
    assert "experience" not in infer_persona(snap(kinds=frozenset({"bank", "cash"})))


def test_housing_from_rent_or_home() -> None:
    assert infer_persona(snap(pays_rent=True))["housing"] == "renter"
    assert infer_persona(snap(owns_home=True, kinds=frozenset({"home"})))["housing"] == "owner"


def test_emergency_months_from_liquid_money_and_fixed_costs() -> None:
    def months(liquid: int) -> object:
        return infer_persona(snap(liquid_toman=liquid, monthly_fixed_toman=20_000_000))["emergency"]

    assert months(5_000_000) == "none"        # کمتر از یک ماه
    assert months(40_000_000) == "lt3"        # ۲ ماه
    assert months(100_000_000) == "3_6"       # ۵ ماه
    assert months(200_000_000) == "gt6"       # ۱۰ ماه
    assert "emergency" not in infer_persona(snap(liquid_toman=10**9))  # هزینه ثابت نامعلوم


def test_no_income_is_known_only_when_user_said_zero() -> None:
    assert infer_persona(snap(monthly_income_toman=0))["income"] == "none"
    assert "income" not in infer_persona(snap(monthly_income_toman=30_000_000))


def test_monthly_left() -> None:
    assert monthly_left(snap(monthly_income_toman=30_000_000, monthly_fixed_toman=18_000_000)) \
        == 12_000_000
    assert monthly_left(snap(monthly_fixed_toman=5)) is None
