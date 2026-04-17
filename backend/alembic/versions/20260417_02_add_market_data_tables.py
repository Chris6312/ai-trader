"""add market data tables

Revision ID: 20260417_02
Revises: f729846edd0b
Create Date: 2026-04-17 18:15:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260417_02"
down_revision: str | None = "f729846edd0b"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


market_data_provider_enum = postgresql.ENUM(
    "kraken",
    "tradier",
    name="market_data_provider_enum",
    create_type=False,
)

market_data_asset_class_enum = postgresql.ENUM(
    "stock",
    "crypto",
    name="market_data_asset_class_enum",
    create_type=False,
)

candle_interval_enum = postgresql.ENUM(
    "1m",
    "5m",
    "15m",
    "1h",
    "4h",
    "1d",
    name="candle_interval_enum",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()

    market_data_provider_enum.create(bind, checkfirst=True)
    market_data_asset_class_enum.create(bind, checkfirst=True)
    candle_interval_enum.create(bind, checkfirst=True)

    op.create_table(
        "symbol_metadata",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("provider", market_data_provider_enum, nullable=False),
        sa.Column("asset_class", market_data_asset_class_enum, nullable=False),
        sa.Column("symbol", sa.String(length=50), nullable=False),
        sa.Column("provider_symbol", sa.String(length=80), nullable=False),
        sa.Column("base_currency", sa.String(length=20), nullable=False),
        sa.Column("quote_currency", sa.String(length=20), nullable=False),
        sa.Column("tick_size", sa.Numeric(precision=18, scale=8), nullable=True),
        sa.Column("lot_size", sa.Numeric(precision=18, scale=8), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.UniqueConstraint("provider", "symbol", name="uq_symbol_metadata_provider_symbol"),
    )
    op.create_index(op.f("ix_symbol_metadata_provider"), "symbol_metadata", ["provider"], unique=False)
    op.create_index(op.f("ix_symbol_metadata_asset_class"), "symbol_metadata", ["asset_class"], unique=False)
    op.create_index(op.f("ix_symbol_metadata_symbol"), "symbol_metadata", ["symbol"], unique=False)

    op.create_table(
        "market_candles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("provider", market_data_provider_enum, nullable=False),
        sa.Column("asset_class", market_data_asset_class_enum, nullable=False),
        sa.Column("symbol", sa.String(length=50), nullable=False),
        sa.Column("interval", candle_interval_enum, nullable=False),
        sa.Column("open_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("close_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("open_price", sa.Numeric(precision=18, scale=8), nullable=False),
        sa.Column("high_price", sa.Numeric(precision=18, scale=8), nullable=False),
        sa.Column("low_price", sa.Numeric(precision=18, scale=8), nullable=False),
        sa.Column("close_price", sa.Numeric(precision=18, scale=8), nullable=False),
        sa.Column("volume", sa.Numeric(precision=24, scale=8), nullable=False),
        sa.Column("vwap", sa.Numeric(precision=18, scale=8), nullable=True),
        sa.Column("trade_count", sa.Integer(), nullable=True),
        sa.Column("is_closed", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("source_updated_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.UniqueConstraint(
            "provider",
            "symbol",
            "interval",
            "open_time",
            name="uq_market_candles_provider_symbol_interval_open_time",
        ),
    )
    op.create_index(op.f("ix_market_candles_provider"), "market_candles", ["provider"], unique=False)
    op.create_index(op.f("ix_market_candles_asset_class"), "market_candles", ["asset_class"], unique=False)
    op.create_index(op.f("ix_market_candles_symbol"), "market_candles", ["symbol"], unique=False)
    op.create_index(op.f("ix_market_candles_interval"), "market_candles", ["interval"], unique=False)
    op.create_index(op.f("ix_market_candles_open_time"), "market_candles", ["open_time"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_market_candles_open_time"), table_name="market_candles")
    op.drop_index(op.f("ix_market_candles_interval"), table_name="market_candles")
    op.drop_index(op.f("ix_market_candles_symbol"), table_name="market_candles")
    op.drop_index(op.f("ix_market_candles_asset_class"), table_name="market_candles")
    op.drop_index(op.f("ix_market_candles_provider"), table_name="market_candles")
    op.drop_table("market_candles")

    op.drop_index(op.f("ix_symbol_metadata_symbol"), table_name="symbol_metadata")
    op.drop_index(op.f("ix_symbol_metadata_asset_class"), table_name="symbol_metadata")
    op.drop_index(op.f("ix_symbol_metadata_provider"), table_name="symbol_metadata")
    op.drop_table("symbol_metadata")

    bind = op.get_bind()
    candle_interval_enum.drop(bind, checkfirst=True)
    market_data_asset_class_enum.drop(bind, checkfirst=True)
    market_data_provider_enum.drop(bind, checkfirst=True)