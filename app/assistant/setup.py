"""راه‌اندازی با گفتگو: بعد از آشنایی (کارت شخصیت) و پیامک، وزیر دارایی و دخل و خرج را می‌پرسد.

در این حالت دو ابزار اضافه هست: suggest_replies (چند جواب کوتاه که کاربر با یک ضربه بفرستد)
و show_setup_card (کارت اتصال پیامک یا کارت پایان زیر جواب). ثبت دارایی و خرج با همان
ابزارهای add_ و کارت تأیید است. کارت پایان یعنی راه‌اندازی تمام شد.
"""

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Account, Asset, ExpenseStream, IncomeStream, Liability
from app.web import strings as s

UI_KEY = "setup_ui"  # db.info: چیزهایی که این نوبت باید زیر جواب نشان داده شود
CARDS = ("sms", "done")
MAX_REPLIES = 4
MAX_REPLY_CHARS = 40

PROMPT = """

حالت راه‌اندازی: کاربر تازه آمده؛ در مصاحبه کارت شخصیتش را گرفته (پرسونای بالا) و حالا وقت
چیدن تصویر مالی اوست. هنوز تقریباً چیزی در اپ ثبت نکرده. مثل دوستی که حالا او را می‌شناسد،
اپ را برایش پر کن تا همین الان وضعش را ببیند. به این ترتیب جلو برو:
۱. دارایی‌ها: با توجه به آنچه از پرسونا می‌دانی بپرس پس‌اندازش به چه شکلی است (طلا، سکه، دلار و
   ارز، حساب بانکی، بورس و صندوق، رمزارز، ماشین، ملک، پول نقد). برای هر کدام مقدار تقریبی را
   بپرس و با add_asset یا برای حساب بانکی با add_account پیشنهاد ثبت بده. عدد تقریبی کافی است؛
   اگر کاربر نمی‌داند یا نمی‌خواهد بگوید، اصرار نکن و برو سراغ بعدی. شماره کامل کارت یا حساب
   نپرس؛ لازم نیست.
۲. ماه به ماه: درآمد ماهانه (add_income) و هزینه‌های ثابت مثل اجاره، قسط، قبض و شهریه (add_bill
   با دسته درست). وام یا بدهی → add_liability. بعد کوتاه بگو تقریباً هر ماه چقدر برایش می‌ماند و
   یک جمله آن را به هدف او (از پرسونا) وصل کن.
۳. وقتی این دو تمام شد یا کاربر نخواست ادامه بدهد، show_setup_card با card=done صدا بزن و در یک
   جمله بگو تصویر مالی‌اش آماده است؛ این پایان راه‌اندازی است. اگر کاربر وسط کار گفت پیامک بانک
   را هنوز وصل نکرده، show_setup_card با card=sms کارت اتصال را دوباره نشان بده.
قواعد این حالت:
- هر پیام کوتاه (حداکثر دو سه جمله)، گرم و خودمانی؛ هر بار فقط یک سؤال.
- در هر نوبت suggest_replies را با ۲ تا ۴ جواب کوتاه و محتمل صدا بزن (مثلاً «طلا دارم»،
  «حساب بانکی دارم»، «چیز دیگه‌ای ندارم»)؛ جواب‌ها را از روی پرسونا و حرف‌های قبلی کاربر شخصی کن.
- اگر کاربر سؤال دیگری پرسید، کوتاه جواب بده و برگرد سر راه‌اندازی.
- آنچه تا الان ثبت شده یا منتظر تأیید است دوباره نپرس:
{recorded}
"""

SETUP_TOOLS: list[dict[str, Any]] = [
    {"type": "function", "function": {
        "name": "suggest_replies",
        "description": "۲ تا ۴ جواب کوتاه پیشنهادی که کاربر با یک ضربه بفرستد.",
        "parameters": {"type": "object", "properties": {
            "options": {"type": "array", "items": {"type": "string"}}},
            "required": ["options"], "additionalProperties": False}}},
    {"type": "function", "function": {
        "name": "show_setup_card",
        "description": "زیر جواب کارت نشان بده: sms = اتصال پیامک بانک؛ done = تصویر مالی "
                       "آماده است (پایان راه‌اندازی).",
        "parameters": {"type": "object", "properties": {
            "card": {"type": "string", "enum": list(CARDS)}},
            "required": ["card"], "additionalProperties": False}}},
]
NAMES = {t["function"]["name"] for t in SETUP_TOOLS}


def ui(db: Session) -> dict[str, list[str]]:
    return db.info.setdefault(UI_KEY, {"suggestions": [], "cards": []})  # type: ignore[no-any-return]


def run(db: Session, name: str, arguments: str) -> str:
    try:
        args = json.loads(arguments or "{}")
    except ValueError:
        args = {}
    state = ui(db)
    if name == "suggest_replies":
        raw = args.get("options") if isinstance(args, dict) else None
        options = [" ".join(str(o).split())[:MAX_REPLY_CHARS] for o in raw or [] if str(o).strip()]
        state["suggestions"] = list(dict.fromkeys(options))[:MAX_REPLIES]
    elif name == "show_setup_card":
        card = args.get("card") if isinstance(args, dict) else None
        if card not in CARDS:
            return json.dumps({"error": "card باید sms یا done باشد"}, ensure_ascii=False)
        if card not in state["cards"]:
            state["cards"].append(card)
    return json.dumps({"ok": True})


def recorded(db: Session) -> str:
    """فهرست آنچه کاربر ثبت کرده، بدون هیچ مبلغی (فقط برای این‌که دوباره پرسیده نشود)."""
    lines = []
    assets = [f"{s.ASSET_KINDS.get(a.kind, a.kind)} ({a.name})" for a in db.scalars(select(Asset))]
    if assets:
        lines.append("دارایی: " + "، ".join(assets))
    banks = [f"حساب بانکی {s.BANKS.get(a.bank, a.bank)}" for a in db.scalars(select(Account))]
    if banks:
        lines.append("، ".join(banks))
    incomes = [i.name for i in db.scalars(select(IncomeStream))]
    if incomes:
        lines.append("درآمد: " + "، ".join(incomes))
    bills = [b.name for b in db.scalars(select(ExpenseStream))]
    if bills:
        lines.append("هزینه ثابت: " + "، ".join(bills))
    debts = [d.lender for d in db.scalars(select(Liability))]
    if debts:
        lines.append("بدهی: " + "، ".join(debts))
    return "\n".join(f"- {line}" for line in lines) or "- هنوز چیزی ثبت نشده"


def prompt(db: Session) -> str:
    return PROMPT.format(recorded=recorded(db))
