"""سازنده‌های کوتاه برای نوشتن محتوای ثابت درس‌ها (هر تابع یک نوع کارت).

`why` توضیحی است که بعد از جواب نشان داده می‌شود (درست یا غلط)؛ اگر دو متن جدا لازم است، good و
bad را مستقیم بده. *واژه* در متن پررنگ می‌شود.
"""

from decimal import Decimal

from app.domain.money import format_number
from app.school.lessons import Card, Facts, Lesson

TRUE_FALSE = ("👍 درسته", "👎 غلطه")
NOT_ADVICE = "آموزشی است، نه توصیه خرید."


def _why(why: str, good: str, bad: str, fallback: str = "") -> tuple[str, str]:
    """توضیح جواب؛ اگر نوشته نشده، خود جواب درست نشان داده می‌شود."""
    return good or why or fallback, bad or why or fallback


def _answer(text: str) -> str:
    return f"جواب درست: «{text}»."


def intro(text: str, sub: str = "", kicker: str = "بیا یاد بگیریم", note: str = "",
          mood: str = "idle") -> Card:
    return Card("intro", kicker, text, sub=sub, note=note, mood=mood)


def choice(text: str, options: tuple[str, ...], correct: int, why: str = "",
           kicker: str = "یه سؤال", note: str = "", good: str = "", bad: str = "") -> Card:
    g, b = _why(why, good, bad, _answer(options[correct]))
    return Card("choice", kicker, text, options=options, correct=correct, good=g, bad=b,
                note=note)


def tf(text: str, truth: bool, why: str = "", kicker: str = "درسته یا غلط؟", note: str = "",
       good: str = "", bad: str = "") -> Card:
    g, b = _why(why, good, bad, "این جمله درسته." if truth else "این جمله غلطه.")
    return Card("truefalse", kicker, text, options=TRUE_FALSE, correct=0 if truth else 1,
                good=g, bad=b, note=note)


def blank(text: str, options: tuple[str, ...], correct: int, why: str = "",
          kicker: str = "جای خالی رو پر کن") -> Card:
    """متن با «___» برای جای خالی."""
    why = why or _answer(text.replace("___", options[correct]))
    return Card("blank", kicker, text, options=options, correct=correct, good=why, bad=why)


def story(scene: str, text: str, options: tuple[str, ...], correct: int, why: str = "",
          kicker: str = "داستان", note: str = "") -> Card:
    why = why or _answer(options[correct])
    return Card("story", kicker, text, story=scene, options=options, correct=correct,
                good=why, bad=why, note=note)


def match(text: str, pairs: tuple[tuple[str, str], ...], why: str = "",
          kicker: str = "بازی جفت‌ها") -> Card:
    why = why or "جفت‌های درست: " + "؛ ".join(f"{a} ← {b}" for a, b in pairs) + "."
    return Card("match", kicker, text, pairs=pairs, good=why, bad=why)


def order(text: str, items: tuple[str, ...], why: str = "", kicker: str = "مرتب کن") -> Card:
    """items به ترتیب درست؛ نمایش به هم ریخته است."""
    why = why or "ترتیب درست: " + " ← ".join(items) + "."
    return Card("order", kicker, text, items=items, good=why, bad=why)


def number(text: str, answer: str | int, why: str = "", unit: str = "",
           tolerance: str = "0.02", kicker: str = "حساب کن", note: str = "") -> Card:
    value = Decimal(answer)
    shown = format_number(value, 1).removesuffix("٫۰")
    why = why or f"جواب درست: {shown} {unit}".strip() + "."
    return Card("number", kicker, text, number=value, tolerance=Decimal(tolerance),
                unit=unit, good=why, bad=why, note=note)


def multi(text: str, options: tuple[str, ...], rights: tuple[int, ...], why: str = "",
          kicker: str = "همه درست‌ها رو انتخاب کن", note: str = "") -> Card:
    why = why or "جواب‌های درست: " + "، ".join(f"«{options[r]}»" for r in rights) + "."
    return Card("multi", kicker, text, options=options, rights=frozenset(rights), good=why,
                bad=why, note=note)


def quick(statements: tuple[tuple[str, bool], ...], why: str = "", seconds: int = 25,
          text: str = "درسته یا غلط؟ تا وقت تموم نشده جواب بده!",
          kicker: str = "دور سریع ⚡") -> Card:
    why = why or "درست‌ها: " + "؛ ".join(s for s, truth in statements if truth) + "."
    return Card("quick", kicker, text, statements=statements, seconds=seconds, good=why,
                bad=why)


def lesson(slug: str, title: str, icon: str, summary: str, *cards: Card) -> Lesson:
    """درس با کارت‌های ثابت (بی‌نیاز از داده کاربر)."""
    fixed = list(cards)

    def build(_facts: Facts) -> list[Card]:
        return list(fixed)

    return Lesson(slug, title, icon, summary, build)
