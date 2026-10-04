"""صفحه‌های عمومی قیمت برای جستجوی گوگل."""

from collections.abc import Iterator
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.models import PriceHistory, PriceQuote, utcnow
from app.web.price_pages import story
from app.web.render import tehran_today
from tests.integration.conftest import FakeSender


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    settings = Settings(database_url=f"sqlite:///{tmp_path / 't.db'}", secret_key="t",
                        public_url="https://getvazir.ir")
    with TestClient(create_app(settings, price_sources=[], schedule=False,
                               otp_sender=FakeSender())) as c:
        yield c


def _seed(client: TestClient) -> None:
    now = utcnow()
    today = tehran_today()
    with client.app.state.session_factory() as db:  # type: ignore[attr-defined]
        db.add(PriceQuote(key="usd", price_toman=100_000, fetched_at=now - timedelta(hours=30),
                          first_seen_at=now - timedelta(hours=30), source="alanchand"))
        db.add(PriceQuote(key="usd", price_toman=102_000, fetched_at=now,
                          first_seen_at=now - timedelta(hours=2), source="alanchand"))
        db.add_all(PriceHistory(key="usd", day=today - timedelta(days=i),
                                price_toman=80_000 + (300 - i) * 70, source="alanchand")
                   for i in range(1, 300))
        db.commit()


def test_price_page_is_public_indexable_and_has_real_numbers(client: TestClient) -> None:
    _seed(client)
    page = client.get("/price/dollar").text
    assert "<title>قیمت دلار امروز | وزیر</title>" in page
    assert "noindex" not in page
    assert '<link rel="canonical" href="https://getvazir.ir/price/dollar">' in page
    assert "۱۰۲٬۰۰۰ تومان" in page or "۱۰۲,۰۰۰ تومان" in page
    assert "بالا رفته" in page and 'class="pub-line"' in page  # بند توضیح و نمودار
    assert '<meta name="description" content="قیمت دلار امروز' in page
    assert 'href="/price/euro"' in page and 'href="/signup"' in page


def test_price_page_without_quote_still_renders(client: TestClient) -> None:
    response = client.get("/price/coin-emami")
    assert response.status_code == 200 and "در دسترس نیست" in response.text


def test_unknown_price_page_is_404(client: TestClient) -> None:
    assert client.get("/price/nothing").status_code == 404


def test_hub_lists_every_price_and_sitemap_includes_them(client: TestClient) -> None:
    _seed(client)
    hub = client.get("/price").text
    assert "قیمت طلا، سکه، دلار و ارز امروز" in hub
    assert 'href="/price/dollar"' in hub and 'href="/price/bitcoin"' in hub
    sitemap = client.get("/sitemap.xml").text
    assert "<loc>https://getvazir.ir/price</loc>" in sitemap
    assert "<loc>https://getvazir.ir/price/gold-18</loc>" in sitemap


def test_landing_ticker_links_to_price_pages(client: TestClient) -> None:
    _seed(client)
    assert 'href="/price/dollar" class="lx-tick"' in client.get("/").text


def test_story_states_facts_only() -> None:
    lines = story("دلار", "۱۴۰۵/۰۷/۱۳", Decimal(102_000), Decimal("0.02"),
                  {"changes": {"1y": Decimal("-0.1")}, "high_1y": Decimal(110_000),
                   "low_1y": Decimal(90_000)})
    assert lines[0].startswith("قیمت دلار امروز ۱۴۰۵/۰۷/۱۳")
    assert "۲٫۰٪ بالا رفته" in lines[1]
    assert "۱۰٪ پایین آمده" in lines[2]
    assert "کمترین" in lines[3]
    assert len(story("دلار", "x", Decimal(1), None, {"changes": {}})) == 1  # بدون داده، فقط قیمت


def test_learn_hub_and_article_pages(client: TestClient) -> None:
    hub = client.get("/learn").text
    assert "آموزش مالی شخصی به زبان ساده" in hub and 'href="/learn/coin-bubble"' in hub
    article = client.get("/learn/coin-bubble")
    assert article.status_code == 200 and "noindex" not in article.text
    assert "<h2>حباب را چطور حساب کنیم؟</h2>" in article.text
    assert '"@type": "Article"' in article.text and 'href="/price/coin-emami"' in article.text
    assert client.get("/learn/nothing").status_code == 404
    sitemap = client.get("/sitemap.xml").text
    assert "<loc>https://getvazir.ir/learn/net-worth</loc>" in sitemap


def test_article_internal_links_all_resolve(client: TestClient) -> None:
    import re

    from app.web.articles import all_articles

    for a in all_articles():
        for href in re.findall(r'href="(/[^"]*)"', str(a.html)):
            assert client.get(href).status_code == 200, (a.slug, href)
