"""phase 11b alpaca history backbone

Revision ID: 20260418_02
Revises: 20260418_01
Create Date: 2026-04-18
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260418_02"
down_revision = "20260418_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("market_candles", sa.Column("source_label", sa.String(length=50), nullable=True))
    op.add_column("market_candles", sa.Column("retention_bucket", sa.String(length=50), nullable=True))


def downgrade() -> None:
    op.drop_column("market_candles", "retention_bucket")
    op.drop_column("market_candles", "source_label")
