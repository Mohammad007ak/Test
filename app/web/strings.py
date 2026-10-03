"""همه رشته‌های رابط کاربری در یک جا."""

APP_NAME = "دستیار مالی"

ASSET_KINDS: dict[str, str] = {
    "fx": "ارز",
    "gold": "طلا",
    "coin": "سکه",
    "stock": "سهام",
    "fund": "صندوق",
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
PRICE_KEYS: dict[str, str] = {
    "usd": "دلار آمریکا",
    "eur": "یورو",
    "gold18_gram": "طلای ۱۸ عیار (هر گرم)",
    "coin_emami": "سکه امامی",
    "coin_half": "نیم‌سکه",
    "coin_quarter": "ربع‌سکه",
}
FX_KEYS = ("usd", "eur")
COIN_KEYS = ("coin_emami", "coin_half", "coin_quarter")

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
    "setup_title": "تعیین رمز عبور",
    "setup_hint": "اولین اجرا: یک رمز عبور برای ورود انتخاب کن (دست‌کم ۸ نویسه).",
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
    "password_short": "رمز عبور باید دست‌کم ۸ نویسه باشد.",
    "password_mismatch": "دو رمز یکسان نیستند.",
    "required": "این فیلد لازم است.",
    "invalid_number": "عدد نامعتبر است.",
    "invalid_date": "تاریخ نامعتبر است (مثل ۱۴۰۵/۰۷/۰۹).",
    "invalid_choice": "گزینه نامعتبر است.",
    "out_of_range": "خارج از محدوده مجاز است.",
    "mask_hint": "دقیقاً ۴ رقم آخر حساب یا کارت.",
    "networth": "ثروت خالص",
    "in_toman": "به تومان",
    "in_usd": "به دلار",
    "in_gold": "به گرم طلای ۱۸",
    "total_assets": "جمع دارایی‌ها",
    "total_liabilities": "جمع بدهی‌ها",
    "cashflow": "جریان نقدی ماهانه",
    "monthly_income": "درآمد ماهانه",
    "monthly_installments": "اقساط ماهانه",
    "free_cash": "باقی‌مانده پس از اقساط",
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
    "prices_hint": "قیمت‌ها از منبع خودکار به‌روز می‌شوند و هر قیمتی را می‌توانی دستی بازنویسی کنی. "
                   "برای سهام و صندوق کلید را به شکل stock:نماد یا fund:نماد بنویس.",
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
    ("loan", "/loan", "تحلیل وام", "calc"),
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
SOURCE_LABELS: dict[str, str] = {"alanchand": "الان‌چند", "manual": "دستی"}
T.update({
    "refresh_now": "به‌روزرسانی از منبع",
    "source_never": "هنوز دریافتی انجام نشده",
    "source_ok": "{count} قیمت · {at}",
    "source_failed": "ناموفق · {at}",
    "no_sources": "هنوز منبع خودکاری فعال نیست؛ قیمت‌ها را دستی وارد کن.",
})
