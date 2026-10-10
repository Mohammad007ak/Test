"""ساختار درس‌های مدرسه وزیر: انواع کارت، داده‌هایی که کارت‌ها از کاربر و بازار می‌خواهند، بررسی جواب.

محتوای هر ایستگاه در app/school/content است. کارت‌ها تابعی از Facts هستند تا عددها (تورم تنظیم
کاربر، پس‌انداز خودش، قیمت واقعی بازار) هنگام نمایش حساب شوند، نه این‌که ثابت نوشته شوند.
"""

from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import date
from decimal import Decimal
from typing import Literal, Protocol

from app.domain.school import (
    Slider,
    check_choice,
    check_multi,
    check_number,
    check_quick,
    check_sequence,
    check_slider,
    shuffled,
)

Kind = Literal["intro", "choice", "truefalse", "slider", "market", "personal", "blank", "story",
               "match", "order", "number", "multi", "quick"]
GRADED: frozenset[str] = frozenset({"choice", "truefalse", "slider", "market", "personal",
                                    "blank", "story", "match", "order", "number", "multi",
                                    "quick"})
CHOICE_LIKE: frozenset[str] = frozenset({"choice", "truefalse", "market", "personal", "blank",
                                         "story"})
SAMPLE_CASH_TOMAN = 40_000_000
SAMPLE_SPEND_TOMAN = 20_000_000
MIN_PERSONAL_TOMAN = 1_000_000  # کمتر از این، عدد نمونه بهتر درس می‌دهد


@dataclass(frozen=True)
class Personal:
    """عدد خود کاربر، یا عدد نمونه (برچسب «نمونه» می‌خورد)."""

    toman: int
    sample: bool


@dataclass(frozen=True)
class RaceRow:
    key: str  # cash یا کلید قیمت
    final_toman: int


@dataclass(frozen=True)
class Race:
    """۱۰۰ میلیون در شروع بازه، در پایان بازه کجا چقدر شد (قیمت واقعی تاریخی)."""

    start: date
    end: date
    amount_toman: int
    rows: tuple[RaceRow, ...]
    live: bool  # از تاریخچه قیمت اپ؛ False یعنی داده ذخیره‌شده

    @property
    def winner(self) -> int:
        return max(range(len(self.rows)), key=lambda i: self.rows[i].final_toman)


class Facts(Protocol):
    @property
    def inflation(self) -> Decimal: ...

    @property
    def cash(self) -> Personal: ...

    @property
    def monthly_spend(self) -> Personal: ...

    @property
    def race(self) -> Race: ...


@dataclass(frozen=True)
class Card:
    kind: Kind
    kicker: str
    text: str  # *واژه* پررنگ می‌شود
    sub: str = ""
    options: tuple[str, ...] = ()
    correct: int | None = None
    slider: Slider | None = None
    slider_unit_toman: int = 0  # نمایش زنده: مقدار × این مبلغ
    good: str = ""
    bad: str = ""
    note: str = ""
    sample: bool = False
    art: str = ""  # bill: اسکناس آب‌شونده
    bars: tuple[tuple[str, int], ...] = ()  # نوارهای intro: (برچسب، تومان)
    race: Race | None = None
    mood: str = "think"
    story: str = ""  # سناریو: ماجرایی که سؤال درباره‌اش است
    pairs: tuple[tuple[str, str], ...] = ()  # جفت‌کردن: (اصطلاح، معنا)
    items: tuple[str, ...] = ()  # مرتب‌کردن: به ترتیب درست
    number: Decimal | None = None  # حساب کن: جواب درست
    tolerance: Decimal = Decimal("0.02")
    unit: str = ""
    rights: frozenset[int] = frozenset()  # چندانتخابی
    statements: tuple[tuple[str, bool], ...] = ()  # دور سریع
    seconds: int = 0  # دور سریع: وقت
    seed: str = ""  # ترتیب ثابت نمایش (slug:شماره کارت)

    @property
    def graded(self) -> bool:
        return self.kind in GRADED

    @property
    def order(self) -> tuple[int, ...]:
        """ترتیب نمایش ستون معناها (جفت‌کردن) یا گزینه‌ها (مرتب‌کردن)."""
        count = len(self.pairs) or len(self.items)
        return shuffled(count, self.seed or self.text)

    @property
    def shown(self) -> list[tuple[int, str]]:
        """(شماره نمایش، متن) برای جفت‌کردن و مرتب‌کردن؛ شماره همان چیزی است که فرم می‌فرستد."""
        texts = [right for _left, right in self.pairs] or list(self.items)
        return [(j, texts[i]) for j, i in enumerate(self.order)]

    @property
    def expected(self) -> tuple[int, ...]:
        return tuple(self.order.index(i) for i in range(len(self.order)))


def check(card: Card, answer: str) -> bool | None:
    """True/False برای جواب، None برای جواب نامعتبر یا کارت بدون سؤال."""
    if card.kind == "slider" and card.slider is not None:
        return check_slider(card.slider, answer)
    if card.kind in ("match", "order"):
        return check_sequence(card.expected, answer)
    if card.kind == "number" and card.number is not None:
        return check_number(card.number, card.tolerance, answer)
    if card.kind == "multi":
        return check_multi(card.rights, len(card.options), answer)
    if card.kind == "quick":
        return check_quick(tuple(truth for _s, truth in card.statements), answer)
    if card.kind in CHOICE_LIKE and card.correct is not None:
        return check_choice(card.correct, len(card.options), answer)
    return None


@dataclass(frozen=True)
class Lesson:
    slug: str
    title: str
    icon: str
    summary: str
    build: Callable[[Facts], list[Card]]

    def cards(self, facts: Facts) -> list[Card]:
        return [replace(card, seed=f"{self.slug}:{i}") for i, card in enumerate(self.build(facts))]


@dataclass(frozen=True)
class Station:
    """هر تاپیک سه ایستگاه دارد: سطح ۱ مقدماتی، ۲ متوسط، ۳ پیشرفته."""

    key: str
    number: int
    title: str
    lessons: tuple[Lesson, ...] = ()
    finale: str = ""  # پیام صندوقچه پایان ایستگاه


@dataclass(frozen=True)
class Course:
    key: str
    number: int
    title: str
    stations: tuple[Station, ...] = field(default_factory=tuple)
