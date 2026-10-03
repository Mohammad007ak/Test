import json
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db import Base
from app.otp import OtpError, OtpService, SmsIrSender


class FakeSender:
    name = "fake"

    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []

    def send(self, phone: str, code: str) -> None:
        self.sent.append((phone, code))


class Clock:
    def __init__(self) -> None:
        self.now = datetime(2026, 10, 3, 9, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now


@pytest.fixture
def env():  # type: ignore[no-untyped-def]
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    sender, clock = FakeSender(), Clock()
    service = OtpService(sender, secret="s3cret", daily_limit=50, clock=clock)
    with Session(engine) as session:
        yield session, service, sender, clock


PHONE = "09121234567"


def test_issue_and_verify_once(env) -> None:  # type: ignore[no-untyped-def]
    session, service, sender, _ = env
    service.issue(session, PHONE, "signup", ip="1.1.1.1")
    (phone, code), = sender.sent
    assert phone == PHONE and len(code) == 6 and code.isdigit()
    assert not service.verify(session, PHONE, "reset", code)  # هدف دیگر
    assert service.verify(session, PHONE, "signup", code)
    assert not service.verify(session, PHONE, "signup", code)  # یک‌بارمصرف


def test_code_is_not_stored_in_plain_text(env) -> None:  # type: ignore[no-untyped-def]
    from sqlalchemy import select

    from app.models import OtpCode

    session, service, sender, _ = env
    service.issue(session, PHONE, "signup", ip="")
    code = sender.sent[0][1]
    row = session.scalars(select(OtpCode)).one()
    assert code not in row.code_hash


def test_expires(env) -> None:  # type: ignore[no-untyped-def]
    session, service, sender, clock = env
    service.issue(session, PHONE, "signup", ip="")
    clock.now += timedelta(minutes=6)
    assert not service.verify(session, PHONE, "signup", sender.sent[0][1])


def test_wrong_attempts_burn_the_code(env) -> None:  # type: ignore[no-untyped-def]
    session, service, sender, _ = env
    service.issue(session, PHONE, "signup", ip="")
    code = sender.sent[0][1]
    wrong = "000000" if code != "000000" else "111111"
    for _ in range(5):
        assert not service.verify(session, PHONE, "signup", wrong)
    assert not service.verify(session, PHONE, "signup", code)


def test_resend_cooldown_and_hourly_cap(env) -> None:  # type: ignore[no-untyped-def]
    session, service, _, clock = env
    service.issue(session, PHONE, "signup", ip="")
    with pytest.raises(OtpError, match="ثانیه"):
        service.issue(session, PHONE, "signup", ip="")
    for _ in range(4):
        clock.now += timedelta(seconds=61)
        service.issue(session, PHONE, "signup", ip="")
    clock.now += timedelta(seconds=61)
    with pytest.raises(OtpError):
        service.issue(session, PHONE, "signup", ip="")


def test_newest_code_replaces_older(env) -> None:  # type: ignore[no-untyped-def]
    session, service, sender, clock = env
    service.issue(session, PHONE, "signup", ip="")
    clock.now += timedelta(seconds=61)
    service.issue(session, PHONE, "signup", ip="")
    old, new = sender.sent[0][1], sender.sent[1][1]
    if old != new:
        assert not service.verify(session, PHONE, "signup", old)
    assert service.verify(session, PHONE, "signup", new)


def test_ip_cap(env) -> None:  # type: ignore[no-untyped-def]
    session, service, _, _ = env
    for i in range(10):
        service.issue(session, f"0912000{i:04d}", "signup", ip="6.6.6.6")
    with pytest.raises(OtpError):
        service.issue(session, "09129999999", "signup", ip="6.6.6.6")


def test_daily_cap(env) -> None:  # type: ignore[no-untyped-def]
    session, _, sender, clock = env
    service = OtpService(sender, secret="x", daily_limit=2, clock=clock)
    service.issue(session, "09120000001", "signup", ip="a")
    service.issue(session, "09120000002", "signup", ip="b")
    with pytest.raises(OtpError):
        service.issue(session, "09120000003", "signup", ip="c")


def test_failed_send_does_not_leave_valid_code(env) -> None:  # type: ignore[no-untyped-def]
    session, _, _, clock = env

    class Broken:
        name = "broken"

        def send(self, phone: str, code: str) -> None:
            raise OtpError("ارسال نشد")

    service = OtpService(Broken(), secret="x", daily_limit=10, clock=clock)
    with pytest.raises(OtpError):
        service.issue(session, PHONE, "signup", ip="")
    from sqlalchemy import func, select

    from app.models import OtpCode
    assert session.scalar(select(func.count()).select_from(OtpCode)) == 0


def test_smsir_request_shape() -> None:
    calls = []

    def post(url: str, body: bytes, headers: dict[str, str]) -> tuple[int, str]:
        calls.append((url, json.loads(body), headers))
        return 200, json.dumps({"status": 1, "message": "موفق", "data": {"messageId": 1}})

    SmsIrSender("KEY", 123456, "CODE", post=post).send(PHONE, "482913")
    url, body, headers = calls[0]
    assert url == "https://api.sms.ir/v1/send/verify"
    assert body == {"mobile": PHONE, "templateId": 123456,
                    "parameters": [{"name": "CODE", "value": "482913"}]}
    assert headers["X-API-KEY"] == "KEY"


def test_smsir_error_is_reported_without_code() -> None:
    def post(url: str, body: bytes, headers: dict[str, str]) -> tuple[int, str]:
        return 400, json.dumps({"status": 0, "message": "اعتبار کافی نیست"})

    with pytest.raises(OtpError) as exc:
        SmsIrSender("KEY", 1, "CODE", post=post).send(PHONE, "482913")
    assert "482913" not in str(exc.value)
