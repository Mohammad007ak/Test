"""نشست دیتابیس حافظه‌ای که به یک کاربر آزمایشی محدود است (مثل درخواست وب)."""

from sqlalchemy.orm import Session

from app.db import Base, make_engine, make_session_factory, user_session
from app.models import User


def memory_session() -> Session:
    engine = make_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = make_session_factory(engine)()
    session.add(User(id=1, phone="09120000001"))
    session.commit()
    return user_session(session, 1)
