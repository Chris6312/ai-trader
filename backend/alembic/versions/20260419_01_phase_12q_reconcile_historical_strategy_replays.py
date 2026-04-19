"""phase 12q reconcile historical strategy replay schema

Revision ID: 20260419_01
Revises: 20260418_09
Create Date: 2026-04-19
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "20260419_01"
down_revision = "20260418_09"
branch_labels = None
depends_on = None

_TABLE_NAME = "historical_strategy_replays"
_OLD_UNIQUE = "uq_historical_strategy_replays_unique"
_NEW_UNIQUE = "uq_historical_strategy_replay_row"


def _column_names() -> set[str]:
    inspector = inspect(op.get_bind())
    return {column["name"] for column in inspector.get_columns(_TABLE_NAME)}


def _index_names() -> set[str]:
    inspector = inspect(op.get_bind())
    return {index["name"] for index in inspector.get_indexes(_TABLE_NAME)}


def _unique_constraint_names() -> set[str]:
    inspector = inspect(op.get_bind())
    return {constraint["name"] for constraint in inspector.get_unique_constraints(_TABLE_NAME)}


def upgrade() -> None:
    column_names = _column_names()

    with op.batch_alter_table(_TABLE_NAME) as batch_op:
        if "strategy_key" in column_names and "strategy_name" not in column_names:
            batch_op.alter_column("strategy_key", new_column_name="strategy_name")
        if "entry_time" in column_names and "entry_candle_time" not in column_names:
            batch_op.alter_column("entry_time", new_column_name="entry_candle_time")
        if "exit_time" in column_names and "exit_candle_time" not in column_names:
            batch_op.alter_column("exit_time", new_column_name="exit_candle_time")
        if "mfe" in column_names and "max_favorable_excursion" not in column_names:
            batch_op.alter_column("mfe", new_column_name="max_favorable_excursion")
        if "mae" in column_names and "max_adverse_excursion" not in column_names:
            batch_op.alter_column("mae", new_column_name="max_adverse_excursion")
        if "checks_json" in column_names and "strategy_checks_json" not in column_names:
            batch_op.alter_column("checks_json", new_column_name="strategy_checks_json")
        if "indicators_json" in column_names and "strategy_indicators_json" not in column_names:
            batch_op.alter_column("indicators_json", new_column_name="strategy_indicators_json")

    column_names = _column_names()

    with op.batch_alter_table(_TABLE_NAME) as batch_op:
        if "source_label" not in column_names:
            batch_op.add_column(sa.Column("source_label", sa.String(length=30), nullable=True))
        if "entry_confidence" not in column_names:
            batch_op.add_column(sa.Column("entry_confidence", sa.Numeric(12, 8), nullable=True))
        if "risk_approved" not in column_names:
            batch_op.add_column(sa.Column("risk_approved", sa.Boolean(), nullable=True))
        if "strategy_summary" not in column_names:
            batch_op.add_column(sa.Column("strategy_summary", sa.String(length=255), nullable=True))
        if "risk_rejection_reason" not in column_names:
            batch_op.add_column(sa.Column("risk_rejection_reason", sa.String(length=50), nullable=True))

    op.execute(
        sa.text(
            """
            UPDATE historical_strategy_replays
            SET source_label = CASE
                WHEN asset_class = 'stock' THEN 'alpaca'
                WHEN asset_class = 'crypto' THEN 'kraken_csv'
                ELSE 'unknown'
            END
            WHERE source_label IS NULL
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE historical_strategy_replays
            SET entry_confidence = 1.0
            WHERE entry_confidence IS NULL
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE historical_strategy_replays
            SET risk_approved = TRUE
            WHERE risk_approved IS NULL
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE historical_strategy_replays
            SET strategy_summary = strategy_name
            WHERE strategy_summary IS NULL
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE historical_strategy_replays
            SET exit_candle_time = entry_candle_time
            WHERE exit_candle_time IS NULL
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE historical_strategy_replays
            SET exit_price = entry_price
            WHERE exit_price IS NULL
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE historical_strategy_replays
            SET exit_reason = 'unknown'
            WHERE exit_reason IS NULL OR btrim(exit_reason) = ''
            """
        )
    )

    with op.batch_alter_table(_TABLE_NAME) as batch_op:
        batch_op.alter_column(
            "symbol",
            existing_type=sa.String(length=32),
            type_=sa.String(length=50),
            existing_nullable=False,
        )
        batch_op.alter_column(
            "timeframe",
            existing_type=sa.String(length=16),
            type_=sa.String(length=10),
            existing_nullable=False,
        )
        batch_op.alter_column(
            "strategy_name",
            existing_type=sa.String(length=64),
            type_=sa.String(length=50),
            existing_nullable=False,
            nullable=False,
        )
        batch_op.alter_column(
            "source_label",
            existing_type=sa.String(length=30),
            nullable=False,
        )
        batch_op.alter_column(
            "replay_version",
            existing_type=sa.String(length=32),
            type_=sa.String(length=30),
            existing_nullable=False,
        )
        batch_op.alter_column(
            "policy_version",
            existing_type=sa.String(length=32),
            type_=sa.String(length=30),
            existing_nullable=False,
        )
        batch_op.alter_column(
            "exit_candle_time",
            existing_type=sa.DateTime(timezone=True),
            nullable=False,
        )
        batch_op.alter_column(
            "entry_price",
            existing_type=sa.Numeric(18, 8),
            type_=sa.Numeric(20, 8),
            existing_nullable=False,
        )
        batch_op.alter_column(
            "exit_price",
            existing_type=sa.Numeric(18, 8),
            type_=sa.Numeric(20, 8),
            existing_nullable=True,
            nullable=False,
        )
        batch_op.alter_column(
            "stop_price",
            existing_type=sa.Numeric(18, 8),
            type_=sa.Numeric(20, 8),
            existing_nullable=False,
        )
        batch_op.alter_column(
            "target_price",
            existing_type=sa.Numeric(18, 8),
            type_=sa.Numeric(20, 8),
            existing_nullable=False,
        )
        batch_op.alter_column(
            "entry_confidence",
            existing_type=sa.Numeric(12, 8),
            nullable=False,
        )
        batch_op.alter_column(
            "risk_approved",
            existing_type=sa.Boolean(),
            nullable=False,
        )
        batch_op.alter_column(
            "exit_reason",
            existing_type=sa.String(length=32),
            type_=sa.String(length=30),
            existing_nullable=True,
            nullable=False,
        )
        batch_op.alter_column(
            "max_favorable_excursion",
            existing_type=sa.Numeric(18, 8),
            type_=sa.Numeric(12, 8),
            existing_nullable=False,
        )
        batch_op.alter_column(
            "max_adverse_excursion",
            existing_type=sa.Numeric(18, 8),
            type_=sa.Numeric(12, 8),
            existing_nullable=False,
        )
        batch_op.alter_column(
            "gross_return",
            existing_type=sa.Numeric(18, 8),
            type_=sa.Numeric(12, 8),
            existing_nullable=False,
        )
        batch_op.alter_column(
            "strategy_summary",
            existing_type=sa.String(length=255),
            nullable=False,
        )

    unique_constraints = _unique_constraint_names()
    with op.batch_alter_table(_TABLE_NAME) as batch_op:
        if _OLD_UNIQUE in unique_constraints:
            batch_op.drop_constraint(_OLD_UNIQUE, type_="unique")
        if _NEW_UNIQUE not in unique_constraints:
            batch_op.create_unique_constraint(
                _NEW_UNIQUE,
                [
                    "decision_date",
                    "symbol",
                    "asset_class",
                    "timeframe",
                    "strategy_name",
                    "entry_candle_time",
                    "replay_version",
                ],
            )

    index_names = _index_names()
    with op.batch_alter_table(_TABLE_NAME) as batch_op:
        if "ix_historical_strategy_replays_decision_date" not in index_names:
            batch_op.create_index("ix_historical_strategy_replays_decision_date", ["decision_date"], unique=False)
        if "ix_historical_strategy_replays_symbol" not in index_names:
            batch_op.create_index("ix_historical_strategy_replays_symbol", ["symbol"], unique=False)
        if "ix_historical_strategy_replays_asset_class" not in index_names:
            batch_op.create_index("ix_historical_strategy_replays_asset_class", ["asset_class"], unique=False)
        if "ix_historical_strategy_replays_timeframe" not in index_names:
            batch_op.create_index("ix_historical_strategy_replays_timeframe", ["timeframe"], unique=False)
        if "ix_historical_strategy_replays_strategy_name" not in index_names:
            batch_op.create_index("ix_historical_strategy_replays_strategy_name", ["strategy_name"], unique=False)
        if "ix_historical_strategy_replays_source_label" not in index_names:
            batch_op.create_index("ix_historical_strategy_replays_source_label", ["source_label"], unique=False)
        if "ix_historical_strategy_replays_replay_version" not in index_names:
            batch_op.create_index("ix_historical_strategy_replays_replay_version", ["replay_version"], unique=False)
        if "ix_historical_strategy_replays_entry_candle_time" not in index_names:
            batch_op.create_index("ix_historical_strategy_replays_entry_candle_time", ["entry_candle_time"], unique=False)


def downgrade() -> None:
    index_names = _index_names()
    with op.batch_alter_table(_TABLE_NAME) as batch_op:
        for index_name in (
            "ix_historical_strategy_replays_entry_candle_time",
            "ix_historical_strategy_replays_replay_version",
            "ix_historical_strategy_replays_source_label",
            "ix_historical_strategy_replays_strategy_name",
            "ix_historical_strategy_replays_timeframe",
            "ix_historical_strategy_replays_asset_class",
            "ix_historical_strategy_replays_symbol",
            "ix_historical_strategy_replays_decision_date",
        ):
            if index_name in index_names:
                batch_op.drop_index(index_name)

    unique_constraints = _unique_constraint_names()
    with op.batch_alter_table(_TABLE_NAME) as batch_op:
        if _NEW_UNIQUE in unique_constraints:
            batch_op.drop_constraint(_NEW_UNIQUE, type_="unique")
        if _OLD_UNIQUE not in unique_constraints:
            batch_op.create_unique_constraint(
                _OLD_UNIQUE,
                [
                    "decision_date",
                    "asset_class",
                    "symbol",
                    "strategy_name",
                    "timeframe",
                    "entry_candle_time",
                ],
            )

        batch_op.alter_column(
            "symbol",
            existing_type=sa.String(length=50),
            type_=sa.String(length=32),
            existing_nullable=False,
        )
        batch_op.alter_column(
            "timeframe",
            existing_type=sa.String(length=10),
            type_=sa.String(length=16),
            existing_nullable=False,
        )
        batch_op.alter_column(
            "strategy_name",
            existing_type=sa.String(length=50),
            type_=sa.String(length=64),
            existing_nullable=False,
        )
        batch_op.alter_column(
            "replay_version",
            existing_type=sa.String(length=30),
            type_=sa.String(length=32),
            existing_nullable=False,
        )
        batch_op.alter_column(
            "policy_version",
            existing_type=sa.String(length=30),
            type_=sa.String(length=32),
            existing_nullable=False,
        )
        batch_op.alter_column(
            "entry_price",
            existing_type=sa.Numeric(20, 8),
            type_=sa.Numeric(18, 8),
            existing_nullable=False,
        )
        batch_op.alter_column(
            "exit_price",
            existing_type=sa.Numeric(20, 8),
            type_=sa.Numeric(18, 8),
            existing_nullable=False,
            nullable=True,
        )
        batch_op.alter_column(
            "stop_price",
            existing_type=sa.Numeric(20, 8),
            type_=sa.Numeric(18, 8),
            existing_nullable=False,
        )
        batch_op.alter_column(
            "target_price",
            existing_type=sa.Numeric(20, 8),
            type_=sa.Numeric(18, 8),
            existing_nullable=False,
        )
        batch_op.alter_column(
            "exit_reason",
            existing_type=sa.String(length=30),
            type_=sa.String(length=32),
            existing_nullable=False,
            nullable=True,
        )
        batch_op.alter_column(
            "max_favorable_excursion",
            existing_type=sa.Numeric(12, 8),
            type_=sa.Numeric(18, 8),
            existing_nullable=False,
        )
        batch_op.alter_column(
            "max_adverse_excursion",
            existing_type=sa.Numeric(12, 8),
            type_=sa.Numeric(18, 8),
            existing_nullable=False,
        )
        batch_op.alter_column(
            "gross_return",
            existing_type=sa.Numeric(12, 8),
            type_=sa.Numeric(18, 8),
            existing_nullable=False,
        )
        batch_op.alter_column(
            "exit_candle_time",
            existing_type=sa.DateTime(timezone=True),
            nullable=True,
        )

    column_names = _column_names()
    with op.batch_alter_table(_TABLE_NAME) as batch_op:
        if "strategy_indicators_json" in column_names and "indicators_json" not in column_names:
            batch_op.alter_column("strategy_indicators_json", new_column_name="indicators_json")
        if "strategy_checks_json" in column_names and "checks_json" not in column_names:
            batch_op.alter_column("strategy_checks_json", new_column_name="checks_json")
        if "max_adverse_excursion" in column_names and "mae" not in column_names:
            batch_op.alter_column("max_adverse_excursion", new_column_name="mae")
        if "max_favorable_excursion" in column_names and "mfe" not in column_names:
            batch_op.alter_column("max_favorable_excursion", new_column_name="mfe")
        if "exit_candle_time" in column_names and "exit_time" not in column_names:
            batch_op.alter_column("exit_candle_time", new_column_name="exit_time")
        if "entry_candle_time" in column_names and "entry_time" not in column_names:
            batch_op.alter_column("entry_candle_time", new_column_name="entry_time")
        if "strategy_name" in column_names and "strategy_key" not in column_names:
            batch_op.alter_column("strategy_name", new_column_name="strategy_key")

    column_names = _column_names()
    with op.batch_alter_table(_TABLE_NAME) as batch_op:
        for column_name in (
            "risk_rejection_reason",
            "strategy_summary",
            "risk_approved",
            "entry_confidence",
            "source_label",
        ):
            if column_name in column_names:
                batch_op.drop_column(column_name)
