import json
from typing import Any

import pytest

from app.assistant.client import AssistantError
from app.assistant.interview import TOOLS, system_prompt, turn

FULL = {"age": "25_34", "job": "freelancer", "income": "variable", "household": "single",
        "housing": "renter", "goal": "home", "horizon": "3_7", "drop": "wait",
        "choice": "coin", "experience": "market", "style": "balanced", "emergency": "lt3",
        "tone": "blunt", "interests": ["gold"]}


def call(name: str, args: dict[str, Any], cid: str = "c1") -> dict[str, Any]:
    return {"role": "assistant", "content": None, "tool_calls": [
        {"id": cid, "type": "function",
         "function": {"name": name, "arguments": json.dumps(args, ensure_ascii=False)}}]}


class Script:
    def __init__(self, *replies: dict[str, Any]) -> None:
        self.replies = list(replies)
        self.seen: list[list[dict[str, Any]]] = []

    def complete(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> dict:
        self.seen.append(list(messages))
        return self.replies.pop(0)


def test_question_with_suggestions() -> None:
    model = Script(call("ask_user", {"question": "کارت چیه؟",
                                     "suggestions": ["کارمندم", "فریلنسر", "کارمندم", ""]}))
    result = turn(model, [{"role": "assistant", "content": "چند سالته؟"}], "۲۸")
    assert result.question == "کارت چیه؟" and result.suggestions == ["کارمندم", "فریلنسر"]
    assert result.answers is None
    sent = model.seen[0]
    assert sent[0]["role"] == "system" and sent[-1] == {"role": "user", "content": "۲۸"}


def test_plain_text_reply_is_a_question() -> None:
    result = turn(Script({"role": "assistant", "content": "خب، هدفت چیه؟"}), [], "سلام")
    assert result.question == "خب، هدفت چیه؟" and result.suggestions == []


def test_save_returns_validated_answers() -> None:
    result = turn(Script(call("save_persona", {**FULL, "summary": "تو آدم حسابگری هستی.",
                                               "notes": "عروسی دارد"})), [], "تموم")
    assert result.answers is not None and result.answers["goal"] == "home"
    assert result.answers["interests"] == ["gold"]
    assert result.summary.startswith("تو") and result.notes == "عروسی دارد"


def test_incomplete_save_goes_back_to_model_which_asks() -> None:
    partial = {k: v for k, v in FULL.items() if k not in ("drop", "choice")}
    model = Script(call("save_persona", {**partial, "summary": "x"}),
                   call("ask_user", {"question": "اگه ۲۰٪ ضرر کنی؟", "suggestions": ["می‌فروشم"]},
                        "c2"))
    result = turn(model, [], "همین")
    assert result.question.startswith("اگه") and result.answers is None
    feedback = json.loads(model.seen[1][-1]["content"])["error"]
    assert "drop" in feedback and "choice" in feedback


def test_gives_up_after_rounds() -> None:
    bad = call("save_persona", {"summary": "x"})
    with pytest.raises(AssistantError):
        turn(Script(bad, bad, bad), [], "x")


def test_tools_and_prompt_cover_every_field() -> None:
    save = next(t for t in TOOLS if t["function"]["name"] == "save_persona")
    props = save["function"]["parameters"]["properties"]
    assert {"age", "drop", "interests", "tone", "summary"} <= set(props)
    assert props["drop"]["enum"] == ["sell", "wait", "buy"]
    assert "drop" in system_prompt() and "ask_user" in system_prompt()


def test_known_facts_reach_the_prompt_and_fill_the_save() -> None:
    known = {"housing": "renter", "interests": ["gold", "fx"]}
    prompt = system_prompt(known)
    assert "housing: renter=مستأجرم" in prompt and "fx=دلار و ارز" in prompt
    assert "حدس زده‌ایم" not in system_prompt()
    partial = {k: v for k, v in FULL.items() if k not in ("housing", "interests")}
    model = Script(call("save_persona", {**partial, "summary": "تو…"}))
    result = turn(model, [], "تمام", known)
    assert result.answers is not None
    assert result.answers["housing"] == "renter" and result.answers["interests"] == ["gold", "fx"]
    assert model.seen[0][0]["content"] == prompt


def test_user_correction_beats_known_fact() -> None:
    model = Script(call("save_persona", {**FULL, "housing": "owner", "summary": "تو…"}))
    result = turn(model, [], "خونه مال خودمه", {"housing": "renter"})
    assert result.answers is not None and result.answers["housing"] == "owner"
