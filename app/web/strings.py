"""همه رشته‌های رابط کاربری در یک جا."""

APP_NAME = "دستیار مالی"

ASSET_KINDS: dict[str, str] = {
    "fx": "ارز",
    "gold": "طلا",
    "coin": "سکه",
    "stock": "سهام",
    "fund": "صندوق",
    "crypto": "رمزارز",
    "car": "خودرو",
    "real_estate": "ملک",
    "receivable": "طلب",
    "cash": "نقد",
    "other": "سایر",
}

COMPOSITION_LABELS: dict[str, str] = {**ASSET_KINDS, "bank": "حساب بانکی"}

LIABILITY_KINDS: dict[str, str] = {
    "bank_loan": "وام بانکی",
    "bnpl": "اقساط خرید (BNPL)",
    "credit_card": "کارت اعتباری",
    "personal": "بدهی شخصی",
    "other": "سایر",
}

FREQUENCIES: dict[str, str] = {"monthly": "ماهانه", "quarterly": "سه‌ماهه", "yearly": "سالانه"}

BANKS: dict[str, str] = {
    "mellat": "ملت",
    "melli": "ملی",
    "saderat": "صادرات",
    "tejarat": "تجارت",
    "sepah": "سپه",
    "maskan": "مسکن",
    "keshavarzi": "کشاورزی",
    "pasargad": "پاسارگاد",
    "saman": "سامان",
    "parsian": "پارسیان",
    "eghtesad_novin": "اقتصاد نوین",
    "ayandeh": "آینده",
    "resalat": "رسالت",
    "blu": "بلو",
    "other": "سایر",
}

BALANCE_SOURCES: dict[str, str] = {"manual": "دستی", "sms": "پیامک"}

# کلیدهای قیمت ثابت؛ سهام و صندوق به‌صورت stock:<نماد> و fund:<نماد>
GOLD_PRICE_KEYS: dict[str, str] = {
    "gold18_gram": "طلای ۱۸ عیار (هر گرم)",
    "gold_mesghal": "آبشده (هر مثقال)",
    "coin_emami": "سکه امامی",
    "coin_bahar": "سکه بهار آزادی",
    "coin_half": "نیم‌سکه",
    "coin_quarter": "ربع‌سکه",
    "coin_gram": "سکه گرمی",
}
COIN_KEYS = ("coin_emami", "coin_bahar", "coin_half", "coin_quarter", "coin_gram")
# قیمت‌های اصلی که همیشه بالای صفحه قیمت‌ها نشان داده می‌شوند
MAIN_PRICE_KEYS = ("usd", "eur", *GOLD_PRICE_KEYS)

NAV = {
    "dashboard": "داشبورد",
    "assets": "دارایی‌ها",
    "accounts": "حساب‌ها",
    "liabilities": "بدهی‌ها",
    "incomes": "درآمدها",
    "prices": "قیمت‌ها",
    "loan": "تحلیل وام",
    "settings": "تنظیمات",
}

