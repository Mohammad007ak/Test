import re
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from tests.integration.conftest import FakeSender, register


@pytest.fixture
def app(tmp_path: Path):  # type: ignore[no-untyped-def]
    settings = Settings(database_url=f"sqlite:///{tmp_path / 't.db'}", secret_key="t")
    return create_app(settings, price_sources=[], schedule=False, otp_sender=FakeSender())


@pytest.fixture
def client(app) -> Iterator[TestClient]:  # type: ignore[no-untyped-def]
    with TestClient(app) as c:
        register(c)
        yield c


def chips(client: TestClient, url: str) -> dict[str, str]:
    html = client.get(url).text
    chip = r'name="category" value="([^"]+)"[^>]*>\s*<span>(?:<svg.*?</svg>)?([^<]+)<'
    return dict(re.findall(chip, html, re.S))


def save(client: TestClient, direction: str, **form: str) -> int:
    return client.post(f"/settings/categories/{direction}", data=form,
                       follow_redirects=False).status_code


def test_rename_hide_and_add_spending_categories(client: TestClient) -> None:
    assert save(client, "out", **{"label:food": "غذا", "hidden:education": "on",
                                  "new": "حیوان خانگی"}) == 303
    options = chips(client, "/spending/new")
    assert options["food"] == "غذا"
    assert "education" not in options
    custom = next(key for key, label in options.items() if label == "حیوان خانگی")
    client.post("/spending", data={"amount_toman": "500,000", "category": custom,
                                   "description": "غذای گربه"})
    page = client.get("/spending").text
    assert "حیوان خانگی" in page and "غذای گربه" in page


def test_hidden_category_still_labels_old_transactions(client: TestClient) -> None:
    client.post("/spending", data={"amount_toman": "100", "category": "education"})
    save(client, "out", **{"hidden:education": "on"})
    assert "آموزش" in client.get("/spending").text


def test_transfer_and_other_cannot_be_hidden(client: TestClient) -> None:
    save(client, "out", **{"hidden:transfer": "on", "hidden:other": "on"})
    options = chips(client, "/spending/new")
    assert "transfer" in options and "other" in options


def test_deposit_categories_are_separate(client: TestClient) -> None:
    save(client, "in", **{"label:salary": "حقوق شرکت", "new": "فروش آنلاین"})
    deposit_options = chips(client, "/deposits/new")
    assert deposit_options["salary"] == "حقوق شرکت"
    assert "فروش آنلاین" in deposit_options.values()
    assert "فروش آنلاین" not in chips(client, "/spending/new").values()


def test_custom_categories_are_private(app) -> None:  # type: ignore[no-untyped-def]
    with TestClient(app) as alice, TestClient(app) as bob:
        register(alice, "09121111111")
        register(bob, "09122222222")
        save(alice, "out", new="دسته آلیس")
        assert "دسته آلیس" in chips(alice, "/spending/new").values()
        assert "دسته آلیس" not in chips(bob, "/spending/new").values()


def test_settings_page_links_and_lists(client: TestClient) -> None:
    assert 'href="/settings/categories"' in client.get("/settings").text
    page = client.get("/settings/categories").text
    assert "خوراک و رستوران" in page and "حقوق" in page
