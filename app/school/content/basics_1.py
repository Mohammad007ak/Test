"""دوره ۱، ایستگاه ۱: «پول و تورم». شش درس، هر درس یک کارت معرفی و سه سؤال.

همه عددها از تورم تنظیم کاربر، پس‌انداز و خرج خودش و قیمت واقعی بازار حساب می‌شوند.
هیچ کارتی توصیه خرید نیست؛ کارت‌های بازار و شخصی این را صریح می‌گویند.
"""

from datetime import date
from decimal import Decimal

import jdatetime

from app.domain.money import format_number, format_percent, format_toman_short, to_persian_digits
from app.domain.school import Slider, purchasing_power, real_rate
from app.school.lessons import Card, Facts, Lesson, Station
from app.web.strings import JALALI_MONTHS

TRUE_FALSE = ("👍 درسته", "👎 غلطه")
NOT_ADVICE = "آموزشی است، نه توصیه خرید."
HUNDRED_M = 100_000_000
RACE_LABELS: dict[str, str] = {
    "cash": "😴 زیر بالش", "usd": "💵 دلار", "coin_emami": "🪙 سکه امامی",
    "gold18_gram": "✨ طلای ۱۸",
}


def _pct(rate: Decimal, places: int = 0) -> str:
    return format_percent(rate, places).replace("-", "منفی ")


def _m(toman: int) -> str:
    return format_toman_short(toman)


def _n(value: int) -> str:
    return to_persian_digits(str(value))


def _factor(rate: Decimal) -> str:
    """۰٫۳۵ → «۱٫۳۵» (ضریب یک سال)."""
    return format_number(1 + rate, 2).rstrip("۰").rstrip("٫")


def _month(day: date) -> str:
    j = jdatetime.date.fromgregorian(date=day)
    return f"{JALALI_MONTHS[j.month - 1]} {_n(j.year)}"


def _assumption(f: Facts) -> str:
    return f"فرض: تورم سالانه {_pct(f.inflation)} (از تنظیمات تو)"


def _sample_note(sample: bool, what: str) -> str:
    return f"عدد نمونه است؛ {what} را ثبت کنی، با عدد خودت حساب می‌شود." if sample else \
        "با عدد خودت حساب شده؛ فقط همین‌جا، نزد خودت."


# ---------- ۱. پول چیه؟ ----------

def _money(f: Facts) -> list[Card]:
    i = f.inflation
    now = round(100 / (1 + i))
    trap = round(100 * (1 - i))
    more = round(100 * (1 + i))
    return [
        Card("intro", "بیا از اول شروع کنیم",
             "اسکناس خودش فقط کاغذه؛ ارزشش *چیزهاییه که باهاش می‌شه خرید*.",
             sub="به این می‌گن «قدرت خرید». هرچی با همون پول کمتر بشه خرید، پولت ضعیف‌تر شده.",
             art="bill", mood="idle"),
        Card("choice", "یه سؤال ساده", "ارزش واقعی پول یعنی چی؟",
             options=("چیزهایی که باهاش می‌شه خرید", "تعداد اسکناس‌هایی که داری",
                      "عدد موجودی حسابت"),
             correct=0,
             good="دقیقاً! ارزش پول همون قدرت خریدشه، نه عددی که روی اسکناس یا حساب نوشته.",
             bad="نه دقیقاً. عدد حساب یا تعداد اسکناس ممکنه ثابت بمونه، ولی اگه کمتر بشه باهاش "
                 "خرید، ارزشش کم شده. ارزش واقعی = قدرت خرید."),
        Card("choice", "نون و تورم",
             f"پارسال با ۱ میلیون تومان *{_n(100)} تا نون* می‌خریدی. امسال با تورم "
             f"*{_pct(i)}*، همون پول چند تا نون می‌خره؟",
             options=(f"{_n(more)} تا", f"{_n(100)} تا", f"{_n(now)} تا", f"{_n(trap)} تا"),
             correct=2, note="قیمت نون فرضی است.",
             good=f"آفرین! نون {_pct(i)} گرون‌تر شده، پس ۱۰۰ تقسیم بر "
                  f"{_factor(i)} می‌شه حدود {_n(now)} تا.",
             bad=f"جواب حدود {_n(now)} تاست: ۱۰۰ تقسیم بر {_factor(i)}. "
                 f"«۱۰۰ منهای {_n(round(i * 100))}» حساب رایج ولی اشتباهیه."),
        Card("truefalse", "درسته یا غلط؟",
             "اگه عدد حسابم یه سال ثابت بمونه، پولم هم *ثابت مونده*.",
             options=TRUE_FALSE, correct=1,
             good="آفرین! عدد ثابت مونده ولی قیمت‌ها رفتن بالا؛ یعنی پولت آروم‌آروم کوچیک شده.",
             bad="این تله رایجیه! عدد ثابت مونده، ولی با همون عدد کمتر می‌شه خرید؛ "
                 "پس پولت در واقع کوچیک شده."),
    ]


