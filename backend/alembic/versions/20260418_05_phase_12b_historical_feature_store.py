"""phase 12b historical feature store

Revision ID: 20260418_05
Revises: 20260418_04
Create Date: 2026-04-18
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260418_05"
down_revision = "20260418_04"
branch_labels = None
depends_on = None


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
        "feature_definition_versions",
        sa.Column("feature_version", sa.String(length=30), nullable=False),
        sa.Column("warmup_period", sa.Integer(), nullable=False),
        sa.Column("feature_keys_json", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("feature_version"),
    )

    op.create_table(
        "historical_feature_rows",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("decision_date", sa.Date(), nullable=False),
        sa.Column("symbol", sa.String(length=50), nullable=False),
        sa.Column("asset_class", asset_class_enum, nullable=False),
        sa.Column("timeframe", sa.String(length=10), nullable=False),
        sa.Column("candle_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_label", sa.String(length=30), nullable=False),
        sa.Column("feature_version", sa.String(length=30), nullable=False),
        sa.Column("values_json", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "decision_date",
            "symbol",
            "asset_class",
            "timeframe",
            "candle_time",
            "source_label",
            "feature_version",
            name="uq_historical_feature_row",
        ),
    )
    op.create_index(op.f("ix_historical_feature_rows_decision_date"), "historical_feature_rows", ["decision_date"], unique=False)
    op.create_index(op.f("ix_historical_feature_rows_symbol"), "historical_feature_rows", ["symbol"], unique=False)
    op.create_index(op.f("ix_historical_feature_rows_asset_class"), "historical_feature_rows", ["asset_class"], unique=False)
    op.create_index(op.f("ix_historical_feature_rows_timeframe"), "historical_feature_rows", ["timeframe"], unique=False)
    op.create_index(op.f("ix_historical_feature_rows_candle_time"), "historical_feature_rows", ["candle_time"], unique=False)
    op.create_index(op.f("ix_historical_feature_rows_source_label"), "historical_feature_rows", ["source_label"], unique=False)
    op.create_index(op.f("ix_historical_feature_rows_feature_version"), "historical_feature_rows", ["feature_version"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_historical_feature_rows_feature_version"), table_name="historical_feature_rows")
    op.drop_index(op.f("ix_historical_feature_rows_source_label"), table_name="historical_feature_rows")
    op.drop_index(op.f("ix_historical_feature_rows_candle_time"), table_name="historical_feature_rows")
    op.drop_index(op.f("ix_historical_feature_rows_timeframe"), table_name="historical_feature_rows")
    op.drop_index(op.f("ix_historical_feature_rows_asset_class"), table_name="historical_feature_rows")
    op.drop_index(op.f("ix_historical_feature_rows_symbol"), table_name="historical_feature_rows")
    op.drop_index(op.f("ix_historical_feature_rows_decision_date"), table_name="historical_feature_rows")
    op.drop_table("historical_feature_rows")
    op.drop_table("feature_definition_versions")
