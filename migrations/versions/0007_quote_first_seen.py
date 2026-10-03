"""quote first seen

زمان اولین مشاهده هر قیمت، برای «تغییر نسبت به ۲۴ ساعت قبل» در صفحه اصلی.

Revision ID: 0007
Revises: 0006
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import app.models

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("price_quotes") as batch:
        batch.add_column(sa.Column("first_seen_at", app.models.UTCDateTime(), nullable=True))
    op.execute("UPDATE price_quotes SET first_seen_at = fetched_at")


def downgrade() -> None:
    with op.batch_alter_table("price_quotes") as batch:
        batch.drop_column("first_seen_at")
