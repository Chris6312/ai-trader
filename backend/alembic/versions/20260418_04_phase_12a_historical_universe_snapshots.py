"""Phase 12A historical universe snapshots"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260418_04"
down_revision = "20260418_03"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "historical_universe_snapshots",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("decision_date", sa.Date(), nullable=False),
        sa.Column("symbol", sa.String(length=50), nullable=False),
        sa.Column(
            "asset_class",
            postgresql.ENUM("STOCK", "CRYPTO", name="asset_class_enum", create_type=False),
            nullable=False,
        ),
        sa.Column("source_label", sa.String(length=30), nullable=False),
        sa.Column("registry_source", sa.String(length=50), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_tradable", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("history_status", sa.String(length=30), nullable=False),
        sa.Column("sector_or_category", sa.String(length=100), nullable=True),
        sa.Column("avg_dollar_volume", sa.Numeric(20, 2), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint(
            "decision_date",
            "asset_class",
            "symbol",
            name="uq_historical_universe_snapshot_row",
        ),
    )
    op.create_index(
        "ix_historical_universe_snapshots_decision_date",
        "historical_universe_snapshots",
        ["decision_date"],
        unique=False,
    )
    op.create_index(
        "ix_historical_universe_snapshots_symbol",
        "historical_universe_snapshots",
        ["symbol"],
        unique=False,
    )
    op.create_index(
        "ix_historical_universe_snapshots_asset_class",
        "historical_universe_snapshots",
        ["asset_class"],
        unique=False,
    )
    op.create_index(
        "ix_historical_universe_snapshots_source_label",
        "historical_universe_snapshots",
        ["source_label"],
        unique=False,
    )
    op.create_index(
        "ix_historical_universe_snapshots_registry_source",
        "historical_universe_snapshots",
        ["registry_source"],
        unique=False,
    )


def downgrade():
    op.drop_index("ix_historical_universe_snapshots_registry_source", table_name="historical_universe_snapshots")
    op.drop_index("ix_historical_universe_snapshots_source_label", table_name="historical_universe_snapshots")
    op.drop_index("ix_historical_universe_snapshots_asset_class", table_name="historical_universe_snapshots")
    op.drop_index("ix_historical_universe_snapshots_symbol", table_name="historical_universe_snapshots")
    op.drop_index("ix_historical_universe_snapshots_decision_date", table_name="historical_universe_snapshots")
    op.drop_table("historical_universe_snapshots")
