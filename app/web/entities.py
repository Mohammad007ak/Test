"""پیکربندی جدول‌های قابل ثبت دستی (F1 تا F3) برای CRUD عمومی."""

from typing import Any

from app.models import Account, Asset, IncomeStream, Liability
from app.web import forms
from app.web.forms import Entity

_UNITS = {"fx": None, "gold": "gram", "coin": "piece", "stock": "share", "fund": "unit"}


def _asset_to_model(values: dict[str, Any]) -> dict[str, Any]:
    kind = values["kind"]
    market = values.pop("market")
    symbol = values.pop("symbol")
    price_key = {
        "fx": market,
        "coin": market,
        "gold": "gold18_gram",
        "stock": f"stock:{symbol}" if symbol else None,
        "fund": f"fund:{symbol}" if symbol else None,
    }.get(kind)
    values["price_key"] = price_key
    values["unit"] = market if kind == "fx" else _UNITS.get(kind)
    return values


def _asset_from_model(asset: Asset) -> dict[str, Any]:
    values = {f.name: getattr(asset, f.name, None) for f in forms.ASSET_FIELDS}
    key = asset.price_key or ""
    values["market"] = key if asset.kind in ("fx", "coin") else None
    values["symbol"] = key.split(":", 1)[1] if ":" in key else None
    return values


def _account_validate(values: dict[str, Any]) -> dict[str, str]:
    mask = values.get("account_mask") or ""
    if not (len(mask) == 4 and mask.isdigit()):
        return {"account_mask": forms.s.T["mask_hint"]}
    return {}


def _liability_to_model(values: dict[str, Any]) -> dict[str, Any]:
    for name in ("installment_toman", "installments_total", "installments_paid"):
        values[name] = values[name] or 0
    return values


def _liability_validate(values: dict[str, Any]) -> dict[str, str]:
    total = values.get("installments_total") or 0
    paid = values.get("installments_paid") or 0
    if paid > total:
        return {"installments_paid": "از تعداد کل اقساط بیشتر است."}
    if total and not values.get("installment_toman"):
        return {"installment_toman": forms.s.T["required"]}
    return {}


ENTITIES: dict[str, Entity] = {
    "assets": Entity("assets", "دارایی", forms.ASSET_FIELDS, Asset,
                     to_model=_asset_to_model, from_model=_asset_from_model),
    "accounts": Entity("accounts", "حساب بانکی", forms.ACCOUNT_FIELDS, Account,
                       validate=_account_validate),
    "liabilities": Entity("liabilities", "بدهی", forms.LIABILITY_FIELDS, Liability,
                          to_model=_liability_to_model, validate=_liability_validate),
    "incomes": Entity("incomes", "درآمد", forms.INCOME_FIELDS, IncomeStream),
}
