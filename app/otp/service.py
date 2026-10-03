"""صدور و بررسی کد: ۶ رقم، ۵ دقیقه اعتبار، ۵ بار تلاش، فقط هش ذخیره می‌شود.

محدودیت‌ها هزینه پیامک را در برابر سوءاستفاده نگه می‌دارند: فاصله ۶۰ ثانیه بین دو ارسال
به یک شماره، ۵ ارسال در ساعت برای هر شماره، ۱۰ در ساعت از هر IP و سقف روزانه کل.
"""

import hashlib
import hmac
import secrets
from collections.abc import Callable
from datetime import datetime, timedelta

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from app.models import OtpCode, utcnow
from app.otp.base import OtpError, OtpSender

CODE_TTL = timedelta(minutes=5)
RESEND_AFTER = timedelta(seconds=60)
PER_PHONE_HOURLY = 5
PER_IP_HOURLY = 10
MAX_ATTEMPTS = 5


class OtpService:
    def __init__(self, sender: OtpSender, secret: str, daily_limit: int,
                 clock: Callable[[], datetime] = utcnow) -> None:
        self.sender = sender
        self.secret = secret.encode()
        self.daily_limit = daily_limit
        self.clock = clock

    def _hash(self, phone: str, purpose: str, code: str) -> str:
        return hmac.new(self.secret, f"{purpose}:{phone}:{code}".encode(),
                        hashlib.sha256).hexdigest()

    def _count_since(self, session: Session, since: datetime, *where: object) -> int:
        query = select(func.count()).select_from(OtpCode).where(OtpCode.created_at >= since,
                                                                 *where)  # type: ignore[arg-type]
        return session.scalar(query) or 0

    def _check_limits(self, session: Session, phone: str, ip: str, now: datetime) -> None:
        last = session.scalar(select(func.max(OtpCode.created_at)).where(OtpCode.phone == phone))
        if last is not None and now - last < RESEND_AFTER:
            wait = int((RESEND_AFTER - (now - last)).total_seconds()) + 1
            raise OtpError(f"برای ارسال دوباره {wait} ثانیه صبر کن")
        hour = now - timedelta(hours=1)
        if self._count_since(session, hour, OtpCode.phone == phone) >= PER_PHONE_HOURLY:
            raise OtpError("تعداد درخواست کد برای این شماره زیاد شد؛ یک ساعت دیگر امتحان کن")
        if ip and self._count_since(session, hour, OtpCode.ip == ip) >= PER_IP_HOURLY:
            raise OtpError("درخواست‌ها زیاد شد؛ یک ساعت دیگر امتحان کن")
        if self._count_since(session, now - timedelta(days=1)) >= self.daily_limit:
            raise OtpError("ارسال کد موقتاً متوقف است؛ بعداً امتحان کن")

    def issue(self, session: Session, phone: str, purpose: str, ip: str) -> None:
        now = self.clock()
        self._check_limits(session, phone, ip, now)
        code = f"{secrets.randbelow(10 ** 6):06d}"
        self.sender.send(phone, code)  # اگر نرسید، کدی هم ثبت نمی‌شود
        session.execute(delete(OtpCode).where(OtpCode.created_at < now - timedelta(days=2)))
        session.execute(update(OtpCode).where(OtpCode.phone == phone, OtpCode.purpose == purpose,
                                              OtpCode.used.is_(False)).values(used=True))
        session.add(OtpCode(phone=phone, purpose=purpose,
                            code_hash=self._hash(phone, purpose, code),
                            ip=ip[:64], created_at=now, expires_at=now + CODE_TTL))
        session.commit()

    def verify(self, session: Session, phone: str, purpose: str, code: str) -> bool:
        now = self.clock()
        row = session.scalars(select(OtpCode).where(
            OtpCode.phone == phone, OtpCode.purpose == purpose, OtpCode.used.is_(False))
            .order_by(OtpCode.id.desc())).first()
        if row is None or row.expires_at <= now or row.attempts >= MAX_ATTEMPTS:
            return False
        if hmac.compare_digest(row.code_hash, self._hash(phone, purpose, code.strip())):
            row.used = True
            session.commit()
            return True
        row.attempts += 1
        session.commit()
        return False
