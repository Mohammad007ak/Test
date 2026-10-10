"""sms templates

قالب‌های یادگرفته مشترک پیامک، انتخاب حساب کاربر برای پیامک‌ها، و خوانده منتظر انتخاب حساب.

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


def upgrade() -> None:
    op.create_table(
        "sms_templates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("pattern", sa.Text(), nullable=False),
        sa.Column("pattern_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("bank", sa.String(50), nullable=False),
        sa.Column("direction", sa.String(3), nullable=False),
        sa.Column("unit", sa.String(5), nullable=False),
        sa.Column("label", sa.String(100), nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("created_at", app.models.UTCDateTime(), nullable=False),
        sa.Column("activated_at", app.models.UTCDateTime(), nullable=True),
    )
    op.create_table(
        "account_aliases",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("account_id", sa.Integer(),
                  sa.ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("bank", sa.String(50), nullable=False),
        sa.Column("account_mask", sa.String(4), nullable=False),
        sa.Column("account_prefix", sa.String(4), nullable=False),
    )
    with op.batch_alter_table("sms_inbox") as batch:
        batch.add_column(sa.Column("parsed_json", sa.Text(), nullable=True))
        batch.add_column(sa.Column("template_id", sa.Integer(), nullable=True))
        batch.create_foreign_key("fk_sms_inbox_template", "sms_templates", ["template_id"],
                                 ["id"], ondelete="SET NULL")


def downgrade() -> None:
    with op.batch_alter_table("sms_inbox") as batch:
        batch.drop_constraint("fk_sms_inbox_template", type_="foreignkey")
        batch.drop_column("template_id")
        batch.drop_column("parsed_json")
    op.drop_table("account_aliases")
    op.drop_table("sms_templates")
