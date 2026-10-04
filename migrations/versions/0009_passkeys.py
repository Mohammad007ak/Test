"""passkeys

ورود با چهره یا اثر انگشت (WebAuthn/Passkey): کلید عمومی هر دستگاه کاربر.

Revision ID: 0009
Revises: 0008
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import app.models

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "passkeys",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("credential_id", sa.String(512), nullable=False, unique=True, index=True),
        sa.Column("public_key", sa.LargeBinary(), nullable=False),
        sa.Column("sign_count", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("created_at", app.models.UTCDateTime(), nullable=False),
        sa.Column("last_used_at", app.models.UTCDateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("passkeys")
