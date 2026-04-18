"""phase 12e backtesting policy versions

Revision ID: 20260418_08
Revises: 20260418_07
Create Date: 2026-04-18
"""

from alembic import op
import sqlalchemy as sa


revision = "20260418_08"
down_revision = "20260418_07"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "backtesting_policy_versions",
        sa.Column("policy_version", sa.String(length=30), primary_key=True),
        sa.Column("policy_name", sa.String(length=50), nullable=False),
        sa.Column("replay_policy_version", sa.String(length=30), nullable=False),
        sa.Column("label_version", sa.String(length=30), nullable=False),
        sa.Column("evaluation_window_bars", sa.Integer(), nullable=False),
        sa.Column("success_threshold_return", sa.Numeric(12, 8), nullable=False),
        sa.Column("max_drawdown_return", sa.Numeric(12, 8), nullable=False),
        sa.Column("require_target_before_stop", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("regime_adjustments_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )


def downgrade() -> None:
    op.drop_table("backtesting_policy_versions")
