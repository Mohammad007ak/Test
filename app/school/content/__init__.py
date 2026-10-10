"""نقشه دوره‌ها و ایستگاه‌ها. فعلاً فقط دوره ۱، ایستگاه ۱ درس دارد؛ بقیه فقط عنوان‌اند تا
افزودن دوره تازه فقط افزودن محتوا باشد."""

from app.school.content import basics_1
from app.school.lessons import Course, Lesson, Station


def _soon(course: str, titles: tuple[str, ...], first: Station | None = None) -> tuple[
        Station, ...]:
    stations = [first] if first else []
    stations += [Station(f"{course}-{n}", n, title)
                 for n, title in enumerate(titles, start=len(stations) + 1)]
    return tuple(stations)


COURSES: tuple[Course, ...] = (
    Course("basics", 1, "مالی مقدماتی", _soon(
        "basics", ("بودجه‌بندی", "خرج‌های پنهان", "صندوق اضطراری", "هدف‌گذاری"),
        basics_1.STATION)),
    Course("loans", 2, "وام گرفتن", _soon(
        "loans", ("انواع وام", "نرخ اسمی و مؤثر", "قسط چقدر زیاد است؟", "خرید اقساطی",
                  "ضامن و قرارداد"))),
    Course("saving", 3, "پس‌انداز و سرمایه‌گذاری", _soon(
        "saving", ("سپرده و سود واقعی", "طلا و سکه", "ریسک و تنوع", "بلندمدت"))),
    Course("stocks", 4, "بورس", _soon(
        "stocks", ("سهام", "صندوق‌ها", "خرید و فروش", "هیجان و ضرر", "تحلیل ساده"))),
    Course("crypto", 5, "کریپتو", _soon(
        "crypto", ("بلاکچین ساده", "بیت‌کوین و تتر", "کیف پول و امنیت", "کلاهبرداری‌ها",
                   "اندازه سرمایه"))),
    Course("fx", 6, "بازار ارز", _soon(
        "fx", ("چرا دلار تغییر می‌کند", "ارز سفر", "ریسک اسکناس", "مقایسه با طلا"))),
)


def path() -> list[tuple[Course, Station, Lesson]]:
    """همه درس‌های آماده به ترتیب مسیر."""
    return [(course, station, lesson) for course in COURSES for station in course.stations
            for lesson in station.lessons]


def find(slug: str) -> tuple[Course, Station, Lesson] | None:
    return next((item for item in path() if item[2].slug == slug), None)
