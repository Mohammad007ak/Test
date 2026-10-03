"""ابزارهای وزیر: مدل زبانی حساب نمی‌کند؛ این توابع عدد دقیق را از کد تست‌شده اپ می‌دهند.

هر ابزار فقط با نشست محدود به کاربر جاری اجرا می‌شود و فقط عدد جمع‌بندی‌شده و برچسب
برمی‌گرداند: شماره حساب، کارت، موبایل یا متن پیامک هرگز در خروجی نیست.
خروجی‌ها JSON است و مبالغ int تومانی.
"""

import json
import re
from collections.abc import Callable
from decimal import Decimal
from typing import Any

import jdatetime
from sqlalchemy.orm import Session

from app import services
from app.domain.loan import LoanInput, analyze_loan
from app.domain.spending import TEHRAN
from app.web import categories
from app.web import strings as s

MAX_TRANSACTIONS = 10
_MONTH = re.compile(r"(\d{4})-(\d{1,2})")


class ToolError(ValueError):
    pass


def _month(text: str | None) -> tuple[int, int]:
    if not text:
        today = jdatetime.datetime.now(TEHRAN)
        return today.year, today.month
    match = _MONTH.fullmatch(str(text).strip())
    if not match or not 1 <= int(match.group(2)) <= 12:
        raise ToolError("ماه باید به شکل YYYY-MM شمسی باشد، مثل 1405-07")
    return int(match.group(1)), int(match.group(2))


def _rate(value: Decimal | None) -> float | None:
    return None if value is None else round(float(value), 4)


def _label(key: str) -> str:
    if key in s.PRICE_KEYS:
        return s.PRICE_KEYS[key]
    kind, _, symbol = key.partition(":")
    return f"{symbol} ({s.ASSET_KINDS.get(kind, kind)})" if symbol else key


# ---------- اجرای ابزارها ----------

def overview(db: Session) -> dict[str, Any]:
    p = services.build_portfolio(db)
    return {
        "networth_toman": p.networth.networth_toman,
        "assets_toman": p.assets_toman,
        "liabilities_toman": p.liabilities_toman,
        "monthly_income_toman": p.monthly_income_toman,
        "monthly_installments_toman": p.monthly_installments_toman,
        "monthly_fixed_expenses_toman": p.monthly_fixed_expenses_toman,
        "monthly_free_cash_toman": p.monthly_free_cash_toman,
        "debt_to_income": _rate(p.dti),
        "dti_threshold": _rate(services.get_decimal_setting(db, "dti_threshold")),
        "unpriced_assets": [line.asset.name for line in p.unvalued_assets],
    }


def spending(db: Session, month: str | None = None, direction: str = "out") -> dict[str, Any]:
    if direction not in ("out", "in"):
        raise ToolError("direction باید out (خرج) یا in (واریز) باشد")
    year, mon = _month(month)
    result = services.month_spending(db, year, mon, direction)
    labels = categories.labels(db)
    return {
        "month": f"{year}-{mon:02d}",
        "direction": direction,
        "total_toman": result.total_toman,
        "by_category": [{"category": labels.get(row.category, row.category),
                         "total_toman": row.total_toman} for row in result.by_category],
        "largest": [{"amount_toman": tx.amount_toman,
                     "category": labels.get(tx.category or "uncategorized", ""),
                     "description": (tx.description or "")[:60]}
                    for tx in sorted(result.transactions, key=lambda t: -t.amount_toman)
                    [:MAX_TRANSACTIONS]],
        "note": "انتقال بین حساب‌های خود کاربر در جمع حساب نشده است.",
    }


def compare_months(db: Session, month_a: str, month_b: str,
                   direction: str = "out") -> dict[str, Any]:
    a, b = spending(db, month_a, direction), spending(db, month_b, direction)
    for side in (a, b):
        side.pop("largest", None)
        side.pop("note", None)
    return {"a": a, "b": b, "difference_toman": b["total_toman"] - a["total_toman"]}


def assets(db: Session) -> dict[str, Any]:
    p = services.build_portfolio(db)
    return {
        "assets": [{"name": line.asset.name, "kind": s.ASSET_KINDS.get(line.asset.kind),
                    "value_toman": line.value_toman} for line in p.assets],
        "bank_accounts": [{"bank": s.BANKS.get(a.bank, a.bank), "label": a.label or "",
                           "balance_toman": a.balance_toman} for a in p.accounts],
        "composition_toman": dict(p.composition),
    }


def liabilities(db: Session) -> dict[str, Any]:
    p = services.build_portfolio(db)
    return {"liabilities": [{
        "lender": line.liability.lender,
        "kind": s.LIABILITY_KINDS.get(line.liability.kind),
        "remaining_toman": line.remaining_toman,
        "monthly_installment_toman": line.monthly_toman,
        "installments_left": line.remaining_count,
    } for line in p.liabilities]}


def prices(db: Session, keys: list[str] | None = None) -> dict[str, Any]:
    quotes = services.latest_quotes(db)
    wanted = keys or list(s.MAIN_PRICE_KEYS)
    found = {}
    for key in wanted[:20]:
        quote = quotes.get(key)
        if quote is not None:
            found[key] = {"label": _label(key), "toman": float(quote.per_unit),
                          "at": quote.fetched_at.isoformat()}
    return {"prices": found, "available_keys_examples": list(s.MAIN_PRICE_KEYS)}