T = {
    "login_title": "ورود",
    "password": "رمز عبور",
    "password_repeat": "تکرار رمز عبور",
    "login": "ورود",
    "logout": "خروج",
    "save": "ذخیره",
    "add": "افزودن",
    "edit": "ویرایش",
    "delete": "حذف",
    "cancel": "انصراف",
    "confirm_delete": "حذف شود؟",
    "empty": "هنوز چیزی ثبت نشده.",
    "wrong_password": "رمز عبور اشتباه است.",
    "request_failed": "انجام نشد؛ اتصال را بررسی کن و دوباره امتحان کن.",
    "login_locked": "چند بار رمز اشتباه زده شد؛ ۱۵ دقیقه دیگر دوباره امتحان کن.",
    "password_short": "رمز عبور باید دست‌کم ۸ نویسه باشد.",
    "password_mismatch": "دو رمز یکسان نیستند.",
    "required": "این فیلد لازم است.",
    "invalid_number": "عدد نامعتبر است.",
    "invalid_date": "تاریخ نامعتبر است (مثل ۱۴۰۵/۰۷/۰۹).",
    "invalid_choice": "گزینه نامعتبر است.",
    "out_of_range": "خارج از محدوده مجاز است.",
    "mask_hint": "۴ رقم آخر حساب یا کارت؛ برای بانکی مثل بلو که در پیامک شماره ندارد خالی بگذار.",
    "networth": "ثروت خالص",
    "in_toman": "به تومان",
    "in_usd": "به دلار",
    "in_gold": "به گرم طلای ۱۸",
    "total_assets": "جمع دارایی‌ها",
    "total_liabilities": "جمع بدهی‌ها",
    "cashflow": "جریان نقدی ماهانه",
    "monthly_income": "درآمد ماهانه",
    "monthly_installments": "اقساط ماهانه",
    "free_cash": "باقی‌مانده ماهانه",
    "dti": "نسبت اقساط به درآمد",
    "dti_warning": "از آستانه {threshold} بیشتر است.",
    "composition": "ترکیب دارایی",
    "trend": "روند ثروت خالص",
    "trend_empty": "نمودار روند از روز دوم استفاده پر می‌شود (یک اسنپ‌شات در روز).",
    "needs_price": "بدون قیمت",
    "needs_price_warning": "{count} دارایی هنوز قیمت بازار ندارد و در جمع حساب نشده:",
    "stale_warning": "ارزش این دارایی‌ها بیش از ۳۰ روز است به‌روز نشده — به‌روزرسانی کن:",
    "no_unit_price": "قیمت {name} ثبت نشده",
    "value": "ارزش",
    "remaining": "مانده",
    "installment_short": "قسط",
    "remaining_installments": "اقساط باقی‌مانده",
    "monthly_equivalent": "معادل ماهانه",
    "inactive": "غیرفعال",
    "price_key": "دارایی",
    "price_toman": "قیمت (تومان)",
    "price_updated": "زمان ثبت",
    "price_source": "منبع",
    "prices_hint": "قیمت‌ها خودکار به‌روز می‌شوند: ارز، طلا، سکه و رمزارز از الان‌چند؛ سهام و "
                   "صندوق‌هایی که ثبت کرده‌ای از شاخص‌بان. هر قیمتی را می‌توانی دستی بازنویسی کنی.",
    "custom_key": "کلید دلخواه (مثل stock:فولاد)",
    "no_price": "ثبت نشده",
    "loan_title": "تحلیلگر وام",
    "loan_disclaimer": "این خروجی تحلیل است، نه توصیه سرمایه‌گذاری.",
    "analyze": "تحلیل کن",
    "effective_rate": "نرخ مؤثر سالانه",
    "nominal_rate": "نرخ اسمی اعلام‌شده",
    "real_rate": "نرخ واقعی (پس از تورم {inflation})",
    "total_cost": "هزینه کل وام",
    "net_received": "پول خالص دریافتی",
    "total_paid": "جمع پرداختی‌ها",
    "installment_amount": "مبلغ قسط",
    "dti_before": "نسبت اقساط به درآمد فعلی",
    "dti_after": "پس از این وام",
    "cost_steps": "هر هزینه پنهان چقدر به نرخ اضافه کرد",
    "cash_flows": "جریان نقدی ماهانه (برای تطبیق با IRR اکسل)",
    "month": "ماه",
    "cash_flow": "جریان نقدی (تومان)",
    "history": "تحلیل‌های قبلی",
    "settings_title": "تنظیمات",
    "dti_threshold": "آستانه هشدار نسبت اقساط به درآمد (٪)",
    "inflation": "نرخ تورم فرضی سالانه (٪)",
    "export": "خروجی کامل JSON",
    "export_hint": "همه داده‌ها به‌صورت یک فایل JSON (برای پشتیبان یا انتقال).",
    "saved": "ذخیره شد.",
}

# ---------- پوسته اپ (نوار پایین، عنوان صفحه‌ها، پیام‌ها) ----------

# (کلید فعال، آدرس، برچسب، آیکون)
TABS: tuple[tuple[str, str, str, str], ...] = (
    ("dashboard", "/", "خانه", "home"),
    ("assets", "/assets", "دارایی", "wallet"),
    ("cashflow", "/liabilities", "اقساط و درآمد", "flow"),
    ("spending", "/spending", "خرج‌ها", "bag"),
    ("more", "/more", "بیشتر", "more"),
)

# کدام تب برای هر صفحه روشن باشد
TAB_OF_PAGE: dict[str, str] = {
    "assets": "assets",
    "accounts": "assets",
    "liabilities": "cashflow",
    "incomes": "cashflow",
    "prices": "more",
    "settings": "more",
}

