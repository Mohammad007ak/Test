"""داده ریلز «۱۰۰ میلیون، ۳ سال پیش»: قیمت هفتگی واقعی دلار، طلای ۱۸ و سکه امامی.

اجرا از ریشه مخزن: uv run python store/video/reel_data.py ← store/video/reel-100m.data.js
"""

import bisect
import json
from datetime import date, timedelta
from pathlib import Path

import jdatetime

from app.adapters.prices.history import AlanchandHistory

KEYS = ("usd", "gold18_gram", "coin_emami")
YEARS = 3


def main() -> None:
    source = AlanchandHistory()
    series = {}
    for key in KEYS:
        points = sorted(source.fetch_history(key), key=lambda p: p.day)
        series[key] = ([p.day for p in points], [p.price_toman for p in points])
    end = min(days[-1] for days, _ in series.values())
    start = date(end.year - YEARS, end.month, end.day)

    def row(day: date) -> dict[str, object]:
        jalali = jdatetime.date.fromgregorian(date=day).strftime("%Y/%m")
        out: dict[str, object] = {"day": day.isoformat(), "jalali": jalali}
        for key, (days, prices) in series.items():
            out[key] = prices[max(bisect.bisect_right(days, day) - 1, 0)]
        return out

    frames = [row(start + timedelta(days=7 * i)) for i in range((end - start).days // 7 + 1)]
    if frames[-1]["day"] != end.isoformat():
        frames.append(row(end))
    data = {"start": start.isoformat(), "end": end.isoformat(), "frames": frames}
    target = Path(__file__).with_name("reel-100m.data.js")
    target.write_text("// داده واقعی قیمت (منبع: الان‌چند) — ساخته‌شده با reel_data.py\n"
                      f"window.REEL = {json.dumps(data, ensure_ascii=False)};\n", encoding="utf-8")


if __name__ == "__main__":
    main()
