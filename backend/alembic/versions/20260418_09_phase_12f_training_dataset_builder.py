"""Phase 12F training dataset builder"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260418_09"
down_revision = "20260418_08"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "training_dataset_versions",
        sa.Column("dataset_version", sa.String(length=40), primary_key=True),
        sa.Column("dataset_name", sa.String(length=80), nullable=False),
        sa.Column("dataset_definition_version", sa.String(length=30), nullable=False),
        sa.Column(
            "asset_class",
            postgresql.ENUM("STOCK", "CRYPTO", name="asset_class_enum", create_type=False),
            nullable=False,
        ),
        sa.Column("timeframe", sa.String(length=10), nullable=False),
        sa.Column("source_label", sa.String(length=30), nullable=True),
        sa.Column("strategy_name", sa.String(length=50), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("policy_version", sa.String(length=30), nullable=False),
        sa.Column("feature_version", sa.String(length=30), nullable=False),
        sa.Column("replay_version", sa.String(length=30), nullable=False),
        sa.Column("label_version", sa.String(length=30), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("feature_keys_json", sa.JSON(), nullable=False),
        sa.Column("build_metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_training_dataset_versions_asset_class", "training_dataset_versions", ["asset_class"], unique=False)
    op.create_index("ix_training_dataset_versions_timeframe", "training_dataset_versions", ["timeframe"], unique=False)
    op.create_index("ix_training_dataset_versions_source_label", "training_dataset_versions", ["source_label"], unique=False)
    op.create_index("ix_training_dataset_versions_strategy_name", "training_dataset_versions", ["strategy_name"], unique=False)

    op.create_table(
        "training_dataset_rows",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("dataset_version", sa.String(length=40), nullable=False),
        sa.Column("row_key", sa.String(length=64), nullable=False),
        sa.Column("decision_date", sa.Date(), nullable=False),
        sa.Column("symbol", sa.String(length=50), nullable=False),
        sa.Column(
            "asset_class",
            postgresql.ENUM("STOCK", "CRYPTO", name="asset_class_enum", create_type=False),
            nullable=False,
        ),
        sa.Column("timeframe", sa.String(length=10), nullable=False),
        sa.Column("strategy_name", sa.String(length=50), nullable=False),
        sa.Column("source_label", sa.String(length=30), nullable=False),
        sa.Column("entry_candle_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("feature_version", sa.String(length=30), nullable=False),
        sa.Column("replay_version", sa.String(length=30), nullable=False),
        sa.Column("label_version", sa.String(length=30), nullable=False),
        sa.Column("feature_values_json", sa.JSON(), nullable=False),
        sa.Column("label_values_json", sa.JSON(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["dataset_version"], ["training_dataset_versions.dataset_version"]),
        sa.UniqueConstraint("dataset_version", "row_key", name="uq_training_dataset_row"),
    )
    op.create_index("ix_training_dataset_rows_dataset_version", "training_dataset_rows", ["dataset_version"], unique=False)
    op.create_index("ix_training_dataset_rows_decision_date", "training_dataset_rows", ["decision_date"], unique=False)
    op.create_index("ix_training_dataset_rows_symbol", "training_dataset_rows", ["symbol"], unique=False)
    op.create_index("ix_training_dataset_rows_asset_class", "training_dataset_rows", ["asset_class"], unique=False)
    op.create_index("ix_training_dataset_rows_timeframe", "training_dataset_rows", ["timeframe"], unique=False)
    op.create_index("ix_training_dataset_rows_strategy_name", "training_dataset_rows", ["strategy_name"], unique=False)
    op.create_index("ix_training_dataset_rows_source_label", "training_dataset_rows", ["source_label"], unique=False)
    op.create_index("ix_training_dataset_rows_entry_candle_time", "training_dataset_rows", ["entry_candle_time"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_training_dataset_rows_entry_candle_time", table_name="training_dataset_rows")
    op.drop_index("ix_training_dataset_rows_source_label", table_name="training_dataset_rows")
    op.drop_index("ix_training_dataset_rows_strategy_name", table_name="training_dataset_rows")
    op.drop_index("ix_training_dataset_rows_timeframe", table_name="training_dataset_rows")
    op.drop_index("ix_training_dataset_rows_asset_class", table_name="training_dataset_rows")
    op.drop_index("ix_training_dataset_rows_symbol", table_name="training_dataset_rows")
    op.drop_index("ix_training_dataset_rows_decision_date", table_name="training_dataset_rows")
    op.drop_index("ix_training_dataset_rows_dataset_version", table_name="training_dataset_rows")
    op.drop_table("training_dataset_rows")

    op.drop_index("ix_training_dataset_versions_strategy_name", table_name="training_dataset_versions")
    op.drop_index("ix_training_dataset_versions_source_label", table_name="training_dataset_versions")
    op.drop_index("ix_training_dataset_versions_timeframe", table_name="training_dataset_versions")
    op.drop_index("ix_training_dataset_versions_asset_class", table_name="training_dataset_versions")
    op.drop_table("training_dataset_versions")
