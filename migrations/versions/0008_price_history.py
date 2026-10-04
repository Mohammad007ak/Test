"""price history

آرشیو قیمت پایانی روزانه برای نمودار هفتگی تا پنج‌ساله و تحلیل تکنیکال.

Revision ID: 0008
Revises: 0007
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "price_history",
        sa.Column("key", sa.String(100), primary_key=True),
        sa.Column("day", sa.Date(), primary_key=True),
        sa.Column("price_toman", sa.BigInteger(), nullable=False),
        sa.Column("real_price_toman", sa.BigInteger(), nullable=True),
        sa.Column("source", sa.String(50), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("price_history")
