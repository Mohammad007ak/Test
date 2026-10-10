"""school

مدرسه وزیر: پیشرفت درس‌ها و امتیاز، زنجیره و دانش هر کاربر.

Revision ID: 0013
Revises: 0012
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import app.models

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _user() -> sa.Column:
    return sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"),
                     primary_key=True, index=True)


def upgrade() -> None:
    op.create_table(
        "lesson_progress",
        _user(),
        sa.Column("lesson_slug", sa.String(60), primary_key=True),
        sa.Column("course", sa.String(40), nullable=False),
        sa.Column("best_correct", sa.Integer(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("completed_at", app.models.UTCDateTime(), nullable=False),
    )
    op.create_table(
        "school_stats",
        _user(),
        sa.Column("xp", sa.BigInteger(), nullable=False),
        sa.Column("knowledge", sa.Integer(), nullable=False),
        sa.Column("streak", sa.Integer(), nullable=False),
        sa.Column("best_streak", sa.Integer(), nullable=False),
        sa.Column("last_day", sa.Date(), nullable=True),
        sa.Column("freeze_day", sa.Date(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("school_stats")
    op.drop_table("lesson_progress")