def loan(db: Session, amount_toman: int, months: int, installment_toman: int | None = None,
         nominal_rate_percent: float | None = None, upfront_fee_toman: int = 0,
         blocked_deposit_toman: int = 0, blocked_months: int = 0) -> dict[str, Any]:
    if amount_toman <= 0 or not 1 <= months <= 600:
        raise ToolError("مبلغ و تعداد اقساط معتبر نیست")
    if installment_toman is None and nominal_rate_percent is None:
        raise ToolError("قسط یا نرخ اسمی لازم است")
    p = services.build_portfolio(db)
    result = analyze_loan(LoanInput(
        amount_toman=int(amount_toman), months=int(months),
        installment_toman=int(installment_toman) if installment_toman else None,
        nominal_rate=(Decimal(str(nominal_rate_percent)) / 100
                      if nominal_rate_percent is not None else None),
        upfront_fee_toman=int(upfront_fee_toman),
        blocked_deposit_toman=int(blocked_deposit_toman), blocked_months=int(blocked_months),
        inflation=services.get_decimal_setting(db, "inflation"),
        monthly_income_toman=p.monthly_income_toman,
        current_installments_toman=p.monthly_installments_toman,
        dti_threshold=services.get_decimal_setting(db, "dti_threshold"),
    ))
    return {
        "installment_toman": result.installment_toman,
        "effective_rate": _rate(result.effective_rate),
        "real_rate_after_inflation": _rate(result.real_rate),
        "total_cost_toman": result.total_cost_toman,
        "net_received_toman": result.net_received_toman,
        "dti_before": _rate(result.dti_before),
        "dti_after": _rate(result.dti_after),
        "dti_exceeds_threshold": result.dti_exceeds,
    }


_RUNNERS: dict[str, Callable[..., dict[str, Any]]] = {
    "overview": overview, "spending": spending, "compare_months": compare_months,
    "assets": assets, "liabilities": liabilities, "prices": prices, "analyze_loan": loan,
}


def run_tool(db: Session, name: str, arguments: str) -> str:
    """اجرای یک ابزار با آرگومان JSON مدل؛ خطا به‌صورت {"error": ...} برمی‌گردد تا مدل اصلاح کند."""
    from app.assistant import actions

    action_names = {t["function"]["name"] for t in actions.ACTION_TOOLS}
    if name not in _RUNNERS and name not in action_names:
        return json.dumps({"error": f"ابزار ناشناخته: {name}"}, ensure_ascii=False)
    try:
        args = json.loads(arguments or "{}")
        if not isinstance(args, dict):
            raise ToolError("آرگومان‌ها باید یک شیء JSON باشد")
        if name in action_names:
            result = actions.propose(db, name, args)
        else:
            result = _RUNNERS[name](db, **args)
    except (ToolError, ValueError, TypeError) as exc:
        return json.dumps({"error": str(exc)}, ensure_ascii=False)
    return json.dumps(result, ensure_ascii=False, default=str)


# ---------- تعریف ابزارها برای مدل (قالب function calling سازگار با OpenAI) ----------

def _tool(name: str, description: str, properties: dict[str, Any] | None = None,
          required: list[str] | None = None) -> dict[str, Any]:
    return {"type": "function", "function": {
        "name": name, "description": description,
        "parameters": {"type": "object", "properties": properties or {},
                       "required": required or [], "additionalProperties": False}}}


_MONTH_ARG = {"type": "string", "description": "ماه شمسی YYYY-MM مثل 1405-07؛ خالی = ماه جاری"}
_DIRECTION = {"type": "string", "enum": ["out", "in"],
              "description": "out = خرج و برداشت، in = واریز و درآمد واقعی"}

TOOLS: list[dict[str, Any]] = [
    _tool("overview", "خلاصه مالی کاربر: ثروت خالص، جمع دارایی و بدهی، درآمد و اقساط و "
                      "هزینه ثابت ماهانه، باقی‌مانده ماهانه و نسبت اقساط به درآمد."),
    _tool("spending", "خرج‌ها (یا واریزها) یک ماه شمسی به تفکیک دسته و بزرگ‌ترین تراکنش‌ها.",
          {"month": _MONTH_ARG, "direction": _DIRECTION}),
    _tool("compare_months", "مقایسه جمع و دسته‌های خرج (یا واریز) دو ماه شمسی.",
          {"month_a": _MONTH_ARG, "month_b": _MONTH_ARG, "direction": _DIRECTION},
          ["month_a", "month_b"]),
    _tool("assets", "فهرست دارایی‌ها با ارزش روز و موجودی حساب‌های بانکی و ترکیب دارایی."),
    _tool("liabilities", "بدهی‌ها و وام‌ها: مانده، قسط ماهانه و تعداد اقساط باقی‌مانده."),
    _tool("prices", "آخرین قیمت بازار به تومان (دلار usd، یورو eur، طلای ۱۸ gold18_gram، "
                    "سکه coin_emami، رمزارز crypto:btc، سهام stock:<نماد>، صندوق fund:<نماد>).",
          {"keys": {"type": "array", "items": {"type": "string"}}}),
    _tool("analyze_loan", "تحلیل یک وام فرضی: نرخ مؤثر و واقعی، هزینه کل و اثر بر نسبت اقساط "
                          "به درآمد همین کاربر. قسط یا نرخ اسمی لازم است.",
          {"amount_toman": {"type": "integer"}, "months": {"type": "integer"},
           "installment_toman": {"type": "integer"},
           "nominal_rate_percent": {"type": "number", "description": "مثلاً 23 یعنی ۲۳٪"},
           "upfront_fee_toman": {"type": "integer"},
           "blocked_deposit_toman": {"type": "integer"},
           "blocked_months": {"type": "integer"}},
          ["amount_toman", "months"]),
]


def _with_actions() -> None:
    from app.assistant.actions import ACTION_TOOLS

    TOOLS.extend(ACTION_TOOLS)


_with_actions()