# زبانه‌های بالای صفحه برای صفحه‌های جفتی
SEGMENTS: dict[str, tuple[tuple[str, str], ...]] = {
    "assets": (("assets", "دارایی‌ها"), ("accounts", "حساب‌های بانکی")),
    "cashflow": (("liabilities", "بدهی و اقساط"), ("incomes", "درآمدها")),
}

ASSET_ICONS: dict[str, str] = {
    "fx": "dollar", "gold": "gold", "coin": "coin", "stock": "chart", "fund": "pie",
    "crypto": "crypto",
    "car": "car", "real_estate": "building", "receivable": "handshake", "cash": "cash",
    "other": "box",
}
LIABILITY_ICONS: dict[str, str] = {
    "bank_loan": "bank", "bnpl": "bag", "credit_card": "card", "personal": "handshake",
    "other": "box",
}

# گروه‌بندی ترکیب دارایی با رنگ ثابت برای هر گروه (رنگ دنبال موجودیت است، نه رتبه)
COMPOSITION_GROUPS: tuple[tuple[str, str, tuple[str, ...], int], ...] = (
    # (کلید، برچسب، انواع دارایی، شماره رنگ در پالت دسته‌ای؛ ۰ = خاکستری «سایر»)
    ("bank", "حساب بانکی", ("bank",), 1),
    ("fx", "ارز", ("fx",), 3),
    ("gold", "طلا", ("gold",), 4),
    ("coin", "سکه", ("coin",), 2),
    ("bourse", "بورس", ("stock", "fund"), 7),
    ("car", "خودرو", ("car",), 5),
    ("real_estate", "ملک", ("real_estate",), 6),
    ("crypto", "رمزارز", ("crypto",), 8),
    ("other", "سایر", ("receivable", "cash", "other"), 0),
)

PAGE_TITLES: dict[str, str] = {
    "assets": "دارایی‌ها",
    "accounts": "حساب‌های بانکی",
    "liabilities": "بدهی و اقساط",
    "incomes": "درآمدها",
    "prices": "قیمت‌ها",
    "loan": "تحلیلگر وام",
    "settings": "تنظیمات",
    "more": "بیشتر",
}

EMPTY_STATES: dict[str, tuple[str, str]] = {
    "assets": ("هنوز دارایی‌ای ثبت نکرده‌ای",
               "طلا، ارز، سکه، سهام، خودرو یا ملک — هر چه داری اضافه کن تا تصویر کامل شود."),
    "accounts": ("حسابی ثبت نشده",
                 "موجودی حساب‌های بانکی‌ات را وارد کن؛ فقط ۴ رقم آخر حساب ذخیره می‌شود."),
    "liabilities": ("بدهی‌ای ثبت نشده",
                    "وام، اقساط خرید، کارت اعتباری یا بدهی شخصی را اضافه کن."),
    "incomes": ("درآمدی ثبت نشده",
                "حقوق، اجاره یا هر درآمد تکراری را اضافه کن تا جریان نقدی حساب شود."),
}

TOASTS: dict[str, str] = {
    "created": "{title} اضافه شد",
    "updated": "تغییرات ذخیره شد",
    "deleted": "{title} حذف شد",
    "prices": "قیمت‌ها ثبت شد",
    "settings": "تنظیمات ذخیره شد",
}

T.update({
    "new": "جدید",
    "close": "بستن",
    "total": "جمع",
    "this_month": "در ماه",
    "since_last": "نسبت به {date}",
    "quick_actions": "میان‌برها",
    "add_asset": "دارایی",
    "add_liability": "بدهی",
    "add_income": "درآمد",
    "update_prices": "قیمت‌ها",
    "welcome_title": "خوش آمدی 👋",
    "welcome_body": "سه قدم تا اولین تصویر کامل از ثروتت:",
    "welcome_steps": ("دارایی‌ها و حساب‌هایت را اضافه کن",
                      "بدهی‌ها و اقساط را وارد کن",
                      "درآمدهای ماهانه را ثبت کن"),
    "of_income": "از درآمد",
    "left_over": "باقی می‌ماند",
    "go_prices": "ثبت قیمت",
    "more_data": "داده‌ها",
    "more_account": "حساب کاربری",
    "advanced": "جزئیات بیشتر",
    "updated_at": "به‌روزرسانی",
    "per_unit": "هر واحد",
    "stale_short": "قدیمی",
    "unit_toggle": "واحد نمایش",
    "loan_empty": "مشخصات وام را وارد کن تا نرخ واقعی و هزینه‌های پنهانش را ببینی.",
    "loan_new": "تحلیل جدید",
    "price_placeholder": "قیمت جدید",
    "version": "نسخه صفر",
})

