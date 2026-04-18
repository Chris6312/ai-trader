"""Phase 12D historical replay labels"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260418_07"
down_revision = "20260418_06"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "label_policy_versions",
        sa.Column("label_version", sa.String(length=30), primary_key=True),
        sa.Column("policy_name", sa.String(length=50), nullable=False),
        sa.Column("success_threshold_return", sa.Numeric(12, 8), nullable=False),
        sa.Column("max_drawdown_return", sa.Numeric(12, 8), nullable=False),
        sa.Column("require_target_before_stop", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("max_hold_bars", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "historical_replay_labels",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("decision_date", sa.Date(), nullable=False),
        sa.Column("symbol", sa.String(length=50), nullable=False),
        sa.Column(
            "asset_class",
            postgresql.ENUM("STOCK", "CRYPTO", name="asset_class_enum", create_type=False),
            nullable=False,
        ),
        sa.Column("timeframe", sa.String(length=10), nullable=False),
        sa.Column("strategy_name", sa.String(length=50), nullable=False),
        sa.Column("entry_candle_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_label", sa.String(length=30), nullable=False),
        sa.Column("replay_version", sa.String(length=30), nullable=False),
        sa.Column("label_version", sa.String(length=30), nullable=False),
        sa.Column("is_trade_profitable", sa.Boolean(), nullable=False),
        sa.Column("hit_target_before_stop", sa.Boolean(), nullable=False),
        sa.Column("follow_through_strength", sa.Numeric(12, 8), nullable=False),
        sa.Column("drawdown_within_limit", sa.Boolean(), nullable=False),
        sa.Column("achieved_label", sa.Boolean(), nullable=False),
        sa.Column("label_values_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["label_version"], ["label_policy_versions.label_version"]),
        sa.UniqueConstraint(
            "decision_date",
            "symbol",
            "asset_class",
            "timeframe",
            "strategy_name",
            "entry_candle_time",
            "label_version",
            name="uq_historical_replay_label_row",
        ),
    )
    op.create_index("ix_historical_replay_labels_decision_date", "historical_replay_labels", ["decision_date"], unique=False)
    op.create_index("ix_historical_replay_labels_symbol", "historical_replay_labels", ["symbol"], unique=False)
    op.create_index("ix_historical_replay_labels_asset_class", "historical_replay_labels", ["asset_class"], unique=False)
    op.create_index("ix_historical_replay_labels_timeframe", "historical_replay_labels", ["timeframe"], unique=False)
    op.create_index("ix_historical_replay_labels_strategy_name", "historical_replay_labels", ["strategy_name"], unique=False)
    op.create_index("ix_historical_replay_labels_entry_candle_time", "historical_replay_labels", ["entry_candle_time"], unique=False)
    op.create_index("ix_historical_replay_labels_source_label", "historical_replay_labels", ["source_label"], unique=False)
    op.create_index("ix_historical_replay_labels_label_version", "historical_replay_labels", ["label_version"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_historical_replay_labels_label_version", table_name="historical_replay_labels")
    op.drop_index("ix_historical_replay_labels_source_label", table_name="historical_replay_labels")
    op.drop_index("ix_historical_replay_labels_entry_candle_time", table_name="historical_replay_labels")
    op.drop_index("ix_historical_replay_labels_strategy_name", table_name="historical_replay_labels")
    op.drop_index("ix_historical_replay_labels_timeframe", table_name="historical_replay_labels")
    op.drop_index("ix_historical_replay_labels_asset_class", table_name="historical_replay_labels")
    op.drop_index("ix_historical_replay_labels_symbol", table_name="historical_replay_labels")
    op.drop_index("ix_historical_replay_labels_decision_date", table_name="historical_replay_labels")
    op.drop_table("historical_replay_labels")
    op.drop_table("label_policy_versions")
