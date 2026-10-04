"""split (dong)

دنگ: گروه، اعضا، خرج‌ها، سهم هر نفر و تسویه‌ها؛ همه متعلق به کاربر سازنده.

Revision ID: 0011
Revises: 0010
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import app.models

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _user() -> sa.Column:
    return sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"),
                     nullable=False, index=True)


def _group() -> sa.Column:
    return sa.Column("group_id", sa.Integer(),
                     sa.ForeignKey("split_groups.id", ondelete="CASCADE"),
                     nullable=False, index=True)


def _member(name: str, primary: bool = False) -> sa.Column:
    return sa.Column(name, sa.Integer(), sa.ForeignKey("split_members.id", ondelete="CASCADE"),
                     nullable=False, primary_key=primary)


def upgrade() -> None:
    op.create_table(
        "split_groups",
        sa.Column("id", sa.Integer(), primary_key=True),
        _user(),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("share_token", sa.String(64), nullable=False, unique=True, index=True),
        sa.Column("created_at", app.models.UTCDateTime(), nullable=False),
    )
    op.create_table(
        "split_members",
        sa.Column("id", sa.Integer(), primary_key=True),
        _user(), _group(),
        sa.Column("name", sa.String(60), nullable=False),
        sa.Column("is_me", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_table(
        "split_expenses",
        sa.Column("id", sa.Integer(), primary_key=True),
        _user(), _group(),
        sa.Column("title", sa.String(100), nullable=False),
        sa.Column("amount_toman", sa.BigInteger(), nullable=False),
        _member("payer_id"),
        sa.Column("category", sa.String(50), nullable=True),
        sa.Column("spent_on", sa.Date(), nullable=False),
        sa.Column("transaction_id", sa.Integer(),
                  sa.ForeignKey("transactions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", app.models.UTCDateTime(), nullable=False),
    )
    op.create_table(
        "split_shares",
        sa.Column("expense_id", sa.Integer(),
                  sa.ForeignKey("split_expenses.id", ondelete="CASCADE"), primary_key=True),
        _member("member_id", primary=True),
        _user(),
        sa.Column("amount_toman", sa.BigInteger(), nullable=False),
    )
    op.create_table(
        "split_settlements",
        sa.Column("id", sa.Integer(), primary_key=True),
        _user(), _group(),
        _member("payer_id"), _member("payee_id"),
        sa.Column("amount_toman", sa.BigInteger(), nullable=False),
        sa.Column("created_at", app.models.UTCDateTime(), nullable=False),
    )


def downgrade() -> None:
    for table in ("split_settlements", "split_shares", "split_expenses", "split_members",
                  "split_groups"):
        op.drop_table(table)