LOAN_GROUPS: tuple[tuple[str, str, bool], ...] = (
    ("main", "مشخصات وام", True),
    ("fees", "کارمزد، ضامن و بیمه", False),
    ("blocked", "سپرده بلوکه", False),
    ("averaging", "معدل‌گیری", False),
    ("budget", "درآمد و اقساط فعلی", False),
)

KIND_SLOT: dict[str, int] = {
    kind: slot for key, _label, kinds, slot in COMPOSITION_GROUPS for kind in (*kinds, key)
}

TOASTS.update({
    "refreshed": "{count} قیمت به‌روز شد",
    "refresh_failed": "دریافت از {names} ناموفق بود؛ آخرین قیمت‌ها حفظ شد",
})
SOURCE_LABELS: dict[str, str] = {"alanchand": "الان‌چند", "shakhesban": "شاخص‌بان",
                                 "manual": "دستی"}
T.update({
    "refresh_now": "به‌روزرسانی از منبع",
    "source_never": "هنوز دریافتی انجام نشده",
    "source_ok": "{count} قیمت · {at}",
    "source_failed": "ناموفق · {at}",
    "no_sources": "هنوز منبع خودکاری فعال نیست؛ قیمت‌ها را دستی وارد کن.",
})


# ارزهای الان‌چند (کلید = کد ارز، قیمت به ازای یک واحد)
CURRENCY_NAMES: dict[str, str] = {
    "usd": "دلار آمریکا",
    "eur": "یورو",
    "aed": "درهم",
    "try": "لیر ترکیه",
    "gbp": "پوند انگلیس",
    "cny": "یوان چین",
    "cad": "دلار کانادا",
    "aud": "دلار استرالیا",
    "rub": "روبل روسیه",
    "iqd": "دینار عراق",
    "myr": "رینگیت مالزی",
    "gel": "لاری گرجستان",
    "azn": "منات آذربایجان",
    "amd": "درام ارمنستان",
    "thb": "بات تایلند",
    "omr": "ریال عمان",
    "inr": "روپیه هند",
    "pkr": "روپیه پاکستان",
    "jpy": "ین ژاپن",
    "sar": "ریال عربستان",
    "afn": "افغانی",
    "sek": "کرون سوئد",
    "chf": "فرانک سوئیس",
    "qar": "ریال قطر",
    "krw": "وون کره جنوبی",
    "nok": "کرون نروژ",
    "nzd": "دلار نیوزلند",
    "sgd": "دلار سنگاپور",
    "hkd": "دلار هنگ کنگ",
    "kwd": "دینار کویت",
    "dkk": "کرون دانمارک",
    "bhd": "دینار بحرین",
    "tjs": "سامانی تاجیکستان",
    "tmt": "منات ترکمنستان",
    "kgs": "سوم قرقیزستان",
    "syp": "پوند سوریه",
    "brl": "رئال برزیل",
    "ars": "پزو آرژانتین",
}

# رمزارزهای الان‌چند (کلید قیمت = crypto:<نماد>)
CRYPTO_NAMES: dict[str, str] = {
    "usdt": "تتر (USDT)",
    "btc": "بیت کوین (BTC)",
    "eth": "اتریوم (ETH)",
    "xrp": "ریپل (XRP)",
    "bnb": "بایننس کوین (BNB)",
    "shib": "شیبا (SHIB)",
    "ada": "کاردانو (ADA)",
    "doge": "دوج‌کوین (DOGE)",
    "ton": "تون کوین (TON)",
    "not": "نات کوین (NOT)",
    "sol": "سولانا (SOL)",
    "trx": "ترون (TRX)",
    "cake": "پنکیک سواپ (CAKE)",
    "avax": "آوالانچ (AVAX)",
    "dot": "پولکادات (DOT)",
    "link": "چین‌لینک (LINK)",
    "ltc": "لایت‌کوین (LTC)",
    "pepe": "پپه (PEPE)",
    "uni": "یونی‌سواپ (UNI)",
    "xlm": "استلار (XLM)",
    "fil": "فایل‌کوین (FIL)",
    "near": "نیر پروتکل (NEAR)",
    "eos": "ایاس (EOS)",
    "aave": "آوه (AAVE)",
    "grt": "گراف (GRT)",
    "xtz": "تزوس (XTZ)",
    "flow": "فلو (FLOW)",
    "sand": "سندباکس (SAND)",
    "mana": "دی‌سنترالند (MANA)",
    "axs": "اکسی اینفینیتی (AXS)",
    "chz": "چیلیز (CHZ)",
    "enj": "انجین کوین (ENJ)",
    "zec": "زدکش (ZEC)",
    "gala": "گالا (GALA)",
    "lrc": "لوپرینگ (LRC)",
    "bat": "بت (BAT)",
    "one": "هارمونی (ONE)",
    "zen": "هورایزن (ZEN)",
    "cvc": "سیویک (CVC)",
    "storj": "استورج (STORJ)",
}

