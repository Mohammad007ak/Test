"""مصاحبه پرسونا، کارت شخصیت، آواتار و اثرش روی وزیر و قیمت‌های صفحه اصلی."""

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.web import strings as s
from tests.integration.conftest import FakeSender, register


def services_card(client: TestClient) -> str:
    from app import services
    from app.db import user_session
    with user_session(client.app.state.session_factory(), 1) as db:  # type: ignore[attr-defined]
        stored = services.load_persona(db)
        assert stored is not None
        return stored.card

ANSWERS = {"age": "25_34", "job": "freelancer", "income": "variable", "household": "single",
           "housing": "renter", "goal": "home", "horizon": "3_7", "drop": "wait",
           "choice": "coin", "experience": "market", "style": "balanced", "emergency": "lt3",
           "tone": "blunt"}


FULL = {**ANSWERS, "interests": ["gold"]}


class Model:
    """چت وزیر: «باشه». مصاحبه: اول یک سؤال با پیشنهاد، بعد ذخیره پرسونا."""

    def __init__(self) -> None:
        self.system: list[str] = []
        self.interview: list[list[dict]] = []

    def complete(self, messages: list[dict], tools: list[dict]) -> dict:
        names = {t["function"]["name"] for t in tools}
        if "save_persona" not in names:
            self.system.append(messages[0]["content"])
            return {"role": "assistant", "content": "باشه."}
        self.interview.append(list(messages))
        if len(self.interview) == 1:
            args = {"question": "هدف مالی اصلی‌ت چیه؟", "suggestions": ["خرید خانه", "مهاجرت"]}
            name = "ask_user"
        else:
            args = {**FULL, "summary": "تو آدم هدفمندی هستی که خانه می‌خواهد.",
                    "notes": "دو سال دیگر عروسی دارد"}
            name = "save_persona"
        return {"role": "assistant", "content": None, "tool_calls": [{
            "id": "c1", "type": "function",
            "function": {"name": name, "arguments": json.dumps(args, ensure_ascii=False)}}]}


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


def test_without_persona_home_invites_and_ai_interview_asks_consent(client: TestClient) -> None:
    assert 'class="persona-cta"' in client.get("/").text
    page = client.get("/persona").text
    assert 'name="next" value="/persona"' in page and 'name="question"' not in page
    assert client.post("/persona/chat", data={"question": "سلام"}).status_code == 403
    consent = client.post("/assistant/consent", data={"next": "/persona"}, follow_redirects=False)
    assert consent.headers["location"] == "/persona"
    page = client.get("/persona").text
    assert 'action="/persona/chat"' in page and "چند سالته" in page
    assert 'data-ask="حدود ۳۰، کارمندم"' in page  # جواب پیشنهادی؛ نوشتن آزاد هم هست


def test_ai_interview_asks_then_saves_persona(client: TestClient, model: Model) -> None:
    client.post("/assistant/consent")
    reply = client.post("/persona/chat", data={"question": "۲۸ سالمه، فریلنسرم"})
    assert reply.status_code == 200 and "هدف مالی" in reply.text
    assert 'data-ask="خرید خانه"' in reply.text
    assert "هدف مالی" in client.get("/persona").text  # گفتگو بعد از رفرش می‌ماند
    done = client.post("/persona/chat", data={"question": "خرید خانه"}, follow_redirects=False)
    assert done.headers["location"] == "/persona?new=1"
    sent = model.interview[1]
    assert sent[0]["role"] == "system"
    assert [m["content"] for m in sent[1:]][-3:] == ["۲۸ سالمه، فریلنسرم", "هدف مالی اصلی‌ت چیه؟",
                                                    "خرید خانه"]
    card = client.get("/persona?new=1").text
    assert "tcard" in card and "تو آدم هدفمندی هستی" in card
    assert "/ ۵۰" in card and "ریسک‌پذیری" in card and "انضباط" in card


def test_interview_answers_are_masked_before_the_model(client: TestClient, model: Model) -> None:
    client.post("/assistant/consent")
    client.post("/persona/chat", data={"question": "کارتم 6037991234567890 است"})
    assert "6037991234567890" not in json.dumps(model.interview[0], ensure_ascii=False)


def test_redo_restarts_conversation_but_keeps_card(client: TestClient) -> None:
    client.post("/assistant/consent")
    client.post("/persona/chat", data={"question": "سلام"})
    client.post("/persona/chat", data={"question": "خرید خانه"})
    page = client.get("/persona/interview").text
    assert "چند سالته" in page and "هدف مالی" not in page
    assert "tcard" in client.get("/persona").text


def test_without_ai_the_quick_form_is_used(tmp_path: Path) -> None:
    settings = Settings(database_url=f"sqlite:///{tmp_path / 'q.db'}", secret_key="t")
    app = create_app(settings, price_sources=[], schedule=False, otp_sender=FakeSender(),
                     chat_model=None)
    with TestClient(app) as c:
        register(c)
        page = c.get("/persona").text
        assert 'id="interview"' in page and 'name="drop"' in page and 'name="interests"' in page


def test_saving_shows_card_and_sets_avatar(client: TestClient) -> None:
    response = answer(client)
    assert response.status_code == 303 and response.headers["location"] == "/persona?new=1"
    page = client.get("/persona?new=1").text
    card = services_card(client)
    name, emoji = s.PERSONA_CARDS[card]["name"], s.PERSONA_CARDS[card]["emoji"]
    assert name in page and "reveal" in page and "متعادل" in page
    home = client.get("/").text
    assert 'class="persona-cta"' not in home and f'avatar-emoji">{emoji}' in home
    assert name in client.get("/more").text


def test_missing_answers_rerender_with_choices_kept(client: TestClient) -> None:
    response = answer(client, goal="")  # پرسش‌نامه سریع
    assert response.status_code == 400
    assert "به همه سؤال‌ها جواب بده" in response.text
    assert 'value="blunt" checked' in response.text


def test_redo_prefills_previous_answers(client: TestClient) -> None:
    answer(client, note="دو سال دیگه عروسی دارم")
    page = client.get("/persona/quick").text
    assert 'value="freelancer" checked' in page and "عروسی" in page


def test_avatar_can_be_any_card(client: TestClient) -> None:
    answer(client)
    client.post("/persona/avatar", data={"card": "dragon"})
    assert 'avatar-emoji">🐉' in client.get("/").text
    assert client.post("/persona/avatar", data={"card": "nope"}).status_code == 400


def test_retake_moves_avatar_to_the_new_card_unless_user_picked_one(client: TestClient) -> None:
    answer(client)
    first = services_card(client)
    answer(client, age="55p", drop="sell", choice="sure", experience="none", horizon="lt1",
           emergency="none", style="spender")
    second = services_card(client)
    assert second != first
    emoji = s.PERSONA_CARDS[second]["emoji"]
    assert f'avatar-emoji">{emoji}' in client.get("/").text  # آواتار با کارت تازه عوض شد
    client.post("/persona/avatar", data={"card": "dragon"})
    answer(client)  # کاربر خودش آواتار انتخاب کرده؛ دیگر عوض نمی‌شود
    assert 'avatar-emoji">🐉' in client.get("/").text


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
    assert "رک و بی‌تعارف" in prompt and "عروسی" in prompt


def test_persona_is_private_per_user(client: TestClient) -> None:
    answer(client)
    client.post("/logout")
    register(client, "09122222222")
    assert "tcard" not in client.get("/persona").text
