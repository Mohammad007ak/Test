"""multi user

کاربران (نام کاربری = موبایل)، کد یک‌بارمصرف، تنظیمات هر کاربر و user_id روی همه داده‌های
شخصی. داده‌های نسخه تک‌کاربره به کاربر شماره ۱ (بدون شماره) می‌رسد تا صاحبش با شماره‌ای
که در FINASSIST_OWNER_PHONE آمده ثبت‌نام کند و همان حساب را تحویل بگیرد.

Revision ID: 0006
Revises: 0005
"""

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

import app.models

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OWNED = ("assets", "accounts", "transactions", "sms_inbox", "liabilities", "income_streams",
         "expense_streams", "loan_analyses")
USER_SETTINGS = ("dti_threshold", "inflation", "sms_ingest_token")
LEGACY_USER = 1


def _has_legacy_data(conn: sa.Connection) -> bool:
    if conn.execute(sa.text("SELECT 1 FROM settings WHERE key = 'password_hash'")).first():
        return True
    return any(conn.execute(sa.text(f"SELECT 1 FROM {table} LIMIT 1")).first()
               for table in (*OWNED, "networth_snapshots"))


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("phone", sa.String(length=11), nullable=True, unique=True),
        sa.Column("password_hash", sa.String(length=200), nullable=True),
        sa.Column("session_version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", app.models.UTCDateTime(), nullable=False),
    )
    op.create_table(
        "user_settings",
        sa.Column("key", sa.String(length=100), primary_key=True),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"),
                  primary_key=True),
    )
    op.create_index("ix_user_settings_user_id", "user_settings", ["user_id"])
    op.create_table(
        "otp_codes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("phone", sa.String(length=11), nullable=False),
        sa.Column("purpose", sa.String(length=10), nullable=False),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("ip", sa.String(length=64), nullable=False),
        sa.Column("created_at", app.models.UTCDateTime(), nullable=False),
        sa.Column("expires_at", app.models.UTCDateTime(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("used", sa.Boolean(), nullable=False),
    )
    op.create_index("ix_otp_codes_phone", "otp_codes", ["phone"])
    op.create_index("ix_otp_codes_created_at", "otp_codes", ["created_at"])

    conn = op.get_bind()
    legacy = _has_legacy_data(conn)
    if legacy:
        row = conn.execute(sa.text("SELECT value FROM settings WHERE key = 'password_hash'")).first()
        conn.execute(sa.text("INSERT INTO users (id, phone, password_hash, session_version,"
                             " created_at) VALUES (:id, NULL, :hash, 0, :now)"),
                     {"id": LEGACY_USER, "hash": row[0] if row else None,
                      "now": datetime.now(UTC).replace(tzinfo=None).isoformat(sep=" ")})
        for key in USER_SETTINGS:
            conn.execute(sa.text("INSERT INTO user_settings (key, value, user_id)"
                                 " SELECT key, value, :id FROM settings WHERE key = :key"),
                         {"id": LEGACY_USER, "key": key})
    conn.execute(sa.text("DELETE FROM settings WHERE key IN"
                         " ('password_hash', 'dti_threshold', 'inflation', 'sms_ingest_token')"))

    for table in OWNED:
        with op.batch_alter_table(table) as batch:
            batch.add_column(sa.Column("user_id", sa.Integer(), nullable=True))
        if legacy:
            conn.execute(sa.text(f"UPDATE {table} SET user_id = :id"), {"id": LEGACY_USER})
        with op.batch_alter_table(table) as batch:
            batch.alter_column("user_id", existing_type=sa.Integer(), nullable=False)
            batch.create_foreign_key(f"fk_{table}_user_id", "users", ["user_id"], ["id"],
                                     ondelete="CASCADE")
            batch.create_index(f"ix_{table}_user_id", ["user_id"])

    with op.batch_alter_table("price_quotes") as batch:
        batch.add_column(sa.Column("user_id", sa.Integer(), nullable=True))
        batch.create_foreign_key("fk_price_quotes_user_id", "users", ["user_id"], ["id"],
                                 ondelete="CASCADE")
    if legacy:  # قیمت‌های دستی قبلی متعلق به همان کاربر است
        conn.execute(sa.text("UPDATE price_quotes SET user_id = :id WHERE source = 'manual'"),
                     {"id": LEGACY_USER})

    op.create_table(
        "networth_snapshots_new",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"),
                  primary_key=True),
        sa.Column("date", sa.Date(), primary_key=True),
        sa.Column("assets_toman", sa.BigInteger(), nullable=False),
        sa.Column("liabilities_toman", sa.BigInteger(), nullable=False),
        sa.Column("networth_toman", sa.BigInteger(), nullable=False),
        sa.Column("usd_rate", sa.BigInteger(), nullable=True),
        sa.Column("gold18_rate", sa.BigInteger(), nullable=True),
    )
    if legacy:
        conn.execute(sa.text(
            "INSERT INTO networth_snapshots_new (user_id, date, assets_toman, liabilities_toman,"
            " networth_toman, usd_rate, gold18_rate) SELECT :id, date, assets_toman,"
            " liabilities_toman, networth_toman, usd_rate, gold18_rate FROM networth_snapshots"),
            {"id": LEGACY_USER})
    op.drop_table("networth_snapshots")
    op.rename_table("networth_snapshots_new", "networth_snapshots")
    op.create_index("ix_networth_snapshots_user_id", "networth_snapshots", ["user_id"])


def downgrade() -> None:
    raise NotImplementedError("بازگشت به نسخه تک‌کاربره پشتیبانی نمی‌شود؛ از پشتیبان استفاده کن")
