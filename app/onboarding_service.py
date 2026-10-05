"""راه‌اندازی اولیه بعد از ثبت‌نام: وضعیت قدم‌ها، ثبت دارایی و دخل و خرج، و تصویر کاربر.

هر چه این‌جا ثبت می‌شود همان ردیف‌های معمولی دارایی، حساب، درآمد و هزینه ثابت است؛ بعداً از
صفحه خودشان قابل ویرایش‌اند. حدس پیش‌فرض پرسونا در app.domain.onboarding است.
"""

import json
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from app import services
from app.domain.onboarding import ASSET_CHOICES, Snapshot
from app.models import Account, Asset, ExpenseStream, IncomeStream, utcnow
from app.web import forms
from app.web import strings as s
from app.web.forms import Field

STATE_KEY = "onboarding"
STEPS = ("have", "amounts", "monthly", "sms", "card")
GOLD_KARAT = 18
COINS = ("coin_emami", "coin_half", "coin_quarter", "coin_gram")
CURRENCIES = ("usd", "eur", "aed", "gbp", "try")
CRYPTOS = ("btc", "usdt", "eth")
# هزینه ثابت ← دسته (EXPENSE_CATEGORIES)
FIXED: dict[str, str] = {"rent": "housing", "installment": "installment", "bills": "bills",
                         "tuition": "education", "transport": "transport", "other": "other"}
# نوع دارایی در جدول ← انتخاب «چی داری؟»
_KIND_CHOICE = {"gold": "gold", "coin": "coin", "fx": "fx", "stock": "market", "fund": "market",
                "crypto": "crypto", "car": "car", "real_estate": "home", "cash": "cash"}
LIQUID_KINDS = ("cash", "fx", "gold", "coin")


@dataclass
class State:
    kinds: list[str] = field(default_factory=list)
    no_income: bool = False
    done: bool = False


def load_state(db: Session) -> State:
    raw = services.get_user_setting(db, STATE_KEY)
    data = json.loads(raw) if raw else {}
    kinds = [k for k in data.get("kinds", []) if k in ASSET_CHOICES]
    return State(kinds, bool(data.get("no_income")), bool(data.get("done")))


def save_state(db: Session, state: State) -> None:
    services.set_user_setting(db, STATE_KEY, json.dumps(state.__dict__))


def amount_fields(kinds: list[str]) -> dict[str, list[Field]]:
    """فیلدهای قدم «چقدر؟» برای هر انتخاب؛ همه اختیاری‌اند."""
    t = s.ONBOARDING
    specs: dict[str, list[Field]] = {
        "gold": [Field("gold_grams", t["gold_grams"], "decimal", hint=t["gold_hint"])],
        "coin": [Field(f"coin_{key}", s.PRICE_KEYS[key], "int", min=0, max=100_000)
                 for key in COINS],
        "fx": [Field("fx_currency", t["fx_currency"], "select",
                     options={c: s.CURRENCY_NAMES[c] for c in CURRENCIES}),
               Field("fx_amount", t["fx_amount"], "decimal")],
        "bank": [Field("bank_name", t["bank_name"], "select", options=s.BANKS),
                 Field("bank_balance", t["bank_balance"], "money")],
        "market": [Field("market_value", t["market_value"], "money", hint=t["market_hint"])],
        "crypto": [Field("crypto_code", t["crypto_code"], "select",
                         options={c: s.CRYPTO_NAMES[c] for c in CRYPTOS}),
                   Field("crypto_amount", t["crypto_amount"], "decimal")],
        "car": [Field("car_value", t["car_value"], "money")],
        "home": [Field("home_value", t["home_value"], "money")],
        "cash": [Field("cash_value", t["cash_value"], "money", hint=t["cash_hint"])],
    }
    return {kind: specs[kind] for kind in ASSET_CHOICES if kind in kinds}


def _manual(kind: str, name: str, value: int) -> Asset:
    return Asset(kind=kind, name=name, manual_value_toman=value,
                 manual_value_updated_at=utcnow())


