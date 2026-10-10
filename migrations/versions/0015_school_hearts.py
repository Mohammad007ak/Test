"""school hearts, placement levels, premium

نوار جان و سطح هر تاپیک در مدرسه؛ تاریخ پایان اشتراک وزیر ویژه برای کاربر.

Revision ID: 0015
Revises: 0014
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import app.models

revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("premium_until", app.models.UTCDateTime(), nullable=True))
    with op.batch_alter_table("school_stats") as batch:
        batch.add_column(sa.Column("hearts", sa.Integer(), nullable=False, server_default="5"))
        batch.add_column(sa.Column("hearts_since", app.models.UTCDateTime(), nullable=True))
        batch.add_column(sa.Column("levels", sa.String(200), nullable=False, server_default=""))


def downgrade() -> None:
    with op.batch_alter_table("school_stats") as batch:
        batch.drop_column("levels")
        batch.drop_column("hearts_since")
        batch.drop_column("hearts")
    with op.batch_alter_table("users") as batch:
        batch.drop_column("premium_until")
