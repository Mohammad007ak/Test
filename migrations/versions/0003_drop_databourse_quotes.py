"""drop databourse quotes

قیمت‌های databourse.ir نادرست بودند و این منبع حذف شده؛ قیمت‌های ذخیره‌شده‌اش
پاک می‌شوند تا جای قیمت شاخص‌بان یا ورود دستی را نگیرند.

Revision ID: 0003
Revises: 0002
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("DELETE FROM price_quotes WHERE source = 'databourse'")
    op.execute("DELETE FROM settings WHERE key = 'price_source_status:databourse'")


def downgrade() -> None:
    pass  # داده پاک‌شده برنمی‌گردد
