"""تنظیمات از متغیرهای محیطی یا فایل .env."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="FINASSIST_", extra="ignore")

    database_url: str = "sqlite:///./data/finassist.db"
    secret_key: str = ""
    secure_cookies: bool = False
    public_url: str = ""  # آدرس اصلی سایت برای sitemap و canonical، مثل https://getvazir.ir
    timezone: str = "Asia/Tehran"
    price_refresh_seconds: int = 30  # وقتی اپ باز است؛ ۰ = دریافت خودکار خاموش
    price_idle_minutes: int = 60  # وقتی کسی اپ را نگاه نمی‌کند
    # کد تأیید پیامکی (ثبت‌نام و بازیابی رمز) از sms.ir؛ خالی = کد فقط در لاگ سرور چاپ می‌شود
    smsir_api_key: str = ""
    smsir_template_id: int = 0
    smsir_param: str = "CODE"  # نام متغیر کد در الگوی پیامک
    otp_daily_limit: int = 300  # سقف کل پیامک کد در ۲۴ ساعت (سپر هزینه)
    # فقط این شماره‌ها ثبت‌نام می‌کنند (با کاما جدا)؛ خالی = ثبت‌نام برای همه باز
    signup_allowlist: str = ""
    # صاحب داده‌های نسخه تک‌کاربره؛ با ثبت‌نام این شماره همان داده‌ها را تحویل می‌گیرد
    owner_phone: str = ""
    # اگر پر باشد، حساب owner_phone با این رمز ساخته یا به‌روز می‌شود (بی‌نیاز از کد پیامکی)
    owner_password: str = ""
    # دستیار «از وزیر بپرس»: مدل زبانی با API سازگار با OpenAI؛ خالی = خاموش
    llm_url: str = ""
    llm_key: str = ""
    llm_model: str = ""
    llm_daily_limit: int = 30  # سؤال در روز برای هر کاربر
    # open = پیشنهاد مشخص مالی و سرمایه‌گذاری (محیط آزمایشی)؛ strict = فقط تحلیل (بدون مجوز مشاوره)
    llm_mode: str = "open"


@lru_cache
def get_settings() -> Settings:
    return Settings()
