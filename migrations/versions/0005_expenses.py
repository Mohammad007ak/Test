"""expenses

هزینه‌های ثابت تکراری، و خرج دستی بدون حساب بانکی (account_id خالی).

Revision ID: 0005
Revises: 0004
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "expense_streams",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("amount_toman", sa.BigInteger(), nullable=False),
        sa.Column("frequency", sa.String(length=10), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False),
    )
    with op.batch_alter_table("transactions", schema=None) as batch_op:
        batch_op.alter_column("account_id", existing_type=sa.Integer(), nullable=True)


def downgrade() -> None:
    op.execute("DELETE FROM transactions WHERE account_id IS NULL")
    with op.batch_alter_table("transactions", schema=None) as batch_op:
        batch_op.alter_column("account_id", existing_type=sa.Integer(), nullable=False)
    op.drop_table("expense_streams")
