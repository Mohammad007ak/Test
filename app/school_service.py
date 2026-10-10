"""مدرسه وزیر: پیشرفت درس‌ها، امتیاز، زنجیره و دانش کاربر در دیتابیس؛ و داده‌هایی که کارت‌ها
از دارایی، خرج و تاریخچه قیمت می‌خواهند.

منطق خالص (امتیاز، زنجیره، سطح کارت) در app.domain.school است؛ محتوا در app.school.content.
داده شخصی فقط به‌صورت جمع (موجودی نقد، خرج ماهانه) به کارت‌ها می‌رسد و جایی بیرون نمی‌رود.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from functools import cached_property

import jdatetime
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import price_history, services
from app.adapters.prices.history import HistorySource
from app.domain import school
from app.domain.persona import stats as persona_stats
from app.domain.spending import TEHRAN, shift_month
from app.models import LessonProgress, SchoolStats, utcnow
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
        row = SchoolStats(xp=0, knowledge=0, streak=0, best_streak=0)
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
    state: str  # done، now، lock
    best_correct: int = 0


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
class Overview:
    xp: int
    streak: int
    best_streak: int
    week: list[str]
    stations: list[tuple[Course, StationView]]
    next_lesson: Lesson | None  # درس امروز: اولین درس تمام‌نشده
    completed: int
    total: int


def overview(db: Session, today: date) -> Overview:
    """نقشه مسیر: هر درس تمام‌شده باز است؛ اولین تمام‌نشده «حالا»؛ بقیه قفل."""
    done = progress(db)
    row = db.scalars(select(SchoolStats)).first()
    streak = _streak(row) if row else school.Streak()
    stations: list[tuple[Course, StationView]] = []
    next_lesson: Lesson | None = None
    for course in COURSES:
        for station in course.stations:
            nodes = []
            for lesson in station.lessons:
                record = done.get(lesson.slug)
                if record is not None:
                    nodes.append(Node(lesson, "done", record.best_correct))
                elif next_lesson is None:
                    next_lesson = lesson
                    nodes.append(Node(lesson, "now"))
                else:
                    nodes.append(Node(lesson, "lock"))
            stations.append((course, StationView(station, tuple(nodes))))
    lessons = path()
    return Overview(
        xp=row.xp if row else 0, streak=school.current_streak(streak, today),
        best_streak=streak.best, week=school.week_marks(streak, today), stations=stations,
        next_lesson=next_lesson, completed=sum(1 for *_x, lesson in lessons
                                               if lesson.slug in done),
        total=len(lessons))


def unlocked(db: Session, slug: str) -> bool:
    """درسی باز است که تمام شده باشد یا درس قبلی‌اش در مسیر تمام شده باشد."""
    done = progress(db)
    slugs = [lesson.slug for *_x, lesson in path()]
    if slug not in slugs:
        return False
    i = slugs.index(slug)
    return slug in done or i == 0 or slugs[i - 1] in done


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
