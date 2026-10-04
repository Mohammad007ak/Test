"""مصاحبه پرسونا، کارت شخصیت، آواتار و اثرش روی وزیر و قیمت‌های صفحه اصلی."""

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from tests.integration.conftest import FakeSender, register

ANSWERS = {"age": "25_34", "job": "freelancer", "income": "variable", "household": "single",
           "housing": "renter", "goal": "home", "horizon": "3_7", "drop": "wait",
           "choice": "coin", "experience": "market", "style": "balanced", "emergency": "lt3",
           "tone": "blunt"}


class Model:
    def __init__(self) -> None:
        self.system: list[str] = []

    def complete(self, messages: list[dict], tools: list[dict]) -> dict:
        self.system.append(messages[0]["content"])
        return {"role": "assistant", "content": "باشه."}


@pytest.fixture
def model() -> Model:
    return Model()


@pytest.fixture
def client(tmp_path: Path, model: Model) -> Iterator[TestClient]:
    settings = Settings(database_url=f"sqlite:///{tmp_path / 't.db'}", secret_key="t")
    app = create_app(settings, price_sources=[], schedule=False, otp_sender=FakeSender(),
                     chat_model=model)
    with TestClient(app) as c:
        register(c)
        yield c


def answer(client: TestClient, interests: tuple[str, ...] = ("gold", "fx"),
           note: str = "", **override: str):  # type: ignore[no-untyped-def]
    data: dict[str, object] = {**ANSWERS, **override, "interests": list(interests), "note": note}
    return client.post("/persona", data=data, follow_redirects=False)


def test_without_persona_home_invites_and_persona_page_is_interview(client: TestClient) -> None:
    assert 'class="persona-cta"' in client.get("/").text
    page = client.get("/persona").text
    assert 'id="interview"' in page and 'name="drop"' in page and 'name="interests"' in page


def test_saving_shows_card_and_sets_avatar(client: TestClient) -> None:
    response = answer(client)
    assert response.status_code == 303 and response.headers["location"] == "/persona?new=1"
    page = client.get("/persona?new=1").text
    assert "معمار" in page and "ری دالیو" in page  # متعادل، افق ۳ تا ۷، سبک متعادل
    assert "pcard reveal" in page and "متعادل" in page
    home = client.get("/").text
    assert 'class="persona-cta"' not in home and "#av-architect" in home
    assert "معمار" in client.get("/more").text


def test_missing_answers_rerender_with_choices_kept(client: TestClient) -> None:
    response = answer(client, goal="")
    assert response.status_code == 400
    assert "به همه سؤال‌ها جواب بده" in response.text
    assert 'value="blunt" checked' in response.text


def test_redo_prefills_previous_answers(client: TestClient) -> None:
    answer(client, note="دو سال دیگه عروسی دارم")
    page = client.get("/persona/interview").text
    assert 'value="freelancer" checked' in page and "عروسی" in page


def test_avatar_can_be_any_card(client: TestClient) -> None:
    answer(client)
    client.post("/persona/avatar", data={"card": "eagle"})
    assert "#av-eagle" in client.get("/").text
    assert client.post("/persona/avatar", data={"card": "nope"}).status_code == 400


def test_interests_fill_untouched_watchlist_only(client: TestClient) -> None:
    answer(client, interests=("crypto",))
    page = client.get("/").text
    assert "بیت" in page or "crypto:btc" in page or "BTC" in page
    client.post("/watchlist", data={"keys": "usd"})
    answer(client, interests=("gold",))
    from app import services
    from app.db import user_session
    with user_session(client.app.state.session_factory(), 1) as s:  # type: ignore[attr-defined]
        assert "gold18_gram" not in services.watchlist_keys(s)


def test_note_is_masked_before_storage(client: TestClient) -> None:
    answer(client, note="کارتم 6037991234567890 است")
    from app import services
    from app.db import user_session
    with user_session(client.app.state.session_factory(), 1) as s:  # type: ignore[attr-defined]
        raw = services.get_user_setting(s, services.PERSONA_KEY) or ""
    assert "6037991234567890" not in raw and "7890" in json.loads(raw)["note"]


def test_vazir_gets_persona_and_goal_starter(client: TestClient, model: Model) -> None:
    client.post("/assistant/consent")
    client.post("/assistant", data={"question": "سلام"})
    assert "پرسونای این کاربر" not in model.system[-1]
    answer(client, note="۲ سال دیگه عروسی دارم")
    client.post("/assistant/clear")
    assert "خرید خانه" in client.get("/assistant").text  # پیشنهاد اول از روی هدف
    client.post("/assistant", data={"question": "سلام"})
    prompt = model.system[-1]
    assert "پرسونای این کاربر" in prompt and "خرید خانه" in prompt
    assert "رک و بی‌تعارف" in prompt and "عروسی" in prompt and "معمار" in prompt


def test_persona_is_private_per_user(client: TestClient) -> None:
    answer(client)
    client.post("/logout")
    register(client, "09122222222")
    assert 'id="interview"' in client.get("/persona").text
