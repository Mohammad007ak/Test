"""واردکردن پیامک از فایل متنی که Shortcuts آیفون با «Append to Text File» می‌سازد.

قالب: هر پیامک با یک خط «--- <زمان دریافت>» شروع می‌شود و تا خط «---» بعدی ادامه دارد.
زمان می‌تواند ISO (2026-10-03T09:42:00+03:30) یا شمسی (۱۴۰۵/۰۷/۱۱ ۰۹:۴۲) باشد؛
زمان بدون منطقه زمانی، به وقت تهران حساب می‌شود.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import jdatetime
from sqlalchemy.orm import Session

from app.domain.normalize import normalize_digits
from app.models import utcnow
from app.sms.llm import LLMClient
from app.sms.pipeline import ingest
from app.sms.text import is_secret

MARKER = "---"
TEHRAN = ZoneInfo("Asia/Tehran")


@dataclass(frozen=True)
class RawMessage:
    received_at: datetime
    text: str


def parse_time(text: str) -> datetime:
    text = normalize_digits(text).strip()
    try:
        moment = datetime.fromisoformat(text)
    except ValueError:
        moment = None
    if moment is None:
        date_part, _, time_part = text.partition(" ")
        year, month, day = (int(p) for p in date_part.split("/"))
        hour, minute = (int(p) for p in (time_part or "0:0").split(":")[:2])
        moment = jdatetime.datetime(year, month, day, hour, minute).togregorian()
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=TEHRAN)
    return moment.astimezone(UTC)


def split_messages(content: str) -> list[RawMessage]:
    messages: list[RawMessage] = []
    current: datetime | None = None
    lines: list[str] = []

    def flush() -> None:
        body = "\n".join(lines).strip()
        if current is not None and body:
            messages.append(RawMessage(current, body))

    for line in content.splitlines():
        if line.startswith(MARKER):
            flush()
            lines = []
            try:
                current = parse_time(line[len(MARKER):])
            except (ValueError, TypeError):
                current = utcnow()  # زمان ناخوانا؛ پیامک گم نشود
        else:
            lines.append(line)
    flush()
    return messages


def import_text(session: Session, content: str, llm: LLMClient | None = None) -> dict[str, int]:
    counts = {"parsed": 0, "failed": 0, "duplicate": 0, "ignored": 0}
    for message in split_messages(content):
        if is_secret(message.text):  # رمز و کد: نه ذخیره، نه پردازش
            counts["ignored"] += 1
            continue
        counts[ingest(session, message.text, message.received_at, llm=llm).status] += 1
    return counts
