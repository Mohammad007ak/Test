"""پرسونای مالی: مصاحبه با هوش مصنوعی (یا پرسش‌نامه سریع)، کارت شخصیت و آواتار."""

import json
from datetime import datetime
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from starlette.datastructures import FormData

from app import onboarding_service as onboarding
from app import services
from app.assistant import interview
from app.assistant.client import AssistantError, ChatModel
from app.domain.money import to_persian_digits
from app.domain.normalize import normalize_chars
from app.domain.onboarding import infer_persona
from app.domain.persona import QUESTIONS, PersonaError, parse_answers, stats
from app.domain.persona_cards import rarity
from app.domain.spending import TEHRAN
from app.sms.text import mask_numbers
from app.web import strings as s
from app.web.common import Db, LoggedIn, done, page, read_form, redirect

CHAT_KEY = "persona_chat"
USAGE_KEY = "persona_usage"
CONSENT_KEY = "assistant_consent"
DAILY_TURNS = 40  # سپر هزینه: پیام‌های مصاحبه در روز
MAX_ANSWER = 500
MAX_MESSAGES = 50


def _multi_values(form: FormData) -> list[str]:
    return [str(v) for q in QUESTIONS if q.multi for v in form.getlist(q.key)]


def known_answers(db: Db) -> dict[str, object]:
    """حدس جواب‌ها از دارایی و دخل و خرجی که کاربر ثبت کرده (پیش‌فرض، قابل تغییر)."""
    return infer_persona(onboarding.snapshot(db, onboarding.load_state(db)))


def _opener(known: dict[str, object]) -> dict[str, Any]:
    text = s.T["persona_opener_known"] if known else s.T["persona_opener"]
    return {"role": "assistant", "content": text,
            "suggestions": list(s.PERSONA_OPENER_SUGGESTIONS)}


def _chat(db: Db) -> list[dict[str, Any]]:
    raw = services.get_user_setting(db, CHAT_KEY)
    messages = json.loads(raw) if raw else []
    return messages or [_opener(known_answers(db))]


def _used_today(db: Db) -> tuple[str, int]:
    today = datetime.now(TEHRAN).date().isoformat()
    raw = services.get_user_setting(db, USAGE_KEY)
    usage = json.loads(raw) if raw else {}
    return today, usage.get("count", 0) if usage.get("date") == today else 0


def register_persona_routes(app: FastAPI, model: ChatModel | None = None) -> None:
    def quick_form(request: Request, db: Db, error: str = "",
                   answers: dict[str, object] | None = None, note: str = "",
                   status: int = 200) -> Response:
        stored = services.load_persona(db)
        inferred: dict[str, object] = {}
        if answers is None and stored is not None:
            answers, note = stored.persona.answers, stored.note
        elif answers is None:  # بار اول: جواب‌هایی که از داده‌های ثبت‌شده معلوم است
            answers = inferred = known_answers(db)
        return page(request, "persona_interview.html", {
            "active": "persona", "questions": QUESTIONS, "answers": answers or {},
            "inferred": inferred, "note": note, "error": error,
            "has_persona": stored is not None}, status)

    def interview_page(request: Request, db: Db) -> Response:
        if model is None:
            return quick_form(request, db)
        return page(request, "persona_chat.html", {
            "active": "persona", "messages": _chat(db),
            "consented": services.get_user_setting(db, CONSENT_KEY) == "yes",
            "has_persona": services.load_persona(db) is not None})

    def turn_fragment(request: Request, text: str, suggestions: list[str] | None = None,
                      error: bool = False, status: int = 200) -> Response:
        return page(request, "_persona_turn.html", {
            "text": text, "suggestions": suggestions or [], "error": error}, status)

    @app.get("/persona", response_class=HTMLResponse, dependencies=[LoggedIn])
    def persona(request: Request, db: Db) -> Response:
        stored = services.load_persona(db)
        if stored is None:
            return interview_page(request, db)
        return page(request, "persona.html", {
            "active": "persona", "stored": stored, "card": stored.card,
            "rarity": rarity(stored.card), "stats": stats(stored.persona),
            "current_avatar": services.avatar(db),
            "reveal": request.query_params.get("new") == "1"})

    @app.get("/persona/interview", response_class=HTMLResponse, dependencies=[LoggedIn])
    def redo(request: Request, db: Db) -> Response:
        """مصاحبه از اول؛ پرسونای قبلی تا پایان مصاحبه تازه سر جایش می‌ماند."""
        services.set_user_setting(db, CHAT_KEY, "[]")
        db.commit()
        return interview_page(request, db)

    @app.get("/persona/quick", response_class=HTMLResponse, dependencies=[LoggedIn])
    def quick(request: Request, db: Db) -> Response:
        return quick_form(request, db)

    @app.post("/persona/chat", response_class=HTMLResponse, dependencies=[LoggedIn])
    async def chat(request: Request, db: Db) -> Response:
        raw = " ".join((await read_form(request)).get("question", "").split())
        if model is None or services.get_user_setting(db, CONSENT_KEY) != "yes":
            return turn_fragment(request, s.T["assistant_off"], error=True, status=403)
        if not raw or len(raw) > MAX_ANSWER:
            return turn_fragment(request, s.T["assistant_bad_question"], error=True, status=400)
        today, used = _used_today(db)
        if used >= DAILY_TURNS:
            limit = to_persian_digits(str(DAILY_TURNS))
            return turn_fragment(request, s.T["assistant_limit"].format(limit=limit),
                                 error=True, status=429)
        text = mask_numbers(normalize_chars(raw))  # فقط متن پوشانده‌شده به مدل می‌رود
        messages = _chat(db)
        history = [{"role": m["role"], "content": m["content"]} for m in messages]
        try:
            result = interview.turn(model, history, text, known_answers(db))
        except AssistantError as exc:
            return turn_fragment(request, str(exc), error=True)
        services.set_user_setting(db, USAGE_KEY, json.dumps({"date": today, "count": used + 1}))
        if result.answers is not None:
            services.save_persona(db, result.answers, result.notes, result.summary)
            services.set_user_setting(db, CHAT_KEY, "[]")
            db.commit()
            request.session["toast"] = s.T["persona_saved"]
            return redirect("/persona?new=1")
        messages += [{"role": "user", "content": text},
                     {"role": "assistant", "content": result.question,
                      "suggestions": result.suggestions}]
        services.set_user_setting(db, CHAT_KEY, json.dumps(messages[-MAX_MESSAGES:],
                                                           ensure_ascii=False))
        db.commit()
        return turn_fragment(request, result.question, result.suggestions)

    @app.post("/persona", response_class=HTMLResponse, dependencies=[LoggedIn])
    async def save(request: Request, db: Db) -> Response:
        form = await request.form()
        single = {k: str(v) for k, v in form.items() if isinstance(v, str)}
        note = single.get("note", "")
        try:
            answers = parse_answers(single, _multi_values(form))
        except PersonaError:
            partial = {**single, **{q.key: form.getlist(q.key) for q in QUESTIONS if q.multi}}
            return quick_form(request, db, s.T["persona_missing"], partial, note, 400)
        services.save_persona(db, answers, note)
        db.commit()
        request.session["toast"] = s.T["persona_saved"]
        return redirect("/persona?new=1")

    @app.post("/persona/avatar", dependencies=[LoggedIn])
    async def choose_avatar(request: Request, db: Db) -> Response:
        card = str((await request.form()).get("card", ""))
        try:
            services.set_avatar(db, card)
        except ValueError:
            raise HTTPException(400) from None
        db.commit()
        return done(request, "/persona", s.T["persona_avatar_saved"])
