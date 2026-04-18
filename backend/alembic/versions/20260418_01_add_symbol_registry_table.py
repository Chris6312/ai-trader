"""add symbol registry table

Revision ID: 20260418_01
Revises: 20260417_02
Create Date: 2026-04-18 01:30:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260418_01"
down_revision: str | None = "20260417_02"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


asset_class_enum = postgresql.ENUM(
    "STOCK",
    "CRYPTO",
    name="asset_class_enum",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    asset_class_enum.create(bind, checkfirst=True)

    op.create_table(
        "symbol_registry",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("symbol", sa.String(length=50), nullable=False),
        sa.Column("asset_class", asset_class_enum, nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_tradable", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("sector_or_category", sa.String(length=100), nullable=True),
        sa.Column("avg_dollar_volume", sa.Numeric(precision=20, scale=2), nullable=True),
        sa.Column("history_status", sa.String(length=30), nullable=False, server_default="pending"),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("asset_class", "symbol", name="uq_symbol_registry_asset_class_symbol"),
    )
    op.create_index(op.f("ix_symbol_registry_symbol"), "symbol_registry", ["symbol"], unique=False)
    op.create_index(op.f("ix_symbol_registry_asset_class"), "symbol_registry", ["asset_class"], unique=False)
    op.create_index(op.f("ix_symbol_registry_source"), "symbol_registry", ["source"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_symbol_registry_source"), table_name="symbol_registry")
    op.drop_index(op.f("ix_symbol_registry_asset_class"), table_name="symbol_registry")
    op.drop_index(op.f("ix_symbol_registry_symbol"), table_name="symbol_registry")
    op.drop_table("symbol_registry")
