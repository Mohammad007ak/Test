from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.models import PriceQuote, utcnow
from tests.integration.conftest import FakeSender, register


@pytest.fixture
def app(tmp_path: Path):  # type: ignore[no-untyped-def]
    settings = Settings(database_url=f"sqlite:///{tmp_path / 't.db'}", secret_key="t")
    app = create_app(settings, price_sources=[], schedule=False, otp_sender=FakeSender())
    now = utcnow()
    with app.state.session_factory() as s:
        s.add_all([
            PriceQuote(key="usd", price_toman=100_000, fetched_at=now - timedelta(hours=2),
                       first_seen_at=now - timedelta(hours=40), source="alanchand"),
            PriceQuote(key="usd", price_toman=105_000, fetched_at=now, source="alanchand"),
            PriceQuote(key="gold18_gram", price_toman=8_000_000, fetched_at=now,
                       source="alanchand"),
            PriceQuote(key="crypto:btc", price_toman=7_000_000_000, fetched_at=now,
                       source="alanchand"),
        ])
        s.commit()
    return app


@pytest.fixture
def client(app) -> Iterator[TestClient]:  # type: ignore[no-untyped-def]
    with TestClient(app) as c:
        register(c)
        yield c


def watch_section(html: str) -> str:
    start = html.index('id="watchlist"')
    return html[start:html.index("</section>", start)]


def test_default_watchlist_on_home_even_without_assets(client: TestClient) -> None:
    section = watch_section(client.get("/").text)
    assert "دلار آمریکا" in section and "طلای ۱۸" in section
    assert "۵٫۰٪" in section  # دلار نسبت به ۲۴ ساعت قبل


def test_user_picks_and_orders_items(client: TestClient) -> None:
    response = client.post("/watchlist", data={"keys": ["crypto:btc", "usd", "nonsense"]},
                           follow_redirects=False)
    assert response.status_code == 303
    section = watch_section(client.get("/").text)
    assert "بیت" in section and "طلای ۱۸" not in section
    assert section.index("بیت") < section.index("دلار آمریکا")
    assert "nonsense" not in section


def test_picker_lists_choices_with_current_ones_checked(client: TestClient) -> None:
    picker = client.get("/watchlist/edit").text
    assert 'value="usd" checked' in picker and 'value="crypto:btc"' in picker


def test_watchlist_is_per_user(app) -> None:  # type: ignore[no-untyped-def]
    with TestClient(app) as alice, TestClient(app) as bob:
        register(alice, "09121111111")
        register(bob, "09122222222")
        alice.post("/watchlist", data={"keys": ["crypto:btc"]})
        assert "طلای ۱۸" in watch_section(bob.get("/").text)
        assert "طلای ۱۸" not in watch_section(alice.get("/").text)
