"""صحت محتوای مدرسه: هر سؤال جواب درست دارد، گزینه‌ها یکتا هستند و slugها تکراری نیستند،
برای هر تورمی که درس‌ها می‌پذیرند و هر عدد شخصی."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import pytest

from app.domain.school import INFLATION_RANGE
from app.school.content import COURSES, find, path
from app.school.lessons import Card, Personal, Race, RaceRow, check

RACE = Race(date(2023, 10, 4), date(2026, 10, 4), 100_000_000,
            (RaceRow("cash", 100_000_000), RaceRow("usd", 543_605_237),
             RaceRow("coin_emami", 994_495_413), RaceRow("gold18_gram", 1_179_954_932)), True)


@dataclass(frozen=True)
class Facts:
    inflation: Decimal = Decimal("0.35")
    cash: Personal = Personal(40_000_000, True)
    monthly_spend: Personal = Personal(20_000_000, True)
    race: Race = RACE


def _inflations() -> list[Decimal]:
    low, high = INFLATION_RANGE
    return [low + Decimal(n) / 100 for n in range(int((high - low) * 100) + 1)]


def _all_cards(facts: Facts) -> list[Card]:
    return [card for _c, _s, lesson in path() for card in lesson.cards(facts)]


def _assert_valid(card: Card) -> None:
    if not card.graded:
        assert card.correct is None and not card.options
        return
    if card.kind == "slider":
        assert card.slider is not None
        sl = card.slider
        assert sl.low <= sl.right_low <= sl.right_high <= sl.high
        assert check(card, str(sl.right_low)) is True
        assert check(card, str(sl.low if sl.low < sl.right_low else sl.high)) is False
        return
    assert card.correct is not None and 0 <= card.correct < len(card.options)
    assert len(set(card.options)) == len(card.options), card.options
    assert check(card, str(card.correct)) is True
    assert all(check(card, str(k)) is False for k in range(len(card.options))
               if k != card.correct)
    assert card.good and card.bad


def test_station_one_has_six_lessons_of_four_to_six_cards() -> None:
    lessons = COURSES[0].stations[0].lessons
    assert len(lessons) == 6
    for lesson in lessons:
        cards = lesson.cards(Facts())
        assert 4 <= len(cards) <= 6, lesson.slug
        assert any(card.graded for card in cards)


def test_slugs_are_unique_and_findable() -> None:
    slugs = [lesson.slug for _c, _s, lesson in path()]
    assert len(slugs) == len(set(slugs))
    assert all(find(slug) is not None for slug in slugs)
    assert find("nope") is None


def test_six_courses_with_stations() -> None:
    assert [c.number for c in COURSES] == [1, 2, 3, 4, 5, 6]
    assert all(c.stations for c in COURSES)
    station_keys = [s.key for c in COURSES for s in c.stations]
    assert len(station_keys) == len(set(station_keys))


@pytest.mark.parametrize("inflation", _inflations())
def test_every_question_is_answerable_for_any_inflation(inflation: Decimal) -> None:
    for card in _all_cards(Facts(inflation=inflation)):
        _assert_valid(card)


@pytest.mark.parametrize("toman", [1_000_000, 3_700_000, 40_000_000, 912_345_678,
                                   12_000_000_000])
def test_personal_numbers(toman: int) -> None:
    facts = Facts(cash=Personal(toman, False), monthly_spend=Personal(toman, False))
    for card in _all_cards(facts):
        _assert_valid(card)


def test_market_winner_is_the_biggest_final_value() -> None:
    race = Race(RACE.start, RACE.end, RACE.amount_toman,
                (RaceRow("cash", 100_000_000), RaceRow("usd", 900_000_000),
                 RaceRow("coin_emami", 400_000_000), RaceRow("gold18_gram", 500_000_000)), False)
    card = next(c for c in _all_cards(Facts(race=race)) if c.kind == "market")
    assert card.correct == 1 and "دلار" in card.good
    assert "داده ذخیره‌شده" in card.note


def test_sample_numbers_are_labelled() -> None:
    personal = [c for c in _all_cards(Facts()) if c.kind in ("personal", "slider")]
    assert personal and all(c.sample and "نمونه" in c.text for c in personal)
    own = [c for c in _all_cards(Facts(cash=Personal(50_000_000, False),
                                       monthly_spend=Personal(30_000_000, False)))
           if c.kind in ("personal", "slider")]
    assert all(not c.sample and "نمونه" not in c.text for c in own)


def test_market_and_personal_cards_say_not_advice() -> None:
    market = [c for c in _all_cards(Facts()) if c.kind == "market"]
    assert market and all("توصیه خرید" in c.note for c in market)


def test_numbers_follow_inflation_setting() -> None:
    lesson = find("inflation")
    assert lesson is not None
    text_35 = " ".join(c.text for c in lesson[2].cards(Facts(inflation=Decimal("0.35"))))
    text_50 = " ".join(c.text for c in lesson[2].cards(Facts(inflation=Decimal("0.5"))))
    assert "۳۵٪" in text_35 and "۵۰٪" in text_50


def test_nothing_says_buy_now() -> None:
    for card in _all_cards(Facts()):
        for text in (card.text, card.good, card.bad, *card.options):
            assert "الان بخر" not in text and "بخرید" not in text