FX_KEYS = tuple(CURRENCY_NAMES)
CRYPTO_KEYS = tuple(f"crypto:{code}" for code in CRYPTO_NAMES)
PRICE_KEYS: dict[str, str] = {
    **CURRENCY_NAMES,
    **GOLD_PRICE_KEYS,
    **{f"crypto:{code}": name for code, name in CRYPTO_NAMES.items()},
}

# ---------- پیامک بانکی ----------
PAGE_TITLES["sms"] = "پیامک‌های بانکی"
TAB_OF_PAGE["sms"] = "more"
DIRECTIONS: dict[str, str] = {"in": "واریز", "out": "برداشت"}
SMS_STATUS: dict[str, str] = {"parsed": "ثبت شد", "failed": "نیاز به بررسی", "ignored": "نادیده"}
TOASTS.update({
    "sms_imported": "{parsed} ثبت شد · {failed} نیاز به بررسی · {duplicate} تکراری",
    "sms_completed": "تراکنش ثبت شد",
    "sms_ignored": "پیامک کنار گذاشته شد",
    "sms_token": "توکن تازه ساخته شد؛ Shortcut را به‌روز کن",
})
T.update({
    "sms_queue": "نیاز به بررسی",
    "sms_queue_empty": "صف بررسی خالی است.",
    "sms_recent": "پیامک‌های اخیر",
    "sms_none": "هنوز پیامکی نرسیده.",
    "sms_complete": "تکمیل",
    "sms_ignore": "نادیده بگیر",
    "sms_review_title": "تکمیل پیامک",
    "sms_upload": "واردکردن فایل پیامک‌ها",
    "sms_upload_hint": "فایل متنی که Shortcut ساخته (هر پیامک با خط «--- زمان» شروع می‌شود).",
    "sms_choose_file": "انتخاب فایل",
    "sms_setup": "راه‌اندازی دریافت خودکار",
    "sms_token_label": "توکن (هدر X-Ingest-Token)",
    "sms_rotate": "ساخت توکن تازه",
    "sms_notice": "{count} پیامک بانکی نیاز به بررسی دارد",
    "sms_more": "دریافت از Shortcuts و صف بررسی",
    "sms_parsers_note": "پارسر اختصاصی برای بانک‌ها با رسیدن نمونه پیامک‌ها اضافه می‌شود؛ تا آن موقع "
                        "پیامک‌ها این‌جا با چند ضربه تکمیل می‌شوند.",
})


# ---------- هزینه‌ها: هزینه ثابت تکراری و خرج واقعی ----------
EXPENSE_CATEGORIES: dict[str, str] = {
    "food": "خوراک و رستوران",
    "housing": "اجاره و مسکن",
    "bills": "قبض و شارژ",
    "transport": "رفت‌وآمد",
    "shopping": "خرید",
    "health": "سلامت",
    "education": "آموزش",
    "fun": "تفریح و سفر",
    "subscriptions": "اشتراک‌ها",
    "gifts": "هدیه و کمک",
    "installment": "قسط",
    "transfer": "انتقال به حساب خودم",
    "other": "سایر",
}
CATEGORY_LABELS: dict[str, str] = {**EXPENSE_CATEGORIES, "uncategorized": "بدون دسته"}
CATEGORY_ICONS: dict[str, str] = {
    "food": "bag", "housing": "building", "bills": "alert", "transport": "car",
    "shopping": "bag", "health": "spark", "education": "pie", "fun": "spark",
    "subscriptions": "clock", "gifts": "handshake", "installment": "bank", "transfer": "flow",
    "other": "box", "uncategorized": "box",
}
CATEGORY_SLOT: dict[str, int] = {
    key: (i % 8) + 1 for i, key in enumerate(EXPENSE_CATEGORIES)
} | {"uncategorized": 0, "other": 0}
WEEKDAYS: tuple[str, ...] = ("شنبه", "یکشنبه", "دوشنبه", "سه‌شنبه", "چهارشنبه", "پنجشنبه", "جمعه")
JALALI_MONTHS: tuple[str, ...] = ("فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
                                  "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند")

