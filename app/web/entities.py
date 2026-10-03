"""پیکربندی جدول‌های قابل ثبت دستی (F1 تا F3) برای CRUD عمومی."""

from typing import Any

from app.domain.normalize import normalize_chars, normalize_digits
from app.models import Account, Asset, IncomeStream, Liability
from app.web import forms
from app.web.forms import Entity

_UNITS = {"fx": None, "gold": "gram", "coin": "piece", "stock": "share", "fund": "unit",
          "crypto": "coin"}


def _clean(text: str | None) -> str | None:
    """فاصله‌های اضافه حذف؛ تا با کلید قیمت منبع (stock:<نماد>، fund:<نام>) یکی شود."""
    if not text:
        return None
    return " ".join(normalize_chars(text).split()) or None


def _asset_to_model(values: dict[str, Any]) -> dict[str, Any]:
    kind = values["kind"]
    currency = values.pop("currency")
    coin_type = values.pop("coin_type")
    symbol = _clean(values.pop("symbol"))
    fund_symbol = _clean(values.pop("fund_symbol"))
    crypto = values.pop("crypto_symbol")
    price_key = {
        "crypto": f"crypto:{crypto}" if crypto else None,
        "fx": currency,
        "coin": coin_type,
        "gold": "gold18_gram",
        "stock": f"stock:{symbol}" if symbol else None,
        "fund": f"fund:{fund_symbol}" if fund_symbol else None,
    }.get(kind)
    values["price_key"] = price_key
    values["unit"] = currency if kind == "fx" else _UNITS.get(kind)
    return values


def _asset_from_model(asset: Asset) -> dict[str, Any]:
    values = {f.name: getattr(asset, f.name, None) for f in forms.ASSET_FIELDS}
    key = asset.price_key or ""
    values["currency"] = key if asset.kind == "fx" else None
    values["coin_type"] = key if asset.kind == "coin" else None
    _, _, code = key.partition(":")
    values["symbol"] = code if asset.kind == "stock" else None
    values["fund_symbol"] = code if asset.kind == "fund" else None
    values["crypto_symbol"] = code if asset.kind == "crypto" else None
    return values


def _account_validate(values: dict[str, Any]) -> dict[str, str]:
    mask = normalize_digits(values.get("account_mask") or "")
    if not (len(mask) == 4 and mask.isascii() and mask.isdigit()):
        return {"account_mask": forms.s.T["mask_hint"]}
    return {}


def _account_to_model(values: dict[str, Any]) -> dict[str, Any]:
    values["account_mask"] = normalize_digits(values["account_mask"])
    return values


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
                       to_model=_account_to_model, validate=_account_validate),
    "liabilities": Entity("liabilities", "بدهی", forms.LIABILITY_FIELDS, Liability,
                          to_model=_liability_to_model, validate=_liability_validate),
    "incomes": Entity("incomes", "درآمد", forms.INCOME_FIELDS, IncomeStream),
}