def _records(kind: str, v: dict[str, Any]) -> list[Asset | Account]:
    t = s.ONBOARDING
    if kind == "gold" and v["gold_grams"]:
        return [Asset(kind="gold", name=t["gold_name"], quantity=v["gold_grams"], unit="gram",
                      karat=GOLD_KARAT, price_key="gold18_gram")]
    if kind == "coin":
        return [Asset(kind="coin", name=s.PRICE_KEYS[key], quantity=v[f"coin_{key}"],
                      unit="piece", price_key=key) for key in COINS if v[f"coin_{key}"]]
    if kind == "fx" and v["fx_amount"] and v["fx_currency"]:
        return [Asset(kind="fx", name=s.CURRENCY_NAMES[v["fx_currency"]],
                      quantity=v["fx_amount"], unit=v["fx_currency"],
                      price_key=v["fx_currency"])]
    if kind == "bank" and v["bank_balance"] is not None and v["bank_name"]:
        return [Account(bank=v["bank_name"], account_mask="", account_prefix="",
                        balance_toman=v["bank_balance"], balance_source="manual")]
    if kind == "crypto" and v["crypto_amount"] and v["crypto_code"]:
        return [Asset(kind="crypto", name=s.CRYPTO_NAMES[v["crypto_code"]],
                      quantity=v["crypto_amount"], unit="coin",
                      price_key=f"crypto:{v['crypto_code']}")]
    manual = {"market": ("other", "market_value"), "car": ("car", "car_value"),
              "home": ("real_estate", "home_value"), "cash": ("cash", "cash_value")}
    if kind in manual:
        model_kind, name = manual[kind]
        if v[name]:
            return [_manual(model_kind, t[f"{kind}_name"], v[name])]
    return []


def save_amounts(db: Session, kinds: list[str], data: dict[str, str]) -> int:
    """همه فیلدها اول اعتبارسنجی، بعد ثبت؛ خطا FormError و هیچ چیز ثبت نمی‌شود."""
    fields = amount_fields(kinds)
    values = forms.parse_form([f for group in fields.values() for f in group], data)
    records = [r for kind in fields for r in _records(kind, values)]
    db.add_all(records)
    return len(records)


def monthly_fields() -> list[Field]:
    t = s.ONBOARDING
    return [Field("income", t["income"], "money", hint=t["income_hint"]),
            *[Field(f"fixed_{key}", t[f"fixed_{key}"], "money") for key in FIXED]]


def save_monthly(db: Session, data: dict[str, str]) -> bool:
    """درآمد و هزینه‌های ثابت ماهانه؛ برمی‌گرداند که کاربر گفته درآمد ندارد یا نه."""
    values = forms.parse_form(monthly_fields(), data)
    no_income = data.get("no_income") == "1"
    t = s.ONBOARDING
    if values["income"] and not no_income:
        db.add(IncomeStream(name=t["income_name"], amount_toman=values["income"],
                            frequency="monthly", active=True))
    for key, category in FIXED.items():
        if values[f"fixed_{key}"]:
            db.add(ExpenseStream(name=t[f"fixed_{key}"], amount_toman=values[f"fixed_{key}"],
                                 frequency="monthly", category=category, active=True))
    return no_income


def snapshot(db: Session, state: State) -> Snapshot:
    """تصویر مالی کاربر از روی همان ردیف‌های ثبت‌شده، برای حدس پرسونا و خلاصه راه‌اندازی."""
    p = services.build_portfolio(db)
    kinds = {_KIND_CHOICE[line.asset.kind] for line in p.assets
             if line.asset.kind in _KIND_CHOICE}
    kinds |= {"market"} if any(line.asset.kind == "other" and line.asset.name ==
                               s.ONBOARDING["market_name"] for line in p.assets) else set()
    if p.accounts:
        kinds.add("bank")
    liquid = sum(line.value_toman or 0 for line in p.assets if line.asset.kind in LIQUID_KINDS)
    liquid += sum(a.balance_toman for a in p.accounts)
    income = 0 if state.no_income else (p.monthly_income_toman if p.incomes else None)
    return Snapshot(
        kinds=frozenset(kinds | set(state.kinds)),
        liquid_toman=liquid,
        monthly_fixed_toman=p.monthly_fixed_expenses_toman + p.monthly_installments_toman,
        monthly_income_toman=income,
        pays_rent=any(e.category == "housing" for e, _m in p.expenses),
        owns_home=any(line.asset.kind == "real_estate" for line in p.assets))
