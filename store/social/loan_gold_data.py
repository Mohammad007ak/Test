"""داده پست «وام اقساطی + طلا»: مهر ۱۴۰۴ وام بگیر، طلا بخر، هر ماه برای قسط طلا بفروش.

فرض‌ها (از کاربر): ۱۳٪ حق اشتراک اول کار از وام کم می‌شود؛ اصل وام با سود ۲۳٪ سالانه در ۱۲ قسط
مساوی؛ ۳٪ کارمزد خرید طلا. قیمت طلای ۱۸ عیار واقعی (الان‌چند). اجرا از ریشه مخزن:
    PYTHONPATH=. uv run python store/social/loan_gold_data.py ← store/social/loan-gold.data.js
"""

import bisect
import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import jdatetime

from app.adapters.prices.history import AlanchandHistory

LOAN = 100_000_000
FEE = Decimal("0.13")
RATE = Decimal("0.23")
MONTHS = 12
BUY_FEE = Decimal("0.03")
START = jdatetime.date(1404, 7, 15)


def installment(principal: int, annual: Decimal, months: int) -> Decimal:
    r = annual / 12
    return principal * r / (1 - (1 + r) ** -months)


def main() -> None:
    points = sorted(AlanchandHistory().fetch_history("gold18_gram"), key=lambda p: p.day)
    days = [p.day for p in points]

    def price(day: date) -> int:
        return points[max(bisect.bisect_right(days, day) - 1, 0)].price_toman

    start = START.togregorian()
    pay = installment(LOAN, RATE, MONTHS)
    cash = LOAN * (1 - FEE)
    grams = cash * (1 - BUY_FEE) / price(start)
    rows = []
    for k in range(1, MONTHS + 1):
        y, m = divmod(START.month - 1 + k, 12)
        jd = jdatetime.date(START.year + y, m + 1, START.day)
        p = price(jd.togregorian())
        sold = pay / p
        grams -= sold
        rows.append({"j": jd.strftime("%Y/%m/%d"), "price": p, "sold": float(round(sold, 3)),
                     "left": float(round(grams, 3))})
    end_price = price(days[-1])
    left_value = int(grams * end_price)
    total_paid = int(pay * MONTHS)
    # بدون طلا: پول نقد نگه می‌داشت و قسط‌ها را از همان می‌داد
    cash_left = int(cash - pay * MONTHS)
    # قیمت لازم برای سر‌به‌سر (فرض رشد یکنواخت نیست؛ فقط یک عدد ساده: اگر طلا ثابت می‌ماند)
    flat_left = int((cash * (1 - BUY_FEE) / price(start) - pay * MONTHS / price(start)) * price(start))
    data = {
        "loan": LOAN, "fee": int(LOAN * FEE), "cash": int(cash), "installment": int(pay), "months": MONTHS,
        "total_paid": total_paid, "start": START.strftime("%Y/%m/%d"), "start_price": price(start),
        "grams0": float(round(cash * (1 - BUY_FEE) / price(start), 3)), "end_price": end_price,
        "end_day": jdatetime.date.fromgregorian(date=days[-1]).strftime("%Y/%m/%d"),
        "left_grams": float(round(grams, 3)), "left_value": left_value, "cash_left": cash_left,
        "flat_left": flat_left, "rows": rows,
        "series": [{"d": jdatetime.date.fromgregorian(date=p.day).strftime("%Y/%m/%d"), "p": p.price_toman}
                   for p in points if p.day >= start],
    }
    Path(__file__).with_name("loan-gold.data.js").write_text(
        "// ساخته‌شده با loan_gold_data.py (قیمت طلا: الان‌چند)\nwindow.LG = "
        + json.dumps(data, ensure_ascii=False) + ";\n", encoding="utf-8")
    print({k: v for k, v in data.items() if k not in ("rows", "series")})
    for r in rows:
        print(r)


if __name__ == "__main__":
    main()
