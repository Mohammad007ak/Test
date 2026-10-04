"""صفحه «از وزیر بپرس»: رضایت کاربر، سقف روزانه، تاریخچه کوتاه و پاسخ با ابزارهای اپ."""

import json
from datetime import datetime
from functools import partial
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, Response

from app import services
from app.assistant import actions
from app.assistant.agent import AssistantError, ask
from app.assistant.client import ChatModel
from app.assistant.prompt import persona_brief
from app.assistant.tools import run_tool
from app.domain.money import to_persian_digits
from app.domain.spending import TEHRAN
from app.web import strings as s
from app.web.common import Db, LoggedIn, done, page, read_form
from app.web.forms import FormError

CONSENT_KEY = "assistant_consent"
HISTORY_KEY = "assistant_history"
USAGE_KEY = "assistant_usage"
MAX_QUESTION = 1000
HISTORY_TURNS = 6  # جفت پرسش و پاسخ که به مدل و صفحه برمی‌گردد


def _history(db: Db) -> list[dict[str, str]]:
    raw = services.get_user_setting(db, HISTORY_KEY)
    return json.loads(raw) if raw else []


def _used_today(db: Db) -> tuple[str, int]:
    today = datetime.now(TEHRAN).date().isoformat()
    raw = services.get_user_setting(db, USAGE_KEY)
    usage = json.loads(raw) if raw else {}
    return today, usage.get("count", 0) if usage.get("date") == today else 0


def _suggestions(db: Db, mode: str) -> list[str]:
    """پیشنهادهای شروع گفتگو؛ اولی از روی هدف پرسونای کاربر."""
    general = list(s.ASSISTANT_SUGGESTIONS[mode])
    stored = services.load_persona(db)
    if stored is None or mode != "open":
        return general
    goal = s.PERSONA_GOAL_SUGGESTIONS.get(stored.persona.get("goal"))
    return [goal, *general[:4]] if goal else general


def register_assistant_routes(app: FastAPI, model: ChatModel | None, daily_limit: int,
                              mode: str = "strict") -> None:
    def chat_page(request: Request, db: Db, status: int = 200) -> Response:
        return page(request, "assistant.html", {
            "active": "assistant", "configured": model is not None,
            "consented": services.get_user_setting(db, CONSENT_KEY) == "yes",
            "history": _history(db), "suggestions": _suggestions(db, mode),
            "disclaimer": s.T[f"assistant_disclaimer_{mode}"],
            "pending": list(actions.pending(db).items()),
        }, status)

    def turn(request: Request, question: str, answer: str, error: bool = False,
             status: int = 200, new_actions: list[Any] | None = None) -> Response:
        """فقط حباب جواب (و کارت‌های تأیید ثبت)؛ پرسش را صفحه همان لحظه نشان داده است."""
        return page(request, "_chat_answer.html", {
            "answer": answer, "error": error, "actions": new_actions or []}, status)

    @app.get("/assistant", response_class=HTMLResponse, dependencies=[LoggedIn])
    def assistant(request: Request, db: Db) -> Response:
        return chat_page(request, db)

    @app.post("/assistant/consent", dependencies=[LoggedIn])
    def consent(request: Request, db: Db) -> Response:
        services.set_user_setting(db, CONSENT_KEY, "yes")
        db.commit()
        return done(request, "/assistant", s.T["assistant_on"])

    @app.post("/assistant/clear", dependencies=[LoggedIn])
    def clear(request: Request, db: Db) -> Response:
        services.set_user_setting(db, HISTORY_KEY, "[]")
        db.commit()
        return done(request, "/assistant", s.T["assistant_cleared"])

    @app.post("/assistant", response_class=HTMLResponse, dependencies=[LoggedIn])
    async def question(request: Request, db: Db) -> Response:
        text = " ".join((await read_form(request)).get("question", "").split())
        if model is None or services.get_user_setting(db, CONSENT_KEY) != "yes":
            return turn(request, text, s.T["assistant_off"], error=True, status=403)
        if not text or len(text) > MAX_QUESTION:
            return turn(request, text[:80], s.T["assistant_bad_question"], error=True, status=400)
        today, used = _used_today(db)
        if used >= daily_limit:
            limit = to_persian_digits(str(daily_limit))
            return turn(request, text, s.T["assistant_limit"].format(limit=limit),
                        error=True, status=429)
        history = _history(db)
        before = set(actions.pending(db))
        try:
            answer = ask(model, partial(run_tool, db), text, history, mode,
                         persona_brief(services.load_persona(db)))
        except AssistantError as exc:
            return turn(request, text, str(exc), error=True, status=200)
        services.set_user_setting(db, USAGE_KEY, json.dumps({"date": today, "count": used + 1}))
        history = [*history, {"role": "user", "content": text},
                   {"role": "assistant", "content": answer.text}][-HISTORY_TURNS * 2:]
        services.set_user_setting(db, HISTORY_KEY, json.dumps(history, ensure_ascii=False))
        db.commit()
        new = [(k, v) for k, v in actions.pending(db).items() if k not in before]
        return turn(request, text, answer.text, new_actions=new)

    @app.post("/assistant/actions/{action_id}/{verb}", response_class=HTMLResponse,
              dependencies=[LoggedIn])
    def action(request: Request, action_id: str, verb: str, db: Db) -> Response:
        if verb not in ("confirm", "cancel"):
            raise HTTPException(404)
        try:
            result = (actions.confirm if verb == "confirm" else actions.cancel)(db, action_id)
        except FormError as exc:
            db.rollback()
            message = s.T["action_failed"].format(errors="، ".join(exc.errors.values()))
            return page(request, "_action_result.html", {"message": message,
                                                         "cancelled": True}, 400)
        if result is None:
            raise HTTPException(404)
        key = "action_saved" if verb == "confirm" else "action_cancelled"
        return page(request, "_action_result.html", {
            "message": s.T[key].format(title=result["title"]), "cancelled": verb == "cancel"})


def default_chat_model(url: str, key: str, model: str) -> Any:
    from app.assistant.client import OpenAICompatClient

    return OpenAICompatClient(url, key, model) if url and key and model else None
