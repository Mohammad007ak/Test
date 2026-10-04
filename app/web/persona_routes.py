"""پرسونای مالی: مصاحبه چت‌گونه با وزیر، کارت شخصیت و آواتار."""

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from starlette.datastructures import FormData

from app import services
from app.domain.persona import QUESTIONS, PersonaError, parse_answers
from app.web import strings as s
from app.web.common import Db, LoggedIn, done, page, redirect


def _multi_values(form: FormData) -> list[str]:
    return [str(v) for q in QUESTIONS if q.multi for v in form.getlist(q.key)]


def register_persona_routes(app: FastAPI) -> None:
    def interview(request: Request, db: Db, error: str = "",
                  answers: dict[str, object] | None = None, note: str = "",
                  status: int = 200) -> Response:
        stored = services.load_persona(db)
        if answers is None and stored is not None:
            answers, note = stored.persona.answers, stored.note
        return page(request, "persona_interview.html", {
            "active": "persona", "questions": QUESTIONS, "answers": answers or {},
            "note": note, "error": error, "has_persona": stored is not None}, status)

    @app.get("/persona", response_class=HTMLResponse, dependencies=[LoggedIn])
    def persona(request: Request, db: Db) -> Response:
        stored = services.load_persona(db)
        if stored is None:
            return interview(request, db)
        return page(request, "persona.html", {
            "active": "persona", "stored": stored, "card": stored.card,
            "current_avatar": services.avatar(db),
            "reveal": request.query_params.get("new") == "1"})

    @app.get("/persona/interview", response_class=HTMLResponse, dependencies=[LoggedIn])
    def redo(request: Request, db: Db) -> Response:
        return interview(request, db)

    @app.post("/persona", response_class=HTMLResponse, dependencies=[LoggedIn])
    async def save(request: Request, db: Db) -> Response:
        form = await request.form()
        single = {k: str(v) for k, v in form.items() if isinstance(v, str)}
        note = single.get("note", "")
        try:
            answers = parse_answers(single, _multi_values(form))
        except PersonaError:
            partial = {**single, **{q.key: form.getlist(q.key) for q in QUESTIONS if q.multi}}
            return interview(request, db, s.T["persona_missing"], partial, note, 400)
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
