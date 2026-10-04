"""پرسونای مالی: از جواب‌های مصاحبه، امتیاز ریسک و کارت شخصیت می‌سازد.

ریسک‌پذیری دو جزء دارد و کمترشان ملاک است (روش رایج مشاوران مالی):
- تمایل (tolerance): واکنش به افت، انتخاب بین سود قطعی و احتمالی، تجربه.
- توان (capacity): سن، افق زمانی، ثبات درآمد، صندوق اضطراری، تعداد نان‌خورها.
همه امتیازها int بین ۰ و ۱۰۰ است. متن فارسی سؤال‌ها و کارت‌ها در strings.py است؛
انتخاب کارت در persona_cards.py.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class Question:
    key: str
    options: tuple[str, ...]
    multi: bool = False  # چندانتخابی و اختیاری


QUESTIONS: tuple[Question, ...] = (
    Question("age", ("u25", "25_34", "35_44", "45_54", "55p")),
    Question("job", ("employee", "freelancer", "business", "student", "retired", "between")),
    Question("income", ("fixed", "mostly", "variable", "none")),
    Question("household", ("single", "couple", "kids", "supports")),
    Question("housing", ("renter", "owner", "family")),
    Question("goal", ("home", "car", "emergency", "retire", "migrate", "inflation", "debt",
                      "growth")),
    Question("horizon", ("lt1", "1_3", "3_7", "gt7")),
    Question("drop", ("sell", "wait", "buy")),
    Question("choice", ("sure", "coin", "moon")),
    Question("experience", ("none", "safe", "market", "advanced")),
    Question("style", ("frugal", "balanced", "spender")),
    Question("emergency", ("none", "lt3", "3_6", "gt6")),
    Question("interests", ("gold", "fx", "stocks", "crypto", "property", "deposit"), multi=True),
    Question("tone", ("simple", "detailed", "blunt")),
)
_BY_KEY = {q.key: q for q in QUESTIONS}

# (وزن از ۱۰۰، امتیاز هر گزینه از ۱۰۰)
_TOLERANCE: dict[str, tuple[int, dict[str, int]]] = {
    "drop": (40, {"sell": 0, "wait": 50, "buy": 100}),
    "choice": (35, {"sure": 0, "coin": 55, "moon": 100}),
    "experience": (25, {"none": 0, "safe": 30, "market": 70, "advanced": 100}),
}
_CAPACITY: dict[str, tuple[int, dict[str, int]]] = {
    "age": (25, {"u25": 100, "25_34": 85, "35_44": 65, "45_54": 40, "55p": 20}),
    "horizon": (30, {"lt1": 0, "1_3": 35, "3_7": 70, "gt7": 100}),
    "income": (20, {"fixed": 90, "mostly": 70, "variable": 40, "none": 10}),
    "emergency": (15, {"none": 10, "lt3": 45, "3_6": 80, "gt6": 100}),
    "household": (10, {"single": 100, "couple": 75, "kids": 45, "supports": 40}),
}
CONSERVATIVE_BELOW = 35
BOLD_FROM = 65
GAP = 25  # فاصله تمایل و توان که ارزش گفتن دارد


class PersonaError(ValueError):
    def __init__(self, missing: list[str]) -> None:
        super().__init__("جواب‌های ناقص: " + "، ".join(missing))
        self.missing = missing


@dataclass(frozen=True)
class Persona:
    answers: dict[str, object]
    tolerance: int
    capacity: int

    @property
    def risk(self) -> int:
        return min(self.tolerance, self.capacity)

    @property
    def profile(self) -> str:
        if self.risk < CONSERVATIVE_BELOW:
            return "conservative"
        return "bold" if self.risk >= BOLD_FROM else "balanced"

    @property
    def gap(self) -> str | None:
        """eager: تمایل به ریسک خیلی بیشتر از توان؛ shy: توان خیلی بیشتر از تمایل."""
        if self.tolerance - self.capacity >= GAP:
            return "eager"
        if self.capacity - self.tolerance >= GAP:
            return "shy"
        return None

    def get(self, key: str) -> str:
        value = self.answers.get(key)
        return value if isinstance(value, str) else ""

    @property
    def interests(self) -> list[str]:
        value = self.answers.get("interests")
        return [v for v in value if isinstance(v, str)] if isinstance(value, list) else []


def _score(answers: Mapping[str, object], table: dict[str, tuple[int, dict[str, int]]]) -> int:
    total = sum(weight * points.get(str(answers.get(key, "")), 0)
                for key, (weight, points) in table.items())
    return total // 100


def build_persona(answers: Mapping[str, object]) -> Persona:
    return Persona(dict(answers), _score(answers, _TOLERANCE), _score(answers, _CAPACITY))


# (وزن از ۱۰۰، امتیاز هر گزینه) برای سه ویژگی دیگر کارت
_DISCIPLINE: dict[str, tuple[int, dict[str, int]]] = {
    "style": (60, {"frugal": 95, "balanced": 60, "spender": 20}),
    "emergency": (40, {"none": 5, "lt3": 40, "3_6": 75, "gt6": 100}),
}
_PATIENCE: dict[str, tuple[int, dict[str, int]]] = {
    "horizon": (60, {"lt1": 10, "1_3": 40, "3_7": 70, "gt7": 95}),
    "drop": (40, {"sell": 10, "wait": 75, "buy": 90}),
}
_KNOWLEDGE: dict[str, tuple[int, dict[str, int]]] = {
    "experience": (100, {"none": 10, "safe": 35, "market": 70, "advanced": 95}),
}
STATS = ("risk", "discipline", "patience", "knowledge")


def stats(persona: Persona) -> dict[str, int]:
    """چهار ویژگی کارت: ریسک‌پذیری، انضباط مالی، صبر و دانش سرمایه‌گذاری (۰ تا ۱۰۰)."""
    a = persona.answers
    return {"risk": persona.risk, "discipline": _score(a, _DISCIPLINE),
            "patience": _score(a, _PATIENCE), "knowledge": _score(a, _KNOWLEDGE)}


def parse_answers(form: Mapping[str, str], multi: Sequence[str]) -> dict[str, object]:
    """فرم مصاحبه → جواب‌های معتبر؛ جواب ناموجود یا ناشناخته PersonaError می‌دهد."""
    answers: dict[str, object] = {}
    missing = []
    for question in QUESTIONS:
        if question.multi:
            answers[question.key] = [v for v in dict.fromkeys(multi) if v in question.options]
            continue
        value = form.get(question.key, "")
        if value in question.options:
            answers[question.key] = value
        else:
            missing.append(question.key)
    if missing:
        raise PersonaError(missing)
    return answers


def question(key: str) -> Question:
    return _BY_KEY[key]