# ---------- ۲. تورم یعنی چی؟ ----------

def _inflation(f: Facts) -> list[Card]:
    i = f.inflation
    power = purchasing_power(HUNDRED_M, i, 1)
    million = 10_000_000
    return [
        Card("intro", "تورم به زبان ساده",
             f"تورم یعنی *بالا رفتن عمومی قیمت‌ها*. تورم {_pct(i)} یعنی چیزی که پارسال "
             f"۱۰۰ تومان بود، امسال حدود {_n(round(100 * (1 + i)))} تومانه.",
             sub="تورم یه میانگینه: قیمت بعضی چیزها بیشتر و بعضی کمتر بالا می‌ره.",
             note=_assumption(f), mood="idle"),
        Card("choice", "حدس بزن",
             f"چیزی که امروز *{_m(million)}* است، با تورم {_pct(i)} سال بعد حدوداً چنده؟",
             options=(_m(million), _m(round(million * (1 + i))),
                      _m(round(million * (1 + 2 * i)))),
             correct=1,
             good=f"درسته! {_m(million)} ضربدر {_factor(i)} می‌شه حدود "
                  f"{_m(round(million * (1 + i)))}.",
             bad=f"جواب {_m(round(million * (1 + i)))} است: قیمت به اندازه تورم، یعنی "
                 f"{_pct(i)}، بالا می‌ره."),
        Card("choice", "قدرت خرید",
             f"*۱۰۰ میلیون* با تورم {_pct(i)}، یه سال بعد قدرت خرید چند میلیون امروز رو داره؟",
             options=(_m(round(HUNDRED_M * (1 + i))), _m(HUNDRED_M), _m(power),
                      _m(round(HUNDRED_M * (1 - i)))),
             correct=2,
             good=f"دقیقاً! ۱۰۰ تقسیم بر {_factor(i)} می‌شه حدود {_m(power)}. "
                  "یعنی بخشی از پولت بی‌صدا رفت.",
             bad=f"حساب درستش ۱۰۰ تقسیم بر {_factor(i)} است، یعنی حدود "
                 f"{_m(power)}؛ نه ۱۰۰ منهای {_n(round(i * 100))}. تقسیم، نه تفریق."),
        Card("truefalse", "درسته یا غلط؟",
             f"با تورم {_pct(i)}، قیمت بعضی چیزها ممکنه *خیلی بیشتر* از {_pct(i)} بالا بره.",
             options=TRUE_FALSE, correct=0,
             good="آفرین! تورم میانگینه؛ مثلاً اجاره یا خوراکی ممکنه خیلی بیشتر بالا رفته باشن. "
                  "برای همین تورم واقعی هر خانواده با بقیه فرق داره.",
             bad="درسته! تورم میانگین قیمت‌هاست؛ بعضی چیزها بیشتر و بعضی کمتر گرون می‌شن، "
                 "برای همین تورم واقعی هر خانواده با بقیه فرق داره."),
    ]


# ---------- ۳. پولت آب می‌شه؟ ----------

