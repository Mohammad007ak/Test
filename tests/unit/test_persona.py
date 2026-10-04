import random

import pytest

from app.domain.persona import (
    QUESTIONS,
    PersonaError,
    build_persona,
    parse_answers,
    question,
    stats,
)
from app.domain.persona_cards import CARDS, card_for, rarity

CALM = {"age": "45_54", "job": "employee", "income": "fixed", "household": "kids",
        "housing": "owner", "goal": "inflation", "horizon": "1_3", "drop": "sell",
        "choice": "sure", "experience": "safe", "style": "frugal", "emergency": "lt3",
        "tone": "simple", "interests": ["gold"]}
BOLD = {**CALM, "age": "u25", "income": "mostly", "household": "single", "horizon": "gt7",
        "drop": "buy", "choice": "moon", "experience": "advanced", "emergency": "gt6",
        "goal": "growth", "style": "balanced", "interests": ["crypto", "stocks"]}


class TestScores:
    def test_cautious_answers_are_conservative(self) -> None:
        p = build_persona(CALM)
        assert p.profile == "conservative" and p.risk < 35

    def test_bold_answers_are_bold(self) -> None:
        p = build_persona(BOLD)
        assert p.profile == "bold" and p.risk >= 65
        assert p.tolerance == 100

    def test_risk_is_the_lower_of_willingness_and_capacity(self) -> None:
        eager_but_fragile = {**BOLD, "age": "55p", "horizon": "lt1", "income": "none",
                             "emergency": "none", "household": "supports"}
        p = build_persona(eager_but_fragile)
        assert p.tolerance == 100 and p.capacity < 30
        assert p.risk == p.capacity and p.profile == "conservative"
        assert p.gap == "eager"  # تمایلش از توانش خیلی بیشتر است

    def test_capable_but_shy_gap(self) -> None:
        shy = {**BOLD, "drop": "sell", "choice": "sure", "experience": "none"}
        p = build_persona(shy)
        assert p.gap == "shy" and p.risk == p.tolerance

    def test_balanced_middle(self) -> None:
        mid = {**BOLD, "drop": "wait", "choice": "coin", "experience": "market"}
        assert build_persona(mid).profile == "balanced"

    def test_scores_are_integers_between_0_and_100(self) -> None:
        for answers in (CALM, BOLD):
            p = build_persona(answers)
            for value in (p.risk, p.tolerance, p.capacity):
                assert isinstance(value, int) and 0 <= value <= 100


class TestStats:
    def test_four_stats_between_0_and_100(self) -> None:
        st = stats(build_persona(BOLD))
        assert set(st) == {"risk", "discipline", "patience", "knowledge"}
        assert all(isinstance(v, int) and 0 <= v <= 100 for v in st.values())
        assert st["risk"] == build_persona(BOLD).risk

    def test_frugal_saver_is_disciplined(self) -> None:
        saver = stats(build_persona({**CALM, "style": "frugal", "emergency": "gt6"}))
        spender = stats(build_persona({**CALM, "style": "spender", "emergency": "none"}))
        assert saver["discipline"] > 80 > 30 > spender["discipline"]


class TestCards:
    def test_fifty_unique_cards(self) -> None:
        assert len(CARDS) == 50 and len(set(CARDS)) == 50

    def test_match_is_deterministic_and_known(self) -> None:
        for answers in (CALM, BOLD):
            card = card_for(build_persona(answers))
            assert card in CARDS and card == card_for(build_persona(answers))

    def test_answers_spread_over_many_cards(self) -> None:
        rng = random.Random(7)
        seen = set()
        for _ in range(3000):
            answers: dict[str, object] = {
                q.key: (rng.sample(q.options, rng.randint(0, 2)) if q.multi
                        else rng.choice(q.options)) for q in QUESTIONS}
            seen.add(card_for(build_persona(answers)))
        assert len(seen) >= 40

    def test_affinity_steers_the_match(self) -> None:
        goals = question("goal").options
        mid = {**BOLD, "drop": "wait", "choice": "coin", "experience": "market",
               "emergency": "3_6", "horizon": "3_7", "interests": []}
        assert len({card_for(build_persona({**mid, "goal": g})) for g in goals}) >= 3

    def test_rarity_levels(self) -> None:
        levels = {rarity(card) for card in CARDS}
        assert levels == {"common", "rare", "epic", "legendary"}


class TestParse:
    def test_valid_form(self) -> None:
        form = {k: v for k, v in CALM.items() if k != "interests"}
        answers = parse_answers(form, ["gold", "fx", "bogus"])
        assert answers["interests"] == ["gold", "fx"]
        assert answers["goal"] == "inflation"

    def test_missing_or_unknown_answer(self) -> None:
        form = {k: v for k, v in CALM.items() if k != "interests"}
        with pytest.raises(PersonaError) as exc:
            parse_answers({**form, "age": "999", "goal": ""}, [])
        assert set(exc.value.missing) == {"age", "goal"}

    def test_question_keys_cover_scoring(self) -> None:
        keys = {q.key for q in QUESTIONS}
        assert {"age", "horizon", "drop", "choice", "experience", "income",
                "emergency", "household", "goal", "interests"} <= keys
