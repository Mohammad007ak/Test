"""مدرسه وزیر سر تا ته: کاربر تازه از داشبورد وارد ایستگاه ۱ می‌شود، ۶ درس را تمام می‌کند،
امتیاز و زنجیره ذخیره می‌شود، فردا زنجیره ادامه پیدا می‌کند و دانش کارتش بالا می‌رود."""

from collections.abc import Iterator
from datetime import date, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.config import Settings
from app.db import user_session
from app.main import create_app
from app.models import LessonProgress, SchoolStats
from app.school.content import COURSES, find
from app.school.lessons import Card
from app.school_service import DbFacts
from app.web import school_routes
from app.web import strings as s
from tests.integration.conftest import FakeSender, register

DAY = date(2026, 10, 10)
SLUGS = [lesson.slug for lesson in COURSES[0].stations[0].lessons]
PERSONA = {"age": "25_34", "job": "freelancer", "income": "variable", "household": "single",
           "housing": "renter", "goal": "home", "horizon": "3_7", "drop": "wait",
           "choice": "coin", "experience": "market", "style": "balanced", "emergency": "lt3",
           "tone": "blunt", "interests": ["gold"]}


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    settings = Settings(database_url=f"sqlite:///{tmp_path / 'test.db'}", secret_key="test")
    app = create_app(settings, migrate=True, price_sources=[], schedule=False,
                     otp_sender=FakeSender(), chat_model=None)
    monkeypatch.setattr(school_routes, "tehran_today", lambda: DAY)
    with TestClient(app) as c:
        register(c)
        yield c


def _set_day(monkeypatch: pytest.MonkeyPatch, day: date) -> None:
    monkeypatch.setattr(school_routes, "tehran_today", lambda: day)


def _db(client: TestClient):  # type: ignore[no-untyped-def]
    return user_session(client.app.state.session_factory(), 1)  # type: ignore[attr-defined]


def _cards(client: TestClient, slug: str) -> list[Card]:
    found = find(slug)
    assert found is not None
    with _db(client) as db:
        return found[2].cards(DbFacts(db, (), DAY))


def _right(card: Card) -> str:
    if card.kind == "slider":
        assert card.slider is not None
        return str(card.slider.right_low)
    if card.kind in ("match", "order"):
        return ",".join(map(str, card.expected))
    if card.kind == "number":
        return str(card.number)
    if card.kind == "multi":
        return ",".join(map(str, sorted(card.rights)))
    if card.kind == "quick":
        return ",".join("1" if truth else "0" for _s, truth in card.statements)
    return str(card.correct)


def _wrong(card: Card) -> str:
    if card.kind == "slider":
        assert card.slider is not None
        return str(card.slider.low)
    if card.kind in ("match", "order"):
        return ",".join(map(str, range(len(card.expected))))
    if card.kind == "number":
        return str((card.number or 0) * 2 + 1)
    if card.kind == "multi":
        return ""
    if card.kind == "quick":
        return ",".join("0" if truth else "1" for _s, truth in card.statements)
    return str((card.correct or 0) + 1 if card.correct == 0 else 0)


def _play(client: TestClient, slug: str, wrong: int = 0) -> str:
    """درس را با جواب درست (یا چند غلط اول) تمام می‌کند و متن صفحه پایان را برمی‌گرداند."""
    assert client.get(f"/school/lesson/{slug}").status_code == 200
    misses = wrong
    for i, card in enumerate(_cards(client, slug)):
        if not card.graded:
            continue
        answer = _wrong(card) if misses else _right(card)
        misses = max(misses - 1, 0)
        response = client.post(f"/school/lesson/{slug}/answer",
                               data={"card": str(i), "answer": answer},
                               headers={"HX-Request": "true"})
        assert response.status_code == 200, response.text
    done = client.post(f"/school/lesson/{slug}/finish", follow_redirects=False)
    assert done.status_code == 303 and done.headers["location"].endswith("/done")
    return client.get(done.headers["location"]).text


def _stats(client: TestClient) -> SchoolStats:
    with _db(client) as db:
        stats = db.scalars(select(SchoolStats)).one()
        db.expunge(stats)
        return stats


def test_dashboard_card_and_tab_lead_to_first_lesson(client: TestClient) -> None:
    home = client.get("/").text
    assert 'href="/school/lesson/money"' in home
    assert 'class="sc-entry' in home and 'href="/school"' in home  # قرص زنجیره بالای خانه
    assert len(s.TABS) == 5 and all(tab[0] != "school" for tab in s.TABS)  # نوار پایین دست نخورده
    school = client.get("/school").text
    assert 'href="/school/lesson/money"' in school
    assert 'href="/school/lesson/inflation"' not in school  # هنوز قفل است