PAGE_TITLES.update({"spending": "خرج‌ها", "bills": "هزینه‌های ثابت", "loan": "تحلیلگر وام"})
TAB_OF_PAGE.update({"spending": "spending", "bills": "spending", "loan": "more"})
SEGMENTS["spending"] = (("spending", "خرج‌ها"), ("bills", "هزینه‌های ثابت"))
NAV.update({"spending": "خرج‌ها", "bills": "هزینه‌های ثابت"})
EMPTY_STATES.update({
    "bills": ("هزینه ثابتی ثبت نشده",
              "اجاره، قبض، شهریه یا هر خرج تکراری را اضافه کن تا باقی‌مانده ماهانه درست حساب شود."),
    "spending": ("این ماه خرجی ثبت نشده",
                 "برداشت‌های پیامک بانکی خودکار این‌جا می‌آیند؛ خرج نقدی را دستی اضافه کن."),
})
T.update({
    "fixed_expenses": "هزینه ثابت",
    "month_spending": "خرج این ماه",
    "spending_total": "جمع خرج",
    "by_category": "به تفکیک دسته",
    "transactions": "تراکنش‌ها",
    "add_expense": "خرج",
    "prev_month": "ماه قبل",
    "next_month": "ماه بعد",
    "transfer_note": "انتقال به حساب خودت در جمع خرج حساب نمی‌شود.",
    "fixed_monthly": "هزینه‌های ثابت ماهانه",
    "cash_expense": "دستی",
    "details": "جزئیات",
    "greeting": "سلام",
})

THEMES: dict[str, str] = {"system": "خودکار", "light": "روشن", "dark": "تیره"}
T.update({"appearance": "ظاهر"})

# ---------- حساب کاربری: موبایل + رمز، کد پیامکی برای ثبت‌نام و بازیابی ----------
T.update({
    "phone": "شماره موبایل",
    "phone_placeholder": "۰۹۱۲۱۲۳۴۵۶۷",
    "phone_invalid": "شماره موبایل درست نیست؛ مثل ۰۹۱۲۱۲۳۴۵۶۷ وارد کن.",
    "phone_taken": "این شماره قبلاً ثبت‌نام کرده؛ وارد شو یا رمز را بازیابی کن.",
    "signup_closed": "ثبت‌نام فعلاً فقط با دعوت است.",
    "wrong_login": "شماره یا رمز عبور درست نیست.",
    "login_hint": "با شماره موبایل و رمز عبورت وارد شو.",
    "no_account": "حساب نداری؟",
    "signup": "ثبت‌نام",
    "forgot": "رمز را فراموش کرده‌ای؟",
    "have_account": "حساب داری؟",
    "send_code": "ارسال کد تأیید",
    "signup_title": "ساخت حساب",
    "signup_hint": "شماره موبایلت نام کاربری‌ات می‌شود؛ یک کد تأیید برایت پیامک می‌کنیم.",
    "reset_title": "بازیابی رمز عبور",
    "reset_hint": "شماره‌ات را وارد کن؛ اگر حساب داشته باشی کد تأیید پیامک می‌شود.",
    "verify_title": "کد تأیید",
    "verify_hint": "کد ۶ رقمی که به {phone} پیامک شد را وارد کن.",
    "code": "کد تأیید",
    "code_wrong": "کد درست نیست یا منقضی شده؛ دوباره بفرست.",
    "code_resent": "اگر شماره درست باشد، کد تازه پیامک شد",
    "resend": "ارسال دوباره کد",
    "change_phone": "تغییر شماره",
    "new_password": "رمز عبور جدید",
    "choose_password": "رمز عبور برای ورودهای بعدی",
    "finish_signup": "ساخت حساب",
    "finish_reset": "ذخیره رمز جدید",
    "welcome": "حسابت ساخته شد؛ خوش آمدی",
    "password_changed": "رمز عبور عوض شد",
})
