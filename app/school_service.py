"""مدرسه وزیر: پیشرفت درس‌ها، امتیاز، زنجیره و دانش کاربر در دیتابیس؛ و داده‌هایی که کارت‌ها
از دارایی، خرج و تاریخچه قیمت می‌خواهند.

منطق خالص (امتیاز، زنجیره، سطح کارت) در app.domain.school است؛ محتوا در app.school.content.
داده شخصی فقط به‌صورت جمع (موجودی نقد، خرج ماهانه) به کارت‌ها می‌رسد و جایی بیرون نمی‌رود.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from functools import cached_property

import jdatetime
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import price_history, services
from app.adapters.prices.history import HistorySource
from app.db import NOBODY, USER_KEY
from app.domain import school
from app.domain.persona import stats as persona_stats
from app.domain.spending import TEHRAN, shift_month
from app.models import LessonProgress, SchoolStats, User, utcnow
from app.school.content import COURSES, find, path
from app.school.lessons import (
    MIN_PERSONAL_TOMAN,
    SAMPLE_CASH_TOMAN,
    SAMPLE_SPEND_TOMAN,
    Course,
    Lesson,
    Personal,
    Race,
    RaceRow,
    Station,
)

RACE_AMOUNT_TOMAN = 100_000_000
RACE_YEARS = 3
RACE_KEYS = ("usd", "coin_emami", "gold18_gram")
# آخرین داده واقعی ذخیره‌شده (الان‌چند، store/video/reel_data.py) برای وقتی که تاریخچه قیمت اپ
# هنوز سه سال را پوشش نمی‌دهد: (قیمت شروع، قیمت پایان)
SAVED_RACE_DAYS = (date(2023, 10, 4), date(2026, 10, 4))
SAVED_RACE_PRICES: dict[str, tuple[int, int]] = {
    "usd": (49_650, 269_900),
    "coin_emami": (27_250_000, 271_000_000),
    "gold18_gram": (2_241_100, 26_443_970),
}


def _race(start: date, end: date, prices: dict[str, tuple[Decimal, Decimal]],
          live: bool) -> Race:
    rows = [RaceRow("cash", RACE_AMOUNT_TOMAN)]
    rows += [RaceRow(key, school.grow(RACE_AMOUNT_TOMAN, *prices[key])) for key in RACE_KEYS]
    return Race(start, end, RACE_AMOUNT_TOMAN, tuple(rows), live)


SAVED_RACE = _race(*SAVED_RACE_DAYS, {k: (Decimal(a), Decimal(b))
                                      for k, (a, b) in SAVED_RACE_PRICES.items()}, live=False)


class DbFacts:
    """داده‌های درس از دیتابیس کاربر؛ هر کدام فقط اگر درسی لازمش داشت حساب می‌شود."""

    def __init__(self, db: Session, history_sources: Sequence[HistorySource] = (),
                 today: date | None = None) -> None:
        self.db = db
        self.history_sources = history_sources
        self.today = today or datetime.now(TEHRAN).date()

    @cached_property
    def inflation(self) -> Decimal:
        return school.lesson_inflation(services.get_decimal_setting(self.db, "inflation"))

    @cached_property
    def _portfolio(self) -> services.Portfolio:
        return services.build_portfolio(self.db)

    @cached_property
    def cash(self) -> Personal:
        """نقد: موجودی حساب‌ها و دارایی «پول نقد»."""
        p = self._portfolio
        total = sum(a.balance_toman for a in p.accounts)
        total += sum(line.value_toman or 0 for line in p.assets if line.asset.kind == "cash")
        return _personal(total, SAMPLE_CASH_TOMAN)

    @cached_property
    def monthly_spend(self) -> Personal:
        """خرج ماهانه: بیشترِ خرج ماه گذشته و هزینه‌های ثابت به‌علاوه اقساط."""
        j = jdatetime.date.fromgregorian(date=self.today)
        last_month = services.month_spending(self.db, *shift_month(j.year, j.month, -1))
        p = self._portfolio
        fixed = p.monthly_fixed_expenses_toman + p.monthly_installments_toman
        return _personal(max(last_month.total_toman, fixed), SAMPLE_SPEND_TOMAN)

    @cached_property
    def race(self) -> Race:
        prices: dict[str, tuple[Decimal, Decimal]] = {}
        series = {}
        for key in RACE_KEYS:
            if self.history_sources:
                price_history.refresh(self.db, key, self.history_sources)
            series[key] = price_history.series(self.db, key)
        if not all(series.values()):
            return SAVED_RACE
        end = min(points[-1][0] for points in series.values())
        start = school.years_before(end, RACE_YEARS)
        for key, points in series.items():
            first, last = school.price_on(points, start), school.price_on(points, end)
            if not first or not last:
                return SAVED_RACE
            prices[key] = (first, last)
        return _race(start, end, prices, live=True)


def _personal(toman: int, sample: int) -> Personal:
    return Personal(toman, False) if toman >= MIN_PERSONAL_TOMAN else Personal(sample, True)


# ---------- پیشرفت ----------

def load_stats(db: Session) -> SchoolStats:
    row = db.scalars(select(SchoolStats)).first()
    if row is None:
        row = SchoolStats(xp=0, knowledge=0, streak=0, best_streak=0,
                          hearts=school.MAX_HEARTS, levels="")
        db.add(row)
    return row


def _streak(row: SchoolStats) -> school.Streak:
    return school.Streak(row.streak, row.best_streak, row.last_day, row.freeze_day)


def progress(db: Session) -> dict[str, LessonProgress]:
    return {p.lesson_slug: p for p in db.scalars(select(LessonProgress))}


def base_knowledge(db: Session) -> int | None:
    """دانش کارت شخصیت از پرسونا؛ None اگر کاربر هنوز کارت ندارد."""
    stored = services.load_persona(db)
    return None if stored is None else persona_stats(stored.persona)["knowledge"]


def card_level(db: Session, bonus: int | None = None) -> school.CardLevel | None:
    base = base_knowledge(db)
    if base is None:
        return None
    if bonus is None:
        row = db.scalars(select(SchoolStats)).first()
        bonus = row.knowledge if row else 0
    return school.card_level(base, bonus)


@dataclass(frozen=True)
class Node:
    lesson: Lesson
    state: str  # done، now، open (سطح پایین‌تر از سطح شروع، برای مرور)، lock
    best_correct: int = 0

    @property
    def playable(self) -> bool:
        return self.state != "lock"


@dataclass(frozen=True)
class StationView:
    station: Station
    nodes: tuple[Node, ...]

    @property
    def done(self) -> int:
        return sum(n.state == "done" for n in self.nodes)

    @property
    def complete(self) -> bool:
        return bool(self.nodes) and self.done == len(self.nodes)


@dataclass(frozen=True)
class CourseView:
    course: Course
    stations: tuple[StationView, ...]
    start_level: int  # از آزمون تعیین سطح؛ ۱ اگر آزمون نداده

    @property
    def next_lesson(self) -> Lesson | None:
        return next((n.lesson for s in self.stations for n in s.nodes if n.state == "now"), None)

    @property
    def done(self) -> int:
        return sum(s.done for s in self.stations)

    @property
    def total(self) -> int:
        return sum(len(s.nodes) for s in self.stations)


@dataclass(frozen=True)
class HeartsView:
    count: int
    premium: bool  # وزیر ویژه: جان بی‌نهایت
    next_in: timedelta | None

    @property
    def empty(self) -> bool:
        return not self.premium and self.count <= 0


@dataclass(frozen=True)
class Overview:
    xp: int
    streak: int
    best_streak: int
    week: list[str]
    courses: list[CourseView]
    next_lesson: Lesson | None  # درس امروز
    completed: int
    total: int
    placed: bool  # آزمون تعیین سطح داده شده
    hearts: HeartsView

    def course(self, key: str) -> CourseView | None:
        return next((c for c in self.courses if c.course.key == key), None)


def levels(row: SchoolStats | None) -> dict[str, int]:
    """«basics=2,loans=1» ← سطح شروع هر تاپیک."""
    out: dict[str, int] = {}
    for part in (row.levels if row else "").split(","):
        key, _, value = part.partition("=")
        if key and value.isdecimal() and 1 <= int(value) <= 3:
            out[key] = int(value)
    return out


def is_placed(db: Session) -> bool:
    return bool(levels(db.scalars(select(SchoolStats)).first()))


def save_levels(db: Session, chosen: dict[str, int]) -> None:
    row = load_stats(db)
    row.levels = ",".join(f"{key}={level}" for key, level in chosen.items())


def _course_view(course: Course, done: dict[str, LessonProgress], start: int) -> CourseView:
    found_now = False
    stations = []
    for station in course.stations:
        nodes = []
        for lesson in station.lessons:
            record = done.get(lesson.slug)
            if record is not None:
                nodes.append(Node(lesson, "done", record.best_correct))
            elif station.number < start:
                nodes.append(Node(lesson, "open"))
            elif not found_now:
                found_now = True
                nodes.append(Node(lesson, "now"))
            else:
                nodes.append(Node(lesson, "lock"))
        stations.append(StationView(station, tuple(nodes)))
    return CourseView(course, tuple(stations), start)


def is_premium(db: Session, now: datetime | None = None) -> bool:
    user = db.get(User, db.info.get(USER_KEY, NOBODY))
    until = user.premium_until if user else None
    return until is not None and until > (now or utcnow())


def _hearts(row: SchoolStats | None) -> school.Hearts:
    if row is None:
        return school.Hearts(school.MAX_HEARTS, None)
    return school.Hearts(row.hearts, row.hearts_since)


def hearts(db: Session, now: datetime | None = None) -> HeartsView:
    now = now or utcnow()
    current = school.hearts_now(_hearts(db.scalars(select(SchoolStats)).first()), now)
    return HeartsView(current.count, is_premium(db, now), school.next_heart_in(current, now))


def lose_heart(db: Session, now: datetime | None = None) -> HeartsView:
    """جواب غلط در درس تازه؛ وزیر ویژه جان از دست نمی‌دهد."""
    now = now or utcnow()
    if not is_premium(db, now):
        row = load_stats(db)
        h = school.lose_heart(_hearts(row), now)
        row.hearts, row.hearts_since = h.count, h.since
        db.flush()
    return hearts(db, now)


def _gain_heart(row: SchoolStats, now: datetime) -> None:
    h = school.gain_heart(_hearts(row), now)
    row.hearts, row.hearts_since = h.count, h.since


def overview(db: Session, today: date, now: datetime | None = None) -> Overview:
    """نقشه همه تاپیک‌ها: هر تاپیک از سطح شروع خودش پیش می‌رود؛ سطح‌های پایین‌تر برای مرور باز."""
    done = progress(db)
    row = db.scalars(select(SchoolStats)).first()
    streak = _streak(row) if row else school.Streak()
    start = levels(row)
    courses = [_course_view(course, done, start.get(course.key, 1)) for course in COURSES]
    lessons = path()
    return Overview(
        xp=row.xp if row else 0, streak=school.current_streak(streak, today),
        best_streak=streak.best, week=school.week_marks(streak, today), courses=courses,
        next_lesson=next((c.next_lesson for c in courses if c.next_lesson), None),
        completed=sum(1 for *_x, lesson in lessons if lesson.slug in done),
        total=len(lessons), placed=bool(start), hearts=hearts(db, now))


def node(db: Session, slug: str) -> Node | None:
    found = find(slug)
    if found is None:
        return None
    row = db.scalars(select(SchoolStats)).first()
    view = _course_view(found[0], progress(db), levels(row).get(found[0].key, 1))
    return next(n for s in view.stations for n in s.nodes if n.lesson.slug == slug)


def unlocked(db: Session, slug: str) -> bool:
    found = node(db, slug)
    return found is not None and found.playable


@dataclass(frozen=True)
class Result:
    xp: int  # امتیاز همین درس (با صندوقچه)
    chest_xp: int
    first_time: bool
    correct: int
    questions: int
    streak: int
    streak_grew: bool
    total_xp: int
    knowledge_gain: int
    level_before: school.CardLevel | None
    level_after: school.CardLevel | None
    station_finale: str  # فقط وقتی همین درس ایستگاه را کامل کرد


def finish(db: Session, slug: str, correct: int, questions: int, today: date) -> Result:
    """پایان درس: امتیاز، زنجیره روز تهران، دانش کارت و صندوقچه ایستگاه (یک بار)."""
    found = find(slug)
    if found is None:
        raise KeyError(slug)
    course, station, _lesson = found
    stats = load_stats(db)
    record = progress(db).get(slug)
    first_time = record is None
    before = card_level(db, stats.knowledge)
    if record is None:
        record = LessonProgress(lesson_slug=slug, course=course.key, best_correct=correct,
                                attempts=1, completed_at=utcnow())
        db.add(record)
        stats.knowledge += school.KNOWLEDGE_PER_LESSON
    else:
        record.attempts += 1
        record.best_correct = max(record.best_correct, correct)
    db.flush()
    finale = ""
    chest = 0
    if first_time and all(lesson.slug in progress(db) for lesson in station.lessons):
        chest, finale = school.CHEST_XP, station.finale
    if not first_time:  # مرور درس تمام‌شده یک جان برمی‌گرداند
        _gain_heart(stats, utcnow())
    xp = school.lesson_xp(correct, first_time)
    old_count = stats.streak if school.current_streak(_streak(stats), today) else 0
    streak = school.record_day(_streak(stats), today)
    stats.streak, stats.best_streak = streak.count, streak.best
    stats.last_day, stats.freeze_day = streak.last_day, streak.freeze_day
    stats.xp += xp + chest
    return Result(
        xp=xp + chest, chest_xp=chest, first_time=first_time, correct=correct,
        questions=questions, streak=streak.count, streak_grew=streak.count > old_count,
        total_xp=stats.xp,
        knowledge_gain=school.KNOWLEDGE_PER_LESSON if first_time else 0,
        level_before=before, level_after=card_level(db, stats.knowledge),
        station_finale=finale)
