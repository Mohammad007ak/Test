"""ابزار مشترک تست‌های یکپارچه: فرستنده کد ساختگی و ثبت‌نام کامل یک کاربر."""

from fastapi.testclient import TestClient

PASSWORD = "very-secret-1"
PHONE = "09121111111"


class FakeSender:
    """به‌جای sms.ir: آخرین کد هر شماره را نگه می‌دارد."""

    name = "fake"

    def __init__(self) -> None:
        self.codes: dict[str, str] = {}

    def send(self, phone: str, code: str) -> None:
        self.codes[phone] = code


def last_code(client: TestClient, phone: str) -> str:
    from app.domain.phone import normalize_phone

    return client.app.state.otp_sender.codes[normalize_phone(phone)]  # type: ignore[attr-defined]


def register(client: TestClient, phone: str = PHONE, password: str = PASSWORD) -> None:
    response = client.post("/signup", data={"phone": phone}, follow_redirects=False)
    assert response.headers["location"] == "/verify", response.text
    response = client.post("/verify", data={"code": last_code(client, phone), "password": password,
                                            "password_repeat": password}, follow_redirects=False)
    assert response.status_code == 303 and response.headers["location"] == "/", response.text