def _melting(f: Facts) -> list[Card]:
    i = f.inflation
    cash = f.cash
    melted = cash.toman - purchasing_power(cash.toman, i, 1)
    years = ("امروز", "۱ سال", "۲ سال", "۳ سال")
    whose = " (نمونه)" if cash.sample else ""
    return [
        Card("intro", "یه چیز عجیب",
             "۱۰۰ میلیون توی حساب، *بدون این‌که خرجش کنی*، هر سال کوچیک‌تر می‌شه.",
             sub=f"با تورم {_pct(i)}، قدرت خریدش به پول امروز این‌جوری آب می‌شه:",
             bars=tuple((label, purchasing_power(HUNDRED_M, i, n))
                        for n, label in enumerate(years)),
             art="bill", note=_assumption(f), mood="idle"),
        Card("personal", "با عدد خودت",
             f"پس‌انداز نقدی تو{whose} *{_m(cash.toman)}* است. با همین تورم، تا یه سال دیگه "
             "حدوداً چقدرش آب می‌شه؟",
             options=(_m(melted // 2), _m(melted), _m(round(cash.toman * i))),
             correct=1, sample=cash.sample,
             note=_sample_note(cash.sample, "موجودی حساب‌هایت"),
             good=f"درسته، حدود {_m(melted)}. وزیر کمکت می‌کنه ببینی کجا بذاریش که کمتر آب بشه.",
             bad=f"حدود {_m(melted)}: {_m(cash.toman)} تقسیم بر {_factor(i)} "
                 f"می‌شه {_m(cash.toman - melted)}؛ بقیه‌ش آب می‌شه."),
        Card("choice", "راه چاره",
             "چی جلوی آب شدن پول رو می‌گیره؟",
             options=("پول بیشتری توی حساب جاری نگه داری",
                      "جایی بذاری که بازدهش از تورم بیشتر باشه",
                      "اسکناس رو توی خونه نگه داری"),
             correct=1, note=NOT_ADVICE,
             good="آفرین! فقط بازده بیشتر از تورم قدرت خرید رو نگه می‌داره؛ "
                  "هر جایی هم ریسک خودش رو داره.",
             bad="حساب جاری و اسکناس هر دو با تورم آب می‌شن. فقط جایی که بازدهش از تورم بیشتر "
                 "باشه قدرت خرید رو نگه می‌داره؛ البته هر کدوم ریسک خودش رو داره."),
        Card("truefalse", "درسته یا غلط؟",
             "توی دوره تورم، نگه داشتن *همه پول* به‌صورت نقد بی‌خطرترین کاره.",
             options=TRUE_FALSE, correct=1,
             good="درسته که غلطه! نقد نوسان نداره ولی ریسک آب شدن داره. "
                  "اندازه روز مبادا نقد نگه دار، نه بیشتر.",
             bad="نقد ریسک نوسان نداره، ولی ریسک آب شدن داره. اندازه روز مبادا نقد نگه دار، "
                 "نه همه‌ش رو."),
    ]


# ---------- ۴. سود بانکی واقعی ----------

def _real_interest(f: Facts) -> list[Card]:
    i = f.inflation
    low = i - Decimal("0.05")
    high = i + Decimal("0.05")
    real_low = real_rate(low, i)
    real_high = real_rate(high, i)
    return [
        Card("intro", "سود واقعی",
             "سود واقعی یعنی سودی که *بعد از کم کردن اثر تورم* می‌مونه.",
             sub="حسابش ساده‌ست: (۱ + سود) تقسیم بر (۱ + تورم)، منهای ۱.",
             note=_assumption(f), mood="idle"),
        Card("truefalse", "درسته یا غلط؟",
             f"سپرده با سود *{_pct(low)}* وقتی تورم *{_pct(i)}* است، یعنی پولدارتر شدی.",
             options=TRUE_FALSE, correct=1,
             good=f"آفرین! سود واقعی حدود {_pct(real_low, 1)} است. عدد حساب بزرگ‌تر شد، "
                  "ولی کمتر می‌تونی بخری.",
             bad=f"این تله رایجیه! عدد حساب بیشتر می‌شه، ولی چون قیمت‌ها تندتر رفتن بالا، "
                 f"سود واقعی حدود {_pct(real_low, 1)} است."),
        Card("choice", "حساب کن",
             f"سود واقعی همین سپرده ({_pct(low)} سود، {_pct(i)} تورم) چنده؟",
             options=(_pct(low), "صفر", f"حدود {_pct(real_low, 1)}",
                      _pct(low - i)),
             correct=2,
             good=f"دقیقاً! {_factor(low)} تقسیم بر {_factor(i)} منهای ۱ می‌شه حدود "
                  f"{_pct(real_low, 1)}.",
             bad=f"جواب حدود {_pct(real_low, 1)} است. «سود منهای تورم» تقریب نزدیکیه، "
                 "ولی حساب دقیقش تقسیمه، نه تفریق."),
        Card("choice", "یه سپرده دیگه",
             f"اگه سود سپرده *{_pct(high)}* و تورم {_pct(i)} باشه، سود واقعی چطوره؟",
             options=(f"مثبت؛ حدود {_pct(real_high, 1)}", "صفر", "منفی"),
             correct=0,
             good=f"آفرین! سود از تورم بیشتره، پس سود واقعی مثبته: حدود {_pct(real_high, 1)}.",
             bad=f"وقتی سود از تورم بیشتر باشه، سود واقعی مثبته: حدود {_pct(real_high, 1)}."),
    ]


# ---------- ۵. صندوق اضطراری ----------

def _emergency(f: Facts) -> list[Card]:
    spend = f.monthly_spend
    whose = " (نمونه)" if spend.sample else ""
    return [
        Card("intro", "روز مبادا",
             "صندوق اضطراری پولیه برای *اتفاق‌های پیش‌بینی‌نشده*: بیکاری، بیماری، "
             "خرابی ماشین.",
             sub="باید زود و بی‌ضرر در دسترس باشه، نه گیر یه سرمایه‌گذاری پرنوسان.",
             mood="idle"),
        Card("slider", "صندوق اضطراری",
             f"خرج ماهانه‌ت{whose} حدود *{_m(spend.toman)}* است. برای روز مبادا چند ماهش رو "
             "کنار بذاری؟",
             slider=Slider(low=1, high=12, right_low=3, right_high=6),
             slider_unit_toman=spend.toman, sample=spend.sample,
             note=_sample_note(spend.sample, "خرج‌هایت"),
             good="عالی! ۳ تا ۶ ماه خرج برای بیشتر آدم‌ها اندازه درستیه؛ "
                  "بقیه پول رو بفرست سراغ رشد.",
             bad="معمولاً ۳ تا ۶ ماه خرج خوبه: کمتر یعنی با یه اتفاق ته می‌کشه، "
                 "بیشتر یعنی پولی که بی‌کار مونده و آب می‌شه."),
        Card("choice", "کجا بذارمش؟",
             "صندوق اضطراری کجا باشه بهتره؟",
             options=("ملکی که خریدی", "جایی که سریع و بی‌ضرر برداشت بشه",
                      "رمزارز، چون سود بیشتری داره"),
             correct=1, note=NOT_ADVICE,
             good="آفرین! روز مبادا خبر نمی‌ده؛ پولش باید همون روز در دسترس باشه.",
             bad="ملک دیر فروش می‌ره و رمزارز ممکنه همون روز نصف شده باشه. صندوق اضطراری "
                 "باید سریع و بی‌ضرر در دسترس باشه."),
        Card("truefalse", "درسته یا غلط؟",
             "اگه درآمدت ثابت نیست (مثلاً آزادکاری)، بهتره صندوق اضطراریت *بزرگ‌تر* باشه.",
             options=TRUE_FALSE, correct=0,
             good="آفرین! درآمد نامنظم یعنی ماه‌های کم‌درآمد بیشتر؛ ۶ ماه یا بیشتر امن‌تره.",
             bad="درسته! با درآمد نامنظم ماه‌های کم‌درآمد بیشتره، پس صندوق بزرگ‌تر "
                 "(۶ ماه یا بیشتر) امن‌تره."),
    ]


# ---------- ۶. ۳ سال پیش ۱۰۰ میلیون کجا؟ ----------

def _race(f: Facts) -> list[Card]:
    race = f.race
    labels = tuple(RACE_LABELS[row.key] for row in race.rows)
    win = race.winner
    best = race.rows[win]
    winner_name = labels[win].split(" ", 1)[1]
    source = "الان‌چند" if race.live else "الان‌چند، داده ذخیره‌شده"
    pillow = purchasing_power(race.amount_toman, f.inflation, 3)
    return [
        Card("intro", "داده واقعی بازار",
             f"بیا با *قیمت‌های واقعی* ببینیم {_m(race.amount_toman)} از {_month(race.start)} "
             f"تا {_month(race.end)} کجا چی شد.",
             sub="اول حدس بزن، بعد مسابقه رو ببین.", mood="idle"),
        Card("market", "حدس بزن",
             f"{_month(race.start)} با *{_m(race.amount_toman)}* چی می‌خریدی که تا "
             f"{_month(race.end)} بیشتر شده باشه؟",
             options=labels, correct=win, race=race,
             note=f"منبع: {source} · {NOT_ADVICE}",
             good=f"{winner_name}! {_m(race.amount_toman)} شد حدود {_m(best.final_toman)}. "
                  "ولی گذشته تضمینی برای آینده نیست.",
             bad=f"این بار {winner_name} برد: حدود {_m(best.final_toman)}. "
                 "ولی گذشته تضمینی برای آینده نیست."),
        Card("choice", "زیر بالش",
             f"{_m(race.amount_toman)} زیر بالش همون {_m(race.amount_toman)} موند. با تورم "
             f"{_pct(f.inflation)}، به پول سه سال پیش چقدر می‌ارزه؟",
             options=(_m(race.amount_toman),
                      _m(round(race.amount_toman * (1 - f.inflation))), _m(pillow)),
             correct=2, note=_assumption(f),
             good=f"درسته؛ حدود {_m(pillow)}. عدد ثابت موند، قدرت خرید نه.",
             bad=f"حدود {_m(pillow)}: سه بار پشت سر هم تقسیم بر "
                 f"{_factor(f.inflation)}."),
        Card("truefalse", "درسته یا غلط؟",
             f"چون {winner_name} توی این سه سال بیشترین سود رو داد، سه سال بعد هم *حتماً* "
             "همین‌طوره.",
             options=TRUE_FALSE, correct=1, note=NOT_ADVICE,
             good="آفرین! بازار حافظه نداره؛ برنده دیروز ممکنه بازنده فردا باشه. "
                  "برای همین تنوع مهمه.",
             bad="نه؛ گذشته تضمینی برای آینده نیست. برنده دیروز ممکنه بازنده فردا باشه، "
                 "برای همین تنوع مهمه."),
    ]


STATION = Station(
    key="basics-1", number=1, title="پول و تورم",
    finale="تورم دیگه نمی‌تونه یواشکی پولت رو بخوره.",
    lessons=(
        Lesson("money", "پول چیه؟", "💸", "ارزش پول یعنی قدرت خریدش", _money),
        Lesson("inflation", "تورم یعنی چی؟", "📈", "چرا با همون پول کمتر می‌شه خرید", _inflation),
        Lesson("melting", "پولت آب می‌شه؟", "🔥", "پس‌انداز نقدی تو با تورم", _melting),
        Lesson("real-interest", "سود بانکی واقعی", "🏦", "سود منهای تورم", _real_interest),
        Lesson("emergency-fund", "صندوق اضطراری", "🛟", "چند ماه خرج برای روز مبادا",
               _emergency),
        Lesson("three-years", "۳ سال پیش ۱۰۰ میلیون کجا؟", "🏁",
               "مسابقه با قیمت واقعی بازار", _race),
    ),
)
