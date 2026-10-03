"""واردکردن پیامک از فایل متنی که Shortcuts آیفون با «Append to Text File» می‌سازد.

قالب: هر پیامک با یک خط «--- <زمان دریافت>» شروع می‌شود و تا خط «---» بعدی ادامه دارد.
زمان می‌تواند ISO (2026-10-03T09:42:00+03:30) یا شمسی (۱۴۰۵/۰۷/۱۱ ۰۹:۴۲) باشد؛
زمان بدون منطقه زمانی، به وقت تهران حساب می‌شود.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import jdatetime
from sqlalchemy.orm import Session

from app.domain.normalize import normalize_digits
from app.models import utcnow
from app.services import get_setting, set_setting
from app.sms.pipeline import ingest

MARKER = "---"
TEHRAN = ZoneInfo("Asia/Tehran")
OFFSET_KEY = "sms_file_offset:{path}"


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


def import_text(session: Session, content: str) -> dict[str, int]:
    counts = {"parsed": 0, "failed": 0, "duplicate": 0}
    for message in split_messages(content):
        counts[ingest(session, message.text, message.received_at).status] += 1
    return counts


def import_new_from_file(session: Session, path: Path) -> dict[str, int] | None:
    """فقط بخش تازه فایل (از آخرین جای خوانده‌شده)؛ اگر فایل کوتاه‌تر شده، از اول."""
    if not path.is_file():
        return None
    data = path.read_bytes()
    key = OFFSET_KEY.format(path=path.resolve())
    offset = int(get_setting(session, key) or 0)
    if offset > len(data):
        offset = 0
    new = data[offset:].decode("utf-8", errors="replace")
    counts = import_text(session, new)
    set_setting(session, key, str(len(data)))
    session.commit()
    return counts
