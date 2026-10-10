"""نقشه مدرسه: ۶ تاپیک، هر تاپیک سه سطح (مقدماتی، متوسط، پیشرفته) و در مجموع ۱۰۰ درس.

افزودن درس = افزودن به ایستگاه همان سطح؛ افزودن تاپیک = یک فایل تازه و یک خط در COURSES.
"""

from app.school.content import basics, basics_1, crypto, fxgold, loans, saving, stocks
from app.school.lessons import Course, Lesson, Station

LEVEL_NAMES = {1: "مقدماتی", 2: "متوسط", 3: "پیشرفته"}

COURSES: tuple[Course, ...] = (
    Course("basics", 1, "مالی پایه", (basics_1.STATION, basics.LEVEL_2, basics.LEVEL_3)),
    Course("loans", 2, "وام و قسط", (loans.LEVEL_1, loans.LEVEL_2, loans.LEVEL_3)),
    Course("saving", 3, "پس‌انداز و سرمایه‌گذاری",
           (saving.LEVEL_1, saving.LEVEL_2, saving.LEVEL_3)),
    Course("stocks", 4, "بورس", (stocks.LEVEL_1, stocks.LEVEL_2, stocks.LEVEL_3)),
    Course("crypto", 5, "کریپتو", (crypto.LEVEL_1, crypto.LEVEL_2, crypto.LEVEL_3)),
    Course("fxgold", 6, "ارز و طلا", (fxgold.LEVEL_1, fxgold.LEVEL_2, fxgold.LEVEL_3)),
)


def path() -> list[tuple[Course, Station, Lesson]]:
    """همه درس‌ها به ترتیب تاپیک و سطح."""
    return [(course, station, lesson) for course in COURSES for station in course.stations
            for lesson in station.lessons]


def find(slug: str) -> tuple[Course, Station, Lesson] | None:
    return next((item for item in path() if item[2].slug == slug), None)


def course(key: str) -> Course | None:
    return next((c for c in COURSES if c.key == key), None)
