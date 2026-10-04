"""مصاحبه پرسونا با هوش مصنوعی: وزیر سؤال‌ها را خودش و شخصی‌شده می‌پرسد.

هر نوبت، مدل یا با ask_user سؤال بعدی و چند جواب پیشنهادی می‌دهد (کاربر می‌تواند خودش
هم بنویسد)، یا وقتی همه چیز را فهمید با save_persona جواب‌ها را در قالب ثابت دامنه
(app.domain.persona) تحویل می‌دهد. امتیاز ریسک و کارت را کد تست‌شده حساب می‌کند، نه مدل.
"""

import json
from dataclasses import dataclass, field
from typing import Any

from app.assistant.client import AssistantError, ChatModel
from app.domain.persona import QUESTIONS, PersonaError, parse_answers
from app.web import strings as s

MAX_ROUNDS = 3
MAX_SUGGESTIONS = 5
MAX_QUESTION_CHARS = 400
MAX_SUGGESTION_CHARS = 60


@dataclass
class Turn:
    question: str = ""
    suggestions: list[str] = field(default_factory=list)
    answers: dict[str, object] | None = None  # پر = مصاحبه تمام شد
    summary: str = ""
    notes: str = ""


def _field_guide() -> str:
    lines = []
    for q in QUESTIONS:
        text, options = s.PERSONA_QUESTIONS[q.key]
        choices = "، ".join(f"{key}={label}" for key, label in options.items())
        many = " (چندانتخابی، می‌تواند خالی باشد)" if q.multi else ""
        lines.append(f"- {q.key}{many}: {text} ← {choices}")
    return "\n".join(lines)


SYSTEM = """تو «وزیر» هستی، وزیر مالی شخصی کاربر در اپ وزیر. داری برای اولین بار با کاربر آشنا
می‌شوی تا پرسونای مالی‌اش را بسازی. مثل یک دوست باهوش و خوش‌برخورد حرف بزن: فارسی
خودمانی، گرم، کوتاه و کمی شوخ.

روش کار:
- هر بار فقط یک سؤال بپرس (حداکثر دو سؤال کوتاه و نزدیک به هم). سؤال را با ابزار ask_user
  بفرست و ۲ تا ۵ جواب پیشنهادی خیلی کوتاه بده؛ کاربر می‌تواند جواب خودش را هم بنویسد.
- سؤال‌ها را از روی جواب‌های قبلی شخصی کن؛ مثلاً اگر گفت فریلنسر است درباره نوسان درآمدش
  بپرس، اگر گفت بچه دارد درباره آینده آن‌ها. اگر از یک جواب چند مورد معلوم شد، دوباره نپرس.
- برای سنجیدن ریسک‌پذیری از سناریوی ملموس استفاده کن (مثلاً «سرمایه‌ات یک‌ماهه ۲۰٪ افت کرد،
  چه می‌کنی؟» یا انتخاب بین سود قطعی و سود احتمالی بیشتر).
- عدد دقیق حقوق، موجودی یا شماره حساب نپرس؛ لازم نیست.
- اگر جوابی مبهم بود یک بار با زبان ساده‌تر بپرس؛ اگر کاربر نخواست جواب بدهد، نزدیک‌ترین
  گزینه را از حرف‌هایش برداشت کن.
- اگر کاربر از موضوع خارج شد، کوتاه و دوستانه جواب بده و برگرد سر مصاحبه.
- معمولاً بعد از ۸ تا ۱۲ سؤال همه چیز معلوم است. آن وقت save_persona را صدا بزن: هر مورد را
  به نزدیک‌ترین گزینه نگاشت کن، در summary دو سه جمله گرم و دقیق خطاب به خود کاربر («تو…»)
  بنویس که او را چطور شناختی، و نکته‌های مهم دیگر (برنامه‌ها، نگرانی‌ها، رویدادهای پیش رو)
  را در notes بگذار.

مواردی که باید بفهمی (کلید = معنای گزینه):
{fields}
"""


def system_prompt() -> str:
    return SYSTEM.format(fields=_field_guide())