def test_locked_lesson_redirects_to_map(client: TestClient) -> None:
    response = client.get("/school/lesson/inflation", follow_redirects=False)
    assert response.status_code == 303 and response.headers["location"] == "/school"
    assert client.get("/school/lesson/nope").status_code == 404


def test_answer_is_not_sent_before_answering(client: TestClient) -> None:
    page = client.get("/school/lesson/money").text
    assert "data-correct" not in page
    card = _cards(client, "money")[1]
    assert card.good not in page and card.bad not in page


def test_answer_is_checked_on_server(client: TestClient) -> None:
    client.get("/school/lesson/money")
    card = _cards(client, "money")[1]
    good = client.post("/school/lesson/money/answer", data={"card": "1", "answer": _right(card)})
    assert 'data-ok="1"' in good.text and card.good in good.text
    # جواب دوم همان کارت امتیاز را عوض نمی‌کند
    again = client.post("/school/lesson/money/answer", data={"card": "1", "answer": _wrong(card)})
    assert 'data-ok="0"' in again.text and 'data-counted="1"' in again.text
    bad = client.post("/school/lesson/money/answer", data={"card": "1", "answer": "9"})
    assert bad.status_code == 400
    intro = client.post("/school/lesson/money/answer", data={"card": "0", "answer": "0"})
    assert intro.status_code == 400


def test_finish_needs_every_answer(client: TestClient) -> None:
    client.get("/school/lesson/money")
    response = client.post("/school/lesson/money/finish", follow_redirects=False)
    assert response.headers["location"] == "/school/lesson/money"
    with _db(client) as db:
        assert db.scalars(select(LessonProgress)).all() == []


