"""فرستنده‌های کد: sms.ir (ارسال وریفای با الگو) و ثبت در لاگ برای اجرای محلی."""

import json
import logging
import ssl
import urllib.error
import urllib.request
from collections.abc import Callable

from app.otp.base import OtpError

log = logging.getLogger("finassist.otp")

SMSIR_VERIFY_URL = "https://api.sms.ir/v1/send/verify"
TIMEOUT_SECONDS = 15

Post = Callable[[str, bytes, dict[str, str]], tuple[int, str]]


def _http_post(url: str, body: bytes, headers: dict[str, str]) -> tuple[int, str]:
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS,
                                    context=ssl.create_default_context()) as response:
            return response.status, response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", errors="replace")
    except OSError as exc:
        raise OtpError("اتصال به سرویس پیامک برقرار نشد؛ کمی بعد دوباره امتحان کن") from exc


class SmsIrSender:
    """POST /v1/send/verify با هدر X-API-KEY؛ متن پیامک الگوی تأییدشده در پنل sms.ir است."""

    name = "sms.ir"

    def __init__(self, api_key: str, template_id: int, param_name: str = "CODE",
                 post: Post = _http_post) -> None:
        self.api_key = api_key
        self.template_id = template_id
        self.param_name = param_name
        self.post = post

    def send(self, phone: str, code: str) -> None:
        body = json.dumps({"mobile": phone, "templateId": self.template_id,
                           "parameters": [{"name": self.param_name, "value": code}]})
        status, text = self.post(SMSIR_VERIFY_URL, body.encode(), {
            "X-API-KEY": self.api_key, "Content-Type": "application/json",
            "Accept": "application/json"})
        try:
            result = json.loads(text)
        except ValueError:
            result = {}
        if status == 200 and result.get("status") == 1:
            return
        message = str(result.get("message") or status)
        log.warning("sms.ir ارسال نشد: %s %s", status, message)
        raise OtpError("ارسال پیامک ناموفق بود؛ کمی بعد دوباره امتحان کن")


class LogSender:
    """بدون سرویس پیامک (اجرای محلی): کد فقط در لاگ سرور چاپ می‌شود."""

    name = "log"

    def send(self, phone: str, code: str) -> None:
        log.warning("کد تأیید %s: %s (سرویس پیامک تنظیم نشده)", phone, code)