def _save_tool() -> dict[str, Any]:
    properties: dict[str, Any] = {}
    required = []
    for q in QUESTIONS:
        enum = {"type": "string", "enum": list(q.options)}
        if q.multi:
            properties[q.key] = {"type": "array", "items": enum}
        else:
            properties[q.key] = enum
            required.append(q.key)
    properties["summary"] = {"type": "string",
                             "description": "دو سه جمله فارسی خطاب به کاربر درباره شخصیت مالی‌اش"}
    properties["notes"] = {"type": "string",
                           "description": "نکته‌های مهم دیگر از حرف‌های کاربر؛ خالی اگر نیست"}
    return {"type": "function", "function": {
        "name": "save_persona",
        "description": "وقتی همه موارد معلوم شد، پرسونای کاربر را ذخیره کن.",
        "parameters": {"type": "object", "properties": properties,
                       "required": [*required, "summary"], "additionalProperties": False}}}


TOOLS: list[dict[str, Any]] = [
    {"type": "function", "function": {
        "name": "ask_user",
        "description": "سؤال بعدی مصاحبه را با چند جواب پیشنهادی کوتاه بپرس.",
        "parameters": {"type": "object", "properties": {
            "question": {"type": "string"},
            "suggestions": {"type": "array", "items": {"type": "string"},
                            "description": "۲ تا ۵ جواب کوتاه پیشنهادی"},
        }, "required": ["question", "suggestions"], "additionalProperties": False}}},
    _save_tool(),
]


def _clip(text: Any, limit: int) -> str:
    return " ".join(str(text or "").split())[:limit]


def _ask(arguments: dict[str, Any]) -> Turn:
    raw = arguments.get("suggestions")
    suggestions = [_clip(x, MAX_SUGGESTION_CHARS) for x in raw] if isinstance(raw, list) else []
    return Turn(question=str(arguments.get("question") or "").strip()[:MAX_QUESTION_CHARS],
                suggestions=[x for x in dict.fromkeys(suggestions) if x][:MAX_SUGGESTIONS])


def _save(arguments: dict[str, Any]) -> Turn:
    """جواب‌ها با همان اعتبارسنجی فرم دامنه؛ مورد ناقص PersonaError می‌دهد تا مدل بپرسد."""
    single = {k: str(v) for k, v in arguments.items() if isinstance(v, str)}
    multi = [str(v) for q in QUESTIONS if q.multi
             for v in (arguments.get(q.key) or []) if isinstance(arguments.get(q.key), list)]
    answers = parse_answers(single, multi)
    return Turn(answers=answers, summary=str(arguments.get("summary") or "").strip(),
                notes=str(arguments.get("notes") or "").strip())


def turn(model: ChatModel, history: list[dict[str, str]], text: str) -> Turn:
    """یک نوبت مصاحبه: پیام کاربر (پوشانده‌شده) ← سؤال بعدی یا پرسونای کامل."""
    messages: list[dict[str, Any]] = [{"role": "system", "content": system_prompt()},
                                      *history, {"role": "user", "content": text}]
    for _ in range(MAX_ROUNDS):
        reply = model.complete(messages, TOOLS)
        calls = reply.get("tool_calls") or []
        if not calls:
            content = (reply.get("content") or "").strip()
            if not content:
                raise AssistantError("جوابی نگرفتم؛ دوباره بنویس.")
            return Turn(question=content[:MAX_QUESTION_CHARS * 2])
        messages.append({"role": "assistant", "content": reply.get("content"),
                         "tool_calls": calls})
        for call in calls:
            function = call.get("function", {})
            try:
                arguments = json.loads(function.get("arguments") or "{}")
                if not isinstance(arguments, dict):
                    raise ValueError
                if function.get("name") == "ask_user":
                    result = _ask(arguments)
                    if result.question:
                        return result
                    feedback = "question خالی است."
                elif function.get("name") == "save_persona":
                    return _save(arguments)
                else:
                    feedback = "ابزار ناشناخته."
            except PersonaError as exc:
                feedback = ("این موارد هنوز معلوم نیست یا گزینه نامعتبر است؛ از کاربر بپرس: "
                            + "، ".join(exc.missing))
            except (ValueError, TypeError):
                feedback = "آرگومان‌ها JSON معتبر نیست."
            messages.append({"role": "tool", "tool_call_id": call.get("id", ""),
                             "content": json.dumps({"error": feedback}, ensure_ascii=False)})
    raise AssistantError("مصاحبه گیر کرد؛ جوابت را کمی ساده‌تر بنویس.")
