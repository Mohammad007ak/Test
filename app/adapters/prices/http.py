"""دریافت صفحه‌های منابع قیمت (کتابخانه استاندارد، بدون وابستگی اضافه)."""

import ssl
import urllib.request
from pathlib import Path

from app.adapters.prices.base import PriceSourceError

USER_AGENT = "finassist/0.1 (personal net-worth tracker)"
TIMEOUT_SECONDS = 20


def _ssl_context() -> ssl.SSLContext:
    context = ssl.create_default_context()
    # پایتون مستقل (uv) روی مک گاهی گواهی‌های سیستم را پیدا نمی‌کند
    if not context.get_ca_certs() and Path("/etc/ssl/cert.pem").exists():
        context.load_verify_locations("/etc/ssl/cert.pem")
    return context


def http_get(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT,
                                                   "Accept-Language": "fa"})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS,
                                    context=_ssl_context()) as response:
            return response.read().decode("utf-8")
    except (OSError, UnicodeDecodeError) as exc:  # URLError، timeout و قطع اتصال همه OSErrorاند
        raise PriceSourceError(f"{url}: {exc}") from exc
