"""user admin fields

آخرین بازدید و غیرفعال‌سازی کاربر برای پنل مدیریت.

Revision ID: 0012
Revises: 0011
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import app.models

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("last_seen_at", app.models.UTCDateTime(), nullable=True))
        batch.add_column(sa.Column("disabled_at", app.models.UTCDateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.drop_column("disabled_at")
        batch.drop_column("last_seen_at")
