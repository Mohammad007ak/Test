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
    "prices_hint": "فعلاً قیمت‌ها دستی وارد می‌شوند؛ دریافت خودکار در مایلستون M2 اضافه می‌شود. "
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
