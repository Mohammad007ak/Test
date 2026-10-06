"""داده استوری «قیمت امروز»: دلار، تتر، طلای ۱۸ و سکه امامی از الان‌چند.

دلار دیگر در فهرست ارزهای الان‌چند نیست؛ آخرین نرخش از آرشیو همان سایت خوانده می‌شود و تاریخش
جدا نشان داده می‌شود. اجرا از ریشه مخزن:
    PYTHONPATH=. uv run python store/social/story_prices.py  ← store/social/story-prices.data.js
    node store/social/render_story.js            ← store/social/story-prices.png
"""

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import jdatetime

from app.adapters.prices import alanchand
from app.adapters.prices.history import AlanchandHistory
from app.adapters.prices.http import http_get

TEHRAN = ZoneInfo("Asia/Tehran")


def jalali(day: datetime) -> str:
    return jdatetime.date.fromgregorian(date=day.date()).strftime("%Y/%m/%d")


def main() -> None:
    gold = {q.key: q.price_toman for q in alanchand.parse_gold(http_get(alanchand.GOLD_URL))}
    crypto = {q.key: q.price_toman for q in alanchand.parse_crypto(http_get(alanchand.CRYPTO_URL))}
    usd = max(AlanchandHistory().fetch_history("usd"), key=lambda p: p.day)
    now = datetime.now(TEHRAN)
    data = {
        "date": jalali(now), "time": now.strftime("%H:%M"),
        "usd": usd.price_toman, "usd_date": jdatetime.date.fromgregorian(date=usd.day).strftime("%Y/%m/%d"),
        "usdt": crypto["crypto:usdt"], "gold18_gram": gold["gold18_gram"], "coin_emami": gold["coin_emami"],
    }
    target = Path(__file__).with_name("story-prices.data.js")
    target.write_text("// ساخته‌شده با story_prices.py (منبع: الان‌چند)\nwindow.PRICES = "
                      + json.dumps(data, ensure_ascii=False) + ";\n", encoding="utf-8")
    print(target, data)


if __name__ == "__main__":
    main()
