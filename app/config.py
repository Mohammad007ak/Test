"""تنظیمات از متغیرهای محیطی یا فایل .env."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="FINASSIST_", extra="ignore")

    database_url: str = "sqlite:///./data/finassist.db"
    secret_key: str = ""
    secure_cookies: bool = False
    timezone: str = "Asia/Tehran"
    price_refresh_seconds: int = 30  # وقتی اپ باز است؛ ۰ = دریافت خودکار خاموش
    price_idle_minutes: int = 60  # وقتی کسی اپ را نگاه نمی‌کند
    sms_token: str = ""  # توکن اندپوینت پیامک؛ خالی = ساخته و در دیتابیس نگه داشته می‌شود
    sms_file: str = ""  # مسیر فایل پیامک‌ها (مثلاً در iCloud Drive) که هر دقیقه خوانده می‌شود


@lru_cache
def get_settings() -> Settings:
    return Settings()
