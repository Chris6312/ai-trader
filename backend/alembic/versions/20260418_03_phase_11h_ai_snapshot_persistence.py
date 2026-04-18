"""Phase 11H AI snapshot persistence expansion"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260418_03"
down_revision = "20260418_02"
branch_labels = None
depends_on = None


def _asset_class_col():
    return sa.Column(
        "asset_class",
        postgresql.ENUM(
            "STOCK",
            "CRYPTO",
            name="asset_class_enum",
            create_type=False,
        ),
        nullable=False,
        index=True,
    )


def _create_snapshot_table(table_name: str):

    op.create_table(

        table_name,

        sa.Column("id", sa.BigInteger(), primary_key=True),

        sa.Column(
            "symbol",
            sa.String(32),
            nullable=False,
            index=True,
        ),

        _asset_class_col(),

        sa.Column(
            "timeframe",
            sa.String(16),
            nullable=False,
            index=True,
        ),

        sa.Column(
            "snapshot_at",
            sa.DateTime(timezone=True),
            nullable=False,
            index=True,
        ),

        sa.Column(
            "score",
            sa.Numeric(10, 6),
            nullable=True,
        ),

        sa.Column(
            "components",
            sa.JSON(),
            nullable=True,
        ),

        sa.Column(
            "inputs",
            sa.JSON(),
            nullable=True,
        ),

        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),

        sa.UniqueConstraint(
            "symbol",
            "asset_class",
            "timeframe",
            "snapshot_at",
            name=f"uq_{table_name}_natural_key",
        ),
    )


def upgrade():

    _create_snapshot_table("ai_technical_snapshots")
    _create_snapshot_table("ai_sentiment_snapshots")
    _create_snapshot_table("ai_regime_snapshots")
    _create_snapshot_table("ai_universe_snapshots")


def downgrade():

    op.drop_table("ai_universe_snapshots")
    op.drop_table("ai_regime_snapshots")
    op.drop_table("ai_sentiment_snapshots")
    op.drop_table("ai_technical_snapshots")