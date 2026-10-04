"""تاریخچه قیمت، نمودار بازه‌ها، تغییر روزانه و ابزار تحلیل بازار وزیر."""

import html
import json
from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.adapters.prices.base import PriceSourceError
from app.adapters.prices.history import HistoryPoint
from app.assistant.tools import run_tool
from app.config import Settings
from app.db import user_session
from app.domain.spending import TEHRAN
from app.main import create_app
from app.models import PriceHistory, PriceQuote
from tests.integration.conftest import FakeSender, register

TODAY = datetime.now(TEHRAN).date()


class FakeHistory:
    name = "alanchand"

    def __init__(self) -> None:
        self.calls: list[str] = []
        self.data: dict[str, list[HistoryPoint]] = {}

    def supports(self, key: str) -> bool:
        return key in ("usd", "coin_emami", "eur")

    def fetch_history(self, key: str) -> list[HistoryPoint]:
        self.calls.append(key)
        if key not in self.data:
            raise PriceSourceError("نیست")
        return self.data[key]


def daily(days: int, start: int, step: int, real: bool = False) -> list[HistoryPoint]:
    first = TODAY - timedelta(days=days)
    return [HistoryPoint(first + timedelta(days=i), start + i * step,
                         (start + i * step) * 9 // 10 if real else None)
            for i in range(days)]  # تا دیروز


@pytest.fixture
def history() -> FakeHistory:
    h = FakeHistory()
    h.data["usd"] = daily(800, 100_000, 200)  # دیروز: ۲۵۹٬۸۰۰
    h.data["coin_emami"] = daily(400, 100_000_000, 100_000, real=True)
    return h


@pytest.fixture
def client(tmp_path: Path, history: FakeHistory) -> Iterator[TestClient]:
    settings = Settings(database_url=f"sqlite:///{tmp_path / 't.db'}", secret_key="t")
    app = create_app(settings, price_sources=[], schedule=False, otp_sender=FakeSender(),
                     history_sources=[history], chat_model=None)
    with TestClient(app) as c:
        register(c)
        with c.app.state.session_factory() as s:  # type: ignore[attr-defined]
            now = datetime.now(UTC)
            for key, price, units in (("usd", 265_000, 1), ("coin_emami", 140_000_000, 1),
                                      ("crypto:btc", 9_000_000_000, 1)):
                s.add(PriceQuote(key=key, price_toman=price, units=units, fetched_at=now,
                                 first_seen_at=now, source="alanchand"))
            s.commit()
        yield c


def db(client: TestClient):  # type: ignore[no-untyped-def]
    session = user_session(client.app.state.session_factory(), 1)  # type: ignore[attr-defined]
    session.info["history_sources"] = client.app.state.history_sources  # type: ignore[attr-defined]
    return session


def test_chart_sheet_has_five_ranges_and_indicators(client: TestClient,
                                                    history: FakeHistory) -> None:
    page = client.get("/prices/chart?key=usd", headers={"HX-Request": "true"}).text
    for label in ("۱ هفته", "۱ ماه", "۳ ماه", "۱ سال", "۵ سال"):
        assert label in page
    data = json.loads(html.unescape(page.split("data-price-chart='")[1].split("'")[0]))
    assert len(data["d"]) == 801 and data["v"][-1] == 265_000  # آرشیو + قیمت امروز اپ
    assert data["d"][-1] == TODAY.isoformat()
    assert "RSI" in page and "صعودی" in page and "بالاترین یک سال" in page
    client.get("/prices/chart?key=usd")
    assert history.calls == ["usd"]  # تا ۱۲ ساعت دوباره گرفته نمی‌شود


def test_coin_chart_shows_bubble(client: TestClient) -> None:
    page = client.get("/prices/chart?key=coin_emami").text
    assert "حباب سکه" in page and "ارزش ذاتی" in page


def test_crypto_without_archive_uses_own_prices(client: TestClient,
                                                history: FakeHistory) -> None:
    page = client.get("/prices/chart?key=crypto:btc").text
    assert "هنوز تاریخچه‌ای" in page and "crypto:btc" not in history.calls


def test_unknown_key_404_and_failed_fetch_is_not_retried_at_once(
        client: TestClient, history: FakeHistory) -> None:
    assert client.get("/prices/chart?key=nope").status_code == 404
    client.get("/prices/chart?key=eur")
    client.get("/prices/chart?key=eur")
    assert history.calls.count("eur") == 1


def test_archive_in_hundreds_is_rescaled(client: TestClient,
                                                               history: FakeHistory) -> None:
    history.data["usd"] = daily(10, 26_000_000, 0)  # قیمت صد دلار
    client.get("/prices/chart?key=usd")
    with db(client) as s:
        assert s.get(PriceHistory, ("usd", TODAY - timedelta(days=1))).price_toman == 260_000


def test_prices_page_shows_daily_change_and_chart_links(client: TestClient) -> None:
    client.get("/prices/chart?key=usd")  # آرشیو پر شود
    page = client.get("/prices").text
    assert "/prices/chart?key=usd" in page
    assert "chg up" in page and "۲٫۰٪" in page  # ۲۶۵٬۰۰۰ نسبت به ۲۵۹٬۸۰۰ دیروز
    assert "/prices/chart?key=usd" in client.get("/").text  # کارت‌های قیمت صفحه اصلی


def test_market_analysis_tool(client: TestClient) -> None:
    with db(client) as s:
        result = json.loads(run_tool(s, "market_analysis", '{"key": "usd"}'))
        coin = json.loads(run_tool(s, "market_analysis", '{"key": "coin_emami"}'))
        bad = json.loads(run_tool(s, "market_analysis", '{"key": "zzz"}'))
    assert result["last"] == 265_000 and result["changes"]["1y"] > 0
    assert result["changes"]["5y"] is None and result["technical"]["trend"] == "up"
    assert result["technical"]["rsi14"] is not None and result["technical"]["macd"]
    assert len(result["weekly_closes_1y"]) == 53 and result["monthly_closes_5y"]
    assert result["fundamental"]["real_change_1y"] < result["changes"]["1y"]
    assert coin["fundamental"]["coin_bubble"] > 0
    assert "change_1y_in_usd_terms" in coin["fundamental"]
    assert "error" in bad


def test_assistant_prefill_from_chart(tmp_path: Path) -> None:
    class Model:
        def complete(self, messages: list, tools: list) -> dict:
            return {"role": "assistant", "content": "x"}

    settings = Settings(database_url=f"sqlite:///{tmp_path / 'a.db'}", secret_key="t")
    app = create_app(settings, price_sources=[], schedule=False, otp_sender=FakeSender(),
                     chat_model=Model())
    with TestClient(app) as c:
        register(c)
        c.post("/assistant/consent")
        assert "تحلیل دلار" in c.get("/assistant?q=تحلیل دلار").text


def test_history_first_day_is_kept(history: FakeHistory) -> None:
    assert history.data["usd"][0].day == TODAY - timedelta(days=800)
    assert isinstance(history.data["usd"][0].day, date)
