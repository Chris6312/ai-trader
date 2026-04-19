"""phase 12c historical strategy replays

Revision ID: 20260418_06
Revises: 20260418_05
Create Date: 2026-04-18
"""

from alembic import op
import sqlalchemy as sa


revision = "20260418_06"
down_revision = "20260418_05"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "historical_strategy_replays",
        sa.Column("id", sa.Integer(), primary_key=True),

        sa.Column("decision_date", sa.Date(), nullable=False),

        sa.Column(
            "asset_class",
            sa.Enum(
                "stock",
                "crypto",
                name="asset_class_enum",
                native_enum=False
            ),
            nullable=False,
        ),

        sa.Column("symbol", sa.String(length=32), nullable=False),

        sa.Column("strategy_key", sa.String(length=64), nullable=False),

        sa.Column("timeframe", sa.String(length=16), nullable=False),

        sa.Column("entry_time", sa.DateTime(timezone=True), nullable=False),

        sa.Column("exit_time", sa.DateTime(timezone=True), nullable=True),

        sa.Column("entry_price", sa.Numeric(18, 8), nullable=False),

        sa.Column("exit_price", sa.Numeric(18, 8), nullable=True),

        sa.Column("stop_price", sa.Numeric(18, 8), nullable=False),

        sa.Column("target_price", sa.Numeric(18, 8), nullable=False),

        sa.Column("exit_reason", sa.String(length=32), nullable=True),

        sa.Column("hold_bars", sa.Integer(), nullable=False),

        sa.Column("mfe", sa.Numeric(18, 8), nullable=False),

        sa.Column("mae", sa.Numeric(18, 8), nullable=False),

        sa.Column("gross_return", sa.Numeric(18, 8), nullable=False),

        sa.Column("checks_json", sa.JSON(), nullable=False),

        sa.Column("indicators_json", sa.JSON(), nullable=False),

        sa.Column("policy_version", sa.String(length=32), nullable=False),

        sa.Column("replay_version", sa.String(length=32), nullable=False),

        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),

        sa.UniqueConstraint(
            "decision_date",
            "asset_class",
            "symbol",
            "strategy_key",
            "timeframe",
            "entry_time",
            name="uq_historical_strategy_replays_unique",
        ),
    )


def downgrade() -> None:
    op.drop_table("historical_strategy_replays")