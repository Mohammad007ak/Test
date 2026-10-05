"""ابزارهای وزیر: مدل زبانی حساب نمی‌کند؛ این توابع عدد دقیق را از کد تست‌شده اپ می‌دهند.

هر ابزار فقط با نشست محدود به کاربر جاری اجرا می‌شود و فقط عدد جمع‌بندی‌شده و برچسب
برمی‌گرداند: شماره حساب، کارت، موبایل یا متن پیامک هرگز در خروجی نیست.
خروجی‌ها JSON است و مبالغ int تومانی.
"""

import json
import re
from collections.abc import Callable
from datetime import timedelta
from decimal import Decimal
from typing import Any

import jdatetime
from sqlalchemy.orm import Session

from app import services
from app.domain import indicators
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


def _num(value: Decimal | None, places: int = 4) -> float | None:
    return None if value is None else round(float(value), places)


def _sample(data: list[tuple[Any, Decimal]], every: int, limit: int) -> list[list[Any]]:
    """هر every روز یک نقطه (از آخر به اول)، حداکثر limit نقطه؛ برای دیدن شکل نمودار."""
    picked = data[::-1][::every][:limit][::-1]
    return [[day.isoformat(), _num(value, 2)] for day, value in picked]


def market(db: Session, key: str) -> dict[str, Any]:
    """تحلیل تکنیکال و داده بنیادی یک قیمت از تاریخچه روزانه (آرشیو منبع + قیمت‌های اپ)."""
    from app import price_history

    quotes = services.latest_quotes(db)
    if key not in quotes and key not in s.PRICE_KEYS:
        raise ToolError(f"کلید قیمت ناشناخته: {key}؛ نمونه‌ها: {', '.join(s.MAIN_PRICE_KEYS)}")
    price_history.refresh(db, key, db.info.get("history_sources", []))
    data = price_history.series(db, key)
    if len(data) < 2:
        return {"key": key, "label": _label(key), "error": "هنوز تاریخچه کافی برای این قیمت نیست"}
    summary = indicators.summarize(data)
    quote = quotes.get(key)
    inflation = services.get_decimal_setting(db, "inflation")
    change_1y = summary["changes"]["1y"]
    out: dict[str, Any] = {
        "key": key, "label": _label(key), "unit": "toman",
        "data_from": summary["from"].isoformat(), "data_to": summary["to"].isoformat(),
        "data_note": "فقط قیمت پایانی روزانه (بدون سقف، کف و حجم)",
        "last": _num(summary["last"], 2),
        "change_24h": _num(price_history.change_24h(db, key, quote)),
        "changes": {k: _num(v) for k, v in summary["changes"].items()},
        "high_1y": _num(summary["high_1y"], 2), "low_1y": _num(summary["low_1y"], 2),
        "distance_from_high_1y": _num(summary["distance_from_high_1y"]),
        "technical": {k: (_jsonable(summary[k])) for k in (
            "trend", "sma20", "sma50", "sma200", "ema20", "above_sma50", "above_sma200",
            "golden_cross", "rsi14", "rsi_state", "macd", "bollinger20", "volatility_90d",
            "max_drawdown_1y")},
        "weekly_closes_1y": _sample([p for p in data if p[0] > data[-1][0] - timedelta(days=365)],
                                    7, 53),
        "monthly_closes_5y": _sample(data, 30, 61),
        "fundamental": {
            "assumed_inflation": _num(inflation),
            "real_change_1y": None if change_1y is None else
            _num((1 + change_1y) / (1 + inflation) - 1),
        },
    }
    usd = price_history.series(db, "usd") if key != "usd" else []
    if usd and change_1y is not None:
        usd_change = indicators.change_since(usd, indicators.PERIODS["1y"])
        if usd_change is not None:
            in_usd = (1 + change_1y) / (1 + usd_change) - 1
            out["fundamental"]["change_1y_in_usd_terms"] = _num(in_usd)
            out["fundamental"]["usd_change_1y"] = _num(usd_change)
    bubble = price_history.intrinsic(db, key)
    if bubble:
        day, price, real = bubble
        out["fundamental"]["coin_intrinsic_value"] = real
        out["fundamental"]["coin_bubble"] = _num(Decimal(price - real) / real)
        out["fundamental"]["coin_bubble_date"] = day.isoformat()
    usd_quote = quotes.get("usd")
    if key == "gold18_gram" and usd_quote and summary["last"]:
        # قیمت دلاری هر اونس طلای خالص از روی طلای ۱۸ عیار داخلی (۳۱٫۱۰۳۵ گرم، عیار ۷۵۰)
        ounce = summary["last"] / Decimal("0.75") * Decimal("31.1035") / usd_quote.per_unit
        out["fundamental"]["implied_ounce_usd"] = _num(ounce, 1)
    return out


def _jsonable(value: Any) -> Any:
    if isinstance(value, Decimal):
        return _num(value, 4)
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    return value


def dong_groups(db: Session) -> dict[str, Any]:
    """گروه‌های دنگ کاربر با اعضا، مانده خودش و کارت‌به‌کارت‌های لازم (تومان)."""
    from app.split_service import all_groups

    groups = []
    for v in all_groups(db):
        groups.append({
            "group": v.group.name,
            "members": [m.name + (" (خود کاربر)" if m.is_me else "") for m in v.members],
            "expenses": len(v.expenses), "total_toman": v.total,
            "my_balance_toman": v.my_balance,
            "transfers": [{"from": v.names[t.debtor], "to": v.names[t.creditor],
                           "amount_toman": t.amount} for t in v.transfers],
        })
    return {"groups": groups, "note": "my_balance مثبت یعنی بقیه به کاربر بدهکارند."}


_RUNNERS: dict[str, Callable[..., dict[str, Any]]] = {
    "overview": overview, "spending": spending, "compare_months": compare_months,
    "assets": assets, "liabilities": liabilities, "prices": prices, "analyze_loan": loan,
    "market_analysis": market, "dong_groups": dong_groups,
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
    _tool("dong_groups", "گروه‌های دنگ (تقسیم خرج گروهی) کاربر: اعضا، مانده او و این‌که چه کسی "
                         "به چه کسی چقدر بدهکار است. پیش از add_split_expense صدا بزن."),
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
    _tool("market_analysis", "تحلیل تکنیکال و بنیادی یک قیمت از تاریخچه روزانه تا پنج سال: "
                             "تغییر ۲۴ساعته، هفتگی، ماهانه، ۳ماهه، سالانه و ۵ساله، سقف و کف "
                             "سالانه، SMA/EMA، RSI، MACD، بولینگر، نوسان، بیشترین افت، "
                             "قیمت‌های پایانی هفتگی و ماهانه، بازده واقعی پس از تورم، تغییر به "
                             "دلار، حباب سکه و قیمت اونس ضمنی طلا.",
          {"key": {"type": "string", "description": "usd، eur، gold18_gram، coin_emami، "
                                                    "crypto:btc، stock:<نماد>، fund:<نماد>"}},
          ["key"]),
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
