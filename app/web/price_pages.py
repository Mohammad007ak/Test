"""صفحه‌های عمومی قیمت («قیمت دلار امروز»، «قیمت طلا امروز»…) برای جستجوی گوگل.

بدون ورود، قابل ایندکس، با نمودار SVG سمت سرور (بدون جاوااسکریپت) و یک بند توضیح
که از همان عددهای روز ساخته می‌شود تا هر صفحه متن یکتای خودش را داشته باشد.
"""

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, Response

from app import price_history, services
from app.domain import indicators
from app.domain.money import format_percent
from app.models import PriceQuote
from app.web import strings as s
from app.web.common import Db, page
from app.web.render import jalali, price_short, sparkline, tehran_today

CHART_DAYS = 365
CHART_POINTS = 120


@dataclass(frozen=True)
class PricePage:
    slug: str
    key: str
    name: str  # همان عبارتی که مردم جستجو می‌کنند: «قیمت {name} امروز»
    group: str


PAGES: tuple[PricePage, ...] = tuple(PricePage(*row) for row in (
    ("dollar", "usd", "دلار", "fx"),
    ("euro", "eur", "یورو", "fx"),
    ("pound", "gbp", "پوند انگلیس", "fx"),
    ("dirham", "aed", "درهم امارات", "fx"),
    ("lira", "try", "لیر ترکیه", "fx"),
    ("gold-18", "gold18_gram", "طلای ۱۸ عیار", "gold"),
    ("gold-mesghal", "gold_mesghal", "مثقال طلا", "gold"),
    ("coin-emami", "coin_emami", "سکه امامی", "gold"),
    ("coin-bahar", "coin_bahar", "سکه بهار آزادی", "gold"),
    ("coin-half", "coin_half", "نیم سکه", "gold"),
    ("coin-quarter", "coin_quarter", "ربع سکه", "gold"),
    ("coin-gram", "coin_gram", "سکه گرمی", "gold"),
    ("bitcoin", "crypto:btc", "بیت کوین", "crypto"),
    ("tether", "crypto:usdt", "تتر", "crypto"),
    ("ethereum", "crypto:eth", "اتریوم", "crypto"),
))
BY_SLUG = {p.slug: p for p in PAGES}
PATHS = ("/price", *(f"/price/{p.slug}" for p in PAGES))


def _direction(change: Decimal) -> str:
    return s.PRICE_PAGE["up"] if change > 0 else s.PRICE_PAGE["down"]


def story(name: str, today: str, last: Decimal, change_1d: Decimal | None,
          summary: dict[str, Any]) -> list[str]:
    """چند جمله ساده از عددهای روز؛ فقط واقعیت، بدون پیش‌بینی یا توصیه خرید."""
    t = s.PRICE_PAGE
    lines = [t["story_now"].format(name=name, day=today, price=price_short(last))]
    if change_1d:
        lines.append(t["story_day"].format(
            direction=_direction(change_1d), pct=format_percent(abs(change_1d), 1)))
    year = summary.get("changes", {}).get("1y")
    if year:
        lines.append(t["story_year"].format(
            name=name, direction=_direction(year), pct=format_percent(abs(year), 0)))
    if summary.get("high_1y") and summary.get("low_1y"):
        lines.append(t["story_range"].format(low=price_short(summary["low_1y"]),
                                             high=price_short(summary["high_1y"])))
    return lines


def _row(db: Db, p: PricePage, quotes: dict[str, PriceQuote]) -> dict[str, Any]:
    quote = quotes.get(p.key)
    return {"page": p, "quote": quote, "change": price_history.change_24h(db, p.key, quote)}


def register_price_pages(app: FastAPI) -> None:
    @app.get("/price", response_class=HTMLResponse)
    def price_hub(request: Request, db: Db) -> Response:
        quotes = services.latest_quotes(db)
        groups = [(title, [_row(db, p, quotes) for p in PAGES if p.group == group])
                  for group, title in s.PRICE_PAGE_GROUPS.items()]
        return page(request, "price_hub.html", {
            "active": "price", "indexable": True, "groups": groups, "today": tehran_today(),
            "meta_description": s.PRICE_PAGE["hub_description"],
            "og_title": s.PRICE_PAGE["hub_title"]})

    @app.get("/price/{slug}", response_class=HTMLResponse)
    def price_page(request: Request, slug: str, db: Db) -> Response:
        p = BY_SLUG.get(slug)
        if p is None:
            raise HTTPException(404)
        price_history.refresh(db, p.key, request.app.state.history_sources)
        quotes = services.latest_quotes(db)
        quote = quotes.get(p.key)
        data = price_history.series(db, p.key)
        summary = indicators.summarize(data)
        year = [(d, v) for d, v in data if d >= tehran_today() - timedelta(days=CHART_DAYS)]
        step = max(len(year) // CHART_POINTS, 1)
        line, area = sparkline([int(v) for _d, v in year[::step]], width=600, height=200)
        change = price_history.change_24h(db, p.key, quote)
        today = jalali(tehran_today())
        title = s.PRICE_PAGE["title"].format(name=p.name)
        lines = story(p.name, today, quote.per_unit, change, summary) if quote else []
        return page(request, "price_public.html", {
            "active": "price", "indexable": True, "p": p, "quote": quote, "change": change,
            "summary": summary, "line": line, "area": area, "story": lines,
            "bubble": price_history.intrinsic(db, p.key) if p.key in s.COIN_KEYS else None,
            "related": [r for r in PAGES if r.group == p.group and r.slug != p.slug],
            "others": [r for r in PAGES if r.group != p.group][:6],
            "page_title": title, "og_title": title,
            "meta_description": " ".join(lines[:2]) or s.PRICE_PAGE["hub_description"]})
