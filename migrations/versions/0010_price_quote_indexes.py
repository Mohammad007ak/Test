"""price quote indexes

ایندکس‌های ترکیبی برای آخرین قیمت هر کلید و قیمت در یک لحظه؛ بدون آن‌ها با بزرگ شدن
جدول قیمت، هر صفحه چند ثانیه طول می‌کشید.

Revision ID: 0010
Revises: 0009
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index("ix_price_quotes_key_fetched_user", "price_quotes",
                    ["key", "fetched_at", "user_id"])
    op.create_index("ix_price_quotes_key_first_seen", "price_quotes",
                    ["key", "first_seen_at", "id"])


def downgrade() -> None:
    op.drop_index("ix_price_quotes_key_first_seen", "price_quotes")
    op.drop_index("ix_price_quotes_key_fetched_user", "price_quotes")
