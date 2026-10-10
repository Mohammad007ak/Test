"""ساختار درس‌های مدرسه وزیر: انواع کارت، داده‌هایی که کارت‌ها از کاربر و بازار می‌خواهند، بررسی جواب.

محتوای هر ایستگاه در app/school/content است. کارت‌ها تابعی از Facts هستند تا عددها (تورم تنظیم
کاربر، پس‌انداز خودش، قیمت واقعی بازار) هنگام نمایش حساب شوند، نه این‌که ثابت نوشته شوند.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Literal, Protocol

from app.domain.school import Slider, check_choice, check_slider

Kind = Literal["intro", "choice", "truefalse", "slider", "market", "personal"]
GRADED: frozenset[str] = frozenset({"choice", "truefalse", "slider", "market", "personal"})
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

    @property
    def graded(self) -> bool:
        return self.kind in GRADED


def check(card: Card, answer: str) -> bool | None:
    """True/False برای جواب، None برای جواب نامعتبر یا کارت بدون سؤال."""
    if card.kind == "slider" and card.slider is not None:
        return check_slider(card.slider, answer)
    if card.graded and card.correct is not None:
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
        return self.build(facts)


@dataclass(frozen=True)
class Station:
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
