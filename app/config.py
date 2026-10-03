"""تنظیمات از متغیرهای محیطی یا فایل .env."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="FINASSIST_", extra="ignore")

    database_url: str = "sqlite:///./data/finassist.db"
    secret_key: str = ""
    secure_cookies: bool = False
    timezone: str = "Asia/Tehran"
    price_refresh_minutes: int = 60  # ۰ = دریافت خودکار خاموش


@lru_cache
def get_settings() -> Settings:
    return Settings()
