"""راه‌اندازی اولیه: از داده‌هایی که کاربر همان اول ثبت کرده، جواب پیش‌فرض پرسونا را حدس می‌زند.

هر حدس فقط پیش‌فرض است و کاربر می‌تواند عوضش کند. چیزی که از داده معلوم نیست، حدس زده
نمی‌شود (خالی می‌ماند تا پرسیده شود).
"""

from dataclasses import dataclass

# آنچه در قدم «چی داری؟» انتخاب می‌شود
ASSET_CHOICES = ("gold", "coin", "fx", "bank", "market", "crypto", "car", "home", "cash")
_INTERESTS = {"gold": "gold", "coin": "gold", "fx": "fx", "market": "stocks",
              "crypto": "crypto", "home": "property"}
_EXPERIENCE = (("crypto", "advanced"), ("market", "market"), ("gold", "safe"), ("coin", "safe"),
               ("fx", "safe"))
_EMERGENCY = ((1, "none"), (3, "lt3"), (6, "3_6"))  # کمتر از n ماه


@dataclass(frozen=True)
class Snapshot:
    kinds: frozenset[str]  # از ASSET_CHOICES
    liquid_toman: int  # نقد، حساب بانکی، ارز و طلا: آنچه زود پول می‌شود
    monthly_fixed_toman: int  # جمع هزینه‌های ثابت ماهانه
    monthly_income_toman: int | None  # None یعنی نگفته
    pays_rent: bool
    owns_home: bool


def _interests(kinds: frozenset[str]) -> list[str]:
    found = [_INTERESTS[k] for k in ASSET_CHOICES if k in kinds and k in _INTERESTS]
    return list(dict.fromkeys(found))


def _emergency(snapshot: Snapshot) -> str | None:
    if snapshot.monthly_fixed_toman <= 0:
        return None
    months = snapshot.liquid_toman / snapshot.monthly_fixed_toman
    return next((label for limit, label in _EMERGENCY if months < limit), "gt6")


def infer_persona(snapshot: Snapshot) -> dict[str, object]:
    """جواب‌های پیش‌فرض مصاحبه پرسونا (کلیدها و گزینه‌های app.domain.persona)."""
    answers: dict[str, object] = {}
    interests = _interests(snapshot.kinds)
    if interests:
        answers["interests"] = interests
    experience = next((level for kind, level in _EXPERIENCE if kind in snapshot.kinds), None)
    if experience:
        answers["experience"] = experience
    if snapshot.owns_home:
        answers["housing"] = "owner"
    elif snapshot.pays_rent:
        answers["housing"] = "renter"
    emergency = _emergency(snapshot)
    if emergency:
        answers["emergency"] = emergency
    if snapshot.monthly_income_toman == 0:
        answers["income"] = "none"
    return answers


def monthly_left(snapshot: Snapshot) -> int | None:
    """باقی‌مانده ماهانه پس از هزینه‌های ثابت؛ None اگر درآمد را نگفته."""
    if snapshot.monthly_income_toman is None:
        return None
    return snapshot.monthly_income_toman - snapshot.monthly_fixed_toman
