"""مدرسه وزیر: نقشه مسیر (/school)، درس کارت‌به‌کارت و صفحه پایان.

جواب‌ها سمت سرور بررسی می‌شوند (POST با htmx) و جواب درست تا کاربر جواب نداده به مرورگر نمی‌رود.
جواب‌های درس در حال خواندن در نشست کوکی نگه داشته می‌شود؛ امتیاز، زنجیره و دانش فقط با پایان
درس در دیتابیس ثبت می‌شود (app.school_service). مسیر /learn مال مقاله‌های عمومی است.
"""

import math
from dataclasses import asdict
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from sqlalchemy.orm import Session

from app import school_service, services
from app.domain.school import CardLevel, lesson_xp
from app.school.content import find
from app.school.lessons import Card, Lesson, check
from app.web import strings as s
from app.web.common import Db, LoggedIn, page, read_form, redirect, toast
from app.web.render import tehran_today

ATTEMPT_KEY = "school_attempt"
RESULT_KEY = "school_result"
NODE_GAP = 104  # فاصله عمودی گره‌های نقشه (پیکسل)
PATH_WIDTH = 300  # عرض viewBox مسیر


def _facts(request: Request, db: Session) -> school_service.DbFacts:
    return school_service.DbFacts(db, request.app.state.history_sources, tehran_today())


def _lesson_or_404(slug: str) -> Lesson:
    found = find(slug)
    if found is None:
        raise HTTPException(404)
    return found[2]


def _path_points(count: int) -> list[tuple[float, int]]:
    """گره‌های مسیر مارپیچ: (x در viewBox، y پیکسل)."""
    return [(round(PATH_WIDTH / 2 + math.sin(i * 1.15) * 84, 1), 52 + i * NODE_GAP)
            for i in range(count)]


def _curve(points: list[tuple[float, int]]) -> str:
    if not points:
        return ""
    d = f"M {points[0][0]} {points[0][1]}"
    for (ax, ay), (bx, by) in zip(points, points[1:], strict=False):
        mid = (ay + by) / 2
        d += f" C {ax} {mid}, {bx} {mid}, {bx} {by}"
    return d


def _level_dict(level: CardLevel | None) -> dict[str, int] | None:
    return None if level is None else asdict(level)


def register_school_routes(app: FastAPI) -> None:
    @app.get("/school", response_class=HTMLResponse, dependencies=[LoggedIn])
    def school_map(request: Request, db: Db) -> Response:
        today = tehran_today()
        view = school_service.overview(db, today)
        maps = []
        for course, station in view.stations:
            if not station.nodes:
                continue
            points = _path_points(len(station.nodes) + 1)  # + صندوقچه
            reached = [i for i, n in enumerate(station.nodes) if n.state != "lock"]
            lit = points[:(reached[-1] + 1 if reached else 1)]
            if station.complete:
                lit = points
            maps.append({"course": course, "station": station, "points": points,
                         "path": _curve(points), "lit": _curve(lit),
                         "height": points[-1][1] + 70})
        upcoming: dict[str, tuple[Any, list[Any]]] = {}
        for course, st in view.stations:
            if not st.nodes:
                upcoming.setdefault(course.key, (course, []))[1].append(st.station)
        return page(request, "school_map.html", {
            "active": "school", "view": view, "maps": maps, "upcoming": list(upcoming.values()),
            "width": PATH_WIDTH, "level": school_service.card_level(db)})

    @app.get("/school/lesson/{slug}", response_class=HTMLResponse, dependencies=[LoggedIn])
    def lesson_page(request: Request, db: Db, slug: str) -> Response:
        lesson = _lesson_or_404(slug)
        if not school_service.unlocked(db, slug):
            return redirect("/school")
        cards = lesson.cards(_facts(request, db))
        request.session[ATTEMPT_KEY] = {"slug": slug, "answers": {}}
        replay = slug in school_service.progress(db)
        questions = sum(card.graded for card in cards)
        return page(request, "school_lesson.html", {
            "active": "school", "lesson": lesson, "cards": cards, "replay": replay,
            "questions": questions, "max_xp": lesson_xp(questions, not replay)})

    @app.post("/school/lesson/{slug}/answer", response_class=HTMLResponse,
              dependencies=[LoggedIn])
    async def answer(request: Request, db: Db, slug: str) -> Response:
        lesson = _lesson_or_404(slug)
        form = await read_form(request)
        attempt = request.session.get(ATTEMPT_KEY) or {}
        if attempt.get("slug") != slug:
            return page(request, "_school_feedback.html", {"expired": True}, 409)
        cards = lesson.cards(_facts(request, db))
        index = form.get("card", "")
        if not index.isdecimal() or int(index) >= len(cards) or not cards[int(index)].graded:
            raise HTTPException(400)
        card: Card = cards[int(index)]
        result = check(card, form.get("answer", ""))
        if result is None:
            return page(request, "_school_feedback.html", {"invalid": True}, 400)
        answers: dict[str, bool] = attempt["answers"]
        first = answers.setdefault(index, result)  # فقط جواب اول هر کارت حساب می‌شود
        request.session[ATTEMPT_KEY] = {"slug": slug, "answers": answers}
        titles = s.SCHOOL["right_titles"].split("|")
        return page(request, "_school_feedback.html", {
            "card": card, "ok": result, "counted": first, "pick": form.get("answer", ""),
            "title": titles[sum(answers.values()) % len(titles)] if result
            else s.SCHOOL["wrong_title"]})

    @app.post("/school/lesson/{slug}/finish", dependencies=[LoggedIn])
    def finish(request: Request, db: Db, slug: str) -> Response:
        lesson = _lesson_or_404(slug)
        attempt = request.session.get(ATTEMPT_KEY) or {}
        cards = lesson.cards(_facts(request, db))
        graded = [str(i) for i, card in enumerate(cards) if card.graded]
        answers = attempt.get("answers", {}) if attempt.get("slug") == slug else {}
        if any(i not in answers for i in graded):
            toast(request, s.SCHOOL["not_finished"])
            return redirect(f"/school/lesson/{slug}")
        correct = sum(bool(answers[i]) for i in graded)
        result = school_service.finish(db, slug, correct, len(graded), tehran_today())
        db.commit()
        request.session.pop(ATTEMPT_KEY, None)
        data = asdict(result)
        data.update(slug=slug, level_before=_level_dict(result.level_before),
                    level_after=_level_dict(result.level_after))
        request.session[RESULT_KEY] = data
        return redirect(f"/school/lesson/{slug}/done")

    @app.get("/school/lesson/{slug}/done", response_class=HTMLResponse, dependencies=[LoggedIn])
    def done(request: Request, db: Db, slug: str) -> Response:
        lesson = _lesson_or_404(slug)
        result: dict[str, Any] | None = request.session.get(RESULT_KEY)
        if not result or result.get("slug") != slug:
            return redirect("/school")
        stored = services.load_persona(db)
        return page(request, "school_done.html", {
            "active": "school", "lesson": lesson, "r": result,
            "card_key": stored.card if stored else None,
            "leveled_up": bool(result["level_before"] and result["level_after"]
                               and result["level_after"]["level"]
                               > result["level_before"]["level"])})