def test_full_station_saves_xp_streak_knowledge_and_continues_tomorrow(
        client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    client.post("/persona", data={k: v for k, v in PERSONA.items() if k != "interests"}
                | {"interests": PERSONA["interests"]})
    before = client.get("/persona").text
    assert "سطح ۱" in before

    done = _play(client, "money", wrong=1)
    assert "+۴۸" in done  # ۴۰ + ۲ جواب درست × ۴
    stats = _stats(client)
    assert (stats.xp, stats.streak, stats.knowledge) == (48, 1, 2)

    for slug in SLUGS[1:]:
        done = _play(client, slug)
    assert "تورم دیگه نمی‌تونه یواشکی پولت رو بخوره" in done  # صندوقچه پایان ایستگاه
    stats = _stats(client)
    assert stats.xp == 48 + 5 * 52 + 50
    assert stats.streak == 1 and stats.knowledge == 12
    with _db(client) as db:
        assert len(db.scalars(select(LessonProgress)).all()) == 6

    # فردا: دوباره خواندن نصف امتیاز دارد، دانش اضافه نمی‌شود، ولی زنجیره ادامه پیدا می‌کند
    _set_day(monkeypatch, DAY + timedelta(days=1))
    done = _play(client, "money")
    assert "+۲۶" in done
    stats = _stats(client)
    assert (stats.streak, stats.best_streak, stats.knowledge) == (2, 2, 12)
    assert stats.last_day == DAY + timedelta(days=1)
    assert "🔥" in client.get("/school").text

    persona = client.get("/persona").text
    assert "سطح" in persona  # دانش مدرسه روی کارت شخصیت


def test_streak_freezes_one_missed_day(client: TestClient,
                                       monkeypatch: pytest.MonkeyPatch) -> None:
    _play(client, "money")
    _set_day(monkeypatch, DAY + timedelta(days=2))
    _play(client, "inflation")
    stats = _stats(client)
    assert stats.streak == 2 and stats.freeze_day == DAY + timedelta(days=1)


def test_progress_is_per_user(client: TestClient) -> None:
    _play(client, "money")
    client.post("/logout")
    register(client, phone="09122222222")
    assert 'href="/school/lesson/inflation"' not in client.get("/school").text
    assert client.get("/school/lesson/inflation", follow_redirects=False).status_code == 303


def test_school_needs_login(tmp_path: Path) -> None:
    settings = Settings(database_url=f"sqlite:///{tmp_path / 't.db'}", secret_key="test")
    app = create_app(settings, migrate=False, price_sources=[], schedule=False,
                     otp_sender=FakeSender(), chat_model=None)
    with TestClient(app) as c:
        response = c.get("/school", follow_redirects=False)
        assert response.headers["location"] == "/login"


def _hearts(client: TestClient) -> int:
    return _stats(client).hearts


def _answer(client: TestClient, slug: str, right: bool = True) -> list[str]:
    """همه سؤال‌های درس را جواب می‌دهد (بدون پایان) و متن بازخوردها را برمی‌گرداند."""
    client.get(f"/school/lesson/{slug}")
    texts = []
    for i, card in enumerate(_cards(client, slug)):
        if card.graded:
            texts.append(client.post(f"/school/lesson/{slug}/answer", data={
                "card": str(i), "answer": _right(card) if right else _wrong(card)}).text)
    return texts


def test_wrong_answers_cost_hearts_until_empty(client: TestClient) -> None:
    _play(client, "money")  # یک بار درس تمام شود تا ردیف آمار ساخته شود
    assert _hearts(client) == 5
    texts = _answer(client, "inflation", right=False)
    assert _hearts(client) == 2  # سه سؤال غلط
    texts = _answer(client, "inflation", right=False)
    assert _hearts(client) == 0
    assert any("جانت تموم شد" in text for text in texts)
    response = client.get("/school/lesson/inflation", follow_redirects=False)
    assert response.status_code == 303  # درس تازه بدون جان باز نمی‌شود
    # مرور درس تمام‌شده بدون جان هم باز است و یک جان برمی‌گرداند
    _play(client, "money")
    assert _hearts(client) == 1


def test_premium_has_infinite_hearts(client: TestClient) -> None:
    from datetime import UTC, datetime

    from app.models import User

    with client.app.state.session_factory() as system:  # type: ignore[attr-defined]
        user = system.get(User, 1)
        user.premium_until = datetime(2099, 1, 1, tzinfo=UTC)
        system.commit()
    _play(client, "money")
    for _ in range(3):
        _answer(client, "inflation", right=False)
    assert _hearts(client) == 5
    assert "∞" in client.get("/school").text


def test_placement_sets_level_per_topic(client: TestClient) -> None:
    from app.school.content.placement import PLACEMENT

    page = client.get("/school").text
    assert "/school/lesson/placement" in page
    client.get("/school/lesson/placement")
    cards = PLACEMENT.cards(None)  # type: ignore[arg-type]
    for i, card in enumerate(cards):
        right = i <= 4  # مالی پایه و وام: هر دو درست؛ پس‌انداز: فقط اولی
        client.post("/school/lesson/placement/answer",
                    data={"card": str(i), "answer": _right(card) if right else _wrong(card)})
    response = client.post("/school/lesson/placement/finish", follow_redirects=False)
    assert response.headers["location"] == "/school"
    assert _stats(client).levels == ("basics=3,loans=3,saving=2,stocks=1,crypto=1,fxgold=1")
    # مالی پایه از سطح پیشرفته شروع می‌شود و سطح‌های پایین‌تر برای مرور باز است
    basics = client.get("/school?t=basics").text
    assert 'href="/school/lesson/net-worth"' in basics
    assert 'href="/school/lesson/money"' in basics and 'href="/school/lesson/inflation"' in basics
    assert client.get("/school/lesson/smart-goals", follow_redirects=False).status_code == 303
    saving = client.get("/school?t=saving").text
    assert 'href="/school/lesson/risk-return"' in saving


def test_new_card_types_render_and_grade(client: TestClient) -> None:
    from app.school.content import COURSES

    client.post("/school/placement/skip")
    for course in COURSES:  # اولین درس هر تاپیک با همه نوع کارتش، سر تا ته
        done = _play(client, course.stations[0].lessons[0].slug)
        assert "درس تموم شد" in done
    page = client.get("/school/lesson/budget-50-30-20", follow_redirects=False)
    assert page.status_code == 303  # سطح متوسط هنوز قفل است
    client.get("/school/lesson/loan-basics")
    text = client.get("/school/lesson/loan-basics").text
    assert 'class="sc-match"' in text


def test_admin_grants_three_months_premium(client: TestClient) -> None:
    from app.models import User

    with client.app.state.session_factory() as system:  # type: ignore[attr-defined]
        system.add(User(id=50, phone="09125555555"))
        system.commit()
    client.app.state.owner_phone = "09121111111"  # type: ignore[attr-defined]
    response = client.post("/admin/users/50/premium", follow_redirects=False)
    assert response.status_code == 303
    with client.app.state.session_factory() as system:  # type: ignore[attr-defined]
        assert system.get(User, 50).premium_until is not None
    assert "ویژه تا" in client.get("/admin?q=5555").text
    client.post("/admin/users/50/premium/revoke")
    with client.app.state.session_factory() as system:  # type: ignore[attr-defined]
        assert system.get(User, 50).premium_until is None
