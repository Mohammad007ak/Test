import pytest

from app.domain.persona import (
    CARDS,
    QUESTIONS,
    PersonaError,
    build_persona,
    card_for,
    parse_answers,
)

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


class TestCards:
    def test_every_card_reachable_and_known(self) -> None:
        seen = {card_for(build_persona(a)) for a in (
            CALM, BOLD,
            {**CALM, "interests": []},
            {**CALM, "goal": "debt"},
            {**BOLD, "experience": "none", "age": "25_34", "drop": "wait", "choice": "coin"},
            {**BOLD, "interests": ["stocks"]},
            {**BOLD, "drop": "wait", "choice": "coin", "experience": "market"},
            {**BOLD, "drop": "wait", "choice": "coin", "experience": "market",
             "horizon": "3_7", "style": "frugal"},
            {**BOLD, "drop": "wait", "choice": "coin", "experience": "market",
             "horizon": "3_7"},
        )}
        assert seen == set(CARDS)

    def test_rules(self) -> None:
        assert card_for(build_persona(CALM)) == "coin"  # محتاط + طلا + تورم
        assert card_for(build_persona({**CALM, "interests": []})) == "turtle"
        assert card_for(build_persona({**CALM, "goal": "debt"})) == "amir"
        assert card_for(build_persona(BOLD)) == "surfer"


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
