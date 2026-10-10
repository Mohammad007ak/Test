"""مدرسه وزیر: نقشه تاپیک‌ها (/school)، آزمون تعیین سطح، درس کارت‌به‌کارت و صفحه پایان.

جواب‌ها سمت سرور بررسی می‌شوند (POST با htmx) و جواب درست تا کاربر جواب نداده به مرورگر نمی‌رود.
جواب‌های درس در حال خواندن در نشست کوکی نگه داشته می‌شود؛ امتیاز، زنجیره و دانش فقط با پایان
درس در دیتابیس ثبت می‌شود (app.school_service). جواب غلط در درس تازه یک جان کم می‌کند (وزیر ویژه
بی‌نهایت). مسیر /learn مال مقاله‌های عمومی است.
"""

import math
from dataclasses import asdict
from datetime import timedelta

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from sqlalchemy.orm import Session

from app import school_service, services
from app.domain.money import to_persian_digits
from app.domain.school import CardLevel, lesson_xp, placement_level
from app.school.content import COURSES, LEVEL_NAMES, find
from app.school.content.placement import PLACEMENT, topic_of
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
    if slug == PLACEMENT.slug:
        return PLACEMENT
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


def wait_text(left: timedelta | None) -> str:
    """«۳ ساعت و ۱۲ دقیقه» تا جان بعدی."""
    if left is None:
        return ""
    minutes = max(1, math.ceil(left.total_seconds() / 60))
    hours, minutes = divmod(minutes, 60)
    parts = ([f"{hours} ساعت"] if hours else []) + ([f"{minutes} دقیقه"] if minutes else [])
    return to_persian_digits(" و ".join(parts))


def _map(station: school_service.StationView) -> dict[str, object]:
    points = _path_points(len(station.nodes) + 1)  # + صندوقچه
    reached = [i for i, n in enumerate(station.nodes) if n.state != "lock"]
    lit = points if station.complete else points[:(reached[-1] + 1 if reached else 1)]
    return {"station": station, "points": points, "path": _curve(points), "lit": _curve(lit),
            "height": points[-1][1] + 70}


def register_school_routes(app: FastAPI) -> None:
    @app.get("/school", response_class=HTMLResponse, dependencies=[LoggedIn])
    def school_map(request: Request, db: Db, t: str = "") -> Response:
        view = school_service.overview(db, tehran_today())
        chosen = view.course(t)
        if chosen is None:  # پیش‌فرض: تاپیک درس امروز
            chosen = next((c for c in view.courses
                           if view.next_lesson and c.next_lesson == view.next_lesson),
                          view.courses[0])
        return page(request, "school_map.html", {
            "active": "school", "view": view, "chosen": chosen,
            "maps": [_map(st) for st in chosen.stations], "width": PATH_WIDTH,
            "levels": LEVEL_NAMES, "wait": wait_text(view.hearts.next_in)})

    @app.get("/school/lesson/{slug}", response_class=HTMLResponse, dependencies=[LoggedIn])
    def lesson_page(request: Request, db: Db, slug: str) -> Response:
        lesson = _lesson_or_404(slug)
        placement = lesson is PLACEMENT
        node = None if placement else school_service.node(db, slug)
        if not placement and (node is None or not node.playable):
            return redirect("/school")
        replay = node is not None and node.state == "done"
        hearts = school_service.hearts(db)
        if not placement and not replay and hearts.empty:
            toast(request, s.SCHOOL["hearts_empty"].format(wait=wait_text(hearts.next_in)))
            return redirect("/school")
        cards = lesson.cards(_facts(request, db))
        request.session[ATTEMPT_KEY] = {"slug": slug, "answers": {}}
        questions = sum(card.graded for card in cards)
        return page(request, "school_lesson.html", {
            "active": "school", "lesson": lesson, "cards": cards, "replay": replay,
            "placement": placement, "hearts": None if placement or replay else hearts,
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
        first_time = index not in answers
        answers.setdefault(index, result)  # فقط جواب اول هر کارت حساب می‌شود
        request.session[ATTEMPT_KEY] = {"slug": slug, "answers": answers}
        hearts = None
        if lesson is not PLACEMENT and slug not in school_service.progress(db):
            hearts = school_service.hearts(db)
            if first_time and not result:
                hearts = school_service.lose_heart(db)
                db.commit()
        titles = s.SCHOOL["right_titles"].split("|")
        return page(request, "_school_feedback.html", {
            "card": card, "ok": result, "counted": answers[index], "pick": form.get("answer", ""),
            "hearts": hearts, "out": hearts is not None and hearts.empty,
            "wait": wait_text(hearts.next_in) if hearts else "",
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
        request.session.pop(ATTEMPT_KEY, None)
        if lesson is PLACEMENT:
            return _finish_placement(request, db, answers)
        correct = sum(bool(answers[i]) for i in graded)
        result = school_service.finish(db, slug, correct, len(graded), tehran_today())
        db.commit()
        data = asdict(result)
        data.update(slug=slug, level_before=_level_dict(result.level_before),
                    level_after=_level_dict(result.level_after))
        request.session[RESULT_KEY] = data
        return redirect(f"/school/lesson/{slug}/done")

    def _finish_placement(request: Request, db: Session, answers: dict[str, bool]) -> Response:
        by_topic: dict[str, list[bool]] = {}
        for index, ok in sorted(answers.items(), key=lambda item: int(item[0])):
            by_topic.setdefault(topic_of(int(index))[0], []).append(bool(ok))
        chosen = {course.key: placement_level(tuple(by_topic.get(course.key, ())))
                  for course in COURSES}
        school_service.save_levels(db, chosen)
        db.commit()
        names = "، ".join(f"{c.title}: {LEVEL_NAMES[chosen[c.key]]}" for c in COURSES)
        toast(request, s.SCHOOL["placed"].format(levels=names))
        return redirect("/school")

    @app.post("/school/placement/skip", dependencies=[LoggedIn])
    def skip_placement(request: Request, db: Db) -> Response:
        school_service.save_levels(db, {course.key: 1 for course in COURSES})
        db.commit()
        return redirect("/school")

    @app.get("/school/lesson/{slug}/done", response_class=HTMLResponse, dependencies=[LoggedIn])
    def done(request: Request, db: Db, slug: str) -> Response:
        lesson = _lesson_or_404(slug)
        result = request.session.get(RESULT_KEY)
        if not result or result.get("slug") != slug:
            return redirect("/school")
        stored = services.load_persona(db)
        found = find(slug)
        return page(request, "school_done.html", {
            "active": "school", "lesson": lesson, "r": result,
            "course_key": found[0].key if found else "",
            "card_key": stored.card if stored else None,
            "leveled_up": bool(result["level_before"] and result["level_after"]
                               and result["level_after"]["level"]
                               > result["level_before"]["level"])})
