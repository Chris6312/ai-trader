from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ai_research import BacktestingPolicyVersion
from app.services.historical.historical_backtesting_policy_schemas import (
    BacktestingPolicyVersionRecord,
    HistoricalBacktestingPolicy,
    ResolvedBacktestingPolicyRecord,
)
from app.services.historical.historical_label_schemas import HistoricalLabelPolicy


class HistoricalBacktestingPolicyService:
    def __init__(
        self,
        session: Session,
        *,
        policy: HistoricalBacktestingPolicy | None = None,
        label_policy: HistoricalLabelPolicy | None = None,
    ) -> None:
        self._session = session
        self._label_policy = label_policy or HistoricalLabelPolicy(
            label_version="12d_v1",
            policy_name="baseline_replay_success",
            success_threshold_return=Decimal("0.01"),
            max_drawdown_return=Decimal("0.02"),
            require_target_before_stop=False,
            max_hold_bars=5,
        )
        self._policy = policy or HistoricalBacktestingPolicy(
            policy_version="12e_policy_v1",
            policy_name="baseline_backtesting_policy",
            replay_policy_version="12c_policy_v1",
            label_version=self._label_policy.label_version,
            evaluation_window_bars=self._label_policy.max_hold_bars,
            success_threshold_return=self._label_policy.success_threshold_return,
            max_drawdown_return=self._label_policy.max_drawdown_return,
            require_target_before_stop=self._label_policy.require_target_before_stop,
            regime_adjustments={
                "trending_up": {"success_threshold_multiplier": "1.00", "max_hold_bars": 5},
                "risk_off": {"success_threshold_multiplier": "1.20", "max_hold_bars": 4},
            },
        )

    def register_policy(self) -> BacktestingPolicyVersionRecord:
        existing = self._session.get(BacktestingPolicyVersion, self._policy.policy_version)
        if existing is None:
            existing = BacktestingPolicyVersion(
                policy_version=self._policy.policy_version,
                policy_name=self._policy.policy_name,
                replay_policy_version=self._policy.replay_policy_version,
                label_version=self._policy.label_version,
                evaluation_window_bars=self._policy.evaluation_window_bars,
                success_threshold_return=self._policy.success_threshold_return,
                max_drawdown_return=self._policy.max_drawdown_return,
                require_target_before_stop=self._policy.require_target_before_stop,
                regime_adjustments_json=self._policy.regime_adjustments,
            )
            self._session.add(existing)
            self._session.flush()
        return self._to_record(existing)

    def list_policies(self) -> list[BacktestingPolicyVersionRecord]:
        rows = list(
            self._session.scalars(
                select(BacktestingPolicyVersion).order_by(BacktestingPolicyVersion.policy_version.asc())
            )
        )
        return [self._to_record(row) for row in rows]

    def get_policy(self, policy_version: str) -> BacktestingPolicyVersionRecord | None:
        row = self._session.get(BacktestingPolicyVersion, policy_version)
        if row is None:
            return None
        return self._to_record(row)

    def resolve_policy(self, policy_version: str | None = None) -> ResolvedBacktestingPolicyRecord:
        if policy_version is None:
            record = self.register_policy()
        else:
            existing = self.get_policy(policy_version)
            if existing is None:
                raise ValueError(f"unknown backtesting policy version: {policy_version}")
            record = existing
        return ResolvedBacktestingPolicyRecord(
            policy_version=record.policy_version,
            replay_policy_version=record.replay_policy_version,
            label_version=record.label_version,
            evaluation_window_bars=record.evaluation_window_bars,
            success_threshold_return=record.success_threshold_return,
            max_drawdown_return=record.max_drawdown_return,
            require_target_before_stop=record.require_target_before_stop,
            regime_adjustments=dict(record.regime_adjustments),
        )

    def _to_record(self, row: BacktestingPolicyVersion) -> BacktestingPolicyVersionRecord:
        return BacktestingPolicyVersionRecord(
            policy_version=row.policy_version,
            policy_name=row.policy_name,
            replay_policy_version=row.replay_policy_version,
            label_version=row.label_version,
            evaluation_window_bars=row.evaluation_window_bars,
            success_threshold_return=row.success_threshold_return,
            max_drawdown_return=row.max_drawdown_return,
            require_target_before_stop=row.require_target_before_stop,
            regime_adjustments=dict(row.regime_adjustments_json),
            created_at=row.created_at,
        )
